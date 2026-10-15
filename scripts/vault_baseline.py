#!/usr/bin/env python3
"""El fichero de baseline: un dueño, un contrato, una sola negativa a crecer.

Hasta v40.23 había **trece entradas de baseline en doce ficheros** y, de los
diez guards que las leen, **ocho reimplementaban carga y congelado**. Tres de
esos ocho —`vault_criterios._baseline`, `vault_ciclos._baseline`,
`vault_kernel._baseline`— eran literalmente el mismo cuerpo con el nombre de la
norma cambiado, y sus comentarios se citaban entre sí para justificarlo. La
negativa a congelar deuda nueva estaba escrita ocho veces con mensajes de
`recovery` distintos, y `vault_arch.freeze()` ni siquiera tenía
`--admitir-nuevos`: allí la negativa no existía.

Eso es AP-57 con nombre y apellidos, y en el repo que publica la norma. Lo caro
no es la duplicación en sí: es que **el caso raro decide si se congela deuda
nueva**, y ocho lectores del mismo formato acaban discrepando justo ahí. La
baseline v1 leída como vacía —el fallo que `vault_firma_sitio` documenta— no
habría podido ocurrir ocho veces si hubiera habido un solo lector.

## Qué es de aquí y qué no

De aquí: leer el fichero, escribirlo conservando lo que no entiende, comparar
lo medido con lo congelado y **negarse a crecer**. El contrato de `objetivo`
—cuánto debe encoger esta deuda, para cuándo y quién lo revisa— también, porque
un campo repetido en trece ficheros con nueve formas distintas es la novena
copia del criterio, no un campo.

No es de aquí: **qué se mide**. Cada guard sigue siendo el dueño de su hallazgo
y de su firma. Este módulo no sabe qué es un ciclo, un handler ciego ni un
módulo del núcleo, y no debe llegar a saberlo — el día que lo sepa, será él
quien tenga que partirse.

Tampoco es de aquí la firma de sitio: eso es `vault_firma_sitio`, que se queda
con lo suyo. Este módulo trata la firma como una cadena opaca.

## Fan-out cero, a propósito

No importa ningún `vault_*`. Lo consumen guards del meta-toolkit y también
tools que miden vaults, y una dependencia hacia arriba desde aquí invertiría la
dirección que AP-59 vigila. Devuelve dicts planos; el envelope de error lo
compone quien llama, con su `emit_error` y su `recovery`, que es información
suya y no de este módulo.

## Lo que este módulo NO puede evitar

Que una baseline crezca por `--freeze --admitir-nuevos`. La negativa es un
freno con marcha atrás declarada, no un candado: existe porque a veces hay que
congelar deuda nueva, y lo que importa es que quede **listada en el envelope**
en vez de aparecer en el JSON sin que nadie la viera pasar.
"""

import json
import re
import subprocess

import vault_subproceso
from datetime import date, datetime
from pathlib import Path
from typing import (Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set,
                    Tuple, Union)

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Claves donde vive la lista, por fichero. No las decide este módulo: las
#: declara cada guard al llamar. Están aquí solo como documentación del zoo que
#: había —`sites`, `sitios`, `tools`, `claims`, `normas`, `crossings`,
#: `failing`, `uncovered_norms`, `stable`— y que no se unifica a la fuerza:
#: renombrar la clave de una baseline la estrenaría entera como deuda nueva.
CLAVES_CONOCIDAS = (
    "sites", "sitios", "tools", "claims", "normas", "crossings",
    "off_port_crossings", "failing", "uncovered_norms", "stable",
)

#: Campos obligatorios de `objetivo`. Un objetivo sin quién lo revisa y cada
#: cuánto es una cifra a mano (AP-47) — es la precondición que la propia deuda
#: declaraba antes de que el campo existiera.
CAMPOS_OBJETIVO = ("tamano", "fecha_limite", "cadencia_dias", "dueno")

_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class BaselineIlegible(RuntimeError):
    """La baseline existe pero no se puede leer o no es JSON válido.

    Es una excepción y no un `{}` a propósito (AP-51): una baseline ilegible
    leída como vacía estrena la deuda entera como nueva y, en `--freeze`, la
    congela sin que nadie la vea pasar. El fallo de la herramienta no se
    presenta como ausencia en el dato.
    """


