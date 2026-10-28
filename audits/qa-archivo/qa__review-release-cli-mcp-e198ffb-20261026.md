# Archivo: `qa/review-release-cli-mcp-e198ffb-20261026`

- Commit(s) sobre la rama de trabajo:
  - `7dc1a254b1f9d0282d393b331d5ad2a7da664b0b` 2026-10-26 — docs(qa): R13 valida matriz CI 25/25 y detecta doble lectura token POST
- Base: `e198ffb3477dc4f9c870bb5176fe99f43b0fb810`
- Tag de conservación: `archivo/qa/review-release-cli-mcp-e198ffb-20261026`

## Texto añadido a `audits/handoff/RESPUESTA-QA.md`



---

# Dictamen QA independiente — R13, candidato e198ffb (2026-10-26)

**Repositorio:** `devcicm/Vault-Obsidian-Architecture`  
**SHA del producto evaluado:** `e198ffb3477dc4f9c870bb5176fe99f43b0fb810`  
**HEAD del ejecutor al revisar:** `76669e4bab4a09b3eb90d61f6e3b55cf5b375447` (un commit posterior con cambios únicamente documentales en informes/buzones)  
**Rama QA:** `qa/review-release-cli-mcp-e198ffb-20261026`  
**Autoridad:** QA técnico independiente, sin autorizar decisiones del propietario.  
**Método:** lectura directa del código/diff del SHA, comparación con HEAD documental, README/informe readiness/protocolo/catálogo QG, API de GitHub Actions y jobs, logs de validación Windows 3.10 y macOS 3.11, inventario de artefactos de CI. **QA no ejecutó localmente el E2E ni la wheel de la estación del ejecutor y no tuvo acceso a `%TEMP%\\opencode\\qg-recibos-r13`.**

## Dictamen ejecutivo

