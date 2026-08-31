#!/usr/bin/env python3

"""

Vault Security Scan Tool — Scan code for vulnerabilities



Scans source files for 45 security rules across 13 categories.

Saves findings to vault with OWASP/CWE mapping.

Redacts secrets in output.



Usage:

    python vault_security_scan.py --path "src/" --project "mi-api"

    python vault_security_scan.py --path "src/" --project "mi-api" --categories "secrets,injection" --save_findings true

"""

import argparse

import json

import re

import sys

from vault_errors import emit_error, wrap_main
from vault_lib import yaml_scalar, slugify_strict, utcnow
import uuid

from datetime import datetime, timezone
from pathlib import Path

from typing import Any, Dict, List, Optional, Tuple


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.gobernanza.repositorio import RepositorioGobernanza  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioGobernanza:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioGobernanza(construir(root))


def _observability_dir() -> Path:
    return _repo().dir_observabilidad


def _vulnerabilities_dir() -> Path:
    return _repo().dir_vulnerabilidades


def _utcdate() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


from vault_io import atomic_write_text, write_report
from vault_secret_scan import redact_secrets as _redactar_por_registro
# El vocabulario se declara una vez y se consume, no se copia. Ver
# `vault_vocabulario.py` para el registro y su contexto dueño.
from vault_vocabulario import cubos as _cubos, opciones as _opciones


IGNORED_DIRS = {
    ".git",
    "node_modules",
    ".next",
    "dist",
    "build",
    "__pycache__",
    ".venv",
}

SCAN_EXTS = {
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".py",
    ".php",
    ".rb",
    ".java",
    ".go",
    ".rs",
    ".cs",
    ".sh",
    ".bash",
    ".ps1",
    ".html",
    ".ejs",
    ".hbs",
    ".pug",
    ".vue",
    ".svelte",
}


from vault_security_rules import REGLAS_POR_CATEGORIA as RULES, CATEGORIAS as CATEGORIES, MITIGACIONES as MITIGATIONS  # noqa: E402



def redact_secrets(line: str) -> str:
    """Redacta un fragmento antes de que entre en el vault.

    Dos capas, y las dos hacen falta:

    - la del registro canónico (`vault_secret_scan`), que reconoce el FORMATO
      de cada credencial —AWS, GitHub, JWT, clave privada— y es la misma que
      bloquea el write path. Sin ella, la copia local de esta tool declaraba
      limpio lo que `atomic_write_text` rechazaba: dos criterios distintos para
      el mismo secreto (AP-05), y el informe se caía al escribirse.
    - la heurística por longitud que ya había aquí, que no reconoce formatos
      pero se lleva por delante cualquier cadena larga que huela a clave. No se
      elimina: cubre lo que el registro todavía no tiene patrón para ver.
    """
    line, _ = _redactar_por_registro(line)

    line = re.sub(r"['\"][a-zA-Z0-9]{20,}['\"]", "'[REDACTED]'", line)

    line = re.sub(r"[a-zA-Z0-9]{32,}", "[REDACTED]", line)

    return line


def scan_file(file_path: Path, active_rules: dict) -> List[Dict[str, Any]]:
    findings = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    except (UnicodeDecodeError, PermissionError, FileNotFoundError):
        return findings

    for line_no, line in enumerate(lines, 1):
        for category, rules in active_rules.items():
            for rule in rules:
                if re.search(rule["pattern"], line):
                    findings.append(
                        {
                            "ruleId": rule["id"],
                            "severity": rule["severity"],
                            "category": category,
                            "file": str(file_path),
                            "line": line_no,
                            "snippet": redact_secrets(line.strip()),
                            "owasp": rule.get("owasp", ""),
                            "cwe": rule.get("cwe", ""),
                            "mitigation": MITIGATIONS.get(
                                rule["id"], "Revisar y corregir el código."
                            ),
                        }
                    )

    return findings


