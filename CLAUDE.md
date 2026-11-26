# CLAUDE.md — Índice de contexto, capas y skills de Vault-Obsidian-Architecture

> **Identidad:** este repositorio es el **estándar** (especificación + toolkit), **no un vault**. Promesa de producto: memoria documental gobernada para agentes LLM sobre **Markdown plano + JSON/JSONL + Git**, sin base de datos, sin embeddings y sin dependencias externas fuera de stdlib + PyYAML + Node nativo.
>
> **Reglas operativas completas:** leer primero [AGENTS.md](AGENTS.md). Este archivo actúa como índice de contexto compacto (referencia cruzada estilo *progressive disclosure*, ≤ 120 líneas, `PAT-9`).

## 1. Mapa de contexto (memoria ↔ referencia)

| Si necesitas saber… | Abre directamente |
|---|---|
| Reglas no negociables, fuentes únicas y comandos de cierre | [AGENTS.md](AGENTS.md) |
| **Inventario y control por capas (Capas 1–6) + dónde editar** | [docs/architecture/MAPA-CAPAS.md](docs/architecture/MAPA-CAPAS.md) |
| Diagramas interactivos Archify (capas, contextos, cruces, onboarding) | [.archify/mapa-capas.html](.archify/mapa-capas.html) · [.archify/mapa-contextos.html](.archify/mapa-contextos.html) · [.archify/mapa-cruces.html](.archify/mapa-cruces.html) · [.archify/mapa-onboarding.html](.archify/mapa-onboarding.html) |
| Contextos acotados, puertos y cruces medidos (derivado de `vault_arch`) | [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) |
| Plano de 7 capas, normas y deuda viva (derivado de `vault_blueprint`) | [docs/BLUEPRINT.md](docs/BLUEPRINT.md) |
| Servicio, 3 capacidades, 5 naturalezas y exclusiones wheel (derivado) | [docs/GOBIERNO.md](docs/GOBIERNO.md) |
| Variables de entorno y límites declarados (derivado de `vault_entorno`) | [docs/ENTORNO.md](docs/ENTORNO.md) |
| Carriles `dev` / `merge` / `release` y lista de puertas | [docs/CARRILES.md](docs/CARRILES.md) · [docs/PUERTAS.md](docs/PUERTAS.md) |
| Especificación normativa completa (manifiesto) y ADRs del repo | [vault-obsidian-architecture.md](vault-obsidian-architecture.md) · [docs/adr/](docs/adr/) |
| Referencia CLI de herramientas y paquetes de normas | [scripts/README.md](scripts/README.md) · [normas/](normas/) |

## 2. Resumen rápido de las 6 capas (dónde vive cada pieza)

1. **Capa 1 — Núcleo (`vault/kernel/`):** IO atómico, locks, `safety.py` (anti-poison + CIA), `banderas.py` (`.flags.jsonl` `SP-05`), `normativa/xp.py` (`xp_level 1..4` `SP-06`) y catálogos hoja. **0 dependencias de dominio.**
2. **Capa 2 — Dominio Base (`autoria`, `grafo`, `indices`, `durabilidad`):** write path único (`vault_write`), señales de ejecutor (`vault_ronda --flag`), requisitos XP (`vault_requirement_save`), revisión de código (`vault_code_review`), BM25 y cuarentena.
3. **Capa 3 — Gobernanza y Consulta (`gobernanza`, `consulta`):** auditoría normativa, `vault_context_pack` (`--max-sensitivity`, `PAT-7`), `vault_ingest` (anti-SSRF) y `vault_preferences --adapters`.
4. **Capa 4 — Ciclo de Vida y Composición (`ciclo_de_vida`, `vault/runtime.py`):** `curacion.py` (`vault_propagate --curate-plan/--curate-apply/--mark-contradicts` vía puerto `BitacoraCambios`), `vault_onboard`, `vault_sanacion`.
5. **Capa 5 — Transporte y RBAC (`cli/`, `mcp/nodejs/vault-mcp-server.mjs`):** servidor MCP (perfiles `lector` < `ejecutor` < `operador`, `VAULT_MCP_ROL`, `SP-04`/`SP-05`) y CLI consolidada.
6. **Capa 6 — Meta-Gobernanza (`meta_toolkit`, fuera de la wheel):** `vault_gate`, `vault_arch`, `vault_blueprint`, `vault_servicio`, `vault_fix_all`. Nunca escribe notas de usuario.

