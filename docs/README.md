# Documentación

Índice de `docs/`. La fuente normativa es el
[manifiesto](../vault-obsidian-architecture.md); lo de aquí lo explica, lo
deriva o lo archiva.

## Instalar y operar

| Documento | Para qué |
|---|---|
| [Instalación limpia](INSTALACION-LIMPIA.md) | Quitar instalaciones previas, instalar la wheel, registrar el MCP y comprobar el handshake |
| [Guía de construcción](GUIA-DE-PRODUCCION.md) | Las promesas hechas a quien instala, y quién las ejerce |
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
| [Arquitectura](ARQUITECTURA.md) | Contextos acotados y fronteras |
| [Plano de construcción](BLUEPRINT.md) | Derivado de los registros: se regenera con `vault_blueprint --blueprint`, no se edita |
| [Seis capas conceptuales](architecture/layers.md) | Piezas y responsabilidades |
| [ADR](adr/) | Decisiones de arquitectura registradas |
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
