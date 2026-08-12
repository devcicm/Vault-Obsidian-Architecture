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

Cinco comprobaciones. Cuatro son exactas y nacen en cero; una lleva baseline.

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
"""

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

sys.path.insert(0, str(Path(__file__).parent))

from vault_errors import emit_error, wrap_main
from vault_vocabulario import mapa

SCRIPTS_DIR = Path(__file__).resolve().parent
BASELINE = SCRIPTS_DIR / "norms-coherence-baseline.json"

#: Orden de gravedad. El **orden** es del punto de uso —C4 necesita comparar
#: severidades con números y nadie más lo necesita—, pero **qué términos
#: existen** no es suyo: eso lo dice el vocabulario `severidad`. `mapa()` lo
#: comprueba al importarse, así que un término nuevo del registro sin peso aquí
#: revienta al cargar el módulo en vez de caer en un `0` silencioso que haría a
#: C4 tratarlo como el menos grave de todos. Escribir el dict a secas era copiar
#: el vocabulario dentro del guard que persigue las copias.
GRAVEDAD = mapa("severidad", {"critical": 4, "high": 3, "medium": 2, "low": 1})

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
    from vault_audit import PENALIZACIONES

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
    from vault_audit import PENALIZACIONES

    return PENALIZACIONES


def _fuente(tool: str) -> str:
    ruta = SCRIPTS_DIR / f"{tool}.py"
    if not ruta.is_file():
        return ""
    return ruta.read_text(encoding="utf-8", errors="ignore")


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
            arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="ignore"))
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
                if nombre in tools:
                    fuente = _fuente(nombre)
                else:
                    fuente = _sitio_de_modulo(nombre)
                    if not fuente:
                        c1_inexistentes.append(
                            {"norm": codigo, "field": campo, "value": nombre}
                        )
                        continue
                    no_catalogo.append(
                        {"norm": codigo, "field": campo, "value": nombre}
                    )
                if codigo not in fuente:
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

    ok = not (
        c1_inexistentes or c3_incoherentes or c4_invertidas
        or c5_sin_distincion or c6_sin_norma or nuevos
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
        # Deuda con nombre, no un hueco: las normas que hoy no mide nadie y lo
        # dicen. Se publica siempre —también cuando la lista es corta— porque el
        # sitio donde esto se esconde es justo el que AP-55 persigue.
        "uncovered_norms": descubiertas,
        "uncovered_total": len(descubiertas),
        "hint": (
            "Una afirmación sin traza se salda de dos formas honestas: que el código "
            "nombre la norma en el sitio que la aplica, o que el catálogo deje de "
            "afirmar una cobertura que no tiene. Ampliar la baseline es la tercera y "
            "no lo es."
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
    BASELINE.write_text(
        json.dumps(
            {
                "norm": "AP-55",
                "description": (
                    "Afirmaciones de cobertura de NORM_CATALOG que ninguna línea de "
                    "código respalda nombrando la norma. Solo puede encoger."
                ),
                "claims": [{"claim": c} for c in claims],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "ok": True,
        "tool": "vault_norms_coherence",
        "frozen": len(claims),
        "admitted_new": nuevos if admitir_nuevos else [],
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
    )
    parser.add_argument("--check", action="store_true", help="las cinco medidas")
    parser.add_argument("--strict", action="store_true", help="exit 1 si algo falla")
    parser.add_argument("--freeze", action="store_true", help="recongela la traza")
    parser.add_argument(
        "--admitir-nuevos", action="store_true",
        help="con --freeze: congela también afirmaciones sin precedente",
    )
    args = parser.parse_args()

    if args.freeze:
        resultado = freeze(admitir_nuevos=args.admitir_nuevos)
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return 0 if resultado.get("ok") else 1

    resultado = scan()
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 1 if (args.strict and not resultado["ok"]) else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_norms_coherence"))
