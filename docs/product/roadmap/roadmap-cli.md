# Roadmap — CLI

**Horizonte:** 6 meses (Q4 2026 — Q2 2027)
**Versión inicial:** v1.0

---

## Problemas a resolver (P0-P2)

| ID | Problema | Prioridad | Hito |
|----|---------|-----------|------|
| P0 | `ergon_de_entrada` (promesa descubierta): no se invoca como programa | P0 | v1.1 |
| P1 | `--stop-on-error` documentado | P1 | v1.1 |
| P1 | Diferencia de guards entre CLI y MCP causa confusión | P2 | v1.2 |
| P2 | Timeout global no configurable | P2 | v1.2 |
| P2 | Sin tests E2E de batch scheduling | P2 | v1.3 |

---

## Milestones

### v1.1 (Q4 2026)

- [ ] `pyproject.toml [project.scripts]` declara entry point `vault`
- [ ] `vault --version` muestra versión del toolkit
- [ ] `vault run --help` lista todas las tools
- [ ] `vault doctor` reporta estado del entorno (vault root, contrato, locks)
- [ ] Pre-flight AP-36 + anti-poison funcionando
- [ ] `vault_produccion` promesa `ergon_de_entrada` cubierta

### v1.2 (Q1 2027)

- [ ] `VAULT_TIMEOUT` configurable globalmente
- [ ] `vault batch --stop-on-error` documentado y funcional
- [ ] Diferencia de guards CLI vs MCP documentada en gobernanza
- [ ] `GobernanzaCLI` integrada en `cli/runner.py`

### v1.3 (Q2 2027)

- [ ] `vault plan` devuelve plan de olas sin ejecutar
- [ ] `vault scan` detecta antipatrones y condiciones de carrera
- [ ] Tests de integración CLI × MCP contra mismo vault-sandbox
- [ ] `--verify-integrity` con hash SHA256 configurable

---

## Métricas de éxito

| Métrica | Target |
|---------|--------|
| Tiempo pre-flight por operación | < 50ms |
| Operaciones concurrentes en ola | hasta 4 (configurable) |
| Cobertura de guards CLI | 100% de los casos AP-36/AP-anti-poison |
| Suite de integración CLI | 50+ tests |
