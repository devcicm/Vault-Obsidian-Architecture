"""AP-21 medida sobre el texto crudo rechazaba documentar la propia norma.

`vault_write` y `cli.safety` corrían el regex de wikilink-con-ruta sobre el
contenido tal cual. Consecuencia: una nota que **enseña** la sintaxis mala
dentro de un fence —que es exactamente como la escribe el manifiesto— no se
podía guardar. El resto de medidas de `scan_content` siguen mirando el crudo:
un carácter invisible dentro de un fence sigue siendo un carácter invisible.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ))

NOTA = "\n".join([
    "Esta nota documenta AP-21 con un ejemplo de lo que NO se debe escribir.",
    "El grafo pierde la arista en cuanto la nota cambia de carpeta, y por eso",
    "el estandar lo prohibe en todas las notas que crea cualquier tool.",
    "",
    "```markdown",
    "[[07_Knowledge/nota-ejemplo]]",
    "```",
    "",
    "La forma correcta es escribir solo el nombre de la nota destino.",
])


def test_el_ejemplo_en_fence_no_dispara_el_guard_de_write():
    import vault_write

    assert vault_write.detect_path_anchored(NOTA) == []


def test_el_ejemplo_en_fence_no_dispara_el_scan_de_safety():
    from cli import safety

    codigos = [f.code for f in safety.scan_content(NOTA, "content")]
    assert "AP-21" not in codigos


def test_fuera_del_fence_si_dispara():
    """El recorte no desarma la norma: el enlace real sigue rechazandose."""
    from cli import safety

    import vault_write

    mala = NOTA + "\n\nY aqui va de verdad: [[07_Knowledge/nota-ejemplo]].\n"
    assert vault_write.detect_path_anchored(mala)
    assert "AP-21" in [f.code for f in safety.scan_content(mala, "content")]


def test_las_demas_medidas_siguen_mirando_dentro_del_fence():
    """AP-21 es la unica que se recorta: un invisible en un fence sigue contando."""
    from cli import safety

    con_invisible = "\n".join([
        "Una nota normal con suficiente texto para que el scan tenga material.",
        "```",
        "texto​con invisible dentro del bloque de codigo",
        "```",
    ])
    codigos = [f.code for f in safety.scan_content(con_invisible, "content")]
    assert "POISON-INVISIBLE" in codigos
