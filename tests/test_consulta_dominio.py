"""El contexto Consulta, probado por donde ahora vive.

Dos cosas se fijan aquí:

1. **Que Consulta no es dueña del grafo.** Lo lee del contexto que lo escribe.
   Si un día deriva la ruta por su cuenta, vuelve AP-05 y el día que el grafo se
   mueva solo se entera uno de los dos.
2. **Que la resolución tardía no tiene agujeros.** La forma cara de AP-49 no era
   la constante obvia: era `SYSTEM_DIR = _resolve_output_dir()`, una llamada a
   función que el guard no contaba y que se evaluaba igual al importar.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from vault.consulta.repositorio import RepositorioConsulta  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _vault(raiz: Path) -> Path:
    for seccion in ("00_System", "99_Index", "17_Preferences", "07_Knowledge"):
        (raiz / seccion).mkdir(parents=True, exist_ok=True)
    return raiz


def _repo(raiz: Path) -> RepositorioConsulta:
    return RepositorioConsulta(construir(raiz))


# ── El criterio de aceptación ────────────────────────────────────────────────


def test_dos_vaults_resuelven_sus_rutas_en_el_mismo_proceso(tmp_path):
    a, b = _repo(_vault(tmp_path / "a")), _repo(_vault(tmp_path / "b"))

    assert a.dir_preferencias.is_relative_to(tmp_path / "a")
    assert b.dir_preferencias.is_relative_to(tmp_path / "b")
    assert a.fichero_tokens != b.fichero_tokens


def test_el_repositorio_no_deja_salir_del_vault(tmp_path):
    repo = _repo(_vault(tmp_path / "v"))
    with pytest.raises(ValueError, match="AP-36"):
        repo.ctx.ruta("..", "fuera.json")


# ── La frontera con Grafo ────────────────────────────────────────────────────


def test_consulta_lee_el_grafo_de_quien_lo_escribe(tmp_path):
    """`vault_subgraph` no deriva `graph.json`: lo recibe del contexto Grafo."""
    import vault_io
    import vault_subgraph
    from vault.grafo.repositorio import RepositorioGrafo

    vault_io.set_vault_root(_vault(tmp_path / "v"))
    esperada = RepositorioGrafo(construir(tmp_path / "v")).grafo

    assert vault_subgraph._graph_file() == esperada


def test_el_repositorio_de_consulta_no_declara_el_grafo():
    """El guard de la frontera: si alguien añade `graph.json` aquí, son dos
    sitios decidiendo dónde vive el grafo (AP-05)."""
    fuente = (
        Path(__file__).parent.parent / "vault" / "consulta" / "repositorio.py"
    ).read_text(encoding="utf-8")
    assert "graph.json" not in fuente
    assert "99_Index" not in fuente


def test_el_cableado_entre_contextos_esta_declarado():
    """Cablear en silencio es como se coló AP-48: el cruce tiene que verse."""
    import vault_arch

    cruces = {f"{c['from']} -> {c['to']}" for c in vault_arch.cruces()}
    assert "vault_subgraph -> vault/grafo" in cruces


# ── AP-49, incluida su forma cara ────────────────────────────────────────────


def test_cambiar_el_vault_alcanza_a_las_preferencias(tmp_path):
    import vault_io
    import vault_preferences

    vault_io.set_vault_root(_vault(tmp_path / "nuevo"))
    assert vault_preferences._preferences_dir() == (
        tmp_path / "nuevo" / "17_Preferences"
    ).resolve()


def test_el_destino_de_los_contratos_se_resuelve_al_usarse(tmp_path):
    """`SYSTEM_DIR = _resolve_output_dir()` parecía resolución tardía y no lo
    era: la llamada se evaluaba al importar, así que el guard de AP-49 no la
    contaba y `set_vault_root()` no la alcanzaba."""
    import vault_compact_contracts as vcc

    assert callable(vcc._system_dir)
    assert vcc._contracts_json().name == "tool-contracts.json"
    assert vcc._contracts_json().parent == vcc._system_dir()


def test_las_rutas_del_servicio_de_tokens_cuelgan_del_vault(tmp_path):
    """Cuatro rutas derivadas de una sola: si una se separa, el servicio escribe
    el pid en un sitio y lo busca en otro."""
    repo = _repo(_vault(tmp_path / "v"))
    for ruta in (repo.dir_flujos_tokens, repo.pid_servicio_tokens,
                 repo.puerto_servicio_tokens):
        assert ruta.is_relative_to(repo.dir_uso_tokens)


# ── Lectura tolerante ────────────────────────────────────────────────────────


def test_un_fichero_ausente_y_uno_corrupto_se_leen_igual_de_vacios(tmp_path):
    repo = _repo(_vault(tmp_path / "v"))
    assert repo.leer_json(repo.fichero_tokens) == {}
    repo.fichero_tokens.write_text("{roto", encoding="utf-8")
    assert repo.leer_json(repo.fichero_tokens) == {}
