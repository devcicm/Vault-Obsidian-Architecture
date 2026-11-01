"""Contrato de vault_doc_counts — el guard anti-drift de cifras en documentación.

Estos tests protegen dos cosas distintas:

1. Que el guard *funcione* (detecta una cifra falsa, respeta el changelog,
   reescribe solo el número y no la frase).
2. Que la documentación del repo esté hoy alineada con el registro. Este
   segundo es el que falla cuando alguien escribe "34 grupos" a mano.
"""

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

import vault_doc_counts as vdc  # noqa: E402


# ─── El guard funciona ───────────────────────────────────────────────────────


def test_valores_vivos_se_derivan_del_registro():
    """Ninguna cifra del guard puede ser un literal congelado."""
    import vault_mcp_catalog
    import vault_registry
    from vault_norms import NORM_CATALOG

    assert vdc.count_tools_active() == len(vault_mcp_catalog.TOOLS_CATALOG)
    assert vdc.count_groups() == len(vault_mcp_catalog.GROUPS)
    assert vdc.count_norms() == len(NORM_CATALOG)
    assert vdc.count_sections() == len(vault_registry.standard_folders())


def test_cada_hecho_tiene_id_unico_valor_y_patrones():
    ids = [f["id"] for f in vdc.COUNTED_FACTS]
    assert len(ids) == len(set(ids)), f"ids duplicados: {ids}"
    for fact in vdc.COUNTED_FACTS:
        assert callable(fact["value"]), fact["id"]
        assert fact["patterns"], f"{fact['id']} sin patrones = hecho no vigilado"
        for pattern in fact["patterns"]:
            compiled = re.compile(pattern)
            assert compiled.groups >= 1, f"{pattern} no captura el número en group(1)"


def test_detecta_una_cifra_falsa(tmp_path, monkeypatch):
    doc = tmp_path / "FAKE.md"
    doc.write_text("El estándar tiene 999 tools activas hoy.\n", encoding="utf-8")
    monkeypatch.setattr(vdc, "REPO_ROOT", tmp_path)

    result = vdc.scan(docs=["FAKE.md"], include_slow=False)
    assert result["ok"] is False
    fallos = [m for m in result["mismatches"] if m["claimed"] == 999]
    assert fallos, result["mismatches"]
    assert fallos[0]["actual"] == vdc.count_tools_active()


