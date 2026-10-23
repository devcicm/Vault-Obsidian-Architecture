#!/usr/bin/env python3
"""vault_norms_coherence — AP-55: el catálogo de normas se certifica a sí mismo.

`NORM_CATALOG` declara, por norma, qué tools la hacen cumplir (`tools_enforcing`)
y cuáles la detectan (`tools_detecting`). Esos dos campos se escriben a mano y
**nada los contrasta contra lo que las tools hacen**. El resultado medido en la
tanda de v40.10: 47 afirmaciones de cobertura sin una sola línea de código que
nombre la norma que dicen aplicar. `AP-05` —severidad `critical`— declara
`vault_graph_inspect` como detector, y esa tool no menciona AP-05 en ninguna parte.

Lo caro no es la lista. Es que el guard que existía para detectar normas mudas
—`vault_voice.coverage()`, el guard de AP-43— comprueba que una norma tenga
`tools_enforcing` o `tools_detecting` **leyendo `tools_enforcing` y
`tools_detecting`**. Verifica el catálogo contra el catálogo, así que da verde
sobre las 47 y es estructuralmente incapaz de verlas. Es AP-44 cometido dentro
del guard, la misma forma exacta que el test de cruces de v40.8 y que el cero de
AP-52 medido sobre un subconjunto en v40.9. Tres veces el mismo error en tres
sitios distintos: el criterio de verificación salía del propio objeto verificado.

    python scripts/vault_norms_coherence.py --check           # las cinco medidas
    python scripts/vault_norms_coherence.py --check --strict  # exit 1 si algo falla
    python scripts/vault_norms_coherence.py --freeze          # recongela la traza

## Qué mide, y con qué criterio

Siete comprobaciones. Cinco son exactas y nacen en cero; dos llevan baseline.

**C1 — el enforcer nombrado existe.** Un valor de `tools_*` tiene que resolver
contra algo real. `"vault_norms --audit"` no resolvía: mezcla la tool con el flag
y ningún consumidor puede buscarlo en `mapa_de_grupos()`. Eran 54 entradas; el
flag no es parte de la identidad de la tool y se ha retirado del catálogo.

Quedan siete valores que **no** son tools y no por error: `vault_io.atomic_write_text`
y `vault_io.assert_within_vault` son los helpers donde AP-46 y AP-36 se cumplen
de verdad, `vault_errors` es donde vive el contrato de AP-43, y `vault_mcp_catalog`
es meta-toolkit que el catálogo MCP no se expone a sí mismo. Se admiten
verificando que existen —módulo en `scripts/`, símbolo definido allí— y se
publican aparte en `non_catalog_enforcers`, informativo y no fallo. Obligarles a
nombrar una tool solo conseguiría una afirmación que resuelve y es falsa.

**C2 — la afirmación tiene traza (baseline).** Que el módulo de la tool nombrada
mencione el código de la norma. Esto **no demuestra enforcement** y no se
presenta como si lo hiciera: `vault_write` podría rechazar AP-12 sin escribir
nunca la cadena `"AP-12"`. Lo que demuestra es lo contrario, que es lo útil: si
el código no nombra la norma en ninguna parte, nadie puede seguir la afirmación
hasta el sitio que la cumple, y la cobertura publicada no es verificable por
quien la lee. Declararlo así importa — un guard que prometiera medir enforcement
real sería justo la afirmación no falsable que AP-37 persigue.

**C3 — el enforcement concuerda con los campos.** `guard` exige
`tools_enforcing` no vacío, `audit` exige `tools_detecting`, `guard+audit` los
dos, `recommended` es solo para patrones y `manual` está prohibido (regla 5).
Nace en cero: fija una invariante que hoy se cumple por costumbre.

**C4 — la severidad no contradice a la penalización.** `vault_audit.PENALIZACIONES`
pesa cada norma en el healthIndex. Si el catálogo dice que A es más grave que B
y el audit penaliza menos a A, hay dos registros canónicos afirmando lo contrario
sobre el mismo par. Destapó AP-22 (`critical`, 2/unidad, tope 5) frente a AP-24
(`high`, 5/unidad, tope 15), invertidos seis versiones; AP-22 pasó a `medium`,
que es lo que el código que la aplica venía diciendo (regla 3).

El criterio se estrechó dos veces al medirlo. Primero a **la misma familia**: sin
eso salían diez pares que solo comparaban dos escalas distintas del healthIndex.
Después a exigir la inversión en **las dos** medidas del peso, por unidad y tope:
AP-14 (`critical`, 2/unidad, tope 20) frente a AP-24 invierte una y no la otra,
y eso es una ponderación deliberada —mucho peso acumulado, poco por unidad—, no
una contradicción. AP-22 frente a AP-24 invertía las dos.

**C5 — la distinción entre dos normas es recíproca.** `distinguido_de` declara,
en la norma A, qué la separa de B. C5 exige que B declare lo simétrico: si solo
lo dice A, quien llegue leyendo B no ve la diferencia, que es exactamente cómo
AP-22 y AP-24 pasaron seis versiones describiendo el mismo defecto mientras el
código ya las separaba sin ambigüedad. Se comprueba también que el otro código
exista y que el discriminador no esté vacío.

Lo que C5 **no** hace, dicho para que nadie lo suponga: no descubre por su cuenta
qué dos normas se solapan. Tres borradores lo intentaron —dos códigos en el mismo
módulo, luego en la misma función, luego etiquetando registros de la misma forma—
y los tres devolvían decenas de pares de `vault_audit` y `vault_write` consigo
mismos, que son los orquestadores y acumulan todas las normas del informe porque
lo arman entero, no porque duden. Detectar solapamiento semántico entre normas es
un problema abierto; C5 verifica la distinción **una vez que alguien la declara**.
Los borradores quedan en `_codigos_que_compiten_por_hallazgo()`, sin llamar, como
registro de lo intentado y por qué no converge.

**C7 — la norma dice de qué se distingue (baseline, AP-60).** C5 tiene un hueco
que no es un descuido sino su forma: itera sobre `distinguido_de`, así que **solo
mira a quien ya declaró algo**. Medido en v40.21: 13 normas de 71 declaraban
alguna distinción, y las otras 58 estaban fuera del alcance del guard por no
haber hablado. El incentivo estaba invertido — declarar una distinción obliga a
editar la otra norma para que devuelva la simétrica, y callarse sale gratis. Es
la forma exacta que este repo prohíbe en `cobertura_descubierta`: declararse
honestamente no puede salir más caro que callarse.

C7 mide **por norma, no por par**, y esa elección es el punto entero. Qué dos
normas se solapan sigue sin saberlo medir nadie —los tres borradores de arriba, y
un cuarto en v40.21 que emparejaba por categoría más tool compartida y del que
**59 de 68 pares eran otra vez `vault_audit`, `vault_write` y `vault_norms`
consigo mismos**—. Lo decidible sin interpretar es si la norma dijo algo alguna
vez: `distinguido_de` con contenido, o `distincion_no_aplica` con el motivo
escrito. El silencio no es una tercera opción. Una norma nueva **no se congela**:
se le escribe la distinción, igual que la capa 4 del plano exige test a la norma
que estrena.

**C9 — severidad, tipo, versión y vigencia no se contradicen.** Cuatro
incongruencias decidibles leyendo una sola norma:

- una norma `critical` con enforcement `recommended`: nadie la hace cumplir;
- un patrón con severidad, o un antipatrón sin ella (`N/A`): la severidad
  califica el daño de una ocurrencia, y un patrón no ocurre como daño;
- una `introduced_version` posterior a la versión vigente;
- una norma con `superseded_by` que sigue nombrando tools que la hacen cumplir:
  la no-derogación conserva su contrato, no su enforcement.

El catálogo no tiene hoy ninguna norma sustituida, así que la cuarta mira un
universo vacío; se publica `superseded_norms_total` para que ese cero se lea
como lo que es y no como una comprobación superada (AP-60).

**C10 — la máquina de estados y quien la describe.** Lo que ya vigilan los tests
de `STATUS_TRANSITIONS` —que cubre el vocabulario, que todo estado es alcanzable
y que sinónimos y dominios aterrizan en el canónico— no se repite aquí. C10
mide lo que nadie cruzaba:

- un estado desde el que no se llega a ningún terminal: la nota queda atrapada;
- una transición de un estado a sí mismo, que no es una transición;
- una máquina sin ningún estado terminal;
- un ciclo de `LIFECYCLE_REGISTRY` que describe el mismo eje que el vocabulario
  de dominio de su tool, pero se queda con una parte. Iguales es coherente;
  disjuntos es otro eje —riesgo publica el tratamiento, no el estado—; un
  solapamiento parcial es el SDD publicando una máquina que la tool no tiene.

**C8 — un sanador no dispara el detector de otra norma.** `SANADORES` dice qué
tool repara qué normas, pero nadie comprobaba que reparar A no estrenara
hallazgos de B. C8 tiene dos mitades. La **estática** está en la puerta: todo
sanador declara en `SANACION_EN_LOTE` cómo se ejecuta sobre un vault entero, o en
`SANADORES_SIN_LOTE` por qué no se puede. La **dinámica** es `--colisiones`:
- copia el vault autodetectado a un temporal y nunca escribe en el origen;
- ejecuta cada sanador sobre una copia fresca y compara `by_norm` de
  `vault_norms --audit` antes y después;
- una norma ajena que sube es una colisión, y una propia que sube es un sanador
  que empeora lo que repara.

Tarda decenas de segundos en el sandbox y decenas de minutos en un vault ajeno
de cientos de notas —su watchdog lo deriva `limite_de_la_tool`—, por eso no
está en la puerta: su cifra se registra
como la métrica observada `colisiones_de_sanadores`. Dos límites, publicados en
el envelope:
- solo ve las normas que `vault_norms --audit` emite;
- un sanador que no cambió nada no prueba nada (`healers_idle`).
"""

