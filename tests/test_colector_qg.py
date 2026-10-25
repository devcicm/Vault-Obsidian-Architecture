"""QA-RC-02 · el colector acredita resultados estructurados, no texto con SHA.

Recibos fieles al contrato; verificadores simulados exactos al contrato real.
Modelo de confianza: el recibo acredita la ejecucion LOCAL del colector; la
firma independiente es la CI (QG-07) y el dictamen QA sobre el SHA congelado.
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


def _recibo(tmp_path: Path, gate: str, sha: str = SHA, exit_code: int = 0,
            status: str = "PASS", artefacto: Path | None = None,
            extra: dict | None = None) -> Path:
    recibos = tmp_path / "recibos"
    recibos.mkdir(parents=True, exist_ok=True)
    dato = {
        "gate": gate, "target_sha": sha,
        "verifier": "vault_arch",
        "command": "python scripts/vault_arch.py --check --strict",
        "exit_code": exit_code, "status": status,
        "started_at": "2026-10-25T00:00:00Z",
        "finished_at": "2026-10-25T00:01:00Z", "run_id": f"local-{gate}",
    }
    if artefacto is not None:
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


# ── Recibos ──────────────────────────────────────────────────────────────────

def test_recibo_valido_acredita(tmp_path):
    assert c.leer_recibo(_recibo(tmp_path, "QG-01"), SHA)["ok"] is True


def test_recibo_de_otro_sha_no_acredita(tmp_path):
    assert c.leer_recibo(_recibo(tmp_path, "QG-01", sha=OTRO), SHA)[
        "detalle"] == "RECIBO_DE_OTRO_SHA"


def test_recibo_con_verificador_fallido_no_acredita(tmp_path):
    assert "VERIFICADOR_FALLIDO" in c.leer_recibo(
        _recibo(tmp_path, "QG-01", exit_code=1), SHA)["detalle"]


def test_recibo_con_status_no_pass_no_acredita(tmp_path):
    assert "STATUS_NO_PASS" in c.leer_recibo(
        _recibo(tmp_path, "QG-01", status="FAIL"), SHA)["detalle"]


def test_recibo_incompleto_no_acredita(tmp_path):
    assert "RECIBO_INCOMPLETO" in c.leer_recibo(
        _recibo(tmp_path, "QG-01", extra={"verifier": ""}), SHA)["detalle"]


def test_recibo_manipulado_no_acredita(tmp_path):
    ruta = _recibo(tmp_path, "QG-01")
    dato = json.loads(ruta.read_text(encoding="utf-8"))
    dato["status"] = "FAIL"
    ruta.write_text(json.dumps(dato), encoding="utf-8")
    assert "STATUS_NO_PASS" in c.leer_recibo(ruta, SHA)["detalle"]


def test_recibo_con_hash_de_artefacto_distinto_no_acredita(tmp_path):
    artefacto = _evidencia(tmp_path, "salida.json", '{"ok": true}')
    recibo = _recibo(tmp_path, "QG-01", artefacto=artefacto)
    artefacto.write_text('{"ok": false}', encoding="utf-8")
    assert "ARTEFACTO_MANIPULADO_O_DISTINTO" in c.leer_recibo(
        recibo, SHA)["detalle"]


def test_recibo_con_artefacto_inexistente_no_acredita(tmp_path):
    artefacto = _evidencia(tmp_path, "x.json", "x")
    recibo = _recibo(tmp_path, "QG-01", artefacto=artefacto)
    artefacto.unlink()
    assert "ARTEFACTO_INEXISTENTE" in c.leer_recibo(recibo, SHA)["detalle"]


def test_gate_y_fichero_tienen_que_coincidir(tmp_path):
    recibos = tmp_path / "recibos"
    recibos.mkdir(parents=True)
    (recibos / "QG-01.recibo.json").write_text(json.dumps(
        {"gate": "QG-99", "target_sha": SHA, "verifier": "x", "command": "x",
         "exit_code": 0, "status": "PASS", "started_at": "t", "finished_at": "t",
         "run_id": "r"}), encoding="utf-8")
    assert "GATE_NO_COINCIDE" in c.leer_recibo(
        recibos / "QG-01.recibo.json", SHA)["detalle"]


def test_un_texto_con_el_sha_no_acredita_nada(tmp_path):
    recibos = tmp_path / "recibos"
    recibos.mkdir()
    (recibos / "QG-01.recibo.txt").write_text(f"SHA: {SHA}\nPASS\n",
                                              encoding="utf-8")
    assert c.estado_desde_recibo("QG-01", SHA, recibos)["estado"] == "no_ejecutado"


def test_sin_directorio_de_recibos_es_no_ejecutado():
    dato = c.estado_desde_recibo("QG-00", SHA, None)
    assert dato["estado"] == "no_ejecutado"
    assert dato["detalle"] == "SIN_DIRECTORIO_DE_RECIBOS"


# ── Identidad del arbol ──────────────────────────────────────────────────────

class _GitSeq:
    def __init__(self, head, status=""):
        self.respuestas = [head + "\n", status]
        self.returncode = 0
        self.stderr = ""

    @property
    def stdout(self):
        return self.respuestas.pop(0) if self.respuestas else ""


def _git_seq(head, status=""):
    return _GitSeq(head, status)


def test_checkout_en_otro_sha_no_acredita(tmp_path):
    seq_otro = _git_seq(OTRO)
    assert "CHECKOUT_EN_OTRO_SHA" in c.checkout_en_sha(
        SHA, lambda *a, **k: seq_otro)["detalle"]


def test_arbol_sucio_no_acredita(tmp_path):
    seq_sucio = _git_seq(SHA, "M scripts/x.py\n")
    assert c.checkout_en_sha(SHA, lambda *a, **k: seq_sucio)["detalle"] == "ARBOL_SUCIO"


def test_checkout_en_sha_y_limpio_acredita(tmp_path):
    seq_limpio = _git_seq(SHA)
    assert c.checkout_en_sha(SHA, lambda *a, **k: seq_limpio)["ok"] is True


# ── CI ───────────────────────────────────────────────────────────────────────

def test_ci_en_cola_es_bloqueante():
    assert c.estado_ci(SHA, lambda s: [
        {"databaseId": 1, "status": "queued", "conclusion": "",
         "headSha": SHA}])["conclusion"] == "queued"


def test_un_run_de_otro_sha_no_acredita():
    assert c.estado_ci(SHA, lambda s: [
        {"databaseId": 2, "status": "completed", "conclusion": "success",
         "headSha": OTRO}])["conclusion"] == "sin_run"


def test_run_exitoso_de_workflow_ajeno_no_acredita():
    dato = c.estado_ci(SHA, lambda s: [
        {"databaseId": 3, "status": "completed", "conclusion": "success",
         "headSha": SHA, "workflowName": "Otro CI"}])
    assert dato["conclusion"] == "no_verificable"


def test_ci_success_del_sha_y_workflow_esperado_acredita():
    assert c.estado_ci(SHA, lambda s: [
        {"databaseId": 4, "status": "completed", "conclusion": "success",
         "headSha": SHA, "workflowName": "Vault CI"}])["conclusion"] == "success"


# ── Suite y control de ejecucion ─────────────────────────────────────────────

def _junit_ok(tmp_path):
    return _junit(tmp_path, 10, 0)


def _junit(tmp_path, tests, failures, errors=0):
    ruta = tmp_path / "junit.xml"
    ruta.write_text(
        f'<?xml version="1.0"?><testsuites><testsuite name="s" tests="{tests}" '
        f'failures="{failures}" errors="{errors}" skipped="0"/></testsuites>',
        encoding="utf-8")
    return ruta


def test_junit_con_fallos_no_acredita(tmp_path):
    assert c.estado_suite(_junit(tmp_path, 10, 1))["estado"] == "fallido"


def test_control_degradado_deja_qg02_bloqueado(tmp_path, monkeypatch):
    class P:
        returncode = 0
        stdout = json.dumps({"total_violations": 0, "completo": False,
                             "checks": [{"control": "AP-40",
                                         "estado": "no_ejecutado",
                                         "hallazgos": 0}]})
        stderr = ""

    control = c.control_ejecucion(ejecutar=lambda *a, **k: P())
    assert control["completo"] is False
    assert control["no_verificados"] == ["AP-40"]


def test_auditoria_con_violaciones_no_da_qg02(tmp_path, monkeypatch):
    class P:
        returncode = 0
        stdout = json.dumps({"total_violations": 3, "completo": True,
                             "checks": [{"control": x, "estado": "ejecutado",
                                         "hallazgos": 0}
                                        for x in ("AP-40", "AP-42", "AP-43")]})
        stderr = ""

    control = c.control_ejecucion(ejecutar=lambda *a, **k: P())
    assert control["violaciones"] == 3
    resultado = c.colectar(SHA, recibos=None, raiz=tmp_path,
                           ejecutar=lambda *a, **k: P(),
                           consultar_ci=lambda s: [])
    assert resultado["politica"]["gates"]["QG-02"] == "BLOCKED"


# ── Orquestacion ─────────────────────────────────────────────────────────────

def _entorno_completo(tmp_path):
    for gate in ("QG-00", "QG-01", "QG-02", "QG-04", "QG-05", "QG-06"):
        artefacto = _evidencia(tmp_path, f"art-{gate}.json", f"salida de {gate}")
        _recibo(tmp_path, gate, artefacto=artefacto)

    class Git:
        returncode = 0
        stdout = ""
        stderr = ""

    class Audit:
        returncode = 0
        stdout = json.dumps({"total_violations": 0, "completo": True,
                             "checks": [{"control": x, "estado": "ejecutado",
                                         "hallazgos": 0}
                                        for x in ("AP-40", "AP-42", "AP-43")]})
        stderr = ""

    def ejecutar(cmd, **kwargs):
        texto = " ".join(str(x) for x in cmd)
        if "vault_norms.py" in texto:
            return Audit()
        if "rev-parse" in texto:
            return _git_seq(SHA)
        if "status" in texto:
            return _git_seq("", "")
        return Git()

    xml = _junit_ok(tmp_path)
    Path(str(xml) + ".procedencia.json").write_text(
        '{"sha": "' + SHA + '", "exit": 0}', encoding="utf-8")
    return ejecutar, xml, lambda s: [
        {"databaseId": 9, "status": "completed", "conclusion": "success",
         "headSha": SHA, "workflowName": "Vault CI"}]


def test_el_caso_completo_con_recibos_permite_pass(tmp_path):
    ejecutar, xml, ci = _entorno_completo(tmp_path)
    resultado = c.colectar(SHA, recibos=tmp_path / "recibos", suite_xml=xml,
                           raiz=tmp_path, ejecutar=ejecutar, consultar_ci=ci)
    assert resultado["politica"]["qg07"] == "PASS", resultado["politica"]


def test_sin_recibos_no_hay_liberacion(tmp_path):
    ejecutar, xml, ci = _entorno_completo(tmp_path)
    resultado = c.colectar(SHA, recibos=None, suite_xml=xml, raiz=tmp_path,
                           ejecutar=ejecutar, consultar_ci=ci)
    assert resultado["politica"]["liberable"] is False


def test_ci_en_cola_bloquea_qg07(tmp_path):
    ejecutar, xml, _ = _entorno_completo(tmp_path)
    resultado = c.colectar(
        SHA, recibos=tmp_path / "recibos", suite_xml=xml, raiz=tmp_path,
        ejecutar=ejecutar,
        consultar_ci=lambda s: [{"databaseId": 1, "status": "queued",
                                 "conclusion": "", "headSha": SHA}])
    assert resultado["politica"]["qg07"] == "BLOCKED"
    assert any("CI_PENDIENTE" in m
               for m in resultado["politica"]["motivos"]["QG-07"])
