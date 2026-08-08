"""El contrato de campos con los repos consumidores.

Un consumidor no lee el catálogo ni el manifiesto: lee el envelope. Lo único que
le importa de una tool es qué claves puede seguir esperando dentro de un mes, y
hasta v40.6 eso no lo declaraba nadie. La anotación existía —`healthScore`
sustituido por `healthIndex` en el tool-spec— y **no la leía ninguna tool**: un
registro sin consumidor, el modo de fallo que `test_orphan_registries.py`
describe para el código y que el contrato repetía en el dato.

Lo que estos tests fijan es una regla y sus dos formas de romperse:

  * un campo estable no desaparece — o sigue emitiéndose, o queda anotado;
  * una anotación sin destino, con destino que la tool no emite, o sin motivo,
    no es una anotación: es un campo borrado con papeleo.

El caso que obligó a corregir el guard recién escrito está en
`test_un_campo_sustituido_puede_dejar_de_emitirse`: el guard nació exigiendo que
todo campo anotado siguiera en `declared_returns`, y `error` en `vault_diff` y
`vault_tags` ya no está —AP-52 lo partió en `error_code`/`message`/`recovery`—.
Con aquella versión, el guard habría pedido reescribir el registro para encajar
con él.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import vault_spec_catalog_check as vscc  # noqa: E402
from vault_io import resolve_tool_spec  # noqa: E402


@pytest.fixture
def spec_editable():
    """Deja tocar el tool-spec y lo restaura pase lo que pase."""
    ruta = resolve_tool_spec()
    original = ruta.read_bytes()

    def escribir(mutar):
        datos = json.loads(original.decode("utf-8"))
        mutar(datos)
        ruta.write_text(
            json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    try:
        yield escribir
    finally:
        ruta.write_bytes(original)


# ── La tabla ─────────────────────────────────────────────────────────────────


def test_la_tabla_sale_del_tool_spec_y_no_de_una_lista_a_mano():
    tabla = vscc.tabla_de_compatibilidad()
    assert tabla, "sin tabla no hay contrato que comprobar"
    assert "vault_audit" in tabla
    assert set(tabla["vault_audit"]) >= {"healthIndex", "healthScore"}


def test_health_score_se_clasifica_como_sustituido_y_sigue_emitiendose():
    """La decisión que abrió esta tanda, hecha comprobable.

    `healthScore` satura: 22 penalizaciones con topes que suman 285 sobre una
    base de 100 dejan de distinguir en cuanto fallan dos o tres familias. La
    respuesta no fue quitarlo —lo leen consumidores— sino anotarlo y publicar
    `healthIndex` al lado.
    """
    tabla = vscc.tabla_de_compatibilidad()
    assert tabla["vault_audit"]["healthScore"] == "superseded"
    assert tabla["vault_audit"]["healthIndex"] == "stable"

    entrada = json.loads(resolve_tool_spec().read_text(encoding="utf-8"))
    entrada = entrada["tools"]["vault_audit"]
    assert "healthScore" in entrada["declared_returns"], (
        "anotarlo no autoriza a dejar de emitirlo: hay consumidores leyéndolo"
    )
    nota = entrada["superseded_fields"]["healthScore"]
    assert vscc.destinos_de(nota) == ["healthIndex"]
    assert vscc.motivo_de(nota)


def test_las_tres_clases_son_las_tres_y_no_hay_campo_sin_clasificar():
    for tool, campos in vscc.tabla_de_compatibilidad().items():
        for campo, clase in campos.items():
            assert clase in ("stable", "superseded", "internal"), f"{tool}.{campo}"


def test_superseded_by_admite_un_campo_o_varios():
    """Partir un campo en tres es lo que hizo AP-52; el registro ya lo refleja."""
    assert vscc.destinos_de({"superseded_by": "healthIndex"}) == ["healthIndex"]
    assert vscc.destinos_de(
        {"superseded_by": ["error_code", "message", "recovery"]}
    ) == ["error_code", "message", "recovery"]
    assert vscc.destinos_de({}) == []


def test_el_motivo_vale_bajo_why_o_bajo_reason():
    assert vscc.motivo_de({"why": "  porque sí  "}) == "porque sí"
    assert vscc.motivo_de({"reason": "porque no"}) == "porque no"
    assert vscc.motivo_de({"reason": "   "}) == ""


def test_un_campo_sustituido_puede_dejar_de_emitirse():
    """`error` en vault_diff ya no se emite y la anotación es su rastro.

    Si la tabla lo dejara fuera, el consumidor que aún lee `error` no tendría
    dónde enterarse de a dónde fue — que es exactamente lo que la anotación
    existe para decirle.
    """
    spec = json.loads(resolve_tool_spec().read_text(encoding="utf-8"))
    entrada = spec["tools"]["vault_diff"]
    assert "error" not in entrada["declared_returns"]
    assert vscc.tabla_de_compatibilidad()["vault_diff"]["error"] == "superseded"


# ── La puerta ────────────────────────────────────────────────────────────────


def test_el_contrato_actual_esta_verde():
    resultado = vscc.revisar_campos()
    assert resultado["ok"], json.dumps(resultado, ensure_ascii=False, indent=2)
    assert resultado["fields_by_class"]["stable"] > 0


def test_la_baseline_cubre_las_tools_del_contrato():
    baseline = vscc._cargar_baseline()
    tabla = vscc.tabla_de_compatibilidad()
    faltan = [
        t for t, campos in tabla.items()
        if any(c == "stable" for c in campos.values()) and t not in baseline
    ]
    assert not faltan, f"tools con campos estables sin congelar: {faltan}"


def test_borrar_un_campo_estable_rompe_la_puerta(spec_editable):
    """La mitad que importa: sin esto el guard es decoración."""
    spec_editable(lambda d: d["tools"]["vault_audit"]["declared_returns"].remove(
        "healthIndex"))
    resultado = vscc.revisar_campos()
    assert resultado["ok"] is False
    assert {"tool": "vault_audit", "field": "healthIndex"} in resultado[
        "removed_fields"]


def test_borrar_un_campo_anotandolo_no_rompe_la_puerta(spec_editable):
    """El camino sancionado tiene que estar abierto, o nadie lo usará."""
    def mutar(d):
        entrada = d["tools"]["vault_audit"]
        entrada["declared_returns"].remove("healthIndex")
        entrada.setdefault("superseded_fields", {})["healthIndex"] = {
            "superseded_by": "healthProfile",
            "why": "prueba: el índice se reparte por familia",
        }
    spec_editable(mutar)
    resultado = vscc.revisar_campos()
    assert resultado["ok"] is True, resultado
    assert any(s["field"] == "healthIndex" for s in resultado["newly_superseded"])


def test_degradar_un_campo_estable_a_interno_rompe_la_puerta(spec_editable):
    """Marcar interno lo que ya era público es borrarlo por la puerta de atrás."""
    spec_editable(lambda d: d["tools"]["vault_audit"].setdefault(
        "internal_fields", []).append("healthIndex"))
    resultado = vscc.revisar_campos()
    assert resultado["ok"] is False
    assert {"tool": "vault_audit", "field": "healthIndex"} in resultado[
        "demoted_to_internal"]


def test_una_anotacion_que_apunta_a_un_campo_inexistente_se_rechaza(spec_editable):
    spec_editable(lambda d: d["tools"]["vault_audit"]["superseded_fields"][
        "healthScore"].update({"superseded_by": "healthQuePasoConEl"}))
    resultado = vscc.revisar_campos()
    assert resultado["ok"] is False
    assert any("healthQuePasoConEl" in a["problem"]
               for a in resultado["bad_annotations"])


def test_una_anotacion_sin_motivo_se_rechaza(spec_editable):
    spec_editable(lambda d: d["tools"]["vault_audit"]["superseded_fields"][
        "healthScore"].pop("why"))
    resultado = vscc.revisar_campos()
    assert resultado["ok"] is False
    assert any("why/reason" in a["problem"] for a in resultado["bad_annotations"])


def test_retirar_la_tool_entera_no_cuenta_como_romper_campos(spec_editable):
    """Que una tool se archive lo vigila --check-contracts, no esta puerta.

    Contarlo dos veces daría un fallo por cada campo de la tool y enterraría el
    hallazgo real bajo veinte líneas de ruido.
    """
    spec_editable(lambda d: d["tools"]["vault_audit"].update({"status": "archived"}))
    resultado = vscc.revisar_campos()
    assert resultado["ok"] is True, resultado
    assert "vault_audit" not in vscc.tabla_de_compatibilidad()


# ── La CLI y la puerta ───────────────────────────────────────────────────────


def _correr(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_spec_catalog_check.py"), *args],
        capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT),
    )


def test_check_fields_sale_con_cero_cuando_esta_verde():
    proc = _correr("--check-fields", "--strict")
    assert proc.returncode == 0, proc.stdout
    assert json.loads(proc.stdout)["ok"] is True


def test_check_fields_falla_con_codigo_del_catalogo(spec_editable):
    """AP-52: el fallo sale con `error_code` y `recovery`, no como cadena libre."""
    spec_editable(lambda d: d["tools"]["vault_audit"]["declared_returns"].remove(
        "healthIndex"))
    proc = _correr("--check-fields", "--strict")
    assert proc.returncode == 1
    envelope = json.loads(proc.stdout)
    assert envelope["error_code"] == "CONTRACT_FIELD_REMOVED"
    assert envelope["recovery"]["hint"]


def test_la_tabla_se_publica_en_markdown():
    proc = _correr("--fields-table", "--markdown")
    assert proc.returncode == 0
    assert "| `vault_audit` | `healthScore` | superseded | healthIndex |" in proc.stdout


def test_la_puerta_esta_registrada_en_vault_gate():
    import vault_gate

    puerta = next((p for p in vault_gate.PUERTAS if p["id"] == "campos"), None)
    assert puerta is not None, "la puerta existe o no existe; documentarla no basta"
    assert puerta["cmd"] == [
        "vault_spec_catalog_check.py", "--check-fields", "--strict"]
    assert puerta["fix"], "una puerta sin arreglo publicado se acaba desactivando"


def test_check_fields_no_escribe_nada():
    """Una comprobación que toca la baseline deja de ser una comprobación."""
    antes = vscc.FIELDS_BASELINE.read_bytes()
    _correr("--check-fields", "--strict")
    assert vscc.FIELDS_BASELINE.read_bytes() == antes
