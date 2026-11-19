"""S4 (producto-usable): `vault_search` answers with current truth, like the context pack.

Until 2026-11-19 a search returned superseded ADRs, archived, deprecated,
obsolete and revoked notes, archived raw sources and quarantined copies mixed
with the current notes, unmarked: a third party asking "how do we transport
events" got the decision that was replaced next to the one that rules. The
context pack already left history out (512b037d); the search now applies the
same rule (one owner, `vault.kernel.vigencia`), says how many it left out and
why, and `--incluir-historico` is the search from before.

The rule reads the note's lifecycle from the search-index row, so searching
reads no note; an index built before the row carried it is answered by reading
only the matching notes, with a warning to reindex.
"""

import json
from pathlib import Path

from apoyo import correr_tool, escribir_nota
from vault_base import copiar_vault

from test_contexto_solo_vigente import HISTORICAS, VIGENTES, _cuerpo

CONSULTA = "transporte bus eventos"


def _vault(tmp_path: Path) -> Path:
    raiz = copiar_vault(tmp_path / "vault")
    for rel in VIGENTES:
        escribir_nota(raiz, rel, {"title": f"Transporte del bus de eventos {Path(rel).stem}",
                                  "status": "approved", "updatedAt": "2026-11-01"},
                      _cuerpo(f"vigente {Path(rel).stem}"))
    for rel, (_motivo, fm) in HISTORICAS.items():
        escribir_nota(raiz, rel, {"title": f"Transporte del bus de eventos {Path(rel).stem}",
                                  "updatedAt": "2026-11-01", **fm},
                      _cuerpo(f"historica {Path(rel).stem}"))
    assert correr_tool("vault_reindex", vault=raiz).envelope["ok"] is True
    return raiz


def _indice(raiz: Path) -> Path:
    """The search index path, from its owner (never derived here, AP-05)."""
    from vault.indices.repositorio import RepositorioIndices
    from vault.kernel import construir

    return RepositorioIndices(construir(raiz)).indice_busqueda


def _buscar(raiz: Path, *extra: str) -> dict:
    corrida = correr_tool("vault_search", "--query", CONSULTA, *extra, vault=raiz)
    assert corrida.envelope.get("ok") is True, corrida.stdout + corrida.stderr
    return corrida.envelope


def _rutas(env: dict) -> set:
    return {r["path"] for r in env["results"]}


def test_la_busqueda_devuelve_solo_lo_vigente_y_cuenta_lo_que_deja_fuera(tmp_path):
    env = _buscar(_vault(tmp_path))
    assert set(VIGENTES) <= _rutas(env), env["results"]
    assert not _rutas(env) & set(HISTORICAS), _rutas(env) & set(HISTORICAS)
    excluido = env["history_excluded"]
    assert excluido["total"] == len(HISTORICAS)
    esperado = {}
    for motivo, _fm in HISTORICAS.values():
        esperado[motivo] = esperado.get(motivo, 0) + 1
    assert excluido["by_reason"] == esperado
    assert "--incluir-historico" in excluido["hint"]
    assert env["matched"] == len(env["results"]) == len(VIGENTES)


def test_incluir_historico_es_la_busqueda_de_antes(tmp_path):
    env = _buscar(_vault(tmp_path), "--incluir-historico")
    assert set(VIGENTES) | set(HISTORICAS) <= _rutas(env)
    assert "history_excluded" not in env


def test_sin_historia_el_sobre_no_cambia_de_forma(tmp_path):
    raiz = copiar_vault(tmp_path / "vault")
    for rel in VIGENTES:
        escribir_nota(raiz, rel, {"title": f"Transporte del bus de eventos {Path(rel).stem}",
                                  "status": "approved"}, _cuerpo("vigente"))
    assert correr_tool("vault_reindex", vault=raiz).envelope["ok"] is True
    env = _buscar(raiz)
    assert "history_excluded" not in env and "warnings" not in env
    assert set(VIGENTES) <= _rutas(env)


