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
from vault_errors import wrap_main
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _utcdate() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


VAULT_ROOT = Path(__file__).parent.parent
OBSERVABILITY_DIR = VAULT_ROOT / "02_Observability"
VULNERABILITIES_DIR = OBSERVABILITY_DIR / "vulnerabilities"

IGNORED_DIRS = {".git", "node_modules", ".next", "dist", "build", "__pycache__", ".venv"}
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

RULES = {
    "secrets": [
        {
            "id": "S001",
            "pattern": r"(?i)(api[_-]?key|apikey|secret[_-]?key)\s*[=:]\s*[\"'][^\"']{8,}",
            "severity": "critical",
            "owasp": "A02:2021",
            "cwe": "CWE-798",
        },
        {
            "id": "S002",
            "pattern": r"(?i)(password|passwd|pwd)\s*[=:]\s*[\"'][^\"']{4,}",
            "severity": "critical",
            "owasp": "A02:2021",
            "cwe": "CWE-798",
        },
        {
            "id": "S003",
            "pattern": r"(?i)jwt[_-]?secret\s*[=:]\s*[\"'][^\"']{8,}",
            "severity": "critical",
            "owasp": "A02:2021",
            "cwe": "CWE-798",
        },
        {
            "id": "S004",
            "pattern": r"(?i)(private[_-]?key|privkey)\s*[=:]?\s*[\"']-----BEGIN",
            "severity": "critical",
            "owasp": "A02:2021",
            "cwe": "CWE-798",
        },
        {
            "id": "S005",
            "pattern": r"(?i)(aws[_-]?access[_-]?key|aws[_-]?secret)\s*[=:]",
            "severity": "critical",
            "owasp": "A02:2021",
            "cwe": "CWE-798",
        },
        {
            "id": "S006",
            "pattern": r"(?i)(github[_-]?token|ghp_[a-zA-Z0-9]{36})",
            "severity": "critical",
            "owasp": "A02:2021",
            "cwe": "CWE-798",
        },
        {
            "id": "S007",
            "pattern": r"(?i)connection[_-]?string.*password\s*[=:]",
            "severity": "high",
            "owasp": "A02:2021",
            "cwe": "CWE-798",
        },
    ],
    "injection": [
        {
            "id": "I001",
            "pattern": r"['\"]SELECT.*\+.*['\"]|['\"]INSERT.*\+.*['\"]|['\"]UPDATE.*\+.*['\"]|['\"]DELETE.*\+.*['\"]",
            "severity": "high",
            "owasp": "A03:2021",
            "cwe": "CWE-89",
        },
        {
            "id": "I002",
            "pattern": r"execute\s*\(\s*['\"].*\%s.*['\"]",
            "severity": "high",
            "owasp": "A03:2021",
            "cwe": "CWE-89",
        },
        {
            "id": "I003",
            "pattern": r"db\.collection\s*\(\s*.*\)\.find\s*\(\s*\{.*\+",
            "severity": "high",
            "owasp": "A03:2021",
            "cwe": "CWE-943",
        },
        {
            "id": "I004",
            "pattern": r"ldap\.search\s*\([^)]*\+[^)]*\)",
            "severity": "high",
            "owasp": "A03:2021",
            "cwe": "CWE-90",
        },
        {
            "id": "I005",
            "pattern": r"xpath\s*\([^)]*\+[^)]*\)",
            "severity": "high",
            "owasp": "A03:2021",
            "cwe": "CWE-643",
        },
        {
            "id": "I006",
            "pattern": r"(render|renderToString)\s*\(.*\+",
            "severity": "medium",
            "owasp": "A03:2021",
            "cwe": "CWE-79",
        },
    ],
    "command_injection": [
        {
            "id": "C001",
            "pattern": r"(exec|spawn|execSync)\s*\([^)]*\(req|process|argv|body|query|params\)",
            "severity": "critical",
            "owasp": "A03:2021",
            "cwe": "CWE-78",
        },
        {"id": "C002", "pattern": r"shell\s*:\s*true", "severity": "high", "owasp": "A03:2021", "cwe": "CWE-78"},
    ],
    "xss": [
        {"id": "X001", "pattern": r"innerHTML\s*=\s*[^;]*\+", "severity": "high", "owasp": "A03:2021", "cwe": "CWE-79"},
        {
            "id": "X002",
            "pattern": r"document\.write\s*\([^)]*\)",
            "severity": "high",
            "owasp": "A03:2021",
            "cwe": "CWE-79",
        },
        {
            "id": "X003",
            "pattern": r"res\.send\s*\(.*\<.*\>.*\)",
            "severity": "high",
            "owasp": "A03:2021",
            "cwe": "CWE-79",
        },
        {
            "id": "X004",
            "pattern": r"dangerouslySetInnerHTML\s*=\s*\{",
            "severity": "medium",
            "owasp": "A03:2021",
            "cwe": "CWE-79",
        },
        {
            "id": "X005",
            "pattern": r"javascript:\s*(location|eval|document)",
            "severity": "high",
            "owasp": "A03:2021",
            "cwe": "CWE-79",
        },
        {"id": "X006", "pattern": r"srcdoc\s*=\s*[^;]*\+", "severity": "medium", "owasp": "A03:2021", "cwe": "CWE-79"},
    ],
    "auth": [
        {
            "id": "A001",
            "pattern": r"alg\s*:\s*['\"]none['\"]",
            "severity": "critical",
            "owasp": "A07:2021",
            "cwe": "CWE-347",
        },
        {
            "id": "A002",
            "pattern": r"(===|==)\s*\(.*token.*\)",
            "severity": "high",
            "owasp": "A07:2021",
            "cwe": "CWE-208",
        },
        {
            "id": "A003",
            "pattern": r"router\s*\.(get|post|put|delete)\s*\([^,]+,\s*(?!.*auth)",
            "severity": "high",
            "owasp": "A01:2021",
            "cwe": "CWE-862",
        },
        {
            "id": "A004",
            "pattern": r"cookie\s*\([^)]*\)\s*(?!.*httpOnly)(?!.*secure)",
            "severity": "medium",
            "owasp": "A07:2021",
            "cwe": "CWE-1004",
        },
        {
            "id": "A005",
            "pattern": r"Access-Control-Allow-Origin\s*:\s*['\"]\*['\"]",
            "severity": "medium",
            "owasp": "A05:2021",
            "cwe": "CWE-942",
        },
        {
            "id": "A006",
            "pattern": r"session\.regenerate\s*\(\s*\)",
            "severity": "low",
            "owasp": "A07:2021",
            "cwe": "CWE-384",
        },
    ],
    "crypto": [
        {
            "id": "K001",
            "pattern": r"md5\s*\(|hashlib\.md5|MD5\s*\(",
            "severity": "high",
            "owasp": "A02:2021",
            "cwe": "CWE-327",
        },
        {
            "id": "K002",
            "pattern": r"sha1\s*\(|hashlib\.sha1|SHA1\s*\(",
            "severity": "high",
            "owasp": "A02:2021",
            "cwe": "CWE-327",
        },
        {"id": "K003", "pattern": r"Math\.random\s*\(\)", "severity": "medium", "owasp": "A02:2021", "cwe": "CWE-338"},
        {
            "id": "K004",
            "pattern": r"(DES|RC4|3DES)\s*\(|\.createCipher\s*\(",
            "severity": "high",
            "owasp": "A02:2021",
            "cwe": "CWE-327",
        },
        {
            "id": "K005",
            "pattern": r"AES\.ECB|createCipheriv.*ECB",
            "severity": "high",
            "owasp": "A02:2021",
            "cwe": "CWE-327",
        },
        {
            "id": "K006",
            "pattern": r"iv\s*:\s*['\"][0-9a-f]{32}['\"]",
            "severity": "high",
            "owasp": "A02:2021",
            "cwe": "CWE-329",
        },
        {
            "id": "K007",
            "pattern": r"rejectUnauthorized\s*:\s*false",
            "severity": "high",
            "owasp": "A02:2021",
            "cwe": "CWE-295",
        },
    ],
    "path_traversal": [
        {
            "id": "P001",
            "pattern": r"readFile\s*\([^)]*\(req|process|argv|body|query|params\)",
            "severity": "high",
            "owasp": "A01:2021",
            "cwe": "CWE-22",
        },
        {
            "id": "P002",
            "pattern": r"path\.join\s*\([^)]*\$",
            "severity": "medium",
            "owasp": "A01:2021",
            "cwe": "CWE-22",
        },
        {
            "id": "P003",
            "pattern": r"__dirname\s*\+\s*\(req|process|argv|body|query|params\)",
            "severity": "high",
            "owasp": "A01:2021",
            "cwe": "CWE-22",
        },
    ],
    "ssrf": [
        {
            "id": "F001",
            "pattern": r"(fetch|axios|requests\.get|requests\.post)\s*\([^)]*req\.",
            "severity": "high",
            "owasp": "A10:2021",
            "cwe": "CWE-918",
        },
        {
            "id": "F002",
            "pattern": r"url\s*=\s*.*\+.*(req|body|query|params)",
            "severity": "high",
            "owasp": "A10:2021",
            "cwe": "CWE-918",
        },
        {"id": "F003", "pattern": r"redirect\s*\(.*\+", "severity": "medium", "owasp": "A01:2021", "cwe": "CWE-601"},
    ],
    "xxe": [
        {
            "id": "X001",
            "pattern": r"XMLParser\s*\(|xmlParser\s*\(|new\s+DOMParser\s*\(",
            "severity": "medium",
            "owasp": "A05:2021",
            "cwe": "CWE-611",
        },
    ],
    "deserialize": [
        {
            "id": "D001",
            "pattern": r"unserialize\s*\(|deserialize\s*\(",
            "severity": "critical",
            "owasp": "A08:2021",
            "cwe": "CWE-502",
        },
        {
            "id": "D002",
            "pattern": r"JSON\.parse\s*\([^)]*\(req|process|argv|body\)",
            "severity": "low",
            "owasp": "A08:2021",
            "cwe": "CWE-915",
        },
    ],
    "prototype_pollution": [
        {
            "id": "PP001",
            "pattern": r"Object\.assign\s*\([^)]*req\.",
            "severity": "high",
            "owasp": "A08:2021",
            "cwe": "CWE-1321",
        },
        {
            "id": "PP002",
            "pattern": r"merge\s*\([^)]*\(req|body|query\)",
            "severity": "high",
            "owasp": "A08:2021",
            "cwe": "CWE-1321",
        },
        {
            "id": "PP003",
            "pattern": r"__proto__|constructor\.prototype",
            "severity": "medium",
            "owasp": "A08:2021",
            "cwe": "CWE-1321",
        },
    ],
    "redos": [
        {
            "id": "R001",
            "pattern": r"new\s+RegExp\s*\([^)]*\(req|process|argv|body|query|params\)",
            "severity": "medium",
            "owasp": "A04:2021",
            "cwe": "CWE-1333",
        },
    ],
    "config": [
        {"id": "CF001", "pattern": r"debug\s*:\s*true", "severity": "medium", "owasp": "A05:2021", "cwe": "CWE-11"},
        {"id": "CF002", "pattern": r"stack\s*:\s*true", "severity": "low", "owasp": "A05:2021", "cwe": "CWE-209"},
        {
            "id": "CF003",
            "pattern": r"app\.use\(helmet\)(?!.*contentSecurityPolicy)",
            "severity": "low",
            "owasp": "A05:2021",
            "cwe": "CWE-16",
        },
        {"id": "CF004", "pattern": r"\.env(?!\.)", "severity": "low", "owasp": "A05:2021", "cwe": "CWE-522"},
        {
            "id": "CF005",
            "pattern": r"(HOST|host)\s*[=:]\s*['\"](0\.0\.0\.0|::)['\"]",
            "severity": "low",
            "owasp": "A05:2021",
            "cwe": "CWE-16",
        },
        {
            "id": "CF006",
            "pattern": r"console\.(log|debug)\s*\([^)]*(req\.|res\.|session|token|password|secret)",
            "severity": "medium",
            "owasp": "A09:2021",
            "cwe": "CWE-532",
        },
        {
            "id": "CF007",
            "pattern": r"express\s*\(\s*\)(?!.*rateLimit)",
            "severity": "low",
            "owasp": "A05:2021",
            "cwe": "CWE-307",
        },
    ],
    "dependencies": [
        {
            "id": "DP001",
            "pattern": r"\"version\"\s*:\s*\"\*\"",
            "severity": "medium",
            "owasp": "A06:2021",
            "cwe": "CWE-1104",
        },
        {
            "id": "DP002",
            "pattern": r"require\s*\([^)]*\(req|process|argv|body\)",
            "severity": "medium",
            "owasp": "A06:2021",
            "cwe": "CWE-827",
        },
    ],
}

