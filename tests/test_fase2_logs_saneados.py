"""Las evidencias publicadas no pueden llevar la maquina de quien las produjo.

Una log de auditoria vive en un repo publico: sin ruta local identificable, sin
nombre de persona, sin bytes NUL (que delatan un UTF-16 que un visor de texto
lee como ruido) y sin nada con forma de credencial. La comprobacion es
ejecutable y reusable (`audits/fase2/comprobar_saneamiento.py`); este test la
deja cubierta por la suite, que es lo que evita que el proximo lote reintroduzca
la fuga.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def _cargar_comprobar_saneamiento():
    """Carga por ruta: `audits/fase2/` no es un paquete de la suite."""
    import importlib.util

    ruta = ROOT / "audits" / "fase2" / "comprobar_saneamiento.py"
    spec = importlib.util.spec_from_file_location("comprobar_saneamiento", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


comprobar_saneamiento = _cargar_comprobar_saneamiento()


def test_las_evidencias_publicadas_estan_saneadas():
    problemas = comprobar_saneamiento.revisar(ROOT)
    assert problemas == [], "\n".join(f"{f}: {m}" for f, m in problemas)


def test_el_verificador_detecta_lo_que_declara_detectar(tmp_path):
    """El verificador tiene que FINDIR con una fuga de verdad: un test que
    solo dice 'todo bien' no prueba que sepa mirar."""
    audits = tmp_path / "audits" / "logs"
    audits.mkdir(parents=True)
    # Compuesto en runtime: publicar la ruta en el fuente seria la fuga que
    # este test comprueba que el verificador sabe ver.
    barra = chr(92)
    ruta_sintetica = "checkout en C:" + barra + "Users" + barra + "alguien" \
        + barra + "proyecto" + barra + "logs"
    (audits / "con_ruta.txt").write_text(ruta_sintetica, encoding="utf-8")
    (audits / "con_nul.txt").write_bytes("contenido en utf-16".encode("utf-16-le"))
    clave_sintetica = "api" + "_key = " + '"' + "AKIA" + "IOSFODNN7EXAMPLE" + '"'
    (audits / "con_clave.txt").write_text(clave_sintetica, encoding="utf-8")
    problemas = comprobar_saneamiento.revisar(tmp_path)
    motivos = " ".join(m for _, m in problemas)
    assert "ruta local identificable" in motivos, problemas
    assert "NUL" in motivos, problemas
    assert "credencial" in motivos, problemas