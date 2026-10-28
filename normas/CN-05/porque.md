# CN-05 — One body, one owner — un cuerpo, un dueño

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí. La entrada nació con la Fase 5 de consolidación del 2026-10-28,
cuando el repo se midió a sí mismo y encontró lo que ningún guard miraba: los
cuerpos copiados.

## Las caras

Derivadas al migrar, no escritas a mano: cada `ruta::símbolo` es una función
que nombra CN-05 en su cuerpo dentro de una tool que el catálogo declara, o un
`test_*` que la ejercita con el criterio de la capa 4.
`vault_norms --check-framework` falla si alguna deja de existir.

- **Aplica** (`tools_enforcing`): `scripts/vault_clones.py::check`, `scripts/vault_clones.py::freeze`. `tools_detecting` queda vacío a propósito: la tool detecta y hace cumplir a la vez, y repetirla en los dos campos duplicaría las caras derivadas sin decir nada nuevo.
- **Dueños** (los cuerpos que la norma dejó con un solo dueño): `vault/kernel/normalizacion.py::slugify`, `vault/kernel/frontmatter_parsing.py::parse_frontmatter`, `scripts/vault_lib.py::utcnow`.
- **Tests**: `normas/CN-05/test_cn05_norma.py::test_cn05_el_catalogo_sirve_la_entrada_del_paquete`, `normas/CN-05/test_cn05_norma.py::test_cn05_un_clon_entre_modulos_se_declara`, `normas/CN-05/test_cn05_norma.py::test_cn05_la_baseline_solo_encoge`.
