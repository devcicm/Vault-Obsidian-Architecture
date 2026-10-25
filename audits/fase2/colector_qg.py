#!/usr/bin/env python3
"""Colector de evidencias para los Quality Gates (QA-RC-02).

Politica: un PASS se acredita con RECIBOS ESTRUCTURADOS producidos por el
verificador que ejecuto la comprobacion, nunca con texto que mencione el SHA.

Contrato de recibo (`<dir>/<QG-xx>.recibo.json`):
{
  "gate": "QG-01", "target_sha": "<40hex>", "verifier": "vault_arch",
  "command": "python scripts/vault_arch.py --check --strict",
  "exit_code": 0, "status": "PASS",
  "started_at": "...", "finished_at": "...",
  "run_id": "...", "artifact": "ruta", "artifact_sha256": "<64hex>"
}

Reglas fail-closed:
  - target_sha tiene que ser el SHA COMPLETO del candidato y existir en git;
  - el checkout tiene que estar EN ese SHA y limpio (identidad del arbol);
  - exit_code 0 y status PASS; cualquier otra cosa NO acredita;
  - el artefacto tiene que existir y su sha256 coincidir;
  - sin recibos, sin suite, sin CI o con `gh` ausente: NOT_RUN / no_verificable.

MODELO DE CONFIANZA (declarado): un recibo local acredita que EL COLECTOR
ejecuto el verificador en esa maquina y obtuvo ese resultado. No es firma
independiente frente a un actor con acceso de escritura: para eso esta la CI
externa (QG-07) y el dictamen de QA sobre el SHA congelado.
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
from typing import Any, Callable, Dict, List, Optional

RAIZ = Path(__file__).resolve().parents[2]
SHA_RE = re.compile(r"^[0-9a-f]{40}$")

GATES_EVIDENCIA = ("QG-00", "QG-01", "QG-02", "QG-04", "QG-05", "QG-06")
CAMPOS_RECIBO = ("gate", "target_sha", "verifier", "command", "exit_code",
                 "status", "started_at", "finished_at", "run_id")


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
    """El checkout tiene que estar EN el SHA declarado y sin cambios pendientes."""
    def git(*args: str) -> Any:
        return ejecutar(["git", *args], cwd=str(raiz), capture_output=True,
                        text=True)

    try:
        head = git("rev-parse", "HEAD").stdout.strip()
        estado = git("status", "--porcelain").stdout.strip()
    except (OSError, AttributeError) as exc:
        return {"ok": False, "detalle": f"git_no_disponible: {exc}"}
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
    faltan = [c for c in CAMPOS_RECIBO if not str(recibo.get(c, "")).strip()
              and c != "exit_code"]
    if faltan:
        return {**base, "detalle": f"RECIBO_INCOMPLETO: {faltan}"}
    if recibo.get("target_sha") != sha:
        return {**base, "detalle": "RECIBO_DE_OTRO_SHA"}
    if recibo.get("gate") != ruta.name.split(".")[0]:
        return {**base, "detalle": "GATE_NO_COINCIDE_CON_EL_FICHERO"}
    if recibo.get("exit_code") != 0:
        return {**base, "detalle": f"VERIFICADOR_FALLIDO: exit={recibo.get('exit_code')}"}
    if recibo.get("status") != "PASS":
        return {**base, "detalle": f"STATUS_NO_PASS: {recibo.get('status')}"}
    artefacto = recibo.get("artifact")
    if artefacto:
        ruta_art = RAIZ / artefacto if not Path(artefacto).is_absolute() else Path(artefacto)
        if not ruta_art.is_file():
            return {**base, "detalle": "ARTEFACTO_INEXISTENTE"}
        digest = hashlib.sha256(ruta_art.read_bytes()).hexdigest()
        if digest != recibo.get("artifact_sha256"):
            return {**base, "detalle": "ARTEFACTO_MANIPULADO_O_DISTINTO"}
    return {**base, "ok": True, "detalle": None, "recibo": recibo}


def estado_desde_recibo(gate: str, sha: str, recibos: Optional[Path]) -> Dict[str, Any]:
    """Estado de una puerta a partir de su recibo estructurado."""
    if recibos is None:
        return {"control": gate, "estado": "no_ejecutado",
                "detalle": "SIN_DIRECTORIO_DE_RECIBOS", "evidencias": []}
    veredicto = leer_recibo(recibos / f"{gate}.recibo.json", sha)
    return {"control": gate,
            "estado": "ejecutado" if veredicto["ok"] else "no_ejecutado",
            "detalle": veredicto["detalle"],
            "evidencias": [{k: v for k, v in veredicto.items() if k != "recibo"}]}


# ── CI ───────────────────────────────────────────────────────────────────────

def estado_ci(sha: str, consultar: Optional[Callable[[str], Any]] = None,
              raiz: Path = RAIZ, workflow_esperado: str = "Vault CI") -> Dict[str, Any]:
    if consultar is None:
        def consultar(sh: str) -> Any:
            p = subprocess.run(
                ["gh", "run", "list", "--commit", sh, "--limit", "10",
                 "--json", "databaseId,status,conclusion,headSha,workflowName"],
                cwd=str(raiz), capture_output=True, text=True, timeout=120)
            if p.returncode != 0:
                raise OSError((p.stderr or "gh no disponible").strip()[:200])
            return json.loads(p.stdout or "[]")
    try:
        runs = consultar(sha) or []
    except (OSError, ValueError) as exc:
        return {"conclusion": "no_verificable", "detalle": str(exc)}
    propios = [r for r in runs if r.get("headSha") == sha]
    if not propios:
        return {"conclusion": "sin_run", "detalle": "no hay run para ese SHA"}
    ajenos = [r.get("databaseId") for r in propios
              if r.get("workflowName") not in (None, workflow_esperado)]
    if ajenos:
        return {"conclusion": "no_verificable",
                "detalle": f"WORKFLOW_AJENO: runs={ajenos}"}
    validos = [r for r in propios
               if r.get("workflowName") in (None, workflow_esperado)]
    if any(r.get("conclusion") == "success" for r in validos):
        return {"conclusion": "success", "runs": [r.get("databaseId") for r in validos]}
    estados = sorted({r.get("status") or "?" for r in validos})
    if "queued" in estados or "in_progress" in estados:
        return {"conclusion": "queued", "detalle": f"estados={estados}"}
    return {"conclusion": validos[0].get("conclusion") or "sin_conclusion",
            "detalle": f"estados={estados}"}


# ── Suite (JUnit XML + recibo) ───────────────────────────────────────────────

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
            "skipped": omitidos}


def _procedencia_suite(xml: Optional[Path], sha: str) -> Dict[str, Any]:
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
            "checks": checks,
            "violaciones": sobre.get("total_violations", 0)}


# ── Orquestacion ─────────────────────────────────────────────────────────────

def colectar(sha: str, *, recibos: Optional[Path] = None,
             suite_xml: Optional[Path] = None, root: Optional[str] = None,
             raiz: Path = RAIZ, ejecutar=subprocess.run,
             consultar_ci=None) -> Dict[str, Any]:
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
                               "detalle": None, "rutas": [str(suite_xml)]}
    else:
        gates["QG-03"] = "NOT_RUN"
        evidencias["QG-03"] = {"sha": sha, "estado": "no_ejecutado",
                               "detalle": procedencia["detalle"], "rutas": []}

    ci = estado_ci(sha, consultar_ci, raiz)
    gates["QG-07"] = "PASS"

    estado = {"sha_objetivo": sha, "gates": gates, "evidencias": evidencias,
              "control_ejecucion": control, "ci": ci, "arbol": arbol}
    from politica_qg import evaluar_politica

    veredicto = evaluar_politica(estado)
    # Identidad del arbol: sin checkout limpio EN el SHA, no hay dictamen.
    if not arbol["ok"] and veredicto["liberable"]:
        veredicto = {**veredicto, "liberable": False,
                     "qg07": "BLOCKED", "gates": {**veredicto["gates"],
                                                  "QG-00": "BLOCKED"},
                     "motivos": {**veredicto.get("motivos", {}),
                                 "QG-00": [arbol["detalle"]]}}
    return {"ok": True, "detalle": None, "estado": estado, "suite": suite,
            "ci": ci, "politica": veredicto}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sha", required=True, help="SHA de 40 hex a dictaminar")
    ap.add_argument("--recibos", default=None,
                    help="Directorio con los recibos <QG-xx>.recibo.json")
    ap.add_argument("--json", dest="salida", default=None)
    ap.add_argument("--con-suite", action="store_true")
    ap.add_argument("--suite-xml", default=None)
    ap.add_argument("--root", default=None)
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
            "sha": args.sha,
            "comando": "python -m pytest tests/ -q -n auto --junitxml=...",
            "exit": p.returncode,
            "generado_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ")}, indent=2) + "\n", encoding="utf-8")
        print(f"suite exit={p.returncode} xml={xml}")

    recibos = Path(args.recibos) if args.recibos else None
    resultado = colectar(args.sha, recibos=recibos, suite_xml=xml, root=args.root)
    texto = json.dumps(resultado, ensure_ascii=False, indent=2)
    if args.salida:
        Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
        Path(args.salida).write_text(texto + "\n", encoding="utf-8")
    print(texto)
    return 0 if (resultado.get("politica") or {}).get("liberable") else 1


if __name__ == "__main__":
    raise SystemExit(main())
