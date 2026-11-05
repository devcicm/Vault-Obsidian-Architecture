#!/usr/bin/env python3
"""mapa del corazón de v41.26 — qué sostiene el repo, y de qué generación es.

Mide, con las herramientas que el repo ya tiene (nada escrito a mano):

- **El corazón por fan-in**: el grafo de imports real (`vault_grafo_import`),
  con el umbral que el propio estándar aplica (AP-59: fan-in ≥ 80, fan-out ≤
  el escalón del núcleo, churn ≤ el escalón del dominio).
- **Las tres capas**: superficie (`scripts/`: tools y fachadas), dueños
  (`vault/<contexto>/`) y hojas (`vault/kernel/`).
- **La tabla de fachadas → dueño**: el residuo del puente ADR-0002, que hoy
  hay que resolver a mano en cada módulo.
- **Las generaciones de refactor**: qué de cada una sigue vivo, medido con
  el diff de sus commits ancla y con el ledger del refactor actual.

Uso:
    python audits/reestructura/generar_corazon.py            # escribe el .md
    python audits/reestructura/generar_corazon.py --json     # el mismo dato, JSON
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import vault_grafo_import as gi  # noqa: E402

LEDGER = AQUI / "CHANGELOG-REFACTOR.md"
DESTINO = AQUI / "CORAZON-V41.26.md"

#: Las tres generaciones, con el commit que las ancla. El diff contra el
#: primer padre es lo que dice qué tocó cada una.
GENERACIONES: Tuple[Tuple[str, str, str], ...] = (
    ("v40.0–v40.3 · contextos", "f0ab0fc",
     "Nace la estructura de contextos y el puente ADR-0002 (las fachadas "
     "`sys.modules[__name__] = _dueno`)."),
    ("v40.20–v40.27 · núcleo y dueños", "d899e73",
     "Nacen los catálogos: los dueños de los criterios. No toca el corazón."),
    ("v41.25–v41.26 · reestructura/teseo (la actual)", "dd86ee3",
     "El ejecutor en proceso, los bancos en paralelo, la frontera de producto "
     "(`vault_toolkit/`) y los inventarios C-01/C-04/C-06."),
)


def git(*args: str) -> str:
    p = subprocess.run(["git", *args], cwd=str(REPO), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.stdout


def dueno_de_fachada(ruta: Path) -> Optional[str]:
    """El dueño al que apunta una fachada.

    Lo dice el dueño del criterio (`vault_grafo_import.dueno_del_alias`): si
    esa puerta devuelve `None`, el fichero no es un alias del puente.
    """
    return gi.dueno_del_alias(ruta)


def es_entry_point(ruta: Path) -> bool:
    """¿El módulo tiene un `if __name__ == "__main__"` de verdad?

    Por AST y no por texto: el patrón también aparece en los docstrings de
    módulos que no son entry points, y contarlos como tools inflaba la
    medida (AP-44: el criterio del consumidor, no el propio).
    """
    import ast

    try:
        arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return False
    for nodo in arbol.body:
        if not isinstance(nodo, ast.If):
            continue
        prueba = nodo.test
        if not isinstance(prueba, ast.Compare):
            continue
        izquierda = prueba.left
        if (isinstance(izquierda, ast.Name) and izquierda.id == "__name__"
                and isinstance(prueba.ops[0], ast.Eq)
                and isinstance(prueba.comparators[0], ast.Constant)
                and prueba.comparators[0].value == "__main__"):
            return True
    return False


def clasifica_scripts() -> Dict[str, List[str]]:
    """`scripts/` en tres: tools (entry points), fachadas (alias) y otros."""
    tools, fachadas, otros = [], [], []
    for ruta in sorted((REPO / "scripts").glob("*.py")):
        if dueno_de_fachada(ruta):
            fachadas.append(ruta.stem)
        elif es_entry_point(ruta):
            tools.append(ruta.stem)
        else:
            otros.append(ruta.stem)
    return {"tools": tools, "fachadas": fachadas, "otros": otros}


def huellas_de_las_generaciones() -> List[Dict[str, Any]]:
    """Qué tocó cada generación y cuánto de eso sigue en pie.

    La generación actual se mide por **su ledger** (los commits que
    registra), no por el commit ancla: el ancla es una fila, la generación
    son sus 53 commits.
    """
    filas = []
    for nombre, sha, que_hizo in GENERACIONES:
        if sha == "dd86ee3":
            tocados: List[str] = []
            for h in commits_del_ledger():
                tocados.extend(f for f in git("show", "--name-only", "--format=", h).splitlines() if f.strip())
            tocados = sorted(set(tocados))
        else:
            tocados = [f for f in git("diff", "--name-only", f"{sha}^1", sha).splitlines() if f.strip()]
        siguen = [f for f in tocados if (REPO / f).exists()]
        filas.append({
            "nombre": nombre,
            "sha": sha,
            "que_hizo": que_hizo,
            "tocados": len(tocados),
            "siguen": len(siguen),
            "areas": dict(Counter(f.split("/")[0] for f in siguen).most_common()),
        })
    return filas


def fases_del_ledger() -> List[str]:
    if not LEDGER.exists():
        return []
    texto = LEDGER.read_text(encoding="utf-8")
    return sorted(set(re.findall(r"\| ([A-Z]-\d+(?:\.\d+)?)[^|]*\|", texto)))


def commits_del_ledger() -> List[str]:
    if not LEDGER.exists():
        return []
    texto = LEDGER.read_text(encoding="utf-8")
    vistos: List[str] = []
    for h in re.findall(r"`([0-9a-f]{7,40})`", texto):
        if h not in vistos:
            vistos.append(h)
    return vistos


def medir() -> Dict[str, Any]:
    grafo = gi.completo()
    fan_in = gi.fan_in(grafo)
    fan_out = gi.fan_out(grafo)

    import vault_kernel  # noqa: E402
    nucleo = vault_kernel.medir()

    import vault_arch  # noqa: E402

    return {
        "grafo_modulos": len(grafo),
        "fan_in": {k: len(v) for k, v in fan_in.items()},
        "fan_out": {k: len(v) for k, v in fan_out.items()},
        "corazon": [
            {"modulo": nombre, "fan_in": len(origenes),
             "fan_out": len(fan_out.get(nombre, ()))}
            for nombre, origenes in sorted(fan_in.items(),
                                          key=lambda kv: (-len(kv[1]), kv[0]))[:16]
        ],
        "nucleo": {
            "modulos": nucleo.get("kernel"),
            "umbral_fan_in": nucleo.get("umbral_fan_in"),
            "umbral_fan_out": nucleo.get("umbral_fan_out"),
            "umbral_churn": nucleo.get("umbral_churn"),
            "mediana_churn_dominio": nucleo.get("churn_mediana_dominio"),
            "fan_in": nucleo.get("fan_in"),
            "fan_out": nucleo.get("fan_out"),
            "hallazgos": nucleo.get("hallazgos"),
        },
        "contextos": {
            "cuantos": len(vault_arch.CONTEXTS),
            "fronteras": len(vault_arch.PRESUPUESTO_DE_CRUCES),
            "modulos_por_contexto": {c: len(d.get("modulos") or ())
                                     for c, d in vault_arch.CONTEXTS.items()},
            "total_modulos": sum(len(d.get("modulos") or ()) for d in vault_arch.CONTEXTS.values()),
        },
        "scripts": clasifica_scripts(),
        "generaciones": huellas_de_las_generaciones(),
        "fases": fases_del_ledger(),
        "commits_ledger": len(commits_del_ledger()),
    }


def markdown(d: Dict[str, Any]) -> str:
    nucleo = d["nucleo"]
    scripts = d["scripts"]
    lineas: List[str] = []
    an = lineas.append

    an("# El corazón de v41.26 — y de qué generación es cada cosa")
    an("")
    an("Documento **generado**: `python audits/reestructura/generar_corazon.py`.")
    an("Ninguna cifra de aquí está escrita a mano (AP-47): todas salen del grafo")
    an("de imports, del registro de contextos y de las puertas del propio repo.")
    an("")
    an("## 1. Qué es el corazón")
    an("")
    an("El estándar ya tiene la medida (AP-59): un módulo del **núcleo** es el")
    an("que de él depende todo lo demás. El umbral de fan-in es")
    an(f"**{nucleo['umbral_fan_in']}**, y el de fan-out **{nucleo['umbral_fan_out']}**;")
    an(f"el churn no puede pasar de **{nucleo['umbral_churn']}** (la mediana del")
    an(f"dominio es {nucleo['mediana_churn_dominio']}).")
    an("")
    an("| Módulo | fan-in | fan-out | Papel |")
    an("|---|---:|---:|---|")
    for fila in d["corazon"]:
        papel = "fachada" if fila["modulo"] in scripts["fachadas"] else "código real"
        an(f"| `{fila['modulo']}` | **{fila['fan_in']}** | {fila['fan_out']} | {papel} |")
    an("")
    an(f"Con el umbral del propio estándar, el corazón son los módulos que")
    an(f"alcanzan fan-in ≥ {nucleo['umbral_fan_in']}: "
       + ", ".join(f"`{f['modulo']}`" for f in d["corazon"]
                   if f["fan_in"] >= nucleo["umbral_fan_in"])
       + ".")
    an("")
    an("### Las tres capas")
    an("")
    an("| Capa | Qué es | Dónde |")
    an("|---|---|---|")
    an(f"| **Superficie** | las tools que se publican y se ejecutan | "
       f"`scripts/`: {len(scripts['tools'])} tools |")
    an(f"| **Dueños** | los criterios, cada uno en su contexto | "
       f"`vault/<contexto>/` |")
    an(f"| **Hojas** | lo que no depende de nadie | `vault/kernel/` |")
    an("")
    an("## 2. Los hallazgos vivos sobre el núcleo")
    an("")
    hallazgos = nucleo.get("hallazgos") or []
    por_tipo: Dict[str, List[Dict[str, Any]]] = {}
    for hallazgo in hallazgos:
        por_tipo.setdefault(str(hallazgo.get("finding")), []).append(hallazgo)
    for tipo, lista in por_tipo.items():
        an(f"### `{tipo}` ({len(lista)})")
        an("")
        for hallazgo in lista:
            an(f"- `{hallazgo.get('module')}`: {hallazgo.get('why')} "
               f"(valor: {hallazgo.get('value')}).")
        an("")
    an("## 3. `scripts/` en tres: tools, fachadas y los demás")
    an("")
    an(f"- **Tools** (con `__main__`, se ejecutan): **{len(scripts['tools'])}**")
    an(f"- **Fachadas** (alias a un dueño en `vault/`): **{len(scripts['fachadas'])}**")
    an(f"- **Otros** (código real sin punto de entrada): **{len(scripts['otros'])}**")
    an("")
    an("### La tabla que no existía: cada fachada y su dueño")
    an("")
    an("| Fachada en `scripts/` | Dueño real |")
    an("|---|---|")
    for nombre in scripts["fachadas"]:
        dueno = dueno_de_fachada(REPO / "scripts" / f"{nombre}.py")
        an(f"| `{nombre}.py` | `{dueno or '?'}` |")
    an("")
    an("## 4. Los contextos, medidos")
    an("")
    ctx = d["contextos"]
    an(f"- **{ctx['cuantos']}** contextos, **{ctx['fronteras']}** fronteras permitidas.")
    an(f"- **{ctx['total_modulos']}** módulos declarados en los contextos.")
    an("")
    an("| Contexto | Módulos |")
    an("|---|---:|")
    for nombre, n in sorted(ctx["modulos_por_contexto"].items()):
        an(f"| {nombre} | {n} |")
    an("")
    an("## 5. Las generaciones de refactor, y qué de cada una sigue vivo")
    an("")
    for fila in d["generaciones"]:
        an(f"### {fila['nombre']} (`{fila['sha']}`)")
        an("")
        an(f"{fila['que_hizo']}")
        an("")
        an(f"- Tocó **{fila['tocados']}** ficheros; **siguen {fila['siguen']}**.")
        an(f"- Dónde: {', '.join(f'{k} {v}' for k, v in fila['areas'].items()) or '—'}.")
        an("")
    an("### La actual, según su propio registro")
    an("")
    an(f"- `audits/reestructura/CHANGELOG-REFACTOR.md`: **{d['commits_ledger']}** "
       "commits registrados.")
    an(f"- Fases: {', '.join(d['fases'])}.")
    an("- Su predecesora está archivada y medida en "
       "`audits/archivo/reestructura-2026-11-02/`.")
    an("")
    return "\n".join(lineas) + "\n"


def main() -> int:
    # La salida por stdout es UTF-8 siempre: en Windows la consola usa
    # cp1252 y un `≥` la tumba (el house lo resuelve por entorno; aquí, en el
    # propio generador, para que se pueda ejecutar sin recordar nada).
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser(description="mapa del corazón de v41.26")
    ap.add_argument("--json", action="store_true", help="el dato, en JSON")
    args = ap.parse_args()

    datos = medir()
    if args.json:
        # `default=str` por los valores que el motor de auditoría deja como
        # conjuntos: el JSON es para consumo humano y no puede romper el
        # generador por eso.
        print(json.dumps(datos, ensure_ascii=False, indent=1, default=str))
        return 0
    texto = markdown(datos)
    DESTINO.write_text(texto, encoding="utf-8")
    print(f"escrito: {DESTINO.relative_to(REPO)} ({len(texto)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
