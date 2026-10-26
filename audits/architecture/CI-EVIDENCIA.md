# Evidencia de CI (QA-RC-04) — lo comprobado y lo que falta

**SHA del candidato:** `31dfa462e87f5dcdb703e649e840e826a136ba50`
**Método:** API de GitHub (`gh api`) y `gh run list`. Sin acciones
administrativas, sin cancelar ni relanzar runs.

## 1. Configuración comprobada

| Elemento | Valor observado | Fuente |
|---|---|---|
| Workflow | `Vault CI` (`.github/workflows/vault-ci.yml`), `state: active` | `GET /actions/workflows` |
| Eventos | `pull_request` y `push` hacia `main`/`master` | fichero del workflow |
| Matriz | 3 SO (`ubuntu`, `windows`, `macos`) × Python 3.9–3.12, en "Validate Vault Spec" y "Product gates (wheel)", más "Lint Python" y un job de SBOM | fichero del workflow |
| Acciones habilitadas | `enabled: true`, `allowed_actions: all` | `GET /actions/permissions` |
| Visibilidad del repo | `public` | `GET /repos/...` |
| Runners autoalojados | `total_count: 0` (el repo no usa runners propios) | `GET /actions/runners` |
| Estado del proveedor | `All Systems Operational`, componente Actions `operational` | `githubstatus.com/api/v2` |
| Facturación | `GET /user/settings/billing/actions` → **404** (sin permiso de administración) | API de GitHub |

## 2. Runs del candidato

| Run ID | SHA | Estado | Conclusión | Jobs |
|---|---|---|---|---|
| `40252807573` | `31dfa46` | `queued` | — | 25, ninguno iniciado |
| `40245754464` | `5a8395c` | `queued` | — | 25 |
| `40245587377` | `532f19e` | `queued` | — | 25 |
| `40244460688` | `29c1a15` | `queued` | — | 25 |
| `40242263586` | `001120c` | `queued` | — | 25 |

En todos: `status: queued`, `runner_id: 0`, `started_at` fijado y
`completed_at` nulo, `steps: []`. Los jobs **existen** y esperan runner: el
workflow corre y encola; lo que no ocurre es el arranque del job.

## 3. Qué se deduce y qué NO

**Se deduce (con evidencia):**
- El workflow está habilitado, es válido y produce jobs: no es un YAML roto ni
  un evento que no dispara.
- Las etiquetas pedidas (`ubuntu-latest`, `windows-latest`, `macos-latest`) son
  las estándar de GitHub.
- El repositorio es público: los runners alojados no dependen de minutos
  pagados.
- GitHub no reporta incidencia.
- **Ningún** run de la ventana ha concluded: no hay un PASS anterior que
  reutilizar, ni un FAIL que explique la cola.

**NO se deduce (y por eso no se afirma):**
- Que la causa sea el límite de gasto o el método de pago: el único endpoint
  que lo diría responde 404 a este token. **Es una hipótesis, no un
  diagnóstico.**
- Que sea la cuota de jobs concurrentes de la cuenta: es plausible (25 jobs ×
  varios runs) pero no está medido.
- Que sea una política de organización: no hay datos de organización.

## 4. Acción concreta que necesita el propietario

En **Settings → Billing & licensing → Actions** de la cuenta:

1. Revisar **límite de gasto**, **método de pago** y **estado de la cuenta**.
2. Si la cuenta pertenece a una organización, revisar **Organization →
   Settings → Actions**: runners permitidos, políticas de concurrencia y
   acceso de la organización a runners alojados.
3. Comprobar si el repositorio está en una lista que restrinja Actions.

Sin ese dato, la atribución de la causa es especulación y este documento no la
hace.

## 5. Lo que sí se ha acreditado en local (complementario, **no** sustituto)

| Comprobación | Resultado |
|---|---|
| Recorrido de terceros sobre wheel instalada | 27/27 |
| Paridad CLI/MCP | 5/5 CONFORME, 97 tools MCP, AP-40 exit 0 |
| Operaciones destructivas con rollback | 23 pruebas, verificación por hash |
| Suite completa (Windows) | 6270 passed / 13 skipped / 0 failed |
| 26 puertas | 26/26 |

Esto demuestra **funcionamiento local**, no la matriz multipataforma: la
matriz la ejecuta la CI. QG-07 permanece **BLOCKED** con `CI_PENDIENTE`.

## 6. Qué NO se ha hecho (y por qué)

- No se ha cancelado ni relanzado ninguna ejecución.
- No se ha modificado ningún workflow ni configuración administrativa.
- No se ha generado runs nuevos con commits cosméticos.
- No se ha atribuido PASS a ningún run en cola.
