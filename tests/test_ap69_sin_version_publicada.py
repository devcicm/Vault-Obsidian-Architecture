"""AP-69 — la norma ya tiene versión publicada.

Este test nació como un límite declarado: entraba en la rama
`reestructura/teseo`, que no sube versión, y AP-55 rechaza una
`introduced_version` posterior a la vigente. Fallaba el día que el release
escribiera la versión —que es justo lo que pasó en v41.26— y entonces la deuda
`ap69_sin_version_publicada` pasaba a `saldada`.

Ahora afirma lo contrario: AP-69 **tiene** versión publicada. Un AP-69 sin
`introduced_version` volvería a ser una norma del catálogo sin entrada de
changelog que la anuncie, que es el hueco que este test cubría.

El valor no se escribe a mano: la versión publicada es un hecho del pasado —
fijarla es lo correcto—, pero la **corriente** no puede aparecer en un literal
de la suite, porque hoy dura una versión (`test_version_coherence` lo vigila).
Lo que se afirma aquí es que la versión que AP-69 lleva existe y es anterior o
igual a la vigente; la concreta la dice el changelog, que es donde vive.

La deuda vive en `docs/BLUEPRINT.md`, que se deriva de los registros; ahí es
donde se ve si está saldada o no.
"""

import vault_norms_catalog as cat
from vault.kernel.version import CURRENT_VERSION


def test_ap69_tiene_version_publicada():
    norma = cat.norma_por_codigo("AP-69")
    publicada = norma.get("introduced_version")
    assert publicada, (
        "AP-69 sin `introduced_version`: una norma del catálogo sin entrada de "
        "changelog que la anuncie")
    assert publicada <= CURRENT_VERSION, (
        f"AP-69 declara {publicada!r} y la vigente es {CURRENT_VERSION!r}: "
        "una norma no puede publicarse en una versión que todavía no existe")


def test_la_version_publicada_de_ap69_tiene_entrada_de_changelog():
    """La versión que AP-69 lleva la nombra el changelog del manifiesto.

    Sin esta entrada, la norma está publicada y no se anuncia: el hueco que
    la deuda `ap69_sin_version_publicada` nombraba, con otra forma.
    """
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent
    manifiesto = (raiz / "vault-obsidian-architecture.md").read_text(encoding="utf-8")
    publicada = cat.norma_por_codigo("AP-69").get("introduced_version")
    assert f"### {publicada} —" in manifiesto, (
        f"el changelog del manifiesto no nombra la versión {publicada!r} de AP-69")
