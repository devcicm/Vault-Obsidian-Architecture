"""El manifiesto del propio estándar cumple AP-25.

Medido 2026-10-18: `vault-obsidian-architecture.md` (el documento normativo
público del estándar) tenía 13 errores Mermaid en sus propios diagramas —
el estándar publicando artefactos que violaban su propia norma AP-25. La
causa raíz fue doble:

1. `validate_state` no aceptaba `state Nombre` sin llaves como
   declaración, ni auto-declaraba estados desde transiciones (el parser era
   más estricto que Mermaid real).
2. Los `classDiagram` del manifiesto referenciaban clases sin
   `class Nombre { }` previo.

Este test cierra el ciclo: el manifiesto pasa el validador del estándar
que el propio estándar exporta. Si vuelve a romperse, `vault_mermaid_check`
lo cazará en CI (el workflow `vault-ci.yml` ejecuta el guard contra la
`00_System/` del sandbox; el manifiesto se audita con este test porque
vive en la raíz del repo, no en una sección del vault).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vault"))

from vault.kernel.mermaid_reglas import validate_mermaid  # noqa: E402

MANIFEST = ROOT / "vault-obsidian-architecture.md"

#: Extrae cada bloque ```mermaid ... ``` del manifiesto. El parser oficial
#: de Mermaid vive en otra dependencia; este regex basta para esta auditoría
#: porque la gramática del estándar (`vault_mermaid_reglas`) también se
#: aplica sobre el texto crudo del bloque.
_MERMAID_BLOCK = re.compile(r"```mermaid\n(.*?)\n```", re.DOTALL)


def _todos_los_bloques() -> list[tuple[int, str]]:
    """Lista `(línea, contenido)` de cada bloque Mermaid del manifiesto."""
    if not MANIFEST.exists():
        return []
    texto = MANIFEST.read_text(encoding="utf-8", errors="replace")
    return [
        (texto.count("\n", 0, m.start()) + 1, m.group(1))
        for m in _MERMAID_BLOCK.finditer(texto)
    ]


def test_manifiesto_tiene_al_menos_un_bloque_mermaid():
    """El manifiesto documenta al menos un diagrama (es la fuente que más
    se referencia; si lo borran, este test falla y obliga a actualizar la
    promesa)."""
    bloques = _todos_los_bloques()
    assert len(bloques) >= 1, (
        f"se esperaba ≥1 bloque Mermaid en {MANIFEST.name}, hay 0"
    )


def test_manifiesto_pasa_ap25_sin_errores_de_sintaxis():
    """Ningún bloque Mermaid del manifiesto viola AP-25.

    Excluye los avisos de severidad `info` (e.g. `unlabeled_node`) — son
    recomendaciones, no errores: una arista `A --> B` sin definir A ni B es
    válida en Mermaid real (se dibuja con el id como etiqueta). Lo que NO
    pasa son `unknown_type`, `mismatched_braces`, `mismatched_brackets`,
    `undefined_state`, `undefined_class`, `undefined_entity`.
    """
    severidades_bloqueantes = {"error"}
    total_bloqueantes: list[tuple[int, str, str]] = []
    for linea, bloque in _todos_los_bloques():
        for err in validate_mermaid(bloque):
            sev = str(err.get("severity", "error")).lower()
            if sev in severidades_bloqueantes:
                total_bloqueantes.append(
                    (linea, err.get("type", "?"), err.get("message", ""))
                )
    assert not total_bloqueantes, (
        "AP-25 roto en el manifiesto:\n"
        + "\n".join(f"  L{l}: {t}: {m}" for l, t, m in total_bloqueantes)
    )
