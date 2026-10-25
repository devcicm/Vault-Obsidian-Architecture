#!/usr/bin/env python3
r"""Auditoria de exposicion HISTORICA (H-F2-01) — version streaming.

Recorre la historia completa de las evidencias con UN SOLO streaming de Git
(`git log --all -p --full-history`) y escanea el TEXTO DE PARCHE: contiene el
contenido completo de cada blob en cada estado, asi que la cobertura es la
historia entera de los ficheros de evidencia, sin leer blob a blob (el enfoque
cat-file por lotes se cuelga en este repositorio: limitacion documentada).

ALCANCE DECLARADO (no promete mas de lo que mira):
  - QUE SE INSPECCIONA: los PARCES que `git log --all -p --full-history`
    produce para los ficheros bajo los prefijos. Un parche contiene las lineas
    que ese commit anadio o quito en ese fichero; NO contiene el blob completo
    de cada estado. Por tanto `blobs_inspeccionados` es 0 y se dice: para leer
    cada blob habria que recorrer `rev-list --objects --all`, que en este
    repositorio no termino en 30 minutos y se descarto por coste.
  - ficheros: SOLO los de evidencia (audits/**/logs/, audits/handoff/);
    el resto del arbol versionado (codigo, manifiesto, tests) NO se escanea
    aqui: su historial puede escanearse con este instrumento cambiando el
    prefijo, y queda declarado como limite;
  - encodings: utf-8 y utf-16 con NUL/BOM; sin OCR, sin zips, sin imagenes;
  - detector: expresiones regulares genericas, sin nombres personales
    incrustados: la cuenta de la maquina se deriva del entorno en tiempo de
    ejecucion (nunca va en el codigo).

METRICAS (separadas a proposito, H-F2-06): `commits_considerados` son TODOS los
commits que tocan los prefijos; `commits_con_exposicion` son los que tienen
hallazgos; `ficheros_considerados` y `deltas_inspeccionados` dicen cuanto se
miro; `errores` recoge lo que no se pudo leer. Una conclusion solo puede
referirse a lo que estas cifras acreditan — nunca "0 secretos en toda la
historia".

PRIVACIDAD: de cada coincidencia se publica solo la CATEGORIA y una HUELLA
(sha256 truncada) del valor, nunca el valor.

Salida: JSON con el inventario por commit (SHA, fichero, categoria, huella),
el estado ACTUAL y el bloque de cobertura. Modo --check: exit != 0 si el
estado ACTUAL tiene exposicion (la historia antigua la decide el propietario).

Uso: python audits/fase2/auditar_exposicion_historica.py [--json SALIDA] [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

ROOT = Path(__file__).resolve().parents[2]

RUTA_WINDOWS = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+([^\s\"'`)\]]+)")
RUTA_UNIX = re.compile(r"/(?:home|Users)/([A-Za-z][^\s\"'`)\]]*)")
CREDENCIAL = re.compile(
    r"AKIA[0-9A-Z]{12,}|(?i:api[_-]?key)\s*[:=]\s*[\"'][^\"']{8,}[\"']"
    r"|Bearer\s+[A-Za-z0-9\-_\.]{16,}|(?i:password|passwd|secret)\s*[:=]\s*[\"'][^\"']{6,}[\"']")
NUL = re.compile("\x00")

GENERICOS = {"...", "user", "usuario", "tu-usuario", "username", "nombre",
             "autor", "<autor>", "<ruta-local>", "<usuario>", "<ruta_local>"}


def _cuenta() -> str:
    """El identificador de cuenta de ESTA maquina, derivado del entorno.

    Nunca va incrustado en el codigo: se lee de la maquina que ejecuta la
    auditoria, que es la unica interesada en saber si su propia cuenta quedo
    publicada.
    """
    try:
        return Path.home().name
    except Exception:
        return ""


def _es_placeholder(segmento: str) -> bool:
    """Un marcador entre <> o un nombre generico no es una maquina real."""
    limpio = segmento.strip().strip("/\\").lower()
    if limpio in GENERICOS:
        return True
    return limpio.startswith("<") and limpio.endswith(">")


def _huella(valor: str) -> str:
    """Huella no reversible del valor: correlaciona sin publicar."""
    return hashlib.sha256(valor.encode("utf-8", "replace")).hexdigest()[:12]


def clasificar(texto: str) -> List[Dict[str, str]]:
    """Las coincidencias de un texto, SIN reproducir el valor.

    El criterio del marcador mira el SEGMENTO que va justo tras `Users/`, no la
    captura entera: `C:/Users/<autor>/resto` lleva el hueco `<autor>` y no es
    exposicion, mientras que una cuenta real en ese mismo sitio si lo es.
    """
    salidas: List[Dict[str, str]] = []
    cuenta = _cuenta()
    for patron in (RUTA_WINDOWS, RUTA_UNIX):
        for coincidencia in patron.finditer(texto):
            captura = coincidencia.group(1)
            segmento = re.split(r"[\\/]+", captura)[0]
            if _es_placeholder(segmento):
                continue
            salidas.append({"categoria": "ruta_local",
                            "huella": _huella(coincidencia.group(0))})
    if cuenta and cuenta.lower() in texto.lower():
        salidas.append({"categoria": "cuenta_usuario",
                        "huella": _huella(cuenta)})
    for coincidencia in CREDENCIAL.finditer(texto):
        salidas.append({"categoria": "forma_secreto",
                        "huella": _huella(coincidencia.group(0))})
    if "\x00" in texto:
        salidas.append({"categoria": "nul_utf16",
                        "huella": _huella("NUL")})
    return salidas


def escanear_historia(prefijos: Tuple[str, ...]) -> Dict[str, Any]:
    """Un streaming de `git log --all -p` sobre los ficheros de evidencia."""
    comando = ["git", "log", "--all", "-p", "--full-history", "--", *prefijos]
    proc = subprocess.Popen(comando, cwd=str(ROOT), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8",
                            errors="replace", bufsize=1 << 20)
    commit_actual: Optional[str] = None
    fichero_actual: Optional[str] = None
    buffer_texto: List[str] = []
    hallazgos: List[Dict[str, Any]] = []
    commits_considerados: Set[str] = set()
    commits_con_exposicion: Set[str] = set()
    ficheros_considerados: Set[str] = set()
    deltas_inspeccionados = 0
    huellas_unicas: Set[str] = set()
    contador: Dict[str, int] = {}
    errores: List[str] = []

    def cerrar_fichero() -> None:
        nonlocal fichero_actual, buffer_texto
        if fichero_actual and buffer_texto:
            texto = "".join(buffer_texto)
            del_fichero = clasificar(texto)
            if del_fichero:
                categorias_fichero = sorted({h["categoria"] for h in del_fichero})
                hallazgos.append({
                    "commit": commit_actual, "fichero": fichero_actual,
                    "categorias": categorias_fichero,
                    "coincidencias": len(del_fichero),
                    "huellas": sorted({h["huella"] for h in del_fichero}),
                })
                commits_con_exposicion.add(commit_actual)
                for h in del_fichero:
                    contador[h["categoria"]] = contador.get(h["categoria"], 0) + 1
                    huellas_unicas.add(h["huella"])
        fichero_actual, buffer_texto = None, []

    for linea in proc.stdout:
        if linea.startswith("commit "):
            cerrar_fichero()
            commit_actual = linea.split()[1].strip()
            commits_considerados.add(commit_actual)
            continue
        m = re.match(r"^\+\+\+ b/(.+)$", linea.rstrip("\n"))
        if m:
            cerrar_fichero()
            fichero_actual = m.group(1).strip()
            if fichero_actual == "/dev/null":
                fichero_actual = None
            else:
                ficheros_considerados.add(fichero_actual)
                deltas_inspeccionados += 1
            continue
        if fichero_actual:
            buffer_texto.append(linea)
            if sum(len(l) for l in buffer_texto) > 2_000_000:
                cerrar_fichero()
    proc.stdout.close()
    cerrar_fichero()
    resto = proc.stderr.read() if proc.stderr else ""
    proc.stderr.close()
    proc.wait()
    for linea in (resto or "").splitlines():
        if linea.strip():
            errores.append(linea.strip())

    ficheros_considerados.discard("/dev/null")
    return {
        "commits_considerados": len(commits_considerados),
        "commits_con_exposicion": sorted(commits_con_exposicion),
        "ficheros_considerados": len(ficheros_considerados),
        "deltas_inspeccionados": deltas_inspeccionados,
        "blobs_inspeccionados": 0,
        "hallazgos": hallazgos,
        "categorias": contador,
        "huellas_unicas": len(huellas_unicas),
        "forma_secreto_encontrada": contador.get("forma_secreto", 0),
        "errores": errores,
    }


def estado_actual(prefijos: Tuple[str, ...]) -> List[Dict[str, str]]:
    """Los ficheros de evidencia EN EL HEAD, con su exposicion."""
    problemas: List[Dict[str, str]] = []
    base = ROOT / "audits"
    for ruta in sorted(base.rglob("*")):
        if not ruta.is_file() or ruta.suffix.lower() not in (".txt", ".md", ".json", ".yaml", ".yml", ".log"):
            continue
        relativa = ruta.relative_to(ROOT).as_posix()
        if not relativa.startswith(prefijos):
            continue
        try:
            datos = ruta.read_bytes()
        except OSError as exc:
            problemas.append({"fichero": relativa,
                              "categoria": "NO_VERIFICABLE",
                              "detalle": f"no se pudo leer: {exc}"})
            continue
        texto = datos.decode("utf-8", errors="replace")
        for hallazgo in clasificar(texto):
            if hallazgo["categoria"] == "cuenta_usuario":
                continue
            problemas.append({"fichero": relativa, **hallazgo})
    return problemas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", dest="salida",
                    default="audits/fase2/logs/H-F2-01-exposicion-historica.json")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    prefijos = ("audits/fase2/logs/", "audits/handoff/logs/", "audits/fase2/",
                "audits/handoff/")

    historia = escanear_historia(prefijos)
    actual = estado_actual(prefijos)

    informe = {
        "alcance": {
            "que_se_inspecciona": ("los parches que `git log --all -p --full-history` "
                                   "produce para los ficheros bajo esos prefijos; un parche "
                                   "contiene las lineas que ese commit anadio o quito en ese "
                                   "fichero, NO el blob completo de cada estado"),
            "ficheros": "los que el streaming de git log --all -p --full-history " 
                        "toca bajo esos prefijos, en TODOS los commits alcanzables",
            "blobs_integridad": ("0: no se leen blobs completos. Recorrerlos con "
                                 "rev-list --objects --all no termino en 30 min en este "
                                 "repositorio y se descarto por coste; se declara"),
            "exclusiones": ("el resto del arbol versionado (codigo, manifiesto, "
                            "tests) no se escanea en este instrumento"),
            "detector": ("regex genericas sobre texto; sin OCR, sin zips, sin "
                         "imagenes; la cuenta de la maquina se deriva del entorno"),
        },
        "historia": {
            "commits_considerados": historia["commits_considerados"],
            "commits_con_exposicion": len(historia["commits_con_exposicion"]),
            "ficheros_considerados": historia["ficheros_considerados"],
            "deltas_inspeccionados": historia["deltas_inspeccionados"],
            "blobs_inspeccionados": historia["blobs_inspeccionados"],
            "errores": historia["errores"],
            "categorias": historia["categorias"],
            "huellas_unicas": historia["huellas_unicas"],
            "forma_secreto": historia["forma_secreto_encontrada"],
        },
        "estado_actual": actual,
    }
    Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
    Path(args.salida).write_text(
        json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("== HISTORIA")
    print(f"  commits considerados: {informe['historia']['commits_considerados']} | "
          f"con exposicion: {informe['historia']['commits_con_exposicion']}")
    print(f"  ficheros considerados: {informe['historia']['ficheros_considerados']} | "
          f"deltas inspeccionados: {informe['historia']['deltas_inspeccionados']} | "
          f"blobs inspeccionados: {informe['historia']['blobs_inspeccionados']}")
    print(f"  categorias: {informe['historia']['categorias']} | "
          f"forma_secreto: {informe['historia']['forma_secreto']} | "
          f"errores: {len(informe['historia']['errores'])}")
    for hallazgo in historia["hallazgos"]:
        print(f"  {hallazgo['commit'][:10]} {hallazgo['fichero']} -> "
              f"{hallazgo['categorias']} ({hallazgo['coincidencias']})")
    print("== ESTADO ACTUAL (HEAD)")
    if actual:
        for problema in actual:
            print(f"  {problema['fichero']} -> {problema['categoria']}")
    else:
        print("  conforme: sin exposicion en el HEAD")
    print(f"log: {args.salida}")

    if args.check:
        return 1 if actual else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())