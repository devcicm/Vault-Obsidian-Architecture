"""QA-RC-02a/b/c · el colector acredita recibos con artefacto y comando autorizado.

Recibos fieles al contrato; verificadores simulados exactos al contrato real.
El ARTEFACTO es obligatorio y su contenido tambien se interpreta: un JSON con
ok:false anula el PASS. La CI exige workflow identificado y matriz completa.
"""
from __future__ import annotations

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


def _recibo(tmp_path: Path, gate: str, sha: str = SHA, exit_code: int = 0,
            status: str = "PASS", artefacto: Path | None = None,
            sin_artefacto: bool = False, verifier: str | None = None,
            comando: str | None = None, extra: dict | None = None) -> Path:
    recibos = tmp_path / "recibos"
    recibos.mkdir(parents=True, exist_ok=True)
    verifier_aut, comando_aut = c.GATE_VERIFICADORES[gate]
    dato = {
        "gate": gate, "target_sha": sha,
        "verifier": verifier or verifier_aut or "x",
        "command": comando or comando_aut or "x",
        "exit_code": exit_code, "status": status,
        "started_at": "2026-10-25T00:00:00Z",
        "finished_at": "2026-10-25T00:01:00Z", "run_id": f"local-{gate}",
    }
    if not sin_artefacto:
        if artefacto is None:
            artefacto = _evidencia(tmp_path, f"art-{gate}.json",
                                   json.dumps({"ok": True}))
        dato["artifact"] = str(artefacto)
        dato["artifact_sha256"] = hashlib.sha256(artefacto.read_bytes()).hexdigest()
    if extra:
        dato.update(extra)
    ruta = recibos / f"{gate}.recibo.json"
    ruta.write_text(json.dumps(dato, indent=2), encoding="utf-8")
    return ruta


def _junit(tmp_path: Path, tests: int, failures: int, errors: int = 0) -> Path:
    ruta = tmp_path / "junit.xml"
    ruta.write_text(
        f'<?xml version="1.0"?><testsuites><testsuite name="s" tests="{tests}" '
        f'failures="{failures}" errors="{errors}" skipped="0"/></testsuites>',
        encoding="utf-8")
    return ruta


# ── QA-RC-02a: el artefacto es obligatorio y se interpreta ───────────────────

def test_recibo_sin_artefacto_no_acredita(tmp_path):
    dato = c.leer_recibo(_recibo(tmp_path, "QG-01", sin_artefacto=True), SHA)
    assert dato["detalle"] == "RECIBO_INCOMPLETO: ['artifact', 'artifact_sha256']"


def test_recibo_valido_con_artefacto_acredita(tmp_path):
    artefacto = _evidencia(tmp_path, "art.json", '{"ok": true, "exit": 0}')
    assert c.leer_recibo(_recibo(tmp_path, "QG-01", artefacto=artefacto),
                         SHA)["ok"] is True


def test_artefacto_json_con_ok_false_anula_el_pass(tmp_path):
    artefacto = _evidencia(tmp_path, "art.json", '{"ok": false}')
    dato = c.leer_recibo(_recibo(tmp_path, "QG-01", artefacto=artefacto), SHA)
    assert dato["detalle"] == "ARTEFACTO_DECLARA_FALLO"


def test_comando_distinto_del_autorizado_no_acredita(tmp_path):
    dato = c.leer_recibo(_recibo(tmp_path, "QG-01",
                                 comando="python scripts/otro.py"), SHA)
    assert dato["detalle"] == "VERIFICADOR_O_COMANDO_NO_AUTORIZADO"


def test_verificador_ajeno_no_acredita(tmp_path):
    dato = c.leer_recibo(_recibo(tmp_path, "QG-01", verifier="otro"), SHA)
    assert dato["detalle"] == "VERIFICADOR_O_COMANDO_NO_AUTORIZADO"


def test_recibo_de_otro_sha_no_acredita(tmp_path):
    assert c.leer_recibo(_recibo(tmp_path, "QG-01", sha=OTRO), SHA)[
        "detalle"] == "RECIBO_DE_OTRO_SHA"


