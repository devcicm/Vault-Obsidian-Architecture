"""Banco de tareas de agente: ¿cumple el vault su promesa a un LLM por MCP?

La promesa del servicio es memoria documental persistente, auditable y
gobernada para un agente. Ninguna puerta la mide: las puertas miran el repo
contra sí mismo. Este banco la mide como la ejerce un agente real —sesión
JSON-RPC contra el servidor MCP con `VAULT_MCP_PERFIL=agente`, sin leer el
fuente— y con las tareas de su sesión, no con las tools una a una:

- **orientar**: cada paso de `inicio` del protocolo sale bien o devuelve un
  error del que el agente puede recuperarse —`error_code`, `recovery` y una
  `recovery.tool` del perfil—. Un vault viejo no tiene por qué validar; lo que
  no puede es dejar al agente sin salida. Esos errores se publican en
  `hallazgos`.
- **recordar**: lo escrito en una sesión se recupera en otra nueva por
  `vault_context_pack`, `vault_search` y `vault_read`.
- **escribir**: el frontmatter que queda en disco lo lee `yaml.safe_load` y
  trae título, tipo, `status` del vocabulario y `agent` (AP-44).
- **recuperarse**: cada error lleva `error_code` y `recovery`, toda
  `recovery.tool` está en el perfil, y seguir la pista de `INVALID_FOLDER`
  lleva a una escritura que sale bien.
- **borrar**: el borrado deja su entrada SP-01 y la nota sale de la búsqueda.

Los argumentos de cada paso salen de `PROTOCOLO_DE_SESION[...]["uso"]` y del
`inputSchema` del servidor, no de una copia aquí.

Con `--copiar-de <vault ajeno>` (regla 7) mide además el recuerdo sobre las
notas que ya existían —título → `vault_context_pack`— en una COPIA: el
original se hashea antes y después y el banco falla si cambió un byte.

Uso:
    python tests/banco_agente.py                     # vault recién creado
    python tests/banco_agente.py --copiar-de <vault> # contraste con un ajeno
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

TESTS = Path(__file__).resolve().parent
REPO_ROOT = TESTS.parent
for _p in (str(TESTS), str(REPO_ROOT), str(REPO_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from test_mcp_runner import SesionMCP, _init_vault  # noqa: E402
from vault.meta_toolkit.protocolo_de_sesion import (  # noqa: E402
    PROTOCOLO_DE_SESION,
    tools_del_perfil,
)
from vault_norms_catalog import STATUS_VOCAB  # noqa: E402

PERFIL = "agente"
AGENTE = "banco-agente"
#: Cuántas notas preexistentes se interrogan en un vault ajeno.
MUESTRA_AJENA = 25


def _envelope(respuesta: dict) -> dict:
    """El envelope de la tool, o un error del protocolo con forma de envelope."""
    if "error" in respuesta:
        return {"ok": False, "jsonrpc_error": respuesta["error"]}
    try:
        return json.loads(respuesta["result"]["content"][0]["text"])
    except (KeyError, IndexError, TypeError, ValueError):
        return {"ok": False, "no_json": respuesta}


class Agente:
    """Una sesión MCP con el perfil del agente."""

    def __init__(self, vault: Path):
        self.sesion = SesionMCP(vault, {"VAULT_MCP_PERFIL": PERFIL})
        lista = self.sesion._pedir("tools/list", {})["result"]["tools"]
        self.esquemas = {t["name"]: t["inputSchema"] for t in lista}
        self.llamadas = []

    def __call__(self, tool: str, args: dict) -> dict:
        env = _envelope(self.sesion.llamar(tool, args))
        self.llamadas.append({"tool": tool, "ok": env.get("ok"),
                              "error_code": env.get("error_code")})
        return env

    def args_de_uso(self, tool: str, uso: str, valores: dict = None) -> dict:
        """`--check structure` → {check: "structure"}; un flag booleano → True.

        `valores` da los que solo el agente conoce (`{"<slug>": "x"}`); sin
        ellos, un paso que pide uno devuelve None."""
        props = self.esquemas[tool].get("properties", {})
        tokens = [(valores or {}).get(tok, tok) for tok in uso.split()]
        args, i = {}, 0
        while i < len(tokens):
            clave = tokens[i].lstrip("-")
            valor = tokens[i + 1] if i + 1 < len(tokens) else None
            if valor is not None and not valor.startswith("--"):
                if valor.startswith("<"):
                    return None
                args[clave] = valor
                i += 2
                continue
            if props.get(clave, {}).get("type") != "boolean":
                return None
            args[clave] = True
            i += 1
        return args

    def cerrar(self):
        self.sesion.cerrar()


def _frontmatter(fichero: Path):
    texto = fichero.read_text(encoding="utf-8")
    if not texto.startswith("---"):
        return None
    partes = texto.split("\n---", 1)
    if len(partes) < 2:
        return None
    try:
        datos = yaml.safe_load(partes[0][3:])
    except yaml.YAMLError:
        return None
    return datos if isinstance(datos, dict) else None


def _error_bien_formado(env: dict, perfil: set) -> list:
    """Lo que le falta a un error para que el agente pueda recuperarse."""
    faltas = []
    if env.get("ok") is not False:
        faltas.append("no es un error")
    if not env.get("error_code"):
        faltas.append("sin error_code")
    rec = env.get("recovery")
    if not isinstance(rec, dict):
        faltas.append("sin recovery")
    elif rec.get("tool") and rec["tool"] not in perfil:
        faltas.append(f"recovery.tool {rec['tool']} fuera del perfil")
    return faltas


def _cuerpo(marca: str) -> str:
    return "\n".join(
        f"El dato de prueba {marca} vive en la línea {i} de esta nota del banco."
        for i in range(4))


def _escribir(agente: Agente, folder: str, titulo: str, cuerpo: str) -> dict:
    return agente("vault_write", {
        "folder": folder, "title": titulo, "content": cuerpo,
        "tags": ["banco"], "agent": AGENTE,
    })


# --- tareas ----------------------------------------------------------------

def orientar(agente: Agente, perfil: set) -> dict:
    pasos, hallazgos = [], []
    for paso in PROTOCOLO_DE_SESION["inicio"]["pasos"]:
        if paso.get("cuando"):  # lo mide `cerrar`, con el proyecto que pide
            pasos.append({"tool": paso["tool"], "ok": True, "condicional": True})
            continue
        args = agente.args_de_uso(paso["tool"], paso["uso"])
        if args is None:
            pasos.append({"tool": paso["tool"], "ok": False, "por_que": "uso sin derivar"})
            continue
        env = agente(paso["tool"], args)
        if env.get("ok") is True:
            pasos.append({"tool": paso["tool"], "ok": True})
            continue
        faltas = _error_bien_formado(env, perfil)
        pasos.append({"tool": paso["tool"], "ok": not faltas,
                      "error_code": env.get("error_code"), "faltas": faltas})
        hallazgos.append({"tool": paso["tool"], "error_code": env.get("error_code"),
                          "recovery_tool": (env.get("recovery") or {}).get("tool")})
    return {"ok": all(p["ok"] for p in pasos), "pasos": pasos, "hallazgos": hallazgos}


def escribir(agente: Agente, vault: Path, marca: str) -> dict:
    titulo = f"Banco {marca}"
    env = _escribir(agente, "07_Knowledge", titulo, _cuerpo(marca))
    if env.get("ok") is not True:
        return {"ok": False, "envelope": env}
    fm = _frontmatter(vault / env["path"]) or {}
    faltas = [c for c in ("title", "type", "status", "agent") if not fm.get(c)]
    if fm.get("title") != titulo:
        faltas.append("title distinto")
    if fm.get("status") not in STATUS_VOCAB:
        faltas.append(f"status fuera del vocabulario: {fm.get('status')!r}")
    if fm.get("agent") != AGENTE:
        faltas.append(f"agent no es el declarado: {fm.get('agent')!r}")
    return {"ok": not faltas, "path": env["path"], "faltas": faltas}


def recordar(agente: Agente, path: str, marca: str, pregunta: str) -> dict:
    pack = agente("vault_context_pack", {"query": pregunta})
    incluidas = [i.get("path") for i in pack.get("included", [])]
    busca = agente("vault_search", {"query": marca})
    halladas = [r.get("path") for r in busca.get("results", [])]
    lee = agente("vault_read", {"path": path})
    r = {
        "context_pack": path in incluidas,
        "posicion_en_pack": incluidas.index(path) + 1 if path in incluidas else None,
        "search": path in halladas,
        "read": marca in (lee.get("body") or ""),
    }
    return {"ok": all(r[k] for k in ("context_pack", "search", "read")), **r}


def recuperarse(agente: Agente, vault: Path, perfil: set) -> dict:
    casos = {}
    # 1. Carpeta que no es sección: seguir la pista hasta escribir bien.
    env = _escribir(agente, "scripts", "Banco carpeta", _cuerpo("CARPETA"))
    caso = {"error_code": env.get("error_code"), "faltas": _error_bien_formado(env, perfil)}
    rec = env.get("recovery") or {}
    if rec.get("tool") in perfil:
        pista = agente(rec["tool"], agente.args_de_uso(rec["tool"], " ".join(rec.get("args", []))) or {})
        secciones = pista.get("writable_sections") or []
        caso["secciones_ofrecidas"] = len(secciones)
        if secciones:
            destino = "07_Knowledge" if "07_Knowledge" in secciones else secciones[0]
            caso["tras_la_pista"] = _escribir(
                agente, destino, "Banco carpeta", _cuerpo("CARPETA")).get("ok") is True
    caso["ok"] = not caso["faltas"] and caso.get("tras_la_pista") is True
    casos["INVALID_FOLDER"] = caso
    # 2. Errores que se corrigen en la entrada: basta con que se puedan leer.
    for nombre, args in {
        "contenido_corto": ("07_Knowledge", "Banco corto", "hola"),
        "enlace_vacio": ("07_Knowledge", "Banco vacio", _cuerpo("VACIO") + "\n[[]]"),
    }.items():
        env = _escribir(agente, *args)
        f = _error_bien_formado(env, perfil)
        casos[nombre] = {"ok": not f, "error_code": env.get("error_code"), "faltas": f}
    env = agente("vault_search", {"query": "x", "clave_inventada": True})
    f = _error_bien_formado(env, perfil)
    casos["clave_desconocida"] = {"ok": not f, "error_code": env.get("error_code"), "faltas": f}
    env = agente("vault_drift_detect", {"mode": "report"})
    f = _error_bien_formado(env, perfil)
    casos["drift_sin_proyecto"] = {"ok": not f, "error_code": env.get("error_code"), "faltas": f}
    env = agente("vault_drift_detect", {"mode": "report", "project": "proyecto-que-no-existe"})
    f = _error_bien_formado(env, perfil)
    casos["proyecto_desconocido"] = {"ok": not f, "error_code": env.get("error_code"), "faltas": f}
    return {"ok": all(c["ok"] for c in casos.values()), "casos": casos}


def borrar(agente: Agente, vault: Path, path: str, marca: str) -> dict:
    env = agente("vault_delete", {"path": path, "reason": "banco de agente"})
    busca = agente("vault_search", {"query": marca})
    r = {
        "borrada": env.get("ok") is True and not (vault / path).exists(),
        "sp01": bool(env.get("sp01_status")),
        "fuera_de_busqueda": path not in [x.get("path") for x in busca.get("results", [])],
    }
    return {"ok": all(r.values()), **r}


def cerrar(agente: Agente, repo: Path, slug: str = "banco-proyecto") -> dict:
    """Una sesión sobre un proyecto: los pasos condicionales de `inicio`, un
    cambio en el repo sin documentar y los de `cierre`, todos desde el uso
    que declara el protocolo. El report tiene que ver el cambio."""
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "modulo.py").write_text("x = 1\n", encoding="utf-8")
    alta = [agente("vault_project", {"add": slug}),
            agente("vault_project", {"link": slug, "path": str(repo)})]
    if not all(e.get("ok") is True for e in alta):
        return {"ok": False, "alta": alta}
    pasos = []

    def dar(momento, filtro):
        for paso in PROTOCOLO_DE_SESION[momento]["pasos"]:
            if not filtro(paso):
                continue
            args = agente.args_de_uso(paso["tool"], paso["uso"], {"<slug>": slug})
            env = agente(paso["tool"], args) if args is not None else {}
            pasos.append({"momento": momento, "tool": paso["tool"],
                          "ok": env.get("ok") is True, "error_code": env.get("error_code")})
            if paso["tool"] == "vault_drift_detect" and "report" in paso["uso"]:
                pasos[-1]["cambio_visto"] = "nuevo.py" in [
                    u.get("file") for u in env.get("undocumented", [])]

    dar("inicio", lambda p: p.get("cuando"))
    (repo / "nuevo.py").write_text("y = 2\n", encoding="utf-8")
    dar("cierre", lambda p: True)
    return {"ok": bool(pasos) and all(p["ok"] and p.get("cambio_visto", True) for p in pasos),
            "pasos": pasos}


def recuerdo_preexistente(agente: Agente, vault: Path) -> dict:
    """Título → context_pack sobre notas que el banco no escribió. Métrica, no veredicto.

    Un título que llevan varias notas es una pregunta ambigua: que la buscada
    salga segunda tras su gemela no es un fallo del ranking. Medido en una copia
    de /ans, eran los tres casos de «no sale primera». Se cuentan aparte y la
    cifra cruda se conserva."""
    candidatas = []
    for f in sorted(vault.rglob("*.md")):
        rel = f.relative_to(vault).as_posix()
        if any(p.startswith(".") for p in f.relative_to(vault).parts):
            continue
        fm = _frontmatter(f)
        titulo = (fm or {}).get("title")
        if isinstance(titulo, str) and len(titulo.split()) >= 2:
            candidatas.append((rel, titulo))
    repetidos = {t for t in (c[1] for c in candidatas)
                 if sum(1 for _, otro in candidatas if otro == t) > 1}
    paso = max(1, len(candidatas) // MUESTRA_AJENA)
    muestra = candidatas[::paso][:MUESTRA_AJENA]
    filas = []
    for rel, titulo in muestra:
        pack = agente("vault_context_pack", {"query": titulo})
        incluidas = [i.get("path") for i in pack.get("included", [])]
        busca = agente("vault_search", {"query": titulo})
        filas.append({"path": rel, "titulo": titulo, "pack_ok": pack.get("ok") is True,
                      "en_pack": rel in incluidas, "primera": incluidas[:1] == [rel],
                      "en_search": rel in [x.get("path") for x in busca.get("results", [])],
                      "titulo_repetido": titulo in repetidos})
    n = len(filas) or 1
    claras = [f for f in filas if not f["titulo_repetido"]]
    return {
        "candidatas": len(candidatas),
        "muestra": len(filas),
        "recall_pack": round(sum(f["en_pack"] for f in filas) / n, 3),
        "acierto_primera": round(sum(f["primera"] for f in filas) / n, 3),
        "ambiguas": len(filas) - len(claras),
        "acierto_primera_sin_ambiguas": round(
            sum(f["primera"] for f in claras) / (len(claras) or 1), 3),
        "recall_search": round(sum(f["en_search"] for f in filas) / n, 3),
        "fallos": [f for f in filas if not f["en_pack"]],
    }


# --- orquestación ------------------------------------------------------------

def correr(vault: Path, ajeno: bool = False) -> dict:
    """Las tareas del agente sobre `vault`, que el banco puede escribir."""
    perfil = set(tools_del_perfil(PERFIL))
    marca = "QX" + hashlib.sha1(str(vault).encode()).hexdigest()[:8].upper()
    informe = {"vault": str(vault), "perfil": PERFIL, "tareas": {}}
    a = Agente(vault)
    try:
        informe["perfil_expuesto"] = sorted(a.esquemas) == sorted(perfil)
        informe["tareas"]["orientar"] = orientar(a, perfil)
        if ajeno:
            chk = a("vault_reindex", {"check": True})
            if chk.get("status") != "index_ok":
                informe["reindexado"] = a("vault_reindex", {"graph": True}).get("ok")
            informe["recuerdo_preexistente"] = recuerdo_preexistente(a, vault)
        informe["tareas"]["escribir"] = escribir(a, vault, marca)
        informe["tareas"]["recuperarse"] = recuperarse(a, vault, perfil)
    finally:
        a.cerrar()
    path = informe["tareas"]["escribir"].get("path")
    b = Agente(vault)  # sesión nueva: el agente no recuerda nada salvo el vault
    try:
        if path:
            informe["tareas"]["recordar"] = recordar(
                b, path, marca, f"¿qué dato de prueba {marca} guarda el banco?")
            informe["tareas"]["borrar"] = borrar(b, vault, path, marca)
        else:
            informe["tareas"]["recordar"] = {"ok": False, "por_que": "no se escribió"}
            informe["tareas"]["borrar"] = {"ok": False, "por_que": "no se escribió"}
        informe["tareas"]["cerrar"] = cerrar(b, vault.parent / "repo-del-banco")
    finally:
        b.cerrar()
    informe["ok"] = informe["perfil_expuesto"] and all(
        t["ok"] for t in informe["tareas"].values())
    informe["llamadas"] = len(a.llamadas) + len(b.llamadas)
    return informe


def huella(raiz: Path) -> str:
    """Hash de todo el árbol —rutas y bytes—, para probar que no se tocó."""
    h = hashlib.sha256()
    for f in sorted(p for p in raiz.rglob("*") if p.is_file()):
        h.update(f.relative_to(raiz).as_posix().encode("utf-8"))
        h.update(f.read_bytes())
    return h.hexdigest()


def correr_sobre_copia(original: Path, trabajo: Path) -> dict:
    antes = huella(original)
    copia = trabajo / "copia"
    shutil.copytree(original, copia, ignore=shutil.ignore_patterns(".git"))
    informe = correr(copia, ajeno=True)
    despues = huella(original)
    informe["original"] = {"ruta": str(original), "sha256": antes,
                           "intacto": antes == despues}
    informe["ok"] = informe["ok"] and antes == despues
    return informe


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--copiar-de", type=Path,
                    help="vault ajeno: se mide una copia y el original solo se lee")
    ap.add_argument("--trabajo", type=Path, help="directorio de trabajo (por defecto, uno temporal)")
    args = ap.parse_args(argv)
    # Se rechaza antes de crear nada: un rechazo no deja directorios detrás.
    original = args.copiar_de.resolve() if args.copiar_de else None
    if original and (REPO_ROOT in original.parents or original == REPO_ROOT):
        print(json.dumps({"ok": False, "error": "el vault ajeno no puede estar en este repo"}))
        return 2
    trabajo = args.trabajo or Path(tempfile.mkdtemp(prefix="voa_banco_"))
    trabajo.mkdir(parents=True, exist_ok=True)
    if original:
        informe = correr_sobre_copia(original, trabajo)
    else:
        informe = correr(_init_vault(trabajo / "vault"))
    informe["trabajo"] = str(trabajo)
    print(json.dumps(informe, ensure_ascii=False, indent=2))
    return 0 if informe["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
