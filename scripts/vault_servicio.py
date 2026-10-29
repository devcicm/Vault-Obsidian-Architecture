#!/usr/bin/env python3
"""vault_servicio — el pilar: qué servicio de negocio presta este estándar, y qué lo realiza.

Este repo tenía diez registros canónicos —`CONTEXTS`, `NORM_CATALOG`, `FUNDAMENTALS`,
`GROUPS`, `VOCABULARIOS`, `PUERTAS`, `STATUS_VOCAB`, `LIFECYCLE_REGISTRY`, el
`tool-spec.json` y la tabla de entorno— y ninguno decía **para qué**. Se podía
responder «esta tool, ¿en qué contexto vive?» y «esta norma, ¿qué severidad tiene?»,
pero no «esta tool, ¿a qué servicio sirve?». Sin esa respuesta, una tool nueva no
tiene contra qué justificarse y el catálogo crece por acumulación.

Tres registros y nada más. No es documentación: es de donde `vault_blueprint`
deriva las capas 1 y 2 del plano.

    python scripts/vault_servicio.py --list            # servicio, capacidades y naturalezas
    python scripts/vault_servicio.py --trace           # tool → grupo → capacidad → servicio
    python scripts/vault_servicio.py --naturalezas     # qué construye, qué documenta, qué custodia
    python scripts/vault_servicio.py --check --strict  # la trazabilidad sin eslabón roto
    python scripts/vault_servicio.py --wheel-sync      # regenera empaquetado/fuera-de-la-wheel.json

## Dos ejes, dos preguntas distintas

`CAPACIDADES` responde **a qué sirve** una tool y se declara por grupo.
`NATURALEZAS` responde **sobre qué actúa** y se declara por tool, porque la
confusión que existe para separar —construir el vault frente a documentarlo—
ocurre *dentro* de los grupos y no entre ellos. Ver el comentario de `NATURALEZAS`.
Los dos ejes se cruzan en un solo punto verificable (`meta_estandar` ⟺
`gobernanza_del_estandar`) y `check()` exige que no discrepen.

## Por qué son tres capacidades y no dos

`AGENTS.md` declara dos ejes: *escritura → gobernanza* (grupos 1–33) y
*consulta → contexto* (Grupo 34). Al clasificar los 37 grupos del catálogo contra
esa prosa aparecieron dos desajustes que no se pueden tapar sin mentir en el registro:

1. **El Grupo 35 (Normas) gobierna el estándar, no el vault del usuario.**
   Cuántas tools son lo dice `--trace`, no esta línea: escribirlo aquí a mano
   es AP-47, y de hecho ya se quedó en 13 mientras el grupo crecía a 17 —el
   número viajó copiado a `docs/BLUEPRINT.md` y a `AGENTS.md`, cada uno con
   una cifra distinta y las tres verdes.
   `vault_gate`, `vault_doc_sync`, `vault_doc_counts`, `vault_changelog_check`,
   `vault_arch`, `vault_noop_audit`, `vault_blame_audit`, `vault_error_contract` y
   `vault_smoke` no tocan las notas de nadie: comprueban que este repo cumple lo que
   publica. Meterlos en «escritura → gobernanza» diría que sirven a la memoria del
   agente, y no es cierto. Es una **tercera capacidad**, y llevaba tiempo existiendo
   sin nombre — de hecho es la que más ha crecido en las últimas versiones.
2. **El Grupo 26 (Tokens) cae en el rango 1–33 pero sirve a la consulta.** Sus tres
   tools viven en el contexto `consulta` y existen para que un paquete de contexto
   quepa en una ventana. El rango numérico de `AGENTS.md` es el orden en que los
   grupos se fueron añadiendo, no una clasificación.

El registro manda y la prosa se corrige: la alternativa —forzar 16 tools a un eje que
no sirven— es exactamente el fallo que este módulo existe para evitar.
"""

import argparse
import ast
import re
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent))

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.kernel import rutas
from vault.kernel.rutas import cita_repo

from vault_errors import emit_error, wrap_main


# ── El servicio ──────────────────────────────────────────────────────────────