import argparse
import ast
import json
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

sys.path.insert(0, str(Path(__file__).parent))

import vault_baseline
import vault_grafo_import
import vault_io
import vault_norms_catalog
import vault_subproceso
from vault_errors import TOOL_TIMEOUT_SECONDS, emit_error, wrap_main
from vault.kernel import procesos_git
from vault_version import CURRENT_VERSION
from vault_vocabulario import mapa

SCRIPTS_DIR = Path(__file__).resolve().parent
BASELINE = SCRIPTS_DIR / "norms-coherence-baseline.json"
#: C7 (AP-60). Separada de la de C2 a propósito: son dos deudas distintas y
#: mezclarlas haría que saldar una moviera el conteo de la otra.
BASELINE_DISTINCION = SCRIPTS_DIR / "norms-distincion-baseline.json"

#: Orden de gravedad. El **orden** es del punto de uso —C4 necesita comparar
#: severidades con números y nadie más lo necesita—, pero **qué términos
#: existen** no es suyo: eso lo dice el vocabulario `severidad`. `mapa()` lo
#: comprueba al importarse, así que un término nuevo del registro sin peso aquí
#: revienta al cargar el módulo en vez de caer en un `0` silencioso que haría a
#: C4 tratarlo como el menos grave de todos. Escribir el dict a secas era copiar
#: el vocabulario dentro del guard que persigue las copias.
GRAVEDAD = mapa("severidad", {"critical": 4, "high": 3, "medium": 2, "low": 1})
#: C9. La severidad de un patrón: no califica un daño, y el catálogo lo
#: escribe así en los seis patrones desde que existen.
SIN_SEVERIDAD = "N/A"

#: Combinaciones válidas de `enforcement` → campos que no pueden estar vacíos.
#:
#: `recommended` exige `tools_del_patron` y no `tools_detecting`: un patrón no se
#: detecta, se sigue. Los seis PAT-x declaraban sus tools en `tools_detecting` y
#: eso hacía que C2 les exigiera una traza que no tiene sentido pedirles —el
#: patrón no es un hallazgo que ninguna tool etiquete—. Ocho de las 47
#: afirmaciones sin traza eran este error de categoría, no deuda.
EXIGE_CAMPOS = {
    "guard": ("tools_enforcing",),
    "audit": ("tools_detecting",),
    "guard+audit": ("tools_enforcing", "tools_detecting"),
    "recommended": ("tools_del_patron",),
}

#: La única forma de tener el campo vacío sin que C3 lo marque: decir por qué.
#:
#: Cuatro normas —AP-01, AP-04, AP-05 y AP-08— no las detecta nadie. Antes eso se
#: escondía nombrando una tool que no las aplica, que es peor que el hueco:
#: `AP-05` es `critical` y publicaba `vault_graph_inspect` como detector. Con el
#: campo vacío a secas el hueco quedaría igual de mudo, así que la única salida
#: es declararlo con motivo escrito, y `descubiertas()` lo publica en una lista
#: que se lee de un vistazo. **No es una exención**: es la deuda con nombre.
CAMPO_DESCUBIERTA = "cobertura_descubierta"
#: C7 (AP-60). La exención honesta: la norma declara que no se confunde con
#: ninguna, y escribe por qué. El silencio no es una tercera opción.
CAMPO_SIN_DISTINCION = "distincion_no_aplica"

#: C8. Cómo se ejecuta cada sanador de `SANADORES` sobre un vault entero. El
#: primer elemento es el script; `{root}` se sustituye por la copia. La raíz llega
#: también por `VAULT_ROOT` con `VAULT_STRICT_ROOT=1`, así que un sanador que
#: autodetecta no puede caer en otro vault.
SANACION_EN_LOTE: Dict[str, tuple] = {
    "vault_fix_brackets": ("vault_fix_brackets.py", "--apply", "--include-sandbox"),
    "vault_frontmatter_heal": ("vault_frontmatter_heal.py", "--apply"),
    "vault_frontmatter_completar": ("vault_frontmatter_completar.py", "--apply"),
    "vault_project": ("vault_project.py", "--heal", "--apply"),
    "vault_norms_engine": ("vault_norms.py", "--heal-ap46", "--apply-heal", "--root", "{root}"),
    "vault_graph_fix": ("vault_graph_fix.py", "--root", "{root}", "--apply", "--auto-fix-safe"),
    "vault_mermaid_check": ("vault_mermaid_check.py", "--fix", "--json"),
}
#: C8. Los sanadores sin modo de lote, con el motivo escrito.
SANADORES_SIN_LOTE: Dict[str, str] = {
    "vault_supersede": (
        "sustituye una nota concreta por otra (--path y --by): no hay lote que "
        "ejecutar sin decidir antes qué nota manda, y eso no lo decide una medida"),
}

