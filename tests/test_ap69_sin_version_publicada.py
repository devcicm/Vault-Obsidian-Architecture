"""AP-69 — la norma ya tiene versión publicada.

Este test nació como un límite declarado: entraba en la rama
`reestructura/teseo`, que no sube versión, y AP-55 rechaza una
`introduced_version` posterior a la vigente. Fallaba el día que el release
escribiera la versión —que es justo lo que pasó en v41.26— y entonces la deuda
`ap69_sin_version_publicada` pasaba a `saldada`.

Ahora afirma lo contrario: AP-69 **tiene** versión publicada, y la publicada
es la que la nombró el release. Un AP-69 sin versión volvería a ser una norma
del catálogo sin entrada de changelog que la anuncie, que es el hueco que este
test cubría.

La deuda vive en `docs/BLUEPRINT.md`, que se deriva de los registros; ahí es
donde se ve si está saldada o no.
"""

import vault_norms_catalog as cat


def test_ap69_tiene_version_publicada():
    norma = cat.norma_por_codigo("AP-69")
    assert norma.get("introduced_version"), (
        "AP-69 sin `introduced_version`: una norma del catálogo sin entrada de "
        "changelog que la anuncie")
    assert norma["introduced_version"] == "v41.26", (
        f"AP-69 se publicó en {norma['introduced_version']}, no en v41.26")
