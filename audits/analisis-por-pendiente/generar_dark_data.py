#!/usr/bin/env python3
"""dark data: qué código del repo está vivo, qué está declarado, qué es
derivado y qué está muerto (o casi).

El barrido mira **todo** el repositorio y clasifica cada fichero en cuatro
estados, con la evidencia de por qué:

- **vivo**: se usa — es una tool, lo importa alguien, o lo cita alguien.
- **declarado**: no se usa, pero su existencia es un contrato (un alias con
  `superseded_by:`, un test que recoge pytest, un índice por convención, el
  registro histórico de `audits/`).
- **derivado**: se regenera (los adaptadores de `vault_toolkit/operations/`,
  los catálogos y los artefactos que produce `vault_fix_all`).
- **muerto**: no lo usa nadie, no lo declara nadie y no se regenera. **Debe
  ser cero**: si aparece, es un hallazgo.

Y los **casi**: cosas que parecen dark data y no lo son, con su riesgo
medido (lo que no está barrido por las puertas, lo que no tiene dueño).

Uso:
    python audits/analisis-por-pendiente/generar_dark_data.py
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import vault_grafo_import as gi  # noqa: E402

DESTINO = AQUI / "DARK-DATA-2026-11-05.md"

#: Carpetas que no son del repo:ephemeras, artefactos de build o runtime.
FUERA = {
    ".git", "node_modules", "__pycache__", "build", "dist", "dist_test",
    ".pytest_cache", ".venv", "venv", ".mypy_cache", ".vs", ".claude",
    "vault-sandbox", "vault_obsidian_architecture.egg-info", ".archify",
    "vault_toolkit.operations", "tests/.spans",
}

#: Ficheros de convención: se descubren por nombre, no por cita.
CONVENCION = {"index.md", "readme.md", "__init__.py", ".gitkeep", ".gitignore",
               ".gitattributes", "conftest.py", "makefile"}

#: Artefactos derivados: los regenera una puerta del repo.
DERIVADOS = {
    "mcp/nodejs/tools-catalog.json",
    "vault/meta_toolkit/tools-catalog.json",
    "normas/norm-registry.json",
    "docs/data-framework.json",
    "docs/quality-index.json",
    "docs/standard-version.json",
    "scripts/toolkit-audit-last.json",
    "schemas/note-contract.json",
}

EXTENSIONES_TEXTO = {".py", ".md", ".json", ".mjs", ".js", ".yaml", ".yml",
                      ".toml", ".txt", ".html", ".css", ".sh", ".ps1"}


def git(*args: str) -> str:
    p = subprocess.run(["git", *args], cwd=str(REPO), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.stdout


def universo() -> List[Path]:
    """Los ficheros **versionados** del repo: lo que se publica.

    Los ficheros locales que el `.gitignore` excluye (ajustes del agente,
    caches, artefactos de build) no son parte del repo y no se miden: contarlos
    sería medir el escritorio de quien lo clone, no el estándar.
    """
    versionados = [f for f in git("ls-files").splitlines() if f.strip()]
    return sorted((REPO / f) for f in versionados if (REPO / f).is_file())


def textos() -> List[Tuple[str, str]]:
    """El contenido de todo lo que puede citar a otro fichero."""
    salida = []
    for ruta in universo():
        if ruta.suffix.lower() not in EXTENSIONES_TEXTO:
            continue
        try:
            salida.append((str(ruta.relative_to(REPO)).replace("\\", "/"),
                           ruta.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
    return salida


def es_alias_con_declaracion(ruta: Path) -> bool:
    """Un alias que declara `superseded_by:` es contrato, no deuda."""
    try:
        t = ruta.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return "superseded_by:" in t and "sys.modules[__name__]" in t


def es_test(ruta: Path) -> bool:
    partes = ruta.relative_to(REPO).parts
    return (partes[0] == "tests" or
            (partes[0] == "normas" and ruta.name.startswith("test_")))


def es_generado(ruta: Path) -> bool:
    """¿El fichero lo produce un generador del repo?"""
    rel = str(ruta.relative_to(REPO)).replace("\\", "/")
    if rel in DERIVADOS:
        return True
    if rel.startswith("vault_toolkit/operations/"):
        return True
    try:
        t = ruta.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return "Adaptador generado" in t or "Generado automáticamente" in t


def medir() -> Dict[str, Any]:
    ficheros = universo()
    todos = textos()
    grafo = gi.completo()
    nodos_grafo = set(grafo)

    # Quién cita a quién: por nombre de fichero y por ruta relativa.
    citas: Dict[str, Set[str]] = defaultdict(set)
    for origen, texto in todos:
        for ruta in ficheros:
            rel = str(ruta.relative_to(REPO)).replace("\\", "/")
            nombre = ruta.name
            if nombre in texto or rel in texto:
                citas[nombre].add(origen)

    clasificacion: Dict[str, List[str]] = defaultdict(list)
    evidencia: Dict[str, List[str]] = {}
    for ruta in ficheros:
        rel = str(ruta.relative_to(REPO)).replace("\\", "/")
        nombre = ruta.name
        partes = rel.split("/")
        citados = citas.get(nombre, set()) - {rel}
        if es_test(ruta):
            estado = "declarado"
            porque = "test: lo recoge pytest, no se cita por nombre"
        elif es_generado(ruta):
            estado = "derivado"
            porque = "lo regenera una puerta del repo"
        elif partes[0] == "audits":
            estado = "declarado"
            porque = "registro histórico del proyecto (no se mueve)"
        elif partes[0] == ".archify":
            estado = "declarado"
            porque = "evidencia de la entrega de los mapas (archify): se guarda " \
                      "junto a su artefacto"
        elif nombre in CONVENCION:
            estado = "declarado"
            porque = "convención de descubrimiento"
        elif es_alias_con_declaracion(ruta):
            estado = "declarado"
            porque = "alias con `superseded_by:` (no-derogación)"
        elif partes[0] == "scripts" and ruta.stem in nodos_grafo:
            estado = "vivo"
            porque = f"tool/adaptador del grafo: {len(citados)} lo citan"
        elif rel in DERIVADOS:
            estado = "derivado"
            porque = "artefacto derivado"
        elif citados:
            estado = "vivo"
            porque = f"{len(citados)} ficheros lo citan"
        else:
            estado = "muerto"
            porque = "nadie lo importa, lo cita ni lo declara"
        clasificacion[estado].append(rel)
        evidencia[rel] = porque

    return {
        "ficheros": len(ficheros),
        "clasificacion": {k: sorted(v) for k, v in clasificacion.items()},
        "evidencia": evidencia,
        "citas": {k: len(v) for k, v in citas.items()},
        "grafo_modulos": len(nodos_grafo),
    }


def casi_muertos(d: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Lo que PARECE dark data y no lo es, con su riesgo medido."""
    casi = []

    # 1. Los adaptadores: derivados, pero su generador puede no estar en el repo.
    adaptadores = [r for r in d["clasificacion"].get("derivado", [])
                   if r.startswith("vault_toolkit/operations/")
                   and not r.endswith("/__init__.py")]
    # Un generador es quien **sostiene** la plantilla para escribirla, no quien
    # la menciona. La primera versión buscaba el texto y pedía
    # `write_text`/`escribir`: no vio `vault_distribution_sync.write_bytes`,
    # así que publicó «sin generador» sobre un repo que ya lo tenía, y después
    # se contó a sí misma al citar la frase en un comentario (AP-44: el
    # instrumento medido con su propia normalización). La señal es sintáctica:
    # una asignación cuyo valor es la plantilla.
    def _sostiene_la_plantilla(texto: str) -> bool:
        try:
            arbol = ast.parse(texto)
        except SyntaxError:
            return False
        for nodo in ast.walk(arbol):
            if isinstance(nodo, (ast.Assign, ast.AnnAssign)):
                valor = nodo.value
                if (isinstance(valor, ast.Constant)
                        and isinstance(valor.value, str)
                        and "Adaptador generado" in valor.value):
                    return True
        return False

    generadores = [
        rel for rel, texto in textos()
        if rel not in {"scripts/vault_mcp_catalog.py"}
        and not rel.startswith("vault_toolkit/operations/")
        and _sostiene_la_plantilla(texto)
    ]
    casi.append({
        "que": f"{len(adaptadores)} adaptadores en `vault_toolkit/operations/`",
        "por_que_no_es_muerto": "se materializan en el artefacto de distribución "
                                 "desde la metadata canónica",
        "riesgo": ("sin generador en el repo: una tool nueva necesita su "
                    "adaptador escrito a mano y nada lo recuerda")
        if not generadores else
        ("con generador en el repo: se regeneran ("
         + ", ".join(sorted(set(generadores))[:2]) + ")"),
        "medida": len(adaptadores),
    })

    # 2. Codigo fuera de las carpetas que barren las puertas Y fuera de las
    #    que el layout declara: ahi no mide nadie.
    sys.path.insert(0, str(REPO / "vault" / "kernel"))
    import rutas as rutas_modulo  # noqa: E402
    barridas = set(rutas_modulo.CARPETAS_DE_CODIGO) | set(rutas_modulo.CARPETAS_DE_CODIGO_Y_MCP)
    # v41.26: «declarada» es `CARPETAS_DEL_REPO`, no `NOMBRES`. Son dos
    # conjuntos a propósito: `NOMBRES` es lo que el guard de literales vigila
    # y `AGENT` está declarada sin dar señal (46 de sus 47 literales nombran
    # un actor, no una ruta). Medir con `NOMBRES` habría seguido publicando
    # una carpeta sin declarar que sí lo está.
    declaradas = set(rutas_modulo.CARPETAS_DEL_REPO)
    ciegas = [r for r in d["clasificacion"].get("vivo", []) + d["clasificacion"].get("declarado", [])
              if r.endswith(".py")
              and r.split("/")[0] not in barridas
              and r.split("/")[0] not in declaradas
              and not es_test(REPO / r)]
    casi.append({
        "que": f"{len(ciegas)} ficheros .py en carpetas que ni el layout declara "
               "ni las puertas barren",
        "por_que_no_es_muerto": (
            "existen y se usan, pero el layout no los reconoce como código"
            if ciegas else
            "ninguno: toda carpeta con `.py` está declarada por el layout"),
        "riesgo": (
            "su calidad no la mide ninguna puerta y el guard de rutas no los ve"
            if ciegas else
            "cerrado en v41.26: `vault/kernel/rutas.py` declara las carpetas y "
            "`test_rutas_repo` falla si aparece una sin declarar"),
        "medida": ", ".join(sorted({r.split('/')[0] for r in ciegas})) or "—",
    })

    # 3. Las carpetas de codigo que el layout no declara.
    sin_declarar = [n for n in ("vault", "vault_toolkit", "audits", "agent")
                    if n not in rutas_modulo.CARPETAS_DEL_REPO]
    casi.append({
        "que": f"{len(sin_declarar)} carpetas con código sin declarar en el layout",
        "por_que_no_es_muerto": (
            "el dueño del layout las barre por otra vía (`CARPETAS_DE_CODIGO`)"
            if sin_declarar else
            "ninguna: `CARPETAS_DEL_REPO` nombra todas las del checkout"),
        "riesgo": (
            "dos verdades sobre qué es código aquí; el guard de rutas no las "
            "reconoce" if sin_declarar else
            "cerrado en v41.26: el layout tiene un dueño único y un test que "
            "falla cuando una carpeta nueva no se declara"),
        "medida": ", ".join(sin_declarar),
    })
    return casi


