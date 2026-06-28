# Process Antipatterns -- Antipatrones de Proceso

> ES arriba, EN abajo.

---

## ES

### SP-01: Delete sin change_log

**Síntoma**: Nota eliminada que no aparece en `.change-log.json`.

**Prevención**: Antes de eliminar, llamar `vault_change_log --action deleted`.

### SP-02: Linkar sin verificar

**Síntoma**: `[[nombre]]` que apunta a nota inexistente.

**Prevención**: `vault_search(query='nombre')` antes de linkar.

### SP-03: Sin snapshot antes de operaciones masivas

**Síntoma**: Cambios sin backup previo, errores irreversibles.

**Prevención**: `vault_backup` antes de operaciones masivas.

### SP-04 (nuevo): Modificar .md directamente (v36)

**Síntoma**: Notas editadas fuera de `vault_write`, sin secret scan.

**Prevención**: Toda edición de `.md` debe pasar por `vault_write`.

### SP-05 (nuevo): Pre-commit sin CI gate (v36)

**Síntoma**: Cambios sin validación automática.

**Prevención**: `.github/workflows/vault-ci.yml` corre en cada PR.

---

## EN

### SP-01: Delete without change_log

(See ES section above.)

### SP-02: Linking without verification

(See ES section above.)

### SP-03: No snapshot before mass operations

(See ES section above.)

### SP-04 (new): Direct .md modification (v36)

(See ES section above.)

### SP-05 (new): Pre-commit without CI gate (v36)

(See ES section above.)
