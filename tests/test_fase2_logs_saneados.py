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
sys.path.insert(0, str(ROOT / "audits" / "fase2"))

import comprobar_saneamiento  # noqa: E402


def test_las_evidencias_publicadas_estan_saneadas():
    problemas = comprobar_saneamiento.revisar(ROOT)
    assert problemas == [], "\n".join(f"{f}: {m}" for f, m in problemas)


def test_el_verificador_detecta_lo_que_declara_detectar(tmp_path):
    """El verificador tiene que FINDIR con una fuga de verdad: un test que
    solo dice 'todo bien' no prueba que sepa mirar."""
    audits = tmp_path / "audits" / "logs"
    audits.mkdir(parents=True)
    (audits / "con_ruta.txt").write_text(
        "checkout en C:\\Users\\alguien\\proyecto\\logs", encoding="utf-8")
    (audits / "con_nul.txt").write_bytes("contenido en utf-16".encode("utf-16-le"))
    (audits / "con_clave.txt").write_text(
        'api_key = "AKIAIOSFODNN7EXAMPLE"', encoding="utf-8")
    problemas = comprobar_saneamiento.revisar(tmp_path)
    motivos = " ".join(m for _, m in problemas)
    assert "ruta local identificable" in motivos, problemas
    assert "NUL" in motivos, problemas
    assert "credencial" in motivos, problemas