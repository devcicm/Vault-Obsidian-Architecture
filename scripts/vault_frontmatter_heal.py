#!/usr/bin/env python3
"""vault_frontmatter_heal — repara el frontmatter que existe y no parsea (AP-56).

## El síntoma, y por qué faltaba esta mitad

v40.2 arregló la **prevención**: `yaml_scalar` escapa el valor antes de
escribirlo, así que un `title: Overview: demo` ya no sale de este toolkit. Lo
que nunca se arregló es lo que ya estaba en disco. El contraste de regla 7
contra los cuatro vaults consumidores encontró **doce notas** con bloque
`---` que `yaml.safe_load` rechaza, ocho de ellas por ese mismo `: ` sin
escapar. Son notas escritas antes del arreglo, o por un consumidor sincronizado
a una versión anterior.

Para el consumidor —Obsidian, y cualquier parser— esa nota **no tiene
frontmatter**: no tiene id, ni tags, ni tipo, ni estado. No es lo mismo que
AP-28, que es la nota que nunca tuvo bloque: aquí el bloque está, se ve al
abrir el fichero, y por eso nadie lo revisa. El dato parece estar y no está.

`vault_fix_brackets` hace este trabajo para AP-22/AP-24. Esto es su equivalente
para el frontmatter.

## Qué repara y qué se niega a tocar

Solo el escalar sin escapar, que es la única causa con arreglo mecánico
seguro: se cita el valor y no se toca nada más. El resto —bloques escalares
truncados, alias rotos, claves duplicadas— se **reporta y no se escribe**.
Adivinar qué quiso decir un YAML roto es inventar dato, y esta tool no está
para eso.

## El límite declarado

Si el bloque no cierra **y el fichero no tiene ningún otro `---`**, no hay
bloque que partir: la nota es indistinguible de una sin frontmatter (AP-28) sin
adivinar dónde acaba el bloque, y adivinarlo es lo que `_cerrar_bloque` se
niega a hacer. Esas notas no se cuentan aquí. Se dice en vez de taparlo con una
heurística, y hay test que lo fija.

## El criterio es el del consumidor (AP-44)

Una reparación se acepta solo si, después, `yaml.safe_load` devuelve un dict
**y las claves que ya se leían siguen valiendo lo mismo**. Si el parser real no
la acepta, el fichero no se escribe: una tool que se conforma con su propia
idea de "arreglado" es exactamente lo que AP-44 describe.

    python scripts/vault_frontmatter_heal.py             # dry-run, no escribe
    python scripts/vault_frontmatter_heal.py --apply     # repara
    python scripts/vault_frontmatter_heal.py --check --strict   # 1 si hay roto

No acepta `--root` (regla 1): el destino sale de `vault_io.get_vault_root()`,
o de `VAULT_ROOT` para forzarlo.
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))

import yaml

from vault_errors import emit_error, wrap_main
from vault_io import atomic_write_text, get_vault_root, is_snapshot_path
from vault_lib import yaml_scalar

#: Lo que esta tool sabe arreglar. Cualquier otra causa se reporta con su
#: mensaje de YAML y se deja en paz — el catálogo de lo que NO se toca es la
#: mitad honesta de un healer.
REPARABLE = "escalar_sin_escapar"

#: La segunda causa, y la que menos se ve: el bloque **no se cerró**. El
#: fichero abre `---`, escribe sus claves y sigue con el cuerpo sin el
#: delimitador de cierre, así que el parser se traga la nota entera como si
#: fuera YAML y revienta cientos de líneas más abajo, en un bloque de código o
#: en una tabla. El mensaje que da (`while scanning a block scalar`) señala el
#: sitio donde explotó, no el sitio donde está el fallo — que es justo por lo
#: que estas tres notas de `ans` llevaban meses así.
SIN_CERRAR = "delimitador_sin_cerrar"


def _partir(texto: str) -> Optional[Tuple[str, str]]:
    """`(bloque, resto)` si hay frontmatter delimitado, o None.

    Se parte por el delimitador y no por regex de líneas: el criterio del
    consumidor es `texto.startswith("---")` y el siguiente `---` (AP-44).
    """
    if not texto.startswith("---"):
        return None
    partes = texto.split("---", 2)
    if len(partes) < 3:
        return None
    return partes[1], partes[2]


def diagnosticar(texto: str) -> Optional[Dict[str, Any]]:
    """El fallo del bloque según el parser real, o None si parsea bien.

    Devuelve también los datos que sí se leían, para poder comprobar después
    que la reparación no cambió ninguno.
    """
    partido = _partir(texto)
    if partido is None:
        return None
    bloque, _ = partido
    try:
        datos = yaml.safe_load(bloque)
    except yaml.YAMLError as exc:
        return {"error": str(exc).splitlines()[0].strip()}
    if not isinstance(datos, dict):
        # Un frontmatter que parsea a una cadena o a una lista tampoco es un
        # frontmatter, pero no es lo mismo que uno que revienta: se distingue.
        return {"error": f"el bloque parsea a {type(datos).__name__}, no a un mapa"}
    return None


def _reparar_bloque(bloque: str) -> Tuple[str, List[str]]:
    """Cita el valor de las claves de primer nivel que lo necesiten.

    Solo líneas `clave: valor` sin sangrar y con valor en la misma línea: una
    clave sangrada pertenece a una estructura anidada, y citarla ahí cambiaría
    el significado en vez de conservarlo.
    """
    tocadas: List[str] = []
    salida: List[str] = []
    for linea in bloque.split("\n"):
        cruda = linea.rstrip("\r")
        if (not cruda or cruda[0] in " \t-#" or ":" not in cruda):
            salida.append(cruda)
            continue
        clave, _, valor = cruda.partition(":")
        valor = valor.strip()
        if not clave.strip() or " " in clave.strip() or not valor:
            salida.append(cruda)
            continue
        try:
            yaml.safe_load(f"k: {valor}")
        except yaml.YAMLError:
            salida.append(f"{clave}: {yaml_scalar(valor)}")
            tocadas.append(clave.strip())
            continue
        salida.append(cruda)
    return "\n".join(salida), tocadas


def _claves_legibles(bloque: str) -> Dict[str, Any]:
    """Lo que el parser sacaba del bloque roto — casi siempre nada.

    Sirve para la única garantía que esta tool da: reparar no puede cambiar un
    valor que ya se leía.
    """
    try:
        datos = yaml.safe_load(bloque)
    except yaml.YAMLError:
        return {}
    return datos if isinstance(datos, dict) else {}


def reparar(texto: str) -> Optional[Dict[str, Any]]:
    """El texto reparado y qué se tocó, o None si no se pudo arreglar.

    None no es "estaba bien": para eso está `diagnosticar`. Es "no sé
    arreglarlo sin inventarme el contenido", que es un resultado legítimo y se
    reporta como tal.
    """
    partido = _partir(texto)
    if partido is None:
        return None
    bloque, resto = partido
    nuevo, tocadas = _reparar_bloque(bloque)
    if not tocadas:
        return _cerrar_bloque(texto)

    try:
        datos = yaml.safe_load(nuevo)
    except yaml.YAMLError:
        return None
    if not isinstance(datos, dict):
        return None

    # Ninguna clave que ya se leía puede cambiar de valor. Sin esto, "arreglado"
    # significaría solo "ahora parsea", que es lo que dice la tool y no el dato.
    antes = _claves_legibles(bloque)
    if any(datos.get(k) != v for k, v in antes.items()):
        return None

    return {
        "text": f"---{nuevo}---{resto}",
        "keys_quoted": tocadas,
        "cause": REPARABLE,
    }


def _cerrar_bloque(texto: str) -> Optional[Dict[str, Any]]:
    """Pone el `---` que falta, y solo si no hay nada que interpretar.

    Las condiciones son deliberadamente estrechas, porque aquí la garantía de
    "ninguna clave cambia de valor" no protege: antes no se leía ninguna. Así
    que el corte tiene que ser evidente por sí mismo — una tira de `clave:
    valor` seguida de una línea en blanco o de un encabezado— y lo que quede
    detrás tiene que parsear a un mapa. Si el cuerpo empieza con algo que
    también parece frontmatter, no se toca: adivinar dónde acaba el bloque es
    inventarse dónde empieza la nota.
    """
    lineas = texto.split("\n")
    if not lineas or lineas[0].rstrip("\r") != "---":
        return None

    claves: List[str] = []
    corte = None
    for i, cruda in enumerate(lineas[1:], start=1):
        linea = cruda.rstrip("\r")
        if not linea.strip() or linea.lstrip().startswith("#"):
            corte = i
            break
        if linea == "---":
            return None  # el bloque sí cerraba: el fallo es otro
        clave, sep, valor = linea.partition(":")
        if not sep or not clave.strip() or " " in clave.strip() or not valor.strip():
            return None
        claves.append(clave.strip())

    if corte is None or not claves:
        return None

    bloque = "\n".join(l.rstrip("\r") for l in lineas[1:corte])
    try:
        datos = yaml.safe_load(bloque)
    except yaml.YAMLError:
        return None
    if not isinstance(datos, dict) or sorted(datos) != sorted(claves):
        return None

    cuerpo = "\n".join(lineas[corte:])
    return {
        "text": f"---\n{bloque}\n---\n{cuerpo}",
        "keys_quoted": [],
        "keys_recovered": claves,
        "cause": SIN_CERRAR,
    }


def _notas(raiz: Path) -> List[Path]:
    return [
        p for p in raiz.rglob("*.md")
        if p.is_file() and not is_snapshot_path(p.relative_to(raiz))
    ]


def heal(apply: bool = False) -> Dict[str, Any]:
    raiz = get_vault_root()
    reparadas: List[Dict[str, Any]] = []
    irreparables: List[Dict[str, Any]] = []

    for p in _notas(raiz):
        try:
            texto = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            # No se cuenta como frontmatter roto: es una nota que no se pudo
            # mirar, y agregarlas juntas es AP-51.
            irreparables.append({
                "path": str(p.relative_to(raiz)).replace("\\", "/"),
                "error": f"ilegible: {type(exc).__name__}",
                "cause": "ilegible",
            })
            continue

        fallo = diagnosticar(texto)
        if fallo is None:
            continue
        rel = str(p.relative_to(raiz)).replace("\\", "/")
        arreglo = reparar(texto)
        if arreglo is None:
            irreparables.append({"path": rel, "error": fallo["error"],
                                 "cause": "no_mecanico"})
            continue

        entrada = {"path": rel, "error": fallo["error"],
                   "keys_quoted": arreglo["keys_quoted"],
                   # Qué claves vuelven a leerse. En el bloque sin cerrar es el
                   # dato que importa: no eran cero por estar vacías, era el
                   # frontmatter entero invisible para el consumidor.
                   "keys_recovered": arreglo.get("keys_recovered", []),
                   "cause": arreglo["cause"]}
        if apply:
            atomic_write_text(p, arreglo["text"])
            entrada["written"] = True
        reparadas.append(entrada)

    return {
        "ok": not (reparadas or irreparables) if not apply else not irreparables,
        "tool": "vault_frontmatter_heal",
        "action": "apply" if apply else "check",
        "notes_scanned": len(_notas(raiz)),
        # AP-37: cuántas notas cambiaron **en disco**, que no es lo mismo que
        # cuántas se pueden reparar. En dry-run es cero, y esa es la respuesta
        # correcta — sin este campo, una llamada que no escribió nada y otra
        # que reparó siete devuelven lo mismo.
        "healed": sum(1 for r in reparadas if r.get("written")),
        "unparseable_total": len(reparadas) + len(irreparables),
        "repaired": reparadas,
        "repaired_count": len(reparadas),
        "unrepairable": irreparables,
        "unrepairable_count": len(irreparables),
        "hint": (
            "Lo irreparable no se adivina: se abre y se decide a mano. Un healer "
            "que completa un YAML truncado inventa dato, que es peor que el hueco."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="vault_frontmatter_heal — repara el frontmatter que no parsea (AP-56)")
    ap.add_argument("--apply", action="store_true", help="escribe las reparaciones")
    ap.add_argument("--check", action="store_true", help="solo mide (por defecto)")
    ap.add_argument("--strict", action="store_true", help="exit 1 si queda algo roto")
    args = ap.parse_args()

    if args.apply and args.check:
        # `emit_error` construye el envelope, no lo imprime ni devuelve un exit
        # code: devolverlo desde `main` hacía que `wrap_main` publicara
        # `UNEXPECTED_ERROR` sobre un fallo de uso que tiene arreglo. Salió al
        # escribir el test de la ruta gemela en `vault_criterios` (v40.13);
        # aquí llevaba desde v40.12 sin que ninguna prueba pisara esta rama.
        env = emit_error(
            "vault_frontmatter_heal", "CONFLICTING_ARGS",
            "--apply y --check piden cosas distintas: o mide o escribe",
        )
        env["recovery"] = "elige uno"
        print(__import__("json").dumps(env, ensure_ascii=False))
        return 1

    resultado = heal(apply=args.apply)
    print(__import__("json").dumps(resultado, ensure_ascii=False))
    return 1 if args.strict and not resultado["ok"] else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_frontmatter_heal"))
