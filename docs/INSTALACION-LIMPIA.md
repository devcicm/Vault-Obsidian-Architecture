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

El **padre** de `<ruta-del-vault>` tiene que existir: `vault init` no crea
directorios intermedios, y con el padre ausente sale con código 8,
`INVALID_PATH` y `"state": "INIT_INVALID_TARGET"` sin tocar nada. Crea antes
la carpeta del proyecto (`mkdir -p <proyecto>`). Medido el 2026-10-15 en
Linux con Python 3.9 siguiendo esta guía al pie de la letra.

Para que ninguna tool adivine la raíz, exporta `VAULT_ROOT=<ruta-del-vault>` y
`VAULT_STRICT_ROOT=1`: con la raíz sin resolver, la tool falla en vez de caer en
otro sitio.

**Cambio de contrato posterior a 41.6 (2026-10-16).** Sin `VAULT_ROOT`, cuando la
autodetección no encuentra vault y cae en el propio paquete instalado, ninguna
tool se ejecuta: sale con código 1 y `VAULT_NOT_FOUND`. Hasta 41.6 las de lectura
—`vault run vault_query_parse`, `vault run vault_audit`— leían
`site-packages/vault_toolkit` como si fuera el vault y devolvían `ok: true`. Si
lanzas la tool desde dentro de un runtime, la pista del rechazo lo dice y
propone `VAULT_ROOT=.`; no lo deduce en silencio. Siguen pasando `--help`,
`--root <ruta>` y `VAULT_PERMISSIVE_ROOT=1`, que restaura lo anterior. Un
checkout de un proyecto sin vault no cambia: su raíz no es un paquete.

Exporta también `VAULT_AGENT=<quién escribe>` (`claude`, `human`, `script`…):
toda nota de contenido lleva `agent:` (AP-16), y sin `--agent` ni `VAULT_AGENT`
la primera escritura sale con `missing_agent` antes de tocar el disco. Las
notas de `00_System/` quedan exentas. Es lo primero con lo que tropezó la
instalación ciega del 2026-10-15 (wheel limpia en un venv nuevo, siguiendo solo
esta guía).

```bash
VAULT_AGENT=claude vault run vault_write --folder 07_Knowledge   --title "Primera nota" --tags inicio --content "<al menos tres líneas>"
```

La respuesta lleva `change_log` con la entrada que la escritura dejó en
`00_System/.change-log.json` (F8, no repudio).

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

### Atar la sesión a un proyecto

Un vault guarda la memoria de varios proyectos. Para que el agente que trabaja
en uno no escriba en la de otro:

```bash
vault mcp-path --root <ruta-del-vault> --project <slug o alias>
```

El nombre se resuelve **aquí**, contra el registro del vault (`01_Projects/`):
uno que no existe sale con `PROJECT_NOT_FOUND` en vez de fundar un proyecto.
La entrada que imprime lleva además `VAULT_PROJECT=<slug>` y
`VAULT_PROJECT_LOCK=1`; con ellas, toda tool a la que se pida otro `--project`
falla con `PROJECT_LOCKED` antes de escribir nada, y lo mismo `vault_write`,
`vault_append`, `vault_move` y `vault_delete` con una ruta `<carpeta>/<otro
proyecto>/…`. El servidor no interpreta
nombres: pasa el entorno a cada tool y el candado lo aplica Python.

### Comprobar el handshake antes de fiarte del cliente

Un cliente MCP que no recibe respuesta a `initialize` suele mostrar solo «server
failed to start» o nada. Comprobarlo a mano lleva una línea:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"prueba","version":"0"}}}' \
  | VAULT_ROOT=<ruta-del-vault> node <server de vault mcp-path>
```

Debe imprimir una línea JSON con `"id":1` y `serverInfo`. Hasta el arreglo de
2026-10-01, el servidor instalado no la imprimía (ver la comparativa).

Por stderr sale además `[MCP WARN] Tools sin script en …, retiradas: …`. Es lo
esperado: el catálogo describe el repo entero y la wheel de producto deja fuera
las tools de gobernanza del estándar (`vault_arch`, `vault_blueprint`,
`vault_doc_counts`…), que miden este repo y no tu vault. El servidor las retira
de `tools/list` y dice cuáles en vez de ofrecer algo que fallaría al llamarlo.
Cuántas son lo dice esa línea; las que quedan, `vault tools list` (las de
`"installed": true`).

## 5. Leer la salida desde otro programa

La CLI escribe JSON en UTF-8 sea cual sea la codificación de la consola. Si un
consumidor ve `est�ndar` en lugar de `estándar`, está leyendo con otra
codificación: lee los bytes como UTF-8.

Lee **los dos canales**. `vault run` lanza la tool y su respuesta —con
`"ok": true` o con su `error_code`, como `missing_agent`— sale por **stdout**.
Cuando es el propio `vault` el que rechaza la orden antes de lanzar nada
(tool desconocida o no instalada, destino inválido, o un argumento que el
pre-flight bloquea, como `--path ../../fuera.md` con `PREFLIGHT_REJECTED`), el
JSON del error sale por **stderr** y stdout queda vacío. El código de salida
dice cuál de los dos casos es:

| Código | Constante | Qué pasó | Dónde está el JSON |
|---|---|---|---|
| `3` | `EXIT_UNKNOWN` | La tool no existe | stderr |
| `4` | `EXIT_NOT_INSTALLED` | Existe, pero esta instalación no la trae | stderr |
| `5` | `EXIT_NOT_RUNTIME` | Es de gobernanza del estándar, no de runtime | stderr |
| `6` | `EXIT_INVALID_TARGET` | El módulo instalado no es un destino válido | stderr |
| `7` | `EXIT_OPERATION_FAILED` | La tool se ejecutó y devolvió un fallo | stdout |
| `8` | `EXIT_RUNTIME_INVALID` | `init`, `doctor` o `status` encontraron un runtime inválido, o `init` recibió una ruta inválida (`INIT_INVALID_TARGET`, p. ej. el padre no existe) | stderr |
| `9` | `EXIT_INIT_CONFLICT` | `init` sobre una ruta en conflicto | stderr |
| `10` | `EXIT_PREFLIGHT_FAILED` | El pre-flight bloqueó un argumento; no se ejecutó nada | stderr |

Medido en la reinstalación del 2026-10-15: quien solo leía stdout veía una
salida vacía con código 10 y ningún motivo.
