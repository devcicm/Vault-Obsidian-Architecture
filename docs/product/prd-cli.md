# PRD — CLI (Command Line Interface)

**Producto:** Vault-Obsidian-Architecture CLI
**Versión target:** v1.0
**Fecha:** 2026-09-20

---

## 1. Problem Statement

La automatización CI/scripts necesita acceso predictible al vault. La CLI
existente funciona pero no es instalable como programa de primer nivel: se
invoca como `python -m cli` o `python scripts/vault_cli.py`. No hay entry point
público.

**Promesa descubierta (vault_produccion):** `ergon_de_entrada` — no se invoca
como programa.

---

## 2. Vision

CLI robusta para pipelines y sistemas desatendidos. Cada operación es
 predecible, documentada y auditada.

**Slogan:** "Ejecuta cualquier tool del toolkit desde shell — sin pensar."

---

## 3. Promise (Product)

> "Ejecuta cualquier tool del toolkit desde shell con pre-vuelo de seguridad,
> planificación de olas y verificación de integridad."

---

## 4. Scope IN

- Comandos: `run`, `batch`, `plan`, `scan`, `doctor`, `groups`, `find`, `show`
- Pre-vuelo de seguridad: AP-36 containment, anti-poison, required args
- Scheduler de olas (concurrencia)
- `--verify-integrity` (hash antes/después)
- Timeout configurable (`VAULT_TIMEOUT`)
- `--stop-on-error` para batch
- Salida JSON estructurada (`{ok, tool, ...}`)
- Códigos de salida: 0 éxito, 1 fallo, 2 pre-vuelo bloqueado, 130 interrumpido

---

## 5. Scope OUT

- Interacción MCP (esa es otra superficie)
- Validación semántica de Mermaid o referencias
- Multi-vault discovery
- Scheduling de operaciones que sí comparten recursos

---

## 6. Constraints

- Sin dependencias externas a stdlib + PyYAML
- Mismo catálogo de tools que MCP
- Misma gobernanza vía `GobernanzaBase`
- CLI es solo Python (no wrappers shell)

---

## 7. Governance (POO)

Hereda de `GobernanzaBase`; override en `cli_gobernanza.py`.

**Pre-flight específico:**
- `AP-36 containment`: rutas absolutas, traversal a parent, escape del vault
- `anti-poison`: directivas de inyección, caracteres invisibles
- Validación de `required_args` del tool-spec

**Post-flight específico:**
- `--verify-integrity`: hash del artefacto antes/después si es escritura
- Registro de findings en trace

---

## 8. Risks

| ID | Riesgo | Mitigación |
|----|---------|-----------|
| R1 | Desincronización con tools del catálogo | `vault_mcp_catalog --check` en CI |
| R2 | Cambios en formato de args rompen scripts CI | Versionado semver de CLI; changelog |
| R3 | `verify-integrity` lento en vaults grandes | Snapshot incremental opcional |

---

## 9. Roadmap

Ver [roadmap-cli.md](./roadmap/roadmap-cli.md)

---

## 10. Definition of Done

- [ ] Entry point declarado en `pyproject.toml [project.scripts]`
- [ ] `vault run --help` muestra todos los comandos disponibles
- [ ] `vault doctor` reporta estado del entorno
- [ ] Pre-flight bloquea contenido peligroso
- [ ] Batch ejecuta con olas y `--stop-on-error` funciona
- [ ] `--verify-integrity` registra hash antes/después
- [ ] Tests de integración contra vault-sandbox
- [ ] Gates: `vault_gate --strict` verde
