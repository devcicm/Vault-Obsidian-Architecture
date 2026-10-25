# Matriz arquitectónica — fase 2 (L1)

**Derivado de:** `vault_arch.CONTEXTS` y `vault_arch.PRESUPUESTO_DE_CRUCES` (el registro vivo), contrastado con el snapshot de Archify.
**SHA del estado:** `e98550d33e302d93dca9327930eafbf0d64436b6` · **generado por:** `python audits/fase2/matriz_contextos.py`

> No se edita a mano: si el registro cambia, este documento se regenera.

## 1. Los diez contextos

| Contexto | Título | Puertos | Módulos | Prohíbe | Puertos publicados |
|---|---|---|---|---|---|
| `kernel` | Kernel | 4 | 23 | 1 | `atomic_write_text`, `file_lock`, `get_vault_root`, `wrap_main` |
| `autoria` | Autoría | 7 | 46 | 0 | `anexar`, `buscar`, `escribir_nota`, `fusionar`, `hablar`, `mover`, `tipo_por_carpeta` |
| `grafo` | Grafo | 4 | 15 | 0 | `construir_grafo`, `impacto`, `refresco_de_grafo`, `resolver_wikilink` |
| `gobernanza` | Gobernanza | 21 | 13 | 0 | `FUNDAMENTOS`, `NORM_CATALOG`, `auditar`, `auditar_normas`, `auditar_runtime`, `cuerpo_sin_marcadores`, `gancho_de_secretos`, `hay_hallazgos_bloqueantes`, `identidad_de_documentacion`, `lineas_de_estado`, `norma_por_codigo`, `normalizar_estado`, `penalizaciones`, `puntuar_calidad`, `referencias_de_norma`, `registro_de_ciclo_de_vida`, `transiciones_de_estado`, `validar_mermaid`, `valores_cia`, `vocabulario_de_dominio`, `vocabulario_de_estado` |
| `indices` | Índices | 12 | 7 | 0 | `coherencia_de_indices`, `enumeracion_indexable`, `indice_de_seccion`, `indice_maestro`, `ledger_de_backfill_de_tags`, `refresco_de_busqueda`, `registrar_tags`, `registro_de_nuevos_terminos`, `reindexar`, `resolucion_de_vocabulario`, `tags_de_frontmatter`, `vocabulario_de_tags` |
| `consulta` | Consulta | 7 | 11 | 3 | `cargar_contexto`, `contexto_de_sesion`, `empaquetar_contexto`, `guardar_contexto`, `limpiar_contexto`, `parsear_consulta`, `subgrafo` |
| `ciclo_de_vida` | Ciclo de vida | 3 | 10 | 0 | `CURRENT_VERSION`, `inicializar`, `migrar` |
| `durabilidad` | Durabilidad | 4 | 4 | 1 | `crear_backup`, `listar_backups`, `poner_en_cuarentena`, `restaurar` |
| `meta_toolkit` | Meta-toolkit | 6 | 38 | 1 | `GROUPS`, `NATIVE_JS_TOOLS`, `TOOLS_CATALOG`, `check_contracts`, `distribution_metadata`, `reconciled_params` |
| `cli` | CLI | 0 | 8 | 1 | — |

**Totales:** 10 contextos · 68 puertos · 23 pares de cruce presupuestados.

## 2. Presupuesto de cruces (23 pares)

Cada par tiene un dueño y una revisión; el objetivo `en_estudio` es el estado declarado: son cruces **autorizados y vigilados**, no defectos.