SERVICIO: Dict[str, Any] = {
    "id": "memoria_documental_gobernada",
    "titulo": "Memoria documental persistente y gobernada para agentes LLM",
    "declaracion": (
        "Dar a un agente LLM memoria documental persistente, auditable y gobernada "
        "sobre markdown plano: lo que el agente escribe queda normalizado, versionado "
        "y trazable, y lo que necesita recordar se le devuelve como contexto acotado."
    ),
    "restricciones": [
        {
            "id": "sin_base_de_datos",
            "texto": "Sin base de datos, sin embeddings y sin servicio externo.",
            "motivo": (
                "Es una decisión de producto, no una limitación pendiente de resolver: "
                "el vault debe seguir siendo legible y editable por una persona con un "
                "editor de texto, y sobrevivir a que este toolkit desaparezca."
            ),
            "declarada_en": "AGENTS.md — Los dos ejes; vault_arch.CONTEXTS['consulta']['prohibe']",
        },
        {
            "id": "sin_dependencias",
            "texto": "Solo stdlib + PyYAML.",
            "motivo": (
                "Un agente instala el toolkit en el repo del usuario; cada dependencia "
                "es una razón para que no lo haga."
            ),
            "declarada_en": "AGENTS.md — Qué contiene",
        },
        {
            "id": "no_derogacion",
            "texto": "Nada se elimina; lo reemplazado se anota `superseded_by:`.",
            "motivo": (
                "Los vaults consumidores leen contratos de este repo. Un campo que "
                "evapora rompe en silencio a quien lo leía."
            ),
            "declarada_en": "AGENTS.md — regla 2; manifiesto § Política de no-derogación",
        },
    ],
}


# ── Las capacidades que lo realizan ──────────────────────────────────────────
#
# `grupos` son ids de la numeración de `scripts/README.md`, que es la fuente única
# que `vault_mcp_catalog.mapa_de_grupos()` deriva. **No hay una numeración propia
# de este módulo**: reintroducirla sería estrenar la divergencia que v40.8 cerró.

from vault.meta_toolkit.capacidades import CAPACIDADES  # noqa: E402 — hoja, AP-58


# ── La naturaleza de cada tool ───────────────────────────────────────────────
#
# Segundo eje, **ortogonal** a la capacidad y con otra granularidad a propósito:
# la capacidad se declara por grupo, la naturaleza por **tool**. No es un capricho
# de diseño, es dónde está el problema — la mezcla ocurre *dentro* de los grupos:
#
#   * el grupo 1 (Core) tiene `vault_write` (documentación) junto a `vault_read`,
#     `vault_search` y `vault_list` (consulta) y `vault_move` (construcción);
#   * el grupo 15 (Índices) es construcción pura, el 6 (Salud) es custodia pura,
#     y ambos caen en la misma capacidad;
#   * `vault_ingest` escribe notas —documentación— viviendo en la capacidad de
#     consulta, que es justo lo que `AGENTS.md` avisa cuando dice que es «la única
#     con superficie de escritura».
#
# Un eje por grupo no separa nada de eso. Por eso este es por tool.
#
# Qué responde: **¿esta tool le da forma al vault, escribe su contenido, lo
# mantiene correcto, lo lee, o mide este repo?** Confundir las dos primeras es el
# error que el usuario nombró: pedir «documenta esto» y recibir una reestructuración,
# o llamar a una tool de construcción creyendo que va a capturar contenido.
#
# Son cinco y no dos porque es lo que da la medida. Forzar 99 tools a
# construcción/documentación exigiría afirmar que `vault_backup` construye y que
# `vault_read` documenta — la misma clase de mentira que la medida desmintió en
# v40.9 con los dos ejes de capacidad. Cuando el registro y el deseo discrepan,
# manda el registro.

from vault.meta_toolkit.naturalezas import NATURALEZAS

# ── Derivaciones ─────────────────────────────────────────────────────────────

def _mapa_de_grupos() -> Dict[str, Dict[str, Any]]:
    """`{tool: {"name": grupo, "id": group_id}}` — puerto de meta_toolkit."""
    from vault_mcp_catalog import mapa_de_grupos

    return mapa_de_grupos()


def capacidad_por_grupo() -> Dict[int, str]:
    """`{group_id: capacidad}`. Si un id se declara dos veces, gana el fallo, no el orden."""
    salida: Dict[int, str] = {}
    for nombre, datos in CAPACIDADES.items():
        for gid in datos["grupos"]:
            salida.setdefault(gid, nombre)
    return salida


def naturaleza_por_tool() -> Dict[str, str]:
    """`{tool: naturaleza}`. Si una tool se declara dos veces, gana el fallo."""
    salida: Dict[str, str] = {}
    for nombre, datos in NATURALEZAS.items():
        for tool in datos["tools"]:
            salida.setdefault(tool, nombre)
    return salida


# ── La wheel de producto ─────────────────────────────────────────────────────
#
# La capacidad `gobernanza_del_estandar` mide este repo y no las notas de nadie:
# sin sus baselines, su manifiesto y su `git`, en la instalación de un tercero
# no tiene sobre qué actuar. Hasta v40.34 viajaba entera en la wheel. La lista
# de lo que se queda fuera **no se escribe a mano**: sale de `CAPACIDADES`, se
# vuelca a un JSON que el hook de build (`empaquetado/construir.py`) lee con
# solo stdlib —el build aislado no tiene PyYAML ni este repo en `sys.path`— y
# `check()` falla si el volcado y la derivación divergen.

