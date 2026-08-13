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
    _strip_redundant_prefix,
    _classify_broken,
    _seq_ratio,
    _jaccard_tokens,
    classify_all_broken,
    wizard_pick,
    _create_stub,
    _stub_already_exists,
    apply_classified_fixes,
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
    """Despojar la carpeta no es gratis: Obsidian **sí** resuelve `[[a/b]]`.

    Hasta v40.13 esta función quitaba la carpeta a ciegas, que es el mismo
    error de basename que v40.12 arregló en la medida, cometido por una tool
    que escribe y con el signo contrario: allí un enlace roto salía verde;
    aquí un enlace bueno se vuelve ambiguo.
    """

    def test_sin_indice_no_toca_nada(self):
        """No saber es motivo para no escribir, no para escribir igual."""
        text = "links to [[folder/note-target]] here"
        new_text, count = _fix_path_anchored(text)
        assert count == 0
        assert new_text == text

    def test_strips_folder_cuando_el_destino_no_existe_y_el_stem_es_unico(self):
        text = "links to [[folder/note-target]] here"
        new_text, count = _fix_path_anchored(
            text, {"notetarget": ["07_Knowledge/note-target.md"]})
        assert count == 1
        assert "[[note-target]]" in new_text

    def test_no_toca_el_destino_que_ya_resuelve(self):
        text = "links to [[07_Knowledge/real-note]] here"
        new_text, count = _fix_path_anchored(
            text, {"realnote": ["07_Knowledge/real-note.md"]})
        assert count == 0
        assert new_text == text

    def test_no_desambigua_por_su_cuenta_cuando_hay_dos_con_el_mismo_nombre(self):
        """Con dos `ct105.md`, quitar la carpeta borra la única pista."""
        text = "[[containers/ct105]]"
        new_text, count = _fix_path_anchored(
            text, {"ct105": ["vms/ct105.md", "backups/ct105.md"]})
        assert count == 0
        assert new_text == text

    def test_keeps_unanchored(self):
        text = "links to [[note-target]] here"
        new_text, count = _fix_path_anchored(text, {})
        assert count == 0
        assert new_text == text

    def test_multiple_paths(self):
        text = "[[a/b]] and [[c/d]]"
        new_text, count = _fix_path_anchored(
            text, {"b": ["x/b.md"], "d": ["y/d.md"]})
        assert count == 2


class TestFixVaultEndToEnd:
    def test_el_destino_con_carpeta_que_resuelve_no_se_reescribe(self, tmp_path):
        """El caso que el test viejo exigía romper.

        `[[07_Knowledge/real-note]]` apunta a esa nota y a ninguna otra.
        Reescribirlo no arregla nada y pierde la única desambiguación escrita.
        """
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
        assert not any(
            f["type"] == "path_anchored"
            for fix in report["fixes"]
            for f in fix["fixes"]
        )

    def test_path_anchored_fix_in_vault(self, tmp_path):
        """Con carpeta inexistente y basename único, sí se despoja."""
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "07_Knowledge").mkdir()
        (vault / "07_Knowledge" / "real-note.md").write_text(
            "---\ntitle: Real Note\n---\n\nBody",
            encoding="utf-8",
        )
        (vault / "07_Knowledge" / "index.md").write_text(
            "---\ntitle: Index\n---\n\nLink to [[carpeta-que-no-existe/real-note]]",
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

    def test_no_reescribe_wikilinks_dentro_de_un_fence(self, tmp_path):
        """Obsidian no resuelve un wikilink dentro de un fence: lo enseña.

        Una tool que mide y no lo excluye infla un número; esta escribe, así
        que corrompía el ejemplo de la nota que documenta la sintaxis.
        """
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "07_Knowledge").mkdir()
        (vault / "07_Knowledge" / "real-note.md").write_text(
            "---\ntitle: Real Note\n---\n\nBody", encoding="utf-8")
        doc = vault / "07_Knowledge" / "convencion.md"
        cuerpo = (
            "---\ntitle: Convención\n---\n\n"
            "Se escribe así:\n\n```md\n[[carpeta-inexistente/real-note]]\n```\n"
        )
        doc.write_text(cuerpo, encoding="utf-8")
        report = fix_vault(vault)
        modificadas = {f["note"] for f in report["fixes"] if f["changed"]}
        assert not any("convencion" in m for m in modificadas)

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


class TestPrefixStripping:
    def test_ans_prefix_stripped(self):
        assert _strip_redundant_prefix("ans-jwt-token") == "jwt-token"

    def test_mcp_prefix_stripped(self):
        assert _strip_redundant_prefix("mcp-server") == "server"

    def test_double_ans_prefix_stripped(self):
        assert _strip_redundant_prefix("ansanspipeline") == "pipeline"

    def test_no_prefix_unchanged(self):
        assert _strip_redundant_prefix("plain-note") is None

    def test_short_after_strip_returns_none(self):
        assert _strip_redundant_prefix("ans-a") is None


class TestScoringHelpers:
    def test_seq_ratio_identical(self):
        assert _seq_ratio("abc", "abc") == 1.0

    def test_seq_ratio_disjoint(self):
        assert _seq_ratio("abc", "xyz") < 0.5

    def test_jaccard_tokens(self):
        sim = _jaccard_tokens("machine-learning", "machine guide")
        assert 0 < sim < 1


