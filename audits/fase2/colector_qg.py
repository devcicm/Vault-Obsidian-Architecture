#!/usr/bin/env python3
"""Colector de evidencias para los Quality Gates (QA-RC-02g/h/i).

Cada PUERTA tiene varios SUBCHECKS y cada subcheck se ejecuta por su cuenta:
su verificador, su comando (o funcion interna), su exit code, su artefacto y
su SHA-256. La puerta solo pasa si TODOS sus subchecks pasan. No se reparte el
resultado de un comando entre los subchecks de la puerta: eso era la
autocertificacion que QA-RC-02g prohibe.

Cadena de procedencia:

    SHA INMUTABLE -> CHECKOUT VERIFICADO -> SUBCHECK EJECUTADO
    -> ARTEFACTO + SHA256 -> RECIBO POR PUERTA -> COLECTOR -> DICTAMEN

Los recibos se escriben FUERA del arbol versionado (`--recibos <dir>`), para
que el commit candidato no contenga su propia acreditacion (circularidad).

MODELO DE CONFIANZA: un recibo acredita la ejecucion LOCAL de ese verificador
en esa maquina, con su exit code y su artefacto. No es firma frente a un actor
con escritura: para eso estan la CI externa (QG-07) y el dictamen de QA sobre
el SHA congelado.
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

GATES_EVIDENCIA = ("QG-00", "QG-01", "QG-02", "QG-03", "QG-04", "QG-05", "QG-06")

#: Comandos reales de los verificadores del repositorio (QA-RC-02g). Cada
#: subcheck tiene su propio verificador: ejecutar uno NO acredita los demas.
COMANDOS = {
    "vault_arch": ["scripts/vault_arch.py", "--check", "--strict"],
    "vault_gate": ["scripts/vault_gate.py", "--strict"],
    "vault_norms_audit": ["scripts/vault_norms.py", "--audit"],
    "saneamiento": ["audits/fase2/comprobar_saneamiento.py"],
    "reconciliador_archify": ["audits/fase2/reconciliar_archify.py", "--check"],
    "ap40_contrato": ["scripts/vault_mcp_catalog.py", "--check-params"],
    "contencion": ["scripts/vault_foreign_check.py", "--self-test"],
    "operaciones_destructivas": ["-m", "pytest", "tests/test_vault_init_clean.py", "-q"],
    "construccion": ["-m", "build", "--wheel", "--sdist"],
    # Con argv propio: se completan en tiempo de ejecucion.
    "pip_audit": ["-m", "pip_audit"],
    "paridad_cli_mcp": ["audits/fase2/paridad_cli_mcp.py"],
}

#: Contrato por puerta: subcheck -> {tipo, verificador, ...}.
#: tipo: comando | interno | derivado | externo
SUBCONTRATOS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "QG-00": {
        "identidad_git": {"tipo": "interno", "verificador": "identidad_git"},
        "arbol_limpio": {"tipo": "interno", "verificador": "arbol_limpio"},
        "saneamiento": {"tipo": "comando", "verificador": "saneamiento"},
        "reconciliador_archify": {"tipo": "comando",
                                  "verificador": "reconciliador_archify"},
    },
    "QG-01": {
        "vault_arch": {"tipo": "comando", "verificador": "vault_arch"},
        "reconciliador_archify": {"tipo": "comando",
                                  "verificador": "reconciliador_archify"},
    },
    "QG-02": {
        "puertas_26": {"tipo": "comando", "verificador": "vault_gate"},
        "auditoria_completa": {"tipo": "comando",
                               "verificador": "vault_norms_audit"},
        "sin_violaciones": {"tipo": "derivado", "verificador": "sin_violaciones",
                            "origen": "auditoria_completa",
                            "predicado": "total_violations==0"},
    },
    "QG-03": {
        "suite_junit": {"tipo": "externo", "verificador": "pytest_junit"},
        "recorrido_e2e": {"tipo": "externo", "verificador": "recorrido_e2e"},
    },
    "QG-04": {
        "saneamiento": {"tipo": "comando", "verificador": "saneamiento"},
        "pip_audit": {"tipo": "comando", "verificador": "pip_audit"},
        "contencion": {"tipo": "comando", "verificador": "contencion"},
        "operaciones_destructivas": {"tipo": "comando",
                                     "verificador": "operaciones_destructivas"},
    },
    "QG-05": {
        "paridad_cli_mcp": {"tipo": "comando", "verificador": "paridad_cli_mcp"},
        "ap40_contrato": {"tipo": "comando", "verificador": "ap40_contrato"},
    },
    "QG-06": {
        "construccion": {"tipo": "comando", "verificador": "construccion"},
        "wheel_contenido": {"tipo": "interno", "verificador": "wheel_contenido"},
        "instalacion_limpia": {"tipo": "externo",
                               "verificador": "recorrido_e2e"},
    },
}

#: Matriz CI obligatoria, contrastada con .github/workflows/vault-ci.yml:
#: 3 SO x Python 3.9-3.12 en "Validate Vault Spec" y "Product gates (wheel)",
#: mas el lint.
MATRIZ_CI = tuple(f"({so}, {py})" for so in
                  ("ubuntu-latest", "windows-latest", "macos-latest")
                  for py in ("3.9", "3.10", "3.11", "3.12"))
WORKFLOW_ESPERADO = "Vault CI"
JOBS_OBLIGATORIOS = tuple(f"Validate Vault Spec {m}" for m in MATRIZ_CI) + \
    tuple(f"Product gates (wheel) {m}" for m in MATRIZ_CI) + ("Lint Python",)

ESTADO_OK = "ejecutado"
ESTADOS = ("ejecutado", "degradado", "fallido", "no_ejecutado")


# ── Utilidades ───────────────────────────────────────────────────────────────

def _sello() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _argv(spec: List[str], raiz: Path) -> List[str]:
    """Convierte la especificacion del comando en argv real."""
    if spec and spec[0] == "-m":
        return [sys.executable, "-m"] + spec[1:]
    return [sys.executable, str(raiz / spec[0])] + spec[1:]


def checkout_en_sha(sha: str, ejecutar: Callable[..., Any] = subprocess.run,
                    raiz: Path = RAIZ) -> Dict[str, Any]:
    """El checkout tiene que estar EN el SHA y sin cambios pendientes.

    Se mide el estado del árbol en el momento en que se ejecutan los
    verificadores: algunos escriben artefactos de runtime propios y ensuciarian
    la comprobación posterior.
    """
    def git(*args: str) -> Any:
        return ejecutar(["git", *args], cwd=str(raiz), capture_output=True,
                        text=True)

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


# ── Checks internos (funciones propias del colector) ─────────────────────────

def _check_identidad_git(sha: str, raiz: Path) -> Dict[str, Any]:
    """El SHA existe en git, es un commit y el HEAD apunta a el."""
    def git(*args: str) -> Tuple[int, str]:
        p = subprocess.run(["git", *args], cwd=str(raiz), capture_output=True,
                           text=True, timeout=120)
        return p.returncode, p.stdout.strip()

    rc, head = git("rev-parse", "HEAD")
    if rc != 0:
        return {"ok": False, "detalle": "GIT_REV_PARSE_FALLIDO"}
    rc2, _ = git("cat-file", "-e", f"{sha}^{{commit}}")
    if rc2 != 0:
        return {"ok": False, "detalle": "SHA_NO_EXISTE_EN_GIT"}
    if head != sha:
        return {"ok": False, "detalle": f"HEAD_DISTINTO:{head[:7]}"}
    return {"ok": True, "detalle": None, "datos": {"head": head}}


def _check_arbol_limpio(sha: str, raiz: Path) -> Dict[str, Any]:
    p = subprocess.run(["git", "status", "--porcelain"], cwd=str(raiz),
                       capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        return {"ok": False, "detalle": "GIT_STATUS_FALLIDO"}
    if p.stdout.strip():
        return {"ok": False, "detalle": "ARBOL_SUCIO",
                "datos": {"cambios": p.stdout.splitlines()[:10]}}
    return {"ok": True, "detalle": None}


def _check_wheel_contenido(sha: str, raiz: Path,
                           contexto: Dict[str, Any]) -> Dict[str, Any]:
    """El artefacto construido existe y no lleva trazas ni material ajeno."""
    dist = Path(contexto.get("dist") or (RAIZ / "dist" / "rc"))
    wheels = sorted(dist.glob("*.whl"))
    if not wheels:
        return {"ok": False, "detalle": "SIN_WHEEL_CONSTRUIDA"}
    import zipfile

    prohibidas = (".tool-trace", ".voice-counter", ".locks", "audits/",
                  "tests/", ".history", "__pycache__")
    salida = []
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as z:
            malos = [n for n in z.namelist()
                     if any(p in n for p in prohibidas)]
            salida.append({"wheel": wheel.name, "sha256": _sha256(wheel),
                            "ficheros": len(z.namelist()),
                            "material_ajeno": malos})
    if any(s["material_ajeno"] for s in salida):
        return {"ok": False, "detalle": "WHEEL_CON_MATERIAL_AJENO",
                "datos": {"artefactos": salida}}
    return {"ok": True, "detalle": None, "datos": {"artefactos": salida}}


INTERNOS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "identidad_git": _check_identidad_git,
    "arbol_limpio": _check_arbol_limpio,
    "wheel_contenido": _check_wheel_contenido,
}


# ── Ejecucion por subcheck ───────────────────────────────────────────────────

def _registro(nombre: str, verificador: str, estado: str, detalle: str | None,
              artefacto: Optional[Path], started: str, finished: str,
              exit_code: Optional[int] = None,
              datos: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    registro = {
        "subcheck": nombre, "verificador": verificador, "estado": estado,
        "detalle": detalle, "exit_code": exit_code,
        "artifact": str(artefacto) if artefacto else None,
        "artifact_sha256": _sha256(artefacto) if artefacto and artefacto.is_file()
        else None,
        "started_at": started, "finished_at": finished,
    }
    if datos:
        registro["datos"] = datos
    return registro


def _ejecutar_subcheck(gate: str, nombre: str, spec: Dict[str, Any], sha: str,
                       salida: Path, ejecutar: Callable[..., Any],
                       raiz: Path, contexto: Dict[str, Any]
                       ) -> Dict[str, Any]:
    started = _sello()
    verificador = spec.get("verificador", nombre)
    tipo = spec.get("tipo")

    if tipo == "interno":
        funcion = INTERNOS.get(verificador)
        if funcion is None:
            return _registro(nombre, verificador, "no_ejecutado",
                             "VERIFICADOR_INTERNO_DESCONOCIDO", None,
                             started, _sello())
        try:
            if verificador == "wheel_contenido":
                resultado = funcion(sha, raiz, contexto)
            else:
                resultado = funcion(sha, raiz)
        except Exception as exc:  # noqa: BLE001 - el fallo se declara, no se calla
            return _registro(nombre, verificador, "fallido", str(exc), None,
                             started, _sello())
        artefacto = salida / f"{gate}.{nombre}.json"
        artefacto.parent.mkdir(parents=True, exist_ok=True)
        artefacto.write_text(json.dumps(resultado, indent=2, default=str) + "\n",
                             encoding="utf-8")
        estado = ESTADO_OK if resultado.get("ok") else "fallido"
        return _registro(nombre, verificador, estado, resultado.get("detalle"),
                         artefacto, started, _sello(),
                         datos=resultado.get("datos"))

    if tipo == "comando":
        comando = COMANDOS.get(verificador)
        if comando is None:
            return _registro(nombre, verificador, "no_ejecutado",
                             "VERIFICADOR_SIN_COMANDO", None, started, _sello())
        argv = _argv(list(comando), raiz)
        if verificador == "construccion":
            dist = salida.parent / "dist"
            argv += ["--outdir", str(dist)]
            contexto["dist"] = str(dist)
        if verificador == "pip_audit":
            interprete = contexto.get("pip_audit_python")
            if not interprete:
                return _registro(nombre, verificador, "no_ejecutado",
                                 "PIP_AUDIT_REQUIERE_INTERPRETE", None,
                                 started, _sello())
            argv = [str(interprete), "-m", "pip_audit", "--progress-spinner",
                    "off"]
        if verificador == "paridad_cli_mcp":
            if not (contexto.get("paridad_venv") and
                    contexto.get("paridad_runtime")):
                return _registro(nombre, verificador, "no_ejecutado",
                                 "PARIDAD_REQUIERE_VENV_Y_RUNTIME", None,
                                 started, _sello())
            argv = [sys.executable, str(raiz / "audits" / "fase2" /
                                       "paridad_cli_mcp.py"),
                    "--venv", str(contexto["paridad_venv"]),
                    "--runtime", str(contexto["paridad_runtime"])]
        try:
            p = ejecutar(argv, cwd=str(raiz), capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=7200)
            exit_code, stdout, stderr = p.returncode, (p.stdout or ""), (p.stderr or "")
        except (OSError, subprocess.SubprocessError) as exc:
            return _registro(nombre, verificador, "no_ejecutado",
                             f"EJECUCION_FALLIDA: {exc}", None, started, _sello())
        artefacto = salida / f"{gate}.{nombre}.salida.txt"
        artefacto.parent.mkdir(parents=True, exist_ok=True)
        artefacto.write_text(
            f"subcheck={nombre}\nverificador={verificador}\n"
            f"argv={' '.join(argv)}\nexit_code={exit_code}\n"
            f"--- stdout ---\n{stdout[-400000:]}\n"
            f"--- stderr ---\n{stderr[-400000:]}", encoding="utf-8")
        estado, detalle = ESTADO_OK, None
        if exit_code != 0:
            estado, detalle = "fallido", f"exit={exit_code}"
        elif not stdout.strip() and not stderr.strip():
            # Una salida vacia no es evidencia de nada.
            estado, detalle = "degradado", "SALIDA_VACIA"
        else:
            # El contrato del verificador: un envelope con ok:false es FAIL.
            for linea in stdout.splitlines():
                if '"ok": false' in linea:
                    estado, detalle = "fallido", "VERIFICADOR_DECLARA_OK_FALSE"
                    break
        return _registro(nombre, verificador, estado, detalle, artefacto,
                         started, _sello(), exit_code=exit_code)

    if tipo == "derivado":
        origen = spec.get("origen")
        registros = contexto.get("registros", {}).get(gate, {})
        previo = registros.get(origen)
        if previo is None or not previo.get("artifact"):
            return _registro(nombre, verificador, "no_ejecutado",
                             f"ORIGEN_NO_EJECUTADO:{origen}", None, started,
                             _sello())
        texto = ""
        try:
            texto = Path(previo["artifact"]).read_text(encoding="utf-8",
                                                       errors="replace")
        except OSError as exc:
            return _registro(nombre, verificador, "degradado",
                             f"ORIGEN_ILEGIBLE: {exc}", None, started, _sello())
        datos = None
        for linea in texto.splitlines():
            linea = linea.strip()
            if linea.startswith("{"):
                try:
                    datos = json.loads(linea)
                    break
                except ValueError:
                    continue
        if datos is None:
            return _registro(nombre, verificador, "degradado",
                             "ORIGEN_SIN_ENVELOPE_JSON", None, started, _sello())
        if isinstance(datos, dict) and "total_violations" in datos:
            valor = datos.get("total_violations")
            ok = valor == 0
            return _registro(nombre, verificador, ESTADO_OK if ok else "fallido",
                             None if ok else f"total_violations={valor}",
                             Path(previo["artifact"]), started, _sello(),
                             datos={"total_violations": valor})
        return _registro(nombre, verificador, "degradado",
                         "PREDICADO_NO_APLICABLE", None, started, _sello())

    if tipo == "externo":
        fuente = spec.get("verificador")
        artefacto = contexto.get(fuente)
        if artefacto is None:
            return _registro(nombre, verificador, "no_ejecutado",
                             f"FALTA_EVIDENCIA_EXTERNA:{fuente}", None,
                             started, _sello())
        ruta = Path(artefacto)
        if not ruta.is_file():
            return _registro(nombre, verificador, "no_ejecutado",
                             "EVIDENCIA_EXTERNA_INEXISTENTE", None, started,
                             _sello())
        estado = ESTADO_OK
        detalle = None
        if fuente == "recorrido_e2e":
            try:
                datos = json.loads(ruta.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                return _registro(nombre, verificador, "degradado",
                                 f"E2E_ILEGIBLE: {exc}", None, started, _sello())
            if not datos.get("todos_ok"):
                estado, detalle = "fallido", "E2E_CON_PASOS_FALLIDOS"
        elif fuente == "pytest_junit":
            procedencia = _procedencia_suite(ruta, sha)
            if not procedencia["ok"]:
                return _registro(nombre, verificador, "no_ejecutado",
                                 f"JUNIT_SIN_PROCEDENCIA: {procedencia['detalle']}",
                                 None, started, _sello())
            try:
                arbol = ET.parse(str(ruta)).getroot()
            except (ET.ParseError, OSError) as exc:
                return _registro(nombre, verificador, "degradado",
                                 f"JUNIT_ILEGIBLE: {exc}", None, started, _sello())
            suites = ([arbol] if arbol.tag == "testsuite"
                      else arbol.findall("testsuite"))
            fallos = sum(int(s.get("failures", 0)) for s in suites)
            errores = sum(int(s.get("errors", 0)) for s in suites)
            total = sum(int(s.get("tests", 0)) for s in suites)
            if total == 0 or fallos or errores:
                estado, detalle = "fallido", f"SUITE tests={total} fallos={fallos}"
        return _registro(nombre, verificador, estado, detalle, ruta, started,
                         _sello())

    return _registro(nombre, verificador, "no_ejecutado",
                     "TIPO_DE_SUBCHECK_DESCONOCIDO", None, started, _sello())


def ejecutar_verificador(gate: str, sha: str, salida: Path,
                         *, ejecutar: Callable[..., Any] = subprocess.run,
                         raiz: Path = RAIZ,
                         contexto: Optional[Dict[str, Any]] = None
                         ) -> Dict[str, Any]:
    """Ejecuta TODOS los subchecks de la puerta y emite el recibo.

    El recibo solo declara PASS si cada subcheck tiene su propio artefacto y
    su propio verificador ejecutado (QA-RC-02g).
    """
    ctx = dict(contexto or {})
    ctx.setdefault("registros", {})
    salida.mkdir(parents=True, exist_ok=True)
    registros: Dict[str, Any] = {}
    ctx["registros"][gate] = registros
    for nombre, spec in SUBCONTRATOS.get(gate, {}).items():
        registros[nombre] = _ejecutar_subcheck(gate, nombre, spec, sha, salida,
                                               ejecutar, raiz, ctx)
    estados = {n: r["estado"] for n, r in registros.items()}
    ok = bool(estados) and all(e == ESTADO_OK for e in estados.values())
    manifiesto = salida / f"{gate}.subchecks.json"
    manifiesto.write_text(json.dumps(registros, indent=2, default=str) + "\n",
                          encoding="utf-8")
    recibo = {
        "gate": gate, "target_sha": sha, "verificador": "colector_qg",
        "command": f"python audits/fase2/colector_qg.py --sha {sha} --ejecutar",
        "exit_code": 0 if ok else 1, "status": "PASS" if ok else "FAIL",
        "started_at": min(r["started_at"] for r in registros.values()),
        "finished_at": max(r["finished_at"] for r in registros.values()),
        "run_id": f"local-{gate}-{sha[:7]}",
        "artifact": str(manifiesto), "artifact_sha256": _sha256(manifiesto),
        "checks": estados, "subchecks": registros,
    }
    ruta = salida / f"{gate}.recibo.json"
    ruta.write_text(json.dumps(recibo, indent=2, default=str) + "\n",
                    encoding="utf-8")
    return {"ok": ok, "status": recibo["status"], "recibo": str(ruta),
            "checks": estados,
            "fallidos": [n for n, e in estados.items() if e != ESTADO_OK]}


# ── Validacion de recibos ────────────────────────────────────────────────────

def leer_recibo(ruta: Path, sha: str) -> Dict[str, Any]:
    """Valida un recibo: SHA, gate, artefactos (agregado e individuales) y
    subchecks en estado ejecutado."""
    base: Dict[str, Any] = {"ruta": str(ruta), "ok": False}
    if not ruta.is_file():
        return {**base, "detalle": "RECIBO_INEXISTENTE"}
    try:
        recibo = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {**base, "detalle": f"RECIBO_ILEGIBLE: {exc}"}
    if not isinstance(recibo, dict):
        return {**base, "detalle": "RECIBO_NO_OBJETO"}
    gate = ruta.name.split(".")[0]
    if recibo.get("gate") != gate:
        return {**base, "detalle": "GATE_NO_COINCIDE_CON_EL_FICHERO"}
    if recibo.get("target_sha") != sha:
        return {**base, "detalle": "RECIBO_DE_OTRO_SHA"}
    if recibo.get("exit_code") != 0:
        return {**base, "detalle": f"VERIFICADOR_FALLIDO: exit={recibo.get('exit_code')}"}
    if recibo.get("status") != "PASS":
        return {**base, "detalle": f"STATUS_NO_PASS: {recibo.get('status')}"}
    requeridos = tuple(SUBCONTRATOS.get(gate, {}))
    checks = recibo.get("checks") or {}
    if not isinstance(checks, dict):
        return {**base, "detalle": "CHECKS_NO_OBJETO"}
    ausentes = [sc for sc in requeridos if checks.get(sc) != ESTADO_OK]
    if ausentes:
        return {**base, "detalle": f"SUBCHECKS_AUSENTES: {ausentes}"}
    # QA-RC-02g: cada subcheck acredita con SU artefacto; un recibo que dice
    # PASS pero sin artefactos individuales no acredita.
    subchecks = recibo.get("subchecks") or {}
    if not isinstance(subchecks, dict):
        return {**base, "detalle": "SUBCHECKS_NO_OBJETO"}
    for nombre in requeridos:
        registro = subchecks.get(nombre)
        if not isinstance(registro, dict):
            return {**base, "detalle": f"SUBCHECK_SIN_REGISTRO: {nombre}"}
        artefacto = registro.get("artifact")
        if not artefacto or not Path(artefacto).is_file():
            return {**base, "detalle": f"SUBCHECK_SIN_ARTEFACTO: {nombre}"}
        if _sha256(Path(artefacto)) != registro.get("artifact_sha256"):
            return {**base, "detalle": f"SUBCHECK_ARTIFACTO_MANIPULADO: {nombre}"}
    agregado = recibo.get("artifact")
    if not agregado or not Path(agregado).is_file():
        return {**base, "detalle": "RECIBO_SIN_ARTEFACTO_AGREGADO"}
    if _sha256(Path(agregado)) != recibo.get("artifact_sha256"):
        return {**base, "detalle": "ARTEFACTO_AGREGADO_MANIPULADO"}
    return {**base, "ok": True, "detalle": None, "recibo": recibo}


def estado_desde_recibo(gate: str, sha: str,
                        recibos: Optional[Path]) -> Dict[str, Any]:
    if recibos is None:
        return {"control": gate, "estado": "no_ejecutado",
                "detalle": "SIN_DIRECTORIO_DE_RECIBOS", "evidencias": []}
    veredicto = leer_recibo(recibos / f"{gate}.recibo.json", sha)
    return {"control": gate,
            "estado": ESTADO_OK if veredicto["ok"] else "no_ejecutado",
            "detalle": veredicto["detalle"],
            "evidencias": [{k: v for k, v in veredicto.items() if k != "recibo"}]}


# ── CI vinculada al run exacto (QA-RC-02i) ──────────────────────────────────

def _gh_json(args: List[str], raiz: Path) -> Any:
    p = subprocess.run(["gh", *args], cwd=str(raiz), capture_output=True,
                       text=True, timeout=180)
    if p.returncode != 0:
        raise OSError((p.stderr or "gh no disponible").strip()[:200])
    return json.loads(p.stdout or "{}")


def jobs_de_run(run_id: int, raiz: Path = RAIZ,
                consultar: Optional[Callable[[int], Any]] = None) -> Dict[str, Any]:
    """Jobs del ENDPOINT DEL RUN, con paginacion y total_count.

    Sin identidad de run, sin total_count o con paginacion incompleta, la CI
    no se puede acreditar.
    """
    if consultar is not None:
        return consultar(run_id)
    datos = _gh_json(["api", "--paginate",
                       f"repos/devcicm/Vault-Obsidian-Architecture/actions/"
                       f"runs/{run_id}/jobs?per_page=100"], raiz)
    jobs = datos.get("jobs") if isinstance(datos, dict) else None
    if jobs is None and isinstance(datos, list):
        jobs = datos
    return {"jobs": jobs or [], "total_count": (datos or {}).get("total_count")
            if isinstance(datos, dict) else None}


def estado_ci(sha: str, consultar: Optional[Callable[[str], Any]] = None,
              raiz: Path = RAIZ, workflow_esperado: str = WORKFLOW_ESPERADO,
              consultar_jobs: Optional[Callable[[int], Any]] = None
              ) -> Dict[str, Any]:
    """Acredita la CI solo con: run del SHA y del workflow esperado,
    completed+success, y sus jobs REALE del endpoint de ese run cubriendo
    exactamente la matriz obligatoria."""
    def _runs(sh: str) -> Any:
        if consultar is not None:
            return consultar(sh)
        return _gh_json(["run", "list", "--commit", sh, "--limit", "10",
                          "--json",
                          "databaseId,status,conclusion,headSha,workflowName"],
                         raiz)

    try:
        runs = _runs(sha) or []
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
    ajenos = sorted({r["workflowName"] for r in propios
                      if r["workflowName"] != workflow_esperado})
    if ajenos:
        return {"conclusion": "no_verificable",
                "detalle": f"WORKFLOW_AJENO: {ajenos}"}
    exitosos = [r for r in propios
                if r.get("status") == "completed"
                and r.get("conclusion") == "success"]
    if not exitosos:
        estados = sorted({f"{r.get('status')}/{r.get('conclusion')}"
                          for r in propios})
        if any(r.get("status") in ("queued", "in_progress") for r in propios):
            return {"conclusion": "queued", "detalle": f"estados={estados}"}
        # Un run CONCLUIDO en rojo es un veredicto, no una espera. Medido el
        # 2026-10-26: la CI del candidato termino con 4 jobs rojos (las cuatro
        # columnas de macOS) y el evaluador de la política lo etiqueto como
        # «CI_PENDIENTE» porque solo miraba runs exitosos. Ahora se leen sus
        # jobs para decir cuales fallaron.
        fallidos = [r for r in propios
                    if r.get("status") == "completed"
                    and r.get("conclusion") != "success"]
        if fallidos:
            run = fallidos[-1]
            run_id = run.get("databaseId")
            nombres = []
            try:
                respuesta = (consultar_jobs(run_id) if consultar_jobs is not None
                              else jobs_de_run(run_id, raiz))
                jobs = (respuesta.get("jobs") if isinstance(respuesta, dict)
                        else respuesta) or []
                nombres = sorted(str(j.get("name")) for j in jobs
                                 if j.get("conclusion") not in (None, "success"))
            except (OSError, ValueError):
                pass
            return {"conclusion": "failure", "run_id": run_id,
                    "detalle": (f"estados={estados}"
                                + (f" jobs_en_rojo={nombres}" if nombres else ""))}
        return {"conclusion": "no_verificable", "detalle": f"estados={estados}"}

    run = exitosos[-1]
    run_id = run.get("databaseId")
    try:
        respuesta = (consultar_jobs(run_id) if consultar_jobs is not None
                     else jobs_de_run(run_id, raiz))
    except (OSError, ValueError) as exc:
        return {"conclusion": "no_verificable",
                "detalle": f"JOBS_NO_DISPONIBLES: {exc}"}
    jobs = respuesta.get("jobs") if isinstance(respuesta, dict) else respuesta
    total = respuesta.get("total_count") if isinstance(respuesta, dict) else None
    if not jobs:
        return {"conclusion": "no_verificable",
                "detalle": "SIN_JOBS: la CI no se puede acreditar sin jobs"}
    if total is not None and len(jobs) < int(total):
        return {"conclusion": "no_verificable",
                "detalle": f"PAGINACION_INCOMPLETA: {len(jobs)}/{total}"}

    # Cada job tiene que ser DEL RUN seleccionado, con conclusion real.
    mios = []
    ajenos_run = []
    sin_identidad = []
    for j in jobs:
        if j.get("run_id") != run_id:
            # Sin run_id == run seleccionado no se puede probar de quien es.
            (sin_identidad if j.get("run_id") is None
             else ajenos_run).append(j.get("name"))
            continue
        mios.append(j)
    if ajenos_run:
        return {"conclusion": "no_verificable", "run_id": run_id,
                "detalle": f"JOBS_DE_OTRO_RUN: {sorted(set(ajenos_run))[:5]}"}
    if sin_identidad:
        return {"conclusion": "no_verificable", "run_id": run_id,
                "detalle": f"JOBS_SIN_IDENTIDAD_DE_RUN: {sorted(set(sin_identidad))[:5]}"}
    nombres = [str(j.get("name", "")) for j in mios]
    duplicados = sorted({n for n in nombres if nombres.count(n) > 1})
    if duplicados:
        return {"conclusion": "no_verificable", "run_id": run_id,
                "detalle": f"JOBS_DUPLICADOS: {duplicados[:5]}"}
    faltan = [j for j in JOBS_OBLIGATORIOS if j not in nombres]
    sin_conclusion = [str(j.get("name")) for j in mios
                      if not j.get("conclusion")]
    fallidos = [str(j.get("name")) for j in mios
                 if j.get("conclusion") != "success"
                 or j.get("status") != "completed"]
    sobrantes = [n for n in nombres if n not in JOBS_OBLIGATORIOS]
    if faltan or sin_conclusion or fallidos or sobrantes:
        return {"conclusion": "no_verificable", "run_id": run_id,
                "detalle": (f"MATRIZ_INCOMPLETA faltan={faltan[:6]} "
                            f"sin_conclusion={sin_conclusion[:6]} "
                            f"fallidos={fallidos[:6]} sobrantes={sobrantes[:6]}")}
    return {"conclusion": "success", "run_id": run_id,
            "jobs": sorted(nombres), "total_count": total}


# ── Suite (JUnit) ────────────────────────────────────────────────────────────

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
    return {"estado": ESTADO_OK if ok else "fallido",
            "detalle": None if ok else "SUITE_CON_FALLOS",
            "tests": total, "failures": fallos, "errors": errores,
            "skipped": omitidos,
            "sha256": _sha256(Path(xml))}


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
    if dato.get("junit_sha256") != _sha256(Path(xml)):
        return {"ok": False, "detalle": "JUNIT_MANIPULADO_O_DISTINTO"}
    return {"ok": True, "detalle": None}


# ── Control de ejecucion (TD-0003) ───────────────────────────────────────────

def control_ejecucion(root: Optional[str] = None,
                      ejecutar: Callable[..., Any] = subprocess.run,
                      raiz: Path = RAIZ) -> Dict[str, Any]:
    comando = [sys.executable, str(raiz / "scripts" / "vault_norms.py"), "--audit"]
    if root:
        comando += ["--root", root]
    try:
        p = ejecutar(comando, cwd=str(raiz), capture_output=True, text=True,
                     encoding="utf-8", errors="replace", timeout=3600)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"completo": False, "degradados": [],
                "no_verificados": ["auditoria_no_ejecutada"], "detalle": str(exc)}
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
             consultar_ci=None,
             consultar_jobs: Optional[Callable[[int], Any]] = None,
             arbol: Optional[Dict[str, Any]] = None
             ) -> Dict[str, Any]:
    if not SHA_RE.match(sha or ""):
        return {"ok": False, "detalle": "SHA_INVALIDO", "estado": {},
                "politica": None}
    gates: Dict[str, str] = {}
    evidencias: Dict[str, Any] = {}
    for gate in GATES_EVIDENCIA:
        dato = estado_desde_recibo(gate, sha, recibos)
        gates[gate] = "PASS" if dato["estado"] == ESTADO_OK else "NOT_RUN"
        evidencias[gate] = {"sha": sha, "estado": dato["estado"],
                            "detalle": dato["detalle"]}

    control = control_ejecucion(root, ejecutar, raiz)
    limpio = bool(control.get("completo")) and not control.get("violaciones")
    gates["QG-02"] = ("PASS" if gates["QG-02"] == "PASS" and limpio else "BLOCKED")

    ci = estado_ci(sha, consultar_ci, raiz, consultar_jobs=consultar_jobs)
    gates["QG-07"] = "PASS"

    estado = {"sha_objetivo": sha, "gates": gates, "evidencias": evidencias,
              "control_ejecucion": control, "ci": ci,
              "arbol": arbol if arbol is not None
              else checkout_en_sha(sha, ejecutar, raiz)}
    from politica_qg import evaluar_politica

    veredicto = evaluar_politica(estado)
    # La identidad del checkout se verifica en el momento de ejecutar los
    # verificadores (que pueden escribir artefactos de runtime propios).
    if not (estado["arbol"] or {}).get("ok"):
        veredicto = {**veredicto, "liberable": False, "qg07": "BLOCKED",
                     "gates": {**veredicto["gates"], "QG-00": "BLOCKED"},
                     "motivos": {**veredicto.get("motivos", {}),
                                 "QG-00": [estado["arbol"].get("detalle")]}}
    return {"ok": True, "detalle": None, "estado": estado,
            "suite": estado_suite(suite_xml),
            "ci": ci, "politica": veredicto}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sha", required=True, help="SHA de 40 hex a dictaminar")
    ap.add_argument("--recibos", default=None,
                    help="Directorio (fuera del arbol) con los recibos")
    ap.add_argument("--ejecutar", action="store_true",
                    help="Ejecuta los verificadores de QG-00..QG-06 y emite "
                         "los recibos en --recibos")
    ap.add_argument("--json", dest="salida", default=None,
                    help="Fichero JSON con el informe final")
    ap.add_argument("--suite-xml", default=None)
    ap.add_argument("--e2e-json", default=None,
                    help="JSON del recorrido E2E (evidencia externa)")
    ap.add_argument("--root", default=None)
    ap.add_argument("--pip-audit-python", default=None)
    ap.add_argument("--paridad-venv", default=None)
    ap.add_argument("--paridad-runtime", default=None)
    args = ap.parse_args()

    if not SHA_RE.match(args.sha or ""):
        print(json.dumps({"ok": False, "error_code": "SHA_INVALIDO",
                          "message": "el SHA debe tener 40 hex"},
                         indent=2, ensure_ascii=False))
        return 2

    recibos = Path(args.recibos) if args.recibos else None
    identidad: Optional[Dict[str, Any]] = None
    if args.ejecutar:
        if recibos is None:
            print(json.dumps({"ok": False, "error_code": "FALTA_RECIBOS",
                              "message": "--ejecutar exige --recibos <dir>"},
                             indent=2, ensure_ascii=False))
            return 2
        contexto = {
            "pytest_junit": args.suite_xml,
            "recorrido_e2e": args.e2e_json,
            "pip_audit_python": args.pip_audit_python,
            "paridad_venv": args.paridad_venv,
            "paridad_runtime": args.paridad_runtime,
        }
        ejecucion = {}
        # La identidad del checkout se comprueba ANTES de ejecutar los
        # verificadores: algunos escriben artefactos de runtime propios.
        identidad = checkout_en_sha(args.sha)
        print(json.dumps({"checkout": identidad}, indent=2, ensure_ascii=False))
        for gate in GATES_EVIDENCIA:
            ejecucion[gate] = ejecutar_verificador(gate, args.sha, recibos,
                                                    contexto=contexto)
        print(json.dumps({"ok": all(e["ok"] for e in ejecucion.values()),
                          "ejecucion": ejecucion}, indent=2, ensure_ascii=False))

    resultado = colectar(args.sha, recibos=recibos,
                          suite_xml=Path(args.suite_xml) if args.suite_xml else None,
                          root=args.root,
                          arbol=identidad if args.ejecutar else None)
    texto = json.dumps(resultado, ensure_ascii=False, indent=2)
    if args.salida:
        Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
        Path(args.salida).write_text(texto + "\n", encoding="utf-8")
    print(texto)
    return 0 if (resultado.get("politica") or {}).get("liberable") else 1


if __name__ == "__main__":
    raise SystemExit(main())
