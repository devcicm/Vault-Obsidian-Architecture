"""Los vocabularios cerrados del estándar, cada uno con un contexto dueño.

`critical | high | medium | low` estaba escrito a mano en catorce ficheros de
`scripts/`: cuatro veces como `choices=` de argparse, diez como constante de
módulo, y con dos variantes que nadie declaraba como tales —`vault_log_error`
añade `info`, `vault_norms` añade `N/A` para los patterns—. Nada ataba esas
copias entre sí: la que se quedase atrás rechazaría un valor válido o aceptaría
uno inventado, y en ninguno de los dos casos habría un test que lo notara.

Es AP-05 sobre vocabulario, y el precedente de cómo se corrige ya existe en el
repo: `vault_norms.DOMAIN_STATUS_VOCABS` resolvió exactamente esto para el campo
`status` y se quedó ahí, sin que ningún otro vocabulario lo siguiera.

Lo que este registro añade sobre una simple constante compartida es el **dueño**:
cada vocabulario declara el contexto acotado que manda sobre él, y ese contexto
tiene que existir en `vault_arch.CONTEXTS`. Un vocabulario sin dueño es una
decisión que nadie tomó y que por eso se acaba tomando en cada punto de uso.

Vive en `scripts/` y no en el paquete `vault/` por la misma razón que
`vault_entorno.py`: un módulo de `scripts/` tiene que seguir funcionando
**copiado suelto**, que es cómo se sincronizan los repos consumidores.

Este módulo es kernel: declara, no decide. Los vocabularios que ya son de otro
registro —CIA, `status`, los estados de dominio— **no se copian aquí**: se
declaran con `derivado_de` y `valores()` los resuelve **al llamarse**, nunca al
importarse (AP-49). Importar `vault_fundamentals` en tiempo de import ataría
este registro a que haya un vault montado.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class Vocabulario:
    """Un vocabulario cerrado y todo lo que hay que saber de él.

    `valores` queda vacío cuando `derivado_de` apunta a otro registro: la lista
    literal es justamente lo que este módulo existe para no volver a escribir.
    """

    nombre: str
    contexto: str
    proposito: str
    valores: Tuple[str, ...] = ()
    default: str | None = None
    #: `"modulo:accesor"` o `"modulo:CONSTANTE"` del registro que ya lo declara.
    derivado_de: str | None = None
    #: Vocabulario del que este es una ampliación declarada (no-derogación).
    amplia: str | None = None


VOCABULARIOS: Dict[str, Vocabulario] = {
    # ── Gobernanza ────────────────────────────────────────────────────────────
    "severidad": Vocabulario(
        nombre="severidad",
        contexto="gobernanza",
        proposito=(
            "Cuánto cuesta que esto esté mal. Ordena hallazgos de auditoría, "
            "normas, bugs y riesgos con la misma escala."
        ),
        valores=("critical", "high", "medium", "low"),
        default="medium",
    ),
    "severidad_con_info": Vocabulario(
        nombre="severidad_con_info",
        contexto="gobernanza",
        proposito=(
            "La escala de `severidad` más `info`, para lo que se registra sin "
            "que sea un problema. La usa `vault_log_error` en 02_Observability."
        ),
        valores=("critical", "high", "medium", "low", "info"),
        default="medium",
        amplia="severidad",
    ),
    "severidad_con_na": Vocabulario(
        nombre="severidad_con_na",
        contexto="gobernanza",
        proposito=(
            "La escala de `severidad` más `N/A`: un patrón (PAT) no tiene "
            "gravedad porque no describe un fallo. La usa `vault_norms`."
        ),
        valores=("critical", "high", "medium", "low", "N/A"),
        amplia="severidad",
    ),
    "cia_integrity": Vocabulario(
        nombre="cia_integrity",
        contexto="gobernanza",
        proposito="Integridad del dato. Endurece el umbral de actualidad.",
        derivado_de="vault_fundamentals:cia_valores",
        default="medium",
    ),
    "cia_availability": Vocabulario(
        nombre="cia_availability",
        contexto="gobernanza",
        proposito=(
            "Disponibilidad del dato. La asimetría es del registro y es real: "
            "no admite `critical`."
        ),
        derivado_de="vault_fundamentals:cia_valores",
        default="medium",
    ),
    "cia_sensitivity": Vocabulario(
        nombre="cia_sensitivity",
        contexto="gobernanza",
        proposito="Confidencialidad. `restricted` activa revisión de secretos.",
        derivado_de="vault_fundamentals:cia_valores",
        default="internal",
    ),
    "status": Vocabulario(
        nombre="status",
        contexto="gobernanza",
        proposito=(
            "Estado de ciclo de vida de una nota (CN-03). Único campo que ya "
            "tenía registro canónico antes de este módulo."
        ),
        derivado_de="vault_norms:STATUS_VOCAB",
    ),
    # ── Autoría ───────────────────────────────────────────────────────────────
    "bug_state": Vocabulario(
        nombre="bug_state",
        contexto="autoria",
        proposito=(
            "Estado del defecto, en su propio campo y no compitiendo con "
            "`status` (AP-38)."
        ),
        derivado_de="vault_norms:DOMAIN_STATUS_VOCABS",
    ),
    "pattern_state": Vocabulario(
        nombre="pattern_state",
        contexto="autoria",
        proposito="Estado de implementación de un patrón.",
        derivado_de="vault_norms:DOMAIN_STATUS_VOCABS",
    ),
    "test_result": Vocabulario(
        nombre="test_result",
        contexto="autoria",
        proposito="Resultado de la última ejecución de un test.",
        derivado_de="vault_norms:DOMAIN_STATUS_VOCABS",
    ),
    "prioridad": Vocabulario(
        nombre="prioridad",
        contexto="autoria",
        proposito="Orden de atención de una tarea o un bug. P1 es lo primero.",
        valores=("P1", "P2", "P3", "P4"),
        default="P3",
    ),
    # ── Consulta ──────────────────────────────────────────────────────────────
    "detalle": Vocabulario(
        nombre="detalle",
        contexto="consulta",
        proposito=(
            "Cuánto contexto se empaqueta en una respuesta. Escrito dos veces "
            "como `choices=` sin que nada atara las dos copias."
        ),
        valores=("minimal", "standard", "full"),
        default="standard",
    ),
}


def valores(nombre: str) -> Tuple[str, ...]:
    """Los valores admitidos, resueltos **al llamarse**.

    Un vocabulario derivado no guarda su lista: la pide al registro que manda.
    Resolverlo aquí y no en el import es lo que impide que este módulo herede
    la dependencia de vault de `vault_fundamentals` (AP-49).
    """
    if nombre not in VOCABULARIOS:
        raise KeyError(
            f"{nombre!r} no está en VOCABULARIOS. Un vocabulario cerrado se "
            "declara en el registro antes de usarse — si no, vuelve a ser una "
            "decisión tomada en el punto de uso (AP-05)."
        )
    voc = VOCABULARIOS[nombre]
    if voc.derivado_de is None:
        return voc.valores

    modulo, _, simbolo = voc.derivado_de.partition(":")
    if modulo == "vault_fundamentals":
        from vault_fundamentals import cia_valores

        return tuple(sorted(cia_valores(nombre)))
    if simbolo == "STATUS_VOCAB":
        from vault_norms import STATUS_VOCAB

        return tuple(sorted(STATUS_VOCAB))
    if simbolo == "DOMAIN_STATUS_VOCABS":
        from vault_norms import DOMAIN_STATUS_VOCABS

        for campo, mapa in DOMAIN_STATUS_VOCABS.values():
            if campo == nombre:
                return tuple(mapa)
        return ()
    raise KeyError(f"{voc.derivado_de!r}: origen no reconocido")


def opciones(nombre: str) -> list:
    """Lo que le pasas a `choices=` de argparse. Lista, porque argparse la ordena."""
    return list(valores(nombre))


def tabla() -> list:
    """El registro completo, para `--vocab` y para la documentación derivada."""
    return [
        {
            "name": v.nombre,
            "context": v.contexto,
            "values": list(valores(k)),
            "default": v.default,
            "derived_from": v.derivado_de,
            "extends": v.amplia,
            "purpose": v.proposito,
        }
        for k, v in sorted(VOCABULARIOS.items())
    ]


# ── Formas derivadas (v40.7) ─────────────────────────────────────────────────
#
# `valores()` y `opciones()` cubrían el caso de listar los términos, y con eso
# se convirtieron los catorce `choices=` y constantes que eran secuencias. Lo
# que quedó fuera —y fuera también del detector, que solo miraba secuencias—
# son los mapas: catorce sitios más que escriben los mismos cuatro términos
# como claves de un diccionario para colgar de cada uno un peso, un orden, un
# cubo vacío o una ficha de datos.
#
# Un mapa cuyas claves son el vocabulario es la misma decisión duplicada que
# una lista: declara qué términos existen. Estas tres funciones son las formas
# en las que aparecía, para que el punto de uso conserve **su** dato —el peso,
# el umbral, la prosa— y deje de reescribir el conjunto de términos.


def rango(nombre: str, *, base: int = 1, mayor_primero: bool = True) -> Dict[str, int]:
    """Cada término con su posición, según el orden declarado del vocabulario.

    `rango("severidad")` da `{"critical": 4, "high": 3, "medium": 2, "low": 1}`,
    que es literalmente lo que había escrito a mano en cinco módulos para
    ordenar y para comparar contra un mínimo.

    El orden sale del registro y no del sitio de uso: eso es lo que se estaba
    decidiendo cinco veces. Que `critical` pese más que `low` no es una
    convención de `vault_impact`, es del vocabulario.
    """
    terminos = valores(nombre)
    if mayor_primero:
        return {t: base + len(terminos) - 1 - i for i, t in enumerate(terminos)}
    return {t: base + i for i, t in enumerate(terminos)}


def peso(nombre: str) -> Dict[str, float]:
    """El rango normalizado a `(0, 1]`, que es la otra forma en que aparecía.

    `vault_context_pack` lo escribía como `{"critical": 1.0, "high": 0.75, ...}`
    — el mismo reparto lineal, calculado a mano para cuatro términos. Añadir un
    quinto término al vocabulario habría dejado ese mapa incompleto en silencio,
    y una nota con el término nuevo habría puntuado cero.
    """
    ordinales = rango(nombre)
    total = len(ordinales)
    return {t: n / total for t, n in ordinales.items()}


def cubos(nombre: str, inicial):
    """Un diccionario con un término por clave y una copia de `inicial` en cada.

    `by_severity = {"critical": [], "high": [], ...}` aparecía dos veces solo en
    `vault_security_scan`, una con listas y otra con contadores. `inicial` se
    copia por término: pasar `[]` no reparte la misma lista entre todos.
    """
    import copy

    return {t: copy.deepcopy(inicial) for t in valores(nombre)}


def mapa(nombre: str, entradas: Dict[str, object]) -> Dict[str, object]:
    """Devuelve `entradas` tras comprobar que sus claves **son** el vocabulario.

    Para los mapas cuyo valor no se puede derivar: los umbrales de riesgo, las
    transiciones válidas entre estados, la ficha de cada prioridad ISO 20000-1.
    Ahí la prosa y los números son del punto de uso y ahí deben quedarse; lo
    que no es suyo es decidir qué claves existen.

    Falla al importarse, no al usarse: un mapa incompleto se descubre la vez
    que llega el término que falta, y para entonces ya devolvió un default
    silencioso en vez de un error.
    """
    esperadas = set(valores(nombre))
    reales = set(entradas)
    if reales != esperadas:
        faltan = sorted(esperadas - reales)
        sobran = sorted(reales - esperadas)
        raise KeyError(
            f"el mapa no cubre el vocabulario {nombre!r}: "
            f"faltan {faltan}, sobran {sobran}. Un término del registro sin "
            "entrada aquí acaba en un default que nadie ve."
        )
    return entradas
