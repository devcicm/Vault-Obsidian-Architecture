# Metrics -- Métricas

> ES arriba, EN abajo.

---

## ES

### Métricas de salud del vault

| Métrica | Rango | Fuente | Significado |
|---|---|---|---|
| **healthScore** | 0-100 | vault_audit | Salud agregada del vault (penalizaciones) |
| **dqHealth.overall_dq_score** | 0-1 | vault_quality_check | Calidad de datos agregada |
| **dqHealth.notes_below_07** | int | vault_quality_check | Notas con DQ < 0.7 |
| **tag_health_score** | 0-100 | vault_audit | Salud del tag registry |
| **orphan_count** | int | vault_graph | Notas sin relaciones |
| **broken_link_count** | int | vault_audit --broken-links | Links a notas inexistentes |
| **mermaid_error_count** | int | vault_mermaid_check | Errores de sintaxis Mermaid |
| **render_error_count** | int | vault_render_check | Errores de render markdown (AP-26) |
| **idempotency_score** | 0-100 | (v36 nuevo) | Cobertura de file_lock + atomic_write |
| **trace_coverage** | % | (v36 nuevo) | % ops con trace entry |
| **secret_findings** | int | vault_secret_scan | Secretos detectados bloqueados |

### Umbrales recomendados

- healthScore >= 80: OK
- healthScore 50-79: warning
- healthScore < 50: critical

---

## EN

### Vault health metrics

(See table above in ES section.)

### Recommended thresholds

(See list above in ES section.)
