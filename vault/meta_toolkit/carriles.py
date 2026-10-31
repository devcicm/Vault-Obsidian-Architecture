"""Hoja canónica de los carriles: qué se corre, cuándo y qué bloquea cada uno.

El dolor que resuelve está medido: cerrar cualquier cambio exigía la suite
entera (~20 min) y las puertas enteras (~11 min), así que cada commit costaba
media hora y el desarrollo dejaba de avanzar. Pero la respuesta no es correr
menos en todas partes, es **no pedirle al desarrollo lo que solo decide un
release**. Tres momentos, tres preguntas distintas:

- `dev` — ¿rompí algo de lo que toco? Se contesta con los tests que alcanzan
  al cambio (`vault_test_scope`) y las puertas de nivel `rapida`. Bloquea el
  commit en una rama de trabajo, y nada más. Mide **el commit**, no la rama:
  contra `main`, una rama de reestructura alcanza a media suite (medido: 247
  ficheros de test), y eso ya es la pregunta de `merge`.
- `merge` — ¿la rama entera cumple todo? La suite completa y todas las
  puertas, en serie. Bloquea la integración en `main`.
- `release` — ¿esto se puede publicar? `merge` más lo que solo existe sobre el
  producto construido: el candidato autorizado, la wheel instalada con sus
  puertas, el SBOM y los recibos del colector QG. Bloquea la publicación, y
  corre en la CI.

Un carril más barato **no rebaja** al siguiente: lo que `dev` deja fuera lo
exige `merge`, y `vault_test_scope` cae a `merge` cuando el cambio no tiene
subconjunto honesto (kernel, configuración de la suite, código sin mapa).

`argv` va detrás de `python`. Es un dato y no un comando que este módulo
ejecute: quien lo corre es la persona, `vault_test_scope --correr` o la CI.
`docs/CARRILES.md` se deriva de aquí (`vault_gate.py --fix-doc`), igual que el
checklist de puertas sale de `vault_gate.PUERTAS`.
"""

from typing import Any, Dict, Tuple

#: Workers de pytest en los carriles que corren tests. `-n auto` mata a un
#: worker (gw1) en la máquina de desarrollo; `-n 4`, la serie y las mitades
#: pasan. Un solo número para el subconjunto y para la suite entera.
WORKERS = 4

#: El pytest de la suite entera, tal como lo corre `merge`.
SUITE_COMPLETA: Tuple[str, ...] = (
    "-m", "pytest", "tests/", "-q", "-n", str(WORKERS), "--tb=short",
    "-p", "no:cacheprovider",
)

CARRILES: Dict[str, Dict[str, Any]] = {
    "dev": {
        "cuando": "cada cambio en una rama de trabajo, antes de su commit",
        "bloquea": "el commit en la rama de trabajo",
        "donde": "local",
        "presupuesto_s": 120,
        "pasos": [
            {"que": "tests que alcanzan a lo que se va a commitear (cae a la suite "
                    "entera si no hay subconjunto honesto, y lo dice)",
             "argv": ("scripts/vault_test_scope.py", "--changed", "--correr")},
            {"que": "puertas de nivel rapida",
             "argv": ("scripts/vault_gate.py", "--strict", "--nivel", "rapida")},
        ],
    },
    "merge": {
        "cuando": "antes de integrar una rama en main",
        "bloquea": "la integración en main",
        "donde": "local, en serie: puertas y suite comparten vault-sandbox/",
        "presupuesto_s": None,
        "presupuesto": "el de vault_metricas: puertas_duracion_s + suite_duracion_s",
        "pasos": [
            {"que": "todas las puertas",
             "argv": ("scripts/vault_gate.py", "--strict", "--nivel", "todas")},
            {"que": "la suite completa", "argv": SUITE_COMPLETA},
        ],
    },
    "release": {
        "cuando": "al etiquetar una versión (tag v*)",
        "bloquea": "la publicación del release",
        "donde": "CI: .github/workflows/release.yml",
        "presupuesto_s": None,
        "presupuesto": "el de la CI; no lo paga el desarrollo",
        "requiere": "merge",
        "pasos": [
            {"que": "el tag es el candidato autorizado de "
                    "audits/fase2/CANDIDATO-RELEASE.yaml",
             "argv": None},
            {"que": "puertas de producto sobre la wheel instalada",
             "argv": ("tests/run_product_gates.py",)},
            {"que": "SBOM e inventario de licencias",
             "argv": ("empaquetado/sbom.py", "--inventario")},
            {"que": "recibos del colector QG sobre el product_sha",
             "argv": ("audits/fase2/colector_qg.py", "--sha", "<product_sha>",
                      "--ejecutar", "--recibos", "qg-recibos", "--json",
                      "qg-informe.json"),
             "cableado": False,
             "deuda": "colector_qg_fuera_de_toda_puerta"},
        ],
    },
}
