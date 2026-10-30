"""A-17 — todo grupo del registro tiene su `### Grupo N` en el manifiesto.

Medido el 2026-10-30: faltaban los encabezados de 32, 33, 35 y 36, de modo que
el manifiesto saltaba de 31 a 34 y de 34 a 37. El criterio sale del registro
(`vault_servicio.trazabilidad`), no de una lista aquí; y cada sección debe
nombrar las tools de su grupo.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_servicio  # noqa: E402

MANIFIESTO = (ROOT / "vault-obsidian-architecture.md").read_text(encoding="utf-8")


def _grupos():
    t = vault_servicio.trazabilidad()
    filas = t["trace"] if isinstance(t, dict) else t
    por_grupo = {}
    for f in filas:
        por_grupo.setdefault(f["group_id"], []).append(f["tool"])
    return por_grupo


def _seccion(n):
    m = re.search(rf"^### Grupo {n} — .*?(?=^### |\Z)", MANIFIESTO, re.S | re.M)
    return m.group(0) if m else None


def test_todo_grupo_del_registro_tiene_encabezado():
    faltan = [n for n in _grupos() if _seccion(n) is None]
    assert not faltan, f"grupos sin `### Grupo N` en el manifiesto: {faltan}"


def test_las_secciones_nuevas_nombran_las_tools_de_su_grupo():
    grupos = _grupos()
    for n in (32, 33, 35, 36):
        cuerpo = _seccion(n)
        sin = [t for t in grupos[n] if t not in cuerpo]
        assert not sin, f"grupo {n} no nombra: {sin}"


def test_toda_tool_del_registro_esta_nombrada_en_el_manifiesto():
    """Eran tres sin una palabra en el manifiesto (vault_gobernanza, vault_undo,
    vault_history_compact): el README las tenía, la fuente normativa no."""
    sin = [t for ts in _grupos().values() for t in ts if t not in MANIFIESTO]
    assert not sin, f"tools sin mención en el manifiesto: {sin}"
