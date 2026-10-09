#!/usr/bin/env python3
"""
vault_registry.py — Fuente de verdad única para estructura del vault.

Centraliza:
  1. SECTIONS     — secciones canónicas ordenadas (nombre, descripción, tool hint)
  2. SUBFOLDERS   — subcarpetas con descripción y tool owner (previene colisiones)
  3. Helpers      — funciones de acceso para cada consumidor

Principio DRY: ningún otro script declara esta información.
Los consumidores importan desde aquí:
  - vault_section_index.py  → section_description(), subsection_description(), section_tool_hint()
  - vault_master_index.py   → ORDERED_SECTIONS, section_name(), section_description()
  - vault_standard_upgrade.py → standard_folders()
  - vault_spec_validate.py  → folder_owner(), check_folder_ownership()

NO importa de vault_io ni de ningún otro vault_* — importar desde aquí
nunca crea dependencias circulares.
"""

import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional

# ──────────────────────────────────────────────────────────────────────────────
# Secciones canónicas — orden, nombre y descripción
# ──────────────────────────────────────────────────────────────────────────────
#
# Fuente de verdad para:
#   - vault_master_index.py   (ORDERED_SECTIONS, SECTION_NAMES)
#   - vault_section_index.py  (SECTION_DESCRIPTIONS)
#   - vault_standard_upgrade.py (STANDARD_FOLDERS)
#
# Campos:
#   folder      — nombre de carpeta relativa al vault root
#   name        — nombre corto legible (para tablas e índices)
#   description — descripción de una línea (propósito de la sección)
#   tool_hint   — comando sugerido cuando la sección está vacía (None = sin hint)

SECTIONS: List[Dict[str, Optional[str]]] = [
    {
        "folder": "00_System",
        "name": "Sistema",
        "description": "Identidad, reglas y configuración del agente",
        "tool_hint": None,
    },
    {
        "folder": "01_Projects",
        "name": "Proyectos",
        "description": "Estado, contexto y progreso de proyectos activos",
        "tool_hint": "vault_project_overview --project <slug> --description '...' --runtime 'Node.js 20'",
    },
    {
        "folder": "02_Observability",
        "name": "Observabilidad",
        "description": "Errores, métricas, alertas e incidentes",
        "tool_hint": "vault_log_error --project <slug> --type error --title '<msg>' --description '...'",
    },
    {
        "folder": "03_Decisions",
        "name": "Decisiones",
        "description": "Decisiones de arquitectura y diseño (ADRs)",
        "tool_hint": "vault_write --folder 03_Decisions --title 'ADR-001 <titulo>' --content '...'",
    },
    {
        "folder": "04_Sessions",
        "name": "Sesiones",
        "description": "Diarios de sesión y contexto de trabajo",
        "tool_hint": "vault_write --folder 04_Sessions --title '$(date +%Y-%m-%d)' --content '...'",
    },
    {
        "folder": "05_Patterns",
        "name": "Patrones",
        "description": "Patrones reutilizables de código y arquitectura",
        "tool_hint": "vault_pattern_save --project <slug> --name <patron> --type design --status planificado",
    },
    {
        "folder": "06_Diagrams",
        "name": "Diagramas",
        "description": "Diagramas y representaciones visuales",
        "tool_hint": "vault_diagram_save --project <slug> --title <diagrama> --diagram_type mermaid --category entity --content '...'",
    },
    {
        "folder": "07_Knowledge",
        "name": "Conocimiento",
        "description": "Base de conocimiento técnico y conceptual",
        "tool_hint": "vault_knowledge_save --project <slug> --title <concepto> --category concept --content '...'",
    },
    {
        "folder": "08_Runbooks",
        "name": "Runbooks",
        "description": "Procedimientos operativos paso a paso",
        "tool_hint": "vault_runbook_save --project <slug> --title <runbook> --trigger '...' --category deploy --steps '[{\"step\": \"...\"}]'",
    },
    {
        "folder": "09_Infrastructure",
        "name": "Infraestructura",
        "description": "Infraestructura, entornos y configuraciones",
        "tool_hint": "vault_infra_save --project <slug> --name <servicio> --type server --description '...' --config '{}'",
    },
    {
        "folder": "10_Migrated",
        "name": "Migrados",
        "description": "Documentos migrados de otras fuentes",
        "tool_hint": "vault_migrate_docs --project <slug> --source_path <path>",
    },
    {
        "folder": "11_Code",
        "name": "Código",
        "description": "Módulos de código y relaciones entre ellos",
        "tool_hint": "vault_code_module --project <slug> --file_path <path> --description '...'",
    },
    {
        "folder": "12_Bibliography",
        "name": "Bibliografía",
        "description": "Fuentes externas: artículos, papers, APIs, libros y docs consultados",
        "tool_hint": "vault_bibliography_save --title <ref> --source_type web --url 'https://...' --summary '...'",
    },
    {
        "folder": "13_Flows",
        "name": "Flujos",
        "description": "Flujos de trabajo, pipelines, ciclos de vida y diagramas de flujo",
        "tool_hint": "vault_flow_save --project <slug> --name <flow> --type workflow --description '...' --mermaid 'flowchart LR; A-->B'",
    },
    {
        "folder": "14_Requirements",
        "name": "Requerimientos",
        "description": "Requerimientos funcionales y no funcionales (ISO 29148)",
        "tool_hint": "vault_requirement_save --project <slug> --title 'REQ-001 ...' --description '...' --type functional --priority must-have",
    },
    {
        "folder": "15_Tests",
        "name": "Tests",
        "description": "Casos de prueba y resultados (ISO 29119): unit, integration, e2e, performance",
        "tool_hint": "vault_test_save --project <slug> --title <test> --test_type unit --description '...'",
    },
    {
        "folder": "16_AI_Governance",
        "name": "IA Governance",
        "description": "Decisiones y auditorías de agentes IA (ISO 42001)",
        "tool_hint": "vault_ai_decision --project <slug> --title <decision> --decision_type architectural --description '...' --rationale '...'",
    },
    {
        "folder": "17_Preferences",
        "name": "Preferencias",
        "description": (
            "Preferencias del usuario: cómo quiere trabajar, estilo, herramientas "
            "y restricciones. Contexto estable que el agente debe respetar entre sesiones"
        ),
        "tool_hint": "vault_preferences --set --category workflow --title <preferencia> --statement '...' --strength should",
    },
    # ── Secciones 18–20 (v39) ───────────────────────────────────────────────
    #
    # No salen de un diseño a priori: salen de medir 17 vaults reales. Los
    # agentes ya estaban escribiendo estas tres cosas, y al no existir sección
    # las repartían entre `02_Observability`, `07_Knowledge` y carpetas que se
    # inventaban sobre la marcha (`docs/`, `scripts/`, `certificates/`). Una
    # nota sin sitio no desaparece: aparece en cualquier sitio.
    {
        "folder": "18_Bugs",
        "name": "Bugs",
        "description": (
            "Defectos con ciclo de vida propio: síntoma, causa raíz, corrección y "
            "verificación. Se distingue de 02_Observability/errors en que un error "
            "es un evento observado y un bug es un defecto que se persigue hasta "
            "cerrarlo (ISO/IEC 25010 §fiabilidad)"
        ),
        "tool_hint": "vault_bug_save --project <slug> --title <bug> --symptom '...' --severity high",
    },
    {
        "folder": "19_Audits",
        "name": "Auditorías",
        "description": (
            "Bitácora del vault: resultados de auditoría, censos de vocabulario y "
            "registro append-only de términos introducidos. Es la memoria que "
            "impide que cada sesión reinvente el vocabulario de la anterior "
            "(ISO 9001 §9.2, ISO/IEC 42001 §9)"
        ),
        "tool_hint": "vault_tags --audit",
    },
    {
        "folder": "20_Quarantine",
        "name": "Cuarentena",
        "description": (
            "Notas retenidas sin destino seguro: origen desconocido, contenido "
            "sospechoso de inyección, o reclasificación pendiente de juicio. "
            "Existe porque la alternativa a cuarentena no es limpieza, es borrado "
            "— y aquí nada se borra (política de no-derogación)"
        ),
        "tool_hint": "vault_quarantine --list",
    },
    # ── 21_QA (v40.35) ───────────────────────────────────────────────────────
    #
    # Gestión de calidad: planes de prueba, métricas QA, reportes y estrategia.
    # Convive con 02_Observability/quality (NCRs y acciones correctivas, ISO 9001
    # §10.2) y con 15_Tests (casos de prueba ejecutados, ISO 29119).
    # 21_QA es el nivel de proceso: política, estrategia, métricas agregadas y
    # reporting — lo que un QA manager necesita para saber cómo va el producto.
    # Se puebla con eventos y con la ejecución de la suite de tests (AP-45).
    {
        "folder": "21_QA",
        "name": "QA",
        "description": "Gestión de calidad: planes de prueba, métricas, reportes y estrategia QA (ISO 9001, ISO 29119, ISO 25010)",
        "tool_hint": "vault_qa_save --project <slug> --title <plan> --type test-plan --description '...'",
    },
    {
        "folder": "99_Index",
        "name": "Índices",
        "description": "Índices de navegación del vault",
        "tool_hint": None,
    },
]

