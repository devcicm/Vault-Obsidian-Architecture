# Recibos del colector QG-00..QG-07: candidato 9ac330a (R27, v41.26)

Ejecución: `python audits/fase2/colector_qg.py --sha 9ac330a658c2583bd21d44348a6a38ba6fa54b0c --ejecutar ...`
el 2026-11-03, en una sesión de Claude Code (Windows 10, Python 3.14), con el árbol limpio en ese SHA
y el producto en su worktree (`git worktree add --detach`), igual que hace el job `qg-receipts` de
`release.yml`. Las rutas de la máquina se normalizan (`<repo>`, `<tmp>`, `<user>`, `<python>`,
`<recibos-base>`, `<vaultqa>`). El sha256 de cada fichero es el del ORIGINAL, antes de normalizar:
`sha256-original.json` los recoge.

**Resultado: QG-00..QG-07 PASS, `liberable: true`.**

| Puerta | Qué midió | Resultado |
|---|---|---|
| QG-00 | identidad git, árbol limpio, saneamiento, reconciliador Archify | PASS |
| QG-01 | `vault_arch --check --strict` y el reconciliador | PASS |
| QG-02 | `vault_gate --strict` (28/28), `vault_norms --audit` y la certificación compuesta | PASS |
| QG-03 | la suite con su JUnit y su recibo de procedencia, y el recorrido E2E (27/27) | PASS |
| QG-04 | saneamiento, `pip-audit`, contención y operaciones destructivas | PASS |
| QG-05 | paridad CLI↔MCP (5/5) y el contrato AP-40 | PASS |
| QG-06 | construcción de wheel y sdist, contenido de la wheel e instalación limpia | PASS |
| QG-07 | la CI del mismo SHA: run 41718868947, `completed/success`, 27/27 jobs | PASS |

Suite: 6789 tests, 6773 passed, 16 skipped, 0 failed, 0 errores (Windows 10, Python 3.14, `-n 4`,
árbol limpio en 9ac330a).

## Límites declarados

- **El `pip-audit` local audita un venv con lo que el producto declara** (PyYAML), no el entorno de
  desarrollo de quien lo ejecuta: auditar la máquina del desarrollo mediría paquetes ajenos al
  producto (chromadb, accelerate…), que es lo que pasó en la primera corrida de esta ronda. La CI
  audita el intérprete del job (`command -v python`), que es el entorno de la ronda.
- **La paridad CLI/MCP (QG-05) se midió sobre un runtime recién creado con `vault init`**, como en
  R26. Un runtime con corridas previas hace que el verificador acuse al MCP de escribir fuera del
  runtime autorizado (el `.tool-trace.json` y el `.voice-counter` que arrastra la foto): el veredicto
  dependía del residuo, no del producto.
- **La suite y el E2E se corrrieron en Windows con Python 3.14.** La CI del candidato ejercita Linux
  y Python 3.9–3.12 (run 41718868947). macOS no se promete.
- **La primera corrida del colector en esta ronda falló** y no se publica: QG-00 quedó en rojo por
  dos pares de contextos que el propio refactor había retirado del presupuesto de cruces
  (`gobernanza → meta_toolkit`, en A-5; `kernel → autoria`, en A-3/A-4) y que la foto `.archify/`
  —de una revisión anterior— todavía listaba. La salida fue ratificar esas dos divergencias
  (DEC-08 del acta del 2026-11-03), no tocar la foto. QG-02 y QG-04 salieron rojos por el mismo
  motivo de residuo (el sandbox sin sembrar y el `pip-audit` del entorno de desarrollo); ambos se
  midieron después con el sandbox sembrado y el venv del producto.
- Los recibos se escriben FUERA del árbol versionado (`--recibos <dir>`): el commit candidato no
  contiene su propia acreditación. Estos los versiona el commit de documentación, que es
  descendiente del candidato.

## Trazabilidad

Candidato, evidencia y estado de gobierno: `audits/fase2/CANDIDATO-RELEASE.yaml` (ronda R27).
El candidato anterior (v41.25, R26) se conserva en su bloque `candidato_v41_25_r26`, y el de R25 en
`candidato_v41_25_r25`: nada se borra.
