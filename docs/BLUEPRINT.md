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
| Sin base de datos, sin embeddings y sin servicio externo. | Es una decisión de producto, no una limitación pendiente de resolver: el vault debe seguir siendo legible y editable por una persona con un editor de texto, y sobrevivir a que este toolkit desaparezca. | `CLAUDE.md — Los dos ejes; vault_arch.CONTEXTS['consulta']['prohibe']` |
| Solo stdlib + PyYAML. | Un agente instala el toolkit en el repo del usuario; cada dependencia es una razón para que no lo haga. | `CLAUDE.md — Qué contiene` |
| Nada se elimina; lo reemplazado se anota `superseded_by:`. | Los vaults consumidores leen contratos de este repo. Un campo que evapora rompe en silencio a quien lo leía. | `CLAUDE.md — regla 2; manifiesto § Política de no-derogación` |

## Capa 2 — Capacidades → grupos

*Registro: `vault_servicio.CAPACIDADES` + `vault_mcp_catalog.mapa_de_grupos()`*

| Capacidad | Resultado | Grupos | Tools |
|---|---|---|---|
| **Escritura → gobernanza** (`escritura_a_gobernanza`) | Lo que el agente captura queda escrito una sola vez, normalizado contra las normas, versionado y auditable después. | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 27, 28, 29, 30, 31, 32, 33, 36, 37 | 77 |
| **Consulta → contexto** (`consulta_a_contexto`) | Una pregunta del agente se convierte en un paquete de contexto acotado y presupuestado, recorriendo el grafo del vault sin índice externo. | 26, 34 | 8 |
| **Gobernanza del estándar** (`gobernanza_del_estandar`) | El estándar cumple lo que publica: registro canónico primero, doc derivada, guard que falla si divergen. Ninguna de estas tools toca las notas de un usuario. | 35 | 16 |

- **`consulta_a_contexto`** — El grupo 26 (Tokens) cae en el rango 1–33 que `CLAUDE.md` atribuye al primer eje, pero sus tres tools viven en el contexto `consulta` y existen para que el paquete quepa en la ventana. El rango es cronológico, no clasificatorio.
- **`gobernanza_del_estandar`** — Tercera capacidad que `CLAUDE.md` no nombraba. Existía desde que se escribió la primera puerta; declararla es lo que impide que sus 13 tools se cuenten como si sirvieran a la memoria del agente.

Guard: todo grupo del catálogo pertenece a exactamente una capacidad y toda
capacidad tiene al menos una tool viva (`vault_servicio.py --check --strict`).

## Capa 3 — Contextos acotados → puertos

*Registro: `vault_arch.CONTEXTS`. El detalle de puertos y cruces vive en
[`docs/ARQUITECTURA.md`](./ARQUITECTURA.md), que no se absorbe aquí: son dos
documentos con dos sujetos, y fundirlos habría hecho un solo documento que nadie
regenera.*

| Contexto | Puertos | Módulos | Prohíbe |
|---|---|---|---|
| **Kernel** (`kernel`) | 4 | 11 | depender de cualquier contexto de dominio |
| **Autoría** (`autoria`) | 7 | 39 | — |
| **Grafo** (`grafo`) | 3 | 15 | — |
| **Gobernanza** (`gobernanza`) | 19 | 9 | — |
| **Índices** (`indices`) | 8 | 6 | — |
| **Consulta** (`consulta`) | 7 | 10 | base de datos; embeddings; servicio externo |
| **Ciclo de vida** (`ciclo_de_vida`) | 3 | 8 | — |
| **Durabilidad** (`durabilidad`) | 4 | 4 | escribir fuera de la raíz del vault (AP-36) |
| **Meta-toolkit** (`meta_toolkit`) | 3 | 22 | escribir en una sección de contenido: sus artefactos derivados viven en 00_System/ |

## Capa 4 — Normas → puertas → tests

*Registros: `vault_norms.NORM_CATALOG` + `vault_gate.PUERTAS` + `tests/`*

54 de 68 normas tienen puerta o test que las nombre.
**Es la única capa con baseline**, y por un motivo concreto: las demás se midieron
en cero el día que se declararon porque sus datos ya existían y solo faltaba
atarlos. Ésta no. Exigir cero aquí el primer día habría hecho nacer la puerta en
rojo, y una puerta en rojo se desactiva.

