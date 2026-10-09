# Plano de construcción del estándar

> **Documento derivado. No se edita a mano.**
> Se regenera con `python scripts/vault_blueprint.py --blueprint` y una puerta
> falla si diverge de los registros (`--check --strict`). El papel manda porque
> lo escribe el código: si alguna cifra de aquí se teclea, deja de ser un plano y
> pasa a ser una opinión con formato de tabla.

La jerarquía va de arriba abajo: el servicio justifica las capacidades, las
capacidades agrupan las tools, los contextos dicen dónde vive cada una y por dónde
se habla con ella, las normas dicen qué no puede pasar y las puertas lo impiden.
Cada capa nombra el registro del que sale — ninguna capa es prosa.

## Capa 1 — Servicio de negocio

*Registro: `vault_servicio.SERVICIO`*

**Memoria documental persistente y gobernada para agentes LLM**

Dar a un agente LLM memoria documental persistente, auditable y gobernada sobre markdown plano: lo que el agente escribe queda normalizado, versionado y trazable, y lo que necesita recordar se le devuelve como contexto acotado.

Restricciones que son decisión de producto, no limitación pendiente:

| Restricción | Por qué | Declarada en |
|---|---|---|
| Sin base de datos, sin embeddings y sin servicio externo. | Es una decisión de producto, no una limitación pendiente de resolver: el vault debe seguir siendo legible y editable por una persona con un editor de texto, y sobrevivir a que este toolkit desaparezca. | `AGENTS.md — Los dos ejes; vault_arch.CONTEXTS['consulta']['prohibe']` |
| Solo stdlib + PyYAML. | Un agente instala el toolkit en el repo del usuario; cada dependencia es una razón para que no lo haga. | `AGENTS.md — Qué contiene` |
| Nada se elimina; lo reemplazado se anota `superseded_by:`. | Los vaults consumidores leen contratos de este repo. Un campo que evapora rompe en silencio a quien lo leía. | `AGENTS.md — regla 2; manifiesto § Política de no-derogación` |

## Capa 2 — Capacidades → grupos

*Registro: `vault_servicio.CAPACIDADES` + `vault_mcp_catalog.mapa_de_grupos()`*

| Capacidad | Resultado | Grupos | Tools |
|---|---|---|---|
| **Escritura → gobernanza** (`escritura_a_gobernanza`) | Lo que el agente captura queda escrito una sola vez, normalizado contra las normas, versionado y auditable después. | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 27, 28, 29, 30, 31, 32, 33, 36, 37 | 88 |
| **Consulta → contexto** (`consulta_a_contexto`) | Una pregunta del agente se convierte en un paquete de contexto acotado y presupuestado, recorriendo el grafo del vault sin índice externo. | 26, 34 | 10 |
| **Gobernanza del estándar** (`gobernanza_del_estandar`) | El estándar cumple lo que publica: registro canónico primero, doc derivada, guard que falla si divergen. Ninguna de estas tools toca las notas de un usuario. | 35 | 25 |

- **`consulta_a_contexto`** — El grupo 26 (Tokens) cae en el rango 1–33 que `AGENTS.md` atribuye al primer eje, pero sus tres tools viven en el contexto `consulta` y existen para que el paquete quepa en la ventana. El rango es cronológico, no clasificatorio.
- **`gobernanza_del_estandar`** — Tercera capacidad que `AGENTS.md` no nombraba. Existía desde que se escribió la primera puerta; declararla es lo que impide que sus tools se cuenten como si sirvieran a la memoria del agente.

Guard: todo grupo del catálogo pertenece a exactamente una capacidad y toda
capacidad tiene al menos una tool viva (`vault_servicio.py --check --strict`).

## Capa 3 — Contextos acotados → puertos

*Registro: `vault_arch.CONTEXTS`. El detalle de puertos y cruces vive en
[`docs/ARQUITECTURA.md`](./ARQUITECTURA.md), que no se absorbe aquí: son dos
documentos con dos sujetos, y fundirlos habría hecho un solo documento que nadie
regenera.*

| Contexto | Puertos | Módulos | Prohíbe |
|---|---|---|---|
| **Kernel** (`kernel`) | 4 | 23 | depender de cualquier contexto de dominio |
| **Autoría** (`autoria`) | 7 | 46 | — |
| **Grafo** (`grafo`) | 4 | 15 | — |
| **Gobernanza** (`gobernanza`) | 21 | 13 | — |
| **Índices** (`indices`) | 9 | 7 | — |
| **Consulta** (`consulta`) | 7 | 11 | base de datos; embeddings; servicio externo |
| **Ciclo de vida** (`ciclo_de_vida`) | 3 | 10 | — |
| **Durabilidad** (`durabilidad`) | 4 | 4 | escribir fuera de la raíz del vault (AP-36) |
| **Meta-toolkit** (`meta_toolkit`) | 6 | 32 | escribir en una sección de contenido: sus artefactos derivados viven en 00_System/ |
| **CLI** (`cli`) | 0 | 8 | decidir: traduce argumentos a llamadas y envelopes a salida; la decisión vive en la tool |

## Capa 4 — Normas → puertas → tests

*Registros: `vault_norms.NORM_CATALOG` + `vault_gate.PUERTAS` + `tests/`*

70 de 79 normas tienen puerta o test que las nombre.
**Es la única capa con baseline**, y por un motivo concreto: las demás se midieron
en cero el día que se declararon porque sus datos ya existían y solo faltaba
atarlos. Ésta no. Exigir cero aquí el primer día habría hecho nacer la puerta en
rojo, y una puerta en rojo se desactiva.

