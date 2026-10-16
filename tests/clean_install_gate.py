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
QUERY_MODULE = "vault_toolkit.operations.vault_query_parse"
QUERY_ARGS = (
    "--query",
    "que decidimos sobre el transporte MCP",
    "--plan-only",
)
DIST_NAME = "vault-obsidian-architecture"


def _fail(message: str) -> None:
    raise AssertionError(message)


def _registros_de_distribucion():
    """Los registros con los que se juzga la wheel, leídos del repo (AP-44).

    Lanzado como `python tests/clean_install_gate.py`, `sys.path[0]` es
    `tests/`: sin la raíz delante, `import vault` lo resolvía la instalación
    global de `site-packages`, y la gate medía la wheel contra el registro de
    otra versión —o caía con un ImportError que no era del producto—.
    """
    for ruta in (REPO_ROOT / "scripts", REPO_ROOT):
        if str(ruta) in sys.path:
            sys.path.remove(str(ruta))
        sys.path.insert(0, str(ruta))
    from vault.meta_toolkit.distribucion import clasificar_tools
    from vault_servicio import NATURALEZAS
    from vault_mcp_catalog import TOOLS_CATALOG
    return clasificar_tools, NATURALEZAS, TOOLS_CATALOG


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


def _mcp_instalado(vault: Path, runtime: Path, work: Path, env: dict[str, str]) -> dict:
    """`vault mcp-path` y una sesión stdio contra el servidor instalado.

    Sin Node se declara omitido en el informe en vez de darse por ejercido.
    """
    info = _json_output(_run([str(vault), "mcp-path"], cwd=work, env=env), "vault mcp-path")
    server = Path(info.get("server", ""))
    if "site-packages" not in server.parts or not server.is_file():
        _fail(f"vault mcp-path no apunta a la instalación: {info}")
    if shutil.which("node") is None:
        return {"server": str(server), "stdio": "omitido: node no está en el PATH"}
    mensajes = [
        {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "clean-install-gate", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "vault_query_parse", "arguments": {"query": QUERY_ARGS[1]}}},
    ]
    sesion = subprocess.run(
        ["node", str(server)], input="".join(json.dumps(m) + "\n" for m in mensajes),
        cwd=work, env={**env, **info["config"]["env"], "VAULT_ROOT": str(runtime)},
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    )
    respuestas = {}
    for linea in sesion.stdout.splitlines():
        try:
            m = json.loads(linea)
        except json.JSONDecodeError:
            continue
        if "id" in m:
            respuestas[m["id"]] = m
    try:
        nombres = {t["name"] for t in respuestas[1]["result"]["tools"]}
        payload = json.loads(respuestas[2]["result"]["content"][0]["text"])
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        _fail(f"sesión MCP instalada inválida ({exc}): {sesion.stderr[-2000:]}")
    if "vault_query_parse" not in nombres or payload.get("ok") is not True:
        _fail(f"el servidor MCP instalado no ejecutó la tool: {payload}")
    return {"server": str(server), "stdio": "ok", "tools": len(nombres)}


