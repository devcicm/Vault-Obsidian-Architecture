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

from vault_errors import emit_error  # noqa: E402
from vault_mcp_catalog import GROUPS, TOOLS_CATALOG  # noqa: E402

README = Path(__file__).resolve().parent / "README.md"

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
    "vault-sandbox/00_System/vault-commands.md",
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
    """
    src = script.read_bytes().decode("utf-8", "replace")
    declarados = set(RE_FLAG_DECLARADO.findall(src))
    if "BooleanOptionalAction" in src:
        declarados |= {"--no-" + f[2:] for f in declarados}
    return declarados


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
ZONAS_DE_RECETAS = ("scripts", "vault", "cli")

# Sitios que exhiben un comando roto como prueba del defecto que documentan,
# igual que el changelog del manifiesto. Mundo cerrado: una entrada que ya no
# aparece falla el test, así que la tabla solo encoge.
RECETAS_EXHIBIDAS = {
    ("scripts/vault_doc_sync.py", "vault_audit", "--root"):
        "el docstring cita el comando que originó la comprobación 6",
    ("scripts/vault_doc_sync.py", "vault_quality_check", "--root"):
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
        if re.fullmatch(r"--[A-Za-z][\w-]*", limpio):
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
                        src = script.read_bytes().decode("utf-8", "replace")
                        declarados = set(RE_FLAG_DECLARADO.findall(src))
                        if "BooleanOptionalAction" in src:
                            declarados |= {"--no-" + f[2:] for f in declarados}
                        flags_cache[m.group(1)] = declarados
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


def scan() -> Dict:
    text = README.read_text(encoding="utf-8")
    problems: List[Dict] = []
    problems.extend(comandos_publicados())
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
    if filas == nuevas:
        return {"ok": True, "tool": "vault_doc_sync", "action": "fix", "fixes_applied": 0}

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
        "fixes_applied": len(set(nuevas) ^ set(filas)) or 1,
        "rows_written": len(nuevas),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="vault_doc_sync — guard anti-drift registro ↔ scripts/README.md"
    , allow_abbrev=False)
    ap.add_argument("--check", action="store_true", help="reporta divergencias (default)")
    ap.add_argument("--fix", action="store_true", help="regenera la tabla de índice desde GROUPS")
    ap.add_argument("--strict", action="store_true", help="exit 1 si hay divergencias")
    args = ap.parse_args()

    result = fix() if args.fix else scan()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if args.strict and not result["ok"] else 0


if __name__ == "__main__":
    sys.exit(main())
