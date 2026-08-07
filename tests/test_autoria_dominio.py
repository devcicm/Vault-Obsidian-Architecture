"""El contexto Autoría, el último en migrarse — y donde estaba toda la deuda.

Al llegar aquí los otros ocho contextos estaban a cero y Autoría concentraba
**los 31 vínculos congelados restantes**: el 100% de AP-49. La causa se ve en el
diff: veinticinco módulos derivaban `SECCION_DIR = VAULT_ROOT / "0X_Loquesea"`
en tiempo de import, cada uno copiado del fichero de al lado. `set_vault_root()`
existía desde hacía versiones y no podía reapuntar a ninguno.

Con esta fase el guard mide 0. Es la primera vez que la costura de inyección
del estándar es real en todo el dominio y no una costura que existe pero no se
usa.
"""

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import vault_arch  # noqa: E402
from vault.autoria import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402


# ── El repositorio ────────────────────────────────────────────────────────────


def test_las_secciones_se_validan_contra_el_registro_canonico(tmp_path):
    """No se enumeran aquí: `vault_registry.ORDERED_SECTIONS` es la fuente única.

    Veintidós constantes copiadas en veinticinco módulos eran veintidós
    oportunidades de que un typo creara una carpeta nueva en el vault del
    usuario sin que nada lo notara (AP-05 + AP-37).
    """
    import vault_registry

    repo = RepositorioAutoria(construir(tmp_path / "v"))
    for seccion in vault_registry.ORDERED_SECTIONS:
        assert repo.seccion(seccion) == tmp_path / "v" / seccion


def test_una_seccion_inventada_falla_ruidosamente(tmp_path):
    """El modo silencioso sería crear la carpeta y seguir."""
    repo = RepositorioAutoria(construir(tmp_path / "v"))
    with pytest.raises(ValueError, match="no es una sección del estándar"):
        repo.seccion("21_Inventada")


def test_dos_vaults_en_el_mismo_proceso_no_se_contaminan(tmp_path):
    a = RepositorioAutoria(construir(tmp_path / "a"))
    b = RepositorioAutoria(construir(tmp_path / "b"))
    assert a.seccion("01_Projects") != b.seccion("01_Projects")
    assert a.indice_busqueda != b.indice_busqueda


def test_las_rutas_ajenas_se_piden_a_su_dueno(tmp_path):
    """Autoría lee y actualiza cuatro ficheros que no define.

    El índice de búsqueda, el de hashes y el registro de etiquetas los construye
    Índices; el grafo, Grafo. Declararlos aquí habría sido la cuarta copia de
    `search-index.json` dentro de `vault/` — y la delató la puerta nueva
    `vault_arch.rutas_duplicadas()`, no una revisión a ojo.
    """
    from vault.grafo.repositorio import RepositorioGrafo
    from vault.indices.repositorio import RepositorioIndices

    ctx = construir(tmp_path / "v")
    repo = RepositorioAutoria(ctx)
    assert repo.indice_busqueda == RepositorioIndices(ctx).indice_busqueda
    assert repo.indice_hashes == RepositorioIndices(ctx).indice_hashes
    assert repo.registro_etiquetas == RepositorioIndices(ctx).registro_etiquetas
    assert repo.grafo == RepositorioGrafo(ctx).grafo


def test_el_repositorio_no_declara_rutas_ajenas():
    fuente = (ROOT / "vault" / "autoria" / "repositorio.py").read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    literales = {
        n.value
        for nodo in arbol.body
        if isinstance(nodo, ast.Assign)
        for n in ast.walk(nodo)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }
    for ajeno in ("search-index.json", "hash-index.json", "tag-registry.json",
                  "graph.json", ".change-log.json"):
        assert ajeno not in literales, ajeno


# ── El adaptador ──────────────────────────────────────────────────────────────


def test_la_bitacora_de_cambios_la_declara_gobernanza(tmp_path):
    """`vault_change_log` la escribe; `vault_fundamentals` y `vault_quality_check`
    la leen. Tres sitios derivando la misma ruta es AP-05, y el día que se
    moviera solo se enteraría el que escribe: el que lee devuelve `{}`.
    """
    import vault_change_log
    import vault_io
    from vault.gobernanza.repositorio import RepositorioGobernanza

    raiz = tmp_path / "v"
    vault_io.set_vault_root(raiz)  # lo deshace el fixture autouse de conftest
    assert vault_change_log._log_json() == RepositorioGobernanza(
        construir(raiz)
    ).bitacora_cambios


def test_un_save_escribe_en_el_vault_que_se_le_apunta(tmp_path):
    """El criterio que decide si la inyección es real o decorativa.

    Antes de migrar, `PATTERNS_DIR` se evaluaba al importar: apuntar la raíz
    después no movía nada y el `*_save` escribía en el vault detectado.
    """
    import vault_io
    import vault_pattern_save

    raiz = tmp_path / "v"
    (raiz / "05_Patterns").mkdir(parents=True)
    vault_io.set_vault_root(raiz)

    assert vault_pattern_save._patterns_dir() == raiz / "05_Patterns"
    assert vault_pattern_save._index_file() == raiz / "05_Patterns" / "index.json"


# ── La deuda de AP-49, saldada ────────────────────────────────────────────────


def test_ningun_modulo_de_autoria_congela_la_raiz():
    congelados = {v["module"] for v in vault_arch.vinculos_congelados()}
    del_contexto = set(vault_arch.CONTEXTS["autoria"]["modulos"])
    assert congelados & del_contexto == set()


def test_no_queda_un_solo_vinculo_congelado_en_el_repo():
    """Eran 82 en 62 módulos. La costura de inyección por fin sirve entera.

    Este test es el que convierte el refactor en irreversible: cualquier módulo
    nuevo que vuelva a derivar su ruta al importarse lo rompe.
    """
    assert vault_arch.vinculos_congelados() == []
