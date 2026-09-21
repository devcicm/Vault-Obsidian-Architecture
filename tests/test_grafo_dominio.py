"""El contexto Grafo, probado por donde ahora vive.

Grafo no tenía fronteras que cruzar —tres cruces salientes y uno entrante, todos
declarados— pero sí **dieciocho vínculos congelados en once módulos**, cuatro de
ellos la misma ruta calculada en sitios distintos. El trabajo de esta fase fue
AP-49 y AP-05, no desacoplar; estos tests fijan el resultado.
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from vault.grafo.repositorio import RepositorioGrafo  # noqa: E402
from vault.grafo.enlace_codigo import link_vault
from vault.kernel import construir  # noqa: E402


def _vault(raiz: Path) -> Path:
    for seccion in ("00_System", "99_Index", "06_Diagrams", "11_Code", "09_Infrastructure"):
        (raiz / seccion).mkdir(parents=True, exist_ok=True)
    return raiz


def _repo(raiz: Path) -> RepositorioGrafo:
    return RepositorioGrafo(construir(raiz))


# ── El criterio de aceptación ────────────────────────────────────────────────


def test_dos_vaults_resuelven_sus_rutas_en_el_mismo_proceso(tmp_path):
    """Si esto falla, la inyección es decorativa: era el estado del import quien
    decidía, y `set_vault_root()` no llegaba."""
    a, b = _repo(_vault(tmp_path / "a")), _repo(_vault(tmp_path / "b"))

    assert a.grafo.is_relative_to(tmp_path / "a")
    assert b.grafo.is_relative_to(tmp_path / "b")
    assert a.indice_codigo != b.indice_codigo


def test_el_repositorio_no_deja_salir_del_vault(tmp_path):
    """AP-36 es invariante del contexto, no algo que cada tool recuerde."""
    repo = _repo(_vault(tmp_path / "v"))
    with pytest.raises(ValueError, match="AP-36"):
        repo.ctx.ruta("..", "fuera.json")


# ── Una ubicación, un sitio donde se declara (AP-05) ─────────────────────────


def test_el_grafo_es_la_misma_ruta_para_todos_los_modulos_del_contexto(tmp_path):
    """`GRAPH_FILE` se calculaba por separado en `vault_graph`, `vault_impact` y
    `vault_graph_merge`: tres copias que había que mover a la vez o ninguna."""
    import vault_graph
    import vault_graph_merge
    import vault_impact
    import vault_io

    vault_io.set_vault_root(_vault(tmp_path / "v"))
    esperada = _repo(tmp_path / "v").grafo

    assert vault_graph._graph_file() == esperada
    assert vault_graph_merge._graph_file() == esperada
    assert vault_impact._graph_file() == esperada


def test_el_indice_de_codigo_es_la_misma_ruta_en_los_dos_modulos_que_lo_leen(tmp_path):
    import vault_code_sync
    import vault_graph_merge
    import vault_io

    vault_io.set_vault_root(_vault(tmp_path / "v"))
    assert vault_code_sync._code_index() == vault_graph_merge._code_index()
    assert vault_code_sync._code_index() == _repo(tmp_path / "v").indice_codigo


def test_cambiar_el_vault_alcanza_a_las_rutas_del_contexto(tmp_path):
    """Lo que AP-49 rompía: la constante ya estaba calculada al importar, así
    que la tool escribía en el vault anterior sin que nada lo detectara."""
    import vault_code_map
    import vault_io

    vault_io.set_vault_root(_vault(tmp_path / "nuevo"))
    assert vault_code_map._code_dir() == (tmp_path / "nuevo" / "11_Code").resolve()


def test_enlace_de_codigo_vive_en_grafo_y_la_fachada_legacy_delega(tmp_path):
    """El runtime y la CLI histórica comparten una sola costura @vault."""
    import vault_code_tag
    import vault_io

    root = _vault(tmp_path / "v")
    vault_io.set_vault_root(root)
    # La tool pública entra por ``wrap_main``, que inicia su ledger antes de
    # ejecutar la operación. Esta caracterización llama a la implementación
    # directamente, así que debe abrir explícitamente la misma frontera.
    vault_io.write_ledger_reset()
    source = tmp_path / "program.py"
    source.write_text("#!/usr/bin/env python3\nprint('ok')\n", encoding="utf-8")

    first = vault_code_tag.vault_code_tag_link_vault(
        "11_Code/demo/program", str(source), "Program"
    )
    again = link_vault("11_Code/demo/program", str(source), "Program", root=root)

    assert first["action"] == "linked"
    assert first["written"] == 2
    assert again["action"] == "already_present"
    assert source.read_text(encoding="utf-8").splitlines()[1].startswith(
        "# @vault: 11_Code/demo/program"
    )
    registry = _repo(root).leer_json(_repo(root).registro_etiquetas_codigo)
    assert registry["tags"]["vault:11_Code:demo:program"]["files"] == [str(source)]


def test_enlace_reemplaza_la_referencia_y_conserva_shebang(tmp_path):
    root = _vault(tmp_path / "v")
    source = tmp_path / "program.py"
    source.write_text(
        "#!/usr/bin/env python3\n# @vault: 11_Code/old/program  — Old\nprint('ok')\n",
        encoding="utf-8",
    )

    result = link_vault("11_Code/new/program.md", str(source), root=root)

    assert result["action"] == "replaced"
    lines = source.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "#!/usr/bin/env python3"
    assert lines[1].startswith("# @vault: 11_Code/new/program")


def test_enlace_de_codigo_preserva_errores_y_formato_no_soportado(tmp_path):
    root = _vault(tmp_path / "v")
    missing = link_vault("11_Code/demo/missing", str(tmp_path / "missing.py"), root=root)
    markdown = tmp_path / "note.md"
    markdown.write_text("# nota\n", encoding="utf-8")
    unsupported = link_vault("11_Code/demo/note", str(markdown), root=root)

    assert missing["error_code"] == "FILE_NOT_FOUND"
    assert unsupported["error_code"] == "UNSUPPORTED_FORMAT"


def test_servicio_de_enlace_es_importable_sin_scripts_en_sys_path(repo_root):
    """La implementación estable carga como paquete; no importa la CLI legacy."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import vault.grafo.enlace_codigo as enlace; print(enlace.__name__)",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "vault.grafo.enlace_codigo"