# ── Carga ────────────────────────────────────────────────────────────────────

def cargar_datos(path: Path, norma: str) -> Dict[str, Any]:
    """El JSON entero, o `{}` si el fichero no existe.

    Ausente y corrupta son cosas distintas: la primera es legítima —una norma
    recién nacida sin deuda congelada— y la segunda no lo es nunca.
    """
    if not path.exists():
        return {}
    try:
        crudo = path.read_text(encoding="utf-8")
    except OSError as e:
        raise BaselineIlegible(f"baseline de {norma} ilegible: {path} ({e})") from e
    try:
        datos = json.loads(crudo)
    except json.JSONDecodeError as e:
        raise BaselineIlegible(f"baseline de {norma} corrupta: {path} ({e})") from e
    if not isinstance(datos, dict):
        raise BaselineIlegible(
            f"baseline de {norma} con raíz {type(datos).__name__}, se esperaba objeto: {path}")
    return datos


def cargar(path: Path, clave: str, norma: str) -> List[Any]:
    """La lista congelada. Los ítems se devuelven tal cual estén escritos.

    Unos ficheros guardan strings y otros dicts, y este módulo no los uniforma:
    normalizar aquí cambiaría lo que cada guard compara y estrenaría deuda.
    """
    valor = cargar_datos(path, norma).get(clave, [])
    if valor is None:
        return []
    if not isinstance(valor, list):
        raise BaselineIlegible(
            f"baseline de {norma}: `{clave}` es {type(valor).__name__}, se esperaba lista: {path}")
    return valor


def tamano_congelado(valor: Any) -> int:
    """Cuántos elementos congela una baseline, sea cual sea su forma.

    No todas guardan una lista: `field-compat-baseline.json` indexa por tool y
    su valor es un **dict de listas**, así que congela campos, no tools —
    contar las claves publicaría 111 donde hay más de mil, que es la cifra a
    mano de AP-47 escrita por el propio generador. El criterio vive aquí y no
    en `vault_blueprint` porque lo necesitan los dos y era el mismo `if` en dos
    sitios (AP-57).
    """
    if isinstance(valor, dict):
        if valor and all(isinstance(v, list) for v in valor.values()):
            return sum(len(v) for v in valor.values())
        return len(valor)
    if isinstance(valor, list):
        return len(valor)
    return 0


def firmas(path: Path, clave: str, norma: str) -> Set[str]:
    """El conjunto de firmas, para los guards cuya lista son cadenas."""
    return {x for x in cargar(path, clave, norma) if isinstance(x, str)}


# ── La comparación y la negativa ─────────────────────────────────────────────

def comparar(actuales: Iterable[str], congeladas: Iterable[str]) -> Tuple[List[str], List[str]]:
    """`(nuevos, resueltos)`, ambos ordenados.

    Es la única resta del repo entre lo medido y lo congelado. Estaba escrita
    ocho veces, siempre igual, y por eso mismo nadie la miraba.
    """
    a, b = set(actuales), set(congeladas)
    return sorted(a - b), sorted(b - a)


def negativa(tool: str, accion: str, clave_nuevos: str,
             nuevos: Sequence[str], recovery: str) -> Dict[str, Any]:
    """El envelope de `DEBT_WOULD_GROW`, con los nuevos listados.

    `clave_nuevos` y `recovery` los pone quien llama porque son suyos: el nombre
    con el que esa tool llama a sus hallazgos y cómo se saldan. Lo que es de
    aquí es que **siempre se listen** — congelar deuda nueva en silencio es lo
    que este mecanismo existe para impedir.
    """
    return {
        "ok": False, "tool": tool, "action": accion,
        "error_code": "DEBT_WOULD_GROW",
        clave_nuevos: list(nuevos),
        "recovery": recovery,
    }


# ── Escritura ────────────────────────────────────────────────────────────────

