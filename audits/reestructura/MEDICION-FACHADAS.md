# Medición de las tres capas de fachada (Fase 1.5, 2026-11-01) — C-03 / H-07

Pregunta: ¿alguna de las tres capas que el auditoría llamó «fachada» es peso
muerto retirable? Método: leer quiénes la consumen de verdad — empacado, MCP,
CI, docs publicadas — sin tocar código.

| Capa | Tamaño | Consumidor medido | Veredicto |
|---|---|---|---|
| `vault_toolkit/operations/*.py` | 97 adaptadores de 1–2 líneas (`from vault_toolkit.loading import import_toolkit_module…`) | **La wheel instalada**: `pyproject.toml` la lista en `packages`; `vault run <tool>` la despacha (producto instalado, ADR-0002); `tests/clean_install_gate.py` ejecuta `python -m vault_toolkit.operations.<x> --help` por cada adaptador | **Contrato de instalación.** Un despachador único (`-m vault_toolkit.operations <tool>`) la sustituiría, pero cambia la superficie verificada (gate + ADR) |
| `scripts/*.py` | 178 versionados; 48 solo reexportan `vault/` | **El checkout**: el servidor MCP lanza `python <script>` con CWD `scripts/` (`vault-mcp-server.mjs:1476-1477`); CI llama `python scripts/<x>.py`; los comandos publicados en `AGENTS.md` y `scripts/README.md` son así | **Contrato de checkout.** No es copia: `package-dir` proyecta `scripts/` ⇄ `vault_toolkit._impl` (ADR-0002, pyproject.toml:59) |
| `vault/` | dominios de producto | `vault_toolkit._impl` (instalado) y `scripts/` (checkout) importan de aquí; el frontón `vault.product_cli` la compone | **Es la lógica**, no fachada |

Hallazgo que corrige la hipótesis de «copia»: **`_impl/` no existe en el
checkout y no se copia en el build** — es la misma capa con otra identidad
(`package-dir = {"vault_toolkit._impl" = "scripts", …}`). Lo que viaja dos
veces es la *identidad*, no el contenido.

**Conclusión:** retirar una capa requiere versión de la superficie
(tool-spec, catálogo de MCP, docs prometidas y regla 7) — no es PURE_REFACTOR.
C-03 se queda CANDIDATE con esta medición al lado; el ahorro de complejidad
medible de la rama va por C-2 (proceso), los derivados (S-3) y la jubilación
del andamio del refactor (S-4).
