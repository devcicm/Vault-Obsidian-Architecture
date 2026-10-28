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
| **Gobernanza del estándar** (`gobernanza_del_estandar`) | El estándar cumple lo que publica: registro canónico primero, doc derivada, guard que falla si divergen. Ninguna de estas tools toca las notas de un usuario. | 35 | 29 |

- **`consulta_a_contexto`** — El grupo 26 (Tokens) cae en el rango 1–33 que `AGENTS.md` atribuye al primer eje, pero sus tres tools viven en el contexto `consulta` y existen para que el paquete quepa en la ventana. El rango es cronológico, no clasificatorio.
- **`gobernanza_del_estandar`** — Tercera capacidad que `AGENTS.md` no nombraba. Existía desde que se escribió la primera puerta; declararla es lo que impide que sus tools se cuenten como si sirvieran a la memoria del agente.

Guard: todo grupo del catálogo pertenece a exactamente una capacidad y toda
capacidad tiene al menos una tool viva (`vault_servicio.py --check --strict`).

## Capa 3 — Contextos acotados → puertos

*Registro: `vault_arch.CONTEXTS`. El detalle de puertos y cruces vive en
[`docs/ARQUITECTURA.md`](./ARQUITECTURA.md), que no se absorbe aquí: son dos
documentos con dos sujetos, y fundirlos habría hecho un solo documento que nadie
regenera.*

| Contexto | Puertos | Módulos | Sin hogar | Prohíbe |
|---|---|---|---|
| **Kernel** (`kernel`) | 4 | 23 | 1 | depender de cualquier contexto de dominio |
| **Autoría** (`autoria`) | 7 | 46 | 0 | — |
| **Grafo** (`grafo`) | 4 | 15 | 0 | — |
| **Gobernanza** (`gobernanza`) | 21 | 13 | 0 | — |
| **Índices** (`indices`) | 12 | 7 | 0 | — |
| **Consulta** (`consulta`) | 7 | 11 | 0 | base de datos; embeddings; servicio externo |
| **Ciclo de vida** (`ciclo_de_vida`) | 3 | 10 | 0 | — |
| **Durabilidad** (`durabilidad`) | 4 | 4 | 0 | escribir fuera de la raíz del vault (AP-36) |
| **Meta-toolkit** (`meta_toolkit`) | 6 | 39 | 1 | escribir en una sección de contenido: sus artefactos derivados viven en 00_System/ |
| **CLI** (`cli`) | 0 | 8 | 0 | decidir: traduce argumentos a llamadas y envelopes a salida; la decisión vive en la tool |

**Puente de ADR-0002:** 2 módulos de `scripts/` no importan nada de `vault/<su contexto>/` (`vault_arch.modulos_sin_hogar`). La cifra solo encoge: un módulo nuevo sin hogar bloquea `vault_arch --check`. Importar del contexto es empezar a delegar, no haber migrado.

## Capa 4 — Normas → puertas → tests

*Registros: `vault_norms.NORM_CATALOG` + `vault_gate.PUERTAS` + `tests/`*

82 de 83 normas tienen puerta o test que las nombre.
**Es la única capa con baseline**, y por un motivo concreto: las demás se midieron
en cero el día que se declararon porque sus datos ya existían y solo faltaba
atarlos. Ésta no. Exigir cero aquí el primer día habría hecho nacer la puerta en
rojo, y una puerta en rojo se desactiva.

