"""El dueño único del grafo de imports (v40.20).

Hasta v40.19 `vault_arch._importaciones` y `vault_ciclos._grafo` respondían a la
misma pregunta con dos criterios distintos, y `vault_criterios` (AP-57) no podía
verlo: solo mide módulos que nombran `*.md`. El criterio más básico de todo el
análisis estructural del repo estaba escrito dos veces y sin dueño.

Estos tests no comprueban que la extracción «funcione» —eso lo dicen las puertas
de `vault_arch` y `vault_ciclos`—. Comprueban las dos cosas que se perderían en
silencio: que **las dos proyecciones siguen siendo distintas y declaradas**, y
que los dos llamadores **no han vuelto a parsear por su cuenta**.

Unificar las proyecciones sin decidirlo sería el fallo caro: cambiaría los cruces
de `arch` y las aristas de `ciclos` a la vez, estrenando deuda en dos baselines
por un refactor que no arregla nada.
"""

import ast
import inspect
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_arch as A  # noqa: E402
import vault_ciclos as C  # noqa: E402
import vault_grafo_import as G  # noqa: E402


# ── Equivalencia viva con los dos llamadores ─────────────────────────────────

def test_la_proyeccion_prefijo_vault_es_la_de_vault_arch():
    for p in sorted((RAIZ / "scripts").glob("*.py")):
        assert A._importaciones(p) == G.importaciones(p, G.PREFIJO_VAULT), (
            f"{p.stem}: la proyección dejó de reproducir a `vault_arch`"
        )


def test_la_proyeccion_modulos_locales_es_la_de_vault_ciclos():
    g1, g2 = C._grafo(), G.grafo()
    assert set(g1["top"]) == set(g2["top"])
    assert set(g1["diferido"]) == set(g2["diferido"])
    for clase in ("top", "diferido"):
        for m in g1[clase]:
            assert g1[clase][m] == g2[clase][m], f"{clase}/{m} divergió"


# ── Lo que se perdería en silencio: que las proyecciones sean distintas ───────

def test_el_import_relativo_separa_las_dos_proyecciones(tmp_path, monkeypatch):
    """`vault_arch` ignora los relativos (`level != 0`); `vault_ciclos` no.

    Si alguien «simplifica» unificando este punto, los cruces de `arch` y las
    aristas de `ciclos` cambian a la vez y dos baselines estrenan deuda por un
    refactor. Este test es lo que lo impide.
    """
    (tmp_path / "vault_destino.py").write_text("", encoding="utf-8")
    origen = tmp_path / "vault_origen.py"
    origen.write_text("from .vault_destino import algo\n", encoding="utf-8")
    monkeypatch.setattr(G, "DIRECTORIO", tmp_path)

    assert G.importaciones(origen, G.PREFIJO_VAULT) == set(), (
        "PREFIJO_VAULT dejó de ignorar los imports relativos"
    )
    assert "vault_destino" in G.importaciones(origen, G.MODULOS_LOCALES), (
        "MODULOS_LOCALES dejó de contar los imports relativos"
    )


def test_el_prefijo_separa_las_dos_proyecciones(tmp_path, monkeypatch):
    """Un módulo local sin prefijo `vault_` lo ve una proyección y la otra no."""
    (tmp_path / "helpers.py").write_text("", encoding="utf-8")
    origen = tmp_path / "vault_origen.py"
    origen.write_text("import helpers\n", encoding="utf-8")
    monkeypatch.setattr(G, "DIRECTORIO", tmp_path)

    assert G.importaciones(origen, G.PREFIJO_VAULT) == set()
    assert G.importaciones(origen, G.MODULOS_LOCALES) == {"helpers"}


def test_un_modulo_ilegible_no_se_lee_como_modulo_sin_aristas(tmp_path, monkeypatch):
    """AP-51, y la razón de que las dos proyecciones difieran en tolerancia.

    En `MODULOS_LOCALES` un fichero roto **tiene** que levantar: contarlo como
    módulo sin imports lo sacaría de todo ciclo y el cero saldría fabricado, que
    es justo el defecto que AP-58 existe para impedir.
    """
    roto = tmp_path / "vault_roto.py"
    roto.write_text("def (:\n", encoding="utf-8")
    monkeypatch.setattr(G, "DIRECTORIO", tmp_path)

    assert G.importaciones(roto, G.PREFIJO_VAULT) == set()
    with pytest.raises(RuntimeError, match="ilegible"):
        G.importaciones(roto, G.MODULOS_LOCALES)


def test_una_proyeccion_inventada_no_se_lee_como_la_de_por_defecto():
    with pytest.raises(ValueError, match="proyección desconocida"):
        G.importaciones(RAIZ / "scripts" / "vault_errors.py", "la_que_me_convenga")


