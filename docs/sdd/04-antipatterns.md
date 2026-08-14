# Antipatterns -- Antipatrones

> Documento bilingüe. Catálogo de normas completo: antipatrones AP-01..AP-61 más
> las familias PAT, SP y CN. Por familia: AP 61, CN 3, PAT 6, SP 3.
> Bilingual document. Full norm catalog: antipatterns AP-01..AP-61 plus the PAT,
> SP and CN families. By family: AP 61, CN 3, PAT 6, SP 3.

---

## ES

Total de normas registradas: 73 (AP 61, CN 3, PAT 6, SP 3)

### AP-01: Documentación alucinada

- **Severidad:** high
- **Enforcement:** audit
- **Detectado por:** sin detector -- Ninguna tool la detecta. Declaraba `vault_drift_detect`, que mide lo contrario: cambios en el código que la documentación no recoge. AP-01 es documentación que describe código inexistente, y para verla haría falta resolver cada referencia contra el repo.

Documentar herramientas, endpoints, funciones o comportamientos que no existen en el código real. El agente genera información convincente pero incorrecta.

**Prevención:** Verificar existencia real antes de documentar. vault_read + grep sobre el código fuente.

### AP-02: Proliferación de versiones del mismo documento

- **Severidad:** high
- **Enforcement:** audit
- **Detectado por:** sin detector -- Sus dos variantes hermanas sí se miden --AP-17 canonical-shadow y AP-18 cross-folder, ambas con penalización propia en vault_audit.PENALIZACIONES--, pero la variante same-folder que es AP-02 no la detecta nadie: `status-v1.md` y `status-v2.md` en la misma carpeta no son duplicados por hash (AP-18) ni pasan el umbral de similitud de título (AP-17). Declararlo aquí es lo que impide que la cobertura de las hermanas se lea como suya.

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
- **Enforcement:** audit
- **Detectado por:** sin detector -- Ninguna tool la detecta. `vault_drift_detect` compara hashes y git; distinguir "lo describe en presente" de "ya está deployado" exige leer el cuerpo de la nota contra el estado real, que hoy no hace nadie.

Documentar comportamientos futuros o planeados como si ya existieran. Confunde al agente sobre el estado real del sistema.

**Prevención:** Usar status: planned/in-progress/implemented. Nunca describir en presente algo que no está deployado.

### AP-05: Múltiples fuentes de verdad para el mismo dato

- **Severidad:** critical
- **Enforcement:** audit
- **Detectado por:** vault_fuente_unica

El mismo dato (IP, URL, versión, configuración) aparece en múltiples notas con valores inconsistentes. Causa decisiones del agente basadas en datos erróneos.

**Prevención:** PAT-1 (canonical source anchoring): una nota canónica por dato, las demás hacen [[wiki-link]] a ella.

### AP-06: Templates sin instancias reales

- **Severidad:** low
- **Enforcement:** audit
- **Detectado por:** vault_norms

Archivos de template (SLOs, métricas, alertas, ADRs) que existen en el vault pero nunca se han instanciado con datos reales.

**Prevención:** Si un template no tiene instancias en 30 días, moverlo a 10_Migrated/ o eliminarlo.

### AP-07: ADRs incompletos

- **Severidad:** medium
- **Enforcement:** audit
- **Detectado por:** vault_norms

ADRs (Architecture Decision Records) sin secciones Contexto, Opciones evaluadas y Consecuencias. Un ADR sin estas secciones no aporta valor de auditoría.

**Prevención:** Usar vault_write con template de ADR completo. vault_audit puede extenderse para validar secciones.

### AP-08: Documentación anclada a versiones obsoletas

- **Severidad:** medium
- **Enforcement:** audit
- **Detectado por:** sin detector -- Ninguna tool la detecta. Declaraba `vault_drift_detect`, que no lee versiones del cuerpo de la nota. La propia `prevention` lo dice en condicional --"vault_audit puede alertar"-- y ese condicional lleva desde v19 sin resolverse.

Notas que mencionan versiones específicas de librerías, APIs o protocolos que ya fueron actualizadas, sin indicar que el contenido puede estar desactualizado.

**Prevención:** Agregar campo version_pinned al frontmatter con la versión referenciada. vault_audit puede alertar.

### AP-09: Runbooks fuera de estructura

- **Severidad:** medium
- **Enforcement:** audit
- **Detectado por:** vault_norms

Procedimientos operativos guardados en carpetas genéricas (07_Knowledge/, 01_Projects/) en lugar de 06_Runbooks/. Dificulta la localización en incidentes.

**Prevención:** Todo runbook va en 06_Runbooks/{proyecto}/. vault_migrate_docs para moverlos.

### AP-10: Migración sin plan de rollback

- **Severidad:** high
- **Enforcement:** audit
- **Detectado por:** vault_norms

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
- **Detectado por:** vault_validate

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
- **Enforcement:** audit
- **Detectado por:** vault_norms

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
- **Enforcement:** audit
- **Detectado por:** vault_norms

Índices de sección creados manualmente, duplicando lo que vault_section_index genera automáticamente. Los índices manuales rotan en AP-02 con el tiempo.

**Prevención:** vault_section_index es la única herramienta para índices. No editar index.md manualmente.

### AP-20: Deceptive skeleton (empty-list)

- **Severidad:** critical
- **Enforcement:** guard
- **Detectado por:** sin detector declarado

Nota que pasa el content gate de 3 líneas porque tiene bullets, pero >50% de los bullets están vacíos (- , - [ ], - []). Variante de AP-11 que evade el guard básico.

**Prevención:** vault_write rechaza si empty_bullets/total_bullets > 0.5. Completar los bullets antes de guardar.

### AP-21: Path-anchored wiki-links

- **Severidad:** critical
- **Enforcement:** guard
- **Detectado por:** sin detector declarado

[[carpeta/nota]] en lugar de [[nota]]. Obsidian no resuelve paths, solo stems. El link siempre aparece roto en el grafo.

**Prevención:** Siempre [[stem]] o [[stem|título visible]]. vault_section_index genera solo [[stem|título]] desde v25.

### AP-22: Wiki-link vacío -- [[]] sin destino

- **Severidad:** medium
- **Enforcement:** guard+audit
- **Detectado por:** vault_audit, vault_fix_brackets

Wiki-link vacío: `[[]]` sin destino, fuera de bloques de código. No hay información que perder, así que la reparación es eliminarlo. vault_write bloquea (hard stop). vault_write también advierte (non-blocking) si [[target]] no existe: ghost_links[].

**Prevención:** Nunca escribir [[]] vacíos. Verificar que el target exista antes de linkar.

### AP-23: Note complexity ceiling -- nota demasiado larga

- **Severidad:** medium
- **Enforcement:** audit
- **Detectado por:** vault_write, vault_norms

Una nota con más de 500 líneas de contenido real se vuelve difícil de mantener y consume excesivo contexto del LLM. Debe dividirse en sub-notas canónicas interconectadas con [[wiki-links]] desde la nota original.

**Prevención:** Al superar 500 líneas, crear sub-notas en la misma carpeta y reemplazar la sección con [[sub-nota|título]]. La nota original actúa como índice/resumen.

### AP-24: Bracket imbalance -- corchetes sin pareja, anidados o invertidos

- **Severidad:** high
- **Enforcement:** guard+audit
- **Detectado por:** vault_audit, vault_fix_brackets

Wiki-links malformados por desbalance de corchetes. Tres variantes: (1) apertura sin cierre ([[nota sin ]]), (2) cierre sin apertura (]] sin [[), (3) anidamiento incorrecto ([[[[nota]]]] o [[nota]]]]). En Obsidian el link se renderiza como texto literal, no como enlace navegable. Rompe la trazabilidad y produce falsos negativos en vault_audit --broken-links.

**Prevención:** Usar siempre el formato [[stem]] o [[stem|alias]]. Validar balance con vault_fix_brackets --fix antes de commit. El content_gate de vault_write rechaza contenido con bracket imbalance.

### AP-25: Mermaid diagram syntax errors -- nodos/tipos no definidos

- **Severidad:** medium
- **Enforcement:** audit
- **Detectado por:** vault_audit, vault_mermaid_check

Diagramas Mermaid con sintaxis inválida: tipos de diagrama no reconocidos (unknown_type), nodos referenciados pero no definidos (undefined_node), flechas huérfanas, o sintaxis de etiquetas incorrecta. El diagrama no se renderiza en Obsidian y pierde su valor documental.

**Prevención:** Validar con vault_mermaid_check antes de commit. Usar tipos conocidos (graph TD, flowchart LR, sequenceDiagram, classDiagram, etc.). Asegurar que cada nodo referenciado en una flecha exista como definición previa.

### AP-26: Missing tags -- nota de contenido sin tags

- **Severidad:** medium
- **Enforcement:** audit
- **Detectado por:** vault_audit

Nota de contenido sin campo `tags` o con la lista vacía. Sin tags la nota es invisible para la búsqueda por facetas y no participa en los edges shared_tag del grafo: queda alcanzable solo por wiki-link directo.

**Prevención:** Pasar --tags en la tool de escritura. vault_ingest y vault_preferences los derivan automáticamente del origen y la categoría.

### AP-27: Missing type field -- nota sin tipo declarado

- **Severidad:** medium
- **Enforcement:** audit
- **Detectado por:** vault_audit

Nota sin campo `type`. El tipo es lo que ancla la nota a su sección canónica (CN-02): sin él no se puede verificar la coincidencia type ↔ carpeta que sostiene la dimensión de exactitud (F4).

**Prevención:** Declarar --type en la escritura; vault_audit lo cuenta en missing_type.

### AP-28: Missing frontmatter -- nota sin bloque YAML

- **Severidad:** high
- **Enforcement:** audit
- **Detectado por:** vault_audit, vault_validate

Nota sin bloque de frontmatter. Es el caso degenerado de AP-26/27/29/30 a la vez: sin frontmatter no hay id, ni agent, ni status, ni CIA, así que la nota queda fuera de toda métrica de calidad y de la cadena de trazabilidad (PAT-5).

**Prevención:** No editar .md a mano (SP-04). Escribir siempre por tool: atomic_write_text garantiza el bloque.

### AP-29: Missing status field -- nota sin estado de ciclo de vida

- **Severidad:** medium
- **Enforcement:** audit
- **Detectado por:** vault_audit, vault_norms

Nota sin campo `status`. Sin estado no se puede distinguir lo vigente de lo obsoleto, y la nota escapa al vocabulario controlado de CN-03: es la vía por la que contenido derogado sigue leyéndose como vigente.

**Prevención:** Declarar --status dentro de STATUS_VOCAB (12 valores).

### AP-30: Missing CIA classification -- nota sin clasificación de la tríada

- **Severidad:** high
- **Enforcement:** audit
- **Detectado por:** vault_audit

Nota sin `cia_integrity` / `cia_availability` / `cia_sensitivity`. Sin clasificación CIA la nota no puede endurecer su umbral de actualidad (30d → 15d en critical|high) ni ponderar su peso en el health score: el pilar del estándar queda sin aplicar sobre ella.

**Prevención:** Declarar los tres ejes en la escritura. vault_ingest asigna cia_integrity: low a lo ingerido por no estar verificado.

### AP-31: Grafo sin tipos semanticos -- edges sin predicate explícito

- **Severidad:** high
- **Enforcement:** audit
- **Detectado por:** vault_audit, vault_graph_merge

Todas las aristas del grafo usan el mismo tipo 'wiki-link' sin distinguir semántica: depends_on, implements, extends, calls, documents, etc. Sin predicates tipados, el analisis de impacto y las busquedas semanticas no pueden filtrar por tipo de relacion. La solucion es mergear las relaciones de entidad (vault_relation_add) y codigo (vault_code_relation) en el grafo para enriquecerlo con predicates.

**Prevención:** Ejecutar vault_graph --typed o vault_graph_merge periodicamente para enriquecer el grafo con predicates. Toda relacion registrada via vault_relation_add o vault_code_relation debe reflejarse en graph-enriched.json.

### AP-32: Relaciones tipadas sin predicate valido en la ontologia

- **Severidad:** medium
- **Enforcement:** audit
- **Detectado por:** vault_graph_merge

Una relacion registrada en entity relations o code relations usa un relationType/type que no existe en vault-ontology.json. Esto produce edges que no pueden interpretarse semanticamente en el grafo enriquecido. Ej: relationType='inherits' cuando el predicate canonico es 'extends'.

**Prevención:** Usar solo predicates del vocabulario canonico en vault-ontology.json. Para entity relations: has_one, has_many, belongs_to, many_to_many, implements, extends, depends_on, uses, calls, owns, aggregates. Para code relations: imports, extends, implements, calls, uses, re-exports, depends_on.

### AP-33: Predicado no canonico -- sinonimo no normalizado

- **Severidad:** low
- **Enforcement:** audit
- **Detectado por:** vault_graph_merge

Las relaciones de entidad usan `relationType` y las de codigo usan `type` para el mismo concepto semantico. Ademas, predicates que semanticamente son equivalentes deben unificarse: `imports` en codigo ≈ `depends_on` a nivel build-time. La ontologia define el mapeo de sinonimos.

**Prevención:** Al registrar relaciones, usar predicates del vocabulario canonico. La ontologia maneja el mapeo relationType→predicate y type→predicate automaticamente. No requiere accion manual.

### AP-34: Relacion tipada huerfana -- endpoint inexistente en el vault

- **Severidad:** high
- **Enforcement:** audit
- **Detectado por:** vault_audit, vault_graph_merge

Una relacion tipada (entity o code) referencia un endpoint que no existe como nota en el vault. Ej: relacion `User -- has_many --> Order` donde no existen `User.md` ni `Order.md`. El grafo enriquecido tendra edges hacia nodos fantasma que nunca resolveran.

**Prevención:** SP-02: verificar que los endpoints existan antes de registrar la relacion. Ejecutar vault_search o vault_list para confirmar que las notas referenciadas en fromEntity/toEntity existen en el vault.

### AP-35: Silos de relacion -- sistemas de grafos aislados

- **Severidad:** high
- **Enforcement:** audit
- **Detectado por:** vault_audit, vault_graph_merge

