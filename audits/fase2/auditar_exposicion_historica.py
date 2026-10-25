#!/usr/bin/env python3
"""Auditoria de exposicion HISTORICA de las evidencias (H-L3-04).

QA tiene razon: sanear el HEAD no elimina lo ya publicado. Este instrumento
mira la HISTORIA COMPLETA (todos los commits alcanzables, todos los blobs) y
deliver un INVENTARIO de la exposicion por commit, fichero y CATEGORIA, **sin
reproducir el valor sensible**: ni la ruta, ni el nombre de cuenta, ni el
token. Para el valor se publica solo una huella (hash corto) que permite
cruzar dos hallazgos sin mostrarlos.

Categorias:
  ruta_local      - ruta absoluta con el directorio del usuario
  nombre_personal - nombre de cuenta que aparece fuera de una ruta
  forma_secreto   - patron con forma de credencial
  nul_utf16       - bytes NUL (UTF-16 embebido)

No reescribe historia, no borra refs y no hace push: solo informa.

Uso: python audits/fase2/auditar_exposicion_historica.py [--json SALIDA]
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

RUTA = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+([^\s\"'`)\]]+)")
UNIX_HOME = re.compile(r"/(?:home|Users)/([A-Za-z][^\s\"'`)\]]*)")
CREDENCIAL = re.compile(r"AKIA[0-9A-Z]{12,}|api_key\s*[:=]\s*[\"'][^\"']{8,}[\"']"
                        r"|Bearer\s+[A-Za-z0-9\-_\.]{16,}")
#: Nombres de cuenta que aparecen FUERA de una ruta (dato personal en prosa).
NOMBRE = re.compile(r"\b(Carlos\s+Ivan)\b")

PREFIJOS = ("audits/fase2/logs/", "audits/handoff/logs/", "audits/fase2/")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout


def _huella(texto: str) -> str:
    """Huella corta del valor sensible: permite correlacionar sin mostrarlo."""
    return hashlib.sha256(texto.encode("utf-8", "replace")).hexdigest()[:12]


def _categorias(datos: bytes) -> Tuple[Set[str], List[str]]:
    """Categorias detectadas y las huellas de los valores (no los valores)."""
    categorias: Set[str] = set()
    huellas: List[str] = []
    if b"\x00" in datos:
        categorias.add("nul_utf16")
    texto = datos.decode("utf-8", errors="replace")
    for patron in (RUTA, UNIX_HOME):
        for coincidencia in patron.finditer(texto):
            # Un marcador (hueco o nombre generico) NO es exposicion: es la
            # forma en que un documento DESCRIBE el patron sin publicar la
            # maquina (la que usa el propio verificador de saneamiento).
            segmento = coincidencia.group(1).strip().strip("/\\").lower()
            if segmento in ("...", "user", "usuario", "tu-usuario", "username",
                            "nombre", "<autor>", "<ruta-local>"):
                continue
            if segmento.startswith("<") and segmento.endswith(">"):
                continue
            categorias.add("ruta_local")
            huellas.append(_huella(coincidencia.group(0)))
    for coincidencia in CREDENCIAL.finditer(texto):
        categorias.add("forma_secreto")
        huellas.append(_huella(coincidencia.group(0)))
    for coincidencia in NOMBRE.finditer(texto):
        categorias.add("nombre_personal")
        huellas.append(_huella(coincidencia.group(0)))
    return categorias, sorted(set(huellas))


def commits_que_tocaron_evidencias() -> List[str]:
    """Todos los commits alcanzables que tocaron las evidencias."""
    salida = _git("log", "--all", "--full-history", "--format=%H",
                  "--", "audits/fase2/logs", "audits/handoff/logs")
    return [c for c in salida.split() if c]


def inventario() -> Dict[str, Any]:
    commits = commits_que_tocaron_evidencias()
    hallazgos: List[Dict[str, Any]] = []
    vistos: Set[Tuple[str, str]] = set()
    for commit in commits:
        arbol = _git("ls-tree", "-r", "--name-only", commit)
        for ruta in arbol.splitlines():
            if not ruta.startswith(PREFIJOS):
                continue
            if not ruta.endswith((".txt", ".md", ".json", ".yaml", ".yml", ".log")):
                continue
            clave = (commit, ruta)
            if clave in vistos:
                continue
            vistos.add(clave)
            datos = subprocess.run(["git", "show", f"{commit}:{ruta}"], cwd=str(ROOT),
                                   capture_output=True).stdout
            if not datos:
                continue
            categorias, huellas = _categorias(datos)
            if categorias:
                hallazgos.append({
                    "commit": commit,
                    "ruta": ruta,
                    "categorias": sorted(categorias),
                    "huellas_de_valores": huellas,
                })
    # Estado actual: lo que hay en HEAD.
    actuales: List[Dict[str, Any]] = []
    for ruta in sorted(str(p.relative_to(ROOT)).replace("\\", "/")
                       for p in (ROOT / "audits").rglob("*") if p.is_file()):
        if not ruta.endswith((".txt", ".md", ".json", ".yaml", ".yml", ".log")):
            continue
        categorias, huellas = _categorias((ROOT / ruta).read_bytes())
        if categorias:
            actuales.append({"ruta": ruta, "categorias": sorted(categorias),
                              "huellas_de_valores": huellas})
    return {
        "commits_examinados": len(commits),
        "commits_con_exposicion": sorted({h["commit"] for h in hallazgos}),
        "hallazgos": hallazgos,
        "estado_actual": {"ficheros_con_exposicion": actuales,
                          "conteo": len(actuales)},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", dest="salida", default="audits/fase2/logs/H-L3-04-exposicion-historica.json")
    args = ap.parse_args()
    datos = inventario()
    print(f"commits examinados: {datos['commits_examinados']}")
    print(f"commits con exposicion: {len(datos['commits_con_exposicion'])}")
    for commit in datos["commits_con_exposicion"]:
        print(f"  {commit}")
    categorias: Dict[str, int] = {}
    for hallazgo in datos["hallazgos"]:
        for categoria in hallazgo["categorias"]:
            categorias[categoria] = categorias.get(categoria, 0) + 1
    print(f"categorias: {categorias}")
    print(f"estado actual (HEAD) con exposicion: {datos['estado_actual']['conteo']}")
    for fichero in datos["estado_actual"]["ficheros_con_exposicion"]:
        print(f"  ACTUAL: {fichero['ruta']} -> {fichero['categorias']}")
    Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
    Path(args.salida).write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8")
    print(f"log: {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())