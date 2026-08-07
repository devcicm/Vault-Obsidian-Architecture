#!/usr/bin/env python3
"""vault_blame_audit — AP-51: la tool no acusa al dato de su propio fallo.

El síntoma que originó esta norma salió al ejecutar contra un vault ajeno al
estándar (regla 7): tres tools declaraban notas "inválidas" que Obsidian leía
sin problema. La nota estaba bien. Lo que estaba mal era el criterio con el que
se la medía — frontmatter por regex línea a línea en vez de `yaml.safe_load`, y
wikilinks resueltos por `title:`, que Obsidian no mira. La tool falló, y el
veredicto que emitió señalaba al dato.

AP-44 cubre la mitad de arriba: verificar con el criterio del consumidor. Esta
norma cubre la de abajo, que es cómo el fallo llega a parecer un dato malo:

    try:
        fm = read_frontmatter(p) or {}
    except Exception:
        return []          # <- "esta nota no tiene aliases"

El llamante no puede distinguir ese `[]` de una nota que legítimamente no tiene
aliases. Un fallo de lectura se ha convertido en un hecho sobre el vault, y el
informe que lo agregue dirá que N notas carecen de aliases sin que eso sea
cierto. **No es lo mismo "no hay" que "no pude mirar".**

Lo que la norma NO prohíbe: capturar amplio y **exponer** el fallo.
`return {"ok": False, "error": ...}` es correcto — el llamante recibe la mala
noticia y decide. Lo que se prohíbe es devolver un vacío indistinguible de un
resultado legítimo.

    python scripts/vault_blame_audit.py --check    # sitios que se tragan el fallo
    python scripts/vault_blame_audit.py --strict   # exit 1 si la deuda CRECIÓ
    python scripts/vault_blame_audit.py --freeze   # recongela la baseline

## Por qué nace con baseline y no como guard duro

101 sitios en 48 módulos. Un guard que falla en 101 sitios se desactiva el
primer día, que es como mueren los guards — lo mismo que le pasó a AP-37, que
nació con 55 y llegó a 0. La baseline congela la deuda conocida y **solo puede
encoger**: `--strict` falla si aparece un sitio nuevo, no por los que ya había.

## Por qué se mide por AST y no por texto

Un detector que buscara la cadena `except Exception` contaría también los que
están en un comentario o en un docstring, y no vería la diferencia entre un
handler que devuelve `[]` y uno que devuelve `{"ok": False}` — que es justo la
distinción que la norma sostiene. Es el mismo error que AP-44 describe, cometido
en el guard: medir con el criterio propio en vez de con el del consumidor.
"""

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from vault_errors import wrap_main

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
BASELINE_PATH = SCRIPTS_DIR / "blame-baseline.json"

#: Excepciones cuya captura no dice nada sobre qué salió mal. Capturar
#: `FileNotFoundError` es un criterio: el autor sabe qué está tolerando y por
#: qué. Capturar `Exception` es renunciar a saberlo, y por eso el vacío que se
#: devuelva después no puede sostener ningún veredicto.
AMPLIAS = {"Exception", "BaseException", "bare"}

#: Contenedores que, vacíos, son indistinguibles de un resultado legítimo.
_CONTENEDORES = (ast.List, ast.Dict, ast.Set, ast.Tuple)

#: Constantes con el mismo problema. `True` y `False` entran porque un
#: predicado que responde por el camino de fallo está afirmando algo que no
#: comprobó, en cualquiera de los dos sentidos.
_CONSTANTES = (None, "", 0, False, True)


def _es_vacio_indistinguible(sentencia: ast.stmt) -> bool:
    """¿Esta salida del handler es indistinguible de un resultado legítimo?"""
    if isinstance(sentencia, (ast.Pass, ast.Continue)):
        return True
    if not isinstance(sentencia, ast.Return):
        return False
    valor = sentencia.value
    if valor is None:
        return True
    if isinstance(valor, ast.Constant) and valor.value in _CONSTANTES:
        return True
    if isinstance(valor, _CONTENEDORES):
        elementos = getattr(valor, "elts", None)
        if elementos is None:
            elementos = getattr(valor, "keys", [])
        return not elementos
    return False


