# PAT-7 — Desacuerdo legítimo declarado: contradicts entre notas

## Por qué existe

El texto normativo —descripción, señal, prevención— está en `norma.py` y no se
repite aquí.

Nace de la LLM Wiki de Karpathy (fase 3 del plan del 2026-11-16): su lint
busca contradicciones entre páginas, y AP-05 ya las medía para el dato tipado.
Lo que faltaba era distinguir la contradicción que nadie decidió de la que el
autor conoce y conserva a propósito. Sin esa distinción, la única salida de
AP-05 era PAT-1 —elegir una canónica—, que borra la información de que había
una elección abierta.

## Las caras

- **Lector único de la declaración** (AP-57): `vault/kernel/normativa/desacuerdos.py::pares_declarados`,
  compartido por los dos consumidores, que viven en contextos distintos.
- **AP-05 sin deuda declarada**: `vault/gobernanza/fuente_unica.py::_medir` separa
  `declared_disagreements` de `conflicts`.
- **Los dos lados en el paquete**: `scripts/vault_context_pack.py::_con_los_dos_lados`.
- **Ontología**: el predicado `contradicts` (inverso `contradicted_by`) en
  `scripts/vault_ontology.json`.
- **Tests**: `tests/test_karpathy_desacuerdos.py`.
