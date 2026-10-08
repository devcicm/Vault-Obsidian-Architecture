"""AP-51 en la cadena de guards de escritura del servidor MCP.

Medido el 2026-10-08: `buildStemPathMap` se tragaba el fallo de `readdir`
con `catch (_) {}` y guardaba en caché un mapa parcial. Con un directorio
ilegible, el guard de notas referenciadas acusaba a la nota que se iba a
escribir —`note_not_found`— de enlazar a una nota que existe: el fallo de
la tool convertido en un veredicto sobre el dato.
"""

from test_backup_base64 import _ilegible
from test_mcp_runner import SesionMCP, _init_vault

_CONTENIDO = (
    "Primera línea de contenido real para el guard de longitud.\n"
    "Segunda línea que enlaza a [[destino]] dentro del vault.\n"
    "Tercera línea para que la nota no parezca un esqueleto vacío.\n"
)


def _escribir(vault, contenido):
    s = SesionMCP(vault)
    try:
        r = s.llamar("vault_write", {
            "title": "Nota que enlaza", "folder": "07_Knowledge", "content": contenido,
        })
    finally:
        s.cerrar()
    return r["result"]["content"][0]["text"]


def test_un_directorio_ilegible_no_se_publica_como_nota_inexistente(tmp_path):
    vault = _init_vault(tmp_path / "vault")
    cerrado = vault / "07_Knowledge" / "cerrado"
    cerrado.mkdir(parents=True)
    (cerrado / "destino.md").write_text("# Destino\n", encoding="utf-8")

    with _ilegible(cerrado):
        texto = _escribir(vault, _CONTENIDO)
    assert "note_not_found" not in texto, texto
    assert "vault_unreadable" in texto, texto
