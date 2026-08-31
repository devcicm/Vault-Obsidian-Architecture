"""Registro central de reglas de seguridad OWASP/CWE.

Una sola declaración: las 45 reglas de escaneo de código viva aquí.
`vault_security_scan` las consume; `vault_log_error` acepta owasp_category y cwe_id
pero no necesita el mapeo completo — lo obtiene del finding que le pasa el escáner.

来源: vault_security_scan.py (original inline, extraído en v40.29).
No se duplica el dato en ningún otro módulo.
"""

from typing import Dict, List, Any

REGLAS_POR_CATEGORIA: Dict[str, List[Dict[str, Any]]] = {
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
            "pattern": r"(?i)(private[_-]?key|privkey)\s*[=:]\s*[\"']-----BEGIN",
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
            "pattern": r"(?i)(slack|discord|telegram)[_-]?token\s*[=:]\s*[\"'][^\"']{16,}",
            "severity": "critical",
            "owasp": "A02:2021",
            "cwe": "CWE-798",
        },
        {
            "id": "S008",
            "pattern": r"xox[baprs]-[0-9a-zA-Z]{10,}",
            "severity": "critical",
            "owasp": "A02:2021",
            "cwe": "CWE-798",
        },
        {
            "id": "S009",
            "pattern": r"(?i)(database|db)[_-]?connection[_-]?string.*password\s*[=:]",
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
        {
            "id": "C002",
            "pattern": r"shell\s*:\s*true",
            "severity": "high",
            "owasp": "A03:2021",
            "cwe": "CWE-78",
        },
    ],
    "xss": [
        {
            "id": "X001",
            "pattern": r"innerHTML\s*=\s*[^;]*\+",
            "severity": "high",
            "owasp": "A03:2021",
            "cwe": "CWE-79",
        },
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
        {
            "id": "X006",
            "pattern": r"srcdoc\s*=\s*[^;]*\+",
            "severity": "medium",
            "owasp": "A03:2021",
            "cwe": "CWE-79",
        },
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
        {
            "id": "K003",
            "pattern": r"Math\.random\s*\(\)",
            "severity": "medium",
            "owasp": "A02:2021",
            "cwe": "CWE-338",
        },
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
        {
            "id": "F003",
            "pattern": r"redirect\s*\(.*\+",
            "severity": "medium",
            "owasp": "A01:2021",
            "cwe": "CWE-601",
        },
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
        {
            "id": "CF001",
            "pattern": r"debug\s*:\s*true",
            "severity": "medium",
            "owasp": "A05:2021",
            "cwe": "CWE-11",
        },
        {
            "id": "CF002",
            "pattern": r"stack\s*:\s*true",
            "severity": "low",
            "owasp": "A05:2021",
            "cwe": "CWE-209",
        },
        {
            "id": "CF003",
            "pattern": r"app\.use\(helmet\)(?!.*contentSecurityPolicy)",
            "severity": "low",
            "owasp": "A05:2021",
            "cwe": "CWE-16",
        },
        {
            "id": "CF004",
            "pattern": r"\.env(?!\.)",
            "severity": "low",
            "owasp": "A05:2021",
            "cwe": "CWE-522",
        },
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

CATEGORIAS = list(REGLAS_POR_CATEGORIA.keys())

TOTAL_REGLAS = sum(len(v) for v in REGLAS_POR_CATEGORIA.values())

MITIGACIONES = {
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
