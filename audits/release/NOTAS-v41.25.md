Vault Obsidian Architecture **v41.25**: estándar y toolkit para dar a agentes LLM
memoria documental persistente, auditable y gobernada sobre Markdown plano.

> **Estado: candidato NO autorizado.** `release_authorized: false` en
> `audits/fase2/CANDIDATO-RELEASE.yaml`. Estas notas no se publican hasta que
> el propietario firme un acta para v41.25 y exista una CI en `success` sobre el
> mismo `product_sha` (QG-07). La DEC-06 fue para v41.23.

## Instalación

```bash
pip install vault_obsidian_architecture-41.25-py3-none-any.whl
vault --help
vault mcp-path        # ruta del servidor MCP empaquetado (Node 18+)
```

Comprueba los ficheros contra `SHA256SUMS.txt`. El inventario de dependencias
y licencias va en `sbom.spdx.json` (SPDX).

## Qué cambia

CN-05, un cuerpo un dueño: `vault_clones` (puerta 27) mide por AST las sombras y
los clones, se borran las sombras de `slugify`, `utcnow` y `parse_frontmatter`,
el layout del repo pasa a `vault/kernel/rutas.py` y la baseline de rutas baja de
175 a 16 sitios declarados. Detalle en el changelog del manifiesto.

## Qué se midió y con qué alcance

- **Suite:** 6501 tests, 6485 passed, 16 skipped, 0 failed, en **Windows 10,
  Python 3.14, `-n 4`**.
- **Puertas:** `vault_gate --strict` en verde dentro de QG-02.
- **E2E desde la wheel:** 27/27 pasos en venv limpio, en Windows.
- **Quality Gates:** QG-00..QG-06 PASS (`audits/fase2/recibos-R25-533e424/`).
  **QG-07 NOT_RUN**: no hay run de CI para este SHA.
- **Regla 7:** contraste contra un vault ajeno (`vault-ans`, en solo lectura),
  sin anomalías nuevas respecto al contraste del 2026-10-16
  (`docs/contrastes/ultimo-contraste.json`).

## Límites declarados

- **Linux y Python 3.9–3.12 no se midieron en esta ronda**: los promete el
  classifier, pero los ejerce la CI, que no ha corrido para este SHA.
- **Crash bajo `-n auto`:** el worker `gw1` se cae en
  `tests/test_noop_audit.py::test_el_banco_sigue_viendo_trabajo_real` (3 de 3
  veces). Pasa solo y con `-n 4`. La causa **no está determinada**.
- **QG-02** se obtuvo con el directorio ajeno `vault-backups` (de junio, dos
  niveles sobre el vault) apartado durante la corrida; sin apartarlo, AP-36
  lo señala. Es un hallazgo de entorno, no de producto.
- **QG-04:** `pip-audit` encontró vulnerabilidades solo en el `pip` del venv de
  auditoría, ya actualizado; el producto no se pudo auditar contra PyPI por no
  estar publicado.
- Capacidades que el E2E no ejerce: `plan`, `batch`, `--verify-integrity`, MCP
  por SSE/HTTP y la salida 130.
- Los controles AP-40/42/43 devuelven `no_ejecutado` desde una wheel limpia
  (fail-closed, nunca un PASS falso).
- El servidor MCP por HTTP escucha solo en `127.0.0.1` y exige token. No es
  autenticación de red.
- macOS no se promete.

## Trazabilidad

Candidato, evidencia y estado de gobierno: `audits/fase2/CANDIDATO-RELEASE.yaml`.
El candidato anterior (v41.23, autorizado en su día) se conserva en su bloque
`candidato_v41_23`.
