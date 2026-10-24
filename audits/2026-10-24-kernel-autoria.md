# Auditoría arquitectónica — Kernel → Autoría (2026-10-24)

**Estado:** análisis estático inicial; no es certificación de conformidad ni resultado de pruebas.

## Evidencia verificable

- `scripts/vault_arch.py` declara `_cruce("kernel", "autoria", "permanente", "kernel", ...)` en `PRESUPUESTO_DE_CRUCES`. La justificación indica que el inyector de envelopes consume el puerto `hablar`.
- `scripts/vault_errors.py` importa `from vault.autoria.voz import speak as _speak_estable` a nivel de módulo (línea 51 de la revisión examinada).
- `vault/autoria/voz.py` implementa el servicio de voz; contiene imports diferidos de `vault_norms_catalog`, `vault_vocabulario` y `vault_raiz`.
- `docs/ARQUITECTURA.md` establece «Kernel ← todos» y «Kernel no cruza a dominio ajeno», pero muestra `kernel -.-> autoria` como cruce.

## Evaluación

**Hallazgo A-01 — excepción explícita, dependencia concreta (revisar).**
El cruce no es accidental: está registrado y justificado. Sin embargo, el consumidor `vault_errors` importa una implementación concreta de `vault.autoria.voz`, no un contrato abstracto independiente. La declaración «consume el puerto» requiere demostrar que el módulo importado es realmente un puerto estable y no un servicio de dominio. No se debe eliminar la voz sin preservar el comportamiento fail-safe y la compatibilidad de los envelopes.

**Hallazgo A-02 — ambigüedad documental (confirmada).**
La regla general de Kernel y el cruce permanente declarado se presentan sin explicar su relación normativa. La excepción existe en el registro, pero un lector del documento derivado puede interpretar el grafo como incumplimiento no permitido. Cualquier corrección documental debe realizarse desde `scripts/vault_arch.py --blueprint`, no editando `docs/ARQUITECTURA.md` a mano.

## Criterios de aceptación antes de modificar el acoplamiento

1. Identificar las llamadas efectivas a `_speak_estable`, sus parámetros y el comportamiento ante fallos.
2. Determinar si el puerto debe residir en Kernel, en un módulo de contratos o en una interfaz inyectada en la raíz de composición; documentar el coste de migración.
3. Agregar pruebas de regresión para envelopes, modo silencioso y ausencia del servicio de voz.
4. Ejecutar `python scripts/vault_arch.py --check --strict` y los gates de gobernanza en un checkout completo.
5. Regenerar documentos derivados solo después de modificar su fuente canónica; no ampliar baselines para silenciar fallos.

## Alcance y límites

No se ha inspeccionado aún el contenido de `.archify/` ni se ha ejecutado la suite completa en un checkout local. Los números de contextos y cruces son los declarados por el repositorio, no mediciones independientes. Este informe no autoriza una fusión a `main`.
