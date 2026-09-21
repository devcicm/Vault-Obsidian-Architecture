# Seis capas conceptuales

Esta es una **vista conceptual y explicativa del producto**, no una arquitectura
normativa. Las capas no sustituyen los contextos acotados, capacidades,
naturalezas, taxonomías, arquitectura canónica, blueprint ni registros normativos
existentes. Tampoco definen dependencias nuevas ni autorizan operaciones.

La numeración sirve para leer el mapa; no fija un orden de ejecución. Una
herramienta puede contribuir a varias capas. Las herramientas y artefactos
citados son ejemplos para orientarse, no un catálogo alternativo ni exhaustivo.
El modelo estándar / toolkit / runtime se explica en la
[visión de producto](../product/overview.md).

## Relación con las fuentes canónicas

| Pregunta | Fuente que la gobierna |
|---|---|
| ¿Qué servicio presta y para qué sirve cada grupo? | `SERVICIO` y `CAPACIDADES` en [vault_servicio](../../scripts/vault_servicio.py). |
| ¿Cuál es la naturaleza declarada de una herramienta? | `NATURALEZAS` en [vault_servicio](../../scripts/vault_servicio.py). |
| ¿Qué contextos, puertos y fronteras existen? | Registros de [vault_arch](../../scripts/vault_arch.py), publicados en la [arquitectura derivada](../ARQUITECTURA.md). |
| ¿Qué normas, vocabularios y fundamentos se aplican? | [Catálogo de normas](../../scripts/vault_norms_catalog.py), [catálogo de fundamentos](../../scripts/vault_fundamentals_catalog.py) y [manifiesto](../../vault-obsidian-architecture.md). |
| ¿Qué parámetros y efectos declara cada herramienta? | [Catálogo de herramientas](../../scripts/vault_mcp_catalog.py), contrato del vault resuelto por [vault_io](../../scripts/vault_io.py) y [referencia de uso](../../scripts/README.md). |
| ¿Cómo se comprueba la evolución del estándar? | [Registro de gates](../../scripts/vault_gate.py) y [blueprint derivado](../BLUEPRINT.md). |

En caso de discrepancia, se corrige esta explicación contra las fuentes
canónicas. Una capa conceptual no cambia la clasificación de ninguna herramienta.

## Mapa conceptual

Las rutas de código corresponden al toolkit. Las secciones documentales y los
artefactos del vault corresponden al runtime; en este repositorio las ejecuciones
se realizan sobre `vault-sandbox/`.