| Norma | Enforcement | Puertas | Tests |
|---|---|---|---|
| **AP-01** — Documentación alucinada | audit | — | `test_ap01_codigo_inexistente.py`, `test_ap46_editores.py`, `test_norms_coherence.py`, `test_skills_catalogo.py`, `test_skills_contract.py` |
| **AP-02** — Proliferación de versiones del mismo documento | audit | — | `test_ap02_versiones_misma_carpeta.py`, `test_skills_contract.py` |
| **AP-03** — Stubs sin política de expansión | audit | — | `test_normas_de_audit_ejercitadas.py` |
| **AP-04** — Features aspiracionales documentadas como implementadas | audit | — | — |
| **AP-05** — Múltiples fuentes de verdad para el mismo dato | audit | `fuente_unica` | `test_ap05_fuente_unica.py`, `test_ap46_editores.py`, `test_blueprint.py`, `test_js_native_frontera.py`, `test_norms_coherence.py` |
| **AP-06** — Templates sin instancias reales | audit | `framework` | — |
| **AP-07** — ADRs incompletos | audit | `framework` | `test_ap07_criterio_adr.py`, `test_ap64_responsable.py`, `test_vault_norms_audit.py` |
| **AP-08** — Documentación anclada a versiones obsoletas | audit | — | `test_ap08_vigencia.py` |
| **AP-09** — Runbooks fuera de estructura | audit | `framework` | `test_vault_norms_audit.py` |
| **AP-10** — Migración sin plan de rollback | audit | `framework` | — |
| **AP-11** — Skeleton files — frontmatter válido, contenido vacío | guard | — | `test_envelope_forma.py`, `test_voice.py` |
| **AP-12** — Frontmatter inconsistente entre notas del mismo tipo | audit | — | — |
| **AP-13** — Timestamps inválidos o incompletos en frontmatter | audit | — | `test_meta_contrato.py` |
| **AP-14** — Wiki-links rotos o vacíos | guard+audit | — | `test_audit_acciones_de_movimiento.py`, `test_normas_enlaces_sin_solape.py`, `test_norms_coherence.py` |
| **AP-15** — Archivos externos depositados en la raíz del vault | guard+audit | `framework` | `test_normas_sin_registro_a_mano.py`, `test_vault_norms_audit.py` |
| **AP-16** — Sin identificador de agente en frontmatter | audit | — | `test_ap64_responsable.py`, `test_context_memory.py` |
| **AP-17** — Canonical-shadow duplication | audit | — | `test_blueprint.py`, `test_normas_de_audit_ejercitadas.py` |
| **AP-18** — Cross-folder content duplication | audit | — | — |
| **AP-19** — Shadow indexing | audit | `framework` | — |
| **AP-20** — Deceptive skeleton (empty-list) | guard | — | `test_ap20_esqueleto_de_lista.py` |
| **AP-21** — Path-anchored wiki-links | guard+audit | — | `test_ap21_dentro_de_fence.py`, `test_ap21_ruta_necesaria.py`, `test_normas_enlaces_sin_solape.py`, `test_vault_regex.py` |
| **AP-22** — Wiki-link vacío — [[]] sin destino | guard+audit | — | `test_normas_enlaces_sin_solape.py`, `test_norms_coherence.py`, `test_vault_regex.py` |
| **PAT-1** — Canonical source anchoring | recommended | — | `test_norms_coherence.py` |
| **PAT-2** — Stub enrichment gradient | recommended | — | — |
| **PAT-3** — Duplicate chain resolution | recommended | — | — |
| **PAT-4** — Phased audit execution | recommended | — | — |
| **PAT-5** — Frontmatter as provenance chain | recommended | — | `test_context_memory.py` |
| **AP-23** — Note complexity ceiling — nota demasiado larga | audit | `framework` | — |
| **AP-24** — Bracket imbalance — corchetes sin pareja, anidados o invertidos | guard+audit | — | `test_norms_coherence.py`, `test_vault_norms.py` |
| **AP-25** — Mermaid diagram syntax errors — nodos/tipos no definidos | audit | — | `test_skills_catalogo.py`, `test_vault_norms.py` |
| **AP-26** — Missing tags — nota de contenido sin tags | guard+audit | — | `test_context_memory.py` |
| **AP-27** — Missing type field — nota sin tipo declarado | guard+audit | — | — |
| **AP-28** — Missing frontmatter — nota sin bloque YAML | audit | — | `test_ap56_frontmatter_heal.py` |
| **AP-29** — Missing status field — nota sin estado de ciclo de vida | audit | `framework` | — |
| **AP-30** — Missing CIA classification — nota sin clasificación de la tríada | audit | — | `test_normas_de_audit_ejercitadas.py` |
| **AP-31** — Grafo sin tipos semanticos — edges sin predicate explícito | audit | — | — |
| **AP-32** — Relaciones tipadas sin predicate valido en la ontologia | audit | — | `test_graph_merge_sugerencias.py` |
| **AP-33** — Predicado no canonico — sinonimo no normalizado | audit | — | `test_graph_merge_sugerencias.py` |
| **AP-34** — Relacion tipada huerfana — endpoint inexistente en el vault | audit | — | `test_graph_merge_sugerencias.py` |
| **AP-35** — Silos de relacion — sistemas de grafos aislados | audit | — | `test_skills_catalogo.py` |
| **AP-36** — Contención e idempotencia — side-effects fuera del vault o no rastreables | guard+audit | `framework` | `test_ap46_heal.py`, `test_arquitectura.py`, `test_ciclo_de_vida_dominio.py`, `test_consulta_dominio.py`, `test_gobernanza_dominio.py`, `test_grafo_dominio.py`, `test_indices_dominio.py`, `test_mcp_http_seguridad.py`, `test_skills_contract.py`, `test_vault_containment.py`, `test_vault_norms_audit.py` |
| **AP-37** — No-op silencioso — ok: true sin indicador de trabajo | audit | `noop` | `test_noop_audit.py`, `test_norms_coherence.py`, `test_voice.py` |
| **AP-38** — Vocabulario validado después de escribir, no antes | guard+audit | `framework` | `test_status_vocabulary.py` |
| **AP-39** — Vocabulario abierto sin memoria | guard+audit | `framework` | `test_ap39_registro_en_el_write_path.py`, `test_tag_vocabulary.py`, `test_vault_init.py` |
| **AP-40** — Contrato publicado que la CLI rechaza | guard+audit | `contratos`, `framework` | `test_catalog_params.py` |
| **AP-41** — Máquina de estados declarada sin verificar | guard+audit | `framework` | `test_status_machine.py`, `test_voice.py` |
| **AP-42** — Tool publicada sin haberse ejecutado nunca | guard+audit | `framework` | `test_smoke.py`, `test_vault_norms_audit.py` |
| **AP-43** — Norma sin refuerzo en el punto de uso | guard+audit | `framework` | `test_ap39_registro_en_el_write_path.py`, `test_vault_norms_audit.py`, `test_voice.py` |
| **AP-44** — Verificación autoconsistente — la tool se certifica a sí misma | guard+audit | `framework` | `test_ap44_verificacion_autoconsistente.py`, `test_kernel.py`, `test_norms_coherence.py` |
| **AP-45** — Cobertura sin evidencia — la nota existe para llenar la sección | guard+audit | `framework` | `test_ap45_cobertura_sin_evidencia.py` |
| **AP-46** — Frontmatter a mano — cada tool es su propio escritor | guard+audit | `framework` | `test_ap46_escritores_migrados.py`, `test_ap46_interpolacion_cruda.py`, `test_ap46_write_path_unico.py`, `test_norms_coherence.py`, `test_vault_sanacion.py` |
| **AP-47** — Artefacto derivado desfasado — el índice dejó de reflejar el disco | guard+audit | `framework` | `test_ap47_indice_refleja_disco.py`, `test_audit_acciones_de_movimiento.py`, `test_grafo_refresco.py` |
| **AP-48** — Implementación paralela por camino de acceso | guard+audit | `contratos`, `framework` | `test_ap48_implementacion_paralela.py` |
| **AP-49** — Vínculo resuelto en tiempo de import | guard+audit | `arquitectura`, `framework` | `test_arquitectura.py`, `test_durabilidad_dominio.py` |
| **AP-50** — Decisión duplicada sin dueño declarado | guard+audit | `arquitectura`, `framework` | `test_ap57_criterios.py` |
| **AP-51** — La tool culpa al dato de su propio fallo | guard+audit | `blame` | `test_ap51_culpar_al_dato.py`, `test_baseline.py` |
| **AP-52** — El error se emite fuera del contrato del catalogo | guard+audit | `contrato_error` | `test_ap52_contrato_de_error.py`, `test_regla7_contraste_ajeno.py` |
| **AP-53** — El historial se afirma a mano y nadie lo contrasta con git | guard | `changelog` | `test_changelog_check.py` |
| **AP-54** — El lock falla y se escribe igual | guard | `arquitectura` | `test_lock_reentrante.py` |
| **AP-55** — El catálogo de normas se certifica a sí mismo | guard+audit | `norms_coherence` | `test_norms_coherence.py` |
| **AP-56** — Frontmatter presente que el consumidor no puede leer | guard+audit | — | `test_ap56_frontmatter_heal.py` |
| **AP-57** — Criterio con dueño, reimplementado en la medida | guard | `criterios` | `test_ap57_criterios.py`, `test_criterios_fronteras.py`, `test_grafo_import.py` |
| **AP-58** — Ciclo esquivado con un import diferido | guard | `ciclos` | `test_ciclos.py` |
| **AP-59** — Núcleo declarado sin contraste | guard+audit | `kernel` | `test_kernel.py` |
| **AP-60** — El guard cobra por declarar y regala el silencio | guard+audit | `norms_coherence` | `test_norms_coherence.py` |
| **AP-61** — El guard cae con el dato que vino a medir | guard+audit | `excepcion_declarada` | `test_excepcion_declarada.py` |
| **AP-62** — El consumidor paga el fan-out del productor | guard+audit | `arquitectura`, `recursos` | `test_recursos.py` |
| **AP-63** — El nombre de un proyecto como texto libre | guard+audit | — | `test_project_registrado.py`, `test_vault_project.py` |
| **AP-64** — Decisión cerrada sin responsable | audit | `framework` | `test_ap64_responsable.py`, `test_iso42005_impacto.py` |
| **AP-65** — Decisión de IA de impacto alto sin evaluación de impacto | audit | `framework` | `test_iso42005_impacto.py` |
| **PAT-6** — Semantic graph enrichment — enriquecimiento periodico del grafo | recommended | — | — |
| **SP-01** — Delete protocol — change_log obligatorio antes de eliminar | audit | `framework` | `test_vault_norms.py` |
| **SP-02** — Forward-link verification — buscar antes de linkar | guard | — | `test_normas_enlaces_sin_solape.py`, `test_vault_norms.py` |
| **SP-03** — Session snapshot pattern — delta antes de operaciones masivas | audit | — | `test_vault_norms.py` |
| **SP-04** — Sesión MCP por HTTP sin credencial — cualquier proceso local la abre | guard | `produccion` | `test_mcp_http_seguridad.py`, `test_token_service_seguridad.py` |
| **CN-01** — Kebab-case filenames — nombres de archivo en minúsculas con guiones | guard | — | `test_ap46_escritores_migrados.py`, `test_cn01_cn04_audit_informativo.py`, `test_meta_contrato.py`, `test_vault_norms.py` |
| **CN-02** — Numbered folder structure — secciones numeradas como únicos destinos | guard+audit | `framework` | `test_blueprint.py`, `test_raiz_no_seccion.py`, `test_vault_norms.py`, `test_vault_norms_audit.py` |
| **CN-03** — Standard status vocabulary — vocabulario canónico de meta.status | audit | `framework` | `test_vault_norms.py`, `test_vault_norms_audit.py`, `test_vault_sanacion.py` |
| **CN-04** — Note opens with its title — la nota abre con su título como H1 | guard | — | `test_cn01_cn04_audit_informativo.py`, `test_cn04_nota_abre_con_titulo.py` |

