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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import yaml

from vault.kernel import rutas

ROOT = rutas.raiz_repo()
SCRIPTS = rutas.ruta_repo(rutas.SCRIPTS)

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
    env = dict(os.environ, PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest")
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
