# Acta de decisiones del propietario — 2026-10-28

**Propietario:** devcicm (titular del repositorio `devcicm/Vault-Obsidian-Architecture`).
**Canal:** sesión de Claude Code abierta por la cuenta del propietario; las seis
decisiones se tomaron como respuesta explícita a una pregunta con alternativas
y recomendación, cuyo texto figura abajo. Claude las asienta en este commit.
**Nivel de garantía:** administrativo, no criptográfico. Es el mismo que el
registro de autoridades ya declaraba (identidad git y permisos de push
compartidos). No hay firma GPG del propietario sobre este fichero.

Las fichas, con sus alternativas, riesgos y costes, están en
[`DECISIONES-PROPIETARIO.md`](DECISIONES-PROPIETARIO.md).

## DEC-01

**Decisión: (a) ratificar la Constitución arquitectónica tal cual.**
Pregunta: «La Constitución arquitectónica está en DRAFT… ¿Qué decides?» →
«Ratificar ambas (Recomendado)».
Efecto: `docs/architecture/CONSTITUCION-ARQUITECTONICA.md` pasa a RATIFICADA
sin cambiar su texto.

## DEC-02

**Decisión: aceptar DIV-01..10 (opción a del expediente: firmar las diez
entradas).** Misma respuesta que DEC-01.
Efecto: `audits/architecture/divergencias-aceptadas.yaml` con `ratificado: true`
en las diez entradas. DIV-01 se asienta con su forma vigente: «par solo en el
snapshot: ['gobernanza', 'autoria']». La ruta B (3e92962) eliminó ese par, así
que la ficha antigua «ficha divergente» ya no aparece. El snapshot `f049b1bd`
no se toca.
Medido antes del acto: `reconciliar_archify.py --check` con exit 1 y 10
divergencias. El informe R22 decía exit 0, y no era así. Después del acto:
exit 0 con 10 divergencias aceptadas por ratificación.

## DEC-03

**Decisión: opción C, certificación compuesta.** Pregunta: «¿qué certifica
QG-02 y qué hacer con vault-backups/?» → «C + archivar y purgar (Recomendado)».
Efecto: el subcheck `certificacion_compuesta` de QG-02 en
`audits/fase2/colector_qg.py` aplica
`audits/fase2/politica_certificacion_compuesta.py`. Audita un runtime recién
creado y el sandbox por separado, y es fail-closed: un escape nuevo es FAIL.

## DEC-04

**Decisión: (c) archivar con verificación de hashes y después purgar.** Misma
respuesta que DEC-03.
El residuo está en la máquina del propietario: `vault-backups/`, dos niveles
por encima del vault de pruebas de su clon. No existe en la CI ni en esta
sesión, así que la ejecución le corresponde al propietario. Los pasos y la
verificación están en
`audits/handoff/DEC-04-archivar-y-purgar.md`: inventario SHA-256, ZIP,
comprobación del ZIP contra el inventario y, solo si coincide, purga. Hasta que
se ejecute, la auditoría del sandbox en esa máquina seguirá reportando el
residuo como ESCAPE_NUEVO.

## DEC-05

**Decisión: (a) conservar la historia con el riesgo documentado.** Pregunta:
«¿conservar o reescribir la historia de Git?» → «Conservar con riesgo
(Recomendado)».
Efecto: no se reescribe nada. La exposición medida (rutas personales y nombre
de cuenta, sin credenciales) queda como riesgo aceptado.

## DEC-06

**Decisión: aprobar con condiciones.** Pregunta: «si QG-00..06 salen PASS en el
candidato nuevo y la CI de 17 jobs queda verde, ¿cómo autorizas la publicación
de v41.23?» → «Aprobar con condiciones (Recomendado)».
Condiciones:
1. El candidato es el SHA que fija `audits/fase2/CANDIDATO-RELEASE.yaml`, con
   QG-00..06 en PASS por el colector y la CI de ese SHA en `completed/success`
   con todos sus jobs.
2. El alcance es Windows + Linux con Python 3.9–3.12. macOS no se promete.
3. Quedan declaradas como límite las capacidades que el E2E no ejerce:
   `plan`, `batch`, `--verify-integrity`, MCP por SSE/HTTP y la salida 130.
4. Los controles AP-40/42/43, ejecutados desde una wheel limpia, devuelven
   `no_ejecutado` (I2-a pendiente). Es un control de mantenimiento del
   estándar, no del producto, y queda declarado.
5. La publicación consiste en el tag `v41.23` y un GitHub Release con wheel,
   sdist, SHA-256 y SBOM.

Si alguna condición no se cumple, la autorización no se aplica.

**Lo que esta decisión deja fuera, a la vista:** el catálogo pone la aceptación
de QG-00..06 y la verificación de QG-07 en manos del QA arquitectónico
independiente. Entre las alternativas estaba «Esperar dictamen QA», y el
propietario eligió no esperar. Para v41.23, la aceptación descansa en los
recibos del colector (`colector_qg.py --ejecutar`, uno por subcheck y por SHA)
y en la CI externa. El dictamen QA independiente puede emitirse después de
publicar, sobre el mismo SHA; si encuentra un defecto, se trata como incidencia
del release publicado.