| Cruce | Objetivo | Dueño | Revisado | Cadencia (días) | Por qué |
|---|---|---|---|---|---|
| `autoria` → `gobernanza` | permanente | autoria | 2026-08-14 | 180 | Validar mermaid al escribir y registrar el cambio: la escritura no puede publicar una nota que el propio estándar rechaz |
| `autoria` → `grafo` | permanente | arquitectura | 2026-08-14 | 180 | Adaptador de DI: cablear el dominio de otro contexto es su oficio. Se cuenta igual — no contarlo dejaría la capa de DI c |
| `autoria` → `indices` | en_estudio | indices | 2026-08-14 | 180 | Reindexado tras escritura. |
| `autoria` → `meta_toolkit` | en_estudio | autoria | 2026-08-14 | 180 | `vault_voice` -> `vault_mcp_catalog`: la voz consulta el catálogo. |
| `ciclo_de_vida` → `autoria` | permanente | ciclo_de_vida | 2026-08-14 | 180 | Onboarding puebla el vault escribiendo notas: pasa por el write path único (AP-46) en vez de escribir por su cuenta. |
| `ciclo_de_vida` → `gobernanza` | permanente | ciclo_de_vida | 2026-08-14 | 180 | Sanación y onboarding aplican las normas al vault del usuario. Sin este cruce las doce fases tendrían que reimplementar  |
| `ciclo_de_vida` → `grafo` | permanente | ciclo_de_vida | 2026-08-14 | 180 | Propagar un cambio exige saber a qué alcanza, y el alcance lo mide el grafo. Reimplementarlo aquí sería AP-57. |
| `ciclo_de_vida` → `indices` | en_estudio | indices | 2026-08-14 | 180 | Reindexado tras escritura. |
| `ciclo_de_vida` → `meta_toolkit` | en_estudio | ciclo_de_vida | 2026-08-14 | 180 | `vault_standard_upgrade` -> `vault_mcp_catalog` para sincronizar el catálogo al subir de versión. |
| `cli` → `meta_toolkit` | permanente | cli | 2026-08-14 | 180 | `cli/registry.py` lee `TOOLS_CATALOG` y `NATIVE_JS_TOOLS` para saber qué tools existen y cuáles viven en el `.mjs`. Un r |
| `consulta` → `autoria` | permanente | consulta | 2026-08-14 | 180 | El paquete de contexto busca notas: la búsqueda tiene dueño en Autoría. |
| `consulta` → `ciclo_de_vida` | permanente | arquitectura | 2026-08-14 | 180 | Adaptador de DI: cablear el dominio de otro contexto es su oficio. Se cuenta igual — no contarlo dejaría la capa de DI c |
| `consulta` → `grafo` | permanente | consulta | 2026-08-14 | 180 | El subgrafo lee el grafo. Es el caso legítimo que el docstring de `cruces()` ya nombra. |
| `gobernanza` → `autoria` | a_eliminar | gobernanza | 2026-08-14 | 180 | `vault_norms_engine` -> `vault_voice`: presentación colgada del motor, se conserva solo en la fachada estándar para ejec |
| `gobernanza` → `indices` | en_estudio | indices | 2026-08-14 | 180 | Reindexado tras escritura. |
| `gobernanza` → `meta_toolkit` | a_eliminar | gobernanza | 2026-08-14 | 180 | `vault_norms_engine` importa `vault_smoke` y `vault_mcp_catalog` en diferido para auditar el catálogo. Va al revés: el m |
| `grafo` → `autoria` | permanente | grafo | 2026-08-14 | 180 | Etiquetar código escribe la nota por el write path único (AP-46). |
| `grafo` → `gobernanza` | permanente | grafo | 2026-08-14 | 180 | Adaptador del contexto Grafo hacia el dominio de Gobernanza. |
| `indices` → `grafo` | permanente | arquitectura | 2026-08-14 | 180 | Adaptador de DI: cablear el dominio de otro contexto es su oficio. Se cuenta igual — no contarlo dejaría la capa de DI c |
| `kernel` → `autoria` | permanente | kernel | 2026-08-14 | 180 | El inyector común de envelopes llama al puerto `hablar` para que el recordatorio llegue a todas las tools. El servicio d |
| `meta_toolkit` → `ciclo_de_vida` | permanente | meta_toolkit | 2026-08-14 | 180 | El checker del changelog necesita el camino de versión que define `vault_standard_upgrade`. Duplicarlo sería AP-05 sobre |
| `meta_toolkit` → `consulta` | permanente | meta_toolkit | 2026-08-14 | 180 | El servidor MCP expone las tools de consulta: exponer es su oficio. |
| `meta_toolkit` → `gobernanza` | permanente | meta_toolkit | 2026-08-14 | 180 | El meta-toolkit audita que este repo cumple lo que publica, y para eso tiene que leer las normas y el audit. Es la direc |

## 3. Reconciliación con el snapshot de Archify

**Pares de contexto:** snapshot 23 · registro 23 · coincidentes **23** · solo en snapshot 0 · solo en registro 0.

**Dependencias (nivel de fichero):** 37 dependencias colapsan a 23 pares de contexto; **23** de esos pares siguen vigentes (los vivos son 23).

**Fichas de los pares:** 23 comparadas, 0 con diferencias de metadatos.

**Accesos fuera de puerto del snapshot:**

| Acceso | Estado | Nota |
|---|---|---|
| `vault_norms_engine -> vault_mcp_catalog.check_params` | VIGENTE (deuda vigilada) | sigue fuera de puerto: no se ha resuelto |
| `vault_norms_engine -> vault_smoke.SIN_SMOKE` | VIGENTE (deuda vigilada) | sigue fuera de puerto: no se ha resuelto |
| `vault_norms_engine -> vault_smoke.invocation` | VIGENTE (deuda vigilada) | sigue fuera de puerto: no se ha resuelto |
| `vault_norms_engine -> vault_smoke.load_baseline` | VIGENTE (deuda vigilada) | sigue fuera de puerto: no se ha resuelto |
| `vault_norms_engine -> vault_voice.coverage` | VIGENTE (deuda vigilada) | sigue fuera de puerto: no se ha resuelto |
| `vault_sanacion -> vault_reindex.notas_indexables` | RESUELTO en ronda 1 | f6a5387 (Q03): puerto enumeracion_indexable |
| `vault_write -> vault_tags.apply_vocabulary` | RESUELTO en ronda 1 | 4fededd (Q01): puerto resolucion_de_vocabulario |
| `vault_write -> vault_tags.record_new_tags` | RESUELTO en ronda 1 | 4fededd (Q01): puerto registro_de_nuevos_terminos |

**Anclas del puente:** snapshot ['vault_grafo_import', 'vault_release'] · registro ['vault_grafo_import', 'vault_release'] · coinciden: **True** · motivos idénticos: {'vault_grafo_import': True, 'vault_release': True}

**Contextos:**

| Contexto | Estado | Puertos (snapshot→registro) | Módulos (snapshot→registro) |
|---|---|---|---|
| `kernel` | VIGENTE | 4→4 | 23→23 |
| `autoria` | VIGENTE | 7→7 | 46→46 |
| `grafo` | VIGENTE | 4→4 | 15→15 |
| `gobernanza` | VIGENTE | 21→21 | 13→13 |
| `indices` | AMPLIADO (puertos publicados en el registro) | 9→12 | 7→7 |
| `consulta` | VIGENTE | 7→7 | 11→11 |
| `ciclo_de_vida` | VIGENTE | 3→3 | 10→10 |
| `durabilidad` | VIGENTE | 4→4 | 4→4 |
| `meta_toolkit` | VIGENTE | 6→6 | 37→38 |
| `cli` | VIGENTE | 0→0 | 8→8 |

## 4. Invariantes del registro en este SHA

| Invariante | Valor |
|---|---|
| contextos | 10 |
| puertos_totales | 68 |
| presupuesto_cruces | 23 |
| off_port_total | 5 |
| off_port_baseline | 5 |

