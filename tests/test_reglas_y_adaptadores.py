"""La política del vault: se persiste, se entrega y se aplica — por separado.

Propuestas `persistent-custom-rules-and-agent-integration` y
`multi-provider-vault-policy-adapters`. La distinción que fijan estos tests:

- **Persistencia:** la regla vive en el vault (`00_System/inmutable.json`,
  `00_System/reglas.json`, `17_Preferences/`).
- **Entrega:** un adaptador la lleva al fichero que cada cliente lee
  (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `copilot-instructions.md`).
- **Enforcing:** la frontera de mutación (`vault_write` / `vault_delete`).
  Un prompt no es un permiso, y un agente que no cargue el adaptador sigue
  sujeto a la misma política.

Y lo que se prueba aquí: que la regla **se aplica donde se muta** (borrado),
que un fichero ilegible bloquea la mutacion, y que el adaptador dice lo
que es y no se pisa sin permiso.
"""

from __future__ import annotations

import json
import os

import pytest

from apoyo import ROOT as REPO_ROOT, correr_python  # el conftest ya pone el path

import vault_delete
import vault_io
import vault_preferences
from vault.kernel.errores import ERROR_CATALOG


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    for seccion in ("00_System", "19_Audits", "07_Knowledge"):
        (raiz / seccion).mkdir(parents=True)
    previa = vault_io.set_vault_root(raiz)
    yield raiz
    vault_io.set_vault_root(previa)


def _nota(vault, seccion, nombre):
    ruta = vault / seccion / nombre
    ruta.write_text(
        f"---\ntitle: {nombre}\n---\n\nContenido de la nota de prueba.\n",
        encoding="utf-8")
    return ruta


def _reglas(vault, datos):
    (vault / "00_System" / "reglas.json").write_text(json.dumps(datos),
                                                     encoding="utf-8")


def test_sin_reglas_no_se_prohibe_nada(vault):
    """Ante la duda no se bloquea a nadie."""
    nota = _nota(vault, "19_Audits", "nota.md")
    assert vault_io.reglas_declaradas(vault) == {"inmutable": [], "no_borrar": []}
    assert vault_io.nota_no_se_borra(nota, vault) is None


def test_no_borrar_se_aplica_en_la_frontera_de_mutacion(vault):
    """Persistir la regla no basta: se aplica donde se borra."""
    _reglas(vault, {"no_borrar": ["19_Audits"]})
    nota = _nota(vault, "19_Audits", "nota.md")

    res = vault_delete.vault_delete(
        "19_Audits/nota.md", "prueba de la valla", agent="opencode")

    assert res.get("ok") is False, res
    assert res.get("error_code") == "DELETE_FORBIDDEN", res
    assert nota.is_file(), "la nota se borro con la politica en contra"


def test_una_seccion_no_declarada_se_puede_borrar(vault):
    """La valla es por seccion, no global."""
    _reglas(vault, {"no_borrar": ["19_Audits"]})
    nota = _nota(vault, "07_Knowledge", "libre.md")

    res = vault_delete.vault_delete(
        "07_Knowledge/libre.md", "prueba de la valla", agent="opencode",
        trash_only=True)

    assert res.get("ok"), res
    assert not nota.exists(), "la nota no se movio a cuarentena"


def test_un_fichero_de_reglas_ilegible_falla_cerrado(vault):
    """Una politica corrupta no equivale a una politica ausente."""
    (vault / "00_System" / "reglas.json").write_text("{roto", encoding="utf-8")
    nota = _nota(vault, "19_Audits", "nota.md")
    with pytest.raises(vault_io.PoliticaInvalidaError):
        vault_io.nota_no_se_borra(nota, vault)


def test_las_reglas_leen_tambien_la_politica_ya_publicada(vault):
    """`inmutable.json` no se mueve: se suma a las reglas."""
    (vault / "00_System" / "inmutable.json").write_text(
        json.dumps({"secciones": ["18_Bugs"]}), encoding="utf-8")
    _reglas(vault, {"no_borrar": ["19_Audits"]})
    declaradas = vault_io.reglas_declaradas(vault)
    assert "18_Bugs" in declaradas["inmutable"]
    assert "19_Audits" in declaradas["no_borrar"]