CATEGORIES = list(RULES.keys())

MITIGATIONS = {
    "S001": "Usar variables de entorno para API keys. Nunca hardcodear secrets en código.",
    "S002": "Usar variables de entorno o gestores de secretos (Vault, AWS Secrets Manager).",
    "I001": "Usar consultas parametrizadas o ORM. Nunca concatenar input del usuario en SQL.",
    "C001": "Evitar exec/spawn con input externo. Usar bibliotecas de validación de comandos.",
    "X001": "Usar textContent en lugar de innerHTML. Sanitizar input con DOMPurify.",
    "A001": "Validar siempre el algoritmo del JWT. Rechazar tokens con alg:'none'.",
    "K001": "Usar bcrypt, scrypt o Argon2 para passwords. MD5/SHA1 son inseguros para passwords.",
    "P001": "Validar y sanitizar rutas de archivo. Usar path.resolve y verificar dentro de un sandbox.",
    "F001": "Validar URLs contra una lista de permitidos. No permitir URLs relativas sin validación.",
    "D001": "Nunca deserializar input no confiable. Usar JSON.parse en lugar de deserialize.",
}


def redact_secrets(line: str) -> str:
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
                            "mitigation": MITIGATIONS.get(rule["id"], "Revisar y corregir el código."),
                        }
                    )

    return findings


