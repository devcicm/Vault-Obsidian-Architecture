#!/usr/bin/env python3
"""
Vault MCP Catalog — Catálogo canónico de tools del vault.

Contiene la definición de todas las 69 tools con sus:
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
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional


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
                "description": "Contenido Markdown. Usar @file:ruta para leer de archivo",
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
        "example": 'python vault_write.py --folder "01_Projects/mi-api" --title "Overview" --content "# Overview\\n\\nAPI REST" --tags "api backend"',
        "related": ["vault_read", "vault_append", "vault_audit"],
    },
    "vault_read": {
        "name": "vault_read",
        "script": "vault_read.py",
        "group": "Core",
        "purpose": "Lee una nota del vault por ruta relativa o por título.",
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
            "project": {
                "type": "string",
                "required": False,
                "description": "Filtrar por proyecto",
                "validators": [],
            },
            "folder": {
                "type": "string",
                "required": False,
                "description": "Filtrar por carpeta",
                "validators": [],
            },
            "limit": {
                "type": "int",
                "required": False,
                "description": "Límite de resultados (default: 10)",
                "validators": ["min:1", "max:100"],
            },
        },
        "guards": [],
        "side_effects": [],
        "example": 'python vault_search.py --query "circuit breaker"\npython vault_search.py --query "deploy" --project "mi-api"',
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
        "side_effects": [],
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
                "description": "Filtrar por tipo: empty, nested",
                "validators": ["enum:empty,nested"],
            },
        },
        "guards": [],
        "side_effects": ["Backups en .vault-fix-backup-YYYYMMDD/"],
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
        "example": "python vault_tags.py --ledger",
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
            "hash": {
                "type": "boolean",
                "required": False,
                "description": "También generar hash-index.json",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": [
            "Actualiza 99_Index/search-index.json",
            "Opcional: 99_Index/graph.json, hash-index.json",
        ],
        "example": "python vault_reindex.py\npython vault_reindex.py --graph --hash",
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
        "example": 'python vault_move.py --from "01_Projects/foo.md" --to "03_Decisions/foo.md"\npython vault_move.py --folder "01_Projects/old" --to_folder "01_Projects/new"',
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
    "vault_mermaid_check": {
        "name": "vault_mermaid_check",
        "script": "vault_mermaid_check.py",
        "group": "Diagramas",
        "purpose": "Valida diagramas Mermaid y detecta errores de sintaxis.",
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
                "description": "Auto-corregir errores",
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
        "side_effects": [],
        "example": 'python vault_mermaid_check.py\npython vault_mermaid_check.py --path "06_Diagrams/foo.md"\npython vault_mermaid_check.py --fix',
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
            "entity": {
                "type": "string",
                "required": True,
                "description": "Entidad origen",
                "validators": ["not_empty"],
            },
            "to": {
                "type": "string",
                "required": True,
                "description": "Entidad destino",
                "validators": ["not_empty"],
            },
            "type": {
                "type": "string",
                "required": True,
                "description": "Tipo: one-to-one, one-to-many, many-to-many",
                "validators": ["enum:one-to-one,one-to-many,many-to-many"],
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
        "example": 'python vault_relation_add.py --project "mi-api" --from "User" --to "Order" --relation_type "one-to-many"',
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
            "module": {
                "type": "string",
                "required": True,
                "description": "Nombre del módulo",
                "validators": ["not_empty"],
            },
            "language": {
                "type": "string",
                "required": True,
                "description": "Lenguaje: python, javascript, typescript, go, rust",
                "validators": ["enum:python,javascript,typescript,go,rust"],
            },
            "viewpoints": {
                "type": "string",
                "required": False,
                "description": "Viewpoints IEEE 1016: context,interface,data,operations,dependency",
                "validators": [],
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
            "depth": {
                "type": "int",
                "required": False,
                "description": "Profundidad máxima (default: 3)",
                "validators": ["min:1", "max:10"],
            },
        },
        "guards": [],
        "side_effects": ["Genera 11_Code/{project}/map.md con diagrama"],
        "example": 'python vault_code_map.py --project "mi-api"\npython vault_code_map.py --project "mi-api" --depth 2',
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
            "from": {
                "type": "string",
                "required": True,
                "description": "Componente origen",
                "validators": [],
            },
            "to": {
                "type": "string",
                "required": True,
                "description": "Componente destino",
                "validators": [],
            },
            "type": {
                "type": "string",
                "required": True,
                "description": "Tipo: imports,calls,extends,implements,depends",
                "validators": ["enum:imports,calls,extends,implements,depends"],
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
            "query": {
                "type": "string",
                "required": True,
                "description": "Consulta: module, relation, imports",
                "validators": ["enum:module,relation,imports"],
            },
            "project": {
                "type": "string",
                "required": False,
                "description": "Filtrar por proyecto",
                "validators": [],
            },
            "pattern": {
                "type": "string",
                "required": False,
                "description": "Patrón de búsqueda",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": [],
        "example": 'python vault_code_query.py --project "mi-api" --list\npython vault_code_query.py --query "imports" --pattern "auth"',
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
            "action": {
                "type": "string",
                "required": True,
                "description": "Acción: scan, update, diff",
                "validators": ["enum:scan,update,diff"],
            },
        },
        "guards": [],
        "side_effects": ["Actualiza 11_Code/{project}/index.json"],
        "example": 'python vault_code_sync.py --project "mi-api"\npython vault_code_sync.py --project "mi-api" --action "update"',
        "related": ["vault_code_map", "vault_reindex"],
    },
    "vault_code_tag": {
        "name": "vault_code_tag",
        "script": "vault_code_tag.py",
        "group": "Normas",
        "purpose": "Etiqueta módulos de código por funcionalidad.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
            "module": {
                "type": "string",
                "required": True,
                "description": "Módulo a etiquetar",
                "validators": [],
            },
            "tags": {
                "type": "string",
                "required": True,
                "description": "Tags separados por coma",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Actualiza frontmatter del módulo"],
        "example": 'python vault_code_tag.py --list',
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
            "category": {
                "type": "string",
                "required": True,
                "description": "Categoría: creational, structural, behavioral, architectural",
                "validators": ["enum:creational,structural,behavioral,architectural"],
            },
            "description": {
                "type": "string",
                "required": True,
                "description": "Descripción del patrón",
                "validators": ["min_length:20"],
            },
            "implementation": {
                "type": "string",
                "required": False,
                "description": "Código de ejemplo",
                "validators": [],
            },
            "use_cases": {
                "type": "string",
                "required": False,
                "description": "Casos de uso separados por coma",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Crea nota en 05_Patterns/"],
        "example": 'python vault_pattern_save.py --project "mi-api" --name "Repository" --type "architectural" --status "implemented" --description "Abstraccion de acceso a datos"',
        "related": ["vault_pattern_list", "vault_code_module"],
    },
    "vault_pattern_list": {
        "name": "vault_pattern_list",
        "script": "vault_pattern_list.py",
        "group": "Patrones",
        "purpose": "Lista patrones arquitectónicos disponibles.",
        "params": {
            "category": {
                "type": "string",
                "required": False,
                "description": "Filtrar por categoría",
                "validators": ["enum:creational,structural,behavioral,architectural"],
            },
            "search": {
                "type": "string",
                "required": False,
                "description": "Buscar por nombre",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": [],
        "example": 'python vault_pattern_list.py\npython vault_pattern_list.py --category "architectural"',
        "related": ["vault_pattern_save", "vault_search"],
    },
    "vault_knowledge_save": {
        "name": "vault_knowledge_save",
        "script": "vault_knowledge_save.py",
        "group": "Conocimiento",
        "purpose": "Guarda conocimiento estructurado por tema.",
        "params": {
            "topic": {
                "type": "string",
                "required": True,
                "description": "Tema principal",
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
        "example": 'python vault_knowledge_save.py --category "architecture" --title "Clean Architecture" --content "# Clean Architecture" --tags "architecture clean"',
        "related": ["vault_knowledge_get", "vault_search"],
    },
    "vault_knowledge_get": {
        "name": "vault_knowledge_get",
        "script": "vault_knowledge_get.py",
        "group": "Conocimiento",
        "purpose": "Recupera conocimiento por tema o búsqueda.",
        "params": {
            "topic": {
                "type": "string",
                "required": False,
                "description": "Tema a buscar",
                "validators": [],
            },
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
            "include_history": {
                "type": "boolean",
                "required": False,
                "description": "Incluir .history/ (default: False)",
                "validators": [],
            },
            "compress": {
                "type": "boolean",
                "required": False,
                "description": "Comprimir a zip (default: False)",
                "validators": [],
            },
            "label": {
                "type": "string",
                "required": False,
                "description": "Etiqueta opcional",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Crea carpeta en vault-backups/"],
        "example": 'python vault_backup.py\npython vault_backup.py --compress --label "pre-migration"',
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
            "backup_id": {
                "type": "string",
                "required": True,
                "description": "ID del backup a restaurar",
                "validators": [],
            },
            "target": {
                "type": "string",
                "required": False,
                "description": "Carpeta destino (default: VAULT_ROOT)",
                "validators": [],
            },
            "dry_run": {
                "type": "boolean",
                "required": False,
                "description": "Simular sin aplicar",
                "validators": [],
            },
        },
        "guards": ["Confirmar antes de sobreescribir"],
        "side_effects": ["Sobreescribe archivos del vault"],
        "example": 'python vault_restore.py --backup_name "2026-06-24_120000"\npython vault_restore.py --backup_name "2026-06-24_120000" --confirm "yes"',
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
            "variables": {
                "type": "string",
                "required": True,
                "description": "Variables en formato KEY=VALUE separadas por espacio",
                "validators": [],
            },
        },
        "guards": ["No guardar secrets en texto plano"],
        "side_effects": ["Crea nota en 09_Infrastructure/{project}/"],
        "example": 'python vault_env_save.py --project "mi-api" --environment "prod" --vars "DB_HOST=localhost"',
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
            "title": {
                "type": "string",
                "required": True,
                "description": "Título",
                "validators": ["not_empty"],
            },
            "provider": {
                "type": "string",
                "required": True,
                "description": "Proveedor: aws, gcp, azure, onprem",
                "validators": ["enum:aws,gcp,azure,onprem"],
            },
            "components": {
                "type": "string",
                "required": True,
                "description": "Componentes separados por coma",
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
        "example": 'python vault_infra_save.py --name "prod-cluster" --type "compute" --description "Cluster productivo" --config "region=us-east-1"',
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
            "components": {
                "type": "string",
                "required": True,
                "description": "Componentes separados por coma",
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
        "example": 'python vault_infra_map.py --project "mi-api" --location "us-east-1"',
        "related": ["vault_infra_save", "vault_diagram_save"],
    },
    "vault_security_scan": {
        "name": "vault_security_scan",
        "script": "vault_security_scan.py",
        "group": "Seguridad",
        "purpose": "Escaneo de seguridad del vault y código.",
        "params": {
            "project": {
                "type": "string",
                "required": False,
                "description": "Proyecto específico",
                "validators": [],
            },
            "scan_type": {
                "type": "string",
                "required": False,
                "description": "Tipo: full, secrets, dependencies",
                "validators": ["enum:full,secrets,dependencies"],
            },
        },
        "guards": [],
        "side_effects": ["Genera reporte en 02_Observability/security/"],
        "example": 'python vault_security_scan.py --path "01_Projects"\npython vault_security_scan.py --path "01_Projects" --project "mi-api" --categories secrets pii',
        "related": ["vault_audit", "vault_log_error"],
    },
    "vault_drift_detect": {
        "name": "vault_drift_detect",
        "script": "vault_drift_detect.py",
        "group": "Drift Detection",
        "purpose": "Detecta drift de configuración entre ambientes.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
            "compare": {
                "type": "string",
                "required": True,
                "description": "Entornos a comparar: dev-staging, staging-prod",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Reporta drift detectado"],
        "example": 'python vault_drift_detect.py --path "01_Projects" --project "mi-api" --mode "status"',
        "related": ["vault_audit", "vault_env_matrix"],
    },
    "vault_impact": {
        "name": "vault_impact",
        "script": "vault_impact.py",
        "group": "Propagación",
        "purpose": "Análisis de impacto en cascada de cambios.",
        "params": {
            "path": {
                "type": "string",
                "required": True,
                "description": "Nota a analizar",
                "validators": ["within_vault"],
            },
            "depth": {
                "type": "int",
                "required": False,
                "description": "Profundidad máxima (default: 3)",
                "validators": ["min:1", "max:10"],
            },
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
            "source": {
                "type": "string",
                "required": True,
                "description": "Nota fuente",
                "validators": ["within_vault"],
            },
            "template": {
                "type": "string",
                "required": True,
                "description": "Template de propagación",
                "validators": [],
            },
            "dry_run": {
                "type": "boolean",
                "required": False,
                "description": "Simular sin aplicar",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Actualiza notas relacionadas"],
        "example": 'python vault_propagate.py --changed "01_Projects/mi-api/overview.md" --queue-report',
        "related": ["vault_impact", "vault_write"],
    },
    "vault_quality_check": {
        "name": "vault_quality_check",
        "script": "vault_quality_check.py",
        "group": "Data Quality",
        "purpose": "Verifica calidad de datos del vault.",
        "params": {
            "project": {
                "type": "string",
                "required": False,
                "description": "Proyecto específico",
                "validators": [],
            },
            "metrics": {
                "type": "string",
                "required": False,
                "description": "Métricas: completeness,consistency,accuracy",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Genera reporte en 00_System/"],
        "example": 'python vault_quality_check.py\npython vault_quality_check.py --project "mi-api" --metrics "completeness"',
        "related": ["vault_audit", "vault_fundamentals"],
    },
    "vault_fundamentals": {
        "name": "vault_fundamentals",
        "script": "vault_fundamentals.py",
        "group": "Data Quality",
        "purpose": "Métricas fundamentales del vault.",
        "params": {},
        "guards": [],
        "side_effects": [],
        "example": "python vault_fundamentals.py",
        "related": ["vault_audit", "vault_quality_check"],
    },
    "vault_project_status": {
        "name": "vault_project_status",
        "script": "vault_project_status.py",
        "group": "Vista del Proyecto",
        "purpose": "Muestra estado actual de un proyecto.",
        "params": {
            "project": {
                "type": "string",
                "required": True,
                "description": "Slug del proyecto",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": [],
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
            "section": {
                "type": "string",
                "required": True,
                "description": "Sección (ej: 01_Projects)",
                "validators": [],
            },
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
        "params": {
            "include_subdirs": {
                "type": "boolean",
                "required": False,
                "description": "Incluir subdirectorios",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Genera 99_Index/master-index.md"],
        "example": "python vault_master_index.py\npython vault_master_index.py --include_subdirs",
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
            "days": {
                "type": "int",
                "required": False,
                "description": "Días hacia atrás (default: 30)",
                "validators": ["min:1", "max:365"],
            },
        },
        "guards": [],
        "side_effects": [],
        "example": "python vault_timeline.py\npython vault_timeline.py --days 7",
        "related": ["vault_audit", "vault_change_log"],
    },
    "vault_change_log": {
        "name": "vault_change_log",
        "script": "vault_change_log.py",
        "group": "Change Log",
        "purpose": "Genera registro de cambios del vault.",
        "params": {
            "project": {
                "type": "string",
                "required": False,
                "description": "Proyecto específico",
                "validators": [],
            },
            "from": {
                "type": "string",
                "required": False,
                "description": "Desde fecha (YYYY-MM-DD)",
                "validators": [],
            },
            "to": {
                "type": "string",
                "required": False,
                "description": "Hasta fecha (YYYY-MM-DD)",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": [],
        "example": 'python vault_change_log.py --query --last 10\npython vault_change_log.py --action "updated" --path "01_Projects/mi-api/overview.md" --summary "Revision"',
        "related": ["vault_timeline", "vault_audit"],
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
            "decision": {
                "type": "string",
                "required": True,
                "description": "Decisión tomada",
                "validators": ["not_empty"],
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
        "side_effects": ["Crea nota en 03_Decisions/"],
        "example": 'python vault_ai_decision.py --project "mi-api" --title "Elegir PostgreSQL" --decision_type "architecture" --description "Motor de datos del servicio" --rationale "Garantias ACID"',
        "related": ["vault_norms", "vault_audit"],
    },
    "vault_norms": {
        "name": "vault_norms",
        "script": "vault_norms.py",
        "group": "Normas",
        "purpose": "Gestiona normas y estándares del vault.",
        "params": {
            "action": {
                "type": "string",
                "required": True,
                "description": "Acción: list, add, check",
                "validators": ["enum:list,add,check"],
            },
            "name": {
                "type": "string",
                "required": False,
                "description": "Nombre de la norma",
                "validators": [],
            },
            "content": {
                "type": "string",
                "required": False,
                "description": "Contenido de la norma",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": [],
        "example": 'python vault_norms.py --list\npython vault_norms.py --action "add" --name "AP-25" --content "Code style rules"',
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
        "example": "python vault_smoke.py --tool vault_write\npython vault_smoke.py --check --strict",
        "related": ["vault_mcp_catalog", "vault_noop_audit"],
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
            "checklist de CLAUDE.md las cite todas. No reimplementa ninguna "
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
                "description": "Comprueba que el checklist de CLAUDE.md cite todas las puertas",
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
            "python vault_gate.py --strict\n"
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
            "project": {
                "type": "string",
                "required": True,
                "description": "Proyecto",
                "validators": [],
            },
            "action": {
                "type": "string",
                "required": True,
                "description": "Acción: list, add, remove",
                "validators": ["enum:list,add,remove"],
            },
            "token_type": {
                "type": "string",
                "required": False,
                "description": "Tipo: api_key, access_token, refresh_token",
                "validators": [],
            },
        },
        "guards": ["No guardar tokens en texto plano"],
        "side_effects": [],
        "example": 'python vault_tokens.py --summary\npython vault_tokens.py --project "mi-api" --action "add" --token_type "api_key"',
        "related": ["vault_token_counter", "vault_token_service"],
    },
    "vault_token_counter": {
        "name": "vault_token_counter",
        "script": "vault_token_counter.py",
        "group": "Tokens",
        "purpose": "Cuenta tokens de contenido.",
        "params": {
            "content": {
                "type": "string",
                "required": True,
                "description": "Contenido a contar",
                "validators": [],
            },
            "model": {
                "type": "string",
                "required": False,
                "description": "Modelo: gpt-4, gpt-3.5-turbo (default: gpt-4)",
                "validators": [],
            },
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
            "action": {
                "type": "string",
                "required": True,
                "description": "Acción: estimate, budget, report",
                "validators": ["enum:estimate,budget,report"],
            },
            "project": {
                "type": "string",
                "required": False,
                "description": "Proyecto",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": [],
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
        "example": 'python vault_requirement_save.py --project "mi-api" --title "Auth" --description "Login de usuario" --type "functional" --priority "high"',
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
            "name": {
                "type": "string",
                "required": True,
                "description": "Nombre del test",
                "validators": ["not_empty"],
            },
            "type": {
                "type": "string",
                "required": True,
                "description": "Tipo: unit, integration, e2e",
                "validators": ["enum:unit,integration,e2e"],
            },
            "description": {
                "type": "string",
                "required": True,
                "description": "Descripción del test",
                "validators": [],
            },
            "coverage": {
                "type": "string",
                "required": False,
                "description": "Cobertura esperada",
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
            "name": {
                "type": "string",
                "required": True,
                "description": "Nombre del runbook",
                "validators": ["not_empty"],
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
        "example": 'python vault_runbook_save.py --project "mi-api" --title "Deploy" --trigger "manual" --category "deploy" --steps "1. Build"',
        "related": ["vault_runbook_log", "vault_incident_save"],
    },
    "vault_runbook_log": {
        "name": "vault_runbook_log",
        "script": "vault_runbook_log.py",
        "group": "Runbooks",
        "purpose": "Registra ejecución de runbook.",
        "params": {
            "runbook": {
                "type": "string",
                "required": True,
                "description": "Nombre del runbook",
                "validators": [],
            },
            "status": {
                "type": "string",
                "required": True,
                "description": "Status: success, failure, partial",
                "validators": ["enum:success,failure,partial"],
            },
            "output": {
                "type": "string",
                "required": False,
                "description": "Output de la ejecución",
                "validators": [],
            },
        },
        "guards": [],
        "side_effects": ["Actualiza log del runbook"],
        "example": 'python vault_runbook_log.py --path "13_Runbooks/deploy.md" --outcome "success"',
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
            "description": {
                "type": "string",
                "required": True,
                "description": "Descripción",
                "validators": ["min_length:20"],
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
            "name": {
                "type": "string",
                "required": True,
                "description": "Nombre del SLO",
                "validators": ["not_empty"],
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
            "description": {
                "type": "string",
                "required": True,
                "description": "Descripción del release",
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
            "probability": {
                "type": "string",
                "required": True,
                "description": "Probabilidad: low, medium, high",
                "validators": ["enum:low,medium,high"],
            },
            "impact": {
                "type": "string",
                "required": True,
                "description": "Impacto: low, medium, high, critical",
                "validators": ["enum:low,medium,high,critical"],
            },
            "description": {
                "type": "string",
                "required": True,
                "description": "Descripción",
                "validators": ["min_length:20"],
            },
            "mitigation": {
                "type": "string",
                "required": False,
                "description": "Mitigación propuesta",
                "validators": [],
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
            "data_type": {
                "type": "string",
                "required": True,
                "description": "Tipo de dato sensible",
                "validators": [],
            },
            "classification": {
                "type": "string",
                "required": True,
                "description": "Clasificación: public, internal, confidential, restricted",
                "validators": ["enum:public,internal,confidential,restricted"],
            },
            "description": {
                "type": "string",
                "required": True,
                "description": "Descripción del dato",
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
            "source": {
                "type": "string",
                "required": True,
                "description": "Vault o carpeta fuente",
                "validators": [],
            },
            "target": {
                "type": "string",
                "required": True,
                "description": "Carpeta destino",
                "validators": [],
            },
            "mapping": {
                "type": "string",
                "required": False,
                "description": "Mapeo de rutas en JSON",
                "validators": ["valid_json"],
            },
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
            "migration_id": {
                "type": "string",
                "required": True,
                "description": "ID de la migración a revertir",
                "validators": [],
            },
            "dry_run": {
                "type": "boolean",
                "required": False,
                "description": "Simular sin aplicar",
                "validators": [],
            },
        },
        "guards": ["Confirmar antes de revertir"],
        "side_effects": ["Revierte archivos migrados"],
        "example": 'python vault_migrate_rollback.py --report_path "19_Audits/migrations/2026-06-24-001.json"\npython vault_migrate_rollback.py --report_path "19_Audits/migrations/2026-06-24-001.json" --confirm "yes"',
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
            "type": {
                "type": "string",
                "required": True,
                "description": "Tipo: book, article, website, paper",
                "validators": ["enum:book,article,website,paper"],
            },
            "authors": {
                "type": "string",
                "required": True,
                "description": "Autores separados por coma",
                "validators": [],
            },
            "year": {
                "type": "string",
                "required": True,
                "description": "Año de publicación",
                "validators": [],
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
            "vault_root": {
                "type": "string",
                "required": False,
                "description": "Ruta al vault (default: VAULT_ROOT env)",
                "validators": [],
            },
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
    "Salud del Vault": ["vault_audit", "vault_validate", "vault_graph", "vault_graph_merge", "vault_graph_inspect"],
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
    "Vista del Proyecto": ["vault_project_status", "vault_project_overview"],
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
    "Tests": ["vault_test_save"],
    "IA Governance": ["vault_ai_decision"],
    "Change Log": ["vault_change_log"],
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
        "vault_noop_audit",
        "vault_smoke",
        "vault_voice",
        "vault_servicio",
        "vault_blueprint",
        "vault_norms_coherence",
    ],
    "Producción/SRE": ["vault_incident_save", "vault_slo_save"],
    "Release": ["vault_release_save"],
    "Riesgos/Calidad": ["vault_risk_save", "vault_privacy_save", "vault_ncr_save"],
    "Bootstrap": ["vault_init", "vault_onboard"],
    "Corrección Automática": ["vault_fix_brackets", "vault_graph_fix", "vault_frontmatter_heal"],
    "Versionado": ["vault_standard_upgrade"],
    "Gestión de Carpetas": ["vault_folder_registry"],
    "Memoria de Contexto": [
        "vault_preferences",
        "vault_query_parse",
        "vault_subgraph",
        "vault_context_pack",
        "vault_ingest",
    ],
    # Grupo 36 (v39) — el ciclo del defecto y la retención sin borrado. Ambas
    # secciones salen de medir el parque real, no de un diseño a priori.
    "Defectos y Cuarentena": [
        "vault_bug_save",
        "vault_quarantine",
    ],
    # Grupo 37 (v39.4) — las capacidades que un agente descubre e invoca por
    # nombre. Existían desde v36 en `.claude/skills/` y en `docs/SKILLS.md`,
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
def argparse_params(script: str) -> Dict[str, Dict[str, Any]]:
    """Params reales de un script, leídos de sus `add_argument` largos."""
    import ast

    ruta = Path(__file__).resolve().parent / script
    if not script or not ruta.is_file():
        return {}
    try:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return {}

    params: Dict[str, Dict[str, Any]] = {}
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.Call) and getattr(nodo.func, "attr", "") == "add_argument"):
            continue
        largos = [
            a.value for a in nodo.args
            if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value.startswith("--")
        ]
        if not largos:
            continue  # posicional o flag corto: no se publica por MCP
        kw = {k.arg: k.value for k in nodo.keywords}

        def _const(nombre):
            v = kw.get(nombre)
            return v.value if isinstance(v, ast.Constant) else None

        accion, nargs = _const("action"), _const("nargs")
        if accion in ("store_true", "store_false"):
            tipo = "boolean"
        elif nargs in ("*", "+") or isinstance(nargs, int):
            tipo = "array"
        else:
            tipo = "string"

        opciones = []
        elecciones = kw.get("choices")
        if isinstance(elecciones, (ast.List, ast.Tuple)):
            opciones = [
                e.value for e in elecciones.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)
            ]

        params[largos[0][2:]] = {
            "type": tipo,
            "required": _const("required") is True,
            "description": _const("help") or "",
            "validators": [f"enum:{','.join(opciones)}"] if opciones else [],
        }
    return params


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
            if declarado.get("validators"):
                entrada["validators"] = declarado["validators"]
        salida[nombre] = entrada
    return salida


def _convert_to_json_schema(py_tool: Dict[str, Any]) -> Dict[str, Any]:
    """Convierte una entrada de TOOLS_CATALOG al formato inputSchema del JSON."""
    schema = {"type": "object", "properties": {}, "required": []}
    for pname, pinfo in reconciled_params(py_tool).items():
        prop = {"type": "string", "description": pinfo.get("description", "")}
        if pinfo.get("required"):
            schema["required"].append(pname)
        if "enum" in str(pinfo.get("validators", [])) or any(v.startswith("enum:") for v in pinfo.get("validators", [])):
            for v in pinfo.get("validators", []):
                if v.startswith("enum:"):
                    prop["enum"] = v.replace("enum:", "").split(",")
        schema["properties"][pname] = prop
    if not schema["required"]:
        del schema["required"]
    return schema


def sync_to_json(output_path: Optional[str] = None) -> str:
    """Exporta TOOLS_CATALOG + GROUPS al formato JSON canónico.
    
    Si output_path es None, se guarda junto a este script como tools-catalog.json.
    Retorna la ruta del archivo generado.
    """
    import json, os

    if output_path is None:
        # Catálogo canónico: mcp/nodejs/tools-catalog.json (consumido por el MCP server)
        output_path = os.path.join(
            os.path.dirname(__file__), "..", "mcp", "nodejs", "tools-catalog.json"
        )

    tools_json = {}
    for name, tool in sorted(TOOLS_CATALOG.items()):
        tools_json[name] = {
            "name": tool["name"],
            "description": tool["purpose"],
            "group": tool.get("group", ""),
            "script": tool.get("script", ""),
            "inputSchema": _convert_to_json_schema(tool),
            "guards": tool.get("guards", []),
            "side_effects": tool.get("side_effects", []),
        }
        if tool.get("related"):
            tools_json[name]["related"] = tool["related"]

    catalog = {
        "tools": tools_json,
        "groups": GROUPS,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return output_path


def check_sync(json_path: Optional[str] = None) -> Dict[str, Any]:
    """Compara el JSON existente contra TOOLS_CATALOG + GROUPS actuales.
    
    Retorna dict con: {ok: bool, diffs: [str], missing_in_json: [str], missing_in_py: [str]}
    """
    import json, os

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

        py_guard_count = len(TOOLS_CATALOG[name].get("guards", []))
        js_guard_count = len(existing["tools"][name].get("guards", []))
        if py_guard_count != js_guard_count:
            result["ok"] = False
            result["diffs"].append(f"{name}: guard count differs (py={py_guard_count}, js={js_guard_count})")

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
            problema("group_divergente", f"{nombre}: {entrada.get('group')!r} ≠ {grupo!r}")
        esperado = gid_por_grupo.get(grupo) if grupo else None
        if esperado is not None and entrada.get("group_id") != esperado:
            problema(
                "group_id_divergente",
                f"{nombre}: {entrada.get('group_id')} ≠ {esperado} (Grupo de scripts/README.md)",
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
    # en el checklist de cierre de `CLAUDE.md`.
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
    # Se lee el `.mjs` porque es lo que se ejecuta; una lista paralela en Python
    # sería el mismo defecto que la norma persigue.
    servidor = Path(__file__).resolve().parent.parent / "mcp" / "nodejs" / "vault-mcp-server.mjs"
    result["js_native"] = []
    if servidor.is_file():
        m = re.search(
            r"const JS_NATIVE_TOOLS = new Set\(\[(.*?)\]\)",
            servidor.read_text(encoding="utf-8"), re.S,
        )
        if m is None:
            problema("js_native_ilegible", f"no se pudo leer JS_NATIVE_TOOLS de {servidor.name}")
        else:
            nativas = sorted(set(re.findall(r'"(vault_[a-z0-9_]+)"', m.group(1))))
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
        if not reales:
            continue  # sin argparse legible no hay contra qué comparar
        result["tools_checked"] += 1
        publicados = (entrada.get("inputSchema") or {}).get("properties", {})
        sobran = [p for p in publicados if p not in reales]
        if sobran:
            result["ok"] = False
            result["problems"].append({
                "tool": nombre,
                "problem": f"params que la CLI rechaza: {', '.join(sorted(sobran))}",
                "fix": "python scripts/vault_mcp_catalog.py --sync",
            })
    return result


def main():
    parser = argparse.ArgumentParser(description="Vault MCP Catalog — sincronizar con JSON canónico")
    parser.add_argument("--sync", action="store_true", help="Generar tools-catalog.json desde PY")
    parser.add_argument("--check", action="store_true", help="Verificar que JSON está en sync con PY")
    parser.add_argument("--stats", action="store_true", help="Mostrar estadísticas del catálogo")
    parser.add_argument("--output", type=str, default=None, help="Ruta de salida para --sync")
    parser.add_argument("--json", type=str, default=None, help="Ruta del JSON para --check")
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
        result = check_params()
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
