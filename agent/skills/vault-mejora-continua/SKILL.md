---
name: vault-mejora-continua
description: "Ciclo de mejora continua guiado por errores observados y antipatrones recurrentes (F1..F13): captura en vivo, clasificación en 18_Bugs, escalamiento obligatorio a test+guard al segundo incidente y cierre con verificaciones DN-01..DN-10."
allowed-tools: Bash, Read, Grep, Glob
argument-hint: "[--error <sintoma>] [--familia F1..F13] [--ronda]"
entry-point: none
version: "1.0"
---

# Vault Mejora Continua (v1.0)

Cierra el ciclo completo **error observado → evidencia → antipatrón → test que falla antes del fix → guard que rechaza → medición de cierre**.

Esta skill **no crea tools nuevas**: orquesta las herramientas ya instaladas del catálogo (`vault_log_error`, `vault_bug_save`, `vault_search`, `vault_context_pack`, `vault_ronda`, `vault_propagate`, `vault_audit`, `vault_write`) para que ningún error operativo o defecto recurrente quede en un parche puntual.

---

## Principio rector

> Un parche sin test que lo capture ni guard que lo bloquee vuelve a romperse en la siguiente sesión.
>
> **Regla de recurrencia (`>= 2` incidentes):** el primer incidente se registra con causa raíz y test de regresión; al **segundo incidente de la misma familia** queda prohibido parchear ad-hoc — es obligatorio promoverlo a **guard ejecutable** + **norma/antipatrón** + **test de frontera**.

---

## Cuándo invocarla

- Cuando una ejecución, prueba, CI o sesión con el usuario produce un **error operativo, fallo silencioso, regresión o inconsistencia**.
- Cuando detectas que un defecto pertenece a una **familia recurrente de antipatrones (`F1..F13`)** ya vista antes.
- Al cierre de una ronda o iteración de trabajo para transformar los errores de la jornada en prevención permanente y nota de sesión `DN-01..DN-10`.

---

## Las 5 etapas del ciclo

### Etapa 1 — Captura inmediata del error observado (en vivo)

En cuanto ocurre un fallo real (comando roto, excepción, falsos verdes, divergencia de contrato, fuga de datos, encoding/plataforma), regístralo con evidencia exacta antes de intentar arreglarlo:

```bash
vault run vault_log_error --type runtime --title "<sintoma-corto>" --description "<que-paso-y-salida-real>" --severity high --context "<archivo:linea-o-comando>" --mitigation "<pendiente-o-accion-inmediata>"
```

**Reglas de captura:**
- Cita el comando exacto, código de salida y error literal. Nunca parafrasees ni maquilles la salida.
- No borres trazas ni reescribas incidentes previos; cada error nuevo se añade al registro.

---

### Etapa 2 — Búsqueda de recurrencia y clasificación por familia (`F1..F13`)

Antes de diseñar un arreglo, comprueba si el mismo síntoma o familia ya ocurrió en el vault:

```bash
vault run vault_search --query "<sintoma-o-modulo>" --folder 18_Bugs
vault run vault_context_pack --query "antipatrones recurrentes <familia-o-sintoma>" --top-k 5
```

Clasifica el error en una de las familias canónicas de antipatrones recurrentes:

| Familia | Qué delata | Acción mínima exigida |
|---|---|---|
| **F1** | Contratos rotos entre CLI, MCP, wheel o `tool-spec` | Validar en entorno instalado (wheel fuera del checkout) |
| **F2** | Fallos silenciosos / `except` amplio que finge éxito | Fallar cerrado con código de `ERROR_CATALOG` (`AP-51`/`AP-52`) |
| **F3** | Estado destructivo o pérdida de cambios en rollback/limpieza | Preservar trabajo sucio/binarios y probar con `DN-02` |
| **F4** | Divergencia entre código y documentación/registro | Fuente única en código + derivado regenerado (`AP-47`) |
| **F5** | Supuestos de plataforma (Windows/Linux, `cp1252`, separadores) | Encoding UTF-8 explícito, `os.pathsep`, `Path` |
| **F6** | Rutas o raíces filtradas fuera del vault (`VAULT_ROOT`, CWD) | `assert_within_vault` y respeto estricto a `VAULT_ROOT` |
| **F7** | Seguridad / aislamiento / auth laxa o por tiempo variable | Comparación constante, fail-closed, políticas por vault |
| **F8** | Concurrencia sin lock o escritura no atómica | Lock de archivo + `atomic_write_*` (`AP-36`) |
| **F9** | Compatibilidad de versión de runtime (ej. Python `<3.10`) | Guard en entrada + piso explícito en `pyproject.toml`/CI |
| **F10** | Pruebas engañosas (falso verde, no reproducen el fallo real) | Test que falla antes del fix y pasa tras el fix (`DN-01`) |
| **F11** | Cambios por defecto que rompen flujos existentes | Nuevo comportamiento estrictamente *opt-in* (`DN-09`) |
| **F12** | Alcance declarado mayor que el recorrido real | Medir cobertura contra registro completo (`AP-44`) |
| **F13** | Seguimiento disperso o sin evidencia verificable | Registrar siempre en el vault de seguimiento con comandos y SHA |

