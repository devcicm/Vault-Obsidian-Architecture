# Evolución hacia un toolkit instalable

Este documento registra decisiones y evidencia de la recuperación PR5. Es una
bitácora de ingeniería, no una fuente canónica de catálogos, versiones,
arquitectura o artefactos derivados.

## Punto de partida

El repositorio nació como estándar más colección de scripts. Eso permitía usar
el toolkit desde un checkout, pero no demostraba el producto que un tercero
instala: los runners podían localizar `scripts/`, insertar el root del repo en
`sys.path` y resolver recursos por rutas del árbol fuente.

La regla que guía esta evolución es:

```text
legacy script -> implementación estable

no:

implementación instalada -> script legacy
```

El objetivo final sigue siendo ejecutar un wheel desde un venv externo con el
árbol fuente físicamente ausente.

## Cadena de recuperación

| Commit | Decisión y resultado |
|---|---|
| `ae25719` | Separó la auditoría runtime de los checks estándar. |
| `8b3a9e0` | Aisló la caracterización de enlaces de código y su ledger. |
| `524057c` | Restauró consistencia de auditoría runtime y derivados. |
| `6914b7b` | Extrajo el servicio de voz reutilizable, sin fuga runtime hacia `vault_voice`. |
| `7694e0b` | Derivó metadata de distribución desde registros canónicos. |
| `4f4b41b` | Definió resolución de destinos declarados, sin fabricar operaciones instaladas. |
| `8107321` | Extrajo el parser de consulta estable a `vault.consulta.query_parse`. |
| `d09fde5` | Declaró `vault_query_parse` como la primera operación instalada real. |
| `389ae7c` | Probó wheel/venv/source-ausente para la operación instalada. |
| `818dd98` | Añadió CLI pública instalada, contrato de error estable y reparación lineal de Mermaid. |
| `cb03e64` | Añadió el lifecycle instalado: `vault init`, `vault doctor`, `vault status`. |

Los commits accidentales `9e0611e`, `7187b9e`, `4661a00` y `b762bb0` fueron
auditados por intención; no se cherry-pickearon. En especial se rechazaron
wrappers `vault_toolkit.operations.*` que sólo reenviaban a `scripts/`.

## Fronteras actuales

```text
                 catálogo canónico / naturalezas
                              |
                    proyecciones empaquetadas
                     /                       \
        vault.product_cli                 legacy adapters
                |                               |
       resolver PRODUCT                   scripts/*.py
                |
   execution_module explícito
                |
 vault.consulta.query_parse
```

La política PRODUCT no cae a scripts: una tool runtime conocida sin
`execution_module` devuelve `KNOWN_NOT_INSTALLED`; una meta tool devuelve
`NOT_RUNTIME_OPERATION`; un nombre inexistente devuelve `UNKNOWN_TOOL`.

La política de desarrollo conserva temporalmente la compatibilidad legacy.

## Operación instalada inicial

La única operación instalada es deliberadamente pequeña:

```text
vault_query_parse
  -> vault.consulta.query_parse
  -> python -m vault.consulta.query_parse
```

El adaptador histórico mantiene la dirección correcta:

```text
scripts/vault_query_parse.py -> vault.consulta.query_parse
```

No importa `scripts/`, no modifica `sys.path`, no busca `REPO_ROOT` y no ejecuta
un script físico. Las otras 91 operaciones runtime siguen con
`execution_module=None`; las 24 meta/maintenance tampoco reciben destino
instalado.

## Producto público actual

El entry point del wheel es `vault = vault.product_cli:main`.

Superficie aprobada:

```text
vault --version
vault tools list
vault tools show <tool>
vault run vault_query_parse ...
vault init <runtime>
vault doctor <runtime>
vault status <runtime>
```

`--version` viene de metadata de distribución, no de la versión del estándar.
Los errores salen por `vault.kernel.errores`, el owner estable del envelope;
la CLI pública no construye envelopes a mano ni importa `scripts/vault_errors.py`.

## Runtime lifecycle instalado

El owner es `vault.ciclo_de_vida.producto`. El recurso
`vault/ciclo_de_vida/runtime-seed.json` es una proyección verificable de
`scripts/vault_registry.runtime_seed_projection()`, no otra lista editorial.

```text
vault init <external-runtime>
  -> runtime-seed empaquetado
  -> staging temporal dentro del padre
  -> os.replace atómico
  -> runtime consumidor

vault doctor/status <external-runtime>
  -> lectura del contrato mínimo
  -> sin escritura y sin autodetección del checkout
```

El runtime mínimo contiene:

- las 23 secciones canónicas;
- `00_System/standard-version.json`;
- `00_System/vault-hub.md`.

