#!/usr/bin/env python3
"""Tests for v38 frontmatter date coercion (vault_lib._coerce_dates).

Run from repo root:
    python -m pytest tests/test_vault_frontmatter_dates.py -v

PyYAML's safe_load turns unquoted ISO date/datetime scalars into datetime
objects. Before v38 that crashed audit/reindex ('datetime not subscriptable' /
'not JSON serializable') on vaults whose notes were written by older tooling.
These tests lock in that parse_frontmatter always returns JSON-safe strings.
"""

import sys
import os
import json
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from vault_lib import parse_frontmatter, parse_frontmatter_with_body, serialize_frontmatter, _coerce_dates


def test_unquoted_datetime_becomes_iso_string():
    note = "---\ncreatedAt: 2026-07-11T10:00:00\ntitle: X\n---\nbody\n"
    fm = parse_frontmatter(note)
    assert isinstance(fm["createdAt"], str)
    assert fm["createdAt"].startswith("2026-07-11T10:00:00")


def test_unquoted_date_becomes_iso_string():
    note = "---\nupdatedAt: 2026-07-11\n---\nbody\n"
    fm = parse_frontmatter(note)
    assert fm["updatedAt"] == "2026-07-11"


def test_parsed_frontmatter_is_json_serializable():
    note = "---\ncreatedAt: 2026-07-11T10:00:00\nupdatedAt: 2026-07-11\n---\nbody\n"
    fm = parse_frontmatter(note)
    json.dumps(fm)  # must not raise TypeError


def test_with_body_also_coerces():
    fm, body = parse_frontmatter_with_body("---\nd: 2026-01-02\n---\nhello")
    assert fm["d"] == "2026-01-02"
    assert body == "hello"


def test_nested_and_list_dates_coerced():
    obj = {"a": datetime(2026, 7, 11, 9, 30), "b": [date(2026, 1, 1)], "c": {"d": date(2026, 2, 2)}}
    out = _coerce_dates(obj)
    assert out["a"].startswith("2026-07-11T09:30")
    assert out["b"][0] == "2026-01-01"
    assert out["c"]["d"] == "2026-02-02"
    json.dumps(out)


def test_non_date_values_untouched():
    obj = {"n": 5, "s": "x", "f": 1.5, "b": True, "none": None, "lst": [1, "a"]}
    assert _coerce_dates(obj) == obj


def test_serialize_roundtrip_is_stable():
    # A dict carrying datetime should serialize to quoted-ISO and re-read as str.
    fm = {"createdAt": datetime(2026, 7, 11, 10, 0, 0), "title": "X"}
    block = serialize_frontmatter(fm)
    reparsed = parse_frontmatter(block + "body\n")
    assert isinstance(reparsed["createdAt"], str)
    json.dumps(reparsed)
