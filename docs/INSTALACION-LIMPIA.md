# Instalación limpia y registro del MCP

El README explica la instalación de un checkout para desarrollar
(`pip install -e .`). Esta guía cubre lo que hace un tercero: **quitar** lo que
hubiera, **instalar la wheel** y **registrar el servidor MCP** que viaja dentro
de ella. Todo lo que aquí se afirma se ejecutó así el 2026-10-01, en Windows 10
con Python 3.14, contra un vault creado con `vault init` dentro de una copia de
un proyecto consumidor.

## 1. Encontrar y quitar instalaciones previas

```bash
pip show vault-obsidian-architecture          # ¿hay una? ¿dónde?
pip uninstall -y vault-obsidian-architecture
python -c "import vault_toolkit"              # debe fallar: ModuleNotFoundError
```

Busca también lo que `pip` no ve:

- **Servidores MCP registrados** a mano: la clave `mcpServers` de
  `~/.claude.json` (Claude Code) y de `claude_desktop_config.json` (Claude Desktop).
  Una entrada que apunte a un checkout borrado o a una instalación antigua hace
  que el cliente arranque otra versión distinta de la que crees.
- **Copias de `scripts/` dentro de proyectos consumidores** (la receta anterior a
  v40.34 copiaba carpetas). No son la instalación: no se actualizan con `pip`, y
  las de la era v34 llevan la raíz del vault **fija en el código** — ignoran
  `VAULT_ROOT` y escriben en el vault de otro proyecto. Ver
  [la comparativa v34/v40](auditorias/2026-10-01-comparativa-v34-v40.md).

## 2. Construir e instalar la wheel

```bash
python -m build --wheel --outdir <directorio-fuera-del-repo>
pip install --user <directorio>/vault_obsidian_architecture-*.whl
vault --version
vault tools list
```

`python -m build` deja `build/` en el checkout. Está en `.gitignore` y fuera de
las fronteras que mide `vault_criterios`, así que no hace falta borrarlo para
pasar las puertas.

### Windows: `vault` no se encuentra

`pip install --user` deja los ejecutables en
`%APPDATA%\Python\Python3XX\Scripts`, que **no** está en el `PATH` por defecto.
`pip` lo avisa con un `WARNING` fácil de perder. Añádelo al `PATH` del usuario
(Configuración → Variables de entorno) y abre una terminal nueva.

## 3. Crear o elegir el vault

```bash
vault init <ruta-del-vault>       # INIT_CREATED
vault doctor <ruta-del-vault>     # RUNTIME_OK
```

Para que ninguna tool adivine la raíz, exporta `VAULT_ROOT=<ruta-del-vault>` y
`VAULT_STRICT_ROOT=1`: con la raíz sin resolver, la tool falla en vez de caer en
otro sitio.

## 4. Registrar el servidor MCP

```bash
vault mcp-path
```

Imprime la ruta del servidor dentro del paquete instalado y una entrada lista
para pegar en la configuración del cliente, con `VAULT_MCP_PYTHON` fijado al
intérprete donde está instalada la wheel. Solo hay que poner el `VAULT_ROOT`:

```json
{
  "mcpServers": {
    "vault": {
      "command": "node",
      "args": ["<server de vault mcp-path>"],
      "env": {
        "VAULT_ROOT": "<ruta absoluta del vault>",
        "VAULT_MCP_PYTHON": "<python de vault mcp-path>"
      }
    }
  }
}
```

En Claude Code, la entrada va en un `.mcp.json` en la raíz del proyecto (ámbito
de proyecto) o en `~/.claude.json`. Regístralo por proyecto: un servidor
global con un `VAULT_ROOT` fijo escribe en el mismo vault desde cualquier
proyecto.

### Comprobar el handshake antes de fiarte del cliente

Un cliente MCP que no recibe respuesta a `initialize` suele mostrar solo «server
failed to start» o nada. Comprobarlo a mano lleva una línea:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"prueba","version":"0"}}}' \
  | VAULT_ROOT=<ruta-del-vault> node <server de vault mcp-path>
```

Debe imprimir una línea JSON con `"id":1` y `serverInfo`. Hasta el arreglo de
2026-10-01, el servidor instalado no la imprimía (ver la comparativa).

## 5. Leer la salida desde otro programa

La CLI escribe JSON en UTF-8 sea cual sea la codificación de la consola. Si un
consumidor ve `est�ndar` en lugar de `estándar`, está leyendo con otra
codificación: lee los bytes como UTF-8.