def escribir(path: Path, clave: str, norma: str, descripcion: str,
             elementos: Union[Sequence[Any], Mapping[str, Any]],
             extra: Optional[Dict[str, Any]] = None,
             campo_descripcion: str = "description") -> int:
    """Escribe la baseline conservando todo lo que este módulo no entiende.

    Las claves previas que no sean `clave` ni las del contrato se copian tal
    cual: ahí viven `sites_v1_superseded`, `off_port_crossings` y lo que venga
    después. Borrarlas al reescribir sería derogar por descuido — que es como
    la anotación de la migración v1 se perdió una vez, dentro del código
    escrito para conservarla.
    """
    previo = cargar_datos(path, norma)
    salida: Dict[str, Any] = dict(previo)
    # `vault_arch` y `vault_smoke` la llaman `note`; renombrarla ensuciaría su
    # fichero por lo mismo que `CLAVES_CONOCIDAS` no se unifica a la fuerza.
    salida[campo_descripcion] = descripcion
    # Un dict se guarda como dict: `changelog-baseline.json` indexa por versión
    # (`tamano_congelado` ya contaba esa forma) y `list()` le dejaría las claves.
    salida[clave] = (dict(sorted(elementos.items())) if isinstance(elementos, Mapping)
                     else list(elementos))
    for k, v in (extra or {}).items():
        salida[k] = v
    # `newline="\n"` explícito: en Windows el default traduce a CRLF y la
    # baseline saldría entera en el diff cada vez que se recongela, escondiendo
    # el único dato que importa —qué firma entró o salió— dentro del ruido.
    # Por lo mismo, la sangría es la que el fichero ya tenía.
    path.write_bytes((json.dumps(salida, ensure_ascii=False, indent=_sangria_de(path)) + "\n").encode("utf-8"))
    return len(elementos)


#: La sangría de una baseline que aún no existe.
SANGRIA_POR_DEFECTO = 1


def _sangria_de(path: Path) -> int:
    """La sangría con la que está escrito `path`, o la de siempre si no existe.

    Hasta 2026-10-09 se reescribía todo con 1, y diez de las catorce baselines del
    repo van con 2: congelar una sola firma sacaba el fichero entero en el
    diff. Se mide en la primera línea indentada, que en un `json.dumps` es
    siempre la del primer nivel.
    """
    try:
        texto = path.read_text(encoding="utf-8")
    except OSError:
        return SANGRIA_POR_DEFECTO
    m = re.search(r"\n( +)\S", texto)
    return len(m.group(1)) if m else SANGRIA_POR_DEFECTO


# ── El contrato de `objetivo` ────────────────────────────────────────────────

def validar_objetivo(objetivo: Any) -> List[str]:
    """Los motivos por los que este `objetivo` no vale. Lista vacía = vale.

    No basta con un número. Un `objetivo: 12` sin fecha ni dueño es una cifra
    escrita a mano en un JSON que nadie vuelve a abrir, y la deuda que declaraba
    este campo lo decía así: *exige decidir la cadencia de revisión antes que el
    campo*.
    """
    if not isinstance(objetivo, dict):
        return [f"`objetivo` es {type(objetivo).__name__}, se esperaba objeto con "
                f"{', '.join(CAMPOS_OBJETIVO)}"]
    problemas = ["falta `tamano`"] if "tamano" not in objetivo else []
    tamano = objetivo.get("tamano")
    if tamano is not None and (not isinstance(tamano, int) or tamano < 0):
        problemas.append("`tamano` debe ser un entero ≥ 0: es el tamaño al que "
                         "esta baseline debe haber encogido")
    return problemas + validar_plazo(objetivo)


#: Lo que todo compromiso con fecha declara, mida lo que mida: para cuándo,
#: cada cuánto se revisa y quién lo revisa.
CAMPOS_PLAZO = ("fecha_limite", "cadencia_dias", "dueno")


