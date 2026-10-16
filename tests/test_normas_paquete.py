"""La norma como paquete: `normas/<código>/` (deuda #10, piloto AP-65).

El ciclo del repo —síntoma → norma → guard+audit+heal → test— vivía en cuatro
listas que solo sincronizaba la memoria de quien las tocaba. Un paquete junta
las caras de una norma en una carpeta: `norma.py` con la entrada del catálogo,
`porque.md` con las rutas de las caras que la cumplen y un `test_*.py`.

`vault_norms_catalog` sigue siendo la fuente única: carga el paquete en el
mismo sitio que ocupaba la entrada, así que `NORM_CATALOG` no cambia ni de orden
ni de contenido. Lo que comprueba la guarda de forma lo publica
`vault_norms --check-framework`, que ya es puerta: no hace falta una nueva.

Los tests del paquete los ejecuta este fichero. La CI y el `Makefile` corren
`pytest tests/`, y un test que vive fuera de `tests/` sin que nadie lo invoque
es la promesa sin ejecutor que `vault_produccion` existe para cazar.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_norms_catalog as cat  # noqa: E402

NORMAS = ROOT / "normas"

import vault_grafo_import as gi  # noqa: E402


def _paquetes():
    return sorted(p for p in NORMAS.iterdir() if p.is_dir() and not p.name.startswith(("_", ".")))


def _anunciada_en_su_version(code: str) -> bool:
    """La entrada de changelog de su `introduced_version` nombra la norma.

    Escribir aquí la versión en que entró caducaba en el bump: mientras fue la
    corriente, `test_version_coherence` la cazó con razón (AP-47). El hecho
    histórico se comprueba contra el changelog, que es donde está escrito.
    """
    version = cat.norma_por_codigo(code)["introduced_version"]
    manifiesto = (ROOT / "vault-obsidian-architecture.md").read_text(encoding="utf-8")
    cabecera = f"\n### {version} — "
    assert cabecera in manifiesto, f"{code}: {version} no tiene entrada de changelog"
    entrada = manifiesto.split(cabecera, 1)[1].split("\n### v", 1)[0]
    return code in entrada


def test_el_piloto_ap65_vive_en_su_paquete():
    assert "AP-65" in cat.NORMAS_EN_PAQUETE
    assert (NORMAS / "AP-65" / "norma.py").is_file()
    # La entrada ya no está escrita en el catálogo: un código en dos sitios es
    # la copia que el paquete viene a quitar.
    fuente = gi.codigo_de(SCRIPTS / "vault_norms_catalog.py").read_text(encoding="utf-8")
    assert '"code": "AP-65"' not in fuente


def test_ap64_es_la_segunda_en_migrar_y_conserva_su_sitio():
    """La migración sigue por atrición: AP-64, la anterior a la piloto.

    Mismo sitio en `NORM_CATALOG` —justo antes de la piloto— y la entrada
    escrita en el catálogo desaparece: el código vive en un solo sitio.
    """
    # Desde el lote PAT+SP+CN (2026-10-09) ya no son las dos primeras de la
    # lista: `NORMAS_EN_PAQUETE` sigue el orden del catálogo, no el de llegada.
    i = cat.NORMAS_EN_PAQUETE.index("AP-64")
    assert cat.NORMAS_EN_PAQUETE[i + 1] == "AP-65"
    fuente = gi.codigo_de(SCRIPTS / "vault_norms_catalog.py").read_text(encoding="utf-8")
    assert '"code": "AP-64"' not in fuente
    codigos = [n["code"] for n in cat.NORM_CATALOG]
    assert codigos.index("AP-64") + 1 == codigos.index("AP-65")
    assert _anunciada_en_su_version("AP-64")


def test_el_catalogo_no_cambia_de_orden_ni_de_contenido():
    codigos = [n["code"] for n in cat.NORM_CATALOG]
    assert len(codigos) == len(set(codigos))
    # Sitio de siempre: tras AP-64, y los antipatrones antes del primer patrón.
    # Ni el patrón ni las normas posteriores se nombran: un código escrito en un
    # test cuenta como cobertura en la capa 4 de `vault_blueprint`, y esta
    # mención de pasada la habría inventado.
    i = codigos.index("AP-65")
    assert codigos[i - 1] == "AP-64"
    siguiente = next(n for n in cat.NORM_CATALOG[i + 1:] if n["type"] != "antipattern")
    assert siguiente["type"] == "pattern"
    ap65 = cat.norma_por_codigo("AP-65")
    assert _anunciada_en_su_version("AP-65")
    assert ap65["tools_detecting"] == ["vault_norms"]
    assert "AP-64" in ap65["distinguido_de"]


def test_todo_paquete_carga_en_el_orden_del_catalogo_y_sale_del_fuente():
    """Deuda #10 por lotes: cada norma migrada vive en un solo sitio.

    Sin nombrar códigos: uno escrito aquí contaría como cobertura en la capa 4
    de `vault_blueprint`, y migrar no es ejercitar la norma.
    """
    codigos = [n["code"] for n in cat.NORM_CATALOG]
    posiciones = [codigos.index(c) for c in cat.NORMAS_EN_PAQUETE]
    assert posiciones == sorted(posiciones)
    fuente = gi.codigo_de(SCRIPTS / "vault_norms_catalog.py").read_text(encoding="utf-8")
    escritas = [c for c in cat.NORMAS_EN_PAQUETE if f'"code": "{c}"' in fuente]
    assert escritas == []
    assert [p.name for p in _paquetes()] == sorted(cat.NORMAS_EN_PAQUETE)


def test_la_forma_de_los_paquetes_del_repo_es_valida():
    assert cat.forma_de_paquetes() == []


@pytest.mark.parametrize("falta", ["norma.py", "porque.md", "guard.py", "heal.py",
                                   "test_x_norma.py"])
def test_la_guarda_ve_la_cara_que_falta(tmp_path, falta):
    paquete = tmp_path / "AP-99"
    paquete.mkdir()
    (paquete / "norma.py").write_text('NORMA = {"code": "AP-99"}\n', encoding="utf-8")
    (paquete / "porque.md").write_text("# AP-99\n", encoding="utf-8")
    (paquete / "guard.py").write_text("GUARD: list = []\n", encoding="utf-8")
    (paquete / "heal.py").write_text("HEAL = None\nMOTIVO = 'x'\n", encoding="utf-8")
    (paquete / "test_x_norma.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    (paquete / falta).unlink()
    problemas = cat.forma_de_paquetes(tmp_path, cargadas=("AP-99",), raiz_repo=ROOT)
    assert problemas and all(p["paquete"] == "AP-99" for p in problemas)


def test_en_la_wheel_no_se_exige_el_test_que_no_viaja(tmp_path):
    """La wheel lleva `norma.py`, `porque.md`, `guard.py` y `heal.py`; el test
    lo ejecuta el repo."""
    paquete = tmp_path / "AP-99"
    paquete.mkdir()
    (paquete / "norma.py").write_text('NORMA = {"code": "AP-99"}\n', encoding="utf-8")
    (paquete / "porque.md").write_text("# AP-99\n", encoding="utf-8")
    (paquete / "guard.py").write_text("GUARD: list = []\n", encoding="utf-8")
    (paquete / "heal.py").write_text("HEAL = None\nMOTIVO = 'x'\n", encoding="utf-8")
    assert cat.forma_de_paquetes(tmp_path, cargadas=("AP-99",)) == []


def test_la_guarda_ve_el_codigo_que_no_es_su_carpeta(tmp_path):
    paquete = tmp_path / "AP-99"
    paquete.mkdir()
    (paquete / "norma.py").write_text('NORMA = {"code": "AP-98"}\n', encoding="utf-8")
    (paquete / "porque.md").write_text("# AP-99\n", encoding="utf-8")
    (paquete / "guard.py").write_text("GUARD: list = []\n", encoding="utf-8")
    (paquete / "heal.py").write_text("HEAL = None\nMOTIVO = 'x'\n", encoding="utf-8")
    (paquete / "test_x_norma.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    problemas = cat.forma_de_paquetes(tmp_path, cargadas=("AP-99",))
    assert any("AP-98" in p["problema"] for p in problemas)


def test_la_guarda_ve_el_paquete_que_nadie_carga(tmp_path):
    """Una carpeta que el catálogo no nombra es una norma que no existe para
    nadie: ni la audita `vault_norms` ni la ve `--check-framework`."""
    paquete = tmp_path / "AP-99"
    paquete.mkdir()
    (paquete / "norma.py").write_text('NORMA = {"code": "AP-99"}\n', encoding="utf-8")
    (paquete / "porque.md").write_text("# AP-99\n", encoding="utf-8")
    (paquete / "guard.py").write_text("GUARD: list = []\n", encoding="utf-8")
    (paquete / "heal.py").write_text("HEAL = None\nMOTIVO = 'x'\n", encoding="utf-8")
    (paquete / "test_x_norma.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    problemas = cat.forma_de_paquetes(tmp_path, cargadas=())
    assert [p["paquete"] for p in problemas] == ["AP-99"]


def test_la_guarda_ve_la_cara_citada_que_no_existe(tmp_path):
    """`porque.md` cita las caras como `ruta::símbolo`; una que no existe es
    AP-01 cometido en la documentación de la propia norma."""
    paquete = tmp_path / "AP-99"
    paquete.mkdir()
    (paquete / "norma.py").write_text('NORMA = {"code": "AP-99"}\n', encoding="utf-8")
    (paquete / "porque.md").write_text(
        "- criterio: `vault/kernel/contenido.py::no_existe_nunca`\n", encoding="utf-8")
    (paquete / "guard.py").write_text("GUARD: list = []\n", encoding="utf-8")
    (paquete / "heal.py").write_text("HEAL = None\nMOTIVO = 'x'\n", encoding="utf-8")
    (paquete / "test_x_norma.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    problemas = cat.forma_de_paquetes(tmp_path, cargadas=("AP-99",), raiz_repo=ROOT)
    assert any("no_existe_nunca" in p["problema"] for p in problemas)


def test_el_check_framework_publica_la_forma():
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_norms.py"), "--check-framework"],
        capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
    )
    datos = json.loads(r.stdout)
    assert datos["paquetes_de_norma"] == {"cargados": list(cat.NORMAS_EN_PAQUETE),
                                          "problemas": [], "caras_desfasadas": []}


def _tests_de_paquete():
    for paquete in _paquetes():
        for fichero in sorted(paquete.glob("test_*.py")):
            spec = importlib.util.spec_from_file_location(
                f"_norma_{paquete.name.replace('-', '_')}_{fichero.stem}", fichero)
            modulo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(modulo)
            for nombre, funcion in inspect.getmembers(modulo, inspect.isfunction):
                if nombre.startswith("test_") and funcion.__module__ == modulo.__name__:
                    yield pytest.param(funcion, id=f"{paquete.name}::{nombre}")


@pytest.mark.parametrize("funcion", list(_tests_de_paquete()))
def test_los_tests_de_cada_paquete(funcion):
    # Sin fixtures a propósito: el paquete se ejecuta igual desde aquí que con
    # `pytest normas/`, y la guarda de forma no tiene que conocer conftest.
    assert not inspect.signature(funcion).parameters
    funcion()
