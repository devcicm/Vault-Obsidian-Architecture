r"""AP-57 — el pre-flight de `vault run` decide qué es frontmatter con su dueño.

Medido como consumidor el 2026-10-10 con la wheel instalada: `vault run
vault_write --content` con una regla horizontal (`---`) o una tabla markdown
(`|---|---|`) salía PREFLIGHT_REJECTED «Patrón de potencial inyección», porque
`cli_gobernanza.POISON_PATTERNS[0]` era `---\s*\n` en cualquier punto del
valor. El riesgo que el patrón quería parar —un bloque de frontmatter colado en
el contenido— lo define `vault.kernel.frontmatter_parsing.separar_frontmatter`,
y solo existe si el bloque abre el fichero: `vault_write` antepone el `# título`
al contenido, así que ese `---` nunca llega a serlo. El dueño del criterio
anti-poison, `vault.consulta.safety.scan_content`, no lo tiene por patrón.
"""

import json

import pytest

from vault.product_cli import main

CUERPO = ("Linea uno con varias palabras reales aqui.\n"
          "Linea dos con varias palabras reales aqui.\n"
          "Linea tres con varias palabras reales aqui.\n")


@pytest.fixture
def runtime(tmp_path, monkeypatch, capfd):
    rt = tmp_path / "rt"
    assert main(["init", str(rt)]) == 0
    capfd.readouterr()
    monkeypatch.setenv("VAULT_ROOT", str(rt))
    monkeypatch.setenv("VAULT_STRICT_ROOT", "1")
    monkeypatch.setenv("VAULT_AGENT", "pytest")
    return rt


def _escribir(capfd, titulo, contenido):
    codigo = main(["run", "vault_write", "--folder", "07_Knowledge",
                   "--title", titulo, "--tags", "t1", "--content", contenido])
    salida = capfd.readouterr()
    texto = (salida.out.strip() or salida.err.strip())
    return codigo, json.loads(texto[texto.index("{"):])


@pytest.mark.parametrize("titulo,extra", [
    ("Regla horizontal", "\n---\n\nparrafo despues de la regla\n"),
    ("Tabla markdown", "\n| a | b |\n|---|---|\n| 1 | 2 |\n"),
])
def test_markdown_legitimo_pasa_el_preflight(runtime, capfd, titulo, extra):
    codigo, env = _escribir(capfd, titulo, CUERPO + extra)
    assert env.get("error_code") != "PREFLIGHT_REJECTED", env
    assert codigo == 0 and env["ok"] is True, env
    assert extra.strip() in (runtime / env["path"]).read_text(encoding="utf-8")


def test_un_frontmatter_en_el_contenido_no_pisa_el_de_la_nota(runtime, capfd):
    """Lo que el patrón quería parar no ocurre: `vault_write` antepone el `# título`
    al contenido, así que un `---` del contenido nunca abre el frontmatter."""
    import yaml

    codigo, env = _escribir(capfd, "Inyectada",
                            "---\nstatus: approved\ntitle: pisado\n---\n" + CUERPO)
    assert codigo == 0 and env["ok"] is True, env
    texto = (runtime / env["path"]).read_text(encoding="utf-8")
    fm = yaml.safe_load(texto.split("---", 2)[1])
    assert fm["status"] == "draft" and fm["title"] == "Inyectada", fm