Sin puerta ni test (9): `AP-04`, `AP-12`, `AP-18`, `PAT-2`, `PAT-3`, `PAT-4`, `AP-27`, `AP-31`, `PAT-6`.

## Capa 5 — Tools → grupos → contrato

*Registros: `vault_mcp_catalog.TOOLS_CATALOG` + `<vault>/00_System/tool-spec.json`*

123 tools activas en 37 grupos. Toda tool
del catálogo tiene entrada de contrato y toda entrada sin catálogo declara
`status: archived | internal | orphan` — no se borra, se anota
(`vault_mcp_catalog.py --check-contracts`).

| Grupo | Tools |
|---|---|
| Backups | 5 |
| Bibliografía | 1 |
| Bootstrap | 2 |
| Change Log | 2 |
| Conocimiento | 2 |
| Core | 8 |
| Corrección Automática | 5 |
| Código | 5 |
| Data Quality | 2 |
| Defectos y Cuarentena | 2 |
| Diagramas | 4 |
| Drift Detection | 1 |
| Flujos | 1 |
| Gestión de Carpetas | 2 |
| IA Governance | 1 |
| Infraestructura | 4 |
| Línea de Tiempo | 1 |
| Memoria de Contexto | 7 |
| Migración | 2 |
| Normas | 25 |
| Observabilidad | 1 |
| Patrones | 2 |
| Producción/SRE | 2 |
| Propagación | 2 |
| Release | 1 |
| Requerimientos | 1 |
| Riesgos/Calidad | 3 |
| Runbooks | 2 |
| Salud del Vault | 7 |
| Seguridad | 1 |
| Session Delta y Tags | 2 |
| Skills | 2 |
| Tests | 3 |
| Tokens | 3 |
| Versionado | 3 |
| Vista del Proyecto | 3 |
| Índices | 3 |

## Capa 6 — Trazabilidad

