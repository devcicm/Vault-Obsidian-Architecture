"""The change log is append-only: one more row costs the row, not the history.

bigo-inmutabilidad (S3, S6). Until this change every logged operation read the
whole `00_System/.change-log.json`, appended one entry and rewrote it — O(h) per
write, O(h^2) over the vault's life — and did the same with `change-log.md`.
Now new entries are appended to `00_System/.change-log.jsonl` (one JSON object
per line) and the Markdown table gets one more row; the legacy array is frozen:
read, legacy first, never written again. One owner reads both formats
(`RepositorioGobernanza.leer_bitacora_cambios`) and no consumer opens the files
itself.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from apoyo import ROOT, correr_en_proceso, correr_tool, lanzar_python

LEGACY = ".change-log.json"
LINES = ".change-log.jsonl"
MD = "change-log.md"


def _vault(tmp_path: Path) -> Path:
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    (raiz / "07_Knowledge").mkdir()
    return raiz


def _legacy_entries(n: int) -> list:
    return [{"id": f"00000000-0000-4000-8000-{i:012d}", "action": "created",
             "path": f"07_Knowledge/old-{i}.md", "new_path": None, "reason": f"old row {i}",
             "agent": "legacy", "timestamp": f"2026-01-01T00:00:{i % 60:02d}.000Z"}
            for i in range(n)]


def _seed_legacy(raiz: Path, entries: list) -> bytes:
    texto = json.dumps(entries, indent=2, ensure_ascii=False)
    (raiz / "00_System" / LEGACY).write_bytes(texto.encode("utf-8"))  # Python 3.9 floor
    return texto.encode("utf-8")


def _add(raiz: Path, path: str, reason: str, action: str = "created"):
    return correr_en_proceso("vault_change_log", "--action", action, "--path", path,
                             "--reason", reason, vault=raiz, agente="pytest")


def _query(raiz: Path, *extra: str) -> dict:
    return correr_en_proceso("vault_change_log", "--query", "--last", "1000", *extra,
                             vault=raiz).envelope


def _read(raiz: Path):
    from vault.gobernanza.repositorio import RepositorioGobernanza
    from vault.kernel import construir

    return RepositorioGobernanza(construir(raiz)).leer_bitacora_cambios()


# ── O(1): written bytes are never rewritten ─────────────────────────────────

def test_an_append_writes_one_line_and_never_rewrites_the_history(tmp_path):
    raiz = _vault(tmp_path)
    for i in range(3):
        assert _add(raiz, f"07_Knowledge/n{i}.md", f"row {i}").envelope["ok"]
    lines = raiz / "00_System" / LINES
    md = raiz / "00_System" / MD
    before_lines, before_md = lines.read_bytes(), md.read_bytes()

    r = _add(raiz, "07_Knowledge/n3.md", "row 3")

    assert r.codigo == 0 and r.envelope["ok"] is True
    assert r.envelope["written"] == 2
    assert r.envelope["log_json"] == f"00_System/{LINES}"
    after_lines, after_md = lines.read_bytes(), md.read_bytes()
    # The history is a byte prefix of the file: nothing already written moved.
    assert after_lines.startswith(before_lines) and after_md.startswith(before_md)
    nueva = after_lines[len(before_lines):]
    assert nueva.endswith(b"\n") and nueva.count(b"\n") == 1
    assert json.loads(nueva)["path"] == "07_Knowledge/n3.md"
    assert after_md[len(before_md):].count(b"\n") == 1
    # No legacy array is created by a vault that never had one.
    assert not (raiz / "00_System" / LEGACY).exists()
    assert after_md.decode("utf-8").count("| Timestamp |") == 1


def test_the_bytes_an_append_writes_do_not_grow_with_the_history(tmp_path):
    pequeno, grande = _vault(tmp_path / "a"), _vault(tmp_path / "b")
    _seed_legacy(grande, _legacy_entries(2000))
    for raiz in (pequeno, grande):
        assert _add(raiz, "07_Knowledge/first.md", "starts the line log").envelope["ok"]
    crecimientos = []
    for raiz in (pequeno, grande):
        lines = raiz / "00_System" / LINES
        antes = lines.stat().st_size
        assert _add(raiz, "07_Knowledge/same.md", "same row").envelope["ok"]
        crecimientos.append(lines.stat().st_size - antes)
    assert crecimientos[0] == crecimientos[1] > 0


# ── Legacy vaults: read unchanged, frozen, never migrated ──────────────────

def test_a_legacy_only_vault_reads_as_before(tmp_path):
    raiz = _vault(tmp_path)
    entries = _legacy_entries(5)
    _seed_legacy(raiz, entries)

    env = _query(raiz)

    assert env["ok"] is True and env["total"] == 5 and env["returned"] == 5
    assert sorted(e["id"] for e in env["entries"]) == sorted(e["id"] for e in entries)
    assert "torn_lines" not in env
    assert _read(raiz).entradas == entries


def test_the_first_append_starts_the_line_log_and_freezes_the_legacy_array(tmp_path):
    raiz = _vault(tmp_path)
    entries = _legacy_entries(4)
    legacy_bytes = _seed_legacy(raiz, entries)
    legacy = raiz / "00_System" / LEGACY
    mtime = legacy.stat().st_mtime_ns

    r = _add(raiz, "07_Knowledge/new.md", "first new row")

    assert r.codigo == 0 and r.envelope["ok"] is True
    assert legacy.read_bytes() == legacy_bytes and legacy.stat().st_mtime_ns == mtime
    lines = (raiz / "00_System" / LINES).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["path"] == "07_Knowledge/new.md"
    # Mixed order: the legacy entries first, then the appended ones.
    leidas = _read(raiz).entradas
    assert leidas[:4] == entries and leidas[4]["path"] == "07_Knowledge/new.md"
    env = _query(raiz)
    assert env["total"] == 5 and env["entries"][0]["path"] == "07_Knowledge/new.md"


def test_an_unreadable_legacy_array_still_blocks_the_first_append(tmp_path):
    raiz = _vault(tmp_path)
    roto = '[{"id": "a", "action": "created"'
    (raiz / "00_System" / LEGACY).write_text(roto, encoding="utf-8")

    env = _add(raiz, "07_Knowledge/x.md", "must not start a new log").envelope

    assert env["ok"] is False and env["error_code"] == "DATA_FILE_CORRUPT", env
    assert (raiz / "00_System" / LEGACY).read_text(encoding="utf-8") == roto
    assert not (raiz / "00_System" / LINES).exists()
    assert _query(raiz)["error_code"] == "DATA_FILE_CORRUPT"


# ── Crash safety: a torn last line ───────────────────────────────────────────

@pytest.mark.parametrize("cola", [b'{"id": "torn", "act', '{"reason": "café'.encode("utf-8")[:-1]],
                         ids=["json_cut", "utf8_cut"])
def test_a_torn_last_line_is_reported_not_merged_and_the_next_append_starts_a_line(tmp_path, cola):
    raiz = _vault(tmp_path)
    for i in range(2):
        assert _add(raiz, f"07_Knowledge/ok{i}.md", f"row {i}").envelope["ok"]
    lines = raiz / "00_System" / LINES
    with open(lines, "ab") as fh:
        fh.write(cola)  # a crash between the first byte and the newline

    env = _query(raiz)
    assert env["ok"] is True and env["total"] == 2
    assert env["torn_lines"] == [3] and env["torn_log"] == f"00_System/{LINES}"

    assert _add(raiz, "07_Knowledge/after.md", "after the crash").envelope["ok"]

    crudo = lines.read_bytes()
    assert crudo.split(b"\n")[2] == cola  # the torn bytes stay as they were
    env = _query(raiz)
    assert env["total"] == 3 and env["torn_lines"] == [3]
    assert env["entries"][0]["path"] == "07_Knowledge/after.md"
    assert json.loads(crudo.split(b"\n")[3])["path"] == "07_Knowledge/after.md"


def test_typographic_quotes_in_a_reason_keep_the_log_readable(tmp_path):
    """Sanitizing the serialized JSON folded `“` into a bare `"` and broke the log."""
    raiz = _vault(tmp_path)
    assert _add(raiz, "07_Knowledge/q.md", "cita “literal” — fin").envelope["ok"]
    assert _add(raiz, "07_Knowledge/r.md", "otra").envelope["ok"]

    env = _query(raiz)

    assert env["ok"] is True and env["total"] == 2
    assert {e["reason"] for e in env["entries"]} == {'cita "literal" -- fin', "otra"}


# ── Concurrency across processes ─────────────────────────────────────────────

def test_concurrent_processes_append_whole_lines(tmp_path):
    raiz = _vault(tmp_path)
    code = (
        "import sys\n"
        "from vault_change_log import vault_change_log_add\n"
        "for k in range(8):\n"
        "    r = vault_change_log_add(action='updated', path=f'07_Knowledge/p{sys.argv[1]}-{k}.md',\n"
        "                             reason='parallel', agent='pytest')\n"
        "    assert r['ok'], r\n"
    )
    procesos = [lanzar_python("-c", code, str(i), vault=raiz) for i in range(4)]
    assert [p.wait(timeout=300) for p in procesos] == [0, 0, 0, 0]

    lectura = _read(raiz)
    assert lectura.lineas_rotas == ()
    assert len(lectura.entradas) == 32
    assert {e["path"] for e in lectura.entradas} == {
        f"07_Knowledge/p{i}-{k}.md" for i in range(4) for k in range(8)}
    md = (raiz / "00_System" / MD).read_text(encoding="utf-8")
    assert md.count("| `updated` |") == 32 and md.count("| Timestamp |") == 1


# ── The CLI contract, by subprocess once ─────────────────────────────────────

def test_the_published_cli_appends_and_queries(tmp_path):
    raiz = _vault(tmp_path)
    _seed_legacy(raiz, _legacy_entries(2))
    r = correr_tool("vault_change_log", "--action", "deleted", "--path", "07_Knowledge/old-0.md",
                    "--reason", "logged before delete", vault=raiz)
    assert r.codigo == 0 and r.envelope["ok"] is True
    q = correr_tool("vault_change_log", "--query", "--action", "deleted", vault=raiz)
    assert q.codigo == 0 and q.envelope["total"] == 1
    assert q.envelope["entries"][0]["reason"] == "logged before delete"


# ── No consumer opens the log itself ─────────────────────────────────────────

#: The owner: the only module that opens the change-log files.
OWNER = "vault/gobernanza/repositorio.py"
#: Names that resolve to the change-log files outside the owner.
_ATTRS = {"bitacora_cambios", "bitacora_cambios_lineas"}
_FUNCS = {"_change_log_json", "_change_log", "_log_json", "_log_lines"}
_OPENERS = {"read_text", "read_bytes", "open"}


def _is_log(nodo: ast.AST, tainted: set) -> bool:
    for sub in ast.walk(nodo):
        if isinstance(sub, ast.Attribute) and sub.attr in _ATTRS:
            return True
        if isinstance(sub, ast.Call):
            fn = sub.func
            nombre = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
            if nombre in _FUNCS:
                return True
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and LEGACY in sub.value:
            return True
        if isinstance(sub, ast.Name) and sub.id in tainted:
            return True
    return False


def _log_openings(source: str) -> list:
    arbol = ast.parse(source)
    tainted: set = set()
    cambio = True
    while cambio:
        cambio = False
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Assign) and _is_log(nodo.value, tainted):
                for target in nodo.targets:
                    if isinstance(target, ast.Name) and target.id not in tainted:
                        tainted.add(target.id)
                        cambio = True
    hallazgos = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        fn = nodo.func
        if isinstance(fn, ast.Attribute) and fn.attr in _OPENERS and _is_log(fn.value, tainted):
            hallazgos.append(nodo.lineno)
        elif isinstance(fn, ast.Name) and fn.id == "open" and nodo.args and _is_log(nodo.args[0], tainted):
            hallazgos.append(nodo.lineno)
    return hallazgos


def test_the_static_check_sees_a_direct_read():
    assert _log_openings("p = repo.bitacora_cambios\ndata = p.read_text()\n") == [2]
    assert _log_openings("x = (root / '00_System' / '.change-log.json').read_text()\n") == [1]
    assert _log_openings("open(_change_log_json())\n") == [1]
    assert _log_openings("repo.leer_bitacora_cambios()\nrepo.bitacora_cambios.exists()\n") == []


def test_no_code_outside_the_owner_opens_the_change_log():
    fuentes = [*sorted((ROOT / "scripts").glob("*.py")), *sorted((ROOT / "vault").rglob("*.py"))]
    hallazgos = {}
    for fuente in fuentes:
        relativa = fuente.relative_to(ROOT).as_posix()
        if relativa == OWNER:
            continue
        lineas = _log_openings(fuente.read_text(encoding="utf-8"))
        if lineas:
            hallazgos[relativa] = lineas
    assert hallazgos == {}
    servidor = (ROOT / "mcp" / "nodejs" / "vault-mcp-server.mjs").read_text(encoding="utf-8")
    assert LEGACY not in servidor  # the MCP server reads the log through the tools


_SALTOS = ("primera linea" + chr(10) + "segunda linea",
           "con crlf" + chr(13) + chr(10) + "fin",
           "con cr" + chr(13) + "fin")


@pytest.mark.parametrize("motivo", _SALTOS)
def test_un_motivo_de_varias_lineas_deja_una_sola_entrada_completa(tmp_path, motivo):
    """Verifier blocker (2026-11-18): a reason with a line break made the
    Markdown append raise AFTER the JSON row was written, so the entry was
    half-written, every retry appended another row and the envelope crashed.
    Base accepted it. The Markdown cell keeps the break as `<br>`."""
    raiz = _vault(tmp_path)
    r = correr_tool("vault_change_log", "--action", "updated", "--path",
                    "07_Knowledge/n.md", "--reason", motivo, vault=raiz)
    assert r.codigo == 0 and r.envelope.get("ok") is True, r.stdout + r.stderr
    filas = [l for l in (raiz / "00_System" / ".change-log.jsonl").read_text(encoding="utf-8").splitlines() if l]
    # The text sanitizer already normalizes line endings (CRLF and CR -> LF).
    normalizado = motivo.replace(chr(13) + chr(10), chr(10)).replace(chr(13), chr(10))
    assert len(filas) == 1 and json.loads(filas[0])["reason"] in (motivo, normalizado), filas
    md = (raiz / "00_System" / "change-log.md").read_text(encoding="utf-8")
    assert md.count("| `updated` |") == 1 and "<br>" in md, md


def test_un_borrado_con_motivo_de_varias_lineas_borra_y_registra_una_vez(tmp_path):
    raiz = _vault(tmp_path)
    nota = raiz / "07_Knowledge" / "n.md"
    nota.write_bytes(b"---\ntitle: n\nstatus: draft\ntype: knowledge\n---\n# n\n\nUno.\nDos.\nTres.\n")
    # An existing Markdown log takes the O(1) append path, the one that failed.
    previa = correr_tool("vault_change_log", "--action", "created", "--path",
                         "07_Knowledge/n.md", "--reason", "alta", vault=raiz)
    assert previa.envelope.get("ok") is True, previa.stdout + previa.stderr
    r = correr_tool("vault_delete", "--path", "07_Knowledge/n.md", "--reason", _SALTOS[0], vault=raiz)
    assert r.codigo == 0 and r.envelope.get("ok") is True, r.stdout + r.stderr
    assert not nota.exists()
    filas = [l for l in (raiz / "00_System" / ".change-log.jsonl").read_text(encoding="utf-8").splitlines() if l]
    assert [json.loads(f)["action"] for f in filas] == ["created", "deleted"]
