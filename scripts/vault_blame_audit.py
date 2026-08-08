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

from vault_errors import emit_error, wrap_main
from vault_firma_sitio import (
    cargar_baseline,
    escribir_baseline,
    firmar_todos,
    mapa_de_qualnames,
)

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


DESCRIPCION = (
    "Deuda conocida de handlers amplios que se tragan el fallo propio y "
    "devuelven un vacío indistinguible de un resultado legítimo. Indexada por "
    "firma de sitio (módulo::función::hash del código normalizado), no por "
    "línea: desplazar el sitio no lo convierte en deuda nueva. Esta lista solo "
    "puede ENCOGER."
)


def offenders() -> List[Dict]:
    """Handlers amplios cuya única salida es un vacío indistinguible.

    La clave es la **firma** del sitio y no un contador por módulo: una baseline
    por conteo se puede "saldar" arreglando un sitio y estrenando otro, que es
    exactamente la regresión que este audit existe para ver. `line` se conserva
    como dato informativo —sirve para ir al sitio— pero ya no es la identidad.
    """
    fuera = []
    for path in sorted(SCRIPTS_DIR.glob("vault_*.py")):
        if path.name == "vault_blame_audit.py":
            continue
        try:
            arbol = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        qualnames = mapa_de_qualnames(arbol)
        encontrados = []
        for handler in [n for n in ast.walk(arbol)
                        if isinstance(n, ast.ExceptHandler)]:
            tipos = _tipos_capturados(handler)
            if not (AMPLIAS & set(tipos)):
                continue
            if not handler.body:
                continue
            if all(_es_vacio_indistinguible(s) for s in handler.body):
                encontrados.append((handler, tipos))
        encontrados.sort(key=lambda par: par[0].lineno)
        firmas = firmar_todos(
            (path.name, qualnames.get(id(h), ""), h) for h, _ in encontrados
        )
        for (handler, tipos), firma in zip(encontrados, firmas):
            fuera.append({
                "firma": firma,
                "module": path.name,
                "line": handler.lineno,
                "site": f"{path.name}:{handler.lineno}",  # informativo
                "catches": ",".join(tipos),
            })
    return fuera


def load_baseline() -> List[str]:
    """Las claves congeladas, ordenadas.

    superseded_by: `vault_firma_sitio.cargar_baseline`, que además devuelve el
    esquema y los datos crudos. Se conserva —no-derogación— porque su contrato
    (una lista de claves comparable con los sitios vivos) sigue siendo válido y
    hay consumidores que solo necesitan eso. Lo que cambió es qué **es** una
    clave: antes `módulo:línea`, ahora la firma del sitio.
    """
    firmas, _, _ = cargar_baseline(BASELINE_PATH)
    return sorted(firmas)


def scan() -> Dict:
    actuales = offenders()
    firmas = {o["firma"] for o in actuales}
    baseline, esquema, _ = cargar_baseline(BASELINE_PATH)

    if esquema < 2:
        return emit_error(
            "vault_blame_audit", "MIGRATION_REQUIRED",
            "La baseline está indexada por línea (esquema 1). Migra con "
            "`python scripts/vault_blame_audit.py --migrate` antes de auditar: "
            "leerla como vacía estrenaría la deuda entera como nueva.",
        )

    nuevos = sorted(firmas - baseline)      # deuda que CRECIÓ: es un fallo
    resueltos = sorted(baseline - firmas)   # deuda saldada: hay que recongelar

    return {
        # `ok` solo mira los nuevos: la deuda histórica no bloquea, pero no crece.
        "ok": not nuevos,
        "tool": "vault_blame_audit",
        "norm": "AP-51",
        "schema": esquema,
        "offenders_total": len(actuales),
        "baseline_size": len(baseline),
        "modules_affected": len({o["module"] for o in actuales}),
        "new_offenders": nuevos,
        "resolved_since_baseline": resueltos,
        "offenders": actuales,
    }


