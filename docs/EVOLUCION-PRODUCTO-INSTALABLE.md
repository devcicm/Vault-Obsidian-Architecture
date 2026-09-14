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
FULL_SUITE:                    3155 passed / 0 failed
EXISTING_GATES:                22 / 22 PASS
CLEAN_INSTALL_GATE:            PASS
RUNTIME_LIFECYCLE_GATE:        PASS
SOURCE_TREE_PHYSICALLY_ABSENT: YES
CHECKOUT_IMPORT_PATH_ABSENT:   YES
REAL_INSTALLED_OPERATIONS:     1
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
5. Sólo cuando todas las operaciones MVP públicas sean reales y empaquetadas:
   ampliar lifecycle/product surfaces, definir compatibilidad completa y evaluar
   publicación.

Estado honesto:

```text
PUBLIC_CLI_MVP_ACCEPTED:          YES
RUNTIME_LIFECYCLE_MVP_ACCEPTED:   YES
GLOBAL_SOURCE_CHECKOUT_DEPENDENCY:YES
PRODUCT_READY:                    NO
NEXT CHECKPOINT:                  MEMORY_RECOVERY_E2E
```
