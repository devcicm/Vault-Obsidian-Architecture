#!/usr/bin/env python3
"""
vault_test_runner.py — Test suite para las 53 vault tools.

Modos:
  --smoke     (~30s)  Verifica que todos los scripts compilan, importan y --help retorna 0.
  --contracts (~3min) Happy-path de cada tool: JSON válido con ok:true y campos obligatorios.
  --errors    (~3min) Error-paths: args faltantes o inválidos retornan {ok:false, error_code}.

Usage:
    python vault_test_runner.py --smoke
    python vault_test_runner.py --contracts
    python vault_test_runner.py --errors
    python vault_test_runner.py --smoke --contracts
"""

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from vault_errors import wrap_main

SCRIPTS_DIR = Path(__file__).parent
PYTHON = sys.executable

# ──────────────────────────────────────────────────────────────────────────────
# Tool registry — (script_name, required_args_for_happy_path)
# ──────────────────────────────────────────────────────────────────────────────

# Tools that take --folder --title --content as minimum args
_WRITE_ARGS = ["--folder", "01_Projects/smoke", "--title", "SmokTest", "--content", "## Test\n\nSmoke test content.\n\nAdditional detail for minimum content gate.\n"]

TOOL_CONTRACTS: List[Dict[str, Any]] = [
    # Group 1 — Core
    {"name": "vault_write",           "args": _WRITE_ARGS, "required_ok_fields": ["path"]},
    {"name": "vault_read",            "args": ["--path", "01_Projects/smoke/smoktest.md"], "required_ok_fields": ["path"]},
    {"name": "vault_search",          "args": ["--query", "smoke"], "required_ok_fields": ["results"]},
    {"name": "vault_list",            "args": ["--folder", "01_Projects"], "required_ok_fields": ["notes"]},
    {"name": "vault_append",          "args": ["--path", "01_Projects/smoke/smoktest.md", "--content", "appended"], "required_ok_fields": ["path"]},
    {"name": "vault_diff",            "args": ["--path", "01_Projects/smoke/smoktest.md"], "required_ok_fields": ["path", "changed"]},
    {"name": "vault_merge",           "args": ["--action", "detect"], "required_ok_fields": ["action"]},
    # Group 2 — Observability
    {"name": "vault_log_error",       "args": ["--type", "error", "--title", "Smoke Error", "--description", "test error"], "required_ok_fields": []},
    # Group 3 — Patterns
    {"name": "vault_pattern_save",    "args": ["--project", "smoke", "--name", "smoke-pat", "--type", "code", "--status", "implementado"], "required_ok_fields": ["path"]},
    {"name": "vault_pattern_list",    "args": [], "required_ok_fields": ["patterns"]},
    # Group 4 — Diagrams
    {"name": "vault_diagram_save",    "args": ["--project", "smoke", "--title", "test-diag", "--diagram_type", "mermaid", "--category", "flow", "--content", "graph TD\n  A-->B"], "required_ok_fields": ["path"]},
    {"name": "vault_relation_add",    "args": ["--project", "smoke", "--from", "A", "--to", "B", "--relation_type", "uses"], "required_ok_fields": ["path"]},
    # Group 5 — Knowledge
    {"name": "vault_knowledge_save",  "args": ["--title", "smoke-kw", "--category", "concept", "--content", "## Concept\n\nDesc."], "required_ok_fields": ["path"]},
    {"name": "vault_knowledge_get",   "args": ["--query", "smoke-kw"], "required_ok_fields": ["results", "query", "total"]},
    # Group 6 — Vault health
    {"name": "vault_audit",           "args": [], "required_ok_fields": ["healthScore"]},
    {"name": "vault_validate",        "args": ["--path", "01_Projects/smoke/smoktest.md", "--check", "frontmatter"], "required_ok_fields": []},
    {"name": "vault_graph",           "args": [], "required_ok_fields": []},
    # Group 7 — Runbooks
    {"name": "vault_runbook_save",    "args": ["--project", "smoke", "--title", "smoke-rb", "--trigger", "smoke test", "--category", "setup", "--steps", '[{"step":"step1"}]'], "required_ok_fields": ["path"]},
    {"name": "vault_runbook_log",     "args": ["--path", "08_Runbooks/setup/smoke-smoke-rb.md", "--outcome", "success", "--notes", "ran fine"], "required_ok_fields": []},
    # Group 8 — Infrastructure
    {"name": "vault_infra_save",      "args": ["--name", "smoke-srv", "--type", "server", "--description", "test", "--config", '{"host":"localhost"}'], "required_ok_fields": ["path"]},
    {"name": "vault_infra_map",       "args": [], "required_ok_fields": ["path", "nodesTotal"]},
    {"name": "vault_env_save",        "args": ["--project", "smoke", "--environment", "dev", "--vars", '[{"name":"DEBUG","description":"Enable debug mode","required":false,"sensitive":false,"provider":"env-file"}]'], "required_ok_fields": ["path"]},
    # Group 9 — Migration
    {"name": "vault_migrate_docs",    "args": ["--source_path", "../10_Migrated", "--project", "smoke"], "required_ok_fields": []},
    {"name": "vault_migrate_rollback","args": ["--report_path", "10_Migrated/_report-smoke.md"], "required_ok_fields": []},
    # Group 10 — Timeline
    {"name": "vault_timeline",        "args": ["--project", "smoke"], "required_ok_fields": ["query"]},
    # Group 11 — Project view
    {"name": "vault_project_status",  "args": ["--project", "smoke", "--status", "en_desarrollo", "--summary", "smoke"], "required_ok_fields": ["path"]},
    {"name": "vault_project_overview","args": ["--project", "smoke"], "required_ok_fields": ["path"]},
    # Group 12 — Code
    {"name": "vault_code_module",     "args": ["--project", "smoke", "--file_path", "src/smoke.py", "--description", "smoke module"], "required_ok_fields": ["path"]},
    {"name": "vault_code_relation",   "args": ["--project", "smoke", "--from_file", "src/smoke.py", "--to_file", "src/main.py", "--relation_type", "imports"], "required_ok_fields": []},
    {"name": "vault_code_map",        "args": ["--project", "smoke"], "required_ok_fields": ["path"]},
    {"name": "vault_code_query",      "args": ["--project", "smoke", "--list"], "required_ok_fields": []},
    # Group 13 — Backups
    {"name": "vault_backup",          "args": ["--label", "smoke-bk"], "required_ok_fields": ["name", "path"]},
    {"name": "vault_backup_list",     "args": [], "required_ok_fields": ["total"]},
    # vault_restore omitted: requires --confirm true which would destroy the temp vault
    # Group 14 — Security
    {"name": "vault_security_scan",   "args": ["--path", "01_Projects/smoke"], "required_ok_fields": ["riskLevel"]},
    # Group 15 — Indexes
    {"name": "vault_section_index",   "args": ["--folder", "01_Projects"], "required_ok_fields": ["path"]},
    {"name": "vault_master_index",    "args": [], "required_ok_fields": ["path"]},
    {"name": "vault_reindex",         "args": [], "required_ok_fields": ["indexed"]},
    # Group 16 — Bibliography
    {"name": "vault_bibliography_save","args": ["--title", "Smoke Ref", "--url", "https://example.com", "--summary", "test ref", "--source_type", "web"], "required_ok_fields": ["path"]},
    # Group 17 — Drift
    {"name": "vault_drift_detect",    "args": ["--path", ".", "--project", "smoke", "--mode", "snapshot"], "required_ok_fields": ["mode"]},
    # Group 18 — Flows
    {"name": "vault_flow_save",       "args": ["--project", "smoke", "--name", "smoke-flow", "--type", "workflow", "--description", "test flow", "--mermaid", "flowchart TD\n  A-->B"], "required_ok_fields": ["path"]},
    # Group 19 — Requirements
    {"name": "vault_requirement_save","args": ["--project", "smoke", "--title", "REQ-01", "--description", "Must smoke", "--type", "functional", "--priority", "must-have"], "required_ok_fields": ["path"]},
    # Group 20 — Tests
    {"name": "vault_test_save",       "args": ["--project", "smoke", "--title", "TC-01", "--test_type", "unit", "--description", "Smoke test case"], "required_ok_fields": ["path"]},
    # Group 21 — AI Governance
    {"name": "vault_ai_decision",     "args": ["--project", "smoke", "--title", "smoke-ai", "--decision_type", "architectural", "--description", "smoke decision", "--rationale", "testing"], "required_ok_fields": ["path"]},
    # Group 22 — Versioning
    {"name": "vault_standard_upgrade","args": ["--check"], "required_ok_fields": []},
    # Group 23 — Change Log
    {"name": "vault_change_log",      "args": ["--action", "created", "--path", "01_Projects/smoke/smoktest.md", "--reason", "smoke test"], "required_ok_fields": ["id"]},
]

