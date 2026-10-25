# L4 — Auditoría documental, de seguridad y de deuda histórica (2026-10-25)

**Estado:** clasificación con evidencia mecánica. Los valores que no se midieron
quedan marcados `NO_VERIFICADO` — sin inventarlos.

## L4-A — Coherencia documental (DOC-0001 … DOC-0008)

Inventario completo en `audits/fase2/inventario-documental.yaml`. Resumen:

| Documento | Clasificación | Motivo corto |
|---|---|---|
| README (Quick Start) | INCOMPLETO (DOC-0001) | Mezcla la superficie del checkout (`python scripts/…`) con la del producto instalado (`vault …`); un consumidor de la wheel no tiene `scripts/` |
| docs/ARQUITECTURA.md | VIGENTE (DOC-0002) | Byte a byte igual al derivado `arch.blueprint()`; un guard lo vigila |
| docs/PUERTAS.md | VIGENTE (DOC-0003) | 26 puertas en el registro, 26 en el documento (derivado) |
| docs/INSTALACION-LIMPIA.md | VIGENTE (DOC-0004) | Sus comandos existen y el recorrido L3 los ejecutó de verdad |
| docs/sdd/gaps.md | OBSOLETO como inventario (DOC-0005) | Registro histórico de v36.0 (85+ hallazgos de junio); reconciliado en L4-C |
| PRD CLI / PRD MCP / runtime-contract | NO_VERIFICADO (DOC-0006) | No se contrastó afirmación por afirmación (pendiente de un lote de L4 ampliado) |
| .archify/ | VIGENTE como evidencia auxiliar (DOC-0007) | Reconciliado en L1; no es fuente de verdad |
| docs/adr/ | VIGENTE (DOC-0008) | ADR-0002 verificado en el empaquetado (package-dir del wheel) |

## L4-B — Seguridad (superficies reales, con lo medido)

### Sistema de archivos (contención)
- **Control presente y usado:** `assert_within_vault` aparece en **103 ficheros**.
- **Medido en el recorrido MVP (L3):** un `--folder "../"` por CLI y por MCP es
  **rechazado**; no se escribió nada fuera del runtime (paso 14 del recorrido).
- **Hallazgo nuevo (TD-0008, P1):** `vault_init --clean` borra el contenido del
  runtime con `shutil.rmtree` **sin copia previa** — código observado en
  `scripts/vault_init.py` («Step 0: --clean wipes existing content …
  shutil.rmtree(entry) … entry.unlink()»). Es el gap histórico D3 de v36.0,
  todavía vigente en v41.23. Mitigación existente: exige flag explícito y
  documenta que es destructivo. Riesgo: una invocación por error destruye el
  runtime sin recuperación (el `.history/` se borra también).
  **Recomendación:** copia previa automática (o mover a cuarentena) antes del
  wipe, y prueba negativa que demuestre la recuperación.
- **PENDIENTE (no verificado):** symlinks y TOCTOU en las rutas de escritura.

### Servidor MCP
- **OBSERVADO (L3):** exige `initialize` antes de `tools/call` — sin sesión
  responde con el error JSON-RPC `-32002` (medido). Con sesión, un error de
  ejecución de tool llega como resultado con `isError` y envelope con
  `error_code`, no como error de transporte (medido).
- **OBSERVADO:** expone **97 de 126** tools del catálogo y **cero** de
  gobernanza: el producto instalado no puede escribir baselines ni tocar los
  registros del repo por MCP.
- **OBSERVADO:** sus trazas de runtime (`.mcp-trace-log.*`) **no** viajan en la
  wheel (TD-0002, medido sobre el artefacto).
- **PENDIENTE:** límites de proceso (tamaño de mensaje, tiempo por tool),
  autorización por cliente y validación de `params` contra el `inputSchema`
  publicado (el catálogo lo declara; la verificación de que el servidor lo
  aplica no está medida).

