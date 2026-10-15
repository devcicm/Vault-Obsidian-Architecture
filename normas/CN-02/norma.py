"""CN-02 — la entrada del catálogo, en su paquete (deuda #10, lote PAT+SP+CN).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "CN-02",
    "distinguido_de": {
        "AP-09": (
            "CN-02 es la convención general de destino: las secciones numeradas "
            "son los únicos sitios válidos. AP-09 es su incumplimiento con nombre "
            "para un tipo concreto: los runbooks fuera de la estructura. Se "
            "separa porque el runbook tiene además exigencias de contenido que "
            "CN-02 no mira."
        ),
        "AP-15": (
            "CN-02 es la nota colocada en una carpeta que no toca, dentro del "
            "esquema. AP-15 es el fichero externo depositado en la raíz del "
            "vault, que ni siquiera es una nota. El discriminador es si el "
            "fichero forma parte del material del vault."
        ),
        "CN-01": (
            "Las dos son convenciones de ubicación y nombre. CN-01 rige el nombre "
            "del fichero —minúsculas con guiones—; CN-02 rige el destino —las "
            "secciones numeradas—. Un fichero bien nombrado en la carpeta "
            "equivocada incumple solo CN-02."
        ),
    },
    "name": "Numbered folder structure — secciones numeradas como únicos destinos",
    "type": "antipattern",
    "category": "convention",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "Solo las secciones numeradas del registro canónico (vault_registry.SECTIONS, "
        "fuente de verdad única — PAT-1) son destinos válidos para notas. "
        "Crear carpetas ad-hoc o escribir en la raíz viola este estándar (ver AP-15). "
        "NO duplicar la lista aquí: consultarla con vault_folder_registry o vault_registry. "
        "Desde v41.2 un vault puede declarar secciones propias NN_Nombre en "
        "00_System/secciones.json con vault_section (números libres del registro, "
        "vault_registry.NUMEROS_PROPIOS); declaradas cuentan como sección para el "
        "contrato de nota, el audit y los índices. Lo que no se declara sigue siendo CN-02."
    ),
    "signal": "Carpeta con nombre que no sigue el patrón NN_Nombre en el vault.",
    "prevention": "Elegir la sección más apropiada del vocabulario estándar. AP-15 para raíz del vault.",
    "tools_enforcing": ["vault_write", "vault_section", "vault_move"],
    "tools_detecting": ["vault_section_index", "vault_norms"],
    "introduced_version": "v30",
    "revisado_en": "2026-10-09",
}
