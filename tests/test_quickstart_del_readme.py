"""El Quick Start del README funciona copiado tal cual, en el orden en que está.

Medido el 2026-10-04 en la QA de producto: el paso «Inicializar un vault
nuevo» no inicializaba nada (`--help` y `tools list`), `VAULT_AGENT` —sin el
que toda escritura se rechaza si no viene `agent` en `--meta`— no aparecía en
ninguna documentación, y `vault_project_overview` respondía
`PROJECT_NOT_FOUND` porque el README no registraba el proyecto antes.

El test lee los comandos del README —criterio del consumidor, no una copia
del test— y los ejecuta en un vault temporal.
"""

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"

# Necesitan un árbol de código fuente que el vault temporal no tiene.
NECESITAN_FUENTES = {"vault_code_module.py", "vault_code_sync.py"}


def _quick_start():
    texto = README.read_text(encoding="utf-8")
    inicio = texto.index("## Quick Start")
    return texto[inicio:texto.index("\n## ", inicio + 1)]


def _comandos(seccion):
    """Líneas de los bloques bash, con las continuaciones `\\` unidas."""
    comandos = []
    for bloque in re.findall(r"```bash\n(.*?)```", seccion, re.S):
        for cmd in re.sub(r"\\\n\s*", " ", bloque).splitlines():
            cmd = cmd.split("  #")[0].strip()
            if cmd and not cmd.startswith("#"):
                comandos.append(cmd)
    return comandos


def test_el_quick_start_nombra_lo_que_una_escritura_necesita():
    seccion = _quick_start()
    assert "VAULT_AGENT" in seccion
    assert "vault init " in seccion
    comandos = _comandos(seccion)
    alta = next(i for i, c in enumerate(comandos) if "vault_project.py --add" in c)
    vista = next(i for i, c in enumerate(comandos) if "vault_project_overview.py" in c)
    assert alta < vista
    titulos = re.findall(r"^### (\d+)\.", seccion, re.M)
    assert len(titulos) == len(set(titulos)), titulos


def test_los_comandos_del_quick_start_funcionan_en_orden(tmp_path):
    vault = tmp_path / "vault-mi-proyecto"
    # `vault init` importa el paquete `vault` desde tmp_path: sin la raíz del
    # repo en PYTHONPATH lo resolvía una wheel instalada, si la había, y medía
    # esa versión en vez de este código; sin ninguna, caía con stdout vacío.
    env = dict(os.environ, PYTHONIOENCODING="utf-8", VAULT_ROOT=str(vault),
               VAULT_STRICT_ROOT="1", VAULT_AGENT="claude",
               PYTHONPATH=os.pathsep.join(
                   [str(ROOT), *filter(None, [os.environ.get("PYTHONPATH")])]))
    ejecutados = []
    for cmd in _comandos(_quick_start()):
        args = shlex.split(cmd)
        # Un `VAR=valor python script…` es bash legal en la misma línea: es
        # la forma en que el README lanza la escritura con VAULT_AGENT. Se
        # limpia del dispatch y se ejecuta con el env que ya trae la
        # corrida — así el comando de la persona y el del test son el mismo.
        while args and re.fullmatch(r"[A-Z_]{2,}=[^=]*", args[0]):
            args.pop(0)
        if args[:2] == ["vault", "init"]:
            argv = [sys.executable, "-c",
                    "import sys; from vault.product_cli import main; "
                    "sys.exit(main(sys.argv[1:]))", "init", str(vault)]
        elif args[0] == "python" and args[1].startswith("scripts/"):
            if Path(args[1]).name in NECESITAN_FUENTES:
                continue
            argv = [sys.executable, str(ROOT / args[1]), *args[2:]]
        else:
            continue
        p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env, cwd=tmp_path, timeout=600)
        sobre = json.loads(p.stdout)
        assert sobre.get("ok") is True, (cmd, p.stdout[-600:])
        ejecutados.append(Path(args[1]).name if args[0] == "python" else "vault init")
    assert ejecutados[0] == "vault init"
    assert {"vault_write.py", "vault_project.py", "vault_project_overview.py",
            "vault_audit.py"} <= set(ejecutados)