# ──────────────────────────────────────────────────────────────────────────────
# Tipos de nota por sección — vocabulario ABIERTO con memoria
# ──────────────────────────────────────────────────────────────────────────────
#
# Antes esto vivía copiado en tres sitios, cada uno con una cobertura distinta:
# `vault_fundamentals` (F2) y `vault_quality_check` (F4) declaraban 14 secciones
# con UN tipo esperado cada una, y `vault_graph_merge` otras 18 con nombres que
# no coincidían (`infra` vs `infrastructure`, `ai_decision` vs `ai_governance`).
# Las tres se quedaron en la v33: ninguna conocía `17_Preferences`, `18_Bugs`,
# `19_Audits` ni `20_Quarantine`.
#
# **Lo que rompía no era la cobertura, era el modelo.** Medido contra un vault
# real de 200 notas ajeno a este repo, una sección no tiene un tipo: tiene una
# familia. `01_Projects` acumulaba seis (`project`, `project-overview`,
# `project-architecture`, `project-directives`, `audit`, `primer`) y el checker
# esperaba exactamente uno, así que penalizaba cinco de cada seis notas — todas
# escritas por las tools de este mismo estándar. Eso es AP-44 en su forma pura:
# la herramienta se certificaba contra su propia normalización.
#
# El vocabulario que se registra aquí es por tanto ABIERTO, en el sentido de
# AP-39: un tipo que no esté en esta tabla **no es una violación**, porque
# rechazar empujaría a omitir el campo. Lo que sí es una señal es un tipo que
# es canónico de OTRA sección — una nota de decisión archivada en 07_Knowledge—,
# y eso solo se puede detectar teniendo la tabla completa.
#
# Consecuencia deliberada del diseño: una entrada incompleta solo puede causar
# un hallazgo que no se ve, nunca uno falso. Es la dirección correcta en la que
# puede fallar una tool que puntúa.
#
# Los tipos salen de ejecutar los escritores y de leer dos vaults, no de la
# intención de nadie. Ojo con un matiz que costó ver: `vault_requirement_save`,
# `vault_test_save`, `vault_ai_decision` y `vault_bibliography_save` NO escriben
# `type:` sino `req_type:`, `test_type:`, `decision_type:` y `source_type:`. El
# mapa viejo esperaba en `type:` valores que esas tools nunca escriben ahí.

#: Secciones dirigidas por eventos: su vacío es estado correcto, no trabajo
#: pendiente. Poblarlas al arrancar sería inventar bugs, auditorías y
#: cuarentenas que no han ocurrido (AP-45: cobertura sin evidencia). El dato
#: estaba solo dentro de `vault_onboard`, así que `vault_init` no lo sabía y
#: sembraba andamios justo donde el estándar promete no escribir nada.
EVENT_DRIVEN_SECTIONS: Dict[str, str] = {
    "18_Bugs": "se puebla cuando aparece un bug (vault_bug_save)",
    "19_Audits": "se puebla al ejecutar una auditoría (vault_tags --audit)",
    "20_Quarantine": "se puebla cuando algo entra en cuarentena",
    "21_QA": "se puebla con eventos QA: ejecución de suite, métricas, reporting (vault_qa_save, vault_test_runner)",
}


#: Artefactos derivados: no los escribe nadie a mano, los regenera entera una
#: tool a partir de otra fuente. No llevan frontmatter —ni les hace falta: no
#: son notas, son salida— y exigírselo es reprobar la salida del propio
#: estándar (AP-44). El `index.md` de cada sección entra por nombre, no por
#: lista; estos dos no tienen un patrón que los distinga y hay que declararlos.
#: Quien los añada aquí asume la otra mitad: si su fuente cambia y el fichero
#: no, eso es AP-47 y lo vigila su tool, no `vault_validate`.
#: Carpetas de maquinaria: viven dentro de una sección canónica pero no
#: contienen notas, sino el estado que una norma necesita para funcionar.
#: Indexarlas produce un `index.md` de una carpeta sin notas —una nota derivada
#: que después cuenta como nota en disco y desajusta el índice de búsqueda
#: (AP-47)— y que además ofrece al agente una sección que no puede poblar.
MACHINERY_FOLDERS: Dict[str, str] = {
    "19_Audits/vocabulary": "bitácora append-only del vocabulario (AP-39)",
}


#: Carpetas legítimas en la raíz del vault que **no** son secciones canónicas.
#: Existían en tres sitios con tres criterios distintos —`vault_norms._ROOT_ALLOWED`
#: decidía qué no viola CN-02, `vault_io._SKIP_AUTO_INDEX` qué no dispara la
#: cascada de índices, y `vault_sdd_init.SDD_OUTPUT_DIR` escribía `docs/` sin
#: aparecer en ninguna de las dos—. El resultado era que el propio estándar
#: generaba una violación de CN-02 al ejecutar su generador de SDD contra el
#: sandbox: el kernel ya sabía que `docs/` no es una sección y el audit no.
#: Eso es AP-05 en su forma más barata de arreglar: una lista, no tres.
NON_SECTION_ROOT_FOLDERS: Dict[str, str] = {
    ".obsidian": "configuración de Obsidian",
    ".trash": "papelera de Obsidian",
    ".history": "instantáneas de nota (SP-01)",
    ".git": "control de versiones",
    ".locks": "bloqueos de escritura del kernel",
    "vault-backups": "destino de `vault_backup` cuando vive dentro del vault",
    "docs": "documentación derivada del estándar (`vault_sdd_init.SDD_OUTPUT_DIR`)",
}


