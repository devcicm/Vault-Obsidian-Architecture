"""Hoja canónica de clasificación de tools del estándar."""

from typing import Any, Dict

NATURALEZAS: Dict[str, Dict[str, Any]] = {
    "construccion": {
        "titulo": "Construcción y diseño del vault",
        "actua_sobre": "la estructura: carpetas, índices, ubicación y forma del vault",
        "distincion": (
            "Le da forma al continente, no al contenido. Si la tool decide **dónde** "
            "vive una nota o qué carpetas existen, es construcción aunque acabe "
            "escribiendo markdown."
        ),
        "tools": [
            "vault_folder_registry", "vault_init", "vault_master_index",
            "vault_merge", "vault_migrate_docs", "vault_migrate_rollback",
            "vault_move", "vault_onboard", "vault_reindex", "vault_sanacion",
            "vault_sdd_init", "vault_section_index", "vault_standard_upgrade",
        ],
    },
    "documentacion": {
        "titulo": "Documentación",
        "actua_sobre": "el contenido: lo que la nota dice",
        "distincion": (
            "Captura conocimiento en notas. Si la tool decide **qué dice** una nota "
            "y no dónde vive, es documentación. Es la capacidad de memoria "
            "propiamente dicha: sin estas tools el vault sería un esqueleto vacío."
        ),
        "tools": [
            "vault_ai_decision", "vault_append", "vault_bibliography_save",
            "vault_bug_save", "vault_change_log", "vault_code_map",
            "vault_code_module", "vault_code_relation", "vault_diagram_export",
            "vault_diagram_save", "vault_env_matrix", "vault_env_save",
            "vault_flow_save", "vault_incident_save", "vault_infra_map",
            "vault_infra_save", "vault_ingest", "vault_knowledge_save",
            "vault_log_error", "vault_ncr_save", "vault_pattern_save",
            "vault_privacy_save", "vault_project_overview", "vault_project_status",
            "vault_relation_add", "vault_release_save", "vault_requirement_save",
            "vault_risk_save", "vault_runbook_log", "vault_runbook_save",
            "vault_slo_save", "vault_test_save", "vault_timeline", "vault_write",
        ],
    },
    "custodia": {
        "titulo": "Custodia",
        "actua_sobre": "lo ya escrito: corrección, integridad y durabilidad",
        "distincion": (
            "No decide qué dice ni dónde vive: comprueba que siga siendo cierto y "
            "recuperable. Audits, validadores, auto-fixes, backups y cuarentena. "
            "Meterlas en construcción —porque «arreglan»— o en documentación "
            "—porque «escriben»— es lo que hace que un agente llame a un auto-fix "
            "cuando quería capturar contenido."
        ),
        "tools": [
            "vault_audit", "vault_backup", "vault_backup_base64",
            "vault_backup_list", "vault_code_sync", "vault_delta",
            "vault_delete", "vault_drift_detect", "vault_fix_brackets",
            "vault_frontmatter_heal", "vault_fuente_unica", "vault_fundamentals",
            "vault_graph_fix", "vault_graph_inspect", "vault_graph_merge",
            "vault_history_compact", "vault_mermaid_check", "vault_propagate",
            "vault_quality_check", "vault_quality_dashboard", "vault_quarantine",
            "vault_qa_save", "vault_restore",
            "vault_restore_base64", "vault_security_scan", "vault_tags",
            "vault_undo", "vault_validate",
        ],
    },
    "consulta": {
        "titulo": "Consulta",
        "actua_sobre": "nada — devuelve lo que ya hay",
        "distincion": (
            "Sin superficie de escritura sobre las notas. Es la única naturaleza que "
            "se puede correr sobre un vault ajeno sin pedir permiso, y por eso "
            "conviene tenerla nombrada y no deducida (regla 7)."
        ),
        "tools": [
            "vault_context_pack", "vault_code_query", "vault_diff", "vault_graph",
            "vault_impact", "vault_knowledge_get", "vault_list",
            "vault_model_profile", "vault_pattern_list", "vault_preferences", "vault_query_parse",
            "vault_read", "vault_search", "vault_subgraph", "vault_token_counter",
            "vault_token_service", "vault_tokens",
        ],
    },
    "meta_estandar": {
        "titulo": "Meta-estándar",
        "actua_sobre": "este repositorio, no el vault de nadie",
        "distincion": (
            "No abre ningún vault de usuario. Miden que el estándar cumpla lo que "
            "publica. Coincide exactamente con la capacidad `gobernanza_del_estandar`, "
            "y `check()` lo exige: si un día divergen, una de las dos clasificaciones "
            "está mintiendo."
        ),
        "tools": [
            "vault_arch", "vault_blame_audit", "vault_blueprint",
            "vault_changelog_check", "vault_code_tag", "vault_doc_counts",
            "vault_doc_staleness", "vault_doc_sync", "vault_error_contract",
            "vault_foreign_check", "vault_gate", "vault_noop_audit",
            "vault_norms", "vault_norms_coherence", "vault_criterios",
            "vault_ciclos", "vault_kernel", "vault_excepcion_declarada",
            "vault_recursos",
            # v40.31. Meta-estándar con un matiz que ninguna otra de esta lista
            # tiene: las demás miden el repo contra sus propios registros, y
            # esta lo mide contra lo que le promete a quien lo instala.
            "vault_produccion",
            "vault_servicio",
            "vault_smoke", "vault_voice",
            # v40.34. Infraestructura de mantenimiento del propio estándar:
            # regenera los artefactos derivados en el orden correcto.
            "vault_fix_all",
        ],
    },
}