def test_el_codigo_de_error_esta_en_el_catalogo():
    assert "DELETE_FORBIDDEN" in ERROR_CATALOG
    assert ERROR_CATALOG["DELETE_FORBIDDEN"]["category"] == "governance"


def test_el_adaptador_dice_que_es_entrega_y_no_pisa(vault, tmp_path):
    """El fichero que lee un cliente no es la frontera de permisos."""
    destino = tmp_path / "proyecto"
    destino.mkdir()
    (destino / "AGENTS.md").write_text("mio", encoding="utf-8")

    res = vault_preferences.vault_preferences_adapters(str(destino))

    assert res.get("ok"), res
    estados = {a["adapter"]: a["estado"] for a in res["adapters"]}
    assert estados["AGENTS.md"] == "existente (no se toca)"
    assert (destino / "AGENTS.md").read_text(encoding="utf-8") == "mio"
    # Los demás sí se escriben, y dicen lo que son.
    claude = (destino / "CLAUDE.md").read_text(encoding="utf-8")
    assert "entrega" in claude and "no enforcing" in claude.lower()
    assert "frontera de mutación" in claude
    assert "Enforcing" not in claude or "no enforcing" in claude.lower()


def test_el_adaptador_publica_las_reglas_del_vault(vault, tmp_path):
    _reglas(vault, {"no_borrar": ["19_Audits"]})
    destino = tmp_path / "proyecto2"
    res = vault_preferences.vault_preferences_adapters(str(destino), force=True)
    assert res.get("ok"), res
    cuerpo = (destino / "GEMINI.md").read_text(encoding="utf-8")
    assert "19_Audits" in cuerpo, cuerpo[:400]
    assert "no se borra" in cuerpo


@pytest.mark.parametrize("failure", ["corrupt", "unreadable"])
def test_adaptadores_no_publican_politica_vacia_si_falla_la_lectura(vault, tmp_path, monkeypatch, failure):
    destino = tmp_path / "project"
    destino.mkdir()
    existing = destino / "AGENTS.md"
    existing.write_text("Manual instructions", encoding="utf-8")
    before = existing.read_bytes()
    if failure == "corrupt":
        (vault / "00_System" / "reglas.json").write_text("{broken", encoding="utf-8")
    else:
        def fail():
            raise OSError("PRIVATE-POLICY-PATH")
        monkeypatch.setattr(vault_io, "reglas_declaradas", fail)
    result = vault_preferences.vault_preferences_adapters(str(destino), force=True)
    assert result["ok"] is False
    assert "PRIVATE-POLICY-PATH" not in str(result)
    assert existing.read_bytes() == before
    assert sorted(p.name for p in destino.iterdir()) == ["AGENTS.md"]


@pytest.mark.parametrize("corrupt", [False, True])
def test_cli_adapters_aplica_politica_y_preserva_archivos_si_es_invalida(vault, tmp_path, corrupt):
    policy = vault / "00_System" / "reglas.json"
    policy.write_text("{broken" if corrupt else json.dumps({"no_borrar": ["19_Audits"]}), encoding="utf-8")
    target = tmp_path / "cli-project"
    target.mkdir()
    existing = target / "AGENTS.md"
    existing.write_text("Manual instructions", encoding="utf-8")
    env = {**os.environ, "VAULT_ROOT": str(vault), "PYTHONIOENCODING": "utf-8"}
    run = correr_python(str(REPO_ROOT / "scripts" / "vault_preferences.py"),
                        "--adapters", str(target), env=env, modo="text", timeout=60)
    payload = json.loads(run.stdout)
    assert existing.read_text(encoding="utf-8") == "Manual instructions"
    if corrupt:
        assert run.returncode != 0 and payload["ok"] is False
        assert payload["error_code"] == "INVALID_INPUT"
        assert sorted(p.name for p in target.iterdir()) == ["AGENTS.md"]
    else:
        assert run.returncode == 0 and payload["ok"] is True
        assert "19_Audits" in (target / "GEMINI.md").read_text(encoding="utf-8")


