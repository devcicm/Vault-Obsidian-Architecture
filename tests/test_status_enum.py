"""D4 — `Status` se deriva de `STATUS_VOCAB` (CN-03) y no lo copia."""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

from vault_norms_catalog import STATUS_VOCAB, Status, normalize_status  # noqa: E402

import vault_grafo_import as gi  # noqa: E402


def test_cn03_el_enum_y_el_vocabulario_son_el_mismo_conjunto():
    assert {s.value for s in Status} == STATUS_VOCAB
    assert len(Status) == len(STATUS_VOCAB)


def test_cn03_un_miembro_es_la_cadena_que_se_escribe():
    assert Status.IN_PROGRESS == "in-progress"
    assert Status("draft") is Status.DRAFT


def test_cn03_normalizar_devuelve_un_valor_del_enum():
    canonico, _nota, _regla = normalize_status("In Progress")
    assert Status(canonico) is Status.IN_PROGRESS


def test_cn03_el_enum_no_lleva_una_lista_propia():
    """Si alguien escribe los doce valores a mano, el set deja de ser el dueño."""
    fuente = gi.codigo_de(RAIZ / "scripts" / "vault_norms_catalog.py").read_text(encoding="utf-8")
    bloque = fuente[fuente.index("Status = Enum("):]
    bloque = bloque[: bloque.index("\n)\n")]
    assert "STATUS_VOCAB" in bloque
    assert '"in-progress"' not in bloque


def test_la_matriz_de_trazabilidad_no_escribe_el_tamano_a_mano():
    """La fila de Validez (F5) decía «12 valores» como literal (AP-47)."""
    from vault_fundamentals import TRACEABILITY_MATRIX
    from vault_norms_catalog import STATUS_VOCAB
    import inspect
    import vault_fundamentals

    fila = next(f for f in TRACEABILITY_MATRIX if f["concept"].startswith("Validez"))
    assert fila["threshold"] == f"{len(STATUS_VOCAB)} valores"
    assert '"12 valores"' not in inspect.getsource(vault_fundamentals)
