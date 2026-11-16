"""Search index content freshness must not require writes during checks."""

import json
import pytest

from vault.indices.coherencia import coherencia_indice
from vault.indices.reconstruccion import ServicioReindex
from vault.indices.repositorio import RepositorioIndices
from vault.kernel import construir


def _setup(tmp_path):
    root = tmp_path / "vault"
    (root / "07_Knowledge").mkdir(parents=True)
    (root / "99_Index").mkdir()
    note = root / "07_Knowledge" / "note.md"
    note.write_text("original", encoding="utf-8")
    repo = RepositorioIndices(construir(root))
    service = ServicioReindex(repo, lambda _: {})
    service.reconstruir()
    return repo, service, note


def test_same_path_content_change_is_stale(tmp_path):
    repo, _, note = _setup(tmp_path)
    note.write_text("modified", encoding="utf-8")
    assert coherencia_indice(repo)["status"] == "index_stale"


def test_newline_only_change_is_stale(tmp_path):
    repo, service, note = _setup(tmp_path)
    note.write_bytes(b"one\r\ntwo\r\n")
    service.reconstruir()
    note.write_bytes(b"one\ntwo\n")
    assert coherencia_indice(repo)["status"] == "index_stale"


def test_old_index_is_unverified_without_rewriting(tmp_path):
    repo, _, _ = _setup(tmp_path)
    data = json.loads(repo.indice_busqueda.read_text(encoding="utf-8"))
    for row in data["notes"]:
        row.pop("content_hash", None)
    repo.indice_busqueda.write_text(json.dumps(data), encoding="utf-8")
    before = repo.indice_busqueda.read_bytes()
    assert coherencia_indice(repo)["status"] == "index_unverified"
    assert repo.indice_busqueda.read_bytes() == before


def test_incremental_refresh_restores_content_coherence(tmp_path):
    repo, service, note = _setup(tmp_path)
    note.write_text("modified", encoding="utf-8")
    service.refrescar(note)
    row = json.loads(repo.indice_busqueda.read_text(encoding="utf-8"))["notes"][0]
    assert len(row["content_hash"]) == 64
    assert coherencia_indice(repo)["status"] == "index_ok"


def test_unreadable_note_is_incomplete_and_does_not_disclose_paths(tmp_path, monkeypatch):
    repo, _, note = _setup(tmp_path)
    original = type(note).read_bytes

    def fail(path, *args, **kwargs):
        if path == note:
            raise PermissionError("private path")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(type(note), "read_bytes", fail)
    result = coherencia_indice(repo)
    assert result["status"] == "index_incomplete"
    assert "private path" not in str(result)


def test_context_receives_independent_read_port(tmp_path):
    from vault.kernel.productores import buscar, registrar, restaurar
    name = "coherencia_indices"
    previous = buscar(name)
    provider = object()
    try:
        registrar(name, provider)
        assert construir(tmp_path).coherencia_indices is provider
    finally:
        restaurar(name, previous)


def test_note_changed_during_read_is_incomplete(tmp_path, monkeypatch):
    repo, _, note = _setup(tmp_path)
    original = type(note).read_bytes

    def changed(path, *args, **kwargs):
        result = original(path, *args, **kwargs)
        if path == note:
            path.write_text("changed while checking", encoding="utf-8")
        return result

    monkeypatch.setattr(type(note), "read_bytes", changed)
    assert coherencia_indice(repo)["status"] == "index_incomplete"


def test_provider_load_failure_does_not_write_trace(tmp_path, monkeypatch):
    from vault import runtime
    from vault.kernel import productores
    import importlib

    name = "coherencia_indices"
    previous = productores.buscar(name)
    productores.restaurar(name, None)
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    monkeypatch.setattr(importlib, "import_module", lambda _: (_ for _ in ()).throw(
        ImportError("private path")))
    try:
        assert runtime.comprobar_coherencia_indices(tmp_path)["status"] == "index_unavailable"
        assert list(tmp_path.iterdir()) == []
    finally:
        productores.restaurar(name, previous)