RE_CODIGO = re.compile(r"\b(?:AP|PAT|SP|CN)-\d+\b")


def _catalogo() -> List[Dict[str, Any]]:
    from vault_norms import NORM_CATALOG

    return NORM_CATALOG


def _tools_del_catalogo() -> Dict[str, Dict[str, Any]]:
    from vault_mcp_catalog import mapa_de_grupos

    return mapa_de_grupos()


def _penalizaciones() -> Dict[str, int]:
    """`{código de norma: puntos por unidad}` según `vault_audit.PENALIZACIONES`.

    Es un puerto de lectura hacia el contexto de salud: el peso lo declara quien
    lo aplica. Copiarlo aquí sería estrenar la segunda fuente de verdad que este
    módulo existe para perseguir.
    """
    from vault_audit_catalog import PENALIZACIONES

    salida: Dict[str, Dict[str, Any]] = {}
    for p in PENALIZACIONES:
        norma = p.get("norma")
        if norma:
            salida[norma] = {
                "por_unidad": p.get("por_unidad", 0),
                "tope": p.get("tope", 0),
                "familia": p.get("familia"),
            }
    return salida


def _penalizaciones_crudas() -> List[Dict[str, Any]]:
    """El registro entero, sin filtrar por norma — es lo que C6 necesita ver.

    `_penalizaciones()` devuelve solo las que declaran norma, y esa es
    exactamente la mitad que C6 no puede mirar: el hueco vive en las que no la
    declaran. Leer el registro dos veces con dos criterios es deliberado y está
    dicho aquí para que nadie las unifique creyendo que son la misma lectura.
    """
    from vault_audit_catalog import PENALIZACIONES

    return PENALIZACIONES


def _fuente(tool: str) -> str:
    """El código de una tool, incluidos los módulos en los que se partió.

    Una tool sigue siendo una cuando su fichero se trocea. `vault_norms` se
    partió en v40.26 en fachada + `vault_norms_catalog` + `vault_norms_engine`,
    y de golpe diecisiete afirmaciones del catálogo se volvieron «sin traza»:
    el código que nombra la norma seguía existiendo, había cambiado de fichero.
    Declarar el reparto a mano habría envejecido a la siguiente partición
    (AP-47), así que **se deriva**: se leen los módulos hermanos que la propia
    fachada importa a nivel superior. Si mañana el motor se parte en dos, la
    traza sigue sola; si un módulo deja de importarse, deja de contar, que es
    justo lo que debe pasar.
    """
    # Un alias del puente (deuda #12) no tiene código: se lee el dueño.
    ruta = vault_grafo_import.fuente_de(tool)
    if not ruta.is_file():
        return ""
    fuente = ruta.read_text(encoding="utf-8", errors="ignore")

    try:
        arbol = ast.parse(fuente)
    except SyntaxError:
        return fuente
    for nodo in arbol.body:
        if not isinstance(nodo, ast.ImportFrom) or not nodo.module:
            continue
        # Solo hermanos: `vault_norms` recoge `vault_norms_engine`, nunca
        # `vault_io`. Importar a otro no es partirse en él.
        if not nodo.module.startswith(f"{tool}_"):
            continue
        parte = vault_grafo_import.fuente_de(nodo.module)
        if parte.is_file():
            fuente += "\n" + parte.read_text(encoding="utf-8", errors="ignore")
    return fuente


def _sin_cabecera(fuente: str) -> str:
    """El módulo sin su docstring de cabecera.

    C2 buscaba el código de la norma en el fichero entero, así que nombrarla en
    la cabecera saldaba la afirmación. La baseline de esta misma medida dice
    desde v40.11 que eso no vale —«en la función que la cumple, no en la
    cabecera del módulo, que pasa la medida sin llevar a nadie al sitio»— y
    hasta v40.16 la regla estaba escrita y no medida. Hoy no cambia ningún
    veredicto: las afirmaciones vivas nombran la norma en el cuerpo. Se cierra
    ahora precisamente por eso, mientras es gratis.

    Los comentarios dentro de una función siguen contando: la medida es traza,
    no enforcement, y eso ya está dicho en el `hint`.
    """
    try:
        doc = ast.get_docstring(ast.parse(fuente))
    except (SyntaxError, ValueError):
        return fuente
    return fuente.replace(doc, "", 1) if doc else fuente


