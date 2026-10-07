# Esquemas de nota por versión

> Derivado de `scripts/vault_contrato_nota.py` por `python scripts/vault_esquema.py --sync`.
> No se edita a mano: `--check` falla si diverge, y lo escrito aquí se pierde.

Un fichero por versión mayor del estándar, todos al lado: un vault que se quedó
en una versión anterior se valida contra lo que esa versión exigía. Cada
esquema es JSON Schema 2020-12 sobre el frontmatter ya parseado como YAML.

## Cómo se usa

La raíz de cada esquema es el contrato de una **nota de contenido**. Las notas
de `00_System/` se validan contra `#/$defs/sistema`. Desde v37, los artefactos
derivados —todo `index.md` y los que declara `vault_registry.DERIVED_ARTIFACTS`—
quedan fuera del contrato. La clase sale de la ruta de la nota, que no está en
el frontmatter: elegirla es de quien valida.

El esquema restringe **solo lo que `vault_validate` restringía** en esa versión.
Lo que el escritor pone de forma habitual va como anotación (`x-vault-*`), no
como restricción: un esquema más estricto que el validador reprobaría notas
que la tool aprueba.

Los campos que faltan se completan con `python scripts/vault_frontmatter_completar.py`
(dry-run por defecto, `--apply` para escribir), que pone lo que el escritor
habría puesto y declara el origen de cada valor.

## Versiones

| Esquema | Requeridos en una nota de contenido | Qué cambió en esa versión |
|---|---|---|
| [v18](vault-v18.schema.json) | `id`, `title`, `createdAt`, `updatedAt`, `tags`, `type` (AP-12 del manifiesto; sin validador) | AP-12 en el manifiesto: los seis campos obligatorios en toda nota; ninguna tool lo aplica |
| [v19](vault-v19.schema.json) | `id`, `title`, `createdAt`, `updatedAt`, `tags`, `type` (AP-12 del manifiesto; sin validador) | — |
| [v20](vault-v20.schema.json) | `id`, `title`, `createdAt`, `updatedAt`, `tags`, `type` (AP-12 del manifiesto; sin validador) | — |
| [v21](vault-v21.schema.json) | `id`, `title`, `createdAt`, `updatedAt`, `tags`, `type` (AP-12 del manifiesto; sin validador) | el escritor pone agent en las notas nuevas |
| [v22](vault-v22.schema.json) | `id`, `title`, `createdAt`, `updatedAt`, `tags`, `type` (AP-12 del manifiesto; sin validador) | — |
| [v23](vault-v23.schema.json) | `id`, `title`, `createdAt`, `updatedAt`, `tags`, `type` (AP-12 del manifiesto; sin validador) | — |
| [v24](vault-v24.schema.json) | `id`, `title`, `createdAt`, `updatedAt`, `tags`, `type` (AP-12 del manifiesto; sin validador) | — |
| [v25](vault-v25.schema.json) | `id`, `title` | primer validador: exige id y title, menos que AP-12, que el manifiesto de v25 sigue escribiendo igual |
| [v26](vault-v26.schema.json) | `id`, `title` | — |
| [v27](vault-v27.schema.json) | `id`, `title` | si están, el valor CIA pertenece al vocabulario y agent no está vacío |
| [v28](vault-v28.schema.json) | `id`, `title` | los scripts de escritura ponen CIA y agent |
| [v29](vault-v29.schema.json) | `id`, `title` | — |
| [v30](vault-v30.schema.json) | `id`, `title` | vocabulario de status auditado (CN-03) |
| [v31](vault-v31.schema.json) | `id`, `title` | — |
| [v32](vault-v32.schema.json) | `id`, `title` | — |
| [v33](vault-v33.schema.json) | `id`, `title` | — |
| [v34](vault-v34.schema.json) | `id`, `title` | — |
| [v35](vault-v35.schema.json) | `id`, `title` | — |
| [v36](vault-v36.schema.json) | `id`, `title` | — |
| [v37](vault-v37.schema.json) | `id`, `title`, `createdAt`, `updatedAt`, `cia_integrity`, `cia_availability`, `cia_sensitivity`, `agent`, `tags` | requeridos; CIA, agent y tags solo en notas de contenido, y los índices quedan fuera del contrato. type y status, recomendados; el escritor los pone por defecto y vault_audit penaliza su ausencia |
| [v38](vault-v38.schema.json) | `id`, `title`, `createdAt`, `updatedAt`, `cia_integrity`, `cia_availability`, `cia_sensitivity`, `agent`, `tags` | — |
| [v39](vault-v39.schema.json) | `id`, `title`, `createdAt`, `updatedAt`, `cia_integrity`, `cia_availability`, `cia_sensitivity`, `agent`, `tags` | — |
| [v40](vault-v40.schema.json) | `id`, `title`, `createdAt`, `updatedAt`, `cia_integrity`, `cia_availability`, `cia_sensitivity`, `agent`, `tags` | — |

Hasta v24 no había validador: el contrato de esas versiones es la regla AP-12
del manifiesto, que exigía los mismos campos a toda nota, de cualquier clase.
De v21 a v24 no hay manifiesto en git; el de v20 y el de v25 escriben
la regla igual, y eso es lo que se aplica. Antes de v18 el manifiesto no está
en el repositorio y no se publica esquema.

Cualquier versión se valida con el validador vigente:
`python scripts/vault_validate.py --check frontmatter --contrato v30`.

## Campos del contrato vigente

| Campo | Nivel | Clases | Norma |
|---|---|---|---|
| `id` | requerido | sistema, contenido | AP-12 |
| `title` | requerido | sistema, contenido | AP-12 |
| `createdAt` | requerido | sistema, contenido | AP-12 |
| `updatedAt` | requerido | sistema, contenido | AP-12 |
| `cia_integrity` | requerido | contenido | AP-30 |
| `cia_availability` | requerido | contenido | AP-30 |
| `cia_sensitivity` | requerido | contenido | AP-30 |
| `agent` | requerido | contenido | AP-16 |
| `tags` | requerido | contenido | AP-26 |
| `type` | recomendado | contenido | AP-27 |
| `status` | recomendado | contenido | AP-29 |
| `dq_validated_at` | opcional | contenido | — |
