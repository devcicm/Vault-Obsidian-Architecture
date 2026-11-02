# Andamio del refactor `reestructura/teseo` — archivado el 2026-11-02

Lo que aquí hay es **andamio de trabajo**: documentos que sirvieron para
ejecutar la fase de refactor y que, al cerrar v41.26, ya no dirigen nada.
**No se borró nada** (no-derogación): sigue versionado, en su sitio, con la
anotación de a qué queda sustituido.

## Qué contiene y a qué queda sustituido

| Fichero | Qué era | Sustituido por |
|---|---|---|
| `PLAN-REFACTOR.md` | El plan de los bloques A, B y C, con su replan cuando la medición lo cambió | `audits/reestructura/AUDITORIA.md` (lo que queda pendiente, con su motivo) y `audits/reestructura/CHANGELOG-REFACTOR.md` (qué se hizo, con su hash) |
| `INVENTARIO-2026-10-30.md` | La foto del repo antes de empezar | El delta, medido: está en el changelog del refactor, fila por fila |
| `MEDICION-FACHADAS.md` | La medición de las tres capas de fachada que decidió que C-03 queda CANDIDATE | La fila de C-03 en `AUDITORIA.md`, que lleva el veredicto y dice dónde está la medición |

## Lo que sigue vivo y por qué

`paridad.py`, `golden/`, `AUDITORIA.md`, `BUGS-DETECTADOS.md` y
`CHANGELOG-REFACTOR.md` **no** se archivan y no se movieron de sitio: están
en `audits/reestructura/`. El instrumento sigue porque el trabajo no ha
terminado —C-2 tanda 2 y A-3/A-4 lo necesitan para contrastar sus cambios— y
la auditoría y la lista de bugs siguen porque tienen hallazgos vivos.

El razonamiento completo, con lo que se queda y lo que se va, está en
`audits/reestructura/JUBILACION-S4.md`.
