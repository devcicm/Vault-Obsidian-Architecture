"""El colector de QG acredita procedencia real, no declaraciones (GOAL C).

Cada prueba fabrica la situacion que debe rechazarse: evidencia ausente, de otro
SHA, vacia, CI en cola, run de otro commit, suite con fallos, control degradado.
El caso positivo demuestra que el PASS es alcanzable con datos reales.
"""
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


# ── Evidencias ───────────────────────────────────────────────────────────────

def test_evidencia_inexistente_no_acredita(tmp_path):
    dato = c.verificar_evidencia("no/existe.txt", SHA, tmp_path)
    assert dato["ok"] is False
    assert dato["detalle"] == "EVIDENCIA_INEXISTENTE"


def test_evidencia_vacia_no_acredita(tmp_path):
    _evidencia(tmp_path, "vacia.txt", "   \n")
    dato = c.verificar_evidencia("vacia.txt", SHA, tmp_path)
    assert dato["detalle"] == "EVIDENCIA_VACIA"


def test_evidencia_de_otro_sha_no_acredita(tmp_path):
    _evidencia(tmp_path, "vieja.txt", f"resultado del commit {OTRO}\n")
    dato = c.verificar_evidencia("vieja.txt", SHA, tmp_path)
    assert dato["detalle"] == "SHA_NO_ACREDITADO_EN_LA_EVIDENCIA"


def test_evidencia_con_el_sha_del_candidato_acredita(tmp_path):
    _evidencia(tmp_path, "buena.txt", f"SHA: {SHA}\nresultado\n")
    dato = c.verificar_evidencia("buena.txt", SHA, tmp_path)
    assert dato["ok"] is True


def test_gate_sin_evidencia_declarada_es_no_ejecutado():
    dato = c.estado_desde_evidencias("QG-03", SHA)
    assert dato["estado"] == "no_ejecutado"
    assert dato["detalle"] == "SIN_EVIDENCIA_DECLARADA"


# ── Git ──────────────────────────────────────────────────────────────────────

def test_sha_invalido_se_rechaza():
    assert c.sha_en_git("abc") is False


def test_sha_que_no_existe_en_git_se_rechaza():
    class P:
        returncode = 128
    assert c.sha_en_git(SHA, lambda *a, **k: P()) is False


# ── CI ───────────────────────────────────────────────────────────────────────

def test_ci_en_cola_es_bloqueante():
    dato = c.estado_ci(SHA, lambda s: [
        {"databaseId": 1, "status": "queued", "conclusion": "",
         "headSha": SHA}])
    assert dato["conclusion"] == "queued"


def test_un_run_de_otro_sha_no_acredita_este():
    dato = c.estado_ci(SHA, lambda s: [
        {"databaseId": 2, "status": "completed", "conclusion": "success",
         "headSha": OTRO}])
    assert dato["conclusion"] == "sin_run"


def test_ci_success_del_sha_correcto_acredita():
    dato = c.estado_ci(SHA, lambda s: [
        {"databaseId": 3, "status": "completed", "conclusion": "success",
         "headSha": SHA}])
    assert dato["conclusion"] == "success"


def test_si_gh_no_esta_disponible_la_ci_no_es_pass():
    def _falla(s):
        raise OSError("gh: not found")
    dato = c.estado_ci(SHA, _falla)
    assert dato["conclusion"] == "no_verificable"


# ── Suite ────────────────────────────────────────────────────────────────────

def _junit(tmp_path: Path, tests: int, failures: int, errors: int = 0) -> Path:
    ruta = tmp_path / "junit.xml"
    ruta.write_text(
        f'<?xml version="1.0"?><testsuites><testsuite name="s" tests="{tests}" '
        f'failures="{failures}" errors="{errors}" skipped="0"/></testsuites>',
        encoding="utf-8")
    return ruta


def test_sin_junit_la_suite_no_esta_acreditada():
    assert c.estado_suite(None)["estado"] == "no_ejecutado"


def test_una_suite_con_fallos_no_acredita(tmp_path):
    dato = c.estado_suite(_junit(tmp_path, tests=10, failures=1))
    assert dato["estado"] == "fallido"
    assert dato["detalle"] == "SUITE_CON_FALLOS"


