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
  sobre el conjunto; un nombre nuevo se reporta y no rompe. Tampoco rompe que
  a un paquete le falte un nombre que es un submódulo suyo que sigue
  importando: ese atributo lo pone el sistema de imports cuando *alguien* del
  proceso de la sonda importó el submódulo antes, así que depende del orden y
  no del contrato. `from paquete import sub` lo resuelve igual, y si el
  submódulo desaparece su propia clave se rompe. Se reporta aparte.
- **ayuda** — `--help` de cada script de tool y de las dos entradas de
  consola. Es la CLI publicada. Comparador `exact` tras sustituir la ruta del
  repo y del intérprete.
- **envelopes** — cada línea `python …` del `example` del catálogo, corrida
  contra una copia desechable del sandbox con el proyecto `mi-api`, con los
  ficheros que el ejemplo da por existentes. Se guarda exit, `ok`,
  `error_code`, las claves del envelope, las rutas del vault que cambió y el
  envelope normalizado.
- **escritos** (2026-11-02) — la MISMA corrida del plan, vista por otro lado:
  qué ficheros dejó la línea y con qué contenido, en digest. `cambiadas` dice
  qué paths cambian de sha; no dice qué se escribió dentro, así que una tool
  que escribiera el mismo path con otro cuerpo salía verde —el punto ciego
  que AP-44 nombra y que el plan ponía como prerrequisito de A-3—. Se mide
  sobre todo el destino de la corrida (el vault, la casa y el trabajo), no
  solo el vault: `vault_init` construye su vault nuevo en la casa.

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
| ruta del directorio que contiene al repo | `<REPO_PADRE>` | depende del clon; `vault_restore` busca ahí `vault-backups/` y la lista en `searched` | una ruta dentro del vault |
| ruta de `sys.executable` | `<PY>` | depende de la máquina | `python` en un texto |
| fecha-hora ISO 8601 | `<TS>` | reloj | una fecha sin hora de una nota del sandbox |
| la fecha de hoy (`AAAA-MM-DD`), local y UTC, en el envelope y en `cambiadas` | `<HOY>` | reloj; las tools fechan en UTC y por la tarde ya es mañana | cualquier otra fecha |

Lo que sigue variando entre **dos capturas del mismo commit** se declara
volátil por su ruta JSON y se lista en `golden/envelopes.json`
(`volatiles`). El comparador solo ignora el *valor* de esas rutas, nunca su
presencia ni su tipo. Nada se da por volátil sin haberlo visto variar.

Hay dos variaciones que dos capturas seguidas **no pueden** ver, porque
dependen del tiempo transcurrido entre la captura y la comparación. Se declaran
en `VOLATILES_DECLARADOS`, con el motivo y lo que se sigue comparando. Las vio
variar la primera comparación completa del cierre del bloque A, seis horas
después del golden, sin que el tablón tocara nada de su camino:

| Corrida | Qué varía | Por qué | Lo que se sigue comparando |
|---|---|---|---|
| `vault_backup#0/#1` | `sizeKB` de la sección y del total | el origen copia el estado de ejecución del sandbox, que no está versionado (`.tool-trace.json` crece con cada test o puerta) | los ficheros copiados, `cambiadas` y el resto del manifiesto |
| `vault_context_pack#0` | la cuarta cifra de cada `score` | la puntuación suma la recencia contra el reloj (vida media de 90 días) | qué notas entran, en qué orden y el texto del paquete fuera de `score N` |
| `vault_audit#0`, `vault_init#0/#1/#2` | `daysSinceUpdate` de cada nota `stale` | son días contra el reloj; el golden se capturó el 2026-10-30 y el primer tablón de B se midió al día siguiente | qué notas salen como `stale`, en qué orden y su `updated` |
| `vault_metricas#0` | `dias_restantes` de cada fila | los días hasta el plazo del objetivo, contados desde hoy | el plazo, el valor y el estado de cada fila |
| `vault_change_log#0` | `total` y el `id` de cada entrada | el origen copia `.change-log.json` del sandbox, que no está versionado y crece con cada test (403 → 424 entre el golden y B-1) | la acción, la ruta, el motivo y el agente de cada una de las diez entradas |
| `vault_quality_check#0` | `scores.timeliness` de cada nota y la cifra de su aviso `timeliness: N days since update` | días contra el reloj, como `daysSinceUpdate` | qué notas avisan de vigencia, el resto de avisos y de puntuaciones |
| `vault_ncr_save#0` | el mes (`AAAA-MM`) del nombre de la nota, en `datos.path` y en `cambiadas` | la tool pone el mes UTC en el nombre; el golden es de octubre y la noche del 2026-10-31 ya era noviembre en UTC | la carpeta, el resto del nombre y las demás rutas de `cambiadas` |
| `vault_query_parse#0` | la fecha `since` de una expresión temporal relativa, allí donde aparece (`structured.temporal`, `evidence`, `plan`) | «la semana pasada» se resuelve contra el reloj UTC (hoy menos 14 días): 2026-10-17 en el golden, 2026-10-18 en el cierre de B-1 | la expresión, su `kind`, qué evidencias y pasos del plan llevan la fecha y todo lo demás |

