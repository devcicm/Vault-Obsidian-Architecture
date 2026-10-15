"""AP-12, AP-18, AP-27 y AP-31: el detector existía y ningún test lo tocaba.

Medido en v41.2: las cuatro estaban en la baseline de la capa 4 —sin puerta
ni test— y las cuatro tienen detección real en `vault_audit` (y AP-12 también
en `vault_norms_scan`): `PENALIZACIONES` las pesa en el healthIndex. Aquí se
ejercita cada detector contra un vault mínimo, en el caso que la norma
describe y en su contrario. No prueba el enforcement completo; prueba que el
detector existe, corre y distingue.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_audit as va  # noqa: E402
import vault_norms  # noqa: E402

FM_COMPLETO = ("id: {id}\ntitle: {t}\ntype: knowledge\nstatus: activo\ntags: [x]\n"
               "agent: test\ncreatedAt: 2026-10-09\nupdatedAt: 2026-10-09\n"
               "cia_integrity: medium\ncia_availability: medium\ncia_sensitivity: internal")


def _vault(tmp_path: Path) -> Path:
    import vault_io

    root = tmp_path / "v"
    for sec in ("00_System", "07_Knowledge", "08_Learning", "99_Index"):
        (root / sec).mkdir(parents=True)
    vault_io.set_vault_root(root)
    return root


def _nota(root: Path, rel: str, fm: str, cuerpo: str = "Cuerpo de la nota.\n") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes((f"---\n{fm}\n---\n\n{cuerpo}").encode("utf-8"))
    return p


def test_ap12_el_contrato_y_el_scan_ven_la_nota_sin_id(tmp_path):
    root = _vault(tmp_path)
    sin_id = _nota(root, "07_Knowledge/sin-id.md",
                   FM_COMPLETO.format(id="x", t="Sin id").replace("id: x\n", ""))
    completa = _nota(root, "07_Knowledge/completa.md", FM_COMPLETO.format(id="c", t="Completa"))

    meta = va._detect_missing_metadata([sin_id, completa])
    faltas = {e["path"]: e["missing"] for e in meta["missing_contract"]}
    assert "id" in faltas.get("07_Knowledge/sin-id.md", []), "AP-12: el contrato no ve el id ausente"
    assert "07_Knowledge/completa.md" not in faltas, "AP-12: marca una nota completa"

    codigos = {n["code"] for n in vault_norms.vault_norms_scan("07_Knowledge/sin-id.md")["applicable_norms"]}
    assert "AP-12" in codigos
    codigos = {n["code"] for n in vault_norms.vault_norms_scan("07_Knowledge/completa.md")["applicable_norms"]}
    assert "AP-12" not in codigos


def test_ap18_ve_el_contenido_identico_entre_carpetas(tmp_path):
    root = _vault(tmp_path)
    fm = FM_COMPLETO.format(id="d", t="Duplicada")
    a = _nota(root, "07_Knowledge/dup.md", fm)
    b = _nota(root, "08_Learning/dup.md", fm)
    c = _nota(root, "07_Knowledge/otra.md", FM_COMPLETO.format(id="o", t="Otra"))
    d = _nota(root, "07_Knowledge/otra-copia.md", FM_COMPLETO.format(id="o", t="Otra"))

    dups = va._detect_cross_folder_duplicates([a, b, c, d])
    assert [sorted(x["files"]) for x in dups] == [["07_Knowledge/dup.md", "08_Learning/dup.md"]], (
        "AP-18: solo cuenta el duplicado entre carpetas distintas")


def test_ap27_ve_la_nota_de_seccion_sin_type(tmp_path):
    root = _vault(tmp_path)
    sin_tipo = _nota(root, "07_Knowledge/sin-tipo.md",
                     FM_COMPLETO.format(id="s", t="Sin tipo").replace("type: knowledge\n", ""))
    con_tipo = _nota(root, "07_Knowledge/con-tipo.md", FM_COMPLETO.format(id="t", t="Con tipo"))

    faltan = {e["path"] for e in va._detect_missing_metadata([sin_tipo, con_tipo])["missing_type"]}
    assert faltan == {"07_Knowledge/sin-tipo.md"}, "AP-27"


def _grafo(root: Path, total: int, tipadas: int) -> None:
    entidad = root / "06_Diagrams" / "entity"
    entidad.mkdir(parents=True, exist_ok=True)
    (entidad / "dominio-relations.json").write_text("{}", encoding="utf-8")
    (root / "99_Index" / "graph-enriched.json").write_text(json.dumps({
        "metadata": {"total_edges": total, "typed_edges": tipadas,
                     "merged_at": "2026-10-09T00:00:00Z"},
    }), encoding="utf-8")


def test_ap31_penaliza_el_grafo_casi_sin_predicates(tmp_path):
    root = _vault(tmp_path)
    _grafo(root, total=100, tipadas=2)
    r = va._detect_graph_knowledge_antipatterns()
    assert r["ap31_typed_ratio"] == 0.02
    assert r["ap31_penalty"] > 0, "AP-31: no penaliza un grafo con 2% de aristas tipadas"


def test_ap31_no_penaliza_el_grafo_tipado(tmp_path):
    root = _vault(tmp_path)
    _grafo(root, total=100, tipadas=60)
    r = va._detect_graph_knowledge_antipatterns()
    assert r["ap31_penalty"] == 0, "AP-31: penaliza un grafo tipado"


def test_pat6_la_senal_del_patron_se_mide_grafo_viejo_o_ausente(tmp_path):
    """PAT-6: su señal es «graph-enriched.json existe y tiene menos de 24 h».

    La mide `_detect_graph_knowledge_antipatterns` como `graph_enriched_stale`
    (el audit la pesa bajo AP-35, el silo que el patrón evita)."""
    root = _vault(tmp_path)
    _grafo(root, total=10, tipadas=10)
    enriquecido = root / "99_Index" / "graph-enriched.json"
    datos = json.loads(enriquecido.read_text(encoding="utf-8"))
    datos["metadata"]["merged_at"] = "2020-01-01T00:00:00Z"
    enriquecido.write_text(json.dumps(datos), encoding="utf-8")
    assert va._detect_graph_knowledge_antipatterns()["ap35_silo_flags"]["graph_enriched_stale"], "PAT-6"

    enriquecido.unlink()
    assert va._detect_graph_knowledge_antipatterns()["ap35_silo_flags"]["graph_enriched_stale"], "PAT-6"


def test_pat6_un_grafo_recien_enriquecido_no_esta_viejo(tmp_path):
    from datetime import datetime, timezone

    root = _vault(tmp_path)
    _grafo(root, total=10, tipadas=10)
    enriquecido = root / "99_Index" / "graph-enriched.json"
    datos = json.loads(enriquecido.read_text(encoding="utf-8"))
    datos["metadata"]["merged_at"] = datetime.now(timezone.utc).isoformat()
    enriquecido.write_text(json.dumps(datos), encoding="utf-8")
    assert not va._detect_graph_knowledge_antipatterns()["ap35_silo_flags"]["graph_enriched_stale"], "PAT-6"


def test_pat3_la_sombra_resuelta_sale_de_canonical_shadow(tmp_path):
    """PAT-3: su señal es «canonicalShadow reducido después de aplicar».

    Aplicarlo sin borrar (no-derogación) es anotar `superseded_by:` en la
    sombra hacia la canónica: el par deja de ser deuda y queda publicado en
    `resueltos`, de modo que la sanación se ve en vez de desaparecer."""
    root = _vault(tmp_path)
    canonica = _nota(root, "07_Knowledge/gateway-de-pagos.md", "title: Gateway de pagos")
    sombra = _nota(root, "08_Learning/gateway-de-pago.md", "title: Gateway de pago")
    antes = va._detect_canonical_shadow([canonica, sombra])
    assert len(antes) == 1, "PAT-3: el par no aparece antes de aplicar"

    _nota(root, "08_Learning/gateway-de-pago.md",
          'title: Gateway de pago\nsuperseded_by: "[[07_Knowledge/gateway-de-pagos]]"')
    resueltos = []
    despues = va._detect_canonical_shadow([canonica, sombra], resueltos=resueltos)
    assert despues == [], "PAT-3: canonicalShadow no se reduce tras aplicar"
    assert resueltos and resueltos[0]["canonica"] == "07_Knowledge/gateway-de-pagos.md"


def test_pat4_snapshot_y_report_distinguen_cero_regresiones_de_una(tmp_path, monkeypatch):
    """PAT-4: fase 1 (snapshot) y fase 4 (report) con `vault_drift_detect`.

    La señal del patrón —cero regresiones entre snapshot y estado final— solo
    se puede leer si el report dice cero cuando nada cambió y no cero cuando
    algo cambió. Se ejercita sobre una carpeta sin git (backend por hash)."""
    import vault_drift_detect as dd

    _vault(tmp_path)
    codigo = tmp_path / "src"
    codigo.mkdir()
    (codigo / "a.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(dd, "_has_git", lambda p: False)

    assert dd.vault_drift_detect(str(codigo), "pat4", mode="snapshot")["ok"]
    sin_cambio = dd.vault_drift_detect(str(codigo), "pat4", mode="report")
    assert sin_cambio["summary"]["total_changed"] == 0, "PAT-4: regresión inventada"

    (codigo / "a.py").write_text("x = 2\n", encoding="utf-8")
    con_cambio = dd.vault_drift_detect(str(codigo), "pat4", mode="report")
    assert con_cambio["summary"]["modified"] == 1, "PAT-4: el report no ve el cambio"