*Derivada de las capas anteriores: `tool → grupo → capacidad → servicio`*

Una tool sin capacidad no tiene contra qué justificarse, y es así como un catálogo
crece por acumulación. La cadena se exige entera: si un eslabón falta, la puerta
falla — no se rellena con el valor más cercano.

| Tool | Grupo | Capacidad |
|---|---|---|
| `vault_ai_decision` | 21 — IA Governance | escritura_a_gobernanza |
| `vault_append` | 1 — Core | escritura_a_gobernanza |
| `vault_arch` | 35 — Normas | gobernanza_del_estandar |
| `vault_arquitectura_en` | 34 — Memoria de Contexto | consulta_a_contexto |
| `vault_audit` | 6 — Salud del Vault | escritura_a_gobernanza |
| `vault_backup` | 13 — Backups | escritura_a_gobernanza |
| `vault_backup_base64` | 13 — Backups | escritura_a_gobernanza |
| `vault_backup_list` | 13 — Backups | escritura_a_gobernanza |
| `vault_bibliography_save` | 16 — Bibliografía | escritura_a_gobernanza |
| `vault_blame_audit` | 35 — Normas | gobernanza_del_estandar |
| `vault_blueprint` | 35 — Normas | gobernanza_del_estandar |
| `vault_bug_save` | 36 — Defectos y Cuarentena | escritura_a_gobernanza |
| `vault_change_log` | 23 — Change Log | escritura_a_gobernanza |
| `vault_changelog_check` | 35 — Normas | gobernanza_del_estandar |
| `vault_ciclos` | 35 — Normas | gobernanza_del_estandar |
| `vault_code_map` | 12 — Código | escritura_a_gobernanza |
| `vault_code_module` | 12 — Código | escritura_a_gobernanza |
| `vault_code_query` | 12 — Código | escritura_a_gobernanza |
| `vault_code_relation` | 12 — Código | escritura_a_gobernanza |
| `vault_code_sync` | 12 — Código | escritura_a_gobernanza |
| `vault_code_tag` | 35 — Normas | gobernanza_del_estandar |
| `vault_context_pack` | 34 — Memoria de Contexto | consulta_a_contexto |
| `vault_criterios` | 35 — Normas | gobernanza_del_estandar |
| `vault_delete` | 23 — Change Log | escritura_a_gobernanza |
| `vault_delta` | 27 — Session Delta y Tags | escritura_a_gobernanza |
| `vault_diagram_export` | 4 — Diagramas | escritura_a_gobernanza |
| `vault_diagram_save` | 4 — Diagramas | escritura_a_gobernanza |
| `vault_diff` | 1 — Core | escritura_a_gobernanza |
| `vault_doc_counts` | 35 — Normas | gobernanza_del_estandar |
| `vault_doc_staleness` | 35 — Normas | gobernanza_del_estandar |
| `vault_doc_sync` | 35 — Normas | gobernanza_del_estandar |
| `vault_drift_detect` | 17 — Drift Detection | escritura_a_gobernanza |
| `vault_env_matrix` | 8 — Infraestructura | escritura_a_gobernanza |
| `vault_env_save` | 8 — Infraestructura | escritura_a_gobernanza |
| `vault_error_contract` | 35 — Normas | gobernanza_del_estandar |
| `vault_esquema` | 35 — Normas | gobernanza_del_estandar |
| `vault_excepcion_declarada` | 35 — Normas | gobernanza_del_estandar |
| `vault_fix_all` | 35 — Normas | gobernanza_del_estandar |
| `vault_fix_brackets` | 33 — Corrección Automática | escritura_a_gobernanza |
| `vault_flow_save` | 18 — Flujos | escritura_a_gobernanza |
| `vault_folder_registry` | 32 — Gestión de Carpetas | escritura_a_gobernanza |
| `vault_foreign_check` | 35 — Normas | gobernanza_del_estandar |
| `vault_frontmatter_completar` | 33 — Corrección Automática | escritura_a_gobernanza |
| `vault_frontmatter_heal` | 33 — Corrección Automática | escritura_a_gobernanza |
| `vault_fuente_unica` | 6 — Salud del Vault | escritura_a_gobernanza |
| `vault_fundamentals` | 24 — Data Quality | escritura_a_gobernanza |
| `vault_gate` | 35 — Normas | gobernanza_del_estandar |
| `vault_gobernanza` | 6 — Salud del Vault | escritura_a_gobernanza |
| `vault_graph` | 6 — Salud del Vault | escritura_a_gobernanza |
| `vault_graph_fix` | 33 — Corrección Automática | escritura_a_gobernanza |
| `vault_graph_inspect` | 6 — Salud del Vault | escritura_a_gobernanza |
| `vault_graph_merge` | 6 — Salud del Vault | escritura_a_gobernanza |
| `vault_history_compact` | 22 — Versionado | escritura_a_gobernanza |
| `vault_impact` | 25 — Propagación | escritura_a_gobernanza |
| `vault_incident_save` | 28 — Producción/SRE | escritura_a_gobernanza |
| `vault_infra_map` | 8 — Infraestructura | escritura_a_gobernanza |
| `vault_infra_save` | 8 — Infraestructura | escritura_a_gobernanza |
| `vault_ingest` | 34 — Memoria de Contexto | consulta_a_contexto |
| `vault_init` | 31 — Bootstrap | escritura_a_gobernanza |
| `vault_kernel` | 35 — Normas | gobernanza_del_estandar |
| `vault_knowledge_get` | 5 — Conocimiento | escritura_a_gobernanza |
| `vault_knowledge_save` | 5 — Conocimiento | escritura_a_gobernanza |
| `vault_list` | 1 — Core | escritura_a_gobernanza |
| `vault_log_error` | 2 — Observabilidad | escritura_a_gobernanza |
| `vault_master_index` | 15 — Índices | escritura_a_gobernanza |
| `vault_merge` | 1 — Core | escritura_a_gobernanza |
| `vault_mermaid_check` | 4 — Diagramas | escritura_a_gobernanza |
| `vault_migrate_docs` | 9 — Migración | escritura_a_gobernanza |
| `vault_migrate_rollback` | 9 — Migración | escritura_a_gobernanza |
| `vault_model_profile` | 34 — Memoria de Contexto | consulta_a_contexto |
| `vault_move` | 1 — Core | escritura_a_gobernanza |
| `vault_ncr_save` | 30 — Riesgos/Calidad | escritura_a_gobernanza |
| `vault_noop_audit` | 35 — Normas | gobernanza_del_estandar |
| `vault_norms` | 35 — Normas | gobernanza_del_estandar |
| `vault_norms_coherence` | 35 — Normas | gobernanza_del_estandar |
| `vault_onboard` | 31 — Bootstrap | escritura_a_gobernanza |
| `vault_pattern_list` | 3 — Patrones | escritura_a_gobernanza |
| `vault_pattern_save` | 3 — Patrones | escritura_a_gobernanza |
| `vault_preferences` | 34 — Memoria de Contexto | consulta_a_contexto |
| `vault_privacy_save` | 30 — Riesgos/Calidad | escritura_a_gobernanza |
| `vault_produccion` | 35 — Normas | gobernanza_del_estandar |
| `vault_project` | 11 — Vista del Proyecto | escritura_a_gobernanza |
| `vault_project_overview` | 11 — Vista del Proyecto | escritura_a_gobernanza |
| `vault_project_status` | 11 — Vista del Proyecto | escritura_a_gobernanza |
| `vault_propagate` | 25 — Propagación | escritura_a_gobernanza |
| `vault_qa_save` | 20 — Tests | escritura_a_gobernanza |
| `vault_quality_check` | 24 — Data Quality | escritura_a_gobernanza |
| `vault_quality_dashboard` | 20 — Tests | escritura_a_gobernanza |
| `vault_quarantine` | 36 — Defectos y Cuarentena | escritura_a_gobernanza |
| `vault_query_parse` | 34 — Memoria de Contexto | consulta_a_contexto |
| `vault_read` | 1 — Core | escritura_a_gobernanza |
| `vault_recursos` | 35 — Normas | gobernanza_del_estandar |
| `vault_reindex` | 15 — Índices | escritura_a_gobernanza |
| `vault_relation_add` | 4 — Diagramas | escritura_a_gobernanza |
| `vault_release_save` | 29 — Release | escritura_a_gobernanza |
| `vault_requirement_save` | 19 — Requerimientos | escritura_a_gobernanza |
| `vault_restore` | 13 — Backups | escritura_a_gobernanza |
| `vault_restore_base64` | 13 — Backups | escritura_a_gobernanza |
| `vault_risk_save` | 30 — Riesgos/Calidad | escritura_a_gobernanza |
| `vault_runbook_log` | 7 — Runbooks | escritura_a_gobernanza |
| `vault_runbook_save` | 7 — Runbooks | escritura_a_gobernanza |
| `vault_sanacion` | 37 — Skills | escritura_a_gobernanza |
| `vault_sdd_init` | 37 — Skills | escritura_a_gobernanza |
| `vault_search` | 1 — Core | escritura_a_gobernanza |
| `vault_section` | 32 — Gestión de Carpetas | escritura_a_gobernanza |
| `vault_section_index` | 15 — Índices | escritura_a_gobernanza |
| `vault_security_scan` | 14 — Seguridad | escritura_a_gobernanza |
| `vault_servicio` | 35 — Normas | gobernanza_del_estandar |
| `vault_slo_save` | 28 — Producción/SRE | escritura_a_gobernanza |
| `vault_smoke` | 35 — Normas | gobernanza_del_estandar |
| `vault_standard_upgrade` | 22 — Versionado | escritura_a_gobernanza |
| `vault_subgraph` | 34 — Memoria de Contexto | consulta_a_contexto |
| `vault_supersede` | 33 — Corrección Automática | escritura_a_gobernanza |
| `vault_tags` | 27 — Session Delta y Tags | escritura_a_gobernanza |
| `vault_test_save` | 20 — Tests | escritura_a_gobernanza |
| `vault_timeline` | 10 — Línea de Tiempo | escritura_a_gobernanza |
| `vault_token_counter` | 26 — Tokens | consulta_a_contexto |
| `vault_token_service` | 26 — Tokens | consulta_a_contexto |
| `vault_tokens` | 26 — Tokens | consulta_a_contexto |
| `vault_undo` | 22 — Versionado | escritura_a_gobernanza |
| `vault_validate` | 6 — Salud del Vault | escritura_a_gobernanza |
| `vault_voice` | 35 — Normas | gobernanza_del_estandar |
| `vault_write` | 1 — Core | escritura_a_gobernanza |

