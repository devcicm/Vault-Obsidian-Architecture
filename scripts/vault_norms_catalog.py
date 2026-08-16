#!/usr/bin/env python3
"""Catálogo canónico de normas AP-XX / PAT-X, y el vocabulario de estado.

**Datos, no comportamiento.** Este módulo no lee el vault, no escribe nada y no
importa ninguna tool: es la mitad de `vault_norms` que era una constante de tres
mil líneas. Salió de ahí en v40.26 porque `vault_norms` hacía de catálogo, de
motor y de fachada a la vez, y el 60% del fichero era esta lista.

**Se entra por `vault_norms`, no por aquí.** La fachada reexporta todo lo
público de este módulo, así que ningún llamador tuvo que tocarse al partirlo —
que es lo que hizo el corte barato. Importar directamente de aquí no está
prohibido, pero tampoco es la superficie declarada: los puertos del contexto de
gobernanza siguen nombrando `vault_norms:NORM_CATALOG` y compañía.

**Por qué el vocabulario de estado vive aquí y no en el motor.** `STATUS_VOCAB`,
`LIFECYCLE_REGISTRY`, `STATUS_SYNONYMS`, `STATUS_TRANSITIONS` y
`DOMAIN_STATUS_VOCABS` son lo mismo que el catálogo: la declaración de qué es
legítimo. Las cuatro funciones que los acompañan —`normalize_status`,
`split_domain_status`, `status_frontmatter_lines`, `_canonical_status`— son
puras y no hacen otra cosa que consultarlos; separarlas de sus datos habría
creado un cruce donde no hay ninguno.
"""

from __future__ import annotations


import re
from typing import Any, Dict, List

# ─── Catálogo canónico (fuente de verdad) ──────────────────────────────────────
#
# type:        antipattern | pattern
# category:    content-quality | structure | frontmatter | linking | process
# severity:    critical | high | medium | low  (N/A para patterns)
# enforcement: guard | audit | guard+audit | manual | recommended
#   - guard:     vault_write rechaza en tiempo de escritura
#   - audit:     vault_audit detecta retrospectivamente
#   - guard+audit: ambos
#   - manual:    DEPRECADO (v38) — toda norma debe tener guard o audit; las no
#                automatizables usan audit heurístico (vault_drift_detect)
#   - recommended: patrón positivo a seguir

