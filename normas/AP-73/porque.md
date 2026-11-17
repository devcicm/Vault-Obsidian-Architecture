# AP-73 — Fuente archivada modificada

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí.

Nace de la LLM Wiki de Karpathy (Parte A del plan de estrés del 2026-11-17): la
capa cruda es inmutable, el modelo la lee y nunca la edita. `vault_ingest
--archivar-fuente` ya guardaba la fuente literal, pero nada impedía reescribirla
después y nada lo detectaba: la cita `source:` de las notas derivadas seguía
apuntando a un texto que ya no era el que llegó.

## Las caras

- **Criterio** (dueño único): `vault/kernel/contenido.py::es_fuente_archivada`
  y la huella `vault/kernel/contenido.py::huella_de_cuerpo`.
- **Guard**: `scripts/vault_io.py::_fuente_archivada_reescrita`, dentro del
  dueño de la escritura, así que lo hereda todo escritor.
- **Registro de la huella**: `scripts/vault_ingest.py::_nota_de_fuente`.
- **Audit**: `scripts/vault_audit.py::_detect_fuentes_alteradas`.
- **Tests**: `tests/test_parte_a_normas.py` y `test_ap73_norma.py`.

## Lo que no dice

No declara `10_Migrated` inmutable: eso sigue siendo decisión del dueño del vault
(`00_System/inmutable.json`). La norma solo protege la nota que la propia
ingesta marcó como fuente archivada. Contraste con un vault ajeno (regla 7): no
hay todavía un vault de fuera con fuentes archivadas por esta tool; el límite se
declara en vez de suponerlo cubierto.
