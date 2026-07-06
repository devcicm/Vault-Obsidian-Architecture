# Antipatterns -- Antipatrones

> Documento bilingüe. Catálogo completo de AP-01..AP-35, SP-01..03, CN-01..03 + PAT-1..6 del vault.
> Bilingual document. Full AP-01..AP-35, SP-01..03, CN-01..03 + PAT-1..6 catalog.

---

## ES

Total de antipatrones registrados: 36 antipatrones + 6 patrones (PAT) + 3 protocolos de sesión (SP) + 3 convenciones (CN)

### AP-01: Documentación alucinada

- **Severidad:** high
- **Enforcement:** manual
- **Detectado por:** manual

Documentar herramientas, endpoints, funciones o comportamientos que no existen en el código real. El agente genera información convincente pero incorrecta.

**Prevención:** Verificar existencia real antes de documentar. vault_read + grep sobre el código fuente.

### AP-02: Proliferación de versiones del mismo documento

- **Severidad:** high
- **Enforcement:** audit
- **Detectado por:** vault_audit

Múltiples notas describiendo la misma entidad: status-v1.md, status-v2.md, status-final.md, status-final2.md. Variantes: same-folder (AP-02), cross-folder (AP-18), canonical-shadow (AP-17).

**Prevención:** Una nota por entidad. Usar .history/ para versiones anteriores (vault_write lo gestiona automáticamente).

### AP-03: Stubs sin política de expansión

- **Severidad:** medium
- **Enforcement:** audit
- **Detectado por:** vault_audit

Nota con contenido real pero incompleto (≥3 líneas reales) sin fecha de expansión. Distinción con AP-11: AP-03 tiene información útil, AP-11 no tiene ningún contenido real.

**Prevención:** Agregar meta: {status: stub, expand_by: YYYY-MM-DD} al crear stubs. Enriquecer en cada sesión.

### AP-04: Features aspiracionales documentadas como implementadas

- **Severidad:** high
- **Enforcement:** manual
- **Detectado por:** manual

Documentar comportamientos futuros o planeados como si ya existieran. Confunde al agente sobre el estado real del sistema.

**Prevención:** Usar status: planned/in-progress/implemented. Nunca describir en presente algo que no está deployado.

### AP-05: Múltiples fuentes de verdad para el mismo dato

- **Severidad:** critical
- **Enforcement:** manual
- **Detectado por:** manual

El mismo dato (IP, URL, versión, configuración) aparece en múltiples notas con valores inconsistentes. Causa decisiones del agente basadas en datos erróneos.

**Prevención:** PAT-1 (canonical source anchoring): una nota canónica por dato, las demás hacen [[wiki-link]] a ella.

### AP-06: Templates sin instancias reales

- **Severidad:** low
- **Enforcement:** manual
- **Detectado por:** manual

Archivos de template (SLOs, métricas, alertas, ADRs) que existen en el vault pero nunca se han instanciado con datos reales.

**Prevención:** Si un template no tiene instancias en 30 días, moverlo a 10_Migrated/ o eliminarlo.

### AP-07: ADRs incompletos

- **Severidad:** medium
- **Enforcement:** manual
- **Detectado por:** manual

ADRs (Architecture Decision Records) sin secciones Contexto, Opciones evaluadas y Consecuencias. Un ADR sin estas secciones no aporta valor de auditoría.

**Prevención:** Usar vault_write con template de ADR completo. vault_audit puede extenderse para validar secciones.

### AP-08: Documentación anclada a versiones obsoletas

- **Severidad:** medium
- **Enforcement:** manual
- **Detectado por:** manual

Notas que mencionan versiones específicas de librerías, APIs o protocolos que ya fueron actualizadas, sin indicar que el contenido puede estar desactualizado.

**Prevención:** Agregar campo version_pinned al frontmatter con la versión referenciada. vault_audit puede alertar.

### AP-09: Runbooks fuera de estructura

- **Severidad:** medium
- **Enforcement:** manual
- **Detectado por:** manual

Procedimientos operativos guardados en carpetas genéricas (07_Knowledge/, 01_Projects/) en lugar de 06_Runbooks/. Dificulta la localización en incidentes.

**Prevención:** Todo runbook va en 06_Runbooks/{proyecto}/. vault_migrate_docs para moverlos.

### AP-10: Migración sin plan de rollback

- **Severidad:** high
- **Enforcement:** manual
- **Detectado por:** manual

Ejecutar vault_migrate_docs sin tener vault_migrate_rollback disponible o sin snapshot previo. Si la migración introduce errores, no hay manera de revertir.

**Prevención:** PAT-4 (phased audit): siempre snapshot → migrate → verify → rollback si falla.

### AP-11: Skeleton files -- frontmatter válido, contenido vacío

- **Severidad:** critical
- **Enforcement:** guard
- **Detectado por:** vault_audit

Nota creada con frontmatter correcto pero cuerpo vacío o solo con TODO/placeholders. El agente indexa la nota pero no recibe información útil de ella. Distinción con AP-03: AP-11 = 0 líneas reales; AP-03 = ≥3 líneas reales pero incompleto.

**Prevención:** vault_write exige ≥3 líneas de contenido real (00_System exempt). No crear notas que no estén listas.