def _sitio_de_modulo(valor: str) -> str:
    """Resuelve un enforcer que **no** es una tool del catálogo, o `""`.

    Cuatro afirmaciones del catálogo no nombran una tool y no por error:
    `vault_io.assert_within_vault` y `vault_io.atomic_write_text` son los helpers
    donde AP-36 y AP-46 se cumplen de verdad, `vault_errors` es donde vive el
    contrato de AP-43, y `vault_mcp_catalog` es una tool del meta-toolkit que el
    catálogo MCP no se expone a sí mismo. Exigirles ser tools obligaría a
    reescribir la afirmación en una que se resuelva pero sea falsa —apuntar a
    `vault_write` porque es una tool— y eso es peor que el hueco.

    Se admiten, pero **verificando que existen**: el módulo tiene que ser un
    fichero de `scripts/` y, si se nombra un símbolo, tiene que estar definido
    allí. Un nombre que no resuelve sigue siendo C1.
    """
    modulo, _, simbolo = valor.partition(".")
    fuente = _fuente(modulo)
    if not fuente:
        return ""
    if not simbolo:
        return fuente
    try:
        arbol = ast.parse(fuente)
    except SyntaxError:
        return ""
    definidos = {
        n.name for n in arbol.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    return fuente if simbolo in definidos else ""


#: Claves de diccionario con las que una tool **etiqueta un hallazgo** con la
#: norma que lo explica. Es el criterio de C5, y es estrecho a propósito: ver el
#: primer borrador, que solo miraba «dos códigos en el mismo módulo», dejó 200
#: pares —`vault_norms` consigo mismo entre ellos, que es el catálogo declarando
#: sus propias normas—. Un guard con ese ruido no se lee, y no leerlo es
#: exactamente cómo AP-22 y AP-24 sobrevivieron seis versiones.
CLAVES_DE_ETIQUETA = ("norm_code", "norma", "norm")


def _codigos_que_compiten_por_hallazgo() -> Dict[str, Set[str]]:
    """`{módulo::función: {códigos que etiquetan el mismo tipo de hallazgo}}`.

    Dos normas solo se confunden si una misma función puede colgarle una u otra
    al **mismo hallazgo**: ahí es donde alguien tiene que saber cuál aplica. Que
    un módulo mencione dos normas en sitios distintos no confunde a nadie.

    Tres estrechamientos, y los tres salieron de medir en vez de suponer:

    1. Solo el valor de una **clave de etiqueta** (`norm_code: "AP-22"`), no
       cualquier literal. Un código en un docstring explica la norma, no la
       emite. Sin esto salían 200 pares, `vault_norms` consigo mismo incluido —
       el catálogo declarando sus propias normas.
    2. Solo dentro de una función. Sin esto, cualquier módulo que toque dos
       normas quedaba marcado.
    3. Solo entre registros de la **misma forma** — mismo conjunto de claves
       hermanas. Sin esto salían `vault_audit::vault_audit` y
       `vault_write::vault_write`, que son los orquestadores: acumulan todas las
       normas del informe porque lo arman entero, no porque duden entre dos. Dos
       etiquetas compiten cuando rellenan el mismo hueco del mismo registro.
    """
    salida: Dict[str, Set[str]] = {}
    for ruta in sorted(SCRIPTS_DIR.glob("vault_*.py")):
        try:
            arbol = ast.parse(vault_grafo_import.fuente_de(ruta.stem)
                              .read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for func in ast.walk(arbol):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            por_forma: Dict[Any, Set[str]] = {}
            for nodo in ast.walk(func):
                if not isinstance(nodo, ast.Dict):
                    continue
                forma = frozenset(
                    k.value for k in nodo.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)
                )
                for clave, valor in zip(nodo.keys, nodo.values):
                    if (
                        isinstance(clave, ast.Constant)
                        and clave.value in CLAVES_DE_ETIQUETA
                        and isinstance(valor, ast.Constant)
                        and isinstance(valor.value, str)
                        and RE_CODIGO.fullmatch(valor.value)
                    ):
                        por_forma.setdefault(forma, set()).add(valor.value)
            compiten = {c for cs in por_forma.values() if len(cs) > 1 for c in cs}
            if compiten:
                salida[f"{ruta.stem}::{func.name}"] = compiten
    return salida


def _cargar_baseline() -> Set[str]:
    if not BASELINE.exists():
        return set()
    datos = json.loads(BASELINE.read_text(encoding="utf-8"))
    return {c["claim"] for c in datos.get("claims", []) if isinstance(c, dict)}


def _cargar_baseline_distincion() -> Set[str]:
    if not BASELINE_DISTINCION.exists():
        return set()
    datos = json.loads(BASELINE_DISTINCION.read_text(encoding="utf-8"))
    return {c["norm"] for c in datos.get("normas", []) if isinstance(c, dict)}


def normas_mudas(catalogo: List[Dict[str, Any]]) -> List[str]:
    """AP-60 — C7: normas que no dicen nada sobre de qué se distinguen.

    Se indexa por código de norma y no por par: **qué dos normas se solapan no
    lo sabe medir nadie** —está escrito arriba, en la nota de C5, y tres
    borradores lo confirmaron—. Lo que sí es decidible sin interpretar es si la
    norma dijo algo alguna vez. Se admiten las dos formas honestas: declarar
    `distinguido_de` con contenido, o declarar `distincion_no_aplica` con el
    motivo escrito. Lo que no se admite es el silencio, que es lo único que C5
    no podía ver.
    """
    mudas = []
    for norma in catalogo:
        tiene = any((t or "").strip() for t in (norma.get("distinguido_de") or {}).values())
        exime = (norma.get(CAMPO_SIN_DISTINCION) or "").strip()
        if not tiene and not exime:
            mudas.append(norma["code"])
    return mudas


def _clave_de_version(version: str) -> tuple:
    """`v40.10` → (40, 10). Solo ordena; una forma que no entiende es C9."""
    return tuple(int(x) for x in version.lstrip("v").split("."))


def incongruencias_de_severidad(catalogo: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """C9 — lo que una norma dice de sí misma no puede contradecirse."""
    vigente = _clave_de_version(CURRENT_VERSION)
    problemas: List[Dict[str, str]] = []
    for norma in catalogo:
        codigo, severidad = norma["code"], norma.get("severity")
        enforcement = norma.get("enforcement")
        if severidad == "critical" and enforcement == "recommended":
            problemas.append({"norm": codigo, "problem": (
                "severity=critical con enforcement=recommended: nadie la hace cumplir")})
        es_patron = norma.get("type") == "pattern"
        if es_patron and severidad != SIN_SEVERIDAD:
            problemas.append({"norm": codigo, "problem": (
                f"patrón con severity={severidad!r}: un patrón no califica un daño")})
        if not es_patron and severidad not in GRAVEDAD:
            problemas.append({"norm": codigo, "problem": (
                f"antipatrón con severity={severidad!r}, fuera del vocabulario")})
        introducida = norma.get("introduced_version")
        if introducida:
            try:
                futura = _clave_de_version(introducida) > vigente
            except ValueError:
                problemas.append({"norm": codigo, "problem": (
                    f"introduced_version={introducida!r} no es una versión")})
            else:
                if futura:
                    problemas.append({"norm": codigo, "problem": (
                        f"introduced_version={introducida} posterior a la vigente "
                        f"{CURRENT_VERSION}")})
        if norma.get("superseded_by") and norma.get("tools_enforcing"):
            problemas.append({"norm": codigo, "problem": (
                f"superseded_by={norma['superseded_by']} y aún nombra tools_enforcing: "
                "lo sustituido conserva su contrato, no su enforcement")})
    return problemas


def incoherencias_del_ciclo(
    transiciones: Dict[str, Set[str]],
    lifecycle: List[Dict[str, Any]],
    dominios: Dict[str, Any],
) -> List[Dict[str, str]]:
    """C10 — la máquina de estados no atrapa, y quien la publica no la recorta."""
    problemas: List[Dict[str, str]] = []
    terminales = {e for e, salidas in transiciones.items() if not salidas}
    if not terminales:
        problemas.append({"state": "*", "problem": "ningún estado terminal: no se sale nunca"})
    for estado, salidas in sorted(transiciones.items()):
        if estado in salidas:
            problemas.append({"state": estado, "problem": "transición de un estado a sí mismo"})
        vistos, pendientes = {estado}, [estado]
        while pendientes:
            for siguiente in transiciones.get(pendientes.pop(), ()):
                if siguiente not in vistos:
                    vistos.add(siguiente)
                    pendientes.append(siguiente)
        if terminales and not vistos & terminales:
            problemas.append({"state": estado, "problem": (
                "desde aquí no se llega a ningún estado terminal")})
    for ciclo in lifecycle:
        if ciclo.get("tool") not in dominios or not ciclo.get("states"):
            continue
        publicados = set(ciclo["states"])
        de_dominio = set(dominios[ciclo["tool"]][1])
        if publicados == de_dominio or not publicados & de_dominio:
            continue
        problemas.append({"entity": ciclo["entity"], "state": "*", "problem": (
            f"el ciclo publicado y el vocabulario de {ciclo['tool']} se solapan "
            f"a medias: faltan {sorted(de_dominio - publicados)}, sobran "
            f"{sorted(publicados - de_dominio)}")})
    return problemas


#: Lo que un sanador tiene para terminar sobre una copia. El watchdog interno de
#: la tool (`VAULT_TOOL_TIMEOUT`) se fija en lo mismo, así que normalmente salta
#: él y la tool devuelve su envelope `TOOL_TIMEOUT`; el del subprocess es la red.
LIMITE_SANADOR_S = 900
#: Lo que tiene cada audit de C8 (dos por sanador: antes y después).
LIMITE_AUDIT_S = 900


def _ejecutar_sanador(tool: str, raiz: Path) -> "int | str":
    argv = [a.replace("{root}", str(raiz)) for a in SANACION_EN_LOTE[tool]]
    # El watchdog de 60 s de VAULT_TOOL_TIMEOUT mataba a frontmatter_completar
    # y graph_fix en una copia de /ans a medio sanar; el límite lo pone aquí
    # el timeout del subprocess, no el de la tool.
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_TOOL_TIMEOUT=str(LIMITE_SANADOR_S))
    try:
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / argv[0]), *argv[1:]], env=env,
            capture_output=True, text=True, encoding="utf-8",
            timeout=LIMITE_SANADOR_S + 60).returncode
    except subprocess.TimeoutExpired:
        # Medido en una copia de /ans: frontmatter_completar no acaba en 900 s.
        # Es un sanador fallido —se publica en `failed_healers`—, no el fin de
        # la medida de los demás.
        return "timeout"