NORM_CATALOG: List[Dict[str, Any]] = [
    # ── Anti-patrones ──────────────────────────────────────────────────────────
    {
        "code": "AP-01",
        "distinguido_de": {
            "AP-04": (
                "Las dos documentan algo que el código no hace. AP-01 es la "
                "afirmación inventada: no hay implementación ni intención de tenerla, "
                "y el discriminador es que no existe rastro en el repo. AP-04 es el "
                "roadmap escrito en presente: la feature está planeada y la nota la "
                "presenta como ya entregada. Una se corrige borrando la afirmación; "
                "la otra, marcando el estado."
            ),
        },
        "name": "Documentación alucinada",
        "type": "antipattern",
        "category": "content-quality",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Documentar herramientas, endpoints, funciones o comportamientos que no existen "
            "en el código real. El agente genera información convincente pero incorrecta."
        ),
        "signal": "Referencias a scripts/tools que no existen en el repo; funciones con firmas que no coinciden con el código.",
        "prevention": "Verificar existencia real antes de documentar. vault_read + grep sobre el código fuente.",
        "tools_enforcing": [],
        "tools_detecting": [],
        "cobertura_descubierta": (
            "Ninguna tool la detecta. Declaraba `vault_drift_detect`, que mide lo "
            "contrario: cambios en el código que la documentación no recoge. AP-01 es "
            "documentación que describe código inexistente, y para verla haría falta "
            "resolver cada referencia contra el repo."
        ),
        "introduced_version": "v19",
    },
    {
        "code": "AP-02",
        "distinguido_de": {
            "AP-17": (
                "AP-02 son varias versiones del mismo documento conviviendo, cada una "
                "con su nombre. AP-17 es la duplicación canónico-sombra: hay un "
                "canónico declarado y una copia que lo sigue mal. El discriminador es "
                "si existe un canónico designado."
            ),
            "PAT-3": (
                "AP-02 es el defecto: la cadena de versiones duplicadas. PAT-3 es el "
                "procedimiento que la resuelve, eligiendo canónico y anotando el "
                "resto sin borrarlo. Saldar AP-02 es aplicar PAT-3."
            ),
        },
        "name": "Proliferación de versiones del mismo documento",
        "type": "antipattern",
        "category": "structure",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Múltiples notas describiendo la misma entidad: status-v1.md, status-v2.md, "
            "status-final.md, status-final2.md. Variantes: same-folder (AP-02), "
            "cross-folder (AP-18), canonical-shadow (AP-17)."
        ),
        "signal": "vault_audit reporta canonicalShadow o crossFolderDuplicates.",
        "prevention": "Una nota por entidad. Usar .history/ para versiones anteriores (vault_write lo gestiona automáticamente).",
        "tools_enforcing": [],
        "tools_detecting": [],
        "cobertura_descubierta": (
            "Sus dos variantes hermanas sí se miden —AP-17 canonical-shadow y "
            "AP-18 cross-folder, ambas con penalización propia en "
            "vault_audit.PENALIZACIONES—, pero la variante same-folder que es "
            "AP-02 no la detecta nadie: `status-v1.md` y `status-v2.md` en la "
            "misma carpeta no son duplicados por hash (AP-18) ni pasan el "
            "umbral de similitud de título (AP-17). Declararlo aquí es lo que "
            "impide que la cobertura de las hermanas se lea como suya."
        ),
        "introduced_version": "v19",
    },
    {
        "code": "AP-03",
        "distinguido_de": {
            "PAT-2": (
                "Miran el mismo stub desde los dos lados. AP-03 es el anti-patrón: el "
                "stub existe sin política que diga cuándo deja de serlo. PAT-2 es el "
                "patrón que la aporta: gradiente de enriquecimiento con umbrales. "
                "Saldar AP-03 es aplicar PAT-2; no son dos hallazgos sobre la misma "
                "nota."
            ),
        },
        "name": "Stubs sin política de expansión",
        "type": "antipattern",
        "category": "content-quality",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Nota con contenido real pero incompleto (≥3 líneas reales) sin fecha de expansión. "
            "Distinción con AP-11: AP-03 tiene información útil, AP-11 no tiene ningún contenido real."
        ),
        "signal": "vault_audit reporta notas con status:stub sin campo expand_by o con expand_by vencido.",
        "prevention": "Agregar meta: {status: stub, expand_by: YYYY-MM-DD} al crear stubs. Enriquecer en cada sesión.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_audit"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-04",
        "distinguido_de": {
            "AP-01": (
                "Las dos documentan algo que el código no hace. AP-01 es la "
                "afirmación inventada: no hay implementación ni intención de tenerla, "
                "y el discriminador es que no existe rastro en el repo. AP-04 es el "
                "roadmap escrito en presente: la feature está planeada y la nota la "
                "presenta como ya entregada. Una se corrige borrando la afirmación; "
                "la otra, marcando el estado."
            ),
            "AP-08": (
                "Las dos son documentación desalineada del código, en sentidos "
                "opuestos. AP-04 va por delante —describe lo que aún no existe—; "
                "AP-08 va por detrás —describe una versión que ya pasó—. El "
                "discriminador es la dirección del desfase respecto a la versión "
                "viva."
            ),
            "AP-42": (
                "AP-04 mide la nota: describe como entregado algo que no lo está. "
                "AP-42 mide la tool: está publicada en el catálogo y nunca se "
                "ejecutó. El discriminador es el sujeto medido —texto frente a "
                "artefacto ejecutable—, y por eso una la detecta el audit de "
                "contenido y la otra el smoke."
            ),
        },
        "name": "Features aspiracionales documentadas como implementadas",
        "type": "antipattern",
        "category": "content-quality",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Documentar comportamientos futuros o planeados como si ya existieran. "
            "Confunde al agente sobre el estado real del sistema."
        ),
        "signal": "Notas sin campo status o con status:planned que describen funcionalidad en presente.",
        "prevention": "Usar status: planned/in-progress/implemented. Nunca describir en presente algo que no está deployado.",
        "tools_enforcing": [],
        "tools_detecting": [],
        "cobertura_descubierta": (
            "Ninguna tool la detecta. `vault_drift_detect` compara hashes y git; "
            "distinguir «lo describe en presente» de «ya está deployado» exige leer el "
            "cuerpo de la nota contra el estado real, que hoy no hace nadie."
        ),
        "introduced_version": "v19",
    },
    {
        "code": "AP-05",
        "distinguido_de": {
            "PAT-1": (
                "AP-05 es el defecto: el mismo dato con valores distintos en varias "
                "notas del mismo ámbito. PAT-1 es el patrón que lo cierra: una nota "
                "canónica declara el dato y las demás la enlazan. Se declaran aparte "
                "porque PAT-1 se aplica también donde AP-05 aún no ha ocurrido."
            ),
        },
        "name": "Múltiples fuentes de verdad para el mismo dato",
        "type": "antipattern",
        "category": "structure",
        "severity": "critical",
        "enforcement": "audit",
        "description": (
            "El mismo dato (IP, URL, versión, configuración) aparece en múltiples notas "
            "con valores inconsistentes. Causa decisiones del agente basadas en datos erróneos."
        ),
        "signal": "IPs/URLs/versiones que difieren entre notas del mismo proyecto.",
        "prevention": "PAT-1 (canonical source anchoring): una nota canónica por dato, las demás hacen [[wiki-link]] a ella.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_fuente_unica"],
        "cobertura_parcial": (
            "Detectada desde v40.15 **en su parte decidible**, y el resto se declara "
            "en vez de darse por cubierto. `vault_fuente_unica` compara valores "
            "**tipados** —IP, URL, puerto, semver— escritos como `clave: valor` "
            "dentro de un mismo ámbito. Ahí la identidad del dato no hay que "
            "adivinarla, porque está escrita al lado, y la divergencia es una "
            "desigualdad de cadenas: no hacen falta embeddings. Lo que sigue sin "
            "medir nadie es la divergencia **en prosa** («el servidor está en el "
            ".20»), la de valores sin tipo y la del sinónimo (`ip:` frente a "
            "`direccion_ip:`). Verde no prueba una sola fuente de verdad; prueba "
            "que no hay divergencia de la clase que se puede decidir sin "
            "interpretar. Estuvo descubierta desde v19 porque el problema se "
            "planteó entero, y entero sigue abierto."
        ),
        "introduced_version": "v19",
    },
    {
        "code": "AP-06",
        "distinguido_de": {
            "AP-11": (
                "AP-06 es la plantilla que nadie instanció: el fichero es un template "
                "y su función es serlo. AP-11 es la nota real con frontmatter válido "
                "y cuerpo vacío, que se presenta como contenido. El discriminador es "
                "si el fichero se declara plantilla."
            ),
        },
        "name": "Templates sin instancias reales",
        "type": "antipattern",
        "category": "content-quality",
        "severity": "low",
        "enforcement": "audit",
        "description": (
            "Archivos de template (SLOs, métricas, alertas, ADRs) que existen en el vault "
            "pero nunca se han instanciado con datos reales."
        ),
        "signal": "Notas con status:template que no tienen notas derivadas con wiki-link hacia ellas.",
        "prevention": "Si un template no tiene instancias en 30 días, moverlo a 10_Migrated/ o eliminarlo.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_norms"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-07",
        "distinguido_de": {
            "AP-10": (
                "Las dos son documentos de proceso incompletos. AP-07 es el ADR al "
                "que le faltan secciones obligatorias —contexto, decisión, "
                "consecuencias—. AP-10 es la migración sin plan de rollback: el "
                "documento puede estar completo en todo lo demás. El discriminador es "
                "que AP-10 nombra una sección concreta cuya ausencia es "
                "operativamente peligrosa."
            ),
        },
        "name": "ADRs incompletos",
        "type": "antipattern",
        "category": "process",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "ADRs (Architecture Decision Records) sin secciones Contexto, Opciones evaluadas "
            "y Consecuencias. Un ADR sin estas secciones no aporta valor de auditoría."
        ),
        "signal": "Notas en 03_Decisions/ sin secciones ## Contexto, ## Opciones, ## Consecuencias.",
        "prevention": "Usar vault_write con template de ADR completo. vault_audit puede extenderse para validar secciones.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_norms"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-08",
        "distinguido_de": {
            "AP-04": (
                "Las dos son documentación desalineada del código, en sentidos "
                "opuestos. AP-04 va por delante —describe lo que aún no existe—; "
                "AP-08 va por detrás —describe una versión que ya pasó—. El "
                "discriminador es la dirección del desfase respecto a la versión "
                "viva."
            ),
        },
        "name": "Documentación anclada a versiones obsoletas",
        "type": "antipattern",
        "category": "content-quality",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Notas que mencionan versiones específicas de librerías, APIs o protocolos que ya "
            "fueron actualizadas, sin indicar que el contenido puede estar desactualizado."
        ),
        "signal": "Notas con versiones hardcodeadas (v1.2.3) y updatedAt > 90 días.",
        "prevention": "Agregar campo version_pinned al frontmatter con la versión referenciada. vault_audit puede alertar.",
        "tools_enforcing": [],
        "tools_detecting": [],
        "cobertura_descubierta": (
            "Ninguna tool la detecta. Declaraba `vault_drift_detect`, que no lee "
            "versiones del cuerpo de la nota. La propia `prevention` lo dice en "
            "condicional —«vault_audit puede alertar»— y ese condicional lleva desde "
            "v19 sin resolverse."
        ),
        "introduced_version": "v19",
    },
    {
        "code": "AP-09",
        "distinguido_de": {
            "CN-02": (
                "CN-02 es la convención general de destino: las secciones numeradas "
                "son los únicos sitios válidos. AP-09 es su incumplimiento con nombre "
                "para un tipo concreto: los runbooks fuera de la estructura. Se "
                "separa porque el runbook tiene además exigencias de contenido que "
                "CN-02 no mira."
            ),
        },
        "name": "Runbooks fuera de estructura",
        "type": "antipattern",
        "category": "process",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Procedimientos operativos guardados en carpetas genéricas (07_Knowledge/, 01_Projects/) "
            "en lugar de 06_Runbooks/. Dificulta la localización en incidentes."
        ),
        "signal": "Notas con title que contiene 'runbook', 'procedure', 'how-to' fuera de 06_Runbooks/.",
        "prevention": "Todo runbook va en 06_Runbooks/{proyecto}/. vault_migrate_docs para moverlos.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_norms"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-10",
        "distinguido_de": {
            "AP-07": (
                "Las dos son documentos de proceso incompletos. AP-07 es el ADR al "
                "que le faltan secciones obligatorias —contexto, decisión, "
                "consecuencias—. AP-10 es la migración sin plan de rollback: el "
                "documento puede estar completo en todo lo demás. El discriminador es "
                "que AP-10 nombra una sección concreta cuya ausencia es "
                "operativamente peligrosa."
            ),
        },
        "name": "Migración sin plan de rollback",
        "type": "antipattern",
        "category": "process",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Ejecutar vault_migrate_docs sin tener vault_migrate_rollback disponible "
            "o sin snapshot previo. Si la migración introduce errores, no hay manera de revertir."
        ),
        "signal": "vault_migrate_docs ejecutado sin llamar vault_drift_detect --snapshot primero.",
        "prevention": "PAT-4 (phased audit): siempre snapshot → migrate → verify → rollback si falla.",
        "tools_enforcing": [],
        # `vault_migrate_rollback` **es** el rollback: tenerlo no detecta que una
        # migración se hizo sin él. Quien lo mide es `vault_norms --audit`, que
        # marca notas en `10_Migrated/` sin su `_report-*.md`.
        "tools_detecting": ["vault_norms"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-11",
        "distinguido_de": {
            "AP-06": (
                "AP-06 es la plantilla que nadie instanció: el fichero es un template "
                "y su función es serlo. AP-11 es la nota real con frontmatter válido "
                "y cuerpo vacío, que se presenta como contenido. El discriminador es "
                "si el fichero se declara plantilla."
            ),
            "AP-20": (
                "AP-11 es el cuerpo vacío: no hay nada que leer y se nota. AP-20 es "
                "el esqueleto engañoso: hay estructura y campos, y las listas están "
                "vacías, así que la nota pasa por completa ante cualquier medida que "
                "cuente secciones. El discriminador es si el vacío es visible o está "
                "disfrazado."
            ),
            "AP-23": (
                "Son los dos extremos del mismo eje. AP-11 es defecto de contenido "
                "—la nota no dice nada—; AP-23 es exceso —la nota supera el techo de "
                "complejidad y debería partirse—. Ninguna nota puede incurrir en las "
                "dos."
            ),
        },
        "name": "Skeleton files — frontmatter válido, contenido vacío",
        "type": "antipattern",
        "category": "content-quality",
        "severity": "critical",
        "enforcement": "guard",
        "description": (
            "Nota creada con frontmatter correcto pero cuerpo vacío o solo con TODO/placeholders. "
            "El agente indexa la nota pero no recibe información útil de ella. "
            "Distinción con AP-03: AP-11 = 0 líneas reales; AP-03 = ≥3 líneas reales pero incompleto."
        ),
        "signal": "vault_write rechaza con error_code: content_too_short.",
        "prevention": "vault_write exige ≥3 líneas de contenido real (00_System exempt). No crear notas que no estén listas.",
        "tools_enforcing": ["vault_write"],
        "tools_detecting": ["vault_audit"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-12",
        "distinguido_de": {
            "AP-46": (
                "AP-12 es el síntoma medido en las notas: dos notas del mismo tipo "
                "con frontmatter distinto. AP-46 es la causa medida en el código: no "
                "hay escritor único de frontmatter. Se separan porque el vault puede "
                "quedar coherente a mano con la causa intacta."
            ),
        },
        "name": "Frontmatter inconsistente entre notas del mismo tipo",
        "type": "antipattern",
        "category": "frontmatter",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Notas del mismo tipo con campos faltantes, tipos mezclados "
            "(timestamp con/sin comillas, migratedFrom relativo vs absoluto). "
            "Rompe vault_list, búsquedas y deduplicación."
        ),
        "signal": "vault_validate reporta campos faltantes. vault_audit detecta inconsistencias de tipo.",
        "prevention": "vault_write como único punto de creación; nunca editar frontmatter manualmente.",
        "tools_enforcing": ["vault_write"],
        # `vault_audit` no mide AP-12: mide los campos uno a uno (AP-16, AP-26,
        # AP-27, AP-29, AP-30), cada uno con su penalización. Quien comprueba el
        # bloque completo es `vault_validate.validate_frontmatter`.
        "tools_detecting": ["vault_validate"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-13",
        "distinguido_de": {
            "AP-53": (
                "AP-13 mide el timestamp del frontmatter contra su propio formato: "
                "inválido o incompleto. AP-53 mide la afirmación histórica contra "
                "git: la fecha es valida y no coincide con el commit. El "
                "discriminador es si hay una fuente externa contra la que contrastar."
            ),
        },
        "name": "Timestamps inválidos o incompletos en frontmatter",
        "type": "antipattern",
        "category": "frontmatter",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Timestamps solo con fecha (2026-05-07), con '...' literal, sin zona horaria "
            "o en formato no ISO 8601. vault_diff y vault_timeline no pueden ordenar versiones."
        ),
        "signal": "vault_audit detecta createdAt/updatedAt que no coinciden con patrón ISO 8601.",
        "prevention": "vault_write genera timestamps con datetime.now(timezone.utc).isoformat() automáticamente.",
        "tools_enforcing": ["vault_write"],
        "tools_detecting": ["vault_audit"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-14",
        "distinguido_de": {
            "AP-21": (
                "Las dos son wikilinks defectuosos. AP-14 es el link que no resuelve "
                "a ningún destino. AP-21 resuelve, pero está anclado a una ruta "
                "concreta, así que se rompe en cuanto la nota se mueve. El "
                "discriminador es si hoy resuelve: AP-14 ya está roto, AP-21 lo "
                "estará."
            ),
            "AP-25": (
                "Las dos son referencias que no resuelven. AP-14 vive en el grafo de "
                "Obsidian —wikilinks entre notas—; AP-25 vive dentro de un diagrama "
                "mermaid, donde el nodo citado no está definido. El discriminador es "
                "el espacio de nombres en el que se busca el destino."
            ),
            "AP-34": (
                "AP-14 es el wikilink sin destino; AP-34 es la relación tipada cuyo "
                "endpoint no existe. La misma ausencia en dos capas: la sintáctica "
                "del enlace y la semántica del grafo de predicados. Una nota puede "
                "tener AP-34 con todos sus wikilinks intactos."
            ),
            "SP-02": (
                "AP-14 es el defecto ya escrito: el link roto está en el vault. SP-02 "
                "es el protocolo que lo evita —buscar el destino antes de escribir el "
                "enlace—. Una se detecta auditando; la otra se cumple o no en el "
                "momento de escribir, y su incumplimiento solo se ve como AP-14 más "
                "tarde."
            ),
        },
        "name": "Wiki-links rotos o vacíos",
        "type": "antipattern",
        "category": "linking",
        "severity": "critical",
        "enforcement": "guard+audit",
        "description": (
            "[[]] vacíos, [[ ]] con espacio, links a notas renombradas/eliminadas, "
            "o links con path (AP-21). Dos causas raíz: (a) wrong stem, (b) path-anchored. "
            "El agente sigue links que no resuelven."
        ),
        "signal": "vault_audit reporta brokenLinks[]. vault_write rechaza [[]] y [[folder/nota]].",
        "prevention": "Solo escribir [[wiki-link]] cuando la nota destino ya existe. vault_search() antes de linkar.",
        "tools_enforcing": ["vault_write"],
        "tools_detecting": ["vault_audit", "vault_graph"],
        "introduced_version": "v19",
    },
    {
        "code": "AP-15",
        "distinguido_de": {
            "AP-36": (
                "AP-15 es material ajeno depositado dentro del vault. AP-36 es lo "
                "contrario: side-effects de las tools que salen del vault o no quedan "
                "rastreados. El discriminador es la dirección del cruce de la "
                "frontera."
            ),
            "CN-02": (
                "CN-02 es la nota colocada en una carpeta que no toca, dentro del "
                "esquema. AP-15 es el fichero externo depositado en la raíz del "
                "vault, que ni siquiera es una nota. El discriminador es si el "
                "fichero forma parte del material del vault."
            ),
        },
        "name": "Archivos externos depositados en la raíz del vault",
        "type": "antipattern",
        "category": "structure",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Archivos .md colocados directamente en vault-{nombre}/ en lugar de en secciones "
            "numeradas. vault_graph parsea sus [[wiki-links]] como broken links reales del proyecto."
        ),
        "signal": "vault_graph reporta decenas de orphans y broken links falsos.",
        "prevention": "Layout correcto: vault/ y scripts/ son hermanos, nunca anidados. Solo 00_System…11_Code y 99_Index son destinos válidos.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_norms"],
        "introduced_version": "v20",
    },
    {
        "code": "AP-16",
        "distinguido_de": {
            "PAT-5": (
                "AP-16 es la falta del identificador de agente en una nota concreta. "
                "PAT-5 es el patrón que hace útil ese campo: el frontmatter como "
                "cadena de procedencia a lo largo de las ediciones. Un vault puede "
                "tener el campo en todas las notas y no encadenar nada."
            ),
        },
        "name": "Sin identificador de agente en frontmatter",
        "type": "antipattern",
        "category": "frontmatter",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Nota sin campo agent: en el frontmatter. Sin este campo es imposible auditar "
            "qué agente creó o modificó la nota (PAT-5: frontmatter as provenance chain)."
        ),
        "signal": "vault_audit reporta notas sin campo agent.",
        "prevention": "vault_write agrega agent: automáticamente. Valores estándar: claude, system, human.",
        "tools_enforcing": ["vault_write"],
        "tools_detecting": ["vault_audit"],
        "introduced_version": "v20",
    },
    {
        "code": "AP-17",
        "distinguido_de": {
            "AP-02": (
                "AP-02 son varias versiones del mismo documento conviviendo, cada una "
                "con su nombre. AP-17 es la duplicación canónico-sombra: hay un "
                "canónico declarado y una copia que lo sigue mal. El discriminador es "
                "si existe un canónico designado."
            ),
            "AP-18": (
                "AP-17 tiene canónico y sombra: una de las dos manda. AP-18 es "
                "duplicación entre carpetas sin jerarquía declarada —dos copias de "
                "igual rango—, y por eso su reparación empieza por decidir cual es la "
                "canónica, que AP-17 ya tiene decidido."
            ),
        },
        "name": "Canonical-shadow duplication",
        "type": "antipattern",
        "category": "structure",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Par de notas con SequenceMatcher ratio ≥ 0.85 en títulos. "
            "Típicamente una nota thin creada cuando ya existía la canónica rica. "
            "Penalización vault_audit: −2 por par."
        ),
        "signal": "vault_audit reporta canonicalShadow[] con similarity ≥ 0.85.",
        "prevention": "PAT-3: buscar con vault_search() antes de crear. Si existe una nota similar, enriquecer en lugar de crear.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_audit"],
        "introduced_version": "v25",
    },
    {
        "code": "AP-18",
        "distinguido_de": {
            "AP-17": (
                "AP-17 tiene canónico y sombra: una de las dos manda. AP-18 es "
                "duplicación entre carpetas sin jerarquía declarada —dos copias de "
                "igual rango—, y por eso su reparación empieza por decidir cual es la "
                "canónica, que AP-17 ya tiene decidido."
            ),
            "AP-19": (
                "AP-18 duplica contenido en dos carpetas. AP-19 duplica el índice: "
                "hay un índice en la sombra que compite con el canónico. El "
                "discriminador es si lo duplicado es material o navegación."
            ),
        },
        "name": "Cross-folder content duplication",
        "type": "antipattern",
        "category": "structure",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Mismo contenido byte-idéntico (MD5) en carpetas distintas. "
            "Penalización vault_audit: −3 por par."
        ),
        "signal": "vault_audit reporta crossFolderDuplicates[].",
        "prevention": "PAT-1: una nota canónica, las demás hacen [[wiki-link]]. Usar vault_change_log --action deleted antes de borrar.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_audit"],
        "introduced_version": "v25",
    },
    {
        "code": "AP-19",
        "distinguido_de": {
            "AP-18": (
                "AP-18 duplica contenido en dos carpetas. AP-19 duplica el índice: "
                "hay un índice en la sombra que compite con el canónico. El "
                "discriminador es si lo duplicado es material o navegación."
            ),
        },
        "name": "Shadow indexing",
        "type": "antipattern",
        "category": "structure",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Índices de sección creados manualmente, duplicando lo que vault_section_index genera "
            "automáticamente. Los índices manuales rotan en AP-02 con el tiempo."
        ),
        "signal": "Múltiples index.md o README.md en una sección que no fueron generados por vault_section_index.",
        "prevention": "vault_section_index es la única herramienta para índices. No editar index.md manualmente.",
        "tools_enforcing": [],
        "tools_detecting": ["vault_norms"],
        "introduced_version": "v25",
    },
    {
        "code": "AP-20",
        "distinguido_de": {
            "AP-11": (
                "AP-11 es el cuerpo vacío: no hay nada que leer y se nota. AP-20 es "
                "el esqueleto engañoso: hay estructura y campos, y las listas están "
                "vacías, así que la nota pasa por completa ante cualquier medida que "
                "cuente secciones. El discriminador es si el vacío es visible o está "
                "disfrazado."
            ),
            "AP-45": (
                "AP-45 es la nota que existe para que la sección no aparezca vacía: "
                "la cobertura se afirma sin evidencia detrás. AP-20 es la nota que "
                "tiene estructura y listas vacías. AP-45 se mide contra lo que la "
                "nota dice cubrir; AP-20, contra su propio contenido."
            ),
        },
        "name": "Deceptive skeleton (empty-list)",
        "type": "antipattern",
        "category": "content-quality",
        "severity": "critical",
        "enforcement": "guard",
        "description": (
            "Nota que pasa el content gate de 3 líneas porque tiene bullets, "
            "pero >50% de los bullets están vacíos (- , - [ ], - []). "
            "Variante de AP-11 que evade el guard básico."
        ),
        "signal": "vault_write rechaza con error_code: content_empty_list.",
        "prevention": "vault_write rechaza si empty_bullets/total_bullets > 0.5. Completar los bullets antes de guardar.",
        "tools_enforcing": ["vault_write"],
        "tools_detecting": [],
        "introduced_version": "v25",
    },
    {
        "code": "AP-21",
        "distinguido_de": {
            "AP-14": (
                "Las dos son wikilinks defectuosos. AP-14 es el link que no resuelve "
                "a ningún destino. AP-21 resuelve, pero está anclado a una ruta "
                "concreta, así que se rompe en cuanto la nota se mueve. El "
                "discriminador es si hoy resuelve: AP-14 ya está roto, AP-21 lo "
                "estará."
            ),
        },
        "name": "Path-anchored wiki-links",
        "type": "antipattern",
        "category": "linking",
        "severity": "critical",
        "enforcement": "guard",
        "description": (
            "[[carpeta/nota]] en lugar de [[nota]]. Obsidian no resuelve paths, "
            "solo stems. El link siempre aparece roto en el grafo."
        ),
        "signal": "vault_write rechaza con error_code: path_anchored_wikilinks.",
        "prevention": "Siempre [[stem]] o [[stem|título visible]]. vault_section_index genera solo [[stem|título]] desde v25.",
        "tools_enforcing": ["vault_write"],
        "tools_detecting": [],
        "introduced_version": "v25",
    },
    {
        "code": "AP-22",
        "name": "Wiki-link vacío — [[]] sin destino",
        "type": "antipattern",
        "category": "linking",
        # Era `critical`, y contradecía al código que la aplica. `vault_audit`
        # pesa AP-22 con 2/unidad (tope 5) y AP-24 con 5/unidad (tope 15), y
        # escribe al lado por qué: «AP-22 es auto-fixable; AP-24 rompe el enlace
        # de verdad». Dos registros canónicos afirmando lo contrario sobre cuál
        # es peor. Manda el que se ejecuta (regla 3): un `[[]]` vacío no pierde
        # información y se elimina solo. Corregido en v40.10 junto con el guard
        # que compara los dos órdenes (`vault_norms_coherence`, AP-55).
        "severity": "medium",
        "enforcement": "guard+audit",
        "description": (
            "Wiki-link vacío: `[[]]` sin destino, fuera de bloques de código. No hay "
            "información que perder, así que la reparación es eliminarlo. "
            "vault_write bloquea (hard stop). "
            "vault_write también advierte (non-blocking) si [[target]] no existe: ghost_links[]."
        ),
        "signal": "vault_write rechaza con error_code: malformed_wikilinks. vault_audit reporta malformedWikilinks[] con norm_code AP-22.",
        "prevention": "Nunca escribir [[]] vacíos. Verificar que el target exista antes de linkar.",
        "tools_enforcing": ["vault_write"],
        "tools_detecting": ["vault_audit", "vault_fix_brackets"],
        # El desbalance de corchetes **no** es esta norma, es AP-24. La
        # `description` de AP-22 lo reclamaba —«corchetes [[ sin ]] matching»—
        # desde v34.2, cuando nació AP-24, y durante seis versiones las dos
        # normas dijeron cubrir el mismo defecto mientras el código ya las
        # separaba sin ambigüedad. El discriminador es observable, no una
        # cuestión de criterio, y por eso se declara aquí en vez de explicarse.
        "distinguido_de": {
            "AP-24": (
                "AP-22 es el link vacío `[[]]`: no hay destino que recuperar y la "
                "reparación no pierde nada. AP-24 es el desbalance —apertura sin "
                "cierre, cierre sin apertura, anidamiento—: hay un destino escrito "
                "que el desbalance vuelve inalcanzable. `vault_audit` los separa por "
                "`norm_code` y, cuando una nota tiene ambos, publica AP-24 como "
                "primario."
            )
        },
        "introduced_version": "v29",
    },
    # ── Patrones recomendados ──────────────────────────────────────────────────
    {
        "code": "PAT-1",
        "distinguido_de": {
            "AP-05": (
                "AP-05 es el defecto: el mismo dato con valores distintos en varias "
                "notas del mismo ámbito. PAT-1 es el patrón que lo cierra: una nota "
                "canónica declara el dato y las demás la enlazan. Se declaran aparte "
                "porque PAT-1 se aplica también donde AP-05 aún no ha ocurrido."
            ),
        },
        "name": "Canonical source anchoring",
        "type": "pattern",
        "category": "structure",
        "severity": "N/A",
        "enforcement": "recommended",
        "description": (
            "Un dominio = una nota canónica rica. Todas las referencias desde otros contextos "
            "son [[wiki-links]] a esa nota canónica, nunca copias del contenido."
        ),
        "signal": "vault_audit muestra 0 canonicalShadow y 0 crossFolderDuplicates.",
        "prevention": "N/A — es el patrón correcto. Aplicar siempre al crear documentación.",
        "tools_enforcing": [],
        "tools_detecting": [],
        "tools_del_patron": ["vault_audit"],
        "introduced_version": "v25",
    },
    {
        "code": "PAT-2",
        "distinguido_de": {
            "AP-03": (
                "Miran el mismo stub desde los dos lados. AP-03 es el anti-patrón: el "
                "stub existe sin política que diga cuándo deja de serlo. PAT-2 es el "
                "patrón que la aporta: gradiente de enriquecimiento con umbrales. "
                "Saldar AP-03 es aplicar PAT-2; no son dos hallazgos sobre la misma "
                "nota."
            ),
        },
        "name": "Stub enrichment gradient",
        "type": "pattern",
        "category": "content-quality",
        "severity": "N/A",
        "enforcement": "recommended",
        "description": (
            "Un stub con ≥3 líneas reales se enriquece progresivamente en cada sesión que lo toca. "
            "La eliminación solo aplica a skeletons (AP-11) y deceptive skeletons (AP-20)."
        ),
        "signal": "Stubs del vault tienen status:stub y fecha expand_by.",
        "prevention": "N/A — es el patrón correcto.",
        "tools_enforcing": [],
        "tools_detecting": [],
        "tools_del_patron": ["vault_audit"],
        "introduced_version": "v25",
    },
    {
        "code": "PAT-3",
        "distinguido_de": {
            "AP-02": (
                "AP-02 es el defecto: la cadena de versiones duplicadas. PAT-3 es el "
                "procedimiento que la resuelve, eligiendo canónico y anotando el "
                "resto sin borrarlo. Saldar AP-02 es aplicar PAT-3."
            ),
        },
        "name": "Duplicate chain resolution",
        "type": "pattern",
        "category": "structure",
        "severity": "N/A",
        "enforcement": "recommended",
        "description": (
            "Algoritmo estándar para resolver duplicados: identificar canónica (más backlinks, "
            "más contenido, ubicación más apropiada) → change_log --action deleted → "
            "mover a 10_Migrated/ → actualizar wiki-links rotos → verificar con vault_audit."
        ),
        "signal": "vault_audit canonicalShadow reducido después de aplicar.",
        "prevention": "N/A — es el algoritmo de resolución.",
        "tools_enforcing": [],
        "tools_detecting": [],
        "tools_del_patron": ["vault_audit", "vault_change_log", "vault_write"],
        "introduced_version": "v25",
    },
    {
        "code": "PAT-4",
        "distinguido_de": {
            "SP-03": (
                "PAT-4 ordena la auditoría en fases para que un fallo no invalide "
                "todo el recorrido. SP-03 exige el snapshot delta antes de una "
                "operación masiva, para poder decir después que cambio. Uno "
                "estructura el trabajo; el otro conserva la evidencia de lo que hizo."
            ),
        },
        "name": "Phased audit execution",
        "type": "pattern",
        "category": "process",
        "severity": "N/A",
        "enforcement": "recommended",
        "description": (
            "Las auditorías masivas se ejecutan en 4 fases atómicas: "
            "1-Snapshot (vault_drift_detect --snapshot), 2-Detección (vault_audit), "
            "3-Resolución (vault_write, vault_change_log), 4-Verificación (vault_drift_detect --report)."
        ),
        "signal": "0 regresiones entre snapshot y estado final.",
        "prevention": "N/A — es el protocolo de auditoría.",
        "tools_enforcing": [],
        "tools_detecting": [],
        "tools_del_patron": ["vault_drift_detect", "vault_audit", "vault_write", "vault_change_log"],
        "introduced_version": "v25",
    },
    {
        "code": "PAT-5",
        "distinguido_de": {
            "AP-16": (
                "AP-16 es la falta del identificador de agente en una nota concreta. "
                "PAT-5 es el patrón que hace útil ese campo: el frontmatter como "
                "cadena de procedencia a lo largo de las ediciones. Un vault puede "
                "tener el campo en todas las notas y no encadenar nada."
            ),
        },
        "name": "Frontmatter as provenance chain",
        "type": "pattern",
        "category": "frontmatter",
        "severity": "N/A",
        "enforcement": "recommended",
        "description": (
            "Los campos id + createdAt + updatedAt + agent + migratedFrom (si aplica) "
            "forman una cadena de custodia completa. Sin esta cadena es imposible auditar "
            "de dónde vino un dato o qué agente lo introdujo."
        ),
        "signal": "vault_audit reporta 0 notas sin campo agent.",
        "prevention": "N/A — vault_write genera estos campos automáticamente.",
        "tools_enforcing": [],
        "tools_detecting": [],
        "tools_del_patron": ["vault_write", "vault_audit"],
        "introduced_version": "v25",
    },
    # ── Anti-patrón AP-23 ──────────────────────────────────────────────────────
    {
        "code": "AP-23",
        "distinguido_de": {
            "AP-11": (
                "Son los dos extremos del mismo eje. AP-11 es defecto de contenido "
                "—la nota no dice nada—; AP-23 es exceso —la nota supera el techo de "
                "complejidad y debería partirse—. Ninguna nota puede incurrir en las "
                "dos."
            ),
        },
        "name": "Note complexity ceiling — nota demasiado larga",
        "type": "antipattern",
        "category": "content-quality",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Una nota con más de 500 líneas de contenido real se vuelve difícil de mantener "
            "y consume excesivo contexto del LLM. Debe dividirse en sub-notas canónicas "
            "interconectadas con [[wiki-links]] desde la nota original."
        ),
        "signal": "vault_write advierte en la respuesta con ap23_warning cuando content > 500 líneas. "
        "vault_norms --scan reporta AP-23 en notas largas.",
        "prevention": (
            "Al superar 500 líneas, crear sub-notas en la misma carpeta y reemplazar la sección "
            "con [[sub-nota|título]]. La nota original actúa como índice/resumen."
        ),
        "tools_enforcing": [],
        "tools_detecting": ["vault_write", "vault_norms"],
        "introduced_version": "v30",
    },
    # ── Anti-patrón AP-24 ──────────────────────────────────────────────────────
    {
        "code": "AP-24",
        "name": "Bracket imbalance — corchetes sin pareja, anidados o invertidos",
        "type": "antipattern",
        "category": "linking",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "Wiki-links malformados por desbalance de corchetes. Tres variantes: "
            "(1) apertura sin cierre ([[nota sin ]]), (2) cierre sin apertura (]] sin [[), "
            "(3) anidamiento incorrecto ([[[[nota]]]] o [[nota]]]]). En Obsidian el link "
            "se renderiza como texto literal, no como enlace navegable. Rompe la trazabilidad "
            "y produce falsos negativos en vault_audit --broken-links."
        ),
        "signal": (
            "vault_write content_gate detecta balance desigual en línea y rechaza la escritura. "
            "vault_audit penaliza con -5 por nota afectada. vault_fix_brackets intenta auto-fix "
            "(eliminación de corchetes extra o inyección de cierre)."
        ),
        "prevention": (
            "Usar siempre el formato [[stem]] o [[stem|alias]]. Validar balance con "
            "vault_fix_brackets --fix antes de commit. El content_gate de vault_write "
            "rechaza contenido con bracket imbalance."
        ),
        "tools_enforcing": ["vault_write", "vault_fix_brackets"],
        "tools_detecting": ["vault_audit", "vault_fix_brackets"],
        "distinguido_de": {
            "AP-22": (
                "AP-24 es el desbalance de corchetes: hay un destino escrito y el "
                "desbalance lo vuelve inalcanzable. AP-22 es el link vacío `[[]]`, "
                "sin destino que recuperar. AP-24 pesa más en el healthIndex (5/unidad "
                "frente a 2) precisamente por esa diferencia."
            )
        },
        "introduced_version": "v34.2",
    },
    # ── Anti-patrón AP-25 ──────────────────────────────────────────────────────
    {
        "code": "AP-25",
        "distinguido_de": {
            "AP-14": (
                "Las dos son referencias que no resuelven. AP-14 vive en el grafo de "
                "Obsidian —wikilinks entre notas—; AP-25 vive dentro de un diagrama "
                "mermaid, donde el nodo citado no está definido. El discriminador es "
                "el espacio de nombres en el que se busca el destino."
            ),
        },
        "name": "Mermaid diagram syntax errors — nodos/tipos no definidos",
        "type": "antipattern",
        "category": "content-quality",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Diagramas Mermaid con sintaxis inválida: tipos de diagrama no reconocidos "
            "(unknown_type), nodos referenciados pero no definidos (undefined_node), "
            "flechas huérfanas, o sintaxis de etiquetas incorrecta. El diagrama no se "
            "renderiza en Obsidian y pierde su valor documental."
        ),
        "signal": (
            "vault_audit detecta errores con vault_mermaid_check.scan_vault() y los reporta "
            "como AP-25 con penalización -2 por error. La nota se marca como mermaidError "
            "en el output del audit."
        ),
        "prevention": (
            "Validar con vault_mermaid_check antes de commit. Usar tipos conocidos "
            "(graph TD, flowchart LR, sequenceDiagram, classDiagram, etc.). "
            "Asegurar que cada nodo referenciado en una flecha exista como definición previa."
        ),
        "tools_enforcing": [],
        "tools_detecting": ["vault_audit", "vault_mermaid_check"],
        "introduced_version": "v34.2",
    },
    # ── Anti-patrones AP-26..AP-30 ────────────────────────────────────────────
    # Frontmatter incompleto. Estaban aplicados por vault_audit desde v30 (con
    # penalización al health score y etiqueta propia en su salida) pero nunca
    # se registraron aquí: `vault_norms --list` no los mostraba y no tenían
    # severidad, enforcement ni prevención declaradas. El hueco lo detectó el
    # chequeo de contiguidad de vault_sdd_init al dejar de estar clavado en
    # AP-01..AP-25. Registrados sin cambiar el comportamiento del audit.
    {
        "code": "AP-26",
        "distinguido_de": {
            "AP-27": (
                "Las dos son campos ausentes del frontmatter. AP-26 es `tags`, que "
                "clasifica de forma abierta y multiple; AP-27 es `type`, que asigna "
                "un único tipo y decide que otras normas aplican. Por eso AP-27 "
                "bloquea más cosas aguas abajo que AP-26."
            ),
            "AP-30": (
                "Las dos clasifican la nota. AP-26 lo hace por tema, con `tags` "
                "libres; AP-30 lo hace por sensibilidad, con la tríada CIA y valores "
                "tasados. Un tag `confidencial` no salda AP-30."
            ),
        },
        "name": "Missing tags — nota de contenido sin tags",
        "type": "antipattern",
        "category": "metadata-completeness",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Nota de contenido sin campo `tags` o con la lista vacía. Sin tags la nota "
            "es invisible para la búsqueda por facetas y no participa en los edges "
            "shared_tag del grafo: queda alcanzable solo por wiki-link directo."
        ),
        "signal": (
            "vault_audit la cuenta en missing_tags y penaliza -2 por nota (tope -15). "
            "Aparece en el resumen como 'N sin tags AP-26'."
        ),
        "prevention": (
            "Pasar --tags en la tool de escritura. vault_ingest y vault_preferences "
            "los derivan automáticamente del origen y la categoría."
        ),
        "tools_enforcing": ["vault_ingest", "vault_preferences"],
        "tools_detecting": ["vault_audit"],
        "introduced_version": "v30",
    },
    {
        "code": "AP-27",
        "distinguido_de": {
            "AP-26": (
                "Las dos son campos ausentes del frontmatter. AP-26 es `tags`, que "
                "clasifica de forma abierta y multiple; AP-27 es `type`, que asigna "
                "un único tipo y decide que otras normas aplican. Por eso AP-27 "
                "bloquea más cosas aguas abajo que AP-26."
            ),
        },
        "name": "Missing type field — nota sin tipo declarado",
        "type": "antipattern",
        "category": "metadata-completeness",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Nota sin campo `type`. El tipo es lo que ancla la nota a su sección "
            "canónica (CN-02): sin él no se puede verificar la coincidencia "
            "type ↔ carpeta que sostiene la dimensión de exactitud (F4)."
        ),
        "signal": "vault_audit la cuenta en missing_type y penaliza -2 por nota (tope -10).",
        "prevention": "Declarar --type en la escritura; vault_audit lo cuenta en missing_type.",
        "tools_enforcing": [],
        # `vault_validate` no mira `type`: su lista de campos exigidos no lo
        # incluye. Lo cuenta `vault_audit` en `missing_type`, con peso propio.
        "tools_detecting": ["vault_audit"],
        "introduced_version": "v30",
    },
    {
        "code": "AP-28",
        "name": "Missing frontmatter — nota sin bloque YAML",
        "type": "antipattern",
        "category": "metadata-completeness",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Nota sin bloque de frontmatter. Es el caso degenerado de AP-26/27/29/30 "
            "a la vez: sin frontmatter no hay id, ni agent, ni status, ni CIA, así que "
            "la nota queda fuera de toda métrica de calidad y de la cadena de "
            "trazabilidad (PAT-5)."
        ),
        "signal": "vault_audit la cuenta en missing_frontmatter y penaliza -3 por nota (tope -20).",
        "prevention": (
            "No editar .md a mano (SP-04). Escribir siempre por tool: "
            "atomic_write_text garantiza el bloque."
        ),
        "tools_enforcing": [],
        "tools_detecting": ["vault_audit", "vault_validate"],
        "distinguido_de": {
            "AP-56": (
                "AP-28 es ausencia: no hay bloque `---` que leer. AP-56 es presencia "
                "ilegible: el bloque está, el humano lo ve al abrir la nota, y el "
                "consumidor no lo lee porque no parsea. Se confunden porque ambas "
                "acaban en 'esta nota no tiene metadatos', pero la reparación es "
                "opuesta: AP-28 pide escribir el frontmatter, AP-56 pide arreglar el "
                "que ya está — y escribir uno nuevo encima perdería lo escrito."
            )
        },
        "introduced_version": "v30",
    },
    {
        "code": "AP-29",
        "distinguido_de": {
            "AP-30": (
                "Las dos son campos ausentes. AP-29 es `status`, el estado del ciclo "
                "de vida, que cambia con el tiempo. AP-30 es la clasificación CIA, "
                "que describe la sensibilidad del contenido y no cambia por avanzar "
                "el trabajo. El discriminador es si el valor es temporal o "
                "intrínseco."
            ),
            "CN-03": (
                "CN-03 exige que el valor de `status` esté en el vocabulario "
                "canónico; AP-29 exige que el campo exista. El discriminador es "
                "presencia frente a valor: una nota sin `status` es AP-29 y no puede "
                "ser CN-03."
            ),
        },
        "name": "Missing status field — nota sin estado de ciclo de vida",
        "type": "antipattern",
        "category": "metadata-completeness",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Nota sin campo `status`. Sin estado no se puede distinguir lo vigente de "
            "lo obsoleto, y la nota escapa al vocabulario controlado de CN-03: es la "
            "vía por la que contenido derogado sigue leyéndose como vigente."
        ),
        "signal": "vault_audit la cuenta en missing_status y penaliza -1 por nota (tope -10).",
        "prevention": "Declarar --status dentro de STATUS_VOCAB (12 valores).",
        "tools_enforcing": [],
        "tools_detecting": ["vault_audit", "vault_norms"],
        "introduced_version": "v30",
    },
    {
        "code": "AP-30",
        "distinguido_de": {
            "AP-26": (
                "Las dos clasifican la nota. AP-26 lo hace por tema, con `tags` "
                "libres; AP-30 lo hace por sensibilidad, con la tríada CIA y valores "
                "tasados. Un tag `confidencial` no salda AP-30."
            ),
            "AP-29": (
                "Las dos son campos ausentes. AP-29 es `status`, el estado del ciclo "
                "de vida, que cambia con el tiempo. AP-30 es la clasificación CIA, "
                "que describe la sensibilidad del contenido y no cambia por avanzar "
                "el trabajo. El discriminador es si el valor es temporal o "
                "intrínseco."
            ),
        },
        "name": "Missing CIA classification — nota sin clasificación de la tríada",
        "type": "antipattern",
        "category": "metadata-completeness",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Nota sin `cia_integrity` / `cia_availability` / `cia_sensitivity`. Sin "
            "clasificación CIA la nota no puede endurecer su umbral de actualidad "
            "(30d → 15d en critical|high) ni ponderar su peso en el health score: el "
            "pilar del estándar queda sin aplicar sobre ella."
        ),
        "signal": "vault_audit la cuenta en missing_cia y penaliza -2 por nota (tope -15).",
        "prevention": (
            "Declarar los tres ejes en la escritura. vault_ingest asigna "
            "cia_integrity: low a lo ingerido por no estar verificado."
        ),
        "tools_enforcing": ["vault_ingest"],
        # `vault_quality_check` valida los valores CIA **cuando están** (`if
        # "cia_integrity" in fm`); la ausencia, que es lo que AP-30 nombra, no la
        # ve. La cuenta `vault_audit` en `missing_cia`.
        "tools_detecting": ["vault_audit"],
        "introduced_version": "v30",
    },
    # ── Anti-patrón AP-31 ──────────────────────────────────────────────────────
    {
        "code": "AP-31",
        "distinguido_de": {
            "AP-32": (
                "AP-31 es la arista sin `predicate`: la relación existe y no dice de "
                "que tipo es. AP-32 tiene predicate, pero no pertenece a la ontología "
                "declarada. El discriminador es si el campo está presente: ausencia "
                "frente a valor fuera de vocabulario."
            ),
            "AP-35": (
                "AP-31 mira la arista —le falta tipo—; AP-35 mira el conjunto —hay "
                "varios sistemas de relaciones que no se hablan entre si—. Un vault "
                "puede tener todas sus aristas tipadas y aun así estar en silos, y al "
                "revés."
            ),
            "PAT-6": (
                "AP-31 es el defecto: aristas sin predicate. PAT-6 es el patrón que "
                "lo cierra: enriquecimiento semántico periodico del grafo. Saldar "
                "AP-31 una vez no basta si PAT-6 no se ejecuta; PAT-6 sin AP-31 "
                "pendiente sigue siendo útil."
            ),
        },
        "name": "Grafo sin tipos semanticos — edges sin predicate explícito",
        "type": "antipattern",
        "category": "linking",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Todas las aristas del grafo usan el mismo tipo 'wiki-link' sin distinguir "
            "semántica: depends_on, implements, extends, calls, documents, etc. "
            "Sin predicates tipados, el analisis de impacto y las busquedas semanticas "
            "no pueden filtrar por tipo de relacion. "
            "La solucion es mergear las relaciones de entidad (vault_relation_add) y "
            "codigo (vault_code_relation) en el grafo para enriquecerlo con predicates."
        ),
        "signal": (
            "vault_audit detecta edges sin predicate o con predicate='wiki-link' como "
            "unico tipo en graph.json. Penaliza -3 por cada 100 edges sin predicates "
            "tipados (solo si existen relaciones de entidad o codigo sin mergear)."
        ),
        "prevention": (
            "Ejecutar vault_graph --typed o vault_graph_merge periodicamente para "
            "enriquecer el grafo con predicates. Toda relacion registrada via "
            "vault_relation_add o vault_code_relation debe reflejarse en graph-enriched.json."
        ),
        "tools_enforcing": [],
        "tools_detecting": ["vault_audit", "vault_graph_merge"],
        "introduced_version": "v37",
    },
    # ── Anti-patrón AP-32 ──────────────────────────────────────────────────────
    {
        "code": "AP-32",
        "distinguido_de": {
            "AP-31": (
                "AP-31 es la arista sin `predicate`: la relación existe y no dice de "
                "que tipo es. AP-32 tiene predicate, pero no pertenece a la ontología "
                "declarada. El discriminador es si el campo está presente: ausencia "
                "frente a valor fuera de vocabulario."
            ),
            "AP-33": (
                "Las dos son predicados que la ontología no acepta tal cual. AP-32 es "
                "el predicado desconocido, sin equivalente canónico. AP-33 es el "
                "sinónimo: existe un canónico al que normalizar, y por eso se repara "
                "sin perder información. El discriminador es si hay destino de "
                "normalización."
            ),
        },
        "name": "Relaciones tipadas sin predicate valido en la ontologia",
        "type": "antipattern",
        "category": "linking",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Una relacion registrada en entity relations o code relations usa un "
            "relationType/type que no existe en vault-ontology.json. Esto produce "
            "edges que no pueden interpretarse semanticamente en el grafo enriquecido. "
            "Ej: relationType='inherits' cuando el predicate canonico es 'extends'."
        ),
        "signal": (
            "vault_graph_merge reporta unknown_predicates[] con el predicate invalido "
            "y la fuente (entity/code). Sugiere el predicate canonico mas cercano."
        ),
        "prevention": (
            "Usar solo predicates del vocabulario canonico en vault-ontology.json. "
            "Para entity relations: has_one, has_many, belongs_to, many_to_many, "
            "implements, extends, depends_on, uses, calls, owns, aggregates. "
            "Para code relations: imports, extends, implements, calls, uses, re-exports, depends_on."
        ),
        "tools_enforcing": [],
        # `vault_audit` pesa AP-31, AP-34 y AP-35 del grafo, no AP-32: no hay
        # entrada suya en PENALIZACIONES. El predicate fuera de ontología lo
        # reporta `vault_graph_merge` en `unknown_predicates`.
        "tools_detecting": ["vault_graph_merge"],
        "introduced_version": "v37",
    },
    # ── Anti-patrón AP-33 ──────────────────────────────────────────────────────
    {
        "code": "AP-33",
        "distinguido_de": {
            "AP-32": (
                "Las dos son predicados que la ontología no acepta tal cual. AP-32 es "
                "el predicado desconocido, sin equivalente canónico. AP-33 es el "
                "sinónimo: existe un canónico al que normalizar, y por eso se repara "
                "sin perder información. El discriminador es si hay destino de "
                "normalización."
            ),
        },
        "name": "Predicado no canonico — sinonimo no normalizado",
        "type": "antipattern",
        "category": "linking",
        "severity": "low",
        "enforcement": "audit",
        "description": (
            "Las relaciones de entidad usan `relationType` y las de codigo usan `type` "
            "para el mismo concepto semantico. Ademas, predicates que semanticamente "
            "son equivalentes deben unificarse: `imports` en codigo ≈ `depends_on` "
            "a nivel build-time. La ontologia define el mapeo de sinonimos."
        ),
        "signal": (
            "vault_graph_merge normaliza automaticamente y reporta normalized_predicates[] "
            "con el mapeo aplicado. vault_audit puede reportar instancias donde el "
            "predicate original no era canonico."
        ),
        "prevention": (
            "Al registrar relaciones, usar predicates del vocabulario canonico. "
            "La ontologia maneja el mapeo relationType→predicate y type→predicate "
            "automaticamente. No requiere accion manual."
        ),
        "tools_enforcing": [],
        "tools_detecting": ["vault_graph_merge"],
        "introduced_version": "v37",
    },
    # ── Anti-patrón AP-34 ──────────────────────────────────────────────────────
    {
        "code": "AP-34",
        "distinguido_de": {
            "AP-14": (
                "AP-14 es el wikilink sin destino; AP-34 es la relación tipada cuyo "
                "endpoint no existe. La misma ausencia en dos capas: la sintáctica "
                "del enlace y la semántica del grafo de predicados. Una nota puede "
                "tener AP-34 con todos sus wikilinks intactos."
            ),
        },
        "name": "Relacion tipada huerfana — endpoint inexistente en el vault",
        "type": "antipattern",
        "category": "linking",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Una relacion tipada (entity o code) referencia un endpoint que no existe "
            "como nota en el vault. Ej: relacion `User -- has_many --> Order` donde "
            "no existen `User.md` ni `Order.md`. El grafo enriquecido tendra edges "
            "hacia nodos fantasma que nunca resolveran."
        ),
        "signal": (
            "vault_audit detecta orphan_typed_relations[] listando la relacion y "
            "los endpoints faltantes. vault_graph_merge reporta unresolved_entities[]."
        ),
        "prevention": (
            "SP-02: verificar que los endpoints existan antes de registrar la relacion. "
            "Ejecutar vault_search o vault_list para confirmar que las notas "
            "referenciadas en fromEntity/toEntity existen en el vault."
        ),
        "tools_enforcing": [],
        "tools_detecting": ["vault_audit", "vault_graph_merge"],
        "introduced_version": "v37",
    },
    # ── Anti-patrón AP-35 ──────────────────────────────────────────────────────
    {
        "code": "AP-35",
        "distinguido_de": {
            "AP-31": (
                "AP-31 mira la arista —le falta tipo—; AP-35 mira el conjunto —hay "
                "varios sistemas de relaciones que no se hablan entre si—. Un vault "
                "puede tener todas sus aristas tipadas y aun así estar en silos, y al "
                "revés."
            ),
        },
        "name": "Silos de relacion — sistemas de grafos aislados",
        "type": "antipattern",
        "category": "structure",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "El vault mantiene tres sistemas de relaciones en silos aislados: "
            "(a) wiki-links en graph.json, (b) entity relations en "
            "06_Diagrams/entity/*-relations.json, (c) code relations en "
            "11_Code/.code-index.json. Ninguno de estos sistemas se integra "
            "con los otros, produciendo un grafo de conocimiento fragmentado. "
            "vault_impact y BFS solo ven wiki-links, ignorando relaciones "
            "semanticas ricas registradas en los otros sistemas."
        ),
        "signal": (
            "vault_audit reporta silo_flags[]: entity_relations sin mergear "
            "(AP-35-entity), code_relations sin mergear (AP-35-code), y "
            "graph_enriched_outdated si el enriquecido tiene >24h."
        ),
        "prevention": (
            "Ejecutar vault_graph_merge periodicamente (recomendado: cada sesion "
            "o cada vez que se registren nuevas relaciones). vault_graph --typed "
            "genera graph-enriched.json que unifica los tres sistemas."
        ),
        "tools_enforcing": [],
        "tools_detecting": ["vault_audit", "vault_graph_merge"],
        "introduced_version": "v37",
    },
    {
        "code": "AP-36",
        "distinguido_de": {
            "AP-15": (
                "AP-15 es material ajeno depositado dentro del vault. AP-36 es lo "
                "contrario: side-effects de las tools que salen del vault o no quedan "
                "rastreados. El discriminador es la dirección del cruce de la "
                "frontera."
            ),
        },
        "name": "Contención e idempotencia — side-effects fuera del vault o no rastreables",
        "type": "antipattern",
        "category": "structure",
        "severity": "critical",
        "enforcement": "guard+audit",
        "description": (
            "Toda operación de tooling debe: (1) escribir ÚNICAMENTE dentro del vault root "
            "(backups, traces, locks, stubs, logs incluidos); (2) ser idempotente — ejecutarla "
            "dos veces no duplica artefactos ni carpetas; (3) dejar sus artefactos indexados o "
            "en ubicaciones registradas (vault_registry) para rastreabilidad. Casos históricos: "
            "vault-backups escrito en el abuelo del repo, 00_System/99_Index generados fuera "
            "del vault por detección de root defectuosa, .bak junto a nodos de contenido."
        ),
        "signal": (
            "Carpetas vault-backups/00_System/99_Index como hermanos del vault; archivos .bak/.tmp "
            "dentro de secciones de contenido; secciones sin index.md."
        ),
        "prevention": (
            "Rutas de salida derivadas SIEMPRE de VAULT_ROOT (nunca de __file__ ni cwd). "
            "Artefactos de mantenimiento van a 02_Observability/maintenance/ o 00_System/. "
            "vault_norms --audit detecta artefactos sueltos y secciones sin índice."
        ),
        "tools_enforcing": ["vault_section_index", "vault_io.assert_within_vault"],
        "tools_detecting": ["vault_norms"],
        "introduced_version": "v38",
    },
    # ── Anti-patrón AP-37 ──────────────────────────────────────────────────────
    # Síntoma que la originó: `vault_standard_upgrade --to latest` devolvía
    # `{"ok": true}` habiendo aplicado CERO migraciones, porque _version_index()
    # no normalizaba la minor version y _pending_migrations() devolvía []. El bug
    # sobrevivió versiones enteras porque su respuesta era indistinguible de un
    # éxito real: no había nada en la salida que un test o un agente pudiera
    # contradecir.
    {
        "code": "AP-37",
        "name": "No-op silencioso — ok: true sin indicador de trabajo",
        "type": "antipattern",
        "category": "observability",
        "severity": "high",
        "enforcement": "audit",
        "description": (
            "Una tool con side effects declarados devuelve ok: true sin exponer ningún "
            "campo que distinga 'hice N cosas' de 'no hice nada'. `ok: true` a secas es "
            "una afirmación no falsable: ni un test ni un agente pueden detectar que la "
            "operación fue vacía. Toda tool que modifica estado debe declarar un "
            "indicador de trabajo en declared_returns (changed, applied, count, "
            "migrations_applied, fixes_applied, skipped, no_op…) y devolverlo siempre, "
            "también cuando vale 0."
        ),
        "signal": (
            "declared_returns sin ningún campo de conteo o cambio en una tool con "
            "side_effects; tests que solo afirman result['ok'] sobre operaciones "
            "mutantes."
        ),
        "prevention": (
            "Declarar el indicador en tool-spec.json y devolverlo desde la tool. "
            "vault_noop_audit --check compara el catálogo contra una baseline "
            "congelada: la deuda histórica no bloquea, pero NO puede crecer."
        ),
        "tools_enforcing": ["vault_noop_audit"],
        "tools_detecting": ["vault_noop_audit"],
        "distinguido_de": {
            "AP-60": (
                "AP-37 es el `ok: true` que ninguna evidencia podría "
                "contradecir; AP-60 es la medida que sí se puede refutar pero "
                "solo mira a quien se declaró. Un guard AP-60 publica un total "
                "verdadero de un universo equivocado — comprobable, y por eso "
                "no es AP-37."
            ),
        },
        "introduced_version": "v39",
    },
    # ── Anti-patrón AP-38 ──────────────────────────────────────────────────────
    # Síntoma que lo originó: un censo sobre 17 vaults reales (2.929 notas)
    # encontró 54 valores distintos de `status`, de los cuales solo el 6% caía
    # dentro de STATUS_VOCAB — pese a que CN-03 lo audita desde v38. La causa no
    # eran los agentes: el valor no canónico más frecuente, `implementado`
    # (205 notas), lo escribía `vault_pattern_save`. El estándar publicaba NUEVE
    # vocabularios de `status` en competencia y auditaba contra uno solo.
    {
        "code": "AP-38",
        "distinguido_de": {
            "AP-39": (
                "Las dos fallan sobre el mismo vocabulario. AP-38 es de orden: se "
                "valida después de escribir, así que el valor malo ya está en disco. "
                "AP-39 es de memoria: el vocabulario es abierto y nadie registra lo "
                "que se aceptó, así que no hay contra que validar. El discriminador "
                "es si existe la lista de referencia."
            ),
        },
        "name": "Vocabulario validado después de escribir, no antes",
        "type": "antipattern",
        "category": "consistency",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "Un campo con vocabulario cerrado se acepta tal cual en la escritura y se "
            "comprueba en un audit posterior. El audit no lo ejecuta nadie — en 1.356 "
            "ejecuciones registradas del parque real, `vault_norms` no aparece ni una "
            "vez — así que el vocabulario no gobierna: solo documenta una intención. "
            "Agravante: que varias tools publiquen vocabularios distintos para el mismo "
            "campo (AP-05 aplicado al dato). Un campo canónico se normaliza en el punto "
            "de escritura y rechaza lo que no pueda derivar; los ejes de dominio "
            "legítimos (resultado de un test, fase de un incidente) van a su propio "
            "campo, no compiten por `status`."
        ),
        "signal": (
            "frontmatter.append(f\"status: {status}\") con un vocabulario local; "
            "valores fuera de STATUS_VOCAB en notas escritas por tools del catálogo; "
            "dos tools con listas de estados distintas para el mismo campo."
        ),
        "prevention": (
            "STATUS_SYNONYMS + normalize_status() normalizan en vault_write antes de "
            "emitir. Las tools con eje propio llaman a status_frontmatter_lines(), que "
            "emite `status` canónico y el campo de dominio desde DOMAIN_STATUS_VOCABS. "
            "Lo que arrastraba información y no era estado se conserva en status_note: "
            "no-derogación aplicada al dato."
        ),
        "tools_enforcing": ["vault_write", "vault_norms"],
        "tools_detecting": ["vault_norms"],
        "introduced_version": "v39",
    },
    # ── Anti-patrón AP-39 ──────────────────────────────────────────────────────
    # Síntoma que lo originó: el mismo censo de 17 vaults midió 1.180 tags
    # distintos para 6.358 usos — el 45% aparece en una sola nota — y 55 familias
    # de casi-duplicados (`ci-cd`/`cicd`/`ci_cd`). El ritmo de invención es plano
    # a lo largo de tres meses (37% → 36% → 34% → 27% → 36%): ninguna sesión
    # hereda el vocabulario de la anterior. La causa, otra vez, era el camino de
    # escritura: `vault_write` consultaba una clave que el tag-registry no tiene,
    # así que la sugerencia no se disparó nunca y un tag inventado costaba cero.
    {
        "code": "AP-39",
        "distinguido_de": {
            "AP-38": (
                "Las dos fallan sobre el mismo vocabulario. AP-38 es de orden: se "
                "valida después de escribir, así que el valor malo ya está en disco. "
                "AP-39 es de memoria: el vocabulario es abierto y nadie registra lo "
                "que se aceptó, así que no hay contra que validar. El discriminador "
                "es si existe la lista de referencia."
            ),
        },
        "name": "Vocabulario abierto sin memoria",
        "type": "antipattern",
        "category": "consistency",
        "severity": "medium",
        "enforcement": "guard+audit",
        "description": (
            "Un campo con vocabulario abierto (tags) admite términos nuevos sin dejar "
            "constancia de quién los introdujo ni cuándo. Sin registro no hay "
            "continuidad: cada sesión reinventa las palabras de la anterior, y el "
            "vocabulario crece sin converger — 1.180 términos para 6.358 usos, el 45% "
            "usado una sola vez. A diferencia de AP-38, la respuesta correcta NO es "
            "rechazar: un vocabulario abierto que rechaza empuja a omitir el campo, y "
            "entonces lo que se incumple es AP-26. Lo que hay que cerrar es el olvido, "
            "no la entrada."
        ),
        "signal": (
            "Tags que solo difieren en acento, mayúscula, separador o plural conviviendo "
            "en el mismo vault; proporción de términos usados una sola vez que no baja "
            "con el tiempo; el camino de escritura no lee el registro de vocabulario."
        ),
        "prevention": (
            "vault_write llama a vault_tags.apply_vocabulary() antes de emitir: colapsa "
            "contra el registro canónico lo que es demostrablemente la misma palabra "
            "(normalize_tag + singular_tag) y admite el término nuevo tal cual. Una vez "
            "la nota está en disco, record_new_tags() lo anota en la bitácora "
            "append-only 19_Audits/vocabulary/tag-ledger.json con agente, fecha y nota "
            "de origen. Inventar sigue siendo posible; deja de ser silencioso."
        ),
        "tools_enforcing": ["vault_write", "vault_tags"],
        "tools_detecting": ["vault_tags", "vault_norms"],
        "introduced_version": "v39",
    },
    {
        "code": "AP-40",
        "distinguido_de": {
            "AP-43": (
                "AP-40 es la contradicción visible: el contrato publicado acepta algo "
                "que la CLI rechaza. AP-43 es la ausencia: la norma existe y el punto "
                "de uso no la menciona ni la aplica. El discriminador es si hay dos "
                "afirmaciones en conflicto o solo una sin refuerzo."
            ),
        },
        "name": "Contrato publicado que la CLI rechaza",
        "type": "antipattern",
        "category": "consistency",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "Una tool publica en su catálogo parámetros que su propio argparse no "
            "acepta. La tool aparece en tools/list, se puede invocar, y falla "
            "siempre con 'unrecognized arguments'. Medido en v39: 45 de 82 tools "
            "conciliables publicaban al menos un param inexistente — más de la "
            "mitad de la superficie MCP era inalcanzable sin que nada lo señalara, "
            "porque el guard de sincronía comparaba el JSON contra el Python: dos "
            "copias de la misma equivocación coinciden perfectamente."
        ),
        "signal": (
            "Invocar la tool por MCP devuelve 'unrecognized arguments'; el nombre "
            "de un param del catálogo no aparece como flag largo en el script."
        ),
        "prevention": (
            "El contrato de argumentos lo declara argparse, no el catálogo: "
            "vault_mcp_catalog.argparse_params() lee los add_argument del script y "
            "reconciled_params() publica solo lo que la CLI acepta, conservando la "
            "descripción escrita a mano cuando el nombre coincide. "
            "vault_mcp_catalog --check-params audita el JSON ya generado (que es lo "
            "que el servidor consume) contra el argparse real."
        ),
        "tools_enforcing": ["vault_mcp_catalog"],
        "tools_detecting": ["vault_mcp_catalog", "vault_norms"],
        "introduced_version": "v39",
    },
    {
        "code": "AP-41",
        "distinguido_de": {
            "CN-03": (
                "CN-03 mira el valor aislado: pertenece al vocabulario. AP-41 mira la "
                "transición: la máquina de estados está declarada y nadie verifica "
                "que los saltos entre valores sean legales. Todos los valores pueden "
                "ser válidos y la secuencia imposible."
            ),
        },
        "name": "Máquina de estados declarada sin verificar",
        "type": "antipattern",
        "category": "lifecycle",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "El estándar declara STATUS_TRANSITIONS —las transiciones válidas del "
            "ciclo de vida de una nota— y no las recorre nadie: su único consumidor "
            "era su propio test de coherencia. Un estado que no controla su "
            "transición es una etiqueta, no un ciclo de vida: una nota 'archived' "
            "podía volver a 'draft', o saltar de 'planned' a 'verified' sin pasar "
            "por revisión, y ningún guard lo veía. Es la misma forma del fallo "
            "histórico del estándar —declarar sin ejecutar— con la agravante de que "
            "existía un test en verde que verificaba que el grafo estaba bien "
            "dibujado, no que alguien lo recorriera."
        ),
        "signal": (
            "Secuencias de `status` en .history/ que no siguen ninguna arista de "
            "STATUS_TRANSITIONS; notas cuyo estado retrocede sin explicación; "
            "ningún script fuera de los tests importa STATUS_TRANSITIONS."
        ),
        "prevention": (
            "vault_write lee el `status` de la nota en disco antes de sobrescribirla "
            "y rechaza la transición que no está en STATUS_TRANSITIONS, citando los "
            "destinos válidos. Una actualización que no menciona `status` conserva el "
            "estado previo en vez de caer al default 'draft'. Las transiciones ya "
            "ocurridas se reportan desde .history/ con vault_norms --audit: se anotan, "
            "no se reescriben, porque el estado actual es un hecho."
        ),
        "tools_enforcing": ["vault_write"],
        "tools_detecting": ["vault_norms"],
        "introduced_version": "v39",
    },
    {
        "code": "AP-42",
        "distinguido_de": {
            "AP-04": (
                "AP-04 mide la nota: describe como entregado algo que no lo está. "
                "AP-42 mide la tool: está publicada en el catálogo y nunca se "
                "ejecutó. El discriminador es el sujeto medido —texto frente a "
                "artefacto ejecutable—, y por eso una la detecta el audit de "
                "contenido y la otra el smoke."
            ),
        },
        "name": "Tool publicada sin haberse ejecutado nunca",
        "type": "antipattern",
        "category": "process",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "Una tool se publica en el catálogo MCP porque responde a `--help` y "
            "porque su entrada existe. `--help` demuestra que el argparse se "
            "construye: no que el módulo importe sus dependencias, ni que el ejemplo "
            "documentado sea aceptado por la CLI, ni que la salida sea el JSON que el "
            "contrato promete. La primera medición dio 41 de 87 tools cuyo ejemplo "
            "documentado no llegaba a emitir un JSON con `ok` —36 de ellas porque el "
            "ejemplo del catálogo usaba flags que la CLI rechazaba, exactamente el "
            "defecto de AP-40 trasladado a la superficie de documentación."
        ),
        "signal": (
            "Ejemplos del catálogo o del README que salen con exit 2 y "
            "'unrecognized arguments'; tools cuya salida es texto para humanos sin "
            "modo JSON; tools que no aparecen en ningún test ni en ninguna ejecución."
        ),
        "prevention": (
            "vault_smoke ejecuta el ejemplo documentado de cada tool contra una copia "
            "desechable del vault de pruebas y exige tres cosas: que termine, que su "
            "salida sea JSON y que ese JSON tenga `ok`. Un `ok: false` bien formado "
            "aprueba: lo que se persigue es el fallo mudo. La baseline solo puede "
            "encoger y quedó en 0, así que es un guard duro desde el primer día. Las "
            "tools sin invocación posible (un servicio HTTP que no retorna) se "
            "declaran en SIN_SMOKE con su motivo, nunca se omiten en silencio."
        ),
        "tools_enforcing": ["vault_smoke"],
        "tools_detecting": ["vault_smoke", "vault_norms"],
        "introduced_version": "v39",
    },
    {
        "code": "AP-43",
        "distinguido_de": {
            "AP-40": (
                "AP-40 es la contradicción visible: el contrato publicado acepta algo "
                "que la CLI rechaza. AP-43 es la ausencia: la norma existe y el punto "
                "de uso no la menciona ni la aplica. El discriminador es si hay dos "
                "afirmaciones en conflicto o solo una sin refuerzo."
            ),
        },
        "name": "Norma sin refuerzo en el punto de uso",
        "type": "antipattern",
        "category": "governance",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "El catálogo de normas está completo, versionado y con guards, pero el "
            "agente que documenta el vault no lo tiene delante mientras trabaja: se "
            "entera de que una norma existe cuando la incumple —y solo si esa norma "
            "es una de las 14 que previenen, no una de las 33 que se limitan a "
            "detectar en un audit que puede no correrse nunca. El refuerzo llega "
            "tarde, fuera de contexto o no llega. Una norma que el agente no ve en el "
            "momento de escribir no gobierna la escritura: gobierna el post-mortem."
        ),
        "signal": (
            "Normas que ninguna tool declara en tools_enforcing ni tools_detecting "
            "(no se pronuncian nunca); resultados de tool que no llevan bloque "
            "`vault_says`; agentes que repiten el mismo antipatrón entre sesiones."
        ),
        "prevention": (
            "vault_errors.wrap_main —el único punto por el que ya pasa la salida de "
            "todas las tools— añade a cada resultado un bloque `vault_says` derivado "
            "de NORM_CATALOG y del estado real de esa llamada: qué norma acaba de "
            "actuar, cuántas notas cambiaron, qué mirar a continuación. El refuerzo "
            "rota entre las normas que gobiernan esa tool para no degradarse en ruido "
            "fijo. vault_voice --coverage nombra las normas que ninguna tool pronuncia."
        ),
        "tools_enforcing": ["vault_voice", "vault_errors"],
        "tools_detecting": ["vault_voice", "vault_norms"],
        "introduced_version": "v39",
    },
    {
        "code": "AP-44",
        "name": "Verificación autoconsistente — la tool se certifica a sí misma",
        "type": "antipattern",
        "category": "quality",
        "severity": "critical",
        "enforcement": "guard+audit",
        "description": (
            "Una tool escribe o mide con un criterio propio y verifica el resultado "
            "con ESE MISMO criterio, en vez de con el que usa el consumidor real "
            "—Obsidian al resolver un enlace, el parser de Mermaid al dibujar, YAML "
            "al leer un frontmatter, el audit del propio estándar al juzgar la nota "
            "que otra tool acaba de escribir. La tool queda internamente coherente y "
            "por eso mismo ciega a su propio fallo: no puede detectar el error porque "
            "lo comete en los dos lados de la comparación. Es más caro que un bug "
            "normal, porque el guard sale en verde y dirige el trabajo hacia donde no "
            "hay problema: reescribir enlaces que funcionan, 'corregir' diagramas "
            "válidos, retaguear notas ya etiquetadas."
        ),
        "signal": (
            "Dos tools del estándar dan cifras distintas para lo mismo (146 vs 86 "
            "enlaces rotos); un hallazgo desaparece al normalizar y reaparece al "
            "abrir el vault; el generador de una nota produce metadatos que el audit "
            "del mismo estándar reprueba; un 'arreglo' se declara aplicado y el "
            "usuario sigue viendo el problema; el 100% de una categoría de hallazgos "
            "resulta falsa al inspeccionarla a mano."
        ),
        "prevention": (
            "Verificar con el criterio del consumidor, no con el propio: resolver "
            "wikilinks por nombre de fichero y `aliases:` —nunca por `title:`, que "
            "Obsidian no mira—, leer frontmatter con `yaml.safe_load` y no con un "
            "regex por líneas, y validar Mermaid contra su gramática real. Toda tool "
            "que escribe reevalúa el resultado releyendo del disco. Un frontmatter "
            "ilegible devuelve error explícito, nunca `{}` silencioso, que es lo que "
            "hace que un write path anteponga un segundo bloque y corrompa la nota. "
            "Y toda medida se contrasta contra un vault preexistente ajeno al "
            "estándar: `vault-sandbox/` lo genera el propio estándar y comparte sus "
            "supuestos, así que no puede exhibir este fallo."
        ),
        # v40.28 — la gramática de Mermaid se mudó a `vault_mermaid_reglas`
        # (AP-62), y con ella el sitio que aplica AP-44: validar contra la
        # gramática real y no contra el criterio del generador. Se nombra al
        # dueño, no a la fachada, porque la traza tiene que llevar al código.
        "tools_enforcing": ["vault_audit", "vault_graph_fix", "vault_mermaid_reglas"],
        "tools_detecting": ["vault_norms", "vault_audit"],
        "distinguido_de": {
            "AP-55": (
                "AP-44 se comete al verificar: la tool mide con su propia "
                "normalización y queda ciega a su error. AP-55 está en el dato "
                "antes de que nadie verifique: dos registros canónicos afirman "
                "cosas distintas sobre el mismo hecho. Un catálogo puede ser "
                "coherente y estar verificado por un guard autoconsistente "
                "(AP-44 solo), o ser incoherente aunque el guard mire fuera "
                "(AP-55 solo). Se dieron juntos en v40.10, que es por lo que "
                "conviene tenerlos separados por escrito."
            )
        },
        "introduced_version": "v39",
    },
    {
        "code": "AP-45",
        "distinguido_de": {
            "AP-20": (
                "AP-45 es la nota que existe para que la sección no aparezca vacía: "
                "la cobertura se afirma sin evidencia detrás. AP-20 es la nota que "
                "tiene estructura y listas vacías. AP-45 se mide contra lo que la "
                "nota dice cubrir; AP-20, contra su propio contenido."
            ),
        },
        "name": "Cobertura sin evidencia — la nota existe para llenar la sección",
        "type": "antipattern",
        "category": "quality",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "Una nota se crea porque una sección estaba vacía, no porque hubiera algo "
            "que afirmar. Su cuerpo son encabezados y marcadores de pendiente "
            "—`_Pendiente_`, `TODO`, `— No detectados`— y no enlaza con nada. Sube la "
            "cobertura y baja la fiabilidad: el conteo de notas dice que la sección "
            "está cubierta, el health score la cuenta como nota real, y el siguiente "
            "lector la abre esperando contenido. Es más caro que la ausencia, porque "
            "la ausencia sí se ve: un hueco invita a llenarlo, un relleno declara que "
            "ya está hecho. El generador que la escribió creía estar documentando."
        ),
        "signal": (
            "Notas cuyo cuerpo bajo el frontmatter, quitados encabezados y "
            "marcadores, queda vacío y sin wikilinks salientes; secciones que pasan "
            "de 0 a N notas en una sola ejecución de una tool; ADRs numerados sin "
            "nombre; conceptos cuyo cuerpo entero remite a leer otra fuente."
        ),
        "prevention": (
            "No escribir la nota sin evidencia detrás. Un generador que no encuentra "
            "contenido real para una sección lo declara en `warnings` y en "
            "`next_steps` —que es información útil— en vez de emitir un stub, que es "
            "desinformación. El andamiaje declarado sí es legítimo: los primers de "
            "vault_init llevan `status: template` y quedan exentos, porque anuncian "
            "lo que son. Secciones dirigidas por eventos (18_Bugs, 19_Audits, "
            "20_Quarantine) se quedan vacías hasta que ocurre el evento."
        ),
        "tools_enforcing": ["vault_onboard", "vault_write"],
        "tools_detecting": ["vault_norms", "vault_audit"],
        "introduced_version": "v39",
    },
    # ── Antipatrón AP-46 ───────────────────────────────────────────────────────
    {
        "code": "AP-46",
        "distinguido_de": {
            "AP-12": (
                "AP-12 es el síntoma medido en las notas: dos notas del mismo tipo "
                "con frontmatter distinto. AP-46 es la causa medida en el código: no "
                "hay escritor único de frontmatter. Se separan porque el vault puede "
                "quedar coherente a mano con la causa intacta."
            ),
            "AP-48": (
                "AP-46 es el caso particular de AP-48 sobre el frontmatter: cada tool "
                "lo escribe a su manera en vez de pasar por un escritor único. AP-48 "
                "es la forma general: la misma funcionalidad implementada dos veces, "
                "una por camino de acceso. Se declara así para que saldar AP-46 no se "
                "lea como haber saldado AP-48."
            ),
        },
        "name": "Frontmatter a mano — cada tool es su propio escritor",
        "type": "antipattern",
        "category": "consistency",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "Veintiséis tools montan el frontmatter concatenando líneas y tres "
            "importan el write path canónico. Cada concatenación es un segundo autor "
            "del formato sin guard detrás: el bloque se cierra o no, `type:` está o "
            "no, la fecha lleva el formato de quien la escribió. El fallo no se ve "
            "al escribir —la tool devuelve `ok: true` porque el fichero se creó— "
            "sino al auditar, y para entonces la nota ya es el dato. Es el mismo "
            "patrón que produjo 22 implementaciones de `slugify` y tres verdades "
            "para la lista de secciones: una fuente única declarada en la "
            "documentación y N implementaciones en el código. `vault_migrate_docs` "
            "cortaba el documento por la línea 7 y llevaba versiones publicándose "
            "así, con el bloque de frontmatter sin cerrar."
        ),
        "signal": (
            "Notas con `---` de apertura que nunca cierra o cuyo bloque no parsea "
            "con `yaml.safe_load`; notas sin `type:` recién escritas por una tool; "
            "tools que construyen listas de líneas de frontmatter en vez de llamar "
            "al write path; el generador aprueba y `vault_audit` reporta "
            "`missingFrontmatter` sobre lo que él mismo acaba de escribir."
        ),
        "prevention": (
            "El write path valida lo que escribe releyendo el resultado, no "
            "confiando en cómo se construyó: `atomic_write_text` rechaza un bloque "
            "de frontmatter que abre y no cierra o que no parsea, y registra el que "
            "parsea pero sale sin `type:`. Así el guard alcanza a las 26 tools sin "
            "reescribir ninguna, y la adopción de `vault_write` puede ser gradual. "
            "Verificar con el criterio del consumidor —`yaml.safe_load`, no un "
            "regex por líneas— es AP-44 aplicado al generador."
        ),
        "tools_enforcing": ["vault_io.atomic_write_text", "vault_write"],
        # AP-46 es una norma sobre **tools**, no sobre notas: dice que veintiséis
        # tools montan el frontmatter a mano. `vault_audit` audita notas y no
        # puede verlo. Quien lo mide es `vault_norms`.
        "tools_detecting": ["vault_norms"],
        "introduced_version": "v39.3",
    },
    # ── Antipatrón AP-47 ───────────────────────────────────────────────────────
    {
        "code": "AP-47",
        "name": "Artefacto derivado desfasado — el índice dejó de reflejar el disco",
        "type": "antipattern",
        "category": "consistency",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "El vault es la fuente de verdad y `search-index.json` y `graph.json` "
            "son proyecciones suyas. Una escritura que no pasa por `vault_write` "
            "—un agente remoto, una tool que escribe la nota y no toca el índice, "
            "una copia a mano— deja la proyección atrás, y a partir de ahí el "
            "agente busca sobre un mapa viejo: la nota existe y `vault_search` no "
            "la encuentra, así que la vuelve a escribir. La duplicación no es un "
            "descuido del agente, es la consecuencia lógica de un índice que "
            "miente.\n\n"
            "El estándar no lleva base de datos por decisión normativa, y con "
            "consistencia eventual el desfase es esperable. Lo que no es "
            "aceptable es que **nadie lo mida**: `vault_reindex --check` "
            "comprobaba `len(notes) > 0`, de modo que un índice con una entrada "
            "sobre un vault de 300 notas pasaba la puerta."
        ),
        "signal": (
            "`vault_reindex --check` devuelve `index_stale`; el conteo de `.md` en "
            "las secciones canónicas no coincide con las entradas de "
            "`search-index.json`; `vault_search` devuelve 0 resultados sobre una "
            "nota que está en disco; `graph.json` tiene menos nodos que notas."
        ),
        "prevention": (
            "`vault_reindex --check` contrasta disco contra índice con el mismo "
            "criterio con el que reconstruye —una sola función, `_notas_en_disco()`, "
            "para que la comprobación y el arreglo no puedan medir cosas distintas "
            "(AP-44)— y reporta las dos direcciones: notas invisibles para la "
            "búsqueda y entradas que apuntan a ficheros que ya no están. El "
            "remedio es `vault_reindex`, y por eso la norma se audita en vez de "
            "bloquear: el desfase es un estado a reconciliar, no una escritura a "
            "rechazar."
        ),
        "tools_enforcing": ["vault_reindex", "vault_write"],
        "tools_detecting": ["vault_norms", "vault_reindex"],
        "distinguido_de": {
            "AP-59": (
                "AP-47 es la **cifra** escrita a mano en la documentación; AP-59 "
                "es su versión estructural, la **lista** escrita a mano en el "
                "código. Comparten disciplina —derivar en vez de escribir— y por "
                "eso los umbrales de AP-59 no pueden ser literales sin cometer "
                "AP-47 dentro de AP-59."
            ),
        },
        "introduced_version": "v39.3",
    },
    {
        "code": "AP-48",
        "distinguido_de": {
            "AP-46": (
                "AP-46 es el caso particular de AP-48 sobre el frontmatter: cada tool "
                "lo escribe a su manera en vez de pasar por un escritor único. AP-48 "
                "es la forma general: la misma funcionalidad implementada dos veces, "
                "una por camino de acceso. Se declara así para que saldar AP-46 no se "
                "lea como haber saldado AP-48."
            ),
        },
        "name": "Implementación paralela por camino de acceso",
        "type": "antipattern",
        "category": "consistency",
        "severity": "critical",
        "enforcement": "guard+audit",
        "description": (
            "La misma tool publicada tiene dos implementaciones y cuál se ejecuta "
            "depende de por dónde entres. No es una fachada sobre un núcleo "
            "común: son dos cuerpos de código que nadie contrasta, con un solo "
            "nombre y un solo contrato publicado — así que el contrato describe "
            "como mucho a uno de los dos.\n\n"
            "Es AP-05 (múltiples fuentes de verdad) desplazado del dato al camino "
            "de ejecución, y se le parece poco en lo importante: dos definiciones "
            "de un vocabulario acaban divergiendo y alguien lo nota al leerlas, "
            "mientras que dos implementaciones divergen **en silencio** porque "
            "cada una tiene su propio público. La suite prueba una; el agente "
            "ejecuta la otra; las dos están verdes.\n\n"
            "Medido en v39.5 sobre el servidor MCP: nueve tools con backend "
            "nativo en Node, siete de ellas con script Python del mismo nombre. "
            "Ninguna de las siete compartía un solo campo de envelope con el "
            "contrato de `00_System/tool-spec.json` — `vault_fundamentals` "
            "devolvía `compliance_pct`/`passed` donde el contrato dice "
            "`path`/`total`. Y la divergencia peor no era de forma sino de "
            "efecto: la implementación nativa de `vault_graph` no escribía el "
            "grafo, así que un agente la llamaba, recibía `ok: true` y el índice "
            "se quedaba desfasado — AP-37 y AP-47 servidos por el único camino "
            "que un agente real usa. `vault_smoke` recorría las 91 tools del "
            "catálogo ejecutando el `.py`: probaba exactamente la implementación "
            "que el agente no toca."
        ),
        "signal": (
            "Una tool del catálogo tiene backend nativo en el servidor MCP **y** "
            "script en `scripts/`; el envelope que devuelve por MCP no cubre los "
            "`declared_returns` de su contrato; un side effect declarado en el "
            "contrato no ocurre por uno de los dos caminos."
        ),
        "prevention": (
            "Backend nativo solo para lo que **no tiene** implementación en "
            "Python; todo lo demás cae al runner, que es donde vive el contrato "
            "publicado. La implementación desplazada no se borra (no-derogación): "
            "se anota `superseded_by:` y se deja fuera del despacho. La regla se "
            "comprueba por comportamiento y no por lectura del código — se llama "
            "la tool por MCP y se contrasta el envelope contra el contrato, que "
            "es el criterio del consumidor y no el propio (AP-44)."
        ),
        "tools_enforcing": ["vault_mcp_catalog"],
        "tools_detecting": ["vault_norms", "vault_mcp_catalog"],
        "introduced_version": "v39.5",
    },
    {
        "code": "AP-49",
        "name": "Vínculo resuelto en tiempo de import",
        "type": "antipattern",
        "category": "architecture",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "Un módulo deriva su ruta, su configuración o su dependencia en el "
            "momento de **importarse**, no en el de usarse. `SYSTEM_DIR = "
            "VAULT_ROOT / '00_System'` a nivel de módulo se evalúa una sola vez, "
            "cuando el intérprete carga el fichero, y a partir de ahí es una "
            "constante.\n\n"
            "Lo grave no es la constante: es que deja **inerte una costura que "
            "existe**. `vault_io.set_vault_root()` está publicado y 12 tests lo "
            "usan, pero no puede reapuntar a un módulo que ya calculó su ruta al "
            "cargar. La inyección parece disponible y no lo está, que es peor que "
            "no tenerla — quien la usa cree haber redirigido la escritura.\n\n"
            "Medido en v40.0 por el propio guard: **0 vínculos congelados en "
            "0 módulos**. "
            "Eran 82 en 62 módulos antes de empezar a migrar contextos al "
            "dominio, y cayeron uno a uno: Durabilidad los dejó en 77, "
            "Índices en 69, Grafo en 51, Consulta en 45, Gobernanza en 38, "
            "Ciclo de vida en 34, Meta-toolkit en 31 y Autoría —donde estaban "
            "los 31 últimos, el 100% de la deuda que quedaba— en 0. Llegar a "
            "cero destapó la otra mitad de la norma: veinte módulos seguían "
            "haciendo `from vault_io import VAULT_ROOT` y usándolo **dentro de "
            "funciones**. No son asignaciones de nivel de módulo, así que el "
            "guard los daba por limpios, y seguían dependiendo del paliativo de "
            "reanclaje que el refactor existe para no necesitar. Se mide aparte "
            "(`raw_vault_root_imports`), también en cero, y el caso legítimo se "
            "pide con alias. La "
            "cifra es la que "
            "cuenta `vault_arch --check`, no una estimación a ojo: la norma y su "
            "puerta miden lo mismo o la norma no es comprobable. La consecuencia visible era "
            "que `cli/runner.py` aislaba cada tool en un subproceso citando "
            "«estado a nivel de módulo» como razón: el aislamiento por proceso "
            "no era una decisión de diseño libre sino la compensación de este "
            "acoplamiento. Saldada la deuda, esa razón caducó y quedó anotada "
            "allí mismo; el subproceso se conserva por las otras dos que siguen "
            "siendo ciertas —timeout que puede matar lo que vigila, y envelope "
            "sin reinterpretar—. El refactor lo hizo posible, no conveniente."
        ),
        "signal": (
            "Las pruebas necesitan subprocesos para aislarse unas de otras; "
            "`set_vault_root()` no cambia dónde escribe una tool; dos raíces de "
            "vault no pueden coexistir en el mismo intérprete; una asignación de "
            "nivel de módulo deriva de `VAULT_ROOT` sin pasar por "
            "`get_vault_root()`."
        ),
        "prevention": (
            "La raíz y sus derivadas se reciben, no se importan: el dominio toma "
            "un contexto (`VaultContext`) y el adaptador lo construye por "
            "llamada. Si un módulo necesita la ruta, la resuelve **tarde** con "
            "`get_vault_root()` dentro de la función. El guard es AST sobre "
            "asignaciones de nivel de módulo que derivan de `VAULT_ROOT`, con "
            "baseline que solo puede encoger — la deuda medida no se arregla en "
            "un commit, pero no puede crecer."
        ),
        "tools_enforcing": ["vault_arch"],
        "tools_detecting": ["vault_norms", "vault_arch"],
        "distinguido_de": {
            "AP-58": (
                "AP-49 mira **cuándo** se resuelve un vínculo: un valor "
                "copiado en tiempo de import deja de responder a un reanclaje. "
                "AP-58 mira la **dirección** de la dependencia, no su momento. "
                "Se tocan porque el ciclo del núcleo es parte de lo que obliga "
                "a congelar vínculos, pero un módulo puede tener ciclos sin un "
                "solo vínculo congelado, y al revés."
            )
        },
        "introduced_version": "v40.0",
    },
    {
        "code": "AP-50",
        "name": "Decisión duplicada sin dueño declarado",
        "type": "antipattern",
        "category": "architecture",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "La misma **decisión** —qué valores son válidos, cuál es el default, "
            "cómo se escapa un campo— se toma en más de un punto de uso sin que "
            "ningún registro declare quién manda. No es AP-05: aquel habla de un "
            "**dato** con dos fuentes, y se ve porque las dos copias divergen. "
            "Esto se ve cuando ya divergieron, que es tarde.\n\n"
            "Lo que lo hace caro es que cada copia parece correcta en su sitio. "
            "`SEVERITIES = ['critical', 'high', 'medium', 'low']` no está mal "
            "escrito en ninguno de los catorce ficheros donde se midió; está mal "
            "que sean catorce y que nada los compare. El día que el registro "
            "cambie, la copia que se quede atrás rechazará un valor válido o "
            "aceptará uno inventado, y ningún test lo notará porque cada fichero "
            "sigue siendo coherente consigo mismo.\n\n"
            "Medido en v40.1 por sus tres guards: **0 copias de vocabulario, 0 "
            "lecturas de entorno sin declarar, 0 vocabularios sin contexto "
            "dueño**. Eran 14 copias del vocabulario en 13 módulos —cuatro como "
            "`choices=` de argparse y diez como constante— y 13 variables de "
            "entorno con su default escrito en cada punto de lectura, de las que "
            "solo seis estaban documentadas. Dos ya habían divergido antes de "
            "que existiera el guard: `VAULT_VOICE` se comparaba contra "
            "`'verbose'` en un módulo y contra `'0'` con default `'1'` en otro, y "
            "`VAULT_MCP_LOG` estaba declarada como fichero de log mientras el "
            "único código que la lee la usa como nivel con default `'info'`.\n\n"
            "El dueño es la mitad que faltaba. `vault_norms.DOMAIN_STATUS_VOCABS` "
            "ya había resuelto esto para `status` en v39 y se quedó solo: "
            "compartir la constante evita la copia, pero no contesta quién decide "
            "cuándo cambia. Por eso cada entrada del registro declara el contexto "
            "acotado que manda sobre ella, y ese contexto tiene que existir en "
            "`vault_arch.CONTEXTS`."
        ),
        "signal": (
            "Un literal de lista o de tupla reproduce —en cualquier orden— un "
            "vocabulario que el registro ya declara; un `os.environ.get()` con "
            "un default escrito en el punto de lectura; un `choices=` de argparse "
            "con valores en duro; dos módulos que escriben el mismo campo con "
            "criterios de escapado distintos; un vocabulario declarado sin "
            "contexto dueño."
        ),
        "prevention": (
            "Registro canónico con dueño, consumidores derivados, guard sin "
            "baseline. Los vocabularios cerrados en `vault_vocabulario.py`, la "
            "configuración en `vault_entorno.py`, y `vault_arch --check` "
            "fallando si aparece una copia, una lectura sin declarar o un "
            "vocabulario huérfano. **Sin baseline a propósito**: las catorce "
            "copias se saldaron al declarar el registro, así que la puerta nace "
            "en cero y una baseline solo serviría para admitir la número quince. "
            "Lo que ya tiene registro canónico no se copia: se declara "
            "`derivado_de` y se resuelve al llamarse, nunca al importarse "
            "(AP-49). Un dato canónico que no es puerto de su contexto se acaba "
            "copiando — los tres registros que `CLAUDE.md` declara fuente única "
            "de verdad se leían por fuera de la superficie publicada, y así "
            "nacieron las catorce copias."
        ),
        "tools_enforcing": ["vault_arch"],
        "tools_detecting": ["vault_norms", "vault_arch"],
        "distinguido_de": {
            "AP-57": (
                "AP-50 mira **datos** duplicados —vocabularios, defaults, "
                "regex—: dos copias que divergen se ven al compararlas. AP-57 "
                "mira **criterios** enterrados en una condición, donde no hay "
                "dato que comparar y la divergencia solo aparece por el "
                "resultado equivocado."
            )
        },
        "introduced_version": "v40.1",
    },
    {
        "code": "AP-51",
        "distinguido_de": {
            "AP-52": (
                "Las dos son fallos del manejo de error en una tool. AP-51 es la "
                "atribución: la tool devuelve un vacío que culpa al dato de su propio "
                "fallo. AP-52 es la forma: el envelope de error se emite fuera del "
                "contrato de ERROR_CATALOG. Un error puede estar bien atribuido y mal "
                "formado, y al revés."
            ),
            "AP-61": (
                "Son los dos extremos del mismo eje. AP-51 es el handler "
                "**demasiado ancho**: captura de más, se traga el fallo propio y "
                "devuelve un vacío indistinguible de un resultado legítimo. "
                "AP-61 es el handler **demasiado estrecho**: nombra menos de lo "
                "que la llamada lanza, así que no se traga nada — deja pasar. El "
                "discriminador es que pasa después del fallo: con AP-51 la tool "
                "sigue y miente, con AP-61 la tool cae."
            ),
        },
        "name": "La tool culpa al dato de su propio fallo",
        "type": "antipattern",
        "category": "quality",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "Una tool falla al leer o al interpretar algo, se traga el fallo y "
            "devuelve un vacio que el llamante no puede distinguir de un "
            "resultado legitimo. El error deja de ser un error y pasa a ser un "
            "**hecho sobre el vault**: el informe que lo agregue dira que N "
            "notas no tienen aliases, y no sera cierto \u2014 es que no se "
            "pudieron leer.\n\n"
            "No es lo mismo *no hay* que *no pude mirar*, y esa es toda la "
            "norma. AP-44 cubre la mitad de arriba \u2014verificar con el "
            "criterio del consumidor y no con el propio\u2014; esta cubre la de "
            "abajo, que es el mecanismo por el que un fallo propio acaba "
            "pareciendo un dato malo. Salio al ejecutar contra un vault ajeno "
            "al estandar (**regla 7**): tres tools declaraban invalidas notas "
            "que Obsidian leia sin problema. Las notas estaban bien; el "
            "criterio que las media, no.\n\n"
            "Lo que la norma **no** prohibe es capturar amplio. Prohibe "
            "capturar amplio y callarse: devolver `ok: false` con el error es "
            "correcto porque el llamante recibe la mala noticia y decide. "
            "Capturar `FileNotFoundError` tampoco infringe: es un criterio, el "
            "autor sabe que tolera y por que. Lo que infringe es `except "
            "Exception: return []`.\n\n"
            "Medida en v40.1: **86 sitios en 37 modulos**. Nace con baseline "
            "por la misma razon que AP-37 \u2014que empezo en 55 y llego a "
            "0\u2014: un guard que falla en 86 sitios se desactiva el primer "
            "dia, y un guard desactivado no protege nada. La baseline solo "
            "puede encoger.\n\n"
            "El propio detector estreno el fallo que persigue. La primera "
            "version midio 101 sitios porque clasificaba `except "
            "yaml.YAMLError` como captura amplia: son `ast.Attribute` y no "
            "`ast.Name`, asi que caian en la rama del `except` desnudo. "
            "Contaba como infraccion justo las capturas mas precisas del "
            "repo. Quince falsos positivos, y el error era el de AP-44 "
            "cometido dentro del guard."
        ),
        "signal": (
            "Un `except Exception` o un `except` desnudo cuya unica salida es "
            "`return []`, `return {}`, `return None`, `pass` o `continue`; un "
            "recuento agregado que no distingue el cero medido del cero por "
            "fallo de lectura; un veredicto sobre una nota emitido por un "
            "camino que ya habia fallado."
        ),
        "prevention": (
            "Capturar la excepcion concreta que se sabe tolerar, y si se "
            "captura amplio, **exponer**: devolver el fallo en el envelope en "
            "vez de un vacio. Cuando el vacio es la respuesta correcta, "
            "distinguirlo del vacio por fallo con un campo aparte "
            "(`unreadable`, `errors`) para que el agregado no los confunda. "
            "`vault_blame_audit --check --strict` mide por AST y no por "
            "texto: un detector que buscara la cadena `except Exception` no "
            "veria la diferencia entre devolver un vacio y devolver un "
            "envelope con `ok: false`, que es toda la distincion que la norma "
            "sostiene."
        ),
        "tools_enforcing": ["vault_blame_audit"],
        # No se lista `vault_norms --audit`: ese audita el **contenido del
        # vault**, y esta norma es sobre el codigo de las tools. Declararlo
        # aqui seria una tool_detecting que no detecta nada, que es la misma
        # afirmacion no falsable que AP-37 persigue.
        "tools_detecting": ["vault_blame_audit"],
        "introduced_version": "v40.1",
    },
    {
        "code": "AP-52",
        "distinguido_de": {
            "AP-51": (
                "Las dos son fallos del manejo de error en una tool. AP-51 es la "
                "atribución: la tool devuelve un vacío que culpa al dato de su propio "
                "fallo. AP-52 es la forma: el envelope de error se emite fuera del "
                "contrato de ERROR_CATALOG. Un error puede estar bien atribuido y mal "
                "formado, y al revés."
            ),
        },
        "name": "El error se emite fuera del contrato del catalogo",
        "type": "antipattern",
        "category": "quality",
        "severity": "medium",
        "enforcement": "guard+audit",
        "description": (
            "Una tool falla, lo dice, y lo dice mal: devuelve `{\"ok\": false, "
            "\"error\": \"...\"}` escrito a mano en vez de pasar por "
            "`vault_errors.emit_error`. La frase es correcta; el contrato, no. "
            "El envelope del catalogo trae `error_code`, `category`, "
            "`severity`, `recovery` y `timestamp`; el escrito a mano no trae "
            "ninguno.\n\n"
            "Importa porque el consumidor no lee la frase: **decide por el "
            "codigo**. El servidor MCP y `cli/` deciden si reintentar, abortar "
            "o pedir permiso mirando `error_code` y `recovery.action`. Sin "
            "ellos, un fallo con recuperacion conocida llega como un fallo "
            "opaco, y la unica salida del agente que lo recibe es adivinar.\n\n"
            "Es AP-05 aplicada al **contrato de error** \u2014hay un registro "
            "que declara como se nombra y se recupera cada fallo, y 158 sitios "
            "que lo deciden por su cuenta\u2014 y es AP-51 vista desde el otro "
            "lado: alli el fallo se disfrazaba de dato, aqui llega como fallo "
            "pero desnudo de todo lo que lo hace accionable.\n\n"
            "Salio de la caracterizacion maliciosa: invocar las 94 tools de "
            "forma malformada y mirar **como** fallan, no si fallan. El grueso "
            "estaba limpio \u2014las 45 tools con `required_args` rechazan la "
            "invocacion vacia por argparse, y las 92 tools Python rechazan un "
            "flag desconocido\u2014 y el hallazgo estaba en la forma del "
            "envelope, no en su ausencia.\n\n"
            "Medida en v40.2: **158 sitios en 58 modulos**. Nace con baseline "
            "por la misma razon que AP-37 y AP-51: un guard que falla en 158 "
            "sitios se desactiva el primer dia. La baseline solo puede "
            "encoger.\n\n"
            "El guard mide **forma y no flujo**: un dict con `ok: False` y "
            "pinta de envelope que no lleva `error_code`. No sigue el valor "
            "hasta stdout, asi que cuenta tambien envelopes internos que nunca "
            "se imprimen. Eso se declara en vez de esconderse: un guard que "
            "promete una precision que no tiene es la clase de afirmacion no "
            "falsable que AP-37 persigue."
        ),
        "signal": (
            "Un literal `{\"ok\": False, \"error\": ...}` en el camino de "
            "salida de una tool; un envelope de fallo sin `error_code`; un "
            "consumidor que tiene que leer `message` con un regex para saber "
            "que paso."
        ),
        "prevention": (
            "Emitir por `emit_error(tool, CODIGO, mensaje)` y, si el codigo no "
            "existe, anadirlo a `ERROR_CATALOG` \u2014 que es donde vive la "
            "decision de como se recupera ese fallo. Anadir el codigo cuesta "
            "una linea; no anadirlo traslada el coste a cada consumidor, para "
            "siempre. `vault_error_contract --check --strict` mide por AST."
        ),
        "tools_enforcing": ["vault_error_contract"],
        # Como en AP-51, no se lista `vault_norms --audit`: audita el
        # contenido del vault, y esta norma es sobre el codigo de las tools.
        "tools_detecting": ["vault_error_contract"],
        "introduced_version": "v40.2",
    },
    {
        "code": "AP-53",
        "distinguido_de": {
            "AP-13": (
                "AP-13 mide el timestamp del frontmatter contra su propio formato: "
                "inválido o incompleto. AP-53 mide la afirmación histórica contra "
                "git: la fecha es valida y no coincide con el commit. El "
                "discriminador es si hay una fuente externa contra la que contrastar."
            ),
        },
        "name": "El historial se afirma a mano y nadie lo contrasta con git",
        "type": "antipattern",
        "category": "quality",
        "severity": "medium",
        "enforcement": "guard",
        "description": (
            "La documentacion afirma un hecho del historial —que la version "
            "v39.0 la introdujo el commit `00731c6` el 2026-07-25— y ese "
            "hecho vive tambien en git, que es donde de verdad existe. Una de "
            "las dos copias se escribe a mano y ninguna se contrasta con la "
            "otra, asi que la de mano se queda atras sin que nada lo note.\n\n"
            "Es AP-05 aplicada al **historial**, y AP-47 en su forma menos "
            "visible: AP-47 persigue cifras escritas a mano —cuantas tools, "
            "cuantas normas— y una fecha o un hash de commit son la misma "
            "clase de dato derivable, solo que nadie los lee como una cifra.\n\n"
            "Medido en v40.7 sobre el changelog del manifiesto: **55 entradas, "
            "31 con hash real, los 31 existen** —ninguno inventado— y "
            "**5 fechas contradecian al commit que citaban**. Cuatro por un dia; "
            "la de v39.0 por once. Esa entrada arrastra ademas un commit de "
            "fijado que corrigio el hash (`13bf9ca -> 00731c6`) y no toco la "
            "fecha: la correccion parcial es el modo de fallo tipico, porque "
            "quien corrige mira el dato que le fallo y no el que viaja con el.\n\n"
            "Detras hay un huevo y una gallina que conviene nombrar, porque es "
            "lo que empuja a escribir el dato a mano: la entrada tiene que citar "
            "el hash del commit que la contiene, y ese hash no existe hasta que "
            "el commit esta hecho. La salida fue un ritual de dos commits "
            "—`feat: vX` con `git: pending`, luego `docs: fijar hash`— "
            "que aparece ocho veces en las ultimas veinte entradas del "
            "historial y cuyo segundo paso depende de que alguien se acuerde. "
            "Una norma que solo prohibe no sirve aqui: hay que dar el comando "
            "que hace el paso, o se seguira haciendo a mano."
        ),
        "signal": (
            "Un hash de commit, una fecha de release o un nombre de rama "
            "escritos en documentacion sin que ninguna tool los verifique "
            "contra el repositorio; un `pending` publicado en una version ya "
            "cerrada; una fecha que no coincide con la del commit que cita."
        ),
        "prevention": (
            "Derivar el dato del repositorio y comprobarlo en una puerta. "
            "`vault_changelog_check --check --strict` contrasta hash, fecha "
            "—de autoria, `%as`, que un rebase no reescribe—, "
            "`pending` y orden. Y `--fijar-hash` convierte en comando el paso "
            "manual que originaba la divergencia."
        ),
        "tools_enforcing": ["vault_changelog_check"],
        "tools_detecting": ["vault_changelog_check"],
        "introduced_version": "v40.7",
    },
    {
        "code": "AP-54",
        "name": "El lock falla y se escribe igual",
        "type": "antipattern",
        "category": "integrity",
        "severity": "high",
        "enforcement": "guard",
        "description": (
            "Un bloque toma un `file_lock`, no lo consigue, y en el handler "
            "escribe de todos modos sin sincronizar. El razonamiento que lleva "
            "ahi es que perder el dato es peor que escribirlo sin lock. Es al "
            "revés, y por una razón que se ve al leer el `TimeoutError`: ese "
            "error significa que **otro lo tiene tomado ahora mismo**. La "
            "escritura del handler no es una carrera improbable, es la unica "
            "situacion en la que ese codigo llega a ejecutarse, y entra justo "
            "encima de la de quien si consiguio el lock.\n\n"
            "Medido en v40.7 en `vault_sdd_init`, que se pasaba del timeout de "
            "60s de la tool y moria dejando `docs/sdd/` a medio escribir "
            "despues de haber anunciado `Drift status: PASS`. La medida: **26 "
            "tomas del lock del fichero de trazas, 13 fallidas, 65,14s de "
            "espera pura** —13 x 5s exactos—. Esas 13 acababan reescribiendo el "
            "trace sin lock mientras el llamante externo lo estaba "
            "reemplazando.\n\n"
            "La causa de las esperas era distinta de la norma y se corrigio "
            "aparte: `file_lock` no era reentrante, asi que un hilo que volvia "
            "a pedir un lock que el mismo sostenia esperaba el timeout entero "
            "contra si mismo. Conviene separar las dos cosas —la causa se "
            "arregla una vez en el kernel; la reaccion es la que se repite en "
            "cada llamante y la que esta norma vigila.\n\n"
            "Omitir la escritura al fallar el lock **no** es esta norma: es la "
            "respuesta correcta, y `vault_quality_check` ya la tenia."
        ),
        "signal": (
            "Un `except TimeoutError` (o un handler mas amplio) alrededor de un "
            "`with file_lock(...)` cuyo cuerpo contiene una llamada de "
            "escritura; una tool que se pasa de su timeout sin trabajo que lo "
            "justifique; un fichero de indice o de trazas con entradas perdidas."
        ),
        "prevention": (
            "Al fallar el lock, descartar la escritura o propagar el error — "
            "nunca escribir sin sincronizar. `vault_arch --check --strict` "
            "reporta el patron en `unsynced_writes`."
        ),
        "tools_enforcing": ["vault_arch"],
        "tools_detecting": ["vault_arch"],
        "distinguido_de": {
            "AP-58": (
                "AP-54 habla de escrituras sin sincronizar; AP-58, de la "
                "dirección de los imports. No se confunden por el tema sino "
                "por el remedio: los dos se arreglan moviendo una "
                "responsabilidad de sitio, y por eso conviene decir cuál toca. "
                "Un ciclo puede vivir entero dentro de un contexto acotado sin "
                "cruzar ninguna frontera — el componente de 14 módulos está "
                "casi todo dentro del kernel."
            )
        },
        "introduced_version": "v40.7",
    },
    {
        "code": "AP-55",
        "name": "El catálogo de normas se certifica a sí mismo",
        "type": "antipattern",
        "category": "process",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "`NORM_CATALOG` declara por norma qué tools la hacen cumplir "
            "(`tools_enforcing`) y cuáles la detectan (`tools_detecting`). Los "
            "dos campos se escriben a mano y nada los contrasta contra lo que "
            "las tools hacen: la cobertura publicada es una promesa sin "
            "verificar.\n\n"
            "Lo caro no es la lista, es el guard. `vault_voice.coverage()` "
            "existe para detectar normas mudas y comprueba que una norma tenga "
            "`tools_enforcing` o `tools_detecting` **leyendo `tools_enforcing` "
            "y `tools_detecting`**. Verifica el catálogo contra el catálogo, "
            "así que da verde sobre las 47 afirmaciones que ningún módulo "
            "respalda y es estructuralmente incapaz de verlas. Es AP-44 "
            "cometido dentro del guard de AP-43 — la tercera vez que el "
            "criterio de verificación sale del objeto verificado, tras el test "
            "de cruces de v40.8 y el cero de AP-52 medido sobre un subconjunto "
            "en v40.9.\n\n"
            "La forma general: **dos registros canónicos que hablan del mismo "
            "hecho no pueden contradecirse sin que algo falle.** Medido en "
            "v40.10: 54 valores de `tools_*` que mezclaban la tool con su flag "
            "y ningún consumidor podía resolver; AP-22 declarada `critical` "
            "mientras `vault_audit` la penalizaba con 2 puntos por unidad "
            "frente a los 5 de AP-24, que el catálogo llamaba `high`; y 47 "
            "afirmaciones de cobertura sin una línea de código que nombre la "
            "norma. `AP-05` —`critical`— nombra `vault_graph_inspect` como "
            "detector, y esa tool no la menciona en ninguna parte."
        ),
        "signal": (
            "Un valor de `tools_*` que no resuelve contra `mapa_de_grupos()`; "
            "una norma cuya `severity` invierte el orden que "
            "`vault_audit.PENALIZACIONES` aplica dentro de su misma familia; un "
            "módulo declarado enforcer que nunca nombra el código de la norma; "
            "un `distinguido_de` que solo declara una de las dos partes."
        ),
        "prevention": (
            "`vault_norms_coherence --check --strict` cruza el catálogo con el "
            "código y con `PENALIZACIONES`. La traza sin respaldo lleva "
            "baseline que solo puede encoger, y se salda de dos formas "
            "honestas: que el código nombre la norma en el sitio que la "
            "aplica, o que el catálogo deje de afirmar una cobertura que no "
            "tiene. Ampliar la baseline es la tercera y no lo es."
        ),
        "tools_enforcing": ["vault_norms_coherence"],
        "tools_detecting": ["vault_norms_coherence"],
        "distinguido_de": {
            "AP-44": (
                "AP-44 es medir con el propio criterio del objeto medido, en "
                "cualquier tool. AP-55 es su caso en el registro normativo: dos "
                "registros canónicos que afirman cosas distintas sobre el mismo "
                "hecho y nada los cruza. AP-44 se comete al verificar; AP-55 "
                "está en el dato antes de que nadie verifique."
            ),
            "AP-60": (
                "AP-55 mira **con qué criterio** se verifica el catálogo; AP-60, "
                "**a cuántos alcanza** esa verificación. C7 nació de que C5 —una "
                "medida de AP-55 correcta y con criterio ajeno— solo recorría a "
                "las 13 normas que habían declarado algo."
            ),
        },
        "introduced_version": "v40.10",
    },
    {
        "code": "AP-56",
        "name": "Frontmatter presente que el consumidor no puede leer",
        "type": "antipattern",
        "category": "metadata-completeness",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "La nota abre `---`, escribe sus claves y, para `yaml.safe_load`, "
            "no tiene frontmatter: ni id, ni tags, ni tipo, ni estado. El "
            "bloque **se ve** al abrir el fichero, y por eso nadie lo revisa. "
            "El dato parece estar y no está.\n\n"
            "No es AP-28, que es la nota que nunca tuvo bloque y se cuenta "
            "sola. Aquí el hueco es invisible a ojo y solo aparece al medir "
            "con el parser real (AP-44).\n\n"
            "Dos causas, medidas sobre doce notas de cuatro vaults "
            "consumidores: **escalar sin escapar** —`title: Overview: demo` no "
            "es un mapeo, nueve de las doce— y **delimitador sin cerrar**, las "
            "otras tres, donde el bloque nunca se cierra y el parser se traga "
            "la nota entera hasta reventar cientos de líneas más abajo, en un "
            "bloque de código. El mensaje de YAML señala ahí, que no es donde "
            "está el fallo; por eso llevaban meses así.\n\n"
            "v40.2 arregló la prevención: `yaml_scalar` escapa antes de "
            "escribir. Lo que faltaba era la otra mitad — nada reparaba lo que "
            "ya estaba en disco, y `vault_fix_brackets` llevaba versiones "
            "haciendo exactamente eso para AP-22/AP-24."
        ),
        "signal": (
            "`vault_frontmatter_heal` lo cuenta en `unparseable_total`; "
            "`vault_foreign_check` lo publica como `frontmatter_unparseable` "
            "al medir un vault ajeno."
        ),
        "prevention": (
            "Escribir por tool, nunca a mano (SP-04): el write path pasa todo "
            "escalar por `yaml_scalar` desde v40.2. Lo ya escrito se repara "
            "con `vault_frontmatter_heal --apply`, que solo toca las dos "
            "causas mecánicas y se niega a adivinar el resto: completar un "
            "YAML truncado inventa dato, que es peor que el hueco."
        ),
        "tools_enforcing": ["vault_write", "vault_frontmatter_heal"],
        "tools_detecting": ["vault_frontmatter_heal", "vault_foreign_check"],
        "distinguido_de": {
            "AP-28": (
                "AP-28 es la nota sin bloque: el hueco se ve y se cuenta. "
                "AP-56 es la nota con bloque que no parsea, que para toda "
                "métrica es idéntica a AP-28 pero para un humano parece "
                "correcta. Se separan porque solo una de las dos se repara "
                "sin escribir metadatos nuevos."
            )
        },
        "introduced_version": "v40.12",
    },
    {
        "code": "AP-57",
        "name": "Criterio con dueño, reimplementado en la medida",
        "type": "antipattern",
        "category": "architecture",
        "severity": "high",
        "enforcement": "guard",
        "description": (
            "Un **criterio** —qué cuenta como instantánea congelada, qué es "
            "documentación del estándar y no una nota, qué es código y no un "
            "enlace— tiene un dueño canónico en el toolkit, y otro módulo lo "
            "vuelve a decidir por su cuenta con un `if` local.\n\n"
            "No es AP-50, que habla de **patrones regex** y de vocabularios: "
            "aquellos son datos que alguien puede leer y comparar. Un criterio "
            "vive enterrado en una condición, así que la copia sobrevive años "
            "sin que nadie la vea, y el día que el dueño cambia solo cambia el "
            "dueño. `vault_graph_fix` llevaba su propio `skip_set` de "
            "instantáneas y ya divergía de `vault_io.SNAPSHOT_DIRS`; como esa "
            "tool **escribe**, la divergencia no inflaba una métrica: reparaba "
            "dentro de una instantánea, que es dejar de serlo.\n\n"
            "Sale de v40.12: cuatro defectos de `vault_foreign_check` "
            "arreglados en una tanda, los cuatro con la misma forma —el "
            "registro canónico existía y la tool no lo consultaba—. Uno de "
            "ellos tenía el sentido de error peligroso: resolver destinos por "
            "basename ponía la medida **verde** justo donde Obsidian pinta el "
            "enlace roto. La regla 4 pide norma, no cuatro parches."
        ),
        "signal": (
            "Un módulo que clasifica notas escribe una constante distintiva de "
            "otro —`\".history\"`, el nombre del manifiesto, la valla de un "
            "fence— sin importar el símbolo que la posee.\n\n"
            "**Y su forma más cara: la copia al otro lado de una frontera de "
            "lenguaje** (v40.19). Un `.mjs`, un workflow de CI o un `Makefile` "
            "no pueden importar un registro Python, así que reescriben la "
            "decisión — y ningún guard que solo lea `*.py` puede verlo. La CI de "
            "este repo listaba a mano seis puertas de las diecisiete del "
            "registro: once no se ejecutaban en ningún PR, y nada estaba roto. "
            "Una copia a través de una frontera no diverge de golpe; se atrasa."
        ),
        "prevention": (
            "Dos registros en `vault_criterios`. `CRITERIOS_CON_DUENO`: "
            "criterio, dueño, símbolo por el que se consulta y las constantes "
            "que lo delatan. `FRONTERAS`: cada frontera de lenguaje con su "
            "**zona dueña** (clave de `vault_arch.CONTEXTS`), su **norma** "
            "(código de `vault_norms`) y la **pasarela** —el artefacto derivado— "
            "por la que el criterio debe cruzar. Al otro lado la exención no es "
            "importar al dueño, que no se puede: es leer la pasarela.\n\n"
            "`vault_criterios --check --strict` (puerta 15) falla si aparece "
            "una copia nueva; la baseline **solo encoge** y se salda "
            "importando al dueño o leyendo la pasarela, no ampliándola. El "
            "alcance se declara: un fichero ejecutable de otro lenguaje fuera de "
            "toda zona declarada sale como `frontera_no_declarada`, porque un "
            "sitio donde una copia no se vería vale tanto como una copia.\n\n"
            "El límite se declara antes de que nadie se apoye en él: la "
            "detección es **sintáctica**. Un módulo puede reimplementar un "
            "criterio sin repetir ninguna constante y esta medida no lo verá. "
            "Verde no prueba que no haya copias — prueba que no hay copias de "
            "la forma que sabemos reconocer, que es exactamente lo que da un "
            "linter y es preferible a no mirar."
        ),
        "tools_enforcing": ["vault_criterios"],
        "tools_detecting": ["vault_criterios"],
        "distinguido_de": {
            "AP-62": (
                "AP-57 mira el criterio **escrito dos veces**; AP-62 mira el "
                "criterio escrito una sola vez y **leído por la puerta cara**. "
                "El consumidor de AP-62 hace justo lo que AP-57 pide —importar "
                "al dueño en vez de copiar— y aun así paga, porque el dueño "
                "trae el motor detrás. Se saldan al revés: AP-57 juntando el "
                "criterio en un dueño, AP-62 partiendo a ese dueño en catálogo "
                "y motor."
            ),
            "AP-61": (
                "AP-57 es el criterio escrito dos veces sin dueño; AP-61 es una "
                "excepción mal nombrada, que puede darse en un sitio único y sin "
                "copia ninguna. Se cruzan cuando la copia envejece —los doce "
                "sitios corregidos en v40.23 eran las dos cosas a la vez— pero "
                "AP-57 se salda importando al dueño y AP-61 nombrando la "
                "excepción, y un módulo puede quedar limpio de una y no de la otra."
            ),
            "AP-50": (
                "AP-50 es la **decisión duplicada legible**: un vocabulario, "
                "un default de entorno, un regex — dos copias que divergen se "
                "ven al compararlas. AP-57 es su generalización a criterios "
                "enterrados en una condición, donde no hay dato que comparar y "
                "la divergencia solo se nota por el resultado equivocado."
            ),
            "AP-59": (
                "AP-57 habla de un criterio escrito **dos veces** sin dueño; "
                "AP-59, de una **pertenencia afirmada una sola vez** y sin nada "
                "con que contrastarla. No hay copia que comparar: hay una lista "
                "y ninguna medida. Se tocan en el remedio —las dos se cierran "
                "dándole dueño a algo— pero AP-57 se salda importando al dueño "
                "y AP-59 derivando el dato de la forma medida."
            ),
        },
        "introduced_version": "v40.13",
    },
    {
        "code": "AP-58",
        "name": "Ciclo esquivado con un import diferido",
        "type": "antipattern",
        "category": "architecture",
        "severity": "high",
        "enforcement": "guard",
        "description": (
            "Dos módulos se necesitan mutuamente, y en vez de invertir la "
            "dependencia se mete uno de los `import` dentro del cuerpo de una "
            "función. Python deja de quejarse, el ciclo sigue ahí y **deja de "
            "verse**: cualquier medida que mire los imports de nivel de módulo "
            "dirá cero ciclos con toda honestidad.\n\n"
            "Aplicado una vez es una excepción razonable. Aplicado muchas es la "
            "arquitectura, tomada sin decidirla. Medido en v40.17 sobre este "
            "repo: **92 imports diferidos en 40 módulos**, de los cuales 30 "
            "esquivan un ciclo, y contándolos aparece un componente "
            "fuertemente conexo de **14 módulos** que contiene el núcleo "
            "entero. Ese componente es el que hacía que `vault_errors_trace` "
            "—un escritor de trazas de bajo nivel— importase `vault_io` "
            "entero, y el que obliga a `cli/runner.py` a aislar cada tool en "
            "un subproceso para que dos raíces no se contaminen.\n\n"
            "El daño no es el arranque: es que la dirección de la dependencia "
            "deja de ser una decisión revisable. Un ciclo escondido no se "
            "discute en revisión porque no aparece en ninguna medida."
        ),
        "signal": (
            "Un `import` de otro módulo del toolkit escrito dentro de una "
            "función, cuyo destino puede volver al origen siguiendo el grafo "
            "completo de imports."
        ),
        "prevention": (
            "`vault_ciclos --check --strict` (puerta 17) calcula los "
            "componentes fuertemente conexos **contando las aristas "
            "diferidas**, que es la única forma de que la pregunta se pueda "
            "formular. La baseline **solo encoge** y se salda invirtiendo la "
            "dependencia —el módulo de bajo nivel deja de pedirle el módulo "
            "entero al de alto y se le pasa lo que necesita—, no subiendo el "
            "import ni ampliando la baseline.\n\n"
            "Dos límites, dichos antes de que nadie se apoye en el verde. "
            "Primero: solo entran en la deuda los diferidos que **esquivan un "
            "ciclo** (30 de 92); los otros 62 se difieren por coste de "
            "arranque o por dependencia opcional y se publican como "
            "`deferred_benign` sin congelarse, porque una baseline llena de "
            "ruido es una baseline que nadie revisa. Segundo: la medida es del "
            "grafo **estático** de módulos. No ve `importlib`, ni un import "
            "construido con una cadena, ni el acoplamiento que pasa por el "
            "sistema de ficheros o por una variable global compartida."
        ),
        "tools_enforcing": ["vault_ciclos"],
        "tools_detecting": ["vault_ciclos"],
        "distinguido_de": {
            "AP-62": (
                "AP-58 mide una dependencia que **vuelve**: el ciclo. AP-62 "
                "mide una que no vuelve nunca y aun así cuesta, porque el "
                "importador solo quería un dato y se lleva el fan-out entero. "
                "Un repo sin un solo ciclo puede estar lleno de arrastre, y el "
                "remedio de AP-62 —partir el productor— es además una de las "
                "formas de romper un ciclo, que es donde se tocan."
            ),
            "AP-49": (
                "AP-49 mira el **vínculo congelado al importar**: un valor que "
                "se copia en tiempo de import y ya no responde a un reanclaje. "
                "AP-58 mira la **dirección** de la dependencia, no su momento. "
                "Se tocan porque el ciclo del núcleo es lo que obliga a "
                "congelar vínculos, pero un módulo puede tener ciclos sin "
                "vínculos congelados y al revés."
            ),
            "AP-54": (
                "AP-54 habla de cruces de frontera entre contextos acotados, "
                "que pueden ser perfectamente acíclicos. AP-58 habla del ciclo "
                "aunque ocurra dentro de un solo contexto — y el componente de "
                "14 módulos vive casi entero dentro del kernel."
            ),
            "AP-59": (
                "AP-58 mira la **dirección** de las dependencias: quién importa "
                "a quién y si eso vuelve. AP-59 mira **quién está declarado como "
                "fondo de esa pila**. Un repo puede tener cero ciclos y un núcleo "
                "mal declarado, y un núcleo impecable lleno de ciclos."
            ),
        },
        "introduced_version": "v40.17",
    },
    {
        "code": "AP-59",
        "name": "Núcleo declarado sin contraste",
        "type": "antipattern",
        "category": "architecture",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "Un sistema declara cuál es su núcleo —la lista de módulos de los "
            "que todo lo demás depende— y **ninguna medida contrasta esa "
            "afirmación** contra la forma real del grafo. La pertenencia al "
            "core deja de ser un hecho y pasa a ser una costumbre: se hereda de "
            "quien escribió la lista, y envejece en la dirección cómoda.\n\n"
            "Lo caro no es equivocarse de lista: es que **todo lo que se apoya "
            "en ella hereda el error en silencio**. Si un módulo está declarado "
            "como núcleo sin serlo, el guard de fronteras lo exime de reglas que "
            "sí debería cumplir y sale verde. Si uno lo es sin estar declarado, "
            "cada cambio suyo propaga hacia arriba sin que nadie lo trate como "
            "un cambio de núcleo. En ambos casos el verde es correcto respecto a "
            "un mapa equivocado.\n\n"
            "Medido en v40.20 sobre este repo, con la lista **bien elegida** —los "
            "cuatro de cabecera eran los correctos y K1 ya estaba verde—: aun "
            "así, **tres de quince módulos del kernel no se comportan como "
            "núcleo**. `vault_log_error` con fan-in 0, declarado núcleo y sin un "
            "solo consumidor; `vault_io` con fan-out 11 y 30 commits; "
            "`vault_errors` con 14, sobre una mediana de dominio de 9. Ninguno "
            "estaba roto. Ninguno se había visto, porque nadie miraba.\n\n"
            "La norma no exige que el núcleo sea perfecto: exige que su "
            "pertenencia sea **derivable y contrastada**, y que la distancia "
            "entre lo declarado y lo medido se publique en vez de suponerse cero."
        ),
        "signal": (
            "La lista del núcleo se edita a mano y ninguna puerta la lee; un "
            "módulo declarado kernel sin consumidores; un módulo de dominio con "
            "fan-in por encima del escalón de la distribución; el churn del "
            "núcleo por encima de la mediana de lo que sostiene."
        ),
        "prevention": (
            "`vault_kernel --check --strict` (puerta 18) mide tres invariantes. "
            "**K1** —el núcleo no depende del dominio— no se reimplementa: se "
            "delega en `vault_arch.dependencias_del_kernel()`, porque una tool "
            "que mide su propia pureza con su propio criterio es AP-44 cometido "
            "en el sitio que existe para detectarlo. **K2** —fan-in alto, "
            "fan-out bajo— sale del dueño único del grafo de imports "
            "(`vault_grafo_import`), no de un parser propio. **K3** —estabilidad— "
            "del churn de git, y sin historia disponible emite `desconocido` y "
            "nunca `0`: un cero fabricado saldría verde por no haber mirado "
            "(AP-51).\n\n"
            "Los umbrales **se derivan del escalón** de la distribución —la "
            "mayor caída relativa— y se publican en el envelope con su ratio en "
            "cada ejecución. Escribirlos a mano sería AP-47 en la tool que "
            "persigue los números a mano; por eso la baseline congela la "
            "**pertenencia** (qué módulo incumple qué invariante) y no el "
            "umbral, que puede oscilar al crecer el repo.\n\n"
            "Dos límites, dichos antes de que nadie se apoye en el verde. "
            "Primero: mide el grafo **estático** de imports y hereda sus "
            "cegueras (`importlib`, un import por cadena, el acoplamiento por "
            "fichero o por variable global). Segundo: mide **forma, no "
            "propósito**. Un módulo puede tener fan-in altísimo sin ser núcleo "
            "de nada, solo un cajón de utilidades que todo el mundo toca. Verde "
            "significa que la lista declarada no contradice a la forma medida."
        ),
        "tools_enforcing": ["vault_kernel"],
        # `vault_arch` NO se lista aquí aunque mida K1: la delegación va en un
        # solo sentido. `dependencias_del_kernel()` existía antes que la norma y
        # no la nombra, así que declararla detectora sería una cobertura que
        # nadie puede seguir hasta el código — el AP-55 que este catálogo mide.
        "tools_detecting": ["vault_kernel"],
        "distinguido_de": {
            "AP-62": (
                "AP-59 mira la **lista del núcleo** y pregunta si la forma "
                "medida la sostiene. AP-62 mira las **aristas de fuera del "
                "núcleo** y pregunta qué se paga al cruzarlas. Se tocan en la "
                "tentación opuesta: quien quiera bajar la cifra de AP-62 "
                "moviendo el productor al núcleo sin darle forma de hoja se "
                "encuentra con AP-59, y por eso el remedio es partirlo, no "
                "reclasificarlo."
            ),
            "AP-57": (
                "AP-57 habla de un **criterio** escrito dos veces sin dueño. "
                "AP-59 habla de una **pertenencia afirmada y no contrastada**: "
                "no hay copia ninguna, hay una sola lista y nada con qué "
                "compararla. Se tocan en el remedio —los dos se cierran dándole "
                "dueño a algo— pero AP-57 se salda importando al dueño y AP-59 "
                "derivando el dato de la forma medida."
            ),
            "AP-58": (
                "AP-58 mira la **dirección** de las dependencias: quién importa "
                "a quién y si eso vuelve. AP-59 mira **quién está declarado como "
                "fondo de esa pila**. Un repo puede tener cero ciclos y un "
                "núcleo mal declarado, y un núcleo perfecto lleno de ciclos."
            ),
            "AP-47": (
                "AP-47 es la cifra escrita a mano en la documentación. AP-59 es "
                "su versión estructural: la **lista** escrita a mano en el "
                "código. Por eso el remedio comparte disciplina —derivar en vez "
                "de escribir— y por eso los umbrales de esta tool no pueden ser "
                "literales sin cometer AP-47 dentro de AP-59."
            ),
        },
        "introduced_version": "v40.20",
    },
    {
        "code": "AP-60",
        "name": "El guard cobra por declarar y regala el silencio",
        "type": "antipattern",
        "category": "process",
        "severity": "medium",
        "enforcement": "guard+audit",
        "description": (
            "Un guard comprueba una propiedad **iterando sobre quien ya la "
            "declaró**. Quien no declaró nada queda fuera de su alcance, no por "
            "una decisión sino por la forma del bucle. El efecto es un incentivo "
            "invertido: declarar cuesta —obliga a mantener lo declarado, a veces "
            "a editar el otro extremo— y callarse sale gratis y verde.\n\n"
            "Medido en v40.21 sobre C5 de `vault_norms_coherence`: la "
            "comprobación de que dos normas se distinguen recorre "
            "`distinguido_de`, así que solo alcanzaba a **13 normas de 71**. Las "
            "otras 58 no estaban exentas: estaban invisibles. Y declarar una "
            "distinción en AP-59 costó tres ediciones recíprocas y un fallo de "
            "puerta, mientras no declarar ninguna habría salido verde a la "
            "primera.\n\n"
            "Es la misma forma que el repo ya prohíbe en `cobertura_descubierta` "
            "—una norma que declara su hueco no cuenta como deuda nueva, porque "
            "declararse honestamente no puede salir más caro que callarse—, "
            "cometida en el guard que vigila el catálogo donde esa regla está "
            "escrita."
        ),
        "symptoms": (
            "Un guard cuyo bucle empieza por un campo opcional; una medida cuyo "
            "total no puede subir porque el denominador es la lista de quienes "
            "ya hablaron; un envelope que publica cuántos casos revisó y no "
            "cuántos existían."
        ),
        "prevention": (
            "Medir sobre el universo —el catálogo, el registro, el conjunto de "
            "módulos— y no sobre el subconjunto que declaró. Admitir dos salidas "
            "honestas, la declaración y la exención con motivo escrito, y "
            "ninguna tercera: el silencio se cuenta como deuda. La baseline "
            "congela lo que ya estaba y solo encoge; lo que estrena se escribe."
        ),
        "tools_enforcing": ["vault_norms_coherence"],
        "tools_detecting": ["vault_norms_coherence"],
        "distinguido_de": {
            "AP-55": (
                "AP-55 es el catálogo verificándose con el catálogo: el criterio "
                "sale del propio objeto medido. AP-60 no habla del criterio sino "
                "del **alcance**: el criterio puede ser impecable y aun así "
                "aplicarse solo a quien se ofreció voluntario. Un guard puede "
                "medir con criterio ajeno —correcto frente a AP-55— y seguir "
                "recorriendo únicamente a los que declararon."
            ),
            "AP-37": (
                "AP-37 persigue la afirmación **no falsable**: el `ok: true` que "
                "ninguna evidencia podría contradecir. AP-60 persigue la "
                "afirmación falsable pero **parcial**: hay evidencia y se mira, "
                "solo que sobre un subconjunto que se autoselecciona. La primera "
                "no se puede refutar; la segunda se refuta mirando a quien no "
                "aparece en la lista."
            ),
        },
        "introduced_version": "v40.21",
    },
    {
        "code": "AP-61",
        "name": "El guard cae con el dato que vino a medir",
        "type": "antipattern",
        "category": "quality",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "Un handler captura la excepción que una librería **declara** y deja "
            "escapar la que esa librería **lanza de verdad**. El `try` parece "
            "contener el fallo y no lo contiene: la excepción sube entera y "
            "tumba la ejecución completa. Lo caro es la asimetría de alcance — "
            "el dato defectuoso es de una nota, la caída es del barrido entero, "
            "así que un solo fichero hostil deja al vault sin medida.\n\n"
            "El caso que le dio nombre: `RecursionError` **no hereda de "
            "`yaml.YAMLError`**. El parser de PyYAML es recursivo y el "
            "frontmatter es dato externo, así que `x: [[[[[…` —doce caracteres "
            "de escribir— desborda la pila dentro de `safe_load`, por encima de "
            "cualquier `except yaml.YAMLError`. `vault_lib.parse_frontmatter` lo "
            "resolvió y lo dejó escrito; los otros **doce sitios** que habían "
            "copiado el mismo `try` no se enteraron de la corrección, y entre "
            "ellos estaba `vault_foreign_check`, que es la tool de la regla 7 y "
            "por tanto la única que corre contra material que este repo no "
            "generó — exactamente donde el dato hostil aparece.\n\n"
            "Es primo de AP-57 y llega por su camino: un criterio copiado "
            "envejece por su lado, y aquí envejeció hacia el lado que deja caer "
            "la tool."
        ),
        "signal": (
            "Un `except` que nombra la excepción base de una librería alrededor "
            "de una llamada que también lanza `RecursionError`, `MemoryError` o "
            "una excepción de otra jerarquía; una tool que muere entera con un "
            "fichero concreto en vez de contarlo como fichero defectuoso."
        ),
        "prevention": (
            "`vault_excepcion_declarada --check --strict` recorre los `try` cuyo "
            "cuerpo contiene una llamada de riesgo declarada en `RIESGOS` y "
            "exige que la excepción que escapa esté nombrada. Se salda "
            "**delegando en el dueño que ya la contuvo** —para el frontmatter, "
            "`vault_lib.parse_frontmatter`— y solo cuando la firma de retorno lo "
            "impide, nombrándola en la tupla y citando al dueño en un "
            "comentario: ampliar la tupla en trece sitios sin dueño es AP-57 "
            "cometido al arreglar AP-61.\n\n"
            "Límite declarado: solo ve la llamada de riesgo escrita **a la "
            "vista** en el cuerpo del `try`. Un `safe_load` detrás de un helper "
            "queda fuera del alcance, que es la forma correcta de escribirlo — "
            "así que este guard mide mejor el código que peor está escrito, y "
            "eso se publica en vez de suponerse cubierto."
        ),
        "tools_enforcing": ["vault_excepcion_declarada"],
        "tools_detecting": ["vault_excepcion_declarada"],
        "distinguido_de": {
            "AP-51": (
                "Son los dos extremos del mismo eje. AP-51 es el handler "
                "**demasiado ancho**: captura `Exception`, se traga el fallo "
                "propio y devuelve un vacío que nadie distingue de un resultado "
                "legítimo. AP-61 es el handler **demasiado estrecho**: nombra "
                "menos de lo que la llamada lanza, así que no se traga nada — "
                "deja pasar. El discriminador es qué pasa después del fallo: "
                "con AP-51 la tool sigue y miente, con AP-61 la tool cae."
            ),
            "AP-57": (
                "AP-57 es el criterio escrito dos veces sin dueño; AP-61 es una "
                "excepción mal nombrada, que puede darse en un sitio único y sin "
                "copia ninguna. Se cruzan cuando la copia envejece —los doce "
                "sitios de v40.23 eran las dos cosas a la vez— pero AP-57 se "
                "salda importando al dueño y AP-61 se salda nombrando la "
                "excepción, y una tool puede quedar limpia de una y no de la otra."
            ),
        },
        "introduced_version": "v40.23",
    },
    # ── Anti-patrón AP-62 ──────────────────────────────────────────────────────
    {
        "code": "AP-62",
        "name": "El consumidor paga el fan-out del productor",
        "type": "antipattern",
        "category": "architecture",
        "severity": "medium",
        "enforcement": "guard+audit",
        "description": (
            "Un módulo importa a otro **solo para leer un recurso** —una tabla "
            "constante, una función pura— y con el import se lleva todas las "
            "dependencias del productor. Cuando los dos están en contextos "
            "distintos, la arquitectura registra un cruce de frontera de "
            "negocio donde lo único que ocurrió fue **leer un dato**.\n\n"
            "El caso que le dio nombre no se buscó: se tropezó con él en "
            "v40.27. De los veinticuatro importadores de `vault_norms`, "
            "**veintiuno solo querían datos** —`NORM_CATALOG`, `STATUS_VOCAB`, "
            "`status_frontmatter_lines`— y entraban por una fachada que "
            "reexporta el motor de auditoría y sus once dependencias. Mudado el "
            "catálogo a una hoja del núcleo y repuntados los importadores, los "
            "cruces del repo pasaron de **62 a 42** sin que se eliminara una "
            "sola capacidad.\n\n"
            "Lo caro es que **cada sitio, por separado, parece razonable**: "
            "quien escribe `from vault_norms import STATUS_VOCAB` no está "
            "haciendo nada mal, y ningún guard tenía por qué ponerse rojo. El "
            "daño solo existe en el agregado, y por eso hace falta medirlo en "
            "vez de revisarlo — que es la forma exacta que tiene el deterioro "
            "por acumulación."
        ),
        "signal": (
            "Un módulo con fan-out alto cuyos importadores solo le piden "
            "constantes; una fachada que reexporta a la vez el catálogo y el "
            "motor que lo consume; un cruce de contexto cuya única razón de ser "
            "es un `from X import UNA_CONSTANTE`."
        ),
        "prevention": (
            "`vault_recursos --check --strict` clasifica cada arista del grafo "
            "y cuenta como deuda la que cumple las cuatro condiciones: el "
            "destino no está en el núcleo, tiene fan-out mayor que cero, todo "
            "lo que el origen le pide es recurso, y los dos están en contextos "
            "distintos. `--ranking` ordena los productores por cuántos cruces "
            "colapsaría mudar cada uno, que es lo que convierte la medida en un "
            "plan.\n\n"
            "Se salda **dándole al recurso un dueño con forma de hoja**: partir "
            "el productor en catálogo y motor, y repuntar a los consumidores al "
            "dueño. La lección de v40.27 es que **partir el fichero por sí solo "
            "no mueve una sola cifra** — la arquitectura no cambia hasta que "
            "los importadores dejan de entrar por la fachada.\n\n"
            "Límites declarados: mide `from X import y` y no `import X`, porque "
            "quien importa el módulo entero no declara qué usa; decide la "
            "pureza por AST a punto fijo, así que una función que dependa de un "
            "global mutable pasará por pura; y da las clases por acopladas sin "
            "mirarlas, prefiriendo no contar un sitio a contar uno que no lo es."
        ),
        "tools_enforcing": ["vault_recursos"],
        "tools_detecting": ["vault_recursos", "vault_arch"],
        "distinguido_de": {
            "AP-57": (
                "AP-57 es el criterio escrito dos veces sin dueño; AP-62 es el "
                "criterio con un dueño perfectamente claro al que se llega por "
                "el camino caro. Son opuestos en el síntoma: AP-57 aparece "
                "cuando alguien **no** importó al dueño y reimplementó, AP-62 "
                "cuando sí lo importó y el dueño estaba envuelto en un módulo "
                "que arrastra. Y por eso la corrección de AP-62 no puede ser "
                "copiar el recurso al consumidor: eso lo cambia por un AP-57."
            ),
            "AP-58": (
                "Los dos hablan de imports, pero AP-58 mide el **ciclo** —el "
                "destino vuelve al origen— y AP-62 mide el **peso** —el destino "
                "arrastra más de lo que hacía falta—. Un arrastre puede no "
                "cerrar ningún ciclo y seguir siendo deuda, y un ciclo puede "
                "darse entre dos módulos que se piden justo lo que necesitan. "
                "Se cruzan al saldarlos: mudar el recurso a una hoja rompió de "
                "paso quince ciclos diferidos en v40.27, y ese efecto fue una "
                "consecuencia medida, no el objetivo."
            ),
            "AP-59": (
                "AP-59 vigila la **forma del núcleo**: que lo declarado núcleo "
                "lo parezca al medirlo. AP-62 vigila **quién paga por quién** "
                "fuera de él. Se necesitan mutuamente y en direcciones "
                "opuestas: la corrección típica de AP-62 es mudar un recurso al "
                "núcleo, y AP-59 es lo único que impide que esa mudanza sea una "
                "reclasificación de conveniencia para bajar la cifra."
            ),
        },
        "introduced_version": "v40.28",
    },
    # ── Patrón PAT-6 ───────────────────────────────────────────────────────────
    {
        "code": "PAT-6",
        "distinguido_de": {
            "AP-31": (
                "AP-31 es el defecto: aristas sin predicate. PAT-6 es el patrón que "
                "lo cierra: enriquecimiento semántico periodico del grafo. Saldar "
                "AP-31 una vez no basta si PAT-6 no se ejecuta; PAT-6 sin AP-31 "
                "pendiente sigue siendo útil."
            ),
        },
        "name": "Semantic graph enrichment — enriquecimiento periodico del grafo",
        "type": "pattern",
        "category": "linking",
        "severity": "N/A",
        "enforcement": "recommended",
        "description": (
            "Ejecutar vault_graph --typed al final de cada sesion productiva para "
            "generar graph-enriched.json con predicates semanticos unificados. "
            "El grafo enriquecido combina wiki-links, entity relations y code relations "
            "en un solo grafo consultable con filtros por predicate, cardinalidad "
            "y tipo de nodo. Esto habilita busquedas de conocimiento semanticas "
            "y analisis de impacto con tipos."
        ),
        "signal": "graph-enriched.json existe y tiene updated_at < 24 horas.",
        "prevention": (
            "N/A — es el patron correcto. Agregar vault_graph --typed al session "
            "protocol como paso automatico antes de vault_audit."
        ),
        "tools_enforcing": [],
        "tools_detecting": [],
        "tools_del_patron": ["vault_graph_merge", "vault_audit"],
        "introduced_version": "v37",
    },
    # ── Protocolo de sesión SP-XX ──────────────────────────────────────────────
    {
        "code": "SP-01",
        "distinguido_de": {
            "SP-03": (
                "SP-01 protege el borrado concreto: no se elimina sin `change_log` "
                "previo. SP-03 protege la tanda: no se opera en masa sin snapshot. El "
                "discriminador es el alcance —una nota frente a una operación— y por "
                "eso un borrado masivo exige los dos."
            ),
        },
        "name": "Delete protocol — change_log obligatorio antes de eliminar",
        "type": "antipattern",
        "category": "session-protocol",
        "severity": "critical",
        "enforcement": "audit",
        "description": (
            "Antes de eliminar cualquier nota del vault, el agente DEBE llamar: "
            "vault_change_log --action deleted --path <nota> --reason <motivo>. "
            "Sin este registro, la nota desaparece sin rastro auditado."
        ),
        "signal": "Nota eliminada que no aparece en 00_System/.change-log.json con action: deleted.",
        "prevention": (
            "Regla de gobernanza: verificar en .change-log.json antes de delete. "
            "Si no hay entrada → llamar vault_change_log primero, luego eliminar."
        ),
        "tools_enforcing": ["vault_change_log"],
        "tools_detecting": ["vault_norms"],
        "introduced_version": "v30",
    },
    {
        "code": "SP-02",
        "distinguido_de": {
            "AP-14": (
                "AP-14 es el defecto ya escrito: el link roto está en el vault. SP-02 "
                "es el protocolo que lo evita —buscar el destino antes de escribir el "
                "enlace—. Una se detecta auditando; la otra se cumple o no en el "
                "momento de escribir, y su incumplimiento solo se ve como AP-14 más "
                "tarde."
            ),
        },
        "name": "Forward-link verification — buscar antes de linkar",
        "type": "antipattern",
        "category": "session-protocol",
        "severity": "high",
        "enforcement": "guard",
        "description": (
            "Antes de escribir [[nombre-nota]] en contenido, verificar que la nota destino "
            "ya existe: vault_search(query:'nombre-nota'). Si no hay resultado, escribir "
            "en texto plano hasta que la nota exista. "
            "vault_write advierte con ghost_links[] (no bloquea) si el target no existe."
        ),
        "signal": "vault_write retorna ghost_links[] en la respuesta de éxito.",
        "prevention": "vault_search() antes de cada [[wiki-link]] nuevo. No crear links especulativos.",
        "tools_enforcing": ["vault_write"],
        "tools_detecting": ["vault_graph", "vault_audit"],
        "introduced_version": "v30",
    },
    {
        "code": "SP-03",
        "distinguido_de": {
            "PAT-4": (
                "PAT-4 ordena la auditoría en fases para que un fallo no invalide "
                "todo el recorrido. SP-03 exige el snapshot delta antes de una "
                "operación masiva, para poder decir después que cambio. Uno "
                "estructura el trabajo; el otro conserva la evidencia de lo que hizo."
            ),
            "SP-01": (
                "SP-01 protege el borrado concreto: no se elimina sin `change_log` "
                "previo. SP-03 protege la tanda: no se opera en masa sin snapshot. El "
                "discriminador es el alcance —una nota frente a una operación— y por "
                "eso un borrado masivo exige los dos."
            ),
        },
        "name": "Session snapshot pattern — delta antes de operaciones masivas",
        "type": "antipattern",
        "category": "session-protocol",
        "severity": "medium",
        "enforcement": "audit",
        "description": (
            "Antes de cualquier operación masiva (migración, rename en lote, vault_tags --rename "
            "múltiple, delete en lote), capturar snapshot con vault_delta --snapshot. "
            "Permite detectar regresiones y calcular impacto real de la operación."
        ),
        "signal": "Operación masiva sin snapshot previo → no hay baseline para detectar regresiones.",
        "prevention": (
            "PAT-4 (phased audit): snapshot → operación → vault_audit() → comparar score. "
            "vault_delta --snapshot antes de cada sesión con cambios masivos."
        ),
        "tools_enforcing": [],
        # `vault_backup` copia el vault entero; el snapshot que SP-03 pide —y que
        # su propia descripción nombra— lo toma `vault_delta --snapshot`, que es
        # además quien luego calcula el delta contra él.
        "tools_detecting": ["vault_delta"],
        "introduced_version": "v30",
    },
    # ── Convenciones de nomenclatura CN-XX ────────────────────────────────────
    {
        "code": "CN-01",
        "distinguido_de": {
            "CN-02": (
                "Las dos son convenciones de ubicación y nombre. CN-01 rige el nombre "
                "del fichero —minúsculas con guiones—; CN-02 rige el destino —las "
                "secciones numeradas—. Un fichero bien nombrado en la carpeta "
                "equivocada incumple solo CN-02."
            ),
        },
        "name": "Kebab-case filenames — nombres de archivo en minúsculas con guiones",
        "type": "antipattern",
        "category": "convention",
        "severity": "high",
        "enforcement": "guard",
        "description": (
            "Los archivos .md del vault deben usar kebab-case: minúsculas, palabras separadas "
            "por guiones, sin espacios ni caracteres especiales. "
            "vault_write aplica slugify() automáticamente al título para generar el filename. "
            "Ej: 'ADR-001 Auth Decision' → adr-001-auth-decision.md."
        ),
        "signal": "Archivos con espacios, mayúsculas o caracteres especiales en el nombre.",
        "prevention": "Siempre usar vault_write para crear notas. Nunca crear archivos .md directamente.",
        "tools_enforcing": ["vault_write"],
        # Ninguna tool audita los nombres de fichero ya escritos: `vault_validate`
        # no los mira. El guard de escritura sí existe (`slugify`), y por eso el
        # enforcement es `guard` y no `guard+audit`.
        "tools_detecting": [],
        "introduced_version": "v30",
    },
    {
        "code": "CN-02",
        "distinguido_de": {
            "AP-09": (
                "CN-02 es la convención general de destino: las secciones numeradas "
                "son los únicos sitios válidos. AP-09 es su incumplimiento con nombre "
                "para un tipo concreto: los runbooks fuera de la estructura. Se "
                "separa porque el runbook tiene además exigencias de contenido que "
                "CN-02 no mira."
            ),
            "AP-15": (
                "CN-02 es la nota colocada en una carpeta que no toca, dentro del "
                "esquema. AP-15 es el fichero externo depositado en la raíz del "
                "vault, que ni siquiera es una nota. El discriminador es si el "
                "fichero forma parte del material del vault."
            ),
            "CN-01": (
                "Las dos son convenciones de ubicación y nombre. CN-01 rige el nombre "
                "del fichero —minúsculas con guiones—; CN-02 rige el destino —las "
                "secciones numeradas—. Un fichero bien nombrado en la carpeta "
                "equivocada incumple solo CN-02."
            ),
        },
        "name": "Numbered folder structure — secciones numeradas como únicos destinos",
        "type": "antipattern",
        "category": "convention",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "Solo las secciones numeradas del registro canónico (vault_registry.SECTIONS, "
            "fuente de verdad única — PAT-1) son destinos válidos para notas. "
            "Crear carpetas ad-hoc o escribir en la raíz viola este estándar (ver AP-15). "
            "NO duplicar la lista aquí: consultarla con vault_folder_registry o vault_registry."
        ),
        "signal": "Carpeta con nombre que no sigue el patrón NN_Nombre en el vault.",
        "prevention": "Elegir la sección más apropiada del vocabulario estándar. AP-15 para raíz del vault.",
        "tools_enforcing": ["vault_write"],
        "tools_detecting": ["vault_section_index", "vault_norms"],
        "introduced_version": "v30",
    },
    {
        "code": "CN-03",
        "distinguido_de": {
            "AP-29": (
                "CN-03 exige que el valor de `status` esté en el vocabulario "
                "canónico; AP-29 exige que el campo exista. El discriminador es "
                "presencia frente a valor: una nota sin `status` es AP-29 y no puede "
                "ser CN-03."
            ),
            "AP-41": (
                "CN-03 mira el valor aislado: pertenece al vocabulario. AP-41 mira la "
                "transición: la máquina de estados está declarada y nadie verifica "
                "que los saltos entre valores sean legales. Todos los valores pueden "
                "ser válidos y la secuencia imposible."
            ),
        },
        "name": "Standard status vocabulary — vocabulario canónico de meta.status",
        "type": "antipattern",
        "category": "convention",
        "severity": "low",
        "enforcement": "audit",
        "description": (
            "El campo meta.status (o status en frontmatter) debe usar solo valores de "
            "vault_norms.STATUS_VOCAB (fuente única, v38 — unifica el vocabulario CN-03 "
            "original con el ciclo de vida del spec §status): planned | draft | in-progress | "
            "reviewed | approved | implemented | verified | deprecated | obsolete | archived | "
            "stub | template. Valores fuera del vocabulario rompen filtros de vault_list y vault_audit."
        ),
        "signal": "vault_list filtra por status y retorna 0 cuando el valor es no-estándar.",
        "prevention": "Usar solo valores de STATUS_VOCAB. vault_norms --audit los valida (CN-03).",
        "tools_enforcing": [],
        "tools_detecting": ["vault_norms"],
        "introduced_version": "v30",
    },
]