def test_la_fila_del_indice_lleva_el_ciclo_de_vida(tmp_path):
    raiz = _vault(tmp_path)
    filas = {f["path"]: f for f in json.loads(
        _indice(raiz).read_text(encoding="utf-8"))["notes"]}
    adr = filas["03_Decisions/adr-0050-transporte-bus-eventos.md"]["lifecycle"]
    assert adr["superseded_by"] == "[[adr-0100-transporte-bus-eventos]]"
    assert adr["status_canonical"] == "approved"
    assert filas["07_Knowledge/transporte-bus-eventos-obsoleta.md"]["lifecycle"]["status_canonical"] == "obsolete"


def test_un_indice_previo_sin_ciclo_de_vida_se_responde_igual_y_pide_reindexar(tmp_path):
    raiz = _vault(tmp_path)
    indice = _indice(raiz)
    datos = json.loads(indice.read_text(encoding="utf-8"))
    for fila in datos["notes"]:
        fila.pop("lifecycle", None)
    indice.write_bytes(json.dumps(datos, ensure_ascii=False, indent=2).encode("utf-8"))
    env = _buscar(raiz)
    assert not _rutas(env) & set(HISTORICAS)
    assert env["history_excluded"]["total"] == len(HISTORICAS)
    assert any("vault_reindex" in w for w in env.get("warnings", [])), env.get("warnings")


def test_buscar_dentro_de_la_cuarentena_no_la_filtra(tmp_path):
    """Asking inside a historic section is asking for history."""
    env = _buscar(_vault(tmp_path), "--folder", "20_Quarantine")
    assert "20_Quarantine/transporte-bus-eventos-retenida.md" in _rutas(env)


def test_el_paquete_de_contexto_y_la_busqueda_comparten_la_regla():
    import vault_context_pack
    from vault.kernel import vigencia

    assert vault_context_pack.motivo_historico is vigencia.motivo_historico
    assert vault_context_pack.penalizacion is vigencia.penalizacion


def test_las_palabras_vacias_no_puntuan_por_subcadena(tmp_path):
    """Tutorial walk (2026-11-19): "cola de eventos" returned the one relevant
    note followed by 18 section indexes and primers, because each query word
    scored as a substring and "de" lives inside "decisions", "index", "code".
    Stopwords come from the owner the context pack already uses."""
    raiz = copiar_vault(tmp_path / "vault")
    escribir_nota(raiz, "07_Knowledge/cola-de-eventos-con-nats.md",
                  {"title": "Cola de eventos con NATS", "status": "approved", "tags": ["eventos"]},
                  "# Cola de eventos con NATS\n\nLos servicios publican eventos en NATS JetStream.\n")
    for seccion in ("03_Decisions", "11_Code", "08_Runbooks"):
        escribir_nota(raiz, f"{seccion}/sin-relacion.md",
                      {"title": f"Indice de {seccion} y decisiones de codigo", "status": "draft"},
                      "# Sin relacion\n\nNada que ver: decisiones de despliegue y codigo.\n")
    assert correr_tool("vault_reindex", vault=raiz).envelope["ok"] is True
    env = correr_tool("vault_search", "--query", "cola de eventos", vault=raiz).envelope
    assert [r["path"] for r in env["results"]] == ["07_Knowledge/cola-de-eventos-con-nats.md"], env["results"]


def test_una_consulta_solo_de_palabras_vacias_sigue_buscando(tmp_path):
    raiz = copiar_vault(tmp_path / "vault")
    escribir_nota(raiz, "07_Knowledge/el-de.md", {"title": "De la A a la Z", "status": "approved"},
                  "# De la A a la Z\n\nRecorrido completo.\n")
    assert correr_tool("vault_reindex", vault=raiz).envelope["ok"] is True
    env = correr_tool("vault_search", "--query", "de la", vault=raiz).envelope
    assert env["ok"] is True and "07_Knowledge/el-de.md" in [r["path"] for r in env["results"]]


def test_la_busqueda_y_el_parser_comparten_las_palabras_vacias():
    from vault.consulta import query_parse
    from vault.kernel import normalizacion

    assert query_parse.STOPWORDS is normalizacion.STOPWORDS