def limite_de_la_tool(argv: List[str]) -> int:
    """Watchdog de la propia tool: el por defecto, salvo en `--colisiones`.

    Medido en copias de /vcloud y /ans: la medida dinámica moría a los 60 s
    (TOOL_TIMEOUT) aunque cada paso tuviera su límite. El suyo se deriva de los
    de sus pasos —sanador, red del subprocess y dos audits por sanador—; un
    VAULT_TOOL_TIMEOUT mayor sigue mandando, como en vault_reindex.
    """
    if "--colisiones" not in argv:
        return TOOL_TIMEOUT_SECONDS
    paso = LIMITE_SANADOR_S + 60 + 2 * LIMITE_AUDIT_S
    return max(TOOL_TIMEOUT_SECONDS, len(SANACION_EN_LOTE) * paso)


def _auditar(raiz: Path) -> Dict[str, Any]:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "vault_norms.py"), "--audit", "--root", str(raiz)],
        env=env, capture_output=True, text=True, encoding="utf-8", timeout=LIMITE_AUDIT_S)
    return json.loads(r.stdout)


#: Normas cuyo hallazgo dice que el audit no pudo leer el frontmatter de la
#: nota: mientras está, todo lo que depende de ese frontmatter queda oculto en
#: esa nota. Medido con C8 en una copia de /ans (ADR-004).
NORMAS_DE_LEGIBILIDAD = ("AP-46",)


def _hallazgos(auditoria: Dict[str, Any]) -> Set[tuple]:
    return {(v.get("norm"), v.get("path")) for v in auditoria.get("violations", [])}


def _huella(raiz: Path) -> Dict[str, str]:
    return {str(p.relative_to(raiz)): hashlib.sha1(p.read_bytes()).hexdigest()
            for p in raiz.rglob("*.md")}


def colisiones_de_sanadores(
    fuente: Path,
    ejecutar: Optional[Callable[[str, Path], "int | str"]] = None,
    auditar: Optional[Callable[[Path], Dict[str, Any]]] = None,
    sanadores: Optional[Dict[str, tuple]] = None,
) -> Dict[str, Any]:
    """C8 — cada sanador sobre una copia fresca de `fuente`; `fuente` no se toca."""
    ejecutar = ejecutar or _ejecutar_sanador
    auditar = auditar or _auditar
    if sanadores is None:
        sanadores = {t: n for t, n in vault_norms_catalog.SANADORES.items()
                     if t in SANACION_EN_LOTE}
    colisiones: List[Dict[str, Any]] = []
    empeoran: List[Dict[str, Any]] = []
    destapadas: List[Dict[str, Any]] = []
    trabajaron: List[str] = []
    ociosos: List[str] = []
    fallidos: List[Dict[str, Any]] = []
    observables: Set[str] = set()
    for tool, propias in sanadores.items():
        temporal = Path(tempfile.mkdtemp(prefix="vault-c8-"))
        try:
            raiz = temporal / "vault"
            # `.locks/` no se copia, por lo mismo que en vault_smoke.
            shutil.copytree(fuente, raiz, ignore=shutil.ignore_patterns(".locks"))
            antes, huella = auditar(raiz), _huella(raiz)
            rc = ejecutar(tool, raiz)
            if rc:
                fallidos.append({"healer": tool, "rc": rc})
            despues = auditar(raiz)
            (trabajaron if _huella(raiz) != huella else ociosos).append(tool)
        finally:
            shutil.rmtree(temporal, ignore_errors=True)
        cuenta_antes, cuenta_despues = antes.get("by_norm", {}), despues.get("by_norm", {})
        observables |= set(cuenta_antes) | set(cuenta_despues)
        h_antes, h_despues = _hallazgos(antes), _hallazgos(despues)
        legibles = ({r for n, r in h_antes if n in NORMAS_DE_LEGIBILIDAD}
                    - {r for n, r in h_despues if n in NORMAS_DE_LEGIBILIDAD})
        for norma in sorted(set(cuenta_despues)):
            previo, ahora = cuenta_antes.get(norma, 0), cuenta_despues[norma]
            if ahora <= previo:
                continue
            nuevas = sorted({r for n, r in h_despues - h_antes if n == norma})
            ajenas = [r for r in nuevas if r not in legibles]
            fila = {"healer": tool, "norm": norma, "before": previo, "after": ahora}
            if nuevas and not ajenas:
                destapadas.append({**fila, "paths": nuevas})
                continue
            fila["paths"] = ajenas
            (empeoran if norma in propias else colisiones).append(fila)
    return {
        "ok": not (colisiones or empeoran or fallidos),
        "tool": "vault_norms_coherence",
        "norm": "AP-55",
        "source": str(fuente),
        "collisions": colisiones,
        "collisions_total": len(colisiones),
        "self_worsening": empeoran,
        # No cuentan para `ok`: el hallazgo ya estaba en una nota que el audit
        # no podía leer, y el sanador lo dejó a la vista al repararla.
        "unmasked": destapadas,
        "failed_healers": fallidos,
        "healers_measured": sorted(sanadores),
        "healers_that_worked": trabajaron,
        # AP-60: un sanador que no cambió nada no prueba que no colisione.
        "healers_idle": ociosos,
        "healers_without_batch": sorted(SANADORES_SIN_LOTE),
        # Solo se ve lo que `vault_norms --audit` emite.
        "observable_norms": sorted(observables),
    }


