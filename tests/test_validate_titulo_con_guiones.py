"""AP-44 / AP-57 — `vault_validate` no corta el frontmatter por un `---` del título.

Medido en v40.34 contra una copia de /ans: `vault_write --title "x\\nstatus:
hackeado\\n---"` escribe `title: "x\\nstatus: hackeado\\n---"`, un escalar entre
comillas que `yaml.safe_load` y Obsidian leen bien —el bloque solo se cierra en
una línea que es `---`—. `vault_validate` partía con `content.split("---", 2)`,
cortaba dentro de las comillas y declaraba la nota rota con «YAML parse error»:
el estándar reprobando una nota que acababa de escribir él mismo.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

_CAMPOS = (
    "id: 1\ncreatedAt: 2026-01-01T00:00:00Z\nupdatedAt: 2026-01-01T00:00:00Z\n"
    "tags: [demo]\ncia_integrity: medium\ncia_availability: medium\n"
    "cia_sensitivity: internal\nagent: test\ntype: knowledge\nstatus: draft\n"
)


def _validar(tmp_path, nombre, texto):
    raiz = tmp_path / "vault"
    carpeta = raiz / "07_Knowledge"
    carpeta.mkdir(parents=True)
    (raiz / "00_System").mkdir()
    (carpeta / nombre).write_text(texto, encoding="utf-8")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_validate.py"), "--folder", "07_Knowledge"],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(cwd), timeout=120,
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


def test_titulo_con_guiones_escapados_es_valido(tmp_path):
    texto = '---\ntitle: "x\\nstatus: hackeado\\n---"\n' + _CAMPOS + "---\n\ncuerpo\n"

    r = _validar(tmp_path, "nota.md", texto)

    rotas = {i["path"]: i["error"] for i in r.get("invalid", [])}
    assert "07_Knowledge/nota.md" in r.get("valid", []), rotas


def test_bloque_sin_cerrar_sigue_saliendo_como_tal(tmp_path):
    texto = "---\ntitle: abierta\n" + _CAMPOS + "\ncuerpo sin cierre\n"

    r = _validar(tmp_path, "abierta.md", texto)

    rotas = {i["path"]: i["error"] for i in r.get("invalid", [])}
    assert rotas.get("07_Knowledge/abierta.md") == "Frontmatter not closed", rotas