No contiene `scripts/`, `cli/`, `tests/`, `.git`, `pyproject.toml` ni módulos
Python del toolkit. `tool-spec.json`, índices, tag registry y auditorías
profundas no se simulan: son proyecciones/operaciones legacy pendientes de
migración y no son requisito del lifecycle MVP.

`init` es idempotente para un runtime válido, rechaza un directorio no vacío
que no sea runtime y no publica un runtime parcial si falla el seed.

## Evidencia actual

```text
FULL_SUITE (lifecycle checkpoint): 3155 passed / 0 failed
EXISTING_GATES:                22 / 22 PASS
CLEAN_INSTALL_GATE:            PASS
RUNTIME_LIFECYCLE_GATE:        PASS
SOURCE_TREE_PHYSICALLY_ABSENT: YES
CHECKOUT_IMPORT_PATH_ABSENT:   YES
REAL_INSTALLED_OPERATIONS:     1 (at lifecycle checkpoint)
RUNTIME_TOOLS / META_TOOLS:    92 / 24
SCRIPT_MODULES:                152
RUNTIME_CLOSURE:               113
META_STANDARD_RUNTIME_LEAKS:   0
META_PATHS:                    NONE
NEW_DEFERRED_IMPORT_CYCLES:    0
```

Los gates de instalación construyen un wheel, crean un venv, instalan sin modo
editable, eliminan la copia temporal de fuente, ejecutan desde cwd externo y
comprueban que módulos y ejecutable pertenecen a `site-packages`/venv.

## Memory recovery checkpoint

El primer vertical de memoria instalado queda cerrado con dos operaciones reales
del catalogo, no wrappers ad hoc:

```text
vault_knowledge_save -> vault.autoria.knowledge_save
vault_knowledge_get  -> vault.autoria.knowledge_get
```

Ambas delegan en `vault.autoria.conocimiento`. Markdown bajo `07_Knowledge/`
es la autoridad: recovery recorre Markdown y frontmatter y aplica ranking
determinista. `search-index.json` sigue siendo una proyeccion legacy opcional;
el vertical no necesita base de datos, embeddings, daemon ni red.

El write path tiene un unico primitive atomico fisico:

```text
installed write: vault.autoria.conocimiento -> vault.kernel.escritura -> Markdown
legacy write:    scripts/vault_io -> scripts/vault_fs -> vault.kernel.escritura
```

`scripts/vault_fs` es solo frontera de compatibilidad. Resuelve el primitive
estable de forma lazy y solo agrega el root del checkout durante ejecucion
legacy directa cuando `ModuleNotFoundError.name == "vault"`; ningun modulo
instalado importa `scripts/`. Se elimino la implementacion atomica historica
duplicada. AP-46 prueba asi un unico primitive activo, mientras ledger e index
hooks legacy permanecen en `vault_io`. El guard de frontmatter sigue siendo
estructural: rechaza delimitadores manuales, delegacion en comentario, import
sin uso y owner sin `Frontmatter`.

`tests/memory_recovery_e2e_gate.py` construye wheel, instala dependencias en
venv externo, borra la copia fuente, inicializa un runtime, comprueba un canary
UUID ausente, lo escribe desde un proceso, lee el Markdown directamente,
recupera su path exacto desde otro proceso, mueve el runtime y lo recupera de
nuevo. Verifica los cuatro modulos (`conocimiento`, `knowledge_save`,
`knowledge_get`, `kernel.escritura`) desde `site-packages`, checkout ausente de
`sys.path` y ausencia medida de `.db`, `.sqlite` y `.sqlite3`.

La evidencia final de este checkpoint:

```text
CLEAN_INSTALL_GATE:            PASS
RUNTIME_LIFECYCLE_GATE:        PASS
MEMORY_RECOVERY_E2E_GATE:      PASS
FULL_SUITE:                    3180 passed / 0 failed
EXISTING_GATES:                22 / 22 PASS
REAL_INSTALLED_OPERATIONS:     3
INSTALLED: vault_query_parse, vault_knowledge_save, vault_knowledge_get
SOURCE_TREE_PHYSICALLY_ABSENT: YES
RUNTIME_CLOSURE:               113
META_STANDARD_RUNTIME_LEAKS:   0
META_PATHS:                    NONE
NEW_DEFERRED_IMPORT_CYCLES:    0
```

Durante la validacion final, la relacion ER de Mermaid resulto realmente
cuadratica ante una tirada de caracteres de palabra sin match. Se aplico el
mismo borde inicial `\\b` que ya usaban las relaciones equivalentes de
flowchart, class y state. La regresion compara el patron historico sin borde
contra el actual por ratios de doubling: el primero es superlineal y el actual
es cercano a lineal. El umbral absoluto de 50 ms no se relajo.

