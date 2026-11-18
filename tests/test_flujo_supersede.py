"""QA-FL-07 - superseding a decision in a frozen section says why, and names the mode.

Measured by the flow QA on a fresh vault (c09473ab): with
`{"secciones": ["03_Decisions"]}` in `00_System/inmutable.json`,
`vault_supersede --apply` failed with `WRITE_ERROR`, whose recovery is "check
permissions": the immutability refusal of the write owner, reported as a disk
problem. The guard is not relaxed (S4): full immutability freezes the section
by design, frontmatter included. The supported mode for decision sections is
`sustitucion` in `00_System/reglas.json`, where a closed body still cannot be
rewritten (AP-75) but the successor is written and linked with
`vault_supersede`, the flow the generated adapters prescribe.
"""

import json
import textwrap

import pytest

from apoyo import correr_en_proceso, correr_tool, escribir_nota

VIEJA = "03_Decisions/adr-001-uno.md"
ADR = """
    ## Contexto

    Las notas se pierden cuando dos agentes escriben a la vez sin lock.

    ## Decisión

    Vamos a serializar las escrituras con un lock por nota y timeout.

    ## Consecuencias

    Una escritura concurrente espera o falla con NOTE_LOCKED explícito.
"""
#: The body as a person writes it: what AP-07 and AP-11 accept.
TEXTO = textwrap.dedent(ADR).lstrip()
#: The same decision with one more sentence: a rewrite of the closed why.
REESCRITO = textwrap.dedent("""
    ## Contexto

    Las notas se pierden cuando dos agentes escriben a la vez sin lock.

    ## Decisión

    Vamos a serializar las escrituras con un lock por nota y timeout.

    ## Consecuencias

    Una escritura concurrente espera o falla con NOTE_LOCKED explícito.

    Una frase nueva que cambia el porqué.
""").lstrip()


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    for seccion in ("00_System", "03_Decisions", "99_Index"):
        (raiz / seccion).mkdir(parents=True)
    escribir_nota(raiz, VIEJA, {"title": "ADR-001 uno", "type": "decision",
                                "status": "approved", "responsable": "persona",
                                "tags": ["arch"]}, ADR)
    return raiz


def _politica(vault, fichero, datos):
    (vault / "00_System" / fichero).write_text(json.dumps(datos), encoding="utf-8")


def _sucesora(vault):
    corrida = correr_en_proceso(
        "vault_write", "--adr", "--folder", "03_Decisions", "--title", "dos",
        "--tags", "arch", "--content", TEXTO, vault=vault, agente="pytest")
    assert corrida.codigo == 0, corrida.stdout[-800:]
    return corrida.envelope["path"]


def test_inmutable_entera_responde_immutable_note_con_el_modo_soportado(vault):
    sucesora = _sucesora(vault)
    _politica(vault, "inmutable.json", {"secciones": ["03_Decisions"]})
    antes = (vault / VIEJA).read_bytes()

    corrida = correr_tool("vault_supersede", "--path", VIEJA, "--by", "adr-002-dos",
                          "--apply", vault=vault)

    env = corrida.envelope
    assert corrida.codigo == 1 and env["ok"] is False, env
    assert env["error_code"] == "IMMUTABLE_NOTE" and env["category"] == "governance", env
    assert env["path"] == VIEJA, env
    pista = env["recovery"]["hint"]
    assert "sustitucion" in pista and "00_System/reglas.json" in pista, env
    assert "00_System/inmutable.json" in pista, env
    assert (vault / VIEJA).read_bytes() == antes
    assert sucesora == "03_Decisions/adr-002-dos.md"


def test_siguiendo_la_pista_la_sucesora_queda_enlazada(vault):
    """The recovery followed literally: move the section to `sustitucion`, retry."""
    _sucesora(vault)
    _politica(vault, "inmutable.json", {"secciones": ["03_Decisions"]})
    primera = correr_en_proceso("vault_supersede", "--path", VIEJA, "--by", "adr-002-dos",
                                "--apply", vault=vault, agente="pytest")
    assert primera.envelope["error_code"] == "IMMUTABLE_NOTE", primera.envelope

    (vault / "00_System" / "inmutable.json").unlink()
    _politica(vault, "reglas.json", {"sustitucion": ["03_Decisions"]})
    corrida = correr_en_proceso("vault_supersede", "--path", VIEJA, "--by", "adr-002-dos",
                                "--apply", vault=vault, agente="pytest")

    env = corrida.envelope
    assert corrida.codigo == 0 and env["ok"] is True and env["written"] is True, env
    assert env["superseded_by"] == "[[adr-002-dos]]", env
    texto = (vault / VIEJA).read_text(encoding="utf-8")
    assert 'superseded_by: "[[adr-002-dos]]"' in texto
    assert "status: approved" in texto and "Vamos a serializar" in texto


def test_en_sustitucion_el_cuerpo_cerrado_sigue_sin_reescribirse(vault):
    """AP-75 holds: the mode that lets supersede write still refuses a body rewrite."""
    _politica(vault, "reglas.json", {"sustitucion": ["03_Decisions"]})
    antes = (vault / VIEJA).read_bytes()
    corrida = correr_en_proceso(
        "vault_write", "--folder", "03_Decisions", "--title", "ADR-001 uno", "--tags", "arch",
        "--content", REESCRITO,
        vault=vault, agente="pytest")
    assert corrida.codigo == 1 and corrida.envelope["error_code"] == "IMMUTABLE_NOTE"
    assert (vault / VIEJA).read_bytes() == antes


def test_sin_politica_supersede_anota_como_siempre(vault):
    _sucesora(vault)
    corrida = correr_en_proceso("vault_supersede", "--path", VIEJA, "--by", "adr-002-dos",
                                vault=vault, agente="pytest")
    env = corrida.envelope
    assert corrida.codigo == 0 and env["action"] == "check" and env["written"] is False, env
    corrida = correr_en_proceso("vault_supersede", "--path", VIEJA, "--by", "adr-002-dos",
                                "--apply", vault=vault, agente="pytest")
    assert corrida.codigo == 0 and corrida.envelope["written"] is True, corrida.envelope
