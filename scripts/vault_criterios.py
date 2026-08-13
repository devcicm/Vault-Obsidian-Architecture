#!/usr/bin/env python3
"""vault_criterios — un criterio con dueño, reimplementado en la medida (AP-57).

## De dónde sale

v40.12 arregló cuatro defectos de `vault_foreign_check` en una sola tanda, y
los cuatro tenían la misma forma: **el registro canónico existía y la tool no
lo consultaba**. Instantáneas congeladas contadas como notas; documentación del
estándar contada como enlaces rotos; wikilinks dentro de un fence contados como
enlaces; destinos con carpeta resueltos por basename. Cuatro parches y ninguna
norma es exactamente lo que la regla 4 prohíbe: una corrección puntual sin
norma que la sostenga se vuelve a romper, y aquí ya se rompió cuatro veces.

AP-50 dice esto mismo para **patrones regex**: un dueño único. AP-57 es su
generalización a **criterios**: qué es una instantánea, qué es documentación
del estándar, qué es código y no enlace, cómo se resuelve un destino. Un
criterio no es un dato duplicado que alguien note al leer —es una decisión
enterrada en un `if`—, así que la copia sobrevive años sin que nadie la vea.

## Por qué se detecta por la forma literal, y qué NO demuestra

No hay forma general de decidir si dos funciones calculan lo mismo. Lo que sí
se puede decidir es si un módulo **reescribe la constante distintiva del
dueño**: el literal `".history"`, el nombre del manifiesto, la valla ```` ``` ````.
Eso es una señal sintáctica, no una prueba semántica.

Consecuencia dicha antes de que nadie se apoye en ella: un módulo puede
reimplementar un criterio sin repetir ninguna constante y esta tool no lo verá.
**Verde aquí no significa que no haya copias**; significa que no hay copias de
la forma que sabemos reconocer. Es lo mismo que pasa con un linter, y es
preferible a no mirar — el `skip_set` literal de `vault_graph_fix`, que llevaba
versiones divergiendo de `vault_io.SNAPSHOT_DIRS`, cae dentro de lo que sí ve.

El límite tiene un caso medido, y se escribe aquí para que nadie lo intente otra
vez. v40.14 promovió a `vault_lib` dos criterios nuevos —cómo se resuelve un
wikilink (`resolver_destino_wikilink`) y qué destinos resuelven de verdad,
sufijos de ruta **y** `aliases:` (`indice_de_destinos`)— y **no** están en el
registro de abajo: sus constantes distintivas serían `"|"`, `"#"` y `"aliases"`,
que escribe media docena de módulos por motivos legítimos. Registrarlos daba 10
hallazgos nuevos, todos falsos. Una señal que no distingue no es una señal, y
congelarlos en la baseline habría sido comprar el verde con ruido — que es
exactamente lo que la precondición del `"*.md"` existe para evitar. Esos dos
criterios tienen dueño y sus consumidores lo importan; lo que no tienen es una
forma sintáctica de vigilarlo, y decirlo es más honesto que fingirla.

    python scripts/vault_criterios.py --check --strict
    python scripts/vault_criterios.py --freeze     # solo puede encoger
"""

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from vault_errors import emit_error, wrap_main

BASELINE = Path(__file__).parent / "criterios-baseline.json"

#: Cada criterio: quién lo posee, por qué símbolo se consulta, y las constantes
#: que lo delatan cuando alguien lo reescribe. `senales` son literales de
#: cadena; si un módulo que no es el dueño escribe uno y no importa el símbolo,
#: está tomando la decisión por su cuenta.
CRITERIOS_CON_DUENO: List[Dict[str, Any]] = [
    {
        "criterio": "que_es_una_instantanea",
        "dueño": "vault_io",
        "simbolo": "is_snapshot_path",
        "senales": ["vault-backups", ".history", ".trash"],
        "por_que": (
            "Una instantánea congelada no es una nota del vault: contarla infla "
            "el total y repararla la deja de ser instantánea. `vault_graph_fix` "
            "llevaba su propia lista y ya divergía."
        ),
    },
    {
        "criterio": "que_es_documentacion_del_estandar",
        "dueño": "vault_audit",
        "simbolo": "es_documentacion_del_estandar",
        "senales": ["vault-obsidian-architecture.md"],
        "por_que": (
            "Se decide por contenido y no por ubicación desde v40.5, justo "
            "porque comparar el nombre exacto dejaba escapar una copia "
            "archivada con sufijo de versión — que es lo que la no-derogación "
            "pide a los consumidores."
        ),
    },
    {
        "criterio": "que_es_codigo_y_no_enlace",
        "dueño": "vault_lib",
        "simbolo": "strip_code_blocks",
        "senales": ["```"],
        "por_que": (
            "Obsidian no resuelve un wikilink dentro de un fence: lo enseña. "
            "Contarlo eran 87 de 301 «rotos» en un vault real."
        ),
    },
]

