# Arquitectura AS-IS y TO-BE — dos vistas, no una

**AS-IS:** lo que el código y los contratos hacen hoy (verificado contra el
código, el registro de contextos y el catálogo QG).
**TO-BE:** lo que la constitución y las decisiones documentadas apuntan a.
**El TO-BE no es arquitectura implementada.** Cada diferencia lleva
identificador, causa, beneficio, costo, riesgo, pasos, pruebas y decisión.

## 1. AS-IS — arquitectura vigente

### Contextos (10, del registro `scripts/vault_arch.py`)

`autoria` · `ciclo_de_vida` · `cli` · `consulta` · `durabilidad` ·
`gobernanza` · `grafo` · `indices` · `kernel` · `meta_toolkit`

### Puertos (23) y cruces (5 fuera de puerto, con baseline)

| Cruc exterior | De → a | Dónde vive hoy | Estado |
|---|---|---|---|
| `gobernanza → meta_toolkit` | componer AP-40/AP-42 | `vault_norms` (fachada de mantenimiento) | `a_eliminar`, plazo 2027-06-30 |
| `gobernanza → autoria` | componer AP-43 | `vault_norms` | `a_eliminar`, plazo 2027-06-30 |

### Composición real

```
usuario ──> vault (CLI de producto)  ──> vault.product_cli ──> vault_toolkit.*
                    │
                    └──> servidor MCP (node, stdio JSON-RPC) ──> 97 tools
                                        (mismo runtime, mismos contratos)
runtime (vault del usuario): secciones 00..99, .history, change-log, índices
estándar (herramienta de desarrollo, NO se distribuye): 28 módulos de
  mantenimiento (vault_gate, vault_arch, vault_norms, vault_criterios, …)
```

### Módulos distribuidos

- `vault/` (producto y su núcleo), `scripts/` (herramiental),
  `vault_toolkit/` (lo que se empaqueta), `mcp/nodejs/` (servidor MCP).
- 28 módulos quedan **fuera** de la wheel (`empaquetado/fuera-de-la-wheel.json`).

### Gobernanza, calidad y evidencia

- 26 puertas (`vault_gate`), 82 normas en paquete, 97 tools en el catálogo.
- Quality Gates: catálogo (`catalogo-qg.yaml`) + política ejecutable
  (`politica_qg.py`) + colector con subchecks (`colector_qg.py`).
- Evidencia: logs por ronda, recibos externos por subcheck, dictamen QA en
  ramas propias.

### Deuda viva

5 cruces declarados, 14 hallazgos reales en el sandbox canónico, 1 defecto de
producto en runtime limpio (AP-39), QG-07 bloqueado por CI.

## 2. TO-BE — arquitectura objetivo

| Límite deseado | Estado | Evidencia del gap |
|---|---|---|
| El dueño de cada control publica su contrato y gobernanza lo **consume** | pendiente | 5 cruces vivos |
| Los cruces del grafo de producto son cero | pendiente | `shipped_imports_of_excluded: []` ya achieved; falta el grafo completo |
| Ningún Content Gate depende de la semántica de another's namespace | **alcanzado** | los Content Gates actuales son context-scoped |
| Evidencia y dictámenes son reproducibles por un tercero | parcial | recibos externos atados a SHA; el auditor histórico mide parches, no blobs |
| El producto cumple las normas que certifica | pendiente | INV-10 / INC-0015 (AP-39 en runtime limpio) |
| La matriz multiplataforma está acreditada por CI | pendiente | CI en cola (evidencia de proveedor) |
| La documentación de producto refleja el comportamiento real | parcial | PRD CLI/MCP no contrastados (NO_VERIFICADO) |

## 3. Diferencias AS-IS → TO-BE

| ID | Diferencia | Causa | Beneficio | Costo | Riesgos | Pasos | Pruebas | Decisión |
|---|---|---|---|---|---|---|---|---|
| **DIF-01** | Los 5 cruces siguen en el grafo | La composición se movió de módulo, no se invirtió en dirección | El dueño publica el contrato; la evidencia la produce el dueño | Puerto nuevo en meta_toolkit y cambio en motor, fachada, catálogo y colector | Ruptura de consumidores de `vault_norms.audit`; ventana de compatibilidad | `refactor(puerto) → test(equivalencia) → refactor(motor) → reconciliación` | estados (15), colector (30), paridad (23), reconciliación | **Propietario**: A/B/C (recomendación B) — `QA-RC-03-CRUZES.md` |
| **DIF-02** | QG-02 audita el vault de evidencia, no un runtime de certificación | El catálogo no fija el objetivo de la auditoría | QG-02 deja de bloquear por contenido ajeno y mide el producto | Contrato de QG-02 a cambiar (ficha y colector) | Que la puerta se vuelva laxa | Fijar el runtime de certificación; corregir AP-39 | auditoría sobre runtime limpio (escenario B) | **Propietario**: contrato de QG-02 |
| **DIF-03** | El producto deja 1 violación (AP-39) al crear un runtime | El init escribe una entrada de vocabulario sin memoria | INV-10 se cumple: el producto cumple su norma | Corrección en el init o en el registro de tags | Regresión en el registro de tags | Corregir y añadir prueba | prueba de init limpio | **Ejecutor** (P2, dentro del alcance) |
| **DIF-04** | La matriz CI no está acreditada | Cola de la cuenta | QG-07 acreditable | Acción administrativa del propietario | — | Desbloquear la cuenta y re-ejecutar | matriz 3×4 | **Propietario** (cuenta) |
| **DIF-05** | PRD CLI/MCP y contrato de runtime sin contrastar con el comportamiento | Nunca se reconciliaron con medición | Documentación fiable | Ronda de contraste | Divergencias de texto | Contrastar PRD ↔ recorrido E2E | contraste como prueba | **Ejecutor** (P2) |
| **DIF-06** | 14 hallazgos reales en el vault de evidencia | Los ADR de las rondas no cumplen AP-07/AP-64/CN-03 | Evidencia de calidad | Corregir 4 ADR + 1 nota | — | Corregir contenido y re-auditar | auditoría del sandbox | **Ejecutor** (P2) |
| **DIF-07** | El auditor histórico mide parches, no blobs | Coste de la lectura completa | Conclusión de privacidad defendible | Recorrido de blobs por lotes | Coste de ejecución | Búsqueda acotada por rutas/tamaño o muestreo declared | pruebas del auditor | **Ejecutor** (P2, declarado como límite) |
| **DIF-08** | La constitución no está ratificada | Es una propuesta | Fija la frontera de producto y los invariantes | — | Que se lea como norma sin ser norma | Ratifación del propietario | — | **Propietario** |

## 4. Cómo se lee esta capa

- AS-IS se verifica contra el código (generadores: `generar_inventario.py`,
  `generar_fichas.py`).
- TO-BE es una **propuesta**; sus diferencias no se tocan automáticamente.
- Cada diferencia con decisión de propietario aparece en
  `audits/architecture/mediciones.json → decisiones_pendientes`.
