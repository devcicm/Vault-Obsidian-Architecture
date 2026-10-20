"""O4 — el canal no reescribe lo idéntico, y los registros no duplican.

Dos hallazgos de la ola, ambos medidos con el barrido ejecutándose de verdad
(los ejemplos ya se preparan con su proyecto y sus ficheros):

1. `atomic_write_text` escribía siempre: comparar el texto compuesto contra el
   disco no servía —el saneado pliega em-dash→`--`— y quien componía un id o un
   sello nuevo por llamada reescribía en cada corrida. La regla se aplica en el
   canal: mismo cuerpo saneado, o mismo cuerpo sin `id`/`createdAt`/`updatedAt`,
   no es una escritura.
2. Los registros por correlativo (`BUG-001`, `AID-001`, `TEST-001`) anexaban
   una entrada por llamada: re-guardar el mismo elemento dejaba el número
   siguiente apuntando a la nota del anterior.
"""

import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from vault_io import (  # noqa: E402
    atomic_write_text,
    reset_vault_root,
    set_vault_root,
)


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    for carpeta in ("18_Bugs", "16_AI_Governance", "11_Code", "07_Knowledge"):
        (tmp_path / carpeta).mkdir(parents=True)
    set_vault_root(tmp_path)
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    yield tmp_path
    reset_vault_root()


def _mtime(ruta: Path) -> int:
    return ruta.stat().st_mtime_ns


def test_el_canal_no_reescribe_lo_identico(vault):
    nota = vault / "07_Knowledge" / "x.md"
    atomic_write_text(nota, "# X\n\ncuerpo\n")
    antes = _mtime(nota)
    time.sleep(0.02)
    atomic_write_text(nota, "# X\n\ncuerpo\n")
    assert _mtime(nota) == antes, "una escritura idéntica movió el fichero"


def test_el_canal_compara_la_forma_de_disco(vault):
    """El texto compuesto con `—` compara contra el `--` que dejó el saneado."""
    nota = vault / "07_Knowledge" / "y.md"
    atomic_write_text(nota, "# Y\n\nuno \u2014 dos\n")
    antes = _mtime(nota)
    time.sleep(0.02)
    atomic_write_text(nota, "# Y\n\nuno \u2014 dos\n")
    assert _mtime(nota) == antes


def test_el_canal_calla_ante_solo_sellos(vault):
    """Cambiar solo `id`/`createdAt`/`updatedAt` no es cambiar el documento."""
    nota = vault / "07_Knowledge" / "z.md"
    atomic_write_text(nota, "---\nid: a\ncreatedAt: 2026-01-01\n"
                            "updatedAt: 2026-01-01\n---\n\n# Z\n")
    antes = _mtime(nota)
    time.sleep(0.02)
    atomic_write_text(nota, "---\nid: b\ncreatedAt: 2026-01-02\n"
                            "updatedAt: 2026-01-02\n---\n\n# Z\n")
    assert _mtime(nota) == antes


def test_el_canal_si_escribe_cuando_el_cuerpo_cambia(vault):
    nota = vault / "07_Knowledge" / "w.md"
    atomic_write_text(nota, "# W\n\nuno\n")
    atomic_write_text(nota, "# W\n\ndos\n")
    assert "dos" in nota.read_text(encoding="utf-8")


def test_bug_save_no_duplica_ni_cambia_el_correlativo(vault, monkeypatch):
    from vault_bug_save import vault_bug_save

    monkeypatch.setenv("VAULT_AGENT", "test-o4")
    for _ in (1, 2):
        r = vault_bug_save(project="mi-api", title="Token numerico",
                           symptom="El token se coerciona",
                           severity="high", status="open")
        assert r["ok"], r

    registro = json.loads((vault / "18_Bugs" / ".bugs-index.json")
                          .read_text(encoding="utf-8"))
    assert len(registro["bugs"]) == 1, registro["bugs"]
    assert registro["bugs"][0]["bug_id"] == "BUG-001"


def test_code_relation_no_duplica_la_relacion(vault, monkeypatch):
    from vault_code_relation import vault_code_relation

    monkeypatch.setenv("VAULT_AGENT", "test-o4")
    for _ in (1, 2):
        r = vault_code_relation(project="mi-api", from_file="User",
                                to_file="Order", relation_type="imports",
                                cardinality="1:N")
        assert r["ok"], r

    registro = json.loads((vault / "11_Code" / ".code-index.json")
                          .read_text(encoding="utf-8"))
    assert len(registro["relations"]) == 1, registro["relations"]


def test_runbook_log_no_promete_una_idempotencia_imposible():
    """Una bitácora suma ejecuciones: `unchanged` se retiró con anotación."""
    spec = json.loads((ROOT / "vault-sandbox" / "00_System" / "tool-spec.json")
                      .read_text(encoding="utf-8"))
    entrada = spec["tools"]["vault_runbook_log"]
    assert "unchanged" not in entrada["declared_returns"]
    anotado = entrada.get("superseded_fields") or {}
    assert "unchanged" in anotado
    assert anotado["unchanged"].get("why")
    assert "executionNumber" in entrada["declared_returns"]