| Norma | Enforcement | Puertas | Tests |
|---|---|---|---|
| **AP-01** — Documentación alucinada | audit | — | `test_cli_package.py`, `test_context_memory.py`, `test_registry_derivation.py`, `test_skills_catalogo.py`, `test_skills_contract.py`, `test_vault_norms.py`, `test_vault_sdd_init.py` |
| **AP-02** — Proliferación de versiones del mismo documento | audit | — | `test_skills_contract.py` |
| **AP-03** — Stubs sin política de expansión | audit | — | `test_audit_resuelve_como_obsidian.py` |
| **AP-04** — Features aspiracionales documentadas como implementadas | audit | — | `test_cli_package.py`, `test_context_memory.py`, `test_data_framework.py`, `test_skills_contract.py` |
| **AP-05** — Múltiples fuentes de verdad para el mismo dato | audit | — | `test_ap50_decision_duplicada.py`, `test_arquitectura.py`, `test_autoria_dominio.py`, `test_blueprint.py`, `test_ciclo_de_vida_dominio.py`, `test_consulta_dominio.py`, `test_durabilidad_caracterizacion.py`, `test_durabilidad_declarada.py`, `test_gobernanza_dominio.py`, `test_grafo_dominio.py`, `test_indices_dominio.py`, `test_lifecycle_registry.py`, `test_norms_coherence.py`, `test_raiz_no_seccion.py`, `test_registro_de_entorno.py`, `test_registro_de_vocabulario.py`, `test_regla7_contraste_ajeno.py`, `test_vault_gate.py` |
| **AP-06** — Templates sin instancias reales | audit | `framework` | — |
| **AP-07** — ADRs incompletos | audit | `framework` | `test_audit_resuelve_como_obsidian.py`, `test_vault_norms_audit.py`, `test_vault_onboard.py` |
| **AP-08** — Documentación anclada a versiones obsoletas | audit | — | — |
| **AP-09** — Runbooks fuera de estructura | audit | `framework` | `test_vault_norms_audit.py` |
| **AP-10** — Migración sin plan de rollback | audit | `framework` | — |
| **AP-11** — Skeleton files — frontmatter válido, contenido vacío | guard | — | `test_status_machine.py`, `test_voice.py` |
| **AP-12** — Frontmatter inconsistente entre notas del mismo tipo | audit | — | — |
| **AP-13** — Timestamps inválidos o incompletos en frontmatter | audit | — | — |
| **AP-14** — Wiki-links rotos o vacíos | guard+audit | — | `test_ap44_verificacion_autoconsistente.py`, `test_audit_no_audita_instantaneas.py`, `test_norms_coherence.py` |
| **AP-15** — Archivos externos depositados en la raíz del vault | audit | `framework` | `test_indices_dominio.py`, `test_vault_norms_audit.py` |
| **AP-16** — Sin identificador de agente en frontmatter | audit | — | `test_caracterizacion_de_los_save.py`, `test_cli_package.py`, `test_context_memory.py` |
| **AP-17** — Canonical-shadow duplication | audit | — | `test_ap17_convencion_de_nombres.py`, `test_mcp_runner.py` |
| **AP-18** — Cross-folder content duplication | audit | — | — |
| **AP-19** — Shadow indexing | audit | `framework` | — |
| **AP-20** — Deceptive skeleton (empty-list) | guard | — | — |
| **AP-21** — Path-anchored wiki-links | guard | — | `test_indices_dominio.py`, `test_vault_regex.py` |
| **AP-22** — Wiki-link vacío — [[]] sin destino | guard+audit | — | `test_norms_coherence.py`, `test_vault_regex.py` |
| **PAT-1** — Canonical source anchoring | recommended | — | `test_norms_coherence.py` |
| **PAT-2** — Stub enrichment gradient | recommended | — | — |
| **PAT-3** — Duplicate chain resolution | recommended | — | — |
| **PAT-4** — Phased audit execution | recommended | — | — |
| **PAT-5** — Frontmatter as provenance chain | recommended | — | `test_context_memory.py` |
| **AP-23** — Note complexity ceiling — nota demasiado larga | audit | `framework` | — |
| **AP-24** — Bracket imbalance — corchetes sin pareja, anidados o invertidos | guard+audit | — | `test_norms_coherence.py`, `test_vault_norms.py` |
| **AP-25** — Mermaid diagram syntax errors — nodos/tipos no definidos | audit | — | `test_cobertura_de_secciones.py`, `test_mermaid_flowchart_parser.py`, `test_skills_catalogo.py`, `test_skills_contract.py`, `test_vault_norms.py`, `test_vault_sdd_init.py` |
| **AP-26** — Missing tags — nota de contenido sin tags | audit | — | `test_context_memory.py`, `test_registry_derivation.py`, `test_tag_vocabulary.py` |
| **AP-27** — Missing type field — nota sin tipo declarado | audit | — | — |
| **AP-28** — Missing frontmatter — nota sin bloque YAML | audit | — | `test_ap56_frontmatter_heal.py` |
| **AP-29** — Missing status field — nota sin estado de ciclo de vida | audit | `framework` | — |
| **AP-30** — Missing CIA classification — nota sin clasificación de la tríada | audit | — | `test_registry_derivation.py` |
| **AP-31** — Grafo sin tipos semanticos — edges sin predicate explícito | audit | — | — |
| **AP-32** — Relaciones tipadas sin predicate valido en la ontologia | audit | — | — |
| **AP-33** — Predicado no canonico — sinonimo no normalizado | audit | — | — |
| **AP-34** — Relacion tipada huerfana — endpoint inexistente en el vault | audit | — | — |
| **AP-35** — Silos de relacion — sistemas de grafos aislados | audit | — | `test_cobertura_de_secciones.py`, `test_skills_catalogo.py` |
| **AP-36** — Contención e idempotencia — side-effects fuera del vault o no rastreables | guard+audit | `framework` | `test_ap44_verificacion_autoconsistente.py`, `test_ap46_heal.py`, `test_ap51_culpar_al_dato.py`, `test_arquitectura.py`, `test_audit_no_audita_instantaneas.py`, `test_backup_base64.py`, `test_ciclo_de_vida_dominio.py`, `test_consulta_dominio.py`, `test_durabilidad_caracterizacion.py`, `test_gobernanza_dominio.py`, `test_grafo_dominio.py`, `test_indice_compartido_concurrente.py`, `test_indices_dominio.py`, `test_mermaid_flowchart_parser.py`, `test_run_context.py`, `test_skills_contract.py`, `test_standard_upgrade_path.py`, `test_vault_containment.py`, `test_vault_norms_audit.py` |
| **AP-37** — No-op silencioso — ok: true sin indicador de trabajo | audit | `noop` | `test_ap46_write_path_unico.py`, `test_ap56_frontmatter_heal.py`, `test_arquitectura.py`, `test_autoria_dominio.py`, `test_caracterizacion_de_los_save.py`, `test_comandos_publicados.py`, `test_degradacion_declarada.py`, `test_durabilidad_caracterizacion.py`, `test_indice_compartido_concurrente.py`, `test_indice_no_se_regenera_dos_veces.py`, `test_indices_dominio.py`, `test_lock_reentrante.py`, `test_mcp_runner.py`, `test_meta_toolkit_dominio.py`, `test_noop_audit.py`, `test_registro_de_entorno.py`, `test_registro_de_vocabulario.py`, `test_smoke_contrato.py`, `test_source_hygiene.py`, `test_standard_upgrade_path.py`, `test_versionado_consumidores.py`, `test_voice.py`, `test_write_ledger.py`, `test_write_path_contenido.py` |
| **AP-38** — Vocabulario validado después de escribir, no antes | guard+audit | `framework` | `test_status_machine.py`, `test_status_vocabulary.py` |
| **AP-39** — Vocabulario abierto sin memoria | guard+audit | `framework` | `test_ap39_registro_en_el_write_path.py`, `test_tag_vocabulary.py` |
| **AP-40** — Contrato publicado que la CLI rechaza | guard+audit | `contratos`, `framework` | `test_catalog_params.py`, `test_smoke.py` |
| **AP-41** — Máquina de estados declarada sin verificar | guard+audit | `framework` | `test_status_machine.py`, `test_voice.py` |
| **AP-42** — Tool publicada sin haberse ejecutado nunca | guard+audit | `framework` | `test_ap49_vinculo_congelado.py`, `test_ap50_decision_duplicada.py`, `test_ap52_contrato_de_error.py`, `test_arquitectura.py`, `test_comandos_publicados.py`, `test_durabilidad_caracterizacion.py`, `test_durabilidad_dominio.py`, `test_skills_catalogo.py`, `test_smoke.py`, `test_vault_gate.py`, `test_vault_onboard.py` |
| **AP-43** — Norma sin refuerzo en el punto de uso | guard+audit | `framework` | `test_ap39_registro_en_el_write_path.py`, `test_norms_coherence.py`, `test_voice.py` |
| **AP-44** — Verificación autoconsistente — la tool se certifica a sí misma | guard+audit | `framework` | `test_ap17_convencion_de_nombres.py`, `test_ap44_verificacion_autoconsistente.py`, `test_ap45_cobertura_sin_evidencia.py`, `test_ap46_heal.py`, `test_ap46_write_path_unico.py`, `test_ap47_indice_refleja_disco.py`, `test_ap48_implementacion_paralela.py`, `test_ap49_vinculo_congelado.py`, `test_ap51_culpar_al_dato.py`, `test_ap52_contrato_de_error.py`, `test_ap56_frontmatter_heal.py`, `test_arquitectura.py`, `test_audit_placeholder_no_traga_notas_reales.py`, `test_blueprint.py`, `test_calidad_no_castiga_el_vocabulario_canonico.py`, `test_caracterizacion_de_los_save.py`, `test_changelog_check.py`, `test_cobertura_de_secciones.py`, `test_documentacion_no_es_vault.py`, `test_durabilidad_caracterizacion.py`, `test_frontmatter_yaml_valido.py`, `test_indice_compartido_concurrente.py`, `test_indices_dominio.py`, `test_lifecycle_registry.py`, `test_mcp_runner.py`, `test_migrate_docs_distribucion.py`, `test_norms_coherence.py`, `test_puertos_verificados.py`, `test_registro_de_entorno.py`, `test_registro_de_vocabulario.py`, `test_regla7_contraste_ajeno.py`, `test_slug_canonico.py`, `test_standard_upgrade_path.py`, `test_validate_criterio_consumidor.py`, `test_vault_gate.py`, `test_vault_norms_audit.py`, `test_vault_onboard.py`, `test_write_path_contenido.py` |
| **AP-45** — Cobertura sin evidencia — la nota existe para llenar la sección | guard+audit | `framework` | `test_ap45_cobertura_sin_evidencia.py`, `test_vault_onboard.py` |
| **AP-46** — Frontmatter a mano — cada tool es su propio escritor | guard+audit | `framework` | `test_ap46_heal.py`, `test_ap46_write_path_unico.py`, `test_caracterizacion_de_los_save.py`, `test_norms_coherence.py` |
| **AP-47** — Artefacto derivado desfasado — el índice dejó de reflejar el disco | guard+audit | `framework` | `test_ap39_registro_en_el_write_path.py`, `test_ap47_indice_refleja_disco.py`, `test_ap48_implementacion_paralela.py`, `test_arquitectura.py`, `test_blueprint.py`, `test_filtro_de_expresiones_regulares.py`, `test_indices_dominio.py`, `test_registro_de_entorno.py`, `test_salud_por_familias.py`, `test_skills_catalogo.py`, `test_vault_norms_audit.py`, `test_version_coherence.py` |
| **AP-48** — Implementación paralela por camino de acceso | guard+audit | `contratos`, `framework` | `test_ap48_implementacion_paralela.py`, `test_ciclo_de_vida_dominio.py`, `test_consulta_dominio.py` |
| **AP-49** — Vínculo resuelto en tiempo de import | guard+audit | `arquitectura`, `framework` | `conftest.py`, `test_ap49_vinculo_congelado.py`, `test_arquitectura.py`, `test_autoria_dominio.py`, `test_catalogo_sin_copia_local.py`, `test_ciclo_de_vida_dominio.py`, `test_consulta_dominio.py`, `test_context_memory.py`, `test_durabilidad_caracterizacion.py`, `test_durabilidad_dominio.py`, `test_gobernanza_dominio.py`, `test_grafo_dominio.py`, `test_puertos_verificados.py`, `test_registro_de_vocabulario.py`, `test_tag_vocabulary.py`, `test_vault_containment.py`, `test_vault_graph_merge.py`, `test_vault_norms_audit.py`, `test_vault_relation_add.py` |
| **AP-50** — Decisión duplicada sin dueño declarado | guard+audit | `arquitectura`, `framework` | `test_ap50_decision_duplicada.py`, `test_arquitectura.py`, `test_data_framework.py`, `test_filtro_de_expresiones_regulares.py`, `test_frontmatter_yaml_valido.py`, `test_vault_gate.py` |
| **AP-51** — La tool culpa al dato de su propio fallo | guard+audit | `blame` | `test_ap51_culpar_al_dato.py`, `test_ap52_contrato_de_error.py`, `test_filtro_de_expresiones_regulares.py`, `test_firma_de_sitio.py`, `test_regla7_contraste_ajeno.py` |
| **AP-52** — El error se emite fuera del contrato del catalogo | guard+audit | `contrato_error` | `test_ap46_heal.py`, `test_ap52_contrato_de_error.py`, `test_arquitectura.py`, `test_contrato_de_campos.py`, `test_data_framework.py`, `test_firma_de_sitio.py`, `test_ingest_tope_de_fuente.py`, `test_regla7_contraste_ajeno.py`, `test_smoke.py`, `test_vault_norms_audit.py` |
| **AP-53** — El historial se afirma a mano y nadie lo contrasta con git | guard | `changelog` | `test_changelog_check.py` |
| **AP-54** — El lock falla y se escribe igual | guard | `arquitectura` | `test_lock_reentrante.py` |
| **AP-55** — El catálogo de normas se certifica a sí mismo | guard+audit | `norms_coherence` | `test_blueprint.py`, `test_norms_coherence.py` |
| **AP-56** — Frontmatter presente que el consumidor no puede leer | guard+audit | — | `test_ap56_frontmatter_heal.py` |
| **PAT-6** — Semantic graph enrichment — enriquecimiento periodico del grafo | recommended | — | — |
| **SP-01** — Delete protocol — change_log obligatorio antes de eliminar | audit | `framework` | `test_vault_norms.py` |
| **SP-02** — Forward-link verification — buscar antes de linkar | guard | — | `test_vault_norms.py` |
| **SP-03** — Session snapshot pattern — delta antes de operaciones masivas | audit | — | `test_vault_norms.py` |
| **CN-01** — Kebab-case filenames — nombres de archivo en minúsculas con guiones | guard | — | `test_vault_norms.py` |
| **CN-02** — Numbered folder structure — secciones numeradas como únicos destinos | guard+audit | `framework` | `test_blueprint.py`, `test_indices_dominio.py`, `test_raiz_no_seccion.py`, `test_vault_norms.py`, `test_vault_norms_audit.py` |
| **CN-03** — Standard status vocabulary — vocabulario canónico de meta.status | audit | `framework` | `test_status_machine.py`, `test_status_vocabulary.py`, `test_vault_norms.py`, `test_vault_norms_audit.py` |

