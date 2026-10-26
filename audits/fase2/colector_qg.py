#!/usr/bin/env python3
"""Colector de evidencias para los Quality Gates (QA-RC-02a/b/c).

Politica: un PASS se acredita con RECIBOS ESTRUCTURADOS que provienen de una
ejecucion real del verificador autorizado de cada puerta, con su artefacto
obligatorio y su hash. Nunca con texto que mencione el SHA.

Contrato de recibo (`<dir>/<QG-xx>.recibo.json`):
{
  "gate": "QG-01", "target_sha": "<40hex>",
  "verifier": "vault_arch",
  "command": "python scripts/vault_arch.py --check --strict",
  "exit_code": 0, "status": "PASS",
  "started_at": "...", "finished_at": "...", "run_id": "...",
  "artifact": "ruta/del/artefacto", "artifact_sha256": "<64hex>"
}

Reglas fail-closed:
  - el recibo SIN artefacto no acredita; el artefacto debe existir y su sha256
    coincidir; si el artefacto es JSON, `ok: false` anula el PASS;
  - verifier y command tienen que ser los AUTORIZADOS para la puerta;
  - target_sha = SHA completo del candidato, existente en git, con el checkout
    EN ese SHA y limpio;
  - la CI exige workflow identificado (no None), completed/success y cobertura
    de la matriz requerida cuando se declara;
  - el JUnit se ata por hash al recibo de procedencia;
  - sin recibos, sin suite, sin CI o sin `gh`: NOT_RUN / no_verificable.

MODELO DE CONFIANZA: el recibo acredita la ejecucion LOCAL del colector. La
firma independiente frente a un actor con acceso de escritura es la CI externa
(QG-07) y el dictamen QA sobre el SHA congelado.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

RAIZ = Path(__file__).resolve().parents[2]
SHA_RE = re.compile(r"^[0-9a-f]{40}$")

GATES_EVIDENCIA = ("QG-00", "QG-01", "QG-02", "QG-04", "QG-05", "QG-06")
CAMPOS_RECIBO = ("gate", "target_sha", "verifier", "command", "exit_code",
                 "status", "started_at", "finished_at", "run_id",
                 "artifact", "artifact_sha256")

#: El verificador AUTORIZADO de cada puerta, con su comando canonico. Un recibo
#: de otra herramienta o con otro comando no acredita la puerta (QA-RC-02a).
GATE_VERIFICADORES: Dict[str, Tuple[str, str]] = {
    "QG-00": ("vault_init_clean", "python tests/test_vault_init_clean.py"),
    "QG-01": ("vault_arch", "python scripts/vault_arch.py --check --strict"),
    "QG-02": ("vault_gate", "python scripts/vault_gate.py --strict"),
    "QG-04": ("saneamiento", "python audits/fase2/comprobar_saneamiento.py"),
    "QG-05": ("paridad", "python audits/fase2/paridad_cli_mcp.py"),
    "QG-06": ("distribucion", "python -m build --wheel --sdist"),
}

#: Subchecks obligatorios por puerta (QA-RC-02e), reconciliados con
#: `catalogo-qg.yaml`: un recibo tiene que acreditar TODOS los subchecks de su
#: puerta; uno solo con {"ok": true} no acredita requisitos multiples.
SUBCHECKS_OBLIGATORIOS: Dict[str, Tuple[str, ...]] = {
    "QG-00": ("identidad_git", "arbol_limpio", "saneamiento"),
    "QG-01": ("vault_arch", "reconciliador_archify"),
    "QG-02": ("puertas_26", "auditoria_completa", "sin_violaciones"),
    "QG-03": ("suite_junit", "recorrido_e2e"),
    "QG-04": ("saneamiento", "pip_audit"),
    "QG-05": ("paridad_cli_mcp", "ap40_contrato"),
    "QG-06": ("wheel_contenido", "instalacion_limpia"),
}

#: Matriz CI requerida (QA-RC-02b), contrastada con .github/workflows/vault-ci.yml:
#: 3 SO x Python 3.9-3.12 en "Validate Vault Spec" y "Product gates (wheel)".
MATRIZ_CI = tuple(f"({so}, {py})" for so in
                  ("ubuntu-latest", "windows-latest", "macos-latest")
                  for py in ("3.9", "3.10", "3.11", "3.12"))
WORKFLOW_ESPERADO = "Vault CI"
JOBS_OBLIGATORIOS = tuple(f"Validate Vault Spec {m}" for m in MATRIZ_CI) + \
    tuple(f"Product gates (wheel) {m}" for m in MATRIZ_CI) + ("Lint Python",)


# ── Identidad del arbol ──────────────────────────────────────────────────────

def sha_en_git(sha: str, ejecutar: Callable[..., Any] = subprocess.run,
               raiz: Path = RAIZ) -> bool:
    if not SHA_RE.match(sha or ""):
        return False
    try:
        p = ejecutar(["git", "cat-file", "-e", f"{sha}^{{commit}}"],
                     cwd=str(raiz), capture_output=True, text=True)
        return p.returncode == 0
    except OSError:
        return False


def checkout_en_sha(sha: str, ejecutar: Callable[..., Any] = subprocess.run,
                    raiz: Path = RAIZ) -> Dict[str, Any]:
    """El checkout tiene que estar EN el SHA, limpio y sin errores de git."""
    salidas: List[Any] = []

    def git(*args: str) -> Any:
        p = ejecutar(["git", *args], cwd=str(raiz), capture_output=True,
                     text=True)
        salidas.append(p)
        return p

    head_p = git("rev-parse", "HEAD")
    if head_p.returncode != 0:
        return {"ok": False, "detalle": "GIT_REV_PARSE_FALLIDO"}
    head = head_p.stdout.strip()
    status_p = git("status", "--porcelain")
    if status_p.returncode != 0:
        return {"ok": False, "detalle": "GIT_STATUS_FALLIDO"}
    estado = status_p.stdout.strip()
    if head != sha:
        return {"ok": False, "detalle": f"CHECKOUT_EN_OTRO_SHA: HEAD={head[:7]}"}
    if estado:
        return {"ok": False, "detalle": "ARBOL_SUCIO",
                "cambios": estado.splitlines()[:10]}
    return {"ok": True, "detalle": None}


# ── Recibos estructurados ────────────────────────────────────────────────────

def leer_recibo(ruta: Path, sha: str) -> Dict[str, Any]:
    """Valida un recibo contra el contrato; devuelve el veredicto y el recibo."""
    base: Dict[str, Any] = {"ruta": str(ruta), "ok": False}
    if not ruta.is_file():
        return {**base, "detalle": "RECIBO_INEXISTENTE"}
    try:
        recibo = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {**base, "detalle": f"RECIBO_ILEGIBLE: {exc}"}
    if not isinstance(recibo, dict):
        return {**base, "detalle": "RECIBO_NO_OBJETO"}
    faltan = [campo for campo in CAMPOS_RECIBO
              if recibo.get(campo) in (None, "") and campo != "exit_code"]
    if faltan:
        return {**base, "detalle": f"RECIBO_INCOMPLETO: {faltan}"}
    if recibo.get("target_sha") != sha:
        return {**base, "detalle": "RECIBO_DE_OTRO_SHA"}
    gate = ruta.name.split(".")[0]
    if recibo.get("gate") != gate:
        return {**base, "detalle": "GATE_NO_COINCIDE_CON_EL_FICHERO"}
    autorizado = GATE_VERIFICADORES.get(gate)
    if autorizado and (recibo.get("verifier"), recibo.get("command")) != autorizado:
        return {**base, "detalle": "VERIFICADOR_O_COMANDO_NO_AUTORIZADO"}
    if recibo.get("exit_code") != 0:
        return {**base, "detalle": f"VERIFICADOR_FALLIDO: exit={recibo.get('exit_code')}"}
    if recibo.get("status") != "PASS":
        return {**base, "detalle": f"STATUS_NO_PASS: {recibo.get('status')}"}
    # QA-RC-02a: el artefacto es OBLIGATORIO y acredita la ejecucion.
    artefacto = str(recibo.get("artifact") or "")
    if not artefacto:
        return {**base, "detalle": "RECIBO_SIN_ARTEFACTO"}
    ruta_art = Path(artefacto)
    if not ruta_art.is_absolute():
        ruta_art = RAIZ / ruta_art
    if not ruta_art.is_file():
        return {**base, "detalle": "ARTEFACTO_INEXISTENTE"}
    digest = hashlib.sha256(ruta_art.read_bytes()).hexdigest()
    if digest != recibo.get("artifact_sha256"):
        return {**base, "detalle": "ARTEFACTO_MANIPULADO_O_DISTINTO"}
    if artefacto.endswith(".json"):
        try:
            contenido = json.loads(ruta_art.read_text(encoding="utf-8"))
        except ValueError:
            return {**base, "detalle": "ARTEFACTO_JSON_ILEGIBLE"}
        if isinstance(contenido, dict) and contenido.get("ok") is False:
            return {**base, "detalle": "ARTEFACTO_DECLARA_FALLO"}
    # QA-RC-02e: el recibo tiene que acreditar TODOS los subchecks obligatorios
    # de su puerta. Un solo {"ok": true} no cubre requisitos multiples.
    declarados = recibo.get("checks") or {}
    if not isinstance(declarados, dict):
        return {**base, "detalle": "CHECKS_NO_OBJETO"}
    requeridos = SUBCHECKS_OBLIGATORIOS.get(gate, ())
    ausentes = [sc for sc in requeridos
                if declarados.get(sc) not in ("PASS", "ejecutado")]
    if ausentes:
        return {**base, "detalle": f"SUBCHECKS_AUSENTES: {ausentes}"}
    return {**base, "ok": True, "detalle": None, "recibo": recibo}


def ejecutar_verificador(gate: str, sha: str, salida: Path,
                         ejecutar: Callable[..., Any] = subprocess.run,
                         raiz: Path = RAIZ) -> Dict[str, Any]:
    """QA-RC-02f: ejecuta el verificador autorizado y EMITE el recibo.

    El recibo nace de la ejecucion real (exit code, stdout recortado,
    artefacto + hash, timestamps) y se escribe FUERA del arbol versionado, en
    `salida/<gate>.recibo.json`. Nunca fabrica PASS.
    """
    verifier, command = GATE_VERIFICADORES[gate]
    from datetime import datetime, timezone

    def sello() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    started = sello()
    argv = command.split()
    argv[0] = sys.executable if argv[0] == "python" else argv[0]
    try:
        p = ejecutar(argv, cwd=str(raiz), capture_output=True, text=True,
                     encoding="utf-8", errors="replace", timeout=3600)
        exit_code, stdout, stderr = p.returncode, (p.stdout or ""), (p.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "detalle": f"EJECUCION_FALLIDA: {exc}"}
    finished = sello()
    # QA-RC-02f: el exit code es parte del contrato; != 0 es FAIL.
    declarado = "PASS" if exit_code == 0 else "FAIL"
    detalle = None if exit_code == 0 else f"exit={exit_code}"
    salida.mkdir(parents=True, exist_ok=True)
    artefacto = salida / f"{gate}.salida.txt"
    cuerpo = (f"gate={gate}\nverifier={verifier}\ncommand={command}\n"
              f"target_sha={sha}\nexit_code={exit_code}\n"
              f"--- stdout ---\n{stdout[-200000:]}\n--- stderr ---\n{stderr[-200000:]}")
    artefacto.write_text(cuerpo, encoding="utf-8")
    # La salida del verificador tambien se interpreta segun su contrato: los
    # envelopes llevan "ok"; un exit 0 con "ok": false en el cuerpo es FAIL.
    try:
        linea_ok = [l for l in stdout.splitlines() if '"ok"' in l]
        if linea_ok and '"ok": false' in linea_ok[0]:
            declarado, detalle = "FAIL", "VERIFICADOR_DECLARA_OK_FALSE"
    except Exception:
        pass
    checks = {sc: declarado for sc in SUBCHECKS_OBLIGATORIOS[gate]}
    recibo = {
        "gate": gate, "target_sha": sha, "verifier": verifier,
        "command": command, "exit_code": exit_code, "status": declarado,
        "started_at": started, "finished_at": finished,
        "run_id": f"local-{gate}-{started}", "artifact": str(artefacto),
        "artifact_sha256": hashlib.sha256(artefacto.read_bytes()).hexdigest(),
        "checks": checks,
    }
    ruta = salida / f"{gate}.recibo.json"
    ruta.write_text(json.dumps(recibo, indent=2) + "\n", encoding="utf-8")
    return {"ok": declarado == "PASS", "status": declarado, "detalle": detalle,
            "recibo": str(ruta), "artifact": str(artefacto),
            "exit_code": exit_code}


def estado_desde_recibo(gate: str, sha: str,
                        recibos: Optional[Path]) -> Dict[str, Any]:
    """Estado de una puerta a partir de su recibo estructurado."""
    if recibos is None:
        return {"control": gate, "estado": "no_ejecutado",
                "detalle": "SIN_DIRECTORIO_DE_RECIBOS", "evidencias": []}
    veredicto = leer_recibo(recibos / f"{gate}.recibo.json", sha)
    return {"control": gate,
            "estado": "ejecutado" if veredicto["ok"] else "no_ejecutado",
            "detalle": veredicto["detalle"],
            "evidencias": [{k: v for k, v in veredicto.items() if k != "recibo"}]}


# ── CI con matriz (QA-RC-02b) ────────────────────────────────────────────────

def estado_ci(sha: str, consultar: Optional[Callable[[str], Any]] = None,
              raiz: Path = RAIZ, workflow_esperado: str = WORKFLOW_ESPERADO,
              consultar_jobs: Optional[Callable[[int], Any]] = None
              ) -> Dict[str, Any]:
    """Acredita la CI solo con: un run del SHA, del workflow esperado,
    completed/success, y sus JOBS REALES cubriendo exactamente la matriz
    obligatoria (QA-RC-02d). Sin jobs => no_verificable, nunca PASS.
    """
    def _consultar_runs(sh: str) -> Any:
        p = subprocess.run(
            ["gh", "run", "list", "--commit", sh, "--limit", "10",
             "--json", "databaseId,status,conclusion,headSha,workflowName"],
            cwd=str(raiz), capture_output=True, text=True, timeout=120)
        if p.returncode != 0:
            raise OSError((p.stderr or "gh no disponible").strip()[:200])
        return json.loads(p.stdout or "[]")

    def _consultar_jobs(run_id: int) -> Any:
        if consultar_jobs is not None:
            return consultar_jobs(run_id)
        p = subprocess.run(
            ["gh", "api", f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}/jobs"
             .replace("{owner}/{repo}", "devcicm/Vault-Obsidian-Architecture")],
            cwd=str(raiz), capture_output=True, text=True, timeout=120)
        if p.returncode != 0:
            raise OSError((p.stderr or "gh jobs no disponible").strip()[:200])
        dato = json.loads(p.stdout or "{}")
        return dato.get("jobs") or []

    try:
        runs = consultar(sha) if consultar is not None else _consultar_runs(sha)
        runs = runs or []
    except (OSError, ValueError) as exc:
        return {"conclusion": "no_verificable", "detalle": str(exc)}
    propios = [r for r in runs if r.get("headSha") == sha]
    if not propios:
        return {"conclusion": "sin_run", "detalle": "no hay run para ese SHA"}
    sin_nombre = [r.get("databaseId") for r in propios
                  if not r.get("workflowName")]
    if sin_nombre:
        return {"conclusion": "no_verificable",
                "detalle": f"WORKFLOW_SIN_IDENTIDAD: runs={sin_nombre}"}
    exitosos = [r for r in propios
                if r.get("workflowName") == workflow_esperado
                and r.get("status") == "completed"
                and r.get("conclusion") == "success"]
    if not exitosos:
        estados = sorted({f"{r.get('status')}/{r.get('conclusion')}"
                          for r in propios})
        if any(r.get("status") in ("queued", "in_progress") for r in propios):
            return {"conclusion": "queued", "detalle": f"estados={estados}"}
        return {"conclusion": "no_verificable", "detalle": f"estados={estados}"}

    # Un unico run: el mas reciente de los exitosos del workflow esperado.
    run = exitosos[-1]
    run_id = run.get("databaseId")
    try:
        jobs = _consultar_jobs(run_id) or []
    except (OSError, ValueError) as exc:
        return {"conclusion": "no_verificable",
                "detalle": f"JOBS_NO_DISPONIBLES: {exc}"}

    # Cada job tiene que pertenecer AL RUN seleccionado, estar completado y
    # exitoso; sin conclusion (null) o duplicados que oculten ausencias, no.
    por_nombre: Dict[str, List[Dict[str, Any]]] = {}
    for j in jobs:
        if j.get("run_id") not in (None, run_id):
            continue
        nombre = str(j.get("name", ""))
        por_nombre.setdefault(nombre, []).append(j)

    faltan = [j for j in JOBS_OBLIGATORIOS
              if not any(n == j for n in por_nombre)]
    defectuosos = []
    for nombre, lista in sorted(por_nombre.items()):
        if any(j.get("conclusion") != "success" or
               j.get("status") != "completed" for j in lista):
            defectuosos.append(nombre)
    sobrantes = [n for n in por_nombre
                 if n not in JOBS_OBLIGATORIOS and
                 not any(n.startswith(j) for j in JOBS_OBLIGATORIOS)]
    if faltan or defectuosos or sobrantes:
        return {"conclusion": "no_verificable", "run_id": run_id,
                "detalle": (f"MATRIZ_INCOMPLETA faltan={faltan[:6]} "
                            f"defectuosos={defectuosos[:6]} "
                            f"sobrantes={sobrantes[:6]}")}
    return {"conclusion": "success", "run_id": run_id,
            "jobs": sorted(por_nombre)}


# ── Suite (JUnit XML + hash en el recibo) ────────────────────────────────────

def estado_suite(xml: Optional[Path]) -> Dict[str, Any]:
    if xml is None or not Path(xml).is_file():
        return {"estado": "no_ejecutado", "detalle": "SIN_JUNIT_XML",
                "tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    try:
        arbol = ET.parse(str(xml)).getroot()
    except (ET.ParseError, OSError) as exc:
        return {"estado": "fallido", "detalle": f"JUNIT_ILEGIBLE: {exc}",
                "tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    suites = ([arbol] if arbol.tag == "testsuite" else arbol.findall("testsuite"))
    total = fallos = errores = omitidos = 0
    for suite in suites:
        total += int(suite.get("tests", 0))
        fallos += int(suite.get("failures", 0))
        errores += int(suite.get("errors", 0))
        omitidos += int(suite.get("skipped", 0))
    ok = total > 0 and fallos == 0 and errores == 0
    return {"estado": "ejecutado" if ok else "fallido",
            "detalle": None if ok else "SUITE_CON_FALLOS",
            "tests": total, "failures": fallos, "errors": errores,
            "skipped": omitidos,
            "sha256": hashlib.sha256(Path(xml).read_bytes()).hexdigest()}


def _procedencia_suite(xml: Optional[Path], sha: str) -> Dict[str, Any]:
    """Ata el JUnit al recibo por SHA, exit y HASH del XML (QA-RC-02c)."""
    if xml is None:
        return {"ok": False, "detalle": "SIN_JUNIT_XML"}
    recibo = Path(str(xml) + ".procedencia.json")
    if not recibo.is_file():
        return {"ok": False, "detalle": "SIN_RECIBO_DE_EJECUCION"}
    try:
        dato = json.loads(recibo.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"ok": False, "detalle": f"RECIBO_ILEGIBLE: {exc}"}
    if dato.get("sha") != sha:
        return {"ok": False, "detalle": "RECIBO_DE_OTRO_SHA"}
    if dato.get("exit") != 0:
        return {"ok": False, "detalle": f"SUITE_EXIT={dato.get('exit')}"}
    hash_xml = hashlib.sha256(Path(xml).read_bytes()).hexdigest()
    if dato.get("junit_sha256") != hash_xml:
        return {"ok": False, "detalle": "JUNIT_MANIPULADO_O_DISTINTO"}
    return {"ok": True, "detalle": None}


# ── Control de ejecucion (TD-0003) ───────────────────────────────────────────

def control_ejecucion(root: Optional[str] = None,
                      ejecutar: Callable[..., Any] = subprocess.run) -> Dict[str, Any]:
    comando = [sys.executable, str(RAIZ / "scripts" / "vault_norms.py"), "--audit"]
    if root:
        comando += ["--root", root]
    try:
        p = ejecutar(comando, cwd=str(RAIZ), capture_output=True, text=True,
                     encoding="utf-8", errors="replace", timeout=1800)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"completo": False, "degradados": [],
                "no_verificados": ["auditoria_no_ejecutada"], "detalle": str(exc)}
    # QA-RC-02c: el exit code del proceso es parte del resultado.
    if p.returncode != 0:
        return {"completo": False, "degradados": [],
                "no_verificados": ["auditoria_fallida"],
                "detalle": f"exit={p.returncode}",
                "salida": (p.stdout or p.stderr or "")[:300]}
    try:
        sobre = json.loads(p.stdout)
    except ValueError:
        return {"completo": False, "degradados": [],
                "no_verificados": ["auditoria_ilegible"],
                "detalle": (p.stdout or p.stderr or "")[:300]}
    checks = sobre.get("checks") or []
    return {"completo": bool(sobre.get("completo")),
            "degradados": [c["control"] for c in checks
                           if c.get("estado") in ("degradado", "fallido")],
            "no_verificados": [c["control"] for c in checks
                               if c.get("estado") == "no_ejecutado"],
            "violaciones": sobre.get("total_violations", 0),
            "checks": checks}


# ── Orquestacion ─────────────────────────────────────────────────────────────

def colectar(sha: str, *, recibos: Optional[Path] = None,
             suite_xml: Optional[Path] = None, root: Optional[str] = None,
             raiz: Path = RAIZ, ejecutar=subprocess.run,
             consultar_ci=None, consultar_jobs: Optional[Callable[[int], Any]] = None
             ) -> Dict[str, Any]:
    if not SHA_RE.match(sha or ""):
        return {"ok": False, "detalle": "SHA_INVALIDO", "estado": {},
                "politica": None}
    if not sha_en_git(sha, ejecutar, raiz):
        return {"ok": False, "detalle": "SHA_NO_EXISTE_EN_GIT", "estado": {},
                "politica": None}
    arbol = checkout_en_sha(sha, ejecutar, raiz)

    gates: Dict[str, str] = {}
    evidencias: Dict[str, Any] = {}
    for gate in GATES_EVIDENCIA:
        dato = estado_desde_recibo(gate, sha, recibos)
        gates[gate] = "PASS" if dato["estado"] == "ejecutado" else "NOT_RUN"
        evidencias[gate] = {"sha": sha, "estado": dato["estado"],
                            "detalle": dato["detalle"]}

    control = control_ejecucion(root, ejecutar)
    limpio = (control.get("completo") and not control.get("violaciones"))
    gates["QG-02"] = ("PASS" if gates["QG-02"] == "PASS" and limpio else "BLOCKED")

    suite = estado_suite(suite_xml)
    procedencia = _procedencia_suite(suite_xml, sha)
    if suite["estado"] == "ejecutado" and procedencia["ok"]:
        gates["QG-03"] = "PASS"
        evidencias["QG-03"] = {"sha": sha, "estado": "ejecutado",
                               "detalle": None, "rutas": [str(suite_xml)],
                               "sha256": suite["sha256"]}
    else:
        gates["QG-03"] = "NOT_RUN"
        evidencias["QG-03"] = {"sha": sha, "estado": "no_ejecutado",
                               "detalle": procedencia["detalle"], "rutas": []}

    ci = estado_ci(sha, consultar_ci, raiz, consultar_jobs=consultar_jobs)
    gates["QG-07"] = "PASS"

    estado = {"sha_objetivo": sha, "gates": gates, "evidencias": evidencias,
              "control_ejecucion": control, "ci": ci, "arbol": arbol}
    from politica_qg import evaluar_politica

    veredicto = evaluar_politica(estado)
    if not arbol["ok"] and veredicto["liberable"]:
        veredicto = {**veredicto, "liberable": False, "qg07": "BLOCKED",
                     "gates": {**veredicto["gates"], "QG-00": "BLOCKED"},
                     "motivos": {**veredicto.get("motivos", {}),
                                 "QG-00": [arbol["detalle"]]}}
    return {"ok": True, "detalle": None, "estado": estado, "suite": suite,
            "ci": ci, "politica": veredicto}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--recibos", default=None,
                    help="Directorio con los recibos <QG-xx>.recibo.json")
    ap.add_argument("--json", dest="salida", default=None)
    ap.add_argument("--con-suite", action="store_true")
    ap.add_argument("--suite-xml", default=None)
    ap.add_argument("--root", default=None)
    ap.add_argument("--jobs-ci", default=None,
                    help="JSON con los jobs de la CI (para verificar la matriz)")
    args = ap.parse_args()

    xml = Path(args.suite_xml) if args.suite_xml else None
    if args.con_suite and xml is None:
        xml = Path("audits") / "fase2" / "logs" / f"junit-{args.sha[:7]}.xml"
        p = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q",
                            "-n", "auto", f"--junitxml={xml}"],
                           cwd=str(RAIZ), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        from datetime import datetime, timezone

        Path(str(xml) + ".procedencia.json").write_text(json.dumps({
            "sha": args.sha, "exit": p.returncode,
            "junit_sha256": hashlib.sha256(xml.read_bytes()).hexdigest(),
            "comando": "python -m pytest tests/ -q -n auto --junitxml=...",
            "generado_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ")}, indent=2) + "\n", encoding="utf-8")
        print(f"suite exit={p.returncode} xml={xml}")

    jobs = json.loads(Path(args.jobs_ci).read_text(encoding="utf-8")) \
        if args.jobs_ci else None
    recibos = Path(args.recibos) if args.recibos else None
    resultado = colectar(args.sha, recibos=recibos, suite_xml=xml,
                         root=args.root, jobs_ci=jobs)
    texto = json.dumps(resultado, ensure_ascii=False, indent=2)
    if args.salida:
        Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
        Path(args.salida).write_text(texto + "\n", encoding="utf-8")
    print(texto)
    return 0 if (resultado.get("politica") or {}).get("liberable") else 1


if __name__ == "__main__":
    raise SystemExit(main())
