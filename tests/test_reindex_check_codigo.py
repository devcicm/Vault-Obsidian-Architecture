"""AP-52 — `vault_reindex --check` con el índice desfasado lleva su código.

Medido el 2026-10-07 con `tests/banco_agente.py`: en un vault donde una nota
se borró por fuera de las tools, el paso `vault_reindex --check` del protocolo
de inicio devolvía `ok: false` y `status: index_stale` sin `error_code` ni
`recovery`. La única salida era `action`, una línea de shell en texto libre,
y el agente que decide por `recovery.action` no tenía por dónde seguir. El
detalle de la medida (`status`, `stale_in_index`, `action`, …) es un campo
estable del contrato y se conserva.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))

from vault.kernel.errores import ERROR_CATALOG  # noqa: E402


def _tool(raiz: Path, script: str, *argv: str):
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / f"{script}.py"), *argv],
        env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", cwd=str(raiz.parent), timeout=300)
    salida = p.stdout.strip()
    assert salida, p.stderr[-1000:]
    return p.returncode, json.loads(salida[salida.index("{"):])


def _vault_con_indice(tmp_path: Path) -> Path:
    raiz = tmp_path / "vault"
    raiz.mkdir()
    assert _tool(raiz, "vault_init")[1]["ok"] is True
    assert _tool(raiz, "vault_reindex", "--graph")[1]["ok"] is True
    return raiz


def test_ap52_indice_desfasado_lleva_codigo_y_recuperacion_que_lo_arregla(tmp_path):
    raiz = _vault_con_indice(tmp_path)
    (raiz / "21_QA" / "index.md").unlink()

    rc, r = _tool(raiz, "vault_reindex", "--check")
    assert rc == 1 and r["ok"] is False
    assert r["error_code"] == "INDEX_STALE", r
    assert r["status"] == "index_stale" and r["stale_in_index"] == ["21_QA/index.md"]
    assert r["action"], "el campo estable se conserva"

    rec = r["recovery"]
    catalogo = ERROR_CATALOG["INDEX_STALE"]["recovery"]
    assert (rec["action"], rec["tool"]) == (catalogo["action"], catalogo["tool"]), rec
    assert _tool(raiz, rec["tool"], *rec["args"])[1]["ok"] is True

    rc, r = _tool(raiz, "vault_reindex", "--check")
    assert rc == 0 and r["ok"] is True, r


def test_ap52_indice_al_dia_no_inventa_codigo(tmp_path):
    raiz = _vault_con_indice(tmp_path)
    rc, r = _tool(raiz, "vault_reindex", "--check")
    assert rc == 0 and r["ok"] is True, r
    assert "error_code" not in r and "recovery" not in r


def test_ap52_indice_corrupto_lo_rehace_la_misma_recuperacion(tmp_path):
    """El índice es derivado: corrupto no es DATA_FILE_CORRUPT («a mano»)."""
    raiz = _vault_con_indice(tmp_path)
    (raiz / "99_Index" / "search-index.json").write_text("{roto", encoding="utf-8")
    rc, r = _tool(raiz, "vault_reindex", "--check")
    assert r["status"] == "index_corrupt" and r["error_code"] == "INDEX_STALE", r
    assert _tool(raiz, r["recovery"]["tool"], *r["recovery"]["args"])[1]["ok"] is True
    assert _tool(raiz, "vault_reindex", "--check")[1]["ok"] is True


def test_ap52_indice_ausente_lleva_index_not_found(tmp_path):
    raiz = _vault_con_indice(tmp_path)
    (raiz / "99_Index" / "search-index.json").unlink()
    rc, r = _tool(raiz, "vault_reindex", "--check")
    assert r["status"] == "index_missing" and r["error_code"] == "INDEX_NOT_FOUND", r
    assert _tool(raiz, r["recovery"]["tool"], *r["recovery"]["args"])[1]["ok"] is True
    assert _tool(raiz, "vault_reindex", "--check")[1]["ok"] is True
