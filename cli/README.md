# `cli/` — CLI consolidada de Vault Obsidian Architecture

**v40.34 · 116 tools · 37 grupos · un único punto de entrada**

```bash
python -m cli <comando> [opciones]
```

Referencia exhaustiva de comandos: [`COMMANDS.md`](COMMANDS.md).

---

## Qué es esto

El repo tiene ~152 scripts y 116 tools activas. Cada una es un ejecutable independiente
con su propio `argparse`, su propio contrato y sus propios side-effects. Eso funciona
bien para invocación puntual y mal para tres cosas:

1. **Buscar.** ¿Qué tool toca el grafo? ¿Cuáles escriben? ¿Cuál necesita `--root`?
   La respuesta estaba repartida entre `scripts/README.md`, el catálogo MCP y el código.
2. **Ejecutar varias a la vez.** Nada impedía lanzar dos escrituras sobre la misma
   carpeta y perder una: los `index.md` se regeneran en cascada en cada escritura.
3. **Confiar en el contenido.** Una nota es contexto persistente de un agente. Texto
   con directivas incrustadas se convierte en instrucciones en la siguiente sesión.

`cli/` resuelve las tres. No reimplementa ninguna tool — las **indexa, planifica y
ejecuta** en subproceso, respetando su contrato y su envelope JSON.

---

## Las tools como fragmentos

Un *fragmento* es una tool vista como pieza buscable: nombre estable, grupo, propósito,
parámetros, guards, side-effects, artefactos que toca y modo (`read`/`write`).

El índice **no inventa nada**. Se construye leyendo las fuentes de verdad del repo:

| Dato | Fuente |
|---|---|
| grupo, propósito, params, guards, side-effects | `scripts/vault_mcp_catalog.py :: TOOLS_CATALOG` |
| `required_args`, `status` | `<vault>/00_System/tool-spec.json` |
| raíz del vault y su origen | `vault_io.get_vault_root()` / `vault_root_origin()` |

Si una tool no está en el catálogo, no existe para la CLI. Es AP-01/AP-04 aplicado a
la propia CLI: nada de documentación alucinada.

```bash
python -m cli groups --pretty          # catálogo completo por grupo
python -m cli find "backup grafo"      # búsqueda AND sobre todo el texto del fragmento
python -m cli find "" --mode write     # las 99 tools que escriben
python -m cli show vault_write --pretty
```

---

## Concurrencia sin corrupción

### El modelo de recursos

| Nivel | Qué es | Efecto |
|---|---|---|
| **EXCLUSIVE** | la nota concreta y su carpeta | se serializa |
| **GUARDED** | artefacto compartido protegido por `vault_io.file_lock` + escritura atómica | se registra, **no** serializa |
| **GLOBAL** | backup, restore, reindex, migraciones | corre sola, nada en paralelo |

Con eso el planificador agrupa las operaciones en **olas**: dentro de una ola nada
comparte recurso exclusivo, entre olas hay barrera. El orden relativo se preserva —
una operación nunca se adelanta a otra con la que comparte recurso.

### La parte que importa: GUARDED se concede por verificación

Declarar que un artefacto está protegido no lo protege. Antes de planificar,
`scheduler.harden()` llama al analizador AST y **comprueba en el código** quién
escribe cada artefacto compartido sin `file_lock`. Los que no pasan la prueba se
degradan a exclusivos y se serializan.

Hoy el escáner encuentra esto:

```
99_Index/graph.json           ← vault_graph, vault_move
99_Index/graph-enriched.json  ← vault_graph_merge
99_Index/search-index.json    ← vault_index, vault_migrate_rollback, vault_move, vault_tags
99_Index/hash-index.json      ← vault_master_index, vault_section_index
00_System/tools-manifest.json ← vault_manifest
```

Son hallazgos reales del repo, no hipótesis. `batch` los reporta en
`unlocked_shared_artifacts` para que se entienda por qué un lote corrió con menos
paralelismo del esperado.

### Cascada de índices

Escribir `01_Projects/api/Nota.md` no toca solo esa carpeta:
`atomic_write_text` → `_auto_section_index` → `vault_section_index("01_Projects")`,
que regenera el índice de la sección **y el de cada subcarpeta**. La CLI modela esa
cascada (`scheduler.cascaded_indexes`), así que `--verify-integrity` no la reporta
como cambio inesperado — y el planificador sabe que la carpeta es exclusiva.

### Verificación de integridad

```bash
python -m cli batch --file lote.json --parallel 4 --verify-integrity
```

