"""A-17 — todo grupo del registro tiene su `### Grupo N` en el manifiesto.

Medido el 2026-10-30: faltaban los encabezados de 32, 33, 35 y 36, de modo que
el manifiesto saltaba de 31 a 34 y de 34 a 37. El criterio sale del registro
(`vault_servicio.trazabilidad`), no de una lista aquí; y cada sección debe
nombrar las tools de su grupo.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

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


_APERTURA = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def _fin_del_contrato(desde):
    """El primer `## ` fuera de un bloque cercado a partir de `desde`: los
    ejemplos de nota del contrato traen sus propios `## ` dentro de fences."""
    pos, fence = 0, None
    for linea in MANIFIESTO.splitlines(keepends=True):
        m = _APERTURA.match(linea)
        if fence is None and m:
            fence = m.group(1)
        elif fence is not None and m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
            fence = None
        elif fence is None and pos > desde and linea.startswith("## "):
            return pos
        pos += len(linea)
    return len(MANIFIESTO)


def _bloques_de_grupo():
    """`{N: texto}` desde `### Grupo N` hasta el siguiente `### Grupo` o el fin
    de la sección del contrato. Un `###` interno no corta el bloque."""
    heads = [(m.start(), int(m.group(1)))
             for m in re.finditer(r"^### Grupo (\d+) — ", MANIFIESTO, re.M)]
    fin = _fin_del_contrato(heads[-1][0])
    return {n: MANIFIESTO[s:(heads[i + 1][0] if i + 1 < len(heads) else fin)]
            for i, (s, n) in enumerate(heads)}


def test_toda_tool_esta_nombrada_en_el_bloque_de_su_grupo():
    """A-18 — medido el 2026-10-30: 18 tools solo salían fuera del bloque de su
    `group_id` (en la sección de otro grupo, en el changelog o en ninguna parte
    de la sección del contrato). Que el manifiesto las nombre en algún sitio no
    basta: quien busca una tool la busca en el bloque de su grupo."""
    bloques = _bloques_de_grupo()
    fuera = sorted((n, t) for n, ts in _grupos().items() for t in ts
                   if not re.search(rf"\b{t}\b", bloques.get(n, "")))
    assert not fuera, f"tools no nombradas en el bloque de su grupo: {fuera}"
