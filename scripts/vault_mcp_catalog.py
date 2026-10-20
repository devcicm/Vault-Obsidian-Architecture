#!/usr/bin/env python3
"""
Vault MCP Catalog — Catálogo canónico de tools del vault.

Contiene la definición de todas las tools (cuántas, `len(TOOLS_CATALOG)`) con sus:
- Propósito
- Parámetros
- Validadores
- Guards
- Efectos secundarios
- Ejemplos
- Tools relacionadas

Este catálogo es la fuente de verdad para el orquestador MCP.
"""

import argparse
import json
import os
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import vault_grafo_import
from vault_version import CURRENT_VERSION
from vault_registry import runtime_seed_projection

#: Raíz del repo — el guard de `js_native_tools` cruza a `mcp/nodejs/`.
REPO_ROOT = Path(__file__).resolve().parent.parent


def _product_catalog_path() -> Path:
    """Ruta física de la proyección empaquetada del catálogo canónico.

    ``REPO_ROOT`` es deliberadamente sustituible en pruebas de la frontera
    JS-native: representa el árbol que se quiere inspeccionar para el `.mjs`.
    La proyección de producto, en cambio, pertenece a esta fuente canónica y
    no debe desaparecer cuando el fixture hace ese árbol hostil.
    """
    return Path(__file__).resolve().parent.parent / "vault" / "meta_toolkit" / "tools-catalog.json"


def _runtime_seed_path() -> Path:
    """Ruta de la semilla que `vault init` lee desde el paquete instalado."""
    return Path(__file__).resolve().parent.parent / "vault" / "ciclo_de_vida" / "runtime-seed.json"


def _runtime_seed_text() -> str:
    """La semilla tal como debe estar, derivada de `vault_registry`.

    Es la otra proyección empaquetada que lleva la versión. En v40.35 el bump
    la dejó en v40.34 porque nadie la escribía ni la comparaba: `vault init`
    sellaba runtimes que `vault doctor` rechazaba como STANDARD_INCOMPATIBLE,
    y solo un test de la suite lo veía. Ahora viaja con el catálogo: `--sync`
    la escribe y `--check`, que es puerta, falla si envejece.
    """
    return json.dumps(runtime_seed_projection(), indent=2, ensure_ascii=False) + "\n"