# Índice rápido por código
_NORM_BY_CODE: Dict[str, Dict[str, Any]] = {n["code"]: n for n in NORM_CATALOG}


def norma_por_codigo(code: str) -> Dict[str, Any] | None:
    """La norma con ese código, o `None`.

    El puerto público del índice. `vault_code_tag` —que es del contexto de
    grafo— venía importando `_NORM_BY_CODE` directamente: un nombre privado
    atravesando una frontera, que es lo contrario de una superficie publicada.
    El dict sigue existiendo para uso interno de este módulo; lo que cambia es
    que quien viene de fuera entra por aquí.
    """
    return _NORM_BY_CODE.get(code)

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "N/A": 4}
_CATEGORY_ORDER = {
    "linking": 0,
    "content-quality": 1,
    "structure": 2,
    "frontmatter": 3,
    "process": 4,
    "session-protocol": 5,
    "convention": 6,
}



# Vocabulario canónico de meta.status (CN-03) — unificado v38.
# Antes existían DOS vocabularios contradictorios: CN-03 (7 valores) y el
# ciclo de vida del spec §status (draft→reviewed→approved→implemented→
# verified→obsolete). Este set es la unión canónica; CN-03 y el spec
# referencian este símbolo como fuente única.
STATUS_VOCAB = {
    "planned",
    "draft",
    "in-progress",
    "reviewed",
    "approved",
    "implemented",
    "verified",
    "deprecated",
    "obsolete",
    "archived",
    "stub",
    "template",
}

