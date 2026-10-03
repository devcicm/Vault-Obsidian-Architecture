"""Todo consumidor del catálogo valida contra los params que la CLI acepta (AP-40 / AP-57).

`reconciled_params` es el dueño: lo que el MCP publica sale de argparse. Medido
2026-10-02, `vault_mcp.py` (show/validate) y `cli/registry.py` seguían leyendo
`TOOLS_CATALOG[t]["params"]` crudo, con 81 params en 41 tools que el script no
acepta. `validate vault_ai_decision` exigía `decision` —inexistente— y no
`decision_type`, que es obligatorio; `cli/safety` marcaba `decision_type` como
CONTRACT-UNKNOWN y aceptaba `decision` como declarado.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

_DECISION = {
    "project": "demo", "title": "t", "decision_type": "security",
    "description": "d", "rationale": "una justificación de más de veinte caracteres",
}


def _validate(params):
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_mcp.py"), "validate",
         "vault_ai_decision", "--params", json.dumps(params)],
        capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
    )
    return json.loads(r.stdout)


def test_ap40_validate_acepta_lo_que_la_cli_acepta():
    assert _validate(_DECISION)["ok"] is True


def test_ap40_validate_exige_lo_que_la_cli_exige():
    sin_tipo = {k: v for k, v in _DECISION.items() if k != "decision_type"}
    errores = _validate(sin_tipo)["errors"]
    assert any("decision_type" in e for e in errores)


def test_ap40_validate_conserva_los_validadores_declarados():
    corto = dict(_DECISION, rationale="corta")
    assert any("rationale" in e for e in _validate(corto)["errors"])


def test_ap57_el_registro_de_la_cli_publica_los_params_reales():
    from cli.registry import load_registry
    from vault_mcp_catalog import argparse_params

    fantasma = {}
    for nombre, frag in load_registry().items():
        reales = argparse_params(frag.script)
        if reales:
            sobran = set(frag.params) - set(reales)
            if sobran:
                fantasma[nombre] = sorted(sobran)
    assert fantasma == {}


def test_ap40_safety_no_marca_un_param_real_como_desconocido():
    from cli.registry import get
    from cli.safety import check_contract

    hallazgos = check_contract(get("vault_ai_decision"), dict(_DECISION, impact_level="low"))
    assert [h for h in hallazgos if h.code == "CONTRACT-UNKNOWN"] == []