def scan() -> Dict[str, Any]:
    catalogo = _catalogo()
    tools = _tools_del_catalogo()
    pesos = _penalizaciones()
    por_codigo = {n["code"]: n for n in catalogo}

    c1_inexistentes: List[Dict[str, str]] = []
    c2_sin_traza: List[Dict[str, str]] = []
    c3_incoherentes: List[Dict[str, str]] = []
    no_catalogo: List[Dict[str, str]] = []

    for norma in catalogo:
        codigo = norma["code"]

        # C1 + C2
        for campo in ("tools_enforcing", "tools_detecting"):
            for nombre in norma.get(campo, []):
                if nombre not in tools:
                    if not _sitio_de_modulo(nombre):
                        c1_inexistentes.append(
                            {"norm": codigo, "field": campo, "value": nombre}
                        )
                        continue
                    no_catalogo.append(
                        {"norm": codigo, "field": campo, "value": nombre}
                    )
                # C2 con el criterio de la cara `guard.py`: alguna función de
                # las partes de la tool nombra la norma. Un registro a nivel de
                # módulo —el catálogo que escribe `_desde_paquete("AP-50")`
                # para todas— no es traza: es AP-55 midiéndose con lo medido.
                modulo = nombre.split()[0].split(".")[0]
                if not any(vault_grafo_import.funciones_que_nombran(p, codigo)
                           for p in vault_grafo_import.partes_de(modulo)):
                    c2_sin_traza.append(
                        {
                            "norm": codigo,
                            "field": campo,
                            "tool": nombre,
                            "claim": f"{codigo}::{campo}::{nombre}",
                        }
                    )

        # C3
        enforcement = norma.get("enforcement")
        if enforcement not in EXIGE_CAMPOS:
            c3_incoherentes.append(
                {"norm": codigo, "problem": f"enforcement no permitido: {enforcement!r}"}
            )
        else:
            motivo = (norma.get(CAMPO_DESCUBIERTA) or "").strip()
            for campo in EXIGE_CAMPOS[enforcement]:
                if norma.get(campo):
                    continue
                if motivo:
                    # Declarada descubierta: el hueco está dicho, no tapado.
                    continue
                c3_incoherentes.append(
                    {
                        "norm": codigo,
                        "problem": f"enforcement={enforcement} con {campo} vacío",
                    }
                )
            if motivo and any(norma.get(c) for c in EXIGE_CAMPOS[enforcement]):
                # Lo contrario también miente: declararse descubierta teniendo
                # quien la aplique deja una deuda publicada que ya no existe, y
                # nadie la retira porque nada la contradice.
                c3_incoherentes.append(
                    {
                        "norm": codigo,
                        "problem": (
                            f"declara {CAMPO_DESCUBIERTA} y a la vez nombra tools "
                            f"que la aplican"
                        ),
                    }
                )
        es_patron = norma.get("type") == "pattern"
        if es_patron and enforcement != "recommended":
            c3_incoherentes.append(
                {"norm": codigo, "problem": f"patrón con enforcement={enforcement}"}
            )
        if not es_patron and enforcement == "recommended":
            c3_incoherentes.append(
                {"norm": codigo, "problem": "antipatrón con enforcement=recommended"}
            )

    # C4 — severidad declarada contra peso aplicado.
    #
    # Solo dentro de la **misma familia** de `PENALIZACIONES`. Comparar todos los
    # pares daba diez inversiones, y la mayoría no lo eran: `severity` califica la
    # gravedad de una ocurrencia y `por_unidad` su peso en el healthIndex, dos
    # escalas que solo son conmensurables donde el propio audit las agrupó. Un
    # guard que declare contradicción entre dos escalas distintas hace ruido, y el
    # ruido es cómo AP-22 y AP-24 pasaron seis versiones invertidas sin que nadie
    # lo viera.
    c4_invertidas: List[Dict[str, Any]] = []
    comparables = sorted(c for c in pesos if c in por_codigo)
    for i, a in enumerate(comparables):
        for b in comparables[i + 1:]:
            if pesos[a]["familia"] != pesos[b]["familia"]:
                continue
            ga = GRAVEDAD.get(por_codigo[a].get("severity"), 0)
            gb = GRAVEDAD.get(por_codigo[b].get("severity"), 0)
            pa, pb = pesos[a]["por_unidad"], pesos[b]["por_unidad"]
            ta, tb = pesos[a]["tope"], pesos[b]["tope"]
            if ga == gb or pa == pb or ta == tb:
                continue
            # Se exige la inversión en **las dos** medidas del peso, no solo en
            # `por_unidad`. AP-14 (`critical`, 2/unidad, tope 20) frente a AP-24
            # (`high`, 5/unidad, tope 15) invierte una y no la otra: el audit
            # penaliza menos cada enlace roto porque hay muchos, y aun así les
            # deja costar más en total. Eso es una ponderación, no una
            # contradicción. AP-22 frente a AP-24 invertía las dos.
            if (ga > gb) != (pa > pb) and (ga > gb) != (ta > tb):
                c4_invertidas.append(
                    {
                        "family": pesos[a]["familia"],
                        "norms": [a, b],
                        "severity": [por_codigo[a]["severity"], por_codigo[b]["severity"]],
                        "penalty": [pa, pb],
                    }
                )

    # C5 — el discriminador declarado es recíproco y apunta a algo que existe.
    c5_sin_distincion: List[Dict[str, Any]] = []
    for norma in catalogo:
        a = norma["code"]
        for b, texto in (norma.get("distinguido_de") or {}).items():
            if b not in por_codigo:
                c5_sin_distincion.append(
                    {"norm": a, "problem": f"se distingue de {b}, que no existe"}
                )
                continue
            if not (texto or "").strip():
                c5_sin_distincion.append(
                    {"norm": a, "problem": f"discriminador vacío frente a {b}"}
                )
            if a not in (por_codigo[b].get("distinguido_de") or {}):
                c5_sin_distincion.append(
                    {
                        "norm": a,
                        "problem": (
                            f"{a} se distingue de {b}, pero {b} no se distingue de "
                            f"{a}: quien lea {b} no verá la diferencia"
                        ),
                    }
                )

    # C6 — el espejo de C2: código que pesa sin afirmación que lo sostenga.
    #
    # C2 persigue afirmaciones del catálogo que ningún código respalda. La
    # dirección contraria no la miraba nadie: seis entradas de `PENALIZACIONES`
    # restaban puntos del healthIndex con `norma: None`, así que el vault podía
    # perder salud por algo que el catálogo de normas no nombra en ninguna parte
    # y el usuario no tenía dónde leer qué había hecho mal. O declaran su norma,
    # o declaran que son una métrica sin norma —hay penalizaciones legítimas que
    # no lo son, como la ponderación por CIA— pero eso se escribe, no se deja en
    # `None`, que no distingue «no aplica» de «nadie lo decidió».
    c6_sin_norma: List[Dict[str, Any]] = []
    for entrada in _penalizaciones_crudas():
        norma_de = entrada.get("norma")
        if norma_de:
            if norma_de not in por_codigo:
                c6_sin_norma.append(
                    {
                        "penalty": entrada["id"],
                        "problem": f"penaliza por {norma_de}, que no está en el catálogo",
                    }
                )
            continue
        if not (entrada.get("metrica_sin_norma") or "").strip():
            c6_sin_norma.append(
                {
                    "penalty": entrada["id"],
                    "problem": (
                        "resta salud sin norma que lo sostenga y sin declararse "
                        "métrica sin norma"
                    ),
                }
            )

    descubiertas = [
        {"norm": n["code"], "severity": n.get("severity"), "why": n[CAMPO_DESCUBIERTA]}
        for n in catalogo
        if (n.get(CAMPO_DESCUBIERTA) or "").strip()
    ]

    baseline = _cargar_baseline()
    claims = {c["claim"] for c in c2_sin_traza}
    nuevos = sorted(claims - baseline)
    resueltos = sorted(baseline - claims)

    # C7 (AP-60) — el hueco que C5 no podía ver por construcción.
    #
    # C5 itera sobre `distinguido_de`, así que solo mira a quien ya declaró
    # algo: declarar una distinción obliga a editar la otra norma, y no
    # declarar nada no cuesta nada. El guard cobraba por hablar y regalaba el
    # silencio, que es la forma exacta del incentivo que este repo prohíbe en
    # `cobertura_descubierta` — declararse honestamente no puede salir más caro
    # que callarse. C7 mide la otra dirección: cuántas normas no dicen nada.
    mudas = normas_mudas(catalogo)
    baseline_dist = _cargar_baseline_distincion()
    mudas_nuevas = sorted(set(mudas) - baseline_dist)
    mudas_saldadas = sorted(baseline_dist - set(mudas))

    # C9 — lo que la norma dice de sí misma.
    c9_incongruentes = incongruencias_de_severidad(catalogo)

    # C8, mitad estática — todo sanador dice cómo se ejecuta en lote o por qué no.
    c8_sin_declarar = sorted(
        set(vault_norms_catalog.SANADORES) - set(SANACION_EN_LOTE) - set(SANADORES_SIN_LOTE))

    # C10 — la máquina de estados y los registros que la describen.
    c10_ciclo = incoherencias_del_ciclo(
        vault_norms_catalog.STATUS_TRANSITIONS,
        vault_norms_catalog.LIFECYCLE_REGISTRY,
        vault_norms_catalog.DOMAIN_STATUS_VOCABS,
    )

    ok = not (
        c1_inexistentes or c3_incoherentes or c4_invertidas
        or c5_sin_distincion or c6_sin_norma or nuevos or mudas_nuevas
        or c9_incongruentes or c10_ciclo or c8_sin_declarar
    )
    return {
        "ok": ok,
        "tool": "vault_norms_coherence",
        "norm": "AP-55",
        "norms_total": len(catalogo),
        "unknown_tools": c1_inexistentes,
        # Informativo, no un fallo: enforcers reales que no son tools del
        # catálogo (helpers de `vault_io`, `vault_errors`, `vault_mcp_catalog`).
        # Se publican para que el hueco se vea, no para taparlo.
        "non_catalog_enforcers": no_catalogo,
        # La lista, no solo el conteo: un consumidor que ve "47" y no puede
        # saber cuáles son no puede saldar ninguna, y el test de la baseline
        # tendría que reimplementar la medida para comprobarla — que es AP-05.
        "untraceable_claims": c2_sin_traza,
        "untraceable_claims_total": len(claims),
        "baseline_size": len(baseline),
        "new_untraceable": nuevos,
        "resolved_since_baseline": resueltos,
        "enforcement_incoherent": c3_incoherentes,
        "severity_vs_penalty_inverted": c4_invertidas,
        "indistinguishable_norms": c5_sin_distincion,
        "penalties_without_norm": c6_sin_norma,
        # C7 (AP-60). La lista entera, no solo las nuevas: una deuda que el
        # envelope no publica es una deuda que nadie salda por atrición.
        "norms_without_distinction": mudas,
        "norms_without_distinction_total": len(mudas),
        "distinction_baseline_size": len(baseline_dist),
        "new_norms_without_distinction": mudas_nuevas,
        "settled_norms_without_distinction": mudas_saldadas,
        # Deuda con nombre, no un hueco: las normas que hoy no mide nadie y lo
        # dicen. Se publica siempre —también cuando la lista es corta— porque el
        # sitio donde esto se esconde es justo el que AP-55 persigue.
        "severity_vs_enforcement": c9_incongruentes,
        "status_machine_incoherent": c10_ciclo,
        "healers_undeclared": c8_sin_declarar,
        "superseded_norms_total": sum(1 for n in catalogo if n.get("superseded_by")),
        "uncovered_norms": descubiertas,
        "uncovered_total": len(descubiertas),
        "hint": (
            "Una afirmación sin traza se salda de dos formas honestas: que el código "
            "nombre la norma en el sitio que la aplica, o que el catálogo deje de "
            "afirmar una cobertura que no tiene. Ampliar la baseline es la tercera y "
            "no lo es. Una norma nueva sin distinción (AP-60) no se congela: se "
            "escribe de qué se distingue, o se declara `distincion_no_aplica` con "
            "el motivo. C7 no adivina qué dos normas se solapan — eso no lo sabe "
            "medir nadie; solo comprueba que la norma dijo algo alguna vez."
        ),
    }


