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
#: Estado de EJECUCION de un vault vivo: no es contenido. El directorio
#: `.locks/` y los ficheros `*.lock` los crea y retira el proceso que escribe;
#: una copia que los arrastre falla cuando desaparecen a mitad (WinError 3 /
#: ENOENT), no por el contenido. Misma clase que el defecto R13-03b del
#: backup, ya corregido alli: aqui se centraliza para que TODOS los sitios
#: que copian un vault vivo usen el MISMO conjunto.
ESTADO_DE_EJECUCION = (".locks", "*.lock")


def copiar_vault(origen: Path, destino: Path, *,
                  ignore_extra: tuple[str, ...] = (),
                  symlinks: bool = False) -> Path:
    """Copia un vault ignorando el estado de ejecucion (locks).

    Un solo sitio decide que se ignora: si cada copia inventa su patron, la
    carrera reaparece (medido el 2026-10-27: `test_durabilidad_caracterizacion`
    ignoraba `*.lock` pero no `.locks/`, y la corrida 40464661392 loDemonstró
    en Windows 3.10 con `shutil.Error`).
    """
    patrones = tuple(ESTADO_DE_EJECUCION) + tuple(ignore_extra)
    shutil.copytree(origen, destino,
                    ignore=shutil.ignore_patterns(*patrones),
                    symlinks=symlinks)
    return destino


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
        target.write_bytes(("---\n"
            f"title: Fixture incomplete {number}\n"
            "---\n\n"
            f"[[{health['broken_link']}]]\n").encode("utf-8"))
    for number in range(health["frontmatterless_notes"]):
        target = root / "07_Knowledge" / f"fixture-raw-{number:02d}.md"
        target.write_bytes((f"Synthetic fixture note {number} without frontmatter.\n").encode("utf-8"))


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
    # El índice es una proyección del disco (AP-47). Las tools de arriba
    # escriben notas —`00_System/data-framework.md`, `00_System/
    # tool-contracts.md`, `99_Index/tag-index.md`— y lo hacen DESPUÉS del
    # reindex: el sandbox quedaba con tres notas en disco y ninguna indexada,
    # y la puerta de contención de la CI (`vault_norms --audit --root
    # vault-sandbox --strict`) lo mide. Se reindexa otra vez al final: el
    # primero deja el índice disponible para las tools que lo leen, el
    # segundo lo deja reflejando el disco entero.
    _run(target, "vault_reindex.py", "--graph")

    missing = [name for name in DERIVED_FILES if not (target / "00_System" / name).is_file()]
    if missing:
        raise RuntimeError(f"bootstrap no generó artefactos: {missing}")
    return target


def _semilla_intacta(target: Path) -> bool:
    """Cada nota de la semilla está, y byte a byte como la semilla la escribe.

    Hasta 2026-10-01 bastaba con que existiera `adr-001-mcp-transport.md`: un
    sandbox de una siembra anterior —con otro `adr-001` y sin las notas
    `mcp-transport-*`— se daba por listo, no se reconstruía, y
    `test_context_memory` fallaba en el repo y pasaba en un worktree limpio.
    Un resultado que depende de restos ignorados no mide el código.
    """
    for note in _seed()["parser_notes"]:
        path = target / note["path"]
        if not path.is_file() or path.read_bytes() != note["content"].encode("utf-8"):
            return False
    return True


def ready(root: Path | None = None) -> bool:
    target = _assert_target(root or default_root())
    return (
        _semilla_intacta(target)
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
