# Auditoría Teseo — rama `reestructura/teseo` (2026-10-31)

Protocolo: `refactor-codebase` v2.1. Fases 0–2: reconocimiento, deconstrucción y auditoría.
Estado de partida: `44a60de` sobre `pre-reestructura`. Golden master en `golden/`,
comparador en `paridad.py`.

**Qué se considera contrato C(P) aquí:**
- el envelope JSON de cada tool, sacando sus rutas volátiles;
- la línea de comando `scripts/<x>.py` que lanzan MCP, CI y los consumidores;
- los nombres públicos de cada módulo importable;
- `tools-catalog.json`, `tool-spec.json` y `schemas/`;
- `vault product --help`;
- el resultado de la suite.

La estructura interna de `scripts/` y de `vault/` **no** es contrato. Los nombres que
importan los consumidores sí lo son, y por eso se conservan con alias `sys.modules`
(no-derogación).

## Resumen por dominio

| Dominio | Revisado | Confirmados | Candidatos | Limpio |
|---|---|---|---|---|
| Núcleo (N) | kernel, fronteras entre contextos, estado global | 5 | 2 | — |
| DRY (D) | catálogos, clones, fachadas | 3 (H-01 reclasificado NOT_APPLICABLE en A-1) | 1 | — |
| FE | 5 HTML y 2 JS sin lógica de producto | 0 | 0 | sí |
| BE | `mcp/nodejs/vault-mcp-server.mjs` | 0 | 1 | — |
| ALG | suite y puertas (atendido en la fase 1) | 0 | 0 | sí, tras la fase 1 |
| RES | escrituras atómicas, locks y subprocesos (AP-36 y AP-68 ya tienen guard) | 0 | 1 | — |
| OBJ | inyección de la raíz y singletons | 2 | 0 | — |

## Hallazgos confirmados

