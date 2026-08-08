"""AP-52 — el error se emite fuera del contrato del catálogo.

La norma salió de la caracterización maliciosa: invocar las tools de forma
malformada y mirar **cómo** fallan. El grueso estaba limpio; el hallazgo fue la
forma del envelope cuando la tool falla bien:

    {"ok": false, "error": "action='merge' requires --source"}

Correcto como frase, roto como contrato. El consumidor no lee la frase — decide
por `error_code` y `recovery.action`, que ese envelope no trae.

Estos tests cubren tres cosas distintas, y conviene no confundirlas:

* **Detección** (`CASOS`): que el detector marque lo que la norma dice y no
  marque lo que no. Es la parte que más falsos positivos ha costado en este repo.
* **Baseline**: que esté congelada, al día, y que solo pueda encoger.
* **Caracterización**: que la superficie de error medida siga comportándose como
  se midió — que es lo que #45 pedía congelar.
"""

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_error_contract as vec  # noqa: E402
import vault_gate  # noqa: E402
import vault_mcp_catalog  # noqa: E402
import vault_norms  # noqa: E402

SPEC = json.loads(
    (REPO_ROOT / "vault-sandbox" / "00_System" / "tool-spec.json").read_text(
        encoding="utf-8"
    )
)["tools"]


# ── Detección ──────────────────────────────────────────────────────────────

#: (fragmento, debe_marcarse, por qué)
CASOS = [
    (
        'def f():\n    return {"ok": False, "error": "falta --source"}\n',
        True,
        "el caso literal de vault_merge: sin error_code no hay nada que decidir",
    ),
    (
        'def f():\n    return {"ok": False, "message": "no se pudo leer"}\n',
        True,
        "message en vez de error es la misma carencia con otro nombre",
    ),
    (
        'def f():\n    return {"ok": False, "tool": "x", "error": "y"}\n',
        True,
        "llevar tool no repone error_code",
    ),
    (
        'def f():\n    return {"ok": False, "error": "y", "error_code": "MISSING_ARG"}\n',
        False,
        "con error_code el envelope está en contrato",
    ),
    (
        'def f():\n    return {"ok": True, "error": None}\n',
        False,
        "no es un envelope de error",
    ),
    (
        'def f():\n    return {"error": "suelto"}\n',
        False,
        "sin ok: False no es un envelope de salida; marcarlo sería ruido",
    ),
    (
        'def f():\n    return {"ok": False, "count": 0}\n',
        False,
        "sin marca de envelope puede ser cualquier estructura interna: la norma "
        "prefiere no verlo a inventárselo",
    ),
    (
        'def f():\n    return {"ok": ok_var, "error": "y"}\n',
        False,
        "ok no es constante: el detector no adivina el valor en runtime",
    ),
]


@pytest.mark.parametrize("fuente,marcado,motivo", CASOS)
def test_deteccion(fuente, marcado, motivo, tmp_path, monkeypatch):
    modulo = tmp_path / "vault_caso.py"
    modulo.write_text(fuente, encoding="utf-8")
    monkeypatch.setattr(vec, "SCRIPTS_DIR", tmp_path)

    encontrados = vec.offenders()
    assert bool(encontrados) is marcado, motivo


def test_se_excluye_a_si_misma_y_al_contrato(tmp_path, monkeypatch):
    """`vault_errors*` define el contrato: sus literales SON la definición.

    Y el propio detector no puede contarse: sus `CASOS` de prueba y su docstring
    contienen justo la forma que persigue. Es la misma exclusión que hace
    `vault_blame_audit`, y por el mismo motivo.
    """
    fuente = 'x = {"ok": False, "error": "definicion"}\n'
    for nombre in ("vault_errors.py", "vault_errors_catalog.py", vec.Path(vec.__file__).name):
        (tmp_path / nombre).write_text(fuente, encoding="utf-8")
    monkeypatch.setattr(vec, "SCRIPTS_DIR", tmp_path)
    assert vec.offenders() == []


# ── Baseline ───────────────────────────────────────────────────────────────

def test_la_baseline_esta_congelada_y_al_dia():
    r = vec.scan()
    assert r["ok"], f"deuda AP-52 nueva: {r['new_offenders']}"
    assert not r["resolved_since_baseline"], (
        f"deuda saldada sin recongelar: {r['resolved_since_baseline']} — "
        "corre `python scripts/vault_error_contract.py --freeze`"
    )


def test_la_baseline_solo_puede_encoger(monkeypatch):
    """Un sitio nuevo rompe; uno resuelto, no.

    La asimetría es la norma entera: si un sitio nuevo no rompiera, la baseline
    sería una lista de deseos.
    """
    monkeypatch.setattr(
        vec, "offenders",
        lambda: [{"firma": "vault_inventado.py::main::deadbeef",
                  "site": "vault_inventado.py:1", "module": "vault_inventado.py",
                  "line": 1, "keys": ["error", "ok"]}],
    )
    assert not vec.scan()["ok"], "un sitio nuevo debe romper el guard"


