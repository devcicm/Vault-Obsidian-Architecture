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
            pedidas = []
            for p in partes[partes.index("--categories") + 1:]:
                if p.startswith("--"):
                    break
                pedidas.append(p)
            assert set(pedidas) <= set(vault_security_rules.CATEGORIAS) | {"all"}, linea


def test_un_path_relativo_del_repo_se_resuelve_desde_donde_se_ejecuta(scan, monkeypatch):
    """README y docstring documentan `--path "src/"` corriendo desde el repo,
    pero la ruta se resolvía solo contra la raíz del vault: desde el repo daba
    FILE_NOT_FOUND. La del vault se mira primero, como hasta ahora."""
    tool, tmp = scan
    repo = tmp / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "a.js").write_text("const x = 1;\n", encoding="utf-8")
    monkeypatch.chdir(repo)
    r = tool.vault_security_scan("src/", save_findings=False)
    assert r["ok"] is True, r
    assert r["filesScanned"] == 1, r


def test_el_path_relativo_al_vault_sigue_mandando(scan, monkeypatch):
    tool, tmp = scan
    vault = vault_io.get_vault_root()
    (vault / "src").mkdir()
    (vault / "src" / "a.js").write_text("const x = 1;\n", encoding="utf-8")
    (vault / "src" / "b.js").write_text("const y = 2;\n", encoding="utf-8")
    repo = tmp / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "c.js").write_text("const z = 3;\n", encoding="utf-8")
    monkeypatch.chdir(repo)
    assert tool.vault_security_scan("src/", save_findings=False)["filesScanned"] == 2



def test_las_cifras_de_reglas_no_estan_escritas_a_mano():
    """Docstring, epílogo, README y manifiesto decían «45 reglas en 13
    categorías» con 58 y 14 en `vault_security_rules` (AP-47). El código las
    deriva; la prosa no las repite, porque registrarlas en `vault_doc_counts`
    abría un cruce meta_toolkit -> gobernanza que la baseline no admite."""
    import re

    import vault_doc_counts
    import vault_security_rules
    import vault_security_scan

    reglas = sum(len(v) for v in vault_security_rules.REGLAS_POR_CATEGORIA.values())
    categorias = len(vault_security_rules.REGLAS_POR_CATEGORIA)
    assert f"{reglas} security rules across {categorias} categories" in vault_security_scan.__doc__
    cifra = re.compile(r"\d+\s+reglas(?: de (?:seguridad|detección))?(?: distribuidas)? en \d+ categor"
                       r"|\d+\s+reglas de (?:seguridad|detección)|activa las \d+ categorías")
    for doc in ("scripts/README.md", "vault-obsidian-architecture.md"):
        vivo = vault_doc_counts._live_body(ROOT / doc)
        assert not cifra.search(vivo), (doc, cifra.search(vivo).group(0))


def test_depth_no_promete_un_limite_que_no_aplica(scan):
    """`--depth` decía «Directory depth (1-5)» y el manifiesto «profundidad de
    recursión», pero `_escanear` recorre el árbol entero: el parámetro nunca
    llegaba. Aplicarlo ahora haría que el mismo comando mirara menos en
    silencio; se declara lo que hace."""
    import subprocess

    tool, tmp = scan
    hondo = tmp / "src" / "a" / "b" / "c" / "d"
    hondo.mkdir(parents=True)
    (hondo / "x.js").write_text("const x = 1;\n", encoding="utf-8")
    r = tool.vault_security_scan(str(tmp / "src"), depth=1, save_findings=False)
    assert r["filesScanned"] == 1, r
    assert r["depthApplied"] is False, r
    ayuda = subprocess.run([sys.executable, str(ROOT / "scripts" / "vault_security_scan.py"), "--help"],
                           capture_output=True, text=True, encoding="utf-8").stdout
    assert "not applied" in ayuda, ayuda
    manifiesto = (ROOT / "vault-obsidian-architecture.md").read_text(encoding="utf-8")
    assert "Profundidad de recursión en directorios (1–5)" not in manifiesto
