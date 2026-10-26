<!-- propiedad: CARLOS IVAN CM — revisión: manual -->
# CONSTITUCIÓN ARQUITECTÓNICA — Vault-Obsidian-Architecture

> **ESTADO: DRAFT — PENDIENTE DE RATIFICACIÓN.**
> Este documento es una **propuesta de norma**, no una imposición retroactiva.
> No cambia ningún contrato vigente ni deroga ninguna norma existente: las
> describe, las ordena y propone las que faltan. Ratificarlo es una decisión
> del propietario (ver §H, «Autoridad»).
>
> Capa de integración: no sustituye a `vault-obsidian-architecture.md`
> (manifiesto), a `scripts/vault_arch.py` (registro de contextos y puertos), al
> catálogo QG, ni a los inventarios existentes. Su función es **enlazarlos**.

**Versión de la propuesta:** 0.1 (2026-10-25) · **Rama:** `work/release-cli-mcp-20261025`
**Generado/verificado contra:** el SHA del árbol en que se redacta; los recuentos
de este documento salen de `audits/architecture/inventario-maestro.yaml` y
`audits/architecture/grafo-trazabilidad.json`, generados por
`audits/architecture/generar_inventario.py`.

---

## A. Identidad

**Qué es.** Un producto distribuible (CLI + MCP) que da a un agente de IA
memoria documental persistente, auditable y gobernada sobre markdown plano, sin
base de datos, sin embeddings y sin servicio externo.

**Naturaleza técnica.** Un *toolkit* (biblioteca + CLI + servidor MCP) con un
**runtime** de datos (el vault del usuario) y un **estándar** de gobernanza que
el toolkit verifica. Tres cosas distintas que el repositorio mezcla en un
mismo árbol: el producto, la herramienta de desarrollo y la evidencia.

**Frontera de producto.** Lo que se distribuye y se puede instalar sin el
checkout: la wheel/sdist, sus entry points (`vault`, `vault_gobernanza`), el
servidor MCP empaquetado y el catálogo de tools. **No** es frontera de producto
el conjunto de scripts de mantenimiento del propio estándar: 28 módulos
(`vault_gate`, `vault_criterios`, `vault_arch`, `vault_norms`, …) que son
*herramienta de desarrollo* y no viajan en la wheel
(`audits/architecture/inventario-maestro.yaml` → `RES-ARTE-*` y
`empaquetado/fuera-de-la-wheel.json`).

**Naturaleza de cada cosa:**

| Cosa | Dónde vive | Regla |
|---|---|---|
| Código fuente | `vault/`, `scripts/`, `normas/`, `mcp/nodejs/` | es el producto o su herramental; versionado |
| Herramienta de desarrollo | los 28 módulos de mantenimiento | gobiernan el estándar; no se distribuyen |
| Documentación | `README.md`, `docs/`, ADR | se deriva o se declara |
| Evidencia | `audits/**/logs/`, recibos externos |outputs de una ejecución, atados a un SHA |
| Runtime | el vault del usuario (`~/.vault-master/…`, `vault-sandbox/`) | dato del usuario; nunca se borra en silencio |
| Artefacto distribuible | `dist/*.whl`, `dist/*.tar.gz` | producto publicado; con hash |

---

## B. Propósito

**Por qué existe.** El agente pierde el contexto entre sesiones y entre
proyectos, y cuando lo conserva lo conserva sin trazabilidad: nadie sabe de
dónde salió un dato ni quién lo cambió. El sistema convierte la memoria del
agente en **documento versionado, con authorship, con changelog y con
verificación**.

**Problemas que resuelve:** memoria persistente; integridad del formato
(frontmatter, secciones, vocabulario); trazabilidad de cambios; detección de
contaminación y de efectos fuera del vault; paridad entre superficies (CLI y
MCP); gobernanza del propio estándar.

**A quién:** (a) al equipo que opera un vault con agentes; (b) al usuario
final que instala el paquete; (c) al mantenedor del estándar, que audita el
producto con las mismas reglas que exige.

**Compromisos funcionales mantenidos:** el vault es texto plano legible con
cualquier editor; sobrevive a la desaparición del toolkit; el runtime no
depende del checkout; toda escritura queda registrada; el producto no exige
servicio externo.