La vista `escritos` normaliza por su cuenta, y solo por su cuenta, lo que una
tool genera al escribir: el `uuid` de una nota o de una entry de índice, el
sello `AAAAMMDD-HHMMSS` de un fichero de trabajo, la hora local suelta tras
`<HOY>`, el mes del nombre de un NCR, su número aleatorio y el `sha256` que
un índice calcula sobre el fichero crudo. Es la misma regla que aplica
`VOLATILES_DECLARADOS` a los envelopes, pero en la vista que mide el
CONTENIDO y no el envelope: allí la tabla del `Normalizador` no se toca
porque el golden de envelopes está congelado con 67 uuids crudos detrás de
declarados. Dos huecos quedan escritos, no escondidos: el algoritmo del
hash de un índice no queda protegido (las claves y el resto del índice, sí),
y el estado que `git init` genera en la casa se excluye del árbol.

Las tools que miden el propio repo (`vault_clones`, `vault_metricas`, …)
**no** se declaran: cuando un tablón cambia lo que miden, su rojo es el delta
del tablón y se anota con sus cifras en `CHANGELOG-REFACTOR.md`.

Cada repetición construye **su propio vault de origen**. Dar de alta `mi-api`
estampa la hora en la nota y en el índice, y un hash sobre ese contenido
(`merkle_root` de `vault_backup`, `source_sha` de `vault_graph_fix`) varía con
el origen y no con la corrida. Hasta el 2026-10-31 las dos repeticiones
compartían un origen, el detector no podía verlo y la primera comparación
completa lo dio por rotura. Contraejemplo: `cambiadas` de esas mismas líneas
no depende del reloj y sigue sin declararse volátil.

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
COMPONENTES = ("estatico", "superficie", "ayuda", "envelopes", "escritos")

# `escritos` (2026-11-01): el contenido normalizado de lo que cada línea deja
# en su destino — el vault, la casa (VAULT_MASTER) y el trabajo. `cambiadas`
# (envelopes) dice qué paths cambian de sha, no con qué contenido: escribir el
# mismo path con otro contenido era verde —el punto ciego AP-44 que el plan
# nombra como prerrequisito de A-3—. La vista no es "paths-only", que
# duplicaría a `cambiadas` midiendo con su misma normalización: lo que compara
# es el contenido, y por eso detecta regresar mientras el envelope siga igual.

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
        # Después de <REPO>, que la contiene: si no, el repo saldría como <REPO_PADRE>\<nombre>.
        self.pares += [(v, "<REPO_PADRE>") for v in _variantes(str(REPO.parent))]
        self.pares += [(v, "<PY>") for v in _variantes(sys.executable)]
        # Local y UTC: las tools fechan con `utcnow()` y entre las 18:00 y la
        # medianoche de aquí ya son otro día. Medido el 2026-10-31.
        self.hoys = sorted({_dt.date.today().isoformat(),
                            _dt.datetime.now(_dt.timezone.utc).date().isoformat()})

    def texto(self, s: str) -> str:
        for viejo, nuevo in self.pares:
            if viejo in s:
                s = s.replace(viejo, nuevo)
        s = _TS.sub("<TS>", s)
        for hoy in self.hoys:
            s = s.replace(hoy, "<HOY>")
        return s

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