def test_el_changelog_es_historia_y_no_se_vigila(tmp_path, monkeypatch):
    """Una cifra dentro del changelog es correcta para su versión."""
    doc = tmp_path / "FAKE.md"
    doc.write_text(
        "Hoy: 999 tools activas.\n\n## Changelog\n\n### v1 — 111 tools activas\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(vdc, "REPO_ROOT", tmp_path)

    result = vdc.scan(docs=["FAKE.md"], include_slow=False)
    reclamadas = {m["claimed"] for m in result["mismatches"]}
    assert 999 in reclamadas
    assert 111 not in reclamadas, "el guard entró en el changelog: eso es derogar historia"


def test_fix_reescribe_solo_el_numero(tmp_path, monkeypatch):
    doc = tmp_path / "FAKE.md"
    doc.write_text("Incluye 999 tools activas y nada más.\n", encoding="utf-8")
    monkeypatch.setattr(vdc, "REPO_ROOT", tmp_path)

    vdc.fix(docs=["FAKE.md"], include_slow=False)
    texto = doc.read_text(encoding="utf-8")
    assert texto == f"Incluye {vdc.count_tools_active()} tools activas y nada más.\n"


def test_fix_no_toca_el_changelog(tmp_path, monkeypatch):
    doc = tmp_path / "FAKE.md"
    original = "Hoy: 999 tools activas.\n\n## Changelog\n\n### v1 — 111 tools activas\n"
    doc.write_text(original, encoding="utf-8")
    monkeypatch.setattr(vdc, "REPO_ROOT", tmp_path)

    vdc.fix(docs=["FAKE.md"], include_slow=False)
    assert "111 tools activas" in doc.read_text(encoding="utf-8")


def test_un_registro_ilegible_no_tumba_el_guard(monkeypatch):
    """Un fallo al derivar una cifra se reporta, no revienta el proceso."""

    def _boom():
        raise RuntimeError("registro ilegible")

    fake = [{"id": "roto", "description": "x", "value": _boom, "patterns": [r"(\d+) x"]}]
    monkeypatch.setattr(vdc, "COUNTED_FACTS", fake)

    result = vdc.scan(docs=["README.md"], include_slow=False)
    assert result["ok"] is False
    assert result["errors"] and result["errors"][0]["fact"] == "roto"


# ─── La documentación del repo está alineada ─────────────────────────────────


def test_documentos_vigilados_existen():
    for rel in vdc.WATCHED_DOCS:
        assert (REPO_ROOT / rel).exists(), f"{rel} vigilado pero inexistente"


def test_ninguna_cifra_del_repo_miente():
    """El test de mayor palanca: falla en cuanto un doc envejece.

    Se omite el conteo de tests (`slow`) porque exigiría lanzar pytest desde
    dentro de pytest. Lo cubre el paso de CI, que corre sin `--no-slow`.
    """
    result = vdc.scan(include_slow=False)
    assert result["ok"], "\n".join(
        f"{m['file']}:{m['line']} [{m['fact']}] dice {m['claimed']}, real {m['actual']}"
        for m in result["mismatches"]
    ) or str(result["errors"])


def test_la_tool_esta_en_el_catalogo_canonico():
    import vault_mcp_catalog

    assert "vault_doc_counts" in vault_mcp_catalog.TOOLS_CATALOG
    agrupadas = {t for tools in vault_mcp_catalog.GROUPS.values() for t in tools}
    assert "vault_doc_counts" in agrupadas
    assert vault_mcp_catalog.TOOLS_CATALOG["vault_doc_counts"]["group"] == "Normas"


def test_una_cifra_historica_marcada_no_se_reescribe_y_se_publica(tmp_path, monkeypatch):
    """Fuera del changelog también hay historia: un censo hecho en v39.

    «41 de las 88 tools del catálogo no se han ejecutado» es una medida de un
    momento. El patrón de tools activas la atrapaba y `--fix` la llevó a 117,
    118, 119 y 120 con cada tool nueva: el censo dejó de decir lo que se midió.
    El marcador la exime solo a ella, y el envelope la lista para que eximir no
    sea una forma de esconder deriva viva.
    """
    doc = tmp_path / "FAKE.md"
    texto = ("Hoy: 999 tools activas.\n"
             "Entonces 41 de las 88 tools del catálogo no se ejecutaban. "
             "<!-- cifra histórica: censo de v39 -->\n")
    doc.write_bytes(texto.encode("utf-8"))
    monkeypatch.setattr(vdc, "REPO_ROOT", tmp_path)

    r = vdc.scan(docs=["FAKE.md"], include_slow=False)
    assert {m["claimed"] for m in r["mismatches"]} == {999}
    assert [(e["file"], e["line"], e["claimed"]) for e in r["historic_exempt"]] == [("FAKE.md", 2, 88)]

    vdc.fix(docs=["FAKE.md"], include_slow=False)
    nuevo = doc.read_text(encoding="utf-8")
    assert "41 de las 88 tools" in nuevo
    assert "999" not in nuevo


def test_el_marcador_exige_motivo(tmp_path, monkeypatch):
    """Sin motivo, el marcador es un interruptor para apagar el guard."""
    doc = tmp_path / "FAKE.md"
    doc.write_bytes("Son 88 tools del catálogo. <!-- cifra histórica -->\n".encode("utf-8"))
    monkeypatch.setattr(vdc, "REPO_ROOT", tmp_path)

    r = vdc.scan(docs=["FAKE.md"], include_slow=False)
    assert [m["claimed"] for m in r["mismatches"]] == [88]


def test_b04_las_tools_expuestas_por_mcp_salen_de_la_pasarela(tmp_path, monkeypatch):
    """«expone N de las M … (las otras K …)»: las dos partes se miden."""
    ruta = REPO_ROOT / "mcp" / "nodejs" / "tools-catalog.json"
    tools = json.loads(ruta.read_text(encoding="utf-8"))["tools"].values()
    expuestas = sum(1 for t in tools if t["exposed_via_mcp"])
    assert vdc.count_tools_mcp_expuestas() == expuestas
    assert expuestas + vdc.count_tools_mcp_no_expuestas() == vdc.count_tools_active()

    doc = tmp_path / "FAKE.md"
    doc.write_bytes("expone 1 de las tools; las otras 2 se ejecutan por CLI.\n"
                    .encode("utf-8"))
    monkeypatch.setattr(vdc, "REPO_ROOT", tmp_path)
    r = vdc.scan(docs=["FAKE.md"], include_slow=False)
    assert {m["fact"]: m["claimed"] for m in r["mismatches"]} == {
        "tools_mcp_expuestas": 1, "tools_mcp_no_expuestas": 2}


def test_b06_la_cifra_del_motivo_no_es_una_afirmacion(tmp_path, monkeypatch):
    """El motivo cita la medida; antes salía como segunda línea exenta."""
    doc = tmp_path / "FAKE.md"
    doc.write_bytes(("Entonces 41 de las 88 tools del catálogo no se ejecutaban. "
                     "<!-- cifra histórica: se midió con 88 tools activas -->\n")
                    .encode("utf-8"))
    monkeypatch.setattr(vdc, "REPO_ROOT", tmp_path)

    r = vdc.scan(docs=["FAKE.md"], include_slow=False)
    assert [(e["line"], e["claimed"]) for e in r["historic_exempt"]] == [(1, 88)]
    assert r["mismatches"] == []
    assert r["claims_checked"] == 1


def test_b02_fix_no_reescribe_una_fila_fechada_sin_marcador(tmp_path, monkeypatch):
    """«| 2026-10-05 | eran 88 tools activas |» es un registro, no el presente."""
    doc = tmp_path / "FAKE.md"
    texto = ("Hoy: 999 tools activas.\n"
             "| 2026-10-05 | eran 88 tools activas |\n")
    doc.write_bytes(texto.encode("utf-8"))
    monkeypatch.setattr(vdc, "REPO_ROOT", tmp_path)

    r = vdc.scan(docs=["FAKE.md"], include_slow=False)
    filas = {m["claimed"]: m["dated_row"] for m in r["mismatches"]}
    assert filas == {999: False, 88: True}, "la fila fechada sigue siendo discrepancia"

    f = vdc.fix(docs=["FAKE.md"], include_slow=False)
    nuevo = doc.read_text(encoding="utf-8")
    assert "| 2026-10-05 | eran 88 tools activas |" in nuevo
    assert "999" not in nuevo
    assert [(x["line"], x["claimed"], x["reason"]) for x in f["refused"]] == [
        (2, 88, "dated_row")]


def test_las_cifras_historicas_del_manifiesto_son_las_medidas():
    texto = (REPO_ROOT / "vault-obsidian-architecture.md").read_text(encoding="utf-8")
    assert "41 de las 88 tools del catálogo" in texto
    assert "`vault_smoke` recorre las 91 tools del catálogo" in texto


def test_el_desglose_python_js_se_vigila(tmp_path, monkeypatch):
    """`scripts/README.md` decía «120 tools (82 Python + 2 JS-native)».

    El total lo vigilaba un patrón; el desglose, ninguno, y se quedó en una
    suma que no daba. Las dos partes se derivan del catálogo.
    """
    import vault_mcp_catalog

    nativas = len(vault_mcp_catalog.NATIVE_JS_TOOLS)
    python = len(vault_mcp_catalog.TOOLS_CATALOG) - nativas
    doc = tmp_path / "FAKE.md"
    doc.write_bytes(f"(82 Python + {nativas + 5} JS-native)\n".encode("utf-8"))
    monkeypatch.setattr(vdc, "REPO_ROOT", tmp_path)

    r = vdc.scan(docs=["FAKE.md"], include_slow=False)
    reclamadas = {(m["claimed"], m["actual"]) for m in r["mismatches"]}
    assert (82, python) in reclamadas
    assert (nativas + 5, nativas) in reclamadas


def test_el_tamano_del_vocabulario_de_status_se_vigila(tmp_path, monkeypatch):
    """«Vocabulario de `status` (12 valores)» estaba en tres documentos vigilados
    sin patrón que la midiera: correcta hoy, a mano igual (AP-47)."""
    from vault_norms_catalog import STATUS_VOCAB

    real = len(STATUS_VOCAB)
    doc = tmp_path / "FAKE.md"
    doc.write_bytes((
        f"| Vocabulario de `status` ({real + 1} valores) | x |\n"
        f"Fuente única de `STATUS_VOCAB` ({real + 2} valores).\n"
        f"- **`STATUS_VOCAB` unificado** ({real + 3} valores) como fuente.\n"
    ).encode("utf-8"))
    monkeypatch.setattr(vdc, "REPO_ROOT", tmp_path)

    r = vdc.scan(docs=["FAKE.md"], include_slow=False)
    reclamadas = {(m["claimed"], m["actual"]) for m in r["mismatches"]}
    assert reclamadas == {(real + 1, real), (real + 2, real), (real + 3, real)}


def test_el_desglose_de_normas_por_familia_se_vigila(tmp_path, monkeypatch):
    """`README.md` decía «74 normas: 65 antipatrones», con el rango de la
    familia acabando en 62, «3 SP, 3 CN» y 79 normas en el catálogo (v41.3).

    El patrón de antipatrones lo vigilaba y `--fix` lo subió a 65; el total con
    dos puntos, el rango y las dos últimas familias no tenían patrón, así que la
    frase quedó a medio derivar: una cifra corregida al lado de cuatro que no.

    Los códigos de la frase se arman con `format`: escritos literales en el
    cuerpo de un test, la capa 4 del plano los cuenta como cobertura de esas
    normas, y este test no prueba ninguna de ellas.
    """
    from vault_norms_catalog import NORM_CATALOG

    def familia(p):
        return [n["code"] for n in NORM_CATALOG if n["code"].startswith(p + "-")]

    def ultimo(p):
        return max(int(c.split("-")[1]) for c in familia(p))

    doc = tmp_path / "FAKE.md"
    linea = "- 74 normas: 65 antipatrones ({a}-01–{a}-62), 5 patrones ({p}-1–{p}-5), 3 SP, 3 CN\n"
    doc.write_bytes(linea.format(a="AP", p="PAT").encode("utf-8"))
    monkeypatch.setattr(vdc, "REPO_ROOT", tmp_path)

    r = vdc.scan(docs=["FAKE.md"], include_slow=False)
    reclamadas = {(m["fact"], m["claimed"], m["actual"]) for m in r["mismatches"]}
    esperadas = {
        ("norms_total", 74, len(NORM_CATALOG)),
        ("norms_ap_ultimo", 62, ultimo("AP")),
        ("norms_pat", 5, len(familia("PAT"))),
        ("norms_pat_ultimo", 5, ultimo("PAT")),
        ("norms_sp", 3, len(familia("SP"))),
        ("norms_cn", 3, len(familia("CN"))),
    }
    assert {e for e in esperadas if e[1] != e[2]} <= reclamadas, reclamadas


def test_el_tamano_del_manifiesto_se_vigila_en_miles(tmp_path, monkeypatch):
    """«~6000 líneas» con 11.110 en el fichero: se publica en miles, que es la
    precisión que la frase promete, y se deriva del fichero."""
    real = vdc.count_spec_kilolineas()
    doc = tmp_path / "FAKE.md"
    doc.write_bytes(f"— ~{real + 5}000 líneas. y (~{real + 6}.000 líneas)\n".encode("utf-8"))
    monkeypatch.setattr(vdc, "REPO_ROOT", tmp_path)

    r = vdc.scan(docs=["FAKE.md"], include_slow=False)
    reclamadas = {(m["claimed"], m["actual"]) for m in r["mismatches"]}
    assert reclamadas == {(real + 5, real), (real + 6, real)}


def test_la_cifra_en_herramientas_se_vigila(tmp_path, monkeypatch):
    """A-19 — el manifiesto decía «expone sus 76 herramientas» y «| 76 herramientas
    con inputSchema» con 127 en el catálogo: ningún patrón miraba la palabra en
    castellano, y la tabla del MCP desglosaba «~10 tools rápidas en JavaScript» y
    «~66 tools via subprocess» sin que nadie lo comparase con `NATIVE_JS_TOOLS`.
    """
    import vault_mcp_catalog

    total = len(vault_mcp_catalog.TOOLS_CATALOG)
    nativas = len(vault_mcp_catalog.NATIVE_JS_TOOLS)
    doc = tmp_path / "FAKE.md"
    doc.write_bytes(("El vault expone sus 76 herramientas como servidor.\n"
                     "| **Tool Registry** | 76 herramientas con inputSchema completo |\n"
                     "| **JS-native backend** | ~10 tools rápidas en JavaScript puro |\n"
                     "| **Python backend** | ~66 tools via subprocess a `scripts/*.py` |\n"
                     ).encode("utf-8"))
    monkeypatch.setattr(vdc, "REPO_ROOT", tmp_path)

    r = vdc.scan(docs=["FAKE.md"], include_slow=False)
    reclamadas = sorted((m["line"], m["claimed"], m["actual"]) for m in r["mismatches"])
    assert reclamadas == [(1, 76, total), (2, 76, total), (3, 10, nativas), (4, 66, total - nativas)]


def test_herramientas_en_sentido_generico_no_casa(tmp_path, monkeypatch):
    """Los patrones son estrechos a propósito: «las 71 herramientas» de una
    retrospectiva o «herramientas de sistema de archivos» no son la cifra del
    catálogo, y un patrón genérico las reescribiría con cada tool nueva."""
    doc = tmp_path / "FAKE.md"
    doc.write_bytes(("Con el estándar en v40.29 y «las 71 herramientas» cuando eran 107.\n"
                     "Harnesses que pasan herramientas de sistema de archivos directas.\n"
                     ).encode("utf-8"))
    monkeypatch.setattr(vdc, "REPO_ROOT", tmp_path)

    r = vdc.scan(docs=["FAKE.md"], include_slow=False)
    assert r["mismatches"] == []