Sin puerta ni test (14): `AP-08`, `AP-12`, `AP-13`, `AP-18`, `AP-20`, `PAT-2`, `PAT-3`, `PAT-4`, `AP-27`, `AP-31`, `AP-32`, `AP-33`, `AP-34`, `PAT-6`.

## Capa 5 — Tools → grupos → contrato

*Registros: `vault_mcp_catalog.TOOLS_CATALOG` + `<vault>/00_System/tool-spec.json`*

101 tools activas en 37 grupos. Toda tool
del catálogo tiene entrada de contrato y toda entrada sin catálogo declara
`status: archived | internal | orphan` — no se borra, se anota
(`vault_mcp_catalog.py --check-contracts`).

| Grupo | Tools |
|---|---|
| Backups | 5 |
| Bibliografía | 1 |
| Bootstrap | 2 |
| Change Log | 1 |
| Conocimiento | 2 |
| Core | 8 |
| Corrección Automática | 3 |
| Código | 5 |
| Data Quality | 2 |
| Defectos y Cuarentena | 2 |
| Diagramas | 4 |
| Drift Detection | 1 |
| Flujos | 1 |
| Gestión de Carpetas | 1 |
| IA Governance | 1 |
| Infraestructura | 4 |
| Línea de Tiempo | 1 |
| Memoria de Contexto | 5 |
| Migración | 2 |
| Normas | 16 |
| Observabilidad | 1 |
| Patrones | 2 |
| Producción/SRE | 2 |
| Propagación | 2 |
| Release | 1 |
| Requerimientos | 1 |
| Riesgos/Calidad | 3 |
| Runbooks | 2 |
| Salud del Vault | 5 |
| Seguridad | 1 |
| Session Delta y Tags | 2 |
| Skills | 2 |
| Tests | 1 |
| Tokens | 3 |
| Versionado | 1 |
| Vista del Proyecto | 2 |
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
| `vault_code_map` | 12 — Código | escritura_a_gobernanza |
| `vault_code_module` | 12 — Código | escritura_a_gobernanza |
| `vault_code_query` | 12 — Código | escritura_a_gobernanza |
| `vault_code_relation` | 12 — Código | escritura_a_gobernanza |
| `vault_code_sync` | 12 — Código | escritura_a_gobernanza |
| `vault_code_tag` | 35 — Normas | gobernanza_del_estandar |
| `vault_context_pack` | 34 — Memoria de Contexto | consulta_a_contexto |
| `vault_delta` | 27 — Session Delta y Tags | escritura_a_gobernanza |
| `vault_diagram_export` | 4 — Diagramas | escritura_a_gobernanza |
| `vault_diagram_save` | 4 — Diagramas | escritura_a_gobernanza |
| `vault_diff` | 1 — Core | escritura_a_gobernanza |
| `vault_doc_counts` | 35 — Normas | gobernanza_del_estandar |
| `vault_doc_sync` | 35 — Normas | gobernanza_del_estandar |
| `vault_drift_detect` | 17 — Drift Detection | escritura_a_gobernanza |
| `vault_env_matrix` | 8 — Infraestructura | escritura_a_gobernanza |
| `vault_env_save` | 8 — Infraestructura | escritura_a_gobernanza |
| `vault_error_contract` | 35 — Normas | gobernanza_del_estandar |
| `vault_fix_brackets` | 33 — Corrección Automática | escritura_a_gobernanza |
| `vault_flow_save` | 18 — Flujos | escritura_a_gobernanza |
| `vault_folder_registry` | 32 — Gestión de Carpetas | escritura_a_gobernanza |
| `vault_foreign_check` | 35 — Normas | gobernanza_del_estandar |
| `vault_frontmatter_heal` | 33 — Corrección Automática | escritura_a_gobernanza |
| `vault_fundamentals` | 24 — Data Quality | escritura_a_gobernanza |
| `vault_gate` | 35 — Normas | gobernanza_del_estandar |
| `vault_graph` | 6 — Salud del Vault | escritura_a_gobernanza |
| `vault_graph_fix` | 33 — Corrección Automática | escritura_a_gobernanza |
| `vault_graph_inspect` | 6 — Salud del Vault | escritura_a_gobernanza |
| `vault_graph_merge` | 6 — Salud del Vault | escritura_a_gobernanza |
| `vault_impact` | 25 — Propagación | escritura_a_gobernanza |
| `vault_incident_save` | 28 — Producción/SRE | escritura_a_gobernanza |
| `vault_infra_map` | 8 — Infraestructura | escritura_a_gobernanza |
| `vault_infra_save` | 8 — Infraestructura | escritura_a_gobernanza |
| `vault_ingest` | 34 — Memoria de Contexto | consulta_a_contexto |
| `vault_init` | 31 — Bootstrap | escritura_a_gobernanza |
| `vault_knowledge_get` | 5 — Conocimiento | escritura_a_gobernanza |
| `vault_knowledge_save` | 5 — Conocimiento | escritura_a_gobernanza |
| `vault_list` | 1 — Core | escritura_a_gobernanza |
| `vault_log_error` | 2 — Observabilidad | escritura_a_gobernanza |
| `vault_master_index` | 15 — Índices | escritura_a_gobernanza |
| `vault_merge` | 1 — Core | escritura_a_gobernanza |
| `vault_mermaid_check` | 4 — Diagramas | escritura_a_gobernanza |
| `vault_migrate_docs` | 9 — Migración | escritura_a_gobernanza |
| `vault_migrate_rollback` | 9 — Migración | escritura_a_gobernanza |
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
| `vault_project_overview` | 11 — Vista del Proyecto | escritura_a_gobernanza |
| `vault_project_status` | 11 — Vista del Proyecto | escritura_a_gobernanza |
| `vault_propagate` | 25 — Propagación | escritura_a_gobernanza |
| `vault_quality_check` | 24 — Data Quality | escritura_a_gobernanza |
| `vault_quarantine` | 36 — Defectos y Cuarentena | escritura_a_gobernanza |
| `vault_query_parse` | 34 — Memoria de Contexto | consulta_a_contexto |
| `vault_read` | 1 — Core | escritura_a_gobernanza |
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
| `vault_section_index` | 15 — Índices | escritura_a_gobernanza |
| `vault_security_scan` | 14 — Seguridad | escritura_a_gobernanza |
| `vault_servicio` | 35 — Normas | gobernanza_del_estandar |
| `vault_slo_save` | 28 — Producción/SRE | escritura_a_gobernanza |
| `vault_smoke` | 35 — Normas | gobernanza_del_estandar |
| `vault_standard_upgrade` | 22 — Versionado | escritura_a_gobernanza |
| `vault_subgraph` | 34 — Memoria de Contexto | consulta_a_contexto |
| `vault_tags` | 27 — Session Delta y Tags | escritura_a_gobernanza |
| `vault_test_save` | 20 — Tests | escritura_a_gobernanza |
| `vault_timeline` | 10 — Línea de Tiempo | escritura_a_gobernanza |
| `vault_token_counter` | 26 — Tokens | consulta_a_contexto |
| `vault_token_service` | 26 — Tokens | consulta_a_contexto |
| `vault_tokens` | 26 — Tokens | consulta_a_contexto |
| `vault_validate` | 6 — Salud del Vault | escritura_a_gobernanza |
| `vault_voice` | 35 — Normas | gobernanza_del_estandar |
| `vault_write` | 1 — Core | escritura_a_gobernanza |

