"""La obligatoriedad que la spec declara es la que el código impone (v41.16).

La obligatoriedad de un flag vive en dos canales, y cada uno declara lo
que él sabe:

1. **argparse** (`required=True`): lo deriva `flags_cli.obligatorios()`,
   el dueño canónico de la introspección. Un flag obligatorio por
   argparse que la spec no declara rechaza dos veces a un agente — el
   MCP y la CLI exigen donde el contrato publicado calla.
2. **Validación manual** (`parser.error("…obligatorio…")`): la
   obligatoriedad condicional o por grupo que no cabe en argparse
   (`vault_write {title+content | scan-path}`, `vault_onboard
   --project y --path`, `vault_section_index --folder salvo --heal`,
   `drift_detect --path *o repo enlazado*`). La spec también declara
   estos en `required_args` — es su única copia: el overlay del
   catálogo no puede llevarlos (`required: true` en el schema haría
   rechazar al servidor las alternativas —`--heal`, `--self-test`— que
   el flag exige condicionalmente; el servidor Node impone el
   `required` del schema en vault-mcp-server.mjs L1240).

Medido el 2026-10-21 con sonda de conducta sobre vault temporal: las
seis tools donde `required_args` de la spec va más allá del argparse
(`context_pack.query`, `query_parse.query`, `drift_detect.path`,
`foreign_check.root`, `onboard.{path,project}`,
`section_index.folder`) **exigen** sus flags en runtime con un error
de validación. La spec era la verdad; el derivador (`flags_cli
.obligatorios`) miraba solo el canal 1 y no el 2, y la experiencia de
la tanda 3 leyó eso como deriva cuando era ceguera del husband-side.

Este test sostiene las dos direcciones, sin special-casing:

- **De menos**: un flag `required=True` del argparse sin declaración en
  la spec → rojo inmediato (estático, sin runtime).
- **De más**: un `required_args` de la spec que ni el argparse ni el
  texto del rechazo manual de la tool nominan → sonda de conducta: si
  la llamada mínima **corre** sin que nadie la exija, la spec miente;
  si el runtime la pide, es un condicional honesto (verde). El detector
  es el mismo para las 6 de hoy que para las herramientas que la
  escriban mañana, así que ninguna edición a mano de la spec queda
  sin verificación.
"""

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import vault_grafo_import as gi  # noqa: E402
from vault_mcp_catalog import TOOLS_CATALOG  # noqa: E402
from vault.meta_toolkit import flags_cli  # noqa: E402

SPEC_JSON = ROOT / "vault-sandbox" / "00_System" / "tool-spec.json"


def _fuente(nombre: str):
    script = str(TOOLS_CATALOG[nombre].get("script") or f"{nombre}.py")
    try:
        ruta = Path(gi.fuente_de(script.replace(".py", "")))
    except Exception:
        return None
    return ruta if ruta.is_file() else None


def _flags(nombre: str):
    """(todos, obligatorios) — ambos del código real de la tool."""
    ruta = _fuente(nombre)
    if ruta is None:
        return set(), set()
    src = ruta.read_text(encoding="utf-8", errors="replace")
    todo, obl = set(), set()
    for d in flags_cli.declaraciones(src):
        largos = [n.lstrip("-") for n in d.nombres if n.lstrip("-")]
        todo.update(largos)
        required = d.kw.get("required")
        if required is not None:
            try:
                if required.value is True:
                    obl.update(largos)
            except AttributeError:
                pass
    return todo, obl


def _spec() -> dict:
    return json.loads(SPEC_JSON.read_text(encoding="utf-8"))["tools"]


def _spec_required(nombre: str) -> list[str]:
    s = _spec().get(nombre) or {}
    return sorted({str(a).lstrip("-") for a in (s.get("required_args") or [])})


def _canal_manual(nombre: str) -> set:
    """Los flags que el texto del rechazo manual de la tool nombra.

    El canal manual vive en literales(`parser.error`, mensajes de
    argumentos); el guard acepta su NOMINACIÓN como declaración en
    código, porque ahí la escribe quien implementa la exigencia.
    """
    ruta = _fuente(nombre)
    if ruta is None:
        return set()
    src = ruta.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r"--([a-z0-9][a-z0-9-]+)", src))


def _valores_de_ejemplo(nombre: str) -> dict[str, str]:
    """Valores plausibles desde el `example` del catálogo (sin inventar {})."""
    ejemplo = TOOLS_CATALOG[nombre].get("example") or ""
    argv = shlex.split(ejemplo.split("\n")[0].strip())
    valores: dict[str, str] = {}
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok.startswith("--"):
            cuerpo = tok.lstrip("-")
            if "=" in cuerpo:
                clave, v = cuerpo.split("=", 1)
                valores[clave] = "demo" if clave == "project" else v
                i += 1
                continue
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                valores[cuerpo] = ("demo" if cuerpo == "project"
                                   else argv[i + 1])
                i += 2
            else:
                valores[cuerpo] = ""
                i += 1
        else:
            i += 1
    return valores


def _validacion_mal(e: dict) -> bool:
    """¿El envelope es un rechazo por argumentos (no un fallo de dominio)?"""
    code = e.get("error_code") or ""
    msg = str(e.get("message") or "")
    return (
        code in ("INVALID_ARGS", "MISSING_REQUIRED_ARG")
        or "obligator" in msg
        or "requerid" in msg
        or "falta el parámetro" in msg
    )