## 3. Índice de skills y modos agénticos (carga bajo demanda)

| Skill / Modo | Cuándo abrirlo | Ruta |
|---|---|---|
| **Curación batch (`SP-05`)** | Consolidar banderas `FLAG-NNN` y contradicciones `PAT-7` | [agent/skills/vault-curate/SKILL.md](agent/skills/vault-curate/SKILL.md) |
| **Sesión y rondas** | Protocolo de inicio/cierre de ronda con trazabilidad | [agent/skills/vault-sesion/SKILL.md](agent/skills/vault-sesion/SKILL.md) |
| **Recordar / contexto** | Ensamblar contexto acotado antes de editar | [agent/skills/vault-recordar/SKILL.md](agent/skills/vault-recordar/SKILL.md) |
| **Ingesta de fuentes** | Ingerir fuentes externas con pre-vuelo anti-poison | [agent/skills/vault-ingest/SKILL.md](agent/skills/vault-ingest/SKILL.md) |
| **Decisiones (ADR)** | Registrar/supersedir ADRs con responsable humano (`AP-64`) | [agent/skills/vault-decision/SKILL.md](agent/skills/vault-decision/SKILL.md) |
| **Code Review** | Revisar diff contra reglas del vault, ADRs y `SP-06` | [agent/skills/vault-code-review/SKILL.md](agent/skills/vault-code-review/SKILL.md) |
| **Sanación de vault ajeno** | Sanar un vault preexistente sin borrar nada (12 fases) | [agent/skills/vault-sanacion/SKILL.md](agent/skills/vault-sanacion/SKILL.md) · [docs/MODO-AGENTICO-SANACION.md](docs/MODO-AGENTICO-SANACION.md) |
| **Onboarding desde cero** | Poblar un vault desde un proyecto sin vault (7 fases) | [agent/skills/vault-onboard/SKILL.md](agent/skills/vault-onboard/SKILL.md) · [docs/MODO-AGENTICO-ONBOARDING.md](docs/MODO-AGENTICO-ONBOARDING.md) |
| **Orquestación y ciclo de vida** | Ejecución durable, DAG, ACID, Saga y patrón `Dispose`/RAII (5 pilares) | [agent/skills/vault-orquestacion/SKILL.md](agent/skills/vault-orquestacion/SKILL.md) · [docs/MODO-AGENTICO-ORQUESTACION.md](docs/MODO-AGENTICO-ORQUESTACION.md) |
| **Operación y custodia** | Backup, mover notas, SDD, diagnóstico MCP y auditoría | [vault-backup](agent/skills/vault-backup/SKILL.md) · [vault-move](agent/skills/vault-move/SKILL.md) · [vault-sdd-init](agent/skills/vault-sdd-init/SKILL.md) · [vault-mcp-diagnose](agent/skills/vault-mcp-diagnose/SKILL.md) · [vault-toolkit-audit](agent/skills/vault-toolkit-audit/SKILL.md) |

## 4. Invariantes rápidos antes de entregar cualquier cambio

- **Destino:** todo runtime va contra `vault-sandbox/`, nunca sobre la raíz del repo ni sobre vaults reales sin orden explícita.
- **Derivados:** nunca edites a mano lo derivado; corre `python scripts/vault_fix_all.py`.
- **Carril `dev`:** `python scripts/vault_test_scope.py --changed --correr` y `python scripts/vault_gate.py --strict --nivel rapida`.
- **Carril `merge` (en serie, nunca a la vez sobre `vault-sandbox/`):** `python scripts/vault_gate.py --strict` y `python -m pytest tests/ -q -n 4 --tb=short -p no:cacheprovider`.
- **No-derogación:** nunca borres tools, normas ni secciones del manifiesto; anota `superseded_by:`.
