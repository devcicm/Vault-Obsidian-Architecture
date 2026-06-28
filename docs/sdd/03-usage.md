# Usage Guide -- Guía de Uso

> ES arriba, EN abajo.

---

## ES

### 1. Protocolo de sesión

1. Inicializar: `vault_init` (crea estructura)
2. Crear notas: `vault_write --folder <X> --title <T> --content <C>`
3. Auditar: `vault_audit`
4. Reindexar: `vault_reindex --graph`
5. Backup: `vault_backup`

### 2. Contrato de frontmatter

Required: `id`, `title`, `createdAt`, `updatedAt`, `agent`
CIA: enum values `high`, `medium`, `low`
`norm_refs`: auto-embedded por folder + content matching

### 3. Wiki-links

- Stem-only: `[[note-name]]`
- AP-22: no `[[]]` vacíos
- AP-24: brackets balanceados
- AP-21: NO `[[folder/note]]`

### 4. Index / Search

- `99_Index/search-index.json` keyed por `id` (estable)
- `99_Index/hash-index.json` keyed por `id`, hash excluye `updatedAt`

### 5. Backup / Restore

- `vault_backup` → snapshot completo + Merkle root
- `vault_restore --backup <name>` → copia + `vault_reindex --graph`

---

## EN

### 1. Session protocol

(See ES section above.)

### 2. Frontmatter contract

(See ES section above.)

### 3. Wiki-links

(See ES section above.)

### 4. Index / Search

(See ES section above.)

### 5. Backup / Restore

(See ES section above.)
