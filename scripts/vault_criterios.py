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

import vault_baseline
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


# ── Fronteras de lenguaje (v40.19) ───────────────────────────────────────────
#
#: Hasta v40.18 esta tool solo leía `scripts/*.py`. El hueco no era teórico y
#: costó una tanda entera: el criterio «esta tool no tiene script Python» estaba
#: escrito en `cli/registry.py`, en el `.mjs` y en dos regex más, y AP-57 no
#: podía verlo porque una de las copias no era Python. Una norma que parece
#: cubierta y tiene un lado ciego es peor que una sin detector, porque nadie
#: vuelve a mirar.
#:
#: Una frontera se declara con **tres cosas que ya tienen dueño en otro sitio**
#: y no se redefinen aquí:
#:   - `zona_dueña`  → clave de `vault_arch.CONTEXTS`. Qué contexto manda.
#:   - `norma`       → código de `vault_norms.NORM_CATALOG`. Qué se incumple.
#:   - `pasarela`    → el artefacto derivado por el que el criterio DEBE cruzar.
#: `check()` verifica que las tres existen: una frontera que declara una zona o
#: una norma inventada sería el mismo defecto un piso más arriba.
#:
#: La `pasarela` es lo que distingue cruzar de copiar. El `.mjs` nombra cinco
#: variables de entorno y **no** es una copia: lee `env-table.json`, que se
#: deriva de `vault_entorno`. Nombrar la constante no es el delito; decidirla
#: por cuenta propia sí. Es la misma regla que `_importa` aplica en Python, con
#: el import sustituido por la lectura del artefacto — porque un `.mjs` no puede
#: importar un registro Python, y esa imposibilidad es justo lo que crea la
#: frontera.
FRONTERAS: List[Dict[str, Any]] = [
    {
        "frontera": "python->nodejs",
        "lenguaje": "javascript",
        "zona_dueña": "meta_toolkit",
        "zona_ajena": ("mcp/nodejs", "*.mjs"),
        "norma": "AP-57",
        "criterios": [
            {
                "criterio": "que_variables_de_entorno_existen",
                "dueño": "vault_entorno:tabla",
                "senales_de": "entorno",
                "pasarela": "env-table.json",
            },
            {
                "criterio": "que_tools_se_despachan_en_js",
                "dueño": "vault_mcp_catalog:NATIVE_JS_TOOLS",
                "senales": ["vault_backup_base64", "vault_restore_base64"],
                "pasarela": "tools-catalog.json",
            },
        ],
        "por_que": (
            "El servidor MCP es el único camino por el que un agente real llama "
            "a estas tools. Un criterio que allí diverge no rompe ningún test: "
            "rompe al usuario, y en silencio. Ya pasó — siete tools con backend "
            "nativo y `.py` a la vez, `vault_graph` devolviendo `ok: true` sin "
            "escribir el grafo."
        ),
    },
    {
        "frontera": "python->ci",
        "lenguaje": "yaml",
        "zona_dueña": "meta_toolkit",
        "zona_ajena": (".github/workflows", "*.yml"),
        "norma": "AP-57",
        "criterios": [
            {
                "criterio": "que_puertas_hay_que_pasar",
                "dueño": "vault_gate:PUERTAS",
                "senales_de": "puertas",
                "pasarela": "vault_gate.py",
            },
        ],
        "por_que": (
            "Medido al declarar esta frontera: la CI listaba a mano seis puertas "
            "de las diecisiete del registro y no invocaba `vault_gate.py` ni una "
            "vez. Once puertas —changelog, arquitectura, blueprint, ciclos, "
            "criterios entre ellas— no se ejecutaban en ningún PR. El registro "
            "crecía y la lista escrita a mano se quedaba quieta, que es la forma "
            "exacta en que una copia envejece: no se rompe, se atrasa."
        ),
    },
    {
        "frontera": "python->make",
        "lenguaje": "make",
        "zona_dueña": "meta_toolkit",
        "zona_ajena": (".", "Makefile"),
        "norma": "AP-57",
        "criterios": [
            {
                "criterio": "que_puertas_hay_que_pasar",
                "dueño": "vault_gate:PUERTAS",
                "senales_de": "puertas",
                "pasarela": "vault_gate.py",
            },
        ],
        "por_que": (
            "`make check` es lo que ejecuta quien no ha leído CLAUDE.md. Si "
            "nombra puertas sueltas en vez de al registro, publica una idea "
            "distinta de «esto está bien» que la que defiende el repo."
        ),
    },
    {
        "frontera": "python->powershell",
        "lenguaje": "powershell",
        "zona_dueña": "meta_toolkit",
        "zona_ajena": (".", "*.ps1"),
        "norma": "AP-57",
        "criterios": [
            {
                "criterio": "que_variables_de_entorno_existen",
                "dueño": "vault_entorno:tabla",
                "senales_de": "entorno",
                "pasarela": "env-table.json",
            },
        ],
        "por_que": (
            "`bootstrap.ps1` es el primer contacto en Windows. Hoy no nombra "
            "ninguna variable del registro; se declara igual, porque el día que "
            "alguien le añada una entra medida en vez de entrar invisible — que "
            "es lo mismo que `ARBOLES_MEDIDOS` hace con `mcp/python`, hoy vacío."
        ),
    },
]