def test_provider_can_be_reactivated_and_uses_explicit_roots(tmp_path):
    from vault import runtime
    from vault.kernel import productores

    a, _, _ = _setup(tmp_path / "a")
    b, _, note_b = _setup(tmp_path / "b")
    note_b.write_text("changed", encoding="utf-8")
    name = "coherencia_indices"
    previous = productores.buscar(name)
    try:
        productores.restaurar(name, None)
        assert runtime.componer_coherencia_indices()
        assert construir(a.raiz).coherencia_indices.comprobar(construir(a.raiz))["status"] == "index_ok"
        assert construir(b.raiz).coherencia_indices.comprobar(construir(b.raiz))["status"] == "index_stale"
    finally:
        productores.restaurar(name, previous)


def test_direct_indexed_search_warns_when_content_is_stale(tmp_path, monkeypatch):
    import vault_search

    repo, _, note = _setup(tmp_path)
    note.write_text("changed", encoding="utf-8")
    monkeypatch.setattr(vault_search, "_raiz", lambda: repo.raiz)
    monkeypatch.setattr(vault_search, "_index_file", lambda: repo.indice_busqueda)
    monkeypatch.delenv("VAULT_MCP_LIVE_SEARCH", raising=False)
    result = vault_search.vault_search("original")
    assert result["ok"]
    assert result["index_coherence"]["status"] == "index_stale"


def test_direct_search_warns_when_provider_unavailable(tmp_path, monkeypatch):
    import vault_search
    from vault import runtime

    repo, _, _ = _setup(tmp_path)
    monkeypatch.setattr(vault_search, "_raiz", lambda: repo.raiz)
    monkeypatch.setattr(vault_search, "_index_file", lambda: repo.indice_busqueda)
    monkeypatch.delenv("VAULT_MCP_LIVE_SEARCH", raising=False)
    monkeypatch.setattr(runtime, "componer_coherencia_indices", lambda: False)
    before = {p.relative_to(repo.raiz): p.read_bytes() for p in repo.raiz.rglob("*") if p.is_file()}
    result = vault_search.vault_search("original")
    assert result["index_coherence"]["status"] == "index_unavailable"
    assert any("vault_reindex" in warning for warning in result["warnings"])
    assert before == {p.relative_to(repo.raiz): p.read_bytes() for p in repo.raiz.rglob("*") if p.is_file()}


def test_nested_and_moved_vaults_keep_relative_index_roots(tmp_path):
    import shutil

    outer, _, _ = _setup(tmp_path / "outer")
    inner, _, _ = _setup(outer.raiz / "nested")
    assert coherencia_indice(outer)["status"] == "index_ok"
    assert coherencia_indice(inner)["status"] == "index_ok"
    destination = tmp_path / "moved"
    shutil.move(str(inner.raiz), str(destination))
    assert coherencia_indice(RepositorioIndices(construir(destination)))["status"] == "index_ok"


def test_public_write_preserves_search_content_hash(tmp_path, monkeypatch):
    import hashlib
    import vault_io
    import vault_write

    (tmp_path / "07_Knowledge").mkdir()
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    monkeypatch.setenv("VAULT_AGENT", "test")
    vault_io.set_vault_root(tmp_path)
    content = ("A sufficiently detailed note body for quality checks.\n"
               "A second line with meaningful content.\n"
               "A third line with additional detail.\n")
    result = vault_write.vault_write("07_Knowledge", "Freshness example", content, tags=["test"])
    assert result["ok"], result
    index = json.loads((tmp_path / "99_Index" / "search-index.json").read_text(encoding="utf-8"))
    row = next(n for n in index["notes"] if n["title"] == "Freshness example")
    assert row["content_hash"] == hashlib.sha256((tmp_path / row["path"]).read_bytes()).hexdigest()


@pytest.mark.parametrize("provider_failure", ["missing", "error"])
def test_public_write_reports_index_refresh_failure_without_private_details(tmp_path, monkeypatch, provider_failure):
    import vault_io
    import vault_write

    class FailingProvider:
        def refrescar_busqueda(self, *args):
            raise OSError("PRIVATE-CANARY")

    (tmp_path / "07_Knowledge").mkdir()
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    monkeypatch.setenv("VAULT_AGENT", "test")
    vault_io.set_vault_root(tmp_path)
    original = vault_write.update_search_index

    def fail_after_legacy(*args, **kwargs):
        monkeypatch.setattr(vault_io, "_regenerador_de_indices",
                            lambda: None if provider_failure == "missing" else FailingProvider())
        return original(*args, **kwargs)

    monkeypatch.setattr(vault_write, "update_search_index", fail_after_legacy)
    result = vault_write.vault_write("07_Knowledge", "Failure example",
                                     "A detailed first line.\nA useful second line.\nA third line with context.\n",
                                     tags=["test"])
    assert result["ok"] and (tmp_path / result["path"]).exists()
    assert "vault_reindex" in result["index_warning"]
    assert "PRIVATE-CANARY" not in str(result)


