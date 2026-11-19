"""ISO/IEC/IEEE 42010: an ADR declares the concerns it addresses and its viewpoint.

- The registry (`vault.kernel.contenido`): concerns and viewpoints, where a
  viewpoint frames concerns.
- `vault_write --adr` accepts `concerns:`/`viewpoint:` through `--meta` and
  refuses a value outside the registry; an ADR that does not declare them is
  written as before.
- `vault_arquitectura_en --intereses` publishes the work list: ADRs without
  concerns, concerns no ADR addresses, viewpoints used.
"""

import pytest

from apoyo import correr_en_proceso, escribir_nota

import vault_io
from vault_lib import parse_frontmatter
from vault.kernel.contenido import (
    INTERESES_DE_ARQUITECTURA,
    PUNTOS_DE_VISTA,
    plantilla_adr,
    secciones_adr_faltantes,
)


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    for seccion in ("00_System", "03_Decisions", "07_Knowledge"):
        (raiz / seccion).mkdir(parents=True)
    previa = vault_io.set_vault_root(raiz)
    yield raiz
    vault_io.set_vault_root(previa)


ADR_COMPLETO = (
    "## Contexto\n\nLas notas se pierden cuando dos agentes escriben a la vez sin lock.\n\n"
    "## Decisión\n\nVamos a serializar las escrituras con un lock por nota y timeout.\n\n"
    "## Consecuencias\n\nUna escritura concurrente espera o falla con NOTE_LOCKED explícito.\n"
)


def _escribir_adr(vault, *meta):
    args = ["--adr", "--folder", "03_Decisions", "--title", "Serializar escrituras",
            "--content", ADR_COMPLETO, "--tags", "arquitectura", "--agent", "pytest"]
    if meta:
        args += ["--meta", meta[0]]
    return correr_en_proceso("vault_write", *args, vault=vault)


# ── Registry ────────────────────────────────────────────────────────────────

def test_every_concern_is_framed_by_some_viewpoint_and_only_known_ones():
    enmarcados = {i for v in PUNTOS_DE_VISTA.values() for i in v["enmarca"]}
    assert enmarcados <= set(INTERESES_DE_ARQUITECTURA)
    assert set(INTERESES_DE_ARQUITECTURA) <= enmarcados
    for nombre, punto in PUNTOS_DE_VISTA.items():
        assert punto["que"].strip() and punto["enmarca"], nombre


# ── Write path ──────────────────────────────────────────────────────────────

def test_adr_declares_known_concerns_and_viewpoint(vault):
    corrida = _escribir_adr(vault, '{"concerns": ["seguridad", "datos"], "viewpoint": "datos"}')

    env = corrida.envelope
    assert corrida.codigo == 0 and env["ok"], env
    nota = vault / "03_Decisions" / "adr-001-serializar-escrituras.md"
    fm = parse_frontmatter(nota.read_text(encoding="utf-8"))
    assert fm["concerns"] == ["seguridad", "datos"]
    assert fm["viewpoint"] == "datos"
    assert fm["status"] == "draft"


def test_adr_with_an_unknown_concern_is_refused_and_nothing_is_written(vault):
    corrida = _escribir_adr(vault, '{"concerns": ["seguridad", "velocidad"]}')

    env = corrida.envelope
    assert corrida.codigo == 1 and env["ok"] is False
    assert env["error_code"] == "INVALID_INPUT"
    assert "velocidad" in env["message"] and "42010" in env["message"]
    assert "mantenibilidad" in env["message"]
    assert not list((vault / "03_Decisions").glob("*.md"))


def test_adr_with_an_unknown_viewpoint_or_a_non_list_is_refused(vault):
    corrida = _escribir_adr(vault, '{"viewpoint": "fisico", "concerns": "seguridad"}')

    env = corrida.envelope
    assert corrida.codigo == 1 and env["error_code"] == "INVALID_INPUT"
    assert "'fisico'" in env["message"] and "lista de textos" in env["message"]
    assert not list((vault / "03_Decisions").glob("*.md"))


def test_a_plain_write_into_decisions_is_validated_too(vault):
    corrida = correr_en_proceso(
        "vault_write", "--folder", "03_Decisions", "--title", "Decision suelta",
        "--content", ADR_COMPLETO, "--tags", "arquitectura", "--agent", "pytest",
        "--meta", '{"viewpoint": "fisico"}', vault=vault)

    assert corrida.codigo == 1 and corrida.envelope["error_code"] == "INVALID_INPUT"
    assert not list((vault / "03_Decisions").glob("*.md"))


def test_adr_without_concerns_is_written_as_before(vault):
    """Previous behavior: the fields are optional and nothing adds them."""
    corrida = _escribir_adr(vault)

    assert corrida.codigo == 0 and corrida.envelope["ok"], corrida.envelope
    fm = parse_frontmatter(
        (vault / "03_Decisions" / "adr-001-serializar-escrituras.md").read_text(encoding="utf-8"))
    assert "concerns" not in fm and "viewpoint" not in fm


