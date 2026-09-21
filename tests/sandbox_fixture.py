"""Bootstrap reproducible del único runtime de pruebas del estándar.

El contenido del sandbox es runtime ignorado; esta utilidad lo reconstruye desde
``vault_init``, una semilla versionada mínima y generadores canónicos. No copia
ningún vault local de quien ejecuta la suite.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_PATH = Path(__file__).resolve().parent / "fixtures" / "sandbox-seed.json"
CANONICAL_SPEC = REPO_ROOT / "vault-sandbox" / "00_System" / "tool-spec.json"
DERIVED_FILES = (
    "data-framework.json",
    "norm-registry.json",
    "data-fundamentals.json",
    "tool-contracts.json",
    "tag-registry.json",
)


def default_root() -> Path:
    return REPO_ROOT / "vault-sandbox"


def _assert_target(root: Path) -> Path:
    resolved = root.resolve()
    if resolved.name != "vault-sandbox":
        raise ValueError("el fixture solo acepta una raíz llamada vault-sandbox")
    return resolved


def _seed() -> dict[str, Any]:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def _run(root: Path, script: str, *args: str) -> None:
    env = {
        **os.environ,
        "VAULT_ROOT": str(root),
        "VAULT_STRICT_ROOT": "1",
        "VAULT_VOICE": "0",
        "PYTHONIOENCODING": "utf-8",
    }
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / script), *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    if result.returncode:
        raise RuntimeError(f"{script} falló: {result.stderr[-1000:] or result.stdout[-1000:]}")


def _write_seed(root: Path) -> None:
    seed = _seed()
    for note in seed["parser_notes"]:
        target = root / note["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(note["content"].encode("utf-8"))

    health = seed["health_fixture"]
    for number in range(health["incomplete_notes"]):
        target = root / "07_Knowledge" / f"fixture-incomplete-{number:02d}.md"
        target.write_text(
            "---\n"
            f"title: Fixture incomplete {number}\n"
            "---\n\n"
            f"[[{health['broken_link']}]]\n",
            encoding="utf-8",
            newline="\n",
        )
    for number in range(health["frontmatterless_notes"]):
        target = root / "07_Knowledge" / f"fixture-raw-{number:02d}.md"
        target.write_text(
            f"Synthetic fixture note {number} without frontmatter.\n",
            encoding="utf-8",
            newline="\n",
        )


def clean(root: Path | None = None, *, preserve_contract: bool = True) -> None:
    target = _assert_target(root or default_root())
    if not target.exists():
        return
    if not preserve_contract:
        shutil.rmtree(target)
        return
    for child in target.iterdir():
        if child.name == "00_System":
            for system_child in child.iterdir():
                if system_child.name != "tool-spec.json":
                    if system_child.is_dir():
                        shutil.rmtree(system_child)
                    else:
                        system_child.unlink()
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def bootstrap(root: Path | None = None) -> Path:
    target = _assert_target(root or default_root())
    # En la raíz por defecto el contrato versionado vive dentro del propio
    # sandbox. Se lee antes de limpiar: es fuente canónica trackeada, no estado
    # runtime que deba sobrevivir al bootstrap.
    contract = CANONICAL_SPEC.read_bytes()
    clean(target, preserve_contract=False)
    (target / "00_System").mkdir(parents=True, exist_ok=True)
    (target / "00_System" / "tool-spec.json").write_bytes(contract)

    _run(target, "vault_init.py", "--no-audit")
    _write_seed(target)
    _run(target, "vault_reindex.py", "--graph")
    _run(target, "vault_fundamentals.py", "--framework")
    _run(target, "vault_fundamentals.py")
    _run(target, "vault_norms.py", "--rebuild")
    _run(target, "vault_compact_contracts.py")
    _run(target, "vault_quality_check.py")
    _run(target, "vault_tags.py")

    missing = [name for name in DERIVED_FILES if not (target / "00_System" / name).is_file()]
    if missing:
        raise RuntimeError(f"bootstrap no generó artefactos: {missing}")
    return target


def ready(root: Path | None = None) -> bool:
    target = _assert_target(root or default_root())
    return (
        (target / "03_Decisions" / "adr-001-mcp-transport.md").is_file()
        and (target / "00_System" / "vault-commands.md").is_file()
        and all((target / "00_System" / name).is_file() for name in DERIVED_FILES)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="fixture reproducible de vault-sandbox")
    parser.add_argument("--root", type=Path, default=default_root())
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.bootstrap:
        bootstrap(args.root)
    elif args.clean:
        clean(args.root)
    elif args.check:
        return 0 if ready(args.root) else 1
    else:
        parser.error("elige --bootstrap, --clean o --check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