| Norma | Enforcement | Puertas | Tests |
|---|---|---|---|
| **AP-01** — Documentación alucinada | audit | — | `test_ap01_codigo_inexistente.py`, `test_ap01_prosa.py`, `test_ap40_42_43_estados.py`, `test_ap46_editores.py`, `test_norms_coherence.py`, `test_skills_catalogo.py`, `test_skills_contract.py` |
| **AP-02** — Proliferación de versiones del mismo documento | audit | — | `test_ap02_versiones_misma_carpeta.py`, `test_norms_coherence.py`, `test_skills_contract.py` |
| **AP-03** — Stubs sin política de expansión | audit | — | `test_normas_de_audit_ejercitadas.py`, `test_pat2_stub_con_plazo.py` |
| **AP-04** — Features aspiracionales documentadas como implementadas | audit | — | — |
| **AP-05** — Múltiples fuentes de verdad para el mismo dato | audit | `fuente_unica` | `test_ap05_fuente_unica.py`, `test_ap46_editores.py`, `test_blueprint.py`, `test_js_native_frontera.py`, `test_norms_coherence.py` |
| **AP-06** — Templates sin instancias reales | audit | `framework` | — |
| **AP-07** — ADRs incompletos | audit | `framework` | `test_ap07_criterio_adr.py`, `test_ap64_responsable.py`, `test_vault_norms_audit.py` |
| **AP-08** — Documentación anclada a versiones obsoletas | audit | — | `test_ap08_version_pinned.py`, `test_ap08_vigencia.py` |
| **AP-09** — Runbooks fuera de estructura | audit | `framework` | `test_vault_norms_audit.py` |
| **AP-10** — Migración sin plan de rollback | audit | `framework` | `test_norms_coherence.py` |
| **AP-11** — Skeleton files — frontmatter válido, contenido vacío | guard | `framework` | `test_envelope_forma.py`, `test_voice.py` |
| **AP-12** — Frontmatter inconsistente entre notas del mismo tipo | audit | — | `test_capa4_audit_ejercitada.py` |
| **AP-13** — Timestamps inválidos o incompletos en frontmatter | audit | — | `test_meta_contrato.py` |
| **AP-14** — Wiki-links rotos o vacíos | guard+audit | — | `test_audit_acciones_de_movimiento.py`, `test_normas_caras.py`, `test_normas_enlaces_sin_solape.py`, `test_norms_coherence.py` |
| **AP-15** — Archivos externos depositados en la raíz del vault | guard+audit | `framework` | `test_normas_sin_registro_a_mano.py`, `test_vault_norms_audit.py` |
| **AP-16** — Sin identificador de agente en frontmatter | audit | — | `test_ap16_prevencion_dice_lo_que_hace.py`, `test_ap64_responsable.py`, `test_context_memory.py` |
| **AP-17** — Canonical-shadow duplication | audit | — | `test_blueprint.py`, `test_normas_caras.py`, `test_normas_de_audit_ejercitadas.py` |
| **AP-18** — Cross-folder content duplication | audit | — | `test_capa4_audit_ejercitada.py` |
| **AP-19** — Shadow indexing | audit | `framework` | — |
| **AP-20** — Deceptive skeleton (empty-list) | guard | — | `test_ap20_esqueleto_de_lista.py` |
| **AP-21** — Path-anchored wiki-links | guard+audit | — | `test_ap21_dentro_de_fence.py`, `test_ap21_ruta_necesaria.py`, `test_normas_caras.py`, `test_normas_enlaces_sin_solape.py`, `test_vault_regex.py` |
| **AP-22** — Wiki-link vacío — [[]] sin destino | guard+audit | — | `test_normas_caras.py`, `test_normas_enlaces_sin_solape.py`, `test_norms_coherence.py`, `test_vault_regex.py` |
| **PAT-1** — Canonical source anchoring | recommended | — | `test_norms_coherence.py` |
| **PAT-2** — Stub enrichment gradient | recommended | — | `test_pat2_stub_con_plazo.py` |
| **PAT-3** — Duplicate chain resolution | recommended | — | `test_capa4_audit_ejercitada.py` |
| **PAT-4** — Phased audit execution | recommended | — | `test_capa4_audit_ejercitada.py` |
| **PAT-5** — Frontmatter as provenance chain | recommended | — | `test_context_memory.py` |
| **AP-23** — Note complexity ceiling — nota demasiado larga | audit | `framework` | — |
| **AP-24** — Bracket imbalance — corchetes sin pareja, anidados o invertidos | guard+audit | — | `test_normas_caras.py`, `test_norms_coherence.py`, `test_vault_norms.py` |
| **AP-25** — Mermaid diagram syntax errors — nodos/tipos no definidos | audit | — | `test_manifiesto_pasa_ap25.py`, `test_mermaid_sanacion.py`, `test_skills_catalogo.py`, `test_vault_norms.py` |
| **AP-26** — Missing tags — nota de contenido sin tags | guard+audit | — | `test_context_memory.py` |
| **AP-27** — Missing type field — nota sin tipo declarado | guard+audit | — | `test_capa4_audit_ejercitada.py` |
| **AP-28** — Missing frontmatter — nota sin bloque YAML | audit | — | `test_ap56_frontmatter_heal.py` |
| **AP-29** — Missing status field — nota sin estado de ciclo de vida | audit | — | `test_contrato_sin_seccion.py` |
| **AP-30** — Missing CIA classification — nota sin clasificación de la tríada | audit | — | `test_normas_de_audit_ejercitadas.py` |
| **AP-31** — Grafo sin tipos semanticos — edges sin predicate explícito | audit | — | `test_capa4_audit_ejercitada.py` |
| **AP-32** — Relaciones tipadas sin predicate valido en la ontologia | audit | — | `test_graph_merge_sugerencias.py` |
| **AP-33** — Predicado no canonico — sinonimo no normalizado | audit | — | `test_graph_merge_sugerencias.py` |
| **AP-34** — Relacion tipada huerfana — endpoint inexistente en el vault | audit | — | `test_graph_merge_sugerencias.py` |
| **AP-35** — Silos de relacion — sistemas de grafos aislados | audit | — | `test_skills_catalogo.py` |
| **AP-36** — Contención e idempotencia — side-effects fuera del vault o no rastreables | guard+audit | `framework` | `test_ap46_heal.py`, `test_arquitectura.py`, `test_ciclo_de_vida_dominio.py`, `test_consulta_dominio.py`, `test_gobernanza_dominio.py`, `test_grafo_dominio.py`, `test_indices_dominio.py`, `test_mcp_http_seguridad.py`, `test_politica_certificacion_compuesta.py`, `test_skills_contract.py`, `test_vault_containment.py`, `test_vault_norms_audit.py` |
| **AP-37** — No-op silencioso — ok: true sin indicador de trabajo | audit | `noop` | `test_noop_audit.py`, `test_norms_coherence.py`, `test_vault_gate.py`, `test_voice.py` |
| **AP-38** — Vocabulario validado después de escribir, no antes | guard+audit | `framework` | `test_status_vocabulary.py` |
| **AP-39** — Vocabulario abierto sin memoria | guard+audit | `framework` | `test_ap39_registro_en_el_write_path.py`, `test_politica_certificacion_compuesta.py`, `test_tag_vocabulary.py`, `test_vault_init.py` |
| **AP-40** — Contrato publicado que la CLI rechaza | guard+audit | `contratos`, `framework` | `test_ap40_42_43_estados.py`, `test_catalog_params.py`, `test_fase2_paridad_fail_closed.py`, `test_puerto_controles.py` |
| **AP-41** — Máquina de estados declarada sin verificar | guard+audit | `framework` | `test_status_machine.py`, `test_voice.py` |
| **AP-42** — Tool publicada sin haberse ejecutado nunca | guard+audit | `framework` | `test_ap40_42_43_estados.py`, `test_fase2_politica_qg.py`, `test_politica_certificacion_compuesta.py`, `test_puerto_controles.py`, `test_smoke.py`, `test_vault_norms_audit.py`, `test_vault_toolkit_audit.py` |
| **AP-43** — Norma sin refuerzo en el punto de uso | guard+audit | `framework` | `test_ap39_registro_en_el_write_path.py`, `test_ap40_42_43_estados.py`, `test_puerto_controles.py`, `test_vault_norms_audit.py`, `test_voice.py` |
| **AP-44** — Verificación autoconsistente — la tool se certifica a sí misma | guard+audit | `framework` | `test_ap44_verificacion_autoconsistente.py`, `test_kernel.py`, `test_norms_coherence.py`, `test_procesos_git.py`, `test_puente_sin_hogar.py` |
| **AP-45** — Cobertura sin evidencia — la nota existe para llenar la sección | guard+audit | `framework` | `test_ap45_cobertura_sin_evidencia.py` |
| **AP-46** — Frontmatter a mano — cada tool es su propio escritor | guard+audit | `framework` | `test_ap46_escritores_migrados.py`, `test_ap46_interpolacion_cruda.py`, `test_ap46_write_path_unico.py`, `test_norms_coherence.py`, `test_vault_sanacion.py` |
| **AP-47** — Artefacto derivado desfasado — el índice dejó de reflejar el disco | guard+audit | `framework` | `test_ap47_indice_refleja_disco.py`, `test_audit_acciones_de_movimiento.py`, `test_delete_no_borra_derivados.py`, `test_grafo_refresco.py`, `test_sanadores_sin_lote.py` |
| **AP-48** — Implementación paralela por camino de acceso | guard+audit | `contratos` | `test_ap48_implementacion_paralela.py`, `test_voice.py` |
| **AP-49** — Vínculo resuelto en tiempo de import | guard+audit | `arquitectura` | `test_arquitectura.py`, `test_durabilidad_dominio.py` |
| **AP-50** — Decisión duplicada sin dueño declarado | guard+audit | `arquitectura` | `test_ap57_criterios.py`, `test_norms_coherence.py` |
| **AP-51** — La tool culpa al dato de su propio fallo | guard+audit | `blame` | `test_ap51_culpar_al_dato.py`, `test_baseline.py` |
| **AP-52** — El error se emite fuera del contrato del catalogo | guard+audit | `contrato_error` | `test_ap52_contrato_de_error.py`, `test_regla7_contraste_ajeno.py` |
| **AP-53** — El historial se afirma a mano y nadie lo contrasta con git | guard | `changelog` | `test_changelog_check.py` |
| **AP-54** — El lock falla y se escribe igual | guard | `arquitectura` | `test_lock_reentrante.py` |
| **AP-55** — El catálogo de normas se certifica a sí mismo | guard+audit | `norms_coherence` | `test_norms_coherence.py` |
| **AP-56** — Frontmatter presente que el consumidor no puede leer | guard+audit | — | `test_ap56_frontmatter_heal.py`, `test_disparos_de_revision.py` |
| **AP-57** — Criterio con dueño, reimplementado en la medida | guard | `criterios` | `test_ap57_criterios.py`, `test_criterios_fronteras.py`, `test_grafo_import.py` |
| **AP-58** — Ciclo esquivado con un import diferido | guard | `ciclos` | `test_ciclos.py` |
| **AP-59** — Núcleo declarado sin contraste | guard+audit | `kernel` | `test_kernel.py` |
| **AP-60** — El guard cobra por declarar y regala el silencio | guard+audit | `norms_coherence` | `test_ap08_prosa_universo.py`, `test_noop_audit.py`, `test_norms_coherence.py` |
| **AP-61** — El guard cae con el dato que vino a medir | guard+audit | `excepcion_declarada` | `test_excepcion_declarada.py` |
| **AP-62** — El consumidor paga el fan-out del productor | guard+audit | `recursos` | `test_recursos.py` |
| **AP-63** — El nombre de un proyecto como texto libre | guard+audit | — | `test_project_registrado.py`, `test_vault_project.py` |
| **AP-64** — Decisión cerrada sin responsable | audit | `framework` | `test_ap64_responsable.py`, `test_iso42005_impacto.py`, `test_normas_paquete.py`, `test_norms_coherence.py` |
| **AP-65** — Decisión de IA de impacto alto sin evaluación de impacto | audit | `framework` | `test_iso42005_impacto.py`, `test_normas_caras.py`, `test_normas_paquete.py` |
| **AP-66** — El coste crece con lo que no es trabajo | guard | `arquitectura` | — |
| **AP-67** — El material que el agente opera, sin nota que lo apunte | guard+audit | — | `test_ap67_conocimiento_del_material.py` |
| **AP-68** — El git que ejecuta el toolkit, sin dueño | guard | `procesos_git` | `test_procesos_git.py` |
| **PAT-6** — Semantic graph enrichment — enriquecimiento periodico del grafo | recommended | — | `test_capa4_audit_ejercitada.py` |
| **SP-01** — Delete protocol — change_log obligatorio antes de eliminar | audit | `framework` | `test_mermaid_reglas_parsers.py`, `test_vault_norms.py` |
| **SP-02** — Forward-link verification — buscar antes de linkar | guard | — | `test_normas_enlaces_sin_solape.py`, `test_vault_norms.py` |
| **SP-03** — Session snapshot pattern — delta antes de operaciones masivas | audit | — | `test_vault_norms.py` |
| **SP-04** — Sesión MCP por HTTP sin credencial — cualquier proceso local la abre | guard | `produccion` | `test_mcp_http_seguridad.py`, `test_token_service_seguridad.py` |
| **CN-01** — Kebab-case filenames — nombres de archivo en minúsculas con guiones | guard | — | `test_ap46_escritores_migrados.py`, `test_cn01_cn04_audit_informativo.py`, `test_cn04_escritores_con_titulo.py`, `test_meta_contrato.py`, `test_vault_norms.py` |
| **CN-02** — Numbered folder structure — secciones numeradas como únicos destinos | guard+audit | `framework` | `test_blueprint.py`, `test_fix_brackets_ruta.py`, `test_raiz_no_seccion.py`, `test_vault_norms.py`, `test_vault_norms_audit.py` |
| **CN-03** — Standard status vocabulary — vocabulario canónico de meta.status | audit | `framework` | `test_calidad_no_castiga_el_vocabulario_canonico.py`, `test_norms_coherence.py`, `test_vault_norms.py`, `test_vault_norms_audit.py`, `test_vault_sanacion.py` |
| **CN-04** — Note opens with its title — la nota abre con su título como H1 | guard | — | `test_cn01_cn04_audit_informativo.py`, `test_cn04_escritores_con_titulo.py`, `test_cn04_nota_abre_con_titulo.py` |
| **CN-05** — One body, one owner — un cuerpo, un dueño | guard | `clones` | — |

Sin puerta ni test (1): `AP-04`.

## Capa 5 — Tools → grupos → contrato

*Registros: `vault_mcp_catalog.TOOLS_CATALOG` + `<vault>/00_System/tool-spec.json`*

127 tools activas en 37 grupos. Toda tool
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
| Normas | 29 |
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
| `vault_clones` | 35 — Normas | gobernanza_del_estandar |
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
| `vault_metricas` | 35 — Normas | gobernanza_del_estandar |
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
| `vault_procesos_git` | 35 — Normas | gobernanza_del_estandar |
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
| `vault_toolkit_audit` | 35 — Normas | gobernanza_del_estandar |
| `vault_undo` | 22 — Versionado | escritura_a_gobernanza |
| `vault_validate` | 6 — Salud del Vault | escritura_a_gobernanza |
| `vault_voice` | 35 — Normas | gobernanza_del_estandar |
| `vault_write` | 1 — Core | escritura_a_gobernanza |

## Capa 7 — Deuda viva

*Registro: `vault_blueprint.DEUDA_DECLARADA` + las baselines de `scripts/`*

Deuda **declarada**: conocida, medida y con motivo escrito de por qué no se ataca
todavía. Lo que no está aquí no es que no exista — es que nadie lo ha medido, que
es una situación distinta y peor.

**0 pendientes** de 26 declaradas. Una deuda saldada no
desaparece de la tabla: se queda con `estado: saldada` y la versión que la cerró,
porque una entrada borrada no se distingue de una que nadie volvió a mirar.