def scan_directory(
    path: Path, depth: int, active_rules: dict
) -> List[Tuple[Path, List[Dict]]]:
    results = []

    if not path.exists():
        return results

    for item in path.rglob("*"):
        if item.is_file():
            if any(ignored in item.parts for ignored in IGNORED_DIRS):
                continue

            if item.suffix.lower() not in SCAN_EXTS:
                continue

            findings = scan_file(item, active_rules)

            if findings:
                results.append((item, findings))

    return results


def save_findings_to_vault(findings: List[Dict], project: str) -> List[str]:
    _vulnerabilities_dir().mkdir(parents=True, exist_ok=True)

    timestamp = _utcdate()

    saved_files = []

    # Redacción en un único punto, antes de construir nada: el fragmento
    # vulnerable es código ajeno y puede llevar la credencial dentro. La tool
    # que existe para encontrar secretos era la que los persistía en claro —y
    # en DOS sitios, el informe agregado y la nota por hallazgo—, así que se
    # redacta aquí y los dos escritores heredan la corrección. Lo que el
    # informe necesita es la forma del fallo, no la clave (AP-44).
    findings = [dict(f) for f in findings]
    for f in findings:
        f["snippet"] = redact_secrets(f.get("snippet", ""))

    by_severity = _cubos("severidad", [])

    for f in findings:
        by_severity[f["severity"]].append(f)

    report_lines = ["---"]

    report_lines.append(f"title: {yaml_scalar(f'Security Scan Report - {project}')}")

    report_lines.append(f"project: {yaml_scalar(project)}")

    report_lines.append(f"date: {timestamp}")

    report_lines.append(f"type: security-scan")

    report_lines.append("---")

    report_lines.append(f"\n# Security Scan Report: {project}\n")

    report_lines.append(f"**Fecha:** {timestamp}")

    report_lines.append(f"**Total hallazgos:** {len(findings)}\n")

    for sev in _opciones("severidad"):
        if by_severity[sev]:
            report_lines.append(f"## {sev.upper()} ({len(by_severity[sev])})\n")

            for f in by_severity[sev]:
                report_lines.append(f"### {f['ruleId']} - {f['category']}")

                report_lines.append(f"- **Archivo:** `{f['file']}:{f['line']}`")

                report_lines.append(f"- **OWASP:** {f['owasp']}")

                report_lines.append(f"- **CWE:** {f['cwe']}")

                report_lines.append(f"- **Código:** ```\n{f['snippet']}\n```")

                report_lines.append(f"- **Mitigación:** {f['mitigation']}\n")

    report_path = (
        _vulnerabilities_dir() / f"security-scan-{slugify(project)}-{timestamp}.md"
    )

    # atomic_write_* y no `open(..., "w")`: el escaneo de secretos, el saneado de
    # encoding y el temp+replace viven ahí (AP-36).
    atomic_write_text(report_path, "\n".join(report_lines))

    saved_files.append(str(report_path.relative_to(_raiz())))

    for f in findings:
        if f["severity"] in ["critical", "high"]:
            slug = slugify(f["ruleId"] + "-" + f["category"])

            note_path = _vulnerabilities_dir() / f"{f['ruleId']}-{slug}-{timestamp}.md"

            note_lines = ["---"]

            note_lines.append(f"title: {yaml_scalar(str(f['ruleId']) + ' - ' + str(f['category']))}")

            note_lines.append(f"ruleId: {yaml_scalar(str(f['ruleId']))}")

            note_lines.append(f"severity: {f['severity']}")

            note_lines.append(f"category: {yaml_scalar(f['category'])}")

            note_lines.append(f"project: {yaml_scalar(project)}")

            note_lines.append(f"date: {timestamp}")

            note_lines.append(f"owasp: {f['owasp']}")

            note_lines.append(f"cwe: {f['cwe']}")

            note_lines.append("---")

            note_lines.append(f"\n# {f['ruleId']}: {f['category']}\n")

            note_lines.append(f"**Severidad:** {f['severity'].upper()}")

            note_lines.append(f"**Archivo:** `{f['file']}:{f['line']}`\n")

            # Ya viene redactado desde la cabecera de esta función.
            note_lines.append(f"## Código Vulnerable\n\n```\n{f['snippet']}\n```\n")

            note_lines.append(f"## Mitigación\n\n{f['mitigation']}\n")

            atomic_write_text(note_path, "\n".join(note_lines))

            saved_files.append(str(note_path.relative_to(_raiz())))

    return saved_files


