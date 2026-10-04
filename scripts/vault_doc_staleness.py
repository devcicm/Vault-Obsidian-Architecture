#!/usr/bin/env python3
"""
vault_doc_staleness — verifica que los artefactos derivados existen y son válidos.

Comprueba que los JSON derivados de los catálogos Python existen, contienen JSON
válido y no están huérfanos (existencia vs. contenido obsoleto).

    python vault_doc_staleness.py --check      # informe sin exit code
    python vault_doc_staleness.py --check --strict  # exit 1 si falta alguno
    python vault_doc_staleness.py --regenerar  # ejecuta el productor de lo que falte

Los artefactos y su productor están en ``ARTIFACTS``, y de ahí salen el informe,
la pista ``fix`` y ``--regenerar``: hasta aquí la pista era una segunda lista
escrita a mano que ya omitía ``data-fundamentals.json`` (AP-47).

La carpeta se resuelve al usarse con ``vault_io.get_vault_root()``, no al
importar desde ``__file__`` (AP-49): congelada, un ``VAULT_ROOT`` o un
``set_vault_root()`` posteriores medían otro vault sin avisar.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from vault_errors import emit_error, wrap_main
from vault_io import get_vault_root

SCRIPTS_DIR = Path(__file__).resolve().parent

# artefacto → argv del productor (script + flags), o None si no se regenera:
# `standard-version.json` lo escribe `vault_init` al crear el vault, y
# rehacerlo es una migración (`vault_standard_upgrade`), no una derivación.
# El orden es el de dependencia: `vault_compact_contracts` lee la versión.
ARTIFACTS = {
    "data-framework.json": ("vault_fundamentals.py", "--framework"),
    "norm-registry.json": ("vault_norms.py", "--rebuild"),
    "data-fundamentals.json": ("vault_fundamentals.py",),
    "tool-contracts.json": ("vault_compact_contracts.py",),
    "quality-index.json": ("vault_quality_check.py",),
    "tag-registry.json": ("vault_tags.py",),
    "standard-version.json": None,
}

_SIN_PRODUCTOR = "vault_init (se inicializa con el vault; no se deriva)"


def _system_dir() -> Path:
    return get_vault_root() / "00_System"


def _source(productor) -> str:
    if productor is None:
        return _SIN_PRODUCTOR
    return " ".join(productor).replace(".py", "")


def _fix() -> str:
    comandos = []
    for productor in ARTIFACTS.values():
        if productor is not None:
            comando = "python scripts/" + " ".join(productor)
            if comando not in comandos:
                comandos.append(comando)
    return "Regenerar con: " + " && ".join(comandos) + "  (o --regenerar)"


def _check() -> dict:
    missing = []
    invalid = []
    ok = []
    system_dir = _system_dir()

    for fname, productor in ARTIFACTS.items():
        source = _source(productor)
        path = system_dir / fname
        if not path.exists():
            missing.append({"file": fname, "source": source})
        else:
            try:
                json.loads(path.read_text(encoding="utf-8"))
                ok.append(fname)
            except (json.JSONDecodeError, OSError) as exc:
                invalid.append({"file": fname, "error": str(exc)})

    stale = missing + invalid

    return {
        "ok": len(stale) == 0,
        "tool": "vault_doc_staleness",
        "total": len(ARTIFACTS),
        "present": len(ok),
        "missing": len(missing),
        "invalid": len(invalid),
        "missing_files": missing,
        "invalid_files": invalid,
        "present_files": ok,
        "fix": _fix(),
    }


def _regenerar() -> dict:
    """Ejecuta el productor de cada artefacto ausente o inválido, una vez cada uno.

    AP-37: el envelope dice qué se ejecutó y qué no se pudo, y ``ok`` sale del
    re-check posterior, no de que los procesos terminaran.
    """
    antes = _check()
    pendientes = [e["file"] for e in antes["missing_files"] + antes["invalid_files"]]
    ejecutados, fallidos, sin_productor = [], [], []
    for fname in ARTIFACTS:
        if fname not in pendientes:
            continue
        productor = ARTIFACTS[fname]
        if productor is None:
            sin_productor.append(fname)
            continue
        if list(productor) in [e["argv"] for e in ejecutados + fallidos]:
            continue
        proceso = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / productor[0]), *productor[1:]],
            env={**os.environ, "VAULT_ROOT": str(get_vault_root()),
                 "PYTHONIOENCODING": "utf-8"},
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        registro = {"argv": list(productor), "returncode": proceso.returncode}
        if proceso.returncode:
            registro["stderr"] = (proceso.stderr or proceso.stdout)[-500:]
            fallidos.append(registro)
        else:
            ejecutados.append(registro)
    despues = _check()
    return {
        **despues,
        "regenerated": len(ejecutados),
        "producers_run": ejecutados,
        "producers_failed": fallidos,
        "without_producer": sin_productor,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Verifica que los artefactos derivados existen y son JSON válido.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,
    )
    parser.add_argument("--check", action="store_true", help="Modo comprobación")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 si falta o está corrupto algún artefacto",
    )
    parser.add_argument(
        "--regenerar",
        action="store_true",
        help="Ejecuta el productor de cada artefacto ausente o inválido",
    )
    args = parser.parse_args()

    if args.regenerar:
        result = _regenerar()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["ok"] else 1

    result = _check()

    if args.check:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    if args.strict and not result["ok"]:
        return 1
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_doc_staleness"))
