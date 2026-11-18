# Acta de decisiones del propietario — 2026-11-18

**Propietario:** devcicm (titular del repositorio `devcicm/Vault-Obsidian-Architecture`).
**Canal:** sesión de Claude Code abierta por la cuenta del propietario, rama
`05_tmp/workspace_miniserver`. Cada decisión es una declaración explícita del
propietario en el chat, cuyo texto figura abajo tal cual. Claude la asienta en este
commit.
**Nivel de garantía:** administrativo, no criptográfico. Es el mismo que las actas de
2026-10-28, 2026-10-29 y 2026-11-03: identidad git y permisos de push compartidos,
sin firma GPG sobre este fichero.
**Alcance:** esta acta **no** autoriza ninguna publicación, tag, push ni merge. Esas
decisiones siguen pendientes y se asentarán, si el propietario las toma, en un acta
propia que nombre el SHA candidato.

## DEC-09 — presupuesto de cruces `autoria ↔ durabilidad` y ediciones bloqueadas

**Pregunta planteada** (2026-11-17), sobre tres ediciones que el clasificador de
permisos había bloqueado a los agentes que las preparaban:

1. ajustar tres tests de requisitos que usaban transiciones ya ilegales
   (`approved` → `reviewed`);
2. actualizar el dorado de `vault_pattern_save` porque la nota lleva `tags`;
3. ampliar el presupuesto de cruces de la arquitectura (`autoria ↔ durabilidad`)
   para que la papelera pase por la cuarentena y se pueda restaurar.

**Declaración literal del propietario:** «Las tres».

Efecto, ya en la historia de la rama:

| Edición | Commit |
|---|---|
| Transiciones legales en `tests/test_requirement_save_transiciones.py` | `5e808b8b` |
| Dorado `tests/dorados/saves/vault_pattern_save.json` | `b94c6f29` |
| `_cruce("autoria", "durabilidad", ...)`, `_cruce("durabilidad", "autoria", ...)`, puerto `reubicar_indices` y las dos aristas de `scripts/arch-baseline.json` | `761df59a` |

### DEC-11 — ratificación de dos divergencias del reconciliador Archify

«Las tres» aprobó el presupuesto de cruces; las divergencias del reconciliador se
preguntaron aparte (2026-11-18), como en DEC-08.

**Declaración literal del propietario:** «Ratificar las dos divergencias».

Asentadas como DIV-12 y DIV-13 en `audits/architecture/divergencias-aceptadas.yaml`.

El reconciliador (`audits/fase2/reconciliar_archify.py --check`) compara el registro
vivo con el snapshot `.archify/`. Tras DEC-09 informa dos divergencias:

| Divergencia | Causa | Evidencia |
|---|---|---|
| `par solo en el registro: ['autoria', 'durabilidad']` (DIV-12) | El par entró al presupuesto por DEC-09: el borrado suave es cuarentena | `761df59a` |
| `par solo en el registro: ['durabilidad', 'autoria']` (DIV-13) | El par entró al presupuesto por DEC-09: los índices los reubica el dueño de mover | `761df59a` |

Lo que se ratifica es **que el snapshot es anterior a un par aprobado por el
propietario**, no que la arquitectura pueda crecer sin decisión: cada par sigue
teniendo su motivo escrito en `vault_arch.PRESUPUESTO_DE_CRUCES`.

## DEC-10 — edición de ISO/IEC 25010

**Pregunta planteada** (2026-11-18): el `isos.txt` del propietario describe ISO/IEC
25010 en su edición 2011 (8 características de producto); la vigente es la 2023
(9 características, con la calidad en uso trasladada a ISO/IEC 25019:2023).

**Declaración literal del propietario:** «usa la edición 2023 y procede».

Efecto: el registro de calidad sigue ISO/IEC 25010:2023 y 25019:2023 y acepta los
nombres de 2011 como alias.
