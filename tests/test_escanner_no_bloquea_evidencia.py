"""El escáner de secretos no bloquea evidencia legítima (y sigue cazando secretos).

Medido el 2026-11-08 auditando el repo antes de subir: el escáner marcaba
**cosas que no son credenciales**, y el guard de escritura del servidor MCP
—que usa este mismo escáner— rechazaba notas por eso:

- un separador de 40 `=` en Markdown (y el banner del propio servidor MCP);
- `token = document.createElementNS(...)` en el HTML generado de `.archify/`;
- un hash de commit de 40 caracteres (el caso que ya se corrigió una vez).

La regla que queda: **una clave es larga y mezcla clases**. Un identificador,
un nombre de función, un separador o un hash no lo son.

Y lo que no se negocia: las credenciales reales siguen saltando.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

from vault.gobernanza.secret_scan import scan_content  # noqa: E402


class TestLoQueNoEsSecreto:
    """Lo que el guard no puede bloquear."""

    def test_un_separador_de_40_iguales_no_es_una_clave(self):
        separador = "=" * 40
        assert len(separador) == 40, "el fixture debe medir el caso real"
        texto = "\n".join(["Ejemplo:", separador, "fin", ""])
        assert scan_content(texto) == []

    def test_un_hash_de_commit_no_es_una_clave(self):
        for sha in ("1db90da822904345980165b44b18917eff2fe257",
                    "1DB90DA822904345980165B44B18917EFF2FE257"):
            assert scan_content(f"El commit es {sha}.\n") == [], sha

    def test_una_asignacion_de_codigo_no_es_una_credencial(self):
        texto = "En el diagrama:\n\n    token = document.createElementNS(ns, 'g');\n"
        assert scan_content(texto) == []

    def test_un_token_corto_en_prosa_no_es_una_credencial(self):
        assert scan_content('La variable `token = "abc123"` guarda el valor.\n') == []


class TestLoQueSiEsSecreto:
    """Lo que el guard no puede dejar pasar."""

    def test_la_clave_de_ejemplo_de_aws_sigue_saltando(self):
        texto = "AWS usa wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY.\n"
        assert any(h["pattern_id"] == "aws_secret_key"
                   for h in scan_content(texto))

    def test_una_api_key_asignada_sigue_saltando(self):
        texto = 'api_key = "sk-Ab3dEfGh1jKlMnOpQrStUvWxYz456789"\n'
        assert any(h["pattern_id"] == "api_key_assignment"
                   for h in scan_content(texto))

    def test_un_secret_asignado_largo_sigue_saltando(self):
        texto = 'client_secret = "Xy9zAbCdEfGh1jKlMnOpQrStUvWxYz"\n'
        assert any(h["pattern_id"] == "api_key_assignment"
                   for h in scan_content(texto))