def comparar_superficie(viejo: Dict[str, Any], nuevo: Dict[str, Any]) -> Dict[str, Any]:
    roturas: Dict[str, Any] = {}
    nuevos: Dict[str, Any] = {}
    por_orden: Dict[str, Any] = {}
    for modulo, nombres in viejo.items():
        actual = nuevo.get(modulo, {"error": "modulo_ausente"})
        if isinstance(nombres, dict) or isinstance(actual, dict):
            if nombres != actual:
                roturas[modulo] = {"antes": nombres if isinstance(nombres, dict) else "importaba",
                                   "ahora": actual if isinstance(actual, dict) else "importa"}
            continue
        d = _diff_conjuntos(nombres, actual)
        submodulos = [n for n in d["faltan"] if isinstance(nuevo.get(f"{modulo}.{n}"), list)]
        faltan = [n for n in d["faltan"] if n not in submodulos]
        if faltan:
            roturas[modulo] = faltan
        if submodulos:
            por_orden[modulo] = submodulos
        if d["nuevos"]:
            nuevos[modulo] = d["nuevos"]
    return {"ok": not roturas, "roturas": roturas,
            "modulos_nuevos": sorted(set(nuevo) - set(viejo)),
            "nombres_nuevos": nuevos,
            "submodulos_que_dependen_del_orden": por_orden}


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


def _escritos_de(antes: Dict[str, str], despues: Dict[str, str], destino: Path,
                 norm: Normalizador) -> Dict[str, Any]:
    """La vista `escritos` de una línea: ruta relativa al destino → contenido.

    Toda la corrida va bajo `destino`; lo que queda FUERA del vault se compara
    igual — `vault_init` construye su vault nuevo en la casa y ocultar el
    árbol por solo-`vault` cegaría justo al ejemplo más escritor. La ruta va
    prefijada (`vault/…`, `.casa/…`, `trabajo/…`), así que cada fichero declara
    dónde lo dejó la tool. Un borrado solo se prueba desde `antes` y queda como
    `<borrado>`; un fichero sin vía de texto viaja con su `sha256:` (el
    contenido no se normaliza, así que es lo más caro de ver volátil).
    """
    salida: Dict[str, Any] = {}
    for r in sorted(set(antes) | set(despues)):
        if antes.get(r) == despues.get(r):
            continue
        if r not in despues:
            salida[norm.texto(r)] = "<borrado>"
            continue
        try:
            contenido = (destino / r).read_text(encoding="utf-8", errors="replace")
        except OSError:
            salida[norm.texto(r)] = f"sha256:{despues[r]}"
            continue
        salida[norm.texto(r)] = norm.texto(contenido)
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
        antes_todo = _arbol(destino)
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
        despues_todo = _arbol(destino)
        norm = Normalizador(str(destino))
        # Se ordena antes de normalizar: el índice de una ruta volátil no se mueve.
        cambiadas = [norm.texto(r) for r in
                     sorted(r for r in set(antes) | set(despues) if antes.get(r) != despues.get(r))]
        escritos = _escritos_de(antes_todo, despues_todo, destino, norm)
        datos = _json_de(proc.stdout)
        corrida: Dict[str, Any] = {"exit": proc.returncode, "cambiadas": cambiadas,
                                   "escritos": escritos, "_duracion_s": duracion}
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
        salida[nombre] = [{k: v for k, v in
                           correr_linea(l, entrada["ficheros"], origen, custodia).items()
                           if k != "escritos"}
                          for l in entrada["lineas"]]
        if avisar:
            print(f"[paridad] {i}/{total} {nombre}", file=sys.stderr, flush=True)
    return salida