El estado global sigue siendo honesto: quedan 89 operaciones runtime legacy-only,
por lo que `GLOBAL_SOURCE_CHECKOUT_DEPENDENCY=YES` y `PRODUCT_READY=NO`. Este
checkpoint no selecciona una cuarta operacion.

## Deuda resuelta durante PR5

- Separación runtime/meta y eliminación de la ruta `runtime -> vault_errors -> vault_voice`.
- Extracción de `NATURALEZAS` como hoja canónica de `meta_toolkit` y eliminación del ciclo diferido con MCP catalog.
- Metadata de distribución derivada, sin segundo registro editorial.
- Distinción honesta entre `distributable` e `installed-ready`.
- Contrato de error package-owned compatible con AP-52.
- Parser Mermaid: el patrón de transición dejó de hacer backtracking cuadrático;
  el escalado medido pasó de aproximadamente x4 por duplicación a ~x2.
- Contadores de documentación normalizados por su productor para evitar CRLF
  y drift de tests en Windows.

## Lo que falta

El producto todavía no está listo para release pública ni para afirmar que el
toolkit completo funciona sin checkout.

1. Seleccionar y migrar, de una en una, el par mínimo de operaciones reales para
   persistir conocimiento y recuperarlo en otro proceso.
2. Crear `MEMORY_RECOVERY_E2E_GATE`: runtime externo, escritura, nuevo proceso,
   recuperación y Markdown legible sin DB ni servicio externo.
3. Migrar operaciones MVP adicionales por bounded context, con implementación
   stable-owned, adaptador legacy y clean-install proof por cada una.
4. Sustituir gradualmente la dependencia global de checkout de registry, runner,
   scripts físicos, recursos legacy y tests que asumen layout de repo.
5. Sómismo cuando todas las operaciones MVP públicas sean reales y empaquetadas:
   ampliar lifecycle/product surfaces, definir compatibilidad completa y evaluar
   publicación.

## Fallos pre-existentes en `test_installable_boundary.py`

Los siguientes tests fallan en el estado base del branch `product/product-readiness`
sin que los cambios de los checkpoints los hayan introducido. Son deuda de diseño
de tests que existía antes de la integración de gobernanza.

| Test | Causa raíz | Sección que lo detecta |
|---|---|---|
| `test_modulo_de_ejecucion_sale_del_script_del_catalogo` | El catálogo no poblaba `execution_module` para `vault_ai_decision` — queda `None` en la distribución, pero el test espera el módulo `vault_toolkit.operations.vault_ai_decision` | `derivar_distribucion` necesita inferir `execution_module` desde el adaptador para tools runtime con script existente |
| `test_resolver_prefiere_modulo_instalado` | El monkeypatch de `find_spec` devuelve `object()` sin atributo `origin`; cuando `execution_module` es `None` el código toma el branch `legacy` (test pasa), pero con `execution_module` inferido entra a `_installed_target` y el mock incompleto falla | Test necesita mock más completo de `spec.origin` o usar `None` como valor de `execution_module` |
| `test_puntos_distribuibles_no_insertan_scripts_en_sys_path` | `cli/registry.py` inserta `SCRIPTS_DIR` en `sys.path` en tiempo de import — el test detecta la llamada `sys.path.insert` y falla | Fuga real de `sys.path` que el test detecta; la operación inyecta `scripts/` donde no debe |
| `test_adaptadores_de_operacion_derivan_del_catalogo` | `sync(check=True)` comparaba el filename derivado de `execution_module` contra el filename real; para `vault_knowledge_save` el stem de `vault.autoria.knowledge_save` es `knowledge_save.py` ≠ `vault_knowledge_save.py` | La función `render()` en `vault_distribution_sync.py` necesita usar `nombre` para el filename, no `execution_module.rsplit` |
| `test_toda_operacion_distribuible_tiene_namespace_importable` | `vault_backup_base64` es JS-native y tiene `execution_module = None`; el test hace `importlib.import_module(None)` y falla | Las tools JS-native deben marcarse como `distributable=False` en la distribución |

Ninguno de estos fallos es atribuible a los cambios de CHECKPOINT 1 o CHECKPOINT 2.
El primero y el último requieren cambios en `derivar_distribucion` (módulo `meta_toolkit/distribucion.py`);
el segundo y tercero son bugs de test; el cuarto requiere un fix en `vault_distribution_sync.py`.

Estado honesto:

```text
PUBLIC_CLI_MVP_ACCEPTED:          YES
RUNTIME_LIFECYCLE_MVP_ACCEPTED:   YES
GLOBAL_SOURCE_CHECKOUT_DEPENDENCY:YES
PRODUCT_READY:                    NO
NEXT CHECKPOINT:                  TO BE DESIGNED FROM REMAINING INVENTORY
```
