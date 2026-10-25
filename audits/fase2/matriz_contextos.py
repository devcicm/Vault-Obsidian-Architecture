#!/usr/bin/env python3
"""Matriz arquitectónica de fase 2 (L1) — derivada del registro, no escrita a mano.

Emite `audits/fase2/matriz-arquitectonica.md` desde `vault_arch.CONTEXTS` (la
verdad) mas el informe de reconciliación de Archify (evidencia auxiliar). Si el
registro cambia, la matriz cambia con él: nadie la reescribe a mano.

Uso: python audits/fase2/matriz_contextos.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import vault_arch as arch  # noqa: E402

DESTINO = ROOT / "audits" / "fase2" / "matriz-arquitectonica.md"
RECON = ROOT / "audits" / "fase2" / "logs" / "L1-reconciliacion-archify.json"


def _sha() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


def _dueño_de_un_contexto(ctx: str) -> str:
    """El dueño de un contexto: quien tiene sus puertos publicados."""
    for par, ficha in arch.PRESUPUESTO_DE_CRUCES.items():
        if ficha.get("dueno") == ctx:
            return str(ficha.get("dueno"))
    return "—"


def _tabla(headers: List[str], filas: List[List[str]]) -> str:
    salida = ["| " + " | ".join(headers) + " |",
              "|" + "|".join("---" for _ in headers) + "|"]
    for fila in filas:
        salida.append("| " + " | ".join(fila) + " |")
    return "\n".join(salida)


def main() -> int:
    recon: Dict[str, Any] = json.loads(RECON.read_text(encoding="utf-8")) if RECON.is_file() else {}

    lineas: List[str] = []
    lineas.append("# Matriz arquitectónica — fase 2 (L1)")
    lineas.append("")
    lineas.append(f"**Derivado de:** `vault_arch.CONTEXTS` y `vault_arch.PRESUPUESTO_DE_CRUCES` "
                  f"(el registro vivo), contrastado con el snapshot de Archify.")
    lineas.append(f"**SHA del estado:** `{_sha()}` · **generado por:** "
                  f"`python audits/fase2/matriz_contextos.py`")
    lineas.append("")
    lineas.append("> No se edita a mano: si el registro cambia, este documento se regenera.")
    lineas.append("")

    # ── 1. Los diez contextos ────────────────────────────────────────────────
    lineas.append("## 1. Los diez contextos")
    lineas.append("")
    filas = []
    for nombre, datos in arch.CONTEXTS.items():
        puertos = datos.get("puertos", {})
        filas.append([
            f"`{nombre}`",
            str(datos.get("titulo", "")),
            str(len(puertos)),
            str(len(datos.get("modulos", []))),
            str(len(datos.get("prohibe", []))),
            ", ".join(f"`{p}`" for p in sorted(puertos)) or "—",
        ])
    lineas.append(_tabla(["Contexto", "Título", "Puertos", "Módulos", "Prohíbe",
                           "Puertos publicados"], filas))
    lineas.append("")
    lineas.append(f"**Totales:** {len(arch.CONTEXTS)} contextos · "
                  f"{sum(len(d['puertos']) for d in arch.CONTEXTS.values())} puertos · "
                  f"{len(arch.PRESUPUESTO_DE_CRUCES)} pares de cruce presupuestados.")
    lineas.append("")

    # ── 2. El presupuesto de cruces, con su ficha ──────────────────────────
    lineas.append("## 2. Presupuesto de cruces (23 pares)")
    lineas.append("")
    lineas.append("Cada par tiene un dueño y una revisión; el objetivo `en_estudio` es el "
                  "estado declarado: son cruces **autorizados y vigilados**, no defectos.")
    lineas.append("")
    filas = []
    for (origen, destino), ficha in sorted(arch.PRESUPUESTO_DE_CRUCES.items()):
        filas.append([
            f"`{origen}` → `{destino}`",
            str(ficha.get("objetivo", "")),
            str(ficha.get("dueno", "")),
            str(ficha.get("revisado", "")),
            str(ficha.get("cadencia_dias", "")),
            str(ficha.get("por_que", "")).replace("|", "\\|")[:120],
        ])
    lineas.append(_tabla(["Cruce", "Objetivo", "Dueño", "Revisado", "Cadencia (días)",
                           "Por qué"], filas))
    lineas.append("")

    # ── 3. Reconciliación con el snapshot de Archify ────────────────────────
    lineas.append("## 3. Reconciliación con el snapshot de Archify")
    lineas.append("")
    if not recon:
        lineas.append("_Sin informe de reconciliación: ejecutar "
                      "`python audits/fase2/reconciliar_archify.py --json "
                      "audits/fase2/logs/L1-reconciliacion-archify.json`._")
        lineas.append("")
    else:
        pares = recon.get("pares_de_contexto", {})
        deps = recon.get("dependencias", {})
        lineas.append(f"**Pares de contexto:** snapshot {pares.get('pares_snapshot_n')} · "
                      f"registro {pares.get('pares_registro_n')} · "
                      f"coincidentes **{pares.get('coincidentes')}** · "
                      f"solo en snapshot {len(pares.get('solo_en_snapshot', []))} · "
                      f"solo en registro {len(pares.get('solo_en_registro', []))}.")
        lineas.append("")
        lineas.append(f"**Dependencias (nivel de fichero):** {deps.get('dependencias_snapshot_n')} "
                      f"dependencias colapsan a {deps.get('pares_snapshot_n')} pares de contexto; "
                      f"**{deps.get('pares_vigentes')}** de esos pares siguen vigentes "
                      f"(los vivos son {deps.get('pares_contexto_vivos_n')}).")
        lineas.append("")
        divergentes = [f for f in pares.get("fichas", []) if f.get("estado") != "VIGENTE"]
        lineas.append(f"**Fichas de los pares:** {len(pares.get('fichas', []))} comparadas, "
                      f"{len(divergentes)} con diferencias de metadatos.")
        lineas.append("")
        lineas.append("**Accesos fuera de puerto del snapshot:**")
        lineas.append("")
        lineas.append(_tabla(["Acceso", "Estado", "Nota"],
                              [[f"`{f['clave']}`", f["estado"], f["nota"]]
                               for f in recon.get("off_port", [])]))
        lineas.append("")
        anclas = recon.get("anclas", {})
        lineas.append(f"**Anclas del puente:** snapshot {anclas.get('anclas_snapshot')} · "
                      f"registro {anclas.get('anclas_registro')} · "
                      f"coinciden: **{anclas.get('coinciden')}** · "
                      f"motivos idénticos: {anclas.get('motivos_iguales')}")
        lineas.append("")
        lineas.append("**Contextos:**")
        lineas.append("")
        lineas.append(_tabla(["Contexto", "Estado", "Puertos (snapshot→registro)",
                               "Módulos (snapshot→registro)"],
                              [[f"`{f['contexto']}`", f["estado"],
                                f"{f.get('puertos_snapshot_n')}→{f.get('puertos_registro_n')}",
                                f"{f.get('modulos_snapshot_n')}→{f.get('modulos_registro_n')}"]
                               for f in recon.get("contextos", [])]))
        lineas.append("")

    # ── 4. Invariantes ──────────────────────────────────────────────────────
    lineas.append("## 4. Invariantes del registro en este SHA")
    lineas.append("")
    inv = recon.get("invariantes", {})
    lineas.append(_tabla(["Invariante", "Valor"],
                          [[k, str(v)] for k, v in inv.items()]))
    lineas.append("")

    DESTINO.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"matriz escrita: {DESTINO} ({DESTINO.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())