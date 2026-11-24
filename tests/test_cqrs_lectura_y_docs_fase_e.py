r"""Fase E (TDD): proyecciones rapidas de lectura (CQRS) y coherencia documental.

Cubre:
- DZ-05: `vault/product_cli.py` no importa dependencias pesadas al arrancar (`vault --version`).
- DZ-07: `vault_search` (indexado y live) excluye `00_System/change-log.md` por defecto
  (devolviendolo solo con `--folder 00_System` o `--incluir-historico`).
- DZ-08: `ServicioReindex` proyecta `aliases` y `contradicts` en `search-index.json`, y
  `vault_context_pack` consume esa proyeccion en O(1) sin barrer todo el disco (`_censo`),
  manteniendo fallback transparente ante indices legados.
- C-01..C-10: cierre de contradicciones documentales verificadas en auditoria.
"""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path

from apoyo import ROOT, SCRIPTS, correr_python, correr_tool, escribir_nota
from vault.kernel.version import CURRENT_VERSION


def _cli(vault: Path, script: str, *args: str, env=None):
    return correr_tool(script, *args, vault=vault, cwd=SCRIPTS, env=env)


def test_dz05_product_cli_no_importa_dependencias_pesadas_al_arrancar():
    codigo = textwrap.dedent(
        """\
        import json, sys
        import vault.product_cli  # noqa: F401
        pesados = [
            "importlib.metadata",
            "vault.ciclo_de_vida.producto",
            "vault.meta_toolkit.catalogo_producto",
            "vault.meta_toolkit.resolucion_producto",
            "vault.kernel.adaptadores",
        ]
        cargados = [m for m in pesados if m in sys.modules]
        print(json.dumps({"cargados": cargados}))
        """
    )
    proc = correr_python("-c", codigo)
    assert proc.returncode == 0, proc.stderr
    datos = json.loads(proc.stdout)
    assert datos["cargados"] == [], f"Imports eager en arranque: {datos['cargados']}"

    ver = correr_python("-m", "vault", "--version")
    assert ver.returncode == 0, ver.stderr
    assert CURRENT_VERSION.lstrip("v") in ver.stdout.strip()


def test_dz07_vault_search_excluye_changelog_de_sistema_por_defecto(tmp_path):
    vault = tmp_path / "vault"
    (vault / "00_System").mkdir(parents=True)
    (vault / "07_Knowledge").mkdir(parents=True)
    (vault / "99_Index").mkdir(parents=True)

    escribir_nota(
        vault,
        "07_Knowledge/nota-real.md",
        {
            "title": "Arquitectura del servicio",
            "id": "k-1",
            "type": "knowledge",
            "status": "active",
            "tags": ["arquitectura"],
        },
        "# Arquitectura del servicio\n\nContenido operativo normal.\n",
    )
    (vault / "00_System" / "change-log.md").write_text(
        textwrap.dedent(
            """\
            ---
            title: "Change Log"
            type: system
            status: active
            ---
            # Change Log

            | Fecha | Accion |
            |---|---|
            | 2026-11-23 | token_bitacora_unica |
            """
        ),
        encoding="utf-8",
    )

    assert _cli(vault, "vault_reindex.py").envelope["ok"]

    # 1. Busqueda indexada por defecto: excluye 00_System/change-log.md
    r_idx = _cli(vault, "vault_search.py", "--query", "token_bitacora_unica").envelope
    assert r_idx["ok"] is True, r_idx
    assert r_idx["results"] == [], f"change-log.md colo ruido: {r_idx['results']}"
    assert r_idx.get("history_excluded", {}).get("by_reason", {}).get("system_log") == 1, r_idx

    # 2. Busqueda live (MCP): tambien excluye 00_System/change-log.md por defecto
    r_live = _cli(
        vault,
        "vault_search.py",
        "--query", "token_bitacora_unica",
        env={**os.environ, "VAULT_MCP_LIVE_SEARCH": "1"},
    ).envelope
    assert r_live["ok"] is True, r_live
    assert r_live["results"] == [], f"live search colo change-log.md: {r_live['results']}"

    # 3. Busqueda explicita en --folder 00_System o --incluir-historico si lo encuentra
    r_sys = _cli(
        vault, "vault_search.py", "--query", "token_bitacora_unica", "--folder", "00_System"
    ).envelope
    assert r_sys["ok"] is True and any(
        x["path"] == "00_System/change-log.md" for x in r_sys["results"]
    ), r_sys

    r_hist = _cli(
        vault, "vault_search.py", "--query", "token_bitacora_unica", "--incluir-historico"
    ).envelope
    assert r_hist["ok"] is True and any(
        x["path"] == "00_System/change-log.md" for x in r_hist["results"]
    ), r_hist


