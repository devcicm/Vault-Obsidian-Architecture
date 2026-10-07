"""`vault_validate --check cumplimiento`: qué contratos cumple cada nota.

Medido el 2026-10-07 en dos vaults ajenos (solo lectura): el cumplimiento no es
monótono —una nota con `id` y `title` y nada más cumple de v25 a v36 y no
cumple ni v18 ni v37— y la ruptura real está en v37 (CIA, `agent`,
`createdAt`). Saberlo exigía lanzar `--contrato vNN` veinticuatro veces y
cruzar los resultados a mano.

El informe lo da en una pasada y con el mismo juez que `--contrato`
(`validate_frontmatter`), no con uno propio (AP-57). Es un informe: no
reprueba, y `ok` no depende de lo que mida.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_validate as vv  # noqa: E402
from vault_contrato_nota import VERSIONES_CON_CONTRATO  # noqa: E402

COMPLETA = (
    "---\nid: b\ntitle: B\ncreatedAt: 2026-10-07T00:00:00Z\nupdatedAt: 2026-10-07T00:00:00Z\n"
    "cia_integrity: medium\ncia_availability: medium\ncia_sensitivity: internal\n"
    "agent: system\ntags: [x]\ntype: knowledge\nstatus: draft\n---\n\n# B\n"
)


def _vault(tmp_path: Path) -> Path:
    import vault_io

    root = tmp_path / "v"
    (root / "07_Knowledge").mkdir(parents=True)
    (root / "07_Knowledge" / "a.md").write_text("---\nid: a\ntitle: A\n---\n\n# A\n", encoding="utf-8")
    (root / "07_Knowledge" / "b.md").write_text(COMPLETA, encoding="utf-8")
    vault_io.set_vault_root(root)
    return root


def _por_ruta(r):
    return {n["path"]: n for n in r["cumplimiento"]["notas"]}


def test_la_nota_con_id_y_title_cumple_de_v25_a_v36(tmp_path):
    _vault(tmp_path)
    a = _por_ruta(vv.vault_validate(folder="07_Knowledge", check="cumplimiento"))["07_Knowledge/a.md"]
    assert a["cumple"] == [f"v{n}" for n in range(25, 37)]
    assert a["version_mas_alta"] == "v36"
    assert a["cumple_vigente"] is False
    assert {"createdAt", "updatedAt", "type", "status"} <= set(a["falta_para_vigente"])


def test_la_nota_completa_cumple_la_vigente(tmp_path):
    _vault(tmp_path)
    b = _por_ruta(vv.vault_validate(folder="07_Knowledge", check="cumplimiento"))["07_Knowledge/b.md"]
    assert b["cumple_vigente"] is True
    assert b["version_mas_alta"] == VERSIONES_CON_CONTRATO[-1]
    assert b["falta_para_vigente"] == []


def test_el_resumen_cuenta_por_version_y_por_campo(tmp_path):
    _vault(tmp_path)
    r = vv.vault_validate(folder="07_Knowledge", check="cumplimiento")["cumplimiento"]
    assert r["total"] == 2
    assert r["cumplen_por_version"]["v30"] == 2
    assert r["cumplen_por_version"]["v41"] == 1
    assert r["cumplen_por_version"]["v18"] == 1
    assert r["faltantes_vigente"]["createdAt"] == 1


def test_es_un_informe_y_no_reprueba(tmp_path):
    _vault(tmp_path)
    r = vv.vault_validate(folder="07_Knowledge", check="cumplimiento")
    assert r["ok"] is True
    assert "invalid" not in r


def test_juzga_con_el_mismo_juez_que_contrato(tmp_path):
    """Cada versión que dice que cumple, `--contrato` la da por válida, y viceversa."""
    _vault(tmp_path)
    notas = _por_ruta(vv.vault_validate(folder="07_Knowledge", check="cumplimiento"))
    for v in VERSIONES_CON_CONTRATO:
        validas = set(vv.vault_validate(folder="07_Knowledge", check="frontmatter", contrato=v)["valid"])
        assert validas == {p for p, n in notas.items() if v in n["cumple"]}, v


def test_los_artefactos_derivados_no_cuentan_como_notas_que_cumplen(tmp_path):
    """Medido en un vault ajeno: 38 de los 40 «cumple v41» eran `index.md`.

    Un derivado no tiene contrato desde v37 y `validate_frontmatter` lo da por
    válido; contarlo inflaba justo la cifra que el informe existe para dar.
    """
    root = _vault(tmp_path)
    (root / "07_Knowledge" / "index.md").write_text("# indice" + chr(10), encoding="utf-8")
    r = vv.vault_validate(folder="07_Knowledge", check="cumplimiento")["cumplimiento"]
    assert "07_Knowledge/index.md" not in {n["path"] for n in r["notas"]}
    assert r["total"] == 2
    assert r["derivadas_excluidas"] == 1
    assert r["cumplen_por_version"]["v41"] == 1


def test_la_cli_acepta_el_modo():
    import subprocess

    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "vault_validate.py"), "--help"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert "cumplimiento" in p.stdout
