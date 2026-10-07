"""El chequeo de cumplimiento de `vault_standard_upgrade` mide con el contrato de nota.

Hasta v40.36 `_run_compliance_check` llevaba su propia lista de campos
(`id`, `title`, `createdAt`), una cuarta copia del contrato (AP-57) que no
coincidía con ninguna versión: ni con AP-12, ni con el validador vigente. Y
juzgaba el frontmatter con su propio criterio en vez del del consumidor
(AP-44): un regex que exigía `\n`, así que una nota con CRLF o con BOM no
tenía frontmatter, y un `in` sobre el texto, así que `title: 'id: x'`
contaba como si la nota llevara `id`. Un fichero ilegible restaba uno a los
cumplidores en vez de no sumar.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_contrato_nota as contrato  # noqa: E402
import vault_standard_upgrade as vsu  # noqa: E402

_COMPLETA = ("id: a\ntitle: x\ntype: note\nstatus: draft\ncreatedAt: '2026-01-01'\n"
             "updatedAt: '2026-01-01'\ntags: [a]\ncia_integrity: medium\n"
             "cia_availability: medium\ncia_sensitivity: internal\nagent: test\n")


def _vault(tmp_path, monkeypatch, notas):
    for rel, contenido in notas.items():
        ruta = tmp_path / rel
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(contenido.encode("utf-8"))
    monkeypatch.setattr(vsu, "_raiz", lambda: tmp_path)
    return vsu._run_compliance_check(vsu.CURRENT_VERSION)


def test_la_lista_de_campos_no_se_copia():
    assert not hasattr(vsu, "FM_REQUIRED_FIELDS")


def test_crlf_y_bom_tienen_frontmatter(tmp_path, monkeypatch):
    completa = "---\n" + _COMPLETA + "---\ncuerpo\n"
    assert not contrato.faltantes(
        {k: 1 for k in ("id", "title", "type", "status", "createdAt", "updatedAt", "tags",
                        "cia_integrity", "cia_availability", "cia_sensitivity", "agent")},
        "07_Knowledge/a.md")
    r = _vault(tmp_path, monkeypatch, {
        "07_Knowledge/crlf.md": completa.replace("\n", "\r\n"),
        "07_Knowledge/bom.md": "﻿" + completa,
    })
    assert r["notes_checked"] == 2
    assert r["frontmatter_compliance"] == 1.0


def test_un_campo_citado_dentro_de_otro_no_cuenta(tmp_path, monkeypatch):
    sin_id = _COMPLETA.replace("id: a\n", "").replace("title: x", "title: 'id: x'")
    r = _vault(tmp_path, monkeypatch, {"07_Knowledge/a.md": "---\n" + sin_id + "---\n"})
    assert r["frontmatter_compliance"] == 0.0


def test_los_indices_derivados_no_cuentan(tmp_path, monkeypatch):
    r = _vault(tmp_path, monkeypatch, {
        "07_Knowledge/index.md": "# índice\n",
        "07_Knowledge/a.md": "---\n" + _COMPLETA + "---\n",
    })
    assert r["notes_checked"] == 1
    assert r["frontmatter_compliance"] == 1.0


def test_mide_con_el_contrato_de_la_version_aplicada(tmp_path, monkeypatch):
    """Un vault en v30 se mide con lo que v30 exigía: id y title."""
    for rel, contenido in {"07_Knowledge/a.md": "---\nid: a\ntitle: x\n---\n"}.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(contenido, encoding="utf-8")
    monkeypatch.setattr(vsu, "_raiz", lambda: tmp_path)
    assert vsu._run_compliance_check("v30")["frontmatter_compliance"] == 1.0
    assert vsu._run_compliance_check("v30")["contract_version"] == "v30"
    assert vsu._run_compliance_check(vsu.CURRENT_VERSION)["frontmatter_compliance"] == 0.0
