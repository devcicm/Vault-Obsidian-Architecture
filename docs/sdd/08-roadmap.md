# Roadmap -- Hoja de Ruta

> Hallazgos pendientes priorizados. Severity-based.
> Pending findings prioritized. Severity-based.

---

## ES

Total de hallazgos documentados en auditoría 2026-06-28: 85+

### Críticos (en curso)

- ✅ A2/A3: AP-24, AP-25 registrados en NORM_CATALOG
- ✅ A1: Versión triple sincronizada en v36.0
- ✅ B1: atomic_write_text temp leak fixed
- ✅ C1/C2: Trace files unificados en 00_System/
- ✅ F1/F2: CI + 132 tests passing
- ✅ I1/I5: Secret scanning integrado en atomic_write_text

### Pendientes (próximas fases)

| ID | Severidad | Descripción |
|---|---|---|
| D2 | HIGH | Hotfix path undocumented |
| D3 | HIGH | vault_init --clean no backup before wipe |
| D4 | MEDIUM | Version detection by folder heuristic is fragile |
| G1 | HIGH | No guidance for concurrent users |
| G2 | HIGH | No fork-and-modify scenario guidance |
| H1 | HIGH | No vault_undo tool |
| H2 | HIGH | --dry-run only on 12 of 94 scripts |
| H6 | MEDIUM | Missing common commands (vault_delete, vault_rename, etc.) |
| J1 | HIGH | No plugin/extension system |
| J3 | HIGH | NORM_CATALOG not externally extendable |
| K3 | HIGH | Two slugify implementations (25+ duplicates) |
| K4 | HIGH | utcnow duplicated in 15+ scripts |

---

## EN

Total findings documented in audit 2026-06-28: 85+

### Critical (in progress)

(See list above in ES section.)

### Pending (next phases)

(See table above in ES section.)
