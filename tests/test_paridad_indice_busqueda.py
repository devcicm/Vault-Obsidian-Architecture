"""QG-05: the CLI/MCP parity measures the search index by meaning, not by clock.

Since the search index proves its freshness with content hashes (af5884b1),
every row of `99_Index/search-index.json` carries `content_hash`: the sha256 of
the note's raw bytes. Those bytes include the note's createdAt/updatedAt (and
the generated `index.md`, the change log...), so the same `vault_write` run
through the CLI and, seconds later, through the MCP server publishes different
hashes for identical content. Masking the timestamps in the TEXT of the index
cannot reach a hash computed over them: `paridad_cli_mcp.py` reported
NO CONFORME on 045d3142 with every other file identical.

The measurement now replaces a `content_hash` by a fixed token only when it is
proven equal to the sha256 of its note in the measured runtime. A hash that
does not match its note keeps its raw value, so a stale or wrong row still
diverges.

The MCP column must also run the measured wheel: without `VAULT_MCP_PYTHON`
the server's Python children run the first interpreter of the PATH, whose
`vault` package may be another checkout.
"""
import hashlib
import json
from pathlib import Path

from apoyo import correr_tool, escribir_nota
from test_fase2_paridad_fail_closed import verificador

INDICE = "99_Index/search-index.json"
NOTA = "07_Knowledge/nota-de-paridad.md"


def _vault_indexado(raiz: Path, marca: str, cuerpo: str = "Cuerpo identico.\n") -> Path:
    """A vault with one note written at `marca`, indexed by the product owner.

    `marca` uses the `+00:00` form `vault_write` emits: the generated
    `index.md` renders it and its BM25 terms keep only tokens of three or more
    characters, so the seconds never become a term (a `Z` suffix would).
    """
    escribir_nota(raiz, NOTA, {"title": "Nota de paridad", "type": "knowledge",
                              "createdAt": marca, "updatedAt": marca,
                              "tags": ["paridad"]}, cuerpo)
    corrida = correr_tool("vault_reindex", vault=raiz)
    assert corrida.returncode == 0, corrida.stderr
    assert corrida.envelope["ok"] is True
    assert (raiz / INDICE).is_file()
    return raiz


def _fila(raiz: Path, relativa: str = NOTA) -> dict:
    datos = json.loads((raiz / INDICE).read_text(encoding="utf-8"))
    return next(n for n in datos["notes"] if n["path"] == relativa)


def _reescribir_indice(raiz: Path, cambio) -> None:
    ruta = raiz / INDICE
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    for fila in datos["notes"]:
        if fila["path"] == NOTA:
            cambio(fila)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def test_the_same_note_written_at_two_instants_leaves_the_same_index_fingerprint(tmp_path):
    cli = _vault_indexado(tmp_path / "cli", "2026-11-18T19:11:12+00:00")
    mcp = _vault_indexado(tmp_path / "mcp", "2026-11-18T19:11:19+00:00")
    # Precondition: the raw hashes differ only because of the clock.
    assert _fila(cli)["content_hash"] != _fila(mcp)["content_hash"]
    huellas_cli = verificador._huellas(cli)
    huellas_mcp = verificador._huellas(mcp)
    assert huellas_cli[NOTA] == huellas_mcp[NOTA]
    assert huellas_cli[INDICE] == huellas_mcp[INDICE]
    # The same files exist on both sides (the full reindex also writes
    # hash-index.json, which `vault_write` never touches and parity never sees
    # change: it is out of this measurement).
    assert set(huellas_cli) == set(huellas_mcp)


def test_a_row_whose_hash_does_not_match_its_note_still_diverges(tmp_path):
    cli = _vault_indexado(tmp_path / "cli", "2026-11-18T19:11:12+00:00")
    mcp = _vault_indexado(tmp_path / "mcp", "2026-11-18T19:11:19+00:00")
    _reescribir_indice(mcp, lambda fila: fila.update(content_hash="0" * 64))
    huellas_cli = verificador._huellas(cli)
    huellas_mcp = verificador._huellas(mcp)
    assert huellas_cli[NOTA] == huellas_mcp[NOTA]
    assert huellas_cli[INDICE] != huellas_mcp[INDICE]


def test_a_stale_row_after_a_note_change_still_diverges(tmp_path):
    cli = _vault_indexado(tmp_path / "cli", "2026-11-18T19:11:12+00:00")
    mcp = _vault_indexado(tmp_path / "mcp", "2026-11-18T19:11:19+00:00")
    # Both notes change the same way; only the CLI side refreshes its index.
    for raiz in (cli, mcp):
        escribir_nota(raiz, NOTA, {"title": "Nota de paridad", "type": "knowledge",
                                  "createdAt": "2026-11-18T19:12:00+00:00",
                                  "updatedAt": "2026-11-18T19:12:00+00:00",
                                  "tags": ["paridad"]}, "Cuerpo cambiado.\n")
    correr_tool("vault_reindex", vault=cli)
    huellas_cli = verificador._huellas(cli)
    huellas_mcp = verificador._huellas(mcp)
    assert huellas_cli[NOTA] == huellas_mcp[NOTA]
    assert huellas_cli[INDICE] != huellas_mcp[INDICE]


def test_other_index_fields_are_still_compared(tmp_path):
    cli = _vault_indexado(tmp_path / "cli", "2026-11-18T19:11:12+00:00")
    mcp = _vault_indexado(tmp_path / "mcp", "2026-11-18T19:11:19+00:00")
    _reescribir_indice(mcp, lambda fila: fila.update(title="Otro titulo"))
    assert verificador._huellas(cli)[INDICE] != verificador._huellas(mcp)[INDICE]


def test_a_row_pointing_outside_the_runtime_is_not_verified(tmp_path):
    fuera = tmp_path / "fuera.md"
    fuera.write_bytes(b"outside\n")
    huella = hashlib.sha256(b"outside\n").hexdigest()
    raiz = tmp_path / "vault"
    (raiz / "99_Index").mkdir(parents=True)
    (raiz / INDICE).write_text(json.dumps(
        {"notes": [{"path": "../fuera.md", "content_hash": huella}]}), encoding="utf-8")
    texto = (raiz / INDICE).read_text(encoding="utf-8")
    resultado = json.loads(verificador._verificar_huellas_del_indice(texto, raiz))
    assert resultado["notes"][0]["content_hash"] == huella


def test_previous_behavior_timestamps_masked_and_unparseable_index_kept(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for raiz, marca in ((a, "2026-11-18T19:11:12+00:00"), (b, "2026-11-18T19:11:19+00:00")):
        escribir_nota(raiz, NOTA, {"title": "N", "createdAt": marca, "updatedAt": marca},
                      "Cuerpo.\n")
        (raiz / "99_Index").mkdir(parents=True)
        (raiz / INDICE).write_text("{not json " + marca, encoding="utf-8")
    assert verificador._huellas(a) == verificador._huellas(b)
    (b / INDICE).write_text("{not json at all", encoding="utf-8")
    assert verificador._huellas(a)[INDICE] != verificador._huellas(b)[INDICE]


def test_mcp_children_are_pinned_to_the_measured_venv_interpreter(tmp_path):
    python = tmp_path / "venv" / "Scripts" / "python.exe"
    env = {"VAULT_ROOT": "x", "VAULT_AGENT": "paridad-fase2"}
    pinned = verificador.mcp_env(env, python)
    assert pinned == {**env, "VAULT_MCP_PYTHON": str(python)}
    assert "VAULT_MCP_PYTHON" not in env