def test_exit_code_no_cero_no_acredita(tmp_path):
    assert "VERIFICADOR_FALLIDO" in c.leer_recibo(
        _recibo(tmp_path, "QG-01", exit_code=1), SHA)["detalle"]


def test_recibo_manipulado_no_acredita(tmp_path):
    artefacto = _evidencia(tmp_path, "art.json", '{"ok": true}')
    ruta = _recibo(tmp_path, "QG-01", artefacto=artefacto)
    dato = json.loads(ruta.read_text(encoding="utf-8"))
    dato["status"] = "FAIL"
    ruta.write_text(json.dumps(dato), encoding="utf-8")
    assert "STATUS_NO_PASS" in c.leer_recibo(ruta, SHA)["detalle"]


def test_hash_de_artefacto_distinto_no_acredita(tmp_path):
    artefacto = _evidencia(tmp_path, "art.json", '{"ok": true}')
    recibo = _recibo(tmp_path, "QG-01", artefacto=artefacto)
    artefacto.write_text('{"ok": false}', encoding="utf-8")
    assert "ARTEFACTO_MANIPULADO_O_DISTINTO" in c.leer_recibo(
        recibo, SHA)["detalle"]


def test_un_texto_con_el_sha_no_acredita_nada(tmp_path):
    recibos = tmp_path / "recibos"
    recibos.mkdir()
    (recibos / "QG-01.recibo.txt").write_text(f"SHA: {SHA}\nPASS\n",
                                              encoding="utf-8")
    assert c.estado_desde_recibo("QG-01", SHA, recibos)["estado"] == "no_ejecutado"


def test_sin_recibos_es_no_ejecutado():
    assert c.estado_desde_recibo("QG-00", SHA, None)[
        "detalle"] == "SIN_DIRECTORIO_DE_RECIBOS"


# ── QA-RC-02b: CI con identidad y matriz ─────────────────────────────────────

def _run(status="completed", conclusion="success", sha=SHA,
         workflow="Vault CI", id=1):
    return {"databaseId": id, "status": status, "conclusion": conclusion,
            "headSha": sha, "workflowName": workflow}


def test_ci_en_cola_es_bloqueante():
    assert c.estado_ci(SHA, lambda s: [
        _run(status="queued", conclusion="")])["conclusion"] == "queued"


def test_workflow_sin_identidad_no_acredita():
    dato = c.estado_ci(SHA, lambda s: [_run(workflow=None)])
    assert "WORKFLOW_SIN_IDENTIDAD" in dato["detalle"]


def test_workflow_ajeno_no_acredita():
    dato = c.estado_ci(SHA, lambda s: [_run(workflow="Otro CI")])
    assert dato["conclusion"] == "no_verificable"


def test_ci_success_del_sha_y_workflow_esperado_acredita():
    assert c.estado_ci(SHA, lambda s: [_run()])["conclusion"] == "success"


def test_matriz_incompleta_no_acredita():
    jobs = [{"name": f"Validate Vault Spec (ubuntu-latest, {p})",
             "conclusion": "success"} for p in ("3.9", "3.10", "3.11", "3.12")]
    dato = c.estado_ci(SHA, lambda s: [_run()], jobs=jobs)
    assert dato["conclusion"] == "no_verificable"
    assert "MATRIZ_INCOMPLETA" in dato["detalle"]


def test_matriz_completa_y_exitosa_acredita():
    jobs = [{"name": f"Validate Vault Spec {m}", "conclusion": "success"}
            for m in c.MATRIZ_CI]
    jobs += [{"name": f"Product gates (wheel) {m}", "conclusion": "success"}
             for m in c.MATRIZ_CI]
    jobs.append({"name": "Lint Python", "conclusion": "success"})
    assert c.estado_ci(SHA, lambda s: [_run()], jobs=jobs)[
        "conclusion"] == "success"