Si el defecto ya tiene impacto reproducible, documéntalo como bug en `18_Bugs/`:

```bash
vault run vault_bug_save --title "<titulo-bug>" --symptom "<sintoma-reproducible>" --root-cause "<causa-raiz-y-familia-F1..F13>" --fix "<solucion-y-guard>" --severity high --verified-by "<comando-pytest-o-gate>"
```

---

### Etapa 3 — Regla de escalamiento por recurrencia (`>= 2`)

Cuenta las ocurrencias previas de la misma familia en `02_Observability/` y `18_Bugs/`:

1. **1.ª ocurrencia:**
   - Escribe un **test TDD que reproduzca el fallo primero** (`DN-01`).
   - Implementa la corrección en la fuente única (sin duplicar lógica).
   - Verifica el verde en el test nuevo y en las pruebas afectadas.
2. **2.ª ocurrencia o superior (recurrencia confirmada):**
   - **Prohibido parchear solo el síntoma.**
   - Señala el desvío en la ronda activa para curación normativa (`SP-05`):

```bash
vault run vault_ronda --flag --kind norm_violation --target-note "<ruta-de-nota-o-norma>" --observed "Recurrencia >=2 de familia <F#> en <modulo>" --proposed-fix "Promover a guard ejecutable + test de frontera"
```

   - Agrega un **guard ejecutable** que rechace la causa raíz en tiempo de ejecución o puerta (`DN-06`) y un test que demuestre el rechazo con código de error canónico.
   - Si aplica a consolidación en lote de banderas acumuladas, inspecciona la cola de curación:

```bash
vault run vault_propagate --curate-plan --flag-status open
```

---

### Etapa 4 — Verificación real y sin atajos

Antes de declarar el error cerrado, ejecuta la verificación acorde al alcance del cambio (en serie, nunca en paralelo sobre el mismo vault):

```bash
vault run vault_audit
```

Y en el repositorio de código del proyecto (por ejemplo, en VOA):
1. Suite TDD del bug + tests del área afectada.
2. Puertas rápidas de consistencia y contratos (`vault_gate --strict --nivel rapida`).
3. Si se tocó empaquetado, CLI o MCP: puerta de instalación limpia fuera del checkout (`DN-03`).

---

### Etapa 5 — Cierre de sesión y memoria persistente (`DN-01..DN-10`)

Registra el cierre de la sesión en `04_Sessions/` usando `vault_write` con el resumen de errores atendidos, su clasificación `F1..F13`, la evidencia ejecutada y las casillas `DN-01..DN-10` marcadas **únicamente con comandos, resultados y SHA reales**:

```bash
vault run vault_write --folder 04_Sessions --title "<fecha-resumen-sesion-mejora-continua>" --content "<cuerpo-con-errores-F1-F13-y-evidencia-DN>"
```

---

## Restricciones y no-negociables

- **Cero evidencias inventadas:** una casilla `DN-*` sin comando ejecutado y resultado observado se marca como pendiente o `N/A` con motivo explícito.
- **No-derogación:** nunca borres bugs, logs de error ni notas previas para "limpiar" métricas; corrige la causa o marca `superseded_by`.
- **Respeto a `VAULT_ROOT`:** ejecuta siempre contra el vault de pruebas o el vault destino explícito, nunca contra la raíz de un repositorio de código.
- **Reporte obligatorio al usuario:** indica versión de la skill (`vault-mejora-continua v1.0`), vault destino, errores capturados/clasificados (`F1..F13`), si hubo escalamiento por recurrencia y evidencia exacta de las verificaciones.