_RAIZ = Path(__file__).resolve().parent.parent
#: El mapa derivado. Es constante de módulo y no una ruta calculada en cada uso para que un test
#: que necesite estropearlo lo haga sobre una copia: dos workers que comparten el árbol veían la
#: edición a mano del otro como `doc_drift` (el flake de `test_naturalezas`, py3.9/Windows).
GOBIERNO_DOC = _RAIZ / rutas.DOCS / "GOBIERNO.md"
FUERA_DE_LA_WHEEL = _RAIZ / "empaquetado" / "fuera-de-la-wheel.json"
PAQUETE_DE_LA_WHEEL = "vault_toolkit._impl"
_EXCEPCIONES_DE_IMPORT = {"ImportError", "ModuleNotFoundError"}


def _scripts_por_tool() -> Dict[str, str]:
    """`{tool: módulo}` del catálogo — mismo puerto que `_mapa_de_grupos`."""
    from vault_mcp_catalog import TOOLS_CATALOG

    return {
        tool: datos["script"].strip().removesuffix(".py")
        for tool, datos in TOOLS_CATALOG.items()
        if (datos.get("script") or "").strip()
    }


def modulos_fuera_de_la_wheel() -> List[str]:
    """Los módulos de `scripts/` cuya tool sirve a la gobernanza del estándar."""
    por_grupo = capacidad_por_grupo()
    scripts = _scripts_por_tool()
    return sorted(
        scripts[tool]
        for tool, datos in _mapa_de_grupos().items()
        if por_grupo.get(datos["id"]) == "gobernanza_del_estandar" and tool in scripts
    )


def volcado_de_la_wheel() -> Dict[str, Any]:
    return {
        "_generado_por": "python scripts/vault_servicio.py --wheel-sync",
        "_no_editar": (
            "Derivado de vault_servicio.CAPACIDADES['gobernanza_del_estandar']. "
            "vault_servicio --check falla si diverge."
        ),
        "capacidad": "gobernanza_del_estandar",
        "paquete": PAQUETE_DE_LA_WHEEL,
        "modulos": modulos_fuera_de_la_wheel(),
    }