### AP-12: Frontmatter inconsistente entre notas del mismo tipo

- **Severidad:** high
- **Enforcement:** audit
- **Detectado por:** vault_validate, vault_audit

Notas del mismo tipo con campos faltantes, tipos mezclados (timestamp con/sin comillas, migratedFrom relativo vs absoluto). Rompe vault_list, búsquedas y deduplicación.

**Prevención:** vault_write como único punto de creación; nunca editar frontmatter manualmente.

### AP-13: Timestamps inválidos o incompletos en frontmatter

- **Severidad:** high
- **Enforcement:** audit
- **Detectado por:** vault_audit

Timestamps solo con fecha (2026-05-07), con '...' literal, sin zona horaria o en formato no ISO 8601. vault_diff y vault_timeline no pueden ordenar versiones.

**Prevención:** vault_write genera timestamps con datetime.now(timezone.utc).isoformat() automáticamente.

### AP-14: Wiki-links rotos o vacíos

- **Severidad:** critical
- **Enforcement:** guard+audit
- **Detectado por:** vault_audit, vault_graph

[[]] vacíos, [[ ]] con espacio, links a notas renombradas/eliminadas, o links con path (AP-21). Dos causas raíz: (a) wrong stem, (b) path-anchored. El agente sigue links que no resuelven.

**Prevención:** Solo escribir [[wiki-link]] cuando la nota destino ya existe. vault_search() antes de linkar.

### AP-15: Archivos externos depositados en la raíz del vault

- **Severidad:** high
- **Enforcement:** manual
- **Detectado por:** vault_audit

Archivos .md colocados directamente en vault-{nombre}/ en lugar de en secciones numeradas. vault_graph parsea sus [[wiki-links]] como broken links reales del proyecto.

**Prevención:** Layout correcto: vault/ y scripts/ son hermanos, nunca anidados. Solo 00_System…11_Code y 99_Index son destinos válidos.

### AP-16: Sin identificador de agente en frontmatter

- **Severidad:** medium
- **Enforcement:** audit
- **Detectado por:** vault_audit

Nota sin campo agent: en el frontmatter. Sin este campo es imposible auditar qué agente creó o modificó la nota (PAT-5: frontmatter as provenance chain).

**Prevención:** vault_write agrega agent: automáticamente. Valores estándar: claude, system, human.

### AP-17: Canonical-shadow duplication

- **Severidad:** medium
- **Enforcement:** audit
- **Detectado por:** vault_audit

Par de notas con SequenceMatcher ratio ≥ 0.85 en títulos. Típicamente una nota thin creada cuando ya existía la canónica rica. Penalización vault_audit: −2 por par.

**Prevención:** PAT-3: buscar con vault_search() antes de crear. Si existe una nota similar, enriquecer en lugar de crear.

### AP-18: Cross-folder content duplication

- **Severidad:** high
- **Enforcement:** audit
- **Detectado por:** vault_audit

Mismo contenido byte-idéntico (MD5) en carpetas distintas. Penalización vault_audit: −3 por par.

**Prevención:** PAT-1: una nota canónica, las demás hacen [[wiki-link]]. Usar vault_change_log --action deleted antes de borrar.

### AP-19: Shadow indexing

- **Severidad:** medium
- **Enforcement:** manual
- **Detectado por:** manual

Índices de sección creados manualmente, duplicando lo que vault_section_index genera automáticamente. Los índices manuales rotan en AP-02 con el tiempo.

**Prevención:** vault_section_index es la única herramienta para índices. No editar index.md manualmente.

### AP-20: Deceptive skeleton (empty-list)

- **Severidad:** critical
- **Enforcement:** guard
- **Detectado por:** manual

Nota que pasa el content gate de 3 líneas porque tiene bullets, pero >50% de los bullets están vacíos (- , - [ ], - []). Variante de AP-11 que evade el guard básico.

**Prevención:** vault_write rechaza si empty_bullets/total_bullets > 0.5. Completar los bullets antes de guardar.

### AP-21: Path-anchored wiki-links

- **Severidad:** critical
- **Enforcement:** guard
- **Detectado por:** manual

[[carpeta/nota]] en lugar de [[nota]]. Obsidian no resuelve paths, solo stems. El link siempre aparece roto en el grafo.

**Prevención:** Siempre [[stem]] o [[stem|título visible]]. vault_section_index genera solo [[stem|título]] desde v25.

### AP-22: Bracket sanity -- corchetes desbalanceados o vacíos

- **Severidad:** critical
- **Enforcement:** guard+audit
- **Detectado por:** vault_audit

Corchetes [[ sin ]] matching, o [[]] vacíos. Se detecta fuera de bloques de código. vault_write bloquea (hard stop). vault_write también advierte (non-blocking) si [[target]] no existe: ghost_links[].

**Prevención:** Cada [[ debe tener su ]]. Nunca escribir [[]] vacíos. Verificar que el target exista antes de linkar.

### AP-23: Note complexity ceiling -- nota demasiado larga

- **Severidad:** medium
- **Enforcement:** audit
- **Detectado por:** vault_write, vault_norms

