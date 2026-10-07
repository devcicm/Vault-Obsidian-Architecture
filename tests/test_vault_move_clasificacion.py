"""vault_move reclasifica con el mismo criterio que vault_write (CN-02).

Medido 2026-10-07 en un vault de prueba: mover `03_Decisions/x.md` a
`07_Knowledge/` devolvía `ok: true` y la nota seguía con `type: decision` —la
combinación que `vault_write` rechaza—, y `--to scripts/x.md` dejaba la nota
fuera de toda sección. Mover es cambiar de sección, y la sección decide el
tipo: el destino se valida como el de una escritura, y un tipo que no
corresponde se cambia explícitamente con `--type` o el movimiento no ocurre.
"""

import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import vault_registry as reg  # noqa: E402

ANTES = "2026-01-01T00:00:00.000Z"


def _nota(tipo=None):
    lineas = ["---", "title: n", "id: x", f"createdAt: {ANTES}", f"updatedAt: {ANTES}"]
    if tipo:
        lineas.append(f"type: {tipo}")
    return "\n".join(lineas + ["---", "# n", "", "cuerpo", ""])


@pytest.fixture
def vault(tmp_path):
    import vault_io

    root = tmp_path / "v"
    for s in ("00_System", "03_Decisions/sub", "07_Knowledge", "99_Index", "scripts"):
        (root / s).mkdir(parents=True)
    (root / reg.SECCIONES_PROPIAS_RUTA).write_text(json.dumps({"schema": 1, "secciones": [
        {"folder": "22_Viejo", "documentacion": "guia", "status": "retirada"},
        {"folder": "23_Libre", "documentacion": "guia", "tipos": ["guia"]},
    ]}), encoding="utf-8")
    (root / "03_Decisions" / "d.md").write_text(_nota("decision"), encoding="utf-8")
    (root / "03_Decisions" / "sub" / "e.md").write_text(_nota("decision"), encoding="utf-8")
    (root / "scripts" / "s.md").write_text(_nota(), encoding="utf-8")
    vault_io.set_vault_root(root)
    return root


def _fm(p: Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8").split("---")[1])


def test_cn02_mover_a_otra_seccion_con_un_tipo_ajeno_no_ocurre(vault):
    import vault_move

    r = vault_move.move_note("03_Decisions/d.md", "07_Knowledge/d.md")
    assert r["ok"] is False and r["error_code"] == "INVALID_INPUT", r
    assert "--type" in json.dumps(r, ensure_ascii=False)
    assert (vault / "03_Decisions" / "d.md").is_file()
    assert not (vault / "07_Knowledge" / "d.md").exists()


def test_cn02_type_reclasifica_y_refresca_updated_at(vault):
    import vault_move

    r = vault_move.move_note("03_Decisions/d.md", "07_Knowledge/d.md", note_type="concept")
    assert r["ok"] is True, r
    assert r["reclassified"] == {"from": "decision", "to": "concept"}
    fm = _fm(vault / "07_Knowledge" / "d.md")
    assert fm["type"] == "concept"
    assert str(fm["updatedAt"]) != ANTES and str(fm["createdAt"]).startswith("2026-01-01")
    assert not (vault / "03_Decisions" / "d.md").exists()


def test_cn02_type_de_otra_seccion_tampoco_vale(vault):
    import vault_move

    r = vault_move.move_note("03_Decisions/d.md", "07_Knowledge/d.md", note_type="runbook")
    assert r["ok"] is False and r["error_code"] == "INVALID_INPUT"
    assert (vault / "03_Decisions" / "d.md").is_file()


@pytest.mark.parametrize("destino", ["scripts/d.md", "d.md", "22_Viejo/d.md", "24_Nada/d.md"])
def test_cn02_el_destino_es_una_seccion_del_vault(vault, destino):
    import vault_move

    r = vault_move.move_note("03_Decisions/d.md", destino, note_type="guia")
    assert r["ok"] is False and r["error_code"] == "INVALID_FOLDER", r
    assert (vault / "03_Decisions" / "d.md").is_file()
    assert not (vault / destino).exists()


def test_dentro_de_la_misma_seccion_no_hay_reclasificacion(vault):
    import vault_move

    r = vault_move.move_note("03_Decisions/d.md", "03_Decisions/sub/d.md")
    assert r["ok"] is True and r["reclassified"] is None
    assert _fm(vault / "03_Decisions" / "sub" / "d.md")["updatedAt"] is not None
    assert "2026-01-01" in (vault / "03_Decisions" / "sub" / "d.md").read_text(encoding="utf-8")


def test_sacar_una_nota_de_ninguna_seccion_es_sanarla(vault):
    import vault_move

    r = vault_move.move_note("scripts/s.md", "23_Libre/s.md")
    assert r["ok"] is True, r
    assert (vault / "23_Libre" / "s.md").is_file()


def test_type_sin_cambio_de_seccion_ni_desajuste_se_aplica_igual(vault):
    import vault_move

    r = vault_move.move_note("03_Decisions/d.md", "03_Decisions/sub/d2.md", note_type="adr")
    assert r["ok"] is True and r["reclassified"] == {"from": "decision", "to": "adr"}
    assert _fm(vault / "03_Decisions" / "sub" / "d2.md")["type"] == "adr"


def test_mover_una_carpeta_comprueba_todo_antes_de_mover_nada(vault):
    import vault_move

    r = vault_move.move_folder("03_Decisions/sub", "07_Knowledge/sub")
    assert r["ok"] is False and r["error_code"] == "INVALID_INPUT", r
    assert (vault / "03_Decisions" / "sub" / "e.md").is_file()
    assert not (vault / "07_Knowledge" / "sub").exists()
    r = vault_move.move_folder("03_Decisions/sub", "scripts/sub")
    assert r["ok"] is False and r["error_code"] == "INVALID_FOLDER", r
    assert (vault / "03_Decisions" / "sub" / "e.md").is_file()


def test_dry_run_rechaza_lo_mismo_que_el_movimiento(vault):
    import vault_move

    r = vault_move.move_note("03_Decisions/d.md", "07_Knowledge/d.md", dry_run=True)
    assert r["ok"] is False and r["error_code"] == "INVALID_INPUT"
