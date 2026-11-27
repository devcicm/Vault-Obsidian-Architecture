Vault Obsidian Architecture **v41.27**: estándar y toolkit para dar a agentes LLM
memoria documental persistente, auditable y gobernada sobre Markdown plano.

> **Estado: preparado en `collaboration-agent` — pendiente de autorización del propietario y creación de tag `v41.27`.**
> No se crea ni publica el tag `v41.27` hasta que el PR de `collaboration-agent` → `main`
> cierre con `Vault CI` en verde y el propietario firme el acta de autorización y actualización
> de `audits/fase2/CANDIDATO-RELEASE.yaml` (`release_authorized: true`).

## Instalación

```bash
pip install vault_obsidian_architecture-41.27-py3-none-any.whl
vault --help
vault mcp-path        # ruta del servidor MCP empaquetado (Node 18+)
```

Comprueba los ficheros contra `SHA256SUMS.txt`. El inventario de dependencias y
licencias va en `sbom.spdx.json` (SPDX).

## Qué cambia

- **Selector de carpetas por vault (`disabled_standard`):** soporte de presets
  `completo`, `minimo` e `infraestructura` en `vault_init` (`--sections-preset`,
  `--only-sections`, `--extra-sections`) y gestión declarativa en `vault_section`
  (`--disable` / `--enable`), respetando el contrato de degradación benigna sobre
  `secciones.json` y el índice maestro.
- **Skill `vault-mejora-continua` v1.0:** protocolo reproducible de cierre de
  hallazgos, saneamiento y trazabilidad en `agent/skills/vault-mejora-continua/`.
- **Endurecimiento de seguridad y acceso cruzado (`H-03` / `T-1`, `H-20` / `T-4`, `H-21` / `T-9`):**
  - Paridad Python ↔ Node (`AP-48`) en `evaluateCrossVaultAccessPolicy`: modo
    **fail-closed (`403`)** cuando el vault destino carece de `00_System/access-policy.json`,
    comparación por ruta resuelta (cierra bypass por carpetas homónimas), aplicación de
    `max_sensitivity`, `allowed_sections`, `denied_sections` y `allowed_tags` en `tools/call`,
    y rechazo `409 Conflict` ante sesiones concurrentes duplicadas de la misma instancia
    (`VAULT_MCP_SINGLE_SESSION`, `X-MCP-Instance`).
  - Detección crítica en `secret_scan.py` para `password=`, `secret=`, `token=` y URIs
    con credenciales (`esquema://usuario:clave@host`).
  - Normalización anti-evasión NFKC + desofuscación de letras separadas + detección de
    directivas en comentarios HTML (`POISON-HTML-COMMENT`) en `vault/kernel/safety.py`,
    junto con bloques forenses cerrados ```` ```audit-evidence ```` / ```` ```literal-probe ````
    para citar sondas como dato inerte en notas de auditoría.
  - Repositorio GitHub endurecido: `private-vulnerability-reporting` habilitado,
    Dependabot security updates habilitado, `permissions: contents: read` en `vault-ci.yml`
    y GitHub Actions fijadas por SHA de 40 caracteres hexadecimales.
- **Integridad, durabilidad y contratos de error (`H-05` / `T-2`, `T-3`, `H-10` / `T-5`, `H-02` / `T-6`):**
  - `ServicioSnapshot.crear` captura ficheros ilegibles en `merkle_vivo`, desactiva la
    deduplicación `unchanged` cuando existen ilegibles y publica `unreadable` en el
    manifiesto y envelope.
  - `vault_change_log_query` desempata entradas en el mismo segundo por posición en
    el fichero JSONL append-only.
  - Nuevo código canónico `STANDARD_INCOMPATIBLE` en `ERROR_CATALOG` y `vault/product_cli.py`.
  - `IsolationUnavailable` propaga `public_reason` (mensajes fijos del toolkit sin rutas
    de máquina) en `vault_errors.py`.
- **Calidad y anti-drift (`H-12` / `T-7`, `H-14` / `T-8`):**
  - `vault_doc_counts` registra `design_patterns` desde `CATALOGO_PATRONES` (72 patrones)
    y vigila `docs/MODO-AGENTICO-ORQUESTACION.md` (`AP-47`).
  - El job `Lint Python` en `vault-ci.yml` ejecuta `ruff check` bloqueante
    (`F821,F841,E722,B904,RUF034,SIM223`) sobre `vault/`, `scripts/` y `cli/` con 0 hallazgos.

## Qué se mide antes de autorizar el tag

- **Suite y pruebas RED → GREEN** de las olas A, B y C en `collaboration-agent`.
- **Puertas del estándar:** `python scripts/vault_gate.py --strict` (29/29 en verde).
- **Puertas de producto:** `python tests/run_product_gates.py` (`clean_install` + `memory_e2e`).
- **CI en PR `collaboration-agent` → `main`:** `Vault CI` (Windows + Ubuntu × Python 3.10/3.11/3.12 + puertas + product-gates + lint).

## Límites declarados

- El servidor MCP HTTP está diseñado para `127.0.0.1` con autenticación por token y
  control de sesión por instancia; no sustituye un gateway TLS/OAuth de red pública.
- macOS no se promete en la matriz de soporte.
- `audits/fase2/CANDIDATO-RELEASE.yaml` conserva el candidato publicado `v41.26`
  (`9ac330a658c2583bd21d44348a6a38ba6fa54b0c`) hasta que el propietario apruebe el
  merge a `main` y emita el acta para `v41.27`.

## Trazabilidad

- Dictamen QA y evidencia completa RED → GREEN (`DN-01..DN-10`) registrados en el
  vault de desarrollo (`vault-dev-codex`, secciones `21_QA/`, `04_Sessions/` y `18_Bugs/`).
- Manifiesto de candidato vigente: `audits/fase2/CANDIDATO-RELEASE.yaml`.
