"""Ningún registro declarado puede quedarse sin consumidor.

Es el modo de fallo característico de este repo: una constante en mayúsculas que
describe un vocabulario, una norma o una lista de valores válidos, y que nadie
lee jamás. Compila, se documenta, parece gobernanza — y no gobierna nada.

Los cinco que existían cuando se escribió este archivo, y lo que costaban:

  * `DATA_SUBJECTS` (vault_privacy_save) — `minors` es un DPIA_TRIGGER del GDPR
    Art. 35. Escribir "minor" en singular desactivaba el disparador en silencio.
  * `QUALITY_ATTRIBUTES` (vault_code_module) — la nota titulaba su tabla
    "Calidad (ISO 25010)" con atributos que podían no ser los de la norma.
  * `INVISIBLE_CHARS` / `DASH_REPLACEMENTS` (vault_encoding) — el detector
    reportaba 18 caracteres y el sanitizador sabía quitar 13: cinco hallazgos
    que ninguna tool podía arreglar.
  * `MIN_RISK_ORDER` (vault_delta) — el `choices` de la CLI era una copia
    literal escrita a mano, libre de divergir del registro.
  * `CATEGORY_NOTES` (vault_diagram_save) — la descripción de cada categoría
    existía y el error de categoría inválida no la mostraba.
"""

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# Constantes de módulo que son registros de verdad y deben tener consumidor.
# Se nombran una a una en vez de barrer todas las mayúsculas: un guard que se
# inventa su propio alcance produce falsos positivos y acaba desactivado.
REGISTROS = [
    ("vault_privacy_save.py", "DATA_SUBJECTS"),
    ("vault_privacy_save.py", "DPIA_TRIGGERS"),
    ("vault_privacy_save.py", "LEGAL_BASES"),
    ("vault_privacy_save.py", "VALID_STATUS"),
    ("vault_code_module.py", "QUALITY_ATTRIBUTES"),
    ("vault_code_module.py", "ISO_TYPES"),
    ("vault_encoding.py", "INVISIBLE_CHARS"),
    ("vault_encoding.py", "DASH_REPLACEMENTS"),
    ("vault_encoding.py", "QUOTE_REPLACEMENTS"),
    ("vault_delta.py", "MIN_RISK_ORDER"),
    ("vault_delta.py", "RISK_THRESHOLDS"),
    ("vault_delta.py", "CIA_WEIGHT"),
    ("vault_diagram_save.py", "CATEGORY_NOTES"),
    ("vault_diagram_save.py", "CATEGORIES"),
    ("vault_diagram_save.py", "DIAGRAM_TYPES"),
]


def _lecturas(script: Path, nombre: str) -> int:
    """Cuántas veces se LEE el nombre (asignarlo no cuenta como consumirlo)."""
    arbol = ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
    return sum(
        1
        for n in ast.walk(arbol)
        if isinstance(n, ast.Name) and n.id == nombre and isinstance(n.ctx, ast.Load)
    )


@pytest.mark.parametrize("archivo,nombre", REGISTROS, ids=lambda v: str(v))
def test_el_registro_existe(archivo, nombre):
    script = SCRIPTS_DIR / archivo
    arbol = ast.parse(script.read_text(encoding="utf-8"))
    definidos = {
        t.id
        for n in ast.walk(arbol)
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name)
    } | {
        n.target.id
        for n in ast.walk(arbol)
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
    }
    assert nombre in definidos, f"{nombre} ya no está en {archivo}"


@pytest.mark.parametrize("archivo,nombre", REGISTROS, ids=lambda v: str(v))
def test_el_registro_tiene_consumidor(archivo, nombre):
    leido = _lecturas(SCRIPTS_DIR / archivo, nombre)
    assert leido > 0, (
        f"{nombre} se declara en {archivo} y no lo lee nadie. Un vocabulario que "
        f"no se comprueba no gobierna: o le das consumidor o lo borras, pero no "
        f"puede quedarse ahí pareciendo una garantía"
    )


# ─── Lo que cada registro garantiza, comprobado de verdad ────────────────────


def test_data_subject_invalido_se_rechaza():
    """El typo que desactivaba el DPIA."""
    import vault_privacy_save as vps

    r = vps.vault_privacy_save(
        project="p",
        title="t",
        purpose="pruebas",
        legal_basis="consent",
        data_subjects=["minor"],
    )
    assert r["ok"] is False
    assert r["error_code"] == "INVALID_DATA_SUBJECT"
    assert "minors" in r["valid_data_subjects"]


def test_data_subject_valido_pasa_y_dispara_dpia():
    import vault_privacy_save as vps

    assert "minors" in vps.DATA_SUBJECTS
    assert vps._dpia_auto_required([], ["minors"]) is True
    assert vps._dpia_auto_required([], ["minor"]) is False, (
        "precondición del bug: el singular nunca disparó el DPIA"
    )


def test_atributo_de_calidad_fuera_de_iso_25010_se_rechaza():
    import vault_code_module as vcm

    r = vcm.vault_code_module(
        project="p",
        file_path="src/a.py",
        description="d",
        quality=[{"attribute": "elegancia", "rating": 5}],
    )
    assert r["ok"] is False
    assert "25010" in r["error"]


def test_el_sanitizador_quita_todo_lo_que_el_detector_reporta():
    """Detectar un problema que ninguna tool sabe arreglar es peor que no verlo."""
    import vault_encoding as ve

    texto = "".join(char for char, _ in ve.INVISIBLE_CHARS)
    limpio, fixes = ve.remove_invisible_chars(texto)
    assert limpio == "", f"quedaron sin quitar: {[repr(c) for c in limpio]}"
    assert len(fixes) == len(ve.INVISIBLE_CHARS)
    assert ve.detect_issues(limpio) == [] or all(
        i["type"] != "invisible_char" for i in ve.detect_issues(limpio)
    )


def test_los_guiones_del_registro_se_normalizan_todos():
    import vault_encoding as ve

    for char, esperado, nombre in ve.DASH_REPLACEMENTS:
        salida, fixes = ve.normalize_dashes(f"a{char}b")
        assert salida == f"a{esperado}b", f"{nombre} no se normalizó"
        assert fixes and fixes[0]["name"] == nombre


def test_los_choices_de_min_risk_salen_del_registro():
    """El `choices` de argparse no puede ser una segunda lista escrita a mano."""
    fuente = (SCRIPTS_DIR / "vault_delta.py").read_text(encoding="utf-8")
    assert "choices=MIN_RISK_ORDER" in fuente