# ─── Registro de lifecycles ──────────────────────────────────────────────────
#
# El catálogo de máquinas de estado vivía escrito a mano dentro de
# `vault_sdd_init.generate_state_machines`, en una cadena constante, y llevaba
# tiempo mintiendo: daba el ciclo de la versión del estándar como «v19 → … →
# v36» estando el repo en v39.5, y el de las tools como
# `active/deprecated/internal/meta/removed` cuando los estados que el tool-spec
# usa de verdad son `active/archived/internal`. Dos de trece filas incorrectas en
# el documento cuyo trabajo entero es describir las máquinas de estado.
#
# El orden que fija CLAUDE.md es registro primero y doc después, así que la tabla
# se declara aquí —junto a STATUS_VOCAB, que es la otra verdad sobre estados— y
# el generador del SDD la deriva. Las dos filas que sí tienen fuente viva
# (versión del estándar, estados de tool) se resuelven en tiempo de generación
# contra esa fuente, no se copian.
LIFECYCLE_REGISTRY = [
    {"entity": "Nota", "entity_en": "Note",
     "states": ["active", "archived", "deleted"], "tool": "vault_change_log"},
    {"entity": "Patrón", "entity_en": "Pattern",
     "states": ["planificado", "en_progreso", "implementado", "deprecado", "refactoring"],
     "tool": "vault_pattern_save"},
    {"entity": "Requisito", "entity_en": "Requirement",
     "states": ["draft", "reviewed", "approved", "implemented", "verified", "obsolete"],
     "tool": "vault_requirement_save"},
    {"entity": "Test", "entity_en": "Test",
     "states": ["not_run", "pass", "fail", "blocked", "skip"], "tool": "vault_test_save"},
    {"entity": "Ejecución de runbook", "entity_en": "Runbook execution",
     "states": ["success", "failed", "partial"], "tool": "vault_runbook_log"},
    {"entity": "Incidente", "entity_en": "Incident",
     "states": ["detected", "investigating", "identified", "mitigating", "resolved",
                "closed", "post-mortem"], "tool": "vault_incident_save"},
    {"entity": "Consumo de SLO", "entity_en": "SLO burn",
     "states": ["healthy", "1h-burn", "6h-burn", "30d-burn", "breached"],
     "tool": "vault_slo_save"},
    {"entity": "Tratamiento de riesgo", "entity_en": "Risk treatment",
     "states": ["accept", "mitigate", "transfer", "avoid"], "tool": "vault_risk_save"},
    {"entity": "NCR", "entity_en": "NCR",
     "states": ["open", "closed"], "tool": "vault_ncr_save"},
    {"entity": "Backup", "entity_en": "Backup",
     "states": ["active", "superseded"], "tool": "vault_backup_list"},
    {"entity": "Propagación pendiente", "entity_en": "Propagation pending",
     "states": ["pending", "reviewed"], "tool": "vault_propagate"},
    # `states: None` = se resuelve contra la fuente viva al generar la doc.
    {"entity": "Ciclo de vida de una tool", "entity_en": "Tool lifecycle",
     "states": None, "source": "tool_spec_status", "tool": "vault_mcp_catalog"},
    {"entity": "Versión del estándar", "entity_en": "Standard version",
     "states": None, "source": "standard_version", "tool": "vault_standard_upgrade"},
]


