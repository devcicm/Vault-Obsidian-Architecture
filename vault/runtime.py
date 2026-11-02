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
}


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


def componer_indices() -> bool:
    """Ofrece el regenerador de índices. Devuelve si ha quedado alguien."""
    from vault.kernel import productores

    componer("indices")
    return productores.hay("indices")
