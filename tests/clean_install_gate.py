#!/usr/bin/env python3
"""Prueba de producto: wheel limpio sin importar el checkout fuente.

No se recoge como pytest (el nombre no empieza por ``test_``). Se ejecuta
explícitamente porque crear un venv y un wheel es una comprobación de producto,
no un unit test ordinario.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
QUERY_MODULE = "vault.consulta.query_parse"
QUERY_ARGS = (
    "--query",
    "que decidimos sobre el transporte MCP",
    "--plan-only",
)
DIST_NAME = "vault-obsidian-architecture"


def _fail(message: str) -> None:
    raise AssertionError(message)


def _copy_source(destination: Path) -> None:
    """Copia una fuente limpia para que el build no deje artefactos en git."""
    ignored = shutil.ignore_patterns(
        ".git", "build", "dist", "*.egg-info", "__pycache__", ".pytest_cache",
        "vault-sandbox", ".history", "vault-backups",
    )
    shutil.copytree(REPO_ROOT, destination, ignore=ignored)


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def _wheel_members(wheel: Path) -> set[str]:
    with zipfile.ZipFile(wheel) as archive:
        return set(archive.namelist())


def _json_output(result: subprocess.CompletedProcess[str], label: str) -> dict:
    if result.returncode:
        _fail(f"{label} failed ({result.returncode}):\n{result.stderr}\n{result.stdout}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        _fail(f"{label} did not emit JSON: {exc}")
    if not isinstance(payload, dict):
        _fail(f"{label} did not emit an object: {payload!r}")
    return payload


def _product_error(
    result: subprocess.CompletedProcess[str], *, label: str, code: int, state: str
) -> None:
    if result.returncode != code:
        _fail(f"{label} exit={result.returncode}, expected={code}: {result.stderr}")
    if "Traceback" in result.stderr:
        _fail(f"{label} leaked a traceback: {result.stderr}")
    try:
        payload = json.loads(result.stderr)
    except json.JSONDecodeError as exc:
        _fail(f"{label} did not emit controlled stderr JSON: {exc}")
    if payload.get("state") != state:
        _fail(f"{label} state={payload.get('state')!r}, expected={state!r}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="voa-clean-install-") as raw:
        root = Path(raw)
        source = root / "source"
        artifact_dir = root / "artifact"
        venv = root / "venv"
        work = root / "work"
        artifact_dir.mkdir()
        work.mkdir()
        _copy_source(source)

        build = _run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", str(artifact_dir)],
            cwd=source,
            env=dict(os.environ),
        )
        if build.returncode:
            _fail(f"wheel build failed:\n{build.stderr}\n{build.stdout}")
        wheels = list(artifact_dir.glob("*.whl"))
        if len(wheels) != 1:
            _fail(f"expected one wheel, got {wheels}")
        wheel = wheels[0]

        members = _wheel_members(wheel)
        required = {
            "vault/__init__.py",
            "vault/product_cli.py",
            "vault/consulta/__init__.py",
            "vault/consulta/query_parse.py",
            "vault/meta_toolkit/tools-catalog.json",
        }
        forbidden_prefixes = ("scripts/", "tests/", "vault-sandbox/", ".git/", "build/")
        missing = sorted(required - members)
        forbidden = sorted(member for member in members if member.startswith(forbidden_prefixes))
        if missing or forbidden:
            _fail(f"wheel content invalid: missing={missing}, forbidden={forbidden}")

        create = _run([sys.executable, "-m", "venv", str(venv)], cwd=work, env=dict(os.environ))
        if create.returncode:
            _fail(f"venv creation failed:\n{create.stderr}")
        python = venv / "Scripts" / "python.exe" if os.name == "nt" else venv / "bin" / "python"
        vault = venv / "Scripts" / "vault.exe" if os.name == "nt" else venv / "bin" / "vault"
        install = _run([str(python), "-m", "pip", "install", "--no-deps", str(wheel)], cwd=work, env=dict(os.environ))
        if install.returncode:
            _fail(f"wheel install failed:\n{install.stderr}\n{install.stdout}")

        # La copia existe sólo para construir el artefacto. Suprimirla antes de
        # importar demuestra que la operación instalada no puede recaer en el
        # árbol fuente usado durante el build. Nunca toca el checkout activo.
        shutil.rmtree(source)
        if source.exists():
            _fail(f"temporary source tree still exists: {source}")

        clean_env = dict(os.environ)
        clean_env.pop("PYTHONPATH", None)

        if not vault.is_file():
            _fail(f"public vault executable missing from venv: {vault}")
        installed_version = _run(
            [str(python), "-I", "-c", (
                "from importlib.metadata import version; "
                f"print(version({DIST_NAME!r}))"
            )],
            cwd=work,
            env=clean_env,
        )
        if installed_version.returncode:
            _fail(f"installed metadata version failed: {installed_version.stderr}")
        public_version = _run([str(vault), "--version"], cwd=work, env=clean_env)
        if public_version.returncode or public_version.stdout.strip() != installed_version.stdout.strip():
            _fail(f"vault --version differs from metadata: {public_version.stderr}\n{public_version.stdout}")

        listed = _json_output(_run([str(vault), "tools", "list"], cwd=work, env=clean_env), "vault tools list")
        listed_by_name = {entry.get("name"): entry for entry in listed.get("tools", [])}
        if listed_by_name.get("vault_query_parse", {}).get("installed") is not True:
            _fail("vault tools list did not expose the installed operation")
        if listed_by_name.get("vault_read", {}).get("installed") is not False:
            _fail("vault tools list did not expose legacy-only status")

        shown = _json_output(
            _run([str(vault), "tools", "show", "vault_query_parse"], cwd=work, env=clean_env),
            "vault tools show installed",
        )
        if shown.get("execution_module") != QUERY_MODULE or shown.get("installed") is not True:
            _fail(f"installed metadata not exposed by public CLI: {shown}")

        public_run = _json_output(
            _run([str(vault), "run", "vault_query_parse", *QUERY_ARGS], cwd=work, env=clean_env),
            "vault run installed",
        )
        if public_run.get("ok") is not True or public_run.get("plan", [{}])[0].get("tool") != "vault_search":
            _fail(f"unexpected public query payload: {public_run}")
        _product_error(
            _run([str(vault), "run", "vault_read"], cwd=work, env=clean_env),
            label="vault run legacy-only", code=4, state="known_not_installed",
        )
        _product_error(
            _run([str(vault), "run", "vault_arch"], cwd=work, env=clean_env),
            label="vault run maintenance", code=5, state="not_runtime_operation",
        )
        _product_error(
            _run([str(vault), "run", "definitely_not_a_real_tool"], cwd=work, env=clean_env),
            label="vault run unknown", code=3, state="unknown_tool",
        )

        invocation = _run([str(python), "-I", "-m", QUERY_MODULE, *QUERY_ARGS], cwd=work, env=clean_env)
        if invocation.returncode:
            _fail(f"installed operation failed:\n{invocation.stderr}\n{invocation.stdout}")
        try:
            payload = json.loads(invocation.stdout)
        except json.JSONDecodeError as exc:
            _fail(f"installed operation did not emit JSON: {exc}")
        if payload.get("ok") is not True or payload.get("plan", [{}])[0].get("tool") != "vault_search":
            _fail(f"unexpected query payload: {payload}")

        origin = _run(
            [str(python), "-I", "-c", (
                "import json, pathlib, sys, vault.consulta.query_parse as module, vault.product_cli as cli; "
                "print(json.dumps({'module': str(pathlib.Path(module.__file__).resolve()), "
                "'public_cli': str(pathlib.Path(cli.__file__).resolve()), "
                "'sys_path': sys.path}))"
            )],
            cwd=work,
            env=clean_env,
        )
        if origin.returncode:
            _fail(f"module origin check failed:\n{origin.stderr}")
        report = json.loads(origin.stdout)
        module_path = Path(report["module"])
        public_cli_path = Path(report["public_cli"])
        source_paths = {REPO_ROOT.resolve(), source.resolve()}
        if "site-packages" not in module_path.parts or any(
            path == module_path or path in module_path.parents for path in source_paths
        ):
            _fail(f"module was not loaded from site-packages: {module_path}")
        if "site-packages" not in public_cli_path.parts or any(
            path == public_cli_path or path in public_cli_path.parents for path in source_paths
        ):
            _fail(f"public CLI was not loaded from site-packages: {public_cli_path}")
        if any(str(path) in entry for path in source_paths for entry in report["sys_path"]):
            _fail(f"source path leaked into isolated sys.path: {report['sys_path']}")

        print(json.dumps({
            "ok": True,
            "gate": "CLEAN_INSTALL_GATE",
            "wheel": wheel.name,
            "module_origin": str(module_path),
            "public_vault_executable": str(vault),
            "public_cli_origin": str(public_cli_path),
            "checkout_import_path_absent": True,
            "source_tree_physically_absent": True,
            "scripts_workaround_absent": True,
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