def capturar_escritos(plan: Dict[str, Any], origen: Path,
                      avisar: bool = True) -> Dict[str, Any]:
    """La vista `escritos` de las mismas líneas del plan: qué contenido dejó.

    Misma corrida, otro corte: de cada línea conserva solo `escritos` (el
    `correr_linea` ya lo produce sin coste extra). Es el prerrequisito de A-3
    y no toca la forma congelada de `golden/envelopes.json`.
    """
    salida: Dict[str, Any] = {}
    total = len(plan["tools"])
    custodia = CustodiaDelRepo()
    for i, (nombre, entrada) in enumerate(sorted(plan["tools"].items()), 1):
        if "omitida" in entrada:
            salida[nombre] = {"omitida": entrada["omitida"]}
            continue
        salida[nombre] = [{"escritos": l.get("escritos", {})} for l in
                          (correr_linea(l, entrada["ficheros"], origen, custodia)
                           for l in entrada["lineas"])]
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


def _sin_volatiles_escritos(escritos: Dict[str, Any],
                             rutas: List[str]) -> Dict[str, Any]:
    """Quita de la vista `escritos` las rutas declaradas volátiles.

    No se usa `_quitar` —la navegación por tokens— porque la clave de un
    fichero lleva puntos (`mi-api-deploy.md`) y el punto separaría la clave de
    su extensión. Aquí la ruta ES la clave: se recorta el prefijo y se
    compara entero, que es lo que se quiso decir.
    """
    fuera = set()
    for ruta in rutas:
        if ruta.startswith(".escritos."):
            fuera.add(ruta[len(".escritos."):])
    return {k: v for k, v in escritos.items() if k not in fuera}


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


_SCORE = re.compile(r"score \d+\.\d+")
_DIAS = re.compile(r"timeliness: \d+ days since update")


def _timeliness_sin_reloj(c: Dict[str, Any]) -> Dict[str, Any]:
    """`vault_quality_check`: los días de cada nota y su puntuación de vigencia.

    Las claves de `notes` son rutas con puntos, que la sintaxis de rutas no
    puede nombrar; por eso es una función y no una entrada de `rutas`.
    """
    notas = (c.get("datos") or {}).get("notes")
    if isinstance(notas, dict):
        for nota in notas.values():
            if not isinstance(nota, dict):
                continue
            if isinstance(nota.get("scores"), dict) and "timeliness" in nota["scores"]:
                nota["scores"]["timeliness"] = "<volatil:float>"
            if isinstance(nota.get("issues"), list):
                nota["issues"] = [_DIAS.sub("timeliness: <N> days since update", i)
                                  if isinstance(i, str) else i for i in nota["issues"]]
    return c


_MES = re.compile(r"(?<!\d)\d{4}-\d{2}(?!-?\d)")


def _mes_sin_reloj(c: Dict[str, Any]) -> Dict[str, Any]:
    """El `AAAA-MM` suelto de `datos.path` y de `cambiadas`: el mes del reloj.

    Una fecha completa (`AAAA-MM-DD`) no casa, ni un id como `NCR-2026-118`.
    """
    if isinstance(c.get("cambiadas"), list):
        c["cambiadas"] = [_MES.sub("<MES>", r) if isinstance(r, str) else r
                          for r in c["cambiadas"]]
    datos = c.get("datos")
    if isinstance(datos, dict) and isinstance(datos.get("path"), str):
        datos["path"] = _MES.sub("<MES>", datos["path"])
    return c



def _desde_sin_reloj(c: Dict[str, Any]) -> Dict[str, Any]:
    """`vault_query_parse`: el `since` de una expresión relativa, que sale del reloj.

    Solo se sustituye ese valor exacto, y solo si la expresión es `relative`:
    una fecha absoluta de la consulta sigue comparándose.
    """
    datos = c.get("datos")
    temporal = ((datos or {}).get("structured") or {}).get("temporal") if isinstance(datos, dict) else None
    if not (isinstance(temporal, dict) and temporal.get("kind") == "relative"
            and isinstance(temporal.get("since"), str)):
        return c
    desde = temporal["since"]

    def sustituir(v: Any) -> Any:
        if isinstance(v, dict):
            return {k: sustituir(x) for k, x in v.items()}
        if isinstance(v, list):
            return [sustituir(x) for x in v]
        return "<DESDE>" if v == desde else v

    c["datos"] = sustituir(datos)
    return c


