"""S4 (bigo-inmutabilidad): the context pack holds current truth only.

Until 2026-11-18 `vault_context_pack` penalized superseded, archived,
deprecated, obsolete and revoked notes (x0.2-x0.5) but let them compete: with
1 000 historic notes relevant to a query the rerank scored 45 candidates and
half the included items were history (`audits/rendimiento/banco_contexto.py`).
Now history leaves the candidates before scoring, a superseded note points to
its successor, the envelope counts what was left out, and
`--incluir-historico` is the pack from before.
"""

import re
from pathlib import Path

import pytest

from apoyo import correr_en_proceso, correr_tool, escribir_nota
from vault_base import copiar_vault

import vault_context_pack as pack

CONSULTA = "transporte del bus de eventos"
PRESUPUESTO = "4000"

VIGENTES = ["03_Decisions/adr-0100-transporte-bus-eventos.md",
            "07_Knowledge/transporte-bus-eventos-guia.md"]

#: path -> (reason the envelope must report, frontmatter)
HISTORICAS = {
    "03_Decisions/adr-0050-transporte-bus-eventos.md":
        ("superseded", {"status": "approved",
                        "superseded_by": "[[adr-0100-transporte-bus-eventos]]"}),
    "07_Knowledge/transporte-bus-eventos-archivada.md": ("archived", {"status": "archived"}),
    "05_Patterns/transporte-bus-eventos-deprecada.md": ("deprecated", {"status": "deprecated"}),
    "07_Knowledge/transporte-bus-eventos-obsoleta.md": ("obsolete", {"status": "obsolete"}),
    "07_Knowledge/transporte-bus-eventos-revocada.md": ("revoked", {"status": "revoked"}),
    "10_Migrated/fuentes/transporte-bus-eventos-fuente.md":
        ("archived_source", {"status": "archived", "type": "migrated"}),
    "20_Quarantine/transporte-bus-eventos-retenida.md": ("quarantine", {"status": "draft"}),
}


def _cuerpo(etiqueta: str) -> str:
    return (f"# Transporte del bus de eventos ({etiqueta})\n\n"
            f"El transporte del bus de eventos entrega eventos entre servicios ({etiqueta}).\n")


def _indexar(raiz: Path) -> Path:
    assert correr_tool("vault_reindex", vault=raiz).envelope["ok"] is True
    assert correr_tool("vault_graph", vault=raiz).returncode == 0
    return raiz


def _vault(tmp_path: Path, historia: bool = True) -> Path:
    raiz = copiar_vault(tmp_path / "vault")
    for rel in VIGENTES:
        escribir_nota(raiz, rel, {"title": f"Transporte del bus de eventos {Path(rel).stem}",
                                  "status": "approved", "updatedAt": "2026-11-01"},
                      _cuerpo(f"vigente {Path(rel).stem}"))
    if historia:
        for rel, (motivo, fm) in HISTORICAS.items():
            escribir_nota(raiz, rel, {"title": f"Transporte del bus de eventos {motivo}",
                                      **fm, "updatedAt": "2026-10-01"},
                          _cuerpo(motivo))
    return _indexar(raiz)


@pytest.fixture(scope="module")
def con_historia(tmp_path_factory) -> Path:
    return _vault(tmp_path_factory.mktemp("con_historia"))


@pytest.fixture(scope="module")
def sin_historia(tmp_path_factory) -> Path:
    return _vault(tmp_path_factory.mktemp("sin_historia"), historia=False)


def _pack(raiz: Path, *argv: str, consulta: str = CONSULTA):
    corrida = correr_en_proceso("vault_context_pack", "--query", consulta,
                                "--budget", PRESUPUESTO, "--explain", *argv, vault=raiz)
    assert corrida.codigo == 0 and corrida.envelope["ok"] is True, corrida.stdout
    return corrida


def _sin_reloj(corrida) -> str:
    """The stdout, byte for byte, except the envelope's wall-clock `timestamp`."""
    return re.sub(r'"timestamp": "[^"]*"', '"timestamp": ""', corrida.stdout)


def _incluidas(envelope) -> list:
    return [i["path"] for i in envelope["included"]]


def test_por_defecto_lo_historico_no_entra_ni_se_puntua(con_historia):
    env = _pack(con_historia).envelope

    assert sorted(_incluidas(env)) == sorted(VIGENTES)
    assert not set(_incluidas(env)) & set(HISTORICAS)
    # Left out before scoring: only the current notes are candidates.
    assert env["candidates_considered"] == len(VIGENTES)
    assert not {e["path"] for e in env["excluded"]} & set(HISTORICAS)
    assert not [p for p in HISTORICAS if p in env["context"]]


def test_el_envelope_cuenta_lo_que_dejo_fuera_por_motivo(con_historia):
    informe = _pack(con_historia).envelope["history_excluded"]

    esperado = {}
    for motivo, _ in HISTORICAS.values():
        esperado[motivo] = esperado.get(motivo, 0) + 1
    assert informe["total"] == len(HISTORICAS)
    assert informe["by_reason"] == esperado
    assert "--incluir-historico" in informe["hint"]


def test_la_sustituida_apunta_a_su_sucesora_vigente(con_historia):
    env = _pack(con_historia).envelope
    sustituida = "03_Decisions/adr-0050-transporte-bus-eventos.md"
    sucesora = "03_Decisions/adr-0100-transporte-bus-eventos.md"

    assert env["history_excluded"]["superseded_by"] == [{
        "path": sustituida,
        "superseded_by": "[[adr-0100-transporte-bus-eventos]]",
        "successor": sucesora,
    }]
    incluida = {i["path"]: i for i in env["included"]}[sucesora]
    assert incluida["supersedes"] == [sustituida]


