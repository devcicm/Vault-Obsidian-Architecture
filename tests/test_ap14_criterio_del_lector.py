"""AP-14 (enlace fantasma) se decide como lo decide Obsidian, no por nombre plegado.

Medido en la auditoría del 2026-10-15: `vault_norms_scan` resolvía cada
wikilink comparando `normalize_stem` del enlace con el de los ficheros —sin
`aliases:`, sin sufijo de ruta, sin quitar `#sección`—. Dos errores a la vez:

- **Falso negativo.** `normalize_stem` quita guiones y espacios, así que
  `[[Elegir PostgreSQL]]` «resolvía» contra `elegir-postgresql.md`. Obsidian
  no lo abre: crea una nota vacía nueva.
- **Falso positivo.** `[[Nombre Legible]]` (alias), `[[07_Knowledge/destino]]`
  y `[[destino#sección]]` funcionan en Obsidian y salían como fantasmas.

Es AP-44 en el detector de la propia norma: `normas/AP-14` ya lo distingue
(«nombre de fichero, sufijo de ruta y aliases»), y `vault_audit` retiró ese
atajo el 2026-10-14. El criterio tiene dueño, `vault_lib.resolver_wikilink`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

DESTINO = """---
title: Elegir PostgreSQL
aliases: [Nombre Legible]
status: active
type: reference
---
# Elegir PostgreSQL

## Motivo

Texto.
"""


def _scan(tmp_path: Path, cuerpo: str) -> list:
    raiz = tmp_path / "vault"
    (raiz / "07_Knowledge").mkdir(parents=True)
    (raiz / "07_Knowledge" / "elegir-postgresql.md").write_text(DESTINO, encoding="utf-8")
    (raiz / "07_Knowledge" / "origen.md").write_text(
        f"---\ntitle: Origen\nstatus: active\ntype: reference\n---\n# Origen\n\n{cuerpo}\n",
        encoding="utf-8")
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_norms.py"), "--scan", "--path", "07_Knowledge/origen.md"],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1", PYTHONIOENCODING="utf-8"),
        cwd=str(SCRIPTS), capture_output=True, text=True, encoding="utf-8", timeout=300)
    env = json.loads(p.stdout[p.stdout.index("{"):])
    assert env["ok"] is True, env
    return [n for n in env["applicable_norms"] if n["code"] == "AP-14"]


def test_el_titulo_plegado_no_resuelve(tmp_path):
    ap14 = _scan(tmp_path, "Ver [[Elegir PostgreSQL]].")
    assert ap14 and "Elegir PostgreSQL" in ap14[0]["reason"], ap14


def test_alias_ruta_y_seccion_resuelven(tmp_path):
    ap14 = _scan(tmp_path, "Ver [[Nombre Legible]], [[07_Knowledge/elegir-postgresql]], "
                           "[[elegir-postgresql#Motivo]] y [[elegir-postgresql|la decisión]].")
    assert ap14 == [], ap14


def test_un_destino_inexistente_sigue_siendo_fantasma(tmp_path):
    ap14 = _scan(tmp_path, "Ver [[no-existe]].")
    assert ap14 and "no-existe" in ap14[0]["reason"], ap14
