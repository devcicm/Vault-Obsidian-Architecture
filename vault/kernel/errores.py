#!/usr/bin/env python3
"""Contrato estable de errores del toolkit.

Esta hoja posee el catálogo y la forma del envelope que consumen tanto el
producto instalado como el adaptador histórico ``vault_errors``. No registra
trazas ni conoce ``scripts/``: esas son responsabilidades del adaptador.
"""

import copy
import traceback
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Mapping, Optional, TypedDict


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
    "DISK_FULL": {
        "category": "infrastructure",
        "severity": "critical",
        "message": "No queda espacio en disco para completar la operación.",
        "recovery": {
            "action": "retry",
            "hint": "Liberar espacio en disco y reintentar. Si persiste, verificar que no hay otro proceso llenando el disco y comprobar permisos de escritura.",
            "docs": None,
        },
    },
    "PERMISSION_DENIED": {
        "category": "infrastructure",
        "severity": "error",
        "message": "No se tiene permiso de escritura en el directorio destino.",
        "recovery": {
            "action": "manual",
            "hint": "Verificar que el proceso tiene permisos de escritura en el directorio destino. En Windows, verificar que el archivo no está abierto por otro programa.",
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
            # 2026-10-01: era `args: []` con la misma pista, y sin `--graph`
            # vault_reindex solo escribe search-index.json: quien seguía la
            # recuperación al pie de la letra seguía sin graph.json.
            "args": ["--graph"],
            "hint": "Ejecutar vault_reindex --graph para regenerar todos los índices (graph.json, search-index.json); sin --graph solo se regenera search-index.json.",
            "docs": "vault-obsidian-architecture.md §Grupo 10 — Indexación",
        },
    },
    # 2026-10-07: `vault_reindex --check` devolvía `status: index_stale` sin
    # código, y el agente que decide por `recovery.action` no tenía salida.
    "INDEX_STALE": {
        "category": "infrastructure",
        "severity": "warning",
        "message": "El índice no refleja las notas que hay en disco o no se puede leer (AP-47).",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_reindex",
            "args": ["--graph"],
            "hint": "Ejecutar vault_reindex --graph para reconstruir search-index.json y graph.json desde el disco; el detalle está en missing_in_index y stale_in_index.",
            "docs": "vault-obsidian-architecture.md §Grupo 10 — Indexación",
        },
    },
    # 2026-10-07: `vault_drift_detect --mode report` sin snapshot sobre un repo
    # sin git salía como INDEX_NOT_FOUND, y su recuperación (`vault_reindex`)
    # no crea el snapshot que falta: el agente la seguía y seguía igual.
    "DRIFT_SNAPSHOT_MISSING": {
        "category": "not_found",
        "severity": "warning",
        "message": "No hay snapshot del repo con el que comparar, y el repo no tiene git.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_drift_detect",
            "args": ["--project", "<project>", "--mode", "snapshot"],
            "hint": "Tomar el snapshot con --mode snapshot al empezar a trabajar en el proyecto; el --mode report del cierre compara contra él.",
            "docs": "vault-obsidian-architecture.md §AP-63",
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
    # v40.29 — los dos que faltaban para que las causas del dominio de
    # durabilidad tuvieran traducción. Sin ellos habría que haber mapeado
    # «backup inexistente» a `FILE_NOT_FOUND`, cuya recuperación manda ejecutar
    # `vault_search` sobre las notas: un `recovery` que no recupera es peor que
    # no tenerlo, porque el consumidor sí lo obedece.
    "BACKUP_NOT_FOUND": {
        "category": "not_found",
        "severity": "error",
        "message": "No existe un snapshot con ese nombre.",
        "recovery": {
            "action": "run_tool",
            # `vault_backup --list` no existe; lista quien se llama así.
            "tool": "vault_backup_list",
            "args": [],
            "hint": "Listar los snapshots disponibles y reintentar con un "
                    "nombre de la lista. `searched` dice dónde se buscó.",
            "docs": None,
        },
    },
    "BACKUP_MANIFEST_INVALID": {
        "category": "io",
        "severity": "error",
        "message": "El manifiesto del snapshot no sirve para verificar su huella.",
        "recovery": {
            "action": "manual",
            "hint": "El campo `causa` distingue los tres casos: sin manifiesto, "
                    "manifiesto ilegible (la copia puede estar truncada) o "
                    "manifiesto sin merkle_root (copia anterior a v29, que no "
                    "es corrupción sino que aún no se sellaba).",
            "docs": None,
        },
    },
    "MODEL_PROFILE_UNKNOWN": {
        "category": "infrastructure",
        "severity": "warning",
        "message": "El perfil de modelo no se reconoció. Se usa budget de fallback.",
        "recovery": {
            "action": "auto",
            "hint": "El servidor MCP mapeó clientInfo a un perfil inexistente. Budget ajustado a 2000 tokens.",
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
        "message": "La carpeta destino no es una sección del vault.",
        # v41.2: mandaba a `vault_audit` y a «una carpeta de la estructura
        # estándar». Desde las secciones propias, la que enseña dónde se puede
        # escribir es `vault_section --list`, que es lo que ya decía la pista
        # de cada sitio que emite este código.
        "recovery": {
            "action": "run_tool",
            "tool": "vault_section",
            "args": ["--list"],
            "hint": "Elegir una sección del vault (vault_section --list enseña las del "
                    "estándar y las propias) o declarar una propia NN_Nombre con "
                    "vault_section --add.",
            "docs": "vault-obsidian-architecture.md §Estructura de carpetas",
        },
    },
    # Los dos códigos de la frontera de proceso de la CLI consolidada. Antes de
    # v40.9 `cli/` no importaba `vault_errors` en ninguna parte: sus doce fallos
    # salían como `{"ok": False, "error": "..."}` a mano, sin `error_code` ni
    # `recovery`, justo en el punto donde el consumidor lee el error. La puerta
    # de AP-52 estaba en verde porque su alcance no llegaba a `cli/`.
    "PREFLIGHT_REJECTED": {
        "category": "validation",
        "severity": "error",
        "message": "La operación no pasó las guardas de seguridad previas.",
        "recovery": {
            "action": "fix_input",
            "hint": "Revisar `findings`: cada hallazgo dice qué campo y por qué. "
                    "Ninguna escritura ocurrió. Repetir con --force asume el riesgo.",
            "docs": "vault-obsidian-architecture.md §Guards anti-poison",
        },
    },
    "INTERRUPTED": {
        "category": "infrastructure",
        "severity": "warning",
        "message": "La operación se interrumpió antes de terminar.",
        "recovery": {
            "action": "retry",
            "hint": "Un lote interrumpido puede haber ejecutado parte de sus olas: "
                    "comprobar el estado con `vault_audit` antes de reintentar.",
            "docs": None,
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
    "RESERVED_NAME": {
        "category": "validation",
        "severity": "error",
        "message": "El nombre produce un archivo de nombre reservado para índices generados automáticamente.",
        "recovery": {
            "action": "fix_input",
            "hint": "Los nombres reservados son 'index' y 'readme' (y sus variantes con mayúsculas). "
                    "Son nombres de los índices de sección y maestro; elegir otro título.",
            "docs": None,
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
            # `vault_write` no tiene `--path`: la nota se nombra por carpeta y título.
            "args": ["--folder", "<folder>", "--title", "<title>", "--content", "<content>"],
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
    "IDENTITY_CONFLICT": {
        "category": "validation",
        "severity": "error",
        "message": "La identidad de la nota (category+slug) ya existe con un project diferente.",
        "recovery": {
            "action": "fix_input",
            "hint": "Cambiar el título (slug) para crear una nota distinta, o usar el project correcto.",
            "docs": "vault-obsidian-architecture.md §FL-01",
        },
    },
    "CONFLICTING_ARGS": {
        "category": "validation",
        "severity": "error",
        "message": "Dos flags de CLI mutuamente excluyentes fueron proporcionados juntos.",
        "recovery": {
            "action": "fix_input",
            "hint": "Revisar la ayuda de la tool y elegir solo una de las opciones en conflicto.",
            "docs": None,
        },
    },
    "STALE_REPORT": {
        "category": "validation",
        "severity": "error",
        "message": (
            "El reporte quedó obsoleto: el archivo cambió entre el análisis y la "
            "operación. Aplicar el fix revertirá la edición que se hizo en el "
            "interino."
        ),
        "recovery": {
            "action": "retry",
            "hint": "Volver a ejecutar la tool para generar un reporte fresco con el estado actual del archivo.",
            "docs": None,
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
    "CIRCULAR_WIKILINK": {
        "category": "governance",
        "severity": "warning",
        "message": "Se detectó un ciclo de wikilinks en el grafo: A→B→C→A.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_graph_fix",
            "args": [],
            "hint": "Ejecutar vault_graph_fix para romper el ciclo automáticamente, o revisar manualmente los wikilinks en las notas del ciclo.",
            "docs": "vault-obsidian-architecture.md §Grafos",
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
            # `--hash` no existe: el audit por defecto ya detecta AP-18.
            "hint": "Ejecutar vault_audit: el informe lista los duplicados exactos cross-folder bajo AP-18.",
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
    # Distinto de JSON_PARSE_ERROR a propósito: aquel es un índice derivado que
    # `vault_reindex` regenera; este es un fichero de datos de origen —las
    # relaciones de un proyecto— que nada regenera. Reescribirlo con lo que se
    # pudo leer, que es nada, borra lo que guardaba.
    "DATA_FILE_CORRUPT": {
        "category": "io",
        "severity": "error",
        "message": "Un fichero de datos de origen está mal formado; no se reescribe.",
        "recovery": {
            "action": "manual",
            "hint": "Corregir el fichero a mano o restaurarlo desde git o un backup, y repetir.",
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
    "YAML_UNAVAILABLE": {
        "category": "dependency",
        "severity": "warning",
        "message": "PyYAML no está disponible. El frontmatter no se verificó.",
        "recovery": {
            "action": "manual",
            "hint": "Instalar PyYAML: pip install PyYAML. Sin ella, el frontmatter no se valida y puede contener errores de sintaxis que pasen desapercibidos.",
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
    "MODULE_NOT_FOUND": {
        "category": "not_found",
        "severity": "error",
        "message": "El módulo Python especificado no existe en scripts/.",
        "recovery": {
            "action": "fix_input",
            "hint": "Verificar el nombre del módulo: usar el stem sin ruta ni extensión (ej. vault_kernel, no scripts/vault_kernel.py).",
            "docs": None,
        },
    },
    "PREFERENCE_NOT_FOUND": {
        "category": "not_found",
        "severity": "error",
        "message": "La nota de preferencia especificada no existe.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_preferences",
            "args": ["--list"],
            "hint": "Ejecutar vault_preferences --list para ver las preferencias disponibles.",
            "docs": "vault-obsidian-architecture.md §Grupo 34 — Memoria de Contexto",
        },
    },
    "PROJECT_NOT_FOUND": {
        "category": "not_found",
        "severity": "error",
        "message": "El proyecto especificado no tiene carpeta en 01_Projects/.",
        "recovery": {
            "action": "run_tool",
            "tool": "vault_project",
            "args": ["--add", "<project>"],
            "hint": "Si el proyecto es nuevo, darlo de alta con vault_project --add <slug>; si es una errata, usar uno de los slugs de `sugerencias`. vault_project --list enseña los registrados.",
            "docs": "vault-obsidian-architecture.md §AP-63",
        },
    },
    "PROJECT_AMBIGUOUS": {
        "category": "validation",
        "severity": "error",
        "message": "El nombre de proyecto lo reclaman varios proyectos registrados.",
        "recovery": {
            "action": "fix_input",
            "hint": "Usar el slug exacto de uno de los candidatos, o quitar el alias duplicado de la ficha project.md que no le corresponde.",
            "docs": "vault-obsidian-architecture.md §AP-63",
        },
    },
    "PROJECT_LOCKED": {
        "category": "governance",
        "severity": "error",
        "message": "La sesión está atada a otro proyecto (VAULT_PROJECT_LOCK=1).",
        "recovery": {
            "action": "fix_input",
            "hint": "Usar el proyecto de la sesión (`session_project`), o abrir otra sesión con VAULT_PROJECT apuntando al proyecto pedido. Si el candado está puesto sin VAULT_PROJECT, fijarla: el candado no se abre solo.",
            "docs": "vault-obsidian-architecture.md §AP-63",
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
            "docs": "AGENTS.md §Trabajar con las baselines",
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
            "docs": "AGENTS.md §Trabajar con las baselines",
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
            "docs": "AGENTS.md §Trabajar con las baselines",
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
            "docs": "AGENTS.md §No-derogación",
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
    # v40.34: leer-modificar-escribir una nota sin lock perdía appends
    # concurrentes con ok:true. Con lock, quien no lo consigue a tiempo no
    # escribe nada y lo dice: la nota queda como la dejó el otro escritor.
    "NOTE_LOCKED": {
        "category": "infrastructure",
        "severity": "error",
        "message": "Otra escritura tiene la nota bloqueada; no se escribió nada.",
        "recovery": {
            "action": "retry",
            "hint": "Reintentar la misma llamada: la nota no se modificó.",
            "docs": None,
        },
    },
    # ── Catch-all ─────────────────────────────────────────────────────────────
    # ── Catalogados en v40.34 (D3) ────────────────────────────────────────────
    # Se emitían por `emit_error` sin estar aquí: el envelope llevaba el código
    # pero category/severity/recovery de UNEXPECTED_ERROR, así que el
    # consumidor recibía un nombre que el catálogo no declaraba y una
    # recuperación que no era la suya. Se conservan los nombres byte a byte —
    # tests y consumidores los leen— y `vault_error_contract` falla desde
    # entonces ante un código literal que no esté en este dict.
    "PARSE_FAILED": {
        "category": "validation",
        "severity": "error",
        "message": "No se reconoció la estructura esperada en el documento de entrada.",
        "recovery": {
            "action": "fix_input",
            "hint": "Comprobar que el documento conserva el formato que la tool documenta.",
            "docs": None,
        },
    },
    "INVALID_INPUT": {
        "category": "validation",
        "severity": "error",
        "message": "El valor de entrada no es válido para esta operación.",
        "recovery": {
            "action": "fix_input",
            "hint": "Revisar el argumento indicado en el mensaje.",
            "docs": None,
        },
    },
    "GIT_UNAVAILABLE": {
        "category": "dependency",
        "severity": "error",
        "message": "No hay repositorio git o git no está disponible.",
        "recovery": {
            "action": "manual",
            "hint": "Ejecutar dentro de un repositorio git con `git` en el PATH.",
            "docs": None,
        },
    },
    "REGISTRY_UNAVAILABLE": {
        "category": "dependency",
        "severity": "error",
        "message": "No se pudo leer un registro canónico del toolkit.",
        "recovery": {
            "action": "manual",
            "hint": "Verificar que la instalación está completa (vault_version).",
            "docs": None,
        },
    },
    "PREFERENCES_UNAVAILABLE": {
        "category": "dependency",
        "severity": "warning",
        "message": "No se pudieron cargar las preferencias; el paquete sale sin ellas.",
        "recovery": {
            "action": "run_tool",
            "hint": "Ejecutar vault_preferences --list para ver el error de origen.",
            "docs": None,
        },
    },
    "GRAPH_LOAD_ERROR": {
        "category": "io",
        "severity": "error",
        "message": "No se pudo leer el grafo del vault.",
        "recovery": {
            "action": "run_tool",
            "hint": "Regenerar el grafo con vault_reindex --graph.",
            "docs": None,
        },
    },
    "CHANGELOG_READ_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo leer el registro de cambios del vault.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "PARSE_FRONTMATTER_ERROR": {
        "category": "validation",
        "severity": "warning",
        "message": "No se pudo leer el frontmatter de una nota; se omite.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "SCAN_ROOT_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo recorrer una raíz de código; se omite.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "TAG_FIX_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo corregir los tags de una nota.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "AST_PARSE_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo analizar un módulo Python; se omite.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "PROFILE_READ_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo leer el perfil instalado; se asume 'full'.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "KEYWORD_EXTRACTION_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudieron extraer palabras clave de una nota; se omite.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "INTEGRITY_PARSE_ERROR": {
        "category": "validation",
        "severity": "warning",
        "message": "No se pudo leer cia_integrity; se asume 'medium'.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "WRITE_REPORT_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo escribir el informe de errores.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "GRAPH_METADATA_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudieron leer los metadatos del grafo enriquecido.",
        "recovery": {
            "action": "run_tool",
            "hint": "Regenerar el grafo con vault_graph_merge.",
            "docs": None,
        },
    },
    "CODE_INDEX_PARSE_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo leer el índice de código; el grafo sale sin esas aristas.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "ENTITY_PARSE_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo leer un fichero de entidades; se omite.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "ENRICHED_PARSE_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo leer el grafo enriquecido previo.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "GRAPH_HISTORY_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo actualizar el histórico del grafo.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "AUTO_INDEX_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo actualizar el índice de sección tras la escritura; la nota sí se escribió.",
        # 2026-10-07: era `run_tool` sin `tool`, con pista a vault_section_index,
        # que no toca el grafo; y `_auto_grafo` emite este mismo código.
        "recovery": {
            "action": "run_tool",
            "tool": "vault_reindex",
            "args": ["--graph"],
            "hint": "Ejecutar vault_reindex --graph: rehace los índices de sección, la búsqueda y el grafo desde el disco.",
            "docs": None,
        },
    },
    "AUTO_TAG_LEDGER_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo actualizar el registro de tags tras la escritura; la nota sí se escribió.",
        "recovery": {
            "action": "run_tool",
            "hint": "Ejecutar vault_tags para regenerar el registro.",
            "docs": None,
        },
    },
    "SPEC_PARSE_ERROR": {
        "category": "io",
        "severity": "error",
        "message": "No se pudo leer tool-spec.json.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "VERSION_READ_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo leer la versión declarada del vault.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "INTROSPECTION_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo introspeccionar una tool; se omite del manifiesto.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "UPDATED_AT_PARSE_ERROR": {
        "category": "validation",
        "severity": "warning",
        "message": "No se pudo leer updated_at; se usa la fecha del fichero.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "INDEX_UPDATE_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudieron actualizar los índices tras el onboarding.",
        "recovery": {
            "action": "run_tool",
            "hint": "Ejecutar vault_reindex.",
            "docs": None,
        },
    },
    "OBSERVABILITY_SCAN_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo completar el análisis de observabilidad.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "DECISION_CREATE_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo crear una nota de decisión durante el onboarding.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "RUNBOOK_CREATE_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo crear un runbook durante el onboarding.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "FLOW_CREATE_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo crear una nota de flujo durante el onboarding.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "REQUIREMENT_CREATE_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo crear una nota de requisito durante el onboarding.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "QUEUE_READ_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo leer la cola de propagación; se parte de una vacía.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "NOTIFY_WRITE_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo marcar una nota como pendiente de revisión.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "REINDEX_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo reindexar una carpeta tras la propagación.",
        "recovery": {
            "action": "run_tool",
            "hint": "Ejecutar vault_reindex.",
            "docs": None,
        },
    },
    "CLEAR_FM_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo limpiar la marca de revisión del frontmatter.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "NORM_CATALOG_UNAVAILABLE": {
        "category": "dependency",
        "severity": "warning",
        "message": "No se pudo leer el catálogo de normas.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "LIFECYCLE_UNAVAILABLE": {
        "category": "dependency",
        "severity": "warning",
        "message": "No se pudo leer el registro de ciclo de vida.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "TOOL_SPEC_UNAVAILABLE": {
        "category": "dependency",
        "severity": "warning",
        "message": "No se pudo leer el contrato de tools.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "VERSION_UNAVAILABLE": {
        "category": "dependency",
        "severity": "warning",
        "message": "No se pudo leer la versión vigente del estándar.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    "SOURCE_READ_ERROR": {
        "category": "io",
        "severity": "warning",
        "message": "No se pudo leer un fichero fuente; se omite.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el trace log en 00_System/.tool-trace.json para el detalle completo del error.",
            "docs": None,
        },
    },
    # Y los que viajaban en envelopes construidos a mano, con `error_code` pero
    # sin el resto del contrato. Catalogarlos no completa esos envelopes —eso
    # es pasarlos por `emit_error`, deuda aparte—, pero el código deja de ser
    # un nombre que solo conoce quien lo escribió: `get_error` ya lo resuelve.
    "EMPTY_QUERY": {
        "category": "validation",
        "severity": "error",
        "message": "La consulta está vacía.",
        "recovery": {
            "action": "fix_input",
            "hint": "Pasar un valor no vacío en el argumento indicado.",
            "docs": None,
        },
    },
    "INVALID_BUDGET": {
        "category": "validation",
        "severity": "error",
        "message": "El presupuesto de tokens no es válido.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "INVALID_DIRECTION": {
        "category": "validation",
        "severity": "error",
        "message": "La dirección de recorrido del grafo no es válida.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "INVALID_HOPS": {
        "category": "validation",
        "severity": "error",
        "message": "El número de saltos no es válido.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "GRAPH_MISSING": {
        "category": "not_found",
        "severity": "error",
        "message": "El vault no tiene grafo generado.",
        "recovery": {
            "action": "run_tool",
            "hint": "Generar el grafo con vault_reindex --graph.",
            "docs": None,
        },
    },
    "NO_SEEDS_RESOLVED": {
        "category": "not_found",
        "severity": "warning",
        "message": "Ninguna semilla de la consulta existe en el grafo.",
        "recovery": {
            "action": "fix_input",
            "hint": "Revisar `unresolved` en el envelope; si la nota es nueva, regenerar el grafo.",
            "docs": None,
        },
    },
    "EMPTY_SOURCE": {
        "category": "validation",
        "severity": "error",
        "message": "La fuente a ingerir está vacía.",
        "recovery": {
            "action": "fix_input",
            "hint": "Pasar un valor no vacío en el argumento indicado.",
            "docs": None,
        },
    },
    "NO_SOURCE": {
        "category": "validation",
        "severity": "error",
        "message": "No se indicó ninguna fuente que ingerir.",
        "recovery": {
            "action": "fix_input",
            "hint": "Pasar --file, --url o --text.",
            "docs": None,
        },
    },
    "SOURCE_NOT_FOUND": {
        "category": "not_found",
        "severity": "error",
        "message": "La fuente indicada no existe.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "SOURCE_UNREADABLE": {
        "category": "io",
        "severity": "error",
        "message": "La fuente indicada no se pudo leer.",
        "recovery": {
            "action": "manual",
            "hint": "Comprobar permisos y codificación del fichero.",
            "docs": None,
        },
    },
    "SOURCE_TOO_LARGE": {
        "category": "validation",
        "severity": "error",
        "message": "La fuente supera el tamaño máximo admitido.",
        "recovery": {
            "action": "fix_input",
            "hint": "Partir la fuente en ficheros más pequeños.",
            "docs": None,
        },
    },
    "INVALID_URL": {
        "category": "validation",
        "severity": "error",
        "message": "La URL no es válida o usa un esquema no admitido.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "NETWORK_DISABLED": {
        "category": "validation",
        "severity": "error",
        "message": "Descargar una URL requiere permiso de red explícito.",
        "recovery": {
            "action": "fix_input",
            "hint": "Descargar el contenido y usar --file, o pasar --allow-network.",
            "docs": None,
        },
    },
    "FETCH_FAILED": {
        "category": "io",
        "severity": "error",
        "message": "No se pudo descargar la URL.",
        "recovery": {
            "action": "retry",
            "hint": "Comprobar la conectividad y reintentar, o descargar y usar --file.",
            "docs": None,
        },
    },
    "FORBIDDEN_SECTION": {
        "category": "governance",
        "severity": "error",
        "message": "La sección no admite ingesta: es generada o de otra tool.",
        "recovery": {
            "action": "fix_input",
            "hint": "Elegir una sección de las que no aparecen en `forbidden`.",
            "docs": None,
        },
    },
    "UNKNOWN_SECTION": {
        "category": "validation",
        "severity": "error",
        "message": "La sección indicada no existe en el vault.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "POISON_DETECTED": {
        "category": "governance",
        "severity": "error",
        "message": "La fuente contiene patrones de inyección; no se escribió nada.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar `preflight` en el envelope; el preflight anti-poison no es desactivable.",
            "docs": None,
        },
    },
    # 2026-10-01 (AP-52): hasta aquí el bloqueo salía como PERMISSION_DENIED,
    # cuya pista manda revisar permisos del disco. El consumidor no podía
    # distinguir «no puedo escribir» de «no debo escribir esto».
    # 2026-10-01 (AP-52): `vault_validate` devolvía `ok: false` sin código
    # cuando el vault tenía notas inválidas. No es un fallo de la tool —la
    # medida terminó y el detalle viaja en `invalid`, `structure` e
    # `indexes`—, pero el consumidor que decide por `recovery.action` no
    # tenía por dónde leerlo.
    "VALIDATION_FAILED": {
        "category": "validation",
        "severity": "error",
        "message": "La validación terminó y encontró notas, carpetas o índices que no cumplen el contrato.",
        "recovery": {
            "action": "fix_input",
            "hint": "El detalle está en `invalid` (nota y motivo), `structure.missing` e `indexes.invalid`. Un frontmatter que no parsea se repara con vault_frontmatter_heal; los campos que faltan se completan con vault_frontmatter_completar (dry-run por defecto, --apply para escribir).",
            "docs": None,
        },
    },
    "SECRET_DETECTED": {
        "category": "governance",
        "severity": "error",
        "message": "El contenido incluye un secreto; no se escribió nada.",
        "recovery": {
            "action": "manual",
            "hint": "Quitar el secreto del contenido y referenciarlo (nombre de la variable de entorno o del gestor de secretos) en vez de copiarlo. `secrets` en el envelope dice qué patrón y en qué línea, ya redactado.",
            "docs": None,
        },
    },
    "NO_CONTENT": {
        "category": "validation",
        "severity": "error",
        "message": "Ningún bloque de la fuente tiene contenido útil suficiente.",
        "recovery": {
            "action": "fix_input",
            "hint": "Aportar una fuente con más contenido.",
            "docs": None,
        },
    },
    "EMPTY_REASON": {
        "category": "validation",
        "severity": "error",
        "message": "La razón es obligatoria.",
        "recovery": {
            "action": "fix_input",
            "hint": "Pasar un valor no vacío en el argumento indicado.",
            "docs": None,
        },
    },
    "EMPTY_STATEMENT": {
        "category": "validation",
        "severity": "error",
        "message": "El enunciado es obligatorio.",
        "recovery": {
            "action": "fix_input",
            "hint": "Pasar un valor no vacío en el argumento indicado.",
            "docs": None,
        },
    },
    "INVALID_CATEGORY": {
        "category": "validation",
        "severity": "error",
        "message": "La categoría no es válida.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "INVALID_STRENGTH": {
        "category": "validation",
        "severity": "error",
        "message": "La fuerza de la preferencia no es válida.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "NOT_A_PREFERENCE": {
        "category": "validation",
        "severity": "error",
        "message": "La nota indicada no es una preferencia.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "NOT_FOUND": {
        "category": "not_found",
        "severity": "error",
        "message": "La nota indicada no existe.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "NOT_QUARANTINED": {
        "category": "validation",
        "severity": "error",
        "message": "La nota indicada no está en cuarentena.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "ORIGIN_OCCUPIED": {
        "category": "validation",
        "severity": "error",
        "message": "La ruta de origen ya está ocupada; restaurar la sobrescribiría.",
        "recovery": {
            "action": "manual",
            "hint": "Mover o renombrar la nota que ocupa el origen antes de restaurar.",
            "docs": None,
        },
    },
    "EMPTY_SYMPTOM": {
        "category": "validation",
        "severity": "error",
        "message": "El síntoma es obligatorio.",
        "recovery": {
            "action": "fix_input",
            "hint": "Pasar un valor no vacío en el argumento indicado.",
            "docs": None,
        },
    },
    "INVALID_DATA_SUBJECT": {
        "category": "validation",
        "severity": "error",
        "message": "El interesado no es válido.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "INVALID_DETECTED_BY": {
        "category": "validation",
        "severity": "error",
        "message": "El origen de la detección no es válido.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "INVALID_ENV": {
        "category": "validation",
        "severity": "error",
        "message": "El entorno no es válido.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "INVALID_IMPACT": {
        "category": "validation",
        "severity": "error",
        "message": "El impacto no es válido.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "INVALID_JSON": {
        "category": "validation",
        "severity": "error",
        "message": "El argumento no contiene JSON válido.",
        "recovery": {
            "action": "fix_input",
            "hint": "Pasar JSON válido en el argumento indicado.",
            "docs": None,
        },
    },
    "INVALID_LEGAL_BASIS": {
        "category": "validation",
        "severity": "error",
        "message": "La base legal no es válida.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "INVALID_LIKELIHOOD": {
        "category": "validation",
        "severity": "error",
        "message": "La probabilidad no es válida.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "INVALID_NCR_TYPE": {
        "category": "validation",
        "severity": "error",
        "message": "El tipo de no conformidad no es válido.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "INVALID_PHASE": {
        "category": "validation",
        "severity": "error",
        "message": "La fase no es válida.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "INVALID_RELEASE_TYPE": {
        "category": "validation",
        "severity": "error",
        "message": "El tipo de release no es válido.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "INVALID_RISK_TYPE": {
        "category": "validation",
        "severity": "error",
        "message": "El tipo de riesgo no es válido.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "INVALID_SEVERITY": {
        "category": "validation",
        "severity": "error",
        "message": "La severidad no es válida.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "INVALID_SLO_TYPE": {
        "category": "validation",
        "severity": "error",
        "message": "El tipo de SLO no es válido.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "INVALID_STATUS": {
        "category": "validation",
        "severity": "error",
        "message": "El status no es válido.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "INVALID_TREATMENT": {
        "category": "validation",
        "severity": "error",
        "message": "El tratamiento no es válido.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "INVALID_WINDOW": {
        "category": "validation",
        "severity": "error",
        "message": "La ventana no es válida.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "missing_agent": {
        "category": "governance",
        "severity": "error",
        "message": "AP-16: falta el agente que firma la escritura.",
        "recovery": {
            "action": "fix_input",
            "hint": "Pasar --agent <nombre> o exportar VAULT_AGENT.",
            "docs": None,
        },
    },
    "READ_ERROR": {
        "category": "io",
        "severity": "error",
        "message": "No se pudo leer el fichero indicado.",
        "recovery": {
            "action": "manual",
            "hint": "Comprobar permisos y codificación del fichero.",
            "docs": None,
        },
    },
    "WRITE_ERROR": {
        "category": "io",
        "severity": "error",
        "message": "No se pudo escribir el fichero indicado.",
        "recovery": {
            "action": "manual",
            "hint": "Comprobar permisos y espacio en disco.",
            "docs": None,
        },
    },
    "UNSUPPORTED_FORMAT": {
        "category": "validation",
        "severity": "error",
        "message": "El formato del fichero no está soportado.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "SPEC_LOAD_ERROR": {
        "category": "io",
        "severity": "error",
        "message": "No se pudo cargar tool-spec.json.",
        "recovery": {
            "action": "manual",
            # Hasta v40.34 decía `vault_compact_contracts`, que lo lee y no lo
            # escribe: el agente obedecía y volvía al mismo error.
            "hint": "Regenerar el contrato con `python scripts/vault_manifest.py --bootstrap`.",
            "docs": None,
        },
    },
    "TOOL_NOT_IN_SPEC": {
        "category": "validation",
        "severity": "error",
        "message": "La tool no tiene entrada en tool-spec.json.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "NOTHING_TO_FIX": {
        "category": "validation",
        "severity": "warning",
        "message": "No hay nada que corregir.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el argumento indicado en el mensaje; el envelope trae los valores admitidos cuando los hay.",
            "docs": None,
        },
    },
    "content_too_short": {
        "category": "governance",
        "severity": "error",
        "message": "El contenido es demasiado corto.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el contenido según la norma que cita `norm_code`.",
            "docs": None,
        },
    },
    "content_empty_list": {
        "category": "governance",
        "severity": "error",
        "message": "El contenido tiene listas vacías (AP-20).",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el contenido según la norma que cita `norm_code`.",
            "docs": None,
        },
    },
    "path_anchored_wikilinks": {
        "category": "governance",
        "severity": "error",
        "message": "Hay wikilinks con ruta (AP-21).",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el contenido según la norma que cita `norm_code`.",
            "docs": None,
        },
    },
    "malformed_wikilinks": {
        "category": "governance",
        "severity": "error",
        "message": "Hay wikilinks mal formados.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el contenido según la norma que cita `norm_code`.",
            "docs": None,
        },
    },
    "mermaid_syntax_error": {
        "category": "governance",
        "severity": "error",
        "message": "Un bloque Mermaid no es válido.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el contenido según la norma que cita `norm_code`.",
            "docs": None,
        },
    },
    "missing_tags": {
        "category": "governance",
        "severity": "error",
        "message": "La nota no lleva tags.",
        "recovery": {
            "action": "fix_input",
            "hint": "Pasar --tags.",
            "docs": None,
        },
    },
    "note_moved": {
        "category": "validation",
        "severity": "error",
        "message": "La nota existe en otra carpeta.",
        "recovery": {
            "action": "run_tool",
            "hint": "Usar vault_move para reubicarla o especificar otra carpeta.",
            "docs": None,
        },
    },
    "illegal_status_transition": {
        "category": "governance",
        "severity": "error",
        "message": "La transición de status no está permitida (AP-41).",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el contenido según la norma que cita `norm_code`.",
            "docs": None,
        },
    },
    # Los que emite el servidor MCP (`mcp/nodejs/vault-mcp-server.mjs`). No
    # puede importar este dict, pero el guard lee sus literales igual.
    "missing_tool_name": {
        "category": "validation",
        "severity": "error",
        "message": "La llamada MCP no nombra ninguna tool.",
        "recovery": {
            "action": "fix_input",
            "hint": "Pasar `name` en tools/call.",
            "docs": None,
        },
    },
    "tool_not_found": {
        "category": "not_found",
        "severity": "error",
        "message": "La tool no existe o no se expone por MCP.",
        "recovery": {
            "action": "fix_input",
            "hint": "Consultar tools/list.",
            "docs": None,
        },
    },
    "INVALID_ARGS": {
        "category": "validation",
        "severity": "error",
        "message": "Los argumentos no cumplen el inputSchema de la tool; no se ejecutó nada.",
        "recovery": {
            "action": "fix_input",
            "hint": "Ajustar los argumentos al inputSchema que publica tools/list.",
            "docs": None,
        },
    },
    "GUARD_CHAIN_FAILED": {
        "category": "governance",
        "severity": "error",
        "message": "La cadena de guards del servidor MCP bloqueó la escritura.",
        "recovery": {
            "action": "fix_input",
            "hint": "Corregir el contenido según el guard que cita el mensaje.",
            "docs": None,
        },
    },
    "TOOL_EXECUTION_FAILED": {
        "category": "infrastructure",
        "severity": "error",
        "message": "El servidor MCP no pudo ejecutar la tool.",
        "recovery": {
            "action": "manual",
            "hint": "Revisar el log del servidor MCP y que VAULT_MCP_PYTHON apunte al Python del toolkit.",
            "docs": None,
        },
    },
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


#: Los códigos del catálogo como tipo (D3, v40.34). Se **deriva** de
#: `ERROR_CATALOG` en vez de escribirse: dos listas de los mismos nombres son
#: dos dueños, y la segunda envejece. Hereda de `str`, así que
#: `ErrorCode.INVALID_PATH == "INVALID_PATH"` y los consumidores que comparan
#: con la cadena no notan nada.
ErrorCode = Enum("ErrorCode", {codigo: codigo for codigo in ERROR_CATALOG}, type=str)
ErrorCode.__doc__ = "Código de error del catálogo; derivado de ERROR_CATALOG."


def get_error(code: str) -> Dict[str, Any]:
    """Return error metadata for a code, or UNEXPECTED_ERROR as fallback."""
    return ERROR_CATALOG.get(getattr(code, "value", code), ERROR_CATALOG["UNEXPECTED_ERROR"])


def construir_error(
    tool: str,
    code: str,
    message: Optional[str] = None,
    args: Optional[Mapping[str, Any]] = None,
    exception: Optional[BaseException] = None,
    extra: Optional[Mapping[str, Any]] = None,
    incluir_traceback: bool = False,
    pista: Optional[str] = None,
) -> Dict[str, Any]:
    """Construye el envelope canónico sin efectos de I/O.

    El consumidor decide por ``error_code`` y ``recovery``; ``extra`` permite
    que una frontera de transporte publique su estado sin reescribir el
    contrato. El adaptador legacy es quien opcionalmente lo registra en trace.

    ``incluir_traceback`` es cerrado por defecto (v40.34): el traceback lleva
    rutas absolutas del intérprete y del usuario, y un envelope es salida para
    terceros. Quien lo quiere lo pide —``emit_error`` con ``VAULT_DEBUG=1``—;
    el kernel no lee el entorno.
    """
    # Un `ErrorCode` viaja como su valor: `json.dumps` lo haría igual, pero un
    # f-string o un `repr` no, y el envelope es contrato con terceros.
    code = getattr(code, "value", code)
    catalog_entry = get_error(code)
    entry: Dict[str, Any] = {
        "ok": False,
        "tool": tool,
        "error_code": code,
        "category": catalog_entry["category"],
        "severity": catalog_entry["severity"],
        "message": message or catalog_entry["message"],
        # Copia, no referencia: el envelope es del invocante y el catálogo es
        # de todos. Una pista añadida a uno no puede llegar a los siguientes.
        "recovery": copy.deepcopy(catalog_entry["recovery"]),
        "timestamp": datetime.now(timezone.utc).isoformat()[:19] + "Z",
    }
    # La pista del sitio es más específica que la del catálogo y va a `hint`;
    # la `action` sigue siendo la del catálogo, que es por la que se decide.
    # Hasta v40.34 nueve sitios la escribían con `env["recovery"] = "…"`
    # después de la llamada y dejaban `recovery` en cadena (AP-52).
    if pista:
        entry["recovery"]["hint"] = pista
    if args:
        entry["args"] = dict(args)
    if exception and incluir_traceback:
        entry["traceback"] = traceback.format_exc()
    if extra:
        entry.update(extra)
    return entry


#: Causa del dominio -> código del catálogo. La otra mitad de la frase que
#: `vault/kernel/fallos.py` empieza: allí se nombra **qué pasó**, aquí **qué
#: puede hacer el consumidor**.
#:
#: Vive en un solo sitio a propósito. La misma tabla repartida entre
#: `vault_folder_registry`, `vault_backup` y `vault_restore` sería AP-57
#: cometido justo al saldar AP-52: tres adaptadores decidiendo por su cuenta
#: qué código le toca a una causa que no es suya. Un test comprueba que cubre
#: `fallos.CAUSAS` entera y que ningún destino falta del `ERROR_CATALOG`.
#:
#: Vivió en `vault_errors` hasta v40.34; bajó al núcleo para que los entry
#: modules de `vault/` —que no importan `scripts/`— traduzcan con la misma
#: tabla en vez de con una copia. `vault_errors` la reexporta.
#:
#: Que tres causas del manifiesto compartan destino no pierde información: la
#: causa exacta viaja en el campo `causa` del envelope. El catálogo dice cómo se
#: recupera, y de las tres se recupera igual.
MAPA_DE_FALLOS: Dict[str, str] = {
    "CARPETA_YA_REGISTRADA": "INVALID_FOLDER",
    "CARPETA_NO_ENCONTRADA": "FOLDER_NOT_FOUND",
    "BACKUP_NO_ENCONTRADO": "BACKUP_NOT_FOUND",
    "MANIFIESTO_AUSENTE": "BACKUP_MANIFEST_INVALID",
    "MANIFIESTO_ILEGIBLE": "BACKUP_MANIFEST_INVALID",
    "MANIFIESTO_SIN_HUELLA": "BACKUP_MANIFEST_INVALID",
    "CONFIRMACION_REQUERIDA": "MISSING_REQUIRED_ARG",
    "INDICE_ILEGIBLE": "DATA_FILE_CORRUPT",
    "FRONTMATTER_ILEGIBLE": "FRONTMATTER_PARSE_ERROR",
    "SECRETO_EN_CONTENIDO": "SECRET_DETECTED",
    "PROYECTO_NO_REGISTRADO": "PROJECT_NOT_FOUND",
    "PROYECTO_AMBIGUO": "PROJECT_AMBIGUOUS",
    "PROYECTO_FUERA_DE_SESION": "PROJECT_LOCKED",
    "LOCK_PERDIDO": "NOTE_LOCKED",
}


def traducir_fallo(fallo: Any) -> "tuple[str, str, Dict[str, Any]]":
    """`(código, mensaje, campos)` de un fallo del dominio, sin construir nada.

    Es la traducción entera: quien emite —`vault_errors.emit_fallo`, con su
    traza, o `envelope_de_fallo`, sin ella— solo decide el transporte. Toma el
    fallo por pato: este módulo es hoja y no importa `fallos`.

    `error` se sigue emitiendo: es un campo estable declarado en
    `field-compat-baseline.json` para `vault_restore`. Lo mismo `hint` y
    `searched`, que llegan por `fallo.datos`.
    """
    causa = getattr(fallo, "causa", None)
    if causa not in MAPA_DE_FALLOS:
        raise ValueError(
            f"causa sin traducción al catálogo: {causa!r}. Añadirla a "
            "MAPA_DE_FALLOS es parte de declararla en fallos.CAUSAS."
        )
    mensaje = getattr(fallo, "mensaje", None) or str(fallo)
    campos: Dict[str, Any] = {"causa": causa, "error": mensaje}
    campos.update(getattr(fallo, "datos", None) or {})
    return MAPA_DE_FALLOS[causa], mensaje, campos


def envelope_de_fallo(tool: str, fallo: Any) -> Dict[str, Any]:
    """El envelope de un fallo del dominio, sin I/O: para el código instalado."""
    codigo, mensaje, campos = traducir_fallo(fallo)
    envelope = construir_error(tool, codigo, mensaje)
    envelope.update(campos)
    return envelope


def mensaje_de(envelope: Mapping[str, Any]) -> Optional[str]:
    """El mensaje de un envelope de error, venga en la forma que venga.

    Desde que todo error pasa por `construir_error` el texto vive en `message`;
    los envelopes escritos a mano que aún quedan lo ponen en `error`. Hasta
    2026-10-02 ocho consumidores leían solo `error`, recibían None y
    `vault_context_pack` culpaba a la consulta de un índice ausente.
    """
    mensaje = envelope.get("message") or envelope.get("error")
    return mensaje if isinstance(mensaje, str) else None


def completar_envelope(tool: str, envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Lleva un envelope de error construido a mano a la forma canónica (D5).

    Medido en v40.34: `vault_write` y `vault_ingest` devolvían `{"ok": False,
    "error_code": …, "error": …}` sin `category`, `severity`, `recovery` ni
    `timestamp`, y el consumidor no tenía `recovery.action` por el que decidir.
    Se aplica en la salida de la tool, no en cada `return`: un solo sitio.

    - Lo propio del sitio (`norm_code`, `fixes`, `preflight`, …) se conserva.
    - Lo canónico (`tool`, `category`, `severity`, `timestamp`) lo pone el
      catálogo; el sitio no lo pisa, porque es lo que el consumidor lee.
    - `message` del sitio gana sobre el del catálogo, y si no hay, `error`.
    - Un `recovery` en cadena es más específico que el del catálogo y pasa a
      `recovery.hint`; la `action` sigue saliendo del catálogo. Un `recovery`
      que ya es dict —el envelope salió de `emit_error(..., pista=)`— conserva
      su `hint`: tirarlo devolvía la pista genérica del catálogo (v41.2).

    Un éxito, o un fallo sin `error_code`, se devuelve tal cual: inventarle un
    código sería el defecto que AP-52 persigue.
    """
    if envelope.get("ok") is not False or not envelope.get("error_code"):
        return envelope
    propio = dict(envelope)
    code = propio.pop("error_code")
    mensaje = mensaje_de(propio)
    propio.pop("message", None)
    recuperacion = propio.pop("recovery", None)
    if isinstance(recuperacion, dict):
        recuperacion = recuperacion.get("hint")
    for clave in _ErrorEnvelopeBase.__annotations__:
        propio.pop(clave, None)
    entry = construir_error(
        tool, code, message=mensaje,
        pista=recuperacion if isinstance(recuperacion, str) else None,
    )
    entry.update(propio)
    return entry


# ── DTOs del envelope (D5, v40.34) ────────────────────────────────────────────
#
# La forma que `construir_error` produce, escrita como tipo. Hasta aquí el
# contrato solo existía como el cuerpo de una función: 349 firmas devolvían
# `Dict[str, Any]` y ninguna decía qué claves trae. Python 3.9 no tiene
# `NotRequired`, así que lo obligatorio va en la base y lo opcional en la
# subclase `total=False`.


class Recovery(TypedDict):
    action: str
    hint: str
    docs: Optional[str]


class _ErrorEnvelopeBase(TypedDict):
    ok: Literal[False]
    tool: str
    error_code: str
    category: str
    severity: str
    message: str
    recovery: Recovery
    timestamp: str


class ErrorEnvelope(_ErrorEnvelopeBase, total=False):
    args: Dict[str, Any]
    traceback: str


class OkEnvelope(TypedDict, total=False):
    """El de éxito solo garantiza `ok`; el resto es de cada tool."""
    ok: Literal[True]
    tool: str


def problemas_de_forma(envelope: Mapping[str, Any]) -> List[str]:
    """Qué le falta a un envelope de error para cumplir `ErrorEnvelope`.

    Lista vacía si cumple. Es el criterio del consumidor (AP-44): el servidor
    MCP y `cli/` deciden por `error_code` y `recovery.action`, así que eso es lo
    que se mide, sobre el envelope real y no sobre la función que lo construye.
    """
    problemas: List[str] = []
    if envelope.get("ok") is not False:
        return ["ok no es False"]
    for clave, tipo in _ErrorEnvelopeBase.__annotations__.items():
        if clave not in envelope:
            problemas.append(f"falta {clave}")
        elif tipo is str and not isinstance(envelope[clave], str):
            problemas.append(f"{clave} no es str")
    rec = envelope.get("recovery")
    if isinstance(rec, Mapping):
        problemas += [f"falta recovery.{k}" for k in Recovery.__annotations__ if k not in rec]
    elif "recovery" in envelope:
        problemas.append("recovery no es un objeto")
    codigo = envelope.get("error_code")
    if isinstance(codigo, str) and codigo not in ERROR_CATALOG:
        problemas.append(f"error_code {codigo!r} fuera de ERROR_CATALOG")
    return problemas