def test_concerns_outside_decisions_stay_an_open_property(vault):
    """Previous behavior: `--meta` keys are open outside the decisions section."""
    corrida = correr_en_proceso(
        "vault_write", "--folder", "07_Knowledge", "--title", "Nota con concerns propios",
        "--content", ADR_COMPLETO, "--tags", "x", "--agent", "pytest",
        "--meta", '{"concerns": ["lo que sea"]}', vault=vault)

    assert corrida.codigo == 0 and corrida.envelope["ok"], corrida.envelope


def test_the_adr_hint_names_the_optional_fields_and_keeps_the_template(vault):
    corrida = correr_en_proceso(
        "vault_write", "--adr", "--folder", "03_Decisions", "--title", "Sin secciones",
        "--content", "Linea uno con bastante texto real aqui.\nLinea dos con mas texto real.\n"
                     "Linea tres que completa el minimo de palabras.\n",
        "--tags", "arquitectura", "--agent", "pytest", vault=vault)

    pista = corrida.envelope["recovery"]["hint"]
    assert corrida.envelope["error_code"] == "VALIDATION_FAILED"
    assert plantilla_adr().strip() in pista
    assert "concerns" in pista and "viewpoint" in pista and "42010" in pista
    # The body template is still the one AP-07 measures: no frontmatter in it.
    assert secciones_adr_faltantes(plantilla_adr()) == []
    assert "concerns" not in plantilla_adr()


# ── Report ──────────────────────────────────────────────────────────────────

def _adr(vault, nombre, **campos):
    fm = {"type": "adr", "title": nombre, "status": "approved",
          "createdAt": "2026-01-01T00:00:00Z", **campos}
    escribir_nota(vault, f"03_Decisions/{nombre}.md", fm, ADR_COMPLETO)


def test_intereses_lists_adrs_without_concerns_and_unanswered_concerns(vault):
    _adr(vault, "adr-001-datos", concerns=["seguridad", "datos"], viewpoint="datos")
    _adr(vault, "adr-002-sin-intereses")
    _adr(vault, "adr-003-retirada", status="deprecated")
    _adr(vault, "adr-004-fuera-del-punto", concerns=["rendimiento"], viewpoint="seguridad")
    _adr(vault, "adr-005-a-mano", concerns=["velocidad"], viewpoint="fisico")
    escribir_nota(vault, "07_Knowledge/no-es-adr.md", {"type": "concept", "title": "x"}, "x\n")

    corrida = correr_en_proceso("vault_arquitectura_en", "--intereses", vault=vault)

    env = corrida.envelope
    assert corrida.codigo == 0 and env["ok"] is True and env["modo"] == "intereses"
    assert env["norma"] == "ISO/IEC/IEEE 42010:2022"
    assert env["adrs"] == 4
    assert env["adrs_sin_intereses"] == ["03_Decisions/adr-002-sin-intereses.md",
                                         "03_Decisions/adr-005-a-mano.md"]
    assert env["intereses_sin_adr"] == [
        i for i in INTERESES_DE_ARQUITECTURA if i not in ("seguridad", "datos", "rendimiento")]
    assert env["intereses_atendidos"]["rendimiento"] == ["03_Decisions/adr-004-fuera-del-punto.md"]
    assert env["puntos_de_vista_usados"] == {
        "datos": ["03_Decisions/adr-001-datos.md"],
        "seguridad": ["03_Decisions/adr-004-fuera-del-punto.md"]}
    assert env["adrs_sin_punto_de_vista"] == ["03_Decisions/adr-002-sin-intereses.md",
                                              "03_Decisions/adr-005-a-mano.md"]
    assert env["fuera_del_punto_de_vista"] == [{
        "path": "03_Decisions/adr-004-fuera-del-punto.md", "viewpoint": "seguridad",
        "intereses": ["rendimiento"]}]
    assert [f["path"] for f in env["fuera_de_vocabulario"]] == ["03_Decisions/adr-005-a-mano.md"]
    assert set(env["registro"]["puntos_de_vista"]) == set(PUNTOS_DE_VISTA)
    # Read only: the report wrote no note.
    assert sorted(p.name for p in (vault / "03_Decisions").glob("*.md")) == [
        "adr-001-datos.md", "adr-002-sin-intereses.md", "adr-003-retirada.md",
        "adr-004-fuera-del-punto.md", "adr-005-a-mano.md"]


def test_intereses_does_not_combine_with_a_point_in_time(vault):
    corrida = correr_en_proceso("vault_arquitectura_en", "--intereses", "--fecha", "2026-05-03",
                                vault=vault)

    assert corrida.codigo == 1
    assert corrida.envelope["error_code"] == "CONFLICTING_ARGS"


def test_the_point_in_time_mode_is_unchanged(vault):
    """Previous behavior: `--fecha` still answers the snapshot, without the new report."""
    _adr(vault, "adr-001-datos", concerns=["seguridad"], viewpoint="datos")

    corrida = correr_en_proceso("vault_arquitectura_en", "--fecha", "2026-05-03", vault=vault)

    env = corrida.envelope
    assert corrida.codigo == 0 and env["modo"] == "punto"
    assert [v["path"] for v in env["vigentes"]] == ["03_Decisions/adr-001-datos.md"]
    assert "adrs_sin_intereses" not in env
