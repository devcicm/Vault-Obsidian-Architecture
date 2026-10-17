"""Sanadores que todavía escriben nota a nota, fuera de `escrituras_en_lote`.

AP-47: `vault_io.escrituras_en_lote()` hace que la sección, la búsqueda y el
grafo se regeneren una vez por lote y no una vez por nota. Lo abren
`vault_frontmatter_completar` y las dos rutas de `vault_graph_fix`
(`apply_classified_fixes` y, desde el 2026-10-16, `apply_fix`); los que no,
de `vault_norms_catalog.SANADORES`, los lista `SIN_LOTE`. Está declarado como deuda
(`sanadores_sin_lote`), y este test fija el límite medido: falla en cuanto un
sanador abre el lote —la deuda encoge y hay que anotarlo— y en cuanto aparece un
sanador nuevo sin él, que es deuda nueva.
"""

import importlib
import inspect
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import vault_blueprint as bp  # noqa: E402
from vault_norms_catalog import SANADORES  # noqa: E402

#: El límite medido el 2026-10-14 sobre 35f5bad; encogió con cada sanador que
#: entró (2026-10-16: `vault_fix_brackets`, `vault_frontmatter_heal`,
#: `vault_project` y `vault_graph_fix.apply_fix`) y quedó vacío. Uno nuevo
#: sin lote lo hace crecer y es deuda nueva.
SIN_LOTE: set = set()

#: Los que no abren el lote porque no tienen nada que aplazar, con el motivo.
#: No es una lista de perdones: cada entrada tiene su test, que mide el
#: motivo, y deja de valer en cuanto el sanador escriba más de lo que dice.
FUERA_DEL_LOTE = {
    "vault_supersede": "una escritura por llamada: la sección ya se regenera una vez "
                       "(test_vault_supersede_escribe_una_nota_por_llamada)",
    "vault_norms_engine": "heal_ap46 escribe con write_bytes, no con atomic_write_text: "
                          "no hay regeneración que aplazar, y lo que falta es la "
                          "escritura atómica, deuda `heal_ap46_escribe_sin_atomic_write` "
                          "(test_limite_declarado_heal_ap46_escribe_sin_atomic_write)",
}


def _abre_el_lote(tool: str) -> bool:
    modulo = importlib.import_module(tool)
    return "escrituras_en_lote" in Path(modulo.__file__).read_text(encoding="utf-8")


def test_la_deuda_de_sanadores_sin_lote_esta_declarada():
    d = next((d for d in bp.DEUDA_DECLARADA if d["id"] == "sanadores_sin_lote"), None)
    assert d is not None
    assert d["estado"] == "pendiente" or d.get("sostenida_por")


def test_limite_declarado_sanadores_sin_lote():
    medidos = {t for t in SANADORES if not _abre_el_lote(t)}
    assert set(FUERA_DEL_LOTE) <= medidos, (
        f"{sorted(set(FUERA_DEL_LOTE) - medidos)} ya abren el lote: sobran en FUERA_DEL_LOTE")
    medidos -= set(FUERA_DEL_LOTE)
    assert medidos == SIN_LOTE, (
        f"sin lote ahora: {sorted(medidos)}; declarados: {sorted(SIN_LOTE)}. "
        "Si encogió, actualiza la deuda `sanadores_sin_lote`; si creció, el "
        "sanador nuevo tiene que abrir `vault_io.escrituras_en_lote()` (AP-47)."
    )


def test_las_dos_rutas_de_graph_fix_abren_el_lote():
    # Hasta el 2026-10-16 `apply_fix` escribía nota a nota y este test lo fijaba.
    from vault.grafo import graph_fix

    assert "escrituras_en_lote" in inspect.getsource(graph_fix.apply_classified_fixes)
    assert "escrituras_en_lote" in inspect.getsource(graph_fix.apply_fix)


# --- Cada sanador que entra en el lote --------------------------------------
# El rojo de cada uno: dos notas de la misma sección escritas por el sanador
# regeneraban la sección dos veces. El árbol con lote y sin él se comparó
# sobre copias de /ans y /vcloud antes de cada commit.

def _secciones_regeneradas(monkeypatch):
    import vault_section_index as vsi

    secciones = []
    original = vsi.vault_section_index

    def contado(folder, *a, **kw):
        secciones.append(folder)
        return original(folder, *a, **kw)

    monkeypatch.setattr(vsi, "vault_section_index", contado)
    return secciones


def _vault_con(tmp_path, monkeypatch, notas):
    import vault_io

    (tmp_path / "00_System").mkdir()
    for rel, texto in notas.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(texto, encoding="utf-8")
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    original = vault_io.get_vault_root()
    vault_io.set_vault_root(tmp_path)
    return original


def test_ap47_fix_brackets_escribe_en_lote(tmp_path, monkeypatch):
    import vault_fix_brackets
    import vault_io

    rota = "---\ntitle: {0}\n---\nver [[]] aquí\n"
    original = _vault_con(tmp_path, monkeypatch, {
        "07_Knowledge/a.md": rota.format("a"), "07_Knowledge/b.md": rota.format("b")})
    try:
        secciones = _secciones_regeneradas(monkeypatch)
        r = vault_fix_brackets.vault_fix_brackets(apply=True)
    finally:
        vault_io.set_vault_root(original)
    assert sorted(r["files_modified"]) == ["07_Knowledge/a.md", "07_Knowledge/b.md"], r
    assert secciones == ["07_Knowledge"], secciones