def test_un_adaptador_que_falla_a_mitad_se_informa_con_lo_ya_escrito(vault, tmp_path):
    """A partial write is reported with the adapters already written, never as ok."""
    destino = tmp_path / "proyecto"
    (destino / "GEMINI.md").mkdir(parents=True)  # a directory cannot be replaced by a file
    res = vault_preferences.vault_preferences_adapters(str(destino), force=True)
    assert res["ok"] is False and res["error_code"] == "FILE_WRITE_ERROR", res
    estados = {a["adapter"]: a["estado"] for a in res["adapters"]}
    assert estados == {"AGENTS.md": "escrito", "CLAUDE.md": "escrito", "GEMINI.md": "no escrito"}
    assert not list(destino.glob(".GEMINI.md.*")), "temporary files must not remain"


def test_un_symlink_colgante_no_se_sigue_sin_force(vault, tmp_path):
    destino = tmp_path / "proyecto"
    destino.mkdir()
    fuera = tmp_path / "fuera.md"
    try:
        (destino / "AGENTS.md").symlink_to(fuera)
    except OSError:
        pytest.skip("symlink creation requires a privilege this host lacks")
    res = vault_preferences.vault_preferences_adapters(str(destino))
    assert res.get("ok"), res
    assert {a["adapter"]: a["estado"] for a in res["adapters"]}["AGENTS.md"] == "existente (no se toca)"
    assert not fuera.exists()


def test_una_clave_desconocida_sin_obligacion_se_ignora_y_la_regla_se_aplica(vault):
    """S4: a vault that did not declare the policy mandatory keeps working (A3)."""
    _reglas(vault, {"no_borrar": ["19_Audits"], "comentario": "owner note"})
    nota = _nota(vault, "19_Audits", "nota.md")
    res = vault_delete.vault_delete("19_Audits/nota.md", "prueba", agent="opencode")
    assert res.get("error_code") == "DELETE_FORBIDDEN", res
    assert nota.is_file()
    libre = _nota(vault, "07_Knowledge", "libre.md")
    assert vault_delete.vault_delete("07_Knowledge/libre.md", "prueba", agent="opencode",
                                     trash_only=True).get("ok")
    assert not libre.exists()
    assert vault_io.claves_de_politica_ignoradas(vault) == ["00_System/reglas.json: comentario"]


@pytest.mark.parametrize("politica", [
    {"no_borrar": ["19_Audits"], "obligatoria": True, "no_borar": ["07_Knowledge"]},
    {"no_borrar": ["19_Audits"], "obligatoria": "yes"},
])
def test_una_politica_obligatoria_no_verificable_bloquea(vault, politica):
    _reglas(vault, politica)
    libre = _nota(vault, "07_Knowledge", "libre.md")
    with pytest.raises(vault_io.PoliticaInvalidaError):
        vault_io.reglas_declaradas(vault)
    res = vault_delete.vault_delete("07_Knowledge/libre.md", "prueba", agent="opencode",
                                    trash_only=True)
    assert res.get("ok") is False, res
    assert libre.is_file()


def test_la_auditoria_informa_la_clave_ignorada_sin_bloquear(vault):
    from vault.gobernanza.auditoria_runtime import auditar_runtime

    _reglas(vault, {"no_borrar": ["19_Audits"], "no_borar": ["07_Knowledge"]})
    hallazgos = [v for v in auditar_runtime(vault)["violations"] if v["norm"] == "AP-70"]
    assert hallazgos == [{
        "norm": "AP-70", "severity": "low", "path": "00_System/reglas.json",
        "detail": "Clave de politica ignorada (00_System/reglas.json: no_borar). Declarar "
                  "\"obligatoria\": true hace que una clave desconocida detenga las mutaciones."}]


def test_un_adaptador_con_un_secreto_no_se_escribe(vault, tmp_path, monkeypatch):
    """Adapters embed vault preferences: the canonical secret guard applies."""
    destino = tmp_path / "proyecto"
    destino.mkdir()
    token = "ghp_" + "a" * 36
    monkeypatch.setattr(vault_preferences, "_cuerpo_adapter",
                        lambda cliente, contexto, reglas: f"token: {token}\n")
    res = vault_preferences.vault_preferences_adapters(str(destino))
    assert res["ok"] is False and res["error_code"] == "SECRET_DETECTED", res
    assert token not in json.dumps(res)
    assert not any(destino.rglob("*.md")) and not list(destino.glob(".*adapter"))
