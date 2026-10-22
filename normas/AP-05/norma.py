"""AP-05 — la entrada del catálogo, en su paquete (deuda #10, lote AP-01..AP-20).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-05",
    "distinguido_de": {
        "AP-67": (
            "AP-05 es el dato repetido en dos sitios. AP-67 es el dato que no esta en ninguno: el vault declara un proyecto y no tiene ni una nota de su codigo. Son las dos direcciones del mismo encargo: una sola fuente de verdad."
        ),
        "AP-63": (
            "AP-05 compara valores dentro de un ámbito; AP-63 es el nombre que "
            "decide el ámbito. Con el nombre del proyecto bifurcado, dos notas "
            "con valores distintos parecen de proyectos distintos y AP-05 no "
            "ve el conflicto: AP-63 se salda antes para que AP-05 pueda medir."
        ),
        "PAT-1": (
            "AP-05 es el defecto: el mismo dato con valores distintos en varias "
            "notas del mismo ámbito. PAT-1 es el patrón que lo cierra: una nota "
            "canónica declara el dato y las demás la enlazan. Se declaran aparte "
            "porque PAT-1 se aplica también donde AP-05 aún no ha ocurrido."
        ),
    },
    "name": "Múltiples fuentes de verdad para el mismo dato",
    "type": "antipattern",
    "category": "structure",
    "severity": "critical",
    "enforcement": "audit",
    "description": (
        "El mismo dato (IP, URL, versión, configuración) aparece en múltiples notas "
        "con valores inconsistentes. Causa decisiones del agente basadas en datos erróneos."
    ),
    "signal": "IPs/URLs/versiones que difieren entre notas del mismo proyecto.",
    "prevention": "PAT-1 (canonical source anchoring): una nota canónica por dato, las demás hacen [[wiki-link]] a ella.",
    "tools_enforcing": [],
    "tools_detecting": ["vault_fuente_unica"],
    "cobertura_parcial": (
        "Detectada desde v40.15 **en su parte decidible**, y el resto se declara "
        "en vez de darse por cubierto. `vault_fuente_unica` compara valores "
        "**tipados** —IP, URL, puerto, semver— escritos como `clave: valor` "
        "dentro de un mismo ámbito. Ahí la identidad del dato no hay que "
        "adivinarla, porque está escrita al lado, y la divergencia es una "
        "desigualdad de cadenas: no hacen falta embeddings. Lo que sigue sin "
        "medir nadie es la divergencia **en prosa** («el servidor está en el "
        ".20»), la de valores sin tipo y la del sinónimo (`ip:` frente a "
        "`direccion_ip:`). Verde no prueba una sola fuente de verdad; prueba "
        "que no hay divergencia de la clase que se puede decidir sin "
        "interpretar. Estuvo descubierta desde v19 porque el problema se "
        "planteó entero, y entero sigue abierto."
    ),
    "introduced_version": "v19",
    "revisado_en": "2026-10-09",
}
