"""QA-RC-02d/e/f · recibos con subchecks, CI con matriz real, ejecutor auténtico.

El colector exige: recibo por puerta con TODOS sus subchecks obligatorios en
PASS, artefacto existente con hash coincidente, verifier+command autorizados,
CI del workflow esperado con sus 25 jobs reales concluidos. Sin recibos, sin
jobs o con gh ausente: NOT_RUN / no_verificable, nunca PASS.
"""
import hashlib
import importlib.util
import json
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


def _evidencia(tmp_path: Path, nombre: str, texto: str) -> Path:
    ruta = tmp_path / nombre
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def _checks(gate: str, estado: str = "PASS") -> dict:
    return {sc: estado for sc in c.SUBCHECKS_OBLIGATORIOS[gate]}


def _recibo(tmp_path: Path, gate: str, sha: str = SHA, exit_code: int = 0,
            status: str = "PASS", checks: dict | None = None,
            sin_checks: bool = False, sin_artefacto: bool = False,
            verifier: str | None = None, comando: str | None = None,
            extra: dict | None = None) -> Path:
    recibos = tmp_path / "recibos"
    recibos.mkdir(parents=True, exist_ok=True)
    verifier_aut, comando_aut = c.GATE_VERIFICADORES[gate]
    artefacto = _evidencia(tmp_path, f"art-{gate}.json",
                           json.dumps({"ok": status == "PASS"}) if not
                           sin_artefacto else "x")
    dato = {
        "gate": gate, "target_sha": sha,
        "verifier": verifier or verifier_aut,
        "command": comando or comando_aut,
        "exit_code": exit_code, "status": status,
        "started_at": "2026-10-25T00:00:00Z",
        "finished_at": "2026-10-25T00:01:00Z", "run_id": f"local-{gate}",
        "artifact": None if sin_artefacto else str(artefacto),
        "artifact_sha256": None if sin_artefacto else hashlib.sha256(
            artefacto.read_bytes()).hexdigest(),
        "checks": {} if sin_checks else (checks if checks is not None
                                         else _checks(gate)),
    }
    if extra:
        dato.update(extra)
    ruta = recibos / f"{gate}.recibo.json"
    ruta.write_text(json.dumps(dato, indent=2), encoding="utf-8")
    return ruta


def _junit(tmp_path: Path, tests: int = 5, failures: int = 0,
           errors: int = 0, firmar: bool = True, sha: str = SHA) -> Path:
    ruta = tmp_path / "junit.xml"
    ruta.write_text(
        f'<?xml version="1.0"?><testsuites><testsuite name="s" tests="{tests}" '
        f'failures="{failures}" errors="{errors}" skipped="0"/></testsuites>',
        encoding="utf-8")
    if firmar:
        Path(str(ruta) + ".procedencia.json").write_text(json.dumps({
            "sha": sha, "exit": 0,
            "junit_sha256": hashlib.sha256(ruta.read_bytes()).hexdigest()}),
            encoding="utf-8")
    return ruta


# ── Recibos con subchecks (02e) ──────────────────────────────────────────────

def test_recibo_completo_acredita(tmp_path):
    assert c.leer_recibo(_recibo(tmp_path, "QG-01"), SHA)["ok"] is True


def test_subchecks_ausentes_no_acreditan(tmp_path):
    dato = c.leer_recibo(_recibo(tmp_path, "QG-01",
                                 checks={"vault_arch": "PASS"}), SHA)
    assert "SUBCHECKS_AUSENTES" in dato["detalle"]
    assert "reconciliador_archify" in dato["detalle"]


def test_subcheck_en_estado_distinto_de_pass_no_acredita(tmp_path):
    checks = _checks("QG-02")
    checks["auditoria_completa"] = "degradado"
    dato = c.leer_recibo(_recibo(tmp_path, "QG-02", checks=checks), SHA)
    assert "SUBCHECKS_AUSENTES" in dato["detalle"]


def test_recibo_sin_seccion_checks_no_acredita(tmp_path):
    dato = c.leer_recibo(_recibo(tmp_path, "QG-04", sin_checks=True), SHA)
    assert "SUBCHECKS_AUSENTES" in dato["detalle"]


# ── Recibos: las negativas de 02a siguen en pie ──────────────────────────────

def test_recibo_de_otro_sha_no_acredita(tmp_path):
    assert c.leer_recibo(_recibo(tmp_path, "QG-01", sha=OTRO), SHA)[
        "detalle"] == "RECIBO_DE_OTRO_SHA"


def test_exit_code_no_cero_no_acredita(tmp_path):
    assert "VERIFICADOR_FALLIDO" in c.leer_recibo(
        _recibo(tmp_path, "QG-01", exit_code=1), SHA)["detalle"]