def markdown(d: Dict[str, Any]) -> str:
    L: List[str] = []
    an = L.append
    an("# Dark data — qué está vivo, qué está declarado, qué es derivado")
    an("")
    an("Documento **generado**: "
       "`python audits/analisis-por-pendiente/generar_dark_data.py`.")
    an("Toda cifra sale del barrido; ninguna está escrita a mano (AP-47).")
    an("")
    an("## 1. El barrido")
    an("")
    an(f"- **{d['ficheros']}** ficheros del repo revisados.")
    an(f"- **{d['grafo_modulos']}** módulos en el grafo de imports.")
    an("")
    an("| Estado | Cuántos | Qué significa |")
    an("|---|---:|---|")
    significado = {
        "vivo": "se usa: es una tool, lo importa alguien o lo cita alguien",
        "declarado": "no se usa, pero su existencia es un contrato",
        "derivado": "lo regenera una puerta del repo",
        "muerto": "nadie lo usa, nadie lo declara, nadie lo regenera",
    }
    for estado in ("vivo", "declarado", "derivado", "muerto"):
        an(f"| `{estado}` | {len(d['clasificacion'].get(estado, []))} | "
           f"{significado[estado]} |")
    an("")
    muertos = d["clasificacion"].get("muerto", [])
    if muertos:
        an("### Los muertos (hallazgos)")
        an("")
        for rel in muertos:
            an(f"- `{rel}` — {d['evidencia'][rel]}")
        an("")
    else:
        an("**No hay código muerto.** Todo lo que hay, o se usa, o está declarado")
        an("por un contrato, o se regenera.")
        an("")

    an("## 2. Los casi: lo que parece dark data y no lo es")
    an("")
    for fila in casi_muertos(d):
        an(f"### {fila['que']}")
        an("")
        an(f"- **Por qué no es muerto**: {fila['por_que_no_es_muerto']}")
        an(f"- **El riesgo**: {fila['riesgo']}")
        an(f"- **Medida**: {fila['medida']}")
        an("")

    an("## 3. Cómo se clasificó (el método, para poder discutirlo)")
    an("")
    an("1. **Test** → *declarado*: lo recoge pytest, no se cita por nombre.")
    an("2. **Generado** → *derivado*: los adaptadores de `vault_toolkit/operations/`, "
       "los catálogos y los artefactos que produce `vault_fix_all`.")
    an("3. **`audits/`** → *declarado*: es el registro histórico del proyecto y no "
       "se mueve.")
    an("4. **Convención** (`index.md`, `README.md`, `__init__.py`, `.gitkeep`) → "
       "*declarado*: se descubre por nombre.")
    an("5. **Alias con `superseded_by:`** → *declarado*: es no-derogación.")
    an("6. **Módulo del grafo** → *vivo*: es una tool o un adaptador.")
    an("7. **Citado por alguien** → *vivo*.")
    an("8. **Resto** → *muerto*.")
    an("")
    an("La cita se busca por **nombre de fichero y por ruta relativa**, en todo")
    an("el repo, con el grafo de imports como criterio de quién usa qué.")
    an("")
    return "\n".join(L) + "\n"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="dark data del repo")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    datos = medir()
    if args.json:
        print(json.dumps(datos, ensure_ascii=False, indent=1, default=str))
        return 0
    texto = markdown(datos)
    DESTINO.write_text(texto, encoding="utf-8")
    print(f"escrito: {DESTINO.relative_to(REPO)} ({len(texto)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