**R13: CI 25/25 ACEPTADA Y VERIFICADA.** El run [40430269201](https://github.com/devcicm/Vault-Obsidian-Architecture/actions/runs/40430269201) corresponde **exactamente** a `e198ffb`, workflow `Vault CI`, `completed/success`, **25/25 jobs `completed/success`** (12 Validate Vault Spec + 12 Product gates (wheel) + Lint) y run_id coincidente en los 25 jobs. La hipótesis antigua "CI bloqueada por facturación" queda **REFUTADA**. Logs de Windows 3.10 y macOS 3.11 muestran suite integral completada (`6328 passed / 15 skipped` en esas dos columnas, diferencia de skips respecto al Windows local reportado `6330 / 13` compatible con pruebas condicionadas por plataforma), 26/26 gates y auditoría QG-02 sin violaciones dentro del sandbox de esos runners. Existen 24 artefactos CI publicados (12 JUnit y 12 SBOM); no se descargaron individualmente sus bytes. El ejecutor **reporta**, no QA ejecuta independientemente, 6330/13/0 locales, E2E 27/27 y hashes wheel/sdist.

**NO SE AUTORIZA RELEASE: `QA_REQUIRES_CHANGES`, `liberable=false`.** QG-00/QG-01 siguen bloqueados por 10 divergencias sin ratificación; QG-02 sigue bloqueado por AP-36 (`vault-backups` externo en el entorno del propietario). QG-03..07 pueden tener **subchecks/CI individualmente PASS**, pero la política de `politica_qg.py` aplica **QG-00 prerrequisito** y QG-07 exige todos QG-00..06 y decisión del propietario. No confundir CI_GREEN con RELEASE_AUTHORIZED.

## Hallazgo nuevo QA-R13-06 — P1, regresión de consumo doble y bloqueo en el servicio de tokens

**Código probado por inspección: `scripts/vault_token_service.py`, `TokenHandler`, incluido en el SHA `e198ffb`.** El arreglo R13-05 añade `_drenar_cuerpo()` para prevenir RST al rechazar un POST no autorizado, pero el camino del **POST autenticado a ruta inexistente** contiene:

```python
def do_POST(self):
    if not self._autorizado(): return
    parsed = urlparse(self.path)
    ok, payload = self._payload()       # consume Content-Length bytes
    ...
    self._drenar_cuerpo()                # intenta consumirlos otra vez
    self._send(404, {"ok": False, "error": "not_found"})
```

`_drenar_cuerpo()` ejecuta `self.rfile.read(min(length, 1 << 20))`. Después de `_payload()` con cuerpo no vacío, esos bytes **ya fueron consumidos**. Si el cliente deja la conexión abierta esperando la respuesta, el handler puede bloquearse esperando otros bytes y **nunca entregar el 404**. Los tests R13-05 ejercitan un **POST sin autorización** con Origin ajeno, pero no el POST **autorizado** a ruta desconocida. Además, un atacante puede declarar `Content-Length` y enviar menos bytes o ninguna carga: `rfile.read` antes de responder 401/403 no establece timeout explícito ni presupuesto temporal, pudiendo retener workers. Para cuerpos mayores de 1 MiB se consume solo el primer MiB, por lo que el cierre aún deja datos sin leer: la promesa de no RST no está garantizada para cargas grandes. `do_GET` también llama `_autorizado` y podría esperar un cuerpo declarado por un cliente no confiable.

**Criterio de cierre:** gestionar el cuerpo **una vez por solicitud** y solo cuando corresponda, con límite de bytes, tiempo y políticas claras de cierre; el 404 de `do_POST` no debe re-drenar un cuerpo ya leído. Tests HTTP externos con timeout real: (1) POST autenticado a ruta desconocida + JSON no vacío retorna 404 pronto; (2) los rechazos 401/403 Origin/Host siguen retornando códigos estables en las plataformas; (3) Content-Length mayor al límite no causa bloqueo; (4) cuerpo incompleto/GET con longitud declarada no retiene threads indefinidamente; (5) no se modifica ni relaja SP-04. No declarar este cierre solo por un `pytest` de 5 iteraciones sobre body `{}`. **Requiere nuevo SHA de producto y revalidación de la matriz afectada**, sin invalidar retroactivamente el hecho verificado de que R13 obtuvo 25/25.

## Arquitectura y decisiones

**QA-RC-03 / DIV-01..10:** los diez desajustes de snapshot reflejan cruces semánticos de gobernanza con meta-toolkit/autoría; el plan `audits/architecture/PLAN-B-MIGRACION-CRUZES.md` se declara `PREPARADO, NO EJECUTADO` y prescribe controles I1..I5 (independencia semántica, operacional desde wheel, retorno observable, efectos laterales y fail-closed). Es válido **recomendar B** al propietario, pero QA **no la ratifica ni activa automáticamente**. La solución debe eliminar la dependencia efectiva, no solo cambiar imports por subprocess o alterar el snapshot para obtener verde. No otorgar waiver QG-00 (catálogo no lo permite). Si propietario ratifica B, ejecutarla y verificar I1-I5, baselines, 26 puertas, CLI/MCP/E2E, luego regenerar snapshot como derivado de un estado conforme. Mientras tanto QG-00/01 siguen bloqueados.

**QG-02 y AP-36:** `audits/fase2/POLITICA-CERTIFICACION-PRODUCTO.md` es una propuesta explícita de **doble medición**: runtime limpio y sandbox canónico, sin reemplazar uno por otro. La CI demuestra 0 violaciones del sandbox en runners que **no tienen la carpeta externa**. En el entorno local del propietario se reporta **1 hallazgo AP-36 crítico** porque hay datos `vault-backups` fuera del vault. No confundir limpiar el entorno de test con subsanar o aceptar un escape de contención. Necesaria ratificación del alcance por el propietario y decisión sobre preservación/migración del backup, con inventario/hashes/propiedad y sin borrado automático. QG-02 no admite waiver bajo catálogo.

**Capacidades no cubiertas:** `INFORME-READINESS-TERCEROS.md` reconoce `plan`, `batch`, `--verify-integrity`, SSE/HTTP y exit 130 como **no ejercitados por el E2E 27/27**. No prometer cobertura integral de esas capacidades por el número 27/27; exigir un alcance de publicación fiel al PRD y pruebas selectivas antes de declarar compatibilidad funcional del release.

**Deriva del informe readiness:** el encabezado más reciente (R13) afirma CI 25/25, pero las secciones §3.3, §5.2, §6 (decisión "macOS") y §7 todavía tratan macOS como `NOT_RUN`/`EXECUTED_FAILED` y afirman que runners "no arrancan". Corregir esas secciones mediante actualización derivada desde el run final, conservando datos históricos sin volverlos estado vigente. Un documento contradictorio no sirve como contrato de liberación. `audits/handoff/RESPUESTA-DEL-EJECUTOR.md` conserva un bloque anterior a la conclusión de CI de esta ronda que señala "la CI del candidato está en marcha"; el bloque posterior es el último vigente, pero debe identificarse su supersesión y evitar ambigüedad.

**Reproducibilidad:** la wheel del E2E y otra reconstrucción reportan 706/706 miembros con bytes iguales aunque el ZIP final tenga timestamps diferentes. Es una equivalencia de contenido, **no reproducibilidad byte a byte del artefacto**; conservar los hashes explícitos y no declarar igualdad de SHA-256 de dos builds distintos.

## Orden de acciones para cierre

1. **Ejecutor, P1:** reparar QA-R13-06, añadir tests de consumo único/tiempo/cargas límites; correr regresión focalizada en Windows/Linux/macOS y tomar nuevo SHA.
2. **Ejecutor, P2:** actualizar `INFORME-READINESS-TERCEROS.md` sin alterar históricos y acreditar por caso las capacidades PRD no cubiertas que deban entrar al canal elegido; etiquetar las demás como límite no certificado.
3. **Propietario:** ratificar o enmendar **B** para DIV-01..10; ratificar la política dual de QG-02; decidir destino preservado de `vault-backups`, sin permitir purga automática. Constitución sigue DRAFT; aprobación de publicación y merges son actos separados.
4. **Ejecutor tras decisión:** aplicar migración compatible con I1-I5, demostrar eliminación real de divergencias sin cambiar baselines para esconderlas, medir ambos escenarios QG-02 y resolver AP-36 real con autorización; ejecutar suite/26 puertas/E2E sobre SHA definitivo.
5. **Evidencia / QA:** exportar (o publicar saneado) manifiesto accesible de los recibos `%TEMP%\\opencode\\qg-recibos-r13` y los del nuevo SHA con exit, artifacts/hashes, estados subcheck y contrato; QA revisa, no presupone acceso al disco local.
6. **Git:** no tocar `main`, no fusionar PR #1/#2/#3, no borrar backups ni reescribir historia, no emitir tag de release antes de todas las puertas y aceptación.

**Veredicto:** `CI_MATRIX_25_OF_25=ACCEPTED`; `QA-R13-05=FIX_VERIFIED_IN_CI_FOR_TESTED_CASE`; `QA-R13-06=OPEN_P1`; `QG-00/01=BLOCKED`; `QG-02=BLOCKED`; `QG-03..06=PASS_REPORTED_SUBCHECKS_BUT_GLOBAL_BLOCKED`; `QG-07=BLOCKED_BY_PREREQUISITES`; `RELEASE_NOT_AUTHORIZED`. QA no acepta excepciones por el propietario ni firma release.

