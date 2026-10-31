#!/usr/bin/env python3
"""paridad — golden master de la reestructura Teseo y su comparador.

Congela el contrato observable C(P) del toolkit en `golden/` y, después de
cada tablón, comprueba que sigue siendo el mismo barco. Cuatro componentes:

- **estatico** — sha256 de los contratos que consume un tercero: los dos
  `tools-catalog.json`, el `tool-spec.json` del sandbox, `schemas/` y los
  `[project.scripts]` de `pyproject.toml`. Comparador `exact`.
- **superficie** — los nombres públicos de cada módulo de `scripts/` y de
  `vault/`, importados de verdad (los alias `sys.modules` cuentan). Mover un
  módulo sin dejar su alias es romper a quien lo importa. Comparador `exact`
  sobre el conjunto; un nombre nuevo se reporta y no rompe.
- **ayuda** — `--help` de cada script de tool y de las dos entradas de
  consola. Es la CLI publicada. Comparador `exact` tras sustituir la ruta del
  repo y del intérprete.
- **envelopes** — cada línea `python …` del `example` del catálogo, corrida
  contra una copia desechable del sandbox con el proyecto `mi-api`, con los
  ficheros que el ejemplo da por existentes. Se guarda exit, `ok`,
  `error_code`, las claves del envelope, las rutas del vault que cambió y el
  envelope normalizado.

**Por qué no reutiliza `vault_smoke.run_one` al comparar.** El comparador no
puede depender del código que el refactor mueve: si `vault_smoke` cambia, la
medida cambiaría con él (AP-44). La captura usa el catálogo y el banco de
`vault_noop_audit` *una vez* para saber qué correr y qué preparar, y guarda el
argv y los contenidos en el golden. A partir de ahí el golden se basta solo.

**Normalización, declarada y pequeña** (references/paridad.md, regla 3):

| Patrón | Se sustituye por | Por qué | Contraejemplo que NO se toca |
|---|---|---|---|
| ruta del directorio desechable de la corrida | `<TMP>` | cambia en cada corrida | una ruta relativa al vault |
| ruta del repo | `<REPO>` | depende del clon | `scripts/vault_x.py` |
| ruta de `sys.executable` | `<PY>` | depende de la máquina | `python` en un texto |
| fecha-hora ISO 8601 | `<TS>` | reloj | una fecha sin hora de una nota del sandbox |
| la fecha de hoy (`AAAA-MM-DD`) | `<HOY>` | reloj | cualquier otra fecha |

Lo que sigue variando entre **dos capturas del mismo commit** se declara
volátil por su ruta JSON y se lista en `golden/envelopes.json`
(`volatiles`). El comparador solo ignora el *valor* de esas rutas, nunca su
presencia ni su tipo. Nada se da por volátil sin haberlo visto variar.

Uso:
    python audits/reestructura/paridad.py --capturar [--repeticiones 2]
    python audits/reestructura/paridad.py --comparar [--solo estatico,superficie,ayuda]
    python audits/reestructura/paridad.py --comparar --tools vault_write,vault_read

`--capturar` escribe solo dentro de `audits/reestructura/golden/`; las copias
del sandbox viven en el temporal del sistema y se borran al acabar. Lo que un
ejemplo escriba en el repo (no en su vault) se anota en `repo_escritas` y se
devuelve a sus bytes antes de la línea siguiente (`CustodiaDelRepo`).
El golden no se regenera para hacer pasar un tablón (regla 5): se regenera
como operación explícita, con su motivo, fuera de un paso de refactor.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent.parent
GOLDEN = AQUI / "golden"
SCRIPTS = REPO / "scripts"
SANDBOX = REPO / "vault-sandbox"
TIMEOUT_S = 180

#: Los contratos que consume un tercero sin pasar por el código.
CONTRATOS_ESTATICOS = (
    "mcp/nodejs/tools-catalog.json",
    "vault/meta_toolkit/tools-catalog.json",
    "vault-sandbox/00_System/tool-spec.json",
)
COMPONENTES = ("estatico", "superficie", "ayuda", "envelopes")

_TS = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?")


# ── utilidades ─────────────────────────────────────────────────────────────


def _sha(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _escribir(ruta: Path, datos: Any) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(datos, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    tmp = ruta.with_suffix(ruta.suffix + ".tmp")
    tmp.write_bytes(texto.encode("utf-8"))
    os.replace(tmp, ruta)


def _leer(ruta: Path) -> Any:
    return json.loads(ruta.read_text(encoding="utf-8"))


def _env_base(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    env = dict(os.environ)
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(REPO), "VAULT_VOICE": "0",
                "VAULT_AGENT": "vault-smoke"})
    env.update(extra or {})
    return env


def _variantes(ruta: str) -> List[str]:
    """Las formas en que una ruta absoluta aparece en un envelope."""
    p = Path(ruta)
    formas = {str(p), p.as_posix()}
    try:
        largo = str(p.resolve())
        formas |= {largo, Path(largo).as_posix()}
    except OSError:
        pass
    # El `repr` de una ruta Windows dobla las barras, en la forma corta
    # (`CARLOS~1`) y en la larga resuelta. Medido el 2026-10-31: un `[Errno 2]`
    # de `vault_validate` traía la larga doblada y, sin esta variante, el
    # mensaje entero salía volátil y dejaba de compararse.
    formas |= {f.replace("\\", "\\\\") for f in formas if "\\" in f}
    return sorted((f for f in formas if f), key=len, reverse=True)


class Normalizador:
    """La tabla del docstring, y nada más."""

    def __init__(self, tmp: Optional[str] = None) -> None:
        self.pares: List[Tuple[str, str]] = []
        if tmp:
            self.pares += [(v, "<TMP>") for v in _variantes(tmp)]
        self.pares += [(v, "<REPO>") for v in _variantes(str(REPO))]
        self.pares += [(v, "<PY>") for v in _variantes(sys.executable)]
        self.hoy = _dt.date.today().isoformat()

    def texto(self, s: str) -> str:
        for viejo, nuevo in self.pares:
            if viejo in s:
                s = s.replace(viejo, nuevo)
        s = _TS.sub("<TS>", s)
        return s.replace(self.hoy, "<HOY>")

    def valor(self, v: Any) -> Any:
        if isinstance(v, str):
            return self.texto(v)
        if isinstance(v, list):
            return [self.valor(x) for x in v]
        if isinstance(v, dict):
            return {self.texto(k): self.valor(x) for k, x in v.items()}
        return v


# ── estatico ───────────────────────────────────────────────────────────────


def capturar_estatico() -> Dict[str, Any]:
    ficheros = {rel: _sha(REPO / rel) for rel in CONTRATOS_ESTATICOS if (REPO / rel).is_file()}
    for p in sorted((REPO / "schemas").rglob("*")):
        if p.is_file():
            ficheros[p.relative_to(REPO).as_posix()] = _sha(p)
    entradas = {}
    en_bloque = False
    for linea in (REPO / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        if linea.strip().startswith("["):
            en_bloque = linea.strip() == "[project.scripts]"
            continue
        if en_bloque and "=" in linea and not linea.lstrip().startswith("#"):
            clave, valor = linea.split("=", 1)
            entradas[clave.strip()] = valor.strip().strip('"')
    return {"ficheros": ficheros, "project_scripts": entradas}


# ── superficie ─────────────────────────────────────────────────────────────

_SONDA_SUPERFICIE = r"""
import importlib, json, sys
salida = {}
for nombre in json.loads(sys.argv[1]):
    try:
        m = importlib.import_module(nombre)
        salida[nombre] = sorted(n for n in vars(m) if not n.startswith("_"))
    except BaseException as e:  # un módulo que no importa también es contrato
        salida[nombre] = {"error": type(e).__name__}
