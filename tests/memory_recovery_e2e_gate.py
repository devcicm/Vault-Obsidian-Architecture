#!/usr/bin/env python3
"""Prueba de producto: memoria recuperable entre procesos sin árbol fuente."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path

from clean_install_gate import DIST_NAME, REPO_ROOT, _copy_source, _run, _wheel_members


def _fail(message: str) -> None:
    raise AssertionError(message)


def _json(result: subprocess.CompletedProcess[str], label: str) -> dict:
    if result.returncode:
        _fail(f"{label} failed ({result.returncode}):\n{result.stderr}\n{result.stdout}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        _fail(f"{label} did not emit JSON: {exc}\n{result.stdout}")
    if not isinstance(payload, dict):
        _fail(f"{label} did not emit an object")
    return payload


def _invoke(command: list[str], *, cwd: Path, env: dict[str, str]) -> tuple[subprocess.CompletedProcess[str], int]:
    process = subprocess.Popen(command, cwd=cwd, env=env, text=True, encoding="utf-8",
                               errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr), process.pid


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="voa-memory-recovery-") as raw:
        root = Path(raw)
        source, artifacts, venv, work = root / "source", root / "artifact", root / "venv", root / "work"
        artifacts.mkdir()
        work.mkdir()
        _copy_source(source)
        build = _run([sys.executable, "-m", "build", "--wheel", "--outdir", str(artifacts)],
                     cwd=source, env=dict(os.environ))
        if build.returncode:
            _fail(f"wheel build failed:\n{build.stderr}\n{build.stdout}")
        wheels = list(artifacts.glob("*.whl"))
        if len(wheels) != 1:
            _fail(f"expected one wheel, got {wheels}")
        wheel = wheels[0]
        members = _wheel_members(wheel)
        with zipfile.ZipFile(wheel) as archive:
            metadata = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
            if "Requires-Dist: PyYAML" not in archive.read(metadata).decode("utf-8"):
                _fail("wheel does not declare its PyYAML dependency")
        required = {"vault/kernel/escritura.py", "vault/autoria/conocimiento.py",
                    "vault/autoria/knowledge_save.py", "vault/autoria/knowledge_get.py"}
        forbidden = [member for member in members if member.startswith(("scripts/", "tests/", "vault-sandbox/", ".git/"))]
        if required - members or forbidden:
            _fail(f"wheel content invalid: missing={sorted(required-members)}, forbidden={forbidden}")
        create = _run([sys.executable, "-m", "venv", str(venv)], cwd=work, env=dict(os.environ))
        if create.returncode:
            _fail(f"venv creation failed: {create.stderr}")
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        vault = venv / ("Scripts/vault.exe" if os.name == "nt" else "bin/vault")
        # El artefacto declara PyYAML como dependencia de frontmatter: la prueba
        # de instalación debe verificar el producto completo, no simular que
        # sus dependencias publicadas ya están presentes en el venv.
        install = _run([str(python), "-m", "pip", "install", str(wheel)], cwd=work, env=dict(os.environ))
        if install.returncode:
            _fail(f"wheel install failed:\n{install.stderr}")
        shutil.rmtree(source)
        if source.exists():
            _fail("temporary source tree still exists")
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        runtime = root / "consumer-runtime"
        if not vault.is_file():
            _fail("vault executable missing from venv")
        _json(_run([str(vault), "init", str(runtime)], cwd=work, env=env), "vault init")
        canary = f"MEMORY_CANARY_{uuid.uuid4().hex}"
        before, before_pid = _invoke([str(vault), "run", "vault_knowledge_get", "--root", str(runtime), "--query", canary], cwd=work, env=env)
        before_payload = _json(before, "recovery before write")
        if before_payload.get("total") != 0:
            _fail(f"canary existed before write: {before_payload}")
        write, write_pid = _invoke([str(vault), "run", "vault_knowledge_save", "--root", str(runtime), "--category", "concept", "--title", canary, "--content", f"Decisión {canary}: usar transporte Boreal-17."], cwd=work, env=env)
        written = _json(write, "memory write")
        note = runtime / str(written.get("path", ""))
        if not note.is_file():
            _fail(f"write did not produce Markdown: {written}")
        markdown = note.read_text(encoding="utf-8")
        if canary not in markdown:
            _fail("canary is absent from Markdown authority")
        recovered, recovery_pid = _invoke([str(vault), "run", "vault_knowledge_get", "--root", str(runtime), "--query", canary], cwd=work, env=env)
        result = _json(recovered, "recovery in new process")
        if (
            result.get("total") != 1
            or result.get("topMatch", {}).get("path") != written.get("path")
            or canary not in result.get("topContent", "")
        ):
            _fail(f"canary not recovered: {result}")
        moved = root / "moved-runtime"
        shutil.copytree(runtime, moved)
        _json(_run([str(vault), "doctor", str(moved)], cwd=work, env=env), "doctor moved runtime")
        moved_result, moved_pid = _invoke([str(vault), "run", "vault_knowledge_get", "--root", str(moved), "--query", canary], cwd=work, env=env)
        moved_payload = _json(moved_result, "recovery moved runtime")
        if (
            moved_payload.get("total") != 1
            or moved_payload.get("topMatch", {}).get("path") != written.get("path")
            or canary not in moved_payload.get("topContent", "")
        ):
            _fail(f"canary not recovered after runtime move: {moved_payload}")
        pids = (before_pid, write_pid, recovery_pid, moved_pid)
        if len(set(pids)) != len(pids):
            _fail(f"memory lifecycle reused a process: {pids}")
        database_files = sorted(
            path.relative_to(runtime).as_posix()
            for suffix in ("*.db", "*.sqlite", "*.sqlite3")
            for path in runtime.rglob(suffix)
        )
        if database_files:
            _fail(f"runtime introduced database storage: {database_files}")
        origin = _run([str(python), "-I", "-c", (
            "import importlib,json,pathlib,sys;"
            "mods={name:importlib.import_module(name) for name in "
            "['vault.kernel.escritura','vault.autoria.conocimiento','vault.autoria.knowledge_save','vault.autoria.knowledge_get']};"
            "print(json.dumps({'origins':{name:str(pathlib.Path(mod.__file__).resolve()) for name,mod in mods.items()},'sys_path':sys.path}))")], cwd=work, env=env)
        if origin.returncode:
            _fail(f"origin check failed: {origin.stderr}")
        paths = json.loads(origin.stdout)
        for value in paths["origins"].values():
            if "site-packages" not in Path(value).parts or str(REPO_ROOT.resolve()) in value:
                _fail(f"module origin is not installed: {value}")
        if any(str(REPO_ROOT.resolve()) in entry or str(source) in entry for entry in paths["sys_path"]):
            _fail(f"checkout leaked into sys.path: {paths['sys_path']}")
        print(json.dumps({
            "ok": True, "gate": "MEMORY_RECOVERY_E2E_GATE", "wheel": wheel.name,
            "canary": canary, "markdown_file": str(note),
            "canary_absent_before_write": True, "canary_present_after_write": True,
            "prewrite_process_separate": len({before_pid, write_pid, recovery_pid, moved_pid}) == 4,
            "write_process_separate": len({before_pid, write_pid, recovery_pid, moved_pid}) == 4,
            "recovery_process_separate": len({before_pid, write_pid, recovery_pid, moved_pid}) == 4,
            "moved_recovery_process_separate": len({before_pid, write_pid, recovery_pid, moved_pid}) == 4,
            "markdown_directly_readable": True, "recovery_after_runtime_move": True,
            "top_match_is_written_path": True,
            "source_tree_physically_absent": True, "checkout_import_path_absent": True,
            "write_service_origin": paths["origins"]["vault.autoria.conocimiento"],
            "write_entry_origin": paths["origins"]["vault.autoria.knowledge_save"],
            "recovery_entry_origin": paths["origins"]["vault.autoria.knowledge_get"],
            "atomic_primitive_origin": paths["origins"]["vault.kernel.escritura"],
            "atomic_primitive_origin_installed": True,
            "write_service_origin_installed": True, "write_entry_origin_installed": True,
            "recovery_entry_origin_installed": True,
            "runtime_contains_database": bool(database_files), "database_files": database_files,
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
