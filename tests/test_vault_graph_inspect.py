"""Unit tests for vault_graph_inspect.

Run: python -m pytest tests/test_vault_graph_inspect.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from vault_graph_inspect import (
    _shingles,
    _jaccard,
    _strip_frontmatter,
    _extract_title,
    _extract_tags,
    _normalize_for_hash,
    _is_migrated,
    _load_notes,
    _detect_wikilink_syntax_errors,
    generate_report,
)


class TestFrontmatterParsing:
    def test_strip_frontmatter_removes_yaml_block(self):
        content = "---\ntitle: Foo\ntags: [a, b]\n---\n\n# Body\n\ntext"
        assert _strip_frontmatter(content).startswith("# Body")

    def test_strip_frontmatter_no_frontmatter(self):
        content = "# Just body\n\nno frontmatter here"
        assert _strip_frontmatter(content) == content

    def test_extract_title(self):
        assert _extract_title("---\ntitle: My Title\n---\nbody") == "My Title"

    def test_extract_title_quoted(self):
        assert _extract_title('---\ntitle: "Quoted Title"\n---\n') == "Quoted Title"

    def test_extract_title_missing(self):
        assert _extract_title("body without title") is None

    def test_extract_tags_list(self):
        assert _extract_tags("---\ntags: [python, vault, api]\n---") == {
            "python",
            "vault",
            "api",
        }

    def test_extract_tags_empty(self):
        assert _extract_tags("body without tags") == set()


class TestNormalization:
    def test_normalize_lowercase_no_punct(self):
        assert _normalize_for_hash("Hello, World!") == "hello world"

    def test_normalize_collapses_whitespace(self):
        assert _normalize_for_hash("foo   bar\t\nbaz") == "foo bar baz"


class TestShingles:
    def test_short_text_returns_one_shingle(self):
        s = _shingles("one two three")
        assert s == {"one two three"}

    def test_window_size_5_default(self):
        s = _shingles("a b c d e f g")
        assert "a b c d e" in s
        assert "c d e f g" in s

    def test_jaccard_identical(self):
        a = {"x", "y", "z"}
        assert _jaccard(a, a) == 1.0

    def test_jaccard_disjoint(self):
        assert _jaccard({"a"}, {"b"}) == 0.0

    def test_jaccard_partial(self):
        sim = _jaccard({"a", "b", "c"}, {"b", "c", "d"})
        assert abs(sim - 0.5) < 1e-9


class TestGenerateReport:
    def test_empty_directory(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "00_System").mkdir()
        report = generate_report(vault)
        assert report["ok"] is True
        assert report["summary"]["total_notes"] == 0
        assert report["summary"]["broken_links"] == 0

    def test_basic_graph(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "07_Knowledge").mkdir()
        (vault / "07_Knowledge" / "a.md").write_text(
            "---\ntitle: Alpha\ntags: [test]\n---\n\nBody A links to [[beta]]",
            encoding="utf-8",
        )
        (vault / "07_Knowledge" / "b.md").write_text(
            "---\ntitle: Beta\n---\n\nBody B has its own content [[alpha]]",
            encoding="utf-8",
        )
        report = generate_report(vault)
        assert report["summary"]["total_notes"] == 2
        assert report["summary"]["total_edges"] == 2

    def test_exact_duplicates_detected(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "07_Knowledge").mkdir()
        body = "---\ntitle: Same\n---\n\n# Common body\n\nidentical"
        (vault / "07_Knowledge" / "x.md").write_text(body, encoding="utf-8")
        (vault / "07_Knowledge" / "y.md").write_text(body, encoding="utf-8")
        report = generate_report(vault)
        assert report["summary"]["exact_duplicates_groups"] == 1

    def test_broken_links_detected(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "07_Knowledge").mkdir()
        (vault / "07_Knowledge" / "a.md").write_text(
            "---\ntitle: Alpha\n---\n\nLinks to [[nonexistent]]",
            encoding="utf-8",
        )
        report = generate_report(vault)
        assert report["summary"]["broken_links"] == 1


class TestMigrationExclusion:
    def test_is_migrated_at_root(self):
        assert _is_migrated("10_Migrated/anything.md")

    def test_is_migrated_subfolder(self):
        assert _is_migrated("10_Migrated/direct/foo.md")
        assert _is_migrated("10_Migrated/indirect/bar.md")
        assert _is_migrated("10_Migrated/excluded/baz.md")

    def test_is_not_migrated_other_folder(self):
        assert not _is_migrated("07_Knowledge/foo.md")
        assert not _is_migrated("01_Projects/ans/AGENTS.md")
        assert not _is_migrated("README.md")

    def test_load_notes_excludes_migrated_by_default(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "07_Knowledge").mkdir()
        (vault / "10_Migrated").mkdir()
        (vault / "07_Knowledge" / "alive.md").write_text("# alive", encoding="utf-8")
        (vault / "10_Migrated" / "archived.md").write_text(
            "# archived", encoding="utf-8"
        )
        notes = _load_notes(vault, include_migrated=False)
        assert "07_Knowledge/alive.md" in notes
        assert not any(k.startswith("10_Migrated/") for k in notes)

    def test_load_notes_includes_when_requested(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "10_Migrated").mkdir()
        (vault / "10_Migrated" / "archived.md").write_text(
            "# archived", encoding="utf-8"
        )
        notes = _load_notes(vault, include_migrated=True)
        assert any(k.startswith("10_Migrated/") for k in notes)


class TestWikilinkSyntaxErrors:
    def test_detects_bracket_anomaly(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "07_Knowledge").mkdir()
        (vault / "07_Knowledge" / "broken.md").write_text(
            "---\ntitle: Broken\n---\n\nHas [[[[nested]]]] brackets.",
            encoding="utf-8",
        )
        notes = _load_notes(vault, include_migrated=True)
        errors = _detect_wikilink_syntax_errors(notes)
        assert any(
            e["type"] == "nested_open" or e["type"] == "bracket_anomaly" for e in errors
        )

    def test_detects_path_anchored(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "07_Knowledge").mkdir()
        (vault / "07_Knowledge" / "anchored.md").write_text(
            "---\ntitle: Anchored\n---\n\nLinks to [[carpeta/nota]] incorrectly.",
            encoding="utf-8",
        )
        notes = _load_notes(vault, include_migrated=True)
        errors = _detect_wikilink_syntax_errors(notes)
        assert any(e["type"] == "path_anchored" for e in errors)

    def test_clean_content_no_errors(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "07_Knowledge").mkdir()
        (vault / "07_Knowledge" / "clean.md").write_text(
            "---\ntitle: Clean\n---\n\nLinks to [[note-one]] and [[note-two|alias]] correctly.",
            encoding="utf-8",
        )
        notes = _load_notes(vault, include_migrated=True)
        errors = _detect_wikilink_syntax_errors(notes)
        assert errors == []


class TestScopeReporting:
    def test_default_scope_excludes_migrated(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "07_Knowledge").mkdir()
        (vault / "10_Migrated").mkdir()
        (vault / "07_Knowledge" / "a.md").write_text("# a", encoding="utf-8")
        (vault / "10_Migrated" / "old.md").write_text("# old", encoding="utf-8")
        report = generate_report(vault)
        assert report["scope"] == "excluding-10_Migrated"
        assert report["summary"]["total_notes"] == 1

    def test_included_scope(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "07_Knowledge").mkdir()
        (vault / "10_Migrated").mkdir()
        (vault / "07_Knowledge" / "a.md").write_text("# a", encoding="utf-8")
        (vault / "10_Migrated" / "old.md").write_text("# old", encoding="utf-8")
        report = generate_report(vault, include_migrated=True)
        assert report["scope"] == "full"
        assert report["summary"]["total_notes"] == 2
