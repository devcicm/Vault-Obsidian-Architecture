---
name: vault-code-review
description: "Trigger: code review, PR review, diff review, revisar cambios, revisar rama, revisar etiquetas @vault en código. Runs deterministic 7-axis code review: resolves file and symbol-level @vault: refs (including short IDs like REQ-042), brings live business rules from the vault, checks PAT-10 and RDD coverage, scans added code lines for security and AP-51 hygiene, computes vault impact, and optionally generates a clickable HTML preview or saves an audit note."
allowed-tools: Bash(vault *) Bash(python *) Read Glob Grep
argument-hint: "[--path PATH] [--project SLUG] [--base REF --head REF | --staged | --files FILE ...] [--run-linters] [--html-preview] [--save] [--report] [--strict]"
version: "1.0"
---

# vault-code-review

Ejecuta una revisión de código / PR determinista en 7 ejes guiada por las notas vivas del vault:

1. **Trazabilidad `@vault:` (archivo y símbolo):** extrae y resuelve referencias de cabecera y de método/clase (con cualquier sangría), aceptando rutas de nota y códigos cortos (`REQ-042`, `QA-003`, `FLOW-007`, `ADR-0001`, `#anclas`) para entregar al revisor las reglas de negocio vigentes sin saturar el código.
2. **Cobertura RDD y lógica de negocio (`PAT-10`):** cruza los símbolos tocados con `OPERACIONES_LOGICA_NEGOCIO` y la matriz RDD (`14_Requirements/` ↔ métodos `@vault:` ↔ `15_Tests/`).
3. **Seguridad y secretos acotados al diff:** analiza únicamente líneas `+` de código real (omitiendo comentarios y docstrings).
4. **Higiene estática (`AP-51`):** detecta `except:` desnudo, `except Exception: pass/continue`, funciones tocadas >120 líneas y cambios de código sin pruebas.
5. **Impacto documental en el vault:** identifica notas directas (`11_Code/`, `14_Requirements/`, notas `@vault:`) y backlinks en `99_Index/graph.json`.
6. **Linters opcionales (`--run-linters`):** ejecuta linters instalados (`ruff`/`eslint`) solo sobre archivos tocados sin inventar resultados.
7. **Veredicto y visor web clicable (`--html-preview`):** emite `APPROVE`, `COMMENT` o `REQUEST_CHANGES` y genera opcionalmente un visor HTML5 autocontenido dentro del vault (`19_Audits/previews/`) donde cada `@vault:` abre al clic las reglas de la nota y enlaces `obsidian://` / `file://`.

## Hard rules

- **Read-only by default.** Sin `--save` ni `--html-preview` la tool no escribe nada en el vault ni en el repo.
- **Containment (AP-36).** Tanto `--save` (`19_Audits/code-review/`) como `--html-preview` (`19_Audits/previews/`) escriben únicamente dentro del vault.
- **No silent approval on broken refs (AP-72).** Cualquier `@vault:` roto o secreto/vulnerabilidad bloqueante en líneas añadidas produce veredicto `REQUEST_CHANGES`.
- **Never fabricate linter output.** Si un linter no está instalado se reporta `skipped: not_installed`, nunca aprobado.

## Prerequisites

- Un vault inicializado (`VAULT_ROOT` resuelto) y un repositorio local (`--path` o proyecto enlazado vía `vault_project --link`).
- Para resolver códigos cortos en vaults multiproject sin ambigüedad, pasar `--project <slug>`.

## When not to use it

- Para poblar desde cero la documentación de un repositorio completo: usar `vault-onboard`.
- Para auditar la salud estructural global del vault: usar `vault_audit` o `vault-sanacion`.
- Para inyectar etiquetas `@vault:` en archivos fuente: usar `vault_code_tag --link-vault ... --symbol ...` o `vault_code_sync --fix`.

## Steps

```bash
# 1. Revisar un PR o rama completa contra base con informe Markdown
vault run vault_code_review --path . --project mi-api --base main --head HEAD --report

# 2. Revisar cambios en staging antes de commitear (fallando si hay bloqueantes)
vault run vault_code_review --path . --project mi-api --staged --strict

# 3. Revisar archivos concretos y generar visor web HTML clicable con reglas del vault
vault run vault_code_review --path . --project mi-api --files src/fiscal.py --html-preview

# 4. Ejecutar linters y guardar el acta oficial en 19_Audits/code-review/
vault run vault_code_review --path . --project mi-api --base main --head HEAD --run-linters --save
```

## Decision gates

| Situation | Action |
|---|---|
| `verdict == "REQUEST_CHANGES"` por `AP-72` (`@vault:` roto) | Corregir el código/ruta en la etiqueta o crear la nota destino antes de integrar |
| `verdict == "REQUEST_CHANGES"` por `SEC_*` | Retirar secretos hardcodeados o corregir la vulnerabilidad en las líneas añadidas |
| `STALE_VAULT_REF` (`superseded`/`deprecated`) | Actualizar el `@vault:` hacia la nota declarada en `superseded_by` |
| `MISSING_BUSINESS_DOC_REF` (`PAT-10`) | Vincular el método con `vault_code_tag --link-vault REQ-NNN --file ... --symbol ...` |
| `NO_TESTS_TOUCHED` | Añadir o actualizar pruebas para los símbolos modificados antes del merge |

## Arguments

| Argument | Description |
|---|---|
| `--agent` | Agente que firma el acta cuando se usa `--save` |
| `--base` | Referencia git base del diff (ej. `main` o commit SHA) |
| `--files` | Lista explícita de archivos fuente a revisar sin exigir diff git |
| `--head` | Referencia git destino del diff (default: `HEAD`) |
| `--html-preview` | Genera visor web HTML autocontenido con `@vault:` clicables en `19_Audits/previews/` |
| `--no-rdd` | Omite el cálculo de matriz de trazabilidad RDD |
| `--path` | Ruta al repositorio o carpeta de código fuente a revisar |
| `--project` | Slug del proyecto (resuelve repo enlazado y desambigua IDs cortos como `REQ-042`) |
| `--report` | Emite informe legible en Markdown en lugar de JSON |
| `--reviewer` | Revisor humano de pareja en XP Nivel 3+ (`SP-06`, validado contra `AP-64`) |
| `--run-linters` | Ejecuta linters instalados (`ruff`/`eslint`) sobre archivos tocados |
| `--save` | Guarda el acta de revisión en `19_Audits/code-review/` |
| `--staged` | Revisa únicamente los cambios en staging (`git diff --cached`) |
| `--strict` | Retorna código de salida 1 si el veredicto es `REQUEST_CHANGES` |

## Output contract

Report: esta skill y versión (`v1.0`); el alcance revisado (`review_scope`); el veredicto
(`APPROVE` / `COMMENT` / `REQUEST_CHANGES`); conteo de bloqueantes, advertencias e
informativos; las reglas vivas `@vault:` resueltas; la cobertura RDD y notas impactadas
del vault; y las rutas creadas si se solicitó `--save` o `--html-preview`.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Revisión completada (o sin bloqueantes bajo `--strict`) |
| 1 | Error de ejecución/ruta inválida o veredicto `REQUEST_CHANGES` con `--strict` |
| 2 | Error de argumentos (argparse) |