_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
_SHA256 = re.compile(r"\b[0-9a-f]{64}\b")


def _determinizar(s: str) -> str:
    """Lo que la vista `escritos` perdona: identidad, sellos de reloj y hashes.

    - `<UUID>`: la tool generó un identificador (un `id:` de frontmatter, un
      `docId` de índice, un id de entry en `.change-log.json`). Se compara por
      PRESENCIA y forma, no por valor: el valor es aleatorio por diseño del
      producto.
    - `<STAMP>`: el `AAAAMMDD-HHMMSS` compacto que la tool estampa en nombres de
      fichero de trabajo (`00_System/.trash/foo-<STAMP>.md.bak`,
      `vault-backups/.vault-fix-backup-<STAMP>/`).
    - `<HOY>THH-MM-SS` y `<HOY>-HHMMSS`: reloj residual en el nombre que la
      tabla del `Normalizador` no tapa (`.history/<nota>__old-<HOY>T03-12-26.md`,
      `vault-backups/vault-<HOY>-031044/`).
    - `<SHA256>`: el hash de un índice (`99_Index/hash-index.json`,
      `vault-backups/.manifest.json`) se calcula sobre el fichero CRUDO, que
      lleva lo de arriba dentro, así que el valor no es igualable de captura a
      captura. Hueco declarado: el ALGORITMO del hash no queda protegido en
      esta vista —las claves del índice y el resto del contenido, sí—.
    - `<HORA>`: la hora local sin segundos que queda tras `<HOY>` (el historial
      de ejecuciones de un runbook: `-- <HOY> 03:39`). El `Normalizador` solo
      tapa la marca de tiempo COMPLETA (`_TS` exige los segundos).
    - `NCR-AAAA-<N>`: el número de no conformidad es aleatorio por diseño
      (`random.randint(100, 999)` en `vault_ncr_save.py`). En el golden de
      envelopes ya está declarado volátil en `.datos.ncr_id`; aquí la misma
      regla, porque el id aparece también en el cuerpo de la nota y en los
      índices que la resumen.
    - `<MES>`: el `AAAA-MM` del nombre de fichero (el NCR se titula con el mes
      UTC). El `Normalizador` no lo tapa —no es fecha completa— y el golden de
      envelopes lo declara con el mismo motivo (`_mes_sin_reloj`).
    Aplicado igual a claves y a contenido, y solo en la vista `escritos`: la
    tabla del Normalizador es del golden congelado de envelopes y ahí no se
    toca (67 uuids crudos detrás de declarados, 2026-11-02).
    """
    s = _UUID.sub("<UUID>", s)
    s = re.sub(r"(?<!\d)\d{8}-\d{6}(?!\d)", "<STAMP>", s)
    s = re.sub(r"<HOY>T\d{2}-\d{2}-\d{2}", "<HOY>THH-MM-SS", s)
    s = re.sub(r"(?<=<HOY>)-\d{6}\b", "-HHMMSS", s)
    s = re.sub(r"(?<=<HOY> )\d{2}:\d{2}\b", "<HORA>", s)
    s = re.sub(r"NCR-(\d{4})-\d{3}\b", r"NCR-\1-<N>", s)
    s = _MES.sub("<MES>", s)
    return _SHA256.sub("<SHA256>", s)