def validar_plazo(objetivo: Dict[str, Any]) -> List[str]:
    """La mitad del contrato de `objetivo` que no depende de qué se mide.

    Separada en 2026-10-14 porque la necesitan también las métricas de
    `vault_metricas` y la revisión de cada norma: tres sitios validando la
    misma fecha y el mismo dueño serían AP-57 cometido al añadir controles.
    """
    problemas: List[str] = []
    for campo in CAMPOS_PLAZO:
        if campo not in objetivo:
            problemas.append(f"falta `{campo}`")
    cadencia = objetivo.get("cadencia_dias")
    if cadencia is not None and (not isinstance(cadencia, int) or cadencia <= 0):
        problemas.append("`cadencia_dias` debe ser un entero > 0: cada cuánto se revisa")
    fecha = objetivo.get("fecha_limite")
    if fecha is not None and not (isinstance(fecha, str) and _FECHA.match(fecha)):
        problemas.append("`fecha_limite` debe ser `YYYY-MM-DD`")
    dueno = objetivo.get("dueno")
    if dueno is not None and not (isinstance(dueno, str) and dueno.strip()):
        problemas.append("`dueno` debe nombrar a quien revisa, no estar en blanco")
    return problemas


def _objetivo_en(datos: Dict[str, Any], clave: Optional[str]) -> Any:
    """El objetivo de `clave`: el suyo en `objetivos_por_clave`, o el del fichero.

    Un fichero puede congelar dos baselines —`arch-baseline.json` lleva
    `crossings` y `off_port_crossings`— y un solo `objetivo` les obligaba a
    compartir meta. `objetivos_por_clave` le da a cada una la suya; sin él, el
    `objetivo` del fichero sigue valiendo para todas, como hasta ahora.
    """
    por_clave = datos.get("objetivos_por_clave")
    if clave is not None and isinstance(por_clave, dict) and clave in por_clave:
        return por_clave[clave]
    return datos.get("objetivo")


