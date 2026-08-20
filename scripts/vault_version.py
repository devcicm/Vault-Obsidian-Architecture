#!/usr/bin/env python3
"""vault_version — la versión del estándar, y nada más.

Hoja del núcleo: no importa ningún `vault_*` y no importará ninguno. Si algún
día lo necesita, es que ha dejado de ser un recurso y deja de tener sitio aquí.

## Por qué existe (AP-62, v40.28)

`CURRENT_VERSION` vivía en `vault_standard_upgrade`, que es la tool que **sube**
el vault de una versión a otra: seis dependencias, escritura en disco y una CLI
propia. Tres módulos —`vault_changelog_check`, `vault_init`, `vault_sdd_init`—
lo importaban entero para leer una cadena de siete caracteres, y uno de los tres
cruzaba de contexto para hacerlo. El síntoma es el de AP-62 en su forma más
pura: la constante no tiene nada que ver con la maquinaria que la rodeaba, y
estaba ahí por la razón de siempre —fue el primer sitio donde hizo falta—, no
porque a nadie le pareciera su casa.

`vault_standard_upgrade` la sigue reexportando, así que ningún llamador de fuera
se rompe (no-derogación). Pero quien solo quiera el dato debe pedirlo aquí: por
la fachada se paga el motor.

## Qué NO va aquí

El número de versión aparece además en el banner del manifiesto, en la tabla de
versiones, en el badge del `README.md`, en el banner de `cli/README.md`, en
`pyproject.toml` y en el `tool-spec.json` del sandbox. Eran **seis y aquí
ponía cinco**: el de `cli/README.md` faltaba de esta lista y lo destapó
`test_el_banner_de_la_cli_coincide` al subir a v40.29, que es exactamente para
lo que ese test existe. **Ninguno se importa de aquí y ninguno debe:** son
documentos y metadatos de empaquetado, cada uno con su formato, y quien los
vigila es `vault_doc_counts` y el test del banner. Convertir este módulo en el
generador de los cinco sería mover el problema, no resolverlo.
"""

#: La versión del estándar en curso. Se sube a mano en la tanda que la cierra,
#: junto con el banner del manifiesto, la tabla de versiones, el badge del
#: README, `pyproject.toml` y el `tool-spec.json` del sandbox.
CURRENT_VERSION = "v40.34"
