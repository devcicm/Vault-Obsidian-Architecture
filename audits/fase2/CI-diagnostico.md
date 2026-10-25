# Diagnostico de la CI — cola permanente (GOAL D)

**Fecha:** 2026-10-25 · **Repositorio:** `devcicm/Vault-Obsidian-Architecture`
**Conclusión:** la cola **no** es un problema de configuracion del workflow ni de
runners autoalojados. Es un bloqueo del lado de la cuenta que el ejecutor no
puede modificar. Requiere intervencion del propietario.

## Evidencia recogida (API de GitHub, no suposiciones)

| Comprobacion | Comando | Resultado |
|---|---|---|
| Workflow activo | `gh api .../actions/workflows` | 1 workflow, `state: active` |
| Acciones habilitadas | `gh api .../actions/permissions` | `enabled: true`, `allowed_actions: all` |
| Visibilidad | `gh api repos/...` | `private: false`, `visibility: public` |
| Runners autoalojados | `gh api .../actions/runners` | `total_count: 0` (normal en un repo que solo usa runners alojados) |
| Estado de GitHub | `githubstatus.com/api/v2/summary.json` | `All Systems Operational`, componente Actions `operational` |
| Historial de runs | `gh run list --limit 12` | **12/12 en `queued`**, ninguno completado en la ventana |
| Jobs del run 40192932202 | `gh api .../runs/40192932202/jobs` | 25 jobs, todos `queued`, `runner_id: 0`, sin pasos, con `started_at` y sin `completed_at` |
| Etiquetas pedidas | idem | `ubuntu-latest`, `windows-latest`, `macos-latest` — estandar de GitHub |
| Facturacion | `gh api user/settings/billing/actions` | `404 Not Found` (sin permiso de administracion) |

## Lectura de los datos

1. Los jobs existen, estan creados y esperan runner (`runner_id: 0`, sin pasos).
   Eso descarta un YAML invalido o un evento que no dispara: el workflow corre y
   encola.
2. Las etiquetas son las estandar. El repositorio es **publico**, asi que los
   runners alojados son gratuitos y no dependen de minutos pagados.
3. GitHub no reporta incidencia.
4. Ningun run de la ventana ha completado **nunca**, ni uno anterior.

Con esas cuatro piezas, la causa que queda es una restriccion de la cuenta o de
la organizacion (limite de gasto, metodo de pago, cuenta marcada, politica de la
organizacion o cuota de runners concurrentes agotada por el propio backlog).
**Ninguna de esas se puede diagnosticar ni corregir con los permisos
disponibles**: el endpoint de facturacion responde 404 al token del ejecutor.

## Que NO se ha hecho (y por que)

- No se han cancelado runs ni relanzado ejecuciones para "probar".
- No se ha tocado `.github/workflows/vault-ci.yml`.
- No se han creado runs nuevos con commits cosmeticos.
- No se ha atribuido PASS a ningun run en `queued`.

## Intervencion que se necesita del propietario

Una sola, en el panel de la cuenta (no en el codigo):

1. Revisar **Settings → Billing → Actions**: limite de gasto, metodo de pago y
   estado de la cuenta.
2. Si la cuenta es una organizacion, revisar **Organization → Settings →
   Actions → Runner groups / Policies**.
3. Confirmado el desbloqueo, no hace falta tocar nada mas: el proximo push a la
   rama dispara el workflow y la matriz completa (3 SO × 4 versiones de Python,
   mas lint, SBOM, JSON-RPC y wheel) se ejecutara sola.

## Consecuencia sobre los Quality Gates

`QG-07` queda **BLOCKED** con `CI_PENDIENTE` segun la politica de R03, y el
colector (`audits/fase2/colector_qg.py`) devuelve `sin_run` para el SHA del
candidato. No se declara PASS.

## Evidencia alternativa que si se puede producir sin CI

- Matriz local de Windows sobre la wheel instalada (Python disponible).
- Contenido de wheel y sdist inspeccionado, con hash.
- Auditoria de dependencias con `pip-audit` en un entorno aislado.
- Recorrido de tercero desde una instalacion limpia fuera del checkout.

Todo eso es **evidencia complementaria**, no sustituto de QG-07.
