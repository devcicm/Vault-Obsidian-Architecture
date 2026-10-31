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