# ─── Sinónimos de estado (AP-38) ─────────────────────────────────────────────
#
# CN-03 lleva desde v38 declarando el vocabulario y auditándolo. Un censo sobre
# 17 vaults reales (2.929 notas) mostró el resultado de auditar sin normalizar:
# **54 valores distintos de `status`, de los cuales solo el 6% caía dentro del
# vocabulario** — y de los 12 canónicos únicamente 4 llegaron a usarse. Los más
# frecuentes eran inventados: `implementado` (205 notas), `active` (60),
# `activo` (53), `accepted` (45), `fixed` (31).
#
# La lección del censo no es que los agentes escriban mal: es que un vocabulario
# que solo se audita *después* de escribir no gobierna nada, porque nadie
# ejecuta el audit — `vault_norms` no aparece ni una vez en las 1.356
# ejecuciones registradas del parque. Por eso este mapa se aplica en la
# escritura, no en la revisión.
#
# Cubre español e inglés porque el parque los mezcla en la misma nota.
STATUS_SYNONYMS = {
    # activo / en curso
    "active": "in-progress",
    "activo": "in-progress",
    "en_desarrollo": "in-progress",
    "en-desarrollo": "in-progress",
    "in_progress": "in-progress",
    "en_progreso": "in-progress",
    "refactoring": "in-progress",
    "wip": "in-progress",
    "investigating": "in-progress",
    "investigado": "in-progress",
    "open": "in-progress",
    "abierto": "in-progress",
    "identificado": "in-progress",
    "pendiente_accion": "in-progress",
    # planificado
    "planificado": "planned",
    "pendiente": "planned",
    "deferred": "planned",
    "proposed": "planned",
    "propuesto": "planned",
    # aprobado
    "accepted": "approved",
    "aceptado": "approved",
    "aceptada": "approved",
    "amended": "approved",
    # implementado
    "implementado": "implemented",
    "implementada": "implemented",
    "completado": "implemented",
    "completada": "implemented",
    "completed": "implemented",
    "complete": "implemented",
    "documentacion_completada": "implemented",
    "documented": "implemented",
    "documentado": "implemented",
    "en_produccion": "implemented",
    "operativo": "implemented",
    "estable": "implemented",
    "vigente": "implemented",
    # verificado
    "fixed": "verified",
    "corregido": "verified",
    "resuelto": "verified",
    "resolved": "verified",
    "validated": "verified",
    "validado": "verified",
    "mitigado": "verified",
    "mitigated": "verified",
    "prevenido": "verified",
    "pass": "verified",
    "implemented-and-validated": "verified",
    # retirado
    "deprecado": "deprecated",
    "deprecada": "deprecated",
    "obsoleto": "obsolete",
    "obsoleta": "obsolete",
    # histórico
    "historical": "archived",
    "archivo-historico": "archived",
    "archivo-histórico": "archived",
    "offline": "archived",
    "no-bug": "archived",
}

