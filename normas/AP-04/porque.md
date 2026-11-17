# AP-04 — Features aspiracionales documentadas como implementadas

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada se movió tal cual desde `NORM_CATALOG` el 2026-10-09
(deuda #10, lote AP-01..AP-20).

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra AP-04 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` de `tests/` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica / detecta**: el catálogo no declara ninguna tool.
- **Hueco declarado**: `cobertura_descubierta` en `norma.py`.
- **Tests** (`tests/`): ninguno la ejercita en el cuerpo de un `test_*`.

## Por qué no es un guard

Sigue en `audit` a propósito (Parte A del plan de estrés, L3, 2026-11-17), y hoy
ni siquiera tiene detector (`cobertura_descubierta`). Lo que separa AP-04 de una
nota correcta es si la funcionalidad descrita está desplegada, y eso no está en la
nota ni en el vault en el momento de escribirla: es un hecho del sistema que se
documenta, y cambia después. Un guard que decidiera por el tiempo verbal del
cuerpo rechazaría la referencia que describe en presente lo que sí existe y
dejaría pasar la promesa escrita en futuro: un guard débil que da verde sin medir.