print(json.dumps(salida))
"""


def _modulos() -> List[str]:
    nombres = [p.stem for p in sorted(SCRIPTS.glob("*.py")) if p.stem != "__init__"]
    for p in sorted((REPO / "vault").rglob("*.py")):
        partes = list(p.relative_to(REPO).with_suffix("").parts)
        if partes[-1] == "__init__":
            partes = partes[:-1]
        if all(x.isidentifier() for x in partes):
            nombres.append(".".join(partes))
    return nombres


def capturar_superficie(vault_tmp: Path) -> Dict[str, Any]:
    env = _env_base({"VAULT_ROOT": str(vault_tmp), "VAULT_STRICT_ROOT": "1",
                     "PYTHONPATH": os.pathsep.join([str(REPO), str(SCRIPTS)])})
    proc = subprocess.run([sys.executable, "-B", "-c", _SONDA_SUPERFICIE,
                           json.dumps(_modulos())],
                          cwd=str(vault_tmp), env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=600)
    if proc.returncode != 0:
        raise RuntimeError("la sonda de superficie falló: " + proc.stderr[-500:])
    return json.loads(proc.stdout.strip().splitlines()[-1])


# ── ayuda ──────────────────────────────────────────────────────────────────


def _catalogo() -> Dict[str, Any]:
    return _leer(REPO / "mcp" / "nodejs" / "tools-catalog.json")


def _scripts_de_tools() -> Dict[str, str]:
    cat = _catalogo()
    tools = cat.get("tools", cat)
    salida = {}
    for nombre, entrada in sorted(tools.items()):
        script = isinstance(entrada, dict) and entrada.get("script")
        if script and (SCRIPTS / script).is_file():
            salida[nombre] = script
    return salida


def capturar_ayuda(vault_tmp: Path) -> Dict[str, Any]:
    env = _env_base({"VAULT_ROOT": str(vault_tmp), "VAULT_STRICT_ROOT": "1"})
    norm = Normalizador(str(vault_tmp))
    comandos = {n: [f"scripts/{s}", "--help"] for n, s in _scripts_de_tools().items()}
    comandos["<consola:vault>"] = ["-m", "vault.product_cli", "--help"]
    comandos["<consola:vault_gobernanza>"] = ["-m", "vault.gobernanza.tool", "--help"]
    salida = {}
    for nombre, args in comandos.items():
        argv = [sys.executable, "-B"] + [str(REPO / a) if a.startswith("scripts/") else a for a in args]
        try:
            proc = subprocess.run(argv, cwd=str(REPO), env=env, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace",
                                  timeout=TIMEOUT_S)
            salida[nombre] = {"exit": proc.returncode, "stdout": norm.texto(proc.stdout)}
        except subprocess.TimeoutExpired:
            salida[nombre] = {"exit": None, "stdout": "<timeout>"}
    return salida


# ── envelopes ──────────────────────────────────────────────────────────────


def plan_de_envelopes(tools: Optional[Set[str]] = None) -> Dict[str, Any]:
    """Qué correr y qué preparar, sacado una sola vez del código vigente."""
    sys.path[:0] = [str(REPO), str(SCRIPTS)]
    import vault_noop_audit as noop
    import vault_smoke

    plan: Dict[str, Any] = {}
    for nombre in _scripts_de_tools():
        if tools and nombre not in tools:
            continue
        if nombre in vault_smoke.SIN_SMOKE:
            plan[nombre] = {"omitida": vault_smoke.SIN_SMOKE[nombre]}
            continue
        lineas = []
        for argv in vault_smoke.invocations(nombre):
            # argv = [python, <repo>/scripts/x.py, args...]: se guarda relativo.
            lineas.append([Path(argv[1]).relative_to(REPO).as_posix()] + argv[2:])
        ficheros = {clave: noop._CONTENIDOS[clase]
                    for clave, clase in (noop.FICHEROS_DEL_EJEMPLO.get(nombre) or {}).items()}
        plan[nombre] = {"lineas": lineas, "ficheros": ficheros}
    return {"proyecto": list(noop.PROYECTO_DEL_EJEMPLO or ()), "tools": plan}


def _origen(base: Path, proyecto: List[str]) -> Path:
    vault = base / "vault"
    shutil.copytree(SANDBOX, vault, ignore=shutil.ignore_patterns(".locks", ".tmp.*"))
    if proyecto and not (vault / "01_Projects" / proyecto[0]).exists():
        env = _env_base({"VAULT_ROOT": str(vault), "VAULT_STRICT_ROOT": "1"})
        proc = subprocess.run([sys.executable, "-B", str(SCRIPTS / "vault_project.py"),
                               "--add", proyecto[0], "--title", proyecto[1]],
                              cwd=str(SCRIPTS), env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=TIMEOUT_S)
        if proc.returncode != 0:
            raise RuntimeError("no se pudo dar de alta el proyecto del ejemplo: "
                               + (proc.stdout + proc.stderr)[-400:])
    return vault


def _arbol(raiz: Path) -> Dict[str, str]:
    salida = {}
    for p in raiz.rglob("*"):
        if p.is_file() and ".locks" not in p.parts and p.name != ".tool-trace.json":
            salida[p.relative_to(raiz).as_posix()] = _sha(p)
    return salida


_FUERA_DE_CUSTODIA = {".git", "build", "node_modules", "__pycache__", ".pytest_cache"}


class CustodiaDelRepo:
    """Ninguna línea de ejemplo deja escrito el repo, y lo que escribiría es contrato.

    Hay ejemplos que escriben en el repo y no en el vault (`vault_doc_sync --fix`,
    `vault_toolkit_audit --tools X`). Dejarlo pasar contamina el golden por orden:
    medido el 2026-10-31, el `--tools X` de `toolkit_audit` reescribió
    `toolkit-audit-last.json` con un alcance de una tool y las corridas siguientes
    vieron `DISPONIBILIDAD` degradada (BUGS B-05). Aquí se guarda el repo en
    memoria antes de la primera línea (unos 35 MB) y, tras cada una, lo que
    cambió de verdad se anota en la corrida y se devuelve a sus bytes.
    """

    def __init__(self) -> None:
        self.bytes: Dict[str, bytes] = {}
        self.stat: Dict[str, Tuple[int, int]] = {}
        self.dirs: Set[str] = set()
        for p in self._recorrer():
            rel = p.relative_to(REPO).as_posix()
            self.bytes[rel] = p.read_bytes()
            self.stat[rel] = self._firma(p)
        self.dirs = {d.relative_to(REPO).as_posix() for d in REPO.rglob("*")
                     if d.is_dir() and not (_FUERA_DE_CUSTODIA & set(d.relative_to(REPO).parts))}

    @staticmethod
    def _firma(p: Path) -> Tuple[int, int]:
        s = p.stat()
        return (s.st_size, s.st_mtime_ns)

    @staticmethod
    def _recorrer() -> Iterable[Path]:
        for p in REPO.rglob("*"):
            partes = p.relative_to(REPO).parts
            if _FUERA_DE_CUSTODIA & set(partes) or partes[:3] == ("audits", "reestructura", "golden"):
                continue
            if p.is_file():
                yield p

    def restaurar(self) -> List[str]:
        """Devuelve el repo a su foto y lista lo que la línea había escrito."""
        escritas: List[str] = []
        vistos: Set[str] = set()
        for p in self._recorrer():
            rel = p.relative_to(REPO).as_posix()
            vistos.add(rel)
            if rel not in self.bytes:
                escritas.append(rel)
                p.unlink()
                padre = p.parent
                while padre != REPO and padre.relative_to(REPO).as_posix() not in self.dirs:
                    try:
                        padre.rmdir()
                    except OSError:
                        break
                    padre = padre.parent
                continue
            if self._firma(p) == self.stat[rel]:
                continue
            if p.read_bytes() != self.bytes[rel]:
                escritas.append(rel)
                p.write_bytes(self.bytes[rel])
            self.stat[rel] = self._firma(p)
        for rel in set(self.bytes) - vistos:
            escritas.append(rel)
            destino = REPO / rel
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(self.bytes[rel])
            self.stat[rel] = self._firma(destino)
        return sorted(escritas)


def _json_de(salida: str) -> Any:
    salida = salida.strip()
    if not salida:
        return None
    for candidato in (salida, salida.splitlines()[-1]):
        try:
            return json.loads(candidato)
        except ValueError:
            continue
    return None


def correr_linea(linea: List[str], ficheros: Dict[str, str], origen: Path,
                 custodia: Optional[CustodiaDelRepo] = None) -> Dict[str, Any]:
    corrida = _correr_linea(linea, ficheros, origen)
    if custodia is not None:
        corrida["repo_escritas"] = custodia.restaurar()
    return corrida


def _correr_linea(linea: List[str], ficheros: Dict[str, str], origen: Path) -> Dict[str, Any]:
    destino = Path(tempfile.mkdtemp(prefix="paridad-"))
    vault = destino / "vault"
    try:
        shutil.copytree(origen, vault, ignore=shutil.ignore_patterns(".locks", ".tmp.*"))
        cwd = SCRIPTS
        if ficheros:
            cwd = destino / "trabajo"
            cwd.mkdir()
            for clave, contenido in ficheros.items():
                ruta = (cwd / clave[len("@trabajo/"):]) if clave.startswith("@trabajo/") else (vault / clave)
                if not ruta.exists():
                    ruta.parent.mkdir(parents=True, exist_ok=True)
                    ruta.write_bytes(contenido.encode("utf-8"))
        antes = _arbol(vault)
        env = _env_base({"VAULT_ROOT": str(vault), "VAULT_MASTER": str(destino / ".casa"),
                         "PYTHONDONTWRITEBYTECODE": "1"})
        argv = [sys.executable, str(REPO / linea[0])] + linea[1:]
        inicio = time.monotonic()
        try:
            proc = subprocess.run(argv, cwd=str(cwd), env=env, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace",
                                  timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return {"exit": None, "problema": "timeout"}
        duracion = round(time.monotonic() - inicio, 2)
        despues = _arbol(vault)
        cambiadas = sorted(r for r in set(antes) | set(despues) if antes.get(r) != despues.get(r))
        norm = Normalizador(str(destino))
        datos = _json_de(proc.stdout)
        corrida: Dict[str, Any] = {"exit": proc.returncode, "cambiadas": cambiadas,
                                   "_duracion_s": duracion}
        if isinstance(datos, dict):
            corrida.update({"ok": datos.get("ok"), "error_code": datos.get("error_code"),
                            "claves": sorted(datos), "datos": norm.valor(datos)})
        else:
            # Sin envelope, el contrato es el texto: se guarda normalizado.
            corrida["texto"] = norm.texto(proc.stdout)[-4000:]
        return corrida
    finally:
        shutil.rmtree(destino, ignore_errors=True)


def capturar_envelopes(plan: Dict[str, Any], origen: Path,
                       avisar: bool = True) -> Dict[str, Any]:
    salida: Dict[str, Any] = {}
    total = len(plan["tools"])
    custodia = CustodiaDelRepo()
    for i, (nombre, entrada) in enumerate(sorted(plan["tools"].items()), 1):
        if "omitida" in entrada:
            salida[nombre] = {"omitida": entrada["omitida"]}
            continue
        salida[nombre] = [correr_linea(l, entrada["ficheros"], origen, custodia)
                          for l in entrada["lineas"]]
        if avisar:
            print(f"[paridad] {i}/{total} {nombre}", file=sys.stderr, flush=True)
    return salida


def _rutas_distintas(a: Any, b: Any, ruta: str = "") -> Iterable[str]:
    """Rutas JSON cuyo valor difiere entre a y b (listas de largo distinto: la lista)."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                yield f"{ruta}.{k}"
            else:
                yield from _rutas_distintas(a[k], b[k], f"{ruta}.{k}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            yield ruta
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                yield from _rutas_distintas(x, y, f"{ruta}[{i}]")
    elif a != b:
        yield ruta


def _clave_corrida(nombre: str, i: int) -> str:
    return f"{nombre}#{i}"


def volatiles_entre(r1: Dict[str, Any], r2: Dict[str, Any]) -> Dict[str, List[str]]:
    salida: Dict[str, List[str]] = {}
    for nombre in sorted(set(r1) & set(r2)):
        if not isinstance(r1[nombre], list):
            continue
        for i, (a, b) in enumerate(zip(r1[nombre], r2[nombre])):
            a = {k: v for k, v in a.items() if not k.startswith("_")}
            b = {k: v for k, v in b.items() if not k.startswith("_")}
            rutas = sorted(set(_rutas_distintas(a, b)))
            if rutas:
                salida[_clave_corrida(nombre, i)] = rutas
    return salida


def _quitar(datos: Any, ruta: str) -> Any:
    """Sustituye el valor de `ruta` por su tipo. La presencia sigue contando."""
    tokens = re.findall(r"\.([^.\[]+)|\[(\d+)\]", ruta)
    if not tokens:
        return f"<volatil:{type(datos).__name__}>"
    if isinstance(datos, dict):
        clave = tokens[0][0]
        if clave in datos:
            resto = ruta[len("." + clave):]
            datos = dict(datos)
            datos[clave] = _quitar(datos[clave], resto)
    elif isinstance(datos, list) and tokens[0][1]:
        i = int(tokens[0][1])
        if i < len(datos):
            resto = ruta[len(f"[{i}]"):]
            datos = list(datos)
            datos[i] = _quitar(datos[i], resto)
    return datos


def _sin_volatiles(corrida: Dict[str, Any], rutas: List[str]) -> Dict[str, Any]:
    c = {k: v for k, v in corrida.items() if not k.startswith("_")}
    for ruta in rutas:
        c = _quitar(c, ruta)
    return c


# ── orquestación ───────────────────────────────────────────────────────────


def capturar(componentes: List[str], tools: Optional[Set[str]], repeticiones: int,
             suite: Optional[Path]) -> Dict[str, Any]:
    GOLDEN.mkdir(parents=True, exist_ok=True)
    resumen: Dict[str, Any] = {"componentes": {}}
    base = Path(tempfile.mkdtemp(prefix="paridad-origen-"))
    try:
        if "estatico" in componentes:
            _escribir(GOLDEN / "estatico.json", capturar_estatico())
            resumen["componentes"]["estatico"] = "capturado"
        vault_plano = base / "plano"
        shutil.copytree(SANDBOX, vault_plano, ignore=shutil.ignore_patterns(".locks", ".tmp.*"))
        if "superficie" in componentes:
            sup = capturar_superficie(vault_plano)
            _escribir(GOLDEN / "superficie.json", sup)
            resumen["componentes"]["superficie"] = len(sup)
        if "ayuda" in componentes:
            ayu = capturar_ayuda(vault_plano)
            _escribir(GOLDEN / "ayuda.json", ayu)
            resumen["componentes"]["ayuda"] = len(ayu)
        if "envelopes" in componentes:
            plan = plan_de_envelopes(tools)
            origen = _origen(base, plan["proyecto"])
            corridas = [capturar_envelopes(plan, origen) for _ in range(max(1, repeticiones))]
            volatiles: Dict[str, List[str]] = {}
            for otra in corridas[1:]:
                for clave, rutas in volatiles_entre(corridas[0], otra).items():
                    volatiles[clave] = sorted(set(volatiles.get(clave, [])) | set(rutas))
            _escribir(GOLDEN / "envelopes.json", {
                "plan": plan, "repeticiones": len(corridas),
                "volatiles": volatiles, "corridas": corridas[0]})
            resumen["componentes"]["envelopes"] = {
                "tools": len(plan["tools"]),
                "lineas": sum(len(v.get("lineas", [])) for v in plan["tools"].values()),
                "corridas_con_volatiles": len(volatiles)}
        if suite:
            texto = suite.read_text(encoding="utf-8", errors="replace").strip().splitlines()
            ultima = next((l for l in reversed(texto) if " passed" in l or " failed" in l), "")
            cifras = {k: int(v) for v, k in re.findall(r"(\d+) (passed|failed|skipped|xfailed|xpassed|errors?)", ultima)}
            _escribir(GOLDEN / "suite.json", {"resumen": _TS.sub("<TS>", ultima), "cifras": cifras})
            resumen["componentes"]["suite"] = cifras
    finally:
        shutil.rmtree(base, ignore_errors=True)
    return {"ok": True, "golden": GOLDEN.relative_to(REPO).as_posix(), **resumen}


def _diff_conjuntos(viejo: Iterable[str], nuevo: Iterable[str]) -> Dict[str, List[str]]:
    viejo, nuevo = set(viejo), set(nuevo)
    return {"faltan": sorted(viejo - nuevo), "nuevos": sorted(nuevo - viejo)}


def comparar(componentes: List[str], tools: Optional[Set[str]]) -> Dict[str, Any]:
    informe: Dict[str, Any] = {}
    base = Path(tempfile.mkdtemp(prefix="paridad-origen-"))
    try:
        vault_plano = base / "plano"
        shutil.copytree(SANDBOX, vault_plano, ignore=shutil.ignore_patterns(".locks", ".tmp.*"))
        if "estatico" in componentes:
            viejo, nuevo = _leer(GOLDEN / "estatico.json"), capturar_estatico()
            difs = sorted(k for k in set(viejo["ficheros"]) | set(nuevo["ficheros"])
                          if viejo["ficheros"].get(k) != nuevo["ficheros"].get(k))
            ps = viejo["project_scripts"] == nuevo["project_scripts"]
            informe["estatico"] = {"ok": not difs and ps, "ficheros_distintos": difs,
                                   "project_scripts_iguales": ps}
        if "superficie" in componentes:
            viejo, nuevo = _leer(GOLDEN / "superficie.json"), capturar_superficie(vault_plano)
            roturas, nuevos = {}, {}
            for modulo, nombres in viejo.items():
                actual = nuevo.get(modulo, {"error": "modulo_ausente"})
                if isinstance(nombres, dict) or isinstance(actual, dict):
                    if nombres != actual:
                        roturas[modulo] = {"antes": nombres if isinstance(nombres, dict) else "importaba",
                                           "ahora": actual if isinstance(actual, dict) else "importa"}
                    continue
                d = _diff_conjuntos(nombres, actual)
                if d["faltan"]:
                    roturas[modulo] = d["faltan"]
                if d["nuevos"]:
                    nuevos[modulo] = d["nuevos"]
            informe["superficie"] = {"ok": not roturas, "roturas": roturas,
                                     "modulos_nuevos": sorted(set(nuevo) - set(viejo)),
                                     "nombres_nuevos": nuevos}
        if "ayuda" in componentes:
            viejo, nuevo = _leer(GOLDEN / "ayuda.json"), capturar_ayuda(vault_plano)
            difs = sorted(k for k in viejo if viejo[k] != nuevo.get(k))
            informe["ayuda"] = {"ok": not difs, "distintas": difs}
        if "envelopes" in componentes:
            golden = _leer(GOLDEN / "envelopes.json")
            plan = golden["plan"]
            if tools:
                plan = {**plan, "tools": {k: v for k, v in plan["tools"].items() if k in tools}}
            origen = _origen(base, plan["proyecto"])
            actuales = capturar_envelopes(plan, origen)
            roturas: Dict[str, Any] = {}
            for nombre, esperado in sorted(golden["corridas"].items()):
                if nombre not in plan["tools"]:
                    continue
                actual = actuales.get(nombre)
                if not isinstance(esperado, list):
                    if esperado != actual:
                        roturas[nombre] = {"antes": esperado, "ahora": actual}
                    continue
                for i, (e, a) in enumerate(zip(esperado, actual or [])):
                    rutas = golden["volatiles"].get(_clave_corrida(nombre, i), [])
                    distintas = sorted(set(_rutas_distintas(_sin_volatiles(e, rutas),
                                                            _sin_volatiles(a, rutas))))
                    if distintas:
                        roturas[_clave_corrida(nombre, i)] = distintas[:12]
                if len(esperado) != len(actual or []):
                    roturas[nombre] = f"líneas: {len(esperado)} → {len(actual or [])}"
            informe["envelopes"] = {"ok": not roturas, "tools": len(plan["tools"]),
                                    "roturas": roturas}
    finally:
        shutil.rmtree(base, ignore_errors=True)
    return {"ok": all(v["ok"] for v in informe.values()), "componentes": informe}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    modo = ap.add_mutually_exclusive_group(required=True)
    modo.add_argument("--capturar", action="store_true", help="congela el golden master")
    modo.add_argument("--comparar", action="store_true", help="compara contra el golden")
    ap.add_argument("--solo", help="componentes separados por coma: " + ",".join(COMPONENTES))
    ap.add_argument("--tools", help="restringe los envelopes a estas tools")
    ap.add_argument("--repeticiones", type=int, default=2,
                    help="capturas de envelopes para detectar lo volátil (por defecto 2)")
    ap.add_argument("--suite", type=Path, help="salida de pytest cuyo resumen se congela")
    args = ap.parse_args(argv)
    componentes = [c for c in (args.solo.split(",") if args.solo else COMPONENTES) if c]
    desconocidos = set(componentes) - set(COMPONENTES)
    if desconocidos:
        print(json.dumps({"ok": False, "error_code": "COMPONENTE_DESCONOCIDO",
                          "message": ", ".join(sorted(desconocidos))}, ensure_ascii=False))
        return 2
    tools = set(args.tools.split(",")) if args.tools else None
    if args.capturar:
        resultado = capturar(componentes, tools, args.repeticiones, args.suite)
    else:
        resultado = comparar(componentes, tools)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0 if resultado["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
