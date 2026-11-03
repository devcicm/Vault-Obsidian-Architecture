# Acta de decisiones del propietario — 2026-11-03

**Propietario:** devcicm (titular del repositorio `devcicm/Vault-Obsidian-Architecture`).
**Canal:** sesión de Claude Code abierta por la cuenta del propietario. La decisión
es una declaración explícita del propietario en el chat, cuyo texto figura abajo.
Claude la asienta en este commit.
**Nivel de garantía:** administrativo, no criptográfico. Es el mismo que el acta de
2026-10-28: identidad git y permisos de push compartidos, sin firma GPG sobre este
fichero.

## DEC-07 (v41.26)

**Decisión: autorizar la publicación de v41.26 condicionada a que se cumplan las
condiciones de QA.** Declaración literal del propietario: «Sí: acta nueva con las
condiciones de DEC-06».

Esta acta no extiende la DEC-06 de v41.23 ni la DEC-06 del 2026-10-29 (v41.25): es
una decisión nueva sobre otro candidato, como pedía `owner_decision_ref_note`.

Condiciones de QA y su medida:

1. **El candidato es el SHA que fija `audits/fase2/CANDIDATO-RELEASE.yaml`
   (`ad66a3d`)**, con QG-00..07 en PASS (recibos en
   `audits/fase2/recibos-R27-ad66a3d/`) y la CI de ese SHA en `completed/success`
   con todos sus jobs: run 41647862242, 27/27. Cumplida.
2. **La publicación se hace sobre un descendiente del candidato**, el tag
   `v41.26`, con su propia CI en `completed/success`. Entre el candidato y el tag
   hay commits de documentación —el acta, estas notas, el manifiesto del
   candidato y los recibos—, que no cambian el producto.
3. **Alcance:** Windows + Linux con Python 3.9–3.12 (lo ejerce la CI) y Python
   3.14 en local (Windows 10). macOS no se promete.
4. **Límites declarados:** las capacidades que el E2E no ejerce (`plan`, `batch`,
   `--verify-integrity`, MCP por SSE/HTTP y la salida 130), y los controles
   AP-40/42/43 desde una wheel limpia, que devuelven `no_ejecutado`.
5. **Publicación:** el tag `v41.26` y un GitHub Release.

Si alguna condición no se cumple, la autorización no se aplica.

**Lo que esta decisión deja fuera, a la vista:**

- No existe dictamen QA arquitectónico independiente sobre este SHA
  (`qa_verdict_ref: PENDIENTE`). El propietario autoriza sin esperarlo; puede
  emitirse después sobre el mismo SHA, y si encuentra un defecto se trata como
  incidencia del release publicado.
- La autorización es sobre **un** candidato: si el producto cambia después, el
  tag deja de ser un descendiente del candidato certificado y la publicación
  queda sinulo.
- El primer `qg-receipts` real ocurre en esta publicación (B-04): hasta ahora
  los recibos versionados eran de corridas a mano. Sus recibos entran después
  de la publicación, con su procedencia, y saldan la deuda declarada.

## DEC-08 (v41.26) — ratificación de dos divergencias del reconciliador

**Decisión: ratificar dos divergencias concretas del reconciliador Archify.**
Declaración literal del propietario: «Ratificar las dos divergencias».

Ambas tienen la misma causa: el par de contextos se **retiró** del presupuesto
de cruces porque el cruce se resolvió por diseño, y el snapshot `.archify/`
(`f049b1bd`) es de una revisión anterior y todavía lo lista.

| Divergencia | Causa | Evidencia |
|---|---|---|
| `par solo en el snapshot: ['gobernanza', 'meta_toolkit']` (DIV-02, cuya forma cambió al retirarse el par) | A-5: el catálogo llega a Gobernanza por el puerto declarado `CatalogoTools` | `b883083` |
| `par solo en el snapshot: ['kernel', 'autoria']` (DIV-11, nueva) | A-3 y A-4: los productores se ofrecen al importarse y el kernel pide por puerto | `49df951` |

Lo que se ratifica es **que la foto antigua listaba cruces ya resueltos**. No se
aceptan los cruces: los dos pares siguen retirados del registro, que es la
verdad, y `presupuesto_de_cruces_huerfano()` sigue sin admitir un par resuelto.
La evidencia queda en `audits/architecture/divergencias-aceptadas.yaml`, con
`ratificado: true` y el commit que resolvió cada par.

Esta decisión **no** re-toma el snapshot de Archify (opción (b) de DEC-02): esa
salida sigue sin ejecutar, y sin un acto expreso.