#: Sufijos que un estado arrastra y que NO son parte del estado: progreso
#: parcial, versión en que se resolvió, fecha de corrección. El censo los
#: encontró incrustados en el propio campo (`1-fixed-6-pending`, `all-fixed`,
#: `resuelto (v0.58)`, `aceptada (corregida 2026-05-11)`, `mayormente_corregido`).
#: Se extraen a `status_note` en vez de perderse: no-derogación aplicada al dato.
STATUS_QUALIFIERS = {
    "mayormente_corregido": ("verified", "corrección parcial"),
    "partial": ("in-progress", "parcial"),
    "all-fixed": ("verified", "all-fixed"),
    "not_run": ("planned", "not_run"),
}

#: Transiciones permitidas del ciclo de vida. Un estado que no puede alcanzarse
#: desde ninguno otro es inalcanzable, y uno del que no se sale es terminal.
#: `stub` y `template` no participan del ciclo: son marcas de naturaleza de la
#: nota, no fases de su vida.
STATUS_TRANSITIONS = {
    "planned": {"draft", "in-progress", "archived"},
    "draft": {"in-progress", "reviewed", "archived"},
    "in-progress": {"draft", "reviewed", "implemented", "archived"},
    "reviewed": {"approved", "draft", "archived"},
    "approved": {"implemented", "deprecated", "archived"},
    "implemented": {"verified", "deprecated", "archived"},
    "verified": {"deprecated", "obsolete", "archived"},
    "deprecated": {"obsolete", "archived"},
    "obsolete": {"archived"},
    "archived": set(),
    "stub": {"draft", "in-progress", "archived"},
    "template": {"archived"},
}


