#!/usr/bin/env python3
"""Bench: what historic notes cost `vault_context_pack` (S5, bigo-inmutabilidad).

A scratch vault (product `vault_init`) gets a fixed set of current notes and a
growing number of historic ones, all relevant to the same query: ADRs replaced
with `superseded_by:`, notes whose status is archived/deprecated/obsolete/
revoked, archived raw sources in `10_Migrated/fuentes/` and notes held in
`20_Quarantine/`. For each size the pack runs in this interpreter
(`vault.ejecutor.ejecutar`, no subprocess per call) and the bench records the
median wall time, the candidates the rerank scored, the tokens used and how
many included items are historic.

No network, no repository writes: every vault lives in a temporary directory
that is removed at the end (`--conservar` keeps it).

Usage:
    python audits/rendimiento/banco_contexto.py
    python audits/rendimiento/banco_contexto.py --historicos 0,100,1000 --repeticiones 5
    python audits/rendimiento/banco_contexto.py --pack-arg=--incluir-historico
    python audits/rendimiento/banco_contexto.py --salida resultado.json
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / "scripts"
for _ruta in (str(SCRIPTS), str(RAIZ)):
    if _ruta not in sys.path:
        sys.path.insert(0, _ruta)

import yaml  # noqa: E402

CONSULTA = "transporte del bus de eventos"
PRESUPUESTO = 4000
VIGENTES = 6

#: Historic classes, written round-robin: (class, folder, extra frontmatter).
CLASES = (
    ("superseded", "03_Decisions", {"status": "approved"}),
    ("archived", "07_Knowledge", {"status": "archived"}),
    ("deprecated", "05_Patterns", {"status": "deprecated"}),
    ("obsolete", "07_Knowledge", {"status": "obsolete"}),
    ("revoked", "07_Knowledge", {"status": "revoked"}),
    ("archived_source", "10_Migrated/fuentes", {"status": "archived", "type": "migrated"}),
    ("quarantine", "20_Quarantine", {"status": "draft"}),
)


def _cuerpo(etiqueta: str) -> str:
    parrafos = [f"# Transporte del bus de eventos ({etiqueta})"]
    parrafos += [f"El transporte del bus de eventos usa la cola {i} para entregar "
                 f"eventos entre servicios; esta nota ({etiqueta}) fija el formato."
                 for i in range(5)]
    return "\n\n".join(parrafos) + "\n"


def _escribir(raiz: Path, rel: str, fm: Dict[str, Any], cuerpo: str) -> None:
    ruta = raiz / rel
    ruta.parent.mkdir(parents=True, exist_ok=True)
    cabecera = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)
    ruta.write_bytes(f"---\n{cabecera}---\n\n{cuerpo}".encode("utf-8"))


def _correr(raiz: Path, script: str, *argv: str) -> None:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_AGENT="banco",
               PYTHONPATH=os.pathsep.join([str(RAIZ), str(SCRIPTS)]))
    p = subprocess.run([sys.executable, str(SCRIPTS / script), *argv], env=env,
                       cwd=str(RAIZ), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=900)
    if p.returncode != 0:
        raise RuntimeError(f"{script} salió con {p.returncode}: {p.stdout[-400:]} {p.stderr[-400:]}")


def construir_vault(raiz: Path, historicos: int) -> Dict[str, List[str]]:
    """A fresh vault with `VIGENTES` current notes and `historicos` historic ones."""
    raiz.mkdir(parents=True)
    _correr(raiz, "vault_init.py")
    vigentes = []
    for k in range(VIGENTES):
        rel = f"03_Decisions/adr-01{k:02d}-transporte-bus-eventos.md"
        _escribir(raiz, rel, {"title": f"Transporte del bus de eventos v{k}",
                              "type": "adr", "status": "approved",
                              "updatedAt": "2026-11-01"}, _cuerpo(f"vigente {k}"))
        vigentes.append(rel)
    historicas = []
    for i in range(historicos):
        clase, carpeta, extra = CLASES[i % len(CLASES)]
        rel = f"{carpeta}/h{i:04d}-{clase}-transporte-bus-eventos.md"
        fm = {"title": f"Transporte del bus de eventos h{i}", **extra,
              "updatedAt": "2026-10-01"}
        if clase == "superseded":
            fm["superseded_by"] = f"[[{Path(vigentes[i % VIGENTES]).stem}]]"
        _escribir(raiz, rel, fm, _cuerpo(f"{clase} {i}"))
        historicas.append(rel)
    _correr(raiz, "vault_reindex.py")
    _correr(raiz, "vault_graph.py")
    return {"vigentes": vigentes, "historicas": historicas}


def medir(raiz: Path, manifiesto: Dict[str, List[str]], repeticiones: int,
          pack_args: List[str]) -> Dict[str, Any]:
    from vault.ejecutor import ejecutar

    historicas = set(manifiesto["historicas"])
    vigentes = set(manifiesto["vigentes"])
    argv = ["vault_context_pack.py", "--query", CONSULTA, "--budget", str(PRESUPUESTO),
            *pack_args]
    tiempos: List[float] = []
    envelope: Dict[str, Any] = {}
    for _ in range(repeticiones):
        inicio = time.perf_counter()
        corrida = ejecutar(None, argv, raiz=raiz, agente="banco")
        tiempos.append((time.perf_counter() - inicio) * 1000.0)
        envelope = corrida.envelope or {}
        if not envelope.get("ok"):
            raise RuntimeError(f"vault_context_pack falló: {corrida.texto[-400:]}")
    incluidas = [i["path"] for i in envelope.get("included", [])]
    fila = {
        "historicos": len(historicas),
        "wall_ms_mediana": round(statistics.median(tiempos), 1),
        "candidatos_puntuados": envelope.get("candidates_considered"),
        "tokens_usados": envelope.get("tokens", {}).get("used"),
        "incluidas": len(incluidas),
        "incluidas_historicas": sum(1 for p in incluidas if p in historicas),
        "incluidas_vigentes": sum(1 for p in incluidas if p in vigentes),
    }
    if "history_excluded" in envelope:
        fila["historia_excluida"] = envelope["history_excluded"]
    return fila


def tabla(filas: List[Dict[str, Any]]) -> str:
    columnas = ["historicos", "wall_ms_mediana", "candidatos_puntuados", "tokens_usados",
                "incluidas", "incluidas_historicas", "incluidas_vigentes"]
    lineas = ["| " + " | ".join(columnas) + " |", "|" + "---|" * len(columnas)]
    lineas += ["| " + " | ".join(str(f.get(c)) for c in columnas) + " |" for f in filas]
    return "\n".join(lineas)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--historicos", default="0,100,1000",
                        help="Tamaños de la historia, separados por comas")
    parser.add_argument("--repeticiones", type=int, default=5)
    parser.add_argument("--pack-arg", action="append", default=[], dest="pack_args",
                        help="Argumento extra para vault_context_pack (repetible)")
    parser.add_argument("--salida", default=None, help="Escribe el JSON aquí además de stdout")
    parser.add_argument("--conservar", action="store_true",
                        help="No borra los vaults temporales")
    args = parser.parse_args()

    base = Path(tempfile.mkdtemp(prefix="banco_contexto_"))
    filas = []
    try:
        for n in [int(x) for x in args.historicos.split(",") if x.strip()]:
            raiz = base / f"vault_{n}"
            manifiesto = construir_vault(raiz, n)
            filas.append(medir(raiz, manifiesto, args.repeticiones, args.pack_args))
    finally:
        if not args.conservar:
            shutil.rmtree(base, ignore_errors=True)
    resultado = {"consulta": CONSULTA, "presupuesto": PRESUPUESTO, "vigentes": VIGENTES,
                 "repeticiones": args.repeticiones, "pack_args": args.pack_args,
                 "filas": filas}
    texto = json.dumps(resultado, indent=2, ensure_ascii=False)
    if args.salida:
        Path(args.salida).write_text(texto + "\n", encoding="utf-8")
    print(texto)
    print()
    print(tabla(filas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
