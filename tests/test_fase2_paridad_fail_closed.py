"""El verificador de paridad CLI<->MCP tiene que ser FAIL-CLOSED (H-L3-02, H-L3-05).

Un verificador que solo sabe decir "todo bien" no verifica nada: basta con que el
guion cambie para que deje de mirar. Estas pruebas fabrican cada situacion que
debe detectar y comprueban que la FUNCION PURA `evaluar()` la senala.

Identidad por escenario: un caso se identifica por su `case_id`, no por el nombre
de la operacion (WRITE_CREATE y WRITE_UPDATE son dos casos de `vault_write`).

Lo que se exige:
  - AP-40 con codigo distinto de cero;
  - un caso requerido omitido (WRITE_UPDATE);
  - un `case_id` duplicado;
  - un `case_id` no previsto;
  - un campo obligatorio ausente;
  - codigos o significados de error divergentes;
  - efectos observables divergentes (ficheros distintos, huellas distintas);
  - la CLI que responde exito sin producir el efecto esperado;
  - algo modificado FUERA del runtime autorizado;
  - el exit code de la CLI que contradice a su envelope;
  - `isError` del protocolo MCP que contradice al CLI, y error de transporte.
Y ademas, el control positivo: una medicion limpia NO puede pasar.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def _cargar_paridad_cli_mcp():
    """Carga por ruta: `audits/fase2/` no es un paquete de la suite."""
    import importlib.util

    ruta = ROOT / "audits" / "fase2" / "paridad_cli_mcp.py"
    spec = importlib.util.spec_from_file_location("paridad_cli_mcp", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


verificador = _cargar_paridad_cli_mcp()

CONTRATO_OK = {"exit": 0}


def _efectos(creados=None, modificados=None, eliminados=None, huellas=None):
    return {"creados": sorted(creados or []), "eliminados": sorted(eliminados or []),
            "modificados": sorted(modificados or []), "huellas": dict(huellas or {})}


def _fila(case_id="READ_MISSING", tool="vault_read", **cambios):
    """Una fila limpia, modificable."""
    fila = {
        "case_id": case_id,
        "operacion": tool,
        "escenario": "escenario de prueba",
        "expuesta_por_mcp": True,
        "cli": {"ok": True, "path": "x.md"},
        "mcp": {"ok": True, "path": "x.md"},
        "cli_error": None,
        "mcp_error": None,
        "is_error": False,
        "error_transporte": None,
        "campos": ["ok", "path"],
        "cli_exit": 0,
        "efectos_cli": _efectos(),
        "efectos_mcp": _efectos(),
        "fuera_del_runtime_cli": [],
        "fuera_del_runtime_mcp": [],
    }
    fila.update(cambios)
    return fila


# â”€â”€ control positivo â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_una_medicion_limpia_pasa():
    veredicto = verificador.evaluar([_fila()], CONTRATO_OK, ["READ_MISSING"],
                                     ["READ_MISSING"])
    assert veredicto["ok"], veredicto["problemas"]


# â”€â”€ identidad por escenario â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_detecta_un_caso_requerido_omitido():
    """Falta WRITE_UPDATE: el verificador tiene que_notarlo, porque se
    identifica por case_id y no por el nombre de la operacion."""
    veredicto = verificador.evaluar(
        [_fila("WRITE_CREATE", "vault_write")], CONTRATO_OK,
        ["WRITE_CREATE", "WRITE_UPDATE"], ["WRITE_CREATE", "WRITE_UPDATE"])
    assert not veredicto["ok"]
    assert any("WRITE_UPDATE" in p and "no ejecutado" in p
               for p in veredicto["problemas"]), veredicto["problemas"]


def test_detecta_un_case_id_duplicado():
    veredicto = verificador.evaluar(
        [_fila("WRITE_CREATE", "vault_write"), _fila("WRITE_CREATE", "vault_write")],
        CONTRATO_OK, ["WRITE_CREATE"], ["WRITE_CREATE"])
    assert not veredicto["ok"]
    assert any("duplicado" in p for p in veredicto["problemas"]), veredicto["problemas"]


def test_detecta_un_case_id_no_previsto():
    veredicto = verificador.evaluar(
        [_fila("WRITE_CREATE", "vault_write"), _fila("CLARO", "vault_read")],
        CONTRATO_OK, ["WRITE_CREATE"], ["WRITE_CREATE"])
    assert not veredicto["ok"]
    assert any("no previsto" in p for p in veredicto["problemas"]), veredicto["problemas"]


# â”€â”€ contrato y errores â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€



def test_detecta_el_verificador_de_contrato_roto():
    veredicto = verificador.evaluar([_fila()], {"exit": 1}, ["READ_MISSING"],
                                     ["READ_MISSING"])
    assert not veredicto["ok"]
    assert any("AP-40" in p for p in veredicto["problemas"]), veredicto["problemas"]


def test_detecta_un_campo_obligatorio_ausente():
    veredicto = verificador.evaluar([_fila(mcp={"ok": True})], CONTRATO_OK,
                                     ["READ_MISSING"], ["READ_MISSING"])
    assert not veredicto["ok"]
    assert any("campo obligatorio ausente" in p for p in veredicto["problemas"])


def test_detecta_divergencia_de_codigo_de_error():
    fila = _fila(cli={"ok": False, "path": "x.md"}, mcp={"ok": False, "path": "x.md"},
                 cli_error="NOTE_NOT_FOUND", mcp_error="INVALID_PATH")
    veredicto = verificador.evaluar([fila], CONTRATO_OK, ["READ_MISSING"],
                                     ["READ_MISSING"])
    assert not veredicto["ok"]
    assert any("codigo de error" in p for p in veredicto["problemas"])


def test_detecta_un_adaptador_que_falla_y_el_otro_no():
    fila = _fila(cli={"ok": False, "path": "x.md"}, mcp={"ok": True, "path": "x.md"},
                 cli_error="NOTE_NOT_FOUND", mcp_error=None)
    veredicto = verificador.evaluar([fila], CONTRATO_OK, ["READ_MISSING"],
                                     ["READ_MISSING"])
    assert not veredicto["ok"]
    assert any("un adaptador devuelve error" in p for p in veredicto["problemas"])


def test_detecta_is_error_que_contradice_al_cli():
    fila = _fila(is_error=True)
    veredicto = verificador.evaluar([fila], CONTRATO_OK, ["READ_MISSING"],
                                     ["READ_MISSING"])
    assert not veredicto["ok"]
    assert any("isError" in p for p in veredicto["problemas"])


def test_is_error_conforme_no_es_problema():
    """`isError` es la convention MCP de error de EJECUCION: si el CLI falla
    con el mismo codigo, los dos adaptadores CONCUERDAN."""
    fila = _fila(cli={"ok": False, "path": "x.md"}, mcp={"ok": False, "path": "x.md"},
                 cli_error="NOTE_NOT_FOUND", mcp_error="NOTE_NOT_FOUND",
                 is_error=True)
    veredicto = verificador.evaluar([fila], CONTRATO_OK, ["READ_MISSING"],
                                     ["READ_MISSING"])
    assert veredicto["ok"], veredicto["problemas"]


def test_detecta_un_error_de_transporte():
    veredicto = verificador.evaluar([_fila(error_transporte="timeout esperando tools/call")],
                                     CONTRATO_OK, ["READ_MISSING"], ["READ_MISSING"])
    assert not veredicto["ok"]
    assert any("transporte" in p for p in veredicto["problemas"])


def test_detecta_una_operacion_no_expuesta_por_mcp():
    veredicto = verificador.evaluar([_fila(expuesta_por_mcp=False)], CONTRATO_OK,
                                     ["READ_MISSING"], ["READ_MISSING"])
    assert not veredicto["ok"]
    assert any("no esta expuesta" in p for p in veredicto["problemas"])


# â”€â”€ efectos observables â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_detecta_efectos_observables_divergentes():
    """MCP modifica un fichero DISTINTO: el conjunto de ficheros tocados no
    coincide."""
    fila = _fila(
        cli={"ok": True, "path": "x.md"}, mcp={"ok": True, "path": "x.md"},
        efectos_cli=_efectos(creados=["nota.md"], huellas={"nota.md": "aaa"}),
        efectos_mcp=_efectos(creados=["otro.md"], huellas={"otro.md": "bbb"}))
    veredicto = verificador.evaluar([fila], CONTRATO_OK, ["READ_MISSING"],
                                     ["READ_MISSING"])
    assert not veredicto["ok"]
    assert any("efectos divergentes" in p for p in veredicto["problemas"])


def test_detecta_huellas_finales_distintas():
    """Los mismos ficheros, pero con CONTENIDO distinto: la respuesta coincide y
    el efecto no."""
    fila = _fila(
        cli={"ok": True, "path": "x.md"}, mcp={"ok": True, "path": "x.md"},
        efectos_cli=_efectos(modificados=["nota.md"], huellas={"nota.md": "aaa"}),
        efectos_mcp=_efectos(modificados=["nota.md"], huellas={"nota.md": "bbb"}))
    veredicto = verificador.evaluar([fila], CONTRATO_OK, ["READ_MISSING"],
                                     ["READ_MISSING"])
    assert not veredicto["ok"]
    assert any("huellas" in p for p in veredicto["problemas"]), veredicto["problemas"]


def test_detecta_la_cli_que_responde_exito_sin_efecto():
    """La CLI dice 'escrito' pero no toco nada: la respuesta y el efecto no
    concuerdan."""
    fila = _fila(
        cli={"ok": True, "created": True, "path": "x.md"},
        mcp={"ok": True, "created": True, "path": "x.md"},
        campos=["ok", "created", "path"],
        efectos_cli=_efectos(),
        efectos_mcp=_efectos(creados=["x.md"], huellas={"x.md": "aaa"}))
    veredicto = verificador.evaluar([fila], CONTRATO_OK, ["WRITE_CREATE"],
                                     ["WRITE_CREATE"])
    assert not veredicto["ok"]
    assert any("efectos divergentes" in p for p in veredicto["problemas"])


def test_detecta_escritura_fuera_del_runtime_por_cli():
    """El exit code de la CLI y su envelope no pueden contradecirse, y una
    escritura FUERA del runtime autorizado es un efecto prohibido que el
    verificador senala por adaptador."""
    fila = _fila(externos_cli={"creados": ["../fuera.md"], "modificados": [],
                               "eliminados": []})
    veredicto = verificador.evaluar([fila], CONTRATO_OK, ["READ_MISSING"],
                                     ["READ_MISSING"])
    assert not veredicto["ok"], veredicto["problemas"]
    assert any("FUERA del runtime" in p and "CLI" in p
               for p in veredicto["problemas"]), veredicto["problemas"]


def test_detecta_el_exit_code_que_contradice_al_envelope():
    """La CLI sale con codigo de error y su envelope dice ok: no puede pasar."""
    fila = _fila(cli_exit=1, cli={"ok": True, "path": "x.md"},
                 mcp={"ok": True, "path": "x.md"})
    veredicto = verificador.evaluar([fila], CONTRATO_OK, ["READ_MISSING"],
                                     ["READ_MISSING"])
    assert not veredicto["ok"]
    assert any("exit code" in p for p in veredicto["problemas"]), veredicto["problemas"]


def test_detectar_cambios_ve_creaciones():
    cambios = verificador.detectar_cambios({}, {"a.md": "h1"})
    assert cambios["creados"] == ["a.md"], cambios
    assert cambios["eliminados"] == [] and cambios["modificados"] == []


def test_detectar_cambios_ve_modificaciones_de_contenido():
    """Mismo nombre, otro contenido: MODIFICADO (el caso que un detector por
    nombres no ve)."""
    cambios = verificador.detectar_cambios(
        {"externo/config.json": "hash_A"}, {"externo/config.json": "hash_B"})
    assert cambios["modificados"] == ["externo/config.json"], cambios
    assert cambios["creados"] == [] and cambios["eliminados"] == []


def test_detectar_cambios_ve_eliminaciones():
    cambios = verificador.detectar_cambios({"externo/viejo.md": "h"}, {})
    assert cambios["eliminados"] == ["externo/viejo.md"], cambios


def test_clasificar_parte_entre_internos_y_externos():
    cambios = {"creados": ["runtime/nueva.md", "externa.md"],
               "modificados": ["runtime/existente.md"],
               "eliminados": ["externa-vieja.md"]}
    reparto = verificador.clasificar_cambios(cambios, internos=("runtime/",))
    assert reparto["internos"]["creados"] == ["runtime/nueva.md"]
    assert reparto["externos"]["creados"] == ["externa.md"]
    assert reparto["externos"]["eliminados"] == ["externa-vieja.md"]


def test_los_no_verificados_son_problema():
    fila = _fila(no_verificados=["externo/sin-permisos.md"])
    veredicto = verificador.evaluar([fila], CONTRATO_OK, ["WRITE_CREATE"])
    assert not veredicto["ok"]
    assert any("no verificables" in p for p in veredicto["problemas"]), veredicto["problemas"]


def test_mcp_que_modifica_un_prohibido_es_no_conforme():
    fila = _fila(externos_mcp={"creados": [], "modificados": ["externo/prohibido.md"],
                               "eliminados": []})
    veredicto = verificador.evaluar([fila], CONTRATO_OK, ["WRITE_CREATE"])
    assert not veredicto["ok"], veredicto["problemas"]
    assert any("MCP" in p and "FUERA" in p for p in veredicto["problemas"]), veredicto["problemas"]