def slugify(text: str) -> str:
    # Delega en el slug canónico (`vault_lib.slugify`). La copia que había
    # aquí divergía del resto: unas borraban los acentos, otras los dejaban
    # en el nombre de fichero. Una sola fuente, un solo nombre de nota.
    return slugify_strict(text)


def vault_security_scan(
    path: str,
    project: str = "",
    depth: int = 3,
    categories: Optional[List[str]] = None,
    save_findings: bool = True,
) -> Dict[str, Any]:
    p = Path(path)

    scan_path = p if p.is_absolute() else _raiz() / p

    if not scan_path.exists():
        return emit_error("vault_security_scan", "FILE_NOT_FOUND", f"Path not found: {path}")

    if categories and "all" not in categories:
        active_rules = {k: v for k, v in RULES.items() if k in categories}

    else:
        active_rules = RULES

    results = scan_directory(scan_path, depth, active_rules)

    all_findings = []

    for file_path, findings in results:
        all_findings.extend(findings)

    files_scanned = len(results)

    by_severity = _cubos("severidad", 0)

    by_category: Dict[str, int] = {}

    for f in all_findings:
        by_severity[f["severity"]] = by_severity.get(f["severity"], 0) + 1

        by_category[f["category"]] = by_category.get(f["category"], 0) + 1

    risk_level = "BAJO"

    if by_severity["critical"] > 0:
        risk_level = "CRÍTICO"

    elif by_severity["high"] > 0:
        risk_level = "ALTO"

    elif by_severity["medium"] > 0:
        risk_level = "MEDIO"

    saved_files = []

    if save_findings and all_findings:
        saved_files = save_findings_to_vault(all_findings, project)

    return {
        "ok": True,
        **write_report(),
        "riskLevel": risk_level,
        "filesScanned": files_scanned,
        "totalFindings": len(all_findings),
        "bySeverity": by_severity,
        "byCategory": by_category,
        "findings": all_findings[:20],
        "savedToVault": saved_files,
        "summary": f"{files_scanned} archivos escaneados — {len(all_findings)} hallazgos ({by_severity['critical']} críticos, {by_severity['high']} altos) — Riesgo: {risk_level}",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Security Scan Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_security_scan.py --path "src/" --project "mi-api"

  python vault_security_scan.py --path "src/" --project "mi-api" --categories "secrets" "injection" --save_findings true

  python vault_security_scan.py --path "C:/repos/backend/src" --project "backend" --depth 5

  python vault_security_scan.py --path "src/" --project "mi-api" --categories "all" --save_findings false



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - 45 reglas en 13 categorias con mapeo OWASP/CWE

  - Los secretos se redactan en el output

  - Categorias disponibles: secrets, injection, command_injection, xss, auth, crypto, path_traversal, ssrf, xxe, deserialize, prototype_pollution, redos, config, dependencies

""",
    )

    parser.add_argument("--path", required=True, help="Path to scan")

    parser.add_argument("--project", default="", help="Project name")

    parser.add_argument("--depth", type=int, default=3, help="Directory depth (1-5)")

    parser.add_argument(
        "--categories", nargs="*", help=f"Categories to scan: {CATEGORIES}"
    )

    parser.add_argument(
        "--save_findings",
        type=lambda x: x.lower() == "true",
        default=True,
        help="Save to vault",
    )

    args = parser.parse_args()

    result = vault_security_scan(
        args.path,
        args.project,
        args.depth,
        args.categories,
        args.save_findings,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_security_scan"))
