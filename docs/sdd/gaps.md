# Gaps — Brechas Detectadas

> Lista priorizada de brechas detectadas durante la generación del SDD.
> Esta lista se actualiza con cada ejecución de la skill.
> Última actualización: 2026-06-28

---

## ES

### Generado: 2026-06-28T01:44:41.000Z

### Drift detectado

- **Versión del vault:** v36.0
- **Normas faltantes:** 0
- **Warnings:** 0

### Estado de FASE 0 (completada)

Los 7 fixes críticos fueron aplicados en esta sesión:

- ✅ A2/A3: AP-24, AP-25 registrados en NORM_CATALOG
- ✅ A1: Versión triple sincronizada en v36.0
- ✅ C1/C2: Trace files unificados en `00_System/`
- ✅ B1: atomic_write_text limpia temp file en error
- ✅ F1/F2: CI workflow + 132 tests passing
- ✅ I1/I5: Secret scanning integrado en atomic_write_text
- ✅ D1: Migration path v34 → v35 → v36 documentado

### Hallazgos pendientes (85+ documentados)

#### Críticos — siguientes fases

| ID | Descripción | Esfuerzo |
|---|---|---|
| D2 | Hotfix path undocumented | Bajo |
| D3 | `vault_init --clean` no hace backup antes de wipe | Bajo |
| G1 | No guidance para concurrent users (multi-user) | Medio |
| G2 | No fork-and-modify scenario guidance | Medio |
| H1 | No `vault_undo` tool (recovery desde `.history/`) | Medio |
| H2 | `--dry-run` solo en 12 de 94 scripts | Medio |
| J1 | No plugin/extension system | Alto |
| J3 | NORM_CATALOG no es extensible externamente | Alto |
| K3 | 25+ implementaciones duplicadas de `slugify()` | Medio |
| K4 | `utcnow()` duplicado en 15+ scripts | Bajo |

#### Medios — backlog

| ID | Descripción |
|---|---|
| D4 | Version detection por folder heuristic es frágil |
| D5 | No hay forma de descubrir upgrades disponibles sin probar |
| D7 | No consumer-side schema version vs spec version |
| E1 | Bilingual section descriptions (mix ES/EN) |
| E2 | Folder numbering vs spec docs discrepancy |
| G3 | Git merge conflicts en vault files unresolved |
| G4 | `vault-backups/` sin rotation policy |
| H3 | No `--quiet` flag |
| H4 | Error messages often non-actionable |
| H6 | Missing common commands (vault_delete, vault_rename, etc.) |
| J4 | SUBFOLDERS registry hardcoded |
| J5 | Tool group assignment is hardcoded |

#### Bajos — nice-to-have

| ID | Descripción |
|---|---|
| D6 | Migrations dict has duplicate keys |
| D8 | `vault_init --target` bypasses MIGRATIONS dict |
| E3 | vault_init y vault-hub dicen 17 folders, crean 18 |
| E4 | Subfolder naming inconsistent |
| E5 | tools_count inconsistente (69/61/53) |
| E6 | vault_init README "85 archivos" (actual 95+) |
| G5 | No concept of "remote vault" |
| G6 | vault_init --clean no backup before wipe |
| H7 | Onboarding ~10 commands |
| H8 | No vault_lint pre-commit hook |
| H9 | Token-counter syntax errors silently absorbed |
| H10 | No JSON schema validation |
| I2-I9 | Resto de issues de seguridad |
| J2 | Override pattern undocumented |
| J6 | vault_mcp.py is meta-tool but undocumented |
| J7 | No extension points for frontmatter validators |
| K1-K10 | Code quality issues |

### Acciones manuales requeridas

1. Revisar y completar los schemas canónicos en [06-documentation-methodology.md](./06-documentation-methodology.md).
2. Revisar y aprobar los state machines en [01-state-machines.md](./01-state-machines.md).
3. Validar la reference matrix en [05-reference-matrix.md](./05-reference-matrix.md).
4. Cerrar los hallazgos críticos arriba listados en próximas sesiones.
5. Ejecutar `vault_sdd_init.py --bilingual --force` cuando se hagan cambios para regenerar.

### Métricas de la sesión 2026-06-28

- Tests passing: 147 (132 nuevos en esta sesión + 15 originales)
- Drift status: PASS
- Versión sincronizada: v36.0
- Archivos SDD generados: 14
- Líneas totales: ~1290

---

## EN

### Generated: 2026-06-28T01:44:41.000Z

### Detected drift

(See ES section above.)

### PHASE 0 status (completed)

The 7 critical fixes were applied in this session.

(See list above in ES section.)

### Pending findings (85+ documented)

(See tables above in ES section.)

### Required manual actions

(See list above in ES section.)

### Session metrics 2026-06-28

(See metrics above in ES section.)