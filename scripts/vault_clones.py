#!/usr/bin/env python3
"""vault_clones — un cuerpo, un dueño (CN-05).

## De dónde sale

Este repo se audita a sí mismo y publica lo que encuentra. Lo que no tenía
guard era lo más fácil de colar: **un cuerpo copiado**. Medido el 2026-10-28
sobre el árbol de `scripts/`, `vault/` y `cli/`: 39 nombres de función
definidos en más de un módulo, 19 de ellos `slugify` —con 15 sombras puras
que delegaban en el dueño sin decirlo—, 9 `parse_frontmatter` y 10 `utcnow`.
Cada copia era una promesa de que el dueño y la copia se portan igual; la
promesa se cumplió hasta que dejó de cumplirse: `vault/kernel/proyectos.py`
tenía `ruta_de_vault` y `anotar_vault` **definidos dos veces**, byte a byte,
y la segunda pareja tapaba a la primera sin que nada lo dijera.

Un guard que mide lo que su propio repo hace —y que se certifica a sí mismo
midiendo con la misma normalización con la que mide— es el mismo blindness
que AP-44 ya advertía. Aquí no se mide por texto: se mide por **AST**, y el
cuerpo que se compara es el que Python ejecuta, no el que alguien escribió.

## Qué mide

**R1 — sombra.** Dos definiciones del mismo nombre en el mismo módulo, o una
definición que tapa un nombre importado. Siempre es deuda: en Python la
última gana, y nadie lee el fichero entero para saber cuál. No admite
excepción: si el módulo necesita dos, el segundo necesita otro nombre.

**R2 — clon.** Dos o más funciones, **en módulos distintos**, con el mismo
cuerpo una vez normalizado (`ast.unparse` sin el docstring). La comparación
es estructural, no textual: los comentarios se caen, el sangrado se cae, y el
cuerpo que queda es el que se ejecuta.

Lo que se mide con dos reglas es lo que se puede decidir sin interpretar: si
dos cuerpos son el mismo, hay dos dueños de un mismo cuerpo. El *qué hacer*
con eso —fusionar, declarar o mover— lo decide quien lo arregla, no el guard.

## Las dos exenciones, y por qué existen

No toda coincidencia es un defecto, y una tool que no lo reconoce se
equivoca en las dos direcciones: marca como deuda lo que está declarado y
deja pasar lo que no.

1. **Contrato sustituido.** Una función cuyo docstring dice `superseded_by:`
   se conserva por no-derogación: el contrato sigue publicado aunque otro lo
   haya sustituido. Su cuerpo puede coincidir con el de otra y ambas siguen
   vivas por un motivo escrito.
2. **Respaldo declarado.** Una función de nivel de módulo cuyo nombre se
   reimporta después en un `try: ... except ImportError:` es un **respaldo**:
   el dueño es el módulo importado y la copia local existe para cuando ese
   import no llega. `vault_lib` lo hace con `slugify`, `slugify_strict` y
   `clave_de_nombre` —el puente de la casa— y `tests/test_slug_canonico.py`
   verifica que las dos copias dan lo mismo. No es un clon: es un contrato
   con dos implementaciones que deben coincidir, y ese contrato ya tiene su
   test.

Ambas exenciones se **publican** en el envelope, con su categoría y su
motivo. Una exención silenciosa es un agujero con nombre bonito.

## La baseline

Los duplicados que no se pueden fusionar —porque fusionarlos cruzaría una
frontera de contexto o crearía un módulo para un solo uso— **se declaran**:
entran en `scripts/clones-baseline.json` con su motivo escrito. No se borran
y no desaparecen: se cuentan, y la cuenta solo puede bajar.

La regla es la de la casa: **una baseline que solo encoge**. Congelar deuda
nueva exige `--freeze --admitir-nuevos`, que la lista en el envelope; y todo
sitio congelado tiene que **decir por qué se queda**. Un duplicado sin motivo
es una excepción sin dueño, y esto lo falla: `sites_without_motive`.

## Qué NO demuestra el verde

Mide el **AST estático** de `scripts/`, `vault/` y `cli/`. No ve el código
generado en runtime, ni las copias que viven en otro lenguaje, ni un cuerpo
que se arma con `exec` o con `eval`. Verde aquí significa que no apareció un
cuerpo duplicado nuevo entre los que se leen por AST; no significa que el
repo no tenga duplicados.

    python scripts/vault_clones.py --check --strict
    python scripts/vault_clones.py --freeze
"""

import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent))

import vault_baseline
from vault_errors import emit_error, wrap_main

#: La baseline de CN-05. Vive junto a la tool, como las de los demás guards.
BASELINE = Path(__file__).parent / "clones-baseline.json"

#: El directorio del programa: `scripts/` en el checkout, `_impl/` en la wheel.
DIRECTORIO = Path(__file__).parent