## Capa 7 — Deuda viva

*Registro: `vault_blueprint.DEUDA_DECLARADA` + las baselines de `scripts/`*

Deuda **declarada**: conocida, medida y con motivo escrito de por qué no se ataca
todavía. Lo que no está aquí no es que no exista — es que nadie lo ha medido, que
es una situación distinta y peor.

**10 pendientes** de 17 declaradas. Una deuda saldada no
desaparece de la tabla: se queda con `estado: saldada` y la versión que la cerró,
porque una entrada borrada no se distingue de una que nadie volvió a mirar.

| Deuda | Estado | Desde | Capa | Qué | Por qué no ahora |
|---|---|---|---|---|---|
| `envelopes_del_dominio_sin_error_code` | saldada en v40.29 | v40.9 | 5 | Nueve `{"ok": False, "error": ...}` en `vault/durabilidad/` y `vault/indices/` que los adaptadores de `scripts/` devuelven tal cual al consumidor: el envelope sale sin `error_code` ni `recovery`. Aparecieron en v40.9 al ensanchar el alcance de AP-52 más allá de `scripts/`, y quedan congelados en `error-contract-baseline.json`. v40.29 los saldó partiendo la frase en dos mitades con dueño: el dominio levanta un `FalloDeDominio` que nombra la **causa** (`vault/kernel/fallos.py`, sin un solo import fuera de `typing`) y la traducción a `error_code` vive en un único sitio del lado de la herramienta, `vault_errors.emit_fallo`. Se levanta en vez de devolver porque un fallo devuelto como valor se ignora por olvido, y uno de los cuatro casos es el borrado del vault sin confirmar. La baseline de AP-52 queda **vacía por primera vez desde que la norma existe**, y los campos que el contrato declara estables —`error`, `hint`, `searched`— siguen saliendo: mejorar el envelope por debajo no autoriza a romper el contrato de arriba. | La pregunta de fondo no es cómo se escribe el envelope sino quién lo escribe: hacer que el dominio importe `vault_errors` lo ata al catálogo de la herramienta, y convertirlo en el adaptador exige decidir qué devuelve el dominio en su lugar. Es una decisión de capas, no un reemplazo de literales. |
| `handler_amplio_en_el_registro_de_la_cli` | saldada en v40.23 | v40.9 | 5 | `cli/registry.py::_load_spec` responde a un `except Exception` con un vacío indistinguible: un `tool-spec.json` ilegible se presenta como un catálogo sin entradas (AP-51). Destapado por el mismo ensanche de alcance de v40.9 y congelado en `blame-baseline.json`. v40.23 (77981b5) lo cerró con `_leer_spec`, que distingue `ausente`, `ilegible` y `legible`, y `spec_status` lo expone a `cli doctor`; el registro siguió diciendo `pendiente` hasta que se midió en v41.2. | Distinguir «no hay spec» de «la spec no se pudo leer» cambia lo que `cli doctor` reporta, y esa salida ya la consumen los repos consumidores. Se toca con su propio test de contrato. |
| `normas_criticas_sin_detector` | pendiente | v40.11 | 4 | Tres normas no las mide nadie y lo declaran por escrito en `cobertura_descubierta`: AP-01, AP-04 y AP-08. Desde v40.11 eran cuatro; AP-02, la variante same-folder cuyas hermanas AP-17 y AP-18 sí pesan en el healthIndex, pasó a `cobertura_parcial` cuando `vault_audit` empezó a medir la versión que el nombre declara (`sameFolderVersions`). **El titular de esta entrada era AP-05, la única `critical` descubierta, y salió en v40.15**: `vault_fuente_unica` (puerta 16) mide el mismo dato **tipado** —IP, URL, puerto, semver— con valores distintos en un mismo ámbito. No cerró el problema general: el catálogo la declara `cobertura_parcial`, porque la divergencia en prosa, la de valores sin tipo y la del sinónimo (`ip:` frente a `direccion_ip:`) siguen sin medirlas nadie. La entrada sigue pendiente por las otras tres, no por AP-05 ni AP-02. (Avance de v41.3: AP-08 pasó a `cobertura_parcial` con `vault_drift_detect --mode vigencia`, y AP-01 también, en el mismo modo: un `files:` que no está en el disco del repo sale en `codigo_inexistente`. Medido contra la copia de /ans: con la base buena, 0 AP-01 y 7 AP-08; con `--path` en la raíz, las 7 salían AP-01, y por eso la respuesta lleva una `pista` cuando no resuelve ninguno. Queda AP-04 entera, y de AP-01 y AP-08 la parte escrita en prosa.) | AP-05 tuvo su tanda en v40.15, y lo que la desbloqueó no fue resolver el problema abierto: fue dejar de plantearlo entero. Un valor **tipado** no se reconoce por parecido, se compara por igualdad, y su identidad no se adivina —está escrita al lado, como clave de un `clave: valor`—. Eso quita la semántica de en medio y deja una parte decidible, que es la que se mide; el resto se declara en vez de darse por cubierto. Las tres que quedan siguen sin una reformulación equivalente, y ninguna es `critical`. (En v41.3 AP-08 y AP-01 la encontraron en `files:`, que la nota declara. AP-04 no: su señal decidible es la misma que la de AP-01 y el discriminador —la intención— no está en ningún campo; el motivo queda en su `cobertura_descubierta`.) |
| `fronteras_de_escritura_por_contexto` | pendiente | v40.9 | 3 | Ningún guard dice qué contexto puede escribir dónde. `00_System` lo escriben hoy seis contextos. | Exige antes sanear `_LLAMADAS_DE_ESCRITURA` —incluye `replace`, que captura `str.replace`, y `write_report`, que no escribe— y una decisión de diseño que nadie ha tomado: de quién es `00_System`. (El saneado está hecho en v41.3: `vault_arch.llamada_de_escritura` es la única definición de «escribe» de las dos guardas, `write_report` salió de la lista y `replace` se decide por la forma —de 640 llamadas que contaban en `scripts/`, 336 no escribían—. Queda la decisión de dueño, que es del usuario.) |
| `recursion_error_en_parsers` | saldada en v40.23 | v40.9 | 5 | `RecursionError` escapa a `except yaml.YAMLError` en 4 parsers: no es subclase. Reproducido a 400 corchetes anidados. El peor caso es `vault_foreign_check`, que es la tool de la regla 7. v40.23 (77981b5) lo cerró con AP-61 y su puerta `vault_excepcion_declarada`, y el test ejecuta el dato hostil contra los parsers reales, `vault_foreign_check` incluido. | Es un arreglo de robustez con su propia norma candidata; entra en la tanda donde se unifiquen los parsers, no en una de alcance. |
| `parsers_de_frontmatter_divergentes` | pendiente | v40.9 | 5 | 8 parsers de frontmatter distintos (esa parte, saldada en v41.2: al medirla eran once lectores por líneas en diez módulos, y todos delegan en `vault/kernel/frontmatter_parsing.cargar_bloque_tolerante`; `vault_criterios.medir_lecturas` hace fallar la puerta AP-57 ante uno nuevo); `vault_write.slugify` no delega en `vault_lib` aunque 20 módulos sí (esa parte, saldada en v40.35: delega en `slugify_strict` y el slug viejo queda solo para encontrar notas ya escritas); 6 aliases de v40.8 con el nombre viejo aún en uso; `--agent default="claude"` en 6 tools frente al AP-16 que `vault_bug_save` exige. | Es AP-50 acumulado y se salda unificando, no parcheando: hacerlo a medias deja nueve parsers en vez de ocho. Quedan los aliases y el `--agent` por defecto, y lo segundo cambia lo que reciben los clientes MCP: lo decide el usuario, no esta tanda. |
| `catch_vacios_en_el_servidor_mjs` | saldada en v41.2 | v40.9 | 7 | 11 `catch (_) {}` en `mcp/nodejs/vault-mcp-server.mjs` (AP-51 en JS). v41.2 los midió uno a uno: los que convertían un fallo en un vacío —traza, sello de versión, backup, recuento del registro, mapa de enlaces— ahora lo exponen; los legítimos —caer a un error declarado, probar el siguiente candidato— lo dicen con `AP-51:`. `vault_blame_audit.catch_silenciosos_js` mide la frontera JS sin baseline, con tolerancia cero. | Los tres audits con baseline miden AST de Python. Un detector de JavaScript es otro proyecto, y fingir que el alcance lo cubre sería el mismo cero sobre un subconjunto que esta versión vino a cerrar. |
| `baselines_sin_objetivo_ni_pendiente` | saldada en v40.24 | v40.20 | 7 | Las baselines del repo solo podían **encoger**, y eso es un suelo, no una trayectoria: nada declaraba a cuánto deberían llegar ni a qué ritmo. v40.24 lo cierra con el mecanismo, no con una cifra: `vault_baseline` es el dueño único de la carga, la escritura y la negativa a crecer, y el contrato de `objetivo` exige tamaño, fecha límite, cadencia y dueño — un número suelto no valida. La pendiente se deriva de `git log` cada vez que se genera este plano y **nunca se escribe** en el fichero, porque escribirla sería afirmar sobre la historia sin que git la respalde (AP-53). Las dos columnas nuevas de la tabla de abajo son eso. Con ello `gancho_sin_presupuesto` deja de ser informativo: los seis `GANCHOS_DEL_KERNEL` declaran presupuesto en `vault_arch.PRESUPUESTO_DE_GANCHOS` y el séptimo sin declarar bloquea la puerta. | Cerrada. Lo que queda no es esta deuda sino la siguiente, y va declarada aparte: el mecanismo existe y la mayoría de las baselines todavía publican `sin objetivo`. |
| `baselines_sin_objetivo_asignado` | pendiente | v40.24 | 7 | El campo `objetivo` ya existe y se valida, pero solo `excepcion-declarada-baseline.json` lo declara — y allí el valor no es una decisión, es lo que la propia baseline ya decía: nació vacía y el objetivo es que siga vacía. Las demás publican `— sin objetivo` en la capa 6, que es el estado honesto y no se confunde con `cumple`. | A cuánto debe encoger cada baseline y para cuándo es un compromiso del dueño del repo, no un dato derivable. Escribir trece cifras plausibles para que la tabla se vea completa sería exactamente el AP-47 que el contrato de `objetivo` existe para impedir, cometido dentro del mecanismo que lo impide. |
| `vault_norms_es_un_modulo_dios` | saldada en v40.27 | v40.20 | 7 | `vault_norms` acumula miles de líneas y la mayor parte de los cruces sin puerto del repo. Las dos cifras iban escritas aquí y las dos habían envejecido —decía 4.257 líneas cuando ya eran más de cinco mil, y «9 de los 13 cruces» cuando el reparto había cambiado—, que es AP-47 cometido dentro del registro que publica la deuda de AP-47; se miden con `wc -l scripts/vault_norms.py` y con `off_port_crossings` de `scripts/arch-baseline.json`, y por eso ya no se copian. No es un problema de clasificación —al medir para v40.20 se comprobó que su fan-in no es el del núcleo—: es un módulo que hace de catálogo, de motor y de fachada a la vez, con las dependencias invertidas. Se parte en `catalog` / `engine` / fachada y se invierten esos cruces. v40.26 hizo el corte y v40.27 lo cobró: partido, `vault_norms_catalog` resultó tener fan-out cero —la forma de `vault_registry`— y se mudó al núcleo con `compute_norm_refs`. Veintiuno de sus veinticuatro importadores solo pedían datos y ahora se los piden al dueño: **62 → 42 cruces, veinte saldados, cero nuevos**, y quince ciclos diferidos de AP-58 resueltos de paso, porque `vault_voice` dejó de importar la fachada. La deuda se cierra midiendo, no declarándolo: el corte por sí solo no movió una sola cifra. | Es la tanda más cara de las cinco y depende de lo que el mapa del núcleo revele. Partirlo antes de tener el grafo con dueño habría sido mover código a ciegas. |
| `la_norma_no_es_un_paquete` | pendiente | v40.20 | 7 | El ciclo obligatorio del repo —síntoma → norma → guard+audit+heal → test— vive hoy en cuatro listas sincronizadas a mano: el catálogo, la tool, la puerta y el fichero de tests. La norma como **paquete** (`normas/AP-XX/` con `norma.py`, `guard.py`, `heal.py`, `test_*.py` y `porque.md`) la convierte en una sola cosa con cuatro caras, y el coste de una norma nueva deja de crecer con la historia del repo. | Migra por atrición, no de golpe: 71 normas movidas en una tanda serían 71 oportunidades de perder un matiz. Empieza por las que se escriban a partir de ahora. |
| `el_vault_no_tiene_kernel_declarado` | pendiente | v40.20 | 7 | `vault_kernel` traza el núcleo **del repo**. El mismo concepto aplicado a las notas —qué subconjunto de un vault es su núcleo— daría prioridad a `vault_context_pack` cuando el paquete no cabe, orden a la sanación y pesos a `vault_audit`. | Declarado sin fecha por decisión de alcance. El núcleo de un vault no se deriva del grafo de imports sino del de enlaces, y esa medida hay que contrastarla contra un vault ajeno antes de creérsela (regla 7). |
| `puente_scripts_impl_sin_contrato` | pendiente | v40.34 | 3 | `_impl/` no es una copia de `scripts/`: es el destino del package-dir que mapea `scripts/` → `vault_toolkit/_impl/`. ADR-0002 formaliza el puente: fachada de re-export + package-dir. La deuda es transitoria: desaparece cuando `scripts/` migre a `vault/<contexto>/` y el puente ya no sea necesario. | Transitorio hasta migrar scripts → vault/<contexto>, ADR-0002. La fachada y el package-dir existen; la deuda es de diseño, no de implementacion. |
| `cn01_cn04_solo_se_miden_al_escribir` | pendiente | v41.1 | 4 | CN-01 (nombre kebab-case) y CN-04 (la nota abre con su título como H1) tienen enforcement `guard` y se cumplen solo en el write path: `vault_write`, `vault_knowledge_save` y `vault_ai_decision`. Una nota escrita por otro camino —un vault preexistente, una edición a mano— no la mide nadie después. El docstring de `vault_write.slugify` lo dice de CN-01: «ninguna otra tool audita después los nombres ya escritos». El único `"norm": "CN-01"` de `vault_audit` es sobre el scaffold, no sobre los nombres de las notas. (La medida, hecha en v41.2: `vault_audit._detect_convenciones_cn01_cn04` las publica en `issues.cn01NotKebab`/`cn04NoTitle`, sin peso, con el criterio de `slugify_strict` y `abre_con_h1`. Regla 7, 2026-10-08, sobre copias: /ans 94 y 253 de 527 notas, /vcloud 1 y 0 de 108. De las 253 de /ans, 137 son de `11_Code`: `vault_code_module` y otros escritores del estándar no pasan por `con_titulo`.) | Medirlas en notas existentes cambia el enforcement a `guard+audit` y, si penalizan, el healthIndex de todo vault consumidor. Es una decisión de norma, con su tabla de penalizaciones y su contraste contra un vault ajeno antes de fijar el peso (regla 7), no un arreglo de la tanda. Queda: decidir el peso —lo decide el usuario— y que los escritores que no aplican `con_titulo` lo hagan, que cambia su salida. |
| `ap17_compara_solo_la_forma_del_titulo` | pendiente | v41.1 | 4 | AP-17 (sombra canónica) se detecta con `SequenceMatcher` ≥ 0.85 sobre el texto del título (`vault_audit._detect_canonical_shadow`). Dos notas sobre lo mismo con títulos distintos no salen, y dos títulos parecidos de cosas distintas solo se separan si `_distintos_por_convencion` reconoce la convención. La atribución que esta entrada también reclamaba ya estaba bien y se corrigió aquí en v41.2: el catálogo declara `tools_detecting: ['vault_audit']`, quien mide, y `tools_enforcing: ['vault_supersede']`, quien sana. Lo pendiente es solo la medida. | Ir más allá de la forma pide comparar contenido o identidad declarada, que es justo lo que el servicio descarta sin embeddings. Hace falta una reformulación decidible, como la que desbloqueó AP-05 en v40.15, antes de tocar el detector. |
| `churn_del_kernel_no_ve_el_commit_en_curso` | pendiente | v41.1 | 7 | K3 de `vault_kernel` (AP-59) cuenta el churn con `git log`, así que la puerta que corre antes de commitear no ve el commit que se está haciendo. El que cruza el umbral pasa en verde y el siguiente, aunque no toque el módulo, hereda el rojo. Pasó en esta ronda: `vault_registry` llegó a churn 23 con umbral 22.85 (mediana 13 × 1.758) y hubo que admitirlo en `kernel-baseline.json` con autorización expresa. | Contar el índice (`git diff --cached --name-only`) arregla el pre-commit pero hace que la misma medida dé cifras distintas según se ejecute antes o después de commitear, y la CI mide después. Hay que decidir cuál es la medida canónica antes de cambiar el contador. |
| `meta_decide_el_orden_del_frontmatter` | saldada en v41.2 | v41.1 | 5 | En `vault_write`, los campos que llegan por `--meta` se añaden al final del frontmatter. Medido el 2026-10-07: con `--meta '{"agent":"claude","type":"concept"}'`, `type` sale detrás de `agent` y de los tres `cia_*`, y su posición depende de por dónde llegó y no de qué campo es. | Ningún consumidor que lea con `yaml.safe_load` depende del orden, así que no rompe nada. Fijar un orden canónico cambia byte a byte la salida de toda nota nueva, y ese orden tiene que salir del contrato de nota (`vault_contrato_nota`), no de una lista nueva. Saldada en v41.2 con el orden mínimo que eligió el usuario: el `type` de `meta` ocupa el hueco del deducido, el resto de campos de `CAMPOS` sale tras `agent` en su orden y lo ajeno al contrato al final; una nota sin esos campos en `meta` no cambia un byte. |