#: Vocabularios de dominio (AP-38).
#:
#: El censo del parque atribuía los 54 estados a agentes descuidados. Falso: el
#: valor no canónico más frecuente, `implementado` (205 notas), lo escribe
#: `vault_pattern_save`, que trae su propio vocabulario y su propia máquina de
#: transiciones. El estándar publicaba **nueve** vocabularios de `status` en
#: competencia — AP-05 dentro del propio toolkit. Un agente que escribía
#: `implementado` estaba obedeciendo a la tool, no ignorándola.
#:
#: La corrección no es borrar esos vocabularios: `pass` de un test o `P2` de un
#: incidente son información real que `verified` no expresa. Son **otro eje**.
#: Así que `status` queda reservado al ciclo de vida de la nota, canónico, y
#: cada dominio conserva su vocabulario íntegro en su propio campo. Las flags de
#: CLI no cambian: lo que cambia es en qué campo aterriza el valor.
#:
#: Formato: `tool -> (campo_de_dominio, {valor_de_dominio: status_canonico})`.
DOMAIN_STATUS_VOCABS = {
    "vault_pattern_save": ("pattern_state", {
        "planificado": "planned",
        "en_progreso": "in-progress",
        "implementado": "implemented",
        "deprecado": "deprecated",
        "refactoring": "in-progress",
    }),
    "vault_bug_save": ("bug_state", {
        "open": "in-progress",
        "confirmed": "in-progress",
        "in_fix": "in-progress",
        "fixed": "verified",
        "wont_fix": "approved",
        "duplicate": "obsolete",
    }),
    "vault_test_save": ("test_result", {
        "not_run": "planned",
        "pass": "verified",
        "fail": "implemented",
        "blocked": "in-progress",
        "skip": "draft",
    }),
    "vault_incident_save": ("incident_state", {
        "detected": "in-progress",
        "investigating": "in-progress",
        "identified": "in-progress",
        "mitigating": "in-progress",
        "resolved": "verified",
        "closed": "archived",
        "post-mortem": "reviewed",
    }),
    "vault_ncr_save": ("ncr_state", {
        "open": "in-progress",
        "in_progress": "in-progress",
        "pending_verification": "reviewed",
        "closed": "archived",
        "cancelled": "obsolete",
    }),
    "vault_risk_save": ("risk_state", {
        "open": "in-progress",
        "in_treatment": "in-progress",
        "accepted": "approved",
        "closed": "archived",
    }),
    "vault_release_save": ("release_state", {
        "planned": "planned",
        "in_progress": "in-progress",
        "deployed": "implemented",
        "rolled_back": "deprecated",
        "cancelled": "obsolete",
    }),
    "vault_privacy_save": ("privacy_state", {
        "active": "implemented",
        "under_review": "reviewed",
        "deprecated": "deprecated",
        "closed": "archived",
    }),
    # El comentario de vault_preferences decía "alineado con STATUS_VOCAB" y sus
    # dos únicos valores estaban fuera. Una afirmación falsa desde que se
    # escribió, y nadie podía verla porque no había guard que la comprobara.
    "vault_preferences": ("preference_state", {
        "active": "implemented",
        "revoked": "deprecated",
    }),
    # `--status` de infra es texto libre y nunca tuvo validación: es la única
    # de las nueve que no publicaba vocabulario, así que aceptaba cualquier
    # cosa. Se le da uno; lo que no encaje sigue cayendo en `normalize_status`.
    "vault_infra_save": ("infra_state", {
        "active": "implemented",
        "activo": "implemented",
        "provisioning": "in-progress",
        "degraded": "in-progress",
        "decommissioned": "archived",
        "offline": "archived",
    }),
    "vault_project_status": ("project_state", {
        "en_desarrollo": "in-progress",
        "en_revision": "reviewed",
        "bloqueado": "in-progress",
        "completado": "implemented",
        "archivado": "archived",
        "en_produccion": "implemented",
    }),
}


