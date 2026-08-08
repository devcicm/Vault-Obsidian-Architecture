#!/usr/bin/env python3
"""vault_errors_catalog — Catálogo canónico de errores con metadata + recovery hints.

Importado por vault_errors.py. No importa otros módulos del vault.
"""

from typing import Any, Dict


ERROR_CATALOG: Dict[str, Dict[str, Any]] = {
    # ── Infrastructure ────────────────────────────────────────────────────────
    "VAULT_NOT_FOUND": {
        "category": "infrastructure",
        "severity": "critical",
        "message": "El directorio raíz del vault no existe o no es accesible.",
        "recovery": {
            "action": "fix_input",
            "hint": "Verificar que el vault tenga carpeta 99_Index/ para que _detect_vault_root() lo detecte, o definir la env var VAULT_ROOT con la ruta absoluta al vault.",
            "docs": "vault-obsidian-architecture.md §Estructura de carpetas",
        },
    },
    "FOLDER_NOT_FOUND": {
        "category": "infrastructure",
        "severity": "error",
        "message": "La carpeta especificada no existe dentro del vault.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_standard_upgrade",
            "args": ["--check"],
            "hint": "Ejecutar vault_standard_upgrade --check para detectar carpetas faltantes y aplicar migraciones.",
            "docs": "vault-obsidian-architecture.md §Versionado del estándar",
        },
    },
    "FILE_NOT_FOUND": {
        "category": "infrastructure",
        "severity": "error",
        "message": "El archivo de nota especificado no existe.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_search",
            "args": ["--query", "<title>"],
            "hint": "Usar vault_search para localizar la nota por título o contenido.",
            "docs": "vault-obsidian-architecture.md §Grupo 1 — Búsqueda",
        },
    },
    "FILE_WRITE_ERROR": {
        "category": "infrastructure",
        "severity": "error",
        "message": "No se pudo escribir el archivo.",
        "recovery": {
            "action": "manual",
            "hint": "Verificar permisos del directorio destino y que no haya otro proceso bloqueando el archivo.",
            "docs": None,
        },
    },
    "FILE_READ_ERROR": {
        "category": "infrastructure",
        "severity": "error",
        "message": "No se pudo leer el archivo (encoding o permisos).",
        "recovery": {
            "action": "fix_input",
            "hint": "El archivo puede tener encoding no UTF-8. Abrirlo en Obsidian y guardarlo de nuevo.",
            "docs": None,
        },
    },
    "INDEX_NOT_FOUND": {
        "category": "infrastructure",
        "severity": "warning",
        "message": "El índice requerido no existe. Debe generarse antes.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_reindex",
            "args": [],
            "hint": "Ejecutar vault_reindex para regenerar todos los índices (graph.json, search-index.json).",
            "docs": "vault-obsidian-architecture.md §Grupo 10 — Indexación",
        },
    },
    "HISTORY_NOT_FOUND": {
        "category": "infrastructure",
        "severity": "warning",
        "message": "No se encontraron versiones anteriores en .history/ para esta nota.",
        "recovery": {
            "action": "manual",
            "hint": "El plugin Obsidian File Recovery / Vault History debe estar habilitado para generar .history/.",
            "docs": None,
        },
    },
    "BACKUP_ERROR": {
        "category": "infrastructure",
        "severity": "error",
        "message": "Error al crear o restaurar el backup.",
        "recovery": {
            "action": "manual",
            "hint": "Verificar espacio en disco y permisos del directorio destino.",
            "docs": None,
        },
    },
    # ── Validation ────────────────────────────────────────────────────────────
    "MISSING_REQUIRED_ARG": {
        "category": "validation",
        "severity": "error",
        "message": "Argumento requerido no proporcionado.",
        "recovery": {
            "action": "fix_input",
            "hint": "Ejecutar el script con --help para ver los argumentos requeridos.",
            "docs": None,
        },
    },
    "INVALID_PATH": {
        "category": "validation",
        "severity": "error",
        "message": "La ruta proporcionada contiene caracteres inválidos o sale del vault.",
        "recovery": {
            "action": "fix_input",
            "hint": "Las rutas deben ser relativas al vault root. Ejemplo: 01_Projects/mi-api/overview.md",
            "docs": "vault-obsidian-architecture.md §Estructura de carpetas",
        },
    },
    "INVALID_FOLDER": {
        "category": "validation",
        "severity": "error",
        "message": "La carpeta destino no pertenece a la estructura estándar del vault.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_audit",
            "args": [],
            "hint": "Usar una carpeta de la estructura estándar (01_Projects, 03_Decisions, 05_Patterns, etc.).",
            "docs": "vault-obsidian-architecture.md §Estructura de carpetas",
        },
    },
    "INVALID_ACTION": {
        "category": "validation",
        "severity": "error",
        "message": "La acción o comando especificado no es válido.",
        "recovery": {
            "action": "fix_input",
            "hint": "Ejecutar el script con --help para ver las acciones disponibles.",
            "docs": None,
        },
    },
    # El caso más repetido de AP-52 en el repo: una tool comprueba que un valor
    # pertenece a un vocabulario cerrado y, al fallar, devolvía la frase con los
    # válidos y nada que un consumidor pudiera mirar. La frase se conserva —es
    # buena— pero ahora viaja como `message` de un envelope con `error_code`.
    "INVALID_VALUE": {
        "category": "validation",
        "severity": "error",
        "message": "El valor no pertenece al vocabulario cerrado de ese campo.",
        "recovery": {
            "action": "fix_input",
            "hint": "El mensaje enumera los valores admitidos; usar uno de ellos. "
                    "Si el vocabulario es de dominio, la fuente es vault_norms.",
            "docs": "vault-obsidian-architecture.md §Vocabularios",
        },
    },
    # Distinto de JSON_PARSE_ERROR a propósito: aquel habla de un índice del
    # vault y su recovery es `vault_reindex`, que aquí no arregla nada — el JSON
    # malformado lo escribió quien invocó la tool, en la propia línea de comandos.
    "ARG_JSON_INVALID": {
        "category": "validation",
        "severity": "error",
        "message": "Un argumento que espera JSON no se pudo parsear.",
        "recovery": {
            "action": "fix_input",
            "hint": "Revisar las comillas del argumento: en PowerShell y en cmd "
                    "el escapado de un JSON en línea no es el de bash.",
            "docs": None,
        },
    },
    "FRONTMATTER_MISSING": {
        "category": "validation",
        "severity": "warning",
        "message": "La nota no tiene frontmatter YAML válido.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_write",
            "args": ["--path", "<path>", "--title", "<title>"],
            "hint": "Usar vault_write para reescribir la nota con frontmatter completo.",
            "docs": "vault-obsidian-architecture.md §Frontmatter obligatorio",
        },
    },
    "FRONTMATTER_PARSE_ERROR": {
        "category": "validation",
        "severity": "warning",
        "message": "El frontmatter YAML no se pudo parsear.",
        "recovery": {
            "action": "manual",
            "hint": "Abrir la nota en Obsidian y corregir el bloque --- manualmente.",
            "docs": "vault-obsidian-architecture.md §Frontmatter obligatorio",
        },
    },
    # ── Governance (antipatrones del estándar) ────────────────────────────────
    "AP20_EMPTY_LIST": {
        "category": "governance",
        "severity": "error",
        "message": "AP-20: Más del 50% de los bullets están vacíos (deceptive skeleton).",
        "recovery": {
            "action": "fix_input",
            "hint": "Completar o eliminar los bullets vacíos antes de guardar.",
            "docs": "vault-obsidian-architecture.md §AP-20",
        },
    },
    "AP21_PATH_WIKILINKS": {
        "category": "governance",
        "severity": "error",
        "message": "AP-21: Se detectaron wiki-links con ruta (path-anchored). Usar solo [[nombre-nota]].",
        "recovery": {
            "action": "fix_input",
            "hint": "Reemplazar [[carpeta/nota]] por [[nota]] en todos los links del contenido.",
            "docs": "vault-obsidian-architecture.md §AP-21",
        },
    },
    "WIKILINK_SYNTAX_ERROR": {
        "category": "governance",
        "severity": "error",
        "message": "Wiki-link mal formado: corchetes extra, cierre/apertura faltante, target vacio o brackets anidados.",
        "recovery": {
            "action": "fix_input",
            "hint": "Usar exactamente [[nombre-nota]] o [[nombre-nota|alias]]. No usar [[[...]]], [[...]]], [[]], [[carpeta/nota]], ni links sin cierre.",
            "docs": "vault-obsidian-architecture.md AP-21",
        },
    },
    "AP17_DUPLICATE_TITLE": {
        "category": "governance",
        "severity": "warning",
        "message": "AP-17: Posible canonical-shadow: existe otra nota con título muy similar.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_audit",
            "args": [],
            "hint": "Ejecutar vault_audit para identificar pares duplicados y decidir cuál es la nota canónica.",
            "docs": "vault-obsidian-architecture.md §AP-17, PAT-3",
        },
    },
    "AP18_HASH_DUPLICATE": {
        "category": "governance",
        "severity": "warning",
        "message": "AP-18: Contenido duplicado detectado en otra carpeta.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_audit",
            "args": [],
            "hint": "Ejecutar vault_audit --hash para identificar duplicados exactos cross-folder.",
            "docs": "vault-obsidian-architecture.md §AP-18, PAT-3",
        },
    },
    "AP19_SHADOW_INDEX": {
        "category": "governance",
        "severity": "error",
        "message": "AP-19: Se intentó crear un índice sombra. Ya existe index.md en esta sección.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_section_index",
            "args": ["--folder", "<folder>"],
            "hint": "Usar vault_section_index para actualizar el índice existente.",
            "docs": "vault-obsidian-architecture.md §AP-19",
        },
    },
    "CONTENT_TOO_SHORT": {
        "category": "governance",
        "severity": "error",
        "message": "El contenido es demasiado corto (menos de 3 líneas). No se puede guardar una nota vacía.",
        "recovery": {
            "action": "fix_input",
            "hint": "Agregar al menos 3 líneas de contenido sustantivo.",
            "docs": "vault-obsidian-architecture.md §PAT-2",
        },
    },
    # ── IO ────────────────────────────────────────────────────────────────────
    "ENCODING_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "Problema de encoding al leer o escribir. Se aplicó fallback latin-1.",
        "recovery": {
            "action": "manual",
            "hint": "El archivo tiene encoding no UTF-8. Abrirlo en un editor que soporte recodificación y guardarlo como UTF-8.",
            "docs": None,
        },
    },
    "JSON_PARSE_ERROR": {
        "category": "io",
        "severity": "error",
        "message": "El archivo JSON del índice está corrupto o mal formado.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_reindex",
            "args": [],
            "hint": "Ejecutar vault_reindex para regenerar los índices desde cero.",
            "docs": None,
        },
    },
    "JSON_WRITE_ERROR": {
        "category": "io",
        "severity": "error",
        "message": "No se pudo serializar la salida como JSON.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el contenido de la nota: puede contener caracteres de control no serializables.",
            "docs": None,
        },
    },
    # ── Dependency ────────────────────────────────────────────────────────────
    # El contador de tokens habla con un servicio local que puede no estar
    # levantado. Sin código, el consumidor tenía que distinguir "no arrancó",
    # "no responde" y "no está corriendo" leyendo tres frases distintas.
    "SERVICE_UNAVAILABLE": {
        "category": "dependency",
        "severity": "error",
        "message": "El servicio local no está disponible.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_token_counter",
            "args": ["start-service"],
            "hint": "Levantar el servicio con `start-service`, o comprobar el "
                    "puerto si ya hay otro proceso escuchando.",
            "docs": None,
        },
    },
    "DEPENDENCY_MISSING": {
        "category": "dependency",
        "severity": "warning",
        "message": "Dependencia opcional no disponible. Se usó modo fallback.",
        "recovery": {
            "action": "manual",
            "hint": "Instalar la dependencia con pip. Ejemplo: pip install nltk",
            "docs": None,
        },
    },
    "PYTHON_VERSION": {
        "category": "dependency",
        "severity": "warning",
        "message": "Versión de Python inferior a la recomendada (3.9+).",
        "recovery": {
            "action": "manual",
            "hint": "Usar Python 3.9 o superior.",
            "docs": None,
        },
    },
    # ── Not found ─────────────────────────────────────────────────────────────
    "NOTE_NOT_FOUND": {
        "category": "not_found",
        "severity": "error",
        "message": "La nota especificada no existe en el vault.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_search",
            "args": ["--query", "<title>"],
            "hint": "Usar vault_search para localizar la nota por título, tags o contenido.",
            "docs": None,
        },
    },
    "PROJECT_NOT_FOUND": {
        "category": "not_found",
        "severity": "error",
        "message": "El proyecto especificado no tiene carpeta en 01_Projects/.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_project_overview",
            "args": ["--project", "<project>"],
            "hint": "Usar vault_project_overview --project <slug> para crear la estructura inicial del proyecto.",
            "docs": "vault-obsidian-architecture.md §Grupo 2 — Proyectos",
        },
    },
    "VERSION_NOT_FOUND": {
        "category": "not_found",
        "severity": "error",
        "message": "No se encontró la versión del estándar especificada.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_standard_upgrade",
            "args": ["--check"],
            "hint": "Ejecutar vault_standard_upgrade --check para ver versiones disponibles.",
            "docs": "vault-obsidian-architecture.md §Versionado del estándar",
        },
    },
    # ── Baselines de deuda ────────────────────────────────────────────────────
    # Los tres audits con baseline (AP-37, AP-51, AP-52) fallan de tres maneras
    # que el consumidor tiene que poder distinguir: el formato es viejo, la
    # traducción no cuadra, o la operación aumentaría la deuda en silencio. Las
    # tres se resolvían antes con un `{"ok": False, "error": "..."}` a mano,
    # que es AP-52 dentro del guard de AP-52.
    "MIGRATION_REQUIRED": {
        "category": "validation",
        "severity": "error",
        "message": "La baseline usa un formato anterior y debe migrarse antes de auditar.",
        "recovery": {
            "action": "run_tool",
            "tool": "<la misma tool>",
            "args": ["--migrate"],
            "hint": (
                "Correr la tool con --migrate. Tratar una baseline vieja como "
                "vacía estrenaría la deuda entera como nueva."
            ),
            "docs": "CLAUDE.md §Trabajar con las baselines",
        },
    },
    "MIGRATION_MISMATCH": {
        "category": "validation",
        "severity": "error",
        "message": "La baseline congelada no coincide con lo medido: migrar ahora sería una amnistía.",
        "recovery": {
            "action": "manual",
            "hint": (
                "Dejar el árbol en verde con el formato viejo (--check --strict) "
                "y volver a migrar. Migrar sobre un árbol divergente mete la "
                "deuda nueva en el formato nuevo como si siempre hubiera estado."
            ),
            "docs": "CLAUDE.md §Trabajar con las baselines",
        },
    },
    "DEBT_WOULD_GROW": {
        "category": "validation",
        "severity": "error",
        "message": "Congelar ahora aumentaría la deuda: hay sitios sin precedente en la baseline.",
        "recovery": {
            "action": "manual",
            "hint": (
                "Saldar los sitios nuevos, o congelarlos explícitamente con "
                "--freeze --admitir-nuevos, que los deja listados en el envelope."
            ),
            "docs": "CLAUDE.md §Trabajar con las baselines",
        },
    },
    "CONTRACT_FIELD_REMOVED": {
        "category": "governance",
        "severity": "error",
        "message": (
            "Un campo publicado desapareció del contrato: el consumidor que lo "
            "leía se rompe sin aviso."
        ),
        "recovery": {
            "action": "manual",
            "hint": (
                "Un campo estable no se borra: se anota en `superseded_fields` "
                "con `superseded_by` y `why`, y se sigue emitiendo. Si el campo "
                "nunca fue público, decláralo en `internal_fields` antes de "
                "quitarlo."
            ),
            "docs": "CLAUDE.md §No-derogación",
        },
    },
    # ── Lifecycle ─────────────────────────────────────────────────────────────
    "TOOL_TIMEOUT": {
        "category": "infrastructure",
        "severity": "error",
        "message": "La tool excedió el timeout configurado y fue terminada.",
        "recovery": {
            "action": "retry",
            "hint": "Reducir el alcance de la operación (usar --folder, --limit, --project) o aumentar VAULT_TOOL_TIMEOUT env var.",
            "docs": None,
        },
    },
    # ── Catch-all ─────────────────────────────────────────────────────────────
    "UNEXPECTED_ERROR": {
        "category": "infrastructure",
        "severity": "critical",
        "message": "Error inesperado no clasificado.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
}


def get_error(code: str) -> Dict[str, Any]:
    """Return error metadata for a code, or UNEXPECTED_ERROR as fallback."""
    return ERROR_CATALOG.get(code, ERROR_CATALOG["UNEXPECTED_ERROR"])