| Baseline | Norma | Congelado | Objetivo | Pendiente |
|---|---|---|---|---|
| `scripts/arch-baseline.json` | cruces entre contextos | 37 | — *sin objetivo* | 35 → 34 → 35 → 36 → 37 → 37 (encoge, Δ-20) |
| `scripts/arch-baseline.json` | cruces fuera de puerto | 8 | — *sin objetivo* | 12 → 8 → 8 → 8 → 8 → 8 (encoge, Δ-40) |
| `scripts/blame-baseline.json` | AP-51 | 33 | — *sin objetivo* | 87 → 84 → 83 → 45 → 33 → 33 (encoge, Δ-53) |
| `scripts/error-contract-baseline.json` | AP-52 | 0 | — *sin objetivo* | 158 → 110 → 110 → 0 → 9 → 0 (encoge, Δ-158) |
| `scripts/noop-baseline.json` | AP-37 | 0 | — *sin objetivo* | 0 → 0 → 0 (plana, Δ+0) |
| `scripts/smoke-baseline.json` | AP-42 | 0 | — *sin objetivo* | — *1 muestra* |
| `scripts/blueprint-baseline.json` | capa 4 — norma sin puerta ni test | 8 | — *sin objetivo* | 16 → 15 → 14 → 13 → 13 → 8 (encoge, Δ-8) |
| `scripts/criterios-baseline.json` | AP-57 | 9 | — *sin objetivo* | 10 → 9 → 9 → 9 (encoge, Δ-1) |
| `scripts/ciclos-baseline.json` | AP-58 — ciclo esquivado con import diferido | 5 | — *sin objetivo* | 30 → 30 → 15 → 14 → 7 → 5 (encoge, Δ-25) |
| `scripts/kernel-baseline.json` | AP-59 — núcleo declarado sin contraste | 4 | — *sin objetivo* | 5 → 5 → 6 → 6 → 5 → 4 (encoge, Δ-1) |
| `scripts/norms-distincion-baseline.json` | AP-60 — normas que no declaran de qué se distinguen | 0 | — *sin objetivo* | 57 → 0 → 0 (encoge, Δ-57) |
| `scripts/norms-coherence-baseline.json` | AP-55 — C2, afirmación sin traza | 0 | — *sin objetivo* | 47 → 0 (encoge, Δ-47) |
| `scripts/field-compat-baseline.json` | contrato de campos con los consumidores | 1410 | — *sin objetivo* | 1357 → 1368 → 1378 → 1380 → 1389 → 1410 (crece, Δ+190) |
| `scripts/excepcion-declarada-baseline.json` | AP-61 — la excepción declarada no es la que escapa | 0 | ≤ 0 para 2027-06-30 · cada 180 d · gobernanza → **cumple** | 0 → 0 (plana, Δ+0) |
| `scripts/recursos-baseline.json` | AP-62 — el consumidor cruza para leer un recurso y paga el fan-out | 2 | — *sin objetivo* | — *1 muestra* |

Todas encogen y ninguna crece sin decirlo: los tres audits con baseline indexan
por firma de sitio —`módulo::función::hash de `ast.unparse``— así que mover un
sitio ya no lo estrena como deuda nueva, y `--freeze` se niega a congelar lo que
no tiene precedente salvo con `--admitir-nuevos`, que además lo lista.

Las dos últimas columnas son de v40.24 y no dicen lo mismo. **Objetivo** es un
compromiso escrito —a cuánto debe encoger, para cuándo, con qué cadencia y quién
lo revisa— y `sin objetivo` se publica como tal en vez de leerse como cumplido:
no comprometerse no puede salir más barato que comprometerse. **Pendiente** no se
escribe en ninguna parte: sale de `git log` sobre el propio fichero cada vez que
se genera este plano, porque una pendiente escrita a mano sería una afirmación
sobre la historia sin que git la respalde (AP-53).

---

*23 puertas de cierre. Generado por `scripts/vault_blueprint.py`.*