DERIVED_ARTIFACTS: Dict[str, str] = {
    "00_System/change-log.md": "vault_change_log",
    "00_System/tool-contracts.md": "vault_compact_contracts",
    "99_Index/tag-index.md": "vault_tags",
}


SECTION_TYPES: Dict[str, tuple] = {
    "00_System": ("system", "knowledge"),
    "01_Projects": (
        "project",
        "project-overview",
        "project-architecture",
        "project-directives",
    ),
    "02_Observability": (
        "observability",
        "error",
        "antipattern",
        "antipattern-log",
        "observation",
        "security-audit",
    ),
    "03_Decisions": ("decision", "adr"),
    "04_Sessions": ("session", "session-log", "documentation"),
    "05_Patterns": ("pattern", "architecture"),
    "06_Diagrams": ("diagram",),
    "07_Knowledge": ("knowledge", "concept", "api", "api-reference", "workflow"),
    "08_Runbooks": ("runbook",),
    "09_Infrastructure": ("infrastructure", "infra-map", "environment"),
    "10_Migrated": ("documentation", "migrated", "migration-report"),
    "11_Code": ("code", "code-map", "code-module"),
    "12_Bibliography": ("reference", "bibliography"),
    "13_Flows": ("flow",),
    "14_Requirements": ("requirement",),
    "15_Tests": ("test",),
    "16_AI_Governance": ("governance", "ai_decision", "ai_governance"),
    "17_Preferences": ("preference",),
    "18_Bugs": ("bug",),
    "19_Audits": ("audit",),
    "20_Quarantine": ("quarantine",),
    "21_QA": ("test-plan", "qa-metrics", "qa-report", "qa-strategy", "coverage-report"),
    "99_Index": ("index",),
}

#: **El primer elemento no es decorativo: es el que escribe el write path.**
#: `vault_write.tipo_por_carpeta` deriva de aquí, así que reordenar una
#: familia cambia lo que se escribe en disco. Los demás elementos son los tipos
#: que ese mismo estándar produce por otras vías (`vault_migrate_docs` escribe
#: `migration-report`, `vault_code_map` escribe `code-map`) más los que se
#: midieron en vaults reales.

#: **Qué clase de documento es una sección**, con el vocabulario de Diátaxis
#: (tutorial, guía, referencia, explicación) más dos clases que Diátaxis no
#: cubre porque no son documentación escrita para leerse de corrido: `registro`
#: —lo que ocurrió, anotado cuando ocurrió— e `indice` —navegación derivada—.
#: Cada sección declara una sola clase y el motivo, sacado de su `description`.
#: Ninguna sección es `tutorial`: se publica el hueco en vez de forzar una.
DOCUMENTACION_CLASES: Dict[str, str] = {
    "tutorial": "aprender haciendo: un recorrido guiado de principio a fin",
    "guia": "resolver una tarea concreta: pasos para quien ya sabe qué quiere",
    "referencia": "consultar un dato: descripción exacta de lo que hay",
    "explicacion": "entender por qué: contexto, decisiones y alternativas",
    "registro": "lo que ocurrió, anotado cuando ocurrió (fuera de Diátaxis)",
    "indice": "navegación derivada que regenera una tool (fuera de Diátaxis)",
}

#: Las cuatro clases que son Diátaxis; las otras dos se publican aparte.
DIATAXIS = ("tutorial", "guia", "referencia", "explicacion")

SECTION_DOCUMENTACION: Dict[str, tuple] = {
    "00_System": ("referencia", "identidad, reglas y configuración que el agente consulta"),
    "01_Projects": ("explicacion", "estado y contexto de cada proyecto: por qué está como está"),
    "02_Observability": ("registro", "errores, alertas e incidentes según ocurren"),
    "03_Decisions": ("explicacion", "un ADR explica por qué se eligió una opción y no otra"),
    "04_Sessions": ("registro", "diario de sesión: lo que se hizo, en su fecha"),
    "05_Patterns": ("guia", "cómo resolver un problema que se repite"),
    "06_Diagrams": ("explicacion", "representación visual para entender una estructura"),
    "07_Knowledge": ("explicacion", "conocimiento técnico y conceptual"),
    "08_Runbooks": ("guia", "procedimientos operativos paso a paso"),
    "09_Infrastructure": ("referencia", "inventario de infraestructura, entornos y configuración"),
    "10_Migrated": ("registro", "lo importado se conserva como llegó; su cuadrante es el de su origen"),
    "11_Code": ("referencia", "mapa de módulos de código y sus relaciones"),
    "12_Bibliography": ("referencia", "fuentes externas consultadas"),
    "13_Flows": ("explicacion", "flujos, pipelines y ciclos de vida: cómo encaja el proceso"),
    "14_Requirements": ("referencia", "requerimientos (ISO 29148): lo que el sistema debe cumplir"),
    "15_Tests": ("referencia", "casos de prueba y resultados (ISO 29119)"),
    "16_AI_Governance": ("registro", "decisiones y auditorías de agentes IA, en su fecha (ISO 42001)"),
    "17_Preferences": ("referencia", "contexto estable que el agente consulta en cada tarea"),
    "18_Bugs": ("registro", "se puebla cuando aparece un bug"),
    "19_Audits": ("registro", "se puebla al ejecutar una auditoría"),
    "20_Quarantine": ("registro", "se puebla cuando algo entra en cuarentena"),
    "21_QA": ("registro", "eventos de calidad: ejecuciones, métricas y reportes"),
    "99_Index": ("indice", "índices de navegación que regeneran las tools"),
}

#: **Eje de versionado: cómo cambia una nota sin perder lo que fue.** Cada modo
#: nombra las tools que lo realizan y cuánto obliga: `guard` si la tool lo hace
#: siempre, `recommended` si existe la vía pero nada impide tomar otra. El test
#: comprueba que cada tool está en el catálogo MCP; un modo sin tool viva sería
#: documentación sin código (regla 3).
MODOS_DE_VERSION: Dict[str, dict] = {
    "historia": {"que": "se reescribe en su sitio y la versión anterior queda en .history/",
                 "tools": ("vault_write", "vault_history_compact"), "enforcement": "guard"},
    "anexado": {"que": "solo se añade al final; lo ya escrito no se reescribe",
                "tools": ("vault_append",), "enforcement": "recommended"},
    "sustitucion": {"que": "la versión nueva es otra nota y la anterior declara superseded_by",
                    "tools": ("vault_supersede",), "enforcement": "recommended"},
    "regenerado": {"que": "artefacto derivado: se regenera desde las notas y no se versiona",
                   "tools": ("vault_section_index",), "enforcement": "guard"},
    "inmutable": {"que": "estado terminal: ni se reescribe ni se sustituye, queda como hecho",
                  "tools": ("vault_write",), "enforcement": "recommended"},
}

