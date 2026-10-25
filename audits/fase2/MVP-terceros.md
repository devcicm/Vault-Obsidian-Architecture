# Recorrido de tercero sobre la wheel instalada (GOAL F)

**Fecha:** 2026-10-25 · **Entorno:** Windows, Python 3.14.3, venv limpio en
`%TEMP%\opencode\rc-venv`, runtime en `%TEMP%\opencode\consumidor-rc\mi-vault`.
**Fuera del checkout**: nada del recorrido importa el repositorio; solo la wheel
instalada.

## Artefactos

| Artefacto | Tamano | sha256 |
|---|---|---|
| `vault_obsidian_architecture-41.23-py3-none-any.whl` | 1 667 001 B | `d80c4974ba71d7ad5f4f0e959c4856f013a9398bbfdc771b0e84fec9a042a2b5` |
| `vault_obsidian_architecture-41.23.tar.gz` | 2 156 269 B | `1b7c81eb3f4bba30929cf15d01a366cdeec8829189e4e7fab71a3853a1cd74a9` |

- 706 ficheros en la wheel; 2 `.mjs` empaquetados; `entry_points.txt` con
  `vault` y `vault_gobernanza`.
- Sin `.tool-trace`, `.locks`, `.history`, `audits/`, `tests/` ni `__pycache__`.
- Única coincidencia de "ruta absoluta" en el contenido: un docstring con
  `C:\Users\<usuario>` (marcador, no una cuenta real). Cero formas de
  credencial.

## Recorrido ejecutado (con su salida real)

| Paso | Comando | Resultado |
|---|---|---|
| Version | `vault --version` | `41.23` |
| Ayuda | `vault --help` | `tools, run, init, doctor, status, mcp-path` |
| Crear runtime | `vault init <rt>` | `ok: true`, `state: INIT_CREATED`, 23 secciones, `bootstrap.ok: true` |
| Diagnostico | `vault doctor <rt>` | `RUNTIME_OK`, `compatible`, 23 secciones |
| Estado | `vault status <rt>` | `RUNTIME_OK` |
| Escribir (CLI) | `vault run vault_write --folder 07_Knowledge --title ... --tags demo tercero --content ...` | `ok: true`, `07_Knowledge/nota-de-tercero.md` |
| Leer (CLI) | `vault run vault_read --path ...` | `ok: true`, contiene el texto escrito |
| Servidor MCP | `vault mcp-path` | ruta al `.mjs` empaquetado + config de cliente con `VAULT_ROOT` y `VAULT_MCP_PYTHON` |
| MCP `initialize` | JSON-RPC por stdio | `vault-mcp-server v41.23` |
| MCP `tools/list` | JSON-RPC | **97 tools** |
| Leer por MCP | `tools/call vault_read` | devuelve la nota escrita por la CLI |
| Buscar por MCP | `tools/call vault_search` | encuentra `nota-de-tercero` |
| Persistencia | segundo proceso del servidor | la nota sigue ahi |
| Backup | `vault run vault_backup` | `vault-backups/vault-2026-10-25-135433/` |
| Listar backups | `vault run vault_backup_list` | 1 backup |
| Borrar y restaurar | `vault_restore --backup_name ... --confirm true` | `ok: true`, 79 ficheros restaurados, 45 notas; la nota volvio |
| Dependencias | `pip-audit` | `No known vulnerabilities found` (PyYAML); el paquete propio no esta en PyPI y se omite, declarado |

## Fricción real encontrada (y corregida en la documentacion)

Un tercero choca, en este orden, con tres normas que no conocia:

1. **AP-11**: el contenido necesita ≥3 lineas reales.
2. **AP-26**: las notas de contenido necesitan `--tags`.
3. **AP-16**: necesitan autor (`--agent` o `VAULT_AGENT`).

El README lo decia para la primera; las otras dos no estaban en el Quick Start.
Ahora el paso 6 las nombra y muestra la forma instalada (`vault run <tool>`)
sin obligar a tener el checkout. Es exactamente la contradiccion DOC-0001 /
TD-0009 del dictamen.

## Limites de esta evidencia

- **Solo Windows** y **solo Python 3.14**: la matriz de 3 SO x 4 versiones la
  tiene que ejecutar la CI, que sigue bloqueada por la cuenta (ver
  `CI-diagnostico.md`). Esto es evidencia complementaria, **no** QG-07.
- El recorrido usa una instalacion limpia, pero no prueba la desinstalacion; el
  `pip uninstall` no se ejecuto para no destruir el entorno de prueba antes de
  capturar la evidencia.

## Reproduccion

```text
python -m build --wheel --sdist --outdir <dist>
python -m venv <venv> && <venv>/Scripts/pip install <dist>/*.whl
vault init <runtime>; vault doctor <runtime>
VAULT_ROOT=<runtime> VAULT_AGENT=<agente> vault run vault_write --folder 07_Knowledge --title ... --tags ... --content ...
vault mcp-path   # y arrancar node con esa ruta hablando JSON-RPC
```
