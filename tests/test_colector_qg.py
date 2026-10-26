"""QA-RC-02g/h/i · subchecks con ejecucion propia, CLI real y CI ligada al run.

Cada subcheck tiene su verificador, su exit code, su artefacto y su SHA-256:
la puerta solo pasa si TODOS pasan. Se prueban los negativos que QA enumera
(subcheck ausente, fallido, no ejecutado, salida vacia, artefacto individual
ausente, comando pytest ejecutado como script) y la CLI como proceso real.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "audits" / "fase2") not in sys.path:
    sys.path.insert(0, str(ROOT / "audits" / "fase2"))


def _colector():
    spec = importlib.util.spec_from_file_location(
        "colector_qg", ROOT / "audits" / "fase2" / "colector_qg.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


SHA = "a" * 40
OTRO = "b" * 40
c = _colector()


class _Proc:
    def __init__(self, exit_code=0, stdout='{"ok": true}', stderr=""):
        self.returncode = exit_code
        self.stdout = stdout
        self.stderr = stderr


def _subchecks(gate: str) -> tuple:
    return tuple(c.SUBCONTRATOS[gate])


def _fake_ejecutar(salidas: dict, por_comando: bool = True):
    """Fake de subprocess: decide por verificador (texto del argv)."""
    def _ejecutar(argv, **kwargs):
        texto = " ".join(str(a) for a in argv)
        for clave, valor in salidas.items():
            if clave in texto:
                if isinstance(valor, _Proc):
                    return valor
                return _Proc(0, valor)
        return _Proc(0, '{"ok": true}')
    return _ejecutar


# ── QA-RC-02g: subchecks independientes ──────────────────────────────────────

def test_los_subchecks_de_cada_puerta_son_contratos_distintos():
    for gate, contrato in c.SUBCONTRATOS.items():
        assert contrato, gate
        for nombre, spec in contrato.items():
            assert spec["tipo"] in ("comando", "interno", "derivado", "externo")
            assert spec.get("verificador")


def test_un_subcheck_fallido_impide_la_puerta(tmp_path):
    """Un comando con exito y otro que falla: la puerta NO pasa."""
    salidas = {"reconciliar_archify.py": _Proc(1, "boom")}
    resultado = c.ejecutar_verificador(
        "QG-01", SHA, tmp_path / "salida",
        ejecutar=_fake_ejecutar(salidas))
    assert resultado["ok"] is False
    assert "reconciliador_archify" in resultado["fallidos"]
    assert resultado["checks"]["vault_arch"] == "ejecutado"


def test_un_subcheck_no_ejecutado_impide_la_puerta(tmp_path):
    """pip_audit sin interprete: no_ejecutado, la puerta no pasa."""
    resultado = c.ejecutar_verificador(
        "QG-04", SHA, tmp_path / "salida", ejecutar=_fake_ejecutar({}))
    assert resultado["ok"] is False
    assert resultado["checks"]["pip_audit"] == "no_ejecutado"


def test_una_salida_vacia_no_acredita(tmp_path):
    def _vacia(argv, **kwargs):
        return _Proc(0, "")
    resultado = c.ejecutar_verificador(
        "QG-01", SHA, tmp_path / "salida", ejecutar=_vacia)
    assert resultado["ok"] is False
    assert resultado["checks"]["vault_arch"] == "degradado"
    recibo = json.loads(Path(resultado["recibo"]).read_text(encoding="utf-8"))
    assert recibo["subchecks"]["vault_arch"]["detalle"] == "SALIDA_VACIA"


def test_el_comando_de_pruebas_se_ejecuta_como_pytest(tmp_path):
    """QA-RC-02g: un .py de pytest ejecutado como script devuelve 0 sin correr
    nada; el comando correcto es `python -m pytest <fichero>`."""
    comando = c.COMANDOS["operaciones_destructivas"]
    assert comando[0] == "-m" and comando[1] == "pytest", comando
    assert comando[2].endswith(".py")


def test_cada_subcheck_tiene_su_propio_artefacto(tmp_path):
    resultado = c.ejecutar_verificador(
        "QG-00", SHA, tmp_path / "salida", ejecutar=_fake_ejecutar({}))
    recibo = json.loads(Path(resultado["recibo"]).read_text(encoding="utf-8"))
    for nombre in _subchecks("QG-00"):
        registro = recibo["subchecks"][nombre]
        assert registro["artifact"], nombre
        assert Path(registro["artifact"]).is_file(), nombre
        assert registro["artifact_sha256"], nombre
    # Y los artefactos son DISTINTOS: no es el mismo archivo repetido.
    rutas = {r["artifact"] for r in recibo["subchecks"].values()}
    assert len(rutas) == len(_subchecks("QG-00"))


def test_el_recibo_de_la_puerta_agrega_los_subchecks(tmp_path):
    resultado = c.ejecutar_verificador(
        "QG-01", SHA, tmp_path / "salida", ejecutar=_fake_ejecutar({}))
    recibo = json.loads(Path(resultado["recibo"]).read_text(encoding="utf-8"))
    assert set(recibo["checks"]) == set(_subchecks("QG-01"))
    veredicto = c.leer_recibo(Path(resultado["recibo"]), SHA)
    assert veredicto["ok"] is True, veredicto


def test_un_recibo_sin_artefactos_individuales_no_acredita(tmp_path):
    """Todo PASS, pero sin artefactos por subcheck: no acredita."""
    salida = tmp_path / "salida"
    c.ejecutar_verificador("QG-01", SHA, salida, ejecutar=_fake_ejecutar({}))
    ruta = salida / "QG-01.recibo.json"
    recibo = json.loads(ruta.read_text(encoding="utf-8"))
    for nombre in recibo["subchecks"]:
        recibo["subchecks"][nombre]["artifact"] = None
    ruta.write_text(json.dumps(recibo), encoding="utf-8")
    detalle = c.leer_recibo(ruta, SHA)["detalle"]
    assert "SUBCHECK_SIN_ARTEFACTO" in detalle


def test_un_recibo_sin_un_subcheck_no_acredita(tmp_path):
    salida = tmp_path / "salida"
    c.ejecutar_verificador("QG-01", SHA, salida, ejecutar=_fake_ejecutar({}))
    ruta = salida / "QG-01.recibo.json"
    recibo = json.loads(ruta.read_text(encoding="utf-8"))
    recibo["checks"].pop("reconciliador_archify")
    ruta.write_text(json.dumps(recibo), encoding="utf-8")
    detalle = c.leer_recibo(ruta, SHA)["detalle"]
    assert "SUBCHECKS_AUSENTES" in detalle


def test_un_recibo_con_artefacto_manipulado_no_acredita(tmp_path):
    salida = tmp_path / "salida"
    c.ejecutar_verificador("QG-01", SHA, salida, ejecutar=_fake_ejecutar({}))
    ruta = salida / "QG-01.recibo.json"
    recibo = json.loads(ruta.read_text(encoding="utf-8"))
    objetivo = Path(recibo["subchecks"]["vault_arch"]["artifact"])
    objetivo.write_text("contenido manipulado\n", encoding="utf-8")
    detalle = c.leer_recibo(ruta, SHA)["detalle"]
    assert "MANIPULADO" in detalle


def test_qg04_sin_pip_audit_no_pasa(tmp_path):
    """Se intenta acreditar QG-04 sin pip_audit."""
    resultado = c.ejecutar_verificador(
        "QG-04", SHA, tmp_path / "salida", ejecutar=_fake_ejecutar({}))
    assert resultado["checks"]["pip_audit"] == "no_ejecutado"
    assert resultado["ok"] is False


def test_qg06_sin_instalacion_limpia_no_pasa(tmp_path):
    """Se intenta acreditar QG-06 sin la evidencia de instalacion limpia."""
    resultado = c.ejecutar_verificador(
        "QG-06", SHA, tmp_path / "salida", ejecutar=_fake_ejecutar({}))
    assert resultado["checks"]["instalacion_limpia"] == "no_ejecutado"
    assert resultado["ok"] is False


def test_qg00_sin_reconciliador_no_pasa(tmp_path):
    resultado = c.ejecutar_verificador(
        "QG-00", SHA, tmp_path / "salida", ejecutar=_fake_ejecutar({}))
    assert resultado["checks"]["reconciliador_archify"] != "ejecutado" or \
        resultado["ok"] is False


def test_recibo_de_otro_sha_no_acredita(tmp_path):
    salida = tmp_path / "salida"
    c.ejecutar_verificador("QG-01", SHA, salida, ejecutar=_fake_ejecutar({}))
    detalle = c.leer_recibo(salida / "QG-01.recibo.json", OTRO)["detalle"]
    assert detalle == "RECIBO_DE_OTRO_SHA"


# ── QA-RC-02h: la CLI real ───────────────────────────────────────────────────

def _cli(*args, cwd=None):
    return subprocess.run([sys.executable, str(ROOT / "audits" / "fase2" /
                                               "colector_qg.py"), *args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(cwd or ROOT), timeout=300)


def test_la_cli_responde_help():
    p = _cli("--help")
    assert p.returncode == 0
    assert "--ejecutar" in p.stdout and "--recibos" in p.stdout


def test_la_cli_rechaza_un_sha_invalido():
    p = _cli("--sha", "no-es-un-sha")
    assert p.returncode == 2
    assert "SHA_INVALIDO" in p.stdout


def test_la_cli_ejecutar_sin_recibos_falla_explicitamente():
    p = _cli("--sha", SHA, "--ejecutar")
    assert p.returncode == 2
    assert "FALTA_RECIBOS" in p.stdout


def test_la_cli_evalua_y_devuelve_json_consistente(tmp_path):
    """Flujo ejecutable como proceso real: evalua y devuelve JSON + exit code."""
    salida = tmp_path / "recibos"
    salida.mkdir()
    p = _cli("--sha", SHA, "--recibos", str(salida))
    assert p.returncode == 1, p.stdout[-400:]
    sobre = json.loads(p.stdout)
    assert sobre["politica"]["liberable"] is False
    assert sobre["politica"]["gates"]["QG-00"] == "NOT_RUN"


# ── QA-RC-02i: CI ligada al run exacto ───────────────────────────────────────

def _run(status="completed", conclusion="success", sha=SHA,
         workflow="Vault CI", id=7):
    return {"databaseId": id, "status": status, "conclusion": conclusion,
            "headSha": sha, "workflowName": workflow}


def _jobs(nombres, conclusion="success", status="completed", run_id=7):
    return {"jobs": [{"name": n, "conclusion": conclusion, "status": status,
                      "run_id": run_id} for n in nombres],
            "total_count": len(nombres)}


def _matriz(completa=True, conclusion="success", run_id=7, status="completed"):
    nombres = list(c.JOBS_OBLIGATORIOS)
    if not completa:
        nombres = nombres[:-1]
    return _jobs(nombres, conclusion=conclusion, status=status, run_id=run_id)


def test_ci_con_matriz_completa_acredita():
    dato = c.estado_ci(SHA, consultar=lambda s: [_run()],
                       consultar_jobs=lambda r: _matriz())
    assert dato["conclusion"] == "success"
    assert dato["run_id"] == 7


def test_ci_sin_jobs_es_bloqueante():
    dato = c.estado_ci(SHA, consultar=lambda s: [_run()],
                       consultar_jobs=lambda r: {"jobs": [], "total_count": 0})
    assert dato["conclusion"] == "no_verificable"
    assert "SIN_JOBS" in dato["detalle"]


def test_ci_con_jobs_sin_identidad_de_run_no_acredita():
    jobs = {"jobs": [{"name": n, "conclusion": "success", "status": "completed"}
                     for n in c.JOBS_OBLIGATORIOS],
            "total_count": len(c.JOBS_OBLIGATORIOS)}
    dato = c.estado_ci(SHA, consultar=lambda s: [_run()],
                       consultar_jobs=lambda r: jobs)
    # Sin run_id no se puede probar que sean de ESTE run: no acredita.
    assert dato["conclusion"] == "no_verificable"


def test_ci_con_paginacion_incompleta_no_acredita():
    jobs = _matriz()
    jobs["total_count"] = len(c.JOBS_OBLIGATORIOS) + 5
    dato = c.estado_ci(SHA, consultar=lambda s: [_run()],
                       consultar_jobs=lambda r: jobs)
    assert "PAGINACION_INCOMPLETA" in dato["detalle"]


def test_ci_con_jobs_duplicados_no_acredita():
    nombres = list(c.JOBS_OBLIGATORIOS) + ["Lint Python"]
    jobs = _jobs(nombres)
    dato = c.estado_ci(SHA, consultar=lambda s: [_run()],
                       consultar_jobs=lambda r: jobs)
    assert "JOBS_DUPLICADOS" in dato["detalle"]


def test_ci_con_conclusion_null_no_acredita():
    jobs = _matriz()
    jobs["jobs"][0]["conclusion"] = None
    dato = c.estado_ci(SHA, consultar=lambda s: [_run()],
                       consultar_jobs=lambda r: jobs)
    assert "MATRIZ_INCOMPLETA" in dato["detalle"]


def test_ci_con_jobs_de_otro_run_no_acredita():
    jobs = _matriz(run_id=999)
    dato = c.estado_ci(SHA, consultar=lambda s: [_run()],
                       consultar_jobs=lambda r: jobs)
    assert "JOBS_DE_OTRO_RUN" in dato["detalle"]


def test_ci_con_job_desconocido_no_acredita():
    jobs = _matriz()
    jobs["jobs"].append({"name": "Job Misterioso", "conclusion": "success",
                          "status": "completed", "run_id": 7})
    jobs["total_count"] = len(jobs["jobs"])
    dato = c.estado_ci(SHA, consultar=lambda s: [_run()],
                       consultar_jobs=lambda r: jobs)
    assert "MATRIZ_INCOMPLETA" in dato["detalle"]


def test_ci_en_cola_es_bloqueante():
    dato = c.estado_ci(SHA, consultar=lambda s: [
        _run(status="queued", conclusion="")],
        consultar_jobs=lambda r: {"jobs": [], "total_count": 0})
    assert dato["conclusion"] == "queued"


def test_sin_permisos_para_jobs_es_bloqueante():
    def _falla(run_id):
        raise OSError("HTTP 403")
    dato = c.estado_ci(SHA, consultar=lambda s: [_run()],
                       consultar_jobs=_falla)
    assert dato["conclusion"] == "no_verificable"
    assert "JOBS_NO_DISPONIBLES" in dato["detalle"]


# ── Orquestacion ─────────────────────────────────────────────────────────────

def test_sin_recibos_no_hay_liberacion(tmp_path):
    resultado = c.colectar(SHA, recibos=None, raiz=tmp_path,
                           ejecutar=lambda *a, **k: _Proc(0, json.dumps(
                               {"total_violations": 0, "completo": True,
                                "checks": []})),
                           consultar_ci=lambda s: [])
    assert resultado["politica"]["liberable"] is False
    assert resultado["politica"]["gates"]["QG-00"] == "NOT_RUN"


def test_el_colector_no_pasa_jobs_fuera_de_su_interfaz():
    """La CLI y la funcion comparten firma: no queda jobs_ci colgando."""
    import inspect
    parametros = inspect.signature(c.colectar).parameters
    assert "jobs_ci" not in parametros
    assert "consultar_jobs" in parametros
