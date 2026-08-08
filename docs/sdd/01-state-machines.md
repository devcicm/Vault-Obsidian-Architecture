# State Machines -- Máquinas de Estado

> Documento bilingüe. ES arriba, EN abajo.
> Bilingual document. ES above, EN below.

---

## ES

### Catálogo maestro de lifecycles

| Lifecycle | Estados | Tool |
|---|---|---|
| **Nota** | active / archived / deleted | vault_change_log |
| **Patrón** | planificado / en_progreso / implementado / deprecado / refactoring | vault_pattern_save |
| **Requisito** | draft / reviewed / approved / implemented / verified / obsolete | vault_requirement_save |
| **Test** | not_run / pass / fail / blocked / skip | vault_test_save |
| **Ejecución de runbook** | success / failed / partial | vault_runbook_log |
| **Incidente** | detected / investigating / identified / mitigating / resolved / closed / post-mortem | vault_incident_save |
| **Consumo de SLO** | healthy / 1h-burn / 6h-burn / 30d-burn / breached | vault_slo_save |
| **Tratamiento de riesgo** | accept / mitigate / transfer / avoid | vault_risk_save |
| **NCR** | open / closed | vault_ncr_save |
| **Backup** | active / superseded | vault_backup_list |
| **Propagación pendiente** | pending / reviewed | vault_propagate |
| **Ciclo de vida de una tool** | active / archived / internal | vault_mcp_catalog |
| **Versión del estándar** | v19 → … → v40.6 | vault_standard_upgrade |

### Vocabulario unificado

- Los nombres canónicos son los listados arriba.
- Aliases comunes (EN/ES) se aceptan en escritura pero se normalizan en auditoría.

---

## EN

### Master lifecycle catalog

| Lifecycle | States | Tool |
|---|---|---|
| **Note** | active / archived / deleted | vault_change_log |
| **Pattern** | planificado / en_progreso / implementado / deprecado / refactoring | vault_pattern_save |
| **Requirement** | draft / reviewed / approved / implemented / verified / obsolete | vault_requirement_save |
| **Test** | not_run / pass / fail / blocked / skip | vault_test_save |
| **Runbook execution** | success / failed / partial | vault_runbook_log |
| **Incident** | detected / investigating / identified / mitigating / resolved / closed / post-mortem | vault_incident_save |
| **SLO burn** | healthy / 1h-burn / 6h-burn / 30d-burn / breached | vault_slo_save |
| **Risk treatment** | accept / mitigate / transfer / avoid | vault_risk_save |
| **NCR** | open / closed | vault_ncr_save |
| **Backup** | active / superseded | vault_backup_list |
| **Propagation pending** | pending / reviewed | vault_propagate |
| **Tool lifecycle** | active / archived / internal | vault_mcp_catalog |
| **Standard version** | v19 → … → v40.6 | vault_standard_upgrade |

### Unified vocabulary

- Canonical names are those listed above.
- Common aliases (EN/ES) are accepted on write but normalized on audit.