def _tipos_capturados(handler: ast.ExceptHandler) -> List[str]:
    tipo = handler.type
    if tipo is None:
        return ["bare"]
    if isinstance(tipo, ast.Name):
        return [tipo.id]
    if isinstance(tipo, ast.Tuple):
        return [e.id for e in tipo.elts if isinstance(e, ast.Name)]
    return []


def offenders() -> List[Dict]:
    """Handlers amplios cuya única salida es un vacío indistinguible.

    La clave es `modulo:linea` y no un contador por módulo: una baseline por
    conteo se puede "saldar" arreglando un sitio y estrenando otro, que es
    exactamente la regresión que este audit existe para ver.
    """
    fuera = []
    for path in sorted(SCRIPTS_DIR.glob("vault_*.py")):
        if path.name == "vault_blame_audit.py":
            continue
        try:
            arbol = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for handler in [n for n in ast.walk(arbol)
                        if isinstance(n, ast.ExceptHandler)]:
            tipos = _tipos_capturados(handler)
            if not (AMPLIAS & set(tipos)):
                continue
            if not handler.body:
                continue
            if all(_es_vacio_indistinguible(s) for s in handler.body):
                fuera.append({
                    "site": f"{path.name}:{handler.lineno}",
                    "module": path.name,
                    "line": handler.lineno,
                    "catches": ",".join(tipos),
                })
    return fuera


def load_baseline() -> List[str]:
    if not BASELINE_PATH.exists():
        return []
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return sorted(data.get("sites", []))


def scan() -> Dict:
    actuales = offenders()
    sitios = {o["site"] for o in actuales}
    baseline = set(load_baseline())

    nuevos = sorted(sitios - baseline)      # deuda que CRECIÓ: es un fallo
    resueltos = sorted(baseline - sitios)   # deuda saldada: hay que recongelar

    return {
        # `ok` solo mira los nuevos: la deuda histórica no bloquea, pero no crece.
        "ok": not nuevos,
        "tool": "vault_blame_audit",
        "norm": "AP-51",
        "offenders_total": len(actuales),
        "baseline_size": len(baseline),
        "modules_affected": len({o["module"] for o in actuales}),
        "new_offenders": nuevos,
        "resolved_since_baseline": resueltos,
        "offenders": actuales,
    }


def freeze() -> Dict:
    sitios = sorted(o["site"] for o in offenders())
    BASELINE_PATH.write_text(
        json.dumps(
            {
                "norm": "AP-51",
                "description": (
                    "Deuda conocida de handlers amplios que se tragan el fallo "
                    "propio y devuelven un vacío indistinguible de un resultado "
                    "legítimo. Esta lista solo puede ENCOGER."
                ),
                "sites": sitios,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "ok": True,
        "tool": "vault_blame_audit",
        "frozen": len(sitios),
        "path": str(BASELINE_PATH),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_blame_audit — AP-51: la tool culpa al dato de su propio fallo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:

  python scripts/vault_blame_audit.py --check
  python scripts/vault_blame_audit.py --check --strict
  python scripts/vault_blame_audit.py --freeze     # tras saldar deuda

Qué cuenta como infracción:

  except Exception:      -> SI. El llamante no distingue ese [] de una nota
      return []             que legitimamente no tiene nada.

  except Exception as e: -> NO. Expone el fallo; el llamante decide.
      return {"ok": False, "error": str(e)}

  except FileNotFoundError:  -> NO. Es un criterio, no una renuncia a saber.
      return []
""",
    )
    parser.add_argument("--check", action="store_true",
                        help="Reporta el estado de la deuda")
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 si la deuda creció")
    parser.add_argument("--freeze", action="store_true",
                        help="Recongela la baseline tras saldar deuda")
    args = parser.parse_args()

    if args.freeze:
        print(json.dumps(freeze(), ensure_ascii=False))
        return 0

    result = scan()
    print(json.dumps(result, ensure_ascii=False))
    if args.strict and not result["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_blame_audit"))
