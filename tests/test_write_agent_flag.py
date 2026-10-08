"""AP-16 — `vault_write` acepta `--agent`, como dice la pista de `missing_agent`.

Medido el 2026-10-07 con `tests/banco_agente.py`: por MCP, sin `VAULT_AGENT`
en el entorno del servidor, la única forma de firmar una nota era meter el
agente dentro de `meta` como JSON. La pista del catálogo para `missing_agent`
dice «Pasar --agent <nombre>», y dieciséis tools de escritura lo declaran;
`vault_write`, la que el protocolo nombra para toda escritura, no. Un agente
que seguía la pista recibía INVALID_ARGS.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
CUERPO = "\n".join(f"Línea {i} de una nota firmada por su agente." for i in range(4))


def _tool(raiz: Path, script: str, *argv: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "VAULT_AGENT"}
    env.update(VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1", PYTHONIOENCODING="utf-8")
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / f"{script}.py"), *argv],
        env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", cwd=str(raiz.parent), timeout=300)
    salida = p.stdout.strip()
    assert salida, p.stderr[-1000:]
    return json.loads(salida[salida.index("{"):])


def _frontmatter(ruta: Path) -> dict:
    return yaml.safe_load(ruta.read_text(encoding="utf-8").split("---")[1])


def test_ap16_seguir_la_pista_de_missing_agent_firma_la_nota(tmp_path):
    raiz = tmp_path / "vault"
    raiz.mkdir()
    assert _tool(raiz, "vault_init")["ok"] is True
    base = ("--folder", "07_Knowledge", "--title", "Nota firmada", "--content", CUERPO, "--tags", "t")

    r = _tool(raiz, "vault_write", *base)
    assert r["ok"] is False and r["error_code"] == "missing_agent", r
    assert "--agent" in r["recovery"]["hint"], r["recovery"]

    r = _tool(raiz, "vault_write", *base, "--agent", "agente-de-prueba")
    assert r["ok"] is True, r
    assert _frontmatter(raiz / r["path"])["agent"] == "agente-de-prueba"


def test_ap16_el_flag_gana_al_agent_de_meta(tmp_path):
    """Dos firmas distintas en la misma llamada: manda la explícita."""
    raiz = tmp_path / "vault"
    raiz.mkdir()
    assert _tool(raiz, "vault_init")["ok"] is True
    r = _tool(raiz, "vault_write", "--folder", "07_Knowledge", "--title", "Dos firmas",
              "--content", CUERPO, "--tags", "t", "--meta", json.dumps({"agent": "de-meta"}),
              "--agent", "del-flag")
    assert r["ok"] is True, r
    assert _frontmatter(raiz / r["path"])["agent"] == "del-flag"