# Error-path test cases: (script, args, expected_ok_false)
ERROR_CASES: List[Dict[str, Any]] = [
    {"name": "vault_write",        "args": ["--folder", "01_Projects"], "desc": "missing --title"},
    {"name": "vault_write",        "args": ["--folder", "01_Projects/smoke", "--title", "SmokTest", "--content", "First line.\nSecond line.\nThird line.\n- valid bullet\n- \n- \n- \n- \n"], "desc": "AP-20 empty bullets", "expect_error_code": "content_empty_list"},
    {"name": "vault_read",         "args": ["--path", "nonexistent/path.md"], "desc": "file not found"},
    {"name": "vault_append",       "args": ["--path", "nonexistent.md", "--content", "x"], "desc": "file not found"},
    {"name": "vault_project_status","args": ["--project", "smoke", "--status", "invalid_status", "--summary", "x"], "desc": "invalid status"},
    {"name": "vault_relation_add", "args": ["--project", "smoke", "--from", "A", "--to", "B", "--relation_type", "invalid_type"], "desc": "invalid relation_type"},
    {"name": "vault_change_log",   "args": ["--action", "deleted", "--path", "test.md"], "desc": "missing --reason"},
]


# ──────────────────────────────────────────────────────────────────────────────
# Runner helpers
# ──────────────────────────────────────────────────────────────────────────────