def _escritos_de(antes: Dict[str, str], despues: Dict[str, str], destino: Path,
                 norm: Normalizador) -> Dict[str, Any]:
    """La vista `escritos` de una línea: ruta relativa al destino → DIGEST.

    Toda la corrida va bajo `destino`; lo que queda FUERA del vault se compara
    igual — `vault_init` construye su vault nuevo en la casa y ocultar el
    árbol por solo-`vault` cegaría justo al ejemplo más escritor. La ruta va
    prefijada (`vault/…`, `.casa/…`, `trabajo/…`), así que cada fichero declara
    dónde lo dejó la tool. Un borrado solo se prueba desde `antes` y queda como
    `<borrado>`; un fichero sin vía de texto viaja con el sha de sus bytes.

    Lo que se guarda es el **sha256 del contenido ya normalizado**, no el
    contenido. Detecta lo mismo —una tool que escribe el mismo path con otro
    cuerpo es una rotura— y el golden baja de 10,4 MB a ~100 KB: el repo
    versiona 22 MB y su mayor fichero son 1,3 MB, así que un golden de 10 MB
    sería media tabla. Además el golden deja de llevar dentro el texto del
    vault, que no es lo que se compara. Es la misma convención que la vista de
    envelopes, que reporta rutas distintas y no valores.

    `git` se excluye del árbol de la casa: es estado que `git init` genera
    (objetivos, logs, index), no la nota que la tool escribe; comparar sus
    internals sería ruido permanente del mecanismo, no señal de producto.
    """
    salida: Dict[str, Any] = {}
    for r in sorted(set(antes) | set(despues)):
        if ".git" in r.split("/"):
            continue
        if antes.get(r) == despues.get(r):
            continue
        if r not in despues:
            salida[_determinizar(norm.texto(r))] = "<borrado>"
            continue
        try:
            contenido = (destino / r).read_text(encoding="utf-8", errors="replace")
        except OSError:
            salida[_determinizar(norm.texto(r))] = f"sha256:{despues[r]}"
            continue
        normalizado = _determinizar(norm.texto(contenido))
        salida[_determinizar(norm.texto(r))] = hashlib.sha256(
            normalizado.encode("utf-8")).hexdigest()
    return salida


# Lo que la captura no puede ver variar (ver el docstring). `[*]` cubre cada
# elemento de la lista; los textos se normalizan solo en el patrón declarado.
VOLATILES_DECLARADOS: Dict[str, Dict[str, Any]] = {
    **{f"vault_backup#{i}": {"rutas": [".datos.manifest.sections[*].sizeKB",
                                       ".datos.manifest.totals.sizeKB"]}
       for i in (0, 1)},
    "vault_context_pack#0": {"rutas": [".datos.included[*].score"],
                             "textos": {".datos.context": (_SCORE, "score <S>")}},
    "vault_audit#0": {"rutas": [".datos.issues.stale[*].daysSinceUpdate"]},
    **{f"vault_init#{i}": {"rutas": [".datos.steps[*].output.issues.stale[*].daysSinceUpdate"]}
       for i in (0, 1, 2)},
    "vault_metricas#0": {"rutas": [".datos.filas[*].dias_restantes"]},
    "vault_quality_check#0": {"ajuste": _timeliness_sin_reloj},
    "vault_change_log#0": {"rutas": [".datos.total", ".datos.entries[*].id"]},
    "vault_ncr_save#0": {"ajuste": _mes_sin_reloj},
    "vault_query_parse#0": {"ajuste": _desde_sin_reloj},
}


def _expandir(datos: Any, ruta: str) -> List[str]:
    """Las rutas concretas de `ruta`, con cada `[*]` resuelto contra `datos`."""
    if "[*]" not in ruta:
        return [ruta]
    cabeza, cola = ruta.split("[*]", 1)
    nodo: Any = datos
    for clave, indice in re.findall(r"\.([^.\[]+)|\[(\d+)\]", cabeza):
        try:
            nodo = nodo[clave] if clave else nodo[int(indice)]
        except (KeyError, IndexError, TypeError):
            return []
    if not isinstance(nodo, list):
        return []
    return [r for i in range(len(nodo)) for r in _expandir(datos, f"{cabeza}[{i}]{cola}")]


