# Variables de entorno

> **Derivado** de `vault.kernel.entorno.VARIABLES`. Se regenera con
> `python scripts/vault_entorno.py --doc` y `--check-doc` falla si
> diverge; lo escrito a mano aquí se pierde. El valor que tiene cada
> una en tu shell lo da `python scripts/vault_entorno.py --filtro <nombre>`:
> se resuelve al llamarse, no al documentarse (AP-49).

Variables: 27.

| Variable | Tipo | Default | Quién la lee | Qué gobierna |
|---|---|---|---|---|
| `VAULT_AGENT` | texto | `''` | autoria | Quién firma la nota cuando no se pasa `--agent` (AP-16). Es el campo `agent:` del frontmatter, no un identificador de sesión. |
| `VAULT_CLIENT_CWD` | ruta | — | kernel | El directorio del cliente MCP, que el servidor no comparte con el proceso Python. Sin ella la autodetección mira el CWD del servidor, que no es el del usuario. |
| `VAULT_CONCURRENCY` | entero | `4` | meta_toolkit | Cuántas tools audita a la vez el banco de `vault_toolkit_audit` y el de `vault_noop_audit` (C-2 tanda 2a). Cada corrida usa su propia copia del sandbox, así que el paralelismo no comparte estado; las tools de gobernanza, que escriben en el repo, siguen en serie. Con `1` el banco vuelve a ser el de antes. |
| `VAULT_COUNT_TOKENS` | bandera | `False` | kernel | Añade el conteo de tokens al envelope de error. Apagado por defecto: contar cuesta más que el propio error. |
| `VAULT_DEBUG` | bandera | `False` | kernel | Adjunta el traceback a los envelopes de error. Apagada por defecto: el traceback lleva rutas absolutas del intérprete y del usuario, y por MCP llega al agente y a sus logs. |
| `VAULT_DQ_CACHE_MINUTES` | entero | `30` | gobernanza | Cuánto vale el índice de calidad cacheado antes de recalcularlo. |
| `VAULT_FSYNC` | bandera | `False` | kernel | Fuerza `fsync()` tras cada escritura atómica. Cuesta latencia; se activa cuando la durabilidad importa más que la velocidad. |
| `VAULT_LATENCY_MAX_MS` | entero | `5` | kernel | Techo duro de la misma medida, en milisegundos: una primitiva que tarde más que esto aun con la mejor de N llamadas es un fallo de latencia, no ruido — una primitiva genuinamente lenta no pasa igual porque su mínimo tampoco pasa (COST-a). |
| `VAULT_LATENCY_NOMINAL_MS` | entero | `2` | kernel | Latencia NOMINAL, en milisegundos, de una llamada a una primitiva caliente del kernel (parse de frontmatter, filtro de regex, resolución de wikilinks, estimación de tokens). Es el objetivo de regresión que mide `test_latencia_primitivas.py` en serie, no el techo: lo que se aleje de aquí sin que nadie lo declare es deuda de latencia silenciosa. Excluidas con motivo declarado las tools gruesas —auditoría, gates, consultas sobre el vault entero—: su presupuesto es `VAULT_TOOL_TIMEOUT`. |
| `VAULT_MASTER` | ruta | — | kernel | La casa de los vaults: donde se crean por defecto (vault_init --name) y donde se listan (vault_init --list). Por defecto ~/.vault-master (Windows: %USERPROFILE%\.vault-master). Cambiarla mueve la casa entera; el valor de la variable no se escribe a mano en la documentacion, se lee de aqui. |
| `VAULT_MCP_LOG` | texto | `'info'` | meta_toolkit | Nivel de log del servidor MCP (`info` por defecto). Solo la lee el `.mjs`. |
| `VAULT_MCP_PERFIL` | texto | `''` | meta_toolkit | Perfil de tools que el servidor MCP expone y acepta (`agente`: las del protocolo de sesión, de `tools-catalog.json` → `perfiles`). Vacía, todas las expuestas por MCP. Solo la lee el `.mjs`. |
| `VAULT_MCP_PYTHON` | ruta | — | meta_toolkit | Intérprete con el que el servidor MCP lanza las tools. Vacía, sondea `python3`, `python` y `py` (en ese orden; `py` al final porque en Windows del runner resuelve el Python registrado en la máquina, no el del toolkit) y exige a cada candidato que pueda `import yaml` (la dependencia declarada). Instalado en un venv, solo el de ese venv ve el toolkit, y `vault mcp-path` la fija a él: esa elección explícita no se segunda adivina. Solo la lee el `.mjs`. |
| `VAULT_MCP_TOKEN` | texto | `''` | meta_toolkit | Token que exige el transporte HTTP/SSE del servidor MCP (`Authorization: Bearer`). Si falta, se genera uno por arranque. Solo la lee el `.mjs`; stdio no la usa. |
| `VAULT_MCP_TOKENS` | texto | `''` | meta_toolkit | Tokens del transporte HTTP/SSE con su perfil, `lector:<t>,operador:<t>` (perfiles de `tools-catalog.json` → `perfiles_de_token`). `lector` solo ve y llama a las tools sin side effects. Se suma a `VAULT_MCP_TOKEN`, que es `operador`. Solo la lee el `.mjs`. |
| `VAULT_MODEL_PROFILE` | texto | `''` | consulta | Perfil de modelo LLM activo. Lo propaga el servidor MCP al detectar el cliente (clientInfo.name). Lo lee vault_model_profile y vault_context_pack para adaptar el budget al modelo. |
| `VAULT_PERMISSIVE_ROOT` | bandera | `False` | kernel | Permite ESCRIBIR sobre una raíz detectada con baja confianza (`repo_root_fallback`). Sin ella, leer con esa raíz sigue permitido y escribir se rechaza: instalado fuera del repo, ese fallback devuelve el propio directorio del programa, así que la escritura caía dentro del toolkit en vez de en un vault. Cuando esa raíz es el paquete del programa tampoco se lee: las tools se niegan con VAULT_NOT_FOUND salvo con esta bandera. |
| `VAULT_PROJECT` | texto | `''` | kernel | Proyecto al que está atada la sesión (slug o alias registrado). Solo restringe con `VAULT_PROJECT_LOCK=1`. `vault mcp-path --project` la fija ya resuelta. |
| `VAULT_PROJECT_LOCK` | bandera | `False` | kernel | Con `1`, todo `--project` que no resuelva al de `VAULT_PROJECT` se rechaza con `PROJECT_LOCKED` antes de que la tool haga nada. Encendida sin `VAULT_PROJECT`, rechaza todos: el candado no se abre por falta de configuración. |
| `VAULT_ROOT` | ruta | — | kernel | Fuerza la raíz del vault en vez de autodetectarla. Es la costura declarada para apuntar las tools a un destino concreto. |
| `VAULT_SCAN_ROOTS` | texto | `''` | meta_toolkit | Rutas separadas por `;` donde el servidor MCP busca vaults. Vacía significa dos rutas relativas al repo, no «ninguna». Solo la lee el `.mjs`; se declara aquí para que `--env` la publique y el servidor deje de inventarse su propia tabla. |
| `VAULT_SKIP_SECRET_SCAN` | bandera | `False` | kernel | Desactiva el escaneo de secretos del write path. Existe para los tests del propio escáner; en uso normal no se toca. |
| `VAULT_SMOKE_TIMEOUT` | entero | `90` | meta_toolkit | Segundos por tool en la pasada de humo. Más alto que `VAULT_TOOL_TIMEOUT` porque el smoke arranca un intérprete nuevo. |
| `VAULT_STRICT_ROOT` | bandera | `False` | kernel | Hace fallar una detección insegura en vez de caer a la raíz del repo. Basta con estar definida (comportamiento heredado). |
| `VAULT_TOOL_TIMEOUT` | entero | `60` | kernel | Segundos antes de que una tool se declare colgada. Lo leen `vault_errors` y el servidor MCP, que hasta ahora lo declaraban por separado con el mismo número. |
| `VAULT_VOICE` | texto | `'1'` | autoria | Verbosidad de la voz del vault: `0` la calla, `verbose` la amplía, cualquier otro valor deja el mensaje normal. |
| `VOAS_MERMAID_ORACLE` | ruta | — | kernel | Directorio con `node_modules` que trae `mermaid` + `jsdom` para el oráculo del compilador real (`vault_mermaid_check`: `mcp/nodejs/mmd_validate.mjs`). Útil con wheels instaladas, donde el pack vive fuera del checkout. Si falta, el checker degrada al parser heurístico y lo declara. |