def _run_script(script: str, args: List[str], vault_root: Optional[Path] = None, timeout: int = 30) -> Tuple[int, str, str]:
    """Run a vault script and return (returncode, stdout, stderr)."""
    script_path = SCRIPTS_DIR / f"{script}.py"
    cmd = [PYTHON, str(script_path)] + args
    env = os.environ.copy()
    if vault_root:
        # Scripts auto-detect vault root from __file__ location; no env override needed.
        pass
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(SCRIPTS_DIR),
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"TIMEOUT after {timeout}s"
    except Exception as e:
        return 1, "", str(e)


def _parse_json_output(stdout: str) -> Optional[Dict]:
    text = stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try last non-empty line
        for line in reversed(text.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except Exception:
                    pass
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Smoke mode
# ──────────────────────────────────────────────────────────────────────────────

def run_smoke() -> Dict[str, Any]:
    """Verify all scripts compile and --help returns 0."""
    scripts = sorted(p.stem for p in SCRIPTS_DIR.glob("vault_*.py") if p.stem != "vault_errors")
    passed, failed, errors = 0, 0, []

    for name in scripts:
        # Syntax check via compile
        path = SCRIPTS_DIR / f"{name}.py"
        try:
            source = path.read_text(encoding="utf-8")
            compile(source, str(path), "exec")
        except SyntaxError as e:
            failed += 1
            errors.append({"tool": name, "test": "syntax", "error": str(e)})
            continue

        # --help must exit 0
        rc, out, err = _run_script(name, ["--help"], timeout=10)
        if rc == 0:
            passed += 1
        else:
            failed += 1
            errors.append({"tool": name, "test": "--help", "returncode": rc, "stderr": err[:200]})

    return {
        "ok": failed == 0,
        "mode": "smoke",
        "total": len(scripts),
        "passed": passed,
        "failed": failed,
        "errors": errors,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Contracts mode
# ──────────────────────────────────────────────────────────────────────────────

def run_contracts() -> Dict[str, Any]:
    """Happy-path test for each tool in a temp vault."""
    vault_dir = Path(tempfile.mkdtemp(prefix="vault_smoke_"))
    try:
        return _run_contracts_in_vault(vault_dir)
    finally:
        shutil.rmtree(vault_dir, ignore_errors=True)


def _run_contracts_in_vault(vault_dir: Path) -> Dict[str, Any]:
    # Create minimal vault structure
    for folder in [
        "00_System", "01_Projects", "02_Observability/errors", "03_Decisions",
        "04_Sessions", "05_Patterns", "06_Diagrams/entity", "07_Knowledge",
        "08_Runbooks", "09_Infrastructure", "10_Migrated", "11_Code",
        "12_Bibliography", "13_Flows", "14_Requirements", "15_Tests",
        "16_AI_Governance", "99_Index",
    ]:
        (vault_dir / folder).mkdir(parents=True, exist_ok=True)

    # Write standard-version.json
    (vault_dir / "00_System" / "standard-version.json").write_text(
        json.dumps({"version": 25, "profile": "full", "upgradedAt": "2026-01-01T00:00:00Z"}),
        encoding="utf-8"
    )

    # Stub migration report for vault_migrate_rollback contract test
    (vault_dir / "10_Migrated" / "_report-smoke.md").write_text(
        "---\ntitle: smoke migration report\nid: smoke-report\n---\n\n"
        "## Archivos Distribuidos\n\n"
        "| Archivo | Destino | Relevancia |\n|---|---|---|\n"
        "| `note.md` | [[01_Projects/smoke/note.md]] | high |\n\n"
        "## Stubs Creados\n\n"
        "- `note.md` → [[10_Migrated/note.md]]\n",
        encoding="utf-8",
    )

    passed, failed, skipped, errors = 0, 0, 0, []

    # Patch scripts to use the temp vault by temporarily rewriting VAULT_ROOT.
    # Simpler: set env var VAULT_SMOKE_ROOT and patch scripts at test time.
    # Since scripts use Path(__file__).parent.parent, we symlink or copy scripts into vault_dir/scripts.
    # Easiest: copy scripts into temp vault, run from there.
    tmp_scripts = vault_dir / "scripts"
    shutil.copytree(str(SCRIPTS_DIR), str(tmp_scripts))

    env = os.environ.copy()

    for tc in TOOL_CONTRACTS:
        name = tc["name"]
        args = tc["args"]
        required_fields = tc.get("required_ok_fields", [])

        script_path = tmp_scripts / f"{name}.py"
        if not script_path.exists():
            skipped += 1
            continue

        cmd = [PYTHON, str(script_path)] + args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                cwd=str(tmp_scripts),
                env=env,
            )
            stdout = result.stdout.strip()
            data = _parse_json_output(stdout)

            if data is None:
                failed += 1
                errors.append({"tool": name, "test": "json_output", "error": "not valid JSON", "stdout": stdout[:300], "stderr": result.stderr[:200]})
                continue

            if not data.get("ok"):
                failed += 1
                errors.append({"tool": name, "test": "ok_true", "error": f"ok={data.get('ok')}", "error_code": data.get("error_code"), "message": data.get("message", "")[:200]})
                continue

            missing = [f for f in required_fields if f not in data]
            if missing:
                failed += 1
                errors.append({"tool": name, "test": "required_fields", "missing": missing, "got_keys": list(data.keys())})
                continue

            passed += 1

        except subprocess.TimeoutExpired:
            failed += 1
            errors.append({"tool": name, "test": "timeout", "error": "exceeded 30s"})
        except Exception as e:
            failed += 1
            errors.append({"tool": name, "test": "exception", "error": str(e)})

    return {
        "ok": failed == 0,
        "mode": "contracts",
        "total": len(TOOL_CONTRACTS),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "errors": errors,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Errors mode
# ──────────────────────────────────────────────────────────────────────────────

def run_errors() -> Dict[str, Any]:
    """Error-path tests: invalid args must return {ok:false}."""
    vault_dir = Path(tempfile.mkdtemp(prefix="vault_errtest_"))
    try:
        return _run_errors_in_vault(vault_dir)
    finally:
        shutil.rmtree(vault_dir, ignore_errors=True)


def _run_errors_in_vault(vault_dir: Path) -> Dict[str, Any]:
    for folder in ["00_System", "01_Projects", "02_Observability/errors"]:
        (vault_dir / folder).mkdir(parents=True, exist_ok=True)

    tmp_scripts = vault_dir / "scripts"
    shutil.copytree(str(SCRIPTS_DIR), str(tmp_scripts))

    passed, failed, errors = 0, 0, []

    for tc in ERROR_CASES:
        name = tc["name"]
        args = tc["args"]
        desc = tc["desc"]
        expect_code = tc.get("expect_error_code")

        script_path = tmp_scripts / f"{name}.py"
        if not script_path.exists():
            continue

        cmd = [PYTHON, str(script_path)] + args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                cwd=str(tmp_scripts),
            )
            stdout = result.stdout.strip()
            data = _parse_json_output(stdout)

            # argparse errors exit with code 2 and no JSON — that's fine
            if result.returncode == 2 and not data:
                passed += 1
                continue

            if data and data.get("ok") is False:
                if expect_code and data.get("error_code") != expect_code:
                    failed += 1
                    errors.append({"tool": name, "test": desc, "expected_error_code": expect_code, "got": data.get("error_code")})
                    continue
                passed += 1
            else:
                failed += 1
                errors.append({"tool": name, "test": desc, "error": "expected ok:false but got ok:true or non-JSON", "stdout": stdout[:300]})

        except subprocess.TimeoutExpired:
            failed += 1
            errors.append({"tool": name, "test": desc, "error": "timeout"})
        except Exception as e:
            failed += 1
            errors.append({"tool": name, "test": desc, "error": str(e)})

    return {
        "ok": failed == 0,
        "mode": "errors",
        "total": len(ERROR_CASES),
        "passed": passed,
        "failed": failed,
        "errors": errors,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_test_runner — Test suite para las 53 vault tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modos:
  --smoke     Verifica sintaxis e --help de cada script (~30s)
  --contracts Happy-path de cada tool en vault temporal (~3min)
  --errors    Error-paths: args invalidos retornan ok:false (~3min)

Ejemplos:
  python vault_test_runner.py --smoke
  python vault_test_runner.py --contracts
  python vault_test_runner.py --smoke --contracts --errors
""",
    )
    parser.add_argument("--smoke",     action="store_true", help="Run syntax + --help checks")
    parser.add_argument("--contracts", action="store_true", help="Run happy-path contract tests")
    parser.add_argument("--errors",    action="store_true", help="Run error-path tests")
    parser.add_argument("--json",      action="store_true", help="Output raw JSON (no pretty print summary)")

    args = parser.parse_args()

    if not (args.smoke or args.contracts or args.errors):
        parser.error("Specify at least one mode: --smoke, --contracts, or --errors")

    all_results = {}
    overall_ok = True
    t0 = time.time()

    if args.smoke:
        if not args.json:
            print("Running smoke tests...", flush=True)
        r = run_smoke()
        all_results["smoke"] = r
        if not r["ok"]:
            overall_ok = False

    if args.contracts:
        if not args.json:
            print("Running contract tests (this may take a few minutes)...", flush=True)
        r = run_contracts()
        all_results["contracts"] = r
        if not r["ok"]:
            overall_ok = False

    if args.errors:
        if not args.json:
            print("Running error-path tests...", flush=True)
        r = run_errors()
        all_results["errors"] = r
        if not r["ok"]:
            overall_ok = False

    elapsed = round(time.time() - t0, 1)
    summary = {"ok": overall_ok, "elapsed_s": elapsed, "results": all_results}

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        for mode, r in all_results.items():
            status = "PASS" if r["ok"] else "FAIL"
            print(f"\n[{status}] {mode}: {r.get('passed', 0)} passed, {r.get('failed', 0)} failed, {r.get('skipped', 0)} skipped")
            for e in r.get("errors", []):
                print(f"  - {e.get('tool','?')} / {e.get('test','?')}: {e.get('error', e.get('error_code', ''))}")
        print(f"\nTotal elapsed: {elapsed}s — {'ALL PASSED' if overall_ok else 'FAILURES DETECTED'}")
        print(json.dumps(summary, indent=2, ensure_ascii=False))

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_test_runner"))
