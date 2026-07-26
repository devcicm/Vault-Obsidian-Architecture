# CLAUDE.md — instrucciones para agentes en este repo

Este repositorio **no es un vault**: es el **estándar** que define cómo se construyen los
vaults. Es spec + toolkit. Confundir ambas cosas es el error más caro que se puede cometer aquí.

---

## Qué contiene

| Ruta | Qué es |
|---|---|
| `vault-obsidian-architecture.md` | **El manifiesto.** Representación pública del estándar (~6.000 líneas). Fuente normativa. |
| `scripts/*.py` | ~103 scripts, 81 tools activas en 34 grupos. Sin dependencias fuera de stdlib + PyYAML. |
| `scripts/README.md` | Referencia de tools por grupo, con ejemplos de CLI. |
| `tests/` | Suite pytest (437 tests). Toda norma con guard debe tener test. |
| `cli/` | CLI consolidada + `safety.py` (guards anti-poison, `scan_content`). |
| `mcp/nodejs/` | Servidor MCP monolítico + `tools-catalog.json` (sincronizado desde Python). |
| `vault-sandbox/` | **Único** vault de pruebas del repo. Todo runtime va aquí. |
| `docs/` | SDD y skills. |

---

## Los dos ejes

El estándar cubre dos recorridos, y una tool nueva pertenece a uno de los dos:

- **escritura → gobernanza** (grupos 1–33): capturar, normalizar, versionar, auditar.
- **consulta → contexto** (Grupo 34, v39): `vault_query_parse` → `vault_subgraph` →
  `vault_context_pack`, con `vault_preferences` (contexto estable en `17_Preferences/`)
  y `vault_ingest` (única con superficie de escritura, con preflight anti-poison no
  desactivable vía `cli/safety.py`). **Sin base de datos, sin embeddings y sin servicio
  externo** — esa restricción es normativa, no una limitación pendiente de resolver.

---

## Reglas no negociables

1. **`vault-sandbox/` para cualquier ejecución.** Ninguna tool se ejecuta contra la raíz del
   repo ni contra vaults reales del usuario. **Solo 4 tools aceptan `--root`**
   (`vault_norms`, `vault_graph_fix`, `vault_graph_inspect`, `vault_section_index`); el resto
   resuelve el vault por autodetección (`vault_io._detect_vault_root()`), que en este repo ya
   devuelve `vault-sandbox/` con origen `spec_repo_sandbox`. Para forzar un destino usa la
   variable de entorno `VAULT_ROOT`; para que una detección insegura falle en vez de caer a la
   raíz del repo, exporta `VAULT_STRICT_ROOT=1`. Verifica con `vault_io.vault_root_origin()`.

2. **No-derogación.** No se elimina ninguna tool, grupo, norma ni sección del manifiesto. Lo
   reemplazado se anota `superseded_by:` conservando su contrato. Si algo parece obsoleto,
   anótalo — no lo borres. Esto está declarado como política en el manifiesto
   (`### Política de no-derogación`).

3. **Registro canónico primero, doc después.** Un concepto que solo existe en el manifiesto no
   existe. El orden es: registro en código → doc derivada → guard que falla si divergen → test.
   Documentar sin código ejecutable es el fallo histórico que el estándar ya cometió una vez.

4. **Ciclo obligatorio ante un síntoma:** `síntoma → norma (AP/PAT/SP/CN) → guard + audit +
   heal → test`. Una corrección puntual sin norma que la sostenga se vuelve a romper.

5. **Enforcement real.** Ninguna norma nueva puede tener enforcement `manual`. Debe ser
   `guard`, `audit`, `guard+audit` o `recommended`, y el catálogo lo verifica.

6. **Escrituras atómicas y contenidas (AP-36).** Todo side-effect (backups, traces, locks,
   stubs) vive DENTRO del vault. Rutas siempre derivadas de `vault_io.get_vault_root()`,
   nunca de `__file__` ni del CWD.

7. **No propagar tools a otros repos** salvo petición explícita. Los vaults consumidores se
   sincronizan por decisión del usuario, no como efecto colateral de un cambio aquí.

---

## Fuentes únicas de verdad

Si necesitas un dato de estos, léelo del registro — no lo redefinas ni lo copies:

| Dato | Fuente |
|---|---|
| Normas AP/PAT/SP/CN y su enforcement | `scripts/vault_norms.py` |
| Vocabulario de `status` (12 valores) | `vault_norms.STATUS_VOCAB` |
| Fundamentos F1–F8 y dimensiones DQ | `vault_fundamentals.FUNDAMENTALS` |
| Tríada CIA, FAIR, V's del Big Data, cobertura ISO, matriz de trazabilidad | `vault_fundamentals.FRAMEWORK_REGISTRIES` |
| Catálogo de tools expuesto por MCP | `scripts/vault_mcp_catalog.py` → `mcp/nodejs/tools-catalog.json` |
| Raíz del vault en runtime | `vault_io.get_vault_root()` / `set_vault_root()` |
| Cómo se detectó esa raíz (confianza) | `vault_io.vault_root_origin()` / `vault_root_is_confident()` |
| Contrato de tools (`tool-spec.json`) | `vault_io.tool_spec_path()` → `<vault>/00_System/`; `resolve_tool_spec()` con fallback legacy |

---

## Comandos habituales

```bash
# Suite completa — debe quedar en verde antes de cerrar cualquier cambio
python -m pytest tests/ --tb=short

# Normas y marco de datos
python scripts/vault_norms.py --audit --root vault-sandbox   # audita el vault contra las normas
python scripts/vault_norms.py --check-framework              # guard anti-drift registro ↔ manifiesto
python scripts/vault_fundamentals.py --framework             # exporta el marco (JSON + MD)
python scripts/vault_fundamentals.py --matrix                # matriz concepto → métrica → tool

# Catálogo MCP
python scripts/vault_mcp_catalog.py --check                  # falla si Python y JSON divergen
python scripts/vault_mcp_catalog.py --sync                   # regenera el JSON

# Salud del vault de pruebas
python scripts/vault_audit.py --root vault-sandbox
python scripts/vault_quality_check.py --root vault-sandbox --min-score 0.7
```

---

## Antes de cerrar un cambio

- [ ] `python -m pytest tests/ --tb=short` en verde.
- [ ] `python scripts/vault_norms.py --check-framework` → `ok: true`.
- [ ] `python scripts/vault_mcp_catalog.py --check` → sincronizado.
- [ ] `git diff --stat vault-obsidian-architecture.md` sin borrados netos de contenido.
- [ ] Si tocaste una versión: banner del manifiesto, tabla de versiones, entrada de changelog
      con hash real, badge del `README.md` y `version` de `pyproject.toml` coherentes.
- [ ] Si añadiste una norma o un id de registro: guard + test que fallen cuando falte.