# ── Portabilidad del envelope ────────────────────────────────────────────────


def test_las_rutas_del_envelope_no_llevan_separador_de_windows(tmp_path):
    """`vault_graph` devolvía `99_Index\\graph.json` mientras `vault_graph_merge`
    ya devolvía POSIX: la misma ruta, dos formas, en el mismo contexto. Quien
    consume el envelope desde el MCP no resuelve la de Windows."""
    repo = _repo(_vault(tmp_path / "v"))
    assert repo.relativa(repo.grafo) == "99_Index/graph.json"
    assert repo.relativa(repo.indice_codigo) == "11_Code/.code-index.json"


# ── Lectura tolerante ────────────────────────────────────────────────────────


def test_un_grafo_ausente_y_uno_corrupto_se_leen_igual_de_vacios(tmp_path):
    repo = _repo(_vault(tmp_path / "v"))
    assert repo.leer_json(repo.grafo) == {}
    repo.grafo.write_text("{roto", encoding="utf-8")
    assert repo.leer_json(repo.grafo) == {}


def test_un_json_que_no_es_objeto_no_se_devuelve_como_tal(tmp_path):
    """Devolver una lista donde el llamador espera un dict rompe más lejos, en
    otro módulo y sin rastro del origen."""
    repo = _repo(_vault(tmp_path / "v"))
    repo.grafo.write_text("[1, 2, 3]", encoding="utf-8")
    assert repo.leer_json(repo.grafo) == {}