#: **Ejes de trazabilidad y versionado por clase de documento.** `traza` dice
#: con qué se enlaza una nota de esa clase y por qué campos de frontmatter; los
#: campos son los que **escriben** las tools nombradas —el test lo comprueba en
#: su código—, no los que el SDD prometía: `relacionado_con:` y
#: `lifecycle_state:` figuraban en él y ninguna tool los escribe. Un `campos`
#: vacío significa que la traza va por wikilink en el cuerpo. `version` es el
#: modo de `MODOS_DE_VERSION` mientras la nota está abierta; el estado puede
#: endurecerlo (`modo_de_version`).
EJES_DOCUMENTACION: Dict[str, dict] = {
    "tutorial": {"traza": "la referencia que enseña a usar, por wikilink",
                 "campos": (), "tools": ("vault_write",), "version": "historia"},
    "guia": {"traza": "los patrones relacionados, los ficheros que toca y el disparador del runbook",
             "campos": ("relatedPatterns", "files", "trigger"),
             "tools": ("vault_pattern_save", "vault_runbook_save"), "version": "historia"},
    "referencia": {"traza": ("el requisito por su identificador y el test que lo verifica; "
                             "el código relacionado va en el cuerpo y en el índice, no en "
                             "el frontmatter"),
                   "campos": ("req_id", "related_requirement"),
                   "tools": ("vault_requirement_save", "vault_test_save"),
                   "version": "historia"},
    "explicacion": {"traza": "las notas relacionadas y la que la sustituye cuando la decisión cambia",
                    "campos": ("related", "superseded_by"),
                    "tools": ("vault_ingest", "vault_supersede"), "version": "historia"},
    "registro": {"traza": "su fecha y el test que verifica la corrección",
                 "campos": ("createdAt", "verified_by"),
                 "tools": ("vault_bug_save",), "version": "anexado"},
    "indice": {"traza": "las notas de las que se deriva, al regenerarse",
               "campos": (), "tools": ("vault_section_index",), "version": "regenerado"},
}

#: **Correlación estado → versionado.** El régimen de un `status` no se declara
#: aquí: lo deriva `regimen_de_estado` de `vault_norms_catalog.STATUS_TRANSITIONS`.
#: Un estado `abierto` puede volver a `draft`, así que se edita con el modo de su
#: clase; uno `cerrado` ya no puede, y cambiar su contenido es una versión nueva;
#: uno `terminal` no tiene salida.
REGIMENES_DE_ESTADO: Dict[str, str] = {
    "abierto": "puede volver a draft: se edita con el modo de su clase",
    "cerrado": "ya no vuelve a draft: un cambio de contenido es una nota nueva",
    "terminal": "sin transiciones de salida: queda como hecho",
}


def regimen_de_estado(status: str,
                      transiciones: Mapping[str, Iterable[str]]) -> str:
    """El régimen de `status`, derivado de sus transiciones de salida (AP-57).

    Las transiciones se reciben en vez de importarse: el dueño es
    `vault_norms_catalog.STATUS_TRANSITIONS` y este registro sigue sin
    depender de nadie. Vivía en `vault_norms_catalog` y la puerta del núcleo
    (AP-59) lo marcó: tocar el catálogo de normas para una función derivada
    lo sacaba de su escalón de churn.
    """
    salidas = tuple(transiciones[status])
    if status == "draft" or "draft" in salidas:
        return "abierto"
    return "cerrado" if salidas else "terminal"


def modo_de_version(clase: str, regimen: str) -> str:
    """El modo de versionado de una nota de `clase` en un estado de `regimen`.

    Lo anexado y lo regenerado no dependen del estado: un registro cerrado se
    sigue anexando y un índice se sigue regenerando. El resto se endurece al
    cerrarse —una nota aprobada no vuelve a draft, así que su cambio es otra
    nota— y se congela al llegar a un estado terminal.
    """
    base = EJES_DOCUMENTACION[clase]["version"]
    if base in ("anexado", "regenerado") or regimen == "abierto":
        return base
    if regimen == "cerrado":
        return "sustitucion"
    if regimen == "terminal":
        return "inmutable"
    raise ValueError(f"régimen desconocido: {regimen}")


#: `type:` de las notas andamio que crea `vault_init`. No pertenecen a ninguna
#: sección: son la misma nota repetida en todas, y por eso se eximen en vez de
#: añadirse a cada familia. `vault_audit` ya las eximía; los otros dos auditores
#: no, y penalizaban el andamiaje que el propio estándar escribe para que un
#: vault nuevo arranque en 100/100.
SCAFFOLD_TYPE = "primer"

# ──────────────────────────────────────────────────────────────────────────────
# Subcarpetas — descripción y tool owner
# ──────────────────────────────────────────────────────────────────────────────
#
# Fuente de verdad para:
#   - vault_section_index.py (SUBSECTION_DESCRIPTIONS)
#   - vault_spec_validate.py (folder_ownership check)
#
# Campos:
#   description  — propósito de la subcarpeta (con norma ISO si aplica)
#   owner        — tool que escribe en esta carpeta (None = múltiples owners)
#
# Regla de ownership:
#   Un subfolder puede tener exactamente UN owner.
#   Si dos tools intentan escribir en el mismo subfolder → colisión de responsabilidad.
#   Para compartir una sección raíz (ej: 09_Infrastructure) use subfolders separados.

