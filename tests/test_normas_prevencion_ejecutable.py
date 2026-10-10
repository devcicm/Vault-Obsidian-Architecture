"""La prevención de una norma solo receta flags que alguna tool acepta.

Medido el 2026-10-07: AP-27 decía «Declarar --type en la escritura» en el
catálogo y «declarar `--type` al escribir; `vault_validate` lo comprueba» en
el manifiesto. `vault_write` no tiene `--type` —el tipo sale de la sección o
de `--meta`—, y la frase no nombraba ninguna tool, así que el guard de AP-42
(recetas con un flag que no existe) no tenía contra qué contrastarla. AP-26
nombraba a `vault_ingest` y `vault_preferences` y callaba a `vault_write`, que
es la que rechaza la nota sin tags.

El criterio es el del consumidor (AP-44): el flag tiene que estar declarado en
el parser de una tool que la propia prevención nombra o que el catálogo da por
enforcer, no en cualquier parte del repo.
"""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from vault_norms_catalog import NORM_CATALOG  # noqa: E402

MANIFIESTO = ROOT / "vault-obsidian-architecture.md"
NORMAS = ["AP-26", "AP-27"]

import vault_grafo_import as gi  # noqa: E402


def _entrada(codigo: str) -> dict:
    return next(n for n in NORM_CATALOG if n["code"] == codigo)


def _prevencion_del_manifiesto(codigo: str) -> str:
    texto = MANIFIESTO.read_text(encoding="utf-8")
    inicio = re.search(rf"^### {re.escape(codigo)} — .*$", texto, re.M)
    assert inicio, f"{codigo} sin sección en el manifiesto"
    resto = texto[inicio.end():]
    fin = re.search(r"^### ", resto, re.M)
    cuerpo = resto[: fin.start() if fin else len(resto)]
    parrafo = re.search(r"\*\*Prevención:\*\*(.*?)(?:\n\n|\Z)", cuerpo, re.S)
    assert parrafo, f"{codigo} sin párrafo de prevención en el manifiesto"
    return parrafo.group(1)


def _acepta(tool: str, flag: str) -> bool:
    fuente = SCRIPTS / f"{tool}.py"
    return fuente.is_file() and f'"{flag}"' in gi.codigo_de(fuente).read_text(encoding="utf-8")


@pytest.mark.parametrize("codigo", NORMAS)
def test_cada_flag_recetado_existe_en_una_tool_que_la_receta_nombra(codigo):
    n = _entrada(codigo)
    for origen, texto in (("catálogo", n["prevention"]),
                          ("manifiesto", _prevencion_del_manifiesto(codigo))):
        tools = set(re.findall(r"\bvault_[a-z_]+", texto)) | set(n["tools_enforcing"])
        for flag in set(re.findall(r"(?<![\w-])--[a-z][a-z-]*", texto)):
            assert any(_acepta(t, flag) for t in tools), (
                f"{codigo} ({origen}) receta {flag}, que no acepta ninguna de {sorted(tools)}")


@pytest.mark.parametrize("codigo", NORMAS)
def test_vault_write_figura_entre_quienes_la_cumplen(codigo):
    """`vault_write` rechaza la nota de contenido sin tags (AP-26) y deriva el
    `type` de la sección o rechaza la nota que no lo trae (AP-27)."""
    assert "vault_write" in _entrada(codigo)["tools_enforcing"]