def main(*, gate: str = "CLEAN_INSTALL_GATE") -> int:
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
            "vault/ciclo_de_vida/producto.py",
            "vault/ciclo_de_vida/runtime-seed.json",
            "vault/meta_toolkit/tools-catalog.json",
            # P3: el servidor MCP viaja en la wheel; sin checkout no hay otro.
            "vault_toolkit/mcp/vault-mcp-server.mjs",
            "vault_toolkit/mcp/tools-catalog.json",
            "vault_toolkit/mcp/env-table.json",
        }
        forbidden_prefixes = ("scripts/", "tests/", "vault-sandbox/", ".git/", "build/")
        missing = sorted(required - members)
        forbidden = sorted(member for member in members if member.startswith(forbidden_prefixes))
        # v40.34: la gobernanza del estándar no viaja. La lista es la derivada
        # que lee el hook de build, no una copia.
        fuera = json.loads((REPO_ROOT / "empaquetado" / "fuera-de-la-wheel.json").read_text(encoding="utf-8"))
        forbidden += sorted(
            f"vault_toolkit/_impl/{m}.py" for m in fuera["modulos"]
            if f"vault_toolkit/_impl/{m}.py" in members
        )
        if missing or forbidden:
            _fail(f"wheel content invalid: missing={missing}, forbidden={forbidden}")

        create = _run([sys.executable, "-m", "venv", str(venv)], cwd=work, env=dict(os.environ))
        if create.returncode:
            _fail(f"venv creation failed:\n{create.stderr}")
        python = venv / "Scripts" / "python.exe" if os.name == "nt" else venv / "bin" / "python"
        vault = venv / "Scripts" / "vault.exe" if os.name == "nt" else venv / "bin" / "vault"
        install = _run([str(python), "-m", "pip", "install", str(wheel)], cwd=work, env=dict(os.environ))
        if install.returncode:
            _fail(f"wheel install failed:\n{install.stderr}\n{install.stdout}")

        clean_env = dict(os.environ)
        clean_env.pop("PYTHONPATH", None)
        # Un VAULT_ROOT de quien lanza el gate decidiría por el consumidor si
        # hay vault o no; la instalación limpia empieza sin ninguno.
        clean_env.pop("VAULT_ROOT", None)

        operations_members = sorted(m for m in members if m.startswith("vault_toolkit/operations/vault_") and m.endswith(".py"))
        if len(operations_members) == 0:
            _fail("wheel no tiene operaciones instaladas (0 encontradas)")

        # AP-47: la cifra sale del registro, no de una constante a mano.
        # El registro dice cuántas son distributable; el test mide el wheel.
        clasificar_tools, NATURALEZAS, TOOLS_CATALOG = _registros_de_distribucion()
        expected_dist = sum(1 for d in clasificar_tools(TOOLS_CATALOG, NATURALEZAS).values() if d.distributable)
        if len(operations_members) != expected_dist:
            _fail(f"wheel deberia tener {expected_dist} operaciones, tiene {len(operations_members)}")
        help_failing = []
        for member in operations_members:
            op_name = Path(member).stem
            result = _run(
                [str(python), "-m", f"vault_toolkit.operations.{op_name}", "--help"],
                cwd=work, env=clean_env,
            )
            if result.returncode != 0:
                help_failing.append(f"{op_name}(exit={result.returncode}): {result.stderr[:100]}")
        if help_failing:
            _fail(f"--help fallo en {len(help_failing)} ops: {help_failing[:3]}")

        run_help_failing = []
        for member in operations_members:
            op_name = Path(member).stem
            result = _run(
                [str(vault), "run", op_name, "--help"],
                cwd=work, env=clean_env,
            )
            if result.returncode != 0:
                run_help_failing.append(f"{op_name}(exit={result.returncode}): {result.stderr[:100]}")
        if run_help_failing:
            _fail(f"vault run --help fallo en {len(run_help_failing)} ops: {run_help_failing[:3]}")

        # La copia existe sólo para construir el artefacto. Suprimirla antes de
        # importar demuestra que la operación instalada no puede recaer en el
        # árbol fuente usado durante el build. Nunca toca el checkout activo.
        shutil.rmtree(source)
        if source.exists():
            _fail(f"temporary source tree still exists: {source}")

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

        # deuda #10: vault_norms_catalog viaja en la wheel y carga las normas en
        # paquete de vault_toolkit/normas/. Si no entraran, fallaría el import
        # de toda tool que lea el catálogo, no solo el de vault_norms.
        normas = _run(
            [str(python), "-I", "-c", (
                "import sys, vault_toolkit._impl as i; "
                "sys.path.insert(0, list(i.__path__)[0]); "
                "import vault_norms_catalog as c; "
                "assert c.NORMAS_EN_PAQUETE and all(c.norma_por_codigo(x) for x in c.NORMAS_EN_PAQUETE); "
                "print(c.RAIZ_NORMAS)"
            )],
            cwd=work,
            env=clean_env,
        )
        if normas.returncode or "vault_toolkit" not in normas.stdout:
            _fail(f"las normas en paquete no viajan en la wheel: {normas.stderr}\n{normas.stdout}")

        listed = _json_output(_run([str(vault), "tools", "list"], cwd=work, env=clean_env), "vault tools list")
        listed_by_name = {entry.get("name"): entry for entry in listed.get("tools", [])}
        if listed_by_name.get("vault_query_parse", {}).get("installed") is not True:
            _fail("vault tools list did not expose the installed operation")
        if listed_by_name.get("vault_read", {}).get("installed") is not True:
            _fail("vault tools list did not expose vault_read as installed")

        shown = _json_output(
            _run([str(vault), "tools", "show", "vault_query_parse"], cwd=work, env=clean_env),
            "vault tools show installed",
        )
        if shown.get("execution_module") != QUERY_MODULE or shown.get("installed") is not True:
            _fail(f"installed metadata not exposed by public CLI: {shown}")

        # AP-36 (2026-10-15): sin VAULT_ROOT la única raíz es el paquete
        # instalado, y ninguna tool la lee como si fuera el vault.
        sin_raiz = _run([str(vault), "run", "vault_query_parse", *QUERY_ARGS], cwd=work, env=clean_env)
        try:
            rechazo = json.loads(sin_raiz.stdout)
        except json.JSONDecodeError:
            rechazo = {}
        if sin_raiz.returncode != 7 or rechazo.get("error_code") != "VAULT_NOT_FOUND":
            _fail(f"vault run sin VAULT_ROOT no se negó: exit={sin_raiz.returncode} {sin_raiz.stdout}")
        public_run = _json_output(
            _run([str(vault), "run", "vault_query_parse", *QUERY_ARGS], cwd=work,
                 env={**clean_env, "VAULT_ROOT": str(work)}),
            "vault run installed",
        )
        if public_run.get("ok") is not True or public_run.get("plan", [{}])[0].get("tool") != "vault_search":
            _fail(f"unexpected public query payload: {public_run}")
        _product_error(
            _run([str(vault), "run", "vault_arch"], cwd=work, env=clean_env),
            label="vault run maintenance", code=5, state="not_runtime_operation",
        )
        _product_error(
            _run([str(vault), "run", "definitely_not_a_real_tool"], cwd=work, env=clean_env),
            label="vault run unknown", code=3, state="unknown_tool",
        )

        # Lifecycle: la misma instalación limpia crea, diagnostica, transporta
        # e inicializa de nuevo un runtime que vive fuera de venv y checkout.
        runtime = root / "consumer-runtime"
        created = _json_output(
            _run([str(vault), "init", str(runtime)], cwd=work, env=clean_env),
            "vault init",
        )
        if created.get("state") != "INIT_CREATED" or not (runtime / "00_System" / "standard-version.json").is_file():
            _fail(f"vault init did not create the minimum runtime: {created}")
        if {"scripts", "cli", "tests", ".git", "pyproject.toml"} & {p.name for p in runtime.rglob("*")}:
            _fail("runtime copied toolkit source")
        doctor = _json_output(_run([str(vault), "doctor", str(runtime)], cwd=work, env=clean_env), "vault doctor")
        status = _json_output(_run([str(vault), "status", str(runtime)], cwd=work, env=clean_env), "vault status")
        if not doctor.get("ok") or not status.get("ok"):
            _fail(f"lifecycle diagnosis failed: doctor={doctor}, status={status}")
        before = {str(p.relative_to(runtime)): p.read_bytes() for p in runtime.rglob("*") if p.is_file()}
        repeated = _json_output(_run([str(vault), "init", str(runtime)], cwd=work, env=clean_env), "vault init idempotent")
        after = {str(p.relative_to(runtime)): p.read_bytes() for p in runtime.rglob("*") if p.is_file()}
        if repeated.get("state") != "INIT_ALREADY_EXISTS" or after != before:
            _fail("vault init was not idempotent")
        moved = root / "moved-runtime"
        shutil.copytree(runtime, moved)
        moved_doctor = _json_output(_run([str(vault), "doctor", str(moved)], cwd=work, env=clean_env), "vault doctor moved runtime")
        if not moved_doctor.get("ok"):
            _fail(f"moved runtime is not portable: {moved_doctor}")

        mcp = _mcp_instalado(vault, runtime, work, clean_env)

        invocation = _run([str(python), "-I", "-m", QUERY_MODULE, *QUERY_ARGS], cwd=work,
                          env={**clean_env, "VAULT_ROOT": str(runtime)})
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
            "gate": gate,
            "wheel": wheel.name,
            "module_origin": str(module_path),
            "public_vault_executable": str(vault),
            "public_cli_origin": str(public_cli_path),
            "checkout_import_path_absent": True,
            "source_tree_physically_absent": True,
            "scripts_workaround_absent": True,
            "runtime_created": True,
            "doctor_ok": True,
            "status_ok": True,
            "idempotent": True,
            "runtime_external": True,
            "runtime_contains_toolkit_source": False,
            "mcp": mcp,
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
