#!/usr/bin/env python3
r"""Vault Secret Scan — Detect common secret patterns in markdown content.

v36: Addresses finding I1/I5 (no frontmatter/content secret scanning).

Patterns detected:
- AWS access keys: AKIA[0-9A-Z]{16}
- AWS secret keys: [A-Za-z0-9/+=]{40}
- GitHub tokens: ghp_[a-zA-Z0-9]{36}, gho_[a-zA-Z0-9]{36}, ghs_[a-zA-Z0-9]{36}
- Generic password assignments: (?i)password\s*[:=]\s*\S+
- Generic api_key/secret/token: (?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"]?\S+
- Bearer tokens: Bearer\s+[A-Za-z0-9\-._~+/]{20,}
- Private key markers: -----BEGIN [A-Z ]*PRIVATE KEY-----
- JWT tokens: eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+

Usage:
    from vault_secret_scan import scan_content, scan_note

    findings = scan_content(content)
    for f in findings:
        print(f"{f['severity']}: {f['pattern']} at offset {f['offset']}")
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional


SECRET_PATTERNS = [
    {
        "id": "aws_access_key",
        "pattern": r"\bAKIA[0-9A-Z]{16}\b",
        "severity": "critical",
        "description": "AWS access key ID",
    },
    {
        "id": "aws_secret_key",
        "pattern": r"(?<![A-Za-z0-9/+=])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])",
        "severity": "high",
        "description": "Possible AWS secret access key (40 chars base64-like)",
    },
    {
        "id": "github_personal_token",
        "pattern": r"\bghp_[a-zA-Z0-9]{36}\b",
        "severity": "critical",
        "description": "GitHub personal access token",
    },
    {
        "id": "github_oauth_token",
        "pattern": r"\bgho_[a-zA-Z0-9]{36}\b",
        "severity": "critical",
        "description": "GitHub OAuth token",
    },
    {
        "id": "github_server_token",
        "pattern": r"\bghs_[a-zA-Z0-9]{36}\b",
        "severity": "critical",
        "description": "GitHub server token",
    },
    {
        "id": "password_assignment",
        "pattern": r"(?i)password\s*[:=]\s*['\"]?([^\s'\"]{4,})",
        "severity": "high",
        "description": "Hardcoded password assignment",
    },
    {
        "id": "api_key_assignment",
        "pattern": r"(?i)(api[_-]?key|apikey|secret|token)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{8,})",
        "severity": "high",
        "description": "Hardcoded API key/secret/token assignment",
    },
    {
        "id": "bearer_token",
        "pattern": r"\bBearer\s+[A-Za-z0-9\-._~+/]{20,}",
        "severity": "critical",
        "description": "Bearer token in content",
    },
    {
        "id": "private_key_marker",
        "pattern": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        "severity": "critical",
        "description": "Private key marker",
    },
    {
        "id": "jwt_token",
        "pattern": r"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
        "severity": "high",
        "description": "JSON Web Token (JWT)",
    },
]


def _redact(value: str, keep: int = 4) -> str:
    """Redact a secret value, keeping only the last `keep` chars for context."""
    if len(value) <= keep:
        return "*" * len(value)
    return "*" * (len(value) - keep) + value[-keep:]


def scan_content(text: str) -> List[Dict[str, Any]]:
    """Scan text content for secret patterns.

    Returns a list of findings with severity, pattern, offset, and redacted match.
    """
    findings: List[Dict[str, Any]] = []
    for pat_def in SECRET_PATTERNS:
        for m in re.finditer(pat_def["pattern"], text):
            findings.append(
                {
                    "pattern_id": pat_def["id"],
                    "description": pat_def["description"],
                    "severity": pat_def["severity"],
                    "offset": m.start(),
                    "match_redacted": _redact(m.group(0)),
                    "line_hint": text[: m.start()].count("\n") + 1,
                }
            )
    return findings


def redact_secrets(text: str) -> tuple[str, int]:
    """Sustituye en el propio texto cada secreto detectado por su redacción.

    Para el caso en que el contenido a persistir ES código ajeno: el informe de
    `vault_security_scan` cita el fragmento vulnerable, y ese fragmento puede
    llevar la credencial dentro. Bloquear la escritura dejaría a la tool sin
    poder informar; escribirla cruda mete el secreto en el vault. Se redacta y
    se escribe, que es lo que el informe necesita —la forma del fallo, no la
    credencial—.

    Devuelve (texto redactado, nº de sustituciones).
    """
    if not text:
        return text, 0
    reemplazos: List[tuple[int, int, str]] = []
    for pat_def in SECRET_PATTERNS:
        for m in re.finditer(pat_def["pattern"], text):
            reemplazos.append((m.start(), m.end(), _redact(m.group(0))))
    if not reemplazos:
        return text, 0
    # De atrás hacia delante: sustituir por el final no invalida los offsets
    # de lo que queda por delante.
    reemplazos.sort(key=lambda r: r[0], reverse=True)
    fuera = text
    hechos = 0
    ultimo_inicio = len(text) + 1
    for inicio, fin, redactado in reemplazos:
        if fin > ultimo_inicio:  # solapado con uno ya sustituido
            continue
        fuera = fuera[:inicio] + redactado + fuera[fin:]
        ultimo_inicio = inicio
        hechos += 1
    return fuera, hechos


def scan_note(path: Path) -> List[Dict[str, Any]]:
    """Scan a single note file for secrets."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return scan_content(text)


def has_blocking_findings(findings: List[Dict[str, Any]]) -> bool:
    """Return True if any finding is critical (blocks write)."""
    return any(f["severity"] == "critical" for f in findings)


def vault_write_hook(text: str) -> tuple[bool, List[Dict[str, Any]]]:
    """Pre-write hook to call from vault_io.atomic_write_text.

    Returns:
        (ok, findings) — ok=False blocks the write if any critical finding.
    """
    findings = scan_content(text)
    ok = not has_blocking_findings(findings)
    return ok, findings


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python vault_secret_scan.py <file_or_dir>")
        sys.exit(1)

    target = Path(sys.argv[1])
    if target.is_file():
        findings = scan_note(target)
        if findings:
            print(f"Found {len(findings)} potential secret(s) in {target}:")
            for f in findings:
                print(
                    f"  [{f['severity']}] {f['pattern_id']} at line {f['line_hint']}: {f['match_redacted']}"
                )
        else:
            print(f"No secrets found in {target}")
        sys.exit(1 if findings else 0)
    elif target.is_dir():
        total_findings = 0
        for md in sorted(target.rglob("*.md")):
            findings = scan_note(md)
            if findings:
                total_findings += len(findings)
                print(f"{md}:")
                for f in findings:
                    print(
                        f"  [{f['severity']}] {f['pattern_id']} at line {f['line_hint']}: {f['match_redacted']}"
                    )
        print(f"\nTotal: {total_findings} findings")
        sys.exit(1 if total_findings else 0)
    else:
        print(f"Not found: {target}")
        sys.exit(1)