def test_la_clave_de_la_baseline_es_el_sitio_y_no_un_conteo():
    """Una baseline por conteo se salda arreglando uno y estrenando otro."""
    sitios = vec.load_baseline()
    assert sitios, "la baseline no puede estar vacía"
    assert all(":" in s for s in sitios), "las claves deben ser modulo:linea"


def test_check_no_escribe_la_baseline():
    antes = (REPO_ROOT / "scripts" / "error-contract-baseline.json").read_bytes()
    vec.scan()
    despues = (REPO_ROOT / "scripts" / "error-contract-baseline.json").read_bytes()
    assert antes == despues, "--check no debe tener side effects"


# ── Registro y enforcement ─────────────────────────────────────────────────

def test_la_norma_esta_registrada_con_enforcement_real():
    norma = next((n for n in vault_norms.NORM_CATALOG if n["code"] == "AP-52"), None)
    assert norma is not None, "AP-52 no está en NORM_CATALOG"
    assert norma["enforcement"] != "manual", "regla 5: ninguna norma nueva es manual"
    assert norma["tools_enforcing"] == ["vault_error_contract --check --strict"]


def test_la_norma_tiene_seccion_en_el_manifiesto():
    r = vault_norms.framework_drift_check()
    assert "AP-52" not in r["norms_without_section"]


def test_es_una_puerta_de_cierre():
    """Un guard que no está en la puerta es un guard que no corre (AP-42)."""
    scripts = {p["cmd"][0] for p in vault_gate.PUERTAS}
    assert "vault_error_contract.py" in scripts


def test_esta_en_el_catalogo_y_en_el_tool_spec():
    assert "vault_error_contract" in vault_mcp_catalog.TOOLS_CATALOG
    assert "vault_error_contract" in vault_mcp_catalog.GROUPS["Normas"]
    assert SPEC["vault_error_contract"]["status"] == "active"


# ── Caracterización de la superficie de error ──────────────────────────────

def _tools_con_argumentos_obligatorios():
    return sorted(
        nombre for nombre, meta in vault_mcp_catalog.TOOLS_CATALOG.items()
        if meta.get("script") and SPEC.get(nombre, {}).get("required_args")
    )


@pytest.mark.parametrize("tool", _tools_con_argumentos_obligatorios())
def test_la_invocacion_vacia_se_rechaza_sin_traceback(tool):
    """Lo congelado por la caracterización maliciosa.

    Una tool a la que le faltan argumentos obligatorios debe rechazar la
    invocación, no caerse con un traceback ni —peor— seguir adelante. El
    criterio de "malformado" es `required_args` del tool-spec y no el mío: la
    primera versión de la sonda contó 26 falsos positivos por dar por hecho que
    invocar sin argumentos es siempre un abuso, cuando para media superficie es
    el contrato. AP-44 cometida dentro de la caracterización.
    """
    script = REPO_ROOT / "scripts" / vault_mcp_catalog.TOOLS_CATALOG[tool]["script"]
    proc = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO_ROOT), timeout=60,
    )
    assert proc.returncode != 0, f"{tool} aceptó una invocación sin sus obligatorios"
    assert "Traceback (most recent call last)" not in (proc.stderr or ""), (
        f"{tool} se cae con traceback en vez de rechazar: {proc.stderr[-400:]}"
    )


def test_un_flag_desconocido_no_produce_traceback():
    """La otra sonda, sobre una muestra: argparse rechaza, nadie explota.

    Se corre sobre las tools de Normas y no sobre las 94 porque el barrido
    completo son ~90 subprocesos y la suite ya dura 17 minutos. El barrido
    completo se hizo una vez, a mano, y su resultado está en la sección AP-52
    del manifiesto: 92/92.
    """
    for tool in sorted(vault_mcp_catalog.GROUPS["Normas"]):
        meta = vault_mcp_catalog.TOOLS_CATALOG[tool]
        if not meta.get("script"):
            continue
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / meta["script"]),
             "--parametro-que-no-existe"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(REPO_ROOT), timeout=60,
        )
        assert proc.returncode != 0, f"{tool} aceptó un flag inexistente"
        assert "Traceback (most recent call last)" not in (proc.stderr or ""), tool


def test_el_detector_no_se_mide_por_texto():
    """Por AST, no por subcadena — el error que ya costó una ronda en AP-51.

    Un detector por texto contaría los ejemplos de este mismo fichero y los de
    la docstring de la tool, que describen la infracción para explicarla.
    """
    fuente = (REPO_ROOT / "scripts" / "vault_error_contract.py").read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    usa_ast = any(
        isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "ast"
        for n in ast.walk(arbol)
    )
    assert usa_ast, "el detector debe recorrer el AST, no el texto"