def test_dz08_context_pack_usa_proyeccion_de_indice_sin_barrido_de_disco(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    (vault / "00_System").mkdir(parents=True)
    (vault / "07_Knowledge").mkdir(parents=True)
    (vault / "99_Index").mkdir(parents=True)

    escribir_nota(
        vault,
        "07_Knowledge/postura-a.md",
        {
            "title": "Postura A sobre cache distribuida",
            "id": "k-a",
            "type": "knowledge",
            "status": "active",
            "aliases": ["alias-postura-a"],
            "tags": ["cache"],
        },
        "# Postura A sobre cache distribuida\n\nUsar cache local determinista.\n",
    )
    escribir_nota(
        vault,
        "07_Knowledge/postura-b.md",
        {
            "title": "Postura B sobre cache distribuida",
            "id": "k-b",
            "type": "knowledge",
            "status": "active",
            "contradicts": ["[[alias-postura-a]]"],
            "tags": ["cache"],
        },
        "# Postura B sobre cache distribuida\n\nContradice la postura A en escenarios multi-nodo.\n",
    )

    assert _cli(vault, "vault_reindex.py", "--graph").envelope["ok"]

    idx = json.loads((vault / "99_Index" / "search-index.json").read_text(encoding="utf-8"))
    por_ruta = {n["path"]: n for n in idx["notes"]}
    assert por_ruta["07_Knowledge/postura-a.md"]["aliases"] == ["alias-postura-a"]
    assert por_ruta["07_Knowledge/postura-b.md"]["contradicts"] == ["alias-postura-a"]

    import vault_context_pack as vcp
    import vault_io

    monkeypatch.setenv("VAULT_ROOT", str(vault))
    vault_io.set_vault_root(vault)

    # Si el indice es fresco y trae la proyeccion, _censo() NO debe barrer el disco
    llamadas_censo = []
    original_censo = vcp._censo

    def detectar_censo():
        llamadas_censo.append(True)
        return original_censo()

    monkeypatch.setattr(vcp, "_censo", detectar_censo)

    pack = vcp.vault_context_pack("Postura B sobre cache distribuida", top_k=1, budget_tokens=2000)
    assert pack["ok"] is True, pack
    incluidas = {n["path"] for n in pack["included"]}
    assert "07_Knowledge/postura-a.md" in incluidas
    assert "07_Knowledge/postura-b.md" in incluidas
    assert llamadas_censo == [], "vault_context_pack ejecuto _censo() teniendo proyeccion fresca"

    # Fallback ante indice legado sin campos de proyeccion: usa _censo() y sigue trayendo ambos lados
    for row in idx["notes"]:
        row.pop("aliases", None)
        row.pop("contradicts", None)
    (vault / "99_Index" / "search-index.json").write_text(json.dumps(idx), encoding="utf-8")

    pack_legado = vcp.vault_context_pack("Postura B sobre cache distribuida", top_k=1, budget_tokens=2000)
    assert pack_legado["ok"] is True, pack_legado
    incluidas_legado = {n["path"] for n in pack_legado["included"]}
    assert "07_Knowledge/postura-a.md" in incluidas_legado
    assert "07_Knowledge/postura-b.md" in incluidas_legado
    assert len(llamadas_censo) >= 1, "el indice legado debia activar fallback a _censo()"


def test_docs_sin_contradicciones_fase_e():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "--host" in readme and "--tls-cert" in readme

    inst = (ROOT / "docs" / "INSTALACION-LIMPIA.md").read_text(encoding="utf-8")
    assert inst.index("El README explica") < inst.index("### Búsqueda de notas desde MCP")

    const = (ROOT / "docs" / "architecture" / "CONSTITUCION-ARQUITECTONICA.md").read_text(encoding="utf-8")
    assert "Hasta entonces es DRAFT" not in const
    assert "82 paquetes" not in const
    assert "97 paquetes" in const

    skill_san = (ROOT / "agent" / "skills" / "vault-sanacion" / "SKILL.md").read_text(encoding="utf-8")
    assert "and macOS" not in skill_san

    cat_qg = (ROOT / "audits" / "fase2" / "catalogo-qg.yaml").read_text(encoding="utf-8")
    assert "26 puertas" not in cat_qg and "26/26" not in cat_qg
    assert "29 puertas" in cat_qg

    carriles_doc = (ROOT / "docs" / "CARRILES.md").read_text(encoding="utf-8")
    assert "colector_qg_sin_primera_corrida" not in carriles_doc

    ctx_doc = (ROOT / "docs" / "CONTRATO-CONTEXT-PACK.md").read_text(encoding="utf-8")
    assert "history_excluded" in ctx_doc and "--incluir-historico" in ctx_doc

    docs_readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    for enlace in ("CARRILES.md", "CONTRATO-CONTEXT-PACK.md", "DISPONIBILIDAD-DE-TOOLS.md"):
        assert enlace in docs_readme, f"Falta {enlace} en docs/README.md"

    overview = (ROOT / "docs" / "product" / "overview.md").read_text(encoding="utf-8")
    assert "v40.x" not in overview and "41.x (próxima)" not in overview
