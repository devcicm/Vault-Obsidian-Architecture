"""Apoyo compartido de la suite: lo que un test no reescribe (AP-69).

Cada clase de `vault_tests_higiene.CLASES` tiene aquí su
sustituto. Lanzar una tool, fabricar una nota de prueba o leer el envelope de
una corrida se decide **una vez**: el entorno del hijo, la codificación y el
timeout son de este módulo, y cambiarlos es un diff aquí, no en 239 ficheros.

    from apoyo import ROOT, correr_tool, nota

    r = correr_tool("vault_audit", vault=tmp_path)
    assert r.codigo == 0 and r.envelope["ok"]

    (tmp_path / "a.md").write_text(nota({"title": "A", "status": "draft"}, '''
        # A
        cuerpo
    '''), encoding="utf-8")

Este fichero no lo mide `vault_tests_higiene`: es el sitio donde ese código
tiene que estar.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Literal, Mapping, Optional

import yaml

from vault.kernel import rutas
from vault.kernel.bloqueo import proceso_vivo as _consultar_proceso

ROOT = rutas.raiz_repo()
SCRIPTS = rutas.ruta_repo(rutas.SCRIPTS)
TESTS = ROOT / "tests"

#: Lo que el 80 % de los lanzadores privados medidos el 2026-10-31 usaba.
TIMEOUT_S = 300


@dataclass(frozen=True)
class Corrida:
    """El resultado de lanzar una tool: código, salidas y el envelope leído."""

    codigo: int
    stdout: str
    stderr: str

    @property
    def returncode(self) -> int:
        """Alias de `codigo`: el nombre que tenía `CompletedProcess`.

        Los tests que pasaron de subproceso a ejecución en proceso leen
        `proceso.returncode`, y el alias evita tocar cada línea: lo que cambia
        es QUIÉN corre la tool, no el nombre del campo.
        """
        return self.codigo

    @property
    def envelope(self) -> Dict[str, Any]:
        """El JSON que la tool imprimió, desde la primera `{`.

        Falla con la cola del stderr a la vista: un envelope que no llega es
        casi siempre una traza, y un `JSONDecodeError` a secas la esconde.
        """
        salida = self.stdout.strip()
        assert "{" in salida, f"la tool no imprimió un envelope:\n{self.stderr[-1500:]}"
        return json.loads(salida[salida.index("{"):])


def entorno(vault: Optional[Path] = None, quitar: tuple = (), **extra: Any) -> Dict[str, str]:
    """El entorno de un hijo: utf-8, agente `pytest` y, con `vault`, raíz estricta.

    `quitar` retira variables heredadas que cambiarían la resolución de la raíz
    (p. ej. `VAULT_PERMISSIVE_ROOT`); `extra` añade o sustituye.
    """
    env = dict(
        os.environ,
        PYTHONIOENCODING="utf-8",
        PYTHONDONTWRITEBYTECODE="1",
        VAULT_AGENT="pytest",
    )
    if vault is not None:
        env.update(VAULT_ROOT=str(vault), VAULT_STRICT_ROOT="1")
    for nombre in quitar:
        env.pop(nombre, None)
    env.update({k: str(v) for k, v in extra.items()})
    return env


def correr_tool(nombre: str, *argv: Any, vault: Optional[Path] = None,
                env: Optional[Mapping[str, str]] = None, cwd: Optional[Path] = None,
                timeout: float = TIMEOUT_S) -> Corrida:
    """Lanza `scripts/<nombre>.py` con el intérprete de la suite.

    Sin `env`, el de `entorno(vault)`. El `cwd` por defecto es la raíz del repo,
    que es desde donde la documentación dice que se ejecutan las tools.
    """
    script = nombre if nombre.endswith(".py") else f"{nombre}.py"
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *map(str, argv)],
        env=dict(env) if env is not None else entorno(vault),
        cwd=str(cwd or ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout)
    return Corrida(p.returncode, p.stdout, p.stderr)


def _entorno_python(vault: Optional[Path],
                    env: Optional[Mapping[str, str]]) -> Dict[str, str]:
    """Compose a child environment that imports this checkout before site packages."""
    resultado = dict(env) if env is not None else entorno(vault)
    # Windows + Python 3.10: `CryptGenRandom` durante `_Py_HashRandomization_Init`
    # exige `SYSTEMROOT` cuando el llamador pasa un `env` mínimo.
    if (
        os.name == "nt"
        and "SYSTEMROOT" in os.environ
        and not any(k.upper() == "SYSTEMROOT" for k in resultado)
    ):
        resultado["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    heredado = resultado.get("PYTHONPATH", "")
    rutas_importacion = [Path(p) for p in heredado.split(os.pathsep) if p]
    rutas_importacion.extend((ROOT, SCRIPTS, TESTS))
    unicas = list(dict.fromkeys(str(p) for p in rutas_importacion))
    resultado["PYTHONPATH"] = os.pathsep.join(unicas)
    return resultado


def correr_python(*argv: Any, vault: Optional[Path] = None,
                  env: Optional[Mapping[str, str]] = None,
                  cwd: Optional[Path] = None,
                  timeout: float = TIMEOUT_S,
                  modo: Literal["bytes", "text"] = "text",
                  capture_output: bool = True,
                  check: bool = False,
                  input: Any = None) -> subprocess.CompletedProcess:
    """Run arbitrary Python with explicit byte or UTF-8 text capture semantics.

    `capture_output=False` leaves stdout/stderr inherited, which is required by
    probes that measure a child's effect on its parent's streams.
    """
    if modo not in ("bytes", "text"):
        raise ValueError("modo debe ser 'bytes' o 'text'")
    text_mode = modo == "text"
    kwargs: Dict[str, Any] = {
        "env": _entorno_python(vault, env),
        "cwd": str(cwd or ROOT),
        "timeout": timeout,
        "capture_output": capture_output,
        "check": check,
        "input": input,
        "text": text_mode,
    }
    if text_mode:
        kwargs.update(encoding="utf-8", errors="replace")
    return subprocess.run([sys.executable, *map(str, argv)], **kwargs)


def lanzar_python(*argv: Any, vault: Optional[Path] = None,
                  env: Optional[Mapping[str, str]] = None,
                  cwd: Optional[Path] = None,
                  **kwargs: Any) -> subprocess.Popen:
    """Launch arbitrary Python; omitted streams stay inherited from the caller."""
    return subprocess.Popen(
        [sys.executable, *map(str, argv)],
        env=_entorno_python(vault, env),
        cwd=str(cwd) if cwd is not None else None, **kwargs)


def esperar_condicion(condicion, *, timeout: float,
                      intervalo: float = 0.01) -> bool:
    """Wait for a predicate until a monotonic deadline, without fixed sleeps."""
    if timeout < 0 or intervalo <= 0:
        raise ValueError("timeout debe ser >= 0 e intervalo debe ser > 0")
    limite = time.monotonic() + timeout
    despertar = threading.Event()
    while True:
        if condicion():
            return True
        restante = limite - time.monotonic()
        if restante <= 0:
            return False
        despertar.wait(min(intervalo, restante))


def proceso_activo(pid: int) -> bool:
    """Check a PID through the shared read-only platform query; unknown is alive."""
    return _consultar_proceso(pid) is not False


def correr_en_proceso(nombre: str, *argv: Any, vault: Optional[Path] = None,
                       agente: Optional[str] = None,
                       cwd: Optional[Path] = None) -> Corrida:
    """Ejecuta `scripts/<nombre>.py` en ESTE intérprete: repone argv en `sys.argv` y corre `main()`.

    Mismo contrato que `correr_tool` —código, stdout, stderr y el envelope— sin
    el arranque del intérprete, que medido era la mayor parte del tiempo de los
    dos test modules con más subprocesos de la suite (C-2, tablón de la raíz de
    composición). La frontera es la de la casa:

    - **En proceso**, el comportamiento: que la tool acepte estos argumentos,
      escriba donde debe y conteste `ok: true`.
    - **Por subproceso** (`correr_tool`), el contrato CLI: que el script
      publicado arranca, rechaza lo malformado sin traceback y su envelope
      llega por stdout. Uno por tool, no por caso.

    La raíz va por `set_vault_root()`, el API que AP-49 dejó honesta (0
    vínculos congelados medidos el 2026-11-01): se fija, se reanchan las
    constantes y se restaura la anterior al salir — el patrón que ya usan
    `test_alcance_medido_v4030` y `test_ap07`, con el autouse
    `_raiz_de_vault_limpia` del conftest respaldando al conjunto.

    `agente` es el `VAULT_AGENT` con el que la tool firma (AP-16) y `cwd` el
    directorio desde el que corre; por defecto, el directorio del script, que
    es donde la documentación dice que se ejecutan las tools.

    **El mecanismo es del producto, no de la suite** (`vault.ejecutor`, C-2
    tanda 2): el ejecutor devuelve el intérprete al estado en que lo encontró
    —argv, directorio, raíz y variables—, corre la tool en su propio hilo (el
    ledger de escrituras es thread-local) y devuelve su envelope. Aquí solo se
    traduce su resultado al `Corrida` que la suite ya consume. Dos
    implementaciones del mismo mecanismo divergen; esta es la única.

    **El envoltorio es el de la CLI** (`wrap_main`): por subproceso la tool
    corre por su bloque `__main__`, que la envuelve en `wrap_main` —el timeout,
    el canónico de AP-52, la voz y el ledger—. En proceso, sin ese envoltorio,
    la tool imprimiría su JSON crudo y el envelope sería otro: no es la misma
    tool, es otra. Con el envoltorio, la salida es byte a byte la de la CLI.
    """
    from vault.ejecutor import ejecutar
    from vault_errors import wrap_main

    # El nombre puede llegar con o sin extensión: hay llamadores que pasan
    # «vault_init.py» (el script) y otros que pasan «vault_init» (el módulo).
    script = nombre if nombre.endswith(".py") else f"{nombre}.py"
    corrida = ejecutar(None, [script, *map(str, argv)], raiz=vault,
                       agente=agente, cwd=cwd, envoltorio=wrap_main)
    return Corrida(corrida.codigo, corrida.texto, corrida.error)


def git_en(vault: Path, *args: str,
           env: Optional[Mapping[str, str]] = None,
           check: bool = False) -> str:
    """La salida de `git` en ese repo: el lanzador, aquí y no en cada test.

    La capa de git del vault (v41.26) hace que `git log` sea parte del
    contrato observable —cada operación que escribe deja un commit— y los
    tests tienen que poder mirarlo. Un `subprocess.run(["git", ...])` en cada
    test es exactamente lo que AP-69 veta: el lanzador privado. `env` aplica
    variables solo a esta llamada; `check=True` hace visibles los errores que
    un fixture no debe confundir con una preparaciÃ³n exitosa.
    """
    p = subprocess.run(["git", "-C", str(vault), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120,
                       env=dict(env) if env is not None else None)
    if check and p.returncode:
        raise subprocess.CalledProcessError(
            p.returncode, p.args, output=p.stdout, stderr=p.stderr)
    return (p.stdout or "").strip()


def nota(frontmatter: Mapping[str, Any], cuerpo: str = "") -> str:
    """El texto de una nota: frontmatter serializado por YAML y cuerpo sin sangría.

    El frontmatter sale de `yaml.safe_dump`, el mismo criterio con el que lo
    lee el vault (AP-44): un título con `:` o comillas no rompe la nota de
    prueba sin que el test lo sepa.
    """
    cabecera = yaml.safe_dump(dict(frontmatter), sort_keys=False, allow_unicode=True)
    return f"---\n{cabecera}---\n\n{textwrap.dedent(cuerpo).lstrip()}"


def escribir_nota(raiz: Path, relativa: str, frontmatter: Mapping[str, Any],
                  cuerpo: str = "") -> Path:
    """Escribe `nota(...)` en `raiz/relativa`, creando las carpetas, en LF."""
    ruta = raiz / relativa
    ruta.parent.mkdir(parents=True, exist_ok=True)
    # Bytes: `write_text(newline=)` no existe en el piso (3.9).
    ruta.write_bytes(nota(frontmatter, cuerpo).encode("utf-8"))
    return ruta


def filas_de_bitacora(raiz: Path) -> list:
    """Every change-log row of `raiz`, read by the log's owner (both formats).

    The log is append-only since bigo-inmutabilidad: new rows live in
    `.change-log.jsonl` and an older vault keeps its frozen `.change-log.json`.
    A test that opened one of them would see half the history.
    """
    from vault.gobernanza.repositorio import RepositorioGobernanza
    from vault.kernel import construir

    return RepositorioGobernanza(construir(raiz)).leer_bitacora_cambios().entradas


def reescribir_bitacora(raiz: Path, filas: list) -> Path:
    """Fixture: replace the vault's change log with `filas`, in the line format.

    For tests that fabricate a history (a replay, a missing row). The frozen
    legacy array is removed so the fabricated rows are the whole history.
    """
    from vault.gobernanza.repositorio import RepositorioGobernanza
    from vault.kernel import construir

    repo = RepositorioGobernanza(construir(raiz))
    repo.bitacora_cambios.unlink(missing_ok=True)
    destino = repo.bitacora_cambios_lineas
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in filas).encode("utf-8"))
    return destino


# ── Skills: their entry point and the commands they teach ───────────────────
#
# Skills audit (2026-11-19, F18): the skill tests only checked that a flag NAME
# existed in the skill's own script, so `vault run vault_backup --verify` with
# no value passed (the flag takes a backup name) and a skill could not teach a
# command of another tool. One owner here for both test modules (AP-69).

#: Frontmatter value of `entry-point` for a skill that orchestrates several tools.
SIN_ENTRY_POINT = "none"


def script_de_skill(skill_md: Path) -> Optional[Path]:
    """The script a skill wraps: `entry-point:` if declared, else its name; None
    for an orchestration skill (`entry-point: none`)."""
    texto = Path(skill_md).read_text(encoding="utf-8")
    fm = {}
    if texto.startswith("---\n"):
        fm = yaml.safe_load(texto.split("---\n", 2)[1]) or {}
    declarado = str(fm.get("entry-point") or "").strip()
    if declarado == SIN_ENTRY_POINT:
        return None
    nombre = declarado or Path(skill_md).parent.name.replace("-", "_")
    return rutas.raiz_repo() / "scripts" / f"{nombre}.py"


def flags_de_argparse(script: Path) -> Dict[str, bool]:
    """Every long flag of a script's argparse -> whether it requires a value.

    Read from the AST of the code that owns the parser (`codigo_de` follows a
    facade to its owner): a flag with `action=store_true/store_false/count/
    store_const/help/version` or `nargs` `?`/`*` does not require one.
    """
    import ast

    import vault_grafo_import as gi

    arbol = ast.parse(gi.codigo_de(Path(script)).read_text(encoding="utf-8"))
    flags: Dict[str, bool] = {}
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.Call) and getattr(nodo.func, "attr", "") == "add_argument"):
            continue
        largos = [a.value for a in nodo.args
                  if isinstance(a, ast.Constant) and str(a.value).startswith("--")]
        if not largos:
            continue
        kw = {k.arg: k.value for k in nodo.keywords}
        accion = kw.get("action")
        nargs = kw.get("nargs")
        sin_valor = (isinstance(accion, ast.Constant) and accion.value in (
            "store_true", "store_false", "count", "store_const", "help", "version")) or (
            isinstance(nargs, ast.Constant) and nargs.value in ("?", "*"))
        for largo in largos:
            flags[largo] = not sin_valor
    return flags


def comandos_vault_run(texto: str) -> list:
    """`(tool, [tokens])` for every `vault run <tool> ...` in the ```bash blocks.

    Line continuations are joined, comments dropped and `$(...)` substitutions
    replaced by one placeholder token, so the tokens are what argparse would see.
    """
    import re
    import shlex

    comandos = []
    for bloque in re.findall(r"```bash\n(.*?)```", texto, re.DOTALL):
        logico = re.sub(r"\\\n\s*", " ", bloque)
        logico = re.sub(r"\$\((?:[^()]|\([^()]*\))*\)", "SUSTITUCION", logico)
        for linea in logico.splitlines():
            if "vault run " not in linea:
                continue
            try:
                tokens = shlex.split(linea, comments=True, posix=True)
            except ValueError:
                continue
            for i in range(len(tokens) - 2):
                if tokens[i] == "vault" and tokens[i + 1] == "run":
                    comandos.append((tokens[i + 2], tokens[i + 3:]))
                    break
    return comandos