| Deuda | Estado | Desde | Capa | Qué | Por qué no ahora |
|---|---|---|---|---|---|
| `barrido_del_toolkit_con_deuda_congelada` | saldada en v41.14 | v41.12 | 4 | La primera corrida del barrido del catálogo (v41.12) dejó un DEFECTO congelado: `vault_changelog_check`. No era un defecto de la tool, era **la línea de release en curso**: el changelog publicaba `git: pending` de una versión que todavía no era la vigente, y el check trata eso como error hasta que `--fijar-hash` la cierra. Congelarlo era medir el momento del release, no la tool — y una baseline que congela el reloj no congela un defecto. Con la entrada escrita (la versión en curso es v41.14) el veredicto pasó a OK: `scripts/toolkit-audit-baseline.json` queda **vacía por primera vez**, con 122 OK y 3 NO-VERIFICABLE sobre 125 tools. El motivo se conserva porque es el que reaparece: barrer el catálogo dentro de la ventana de release vuelve a medir la línea en curso. | No es una deuda viva: está saldada, y lo que se guarda es la explicación de por qué apareció —una tool se declara DEFECTO por estar en plena línea de release—, no la obligación de arreglarla. |
| `envelopes_del_dominio_sin_error_code` | saldada en v40.29 | v40.9 | 5 | Nueve `{"ok": False, "error": ...}` en `vault/durabilidad/` y `vault/indices/` que los adaptadores de `scripts/` devuelven tal cual al consumidor: el envelope sale sin `error_code` ni `recovery`. Aparecieron en v40.9 al ensanchar el alcance de AP-52 más allá de `scripts/`, y quedan congelados en `error-contract-baseline.json`. v40.29 los saldó partiendo la frase en dos mitades con dueño: el dominio levanta un `FalloDeDominio` que nombra la **causa** (`vault/kernel/fallos.py`, sin un solo import fuera de `typing`) y la traducción a `error_code` vive en un único sitio del lado de la herramienta, `vault_errors.emit_fallo`. Se levanta en vez de devolver porque un fallo devuelto como valor se ignora por olvido, y uno de los cuatro casos es el borrado del vault sin confirmar. La baseline de AP-52 queda **vacía por primera vez desde que la norma existe**, y los campos que el contrato declara estables —`error`, `hint`, `searched`— siguen saliendo: mejorar el envelope por debajo no autoriza a romper el contrato de arriba. | La pregunta de fondo no es cómo se escribe el envelope sino quién lo escribe: hacer que el dominio importe `vault_errors` lo ata al catálogo de la herramienta, y convertirlo en el adaptador exige decidir qué devuelve el dominio en su lugar. Es una decisión de capas, no un reemplazo de literales. |
| `handler_amplio_en_el_registro_de_la_cli` | saldada en v40.23 | v40.9 | 5 | `cli/registry.py::_load_spec` responde a un `except Exception` con un vacío indistinguible: un `tool-spec.json` ilegible se presenta como un catálogo sin entradas (AP-51). Destapado por el mismo ensanche de alcance de v40.9 y congelado en `blame-baseline.json`. v40.23 (77981b5) lo cerró con `_leer_spec`, que distingue `ausente`, `ilegible` y `legible`, y `spec_status` lo expone a `cli doctor`; el registro siguió diciendo `pendiente` hasta que se midió en v41.3. | Distinguir «no hay spec» de «la spec no se pudo leer» cambia lo que `cli doctor` reporta, y esa salida ya la consumen los repos consumidores. Se toca con su propio test de contrato. |
| `normas_criticas_sin_detector` | saldada en v41.4 | v40.11 | 4 | Tres normas no las mide nadie y lo declaran por escrito en `cobertura_descubierta`: AP-01, AP-04 y AP-08. Desde v40.11 eran cuatro; AP-02, la variante same-folder cuyas hermanas AP-17 y AP-18 sí pesan en el healthIndex, pasó a `cobertura_parcial` cuando `vault_audit` empezó a medir la versión que el nombre declara (`sameFolderVersions`). **El titular de esta entrada era AP-05, la única `critical` descubierta, y salió en v40.15**: `vault_fuente_unica` (puerta 16) mide el mismo dato **tipado** —IP, URL, puerto, semver— con valores distintos en un mismo ámbito. No cerró el problema general: el catálogo la declara `cobertura_parcial`, porque la divergencia en prosa, la de valores sin tipo y la del sinónimo (`ip:` frente a `direccion_ip:`) siguen sin medirlas nadie. La entrada sigue pendiente por las otras tres, no por AP-05 ni AP-02. (Avance de v41.3: AP-08 pasó a `cobertura_parcial` con `vault_drift_detect --mode vigencia`, y AP-01 también, en el mismo modo: un `files:` que no está en el disco del repo sale en `codigo_inexistente`. Medido contra la copia de /ans: con la base buena, 0 AP-01 y 7 AP-08; con `--path` en la raíz, las 7 salían AP-01, y por eso la respuesta lleva una `pista` cuando no resuelve ninguno. Queda AP-04 entera, y de AP-01 y AP-08 la parte escrita en prosa.) (Avance de v41.3, 2026-10-09: AP-01 mide la ruta de código citada entre backticks, en `prosa_inexistente`. Regla 7 con la tool, sobre una copia de /ans y su repo en solo lectura (hash igual antes y después): en las notas del proyecto que afirman —ni `registro` ni `indice`, ni doc del estándar—, 14 notas citan una ruta ausente sin otro sitio con el mismo nombre. Las copias de los otros consumidores no traen historia de git y el modo vigencia responde `GIT_UNAVAILABLE`, así que no hay cifra suya; la muestra de /ans contrastada con el original dio código archivado o renombrado —`core/toon.py` vive en `_archive/` de /ans— junto a rutas de otro repo indistinguibles, así que informa sin entrar en `action_required`. Lo que el nombre sí encuentra en otro sitio —289 en /ans— se cuenta como base ambigua.) | AP-05 tuvo su tanda en v40.15, y lo que la desbloqueó no fue resolver el problema abierto: fue dejar de plantearlo entero. Un valor **tipado** no se reconoce por parecido, se compara por igualdad, y su identidad no se adivina —está escrita al lado, como clave de un `clave: valor`—. Eso quita la semántica de en medio y deja una parte decidible, que es la que se mide; el resto se declara en vez de darse por cubierto. Las tres que quedan siguen sin una reformulación equivalente, y ninguna es `critical`. (En v41.3 AP-08 y AP-01 la encontraron en `files:`, que la nota declara. AP-04 no: su señal decidible es la misma que la de AP-01 y el discriminador —la intención— no está en ningún campo; el motivo queda en su `cobertura_descubierta`. El 2026-10-09 se midió la última hipótesis, la historia del `status` en git, y dio señal nula en /ans; la cifra vive en esa misma `cobertura_descubierta`. La parte en prosa de AP-08 tampoco: el `version_pinned:` que la haría decidible no lo declara ninguna nota de las copias medidas, y el motivo queda en su `cobertura_parcial`.) Saldada, 2026-10-09, cerrando lo decidible y declarando el resto, como decidió el usuario: `version_pinned` entra en el contrato v41 (opcional, mapa `paquete: versión`), lo emite `vault_write --version-pinned` y `vault_drift_detect --mode vigencia` lo cruza con el manifiesto de la raíz del repo, publicando su universo aunque esté vacío (AP-60). Regla 7 sobre la copia de /ans y su repo en solo lectura: 0 notas lo declaran, y la respuesta lo dice en vez de salir verde. Lo que queda sin detector —AP-04 entera, la prosa de AP-01 que no es una ruta y la versión en prosa de AP-08 sin el campo— exige interpretar el texto, y cada norma lo declara con su cifra medida en su `cobertura_*`: ninguna queda en silencio ni es `critical`. |
| `fronteras_de_escritura_por_contexto` | saldada en v41.3 | v40.9 | 3 | Ningún guard dice qué contexto puede escribir dónde. `00_System` lo escriben hoy seis contextos. (Cerrada con la decisión del usuario del 2026-10-08, «registro de subrutas»: `vault_arch.duenos_de_sistema` deriva el dueño de cada subruta de los `FICHERO_*` de los repositorios de dominio, y `SUBRUTAS_DE_SISTEMA_SIN_REPOSITORIO` declara, con motivo, las seis que ninguno declara. `escrituras_de_sistema_ajenas` bloquea la puerta ante un cruce nuevo; los cinco que ya existían quedaron en `system_writes` de `arch-baseline.json`, que solo encoge. Residuo saldado en v41.3 con el criterio «dueño = único escritor», decidido el 2026-10-08: el dueño expone la escritura y el otro contexto delega por un par que ya estaba en el presupuesto; `.tool-tokens.json` pasó al kernel, que es quien lo escribe, y Consulta lo reexporta anotado. `system_writes` quedó vacío con el fichero en pie. Cobertura: no ve rutas que llegan por parámetro desde otro módulo ni subrutas calculadas, y falla del lado de no marcar. Caso medido el 2026-10-09: `vault_manifest --bootstrap` escribe `00_System/tool-spec.json` con `atomic_write_json(tool_spec_path())`; la ruta sale de `vault_io`, la subruta colapsa a «la carpeta» y no se reporta. Ese mismo día `tool-spec.json` recibió dueño declarado en `SUBRUTAS_DE_SISTEMA_SIN_REPOSITORIO` (meta_toolkit, su único escritor). Desde v41.3 la guarda la ve: `funciones_de_sistema_del_repo` indexa las funciones cuyo `return` es ruta literal de `00_System/` y `escrituras_de_sistema_en` las resuelve un nivel en quien las importa (`from m import f` o `m.f()`); medido ese día, no apareció ningún cruce nuevo. Sigue fuera: la ruta que llega por parámetro a un helper de nombre neutro (uno que se llama como una escritura sí se ve), la función sin import que la resuelva y la ruta calculada a más de un nivel. `tests/test_arch_escrituras_por_parametro.py` fija lo que se ve y lo que no, para que quien lo amplíe tenga que corregir esta declaración.) | Exige antes sanear `_LLAMADAS_DE_ESCRITURA` —incluye `replace`, que captura `str.replace`, y `write_report`, que no escribe— y una decisión de diseño que nadie ha tomado: de quién es `00_System`. (El saneado está hecho en v41.3: `vault_arch.llamada_de_escritura` es la única definición de «escribe» de las dos guardas, `write_report` salió de la lista y `replace` se decide por la forma —de 640 llamadas que contaban en `scripts/`, 336 no escribían—. Queda la decisión de dueño, que es del usuario.) |
| `recursion_error_en_parsers` | saldada en v40.23 | v40.9 | 5 | `RecursionError` escapa a `except yaml.YAMLError` en 4 parsers: no es subclase. Reproducido a 400 corchetes anidados. El peor caso es `vault_foreign_check`, que es la tool de la regla 7. v40.23 (77981b5) lo cerró con AP-61 y su puerta `vault_excepcion_declarada`, y el test ejecuta el dato hostil contra los parsers reales, `vault_foreign_check` incluido. | Es un arreglo de robustez con su propia norma candidata; entra en la tanda donde se unifiquen los parsers, no en una de alcance. |
| `parsers_de_frontmatter_divergentes` | saldada en v41.3 | v40.9 | 7 | 8 parsers de frontmatter distintos (esa parte, saldada en v41.3: al medirla eran once lectores por líneas en diez módulos, y todos delegan en `vault/kernel/frontmatter_parsing.cargar_bloque_tolerante`; `vault_criterios.medir_lecturas` hace fallar la puerta AP-57 ante uno nuevo); `vault_write.slugify` no delega en `vault_lib` aunque 20 módulos sí (esa parte, saldada en v40.35: delega en `slugify_strict` y el slug viejo queda solo para encontrar notas ya escritas); 6 aliases de v40.8 con el nombre viejo aún en uso (esa parte, saldada en v41.3: el repo lee solo los nombres canónicos y los viejos siguen definidos con su `superseded_by:`, sin derogarse); `--agent default="claude"` en 6 tools frente al AP-16 que `vault_bug_save` exige. | Es AP-50 acumulado y se salda unificando, no parcheando: hacerlo a medias deja nueve parsers en vez de ocho. Quedan los aliases y el `--agent` por defecto, y lo segundo cambia lo que reciben los clientes MCP: lo decide el usuario, no esta tanda. (Decidido el 2026-10-08: el default se mantiene. Medido ese día, ya son 13 tools con `default="claude"`, no 6; cambiarlo alteraría lo que reciben los clientes MCP que no pasan `--agent`, y `vault_bug_save` sigue exigiéndolo donde la atribución es parte del defecto. Esa parte queda decidida. Los aliases se migraron ese mismo día, y con ello la entrada se salda.) |
| `catch_vacios_en_el_servidor_mjs` | saldada en v41.3 | v40.9 | 7 | 11 `catch (_) {}` en `mcp/nodejs/vault-mcp-server.mjs` (AP-51 en JS). v41.3 los midió uno a uno: los que convertían un fallo en un vacío —traza, sello de versión, backup, recuento del registro, mapa de enlaces— ahora lo exponen; los legítimos —caer a un error declarado, probar el siguiente candidato— lo dicen con `AP-51:`. `vault_blame_audit.catch_silenciosos_js` mide la frontera JS sin baseline, con tolerancia cero. | Los tres audits con baseline miden AST de Python. Un detector de JavaScript es otro proyecto, y fingir que el alcance lo cubre sería el mismo cero sobre un subconjunto que esta versión vino a cerrar. |
| `baselines_sin_objetivo_ni_pendiente` | saldada en v40.24 | v40.20 | 7 | Las baselines del repo solo podían **encoger**, y eso es un suelo, no una trayectoria: nada declaraba a cuánto deberían llegar ni a qué ritmo. v40.24 lo cierra con el mecanismo, no con una cifra: `vault_baseline` es el dueño único de la carga, la escritura y la negativa a crecer, y el contrato de `objetivo` exige tamaño, fecha límite, cadencia y dueño — un número suelto no valida. La pendiente se deriva de `git log` cada vez que se genera este plano y **nunca se escribe** en el fichero, porque escribirla sería afirmar sobre la historia sin que git la respalde (AP-53). Las dos columnas nuevas de la tabla de abajo son eso. Con ello `gancho_sin_presupuesto` deja de ser informativo: los seis `GANCHOS_DEL_KERNEL` declaran presupuesto en `vault_arch.PRESUPUESTO_DE_GANCHOS` y el séptimo sin declarar bloquea la puerta. | Cerrada. Lo que queda no es esta deuda sino la siguiente, y va declarada aparte: el mecanismo existe y la mayoría de las baselines todavía publican `sin objetivo`. |
| `baselines_sin_objetivo_asignado` | saldada en v41.3 | v40.24 | 7 | El campo `objetivo` ya existe y se valida, pero solo `excepcion-declarada-baseline.json` lo declara — y allí el valor no es una decisión, es lo que la propia baseline ya decía: nació vacía y el objetivo es que siga vacía. Las demás publican `— sin objetivo` en la capa 6, que es el estado honesto y no se confunde con `cumple`. (Saldada en v41.3, 2026-10-09: el usuario aprobó una propuesta medida —tamaño actual e historia en git de cada baseline— y cada una declara tamaño, fecha, cadencia y dueño; la capa 6 los publica. Para escribirlos hubo que ampliar el contrato: `objetivos_por_clave` cuando un fichero congela dos baselines, y `sin_objetivo_porque` para el contrato de campos, que crece por diseño y se publica como `no_aplica` en vez de con una meta falsa.) | A cuánto debe encoger cada baseline y para cuándo es un compromiso del dueño del repo, no un dato derivable. Escribir trece cifras plausibles para que la tabla se vea completa sería exactamente el AP-47 que el contrato de `objetivo` existe para impedir, cometido dentro del mecanismo que lo impide. |
| `vault_norms_es_un_modulo_dios` | saldada en v40.27 | v40.20 | 7 | `vault_norms` acumula miles de líneas y la mayor parte de los cruces sin puerto del repo. Las dos cifras iban escritas aquí y las dos habían envejecido —decía 4.257 líneas cuando ya eran más de cinco mil, y «9 de los 13 cruces» cuando el reparto había cambiado—, que es AP-47 cometido dentro del registro que publica la deuda de AP-47; se miden con `wc -l scripts/vault_norms.py` y con `off_port_crossings` de `scripts/arch-baseline.json`, y por eso ya no se copian. No es un problema de clasificación —al medir para v40.20 se comprobó que su fan-in no es el del núcleo—: es un módulo que hace de catálogo, de motor y de fachada a la vez, con las dependencias invertidas. Se parte en `catalog` / `engine` / fachada y se invierten esos cruces. v40.26 hizo el corte y v40.27 lo cobró: partido, `vault_norms_catalog` resultó tener fan-out cero —la forma de `vault_registry`— y se mudó al núcleo con `compute_norm_refs`. Veintiuno de sus veinticuatro importadores solo pedían datos y ahora se los piden al dueño: **62 → 42 cruces, veinte saldados, cero nuevos**, y quince ciclos diferidos de AP-58 resueltos de paso, porque `vault_voice` dejó de importar la fachada. La deuda se cierra midiendo, no declarándolo: el corte por sí solo no movió una sola cifra. | Es la tanda más cara de las cinco y depende de lo que el mapa del núcleo revele. Partirlo antes de tener el grafo con dueño habría sido mover código a ciegas. |
| `la_norma_no_es_un_paquete` | saldada en v41.4 | v40.20 | 7 | El ciclo obligatorio del repo —síntoma → norma → guard+audit+heal → test— vive hoy en cuatro listas sincronizadas a mano: el catálogo, la tool, la puerta y el fichero de tests. La norma como **paquete** (`normas/AP-XX/` con `norma.py`, `guard.py`, `heal.py`, `test_*.py` y `porque.md`) la convierte en una sola cosa con cuatro caras, y el coste de una norma nueva deja de crecer con la historia del repo. | Migra por atrición, no de golpe: 71 normas movidas en una tanda serían 71 oportunidades de perder un matiz. Empieza por las que se escriban a partir de ahora.

