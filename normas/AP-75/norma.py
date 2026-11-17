"""AP-75 — the catalog entry, in its package.

Data only: `vault_norms_catalog` reads this file with `ast.literal_eval` and
does not import it, so there is room for neither an import nor an expression
that needs executing. The faces are in `porque.md`.
"""

NORMA = {
    "code": "AP-75",
    "name": "Decisión cerrada reescrita",
    "type": "antipattern",
    "category": "process",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "Un ADR aprobado se edita en su cuerpo en vez de sustituirse. Quien "
        "consultó la decisión antes ya no puede leer lo que se decidió, y "
        "quien la consulta ahora no sabe que cambió ni por qué. Torti Code lo "
        "resume: una decisión aprobada no se reescribe, se escribe la nueva y "
        "se enlaza. Cambiar el frontmatter —la transición de estado, el "
        "`superseded_by`— no reescribe el porqué; cambiar el cuerpo sí."
    ),
    "signal": (
        "Un ADR (`es_adr`) en un estado de régimen cerrado o terminal cuyo "
        "cuerpo actual no tiene la huella del cuerpo de la primera versión "
        "cerrada guardada en `.history/`. Sin ninguna versión en `.history/` "
        "la decisión sale como no verificable, no como intacta."
    ),
    "prevention": (
        "Un vault que declara `sustitucion` en `00_System/reglas.json` "
        "convierte la norma en guard: el dueño de la escritura rechaza con "
        "`IMMUTABLE_NOTE` el cambio de cuerpo de una decisión cerrada y "
        "señala `vault_supersede`. La auditoría corre siempre, declare o no "
        "el vault la sustitución: `vault_audit` publica "
        "`closedDecisionsRewritten`, contrastando con el historial de la nota."
    ),
    "tools_enforcing": ["vault_io"],
    "tools_detecting": ["vault_audit"],
    "distinguido_de": {
        "AP-73": (
            "Las dos son reescribir lo que debía conservarse. AP-73 es la "
            "fuente cruda, que no se edita nunca y no tiene sucesora: otra "
            "versión es otra fuente. AP-75 es la decisión cerrada, que sí "
            "cambia, pero escribiendo su sucesora y enlazándola."
        ),
        "AP-07": (
            "Las dos miran el ADR cerrado. AP-07 pregunta si su porqué está "
            "escrito; AP-75, si ese porqué sigue siendo el que se aprobó. Un "
            "ADR completo puede haberse reescrito, y uno incompleto puede no "
            "haberse tocado nunca."
        ),
        "AP-64": (
            "AP-64 pide que alguien responda de la decisión cerrada; AP-75, "
            "que lo que esa persona aprobó no cambie por debajo. Reescribirla "
            "deja al responsable firmando un texto que no aprobó."
        ),
    },
    "introduced_version": "v41.27",
    "revisado_en": "2026-11-17",
}
