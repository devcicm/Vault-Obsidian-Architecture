"""Las acciones de `vault_audit` para notas movidas y borradas.

Medido el 2026-10-07 en un vault de prueba:

- Con `00_System/move-log.json` y sin `99_Index/graph.json` —lo que deja un
  `vault_move` en un vault donde aún no se ha generado el grafo—, el audit
  entero caía con `UnboundLocalError`: `json_module` solo se importaba dentro
  del bloque del grafo, y el de movimientos lo usaba igual.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_audit as va  # noqa: E402


def _vault(tmp_path: Path, con_grafo: bool) -> Path:
    import vault_io

    root = tmp_path / "v"
    for sec in ("00_System", "07_Knowledge", "99_Index"):
        (root / sec).mkdir(parents=True)
        (root / sec / "index.md").write_text("# index\n", encoding="utf-8")
    (root / "00_System" / "move-log.json").write_text(
        json.dumps([{"from": "07_Knowledge/a.md", "to": "07_Knowledge/b.md"}]),
        encoding="utf-8",
    )
    if con_grafo:
        (root / "99_Index" / "graph.json").write_text(
            json.dumps({"nodes": [], "edges": [
                {"from": "07_Knowledge/c.md", "to": "__deleted__"}]}),
            encoding="utf-8",
        )
    vault_io.set_vault_root(root)
    return root


def _acciones(informe, categoria):
    return [a for a in informe.get("nextActions", []) if a.get("category") == categoria]


def test_el_audit_no_cae_con_move_log_y_sin_grafo(tmp_path):
    _vault(tmp_path, con_grafo=False)
    informe = va.vault_audit()
    assert _acciones(informe, "moved_node"), "la nota movida no generó acción"


def test_la_nota_borrada_con_entrantes_cita_ap14(tmp_path):
    """Un nodo borrado que tenía entrantes deja enlaces que no resuelven: AP-14.
    Hasta v41.2 citaba AP-15, que es material ajeno en la raíz del vault."""
    _vault(tmp_path, con_grafo=True)
    acciones = _acciones(va.vault_audit(), "deleted_node")
    assert acciones
    assert {a["norm"] for a in acciones} == {"AP-14"}


def test_la_nota_movida_cita_ap47(tmp_path):
    """La acción manda regenerar el grafo, que es un artefacto derivado: AP-47.
    Hasta v41.2 citaba AP-16, que es el campo `agent` del frontmatter."""
    _vault(tmp_path, con_grafo=True)
    acciones = _acciones(va.vault_audit(), "moved_node")
    assert acciones
    assert {a["norm"] for a in acciones} == {"AP-47"}