## Capa 7 — Deuda viva

*Registro: `vault_blueprint.DEUDA_DECLARADA` + las baselines de `scripts/`*

Deuda **declarada**: conocida, medida y con motivo escrito de por qué no se ataca
todavía. Lo que no está aquí no es que no exista — es que nadie lo ha medido, que
es una situación distinta y peor.

**7 pendientes** de 7 declaradas. Una deuda saldada no
desaparece de la tabla: se queda con `estado: saldada` y la versión que la cerró,
porque una entrada borrada no se distingue de una que nadie volvió a mirar.

| Deuda | Estado | Desde | Capa | Qué | Por qué no ahora |
|---|---|---|---|---|---|
| `envelopes_del_dominio_sin_error_code` | pendiente | v40.9 | 5 | Nueve `{"ok": False, "error": ...}` en `vault/durabilidad/` y `vault/indices/` que los adaptadores de `scripts/` devuelven tal cual al consumidor: el envelope sale sin `error_code` ni `recovery`. Aparecieron en v40.9 al ensanchar el alcance de AP-52 más allá de `scripts/`, y quedan congelados en `error-contract-baseline.json`. | La pregunta de fondo no es cómo se escribe el envelope sino quién lo escribe: hacer que el dominio importe `vault_errors` lo ata al catálogo de la herramienta, y convertirlo en el adaptador exige decidir qué devuelve el dominio en su lugar. Es una decisión de capas, no un reemplazo de literales. |
| `handler_amplio_en_el_registro_de_la_cli` | pendiente | v40.9 | 5 | `cli/registry.py::_load_spec` responde a un `except Exception` con un vacío indistinguible: un `tool-spec.json` ilegible se presenta como un catálogo sin entradas (AP-51). Destapado por el mismo ensanche de alcance de v40.9 y congelado en `blame-baseline.json`. | Distinguir «no hay spec» de «la spec no se pudo leer» cambia lo que `cli doctor` reporta, y esa salida ya la consumen los repos consumidores. Se toca con su propio test de contrato. |
| `normas_criticas_sin_detector` | pendiente | v40.11 | 4 | Cinco normas no las mide nadie y desde v40.11 lo declaran por escrito en `cobertura_descubierta`: AP-01, AP-02, AP-04, AP-08 y —el titular— **AP-05, la única `critical` descubierta**. Diecisiete módulos citan AP-05 en un comentario, al explicar por qué NO copian un dato, y citar no es detectar: nada mide hoy que el mismo dato aparezca con valores distintos en varias notas. AP-02 es la variante same-folder, cuyas dos hermanas —AP-17 y AP-18— sí pesan en el healthIndex. | Detectar AP-05 sobre markdown plano, sin embeddings y sin base de datos, es un problema de diseño abierto, no una tool que falte escribir: la restricción que lo hace difícil es la misma decisión de producto que sostiene el estándar. Merece su propia tanda. Lo que v40.11 sí cierra es lo que era falso: la contradicción del catálogo (v40.10, AP-55), las 47 afirmaciones de cobertura sin traza, y el `vault_voice.coverage()` que certificaba el catálogo contra sí mismo. |
| `fronteras_de_escritura_por_contexto` | pendiente | v40.9 | 3 | Ningún guard dice qué contexto puede escribir dónde. `00_System` lo escriben hoy seis contextos. | Exige antes sanear `_LLAMADAS_DE_ESCRITURA` —incluye `replace`, que captura `str.replace`, y `write_report`, que no escribe— y una decisión de diseño que nadie ha tomado: de quién es `00_System`. |
| `recursion_error_en_parsers` | pendiente | v40.9 | 5 | `RecursionError` escapa a `except yaml.YAMLError` en 4 parsers: no es subclase. Reproducido a 400 corchetes anidados. El peor caso es `vault_foreign_check`, que es la tool de la regla 7. | Es un arreglo de robustez con su propia norma candidata; entra en la tanda donde se unifiquen los parsers, no en una de alcance. |
| `parsers_de_frontmatter_divergentes` | pendiente | v40.9 | 5 | 8 parsers de frontmatter distintos; `vault_write.slugify` no delega en `vault_lib` aunque 20 módulos sí; 6 aliases de v40.8 con el nombre viejo aún en uso; `--agent default="claude"` en 6 tools frente al AP-16 que `vault_bug_save` exige. | Es AP-50 acumulado y se salda unificando, no parcheando: hacerlo a medias deja nueve parsers en vez de ocho. |
| `catch_vacios_en_el_servidor_mjs` | pendiente | v40.9 | 7 | 11 `catch (_) {}` en `mcp/nodejs/vault-mcp-server.mjs` (AP-51 en JS). | Los tres audits con baseline miden AST de Python. Un detector de JavaScript es otro proyecto, y fingir que el alcance lo cubre sería el mismo cero sobre un subconjunto que esta versión vino a cerrar. |

| Baseline | Norma | Congelado |
|---|---|---|
| `scripts/arch-baseline.json` | cruces entre contextos | 61 |
| `scripts/arch-baseline.json` | cruces fuera de puerto | 13 |
| `scripts/blame-baseline.json` | AP-51 | 87 |
| `scripts/error-contract-baseline.json` | AP-52 | 9 |
| `scripts/noop-baseline.json` | AP-37 | 0 |
| `scripts/smoke-baseline.json` | AP-42 | 0 |
| `scripts/blueprint-baseline.json` | capa 4 — norma sin puerta ni test | 14 |

Todas encogen y ninguna crece sin decirlo: los tres audits con baseline indexan
por firma de sitio —`módulo::función::hash de `ast.unparse``— así que mover un
sitio ya no lo estrena como deuda nueva, y `--freeze` se niega a congelar lo que
no tiene precedente salvo con `--admitir-nuevos`, que además lo lista.

---

*14 puertas de cierre. Generado por `scripts/vault_blueprint.py`.*
