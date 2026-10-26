# Política de certificación del producto — runtime limpio y sandbox canónico

**Estado: PROPUESTA. No aplicada.** El ejecutor propone; el propietario
ratifica. La política que aquí se propone no está en vigor y no se aplica sin
su decisión (informe de readiness §6, decisión 2).

## 1. Lo que se creía y lo que se ha medido

El expediente de QG-02 arrastraba **14 hallazgos del sandbox canónico**
(CN-03×5, AP-07×4, AP-64×4, AP-36×1) y un contrato de certificación sin
ratificar que debía distinguir «runtime limpio» de «sandbox canónico».

Al re-medir con el código actual (no con el del ledger, que era de `ab31bf3`),
los 14 se desglosan así:

| # | Hallazgo | Dónde vive | Quién lo puede corregir | Estado medido (2026-10-26) |
|---|---|---|---|---|
| 5 | CN-03: `status` fuera del vocabulario canónico (`accepted`, `active`) | las 5 notas semilla del sandbox | **el repo** (la semilla es versionada) | **CORREGIDO** — la semilla escribe `approved`/`verified` |
| 4 | AP-07: ADR sin Contexto/Decisión/Consecuencias | las 4 notas semilla | **el repo** | **CORREGIDO** — la semilla trae las tres secciones |
| 4 | AP-64: decisión cerrada sin `responsable` | las 4 notas semilla | **el repo** | **CORREGIDO** — con responsable distinto del agente que escribe |
| 1 | AP-36: `vault-backups` dos niveles por encima del vault | **fuera del repo**, en la carpeta del propietario | **el dueño de los datos** | **ABIERTO** — decisión del propietario (purgar o declarar) |

El cambio de fondo: **13 de los 14 no eran «contenido de evidencia que hay que
perdonar», sino contenido de nuestra propia semilla**. El sandbox se
construye con `tests/fixtures/sandbox-seed.json`, versionado en este repo; sus
notas eran defectos nuestros y se corrigen como se corrige cualquier defecto
nuestro: en el generador, no a mano en el runtime.

**Medición tras la corrección** (mismo comando, código actual):

```
python scripts/vault_norms.py --audit --root vault-sandbox --strict
→ 1 violación: AP-36 (vault-backups externo). Los tres controles
  obligatorios: AP-40, AP-42 y AP-43, los tres «ejecutado», 0 hallazgos.
```

En la CI el sandbox vive en `D:\a\<repo>\vault-sandbox`, sin `vault-backups`
dos niveles arriba: el mismo audit da **0 violaciones** y el paso de
contención (`--strict`) sale en verde.

## 2. Los dos alcances, y por qué no se sustituyen

| Alcance | Qué demuestra | Qué NO demuestra | Quién lo produce |
|---|---|---|---|
| **Runtime limpio** (escenario B) | que una instalación nueva del producto cumple el estándar que el producto certifica | nada del estado del repositorio de desarrollo | el producto, con `vault init` |
| **Sandbox canónico** (escenario A) | el estado de la evidencia y del ambiente de desarrollo: que las notas del repo también cumplen lo que el estándar exige | nada sobre una instalación de un tercero | este repo, con su fixture |

Un runtime limpio en verde **no** dice nada del sandbox, y un sandbox en verde
**no** dice nada de una instalación nueva. Se miden los dos, y cada uno responde
a su pregunta. Lo que no se hace es usar uno para tapar al otro.

## 3. Política propuesta

1. **El producto se certifica sobre el runtime limpio.** Es lo que consume un
   tercero y es lo que el producto produce. Un runtime limpio con
   violaciones es un defecto del producto, y se corrige en el producto.
2. **El sandbox canónico se certifica también, contra el mismo estándar.** Su
   contenido lo produce este repo: si una nota semilla viola CN-03, AP-07 o
   AP-64, es un defecto del fixture y se corrige en el fixture. No hay
   «contenido de evidencia» que quede exento por el hecho de ser evidencia: la
   evidencia que el estándar publica tiene que cumplir el estándar, o el
   estándar se está aplicando a sí mismo con una excepción que no existe.
3. **Lo único declarable es la contaminación externa**, y se declara con
   nombre: qué ruta, qué dueño, qué decisión se pide y qué fecha. Mientras
   siga abierta, el resultado del audit lo dice (AP-36, severidad `critical`)
   y **no se puede marcar como PASS**. No se borra desde el repositorio:
   esos datos son de su dueño (decisión 5 del informe de readiness).
4. **Un alcance no sustituye al otro en el expediente.** El QG-02 reporta los
   dos: `escenario A` y `escenario B`, con su recuento de violaciones
   respectivo. Si uno de los dos tiene hallazgos, el gate no está en verde.
5. **La corrección se hace en el generador, no en el runtime.** El sandbox es
   runtime ignorado por git: arreglarlo a mano sería arreglar un fichero que
   el siguiente `bootstrap` sobrescribe. La semilla es la fuente; el audit
   mide el resultado.

## 4. Lo que esta política NO hace

- No perdona ni un hallazgo del sandbox: los 13 de contenido se corrigieron
  porque eran **nuestros**, no porque se aceptaran.
- No borra `vault-backups` ni ningún dato fuera del vault.
- No amplía baselines ni relaja ninguna comprobación.
- No cambia el producto: el runtime limpio ya daba 0 violaciones (AP-39
  corregido en `2174bb1` y re-auditado).

## 5. Lo que el propietario tiene que decidir

| # | Decisión | Opciones | Recomendación técnica |
|---|---|---|---|
| A | ¿Se ratifica esta política? | ratificar / pedir cambios / rechazar | ratificar: no deja ningún hallazgo del sandbox sin dueño, y separa producto de entorno |
| B | ¿Qué se hace con `vault-backups` (AP-36)? | purgar / mover / declarar como histórico con fecha | **declarar con fecha y dueño**: son datos de una ejecución previa, y purgarlos es decisión de quien los tiene |
| C | ¿Se ratifica el sandbox canónico como parte del producto que se certify? | sí, con la política de §3 / no, y entonces el gate solo mira el runtime limpio | sí, con la política: es lo que impide que el estándar se aplique a sí mismo con excepciones |

Sin ratificación de A, QG-02 sigue **BLOCKED** y el ejecutor no aplica nada de
esto.