Hashea el vault antes y después y clasifica cada cambio:

- **declarado** — el plan lo anunciaba;
- **ambient** — ruido de instrumentación (`.tool-trace.json`, `.change-log.json`,
  `token-usage.json`, `*.locks`), que toda tool escribe vía `wrap_main`;
- **inesperado** — cualquier otra cosa. Marca el lote como `ok: false`.

Un cambio inesperado no es necesariamente un fallo: es un side-effect que nadie
declaró. Que salte es exactamente el punto.

---

## Pre-vuelo de seguridad (`cli/safety.py`)

Antes de ejecutar, cada operación pasa por comprobaciones que se ejecutan **sobre los
argumentos, no sobre el resultado** — porque después de escribir ya es tarde:

- **Contención (AP-36):** rutas absolutas, `..`, destinos fuera del vault.
- **Raíz fiable:** si `vault_root_origin()` no es de confianza, avisa; con
  `VAULT_STRICT_ROOT=1` la detección insegura falla en vez de adivinar.
- **Contrato:** `required_args` del `tool-spec.json` presentes (normalizando
  `--meta-file` → `meta_file`).
- **Anti-poisoning:** el contenido se escanea por patrones de inyección
  (`POISON-01..05`): directivas de override, turnos de conversación falsos, etiquetas
  `<system>` falsas, reasignación de identidad, instrucciones de ocultar al usuario.
  También caracteres invisibles y *tag characters* Unicode (`U+E0000–E007F`), el
  vector clásico de payload oculto.
- **AP-21:** wikilinks anclados a ruta.
- **Frontmatter:** intento de sobrescribir `created` / `id` (aviso `medium`).
  `agent` **no** se bloquea: AP-16 exige fijarlo por ahí.

Los hallazgos `high`/`critical` bloquean. `--strict` hace que también bloqueen los
`medium`. `--force` ejecuta de todas formas y deja constancia del override.

---

## Escáner de código (`cli/analyzer.py`)

Analiza los 98 scripts por AST (no por regex) buscando condiciones de carrera y
antipatrones:

| Código | Qué detecta |
|---|---|
| `RC-01` | artefacto compartido escrito sin `file_lock()` |
| `RC-02` | escritura no atómica sobre un JSON del vault |
| `RC-03` | TOCTOU: `exists()` seguido de escritura o borrado |
| `RC-04` | read-modify-write de JSON sin lock (*lost update*) |
| `RC-05` | estado mutable de módulo modificado dentro de una función |
| `RC-06` | lock por `mkdir` sin detección de lock obsoleto |
| `AP-36` | ruta derivada de `__file__` o del CWD, no del vault root |
| `AP-01` | referencia a un script que no existe |
| `PY-01..04` | excepción silenciada, entry point sin `wrap_main`, argumento por defecto mutable, `shell=True` |

Supresión puntual con `# cli-scan: ignore <CODIGO>` en la línea.

```bash
python -m cli scan --summary --pretty          # recuento global
python -m cli scan --races --summary --pretty  # + mapa artefacto → culpables
python -m cli scan --tool vault_write --pretty
python -m cli scan --min-severity high
```

---

## Flujo recomendado

```bash
python -m cli doctor --pretty                 # 1. ¿dónde escribo y con qué contrato?
python -m cli find "escribir nota"            # 2. ¿qué fragmento necesito?
python -m cli show vault_write --pretty       # 3. ¿qué exige y qué toca?
python -m cli plan --file lote.json --pretty  # 4. ¿cómo se va a paralelizar y por qué?
python -m cli batch --file lote.json --verify-integrity   # 5. ejecutar y comprobar
```

Todo emite JSON en stdout con envelope `{ok, tool, ...}` y código de salida
`0`/`1` — apto para encadenar y para CI.

---

## Reglas del repo que la CLI hereda

- **`vault-sandbox/` para cualquier ejecución.** La CLI no acepta un `--root` propio:
  resuelve el vault con `vault_io`, igual que las tools. Para forzar destino,
  `VAULT_ROOT`; para que una detección insegura falle, `VAULT_STRICT_ROOT=1`.
- **AP-16 — atribución.** Exporta `VAULT_AGENT=<nombre>` o pasa `meta` con `agent`.
  Sin eso, las escrituras que lo exigen fallan.
- **No-derogación.** La CLI no sustituye a ninguna tool ni oculta ninguna: es una
  capa por encima. Los scripts siguen siendo invocables directamente.