def test_ap47_frontmatter_heal_escribe_en_lote(tmp_path, monkeypatch):
    import vault_io
    from vault.autoria import frontmatter_heal

    roto = "---\ntitle: Overview: {0}\nid: {0}\n---\n\ncuerpo\n"
    original = _vault_con(tmp_path, monkeypatch, {
        "07_Knowledge/a.md": roto.format("a"), "07_Knowledge/b.md": roto.format("b")})
    try:
        secciones = _secciones_regeneradas(monkeypatch)
        r = frontmatter_heal.heal(apply=True)
    finally:
        vault_io.set_vault_root(original)
    assert r["healed"] == 2, r
    assert secciones == ["07_Knowledge"], secciones


def test_ap47_project_heal_escribe_en_lote(tmp_path, monkeypatch):
    import vault_io
    import vault_project

    nota = "---\ntitle: {0}\nProyecto: Pasarela\n---\n\n# {0}\n\ncuerpo\n"
    original = _vault_con(tmp_path, monkeypatch, {
        "07_Knowledge/a.md": nota.format("a"), "07_Knowledge/b.md": nota.format("b")})
    try:
        assert vault_project.registrar("mi-api", None, ["Pasarela"], "in-progress")["ok"]
        secciones = _secciones_regeneradas(monkeypatch)
        r = vault_project.sanar(apply=True)
    finally:
        vault_io.set_vault_root(original)
    assert r["healed"] == 2, r
    assert secciones == ["07_Knowledge"], secciones


def test_ap47_graph_fix_apply_fix_escribe_en_lote(tmp_path, monkeypatch):
    import vault_io
    from vault.grafo import graph_fix

    nota = "---\ntitle: {0}\n---\n\n# {0}\n\nver [[roto]]\n"
    original = _vault_con(tmp_path, monkeypatch, {
        "07_Knowledge/a.md": nota.format("a"), "07_Knowledge/b.md": nota.format("b")})
    informe = {"summary": {}, "fixes": [
        {"note": f"07_Knowledge/{n}.md", "new_content": f"\n# {n}\n\nver roto\n"}
        for n in ("a", "b")]}
    try:
        secciones = _secciones_regeneradas(monkeypatch)
        r = graph_fix.apply_fix(informe, tmp_path)
    finally:
        vault_io.set_vault_root(original)
    assert r["applied"] == 2 and not r["errors"], r
    assert secciones == ["07_Knowledge"], secciones


def test_ap47_apply_fix_no_da_por_caducado_el_indice_que_el_mismo_regenero(tmp_path, monkeypatch):
    # Medido el 2026-10-16 en una copia de /ans: sin lote, escribir una nota
    # regeneraba el `index.md` de su sección; si ese índice venía también en
    # el informe, su `source_sha` ya no cuadraba y salía STALE_REPORT —rc 1—
    # por un cambio que había hecho la propia tool.
    import vault_io
    from vault.grafo import graph_fix

    import vault_section_index

    original = _vault_con(tmp_path, monkeypatch, {
        "07_Knowledge/a.md": "---\ntitle: a\n---\n\n# a\n\nver [[roto]]\n"})
    try:
        vault_section_index.vault_section_index("07_Knowledge")
        indice = tmp_path / "07_Knowledge" / "index.md"
        assert indice.is_file()
        informe = {"summary": {}, "fixes": [
            {"note": "07_Knowledge/a.md", "new_content": "\n# a\n\nver [[a]] de nuevo\n",
             "source_sha": graph_fix._sha_del_fichero(tmp_path / "07_Knowledge" / "a.md")},
            {"note": "07_Knowledge/index.md",
             "new_content": indice.read_text(encoding="utf-8"),
             "source_sha": graph_fix._sha_del_fichero(indice)}]}
        r = graph_fix.apply_fix(informe, tmp_path)
    finally:
        vault_io.set_vault_root(original)
    assert r["applied"] == 2 and not r["errors"], r


def test_vault_supersede_escribe_una_nota_por_llamada(tmp_path, monkeypatch):
    # El motivo de FUERA_DEL_LOTE: sin bucle de escritura, un lote no aplaza
    # nada. Si un día anota varias sombras en una llamada, esto falla.
    import vault_io
    from vault.autoria import supersede

    escritas = []
    original_write = supersede.atomic_write_text

    def contada(path, *a, **kw):
        escritas.append(Path(path).name)
        return original_write(path, *a, **kw)

    monkeypatch.setattr(supersede, "atomic_write_text", contada)
    nota = "---\ntitle: {0}\n---\n\n# {0}\n\ncuerpo\n"
    original = _vault_con(tmp_path, monkeypatch, {
        "07_Knowledge/guia.md": nota.format("guia"),
        "07_Knowledge/guia-copia.md": nota.format("guia-copia")})
    try:
        secciones = _secciones_regeneradas(monkeypatch)
        r = supersede.supersede("07_Knowledge/guia-copia.md", "guia", apply=True)
    finally:
        vault_io.set_vault_root(original)
    assert r["ok"] and r["written"], r
    assert escritas == ["guia-copia.md"], escritas
    assert secciones == ["07_Knowledge"], secciones


def test_limite_declarado_heal_ap46_escribe_sin_atomic_write():
    # El motivo de FUERA_DEL_LOTE para vault_norms_engine, y la deuda que
    # destapa: falla en cuanto heal_ap46 pase por atomic_write_text, y entonces
    # la deuda se salda y el sanador entra en el lote como los demás.
    import vault_norms_engine

    fuente = inspect.getsource(vault_norms_engine.heal_ap46)
    assert "path.write_bytes(" in fuente
    assert "atomic_write_text" not in fuente
    assert "file_lock" not in fuente and "tomar_lock" not in fuente
    d = next(d for d in bp.DEUDA_DECLARADA if d["id"] == "heal_ap46_escribe_sin_atomic_write")
    assert d["estado"] == "pendiente"
