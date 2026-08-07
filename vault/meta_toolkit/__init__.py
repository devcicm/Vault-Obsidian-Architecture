"""Contexto **Meta-toolkit**: opera sobre el estándar, no sobre un vault.

Lenguaje ubicuo: catálogo, contrato, spec, smoke, baseline, plano. Es el único
contexto cuya frontera es una **prohibición** en vez de una dependencia, y por
eso el que menos sentido tenía declarar en prosa: hasta v40.0, `prohibe` era una
línea del registro que ningún guard leía.

Medida al migrarlo, la prohibición tal como estaba escrita —«no escribir en un
vault»— era **falsa**: `vault_manifest` escribe `00_System/tools-manifest.json`
y `vault_spec_memory` escribe `00_System/spec-memory.json`. No es un abuso; son
artefactos derivados del propio estándar que viven en el vault porque ahí es
donde los consume un agente. Lo que estaba mal era el enunciado, no el código —
y un enunciado que el código incumple desde el primer día es una norma con
enforcement `manual`, que es justo lo que la regla 5 prohíbe.

La frontera precisa, y ya ejecutable (`vault_arch --check`):

- **Sí** puede escribir artefactos derivados del estándar en `00_System/`.
- **Sí** puede crear vaults desechables para medirse (`vault_smoke`,
  `vault_test_runner` los levantan en un temporal y los borran).
- **No** puede escribir notas ni datos del usuario en ninguna sección de
  contenido. Ese es el límite que importa y el que ahora falla si se cruza.

Tampoco declara rutas ajenas: `quality-index.json`, `propagation-queue.json`,
`.change-log.json` y `standard-version.json` los **lee** de los contextos que
los escriben. `vault_spec_memory` los derivaba por su cuenta, con lo que
`quality-index.json` llegó a calcularse en cuatro módulos de tres contextos.
"""

from .repositorio import RepositorioMetaToolkit

__all__ = ["RepositorioMetaToolkit"]