def test_job_cancelado_no_acredita():
    jobs = [{"name": f"Validate Vault Spec {m}", "conclusion": "success"}
            for m in c.MATRIZ_CI]
    jobs += [{"name": f"Product gates (wheel) {m}", "conclusion": "success"}
             for m in c.MATRIZ_CI]
    jobs.append({"name": "Lint Python", "conclusion": "cancelled"})
    assert c.estado_ci(SHA, lambda s: [_run()], jobs=jobs)[
        "conclusion"] == "no_verificable"


def test_run_de_otro_sha_no_acredita():
    assert c.estado_ci(SHA, lambda s: [
        _run(sha=OTRO)])["conclusion"] == "sin_run"


# ── QA-RC-02c: procedencia e integridad ──────────────────────────────────────

def test_junit_con_fallos_no_acredita(tmp_path):
    assert c.estado_suite(_junit(tmp_path, 10, 1))["estado"] == "fallido"


def test_procedencia_sin_hash_del_junit_no_acredita(tmp_path):
    xml = _junit(tmp_path, 5, 0)
    Path(str(xml) + ".procedencia.json").write_text(
        '{"sha": "' + SHA + '", "exit": 0}', encoding="utf-8")
    assert "JUNIT_MANIPULADO" in c._procedencia_suite(xml, SHA)["detalle"]


def test_procedencia_con_hash_correcto_acredita(tmp_path):
    xml = _junit(tmp_path, 5, 0)
    Path(str(xml) + ".procedencia.json").write_text(json.dumps({
        "sha": SHA, "exit": 0,
        "junit_sha256": hashlib.sha256(xml.read_bytes()).hexdigest()}),
        encoding="utf-8")
    assert c._procedencia_suite(xml, SHA)["ok"] is True


def test_junit_manipulado_tras_firmar_no_acredita(tmp_path):
    xml = _junit(tmp_path, 5, 0)
    Path(str(xml) + ".procedencia.json").write_text(json.dumps({
        "sha": SHA, "exit": 0,
        "junit_sha256": hashlib.sha256(xml.read_bytes()).hexdigest()}),
        encoding="utf-8")
    _junit(tmp_path, 5, 2)  # se reescribe con fallos: el hash ya no coincide
    assert "JUNIT_MANIPULADO" in c._procedencia_suite(xml, SHA)["detalle"]


class _GitSeq:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.returncode = 0
        self.stderr = ""

    @property
    def stdout(self):
        return self.respuestas.pop(0) if self.respuestas else ""


def test_git_con_error_de_retorno_no_acredita(tmp_path):
    p = _GitSeq([""])
    p.returncode = 128
    assert c.checkout_en_sha(SHA, lambda *a, **k: p)["detalle"] == "GIT_REV_PARSE_FALLIDO"


def test_checkout_en_otro_sha_no_acredita(tmp_path):
    seq = _GitSeq([OTRO + "\n", ""])
    assert "CHECKOUT_EN_OTRO_SHA" in c.checkout_en_sha(
        SHA, lambda *a, **k: seq)["detalle"]


def test_arbol_sucio_no_acredita(tmp_path):
    seq = _GitSeq([SHA + "\n", "M scripts/x.py\n"])
    assert c.checkout_en_sha(SHA, lambda *a, **k: seq)["detalle"] == "ARBOL_SUCIO"


def test_checkout_en_sha_y_limpio_acredita(tmp_path):
    seq = _GitSeq([SHA + "\n", ""])
    assert c.checkout_en_sha(SHA, lambda *a, **k: seq)["ok"] is True


# ── Control de ejecucion (TD-0003) ───────────────────────────────────────────

class _Proc:
    def __init__(self, exit_code, stdout):
        self.returncode = exit_code
        self.stdout = stdout
        self.stderr = ""


def test_auditoria_con_exit_no_cero_no_se_acredita(tmp_path, monkeypatch):
    control = c.control_ejecucion(
        ejecutar=lambda *a, **k: _Proc(1, json.dumps({"completo": True})))
    assert control["completo"] is False
    assert control["no_verificados"] == ["auditoria_fallida"]


