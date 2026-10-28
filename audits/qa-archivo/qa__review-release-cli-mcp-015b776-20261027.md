# Archivo: `qa/review-release-cli-mcp-015b776-20261027`

- Commit(s) sobre la rama de trabajo:
  - `e47d62f0135cd054be2267b77a72fc26007fc97d` 2026-10-26 — docs(qa): dictamen independiente R14 015b776, CI 25/25 y bloqueos release
- Base: `08f8cefe32d38b4e2571f19ec8c26dcfc8924363`
- Tag de conservación: `archivo/qa/review-release-cli-mcp-015b776-20261027`

## Texto añadido a `audits/handoff/RESPUESTA-QA.md`



---

# Dictamen QA R14 — Candidato 015b776 y documentación 08f8cef (2026-10-27)

**Candidato de producto:** `015b7765b80cac21c6dcf859ae075d036cd01def`.  
**Tree de producto declarado:** `d190fd243567556e824795154b6fd44bd76309d5`.  
**Commit documental examinado:** `08f8cefe32d38b4e2571f19ec8c26dcfc8924363`.  
**Rama del ejecutor:** `work/release-cli-mcp-20261025`.  
**QA independiente:** `qa/review-release-cli-mcp-015b776-20261027` (nacida desde el commit documental 08f8cef para revisar expediente completo; no modifica producto).  
**Dictamen antecedente:** `7dc1a254b1f9d0282d393b331d5ad2a7da664b0b` sobre `e198ffb`.

## Método y límites

Se leyó código de `scripts/vault_token_service.py`, tests HTTP, catálogo QG, `INFORME-READINESS-TERCEROS.md`, `CANDIDATO-RELEASE.yaml`, `RECIBOS-R14-MANIFIESTO.md`, `DECISIONES-PROPIETARIO.md`, `PROTOCOLO-QA.md`, `PLAN-B-MIGRACION-CRUZES.md`, política propuesta QG-02 y el inventario de deuda; se consultó **en vivo** la CI `40442954197` (25 jobs completed/success, workflow completed/success y SHA correcto), PR #3 DRAFT, diferencias 015b776→08f8cef, ramas y releases. **QA NO ejecutó independientemente pytest, las 26 puertas, E2E ni la rueda; sus resultados locales provienen de recibos publicados y de la declaración del ejecutor.** Los recibos originales están fuera de Git, mientras el reporte publicado ofrece hashes truncados por subcheck y el agregado completo: no presentar ese reporte como una firma independiente de la ejecución local.

## Dictamen

**QA-R13-06 CORREGIDO, revisión estática favorable y CI 25/25 real. RELEASE NO APROBADO.** La nueva implementación consume el cuerpo HTTP una sola vez al inicio, con límite de 1 MiB y plazo de 5 s; `_payload()` solo decodifica lo ya recibido y mapea exceso a 413. Cuatro nuevos tests ejercitan rutas 404/401/403/413 y presupuesto; el run del SHA `015b776` completó 25/25 jobs exitosamente. Se **reconoce cierre técnico focalizado del P1** (sin afirmar ejecución QA local).

Los resultados locales reportados para el SHA incluyen suite **6334 passed / 13 skipped / 0 failed**, puertas **26/26** y recorrido wheel **27/27**. El compare `015b776 → 08f8cef` cambia solo manifiestos, informes y buzones, no producto. **CI 25/25 ≠ aprobación QG-07 ≠ aprobación QA global ≠ autorización propietario**.

### Bloqueos de release actuales

- **QG-00 y QG-01: BLOCKED**, reconciliador Archify exit=1 con DIV-01..10 no resueltas. `vault_arch` conforma la baseline de 5 cruces, pero no elimina ni acepta la divergencia. **DEC-02**: el propietario debe elegir una ruta. B es una **migración con código y re-certificación**, no una simple ratificación; los estudios nuevos muestran que el puerto propuesto **no funciona desde wheel instalada** (`installed:false`, exit 3) y que la variante de proceso ingenua cuesta ~149 s contra ~2,4 s (≈60×). La solución B requiere escoger enmiendas I2 y rendimiento, implementar, cumplir I1–I5, repetir CI y pedir QA nueva. C exige política formal y QA, no aceptación automática ni waiver de QG-00.
- **QG-02: BLOCKED**, un residuo AP-36 externo a la instalación `vault-backups`, además de contrato aún no ratificado para certificar runtime limpio y sandbox. **DEC-03 + DEC-04** deben resolverse; la opción C compuesta no permite declarar PASS a un hallazgo crítico sin tratamiento formal. No mover, archivar ni borrar los 66 ficheros (~834 KiB) sin autorización del dueño y preservación por hashes.
- **QG-03 a QG-06:** recibos locales de subchecks con `PASS` reportado, pero la política de prerequisitos globales mantiene el release `BLOCKED`; no confundir evidencia satisfactoria de un gate con liberación.
- **QG-07:** CI del candidato aprobó 25/25, pero política fail-closed por QG-00/01/02; `liberable:false` correcto.
- **DEC-01 Constitución DRAFT, DEC-05 historia publicada, DEC-06 autoridad final:** no ratificados. No existen tag ni GitHub Release; PR #3 permanece OPEN/DRAFT, `main` intacta.