### CLI
- **OBSERVADO:** `vault run <operación>` solo alcanza las **96 operaciones** de
  `vault_toolkit/operations/` — **cero tools de gobernanza** entre ellas.
- **OBSERVADO:** `cli/safety.py` existe (guards anti-poison, `scan_content`) y
  el recorrido L3 mostró el gate de contenido (AP-11) rechazando un cuerpo corto.
- **PENDIENTE:** inventario de operaciones destructivas accesibles por `vault run`
  y de sus confirmaciones.

### Dependencias y distribución
- **OBSERVADO:** la wheel declara `PyYAML>=6.0` como única dependencia de
  runtime (medido en los METADATA del artefacto) y `Requires-Python: >=3.9`.
- **OBSERVADO:** 705 miembros, sin trazas de runtime (TD-0002).
- **PENDIENTE (QG-04):** auditoría de vulnerabilidades de dependencias
  (`pip-audit` no está disponible en este entorno) y cadena de suministro
  del sdist (no se construyó).
- **OBSERVADO (TD-0001):** el job de CI de la wheel no instalaba el artefacto:
  corregido y verificado en local; la confirmación de CI sigue pendiente.

### Persistencia
- **OBSERVADO (L3, memory_e2e):** escritura atómica instalada
  (`atomic_primitive_origin` en `site-packages`), canario escrito y recuperado
  tras mover el runtime, árbol fuente físicamente ausente, import del checkout
  ausente y **sin ficheros de base de datos** en el runtime.
- **OBSERVADO (TD-0008):** el wipe de `--clean` no tiene copia previa.

## L4-C — Reconciliación histórica (gaps.md de v36.0 → v41.23)

| ID histórico | Descripción | Estado hoy | Evidencia |
|---|---|---|---|
| H1 | No `vault_undo` | **CORREGIDA** | `scripts/vault_undo.py` + operación `vault_undo` |
| H2 | `--dry-run` solo en 12 de 94 | **PARCIAL** | 14 de 167 scripts hoy |
| D3 | `--clean` sin backup | **VIGENTE** | TD-0008 (nuevo) |
| K3 | 25+ `slugify()` duplicados | **PARCIAL** | 21 hoy |
| K4 | 15+ `utcnow()` duplicados | **PARCIAL** | 14 hoy |
| J1/J3/D2/G1/G2/D4/D5/D7/E1/E2/G3/G4/H3/H4/H6/J5 | resto (85+ en total) | NO_VERIFICADO en este lote | queda para un lote de reconciliación ampliada |

**No se crean duplicados:** los que siguen vigentes entran al
`inventario-deuda.yaml` referenciando su ID histórico.

## L4-D — Nueva deuda técnica (descubrimiento de este lote)

| ID | Sev | Hallazgo | Evidencia |
|---|---|---|---|
| TD-0008 | P1 | `vault_init --clean` destruye el runtime sin copia previa (gap D3 de v36.0, vigente) | código observado; reconciliation arriba |
| TD-0009 | P2 | El Quick Start del README mezcla las dos superficies (checkout y producto instalado) sin decir cuál asume | DOC-0001 |
| TD-0010 | P2 | Las baselines de estructura están por encima de su objetivo declarado con plazo activo | ya registrado como TD-0006 (se confirma con la medición de L4) |
| TD-0011 | P3 | 21 `slugify` y 14 `utcnow` duplicados (K3/K4 históricos, mejorados pero no consolidados) | medido en L4 |

## Hallazgos descartados (y por qué)

1. **«docs/ARQUITECTURA.md está desfasado»** — descartado: el documento es
   byte a byte el derivado de `arch.blueprint()`; mi primera comparación usó
   otro derivado (error del instrumento, corregido).
2. **«la wheel lleva trazas de runtime»** — descartado por medición (TD-0002,
   falso positivo).
3. **«el catálogo MCP expone tools de gobernanza»** — descartado: 0 de 97.
4. **«hay credenciales publicadas en las evidencias»** — descartado: 0 en
   ninguna rama publicada (H-L3-04).