def freeze(admitir_nuevos: bool = False) -> Dict[str, Any]:
    """Recongela la traza. Se niega a crecer sin que se lo pidan explícitamente."""
    resultado = scan()
    nuevos = resultado["new_untraceable"]
    if nuevos and not admitir_nuevos:
        # `args=` y no un kwarg suelto: `emit_error` no acepta campos
        # arbitrarios, y pasarlos así reventaba con `TypeError` justo en el
        # camino de negarse — la operación peligrosa se caía en vez de frenar.
        return emit_error(
            "vault_norms_coherence",
            "DEBT_WOULD_GROW",
            f"{len(nuevos)} afirmaciones sin precedente en la baseline",
            args={"new_claims": nuevos},
        )
    # Del mismo scan, no de un segundo recorrido: dos lectores del mismo hecho
    # acaban discrepando en el caso raro, y el caso raro aquí decide qué se
    # congela (AP-05).
    claims = sorted({c["claim"] for c in resultado["untraceable_claims"]})
    vault_baseline.escribir(
        BASELINE, "claims", "AP-55",
        "Afirmaciones de cobertura de NORM_CATALOG que ninguna línea de "
        "código respalda nombrando la norma. Solo puede encoger.",
        [{"claim": c} for c in claims], extra={"norm": "AP-55"},
    )
    return {
        "ok": True,
        "tool": "vault_norms_coherence",
        "frozen": len(claims),
        "admitted_new": nuevos if admitir_nuevos else [],
    }


def freeze_distincion(admitir_nuevos: bool = False) -> Dict[str, Any]:
    """Recongela las normas mudas de C7 (AP-60). Solo encoge sin permiso."""
    resultado = scan()
    nuevas = resultado["new_norms_without_distinction"]
    if nuevas and not admitir_nuevos:
        return emit_error(
            "vault_norms_coherence",
            "DEBT_WOULD_GROW",
            f"{len(nuevas)} normas sin distinción sin precedente en la baseline",
            args={"new_norms": nuevas},
        )
    mudas = sorted(resultado["norms_without_distinction"])
    vault_baseline.escribir(
        BASELINE_DISTINCION, "normas", "AP-60",
        "Normas de NORM_CATALOG que no declaran de qué se distinguen ni "
        "por qué no aplica. Solo puede encoger: se salda escribiendo la "
        "distinción, no ampliando esta lista.",
        [{"norm": c} for c in mudas], extra={"norm": "AP-60"},
    )
    return {
        "ok": True,
        "tool": "vault_norms_coherence",
        "frozen": len(mudas),
        "admitted_new": nuevas if admitir_nuevos else [],
    }