#: El dueño escribe sus propias constantes: es su trabajo, no una copia.
DUEÑOS = {c["dueño"] for c in CRITERIOS_CON_DUENO}


def _literales(arbol: ast.AST) -> List[str]:
    return [n.value for n in ast.walk(arbol)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _importa(arbol: ast.AST, modulo: str, simbolo: str) -> bool:
    """¿El módulo consulta al dueño, en vez de decidir por su cuenta?

    Vale tanto `from vault_io import is_snapshot_path` como `import vault_io` +
    `vault_io.is_snapshot_path`: las dos formas llevan al mismo sitio, y exigir
    una sola sería inventarse un estilo.
    """
    for n in ast.walk(arbol):
        if isinstance(n, ast.ImportFrom) and n.module == modulo:
            if any(a.name == simbolo for a in n.names):
                return True
        if isinstance(n, ast.Attribute) and n.attr == simbolo:
            return True
    return False


def _modulos() -> List[Path]:
    aqui = Path(__file__).parent
    return sorted(p for p in aqui.glob("*.py") if p.name != Path(__file__).name)


#: Qué módulos entraron de verdad en la medida y cuáles quedaron fuera por la
#: precondición del `*.md`. Se publica en el envelope: `modules_scanned` decía
#: 125 mientras la medida miraba 31, y un alcance que no se ve no se discute.
_ALCANCE: Dict[str, List[str]] = {"medidos": [], "saltados": []}


def medir() -> List[Dict[str, str]]:
    """Copias de un criterio con dueño, en los módulos que clasifican notas.

    **La precondición del `*.md` es el alcance real de esta tool, y cuesta:**
    de 125 módulos, solo los que nombran ese literal entran en la medida; el
    resto se salta entero. Sin ella el detector marcaría a quien escribe la
    constante por otro motivo legítimo (`vault_restore` nombra `vault-backups`
    porque restaurar de ahí *es* su trabajo), pero el precio es que un módulo
    que clasifique notas sin nombrar `*.md` no lo mira nadie. Los dos números
    salen en el envelope como `modules_measured` / `modules_skipped`.
    """
    _ALCANCE["medidos"] = []
    _ALCANCE["saltados"] = []
    hallazgos: List[Dict[str, str]] = []
    for p in _modulos():
        nombre = p.stem
        try:
            arbol = ast.parse(p.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            # Un módulo que no parsea es un problema, pero no el de esta tool:
            # se salta explícitamente en vez de contarse como limpio (AP-51).
            hallazgos.append({"modulo": nombre, "criterio": "_no_parsea",
                              "senal": "", "dueño": ""})
            continue
        literales = set(_literales(arbol))
        # Un criterio de clasificación solo puede incumplirse donde se
        # clasifican notas. Sin esta condición el detector marca a quien
        # escribe la constante por otro motivo legítimo: `vault_restore`
        # nombra `vault-backups` porque restaurar de ahí *es* su trabajo, y
        # `vault_norms` nombra el manifiesto porque lo edita. Marcarlos sería
        # llenar la baseline de ruido, que es como un guard deja de leerse.
        if "*.md" not in literales:
            _ALCANCE["saltados"].append(nombre)
            continue
        _ALCANCE["medidos"].append(nombre)
        for c in CRITERIOS_CON_DUENO:
            if nombre == c["dueño"] or nombre in DUEÑOS:
                continue
            copiadas = [s for s in c["senales"] if s in literales]
            if not copiadas:
                continue
            if _importa(arbol, c["dueño"], c["simbolo"]):
                continue
            hallazgos.append({
                "modulo": nombre,
                "criterio": c["criterio"],
                "senal": copiadas[0],
                "dueño": f"{c['dueño']}:{c['simbolo']}",
            })
    return hallazgos


def _firma(h: Dict[str, str]) -> str:
    return f"{h['modulo']}::{h['criterio']}"


def _baseline() -> List[str]:
    if not BASELINE.exists():
        return []
    # No se traga el fallo (AP-51): una baseline ilegible leída como vacía
    # estrena la deuda entera como nueva y, en `freeze`, la congela sin que
    # nadie la vea pasar. El fallo de la tool no se presenta como ausencia en
    # el dato. `vault_fuente_unica._baseline()` hace lo mismo, y esta lo hacía
    # al revés siendo el mismo formato.
    try:
        crudo = BASELINE.read_text(encoding="utf-8")
    except OSError as e:
        raise RuntimeError(f"baseline de AP-57 ilegible: {BASELINE} ({e})") from e
    try:
        return json.loads(crudo).get("sitios", [])
    except json.JSONDecodeError as e:
        raise RuntimeError(f"baseline de AP-57 corrupta: {BASELINE} ({e})") from e


def check() -> Dict[str, Any]:
    hallazgos = medir()
    firmas = {_firma(h) for h in hallazgos}
    base = set(_baseline())
    nuevos = sorted(firmas - base)
    resueltos = sorted(base - firmas)
    return {
        "ok": not nuevos,
        "tool": "vault_criterios",
        "norm": "AP-57",
        "action": "check",
        "criterios": len(CRITERIOS_CON_DUENO),
        "modules_scanned": len(_modulos()),
        # El alcance real, no el nominal: la precondición del `*.md` deja fuera
        # a la mayoría, y hasta v40.16 solo se publicaba el total.
        "modules_measured": len(_ALCANCE["medidos"]),
        "modules_skipped": len(_ALCANCE["saltados"]),
        "skip_reason": "sin literal `*.md`: no clasifica notas de forma reconocible",
        "copies": hallazgos,
        "copies_total": len(hallazgos),
        "baseline_size": len(base),
        "new_copies": nuevos,
        "resolved_since_baseline": resueltos,
        "hint": (
            "Se salda importando al dueño, no ampliando la baseline. Verde aquí "
            "no prueba que no haya copias: prueba que no hay copias de la forma "
            "que esta tool sabe reconocer, y solo en los `modules_measured` que "
            "nombran `*.md` — los `modules_skipped` no los mira nadie."
        ),
    }


def freeze(admitir_nuevos: bool = False) -> Dict[str, Any]:
    hallazgos = medir()
    firmas = sorted({_firma(h) for h in hallazgos})
    base = set(_baseline())
    nuevos = sorted(set(firmas) - base)
    # Sin `and base`: una baseline vacía no es permiso para congelar la
    # primera deuda en silencio (ver la misma corrección en vault_fuente_unica).
    if nuevos and not admitir_nuevos:
        return {
            "ok": False, "tool": "vault_criterios", "action": "freeze",
            "error_code": "DEBT_WOULD_GROW", "new_copies": nuevos,
            "recovery": ("Importa al dueño. Si de verdad hay que congelar deuda "
                         "nueva, `--freeze --admitir-nuevos` la lista aquí."),
        }
    BASELINE.write_text(json.dumps({
        "description": (
            "Copias de un criterio con dueño que ya estaban cuando nació AP-57. "
            "Solo puede encoger: una copia nueva se arregla, no se congela."
        ),
        "sitios": firmas,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"ok": True, "tool": "vault_criterios", "action": "freeze",
            "frozen": len(firmas), "admitted_new": nuevos if admitir_nuevos else []}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="vault_criterios — criterios con dueño, reimplementados (AP-57)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--admitir-nuevos", action="store_true")
    args = ap.parse_args()

    if args.freeze and args.check:
        # `emit_error` **construye** el envelope y devuelve el dict; no imprime
        # ni es un exit code. Devolverlo tal cual desde `main` hacía que
        # `wrap_main` lo tomara por un retorno inesperado y publicara
        # `UNEXPECTED_ERROR`: el consumidor recibía «fallo interno» donde el
        # fallo era suyo y tenía arreglo. AP-52 pide el contrato, no solo la
        # llamada.
        env = emit_error("vault_criterios", "CONFLICTING_ARGS",
                         "--freeze y --check piden cosas distintas: o mide o congela")
        env["recovery"] = "elige uno"
        print(json.dumps(env, ensure_ascii=False))
        return 1

    r = freeze(args.admitir_nuevos) if args.freeze else check()
    print(json.dumps(r, ensure_ascii=False))
    return 1 if args.strict and not r["ok"] else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_criterios"))