def test_la_sucesora_entra_aunque_solo_la_sustituida_responda(tmp_path):
    """The successor answers what its predecessor answered, in other words."""
    raiz = copiar_vault(tmp_path / "vault")
    escribir_nota(raiz, "03_Decisions/adr-0001-cola-de-mensajes.md",
                  {"title": "Cola de mensajes", "status": "approved"},
                  "# Cola de mensajes\n\nSe adopta una cola persistente.\n")
    escribir_nota(raiz, "03_Decisions/adr-0000-ornitorrinco.md",
                  {"title": "Ornitorrinco cuántico", "status": "approved",
                   "superseded_by": "[[adr-0001-cola-de-mensajes]]"},
                  "# Ornitorrinco cuántico\n\nEl ornitorrinco cuántico era el transporte.\n")
    _indexar(raiz)

    env = _pack(raiz, consulta="ornitorrinco cuántico").envelope

    assert _incluidas(env) == ["03_Decisions/adr-0001-cola-de-mensajes.md"]
    assert env["included"][0]["supersedes"] == ["03_Decisions/adr-0000-ornitorrinco.md"]
    assert env["history_excluded"]["by_reason"] == {"superseded": 1}


def test_una_sucesora_rota_no_se_inventa(tmp_path):
    raiz = copiar_vault(tmp_path / "vault")
    escribir_nota(raiz, "03_Decisions/adr-0000-ornitorrinco.md",
                  {"title": "Ornitorrinco cuántico", "status": "approved",
                   "superseded_by": "[[no-existe]]"},
                  "# Ornitorrinco cuántico\n\nEl ornitorrinco cuántico era el transporte.\n")
    _indexar(raiz)

    env = _pack(raiz, consulta="ornitorrinco cuántico").envelope

    assert env["included"] == []
    assert env["history_excluded"]["superseded_by"] == [{
        "path": "03_Decisions/adr-0000-ornitorrinco.md",
        "superseded_by": "[[no-existe]]", "successor": None}]


def test_incluir_historico_devuelve_el_paquete_penalizado_de_antes(con_historia):
    env = _pack(con_historia, "--incluir-historico").envelope
    incluidas = {i["path"]: i for i in env["included"]}

    assert "history_excluded" not in env
    assert env["candidates_considered"] == len(VIGENTES) + len(HISTORICAS)
    assert set(HISTORICAS) & set(incluidas)
    for path in set(HISTORICAS) & set(incluidas):
        if not path.startswith("20_Quarantine/"):
            assert incluidas[path]["signals"]["status_penalty"] < 1.0
        assert "supersedes" not in incluidas[path]


def test_una_consulta_que_nombra_un_estado_historico_pide_historia(con_historia):
    """`deprecated` in the question is a request for history, not a filter target."""
    consulta = CONSULTA + " deprecated"
    por_defecto = _pack(con_historia, consulta=consulta)
    explicito = _pack(con_historia, "--incluir-historico", consulta=consulta)

    assert _sin_reloj(por_defecto) == _sin_reloj(explicito)
    assert "05_Patterns/transporte-bus-eventos-deprecada.md" in _incluidas(por_defecto.envelope)


@pytest.mark.parametrize("consulta", [CONSULTA, "guia del bus", "adr transporte eventos"])
def test_sin_historia_el_paquete_es_byte_a_byte_el_de_antes(sin_historia, consulta):
    por_defecto = _pack(sin_historia, consulta=consulta)
    de_antes = _pack(sin_historia, "--incluir-historico", consulta=consulta)

    assert _sin_reloj(por_defecto) == _sin_reloj(de_antes)
    assert "history_excluded" not in por_defecto.envelope


@pytest.mark.parametrize("presupuesto", ["400", "900"])
def test_el_presupuesto_se_respeta_sin_historia_en_el_paquete(con_historia, presupuesto):
    corrida = correr_en_proceso("vault_context_pack", "--query", CONSULTA,
                                "--budget", presupuesto, vault=con_historia)
    env = corrida.envelope

    assert corrida.codigo == 0 and env["ok"] is True
    assert env["tokens"]["used"] <= int(presupuesto)
    assert not set(_incluidas(env)) & set(HISTORICAS)
    assert env["history_excluded"]["total"] == len(HISTORICAS)


def test_la_cli_publica_la_opcion(con_historia):
    """The contract test by subprocess: the published script accepts the flag."""
    r = correr_tool("vault_context_pack", "--query", CONSULTA, "--budget", PRESUPUESTO,
                    "--incluir-historico", vault=con_historia)
    assert r.returncode == 0 and r.envelope["ok"] is True
    assert "history_excluded" not in r.envelope


@pytest.mark.parametrize("rel, frontmatter, esperado", [
    ("07_Knowledge/a.md", {"status": "approved"}, None),
    ("07_Knowledge/a.md", {}, None),
    ("07_Knowledge/a.md", {"status": "Deprecated"}, "deprecated"),
    ("07_Knowledge/a.md", {"status": "superseded"}, "superseded"),
    ("07_Knowledge/a.md", {"superseded_by": "[[b]]", "status": "approved"}, "superseded"),
    ("10_Migrated/fuentes/a.md", {"status": "archived", "type": "migrated"}, "archived_source"),
    ("10_Migrated/a.md", {"status": "archived", "type": "migrated"}, "archived"),
    ("20_Quarantine/a.md", {"status": "draft"}, "quarantine"),
])
def test_la_clasificacion_sale_de_sus_duenos(rel, frontmatter, esperado):
    assert pack.motivo_historico(rel, frontmatter) == esperado