Una nota con más de 500 líneas de contenido real se vuelve difícil de mantener y consume excesivo contexto del LLM. Debe dividirse en sub-notas canónicas interconectadas con [[wiki-links]] desde la nota original.

**Prevención:** Al superar 500 líneas, crear sub-notas en la misma carpeta y reemplazar la sección con [[sub-nota|título]]. La nota original actúa como índice/resumen.

### AP-24: Bracket imbalance -- corchetes sin pareja, anidados o invertidos

- **Severidad:** high
- **Enforcement:** guard+audit
- **Detectado por:** vault_audit, vault_render_check

Wiki-links malformados por desbalance de corchetes. Tres variantes: (1) apertura sin cierre ([[nota sin ]]), (2) cierre sin apertura (]] sin [[), (3) anidamiento incorrecto ([[[[nota]]]] o [[nota]]]]). En Obsidian el link se renderiza como texto literal, no como enlace navegable. Rompe la trazabilidad y produce falsos negativos en vault_audit --broken-links.

**Prevención:** Usar siempre el formato [[stem]] o [[stem|alias]]. Validar balance con vault_render_check --fix antes de commit. El content_gate de vault_write rechaza contenido con bracket imbalance.

### AP-25: Mermaid diagram syntax errors -- nodos/tipos no definidos

- **Severidad:** medium
- **Enforcement:** audit
- **Detectado por:** vault_audit, vault_mermaid_check

Diagramas Mermaid con sintaxis inválida: tipos de diagrama no reconocidos (unknown_type), nodos referenciados pero no definidos (undefined_node), flechas huérfanas, o sintaxis de etiquetas incorrecta. El diagrama no se renderiza en Obsidian y pierde su valor documental.

**Prevención:** Validar con vault_mermaid_check antes de commit. Usar tipos conocidos (graph TD, flowchart LR, sequenceDiagram, classDiagram, etc.). Asegurar que cada nodo referenciado en una flecha exista como definición previa.

### AP-31: Grafo sin tipos semánticos — edges sin predicate explícito

- **Severidad:** high
- **Enforcement:** audit
- **Detectado por:** vault_audit, vault_graph_merge

Todas las aristas del grafo usan el mismo tipo 'wiki-link' sin distinguir semántica: depends_on, implements, extends, calls, documents, etc. Sin predicates tipados, el análisis de impacto y las búsquedas semánticas no pueden filtrar por tipo de relación. La solución es mergear las relaciones de entidad (vault_relation_add) y código (vault_code_relation) en el grafo para enriquecerlo con predicates.

**Prevención:** Ejecutar vault_graph --typed periódicamente para generar graph-enriched.json con predicates semánticos unificados.

### AP-32: Relaciones tipadas sin predicate válido en la ontología

- **Severidad:** medium
- **Enforcement:** audit
- **Detectado por:** vault_graph_merge, vault_audit

Una relación registrada en entity relations o code relations usa un relationType/type que no existe en vault-ontology.json. Esto produce edges que no pueden interpretarse semánticamente en el grafo enriquecido. Ej: relationType='inherits' cuando el predicate canónico es 'extends'.

**Prevención:** Validar nuevos predicates contra vault-ontology.json. Usar los 18 predicates canónicos definidos: depends_on, implements, extends, calls, imports, uses, has_many, belongs_to, produces, consumes, configures, routes_to, monitors, secures, documents, deploys, tests, orquestrates.

### AP-33: Predicado no canónico — sinónimo no normalizado

- **Severidad:** low
- **Enforcement:** audit
- **Detectado por:** vault_graph_merge

Las relaciones de entidad usan `relationType` y las de código usan `type` para el mismo concepto semántico. Además, predicates que semánticamente son equivalentes deben unificarse: `imports` en código ≈ `depends_on` a nivel build-time. La ontología define el mapeo de sinónimos.

**Prevención:** Usar los predicates canónicos de vault-ontology.json. vault_graph_merge auto-mapea sinónimos al predicate canónico.

### AP-34: Relación tipada huérfana — endpoint inexistente en el vault

- **Severidad:** high
- **Enforcement:** audit
- **Detectado por:** vault_audit, vault_graph_merge

Una relación tipada (entity o code) referencia un endpoint que no existe como nota en el vault. Ej: relación `User -- has_many --> Order` donde no existen `User.md` ni `Order.md`. El grafo enriquecido tendrá edges hacia nodos fantasma que nunca resolverán.

**Prevención:** Crear las notas correspondientes en el vault antes de registrar relaciones. vault_graph_merge detecta y reporta huérfanos con fuzzy matching para sugerir el note path más probable.

### AP-35: Silos de relación — sistemas de grafos aislados

- **Severidad:** high
- **Enforcement:** audit
- **Detectado por:** vault_audit, vault_graph_merge

