# AP-68 — El git que ejecuta el toolkit, sin dueño

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí.

Nació de una pregunta que no era retórica: «¿ejecuta alguna tool o algún
proceso git, o sus comandos, sin supervisión, o se pasan comandos no
autorizados, o sin idempotencia, o reescribiendo el git?». La respuesta fue
que no, y que «no» no valía como hallazgo porque **no había nada que lo
verificara**.

## Lo que encontró la auditoría del 2026-10-23

24 sitios levantaban git fuera de cualquier dueño. Doce leían (churn del
núcleo, baseline de ciclos, fecha de commit de una norma, historial del
proyecto en el onboarding, drift, sync de código); uno escribía —el bootstrap
de `vault_init`: `init -b main`, `add -A`, `commit`— sobre un vault recién
creado, sin `push` ni `user.name` configurado, y con el vault existente
rechazado antes de llegar ahí. Ni un `shell=True`, ni un `--force`, ni un
reflog `apply`, ni un `config` que escribiera. El servidor MCP nunca ejecuta
git: lanza `python script.py --flag=value` con el script del catálogo
sincronizado, y no existe ninguna tool «ejecuta comandos» en el catálogo.

Todo correcto. Todo **declarado por nadie**: sin guard, sin puerta, sin test.
La única defensa era que quien leyera el diff se acuerde de mirar el verbo —
que es exactamente el criterio reimplementado por persona, distributed por
cada línea, que es AP-57 aplicado al repo contra sí mismo.

## Las caras

Derivadas al generarse, no escritas a mano: cada `ruta::símbolo` es una
función que nombra AP-68 en su cuerpo dentro de una tool que el catálogo
declara, o un `test_*` de `tests/` que la ejercita con el criterio de la capa
4. `vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): las funciones de `scripts/vault_procesos_git.py`.
- **Detecta** (`tools_detecting`): las mismas.
- **Tests** (`tests/`): `tests/test_procesos_git.py`.

## Lo que se dejó fuera y por qué

- **`tests/`**: un test necesita git crudo para fabricar el repositorio con
  el que va a medir. Migrar los tests al dueño los convertiría en certificadores de sí mismos (AP-44), y los tests no viajan en la wheel, donde no hay repo al
  que tocar.
- **Un argv armado con `" ".join(...)` o con un f-string**: la puerta es
  estática y no lo ve. Lo que sí lo cubre, para siempre, es el runtime: una
  llamada así no puede ejecutarse sin pasar por `ejecutar_git`, que juzga el
  verbo antes de lanzar. El límite está declarado en la puerta y en el
  docstring del dueño, no supuesto en silencio.