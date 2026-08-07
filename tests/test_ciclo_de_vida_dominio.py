"""El contexto Ciclo de vida, probado por donde ahora vive.

Es el único contexto que se ejecuta **contra vaults ajenos** por diseño: el modo
agéntico de sanación apunta con `VAULT_ROOT` a un vault que no construyó este
estándar. Ahí la raíz pedida y la detectada casi nunca coinciden, así que
congelarla no produce un fallo ruidoso — produce un informe verosímil del vault
equivocado. Eso es lo que se fija aquí.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from vault.ciclo_de_vida.repositorio import RepositorioCicloDeVida  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _vault(raiz: Path) -> Path:
    for seccion in ("00_System", "10_Migrated", "99_Index", "01_Projects"):
        (raiz / seccion).mkdir(parents=True, exist_ok=True)
    return raiz


def _repo(raiz: Path) -> RepositorioCicloDeVida:
    return RepositorioCicloDeVida(construir(raiz))


# ── El criterio de aceptación ────────────────────────────────────────────────


def test_dos_vaults_resuelven_sus_rutas_en_el_mismo_proceso(tmp_path):
    a, b = _repo(_vault(tmp_path / "a")), _repo(_vault(tmp_path / "b"))

    assert a.fichero_version.is_relative_to(tmp_path / "a")
    assert b.fichero_version.is_relative_to(tmp_path / "b")
    assert a.dir_staging != b.dir_staging


def test_el_repositorio_no_deja_salir_del_vault(tmp_path):
    repo = _repo(_vault(tmp_path / "v"))
    with pytest.raises(ValueError, match="AP-36"):
        repo.ctx.ruta("..", "fuera.json")


def test_el_staging_cuelga_de_migrados(tmp_path):
    """Dos rutas derivadas de una: si se separan, la migración deja el material
    en un sitio y lo publica desde otro."""
    repo = _repo(_vault(tmp_path / "v"))
    assert repo.dir_staging.is_relative_to(repo.dir_migrados)


def test_cambiar_el_vault_alcanza_al_fichero_de_version(tmp_path):
    import vault_io
    import vault_standard_upgrade

    vault_io.set_vault_root(_vault(tmp_path / "nuevo"))
    assert vault_standard_upgrade._version_file() == (
        tmp_path / "nuevo" / "00_System" / "standard-version.json"
    ).resolve()


# ── El defecto que encontró esta fase ────────────────────────────────────────


def test_la_sanacion_audita_el_vault_que_le_piden(tmp_path):
    """`vault_sanacion` reasignaba `vault_audit.VAULT_ROOT`.

    Tras migrar Gobernanza esa constante dejó de existir: la asignación seguía
    siendo legal y no hacía nada, así que las fases 2, 4 y 12 medían el vault
    **detectado** en vez del pedido, sin excepción que lo delatara. Es el modo
    de fallo que el modo agéntico de sanación no puede permitirse, porque corre
    justamente contra vaults que no son el detectado.
    """
    import vault_sanacion

    ajeno = _vault(tmp_path / "ajeno")
    (ajeno / "01_Projects" / "una-nota.md").write_text(
        "---\ntitle: Una nota\nstatus: draft\n---\n\nCuerpo.\n", encoding="utf-8"
    )

    medida = vault_sanacion._medir_audit(ajeno)

    assert "_error" not in medida, medida
    rutas = " ".join(str(v) for v in medida.values())
    assert "vault-sandbox" not in rutas, (
        "midió el vault detectado, no el que se le pidió"
    )


def test_la_sanacion_no_deja_reapuntado_el_vault_del_proceso(tmp_path):
    """Read-only significa también no dejar rastro en el proceso: apuntar la
    raíz y no devolverla reapuntaría el vault de quien llamó."""
    import vault_io
    import vault_sanacion

    antes = vault_io.get_vault_root()
    vault_sanacion._medir_audit(_vault(tmp_path / "ajeno"))
    assert vault_io.get_vault_root() == antes


# ── La frontera con Gobernanza ───────────────────────────────────────────────


def test_la_cola_de_propagacion_es_la_misma_ruta_en_los_dos_modulos_que_la_escriben(
    tmp_path,
):
    import vault_audit
    import vault_io
    import vault_propagate

    vault_io.set_vault_root(_vault(tmp_path / "v"))
    assert vault_propagate._propagation_queue() == vault_audit._propagation_queue()


def test_el_repositorio_de_ciclo_de_vida_no_declara_la_cola():
    """El guard de la frontera: si alguien añade `propagation-queue.json` aquí,
    son dos sitios decidiendo dónde vive la cola (AP-05)."""
    import ast

    fuente = (
        Path(__file__).parent.parent / "vault" / "ciclo_de_vida" / "repositorio.py"
    ).read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    # Se mira el código, no el texto: el docstring del módulo nombra la cola a
    # propósito, para explicar por qué NO está declarada aquí.
    literales = {
        n.value
        for nodo in arbol.body
        if isinstance(nodo, ast.Assign)
        for n in ast.walk(nodo)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }
    assert "propagation-queue.json" not in literales


def test_el_cableado_entre_contextos_esta_declarado():
    """Cablear en silencio es como se coló AP-48: el cruce tiene que verse."""
    import vault_arch

    cruces = {f"{c['from']} -> {c['to']}" for c in vault_arch.cruces()}
    assert "vault_propagate -> vault/gobernanza" in cruces


# ── AP-49 en el contexto ─────────────────────────────────────────────────────


def test_ningun_modulo_de_ciclo_de_vida_congela_la_raiz():
    import vault_arch

    congelados = {v["module"] for v in vault_arch.vinculos_congelados()}
    del_contexto = set(vault_arch.CONTEXTS["ciclo_de_vida"]["modulos"])
    assert congelados & del_contexto == set()


# ── Lectura tolerante ────────────────────────────────────────────────────────


def test_un_fichero_ausente_y_uno_corrupto_se_leen_igual_de_vacios(tmp_path):
    repo = _repo(_vault(tmp_path / "v"))
    assert repo.leer_json(repo.fichero_version) == {}
    repo.fichero_version.write_text("{roto", encoding="utf-8")
    assert repo.leer_json(repo.fichero_version) == {}