#: Extensiones que **son** código ejecutable de otro lenguaje. Un fichero así
#: fuera de toda `zona_ajena` declarada es una frontera que nadie mide, y sale
#: como hallazgo: el alcance se declara, no se supone.
EXT_EJECUTABLES = {".mjs", ".js", ".cjs", ".ts", ".ps1", ".sh", ".yml", ".yaml"}

#: Rutas ajenas al toolkit que no son frontera de ningún criterio de este repo.
#: Se listan una a una y con motivo: una exclusión por patrón se traga lo que
#: venga después.
FUERA_DE_FRONTERA = {
    "vault-sandbox": "vault de pruebas: contenido generado, no código del toolkit",
    "docs/sdd": "artefactos SDD derivados",
    # Excluidos de git por sensibles y ajenos al estándar. Sin esta entrada, el
    # plugin de un vault de terceros que vive ahí dentro entraba como
    # `frontera_no_declarada`: un hallazgo verdadero sobre código que este repo
    # ni versiona ni gobierna. Se listan uno a uno y no por patrón porque una
    # exclusión ancha se traga lo que venga después.
    "_datasets": "datos del usuario, fuera de git: código de terceros, no del toolkit",
    "_datasets-reports": "informes derivados de esos datos",
    "_backups-builderx": "copias de un repo ajeno, en solo lectura",
    "node_modules": "dependencias instaladas, no fuente",
}


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


# ── La medida de las fronteras ───────────────────────────────────────────────

REPO = Path(__file__).resolve().parent.parent


def _senales_de(clave: str) -> List[str]:
    """Las señales de un criterio, pedidas al registro que las posee.

    Escribirlas aquí sería reimplementar el criterio dentro del detector de
    criterios reimplementados. Los imports son perezosos a propósito: `vault_gate`
    importa esta tool por su registro de puertas, y subirlos cerraría el ciclo
    que AP-58 mide (el import diferido queda declarado en `ciclos-baseline`).
    """
    if clave == "entorno":
        from vault_entorno import tabla

        return [v["name"] for v in tabla()]
    if clave == "puertas":
        from vault_gate import PUERTAS

        return [p["cmd"][0] for p in PUERTAS]
    raise RuntimeError(f"señales sin registro: {clave}")


def _ficheros_de(zona) -> List[Path]:
    raiz = REPO / zona[0]
    if not raiz.is_dir():
        return []
    return sorted(p for p in raiz.glob(zona[1]) if p.is_file())


def _zonas_declaradas() -> List[Path]:
    fuera = []
    for f in FRONTERAS:
        fuera.extend(_ficheros_de(f["zona_ajena"]))
    return fuera


def _registros_ajenos() -> Dict[str, set]:
    """Zonas y normas que existen de verdad, preguntadas a su dueño."""
    from vault_arch import CONTEXTS
    from vault_norms_catalog import NORM_CATALOG

    return {
        "zonas": set(CONTEXTS),
        "normas": {n["code"] for n in NORM_CATALOG},
    }


def medir_fronteras() -> List[Dict[str, str]]:
    """Criterios reescritos al otro lado de una frontera de lenguaje.

    Tres hallazgos distintos, y conviene no confundirlos:

    - `copia_en_frontera` — el fichero ajeno escribe la señal y **no** lee la
      pasarela: decidió por su cuenta.
    - `frontera_no_declarada` — hay código ejecutable de otro lenguaje que no
      cae en ninguna `zona_ajena`. No es una copia; es un sitio donde una copia
      no se vería. Se reporta porque un alcance que no se declara es un cero
      fabricado, que es lo que AP-58 acababa de destapar en los ciclos.
    - `zona_inexistente` / `norma_inexistente` — la frontera declara algo que su
      registro no reconoce. El detector no puede permitirse el defecto que mide.
    """
    hallazgos: List[Dict[str, str]] = []
    reg = _registros_ajenos()

    for f in FRONTERAS:
        if f["zona_dueña"] not in reg["zonas"]:
            hallazgos.append({"modulo": f["frontera"], "criterio": "zona_inexistente",
                              "senal": f["zona_dueña"], "dueño": "vault_arch:CONTEXTS"})
        if f["norma"] not in reg["normas"]:
            hallazgos.append({"modulo": f["frontera"], "criterio": "norma_inexistente",
                              "senal": f["norma"], "dueño": "vault_norms:NORM_CATALOG"})

        for ruta in _ficheros_de(f["zona_ajena"]):
            try:
                texto = ruta.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                # AP-51: ilegible no es limpio.
                hallazgos.append({"modulo": ruta.name, "criterio": "_no_se_lee",
                                  "senal": "", "dueño": f["frontera"]})
                continue
            for c in f["criterios"]:
                senales = c.get("senales") or _senales_de(c["senales_de"])
                copiadas = [s for s in senales if s in texto]
                if not copiadas:
                    continue
                # Nombrar la constante no es el delito: decidirla lo es. Quien
                # lee la pasarela está cruzando, no copiando.
                if c["pasarela"] in texto:
                    continue
                hallazgos.append({
                    "modulo": str(ruta.relative_to(REPO)).replace("\\", "/"),
                    "criterio": c["criterio"],
                    "senal": copiadas[0],
                    "dueño": c["dueño"],
                    "frontera": f["frontera"],
                    "zona": f["zona_dueña"],
                    "norma": f["norma"],
                    "pasarela": c["pasarela"],
                })

    declaradas = {p.resolve() for p in _zonas_declaradas()}
    for ruta in sorted(REPO.rglob("*")):
        if not ruta.is_file() or ruta.suffix not in EXT_EJECUTABLES:
            continue
        rel = str(ruta.relative_to(REPO)).replace("\\", "/")
        if rel.startswith(".git/") or "/node_modules/" in f"/{rel}":
            continue
        if any(rel == k or rel.startswith(k + "/") for k in FUERA_DE_FRONTERA):
            continue
        if ruta.resolve() in declaradas:
            continue
        hallazgos.append({"modulo": rel, "criterio": "frontera_no_declarada",
                          "senal": ruta.suffix, "dueño": "vault_criterios:FRONTERAS"})
    return hallazgos