#: Carpetas que no se miden: material archivado, material ilegible o copiado.
#: `vault-sandbox/` no está en la lista porque **no está en los árboles que se
#: miden** —la raíz del repo tiene su propia carpeta, y `scripts/`, `vault/` y
#: `cli/` no la contienen—: escribir su nombre aquí sería nombrarlo sin dueño
#: (el guard de rutas, `tests/test_rutas_repo.py`).
EXCLUIR = ("_archived", "__pycache__", "dist", "build",
           "node_modules", "site-packages", ".git")


def _raiz(raiz: Optional[Path] = None) -> Path:
    """La raíz del repo, o la que se le inyecte (para los tests)."""
    return (raiz or DIRECTORIO.parent).resolve()


def _bases(raiz: Path, por_defecto: bool) -> List[Path]:
    """Las carpetas que se miden, en el checkout y en la wheel.

    En el checkout el programa vive en `scripts/`; en la wheel, en `_impl/`.
    `vault/` y `cli/` son hermanos del programa, no hijos: se buscan en la
    raíz.

    Con una raíz inyectada (los tests) **no** se cae al programa real: un
    árbol de prueba que mide el repo entero mediría lo que no quiere.
    """
    scripts = raiz / "scripts"
    if not scripts.is_dir():
        scripts = DIRECTORIO if por_defecto else None
    bases = [scripts] if scripts else []
    for nombre in ("vault", "cli"):
        carpeta = raiz / nombre
        if carpeta.is_dir():
            bases.append(carpeta)
    return bases


def _ficheros(raiz: Path, por_defecto: bool = True) -> List[Path]:
    salida: List[Path] = []
    for base in _bases(raiz, por_defecto):
        for p in sorted(base.rglob("*.py")):
            if any(parte in EXCLUIR for parte in p.parts):
                continue
            salida.append(p)
    return salida


def _docstring(node: ast.AST) -> str:
    if (node.body and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)):
        return node.body[0].value.value
    return ""


def _cuerpo(node: ast.AST) -> str:
    """El cuerpo sin docstring, normalizado: lo que se ejecuta."""
    stmts = list(node.body)
    if (stmts and isinstance(stmts[0], ast.Expr)
            and isinstance(stmts[0].value, ast.Constant)
            and isinstance(stmts[0].value.value, str)):
        stmts = stmts[1:]
    return "\n".join(ast.unparse(s) for s in stmts)


def _respaldo(arbol: ast.Module) -> Set[str]:
    """Nombres reimportados en un `try/except ImportError`: respaldos de casa.

    El patrón del puente es: se declara la función local, y después se
    intenta el import del dueño; si el import no llega, la local queda. La
    copia no es un clon: es el respaldo de un contrato, y su equivalente
    (que ambas den lo mismo) lo verifica otro test.
    """
    respaldos: Set[str] = set()
    for node in ast.walk(arbol):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if handler.type is None:
                continue
            # `except ImportError` y `except (ImportError, ValueError)` cuentan
            # los dos: `handler.type` es una expresión, no una lista.
            if "ImportError" not in ast.unparse(handler.type):
                continue
            for stmt in node.body:
                if isinstance(stmt, ast.ImportFrom):
                    for alias in stmt.names:
                        respaldos.add(alias.asname or alias.name.split(".")[0])
                elif isinstance(stmt, ast.Import):
                    for alias in stmt.names:
                        respaldos.add(alias.asname or alias.name.split(".")[0])
    return respaldos


def _nombres_importados(arbol: ast.Module) -> Set[str]:
    nombres: Set[str] = set()
    for node in arbol.body:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                nombres.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                nombres.add(alias.asname or alias.name.split(".")[0])
    return nombres