(Avance de v41.3, fecha: 2026-10-09.) La infraestructura existe y tiene piloto: AP-65, la última norma del catálogo, vive en `normas/AP-65/` con `norma.py`, `porque.md` y su test. `vault_norms_catalog` la carga en su sitio de siempre —el catálogo y el registro que reconstruye `vault_norms --rebuild` no cambiaron ni un byte, salvo la fecha—; `--check-framework` falla si un paquete pierde una cara, declara otro código, no lo carga el catálogo o cita en `porque.md` una cara `ruta::símbolo` que no existe; `normas/` viaja en la wheel y lo comprueba `clean_install_gate`. Lo que no tiene el piloto, y se declara: `guard.py` y `heal.py` propios. Su criterio sigue con su dueño en el kernel y AP-65 no tiene heal, porque nadie puede escribir por otro a quién afecta una decisión. Queda la migración del resto, una norma cada vez. (2026-10-09: AP-64, la anterior a la piloto, vive en `normas/AP-64/`; el catálogo serializado sale idéntico al de antes de moverla y sus tests de `tests/` siguen donde estaban. Cuántas van lo publica `vault_norms_catalog.NORMAS_EN_PAQUETE`.) (2026-10-09, m183–m186: el resto migró por familias —patrones, protocolos y convenciones en un lote; AP en tres tramos—. `NORM_CATALOG` ya no escribe ninguna entrada: toda norma la carga `_desde_paquete`, el catálogo serializado sale idéntico byte a byte al de antes del primer lote y `--rebuild` no escribe nada. Las caras de `porque.md` se derivaron al migrar, no se escribieron, y donde una tool declarada no tiene función que nombre la norma lo dice en vez de inventarla. Lo que sigue pendiente es lo que el piloto ya declaraba: `guard.py` y `heal.py` propios. El criterio de cada norma sigue con su dueño en `scripts/` o `vault/`, y moverlo a la carpeta sería la segunda copia que el paquete viene a quitar, así que esta deuda no se salda solo por haber migrado las entradas.)