def escribir_volcado_de_la_wheel() -> Dict[str, Any]:
    datos = volcado_de_la_wheel()
    FUERA_DE_LA_WHEEL.parent.mkdir(parents=True, exist_ok=True)
    FUERA_DE_LA_WHEEL.write_bytes((json.dumps(datos, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return {"ok": True, "tool": "vault_servicio", "action": "wheel_sync",
            "written": str(FUERA_DE_LA_WHEEL.relative_to(_RAIZ)).replace("\\", "/"),
            "modules": len(datos["modulos"])}


def _protegido(cadena: List[ast.AST]) -> bool:
    """¿Algún `try` de la cadena captura el fallo de importar?"""
    for nodo in cadena:
        if isinstance(nodo, ast.Try):
            for h in nodo.handlers:
                tipos = h.type.elts if isinstance(h.type, ast.Tuple) else [h.type]
                if h.type is None or any(
                    getattr(t, "id", None) in _EXCEPCIONES_DE_IMPORT for t in tipos
                ):
                    return True
    return False


def importaciones_sin_proteger(codigo: str, fuera: set) -> List[Dict[str, Any]]:
    """Imports de un módulo excluido que fallarían en la wheel.

    Cuenta `import x`, `from x import …` e `import_toolkit_module("x")`. Un
    import dentro de un `try` que captura `ImportError` es una degradación
    declarada —`vault_norms_engine` hace eso con `vault_smoke`— y no cuenta.
    """
    hallados: List[Dict[str, Any]] = []

    def visitar(nodo: ast.AST, cadena: List[ast.AST]) -> None:
        nombres: List[str] = []
        if isinstance(nodo, ast.Import):
            nombres = [a.name.split(".")[0] for a in nodo.names]
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and not nodo.level:
            nombres = [nodo.module.split(".")[-1]]
            if nodo.module == PAQUETE_DE_LA_WHEEL:
                nombres += [a.name for a in nodo.names]
        elif isinstance(nodo, ast.Call) and nodo.args:
            f = nodo.func
            if (getattr(f, "id", None) or getattr(f, "attr", None)) == "import_toolkit_module":
                arg = nodo.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    nombres = [arg.value.split(".")[-1]]
        for n in nombres:
            if n in fuera and not _protegido(cadena):
                hallados.append({"module": n, "line": nodo.lineno})
        for hijo in ast.iter_child_nodes(nodo):
            visitar(hijo, cadena + [nodo])

    visitar(ast.parse(codigo), [])
    return hallados


def _fuentes_de_la_wheel(fuera: set) -> List[Path]:
    fuentes = [p for p in sorted((_RAIZ / "scripts").glob("*.py")) if p.stem not in fuera]
    for paquete in ("vault", "vault_toolkit"):
        fuentes += sorted((_RAIZ / paquete).rglob("*.py"))
    return fuentes


def check_de_la_wheel() -> Dict[str, Any]:
    derivado = modulos_fuera_de_la_wheel()
    try:
        volcado = json.loads(FUERA_DE_LA_WHEEL.read_text(encoding="utf-8")).get("modulos")
    except (OSError, ValueError):
        volcado = None
    fuera = set(derivado)
    rotos = []
    for fuente in _fuentes_de_la_wheel(fuera):
        for h in importaciones_sin_proteger(fuente.read_text(encoding="utf-8"), fuera):
            rel = str(fuente.relative_to(_RAIZ)).replace("\\", "/")
            rotos.append({"file": rel, **h})
    return {
        "excluded_modules": len(derivado),
        "exclusion_drift": None if volcado == derivado else {
            "derived": derivado, "dumped": volcado,
            "fix": "python scripts/vault_servicio.py --wheel-sync",
        },
        "shipped_imports_of_excluded": rotos,
    }


def trazabilidad() -> List[Dict[str, Any]]:
    """La cadena completa, una fila por tool: tool → grupo → capacidad → servicio.

    `nature` va en la misma fila y no en una tabla aparte porque la pregunta que
    contesta —«esto construye o documenta»— se hace sobre una tool concreta, en el
    momento de elegirla.
    """
    por_grupo = capacidad_por_grupo()
    por_tool = naturaleza_por_tool()
    filas = []
    for tool, datos in sorted(_mapa_de_grupos().items()):
        capacidad = por_grupo.get(datos["id"])
        filas.append(
            {
                "tool": tool,
                "group": datos["name"],
                "group_id": datos["id"],
                "capability": capacidad,
                "nature": por_tool.get(tool),
                "service": SERVICIO["id"] if capacidad else None,
            }
        )
    return filas


def check(strict: bool = False) -> Dict[str, Any]:
    """Trazabilidad exigida. Es lo que convierte esto en registro y no en prosa.

    Cuatro invariantes, ninguna con baseline: se miden en cero al declararlas
    porque los 37 grupos se clasifican en la misma tanda. Una baseline aquí
    permitiría añadir un grupo sin decidir a qué sirve, que es justo el vacío
    que este módulo cierra.
    """
    mapa = _mapa_de_grupos()
    ids_reales = {d["id"]: d["name"] for d in mapa.values()}
    por_grupo = capacidad_por_grupo()

    # 1. Todo grupo del catálogo pertenece a una capacidad.
    huerfanos = sorted(
        (
            {"group_id": gid, "group": nombre}
            for gid, nombre in ids_reales.items()
            if gid not in por_grupo
        ),
        key=lambda x: x["group_id"],
    )

    # 2. Ninguna capacidad reclama un grupo que no existe.
    inventados = sorted(
        (
            {"group_id": gid, "capability": cap}
            for gid, cap in por_grupo.items()
            if gid not in ids_reales
        ),
        key=lambda x: x["group_id"],
    )

    # 3. Ningún grupo en dos capacidades.
    duplicados = []
    vistos: Dict[int, str] = {}
    for nombre, datos in CAPACIDADES.items():
        for gid in datos["grupos"]:
            if gid in vistos:
                duplicados.append(
                    {"group_id": gid, "capabilities": [vistos[gid], nombre]}
                )
            else:
                vistos[gid] = nombre

    # 4. Toda capacidad tiene al menos una tool viva.
    tools_por_capacidad: Dict[str, int] = {c: 0 for c in CAPACIDADES}
    for fila in trazabilidad():
        if fila["capability"]:
            tools_por_capacidad[fila["capability"]] += 1
    vacias = sorted(c for c, n in tools_por_capacidad.items() if n == 0)

    # 5. Toda capacidad sirve a un servicio declarado.
    sin_servicio = sorted(
        c for c, d in CAPACIDADES.items() if d.get("sirve_a") != SERVICIO["id"]
    )

    # ── El eje de naturaleza, por tool ───────────────────────────────────────
    # Mismas invariantes y por el mismo motivo: sin baseline. Una baseline aquí
    # dejaría añadir una tool sin decidir si construye o documenta, que es
    # exactamente la confusión que el eje existe para impedir.
    por_tool = naturaleza_por_tool()

    # 6. Toda tool del catálogo tiene naturaleza.
    sin_naturaleza = sorted(t for t in mapa if t not in por_tool)

    # 7. Ninguna naturaleza reclama una tool que no está en el catálogo.
    naturaleza_inventada = sorted(t for t in por_tool if t not in mapa)

    # 8. Ninguna tool en dos naturalezas.
    naturaleza_duplicada = []
    vistas: Dict[str, str] = {}
    for nombre, datos in NATURALEZAS.items():
        for tool in datos["tools"]:
            if tool in vistas:
                naturaleza_duplicada.append(
                    {"tool": tool, "natures": [vistas[tool], nombre]}
                )
            else:
                vistas[tool] = nombre

    # 9. Toda naturaleza tiene al menos una tool viva.
    tools_por_naturaleza: Dict[str, int] = {n: 0 for n in NATURALEZAS}
    for tool, nat in por_tool.items():
        if tool in mapa:
            tools_por_naturaleza[nat] += 1
    naturalezas_vacias = sorted(n for n, c in tools_por_naturaleza.items() if c == 0)

    # 10. Los dos ejes no se contradicen donde coinciden.
    #     `meta_estandar` y `gobernanza_del_estandar` son la misma frontera vista
    #     desde dos preguntas distintas: «¿a qué sirve?» y «¿sobre qué actúa?».
    #     Que coincidan no es redundancia — es la única pareja verificable que
    #     tienen los dos ejes, y si un día divergen una de las dos miente.
    desacuerdos = []
    for fila in trazabilidad():
        es_meta_nat = fila["nature"] == "meta_estandar"
        es_meta_cap = fila["capability"] == "gobernanza_del_estandar"
        if es_meta_nat != es_meta_cap:
            desacuerdos.append(
                {
                    "tool": fila["tool"],
                    "nature": fila["nature"],
                    "capability": fila["capability"],
                }
            )

    # 11. La wheel deja fuera exactamente la gobernanza del estándar, y nada
    #     de lo que viaja la necesita sin declararlo con un `except ImportError`.
    wheel = check_de_la_wheel()

    # 12. El mapa derivado de la gobernanza (v41.21) refleja los registros:
    #     si alguien edita `docs/GOBIERNO.md` a mano o los registros cambian
    #     sin regenerar, el mapa dice lo que ya no es — AP-47 con formato de
    #     doc. El contenido se genera en memoria y se compara contra el
    #     disco: una verificación no escribe ni un fichero transitorio
    #     (v41.24 — generar != escribir != verificar).
    destino_doc = GOBIERNO_DOC
    doc_drift = None
    if not destino_doc.is_file():
        doc_drift = f"{cita_repo(rutas.DOCS, 'GOBIERNO.md')} no existe: regenera con --doc"
    elif destino_doc.read_text(encoding="utf-8") != documento():
        doc_drift = (
            f"{cita_repo(rutas.DOCS, 'GOBIERNO.md')} difiere de lo que los registros producirían: "
            "regenera con --doc. Lo escrito a mano se pierde — el registro es "
            "la fuente")

    ok = not (
        huerfanos or inventados or duplicados or vacias or sin_servicio
        or sin_naturaleza or naturaleza_inventada or naturaleza_duplicada
        or naturalezas_vacias or desacuerdos
        or wheel["exclusion_drift"] or wheel["shipped_imports_of_excluded"]
        or doc_drift
    )
    resultado = {
        "ok": ok,
        "tool": "vault_servicio",
        "service": SERVICIO["id"],
        "capabilities_total": len(CAPACIDADES),
        "natures_total": len(NATURALEZAS),
        "groups_total": len(ids_reales),
        "tools_total": len(mapa),
        "tools_by_capability": tools_por_capacidad,
        "tools_by_nature": tools_por_naturaleza,
        "orphan_groups": huerfanos,
        "unknown_groups": inventados,
        "duplicated_groups": duplicados,
        "empty_capabilities": vacias,
        "capabilities_without_service": sin_servicio,
        "tools_without_nature": sin_naturaleza,
        "unknown_tools_in_natures": naturaleza_inventada,
        "duplicated_natures": naturaleza_duplicada,
        "empty_natures": naturalezas_vacias,
        "axis_disagreements": desacuerdos,
        "doc_drift": doc_drift,
        "wheel": wheel,
        "hint": (
            "Un grupo huérfano no se arregla ampliando una capacidad al azar: se "
            "decide a qué servicio sirve. Si no sirve a ninguno, la pregunta es por "
            "qué existe el grupo. Una tool sin naturaleza es la misma pregunta en el "
            "otro eje: ¿le da forma al vault, escribe su contenido, lo mantiene, lo "
            "lee, o mide este repo?"
        ),
    }
    if strict and not ok:
        resultado["exit_code"] = 1
    return resultado


def listar() -> Dict[str, Any]:
    return {
        "ok": True,
        "tool": "vault_servicio",
        "service": SERVICIO,
        "capabilities": {
            nombre: {
                "titulo": datos["titulo"],
                "resultado": datos["resultado"],
                "groups": len(datos["grupos"]),
                "nota": datos.get("nota"),
            }
            for nombre, datos in CAPACIDADES.items()
        },
        "natures": {
            nombre: {
                "titulo": datos["titulo"],
                "actua_sobre": datos["actua_sobre"],
                "distincion": datos["distincion"],
                "tools": len(datos["tools"]),
            }
            for nombre, datos in NATURALEZAS.items()
        },
    }


def documento() -> str:
    """El texto completo de `docs/GOBIERNO.md`, sin escribir nada.

    GENERAR != ESCRIBIR != VERIFICAR (v41.24): esta función es la única
    fuente del contenido — `escribir_doc()` persiste lo que ella produce y
    `check()` compara contra lo que ella produce, sin tocar el disco. Sin
    fecha de generación: el doc es función de los registros canónicos y de
    nada más, así que el mismo registro produce los mismos bytes cualquier
    día — el cuándo lo dice el commit que regeneró el fichero. Es el criterio
    que `vault_metricas.documento()` ya declaró para `docs/METRICAS.md`
    («Sin estados: dependen del día»).

    La pregunta que contesta —qué es una norma, qué es ley del estándar y qué
    es regla del propio repo, y quién vigila qué— estaba repartida entre el
    manifiesto, `docs/PUERTAS.md`, `docs/sdd/04-antipatterns.md` y el catálogo.
    Cuatro lectores armando el mismo modelo a mano es AP-57 con formato de
    documentación: cada cifra aquí sale del registro que la posee, y `--check`
    falla si el documento se aparta de la regeneración (el criterio de
    `docs/METRICAS.md`).
    """
    from vault_gate import PUERTAS
    from vault_norms_catalog import NORM_CATALOG

    # El propietario del estándar se deriva del banner del manifiesto: no se
    # escribe aquí — un dueño escrito a mano en un derivado es un dueño que se
    # desincroniza del registro que lo declara.
    from vault_audit_catalog import manifiesto_del_estandar

    manifiesto = manifiesto_del_estandar(_RAIZ)
    banner = re.search(
        r"^\*\*Autor:\*\*\s*(.+)$",
        manifiesto.read_text(encoding="utf-8") if manifiesto else "",
        re.MULTILINE,
    )
    propietario = banner.group(1).strip() if banner else "sin declarar"
    responsables_adr = sorted(
        m.group(1).strip()
        for m in re.finditer(
            r"^\s*-\s*\*\*Responsable:\*\*\s*([^—(]+)",
            "\n".join(
                (p.read_text(encoding="utf-8", errors="replace")
                 for p in sorted((_RAIZ / "docs" / "adr").glob("*.md"))),
            ),
            re.MULTILINE,
        )
    )

    filas = trazabilidad()
    normas_por_tipo: Dict[str, int] = {}
    normas_por_enforcement: Dict[str, int] = {}
    for n in NORM_CATALOG:
        normas_por_tipo[n["type"]] = normas_por_tipo.get(n["type"], 0) + 1
        normas_por_enforcement[n["enforcement"]] = (
            normas_por_enforcement.get(n["enforcement"], 0) + 1)

    from vault.meta_toolkit.naturalezas import NATURALEZAS
    from vault.meta_toolkit.protocolo_de_sesion import _tools_del_protocolo

    meta_tools = set(NATURALEZAS["meta_estandar"]["tools"])
    n_herramientas_meta = len(meta_tools)
    # el mismo corte que hace el catálogo al publicar: se le pregunta a la
    # capacidad, que es su dueña
    from vault_mcp_catalog import grupos_no_expuestos
    n_meta_no_expuestas = sum(
        1 for d in _mapa_de_grupos().values() if d["name"] in set(grupos_no_expuestos()))

    por_capacidad: Dict[str, List[Dict[str, str]]] = {}
    for f in filas:
        por_capacidad.setdefault(f["capability"] or "sin clasificar", []).append(f)

    lineas: List[str] = [
        "# Gobierno del estándar",
        "",
        "_Derivado de los registros canónicos. "
        "Se regenera con `python scripts/vault_servicio.py --doc` y no se "
        "edita a mano: lo escrito aquí se pierde (AP-47). El cuándo lo dice "
        "el commit que lo regeneró, no este texto._",
        "",
        "## El servicio y sus tres capacidades",
        "",
    ]
    for cap_id, cap in CAPACIDADES.items():
        lineas.append(
            f"- **{cap['titulo']}** (`{cap_id}`) — {cap['resultado']} Sirve a: "
            f"`{cap['sirve_a']}`.")
    lineas += [
        "",
        "## Las cuatro familias de normas",
        "",
        f"{len(NORM_CATALOG)} normas vivas, cada una un paquete en "
        "`normas/<código>/`. El catálogo derivado completo está en "
        "[docs/sdd/04-antipatterns.md](sdd/04-antipatterns.md).",
        "",
    ]
    for prefijo, tipo, titulo, que in [
        ("AP", "antipattern", "Anti-patrón",
         "Un fallo con nombre, señal, prevención y límites. La unidad "
         "normativa principal."),
        ("PAT", "pattern", "Patrón",
         "La forma recomendada de resolver algo que el estándar ya resolvió "
         "mal una vez."),
        ("SP", "session_protocol", "Protocolo de sesión",
         "Reglas de proceso entre el agente y el vault durante una sesión."),
        ("CN", "convention", "Convención",
         "Un acuerdo de nomenclatura o forma que mantiene el vault legible y "
         "predecible."),
    ]:
        lineas.append(
            f"- **{prefijo}** · {titulo} — {que} "
            f"({normas_por_tipo.get(tipo, 0)} vigentes).")
    lineas += [
        "",
        "## La escalera de enforcement",
        "",
    ]
    for nivel, que in [
        ("guard", "Falla en el punto de uso: la tool se niega a hacerlo mal."),
        ("guard+audit", "Y además una puerta la mide sobre el repo entero."),
        ("audit", "Una puerta la mide; se arregla en el siguiente ciclo."),
        ("recommended", "Se publica, no se fuerza. La cobertura débil se declara."),
    ]:
        lineas.append(
            f"- **{nivel}** ({normas_por_enforcement.get(nivel, 0)} normas) — {que}")
    lineas += [
        "",
        "## Qué es ley para quién",
        "",
        "- **Para quien usa el vault**: las normas, aplicadas por las tools de "
        "escritura y consulta — contrato de nota, vocabulario de estados, "
        "protocolo de borrado.",
        # El criterio de «esto es documentación del estándar y no una nota»
        # tiene dueño (vault_audit_catalog); aquí no se re-enuncia: se le
        # pregunta, y el mapa publica lo que responde (AP-57).
        "- **Para quien mantiene este repositorio**: la gobernanza del "
        "meta-toolkit — el conjunto de tools cuya naturaleza es "
        f"`meta_estandar` ({n_herramientas_meta}), que miden este repo y no "
        f"el vault de nadie, por las {len(PUERTAS)} puertas de "
        "`docs/PUERTAS.md`.",
        "",
        "## La superficie que ve el agente por MCP",
        "",
        f"El catálogo marca `exposed_via_mcp` y el servidor MCP lo respeta: "
        f"las {n_meta_no_expuestas} tools de gobernanza **no** llegan al "
        "cliente (el recorte lo deriva de la capacidad "
        "`gobernanza_del_estandar`, no de una lista escrita a mano). "
        "`VAULT_MCP_PERFIL=agente` reduce el menú a las "
        f"{len(_tools_del_protocolo())} del protocolo de sesión, y el "
        "servidor poda además en runtime las tools cuyo script no existe.",
        "",
        "## El mapa: capacidad → grupo → tool",
        "",
    ]
    for cap_id, cap in CAPACIDADES.items():
        filas_cap = por_capacidad.get(cap_id, [])
        lineas.append(f"### {cap['titulo']} — {len(filas_cap)} tools (`{cap_id}`)")
        lineas.append("")
        grupos: Dict[str, List[str]] = {}
        for f in filas_cap:
            grupos.setdefault(f"{f['group']} ({f['group_id']})", []).append(f["tool"])
        for grupo, tools_g in sorted(grupos.items()):
            lineas.append(f"- **{grupo}** — {', '.join(sorted(tools_g))}")
        lineas.append("")
    lineas += [
        "## El vocabulario y su dueño",
        "",
        "- **`meta.status`** (12 valores) — `vault_norms_catalog.STATUS_VOCAB`.",
        "- **Secciones del vault y su clase documental** — `vault_registry`.",
        "- **Instantáneas congeladas** — `vault_io.SNAPSHOT_DIRS`.",
        "- **Material ajeno al vault** (`node_modules`, cachés) — "
        "`vault_io.DIRECTORIOS_AJENOS`.",
        "- **Los verbos de git que el toolkit ejecuta** — "
        "`vault/kernel/procesos_git.py` (AP-68).",
        "- **Las causas del dominio** — `vault/kernel/fallos.py`.",
        "- **Los códigos de error y su recuperación** — `ERROR_CATALOG` en "
        "`vault/kernel/errores.py`.",
        "",
        "## Cómo se lee una norma",
        "",
        "1. `normas/<código>/norma.py` — la declaración: qué fallo es, "
        "severidad, enforcement, de qué se distingue.",
        "2. `porque.md` — por qué existe y qué dejó fuera, con el alcance "
        "declarado.",
        "3. `guard.py` / `heal.py` — apuntan a las funciones que la aplican: "
        "derivados, no escritura.",
        "4. El `test_*.py` del paquete la ejercita.",
        "5. La versión pública completa: "
        "[docs/sdd/04-antipatterns.md](sdd/04-antipatterns.md).",
        "",
        "## Quién responde",
        "",
        "- **Por el estándar**: el mantenedor que declara el banner del "
        f"manifiesto — **{propietario}**. No hay segunda instancia: cada "
        "release pasa por una invocación explícita de `vault_release "
        "--nueva-version`, y quien la invoca queda como autoría en git. La "
        "aprobación de cada versión es otro dato — autoría y aprobación son "
        "conceptos distintos: la acredita el registro canónico de "
        "aprobaciones cuando existe evidencia para ella, y nunca se infiere "
        "de quién hizo el commit.",
        "- **Por cada decisión de arquitectura**: el `Responsable:` "
        f"declarado en cada ADR de `docs/adr/` — {' · '.join(sorted(set(responsables_adr)))}. "
        "AP-64 aplicado al propio repo (v41.21): un ADR sin responsable no "
        "es una decisión, es una intención.",
        "- **Por cada duda de norma**: el catálogo (`vault_norms --show "
        "<código>`) y el `porque.md` del paquete, que declara qué quedó fuera "
        "y por qué.",
        "- **Por cada promesa al consumidor**: el ejercedor que declara "
        "`vault_produccion`; por cada propiedad afirmada, la puerta o el "
        "instrumento de `AFIRMADAS`.",
        "",
        "## Las puertas",
        "",
        f"La gobernanza se ejerce por {len(PUERTAS)} puertas de cierre, una por "
        "registro. El porqué de cada una está en "
        "[docs/PUERTAS.md](PUERTAS.md), derivado de `vault_gate.PUERTAS`.",
        "",
    ]
    return "\n".join(lineas)


def escribir_doc(ruta: "Path | None" = None) -> Dict[str, Any]:
    """Persiste `documento()`. Desde v41.24 es SOLO la mitad escritora.

    Hasta v41.23 aquí vivía también la generación, y `check()` la llamaba
    apuntada a un `.regenerado.md` dentro del repo para leerlo y borrarlo:
    la verificación con efectos secundarios. Ahora solo escribe — por
    escrito atómico, y con una ruta fuera del repo responde igual, porque
    el relativo del envelope es cortesía, no una exigencia del caller.
    """
    texto = documento()
    from vault_io import atomic_write_text

    destino = ruta or GOBIERNO_DOC
    atomic_write_text(destino, texto, encoding="utf-8", sanitize=False)
    try:
        escrito = str(destino.relative_to(_RAIZ)).replace("\\", "/")
    except ValueError:
        escrito = str(destino).replace("\\", "/")
    return {"ok": True, "tool": "vault_servicio", "action": "doc",
            "written": escrito, "bytes": len(texto.encode("utf-8"))}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Servicio de negocio del estándar y capacidades que lo realizan"
    , allow_abbrev=False)
    parser.add_argument("--list", action="store_true", help="servicio y capacidades")
    parser.add_argument("--trace", action="store_true", help="tool → capacidad → servicio")
    parser.add_argument(
        "--naturalezas", action="store_true",
        help="tools agrupadas por naturaleza (construcción / documentación / …)",
    )
    parser.add_argument("--check", action="store_true", help="trazabilidad exigida")
    parser.add_argument(
        "--doc", action="store_true",
        help="regenera docs/GOBIERNO.md, el mapa derivado de la gobernanza",
    )
    parser.add_argument(
        "--wheel-sync", action="store_true",
        help="regenera empaquetado/fuera-de-la-wheel.json desde CAPACIDADES",
    )
    parser.add_argument("--strict", action="store_true", help="exit 1 si falla")
    args = parser.parse_args()

    if args.doc:
        salida = escribir_doc()
    elif args.wheel_sync:
        salida = escribir_volcado_de_la_wheel()
    elif args.naturalezas:
        salida = {
            "ok": True,
            "tool": "vault_servicio",
            "natures_total": len(NATURALEZAS),
            "natures": {
                nombre: {
                    "titulo": datos["titulo"],
                    "actua_sobre": datos["actua_sobre"],
                    "distincion": datos["distincion"],
                    "tools": sorted(datos["tools"]),
                }
                for nombre, datos in NATURALEZAS.items()
            },
        }
    elif args.trace:
        filas = trazabilidad()
        salida: Dict[str, Any] = {
            "ok": all(f["capability"] for f in filas),
            "tool": "vault_servicio",
            "rows": len(filas),
            "trace": filas,
        }
    elif args.list:
        salida = listar()
    elif args.check:
        salida = check(strict=args.strict)
    else:
        salida = listar()

    print(json.dumps(salida, indent=2, ensure_ascii=False))
    return 1 if (args.strict and not salida.get("ok")) else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_servicio"))