def test_status_no_pass_no_acredita(tmp_path):
    assert "STATUS_NO_PASS" in c.leer_recibo(
        _recibo(tmp_path, "QG-01", status="FAIL"), SHA)["detalle"]


def test_comando_no_autorizado_no_acredita(tmp_path):
    dato = c.leer_recibo(_recibo(tmp_path, "QG-01",
                                 comando="python scripts/otro.py"), SHA)
    assert dato["detalle"] == "VERIFICADOR_O_COMANDO_NO_AUTORIZADO"


def test_verificador_ajeno_no_acredita(tmp_path):
    dato = c.leer_recibo(_recibo(tmp_path, "QG-01", verifier="otro"), SHA)
    assert dato["detalle"] == "VERIFICADOR_O_COMANDO_NO_AUTORIZADO"


def test_texto_con_el_sha_no_acredita_nada(tmp_path):
    recibos = tmp_path / "recibos"
    recibos.mkdir()
    (recibos / "QG-01.recibo.txt").write_text(f"SHA: {SHA}\nPASS\n",
                                              encoding="utf-8")
    assert c.estado_desde_recibo("QG-01", SHA, recibos)["estado"] == "no_ejecutado"


def test_sin_recibos_es_no_ejecutado():
    dato = c.estado_desde_recibo("QG-00", SHA, None)
    assert dato["estado"] == "no_ejecutado"


# ── QA-RC-02d: CI con jobs reales y matriz exacta ────────────────────────────

def _jobs(nombres, conclusion="success", status="completed", run_id=None):
    return [{"name": n, "conclusion": conclusion, "status": status,
             "run_id": run_id} for n in nombres]


def _matriz(completa=True, conclusion="success", run_id=None):
    nombres = list(c.JOBS_OBLIGATORIOS)
    if not completa:
        nombres = nombres[:-1]  # quita uno: matriz incompleta
    return _jobs(nombres, conclusion=conclusion, run_id=run_id)


def test_ci_exitosa_con_matriz_completa_acredita():
    runs = [_run()]
    dato = c.estado_ci(SHA, consultar=lambda s: runs,
                       consultar_jobs=lambda rid: _matriz())
    assert dato["conclusion"] == "success"
    assert dato["run_id"] == 1


def _run(status="completed", conclusion="success", sha=SHA,
         workflow="Vault CI", id=1):
    return {"databaseId": id, "status": status, "conclusion": conclusion,
            "headSha": sha, "workflowName": workflow}


def test_ci_en_cola_es_bloqueante():
    dato = c.estado_ci(SHA, consultar=lambda s: [
        _run(status="queued", conclusion="")], consultar_jobs=lambda r: [])
    assert dato["conclusion"] == "queued"


def test_ci_exitosa_sin_jobs_consultables_no_acredita():
    def _jobs_fallan(run_id):
        raise OSError("sin permiso para jobs")
    dato = c.estado_ci(SHA, consultar=lambda s: [_run()],
                       consultar_jobs=_jobs_fallan)
    assert dato["conclusion"] == "no_verificable"
    assert "JOBS_NO_DISPONIBLES" in dato["detalle"]


def test_workflow_sin_identidad_no_acredita():
    dato = c.estado_ci(SHA, consultar=lambda s: [_run(workflow=None)],
                       consultar_jobs=lambda r: [])
    assert "WORKFLOW_SIN_IDENTIDAD" in dato["detalle"]


def test_workflow_ajeno_no_acredita():
    dato = c.estado_ci(SHA, consultar=lambda s: [_run(workflow="Otro CI")],
                       consultar_jobs=lambda r: [])
    assert dato["conclusion"] == "no_verificable"


def test_matriz_incompleta_no_acredita():
    dato = c.estado_ci(SHA, consultar=lambda s: [_run()],
                       consultar_jobs=lambda r: _matriz(completa=False))
    assert "MATRIZ_INCOMPLETA" in dato["detalle"]


def test_job_sin_conclusion_no_acredita():
    jobs = _matriz() + [{"name": "Extra", "conclusion": None,
                         "status": "completed", "run_id": 1}]
    dato = c.estado_ci(SHA, consultar=lambda s: [_run()],
                       consultar_jobs=lambda r: jobs)
    assert "MATRIZ_INCOMPLETA" in dato["detalle"]


def test_job_cancelado_no_acredita():
    jobs = _matriz()
    jobs[-1]["conclusion"] = "cancelled"
    dato = c.estado_ci(SHA, consultar=lambda s: [_run()],
                       consultar_jobs=lambda r: jobs)
    assert "MATRIZ_INCOMPLETA" in dato["detalle"]