(2026-10-09, m197: saldada.) `guard.py` y `heal.py` existen en cada paquete y son **derivados**, no escritos: cada `ruta::símbolo` es una función que nombra la norma en su cuerpo dentro de una tool que el catálogo declara, así que apuntan al dueño sin copiar su criterio. Las tools que reparan salen de un registro nuevo con dueño, `vault_norms_catalog.SANADORES`, que es por tool y no por norma; `tools_healing(code)` se deriva de él. Una norma sin sanador lleva `HEAL = None` con su `MOTIVO`, y un par del registro sin función que lo nombre falla la puerta (AP-55). `--check-framework` falla si una cara falta o no es la que sale de derivarla, y la wheel las lleva. |
| `el_vault_no_tiene_kernel_declarado` | saldada en v41.4 | v40.20 | 7 | `vault_kernel` traza el núcleo **del repo**. El mismo concepto aplicado a las notas —qué subconjunto de un vault es su núcleo— daría prioridad a `vault_context_pack` cuando el paquete no cabe, orden a la sanación y pesos a `vault_audit`. | Declarado sin fecha por decisión de alcance. El núcleo de un vault no se deriva del grafo de imports sino del de enlaces, y esa medida hay que contrastarla contra un vault ajeno antes de creérsela (regla 7). (Avance de v41.3, 2026-10-09: la medida existe y es informativa. `vault_audit._nucleo_del_vault` cuenta el fan-in de cada nota desde notas de contenido distintas, resuelto como Obsidian —nombre, `aliases:`, sufijo de carpeta, nunca `title:`—, y corta con el mismo escalón que `vault_kernel`, que pasa a `vault/kernel/escalon.py` para tener un solo dueño; sale en `vaultCore` sin fila en `PENALIZACIONES`. Regla 7 sobre copias nuevas, hash de los originales intacto: /ans, 527 notas, umbral 29 (ratio 1.933), una nota núcleo, `01_Projects/ans/overview.md`; /vcloud, 106 notas, umbral 26 (ratio 1.444), una nota núcleo, `09_Infrastructure/network-topology.md`. Sigue pendiente lo que la medida habilita y no hace todavía: la prioridad en `vault_context_pack`, el orden de la sanación y cualquier peso. Medida y descartada, 2026-10-09: la prioridad en el paquete —las candidatas del núcleo entran primero cuando la ventana no cabe, sin traer ninguna que la consulta no recuperó— se implementó y se midió con recall título → paquete sobre copias nuevas, y **baja** el recall: /vcloud a 500 tokens de 1.0 a 0.76; /ans a 800 de 0.96 a 0.92 y a 500 de 0.84 a 0.80; la nota buscada en primera posición cae en los dos (vcloud de 1.0 a 0.76–0.80, ans de 0.84 a 0.72). La causa es la del corte: el núcleo es una nota-hub que el grafo trae como candidata a casi toda consulta, y adelantarla desplaza a la que la consulta buscaba. Revertida, como pedía el criterio fijado antes de medir. Lo que queda habilitado es orden de sanación o peso, y ninguno se mide todavía. Saldada, 2026-10-09, con las tres salidas decididas: la prioridad en el paquete, descartada por medida (arriba); el peso en el `healthIndex`, descartado por el usuario; y el orden de la sanación, hecho: la fase 8 de `vault_sanacion` publica `order` —las notas de `vaultCore` con enlaces rotos primero, luego por fan-in y por enlaces rotos— y `order_criterion`, sin escribir nada ni decidir qué enlace es nota ausente. Regla 7 sobre las mismas copias, hash intacto antes y después: en /ans (18 notas con rotos) y /vcloud (6) la única nota núcleo no tiene enlaces rotos, así que allí el orden coincide hoy con el recuento; el criterio existe y se declara, no cambia nada en esos dos vaults.) |
| `puente_scripts_impl_sin_contrato` | saldada en v41.8 (2026-10-17) | v40.34 | 3 | `_impl/` no es una copia de `scripts/`: es el destino del package-dir que mapea `scripts/` → `vault_toolkit/_impl/`. ADR-0002 formaliza el puente: fachada de re-export + package-dir. La deuda es transitoria: desaparece cuando `scripts/` migre a `vault/<contexto>/` y el puente ya no sea necesario. (Avance de v41.3, 2026-10-09: la cifra ya no se escribe a mano. `vault_arch.modulos_sin_hogar` cuenta los módulos de `scripts/` que no importan nada de `vault/<su contexto>/`, la capa 3 la publica derivada y la baseline `bridge_modules` de `arch-baseline.json` la congela: solo encoge, y un módulo nuevo sin hogar bloquea `vault_arch --check`. Primera migración, para probar que el puente aguanta: `vault_subproceso`, hoja del kernel, vive en `vault/kernel/subproceso.py` y `scripts/` conserva el nombre como fachada; la wheel limpia lo importa desde `_impl`. Segunda, el mismo 2026-10-09: `vault_ledger`, el contador thread-local de AP-37, vive en `vault/kernel/ledger.py` y la fachada reexporta el mismo `threading.local`, también sus nombres privados, porque `vault_io` los reexporta a su vez. Medida corregida el mismo día: la cifra contaba también los módulos que la wheel no lleva —`empaquetado/fuera-de-la-wheel.json`, la gobernanza del estándar—, que no cruzan el puente porque no viajan; excluidos, la baseline perdió 22 entradas sin ganar ninguna. Lote A, 2026-10-09: cuatro hojas sin `__file__` ni lectores del fuente por ruta —`vault_audit_catalog`, `vault_fundamentals_catalog` y `vault_mermaid_reglas` al kernel, `vault_security_rules` a gobernanza—, ya como alias en `sys.modules` y no como fachada que reexporta, para que un monkeypatch sobre el nombre viejo lo vea el dueño; wheel limpia y `run_product_gates` en verde. Quedan fuera del lote, con motivo: `vault_norms_catalog` y `vault_entorno` (otros módulos y tests leen su fuente por ruta), `vault_grafo_import` (usa `__file__`), `vault_secret_scan` (lo leen por ruta tres tests y `vault_standard_upgrade`) y `vault_version` (lo lee `cli/`). Lote B, 2026-10-09: `vault_secret_scan` a gobernanza. Lo que lo frenaba no eran los lectores —`vault_standard_upgrade` solo lo nombra en una cadena— sino que es CLI: un alias en `sys.modules` no ejecuta el `__main__` del dueño, así que el alias de una tool con CLI lo delega con `runpy`. Los guards que leen el fuente de una tool siguen el alias hasta el dueño por un solo sitio, `vault_grafo_import.fuente_de`. `vault_version` sigue fuera: `cli/` ejecuta su fichero con `spec_from_file_location` para no tocar `sys.path`, y un alias no tiene `CURRENT_VERSION`. Lote C, 2026-10-09: `vault_entorno` al kernel —el motivo que lo dejó fuera del lote A no se sostuvo al medirlo: el `.mjs` y `env-table.json` lo nombran en prosa y la tabla se deriva por import—. Lo que queda son cadenas: `vault/` solo importa de `scripts/` por `vault/kernel/adaptadores.py`, así que un módulo con dependencias en `scripts/` no migra como alias sin reescribir sus imports; las raíces que las bloquean son `vault_norms_catalog` (`__file__` para `normas/` y tests que leen su fuente: punto de la deuda #10), `vault_version` y `vault_grafo_import`. Lote D, 2026-10-10: `vault_link_safety` a grafo, `vault_escaneo_grafo` al kernel, `vault_firma_sitio` a meta_toolkit y `vault_index` a índices. La frase anterior sobre cadenas era más estricta que la regla medida: `vault_arch` solo marca un cruce cuando un módulo de `vault/<ctx>/` importa uno de **otro contexto que no es el kernel**, así que una hoja cuyas dependencias en `scripts/` son del kernel o de su contexto migra sin puerto; los cruces no se movieron. Lo destapó la guarda de puertos, que leía el fichero del alias y dio por roto `resolver_wikilink`: ahora sigue el alias con `fuente_de`, como un import.)

(Lote E, 2026-10-10: ocho tools con CLI migran —append, list, log_error, merge, project_status y runbook_log a autoría, section a índices como `registro_de_secciones` y env_matrix a grafo—; el alias corre su `main` con `runpy`. Los tests de AP-46 y del barrido de secciones leían la ruta del alias y ahora siguen al dueño, y las caras de CN-02 citan `vault/indices/registro_de_secciones.py`.)

(Lote F, 2026-10-10: seis migran —history_compact y arquitectura_en a ciclo de vida, graph_fix a grafo, supersede, frontmatter_completar y frontmatter_heal a autoría—, y las caras de las catorce normas que los citaban apuntan al dueño. `vault_subgraph` se quedó en `scripts/`: su cruce hacia `vault/grafo` está en la baseline con la clave del nombre de `scripts/`, y moverlo lo re-clavaba como cruce nuevo. Es la misma traba que la de las cinco firmas de las baselines de AP-51 y AP-57: la clave tiene que seguir al alias. Desde que la sigue —`vault_arch.alias_de_dueno`—, `vault_subgraph` migra a `vault/consulta/subgraph.py` con su cruce intacto.)

(Lote H, 2026-10-10: los cinco con sitios en baselines —errors_trace al kernel, fix_brackets a autoría, graph_inspect a grafo, sanacion a ciclo de vida y spec_generate_catalog a meta_toolkit— migran sin re-clavar nada: blame y criterios ya indexaban por el alias, y `cruces_fuera_de_puerto` pasó a hacerlo al destapar que medía los dueños por `ruta.stem` (m245). Las caras de AP-22 y AP-24 citan `vault/autoria/fix_brackets.py`.)

(Lote G, 2026-10-10: mcp, spec_catalog_check y test_runner a meta_toolkit, fuente_unica a gobernanza y token_counter a consulta. Sus `SCRIPTS_DIR` y baselines se derivaban de `__file__`; ahora salen de `vault_grafo_import.DIRECTORIO`, que es `scripts/` en el checkout y `_impl/` en la wheel. Antes, m248 hizo que los tests de propiedad leyeran al dueño con `codigo_de`. Las caras de AP-05 citan `vault/gobernanza/fuente_unica.py`. Quedan las nueve raíces del kernel.)

(Lote D, raíces del kernel, 2026-10-10: version, vocabulario y contrato_nota a `vault/kernel/`. `cli/__init__.py` lee la versión del dueño en el kernel —la CLI no viaja en la wheel—, el README de `schemas/` cita `vault/kernel/contrato_nota.py` y la cara de AP-64 también. Antes, m251 hizo que `vault_grafo_import.grafo()` midiera al dueño y no al alias: con las aristas del alias el escalón de AP-59 bajaba y `vault_errors` cruzaba un umbral que con las reales no cruza.)

(Lote A de la quinta tanda, 2026-10-16: raiz y fs a `vault/kernel/`. Las dos se anclaban en su `__file__`: `vault_raiz` toma ahora el directorio del programa de `vault_grafo_import.DIRECTORIO` —la raíz autodetectada no cambia, `spec_repo_sandbox` en el checkout— y `vault_fs` deja de tocar el path, que ya pone el alias. Tres tests leían `scripts/vault_fs.py` por ruta y leen al dueño.)

(Lote B, 2026-10-16: baseline a `vault/kernel/`, con `REPO_ROOT` derivado del directorio del programa. `vault_grafo_import` no se muda: es el ancla del puente, quien dice dónde está `scripts/`, y lo dice con su propio `__file__`; mudarlo exigiría derivar ese directorio de dos formas, por el checkout y por la wheel, en el sitio que existe para que nadie más lo derive. Lo fija `test_el_ancla_del_puente_no_se_muda`.)

(Lote C, 2026-10-16: registry a `vault/kernel/`. `comando_de_tool` decidía «estoy instalado» por el nombre del directorio de su `__file__`; lo decide el del programa. La cara de AP-64 y `docs/architecture/layers.md` citan al dueño.)

(Lote D, 2026-10-16: norms_catalog a `vault/kernel/`, con `RAIZ_NORMAS` derivado del directorio del programa; su fan-out pasa de cero a exactamente `vault_grafo_import`, núcleo → núcleo. Las caras `guard.py` de seis normas se regeneran hacia el dueño. El puente queda en el ancla declarada.)

(Saldada el 2026-10-16: el contrato existe. `vault_arch --check` falla si un módulo de `scripts/` que viaja en la wheel no es alias, no tiene hogar y no está en `vault_arch.ANCLA_DEL_PUENTE`, y también si un ancla declarada ya tiene hogar. La baseline `bridge_modules` no bastaba: `--freeze` la reescribe sin negarse. Lo que no se salda: `vault_grafo_import` sigue en `scripts/` por diseño, con el motivo escrito en el registro, y `tiene_hogar` es sintáctico —importar del contexto no es haber migrado entero—.) | Transitorio hasta migrar scripts → vault/<contexto>, ADR-0002. La fachada y el package-dir existen; la deuda es de diseño, no de implementacion. (Ya no aplica desde el 2026-10-16: se conserva como estaba, por no-derogación.) |
| `cn01_cn04_solo_se_miden_al_escribir` | saldada en v41.3 | v41.1 | 7 | CN-01 (nombre kebab-case) y CN-04 (la nota abre con su título como H1) tienen enforcement `guard` y se cumplen solo en el write path: `vault_write`, `vault_knowledge_save` y `vault_ai_decision`. Una nota escrita por otro camino —un vault preexistente, una edición a mano— no la mide nadie después. El docstring de `vault_write.slugify` lo dice de CN-01: «ninguna otra tool audita después los nombres ya escritos». El único `"norm": "CN-01"` de `vault_audit` es sobre el scaffold, no sobre los nombres de las notas. (La medida, hecha en v41.3: `vault_audit._detect_convenciones_cn01_cn04` las publica en `issues.cn01NotKebab`/`cn04NoTitle`, sin peso, con el criterio de `slugify_strict` y `abre_con_h1`. Regla 7, 2026-10-08, sobre copias, repetida igual sobre copias nuevas el 2026-10-08: /ans 94 y 253 de 527 notas, /vcloud 1 y 0 de 108. De las 253 de /ans, 137 son de `11_Code`: `vault_code_module` y otros escritores del estándar no pasan por `con_titulo`.) | Medirlas en notas existentes cambia el enforcement a `guard+audit` y, si penalizan, el healthIndex de todo vault consumidor. Es una decisión de norma, con su tabla de penalizaciones y su contraste contra un vault ajeno antes de fijar el peso (regla 7), no un arreglo de la tanda. Queda: decidir el peso —lo decide el usuario— y que los escritores que no aplican `con_titulo` lo hagan, que cambia su salida. (Decidido el 2026-10-08: sin peso; la medida sigue informativa. Y los diez escritores que creaban la nota sin H1 —bug, code_module, diagram, flow, test, requirement, infra_save, infra_map, pattern y runbook— pasan por `con_titulo`; sus dorados cambian solo en esa línea. `vault_onboard` ya escribía el H1 en sus plantillas y `vault_undo` restaura el contenido tal cual, que es lo que debe hacer.) |
| `ap17_compara_solo_la_forma_del_titulo` | saldada en v41.3 | v41.1 | 4 | AP-17 (sombra canónica) se detecta con `SequenceMatcher` ≥ 0.85 sobre el texto del título (`vault_audit._detect_canonical_shadow`). Dos notas sobre lo mismo con títulos distintos no salen, y dos títulos parecidos de cosas distintas solo se separan si `_distintos_por_convencion` reconoce la convención. La atribución que esta entrada también reclamaba ya estaba bien y se corrigió aquí en v41.3: el catálogo declara `tools_detecting: ['vault_audit']`, quien mide, y `tools_enforcing: ['vault_supersede']`, quien sana. Lo pendiente es solo la medida. (Saldada en v41.3 con la reformulación decidible: se compara la identidad que la nota **declara** —un `aliases:` que es el nombre de fichero o el alias de otra, o el mismo conjunto de `files:`—, con el criterio de resolución de Obsidian. Cada par publica su `motivo`. Regla 7, 2026-10-09, solo lectura y hash intacto: contra las copias de /ans, /vcloud, builderx, electron, synesis, smart-pos-cr, ecommerce y grooming-scheduler, 0 pares por `alias` o `files` y los de `titulo` sin cambio (112, 1, 0, 1, 0, 2, 9, 13). Sin un solo acierto no hay dato con el que fijar un peso, así que `canonicalShadowIdentity` se informa sin pesar, como AP-02. Lo que sigue sin medir —el mismo tema con identidad distinta— lo declara la `cobertura_parcial` de AP-17.) | Ir más allá de la forma pide comparar contenido o identidad declarada, que es justo lo que el servicio descarta sin embeddings. Hace falta una reformulación decidible, como la que desbloqueó AP-05 en v40.15, antes de tocar el detector. |
| `churn_del_kernel_no_ve_el_commit_en_curso` | saldada en v41.3 | v41.1 | 7 | K3 de `vault_kernel` (AP-59) cuenta el churn con `git log`, así que la puerta que corre antes de commitear no ve el commit que se está haciendo. El que cruza el umbral pasa en verde y el siguiente, aunque no toque el módulo, hereda el rojo. Pasó en esta ronda: `vault_registry` llegó a churn 23 con umbral 22.85 (mediana 13 × 1.758) y hubo que admitirlo en `kernel-baseline.json` con autorización expresa. | Contar el índice (`git diff --cached --name-only`) arregla el pre-commit pero hace que la misma medida dé cifras distintas según se ejecute antes o después de commitear, y la CI mide después. Hay que decidir cuál es la medida canónica antes de cambiar el contador. (Decidido el 2026-10-08: la canónica es la de `git log`, la que mide la CI. `vault_kernel --aviso-indice` lee el índice con el mismo criterio de comportamiento y el pre-commit avisa del cruce sin bloquear ni cambiar la cifra publicada.) |
| `meta_decide_el_orden_del_frontmatter` | saldada en v41.3 | v41.1 | 5 | En `vault_write`, los campos que llegan por `--meta` se añaden al final del frontmatter. Medido el 2026-10-07: con `--meta '{"agent":"claude","type":"concept"}'`, `type` sale detrás de `agent` y de los tres `cia_*`, y su posición depende de por dónde llegó y no de qué campo es. | Ningún consumidor que lea con `yaml.safe_load` depende del orden, así que no rompe nada. Fijar un orden canónico cambia byte a byte la salida de toda nota nueva, y ese orden tiene que salir del contrato de nota (`vault_contrato_nota`), no de una lista nueva. Saldada en v41.3 con el orden mínimo que eligió el usuario: el `type` de `meta` ocupa el hueco del deducido, el resto de campos de `CAMPOS` sale tras `agent` en su orden y lo ajeno al contrato al final; una nota sin esos campos en `meta` no cambia un byte. |
| `backlinks_del_audit_indexados_por_nombre` | saldada en v41.3 | v41.3 | 5 | `vault_audit._build_indexes` indexa los backlinks por **nombre de fichero**, no por ruta: dos notas homónimas en carpetas distintas comparten entrantes, y un enlace que fija una de ellas con su carpeta deja a la otra «enlazada» también. Es un falso verde en `orphans` y en `notIntegrated`. Medido el 2026-10-09 en una copia de /ans: `[[code/playbook-versioning]]` resuelve a `05_Patterns/code/playbook-versioning.md` y saca de huérfanas a `11_Code/ans/playbook-versioning.md`, que no enlaza nadie. | Pasar la clave a ruta cambia la forma del índice que leen `_detect_orphans`, `_detect_no_integradas` y cinco ficheros de tests, y es un arreglo distinto del que la destapó: m155 hizo que los backlinks resolvieran alias, carpeta y ancla como Obsidian (AP-44), y con eso el caso homónimo se hizo visible. El test `tests/test_audit_backlinks_como_obsidian.py::test_limite_declarado_los_homonimos_comparten_entrantes` fija el límite y falla el día que se salde. (Saldada en v41.3, 2026-10-09, sin cambiar la forma del índice para nadie más: `vault_audit._claves_de_nota` indexa por nombre a la nota única y por ruta a cada homónima, también como origen, y los detectores leen con `_clave_de`. Un enlace ambiguo sigue contando para todas las candidatas. Regla 7 sobre copias nuevas, hash de los originales intacto: /ans, huérfanas 2 → 2 y no integradas 271 → 274 —`10_Migrated/direct/claude-code-setup.md`, `10_Migrated/excluded/codex-guide.md` y `11_Code/ans/playbook-versioning.md`, sin ningún wikilink saliente y citadas solo por su `index.md`: se integraban con los salientes de su gemela—; /vcloud, sin cambios (12 y 2); healthIndex igual en los dos. La medida de arriba erraba en un punto: a `playbook-versioning` sí la cita un índice, así que el falso verde era de `notIntegrated`, no de `orphans`.) |
| `f8_criterio_sin_decidir` | saldada en v41.6 (2026-10-15) | v41.3 | 5 | F8 (no repudio) se mide con un criterio que el manifiesto no publica. El registro (`vault_fundamentals_catalog`, F8) verifica que «al menos una entrada en .change-log.json referencia la ruta de la nota» y `vault_quality_check._score_non_repudiation` lo aplica a toda nota viva; la tabla de dimensiones del manifiesto pide «1 por borrado». Como `vault_write` no anota creaciones en el change-log, un vault recién poblado puntúa 0 en `non_repudiation` en todas sus notas: 26 de 26, medido el 2026-10-14 con la wheel instalada en un consumidor limpio. | Cuál de los dos criterios manda es una decisión de producto: (a) `vault_write` anota creaciones y actualizaciones, lo que es un campo nuevo en su contrato, o (b) el registro se ciñe a borrados y movimientos, como dice el manifiesto. El usuario la dejó declarada el 2026-10-14. `tests/test_f8_criterio_sin_decidir.py::test_limite_declarado_f8_registro_y_manifiesto_divergen` fija la divergencia y falla el día que los dos digan lo mismo. (Saldada el 2026-10-15: el usuario eligió (a). `vault_write` anota cada alta y cada cambio en `.change-log.json` y lo publica en el campo nuevo `change_log` de su envelope —`change_log_error` si la bitácora falla, sin tumbar la escritura—; la matriz y el manifiesto pasan a «1 por nota», que es lo que el registro ya medía, y `vault_write` entra en las tools de F8. El criterio no se rebajó: una nota viva sin entrada sigue puntuando 0.) |
| `sanadores_sin_lote` | saldada en v41.8 (2026-10-17) | v41.4 | 5 | AP-47: `vault_io.escrituras_en_lote()` regenera sección, búsqueda y grafo una vez por lote en vez de una vez por nota. Lo abren `vault_frontmatter_completar` (2990 s → 32 s) y la ruta clasificada de `vault_graph_fix` (107 s → 15 s), y desde el 2026-10-16 `vault_fix_brackets` (58,8 s → 11,5 s sobre 50 notas sembradas en una copia de /ans: sin lote moría por TOOL_TIMEOUT) y `vault_frontmatter_heal` (59,6 s → 11,9 s sobre 45 notas con el frontmatter sembrado en una copia de /ans; 13,8 s → 4,6 s en /vcloud) y `vault_project --heal` (29,6 s → 9,5 s en /ans; 16,0 s → 5,1 s en /vcloud) y `vault_graph_fix.apply_fix`: en una copia de /ans, sin lote, escribir una nota regeneraba el `index.md` de su sección y los dos índices que venían en el mismo informe salían como STALE_REPORT —10 de 12 aplicados, rc 1—; con lote, 12 de 12. `vault_supersede` no lo abre porque escribe una nota por llamada y no tiene nada que aplazar (medido en `test_vault_supersede_escribe_una_nota_por_llamada`). `vault_norms_engine` tampoco, y no por coste: `heal_ap46` escribe con `write_bytes` y no pasa por `atomic_write_text`, así que no hay regeneración que aplazar; lo que le falta es otra deuda, `heal_ap46_escribe_sin_atomic_write`. Medido el 2026-10-14 sobre 35f5bad; `SIN_LOTE` vacío el 2026-10-16. | Cada sanador que entra en el lote exige comparar el árbol de dos copias de un vault ajeno —con lote y sin él— y no solo el contador, como se hizo con los dos primeros; ninguno de los restantes ha dado un TOOL_TIMEOUT medido. `tests/test_sanadores_sin_lote.py::test_limite_declarado_sanadores_sin_lote` fija la lista y falla en cuanto encoge o crece. El árbol se compara sembrando el defecto en hasta 3 notas por carpeta de una copia de /ans y de /vcloud —el defecto real está en una nota o en ninguna, y así el lote no se ejercita— y quitando marcas de tiempo y orden de listas JSON antes de comparar. |
| `heal_ap46_escribe_sin_atomic_write` | saldada en v41.8 (2026-10-17) | v41.7 | 5 | Regla 6 y AP-54: `vault_norms_engine.heal_ap46` —`vault_norms --heal-ap46 --apply-heal`, que acepta `--root` y se pensó para vaults reales— escribe la nota reparada con `path.write_bytes`: sin temporal ni `os.replace`, sin lock entre diagnóstico y escritura, sin escáner de secretos y sin regenerar sección, búsqueda ni grafo. La copia en `.history/ap46-heal/` sale igual. Un corte a mitad deja la nota truncada con el backup como única salida. Medido el 2026-10-16 al cerrar `sanadores_sin_lote`, sobre d21bebd.

(Saldada el 2026-10-17: con `--apply-heal`, `heal_ap46` apunta la raíz del proceso al vault pedido y la devuelve al salir, abre `escrituras_en_lote()` y escribe cada nota con lock, relectura bajo el lock, backup por temporal y `atomic_write_text(sanitize=False)`: el heal repara el bloque y no sanea bytes del cuerpo. Un rechazo del write path —secreto, nombre reservado, frontmatter que no relee, corte de E/S— sale en `skipped` con su motivo y no cuenta como curada. `vault_norms_engine` sale de `FUERA_DEL_LOTE`.) | Pasar a `atomic_write_text` cambia lo que se escribe, no solo cómo: sanea el encoding, puede rechazar por el escáner de secretos, y regenera la sección contra `vault_io.get_vault_root()`, que con `--root` no es el vault objetivo porque `--heal-ap46` no llama a `set_vault_root` (el `--audit` sí). Exige decidir esa raíz y medir el árbol sobre copias de /ans y /vcloud antes, como con los demás sanadores. `tests/test_sanadores_sin_lote.py::test_limite_declarado_heal_ap46_escribe_sin_atomic_write` fija el límite y falla en cuanto cambie. (Ya no aplica desde el 2026-10-17: se conserva como estaba, por no-derogación.) |
| `spec_validate_returns_ciego` | saldada en v41.8 (2026-10-17, superseded_by vault_smoke) | v41.6 | 5 | AP-44: `vault_spec_validate` comprueba `declared_returns` de `tool-spec.json` contra las claves escritas como literal en un `return {...}` (o en el dict asignado a la variable que se devuelve). No ve `r['clave'] = …`, `r.update(...)` ni las claves que pone un ayudante común —el indicador de trabajo de AP-37, el envelope de `emit_error`—, así que da drift a 90 de 145 tools y 8 «missing» que son tools del servidor JS. La CI lo ejecutaba con `|| echo "not yet implemented"`. Medido el 2026-10-15 sobre 72bee01. | Ampliar el AST a asignaciones por subíndice y `update` se midió: baja de 98 a 95 sin pasar, porque el grueso lo ponen ayudantes de otro módulo. Medirlo con el criterio del consumidor exige ejecutar cada tool y leer su envelope, que es lo que ya hace `vault_smoke` por otra vía; decidir si este detector se reescribe o se anota `superseded_by` es una decisión de producto. Mientras, la CI lo corre con `continue-on-error` y el nombre del paso cita esta deuda. `tests/test_ci_sin_enmascarar.py::test_limite_declarado_spec_validate_returns_ciego` fija el punto ciego y falla el día que el detector lo vea. Saldada el 2026-10-16 por decisión del usuario: `returns_match` queda superseded_by `vault_smoke.contract_gap`, que contrasta el envelope emitido, y sigue detrás de `--returns-estatico` (no-derogación). Sin él, lo que quedaba eran 8 «missing» que no viven en `scripts/` por diseño —5 archivadas, 2 JS nativas y `vault_gobernanza`, que es `execution_module`— y un drift real (`vault_qa_save` publicaba `--qa_type`, saldado en d6adcdd). La tool pasa en verde y la CI la corre como paso duro. |
| `ap37_mide_lo_declarado` | saldada en v41.9 (2026-10-17) | tras v41.6 | 4 | AP-44 sobre AP-37: `vault_noop_audit` comprueba que el contrato **declare** un indicador de trabajo, no que la tool lo **emita**. `vault_tags` declaraba `total` y `renamed`, que ningún modo devuelve, y `rebuild`/`rename` escribían sin `write_report()`: el audit en 0 con una tool que callaba lo que escribía. Lo de `vault_tags` se arregló; el criterio del audit sigue siendo el declarado. Medido el 2026-10-15. | Contrastar lo emitido exige ejecutar cada tool con escritura por el camino que escribe, sobre un vault desechable y con argumentos válidos por modo; `vault_smoke` ejecuta un solo ejemplo, casi siempre de lectura, y solo exige que salga **algún** campo declarado. Es un banco de ejecución nuevo, no un arreglo del audit. `tests/test_tags_dice_lo_que_escribe.py::test_limite_declarado_ap37_mide_lo_declarado` fija el límite. El 2026-10-16 entró el banco: `vault_noop_audit --ejecutado` ejecuta el ejemplo de cada tool con side effects sobre la copia de `vault_smoke` y contrasta el árbol con el envelope. Destapó dos que escribían callando (`vault_delta --snapshot`, `vault_graph_fix --apply`; a0fdb0c y 9985e24). Medido ese día: de 92 tools, 17 medidas y en verde, 2 sin invocación (runtime node) y 73 cuyo ejemplo no escribe, que el banco no ve. Saldarla exige un ejemplo de escritura por tool, no otro detector; el modo estático sigue midiendo lo declarado. El 2026-10-17 el banco ejecuta cada línea del ejemplo y prepara el proyecto y los ficheros que presupone: de 92, 57 medidas, 12 que no escriben con su motivo en `vault_noop_audit.SIN_ESCRITURA_DECLARADA` (una sin motivo, o declarada que sí escribe, lo deja en rojo), 2 sin invocación (runtime node), 21 fuera del vault (gobernanza del estándar) y 0 ofensores; destapó `vault_drift_detect --mode snapshot` (a744633). Se saldó en v41.9: la puerta `noop` corre `--check --ejecutado` (el banco mide en ~104 s, dentro del límite por puerta) y `vault_tags` anotó `total`/`renamed`/`tags` en `superseded_fields`. |
| `ap48_sin_voz` | saldada en v41.7 (2026-10-16) | tras v41.6 | 4 | AP-43 sobre AP-48: ninguna tool del catálogo MCP pronuncia AP-48. Su guard es `vault_mcp_catalog.check_contracts`, que corre la puerta `contratos` y no es una tool del catálogo, así que la norma no llega al agente por `vault_says`. Hasta f2110b5 la «pronunciaba» `vault_norms`, que solo la nombraba en el registro: la afirmación era falsa y C2 dejó de aceptarla. Medido el 2026-10-15. | Darle voz exige que una tool del catálogo ejecute la comprobación —exponer `vault_mcp_catalog` como tool, o que `vault_gate` publique las normas de cada puerta desde una función que las mida— y las dos son decisiones de superficie de producto, no un arreglo. Volver a atribuírsela a `vault_norms` sería reponer la afirmación falsa. `tests/test_voice.py::test_limite_declarado_ap48_sin_voz` fija la muda y falla el día que una tool la pronuncie. |
| `lock_caduca_por_reloj_de_pared` | saldada en v41.7 (2026-10-16) | v41.6 | 5 | `vault.kernel.bloqueo.adquirir` da un lock por huérfano cuando `time.time() - createdAt` supera `CADUCA_TRAS` (120 s), y la edad sale del reloj de pared, que salta: NTP, una VM que despierta, la resincronización de WSL. Un salto hacia delante de más de 120 s le roba el lock a un dueño vivo y dos escritores pisan la misma nota. Medido el 2026-10-15 con la suite en python:3.9-slim sobre Docker Desktop: el reloj del contenedor saltó 3458 s y `vault_append` escribió con ok:true sobre una nota bloqueada (`test_append_concurrente::test_con_la_nota_bloqueada_no_escribe_y_lo_dice`). | No es regresión: el criterio es el de siempre, y apareció en la ronda que sube a v41.6. Arreglarlo es una decisión de diseño: mirar si el `pid` de `owner.json` vive exige una consulta por plataforma y no sirve si dos máquinas comparten el vault por una carpeta sincronizada, y `owner.json` no guarda el host. `tests/test_lock_caduca_por_reloj_de_pared.py::test_limite_declarado_lock_caduca_por_reloj_de_pared` fija el límite y falla el día que un dueño vivo conserve el lock. (Saldada el 2026-10-15 con el criterio de py-filelock, elegido por el usuario tras comparar py-filelock, QLockFile, proper-lockfile, el DynamoDB Lock Client y git: `owner.json` guarda `maquina` —host y plataforma, porque WSL y Windows comparten host y no pids— e `inicio` del proceso, y en la misma máquina el lock solo se rompe si el dueño murió o su pid es ya de otro; el reloj no interviene. En Windows el pid se consulta con `OpenProcess`, nunca con `os.kill`, que lo terminaría. Queda declarado el límite que no tiene arreglo en un lock de ficheros: un dueño de otra máquina —una carpeta sincronizada— o un `owner.json` anterior siguen caducando por edad.) |

| Baseline | Norma | Congelado | Objetivo | Pendiente |
|---|---|---|---|---|
| `scripts/arch-baseline.json` | cruces entre contextos | 34 | ≤ 30 para 2027-03-31 · cada 90 d · meta_toolkit — vault_arch → **en_plazo** | 37 → 37 → 37 → 37 → 37 → 34 (encoge, Δ-3) |
| `scripts/arch-baseline.json` | cruces fuera de puerto | 0 | ≤ 4 para 2027-03-31 · cada 90 d · meta_toolkit — vault_arch → **cumple** | 8 → 8 → 6 → 5 → 5 → 0 (encoge, Δ-8) |
| `scripts/blame-baseline.json` | AP-51 | 30 | ≤ 20 para 2027-03-31 · cada 90 d · meta_toolkit — vault_blame_audit → **en_plazo** | 30 → 30 → 30 → 30 → 30 → 30 (encoge, Δ-56) |
| `scripts/error-contract-baseline.json` | AP-52 | 0 | ≤ 0 para 2027-06-30 · cada 180 d · meta_toolkit — vault_error_contract → **cumple** | 110 → 110 → 0 → 9 → 0 → 0 (encoge, Δ-158) |
| `scripts/noop-baseline.json` | AP-37 | 0 | ≤ 0 para 2027-06-30 · cada 180 d · meta_toolkit — vault_noop_audit → **cumple** | 0 → 0 → 0 → 0 (plana, Δ+0) |
| `scripts/smoke-baseline.json` | AP-42 | 0 | ≤ 0 para 2027-06-30 · cada 180 d · meta_toolkit — vault_smoke → **cumple** | 0 → 0 (plana, Δ+0) |
| `scripts/toolkit-audit-baseline.json` | AP-42 — pero tool por tool: el ejemplo debe ejercitar la función declarada | 0 | ≤ 0 para 2027-06-30 · cada 180 d · meta_toolkit — vault_toolkit_audit → **cumple** | 0 → 19 → 1 → 0 (plana, Δ+0) |
| `scripts/blueprint-baseline.json` | capa 4 — norma sin puerta ni test | 0 | ≤ 4 para 2027-03-31 · cada 90 d · meta_toolkit — vault_blueprint → **cumple** | 13 → 8 → 8 → 3 → 1 → 0 (encoge, Δ-16) |
| `scripts/criterios-baseline.json` | AP-57 | 2 | ≤ 6 para 2027-03-31 · cada 90 d · meta_toolkit — vault_criterios → **cumple** | 9 → 9 → 9 → 9 → 7 → 2 (encoge, Δ-8) |
| `scripts/ciclos-baseline.json` | AP-58 — ciclo esquivado con import diferido | 3 | ≤ 2 para 2027-03-31 · cada 90 d · meta_toolkit — vault_ciclos → **en_plazo** | 15 → 14 → 7 → 5 → 5 → 3 (encoge, Δ-27) |
| `scripts/kernel-baseline.json` | AP-59 — núcleo declarado sin contraste | 4 | ≤ 2 para 2027-03-31 · cada 90 d · meta_toolkit — vault_kernel → **en_plazo** | 5 → 6 → 6 → 5 → 4 → 4 (encoge, Δ-1) |
| `scripts/norms-distincion-baseline.json` | AP-60 — normas que no declaran de qué se distinguen | 0 | ≤ 0 para 2027-06-30 · cada 180 d · meta_toolkit — vault_norms_distincion → **cumple** | 57 → 0 → 0 → 0 (encoge, Δ-57) |
| `scripts/norms-coherence-baseline.json` | AP-55 — C2, afirmación sin traza | 0 | ≤ 0 para 2027-06-30 · cada 180 d · meta_toolkit — vault_norms_coherence → **cumple** | 47 → 0 → 0 → 0 (encoge, Δ-47) |
| `scripts/field-compat-baseline.json` | contrato de campos con los consumidores | 1471 | — *no aplica*: No es deuda: es el contrato de campos estables con los repos consumidores y crece por diseño cada vez que una tool publica un campo nuevo (1334 → 1410 entre 2026-08-30 y 2026-10-08). Lo que la puerta vigila es que ningún campo desaparezca sin `superseded_fields`, no su tamaño. Declarado el 2026-10-09 con la deuda #8. | 1427 → 1435 → 1437 → 1436 → 1448 → 1471 (crece, Δ+137) |
| `scripts/excepcion-declarada-baseline.json` | AP-61 — la excepción declarada no es la que escapa | 0 | ≤ 0 para 2027-06-30 · cada 180 d · gobernanza → **cumple** | 0 → 0 (plana, Δ+0) |
| `scripts/recursos-baseline.json` | AP-62 — el consumidor cruza para leer un recurso y paga el fan-out | 2 | ≤ 0 para 2027-03-31 · cada 90 d · meta_toolkit — vault_recursos → **en_plazo** | 2 → 2 (plana, Δ+0) |
| `scripts/rutas-baseline.json` | v41.21 — el layout del repo escrito como literal fuera de su dueño vault/kernel/rutas.py; solo encoge | 16 | ≤ 16 para 2027-06-30 · cada 90 d · meta_toolkit — vault.kernel.rutas → **cumple** | 177 → 175 → 16 (encoge, Δ-161) |
| `scripts/clones-baseline.json` | CN-05 — cuerpos duplicados que no se pueden fusionar sin cruzar una frontera | 3 | ≤ 2 para 2027-03-31 · cada 90 d · meta_toolkit ? vault_clones → **en_plazo** | 4 → 3 (encoge, Δ-1) |

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

*27 puertas de cierre. Generado por `scripts/vault_blueprint.py`.*
