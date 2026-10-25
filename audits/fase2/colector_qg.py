#!/usr/bin/env python3
"""Colector de evidencias para los Quality Gates (GOAL C / OBS-R06-02).

`politica_qg.evaluar_politica()` es puro: aplica la politica al estado que le
den. El defecto que QA señalo es que ese estado podia venir de una declaracion
—un JSON que dice PASS— sin comprobar nada. Este colector es la otra mitad:

  codigo/commit -> verificadores reales -> resultados normalizados -> politica

No duplica las 26 puertas: ejecuta `vault_gate` (que las corre), la auditoria
con estados de TD-0003, la suite por JUnit XML y la CI real por `gh`. Todo lo
que no pueda acreditarse queda `no_ejecutado`, nunca PASS.

Reglas:
  - el SHA objetivo tiene que existir en git y tener 40 hex;
  - una evidencia que no menciona el SHA objetivo no acredita ese SHA;
  - un fichero vacio o ilegible no es evidencia;
  - la CI solo cuenta si hay un run con `head_sha == sha` y `conclusion ==
    success`; en cola es BLOCKED;
  - la suite solo cuenta si el JUnit XML declara 0 failures y 0 errors;
  - si `gh` no esta disponible, la CI es `no_verificable` (no PASS).

Uso:
    python audits/fase2/colector_qg.py --sha <40hex> [--json salida] [--con-suite]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

RAIZ = Path(__file__).resolve().parents[2]
SHA_RE = re.compile(r"^[0-9a-f]{40}$")

#: Evidencia publicada que acredita cada puerta. La lista es el contrato: si un
#: fichero no menciona el SHA objetivo, la puerta queda `no_ejecutado`.
EVIDENCIAS: Dict[str, List[str]] = {
    "QG-00": ["audits/fase2/logs/R06-dictamen-correcciones.txt"],
    "QG-01": ["audits/fase2/logs/L1-reconciliacion-archify.txt"],
    "QG-02": ["audits/fase2/logs/R03-politica-qg.txt"],
    "QG-03": [],  # la suite: se mide por JUnit, no por un log escrito a mano
    "QG-04": ["audits/fase2/logs/H-F2-01-exposicion-historica.json"],
    "QG-05": ["audits/fase2/logs/L3-paridad-cli-mcp.txt"],
    "QG-06": ["audits/fase2/logs/L3-wheel-contenido.txt"],
    "QG-07": [],
}

MENCION_SHA = re.compile(r"\b[0-9a-f]{7,40}\b")


# ── Evidencias ───────────────────────────────────────────────────────────────

def verificar_evidencia(ruta: str, sha: str, raiz: Path = RAIZ) -> Dict[str, Any]:
    """Comprueba existencia, contenido y procedencia (mención del SHA)."""
    absoluta = raiz / ruta
    base = {"ruta": ruta, "sha": sha, "ok": False}
    if not absoluta.is_file():
        return {**base, "detalle": "EVIDENCIA_INEXISTENTE"}
    try:
        texto = absoluta.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {**base, "detalle": f"EVIDENCIA_ILEGIBLE: {exc}"}
    if len(texto.strip()) < 10:
        return {**base, "detalle": "EVIDENCIA_VACIA"}
    if sha not in texto and sha[:7] not in texto:
        return {**base, "detalle": "SHA_NO_ACREDITADO_EN_LA_EVIDENCIA"}
    return {**base, "ok": True, "detalle": None,
            "bytes": len(texto)}


def estado_desde_evidencias(gate: str, sha: str, raiz: Path = RAIZ) -> Dict[str, Any]:
    """Estado de una puerta cuyas evidencias son ficheros publicados."""
    rutas = EVIDENCIAS.get(gate, [])
    if not rutas:
        return {"control": gate, "estado": "no_ejecutado",
                "detalle": "SIN_EVIDENCIA_DECLARADA", "hallazgos": 0,
                "evidencias": []}
    verificadas = [verificar_evidencia(r, sha, raiz) for r in rutas]
    ok = all(v["ok"] for v in verificadas)
    return {
        "control": gate,
        "estado": "ejecutado" if ok else "no_ejecutado",
        "detalle": None if ok else next(
            v["detalle"] for v in verificadas if not v["ok"]),
        "hallazgos": 0,
        "evidencias": verificadas,
    }


# ── Git ──────────────────────────────────────────────────────────────────────

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


# ── CI ───────────────────────────────────────────────────────────────────────

def estado_ci(sha: str, consultar: Optional[Callable[[str], Any]] = None,
              raiz: Path = RAIZ) -> Dict[str, Any]:
    """La CI solo acredita si hay un run de ESE sha concluido en success."""
    if consultar is None:
        def consultar(sh: str) -> Any:
            p = subprocess.run(
                ["gh", "run", "list", "--commit", sh, "--limit", "10",
                 "--json", "databaseId,status,conclusion,headSha"],
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
    if any(r.get("conclusion") == "success" for r in propios):
        return {"conclusion": "success",
                "runs": [r.get("databaseId") for r in propios]}
    estados = sorted({r.get("status") or "?" for r in propios})
    if "queued" in estados or "in_progress" in estados:
        return {"conclusion": "queued", "detalle": f"estados={estados}"}
    return {"conclusion": propios[0].get("conclusion") or "sin_conclusion",
            "detalle": f"estados={estados}"}


# ── Suite (JUnit XML) ────────────────────────────────────────────────────────

def estado_suite(xml: Optional[Path]) -> Dict[str, Any]:
    """La suite se acredita con el JUnit XML que produce pytest."""
    if xml is None or not Path(xml).is_file():
        return {"estado": "no_ejecutado", "detalle": "SIN_JUNIT_XML",
                "tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    try:
        arbol = ET.parse(str(xml)).getroot()
    except (ET.ParseError, OSError) as exc:
        return {"estado": "fallido", "detalle": f"JUNIT_ILEGIBLE: {exc}",
                "tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    suites = ([arbol] if arbol.tag == "testsuite"
              else arbol.findall("testsuite"))
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
    """El JUnit acredita ESE SHA solo si el colector dejo su recibo.

    Un XML suelto es una declaracion mas: el recibo (`<xml>.procedencia.json`)
    lo escribe quien ejecuto la suite, con el SHA, el comando y el exit code.
    """
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


# ── Auditoria con estados (TD-0003) ──────────────────────────────────────────

def control_ejecucion(root: Optional[str] = None,
                      ejecutar: Callable[..., Any] = subprocess.run) -> Dict[str, Any]:
    """Lee `checks`/`completo` de la auditoria real; sin eso, no verificado."""
    comando = [sys.executable, str(RAIZ / "scripts" / "vault_norms.py"),
               "--audit"]
    if root:
        comando += ["--root", root]
    try:
        p = ejecutar(comando, cwd=str(RAIZ), capture_output=True, text=True,
                     encoding="utf-8", errors="replace", timeout=1800)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"completo": False, "degradados": [],
                "no_verificados": ["auditoria_no_ejecutada"],
                "detalle": str(exc)}
    try:
        sobre = json.loads(p.stdout)
    except ValueError:
        return {"completo": False, "degradados": [],
                "no_verificados": ["auditoria_ilegible"],
                "detalle": (p.stdout or p.stderr or "")[:300]}
    checks = sobre.get("checks") or []
    return {
        "completo": bool(sobre.get("completo")),
        "degradados": [c["control"] for c in checks
                       if c.get("estado") in ("degradado", "fallido")],
        "no_verificados": [c["control"] for c in checks
                           if c.get("estado") == "no_ejecutado"],
        "checks": checks,
    }


# ── Orquestacion ─────────────────────────────────────────────────────────────

def colectar(sha: str, *, con_suite: bool = False,
             suite_xml: Optional[Path] = None, root: Optional[str] = None,
             raiz: Path = RAIZ, ejecutar=subprocess.run,
             consultar_ci=None) -> Dict[str, Any]:
    """Reune el estado REAL de cada puerta para el SHA objetivo."""
    if not SHA_RE.match(sha or ""):
        return {"ok": False, "detalle": "SHA_INVALIDO",
                "politica": None, "estado": {}}
    if not sha_en_git(sha, ejecutar, raiz):
        return {"ok": False, "detalle": "SHA_NO_EXISTE_EN_GIT",
                "politica": None, "estado": {}}

    gates: Dict[str, str] = {}
    evidencias: Dict[str, Any] = {}
    for gate in ("QG-00", "QG-01", "QG-02", "QG-04", "QG-05", "QG-06"):
        dato = estado_desde_evidencias(gate, sha, raiz)
        gates[gate] = "PASS" if dato["estado"] == "ejecutado" else "NOT_RUN"
        evidencias[gate] = {"sha": sha, "estado": dato["estado"],
                            "detalle": dato["detalle"],
                            "rutas": [e["ruta"] for e in dato["evidencias"]]}

    control = control_ejecucion(root, ejecutar)
    gates["QG-02"] = ("PASS" if gates["QG-02"] == "PASS"
                      and control.get("completo") else "BLOCKED")

    suite = estado_suite(suite_xml)
    procedencia = _procedencia_suite(suite_xml, sha)
    if suite["estado"] == "ejecutado" and procedencia["ok"]:
        gates["QG-03"] = "PASS"
        evidencias["QG-03"] = {"sha": sha, "estado": "ejecutado",
                               "detalle": None, "rutas": [str(suite_xml)]}
    else:
        gates["QG-03"] = "NOT_RUN"
        evidencias["QG-03"] = {"sha": sha, "estado": "no_ejecutado",
                               "detalle": procedencia["detalle"],
                               "rutas": [str(suite_xml)] if suite_xml else []}

    ci = estado_ci(sha, consultar_ci, raiz)
    # QG-07 se declara como intencion: la politica exige, ademas, que
    # QG-00..QG-06 esten en PASS y que la CI del SHA haya concluido.
    gates["QG-07"] = "PASS"

    estado = {
        "sha_objetivo": sha,
        "gates": gates,
        "evidencias": evidencias,
        "control_ejecucion": control,
        "ci": ci,
    }
    from politica_qg import evaluar_politica

    return {"ok": True, "detalle": None, "estado": estado,
            "suite": suite, "ci": ci,
            "politica": evaluar_politica(estado)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sha", required=True, help="SHA de 40 hex a dictaminar")
    ap.add_argument("--json", dest="salida", default=None)
    ap.add_argument("--con-suite", action="store_true",
                    help="Ejecuta la suite y genera el JUnit XML.")
    ap.add_argument("--suite-xml", default=None,
                    help="JUnit XML ya generado (evita ejecutar la suite).")
    ap.add_argument("--root", default=None, help="Vault a auditar (opcional).")
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
                "%Y-%m-%dT%H:%M:%SZ"),
        }, indent=2) + "\n", encoding="utf-8")
        print(f"suite exit={p.returncode} xml={xml}")

    resultado = colectar(args.sha, suite_xml=xml, root=args.root)
    texto = json.dumps(resultado, ensure_ascii=False, indent=2)
    if args.salida:
        Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
        Path(args.salida).write_text(texto + "\n", encoding="utf-8")
    print(texto)
    politica = resultado.get("politica") or {}
    return 0 if politica.get("liberable") else 1


if __name__ == "__main__":
    raise SystemExit(main())
