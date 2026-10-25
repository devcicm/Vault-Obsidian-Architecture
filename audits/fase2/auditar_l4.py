"""L4 — evidencia mecanica de la auditoria documental y de seguridad.

Comprobaciones REPRODUCIBLES (no afirmaciones): cada linea del log sale de
ejecutar algo contra el estado real del repo o del artefacto instalado.

Uso: python audits/fase2/auditar_l4.py [--salida F]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import vault_arch as arch  # noqa: E402
import vault_gate as gate  # noqa: E402


def _linea(titulo: str, valor: Any) -> str:
    return f"{titulo}: {valor}"


def documental() -> List[str]:
    lineas: List[str] = []
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    inicio = readme.index("## Quick Start")
    quick = readme[inicio:readme.index("\n## ", inicio + 10)]
    comandos = [c.strip() for c in quick.splitlines()
                if c.strip().startswith(("python ", "vault ", "pip "))]
    lineas.append(_linea("README quick start: comandos", len(comandos)))
    lineas.append(_linea("README quick start: usa el checkout (python scripts/)",
                         "python scripts/" in quick))
    lineas.append(_linea("README quick start: usa el producto instalado (vault ...)",
                         bool(re.search(r"\bvault (init|run|tools|--version|mcp-path)", quick))))
    lineas.append(_linea("README quick start: instalacion documentada",
                         re.findall(r"pip install[^\n]*", quick)[:2]))
    lineas.append(_linea("ARQUITECTURA.md igual al derivado arch.blueprint()",
                         (ROOT / "docs" / "ARQUITECTURA.md").read_text(encoding="utf-8").strip()
                         == arch.blueprint().strip()))
    lineas.append(_linea("PUERTAS: registro", len(gate.PUERTAS)))
    lineas.append(_linea("PUERTAS.md menciona 26",
                         "26" in (ROOT / "docs" / "PUERTAS.md").read_text(encoding="utf-8")))
    inst = (ROOT / "docs" / "INSTALACION-LIMPIA.md").read_text(encoding="utf-8")
    lineas.append(_linea("INSTALACION-LIMPIA.md cita la wheel", ".whl" in inst))
    for nombre in ("docs/product/prd-cli.md", "docs/product/prd-mcp.md",
                   "docs/product/runtime-contract.md", "docs/sdd/gaps.md"):
        ruta = ROOT / nombre
        lineas.append(_linea(f"{nombre}: existe", ruta.exists()))
    gaps = (ROOT / "docs" / "sdd" / "gaps.md").read_text(encoding="utf-8")
    lineas.append(_linea("gaps.md: fecha de la ultima actualizacion",
                         re.search(r"ltima actualizaci..n:\s*([0-9-]+)", gaps).group(1)
                         if re.search(r"ltima actualizaci..n:\s*([0-9-]+)", gaps) else "?"))
    lineas.append(_linea("gaps.md: hallazgos pendientes que declara",
                         re.search(r"Hallazgos pendientes \(([^)]+)\)", gaps).group(1)
                         if re.search(r"Hallazgos pendientes \(([^)]+)\)", gaps) else "?"))
    return lineas


def seguridad() -> List[str]:
    lineas: List[str] = []
    # Contencion de rutas: el helper y quien lo usa.
    ficheros = [p for p in ROOT.rglob("*.py")
                if "assert_within_vault" in p.read_text(encoding="utf-8", errors="ignore")]
    lineas.append(_linea("contencion: ficheros que usan assert_within_vault", len(ficheros)))
    # Superficie de operaciones: nada de gobernanza fuera del repo.
    ops = sorted(p.stem for p in (ROOT / "vault_toolkit" / "operations").glob("*.py"))
    gob = [o for o in ops if o.startswith(("vault_norms", "vault_arch", "vault_gate",
                                           "vault_blame", "vault_doc", "vault_noop"))]
    lineas.append(_linea("superficie de operaciones", len(ops)))
    lineas.append(_linea("superficie: tools de gobernanza expuestas", gob))
    # Catalogo MCP.
    cat = json.loads((ROOT / "mcp" / "nodejs" / "tools-catalog.json").read_text(encoding="utf-8"))
    tools = cat["tools"]
    exp = {n: t for n, t in tools.items() if t.get("exposed_via_mcp")}
    lineas.append(_linea("catalogo: tools totales", len(tools)))
    lineas.append(_linea("catalogo: expuestas por MCP", len(exp)))
    lineas.append(_linea("catalogo: expuestas con side_effects declarados",
                         len([n for n, t in exp.items() if t.get("side_effects")])))
    lineas.append(_linea("catalogo: expuestas sin side_effects",
                         len([n for n, t in exp.items() if not t.get("side_effects")])))
    # Operacion destructiva sin copia previa (gap historico D3).
    limpio = ""
    for ruta in list((ROOT / "vault").rglob("*.py")) + list((ROOT / "scripts").glob("*.py")):
        texto = ruta.read_text(encoding="utf-8", errors="ignore")
        if "if clean and" in texto and "rmtree" in texto:
            i = texto.index("if clean and")
            limpio = f"{ruta.relative_to(ROOT).as_posix()}: " + \
                     " ".join(texto[i:i + 320].split())[:260]
            break
    lineas.append(_linea("operacion destructiva sin copia (gap D3)", limpio or "no localizada"))
    # Duplicacion (gaps K3, K4).
    def _count(patron: str) -> int:
        total = 0
        for ruta in list((ROOT / "scripts").glob("*.py")) + list((ROOT / "vault").rglob("*.py")):
            total += len(re.findall(patron, ruta.read_text(encoding="utf-8", errors="ignore")))
        return total
    lineas.append(_linea("implementaciones de slugify (gap K3)", _count(r"def _?slugify")))
    lineas.append(_linea("implementaciones de utcnow (gap K4)", _count(r"def _?utcnow")))
    # Dependencias declaradas en la wheel construida.
    dist = Path(os.environ.get("L3_DIST", "")) if os.environ.get("L3_DIST") else None
    if dist and dist.is_dir():
        whls = sorted(dist.glob("*.whl"))
        if whls:
            with zipfile.ZipFile(whls[0]) as z:
                meta = [n for n in z.namelist() if n.endswith("METADATA")][0]
                texto = z.read(meta).decode("utf-8")
                for linea_meta in texto.splitlines():
                    if linea_meta.startswith(("Requires-Dist", "Requires-Python")):
                        lineas.append(_linea("wheel metadatos", linea_meta))
            lineas.append(_linea("wheel: miembros",
                                 len(zipfile.ZipFile(whls[0]).infolist())))
    return lineas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--salida", default="audits/fase2/logs/L4-documental.txt")
    args = ap.parse_args()
    lineas = ["L4 — evidencia mecanica: documental y seguridad", "=" * 46, "",
              "== DOCUMENTAL (L4-A)"] + documental() + ["", "== SEGURIDAD (L4-B)"] + seguridad()
    Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
    Path(args.salida).write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))
    print(f"\nlog: {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())