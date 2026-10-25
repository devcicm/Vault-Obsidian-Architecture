# TD-0003 / Q04–Q07 — Diseño final de la corrección (SIN IMPLEMENTAR)

**Estado:** diseño completo para dictamen. **No se ha implementado nada** (la
autorización es de investigación y diseño).

## 1. Causa raíz (demostrada en L2)

El contrato de salida de la auditoría (`vault/gobernanza/auditoria_runtime.py`)
publica `ok: True` **hardcodeado**, `total_violations`, `by_norm` y
`violations` — y **no declara el estado de ejecución de los controles**. Los
tres controles del estándar (AP-40/42/43) viven en
`scripts/vault_norms_engine.py::_checks_estandar` y cada bloque captura su
fallo de dependencia con `except (ImportError, OSError, ValueError): pass`
(líneas 151, 179, 196): el control desaparece y el resultado es
indistinguible de "no se encontró nada".

## 2. Inventario completo de consumidores (lo que no se puede romper)

| Consumidor | Qué lee | Dependencia con el cambio |
|---|---|---|
| `scripts/vault_norms.py:588-594` (CLI `--audit --strict`) | `result.get("total_violations")` | La única condición de fallo hoy: debe seguir leyendo esa clave |
| `scripts/vault_norms.py` (impresión del envelope) | todo el envelope | El JSON crece: es aditivo |
| `scripts/vault_norms_coherence.py:652` (puerta de coherencia) | `antes.get("by_norm")` / `despues.get("by_norm")` | Sin cambio: la sección `checks` es nueva y aditiva |
| `scripts/vault_arch.py:347` (puerto `auditar_normas`) | la fachada | Sin cambio |
| `tests/test_vault_norms_audit.py`, `test_norms_coherence.py` | hallazgos y conteos | Los envelopes actuales siguen siendo válidos; los nuevos campos son aditivos |
| MCP `tools/list` (97 tools) | el catálogo, no este envelope | Sin cambio |

## 3. Solución arquitectónica (inversión + estados explícitos)

**Inversión de dependencias.** Hoy el motor importa los verificadores
(`vault_mcp_catalog`, `vault_smoke`, `vault_voice`). El diseño invierte la
flecha: quien TIENE el verificador ejecuta el control y entrega su resultado;
el motor solo lo COLECCIONA con su estado.

```text
ANTES (cruce entrante, a_eliminar):
  vault_norms_engine --import--> vault_mcp_catalog / vault_smoke / vault_voice
  (el motor tira de la dependencia: si falla, el control muere en silencio)

DESPUES (cruce eliminado):
  dueno del verificador ejecuta el control y entrega
  resultado = {control, estado, hallazgos}
        |
        v
  motor: colecciona y publica `checks[]` en el envelope
```

Los duenos son Meta-toolkit (AP-40) y el smoke/la voz, que hoy están en el
mismo recorrido de auditoría: la ejecución de los controles se queda donde está
el conocimiento (cada dueno registra una función `control()` que devuelve
estado + hallazgos), y el motor los COLECCIONA por registro (como hace la
fachada con las reexportaciones: el conocimiento vive en el dueno, el
consumidor lo pide).

**Compatibilidad contractual.** El envelope gana una sección nueva y aditiva:

```json
{
  "ok": true,
  "completo": false,
  "total_violations": 0,
  "checks": [
    {"control": "AP-40", "estado": "ejecutado", "detalle": null, "hallazgos": 0},
    {"control": "AP-42", "estado": "no_ejecutado", "detalle": "dependencia_no_disponible", "hallazgos": 0}
  ]
}
```

- `ok` y `total_violations` y `by_norm` y `violations`: **sin cambio** (los
  consumidores actuales no se enteran).
- `completo`: `false` si algún control obligatorio no pudo ejecutarse.
- El ejemplo NO es un contrato aprobado: es la propuesta para dictamen.

**Fail-closed de los consumidores de gobernanza.** La CLI `--audit --strict`
pasa a fallar (exit != 0) cuando `completo` es `false`, además de cuando hay
violaciones: la puerta no puede pasar sobre una auditoría incompleta. La
puerta de coherencia igual.

## 4. Flujo de ejecución y propietarios

| Control | Dueño del verificador | Quién lo ejecuta tras el diseño | Estado que publica |
|---|---|---|---|
| AP-40 | Meta-toolkit (`vault_mcp_catalog.check_params`) | el coleccionista del motor, con el resultado entregado | `ejecutado` / `degradado` (dependencia) / `no_ejecutado` |
| AP-42 | `vault_smoke` (baseline + catálogo + `invocation`) | ídem | ídem |
| AP-43 | Autoría (`vault_voice.coverage`) | ídem | ídem |

Propietario del contrato: Gobernanza (el envelope es suyo). Responsable de la
remediación: el agente ejecutor, con dictamen de QA. Autoridad de aceptación:
QA + propietario.

## 5. Migración de consumidores y compatibilidad

1. **Fase 1 (aditiva, sin riesgo):** añadir `checks[]` y `completo` al envelope,
   sin quitar nada. Los consumidores actuales no leen esos campos.
2. **Fase 2 (inversión):** mover la ejecución de los tres controles fuera del
   motor (cada dueno entrega su resultado al coleccionista). Los cruces
   `gobernanza → meta_toolkit` y `gobernanza → autoria` desaparecen de la
   baseline (solo encoge).
3. **Fase 3 (fail-closed):** la CLI `--strict` y la puerta de coherencia pasan a
   exigir `completo: true` para dar por buena una auditoría limpia.

**Rollback:** cada fase es revertible por `git revert` del commit (sin tocar
baselines): el envelope vuelve a su forma anterior y los consumidores no
cambian. No hay migración de datos.

## 6. Tests propuestos (positivos, negativos y de fallo)

| # | Caso | Verificación |
|---|---|---|
| 1 | Control sano con hallazgo | `checks[AP-40].estado == "ejecutado"` y el hallazgo en `violations` |
| 2 | Dependencia rota (inyección del ImportError) | `checks[AP-40].estado == "no_ejecutado"` + `completo: false` |
| 3 | Control degradado (el verificador corre pero falla a mitad) | `estado == "degradado"` con el detalle |
| 4 | CLI `--strict` con auditoría incompleta | exit != 0 (hoy sale 0: es el defecto) |
| 5 | CLI `--strict` con auditoría completa y sin hallazgos | exit 0 |
| 6 | Regresión de consumidores | los envelopes de hoy (sin la sección nueva) siguen parseando igual |
| 7 | Equivalencia | un control sano produce EXACTAMENTE el envelope de antes más `checks` |

## 7. Riesgos de regresión y plan de commits previstos

- R1: consumidores que parsean el envelope por posición → mitigado: los campos
  nuevos son aditivos y van al final.
- R2: la inversión puede mover un cruce de la baseline → mitigado: la baseline
  solo encoge y el reconciliador verifica que los cruces eliminados sean
  exactamente los declarados `a_eliminar`.
- R3: el estado `degradado` puede confundirse con un hallazgo → mitigado: se
  documenta y se prueba que `degradado` NO añade violaciones.

Commits previstos (uno por fase): `refactor(AP-40/42/43): inversion de los
controles del estandar` → `test(AP-40/42/43): estados de ejecucion` → 
`fix(AP-40/42/43): la CLI --strict exige auditoria completa`.

**No se ejecuta ninguno hasta recibir autorización adicional.**