---

## C. Promesa de producto

| Promesa | Qué significa | Cómo se verifica |
|---|---|---|
| **CLI** | operar el vault desde la terminal sin Python | `vault init/doctor/status/run/tools/mcp-path` |
| **MCP** | la misma capacidad por protocolo, con los mismos contratos | `initialize → tools/list → tools/call`; 97 tools |
| **Instalación de terceros** | instalar y usar sin el repositorio | recorrido E2E sobre wheel, 27/27 |
| **Recuperación de datos** | ninguna operación destructiva deja datos irrecuperables | cuarentena verificada por hash + rollback; 23 pruebas |
| **Gobernanza** | las verificaciones dicen si se ejecutaron | `checks[]` + `completo`; collector fail-closed |
| **Verificabilidad** | la evidencia pertenece al SHA que declara | recibos con artefacto y hash por subcheck |

**Límites asumidos:** compatibilidad declarada en Python 3.9–3.12 y
Windows/Linux/macOS (**aún no acreditada por CI concluyente**); un único
usuario local por vault; sin sincronización ni multi-tenant; el MCP expone
herramientas locales (sin autenticación propia: la seguridad es del proceso
que lo lanza).

---

## D. Premisas

Si alguna de estas deja de ser cierta, las promesas de §C dejan de estar
garantizadas:

1. **P-01** El runtime no depende del checkout: la wheel es autosuficiente.
2. **P-02** Los datos del usuario no se eliminan en silencio: toda operación
   destructiva deja una vía de recuperación comprobable.
3. **P-03** Una verificación que no se ejecutó **no** es un resultado: los
   verificadores declaran su estado y sus artefactos.
4. **P-04** CLI y MCP comparten contratos de negocio: una operación tiene el
   mismo efecto por las dos superficies.
5. **P-05** La evidencia pertenece al SHA que declara (y solo a ese).
6. **P-06** Un resultado incompleto no equivale a éxito.
7. **P-07** Toda dependencia entre contextos tiene dueño y contrato
   declarado.
8. **P-08** Lo derivado se regenera desde su fuente; no se edita a mano.
9. **P-09** Lo que no se puede verificar se declara como no verificado.

---

## E. Invariantes

| ID | Invariante | Justificación | Alcance | Verificador | Evidencia | QG | Consecuencia | Autoridad |
|---|---|---|---|---|---|---|---|---|
| **INV-01** | Ningún side-effect se escribe fuera del vault root | datos del usuario fuera del control del producto | runtime | AP-36 (auditoría) | `vault_norms --audit` (AP-36) | QG-02 | auditoría no conforme | QA |
| **INV-02** | Una operación destructiva deja recuperación comprobable | pérdida irreversible | CLI | `tests/test_vault_init_clean.py` (23) | logs de las pruebas | QG-02 | rollback verificado | QA |
| **INV-03** | Un control no ejecutado no se reporta como ejecutado | gobernanza mentirosa | gobernanza | `tests/test_ap40_42_43_estados.py` | `checks[]`/`completo` | QG-02 | auditoría incompleta | QA |
| **INV-04** | Una evidencia acredita solo el SHA que declara | trazabilidad | evidencia | `tests/test_colector_qg.py` | recibos con hash | QG-00 | PASS no acreditado | QA |
| **INV-05** | Un Quality Gate en PASS exige ejecución real de todos sus subchecks | certificación | calidad | colector (subchecks por puerta) | recibos externos | QG-07 | PASS sin ejecución | QA |
| **INV-06** | La CLI y MCP producen el mismo efecto | paridad de producto | producto | `audits/fase2/paridad_cli_mcp.py` | paridad 5/5 | QG-05 | divergencia de contrato | QA |
| **INV-07** | Ningún artefacto distribuido importa módulos no distribuidos | distribución | paquete | `vault_servicio --check` | `shipped_imports_of_excluded: []` | QG-06 | wheel no ejecutable | QA |
| **INV-08** | Ningún cruce de contextos queda sin dueño, contrato o fecha | gobernanza de dependencias | arquitectura | `vault_arch --check --strict` | `arch-baseline.json` | QG-01 | deuda invisible | propietario (fichas) / QA |
| **INV-09** | Lo derivado se regenera desde su fuente | deriva desactualizada | documentación | `vault_doc_counts --check`, `vault_doc_sync --check` | derivados regenerados | QG-06 | documentación mentirosa | QA |
| **INV-10** | El estándar no se aplica a sí mismo con reglas que el propio producto incumple | coherencia | estándar | `vault_norms --audit` sobre runtime limpio | INC-0015 (AP-39) | QG-02 | contradicción | QA |
| **INV-11** | Las baselines solo encogen | deuda congelada | gobernanza | guards con baseline | `vault_arch`, `vault_criterios` | QG-01 | verde fabricado | QA |
| **INV-12** | Ningún procedimiento destructivo se ejecuta sobre datos reales | datos del usuario | operativa | recorrido E2E sobre sandbox descartable | `recorrido_terceros_r07.py` | QG-05 | pérdida de datos | propietario |