El vault mantiene tres sistemas de relaciones en silos aislados: (a) wiki-links en graph.json, (b) entity relations en 06_Diagrams/entity/*-relations.json, (c) code relations en 11_Code/.code-index.json. Ninguno de estos sistemas se integra con los otros, produciendo un grafo de conocimiento fragmentado. vault_impact y BFS solo ven wiki-links, ignorando relaciones semanticas ricas registradas en los otros sistemas.

**Prevención:** Ejecutar vault_graph_merge periodicamente (recomendado: cada sesion o cada vez que se registren nuevas relaciones). vault_graph --typed genera graph-enriched.json que unifica los tres sistemas.

### AP-36: Contención e idempotencia -- side-effects fuera del vault o no rastreables

- **Severidad:** critical
- **Enforcement:** guard+audit
- **Detectado por:** vault_norms

Toda operación de tooling debe: (1) escribir ÚNICAMENTE dentro del vault root (backups, traces, locks, stubs, logs incluidos); (2) ser idempotente -- ejecutarla dos veces no duplica artefactos ni carpetas; (3) dejar sus artefactos indexados o en ubicaciones registradas (vault_registry) para rastreabilidad. Casos históricos: vault-backups escrito en el abuelo del repo, 00_System/99_Index generados fuera del vault por detección de root defectuosa, .bak junto a nodos de contenido.

**Prevención:** Rutas de salida derivadas SIEMPRE de VAULT_ROOT (nunca de __file__ ni cwd). Artefactos de mantenimiento van a 02_Observability/maintenance/ o 00_System/. vault_norms --audit detecta artefactos sueltos y secciones sin índice.

### AP-37: No-op silencioso -- ok: true sin indicador de trabajo

- **Severidad:** high
- **Enforcement:** audit
- **Detectado por:** vault_noop_audit

Una tool con side effects declarados devuelve ok: true sin exponer ningún campo que distinga 'hice N cosas' de 'no hice nada'. `ok: true` a secas es una afirmación no falsable: ni un test ni un agente pueden detectar que la operación fue vacía. Toda tool que modifica estado debe declarar un indicador de trabajo en declared_returns (changed, applied, count, migrations_applied, fixes_applied, skipped, no_op…) y devolverlo siempre, también cuando vale 0.

**Prevención:** Declarar el indicador en tool-spec.json y devolverlo desde la tool. vault_noop_audit --check compara el catálogo contra una baseline congelada: la deuda histórica no bloquea, pero NO puede crecer.

### AP-38: Vocabulario validado después de escribir, no antes

- **Severidad:** high
- **Enforcement:** guard+audit
- **Detectado por:** vault_norms

Un campo con vocabulario cerrado se acepta tal cual en la escritura y se comprueba en un audit posterior. El audit no lo ejecuta nadie -- en 1.356 ejecuciones registradas del parque real, `vault_norms` no aparece ni una vez -- así que el vocabulario no gobierna: solo documenta una intención. Agravante: que varias tools publiquen vocabularios distintos para el mismo campo (AP-05 aplicado al dato). Un campo canónico se normaliza en el punto de escritura y rechaza lo que no pueda derivar; los ejes de dominio legítimos (resultado de un test, fase de un incidente) van a su propio campo, no compiten por `status`.

**Prevención:** STATUS_SYNONYMS + normalize_status() normalizan en vault_write antes de emitir. Las tools con eje propio llaman a status_frontmatter_lines(), que emite `status` canónico y el campo de dominio desde DOMAIN_STATUS_VOCABS. Lo que arrastraba información y no era estado se conserva en status_note: no-derogación aplicada al dato.

### AP-39: Vocabulario abierto sin memoria

- **Severidad:** medium
- **Enforcement:** guard+audit
- **Detectado por:** vault_tags, vault_norms

Un campo con vocabulario abierto (tags) admite términos nuevos sin dejar constancia de quién los introdujo ni cuándo. Sin registro no hay continuidad: cada sesión reinventa las palabras de la anterior, y el vocabulario crece sin converger -- 1.180 términos para 6.358 usos, el 45% usado una sola vez. A diferencia de AP-38, la respuesta correcta NO es rechazar: un vocabulario abierto que rechaza empuja a omitir el campo, y entonces lo que se incumple es AP-26. Lo que hay que cerrar es el olvido, no la entrada.

**Prevención:** vault_write llama a vault_tags.apply_vocabulary() antes de emitir: colapsa contra el registro canónico lo que es demostrablemente la misma palabra (normalize_tag + singular_tag) y admite el término nuevo tal cual. Una vez la nota está en disco, record_new_tags() lo anota en la bitácora append-only 19_Audits/vocabulary/tag-ledger.json con agente, fecha y nota de origen. Inventar sigue siendo posible; deja de ser silencioso.

### AP-40: Contrato publicado que la CLI rechaza

- **Severidad:** high
- **Enforcement:** guard+audit
- **Detectado por:** vault_mcp_catalog, vault_norms

Una tool publica en su catálogo parámetros que su propio argparse no acepta. La tool aparece en tools/list, se puede invocar, y falla siempre con 'unrecognized arguments'. Medido en v39: 45 de 82 tools conciliables publicaban al menos un param inexistente -- más de la mitad de la superficie MCP era inalcanzable sin que nada lo señalara, porque el guard de sincronía comparaba el JSON contra el Python: dos copias de la misma equivocación coinciden perfectamente.

**Prevención:** El contrato de argumentos lo declara argparse, no el catálogo: vault_mcp_catalog.argparse_params() lee los add_argument del script y reconciled_params() publica solo lo que la CLI acepta, conservando la descripción escrita a mano cuando el nombre coincide. vault_mcp_catalog --check-params audita el JSON ya generado (que es lo que el servidor consume) contra el argparse real.

### AP-41: Máquina de estados declarada sin verificar

- **Severidad:** high
- **Enforcement:** guard+audit
- **Detectado por:** vault_norms

El estándar declara STATUS_TRANSITIONS --las transiciones válidas del ciclo de vida de una nota-- y no las recorre nadie: su único consumidor era su propio test de coherencia. Un estado que no controla su transición es una etiqueta, no un ciclo de vida: una nota 'archived' podía volver a 'draft', o saltar de 'planned' a 'verified' sin pasar por revisión, y ningún guard lo veía. Es la misma forma del fallo histórico del estándar --declarar sin ejecutar-- con la agravante de que existía un test en verde que verificaba que el grafo estaba bien dibujado, no que alguien lo recorriera.

**Prevención:** vault_write lee el `status` de la nota en disco antes de sobrescribirla y rechaza la transición que no está en STATUS_TRANSITIONS, citando los destinos válidos. Una actualización que no menciona `status` conserva el estado previo en vez de caer al default 'draft'. Las transiciones ya ocurridas se reportan desde .history/ con vault_norms --audit: se anotan, no se reescriben, porque el estado actual es un hecho.

### AP-42: Tool publicada sin haberse ejecutado nunca

- **Severidad:** high
- **Enforcement:** guard+audit
- **Detectado por:** vault_smoke, vault_norms

Una tool se publica en el catálogo MCP porque responde a `--help` y porque su entrada existe. `--help` demuestra que el argparse se construye: no que el módulo importe sus dependencias, ni que el ejemplo documentado sea aceptado por la CLI, ni que la salida sea el JSON que el contrato promete. La primera medición dio 41 de 87 tools cuyo ejemplo documentado no llegaba a emitir un JSON con `ok` --36 de ellas porque el ejemplo del catálogo usaba flags que la CLI rechazaba, exactamente el defecto de AP-40 trasladado a la superficie de documentación.

**Prevención:** vault_smoke ejecuta el ejemplo documentado de cada tool contra una copia desechable del vault de pruebas y exige tres cosas: que termine, que su salida sea JSON y que ese JSON tenga `ok`. Un `ok: false` bien formado aprueba: lo que se persigue es el fallo mudo. La baseline solo puede encoger y quedó en 0, así que es un guard duro desde el primer día. Las tools sin invocación posible (un servicio HTTP que no retorna) se declaran en SIN_SMOKE con su motivo, nunca se omiten en silencio.

### AP-43: Norma sin refuerzo en el punto de uso

- **Severidad:** high
- **Enforcement:** guard+audit
- **Detectado por:** vault_voice, vault_norms

El catálogo de normas está completo, versionado y con guards, pero el agente que documenta el vault no lo tiene delante mientras trabaja: se entera de que una norma existe cuando la incumple --y solo si esa norma es una de las 14 que previenen, no una de las 33 que se limitan a detectar en un audit que puede no correrse nunca. El refuerzo llega tarde, fuera de contexto o no llega. Una norma que el agente no ve en el momento de escribir no gobierna la escritura: gobierna el post-mortem.

**Prevención:** vault_errors.wrap_main --el único punto por el que ya pasa la salida de todas las tools-- añade a cada resultado un bloque `vault_says` derivado de NORM_CATALOG y del estado real de esa llamada: qué norma acaba de actuar, cuántas notas cambiaron, qué mirar a continuación. El refuerzo rota entre las normas que gobiernan esa tool para no degradarse en ruido fijo. vault_voice --coverage nombra las normas que ninguna tool pronuncia.

### AP-44: Verificación autoconsistente -- la tool se certifica a sí misma

- **Severidad:** critical
- **Enforcement:** guard+audit
- **Detectado por:** vault_norms, vault_audit

Una tool escribe o mide con un criterio propio y verifica el resultado con ESE MISMO criterio, en vez de con el que usa el consumidor real --Obsidian al resolver un enlace, el parser de Mermaid al dibujar, YAML al leer un frontmatter, el audit del propio estándar al juzgar la nota que otra tool acaba de escribir. La tool queda internamente coherente y por eso mismo ciega a su propio fallo: no puede detectar el error porque lo comete en los dos lados de la comparación. Es más caro que un bug normal, porque el guard sale en verde y dirige el trabajo hacia donde no hay problema: reescribir enlaces que funcionan, 'corregir' diagramas válidos, retaguear notas ya etiquetadas.

**Prevención:** Verificar con el criterio del consumidor, no con el propio: resolver wikilinks por nombre de fichero y `aliases:` --nunca por `title:`, que Obsidian no mira--, leer frontmatter con `yaml.safe_load` y no con un regex por líneas, y validar Mermaid contra su gramática real. Toda tool que escribe reevalúa el resultado releyendo del disco. Un frontmatter ilegible devuelve error explícito, nunca `{}` silencioso, que es lo que hace que un write path anteponga un segundo bloque y corrompa la nota. Y toda medida se contrasta contra un vault preexistente ajeno al estándar: `vault-sandbox/` lo genera el propio estándar y comparte sus supuestos, así que no puede exhibir este fallo.

### AP-45: Cobertura sin evidencia -- la nota existe para llenar la sección

- **Severidad:** high
- **Enforcement:** guard+audit
- **Detectado por:** vault_norms, vault_audit

Una nota se crea porque una sección estaba vacía, no porque hubiera algo que afirmar. Su cuerpo son encabezados y marcadores de pendiente --`_Pendiente_`, `TODO`, `-- No detectados`-- y no enlaza con nada. Sube la cobertura y baja la fiabilidad: el conteo de notas dice que la sección está cubierta, el health score la cuenta como nota real, y el siguiente lector la abre esperando contenido. Es más caro que la ausencia, porque la ausencia sí se ve: un hueco invita a llenarlo, un relleno declara que ya está hecho. El generador que la escribió creía estar documentando.

**Prevención:** No escribir la nota sin evidencia detrás. Un generador que no encuentra contenido real para una sección lo declara en `warnings` y en `next_steps` --que es información útil-- en vez de emitir un stub, que es desinformación. El andamiaje declarado sí es legítimo: los primers de vault_init llevan `status: template` y quedan exentos, porque anuncian lo que son. Secciones dirigidas por eventos (18_Bugs, 19_Audits, 20_Quarantine) se quedan vacías hasta que ocurre el evento.

### AP-46: Frontmatter a mano -- cada tool es su propio escritor

- **Severidad:** high
- **Enforcement:** guard+audit
- **Detectado por:** vault_norms

Veintiséis tools montan el frontmatter concatenando líneas y tres importan el write path canónico. Cada concatenación es un segundo autor del formato sin guard detrás: el bloque se cierra o no, `type:` está o no, la fecha lleva el formato de quien la escribió. El fallo no se ve al escribir --la tool devuelve `ok: true` porque el fichero se creó-- sino al auditar, y para entonces la nota ya es el dato. Es el mismo patrón que produjo 22 implementaciones de `slugify` y tres verdades para la lista de secciones: una fuente única declarada en la documentación y N implementaciones en el código. `vault_migrate_docs` cortaba el documento por la línea 7 y llevaba versiones publicándose así, con el bloque de frontmatter sin cerrar.

**Prevención:** El write path valida lo que escribe releyendo el resultado, no confiando en cómo se construyó: `atomic_write_text` rechaza un bloque de frontmatter que abre y no cierra o que no parsea, y registra el que parsea pero sale sin `type:`. Así el guard alcanza a las 26 tools sin reescribir ninguna, y la adopción de `vault_write` puede ser gradual. Verificar con el criterio del consumidor --`yaml.safe_load`, no un regex por líneas-- es AP-44 aplicado al generador.

### AP-47: Artefacto derivado desfasado -- el índice dejó de reflejar el disco

- **Severidad:** high
- **Enforcement:** guard+audit
- **Detectado por:** vault_norms, vault_reindex

El vault es la fuente de verdad y `search-index.json` y `graph.json` son proyecciones suyas. Una escritura que no pasa por `vault_write` --un agente remoto, una tool que escribe la nota y no toca el índice, una copia a mano-- deja la proyección atrás, y a partir de ahí el agente busca sobre un mapa viejo: la nota existe y `vault_search` no la encuentra, así que la vuelve a escribir. La duplicación no es un descuido del agente, es la consecuencia lógica de un índice que miente.

El estándar no lleva base de datos por decisión normativa, y con consistencia eventual el desfase es esperable. Lo que no es aceptable es que **nadie lo mida**: `vault_reindex --check` comprobaba `len(notes) > 0`, de modo que un índice con una entrada sobre un vault de 300 notas pasaba la puerta.

**Prevención:** `vault_reindex --check` contrasta disco contra índice con el mismo criterio con el que reconstruye --una sola función, `_notas_en_disco()`, para que la comprobación y el arreglo no puedan medir cosas distintas (AP-44)-- y reporta las dos direcciones: notas invisibles para la búsqueda y entradas que apuntan a ficheros que ya no están. El remedio es `vault_reindex`, y por eso la norma se audita en vez de bloquear: el desfase es un estado a reconciliar, no una escritura a rechazar.

### AP-48: Implementación paralela por camino de acceso

- **Severidad:** critical
- **Enforcement:** guard+audit
- **Detectado por:** vault_norms, vault_mcp_catalog

La misma tool publicada tiene dos implementaciones y cuál se ejecuta depende de por dónde entres. No es una fachada sobre un núcleo común: son dos cuerpos de código que nadie contrasta, con un solo nombre y un solo contrato publicado -- así que el contrato describe como mucho a uno de los dos.

Es AP-05 (múltiples fuentes de verdad) desplazado del dato al camino de ejecución, y se le parece poco en lo importante: dos definiciones de un vocabulario acaban divergiendo y alguien lo nota al leerlas, mientras que dos implementaciones divergen **en silencio** porque cada una tiene su propio público. La suite prueba una; el agente ejecuta la otra; las dos están verdes.

Medido en v39.5 sobre el servidor MCP: nueve tools con backend nativo en Node, siete de ellas con script Python del mismo nombre. Ninguna de las siete compartía un solo campo de envelope con el contrato de `00_System/tool-spec.json` -- `vault_fundamentals` devolvía `compliance_pct`/`passed` donde el contrato dice `path`/`total`. Y la divergencia peor no era de forma sino de efecto: la implementación nativa de `vault_graph` no escribía el grafo, así que un agente la llamaba, recibía `ok: true` y el índice se quedaba desfasado -- AP-37 y AP-47 servidos por el único camino que un agente real usa. `vault_smoke` recorría las 91 tools del catálogo ejecutando el `.py`: probaba exactamente la implementación que el agente no toca.

**Prevención:** Backend nativo solo para lo que **no tiene** implementación en Python; todo lo demás cae al runner, que es donde vive el contrato publicado. La implementación desplazada no se borra (no-derogación): se anota `superseded_by:` y se deja fuera del despacho. La regla se comprueba por comportamiento y no por lectura del código -- se llama la tool por MCP y se contrasta el envelope contra el contrato, que es el criterio del consumidor y no el propio (AP-44).

### AP-49: Vínculo resuelto en tiempo de import

- **Severidad:** high
- **Enforcement:** guard+audit
- **Detectado por:** vault_norms, vault_arch

Un módulo deriva su ruta, su configuración o su dependencia en el momento de **importarse**, no en el de usarse. `SYSTEM_DIR = VAULT_ROOT / '00_System'` a nivel de módulo se evalúa una sola vez, cuando el intérprete carga el fichero, y a partir de ahí es una constante.

Lo grave no es la constante: es que deja **inerte una costura que existe**. `vault_io.set_vault_root()` está publicado y 12 tests lo usan, pero no puede reapuntar a un módulo que ya calculó su ruta al cargar. La inyección parece disponible y no lo está, que es peor que no tenerla -- quien la usa cree haber redirigido la escritura.

Medido en v40.0 por el propio guard: **0 vínculos congelados en 0 módulos**. Eran 82 en 62 módulos antes de empezar a migrar contextos al dominio, y cayeron uno a uno: Durabilidad los dejó en 77, Índices en 69, Grafo en 51, Consulta en 45, Gobernanza en 38, Ciclo de vida en 34, Meta-toolkit en 31 y Autoría --donde estaban los 31 últimos, el 100% de la deuda que quedaba-- en 0. Llegar a cero destapó la otra mitad de la norma: veinte módulos seguían haciendo `from vault_io import VAULT_ROOT` y usándolo **dentro de funciones**. No son asignaciones de nivel de módulo, así que el guard los daba por limpios, y seguían dependiendo del paliativo de reanclaje que el refactor existe para no necesitar. Se mide aparte (`raw_vault_root_imports`), también en cero, y el caso legítimo se pide con alias. La cifra es la que cuenta `vault_arch --check`, no una estimación a ojo: la norma y su puerta miden lo mismo o la norma no es comprobable. La consecuencia visible era que `cli/runner.py` aislaba cada tool en un subproceso citando "estado a nivel de módulo" como razón: el aislamiento por proceso no era una decisión de diseño libre sino la compensación de este acoplamiento. Saldada la deuda, esa razón caducó y quedó anotada allí mismo; el subproceso se conserva por las otras dos que siguen siendo ciertas --timeout que puede matar lo que vigila, y envelope sin reinterpretar--. El refactor lo hizo posible, no conveniente.

**Prevención:** La raíz y sus derivadas se reciben, no se importan: el dominio toma un contexto (`VaultContext`) y el adaptador lo construye por llamada. Si un módulo necesita la ruta, la resuelve **tarde** con `get_vault_root()` dentro de la función. El guard es AST sobre asignaciones de nivel de módulo que derivan de `VAULT_ROOT`, con baseline que solo puede encoger -- la deuda medida no se arregla en un commit, pero no puede crecer.

### AP-50: Decisión duplicada sin dueño declarado

- **Severidad:** high
- **Enforcement:** guard+audit
- **Detectado por:** vault_norms, vault_arch

La misma **decisión** --qué valores son válidos, cuál es el default, cómo se escapa un campo-- se toma en más de un punto de uso sin que ningún registro declare quién manda. No es AP-05: aquel habla de un **dato** con dos fuentes, y se ve porque las dos copias divergen. Esto se ve cuando ya divergieron, que es tarde.

Lo que lo hace caro es que cada copia parece correcta en su sitio. `SEVERITIES = ['critical', 'high', 'medium', 'low']` no está mal escrito en ninguno de los catorce ficheros donde se midió; está mal que sean catorce y que nada los compare. El día que el registro cambie, la copia que se quede atrás rechazará un valor válido o aceptará uno inventado, y ningún test lo notará porque cada fichero sigue siendo coherente consigo mismo.

Medido en v40.1 por sus tres guards: **0 copias de vocabulario, 0 lecturas de entorno sin declarar, 0 vocabularios sin contexto dueño**. Eran 14 copias del vocabulario en 13 módulos --cuatro como `choices=` de argparse y diez como constante-- y 13 variables de entorno con su default escrito en cada punto de lectura, de las que solo seis estaban documentadas. Dos ya habían divergido antes de que existiera el guard: `VAULT_VOICE` se comparaba contra `'verbose'` en un módulo y contra `'0'` con default `'1'` en otro, y `VAULT_MCP_LOG` estaba declarada como fichero de log mientras el único código que la lee la usa como nivel con default `'info'`.

El dueño es la mitad que faltaba. `vault_norms.DOMAIN_STATUS_VOCABS` ya había resuelto esto para `status` en v39 y se quedó solo: compartir la constante evita la copia, pero no contesta quién decide cuándo cambia. Por eso cada entrada del registro declara el contexto acotado que manda sobre ella, y ese contexto tiene que existir en `vault_arch.CONTEXTS`.

**Prevención:** Registro canónico con dueño, consumidores derivados, guard sin baseline. Los vocabularios cerrados en `vault_vocabulario.py`, la configuración en `vault_entorno.py`, y `vault_arch --check` fallando si aparece una copia, una lectura sin declarar o un vocabulario huérfano. **Sin baseline a propósito**: las catorce copias se saldaron al declarar el registro, así que la puerta nace en cero y una baseline solo serviría para admitir la número quince. Lo que ya tiene registro canónico no se copia: se declara `derivado_de` y se resuelve al llamarse, nunca al importarse (AP-49). Un dato canónico que no es puerto de su contexto se acaba copiando -- los tres registros que `CLAUDE.md` declara fuente única de verdad se leían por fuera de la superficie publicada, y así nacieron las catorce copias.

### AP-51: La tool culpa al dato de su propio fallo

- **Severidad:** high
- **Enforcement:** guard+audit
- **Detectado por:** vault_blame_audit

Una tool falla al leer o al interpretar algo, se traga el fallo y devuelve un vacio que el llamante no puede distinguir de un resultado legitimo. El error deja de ser un error y pasa a ser un **hecho sobre el vault**: el informe que lo agregue dira que N notas no tienen aliases, y no sera cierto -- es que no se pudieron leer.

No es lo mismo *no hay* que *no pude mirar*, y esa es toda la norma. AP-44 cubre la mitad de arriba --verificar con el criterio del consumidor y no con el propio--; esta cubre la de abajo, que es el mecanismo por el que un fallo propio acaba pareciendo un dato malo. Salio al ejecutar contra un vault ajeno al estandar (**regla 7**): tres tools declaraban invalidas notas que Obsidian leia sin problema. Las notas estaban bien; el criterio que las media, no.

Lo que la norma **no** prohibe es capturar amplio. Prohibe capturar amplio y callarse: devolver `ok: false` con el error es correcto porque el llamante recibe la mala noticia y decide. Capturar `FileNotFoundError` tampoco infringe: es un criterio, el autor sabe que tolera y por que. Lo que infringe es `except Exception: return []`.

Medida en v40.1: **86 sitios en 37 modulos**. Nace con baseline por la misma razon que AP-37 --que empezo en 55 y llego a 0--: un guard que falla en 86 sitios se desactiva el primer dia, y un guard desactivado no protege nada. La baseline solo puede encoger.

El propio detector estreno el fallo que persigue. La primera version midio 101 sitios porque clasificaba `except yaml.YAMLError` como captura amplia: son `ast.Attribute` y no `ast.Name`, asi que caian en la rama del `except` desnudo. Contaba como infraccion justo las capturas mas precisas del repo. Quince falsos positivos, y el error era el de AP-44 cometido dentro del guard.

**Prevención:** Capturar la excepcion concreta que se sabe tolerar, y si se captura amplio, **exponer**: devolver el fallo en el envelope en vez de un vacio. Cuando el vacio es la respuesta correcta, distinguirlo del vacio por fallo con un campo aparte (`unreadable`, `errors`) para que el agregado no los confunda. `vault_blame_audit --check --strict` mide por AST y no por texto: un detector que buscara la cadena `except Exception` no veria la diferencia entre devolver un vacio y devolver un envelope con `ok: false`, que es toda la distincion que la norma sostiene.

### AP-52: El error se emite fuera del contrato del catalogo

- **Severidad:** medium
- **Enforcement:** guard+audit
- **Detectado por:** vault_error_contract

Una tool falla, lo dice, y lo dice mal: devuelve `{"ok": false, "error": "..."}` escrito a mano en vez de pasar por `vault_errors.emit_error`. La frase es correcta; el contrato, no. El envelope del catalogo trae `error_code`, `category`, `severity`, `recovery` y `timestamp`; el escrito a mano no trae ninguno.

Importa porque el consumidor no lee la frase: **decide por el codigo**. El servidor MCP y `cli/` deciden si reintentar, abortar o pedir permiso mirando `error_code` y `recovery.action`. Sin ellos, un fallo con recuperacion conocida llega como un fallo opaco, y la unica salida del agente que lo recibe es adivinar.

Es AP-05 aplicada al **contrato de error** --hay un registro que declara como se nombra y se recupera cada fallo, y 158 sitios que lo deciden por su cuenta-- y es AP-51 vista desde el otro lado: alli el fallo se disfrazaba de dato, aqui llega como fallo pero desnudo de todo lo que lo hace accionable.

Salio de la caracterizacion maliciosa: invocar las 94 tools de forma malformada y mirar **como** fallan, no si fallan. El grueso estaba limpio --las 45 tools con `required_args` rechazan la invocacion vacia por argparse, y las 92 tools Python rechazan un flag desconocido-- y el hallazgo estaba en la forma del envelope, no en su ausencia.

Medida en v40.2: **158 sitios en 58 modulos**. Nace con baseline por la misma razon que AP-37 y AP-51: un guard que falla en 158 sitios se desactiva el primer dia. La baseline solo puede encoger.

El guard mide **forma y no flujo**: un dict con `ok: False` y pinta de envelope que no lleva `error_code`. No sigue el valor hasta stdout, asi que cuenta tambien envelopes internos que nunca se imprimen. Eso se declara en vez de esconderse: un guard que promete una precision que no tiene es la clase de afirmacion no falsable que AP-37 persigue.

**Prevención:** Emitir por `emit_error(tool, CODIGO, mensaje)` y, si el codigo no existe, anadirlo a `ERROR_CATALOG` -- que es donde vive la decision de como se recupera ese fallo. Anadir el codigo cuesta una linea; no anadirlo traslada el coste a cada consumidor, para siempre. `vault_error_contract --check --strict` mide por AST.

### AP-53: El historial se afirma a mano y nadie lo contrasta con git

- **Severidad:** medium
- **Enforcement:** guard
- **Detectado por:** vault_changelog_check

La documentacion afirma un hecho del historial --que la version v39.0 la introdujo el commit `00731c6` el 2026-07-25-- y ese hecho vive tambien en git, que es donde de verdad existe. Una de las dos copias se escribe a mano y ninguna se contrasta con la otra, asi que la de mano se queda atras sin que nada lo note.

Es AP-05 aplicada al **historial**, y AP-47 en su forma menos visible: AP-47 persigue cifras escritas a mano --cuantas tools, cuantas normas-- y una fecha o un hash de commit son la misma clase de dato derivable, solo que nadie los lee como una cifra.

Medido en v40.7 sobre el changelog del manifiesto: **55 entradas, 31 con hash real, los 31 existen** --ninguno inventado-- y **5 fechas contradecian al commit que citaban**. Cuatro por un dia; la de v39.0 por once. Esa entrada arrastra ademas un commit de fijado que corrigio el hash (`13bf9ca -> 00731c6`) y no toco la fecha: la correccion parcial es el modo de fallo tipico, porque quien corrige mira el dato que le fallo y no el que viaja con el.

Detras hay un huevo y una gallina que conviene nombrar, porque es lo que empuja a escribir el dato a mano: la entrada tiene que citar el hash del commit que la contiene, y ese hash no existe hasta que el commit esta hecho. La salida fue un ritual de dos commits --`feat: vX` con `git: pending`, luego `docs: fijar hash`-- que aparece ocho veces en las ultimas veinte entradas del historial y cuyo segundo paso depende de que alguien se acuerde. Una norma que solo prohibe no sirve aqui: hay que dar el comando que hace el paso, o se seguira haciendo a mano.

**Prevención:** Derivar el dato del repositorio y comprobarlo en una puerta. `vault_changelog_check --check --strict` contrasta hash, fecha --de autoria, `%as`, que un rebase no reescribe--, `pending` y orden. Y `--fijar-hash` convierte en comando el paso manual que originaba la divergencia.

### AP-54: El lock falla y se escribe igual

- **Severidad:** high
- **Enforcement:** guard
- **Detectado por:** vault_arch

Un bloque toma un `file_lock`, no lo consigue, y en el handler escribe de todos modos sin sincronizar. El razonamiento que lleva ahi es que perder el dato es peor que escribirlo sin lock. Es al reves, y por una razon que se ve al leer el `TimeoutError`: ese error significa que **otro lo tiene tomado ahora mismo**. La escritura del handler no es una carrera improbable, es la unica situacion en la que ese codigo llega a ejecutarse, y entra justo encima de la de quien si consiguio el lock.

Medido en v40.7 en `vault_sdd_init`, que se pasaba del timeout de 60s de la tool y moria dejando `docs/sdd/` a medio escribir despues de haber anunciado `Drift status: PASS`. La medida: **26 tomas del lock del fichero de trazas, 13 fallidas, 65,14s de espera pura** --13 x 5s exactos--. Esas 13 acababan reescribiendo el trace sin lock mientras el llamante externo lo estaba reemplazando.

La causa de las esperas era distinta de la norma y se corrigio aparte: `file_lock` no era reentrante, asi que un hilo que volvia a pedir un lock que el mismo sostenia esperaba el timeout entero contra si mismo. Conviene separar las dos cosas --la causa se arregla una vez en el kernel; la reaccion es la que se repite en cada llamante y la que esta norma vigila.

Omitir la escritura al fallar el lock **no** es esta norma: es la respuesta correcta, y `vault_quality_check` ya la tenia.

**Prevención:** Al fallar el lock, descartar la escritura o propagar el error -- nunca escribir sin sincronizar. `vault_arch --check --strict` reporta el patron en `unsynced_writes`.

### AP-55: El catálogo de normas se certifica a sí mismo

- **Severidad:** high
- **Enforcement:** guard+audit
- **Detectado por:** vault_norms_coherence

`NORM_CATALOG` declara por norma qué tools la hacen cumplir (`tools_enforcing`) y cuáles la detectan (`tools_detecting`). Los dos campos se escriben a mano y nada los contrasta contra lo que las tools hacen: la cobertura publicada es una promesa sin verificar.

Lo caro no es la lista, es el guard. `vault_voice.coverage()` existe para detectar normas mudas y comprueba que una norma tenga `tools_enforcing` o `tools_detecting` **leyendo `tools_enforcing` y `tools_detecting`**. Verifica el catálogo contra el catálogo, así que da verde sobre las 47 afirmaciones que ningún módulo respalda y es estructuralmente incapaz de verlas. Es AP-44 cometido dentro del guard de AP-43 -- la tercera vez que el criterio de verificación sale del objeto verificado, tras el test de cruces de v40.8 y el cero de AP-52 medido sobre un subconjunto en v40.9.

La forma general: **dos registros canónicos que hablan del mismo hecho no pueden contradecirse sin que algo falle.** Medido en v40.10: 54 valores de `tools_*` que mezclaban la tool con su flag y ningún consumidor podía resolver; AP-22 declarada `critical` mientras `vault_audit` la penalizaba con 2 puntos por unidad frente a los 5 de AP-24, que el catálogo llamaba `high`; y 47 afirmaciones de cobertura sin una línea de código que nombre la norma. `AP-05` --`critical`-- nombra `vault_graph_inspect` como detector, y esa tool no la menciona en ninguna parte.

**Prevención:** `vault_norms_coherence --check --strict` cruza el catálogo con el código y con `PENALIZACIONES`. La traza sin respaldo lleva baseline que solo puede encoger, y se salda de dos formas honestas: que el código nombre la norma en el sitio que la aplica, o que el catálogo deje de afirmar una cobertura que no tiene. Ampliar la baseline es la tercera y no lo es.

### AP-56: Frontmatter presente que el consumidor no puede leer

- **Severidad:** high
- **Enforcement:** guard+audit
- **Detectado por:** vault_frontmatter_heal, vault_foreign_check

La nota abre `---`, escribe sus claves y, para `yaml.safe_load`, no tiene frontmatter: ni id, ni tags, ni tipo, ni estado. El bloque **se ve** al abrir el fichero, y por eso nadie lo revisa. El dato parece estar y no está.

No es AP-28, que es la nota que nunca tuvo bloque y se cuenta sola. Aquí el hueco es invisible a ojo y solo aparece al medir con el parser real (AP-44).

Dos causas, medidas sobre doce notas de cuatro vaults consumidores: **escalar sin escapar** --`title: Overview: demo` no es un mapeo, nueve de las doce-- y **delimitador sin cerrar**, las otras tres, donde el bloque nunca se cierra y el parser se traga la nota entera hasta reventar cientos de líneas más abajo, en un bloque de código. El mensaje de YAML señala ahí, que no es donde está el fallo; por eso llevaban meses así.

v40.2 arregló la prevención: `yaml_scalar` escapa antes de escribir. Lo que faltaba era la otra mitad -- nada reparaba lo que ya estaba en disco, y `vault_fix_brackets` llevaba versiones haciendo exactamente eso para AP-22/AP-24.

**Prevención:** Escribir por tool, nunca a mano (SP-04): el write path pasa todo escalar por `yaml_scalar` desde v40.2. Lo ya escrito se repara con `vault_frontmatter_heal --apply`, que solo toca las dos causas mecánicas y se niega a adivinar el resto: completar un YAML truncado inventa dato, que es peor que el hueco.

### AP-57: Criterio con dueño, reimplementado en la medida

- **Severidad:** high
- **Enforcement:** guard
- **Detectado por:** vault_criterios

Un **criterio** --qué cuenta como instantánea congelada, qué es documentación del estándar y no una nota, qué es código y no un enlace-- tiene un dueño canónico en el toolkit, y otro módulo lo vuelve a decidir por su cuenta con un `if` local.

No es AP-50, que habla de **patrones regex** y de vocabularios: aquellos son datos que alguien puede leer y comparar. Un criterio vive enterrado en una condición, así que la copia sobrevive años sin que nadie la vea, y el día que el dueño cambia solo cambia el dueño. `vault_graph_fix` llevaba su propio `skip_set` de instantáneas y ya divergía de `vault_io.SNAPSHOT_DIRS`; como esa tool **escribe**, la divergencia no inflaba una métrica: reparaba dentro de una instantánea, que es dejar de serlo.

Sale de v40.12: cuatro defectos de `vault_foreign_check` arreglados en una tanda, los cuatro con la misma forma --el registro canónico existía y la tool no lo consultaba--. Uno de ellos tenía el sentido de error peligroso: resolver destinos por basename ponía la medida **verde** justo donde Obsidian pinta el enlace roto. La regla 4 pide norma, no cuatro parches.

**Prevención:** Dos registros en `vault_criterios`. `CRITERIOS_CON_DUENO`: criterio, dueño, símbolo por el que se consulta y las constantes que lo delatan. `FRONTERAS`: cada frontera de lenguaje con su **zona dueña** (clave de `vault_arch.CONTEXTS`), su **norma** (código de `vault_norms`) y la **pasarela** --el artefacto derivado-- por la que el criterio debe cruzar. Al otro lado la exención no es importar al dueño, que no se puede: es leer la pasarela.

`vault_criterios --check --strict` (puerta 15) falla si aparece una copia nueva; la baseline **solo encoge** y se salda importando al dueño o leyendo la pasarela, no ampliándola. El alcance se declara: un fichero ejecutable de otro lenguaje fuera de toda zona declarada sale como `frontera_no_declarada`, porque un sitio donde una copia no se vería vale tanto como una copia.

El límite se declara antes de que nadie se apoye en él: la detección es **sintáctica**. Un módulo puede reimplementar un criterio sin repetir ninguna constante y esta medida no lo verá. Verde no prueba que no haya copias -- prueba que no hay copias de la forma que sabemos reconocer, que es exactamente lo que da un linter y es preferible a no mirar.

### AP-58: Ciclo esquivado con un import diferido

- **Severidad:** high
- **Enforcement:** guard
- **Detectado por:** vault_ciclos

Dos módulos se necesitan mutuamente, y en vez de invertir la dependencia se mete uno de los `import` dentro del cuerpo de una función. Python deja de quejarse, el ciclo sigue ahí y **deja de verse**: cualquier medida que mire los imports de nivel de módulo dirá cero ciclos con toda honestidad.

Aplicado una vez es una excepción razonable. Aplicado muchas es la arquitectura, tomada sin decidirla. Medido en v40.17 sobre este repo: **92 imports diferidos en 40 módulos**, de los cuales 30 esquivan un ciclo, y contándolos aparece un componente fuertemente conexo de **14 módulos** que contiene el núcleo entero. Ese componente es el que hacía que `vault_errors_trace` --un escritor de trazas de bajo nivel-- importase `vault_io` entero, y el que obliga a `cli/runner.py` a aislar cada tool en un subproceso para que dos raíces no se contaminen.

El daño no es el arranque: es que la dirección de la dependencia deja de ser una decisión revisable. Un ciclo escondido no se discute en revisión porque no aparece en ninguna medida.

**Prevención:** `vault_ciclos --check --strict` (puerta 17) calcula los componentes fuertemente conexos **contando las aristas diferidas**, que es la única forma de que la pregunta se pueda formular. La baseline **solo encoge** y se salda invirtiendo la dependencia --el módulo de bajo nivel deja de pedirle el módulo entero al de alto y se le pasa lo que necesita--, no subiendo el import ni ampliando la baseline.

Dos límites, dichos antes de que nadie se apoye en el verde. Primero: solo entran en la deuda los diferidos que **esquivan un ciclo** (30 de 92); los otros 62 se difieren por coste de arranque o por dependencia opcional y se publican como `deferred_benign` sin congelarse, porque una baseline llena de ruido es una baseline que nadie revisa. Segundo: la medida es del grafo **estático** de módulos. No ve `importlib`, ni un import construido con una cadena, ni el acoplamiento que pasa por el sistema de ficheros o por una variable global compartida.

### AP-59: Núcleo declarado sin contraste

- **Severidad:** high
- **Enforcement:** guard+audit
- **Detectado por:** vault_kernel

Un sistema declara cuál es su núcleo --la lista de módulos de los que todo lo demás depende-- y **ninguna medida contrasta esa afirmación** contra la forma real del grafo. La pertenencia al core deja de ser un hecho y pasa a ser una costumbre: se hereda de quien escribió la lista, y envejece en la dirección cómoda.

Lo caro no es equivocarse de lista: es que **todo lo que se apoya en ella hereda el error en silencio**. Si un módulo está declarado como núcleo sin serlo, el guard de fronteras lo exime de reglas que sí debería cumplir y sale verde. Si uno lo es sin estar declarado, cada cambio suyo propaga hacia arriba sin que nadie lo trate como un cambio de núcleo. En ambos casos el verde es correcto respecto a un mapa equivocado.

Medido en v40.20 sobre este repo, con la lista **bien elegida** --los cuatro de cabecera eran los correctos y K1 ya estaba verde--: aun así, **tres de quince módulos del kernel no se comportan como núcleo**. `vault_log_error` con fan-in 0, declarado núcleo y sin un solo consumidor; `vault_io` con fan-out 11 y 30 commits; `vault_errors` con 14, sobre una mediana de dominio de 9. Ninguno estaba roto. Ninguno se había visto, porque nadie miraba.

La norma no exige que el núcleo sea perfecto: exige que su pertenencia sea **derivable y contrastada**, y que la distancia entre lo declarado y lo medido se publique en vez de suponerse cero.

**Prevención:** `vault_kernel --check --strict` (puerta 18) mide tres invariantes. **K1** --el núcleo no depende del dominio-- no se reimplementa: se delega en `vault_arch.dependencias_del_kernel()`, porque una tool que mide su propia pureza con su propio criterio es AP-44 cometido en el sitio que existe para detectarlo. **K2** --fan-in alto, fan-out bajo-- sale del dueño único del grafo de imports (`vault_grafo_import`), no de un parser propio. **K3** --estabilidad-- del churn de git, y sin historia disponible emite `desconocido` y nunca `0`: un cero fabricado saldría verde por no haber mirado (AP-51).

Los umbrales **se derivan del escalón** de la distribución --la mayor caída relativa-- y se publican en el envelope con su ratio en cada ejecución. Escribirlos a mano sería AP-47 en la tool que persigue los números a mano; por eso la baseline congela la **pertenencia** (qué módulo incumple qué invariante) y no el umbral, que puede oscilar al crecer el repo.

Dos límites, dichos antes de que nadie se apoye en el verde. Primero: mide el grafo **estático** de imports y hereda sus cegueras (`importlib`, un import por cadena, el acoplamiento por fichero o por variable global). Segundo: mide **forma, no propósito**. Un módulo puede tener fan-in altísimo sin ser núcleo de nada, solo un cajón de utilidades que todo el mundo toca. Verde significa que la lista declarada no contradice a la forma medida.

### AP-60: El guard cobra por declarar y regala el silencio

- **Severidad:** medium
- **Enforcement:** guard+audit
- **Detectado por:** vault_norms_coherence

Un guard comprueba una propiedad **iterando sobre quien ya la declaró**. Quien no declaró nada queda fuera de su alcance, no por una decisión sino por la forma del bucle. El efecto es un incentivo invertido: declarar cuesta --obliga a mantener lo declarado, a veces a editar el otro extremo-- y callarse sale gratis y verde.

Medido en v40.21 sobre C5 de `vault_norms_coherence`: la comprobación de que dos normas se distinguen recorre `distinguido_de`, así que solo alcanzaba a **13 normas de 71**. Las otras 58 no estaban exentas: estaban invisibles. Y declarar una distinción en AP-59 costó tres ediciones recíprocas y un fallo de puerta, mientras no declarar ninguna habría salido verde a la primera.

Es la misma forma que el repo ya prohíbe en `cobertura_descubierta` --una norma que declara su hueco no cuenta como deuda nueva, porque declararse honestamente no puede salir más caro que callarse--, cometida en el guard que vigila el catálogo donde esa regla está escrita.

**Prevención:** Medir sobre el universo --el catálogo, el registro, el conjunto de módulos-- y no sobre el subconjunto que declaró. Admitir dos salidas honestas, la declaración y la exención con motivo escrito, y ninguna tercera: el silencio se cuenta como deuda. La baseline congela lo que ya estaba y solo encoge; lo que estrena se escribe.

### AP-61: El guard cae con el dato que vino a medir

- **Severidad:** high
- **Enforcement:** guard+audit
- **Detectado por:** vault_excepcion_declarada

Un handler captura la excepción que una librería **declara** y deja escapar la que esa librería **lanza de verdad**. El `try` parece contener el fallo y no lo contiene: la excepción sube entera y tumba la ejecución completa. Lo caro es la asimetría de alcance -- el dato defectuoso es de una nota, la caída es del barrido entero, así que un solo fichero hostil deja al vault sin medida.

El caso que le dio nombre: `RecursionError` **no hereda de `yaml.YAMLError`**. El parser de PyYAML es recursivo y el frontmatter es dato externo, así que `x: [[[[[…` --doce caracteres de escribir-- desborda la pila dentro de `safe_load`, por encima de cualquier `except yaml.YAMLError`. `vault_lib.parse_frontmatter` lo resolvió y lo dejó escrito; los otros **doce sitios** que habían copiado el mismo `try` no se enteraron de la corrección, y entre ellos estaba `vault_foreign_check`, que es la tool de la regla 7 y por tanto la única que corre contra material que este repo no generó -- exactamente donde el dato hostil aparece.

Es primo de AP-57 y llega por su camino: un criterio copiado envejece por su lado, y aquí envejeció hacia el lado que deja caer la tool.

**Prevención:** `vault_excepcion_declarada --check --strict` recorre los `try` cuyo cuerpo contiene una llamada de riesgo declarada en `RIESGOS` y exige que la excepción que escapa esté nombrada. Se salda **delegando en el dueño que ya la contuvo** --para el frontmatter, `vault_lib.parse_frontmatter`-- y solo cuando la firma de retorno lo impide, nombrándola en la tupla y citando al dueño en un comentario: ampliar la tupla en trece sitios sin dueño es AP-57 cometido al arreglar AP-61.

Límite declarado: solo ve la llamada de riesgo escrita **a la vista** en el cuerpo del `try`. Un `safe_load` detrás de un helper queda fuera del alcance, que es la forma correcta de escribirlo -- así que este guard mide mejor el código que peor está escrito, y eso se publica en vez de suponerse cubierto.

### CN-01: Kebab-case filenames -- nombres de archivo en minúsculas con guiones

- **Severidad:** high
- **Enforcement:** guard
- **Detectado por:** sin detector declarado

Los archivos .md del vault deben usar kebab-case: minúsculas, palabras separadas por guiones, sin espacios ni caracteres especiales. vault_write aplica slugify() automáticamente al título para generar el filename. Ej: 'ADR-001 Auth Decision' → adr-001-auth-decision.md.

**Prevención:** Siempre usar vault_write para crear notas. Nunca crear archivos .md directamente.

### CN-02: Numbered folder structure -- secciones numeradas como únicos destinos

- **Severidad:** high
- **Enforcement:** guard+audit
- **Detectado por:** vault_section_index, vault_norms

Solo las secciones numeradas del registro canónico (vault_registry.SECTIONS, fuente de verdad única -- PAT-1) son destinos válidos para notas. Crear carpetas ad-hoc o escribir en la raíz viola este estándar (ver AP-15). NO duplicar la lista aquí: consultarla con vault_folder_registry o vault_registry.

**Prevención:** Elegir la sección más apropiada del vocabulario estándar. AP-15 para raíz del vault.

### CN-03: Standard status vocabulary -- vocabulario canónico de meta.status

- **Severidad:** low
- **Enforcement:** audit
- **Detectado por:** vault_norms

El campo meta.status (o status en frontmatter) debe usar solo valores de vault_norms.STATUS_VOCAB (fuente única, v38 -- unifica el vocabulario CN-03 original con el ciclo de vida del spec §status): planned | draft | in-progress | reviewed | approved | implemented | verified | deprecated | obsolete | archived | stub | template. Valores fuera del vocabulario rompen filtros de vault_list y vault_audit.

**Prevención:** Usar solo valores de STATUS_VOCAB. vault_norms --audit los valida (CN-03).

### PAT-1: Canonical source anchoring

- **Severidad:** N/A
- **Enforcement:** recommended
- **Detectado por:** vault_audit

Un dominio = una nota canónica rica. Todas las referencias desde otros contextos son [[wiki-links]] a esa nota canónica, nunca copias del contenido.

**Prevención:** N/A -- es el patrón correcto. Aplicar siempre al crear documentación.

### PAT-2: Stub enrichment gradient

- **Severidad:** N/A
- **Enforcement:** recommended
- **Detectado por:** vault_audit

Un stub con ≥3 líneas reales se enriquece progresivamente en cada sesión que lo toca. La eliminación solo aplica a skeletons (AP-11) y deceptive skeletons (AP-20).

**Prevención:** N/A -- es el patrón correcto.

### PAT-3: Duplicate chain resolution

- **Severidad:** N/A
- **Enforcement:** recommended
- **Detectado por:** vault_audit, vault_change_log, vault_write

Algoritmo estándar para resolver duplicados: identificar canónica (más backlinks, más contenido, ubicación más apropiada) → change_log --action deleted → mover a 10_Migrated/ → actualizar wiki-links rotos → verificar con vault_audit.

**Prevención:** N/A -- es el algoritmo de resolución.

### PAT-4: Phased audit execution

- **Severidad:** N/A
- **Enforcement:** recommended
- **Detectado por:** vault_drift_detect, vault_audit, vault_write, vault_change_log

Las auditorías masivas se ejecutan en 4 fases atómicas: 1-Snapshot (vault_drift_detect --snapshot), 2-Detección (vault_audit), 3-Resolución (vault_write, vault_change_log), 4-Verificación (vault_drift_detect --report).

**Prevención:** N/A -- es el protocolo de auditoría.

### PAT-5: Frontmatter as provenance chain

- **Severidad:** N/A
- **Enforcement:** recommended
- **Detectado por:** vault_write, vault_audit

Los campos id + createdAt + updatedAt + agent + migratedFrom (si aplica) forman una cadena de custodia completa. Sin esta cadena es imposible auditar de dónde vino un dato o qué agente lo introdujo.

**Prevención:** N/A -- vault_write genera estos campos automáticamente.

### PAT-6: Semantic graph enrichment -- enriquecimiento periodico del grafo

- **Severidad:** N/A
- **Enforcement:** recommended
- **Detectado por:** vault_graph_merge, vault_audit

Ejecutar vault_graph --typed al final de cada sesion productiva para generar graph-enriched.json con predicates semanticos unificados. El grafo enriquecido combina wiki-links, entity relations y code relations en un solo grafo consultable con filtros por predicate, cardinalidad y tipo de nodo. Esto habilita busquedas de conocimiento semanticas y analisis de impacto con tipos.

**Prevención:** N/A -- es el patron correcto. Agregar vault_graph --typed al session protocol como paso automatico antes de vault_audit.

### SP-01: Delete protocol -- change_log obligatorio antes de eliminar

- **Severidad:** critical
- **Enforcement:** audit
- **Detectado por:** vault_norms

Antes de eliminar cualquier nota del vault, el agente DEBE llamar: vault_change_log --action deleted --path <nota> --reason <motivo>. Sin este registro, la nota desaparece sin rastro auditado.

**Prevención:** Regla de gobernanza: verificar en .change-log.json antes de delete. Si no hay entrada → llamar vault_change_log primero, luego eliminar.

### SP-02: Forward-link verification -- buscar antes de linkar

- **Severidad:** high
- **Enforcement:** guard
- **Detectado por:** vault_graph, vault_audit

Antes de escribir [[nombre-nota]] en contenido, verificar que la nota destino ya existe: vault_search(query:'nombre-nota'). Si no hay resultado, escribir en texto plano hasta que la nota exista. vault_write advierte con ghost_links[] (no bloquea) si el target no existe.

**Prevención:** vault_search() antes de cada [[wiki-link]] nuevo. No crear links especulativos.

### SP-03: Session snapshot pattern -- delta antes de operaciones masivas

- **Severidad:** medium
- **Enforcement:** audit
- **Detectado por:** vault_delta

Antes de cualquier operación masiva (migración, rename en lote, vault_tags --rename múltiple, delete en lote), capturar snapshot con vault_delta --snapshot. Permite detectar regresiones y calcular impacto real de la operación.

**Prevención:** PAT-4 (phased audit): snapshot → operación → vault_audit() → comparar score. vault_delta --snapshot antes de cada sesión con cambios masivos.

---

## EN

Total registered norms: 73 (AP 61, CN 3, PAT 6, SP 3)

### AP-01: Documentación alucinada

- **Severity:** high
- **Enforcement:** audit
- **Detected by:** sin detector -- Ninguna tool la detecta. Declaraba `vault_drift_detect`, que mide lo contrario: cambios en el código que la documentación no recoge. AP-01 es documentación que describe código inexistente, y para verla haría falta resolver cada referencia contra el repo.

Documentar herramientas, endpoints, funciones o comportamientos que no existen en el código real. El agente genera información convincente pero incorrecta.

**Prevention:** Verificar existencia real antes de documentar. vault_read + grep sobre el código fuente.

### AP-02: Proliferación de versiones del mismo documento

- **Severity:** high
- **Enforcement:** audit
- **Detected by:** sin detector -- Sus dos variantes hermanas sí se miden --AP-17 canonical-shadow y AP-18 cross-folder, ambas con penalización propia en vault_audit.PENALIZACIONES--, pero la variante same-folder que es AP-02 no la detecta nadie: `status-v1.md` y `status-v2.md` en la misma carpeta no son duplicados por hash (AP-18) ni pasan el umbral de similitud de título (AP-17). Declararlo aquí es lo que impide que la cobertura de las hermanas se lea como suya.

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
- **Enforcement:** audit
- **Detected by:** sin detector -- Ninguna tool la detecta. `vault_drift_detect` compara hashes y git; distinguir "lo describe en presente" de "ya está deployado" exige leer el cuerpo de la nota contra el estado real, que hoy no hace nadie.

Documentar comportamientos futuros o planeados como si ya existieran. Confunde al agente sobre el estado real del sistema.

**Prevention:** Usar status: planned/in-progress/implemented. Nunca describir en presente algo que no está deployado.

### AP-05: Múltiples fuentes de verdad para el mismo dato

- **Severity:** critical
- **Enforcement:** audit
- **Detected by:** vault_fuente_unica

El mismo dato (IP, URL, versión, configuración) aparece en múltiples notas con valores inconsistentes. Causa decisiones del agente basadas en datos erróneos.

**Prevention:** PAT-1 (canonical source anchoring): una nota canónica por dato, las demás hacen [[wiki-link]] a ella.

### AP-06: Templates sin instancias reales

- **Severity:** low
- **Enforcement:** audit
- **Detected by:** vault_norms

Archivos de template (SLOs, métricas, alertas, ADRs) que existen en el vault pero nunca se han instanciado con datos reales.

**Prevention:** Si un template no tiene instancias en 30 días, moverlo a 10_Migrated/ o eliminarlo.

### AP-07: ADRs incompletos

- **Severity:** medium
- **Enforcement:** audit
- **Detected by:** vault_norms

ADRs (Architecture Decision Records) sin secciones Contexto, Opciones evaluadas y Consecuencias. Un ADR sin estas secciones no aporta valor de auditoría.

**Prevention:** Usar vault_write con template de ADR completo. vault_audit puede extenderse para validar secciones.

### AP-08: Documentación anclada a versiones obsoletas

- **Severity:** medium
- **Enforcement:** audit
- **Detected by:** sin detector -- Ninguna tool la detecta. Declaraba `vault_drift_detect`, que no lee versiones del cuerpo de la nota. La propia `prevention` lo dice en condicional --"vault_audit puede alertar"-- y ese condicional lleva desde v19 sin resolverse.

Notas que mencionan versiones específicas de librerías, APIs o protocolos que ya fueron actualizadas, sin indicar que el contenido puede estar desactualizado.

**Prevention:** Agregar campo version_pinned al frontmatter con la versión referenciada. vault_audit puede alertar.

### AP-09: Runbooks fuera de estructura

- **Severity:** medium
- **Enforcement:** audit
- **Detected by:** vault_norms

Procedimientos operativos guardados en carpetas genéricas (07_Knowledge/, 01_Projects/) en lugar de 06_Runbooks/. Dificulta la localización en incidentes.

**Prevention:** Todo runbook va en 06_Runbooks/{proyecto}/. vault_migrate_docs para moverlos.

### AP-10: Migración sin plan de rollback

- **Severity:** high
- **Enforcement:** audit
- **Detected by:** vault_norms

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
- **Detected by:** vault_validate

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
- **Enforcement:** audit
- **Detected by:** vault_norms

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
- **Enforcement:** audit
- **Detected by:** vault_norms

Índices de sección creados manualmente, duplicando lo que vault_section_index genera automáticamente. Los índices manuales rotan en AP-02 con el tiempo.

**Prevention:** vault_section_index es la única herramienta para índices. No editar index.md manualmente.

### AP-20: Deceptive skeleton (empty-list)

- **Severity:** critical
- **Enforcement:** guard
- **Detected by:** sin detector declarado

Nota que pasa el content gate de 3 líneas porque tiene bullets, pero >50% de los bullets están vacíos (- , - [ ], - []). Variante de AP-11 que evade el guard básico.

**Prevention:** vault_write rechaza si empty_bullets/total_bullets > 0.5. Completar los bullets antes de guardar.

### AP-21: Path-anchored wiki-links

- **Severity:** critical
- **Enforcement:** guard
- **Detected by:** sin detector declarado

[[carpeta/nota]] en lugar de [[nota]]. Obsidian no resuelve paths, solo stems. El link siempre aparece roto en el grafo.

**Prevention:** Siempre [[stem]] o [[stem|título visible]]. vault_section_index genera solo [[stem|título]] desde v25.

### AP-22: Wiki-link vacío -- [[]] sin destino

- **Severity:** medium
- **Enforcement:** guard+audit
- **Detected by:** vault_audit, vault_fix_brackets

Wiki-link vacío: `[[]]` sin destino, fuera de bloques de código. No hay información que perder, así que la reparación es eliminarlo. vault_write bloquea (hard stop). vault_write también advierte (non-blocking) si [[target]] no existe: ghost_links[].

**Prevention:** Nunca escribir [[]] vacíos. Verificar que el target exista antes de linkar.

### AP-23: Note complexity ceiling -- nota demasiado larga

- **Severity:** medium
- **Enforcement:** audit
- **Detected by:** vault_write, vault_norms

Una nota con más de 500 líneas de contenido real se vuelve difícil de mantener y consume excesivo contexto del LLM. Debe dividirse en sub-notas canónicas interconectadas con [[wiki-links]] desde la nota original.

**Prevention:** Al superar 500 líneas, crear sub-notas en la misma carpeta y reemplazar la sección con [[sub-nota|título]]. La nota original actúa como índice/resumen.

### AP-24: Bracket imbalance -- corchetes sin pareja, anidados o invertidos

- **Severity:** high
- **Enforcement:** guard+audit
- **Detected by:** vault_audit, vault_fix_brackets

Wiki-links malformados por desbalance de corchetes. Tres variantes: (1) apertura sin cierre ([[nota sin ]]), (2) cierre sin apertura (]] sin [[), (3) anidamiento incorrecto ([[[[nota]]]] o [[nota]]]]). En Obsidian el link se renderiza como texto literal, no como enlace navegable. Rompe la trazabilidad y produce falsos negativos en vault_audit --broken-links.

**Prevention:** Usar siempre el formato [[stem]] o [[stem|alias]]. Validar balance con vault_fix_brackets --fix antes de commit. El content_gate de vault_write rechaza contenido con bracket imbalance.

### AP-25: Mermaid diagram syntax errors -- nodos/tipos no definidos

- **Severity:** medium
- **Enforcement:** audit
- **Detected by:** vault_audit, vault_mermaid_check

Diagramas Mermaid con sintaxis inválida: tipos de diagrama no reconocidos (unknown_type), nodos referenciados pero no definidos (undefined_node), flechas huérfanas, o sintaxis de etiquetas incorrecta. El diagrama no se renderiza en Obsidian y pierde su valor documental.

**Prevention:** Validar con vault_mermaid_check antes de commit. Usar tipos conocidos (graph TD, flowchart LR, sequenceDiagram, classDiagram, etc.). Asegurar que cada nodo referenciado en una flecha exista como definición previa.

### AP-26: Missing tags -- nota de contenido sin tags

- **Severity:** medium
- **Enforcement:** audit
- **Detected by:** vault_audit

Nota de contenido sin campo `tags` o con la lista vacía. Sin tags la nota es invisible para la búsqueda por facetas y no participa en los edges shared_tag del grafo: queda alcanzable solo por wiki-link directo.

**Prevention:** Pasar --tags en la tool de escritura. vault_ingest y vault_preferences los derivan automáticamente del origen y la categoría.

### AP-27: Missing type field -- nota sin tipo declarado

- **Severity:** medium
- **Enforcement:** audit
- **Detected by:** vault_audit

Nota sin campo `type`. El tipo es lo que ancla la nota a su sección canónica (CN-02): sin él no se puede verificar la coincidencia type ↔ carpeta que sostiene la dimensión de exactitud (F4).

**Prevention:** Declarar --type en la escritura; vault_audit lo cuenta en missing_type.

### AP-28: Missing frontmatter -- nota sin bloque YAML

- **Severity:** high
- **Enforcement:** audit
- **Detected by:** vault_audit, vault_validate

Nota sin bloque de frontmatter. Es el caso degenerado de AP-26/27/29/30 a la vez: sin frontmatter no hay id, ni agent, ni status, ni CIA, así que la nota queda fuera de toda métrica de calidad y de la cadena de trazabilidad (PAT-5).

**Prevention:** No editar .md a mano (SP-04). Escribir siempre por tool: atomic_write_text garantiza el bloque.

### AP-29: Missing status field -- nota sin estado de ciclo de vida

- **Severity:** medium
- **Enforcement:** audit
- **Detected by:** vault_audit, vault_norms

Nota sin campo `status`. Sin estado no se puede distinguir lo vigente de lo obsoleto, y la nota escapa al vocabulario controlado de CN-03: es la vía por la que contenido derogado sigue leyéndose como vigente.

**Prevention:** Declarar --status dentro de STATUS_VOCAB (12 valores).

### AP-30: Missing CIA classification -- nota sin clasificación de la tríada

- **Severity:** high
- **Enforcement:** audit
- **Detected by:** vault_audit

Nota sin `cia_integrity` / `cia_availability` / `cia_sensitivity`. Sin clasificación CIA la nota no puede endurecer su umbral de actualidad (30d → 15d en critical|high) ni ponderar su peso en el health score: el pilar del estándar queda sin aplicar sobre ella.

**Prevention:** Declarar los tres ejes en la escritura. vault_ingest asigna cia_integrity: low a lo ingerido por no estar verificado.

### AP-31: Grafo sin tipos semanticos -- edges sin predicate explícito

- **Severity:** high
- **Enforcement:** audit
- **Detected by:** vault_audit, vault_graph_merge

Todas las aristas del grafo usan el mismo tipo 'wiki-link' sin distinguir semántica: depends_on, implements, extends, calls, documents, etc. Sin predicates tipados, el analisis de impacto y las busquedas semanticas no pueden filtrar por tipo de relacion. La solucion es mergear las relaciones de entidad (vault_relation_add) y codigo (vault_code_relation) en el grafo para enriquecerlo con predicates.

**Prevention:** Ejecutar vault_graph --typed o vault_graph_merge periodicamente para enriquecer el grafo con predicates. Toda relacion registrada via vault_relation_add o vault_code_relation debe reflejarse en graph-enriched.json.

### AP-32: Relaciones tipadas sin predicate valido en la ontologia

- **Severity:** medium
- **Enforcement:** audit
- **Detected by:** vault_graph_merge

Una relacion registrada en entity relations o code relations usa un relationType/type que no existe en vault-ontology.json. Esto produce edges que no pueden interpretarse semanticamente en el grafo enriquecido. Ej: relationType='inherits' cuando el predicate canonico es 'extends'.

**Prevention:** Usar solo predicates del vocabulario canonico en vault-ontology.json. Para entity relations: has_one, has_many, belongs_to, many_to_many, implements, extends, depends_on, uses, calls, owns, aggregates. Para code relations: imports, extends, implements, calls, uses, re-exports, depends_on.

### AP-33: Predicado no canonico -- sinonimo no normalizado

- **Severity:** low
- **Enforcement:** audit
- **Detected by:** vault_graph_merge

Las relaciones de entidad usan `relationType` y las de codigo usan `type` para el mismo concepto semantico. Ademas, predicates que semanticamente son equivalentes deben unificarse: `imports` en codigo ≈ `depends_on` a nivel build-time. La ontologia define el mapeo de sinonimos.

**Prevention:** Al registrar relaciones, usar predicates del vocabulario canonico. La ontologia maneja el mapeo relationType→predicate y type→predicate automaticamente. No requiere accion manual.

### AP-34: Relacion tipada huerfana -- endpoint inexistente en el vault

- **Severity:** high
- **Enforcement:** audit
- **Detected by:** vault_audit, vault_graph_merge

Una relacion tipada (entity o code) referencia un endpoint que no existe como nota en el vault. Ej: relacion `User -- has_many --> Order` donde no existen `User.md` ni `Order.md`. El grafo enriquecido tendra edges hacia nodos fantasma que nunca resolveran.

**Prevention:** SP-02: verificar que los endpoints existan antes de registrar la relacion. Ejecutar vault_search o vault_list para confirmar que las notas referenciadas en fromEntity/toEntity existen en el vault.

### AP-35: Silos de relacion -- sistemas de grafos aislados

- **Severity:** high
- **Enforcement:** audit
- **Detected by:** vault_audit, vault_graph_merge

El vault mantiene tres sistemas de relaciones en silos aislados: (a) wiki-links en graph.json, (b) entity relations en 06_Diagrams/entity/*-relations.json, (c) code relations en 11_Code/.code-index.json. Ninguno de estos sistemas se integra con los otros, produciendo un grafo de conocimiento fragmentado. vault_impact y BFS solo ven wiki-links, ignorando relaciones semanticas ricas registradas en los otros sistemas.

**Prevention:** Ejecutar vault_graph_merge periodicamente (recomendado: cada sesion o cada vez que se registren nuevas relaciones). vault_graph --typed genera graph-enriched.json que unifica los tres sistemas.

### AP-36: Contención e idempotencia -- side-effects fuera del vault o no rastreables

- **Severity:** critical
- **Enforcement:** guard+audit
- **Detected by:** vault_norms

Toda operación de tooling debe: (1) escribir ÚNICAMENTE dentro del vault root (backups, traces, locks, stubs, logs incluidos); (2) ser idempotente -- ejecutarla dos veces no duplica artefactos ni carpetas; (3) dejar sus artefactos indexados o en ubicaciones registradas (vault_registry) para rastreabilidad. Casos históricos: vault-backups escrito en el abuelo del repo, 00_System/99_Index generados fuera del vault por detección de root defectuosa, .bak junto a nodos de contenido.

**Prevention:** Rutas de salida derivadas SIEMPRE de VAULT_ROOT (nunca de __file__ ni cwd). Artefactos de mantenimiento van a 02_Observability/maintenance/ o 00_System/. vault_norms --audit detecta artefactos sueltos y secciones sin índice.

### AP-37: No-op silencioso -- ok: true sin indicador de trabajo

- **Severity:** high
- **Enforcement:** audit
- **Detected by:** vault_noop_audit

Una tool con side effects declarados devuelve ok: true sin exponer ningún campo que distinga 'hice N cosas' de 'no hice nada'. `ok: true` a secas es una afirmación no falsable: ni un test ni un agente pueden detectar que la operación fue vacía. Toda tool que modifica estado debe declarar un indicador de trabajo en declared_returns (changed, applied, count, migrations_applied, fixes_applied, skipped, no_op…) y devolverlo siempre, también cuando vale 0.

**Prevention:** Declarar el indicador en tool-spec.json y devolverlo desde la tool. vault_noop_audit --check compara el catálogo contra una baseline congelada: la deuda histórica no bloquea, pero NO puede crecer.

### AP-38: Vocabulario validado después de escribir, no antes

- **Severity:** high
- **Enforcement:** guard+audit
- **Detected by:** vault_norms

Un campo con vocabulario cerrado se acepta tal cual en la escritura y se comprueba en un audit posterior. El audit no lo ejecuta nadie -- en 1.356 ejecuciones registradas del parque real, `vault_norms` no aparece ni una vez -- así que el vocabulario no gobierna: solo documenta una intención. Agravante: que varias tools publiquen vocabularios distintos para el mismo campo (AP-05 aplicado al dato). Un campo canónico se normaliza en el punto de escritura y rechaza lo que no pueda derivar; los ejes de dominio legítimos (resultado de un test, fase de un incidente) van a su propio campo, no compiten por `status`.

**Prevention:** STATUS_SYNONYMS + normalize_status() normalizan en vault_write antes de emitir. Las tools con eje propio llaman a status_frontmatter_lines(), que emite `status` canónico y el campo de dominio desde DOMAIN_STATUS_VOCABS. Lo que arrastraba información y no era estado se conserva en status_note: no-derogación aplicada al dato.

### AP-39: Vocabulario abierto sin memoria

- **Severity:** medium
- **Enforcement:** guard+audit
- **Detected by:** vault_tags, vault_norms

Un campo con vocabulario abierto (tags) admite términos nuevos sin dejar constancia de quién los introdujo ni cuándo. Sin registro no hay continuidad: cada sesión reinventa las palabras de la anterior, y el vocabulario crece sin converger -- 1.180 términos para 6.358 usos, el 45% usado una sola vez. A diferencia de AP-38, la respuesta correcta NO es rechazar: un vocabulario abierto que rechaza empuja a omitir el campo, y entonces lo que se incumple es AP-26. Lo que hay que cerrar es el olvido, no la entrada.

**Prevention:** vault_write llama a vault_tags.apply_vocabulary() antes de emitir: colapsa contra el registro canónico lo que es demostrablemente la misma palabra (normalize_tag + singular_tag) y admite el término nuevo tal cual. Una vez la nota está en disco, record_new_tags() lo anota en la bitácora append-only 19_Audits/vocabulary/tag-ledger.json con agente, fecha y nota de origen. Inventar sigue siendo posible; deja de ser silencioso.

### AP-40: Contrato publicado que la CLI rechaza

- **Severity:** high
- **Enforcement:** guard+audit
- **Detected by:** vault_mcp_catalog, vault_norms

Una tool publica en su catálogo parámetros que su propio argparse no acepta. La tool aparece en tools/list, se puede invocar, y falla siempre con 'unrecognized arguments'. Medido en v39: 45 de 82 tools conciliables publicaban al menos un param inexistente -- más de la mitad de la superficie MCP era inalcanzable sin que nada lo señalara, porque el guard de sincronía comparaba el JSON contra el Python: dos copias de la misma equivocación coinciden perfectamente.

**Prevention:** El contrato de argumentos lo declara argparse, no el catálogo: vault_mcp_catalog.argparse_params() lee los add_argument del script y reconciled_params() publica solo lo que la CLI acepta, conservando la descripción escrita a mano cuando el nombre coincide. vault_mcp_catalog --check-params audita el JSON ya generado (que es lo que el servidor consume) contra el argparse real.

### AP-41: Máquina de estados declarada sin verificar

- **Severity:** high
- **Enforcement:** guard+audit
- **Detected by:** vault_norms

El estándar declara STATUS_TRANSITIONS --las transiciones válidas del ciclo de vida de una nota-- y no las recorre nadie: su único consumidor era su propio test de coherencia. Un estado que no controla su transición es una etiqueta, no un ciclo de vida: una nota 'archived' podía volver a 'draft', o saltar de 'planned' a 'verified' sin pasar por revisión, y ningún guard lo veía. Es la misma forma del fallo histórico del estándar --declarar sin ejecutar-- con la agravante de que existía un test en verde que verificaba que el grafo estaba bien dibujado, no que alguien lo recorriera.

**Prevention:** vault_write lee el `status` de la nota en disco antes de sobrescribirla y rechaza la transición que no está en STATUS_TRANSITIONS, citando los destinos válidos. Una actualización que no menciona `status` conserva el estado previo en vez de caer al default 'draft'. Las transiciones ya ocurridas se reportan desde .history/ con vault_norms --audit: se anotan, no se reescriben, porque el estado actual es un hecho.

### AP-42: Tool publicada sin haberse ejecutado nunca

- **Severity:** high
- **Enforcement:** guard+audit
- **Detected by:** vault_smoke, vault_norms

Una tool se publica en el catálogo MCP porque responde a `--help` y porque su entrada existe. `--help` demuestra que el argparse se construye: no que el módulo importe sus dependencias, ni que el ejemplo documentado sea aceptado por la CLI, ni que la salida sea el JSON que el contrato promete. La primera medición dio 41 de 87 tools cuyo ejemplo documentado no llegaba a emitir un JSON con `ok` --36 de ellas porque el ejemplo del catálogo usaba flags que la CLI rechazaba, exactamente el defecto de AP-40 trasladado a la superficie de documentación.

**Prevention:** vault_smoke ejecuta el ejemplo documentado de cada tool contra una copia desechable del vault de pruebas y exige tres cosas: que termine, que su salida sea JSON y que ese JSON tenga `ok`. Un `ok: false` bien formado aprueba: lo que se persigue es el fallo mudo. La baseline solo puede encoger y quedó en 0, así que es un guard duro desde el primer día. Las tools sin invocación posible (un servicio HTTP que no retorna) se declaran en SIN_SMOKE con su motivo, nunca se omiten en silencio.

### AP-43: Norma sin refuerzo en el punto de uso

- **Severity:** high
- **Enforcement:** guard+audit
- **Detected by:** vault_voice, vault_norms

El catálogo de normas está completo, versionado y con guards, pero el agente que documenta el vault no lo tiene delante mientras trabaja: se entera de que una norma existe cuando la incumple --y solo si esa norma es una de las 14 que previenen, no una de las 33 que se limitan a detectar en un audit que puede no correrse nunca. El refuerzo llega tarde, fuera de contexto o no llega. Una norma que el agente no ve en el momento de escribir no gobierna la escritura: gobierna el post-mortem.

**Prevention:** vault_errors.wrap_main --el único punto por el que ya pasa la salida de todas las tools-- añade a cada resultado un bloque `vault_says` derivado de NORM_CATALOG y del estado real de esa llamada: qué norma acaba de actuar, cuántas notas cambiaron, qué mirar a continuación. El refuerzo rota entre las normas que gobiernan esa tool para no degradarse en ruido fijo. vault_voice --coverage nombra las normas que ninguna tool pronuncia.

### AP-44: Verificación autoconsistente -- la tool se certifica a sí misma

- **Severity:** critical
- **Enforcement:** guard+audit
- **Detected by:** vault_norms, vault_audit

Una tool escribe o mide con un criterio propio y verifica el resultado con ESE MISMO criterio, en vez de con el que usa el consumidor real --Obsidian al resolver un enlace, el parser de Mermaid al dibujar, YAML al leer un frontmatter, el audit del propio estándar al juzgar la nota que otra tool acaba de escribir. La tool queda internamente coherente y por eso mismo ciega a su propio fallo: no puede detectar el error porque lo comete en los dos lados de la comparación. Es más caro que un bug normal, porque el guard sale en verde y dirige el trabajo hacia donde no hay problema: reescribir enlaces que funcionan, 'corregir' diagramas válidos, retaguear notas ya etiquetadas.

**Prevention:** Verificar con el criterio del consumidor, no con el propio: resolver wikilinks por nombre de fichero y `aliases:` --nunca por `title:`, que Obsidian no mira--, leer frontmatter con `yaml.safe_load` y no con un regex por líneas, y validar Mermaid contra su gramática real. Toda tool que escribe reevalúa el resultado releyendo del disco. Un frontmatter ilegible devuelve error explícito, nunca `{}` silencioso, que es lo que hace que un write path anteponga un segundo bloque y corrompa la nota. Y toda medida se contrasta contra un vault preexistente ajeno al estándar: `vault-sandbox/` lo genera el propio estándar y comparte sus supuestos, así que no puede exhibir este fallo.

### AP-45: Cobertura sin evidencia -- la nota existe para llenar la sección

- **Severity:** high
- **Enforcement:** guard+audit
- **Detected by:** vault_norms, vault_audit

Una nota se crea porque una sección estaba vacía, no porque hubiera algo que afirmar. Su cuerpo son encabezados y marcadores de pendiente --`_Pendiente_`, `TODO`, `-- No detectados`-- y no enlaza con nada. Sube la cobertura y baja la fiabilidad: el conteo de notas dice que la sección está cubierta, el health score la cuenta como nota real, y el siguiente lector la abre esperando contenido. Es más caro que la ausencia, porque la ausencia sí se ve: un hueco invita a llenarlo, un relleno declara que ya está hecho. El generador que la escribió creía estar documentando.

**Prevention:** No escribir la nota sin evidencia detrás. Un generador que no encuentra contenido real para una sección lo declara en `warnings` y en `next_steps` --que es información útil-- en vez de emitir un stub, que es desinformación. El andamiaje declarado sí es legítimo: los primers de vault_init llevan `status: template` y quedan exentos, porque anuncian lo que son. Secciones dirigidas por eventos (18_Bugs, 19_Audits, 20_Quarantine) se quedan vacías hasta que ocurre el evento.

### AP-46: Frontmatter a mano -- cada tool es su propio escritor

- **Severity:** high
- **Enforcement:** guard+audit
- **Detected by:** vault_norms

Veintiséis tools montan el frontmatter concatenando líneas y tres importan el write path canónico. Cada concatenación es un segundo autor del formato sin guard detrás: el bloque se cierra o no, `type:` está o no, la fecha lleva el formato de quien la escribió. El fallo no se ve al escribir --la tool devuelve `ok: true` porque el fichero se creó-- sino al auditar, y para entonces la nota ya es el dato. Es el mismo patrón que produjo 22 implementaciones de `slugify` y tres verdades para la lista de secciones: una fuente única declarada en la documentación y N implementaciones en el código. `vault_migrate_docs` cortaba el documento por la línea 7 y llevaba versiones publicándose así, con el bloque de frontmatter sin cerrar.

**Prevention:** El write path valida lo que escribe releyendo el resultado, no confiando en cómo se construyó: `atomic_write_text` rechaza un bloque de frontmatter que abre y no cierra o que no parsea, y registra el que parsea pero sale sin `type:`. Así el guard alcanza a las 26 tools sin reescribir ninguna, y la adopción de `vault_write` puede ser gradual. Verificar con el criterio del consumidor --`yaml.safe_load`, no un regex por líneas-- es AP-44 aplicado al generador.

### AP-47: Artefacto derivado desfasado -- el índice dejó de reflejar el disco

- **Severity:** high
- **Enforcement:** guard+audit
- **Detected by:** vault_norms, vault_reindex

El vault es la fuente de verdad y `search-index.json` y `graph.json` son proyecciones suyas. Una escritura que no pasa por `vault_write` --un agente remoto, una tool que escribe la nota y no toca el índice, una copia a mano-- deja la proyección atrás, y a partir de ahí el agente busca sobre un mapa viejo: la nota existe y `vault_search` no la encuentra, así que la vuelve a escribir. La duplicación no es un descuido del agente, es la consecuencia lógica de un índice que miente.

El estándar no lleva base de datos por decisión normativa, y con consistencia eventual el desfase es esperable. Lo que no es aceptable es que **nadie lo mida**: `vault_reindex --check` comprobaba `len(notes) > 0`, de modo que un índice con una entrada sobre un vault de 300 notas pasaba la puerta.

**Prevention:** `vault_reindex --check` contrasta disco contra índice con el mismo criterio con el que reconstruye --una sola función, `_notas_en_disco()`, para que la comprobación y el arreglo no puedan medir cosas distintas (AP-44)-- y reporta las dos direcciones: notas invisibles para la búsqueda y entradas que apuntan a ficheros que ya no están. El remedio es `vault_reindex`, y por eso la norma se audita en vez de bloquear: el desfase es un estado a reconciliar, no una escritura a rechazar.

### AP-48: Implementación paralela por camino de acceso

- **Severity:** critical
- **Enforcement:** guard+audit
- **Detected by:** vault_norms, vault_mcp_catalog

La misma tool publicada tiene dos implementaciones y cuál se ejecuta depende de por dónde entres. No es una fachada sobre un núcleo común: son dos cuerpos de código que nadie contrasta, con un solo nombre y un solo contrato publicado -- así que el contrato describe como mucho a uno de los dos.

Es AP-05 (múltiples fuentes de verdad) desplazado del dato al camino de ejecución, y se le parece poco en lo importante: dos definiciones de un vocabulario acaban divergiendo y alguien lo nota al leerlas, mientras que dos implementaciones divergen **en silencio** porque cada una tiene su propio público. La suite prueba una; el agente ejecuta la otra; las dos están verdes.

Medido en v39.5 sobre el servidor MCP: nueve tools con backend nativo en Node, siete de ellas con script Python del mismo nombre. Ninguna de las siete compartía un solo campo de envelope con el contrato de `00_System/tool-spec.json` -- `vault_fundamentals` devolvía `compliance_pct`/`passed` donde el contrato dice `path`/`total`. Y la divergencia peor no era de forma sino de efecto: la implementación nativa de `vault_graph` no escribía el grafo, así que un agente la llamaba, recibía `ok: true` y el índice se quedaba desfasado -- AP-37 y AP-47 servidos por el único camino que un agente real usa. `vault_smoke` recorría las 91 tools del catálogo ejecutando el `.py`: probaba exactamente la implementación que el agente no toca.

**Prevention:** Backend nativo solo para lo que **no tiene** implementación en Python; todo lo demás cae al runner, que es donde vive el contrato publicado. La implementación desplazada no se borra (no-derogación): se anota `superseded_by:` y se deja fuera del despacho. La regla se comprueba por comportamiento y no por lectura del código -- se llama la tool por MCP y se contrasta el envelope contra el contrato, que es el criterio del consumidor y no el propio (AP-44).

### AP-49: Vínculo resuelto en tiempo de import

- **Severity:** high
- **Enforcement:** guard+audit
- **Detected by:** vault_norms, vault_arch

Un módulo deriva su ruta, su configuración o su dependencia en el momento de **importarse**, no en el de usarse. `SYSTEM_DIR = VAULT_ROOT / '00_System'` a nivel de módulo se evalúa una sola vez, cuando el intérprete carga el fichero, y a partir de ahí es una constante.

Lo grave no es la constante: es que deja **inerte una costura que existe**. `vault_io.set_vault_root()` está publicado y 12 tests lo usan, pero no puede reapuntar a un módulo que ya calculó su ruta al cargar. La inyección parece disponible y no lo está, que es peor que no tenerla -- quien la usa cree haber redirigido la escritura.

Medido en v40.0 por el propio guard: **0 vínculos congelados en 0 módulos**. Eran 82 en 62 módulos antes de empezar a migrar contextos al dominio, y cayeron uno a uno: Durabilidad los dejó en 77, Índices en 69, Grafo en 51, Consulta en 45, Gobernanza en 38, Ciclo de vida en 34, Meta-toolkit en 31 y Autoría --donde estaban los 31 últimos, el 100% de la deuda que quedaba-- en 0. Llegar a cero destapó la otra mitad de la norma: veinte módulos seguían haciendo `from vault_io import VAULT_ROOT` y usándolo **dentro de funciones**. No son asignaciones de nivel de módulo, así que el guard los daba por limpios, y seguían dependiendo del paliativo de reanclaje que el refactor existe para no necesitar. Se mide aparte (`raw_vault_root_imports`), también en cero, y el caso legítimo se pide con alias. La cifra es la que cuenta `vault_arch --check`, no una estimación a ojo: la norma y su puerta miden lo mismo o la norma no es comprobable. La consecuencia visible era que `cli/runner.py` aislaba cada tool en un subproceso citando "estado a nivel de módulo" como razón: el aislamiento por proceso no era una decisión de diseño libre sino la compensación de este acoplamiento. Saldada la deuda, esa razón caducó y quedó anotada allí mismo; el subproceso se conserva por las otras dos que siguen siendo ciertas --timeout que puede matar lo que vigila, y envelope sin reinterpretar--. El refactor lo hizo posible, no conveniente.

**Prevention:** La raíz y sus derivadas se reciben, no se importan: el dominio toma un contexto (`VaultContext`) y el adaptador lo construye por llamada. Si un módulo necesita la ruta, la resuelve **tarde** con `get_vault_root()` dentro de la función. El guard es AST sobre asignaciones de nivel de módulo que derivan de `VAULT_ROOT`, con baseline que solo puede encoger -- la deuda medida no se arregla en un commit, pero no puede crecer.

### AP-50: Decisión duplicada sin dueño declarado

- **Severity:** high
- **Enforcement:** guard+audit
- **Detected by:** vault_norms, vault_arch

La misma **decisión** --qué valores son válidos, cuál es el default, cómo se escapa un campo-- se toma en más de un punto de uso sin que ningún registro declare quién manda. No es AP-05: aquel habla de un **dato** con dos fuentes, y se ve porque las dos copias divergen. Esto se ve cuando ya divergieron, que es tarde.

Lo que lo hace caro es que cada copia parece correcta en su sitio. `SEVERITIES = ['critical', 'high', 'medium', 'low']` no está mal escrito en ninguno de los catorce ficheros donde se midió; está mal que sean catorce y que nada los compare. El día que el registro cambie, la copia que se quede atrás rechazará un valor válido o aceptará uno inventado, y ningún test lo notará porque cada fichero sigue siendo coherente consigo mismo.

Medido en v40.1 por sus tres guards: **0 copias de vocabulario, 0 lecturas de entorno sin declarar, 0 vocabularios sin contexto dueño**. Eran 14 copias del vocabulario en 13 módulos --cuatro como `choices=` de argparse y diez como constante-- y 13 variables de entorno con su default escrito en cada punto de lectura, de las que solo seis estaban documentadas. Dos ya habían divergido antes de que existiera el guard: `VAULT_VOICE` se comparaba contra `'verbose'` en un módulo y contra `'0'` con default `'1'` en otro, y `VAULT_MCP_LOG` estaba declarada como fichero de log mientras el único código que la lee la usa como nivel con default `'info'`.

El dueño es la mitad que faltaba. `vault_norms.DOMAIN_STATUS_VOCABS` ya había resuelto esto para `status` en v39 y se quedó solo: compartir la constante evita la copia, pero no contesta quién decide cuándo cambia. Por eso cada entrada del registro declara el contexto acotado que manda sobre ella, y ese contexto tiene que existir en `vault_arch.CONTEXTS`.

**Prevention:** Registro canónico con dueño, consumidores derivados, guard sin baseline. Los vocabularios cerrados en `vault_vocabulario.py`, la configuración en `vault_entorno.py`, y `vault_arch --check` fallando si aparece una copia, una lectura sin declarar o un vocabulario huérfano. **Sin baseline a propósito**: las catorce copias se saldaron al declarar el registro, así que la puerta nace en cero y una baseline solo serviría para admitir la número quince. Lo que ya tiene registro canónico no se copia: se declara `derivado_de` y se resuelve al llamarse, nunca al importarse (AP-49). Un dato canónico que no es puerto de su contexto se acaba copiando -- los tres registros que `CLAUDE.md` declara fuente única de verdad se leían por fuera de la superficie publicada, y así nacieron las catorce copias.

### AP-51: La tool culpa al dato de su propio fallo

- **Severity:** high
- **Enforcement:** guard+audit
- **Detected by:** vault_blame_audit

Una tool falla al leer o al interpretar algo, se traga el fallo y devuelve un vacio que el llamante no puede distinguir de un resultado legitimo. El error deja de ser un error y pasa a ser un **hecho sobre el vault**: el informe que lo agregue dira que N notas no tienen aliases, y no sera cierto -- es que no se pudieron leer.

No es lo mismo *no hay* que *no pude mirar*, y esa es toda la norma. AP-44 cubre la mitad de arriba --verificar con el criterio del consumidor y no con el propio--; esta cubre la de abajo, que es el mecanismo por el que un fallo propio acaba pareciendo un dato malo. Salio al ejecutar contra un vault ajeno al estandar (**regla 7**): tres tools declaraban invalidas notas que Obsidian leia sin problema. Las notas estaban bien; el criterio que las media, no.

Lo que la norma **no** prohibe es capturar amplio. Prohibe capturar amplio y callarse: devolver `ok: false` con el error es correcto porque el llamante recibe la mala noticia y decide. Capturar `FileNotFoundError` tampoco infringe: es un criterio, el autor sabe que tolera y por que. Lo que infringe es `except Exception: return []`.

Medida en v40.1: **86 sitios en 37 modulos**. Nace con baseline por la misma razon que AP-37 --que empezo en 55 y llego a 0--: un guard que falla en 86 sitios se desactiva el primer dia, y un guard desactivado no protege nada. La baseline solo puede encoger.

El propio detector estreno el fallo que persigue. La primera version midio 101 sitios porque clasificaba `except yaml.YAMLError` como captura amplia: son `ast.Attribute` y no `ast.Name`, asi que caian en la rama del `except` desnudo. Contaba como infraccion justo las capturas mas precisas del repo. Quince falsos positivos, y el error era el de AP-44 cometido dentro del guard.

**Prevention:** Capturar la excepcion concreta que se sabe tolerar, y si se captura amplio, **exponer**: devolver el fallo en el envelope en vez de un vacio. Cuando el vacio es la respuesta correcta, distinguirlo del vacio por fallo con un campo aparte (`unreadable`, `errors`) para que el agregado no los confunda. `vault_blame_audit --check --strict` mide por AST y no por texto: un detector que buscara la cadena `except Exception` no veria la diferencia entre devolver un vacio y devolver un envelope con `ok: false`, que es toda la distincion que la norma sostiene.

### AP-52: El error se emite fuera del contrato del catalogo

- **Severity:** medium
- **Enforcement:** guard+audit
- **Detected by:** vault_error_contract

Una tool falla, lo dice, y lo dice mal: devuelve `{"ok": false, "error": "..."}` escrito a mano en vez de pasar por `vault_errors.emit_error`. La frase es correcta; el contrato, no. El envelope del catalogo trae `error_code`, `category`, `severity`, `recovery` y `timestamp`; el escrito a mano no trae ninguno.

Importa porque el consumidor no lee la frase: **decide por el codigo**. El servidor MCP y `cli/` deciden si reintentar, abortar o pedir permiso mirando `error_code` y `recovery.action`. Sin ellos, un fallo con recuperacion conocida llega como un fallo opaco, y la unica salida del agente que lo recibe es adivinar.

Es AP-05 aplicada al **contrato de error** --hay un registro que declara como se nombra y se recupera cada fallo, y 158 sitios que lo deciden por su cuenta-- y es AP-51 vista desde el otro lado: alli el fallo se disfrazaba de dato, aqui llega como fallo pero desnudo de todo lo que lo hace accionable.

Salio de la caracterizacion maliciosa: invocar las 94 tools de forma malformada y mirar **como** fallan, no si fallan. El grueso estaba limpio --las 45 tools con `required_args` rechazan la invocacion vacia por argparse, y las 92 tools Python rechazan un flag desconocido-- y el hallazgo estaba en la forma del envelope, no en su ausencia.

Medida en v40.2: **158 sitios en 58 modulos**. Nace con baseline por la misma razon que AP-37 y AP-51: un guard que falla en 158 sitios se desactiva el primer dia. La baseline solo puede encoger.

El guard mide **forma y no flujo**: un dict con `ok: False` y pinta de envelope que no lleva `error_code`. No sigue el valor hasta stdout, asi que cuenta tambien envelopes internos que nunca se imprimen. Eso se declara en vez de esconderse: un guard que promete una precision que no tiene es la clase de afirmacion no falsable que AP-37 persigue.

**Prevention:** Emitir por `emit_error(tool, CODIGO, mensaje)` y, si el codigo no existe, anadirlo a `ERROR_CATALOG` -- que es donde vive la decision de como se recupera ese fallo. Anadir el codigo cuesta una linea; no anadirlo traslada el coste a cada consumidor, para siempre. `vault_error_contract --check --strict` mide por AST.

### AP-53: El historial se afirma a mano y nadie lo contrasta con git

- **Severity:** medium
- **Enforcement:** guard
- **Detected by:** vault_changelog_check

La documentacion afirma un hecho del historial --que la version v39.0 la introdujo el commit `00731c6` el 2026-07-25-- y ese hecho vive tambien en git, que es donde de verdad existe. Una de las dos copias se escribe a mano y ninguna se contrasta con la otra, asi que la de mano se queda atras sin que nada lo note.

Es AP-05 aplicada al **historial**, y AP-47 en su forma menos visible: AP-47 persigue cifras escritas a mano --cuantas tools, cuantas normas-- y una fecha o un hash de commit son la misma clase de dato derivable, solo que nadie los lee como una cifra.

Medido en v40.7 sobre el changelog del manifiesto: **55 entradas, 31 con hash real, los 31 existen** --ninguno inventado-- y **5 fechas contradecian al commit que citaban**. Cuatro por un dia; la de v39.0 por once. Esa entrada arrastra ademas un commit de fijado que corrigio el hash (`13bf9ca -> 00731c6`) y no toco la fecha: la correccion parcial es el modo de fallo tipico, porque quien corrige mira el dato que le fallo y no el que viaja con el.

Detras hay un huevo y una gallina que conviene nombrar, porque es lo que empuja a escribir el dato a mano: la entrada tiene que citar el hash del commit que la contiene, y ese hash no existe hasta que el commit esta hecho. La salida fue un ritual de dos commits --`feat: vX` con `git: pending`, luego `docs: fijar hash`-- que aparece ocho veces en las ultimas veinte entradas del historial y cuyo segundo paso depende de que alguien se acuerde. Una norma que solo prohibe no sirve aqui: hay que dar el comando que hace el paso, o se seguira haciendo a mano.

**Prevention:** Derivar el dato del repositorio y comprobarlo en una puerta. `vault_changelog_check --check --strict` contrasta hash, fecha --de autoria, `%as`, que un rebase no reescribe--, `pending` y orden. Y `--fijar-hash` convierte en comando el paso manual que originaba la divergencia.

### AP-54: El lock falla y se escribe igual

- **Severity:** high
- **Enforcement:** guard
- **Detected by:** vault_arch

Un bloque toma un `file_lock`, no lo consigue, y en el handler escribe de todos modos sin sincronizar. El razonamiento que lleva ahi es que perder el dato es peor que escribirlo sin lock. Es al reves, y por una razon que se ve al leer el `TimeoutError`: ese error significa que **otro lo tiene tomado ahora mismo**. La escritura del handler no es una carrera improbable, es la unica situacion en la que ese codigo llega a ejecutarse, y entra justo encima de la de quien si consiguio el lock.

Medido en v40.7 en `vault_sdd_init`, que se pasaba del timeout de 60s de la tool y moria dejando `docs/sdd/` a medio escribir despues de haber anunciado `Drift status: PASS`. La medida: **26 tomas del lock del fichero de trazas, 13 fallidas, 65,14s de espera pura** --13 x 5s exactos--. Esas 13 acababan reescribiendo el trace sin lock mientras el llamante externo lo estaba reemplazando.

La causa de las esperas era distinta de la norma y se corrigio aparte: `file_lock` no era reentrante, asi que un hilo que volvia a pedir un lock que el mismo sostenia esperaba el timeout entero contra si mismo. Conviene separar las dos cosas --la causa se arregla una vez en el kernel; la reaccion es la que se repite en cada llamante y la que esta norma vigila.

Omitir la escritura al fallar el lock **no** es esta norma: es la respuesta correcta, y `vault_quality_check` ya la tenia.

**Prevention:** Al fallar el lock, descartar la escritura o propagar el error -- nunca escribir sin sincronizar. `vault_arch --check --strict` reporta el patron en `unsynced_writes`.

### AP-55: El catálogo de normas se certifica a sí mismo

- **Severity:** high
- **Enforcement:** guard+audit
- **Detected by:** vault_norms_coherence

`NORM_CATALOG` declara por norma qué tools la hacen cumplir (`tools_enforcing`) y cuáles la detectan (`tools_detecting`). Los dos campos se escriben a mano y nada los contrasta contra lo que las tools hacen: la cobertura publicada es una promesa sin verificar.

Lo caro no es la lista, es el guard. `vault_voice.coverage()` existe para detectar normas mudas y comprueba que una norma tenga `tools_enforcing` o `tools_detecting` **leyendo `tools_enforcing` y `tools_detecting`**. Verifica el catálogo contra el catálogo, así que da verde sobre las 47 afirmaciones que ningún módulo respalda y es estructuralmente incapaz de verlas. Es AP-44 cometido dentro del guard de AP-43 -- la tercera vez que el criterio de verificación sale del objeto verificado, tras el test de cruces de v40.8 y el cero de AP-52 medido sobre un subconjunto en v40.9.

La forma general: **dos registros canónicos que hablan del mismo hecho no pueden contradecirse sin que algo falle.** Medido en v40.10: 54 valores de `tools_*` que mezclaban la tool con su flag y ningún consumidor podía resolver; AP-22 declarada `critical` mientras `vault_audit` la penalizaba con 2 puntos por unidad frente a los 5 de AP-24, que el catálogo llamaba `high`; y 47 afirmaciones de cobertura sin una línea de código que nombre la norma. `AP-05` --`critical`-- nombra `vault_graph_inspect` como detector, y esa tool no la menciona en ninguna parte.

**Prevention:** `vault_norms_coherence --check --strict` cruza el catálogo con el código y con `PENALIZACIONES`. La traza sin respaldo lleva baseline que solo puede encoger, y se salda de dos formas honestas: que el código nombre la norma en el sitio que la aplica, o que el catálogo deje de afirmar una cobertura que no tiene. Ampliar la baseline es la tercera y no lo es.

### AP-56: Frontmatter presente que el consumidor no puede leer

- **Severity:** high
- **Enforcement:** guard+audit
- **Detected by:** vault_frontmatter_heal, vault_foreign_check

La nota abre `---`, escribe sus claves y, para `yaml.safe_load`, no tiene frontmatter: ni id, ni tags, ni tipo, ni estado. El bloque **se ve** al abrir el fichero, y por eso nadie lo revisa. El dato parece estar y no está.

No es AP-28, que es la nota que nunca tuvo bloque y se cuenta sola. Aquí el hueco es invisible a ojo y solo aparece al medir con el parser real (AP-44).

Dos causas, medidas sobre doce notas de cuatro vaults consumidores: **escalar sin escapar** --`title: Overview: demo` no es un mapeo, nueve de las doce-- y **delimitador sin cerrar**, las otras tres, donde el bloque nunca se cierra y el parser se traga la nota entera hasta reventar cientos de líneas más abajo, en un bloque de código. El mensaje de YAML señala ahí, que no es donde está el fallo; por eso llevaban meses así.

v40.2 arregló la prevención: `yaml_scalar` escapa antes de escribir. Lo que faltaba era la otra mitad -- nada reparaba lo que ya estaba en disco, y `vault_fix_brackets` llevaba versiones haciendo exactamente eso para AP-22/AP-24.

**Prevention:** Escribir por tool, nunca a mano (SP-04): el write path pasa todo escalar por `yaml_scalar` desde v40.2. Lo ya escrito se repara con `vault_frontmatter_heal --apply`, que solo toca las dos causas mecánicas y se niega a adivinar el resto: completar un YAML truncado inventa dato, que es peor que el hueco.

### AP-57: Criterio con dueño, reimplementado en la medida

- **Severity:** high
- **Enforcement:** guard
- **Detected by:** vault_criterios

Un **criterio** --qué cuenta como instantánea congelada, qué es documentación del estándar y no una nota, qué es código y no un enlace-- tiene un dueño canónico en el toolkit, y otro módulo lo vuelve a decidir por su cuenta con un `if` local.

No es AP-50, que habla de **patrones regex** y de vocabularios: aquellos son datos que alguien puede leer y comparar. Un criterio vive enterrado en una condición, así que la copia sobrevive años sin que nadie la vea, y el día que el dueño cambia solo cambia el dueño. `vault_graph_fix` llevaba su propio `skip_set` de instantáneas y ya divergía de `vault_io.SNAPSHOT_DIRS`; como esa tool **escribe**, la divergencia no inflaba una métrica: reparaba dentro de una instantánea, que es dejar de serlo.

Sale de v40.12: cuatro defectos de `vault_foreign_check` arreglados en una tanda, los cuatro con la misma forma --el registro canónico existía y la tool no lo consultaba--. Uno de ellos tenía el sentido de error peligroso: resolver destinos por basename ponía la medida **verde** justo donde Obsidian pinta el enlace roto. La regla 4 pide norma, no cuatro parches.

**Prevention:** Dos registros en `vault_criterios`. `CRITERIOS_CON_DUENO`: criterio, dueño, símbolo por el que se consulta y las constantes que lo delatan. `FRONTERAS`: cada frontera de lenguaje con su **zona dueña** (clave de `vault_arch.CONTEXTS`), su **norma** (código de `vault_norms`) y la **pasarela** --el artefacto derivado-- por la que el criterio debe cruzar. Al otro lado la exención no es importar al dueño, que no se puede: es leer la pasarela.

`vault_criterios --check --strict` (puerta 15) falla si aparece una copia nueva; la baseline **solo encoge** y se salda importando al dueño o leyendo la pasarela, no ampliándola. El alcance se declara: un fichero ejecutable de otro lenguaje fuera de toda zona declarada sale como `frontera_no_declarada`, porque un sitio donde una copia no se vería vale tanto como una copia.

El límite se declara antes de que nadie se apoye en él: la detección es **sintáctica**. Un módulo puede reimplementar un criterio sin repetir ninguna constante y esta medida no lo verá. Verde no prueba que no haya copias -- prueba que no hay copias de la forma que sabemos reconocer, que es exactamente lo que da un linter y es preferible a no mirar.

### AP-58: Ciclo esquivado con un import diferido

- **Severity:** high
- **Enforcement:** guard
- **Detected by:** vault_ciclos

Dos módulos se necesitan mutuamente, y en vez de invertir la dependencia se mete uno de los `import` dentro del cuerpo de una función. Python deja de quejarse, el ciclo sigue ahí y **deja de verse**: cualquier medida que mire los imports de nivel de módulo dirá cero ciclos con toda honestidad.

Aplicado una vez es una excepción razonable. Aplicado muchas es la arquitectura, tomada sin decidirla. Medido en v40.17 sobre este repo: **92 imports diferidos en 40 módulos**, de los cuales 30 esquivan un ciclo, y contándolos aparece un componente fuertemente conexo de **14 módulos** que contiene el núcleo entero. Ese componente es el que hacía que `vault_errors_trace` --un escritor de trazas de bajo nivel-- importase `vault_io` entero, y el que obliga a `cli/runner.py` a aislar cada tool en un subproceso para que dos raíces no se contaminen.

El daño no es el arranque: es que la dirección de la dependencia deja de ser una decisión revisable. Un ciclo escondido no se discute en revisión porque no aparece en ninguna medida.

**Prevention:** `vault_ciclos --check --strict` (puerta 17) calcula los componentes fuertemente conexos **contando las aristas diferidas**, que es la única forma de que la pregunta se pueda formular. La baseline **solo encoge** y se salda invirtiendo la dependencia --el módulo de bajo nivel deja de pedirle el módulo entero al de alto y se le pasa lo que necesita--, no subiendo el import ni ampliando la baseline.

Dos límites, dichos antes de que nadie se apoye en el verde. Primero: solo entran en la deuda los diferidos que **esquivan un ciclo** (30 de 92); los otros 62 se difieren por coste de arranque o por dependencia opcional y se publican como `deferred_benign` sin congelarse, porque una baseline llena de ruido es una baseline que nadie revisa. Segundo: la medida es del grafo **estático** de módulos. No ve `importlib`, ni un import construido con una cadena, ni el acoplamiento que pasa por el sistema de ficheros o por una variable global compartida.

### AP-59: Núcleo declarado sin contraste

- **Severity:** high
- **Enforcement:** guard+audit
- **Detected by:** vault_kernel

Un sistema declara cuál es su núcleo --la lista de módulos de los que todo lo demás depende-- y **ninguna medida contrasta esa afirmación** contra la forma real del grafo. La pertenencia al core deja de ser un hecho y pasa a ser una costumbre: se hereda de quien escribió la lista, y envejece en la dirección cómoda.

Lo caro no es equivocarse de lista: es que **todo lo que se apoya en ella hereda el error en silencio**. Si un módulo está declarado como núcleo sin serlo, el guard de fronteras lo exime de reglas que sí debería cumplir y sale verde. Si uno lo es sin estar declarado, cada cambio suyo propaga hacia arriba sin que nadie lo trate como un cambio de núcleo. En ambos casos el verde es correcto respecto a un mapa equivocado.

Medido en v40.20 sobre este repo, con la lista **bien elegida** --los cuatro de cabecera eran los correctos y K1 ya estaba verde--: aun así, **tres de quince módulos del kernel no se comportan como núcleo**. `vault_log_error` con fan-in 0, declarado núcleo y sin un solo consumidor; `vault_io` con fan-out 11 y 30 commits; `vault_errors` con 14, sobre una mediana de dominio de 9. Ninguno estaba roto. Ninguno se había visto, porque nadie miraba.

La norma no exige que el núcleo sea perfecto: exige que su pertenencia sea **derivable y contrastada**, y que la distancia entre lo declarado y lo medido se publique en vez de suponerse cero.

**Prevention:** `vault_kernel --check --strict` (puerta 18) mide tres invariantes. **K1** --el núcleo no depende del dominio-- no se reimplementa: se delega en `vault_arch.dependencias_del_kernel()`, porque una tool que mide su propia pureza con su propio criterio es AP-44 cometido en el sitio que existe para detectarlo. **K2** --fan-in alto, fan-out bajo-- sale del dueño único del grafo de imports (`vault_grafo_import`), no de un parser propio. **K3** --estabilidad-- del churn de git, y sin historia disponible emite `desconocido` y nunca `0`: un cero fabricado saldría verde por no haber mirado (AP-51).

Los umbrales **se derivan del escalón** de la distribución --la mayor caída relativa-- y se publican en el envelope con su ratio en cada ejecución. Escribirlos a mano sería AP-47 en la tool que persigue los números a mano; por eso la baseline congela la **pertenencia** (qué módulo incumple qué invariante) y no el umbral, que puede oscilar al crecer el repo.

Dos límites, dichos antes de que nadie se apoye en el verde. Primero: mide el grafo **estático** de imports y hereda sus cegueras (`importlib`, un import por cadena, el acoplamiento por fichero o por variable global). Segundo: mide **forma, no propósito**. Un módulo puede tener fan-in altísimo sin ser núcleo de nada, solo un cajón de utilidades que todo el mundo toca. Verde significa que la lista declarada no contradice a la forma medida.

### AP-60: El guard cobra por declarar y regala el silencio

- **Severity:** medium
- **Enforcement:** guard+audit
- **Detected by:** vault_norms_coherence

Un guard comprueba una propiedad **iterando sobre quien ya la declaró**. Quien no declaró nada queda fuera de su alcance, no por una decisión sino por la forma del bucle. El efecto es un incentivo invertido: declarar cuesta --obliga a mantener lo declarado, a veces a editar el otro extremo-- y callarse sale gratis y verde.

Medido en v40.21 sobre C5 de `vault_norms_coherence`: la comprobación de que dos normas se distinguen recorre `distinguido_de`, así que solo alcanzaba a **13 normas de 71**. Las otras 58 no estaban exentas: estaban invisibles. Y declarar una distinción en AP-59 costó tres ediciones recíprocas y un fallo de puerta, mientras no declarar ninguna habría salido verde a la primera.

Es la misma forma que el repo ya prohíbe en `cobertura_descubierta` --una norma que declara su hueco no cuenta como deuda nueva, porque declararse honestamente no puede salir más caro que callarse--, cometida en el guard que vigila el catálogo donde esa regla está escrita.

**Prevention:** Medir sobre el universo --el catálogo, el registro, el conjunto de módulos-- y no sobre el subconjunto que declaró. Admitir dos salidas honestas, la declaración y la exención con motivo escrito, y ninguna tercera: el silencio se cuenta como deuda. La baseline congela lo que ya estaba y solo encoge; lo que estrena se escribe.

### AP-61: El guard cae con el dato que vino a medir

- **Severity:** high
- **Enforcement:** guard+audit
- **Detected by:** vault_excepcion_declarada

Un handler captura la excepción que una librería **declara** y deja escapar la que esa librería **lanza de verdad**. El `try` parece contener el fallo y no lo contiene: la excepción sube entera y tumba la ejecución completa. Lo caro es la asimetría de alcance -- el dato defectuoso es de una nota, la caída es del barrido entero, así que un solo fichero hostil deja al vault sin medida.

El caso que le dio nombre: `RecursionError` **no hereda de `yaml.YAMLError`**. El parser de PyYAML es recursivo y el frontmatter es dato externo, así que `x: [[[[[…` --doce caracteres de escribir-- desborda la pila dentro de `safe_load`, por encima de cualquier `except yaml.YAMLError`. `vault_lib.parse_frontmatter` lo resolvió y lo dejó escrito; los otros **doce sitios** que habían copiado el mismo `try` no se enteraron de la corrección, y entre ellos estaba `vault_foreign_check`, que es la tool de la regla 7 y por tanto la única que corre contra material que este repo no generó -- exactamente donde el dato hostil aparece.

Es primo de AP-57 y llega por su camino: un criterio copiado envejece por su lado, y aquí envejeció hacia el lado que deja caer la tool.

**Prevention:** `vault_excepcion_declarada --check --strict` recorre los `try` cuyo cuerpo contiene una llamada de riesgo declarada en `RIESGOS` y exige que la excepción que escapa esté nombrada. Se salda **delegando en el dueño que ya la contuvo** --para el frontmatter, `vault_lib.parse_frontmatter`-- y solo cuando la firma de retorno lo impide, nombrándola en la tupla y citando al dueño en un comentario: ampliar la tupla en trece sitios sin dueño es AP-57 cometido al arreglar AP-61.

Límite declarado: solo ve la llamada de riesgo escrita **a la vista** en el cuerpo del `try`. Un `safe_load` detrás de un helper queda fuera del alcance, que es la forma correcta de escribirlo -- así que este guard mide mejor el código que peor está escrito, y eso se publica en vez de suponerse cubierto.

### CN-01: Kebab-case filenames -- nombres de archivo en minúsculas con guiones

- **Severity:** high
- **Enforcement:** guard
- **Detected by:** sin detector declarado

Los archivos .md del vault deben usar kebab-case: minúsculas, palabras separadas por guiones, sin espacios ni caracteres especiales. vault_write aplica slugify() automáticamente al título para generar el filename. Ej: 'ADR-001 Auth Decision' → adr-001-auth-decision.md.

**Prevention:** Siempre usar vault_write para crear notas. Nunca crear archivos .md directamente.

### CN-02: Numbered folder structure -- secciones numeradas como únicos destinos

- **Severity:** high
- **Enforcement:** guard+audit
- **Detected by:** vault_section_index, vault_norms

Solo las secciones numeradas del registro canónico (vault_registry.SECTIONS, fuente de verdad única -- PAT-1) son destinos válidos para notas. Crear carpetas ad-hoc o escribir en la raíz viola este estándar (ver AP-15). NO duplicar la lista aquí: consultarla con vault_folder_registry o vault_registry.

**Prevention:** Elegir la sección más apropiada del vocabulario estándar. AP-15 para raíz del vault.

### CN-03: Standard status vocabulary -- vocabulario canónico de meta.status

- **Severity:** low
- **Enforcement:** audit
- **Detected by:** vault_norms

El campo meta.status (o status en frontmatter) debe usar solo valores de vault_norms.STATUS_VOCAB (fuente única, v38 -- unifica el vocabulario CN-03 original con el ciclo de vida del spec §status): planned | draft | in-progress | reviewed | approved | implemented | verified | deprecated | obsolete | archived | stub | template. Valores fuera del vocabulario rompen filtros de vault_list y vault_audit.

**Prevention:** Usar solo valores de STATUS_VOCAB. vault_norms --audit los valida (CN-03).

### PAT-1: Canonical source anchoring

- **Severity:** N/A
- **Enforcement:** recommended
- **Detected by:** vault_audit

Un dominio = una nota canónica rica. Todas las referencias desde otros contextos son [[wiki-links]] a esa nota canónica, nunca copias del contenido.

**Prevention:** N/A -- es el patrón correcto. Aplicar siempre al crear documentación.

### PAT-2: Stub enrichment gradient

- **Severity:** N/A
- **Enforcement:** recommended
- **Detected by:** vault_audit

Un stub con ≥3 líneas reales se enriquece progresivamente en cada sesión que lo toca. La eliminación solo aplica a skeletons (AP-11) y deceptive skeletons (AP-20).

**Prevention:** N/A -- es el patrón correcto.

### PAT-3: Duplicate chain resolution

- **Severity:** N/A
- **Enforcement:** recommended
- **Detected by:** vault_audit, vault_change_log, vault_write

Algoritmo estándar para resolver duplicados: identificar canónica (más backlinks, más contenido, ubicación más apropiada) → change_log --action deleted → mover a 10_Migrated/ → actualizar wiki-links rotos → verificar con vault_audit.

**Prevention:** N/A -- es el algoritmo de resolución.

### PAT-4: Phased audit execution

- **Severity:** N/A
- **Enforcement:** recommended
- **Detected by:** vault_drift_detect, vault_audit, vault_write, vault_change_log

Las auditorías masivas se ejecutan en 4 fases atómicas: 1-Snapshot (vault_drift_detect --snapshot), 2-Detección (vault_audit), 3-Resolución (vault_write, vault_change_log), 4-Verificación (vault_drift_detect --report).

**Prevention:** N/A -- es el protocolo de auditoría.

### PAT-5: Frontmatter as provenance chain

- **Severity:** N/A
- **Enforcement:** recommended
- **Detected by:** vault_write, vault_audit

Los campos id + createdAt + updatedAt + agent + migratedFrom (si aplica) forman una cadena de custodia completa. Sin esta cadena es imposible auditar de dónde vino un dato o qué agente lo introdujo.

**Prevention:** N/A -- vault_write genera estos campos automáticamente.

### PAT-6: Semantic graph enrichment -- enriquecimiento periodico del grafo

- **Severity:** N/A
- **Enforcement:** recommended
- **Detected by:** vault_graph_merge, vault_audit

Ejecutar vault_graph --typed al final de cada sesion productiva para generar graph-enriched.json con predicates semanticos unificados. El grafo enriquecido combina wiki-links, entity relations y code relations en un solo grafo consultable con filtros por predicate, cardinalidad y tipo de nodo. Esto habilita busquedas de conocimiento semanticas y analisis de impacto con tipos.

**Prevention:** N/A -- es el patron correcto. Agregar vault_graph --typed al session protocol como paso automatico antes de vault_audit.

### SP-01: Delete protocol -- change_log obligatorio antes de eliminar

- **Severity:** critical
- **Enforcement:** audit
- **Detected by:** vault_norms

Antes de eliminar cualquier nota del vault, el agente DEBE llamar: vault_change_log --action deleted --path <nota> --reason <motivo>. Sin este registro, la nota desaparece sin rastro auditado.

**Prevention:** Regla de gobernanza: verificar en .change-log.json antes de delete. Si no hay entrada → llamar vault_change_log primero, luego eliminar.

### SP-02: Forward-link verification -- buscar antes de linkar

- **Severity:** high
- **Enforcement:** guard
- **Detected by:** vault_graph, vault_audit

Antes de escribir [[nombre-nota]] en contenido, verificar que la nota destino ya existe: vault_search(query:'nombre-nota'). Si no hay resultado, escribir en texto plano hasta que la nota exista. vault_write advierte con ghost_links[] (no bloquea) si el target no existe.

**Prevention:** vault_search() antes de cada [[wiki-link]] nuevo. No crear links especulativos.

### SP-03: Session snapshot pattern -- delta antes de operaciones masivas

- **Severity:** medium
- **Enforcement:** audit
- **Detected by:** vault_delta

Antes de cualquier operación masiva (migración, rename en lote, vault_tags --rename múltiple, delete en lote), capturar snapshot con vault_delta --snapshot. Permite detectar regresiones y calcular impacto real de la operación.

**Prevention:** PAT-4 (phased audit): snapshot → operación → vault_audit() → comparar score. vault_delta --snapshot antes de cada sesión con cambios masivos.
