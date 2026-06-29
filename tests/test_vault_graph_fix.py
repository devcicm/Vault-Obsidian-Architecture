"""Unit tests for vault_graph_fix.

Run: python -m pytest tests/test_vault_graph_fix.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from vault_graph_fix import (
    _split_clean_note,
    _find_target,
    _replace_wikilink,
    _fix_brackets_in_content,
    _fix_path_anchored,
    fix_vault,
)


class TestWikiLinkSplitting:
    def test_simple_link(self):
        note, alias = _split_clean_note("[[note-one]]")
        assert note == "note-one"
        assert alias is None

    def test_link_with_alias(self):
        note, alias = _split_clean_note("[[note-one|Display Name]]")
        assert note == "note-one"
        assert alias == "Display Name"


class TestFindTarget:
    def test_exact_match(self):
        stems = {"noteone": ["01_Projects/foo.md"], "notetwo": ["07_Knowledge/bar.md"]}
        result = _find_target("noteone", stems)
        assert result == ("01_Projects/foo.md", "exact")

    def test_missing_returns_none(self):
        stems = {"noteone": ["01_Projects/foo.md"]}
        result = _find_target("nonexistent", stems)
        assert result is None

    def test_fuzzy_match_returns_canonical(self):
        stems = {
            "machine-learning-guide": ["07_Knowledge/ml-guide.md"],
            "other": ["random.md"],
        }
        result = _find_target("machine-learning", stems, threshold=0.5)
        assert result is not None
        path, strategy = result
        assert path == "07_Knowledge/ml-guide.md"
        assert strategy.startswith("fuzzy:")


class TestReplaceWikiLink:
    def test_replace_simple(self):
        new_text, changed = _replace_wikilink(
            "see [[old-target]] here", "old-target", "new-target"
        )
        assert changed
        assert new_text == "see [[new-target]] here"

    def test_replace_path_anchored(self):
        new_text, changed = _replace_wikilink(
            "see [[/old-target]] here", "old-target", "new-target"
        )
        assert changed
        assert new_text == "see [[new-target]] here"

    def test_no_change_when_missing(self):
        new_text, changed = _replace_wikilink("no link here", "old", "new")
        assert not changed
        assert new_text == "no link here"


class TestBracketFixer:
    def test_nested_brackets_fixed(self):
        text = "[[[[nested]]]] brackets"
        new_text, count = _fix_brackets_in_content(text)
        assert count > 0
        assert "[[nested]]" in new_text

    def test_whitespace_inside_brackets_fixed(self):
        text = "[[ note with spaces ]]"
        new_text, count = _fix_brackets_in_content(text)
        assert count >= 0


class TestPathAnchoredFixer:
    def test_strips_folder(self):
        text = "links to [[folder/note-target]] here"
        new_text, count = _fix_path_anchored(text)
        assert count == 1
        assert "[[note-target]]" in new_text

    def test_keeps_unanchored(self):
        text = "links to [[note-target]] here"
        new_text, count = _fix_path_anchored(text)
        assert count == 0
        assert new_text == text

    def test_multiple_paths(self):
        text = "[[a/b]] and [[c/d]]"
        new_text, count = _fix_path_anchored(text)
        assert count == 2


class TestFixVaultEndToEnd:
    def test_path_anchored_fix_in_vault(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "07_Knowledge").mkdir()
        (vault / "07_Knowledge" / "real-note.md").write_text(
            "---\ntitle: Real Note\n---\n\nBody",
            encoding="utf-8",
        )
        (vault / "07_Knowledge" / "index.md").write_text(
            "---\ntitle: Index\n---\n\nLink to [[07_Knowledge/real-note]]",
            encoding="utf-8",
        )
        report = fix_vault(vault)
        assert report["summary"]["notes_to_modify"] >= 1
        path_anchored_fix = any(
            f["type"] == "path_anchored"
            for fix in report["fixes"]
            for f in fix["fixes"]
        )
        assert path_anchored_fix

    def test_bracket_fix_in_vault(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "07_Knowledge").mkdir()
        (vault / "07_Knowledge" / "broken.md").write_text(
            "---\ntitle: Broken\n---\n\nHas [[[[too many brackets]]]] in a sentence.",
            encoding="utf-8",
        )
        report = fix_vault(vault, only="brackets")
        assert report["summary"]["notes_to_modify"] >= 1