TOOLS_CATALOG: Dict[str, Dict[str, Any]] = {
    "vault_write": {
        "name": "vault_write",
        "script": "vault_write.py",
        "group": "Core",
        "purpose": "Crea o actualiza notas con frontmatter YAML correcto. Versiona en .history/ antes de sobreescribir.",
        "params": {
            "folder": {
                "type": "string",
                "required": True,
                "description": "Ruta relativa al vault (ej: 01_Projects/mi-api)",
                "validators": ["no_absolute", "no_traversal", "within_vault"],
            },
            "title": {
                "type": "string",
                "required": True,
                "description": "Título de la nota",
                "validators": ["not_empty", "max_length:200"],
            },
            "content": {
                "type": "string",
                "required": True,
                "description": "Contenido Markdown (solo por CLI: @file:ruta lee de un archivo)",
                "validators": [
                    "min_lines:3",
                    "min_words:10",
                    "no_empty_bullets",
                    "no_path_anchored_links",
                    "no_bracket_anomalies",
                ],
            },
            "tags": {
                "type": "list",
                "required": False,
                "description": "Etiquetas separadas por espacio",
                "validators": [],
            },
            "meta": {
                "type": "json",
                "required": False,
                "description": "JSON con frontmatter adicional",
                "validators": ["valid_json"],
            },
            "meta-file": {
                "type": "string",
                "required": False,
                "description": "Ruta a archivo JSON con frontmatter adicional",
                "validators": ["file_exists", "valid_json_file"],
            },
        },
        "guards": [
            "AP-20 (no bullets vacíos)",
            "AP-21 (no [[/note]])",
            "AP-22 (no [[]] vacíos)",
        ],
        "side_effects": [
            "Versiona en .history/",
            "Actualiza search-index.json",
            "Regenera section index",
        ],
        "example": 'python vault_write.py --folder "01_Projects/mi-api" --title "Overview" --content "@file:overview.md" --tags api backend --agent mi-agente',
        "related": ["vault_read", "vault_append", "vault_audit"],
    },
    "vault_read": {
        "name": "vault_read",
        "script": "vault_read.py",
        "group": "Core",
        "purpose": ("Lee una nota del vault por ruta relativa o por nombre "
                    "(stem o alias: el criterio con el que Obsidian resuelve; "
                    "`title:` no es clave de resolución)."),
        "params": {
            "path": {
                "type": "string",
                "required": False,
                "description": "Ruta relativa al vault (ej: 01_Projects/mi-api/overview.md)",
                "validators": ["within_vault"],
            },
        },
        "guards": [],
        "side_effects": [],
        "example": 'python vault_read.py --path "01_Projects/mi-api/overview.md"',
        "related": ["vault_write", "vault_search"],
    },
    "vault_search": {
        "name": "vault_search",
        "script": "vault_search.py",
        "group": "Core",
        "purpose": "Búsqueda full-text en search-index.json con score ponderado.",
        "params": {
            "query": {
                "type": "string",
                "required": True,
                "description": "Término de búsqueda",
                "validators": ["not_empty"],
            },
            "folder": {
                "type": "string",
                "required": False,
                "description": "Filtrar por carpeta",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": [],
        "example": 'python vault_search.py --query "circuit breaker"\npython vault_search.py --query "deploy" --folder "01_Projects"',
        "related": ["vault_read", "vault_list"],
    },
    "vault_list": {
        "name": "vault_list",
        "script": "vault_list.py",
        "group": "Core",
        "purpose": "Lista notas de una carpeta del vault.",
        "params": {
            "folder": {
                "type": "string",
                "required": False,
                "description": "Carpeta a listar (sin vault root)",
                "validators": [],
            },
            "status": {
                "type": "string",
                "required": False,
                "description": "Filtrar por status",
                "validators": [],
            },
            "limit": {
                "type": "int",
                "required": False,
                "description": "Límite de resultados (default: 50)",
                "validators": ["min:1", "max:500"],
            },
        },
        "guards": [],
        "side_effects": [],
        "example": 'python vault_list.py\npython vault_list.py --folder "01_Projects"',
        "related": ["vault_search", "vault_read"],
    },
    "vault_append": {
        "name": "vault_append",
        "script": "vault_append.py",
        "group": "Core",
        "purpose": "Agrega contenido al final de una nota existente (modo append-only).",
        "params": {
            "path": {
                "type": "string",
                "required": True,
                "description": "Ruta relativa de la nota",
                "validators": ["within_vault", "file_exists"],
            },
            "content": {
                "type": "string",
                "required": True,
                "description": "Contenido a agregar",
                "validators": ["not_empty"],
            },
            "section": {
                "type": "string",
                "required": False,
                "description": "Encabezado de sección donde agregar",
                "validators": [],
            },
        },
        "guards": [],
        # O2: el registro decía que añadir texto no tenía efecto. Lo tiene y
        # no es solo el texto: la nota cambia y queda anotada en la bitácora.
        "side_effects": [
            "Añade contenido a la nota existente y refresca su updatedAt",
            "Anota el cambio en el change-log (F8, no repudio)",
        ],
        "example": 'python vault_append.py --path "01_Projects/mi-api/changelog.md" --content "## v1.2\\n\\nFix deploy"',
        "related": ["vault_write", "vault_read"],
    },
    "vault_diff": {
        "name": "vault_diff",
        "script": "vault_diff.py",
        "group": "Core",
        "purpose": "Muestra diferencias entre versiones de una nota.",
        "params": {
            "path": {
                "type": "string",
                "required": True,
                "description": "Ruta de la nota",
                "validators": ["within_vault"],
            },
            "version": {
                "type": "string",
                "required": False,
                "description": "Número de versión a comparar (default: última)",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": [],
        "example": 'python vault_diff.py --path "01_Projects/mi-api/overview.md"',
        "related": ["vault_read", "vault_backup"],
    },
    "vault_merge": {
        "name": "vault_merge",
        "script": "vault_merge.py",
        "group": "Core",
        "purpose": "Detecta y resuelve duplicados entre vaults o dentro del mismo vault.",
        "params": {
            "action": {
                "type": "string",
                "required": True,
                "description": "Acción a realizar: detect, merge, dedup",
                "validators": ["enum:detect,merge,dedup"],
            },
            "source": {
                "type": "string",
                "required": False,
                "description": "Vault fuente para merge",
                "validators": ["path_exists"],
            },
            "conflict": {
                "type": "string",
                "required": False,
                "description": "Cómo resolver conflictos: skip, overwrite, rename",
                "validators": ["enum:skip,overwrite,rename"],
            },
        },
        "guards": [],
        "side_effects": ["Crea backups antes de modificar"],
        "example": 'python vault_merge.py --action detect\npython vault_merge.py --source "/path/to/other-vault" --action merge',
        "related": ["vault_backup", "vault_diff"],
    },
    "vault_log_error": {
        "name": "vault_log_error",
        "script": "vault_log_error.py",
        "group": "Observabilidad",
        "purpose": "Registra errores, antipatrones, vulnerabilidades, métricas, alertas y SLOs.",
        "params": {
            "type": {
                "type": "string",
                "required": True,
                "description": "Tipo: error, antipattern, vulnerability, metric, alert, slo",
                "validators": [
                    "enum:error,antipattern,vulnerability,waf,metric,alert,slo"
                ],
            },
            "title": {
                "type": "string",
                "required": True,
                "description": "Título descriptivo",
                "validators": ["not_empty", "max_length:200"],
            },
            "description": {
                "type": "string",
                "required": True,
                "description": "Descripción detallada",
                "validators": ["min_length:10"],
            },
            "severity": {
                "type": "string",
                "required": True,
                "description": "Severidad: critical, high, medium, low, info",
                "validators": ["enum:critical,high,medium,low,info"],
            },
            "project": {
                "type": "string",
                "required": False,
                "description": "Proyecto relacionado",
                "validators": [],
            },
            "meta": {
                "type": "json",
                "required": False,
                "description": "Metadatos adicionales",
                "validators": ["valid_json"],
            },
        },
        "guards": [],
        "side_effects": ["Crea/actualiza nota en 02_Observability/"],
        "example": 'python vault_log_error.py --type error --title "NullPointerException" --description "..." --severity high',
        "related": ["vault_audit", "vault_drift_detect", "vault_impact"],
    },
    "vault_audit": {
        "name": "vault_audit",
        "script": "vault_audit.py",
        "group": "Salud del Vault",
        "purpose": (
            "Evalua la salud del vault y genera nextActions. `healthScore` "
            "se conserva tal cual (lo leen los consumidores) pero satura en 0; "
            "la lectura que discrimina es `healthIndex` + `healthProfile`, "
            "seis familias normalizadas cada una contra su propio tope."
        ),
        "params": {
            "project": {
                "type": "string",
                "required": False,
                "description": "Proyecto a auditar",
                "validators": [],
            },
            "refresh-dq": {
                "type": "boolean",
                "required": False,
                "description": "Forzar refresh de Data Quality",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": [],
        "example": 'python vault_audit.py\npython vault_audit.py --project "mi-proyecto"',
        "related": ["vault_validate", "vault_fix_brackets", "vault_quality_check"],
    },
    "vault_validate": {
        "name": "vault_validate",
        "script": "vault_validate.py",
        "group": "Salud del Vault",
        "purpose": "Valida notas contra el schema y normas del vault.",
        "params": {
            "path": {
                "type": "string",
                "required": False,
                "description": "Ruta de nota a validar",
                "validators": ["within_vault"],
            },
            "folder": {
                "type": "string",
                "required": False,
                "description": "Carpeta a validar",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": [],
        "example": 'python vault_validate.py --path "01_Projects/mi-api/overview.md"',
        "related": ["vault_audit", "vault_write"],
    },
    "vault_fix_brackets": {
        "name": "vault_fix_brackets",
        "script": "vault_fix_brackets.py",
        "group": "Corrección Automática",
        "purpose": "Detecta y corrige anomalías de corchetes en wiki-links (AP-22, AP-24).",
        "params": {
            "path": {
                "type": "string",
                "required": False,
                "description": "Procesar solo esta nota",
                "validators": ["within_vault"],
            },
            "apply": {
                "type": "boolean",
                "required": False,
                "description": "Aplicar fixes (default: dry-run)",
                "validators": [],
            },
            "only": {
                "type": "string",
                "required": False,
                "description": "Filtrar por tipo de hallazgo (repetible); los valores los fija la CLI",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Backups en vault-backups/.vault-fix-backup-YYYYMMDD-HHMMSS/"],
        "example": 'python vault_fix_brackets.py\npython vault_fix_brackets.py --apply\npython vault_fix_brackets.py --path "02_Observability/errors/foo.md"',
        "related": ["vault_audit", "vault_regex"],
    },
    "vault_frontmatter_heal": {
        "name": "vault_frontmatter_heal",
        "script": "vault_frontmatter_heal.py",
        "group": "Corrección Automática",
        "purpose": "Repara el frontmatter que existe y no parsea (AP-56): escalar sin escapar y bloque sin cerrar.",
        "params": {
            "apply": {
                "type": "boolean",
                "required": False,
                "description": "Escribe las reparaciones (default: dry-run)",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit 1 si queda frontmatter ilegible",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Reescribe la nota reparada por atomic_write_text"],
        "example": "python vault_frontmatter_heal.py\npython vault_frontmatter_heal.py --apply",
        "related": ["vault_fix_brackets", "vault_validate", "vault_foreign_check"],
    },
    "vault_frontmatter_completar": {
        "name": "vault_frontmatter_completar",
        "script": "vault_frontmatter_completar.py",
        "group": "Corrección Automática",
        "purpose": "Pone los campos del contrato de nota que faltan (AP-12/16/26/27/28/29/30), con el origen de cada valor; no toca ninguno que ya esté.",
        "params": {
            "apply": {
                "type": "boolean",
                "required": False,
                "description": "Escribe los campos (default: dry-run)",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit 1 si queda algo por completar u omitido",
                "validators": [],
            },
            "path": {
                "type": "string",
                "required": False,
                "description": "Una sola nota, ruta relativa al vault",
                "validators": ["within_vault"],
            },
            "agent": {
                "type": "string",
                "required": False,
                "description": "Valor de agent para las notas que no lo llevan (default: VAULT_AGENT o el del escritor)",
                "validators": [],
            },
        },
        "guards": ["AP-56: un frontmatter que no parsea no se completa; se manda a vault_frontmatter_heal",
                   "AP-54: no escribe si la nota cambió desde que se leyó"],
        "side_effects": ["Reescribe el frontmatter de la nota por atomic_write_text"],
        "example": "python vault_frontmatter_completar.py\npython vault_frontmatter_completar.py --apply\npython vault_frontmatter_completar.py --path 07_Knowledge/x.md --apply",
        "related": ["vault_validate", "vault_frontmatter_heal", "vault_esquema"],
    },
    "vault_supersede": {
        "name": "vault_supersede",
        "script": "vault_supersede.py",
        "group": "Corrección Automática",
        "purpose": "Anota superseded_by en una nota que ya existe sin tocar su cuerpo: la sustituida no se borra, declara cuál manda (AP-17).",
        "params": {
            "path": {
                "type": "string",
                "required": True,
                "description": "La nota sustituida, ruta relativa al vault",
                "validators": ["within_vault"],
            },
            "by": {
                "type": "string",
                "required": True,
                "description": "La nota que manda, como wikilink: nombre de fichero, alias o ruta (nunca title:)",
                "validators": [],
            },
            "apply": {
                "type": "boolean",
                "required": False,
                "description": "Escribe la anotación (default: dry-run)",
                "validators": [],
            },
            "replace": {
                "type": "boolean",
                "required": False,
                "description": "Sustituye una superseded_by distinta ya escrita",
                "validators": [],
            },
        },
        "guards": ["AP-44: --by se resuelve por nombre de fichero y aliases, nunca por title:",
                   "Rechaza --by roto, ambiguo, a sí misma o que cierra un ciclo",
                   "AP-54: no escribe si la nota cambió desde que se leyó"],
        "side_effects": ["Reescribe el frontmatter de la nota por atomic_write_text; el cuerpo no cambia"],
        "example": "python vault_supersede.py --path 10_Migrated/GUIA.md --by guia\npython vault_supersede.py --path 10_Migrated/GUIA.md --by \"[[guia]]\" --apply",
        "related": ["vault_audit", "vault_context_pack", "vault_frontmatter_completar"],
    },
    "vault_delete": {
        "name": "vault_delete",
        "script": "vault_delete.py",
        "group": "Change Log",
        "purpose": "Elimina notas con SP-01 obligatorio: crea change-log antes de borrar.",
        "params": {
            "path": {
                "type": "string",
                "required": True,
                "description": "Ruta relativa de la nota a eliminar",
                "validators": ["within_vault"],
            },
            "reason": {
                "type": "string",
                "required": True,
                "description": "Motivo de eliminacion (SP-01)",
                "validators": ["not_empty"],
            },
            "trash_only": {
                "type": "boolean",
                "required": False,
                "description": "Solo mover a 20_Quarantine/",
                "validators": [],
            },
            "dry_run": {
                "type": "boolean",
                "required": False,
                "description": "Simular sin escribir",
                "validators": [],
            },
            "force": {
                "type": "boolean",
                "required": False,
                "description": "Omitir creacion de change-log",
                "validators": [],
            },
        },
        "guards": ["SP-01: change_log obligatorio antes de delete"],
        "side_effects": [
            "Escribe entrada en 00_System/.change-log.json",
            "Escribe entrada en 00_System/change-log.md",
            "Elimina o mueve a 20_Quarantine/",
            "Guarda la versión borrada en .history/ (la restaura vault_undo --restore)",
        ],
        "example": "python vault_delete.py --path \"07_Knowledge/old.md\" --reason \"Duplicate of glossary/jwt.md\"",
        "related": ["vault_change_log", "vault_undo"],
    },
    "vault_delta": {
        "name": "vault_delta",
        "script": "vault_delta.py",
        "group": "Session Delta y Tags",
        "purpose": "Detecta cambios entre sesiones usando SHA-256 y BFS sobre grafo de backlinks.",
        "params": {
            "snapshot": {
                "type": "boolean",
                "required": False,
                "description": "Guardar snapshot actual",
                "validators": [],
            }
        },
        "guards": [],
        "side_effects": ["Crea 00_System/delta-snapshot.json"],
        "example": "python vault_delta.py --snapshot\npython vault_delta.py",
        "related": ["vault_tags", "vault_reindex", "vault_drift_detect"],
    },
    "vault_tags": {
        "name": "vault_tags",
        "script": "vault_tags.py",
        "group": "Session Delta y Tags",
        "purpose": (
            "Registro canónico de tags, auditoría de orphans y near-dupes, y "
            "bitácora append-only del vocabulario introducido (AP-39)."
        ),
        # Los params son los flags de argparse verbatim: el servidor MCP compone
        # `--<key>`. Los que había (`action`, `tag`) no existían en la CLI, así
        # que toda invocación desde MCP fallaba con "unrecognized arguments".
        "params": {
            "audit": {
                "type": "boolean",
                "required": False,
                "description": "Reporte de salud de tags (orphans, near-dupes, singletons)",
                "validators": [],
            },
            "suggest": {
                "type": "string",
                "required": False,
                "description": "Ruta de una nota — sugiere tags canónicos para ella",
                "validators": [],
            },
            "rename": {
                "type": "array",
                "required": False,
                "description": "OLD NEW — renombra un tag en todas las notas",
                "validators": [],
            },
            "ledger": {
                "type": "boolean",
                "required": False,
                "description": "Bitácora de vocabulario: qué término se introdujo, quién y cuándo (AP-39)",
                "validators": [],
            },
            "backfill-ledger": {
                "type": "boolean",
                "required": False,
                "description": "Heal AP-39: anota en la bitácora el vocabulario ya en uso",
                "validators": [],
            },
            "dry-run": {
                "type": "boolean",
                "required": False,
                "description": "Simular sin escribir archivos",
                "validators": [],
            },
        },
        "guards": ["AP-39: el vocabulario introducido queda registrado, no se pierde"],
        "side_effects": [
            "Reconstruye 00_System/tag-registry.json y 99_Index/tag-index.md",
            "Anota términos nuevos en 19_Audits/vocabulary/tag-ledger.json (append-only)",
        ],
        "example": "python vault_tags.py\npython vault_tags.py --ledger",
        "related": ["vault_delta", "vault_audit"],
    },
    "vault_reindex": {
        "name": "vault_reindex",
        "script": "vault_reindex.py",
        "group": "Índices",
        "purpose": "Actualiza search-index.json y opcionalmente hash-index.json.",
        "params": {
            "graph": {
                "type": "boolean",
                "required": False,
                "description": "También generar graph.json",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": [
            "Actualiza 99_Index/search-index.json",
            "Opcional: 99_Index/graph.json, hash-index.json",
        ],
        "example": "python vault_reindex.py\npython vault_reindex.py --graph --check",
        "related": ["vault_search", "vault_graph"],
    },
    "vault_graph": {
        "name": "vault_graph",
        "script": "vault_graph.py",
        "group": "Salud del Vault",
        "purpose": "Genera grafo de relaciones entre notas.",
        "params": {},
        "guards": [],
        "side_effects": ["Crea 99_Index/graph.json"],
        "example": "python vault_graph.py",
        "related": ["vault_audit", "vault_impact", "vault_propagate"],
    },
    "vault_init": {
        "name": "vault_init",
        "script": "vault_init.py",
        "group": "Bootstrap",
        "purpose": "Bootstrap de vault nuevo en un comando.",
        "params": {
            "target": {
                "type": "string",
                "required": False,
                "description": "Versión objetivo (default: v34)",
                "validators": [],
            },
            "no-audit": {
                "type": "boolean",
                "required": False,
                "description": "No ejecutar vault_audit al final",
                "validators": [],
            },
            "clean": {
                "type": "boolean",
                "required": False,
                "description": "Borrar contenido existente (DANGEROUS)",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Crea carpetas, versiona, indexa, audit"],
        "example": "python vault_init.py\npython vault_init.py --target v34",
        "related": ["vault_standard_upgrade", "vault_onboard", "vault_audit"],
    },
    "vault_onboard": {
        "name": "vault_onboard",
        "script": "vault_onboard.py",
        "group": "Bootstrap",
        "purpose": (
            "Puebla un vault vacío desde un proyecto de código que nunca tuvo "
            "uno: lee el repo, reconstruye su historia con git y escribe las "
            "notas iniciales. Lee el proyecto, escribe solo en el vault."
        ),
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Nombre del proyecto en el vault",
                "validators": ["non_empty"],
            },
            "path": {
                "type": "string",
                "required": True,
                "description": "Ruta del repositorio a leer (solo lectura)",
                "validators": ["path_exists"],
            },
            "depth": {
                "type": "number",
                "required": False,
                "description": "Profundidad de escaneo de directorios",
                "validators": [],
            },
            "max-modules": {
                "type": "number",
                "required": False,
                "description": "Tope de módulos que reciben nota en 11_Code",
                "validators": [],
            },
            "lang": {
                "type": "string",
                "required": False,
                "description": "Lenguaje principal si la autodetección falla",
                "validators": [],
            },
            "max-commits": {
                "type": "number",
                "required": False,
                "description": (
                    "Ventana de historia leída. Si se alcanza, la salida lo "
                    "declara en warnings: el tope es un parámetro de la "
                    "invocación, no un hecho del proyecto"
                ),
                "validators": [],
            },
            "git-phases": {
                "type": "number",
                "required": False,
                "description": "Número máximo de fases a reconstruir",
                "validators": [],
            },
            "no-git": {
                "type": "boolean",
                "required": False,
                "description": "Omitir la arqueología de historia",
                "validators": [],
            },
            "skip": {
                "type": "array",
                "required": False,
                "description": "Secciones a omitir (01…17)",
                "validators": [],
            },
            "agent": {
                "type": "string",
                "required": False,
                "description": "Agente que firma las notas creadas",
                "validators": [],
            },
            "dry-run": {
                "type": "boolean",
                "required": False,
                "description": "Simular sin escribir",
                "validators": [],
            },
        },
        "guards": [
            "AP-45: no escribe una nota sin evidencia detrás; lo omitido se "
            "reporta en skipped_no_evidence en vez de rellenarse",
            "AP-44: relee del disco y valida el frontmatter con yaml.safe_load; "
            "los diagramas pasan por vault_mermaid_check antes de escribirse",
            "18_Bugs, 19_Audits y 20_Quarantine se dejan vacías por diseño y "
            "así se declara en sections_left_empty_by_design",
        ],
        "side_effects": [
            "Crea notas en las secciones 01…17 del vault destino",
            "No modifica el proyecto de origen: solo lo lee",
        ],
        "example": (
            "python vault_onboard.py --project mi-api --path ../mi-api\n"
            "python vault_onboard.py --project mi-api --path ../mi-api --dry-run"
        ),
        "related": ["vault_init", "vault_migrate_docs", "vault_audit", "vault_norms"],
    },
    "vault_standard_upgrade": {
        "name": "vault_standard_upgrade",
        "script": "vault_standard_upgrade.py",
        "group": "Versionado",
        "purpose": "Detecta y aplica migraciones entre versiones del estándar.",
        "params": {
            "from": {
                "type": "string",
                "required": False,
                "description": "Versión actual (lee standard-version.json si se omite)",
                "validators": [],
            },
            "to": {
                "type": "string",
                "required": False,
                "description": "Versión objetivo (default: v34)",
                "validators": [],
            },
            "check": {
                "type": "boolean",
                "required": False,
                "description": "Solo reportar sin aplicar",
                "validators": [],
            },
            "init": {
                "type": "string",
                "required": False,
                "description": "Inicializar archivo de versión",
                "validators": [],
            },
            "fixes-only": {
                "type": "boolean",
                "required": False,
                "description": "Solo ejecutar fixes sin migrar",
                "validators": [],
            },
            "dry-run": {
                "type": "boolean",
                "required": False,
                "description": "Simular sin aplicar cambios",
                "validators": [],
            },
            "report": {
                "type": "boolean",
                "required": False,
                "description": "Generar reporte de fixes disponibles",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": [
            "Actualiza 00_System/standard-version.json",
            "Ejecuta fixes automáticos",
        ],
        "example": "python vault_standard_upgrade.py --check\npython vault_standard_upgrade.py --to v34\npython vault_standard_upgrade.py --report",
        "related": ["vault_init", "vault_audit"],
    },
    "vault_undo": {
        "name": "vault_undo",
        "script": "vault_undo.py",
        "group": "Versionado",
        "purpose": "Recupera una nota desde .history/. Lista versiones y restaura sin sobreescribir (por defecto).",
        "params": {
            "list": {
                "type": "string",
                "required": False,
                "description": "Listar versiones disponibles para esta nota",
                "validators": [],
            },
            "restore": {
                "type": "string",
                "required": False,
                "description": "Restaurar version desde .history/",
                "validators": [],
            },
            "version": {
                "type": "string",
                "required": False,
                "description": "Version especifica a restaurar (filename en .history/)",
                "validators": [],
            },
            "force": {
                "type": "boolean",
                "required": False,
                "description": "Sobrescribir nota actual (default: restaurar como copia nueva)",
                "validators": [],
            },
            "dry_run": {
                "type": "boolean",
                "required": False,
                "description": "Simular sin escribir",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": [
            "SP-01: escribe change_log si --force",
            "Crea nota restaurada o sobreescribe la actual",
        ],
        "example": "python vault_undo.py --list \"01_Projects/ans/status.md\"\npython vault_undo.py --restore \"01_Projects/ans/status.md\" --force",
        "related": ["vault_write", "vault_diff", "vault_history_compact"],
    },
    "vault_sdd_init": {
        "name": "vault_sdd_init",
        "script": "vault_sdd_init.py",
        "group": "Skills",
        "purpose": "Genera la documentación SDD del vault (14 documentos en docs/sdd/).",
        "params": {
            "bilingual": {
                "type": "boolean",
                "required": False,
                "description": "Genera contenido ES + EN en paralelo",
                "validators": [],
            },
            "check": {
                "type": "boolean",
                "required": False,
                "description": "Compara el rango del disco contra NORM_CATALOG; falla si desfasado (AP-47)",
                "validators": [],
            },
            "dry-run": {
                "type": "boolean",
                "required": False,
                "description": "Muestra el plan sin escribir",
                "validators": [],
            },
            "force": {
                "type": "boolean",
                "required": False,
                "description": "Regenera los 13 documentos derivados; NO pisa gaps.md",
                "validators": [],
            },
            "vault-root": {
                "type": "string",
                "required": False,
                "description": "Vault destino (default: autodetección de vault_io)",
                "validators": [],
            },
        },
        "guards": ["AP-36: toda escritura ocurre bajo <vault-root>/docs/sdd/"],
        "side_effects": [
            "Escribe 13 documentos derivados en docs/sdd/",
            "Escribe docs/sdd/gaps.md solo si no existe o no tiene contenido manual",
        ],
        "example": "python vault_sdd_init.py --bilingual\npython vault_sdd_init.py --check\npython vault_sdd_init.py --bilingual --force",
        "related": ["vault_norms", "vault_reindex", "vault_doc_counts"],
    },
    "vault_sanacion": {
        "name": "vault_sanacion",
        "script": "vault_sanacion.py",
        "group": "Skills",
        "purpose": "Diagnostica un vault preexistente y devuelve el plan de 12 fases con evidencia.",
        "params": {
            "phase": {
                "type": "number",
                "required": False,
                "description": "Detalle de una sola fase (1..12)",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit 1 si alguna fase aplica o no se pudo medir",
                "validators": [],
            },
        },
        "guards": [
            "No escribe nada: la escritura la hace la tool que cada fase nombra",
            "Vault destino por autodetección o VAULT_ROOT; sin flag de raíz propia",
        ],
        "side_effects": [],
        "example": "python vault_sanacion.py\nVAULT_ROOT=/ruta/al/vault python vault_sanacion.py\npython vault_sanacion.py --phase 8",
        "related": ["vault_audit", "vault_norms", "vault_reindex", "vault_onboard"],
    },
    "vault_move": {
        "name": "vault_move",
        "script": "vault_move.py",
        "group": "Core",
        "purpose": "Reubica notas entre carpetas del vault, actualiza wiki-links, índices y grafo.",
        "params": {
            "from": {
                "type": "string",
                "required": False,
                "description": "Nota origen",
                "validators": ["within_vault"],
            },
            "to": {
                "type": "string",
                "required": False,
                "description": "Nota destino",
                "validators": [],
            },
            "folder": {
                "type": "string",
                "required": False,
                "description": "Carpeta origen (mover toda)",
                "validators": [],
            },
            "to-folder": {
                "type": "string",
                "required": False,
                "description": "Carpeta destino",
                "validators": [],
            },
            "dry_run": {
                "type": "boolean",
                "required": False,
                "description": "Simular sin aplicar",
                "validators": [],
            },
            "impact": {
                "type": "boolean",
                "required": False,
                "description": "Analizar impacto sin ejecutar",
                "validators": [],
            },
        },
        "guards": ["Confimar antes de sobreescribir"],
        "side_effects": ["Actualiza wiki-links, search-index, graph.json, move-log"],
        "example": 'python vault_move.py --from "01_Projects/foo.md" --to "03_Decisions/foo.md"\npython vault_move.py --folder "01_Projects/old" --to-folder "01_Projects/new"',
        "related": ["vault_write", "vault_graph", "vault_reindex"],
    },
    "vault_folder_registry": {
        "name": "vault_folder_registry",
        "script": "vault_folder_registry.py",
        "group": "Gestión de Carpetas",
        "purpose": "Auto-detecta y registra carpetas personalizadas dentro de secciones del vault.",
        "params": {
            "scan": {
                "type": "boolean",
                "required": False,
                "description": "Escanear carpetas nuevas",
                "validators": [],
            },
            "list": {
                "type": "boolean",
                "required": False,
                "description": "Listar carpetas",
                "validators": [],
            },
            "add": {
                "type": "string",
                "required": False,
                "description": "Agregar carpeta manualmente",
                "validators": [],
            },
            "remove": {
                "type": "string",
                "required": False,
                "description": "Eliminar carpeta del registro",
                "validators": [],
            },
            "cleanup": {
                "type": "boolean",
                "required": False,
                "description": "Limpiar carpetas huérfanas",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Crea/actualiza 00_System/custom-folders.json"],
        "example": 'python vault_folder_registry.py\npython vault_folder_registry.py --scan\npython vault_folder_registry.py --add "11_Code/tests"',
        "related": ["vault_reindex", "vault_audit"],
    },
    "vault_section": {
        "name": "vault_section",
        "script": "vault_section.py",
        "group": "Gestión de Carpetas",
        "purpose": "Declara, lista y retira las secciones propias de un vault (NN_Nombre en 00_System/secciones.json); lo no declarado sigue siendo CN-02.",
        "params": {
            "list": {
                "type": "boolean",
                "required": False,
                "description": "Listar secciones propias y carpetas de raíz sin sección",
                "validators": [],
            },
            "add": {
                "type": "string",
                "required": False,
                "description": "Declarar una sección propia NN_Nombre",
                "validators": [],
            },
            "retire": {
                "type": "string",
                "required": False,
                "description": "Retirar una sección propia sin borrar nada",
                "validators": [],
            },
            "documentacion": {
                "type": "string",
                "required": False,
                "description": "Clase de documento: tutorial, guia, referencia, explicacion, registro, indice",
                "validators": [],
            },
            "description": {
                "type": "string",
                "required": False,
                "description": "Qué contiene la sección",
                "validators": [],
            },
            "superseded-by": {
                "type": "string",
                "required": False,
                "description": "Sección que sustituye a la retirada",
                "validators": [],
            },
        },
        "guards": ["Nombre NN_Nombre en el rango libre, sin repetir número", "Un secciones.json ilegible no se reescribe"],
        "side_effects": ["Crea/actualiza 00_System/secciones.json", "Crea la carpeta de la sección si no existe"],
        "example": 'python vault_section.py --list\npython vault_section.py --add 22_Scripts --documentacion referencia --description "Scripts de despliegue"',
        "related": ["vault_folder_registry", "vault_audit", "vault_validate"],
    },
    "vault_mermaid_check": {
        "name": "vault_mermaid_check",
        "script": "vault_mermaid_check.py",
        "group": "Diagramas",
        "purpose": (
            "Valida diagramas Mermaid con el compilador real (oráculo) y sana "
            "los bloques que rechaza con sanadores mecánicos verificados."
        ),
        "params": {
            "path": {
                "type": "string",
                "required": False,
                "description": "Archivo específico",
                "validators": ["within_vault"],
            },
            "project": {
                "type": "string",
                "required": False,
                "description": "Proyecto a verificar",
                "validators": [],
            },
            "fix": {
                "type": "boolean",
                "required": False,
                "description": "Sanar los bloques que el compilador rechaza (requiere oráculo)",
                "validators": [],
            },
            "dry_run": {
                "type": "boolean",
                "required": False,
                "description": "Con --fix: propone y reporta sin escribir",
                "validators": [],
            },
            "json": {
                "type": "boolean",
                "required": False,
                "description": "Salida JSON",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": [
            "Con --fix (sin --dry-run): reescribe los .md cuyo bloque el compilador "
            "señala, SOLO si una propuesta es aprobada por el compilador; escritura "
            "por el patrón canónico (file_lock + record_raw_write + escritura_atomica "
            "+ refrescar_grafo)",
        ],
        "example": 'python vault_mermaid_check.py\npython vault_mermaid_check.py --path "06_Diagrams/foo.md"\npython vault_mermaid_check.py --fix --dry-run\npython vault_mermaid_check.py --fix',
        "related": ["vault_diagram_save", "vault_write"],
    },
    "vault_diagram_export": {
        "name": "vault_diagram_export",
        "script": "vault_diagram_export.py",
        "group": "Diagramas",
        "purpose": "Exporta diagramas con opciones de zoom, pan y filtros.",
        "params": {
            "path": {
                "type": "string",
                "required": False,
                "description": "Archivo a exportar",
                "validators": ["within_vault"],
            },
            "project": {
                "type": "string",
                "required": False,
                "description": "Proyecto a exportar",
                "validators": [],
            },
            "output": {
                "type": "string",
                "required": False,
                "description": "Carpeta de salida",
                "validators": [],
            },
            "zoom": {
                "type": "float",
                "required": False,
                "description": "Nivel de zoom (default: 1.0)",
                "validators": [],
            },
            "pan_x": {
                "type": "int",
                "required": False,
                "description": "Posición X del pan",
                "validators": [],
            },
            "pan_y": {
                "type": "int",
                "required": False,
                "description": "Posición Y del pan",
                "validators": [],
            },
            "filter": {
                "type": "string",
                "required": False,
                "description": "Filtrar por tipo",
                "validators": [],
            },
            "highlight": {
                "type": "string",
                "required": False,
                "description": "Nodos a resaltar (coma)",
                "validators": [],
            },
            "hide": {
                "type": "string",
                "required": False,
                "description": "Nodos a ocultar (coma)",
                "validators": [],
            },
            "config": {
                "type": "boolean",
                "required": False,
                "description": "Guardar configuración global",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Genera archivos exportados"],
        "example": 'python vault_diagram_export.py --path "06_Diagrams/foo.md" --zoom 2.0\npython vault_diagram_export.py --project "mi-api" --output "export/"',
        "related": ["vault_diagram_save", "vault_mermaid_check"],
    },
    "vault_diagram_save": {
        "name": "vault_diagram_save",
        "script": "vault_diagram_save.py",
        "group": "Diagramas",
        "purpose": "Guarda diagramas Mermaid/ASCII/PlantUML con frontmatter categorizado.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto relacionado",
                "validators": [],
            },
            "title": {
                "type": "string",
                "required": True,
                "description": "Título del diagrama",
                "validators": ["not_empty"],
            },
            "diagram_type": {
                "type": "string",
                "required": True,
                "description": "Tipo: mermaid, ascii, plantuml",
                "validators": ["enum:mermaid,ascii,plantuml"],
            },
            "category": {
                "type": "string",
                "required": True,
                "description": "Categoría: entity, component, sequence, dependency, flow, state, lifecycle",
                "validators": [
                    "enum:entity,component,sequence,dependency,flow,state,lifecycle"
                ],
            },
            "content": {
                "type": "string",
                "required": True,
                "description": "Contenido del diagrama (sin backticks)",
                "validators": [],
            },
            "description": {
                "type": "string",
                "required": False,
                "description": "Descripción opcional",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Crea nota en 06_Diagrams/{category}/"],
        "example": 'python vault_diagram_save.py --project "mi-api" --title "User Flow" --diagram_type "mermaid" --category "flow" --content "graph TD\\n  A --> B"',
        "related": ["vault_relation_add", "vault_graph"],
    },
    "vault_relation_add": {
        "name": "vault_relation_add",
        "script": "vault_relation_add.py",
        "group": "Diagramas",
        "purpose": "Agrega relaciones entre entidades y genera ERD automático.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
            "to": {
                "type": "string",
                "required": True,
                "description": "Entidad destino",
                "validators": ["not_empty"],
            },
            "label": {
                "type": "string",
                "required": False,
                "description": "Etiqueta de la relación",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Actualiza relaciones en 07_Knowledge/"],
        "example": 'python vault_relation_add.py --project "mi-api" --from "User" --to "Order" --relation_type "has_many" --cardinality "1:N"',
        "related": ["vault_diagram_save", "vault_code_relation"],
    },
    "vault_code_module": {
        "name": "vault_code_module",
        "script": "vault_code_module.py",
        "group": "Código",
        "purpose": "Genera templates de módulos de código con IEEE 1016.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
            "language": {
                "type": "string",
                "required": True,
                "description": "Lenguaje: python, javascript, typescript, go, rust",
                "validators": ["enum:python,javascript,typescript,go,rust"],
            },
        },
        "guards": [],
        "side_effects": ["Crea nota en 11_Code/{project}/"],
        "example": 'python vault_code_module.py --project "mi-api" --file_path "src/auth.py" --description "Modulo de autenticacion" --language "python"',
        "related": ["vault_code_map", "vault_code_relation", "vault_diagram_save"],
    },
    "vault_code_map": {
        "name": "vault_code_map",
        "script": "vault_code_map.py",
        "group": "Código",
        "purpose": "Genera mapa de dependencias entre módulos de código.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Genera 11_Code/{project}/map.md con diagrama"],
        "example": 'python vault_code_map.py --project "mi-api"',
        "related": ["vault_code_module", "vault_code_relation", "vault_graph"],
    },
    "vault_code_relation": {
        "name": "vault_code_relation",
        "script": "vault_code_relation.py",
        "group": "Código",
        "purpose": "Registra y visualiza relaciones entre componentes de código.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Actualiza índice de relaciones en 11_Code/"],
        "example": 'python vault_code_relation.py --project "mi-api" --from_file "auth.py" --to_file "user.py" --relation_type "imports"',
        "related": ["vault_code_map", "vault_code_module"],
    },
    "vault_code_query": {
        "name": "vault_code_query",
        "script": "vault_code_query.py",
        "group": "Código",
        "purpose": "Consulta información del índice de código.",
        "params": {
            "project": {
                "type": "string",
                "required": False,
                "description": "Filtrar por proyecto",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": [],
        "example": 'python vault_code_query.py --project "mi-api" --list\npython vault_code_query.py --project "mi-api" --class "AuthService" --deps',
        "related": ["vault_code_map", "vault_search"],
    },
    "vault_code_sync": {
        "name": "vault_code_sync",
        "script": "vault_code_sync.py",
        "group": "Código",
        "purpose": "Sincroniza estado del código con el vault.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Actualiza 11_Code/{project}/index.json"],
        "example": 'python vault_code_sync.py --project "mi-api"\npython vault_code_sync.py --project "mi-api" --dry-run',
        "related": ["vault_code_map", "vault_reindex"],
    },
    "vault_code_tag": {
        "name": "vault_code_tag",
        "script": "vault_code_tag.py",
        "group": "Normas",
        "purpose": "Etiqueta módulos de código por funcionalidad.",
        "params": {
        },
        "guards": [],
        "side_effects": ["Actualiza frontmatter del módulo"],
        "example": ('python vault_code_tag.py --list\n'
                    'python vault_code_tag.py --define cr-ejemplo --name '
                    '"Ejemplo" --description "Etiqueta de prueba"'),
        "related": ["vault_tags", "vault_code_module"],
    },
    "vault_flow_save": {
        "name": "vault_flow_save",
        "script": "vault_flow_save.py",
        "group": "Flujos",
        "purpose": "Guarda workflows, pipelines, lifecycles y dataflows con diagrama Mermaid.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
            "name": {
                "type": "string",
                "required": True,
                "description": "Nombre del flujo",
                "validators": ["not_empty"],
            },
            "type": {
                "type": "string",
                "required": True,
                "description": "Tipo: workflow, pipeline, lifecycle, dataflow",
                "validators": ["enum:workflow,pipeline,lifecycle,dataflow"],
            },
            "description": {
                "type": "string",
                "required": True,
                "description": "Descripción",
                "validators": ["min_length:10"],
            },
            "mermaid": {
                "type": "string",
                "required": True,
                "description": "Diagrama Mermaid (sin backticks)",
                "validators": [],
            },
            "actors": {
                "type": "string",
                "required": False,
                "description": "Actores separados por coma",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Crea nota en 13_Flows/{type}/"],
        "example": 'python vault_flow_save.py --project "mi-api" --name "User Registration" --type workflow --description "Full process" --mermaid "flowchart TD\\n  A --> B"',
        "related": ["vault_diagram_save", "vault_graph"],
    },
    "vault_pattern_save": {
        "name": "vault_pattern_save",
        "script": "vault_pattern_save.py",
        "group": "Patrones",
        "purpose": "Guarda patrones arquitectónicos en el vault.",
        "params": {
            "name": {
                "type": "string",
                "required": True,
                "description": "Nombre del patrón",
                "validators": ["not_empty"],
            },
            "description": {
                "type": "string",
                "required": True,
                "description": "Descripción del patrón",
                "validators": ["min_length:20"],
            },
        },
        "guards": [],
        "side_effects": ["Crea nota en 05_Patterns/"],
        "example": 'python vault_pattern_save.py --project "mi-api" --name "Repository" --type "architecture" --status "implementado" --description "Abstraccion de acceso a datos"',
        "related": ["vault_pattern_list", "vault_code_module"],
    },
    "vault_pattern_list": {
        "name": "vault_pattern_list",
        "script": "vault_pattern_list.py",
        "group": "Patrones",
        "purpose": "Lista patrones arquitectónicos disponibles.",
        "params": {
        },
        "guards": [],
        "side_effects": [],
        "example": 'python vault_pattern_list.py\npython vault_pattern_list.py --type "architecture"',
        "related": ["vault_pattern_save", "vault_search"],
    },
    "vault_knowledge_save": {
        "name": "vault_knowledge_save",
        "script": "vault_knowledge_save.py",
        "execution_module": "vault_toolkit.operations.vault_knowledge_save",
        "group": "Conocimiento",
        "purpose": "Guarda conocimiento estructurado por tema.",
        "params": {
            "category": {
                "type": "string",
                "required": True,
                "description": "Categoría; los valores válidos son vault.autoria.conocimiento.CATEGORIES",
                "validators": ["not_empty"],
            },
            "title": {
                "type": "string",
                "required": True,
                "description": "Título del conocimiento",
                "validators": ["not_empty"],
            },
            "content": {
                "type": "string",
                "required": True,
                "description": "Contenido estructurado",
                "validators": ["min_lines:3"],
            },
            "tags": {
                "type": "string",
                "required": False,
                "description": "Tags separados por espacio",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Crea nota en 07_Knowledge/{topic}/"],
        "example": 'python vault_knowledge_save.py --category "concept" --title "Clean Architecture" --content "# Clean Architecture" --tags "architecture clean"',
        "related": ["vault_knowledge_get", "vault_search"],
    },
    "vault_knowledge_get": {
        "name": "vault_knowledge_get",
        "script": "vault_knowledge_get.py",
        "execution_module": "vault_toolkit.operations.vault_knowledge_get",
        "group": "Conocimiento",
        "purpose": "Recupera conocimiento por tema o búsqueda.",
        "params": {
            "query": {
                "type": "string",
                "required": False,
                "description": "Palabra clave",
                "validators": [],
            },
            "limit": {
                "type": "int",
                "required": False,
                "description": "Límite de resultados (default: 10)",
                "validators": ["min:1", "max:50"],
            },
        },
        "guards": [],
        "side_effects": [],
        "example": 'python vault_knowledge_get.py --query "architecture"\npython vault_knowledge_get.py --query "clean"',
        "related": ["vault_knowledge_save", "vault_search"],
    },
    "vault_backup": {
        "name": "vault_backup",
        "script": "vault_backup.py",
        "group": "Backups",
        "purpose": "Crea backup del vault en carpeta timestamped.",
        "params": {
            "label": {
                "type": "string",
                "required": False,
                "description": "Etiqueta opcional",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Crea carpeta en vault-backups/"],
        "example": 'python vault_backup.py\npython vault_backup.py --label "pre-migration"',
        "related": ["vault_backup_list", "vault_restore"],
    },
    "vault_backup_list": {
        "name": "vault_backup_list",
        "script": "vault_backup_list.py",
        "group": "Backups",
        "purpose": "Lista backups disponibles.",
        "params": {
            "limit": {
                "type": "int",
                "required": False,
                "description": "Cantidad máxima (default: 20)",
                "validators": ["min:1", "max:100"],
            },
        },
        "guards": [],
        "side_effects": [],
        "example": "python vault_backup_list.py\npython vault_backup_list.py --limit 5",
        "related": ["vault_backup", "vault_restore"],
    },
    "vault_restore": {
        "name": "vault_restore",
        "script": "vault_restore.py",
        "group": "Backups",
        "purpose": "Restaura vault desde backup.",
        "params": {
        },
        "guards": ["Confirmar antes de sobreescribir"],
        "side_effects": ["Sobreescribe archivos del vault"],
        "example": 'python vault_restore.py --backup_name "2026-06-24_120000" --confirm true',
        "related": ["vault_backup", "vault_backup_list"],
    },
    "vault_env_save": {
        "name": "vault_env_save",
        "script": "vault_env_save.py",
        "group": "Infraestructura",
        "purpose": "Guarda variables de entorno y secretos para un proyecto.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
            "environment": {
                "type": "string",
                "required": True,
                "description": "Entorno: dev, staging, prod",
                "validators": ["enum:dev,staging,prod"],
            },
        },
        "guards": ["No guardar secrets en texto plano"],
        "side_effects": ["Crea nota en 09_Infrastructure/{project}/"],
        "example": 'python vault_env_save.py --project "mi-api" --environment "prod" --vars \'[{"name": "DB_HOST", "default": "localhost"}]\'',
        "related": ["vault_env_matrix", "vault_infra_save"],
    },
    "vault_env_matrix": {
        "name": "vault_env_matrix",
        "script": "vault_env_matrix.py",
        "group": "Infraestructura",
        "purpose": "Genera matriz comparativa de entornos.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Genera 09_Infrastructure/{project}/matrix.md"],
        "example": 'python vault_env_matrix.py --project "mi-api" --env "prod"',
        "related": ["vault_env_save", "vault_infra_map"],
    },
    "vault_infra_save": {
        "name": "vault_infra_save",
        "script": "vault_infra_save.py",
        "group": "Infraestructura",
        "purpose": "Guarda documentación de infraestructura.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
            "description": {
                "type": "string",
                "required": False,
                "description": "Descripción",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Crea nota en 09_Infrastructure/{project}/"],
        "example": 'python vault_infra_save.py --name "prod-cluster" --type "server" --description "Cluster productivo" --config \'{"region": "us-east-1"}\'',
        "related": ["vault_infra_map", "vault_env_save"],
    },
    "vault_infra_map": {
        "name": "vault_infra_map",
        "script": "vault_infra_map.py",
        "group": "Infraestructura",
        "purpose": "Genera mapa visual de infraestructura en Mermaid.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
            "location": {
                "type": "string",
                "required": False,
                "description": "Ubicación geográfica",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Genera diagrama en 09_Infrastructure/{project}/"],
        "example": 'python vault_infra_map.py --project "mi-api" --location "cloud-aws"',
        "related": ["vault_infra_save", "vault_diagram_save"],
    },
    "vault_security_scan": {
        "name": "vault_security_scan",
        "script": "vault_security_scan.py",
        "group": "Seguridad",
        "purpose": (
            "Escaneo de seguridad del código de un proyecto (OWASP/CWE) por "
            "extensión de código; las notas .md no se escanean."
        ),
        "params": {
            "project": {
                "type": "string",
                "required": False,
                "description": "Proyecto específico",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Genera reporte en 02_Observability/vulnerabilities/"],
        "example": 'python vault_security_scan.py --path "src/" --project "mi-api"\npython vault_security_scan.py --path "src/" --project "mi-api" --categories secrets command_injection --save_findings false',
        "related": ["vault_audit", "vault_log_error"],
    },
    "vault_drift_detect": {
        "name": "vault_drift_detect",
        "script": "vault_drift_detect.py",
        "group": "Drift Detection",
        "purpose": (
            "Detecta cambios de código sin documentar: compara el código del "
            "proyecto con un snapshot y cruza lo cambiado con la documentación "
            "del vault (AP-08 con --mode vigencia)."
        ),
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
            "path": {
                "type": "string",
                "required": False,
                "description": "Raíz del código a escanear; por defecto, el repo enlazado con vault_project --link",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": [
            "--mode snapshot escribe el snapshot de sesión en 00_System/ y, sobre git, "
            "repo.synced_commit en la ficha del proyecto",
        ],
        "example": (
            'python vault_drift_detect.py --path "src/" --project "mi-api" --mode snapshot\n'
            'python vault_drift_detect.py --path "src/" --project "mi-api" --mode status'
        ),
        "related": ["vault_audit", "vault_env_matrix"],
    },
    "vault_impact": {
        "name": "vault_impact",
        "script": "vault_impact.py",
        "group": "Propagación",
        "purpose": "Análisis de impacto en cascada de cambios.",
        "params": {
        },
        "guards": [],
        "side_effects": [],
        "example": 'python vault_impact.py --changed "01_Projects/mi-api/overview.md" --max-hops "2"\npython vault_impact.py --since "2026-01-01" --min-risk "high"',
        "related": ["vault_propagate", "vault_graph"],
    },
    "vault_propagate": {
        "name": "vault_propagate",
        "script": "vault_propagate.py",
        "group": "Propagación",
        "purpose": "Propaga cambios entre notas relacionadas.",
        "params": {
        },
        "guards": [],
        "side_effects": ["Actualiza notas relacionadas"],
        "example": 'python vault_propagate.py --changed "01_Projects/mi-api/overview.md" --queue-report',
        "related": ["vault_impact", "vault_write"],
    },
    "vault_qa_save": {
        "name": "vault_qa_save",
        "script": "vault_qa_save.py",
        "group": "Tests",
        "purpose": "Registra planes de test, métricas, reportes y estrategias QA en 21_QA/.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Slug del proyecto",
                "validators": [],
            },
            "type": {
                "type": "string",
                "required": True,
                "description": "Tipo: test-plan | qa-metrics | qa-report | qa-strategy | coverage-report",
                "validators": ["one_of:test-plan,qa-metrics,qa-report,qa-strategy,coverage-report"],
            },
            "title": {
                "type": "string",
                "required": True,
                "description": "Título del documento QA",
                "validators": ["not_empty"],
            },
            "description": {
                "type": "string",
                "required": True,
                "description": "Descripción del documento QA",
                "validators": ["not_empty"],
            },
            "status": {
                "type": "string",
                "required": False,
                "description": "Estado: draft | review | approved | published | archived",
                "validators": ["one_of:draft,review,approved,published,archived"],
            },
        },
        "guards": [],
        "side_effects": ["Crea 21_QA/.qa-index.json si no existe"],
        "example": 'python vault_qa_save.py --project "mi-api" --type "test-plan" --title "Plan de Pruebas v2" --description "Plan de pruebas de la API para la v2"',
        "related": ["vault_test_save", "vault_quality_dashboard"],
    },
    "vault_quality_check": {
        "name": "vault_quality_check",
        "script": "vault_quality_check.py",
        "group": "Data Quality",
        "purpose": "Verifica calidad de datos del vault.",
        "params": {
        },
        "guards": [],
        "side_effects": ["Genera reporte en 00_System/"],
        "example": 'python vault_quality_check.py\npython vault_quality_check.py --min-score 0.7',
        "related": ["vault_audit", "vault_fundamentals"],
    },
    "vault_quality_dashboard": {
        "name": "vault_quality_dashboard",
        "script": "vault_quality_dashboard.py",
        "group": "Tests",
        "purpose": "Genera dashboard de calidad operacional en 02_Observability/qa/ combinando quality-index, tag-registry, qa-index y tests-index.",
        "params": {},
        "guards": [],
        "side_effects": ["Genera 02_Observability/qa/quality-dashboard.md"],
        "example": "python vault_quality_dashboard.py\npython vault_quality_dashboard.py --check",
        "related": ["vault_quality_check", "vault_qa_save", "vault_test_save"],
    },
    "vault_fundamentals": {
        "name": "vault_fundamentals",
        "script": "vault_fundamentals.py",
        "group": "Data Quality",
        "purpose": "Métricas fundamentales del vault.",
        "params": {},
        "guards": [],
        "side_effects": [
            "Con --framework/--doc escribe el marco de datos y la documentación derivada (en el checkout del estándar)",
        ],
        "example": "python vault_fundamentals.py",
        "related": ["vault_audit", "vault_quality_check"],
    },
    "vault_project": {
        "name": "vault_project",
        "script": "vault_project.py",
        "group": "Vista del Proyecto",
        "purpose": "Registro de proyectos (AP-63): lista, resuelve nombre->slug, audita fantasmas, da de alta con alias y enlaza la ruta local en 00_System/.local/.",
        "params": {
            "list": {"type": "boolean", "required": False, "description": "Lista proyectos, alias, ambigüedades e incidencias", "validators": []},
            "resolve": {"type": "string", "required": False, "description": "Nombre o alias a resolver a su slug canónico", "validators": []},
            "audit": {"type": "boolean", "required": False, "description": "Notas cuyo project: no resuelve y claves no canónicas (solo lectura)", "validators": []},
            "add": {"type": "string", "required": False, "description": "Slug a registrar, o al que sumar alias si ya existe", "validators": []},
            "link": {"type": "string", "required": False, "description": "Proyecto cuya ruta local se guarda (con path)", "validators": []},
            "rebuild": {"type": "boolean", "required": False, "description": "Regenera 00_System/project-registry.json", "validators": []},
            "title": {"type": "string", "required": False, "description": "Título de la ficha (con add)", "validators": []},
            "alias": {"type": "array", "required": False, "description": "Alias del proyecto (con add)", "validators": []},
            "status": {"type": "string", "required": False, "description": "Estado de la ficha nueva (con add; default in-progress)", "validators": ["enum:approved,archived,deprecated,draft,implemented,in-progress,obsolete,planned,reviewed,stub,template,verified"]},
            "path": {"type": "string", "required": False, "description": "Ruta local del repositorio (con link)", "validators": []},
        },
        "guards": ["AP-63: un nombre de proyecto resuelve a un único slug o la tool falla"],
        "side_effects": [
            "Crea 01_Projects/<slug>/project.md (add)",
            "Escribe 00_System/.local/project-paths.json y su .gitignore (link)",
            "Escribe 00_System/project-registry.json (rebuild)",
        ],
        "example": 'python vault_project.py --add ans --title "ANS" --alias ans-api\npython vault_project.py --resolve "ANS API"\npython vault_project.py --audit',
        "related": ["vault_project_status", "vault_project_overview"],
    },
    "vault_project_status": {
        "name": "vault_project_status",
        "script": "vault_project_status.py",
        "group": "Vista del Proyecto",
        "purpose": (
            "Actualiza el estado de un proyecto: escribe status.md y anota el "
            "cambio en su changelog.md (--status y --summary obligatorios)."
        ),
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Slug del proyecto",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": [
            "Con --status/--summary escribe el status del proyecto y anota la entrada en su changelog",
        ],
        "example": 'python vault_project_status.py --project "mi-api" --status "en_desarrollo" --summary "Sprint 3 en curso"',
        "related": ["vault_project_overview", "vault_audit"],
    },
    "vault_project_overview": {
        "name": "vault_project_overview",
        "script": "vault_project_overview.py",
        "group": "Vista del Proyecto",
        "purpose": "Genera overview consolidado de proyecto.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Slug del proyecto",
                "validators": [],
            },
            "description": {
                "type": "string",
                "required": False,
                "description": "Descripción del proyecto",
                "validators": [],
            },
            "runtime": {
                "type": "string",
                "required": False,
                "description": "Runtime (ej: Node.js 20)",
                "validators": [],
            },
            "extra_sections": {
                "type": "string",
                "required": False,
                "description": "Secciones extra en JSON",
                "validators": ["valid_json"],
            },
        },
        "guards": [],
        "side_effects": ["Crea/actualiza 01_Projects/{slug}/overview.md"],
        "example": 'python vault_project_overview.py --project "mi-api" --description "REST API" --runtime "Node.js 20"',
        "related": ["vault_project_status", "vault_audit"],
    },
    "vault_section_index": {
        "name": "vault_section_index",
        "script": "vault_section_index.py",
        "group": "Índices",
        "purpose": "Genera índice de una sección del vault.",
        "params": {
        },
        "guards": [],
        "side_effects": ["Genera {section}/index.md"],
        "example": 'python vault_section_index.py --folder "01_Projects"',
        "related": ["vault_master_index", "vault_reindex"],
    },
    "vault_master_index": {
        "name": "vault_master_index",
        "script": "vault_master_index.py",
        "group": "Índices",
        "purpose": "Genera índice maestro del vault.",
        # `include_subdirs` se publicaba y el parser no tenía **ningún**
        # `add_argument`: la invocación MCP moría en `unrecognized arguments`.
        # `check_params` no lo veía porque saltaba las tools con `argparse`
        # vacío —«sin argparse legible no hay contra qué comparar»—, que es
        # justo el caso en que todo lo publicado sobra.
        "params": {},
        "guards": [],
        # El fichero real es `99_Index/index.md`. `master-index.md` no lo
        # escribe nadie: el side effect declarado apuntaba a una ruta que no
        # existe, y es la que un consumidor mira para saber si hubo trabajo.
        "side_effects": ["Genera 99_Index/index.md"],
        "example": "python vault_master_index.py",
        "related": ["vault_section_index", "vault_reindex"],
    },
    "vault_timeline": {
        "name": "vault_timeline",
        "script": "vault_timeline.py",
        "group": "Línea de Tiempo",
        "purpose": "Genera línea temporal de eventos del vault.",
        "params": {
            "project": {
                "type": "string",
                "required": False,
                "description": "Filtrar por proyecto",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": [],
        "example": "python vault_timeline.py\npython vault_timeline.py --project mi-api --limit 20",
        "related": ["vault_audit", "vault_change_log"],
    },
    "vault_change_log": {
        "name": "vault_change_log",
        "script": "vault_change_log.py",
        "group": "Change Log",
        "purpose": "Genera registro de cambios del vault.",        "params": {
            "project": {
                "type": "string",
                "required": False,
                "description": "Proyecto específico",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": [
            "Registra el cambio en el changelog del vault (con --propagate encola la propagación)",
        ],
        "example": 'python vault_change_log.py --query --last 10\npython vault_change_log.py --action "updated" --path "01_Projects/mi-api/overview.md" --summary "Revision"',
        "related": ["vault_timeline", "vault_audit"],
    },
    "vault_gobernanza": {
        "name": "vault_gobernanza",
        "group": "Salud del Vault",
        "purpose": "Valida contenido contra las normas de gobernanza del MCP (secret scan, content gate, brackets, Mermaid).",
        "params": {
            "content": {
                "type": "string",
                "required": True,
                "description": "Contenido a validar",
                "validators": [],
            },
            "folder": {
                "type": "string",
                "required": False,
                "description": "Carpeta destino (para path-anchored links)",
            },
            "vault_root": {
                "type": "string",
                "required": False,
                "description": "Ruta al vault",
            },
            "format": {
                "type": "string",
                "required": False,
                "description": "Formato de salida (json o text)",
            },
            "trace": {
                "type": "boolean",
                "required": False,
                "description": "Incluir trace de validación",
            },
        },
        "guards": [],
        "side_effects": [],
        "status": "active",
        "exposed_via_mcp": True,
        "execution_module": "vault.gobernanza.tool",
    },
    "vault_ai_decision": {
        "name": "vault_ai_decision",
        "script": "vault_ai_decision.py",
        "group": "IA Governance",
        "purpose": "Registra decisiones de IA del proyecto.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
            "rationale": {
                "type": "string",
                "required": True,
                "description": "Razón de la decisión",
                "validators": ["min_length:20"],
            },
            "alternatives": {
                "type": "string",
                "required": False,
                "description": "Alternativas consideradas",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Crea nota en 16_AI_Governance/decisions/"],
        "example": 'python vault_ai_decision.py --project "mi-api" --title "Elegir PostgreSQL" --decision_type "architectural" --description "Motor de datos del servicio" --rationale "Garantias ACID"',
        "related": ["vault_norms", "vault_audit"],
    },
    "vault_norms": {
        "name": "vault_norms",
        "script": "vault_norms.py",
        "group": "Normas",
        "purpose": "Gestiona normas y estándares del vault.",
        "params": {
        },
        "guards": [],
        "side_effects": [
            "Con --apply/--apply-heal edita las notas de norma del vault",
            "Con --rebuild/--audit escribe el registro de normas y sus artefactos derivados",
        ],
        "example": ('python vault_norms.py --list\n'
                    'python vault_norms.py --show AP-25\n'
                    'python vault_norms.py --audit'),
        "related": ["vault_ai_decision", "vault_audit"],
    },
    "vault_smoke": {
        "name": "vault_smoke",
        "script": "vault_smoke.py",
        "group": "Normas",
        "purpose": (
            "AP-42 — ejecuta el ejemplo documentado de cada tool contra una copia "
            "desechable del vault de pruebas y exige que termine, que emita JSON y "
            "que ese JSON tenga `ok`. Baseline que solo puede encoger."
        ),
        "params": {
            "check": {
                "type": "boolean",
                "required": False,
                "description": "Corre el smoke sobre el catálogo",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit 1 si la deuda creció",
                "validators": [],
            },
            "freeze": {
                "type": "boolean",
                "required": False,
                "description": "Recongela la baseline",
                "validators": [],
            },
            "tool": {
                "type": "string",
                "required": False,
                "description": "Ejecuta el smoke de una sola tool",
                "validators": [],
            },
        },
        "guards": ["AP-42"],
        "side_effects": ["scripts/smoke-baseline.json"],
        "example": ("python vault_smoke.py --tool vault_write\n"
                    "python vault_smoke.py --tool vault_search"),
        "related": ["vault_mcp_catalog", "vault_noop_audit"],
    },
    "vault_toolkit_audit": {
        "name": "vault_toolkit_audit",
        "script": "vault_toolkit_audit.py",
        "group": "Normas",
        "purpose": (
            "Verificación funcional del toolkit, tool por tool: que el ejemplo "
            "documentado ejercite la función declarada. Ejecuta TODAS las líneas "
            "`python` del `example` contra copia desechable del sandbox (incluida "
            "la de escritura, que el smoke no corre), contrasta el envelope con "
            "el contrato y con el exit code, mide idempotencia donde se declara, "
            "reparte los hallazgos de paridad CLI↔MCP de los dueños (check_params/"
            "check_sync) y mira cómo falla una `VOAS_*` sin su variable. "
            "Baseline que solo encoge; --doc regenera el informe derivado."
        ),
        "params": {
            "todo": {
                "type": "boolean",
                "required": False,
                "description": "Barrido completo del catálogo",
                "validators": [],
            },
            "tools": {
                "type": "string",
                "required": False,
                "description": "Lista separada por comas de tools a auditar",
                "validators": [],
            },
            "grupo": {
                "type": "array",
                "required": False,
                "description": "Número(s) de grupo según scripts/README.md (una ola)",
                "validators": [],
            },
            "check": {
                "type": "boolean",
                "required": False,
                "description": "Exit 1 con deuda nueva no congelada",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "junto a --check: la deuda congelada aún en rojo también falla",
                "validators": [],
            },
            "freeze": {
                "type": "boolean",
                "required": False,
                "description": "Recongela la baseline con el veredicto de esta corrida",
                "validators": [],
            },
            "admitir-nuevos": {
                "type": "boolean",
                "required": False,
                "description": "junto a --freeze: admisión explícita (y listado) de deuda nueva",
                "validators": [],
            },
            "doc": {
                "type": "boolean",
                "required": False,
                "description": "Regenera docs/auditorias/auditoria-toolkit.md desde el last-run",
                "validators": [],
            },
        },
        "guards": ["AP-42", "AP-37", "AP-47"],
        "side_effects": [
            "scripts/toolkit-audit-baseline.json",
            "scripts/toolkit-audit-last.json",
        ],
        "example": "python vault_toolkit_audit.py --tools vault_voice",
        "related": ["vault_smoke", "vault_noop_audit", "vault_mcp_catalog", "vault_baseline"],
    },
    "vault_voice": {
        "name": "vault_voice",
        "script": "vault_voice.py",
        "group": "Normas",
        "purpose": (
            "AP-43 — refuerzo de normas en el punto de uso. Deriva de NORM_CATALOG "
            "el bloque `vault_says` que wrap_main añade a cada resultado de tool, y "
            "permite consultarlo: qué normas gobiernan una tool concreta y qué "
            "normas no pronuncia ninguna."
        ),
        "params": {
            "tool": {
                "type": "string",
                "required": False,
                "description": "Normas que gobiernan una tool",
                "validators": [],
            },
            "coverage": {
                "type": "boolean",
                "required": False,
                "description": "Normas que ninguna tool pronuncia",
                "validators": [],
            },
        },
        "guards": ["AP-43"],
        "side_effects": ["00_System/.voice-counter"],
        "example": "python vault_voice.py --tool vault_write\npython vault_voice.py --coverage",
        "related": ["vault_norms", "vault_errors"],
    },
    "vault_changelog_check": {
        "name": "vault_changelog_check",
        "script": "vault_changelog_check.py",
        "group": "Normas",
        "purpose": (
            "Contrasta el changelog del manifiesto contra git: que el hash citado "
            "exista, que la fecha coincida con la del commit, que ninguna versión "
            "cerrada siga publicando `git: pending` y que el orden sea decreciente. "
            "Con --fijar-hash cierra la versión en curso sustituyendo el `pending` "
            "por el hash real, que hasta ahora era un commit manual de ritual."
        ),
        "params": {
            "check": {
                "type": "boolean",
                "required": False,
                "description": "Contrasta cada entrada con el commit que cita",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit code 1 ante cualquier problema (uso en CI)",
                "validators": [],
            },
            "list": {
                "type": "boolean",
                "required": False,
                "description": "Tabla de entradas con la fecha real de su commit",
                "validators": [],
            },
            "fijar_hash": {
                "type": "boolean",
                "required": False,
                "description": "Sustituye el `pending` de la versión en curso",
                "validators": [],
            },
            "hash": {
                "type": "string",
                "required": False,
                "description": "Commit a citar con --fijar-hash (por defecto HEAD)",
                "validators": [],
            },
            "dry_run": {
                "type": "boolean",
                "required": False,
                "description": "Con --fijar-hash, no escribe el manifiesto",
                "validators": [],
            },
            "freeze": {
                "type": "boolean",
                "required": False,
                "description": "Anota divergencias de fecha que no se pueden corregir",
                "validators": [],
            },
        },
        "guards": [
            "Usa la fecha de autoría (%as), no la de commit: un rebase reescribe la "
            "segunda y estrenaría divergencias falsas",
            "--fijar-hash no commitea: escribe el manifiesto y devuelve el mensaje "
            "de commit sugerido. Una tool de gobernanza no toca el historial",
            "--freeze se niega a congelar divergencias nuevas (DEBT_WOULD_GROW): la "
            "baseline solo puede encoger",
            "Sin repositorio git no inventa un veredicto: publica git_available: false",
        ],
        "side_effects": [
            "Con --fijar-hash reescribe la entrada de la versión en curso",
            "Con --freeze escribe scripts/changelog-baseline.json",
        ],
        "example": (
            "python vault_changelog_check.py --check --strict\n"
            "python vault_changelog_check.py --list\n"
            "python vault_changelog_check.py --fijar-hash --dry-run"
        ),
        "related": ["vault_doc_counts", "vault_standard_upgrade", "vault_norms"],
    },
    "vault_doc_counts": {
        "name": "vault_doc_counts",
        "script": "vault_doc_counts.py",
        "group": "Normas",
        "purpose": (
            "Guard anti-drift de cifras en documentación: verifica que cada número "
            "escrito a mano en los docs (tools activas, normas, secciones, scripts, "
            "tests) coincida con el registro canónico. El changelog queda excluido: "
            "sus cifras son historia, no drift."
        ),
        "params": {
            "check": {
                "type": "boolean",
                "required": False,
                "description": "Reporta las cifras que divergen del registro",
                "validators": [],
            },
            "fix": {
                "type": "boolean",
                "required": False,
                "description": "Reescribe solo el número, nunca la frase que lo rodea",
                "validators": [],
            },
            "list": {
                "type": "boolean",
                "required": False,
                "description": "Emite los valores vivos derivados del registro",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit code 1 ante cualquier divergencia (uso en CI)",
                "validators": [],
            },
            "no_slow": {
                "type": "boolean",
                "required": False,
                "description": "Omite el conteo de tests (requiere pytest --collect-only)",
                "validators": [],
            },
        },
        "guards": [
            "No reescribe el changelog ni la tabla de versiones (cifras históricas)",
            "Los patrones son deliberadamente específicos: un patrón laxo produce "
            "falsos positivos y el guard acaba desactivado",
        ],
        "side_effects": ["Con --fix reescribe cifras en los documentos vigilados"],
        "example": (
            "python vault_doc_counts.py --list\n"
            "python vault_doc_counts.py --check --strict\n"
            "python vault_doc_counts.py --fix"
        ),
        "related": ["vault_norms", "vault_mcp_catalog", "vault_fundamentals"],
    },
    "vault_doc_sync": {
        "name": "vault_doc_sync",
        "script": "vault_doc_sync.py",
        "group": "Normas",
        "purpose": (
            "Guard anti-drift de nombres entre el registro y scripts/README.md: "
            "toda tool del catálogo tiene sección, toda clave de GROUPS tiene "
            "grupo, y el índice tiene una fila por sección con el ancla resuelta. "
            "Complemento de vault_doc_counts, que vigila las cifras."
        ),
        "params": {
            "check": {
                "type": "boolean",
                "required": False,
                "description": "Reporta tools sin sección, grupos sin sección y filas de índice erróneas",
                "validators": [],
            },
            "fix": {
                "type": "boolean",
                "required": False,
                "description": "Regenera la tabla de índice desde GROUPS (no inventa secciones)",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit code 1 ante cualquier divergencia (uso en CI)",
                "validators": [],
            },
        },
        "guards": [
            "El encabezado de sección usa la clave literal de GROUPS: un título "
            "propio en el README crearía un cuarto vocabulario de grupos",
            "--fix solo toca la tabla de índice; nunca escribe prosa de secciones",
            "Los encabezados fuera de una sección `## Grupo N` no cuentan como drift",
        ],
        "side_effects": ["Con --fix reescribe la tabla de índice de scripts/README.md"],
        "example": (
            "python vault_doc_sync.py --check --strict\n"
            "python vault_doc_sync.py --fix"
        ),
        "related": ["vault_doc_counts", "vault_norms", "vault_mcp_catalog"],
    },
    "vault_doc_staleness": {
        "name": "vault_doc_staleness",
        "script": "vault_doc_staleness.py",
        "group": "Normas",
        "purpose": (
            "Guard anti-drift de artefactos derivados: verifica que los JSON generados "
            "por las tools del catálogo existen, contienen JSON válido y no están huérfanos. "
            "Complemento de vault_doc_counts (cifras) y vault_doc_sync (nombres)."
        ),
        "params": {
            "check": {
                "type": "boolean",
                "required": False,
                "description": "Modo comprobación (informe sin exit code)",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit 1 si falta o está corrupto algún artefacto",
                "validators": [],
            },
        },
        "guards": [
            "No regenera nada: solo verifica existencia y validez de los JSON",
            "Los artefactos los generan otras tools; esta solo los vigila",
        ],
        "side_effects": [],
        "example": (
            "python vault_doc_staleness.py --check\n"
            "python vault_doc_staleness.py --check --strict"
        ),
        "related": ["vault_doc_counts", "vault_doc_sync", "vault_compact_contracts"],
    },
    "vault_fix_all": {
        "name": "vault_fix_all",
        "script": "vault_fix_all.py",
        "group": "Normas",
        "purpose": (
            "Regenera todos los artefactos derivados del registro en el orden "
            "correcto: tools-catalog, env-table, baseline de campos, "
            "ARQUITECTURA, BLUEPRINT, cifras de la documentación e índice de "
            "scripts/README.md. Infraestructura de mantenimiento, no una puerta: "
            "orquesta las herramientas de sync para cerrar el drift recurrente."
        ),
        "params": {
            "dry-run": {
                "type": "boolean",
                "required": False,
                "description": "Muestra el plan de pasos sin ejecutar ninguno",
                "validators": [],
            },
            "step": {
                "type": "integer",
                "required": False,
                "description": "Ejecuta solo un paso (1-7) en vez de todos",
                "validators": [],
            },
        },
        "guards": [
            "El orden de los pasos importa: cada uno lee lo que el anterior regenera",
            "Un paso que falla no detiene los siguientes; se reportan todos",
            "No mide nada: solo regenera; las puertas verifican el resultado",
        ],
        "side_effects": [
            "Regenera tools-catalog.json, env-table.json, field-compat-baseline.json, "
            "docs/ARQUITECTURA.md, docs/BLUEPRINT.md y las cifras del README",
        ],
        "example": (
            "python vault_fix_all.py --dry-run\n"
            "python vault_fix_all.py"
        ),
        "related": ["vault_mcp_catalog", "vault_arch", "vault_blueprint", "vault_doc_counts", "vault_doc_sync"],
    },
    "vault_arch": {
        "name": "vault_arch",
        "script": "vault_arch.py",
        "group": "Normas",
        "purpose": (
            "Plano técnico del estándar: declara los nueve contextos acotados, "
            "su lenguaje ubicuo y sus fronteras, y falla cuando una importación "
            "cruza un límite no declarado. Vigila también AP-49 —vínculos "
            "resueltos en tiempo de import—. Ambas deudas arrancan congeladas y "
            "solo pueden encoger."
        ),
        "params": {
            "check": {
                "type": "boolean", "required": False,
                "description": "Reporta fronteras cruzadas y vínculos congelados",
                "validators": [],
            },
            "strict": {
                "type": "boolean", "required": False,
                "description": "Exit 1 también si se saldó deuda sin recongelar (gate de CI)",
                "validators": [],
            },
            "freeze": {
                "type": "boolean", "required": False,
                "description": "Recongela scripts/arch-baseline.json tras saldar deuda",
                "validators": [],
            },
            "blueprint": {
                "type": "boolean", "required": False,
                "description": "Deriva docs/ARQUITECTURA.md desde el registro CONTEXTS",
                "validators": [],
            },
            "map": {
                "type": "string", "required": False,
                "description": "Dice a qué contexto acotado pertenece un módulo",
                "validators": [],
            },
        },
        "guards": [
            "Todo módulo en disco pertenece a un contexto: sin clasificar es puerta dura, no baseline",
            "El grafo de importaciones se reconstruye por AST, no por una lista escrita a mano que envejecería sola",
            "Depender del kernel no es cruce (límite 1); importar el módulo de otro contexto sí",
        ],
        "side_effects": [
            "Con --freeze reescribe scripts/arch-baseline.json",
            "Con --blueprint reescribe docs/ARQUITECTURA.md",
        ],
        "example": (
            "python vault_arch.py --check --strict\n"
            "python vault_arch.py --map vault_backup\n"
            "python vault_arch.py --blueprint"
        ),
        "related": ["vault_norms", "vault_noop_audit", "vault_mcp_catalog"],
    },
    "vault_error_contract": {
        "name": "vault_error_contract",
        "script": "vault_error_contract.py",
        "group": "Normas",
        "purpose": (
            "AP-52: detecta por AST los envelopes de error construidos a mano "
            "\u2014 `{ok: False, error: ...}` sin `error_code`, `category`, "
            "`severity` ni `recovery` \u2014 que dejan al consumidor sin nada "
            "sobre lo que decidir. Baseline que solo puede encoger."
        ),
        "params": {
            "check": {
                "type": "boolean",
                "required": False,
                "description": "Reporta el estado de la deuda",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit 1 si la deuda crecio respecto a la baseline",
                "validators": [],
            },
            "freeze": {
                "type": "boolean",
                "required": False,
                "description": "Recongela la baseline tras saldar deuda",
                "validators": [],
            },
        },
        "guards": [
            "La baseline solo puede encoger: --strict falla por sitios nuevos, "
            "no por la deuda historica",
            "Mide forma y no flujo: cuenta tambien envelopes internos que nunca "
            "se imprimen, y lo declara en vez de prometer una precision que no tiene",
            "Se excluye a si misma y a vault_errors*, cuyos literales SON el contrato",
        ],
        "side_effects": ["scripts/error-contract-baseline.json (solo con --freeze)"],
        "example": (
            "python vault_error_contract.py --check\n"
            "python vault_error_contract.py --check --strict\n"
            "python vault_error_contract.py --freeze"
        ),
        "related": ["vault_errors", "vault_blame_audit", "vault_noop_audit", "vault_gate"],
    },
    "vault_foreign_check": {
        "name": "vault_foreign_check",
        "script": "vault_foreign_check.py",
        "group": "Normas",
        "purpose": (
            "Regla 7: contrasta las medidas del estandar contra un vault AJENO, "
            "en solo lectura. Unica tool sin destino por defecto \u2014 la "
            "autodeteccion caeria en `vault-sandbox/`, que este repo genera y "
            "que por eso no puede exhibir el fallo que la regla persigue."
        ),
        "params": {
            "root": {
                "type": "string",
                "required": True,
                "description": "Raiz del vault ajeno (obligatoria, sin default)",
                "validators": [],
            },
            "report": {
                "type": "string",
                "required": False,
                "description": "Fichero del informe, siempre fuera del vault medido",
                "validators": [],
            },
            "self-test": {
                "type": "boolean",
                "required": False,
                "description": "Verifica las negativas de la tool, sin vault ajeno",
                "validators": [],
            },
        },
        "guards": [
            "Rechaza cualquier raiz dentro del repo del estandar, sandbox incluido",
            "Solo lectura: no escribe una linea en el vault medido, ni traces ni backups",
            "--report no puede caer dentro del vault medido",
            "Separa lo ilegible de lo ausente: un recuento sobre lo medido no es "
            "un recuento sobre el vault (AP-51)",
            "No emite veredicto de salud: mide si nuestras medidas sobreviven al "
            "material ajeno, no la calidad de ese material",
        ],
        "side_effects": [],
        "example": (
            "python vault_foreign_check.py --root D:/vaults/notas\n"
            "python vault_foreign_check.py --root D:/vaults/notas --report informe.json\n"
            "python vault_foreign_check.py --self-test"
        ),
        "related": ["vault_validate", "vault_graph_inspect", "vault_norms"],
    },
    "vault_gate": {
        "name": "vault_gate",
        "script": "vault_gate.py",
        "group": "Normas",
        "purpose": (
            "La puerta unica: corre todas las puertas de cierre como "
            "subprocesos y agrega el veredicto. La lista canonica de puertas "
            "vive en el registro PUERTAS, y --check-doc verifica que el "
            "checklist de AGENTS.md las cite todas. No reimplementa ninguna "
            "comprobacion ni baja el enforcement de ninguna norma."
        ),
        "params": {
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit 1 si alguna puerta falla (gate de CI)",
                "validators": [],
            },
            "list": {
                "type": "boolean",
                "required": False,
                "description": "Lista las puertas y que mide cada una, sin ejecutarlas",
                "validators": [],
            },
            "check-doc": {
                "type": "boolean",
                "required": False,
                "description": "Comprueba que el checklist de AGENTS.md cite todas las puertas",
                "validators": [],
            },
        },
        "guards": [
            "El registro manda sobre el doc: una puerta ausente del checklist "
            "se anade al checklist, no se quita del registro",
            "Cada puerta corre como subproceso con su propio exit code: mirar "
            "los datos por su cuenta seria una segunda fuente de verdad (AP-05) "
            "y medirlos con criterio propio (AP-44)",
            "No sustituye a pytest: verde aqui no es verde en la suite",
        ],
        "side_effects": [],
        "example": (
            "python vault_gate.py --list\n"
            "python vault_gate.py --check-doc"
        ),
        "related": ["vault_norms", "vault_arch", "vault_noop_audit", "vault_blame_audit"],
    },
    "vault_blueprint": {
        "name": "vault_blueprint",
        "script": "vault_blueprint.py",
        "group": "Normas",
        "purpose": (
            "El plano de construccion: ata los once registros canonicos en "
            "siete capas —servicio, capacidades, contextos, normas, tools, "
            "trazabilidad y deuda— y genera docs/BLUEPRINT.md. El documento es "
            "derivado: --check falla si diverge del registro, asi que ninguna "
            "cifra del plano se escribe a mano. No reimplementa ningun guard."
        ),
        "params": {
            "blueprint": {
                "type": "boolean",
                "required": False,
                "description": "Regenera docs/BLUEPRINT.md desde los registros",
                "validators": [],
            },
            "check": {
                "type": "boolean",
                "required": False,
                "description": "El doc publicado y la trazabilidad contra los registros",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit 1 si el plano diverge o hay eslabon roto",
                "validators": [],
            },
            "freeze": {
                "type": "boolean",
                "required": False,
                "description": "Congela la deuda de la capa 4 (norma sin puerta ni test)",
                "validators": [],
            },
            "admitir-nuevos": {
                "type": "boolean",
                "required": False,
                "description": "Permite congelar normas sin cobertura sin precedente",
                "validators": [],
            },
            "layers": {
                "type": "boolean",
                "required": False,
                "description": "Las 7 capas en JSON, sin generar el documento",
                "validators": [],
            },
        },
        "guards": [
            "El plano es derivado: editarlo a mano lo rompe en --check, porque "
            "el registro es la fuente y el documento el efecto",
            "Solo la capa 4 tiene baseline, y solo encoge: una norma nueva sin "
            "puerta ni test no se congela, se le escribe el test",
            "No reimplementa guards: delega en vault_arch, vault_mcp_catalog y "
            "vault_servicio para no ser una segunda fuente de verdad (AP-05)",
        ],
        "side_effects": ["docs/BLUEPRINT.md", "scripts/blueprint-baseline.json"],
        "example": (
            "python vault_blueprint.py --blueprint\n"
            "python vault_blueprint.py --check --strict\n"
            "python vault_blueprint.py --freeze"
        ),
        "related": ["vault_servicio", "vault_arch", "vault_gate", "vault_norms"],
    },
    "vault_criterios": {
        "name": "vault_criterios",
        "script": "vault_criterios.py",
        "group": "Normas",
        "purpose": (
            "AP-57: un criterio con dueno canonico, reimplementado en la "
            "medida. Generaliza AP-50 de patrones regex a criterios — que es "
            "una instantanea, que es documentacion del estandar, que es codigo "
            "y no enlace. Sale de v40.12, donde los cuatro defectos de "
            "vault_foreign_check tenian la misma forma: el registro existia y "
            "la tool no lo consultaba. Detecta por la constante distintiva del "
            "dueno, y solo en modulos que clasifican notas."
        ),
        "params": {
            "check": {
                "type": "boolean",
                "required": False,
                "description": "Mide los criterios contra los modulos vivos",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit 1 si aparece una copia nueva",
                "validators": [],
            },
            "freeze": {
                "type": "boolean",
                "required": False,
                "description": "Recongela la baseline de copias preexistentes",
                "validators": [],
            },
            "admitir-nuevos": {
                "type": "boolean",
                "required": False,
                "description": "Permite congelar copias sin precedente",
                "validators": [],
            },
        },
        "guards": [
            "Verde no prueba que no haya copias: prueba que no hay copias de "
            "la forma que la tool sabe reconocer, y eso se dice en el envelope",
            "Solo mira modulos que clasifican notas: quien escribe la "
            "constante por otro motivo legitimo — vault_restore nombra "
            "vault-backups porque restaurar de ahi es su trabajo — no es copia",
            "Baseline que solo encoge: una copia nueva se importa, no se congela",
        ],
        "side_effects": ["scripts/criterios-baseline.json"],
        "example": (
            "python vault_criterios.py --check\n"
            "python vault_criterios.py --check --strict\n"
            "python vault_criterios.py --freeze"
        ),
        "related": ["vault_norms", "vault_io", "vault_lib", "vault_gate"],
    },
    "vault_ciclos": {
        "name": "vault_ciclos",
        "script": "vault_ciclos.py",
        "group": "Normas",
        "purpose": (
            "AP-58: el ciclo de importacion que se esquiva metiendo el import "
            "dentro de una funcion. Este repo declaraba cero ciclos y era "
            "verdad mirando solo el nivel de modulo; el cero lo fabricaban 92 "
            "imports diferidos en 40 modulos. Contando esas aristas aparece un "
            "componente fuertemente conexo de 14 modulos con el nucleo entero "
            "dentro. Solo entran en la deuda los 30 que esquivan un ciclo: los "
            "otros 62 se difieren por coste de arranque o dependencia opcional "
            "y se publican sin congelarse."
        ),
        "params": {
            "check": {
                "type": "boolean",
                "required": False,
                "description": "Calcula los componentes contando aristas diferidas",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit 1 si aparece un ciclo diferido nuevo",
                "validators": [],
            },
            "freeze": {
                "type": "boolean",
                "required": False,
                "description": "Recongela la baseline de ciclos preexistentes",
                "validators": [],
            },
            "admitir-nuevos": {
                "type": "boolean",
                "required": False,
                "description": "Permite congelar ciclos sin precedente",
                "validators": [],
            },
        },
        "guards": [
            "Mide el grafo estatico de modulos: no ve importlib, ni un import "
            "construido con una cadena, ni el acoplamiento que pasa por el "
            "sistema de ficheros o por una variable global compartida",
            "Solo son deuda los diferidos cuyo destino vuelve al origen; una "
            "baseline llena de aristas benignas es una que nadie revisa",
            "Baseline que solo encoge: un ciclo nuevo se invierte, no se "
            "congela, y subir el import tampoco lo arregla — solo lo hace "
            "visible al arrancar",
        ],
        "side_effects": ["scripts/ciclos-baseline.json"],
        "example": (
            "python vault_ciclos.py --check\n"
            "python vault_ciclos.py --check --strict\n"
            "python vault_ciclos.py --freeze"
        ),
        "related": ["vault_arch", "vault_norms", "vault_gate", "vault_blueprint"],
    },
    "vault_recursos": {
        "name": "vault_recursos",
        "script": "vault_recursos.py",
        "group": "Normas",
        "purpose": (
            "AP-62: el consumidor cruza una frontera de contexto para leer un "
            "recurso —una constante, una funcion pura— y por el camino paga "
            "todo el fan-out del productor. Es el patron que v40.27 encontro "
            "por accidente en vault_norms: 21 de sus 24 importadores solo "
            "querian una tabla y entraban por una fachada que arrastra el "
            "motor. Esta tool lo busca en los 136 modulos en vez de a ojo, y "
            "publica el ranking de productores por cuantos cruces colapsaria "
            "darle a cada recurso un dueno con forma de hoja."
        ),
        "params": {
            "check": {
                "type": "boolean",
                "required": False,
                "description": "Clasifica cada arista del grafo y mide el arrastre",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit 1 si aparece un sitio de arrastre nuevo",
                "validators": [],
            },
            "ranking": {
                "type": "boolean",
                "required": False,
                "description": "Productores ordenados por cruces que colapsan",
                "validators": [],
            },
            "freeze": {
                "type": "boolean",
                "required": False,
                "description": "Recongela la baseline de arrastre preexistente",
                "validators": [],
            },
            "admitir-nuevos": {
                "type": "boolean",
                "required": False,
                "description": "Permite congelar arrastre sin precedente",
                "validators": [],
            },
        },
        "guards": [
            "Mide `from X import y`, no `import X`: quien importa el modulo "
            "entero no declara que usa, sale del alcance y se publica en "
            "importadores_opacos",
            "La pureza se decide por AST y a punto fijo: un simbolo se contagia "
            "de acoplado si nombra a otro que ya lo esta. Una funcion que "
            "dependa de un global mutable del modulo pasara por pura",
            "Las clases se dan por acopladas sin mirar el cuerpo — se prefiere "
            "no contar un sitio a contar uno que no lo es",
            "Solo es deuda el arrastre que cruza contexto; el intracontexto se "
            "publica sin congelarse, porque no lo es mientras los dos modulos "
            "compartan contexto",
        ],
        "side_effects": ["scripts/recursos-baseline.json"],
        "example": (
            "python vault_recursos.py --check\n"
            "python vault_recursos.py --ranking\n"
            "python vault_recursos.py --check --strict"
        ),
        "related": ["vault_arch", "vault_ciclos", "vault_kernel", "vault_blueprint"],
    },
    "vault_esquema": {
        "name": "vault_esquema",
        "script": "vault_esquema.py",
        "group": "Normas",
        "purpose": (
            "Publica el contrato de campos de una nota (vault_contrato_nota) como "
            "un JSON Schema 2020-12 por version mayor del estandar, todos al lado "
            "en schemas/: un vault que se quedo en v28 se valida contra lo que v28 "
            "exigia. Quien consume un vault sin este toolkit no puede importar el "
            "contrato Python; puede leer el esquema. Los ficheros son derivados: "
            "--check falla si divergen del contrato."
        ),
        "params": {
            "check": {
                "type": "boolean",
                "required": False,
                "description": "Falla si schemas/ diverge del contrato",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit 1 si algo diverge",
                "validators": [],
            },
            "sync": {
                "type": "boolean",
                "required": False,
                "description": "Regenera schemas/ desde el contrato",
                "validators": [],
            },
            "version": {
                "type": "string",
                "required": False,
                "description": "Imprime el esquema de una version (v21..)",
                "validators": [],
            },
        },
        "guards": [
            "El esquema restringe solo lo que vault_validate restringia en esa "
            "version: uno mas estricto reprobaria notas que la tool aprueba (AP-44)",
            "Antes de v21 no hay migracion registrada y no se publica esquema; de "
            "v21 a v24 no habia validador y el esquema lo declara",
            "Un esquema en schemas/ sin version en el contrato no se borra: se "
            "informa en unknown",
        ],
        "side_effects": ["schemas/"],
        "example": (
            "python vault_esquema.py --check --strict\n"
            "python vault_esquema.py --sync"
        ),
        "related": ["vault_validate", "vault_gate", "vault_frontmatter_heal"],
    },
    "vault_metricas": {
        "name": "vault_metricas",
        "script": "vault_metricas.py",
        "group": "Normas",
        "purpose": (
            "Metricas de desarrollo (deuda pendiente, baselines vencidas, fallos "
            "y duracion de la suite) y de producto (smoke, banco del agente, "
            "recall sobre un vault ajeno, promesas sin ejecutor), cada una con "
            "que mide, de donde sale, objetivo con fecha, cadencia y dueno, o "
            "el motivo escrito de no tenerlo. Las calculadas se derivan del "
            "repo; las observadas se guardan con el commit que las produjo en "
            "un historico que solo crece."
        ),
        "params": {
            "check": {"type": "boolean", "required": False,
                      "description": "Registro, historico y documento", "validators": []},
            "strict": {"type": "boolean", "required": False,
                       "description": "Exit 1 si el check falla", "validators": []},
            "doc": {"type": "boolean", "required": False,
                    "description": "Regenera docs/METRICAS.md", "validators": []},
            "registrar-suite": {"type": "string", "required": False,
                                "description": "Log de una ronda de pytest", "validators": []},
            "registrar-smoke": {"type": "string", "required": False,
                                "description": "Salida JSON de vault_smoke", "validators": []},
            "registrar-banco": {"type": "string", "required": False,
                                "description": "Informe JSON de banco_agente", "validators": []},
            "registrar": {"type": "string", "required": False,
                          "description": "Registra una metrica observada", "validators": []},
            "valor": {"type": "number", "required": False,
                      "description": "Valor para --registrar", "validators": []},
            "fuente": {"type": "string", "required": False,
                       "description": "De donde sale la observacion", "validators": []},
            "commit": {"type": "string", "required": False,
                       "description": "Commit sobre el que se midio (por defecto HEAD)",
                       "validators": []},
        },
        "guards": [
            "El plazo del objetivo se valida con vault_baseline.validar_plazo, el "
            "mismo contrato que las baselines (AP-57)",
            "Una observacion cuyo commit no existe en git, o que estaba en HEAD y "
            "desaparece, pone la puerta en rojo (AP-53)",
            "Un log de pytest sin linea de resumen no se registra como cero fallos",
            "Lo vencido y lo desactualizado se publica en alertas sin poner la "
            "puerta en rojo",
        ],
        "side_effects": ["scripts/metricas-observaciones.json", "docs/METRICAS.md"],
        "example": (
            "python vault_metricas.py --check --strict\n"
            "python vault_metricas.py --doc"
        ),
        "related": ["vault_blueprint", "vault_produccion", "vault_smoke", "vault_gate"],
    },
    "vault_produccion": {
        "name": "vault_produccion",
        "script": "vault_produccion.py",
        "group": "Normas",
        "purpose": (
            "Puede usar esto otra persona, y con que fiabilidad. Las demas "
            "puertas miden el repo contra si mismo —que el catalogo no "
            "diverja del JSON, que la baseline no crezca— y en esa sala no "
            "esta el consumidor. Esta tool registra cada promesa que se le hace "
            "a quien instala (version minima, dependencias, plataformas, "
            "superficie de red) junto a quien la ejerce de verdad, y falla "
            "cuando una promesa marcada como cubierta se queda sin ejecutor. "
            "Nacio de medir la pregunta en vez de opinarla: pyproject prometia "
            ">=3.9, la CI corria solo 3.11, y seis sitios rompian al IMPORTAR "
            "en 3.9 sin que nada lo viera."
        ),
        "params": {
            "check": {
                "type": "boolean",
                "required": False,
                "description": "Mide cada promesa contra su ejecutor",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit 1 si alguna promesa perdio su ejecutor",
                "validators": [],
            },
            "guia": {
                "type": "boolean",
                "required": False,
                "description": "Regenera docs/GUIA-DE-PRODUCCION.md desde el registro",
                "validators": [],
            },
            "check-doc": {
                "type": "boolean",
                "required": False,
                "description": "Falla si la guia diverge del registro",
                "validators": [],
            },
        },
        "guards": [
            "Verde significa que toda promesa LISTADA tiene ejecutor, no que la "
            "lista este completa: una promesa que nadie escribio en el registro "
            "sigue sin medirse, y esta tool no lee el README donde la hiciste",
            "Comprueba que el ejecutor EXISTA, no que pase — eso es trabajo de "
            "la CI y de la suite; existir era la condicion que faltaba",
            "Una promesa `descubierta` con motivo escrito no rompe la puerta: "
            "declarar un hueco no puede salir mas caro que callarlo",
        ],
        "side_effects": ["docs/GUIA-DE-PRODUCCION.md"],
        "example": (
            "python vault_produccion.py --check\n"
            "python vault_produccion.py --check --strict\n"
            "python vault_produccion.py --guia"
        ),
        "related": ["vault_gate", "vault_foreign_check", "vault_blueprint"],
    },
    "vault_excepcion_declarada": {
        "name": "vault_excepcion_declarada",
        "script": "vault_excepcion_declarada.py",
        "group": "Normas",
        "purpose": (
            "AP-61: el handler que captura la excepcion que una libreria "
            "declara y deja escapar la que lanza de verdad. RecursionError no "
            "hereda de yaml.YAMLError, y el parser de PyYAML es recursivo: doce "
            "caracteres de anidamiento en el frontmatter de UNA nota desbordan "
            "la pila dentro de safe_load y tumban el barrido entero del vault. "
            "vault_lib.parse_frontmatter lo contuvo en su dia; los otros doce "
            "sitios que habian copiado el mismo try no se enteraron, uno de "
            "ellos vault_foreign_check, que es la tool de la regla 7."
        ),
        "params": {
            "check": {
                "type": "boolean",
                "required": False,
                "description": "Recorre los try con llamada de riesgo a la vista",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit 1 si aparece un handler sin la excepcion que escapa",
                "validators": [],
            },
            "freeze": {
                "type": "boolean",
                "required": False,
                "description": "Recongela la baseline; nace vacia y solo encoge",
                "validators": [],
            },
            "admitir-nuevos": {
                "type": "boolean",
                "required": False,
                "description": "Permite congelar sitios sin precedente, y los lista",
                "validators": [],
            },
        },
        "guards": [
            "Solo ve la llamada de riesgo escrita a la vista en el cuerpo del "
            "try: un safe_load detras de un helper queda fuera, asi que mide "
            "mejor el codigo que peor esta escrito, y lo declara",
            "No valida que la contencion sea correcta, solo que la excepcion "
            "este nombrada",
            "Baseline que solo encoge, y nace vacia: los doce sitios que habia "
            "se corrigieron en v40.23 en vez de congelarse",
        ],
        "side_effects": ["scripts/excepcion-declarada-baseline.json"],
        "example": (
            "python vault_excepcion_declarada.py --check\n"
            "python vault_excepcion_declarada.py --check --strict\n"
            "python vault_excepcion_declarada.py --freeze"
        ),
        "related": ["vault_blame_audit", "vault_error_contract", "vault_criterios",
                    "vault_gate"],
    },
    "vault_kernel": {
        "name": "vault_kernel",
        "script": "vault_kernel.py",
        "group": "Normas",
        "purpose": (
            "AP-59: el nucleo se declara pero nadie lo mide. La lista del "
            "kernel es una enumeracion escrita a mano en vault_arch y ninguna "
            "puerta la contrasta con la forma real del grafo. Mide tres "
            "invariantes: K1 (el nucleo no depende del dominio) delegada en "
            "vault_arch.dependencias_del_kernel, K2 (fan-in alto, fan-out bajo) "
            "desde el dueno unico del grafo de imports, y K3 (estabilidad) por "
            "churn de git contra la mediana del dominio. Con la lista bien "
            "elegida, en v40.20 salieron aun asi tres modulos del kernel que no "
            "se comportan como nucleo. --trace responde si toco esto, que se cae."
        ),
        "params": {
            "check": {
                "type": "boolean",
                "required": False,
                "description": "Mide las tres invariantes y publica los umbrales derivados",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit 1 si aparece un hallazgo sin precedente",
                "validators": [],
            },
            "trace": {
                "type": "string",
                "required": False,
                "description": "Camino mas corto de un modulo hasta el nucleo",
                "validators": [],
            },
            "freeze": {
                "type": "boolean",
                "required": False,
                "description": "Recongela la baseline de hallazgos preexistentes",
                "validators": [],
            },
            "admitir-nuevos": {
                "type": "boolean",
                "required": False,
                "description": "Permite congelar hallazgos sin precedente",
                "validators": [],
            },
        },
        "guards": [
            "No parsea un solo import ni reimplementa K1: si midiera su propia "
            "pureza con su propio criterio seria AP-44 cometido en la tool que "
            "existe para trazar el nucleo",
            "Los umbrales se derivan del escalon de la distribucion y se "
            "publican con su ratio en cada ejecucion; un literal aqui seria "
            "AP-47 dentro de AP-59",
            "Sin historia de git el churn sale desconocido, nunca 0: un cero "
            "fabricado saldria verde por no haber mirado (AP-51)",
            "Mide forma, no proposito: un modulo puede tener fan-in altisimo y "
            "no ser nucleo de nada, solo un cajon que todo el mundo toca",
            "Baseline por nombre de modulo que solo encoge; los ganchos del "
            "kernel se publican como informativos y no bloquean, porque el "
            "mecanismo que los cerraria todavia no existe",
        ],
        "side_effects": ["scripts/kernel-baseline.json"],
        "example": (
            "python vault_kernel.py --check\n"
            "python vault_kernel.py --check --strict\n"
            "python vault_kernel.py --trace vault_context_pack"
        ),
        "related": ["vault_arch", "vault_ciclos", "vault_gate", "vault_blueprint"],
    },
    "vault_fuente_unica": {
        "name": "vault_fuente_unica",
        "script": "vault_fuente_unica.py",
        "group": "Salud del Vault",
        "purpose": (
            "AP-05: el mismo dato con valores distintos en varias notas. Era "
            "la unica norma critical sin detector desde v19, porque decidir "
            "que es el mismo dato sin embeddings es un problema abierto. Lo es "
            "en general, no para un valor tipado: una IP, una URL, un puerto o "
            "un semver escritos como clave: valor llevan su identidad al lado "
            "y se comparan por igualdad. Cubre esa parte y declara el resto."
        ),
        "params": {
            "check": {
                "type": "boolean",
                "required": False,
                "description": "Mide los conflictos de fuente de verdad",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit 1 si aparece un conflicto nuevo",
                "validators": [],
            },
            "report": {
                "type": "boolean",
                "required": False,
                "description": "Los conflictos legibles: que valor dice cada nota",
                "validators": [],
            },
            "freeze": {
                "type": "boolean",
                "required": False,
                "description": "Recongela la baseline de conflictos preexistentes",
                "validators": [],
            },
            "admitir-nuevos": {
                "type": "boolean",
                "required": False,
                "description": "Permite congelar conflictos sin precedente",
                "validators": [],
            },
            "root": {
                "type": "string",
                "required": False,
                "description": "Vault ajeno a contrastar, solo lectura (regla 7)",
                "validators": [],
            },
        },
        "guards": [
            "Verde no prueba una sola fuente de verdad: prueba que no hay "
            "divergencia de la clase decidible sin interpretar. La prosa, el "
            "valor sin tipo y el sinonimo quedan fuera y se declaran",
            "Solo compara valores tipados: un status o un owner divergen entre "
            "notas legitimamente, y medirlos seria ruido",
            "Excluye instantaneas, documentacion del estandar y bloques de "
            "codigo preguntando a sus duenos canonicos (AP-57)",
            "Baseline que solo encoge: un conflicto nuevo se resuelve con PAT-1",
        ],
        "side_effects": ["scripts/fuente-unica-baseline.json"],
        "example": (
            "python vault_fuente_unica.py --check\n"
            "python vault_fuente_unica.py --report\n"
            "python vault_fuente_unica.py --check --strict"
        ),
        "related": ["vault_norms", "vault_regex", "vault_audit", "vault_gate"],
    },
    "vault_norms_coherence": {
        "name": "vault_norms_coherence",
        "script": "vault_norms_coherence.py",
        "group": "Normas",
        "purpose": (
            "AP-55: cruza NORM_CATALOG con el codigo y con "
            "vault_audit.PENALIZACIONES. El catalogo declara a mano que tools "
            "aplican y detectan cada norma, y hasta v40.10 nada lo contrastaba: "
            "el guard que existia para ello leia el catalogo contra el "
            "catalogo. Cinco medidas — el enforcer resuelve, la afirmacion "
            "tiene traza, el enforcement concuerda con los campos, la "
            "severidad no invierte la penalizacion y la distincion entre dos "
            "normas es reciproca."
        ),
        "params": {
            "check": {
                "type": "boolean",
                "required": False,
                "description": "Las cinco medidas contra el catalogo vivo",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit 1 si alguna medida falla",
                "validators": [],
            },
            "freeze": {
                "type": "boolean",
                "required": False,
                "description": "Recongela la baseline de afirmaciones sin traza",
                "validators": [],
            },
            "admitir-nuevos": {
                "type": "boolean",
                "required": False,
                "description": "Permite congelar afirmaciones sin precedente",
                "validators": [],
            },
        },
        "guards": [
            "La traza no demuestra enforcement y no se presenta como si lo "
            "hiciera: demuestra lo contrario, que la afirmacion no es "
            "seguible hasta el codigo que la cumple",
            "Solo C2 tiene baseline, y solo encoge: se salda nombrando la "
            "norma en el sitio que la aplica o retirando la afirmacion",
            "Los pesos se leen de vault_audit.PENALIZACIONES, no se copian: "
            "el peso lo declara quien lo aplica",
        ],
        "side_effects": ["scripts/norms-coherence-baseline.json"],
        "example": (
            "python vault_norms_coherence.py --check\n"
            "python vault_norms_coherence.py --check --strict\n"
            "python vault_norms_coherence.py --freeze"
        ),
        "related": ["vault_norms", "vault_audit", "vault_voice", "vault_gate"],
    },
    "vault_servicio": {
        "name": "vault_servicio",
        "script": "vault_servicio.py",
        "group": "Normas",
        "purpose": (
            "El pilar: declara el servicio de negocio del estandar y las "
            "capacidades que lo realizan, y exige la trazabilidad "
            "tool -> grupo -> capacidad -> servicio. Todo grupo del catalogo "
            "pertenece a exactamente una capacidad y toda capacidad tiene al "
            "menos una tool viva; si no, falla. Los group_id salen de "
            "mapa_de_grupos(), no de una numeracion propia."
        ),
        "params": {
            "list": {
                "type": "boolean",
                "required": False,
                "description": "Servicio, restricciones y capacidades declaradas",
                "validators": [],
            },
            "trace": {
                "type": "boolean",
                "required": False,
                "description": "Una fila por tool: grupo, capacidad y servicio",
                "validators": [],
            },
            "check": {
                "type": "boolean",
                "required": False,
                "description": "Trazabilidad exigida: grupos huerfanos, capacidades vacias",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit 1 si la trazabilidad tiene un eslabon roto",
                "validators": [],
            },
        },
        "guards": [
            "Sin baseline: se mide cero al declararla porque los 37 grupos se "
            "clasifican en la misma tanda. Una baseline permitiria anadir un "
            "grupo sin decidir a que sirve, que es el vacio que cierra",
            "Un grupo huerfano no se arregla ampliando una capacidad al azar",
            "Los group_id se derivan de mapa_de_grupos(): no hay numeracion propia",
        ],
        "side_effects": [],
        "example": (
            "python vault_servicio.py --list\n"
            "python vault_servicio.py --trace\n"
            "python vault_servicio.py --check --strict"
        ),
        "related": ["vault_mcp_catalog", "vault_arch", "vault_gate"],
    },
    "vault_blame_audit": {
        "name": "vault_blame_audit",
        "script": "vault_blame_audit.py",
        "group": "Normas",
        "purpose": (
            "AP-51 \u2014 detecta handlers amplios que se tragan el fallo propio "
            "y devuelven un vacio indistinguible de un resultado legitimo, con "
            "lo que un error acaba contado como un hecho sobre el vault. "
            "Compara contra una baseline congelada: la deuda historica no "
            "bloquea, pero no puede crecer."
        ),
        "params": {
            "check": {
                "type": "boolean",
                "required": False,
                "description": "Reporta el estado de la deuda AP-51",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit 1 si aparecieron sitios nuevos (gate de CI)",
                "validators": [],
            },
            "freeze": {
                "type": "boolean",
                "required": False,
                "description": "Recongela scripts/blame-baseline.json tras saldar deuda",
                "validators": [],
            },
        },
        "guards": [
            "La baseline solo puede encoger: todo codigo nuevo nace conforme",
            "Se mide por AST y no por texto: buscar la cadena 'except Exception' "
            "no distingue devolver un vacio de devolver ok: false, que es toda "
            "la distincion que la norma sostiene",
            "La clave es modulo:linea y no un conteo por modulo: una baseline "
            "por conteo se salda arreglando un sitio y estrenando otro",
        ],
        "side_effects": ["Con --freeze reescribe scripts/blame-baseline.json"],
        "example": (
            "python vault_blame_audit.py --check\n"
            "python vault_blame_audit.py --check --strict\n"
            "python vault_blame_audit.py --freeze"
        ),
        "related": ["vault_norms", "vault_noop_audit", "vault_arch"],
    },
    "vault_noop_audit": {
        "name": "vault_noop_audit",
        "script": "vault_noop_audit.py",
        "group": "Normas",
        "purpose": (
            "AP-37 — detecta tools con side effects que devuelven ok: true sin "
            "exponer ningún indicador de trabajo. Compara contra una baseline "
            "congelada: la deuda histórica no bloquea, pero no puede crecer."
        ),
        "params": {
            "check": {
                "type": "boolean",
                "required": False,
                "description": "Reporta el estado de la deuda AP-37",
                "validators": [],
            },
            "strict": {
                "type": "boolean",
                "required": False,
                "description": "Exit 1 si aparecieron infractoras nuevas (gate de CI)",
                "validators": [],
            },
            "freeze": {
                "type": "boolean",
                "required": False,
                "description": "Recongela scripts/noop-baseline.json tras saldar deuda",
                "validators": [],
            },
        },
        "guards": [
            "La baseline solo puede encoger: toda tool nueva nace conforme",
            "WORK_INDICATORS se amplía deliberadamente — añadir un campo siempre "
            "presente (path, ok) vaciaría la norma de contenido",
        ],
        "side_effects": ["Con --freeze reescribe scripts/noop-baseline.json"],
        "example": (
            "python vault_noop_audit.py --check\n"
            "python vault_noop_audit.py --check --strict\n"
            "python vault_noop_audit.py --freeze"
        ),
        "related": ["vault_norms", "vault_doc_counts", "vault_standard_upgrade"],
    },
    "vault_tokens": {
        "name": "vault_tokens",
        "script": "vault_tokens.py",
        "group": "Tokens",
        "purpose": "Gestión de tokens del proyecto.",
        "params": {
        },
        "guards": ["No guardar tokens en texto plano"],
        "side_effects": [],
        "example": 'python vault_tokens.py --summary\npython vault_tokens.py --since "2026-01-01" --top 10',
        "related": ["vault_token_counter", "vault_token_service"],
    },
    "vault_token_counter": {
        "name": "vault_token_counter",
        "script": "vault_token_counter.py",
        "group": "Tokens",
        "purpose": "Cuenta tokens de contenido.",
        "params": {
        },
        "guards": [],
        "side_effects": [],
        "example": 'python vault_token_counter.py self-test',
        "related": ["vault_tokens", "vault_token_service"],
    },
    "vault_token_service": {
        "name": "vault_token_service",
        "script": "vault_token_service.py",
        "group": "Tokens",
        "purpose": "Servicio de gestión de tokens.",
        "params": {
        },
        "guards": [],
        "side_effects": [
            "Sirve la API HTTP local y escribe los flujos de tokens y los ficheros de estado del servicio",
        ],
        "example": 'python vault_token_service.py --host "127.0.0.1" --port "8899"',
        "related": ["vault_tokens", "vault_token_counter"],
    },
    "vault_requirement_save": {
        "name": "vault_requirement_save",
        "script": "vault_requirement_save.py",
        "group": "Requerimientos",
        "purpose": "Guarda requerimiento del proyecto.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
            "title": {
                "type": "string",
                "required": True,
                "description": "Título del requerimiento",
                "validators": ["not_empty"],
            },
            "description": {
                "type": "string",
                "required": True,
                "description": "Descripción",
                "validators": ["min_length:20"],
            },
            "priority": {
                "type": "string",
                "required": True,
                "description": "Prioridad: critical, high, medium, low",
                "validators": ["enum:critical,high,medium,low"],
            },
            "status": {
                "type": "string",
                "required": False,
                "description": "Status: draft, reviewed, approved, implemented, verified, obsolete",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Crea nota en 01_Projects/{project}/requirements/"],
        "example": 'python vault_requirement_save.py --project "mi-api" --title "Auth" --description "Login de usuario" --type "functional" --priority "must-have"',
        "related": ["vault_test_save", "vault_audit"],
    },
    "vault_test_save": {
        "name": "vault_test_save",
        "script": "vault_test_save.py",
        "group": "Tests",
        "purpose": "Guarda casos de prueba.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
            "description": {
                "type": "string",
                "required": True,
                "description": "Descripción del test",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Crea nota en 01_Projects/{project}/tests/"],
        "example": 'python vault_test_save.py --project "mi-api" --title "Login" --test_type "unit" --description "Verifica el login"',
        "related": ["vault_requirement_save", "vault_code_module"],
    },
    "vault_runbook_save": {
        "name": "vault_runbook_save",
        "script": "vault_runbook_save.py",
        "group": "Runbooks",
        "purpose": "Guarda runbook de operaciones.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
            "trigger": {
                "type": "string",
                "required": True,
                "description": "Trigger: manual, alert, schedule",
                "validators": ["enum:manual,alert,schedule"],
            },
            "steps": {
                "type": "string",
                "required": True,
                "description": "Pasos en Markdown",
                "validators": ["min_lines:5"],
            },
        },
        "guards": [],
        "side_effects": ["Crea nota en 08_Runbooks/{project}/"],
        "example": 'python vault_runbook_save.py --project "mi-api" --title "Deploy" --trigger "manual" --category "deploy" --steps \'[{"step": "Build"}, {"step": "Publicar"}]\'',
        "related": ["vault_runbook_log", "vault_incident_save"],
    },
    "vault_runbook_log": {
        "name": "vault_runbook_log",
        "script": "vault_runbook_log.py",
        "group": "Runbooks",
        "purpose": "Registra ejecución de runbook.",
        "params": {
        },
        "guards": [],
        "side_effects": ["Actualiza log del runbook"],
        "example": 'python vault_runbook_log.py --path "08_Runbooks/deploy.md" --outcome "success"',
        "related": ["vault_runbook_save", "vault_audit"],
    },
    "vault_incident_save": {
        "name": "vault_incident_save",
        "script": "vault_incident_save.py",
        "group": "Producción/SRE",
        "purpose": "Registra incidente de producción.",
        "params": {
            "title": {
                "type": "string",
                "required": True,
                "description": "Título del incidente",
                "validators": ["not_empty"],
            },
            "severity": {
                "type": "string",
                "required": True,
                "description": "Severidad: SEV1, SEV2, SEV3, SEV4",
                "validators": ["enum:SEV1,SEV2,SEV3,SEV4"],
            },
            "timeline": {
                "type": "string",
                "required": False,
                "description": "Timeline del incidente",
                "validators": [],
            },
            "action_items": {
                "type": "string",
                "required": False,
                "description": "Action items en JSON",
                "validators": ["valid_json"],
            },
        },
        "guards": [],
        "side_effects": ["Crea nota en 02_Observability/incidents/"],
        "example": 'python vault_incident_save.py --project "mi-api" --title "API caida" --severity "P1"',
        "related": ["vault_slo_save", "vault_runbook_save"],
    },
    "vault_slo_save": {
        "name": "vault_slo_save",
        "script": "vault_slo_save.py",
        "group": "Producción/SRE",
        "purpose": "Guarda SLO (Service Level Objective).",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
            "target": {
                "type": "string",
                "required": True,
                "description": "Target: 99.9%, 99.99%, etc",
                "validators": [],
            },
            "description": {
                "type": "string",
                "required": True,
                "description": "Descripción del SLO",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Crea nota en 02_Observability/slos/"],
        "example": 'python vault_slo_save.py --project "mi-api" --service "api" --slo_type "availability" --target "99.9"',
        "related": ["vault_incident_save", "vault_audit"],
    },
    "vault_release_save": {
        "name": "vault_release_save",
        "script": "vault_release_save.py",
        "group": "Release",
        "purpose": "Guarda información de release.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
            "version": {
                "type": "string",
                "required": True,
                "description": "Versión (semver)",
                "validators": [],
            },
            "changes": {
                "type": "string",
                "required": False,
                "description": "Cambios en JSON",
                "validators": ["valid_json"],
            },
        },
        "guards": [],
        "side_effects": ["Crea nota en 01_Projects/{project}/releases/"],
        "example": 'python vault_release_save.py --project "mi-api" --version "1.2.0" --type "minor"',
        "related": ["vault_change_log", "vault_incident_save"],
    },
    "vault_risk_save": {
        "name": "vault_risk_save",
        "script": "vault_risk_save.py",
        "group": "Riesgos/Calidad",
        "purpose": "Registra riesgo del proyecto.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
            "title": {
                "type": "string",
                "required": True,
                "description": "Título del riesgo",
                "validators": ["not_empty"],
            },
            # Hasta v40.35 declaraba `low..critical` como texto obligatorio: la
            # CLI pide un entero 1-5 con 3 por defecto, y el esquema publicado
            # anunciaba cuatro valores que ella rechaza.
            "impact": {
                "type": "integer",
                "required": False,
                "description": "Impacto en la matriz de riesgo, 1-5 (por defecto 3)",
                "validators": ["enum:1,2,3,4,5"],
            },
        },
        "guards": [],
        "side_effects": ["Crea nota en 01_Projects/{project}/risks/"],
        "example": 'python vault_risk_save.py --project "mi-api" --title "Caida de la base" --likelihood "3" --impact "4"',
        "related": ["vault_ncr_save", "vault_privacy_save"],
    },
    "vault_privacy_save": {
        "name": "vault_privacy_save",
        "script": "vault_privacy_save.py",
        "group": "Riesgos/Calidad",
        "purpose": "Gestiona privacidad de datos.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
            "third_parties": {
                "type": "string",
                "required": False,
                "description": "Terceros en JSON",
                "validators": ["valid_json"],
            },
        },
        "guards": [],
        "side_effects": ["Crea nota en 02_Observability/privacy/"],
        "example": 'python vault_privacy_save.py --project "mi-api" --title "Emails de usuario" --purpose "Notificaciones" --legal_basis "consent"',
        "related": ["vault_risk_save", "vault_security_scan"],
    },
    "vault_ncr_save": {
        "name": "vault_ncr_save",
        "script": "vault_ncr_save.py",
        "group": "Riesgos/Calidad",
        "purpose": "Registra No Conformidad (NCR).",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
            "title": {
                "type": "string",
                "required": True,
                "description": "Título de la NCR",
                "validators": ["not_empty"],
            },
            "description": {
                "type": "string",
                "required": True,
                "description": "Descripción",
                "validators": ["min_length:20"],
            },
            "severity": {
                "type": "string",
                "required": True,
                "description": "Severidad: minor, major, critical",
                "validators": ["enum:minor,major,critical"],
            },
            "detected_by": {
                "type": "string",
                "required": True,
                "description": "Detectado por: audit, customer, internal, automated",
                "validators": ["enum:audit,customer,internal,automated"],
            },
            "root_cause": {
                "type": "string",
                "required": False,
                "description": "Causa raíz",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Crea nota en 02_Observability/ncr/"],
        "example": 'python vault_ncr_save.py --project "mi-api" --title "Missing validation" --severity "major" --detected_by "audit"',
        "related": ["vault_risk_save", "vault_audit"],
    },
    "vault_migrate_docs": {
        "name": "vault_migrate_docs",
        "script": "vault_migrate_docs.py",
        "group": "Migración",
        "purpose": "Migra documentación entre vaults o estructuras.",
        "params": {
            "dry_run": {
                "type": "boolean",
                "required": False,
                "description": "Simular sin aplicar",
                "validators": [],
            },
        },
        "guards": ["Hacer backup antes de migrar"],
        "side_effects": ["Copia/move archivos"],
        "example": 'python vault_migrate_docs.py --source_path "./docs" --project "mi-api" --dry_run "true"',
        "related": ["vault_migrate_rollback", "vault_merge"],
    },
    "vault_migrate_rollback": {
        "name": "vault_migrate_rollback",
        "script": "vault_migrate_rollback.py",
        "group": "Migración",
        "purpose": "Revierte migración anterior.",
        "params": {
        },
        "guards": ["Confirmar antes de revertir"],
        "side_effects": ["Revierte archivos migrados"],
        "example": 'python vault_migrate_rollback.py --report_path "19_Audits/migrations/2026-06-24-001.json"\npython vault_migrate_rollback.py --report_path "19_Audits/migrations/2026-06-24-001.json" --confirm true',
        "related": ["vault_migrate_docs", "vault_backup"],
    },
    "vault_bibliography_save": {
        "name": "vault_bibliography_save",
        "script": "vault_bibliography_save.py",
        "group": "Bibliografía",
        "purpose": "Guarda referencia bibliográfica.",
        "params": {
            "title": {
                "type": "string",
                "required": True,
                "description": "Título",
                "validators": ["not_empty"],
            },
            "url": {
                "type": "string",
                "required": False,
                "description": "URL",
                "validators": [],
            },
            "tags": {
                "type": "string",
                "required": False,
                "description": "Tags separados por espacio",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Crea nota en 07_Knowledge/bibliography/"],
        "example": 'python vault_bibliography_save.py --title "Clean Code" --url "https://example.com/clean-code" --summary "Guia de estilo de codigo" --source_type "book"',
        "related": ["vault_knowledge_save", "vault_search"],
    },
    "vault_graph_merge": {
        "name": "vault_graph_merge",
        "script": "vault_graph_merge.py",
        "group": "Salud del Vault",
        "purpose": "Unifica wikilinks + entity relations + code relations en graph-enriched.json con predicados semánticos.",
        "params": {
        },
        "guards": [],
        "side_effects": [
            "Genera 99_Index/graph-enriched.json",
            "Detecta AP-31 (untyped graph), AP-34 (orphan typed relations), AP-35 (relationship silos)",
        ],
        "example": "python vault_graph_merge.py",
        "related": ["vault_graph", "vault_graph_inspect", "vault_impact"],
    },
    "vault_graph_inspect": {
        "name": "vault_graph_inspect",
        "script": "vault_graph_inspect.py",
        "group": "Salud del Vault",
        "purpose": "Analiza el grafo del vault: broken links, orphans, duplicates, syntax errors, hubs.",
        "params": {},
        "guards": [],
        "side_effects": [],
        "example": "python vault_graph_inspect.py",
        "related": ["vault_graph", "vault_graph_merge", "vault_graph_fix"],
    },
    "vault_graph_fix": {
        "name": "vault_graph_fix",
        "script": "vault_graph_fix.py",
        "group": "Corrección Automática",
        "purpose": "Auto-fix de broken wiki-links (stem match, fuzzy, brackets, path-anchored, stubs, wizard).",
        "params": {
            "threshold": {
                "type": "string",
                "required": False,
                "description": "Fuzzy match threshold (default: 0.7)",
                "validators": [],
            },
            "auto_apply_partial": {
                "type": "string",
                "required": False,
                "description": "Auto-fix partial matches above this threshold",
                "validators": [],
            },
            "apply": {
                "type": "string",
                "required": False,
                "description": "Apply fixes (default: dry-run)",
                "validators": [],
            },
            "only": {
                "type": "string",
                "required": False,
                "description": "Only run: brackets, path_anchored",
                "validators": ["enum:brackets,path_anchored"],
            },
        },
        "guards": ["Hacer backup antes de aplicar fixes"],
        "side_effects": ["Modifica wikilinks en notas", "Crea stubs si es necesario"],
        "example": 'python vault_graph_fix.py --apply --threshold 0.7\npython vault_graph_fix.py --only brackets',
        "related": ["vault_graph", "vault_graph_inspect", "vault_fix_brackets"],
    },
    "vault_history_compact": {
        "name": "vault_history_compact",
        "script": "vault_history_compact.py",
        "group": "Versionado",
        "purpose": "Rota versiones en .history/: mantiene N mas recientes, borra el resto.",
        "params": {
            "keep": {
                "type": "integer",
                "required": False,
                "description": "Numero de versiones a mantener (default: 10)",
                "validators": ["min:1"],
            },
            "note": {
                "type": "string",
                "required": False,
                "description": "Solo procesar esta nota",
                "validators": [],
            },
            "apply": {
                "type": "boolean",
                "required": False,
                "description": "Aplicar el pruning (sin esto solo dry-run)",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Borra archivos de .history/"],
        "example": "python vault_history_compact.py --apply\npython vault_history_compact.py --apply --keep 5",
        "related": ["vault_undo", "vault_write"],
    },
    # Las dos únicas tools sin script Python: están implementadas nativas en
    # mcp/nodejs/vault-mcp-server.mjs. `script: ""` sola no dice eso — los guards
    # que iteran el catálogo las saltaban en silencio creyéndolas inexistentes.
    # `runtime` lo declara, y test_source_hygiene comprueba que el .mjs las tiene.
    "vault_backup_base64": {
        "name": "vault_backup_base64",
        "script": "",
        "runtime": "node",
        "group": "Backups",
        "purpose": "Crea backup comprimido base64 del vault completo. Antes de cualquier migración o modificación masiva.",
        "params": {
            "label": {
                "type": "string",
                "required": False,
                "description": "Etiqueta del backup (default: backup-timestamp)",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Genera archivo .b64zip.json en vault-backups/"],
        "example": "node vault-mcp-server.mjs --tool vault_backup_base64",
        "related": ["vault_restore_base64", "vault_backup"],
    },
    "vault_restore_base64": {
        "name": "vault_restore_base64",
        "script": "",
        "runtime": "node",
        "group": "Backups",
        "purpose": "Restaura vault desde backup base64. Requiere --confirm true. Restaura a directorio nuevo sin tocar el original.",
        "params": {
            "path": {
                "type": "string",
                "required": True,
                "description": "Ruta al archivo .b64zip.json",
                "validators": ["file_exists"],
            },
            "confirm": {
                "type": "string",
                "required": False,
                "description": "Confirmar restauración (debe ser 'true')",
                "validators": [],
            },
        },
        "guards": ["Confirmación explícita requerida"],
        "side_effects": ["Restaura vault a nuevo directorio"],
        "example": 'node vault-mcp-server.mjs --tool vault_restore_base64 --path "backups/vault.b64zip.json" --confirm true',
        "related": ["vault_backup_base64", "vault_restore"],
    },
    # ── Memoria de contexto ──────────────────────────────────────────────────
    # Eje consulta → contexto: recuperar y empaquetar lo que hace falta para
    # responder. Complementa el eje escritura → gobernanza del resto del
    # catálogo. Sin base de datos ni embeddings: reglas léxicas y el grafo.
    "vault_preferences": {
        "name": "vault_preferences",
        "script": "vault_preferences.py",
        "group": "Memoria de Contexto",
        "purpose": "Preferencias del usuario como contexto estable: cómo quiere trabajar, qué no debe tocarse. Se revocan, no se borran.",
        "params": {
            "set": {"type": "bool", "required": False,
                    "description": "Registra o actualiza una preferencia", "validators": []},
            "list": {"type": "bool", "required": False,
                     "description": "Lista las preferencias registradas", "validators": []},
            "context": {"type": "bool", "required": False,
                        "description": "Bloque markdown listo para inyectar", "validators": []},
            "revoke": {"type": "string", "required": False,
                       "description": "Ruta de la preferencia a revocar", "validators": ["within_vault"]},
            "category": {"type": "string", "required": False,
                         "description": "workflow | style | tooling | constraints | domain", "validators": []},
            "title": {"type": "string", "required": False,
                      "description": "Título de la preferencia", "validators": []},
            "statement": {"type": "string", "required": False,
                          "description": "Enunciado: qué debe hacer el agente", "validators": []},
            "strength": {"type": "string", "required": False,
                         "description": "must | should | may (default: should)", "validators": []},
            "reason": {"type": "string", "required": False,
                       "description": "Motivo de la revocación (obligatorio con --revoke)", "validators": []},
            "agent": {"type": "string", "required": False,
                      "description": "Agente que ejecuta (AP-16)", "validators": []},
        },
        "guards": ["AP-16: requiere agent o VAULT_AGENT",
                   "Categoría validada contra vault_registry",
                   "Revocar exige motivo y no borra la nota"],
        "side_effects": ["Crea/actualiza nota en 17_Preferences/{category}/",
                         "Actualiza índice de 17_Preferences"],
        "example": 'python vault_preferences.py --set --category constraints --title "No mover tools" --statement "No propagar scripts a otros repos" --strength must\npython vault_preferences.py --context',
        "related": ["vault_context_pack", "vault_write"],
    },
    "vault_model_profile": {
        "name": "vault_model_profile",
        "script": "vault_model_profile.py",
        "group": "Memoria de Contexto",
        "purpose": "Perfil de modelo LLM para contexto adaptativo. Auto-detecta el modelo desde VAULT_MODEL_PROFILE y expone budget correcto para vault_context_pack.",
        "params": {
            "list": {"type": "bool", "required": False,
                     "description": "Lista perfiles disponibles", "validators": []},
            "active": {"type": "bool", "required": False,
                       "description": "Devuelve el perfil activo", "validators": []},
            "set": {"type": "string", "required": False,
                    "description": "Activa el perfil dado (id)", "validators": []},
            "auto": {"type": "string", "required": False,
                     "description": "Auto-detecta desde nombre del cliente MCP", "validators": []},
            "budget": {"type": "bool", "required": False,
                       "description": "Solo imprime el budget (consumo interno)", "validators": []},
            "window": {"type": "bool", "required": False,
                       "description": "Solo imprime context_window", "validators": []},
        },
        "guards": [],
        "side_effects": ["Actualiza 17_Preferences/model_profile.active"],
        "example": 'python vault_model_profile.py --list\npython vault_model_profile.py --set claude\npython vault_model_profile.py --auto "claude-desktop"',
        "related": ["vault_context_pack", "vault_preferences"],
    },
    "vault_bug_save": {
        "name": "vault_bug_save",
        "script": "vault_bug_save.py",
        "group": "Defectos y Cuarentena",
        "purpose": "Ciclo del defecto en 18_Bugs/: síntoma → causa raíz → corrección verificada, con aristas de causalidad tipadas.",
        "params": {
            "project": {"type": "string", "required": True,
                        "description": "Slug del proyecto", "validators": []},
            "title": {"type": "string", "required": True,
                      "description": "Título breve del defecto", "validators": []},
            "symptom": {"type": "string", "required": True,
                        "description": "Qué se observa que falla (obligatorio: sin síntoma no es reproducible)", "validators": []},
            "phase": {"type": "string", "required": False,
                      "description": "open | root-cause | fixed — determina la subcarpeta", "validators": []},
            "status": {"type": "string", "required": False,
                       "description": "open | confirmed | in_fix | fixed | wont_fix | duplicate", "validators": []},
            "severity": {"type": "string", "required": False,
                         "description": "critical | high | medium | low", "validators": []},
            "repro": {"type": "string", "required": False,
                      "description": "Pasos de reproducción", "validators": []},
            "root_cause": {"type": "string", "required": False,
                           "description": "Causa raíz identificada", "validators": []},
            "fix": {"type": "string", "required": False,
                    "description": "Corrección aplicada", "validators": []},
            "causes": {"type": "array", "required": False,
                       "description": "Notas que este defecto causa (arista tipada)", "validators": []},
            "caused_by": {"type": "array", "required": False,
                          "description": "Notas que lo causan (arista tipada)", "validators": []},
            "verified_by": {"type": "string", "required": False,
                            "description": "Test que verifica la corrección", "validators": []},
            "agent": {"type": "string", "required": False,
                      "description": "Agente que registra (AP-16)", "validators": []},
        },
        "guards": ["AP-16: requiere agent o VAULT_AGENT",
                   "AP-38: status canónico + bug_state de dominio",
                   "Síntoma obligatorio y no vacío",
                   "La fase determina la subcarpeta: estado y ubicación no pueden divergir"],
        "side_effects": ["Crea nota en 18_Bugs/{open|root-causes|fixed}/",
                         "Actualiza 18_Bugs/.bugs-index.json"],
        "example": 'python vault_bug_save.py --project mi-api --title "Token numérico coercionado" --symptom "El literal 0.5 llega al CSS como 0.5px" --severity high --agent claude',
        "related": ["vault_log_error", "vault_test_save", "vault_ncr_save"],
    },
    "vault_quarantine": {
        "name": "vault_quarantine",
        "script": "vault_quarantine.py",
        "group": "Defectos y Cuarentena",
        "purpose": "Retiene notas sin destino seguro en 20_Quarantine/ conservando su origen. La alternativa a retener no es limpiar: es borrar.",
        "params": {
            "add": {"type": "string", "required": False,
                    "description": "Ruta de la nota a retener", "validators": ["within_vault"]},
            "restore": {"type": "string", "required": False,
                        "description": "Ruta en cuarentena a devolver a su origen", "validators": ["within_vault"]},
            "list": {"type": "bool", "required": False,
                     "description": "Lista lo retenido y sin restaurar", "validators": []},
            "reason": {"type": "string", "required": False,
                       "description": "Por qué se retiene (obligatorio con --add)", "validators": []},
            "category": {"type": "string", "required": False,
                         "description": "unclassified | suspicious | duplicates", "validators": []},
            "agent": {"type": "string", "required": False,
                      "description": "Agente que actúa (AP-16)", "validators": []},
        },
        "guards": ["AP-16: requiere agent o VAULT_AGENT",
                   "Razón obligatoria y no vacía",
                   "La nota se mueve, no se copia",
                   "Restaurar sobre un origen ocupado falla en vez de sobrescribir"],
        "side_effects": ["Mueve la nota a 20_Quarantine/{category}/",
                         "Actualiza 20_Quarantine/.quarantine-ledger.json (append-only)"],
        "example": 'python vault_quarantine.py --add "07_Knowledge/rara.md" --reason "Sin frontmatter y origen desconocido" --agent claude\npython vault_quarantine.py --list',
        "related": ["vault_merge", "vault_security_scan", "vault_move"],
    },
    "vault_arquitectura_en": {
        "name": "vault_arquitectura_en",
        "script": "vault_arquitectura_en.py",
        "group": "Memoria de Contexto",
        "purpose": "La arquitectura de un proyecto vista en una fecha o versión, o lo que cambió entre dos: qué notas regían, su texto entonces (desde .history/) y sus files:. Solo lectura.",
        "params": {
            "fecha": {
                "type": "string",
                "required": False,
                "description": "YYYY-MM-DD: qué arquitectura regía al final de ese día",
                "validators": [],
            },
            "version": {
                "type": "string",
                "required": False,
                "description": "vX.Y[.Z]: qué regía en esa versión (fecha de su nota de release, o vigente_desde:)",
                "validators": [],
            },
            "desde": {
                "type": "string",
                "required": False,
                "description": "Inicio del rango: fecha o versión",
                "validators": [],
            },
            "hasta": {
                "type": "string",
                "required": False,
                "description": "Fin del rango: fecha o versión",
                "validators": [],
            },
            "project": {
                "type": "string",
                "required": False,
                "description": "Limita a las notas y releases de ese proyecto",
                "validators": [],
            },
        },
        "guards": ["Solo lectura: no escribe nada en el vault",
                   "La fecha de una versión guardada sale de su nombre en .history/, nunca del mtime",
                   "Lo indecidible sale en indeterminadas: no se adivina"],
        "side_effects": [],
        "example": "python vault_arquitectura_en.py --fecha 2026-05-03\npython vault_arquitectura_en.py --desde v1.0 --hasta v1.5 --project demo",
        "related": ["vault_undo", "vault_supersede", "vault_release_save", "vault_context_pack"],
    },
    "vault_subgraph": {
        "name": "vault_subgraph",
        "script": "vault_subgraph.py",
        "group": "Memoria de Contexto",
        "purpose": "Subgrafo de K semillas y N saltos sobre el grafo del vault, con peso por predicado y decaimiento por salto.",
        "params": {
            "seeds": {"type": "array", "required": True,
                      "description": "Notas de partida (ruta, ruta sin .md o título)", "validators": []},
            "hops": {"type": "int", "required": False,
                     "description": "Saltos de expansión (default: 2)", "validators": ["min:0", "max:6"]},
            "direction": {"type": "string", "required": False,
                          "description": "in | out | both (default: both)", "validators": []},
            "max_nodes": {"type": "int", "required": False,
                          "description": "Tope de nodos (default: 50)", "validators": ["min:1"]},
            "predicate": {"type": "array", "required": False,
                          "description": "Filtra por tipo de relación", "validators": []},
            "section": {"type": "string", "required": False,
                        "description": "Limita a una sección", "validators": []},
            "format": {"type": "string", "required": False,
                       "description": "json | mermaid (default: json)", "validators": []},
        },
        "guards": ["Requiere 99_Index/graph.json o graph-enriched.json"],
        "side_effects": [],
        "example": 'python vault_subgraph.py --seeds "03_Decisions/adr-001.md" --hops 2\npython vault_subgraph.py --seeds mcp-protocol --format mermaid',
        "related": ["vault_impact", "vault_graph", "vault_context_pack"],
    },
    "vault_query_parse": {
        "name": "vault_query_parse",
        "script": "vault_query_parse.py",
        "execution_module": "vault_toolkit.operations.vault_query_parse",
        "group": "Memoria de Contexto",
        "purpose": "Lenguaje natural → consulta estructurada (términos, secciones, tags, semillas, ventana temporal, intención) y plan de tools. Determinista, sin modelo.",
        "params": {
            "query": {"type": "string", "required": True,
                      "description": "Pregunta en lenguaje natural", "validators": []},
            "explain": {"type": "bool", "required": False,
                        "description": "Incluye la evidencia de cada campo inferido", "validators": []},
            "plan_only": {"type": "bool", "required": False,
                          "description": "Emite solo el plan de tools", "validators": []},
        },
        "guards": [],
        "side_effects": [],
        "example": 'python vault_query_parse.py "que decidimos la semana pasada sobre MCP" --explain',
        "related": ["vault_context_pack", "vault_search", "vault_subgraph"],
    },
    "vault_context_pack": {
        "name": "vault_context_pack",
        "script": "vault_context_pack.py",
        "group": "Memoria de Contexto",
        "purpose": "Pregunta → contexto empaquetado bajo presupuesto de tokens: parse, búsqueda léxica, expansión por grafo, rerank y Top-K.",
        "params": {
            "query": {"type": "string", "required": True,
                      "description": "Pregunta en lenguaje natural", "validators": []},
            "budget": {"type": "int", "required": False,
                       "description": "Presupuesto en tokens (default: 4000)", "validators": ["min:1"]},
            "top_k": {"type": "int", "required": False,
                      "description": "Máximo de notas candidatas (default: 12)", "validators": ["min:1"]},
            "excerpt_tokens": {"type": "int", "required": False,
                               "description": "Tope por nota (default: 350)", "validators": ["min:1"]},
            "min_score": {"type": "float", "required": False,
                          "description": "Descarta candidatas por debajo de este score", "validators": []},
            "no_preferences": {"type": "bool", "required": False,
                               "description": "No inyecta las preferencias 'must'", "validators": []},
            "format": {"type": "string", "required": False,
                       "description": "json | markdown (default: json)", "validators": []},
        },
        "guards": ["El presupuesto recorta notas enteras: nunca entrega media nota como entera",
                   "Requiere 99_Index/search-index.json y graph.json"],
        "side_effects": [],
        "example": 'python vault_context_pack.py "que decidimos sobre el transporte MCP" --budget 2000',
        "related": ["vault_query_parse", "vault_subgraph", "vault_search", "vault_preferences"],
    },
    "vault_ingest": {
        "name": "vault_ingest",
        "script": "vault_ingest.py",
        "group": "Memoria de Contexto",
        "purpose": "Ingesta gobernada de conversaciones, ficheros y URLs con extracción de entidades. Dry-run por defecto; pre-vuelo anti-poison no desactivable.",
        "params": {
            "file": {"type": "string", "required": False,
                     "description": "Fichero de origen", "validators": ["file_exists"]},
            "text": {"type": "string", "required": False,
                     "description": "Texto literal", "validators": []},
            "stdin": {"type": "bool", "required": False,
                      "description": "Lee de stdin", "validators": []},
            "url": {"type": "string", "required": False,
                    "description": "URL http(s); requiere allow_network", "validators": []},
            "section": {"type": "string", "required": True,
                        "description": "Sección destino (no admite 00_System, 99_Index ni 17_Preferences)", "validators": []},
            "subfolder": {"type": "string", "required": False,
                          "description": "Subcarpeta dentro de la sección", "validators": []},
            "commit": {"type": "bool", "required": False,
                       "description": "Escribe de verdad (por defecto es dry-run)", "validators": []},
            "max_notes": {"type": "int", "required": False,
                          "description": "Tope de notas derivadas (default: 20)", "validators": ["min:1"]},
            "allow_network": {"type": "bool", "required": False,
                              "description": "Permite descargar la URL", "validators": []},
            "agent": {"type": "string", "required": False,
                      "description": "Agente que ejecuta (AP-16)", "validators": []},
        },
        "guards": ["Pre-vuelo anti-poison obligatorio (cli.safety)",
                   "AP-16: requiere agent o VAULT_AGENT",
                   "Dry-run por defecto: escribir exige commit",
                   "Nunca sobrescribe una nota existente",
                   "Red apagada salvo allow_network explícito"],
        "side_effects": ["Con --commit: crea notas en la sección destino con status draft",
                         "Actualiza el índice de la sección"],
        "example": 'python vault_ingest.py --file notas.md --section 07_Knowledge\npython vault_ingest.py --file notas.md --section 07_Knowledge --commit',
        "related": ["vault_write", "vault_knowledge_save", "vault_context_pack"],
    },
}

# ──── end TOOLS_CATALOG ────

#: Tools que arrancan un servicio y no vuelven hasta que las matan
#: (`serve_forever`). Siguen catalogadas y se lanzan como proceso propio desde la
#: CLI; por MCP cada llamada acababa en TOOL_TIMEOUT, así que no se exponen
#: (AP-44: `tools/list` no anuncia lo que el consumidor no puede completar).
SERVICIOS_DE_PROCESO_LARGO: frozenset = frozenset({"vault_token_service"})

#: Tools sin script Python: implementadas de forma nativa en el servidor MCP.
#: **Fuente única** del criterio — `cli/registry.py` lo importa de aquí y el
#: `.mjs` lo lee de `tools-catalog.json`. No son fragmentos ausentes: son
#: fragmentos de otro runtime, y distinguirlas evita reportar un AP-04 falso.
NATIVE_JS_TOOLS: frozenset = frozenset({
    "vault_backup_base64",
    "vault_restore_base64",
})

GROUPS: Dict[str, List[str]] = {
    "Core": [
        "vault_write",
        "vault_read",
        "vault_search",
        "vault_list",
        "vault_append",
        "vault_diff",
        "vault_merge",
        "vault_move",
    ],
    "Observabilidad": ["vault_log_error"],
    "Salud del Vault": ["vault_fuente_unica", "vault_audit", "vault_gobernanza", "vault_validate", "vault_graph", "vault_graph_merge", "vault_graph_inspect"],
    "Patrones": ["vault_pattern_save", "vault_pattern_list"],
    "Diagramas": [
        "vault_diagram_save",
        "vault_relation_add",
        "vault_mermaid_check",
        "vault_diagram_export",
    ],
    "Conocimiento": ["vault_knowledge_save", "vault_knowledge_get"],
    "Runbooks": ["vault_runbook_save", "vault_runbook_log"],
    "Infraestructura": [
        "vault_infra_save",
        "vault_infra_map",
        "vault_env_save",
        "vault_env_matrix",
    ],
    "Migración": ["vault_migrate_docs", "vault_migrate_rollback"],
    "Línea de Tiempo": ["vault_timeline"],
    "Vista del Proyecto": ["vault_project_status", "vault_project_overview", "vault_project"],
    "Código": [
        "vault_code_module",
        "vault_code_relation",
        "vault_code_map",
        "vault_code_query",
        "vault_code_sync",
        # vault_code_tag NO se lista aquí: su `group` en TOOLS_CATALOG es
        # "Normas y Etiquetas" y ya está en el grupo "Normas". Estaba en ambos,
        # y una tool en dos grupos se cuenta dos veces en cualquier recorrido.
        # La tool no se retira de nada — solo deja de estar duplicada en el índice.
    ],
    # vault_backup_base64 / vault_restore_base64 son JS-native (script: ""), y por
    # eso quedaron fuera de esta lista durante varias versiones: declaraban
    # "group": "Backups" en TOOLS_CATALOG pero GROUPS no las contenía, así que
    # cualquier recorrido por grupos las omitía en silencio. No tener entry point
    # Python no las saca del catálogo.
    "Backups": [
        "vault_backup",
        "vault_backup_list",
        "vault_restore",
        "vault_backup_base64",
        "vault_restore_base64",
    ],
    "Seguridad": ["vault_security_scan"],
    "Índices": ["vault_section_index", "vault_master_index", "vault_reindex"],
    "Bibliografía": ["vault_bibliography_save"],
    "Drift Detection": ["vault_drift_detect"],
    "Flujos": ["vault_flow_save"],
    "Requerimientos": ["vault_requirement_save"],
    "Tests": ["vault_test_save", "vault_qa_save", "vault_quality_dashboard"],
    "IA Governance": ["vault_ai_decision"],
    "Change Log": ["vault_change_log", "vault_delete"],
    "Data Quality": ["vault_quality_check", "vault_fundamentals"],
    "Propagación": ["vault_impact", "vault_propagate"],
    "Tokens": ["vault_tokens", "vault_token_counter", "vault_token_service"],
    "Session Delta y Tags": ["vault_delta", "vault_tags"],
    "Normas": [
        "vault_norms",
        "vault_arch",
        "vault_blame_audit",
        "vault_changelog_check",
        "vault_error_contract",
        "vault_foreign_check",
        "vault_gate",
        "vault_code_tag",
        "vault_doc_counts",
        "vault_doc_sync",
        "vault_doc_staleness",
        "vault_noop_audit",
        "vault_smoke",
        "vault_toolkit_audit",
        "vault_voice",
        "vault_servicio",
        "vault_blueprint",
        "vault_norms_coherence",
        "vault_criterios",
        "vault_ciclos",
        "vault_kernel",
        "vault_excepcion_declarada",
        "vault_recursos",
        "vault_produccion",
        "vault_esquema",
        "vault_metricas",
        "vault_fix_all",
    ],
    "Producción/SRE": ["vault_incident_save", "vault_slo_save"],
    "Release": ["vault_release_save"],
    "Riesgos/Calidad": ["vault_risk_save", "vault_privacy_save", "vault_ncr_save"],
    "Bootstrap": ["vault_init", "vault_onboard"],
    "Corrección Automática": ["vault_fix_brackets", "vault_graph_fix", "vault_frontmatter_heal",
                              "vault_frontmatter_completar", "vault_supersede"],
    "Versionado": ["vault_standard_upgrade", "vault_undo", "vault_history_compact"],
    "Gestión de Carpetas": ["vault_folder_registry", "vault_section"],
    "Memoria de Contexto": [
        "vault_preferences",
        "vault_model_profile",
        "vault_query_parse",
        "vault_subgraph",
        "vault_context_pack",
        "vault_ingest",
        "vault_arquitectura_en",
    ],
    # Grupo 36 (v39) — el ciclo del defecto y la retención sin borrado. Ambas
    # secciones salen de medir el parque real, no de un diseño a priori.
    "Defectos y Cuarentena": [
        "vault_bug_save",
        "vault_quarantine",
    ],
    # Grupo 37 (v39.4) — las capacidades que un agente descubre e invoca por
    # nombre. Existían desde v36 en `agent/skills/` y en `docs/SKILLS.md`,
    # pero fuera del catálogo y fuera del tool-spec: AP-42 —tool publicada sin
    # contrato ejecutable— sobre la puerta de entrada de los agentes.
    "Skills": [
        "vault_sdd_init",
        "vault_sanacion",
    ],
}


VALIDATORS: Dict[str, callable] = {}


def get_tool(name: str) -> Optional[Dict[str, Any]]:
    """Retorna la definición de una tool por nombre."""
    return TOOLS_CATALOG.get(name)


@lru_cache(maxsize=1)
def distribution_metadata():
    """Proyección de distribución de los registros canónicos.

    El catálogo ya es el puerto que consume la CLI. Exponer aquí esta lectura
    evita que el adaptador de transporte abra un segundo cruce hacia el registro
    de naturalezas; la lógica de clasificación sigue viviendo en el módulo
    estable ``vault.meta_toolkit.distribucion``.
    """
    from vault.meta_toolkit.distribucion import derivar_distribucion
    from vault.meta_toolkit.naturalezas import NATURALEZAS

    return derivar_distribucion(TOOLS_CATALOG, NATURALEZAS)


def get_group_tools(group: str) -> List[Dict[str, Any]]:
    """Retorna todas las tools de un grupo."""
    tool_names = GROUPS.get(group, [])
    return [TOOLS_CATALOG.get(name) for name in tool_names if name in TOOLS_CATALOG]


def get_all_groups() -> List[str]:
    """Retorna lista de todos los grupos."""
    return list(GROUPS.keys())


def find_tools_by_purpose(query: str) -> List[Dict[str, Any]]:
    """Busca tools por propósito o palabra clave."""
    query = query.lower()
    results = []
    for name, tool in TOOLS_CATALOG.items():
        if query in tool["purpose"].lower() or query in name.lower():
            results.append(tool)
    return results


def get_related_tools(name: str) -> List[Dict[str, Any]]:
    """Retorna tools relacionadas."""
    tool = TOOLS_CATALOG.get(name)
    if not tool:
        return []
    related_names = tool.get("related", [])
    return [TOOLS_CATALOG.get(n) for n in related_names if n in TOOLS_CATALOG]


# ── Conciliación con argparse (AP-40) ────────────────────────────────────────
#
# El contrato de argumentos de una tool no lo decide el catálogo: lo decide su
# `argparse`. El servidor MCP compone `--<param>` literalmente, así que un param
# que la CLI no declara produce `unrecognized arguments` — la tool aparece en
# `tools/list`, se puede invocar, y falla siempre.
#
# Medido antes de este cambio: **43 de las 86 tools** publicaban al menos un
# param inexistente (`vault_impact` ofrecía `path`/`depth` cuando la CLI tiene
# `--changed`/`--max-hops`; `vault_test_save` ofrecía `name`/`type`/`coverage`
# cuando pide `--title`/`--test_type`). La mitad de la superficie MCP era
# inaccesible y ningún guard lo veía, porque el `--check` solo comparaba el JSON
# contra el Python: dos copias de la misma equivocación coinciden perfectamente.
#
# Por eso los params se derivan del script y la descripción escrita a mano se
# conserva cuando el nombre coincide: el catálogo aporta la prosa, argparse
# aporta la verdad.


@lru_cache(maxsize=None)
def posicionales_obligatorios(script: str) -> List[str]:
    """Posicionales sin `nargs="?"` de un script.

    Un posicional **no se puede publicar** en el `inputSchema`: MCP invoca con
    flags. Así que un posicional obligatorio no es un detalle de estilo — es
    una entrada que ningún consumidor MCP puede rellenar, y la tool queda
    inalcanzable. `check_params` solo miraba `publicado ⊆ argparse`, que es la
    dirección que no ve este caso: no sobraba nada, faltaba todo.
    """
    import ast

    ruta = Path(__file__).resolve().parent / script
    if not script or not ruta.is_file():
        return []
    try:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []

    fuera: List[str] = []
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.Call) and getattr(nodo.func, "attr", "") == "add_argument"):
            continue
        nombres = [a.value for a in nodo.args
                   if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        if not nombres or nombres[0].startswith("-"):
            continue
        kw = {k.arg: k.value for k in nodo.keywords}
        nargs = kw.get("nargs")
        if isinstance(nargs, ast.Constant) and nargs.value in ("?", "*"):
            continue
        fuera.append(nombres[0])
    return sorted(set(fuera))


#: Conversor de argparse → tipo JSON Schema. Uno que no está aquí (`str`, una
#: función propia como `proyecto_registrado`) se publica como `string`, que es
#: lo que argparse recibe antes de convertirlo.
_TIPO_DE_CONVERSOR = {"int": "integer", "float": "number", "json.loads": "object"}


#: Obligatorios que argparse no conoce porque los exige la función: la CLI
#: acepta la llamada y es el código quien la rechaza. Cada alternativa es un
#: conjunto de params que, juntos, bastan. `test_mcp_requisitos_alternativos`
#: ejecuta la CLI sin ninguna alternativa y comprueba que la rechaza: una
#: entrada que la CLI no exige no puede quedarse aquí.
REQUISITOS_EN_CODIGO: Dict[str, List[List[str]]] = {
    "vault_write": [["title", "content"], ["scan-path"]],
    "vault_knowledge_save": [["title", "content"], ["scan-path"]],
}


def grupos_obligatorios(script: str) -> List[List[List[str]]]:
    """Grupos `add_mutually_exclusive_group(required=True)` de un script.

    Hasta v40.35 el esquema no los publicaba: `vault_preferences`,
    `vault_project`, `vault_undo`… salían sin un solo obligatorio y la llamada
    vacía llegaba a argparse. Cada grupo es una restricción cuyas alternativas
    son sus flags, uno a uno.
    """
    import ast

    ruta = Path(__file__).resolve().parent / script
    if not script or not ruta.is_file():
        return []
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    grupos: Dict[str, List[List[str]]] = {}
    for nodo in ast.walk(arbol):
        if (isinstance(nodo, ast.Assign) and isinstance(nodo.value, ast.Call)
                and getattr(nodo.value.func, "attr", "") == "add_mutually_exclusive_group"
                and any(k.arg == "required" and isinstance(k.value, ast.Constant)
                        and k.value.value is True for k in nodo.value.keywords)):
            for destino in nodo.targets:
                if isinstance(destino, ast.Name):
                    grupos[destino.id] = []
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.Call) and getattr(nodo.func, "attr", "") == "add_argument"
                and isinstance(nodo.func.value, ast.Name) and nodo.func.value.id in grupos):
            continue
        largos = [a.value for a in nodo.args
                  if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value.startswith("--")]
        if largos:
            grupos[nodo.func.value.id].append([largos[0][2:]])
    return [alternativas for alternativas in grupos.values() if alternativas]


def alternativas_obligatorias(py_tool: Dict[str, Any]) -> List[List[List[str]]]:
    """Restricciones «al menos una de estas alternativas» de una tool.

    No van como `anyOf` dentro del `inputSchema`: la API de Claude rechaza un
    esquema de entrada con `anyOf`/`oneOf`/`allOf` en el nivel superior, así que
    publicarlo ahí dejaría la tool inservible para el cliente más común. Viajan
    como `requires_one_of` junto al esquema, el servidor las hace cumplir antes
    de lanzar el proceso, y la descripción de cada param las anuncia.
    """
    restricciones = grupos_obligatorios(py_tool.get("script") or "")
    codigo = REQUISITOS_EN_CODIGO.get(py_tool.get("name", ""))
    if codigo:
        restricciones.append(codigo)
    return restricciones


def _elecciones_del_modulo(script: str, expresion: Any) -> List[str]:
    """Valores de un `choices=` que no es una lista literal (AP-44).

    Hasta v40.35 solo se publicaban los `choices=[...]` escritos en la llamada:
    35 de 50 eran un nombre —`CATEGORIES`, `list(TYPE_FOLDERS.keys())`,
    `_opciones("severidad")`— y salían al esquema MCP sin `enum`, así que un
    cliente que validaba contra el esquema aceptaba cualquier cadena y se
    enteraba por el exit 2 de argparse. Los valores se leen con el criterio del
    consumidor: la misma expresión, evaluada en el módulo que se la da a
    argparse. Sin `except`: un script que no se importa es un fallo de la
    sincronización, no un enum vacío que la haga pasar en verde.
    """
    return [str(v) for v in _evaluar_en_el_modulo(script, expresion)]


def _evaluar_en_el_modulo(script: str, expresion: Any) -> Any:
    """Valor de una expresión de `add_argument` en el módulo que la escribe.

    Un solo sitio para los dos campos que se calculan: `choices=` y `help=`.
    """
    import ast
    import importlib

    modulo = importlib.import_module(Path(script).stem)
    return eval(compile(ast.Expression(expresion), script, "eval"), vars(modulo))


def argparse_params(script: str) -> Dict[str, Dict[str, Any]]:
    """Params reales de un script, leídos de sus `add_argument` largos.

    Las llamadas las lee `vault.meta_toolkit.flags_cli`, el extractor único
    que comparten `vault_manifest`, `vault_spec_validate`, `vault_spec_memory`
    y `vault_doc_sync` (v41.9); aquí solo se evalúa lo que no es literal.
    """
    import ast
    from vault.meta_toolkit import flags_cli

    ruta = Path(__file__).resolve().parent / script
    if not script or not ruta.is_file():
        return {}
    # Tras la deuda #12 `scripts/<tool>.py` puede ser un alias sin un solo
    # `add_argument`: leerlo publicaba un esquema vacío. Se sigue el alias con
    # `fuente_de`, el criterio del import (AP-44).
    ruta = vault_grafo_import.fuente_de(ruta.stem)
    try:
        llamadas = flags_cli.declaraciones(ruta.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return {}

    params: Dict[str, Dict[str, Any]] = {}
    for llamada in llamadas:
        largos = [n for n in llamada.nombres if n.startswith("--")]
        if not largos:
            continue  # posicional o flag corto: no se publica por MCP
        kw, _const = llamada.kw, llamada.constante
        accion, nargs = llamada.accion, _const("nargs")
        # El `type=` de argparse es el contrato real del valor: hasta v40.34 se
        # ignoraba y `limit`, `budget`, `hops`… salían como `string`, así que un
        # cliente que validaba contra el esquema mandaba `"diez"` y solo se
        # enteraba por el texto de uso de argparse, y `--meta` (`json.loads`)
        # se publicaba como texto en vez de como objeto.
        convierte = kw.get("type")
        if isinstance(convierte, ast.Name):
            convierte = convierte.id
        elif isinstance(convierte, ast.Attribute):
            convierte = ast.unparse(convierte)
        else:
            convierte = None
        escalar = _TIPO_DE_CONVERSOR.get(convierte, "string")
        items = None
        # `negable` es `BooleanOptionalAction`: hasta v41.8 su `action=` no era
        # literal, no se leía, y `--reversible` se publicaba como texto.
        if accion in ("store_true", "store_false", "negable"):
            tipo = "boolean"
        elif nargs in ("*", "+") or isinstance(nargs, int):
            tipo = "array"
            items = escalar if escalar in ("integer", "number") else "string"
        else:
            tipo = escalar

        opciones = []
        elecciones = kw.get("choices")
        if isinstance(elecciones, (ast.List, ast.Tuple)):
            # También los enteros: `--likelihood choices=[1, 2, 3, 4, 5]` se
            # descartaba por no ser texto y salía sin enum.
            opciones = [
                str(e.value) for e in elecciones.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, (str, int, float))
            ]
        elif elecciones is not None:
            opciones = _elecciones_del_modulo(script, elecciones)

        # Una ayuda calculada —`f"Tope de nodos (default: {DEFAULT_MAX_NODES})"`—
        # salía como `""` hasta v41.3: 21 params publicados sin descripción,
        # justo los que llevan el default o el vocabulario del registro. Se
        # evalúa como `choices`, con el mismo criterio del consumidor.
        ayuda = kw.get("help")
        if ayuda is not None and not isinstance(ayuda, ast.Constant):
            ayuda = str(_evaluar_en_el_modulo(script, ayuda))
        else:
            ayuda = _const("help") or ""

        params[largos[0][2:]] = {
            "type": tipo,
            "required": _const("required") is True,
            "description": ayuda,
            "validators": [f"enum:{','.join(opciones)}"] if opciones else [],
        }
        if items:
            params[largos[0][2:]]["items"] = items
        if accion == "negable":
            params[largos[0][2:]]["negable"] = True
    return params


def acepta_modo_json(script: str) -> bool:
    """La tool habla a una persona por defecto y a una máquina con `--json`.

    Dueño único del criterio (AP-57): lo consultan `vault_smoke`, que mide el
    contrato de máquina, y `sync_to_json`, que lo publica como `json_flag` para
    que el servidor MCP pida el JSON. Hasta v40.34 solo el smoke lo pedía, así
    que el smoke probaba un contrato que el agente nunca recibía: por MCP
    `vault_move` y otras cuatro devolvían su texto como `non_json_output`.
    Solo cuenta un `--json` booleano; uno que toma una ruta es otra cosa.
    """
    param = argparse_params(script).get("json")
    return bool(param) and param["type"] == "boolean"


def reconciled_params(py_tool: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Params publicables: los que la CLI acepta de verdad.

    La descripción escrita a mano gana sobre el `help=` cuando el nombre existe
    en ambos — es la que explica *para qué* sirve el argumento, no solo qué es.
    """
    reales = argparse_params(py_tool.get("script", ""))
    if not reales:
        # Sin argparse legible (tool archivada, script ausente) no hay nada
        # contra qué conciliar: se publica lo declarado, que es lo único que hay.
        return py_tool.get("params", {})

    declarados = py_tool.get("params", {})
    salida: Dict[str, Dict[str, Any]] = {}
    for nombre, real in reales.items():
        declarado = (
            declarados.get(nombre)
            or declarados.get(nombre.replace("-", "_"))
            or declarados.get(nombre.replace("_", "-"))
        )
        entrada = dict(real)
        if declarado:
            if declarado.get("description"):
                entrada["description"] = declarado["description"]
            # Unos `choices` en la CLI son la verdad sobre los valores: un
            # enum escrito a mano no los sustituye. `vault_fix_brackets`
            # publicaba `nested`, que la CLI rechaza, y un cliente que valida
            # contra el esquema no podía enviar `nested_open`, que sí acepta.
            if declarado.get("validators") and not real.get("validators"):
                entrada["validators"] = declarado["validators"]
        salida[nombre] = entrada
    return salida


def params_huerfanos(catalogo: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, List[str]]:
    """AP-40 en el registro: params escritos en `TOOLS_CATALOG` que no son flags.

    `reconciled_params` los descarta al publicar, así que el MCP nunca los
    vio; pero el registro afirmaba un contrato que la CLI no tenía —`decision`
    en `vault_ai_decision`, `probability: low|medium|high` en `vault_risk_save`
    cuando el flag es `--likelihood 1..5`— y ningún guard lo miraba. Hasta
    v41.8 había 81 en 41 tools. Una tool sin argparse legible no cuenta: allí
    lo declarado es lo único que se publica.
    """
    salida: Dict[str, List[str]] = {}
    for nombre, tool in sorted((catalogo or TOOLS_CATALOG).items()):
        reales = argparse_params(tool.get("script", "") or "")
        if not reales:
            continue
        conocidos = {k.replace("-", "_") for k in reales}
        sobran = sorted(p for p in tool.get("params", {}) if p.replace("-", "_") not in conocidos)
        if sobran:
            salida[nombre] = sobran
    return salida


#: Flags que la CLI acepta y MCP no publica: el vault de una llamada MCP lo fija
#: la sesión del servidor (`VAULT_ROOT` del hijo), no el agente. Publicado,
#: `root` dejaba a un agente dirigir `vault_graph_fix` o `vault_section_index`
#: —que escriben— contra cualquier carpeta del disco, y a `vault_fuente_unica`
#: leerla; `vault-root` hacía lo mismo con `vault_sdd_init`, y `vault_root` con
#: `vault_gobernanza`. Se quitan del contrato, no se esconden: el servidor
#: rechaza toda clave que el schema no publique (`additionalProperties: false`).
PARAMS_FIJADOS_POR_LA_SESION = frozenset({"root", "vault-root", "vault_root"})

#: Tipos JSON Schema que el servidor sabe validar y convertir a flags. Uno
#: fuera de aquí se publica como `string`, que es como llega a argparse.
_TIPOS_PUBLICABLES = frozenset({"string", "boolean", "array", "integer", "number", "object"})


def enum_publicado(prop: Dict[str, Any]) -> Optional[List[Any]]:
    """Los valores que el esquema admite para `prop`, o None si no los acota.

    En una lista el enum va en `items`; quien lo lea solo en `prop` no lo ve.
    """
    if prop.get("type") == "array":
        return (prop.get("items") or {}).get("enum")
    return prop.get("enum")


def _convert_to_json_schema(py_tool: Dict[str, Any]) -> Dict[str, Any]:
    """Convierte una entrada de TOOLS_CATALOG al formato inputSchema del JSON.

    AP-40 en las dos direcciones. Hasta v40.34 toda propiedad salía como
    `string` aunque `argparse_params` ya supiera que era `boolean` o `array`: un
    cliente que validaba contra el esquema mandaba `tags: "api demo"` y la nota
    acababa con un solo tag. Y sin `additionalProperties: false` el servidor
    convertía cualquier clave en `--clave`, publicada o no.
    """
    schema = {"type": "object", "properties": {}, "required": [],
              "additionalProperties": False}
    for pname, pinfo in reconciled_params(py_tool).items():
        if pname in PARAMS_FIJADOS_POR_LA_SESION:
            continue
        tipo = pinfo.get("type") if pinfo.get("type") in _TIPOS_PUBLICABLES else "string"
        prop = {"type": tipo, "description": pinfo.get("description", "")}
        if tipo == "array":
            prop["items"] = {"type": pinfo.get("items", "string")}
        if pinfo.get("negable"):
            # `false` tiene flag propio (`--no-<param>`): sin esta marca el
            # servidor solo sabe omitir el flag, y el default de un negable
            # puede ser `True`.
            prop["x-negable"] = True
        if pinfo.get("required"):
            schema["required"].append(pname)
        if "enum" in str(pinfo.get("validators", [])) or any(v.startswith("enum:") for v in pinfo.get("validators", [])):
            for v in pinfo.get("validators", []):
                if v.startswith("enum:"):
                    # En una lista el enum restringe cada elemento, no la lista:
                    # `{"type": "array", "enum": ["01"]}` solo lo cumple un
                    # valor que sea a la vez lista y "01", o sea ninguno.
                    destino = prop["items"] if tipo == "array" else prop
                    tipo_valor = destino["type"]
                    destino["enum"] = v.replace("enum:", "").split(",")
                    # El enum de un entero son enteros: `["1", "2"]` en un
                    # `integer` es un esquema que ningún valor válido cumple.
                    if tipo_valor in ("integer", "number"):
                        convierte = int if tipo_valor == "integer" else float
                        destino["enum"] = [convierte(e) for e in destino["enum"]]
        schema["properties"][pname] = prop
    for restriccion in alternativas_obligatorias(py_tool):
        texto = " | ".join(" + ".join(alt) for alt in restriccion)
        for alternativa in restriccion:
            for pname in alternativa:
                prop = schema["properties"].get(pname)
                if prop is not None:
                    previa = prop["description"]
                    prop["description"] = f"{previa} " if previa else ""
                    prop["description"] += f"(obligatorio uno de: {texto})"
    if not schema["required"]:
        del schema["required"]
    return schema


def errores_para_transporte() -> Dict[str, Any]:
    """La parte de `ERROR_CATALOG` que el servidor MCP necesita para emitir el
    envelope canónico: lo mismo que `construir_error` copia de cada entrada.

    Dueño único de la proyección (AP-57): `sync_to_json` la escribe y
    `check_sync` la compara con esta misma función.
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from vault.kernel.errores import ERROR_CATALOG
    return {
        code: {campo: entrada[campo] for campo in ("category", "severity", "message", "recovery")}
        for code, entrada in sorted(ERROR_CATALOG.items())
    }


def sync_to_json(output_path: Optional[str] = None) -> str:
    """Exporta TOOLS_CATALOG + GROUPS al formato JSON canónico.
    
    Si output_path es None, se guarda junto a este script como tools-catalog.json.
    Retorna la ruta del archivo generado.
    """
    import json, os, sys
    from pathlib import Path

    default_output = output_path is None
    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(__file__), "..", "mcp", "nodejs", "tools-catalog.json"
        )

    # Leer tool-spec.json del vault para obtener status de cada tool.
    # Auto-detecta el vault root (vault-sandbox en este repo).
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import vault_io
    spec_path = Path(vault_io.resolve_tool_spec())
    spec_data: Dict[str, Any] = {}
    if spec_path and spec_path.exists():
        spec_data = json.loads(spec_path.read_text(encoding="utf-8"))
    spec_tools = spec_data.get("tools", {})

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from vault.meta_toolkit.naturalezas import NATURALEZAS
    from vault.meta_toolkit.protocolo_de_sesion import PERFILES, tools_del_perfil

    # Derivar execution_module sin dependencia circular (AP-58).
    # A2: toda tool runtime con script tiene execution_module derivado.
    # Inline de clasificar_tools para no importar vault_servicio desde vault_mcp_catalog.
    naturaleza_por_tool: Dict[str, str] = {}
    for _nat_key, _nat_entry in NATURALEZAS.items():
        for _t in _nat_entry.get("tools", ()):
            naturaleza_por_tool[_t] = _nat_key

    def _execution_module(tool_name: str, tool_entry: Dict[str, Any]) -> Optional[str]:
        if naturaleza_por_tool.get(tool_name) == "meta_estandar":
            return None
        explicit = tool_entry.get("execution_module")
        if explicit and isinstance(explicit, str) and explicit.strip():
            return explicit
        script = tool_entry.get("script", "")
        if script and script.strip():
            stem = script.removesuffix(".py")
            return f"vault_toolkit.operations.{stem}"
        return None

    # Tools de gobernanza del estándar, internal o archived no se exponen via MCP.
    GRUPOS_NO_EXPUESTOS = set(grupos_no_expuestos())
    STATUS_NO_EXPUESTO = {"internal", "archived", "orphan"}

    tools_json = {}
    for name, tool in sorted(TOOLS_CATALOG.items()):
        spec_entry = spec_tools.get(name, {})
        status = spec_entry.get("status", "active")
        group = tool.get("group", "")
        # exposed_via_mcp: false para tools de gobernanza, internal o archived.
        exposed = (status not in STATUS_NO_EXPUESTO and group not in GRUPOS_NO_EXPUESTOS
                   and name not in SERVICIOS_DE_PROCESO_LARGO)

        tools_json[name] = {
            "name": tool["name"],
            "description": tool["purpose"],
            "group": group,
            "script": tool.get("script", ""),
            "inputSchema": _convert_to_json_schema(tool),
            "guards": tool.get("guards", []),
            "side_effects": tool.get("side_effects", []),
            "status": status,
            "exposed_via_mcp": exposed,
            # A2: se deriva inline (misma lógica que clasificar_tools, sin ciclo).
            "execution_module": _execution_module(name, tool),
        }
        if tool.get("related"):
            tools_json[name]["related"] = tool["related"]
        if acepta_modo_json(tool.get("script", "")):
            # El transporte añade `--json`: sin él la tool contesta en prosa.
            tools_json[name]["json_flag"] = True
        alternativas = alternativas_obligatorias(tool)
        if alternativas:
            tools_json[name]["requires_one_of"] = alternativas

    catalog = {
        "tools": tools_json,
        "groups": GROUPS,
        # v40.17 — dueño único del criterio «esta tool no tiene script Python».
        # Vivía duplicado a los dos lados de la frontera de lenguaje:
        # `cli/registry.NATIVE_JS_TOOLS` y `JS_NATIVE_TOOLS` en el `.mjs`, sin
        # nada que los comparase. Ya divergieron una vez —siete contra el
        # catálogo— y el efecto fue AP-05 en el camino de ejecución: el agente
        # recibía `ok: true` de una implementación JS que no escribía, mientras
        # `vault_smoke` probaba el `.py` que el agente no toca. Ahora sale de
        # aquí y los dos consumidores lo leen; `--check` falla si divergen.
        "js_native_tools": sorted(NATIVE_JS_TOOLS),
        # v40.30 — la versión del estándar, para que el `.mjs` deje de escribirla.
        # El servidor anunciaba `v39.3 (SDD)` en su handshake, en `--version` y
        # en cada evento SSE mientras el estándar iba por v40.29: nueve versiones
        # de desfase en la superficie que ve el agente, que es donde más caro
        # sale. Es AP-47 al otro lado de la frontera de lenguaje, donde el guard
        # de cifras a mano no llega — y por eso viaja por la pasarela que sí la
        # cruza, este JSON, en vez de arreglarse escribiendo el número correcto.
        "standard_version": CURRENT_VERSION,
        # AP-52 al otro lado de la frontera de lenguaje: el servidor construía
        # sus errores como `{ok, error_code, tool, message}`, sin `category`,
        # `severity`, `recovery` ni `timestamp`, y el agente no tenía
        # `recovery.action` por el que decidir justo en los fallos del
        # transporte. El `.mjs` no puede importar `ERROR_CATALOG`; lo lee de
        # aquí, y `--check` falla si la copia envejece.
        "errors": errores_para_transporte(),
        # v41.2 — los perfiles que un cliente MCP puede pedir con
        # `VAULT_MCP_PERFIL`. Por MCP el agente recibía todas las tools
        # `runtime` sin guía de cuáles usa una sesión; el perfil `agente` es la
        # unión de las que nombra `PROTOCOLO_DE_SESION`, y viaja por esta
        # pasarela porque el `.mjs` no puede importar el registro.
        "perfiles": {p: tools_del_perfil(p) for p in sorted(PERFILES)},
    }

    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # La CLI pública consume exactamente la misma proyección derivada que el
    # transporte MCP, pero como recurso del paquete. Sólo la sincronización
    # canónica actualiza ambas copias; el paquete no convierte el JSON en una
    # segunda autoridad editorial.
    if default_output:
        product_output = _product_catalog_path()
        with product_output.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)
            f.write("\n")
        _runtime_seed_path().write_bytes(_runtime_seed_text().encode("utf-8"))

    return output_path



def _js_native_del_servidor():
    """El respaldo literal del `.mjs`, leído para poder contrastarlo.

    El servidor prefiere `js_native_tools` del catálogo, pero conserva un
    literal por si el catálogo falta. Un respaldo que nadie compara vuelve a
    ser la segunda declaración que este guard existe para impedir: si diverge,
    basta con que el catálogo no cargue para que las dos fronteras despachen
    distinto. Devuelve None si no se encuentra — que el fichero no esté no es
    lo mismo que que esté vacío (AP-51).
    """
    ruta = REPO_ROOT / "mcp" / "nodejs" / "vault-mcp-server.mjs"
    try:
        texto = ruta.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"JS_NATIVE_TOOLS\s*=\s*new Set\(\[(.*?)\]\)", texto, re.S)
    if not m:
        return None
    return set(re.findall(r'"([^"]+)"', m.group(1)))

def check_sync(json_path: Optional[str] = None) -> Dict[str, Any]:
    """Compara el JSON existente contra TOOLS_CATALOG + GROUPS actuales.
    
    Retorna dict con: {ok: bool, diffs: [str], missing_in_json: [str], missing_in_py: [str]}
    """
    import json, os

    default_json = json_path is None
    if json_path is None:
        json_path = os.path.join(
            os.path.dirname(__file__), "..", "mcp", "nodejs", "tools-catalog.json"
        )

    result = {"ok": True, "diffs": [], "missing_in_json": [], "missing_in_py": []}

    if not os.path.exists(json_path):
        result["ok"] = False
        result["diffs"].append(f"JSON file not found at {json_path}")
        return result

    with open(json_path, "r", encoding="utf-8") as f:
        try:
            existing = json.load(f)
        except json.JSONDecodeError as e:
            result["ok"] = False
            result["diffs"].append(f"Invalid JSON: {e}")
            return result

    existing_tools = set(existing.get("tools", {}).keys())
    py_tools = set(TOOLS_CATALOG.keys())

    result["missing_in_json"] = sorted(py_tools - existing_tools)
    result["missing_in_py"] = sorted(existing_tools - py_tools)

    if result["missing_in_json"]:
        result["ok"] = False
        result["diffs"].append(f"Tools in Python but missing from JSON: {', '.join(result['missing_in_json'])}")
    if result["missing_in_py"]:
        result["ok"] = False
        result["diffs"].append(f"Tools in JSON but missing from Python: {', '.join(result['missing_in_py'])}")

    huerfanos = params_huerfanos()
    if huerfanos:
        result["ok"] = False
        result["params_huerfanos"] = huerfanos
        result["diffs"].append(
            "Params del catálogo que no son flags de argparse (AP-40): "
            + "; ".join(f"{t}: {', '.join(ps)}" for t, ps in huerfanos.items())
            + " — se nombran como el flag real o se quitan")

    # AP-57 — el criterio «esta tool no tiene script Python» tiene un dueño,
    # y aquí se comprueba que nadie lo reescriba. La frontera de lenguaje es lo
    # que lo hacía invisible para `vault_criterios`, que solo mira módulos
    # Python: un criterio copiado en `.mjs` no lo ve ningún guard del repo.
    # Sin esto, el servidor puede despachar como nativo lo que Python cree
    # Python, y el agente recibe `ok: true` de algo que no se ejecutó.
    # La versión viaja por la pasarela, así que la pasarela también se vigila:
    # un JSON con la versión vieja deja al servidor anunciando la vieja, que es
    # el defecto que v40.30 corrigió.
    if existing.get("standard_version") != CURRENT_VERSION:
        result["ok"] = False
        result["diffs"].append(
            f"standard_version divergen: Python={CURRENT_VERSION} "
            f"JSON={existing.get('standard_version')}"
        )

    if existing.get("errors") != errores_para_transporte():
        result["ok"] = False
        result["diffs"].append(
            "errors divergen: el catálogo de errores del JSON no es el de "
            "vault.kernel.errores.ERROR_CATALOG"
        )

    js_en_json = set(existing.get("js_native_tools", []))
    for origen, medido in (("mjs", _js_native_del_servidor()),):
        if medido is not None and medido != set(NATIVE_JS_TOOLS):
            result["ok"] = False
            result["diffs"].append(
                f"js_native_tools divergen ({origen}): "
                f"Python={sorted(NATIVE_JS_TOOLS)} {origen}={sorted(medido)}"
            )
    if js_en_json != set(NATIVE_JS_TOOLS):
        result["ok"] = False
        result["diffs"].append(
            f"js_native_tools divergen: Python={sorted(NATIVE_JS_TOOLS)} "
            f"JSON={sorted(js_en_json)}"
        )

    existing_groups = set(existing.get("groups", {}).keys())
    py_groups = set(GROUPS.keys())

    missing_groups_json = sorted(py_groups - existing_groups)
    missing_groups_py = sorted(existing_groups - py_groups)

    if missing_groups_json:
        result["ok"] = False
        result["diffs"].append(f"Groups in Python missing from JSON: {', '.join(missing_groups_json)}")
    if missing_groups_py:
        result["ok"] = False
        result["diffs"].append(f"Groups in JSON missing from Python: {', '.join(missing_groups_py)}")

    for name in existing_tools & py_tools:
        py_desc = TOOLS_CATALOG[name]["purpose"]
        js_desc = existing["tools"][name].get("description", "")
        if py_desc != js_desc:
            result["ok"] = False
            result["diffs"].append(f"{name}: description differs")

        py_group = TOOLS_CATALOG[name].get("group", "")
        js_group = existing["tools"][name].get("group", "")
        if py_group != js_group:
            result["ok"] = False
            result["diffs"].append(f"{name}: group differs (py={py_group}, js={js_group})")

        # AP-40 — el esquema es lo que el servidor valida (S2) antes de
        # despachar. Hasta v40.34 esta puerta comparaba nombres, grupo y
        # descripción, y un `required: ["path"]` que la CLI ya no exige
        # pasaba en verde: el servidor habría rechazado la llamada válida.
        if existing["tools"][name].get("inputSchema") != _convert_to_json_schema(TOOLS_CATALOG[name]):
            result["ok"] = False
            result["diffs"].append(f"{name}: inputSchema differs (regenerar con --sync)")
        if existing["tools"][name].get("requires_one_of") != (alternativas_obligatorias(TOOLS_CATALOG[name]) or None):
            result["ok"] = False
            result["diffs"].append(f"{name}: requires_one_of differs (regenerar con --sync)")

        py_guard_count = len(TOOLS_CATALOG[name].get("guards", []))
        js_guard_count = len(existing["tools"][name].get("guards", []))
        if py_guard_count != js_guard_count:
            result["ok"] = False
            result["diffs"].append(f"{name}: guard count differs (py={py_guard_count}, js={js_guard_count})")

    # El recurso instalado es una proyección, no un catálogo independiente.
    # Sólo se contrasta en el camino canónico (sin --json de prueba).
    if default_json:
        product_path = _product_catalog_path()
        if not product_path.is_file():
            result["ok"] = False
            result["diffs"].append(f"product catalog not found at {product_path}")
        else:
            try:
                product_catalog = json.loads(product_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                result["ok"] = False
                result["diffs"].append(f"invalid product catalog: {exc}")
            else:
                if product_catalog != existing:
                    result["ok"] = False
                    result["diffs"].append("product catalog differs from canonical JSON projection")
        seed_path = _runtime_seed_path()
        try:
            seed_actual = seed_path.read_text(encoding="utf-8")
        except OSError:
            seed_actual = None
        if seed_actual != _runtime_seed_text():
            result["ok"] = False
            result["diffs"].append(
                f"runtime seed {seed_path.name} differs from vault_registry.runtime_seed_projection() "
                "(regenerar con --sync)"
            )

    return result


def mapa_de_grupos() -> Dict[str, Dict[str, Any]]:
    """`{tool: {"name": grupo, "id": group_id}}` derivado de la fuente única.

    El grupo sale de `GROUPS` y el número de la numeración de
    `scripts/README.md` — exactamente lo que `check_contracts` exige que el
    tool-spec cumpla. Se extrae aquí para que la derivación tenga **un solo
    sitio**: `check_contracts` la verificaba y `vault_manifest._bootstrap_spec`
    la producía, y cada uno la sacaba de un lado distinto —el segundo, de
    `vault_compact_contracts.GROUPS`, que ya es un derivado del tool-spec que
    el propio bootstrap está generando—. El productor y el verificador leyendo
    fuentes diferentes es la forma en que una divergencia se estrena.
    """
    import re
    from pathlib import Path

    readme = (Path(__file__).resolve().parent / "README.md").read_text(
        encoding="utf-8"
    )
    gid_por_grupo = {
        etiqueta: int(numero)
        for numero, etiqueta in re.findall(
            r"^## Grupo (\d+) — (.+?)\s*$", readme, re.M
        )
    }
    return {
        t: {"name": grupo, "id": gid_por_grupo.get(grupo, 0)}
        for grupo, tools in GROUPS.items()
        for t in tools
    }


# Citas retiradas del conjunto de grupos no expuestos (no-derogación).
GRUPOS_NO_EXPUESTOS_RETIRADOS: Dict[str, Dict[str, str]] = {
    "meta": {
        "superseded_by": "grupos_no_expuestos() — CAPACIDADES['gobernanza_del_estandar']",
        "why": (
            "«meta» no es un grupo de GROUPS: solo es el `group` que vault_manifest "
            "pone a seis tools `internal` del tool-spec, que ya se ocultan por su "
            "status. La cita no excluía nada (medido en v41.2)."
        ),
        "since": "v41.3",
    },
}


def grupos_no_expuestos() -> List[str]:
    """Grupos de `GROUPS` que no se exponen a MCP, derivados de la capacidad.

    Son los de `CAPACIDADES['gobernanza_del_estandar']`: miden este repo y no las
    notas de nadie, así que un agente que usa el vault no tiene para qué
    llamarlos. Hasta v41.2 era un conjunto escrito a mano que citaba un grupo
    inexistente; ahora un grupo que entre o salga de la capacidad cambia la
    exposición sin tocar este fichero. Los datos se leen de la hoja
    `vault.meta_toolkit.capacidades` y no de `vault_servicio`, que importa este
    módulo (AP-58).
    """
    raiz = str(Path(__file__).resolve().parent.parent)
    if raiz not in sys.path:
        sys.path.insert(0, raiz)
    from vault.meta_toolkit.capacidades import CAPACIDADES

    ids = set(CAPACIDADES["gobernanza_del_estandar"]["grupos"])
    return sorted({d["name"] for d in mapa_de_grupos().values() if d["id"] in ids})

def check_contracts(spec_path: Optional[str] = None) -> Dict[str, Any]:
    """Guard catálogo ↔ `tool-spec.json`.

    El contrato es el registro que dice qué devuelve cada tool; el catálogo es
    el que dice qué tools existen. Cuando divergen, la tool existe pero nadie
    puede validarla: fue el caso de las 10 que se expusieron por MCP durante
    versiones sin entrada de contrato, y el de las 5 archivadas que seguían
    declarando contrato sin código detrás.

    Tres invariantes:

      1. Toda tool del catálogo tiene entrada en `tool-spec.json`.
      2. Toda entrada que NO está en el catálogo declara por qué sigue ahí —
         `status` en `archived | internal | orphan`. No se borran (no-derogación):
         se anotan.
      3. `group` y `group_id` de cada tool del catálogo se derivan de `GROUPS`
         y de la numeración de `scripts/README.md`, que es la que `vault_doc_sync`
         ya vigila. Sin esto reaparece el cuarto sistema de nombres.
    """
    import json
    import re
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import vault_io

    ruta = Path(spec_path) if spec_path else Path(vault_io.resolve_tool_spec())
    data = json.loads(ruta.read_text(encoding="utf-8"))
    entradas = data.get("tools", {})

    # La derivación vive en `mapa_de_grupos()`, que es también la que consume
    # el bootstrap del tool-spec: verificador y productor, la misma fuente.
    mapa = mapa_de_grupos()
    pertenencia = {t: d["name"] for t, d in mapa.items()}
    gid_por_grupo = {d["name"]: d["id"] for d in mapa.values()}

    ESTADOS_SIN_CATALOGO = {"archived", "internal", "orphan"}
    result: Dict[str, Any] = {
        "ok": True,
        "tool": "vault_mcp_catalog",
        "action": "check-contracts",
        "spec_path": str(ruta),
        "tools_checked": len(TOOLS_CATALOG),
        "entries_checked": len(entradas),
        "problems": [],
    }

    def problema(kind: str, detail: str) -> None:
        result["ok"] = False
        result["problems"].append({"kind": kind, "detail": detail})

    for nombre in sorted(TOOLS_CATALOG):
        entrada = entradas.get(nombre)
        if entrada is None:
            problema("tool_sin_contrato", nombre)
            continue
        grupo = pertenencia.get(nombre)
        if grupo and entrada.get("group") != grupo:
            problema("group_divergente", f"{nombre}: {entrada.get('group')!r} != {grupo!r}")
        esperado = gid_por_grupo.get(grupo) if grupo else None
        if esperado is not None and entrada.get("group_id") != esperado:
            problema(
                "group_id_divergente",
                f"{nombre}: {entrada.get('group_id')} != {esperado} (Grupo de scripts/README.md)",
            )

    for nombre in sorted(entradas):
        if nombre in TOOLS_CATALOG:
            continue
        estado = entradas[nombre].get("status")
        if estado not in ESTADOS_SIN_CATALOGO:
            problema(
                "entrada_sin_catalogo_ni_estado",
                f"{nombre}: status={estado!r}, se esperaba uno de {sorted(ESTADOS_SIN_CATALOGO)}",
            )

    # Invariante 4 — ningún módulo ejecutable queda sin clasificar.
    #
    # Los tres invariantes de arriba miran del catálogo hacia el contrato y del
    # contrato hacia el catálogo, pero ninguno mira el disco: un script con CLI
    # propia que no aparece en ninguno de los dos registros no incumple nada y no
    # existe para el estándar. Medido: cinco módulos con `ArgumentParser` y
    # `__main__` —`vault_errors`, `vault_mcp`, `vault_mcp_catalog`,
    # `vault_spec_catalog_check`, `vault_spec_generate_catalog`— estaban en ese
    # estado, y uno de ellos es el que ejecuta esta misma comprobación y aparece
    # en el checklist de cierre de `AGENTS.md`.
    #
    # La clasificación se saca del AST y no de una lista escrita a mano, porque
    # una lista a mano es justo la fuente de verdad paralela que AP-05 prohíbe:
    # un módulo que gana CLI mañana entra solo. Las librerías —sin `__main__`—
    # no necesitan entrada: no son un camino de acceso.
    import ast

    scripts_dir = Path(__file__).resolve().parent
    sin_clasificar = []
    for src in sorted(scripts_dir.glob("vault_*.py")):
        texto = src.read_text(encoding="utf-8", errors="replace")
        if "__main__" not in texto or "ArgumentParser" not in texto:
            continue
        try:
            ast.parse(texto)
        except SyntaxError:
            continue
        if src.stem in TOOLS_CATALOG or src.stem in entradas:
            continue
        sin_clasificar.append(src.stem)
    result["executable_modules_unclassified"] = sin_clasificar
    for nombre in sin_clasificar:
        problema(
            "modulo_ejecutable_sin_clasificar",
            f"{nombre}: tiene CLI propia y no está ni en el catálogo ni en el "
            f"tool-spec — publícalo o anótalo con status internal/archived/orphan",
        )

    # Toda entrada que no se publica dice por qué. `status: internal` sin motivo
    # escrito es una decisión que nadie puede revisar: al inventariarlas, las
    # nueve `internal` iban desde «es una librería con CLI de diagnóstico» hasta
    # «mantiene el toolkit, no el vault», y el registro no distinguía.
    for nombre in sorted(entradas):
        entrada = entradas[nombre]
        if entrada.get("status", "active") == "active":
            continue
        if not (entrada.get("reason") or "").strip():
            problema("estado_sin_motivo",
                     f"{nombre}: status={entrada.get('status')!r} sin campo `reason`")

    # AP-48 — implementación paralela por camino de acceso.
    #
    # El servidor MCP puede resolver una tool con backend nativo en Node en vez
    # de lanzar el script. Eso es legítimo solo cuando **no hay** script: si los
    # dos existen, hay dos implementaciones bajo un nombre y un contrato, y cuál
    # se ejecuta depende de por dónde entre el llamante. Medido en v39.4: siete
    # de las nueve nativas tenían `.py`, ninguna coincidía con su contrato, y la
    # de `vault_graph` devolvía `ok: true` sin escribir el grafo.
    #
    # Hasta v40.17 esto leía el `.mjs` con su propia regex y el comentario decía
    # que una lista en Python «sería el mismo defecto que la norma persigue».
    # Era cierto mientras Python no fuese el dueño: había dos declaraciones y
    # ninguna comparación. Ahora el dueño es `NATIVE_JS_TOOLS`, viaja al `.mjs`
    # por `js_native_tools` del catálogo, y el literal del servidor sobrevive
    # solo como respaldo — que `--check` contrasta. Sigue midiéndose lo que se
    # ejecuta; lo que desaparece es el segundo lector con su propia regex, que
    # es lo que se rompió al cambiar un `const` por un `let`.
    nativas_mjs = _js_native_del_servidor()
    result["js_native"] = []
    if nativas_mjs is None:
        problema("js_native_ilegible", "no se pudo leer JS_NATIVE_TOOLS de vault-mcp-server.mjs")
    else:
        nativas = sorted(nativas_mjs)
        result["js_native"] = nativas
        scripts_dir = Path(__file__).resolve().parent
        for nombre in nativas:
            if (scripts_dir / f"{nombre}.py").is_file():
                problema(
                    "implementacion_paralela",
                    f"{nombre}: backend nativo en el servidor MCP y scripts/{nombre}.py "
                    f"a la vez — dos implementaciones, un contrato (AP-48)",
                )

    return result


def check_params(json_path: Optional[str] = None) -> Dict[str, Any]:
    """AP-40 — ningún param publicado puede ser rechazado por la CLI.

    Lee el JSON ya generado (que es lo que el servidor MCP consume de verdad,
    no el catálogo Python) y comprueba cada propiedad contra el `argparse` del
    script. Comparar Python contra Python no detectaría nada: el defecto vivía
    en las dos copias a la vez.
    """
    ruta = Path(json_path) if json_path else (
        Path(__file__).resolve().parent.parent / "mcp" / "nodejs" / "tools-catalog.json"
    )
    result: Dict[str, Any] = {
        "ok": True, "tool": "vault_mcp_catalog", "action": "check-params",
        "json_path": str(ruta), "tools_checked": 0, "problems": [],
    }
    if not ruta.is_file():
        result["ok"] = False
        result["problems"].append({"tool": "-", "problem": f"no existe {ruta}"})
        return result

    catalogo = json.loads(ruta.read_text(encoding="utf-8"))
    tools = catalogo.get("tools", catalogo)
    for nombre, entrada in sorted(tools.items()):
        py = TOOLS_CATALOG.get(nombre, {})
        reales = argparse_params(py.get("script", ""))
        if py.get("runtime") == "node":
            # Las tools JS-native no tienen argparse contra el que comparar: su
            # contrato lo implementa el servidor. Se excluyen por lo que son,
            # no por parecer vacías — que era el efecto de la regla anterior.
            continue
        if py.get("script") is None:
            # Las tools con script=None son invocadas via __module__: no tienen
            # script en scripts/ y argparse_params devuelve {}. No hay contra
            # qué comparar; el MCP las sirve por su execution_module.
            continue
        publicados_pre = (entrada.get("inputSchema") or {}).get("properties", {})
        if not reales and not publicados_pre:
            # Sin argparse y sin nada publicado no hay contra qué comparar. Con
            # algo publicado sí lo hay, y el veredicto es duro: **todo** sobra.
            # Saltar este caso era saltarse el único en que el fallo es total,
            # y es el que tenía `vault_master_index`.
            continue
        result["tools_checked"] += 1
        publicados = (entrada.get("inputSchema") or {}).get("properties", {})
        inalcanzables = posicionales_obligatorios(py.get("script", ""))
        if inalcanzables:
            result["ok"] = False
            result["problems"].append({
                "tool": nombre,
                "problem": ("entrada obligatoria que MCP no puede rellenar "
                            f"(posicional): {', '.join(inalcanzables)}"),
                "fix": ("añade la forma nombrada `--<param>` conservando el "
                        "posicional para la CLI"),
            })
        sobran = [p for p in publicados if p not in reales]
        if sobran:
            result["ok"] = False
            result["problems"].append({
                "tool": nombre,
                "problem": f"params que la CLI rechaza: {', '.join(sorted(sobran))}",
                "fix": "python scripts/vault_mcp_catalog.py --sync",
            })
        # AP-40 también en los valores: un param que la CLI acepta con un enum
        # publicado que ella rechaza falla igual, solo que para ciertos valores.
        for param, prop in sorted(publicados.items()):
            elecciones = [v[len("enum:"):].split(",")
                          for v in (reales.get(param) or {}).get("validators", [])
                          if v.startswith("enum:")]
            enum = enum_publicado(prop)
            if not elecciones or enum is None:
                continue
            ajenos = sorted(set(map(str, enum)) - set(elecciones[0]))
            if ajenos:
                result["ok"] = False
                result["problems"].append({
                    "tool": nombre,
                    "problem": f"--{param}: valores publicados que la CLI rechaza: {', '.join(ajenos)}",
                    "fix": "python scripts/vault_mcp_catalog.py --sync",
                })
    return result


def main():
    parser = argparse.ArgumentParser(description="Vault MCP Catalog — sincronizar con JSON canónico", allow_abbrev=False)
    parser.add_argument("--sync", action="store_true", help="Generar tools-catalog.json desde PY")
    parser.add_argument("--check", action="store_true", help="Verificar que JSON está en sync con PY")
    parser.add_argument("--stats", action="store_true", help="Mostrar estadísticas del catálogo")
    parser.add_argument("--output", type=str, default=None, help="Ruta de salida para --sync")
    parser.add_argument("--json", type=str, default=None, help="Ruta del JSON para --check y --check-params")
    parser.add_argument("--check-contracts", action="store_true",
                        # Sin flechas Unicode: el help se imprime en la consola
                        # de Windows (cp1252) y un '↔' aquí rompe `--help`.
                        help="Verificar catalogo vs tool-spec.json (contratos, grupo y group_id)")
    parser.add_argument("--spec", type=str, default=None,
                        help="Ruta del tool-spec.json para --check-contracts")
    parser.add_argument("--check-params", action="store_true",
                        help="AP-40: verificar que todo param publicado existe en el argparse del script")
    args = parser.parse_args()

    if args.check_params:
        # `--json` es la ruta del catálogo a medir. Hasta v40.34 no se pasaba:
        # `--check-params --json otro.json` medía en silencio el del repo y
        # salía verde aunque el catálogo señalado estuviera roto (AP-44).
        result = check_params(args.json)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["ok"] else 1)

    if args.check_contracts:
        result = check_contracts(args.spec)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["ok"] else 1)

    if args.stats:
        print(f"Tools en catálogo Python: {len(TOOLS_CATALOG)}")
        print(f"Grupos: {len(GROUPS)}")
        for grp, names in GROUPS.items():
            print(f"  {grp}: {len(names)} tools")
        sys.exit(0)

    if args.sync:
        path = sync_to_json(args.output)
        print(f"Catálogo JSON generado: {path}")
        print(f"  Tools: {len(TOOLS_CATALOG)}")
        print(f"  Grupos: {len(GROUPS)}")
        sys.exit(0)

    if args.check:
        result = check_sync(args.json)
        if result["ok"]:
            print("OK: El JSON está sincronizado con el catálogo Python.")
            sys.exit(0)
        else:
            print("DESINCRONIZADO:")
            for d in result["diffs"]:
                print(f"  - {d}")
            if result["missing_in_json"]:
                print(f"  Herramientas en Python que faltan en JSON: {', '.join(result['missing_in_json'])}")
            if result["missing_in_py"]:
                print(f"  Herramientas en JSON que faltan en Python: {', '.join(result['missing_in_py'])}")
            sys.exit(1)

    parser.print_help()


if __name__ == "__main__":
    main()