| ID | Criterio | Ubicación | Evidencia | Clase | Sev. | Riesgo | P |
|---|---|---|---|---|---|---|---|
| H-01 | D-01 | `mcp/nodejs/tools-catalog.json` y `vault/meta_toolkit/tools-catalog.json` | El sha256 es idéntico byte a byte. Son dos copias versionadas del mismo conocimiento y `--sync` escribe las dos. **Revisado al ejecutar A-1:** no son dos conocimientos. Las dos son proyecciones de `TOOLS_CATALOG`, cada una con un lector en un paquete distinto de la wheel (`vault.meta_toolkit.catalogo_producto` por `importlib.resources`; `vault-mcp-server.mjs` por `join(__dirname, …)`, que también se sirve desde el checkout con `vault mcp-path`). `check_sync` ya exige que sean iguales. Quitar una cambia el contenido de la wheel, y eso es contrato. | ~~COMPATIBLE_EVOLUTION~~ → NOT_APPLICABLE (duplicación accidental de texto y no de conocimiento, regla 8) | media | bajo | — |
| H-02 | N-06 / ciclo | `scripts/vault_io.py` ↔ `vault_section_index.py`, `vault_tags.py` | `ciclos-baseline` tiene 3 sitios. Hay imports diferidos en `vault_io.py:601, 746, 758, 877, 1086`, y los dos módulos importan `vault_io` arriba. | ~~PURE_REFACTOR~~ → CANDIDATE hasta C-2: sin raíz de composición, la inversión cambia C(P) o esconde el ciclo (ver PLAN, «Obstáculos del bloque A») | alta | medio | P1 |
| H-03 | N-06 | `scripts/vault_errors.py:51` → `vault.autoria.voz` | Es el único cruce del núcleo hacia un contexto de dominio. `_inject_voice` (línea 294) llama a la voz para cada error. | ~~PURE_REFACTOR~~ → CANDIDATE hasta C-2: sin raíz de composición, la inversión cambia C(P) o esconde el ciclo (ver PLAN, «Obstáculos del bloque A») | alta | medio | P1 |
| H-04 | N-07 | `vault/kernel/` (13.579 LOC) | El núcleo guarda catálogos de dominio: `norms_catalog` 898, `fundamentals_catalog` 703, `registry` 1.307, `contrato_nota` 493, `mermaid_reglas` 442, `vocabulario` 306, `audit_catalog` 206 y `proyectos` 509. Ninguno es infraestructura. `kernel-baseline` tiene 4 sitios (`kernel_impuro::vault_io` y 3 inestables). | PURE_REFACTOR (mover y dejar alias). **Al ejecutarlo:** son *shared kernel* (de 3 a 37 consumidores en 3–7 contextos), así que van a un subpaquete `vault/kernel/normativa/` y no a un contexto aparte, que sumaría 6 cruces. Ver PLAN B-1. **Al medir B-2 (sobre `4d9d031`):** `registry` tiene 47 consumidores en 9 contextos y `proyectos` 21 en 5, incluido el propio núcleo (`vault_errors`). Llevarlos a autoria, su mayor consumidor, estrenaría tres pares fuera de `PRESUPUESTO_DE_CRUCES` (gobernanza, meta_toolkit e indices → autoria) y ataría `vault_errors` al cruce kernel→autoria que C-1 quiere quitar. B-2 queda NOT_APPLICABLE; meter `registry` en `normativa` es CANDIDATE (no es hoja: importa `vault_grafo_import`) | alta | medio | P2 |
| H-05 | N-07 | `vault/meta_toolkit/` | Mezcla guards del propio repo (`carriles`, `perfil_suite`, `test_scope`, `firma_sitio`, `spec_catalog_check`) con piezas del producto instalado (`mcp`, `catalogo_producto`, `resolucion_producto`, `distribucion`). La wheel arrastra la gobernanza del estándar. | COMPATIBLE_EVOLUTION | media | medio | P2 |
| H-06 | N-07 (módulo dios) | `vault_mcp_catalog` 5.981 líneas (4.710 de datos), `vault_arch` 3.196, `vault_audit` 3.175, `vault_onboard` 3.184, `vault_blueprint` 2.169 (1.408 de datos), `vault_write` 1.723 | Cada uno junta un catálogo de datos, el motor y la CLI en un solo fichero. | PURE_REFACTOR (partir en catálogo, motor y CLI con alias) | media | medio | P3 |
| H-07 | D-02 (capas de fachada) | `vault_toolkit/operations/` (97 adaptadores generados), 48 scripts de `scripts/` que solo reexportan `vault/` | Para llegar a una función se cruzan tres capas: operations, alias de scripts y `vault/`. Las dos primeras no tienen lógica. | CANDIDATE → ver C-03 | — | — | — |
| H-08 | D-04 | `vault/install.py::_run` y `vault/uninstall.py::_run` | `clones-baseline` tiene 1 sitio. Es el mismo cuerpo de lanzador. | PURE_REFACTOR | baja | bajo | P3 |
| H-09 | N-09 / OBJ-03 | `vault/kernel/raiz.py:460` `_reanclar_constantes` | Reescribe constantes `Path` de módulo en `sys.modules` cada vez que cambia la raíz. Su docstring dice que 89 de 98 módulos derivan rutas al importarse. Hay 151 llamadas a `get_vault_root()` en scripts/vault/cli. | COMPATIBLE_EVOLUTION (el código nuevo recibe `VaultContext` y el resto se queda como está) | alta | alto | P2 |
| H-10 | OBJ-01 | Las tools que construyen su raíz, su `ERROR_CATALOG` y su escritor en el cuerpo de `main()` | Es la consecuencia de H-09: sin un parámetro de contexto no se pueden ejecutar en proceso, y por eso los tests las lanzan por subproceso (el 55 % del tiempo de la suite). | COMPATIBLE_EVOLUTION | media | medio | P2 |
| H-11 | N-06 (ciclo de contexto) | `PRESUPUESTO_DE_CRUCES`: gobernanza→meta_toolkit | El par está declarado `a_eliminar` y sigue vivo. | PURE_REFACTOR | media | bajo | P2 |
| H-12 | D-03 (cifra a mano) | `scripts/README.md`, «98 de las 129» tools expuestas por MCP | `vault_doc_counts` no mide esa cifra (AP-47). Ver B-04. | FIX → BUGS | — | — | — |

## Candidatos (no entran al plan de ejecución sin más evidencia)

