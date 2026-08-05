"""vault_cli — punto de entrada único de la CLI consolidada.

    python -m cli <comando> [opciones]

Comandos de descubrimiento (las tools como fragmentos buscables):
    groups | find | show | doctor

Comandos de ejecución:
    run   — una tool, con pre-vuelo de seguridad
    batch — varias tools a la vez, planificadas para no corromperse
    plan  — muestra el plan de un lote sin ejecutar nada

Comandos de análisis:
    scan  — antipatrones y condiciones de carrera sobre scripts/

Toda salida es JSON por defecto (contrato de las tools); `--pretty` la formatea
para lectura humana. Exit code 0 sólo si todo salió bien.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import __version__, analyzer, registry, runner, safety, scheduler
from .scheduler import Operation


def _emit(data: Dict[str, Any], pretty: bool = False) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2 if pretty else None)
    try:
        sys.stdout.buffer.write((text + "\n").encode("utf-8"))
        sys.stdout.buffer.flush()
    except (AttributeError, ValueError):
        print(text)


def _covers(declared: str, changed: str) -> bool:
    """¿La ruta declarada cubre la que cambió?

    Compara por segmento, no por prefijo de cadena: `01_Projects/api` no debe
    cubrir `01_Projects/api-legacy`. Se acepta también el caso inverso (lo
    declarado es la nota sin extensión y lo cambiado es el archivo real).
    """
    if declared == changed:
        return True
    if changed.startswith(declared + "/"):
        return True
    stem = changed.rsplit(".", 1)[0]
    return stem == declared or stem.lower() == declared.lower()


def _vault_root() -> Path:
    from vault_io import get_vault_root

    return get_vault_root()


def parse_kv(pairs: List[str]) -> Dict[str, Any]:
    """Convierte `clave=valor` en dict. `clave` sola es un booleano True."""
    args: Dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            args[pair.lstrip("-")] = True
            continue
        key, _, value = pair.partition("=")
        key = key.lstrip("-")
        if value.startswith("@") and not value.startswith("@file:"):
            # @ruta → lee el valor de un archivo (contenidos largos)
            args[key] = Path(value[1:]).read_text(encoding="utf-8")
        elif value.lower() in ("true", "false"):
            args[key] = value.lower() == "true"
        else:
            args[key] = value
    return args


# ── descubrimiento ───────────────────────────────────────────────────────────

def cmd_groups(args: argparse.Namespace) -> int:
    data = {
        "ok": True,
        "tool": "cli.groups",
        **registry.stats(),
        "catalog": {
            group: [
                {"name": f.name, "mode": f.mode, "purpose": f.purpose[:100]}
                for f in frags
            ]
            for group, frags in registry.groups().items()
        },
    }
    _emit(data, args.pretty)
    return 0


def cmd_find(args: argparse.Namespace) -> int:
    results = registry.search(args.query, mode=args.mode, group=args.group)
    _emit({
        "ok": True,
        "tool": "cli.find",
        "query": args.query,
        "matches": len(results),
        "fragments": [f.to_dict() if args.full else {
            "name": f.name, "group": f.group, "mode": f.mode,
            "purpose": f.purpose[:140],
        } for f in results],
    }, args.pretty)
    return 0 if results else 1


def cmd_show(args: argparse.Namespace) -> int:
    frag = registry.resolve(args.tool)
    if frag is None:
        suggestions = [f.name for f in registry.search(args.tool)][:5]
        _emit({
            "ok": False, "tool": "cli.show",
            "error": f"fragmento desconocido: '{args.tool}'",
            "did_you_mean": suggestions,
        }, args.pretty)
        return 1
    data = frag.to_dict()
    data["params_detail"] = frag.params
    data["example"] = frag.example
    data["concurrency"] = {
        "global_scope": frag.name in scheduler.GLOBAL_SCOPE_TOOLS,
        "parallelizable": frag.mode == "read"
        and frag.name not in scheduler.GLOBAL_SCOPE_TOOLS,
    }
    _emit({"ok": True, "tool": "cli.show", "fragment": data}, args.pretty)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from vault_io import (resolve_tool_spec, tool_spec_path, vault_root_is_confident,
                          vault_root_origin)

    root = _vault_root()
    spec = resolve_tool_spec()
    checks = []

    confident = vault_root_is_confident()
    checks.append({
        "check": "vault_root",
        "ok": confident,
        "value": str(root),
        "origin": vault_root_origin(),
        "hint": None if confident else
        "Raíz adivinada. Exporta VAULT_ROOT=<ruta> o VAULT_STRICT_ROOT=1 para fallar rápido.",
    })
    checks.append({
        "check": "tool_spec",
        "ok": spec is not None,
        "value": str(spec) if spec else None,
        "expected": str(tool_spec_path()),
        "hint": None if spec else "Genéralo con: python scripts/vault_manifest.py --bootstrap",
    })
    missing = registry.missing_scripts()
    checks.append({
        "check": "fragments",
        "ok": not missing,
        "value": registry.stats(),
        "hint": f"scripts ausentes: {missing}" if missing else None,
    })

    unsafe = analyzer.unsafe_artifacts()
    checks.append({
        "check": "shared_artifact_locks",
        "ok": not unsafe,
        "value": unsafe,
        "hint": None if not unsafe else
        "Estos artefactos se escriben sin file_lock; el planificador los "
        "serializará en vez de paralelizarlos.",
    })

    ok = all(c["ok"] for c in checks)
    _emit({"ok": ok, "tool": "cli.doctor", "version": __version__,
           "checks": checks}, args.pretty)
    return 0 if ok else 1


# ── ejecución ────────────────────────────────────────────────────────────────

def _load_operations(args: argparse.Namespace) -> Tuple[List[Operation], Optional[str]]:
    """Lee operaciones de --op repetido o de un archivo/stdin JSON."""
    ops: List[Operation] = []

    if args.file:
        raw = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(
            encoding="utf-8"
        )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            return [], f"JSON inválido en '{args.file}': {exc}"
        entries = data.get("operations", data) if isinstance(data, dict) else data
        if not isinstance(entries, list):
            return [], "el archivo debe contener una lista de operaciones"
        for i, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict) or "tool" not in entry:
                return [], f"operación #{i} sin campo 'tool'"
            ops.append(Operation(
                tool=entry["tool"],
                args=entry.get("args", {}) or {},
                id=entry.get("id", f"{entry['tool']}#{i}"),
            ))

    for i, spec in enumerate(args.op or [], start=len(ops) + 1):
        parts = spec.split()
        if not parts:
            continue
        ops.append(Operation(
            tool=parts[0], args=parse_kv(parts[1:]), id=f"{parts[0]}#{i}",
        ))

    return ops, None


def _preflight_all(ops: List[Operation], root: Path,
                   strict: bool) -> Tuple[List[Dict[str, Any]], bool]:
    reports: List[Dict[str, Any]] = []
    all_ok = True
    for op in ops:
        frag = op.fragment
        if frag is None:
            reports.append({
                "id": op.id, "ok": False,
                "findings": [{"code": "TOOL-UNKNOWN", "severity": "critical",
                              "field": op.tool, "detail": "no está en el catálogo"}],
            })
            all_ok = False
            continue
        verdict = safety.preflight(frag, op.args, root, strict=strict)
        reports.append({"id": op.id, **verdict.to_dict()})
        all_ok = all_ok and verdict.ok
    return reports, all_ok


def cmd_run(args: argparse.Namespace) -> int:
    op = Operation(tool=args.tool, args=parse_kv(args.arg or []), id=args.tool)
    frag = op.fragment
    if frag is None:
        _emit({"ok": False, "tool": "cli.run",
               "error": f"fragmento desconocido: '{args.tool}'",
               "did_you_mean": [f.name for f in registry.search(args.tool)][:5]},
              args.pretty)
        return 1

    root = _vault_root()
    verdict = safety.preflight(frag, op.args, root, strict=args.strict)
    if not verdict.ok and not args.force:
        _emit({
            "ok": False, "tool": "cli.run", "stage": "preflight",
            "error": "la operación no pasó las guardas de seguridad",
            **verdict.to_dict(),
            "hint": "revisa los hallazgos, o repite con --force bajo tu responsabilidad",
        }, args.pretty)
        return 2

    result = runner.run_one(op, timeout=args.timeout, dry_run=args.dry_run)
    payload = result.to_dict()
    if verdict.findings:
        payload["preflight_findings"] = [f.to_dict() for f in verdict.findings]
    _emit({"ok": result.ok, "tool": "cli.run", **payload}, args.pretty)
    return 0 if result.ok else 1


def cmd_plan(args: argparse.Namespace) -> int:
    ops, error = _load_operations(args)
    if error:
        _emit({"ok": False, "tool": "cli.plan", "error": error}, args.pretty)
        return 1
    if not ops:
        _emit({"ok": False, "tool": "cli.plan",
               "error": "ninguna operación indicada (usa --op o --file)"}, args.pretty)
        return 1

    unsafe = scheduler.harden(ops)
    root = _vault_root()
    reports, preflight_ok = _preflight_all(ops, root, args.strict)

    _emit({
        "ok": preflight_ok,
        "tool": "cli.plan",
        "preflight": reports,
        "unlocked_shared_artifacts": unsafe,
        **scheduler.explain(ops),
    }, args.pretty)
    return 0 if preflight_ok else 2


def cmd_batch(args: argparse.Namespace) -> int:
    ops, error = _load_operations(args)
    if error:
        _emit({"ok": False, "tool": "cli.batch", "error": error}, args.pretty)
        return 1
    if not ops:
        _emit({"ok": False, "tool": "cli.batch",
               "error": "ninguna operación indicada (usa --op o --file)"}, args.pretty)
        return 1

    root = _vault_root()
    unsafe = scheduler.harden(ops)
    reports, preflight_ok = _preflight_all(ops, root, args.strict)

    if not preflight_ok and not args.force:
        _emit({
            "ok": False, "tool": "cli.batch", "stage": "preflight",
            "error": "el lote no se ejecutó: hay operaciones que no pasan las guardas",
            "preflight": reports,
            "hint": "ninguna escritura ocurrió. Corrige y reintenta, o usa --force.",
        }, args.pretty)
        return 2

    waves = scheduler.plan(ops, max_parallel=args.parallel)
    before = safety.snapshot(root) if args.verify_integrity and not args.dry_run else {}

    results: List[runner.Result] = []
    aborted = False
    for wave in waves:
        wave_results = runner.run_wave(
            wave, timeout=args.timeout, dry_run=args.dry_run,
            max_parallel=args.parallel,
        )
        results.extend(wave_results)
        if args.stop_on_error and any(not r.ok for r in wave_results):
            aborted = True
            break

    payload: Dict[str, Any] = {
        "ok": all(r.ok for r in results) and not aborted,
        "tool": "cli.batch",
        "dry_run": args.dry_run,
        "operations": len(ops),
        "executed": len(results),
        "waves": len(waves),
        "max_parallel": args.parallel,
        "aborted_early": aborted,
        "unlocked_shared_artifacts": unsafe,
        "results": [r.to_dict() for r in results],
    }
    if aborted:
        payload["not_executed"] = [op.id for op in ops[len(results):]]

    if before:
        after = safety.snapshot(root)
        changes = safety.diff_snapshots(before, after)
        declared = scheduler.declared_targets(ops, root)
        unexpected = []
        ambient = []
        if "*" not in declared:
            for path in changes["created"] + changes["modified"] + changes["deleted"]:
                if safety.is_ambient(path):
                    ambient.append(path)
                elif not any(_covers(d, path) for d in declared):
                    unexpected.append(path)
        payload["integrity"] = {
            **changes,
            "declared_targets": sorted(declared),
            "ambient_changes": ambient,
            "unexpected_changes": unexpected,
        }
        if unexpected:
            payload["ok"] = False
            payload["integrity"]["note"] = (
                "Se modificaron rutas que el plan no declaraba. Revisa antes de "
                "seguir escribiendo — puede indicar un side-effect no documentado."
            )

    _emit(payload, args.pretty)
    return 0 if payload["ok"] else 1


# ── análisis ─────────────────────────────────────────────────────────────────

def cmd_scan(args: argparse.Namespace) -> int:
    kind = None
    if args.races and not args.antipatterns:
        kind = "race"
    elif args.antipatterns and not args.races:
        kind = "antipattern"

    paths = None
    if args.tool:
        frag = registry.resolve(args.tool)
        target = frag.script_path if frag else registry.SCRIPTS_DIR / f"{args.tool}.py"
        if not target.exists():
            _emit({"ok": False, "tool": "cli.scan",
                   "error": f"no existe el script '{target.name}'"}, args.pretty)
            return 1
        paths = [target]
    elif args.path:
        paths = [Path(args.path)]

    result = analyzer.scan(paths, kind=kind, min_severity=args.min_severity)
    if kind == "race" and not paths:
        # El dato accionable de un escaneo de carreras: qué artefacto compartido
        # se escribe sin lock y quién lo hace. Es lo que el scheduler consume
        # para degradar esos artefactos a exclusivos.
        result["unsafe_artifacts"] = analyzer.unsafe_artifacts()
    if args.summary:
        result.pop("issues", None)
    _emit(result, args.pretty)
    return 0 if result["ok"] else 1


# ── parser ───────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    # --pretty se declara además en cada subcomando: nadie recuerda que una
    # flag global tiene que ir ANTES del subcomando, y fallar por eso es
    # gratuito. Con el parent se acepta en las dos posiciones.
    common = argparse.ArgumentParser(add_help=False)
    # SUPPRESS es deliberado: sin él, el subparser reescribe con su default
    # (False) el `--pretty` que ya venía del parser principal, y la opción solo
    # funcionaría después del subcomando.
    common.add_argument("--pretty", action="store_true",
                        default=argparse.SUPPRESS, help="JSON indentado")

    parser = argparse.ArgumentParser(
        prog="python -m cli",
        # La cifra se cuenta, no se afirma: escrita a mano envejecía en
        # silencio (decía 76 con 86 tools en el catálogo) y ningún guard la veía,
        # porque vault_doc_counts solo audita documentos .md.
        description="CLI consolidada de Vault Obsidian Architecture "
                    f"v{__version__} — {len(list(registry.iter_fragments()))} tools "
                    "bajo un único punto de entrada",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python -m cli groups --pretty
  python -m cli find "backup grafo"
  python -m cli show vault_write --pretty
  python -m cli doctor --pretty

  python -m cli run vault_audit
  python -m cli run vault_write folder=01_Projects/api title="API" content=@nota.md

  python -m cli plan --file lote.json --pretty
  python -m cli batch --file lote.json --parallel 4 --verify-integrity

  python -m cli scan --races --pretty
  python -m cli scan --tool vault_write --summary

Documentación: cli/README.md (guía) y cli/COMMANDS.md (referencia).
""",
    )
    parser.add_argument("--pretty", action="store_true", help="JSON indentado")
    parser.add_argument("--version", action="version", version=f"cli {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("groups", parents=[common], help="Catálogo completo por grupo")
    p.set_defaults(func=cmd_groups)

    p = sub.add_parser("find", parents=[common], help="Busca fragmentos por texto libre")
    p.add_argument("query", help="Términos (todos deben aparecer)")
    p.add_argument("--mode", choices=["read", "write"], help="Filtra por modo")
    p.add_argument("--group", help="Filtra por grupo")
    p.add_argument("--full", action="store_true", help="Ficha completa de cada fragmento")
    p.set_defaults(func=cmd_find)

    p = sub.add_parser("show", parents=[common], help="Ficha de un fragmento")
    p.add_argument("tool")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("doctor", parents=[common], help="Estado del entorno: raíz, contrato, locks")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("run", parents=[common], help="Ejecuta una tool con pre-vuelo de seguridad")
    p.add_argument("tool")
    p.add_argument("arg", nargs="*", help="Argumentos clave=valor (@archivo para leer)")
    p.add_argument("--timeout", type=int, default=runner.DEFAULT_TIMEOUT)
    p.add_argument("--dry-run", action="store_true", help="Muestra el comando sin ejecutar")
    p.add_argument("--strict", action="store_true", help="Los avisos medium también bloquean")
    p.add_argument("--force", action="store_true", help="Ejecuta pese a los hallazgos")
    p.set_defaults(func=cmd_run)

    for name, func, help_text in (
        ("plan", cmd_plan, "Planifica un lote sin ejecutarlo"),
        ("batch", cmd_batch, "Ejecuta varias tools en paralelo con seguridad"),
    ):
        p = sub.add_parser(name, parents=[common], help=help_text)
        p.add_argument("--op", action="append",
                       help='Operación: "vault_audit" o "vault_write folder=X title=Y"')
        p.add_argument("--file", help="JSON con lista de operaciones ('-' = stdin)")
        p.add_argument("--strict", action="store_true")
        if name == "batch":
            p.add_argument("--parallel", type=int, default=4,
                           help="Operaciones simultáneas por ola (default: 4)")
            p.add_argument("--timeout", type=int, default=runner.DEFAULT_TIMEOUT)
            p.add_argument("--dry-run", action="store_true")
            p.add_argument("--force", action="store_true")
            p.add_argument("--stop-on-error", action="store_true",
                           help="Detiene tras la primera ola con fallos")
            p.add_argument("--verify-integrity", action="store_true",
                           help="Hashea el vault antes/después y compara con el plan")
        p.set_defaults(func=func)

    p = sub.add_parser("scan", parents=[common], help="Antipatrones y condiciones de carrera")
    p.add_argument("--races", action="store_true", help="Solo condiciones de carrera")
    p.add_argument("--antipatterns", action="store_true", help="Solo antipatrones")
    p.add_argument("--tool", help="Analiza un único fragmento")
    p.add_argument("--path", help="Analiza un archivo concreto")
    p.add_argument("--min-severity", default="low",
                   choices=["critical", "high", "medium", "low"])
    p.add_argument("--summary", action="store_true", help="Solo el recuento")
    p.set_defaults(func=cmd_scan)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        _emit({"ok": False, "tool": "cli", "error": "interrumpido por el usuario"})
        return 130
    except Exception as exc:  # noqa: BLE001 — frontera del proceso
        _emit({
            "ok": False, "tool": "cli",
            "error": f"{type(exc).__name__}: {exc}",
            "command": getattr(args, "command", None),
        })
        return 1


if __name__ == "__main__":
    sys.exit(main())
