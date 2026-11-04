"""`vault.ejecutor` — correr una tool del toolkit en ESTE intérprete.

## Qué es

Un orquestador —`vault_fix_all`, `vault_noop_audit`, el banco de humo— lanza
hijas que son tools del propio toolkit. Cada hija era un intérprete nuevo:
el coste de arranque se pagaba una vez por llamada, y el banco de AP-37 la
pagaba 123 veces. Este módulo hace esa llamada **en proceso**, con el mismo
contrato observable: los mismos argumentos, la misma salida, el mismo código
de salida y el mismo envelope.

La forma es la que el plan dejó escrita —`ejecutar(ctx: VaultContext, argv)`—
y el contexto entra como argumento porque la raíz es lo que la tool tiene que
usar: sin él, la tool resolvería la raíz por autodetección y apuntaría al
sandbox del repo en vez de al vault del que se le pidió.

## Qué NO cambia

- **El contrato CLI.** Cada tool conserva su subproceso en la prueba de
  contrato: lo que se prueba aquí es el *comportamiento* en proceso, y el
  contrato por línea de comandos se sigue comprobando como se comprobaba.
- **El envelope.** La tool imprime su JSON; el ejecutor lo recoge del stdout
  y lo devuelve. Con `envoltorio=wrap_main` el envelope sale byte a byte el
  mismo que por subproceso, porque quien lo compone es el mismo.
- **La voz y el ledger.** `wrap_main` es quien compone la voz (A-04) y quien
  pone el contador de escrituras a cero en el hilo donde corre la tool (el
  ledger es thread-local). Por eso el ejecutor corre la llamada **en su propio
  hilo**: el contador de la tool es el de ese hilo, y el del ejecutor no se
  mezcla con él.

## Lo que el ejecutor restaura

`sys.argv`, el directorio de trabajo, la raíz activa del vault y las variables
de entorno que superpone. Una tool que deja el intérprete distinto de como lo
encontró envenena a la siguiente: por eso el ejecutor devuelve el intérprete
al estado en que lo encontró, y su test lo comprueba.

## Lo que no puede

- **Matar lo que vigila.** Un subproceso colgado se mata; un hilo no. Por eso
  el ejecutor usa el presupuesto de la propia tool (`VAULT_TOOL_TIMEOUT`), que
  es el que `wrap_main` aplica, y su propio `timeout` es un añadido seguro:
  expirado, la llamada sigue viva en segundo plano y su resultado se declara
  perdido.
- **Correr dos tools a la vez.** `sys.stdout` es del proceso, no del hilo:
  dos capturas simultáneas se pisarían. El ejecutor tiene un candado global y
  serializa las ejecuciones.
"""

from __future__ import annotations

import importlib
import io
import json
import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from .kernel.contexto import VaultContext
from .kernel.ledger import write_ledger_reset
from .kernel.raiz import (
    get_vault_root,
    reset_vault_root,
    set_vault_root,
    vault_root_origin,
)

#: `sys.stdout` es del proceso: dos tools en proceso a la vez capturarían el
#: mismo flujo. El candado serializa; no es una decisión de rendimiento.
_CANDADO = threading.Lock()

#: Las variables que el ejecutor superpone y restaura. Ninguna más: una tool
#: que lea cualquier otra variable la lee del entorno que hereda, que es el
#: del proceso que la lanzó.
_VARIABLES = ("VAULT_AGENT", "VAULT_MASTER", "VAULT_VOICE")

#: Las que la raíz necesita también en el ENTORNO, no solo como override en
#: proceso. Una tool que lanza un hijo —los pasos de `vault_init` son
#: `vault_standard_upgrade`, `vault_master_index` y `vault_reindex`, los tres
#: subprocesos— hereda el entorno del padre, y sin `VAULT_ROOT` el hijo
#: autodetecta la raíz y escribe en otro vault. Medido el 2026-11-04 al
#: migrar `test_indice_no_se_regenera_dos_veces.py` a ejecución en proceso: el
#: vault salía sin índice maestro, sin grafo, sin hash-index y sin la versión
#: del estándar, porque sus pasos se escribieron en el vault del sandbox.
_VARIABLES_DE_RAIZ = ("VAULT_ROOT", "VAULT_STRICT_ROOT")

#: El nombre por el que se importa una tool en cada layout. En el checkout es
#: el nombre de `scripts/`; instalada, la proyección `_impl` del puente
#: (ADR-0002).
_LAYOUTS = ("{nombre}", "vault_toolkit._impl.{nombre}")