@pytest.mark.parametrize("created,updated", [
    ("2020-01-02T03:04:05Z", "2021-02-03T04:05:06Z"),
    (None, None),
    (0, False),
])
def test_rebuild_distinguishes_declared_dates_and_observed_mtime(tmp_path, created, updated):
    repo, _, note = _setup(tmp_path)
    metadata = {"createdAt": created, "updatedAt": updated}
    ServicioReindex(repo, lambda _: metadata).reconstruir()
    row = json.loads(repo.indice_busqueda.read_text(encoding="utf-8"))["notes"][0]
    dates = row["timestamps"]
    assert dates["declared_created_at"] == created
    assert dates["declared_updated_at"] == updated
    assert dates["declared_source"] == "frontmatter"
    assert dates["observed_mtime_source"] == "filesystem"
    assert dates["observed_mtime_utc"] is not None
    assert dates["observed_mtime_utc"] != created


def test_public_reindex_twice_preserves_unchanged_index_bytes(tmp_path, monkeypatch):
    import vault_io
    import vault_reindex

    for folder in ("00_System", "07_Knowledge", "99_Index"):
        (tmp_path / folder).mkdir()
    (tmp_path / "07_Knowledge" / "note.md").write_text("sample", encoding="utf-8")
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    vault_io.set_vault_root(tmp_path)
    assert vault_reindex.vault_reindex()["ok"]
    index = tmp_path / "99_Index" / "search-index.json"
    before = index.read_bytes()
    assert vault_reindex.vault_reindex()["ok"]
    assert index.read_bytes() == before


def test_ordinary_write_after_reindex_keeps_search_index_coherent(tmp_path, monkeypatch):
    """Updated section index.md files and the change log keep current fingerprints (F2)."""
    import vault_io
    import vault_reindex
    import vault_write

    for folder in ("00_System", "07_Knowledge", "99_Index"):
        (tmp_path / folder).mkdir()
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    monkeypatch.setenv("VAULT_AGENT", "test")
    vault_io.set_vault_root(tmp_path)
    content = ("A sufficiently detailed note body for quality checks.\n"
               "A second line with meaningful content.\n"
               "A third line with additional detail.\n")
    assert vault_write.vault_write("07_Knowledge", "First freshness note", content, tags=["test"])["ok"]
    assert vault_reindex.vault_reindex()["ok"]
    repo = RepositorioIndices(construir(tmp_path))
    assert coherencia_indice(repo)["status"] == "index_ok"
    assert vault_write.vault_write("07_Knowledge", "Second freshness note", content, tags=["test"])["ok"]
    verdict = coherencia_indice(repo)
    assert verdict["status"] == "index_ok", verdict


def test_requirement_event_marker_keeps_the_changelog_table_contiguous(tmp_path, monkeypatch):
    import vault_change_log
    import vault_io

    (tmp_path / "00_System").mkdir()
    vault_io.set_vault_root(tmp_path)
    requirement = {"project": "demo", "req_id": "REQ-001", "from": None, "to": "draft"}
    assert vault_change_log.vault_change_log_add(
        action="transition", path="14_Requirements/demo/req-001.md", reason="created",
        agent="test", requirement=requirement)["ok"]
    assert vault_change_log.vault_change_log_add(
        action="created", path="07_Knowledge/n.md", reason="later row", agent="test")["ok"]
    lines = (tmp_path / "00_System" / "change-log.md").read_text(encoding="utf-8").splitlines()
    table = lines[lines.index(next(line for line in lines if line.startswith("| Timestamp"))):]
    assert all(line.startswith("|") for line in table if line.strip()), table
    assert sum("requirement-event:" in line for line in table) == 1
