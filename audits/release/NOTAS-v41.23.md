Vault Obsidian Architecture **v41.23**: estándar y toolkit para dar a agentes LLM
memoria documental persistente, auditable y gobernada sobre Markdown plano.

## Instalación

```bash
pip install vault_obsidian_architecture-41.23-py3-none-any.whl
vault --help
vault mcp-path        # ruta del servidor MCP empaquetado (Node 18+)
```

Comprueba los ficheros contra `SHA256SUMS.txt`. El inventario de dependencias
y licencias va en `sbom.spdx.json` (SPDX).

## Alcance soportado

- **Windows y Linux**, Python **3.9–3.12**. Cada combinación la ejecuta la CI
  del SHA publicado.
- macOS **no se promete**: no tiene runner en la CI ni classifier.

## Límites declarados (autorización del propietario con condiciones, DEC-06)

- Capacidades que el recorrido E2E desde la wheel no ejerce: `plan`, `batch`,
  `--verify-integrity`, MCP por SSE/HTTP y la salida 130.
- Los controles de mantenimiento del estándar AP-40/42/43 devuelven
  `no_ejecutado` cuando se ejecutan desde una wheel limpia (I2-a pendiente). Es
  el comportamiento fail-closed: nunca devuelven un PASS falso.
- El servidor MCP por HTTP escucha solo en `127.0.0.1` y exige token. No es
  autenticación de red.

## Trazabilidad

El candidato, su evidencia (suite, puertas, E2E, CI) y las decisiones del
propietario están en `audits/fase2/CANDIDATO-RELEASE.yaml` y
`audits/handoff/ACTA-DECISIONES-PROPIETARIO-2026-10-28.md`.