SUBFOLDERS: Dict[str, Dict[str, Optional[str]]] = {
    # ── 02_Observability ────────────────────────────────────────────────────
    "02_Observability/errors": {
        "description": "Errores de runtime, compilación o lógica con stack trace y solución",
        "owner": "vault_log_error",
    },
    "02_Observability/antipatterns": {
        "description": "Código o arquitectura problemática: detección, por qué es problemático, alternativa",
        "owner": "vault_log_error",
    },
    "02_Observability/vulnerabilities": {
        "description": "Hallazgos de seguridad: CVE, OWASP, injection, XSS, SSRF, etc.",
        "owner": "vault_log_error",
    },
    "02_Observability/waf": {
        "description": "Reglas de firewall activadas, bypass detectado, contexto de amenaza",
        "owner": "vault_log_error",
    },
    "02_Observability/metrics": {
        "description": "SLIs y KPIs: qué se mide, servicio, valor objetivo, unidad, herramienta",
        "owner": "vault_log_error",
    },
    "02_Observability/alerts": {
        "description": "Reglas de alerta: condición, umbral, canal, severidad, link al runbook",
        "owner": "vault_log_error",
    },
    "02_Observability/incidents": {
        "description": "Incidentes de producción con ciclo de vida P1-P4 (ISO 20000-1 §8.6)",
        "owner": "vault_incident_save",
    },
    "02_Observability/slos": {
        "description": "SLO definitions con error budget y burn rates (ISO 20000-1 §8.3)",
        "owner": "vault_slo_save",
    },
    "02_Observability/risks": {
        "description": "Registro de riesgos con score likelihood×impact (ISO 31000:2018)",
        "owner": "vault_risk_save",
    },
    "02_Observability/quality": {
        "description": "No conformidades NCR-YYYY-NNN y acciones correctivas (ISO 9001:2015 §10.2)",
        "owner": "vault_ncr_save",
    },
    "02_Observability/maintenance": {
        "description": (
            "Notas de mantenimiento del vault: fixes aplicados, depuraciones, limpiezas, "
            "reorganizaciones/reclasificaciones de nodos, y stubs pendientes de triage "
            "(subcarpeta stubs/). Separa artefactos de mantenimiento de los nodos de "
            "contenido para que todo sea rastreable sin contaminar el grafo (AP-36)."
        ),
        "owner": "vault_graph_fix",
    },
    # ── 05_Patterns ───────────────────────────────────────────────────────────
    "05_Patterns/design": {
        "description": "Patrones de diseño GoF: Singleton, Factory, Observer, Strategy, Decorator, Proxy, Command, Adapter, Facade",
        "owner": "vault_pattern_save",
    },
    "05_Patterns/architecture": {
        "description": "Patrones arquitectónicos: MVC, Hexagonal, Event-Driven, CQRS, Microservices, Monolith, BFF, Clean Architecture",
        "owner": "vault_pattern_save",
    },
    "05_Patterns/code": {
        "description": "Patrones de código: Retry, Circuit-Breaker, Cache-Aside, Saga, Idempotency, Rate-Limit, Bulkhead",
        "owner": "vault_pattern_save",
    },
    "05_Patterns/integration": {
        "description": "Patrones de integración: REST, GraphQL, WebSocket, Pub-Sub, Webhook, gRPC, Message-Queue, Batch",
        "owner": "vault_pattern_save",
    },
    # ── 06_Diagrams ───────────────────────────────────────────────────────────
    "06_Diagrams/entity": {
        "description": "Diagramas ER y relaciones entre entidades de dominio (Mermaid erDiagram)",
        "owner": "vault_relation_add",
    },
    "06_Diagrams/component": {
        "description": "Diagramas de componentes y módulos de la aplicación (Mermaid graph TD)",
        "owner": "vault_diagram_save",
    },
    "06_Diagrams/sequence": {
        "description": "Diagramas de secuencia de flujos de ejecución (Mermaid sequenceDiagram)",
        "owner": "vault_diagram_save",
    },
    "06_Diagrams/dependency": {
        "description": "Grafo de dependencias entre paquetes o módulos (Mermaid graph LR)",
        "owner": "vault_diagram_save",
    },
    "06_Diagrams/flow": {
        "description": "Flujos generales, decisiones de proceso, diagramas de negocio (Mermaid flowchart TD)",
        "owner": "vault_diagram_save",
    },
    # ── 07_Knowledge ──────────────────────────────────────────────────────────
    "07_Knowledge/glossary": {
        "description": "Glosario de términos de dominio o negocio con definición y contexto",
        "owner": "vault_knowledge_save",
    },
    "07_Knowledge/apis": {
        "description": "Documentación de APIs: endpoints, auth, rate limits, ejemplos de request/response",
        "owner": "vault_knowledge_save",
    },
    "07_Knowledge/concepts": {
        "description": "Conceptos técnicos específicos del proyecto (no documentación genérica)",
        "owner": "vault_knowledge_save",
    },
    "07_Knowledge/business-rules": {
        "description": "Reglas de negocio no obvias: cuándo aplican, excepciones, quién las definió",
        "owner": "vault_knowledge_save",
    },
    "07_Knowledge/configs": {
        "description": "Configuración importante de herramientas, entornos o servicios",
        "owner": "vault_knowledge_save",
    },
    "07_Knowledge/dependencies": {
        "description": "Paquetes o librerías: nombre, versión, propósito, por qué se eligió, alternativas",
        "owner": "vault_knowledge_save",
    },
    "07_Knowledge/frameworks": {
        "description": "Frameworks usados: rol, convenciones adoptadas, decisiones de configuración",
        "owner": "vault_knowledge_save",
    },
    # ── 08_Runbooks ─────────────────────────────────────────────────────────
    "08_Runbooks/deploy": {
        "description": "Release notes y procedimientos de despliegue (ISO 12207:2017 §6.3.7)",
        "owner": "vault_release_save",
    },
    # ── 09_Infrastructure ───────────────────────────────────────────────────
    "09_Infrastructure/envs": {
        "description": "Variables de entorno estáticas por archivo .env — una nota por env file",
        "owner": "vault_env_save",
    },
    "09_Infrastructure/env-matrix": {
        "description": "Matriz multi-entorno dev/staging/prod/dr/perf (ISO 12207:2017 §6.3.4)",
        "owner": "vault_env_matrix",
    },
    "09_Infrastructure/privacy": {
        "description": "Registros de tratamiento de datos personales GDPR Art.30 (ISO 27701:2019)",
        "owner": "vault_privacy_save",
    },
    # ── 12_Bibliography ─────────────────────────────────────────────────────
    "12_Bibliography/web": {
        "description": "Referencias web: artículos, blog posts, documentación online",
        "owner": "vault_bibliography_save",
    },
    "12_Bibliography/papers": {
        "description": "Papers académicos y técnicos",
        "owner": "vault_bibliography_save",
    },
    "12_Bibliography/docs": {
        "description": "Documentación oficial de herramientas y frameworks",
        "owner": "vault_bibliography_save",
    },
    "12_Bibliography/apis": {
        "description": "Referencias de APIs y especificaciones de interfaces",
        "owner": "vault_bibliography_save",
    },
    "12_Bibliography/books": {
        "description": "Libros técnicos consultados",
        "owner": "vault_bibliography_save",
    },
    # ── 13_Flows ────────────────────────────────────────────────────────────
    "13_Flows/workflow": {
        "description": "Flujos de trabajo y procesos de negocio",
        "owner": "vault_flow_save",
    },
    "13_Flows/pipeline": {
        "description": "Pipelines de CI/CD, datos o procesamiento",
        "owner": "vault_flow_save",
    },
    "13_Flows/lifecycle": {
        "description": "Ciclos de vida de entidades, tickets o deploys",
        "owner": "vault_flow_save",
    },
    "13_Flows/dataflow": {
        "description": "Flujos de datos entre componentes o servicios",
        "owner": "vault_flow_save",
    },
    # ── 15_Tests ────────────────────────────────────────────────────────────
    "15_Tests/unit": {
        "description": "Tests unitarios por módulo o función",
        "owner": "vault_test_save",
    },
    "15_Tests/integration": {
        "description": "Tests de integración entre componentes",
        "owner": "vault_test_save",
    },
    "15_Tests/e2e": {
        "description": "Tests end-to-end sobre flujos completos",
        "owner": "vault_test_save",
    },
    "15_Tests/performance": {
        "description": "Tests de rendimiento, carga y estrés",
        "owner": "vault_test_save",
    },
    "15_Tests/security": {
        "description": "Tests de seguridad y penetración",
        "owner": "vault_test_save",
    },
    "15_Tests/acceptance": {
        "description": "Tests de aceptación con criterios de usuario",
        "owner": "vault_test_save",
    },
    # ── 16_AI_Governance ────────────────────────────────────────────────────
    "16_AI_Governance/decisions": {
        "description": "Decisiones formales de agentes IA con trazabilidad ISO 42001",
        "owner": "vault_ai_decision",
    },
    # ── 17_Preferences ──────────────────────────────────────────────────────
    # Preferencias = contexto estable, no conocimiento del dominio. Van
    # separadas de 07_Knowledge porque su ciclo de vida es distinto: una
    # preferencia se revoca, no se corrige, y el agente debe poder cargarlas
    # todas sin arrastrar el resto de la base de conocimiento.
    "17_Preferences/workflow": {
        "description": "Cómo quiere el usuario que se trabaje: flujo, ritmo, qué confirmar antes de actuar",
        "owner": "vault_preferences",
    },
    "17_Preferences/style": {
        "description": "Estilo de comunicación y de código: idioma, tono, formato, convenciones",
        "owner": "vault_preferences",
    },
    "17_Preferences/tooling": {
        "description": "Herramientas, lenguajes y librerías preferidas o vetadas",
        "owner": "vault_preferences",
    },
    "17_Preferences/constraints": {
        "description": "Restricciones duras: qué no se debe tocar, mover, borrar o propagar",
        "owner": "vault_preferences",
    },
    "17_Preferences/domain": {
        "description": "Preferencias específicas de un proyecto o dominio concreto",
        "owner": "vault_preferences",
    },
    # ── 18_Bugs ─────────────────────────────────────────────────────────────
    # El ciclo del defecto es el que estaba disperso: el síntoma acababa en
    # 02_Observability/errors, la causa en 07_Knowledge y la corrección en
    # 03_Decisions, sin nada que las uniera. Separadas por fase, la relación
    # entre ellas es explícita en vez de quedar en la cabeza de quien la vio.
    "18_Bugs/open": {
        "description": "Defectos reproducidos y sin corregir, con síntoma y pasos de reproducción",
        "owner": "vault_bug_save",
    },
    "18_Bugs/root-causes": {
        "description": "Causa raíz de un defecto, enlazada al bug que la manifestó (ISO/IEC 25010)",
        "owner": "vault_bug_save",
    },
    "18_Bugs/fixed": {
        "description": "Defectos corregidos y verificados, con la corrección y su evidencia",
        "owner": "vault_bug_save",
    },
    # ── 19_Audits ───────────────────────────────────────────────────────────
    # La bitácora. `vocabulary` es la pieza que faltaba: un registro append-only
    # de cada término introducido, con quién lo introdujo y cuándo. Sin él, el
    # vocabulario del vault vive solo en la sesión que lo escribió — y medido
    # sobre 17 vaults, la tasa de invención de tags no bajó en tres meses.
    "19_Audits/vocabulary": {
        "description": "Registro append-only de términos: qué entró, cuándo, quién y a qué sucede",
        "owner": "vault_tags",
    },
    "19_Audits/runs": {
        "description": "Resultados de auditorías ejecutadas: normas, calidad, grafo, seguridad (ISO 9001 §9.2)",
        "owner": "vault_audit",
    },
    "19_Audits/findings": {
        "description": "Hallazgos que exigen acción, con norma incumplida y estado de resolución",
        "owner": "vault_audit",
    },
    # ── 20_Quarantine ───────────────────────────────────────────────────────
    "20_Quarantine/unclassified": {
        "description": "Notas sin sección determinable: se retienen hasta que haya criterio, no se borran",
        "owner": "vault_quarantine",
    },
    "20_Quarantine/suspicious": {
        "description": "Contenido que disparó el pre-vuelo anti-poisoning (POISON-01..05) y no se ha revisado",
        "owner": "vault_quarantine",
    },
    "20_Quarantine/duplicates": {
        "description": "Candidatas a duplicado pendientes de decidir cuál es la canónica (PAT-1)",
        "owner": "vault_quarantine",
    },
    # ── 21_QA ───────────────────────────────────────────────────────────────
    "21_QA/test-plans": {
        "description": "Planes de prueba y estrategia de testing (ISO 29119-1)",
        "owner": "vault_qa_save",
    },
    "21_QA/metrics": {
        "description": "KPIs y métricas de calidad: defect-rate, coverage, MTTR, pass-rate (ISO 25010)",
        "owner": "vault_qa_save",
    },
    "21_QA/reports": {
        "description": "Reportes de calidad por sprint, release o período (QA reporting)",
        "owner": "vault_qa_save",
    },
    "21_QA/strategy": {
        "description": "Política y estrategia QA: niveles de prueba, criterios de aceptación, gates",
        "owner": "vault_qa_save",
    },
    # ── 02_Observability/qa ───────────────────────────────────────────────
    # Dashboard de calidad operacional: se genera desde vault_quality_check
    # y vault_test_runner, no se escribe a mano.
    "02_Observability/qa": {
        "description": "Dashboard de calidad operacional: healthScore, coverage, defect-rate y SLO compliance (ISO 9001 §9.1)",
        "owner": "vault_quality_check",
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# Helpers — acceso tipado para cada consumidor
# ──────────────────────────────────────────────────────────────────────────────

# Índices derivados — construidos una sola vez al importar el módulo
_SECTION_BY_FOLDER: Dict[str, Dict] = {s["folder"]: s for s in SECTIONS}

ORDERED_SECTIONS: List[str] = [s["folder"] for s in SECTIONS]


def standard_folders() -> List[str]:
    """Lista de carpetas raíz del vault (para vault_standard_upgrade)."""
    return [s["folder"] for s in SECTIONS]


def runtime_seed_projection() -> Dict[str, object]:
    """Proyección mínima para crear un runtime desde el paquete instalado.

    ``SECTIONS`` sigue siendo la autoridad editorial. El wheel sólo transporta
    una proyección JSON comprobable de sus nombres y de la versión vigente; no
    duplica el registro ni necesita importar ``scripts/`` al ejecutarse en un
    consumidor.
    """
    from vault_version import CURRENT_VERSION

    return {
        "schema": 1,
        "standard_version": CURRENT_VERSION,
        "sections": standard_folders(),
    }


def section_name(folder: str) -> str:
    """Nombre corto de una sección (para tablas en master index)."""
    sec = _SECTION_BY_FOLDER.get(folder.split("/")[0])
    return sec["name"] if sec else folder


def section_description(folder: str, raiz: Optional[Path] = None) -> str:
    """Descripción de una sección raíz o subcarpeta.

    Busca primero en SUBFOLDERS (descripción específica), luego en SECTIONS
    (descripción del padre). Fallback: 'Subcarpeta de {parent}'.

    Con `raiz`, una sección propia aporta la `description` que declara en
    `secciones.json` (`vault_section --add --description`), o una que dice lo
    que es si no declara ninguna. Hasta v41.2 caía al fallback y una sección
    raíz salía como «Subcarpeta de 22_Scripts» en su índice y en el maestro.
    Sin `raiz`, solo cuentan las del estándar, como en `section_types`.
    """
    folder_key = folder.replace("\\", "/")
    if folder_key in SUBFOLDERS:
        return SUBFOLDERS[folder_key]["description"]
    top = folder_key.split("/")[0]
    sec = _SECTION_BY_FOLDER.get(top)
    if sec:
        return sec["description"]
    if raiz is not None:
        propia = next((s for s in leer_secciones_propias(raiz) if s["folder"] == top), None)
        if propia:
            return (propia.get("description")
                    or f"Sección propia del vault (documentación: {propia['documentacion']})")
    return f"Subcarpeta de {top}"


def section_tool_hint(folder: str) -> Optional[str]:
    """Comando sugerido para poblar una sección vacía."""
    top = folder.replace("\\", "/").split("/")[0]
    sec = _SECTION_BY_FOLDER.get(top)
    return sec["tool_hint"] if sec else None


def comando_de_tool(receta: str) -> str:
    """La receta `vault_x --flag ...` en la forma que corre donde se ejecuta.

    Hasta v40.35 cada consumidor anteponía `python scripts/` a mano, y la nota
    de comandos que se reparte a cada vault la publicaba también en la wheel,
    donde `scripts/` no existe. Instalado, este módulo vive en
    `vault_toolkit/_impl/` y la forma que corre es `vault run`.
    """
    tool, _, args = receta.strip().partition(" ")
    if Path(__file__).resolve().parent.name == "_impl":
        return f"vault run {tool} {args}".rstrip()
    return f"python scripts/{tool}.py {args}".rstrip()


def es_andamio(texto: str) -> bool:
    """¿Es una nota andamio de `vault_init` (primer), y no contenido real?

    La condición estaba copiada literal en tres sitios de `vault_audit`, con el
    valor `"primer"` escrito a mano en cada uno. Aquí es `SCAFFOLD_TYPE`, que es
    también lo que `type_misfiled_in` exceptúa: si los dos criterios se separan,
    el andamio queda exento en un sitio y penalizado en el otro.

    Sigue siendo una comprobación por subcadena, no por frontmatter, y por eso
    una nota que *hable* de andamios cuenta como andamio. Se conserva tal cual
    —cambiarlo alteraría qué notas se excluyen de tres auditorías distintas—
    pero queda anotado en un solo sitio en vez de invisible en tres.
    """
    return "scaffold: true" in texto or f"type: {SCAFFOLD_TYPE}" in texto


def es_artefacto_derivado(ruta_relativa: str) -> bool:
    """¿Lo escribe una tool como salida, en vez de ser una nota del vault?

    Dos criterios, no uno: el `index.md` de cualquier sección entra por nombre
    —hay veintidós y no se enumeran— y los demás por declaración explícita en
    `DERIVED_ARTIFACTS`. Acepta separador Windows porque quien llama suele venir
    de `relative_to()`.
    """
    rel = ruta_relativa.replace("\\", "/")
    return rel.rsplit("/", 1)[-1].lower() == "index.md" or rel in DERIVED_ARTIFACTS


# ──────────────────────────────────────────────────────────────────────────────
# Secciones propias — las que declara un vault, no el estándar
# ──────────────────────────────────────────────────────────────────────────────
#
# Un vault vivo necesita a veces una sección que el estándar no tiene (`/ans`
# guarda `scripts/` en la raíz). Hasta v41.1 la única salida era CN-02: o la
# carpeta encajaba en una de las 23 secciones o era una violación. Una sección
# propia se **declara** en el vault —no en este fichero, que es del estándar—
# y desde ese momento cuenta como sección para el contrato, el audit y los
# índices. Lo que no se declara sigue siendo CN-02.
#
# El fichero lo escribe `vault_section`; este módulo solo lo lee y valida. No
# importa `vault_io` (ver cabecera), así que la raíz se pasa como argumento.

#: Dónde declara un vault sus secciones propias, relativo a su raíz.
SECCIONES_PROPIAS_RUTA = "00_System/secciones.json"

#: Números libres para secciones propias: del primero que el estándar no usa
#: (22, tras `21_QA`) al anterior a `99_Index`. Una sección nueva del estándar
#: tomaría el siguiente número libre *del estándar*, así que el rango se deriva
#: del registro en vez de escribirse.
NUMEROS_PROPIOS = (
    max(int(f[:2]) for f in ORDERED_SECTIONS if f != "99_Index") + 1,
    int("99_Index"[:2]) - 1,
)

#: Estado de una sección propia. `retirada` no se borra (no-derogación): sus
#: notas siguen siendo de sección y `superseded_by` dice adónde va lo nuevo.
ESTADOS_DE_SECCION = ("activa", "retirada")

_NOMBRE_DE_SECCION = re.compile(r"^(\d{2})_[A-Za-z][A-Za-z0-9_]*$")


_TIPO_DE_NOTA = re.compile(r"^[a-z][a-z0-9_-]*$")


def motivo_de_tipos_invalidos(tipos) -> Optional[str]:
    """Por qué `tipos` no vale como lista de tipos de una sección propia; None si vale.

    Es el equivalente propio de `SECTION_TYPES[seccion]`: el primero es el que
    el write path escribe cuando la nota no trae `type`. Una cadena suelta no
    se acepta como lista de un elemento, porque `"script"` iterado son seis.
    """
    if not isinstance(tipos, list) or not tipos:
        return "'tipos' debe ser una lista no vacía"
    malos = [t for t in tipos if not isinstance(t, str) or not _TIPO_DE_NOTA.match(t)]
    if malos:
        return (f"'tipos' {malos!r}: cada tipo va en minúsculas, empieza por letra "
                "y solo lleva letras, cifras, '-' o '_'")
    return None


def motivo_de_nombre_invalido(carpeta: str) -> Optional[str]:
    """Por qué `carpeta` no puede ser una sección propia; None si puede."""
    m = _NOMBRE_DE_SECCION.match(carpeta or "")
    if not m:
        return "el nombre debe ser NN_Nombre: dos cifras, guion bajo y letras, cifras o guiones bajos"
    numero = int(m.group(1))
    if not NUMEROS_PROPIOS[0] <= numero <= NUMEROS_PROPIOS[1]:
        return (f"el número {numero:02d} no está libre: las secciones propias van del "
                f"{NUMEROS_PROPIOS[0]:02d} al {NUMEROS_PROPIOS[1]:02d}")
    if carpeta in ORDERED_SECTIONS:
        return "ya es una sección del estándar"
    return None


def leer_secciones_propias(raiz: Path) -> List[Dict[str, Optional[str]]]:
    """Las secciones propias declaradas en el vault de `raiz`, en orden de número.

    Sin fichero devuelve `[]`: un vault sin secciones propias es lo normal. Un
    fichero que existe y no se puede leer, o una entrada inválida, **lanza
    ValueError**: devolver `[]` ahí sería decir «no hay secciones propias» de un
    vault que sí las declaró, y cada nota suya pasaría a violar CN-02 sin que
    nadie supiera por qué (AP-51).
    """
    ruta = Path(raiz) / SECCIONES_PROPIAS_RUTA
    if not ruta.is_file():
        return []
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"{SECCIONES_PROPIAS_RUTA} no se puede leer: {e}") from e
    secciones = datos.get("secciones") if isinstance(datos, dict) else None
    if not isinstance(secciones, list):
        raise ValueError(f"{SECCIONES_PROPIAS_RUTA}: falta la lista 'secciones'")
    vistas = set()
    for s in secciones:
        carpeta = s.get("folder") if isinstance(s, dict) else None
        motivo = motivo_de_nombre_invalido(carpeta)
        if motivo:
            raise ValueError(f"{SECCIONES_PROPIAS_RUTA}: {carpeta!r} — {motivo}")
        if carpeta in vistas or carpeta[:2] in {v[:2] for v in vistas}:
            raise ValueError(f"{SECCIONES_PROPIAS_RUTA}: {carpeta!r} repite número o nombre")
        vistas.add(carpeta)
        if s.get("documentacion") not in DOCUMENTACION_CLASES:
            raise ValueError(f"{SECCIONES_PROPIAS_RUTA}: {carpeta!r} — 'documentacion' "
                             f"debe ser una de {', '.join(DOCUMENTACION_CLASES)}")
        if "tipos" in s:
            motivo = motivo_de_tipos_invalidos(s["tipos"])
            if motivo:
                raise ValueError(f"{SECCIONES_PROPIAS_RUTA}: {carpeta!r} — {motivo}")
        if s.get("status", "activa") not in ESTADOS_DE_SECCION:
            raise ValueError(f"{SECCIONES_PROPIAS_RUTA}: {carpeta!r} — 'status' debe ser "
                             f"una de {', '.join(ESTADOS_DE_SECCION)}")
    return sorted(secciones, key=lambda s: s["folder"])


#: `{ruta de secciones.json: (firma, secciones)}`. El contrato pregunta por
#: cada nota y releer el JSON miles de veces por recorrido no compra nada; la
#: firma (mtime y tamaño) invalida la entrada en cuanto `vault_section` escribe.
_SECCIONES_LEIDAS: Dict[str, tuple] = {}


def secciones_del_vault(raiz: Path) -> List[str]:
    """Las del estándar más las propias declaradas (activas y retiradas), en orden.

    Las retiradas cuentan: sus notas no dejan de ser de sección por haberse
    retirado la sección para lo nuevo. Un fichero roto no se cachea: lanza
    cada vez (ver `leer_secciones_propias`).
    """
    ruta = Path(raiz) / SECCIONES_PROPIAS_RUTA
    try:
        st = ruta.stat()
        firma = (st.st_mtime_ns, st.st_size)
    except OSError:
        firma = None
    previa = _SECCIONES_LEIDAS.get(str(ruta))
    if previa is not None and previa[0] == firma:
        return list(previa[1])
    secciones = sorted(ORDERED_SECTIONS + [s["folder"] for s in leer_secciones_propias(raiz)])
    _SECCIONES_LEIDAS[str(ruta)] = (firma, tuple(secciones))
    return secciones


def es_de_seccion(ruta_relativa: str, raiz: Optional[Path] = None) -> bool:
    """¿Vive la nota dentro de una carpeta de sección del registro?

    Un `.md` de la raíz (`README.md`, `Home.md`) o de una carpeta que el
    registro no declara (`docs/`, `scripts/`) no es de ninguna sección, y el
    contrato no puede exigirle lo que decide la sección: tipo y sensibilidad.
    El criterio es la primera componente de la ruta, y solo cuenta si hay algo
    debajo: `07_Knowledge.md` en la raíz no es de `07_Knowledge/`.

    Con `raiz`, también cuentan las secciones propias que ese vault declara
    (`leer_secciones_propias`). Sin ella, solo las del estándar: quien no sabe
    de qué vault es la ruta no puede saber qué secciones declaró.
    """
    partes = ruta_relativa.replace("\\", "/").split("/")
    if len(partes) < 2:
        return False
    if partes[0] in ORDERED_SECTIONS:
        return True
    return raiz is not None and partes[0] in secciones_del_vault(raiz)


def motivo_de_destino_invalido(folder: str, raiz: Path, nueva: bool = True) -> Optional[str]:
    """Por qué `folder` no admite la nota en el vault de `raiz`; None si la admite (CN-02).

    Son destino las secciones del estándar y las propias que el vault declara.
    Una propia **retirada** no admite notas nuevas, pero sí actualizar las que
    ya tiene: siguen siendo de sección (`secciones_del_vault`). Un registro de
    secciones ilegible lanza ValueError, como `leer_secciones_propias`.
    """
    seccion = (folder or "").replace("\\", "/").strip("/").split("/")[0]
    if not seccion:
        return "la raíz del vault no es una sección (AP-15)"
    if seccion in ORDERED_SECTIONS:
        return None
    propia = next((s for s in leer_secciones_propias(raiz) if s["folder"] == seccion), None)
    if propia is None:
        return (f"{seccion!r} no es una sección del estándar ni una sección propia "
                f"declarada en {SECCIONES_PROPIAS_RUTA}")
    if nueva and propia.get("status", "activa") == "retirada":
        sustituta = propia.get("superseded_by")
        return (f"la sección propia {seccion!r} está retirada y no admite notas nuevas"
                + (f"; lo nuevo va a {sustituta!r}" if sustituta else ""))
    return None


def section_documentacion(folder: str) -> str:
    """Clase de documento de una sección (ver `DOCUMENTACION_CLASES`); "" si no es sección."""
    top = folder.replace("\\", "/").split("/")[0]
    return SECTION_DOCUMENTACION.get(top, ("", ""))[0]


def section_default_type(folder: str, raiz: Optional[Path] = None) -> str:
    """El `type:` que el write path escribe para una sección ("" si no aplica).

    Existía como cuarta copia dentro de `vault_write`, y esa copia ya se había
    quedado corta una vez: las cuatro secciones nuevas faltaban, así que una
    nota escrita ahí salía sin `type:` y `vault_audit` la reprobaba — el
    estándar suspendiendo lo que su propio write path acababa de escribir.
    """
    tipos = section_types(folder, raiz)
    return tipos[0] if tipos else ""


def section_types(folder: str, raiz: Optional[Path] = None) -> tuple:
    """Tipos canónicos de una sección. Vacío si la sección no está registrada.

    Con `raiz`, una sección propia aporta los `tipos` que declara en
    `secciones.json` (vacío si no declara ninguno). Sin ella, solo cuentan las
    del estándar, por la misma razón que en `es_de_seccion`.
    """
    top = folder.replace("\\", "/").split("/")[0]
    if top in SECTION_TYPES or raiz is None:
        return SECTION_TYPES.get(top, ())
    propia = next((s for s in leer_secciones_propias(raiz) if s["folder"] == top), None)
    return tuple(propia.get("tipos") or ()) if propia else ()


def sections_for_type(note_type: str) -> List[str]:
    """Secciones donde ese tipo es canónico. Vacío si no lo es en ninguna.

    Vacío significa "tipo nuevo", no "tipo inválido": el vocabulario es abierto
    (AP-39) y quien consulta esto debe tratarlo como ausencia de señal.
    """
    t = (note_type or "").strip().lower()
    return [f for f, tipos in SECTION_TYPES.items() if t in tipos] if t else []


def type_misfiled_in(folder: str, note_type: str, raiz: Optional[Path] = None) -> List[str]:
    """Secciones a las que ese tipo pertenece, si NO pertenece a `folder`.

    Es la única señal que se puede dar sin cerrar el vocabulario: un tipo
    desconocido devuelve [] (no es un hallazgo), y uno canónico de otra sección
    devuelve dónde debería estar. Quien mide con equivalencia exacta contra un
    tipo único por sección penaliza a las tools del propio estándar (AP-44).
    """
    t = (note_type or "").strip().lower()
    if not t or t == SCAFFOLD_TYPE:
        return []
    top = folder.replace("\\", "/").split("/")[0]
    if t in section_types(top, raiz):
        return []
    return [s for s in sections_for_type(t) if s != top]


def folder_owner(folder: str) -> Optional[str]:
    """Retorna el tool owner de un subfolder, o None si no está registrado."""
    return SUBFOLDERS.get(folder.replace("\\", "/"), {}).get("owner")


def assert_folder_owner(tool_name: str, folder: str) -> None:
    """Lanza ValueError si otro tool ya declara ownership del folder.

    Llamar desde el FOLDER de cada tool para detectar colisiones en import time.
    No falla si el folder no está en el registro (sección raíz compartida es válida).
    """
    owner = folder_owner(folder)
    if owner is not None and owner != tool_name:
        raise ValueError(
            f"Conflicto de ownership: '{tool_name}' intenta escribir en '{folder}' "
            f"que pertenece a '{owner}'. Registrar un subfolder exclusivo en vault_registry.py."
        )


def check_folder_collisions() -> List[Dict[str, str]]:
    """Detecta todos los conflictos de ownership. Usado por vault_spec_validate."""
    seen: Dict[str, str] = {}
    conflicts = []
    for folder, meta in SUBFOLDERS.items():
        owner = meta.get("owner") or ""
        if not owner:
            continue
        if folder in seen and seen[folder] != owner:
            conflicts.append(
                {
                    "folder": folder,
                    "owner_a": seen[folder],
                    "owner_b": owner,
                }
            )
        else:
            seen[folder] = owner
    return conflicts
