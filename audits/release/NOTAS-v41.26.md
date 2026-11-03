Vault Obsidian Architecture **v41.26**: estándar y toolkit para dar a agentes LLM
memoria documental persistente, auditable y gobernada sobre Markdown plano.

> **Estado: autorizado por el propietario** (DEC-07, acta del 2026-11-03,
> `audits/handoff/ACTA-DECISIONES-PROPIETARIO-2026-11-03.md`), condicionado a que el
> candidato que fija `audits/fase2/CANDIDATO-RELEASE.yaml` tenga QG-00..07 en PASS
> y su CI en `success` sobre el mismo SHA. Ambas condiciones se cumplen y están
> medidas en `audits/fase2/recibos-R27-9ac330a/`.

## Instalación

```bash
pip install vault_obsidian_architecture-41.26-py3-none-any.whl
vault --help
vault mcp-path        # ruta del servidor MCP empaquetado (Node 18+)
```

Comprueba los ficheros contra `SHA256SUMS.txt`. El inventario de dependencias y
licencias va en `sbom.spdx.json` (SPDX).

## Qué cambia

**La rama `reestructura/teseo` sube.** 63 commits que midieron el repo contra sí
mismo antes de tocarlo, y la auditoría es lo que decide:
`audits/reestructura/AUDITORIA.md` clasifica cada hallazgo como PURE_REFACTOR,
COMPATIBLE_EVOLUTION o NOT_APPLICABLE, y lo que no se puede decidir leyendo se
midió —las tres capas de fachada quedan CANDIDATE con su consumidor medido, no
retiradas—.

- **A-1 se descartó:** los dos `tools-catalog.json` son proyecciones de un único
  `TOOLS_CATALOG`.
- **A-2** fundió un cuerpo duplicado (`install/uninstall::_run`).
- **A-3 y A-4, cerrados con la raíz de composición que faltaba:** nace
  `vault/kernel/productores.py` (un productor se ofrece al importarse) y tres
  puertos (`Voz`, `RegeneradorIndices`, `BitacoraTags`). La ausencia de un
  productor deja su motivo en la traza: no hay `except Exception: pass`.
- **A-5** cruzó el catálogo por un puerto declarado (`CatalogoTools`).
- **B-1** movió seis catálogos a `vault/kernel/normativa/`, fuera de la wheel.
- **C-1** cuenta también el `get_vault_root()` que se dispara al importar.
- **C-2** pasa el comportamiento de los tests a ejecución en proceso —13 ejemplos
  AP-42, el barrido de flags de 30 tools y, en esta ronda, el mecanismo
  `vault.ejecutor`, que es del producto— conservando el contrato CLI en un
  subproceso por tool.
- **AP-69** entra al catálogo: higiene de los tests, con `tests/apoyo.py` como
  casa del apoyo compartido. Y la firma de sitio deja de depender del
  intérprete: `ast.unparse` difiere entre 3.9 y 3.14, y una baseline congelada en
  una versión salía roja en la CI sin que una línea se moviera.
- **El instrumento:** `paridad.py` gana la vista `escritos`, que mide el digest
  de lo que cada tool deja escrito; el golden comparaba envelopes y no el
  contenido, así que una tool que escribiera el mismo path con otro cuerpo salía
  verde.

Lo que queda abierto se declara con su nombre: C-01, C-04 y C-06 tienen su
medición y siguen CANDIDATE.

## Qué se midió y con qué alcance

- **Suite:** 6789 tests, 6773 passed, 16 skipped, 0 failed, en **Windows 10,
  Python 3.14, `-n 4`**, con el árbol limpio en el candidato.
- **Puertas:** `vault_gate --strict` en verde dentro de QG-02 (28/28).
- **E2E desde la wheel:** 27/27 pasos en venv limpio, en Windows.
- **Quality Gates:** QG-00..QG-07 PASS (`audits/fase2/recibos-R27-9ac330a/`).
- **CI:** run 41718868947 sobre el mismo SHA, `completed/success`, 27/27 jobs
  (Linux y Windows, Python 3.9–3.12).
- **Regla 7:** contraste contra un vault ajeno (`vault-ans`, en solo lectura),
  sin anomalías nuevas respecto al contraste del 2026-10-16
  (`docs/contrastes/ultimo-contraste.json`).

## Límites declarados

- Capacidades que el E2E no ejerce: `plan`, `batch`, `--verify-integrity`, MCP
  por SSE/HTTP y la salida 130.
- Los controles AP-40/42/43 devuelven `no_ejecutado` desde una wheel limpia
  (fail-closed, nunca un PASS falso).
- El servidor MCP por HTTP escucha solo en `127.0.0.1` y exige token. No es
  autenticación de red.
- macOS no se promete.
- No hay dictamen QA arquitectónico independiente sobre este SHA
  (`qa_verdict_ref: PENDIENTE`): el propietario autoriza sin esperarlo.
- El `pip-audit` local audita un venv con lo que el producto declara (PyYAML); la
  CI audita el intérprete de su job.

## Trazabilidad

Candidato, evidencia y estado de gobierno: `audits/fase2/CANDIDATO-RELEASE.yaml`
(ronda R27). El candidato anterior (v41.25, autorizado en su día) se conserva en
su bloque `candidato_v41_25_r26`, y el de R25 en `candidato_v41_25_r25`: nada se
borra.
