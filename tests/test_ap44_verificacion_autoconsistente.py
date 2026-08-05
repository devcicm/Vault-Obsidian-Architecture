"""AP-44 — la tool que verifica con su propio criterio se certifica a sí misma.

La norma cubre cinco fallos encontrados sanando el vault de BuilderX que tienen
la MISMA forma: una tool escribe o mide con un criterio propio, verifica con ese
mismo criterio, y por eso no puede ver su error.

  * `vault_graph_fix` indexaba destinos por `title:` y declaraba reparado un
    enlace que Obsidian no resuelve.
  * `vault_audit` hacía lo mismo al contar enlaces rotos: 86 donde había 37.
  * `vault_audit` leía frontmatter con un regex por líneas, ciego a las listas
    YAML que `vault_write` escribe: 45 notas etiquetadas, reportadas sin tags.
  * `vault_mermaid_check` validaba con patrones anclados: 23 de 23 hallazgos
    `undefined_node` falsos, a -2 puntos de health score cada uno.
  * `vault_init` escribía primers sin `status` que el audit del mismo estándar
    reprobaba: 18 de 18.

El síntoma automatizable —el que este guard detecta— es el más nítido: **un
wikilink que solo resuelve por `title:`**. Obsidian resuelve por nombre de
fichero o por `aliases:`, nunca por `title:`. Ese enlace está verde para el
tooling y muerto para quien lee, y la brecha entre los dos criterios es
exactamente la lista que el guard emite: 49 instancias en la baseline de
BuilderX, 0 tras la sanación.

Por qué es `critical` y no `high`: un guard en verde que apunta al sitio
equivocado es peor que no tener guard. Dirige el trabajo a reescribir enlaces
que funcionan, y cada reescritura puede romper uno que estaba bien.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_norms as vn  # noqa: E402


def _vault(tmp_path: Path) -> Path:
    root = tmp_path / "v"
    for sec in ("00_System", "01_Projects", "99_Index"):
        (root / sec).mkdir(parents=True)
        (root / sec / "index.md").write_text("# index\n", encoding="utf-8")
    return root


def _ap44(root: Path):
    r = vn.vault_norms_audit(root)
    return [
        v
        for v in r.get("violations", [])
        if (v.get("norm") or v.get("code")) == "AP-44"
    ]


def test_la_norma_existe_y_no_es_manual():
    norma = next(n for n in vn.NORM_CATALOG if n["code"] == "AP-44")
    assert norma["enforcement"] in ("guard", "audit", "guard+audit", "recommended")
    assert norma["enforcement"] == "guard+audit"
    assert norma["tools_detecting"], "una norma sin detector no gobierna nada"


def test_un_enlace_que_solo_casa_por_title_se_reporta(tmp_path):
    """El caso literal: 49 instancias en la baseline de BuilderX."""
    root = _vault(tmp_path)
    (root / "01_Projects" / "ap-levenshtein-dual.md").write_text(
        "---\ntitle: AP-MAINT-01\nstatus: draft\ntype: reference\n---\n\n# n\n",
        encoding="utf-8",
    )
    (root / "01_Projects" / "origen.md").write_text(
        "---\ntitle: Origen\nstatus: draft\ntype: reference\n---\n\nVer [[AP-MAINT-01]].\n",
        encoding="utf-8",
    )

    hallazgos = _ap44(root)
    assert len(hallazgos) == 1
    assert "01_Projects/origen.md" in hallazgos[0]["path"].replace("\\", "/")


def test_anadir_el_alias_al_destino_cierra_el_hallazgo(tmp_path):
    """La reparación correcta: alias en el destino, no reescribir la llamada.

    El texto legible del enlace es contenido. Sustituirlo por un slug degrada la
    nota para arreglar una métrica — que es el error que AP-44 previene.
    """
    root = _vault(tmp_path)
    (root / "01_Projects" / "ap-levenshtein-dual.md").write_text(
        "---\ntitle: AP-MAINT-01\naliases:\n- AP-MAINT-01\nstatus: draft\n"
        "type: reference\n---\n\n# n\n",
        encoding="utf-8",
    )
    (root / "01_Projects" / "origen.md").write_text(
        "---\ntitle: Origen\nstatus: draft\ntype: reference\n---\n\nVer [[AP-MAINT-01]].\n",
        encoding="utf-8",
    )

    assert _ap44(root) == []


def test_un_enlace_que_casa_por_nombre_de_fichero_no_se_reporta(tmp_path):
    """No puede convertirse en ruido sobre enlaces que ya funcionan."""
    root = _vault(tmp_path)
    (root / "01_Projects" / "destino.md").write_text(
        "---\ntitle: Un Titulo Distinto\nstatus: draft\ntype: reference\n---\n\n# d\n",
        encoding="utf-8",
    )
    (root / "01_Projects" / "origen.md").write_text(
        "---\ntitle: O\nstatus: draft\ntype: reference\n---\n\nVer [[destino]].\n",
        encoding="utf-8",
    )

    assert _ap44(root) == []


def test_un_enlace_roto_de_verdad_no_es_AP44(tmp_path):
    """AP-44 es 'resuelve para la tool y no para el lector', no 'roto'.

    Un destino que no existe en ninguna forma es AP-14, no AP-44. Confundirlos
    volvería a mezclar dos listas de trabajo distintas: una es añadir alias, la
    otra es crear o corregir la nota.
    """
    root = _vault(tmp_path)
    (root / "01_Projects" / "origen.md").write_text(
        "---\ntitle: O\nstatus: draft\ntype: reference\n---\n\nVer [[no-existe-nada]].\n",
        encoding="utf-8",
    )

    assert _ap44(root) == []


def test_no_reporta_dentro_de_una_instantanea(tmp_path):
    """Coherente con AP-36: un backup no se corrige, se conserva."""
    root = _vault(tmp_path)
    (root / "01_Projects" / "destino.md").write_text(
        "---\ntitle: Titulo Legible\nstatus: draft\ntype: reference\n---\n\n# d\n",
        encoding="utf-8",
    )
    snap = root / "vault-backups" / "snap" / "01_Projects"
    snap.mkdir(parents=True)
    (snap / "vieja.md").write_text(
        "---\ntitle: V\nstatus: draft\ntype: reference\n---\n\nVer [[Titulo Legible]].\n",
        encoding="utf-8",
    )

    assert _ap44(root) == []


def test_el_mensaje_nombra_el_destino_y_la_reparacion(tmp_path):
    """Un hallazgo que no dice qué hacer obliga a re-investigar el mismo caso."""
    root = _vault(tmp_path)
    (root / "01_Projects" / "destino.md").write_text(
        "---\ntitle: Titulo Legible\nstatus: draft\ntype: reference\n---\n\n# d\n",
        encoding="utf-8",
    )
    (root / "01_Projects" / "origen.md").write_text(
        "---\ntitle: O\nstatus: draft\ntype: reference\n---\n\nVer [[Titulo Legible]].\n",
        encoding="utf-8",
    )

    texto = " ".join(str(v) for v in _ap44(root))
    assert "destino.md" in texto
    assert "aliases" in texto
