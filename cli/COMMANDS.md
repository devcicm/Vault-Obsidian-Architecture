# `cli/` — referencia de comandos

Guía conceptual: [`README.md`](README.md).

```
python -m cli [--pretty] [--version] <comando> [opciones]
```

`--pretty` funciona en cualquiera de las dos posiciones (antes o después del comando).
Toda salida es JSON en stdout con envelope `{"ok": bool, "tool": "cli.<comando>", ...}`.

**Códigos de salida:** `0` éxito · `1` fallo o sin resultados · `2` bloqueado en
pre-vuelo · `130` interrumpido.

**Variables de entorno relevantes:**

| Variable | Efecto |
|---|---|
| `VAULT_ROOT` | fuerza la raíz del vault |
| `VAULT_STRICT_ROOT=1` | una detección insegura falla en vez de adivinar |
| `VAULT_AGENT` | atribución exigida por AP-16 en las escrituras |

---

## Índice

| Comando | Para qué |
|---|---|
| [`groups`](#groups) | catálogo completo por grupo |
| [`find`](#find) | buscar fragmentos por texto libre |
| [`show`](#show) | ficha de un fragmento |
| [`doctor`](#doctor) | estado del entorno |
| [`run`](#run) | ejecutar una tool con pre-vuelo |
| [`plan`](#plan) | planificar un lote sin ejecutarlo |
| [`batch`](#batch) | ejecutar un lote en paralelo |
| [`scan`](#scan) | antipatrones y condiciones de carrera |

---

## `groups`

Catálogo completo, agrupado. Sin opciones propias.

```bash
python -m cli groups --pretty
```

```jsonc
{
  "ok": true, "tool": "cli.groups",
  "total": 76, "read": 15, "write": 61, "groups": 35,
  "missing_scripts": [],
  "catalog": { "Backups": [ {"name": "vault_backup", "mode": "write", "purpose": "..."} ] }
}
```

`missing_scripts` no vacío es señal de AP-01/AP-04: el catálogo declara una tool cuyo
script no existe. Las dos tools nativas del servidor MCP (`vault_backup_base64`,
`vault_restore_base64`) no cuentan como ausentes — se marcan `"runtime": "node"`.

---

## `find`

Búsqueda **AND**: todos los términos deben aparecer en el texto del fragmento (nombre,
grupo, propósito, guards, side-effects, parámetros, relacionadas, ejemplo).

```
python -m cli find <query> [--mode read|write] [--group <texto>] [--full]
```

| Opción | Efecto |
|---|---|
| `--mode` | filtra por modo de acceso |
| `--group` | filtra por grupo (subcadena, insensible a mayúsculas) |
| `--full` | ficha completa de cada resultado en vez del resumen |

```bash
python -m cli find "backup grafo"
python -m cli find "" --mode write          # las 92 tools que escriben
python -m cli find "indice" --group Index --full --pretty
```

Sale con `1` si no hay coincidencias — usable como condición en un script.

---

## `show`

Ficha de un fragmento. Tolera el prefijo `vault_` omitido (`show write` ≡
`show vault_write`).

```bash
python -m cli show vault_write --pretty
```

Devuelve `params_detail`, `required_args`, `guards`, `side_effects`,
`touched_artifacts`, `related`, `script_exists` y un bloque `concurrency`:

```jsonc
"concurrency": { "global_scope": false, "parallelizable": false }
```

- `global_scope: true` → la tool corre sola, sin nada en paralelo.
- `parallelizable: true` → solo lectura y sin alcance global: puede correr con
  cualquier cosa.

Si el nombre no existe, devuelve `did_you_mean` con hasta 5 sugerencias y sale con `1`.

---

## `doctor`

Estado del entorno antes de escribir nada. Sin opciones propias.

```bash
python -m cli doctor --pretty
```

Cuatro comprobaciones:

| Check | Qué verifica | Si falla |
|---|---|---|
| `vault_root` | raíz resuelta y **origen fiable** (`vault_root_origin()`) | exporta `VAULT_ROOT` o `VAULT_STRICT_ROOT=1` |
| `tool_spec` | `<vault>/00_System/tool-spec.json` presente | `python scripts/vault_manifest.py --bootstrap` |
| `fragments` | todo script catalogado existe | revisa el catálogo (AP-01/AP-04) |
| `shared_artifact_locks` | qué artefactos compartidos se escriben sin `file_lock` | el planificador los serializará |

El último check no es un error de configuración: es el estado real del código. Que
salga `ok: false` significa que el paralelismo será menor, no que algo esté roto.

---

## `run`

Ejecuta **una** tool en subproceso, tras el pre-vuelo de seguridad.

```
python -m cli run <tool> [clave=valor ...] [--timeout N] [--dry-run] [--strict] [--force]
```

**Sintaxis de argumentos:**

| Forma | Significado |
|---|---|
| `clave=valor` | valor literal |
| `clave=@ruta` | lee el valor del archivo (contenidos largos) |
| `clave=true` / `clave=false` | booleano |
| `clave` (sin `=`) | booleano `True` (flag) |

| Opción | Efecto |
|---|---|
| `--timeout N` | segundos (default: 120) |
| `--dry-run` | muestra el `argv` construido y no ejecuta |
| `--strict` | los hallazgos `medium` también bloquean |
| `--force` | ejecuta pese a los hallazgos; queda registrado |

```bash
export VAULT_AGENT=mi-agente
python -m cli run vault_audit
python -m cli run vault_write folder=01_Projects/api title="API" content=@nota.md tags="api backend"
python -m cli run vault_write folder=01_Projects/api title=X content=@n.md --dry-run --pretty
```

Si el pre-vuelo bloquea, sale con **`2`** y `"stage": "preflight"` con la lista de
hallazgos. Los avisos que no bloquean se adjuntan igualmente en
`preflight_findings`.

**Códigos de pre-vuelo:**

| Código | Severidad | Qué es |
|---|---|---|
| `TOOL-UNKNOWN` | critical | la tool no está en el catálogo |
| `TOOL-MISSING` | critical | el script del fragmento no existe |
| `TOOL-RUNTIME` | high | fragmento nativo de Node, no ejecutable desde aquí |
| `TOOL-STATUS` | medium | fragmento marcado como no activo en el `tool-spec.json` |
| `AP36-ABS` | critical | ruta absoluta como destino |
| `AP36-TRAVERSAL` | critical | `..` en la ruta |
| `AP36-ESCAPE` | critical | el destino resuelto cae fuera del vault |
| `AP36-ROOT` | critical | raíz del vault adivinada, no fiable |
| `PATH-INVALID` | high | ruta no interpretable |
| `CONTRACT-MISSING` | high | falta un `required_args` del `tool-spec.json` |
| `CONTRACT-UNKNOWN` | medium | argumento que el contrato no declara |
| `ARG-COUNT` / `ARG-SIZE` | high | demasiados argumentos, o uno desproporcionado |
| `POISON-01..05` | critical | patrón de inyección en el contenido |
| `POISON-INVISIBLE` | high | caracteres invisibles o *tag characters* Unicode |
| `POISON-CONTROL` | high | caracteres de control en el contenido |
| `POISON-FRONTMATTER` | medium | intento de sobrescribir `created` / `id` |
| `AP-21` | high | wikilink anclado a ruta |

`agent` en el frontmatter **no** se bloquea: AP-16 exige fijarlo por esa vía.

---

## `plan`

Calcula las olas de ejecución **sin ejecutar nada**. Mismas fuentes de operaciones
que `batch`.

```
python -m cli plan (--op "..." | --file <ruta|->) [--strict]
```

**Formato `--op`** (repetible): `"<tool> [clave=valor ...]"`, separado por espacios.

**Formato `--file`**: JSON con una lista, o un objeto con clave `operations`:

```json
{
  "operations": [
    {"id": "a", "tool": "vault_write",
     "args": {"folder": "01_Projects/api", "title": "Nota A", "content": "...", "tags": "api"}},
    {"id": "b", "tool": "vault_audit", "args": {}}
  ]
}
```

`id` es opcional (por defecto `<tool>#<n>`). `--file -` lee de stdin.

```bash
python -m cli plan --op "vault_write folder=01_Projects/a title=A content=@a.md" \
                   --op "vault_audit" --pretty
python -m cli plan --file lote.json --pretty
```

Salida: `waves` con las operaciones de cada ola y sus recursos por nivel
(`exclusive` / `guarded` / `global`), `wave_count`, `max_wave_size`, y
`serialization_reasons` — por cada par serializado, qué recurso comparten.

Antes de planificar, `plan` endurece el modelo con el escáner: los artefactos
compartidos que se escriben sin lock aparecen en `unlocked_shared_artifacts` y se
tratan como exclusivos.

---

## `batch`

Ejecuta el lote por olas: dentro de cada ola, en paralelo; entre olas, barrera.

```
python -m cli batch (--op "..." | --file <ruta|->)
                    [--parallel N] [--timeout N] [--strict] [--force]
                    [--dry-run] [--stop-on-error] [--verify-integrity]
```

| Opción | Efecto |
|---|---|
| `--parallel N` | operaciones simultáneas por ola (default: 4) |
| `--timeout N` | segundos por operación (default: 120) |
| `--strict` | los hallazgos `medium` bloquean el lote |
| `--force` | ejecuta pese a los hallazgos |
| `--dry-run` | no ejecuta; muestra el plan y los `argv` |
| `--stop-on-error` | detiene tras la primera ola con fallos; el resto va a `not_executed` |
| `--verify-integrity` | hashea el vault antes/después y contrasta con lo declarado |

```bash
export VAULT_AGENT=mi-agente
python -m cli batch --file lote.json --parallel 4 --verify-integrity --pretty
```

**Bloque `integrity`** (solo con `--verify-integrity`):

```jsonc
"integrity": {
  "created": ["01_Projects/api/Nota-A.md", "01_Projects/api/index.md"],
  "modified": ["00_System/.tool-trace.json", "01_Projects/index.md", "99_Index/search-index.json"],
  "deleted": [],
  "declared_targets": ["01_Projects/api", "01_Projects/index.md", "..."],
  "ambient_changes": ["00_System/.tool-trace.json"],
  "unexpected_changes": []
}
```

- **`ambient_changes`** — instrumentación que escribe toda tool vía `wrap_main`
  (`.tool-trace.json`, `.change-log.json`, `token-usage.json`, `*.locks`). No cuenta
  como cambio inesperado.
- **`unexpected_changes`** no vacío marca el lote `ok: false`. Significa que alguna
  tool tocó algo que no declara en su catálogo: revísalo antes de seguir escribiendo.

La comparación es por segmento de ruta, no por prefijo de cadena: `01_Projects/api`
no cubre `01_Projects/api-legacy`.

---

## `scan`

Escáner AST sobre los scripts del repo.

```
python -m cli scan [--races] [--antipatterns] [--tool <nombre>] [--path <archivo>]
                   [--min-severity critical|high|medium|low] [--summary]
```

| Opción | Efecto |
|---|---|
| `--races` | solo condiciones de carrera (`RC-*`) |
| `--antipatterns` | solo antipatrones (`AP-*`, `PY-*`) |
| `--tool` | analiza el script de un fragmento concreto |
| `--path` | analiza un archivo suelto |
| `--min-severity` | umbral de reporte (default: `low`) |
| `--summary` | omite `issues`, deja solo los recuentos |

```bash
python -m cli scan --summary --pretty
python -m cli scan --races --summary --pretty     # incluye unsafe_artifacts
python -m cli scan --tool vault_write --pretty
python -m cli scan --min-severity high
```

**Reglas:**

| Código | Severidad | Qué detecta |
|---|---|---|
| `RC-01` | critical | artefacto compartido escrito sin `file_lock()` |
| `RC-02` | high | escritura no atómica sobre un JSON del vault |
| `RC-03` | high | TOCTOU: `exists()` seguido de escritura o borrado |
| `RC-04` | critical | read-modify-write de JSON sin lock (*lost update*) |
| `RC-05` | medium | estado mutable de módulo modificado dentro de una función |
| `RC-06` | high | lock por `mkdir` sin detección de lock obsoleto |
| `AP-36` | critical | ruta derivada de `__file__` o del CWD, no del vault root |
| `AP-01` | high | referencia a un script que no existe |
| `PY-01` | medium | excepción silenciada sin registro (`except: pass`) |
| `PY-02` | medium | entry point sin `wrap_main` (sin timeout ni trace) |
| `PY-03` | high | argumento por defecto mutable (estado compartido) |
| `PY-04` | critical | `subprocess` con `shell=True` (inyección de comandos) |

`scan --races` sin `--tool`/`--path` añade `unsafe_artifacts`: el mapa
artefacto compartido → scripts que lo escriben sin lock. Es el dato que consume el
planificador.

**Supresión:** `# cli-scan: ignore <CODIGO>` al final de la línea afectada. Se usa
para el caso legítimo, no para silenciar un hallazgo real.

Sale con `1` si hay hallazgos por encima del umbral — apto como gate de CI.

---

## Recetas

**Cerrar una sesión de escritura con verificación completa**

```bash
export VAULT_AGENT=mi-agente
python -m cli doctor --pretty || exit 1
python -m cli plan --file lote.json --pretty
python -m cli batch --file lote.json --parallel 4 --verify-integrity --stop-on-error --pretty
```

**Gate de CI sobre el código de las tools**

```bash
python -m cli scan --min-severity high --summary
```

**Auditar qué toca una tool antes de usarla**

```bash
python -m cli show vault_move --pretty
python -m cli scan --tool vault_move --races --pretty
```
