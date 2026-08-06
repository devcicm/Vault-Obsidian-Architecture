"""Toda escritura de nota pasa por el write path canónico.

`atomic_write_text` no es una comodidad: es donde viven el escaneo de secretos,
el saneado de encoding y el temp+replace. Trece sitios escribían con
`open(..., "w")` directo y se saltaban los tres a la vez.

El peor era `vault_security_scan`: la tool que existe para encontrar secretos
persistía el fragmento vulnerable —código ajeno, con la credencial dentro— por
la vía que no escanea. Verificarse con el propio criterio en vez de con el del
consumidor, sobre la propia especialidad (AP-44).

Y el escáner fallaba abierto en silencio (`except Exception: pass`): un guard
roto dejaba de proteger sin que ningún envelope lo dijera (AP-37).
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import vault_io  # noqa: E402
from vault_secret_scan import redact_secrets, scan_content  # noqa: E402

#: `vault_mcp_catalog` escribe `mcp/nodejs/tools-catalog.json`, que vive FUERA
#: de todo vault por definición: es un artefacto del repo del estándar, no un
#: dato del vault. Es la única excepción, y se declara aquí para que cualquier
#: otra aparezca en el test en vez de colarse.
#: `vault_io` es el write path: su `open(temp, "w")` en `_escribir_temporal` es
#: la escritura que todas las demás delegan aquí, y va DESPUÉS del escaneo y del
#: saneado. Se abre con un descriptor propio en vez de `Path.write_text` porque
#: `VAULT_FSYNC=1` sincroniza sobre ese mismo descriptor: en Windows, reabrir el
#: fichero en solo lectura para hacer `fsync` falla con `Bad file descriptor`.
_ESCRITURA_FUERA_DEL_VAULT = {
    "vault_mcp_catalog.py": "tools-catalog.json es del repo",
    "vault_io.py": "es el propio write path — el temp+replace vive ahí",
}

TOKEN_FALSO = "ghp_" + "a" * 36


def _escrituras_crudas(texto: str) -> int:
    """Cuenta `open(..., "w")` reales, no las menciones en comentarios."""
    return sum(
        1
        for linea in texto.splitlines()
        if 'open(' in linea
        and '"w"' in linea
        and not linea.lstrip().startswith("#")
    )


def test_ninguna_tool_escribe_saltandose_el_write_path():
    culpables = {
        py.name: _escrituras_crudas(py.read_text(encoding="utf-8"))
        for py in sorted(SCRIPTS.glob("vault_*.py"))
        if py.name not in _ESCRITURA_FUERA_DEL_VAULT
    }
    culpables = {k: v for k, v in culpables.items() if v}
    assert not culpables, (
        f"escriben en crudo, sin escaneo de secretos ni temp+replace: {culpables}"
    )


def test_la_excepcion_de_vault_io_es_solo_el_temporal():
    """Eximir el fichero entero dejaría entrar la siguiente escritura cruda.

    La exención es de UNA línea con nombre y sitio: la del temporal dentro de
    `_escribir_temporal`. Cualquier otra en `vault_io` sería exactamente lo que
    el test de arriba existe para cazar, escondida detrás de su propia excepción.
    """
    fuente = (SCRIPTS / "vault_io.py").read_text(encoding="utf-8")
    assert _escrituras_crudas(fuente) == 1
    cuerpo = fuente.split("def _escribir_temporal", 1)[1].split("\ndef ", 1)[0]
    assert _escrituras_crudas(cuerpo) == 1, (
        "la única escritura cruda de vault_io ya no está en _escribir_temporal"
    )


def test_el_informe_de_seguridad_no_persiste_la_credencial(tmp_path, monkeypatch):
    """El fragmento vulnerable llega redactado, no en claro."""
    import vault_security_scan

    vault = tmp_path / "vault"
    monkeypatch.setattr(vault_security_scan, "VAULT_ROOT", vault)
    monkeypatch.setattr(
        vault_security_scan, "VULNERABILITIES_DIR", vault / "02_Observability" / "vuln"
    )
    (vault / "02_Observability" / "vuln").mkdir(parents=True)

    hallazgo = {
        "ruleId": "S006",
        "category": "secrets",
        "severity": "critical",
        "file": "src/auth.ts",
        "line": 12,
        "owasp": "A02:2021",
        "cwe": "CWE-798",
        "snippet": f'const token = "{TOKEN_FALSO}";',
        "mitigation": "Mover el token a una variable de entorno.",
    }
    guardados = vault_security_scan.save_findings_to_vault([hallazgo], "demo")
    assert guardados, "la tool no escribió nada"

    for rel in guardados:
        texto = (vault / rel).read_text(encoding="utf-8")
        assert TOKEN_FALSO not in texto, f"el secreto quedó en claro en {rel}"


def test_la_redaccion_deja_el_codigo_legible():
    """Se redacta el valor, no el fragmento: el informe tiene que servir."""
    original = f'const token = "{TOKEN_FALSO}";\nconst url = "https://api.example.com";'
    redactado, hechos = redact_secrets(original)
    assert hechos >= 1
    assert TOKEN_FALSO not in redactado
    assert "const token =" in redactado, "se llevó por delante el código"
    assert "https://api.example.com" in redactado, "redactó lo que no era secreto"
    assert not scan_content(redactado), "el texto redactado todavía dispara el escáner"


def test_un_texto_sin_secretos_no_se_toca():
    limpio = "def suma(a, b):\n    return a + b\n"
    assert redact_secrets(limpio) == (limpio, 0)


def test_el_escaner_roto_queda_registrado(tmp_path, monkeypatch):
    """Fallar abierto está bien; fallar abierto EN SILENCIO no (AP-37)."""
    import vault_secret_scan

    monkeypatch.setattr(vault_io, "_ACTIVE_VAULT_ROOT", tmp_path)
    vault_io._ESCANER_DEGRADADO.clear()

    def escaner_roto(_texto):
        raise RuntimeError("patrón mal compilado")

    monkeypatch.setattr(vault_secret_scan, "vault_write_hook", escaner_roto)

    destino = tmp_path / "07_Knowledge" / "nota.md"
    vault_io.atomic_write_text(destino, "---\ntype: knowledge\n---\n\nCuerpo.\n")

    # La escritura NO se bloquea: un bug del guard no puede tirar el estándar.
    assert destino.exists()
    degradaciones = vault_io.scanner_degradations()
    assert degradaciones, "la escritura pasó sin escanear y nadie lo registró"
    assert "patrón mal compilado" in degradaciones[-1]["error"]
    registro = tmp_path / "00_System" / vault_io.SCANNER_DEGRADED_LOG
    assert registro.exists(), "no quedó constancia en disco"
    vault_io._ESCANER_DEGRADADO.clear()