def resumen_de_fronteras() -> List[Dict[str, Any]]:
    """Cada frontera con su zona, su norma y lo que cubre de verdad.

    Se publica en el envelope porque «verde» sin esto no dice cuánto se miró.
    """
    return [
        {
            "frontera": f["frontera"],
            "lenguaje": f["lenguaje"],
            "zona_dueña": f["zona_dueña"],
            "zona_ajena": f"{f['zona_ajena'][0]}/{f['zona_ajena'][1]}",
            "norma": f["norma"],
            "criterios": [c["criterio"] for c in f["criterios"]],
            "pasarelas": sorted({c["pasarela"] for c in f["criterios"]}),
            "ficheros": len(_ficheros_de(f["zona_ajena"])),
        }
        for f in FRONTERAS
    ]


def _firma(h: Dict[str, str]) -> str:
    return f"{h['modulo']}::{h['criterio']}"


def _baseline() -> List[str]:
    """superseded_by: vault_baseline.cargar (v40.24).

    Esta era una de las tres copias literales, y la que peor sienta: la tool que
    publica AP-57 tenía el criterio de «cómo se lee una baseline» copiado de
    `vault_fuente_unica`. Se conserva la función —la llaman `check` y `freeze`—
    con el cuerpo reducido a delegación.
    """
    return vault_baseline.cargar(BASELINE, "sitios", "AP-57")


def check() -> Dict[str, Any]:
    hallazgos = medir() + medir_fronteras()
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
        # Las fronteras de lenguaje, con su zona y su norma (v40.19). Se
        # publican aunque estén limpias: el alcance es la mitad del dato.
        "boundaries": resumen_de_fronteras(),
        "boundaries_total": len(FRONTERAS),
        "boundary_files": len(_zonas_declaradas()),
        "copies": hallazgos,
        "copies_total": len(hallazgos),
        "baseline_size": len(base),
        "new_copies": nuevos,
        "resolved_since_baseline": resueltos,
        "hint": (
            "Se salda importando al dueño —o leyendo la pasarela, al otro lado "
            "de una frontera—, no ampliando la baseline. Verde aquí no prueba "
            "que no haya copias: prueba que no hay copias de la forma que esta "
            "tool sabe reconocer, y en Python solo en los `modules_measured` que "
            "nombran `*.md` — los `modules_skipped` no los mira nadie. En las "
            "fronteras la señal es el literal en el fichero ajeno: un `.mjs` que "
            "reimplemente la decisión sin escribir la constante tampoco se ve."
        ),
    }


def freeze(admitir_nuevos: bool = False) -> Dict[str, Any]:
    hallazgos = medir() + medir_fronteras()
    firmas = sorted({_firma(h) for h in hallazgos})
    base = set(_baseline())
    nuevos = sorted(set(firmas) - base)
    # Sin `and base`: una baseline vacía no es permiso para congelar la
    # primera deuda en silencio (ver la misma corrección en vault_fuente_unica).
    if nuevos and not admitir_nuevos:
        return vault_baseline.negativa(
            "vault_criterios", "freeze", "new_copies", nuevos,
            "Importa al dueño. Si de verdad hay que congelar deuda nueva, "
            "`--freeze --admitir-nuevos` la lista aquí.")
    vault_baseline.escribir(
        BASELINE, "sitios", "AP-57",
        "Copias de un criterio con dueño que ya estaban cuando nació AP-57. "
        "Solo puede encoger: una copia nueva se arregla, no se congela.",
        firmas)
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
