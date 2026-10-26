# Estado y trazabilidad — lectura para el propietario

**Generado por:** `audits/architecture/generar_informe.py`
**SHA:** `f049b1bd43fcdd5b0a010d73016139fbcf2286b9`

## 1. Resumen

El proyecto ya no es una colección de correcciones: hay una capa de
trazabilidad que enlaza recursos, contratos, derivaciones, evidencia y
decisiones. Este documento resume esa capa y lo que sigue abierto.

## 2. Propósito y promesa

Ver `docs/architecture/CONSTITUCION-ARQUITECTONICA.md` (DRAFT,
pendiente de ratificación).

## 3-5. Recursos inventariados

- **Total de recursos:** 699
- **Verificados:** 686 · **No verificados:** 13

| Naturaleza | Recursos |
|---|---|
| codigo | 293 |
| interfaz | 128 |
| norma | 82 |
| contrato | 68 |
| evidencia | 37 |
| documento | 29 |
| dependencia | 23 |
| deuda | 12 |
| arquitectura | 10 |
| gobierno | 8 |
| indice | 5 |
| artefacto | 2 |
| decision | 1 |
| entorno | 1 |

## 6. Dependencias y derivaciones

- **Relaciones en el grafo:** 703

| Relación | Aristas |
|---|---|
| PROVIDES | 314 |
| IMPLEMENTS | 170 |
| APPLIES_TO | 82 |
| OWNS | 68 |
| CONSUMES | 64 |
| VERIFIES | 3 |
| AFFECTS | 2 |

## 7. Contratos y responsabilidades

- **Contextos:** 10
- **Puertos:** 68
- **Tools publicadas:** 126
- **Normas en paquete:** 82
- **Quality Gates:** 8

## 8-9. Normas, Quality Gates y evidencia

- Trazabilidad por puerta: `audits/architecture/trazabilidad-qg.md`.
- Evidencia de esta ronda: `audits/architecture/mediciones.json`.

## 10-13. Hallazgos abiertos, deuda y divergencias

- **Hallazgos de QG-02 con ficha:** 15 (14 en el sandbox
  canónico + 1 en runtime limpio del producto).
- **Divergencias de inventario con ficha:** 10 (movimiento
  legítimo del sitio del cruce + fichas actualizadas).
- **Veredictos QA registrados:** 56

## 14. Riesgos

- La CI no se ejecuta: ningun gate de release se puede acredita en la matriz multipataforma.
- Los cruces fuera de puerto siguen declarados y el reconciliador los refleja (10 divergencias).
- El producto deja 1 violacion (AP-39) en un runtime recien creado: incumple la norma que certifica.
- El sandbox canonico acumula 14 hallazgos reales de contenido de evidencia.
- El auditor historico mide parches, no blobs integros.

## 15. Decisiones pendientes del propietario

- Ratificar (o corregir) la Constitucion arquitectonica propuesta (DRAFT).
- Divergencias DIV-01..DIV-10: alternativa A (eliminar el cruce componiendo desde el meta-toolkit), B (migrarlo a un owner con puerto declarado) o C (excepcion formal con plazo y riesgo).
- Contrato de QG-02: certificar sobre runtime limpio (recomendado) y no sobre el vault de evidencia.
- Purga del directorio vault-backups fuera del vault (AP-36): lo decide el dueno de los datos.
- Reescritura del historial publicado: solo el propietario.

## 16-19. AS-IS, TO-BE, diferencias y estado del candidato

- Vistas: `audits/architecture/arquitectura-asis-tobe.md`.
- Candidato: `31dfa462e87f5dcdb703e649e840e826a136ba50` · puertas 26/26 · suite 6270 passed / 13 skipped / 0 failed (sobre 001120c; re-ejecucion en curso) · E2E 27/27.

## 20. Recomendación técnica

1. Ratificar la constitución (§H) o devolverla con cambios: fija la
   frontera de producto y los invariantes que el resto de capas citan.
2. Decidir las divergencias (A/B/C) con la evidencia de las diez
   fichas; alternativa preferida: re-tomar el snapshot de Archify.
3. Corregir el defecto de AP-39 en el runtime limpio: hoy el producto
   no cumple la norma que certifica (INV-10).
4. Desbloquear la CI de la cuenta: es lo único que separa
   `READY_FOR_QA` de `RELEASED`.