SONDA_TOTAL = 400


@pytest.fixture(scope="module")
def vault_sonda(tmp_path_factory):
    """Un vault temporal con un proyecto alto: el escenario de la sonda.

    Casa temporal (VAULT_MASTER dentro del tmp) para no tocar la del
    usuario; proyecto `demo` registrado tal como registraría quien
    compone la llamada desde el contrato.
    """
    raiz = tmp_path_factory.mktemp("spec-verdad")
    casa = raiz / ".vault-master"
    # O1b: el VAULT_MASTER va en el env de los procesos, no en `os.environ`
    # de este worker — en `-n auto` el mismo proceso correrá otros tests y
    # una variable global suelta es la fuga hacia su casa real.
    env = dict(os.environ, VAULT_MASTER=str(casa), VAULT_AGENT="test",
               VAULT_VOICE="0", VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_init.py"),
         "--name", "v", "--no-audit", "--no-git"],
        capture_output=True, text=True, env=env, encoding="utf-8",
        errors="replace", timeout=SONDA_TOTAL, cwd=str(ROOT))
    assert json.loads(r.stdout).get("ok"), r.stdout[:400]
    vault = casa / "v"
    env["VAULT_ROOT"] = str(vault)
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_project.py"),
         "--add", "demo"],
        capture_output=True, text=True, env=env, encoding="utf-8",
        errors="replace", timeout=120, cwd=str(ROOT))
    assert json.loads(r.stdout).get("ok"), r.stdout[:400]
    return env


def _probe(nombre: str, argv: list[str], env: dict) -> dict:
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / f"{nombre}.py"), *argv],
        capture_output=True, text=True, env=env, encoding="utf-8",
        errors="replace", timeout=SONDA_TOTAL, cwd=str(ROOT))
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error_code": "NO_ENVELOPE",
                "message": (r.stdout + r.stderr)[:200]}


# ── el guard, estático ─────────────────────────────────────────────────────


def test_la_spec_no_declara_flags_fantasma():
    """Todo `required_args` de la spec existe como flag real de la tool.

    Solo para tools con backend Python: las tres node-native
    (`vault_backup_base64`, `vault_gobernanza`, `vault_restore_base64`)
    no tienen script que introspectar y su contrato vive íntegro en el
    spec JSON, que AP-48 vigila por su lado.
    """
    spec = _spec()
    fantasma = []
    for nombre in sorted(TOOLS_CATALOG):
        if nombre not in spec or _fuente(nombre) is None:
            continue
        todo, _ = _flags(nombre)
        manual = _canal_manual(nombre)
        for req in _spec_required(nombre):
            variantes = {req, req.replace("-", "_"), req.replace("_", "-")}
            if not (todo & variantes) and req not in manual and \
                    req.replace("-", "_") not in manual and \
                    req.replace("_", "-") not in manual:
                fantasma.append((nombre, req))
    assert not fantasma, (
        "required_args de la spec que ninguna tool declara — un agente que "
        f"componga la llamada se lleva el rechazo: {fantasma}")


def test_el_argparse_obligatorio_esta_en_la_spec():
    """Lo que el argparse exige, la spec lo declara (canal 1 heredado)."""
    spec = _spec()
    huecos = []
    for nombre in sorted(TOOLS_CATALOG):
        if nombre not in spec:
            continue
        _, obl = _flags(nombre)
        faltan = sorted(obl - set(_spec_required(nombre)))
        if faltan:
            huecos.append((nombre, faltan))
    assert not huecos, (
        "flags obligatorios por argparse fuera de la spec: un agente que "
        f"solo obeya el schema del MCP no los lleva: {huecos}")


# ── el guard, por conducta ────────────────────────────────────────────────


def test_el_condicional_de_la_spec_lo_exige_el_runtime(vault_sonda):
    """Los `required_args` condicionales de la spec son verdad en runtime.

    Para cada tool donde la spec declara obligatorios que el argparse no
    conoce: componer la llamada **sin** esos flags (los demás, del
    ejemplo del catálogo, sin inventar) y exigir el rechazo. Si corre y
    la spec exigía datos que nadie pide, un consumidor está rellenando
    campos que no existen.
    """
    env = vault_sonda
    de_mas = []
    for nombre in sorted(TOOLS_CATALOG):
        if nombre not in _spec() or _fuente(nombre) is None:
            continue
        todo, obl = _flags(nombre)
        condicional = [f for f in _spec_required(nombre) if f not in obl]
        if not condicional:
            continue
        valores = _valores_de_ejemplo(nombre)
        argv: list[str] = []
        for f, v in sorted(valores.items()):
            if f in condicional or f in ("json", "help"):
                continue
            if v:
                argv += [f"--{f}", v]
            else:
                argv += [f"--{f}"]
        vivel = _probe(nombre, argv, env)
        if not _validacion_mal(vivel):
            de_mas.append((nombre, condicional,
                           vivel.get("error_code"),
                           str(vivel.get("message"))[:80]))
    assert not de_mas, (
        "la spec declara required_args que el runtime NO exige — el "
        f"consumidor rellena datos que nadie pide: {de_mas}")
