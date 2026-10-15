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


# --- El grafo también en lote ------------------------------------------------
# Medido después de c3b7879 en la misma copia de /ans: de 210 s con cProfile,
# 115 eran `_auto_grafo`, y de ellos 110 el escáner de secretos sobre
# `graph.json` reescrito tras cada una de las 504 notas.

def _con_grafo(raiz, monkeypatch):
    import os
    import subprocess

    vault_io = _vault(raiz, monkeypatch)
    vault_io.atomic_write_text(raiz / "07_Knowledge/base.md", _texto("base"))
    r = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "vault_graph.py")],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    return vault_io


def _grafo(raiz):
    (fichero,) = [p for p in raiz.rglob("graph.json") if ".locks" not in p.parts]
    g = json.loads(fichero.read_text(encoding="utf-8"))
    aristas = sorted(json.dumps(e, sort_keys=True) for e in g.get("edges", []))
    return sorted(g["nodes"]), aristas


def _con_enlace(nombre):
    return _texto(nombre).replace("Tercera línea", "Enlaza [[base]] en la tercera línea")


def test_ap47_en_lote_el_grafo_se_refresca_una_sola_vez(tmp_path, monkeypatch):
    vault_io = _con_grafo(tmp_path, monkeypatch)
    llamadas = []
    original = vault_io.refrescar_grafo
    monkeypatch.setattr(vault_io, "refrescar_grafo",
                        lambda *a: llamadas.append(a) or original(*a))
    with vault_io.escrituras_en_lote():
        for rel in NOTAS:
            vault_io.atomic_write_text(tmp_path / rel, _con_enlace(Path(rel).stem))
        assert llamadas == []
    assert len(llamadas) == 1


def test_ap47_el_grafo_en_lote_es_el_de_nota_a_nota(tmp_path, monkeypatch):
    vault_io = _con_grafo(tmp_path / "a", monkeypatch)
    for rel in NOTAS:
        vault_io.atomic_write_text(tmp_path / "a" / rel, _con_enlace(Path(rel).stem))
    nota_a_nota = _grafo(tmp_path / "a")

    vault_io = _con_grafo(tmp_path / "b", monkeypatch)
    with vault_io.escrituras_en_lote():
        for rel in NOTAS:
            vault_io.atomic_write_text(tmp_path / "b" / rel, _con_enlace(Path(rel).stem))
    assert _grafo(tmp_path / "b") == nota_a_nota
    assert "07_Knowledge/sub/gamma.md" in nota_a_nota[0]
    assert "07_Knowledge/sub/index.md" in nota_a_nota[0]


def test_ap47_el_refresco_no_descarta_el_lote_si_la_primera_ruta_no_es_nota(tmp_path, monkeypatch):
    # El servicio miraba solo la primera ruta para decidir «not_a_note»; con
    # un lote eso dejaba fuera del grafo todas las demás.
    vault_io = _con_grafo(tmp_path, monkeypatch)
    nota = tmp_path / "07_Knowledge/alfa.md"
    nota.write_text(_con_enlace("alfa"), encoding="utf-8")
    r = vault_io.refrescar_grafo(tmp_path / "fuera.txt", nota)
    assert r.get("refreshed") is True, r
    assert "07_Knowledge/alfa.md" in _grafo(tmp_path)[0]


# --- La traza también en lote ------------------------------------------------
# Misma medida tras ca5c0bc: de 103 s, 47,6 eran `log_trace` en 191 llamadas
# (las de `log_encoding_fixes`): cada entrada relee hasta 500, reescribe el
# fichero entero y le pasa el escáner de secretos.

def _traza(monkeypatch, tmp_path):
    import vault.kernel.errors_trace as et

    vault_io = _vault(tmp_path, monkeypatch)
    escrituras = []
    original = et.escritura_atomica

    def contada(ruta, *a, **kw):
        if Path(ruta).name == ".tool-trace.json":
            escrituras.append(ruta)
        return original(ruta, *a, **kw)

    monkeypatch.setattr(et, "escritura_atomica", contada)
    return vault_io, et, escrituras


def _entradas(et):
    return [e.get("n") for e in json.loads(et.trace_file().read_text(encoding="utf-8"))]


def test_ap47_en_lote_la_traza_se_escribe_una_sola_vez(tmp_path, monkeypatch):
    vault_io, et, escrituras = _traza(monkeypatch, tmp_path)
    et.log_trace({"tool": "previa", "n": 0})
    escrituras.clear()
    with vault_io.escrituras_en_lote():
        for n in (1, 2, 3):
            et.log_trace({"tool": "t", "n": n})
        assert escrituras == []
        assert _entradas(et) == [0]
    assert len(escrituras) == 1
    assert _entradas(et) == [0, 1, 2, 3]


def test_ap47_la_traza_en_lote_respeta_la_rotacion(tmp_path, monkeypatch):
    vault_io, et, _ = _traza(monkeypatch, tmp_path)
    monkeypatch.setattr(et, "TRACE_MAX_ENTRIES", 3)
    with vault_io.escrituras_en_lote():
        for n in range(5):
            et.log_trace({"tool": "t", "n": n})
    assert _entradas(et) == [2, 3, 4]


def test_ap47_la_traza_en_lote_se_escribe_aunque_el_lote_falle(tmp_path, monkeypatch):
    vault_io, et, _ = _traza(monkeypatch, tmp_path)
    try:
        with vault_io.escrituras_en_lote():
            et.log_trace({"tool": "t", "n": 1})
            raise RuntimeError("fallo a mitad del lote")
    except RuntimeError:
        pass
    assert _entradas(et) == [1]
