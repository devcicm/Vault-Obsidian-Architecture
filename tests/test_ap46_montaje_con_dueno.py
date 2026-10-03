"""Nadie más monta un frontmatter a mano (AP-46, 2026-10-02).

La tanda AP-46 llevó a `Frontmatter` —también en modo edición— los dieciséis
sitios que montaban el bloque con su propio escapado. `MIGRADOS` vigila esos
dieciséis por nombre; esto vigila a todos los demás, incluidos los que aún no
existen: un montaje nuevo hace fallar `vault_criterios`.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_criterios  # noqa: E402

MONTAJES = {
    "lista.py": 'def f(t):\n    return "\\n".join(["---", f"title: {t}", "---"])\n',
    "concatenado.py": 'def f(t):\n    return "---\\n" + "type: nota\\n" + "---\\n" + t\n',
    "plantilla.py": 'def f(t):\n    return f"""---\\ntitle: {t}\\n---\\n"""\n',
}

LEGITIMOS = {
    # Regla horizontal del cuerpo y prosa con dos puntos: no es un bloque.
    "informe.py": 'def f(A):\n    A("Guard: todo grupo")\n    A("---")\n',
    # Un lector compara el delimitador; el mensaje no es una línea escrita.
    "lector.py": (
        'def f(t):\n    if not t.startswith("---"):\n'
        '        return "title: falta"\n    return t.split("\\n---\\n")[0]\n'
    ),
    # Delimitador y clave en funciones distintas: ninguna monta el bloque.
    "separados.py": 'def a():\n    return "---"\n\ndef b(t):\n    return f"title: {t}"\n',
}


def _arbol(tmp_path, ficheros):
    (tmp_path / "scripts").mkdir()
    for nombre, codigo in ficheros.items():
        (tmp_path / "scripts" / nombre).write_text(codigo, encoding="utf-8")


def test_ap46_un_montaje_a_mano_se_detecta_en_sus_tres_formas(tmp_path):
    _arbol(tmp_path, MONTAJES)
    h = vault_criterios.medir_montajes(tmp_path)
    assert sorted(x["modulo"] for x in h) == sorted(f"scripts/{n}" for n in MONTAJES)
    assert all(x["dueño"].endswith(":Frontmatter") for x in h)


def test_ap46_un_lector_o_una_regla_del_cuerpo_no_son_montajes(tmp_path):
    _arbol(tmp_path, LEGITIMOS)
    assert vault_criterios.medir_montajes(tmp_path) == []


def test_ap46_el_dueno_y_lo_archivado_quedan_fuera(tmp_path):
    dueño = tmp_path / "vault" / "kernel"
    dueño.mkdir(parents=True)
    (dueño / "frontmatter_escritura.py").write_text(MONTAJES["lista.py"], encoding="utf-8")
    archivado = tmp_path / "scripts" / "_archived"
    archivado.mkdir(parents=True)
    (archivado / "viejo.py").write_text(MONTAJES["lista.py"], encoding="utf-8")
    assert vault_criterios.medir_montajes(tmp_path) == []


def test_ap46_hoy_nadie_monta_el_bloque_por_su_cuenta():
    assert vault_criterios.medir_montajes() == []


def test_ap46_un_montaje_nuevo_hace_fallar_la_puerta(monkeypatch):
    nuevo = {"modulo": "scripts/vault_nuevo.py", "criterio": "montaje_de_frontmatter",
             "senal": "f", "dueño": vault_criterios.MONTAJE_CON_DUENO["dueño"]}
    monkeypatch.setattr(vault_criterios, "medir_montajes", lambda raiz=None: [nuevo])
    r = vault_criterios.check()
    assert not r["ok"]
    assert r["new_copies"] == ["scripts/vault_nuevo.py::montaje_de_frontmatter"]