@dataclass(frozen=True)
class Ejecucion:
    """Lo que salió de una tool ejecutada en proceso."""

    #: El código de salida, el mismo que devolvería el subproceso.
    codigo: int
    #: El envelope que la tool imprimió, ya en JSON. `None` si no imprimió uno.
    envelope: Optional[Dict[str, Any]]
    #: Todo lo que la tool escribió en stdout.
    texto: str
    #: Todo lo que escribió en stderr.
    error: str
    #: El motivo por el que no se pudo ejecutar, si lo hubo.
    motivo: Optional[str] = None

    @property
    def ok(self) -> bool:
        """Si la tool dijo que salió bien. Sin envelope, no."""
        return bool(self.envelope) and bool(self.envelope.get("ok"))


def _modulo_de(nombre: str) -> Any:
    """Importa la tool por su nombre, en el layout que toque.

    El import es dinámico a propósito: el ejecutor no depende de ninguna tool
    concreta, y un import estático de las 126 sería un acoplamiento que el
    registro no declara.
    """
    errores: List[str] = []
    for patron in _LAYOUTS:
        candidato = patron.format(nombre=nombre)
        try:
            return importlib.import_module(candidato)
        except ImportError as exc:
            errores.append(f"{candidato}: {exc}")
    raise ModuleNotFoundError(
        f"no se pudo importar la tool {nombre!r}: " + "; ".join(errores))


def _json_de(texto: str) -> Optional[Dict[str, Any]]:
    """El envelope que la tool imprimió, si imprimió uno.

    Las tools imprimen el JSON compacto en una línea y otras con indentación;
    algunas emiten una línea de texto antes. Se busca el primer `{` y se
    intenta leer desde ahí, que es lo que hace el humo (`vault_smoke`).
    """
    limpio = (texto or "").strip()
    if not limpio:
        return None
    try:
        datos = json.loads(limpio)
    except ValueError:
        i = limpio.find("{")
        if i == -1:
            return None
        try:
            datos = json.loads(limpio[i:])
        except ValueError:
            return None
    return datos if isinstance(datos, dict) else None


def _directorio_de(modulo: Any) -> Optional[Path]:
    """El directorio del módulo: el cwd que tendría su script."""
    fichero = getattr(modulo, "__file__", None)
    return Path(fichero).resolve().parent if fichero else None


def _invocable(modulo: Any) -> Callable[[], Any]:
    """La entrada de la tool: su `main()` o su bloque `__main__`.

    Las tools con alias (ADR-0002) no tienen `main()`: su CLI vive en el
    bloque `__main__` del dueño, y el facade la corre con
    `runpy.run_module("vault.gobernanza.secret_scan", run_name="__main__")`.
    `vault_secret_scan` es una de ellas: sin esta forma, el ejecutor la
    invocaría con un `AttributeError` y no imprimiría nada.

    Se ejecuta con la misma forma que usa el facade, para que la salida sea la
    misma que por línea de comandos.
    """
    main = getattr(modulo, "main", None)
    if callable(main):
        return main

    def _por_runpy() -> Any:
        import runpy

        return runpy.run_module(modulo.__name__, run_name="__main__", alter_sys=True)

    return _por_runpy