El vault mantiene tres sistemas de relaciones en silos aislados: (a) wiki-links en graph.json, (b) entity relations en 06_Diagrams/entity/*-relations.json, (c) code relations en 11_Code/.code-index.json. Ninguno de estos sistemas se integra con los otros, produciendo un grafo de conocimiento fragmentado. vault_impact y BFS solo ven wiki-links, ignorando relaciones semánticas ricas registradas en los otros sistemas.

**Prevención:** Ejecutar vault_graph --typed al final de cada sesión productiva para generar graph-enriched.json unificado con todos los sistemas de relaciones. vault_impact acepta --predicate para filtrar BFS por tipo semántico.

### SP-01: Delete protocol — change_log obligatorio antes de eliminar

- **Severidad:** critical
- **Enforcement:** manual
- **Detectado por:** vault_audit

Antes de eliminar cualquier nota del vault, el agente DEBE llamar: vault_change_log --action deleted --path <nota> --reason <motivo>. Sin este registro, la nota desaparece sin rastro auditado.

**Prevención:** No eliminar notas directamente. Usar el protocolo: change_log → respaldar → eliminar.

### SP-02: Forward-link verification — buscar antes de linkar

- **Severidad:** high
- **Enforcement:** guard
- **Detectado por:** vault_graph, vault_audit

Antes de escribir [[nombre-nota]] en contenido, verificar que la nota destino ya existe: vault_search(query:'nombre-nota'). Si no hay resultado, escribir en texto plano hasta que la nota exista. vault_write advierte con ghost_links[] (no bloquea) si el target no existe.

**Prevención:** Usar vault_search antes de crear wikilinks. Preferir [[nombre-nota|alias descriptivo]].

### SP-03: Session snapshot pattern — delta antes de operaciones masivas

- **Severidad:** medium
- **Enforcement:** manual
- **Detectado por:** vault_delta

Antes de cualquier operación masiva (migración, rename en lote, vault_tags --rename múltiple, delete en lote), capturar snapshot con vault_delta --snapshot. Permite detectar regresiones y calcular impacto real de la operación.

**Prevención:** vault_delta --snapshot antes de toda operación masiva; vault_delta --report después para verificar.

### CN-01: Kebab-case filenames — nombres de archivo en minúsculas con guiones

- **Severidad:** high
- **Enforcement:** guard
- **Detectado por:** vault_validate

Los archivos .md del vault deben usar kebab-case: minúsculas, palabras separadas por guiones, sin espacios ni caracteres especiales. vault_write aplica slugify() automáticamente al título para generar el filename. Ej: 'ADR-001 Auth Decision' → adr-001-auth-decision.md.

**Prevención:** Usar vault_write para crear notas (aplica slugify automáticamente). No crear archivos manualmente.

### CN-02: Numbered folder structure — secciones numeradas como únicos destinos

- **Severidad:** high
- **Enforcement:** manual
- **Detectado por:** vault_validate

Solo las 16 secciones numeradas son destinos válidos para notas: 00_System, 01_Projects, 02_Observability, 03_Decisions, 04_Specs, 05_Patterns, 06_Runbooks, 07_Knowledge, 08_Integrations, 09_Architecture, 10_Migrated, 11_Code, 12_Bibliography, 13_Flows, 14_Requirements, 15_Tests, 16_AI_Governance, 99_Index. Crear carpetas ad-hoc o escribir en la raíz viola este estándar (ver AP-15).

**Prevención:** vault_folder_registry mantiene el registro canónico de carpetas. vault_write rechaza paths fuera de las secciones numeradas.

### CN-03: Standard status vocabulary — vocabulario canónico de meta.status

- **Severidad:** low
- **Enforcement:** manual
- **Detectado por:** vault_validate

El campo meta.status (o status en frontmatter) debe usar solo valores del vocabulario estándar: planned | in-progress | implemented | deprecated | archived | stub | template. Valores fuera del vocabulario rompen filtros de vault_list y vault_audit.

**Prevención:** Usar vault_write con parámetros estándar. vault_validate reporta status fuera del vocabulario.

### PAT-1: Canonical source anchoring — una nota canónica por dominio

- **Severidad:** N/A (patrón recomendado)
- **Enforcement:** recommended
- **Detectado por:** vault_audit

Un dominio = una nota canónica rica. Todas las referencias desde otros contextos son [[wiki-links]] a esa nota canónica, nunca copias del contenido.

**Aplicación:** Identificar la nota con más backlinks y contenido para cada dominio. Redirigir todas las referencias hacia la canónica.

### PAT-2: Stub enrichment gradient — enriquecimiento progresivo de stubs

- **Severidad:** N/A (patrón recomendado)
- **Enforcement:** recommended
- **Detectado por:** vault_audit

Un stub con ≥3 líneas reales se enriquece progresivamente en cada sesión que lo toca. La eliminación solo aplica a skeletons (AP-11) y deceptive skeletons (AP-20).

**Aplicación:** En cada sesión, buscar stubs del proyecto activo y añadir al menos 3 líneas de contenido real.

### PAT-3: Duplicate chain resolution — resolución estándar de duplicados

- **Severidad:** N/A (patrón recomendado)
- **Enforcement:** recommended
- **Detectado por:** vault_audit

Algoritmo estándar para resolver duplicados: identificar canónica (más backlinks, más contenido, ubicación más apropiada) → change_log --action deleted → mover a 10_Migrated/ → actualizar wiki-links rotos → verificar con vault_audit.

**Aplicación:** Usar vault_graph_fix para resolver duplicados automáticamente con el wizard interactivo.

### PAT-4: Phased audit execution — ejecución de auditorías en 4 fases

- **Severidad:** N/A (patrón recomendado)
- **Enforcement:** recommended
- **Detectado por:** vault_drift_detect

Las auditorías masivas se ejecutan en 4 fases atómicas: 1-Snapshot (vault_drift_detect --snapshot), 2-Detección (vault_audit), 3-Resolución (vault_write, vault_change_log), 4-Verificación (vault_drift_detect --report).

**Aplicación:** Establecer este flujo como práctica estándar antes de cualquier sesión de limpieza del vault.

### PAT-5: Frontmatter as provenance chain — cadena de custodia via frontmatter

- **Severidad:** N/A (patrón recomendado)
- **Enforcement:** recommended
- **Detectado por:** vault_audit

Los campos id + createdAt + updatedAt + agent + migratedFrom (si aplica) forman una cadena de custodia completa. Sin esta cadena es imposible auditar de dónde vino un dato o qué agente lo introdujo.

**Aplicación:** vault_write genera automáticamente id, createdAt, updatedAt y agent. vault_migrate_docs añade migratedFrom.

### PAT-6: Semantic graph enrichment — enriquecimiento periódico del grafo

- **Severidad:** N/A (patrón recomendado)
- **Enforcement:** recommended
- **Detectado por:** vault_graph_merge, vault_audit

Ejecutar vault_graph --typed al final de cada sesión productiva para generar graph-enriched.json con predicates semánticos unificados. El grafo enriquecido combina wiki-links, entity relations y code relations en un solo grafo consultable con filtros por predicate, cardinalidad y tipo de nodo.

**Aplicación:** vault_graph --typed al final de cada sesión. vault_impact --predicate depends_on para análisis de impacto semántico.

---

## EN

Total registered antipatterns: 36 antipatterns + 6 patterns (PAT) + 3 session protocols (SP) + 3 conventions (CN)

### AP-01: Documentación alucinada

- **Severity:** high
- **Enforcement:** manual
- **Detected by:** manual

Documentar herramientas, endpoints, funciones o comportamientos que no existen en el código real. El agente genera información convincente pero incorrecta.

**Prevention:** Verificar existencia real antes de documentar. vault_read + grep sobre el código fuente.

### AP-02: Proliferación de versiones del mismo documento

- **Severity:** high
- **Enforcement:** audit
- **Detected by:** vault_audit

Múltiples notas describiendo la misma entidad: status-v1.md, status-v2.md, status-final.md, status-final2.md. Variantes: same-folder (AP-02), cross-folder (AP-18), canonical-shadow (AP-17).

**Prevention:** Una nota por entidad. Usar .history/ para versiones anteriores (vault_write lo gestiona automáticamente).

### AP-03: Stubs sin política de expansión

- **Severity:** medium
- **Enforcement:** audit
- **Detected by:** vault_audit

Nota con contenido real pero incompleto (≥3 líneas reales) sin fecha de expansión. Distinción con AP-11: AP-03 tiene información útil, AP-11 no tiene ningún contenido real.

**Prevention:** Agregar meta: {status: stub, expand_by: YYYY-MM-DD} al crear stubs. Enriquecer en cada sesión.

### AP-04: Features aspiracionales documentadas como implementadas

- **Severity:** high
- **Enforcement:** manual
- **Detected by:** manual

Documentar comportamientos futuros o planeados como si ya existieran. Confunde al agente sobre el estado real del sistema.

**Prevention:** Usar status: planned/in-progress/implemented. Nunca describir en presente algo que no está deployado.

### AP-05: Múltiples fuentes de verdad para el mismo dato

- **Severity:** critical
- **Enforcement:** manual
- **Detected by:** manual

El mismo dato (IP, URL, versión, configuración) aparece en múltiples notas con valores inconsistentes. Causa decisiones del agente basadas en datos erróneos.

**Prevention:** PAT-1 (canonical source anchoring): una nota canónica por dato, las demás hacen [[wiki-link]] a ella.

### AP-06: Templates sin instancias reales

- **Severity:** low
- **Enforcement:** manual
- **Detected by:** manual

Archivos de template (SLOs, métricas, alertas, ADRs) que existen en el vault pero nunca se han instanciado con datos reales.

**Prevention:** Si un template no tiene instancias en 30 días, moverlo a 10_Migrated/ o eliminarlo.

### AP-07: ADRs incompletos

- **Severity:** medium
- **Enforcement:** manual
- **Detected by:** manual

ADRs (Architecture Decision Records) sin secciones Contexto, Opciones evaluadas y Consecuencias. Un ADR sin estas secciones no aporta valor de auditoría.

**Prevention:** Usar vault_write con template de ADR completo. vault_audit puede extenderse para validar secciones.

### AP-08: Documentación anclada a versiones obsoletas

- **Severity:** medium
- **Enforcement:** manual
- **Detected by:** manual

Notas que mencionan versiones específicas de librerías, APIs o protocolos que ya fueron actualizadas, sin indicar que el contenido puede estar desactualizado.

**Prevention:** Agregar campo version_pinned al frontmatter con la versión referenciada. vault_audit puede alertar.

### AP-09: Runbooks fuera de estructura

- **Severity:** medium
- **Enforcement:** manual
- **Detected by:** manual

Procedimientos operativos guardados en carpetas genéricas (07_Knowledge/, 01_Projects/) en lugar de 06_Runbooks/. Dificulta la localización en incidentes.

**Prevention:** Todo runbook va en 06_Runbooks/{proyecto}/. vault_migrate_docs para moverlos.

### AP-10: Migración sin plan de rollback

- **Severity:** high
- **Enforcement:** manual
- **Detected by:** manual

Ejecutar vault_migrate_docs sin tener vault_migrate_rollback disponible o sin snapshot previo. Si la migración introduce errores, no hay manera de revertir.

**Prevention:** PAT-4 (phased audit): siempre snapshot → migrate → verify → rollback si falla.

### AP-11: Skeleton files -- frontmatter válido, contenido vacío

- **Severity:** critical
- **Enforcement:** guard
- **Detected by:** vault_audit

Nota creada con frontmatter correcto pero cuerpo vacío o solo con TODO/placeholders. El agente indexa la nota pero no recibe información útil de ella. Distinción con AP-03: AP-11 = 0 líneas reales; AP-03 = ≥3 líneas reales pero incompleto.

**Prevention:** vault_write exige ≥3 líneas de contenido real (00_System exempt). No crear notas que no estén listas.

### AP-12: Frontmatter inconsistente entre notas del mismo tipo

- **Severity:** high
- **Enforcement:** audit
- **Detected by:** vault_validate, vault_audit

Notas del mismo tipo con campos faltantes, tipos mezclados (timestamp con/sin comillas, migratedFrom relativo vs absoluto). Rompe vault_list, búsquedas y deduplicación.

**Prevention:** vault_write como único punto de creación; nunca editar frontmatter manualmente.

### AP-13: Timestamps inválidos o incompletos en frontmatter

- **Severity:** high
- **Enforcement:** audit
- **Detected by:** vault_audit

Timestamps solo con fecha (2026-05-07), con '...' literal, sin zona horaria o en formato no ISO 8601. vault_diff y vault_timeline no pueden ordenar versiones.

**Prevention:** vault_write genera timestamps con datetime.now(timezone.utc).isoformat() automáticamente.

### AP-14: Wiki-links rotos o vacíos

- **Severity:** critical
- **Enforcement:** guard+audit
- **Detected by:** vault_audit, vault_graph

[[]] vacíos, [[ ]] con espacio, links a notas renombradas/eliminadas, o links con path (AP-21). Dos causas raíz: (a) wrong stem, (b) path-anchored. El agente sigue links que no resuelven.

**Prevention:** Solo escribir [[wiki-link]] cuando la nota destino ya existe. vault_search() antes de linkar.

### AP-15: Archivos externos depositados en la raíz del vault

- **Severity:** high
- **Enforcement:** manual
- **Detected by:** vault_audit

Archivos .md colocados directamente en vault-{nombre}/ en lugar de en secciones numeradas. vault_graph parsea sus [[wiki-links]] como broken links reales del proyecto.

**Prevention:** Layout correcto: vault/ y scripts/ son hermanos, nunca anidados. Solo 00_System…11_Code y 99_Index son destinos válidos.

### AP-16: Sin identificador de agente en frontmatter

- **Severity:** medium
- **Enforcement:** audit
- **Detected by:** vault_audit

Nota sin campo agent: en el frontmatter. Sin este campo es imposible auditar qué agente creó o modificó la nota (PAT-5: frontmatter as provenance chain).

**Prevention:** vault_write agrega agent: automáticamente. Valores estándar: claude, system, human.

### AP-17: Canonical-shadow duplication

- **Severity:** medium
- **Enforcement:** audit
- **Detected by:** vault_audit

Par de notas con SequenceMatcher ratio ≥ 0.85 en títulos. Típicamente una nota thin creada cuando ya existía la canónica rica. Penalización vault_audit: −2 por par.

**Prevention:** PAT-3: buscar con vault_search() antes de crear. Si existe una nota similar, enriquecer en lugar de crear.

### AP-18: Cross-folder content duplication

- **Severity:** high
- **Enforcement:** audit
- **Detected by:** vault_audit

Mismo contenido byte-idéntico (MD5) en carpetas distintas. Penalización vault_audit: −3 por par.

**Prevention:** PAT-1: una nota canónica, las demás hacen [[wiki-link]]. Usar vault_change_log --action deleted antes de borrar.

### AP-19: Shadow indexing

- **Severity:** medium
- **Enforcement:** manual
- **Detected by:** manual

Índices de sección creados manualmente, duplicando lo que vault_section_index genera automáticamente. Los índices manuales rotan en AP-02 con el tiempo.

**Prevention:** vault_section_index es la única herramienta para índices. No editar index.md manualmente.

### AP-20: Deceptive skeleton (empty-list)

- **Severity:** critical
- **Enforcement:** guard
- **Detected by:** manual

Nota que pasa el content gate de 3 líneas porque tiene bullets, pero >50% de los bullets están vacíos (- , - [ ], - []). Variante de AP-11 que evade el guard básico.

**Prevention:** vault_write rechaza si empty_bullets/total_bullets > 0.5. Completar los bullets antes de guardar.

### AP-21: Path-anchored wiki-links

- **Severity:** critical
- **Enforcement:** guard
- **Detected by:** manual

[[carpeta/nota]] en lugar de [[nota]]. Obsidian no resuelve paths, solo stems. El link siempre aparece roto en el grafo.

**Prevention:** Siempre [[stem]] o [[stem|título visible]]. vault_section_index genera solo [[stem|título]] desde v25.

### AP-22: Bracket sanity -- corchetes desbalanceados o vacíos

- **Severity:** critical
- **Enforcement:** guard+audit
- **Detected by:** vault_audit

Corchetes [[ sin ]] matching, o [[]] vacíos. Se detecta fuera de bloques de código. vault_write bloquea (hard stop). vault_write también advierte (non-blocking) si [[target]] no existe: ghost_links[].

**Prevention:** Cada [[ debe tener su ]]. Nunca escribir [[]] vacíos. Verificar que el target exista antes de linkar.

### AP-23: Note complexity ceiling -- nota demasiado larga

- **Severity:** medium
- **Enforcement:** audit
- **Detected by:** vault_write, vault_norms

Una nota con más de 500 líneas de contenido real se vuelve difícil de mantener y consume excesivo contexto del LLM. Debe dividirse en sub-notas canónicas interconectadas con [[wiki-links]] desde la nota original.

**Prevention:** Al superar 500 líneas, crear sub-notas en la misma carpeta y reemplazar la sección con [[sub-nota|título]]. La nota original actúa como índice/resumen.

### AP-24: Bracket imbalance -- corchetes sin pareja, anidados o invertidos

- **Severity:** high
- **Enforcement:** guard+audit
- **Detected by:** vault_audit, vault_render_check

Wiki-links malformados por desbalance de corchetes. Tres variantes: (1) apertura sin cierre ([[nota sin ]]), (2) cierre sin apertura (]] sin [[), (3) anidamiento incorrecto ([[[[nota]]]] o [[nota]]]]). En Obsidian el link se renderiza como texto literal, no como enlace navegable. Rompe la trazabilidad y produce falsos negativos en vault_audit --broken-links.

**Prevention:** Usar siempre el formato [[stem]] o [[stem|alias]]. Validar balance con vault_render_check --fix antes de commit. El content_gate de vault_write rechaza contenido con bracket imbalance.

### AP-25: Mermaid diagram syntax errors -- nodos/tipos no definidos

- **Severity:** medium
- **Enforcement:** audit
- **Detected by:** vault_audit, vault_mermaid_check

Diagramas Mermaid con sintaxis inválida: tipos de diagrama no reconocidos (unknown_type), nodos referenciados pero no definidos (undefined_node), flechas huérfanas, o sintaxis de etiquetas incorrecta. El diagrama no se renderiza en Obsidian y pierde su valor documental.

**Prevention:** Validar con vault_mermaid_check antes de commit. Usar tipos conocidos (graph TD, flowchart LR, sequenceDiagram, classDiagram, etc.). Asegurar que cada nodo referenciado en una flecha exista como definición previa.

### AP-31: Untyped graph — edges without explicit predicate

- **Severity:** high
- **Enforcement:** audit
- **Detected by:** vault_audit, vault_graph_merge

All graph edges use the same 'wiki-link' type without distinguishing semantics: depends_on, implements, extends, calls, documents, etc. Without typed predicates, impact analysis and semantic searches cannot filter by relationship type. The solution is to merge entity relations (vault_relation_add) and code relations (vault_code_relation) into the graph to enrich it with predicates.

**Prevention:** Run vault_graph --typed periodically to generate graph-enriched.json with unified semantic predicates.

### AP-32: Typed relations without valid ontology predicate

- **Severity:** medium
- **Enforcement:** audit
- **Detected by:** vault_graph_merge, vault_audit

A relation registered in entity or code relations uses a relationType/type that doesn't exist in vault-ontology.json. This produces edges that cannot be semantically interpreted. Example: relationType='inherits' when the canonical predicate is 'extends'.

**Prevention:** Validate new predicates against vault-ontology.json. Use the 18 canonical predicates.

### AP-33: Non-canonical predicate — unnormalized synonym

- **Severity:** low
- **Enforcement:** audit
- **Detected by:** vault_graph_merge

Entity relations use `relationType` and code relations use `type` for the same semantic concept. Semantically equivalent predicates must be unified: `imports` in code ≈ `depends_on` at build time.

**Prevention:** Use canonical predicates from vault-ontology.json. vault_graph_merge auto-maps synonyms.

### AP-34: Orphan typed relation — nonexistent endpoint in vault

- **Severity:** high
- **Enforcement:** audit
- **Detected by:** vault_audit, vault_graph_merge

A typed relation references an endpoint that doesn't exist as a note in the vault. The enriched graph will have edges to ghost nodes that never resolve.

**Prevention:** Create corresponding notes in the vault before registering relations. vault_graph_merge detects orphans with fuzzy matching.

### AP-35: Relationship silos — isolated graph systems

- **Severity:** high
- **Enforcement:** audit
- **Detected by:** vault_audit, vault_graph_merge

The vault maintains three relationship systems in isolated silos: (a) wiki-links in graph.json, (b) entity relations, (c) code relations. None of these systems integrates with the others, producing a fragmented knowledge graph.

**Prevention:** Run vault_graph --typed at the end of each productive session.

### SP-01: Delete protocol — mandatory change_log before deletion

- **Severity:** critical
- **Enforcement:** manual
- **Detected by:** vault_audit

Before deleting any vault note, the agent MUST call: vault_change_log --action deleted --path <note> --reason <reason>. Without this record, the note disappears without an audit trail.

**Prevention:** Never delete notes directly. Use: change_log → backup → delete.

### SP-02: Forward-link verification — search before linking

- **Severity:** high
- **Enforcement:** guard
- **Detected by:** vault_graph, vault_audit

Before writing [[note-name]] in content, verify the target note exists: vault_search(query:'note-name'). If no result found, write as plain text until the note exists.

**Prevention:** Use vault_search before creating wikilinks. Prefer [[note-name|descriptive alias]].

### SP-03: Session snapshot pattern — delta before massive operations

- **Severity:** medium
- **Enforcement:** manual
- **Detected by:** vault_delta

Before any massive operation (migration, batch rename, batch delete), capture snapshot with vault_delta --snapshot. Enables regression detection and impact calculation.

**Prevention:** vault_delta --snapshot before all massive operations; vault_delta --report afterwards.

### CN-01: Kebab-case filenames — lowercase filenames with hyphens

- **Severity:** high
- **Enforcement:** guard
- **Detected by:** vault_validate

Vault .md files must use kebab-case: lowercase, words separated by hyphens, no spaces or special characters. vault_write applies slugify() automatically. Example: 'ADR-001 Auth Decision' → adr-001-auth-decision.md.

**Prevention:** Use vault_write to create notes (auto-applies slugify). Never create files manually.

### CN-02: Numbered folder structure — numbered sections as only destinations

- **Severity:** high
- **Enforcement:** manual
- **Detected by:** vault_validate

Only the 16 numbered sections are valid destinations for notes: 00_System through 16_AI_Governance and 99_Index. Creating ad-hoc folders or writing at root violates the standard (see AP-15).

**Prevention:** vault_folder_registry maintains the canonical folder registry. vault_write rejects paths outside numbered sections.

### CN-03: Standard status vocabulary — canonical meta.status vocabulary

- **Severity:** low
- **Enforcement:** manual
- **Detected by:** vault_validate

The meta.status field must use only standard vocabulary: planned | in-progress | implemented | deprecated | archived | stub | template. Values outside this set break vault_list and vault_audit filters.

**Prevention:** Use vault_write with standard parameters. vault_validate reports non-standard status values.

### PAT-1: Canonical source anchoring — one rich canonical note per domain

- **Severity:** N/A (recommended pattern)
- **Enforcement:** recommended
- **Detected by:** vault_audit

One domain = one rich canonical note. All references from other contexts are [[wiki-links]] to that canonical note, never content copies.

**Application:** Identify the note with most backlinks and content for each domain. Redirect all references to the canonical.

### PAT-2: Stub enrichment gradient — progressive stub enrichment

- **Severity:** N/A (recommended pattern)
- **Enforcement:** recommended
- **Detected by:** vault_audit

A stub with ≥3 real lines is progressively enriched each session that touches it. Deletion only applies to skeletons (AP-11) and deceptive skeletons (AP-20).

**Application:** Each session, find stubs for the active project and add at least 3 lines of real content.

### PAT-3: Duplicate chain resolution — standard duplicate resolution

- **Severity:** N/A (recommended pattern)
- **Enforcement:** recommended
- **Detected by:** vault_audit

Standard algorithm: identify canonical (most backlinks, most content, most appropriate location) → change_log --action deleted → move to 10_Migrated/ → update broken wiki-links → verify with vault_audit.

**Application:** Use vault_graph_fix to resolve duplicates automatically with the interactive wizard.

### PAT-4: Phased audit execution — 4-phase audit execution

- **Severity:** N/A (recommended pattern)
- **Enforcement:** recommended
- **Detected by:** vault_drift_detect

Massive audits run in 4 atomic phases: 1-Snapshot, 2-Detection, 3-Resolution, 4-Verification.

**Application:** Establish this flow as standard practice before any vault cleanup session.

### PAT-5: Frontmatter as provenance chain — audit chain via frontmatter

- **Severity:** N/A (recommended pattern)
- **Enforcement:** recommended
- **Detected by:** vault_audit

The fields id + createdAt + updatedAt + agent + migratedFrom form a complete chain of custody. Without this chain, it's impossible to audit data origins.

**Application:** vault_write auto-generates id, createdAt, updatedAt, and agent. vault_migrate_docs adds migratedFrom.

### PAT-6: Semantic graph enrichment — periodic graph enrichment

- **Severity:** N/A (recommended pattern)
- **Enforcement:** recommended
- **Detected by:** vault_graph_merge, vault_audit

Run vault_graph --typed at the end of each productive session to generate graph-enriched.json with unified semantic predicates.

**Application:** vault_graph --typed at end of each session. vault_impact --predicate depends_on for semantic impact analysis.
