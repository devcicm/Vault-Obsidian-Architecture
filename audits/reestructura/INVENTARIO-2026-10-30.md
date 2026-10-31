# Inventario antes de la reestructuración — 2026-10-30

El repo queda congelado en el tag local `pre-reestructura`. Este documento es la entrada medida para decidir qué se conserva, qué se fusiona y qué sobra, y no decide nada.

Todo lo que contiene salió de leer el árbol de forma estática (AST, git log, el registro de `vault_servicio --trace`). Ninguna tool se ejecutó contra un vault. Las cifras son de esa fecha y ese commit; si se repite la medida y salen otras, valen las nuevas.

## 1. El síntoma en una tabla

| Medida | Valor |
|---|---|
| Código Python en `scripts/` | 168 ficheros, 78.228 líneas |
| Código Python en `vault/` (paquete) | 128 ficheros, 33.856 líneas |
| Tests | 552 ficheros, 75.896 líneas |
| Manifiesto | 12.262 líneas, 26 secciones `##` |
| Puertas (`vault_gate.PUERTAS`) | 27 (26 scripts, 24.454 líneas) |
| Baselines que solo encogen | 17 |
| Normas (`normas/`) | 83 |
| Commits totales / últimos 30 días | 1.345 / **1.017** |
| Commits `fix` en 30 días | 511 (50 %) |

**Lectura.** Tres de cada cuatro commits del repo son del último mes y la mitad son `fix`. Eso es un sistema que se corrige a sí mismo más deprisa de lo que se diseña.

## 2. Producto frente a autovigilancia

Las líneas por capacidad salen del registro (`vault_servicio --trace`) y cuentan solo el script de cada tool:

| Capacidad | Tools | Líneas |
|---|---|---|
| escritura → gobernanza (notas del usuario) | 88 | 39.031 |
| **gobernanza del estándar** (vigila este repo) | 29 | **21.422** |
| **consulta → contexto** (lo que el agente lee) | 10 | **2.822** |

Fuera de esas 127 quedan 44 scripts que no son tools, con 14.954 líneas, y las 24.454 líneas de las 27 puertas.

**Lectura.** El servicio declarado es dar memoria documental a un agente. La parte que entrega esa memoria, la consulta, pesa 8 veces menos que la parte que vigila que el repo cumple lo que dice de sí mismo.

## 3. Dónde se concentra el trabajo (últimos 30 días)

| Fichero | Commits que lo tocan |
|---|---|
| `AGENTS.md` | **628** de 1.017 |
| `docs/BLUEPRINT.md` | 197 |
| `vault-obsidian-architecture.md` | 114 |
| `mcp/nodejs/tools-catalog.json` y `vault/meta_toolkit/tools-catalog.json` | 103 cada uno, y son **idénticos** |
| `scripts/vault_blueprint.py` | 98 |

Por líneas cambiadas (churn), lideran artefactos generados y versionados: `audits/architecture/inventario-maestro.yaml` (73.718), `scripts/toolkit-audit-last.json` (35.472), `vault-sandbox/00_System/tool-spec.json` (19.722) y los HTML/JSON de `.archify/` (5,5 MB en git).

**Lectura.** El 62 % de los commits tocan el documento de instrucciones para agentes. La documentación se está usando como mecanismo de control. Además, los artefactos derivados versionados inflan cada diff.

## 4. Dos casas para el mismo código

- **48 scripts de `scripts/` son fachadas**: solo reexportan desde `vault/` (1.351 líneas), por ejemplo `vault_raiz.py`, `vault_regex.py`, `vault_registry.py` y `vault_norms_catalog.py`. La migración de `scripts/` a `vault/` quedó a medias y hoy conviven las dos rutas de import.
- **El catálogo MCP existe por duplicado**: dos copias byte a byte en `mcp/nodejs/` y en `vault/meta_toolkit/`.
- Hay un solo módulo sin ningún uso en código, `vault/autoria/knowledge_get.py` (28 líneas), con 3 menciones en tests. El código muerto no es el problema; lo es la duplicación de rutas.

## 5. El manifiesto

| Sección | Líneas |
|---|---|
| Changelog | **3.862** |
| Las Tools del Vault — Contrato normativo | 3.460 |
| Anti-patrones de implementación | 1.685 |
| Patrones recomendados | 1.210 |
| Las 22 secciones restantes | ~2.000 |

**Lectura.** Casi un tercio de la «fuente normativa» es historial, y otro tercio repite lo que ya dicen `scripts/README.md` y el catálogo.

## 6. Los tests

La clasificación es heurística: un fichero se asigna por las tools que nombra. Sirve para dimensionar, no para decidir test por test.

| Clase | Ficheros | Líneas |
|---|---|---|
| Nombra alguna tool de producto | 430 | 61.537 |
| Solo nombra tools que vigilan el repo | 57 | 7.048 |
| Kernel u otros, sin tool nombrada | 54 | 5.964 |
| Solo lee `.md` del repo | 11 | 1.353 |

**Lectura.** La mayor parte de la suite sí ejercita producto, y por eso es la red de seguridad de la reestructuración: **no se recorta antes de reestructurar**. Lo que se puede recortar después son los ~68 ficheros que vigilan al repo o su texto.

## 7. Deuda declarada al congelar

- Al redactar el borrador (2026-10-30), `DEUDA_DECLARADA` tenía 27 saldadas y 4 pendientes: perfiles MCP, B-04 (colector QG), D-07 (`round_id`) y A-11.
- Actualizado el 2026-10-31, antes de los tablones:
  - **A-11, perfiles MCP y D-07 están saldadas**. D-07 se saldó con `vault_ronda` en `44a60de`.
  - **B-04 sigue pendiente**: el job `qg-receipts` ya está cableado (`11f9785`), pero falta su primera corrida real en la CI, y sin push no la hay.
  - **AP-69 sin versión publicada**, pendiente desde la fase 1. La norma de higiene de tests entró en la rama sin `introduced_version` y la recibe con el bump que integre la rama.
  - Total: 31 saldadas y 2 pendientes.
- El cuadro vigente está en `vault_blueprint.DEUDA_DECLARADA`. Esta lista es la foto del momento y no se mantiene.

## 8. Preguntas que la reestructuración tiene que contestar

Están ordenadas por cuánto peso quitan:

1. **¿Una sola casa para el código?** Terminar la migración a `vault/` y borrar las 48 fachadas, con un periodo de `superseded_by`, o deshacerla.
2. **¿Qué parte de la autovigilancia es producto?** Las puertas que protegen a quien instala (instalación limpia, contrato de campos, raíz del vault) son producto. Las que vigilan cifras y texto de la documentación del propio repo son coste. Cada una de las 27 se clasifica por esa pregunta.
3. **¿El manifiesto es norma o historial?** El changelog sale a su propio fichero, y el contrato de tools se genera desde el catálogo en vez de escribirse.
4. **¿Qué se versiona?** Los artefactos derivados (`.archify/`, `inventario-maestro.yaml`, `toolkit-audit-last.json`, el catálogo duplicado) salen de git o se generan en CI.
5. **¿`AGENTS.md` instruye o controla?** Si 628 commits lo tocan, está haciendo de registro. Lo que es dato se queda en código y el documento se reduce a lo que no se deriva.
6. **¿Dónde está el servicio?** Las 10 tools de consulta son el producto declarado. La reestructuración debería partir de ellas y del contrato de nota, no de la gobernanza.
