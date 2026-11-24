# Documentación

<!-- propiedad: CARLOS IVAN CM · revisión: manual -->

Índice de `docs/`. La fuente normativa es el
[manifiesto](../vault-obsidian-architecture.md); lo de aquí lo explica, lo
deriva o lo archiva.

La clase de cada documento —tutorial, guía, referencia o explicación, más
`registro` e `indice`— la declara `vault_registry.DOCS_DEL_REPO`, y no se
mezclan en un mismo documento. Si es tu primera vez, empieza por el
[Tutorial](TUTORIAL.md): un recorrido de quince minutos que un test ejecuta en
cada cambio.

## Instalar y operar

| Documento | Para qué |
|---|---|
| [Tutorial](TUTORIAL.md) | Primer uso de principio a fin: crear un vault, guardar, buscar, sustituir una decisión, contexto e historia |
| [Instalación limpia](INSTALACION-LIMPIA.md) | Quitar instalaciones previas, instalar la wheel, registrar el MCP y comprobar el handshake |
| [Variables de entorno](ENTORNO.md) | Cada variable que el estándar lee, con tipo, default y quién la lee (derivado del registro) |
| [Guía de construcción](GUIA-DE-PRODUCCION.md) | Las promesas hechas a quien instala, y quién las ejerce |
| [Disponibilidad de tools](DISPONIBILIDAD-DE-TOOLS.md) | Qué tools están activas en runtime instalado, MCP o checkout (derivado) |
| [Contrato del presupuesto de contexto](CONTRATO-CONTEXT-PACK.md) | Garantías de `vault_context_pack`, preferencias `must`, `history_excluded` y frescura del índice |
| [Evolución hacia un toolkit instalable](EVOLUCION-PRODUCTO-INSTALABLE.md) | De la copia de carpetas a la wheel |
| [Skills](SKILLS.md) | Capacidades del vault expuestas a un agente |

## Trabajar con un vault

| Documento | Para qué |
|---|---|
| [Onboarding](MODO-AGENTICO-ONBOARDING.md) | Poblar un vault desde un proyecto que no tenía |
| [Sanación](MODO-AGENTICO-SANACION.md) | Adaptar un vault preexistente sin borrar nada |

## Arquitectura

| Documento | Para qué |
|---|---|
| [Arquitectura](ARQUITECTURA.md) | Contextos acotados y fronteras — derivado: se regenera con `vault_arch --blueprint` |
| [Gobierno del estándar](GOBIERNO.md) | Qué es una norma, la escalera de enforcement, qué es ley del consumidor vs del mantenedor, el mapa capacidad→grupo→tool y el vocabulario — derivado: se regenera con `vault_servicio --doc` |
| [Mapa del manifiesto](MAPA-MANIFIESTO.md) | Cada titular de nivel 2 del manifiesto clasificado: qué es norma, qué es guía, qué es registro — cruzado por `test_mapa_manifiesto.py` |
| [Puertas de cierre](PUERTAS.md) | Qué mide cada puerta, cómo se arregla y por qué existe — derivado de `vault_gate.PUERTAS` y de los docstrings: se regenera con `vault_gate --fix-doc` |
| [Carriles de verificación](CARRILES.md) | Qué exige cada carril (`dev`, `merge`, `release`) y qué bloquea — derivado de `carriles.py` con `vault_gate --fix-doc` |
| [Plano de construcción](BLUEPRINT.md) | Derivado de los registros: se regenera con `vault_blueprint --blueprint`, no se edita |
| [Seis capas conceptuales](architecture/layers.md) | Piezas y responsabilidades |
| [ADR](adr/) | Decisiones de arquitectura registradas |
| [Normas](sdd/04-antipatterns.md) | Catálogo AP/PAT/SP/CN derivado de `vault_norms_catalog`; cada norma es un paquete en [`normas/`](../normas/) con su `porque.md` |
| [SDD](sdd/) | Principios, máquinas de estado, implementación, uso y antipatrones |

## Producto

| Documento | Para qué |
|---|---|
| [Visión de producto](product/overview.md) | Propósito, promesas y límites |
| [PRD de la CLI](product/prd-cli.md) y [del MCP](product/prd-mcp.md) | Requisitos de cada superficie |
| [Contrato de runtime](product/runtime-contract.md) | Qué garantiza la instalación |
| [Roadmap](product/roadmap/) | CLI y MCP |
| [Informe base](product/baseline-report.md) | Punto de partida de la productización |

## Auditorías

Informes fechados. No se reescriben: un hallazgo posterior va en un informe nuevo.

| Fecha | Documento |
|---|---|
| 2026-10-01 | [Comparativa de comportamiento v34.1 / v40.34](auditorias/2026-10-01-comparativa-v34-v40.md) |
| 2026-09-25 | [Análisis y hallazgos del repositorio](auditorias/2026-09-25-analisis-del-repositorio.md) |

## Archivo

Documentos que cumplieron su función y se conservan como registro (no-derogación).

| Documento | Origen |
|---|---|
| [Cuerpo del PR del checkpoint 3](archivo/2026-pr-checkpoint-3-gobernanza.md) | `PR_BODY.md` de la raíz |
