"""AP-37 — no-op silencioso. Contrato de vault_noop_audit y de la baseline.

La invariante central no es "cero infractoras" (hoy son 53), sino que la deuda
sea **monótona decreciente**: puede encogerse, nunca crecer. Una tool nueva con
side effects nace conforme o el gate falla.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_mcp_catalog  # noqa: E402
import vault_noop_audit as vna  # noqa: E402
from vault_norms import NORM_CATALOG  # noqa: E402


# ─── La norma existe en el registro canónico ─────────────────────────────────


def test_ap37_esta_registrada():
    norma = next((n for n in NORM_CATALOG if n["code"] == "AP-37"), None)
    assert norma is not None, "AP-37 aplicada por una tool pero ausente de NORM_CATALOG"
    assert norma["enforcement"] != "manual"
    assert "vault_noop_audit" in " ".join(norma["tools_detecting"])


def test_la_tool_esta_en_el_catalogo_y_en_un_grupo():
    assert "vault_noop_audit" in vault_mcp_catalog.TOOLS_CATALOG
    agrupadas = {t for tools in vault_mcp_catalog.GROUPS.values() for t in tools}
    assert "vault_noop_audit" in agrupadas


# ─── La deuda no crece ───────────────────────────────────────────────────────


def test_la_baseline_existe_y_es_legible():
    assert vna.BASELINE_PATH.exists(), (
        "sin baseline el gate no tiene referencia y --strict pasa siempre"
    )
    data = json.loads(vna.BASELINE_PATH.read_text(encoding="utf-8"))
    assert data["norm"] == "AP-37"
    assert isinstance(data["tools"], list)


def test_la_deuda_esta_saldada_y_la_norma_es_un_guard_duro():
    """v39: la baseline llegó a 0, así que AP-37 dejó de ser tolerante.

    Con la lista vacía, cualquier tool con side effects y sin indicador aparece
    como `new_offenders` y `--strict` sale con 1. Este test es el que impide
    que alguien vuelva a llenarla: la baseline solo podía encoger, y ya no
    queda nada que encoger.
    """
    assert vna.load_baseline() == [], (
        f"la baseline volvió a tener deuda: {vna.load_baseline()}. AP-37 es un "
        f"guard duro desde v39 — corrige la tool en vez de recongelar"
    )
    assert not vna.offenders(), (
        f"tools sin indicador de trabajo: {[o['tool'] for o in vna.offenders()]}"
    )


def test_no_hay_infractoras_nuevas():
    """El test que falla cuando alguien añade una tool que no dice qué hizo."""
    result = vna.scan()
    assert result["ok"], (
        "tools nuevas sin indicador de trabajo: "
        f"{result['new_offenders']} — declara uno en tool-spec.json "
        f"(WORK_INDICATORS) o corrige la tool"
    )


def test_la_baseline_no_contiene_tools_inexistentes():
    """Deuda saldada que sigue en la baseline la readmitiría en silencio."""
    baseline = set(vna.load_baseline())
    fantasmas = sorted(baseline - set(vault_mcp_catalog.TOOLS_CATALOG))
    assert not fantasmas, f"baseline cita tools inexistentes: {fantasmas}"


def test_la_baseline_esta_al_dia():
    """Si hay deuda saldada sin recongelar, la lista permite regresiones."""
    result = vna.scan()
    assert not result["resolved_since_baseline"], (
        f"{result['resolved_since_baseline']} ya cumplen AP-37 pero siguen en la "
        "baseline: ejecuta `python scripts/vault_noop_audit.py --freeze`"
    )


# ─── El detector detecta ─────────────────────────────────────────────────────


def test_ok_a_secas_no_cuenta_como_indicador():
    """`ok` y `path` están siempre: admitirlos vaciaría la norma de contenido."""
    for campo in ("ok", "path", "tool", "action", "status"):
        assert campo not in vna.WORK_INDICATORS, (
            f"'{campo}' está presente en casi toda respuesta; como indicador de "
            "trabajo no distingue nada"
        )


def test_las_tools_nuevas_de_v39_cumplen_ap37():
    """Una norma que su propio autor no cumple no es una norma."""
    baseline = set(vna.load_baseline())
    for tool in ("vault_doc_counts", "vault_noop_audit", "vault_standard_upgrade"):
        assert tool not in baseline, f"{tool} debería cumplir AP-37 y no cumple"


def test_freeze_produce_una_baseline_que_deja_el_scan_limpio(monkeypatch, tmp_path):
    destino = tmp_path / "baseline.json"
    monkeypatch.setattr(vna, "BASELINE_PATH", destino)
    vna.freeze()
    assert vna.scan()["new_offenders"] == []


def test_freeze_se_niega_a_congelar_deuda_sin_precedente(tmp_path, monkeypatch):
    """`CLAUDE.md` promete `DEBT_WOULD_GROW` para los tres guards con baseline.

    De los tres era el único que no lo implementaba: `freeze()` reescribía la
    baseline con lo que hubiera. Con la lista en cero, una tool nueva sin
    indicador más un `--freeze` de rutina la congelaba y la puerta seguía
    verde. La deuda entra por donde nadie mira, y nadie mira el `--freeze`.
    """
    import vault_noop_audit as na

    monkeypatch.setattr(na, "offenders", lambda: [{"tool": "vault_inventada"}])
    monkeypatch.setattr(na, "load_baseline", lambda: [])
    salida = na.freeze()
    assert salida["ok"] is False
    assert salida["error_code"] == "DEBT_WOULD_GROW"
    assert "vault_inventada" in salida["message"]

    # `--admitir-nuevos` sí congela, y se comprueba contra una baseline de
    # usar y tirar: la de verdad vive en `scripts/` y un test que la reescriba
    # deja la deuda del repo en lo que el test inventó.
    falsa = tmp_path / "noop-baseline.json"
    monkeypatch.setattr(na, "BASELINE_PATH", falsa)
    assert na.freeze(admitir_nuevos=True)["ok"] is True
    assert json.loads(falsa.read_text(encoding="utf-8"))["tools"] == ["vault_inventada"]