def test_una_suite_limpia_acredita(tmp_path):
    dato = c.estado_suite(_junit(tmp_path, tests=10, failures=0))
    assert dato["estado"] == "ejecutado"
    assert dato["tests"] == 10


# ── Control de ejecucion (TD-0003) ───────────────────────────────────────────

def test_un_control_no_ejecutado_deja_qg02_bloqueado(tmp_path, monkeypatch):
    class P:
        returncode = 0
        stdout = json.dumps({
            "ok": True, "total_violations": 0,
            "checks": [
                {"control": "AP-40", "estado": "no_ejecutado",
                 "detalle": "dependencia_no_disponible", "hallazgos": 0},
                {"control": "AP-42", "estado": "ejecutado", "hallazgos": 0},
                {"control": "AP-43", "estado": "ejecutado", "hallazgos": 0}],
            "completo": False})
        stderr = ""

    control = c.control_ejecucion(ejecutar=lambda *a, **k: P())
    assert control["completo"] is False
    assert control["no_verificados"] == ["AP-40"]


# ── Orquestacion completa ────────────────────────────────────────────────────

def _entorno_completo(tmp_path, monkeypatch):
    """Evidencias con el SHA, control completo y CI en success."""
    for gate, rutas in c.EVIDENCIAS.items():
        for ruta in rutas:
            _evidencia(tmp_path, ruta, f"SHA: {SHA}\nevidencia de {gate}\n")

    class Git:
        returncode = 0

    class Audit:
        returncode = 0
        stdout = json.dumps({
            "total_violations": 0,
            "checks": [{"control": x, "estado": "ejecutado", "hallazgos": 0}
                       for x in ("AP-40", "AP-42", "AP-43")],
            "completo": True})
        stderr = ""

    def ejecutar(cmd, **kwargs):
        if "vault_norms.py" in " ".join(str(x) for x in cmd):
            return Audit()
        return Git()

    xml = _junit(tmp_path, tests=5, failures=0)
    Path(str(xml) + ".procedencia.json").write_text(
        '{"sha": "' + SHA + '", "exit": 0}', encoding="utf-8")
    return ejecutar, xml, lambda s: [
        {"databaseId": 9, "status": "completed", "conclusion": "success",
         "headSha": SHA}]


def test_el_caso_completo_permite_pass(tmp_path, monkeypatch):
    ejecutar, xml, ci = _entorno_completo(tmp_path, monkeypatch)
    resultado = c.colectar(SHA, suite_xml=xml, raiz=tmp_path,
                           ejecutar=ejecutar, consultar_ci=ci)
    assert resultado["ok"] is True
    assert resultado["politica"]["qg07"] == "PASS", resultado["politica"]


def test_sin_evidencias_el_colector_no_libera(tmp_path, monkeypatch):
    ejecutar, xml, ci = _entorno_completo(tmp_path, monkeypatch)
    # Borra las evidencias: la politica no puede inventar PASS.
    for rutas in c.EVIDENCIAS.values():
        for ruta in rutas:
            (tmp_path / ruta).unlink()
    resultado = c.colectar(SHA, suite_xml=xml, raiz=tmp_path,
                           ejecutar=ejecutar, consultar_ci=ci)
    assert resultado["politica"]["liberable"] is False
    assert resultado["politica"]["gates"]["QG-00"] == "NOT_RUN"


def test_ci_en_cola_bloquea_qg07_aunque_todo_lo_demas_este(tmp_path, monkeypatch):
    ejecutar, xml, _ = _entorno_completo(tmp_path, monkeypatch)
    resultado = c.colectar(
        SHA, suite_xml=xml, raiz=tmp_path, ejecutar=ejecutar,
        consultar_ci=lambda s: [{"databaseId": 1, "status": "queued",
                                 "conclusion": "", "headSha": SHA}])
    assert resultado["politica"]["qg07"] == "BLOCKED"
    assert any("CI_PENDIENTE" in m for m in resultado["politica"]["motivos"]["QG-07"])


def test_un_sha_que_no_existe_no_produce_dictamen(tmp_path):
    resultado = c.colectar(SHA, raiz=tmp_path,
                           ejecutar=lambda *a, **k: type("P", (), {"returncode": 128})())
    assert resultado["ok"] is False
    assert resultado["detalle"] == "SHA_NO_EXISTE_EN_GIT"
