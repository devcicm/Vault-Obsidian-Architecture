#!/usr/bin/env python3
"""vault_blueprint — el plano de construcción: qué se construye, sobre qué, y con qué guard.

Este repo tenía once registros canónicos —`SERVICIO`, `CAPACIDADES`, `CONTEXTS`,
`NORM_CATALOG`, `FUNDAMENTALS`, `GROUPS`/`TOOLS_CATALOG`, `VOCABULARIOS`, `PUERTAS`,
`STATUS_VOCAB`, `LIFECYCLE_REGISTRY` y el `tool-spec.json`— repartidos en diez módulos
y **sin nada que los atase**. Se podía responder cualquier pregunta dentro de un
registro y ninguna que cruzara dos: «esta tool, ¿a qué servicio sirve?», «esta norma,
¿qué puerta la hace cumplir y qué test la muerde?». `docs/ARQUITECTURA.md` cubre una
sola capa —contextos y puertos— y no pretende otra cosa.

    python scripts/vault_blueprint.py --blueprint      # regenera docs/BLUEPRINT.md
    python scripts/vault_blueprint.py --check --strict # el doc vs. los registros
    python scripts/vault_blueprint.py --freeze         # capa 4: congela la deuda

## El papelito manda porque el código lo escribe

La petición era «papelito manda, fuente de verdad única»; `CLAUDE.md` regla 3 dice
«registro canónico primero, doc después», y añade que documentar sin código ejecutable
«es el fallo histórico que el estándar ya cometió una vez». Las dos cosas se cumplen de
la única forma que no se pudre: **el plano manda porque lo genera el código y una
puerta falla si diverge.** Ni una cifra de este documento se escribe a mano — incluida
la deuda declarada, que vive en el registro `DEUDA_DECLARADA` de este módulo y no en la
prosa del doc. Un plano editable a mano sería, exactamente, el fallo que describe.

## Por qué solo la capa 4 tiene baseline

Las capas 1, 2, 3, 5 y 6 se miden en cero el día que se declaran: sus datos ya existían
y solo faltaba atarlos. La capa 4 no: al cruzar `NORM_CATALOG` con `PUERTAS` y con
`tests/` por primera vez aparecieron 16 normas sin puerta **ni** test. Exigir cero el
primer día habría hecho nacer la puerta en rojo, y una puerta en rojo se desactiva —
esa lección ya se pagó aquí. Baseline indexada por código de norma, que solo encoge.

## Lo que esta tool NO hace

**No reimplementa ningún guard.** Los puertos rotos los dice `vault_arch.puertos_rotos()`,
los contratos `vault_mcp_catalog.check_contracts()` y la trazabilidad del servicio
`vault_servicio.check()`. Si mirara los datos por su cuenta sería una segunda fuente de
verdad sobre el repo (AP-05) midiendo con criterio propio (AP-44) — que es justo lo que
un plano no puede permitirse.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from vault_errors import emit_error, wrap_main

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
DOC = REPO_ROOT / "docs" / "BLUEPRINT.md"
BASELINE = SCRIPTS_DIR / "blueprint-baseline.json"
TESTS_DIR = REPO_ROOT / "tests"


#: Estados admitidos de una deuda declarada. `pendiente` es el único que la deja
#: viva; `saldada` la conserva con la versión que la cerró, porque una deuda que
#: desaparece del registro no se distingue de una que nadie volvió a mirar.
#: No hay `en_curso`: o está saldada y se puede citar la versión, o está
#: pendiente — un estado intermedio sería una promesa, y una promesa no es un
#: dato verificable (AP-37).
ESTADOS_DE_DEUDA = ("pendiente", "saldada")

#: Deuda conocida que **no** se ataca en esta tanda, con el motivo por el que no.
#: Vive aquí y no en la prosa del plano por la misma razón que todo lo demás: una
#: lista de deuda escrita a mano en un documento derivado se queda quieta el día
#: que la deuda se salda, y entonces el plano miente en la dirección cómoda.
#:
#: `estado` y `desde` son obligatorios desde v40.11, y son el mismo argumento
#: llevado un paso más: hasta entonces la lista solo tenía deuda viva, así que
#: «pendiente» era una propiedad implícita de estar en ella. Implícita significa
#: que nadie la comprueba — y el día que una entrada se saldara, la forma natural
#: de anotarlo habría sido borrarla, que es exactamente cómo un registro de deuda
#: deja de servir para nada.
DEUDA_DECLARADA: List[Dict[str, str]] = [
    {
        "id": "envelopes_del_dominio_sin_error_code",
        "estado": "pendiente",
        "desde": "v40.9",
        "capa": "5",
        "que": (
            "Nueve `{\"ok\": False, \"error\": ...}` en `vault/durabilidad/` y "
            "`vault/indices/` que los adaptadores de `scripts/` devuelven tal cual "
            "al consumidor: el envelope sale sin `error_code` ni `recovery`. "
            "Aparecieron en v40.9 al ensanchar el alcance de AP-52 más allá de "
            "`scripts/`, y quedan congelados en `error-contract-baseline.json`."
        ),
        "por_que_no_ahora": (
            "La pregunta de fondo no es cómo se escribe el envelope sino quién lo "
            "escribe: hacer que el dominio importe `vault_errors` lo ata al "
            "catálogo de la herramienta, y convertirlo en el adaptador exige "
            "decidir qué devuelve el dominio en su lugar. Es una decisión de "
            "capas, no un reemplazo de literales."
        ),
    },
    {
        "id": "handler_amplio_en_el_registro_de_la_cli",
        "estado": "pendiente",
        "desde": "v40.9",
        "capa": "5",
        "que": (
            "`cli/registry.py::_load_spec` responde a un `except Exception` con un "
            "vacío indistinguible: un `tool-spec.json` ilegible se presenta como "
            "un catálogo sin entradas (AP-51). Destapado por el mismo ensanche de "
            "alcance de v40.9 y congelado en `blame-baseline.json`."
        ),
        "por_que_no_ahora": (
            "Distinguir «no hay spec» de «la spec no se pudo leer» cambia lo que "
            "`cli doctor` reporta, y esa salida ya la consumen los repos "
            "consumidores. Se toca con su propio test de contrato."
        ),
    },
    {
        "id": "normas_criticas_sin_detector",
        "estado": "pendiente",
        "desde": "v40.11",
        "capa": "4",
        "que": (
            "Cinco normas no las mide nadie y desde v40.11 lo declaran por escrito "
            "en `cobertura_descubierta`: AP-01, AP-02, AP-04, AP-08 y —el titular— "
            "**AP-05, la única `critical` descubierta**. Diecisiete módulos citan "
            "AP-05 en un comentario, al explicar por qué NO copian un dato, y citar "
            "no es detectar: nada mide hoy que el mismo dato aparezca con valores "
            "distintos en varias notas. AP-02 es la variante same-folder, cuyas dos "
            "hermanas —AP-17 y AP-18— sí pesan en el healthIndex."
        ),
        "por_que_no_ahora": (
            "Detectar AP-05 sobre markdown plano, sin embeddings y sin base de "
            "datos, es un problema de diseño abierto, no una tool que falte "
            "escribir: la restricción que lo hace difícil es la misma decisión de "
            "producto que sostiene el estándar. Merece su propia tanda. Lo que "
            "v40.11 sí cierra es lo que era falso: la contradicción del catálogo "
            "(v40.10, AP-55), las 47 afirmaciones de cobertura sin traza, y el "
            "`vault_voice.coverage()` que certificaba el catálogo contra sí mismo."
        ),
    },
    {
        "id": "fronteras_de_escritura_por_contexto",
        "estado": "pendiente",
        "desde": "v40.9",
        "capa": "3",
        "que": (
            "Ningún guard dice qué contexto puede escribir dónde. `00_System` lo "
            "escriben hoy seis contextos."
        ),
        "por_que_no_ahora": (
            "Exige antes sanear `_LLAMADAS_DE_ESCRITURA` —incluye `replace`, que "
            "captura `str.replace`, y `write_report`, que no escribe— y una decisión "
            "de diseño que nadie ha tomado: de quién es `00_System`."
        ),
    },
    {
        "id": "recursion_error_en_parsers",
        "estado": "pendiente",
        "desde": "v40.9",
        "capa": "5",
        "que": (
            "`RecursionError` escapa a `except yaml.YAMLError` en 4 parsers: no es "
            "subclase. Reproducido a 400 corchetes anidados. El peor caso es "
            "`vault_foreign_check`, que es la tool de la regla 7."
        ),
        "por_que_no_ahora": (
            "Es un arreglo de robustez con su propia norma candidata; entra en la "
            "tanda donde se unifiquen los parsers, no en una de alcance."
        ),
    },
    {
        "id": "parsers_de_frontmatter_divergentes",
        "estado": "pendiente",
        "desde": "v40.9",
        "capa": "5",
        "que": (
            "8 parsers de frontmatter distintos; `vault_write.slugify` no delega en "
            "`vault_lib` aunque 20 módulos sí; 6 aliases de v40.8 con el nombre viejo "
            "aún en uso; `--agent default=\"claude\"` en 6 tools frente al AP-16 que "
            "`vault_bug_save` exige."
        ),
        "por_que_no_ahora": (
            "Es AP-50 acumulado y se salda unificando, no parcheando: hacerlo a "
            "medias deja nueve parsers en vez de ocho."
        ),
    },
    {
        "id": "catch_vacios_en_el_servidor_mjs",
        "estado": "pendiente",
        "desde": "v40.9",
        "capa": "7",
        "que": "11 `catch (_) {}` en `mcp/nodejs/vault-mcp-server.mjs` (AP-51 en JS).",
        "por_que_no_ahora": (
            "Los tres audits con baseline miden AST de Python. Un detector de "
            "JavaScript es otro proyecto, y fingir que el alcance lo cubre sería el "
            "mismo cero sobre un subconjunto que esta versión vino a cerrar."
        ),
    },
]


# ── Lectura de los registros (todo por puerto, nada reimplementado) ──────────

def _doc_rel() -> str:
    """Ruta del plano relativa al repo, sin reventar si apunta fuera.

    `relative_to` lanza `ValueError` cuando el destino queda fuera del repo —el
    caso de un test que redirige `DOC` a un temporal—, y un guard que aborta con
    traza en vez de emitir su envelope presenta un fallo propio como si no
    hubiera medida (AP-51).
    """
    try:
        return str(DOC.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(DOC).replace("\\", "/")


def _registros() -> Dict[str, Any]:
    import vault_arch
    import vault_gate
    import vault_mcp_catalog
    import vault_norms
    import vault_servicio

    return {
        "arch": vault_arch,
        "gate": vault_gate,
        "catalog": vault_mcp_catalog,
        "norms": vault_norms,
        "servicio": vault_servicio,
    }


def _leer_baseline() -> Dict[str, Any]:
    if not BASELINE.exists():
        return {"uncovered_norms": []}
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def cobertura_de_normas() -> List[Dict[str, Any]]:
    """Capa 4: por cada norma, qué puerta la hace cumplir y qué tests la nombran.

    La puerta se deriva de `tools_enforcing`/`tools_detecting` cruzado con el script
    de cada entrada de `PUERTAS`. Es la única unión posible sin inventar un campo
    nuevo en el catálogo de normas — y añadir ese campo sería pedirle a la norma que
    conozca al guard, que es la dependencia al revés.
    """
    r = _registros()
    scripts_de_puerta = {p["cmd"][0][:-3]: p["id"] for p in r["gate"].PUERTAS}
    textos = {
        p.name: p.read_text(encoding="utf-8", errors="replace")
        for p in TESTS_DIR.rglob("*.py")
    }

    filas = []
    for norma in r["norms"].NORM_CATALOG:
        code = norma["code"]
        tools = (
            list(norma.get("tools_enforcing", []))
            + list(norma.get("tools_detecting", []))
            + list(norma.get("tools_del_patron", []))
        )
        # `tools_enforcing` admite entradas con paréntesis explicativo
        # ("vault_section_index (guard CN-02)"): el nombre es el primer token.
        puertas = sorted(
            {
                scripts_de_puerta[t.split()[0]]
                for t in tools
                if t.split() and t.split()[0] in scripts_de_puerta
            }
        )
        tests = sorted(f for f, texto in textos.items() if code in texto)
        # Una norma que declara `cobertura_descubierta` no es deuda descubierta
        # por sorpresa: es un hueco escrito, con motivo, y se publica aparte.
        # Mezclarla con las que nadie miró haría que declararse honestamente
        # saliera más caro que callarse.
        motivo = (norma.get("cobertura_descubierta") or "").strip()
        filas.append(
            {
                "code": code,
                "name": norma["name"],
                "enforcement": norma["enforcement"],
                "gates": puertas,
                "tests": tests,
                "covered": bool(puertas or tests),
                "uncovered_declared": motivo or None,
            }
        )
    return filas


def capas() -> Dict[str, Any]:
    """Las siete capas del plano, cada una derivada de su registro."""
    r = _registros()
    servicio = r["servicio"]
    traza = servicio.trazabilidad()
    cobertura = cobertura_de_normas()

    tools_por_grupo: Dict[str, int] = {}
    for fila in traza:
        tools_por_grupo[fila["group"]] = tools_por_grupo.get(fila["group"], 0) + 1

    return {
        "1_servicio": servicio.SERVICIO,
        "2_capacidades": {
            nombre: {
                "titulo": datos["titulo"],
                "resultado": datos["resultado"],
                "nota": datos.get("nota"),
                "grupos": sorted(datos["grupos"]),
                "tools": sum(
                    1 for f in traza if f["capability"] == nombre
                ),
            }
            for nombre, datos in servicio.CAPACIDADES.items()
        },
        "3_contextos": {
            ctx: {
                "titulo": datos["titulo"],
                "puertos": len(datos["puertos"]),
                "modulos": len(datos["modulos"]),
                "prohibe": datos["prohibe"],
            }
            for ctx, datos in r["arch"].CONTEXTS.items()
        },
        "4_normas": cobertura,
        "5_tools": {
            "total": len(traza),
            "grupos": len(tools_por_grupo),
            "por_grupo": dict(sorted(tools_por_grupo.items())),
        },
        "6_trazabilidad": traza,
        "7_deuda": DEUDA_DECLARADA,
    }


# ── El plano ─────────────────────────────────────────────────────────────────

def blueprint() -> str:
    r = _registros()
    c = capas()
    lineas: List[str] = []
    A = lineas.append

    A("# Plano de construcción del estándar")
    A("")
    A("> **Documento derivado. No se edita a mano.**")
    A("> Se regenera con `python scripts/vault_blueprint.py --blueprint` y una puerta")
    A("> falla si diverge de los registros (`--check --strict`). El papel manda porque")
    A("> lo escribe el código: si alguna cifra de aquí se teclea, deja de ser un plano y")
    A("> pasa a ser una opinión con formato de tabla.")
    A("")
    A("La jerarquía va de arriba abajo: el servicio justifica las capacidades, las")
    A("capacidades agrupan las tools, los contextos dicen dónde vive cada una y por dónde")
    A("se habla con ella, las normas dicen qué no puede pasar y las puertas lo impiden.")
    A("Cada capa nombra el registro del que sale — ninguna capa es prosa.")
    A("")

    # ── Capa 1 ──
    s = c["1_servicio"]
    A("## Capa 1 — Servicio de negocio")
    A("")
    A("*Registro: `vault_servicio.SERVICIO`*")
    A("")
    A(f"**{s['titulo']}**")
    A("")
    A(s["declaracion"])
    A("")
    A("Restricciones que son decisión de producto, no limitación pendiente:")
    A("")
    A("| Restricción | Por qué | Declarada en |")
    A("|---|---|---|")
    for rest in s["restricciones"]:
        A(f"| {rest['texto']} | {rest['motivo']} | `{rest['declarada_en']}` |")
    A("")

    # ── Capa 2 ──
    A("## Capa 2 — Capacidades → grupos")
    A("")
    A("*Registro: `vault_servicio.CAPACIDADES` + `vault_mcp_catalog.mapa_de_grupos()`*")
    A("")
    A("| Capacidad | Resultado | Grupos | Tools |")
    A("|---|---|---|---|")
    for nombre, datos in c["2_capacidades"].items():
        grupos = ", ".join(str(g) for g in datos["grupos"])
        A(f"| **{datos['titulo']}** (`{nombre}`) | {datos['resultado']} | {grupos} | {datos['tools']} |")
    A("")
    for nombre, datos in c["2_capacidades"].items():
        if datos.get("nota"):
            A(f"- **`{nombre}`** — {datos['nota']}")
    A("")
    A("Guard: todo grupo del catálogo pertenece a exactamente una capacidad y toda")
    A("capacidad tiene al menos una tool viva (`vault_servicio.py --check --strict`).")
    A("")

    # ── Capa 3 ──
    A("## Capa 3 — Contextos acotados → puertos")
    A("")
    A("*Registro: `vault_arch.CONTEXTS`. El detalle de puertos y cruces vive en")
    A("[`docs/ARQUITECTURA.md`](./ARQUITECTURA.md), que no se absorbe aquí: son dos")
    A("documentos con dos sujetos, y fundirlos habría hecho un solo documento que nadie")
    A("regenera.*")
    A("")
    A("| Contexto | Puertos | Módulos | Prohíbe |")
    A("|---|---|---|---|")
    for ctx, datos in c["3_contextos"].items():
        prohibe = "; ".join(datos["prohibe"]) or "—"
        A(f"| **{datos['titulo']}** (`{ctx}`) | {datos['puertos']} | {datos['modulos']} | {prohibe} |")
    A("")

    # ── Capa 4 ──
    cobertura = c["4_normas"]
    cubiertas = [n for n in cobertura if n["covered"]]
    descubiertas = [n for n in cobertura if not n["covered"]]
    A("## Capa 4 — Normas → puertas → tests")
    A("")
    A("*Registros: `vault_norms.NORM_CATALOG` + `vault_gate.PUERTAS` + `tests/`*")
    A("")
    A(f"{len(cubiertas)} de {len(cobertura)} normas tienen puerta o test que las nombre.")
    A("**Es la única capa con baseline**, y por un motivo concreto: las demás se midieron")
    A("en cero el día que se declararon porque sus datos ya existían y solo faltaba")
    A("atarlos. Ésta no. Exigir cero aquí el primer día habría hecho nacer la puerta en")
    A("rojo, y una puerta en rojo se desactiva.")
    A("")
    A("| Norma | Enforcement | Puertas | Tests |")
    A("|---|---|---|---|")
    for n in cobertura:
        puertas = ", ".join(f"`{p}`" for p in n["gates"]) or "—"
        tests = ", ".join(f"`{t}`" for t in n["tests"]) or "—"
        A(f"| **{n['code']}** — {n['name']} | {n['enforcement']} | {puertas} | {tests} |")
    A("")
    if descubiertas:
        A(f"Sin puerta ni test ({len(descubiertas)}): " + ", ".join(
            f"`{n['code']}`" for n in descubiertas
        ) + ".")
        A("")

    # ── Capa 5 ──
    A("## Capa 5 — Tools → grupos → contrato")
    A("")
    A("*Registros: `vault_mcp_catalog.TOOLS_CATALOG` + `<vault>/00_System/tool-spec.json`*")
    A("")
    A(f"{c['5_tools']['total']} tools activas en {c['5_tools']['grupos']} grupos. Toda tool")
    A("del catálogo tiene entrada de contrato y toda entrada sin catálogo declara")
    A("`status: archived | internal | orphan` — no se borra, se anota")
    A("(`vault_mcp_catalog.py --check-contracts`).")
    A("")
    A("| Grupo | Tools |")
    A("|---|---|")
    for grupo, n in c["5_tools"]["por_grupo"].items():
        A(f"| {grupo} | {n} |")
    A("")

    # ── Capa 6 ──
    A("## Capa 6 — Trazabilidad")
    A("")
    A("*Derivada de las capas anteriores: `tool → grupo → capacidad → servicio`*")
    A("")
    A("Una tool sin capacidad no tiene contra qué justificarse, y es así como un catálogo")
    A("crece por acumulación. La cadena se exige entera: si un eslabón falta, la puerta")
    A("falla — no se rellena con el valor más cercano.")
    A("")
    A("| Tool | Grupo | Capacidad |")
    A("|---|---|---|")
    for fila in c["6_trazabilidad"]:
        A(f"| `{fila['tool']}` | {fila['group_id']} — {fila['group']} | {fila['capability']} |")
    A("")

    # ── Capa 7 ──
    A("## Capa 7 — Deuda viva")
    A("")
    A("*Registro: `vault_blueprint.DEUDA_DECLARADA` + las baselines de `scripts/`*")
    A("")
    A("Deuda **declarada**: conocida, medida y con motivo escrito de por qué no se ataca")
    A("todavía. Lo que no está aquí no es que no exista — es que nadie lo ha medido, que")
    A("es una situación distinta y peor.")
    A("")
    pendientes = sum(1 for d in c["7_deuda"] if d.get("estado") == "pendiente")
    A(f"**{pendientes} pendientes** de {len(c['7_deuda'])} declaradas. Una deuda saldada no")
    A("desaparece de la tabla: se queda con `estado: saldada` y la versión que la cerró,")
    A("porque una entrada borrada no se distingue de una que nadie volvió a mirar.")
    A("")
    A("| Deuda | Estado | Desde | Capa | Qué | Por qué no ahora |")
    A("|---|---|---|---|---|---|")
    for d in c["7_deuda"]:
        A(f"| `{d['id']}` | {d.get('estado', '—')} | {d.get('desde', '—')} "
          f"| {d['capa']} | {d['que']} | {d['por_que_no_ahora']} |")
    A("")
    A("| Baseline | Norma | Congelado |")
    A("|---|---|---|")
    for fichero, clave, norma in _BASELINES:
        ruta = SCRIPTS_DIR / fichero
        if not ruta.exists():
            continue
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        valor = datos.get(clave)
        total = len(valor) if isinstance(valor, (list, dict)) else valor
        A(f"| `scripts/{fichero}` | {norma} | {total} |")
    A("")
    A("Todas encogen y ninguna crece sin decirlo: los tres audits con baseline indexan")
    A("por firma de sitio —`módulo::función::hash de `ast.unparse``— así que mover un")
    A("sitio ya no lo estrena como deuda nueva, y `--freeze` se niega a congelar lo que")
    A("no tiene precedente salvo con `--admitir-nuevos`, que además lo lista.")
    A("")
    A("---")
    A("")
    A(f"*{len(r['gate'].PUERTAS)} puertas de cierre. Generado por "
      "`scripts/vault_blueprint.py`.*")
    return "\n".join(lineas) + "\n"


#: Las baselines del repo, con la clave donde vive la lista y la norma que sostienen.
_BASELINES = [
    ("arch-baseline.json", "crossings", "cruces entre contextos"),
    ("arch-baseline.json", "off_port_crossings", "cruces fuera de puerto"),
    ("blame-baseline.json", "sites", "AP-51"),
    ("error-contract-baseline.json", "sites", "AP-52"),
    ("noop-baseline.json", "tools", "AP-37"),
    ("smoke-baseline.json", "failing", "AP-42"),
    ("blueprint-baseline.json", "uncovered_norms", "capa 4 — norma sin puerta ni test"),
]


# ── Guards ───────────────────────────────────────────────────────────────────

def check(strict: bool = False) -> Dict[str, Any]:
    r = _registros()
    problemas: List[Dict[str, str]] = []

    # 1. El doc publicado no diverge de los registros.
    if not DOC.exists():
        problemas.append(
            {"kind": "plano_ausente", "detail": "docs/BLUEPRINT.md no existe — "
             "genera con `python scripts/vault_blueprint.py --blueprint`"}
        )
    elif DOC.read_text(encoding="utf-8").strip() != blueprint().strip():
        problemas.append(
            {"kind": "plano_desactualizado", "detail": "docs/BLUEPRINT.md difiere de "
             "los registros — regenera con `--blueprint`. Si el cambio se escribió a "
             "mano en el doc, se pierde: el registro es la fuente"}
        )

    # 2. Las capas 2, 3 y 5 delegan en el guard de su registro. No se remide.
    traza = r["servicio"].check()
    if not traza["ok"]:
        problemas.append(
            {"kind": "trazabilidad_rota",
             "detail": f"vault_servicio --check falla: {traza['orphan_groups']} "
                       f"{traza['unknown_groups']} {traza['empty_capabilities']}"}
        )
    rotos = r["arch"].puertos_rotos()
    if rotos:
        problemas.append(
            {"kind": "puertos_rotos", "detail": f"{len(rotos)} puertos apuntan a un "
             "símbolo que no existe (`vault_arch --check`)"}
        )

    # 3. Capa 4 contra la baseline: solo puede encoger.
    base = set(_leer_baseline().get("uncovered_norms", []))
    descubiertas = {n["code"] for n in cobertura_de_normas() if not n["covered"]}
    nuevas = sorted(descubiertas - base)
    saldadas = sorted(base - descubiertas)
    if nuevas:
        problemas.append(
            {"kind": "norma_sin_puerta_ni_test", "detail": ", ".join(nuevas)}
        )

    # 4. Toda deuda declarada dice en qué estado está y desde cuándo. Sin esto,
    #    «pendiente» sería una propiedad implícita de aparecer en la lista, y una
    #    propiedad implícita no la comprueba nadie: el día que una se salde, la
    #    forma cómoda de anotarlo es borrarla, y ahí el registro deja de servir.
    for d in DEUDA_DECLARADA:
        estado = d.get("estado")
        if estado not in ESTADOS_DE_DEUDA:
            problemas.append(
                {"kind": "deuda_sin_estado",
                 "detail": f"{d['id']}: estado {estado!r} no está en "
                           f"{list(ESTADOS_DE_DEUDA)}"}
            )
        if not (d.get("desde") or "").strip():
            problemas.append(
                {"kind": "deuda_sin_version",
                 "detail": f"{d['id']}: no dice desde qué versión se arrastra"}
            )

    ok = not problemas
    resultado = {
        "ok": ok,
        "tool": "vault_blueprint",
        "action": "check",
        "layers": 7,
        "doc": _doc_rel(),
        "norms_total": len(r["norms"].NORM_CATALOG),
        "norms_uncovered": len(descubiertas),
        "norms_uncovered_baseline": len(base),
        "new_uncovered_norms": nuevas,
        "settled_uncovered_norms": saldadas,
        "declared_debt": len(DEUDA_DECLARADA),
        # Publicado por separado y no solo como total: el número de deudas
        # declaradas baja igual si una se salda que si alguien la borra, así que
        # por sí solo no dice nada. Lo que se lee es cuántas siguen vivas.
        "declared_debt_pending": sum(
            1 for d in DEUDA_DECLARADA if d.get("estado") == "pendiente"),
        "declared_debt_settled": sorted(
            d["id"] for d in DEUDA_DECLARADA if d.get("estado") == "saldada"),
        "problems": problemas,
        "hint": (
            "Una norma nueva sin puerta ni test no se congela: se le escribe el test. "
            "La baseline existe para la deuda que ya estaba, no para la que entra hoy."
        ),
    }
    if strict and not ok:
        resultado["exit_code"] = 1
    return resultado


def freeze(admitir_nuevos: bool = False) -> Dict[str, Any]:
    """Congela la deuda de la capa 4. Se niega a estrenar deuda sin `--admitir-nuevos`.

    Mismo contrato que los tres audits desde v40.6, y por el mismo motivo: un
    `--freeze` que acepta cualquier cosa convierte la baseline en un registro de lo
    que hay, que es lo contrario de un techo.
    """
    base = set(_leer_baseline().get("uncovered_norms", []))
    descubiertas = {n["code"] for n in cobertura_de_normas() if not n["covered"]}
    nuevas = sorted(descubiertas - base)
    if nuevas and not admitir_nuevos:
        salida = emit_error(
            "vault_blueprint",
            "DEBT_WOULD_GROW",
            f"{len(nuevas)} normas sin puerta ni test que no estaban congeladas: "
            + ", ".join(nuevas),
        )
        salida["new_uncovered_norms"] = nuevas
        return salida

    BASELINE.write_text(
        json.dumps(
            {
                "norm": "capa 4 del plano",
                "description": (
                    "Normas sin puerta que las haga cumplir ni test que las nombre. "
                    "Indexada por código de norma. Esta lista solo puede ENCOGER: una "
                    "norma nueva sin cobertura no se congela, se le escribe el test."
                ),
                "uncovered_norms": sorted(descubiertas),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "ok": True,
        "tool": "vault_blueprint",
        "action": "freeze",
        "uncovered_norms": len(descubiertas),
        "admitted_new": nuevas if admitir_nuevos else [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plano de construcción: registros atados y verificados"
    )
    parser.add_argument("--blueprint", action="store_true", help="regenera docs/BLUEPRINT.md")
    parser.add_argument("--check", action="store_true", help="el doc y la trazabilidad")
    parser.add_argument("--strict", action="store_true", help="exit 1 si falla")
    parser.add_argument("--freeze", action="store_true", help="congela la deuda de la capa 4")
    parser.add_argument(
        "--admitir-nuevos", action="store_true",
        help="permite congelar normas sin cobertura que no tenían precedente",
    )
    parser.add_argument("--layers", action="store_true", help="las 7 capas en JSON")
    args = parser.parse_args()

    if args.blueprint:
        DOC.parent.mkdir(parents=True, exist_ok=True)
        texto = blueprint()
        # AP-37: `changed` distingue «regeneré el plano» de «el plano ya estaba
        # al día». Sin ese dato, una regeneración que no toca nada y otra que
        # reescribe el documento entero devuelven el mismo `ok: true`, y quien
        # llama no puede saber cuál de las dos ocurrió.
        anterior = DOC.read_text(encoding="utf-8") if DOC.exists() else None
        DOC.write_text(texto, encoding="utf-8", newline="\n")
        salida: Dict[str, Any] = {
            "ok": True,
            "tool": "vault_blueprint",
            "action": "blueprint",
            "doc": _doc_rel(),
            "changed": 0 if anterior == texto else 1,
            "lines": texto.count("\n"),
        }
    elif args.freeze:
        salida = freeze(admitir_nuevos=args.admitir_nuevos)
    elif args.layers:
        salida = {"ok": True, "tool": "vault_blueprint", "layers": capas()}
    else:
        salida = check(strict=args.strict)

    print(json.dumps(salida, indent=2, ensure_ascii=False))
    return 1 if (args.strict and not salida.get("ok")) else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_blueprint"))