| ID | Criterio | Ubicación | Por qué no es CONFIRMED |
|---|---|---|---|
| C-01 | N-06 | Pares `en_estudio`: ciclo_de_vida/autoria/gobernanza→indices, ciclo_de_vida→meta_toolkit, autoria→meta_toolkit (`vault_voice`→`vault_mcp_catalog`) | Hay que medir si cada cruce lee un recurso (AP-62) o llama a un motor. Sin eso no se sabe hacia dónde se invierte. |
| C-02 | N-06 | autoria↔grafo, declarado permanente en las dos direcciones | La declaración tiene motivo escrito. Romperlo es una decisión de diseño, no de refactor. |
| C-03 | D-02 | Retirar una de las tres capas de fachada | `vault_toolkit/operations` es superficie que importa la wheel instalada, y los alias de `scripts/` son las rutas que lanzan MCP y CI. Cualquiera de las dos puede ser contrato de un consumidor ajeno (regla 7) y no se ha medido. | **Medido el 2026-11-01 (Fase 1.5, ver `audits/archivo/reestructura-2026-11-02/MEDICION-FACHADAS.md`): las tres capas tienen consumidor vivo y las tres son contrato.** `operations/` (97) viaja en la wheel y es la ruta de `vault run` instalado; `clean_install_gate` ejecuta cada adaptador `--help`. `scripts/` es una proyección, no una copia: `package-dir` mapea `vault_toolkit._impl` ⇄ `scripts/` (ADR-0002), el servidor MCP lanza `python <script>` con CWD `scripts/`, y los ejemplos de `scripts/README.md` y `AGENTS.md` lo publican como vía de checkout. Retirar cualquiera exige versión de la superficie (tool-spec, catálogo, docs prometidas) y no es PURE_REFACTOR. **Queda CANDIDATE con la medición al lado; el ahorro real se va por otras vías** (C-2 en proceso, derivados, jubilación del andamio) |
| C-04 | D-01 | `scripts/` (76,5 k LOC) frente a `vault/` (33,9 k): la lógica está en la capa de entrada | Moverla es PURE_REFACTOR solo si el alias conserva **todos** los nombres públicos, incluidos los privados que importan los tests. El golden de `superficie` los fija, pero el coste por módulo no está medido. |
| C-05 | BE | `vault-mcp-server.mjs` monolítico | El servidor está cubierto por `node --test` y por `paridad_cli_mcp`. Partirlo no mejora ninguna métrica medida hoy. |
| C-06 | RES | Subprocesos de las tools con `timeout` dispares | AP-68 ya centraliza git, pero no python. Hace falta inventariar antes de clasificar. |
| C-07 | N-07 | `vault/kernel/errores.py` 2.166 LOC, `baseline.py` 545 | `errores` es núcleo legítimo, pero arrastra el catálogo entero. `baseline` es infraestructura de la gobernanza del estándar y no del producto. Hay que decidir el destino junto con H-05. **Decidido en B-3 (sobre `be613d2`):** `baseline` se queda en el núcleo y en la wheel, porque la importa `vault.gobernanza.fuente_unica`, que es la tool de producto `vault_fuente_unica`. Infraestructura compartida, no gobernanza. |

## Zonas limpias

- **FE:** no hay lógica de producto en HTML ni en JS fuera del servidor MCP.
- **RES, escrituras:** AP-36 tiene guard y cubre backups, traces y locks dentro del vault. No se encontraron escrituras fuera.
- **Git:** AP-68 tiene guard sin baseline, y hoy no hay ningún sitio fuera del dueño.
- **`excepcion-declarada`:** baseline en 0.
- **Suite y puertas (ALG):** la fase 1 dejó el carril `dev` con selección por impacto y las puertas `rapida` en unos 80 s. Ya no es un hallazgo abierto: la medida está en `vault_metricas`.

## Dependencias de orden

1. ~~H-02 y H-03 (ciclos) van antes que H-04 (mover catálogos). Si no, el movimiento arrastra el ciclo al contexto nuevo.~~ **Corregido al ejecutar el bloque A:** ninguno de los módulos de H-04 importa los extremos de esos ciclos. H-02 y H-03 van **después** de H-10, porque necesitan la raíz de composición que da `VaultContext`.
2. H-04 va antes que H-05. La separación del meta-toolkit decide dónde vive `baseline.py` (C-07).
3. H-09 y H-10 van antes que la migración de tests a ejecución en proceso. Sin contexto inyectable, la migración vuelve a monkeypatchear la raíz.
4. H-06 va el último entre los PURE_REFACTOR: los dioses dependen de todo lo anterior.