| Capa | Propósito | Responsabilidad | Artefactos principales | Herramientas relacionadas | Valor para el agente | Valor para el humano | Riesgo si falla | Relación con las fuentes canónicas |
|---|---|---|---|---|---|---|---|---|
| **1. Propósito y contrato** | Dar sentido y reglas a la memoria documental. | Explicar el servicio y los contratos que lo sustentan. | `vault-obsidian-architecture.md`; `scripts/vault_servicio.py`; catálogos de normas y fundamentos. | `vault_servicio`, `vault_norms`, `vault_fundamentals`. | Lenguaje y contratos previsibles. | Comprender qué adopta y qué puede comprobar. | Expectativas incompatibles y promesas sin cobertura. | Servicio y clasificaciones en `vault_servicio`; reglas en los catálogos y el manifiesto. |
| **2. Estructura y captura** | Convertir evidencia del proyecto en documentos organizados. | Distinguir creación de estructura, captura de contenido y adaptación de material existente. | `vault/autoria/`; `vault/ciclo_de_vida/`; guías de onboarding y sanación; notas de proyecto, decisiones y conocimiento en el runtime. | `vault_init`, `vault_onboard`, `vault_write`, `vault_append`, `vault_ingest`, `vault_project_overview`. | Conservar hechos y aprendizajes entre sesiones. | Revisar y navegar el conocimiento capturado. | Duplicación, estructuras vacías o contenido inventado. | Secciones en [vault_registry](../../scripts/vault_registry.py); contratos de captura en el catálogo; fronteras en `vault_arch`. |
| **3. Recuperación y contexto** | Seleccionar conocimiento para la tarea siguiente. | Relacionar búsqueda, grafo, preferencias y presupuesto de contexto. | `vault/consulta/`; `vault/grafo/`; `vault/indices/`; `17_Preferences/` y `99_Index/` del runtime. | `vault_search`, `vault_query_parse`, `vault_subgraph`, `vault_context_pack`, `vault_preferences`, `vault_model_profile`. | Acceder a contexto seleccionado e inspeccionable. | Mantener continuidad y preferencias explícitas. | Omisiones, información desactualizada o presupuesto inadecuado. | Finalidad en `CAPACIDADES`; parámetros y efectos en el catálogo; selección en `vault_context_pack`. |
| **4. Custodia y confianza** | Conservar integridad, procedencia y posibilidades de recuperación. | Conectar validación, escritura contenida, historial, auditoría y backups. | `vault/kernel/`; `vault/durabilidad/`; `vault/gobernanza/`; `scripts/vault_io.py`; historial, backups y auditorías del runtime. | `vault_audit`, `vault_validate`, `vault_quality_check`, `vault_backup`, `vault_restore`, `vault_quarantine`. | Detectar problemas y recuperar estados disponibles. | Inspeccionar cambios y conservar control sobre los datos. | Corrupción, pérdida o confianza excesiva en una puntuación. | Cobertura en el catálogo de normas; mecanismos en `vault_io` y `vault_fs`; recuperación según contrato. |
| **5. Acceso y operación** | Hacer accesibles las operaciones desde terminales y agentes. | Explicar interfaces, selección del destino, planificación y comprobaciones de ejecución. | `cli/`; `cli/safety.py`; `cli/scheduler.py`; `mcp/nodejs/vault-mcp-server.mjs`; catálogo y contrato de herramientas. | CLI consolidada, servidor MCP y scripts invocables. | Descubrir y ejecutar operaciones con argumentos explícitos. | Elegir interfaz y entender qué datos puede afectar. | Destino incorrecto, diferencias entre interfaces o exposición accidental. | Superficies y parámetros en el catálogo; instrucciones en las referencias CLI/MCP; soporte en la guía de producción. |
| **6. Evolución del estándar** | Mantener coherencia y compatibilidad del producto técnico. | Relacionar registros, documentación derivada, pruebas y deuda declarada. | `vault/meta_toolkit/`; `tests/`; `.github/workflows/`; baselines; `docs/BLUEPRINT.md`; `docs/ARQUITECTURA.md`. | `vault_gate`, `vault_arch`, `vault_blueprint`, `vault_doc_counts`, `vault_produccion`, `vault_fix_all`. | Disponer de contratos previsibles al actualizar el toolkit. | Revisar contribuciones y evolución de la deuda. | Documentación autoconsistente que no demuestra la experiencia del consumidor. | Gates en `PUERTAS`; deuda y trazabilidad en el registro del blueprint; arquitectura en `vault_arch`. |

## Cómo usar esta vista

Las capas ayudan a situar una necesidad. Capturar una decisión comienza en
estructura y captura; recuperarla conecta recuperación y contexto con custodia
y confianza. El acceso elegido determina cómo se invocan esas operaciones.
La evolución del estándar comprueba el repositorio que publica las reglas.

Esta agrupación no decide si una operación escribe. Por ejemplo,
`vault_preferences` puede consultar preferencias o modificarlas, y
`vault_model_profile` puede activar un perfil. Los argumentos y efectos del
contrato concreto siguen siendo necesarios para elegir una operación.

Las garantías y sus límites se explican en la
[visión de producto](../product/overview.md#qué-garantiza-el-sistema-y-bajo-qué-condiciones).
Para límites de dependencias y puertos, consultar la
[arquitectura canónica derivada](../ARQUITECTURA.md); para el estado del soporte,
la [guía de producción](../GUIA-DE-PRODUCCION.md).