### Observaciones documentales adicionales (P2, requieren reconciliación, NO maquillar)

**QA-R14-DOC-01: TD-0008 obsoleta y contradictoria.** `audits/fase2/inventario-deuda.yaml` conserva `TD-0008: vigente` describiendo borrado sin backup, símbolo `shutil.rmtree(entry)`, `decision: pending` y `DISENO unicamente: scripts/vault_init.py sin cambios`; `DECISIONES-PROPIETARIO.md` DEC-06 y el informe de readiness §7 lo reiteran como P1 `--clean` diseñado-sin-implementar. **Contradicción con el código vivo de `scripts/vault_init.py` en 015b776**: `_preparar_clean`, copia/cuarentena, `VERIFY_BACKUP`, hash, `--confirm`, `--dry-run`, rollback y tests/QA previas de alcance. Esto es deriva del registro histórico, no prueba de que el producto carezca del mecanismo. **Acción:** añadir estado vigente al registro canónico o supersesión con commit correctivo y pruebas verificadas, preservando campos históricos como observación de su SHA original; corregir DEC-06 y readiness sin falsear historia. Confirmar que el entry point de distribución usa efectivamente esa implementación antes de retirar la alerta P1.

**QA-R14-DOC-02: manifiesto no apto como registro mecánicamente validable de un release.** `CANDIDATO-RELEASE.yaml` guarda `product_sha`, `wheel_sha256`, `sdist_sha256`, `suite_junit_sha256` como **cadenas con comentarios y prosa anexada**, en vez de hashes puros; `documentation_sha` sigue sin valor real (texto `el HEAD... cuando QA dicte`) aun cuando el commit documental ya se publicó. Un parser puede cargar el YAML, pero NO validar esas cadenas como identidades SHA-1/SHA-256 sin heurísticas ad hoc. **Acción:** elaborar un manifiesto externo/versionado mecánicamente validable con hashes como campos hexadecimales puros y metadatos en claves separadas (`artifact_filename`, `digest`, `evidence_note`, `doc_parent_sha`); si se almacena dentro de Git, evitar circularidad de SHA mediante la relación `product_sha` y el SHA de publicación obtenido por Git/ref externo. Añadir tests negativos de hash mal formado y de SHA ajeno. No cambiar los hashes por estética ni afirmar reproducibilidad bit a bit: el agente documenta equivalencia por contenido 706/706, no ZIP determinista.

**QA-R14-DOC-03: fuentes de readiness con fechas/estados anteriores.** El informe presenta la cabecera R12, un HEAD viejo `408eb23` y líneas de matriz de `e198ffb` junto con su nuevo §10 R14, y la `MATRIZ-CAPACIDAD-PRODUCTO.md` conserva macOS `NOT_RUN` aunque CI del candidato 25/25 PASS; el párrafo §6 afirma seis decisiones pero trata a macOS como una decisión ya cerrada, mientras `DECISIONES-PROPIETARIO.md` contiene DEC-01..06 con otras identidades. **Acción:** añadir una cabecera canónica de estado vigente identificada por product_sha `015b776`, dejar los cortes anteriores rotulados HISTÓRICO y reconciliar enlaces/decisiones/capacidades. No borrar medidas históricas.

**QA-R14-PORT-01: superficie distribuida no totalmente certificada frente a PRD.** E2E 27/27 no mide todos los contratos anunciados: `plan`, `batch`, `--verify-integrity`, SSE/HTTP ni salida 130. Elegir para release un **alcance explicitamente limitado** o ejecutar los recorridos que faltan; no anunciar soporte certificado de funciones con estado `NOT_RUN` en la matriz.

## Ruta ordenada para concluir

1. **Propietario decide DEC-02** con base en las enmiendas I2/rendimiento y consecuencias. Si B, nueva ronda técnica y nuevo SHA/CI/E2E/QA; si C, expediente de waiver formal y aceptación QA, no aprobación automática.
2. **Propietario decide DEC-03/04**, evitando excepciones automáticas a QG-02; resolver el residuo externo con custodia e integridad, y política sin relajar detecciones.
3. **Agente corrige deriva documental** (TD-0008, manifiesto, encabezados de readiness, matriz de capacidad) y entrega controles sobre SHA correcto sin false PASS.
4. **QA revisa el nuevo estado**; QG-00..QG-07 deben quedar en PASS para el candidato final o permanece BLOCKED.
5. **DEC-01 ratificación de Constitución; DEC-05 postura sobre historia; DEC-06 autorización explícita posterior a QA.** Solo entonces permitir tag y release conforme al canal aprobado.

**Estado formal:** `QA-R13-06=ACCEPTED_SCOPED`; `CI_MATRIX_25_OF_25=VERIFIED`; `PRODUCT_TESTS=REPORTED_NOT_INDEPENDENTLY_EXECUTED`; `QA-RELEASE=BLOCKED`; `QG-00/01/02=BLOCKED`; `QG-07=BLOCKED_BY_POLICY`; `OWNER_DECISIONS=OPEN`; `NO_MERGE, NO_RELEASE, MAIN_UNCHANGED`.

