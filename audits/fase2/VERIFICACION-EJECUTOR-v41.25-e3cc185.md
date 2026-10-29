# Verificación del ejecutor — v41.25 (tag sobre e3cc185) — 2026-10-29

**Esto NO es el dictamen del QA arquitectónico independiente.** Lo escribe el
ejecutor que preparó el release; por `PROTOCOLO-QA.md` el dictamen QA vive solo en
`audits/handoff/RESPUESTA-QA.md` y no se toca desde aquí. `qa_verdict_ref` sigue en
`PENDIENTE`. Este documento mide el artefacto publicado y declara qué no cubre.

**SHA revisado:** `e3cc18568dea15ed26294f9624d2b64e1349d5fc` (tag anotado `v41.25`).
**Candidato de QG:** `e101004` (R26, recibos en `audits/fase2/recibos-R26-e101004/`).

## Método (checkout limpio del tag, worktree temporal)

| Medida | Resultado |
|---|---|
| Tag `v41.25` → commit | e3cc185; release publicada, no borrador |
| CI run 40896422816 sobre e3cc185 | success, 27/27 jobs |
| `vault_gate --strict` en checkout limpio, sin preparar | 25/27: fallan `noop` y `doc_staleness` |
| Mismos dos gates tras materializar los 7 artefactos derivados | ambos en verde |
| `noop` y `doc_staleness` en el repo de trabajo | verdes |

## Hallazgo H-1 — las puertas no corren en verde en un clon sin inicializar

Los 7 artefactos derivados de `vault-sandbox/00_System/` están en `.gitignore` y
no viajan con el repo. En un clon recién hecho `doc_staleness` los da por ausentes
y `noop` pierde la base de `vault_standard_upgrade`. La CI lo evita porque ejecuta
`python scripts/vault_init.py` antes de las puertas (`vault-ci.yml`). Aquí no
corrí `vault_init`: copié los derivados desde el repo de trabajo, lo que prueba la
causa pero no el camino documentado.

- **Gravedad:** media para un tercero. No es un fallo del código ni de la
  publicación; sí es un requisito previo que quien clona y lanza `--strict` no ve.
- **Estado:** `ABIERTO — requiere documentar el paso previo o hacer que las
  puertas lo generen`. No se corrigió en este commit.

## No ejecutado en esta verificación

- Suite pytest completa (6508 tests) sobre el tag: la cubre la CI, no la repetí.
- Colector QG sobre e3cc185 (`colector_qg.py --ejecutar`): no corrido; los recibos
  vigentes son los de R26 sobre e101004.
- E2E desde wheel limpia, verificación de procedencia visual de `.archify/` y
  macOS: sin medir.
- Los límites declarados en el acta del 2026-10-29 (plan, batch,
  `--verify-integrity`, MCP SSE/HTTP, salida 130, AP-40/42/43) siguen sin ejercer.

## Veredicto del ejecutor

- **Publicación coherente:** tag, release y CI de e3cc185 concuerdan: ACEPTADO.
- **Puertas estrictas:** 27/27 solo con el entorno inicializado; 25/27 en un clon
  sin preparar (H-1).
- **Decisión de release:** corresponde al propietario (acta 2026-10-29) y el QA
  independiente puede dictaminar después sobre el mismo SHA.

NO FALSE PASS · NO ES DICTAMEN QA INDEPENDIENTE.

Estado: VERIFICACIÓN DEL EJECUTOR CON UN HALLAZGO ABIERTO (H-1).

## Seguimiento de H-1 (2026-10-29)

`vault_gate.preparar_entorno()` ejecuta `tests/sandbox_fixture.py --bootstrap` (el
mismo paso que la CI) cuando `doc_staleness` no ve los derivados, y publica el
resultado en `preparacion` del envelope. Comprobado en un worktree limpio:
bootstrap ejecutado, y `noop` y `doc_staleness` en verde. Cuatro tests lo cubren
y `AGENTS.md` lo menciona. Esto vive en un commit posterior; el tag `v41.25` no
cambia y sigue sin esta mejora. Estado de H-1: `CORREGIDO EN main (post-tag)`,
puertas 27/27 tras el arreglo. Suite completa (`-n 4`): 6495 pasados y 1 fallo propio (un literal `"tests"` en `vault_gate.py`, migrado a `rutas.TESTS`); tras ese cambio solo se re-corrieron los tests dirigidos y las puertas, no la suite entera.
