"""AP-69 — límite declarado: la norma no tiene versión publicada.

Entra en la rama reestructura/teseo, que no sube versión, y AP-55 rechaza una
`introduced_version` posterior a la vigente. Este test fija el hueco y falla
el día que el release escriba la versión: entonces la deuda
`ap69_sin_version_publicada` pasa a `saldada`.
"""

import vault_norms_catalog as cat


def test_limite_declarado_ap69_sin_version_publicada():
    norma = cat.norma_por_codigo("AP-69")
    assert "introduced_version" not in norma, (
        "AP-69 ya tiene version: salda la deuda ap69_sin_version_publicada")
