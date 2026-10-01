# Comparativa de comportamiento: v34.1 frente a v40.34

Fecha: 2026-10-01. Rama `product/product-readiness`.

## Qué se comparó y cómo

Un vault consumidor real (/ans) declara `applied_version: v34.1` en
`00_System/standard-version.json` y lleva sus propias tools en `data/scripts/`,
copiadas en la era v34. La comparación se hizo sobre una **copia** de ese
repositorio en `%TEMP%`; el original no se tocó (regla 7, solo lectura sobre
material ajeno).

- **v34.1**: las tools de la copia, ejecutadas con `python data/scripts/<tool>.py`.
- **v40.34**: la wheel construida desde la rama e instalada con `pip install --user`,
  ejecutada como la usaría un tercero: `vault run <tool>` con `VAULT_ROOT` apuntando
  a un vault nuevo creado con `vault init` dentro de la copia, y
  `VAULT_STRICT_ROOT=1`.

La misma batería de operaciones se lanzó contra las dos. Para cada caso se
registró el código de salida, el envelope JSON y **lo que quedó en disco**, que
es lo que decide si un `ok: true` es verdad.

## Resultado por escenario

| Escenario | v34.1 | v40.34 |
|---|---|---|
| Escritura normal | Crea la nota | Crea la nota |
| Título con `:` (`ADR-001: usar markdown`) | `ok: true` y **YAML roto** (`mapping values are not allowed here`): la nota no tiene frontmatter legible | Escalar entre comillas; frontmatter válido |
| Título con salto de línea y `status: hackeado` | **Inyección**: la nota queda con `status: hackeado` en el frontmatter | Sin inyección: el título queda como un escalar entre comillas |
| `--folder ../../fuera-del-vault` | **Escribe fuera del vault** con `ok: true` | `PREFLIGHT_REJECTED` (rc 10); nada fuera |
| `--content @file:<ruta>` | Rechazado por contenido corto; no copia el fichero | Igual (AP-11) |
| Secreto (`aws_access_key_id`) en el contenido | **Guardado en disco** con `ok: true` | Rechazado; el secreto no llega al disco |
| Sobrescribir una nota | Guarda la versión anterior en `.history/` | Igual |
| `vault_read` con `../../` hacia un `.md` externo | **Lee y devuelve el fichero externo** | `PREFLIGHT_REJECTED` |
| `vault_relation_add` sobre un JSON de relaciones corrupto | **Pierde todas las relaciones** previas y responde `ok: true` | `DATA_FILE_CORRUPT`; el fichero se conserva intacto |
| `vault_merge --conflict overwrite` | Tapa la nota sin guardar la versión anterior | Guarda la versión tapada en `.history/` y escribe bajo lock |
| `vault_validate` | rc 1, sin código de error | rc 7, sin código de error (ver abajo) |
| Raíz del vault | **Fija en el código** a la ruta de otro proyecto: ignora `VAULT_ROOT` | `VAULT_ROOT` / autodetección; `VAULT_STRICT_ROOT=1` falla en vez de adivinar |

## Lo que la comparación destapó en v40.34

La pasada no solo midió la versión vieja. Cuatro defectos de la actual salieron
de ejecutar como lo hace un tercero, y ninguno lo veía la suite:

1. **El servidor MCP instalado no completaba el handshake.** En modo stdio,
   `initialize` asignaba a una variable `clientInfo` nunca declarada; en un
   módulo ES eso es `ReferenceError`, y el servidor no respondía al primer
   mensaje de cualquier cliente. El test de instalación enviaba `initialize`
   pero no comprobaba su respuesta.
2. **`vault_validate` declaraba rota una nota válida** cuyo título contenía
   `---` entre comillas: partía el frontmatter con `split("---")` en vez de
   cerrarlo en una línea `---`, como hacen Obsidian y el parser del kernel.
   Catorce módulos activos más parten igual; quedan anotados como deuda (AP-57).
3. **La CLI emitía su propio envelope en la codificación de la consola**
   (cp1252 en Windows) cuando la salida iba a una tubería o un fichero: un
   consumidor que lee UTF-8 recibía JSON con bytes inválidos.
4. **Construir la wheel ponía en rojo la puerta AP-57**: `build/` contenía una
   copia del `.mjs` que la puerta contaba como frontera no declarada.

Cada uno se corrigió en su propio commit con un test que falla sin el cambio.

## Pendiente

- `vault_validate` sale con rc 7 y `ok: false` sin `error_code` cuando hay notas
  inválidas: es un informe, no un fallo de la tool, y el contrato no distingue
  los dos casos.
- `PERMISSION_DENIED` para un secreto detectado es correcto en efecto pero
  pobre en causa: el mensaje lo dice, el código no.
- El rechazo por falta de `tags` (AP-26) llega antes que el escaneo de secretos:
  un contenido con un secreto y sin tags se rechaza por los tags, y quien lo
  corrija se encontrará el segundo rechazo después.