# ── El import diferido, que es lo que hace medible AP-58 ─────────────────────

def test_el_import_dentro_de_una_funcion_cae_en_diferido(tmp_path, monkeypatch):
    (tmp_path / "vault_destino.py").write_text("", encoding="utf-8")
    (tmp_path / "vault_origen.py").write_text(
        "import vault_destino\n"
        "def f():\n"
        "    import vault_destino as _v\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(G, "DIRECTORIO", tmp_path)
    g = G.grafo()
    assert g["top"]["vault_origen"] == {"vault_destino"}
    assert g["diferido"]["vault_origen"] == {"vault_destino"}


def test_solo_diferido_no_aparece_en_top(tmp_path, monkeypatch):
    (tmp_path / "vault_destino.py").write_text("", encoding="utf-8")
    (tmp_path / "vault_origen.py").write_text(
        "def f():\n    import vault_destino\n", encoding="utf-8")
    monkeypatch.setattr(G, "DIRECTORIO", tmp_path)
    g = G.grafo()
    assert g["top"]["vault_origen"] == set()
    assert g["diferido"]["vault_origen"] == {"vault_destino"}


# ── fan_in / fan_out se derivan, no se recorren dos veces ────────────────────

def test_fan_in_es_la_inversa_exacta_de_fan_out():
    """Dos recorridos con dos criterios es el defecto que este módulo cierra."""
    Gc = G.completo()
    fi, fo = G.fan_in(Gc), G.fan_out(Gc)
    aristas_out = {(a, b) for a, ds in fo.items() for b in ds}
    aristas_in = {(a, b) for b, os_ in fi.items() for a in os_}
    assert aristas_out == aristas_in


def test_el_kernel_sigue_siendo_lo_mas_dependido():
    """Ancla de cordura: si `vault_errors` deja de encabezar el fan-in, algo
    estructural cambió y hay que mirarlo, no ajustar el número."""
    fi = G.fan_in()
    top = sorted(fi, key=lambda m: -len(fi[m]))[:3]
    assert set(top) <= {"vault_errors", "vault_io", "vault_lib"}, top


# ── AP-57: los dos llamadores no vuelven a parsear por su cuenta ─────────────

@pytest.mark.parametrize("fn", [A._importaciones, C._grafo])
def test_los_llamadores_delegan_en_el_dueno(fn):
    """El mutante que impide la regresión.

    No basta con que hoy coincidan: si alguien reintroduce un `ast.parse` de
    imports dentro de estas dos funciones, vuelven a ser dueños del criterio y
    la divergencia puede reaparecer sin que nadie la vea. Se mira el cuerpo de
    la función, no el módulo: `vault_arch` usa `ast` legítimamente en otras
    medidas (AP-54, símbolos de los cruces sin puerto) y prohibirlo entero
    sería marcar en falso.
    """
    arbol = ast.parse(inspect.getsource(fn).lstrip())
    llamadas = {
        n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
        for n in ast.walk(arbol) if isinstance(n, ast.Call)
    }
    assert "parse" not in llamadas, (
        f"{fn.__qualname__} volvió a parsear imports por su cuenta: el criterio "
        f"tiene dueño en `vault_grafo_import` y esto es AP-57 otra vez"
    )
    fuentes = {n.value.id for n in ast.walk(arbol)
               if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
    assert fuentes & {"vault_grafo_import", "G", "_grafo_import"}, (
        f"{fn.__qualname__} no llama al dueño del grafo de imports"
    )


def test_el_dueno_no_importa_a_nadie():
    """Fan-out cero. Un dueño de criterio que importa a sus consumidores no es
    un dueño: es un nudo, y cierra el ciclo que AP-58 mide."""
    assert G.fan_out()["vault_grafo_import"] == set()


def test_codigo_de_resuelve_el_alias_a_su_dueno_y_deja_lo_demas():
    """AP-44, deuda #12: un lector por ruta de `scripts/<m>.py` medía el alias
    sin código. `codigo_de` es el único sitio que decide si una ruta es alias
    (AP-57); el escáner de la CLI y los tests de propiedad pasan por él."""
    raiz = G.DIRECTORIO.parent
    alias = G.DIRECTORIO / "vault_subgraph.py"
    assert G.codigo_de(alias) == (raiz / "vault" / "consulta" / "subgraph.py").resolve()
    # Un módulo sin migrar se lee a sí mismo; una ruta de fuera, también.
    assert G.codigo_de(G.DIRECTORIO / "vault_audit.py") == (G.DIRECTORIO / "vault_audit.py").resolve()
    fuera = raiz / "cli" / "analyzer.py"
    assert G.codigo_de(fuera) == fuera
    # Un dato que vive en scripts/ no es un alias de nada.
    dato = G.DIRECTORIO / "arch-baseline.json"
    assert G.codigo_de(dato) == dato
    # Todo alias que el puente conoce resuelve a un fichero con código.
    for nombre, dueno in G._puente().items():
        assert G.codigo_de(G.DIRECTORIO / f"{nombre}.py") == dueno
        assert any(isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Assign))
                   for n in ast.parse(dueno.read_text(encoding="utf-8")).body), nombre