def scan_directory(path: Path, depth: int, active_rules: dict) -> List[Tuple[Path, List[Dict]]]:
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
    VULNERABILITIES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = _utcdate()
    saved_files = []

    by_severity = {"critical": [], "high": [], "medium": [], "low": []}
    for f in findings:
        by_severity[f["severity"]].append(f)

    report_lines = ["---"]
    report_lines.append(f"title: Security Scan Report - {project}")
    report_lines.append(f"project: {project}")
    report_lines.append(f"date: {timestamp}")
    report_lines.append(f"type: security-scan")
    report_lines.append("---")
    report_lines.append(f"\n# Security Scan Report: {project}\n")
    report_lines.append(f"**Fecha:** {timestamp}")
    report_lines.append(f"**Total hallazgos:** {len(findings)}\n")

    for sev in ["critical", "high", "medium", "low"]:
        if by_severity[sev]:
            report_lines.append(f"## {sev.upper()} ({len(by_severity[sev])})\n")
            for f in by_severity[sev]:
                report_lines.append(f"### {f['ruleId']} - {f['category']}")
                report_lines.append(f"- **Archivo:** `{f['file']}:{f['line']}`")
                report_lines.append(f"- **OWASP:** {f['owasp']}")
                report_lines.append(f"- **CWE:** {f['cwe']}")
                report_lines.append(f"- **Código:** ```\n{f['snippet']}\n```")
                report_lines.append(f"- **Mitigación:** {f['mitigation']}\n")

    report_path = VULNERABILITIES_DIR / f"security-scan-{slugify(project)}-{timestamp}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    saved_files.append(str(report_path.relative_to(VAULT_ROOT)))

    for f in findings:
        if f["severity"] in ["critical", "high"]:
            slug = slugify(f["ruleId"] + "-" + f["category"])
            note_path = VULNERABILITIES_DIR / f"{f['ruleId']}-{slug}-{timestamp}.md"

            note_lines = ["---"]
            note_lines.append(f"title: {f['ruleId']} - {f['category']}")
            note_lines.append(f"ruleId: {f['ruleId']}")
            note_lines.append(f"severity: {f['severity']}")
            note_lines.append(f"category: {f['category']}")
            note_lines.append(f"project: {project}")
            note_lines.append(f"date: {timestamp}")
            note_lines.append(f"owasp: {f['owasp']}")
            note_lines.append(f"cwe: {f['cwe']}")
            note_lines.append("---")
            note_lines.append(f"\n# {f['ruleId']}: {f['category']}\n")
            note_lines.append(f"**Severidad:** {f['severity'].upper()}")
            note_lines.append(f"**Archivo:** `{f['file']}:{f['line']}`\n")
            note_lines.append(f"## Código Vulnerable\n\n```\n{f['snippet']}\n```\n")
            note_lines.append(f"## Mitigación\n\n{f['mitigation']}\n")

            with open(note_path, "w", encoding="utf-8") as nf:
                nf.write("\n".join(note_lines))
            saved_files.append(str(note_path.relative_to(VAULT_ROOT)))

    return saved_files


def slugify(text: str) -> str:
    slug = text.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"^-+|-+$", "", slug)
    return slug


def vault_security_scan(
    path: str,
    project: str = "",
    depth: int = 3,
    categories: Optional[List[str]] = None,
    save_findings: bool = True,
) -> Dict[str, Any]:
    p = Path(path)
    scan_path = p if p.is_absolute() else VAULT_ROOT / p
    if not scan_path.exists():
        return {"ok": False, "error": f"Path not found: {path}"}

    if categories and "all" not in categories:
        active_rules = {k: v for k, v in RULES.items() if k in categories}
    else:
        active_rules = RULES

    results = scan_directory(scan_path, depth, active_rules)

    all_findings = []
    for file_path, findings in results:
        all_findings.extend(findings)

    files_scanned = len(results)
    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
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
    parser.add_argument("--categories", nargs="*", help=f"Categories to scan: {CATEGORIES}")
    parser.add_argument("--save_findings", type=lambda x: x.lower() == "true", default=True, help="Save to vault")

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