def ejecutar(
    contexto: Optional[VaultContext],
    argv: Sequence[str],
    *,
    modulo: Any = None,
    envoltorio: Optional[Callable[[Callable[[], Any], str], int]] = None,
    raiz: Optional[Path] = None,
    agente: Optional[str] = None,
    casa: Optional[Path] = None,
    voz: Optional[str] = None,
    cwd: Optional[Path] = None,
    timeout: Optional[float] = None,
) -> Ejecucion:
    """Corre una tool en este intérprete y devuelve lo que devolvió.

    - `contexto`: el contexto del vault en el que corre. Su raíz es la que la
      tool usa mientras dura la llamada, y la anterior se restaura al salir.
      `None` deja la raíz como esté.
    - `argv`: lo que la CLI recibiría, con el script en el primer sitio
      (`["vault_append.py", "--path", ...]`).
    - `raiz`: la raíz que la tool usa mientras corre, cuando no hay contexto.
      Es el mismo API que usa el contexto (`set_vault_root`), por lo que la
      raíz anterior se restaura igual.
    - `modulo`: el módulo a correr. Por defecto se importa por el nombre del
      script.
    - `envoltorio`: `wrap_main` de `vault_errors`, que es como lo envuelve la
      CLI. Con él, el envelope y el código de salida son los de la CLI.
    - `agente`, `casa`, `voz`: lo que se superpone al entorno de la llamada.
    - `cwd`: el directorio de trabajo. Por defecto, el del script.
    - `timeout`: segundos de espera. `None` espera a que la tool termine por
      su cuenta —su propio presupuesto, `VAULT_TOOL_TIMEOUT`—.

    El intérprete queda como estaba: `argv`, cwd, raíz y las variables
    superpuestas se restauran siempre, también cuando la tool falla.
    """
    if not argv:
        raise ValueError("`argv` vacío: no hay script que correr")
    script = str(argv[0])
    nombre = Path(script).stem

    if modulo is None:
        modulo = _modulo_de(nombre)

    anterior_argv = sys.argv
    anterior_cwd = os.getcwd()
    anterior_entorno = {v: os.environ.get(v) for v in _VARIABLES + _VARIABLES_DE_RAIZ}
    anterior_raiz = get_vault_root()
    habia_override = vault_root_origin() == "explicit_override"
    anterior_stdout, anterior_stderr = sys.stdout, sys.stderr
    salida, errores = io.StringIO(), io.StringIO()
    codigo = 0
    motivo: Optional[str] = None
    raiz_de_la_llamada: Optional[Path] = None

    with _CANDADO:
        try:
            os.chdir(str(cwd) if cwd else (_directorio_de(modulo) or anterior_cwd))
            sys.argv = [script, *[str(a) for a in argv[1:]]]
            if agente is not None:
                os.environ["VAULT_AGENT"] = agente
            if casa is not None:
                os.environ["VAULT_MASTER"] = str(casa)
            if voz is not None:
                os.environ["VAULT_VOICE"] = voz
            if contexto is not None:
                raiz_de_la_llamada = Path(contexto.raiz)
            elif raiz is not None:
                raiz_de_la_llamada = Path(raiz)
            if raiz_de_la_llamada is not None:
                set_vault_root(raiz_de_la_llamada)
                # Y en el entorno: los hijos que lance la tool (los pasos de
                # `vault_init` lo son) heredan la raíz, no la autodetección.
                os.environ["VAULT_ROOT"] = str(raiz_de_la_llamada)
                os.environ["VAULT_STRICT_ROOT"] = "1"

            sys.stdout = salida
            sys.stderr = errores
            codigo, motivo = _correr(modulo, nombre, envoltorio, timeout)
        except Exception as exc:  # noqa: BLE001 — el motivo se publica, no se tapa
            codigo = 1
            motivo = f"{type(exc).__name__}: {exc}"
        finally:
            sys.stdout = anterior_stdout
            sys.stderr = anterior_stderr
            sys.argv = anterior_argv
            try:
                os.chdir(anterior_cwd)
            except OSError:
                pass
            for variable, valor in anterior_entorno.items():
                if valor is None:
                    os.environ.pop(variable, None)
                else:
                    os.environ[variable] = valor
            # La raíz se restaura como estaba: si había override explícito se
            # vuelve a él; si no, se deshace el override y la autodetección
            # vuelve a mandar. Dejar un override donde no lo había cambia el
            # origen de la raíz (`vault_root_origin`), y ese origen se publica.
            if habia_override:
                set_vault_root(anterior_raiz)
            else:
                reset_vault_root()

    texto = salida.getvalue()
    return Ejecucion(
        codigo=codigo,
        envelope=_json_de(texto),
        texto=texto,
        error=errores.getvalue(),
        motivo=motivo,
    )


def _correr(modulo: Any, nombre: str,
            envoltorio: Optional[Callable[[Callable[[], Any], str], int]],
            timeout: Optional[float]) -> tuple:
    """Corre `main()` de la tool y devuelve `(código, motivo)`.

    En su propio hilo, por dos razones que son la misma: el ledger de
    escrituras es thread-local (así que el de la tool es el de ese hilo y no
    arrastra lo que el ejecutor haya contado antes), y `sys.stdout` —que la
    tool sustituye— es del proceso (así que se restaura al hilo que la dejó
    como estaba).
    """
    codigo = {"valor": 0, "motivo": None}

    def _objetivo() -> None:
        try:
            write_ledger_reset()
            if envoltorio is not None:
                codigo["valor"] = int(envoltorio(_invocable(modulo), nombre) or 0)
            else:
                resultado = _invocable(modulo)()
                codigo["valor"] = 0 if resultado is None else int(resultado or 0)
        except SystemExit as fin:
            codigo["valor"] = fin.code if isinstance(fin.code, int) else (
                1 if fin.code else 0)
        except BaseException as exc:  # noqa: BLE001 — se publica como motivo
            codigo["valor"] = 1
            codigo["motivo"] = f"{type(exc).__name__}: {exc}"

    hilo = threading.Thread(target=_objetivo, daemon=True)
    hilo.start()
    hilo.join(timeout=timeout)
    if hilo.is_alive():
        codigo["valor"] = 1
        codigo["motivo"] = f"la tool {nombre} excedió el timeout de {timeout}s"
    return codigo["valor"], codigo["motivo"]