def objetivo_de(path: Path, norma: str,
                clave: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """El `objetivo` declarado, o `None` si esta baseline no declara ninguno.

    `None` no es un fallo: una baseline sin objetivo es una deuda que nadie se
    ha comprometido a encoger todavía, y eso se publica como tal en vez de
    inventarse una fecha.
    """
    return _objetivo_en(cargar_datos(path, norma), clave)


def estado_objetivo(path: Path, clave: str, norma: str,
                    hoy: Optional[date] = None) -> Dict[str, Any]:
    """Si esta baseline cumple lo que se comprometió a cumplir.

    Respuestas distintas y ninguna se confunde con las otras:
    `sin_objetivo` (no hay compromiso), `no_aplica` (no es deuda, y lo dice con
    su motivo), `cumple` / `en_plazo` (lo hay y se mide contra el tamaño real),
    `vencido` (la fecha pasó). Un `sin_objetivo` que
    saliera como `cumple` haría que no comprometerse fuese la opción cómoda.
    """
    hoy = hoy or date.today()
    datos = cargar_datos(path, norma)
    objetivo = _objetivo_en(datos, clave)
    # `tamano_congelado` y no `len(cargar(...))`: hay una baseline cuyo valor es
    # un dict de listas, y exigir lista aquí la dejaría fuera del contrato justo
    # por ser la única que puede crecer.
    tamano = tamano_congelado(datos.get(clave))
    # Una baseline que no es deuda —el contrato de campos crece por diseño— lo
    # declara con su motivo. Sin esto solo podía publicarse `sin objetivo`, que
    # se lee como un compromiso pendiente, o llevar una meta de encoger falsa.
    if objetivo is None and "sin_objetivo_porque" in datos:
        motivo = datos["sin_objetivo_porque"]
        if isinstance(motivo, str) and motivo.strip():
            return {"estado": "no_aplica", "tamano": tamano, "objetivo": None,
                    "motivo": motivo.strip(), "problemas": []}
        return {"estado": "objetivo_invalido", "tamano": tamano, "objetivo": None,
                "problemas": ["`sin_objetivo_porque` debe decir por qué, no estar en blanco"]}
    if objetivo is None:
        return {"estado": "sin_objetivo", "tamano": tamano, "objetivo": None,
                "problemas": []}
    problemas = validar_objetivo(objetivo)
    if problemas:
        return {"estado": "objetivo_invalido", "tamano": tamano,
                "objetivo": objetivo, "problemas": problemas}
    meta = objetivo["tamano"]
    limite = datetime.strptime(objetivo["fecha_limite"], "%Y-%m-%d").date()
    if tamano <= meta:
        estado = "cumple"
    elif hoy > limite:
        estado = "vencido"
    else:
        estado = "en_plazo"
    return {"estado": estado, "tamano": tamano, "objetivo": objetivo,
            "dias_restantes": (limite - hoy).days, "problemas": []}


# ── La pendiente, derivada de git ────────────────────────────────────────────

def _tamano_en_curso(path: Path, rel: str, clave: str) -> Optional[int]:
    """El tamaño del fichero en disco si difiere del de HEAD; si no, `None`.

    Se compara el contenido, no la fecha: un fichero tocado sin cambios no es un
    cambio en curso. Un fichero ilegible tampoco aporta punto —inventar su tamaño
    sería escribir historia—, y lo dirá quien lo cargue con `cargar`.
    """
    try:
        en_disco = path.read_bytes()
    except OSError:
        return None
    try:
        head = vault_subproceso.ejecutar(["git", "show", f"HEAD:{rel}"], cwd=REPO_ROOT,
                                         capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    def _sin_cr(texto: str) -> str:
        return texto.replace("\r\n", "\n")
    if head.returncode == 0 and _sin_cr(head.stdout) == _sin_cr(
            en_disco.decode("utf-8", "replace")):
        return None
    try:
        datos = json.loads(en_disco.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    valor = datos.get(clave) if isinstance(datos, dict) else None
    return None if valor is None else tamano_congelado(valor)


def pendiente(path: Path, clave: str, norma: str, ultimos: int = 20) -> Dict[str, Any]:
    """Cómo ha cambiado el tamaño de esta baseline, commit a commit.

    **Se deriva, no se escribe.** Escribir la pendiente en el propio fichero
    sería afirmar sobre la historia sin que git la respalde, que es AP-53
    exactamente. Aquí se lee de `git log` cada vez, y si git no está disponible
    se dice —`disponible: false`— en vez de devolver una serie vacía que se leería
    como «esta deuda nunca se movió».
    """
    rel = path.relative_to(REPO_ROOT).as_posix()
    # El cambio en curso cuenta como un punto, y entonces git aporta uno menos.
    # Sin esto, el plano regenerado antes del commit que toca la baseline dejaba
    # de estar al día justo después: la ventana de `git log -N` se desplazaba un
    # commit y la serie empezaba en otro sitio (m166 existió solo para eso).
    en_curso = _tamano_en_curso(path, rel, clave)
    try:
        salida = vault_subproceso.ejecutar(
            ["git", "log", f"-{ultimos - (1 if en_curso is not None else 0)}",
             "--format=%H %cs", "--", rel],
            cwd=REPO_ROOT, capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError) as e:
        return {"disponible": False, "motivo": f"git no ejecutable: {e}", "serie": []}
    if salida.returncode != 0:
        return {"disponible": False,
                "motivo": (salida.stderr or "git log falló").strip(), "serie": []}
    serie: List[Dict[str, Any]] = []
    for linea in salida.stdout.splitlines():
        commit, _, fecha = linea.partition(" ")
        if not commit:
            continue
        blob = vault_subproceso.ejecutar(["git", "show", f"{commit}:{rel}"], cwd=REPO_ROOT,
                              capture_output=True, timeout=30, check=False)
        if blob.returncode != 0:
            continue
        try:
            datos = json.loads(blob.stdout)
        except json.JSONDecodeError:
            # Un commit con la baseline a medias no invalida la serie entera:
            # se salta y se sigue. Fingir un tamaño sería inventar historia.
            continue
        valor = datos.get(clave) if isinstance(datos, dict) else None
        if valor is not None:
            serie.append({"commit": commit[:7], "fecha": fecha.strip(),
                          "tamano": tamano_congelado(valor)})
    serie.reverse()  # del más viejo al más nuevo, que es como se lee una pendiente
    if en_curso is not None:
        serie.append({"commit": "en_curso", "fecha": date.today().isoformat(),
                      "tamano": en_curso})
    delta = (serie[-1]["tamano"] - serie[0]["tamano"]) if len(serie) > 1 else None
    return {"disponible": True, "norma": norma, "serie": serie,
            "muestras": len(serie), "delta": delta,
            "sentido": ("encoge" if delta is not None and delta < 0 else
                        "crece" if delta is not None and delta > 0 else
                        "plana" if delta == 0 else None)}