def _sin_declarados(corrida: Dict[str, Any], clave: str) -> Dict[str, Any]:
    decl = VOLATILES_DECLARADOS.get(clave)
    if not decl:
        return corrida
    c = json.loads(json.dumps(corrida))
    for ruta, (patron, por) in decl.get("textos", {}).items():
        nodo: Any = c
        claves = re.findall(r"\.([^.\[]+)", ruta)
        for k in claves[:-1]:
            nodo = nodo.get(k, {}) if isinstance(nodo, dict) else {}
        if isinstance(nodo, dict) and isinstance(nodo.get(claves[-1]), str):
            nodo[claves[-1]] = patron.sub(por, nodo[claves[-1]])
    for ruta in decl.get("rutas", []):
        for concreta in _expandir(c, ruta):
            c = _quitar(c, concreta)
    if decl.get("ajuste"):
        c = decl["ajuste"](c)
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
            corridas = []
            for i in range(max(1, repeticiones)):
                rep = base / f"rep{i}"
                rep.mkdir()
                corridas.append(capturar_envelopes(plan, _origen(rep, plan["proyecto"])))
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
        if "escritos" in componentes:
            plan_e = plan_de_envelopes(tools)
            corridas_e = []
            for i in range(max(1, repeticiones)):
                rep = base / f"rep-e{i}"
                rep.mkdir()
                corridas_e.append(capturar_escritos(plan_e, _origen(rep, plan_e["proyecto"])))
            volatiles_e: Dict[str, List[str]] = {}
            for otra in corridas_e[1:]:
                for clave, rutas in volatiles_entre(corridas_e[0], otra).items():
                    volatiles_e[clave] = sorted(set(volatiles_e.get(clave, [])) | set(rutas))
            _escribir(GOLDEN / "escritos.json", {
                "plan": plan_e, "repeticiones": len(corridas_e),
                "volatiles": volatiles_e, "corridas": corridas_e[0]})
            resumen["componentes"]["escritos"] = {
                "tools": len(plan_e["tools"]),
                "lineas": sum(len(v.get("lineas", [])) for v in plan_e["tools"].values()),
                "ficheros_escritos": sum(len(l.get("escritos", {}))
                                         for li in corridas_e[0].values() if isinstance(li, list)
                                         for l in li),
                "corridas_con_volatiles": len(volatiles_e)}
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
            informe["superficie"] = comparar_superficie(
                _leer(GOLDEN / "superficie.json"), capturar_superficie(vault_plano))
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
                    clave = _clave_corrida(nombre, i)
                    rutas = golden["volatiles"].get(clave, [])
                    distintas = sorted(set(_rutas_distintas(
                        _sin_declarados(_sin_volatiles(e, rutas), clave),
                        _sin_declarados(_sin_volatiles(a, rutas), clave))))
                    if distintas:
                        roturas[_clave_corrida(nombre, i)] = distintas[:12]
                if len(esperado) != len(actual or []):
                    roturas[nombre] = f"líneas: {len(esperado)} → {len(actual or [])}"
            informe["envelopes"] = {"ok": not roturas, "tools": len(plan["tools"]),
                                    "roturas": roturas}
        if "escritos" in componentes:
            golden_e = _leer(GOLDEN / "escritos.json")
            plan = golden_e["plan"]
            if tools:
                plan = {**plan, "tools": {k: v for k, v in plan["tools"].items() if k in tools}}
            origen = _origen(base, plan["proyecto"])
            actuales = capturar_escritos(plan, origen)
            roturas: Dict[str, Any] = {}
            for nombre, esperado in sorted(golden_e["corridas"].items()):
                if nombre not in plan["tools"]:
                    continue
                actual = actuales.get(nombre)
                if not isinstance(esperado, list):
                    if esperado != actual:
                        roturas[nombre] = {"antes": esperado, "ahora": actual}
                    continue
                for i, (e, a) in enumerate(zip(esperado, actual or [])):
                    clave = _clave_corrida(nombre, i)
                    rutas = golden_e["volatiles"].get(clave, [])
                    # La vista guarda un digest por ruta, así que la rotura es
                    # la ruta cuyo digest cambió —el mismo path con otro
                    # cuerpo— y no una diferencia de estructura.
                    ee = _sin_volatiles_escritos(e.get("escritos", {}), rutas)
                    aa = _sin_volatiles_escritos(a.get("escritos", {}), rutas)
                    distintas = sorted(k for k in set(ee) | set(aa) if ee.get(k) != aa.get(k))
                    if distintas:
                        roturas[_clave_corrida(nombre, i)] = distintas[:12]
                if len(esperado) != len(actual or []):
                    roturas[nombre] = f"líneas: {len(esperado)} → {len(actual or [])}"
            informe["escritos"] = {"ok": not roturas, "tools": len(plan["tools"]),
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