def test_jobs_duplicados_que_ocultan_ausencias_no_acreditan():
    """Dos Lint Python no sustituyen a los jobs de la matriz que faltan."""
    jobs = _jobs(["Lint Python", "Lint Python", "Lint Python",
                  "Lint Python", "Lint Python"])
    dato = c.estado_ci(SHA, consultar=lambda s: [_run()],
                       consultar_jobs=lambda r: jobs)
    assert "MATRIZ_INCOMPLETA" in dato["detalle"]


def test_jobs_de_otro_run_no_se_considenan():
    jobs = _matriz(run_id=777)  # matriz completa pero de OTRO run
    dato = c.estado_ci(SHA, consultar=lambda s: [_run()],
                       consultar_jobs=lambda r: jobs)
    assert "MATRIZ_INCOMPLETA" in dato["detalle"]


def test_run_de_otro_sha_no_acredita():
    dato = c.estado_ci(SHA, consultar=lambda s: [_run(sha=OTRO)],
                       consultar_jobs=lambda r: [])
    assert dato["conclusion"] == "sin_run"


# ── QA-RC-02c: procedencia JUnit y control de ejecucion ──────────────────────

def test_junit_sin_firma_no_acredita(tmp_path):
    xml = _junit(tmp_path, firmar=False)
    assert "SIN_RECIBO_DE_EJECUCION" in c._procedencia_suite(xml, SHA)["detalle"]


def test_junit_manipulado_tras_firmar_no_acredita(tmp_path):
    xml = _junit(tmp_path, 5, 0)
    _junit(tmp_path, 5, 2, firmar=False)
    # reescrito sin firmar: el hash del recibo ya no coincide
    assert "JUNIT_MANIPULADO" in c._procedencia_suite(xml, SHA)["detalle"]


def test_junit_firmado_y_limpio_acredita(tmp_path):
    xml = _junit(tmp_path, 5, 0)
    assert c._procedencia_suite(xml, SHA)["ok"] is True


def test_checkout_en_otro_sha_no_acredita(tmp_path):
    class P:
        returncode = 0
        stdout = OTRO + "\n"
        stderr = ""

    seq = [P]
    def ejecutar(cmd, **k):
        p = _P2(seq)
        return p
    class _P2:
        returncode = 0
        stdout = ""
        stderr = ""
    # rev-parse devuelve OTRO: el detalle debe nombrar el desvio.
    dato = c.checkout_en_sha(SHA, lambda *a, **k: type(
        "R", (), {"returncode": 0, "stdout": OTRO + "\n", "stderr": ""})())
    assert "CHECKOUT_EN_OTRO_SHA" in dato["detalle"]


def test_git_con_error_de_retorno_no_acredita(tmp_path):
    dato = c.checkout_en_sha(SHA, lambda *a, **k: type(
        "R", (), {"returncode": 128, "stdout": "", "stderr": ""})())
    assert dato["detalle"] == "GIT_REV_PARSE_FALLIDO"


# ── Control de ejecucion (TD-0003) ───────────────────────────────────────────

class _Proc:
    def __init__(self, exit_code, stdout):
        self.returncode = exit_code
        self.stdout = stdout
        self.stderr = ""


class _GitSeq:
    """Fiel al contrato de `checkout_en_sha`: rev-parse HEAD -> status."""

    def __init__(self, head, status=""):
        self.respuestas = [head + "\n", status]
        self.returncode = 0
        self.stderr = ""

    @property
    def stdout(self):
        return self.respuestas.pop(0) if self.respuestas else ""


def _git_seq(head, status=""):
    return _GitSeq(head, status)


def test_auditoria_con_exit_no_cero_no_se_acredita():
    control = c.control_ejecucion(
        ejecutar=lambda *a, **k: _Proc(1, json.dumps({"completo": True})))
    assert control["completo"] is False
    assert control["no_verificados"] == ["auditoria_fallida"]


def test_auditoria_ilegible_es_no_ejecutada():
    control = c.control_ejecucion(ejecutar=lambda *a, **k: _Proc(0, "no-json"))
    assert control["no_verificados"] == ["auditoria_ilegible"]


def test_auditoria_con_violaciones_bloquea_qg02(tmp_path):
    sobre = json.dumps({"total_violations": 2, "completo": True, "checks": []})
    resultado = c.colectar(SHA, recibos=None, raiz=tmp_path,
                           ejecutar=lambda *a, **k: _Proc(0, sobre),
                           consultar_ci=lambda s: [])
    assert resultado["politica"]["gates"]["QG-02"] == "BLOCKED"


# ── QA-RC-02f: el ejecutor produce recibos autenticos ────────────────────────

