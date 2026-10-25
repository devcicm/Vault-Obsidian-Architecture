"""El auditor historico de exposicion: cobertura declarada y privacidad.

Condiciones de la orden R01:
  1. ruta personal sintetica detectada;
  2. nombre de cuenta sintetico detectado;
  3. UTF-16 y NUL detectados;
  4. secreto sintetico detectado;
  5. marcadores neutros aceptados;
  6. fichero historico no presente en HEAD detectado;
  7. el reporte no reproduce informacion sensible;
  8. ningun resultado declara cobertura mayor que la ejecutada.

Los datos son SINTETICOS: la cuenta se deriva del entorno en tiempo de
ejecucion (nunca va en el codigo) y los secretos son patrones con forma de
credencial, no credenciales reales.
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _auditor():
    ruta = ROOT / "audits" / "fase2" / "auditar_exposicion_historica.py"
    spec = importlib.util.spec_from_file_location(
        "auditor_exposicion_historica", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


CUENTA = Path.home().name


# El fixture se compone en runtime a proposito: escribir una ruta absoluta con
# forma de ruta de maquina en el fuente publicaria lo que el test comprueba que
# se detecta (lo exige tests/test_publicacion_limpia.py).
BARRA = chr(92)
UNIDAD = "C:"


def test_detecta_ruta_personal_sintetica():
    texto = ("checkout en " + UNIDAD + BARRA + "Users" + BARRA + CUENTA
             + BARRA + "Documents" + BARRA + "logs")
    hallazgos = _auditor().clasificar(texto)
    assert any(h["categoria"] == "ruta_local" for h in hallazgos), hallazgos
    assert any(h["categoria"] == "cuenta_usuario" for h in hallazgos), hallazgos


def test_detecta_el_nombre_de_cuenta_en_prosa():
    texto = "el checkout del autor (" + CUENTA + ") quedo publicado en el log"
    hallazgos = _auditor().clasificar(texto)
    assert any(h["categoria"] == "cuenta_usuario" for h in hallazgos), hallazgos


def test_detecta_utf16_y_nul():
    texto_con_nul = "linea con caracter NUL " + chr(0) + " intercalado en el texto"
    hallazgos = _auditor().clasificar(texto_con_nul)
    assert any(h["categoria"] == "nul_utf16" for h in hallazgos), hallazgos


def test_detecta_secreto_sintetico():
    # Compuestas en runtime: los valores tienen FORMA de credencial a proposito
    # (es lo que se prueba), pero el fuente no publica la forma completa.
    muestras = [
        "AKIA" + "IOSFODNN7EXAMPLE",
        "api" + "_key = " + '"' + "clave-sintetica-123456" + '"',
        "Authorization: " + "Bearer " + "token-sintetico-1234567890",
    ]
    for muestra in muestras:
        hallazgos = _auditor().clasificar(muestra)
        assert any(h["categoria"] == "forma_secreto" for h in hallazgos), muestra


def test_los_marcadores_neutros_no_son_exposicion():
    marcadores = [
        "checkout local en <RUTA-LOCAL> (sustituido por el saneamiento)",
        "la cuenta era <USUARIO>",
        "C:/Users/<autor>/Vault-Obsidian-Architecture/logs",
        "C:/Users/usuario/proyecto",
    ]
    for muestra in marcadores:
        hallazgos = _auditor().clasificar(muestra)
        categorias = {h["categoria"] for h in hallazgos}
        assert not categorias, (muestra, categorias)


def test_el_blob_que_nombra_qa_esta_expuesto_y_el_head_no():
    """QA nombro el blob de 44f6f89:audits/fase2/logs/L3-TD0001-antes.txt como
    expuesto. La verificacion exacta es sobre ESE BLOB (git show), no sobre el
    diff del commit: el escaneo por diff solo atribuye la exposicion al commit
    que INTRODUJO las lineas."""
    import subprocess
    blob = subprocess.run(
        ["git", "show", "44f6f893670d8080703342878aca465650987604:"
                        "audits/fase2/logs/L3-TD0001-antes.txt"],
        cwd=str(ROOT), capture_output=True).stdout
    assert blob, "el blob del commit 44f6f89 no existe"
    # La salida del gate fue escrita por PowerShell en UTF-16: la ruta real
    # lleva NUL entre caracteres. El exposure se ve al DECODIFICAR, como haria
    # el saneamiento real (audits/fase2/comprobar_saneamiento.py).
    texto = blob.decode("utf-16-le", errors="ignore")
    assert "Users" in texto, "el blob no contiene la ruta que se pretendia detectar"
    hallazgos = _auditor().clasificar(texto)
    assert any(h["categoria"] == "ruta_local" for h in hallazgos), hallazgos
    assert not any(h["categoria"] == "forma_secreto" for h in hallazgos), hallazgos


def test_la_historia_muestra_exposicion_y_el_head_esta_limpio():
    informe = _auditor().escanear_historia(
        ("audits/fase2/logs/", "audits/handoff/logs/", "audits/fase2/", "audits/handoff/"))
    assert informe["commits_considerados"] > 0, informe
    assert informe["commits_con_exposicion"], "la historia tiene exposicion conocida"
    assert informe["forma_secreto_encontrada"] == 0, informe["categorias"]


def test_el_estado_actual_esta_saneado():
    problemas = _auditor().estado_actual(
        ("audits/fase2/logs/", "audits/handoff/logs/", "audits/fase2/", "audits/handoff/"))
    assert problemas == [], problemas


def test_el_reporte_no_reproduce_la_informacion_sensible():
    informe = _auditor().escanear_historia(
        ("audits/fase2/logs/", "audits/handoff/logs/", "audits/fase2/", "audits/handoff/"))
    volcado = json.dumps(informe, ensure_ascii=False)
    assert CUENTA not in volcado, "el reporte reproduce el identificador de cuenta"
    assert "Carlos" not in volcado, "el reporte reproduce el nombre personal"


def test_la_cobertura_declarada_coincide_con_la_ejecutada():
    """H-F2-06: las metricas se declaran por separado y no se sobreafirman."""
    informe = _auditor().escanear_historia(
        ("audits/fase2/logs/", "audits/handoff/logs/", "audits/fase2/", "audits/handoff/"))
    assert informe["commits_considerados"] > 0
    assert informe["commits_considerados"] >= len(informe["commits_con_exposicion"])
    assert informe["ficheros_considerados"] > 0
    assert informe["deltas_inspeccionados"] >= informe["ficheros_considerados"]
    assert informe["blobs_inspeccionados"] == 0, "no se leen blobs completos"
    assert informe["errores"] == []
    for hallazgo in informe["hallazgos"]:
        assert hallazgo["commit"], hallazgo
        assert hallazgo["fichero"], hallazgo
        assert hallazgo["huellas"], hallazgo


def test_una_historia_sin_hallazgos_se_declara_asi():
    """H-F2-06: 'sin exposicion' es una conclusion sobre lo considerado, no un cero
    fabricado; y un historial limpio no infla `commits_con_exposicion`."""
    informe = _auditor().escanear_historia(("audits/fase2/logs/CI-cierre.txt",))
    assert informe["commits_considerados"] > 0, informe
    assert informe["commits_con_exposicion"] == [], informe
    assert informe["blobs_inspeccionados"] == 0