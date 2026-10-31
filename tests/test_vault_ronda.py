"""D-07 — la ronda de trabajo la abre el agente y sus notas la llevan.

`vault_ronda --abrir` deja `00_System/ronda-activa.json`; mientras existe,
`vault_write` estampa su `round_id` en cada nota, y `--cerrar` escribe la nota
de sesión en `04_Sessions/` con las que lo llevan. Se mide por la CLI, que es
por donde llega el agente vía MCP, y el frontmatter con `yaml.safe_load`
(AP-44: el criterio del consumidor).
"""
import re

import pytest
import yaml

from apoyo import correr_tool
from vault_base import copiar_vault

from vault.autoria.ronda import es_round_id, nuevo_round_id
from vault.kernel.contrato_nota import CAMPOS

CUERPO = "Una linea.\nOtra linea.\nY una tercera con palabras de sobra."


@pytest.fixture
def vault(tmp_path):
    return copiar_vault(tmp_path / "vault")


def _frontmatter(ruta):
    texto = ruta.read_text(encoding="utf-8")
    return yaml.safe_load(texto.split("---", 2)[1])


def _abrir(vault):
    corrida = correr_tool("vault_ronda", "--abrir", "--agente", "claude",
                          "--objetivo", "probar la ronda", vault=vault)
    assert corrida.codigo == 0, corrida.stdout[-800:] + corrida.stderr[-800:]
    return corrida.envelope["round"]["round_id"]


def _escribir(vault, titulo):
    corrida = correr_tool("vault_write", "--folder", "07_Knowledge", "--title", titulo,
                          "--content", CUERPO, "--tags", "ronda-prueba",
                          "--agent", "claude", vault=vault)
    assert corrida.codigo == 0, corrida.stdout[-800:] + corrida.stderr[-800:]
    return vault / corrida.envelope["path"]


def test_el_contrato_declara_round_id_con_el_patron_del_identificador():
    campo = CAMPOS["round_id"]
    assert campo["nivel"] == "opcional"
    assert re.match(campo["patron"], nuevo_round_id())
    assert not es_round_id("r2026-abc") and not es_round_id(None)


def test_una_ronda_abierta_se_estampa_y_se_cierra_en_su_nota_de_sesion(vault):
    round_id = _abrir(vault)
    assert es_round_id(round_id)
    assert (vault / "00_System" / "ronda-activa.json").is_file()

    nota = _escribir(vault, "Nota de la ronda")
    assert _frontmatter(nota)["round_id"] == round_id

    cierre = correr_tool("vault_ronda", "--cerrar", "--resumen", "una nota escrita", vault=vault)
    assert cierre.codigo == 0, cierre.stdout[-800:] + cierre.stderr[-800:]
    envelope = cierre.envelope
    assert envelope["closed"] is True
    assert nota.relative_to(vault).as_posix() in envelope["notes"]

    sesion = vault / envelope["session_note"]
    assert sesion.parent.name == "04_Sessions"
    assert _frontmatter(sesion)["round_id"] == round_id
    assert "una nota escrita" in sesion.read_text(encoding="utf-8")
    assert not (vault / "00_System" / "ronda-activa.json").exists()

    activa = correr_tool("vault_ronda", "--activa", vault=vault).envelope
    assert activa["ok"] and activa["active"] is False


def test_sin_ronda_abierta_vault_write_no_estampa(vault):
    assert "round_id" not in _frontmatter(_escribir(vault, "Nota sin ronda"))


def test_una_segunda_ronda_no_pisa_a_la_abierta(vault):
    round_id = _abrir(vault)
    otra = correr_tool("vault_ronda", "--abrir", "--agente", "otro",
                       "--objetivo", "pisarla", vault=vault)
    assert otra.codigo == 1
    assert otra.envelope["error_code"] == "ROUND_ALREADY_ACTIVE"
    assert otra.envelope["round"]["round_id"] == round_id


def test_cerrar_sin_ronda_lo_dice(vault):
    corrida = correr_tool("vault_ronda", "--cerrar", "--resumen", "nada", vault=vault)
    assert corrida.codigo == 1
    assert corrida.envelope["error_code"] == "ROUND_NOT_ACTIVE"


def test_abrir_sin_objetivo_se_rechaza(vault):
    corrida = correr_tool("vault_ronda", "--abrir", "--agente", "claude", vault=vault)
    assert corrida.envelope["error_code"] == "MISSING_REQUIRED_ARG"
    assert not (vault / "00_System" / "ronda-activa.json").exists()


def test_un_estado_ilegible_no_se_lee_como_sin_ronda(vault):
    """AP-51: leerlo como «no hay ronda» escribiría notas sin su round_id."""
    (vault / "00_System" / "ronda-activa.json").write_text('{"round_id": "x"}', encoding="utf-8")
    for corrida in (correr_tool("vault_ronda", "--activa", vault=vault),
                    correr_tool("vault_write", "--folder", "07_Knowledge", "--title", "Nota",
                                "--content", CUERPO, "--tags", "ronda-prueba",
                                "--agent", "claude", vault=vault)):
        assert corrida.codigo == 1
        assert corrida.envelope["error_code"] == "DATA_FILE_CORRUPT"


def test_meta_con_un_round_id_mal_formado_se_rechaza(vault):
    corrida = correr_tool("vault_write", "--folder", "07_Knowledge", "--title", "Nota",
                          "--content", CUERPO, "--tags", "ronda-prueba", "--agent", "claude",
                          "--meta", '{"round_id": "ronda-1"}', vault=vault)
    assert corrida.codigo == 1
    assert "round_id" in corrida.envelope["message"]