def freeze(admitir_nuevos: bool = False) -> Dict:
    """Recongela. Se niega a congelar deuda nueva salvo que se le exija.

    Es la mitad que faltaba. Con el índice por línea, `--freeze` legítimo y
    `--freeze` que esconde deuda recién estrenada se tecleaban igual, y lo único
    que los separaba era que alguien verificase tres condiciones a mano. Ahora
    el desplazamiento ya no genera falsos nuevos, así que **un sitio nuevo es un
    sitio nuevo** y congelarlo exige decirlo en voz alta.
    """
    actuales = offenders()
    baseline, esquema, previos = cargar_baseline(BASELINE_PATH)
    firmas = {o["firma"] for o in actuales}
    nuevos = sorted(firmas - baseline)

    if nuevos and not admitir_nuevos and esquema >= 2:
        return emit_error(
            "vault_blame_audit", "DEBT_WOULD_GROW",
            f"{len(nuevos)} sitio(s) sin precedente en la baseline: congelarlos "
            f"aumentaría la deuda en silencio. Si es deliberado, "
            f"`--freeze --admitir-nuevos`. Sitios: {nuevos}",
        )

    sitios = [{"firma": o["firma"], "visto_en": o["site"]} for o in actuales]
    escribir_baseline(BASELINE_PATH, "AP-51", DESCRIPCION, sitios, previos)
    return {
        "ok": True,
        "tool": "vault_blame_audit",
        "frozen": len(sitios),
        "admitted_new": nuevos if admitir_nuevos else [],
        "path": str(BASELINE_PATH),
    }


def migrate() -> Dict:
    """Traduce la baseline v1 (por línea) a v2 (por firma), sin cambiar la deuda.

    Se niega si el conjunto de `módulo:línea` que ve ahora no coincide **exacto**
    con el congelado. Migrar sobre un árbol que ya divergía convertiría la
    traducción en una amnistía: la deuda nueva entraría en la v2 como si
    siempre hubiera estado ahí, y nadie podría distinguirlo después.
    """
    _, esquema, previos = cargar_baseline(BASELINE_PATH)
    if esquema >= 2:
        return {"ok": True, "tool": "vault_blame_audit",
                "already": True, "schema": esquema}

    actuales = offenders()
    v1_previa = sorted(s for s in previos.get("sites", []) if isinstance(s, str))
    v1_actual = sorted(o["site"] for o in actuales)
    if v1_previa != sorted(set(v1_actual)):
        return emit_error(
            "vault_blame_audit", "MIGRATION_MISMATCH",
            "La baseline v1 no coincide con lo que se mide ahora: "
            f"{len(v1_previa)} congelados vs {len(set(v1_actual))} actuales. "
            "Deja el árbol en verde con la v1 antes de migrar.",
        )

    sitios = [{"firma": o["firma"], "visto_en": o["site"]} for o in actuales]
    escribir_baseline(BASELINE_PATH, "AP-51", DESCRIPCION, sitios, previos)
    return {
        "ok": True, "tool": "vault_blame_audit", "migrated": len(sitios),
        "from_schema": esquema, "to_schema": 2, "path": str(BASELINE_PATH),
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
    parser.add_argument("--admitir-nuevos", action="store_true",
                        help="Con --freeze: congela también sitios sin precedente")
    parser.add_argument("--migrate", action="store_true",
                        help="Traduce una baseline v1 (por línea) a v2 (por firma)")
    args = parser.parse_args()

    if args.migrate:
        resultado = migrate()
        print(json.dumps(resultado, ensure_ascii=False))
        return 0 if resultado.get("ok") else 1

    if args.freeze:
        resultado = freeze(admitir_nuevos=args.admitir_nuevos)
        print(json.dumps(resultado, ensure_ascii=False))
        return 0 if resultado.get("ok") else 1

    result = scan()
    print(json.dumps(result, ensure_ascii=False))
    if args.strict and not result["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_blame_audit"))
