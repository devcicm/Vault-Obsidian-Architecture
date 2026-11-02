# Plan deierre del refactor — qué se queda vivo y qué se archiva (S-4)

Decisión del 2026-11-02, al cerrar v41.26. La rama `reestructura/teseo` sube
con 63 commits y el trabajo del refactor **no termina aquí**: C-2 tanda 2
(inyección de `VaultContext`) y A-3/A-4 dependen del instrumento que este
refactor construyó. Jubilar el andamio antes de tiempo sería tirar la
herramienta con el trabajo a medias.

## Lo que se queda vivo, y por qué

| Qué | Por qué sigue |
|---|---|
| `paridad.py` | El instrumento de medición del contrato observable. C-2 tanda 2 y A-3 lo usan para contrastar sus cambios: la vista `escritos` es la que detecta una tool que escribe el mismo path con otro cuerpo. Sin él, la siguiente tanda no tiene con qué medirse. |
| `golden/` | El golden master que `paridad.py` compara. `estatico`, `superficie`, `ayuda`, `envelopes` y `escritos`. Recaptured tras el bump a v41.26. |
| `AUDITORIA.md` | El veredicto de cada hallazgo con su clase (PURE_REFACTOR / COMPATIBLE_EVOLUTION / NOT_APPLICABLE). Lo que queda pendiente (C-4, A-3, A-4) se lee ahí, y con su motivo. |
| `BUGS-DETECTADOS.md` | B-01..B-11 con su estado. B-11 saldada; las demás son hallazgos vivos con su causa y su remedies escrito. Un hallazgo sin su ficha se pierde. |
| `CHANGELOG-REFACTOR.md` | Una fila por tablón, con su hash. Es la memoria de qué se midió y qué se movió. |

## Lo que se archiva, y por qué

`audits/archivo/reestructura-2026-11-02/` con un `README.md` que dice qué
contiene cada cosa y por qué se jubila:

| Qué | Por qué era andamio |
|---|---|
| `PLAN-REFACTOR.md` | El plan de los bloques A, B y C. Cumplido en lo que se hizo; lo que queda (C-2 tanda 2, C-4, A-3, A-4) está anotado en `AUDITORIA.md` y en `CHANGELOG-REFACTOR.md`, que son los que se leen. Un plan que ya no se ejecuta en esta rama es historia. |
| `INVENTARIO-2026-10-30.md` | La foto del repo antes de empezar. Su valor es el delta, y el delta está medido en el changelog. |
| `MEDICION-FACHADAS.md` | La medición que decidió que C-03 queda CANDIDATE. El veredicto está en la fila de C-03 de `AUDITORIA.md`; la medición larga queda como historia. |

**Nada se borra** (no-derogación): lo archivado sigue versionado, en su sitio,
con la anotación de a qué queda sustituido.

## Lo que NO se jubila, y por qué no

- **`paridad.py` y `golden/`**: no son andamio, son el instrumento. Se
  jubilarían cuando el trabajo que los usa termine —C-2 tanda 2, A-3, A-4— y
  entonces la decisión se toma con el trabajo hecho delante, no ahora.
- **`AUDITORIA.md` y `BUGS-DETECTADOS.md`**: tienen hallazgos vivos. Un
  registro con lo que sigue pendiente se lee; uno con todo cerrado se archiva.
- **El `paridad.py` no se toca sin su instrumento**: si se mueve de sitio, la
  fila de `vault_arch.py` que lo cita y las rutas del changelog cambian.
