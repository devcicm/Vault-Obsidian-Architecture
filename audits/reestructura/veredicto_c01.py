#!/usr/bin/env python3
"""veredicto de los pares `en_estudio` (C-01).

Para cada par que el presupuesto declara «en estudio», mira el cruce real y
qué símbolos consume del destino, y decide:

- **recurso** — el cruce lee un dato que ya tiene dueño (catálogo, constante,
  vocabulario). Es barato y estable: se puede declarar permanente.
- **motor** — el cruce llama a una función que hace trabajo (escribe, escanea,
  genera). Eso es acoplamiento y hay que invertirlo con un puerto.

Uso:
    python audits/reestructura/veredicto_c01.py [--markdown]
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import vault_arch as arch  # noqa: E402

#: Símbolos que se consideran datos, no motor. Si el cruce solo importa estos,
#: es un recurso: leerlo no ejecuta nada.
PISTAS_DE_RECURSO = (
    "ORDERED_SECTIONS", "MACHINERY_FOLDERS", "CONTEXTS", "STATUS_VOCAB",
    "NORMA", "CATALOG", "REGISTRY", "CATALOGO", "SECCIONES", "VOCABULARIO",
    "SECTION_DOCUMENTACION", "EJES_DOCUMENTACION", "MODOS_DE_VERSION",
    "_catalogo", "catalogo", "registro", "constante",
)


def _simbolos_importados(ruta: Path, modulo_destino: str) -> List[str]:
    """Los nombres que `ruta` importa de `modulo_destino` (o de su paquete)."""
    try:
        arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return []
    # El paquete del fichero, para resolver los imports relativos.
    partes = ruta.relative_to(REPO).with_suffix("").parts
    paquete = ".".join(partes[:-1]) if len(partes) > 1 else ""

    def absoluto(nodo: ast.ImportFrom) -> str:
        if nodo.level:
            base = paquete.split(".")[: len(paquete.split(".")) - (nodo.level - 1)]
            return ".".join(base + ([nodo.module] if nodo.module else []))
        return nodo.module or ""

    nombres: List[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                if (alias.name == modulo_destino
                        or alias.name.startswith(modulo_destino + ".")
                        or modulo_destino.startswith(alias.name + ".")):
                    nombres.append(alias.asname or alias.name.split(".")[-1])
            continue
        if not isinstance(nodo, ast.ImportFrom):
            continue
        modulo = absoluto(nodo)
        if not modulo:
            continue
        if not (modulo == modulo_destino or modulo.startswith(modulo_destino + ".")
                or modulo_destino.startswith(modulo + ".")):
            continue
        nombres.extend(a.name for a in nodo.names)
    return sorted(set(nombres))


def _clasificar(simbolos: List[str]) -> str:
    if not simbolos:
        return "desconocido"
    if all(any(p in s for p in PISTAS_DE_RECURSO) for s in simbolos):
        return "recurso"
    return "motor"


def veredictos() -> List[Dict[str, Any]]:
    en_estudio = {
        par for par, datos in arch.PRESUPUESTO_DE_CRUCES.items()
        if datos.get("objetivo") == "en_estudio"
    }
    salida: List[Dict[str, Any]] = []
    vistos = set()
    por_sitio = {}
    for cruce in arch.cruces():
        par = (cruce["from_context"], cruce["to_context"])
        if par not in en_estudio:
            continue
        por_sitio[(cruce["from"], cruce["to"])] = par
    for (origen, destino), par in sorted(por_sitio.items()):
        ruta = REPO / "scripts" / f"{origen}.py"
        if not ruta.exists():
            candidata = REPO / (origen if origen.endswith(".py") else origen + ".py")
            ruta = candidata if candidata.exists() else REPO / "vault" / f"{origen}.py"
        # Un alias de `scripts/` no lleva el código: el import vive en su dueño.
        try:
            import vault_grafo_import as gi
            ruta = gi.codigo_de(ruta)
        except Exception:
            pass
        # El módulo destino tal y como aparece en el import.
        modulo = destino.replace("/", ".").replace(".py", "")
        simbolos = _simbolos_importados(ruta, modulo) if ruta.exists() else []
        salida.append({
            "par": f"{par[0]} -> {par[1]}",
            "origen": origen,
            "destino": destino,
            "simbolos": simbolos,
            "veredicto": _clasificar(simbolos),
        })
        vistos.add(par)
    for par in sorted(en_estudio - vistos):
        salida.append({"par": f"{par[0]} -> {par[1]}", "origen": "", "destino": "",
                       "simbolos": [], "veredicto": "sin cruce medido"})
    return salida


def _markdown(filas: List[Dict[str, Any]]) -> str:
    lineas = [
        "# Veredicto de los pares `en_estudio` (C-01)",
        "",
        "Instrumento: `audits/reestructura/veredicto_c01.py`.",
        "",
        "| Par | Origen | Destino | Símbolos | Veredicto |",
        "|---|---|---|---|---|",
    ]
    for f in filas:
        simbolos = ", ".join(f["simbolos"][:8]) or "—"
        lineas.append(f"| `{f['par']}` | `{f['origen']}` | `{f['destino']}` | {simbolos} | "
                      f"**{f['veredicto']}** |")
    return "\n".join(lineas) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    filas = veredictos()
    if "--markdown" in argv:
        print(_markdown(filas))
    else:
        print(json.dumps(filas, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
