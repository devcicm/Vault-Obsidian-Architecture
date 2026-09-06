# Visión de producto

Vault Obsidian Architecture es un estándar abierto con un toolkit para dar a agentes LLM memoria documental persistente, auditable y gobernada sobre Markdown plano.

Este documento explica el producto. No añade normas ni reemplaza contratos:
la declaración del servicio, sus capacidades y restricciones pertenecen a
[vault_servicio](../../scripts/vault_servicio.py), y su representación pública
está en el [manifiesto](../../vault-obsidian-architecture.md).

## Problema y premisa

Un proyecto acumula decisiones, errores resueltos, restricciones y conocimiento
operativo. Una conversación aislada no asegura que todo eso llegue a la
siguiente sesión del agente. La persona acaba repitiendo contexto y pierde
visibilidad sobre qué información sustentó el trabajo.

La premisa es que ese conocimiento puede conservarse como documentos con
identidad, metadatos, relaciones y reglas de actualización. El agente puede
recuperarlos después, y una persona puede revisar su contenido y procedencia.
El toolkit ayuda a gobernar esa memoria; el agente o su integración debe usarlo.

## Promesa

| Perspectiva | Promesa |
|---|---|
| Técnica | Persistir conocimiento en Markdown con metadatos, relaciones y trazabilidad, aplicando reglas de escritura y recuperándolo bajo un presupuesto de contexto. |
| De producto | Permitir que los agentes retomen proyectos con conocimiento documentado que las personas puedan revisar, mantener y recuperar. |
| Simple | Que tu agente pueda retomar lo aprendido y tú puedas comprobarlo. |

Son formulaciones del resultado buscado. Su alcance depende de la evidencia
capturada, los contratos de las operaciones y la integración del agente.

## Estándar, toolkit y runtime

| Nivel | Alcance | Usuario principal |
|---|---|---|
| **Estándar** | Define estructura, reglas, contratos y gobernanza de la memoria documental. Se expresa en el manifiesto y en los registros canónicos que lo sustentan. | Arquitectos, integradores y maintainers que adoptan o evolucionan el modelo. |
| **Toolkit** | Implementa captura, consulta, custodia, recuperación y verificaciones del estándar. Incluye `scripts/`, el paquete de dominio `vault/`, la CLI y el adaptador MCP. | Agentes mediante su harness, desarrolladores e integradores. |
| **Runtime** | Es el vault concreto de un proyecto: su memoria operativa, notas, relaciones, preferencias, índices y artefactos. | El agente que trabaja en ese proyecto y la persona responsable de los datos. |

Aquí, runtime significa la instancia operativa de memoria; no exige un servidor
permanente. `vault/` es código del toolkit, mientras que `vault-sandbox/` es el
vault de pruebas de este repositorio. Los vaults consumidores pertenecen a sus
respectivos proyectos.

## Cómo fluye el conocimiento

```text
evidencia
    ↓
captura
    ↓
conocimiento gobernado
    ↓
persistencia
    ↓
recuperación
    ↓
selección contextual
    ↓
siguiente sesión del agente
```

La evidencia procede del proyecto: una decisión explicada, un incidente o un
procedimiento comprobado. La captura la convierte en documentos. Las operaciones
del toolkit aplican las reglas que cubren y conservan información para su
seguimiento. «Gobernado» describe ese tratamiento; no certifica la verdad del dato.

Los archivos persisten fuera de la conversación. Cuando otra sesión necesita
recordar algo, la búsqueda y el grafo permiten recuperar candidatos; el paquete
de contexto selecciona contenido con un presupuesto de tokens estimado. La
implementación está en [vault_context_pack](../../scripts/vault_context_pack.py)
y las operaciones disponibles en la [referencia de herramientas](../../scripts/README.md).

Por ejemplo, registrar una decisión con su motivo y su fuente permite consultarla
cuando vuelva a plantearse el mismo cambio. Ese recorrido necesita que la sesión
inicial capture la decisión y que la siguiente consulte el vault.

## Qué garantiza el sistema y bajo qué condiciones

| Base verificable | Alcance y condición | Fuente |
|---|---|---|
| Legibilidad documental | Las notas se conservan como Markdown con frontmatter YAML y wikilinks; pueden leerse sin ejecutar el toolkit. | [Manifiesto](../../vault-obsidian-architecture.md) |
| Escritura contenida y atómica en el camino común | Las operaciones que usan ese camino comprueban el destino y reemplazan el archivo mediante un temporal. No equivale a una transacción de todo el vault. | [vault_io](../../scripts/vault_io.py), [vault_fs](../../scripts/vault_fs.py) |
| Gobernanza verificable dentro de su cobertura | Los guards y audits detectan o previenen los casos que implementan; el catálogo declara su enforcement y sus límites. | [Catálogo de normas](../../scripts/vault_norms_catalog.py) |
| Trazabilidad y recuperación mediante herramientas | Hay historial, trazas, backups y restauración según cada operación. Recuperar un estado requiere que exista el artefacto correspondiente. | [Referencia de herramientas](../../scripts/README.md), [durabilidad](../../vault/durabilidad/) |
| Selección de contexto inspeccionable | El paquete informa qué notas incluye o excluye y su estimación de tokens. Su selección depende de la consulta, el contenido disponible y el presupuesto. | [vault_context_pack](../../scripts/vault_context_pack.py) |

## Qué no garantiza

- Veracidad, completitud o relevancia de todo lo escrito por el mero hecho de
  obtener una puntuación de salud alta.
- Recuerdo automático, consulta en cada sesión u obediencia del agente a una nota.
- Cobertura de todos los errores posibles por las gates, ni certificación de
  cumplimiento por mencionar marcos de calidad o seguridad.
- Protección automática de ediciones hechas fuera del camino de escritura del
  toolkit, ni recuperación sin historial o backups disponibles.
- Identificación exacta del modelo a partir del nombre de su cliente, ni un
  conteo de tokens idéntico al tokenizador de cualquier modelo.
- Instalación completa demostrada en todos los entornos. La
  [guía de producción](../GUIA-DE-PRODUCCION.md) publica el soporte y sus huecos;
  el [Quick Start](../../README.md#quick-start) conserva una limitación de copia
  pendiente de revisión.

## Papel de Obsidian y del agente

Obsidian permite a una persona explorar las notas y sus enlaces. Es una interfaz
compatible, no un requisito para que el agente acceda a los documentos.

El harness es el entorno que ejecuta al agente, conecta sus herramientas y
prepara su contexto. Debe integrar la captura y consulta en el trabajo entre
sesiones, respetando las instrucciones de la persona y los contratos de las
operaciones. Los accesos disponibles están documentados en la
[CLI](../../cli/README.md) y en el
[servidor MCP](../../mcp/nodejs/vault-mcp-server.mjs).

## Propiedad y legibilidad humana

El vault queda bajo control de la persona o del proyecto que lo mantiene. La
persistencia documental no requiere una base de datos, embeddings ni un servicio
externo. Las notas siguen siendo legibles aunque se deje de usar el toolkit.

La persona decide qué documentar, compartir y respaldar. Si configura un agente
remoto, el contenido que le entregue depende de esa integración: almacenamiento
local no implica que el contexto enviado al modelo permanezca en la máquina.

## Siguiente lectura

- [Seis capas conceptuales](../architecture/layers.md): responsabilidades y fuentes.
- [Onboarding](../MODO-AGENTICO-ONBOARDING.md): poblar memoria desde un proyecto.
- [Sanación](../MODO-AGENTICO-SANACION.md): trabajar sobre un vault preexistente.
- [README](../../README.md#qué-leer-después): instalación y referencias existentes.