# ─── Disparos de revisión (R5) ───────────────────────────────────────────────
#
# R4 dice cuándo se revisó cada norma; esto dice cuáles toca revisar ya y por
# qué. Dos disparos, los dos decidibles sin interpretar: la cadencia vencida y
# el código que sostiene la norma cambiado en git después de la revisión. El
# segundo no dice que la norma sea falsa: dice que nadie la ha vuelto a leer
# contra ese código. Disparar no es fallar, y ninguna puerta mira esta salida.

#: Los campos del catálogo cuyas tools sostienen una norma. Los sanadores se
#: suman desde `vault_norms_catalog.tools_healing`, que es su registro.
CAMPOS_QUE_SOSTIENEN = ("tools_enforcing", "tools_detecting", "tools_del_patron")


def _fecha_git(ruta: Path) -> Optional[str]:
    """Fecha (AAAA-MM-DD) del último commit que tocó `ruta`, o `None` si git
    no la da: sin git, fuera del repo o sin historia.

    Desde AP-68 la llamada pasa por `vault.kernel.procesos_git`, que juzga el
    verbo (`log`) y fija la codificación del hijo —el `text=True` a secas que
    antes se corregía a mano aquí ya no existe en este repo.
    """
    try:
        salida = procesos_git.ejecutar_git(
            Path(ruta).parent,
            ["log", "-1", "--format=%cs", "--", str(ruta)],
            capture_output=True, timeout=TOOL_TIMEOUT_SECONDS, check=False,
        )
    except (OSError, subprocess.SubprocessError, procesos_git.GitProhibido):
        return None
    fecha = salida.stdout.strip()
    return fecha if salida.returncode == 0 and len(fecha) == 10 else None


def disparos(hoy=None, catalogo: Optional[List[Dict[str, Any]]] = None,
             fecha_de: Optional[Callable[[Path], Optional[str]]] = None) -> Dict[str, Any]:
    """Qué normas toca revisar (R5): por cadencia vencida o por código cambiado.

    `fecha_de(ruta)` da la fecha del último cambio de un fichero; por defecto,
    git. Una tool cuya fecha no se puede medir sale en `codigo_sin_medir` en vez
    de contar como «sin cambios» (AP-60): un cero de quien no pudo mirar no es
    un cero.
    """
    gestion = vault_norms_catalog.gestion_de_normas(hoy=hoy, catalogo=catalogo)
    por_codigo = {n["code"]: n for n in (_catalogo() if catalogo is None else catalogo)}
    fecha_de = fecha_de or _fecha_git
    fechas: Dict[str, Optional[str]] = {}
    sin_fichero: Set[str] = set()
    sin_medir: Set[str] = set()
    salida: List[Dict[str, Any]] = []
    for g in gestion["normas"]:
        norma = por_codigo[g["code"]]
        motivos: List[Dict[str, str]] = []
        if g["vencida"]:
            motivos.append({"disparo": "cadencia", "vence_en": g["vence_en"],
                            "revisado_en": g["revisado_en"]})
        tools: List[str] = []
        for campo in CAMPOS_QUE_SOSTIENEN:
            tools.extend(norma.get(campo) or [])
        tools.extend(vault_norms_catalog.tools_healing(g["code"]))
        for tool in dict.fromkeys(tools):
            # `vault_io.atomic_write_text` es un símbolo: su código es el del módulo.
            modulo = tool.split(".")[0]
            if modulo not in fechas:
                ruta = vault_grafo_import.fuente_de(modulo)
                if not ruta.is_file():
                    sin_fichero.add(tool)
                    fechas[modulo] = None
                    continue
                fechas[modulo] = fecha_de(ruta)
                if fechas[modulo] is None:
                    sin_medir.add(tool)
            cambiado = fechas[modulo]
            if cambiado and cambiado > g["revisado_en"]:
                motivos.append({"disparo": "codigo", "tool": tool, "cambiado_en": cambiado})
        if motivos:
            salida.append({"code": g["code"], "responsable": g["responsable"],
                           "revisado_en": g["revisado_en"], "motivos": motivos})
    return {
        "ok": not gestion["problemas"],
        "tool": "vault_norms_coherence.disparos",
        "hoy": gestion["hoy"],
        "normas_medidas": len(gestion["normas"]),
        "disparos_total": len(salida),
        "disparos": salida,
        "registro_ilegible": gestion["problemas"],
        "codigo_sin_medir": sorted(sin_medir),
        "tools_sin_fichero": sorted(sin_fichero),
        "hint": ("Revisar es leer la norma contra el código que la sostiene y poner "
                 "`revisado_en` con la fecha del día en su norma.py; disparar no es "
                 "fallar y ninguna puerta mira esta lista."),
    }


def scan_claims() -> List[Dict[str, str]]:
    """Solo las afirmaciones sin traza. Delega en `scan()`.

    Tenía cuerpo propio, y ya había divergido: no contemplaba los enforcers que
    no son tools del catálogo, así que medía un conjunto distinto del que
    `--check` publica. Dos implementaciones de la misma medida es AP-05, y aquí
    la discrepancia decidía qué entraba en la baseline.
    """
    return scan()["untraceable_claims"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_norms_coherence — AP-55: coherencia interna del catálogo de normas",
        allow_abbrev=False,
    )
    parser.add_argument("--check", action="store_true", help="C1-C10 (de C8, la mitad estática)")
    parser.add_argument("--strict", action="store_true", help="exit 1 si algo falla")
    parser.add_argument("--freeze", action="store_true", help="recongela la traza")
    parser.add_argument(
        "--admitir-nuevos", action="store_true",
        help="con --freeze: congela también afirmaciones sin precedente",
    )
    parser.add_argument(
        "--freeze-distincion", action="store_true",
        help="recongela las normas sin distinción de C7 (AP-60)",
    )
    parser.add_argument(
        "--colisiones", action="store_true",
        help="C8 dinámica: cada sanador sobre una copia temporal del vault autodetectado",
    )
    parser.add_argument(
        "--disparos", action="store_true",
        help="R5: normas que toca revisar, por cadencia vencida o código cambiado",
    )
    args = parser.parse_args()

    if args.disparos:
        resultado = disparos()
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return 0 if resultado["ok"] else 1

    if args.colisiones:
        resultado = colisiones_de_sanadores(Path(vault_io.get_vault_root()))
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return 1 if (args.strict and not resultado["ok"]) else 0

    if args.freeze_distincion:
        resultado = freeze_distincion(admitir_nuevos=args.admitir_nuevos)
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return 0 if resultado.get("ok") else 1

    if args.freeze:
        resultado = freeze(admitir_nuevos=args.admitir_nuevos)
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return 0 if resultado.get("ok") else 1

    resultado = scan()
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 1 if (args.strict and not resultado["ok"]) else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_norms_coherence",
                       timeout=limite_de_la_tool(sys.argv[1:])))