def test_el_ejecutor_emite_recibo_desde_una_ejecucion_real(tmp_path):
    verifier, comando = c.GATE_VERIFICADORES["QG-04"]
    resultado = c.ejecutar_verificador(
        "QG-04", SHA, tmp_path / "salida",
        ejecutar=lambda *a, **k: _Proc(0, '{"ok": true}'))
    assert resultado["ok"] is True
    recibo = json.loads(Path(resultado["recibo"]).read_text(encoding="utf-8"))
    assert recibo["target_sha"] == SHA
    assert recibo["exit_code"] == 0
    assert recibo["status"] == "PASS"
    assert set(recibo["checks"]) == set(c.SUBCHECKS_OBLIGATORIOS["QG-04"])
    assert all(v == "PASS" for v in recibo["checks"].values())
    artefacto = Path(recibo["artifact"])
    assert artefacto.is_file()
    assert hashlib.sha256(artefacto.read_bytes()).hexdigest() == \
        recibo["artifact_sha256"]
    veredicto = c.leer_recibo(Path(resultado["recibo"]), SHA)
    assert veredicto["ok"] is True, veredicto


def test_el_ejecutor_registra_el_fallo_del_verificador(tmp_path):
    resultado = c.ejecutar_verificador(
        "QG-01", SHA, tmp_path / "salida",
        ejecutar=lambda *a, **k: _Proc(1, 'json roto'))
    assert resultado["ok"] is False
    assert resultado["status"] == "FAIL"
    recibo = json.loads(Path(resultado["recibo"]).read_text(encoding="utf-8"))
    assert recibo["exit_code"] == 1
    assert all(v == "FAIL" for v in recibo["checks"].values())


# ── Orquestacion con recibos autenticos + CI simulada fiel ───────────────────

def _ci_con_jobs(jobs):
    def _consultar(sha):
        return [_run()]

    def _consultar_jobs(run_id):
        return jobs

    _consultar.jobs = _consultar_jobs
    return _consultar


def test_la_orquestacion_con_recibos_reales_y_matriz_acredita(tmp_path):
    salida = tmp_path / "salida"
    for gate in ("QG-00", "QG-01", "QG-02", "QG-04", "QG-05", "QG-06"):
        r = c.ejecutar_verificador(
            gate, SHA, salida,
            ejecutar=lambda *a, **k: _Proc(0, '{"ok": true}'))
        assert r["ok"] is True, (gate, r)
    xml = _junit(tmp_path, 5, 0)
    jobs = _matriz()
    seq_git = _git_seq(SHA)

    def ejecutar(cmd, **kwargs):
        texto = " ".join(str(x) for x in cmd)
        if "vault_norms.py" in texto:
            return _Proc(0, json.dumps(
                {"total_violations": 0, "completo": True,
                 "checks": [{"control": x, "estado": "ejecutado", "hallazgos": 0}
                            for x in ("AP-40", "AP-42", "AP-43")]}))
        if "rev-parse" in texto:
            return seq_git
        if "status" in texto:
            return seq_git
        return _Proc(0, '{"ok": true}')

    resultado = c.colectar(
        SHA, recibos=salida, suite_xml=xml, raiz=tmp_path, ejecutar=ejecutar,
        consultar_ci=_ci_con_jobs(jobs), consultar_jobs=lambda r: jobs)
    assert resultado["politica"]["qg07"] == "PASS", resultado["politica"]


def test_sin_recibos_la_orquestacion_bloquea_todo(tmp_path):
    resultado = c.colectar(SHA, recibos=None, raiz=tmp_path,
                           ejecutar=lambda *a, **k: _Proc(
                               0, json.dumps({"total_violations": 0,
                                              "completo": True, "checks": []})),
                           consultar_ci=lambda s: [])
    assert resultado["politica"]["liberable"] is False
    assert resultado["politica"]["gates"]["QG-00"] == "NOT_RUN"


def test_ci_en_cola_bloquea_qg07(tmp_path):
    salida = tmp_path / "salida"
    for gate in ("QG-00", "QG-01", "QG-02", "QG-04", "QG-05", "QG-06"):
        c.ejecutar_verificador(
            gate, SHA, salida,
            ejecutar=lambda *a, **k: _Proc(0, '{"ok": true}'))
    xml = _junit(tmp_path, 5, 0)
    resultado = c.colectar(
        SHA, recibos=salida, suite_xml=xml, raiz=tmp_path,
        ejecutar=lambda *a, **k: _Proc(0, json.dumps(
            {"total_violations": 0, "completo": True, "checks": []})),
        consultar_ci=lambda s: [_run(status="queued", conclusion="")])
    assert resultado["politica"]["qg07"] == "BLOCKED"
    assert any("CI_PENDIENTE" in m
               for m in resultado["politica"]["motivos"]["QG-07"])
