"""Los campos que el contrato exige y la nota no lleva se ponen, y se dice de dónde sale cada uno.

`vault_validate` decía qué faltaba y su pista era «edita la nota». Con 26
notas inválidas en el sandbox y una entrada a mano por campo, eso no es una
pista: es la razón por la que nadie lo arregla. Esta tool completa el hueco con
lo que el escritor habría puesto, sin tocar ningún valor que ya estaba, y se
niega a lo que no es suyo: un bloque que no parsea es de `vault_frontmatter_heal`
y un artefacto derivado no tiene contrato.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_contrato_nota as contrato  # noqa: E402
import vault_frontmatter_completar as completar_mod  # noqa: E402
import vault_validate  # noqa: E402
from vault_fundamentals_catalog import cia_por_defecto  # noqa: E402
from vault_norms_catalog import NORM_CATALOG  # noqa: E402


@pytest.fixture
def vault(tmp_path, monkeypatch):
    for seccion in ("00_System", "07_Knowledge"):
        (tmp_path / seccion).mkdir()
    monkeypatch.setattr(completar_mod, "get_vault_root", lambda: tmp_path)
    monkeypatch.setattr(vault_validate, "_raiz", lambda: tmp_path)
    monkeypatch.setattr(completar_mod, "fuera_de_sesion", lambda *a: None)
    monkeypatch.delenv("VAULT_AGENT", raising=False)
    return tmp_path


def _fm(ruta: Path) -> dict:
    texto = ruta.read_text(encoding="utf-8")
    return yaml.safe_load(texto.split("---\n", 2)[1])


def test_el_dry_run_no_escribe_y_lo_dice(vault):
    nota = vault / "07_Knowledge" / "jwt.md"
    original = "---\nid: a1\ntitle: JWT\n---\n\n# JWT\n"
    nota.write_text(original, encoding="utf-8")

    r = completar_mod.completar()
    assert r["completed_count"] == 1
    assert r["written_count"] == 0
    assert nota.read_text(encoding="utf-8") == original
    campos = r["completed"][0]["fields"]
    assert list(campos) == contrato.faltantes({"id": 1, "title": 1}, "07_Knowledge/jwt.md")
    assert {"type", "status"} <= set(campos)  # requeridos desde v41


def test_tras_aplicar_vault_validate_la_aprueba(vault):
    """El criterio es el del consumidor (AP-44): lo decide el validador, no la tool."""
    nota = vault / "07_Knowledge" / "jwt.md"
    nota.write_text("---\nid: a1\ntitle: JWT\n---\n\n# JWT\n", encoding="utf-8")
    assert vault_validate.validate_frontmatter(nota)["valid"] is False

    r = completar_mod.completar(apply=True)
    assert r["written_count"] == 1
    assert vault_validate.validate_frontmatter(nota)["valid"] is True


def test_lo_que_ya_estaba_no_se_toca(vault):
    nota = vault / "07_Knowledge" / "jwt.md"
    bloque = "id: a1\ntitle: 'JWT: tokens'\ncia_integrity: HIGH\ntags:\n- api\n- auth"
    nota.write_text(f"---\n{bloque}\n---\n\ncuerpo\n", encoding="utf-8")

    completar_mod.completar(apply=True)
    texto = nota.read_text(encoding="utf-8")
    assert texto.startswith(f"---\n{bloque}\n")
    assert texto.endswith("\n---\n\ncuerpo\n")
    datos = _fm(nota)
    assert datos["cia_integrity"] == "HIGH" and datos["tags"] == ["api", "auth"]


def test_cada_valor_declara_su_origen(vault, monkeypatch):
    nota = vault / "07_Knowledge" / "jwt.md"
    nota.write_text("---\nupdatedAt: 2026-01-02T03:04:05.000Z\n---\n\n# Tokens firmados\n",
                    encoding="utf-8")
    monkeypatch.setenv("VAULT_AGENT", "claude")

    campos = completar_mod.completar()["completed"][0]["fields"]
    assert campos["title"] == {"value": "Tokens firmados", "origin": "primer_h1"}
    assert campos["id"]["origin"] == "uuid4"
    # Una nota no se crea después de su última edición.
    assert campos["createdAt"] == {"value": "2026-01-02T03:04:05.000Z", "origin": "updatedAt"}
    assert "updatedAt" not in campos
    assert campos["agent"] == {"value": "claude", "origin": "VAULT_AGENT"}
    assert campos["cia_integrity"]["value"] == cia_por_defecto()["cia_integrity"]
    assert campos["tags"] == {"value": [], "origin": "por_defecto"}
    assert campos["status"] == {"value": contrato.POR_DEFECTO["status"], "origin": "por_defecto"}


def test_sin_h1_el_titulo_sale_del_fichero_y_el_agente_explicito_gana(vault, monkeypatch):
    nota = vault / "07_Knowledge" / "jwt-y-oauth.md"
    nota.write_text("---\nid: a1\n---\n\nsin encabezado\n", encoding="utf-8")
    monkeypatch.setenv("VAULT_AGENT", "otro")

    campos = completar_mod.completar(agent="yo")["completed"][0]["fields"]
    assert campos["title"] == {"value": "jwt-y-oauth", "origin": "nombre_de_fichero"}
    assert campos["agent"] == {"value": "yo", "origin": "--agent"}


def test_una_nota_sin_bloque_recibe_uno_entero(vault):
    """AP-28: sin bloque no hay campo que discutir; se pone el bloque entero."""
    nota = vault / "07_Knowledge" / "suelta.md"
    nota.write_text("# Suelta\n\ntexto\n", encoding="utf-8")

    completar_mod.completar(apply=True)
    texto = nota.read_text(encoding="utf-8")
    assert texto.startswith("---\n") and texto.endswith("---\n# Suelta\n\ntexto\n")
    assert vault_validate.validate_frontmatter(nota)["valid"] is True


def test_una_nota_de_sistema_solo_recibe_lo_de_su_clase(vault):
    nota = vault / "00_System" / "primer.md"
    nota.write_text("---\ntitle: Primer\n---\n", encoding="utf-8")

    completar_mod.completar(apply=True)
    assert set(_fm(nota)) == {"title", "id", "createdAt", "updatedAt"}


def test_un_bloque_ilegible_no_se_toca_y_se_manda_a_heal(vault):
    nota = vault / "07_Knowledge" / "rota.md"
    roto = "---\ntitle: Overview: demo\n---\n\ncuerpo\n"
    nota.write_text(roto, encoding="utf-8")

    r = completar_mod.completar(apply=True)
    assert nota.read_text(encoding="utf-8") == roto
    assert r["skipped"] == [{"path": "07_Knowledge/rota.md", "cause": "frontmatter_ilegible",
                             "hint": "python scripts/vault_frontmatter_heal.py --apply"}]


def test_un_derivado_y_una_instantanea_no_se_tocan(vault):
    indice = vault / "07_Knowledge" / "index.md"
    indice.write_text("# Índice\n", encoding="utf-8")
    snap = vault / "07_Knowledge" / ".history" / "x.md"
    snap.parent.mkdir()
    snap.write_text("# x\n", encoding="utf-8")

    r = completar_mod.completar(apply=True)
    assert r["completed_count"] == 0
    assert indice.read_text(encoding="utf-8") == "# Índice\n"
    assert snap.read_text(encoding="utf-8") == "# x\n"


def test_fuera_de_las_secciones_no_es_una_nota(vault):
    (vault / "docs").mkdir()
    (vault / "docs" / "leeme.md").write_text("# x\n", encoding="utf-8")
    assert completar_mod.completar()["notes_scanned"] == 0


def test_un_cambio_entre_leer_y_escribir_no_se_pisa(vault):
    nota = vault / "07_Knowledge" / "jwt.md"
    nota.write_text("---\nid: a1\n---\n", encoding="utf-8")
    visto = nota.read_text(encoding="utf-8")
    nota.write_text("---\nid: a1\ntitle: editado por otro\n---\n", encoding="utf-8")

    r = completar_mod._escribir(nota, visto, "---\nid: a1\ntitle: x\n---\n")
    assert r == "cambio_concurrente"
    assert "editado por otro" in nota.read_text(encoding="utf-8")


def test_una_nota_completa_no_se_reescribe(vault):
    nota = vault / "07_Knowledge" / "jwt.md"
    nota.write_text("---\nid: a1\n---\n", encoding="utf-8")
    completar_mod.completar(apply=True)
    r = completar_mod.completar(apply=True)
    assert r["completed_count"] == 0 and r["written_count"] == 0 and r["ok"] is True


def test_path_limita_a_una_nota_y_no_sale_del_vault(vault):
    for n in ("a", "b"):
        (vault / "07_Knowledge" / f"{n}.md").write_text("# x\n", encoding="utf-8")
    assert completar_mod.completar(path="07_Knowledge/a.md")["notes_scanned"] == 1
    r = completar_mod.completar(path="../fuera.md")
    assert r["ok"] is False and r["error_code"] == "INVALID_PATH"


def test_los_valores_por_defecto_son_los_del_escritor():
    """AP-57: completar pone lo que `vault_write` habría puesto, no un valor propio."""
    import vault_write

    bloque = vault_write.generate_frontmatter("x", folder="07_Knowledge")
    escrito = yaml.safe_load("\n".join(bloque.split("\n")[1:-1]))
    assert escrito["status"] == contrato.POR_DEFECTO["status"]
    assert escrito["agent"] == contrato.POR_DEFECTO["agent"]
    for campo, valor in cia_por_defecto().items():
        assert escrito[campo] == valor


def test_el_escritor_lee_los_valores_por_defecto_de_sus_duenos(monkeypatch):
    """AP-57: la igualdad de arriba la cumplían dos copias que coincidían.

    `vault_write` escribía `"medium"`, `"internal"`, `"system"` y `"draft"`
    como literales. Si `CIA_TRIAD` o `POR_DEFECTO` cambian, el escritor y
    `vault_frontmatter_completar` dejan de poner lo mismo sin que nada falle.
    """
    import vault_fundamentals_catalog
    import vault_write

    otros_cia = {"cia_integrity": "high", "cia_availability": "low", "cia_sensitivity": "public"}
    monkeypatch.setattr(vault_fundamentals_catalog, "cia_por_defecto", lambda: dict(otros_cia))
    monkeypatch.setattr(contrato, "POR_DEFECTO", {"status": "planned", "agent": "otro", "tags": []})

    bloque = vault_write.generate_frontmatter("x", folder="07_Knowledge")
    escrito = yaml.safe_load("\n".join(bloque.split("\n")[1:-1]))
    assert escrito["status"] == "planned" and escrito["agent"] == "otro"
    for campo, valor in otros_cia.items():
        assert escrito[campo] == valor


@pytest.mark.parametrize("codigo", ["AP-12", "AP-16", "AP-26", "AP-27", "AP-28", "AP-29", "AP-30"])
def test_las_normas_de_campos_nombran_a_quien_los_completa(codigo):
    norma = next(n for n in NORM_CATALOG if n["code"] == codigo)
    assert "vault_frontmatter_completar" in norma["tools_enforcing"]


def test_la_pista_de_validate_apunta_a_completar():
    from vault.kernel.errores import ERROR_CATALOG

    texto = json.dumps(ERROR_CATALOG, ensure_ascii=False)
    assert "vault_frontmatter_completar" in texto


def test_apply_y_check_a_la_vez_sale_por_el_contrato_de_error():
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_frontmatter_completar.py"), "--apply", "--check"],
        capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1
    assert json.loads(r.stdout)["error_code"] == "CONFLICTING_ARGS"


def test_la_normalizacion_de_codificacion_se_declara(vault):
    """`atomic_write_text` escribe LF sin BOM, que es el formato del estándar.

    En una nota CRLF con BOM eso convierte el diff en el fichero entero. No se
    esquiva con un criterio de codificación propio —sería una segunda opinión
    sobre el mismo dato (AP-57)—: se dice, para que quien revise sepa por qué.
    """
    nota = vault / "07_Knowledge" / "win.md"
    nota.write_bytes("﻿---\r\nid: a1\r\n---\r\n\r\ncuerpo\r\n".encode("utf-8"))
    (vault / "07_Knowledge" / "lf.md").write_bytes(b"---\nid: a2\n---\n")  # write_text pone CRLF en Windows

    r = completar_mod.completar(apply=True)
    por_ruta = {e["path"]: e for e in r["completed"]}
    assert por_ruta["07_Knowledge/win.md"]["encoding_normalized"] == ["bom", "crlf"]
    assert por_ruta["07_Knowledge/lf.md"]["encoding_normalized"] == []
    assert nota.read_bytes().endswith(b"\n---\n\ncuerpo\n")
