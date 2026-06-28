# Antipatterns -- Antipatrones

> Documento bilingüe. Catálogo completo de AP-01..AP-25 del vault.
> Bilingual document. Full AP-01..AP-25 catalog.

---

## ES

Total de antipatrones registrados: 25

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

---

## EN

Total registered antipatterns: 25

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
