"""La caché de stems del servidor MCP se invalida: una nota escrita ahora
se puede enlazar ahora.

El servidor MCP cachea el mapa de stems del vault (`buildStemPathMap`) para
resolver los wikilinks del guard `referencedNotes`. La función
`invalidateStemPathCache()` **existía y no se llamaba en ningún sitio**: el
mapa quedaba congelado toda la vida del proceso, así que una nota escrita
durante una sesión no se podía enlazar — el guard la daba por inexistente
(`note_not_found`) y la escritura se rechazaba.

Medido el 2026-11-08 contra el vault `vault dev codex`: dos rechazos y una
nota que quedó `notIntegrated`. Aquí se comprueba con el criterio del
consumidor (AP-44): una sesión MCP real, una nota escrita y otra que la
enlaza.
"""

from test_mcp_runner import SesionMCP, _init_vault

CONTENIDO_ENLACEDO = (
    "Primera línea de contenido real para el guard de longitud.\n"
    "Segunda línea que enlaza a [[destino-escrito-antes]] dentro del vault.\n"
    "Tercera línea para que la nota no parezca un esqueleto vacío.\n"
)


def _escribir(sesion, titulo, contenido):
    r = sesion.llamar("vault_write", {
        "title": titulo, "folder": "07_Knowledge", "content": contenido,
        # AP-26: una nota de contenido sin tags no se escribe (el guard de
        # `tagCompleteness` la rechaza), así que sin esto la nota del
        # destino no existiría y el enlace no podría resolverse por la razón
        # equivocada. AP-16: la escritura la firma un agente.
        "tags": ["prueba"],
        "agent": "pytest",
    })
    return r["result"]["content"][0]["text"]


def test_una_nota_escrita_durante_la_sesion_se_puede_enlazar(tmp_path):
    """El caso que fallaba: la nota existe, pero el mapa la ignoraba.

    El orden importa y es el del fallo real: el mapa de stems se construye la
    **primera vez que hay un enlace que resolver**. Si una nota se escribe
    después de ese momento, el mapa no la contiene hasta que se invalida.
    """
    vault = _init_vault(tmp_path / "vault")
    sesion = SesionMCP(vault)
    try:
        # 1. Una escritura **con** un enlace: esto construye el mapa de stems.
        _escribir(sesion, "Nota que abre el mapa", (
            "Primera línea de contenido real para el guard de longitud.\n"
            "Segunda línea que enlaza a [[vault-hub]], que ya existe.\n"
            "Tercera línea para que la nota no parezca un esqueleto vacío.\n"
        ))

        # 2. Se escribe el destino, DESPUÉS del mapa.
        texto_destino = _escribir(sesion, "Destino escrito despues", (
            "Primera línea de contenido real para el guard de longitud.\n"
            "Segunda línea con texto de verdad para el cuerpo.\n"
            "Tercera línea para que la nota no sea un esqueleto.\n"
        ))
        assert "note_not_found" not in texto_destino, texto_destino

        # 3. Otra nota lo enlaza: el guard tiene que encontrarlo. Con el mapa
        #    congelado, no lo encuentra y la escritura se rechaza.
        texto_enlace = _escribir(sesion, "Nota que enlaza", (
            "Primera línea de contenido real para el guard de longitud.\n"
            "Segunda línea que enlaza a [[destino-escrito-despues]].\n"
            "Tercera línea para que la nota no parezca un esqueleto vacío.\n"
        ))
        assert "note_not_found" not in texto_enlace, texto_enlace
        assert "GUARD_CHAIN_FAILED" not in texto_enlace, texto_enlace
        # Y la escritura ocurrió de verdad: el envelope lo dice.
        assert '"ok": true' in texto_enlace, texto_enlace
    finally:
        sesion.cerrar()


def test_la_invalidadora_existe_y_se_llama(tmp_path):
    """El guard de la puerta: la función que existe para esto se usa.

    Sin esta comprobación, la invalidación podría desaparecer y el primer
    test seguiría verde en un vault donde el destino ya estaba en el mapa
    (por ejemplo, si el destino se crea antes de que el servidor arranque).
    """
    from pathlib import Path

    servidor = Path(__file__).resolve().parent.parent / "mcp" / "nodejs" / "vault-mcp-server.mjs"
    fuente = servidor.read_text(encoding="utf-8")
    llamadas = fuente.count("invalidateStemPathCache()")
    # Una definición + al menos una llamada: la definición sola es el defecto
    # que se Midió (una función muerta escrita para lo mismo).
    assert llamadas >= 2, f"invalidateStemPathCache aparece {llamadas} vez/veces"
