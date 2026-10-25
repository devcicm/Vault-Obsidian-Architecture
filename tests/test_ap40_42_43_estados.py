"""TD-0003 · AP-40/AP-42/AP-43 declaran su estado de ejecucion (GOAL B).

El defecto: cada control capturaba su fallo con `except ...: pass`; una
dependencia rota producia una auditoria "limpia". Estas pruebas fijan lo
contrario: un control que no corre se declara `no_ejecutado`, `completo` pasa a
False y la CLI `--strict` falla.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from vault.gobernanza.controles import (  # noqa: E402
    CONTROLES_OBLIGATORIOS,
    ejecutar_control,
    resumen,
)


def _runtime():
    """Import normal: el paquete `vault` resuelve sus imports relativos."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import vault.gobernanza.auditoria_runtime as modulo
    return modulo


def _modulo(ruta_relativa: str, nombre: str):
    spec = importlib.util.spec_from_file_location(nombre, ROOT / ruta_relativa)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


# ── Contrato de estados ──────────────────────────────────────────────────────

def test_control_sano_queda_ejecutado_con_sus_hallazgos():
    check = ejecutar_control("AP-40", lambda: 2)
    assert check["estado"] == "ejecutado"
    assert check["hallazgos"] == 2
    assert check["detalle"] is None


def test_dependencia_ausente_no_se_silencia():
    def _sin_dependencia():
        raise ImportError("No module named 'vault_mcp_catalog'")

    check = ejecutar_control("AP-40", _sin_dependencia)
    assert check["estado"] == "no_ejecutado"
    assert "dependencia_no_disponible" in check["detalle"]


def test_fallo_de_datos_se_declara_degradado():
    def _roto():
        raise ValueError("catalogo ilegible")

    check = ejecutar_control("AP-42", _roto)
    assert check["estado"] == "degradado"
    assert "ValueError" in check["detalle"]


def test_fallo_inesperado_se_declara_fallido():
    def _explota():
        raise RuntimeError("boom")

    check = ejecutar_control("AP-43", _explota)
    assert check["estado"] == "fallido"
    assert "RuntimeError" in check["detalle"]


def test_cero_hallazgos_no_es_prueba_de_ejecucion():
    """El centro del defecto: no_ejecutado tiene hallazgos 0 y NO es conforme."""
    check = ejecutar_control("AP-42", lambda: (_ for _ in ()).throw(ImportError("x")))
    assert check["hallazgos"] == 0
    assert resumen([check])["completo"] is False


def test_resumen_exige_los_tres_controles():
    solo_uno = [{"control": "AP-40", "estado": "ejecutado", "detalle": None,
                 "hallazgos": 0}]
    resultado = resumen(solo_uno)
    assert resultado["completo"] is False
    assert set(resultado["controles_faltantes"]) == {"AP-42", "AP-43"}


def test_resumen_completo_solo_con_los_tres_ejecutados():
    checks = [{"control": c, "estado": "ejecutado", "detalle": None,
               "hallazgos": 0} for c in CONTROLES_OBLIGATORIOS]
    assert resumen(checks)["completo"] is True
    checks[1]["estado"] = "degradado"
    assert resumen(checks)["completo"] is False


# ── El motor entrega los tres estados ────────────────────────────────────────

def test_la_fachada_ejecuta_y_entrega_los_tres_controles():
    fachada = _vault_norms()
    checks = fachada._checks_estandar(lambda *a: None)
    assert [c["control"] for c in checks] == list(CONTROLES_OBLIGATORIOS)
    assert all(c["estado"] in ("ejecutado", "degradado") for c in checks), checks


def test_la_fachada_registra_los_checks_para_el_envelope():
    fachada = _vault_norms()
    registrados = []
    fachada._checks_estandar(lambda *a: None, registrados.append)
    assert len(registrados) == 3


# ── El envelope declara cobertura ────────────────────────────────────────────

def test_el_envelope_incluye_checks_y_completo(tmp_path):
    runtime = _runtime()
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)

    def _insertar(flag, registrar):
        for control in CONTROLES_OBLIGATORIOS:
            registrar({"control": control, "estado": "ejecutado",
                       "detalle": None, "hallazgos": 0})

    resultado = runtime.auditar_runtime(raiz, insertar_checks_estandar=_insertar)
    assert resultado["completo"] is True
    assert len(resultado["checks"]) == 3
    # Lo que ya leian los consumidores sigue ahi.
    assert "total_violations" in resultado and "by_norm" in resultado


def test_el_envelope_marca_incompleto_cuando_un_control_no_corrio(tmp_path):
    runtime = _runtime()
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)

    def _insertar(flag, registrar):
        registrar({"control": "AP-40", "estado": "ejecutado", "detalle": None,
                   "hallazgos": 0})
        registrar({"control": "AP-42", "estado": "no_ejecutado",
                   "detalle": "dependencia_no_disponible", "hallazgos": 0})
        registrar({"control": "AP-43", "estado": "ejecutado", "detalle": None,
                   "hallazgos": 0})

    resultado = runtime.auditar_runtime(raiz, insertar_checks_estandar=_insertar)
    assert resultado["completo"] is False
    assert "AP-42" in resultado["controles_no_ejecutados"]


def test_el_camino_de_runtime_puro_no_inventa_checks(tmp_path):
    runtime = _runtime()
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    resultado = runtime.auditar_runtime(raiz)
    assert "checks" not in resultado
    assert "completo" not in resultado


# ── La CLI --strict es fail-closed ───────────────────────────────────────────

def _vault_norms():
    return _modulo("scripts/vault_norms.py", "vault_norms_td0003")


def test_la_cli_strict_falla_con_auditoria_incompleta(monkeypatch):
    modulo = _vault_norms()
    monkeypatch.setattr(modulo, "vault_norms_audit", lambda root=None: {
        "ok": True, "total_violations": 0, "by_norm": {}, "violations": [],
        "completo": False, "checks": [
            {"control": "AP-40", "estado": "no_ejecutado", "detalle": "x",
             "hallazgos": 0}]})
    monkeypatch.setattr(sys, "argv", ["vault_norms.py", "--audit", "--strict"])
    assert modulo.main() == 1


def test_la_cli_strict_pasa_con_auditoria_completa_y_limpia(monkeypatch):
    modulo = _vault_norms()
    monkeypatch.setattr(modulo, "vault_norms_audit", lambda root=None: {
        "ok": True, "total_violations": 0, "by_norm": {}, "violations": [],
        "completo": True, "checks": []})
    monkeypatch.setattr(sys, "argv", ["vault_norms.py", "--audit", "--strict"])
    assert modulo.main() == 0


def test_la_cli_strict_sigue_fallando_con_violaciones(monkeypatch):
    modulo = _vault_norms()
    monkeypatch.setattr(modulo, "vault_norms_audit", lambda root=None: {
        "ok": True, "total_violations": 1, "by_norm": {"AP-01": 1},
        "violations": [{"norm": "AP-01", "path": "x", "message": "m"}],
        "completo": True, "checks": []})
    monkeypatch.setattr(sys, "argv", ["vault_norms.py", "--audit", "--strict"])
    assert modulo.main() == 1
