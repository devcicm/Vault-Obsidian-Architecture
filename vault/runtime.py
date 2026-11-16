"""La raíz de composición: quién se ofrece a quién al arrancar una tool.

## Qué es

Un proceso corre **una** tool. Ese proceso es la raíz de composición: es el
sitio donde se decide qué producers existen y qué implementaciones se ofrecen.
Hoy esa decisión no existe —cada módulo que necesita algo lo importa— y de
ahí vienen los cruces que la auditoría nombró.

## Por qué aquí y no en el kernel

El kernel **prohíbe** depender de un contexto de dominio
(`CONTEXTS["kernel"]["prohibe"]`). Si el kernel ofreciera la voz importando
`vault.autoria.voz`, el cruce `kernel -> autoria` seguiría existiendo con otro
nombre. Este módulo no es del kernel: es el **runtime**, y su oficio es
justamente el cableado —componer es lo que hace un runtime.

Por eso puede importar de los dos lados sin que sea un ciclo: no es un módulo
de dominio que sube a un dominio, es el sitio donde se enchufan.

## Qué ofrece

| Productor | Lo ofrece | Para qué |
|---|---|---|
| `voz` | `vault.autoria.voz` | el recordatorio que acompaña a cada envelope (AP-43) |
| `indices` | `vault_section_index` | regenerar el índice de sección tras una escritura (A-03) |
| `bitacora_cambios` | `vault.autoria.bitacora` | la fila de la bitácora y el anexo para consulta y gobernanza (`ingested`, `linted`) |

Cada uno **se ofrece al importarse**: el módulo que lo implementa se registra
en `vault.kernel.productores` cuando se carga. Quien quiera solo el registro
del kernel no carga la Autoría.

## Por qué no se ofrecen «por defecto» al importar este módulo

Porque ofrecerlos todos cargaría la Autoría y el regenerador de índices en
**todas** las tools, incluidas las que no los usan. Se ofrecen **bajo
demanda**: `componer()` ofrece lo que la tool necesita, y el resto del
proceso no lo carga.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

#: Los productores que el runtime sabe ofrecer. La clave es el nombre del
#: puerto; el valor es el módulo que lo implementa.
PRODUCTORES: Dict[str, str] = {
    "voz": "vault.autoria.voz",
    "indices": "vault_section_index",
    "tags": "vault_tags",
    "coherencia_indices": "vault.indices.proveedor_coherencia",
    # Change log and append path for consulta/gobernanza (2026-11-16): the
    # `ingested` and `linted` rows and the appends `vault_ingest` applies.
    "bitacora_cambios": "vault.autoria.bitacora",
}


def componer_coherencia_indices() -> bool:
    """Offer the read-only provider without writing diagnostic traces."""
    import importlib
    from vault.kernel import productores

    nombre = "coherencia_indices"
    if productores.hay(nombre):
        return True
    modulo = PRODUCTORES[nombre]
    importado = importlib.import_module(modulo)
    _reofrecer(modulo, importado)
    return productores.hay(nombre)


def comprobar_coherencia_indices(raiz=None) -> dict:
    """Return a sanitized read-only search-index verification status."""
    try:
        if not componer_coherencia_indices():
            return {"status": "index_unavailable"}
        from vault.kernel import construir

        contexto = construir(raiz)
        proveedor = contexto.coherencia_indices
        estado = proveedor.comprobar(contexto).get("status") if proveedor else None
        validos = {"index_ok", "index_stale", "index_incomplete", "index_unverified",
                   "index_missing", "index_corrupt"}
        return {"status": estado if estado in validos else "index_unavailable"}
    except Exception:
        return {"status": "index_unavailable"}


def _importar(modulo: str) -> Optional[Any]:
    """Importa un módulo y devuelve `None` si no se puede.

    El runtime degrada: un producto que no está disponible no rompe la tool.

    **`sys.modules` puede devolver el módulo sin ejecutar su cuerpo**: si
    otro importador lo cargó antes —o si el registro se vació después—, el
    producto no se vuelve a ofrecer. Por eso, tras importar, se comprueba que
    el registro lo tiene y, si no, se vuelve a ofrecer el que el módulo
    expone. Sin esto, vaciar el registro en un test dejaba al runtime
    incapaz de recuperar el producto durante el resto de la sesión.
    """
    import importlib

    try:
        importado = importlib.import_module(modulo)
    except ImportError as exc:
        # Un módulo que NO está es un estado legítimo: el producto puede no
        # estar instalado. Se avisa (AP-51) y se sigue sin él.
        _aviso("productor_no_cargable", modulo, exc)
        return None
    _reofrecer(modulo, importado)
    return importado


def _aviso(codigo: str, modulo: str, exc: Exception) -> None:
    """Deja el motivo del fallo en la traza del vault, si la hay.

    El runtime no es un módulo de tool: no puede emitir un envelope. Lo que
    puede es dejar el motivo donde el resto del toolkit deja el suyo —la
    traza— y no tragárselo (AP-51). Si la traza tampoco está (no hay vault),
    el fallo se queda sin escribir, pero **consta** en la excepción que lo
    produjo: quien llama lo decide.
    """
    try:
        from vault.kernel.errors_trace import log_trace

        log_trace({
            "ok": False,
            "tool": "vault_runtime",
            "error_code": codigo,
            "message": f"el productor {modulo!r} no se pudo cargar: {exc}",
        })
    except Exception as fallo_de_traza:
        # Sin traza no hay dónde dejarlo. Se dice igual, con el aviso de
        # Python: un `pass` aquí sería el silencio que AP-51 prohíbe. Y si ni
        # el aviso se puede emitir, el motivo original sigue en la excepción
        # que lo produjo —quien llama lo ve.
        import warnings

        try:
            warnings.warn(
                f"el productor {modulo!r} no se pudo cargar: {exc} "
                f"(y tampoco se pudo dejar en la traza: {fallo_de_traza})",
                RuntimeWarning,
                stacklevel=2,
            )
        except Exception:
            # El último recurso: la excepción original, que sigue viva y
            # llega hasta quien la pidió. No se traga.
            raise


def _reofrecer(modulo: str, importado: Any) -> None:
    """Vuelve a ofrecer el producto si el módulo ya cargado no lo hizo.

    El cuerpo del módulo —el que se registra— se ejecuta una vez por proceso.
    Si el registro se vació después, quien llama tiene que poder recuperarlo.
    """
    from vault.kernel import productores

    nombre = _nombre_de(modulo)
    if nombre is None or productores.hay(nombre):
        return
    oferente = getattr(importado, "_ofrecer", None)
    if callable(oferente):
        oferente()


def _nombre_de(modulo: str) -> Optional[str]:
    """El nombre del puerto que implementa un módulo, si lo implementa."""
    for nombre, ruta in PRODUCTORES.items():
        if ruta == modulo:
            return nombre
    return None


def componer(*nombres: str) -> Dict[str, Any]:
    """Ofrece los productores pedidos y devuelve lo que se ha quedado.

    `nombres` son los del puerto: `"voz"`, `"indices"`. Lo que no se puede
    ofrecer **no se oferece**, y eso es un estado observable
    (`vault.kernel.productores.registrados()`), no un fallo silencioso: quien
    llama sabe que no lo tiene.
    """
    from vault.kernel import productores

    for nombre in nombres:
        if productores.hay(nombre):
            continue
        modulo = PRODUCTORES.get(nombre)
        if not modulo:
            continue
        _importar(modulo)  # el módulo se registra solo al importarse
    return productores.registrados()


def componer_voz() -> bool:
    """Ofrece la voz. Devuelve si ha quedado alguien que atienda."""
    from vault.kernel import productores

    componer("voz")
    return productores.hay("voz")


def bitacora_de_cambios() -> Optional[Any]:
    """The `bitacora_cambios` producer, composed on demand, or `None`.

    Same contract as `vault_io._regenerador_de_indices`: a library caller that
    did not compose it still gets it, and an absent producer is a value the
    caller can check and report, never a silent loss.
    """
    from vault.kernel import productores

    if not productores.hay("bitacora_cambios"):
        componer("bitacora_cambios")
    return productores.buscar("bitacora_cambios")


def anotar_operacion(accion: str, ruta: str, motivo: str, agente: str) -> Dict[str, Any]:
    """One operation-log row through the port, as an envelope fragment.

    `{"change_log": {"id", "action"}}` when the row was written, or
    `{"change_log_error": <reason>}` when it was not. The reason is sanitized
    (AP-51): it names the port or the error code, never a path or a trace,
    because it travels in the envelope of the tool that called it.
    """
    try:
        bitacora = bitacora_de_cambios()
    except Exception as exc:  # the composer must never take the action down
        return {"change_log_error": f"bitacora_cambios: {type(exc).__name__}"}
    if bitacora is None:
        return {"change_log_error": "nadie atiende el puerto bitacora_cambios: "
                                    "no se anotó la fila"}
    try:
        fila = bitacora.anotar(accion, ruta, motivo, agente)
    except Exception as exc:
        return {"change_log_error": f"bitacora_cambios: {type(exc).__name__}"}
    if isinstance(fila, dict) and fila.get("ok") and fila.get("id"):
        return {"change_log": {"id": fila["id"], "action": accion}}
    codigo = fila.get("error_code") if isinstance(fila, dict) else None
    return {"change_log_error": f"bitacora_cambios: {codigo or 'la bitácora rechazó la fila'}"}


def componer_indices() -> bool:
    """Ofrece el regenerador de índices. Devuelve si ha quedado alguien."""
    from vault.kernel import productores

    componer("indices")
    return productores.hay("indices")
