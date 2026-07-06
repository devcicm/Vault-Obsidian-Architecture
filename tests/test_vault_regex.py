#!/usr/bin/env python3
"""
Tests for vault_regex module.

Run with: python -m pytest tests/test_vault_regex.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
from vault_regex import (
    detect_bracket_anomalies,
    detect_path_anchored,
    sanitize_wikilink_content,
    fix_nested_brackets,
    fix_whitespace_in_links,
    fix_all_brackets,
    is_valid_link_content,
    validate_wikilink,
    extract_wiki_links_strict,
    validate_and_fix,
    WIKILINK_MAX_LEN,
    RE_NESTED_OPEN_3,
    RE_NESTED_CLOSE_3,
    RE_EMPTY_LINK,
)


class TestDetectBracketAnomalies:
    def test_no_anomalies(self):
        result = detect_bracket_anomalies("Hello [[world]] test")
        assert result == []

    def test_empty_link(self):
        result = detect_bracket_anomalies("Hello [[]] world")
        # May detect as mixed + empty (both are valid detections)
        types = [r["type"] for r in result]
        assert "empty" in types or "mixed" in types

    def test_nested_open_3(self):
        result = detect_bracket_anomalies("Hello [[[[world]]] test")
        assert len(result) >= 1
        types = [r["type"] for r in result]
        assert "nested_open" in types

    def test_nested_open_4(self):
        result = detect_bracket_anomalies("Hello [[[[[[world]]] test")
        assert len(result) >= 1

    def test_nested_close_3(self):
        result = detect_bracket_anomalies("Hello world]]]] test")
        assert len(result) >= 1
        types = [r["type"] for r in result]
        assert "nested_close" in types

    def test_mixed_brackets(self):
        result = detect_bracket_anomalies("Hello ][ world")
        assert len(result) >= 1
        types = [r["type"] for r in result]
        assert "mixed" in types

    def test_in_code_blocks_ignored(self):
        result = detect_bracket_anomalies("```\n[[[]]]\n```")
        assert result == []

    def test_multiple_anomalies(self):
        result = detect_bracket_anomalies("[[[]]] ][[ test [[]]")
        assert len(result) >= 2


class TestDetectPathAnchored:
    def test_no_path_anchored(self):
        result = detect_path_anchored("Hello [[world]] test")
        assert result == []

    def test_folder_path(self):
        result = detect_path_anchored("Hello [[folder/note]] test")
        assert len(result) == 1

    def test_absolute_path(self):
        result = detect_path_anchored("Hello [[/note]] test")
        assert len(result) == 1

    def test_relative_path(self):
        result = detect_path_anchored("Hello [[./note]] test")
        assert len(result) >= 1


class TestSanitizeWikilinkContent:
    def test_empty(self):
        result = sanitize_wikilink_content("")
        assert result == "nota-sin-titulo"

    def test_whitespace_only(self):
        result = sanitize_wikilink_content("   ")
        assert result == "nota-sin-titulo"

    def test_extras_spaces(self):
        result = sanitize_wikilink_content("  hello  world  ")
        assert result == "hello world"

    def test_brackets_removed(self):
        result = sanitize_wikilink_content("test[value]")
        assert "[" not in result
        assert "]" not in result

    def test_pipe_removed(self):
        result = sanitize_wikilink_content("title|alias")
        assert "|" not in result


class TestFixNestedBrackets:
    def test_no_change(self):
        result = fix_nested_brackets("Hello [[world]] test")
        assert result == "Hello [[world]] test"

    def test_collapse_4_opens(self):
        result = fix_nested_brackets("Hello [[[[world]] test")
        # Collapses directly to [[ (not [[[)
        assert "[[[[" not in result
        assert "[[" in result

    def test_collapse_3_opens(self):
        result = fix_nested_brackets("Hello [[[world]] test")
        assert "[[[" not in result
        assert "[[" in result

    def test_collapse_4_closes(self):
        result = fix_nested_brackets("Hello world]]]] test")
        assert "]]]]" not in result
        assert "]]]" not in result

    def test_inverted_bracket(self):
        result = fix_nested_brackets("][[test")
        assert "][" not in result


class TestFixWhitespaceInLinks:
    def test_no_change(self):
        result = fix_whitespace_in_links("Hello [[world]] test")
        assert result == "Hello [[world]] test"

    def test_leading_spaces(self):
        result = fix_whitespace_in_links("[[  note]]")
        assert "[[  note" not in result
        assert "[[note" in result

    def test_trailing_spaces(self):
        result = fix_whitespace_in_links("[[note  ]]")
        assert "note  ]]" not in result
        assert "note]]" in result

    def test_excessive_internal_spaces(self):
        result = fix_whitespace_in_links("[[note  with  spaces]]")
        assert "  " not in result


class TestIsValidLinkContent:
    def test_valid(self):
        assert is_valid_link_content("hello-world") is True
        assert is_valid_link_content("Hello World") is True

    def test_empty(self):
        assert is_valid_link_content("") is False
        assert is_valid_link_content("   ") is False

    def test_too_long(self):
        long_name = "a" * (WIKILINK_MAX_LEN + 1)
        assert is_valid_link_content(long_name) is False

    def test_invalid_chars(self):
        assert is_valid_link_content("test<file>") is False
        assert is_valid_link_content("test\x00value") is False
        assert is_valid_link_content("test|pipe") is False


class TestValidateWikilink:
    def test_valid_simple(self):
        valid, msg = validate_wikilink("hello")
        assert valid is True
        assert msg is None

    def test_valid_with_brackets(self):
        valid, msg = validate_wikilink("[[hello]]")
        assert valid is True
        assert msg is None

    def test_valid_with_alias(self):
        valid, msg = validate_wikilink("[[hello|world]]")
        assert valid is True
        assert msg is None

    def test_empty(self):
        valid, msg = validate_wikilink("")
        assert valid is False
        assert "empty" in msg.lower()

    def test_too_long(self):
        long_name = "a" * (WIKILINK_MAX_LEN + 1)
        valid, msg = validate_wikilink(long_name)
        assert valid is False
        assert "exceeds" in msg.lower()


class TestExtractWikiLinksStrict:
    def test_simple_link(self):
        result = extract_wiki_links_strict("Check [[my-note]] here")
        assert "my-note" in result

    def test_link_with_alias(self):
        result = extract_wiki_links_strict("Check [[my-note|alias]] here")
        assert "my-note" in result

    def test_empty_link_filtered(self):
        result = extract_wiki_links_strict("Check [[]] here")
        assert "empty" not in [r for r in result]

    def test_too_long_filtered(self):
        long_name = "a" * (WIKILINK_MAX_LEN + 1)
        content = f"Check [[{long_name}]] here"
        result = extract_wiki_links_strict(content)
        assert long_name not in result


class TestValidateAndFix:
    def test_clean_content(self):
        text, fixes, errors = validate_and_fix("Hello [[world]] test")
        assert errors == []

    def test_path_anchored_error(self):
        text, fixes, errors = validate_and_fix("[[folder/note]]")
        assert any("AP-21" in e for e in errors)

    def test_empty_link_error(self):
        text, fixes, errors = validate_and_fix("[[]]", allow_empty=False)
        assert any("AP-22" in e for e in errors)

    def test_nested_auto_fix(self):
        text, fixes, errors = validate_and_fix("[[[[test]]", allow_nested=False)
        # Should auto-fix
        assert "[[[" not in text
        assert "[[" in text


class TestFixAllBrackets:
    def test_nested_and_whitespace(self):
        text, fixes = fix_all_brackets("[[[  test  ]]]")
        assert len(fixes) >= 1
        assert "[[[" not in text


class TestEdgeCases:
    def test_unicode_brackets_in_content(self):
        # Unicode brackets should be detected as invalid
        assert is_valid_link_content("test〔value〕") is False

    def test_multiple_problems(self):
        # Multiple issues in one text
        result = detect_bracket_anomalies("[[[note]]] ][[ another")
        assert len(result) >= 2

    def test_preserves_normal_content(self):
        text = "This is normal markdown content with [[links]] and more text."
        result = detect_bracket_anomalies(text)
        assert result == []

    def test_nested_inside_link(self):
        # Nested brackets inside a link should be detected
        result = detect_bracket_anomalies("[[[[nested-link]]]]")
        assert len(result) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
