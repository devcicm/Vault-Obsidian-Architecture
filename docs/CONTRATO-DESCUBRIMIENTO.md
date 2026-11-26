<!-- propiedad: CARLOS IVAN CM · revisión: manual -->

# Contrato de descubrimiento del MCP

`vault_registry` y el recurso `vault://registry` conservan sus respuestas
habituales cuando el barrido termina sin errores. Si no se puede recorrer un
subárbol o inspeccionar un candidato, ambas superficies siguen publicando los
vaults que sí se encontraron y añaden `discovery_incomplete`; no presentan ese
conjunto parcial como un inventario completo.

## Respuesta

En una ejecución completa, el envelope mantiene `ok` y `vaults` con los campos
existentes. En una ejecución incompleta, agrega:

```json
{
  "discovery_incomplete": {
    "traversal_failures": 1,
    "candidate_failures": 0,
    "truncated": false
  }
}
```

Los contadores se limitan a 100 por categoría. Si se supera ese límite,
`truncated` pasa a `true`. El diagnóstico no expone rutas, nombres de
directorios ni mensajes del sistema de archivos. Las entradas encontradas y
las ya registradas siguen disponibles; un barrido parcial no las elimina.

## Raíces opcionales

Una raíz de búsqueda configurada que no existe no es un fallo fatal ni marca el
resultado como incompleto. Otros errores de lectura sí se informan en el
resumen, mientras el servidor continúa con las raíces accesibles.

## Paridad con `VAULT_MASTER`, registro maestro y `.vault-path`

Para eliminar la divergencia entre Python (`vault/kernel/vault_home.py`,
`vault/kernel/raiz.py`, `vault/kernel/acceso_baules.py`) y el servidor MCP:

- **`VAULT_MASTER` (`~/.vault-master/`):** sus subdirectorios se registran por
  nombre propio (`agente`, `gestion`, `infraestructura-redes`, etc.) sin exigir
  prefijo `vault-`, con `origin: "master"` y la bandera `has_access_policy`
  indicando si existe `00_System/access-policy.json`.
- **Registro maestro (`<VAULT_MASTER>/registry.json`):** declara baúles
  externos en rutas personalizadas (p. ej. `B:\vault-dev-codex`), expuestos en
  `vault_registry` con `origin: "external"` y en `vault_init --list` bajo
  `external_vaults`.
- **Puntero `.vault-path`:** `detectVaultRoot()` resuelve `.vault-path` desde
  `VAULT_CLIENT_CWD` o el CWD actual antes de caer al fallback.
- **Modelo de tenencia e identidad:** **1 Baúl = 1 Tenant soberano** (silo
  físico en disco y Git). El intercambio entre baúles es **estrictamente de
  solo lectura (`AP-36`)** y **cerrado por defecto (*fail-closed*)** mediante
  `Principal(vault, role, project)` y `<baul-destino>/00_System/access-policy.json`.
