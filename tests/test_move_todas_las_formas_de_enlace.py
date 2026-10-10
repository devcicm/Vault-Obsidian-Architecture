"""AP-14 — mover una nota reescribe todo enlace que Obsidian resuelve a ella.

`update_wiki_links_in_file` sustituía tres cadenas literales (`[[viejo]]`,
`[[carpeta/viejo]]` y `[[carpeta/viejo|`). Medido como consumidor el
2026-10-10: de nueve formas corrientes de enlazar una nota, siete quedaban
rotas tras `vault_move` —alias, ancla, ancla con alias, mayúsculas, `.md`,
enlace markdown y el `\\|` de una tabla— y el sobre respondía
`links_pending: []`. El criterio de qué enlace apunta a qué nota es el de
Obsidian, y tiene dueño (`vault_lib.resolver_wikilink`, AP-44/AP-57).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
BS = chr(92)

#: (forma escrita, forma esperada tras mover `movible` → `movida`)
FORMAS = [
    ("[[movible]]", "[[movida]]"),
    ("[[movible|alias]]", "[[movida|alias]]"),
    ("[[movible#Sección]]", "[[movida#Sección]]"),
    ("[[movible#Sección|alias]]", "[[movida#Sección|alias]]"),
    ("[[Movible]]", "[[movida]]"),
    ("[[movible.md]]", "[[movida.md]]"),
    ("![[movible]]", "![[movida]]"),
    ("[[07_Knowledge/movible]]", "[[07_Knowledge/movida]]"),
    ("[[07_Knowledge/movible|alias]]", "[[07_Knowledge/movida|alias]]"),
    ("[texto](movible.md)", "[texto](movida.md)"),
    ("[texto](movible.md#Sección)", "[texto](movida.md#Sección)"),
    ("| [[movible" + BS + "|alias]] |", "| [[movida" + BS + "|alias]] |"),
]

#: Enlaces que no apuntan a la nota movida y no se tocan.
AJENOS = ["[[movible-extra]]", "[[otra]]", "[texto](otra.md)", "[web](https://x.org/movible.md)"]


def _run(raiz: Path, *args: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPTS / "vault_move.py"), *args, "--json"],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    texto = p.stdout.strip()
    return json.loads(texto[texto.index("{"):])


def _nota(ruta: Path, cuerpo: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(f"---\ntitle: {ruta.stem}\nstatus: draft\ntype: knowledge\n---\n"
                    f"# {ruta.stem}\n\n{cuerpo}\n", encoding="utf-8")


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    k = raiz / "07_Knowledge"
    _nota(k / "movible.md", "## Sección\n\ntexto")
    _nota(k / "movible-extra.md", "x")
    _nota(k / "otra.md", "x")
    _nota(k / "apunta.md", "\n".join(f for f, _ in FORMAS) + "\n" + "\n".join(AJENOS))
    return raiz


def test_move_reescribe_cada_forma_de_enlace(vault):
    # AP-14: tras mover, ningún enlace entrante queda roto.
    env = _run(vault, "--from", "07_Knowledge/movible.md", "--to", "07_Knowledge/movida.md")
    assert env["ok"] is True, env
    lineas = (vault / "07_Knowledge" / "apunta.md").read_text(encoding="utf-8").splitlines()
    for escrita, esperada in FORMAS:
        assert esperada in lineas, f"{escrita!r} no se reescribió a {esperada!r}"
    for ajeno in AJENOS:
        assert ajeno in lineas, f"{ajeno!r} se tocó y no apuntaba a la nota movida"
    assert env["links_updated"] == 1


def test_move_no_reescribe_un_enlace_ambiguo(vault):
    # Con dos `movible.md` el `[[movible]]` desnudo no fija identidad: elegir
    # una sería inventarla. Se deja y se declara pendiente.
    _nota(vault / "08_Runbooks" / "movible.md", "homónima")
    env = _run(vault, "--from", "07_Knowledge/movible.md", "--to", "07_Knowledge/movida.md")
    assert env["ok"] is True, env
    texto = (vault / "07_Knowledge" / "apunta.md").read_text(encoding="utf-8")
    assert "[[movible]]" in texto.splitlines()
    assert "[[07_Knowledge/movida]]" in texto.splitlines()
    assert "07_Knowledge/apunta.md" in env["links_ambiguous"], env


def test_move_dry_run_cuenta_sin_escribir(vault):
    antes = (vault / "07_Knowledge" / "apunta.md").read_bytes()
    env = _run(vault, "--from", "07_Knowledge/movible.md", "--to", "07_Knowledge/movida.md",
               "--dry-run")
    assert env["ok"] is True and env["links_updated"] == 1, env
    assert (vault / "07_Knowledge" / "apunta.md").read_bytes() == antes


def test_impact_anuncia_los_mismos_backlinks_que_el_movimiento_reescribe(vault):
    # AP-57: `--impact` contaba con su propio criterio literal y no veía alias,
    # anclas ni enlaces markdown; anunciaba menos impacto del que había.
    _nota(vault / "08_Runbooks" / "solo-alias.md", "ver [[movible|alias]]")
    env = _run(vault, "--from", "07_Knowledge/movible.md", "--to", "07_Knowledge/movida.md",
               "--impact")
    assert env["ok"] is True, env
    assert env["backlinks_count"] == 2, env
