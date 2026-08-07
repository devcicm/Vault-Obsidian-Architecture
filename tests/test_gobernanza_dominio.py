"""El contexto Gobernanza, probado por donde ahora vive.

Gobernanza es el contexto con más acoplamiento entrante del estándar —veintisiete
módulos de siete contextos importan `vault_norms`—, así que su estado propio es
el que más lejos llega si se congela mal. Lo que se fija aquí:

1. **Que dos vaults conviven en el mismo proceso.** El criterio de aceptación del
   refactor, aplicado al contexto que más consumidores tiene.
2. **Que las ubicaciones compartidas se deciden en un solo sitio.**
   `quality-index.json` lo calculaban `vault_audit` y `vault_quality_check`;
   `.change-log.json`, `vault_fundamentals` y `vault_quality_check`. Dos módulos
   derivando la misma ruta es AP-05 con otra cara: el día que se mueva, se entera
   uno.
3. **Que la sustitución no tocó el texto de las normas.** `vault_norms` cita
   `VAULT_ROOT` dentro de la propia descripción de AP-36 y de AP-49; una
   migración por texto se las habría comido y la norma seguiría en verde.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from vault.gobernanza.repositorio import RepositorioGobernanza  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _vault(raiz: Path) -> Path:
    for seccion in ("00_System", "02_Observability", "99_Index"):
        (raiz / seccion).mkdir(parents=True, exist_ok=True)
    return raiz


def _repo(raiz: Path) -> RepositorioGobernanza:
    return RepositorioGobernanza(construir(raiz))


# ── El criterio de aceptación ────────────────────────────────────────────────


def test_dos_vaults_resuelven_sus_rutas_en_el_mismo_proceso(tmp_path):
    a, b = _repo(_vault(tmp_path / "a")), _repo(_vault(tmp_path / "b"))

    assert a.registro_normas.is_relative_to(tmp_path / "a")
    assert b.registro_normas.is_relative_to(tmp_path / "b")
    assert a.indice_calidad != b.indice_calidad


def test_el_repositorio_no_deja_salir_del_vault(tmp_path):
    repo = _repo(_vault(tmp_path / "v"))
    with pytest.raises(ValueError, match="AP-36"):
        repo.ctx.ruta("..", "fuera.json")


def test_cambiar_el_vault_alcanza_al_registro_de_normas(tmp_path):
    import vault_io
    import vault_norms

    vault_io.set_vault_root(_vault(tmp_path / "nuevo"))
    assert vault_norms._norm_registry() == (
        tmp_path / "nuevo" / "00_System" / "norm-registry.json"
    ).resolve()


# ── AP-05: una ubicación, un sitio que la decide ─────────────────────────────


def test_el_indice_de_calidad_es_la_misma_ruta_en_los_dos_modulos_que_lo_escriben(
    tmp_path,
):
    import vault_audit
    import vault_io
    import vault_quality_check

    vault_io.set_vault_root(_vault(tmp_path / "v"))
    esperada = _repo(tmp_path / "v").indice_calidad

    assert vault_audit._quality_index() == esperada
    assert vault_quality_check._quality_index() == esperada


def test_la_bitacora_de_cambios_es_la_misma_ruta_en_los_dos_modulos_que_la_leen(
    tmp_path,
):
    import vault_fundamentals
    import vault_io
    import vault_quality_check

    vault_io.set_vault_root(_vault(tmp_path / "v"))
    esperada = _repo(tmp_path / "v").bitacora_cambios

    assert vault_fundamentals._change_log_json() == esperada
    assert vault_quality_check._change_log_json() == esperada


def test_las_vulnerabilidades_cuelgan_de_observabilidad(tmp_path):
    """Dos rutas derivadas de una: si se separan, el escaneo escribe el informe
    en un sitio y lo busca en otro."""
    repo = _repo(_vault(tmp_path / "v"))
    assert repo.dir_vulnerabilidades.is_relative_to(repo.dir_observabilidad)


# ── Lo que la migración no podía tocar ───────────────────────────────────────


def test_el_texto_de_las_normas_sigue_citando_vault_root():
    """La sustitución fue por AST, no por texto, justo por esto: AP-36 y AP-49
    describen el defecto nombrando `VAULT_ROOT`. Si un reemplazo ciego las
    reescribe, la norma queda ininteligible y ningún guard se entera."""
    import vault_norms

    textos = " ".join(
        str(v)
        for norma in vault_norms.NORM_CATALOG
        for v in norma.values()
        if isinstance(v, str)
    )
    assert "VAULT_ROOT" in textos
    assert "_raiz()" not in textos


def test_ningun_modulo_de_gobernanza_congela_la_raiz():
    """La medida de AP-49 restringida a este contexto: cero, y que se vea."""
    import vault_arch

    congelados = {v["module"] for v in vault_arch.vinculos_congelados()}
    del_contexto = set(vault_arch.CONTEXTS["gobernanza"]["modulos"])
    assert congelados & del_contexto == set()


# ── Lectura tolerante ────────────────────────────────────────────────────────


def test_un_fichero_ausente_y_uno_corrupto_se_leen_igual_de_vacios(tmp_path):
    repo = _repo(_vault(tmp_path / "v"))
    assert repo.leer_json(repo.indice_calidad) == {}
    repo.indice_calidad.write_text("{roto", encoding="utf-8")
    assert repo.leer_json(repo.indice_calidad) == {}
