"""AP-47 en lote: un sanador regenera cada sección una vez, no una por nota.

Medido el 2026-10-14 con cProfile en una copia de /ans: el 95 % de los
2990 s de `vault_frontmatter_completar --apply` sobre 504 notas era el
gancho `_auto_section_index`, que regenera el índice de la sección tras
cada escritura. Dentro de `vault_io.escrituras_en_lote()` las escrituras
se acumulan y cada sección se regenera una vez al salir, con la búsqueda
puesta al día para todas las notas escritas. El resultado tiene que ser el
mismo que escribiendo nota a nota: se mide con el consumidor (la búsqueda
y el `index.md`), no con el contador.
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

NOTAS = ("07_Knowledge/alfa.md", "07_Knowledge/beta.md", "07_Knowledge/sub/gamma.md",
         "01_Projects/delta.md")


def _texto(nombre):
    return (f"---\ntitle: {nombre}\ntags: [ops]\n---\n\n# {nombre}\n"
            f"Contenido real de {nombre} para la búsqueda.\n"
            "Segunda línea del cuerpo de la nota.\nTercera línea del cuerpo.\n")


def _vault(tmp_path, monkeypatch):
    import vault_io

    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    vault_io.set_vault_root(tmp_path)
    for rel in NOTAS:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
    return vault_io


def _contando(monkeypatch):
    import vault_section_index as vsi

    secciones = []
    original = vsi.vault_section_index

    def contado(folder, *a, **kw):
        secciones.append(folder)
        return original(folder, *a, **kw)

    monkeypatch.setattr(vsi, "vault_section_index", contado)
    return secciones


def _estado(raiz):
    indice = json.loads((raiz / "99_Index" / "search-index.json").read_text(encoding="utf-8"))
    rutas = {n["path"] for n in indice["notes"]}
    listados = {
        s: (raiz / s / "index.md").read_text(encoding="utf-8")
        for s in ("07_Knowledge", "07_Knowledge/sub", "01_Projects")}
    return rutas, {s: [l for l in t.splitlines() if "[[" in l] for s, t in listados.items()}


def test_ap47_en_lote_cada_seccion_se_regenera_una_sola_vez(tmp_path, monkeypatch):
    vault_io = _vault(tmp_path, monkeypatch)
    secciones = _contando(monkeypatch)
    with vault_io.escrituras_en_lote():
        for rel in NOTAS:
            vault_io.atomic_write_text(tmp_path / rel, _texto(Path(rel).stem))
        assert secciones == []  # nada se regenera dentro del lote
    assert sorted(secciones) == ["01_Projects", "07_Knowledge"]


def test_ap47_el_lote_deja_lo_mismo_que_nota_a_nota(tmp_path, monkeypatch):
    vault_io = _vault(tmp_path / "a", monkeypatch)
    for rel in NOTAS:
        vault_io.atomic_write_text(tmp_path / "a" / rel, _texto(Path(rel).stem))
    nota_a_nota = _estado(tmp_path / "a")

    vault_io = _vault(tmp_path / "b", monkeypatch)
    with vault_io.escrituras_en_lote():
        for rel in NOTAS:
            vault_io.atomic_write_text(tmp_path / "b" / rel, _texto(Path(rel).stem))
    assert _estado(tmp_path / "b") == nota_a_nota
    assert {"07_Knowledge/alfa.md", "07_Knowledge/sub/gamma.md",
            "07_Knowledge/sub/index.md"} <= nota_a_nota[0]


def test_ap47_un_fallo_dentro_del_lote_no_deja_las_secciones_sin_regenerar(tmp_path, monkeypatch):
    vault_io = _vault(tmp_path, monkeypatch)
    secciones = _contando(monkeypatch)
    try:
        with vault_io.escrituras_en_lote():
            vault_io.atomic_write_text(tmp_path / NOTAS[0], _texto("alfa"))
            raise RuntimeError("el sanador muere a mitad")
    except RuntimeError:
        pass
    assert secciones == ["07_Knowledge"]


def test_ap47_un_lote_anidado_lo_cierra_el_de_fuera(tmp_path, monkeypatch):
    vault_io = _vault(tmp_path, monkeypatch)
    secciones = _contando(monkeypatch)
    with vault_io.escrituras_en_lote():
        with vault_io.escrituras_en_lote():
            vault_io.atomic_write_text(tmp_path / NOTAS[0], _texto("alfa"))
        assert secciones == []
        vault_io.atomic_write_text(tmp_path / NOTAS[1], _texto("beta"))
    assert secciones == ["07_Knowledge"]


def test_ap47_frontmatter_completar_escribe_en_lote(tmp_path, monkeypatch):
    vault_io = _vault(tmp_path, monkeypatch)
    for rel in NOTAS[:3]:
        (tmp_path / rel).write_text(f"# {Path(rel).stem}\n\nCuerpo sin frontmatter.\n",
                                    encoding="utf-8")
    secciones = _contando(monkeypatch)
    from vault.autoria import frontmatter_completar

    r = frontmatter_completar.completar(apply=True, agent="pytest")
    assert r["written_count"] == 3, r
    assert secciones == ["07_Knowledge"]
