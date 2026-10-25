"""El verificador de paridad CLI<->MCP tiene que ser FAIL-CLOSED (H-L3-02).

Un verificador que solo sabe decir "todo bien" no verifica nada: basta con que
el guion cambie para que deje de mirar. Estas pruebas fabrican cada situacion
que debe detectar y comprueban que la FUNCION PURA `evaluar()` la senala.

Lo que se exige, por QA:
  - el verificador de contrato (AP-40) devuelva un codigo distinto de cero;
  - falte un campo obligatorio del contrato en alguno de los dos adaptadores;
  - divergan los codigos o el significado del error;
  - divergan los efectos observables;
  - un caso requerido no se haya ejecutado;
  - la respuesta MCP llegue marcada como isError o como error de transporte.

Y ademas, el control positivo: una medicion limpia NO puede pasar.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "audits" / "fase2"))

import paridad_cli_mcp as verificador  # noqa: E402


def _fila(**cambios):
    """Una fila limpia, modificable."""
    fila = {
        "operacion": "vault_read",
        "argumentos": {"path": "x.md"},
        "expuesta_por_mcp": True,
        "cli": {"ok": True, "path": "x.md"},
        "mcp": {"ok": True, "path": "x.md"},
        "cli_error": None,
        "mcp_error": None,
        "is_error": False,
        "error_transporte": None,
        "campos": ["ok", "path"],
    }
    fila.update(cambios)
    return fila


CONTRATO_OK = {"exit": 0}


def test_una_medicion_limpia_pasa():
    veredicto = verificador.evaluar([_fila()], CONTRATO_OK, ["vault_read"])
    assert veredicto["ok"], veredicto["problemas"]


def test_detecta_el_verificador_de_contrato_roto():
    veredicto = verificador.evaluar([_fila()], {"exit": 1}, ["vault_read"])
    assert not veredicto["ok"]
    assert any("AP-40" in p for p in veredicto["problemas"]), veredicto["problemas"]


def test_detecta_un_campo_obligatorio_ausente():
    fila = _fila(mcp={"ok": True})  # sin `path`
    veredicto = verificador.evaluar([fila], CONTRATO_OK, ["vault_read"])
    assert not veredicto["ok"]
    assert any("campo obligatorio ausente" in p for p in veredicto["problemas"])


def test_detecta_divergencia_de_codigo_de_error():
    fila = _fila(cli={"ok": False}, mcp={"ok": False},
                 cli_error="NOTE_NOT_FOUND", mcp_error="INVALID_PATH")
    veredicto = verificador.evaluar([fila], CONTRATO_OK, ["vault_read"])
    assert not veredicto["ok"]
    assert any("codigo de error" in p for p in veredicto["problemas"]), veredicto["problemas"]


def test_detecta_un_adaptador_que_falla_y_el_otro_no():
    fila = _fila(cli={"ok": False}, mcp={"ok": True},
                 cli_error="NOTE_NOT_FOUND", mcp_error=None)
    veredicto = verificador.evaluar([fila], CONTRATO_OK, ["vault_read"])
    assert not veredicto["ok"]
    assert any("un adaptador devuelve error" in p for p in veredicto["problemas"])


def test_detecta_efectos_observables_divergentes():
    fila = _fila(cli={"ok": True, "path": "a.md"}, mcp={"ok": True, "path": "b.md"})
    veredicto = verificador.evaluar([fila], CONTRATO_OK, ["vault_read"])
    assert not veredicto["ok"]
    assert any("divergencia de efecto" in p for p in veredicto["problemas"])


def test_detecta_un_caso_requerido_no_ejecutado():
    veredicto = verificador.evaluar([], CONTRATO_OK, ["vault_read"])
    assert not veredicto["ok"]
    assert any("no ejecutado" in p for p in veredicto["problemas"])


def test_detecta_is_error_del_protocolo_mcp():
    fila = _fila(is_error=True)
    veredicto = verificador.evaluar([fila], CONTRATO_OK, ["vault_read"])
    assert not veredicto["ok"]
    assert any("isError" in p for p in veredicto["problemas"])


def test_detecta_un_error_de_transporte():
    fila = _fila(error_transporte="timeout esperando tools/call")
    veredicto = verificador.evaluar([fila], CONTRATO_OK, ["vault_read"])
    assert not veredicto["ok"]
    assert any("transporte" in p for p in veredicto["problemas"])


def test_detecta_una_operacion_no_expuesta_por_mcp():
    fila = _fila(expuesta_por_mcp=False)
    veredicto = verificador.evaluar([fila], CONTRATO_OK, ["vault_read"])
    assert not veredicto["ok"]
    assert any("no esta expuesta" in p for p in veredicto["problemas"])


def test_is_error_conforme_no_es_problema():
    """`isError` es la convention MCP de error de EJECUCION: si el CLI falla
    con el mismo codigo, los dos adaptadores CONCUERDAN y no hay problema."""
    fila = _fila(cli={"ok": False, "path": "x.md"},
                 mcp={"ok": False, "path": "x.md"},
                 cli_error="NOTE_NOT_FOUND", mcp_error="NOTE_NOT_FOUND",
                 is_error=True)
    veredicto = verificador.evaluar([fila], CONTRATO_OK, ["vault_read"])
    assert veredicto["ok"], veredicto["problemas"]
