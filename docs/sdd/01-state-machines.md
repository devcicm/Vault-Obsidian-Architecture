# State Machines -- Máquinas de Estado

> Documento bilingüe. ES arriba, EN abajo.
> Bilingual document. ES above, EN below.

---

## ES

### Catálogo maestro de lifecycles

| Lifecycle | Estados | Tool |
|---|---|---|
| **Nota (Note)** | active / archived / deleted | vault_change_log |
| **Patrón (Pattern)** | planificado / en_progreso / implementado / deprecado / refactoring | vault_pattern_save |
| **Requisito (Requirement)** | draft / reviewed / approved / implemented / verified / obsolete | vault_requirement_save |
| **Test** | not_run / pass / fail / blocked / skip | vault_test_save |
| **Runbook execution** | success / failed / partial | vault_runbook_log |
| **Incidente (Incident)** | detected / investigating / identified / mitigating / resolved / closed / post-mortem | vault_incident_save |
| **SLO burn** | healthy / 1h-burn / 6h-burn / 30d-burn / breached | vault_slo_save |
| **Risk treatment** | accept / mitigate / transfer / avoid | vault_risk_save |
| **NCR** | open / closed | vault_ncr_save |
| **Backup** | active / superseded | (manual) |
| **Propagation pending** | pending / reviewed | vault_propagate |
| **Tool lifecycle** | active / deprecated / internal / meta / removed | tool-spec.json |
| **Standard version** | v19 → v20 → … → v36 | vault_standard_upgrade |

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
| **Backup** | active / superseded | (manual) |
| **Propagation pending** | pending / reviewed | vault_propagate |
| **Tool lifecycle** | active / deprecated / internal / meta / removed | tool-spec.json |
| **Standard version** | v19 → v20 → … → v36 | vault_standard_upgrade |

### Unified vocabulary

- Canonical names are those listed above.
- Common aliases (EN/ES) are accepted on write but normalized on audit.
