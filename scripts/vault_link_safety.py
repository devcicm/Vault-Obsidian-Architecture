#!/usr/bin/env python3
"""Shared wiki-link validation and extraction helpers for vault tools."""

import re
from typing import Any, Dict, List


def _line_col(text: str, pos: int) -> Dict[str, int]:
    line = text.count("\n", 0, pos) + 1
    last_nl = text.rfind("\n", 0, pos)
    col = pos + 1 if last_nl < 0 else pos - last_nl
    return {"line": line, "column": col}


def _excerpt(text: str, pos: int, width: int = 48) -> str:
    start = max(0, pos - width // 2)
    end = min(len(text), pos + width // 2)
    return text[start:end].replace("\n", "\\n")


def _issue(code: str, message: str, text: str, pos: int, raw: str = "") -> Dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "raw": raw or _excerpt(text, pos),
        "excerpt": _excerpt(text, pos),
        **_line_col(text, pos),
    }


def validate_wikilinks(content: str) -> List[Dict[str, Any]]:
    """Return structured issues for malformed or non-contract wiki-links.

    Contract:
    - accepted shape is exactly [[target]] or [[target|alias]]
    - target cannot be empty
    - target cannot contain folder paths, backslashes, nested brackets, or extra
      opening/closing brackets
    """
    issues: List[Dict[str, Any]] = []

    for match in re.finditer(r"\[{3,}|\]{3,}", content):
        token = match.group(0)
        issues.append(
            _issue(
                "wikilink_extra_brackets",
                f"Wiki-link has too many bracket characters: {token}",
                content,
                match.start(),
                token,
            )
        )

    pos = 0
    while pos < len(content):
        next_open = content.find("[[", pos)
        next_close = content.find("]]", pos)

        if next_close != -1 and (next_open == -1 or next_close < next_open):
            issues.append(
                _issue(
                    "wikilink_unopened_or_extra_close",
                    "Found closing wiki-link brackets without a matching opening [[.",
                    content,
                    next_close,
                    "]]",
                )
            )
            pos = next_close + 2
            continue

        if next_open == -1:
            break

        close = content.find("]]", next_open + 2)
        if close == -1:
            issues.append(
                _issue(
                    "wikilink_unclosed",
                    "Found opening wiki-link brackets [[ without closing ]].",
                    content,
                    next_open,
                    content[next_open : min(len(content), next_open + 64)],
                )
            )
            break

        raw_body = content[next_open + 2 : close]
        target = raw_body.split("|", 1)[0].strip()
        raw_link = content[next_open : close + 2]

        if "[[" in raw_body or "]]" in raw_body or "[" in raw_body or "]" in raw_body:
            issues.append(
                _issue(
                    "wikilink_nested_or_stray_bracket",
                    "Wiki-link target or alias contains stray bracket characters.",
                    content,
                    next_open,
                    raw_link,
                )
            )
        if not target:
            issues.append(
                _issue(
                    "wikilink_empty_target",
                    "Wiki-link target is empty.",
                    content,
                    next_open,
                    raw_link,
                )
            )
        if "/" in target or "\\" in target:
            issues.append(
                _issue(
                    "wikilink_path_anchored",
                    "AP-21: wiki-link target contains a path. Use [[note-name]] only.",
                    content,
                    next_open,
                    raw_link,
                )
            )

        pos = close + 2

    unique: List[Dict[str, Any]] = []
    seen = set()
    for item in issues:
        key = (item["code"], item["line"], item["column"], item["raw"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def extract_wikilinks(content: str) -> List[str]:
    """Extract valid wiki-link targets after excluding malformed links."""
    valid: List[str] = []
    invalid_positions = {(i["line"], i["column"]) for i in validate_wikilinks(content)}
    for match in re.finditer(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content):
        pos = _line_col(content, match.start())
        if (pos["line"], pos["column"]) in invalid_positions:
            continue
        target = match.group(1).strip()
        if target:
            valid.append(target)
    return valid