def split_domain_status(tool, raw):
    """Separa el eje de dominio del ciclo de vida de la nota.

    Devuelve `(status_canonico, campo_dominio, valor_dominio)`. El valor de
    dominio se devuelve intacto — se conserva, no se traduce. Si la tool no
    tiene vocabulario propio, o el valor no está en él, cae en
    `normalize_status` y no se emite campo de dominio.
    """
    entrada = DOMAIN_STATUS_VOCABS.get(tool)
    if entrada and raw in entrada[1]:
        campo, mapa = entrada
        return mapa[raw], campo, raw
    canonico, _nota, _regla = normalize_status(raw)
    return canonico, None, None


def status_frontmatter_lines(tool, raw):
    """Las líneas de frontmatter que corresponden a un estado de dominio.

    Devuelve siempre `status:` canónico primero y, si aplica, el campo de
    dominio detrás. Que las 8 tools con vocabulario propio llamen aquí es lo que
    impide que vuelvan a divergir: el orden y los nombres de campo salen de un
    único sitio.
    """
    if raw is None:
        return []
    canonico, campo, valor = split_domain_status(tool, raw)
    if canonico is None:
        raise ValueError(
            f"{tool}: status {raw!r} no pertenece a su vocabulario de dominio "
            f"ni al canónico (CN-03)"
        )
    lineas = [f"status: {canonico}"]
    if campo:
        lineas.append(f"{campo}: {valor}")
    return lineas


def normalize_status(raw):
    """Lleva un `status` cualquiera al vocabulario canónico.

    Devuelve `(canonico, nota, regla)`:

      - `canonico` es un valor de `STATUS_VOCAB`, o `None` si no se pudo decidir
        — y entonces quien llama **rechaza**, no adivina. Inventar un estado es
        peor que no tenerlo: uno se detecta, el otro se hereda.
      - `nota` recoge lo que el valor original arrastraba y no era estado
        (progreso, versión, fecha). Nunca se descarta.
      - `regla` dice por qué se decidió: `canonical`, `synonym`, `qualifier`,
        `parenthetical` o `unknown`. Sirve para auditar la propia normalización.
    """
    if raw is None:
        return None, None, "unknown"

    original = str(raw).strip()
    if not original:
        return None, None, "unknown"

    # Un paréntesis o guion largo suele traer la circunstancia, no el estado:
    # "resuelto (v0.58)" es `verified` con una nota, no un estado nuevo.
    nota = None
    # El prefiltro barato va antes a propósito. `(.*?)\s*` delante de un
    # delimitador que **no está** hace al motor probar cada punto de corte:
    # 10.000 espacios sin paréntesis tardan 417 ms en decir que no. Preguntar
    # primero si hay delimitador cuesta una pasada lineal y evita el caso malo
    # entero, que es además el único que un valor hostil puede provocar.
    if any(c in original for c in "([—-"):
        m = re.match(r"^(.*?)\s*[\(\[—-]\s*(.+?)[\)\]]?$", original)
    else:
        m = None
    base = original
    if m and m.group(1).strip():
        candidato_base, candidato_nota = m.group(1).strip(), m.group(2).strip()
        if _canonical_status(candidato_base) is not None:
            base, nota = candidato_base, candidato_nota

    clave = base.lower().replace(" ", "_").replace("__", "_")

    if clave in STATUS_QUALIFIERS:
        canonico, cualificador = STATUS_QUALIFIERS[clave]
        return canonico, nota or cualificador, "qualifier"

    directo = _canonical_status(base)
    if directo is not None:
        regla = "parenthetical" if nota else (
            "canonical" if directo == base.lower() else "synonym"
        )
        return directo, nota, regla

    # "1-fixed-6-pending" y similares: un informe de progreso en el campo de
    # estado. No hay estado que deducir sin mentir, pero el dato se conserva.
    return None, original, "unknown"


def _canonical_status(valor):
    clave = str(valor).strip().lower().replace(" ", "_")
    if clave in STATUS_VOCAB:
        return clave
    guion = clave.replace("_", "-")
    if guion in STATUS_VOCAB:
        return guion
    if clave in STATUS_SYNONYMS:
        return STATUS_SYNONYMS[clave]
    if guion in STATUS_SYNONYMS:
        return STATUS_SYNONYMS[guion]
    return None


def compute_norm_refs(folder: str, content: str, wiki_links: List[str]) -> List[str]:
    """Las normas que aplican a una nota, deducidas de su carpeta y su cuerpo.

    Vive aquí y no en la fachada (v40.27) porque es **derivación de catálogo**:
    no lee el vault, no escribe nada y su única dependencia es `re`. Estaba
    arriba por herencia del fichero único, y eso costaba nueve cruces de
    contexto — nueve tools de Autoría importando `vault_norms`, y con él la
    fachada que reexporta el motor entero, para pedir una lista de códigos.

    Reglas:
      - universales:             AP-11, AP-12, AP-13, AP-16, CN-01, CN-02, SP-01
      - hay wikilinks:           + AP-14, AP-21, AP-22, SP-02
      - hay viñetas:             + AP-20
      - carpeta 03_Decisions/:   + AP-07
      - más de 500 líneas:       + AP-23 (informativa)
    """
    refs: set = {"AP-11", "AP-12", "AP-13", "AP-16", "CN-01", "CN-02", "SP-01"}

    if wiki_links:
        refs.update({"AP-14", "AP-21", "AP-22", "SP-02"})

    bullets = re.findall(r"^\s*[-*]\s*(.*)", content, re.MULTILINE)
    if bullets:
        refs.add("AP-20")

    folder_lower = folder.lower()
    if folder_lower.startswith("03_decisions") or "decisions" in folder_lower:
        refs.add("AP-07")

    if len(content.split("\n")) > 500:
        refs.add("AP-23")

    return sorted(refs)