class TestClassifyBroken:
    def test_exact_match_active(self):
        active = {"jwttoken": ["07_Knowledge/jwt-token.md"]}
        migrated: dict = {}
        result = _classify_broken("jwttoken", active, migrated)
        assert result["category"] == "exact_candidate"
        assert result["recommended_stem"] == "jwttoken"

    def test_prefix_strip_match(self):
        active = {"ansexecutionpipeline": ["13_Flows/pipeline.md"]}
        result = _classify_broken("ansansexecutionpipeline", active, {})
        # If score is 1.0 (after prefix strip + same stem match) → exact
        # If not, falls through to fuzzy match against the same stem → partial
        assert result["recommended_stem"] == "ansexecutionpipeline"
        assert result["category"] in ("exact_candidate", "partial_match")
        assert len(result["candidates"]) >= 1

    def test_points_to_migrated(self):
        active: dict = {}
        migrated = {"legacy-doc": ["10_Migrated/old.md"]}
        result = _classify_broken("legacy-doc", active, migrated)
        assert result["category"] == "points_to_migrated"

    def test_partial_match_fuzzy(self):
        active = {"machine-learning-guide": ["07_Knowledge/ml.md"]}
        result = _classify_broken("machinelearning", active, {}, threshold_partial=0.5)
        assert result["category"] in ("partial_match", "exact_candidate")

    def test_no_match(self):
        active = {"something-else": ["x.md"]}
        result = _classify_broken("totally-unrelated-zzz", active, {})
        assert result["category"] == "no_match"
        assert result["candidates"] == []


class TestWizardPick:
    def test_pick_first_candidate(self):
        from io import StringIO

        stdin = StringIO("1\n")
        stdout = StringIO()
        candidates = [
            {
                "stem": "note-a",
                "path": "07_Knowledge/a.md",
                "score": 0.9,
                "strategy": "fuzzy",
            },
            {
                "stem": "note-b",
                "path": "07_Knowledge/b.md",
                "score": 0.7,
                "strategy": "fuzzy",
            },
        ]
        result = wizard_pick("missing", candidates, 5, stdin=stdin, stdout=stdout)
        assert result["action"] == "fix"
        assert result["stem"] == "note-a"

    def test_skip(self):
        from io import StringIO

        stdin = StringIO("s\n")
        stdout = StringIO()
        result = wizard_pick("missing", [], 5, stdin=stdin, stdout=stdout)
        assert result["action"] == "skip"

    def test_stub_choice(self):
        from io import StringIO

        stdin = StringIO("t\n")
        stdout = StringIO()
        result = wizard_pick("missing", [], 5, stdin=stdin, stdout=stdout)
        assert result["action"] == "stub"

    def test_quit_returns_none(self):
        from io import StringIO

        stdin = StringIO("q\n")
        stdout = StringIO()
        result = wizard_pick("missing", [], 5, stdin=stdin, stdout=stdout)
        assert result is None


class TestStubCreation:
    def test_stub_created(self, tmp_path):
        from vault_graph_fix import _create_stub

        vault = tmp_path / "vault"
        vault.mkdir()
        result = _create_stub(
            vault,
            "new-target",
            ["01_Projects/foo.md", "07_Knowledge/bar.md"],
            {"category": "no_match"},
        )
        assert result["created"] is True
        assert (vault / "02_Observability/maintenance/stubs/new-target.md").exists()

    def test_stub_skipped_if_real_note_exists(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "07_Knowledge").mkdir()
        (vault / "07_Knowledge" / "existing.md").write_text("# real", encoding="utf-8")
        result = _create_stub(
            vault,
            "existing",
            ["01_Projects/foo.md"],
            {"category": "no_match"},
        )
        assert result["created"] is False
        assert result["reason"] == "already_exists"

    def test_stub_skipped_if_already_in_stubs(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "02_Observability/maintenance/stubs").mkdir(parents=True)
        (vault / "02_Observability/maintenance/stubs/existing.md").write_text("# stub", encoding="utf-8")
        result = _create_stub(
            vault,
            "existing",
            ["01_Projects/foo.md"],
            {"category": "no_match"},
        )
        assert result["created"] is False


class TestApplyClassifiedFixes:
    def test_apply_fix_modifies_source(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "07_Knowledge").mkdir()
        (vault / "07_Knowledge" / "real.md").write_text(
            "---\ntitle: Real\n---\n\nBody",
            encoding="utf-8",
        )
        (vault / "01_Projects").mkdir()
        (vault / "01_Projects" / "source.md").write_text(
            "---\ntitle: Source\n---\n\nLink to [[wrong-name]]",
            encoding="utf-8",
        )
        notes_active = {
            "07_Knowledge/real.md": {
                "body": "Body",
                "title": "Real",
                "tags": set(),
                "body_hash": "x",
            },
            "01_Projects/source.md": {
                "body": "Link to [[wrong-name]]",
                "title": "Source",
                "tags": set(),
                "body_hash": "y",
            },
        }
        decisions = {
            "wrongname": {
                "action": "fix",
                "stem": "real",
                "path": "07_Knowledge/real.md",
                "referenced_by": ["01_Projects/source.md"],
                "classification": {"category": "exact_candidate"},
            }
        }
        result = apply_classified_fixes(decisions, notes_active, vault)
        assert result["links_fixed"] >= 1
        new_text = (vault / "01_Projects/source.md").read_text(encoding="utf-8")
        assert "[[wrong-name]]" not in new_text

    def test_apply_stub_creates_note(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        notes_active: dict = {}
        decisions = {
            "orphan": {
                "action": "stub",
                "referenced_by": ["some/source.md"],
                "classification": {"category": "no_match"},
            }
        }
        result = apply_classified_fixes(decisions, notes_active, vault)
        assert result["stubs_created"] == 1
        assert (vault / "02_Observability/maintenance/stubs/orphan.md").exists()
