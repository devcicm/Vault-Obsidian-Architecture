# Acta de decisiones del propietario — 2026-10-29

**Propietario:** devcicm (titular del repositorio `devcicm/Vault-Obsidian-Architecture`).
**Canal:** sesión de Claude Code abierta por la cuenta del propietario. La decisión
es una declaración explícita del propietario en el chat, cuyo texto figura abajo.
Claude la asienta en este commit.
**Nivel de garantía:** administrativo, no criptográfico. Es el mismo que el acta de
2026-10-28: identidad git y permisos de push compartidos, sin firma GPG sobre este
fichero.

## DEC-06 (v41.25)

**Decisión: autorizar la publicación de v41.25 condicionada a que se cumplan las
condiciones de QA.** Declaración literal del propietario: «Yo devcicm carlos Ivan
cm declaró que si las condiciones de qa se cumple firmo el acta».

Esta acta no extiende la DEC-06 de v41.23: es una decisión nueva sobre otro
candidato, como pedía `owner_decision_ref_note`.

Condiciones de QA y su medida:

1. **El candidato es el SHA que fija `audits/fase2/CANDIDATO-RELEASE.yaml`
   (`e101004`)**, con QG-00..07 en PASS (recibos en `audits/fase2/recibos-R26-e101004/`)
   y la CI de ese SHA en `completed/success` con todos sus jobs: run 40843103452,
   27/27. Cumplida.
2. **La publicación se hace sobre un descendiente del candidato, `e3cc185`**
   (tag `v41.25`). Entre ambos hay cambios de documentación, tests, la constante
   `GOBIERNO_DOC` de `vault_servicio` y la evidencia de `.archify/`. La CI de
   `e3cc185` es run 40896422816, `completed/success`, 27/27 jobs. Cumplida.
3. **Alcance:** Windows + Linux con Python 3.9–3.12. macOS no se promete.
4. **Límites declarados:** las capacidades que el E2E no ejerce (`plan`, `batch`,
   `--verify-integrity`, MCP por SSE/HTTP y la salida 130), y los controles
   AP-40/42/43 desde una wheel limpia, que devuelven `no_ejecutado`.
5. **Publicación:** el tag `v41.25` y un GitHub Release.

Si alguna condición no se cumple, la autorización no se aplica.

**Lo que esta decisión deja fuera, a la vista:**
- No existe dictamen QA arquitectónico independiente sobre este SHA
  (`qa_verdict_ref: PENDIENTE`). El propietario autoriza sin esperarlo; puede
  emitirse después sobre el mismo SHA, y si encuentra un defecto se trata como
  incidencia del release publicado.
- La evidencia visual de `.archify/` se verificó en local con procedencia vigente,
  pero los recibos publicados llevan rutas relativas (regla de publicación limpia) y
  el verificador de procedencia de archify no los acepta en ese formato. No es
  reproducible desde el repositorio publicado.
- El tag y la release de v41.25 se publicaron el 2026-10-29, antes de que esta acta
  existiera, por orden del propietario en el chat («Procede»). Esta acta regulariza
  el registro; no cambia lo publicado.
