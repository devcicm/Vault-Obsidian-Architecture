"""El contexto Meta-toolkit: el único cuya frontera es una prohibición.

Hasta v40.0 esa prohibición era prosa. `prohibe` aparecía en el registro, se
renderizaba en el plano y no la leía ningún guard — enforcement `manual`, que es
justo lo que la regla 5 de `CLAUDE.md` no permite. Peor: el enunciado que nadie
comprobaba era **falso**. Decía «no escribir en un vault» y dos módulos llevaban
años escribiendo dentro de `00_System/`.

Aquí se fija lo que sí es la frontera —artefactos derivados en `00_System/` sí,
vaults desechables para medirse sí, notas o datos del usuario no— y que el guard
la hace cumplir de verdad.
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import vault_arch  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.meta_toolkit.repositorio import RepositorioMetaToolkit  # noqa: E402


# ── El repositorio ────────────────────────────────────────────────────────────


def test_el_repositorio_resuelve_contra_la_raiz_inyectada(tmp_path):
    repo = RepositorioMetaToolkit(construir(tmp_path / "v"))
    assert repo.manifiesto_tools == tmp_path / "v" / "00_System" / "tools-manifest.json"
    assert repo.memoria_spec == tmp_path / "v" / "00_System" / "spec-memory.json"


def test_dos_vaults_en_el_mismo_proceso_no_se_contaminan(tmp_path):
    """El criterio que decide si la inyección es real o decorativa."""
    a = RepositorioMetaToolkit(construir(tmp_path / "a"))
    b = RepositorioMetaToolkit(construir(tmp_path / "b"))
    assert a.memoria_spec != b.memoria_spec


def test_el_repositorio_no_declara_rutas_ajenas():
    """`vault_spec_memory` derivaba cuatro ficheros que no son suyos.

    `quality-index.json` llegó a calcularse en cuatro módulos de tres contextos.
    Declararlos aquí habría dejado la quinta copia. Se leen del contexto que los
    escribe, y ese cruce está declarado en el baseline.
    """
    fuente = (ROOT / "vault" / "meta_toolkit" / "repositorio.py").read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    literales = {
        n.value
        for nodo in arbol.body
        if isinstance(nodo, ast.Assign)
        for n in ast.walk(nodo)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }
    for ajeno in ("quality-index.json", "propagation-queue.json",
                  ".change-log.json", "standard-version.json"):
        assert ajeno not in literales, ajeno


def test_la_memoria_spec_pide_las_rutas_ajenas_a_su_dueno(tmp_path):
    """Y las pide de verdad: no basta con no declararlas aquí.

    Se compara contra el repositorio dueño, no contra una cadena escrita a mano:
    un test que repitiera la ruta sería la quinta copia del mismo dato.
    """
    import vault_io
    import vault_spec_memory
    from vault.ciclo_de_vida.repositorio import RepositorioCicloDeVida
    from vault.gobernanza.repositorio import RepositorioGobernanza

    raiz = tmp_path / "v"
    vault_io.set_vault_root(raiz)  # lo deshace el fixture autouse de conftest
    gob = RepositorioGobernanza(construir(raiz))
    ciclo = RepositorioCicloDeVida(construir(raiz))

    assert vault_spec_memory._quality_index() == gob.indice_calidad
    assert vault_spec_memory._propagation_queue() == gob.cola_propagacion
    assert vault_spec_memory._change_log() == gob.bitacora_cambios
    assert vault_spec_memory._standard_version_file() == ciclo.fichero_version


def test_ningun_modulo_de_meta_toolkit_congela_la_raiz():
    congelados = {v["module"] for v in vault_arch.vinculos_congelados()}
    del_contexto = set(vault_arch.CONTEXTS["meta_toolkit"]["modulos"])
    assert congelados & del_contexto == set()


# ── La prohibición, ya ejecutable ─────────────────────────────────────────────


def test_la_prohibicion_se_cumple_hoy():
    assert vault_arch.escrituras_prohibidas() == []


def test_la_prohibicion_muerde_si_alguien_la_cruza(tmp_path, monkeypatch):
    """Sin este test la puerta podría estar siempre en verde por no mirar nada.

    Es el mismo fallo que AP-37 describe: un guard que no puede fallar no es un
    guard. Se planta un módulo que escribe una nota en una sección de contenido
    y se comprueba que el guard lo ve.
    """
    modulo = tmp_path / "vault_intruso.py"
    modulo.write_text(
        "from pathlib import Path\n"
        "def escribe(raiz):\n"
        "    (Path(raiz) / '01_Projects' / 'nota.md').write_text('x')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(vault_arch, "SCRIPTS_DIR", tmp_path)
    monkeypatch.setitem(
        vault_arch.CONTEXTS["meta_toolkit"], "modulos", ["vault_intruso"]
    )

    hallazgos = vault_arch.escrituras_prohibidas()
    assert [(h["module"], h["section"]) for h in hallazgos] == [
        ("vault_intruso", "01_Projects")
    ]


def test_un_vault_desechable_no_cuenta_como_cruzar_la_frontera(tmp_path, monkeypatch):
    """La otra mitad, y la que decide si la puerta sirve.

    `vault_smoke` y `vault_test_runner` levantan un vault entero en un temporal
    para probar contratos de verdad. Si el guard los marcara, se desactivaría el
    primer día — que es como mueren las puertas que solo saben decir que no.
    """
    modulo = tmp_path / "vault_intruso.py"
    modulo.write_text(
        "import tempfile\n"
        "from pathlib import Path\n"
        "def mide():\n"
        "    desechable = Path(tempfile.mkdtemp())\n"
        "    (desechable / '01_Projects').mkdir(parents=True)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(vault_arch, "SCRIPTS_DIR", tmp_path)
    monkeypatch.setitem(
        vault_arch.CONTEXTS["meta_toolkit"], "modulos", ["vault_intruso"]
    )

    assert vault_arch.escrituras_prohibidas() == []


def test_el_enunciado_de_la_frontera_ya_no_es_el_falso():
    """El anterior decía «no escribir en un vault» y era falso desde el día uno.

    `vault_manifest` escribe `00_System/tools-manifest.json`; `vault_spec_memory`
    escribe `00_System/spec-memory.json`. Lo que estaba mal era el enunciado.
    """
    prohibe = " ".join(vault_arch.CONTEXTS["meta_toolkit"]["prohibe"])
    assert "00_System" in prohibe
    assert "sección de contenido" in prohibe


def test_el_check_falla_si_hay_una_escritura_prohibida(monkeypatch):
    """La medida tiene que llegar hasta el `ok` del envelope, no quedarse dentro."""
    monkeypatch.setattr(
        vault_arch, "escrituras_prohibidas",
        lambda: [{"module": "x", "line": 1, "call": "write_text", "section": "01_Projects"}],
    )
    resultado = vault_arch.check()
    assert resultado["ok"] is False
    assert resultado["forbidden_writes"]
