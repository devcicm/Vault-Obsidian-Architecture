# Deuda: consistencia entre lo declarado, lo implementado y lo verificado

**Generado por:** `audits/architecture/generar_informe.py`

Cada registro de `inventario-deuda.yaml` se contrasta con la
implementación publicada y con su evidencia. Donde el estado declarado y
el estado real no coinciden, se dice aquí; no se reescribe el histórico.

| TD | Título | Estado declarado | Implementación verificable | Nota |
|---|---|---|---|---|
| TD-0001 | El job de CI que valida la wheel no instala el p | parcial | no consta |  |
| TD-0002 | Las trazas runtime del servidor MCP caen dentro  | falso_positivo | no consta |  |
| TD-0003 | Un control que no puede cargar su dependencia in | vigente | sí | implementada y con evidencia; el estado declarado se actualiza en el anexo |
| TD-0004 | Reconciliacion del snapshot de Archify con el co | corregida | no consta |  |
| TD-0005 | Documentacion de producto sin clasificar y con h | no_verificada | no consta |  |
| TD-0006 | Las baselines de estructura estan por encima de  | vigente | no consta | sigue vigente |
| TD-0007 | El cliente MCP del harness de auditoria leia la  | corregida | no consta |  |
| TD-0008 | vault_init --clean destruye el runtime sin copia | vigente | sí | implementada y con evidencia; el estado declarado se actualiza en el anexo |
| TD-0009 | El Quick Start del README mezcla la superficie d | vigente | no consta | sigue vigente |
| TD-0010 | La politica de QG acreditaba un estado sin SHA o | corregida | sí | implementada y con evidencia; el estado declarado se actualiza en el anexo |
| TD-0011 | YAML de datos reportado como frontera de lenguaj | corregida | sí | implementada y con evidencia; el estado declarado se actualiza en el anexo |
| TD-0012 | El auditor historico sobreafirmaba su alcance y  | corregida | sí | implementada y con evidencia; el estado declarado se actualiza en el anexo |

## Regla aplicada

Un registro pasa a `corregida` solo con: commit correctivo, evidencia de
comportamiento, prueba de regresión, verificador, SHA y resultado. La
columna «Implementación verificable» de esta tabla NO sustituye al
registro canónico: la fuente sigue siendo `inventario-deuda.yaml`; este
informe es la capa que señala las desalineaciones.

