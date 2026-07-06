#!/usr/bin/env python3
"""
Tests for vault_encoding module.

Run with: python -m pytest tests/test_vault_encoding.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
from vault_encoding import (
    normalize_to_nfc,
    normalize_to_nfd,
    normalize_quotes,
    normalize_dashes,
    remove_invisible_chars,
    normalize_newlines,
    remove_control_chars,
    strip_bom,
    sanitize_content,
    sanitize_filename,
    decode_safely,
    detect_issues,
)


class TestNormalizeToNfc:
    def test_empty_string(self):
        assert normalize_to_nfc("") == ""

    def test_simple_ascii(self):
        assert normalize_to_nfc("hello") == "hello"

    def test_combined_accents(self):
        assert normalize_to_nfc("\u00e9") == "\u00e9"

    def test_decomposed_accents(self):
        assert normalize_to_nfc("e\u0301") == "\u00e9"

    def test_mixed_accents(self):
        result = normalize_to_nfc("caf\u0065\u0301")
        assert result == "caf\u00e9"


class TestNormalizeToNfd:
    def test_empty_string(self):
        assert normalize_to_nfd("") == ""

    def test_simple_ascii(self):
        assert normalize_to_nfd("hello") == "hello"

    def test_combined_to_decomposed(self):
        assert normalize_to_nfd("\u00e9") == "e\u0301"


class TestNormalizeQuotes:
    def test_empty_string(self):
        result, fixes = normalize_quotes("")
        assert result == ""

    def test_smart_double_quotes(self):
        result, fixes = normalize_quotes("\u201chello\u201d")
        assert result == '"hello"'
        assert len(fixes) == 2

    def test_smart_single_quotes(self):
        result, fixes = normalize_quotes("\u2018hello\u2019")
        assert result == "'hello'"
        assert len(fixes) == 2

    def test_guillemets(self):
        result, fixes = normalize_quotes("\u00abhello\u00bb")
        assert result == '"hello"'

    def test_no_quotes(self):
        result, fixes = normalize_quotes("hello world")
        assert result == "hello world"
        assert fixes == []


class TestNormalizeDashes:
    def test_empty_string(self):
        result, fixes = normalize_dashes("")
        assert result == ""

    def test_en_dash(self):
        result, fixes = normalize_dashes("hello \u2013 world")
        assert result == "hello - world"
        assert any(f["type"] == "unicode_dash" for f in fixes)

    def test_em_dash(self):
        result, fixes = normalize_dashes("hello \u2014 world")
        assert result == "hello -- world"

    def test_non_breaking_hyphen(self):
        result, fixes = normalize_dashes("hello\u2011world")
        assert result == "hello-world"

    def test_thin_space(self):
        result, fixes = normalize_dashes("hello\u2009world")
        assert result == "hello world"


class TestRemoveInvisibleChars:
    def test_empty_string(self):
        result, fixes = remove_invisible_chars("")
        assert result == ""

    def test_zero_width_space(self):
        result, fixes = remove_invisible_chars("hello\u200bworld")
        assert result == "helloworld"
        assert len(fixes) == 1

    def test_zero_width_joiner(self):
        result, fixes = remove_invisible_chars("hello\u200dworld")
        assert result == "helloworld"

    def test_bom(self):
        result, fixes = remove_invisible_chars("\ufeffhello")
        assert result == "hello"

    def test_soft_hyphen(self):
        result, fixes = remove_invisible_chars("hello\u00adworld")
        assert result == "helloworld"

    def test_directional_marks(self):
        result, fixes = remove_invisible_chars("hello\u200eworld")
        assert result == "helloworld"


class TestNormalizeNewlines:
    def test_empty_string(self):
        result, fixes = normalize_newlines("")
        assert result == ""

    def test_crlf_to_lf(self):
        result, fixes = normalize_newlines("hello\r\nworld")
        assert result == "hello\nworld"
        assert any(f["from"] == "CRLF" for f in fixes)

    def test_cr_to_lf(self):
        result, fixes = normalize_newlines("hello\rworld")
        assert result == "hello\nworld"

    def test_mixed_newlines(self):
        result, fixes = normalize_newlines("line1\r\nline2\rline3\nline4")
        assert result == "line1\nline2\nline3\nline4"


class TestRemoveControlChars:
    def test_empty_string(self):
        result, fixes = remove_control_chars("")
        assert result == ""

    def test_keeps_valid_chars(self):
        result, fixes = remove_control_chars("hello\tworld\n")
        assert result == "hello\tworld\n"
        assert fixes == []

    def test_removes_invalid_control(self):
        result, fixes = remove_control_chars("hello\x00world")
        assert result == "helloworld"
        assert len(fixes) == 1


class TestStripBom:
    def test_empty_string(self):
        result, was_present = strip_bom("")
        assert result == ""
        assert was_present is False

    def test_bom_present(self):
        result, was_present = strip_bom("\ufeffhello")
        assert result == "hello"
        assert was_present is True

    def test_bom_not_present(self):
        result, was_present = strip_bom("hello")
        assert result == "hello"
        assert was_present is False


class TestSanitizeContent:
    def test_empty_string(self):
        result, fixes = sanitize_content("")
        assert result == ""

    def test_clean_content(self):
        result, fixes = sanitize_content("Hello world")
        assert result == "Hello world"
        assert fixes == []

    def test_smart_quotes_fixed(self):
        result, fixes = sanitize_content("\u201chello\u201d")
        assert result == '"hello"'
        assert any(f["step"] == "normalize_quotes" for f in fixes)

    def test_unicode_dashes_fixed(self):
        result, fixes = sanitize_content("hello \u2014 world")
        assert result == "hello -- world"

    def test_invisible_chars_removed(self):
        result, fixes = sanitize_content("hello\u200bworld")
        assert result == "helloworld"

    def test_dry_run(self):
        result, fixes = sanitize_content("\u201chello\u201d", dry_run=True)
        assert result == "\u201chello\u201d"
        assert fixes == []


class TestSanitizeFilename:
    def test_empty_string(self):
        assert sanitize_filename("") == "untitled"

    def test_simple_filename(self):
        assert sanitize_filename("my-note.md") == "my-note.md"

    def test_spaces_replaced(self):
        assert sanitize_filename("my note.md") == "my-note.md"

    def test_invalid_chars_removed(self):
        assert sanitize_filename("my<file>name.md") == "myfilename.md"

    def test_colon_removed(self):
        result = sanitize_filename("my:file:name.md")
        assert ":" not in result

    def test_normalizes_unicode(self):
        result = sanitize_filename("caf\u0065\u0301.md")
        assert "e\u0301" in result or "\u00e9" in result

    def test_strips_dashes(self):
        result = sanitize_filename("--my-note--.md")
        assert not result.startswith("-")
        assert "my-note" in result

    def test_truncates_long_filename(self):
        long_name = "a" * 300 + ".md"
        result = sanitize_filename(long_name)
        assert len(result) <= 200

    def test_preserves_extension_on_truncate(self):
        long_name = "a" * 300 + ".md"
        result = sanitize_filename(long_name)
        assert result.endswith(".md")


class TestDecodeSafely:
    def test_utf8_bytes(self):
        content, encoding = decode_safely(b"hello world")
        assert content == "hello world"
        assert encoding == "utf-8"

    def test_utf8_with_bom(self):
        content, encoding = decode_safely("\ufeffhello".encode("utf-8"))
        assert "hello" in content
        assert encoding in ["utf-8-sig", "utf-8"]

    def test_latin1_bytes(self):
        content, encoding = decode_safely(b"caf\xe9")
        assert content == "café"
        assert encoding == "latin-1"

    def test_invalid_utf8_replacement(self):
        content, encoding = decode_safely(b"hello\xffworld")
        assert "hello" in content
        assert encoding in ["latin-1", "utf-8-replaced"]


class TestDetectIssues:
    def test_empty_string(self):
        issues = detect_issues("")
        assert issues == []

    def test_clean_content(self):
        issues = detect_issues("Hello world")
        assert issues == []

    def test_detects_smart_quotes(self):
        issues = detect_issues("\u201chello\u201d")
        assert any(i["type"] == "smart_quotes" for i in issues)

    def test_detects_en_dash(self):
        issues = detect_issues("hello\u2013world")
        assert any(i["type"] == "unicode_dash" for i in issues)

    def test_detects_invisible_chars(self):
        issues = detect_issues("hello\u200bworld")
        assert any(i["type"] == "invisible_char" for i in issues)

    def test_detects_bom(self):
        issues = detect_issues("\ufeffhello")
        assert any(i["type"] == "bom" for i in issues)

    def test_detects_crlf(self):
        issues = detect_issues("hello\r\nworld")
        assert any(i["type"] == "newline_inconsistency" for i in issues)


class TestIntegration:
    def test_full_pipeline(self):
        dirty = "\u201chello\u2014world\u200b\u2019"
        result, fixes = sanitize_content(dirty)
        assert '"' in result
        assert "--" in result
        assert "\u200b" not in result
        assert "'" in result

    def test_filename_survival(self):
        dirty = "my <invalid> file \u2014 name.md"
        result = sanitize_filename(dirty)
        assert "<" not in result
        assert ">" not in result
        assert "invalid" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