def test_ningun_test_lee_un_script_por_ruta_sin_seguir_al_alias():
    """m250: medio centenar de tests leían `scripts/<m>.py` por ruta. Con la deuda
    #12 un nombre de `scripts/` puede ser un alias sin código, y el test pasaba
    midiendo nada. La forma directa —la ruta a `scripts/` entre paréntesis y
    leída en la misma expresión— tiene que pasar por `codigo_de`. La indirecta (la ruta en una variable) no la ve
    este regex: se declara, no se da por cubierta."""
    import re

    directo = re.compile(
        r"(?<!codigo_de)\(([^()]*?(?:\"scripts\"|\bSCRIPTS(?:_DIR)?\b)[^()]*?)\)\.read_text\(")
    culpables = []
    for f in sorted((G.DIRECTORIO.parent / "tests").glob("test_*.py")):
        for n, linea in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            m = directo.search(linea)
            if m and not re.search(r"\.(json|md|txt|toml|ya?ml)\b", m.group(1)):
                culpables.append(f"{f.name}:{n}")
    assert culpables == [], culpables


def test_el_grafo_mide_al_dueno_de_un_alias_y_no_al_alias():
    """AP-44, deuda #12: `grafo()` parseaba `scripts/<m>.py`, y en un módulo
    migrado eso es el alias, que no importa nada de `scripts/`. Todo migrado
    salía con fan-out 0: AP-59 lo veía puro y AP-58 no veía los ciclos que
    pasaban por él. Las aristas de un alias son las de su dueño."""
    G_ = G.completo()
    migrados = sorted(G._puente())
    assert migrados, "sin alias no hay nada que medir"
    for nombre in migrados:
        esperado = G.importaciones(G.codigo_de(G.DIRECTORIO / f"{nombre}.py"),
                                   G.MODULOS_LOCALES) - {nombre}
        assert G_[nombre] == esperado, nombre
    # Y al menos uno de ellos importa algo: si no, la igualdad no prueba nada.
    assert any(G_[n] for n in migrados)


# ── Coste: lineal en el tamaño, no en la historia de llamadas ────────────────

def _anidadas(profundidad: int) -> ast.Module:
    fuente, sangria = "", ""
    for i in range(profundidad):
        fuente += f"{sangria}def f{i}():\n"
        sangria += "    "
    fuente += f"{sangria}import vault_io\n"
    return ast.parse(fuente)


def test_en_funcion_es_lineal_en_el_anidamiento(monkeypatch):
    """Auditoría del 2026-10-15: `_en_funcion` recorría cada función entera, y
    las anidadas otra vez por cada función que las contiene — cuadrático en la
    profundidad. Se cuentan nodos visitados: con 90 niveles no pueden pasar
    de unas pocas veces el tamaño del árbol."""
    arbol = _anidadas(90)  # el parser no admite 100
    total = sum(1 for _ in ast.walk(arbol))
    visitas = []
    real = ast.iter_child_nodes
    def espia(n):
        visitas.append(1)
        return real(n)
    monkeypatch.setattr(ast, "iter_child_nodes", espia)
    dentro = G._en_funcion(arbol)
    monkeypatch.setattr(ast, "iter_child_nodes", real)
    # Mismo resultado: todo nodo bajo alguna función, y la función misma.
    esperado = {id(n) for n in ast.walk(arbol) if not isinstance(n, ast.Module)}
    assert dentro == esperado
    assert len(visitas) <= 3 * total, (len(visitas), total)


def test_el_grafo_no_vuelve_a_recorrer_un_fichero_que_no_cambio(monkeypatch):
    """`vault_recursos --check` pedía el grafo cuatro veces y cada una recorría
    los ~250 árboles otra vez (22 s de 32). Los árboles ya estaban en caché; el
    recorrido no. La segunda llamada no puede recorrer ninguno."""
    G.grafo()
    G.importaciones(RAIZ / "scripts" / "vault_arch.py")
    recorridos = []
    real = ast.walk
    def espia(n):
        recorridos.append(1)
        return real(n)
    monkeypatch.setattr(ast, "walk", espia)
    segundo = G.grafo()
    G.importaciones(RAIZ / "scripts" / "vault_arch.py")
    monkeypatch.setattr(ast, "walk", real)
    assert recorridos == []
    assert segundo == G.grafo()