---

## F. Gobierno del cambio

```
PROPÓSITO → PROMESA → PREMISA → REQUISITO → CONTRATO → RECURSO
   → IMPLEMENTACIÓN → VERIFICACIÓN → EVIDENCIA → QUALITY GATE
   → DICTAMEN → DECISIÓN → ESTADO VERSIONADO
```

Trazabilidad en sentido contrario: desde un **estado versionado** se puede
volver a la evidencia, al verificador, al contrato, al recurso, al requisito y
a la promesa. Esa cadena es la que materializa
`audits/architecture/grafo-trazabilidad.json` (aristas `DERIVED_FROM`,
`PRODUCES_EVIDENCE`, `VERIFIES`, `SUPERSEDES`…).

Reglas de la secuencia:

1. Una decisión del propietario se registra **antes** de codificarla.
2. Un recurso nuevo se inventaría en `inventario-maestro.yaml` **derivado** de
   su fuente, no escrito a mano.
3. Toda corrección técnica lleva ficha de impacto (matriz CHG-XXXX) y prueba
   negativa, positiva y de regresión.
4. Un Quality Gate no se declara PASS sin ejecución registrada.
5. Un cambio de contrato público o una aceptación de deuda requiere
   ratificación expresa del propietario.

---

## G. Relación con lo que ya existe (no duplica)

| Este documento | Registro canónico que NO sustituye |
|---|---|
| §A–F (identidad, promesas, premisas, invariantes) | `vault-obsidian-architecture.md` (manifiesto) |
| §E (invariantes) | `normas/` (82 paquetes con guard) y sus verificadores |
| §F (gobierno) | `scripts/vault_gate.py` (26 puertas) y `vault_arch.py` |
| Inventario maestro | `scripts/vault_arch.py:CONTEXTS`, `vault_mcp_catalog.TOOLS_CATALOG` |
| Grafo de trazabilidad | `scripts/arch-baseline.json` (baseline de cruces) |
| Fichas de divergencias | `audits/fase2/reconciliar_archify.py` + snapshot `.archify/` |
| Hallazgos QG-02 | `audits/fase2/inventario-deuda.yaml` (deuda) |
| Registro de veredictos | buzones `audits/handoff/RESPUESTA-QA.md` (ramas QA) |

Todo lo nuevo es **aditivo**: capa de integración sobre registros vivos.

---

## H. Autoridad y ratificación

| Materia | Autoridad |
|---|---|
| Aceptación del producto y del release | **Propietario** |
| Dictamen técnico independiente | **QA** |
| Correcciones dentro del alcance | ejecutor (dentro de una orden) |
| Cambios de contrato público, excepciones de deuda, reescritura de historia | **Propietario** |

**Ratificación pendiente de este documento:** el propietario debe confirmar
(a) la frontera de producto de §A, (b) las promesas de §C y sus límites, (c) los
invariantes de §E y (d) las premisas de §D. Hasta entonces es DRAFT y no
obliga a ninguna puerta.

---

## I. Lo que esta constitución NO hace

- No deroga ni reescribe ninguna norma, ADR, catálogo o contrato vigente.
- No declara conforme lo que no está verificado.
- No convierte deuda en aceptada.
- No sustituye el manifiesto por un segundo manifiesto: este documento lo
  **enlaza**.
