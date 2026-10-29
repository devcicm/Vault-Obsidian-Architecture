#!/usr/bin/env python3
"""vault_doc_sync — guard anti-drift de NOMBRES entre el registro y scripts/README.md.

`vault_doc_counts` vigila las cifras; esta tool vigila los nombres, que es la
otra mitad del mismo problema. El síntoma que la originó, medido en v39:

  - 19 tools del catálogo no tenían sección propia en `scripts/README.md`.
    Existían, se podían invocar por MCP, y la referencia de tools no las
    mencionaba. Nadie lo notó porque nada lo comprobaba.
  - El índice tenía 30 filas para 35 grupos.
  - La fila "Grupo 34 — Gestión de Carpetas" apuntaba a un ancla inexistente:
    la sección 34 real es "Memoria de Contexto". Un enlace roto dentro del
    propio documento, estable durante versiones.

Qué comprueba:

  1. Toda tool de `TOOLS_CATALOG` tiene su encabezado `### <nombre>`.
  2. Todo encabezado `###` de tool corresponde a una tool que existe.
  3. Toda clave de `GROUPS` tiene su sección `## Grupo N — <clave>`.
  4. La numeración `Grupo N` no se repite.
  5. El índice tiene exactamente una fila por sección, con el mismo número y
     etiqueta, ancla resuelta, y las tools de `GROUPS` en la fila.
  6. Todo comando `python scripts/X.py --flag` que la documentación publica
     existe y acepta esos flags.
  7. Toda receta `vault_x --flag` que el **código** entrega —ejemplos del
     catálogo MCP, `nextActions`, `tool_hint`, plantillas de vault_sdd_init—
     usa flags que la tool acepta (ver `recetas_en_codigo`).

La sexta llegó tarde y con factura. `AGENTS.md` publicaba
`vault_audit.py --root vault-sandbox` y `vault_quality_check.py --root ...` en
su sección de comandos habituales: ninguno de los dos acepta `--root`, así que
el comando que un agente copia para medir la salud del vault moría en
`unrecognized arguments`. Y lo contradecía su propia regla 1, tres pantallas más
arriba, que dice que solo cuatro tools aceptan `--root` y que el destino se
fuerza con `VAULT_ROOT`. Un comando publicado que nadie ejecuta es AP-42; que
además fuese el de la salud lo dejó invisible hasta que se corrió a mano.

Se comprueba de forma estática —los flags declarados en `add_argument`— y no
ejecutando: varios de estos comandos escriben.

El encabezado de sección usa la **clave literal de `GROUPS`**. Es deliberado:
un título más bonito en el README crea un cuarto vocabulario de grupos, y ya
hubo tres conviviendo (etiqueta `group` de la tool, clave de `GROUPS`, título
del README). La clave manda; el documento la refleja.

Uso:
    python vault_doc_sync.py --check
    python vault_doc_sync.py --check --strict    # exit 1 (gate de CI)
    python vault_doc_sync.py --fix               # regenera la tabla de índice
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import vault_grafo_import  # noqa: E402
from vault.kernel import rutas  # noqa: E402
from vault.kernel.rutas import cita_repo  # noqa: E402
from vault_errors import emit_error  # noqa: E402
from vault_mcp_catalog import GROUPS, TOOLS_CATALOG  # noqa: E402
from vault.meta_toolkit import flags_cli  # extractor único de add_argument (v41.9)  # noqa: E402
from vault.meta_toolkit.catalogo_producto import catalogo_producto  # noqa: E402

_RE_VAULT_DOC_SYNC_1 = re.compile('--[A-Za-z][\\w-]*')

README = Path(__file__).resolve().parent / "README.md"
DISPONIBILIDAD = Path(__file__).resolve().parent.parent / rutas.DOCS / "DISPONIBILIDAD-DE-TOOLS.md"
TOOL_SPEC = Path(__file__).resolve().parent.parent / "vault-sandbox" / "00_System" / "tool-spec.json"
AUDITORIA = Path(__file__).resolve().parent / "toolkit-audit-last.json"
README_RAIZ = Path(__file__).resolve().parent.parent / "README.md"
CATALOGO_MCP = Path(__file__).resolve().parent.parent / "mcp" / "nodejs" / "tools-catalog.json"

RE_SECTION = re.compile(r"^## Grupo (\d+) — (.+?)\s*$", re.M)
RE_TOOL_HEADING = re.compile(r"^### `?(vault_[a-z0-9_]+)", re.M)
RE_INDEX_ROW = re.compile(r"^\| \[Grupo (\d+) — (.+?)\]\((#[^)]*)\) \| (.*?) \|$", re.M)


def anchor(number: int, label: str) -> str:
    """Slug estilo GitHub del encabezado `## Grupo N — <label>`."""
    text = f"grupo {number} — {label}".lower()
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[^\w\sÀ-ɏ-]", "", text, flags=re.UNICODE)
    return "#" + text.replace(" ", "-")


def index_row(number: int, label: str, tools: List[str]) -> str:
    return (
        f"| [Grupo {number} — {label}]({anchor(number, label)}) "
        f"| {', '.join(tools)} |"
    )


REPO_ROOT = Path(__file__).resolve().parent.parent

# Documentos que le dicen a un agente qué comando teclear. Si mienten, el
# agente pierde el turno en un `unrecognized arguments`.
#
# `vault-obsidian-architecture.md` está fuera **a propósito**, y no por
# descuido: su changelog cita comandos rotos como prueba del defecto que
# describe. La entrada de v40.4 reproduce literalmente las dos líneas con
# `--root` que originaron este guard. Incluirlo obligaría al changelog a dejar
# de mostrar el fallo que documenta — el guard no distingue un comando que se
# dicta de uno que se exhibe. Se comprobó: los únicos tres positivos fuera de
# esta lista son esas dos citas y una copia de backup que no se toca.
#
# Desde v40.9 entra también el documento de comandos que el estándar **genera**
# (`vault_section_index` lo escribe en `<vault>/00_System/vault-commands.md`).
# Publicaba `vault_restore.py --name`, un flag que la tool no acepta, y no lo
# publicaba en un doc: lo repartía a cada vault creado. El guard de v40.4 medía
# los documentos escritos a mano y era ciego justo a la copia que viaja.
DOCS_CON_COMANDOS = (
    "AGENTS.md",
    "README.md",
    "scripts/README.md",
    f"{rutas.SANDBOX}/00_System/vault-commands.md",
)

# `scripts/` es opcional: `scripts/README.md` publica sus ejemplos como
# `python vault_read.py --note X`, que es la forma en que se ejecutan con el
# CWD dentro de `scripts/`. Exigir el prefijo dejaba fuera de la medida justo
# el documento que más comandos publica — la referencia de tools por grupo.
RE_COMANDO = re.compile(
    r"python\s+(?:scripts/)?([a-z0-9_]+\.py)((?:\s+--?[a-zA-Z0-9_-]+(?:[ =][^\s`|#]+)?)*)"
)
RE_FLAG_USADO = re.compile(r"(?<![\w-])--[a-zA-Z][a-zA-Z0-9_-]*")
# La invocación sin sus flags: los flags los lee `_flags_de_receta`, que
# tokeniza respetando comillas. `RE_COMANDO` paraba en el primer valor entre
# comillas con espacios —`--title "Q1 2026 Test Plan"`— y todo flag posterior
# quedaba sin medir (v41.3). Se conserva: lo citan los tests y otros módulos.
RE_INVOCACION = re.compile(r"python\s+(?:scripts/)?([a-z0-9_]+\.py)")
RE_FLAG_DECLARADO = re.compile(r"""add_argument\(\s*["'](--[a-zA-Z][a-zA-Z0-9_-]*)["']""")


def _flags_declarados(script: Path) -> set:
    """Los flags que el script acepta, leídos de sus `add_argument`.

    Estático a propósito: importar o ejecutar 96 scripts para preguntarles su
    parser tendría side effects, y varios de los comandos documentados escriben
    en el vault. Un parser construido en una función auxiliar que este regex no
    vea daría un falso positivo, no un falso negativo — el guard se equivocaría
    hacia el lado que se nota.

    Un script migrado es un alias en `sys.modules` (deuda #12) que no declara
    nada: quien lo ejecuta corre el parser del dueño, así que se lee el dueño
    con `vault_grafo_import.fuente_de`, el criterio del import (AP-44).
    """
    if script.parent.resolve() == (REPO_ROOT / "scripts").resolve():
        script = vault_grafo_import.fuente_de(script.stem)
    src = script.read_bytes().decode("utf-8", "replace")
    # El extractor único (v41.9): el regex veía solo el primer nombre de la
    # llamada y daba `--no-x` a todo flag si el fichero nombraba
    # `BooleanOptionalAction` en cualquier sitio.
    return {f for f in flags_cli.flags_aceptados(src) if f.startswith("--")}


def lineas_logicas(texto: str) -> List[tuple]:
    """`(número de la primera línea, línea)` con las continuaciones unidas.

    El shell une una línea que acaba en `\\` con la siguiente antes de
    ejecutarla, y quien copia un ejemplo de varias líneas ejecuta la línea
    unida. Medir línea a línea veía solo el primer trozo: los flags de las
    siguientes no se comprobaban nunca. Medido en v41.3: nueve ejemplos de
    `scripts/README.md` con flags que su tool rechaza —`--decision` en
    `vault_ai_decision`, `--ip` en `vault_infra_save`, `--content` en
    `vault_qa_save`…—, todos
    partidos con `\\` y todos en verde (AP-44: el guard leía el documento
    como un fichero de texto, no como lo lee el shell).
    """
    salida: List[tuple] = []
    inicio, partes = None, []
    for numero, linea in enumerate(texto.splitlines(), 1):
        if inicio is None:
            inicio = numero
        recortada = linea.rstrip()
        if recortada.endswith("\\"):
            partes.append(recortada[:-1])
            continue
        partes.append(linea)
        salida.append((inicio, " ".join(partes)))
        inicio, partes = None, []
    if partes:
        salida.append((inicio, " ".join(partes)))
    return salida


def comandos_publicados() -> List[Dict]:
    """AP-42 en la documentación: comandos que se publican y no corren."""
    problems: List[Dict] = []
    for doc in DOCS_CON_COMANDOS:
        ruta = REPO_ROOT / doc
        if not ruta.exists():
            continue
        for numero, linea in lineas_logicas(
            ruta.read_bytes().decode("utf-8", "replace")
        ):
            for m in RE_INVOCACION.finditer(linea):
                # El grupo ya no trae el prefijo: se ancla siempre en scripts/.
                script = REPO_ROOT / "scripts" / m.group(1)
                donde = f"{doc}:{numero}"
                if not script.exists():
                    problems.append({"kind": "comando_sin_script",
                                     "detail": f"{donde} — scripts/{m.group(1)} no existe"})
                    continue
                declarados = _flags_declarados(script)
                for flag in _flags_de_receta(linea[m.end():]):
                    if flag not in declarados and flag != "--help":
                        problems.append({
                            "kind": "flag_no_aceptado",
                            "detail": f"{donde} — {m.group(1)} no acepta {flag}",
                        })
    return problems


# Séptima comprobación (2026-10-02). La sexta medía los `.md` escritos a mano y
# era ciega a las recetas que de verdad llegan al agente: el `example` del
# catálogo MCP, `nextActions` del audit, el `tool_hint` del registro de
# carpetas, la siguiente acción de `vault/autoria/voz.py` y las tablas que
# `vault_sdd_init` reparte a cada vault. Medidas ese día: 46 sitios con un
# flag que la tool no acepta — `vault_audit --broken-links`,
# `vault_norms --explain`, `vault_restore --backup`, `vault_fix_brackets --fix`.
# Se leen los literales por AST, no las líneas: un comentario que *cita* un
# flag roto para explicar por qué no existe no es una receta.
ZONAS_DE_RECETAS = (rutas.SCRIPTS, "vault", rutas.CLI)

# Sitios que exhiben un comando roto como prueba del defecto que documentan,
# igual que el changelog del manifiesto. Mundo cerrado: una entrada que ya no
# aparece falla el test, así que la tabla solo encoge.
RECETAS_EXHIBIDAS = {
    (cita_repo(rutas.SCRIPTS, "vault_doc_sync.py"), "vault_audit", "--root"):
        "el docstring cita el comando que originó la comprobación 6",
    (cita_repo(rutas.SCRIPTS, "vault_doc_sync.py"), "vault_quality_check", "--root"):
        "el docstring cita el comando que originó la comprobación 6",
}

VERBOS_CON_TOOL = {"show", "exec", "validate", "run"}
RE_TOOL_EN_TEXTO = re.compile(r"(?<![\w.-])(vault_[a-z0-9_]+)(?:\.py)?(?![\w.])")
RE_TOKEN = re.compile(r"\"[^\"\n]*\"|'[^'\n]*'|<[^>\n]*>|[^\s]+")
_CIERRE = "`),;:|."


def _literales(tree) -> List[tuple]:
    """(línea, texto) de cada literal de cadena; los f-strings con `<x>` en sus huecos."""
    import ast

    dentro_de_fstring = set()
    salida = []
    for nodo in ast.walk(tree):
        if isinstance(nodo, ast.JoinedStr):
            partes = []
            for v in nodo.values:
                dentro_de_fstring.add(id(v))
                partes.append(v.value if isinstance(v, ast.Constant) else "<x>")
            salida.append((nodo.lineno, "".join(str(p) for p in partes)))
    for nodo in ast.walk(tree):
        if (isinstance(nodo, ast.Constant) and isinstance(nodo.value, str)
                and id(nodo) not in dentro_de_fstring):
            salida.append((nodo.lineno, nodo.value))
    return salida


def _flags_de_receta(resto: str) -> List[str]:
    """Los flags de la invocación que empieza en `resto`: `(--flag valor?)*`.

    Se para en lo que deja de ser la misma invocación —`&&`, una tubería, el
    cierre de un span de código o la primera palabra que no es flag ni valor
    de uno—, para no cargarle a una tool los flags de la siguiente.
    """
    flags: List[str] = []
    espera_valor = False
    for tok in RE_TOKEN.findall(resto.split("\n", 1)[0]):
        if tok in ("&&", "||", "|", ";", "+", "→", "->"):
            break
        limpio = tok.rstrip(_CIERRE)
        if _RE_VAULT_DOC_SYNC_1.fullmatch(limpio):
            flags.append(limpio)
            espera_valor = True
        elif espera_valor:
            espera_valor = False
        else:
            break
        if limpio != tok:
            break
    return flags


def recetas_en_codigo(raices=None, repo_root: Path = None) -> List[Dict]:
    """AP-42 en el código: recetas `vault_x --flag` con un flag que la tool no acepta."""
    import ast

    repo_root = repo_root or REPO_ROOT
    scripts = REPO_ROOT / "scripts"
    flags_cache: Dict[str, set] = {}
    problems: List[Dict] = []
    for zona in raices or ZONAS_DE_RECETAS:
        for ruta in sorted((repo_root / zona).rglob("*.py")):
            if "__pycache__" in ruta.parts:
                continue
            rel = ruta.relative_to(repo_root).as_posix()
            try:
                tree = ast.parse(ruta.read_bytes().decode("utf-8", "replace"))
            except SyntaxError:
                continue
            for linea0, texto in _literales(tree):
                for m in RE_TOOL_EN_TEXTO.finditer(texto):
                    script = scripts / f"{m.group(1)}.py"
                    if not script.exists():
                        continue
                    # `--tool vault_write --summary`, `cli show vault_write --pretty`,
                    # `vault_mcp.py exec vault_write --params`: ahí el nombre es el
                    # argumento de otro comando, y los flags son de ese otro.
                    previa = texto[:m.start()].rstrip().rsplit(None, 1)
                    if previa and (previa[-1].startswith("--") or previa[-1] in VERBOS_CON_TOOL):
                        continue
                    if m.group(1) not in flags_cache:
                        flags_cache[m.group(1)] = _flags_declarados(script)
                    for flag in _flags_de_receta(texto[m.end():]):
                        if flag in flags_cache[m.group(1)] or flag == "--help":
                            continue
                        if (rel, m.group(1), flag) in RECETAS_EXHIBIDAS:
                            continue
                        linea = linea0 + texto.count("\n", 0, m.start())
                        problems.append({
                            "kind": "receta_flag_no_aceptado",
                            "detail": f"{rel}:{linea} — {m.group(1)} no acepta {flag}",
                            "sitio": (rel, m.group(1), flag),
                        })
    return problems


# ── Disponibilidad de las tools (docs/DISPONIBILIDAD-DE-TOOLS.md) ────────────

#: Tools activas que cambian o borran estado y que un agente no debe lanzar sin
#: haber leído antes su salida en seco. El motivo se escribe aquí, a mano, porque
#: ningún campo del catálogo dice «destructiva»: `side_effects` es prosa libre.
#: Una clave que deje de ser una tool activa rompe `scan` (disponibilidad_cuidado_huerfano).
TOOLS_DE_CUIDADO: Dict[str, str] = {
    "vault_delete": "Borra la nota (o la manda a `20_Quarantine/` con `--trash-only`); deja change-log y copia en `.history/`, y `--dry-run` muestra el efecto antes.",
    "vault_restore": "Sobrescribe archivos del vault con los de una copia; exige `confirm`.",
    "vault_restore_base64": "Restaura a un directorio nuevo sin tocar el original; exige `--confirm true`. Cuidado con el espacio que ocupa, no con el original.",
    "vault_undo": "Por defecto restaura sin sobrescribir; con `--force` sobrescribe la nota actual.",
    "vault_migrate_rollback": "Revierte una migración ya hecha; exige `confirm`.",
    "vault_history_compact": "Con `--apply` borra versiones de `.history/` (conserva las N más recientes); lo borrado no se recupera.",
    "vault_quarantine": "Mueve la nota a `20_Quarantine/` y anota el movimiento en el libro append-only; `--restore` la devuelve.",
    "vault_mermaid_check": "Con `--fix` (sin `--dry-run`) reescribe los `.md` cuyo bloque Mermaid corrige.",
    "vault_fix_all": "Regenera artefactos derivados del checkout del estándar (catálogos, planos, documentación); no es de un vault.",
}


def _spec_no_activas() -> Dict[str, Dict]:
    """Las tools del `tool-spec.json` que no están activas, con su estado y motivo."""
    try:
        tools = json.loads(TOOL_SPEC.read_text(encoding="utf-8")).get("tools", {})
    except (OSError, ValueError):
        return {}
    return {n: t for n, t in sorted(tools.items()) if t.get("status") != "active"}


def _catalogo_mcp() -> Dict[str, Dict]:
    """Las tools tal como las publica `tools-catalog.json` (`exposed_via_mcp`, `side_effects`)."""
    try:
        return json.loads(CATALOGO_MCP.read_text(encoding="utf-8")).get("tools", {})
    except (OSError, ValueError):
        return {}


def _veredictos_de_auditoria() -> Dict[str, Dict]:
    """Veredicto y motivos por tool de la última corrida de `vault_toolkit_audit`."""
    try:
        resultados = json.loads(AUDITORIA.read_text(encoding="utf-8")).get("results", [])
    except (OSError, ValueError):
        return {}
    return {r["tool"]: r for r in resultados if "tool" in r}


def _reemplazo(t: Dict) -> str:
    destino = t.get("superseded_by") or t.get("replaced_by") or "—"
    return "`{}`".format(destino) if re.fullmatch(r"vault_\w+", destino) else destino


def _celda(texto) -> str:
    return " ".join(str(texto).split()).replace("|", "\\|")


def disponibilidad_texto() -> str:
    """El documento completo, derivado de los registros. No inventa nada."""
    producto = catalogo_producto()
    no_activas = _spec_no_activas()
    auditoria = _veredictos_de_auditoria()
    publicadas = _catalogo_mcp()

    runtime_cli = [n for n, t in producto.items() if t.clase == "runtime" and t.via == rutas.CLI]  # el canal CLI se llama como la carpeta
    runtime_mcp = [n for n, t in producto.items() if t.clase == "runtime" and t.via == "mcp"]
    mantenimiento = [n for n, t in producto.items() if t.clase != "runtime"]
    expuestas = [n for n in producto if publicadas.get(n, {}).get("exposed_via_mcp")]
    internas = {n: t for n, t in no_activas.items() if t.get("status") == "internal"}
    archivadas = {n: t for n, t in no_activas.items() if t.get("status") == "archived"}
    no_ok = {n: r for n, r in auditoria.items() if r.get("veredicto") != "OK"}

    def fila(n: str) -> str:
        t = publicadas.get(n, {})
        efectos = [e for e in (t.get("side_effects") or []) if e]
        return "| `{}` | {} | {} | {} | {} |".format(
            n, _celda(producto[n].grupo), "sí" if t.get("exposed_via_mcp") else "no",
            "sí" if efectos else "no", auditoria.get(n, {}).get("veredicto", "sin dato"))

    cab = "| Tool | Grupo | MCP | Escribe | Ejemplo verificado |\n|---|---|---|---|---|"
    out: List[str] = []
    w = out.append
    w("# Disponibilidad de las tools\n")
    w("> **Documento derivado.** Sale de `vault_mcp_catalog.TOOLS_CATALOG`, del catálogo de producto "
      "(`vault.meta_toolkit.catalogo_producto`), de `vault-sandbox/00_System/tool-spec.json` y de "
      "`scripts/toolkit-audit-last.json`. Se regenera con `python scripts/vault_doc_sync.py --fix` y "
      "`--check` falla si diverge: lo escrito a mano aquí se pierde. El motivo de cada tool «de cuidado» "
      "vive en `vault_doc_sync.TOOLS_DE_CUIDADO`.\n")
    w("Responde tres preguntas sobre cada tool: **dónde se puede usar**, **si hay evidencia de que "
      "funciona** y **cuándo no debe usarse y por qué**.\n")
    w("## En una tabla\n")
    w("| Categoría | Cuántas | Dónde corre | Quién la usa |\n|---|---|---|---|")
    w("| Operaciones del vault por CLI | {} | `vault run <tool>` desde la wheel instalada; por MCP las que estén expuestas | agentes y personas con un vault |".format(len(runtime_cli)))
    w("| Operaciones del vault solo por MCP | {} | servidor MCP (JavaScript nativo); `vault run` no las ejecuta | agentes por MCP |".format(len(runtime_mcp)))
    w("| Mantenimiento del estándar | {} | solo en un checkout de este repo (`python scripts/<tool>.py`); la wheel no las instala | quien mantiene el estándar |".format(len(mantenimiento)))
    w("| Internas | {} | no son tools de un vault: librerías, registros o CLIs de diagnóstico del toolkit | nadie desde fuera |".format(len(internas)))
    w("| Archivadas | {} | no se ejecutan; cada una nombra su reemplazo | nadie |".format(len(archivadas)))
    w("")
    w("Las {} activas son {} + {} + {}. Expuestas por el servidor MCP: **{}**; las otras {} se ejecutan por CLI o en el checkout.\n".format(
        len(producto), len(runtime_cli), len(runtime_mcp), len(mantenimiento), len(expuestas), len(producto) - len(expuestas)))
    w("`vault tools list` dice lo mismo desde la wheel: `class: runtime` con `installed: true` es lo que corre; "
      "`class: maintenance` con `installed: false` es del checkout, y `vault run` la rechaza con `not_runtime_operation`.\n")

    w("## 1. Disponibles y funcionales\n")
    w("«Ejemplo verificado» es el veredicto de `vault_toolkit_audit` (AP-42): el ejemplo documentado de la tool "
      "se ejecuta de verdad sobre una copia del sandbox y su envelope cubre el contrato. `OK` es evidencia de "
      "que funciona **en ese ejemplo**, no de que cubra todos los argumentos. «Escribe» indica que la tool "
      "declara efectos sobre disco.\n")
    w("### 1.1 Operaciones del vault por CLI (y por MCP si se indica)\n")
    w(cab)
    for n in sorted(runtime_cli):
        w(fila(n))
    w("")
    w("### 1.2 Operaciones solo por MCP\n")
    w("Las sirve el servidor MCP con JavaScript nativo; `vault run` responde que no están instaladas en la CLI.\n")
    w(cab)
    for n in sorted(runtime_mcp):
        w(fila(n))
    w("")
    w("### 1.3 Mantenimiento del estándar (solo en el checkout)\n")
    w("Comprueban o regeneran este repositorio. **No** operan el vault de nadie y no están en la wheel; "
      "lanzarlas contra un vault real no es su uso.\n")
    w(cab)
    for n in sorted(mantenimiento):
        w(fila(n))
    w("")

    w("## 2. Sin evidencia de ejemplo\n")
    if no_ok:
        w("Activas, pero `vault_toolkit_audit` no puede ejercitarlas con un ejemplo de CLI. No significa que fallen: "
          "significa que esa puerta no las prueba, y el motivo es:\n")
        w("| Tool | Veredicto | Motivo |\n|---|---|---|")
        for n, r in sorted(no_ok.items()):
            w("| `{}` | {} | {} |".format(n, r.get("veredicto"), _celda("; ".join(r.get("motivos") or []))))
    else:
        w("Ninguna: todas las activas tienen un ejemplo que se ejecuta y cubre su contrato.")
    w("")

    w("## 3. Úsalas con cuidado\n")
    w("Activas y funcionales, pero cambian o borran estado. Léelas antes de lanzarlas y, si tienen `--dry-run`, "
      "empieza por ahí.\n")
    w("| Tool | Dónde corre | Por qué cuidado |\n|---|---|---|")
    for n, motivo in sorted(TOOLS_DE_CUIDADO.items()):
        via = producto[n].via if n in producto else "?"
        donde = "wheel (`vault run`)" if via == rutas.CLI else ("MCP" if via == "mcp" else "checkout")
        w("| `{}` | {} | {} |".format(n, donde, _celda(motivo)))
    w("")

    w("## 4. No las uses\n")
    w("### 4.1 Archivadas\n")
    w("Siguen en el registro por la política de no-derogación (se anota el reemplazo, no se borra). "
      "No se ejecutan; usa el reemplazo.\n")
    w("| Tool | Usa en su lugar | Motivo |\n|---|---|---|")
    for n, t in archivadas.items():
        w("| `{}` | {} | {} |".format(n, _celda(_reemplazo(t)),
                                         _celda(t.get("reason") or t.get("deprecation_reason") or "—")))
    w("")
    w("### 4.2 Internas\n")
    w("Existen en `scripts/` pero no son tools de un vault: librerías, registros o utilidades del propio toolkit. "
      "Ni la CLI ni el servidor MCP las publican.\n")
    w("| Tool | Motivo |\n|---|---|")
    for n, t in internas.items():
        w("| `{}` | {} |".format(n, _celda(t.get("reason") or "—")))
    w("")
    return "\n".join(out)


def disponibilidad_problemas() -> List[Dict]:
    problemas: List[Dict] = []
    for n in sorted(TOOLS_DE_CUIDADO):
        if n not in catalogo_producto():
            problemas.append({"kind": "disponibilidad_cuidado_huerfano", "detail": n})
    if not DISPONIBILIDAD.exists():
        problemas.append({"kind": "disponibilidad_ausente", "detail": cita_repo(rutas.DOCS, "DISPONIBILIDAD-DE-TOOLS.md")})
        return problemas
    actual = DISPONIBILIDAD.read_text(encoding="utf-8").replace("\r\n", "\n")
    if actual != disponibilidad_texto():
        problemas.append({"kind": "disponibilidad_desincronizada",
                          "detail": cita_repo(rutas.DOCS, "DISPONIBILIDAD-DE-TOOLS.md") + " no coincide con los registros; regenerar con --fix"})
    return problemas


def disponibilidad_fix() -> int:
    """Reescribe el documento si difiere. Devuelve 1 si lo cambió, 0 si ya estaba al día."""
    nuevo = disponibilidad_texto()
    previo = DISPONIBILIDAD.read_text(encoding="utf-8").replace("\r\n", "\n") if DISPONIBILIDAD.exists() else None
    if previo == nuevo:
        return 0
    DISPONIBILIDAD.parent.mkdir(parents=True, exist_ok=True)
    DISPONIBILIDAD.write_bytes(nuevo.encode("utf-8"))
    return 1


def tabla_del_readme_raiz() -> List[Dict]:
    """El README de la raíz lista cada tool activa en su tabla de grupos, y solo esas."""
    texto = README_RAIZ.read_text(encoding="utf-8")
    m = re.search(r"^## Las \d+ tools activas.*?(?=^## )", texto, re.M | re.S)
    if not m:
        return [{"kind": "readme_raiz_sin_tabla_de_tools", "detail": "falta la sección «Las N tools activas»"}]
    filas = [linea for linea in m.group(0).splitlines() if linea.startswith("| ")]
    listadas = set(re.findall(r"`(vault_\w+)`", " ".join(filas)))
    problemas = [{"kind": "readme_raiz_tool_ausente", "detail": n} for n in sorted(set(TOOLS_CATALOG) - listadas)]
    problemas += [{"kind": "readme_raiz_tool_sobrante", "detail": n} for n in sorted(listadas - set(TOOLS_CATALOG))]
    return problemas


def scan() -> Dict:
    text = README.read_text(encoding="utf-8")
    problems: List[Dict] = []
    problems.extend(comandos_publicados())
    problems.extend(disponibilidad_problemas())
    problems.extend(tabla_del_readme_raiz())
    problems.extend({k: v for k, v in p.items() if k != "sitio"} for p in recetas_en_codigo())

    sections = {label: int(num) for num, label in RE_SECTION.findall(text)}
    numbers = [int(num) for num, _ in RE_SECTION.findall(text)]

    for repetido in sorted({n for n in numbers if numbers.count(n) > 1}):
        problems.append({"kind": "grupo_duplicado", "detail": f"Grupo {repetido}"})

    for grupo in GROUPS:
        if grupo not in sections:
            problems.append({"kind": "grupo_sin_seccion", "detail": grupo})
    for label in sections:
        if label not in GROUPS:
            problems.append({"kind": "seccion_sin_grupo", "detail": label})

    # Solo cuentan los encabezados que viven DENTRO de una sección `## Grupo N`.
    # El README tiene secciones que no son grupos del catálogo ("Observabilidad
    # de Tools" documenta `vault_errors`, que es instrumentación interna y no se
    # expone por MCP). Esas no son drift: son documentación adicional legítima.
    h2 = list(re.finditer(r"^## .+$", text, re.M))
    cuerpo_de_grupos = "\n".join(
        text[m.end(): (h2[i + 1].start() if i + 1 < len(h2) else len(text))]
        for i, m in enumerate(h2)
        if RE_SECTION.match(m.group(0))
    )
    documentadas = set(RE_TOOL_HEADING.findall(cuerpo_de_grupos))
    for tool in sorted(set(TOOLS_CATALOG) - documentadas):
        problems.append({"kind": "tool_sin_seccion", "detail": tool})
    for tool in sorted(documentadas - set(TOOLS_CATALOG)):
        problems.append({"kind": "seccion_sin_tool", "detail": tool})

    esperado = [
        index_row(sections[g], g, GROUPS[g])
        for g in sorted(GROUPS, key=lambda g: sections.get(g, 10**6))
        if g in sections
    ]
    actual = [m.group(0) for m in RE_INDEX_ROW.finditer(text)]
    if actual != esperado:
        for fila in sorted(set(esperado) - set(actual)):
            problems.append({"kind": "fila_de_indice_ausente_o_erronea", "detail": fila})
        for fila in sorted(set(actual) - set(esperado)):
            problems.append({"kind": "fila_de_indice_sobrante", "detail": fila})
        if not (set(esperado) ^ set(actual)):
            problems.append({"kind": "indice_desordenado", "detail": "el orden de las filas no sigue al de las secciones"})

    return {
        "ok": not problems,
        "tool": "vault_doc_sync",
        "action": "check",
        "tools_checked": len(TOOLS_CATALOG),
        "commands_checked": True,
        "groups_checked": len(GROUPS),
        "problems": problems,
    }


def fix() -> Dict:
    """Regenera las filas del índice desde GROUPS. No inventa secciones."""
    text = README.read_text(encoding="utf-8")
    sections = {label: int(num) for num, label in RE_SECTION.findall(text)}

    filas = [m.group(0) for m in RE_INDEX_ROW.finditer(text)]
    if not filas:
        return {**emit_error("vault_doc_sync", "INDEX_NOT_FOUND",
                             "no se encontró la tabla de índice"),
                "action": "fix", "fixes_applied": 0}

    nuevas = [
        index_row(sections[g], g, GROUPS[g])
        for g in sorted(GROUPS, key=lambda g: sections.get(g, 10**6))
        if g in sections
    ]
    disp = disponibilidad_fix()
    if filas == nuevas:
        return {"ok": True, "tool": "vault_doc_sync", "action": "fix", "fixes_applied": disp}

    bloque_viejo = "\n".join(filas)
    if bloque_viejo not in text:
        # Las filas no son contiguas: se reescribe en sitio, una a una, y las
        # sobrantes se eliminan. No se toca nada fuera de la tabla.
        return {**emit_error("vault_doc_sync", "INDEX_NOT_FOUND",
                             "las filas del índice no son contiguas; corregir a mano"),
                "action": "fix", "fixes_applied": 0}

    README.write_text(text.replace(bloque_viejo, "\n".join(nuevas)), encoding="utf-8")
    return {
        "ok": True,
        "tool": "vault_doc_sync",
        "action": "fix",
        "fixes_applied": (len(set(nuevas) ^ set(filas)) or 1) + disp,
        "rows_written": len(nuevas),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="vault_doc_sync — guard anti-drift registro ↔ scripts/README.md"
    , allow_abbrev=False)
    ap.add_argument("--check", action="store_true", help="reporta divergencias (default)")
    ap.add_argument("--fix", action="store_true", help="regenera la tabla de índice desde GROUPS y " + cita_repo(rutas.DOCS, "DISPONIBILIDAD-DE-TOOLS.md"))
    ap.add_argument("--strict", action="store_true", help="exit 1 si hay divergencias")
    args = ap.parse_args()

    result = fix() if args.fix else scan()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if args.strict and not result["ok"] else 0


if __name__ == "__main__":
    sys.exit(main())
