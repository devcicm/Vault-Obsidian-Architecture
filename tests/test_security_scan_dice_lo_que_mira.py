"""`vault_security_scan` dice cuánto miró, no cuánto encontró.

Medido el 2026-10-17 al leer por qué el banco de AP-37 la daba «sin
escritura»: `filesScanned` era `len(results)`, y `scan_directory` solo añade a
`results` los ficheros con hallazgos. Diez ficheros limpios salían como «0
archivos escaneados — Riesgo: BAJO», igual que una ruta sin un solo fichero de
código: la tool que existe para dar confianza no distinguía «limpio» de «no
miré nada» (AP-60).
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import vault_io  # noqa: E402


@pytest.fixture
def scan(tmp_path):
    import vault_security_scan

    anterior = vault_io.get_vault_root()
    vault = tmp_path / "vault"
    vault.mkdir()
    vault_io.set_vault_root(vault)
    yield vault_security_scan, tmp_path
    vault_io.set_vault_root(anterior)


def test_cuenta_los_ficheros_limpios_que_escaneo(scan):
    tool, tmp = scan
    codigo = tmp / "src"
    codigo.mkdir()
    for i in range(3):
        (codigo / f"limpio_{i}.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    r = tool.vault_security_scan(str(codigo), save_findings=False)
    assert r["ok"] is True, r
    assert r["filesScanned"] == 3, r
    assert r["filesWithFindings"] == 0, r
    assert r["summary"].startswith("3 archivos escaneados"), r["summary"]


def test_separa_los_ficheros_con_hallazgos(scan):
    tool, tmp = scan
    codigo = tmp / "src"
    codigo.mkdir()
    (codigo / "limpio.py").write_text("x = 1\n", encoding="utf-8")
    (codigo / "sucio.py").write_text("import os\nos.system(input())\n", encoding="utf-8")
    r = tool.vault_security_scan(str(codigo), save_findings=False)
    assert r["filesScanned"] == 2, r
    assert r["filesWithFindings"] == (1 if r["totalFindings"] else 0), r


def test_sin_ficheros_de_codigo_no_afirma_riesgo_bajo(scan):
    """Las notas `.md` no están en `SCAN_EXTS`: el ejemplo del catálogo
    escaneaba `01_Projects` y respondía «Riesgo: BAJO» sin haber mirado nada."""
    tool, tmp = scan
    notas = tmp / "notas"
    notas.mkdir()
    (notas / "nota.md").write_text("# Nota\n\nTexto.\n", encoding="utf-8")
    r = tool.vault_security_scan(str(notas), save_findings=False)
    assert r["ok"] is True, r
    assert r["filesScanned"] == 0, r
    assert r["riskLevel"] == "SIN_DATOS", r
    assert "BAJO" not in r["summary"], r["summary"]


def test_una_categoria_que_no_existe_se_rechaza(scan):
    """El ejemplo del catálogo pedía `--categories secrets pii`: `pii` no es
    una categoría y se descartaba en silencio. Con solo ella el escaneo corría
    con cero reglas y salía limpio."""
    tool, tmp = scan
    codigo = tmp / "src"
    codigo.mkdir()
    (codigo / "a.py").write_text("x = 1\n", encoding="utf-8")
    r = tool.vault_security_scan(str(codigo), categories=["pii"], save_findings=False)
    assert r["ok"] is False and r["error_code"] == "INVALID_CATEGORY", r
    assert "pii" in r["message"], r


def test_las_categorias_separadas_por_comas_son_las_documentadas(scan):
    """README y docstring documentan `--categories "secrets,injection"`; con
    `nargs="*"` llegaba como una sola categoría inexistente."""
    tool, tmp = scan
    codigo = tmp / "src"
    codigo.mkdir()
    (codigo / "a.js").write_text('const password = "hunter22";\nspawn(cmd, { shell: true });\n',
                                 encoding="utf-8")
    con_coma = tool.vault_security_scan(str(codigo), categories=["secrets,command_injection"],
                                        save_findings=False)
    separadas = tool.vault_security_scan(str(codigo), categories=["secrets", "command_injection"],
                                         save_findings=False)
    assert con_coma["ok"] is True, con_coma
    assert separadas["totalFindings"] >= 2, separadas
    assert con_coma["totalFindings"] == separadas["totalFindings"], (con_coma, separadas)


def test_el_catalogo_no_promete_escanear_las_notas():
    from vault_mcp_catalog import TOOLS_CATALOG

    ficha = TOOLS_CATALOG["vault_security_scan"]
    assert "vault y código" not in ficha["purpose"], ficha["purpose"]
    assert ".md" in ficha["purpose"], ficha["purpose"]
    import vault_security_rules
    for linea in ficha["example"].splitlines():
        partes = linea.split()
        if "--categories" in partes:
            pedidas = partes[partes.index("--categories") + 1:]
            pedidas = [p for p in pedidas if not p.startswith("--")]
            assert set(pedidas) <= set(vault_security_rules.CATEGORIAS) | {"all"}, linea
