# AP-69 — El test que construye a mano lo que ya tiene apoyo

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí.

Nació del dolor que frenaba el desarrollo el 2026-10-30: cada cambio pedía
una suite de casi siete mil tests y veinte minutos de reloj. La mitad de ese
reloj era subproceso, y al buscar dónde acelerarlo no había un sitio: había
239. Cada módulo de test traía su `_run`, su `_tool` o su `_cli`, con su
entorno, su codificación y su timeout —o sin timeout—, y su `sys.path.insert`
encima. Acelerar el lanzamiento de una tool, o pasar las tools puras a
ejecutarse en proceso, exigía tocar cada copia.

## Lo que encontró la medida del 2026-10-31

Sobre los 555 módulos de `tests/`, por AST:

- 476 `sys.path.insert`/`append` en 399 módulos, cuando el conftest ya pone
  `scripts/` en el path.
- 239 funciones que lanzan `subprocess` con `sys.executable`, en 179 módulos.
  De las 45 que más se parecen entre sí, 36 no pasaban `errors=` y 26 no
  pasaban `timeout`: un hijo colgado bloqueaba al worker entero.
- 133 textos con salto de línea pegados con `+` en 75 módulos, casi todos
  frontmatter de notas de prueba.
- 13 `time.sleep` y 3 `+=` sobre una cadena.

Ninguno es un fallo por separado, y por eso ninguna puerta lo había visto: el
defecto es el agregado.

## Las caras

Derivadas al generarse, no escritas a mano: cada `ruta::símbolo` es una
función que nombra AP-69 en su cuerpo dentro de una tool que el catálogo
declara, o un `test_*` de `tests/` que la ejercita con el criterio de la capa
4. `vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): las funciones de `scripts/vault_tests_higiene.py`.
- **Detecta** (`tools_detecting`): las mismas.
- **Tests** (`tests/`): `tests/test_tests_higiene.py`.

## Lo que se dejó fuera y por qué

- **`tests/apoyo.py` y `tests/conftest.py`**: son el sitio donde ese código
  tiene que estar. El guard solo recorre `test_*.py`.
- **`normas/*/test_*.py`**: corren con `pytest normas/` sin el conftest de
  `tests/`, y su `sys.path` es necesario, no copia.
- **Un lanzador sin `sys.executable`** (el binario `vault`, `node`) y **un
  texto armado con `join` o con f-strings encadenados**: la puerta es estática
  y no los ve. El límite está declarado en el docstring del dueño, no supuesto.
- **La velocidad**: verde no dice que la suite sea rápida. Eso lo mide
  `perfil_suite`, por módulo, y lo exige el presupuesto del carril `dev`.
