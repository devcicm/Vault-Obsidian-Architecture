"""El vocabulario con el que el dominio nombra lo que salió mal.

Nace de la deuda declarada `envelopes_del_dominio_sin_error_code` (v40.9), que
llevaba nueve versiones abierta con el motivo escrito: *«la pregunta de fondo no
es cómo se escribe el envelope sino quién lo escribe»*. Nueve sitios de
`vault/indices/` y `vault/durabilidad/` devolvían `{"ok": False, "error": "..."}`
—la forma exacta del envelope de una tool— y los adaptadores de `scripts/` lo
reenviaban tal cual al consumidor, sin `error_code` y sin `recovery`. Es AP-52
cometido una capa más adentro, donde el guard lo veía pero no había dónde
arreglarlo.

Las dos salidas obvias eran malas y por eso la deuda esperó:

- **Que el dominio importe `vault_errors`** lo ata al catálogo de la
  herramienta. Un dominio que sabe qué es un `recovery.action` ya no es dominio:
  es la tool escrita en otro directorio, y el kernel dejaría de poder decir que
  no depende de nadie.
- **Que el dominio devuelva un dict con más campos** no mueve nada: el envelope
  seguiría escrito donde no se sabe quién lo va a leer.

La salida es partir la frase en dos mitades y darle dueño a cada una. El
**dominio nombra la causa** —qué pasó, en su propio vocabulario, sin saber que
existe un JSON— y la **tool nombra la recuperación** —qué código del catálogo le
corresponde y qué puede hacer el consumidor—. La traducción vive en un solo
sitio, `vault_errors.emit_fallo`, porque una tabla de equivalencias copiada en
tres adaptadores sería AP-57 cometido al saldar AP-52.

Se señala **levantando**, no devolviendo. Un fallo devuelto como valor se puede
ignorar por olvido —basta con no mirar `["ok"]`—, y estos cuatro casos incluyen
el de una operación destructiva sin confirmar. Que el adaptador tenga que
escribir el `except` es justamente el punto: es la frontera, y ahí es donde se
decide qué ve el consumidor.

Este módulo no importa nada fuera de `typing`: es kernel, y el kernel no depende
de nadie.
"""

from __future__ import annotations

from typing import Any, Dict

#: Causa -> qué significa, en el vocabulario del dominio.
#:
#: La lista es cerrada a propósito y `vault_errors.MAPA_DE_FALLOS` tiene que
#: cubrirla entera: una causa nueva sin traducción saldría al consumidor por el
#: camino genérico, que es la opacidad que esta deuda vino a cerrar. Un test lo
#: comprueba en las dos direcciones.
CAUSAS: Dict[str, str] = {
    "CARPETA_YA_REGISTRADA":
        "la ruta ya está en el registro de carpetas; registrarla dos veces "
        "produciría dos entradas para la misma carpeta.",
    "CARPETA_NO_ENCONTRADA":
        "la ruta no está en el registro, así que no hay nada que eliminar. No "
        "dice nada sobre si la carpeta existe en disco: eso es `huerfanas()`.",
    "BACKUP_NO_ENCONTRADO":
        "no hay snapshot con ese nombre en ninguna de las ubicaciones que el "
        "adaptador declaró buscar.",
    "MANIFIESTO_AUSENTE":
        "el snapshot existe pero no lleva manifiesto, así que no hay huella "
        "sellada contra la que comparar.",
    "MANIFIESTO_ILEGIBLE":
        "el manifiesto está pero no se puede leer como JSON. La copia puede "
        "estar truncada.",
    "MANIFIESTO_SIN_HUELLA":
        "el manifiesto no declara `merkle_root`. Es lo que ocurre con copias "
        "anteriores a v29: no es corrupción, es que aún no se sellaban.",
    "CONFIRMACION_REQUERIDA":
        "la operación borra datos del usuario y no se confirmó. No tiene "
        "default permisivo a propósito.",
}


class FalloDeDominio(Exception):
    """Algo que el dominio sabe que salió mal, dicho sin forma de envelope.

    `causa` es una clave de `CAUSAS`. `datos` lleva lo que el consumidor
    necesita para actuar y que solo el dominio conoce —dónde se buscó, qué ruta
    se pidió—; viaja como diccionario y no como campos fijos porque cada causa
    aporta lo suyo y una firma común los obligaría a compartir vocabulario sin
    razón.

    El mensaje se conserva en castellano o en inglés según lo que ya emitía cada
    sitio antes de v40.29: cambiarlo aquí habría movido texto que los
    consumidores pueden estar leyendo, y esta tanda decide **quién escribe el
    envelope**, no cómo se redacta.
    """

    def __init__(self, causa: str, mensaje: str, **datos: Any) -> None:
        if causa not in CAUSAS:
            raise ValueError(
                f"causa no declarada en fallos.CAUSAS: {causa!r}. "
                "Una causa sin entrada no tiene traducción al catálogo de "
                "errores y saldría al consumidor como fallo opaco."
            )
        super().__init__(mensaje)
        self.causa = causa
        self.mensaje = mensaje
        self.datos: Dict[str, Any] = datos

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"FalloDeDominio({self.causa!r}, {self.mensaje!r}, **{self.datos!r})"