def test_auditoria_con_violaciones_no_da_qg02(tmp_path, monkeypatch):
    sobre = json.dumps({"total_violations": 3, "completo": True, "checks": []})
    control = c.control_ejecucion(ejecutar=lambda *a, **k: _Proc(0, sobre))
    assert control["violaciones"] == 3
    resultado = c.colectar(SHA, recibos=None, raiz=tmp_path,
                           ejecutar=lambda *a, **k: _Proc(0, sobre),
                           consultar_ci=lambda s: [])
    assert resultado["politica"]["gates"]["QG-02"] == "BLOCKED"


def test_auditoria_ilegible_es_no_ejecutada(tmp_path):
    control = c.control_ejecucion(ejecutar=lambda *a, **k: _Proc(0, "no-json"))
    assert control["no_verificados"] == ["auditoria_ilegible"]


# ── Orquestacion ─────────────────────────────────────────────────────────────

def _entorno_completo(tmp_path):
    for gate in ("QG-00", "QG-01", "QG-02", "QG-04", "QG-05", "QG-06"):
        verifier, comando = c.GATE_VERIFICADORES[gate]
        artefacto = _evidencia(tmp_path, f"art-{gate}.json",
                               json.dumps({"ok": True}))
        _recibo(tmp_path, gate, artefacto=artefacto, verifier=verifier,
                comando=comando)

    class Audit:
        returncode = 0
        stdout = json.dumps({"total_violations": 0, "completo": True,
                             "checks": [{"control": x, "estado": "ejecutado",
                                         "hallazgos": 0}
                                        for x in ("AP-40", "AP-42", "AP-43")]})
        stderr = ""

    class Git:
        returncode = 0
        stdout = ""
        stderr = ""

    def ejecutar(cmd, **kwargs):
        texto = " ".join(str(x) for x in cmd)
        if "vault_norms.py" in texto:
            return Audit()
        if "rev-parse" in texto:
            return _GitSeq([SHA + "\n", ""])
        if "status" in texto:
            return _GitSeq([""])
        return Git()

    xml = _junit(tmp_path, 5, 0)
    Path(str(xml) + ".procedencia.json").write_text(json.dumps({
        "sha": SHA, "exit": 0,
        "junit_sha256": hashlib.sha256(xml.read_bytes()).hexdigest()}),
        encoding="utf-8")
    jobs = [{"name": f"Validate Vault Spec {m}", "conclusion": "success"}
            for m in c.MATRIZ_CI]
    jobs += [{"name": f"Product gates (wheel) {m}", "conclusion": "success"}
             for m in c.MATRIZ_CI] + [{"name": "Lint Python",
                                       "conclusion": "success"}]
    return ejecutar, xml, (lambda s: [_run()]), jobs


def test_el_caso_completo_con_recibos_permite_pass(tmp_path):
    ejecutar, xml, ci, jobs = _entorno_completo(tmp_path)
    resultado = c.colectar(SHA, recibos=tmp_path / "recibos", suite_xml=xml,
                           raiz=tmp_path, ejecutar=ejecutar, consultar_ci=ci,
                           jobs_ci=jobs)
    assert resultado["politica"]["qg07"] == "PASS", resultado["politica"]


def test_sin_recibos_no_hay_liberacion(tmp_path):
    ejecutar, xml, ci, jobs = _entorno_completo(tmp_path)
    resultado = c.colectar(SHA, recibos=None, suite_xml=xml, raiz=tmp_path,
                           ejecutar=ejecutar, consultar_ci=ci, jobs_ci=jobs)
    assert resultado["politica"]["liberable"] is False


def test_ci_en_cola_bloquea_qg07(tmp_path):
    ejecutar, xml, _, jobs = _entorno_completo(tmp_path)
    resultado = c.colectar(
        SHA, recibos=tmp_path / "recibos", suite_xml=xml, raiz=tmp_path,
        ejecutar=ejecutar, jobs_ci=jobs,
        consultar_ci=lambda s: [_run(status="queued", conclusion="")])
    assert resultado["politica"]["qg07"] == "BLOCKED"
    assert any("CI_PENDIENTE" in m
               for m in resultado["politica"]["motivos"]["QG-07"])