def _asignaciones(arbol: ast.Module) -> Set[str]:
    """Nombres asignados a nivel de módulo (`x = ...`)."""
    nombres: Set[str] = set()
    for node in arbol.body:
        if isinstance(node, ast.Assign):
            for objetivo in node.targets:
                if isinstance(objetivo, ast.Name):
                    nombres.add(objetivo.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            nombres.add(node.target.id)
    return nombres


def _analizar(p: Path, raiz: Path) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    """`(sombras, funciones)` de un módulo. El AST manda; el texto no."""
    texto = p.read_text(encoding="utf-8", errors="replace")
    arbol = ast.parse(texto)
    rel = p.relative_to(raiz).as_posix()

    importados = _nombres_importados(arbol)
    asignados = _asignaciones(arbol)
    respaldos = _respaldo(arbol)

    definiciones: Dict[str, List[ast.AST]] = {}
    for node in arbol.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definiciones.setdefault(node.name, []).append(node)

    sombras: List[Dict[str, str]] = []
    for nombre, nodes in sorted(definiciones.items()):
        if len(nodes) > 1:
            sombras.append({"ruta": rel, "nombre": nombre,
                            "motivo": f"definido {len(nodes)} veces en el mismo módulo"})
        elif nombre in importados:
            sombras.append({"ruta": rel, "nombre": nombre,
                            "motivo": "la definición tapa un nombre importado"})
    for nombre in sorted(asignados & importados):
        if nombre not in definiciones:
            sombras.append({"ruta": rel, "nombre": nombre,
                            "motivo": "la asignación tapa un nombre importado"})

    funciones: List[Dict[str, Any]] = []
    for node in arbol.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        doc = _docstring(node)
        cuerpo = _cuerpo(node)
        exencion = None
        if "superseded_by" in doc:
            exencion = "contrato"
        elif node.name in respaldos:
            exencion = "respaldo"
        funciones.append({
            "ruta": rel,
            "nombre": node.name,
            "cuerpo": cuerpo,
            "huella": hashlib.sha1(cuerpo.encode("utf-8")).hexdigest()[:8],
            "sentencias": len([l for l in cuerpo.splitlines() if l.strip()]),
            "exencion": exencion,
            "docstring": doc,
        })
    return sombras, funciones


def _firma_sombra(sombra: Dict[str, str]) -> str:
    return f"sombra|{sombra['ruta']}::{sombra['nombre']}"


def _firma_clon(grupo: List[Dict[str, Any]]) -> str:
    """La firma de un grupo de clones: qué cuerpo, cuántos y dónde.

    Lleva el número de miembros y su lista, así que un clon que **se suma**
    a un grupo ya congelado cambia la firma y aparece como deuda nueva: el
    grupo no puede crecer en silencio. Y llevar las rutas —no las líneas—
    hace que mover una función no la vuelva nueva.
    """
    lugares = sorted(f"{f['ruta']}::{f['nombre']}" for f in grupo)
    return f"clone|{grupo[0]['huella']}|{len(grupo)}|" + ",".join(lugares)


def medir(raiz: Optional[Path] = None) -> Dict[str, Any]:
    """Mide el árbol. Devuelve firmas, no objetos: lo que se congela son firmas."""
    por_defecto = raiz is None
    base = _raiz(raiz)
    sombras: List[Dict[str, str]] = []
    funciones: List[Dict[str, Any]] = []
    modulos = 0
    for p in _ficheros(base, por_defecto):
        try:
            s, f = _analizar(p, base)
        except SyntaxError:
            continue
        modulos += 1
        sombras.extend(s)
        funciones.extend(f)

    # R1 — sombra
    firmas_sombra = sorted(_firma_sombra(s) for s in sombras)

    # R2 — clones: cuerpos idénticos, en módulos distintos
    por_cuerpo: Dict[str, List[Dict[str, Any]]] = {}
    for f in funciones:
        if not f["cuerpo"].strip() or f["sentencias"] < 2:
            continue
        por_cuerpo.setdefault(f["huella"], []).append(f)

    grupos: List[Dict[str, Any]] = []
    exentos_contrato: List[Dict[str, str]] = []
    exentos_respaldo: List[Dict[str, str]] = []
    for huella, miembros in sorted(por_cuerpo.items()):
        if len(miembros) < 2:
            continue
        medibles = [m for m in miembros if m["exencion"] is None]
        for m in miembros:
            if m["exencion"] == "contrato":
                exentos_contrato.append({"ruta": m["ruta"], "nombre": m["nombre"],
                                         "motivo": "docstring con `superseded_by:`"})
            elif m["exencion"] == "respaldo":
                exentos_respaldo.append({"ruta": m["ruta"], "nombre": m["nombre"],
                                         "motivo": "respaldo declarado: el dueño se reimporta "
                                                   "en un `try/except ImportError`"})
        if len(medibles) < 2:
            continue
        if len({m["ruta"] for m in medibles}) < 2:
            # Mismo módulo: no es un clon entre módulos, es otra sombra (R1).
            continue
        grupos.append({
            "huella": huella,
            "firma": _firma_clon(medibles),
            "sitios": sorted(f"{m['ruta']}::{m['nombre']}" for m in medibles),
        })

    firmas_clon = sorted(g["firma"] for g in grupos)
    return {
        "modulos": modulos,
        "funciones": len(funciones),
        "firmas_sombra": firmas_sombra,
        "firmas_clon": firmas_clon,
        "grupos": grupos,
        "sombras": sombras,
        "exentos_contrato": sorted(exentos_contrato, key=lambda x: (x["ruta"], x["nombre"])),
        "exentos_respaldo": sorted(exentos_respaldo, key=lambda x: (x["ruta"], x["nombre"])),
    }


def _datos(path: Path) -> Dict[str, Any]:
    return vault_baseline.cargar_datos(path, "CN-05")


def _sitios(path: Path) -> List[str]:
    return vault_baseline.cargar(path, "sitios", "CN-05")


def _motivos(path: Path) -> Dict[str, str]:
    motivos = _datos(path).get("motivos", {})
    return motivos if isinstance(motivos, dict) else {}


def check(raiz: Optional[Path] = None,
          baseline: Optional[Path] = None) -> Dict[str, Any]:
    """El veredicto. `CN-05` se nombra aquí: esta función es la cara del guard."""
    path = baseline or BASELINE
    m = medir(raiz)
    congelados = set(_sitios(path))
    firmas = set(m["firmas_sombra"]) | set(m["firmas_clon"])
    nuevos = sorted(firmas - congelados)
    resueltos = sorted(congelados - firmas)
    motivos = _motivos(path)
    # El motivo se exige de los sitios **vivos**: uno que ya se pagó sale como
    # resuelto y no puede seguir haciendo fallar la puerta —la deuda está
    # saldada, no abandonada—. El que sigue vivo y no dice por qué se queda,
    # ese sí es una excepción sin dueño.
    sin_motivo = sorted(s for s in (congelados & firmas)
                        if not str(motivos.get(s, "")).strip())
    return {
        "ok": not nuevos and not sin_motivo,
        "tool": "vault_clones",
        "norm": "CN-05",
        "action": "check",
        "modules_scanned": m["modulos"],
        "functions_scanned": m["funciones"],
        "shadowing_total": len(m["firmas_sombra"]),
        "shadowing_sites": m["firmas_sombra"],
        "clone_groups_total": len(m["firmas_clon"]),
        "clone_groups": m["grupos"],
        "baseline_size": len(congelados),
        "new_shadowing": sorted(s for s in nuevos if s.startswith("sombra|")),
        "new_clones": sorted(s for s in nuevos if s.startswith("clone|")),
        "resolved_since_baseline": resueltos,
        "sites_without_motive": sin_motivo,
        "exempt_contract": m["exentos_contrato"],
        "exempt_backup": m["exentos_respaldo"],
        "hint": (
            "CN-05 — un cuerpo, un dueño. Un clon nuevo se salda uniendo los "
            "cuerpos en su dueño, no congelándolo. Si el duplicado no se puede "
            "fusionar —porque cruza una frontera de contexto o porque su "
            "duelo exige un módulo para un solo uso— se declara con su motivo "
            "escrito en `scripts/clones-baseline.json`: la cuenta solo puede "
            "bajar. Un sitio congelado sin motivo falla la puerta."
        ),
    }


def freeze(admitir_nuevos: bool = False,
           raiz: Optional[Path] = None,
           baseline: Optional[Path] = None) -> Dict[str, Any]:
    """Congela la deuda viva. Solo puede encoger; crecer se declara o no pasa."""
    path = baseline or BASELINE
    m = medir(raiz)
    firmas = sorted(set(m["firmas_sombra"]) | set(m["firmas_clon"]))
    congelados = set(_sitios(path))
    nuevos = sorted(set(firmas) - congelados)
    if nuevos and not admitir_nuevos:
        return vault_baseline.negativa(
            "vault_clones", "freeze", "new_clones", nuevos,
            "Une los cuerpos en su dueño (CN-05). Si de verdad hay que "
            "congelar deuda nueva, `--freeze --admitir-nuevos` la lista aquí; "
            "el motivo se escribe después en `scripts/clones-baseline.json`, "
            "y un sitio sin motivo hace fallar la puerta.")
    motivos = dict(_motivos(path))
    for firma in firmas:
        motivos.setdefault(firma, "")
    vault_baseline.escribir(
        path, "sitios", "CN-05",
        "Cuerpos duplicados que no se pueden fusionar sin cruzar una frontera "
        "de contexto o sin crear un módulo para un solo uso. Solo puede "
        "encoger: un duplicado nuevo se une a su dueño, no se congela. Cada "
        "sitio dice por qué se queda.",
        firmas, extra={"motivos": motivos})
    return {"ok": True, "tool": "vault_clones", "norm": "CN-05", "action": "freeze",
            "frozen": len(firmas), "admitted_new": nuevos if admitir_nuevos else []}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="vault_clones — cuerpos duplicados: un cuerpo, un dueño (CN-05)",
        allow_abbrev=False)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--admitir-nuevos", action="store_true")
    args = ap.parse_args()

    if args.freeze and args.check:
        env = emit_error("vault_clones", "CONFLICTING_ARGS",
                         "--freeze y --check piden cosas distintas: o mide o congela",
                         pista="elige uno")
        print(json.dumps(env, ensure_ascii=False))
        return 1

    r = freeze(args.admitir_nuevos) if args.freeze else check()
    print(json.dumps(r, ensure_ascii=False))
    return 1 if args.strict and not r["ok"] else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_clones"))
