"""Una sección inferida por una palabra es una apuesta, no un filtro.

Medido el 2026-10-07 con `tests/banco_agente.py` sobre copias de /vcloud y /ans
(regla 7): preguntando a `vault_context_pack` por el título exacto de una nota,
no la recuperaba en el 16 % y el 12 % de los casos, mientras que `vault_search`
la encontraba en todos. «Diagrama de Componentes Runtime» se parseaba con
`sections: ["13_Flows"]` por la pista léxica «diagrama»; la nota vivía en
`06_Diagrams`, y el paquete buscaba solo en `13_Flows` y descartaba en el
rerank todo lo de fuera. El propio código decía «una apuesta, no un filtro
duro», pero solo volvía atrás si la sección no devolvía nada.

La sección que se nombra literalmente («en 13_Flows») sí sigue mandando.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))

from vault.consulta.query_parse import vault_query_parse  # noqa: E402


def _ejecutar(raiz: Path, script: str, *argv: str) -> dict:
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *argv],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS),
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


def _escribir(raiz: Path, carpeta: str, titulo: str, cuerpo: str) -> str:
    env = _ejecutar(raiz, "vault_write.py", "--folder", carpeta, "--title", titulo,
                    "--content", cuerpo, "--tags", "t",
                    "--meta", json.dumps({"agent": "pytest"}))
    assert env["ok"] is True, env
    return env["path"]


@pytest.fixture(scope="module")
def raiz(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("pack") / "vault"
    raiz.mkdir()
    assert _ejecutar(raiz, "vault_init.py")["ok"] is True
    _escribir(raiz, "06_Diagrams", "Diagrama de componentes runtime", "\n".join([
        "Los componentes runtime del servicio y cómo se conectan entre sí.",
        "El gateway recibe la petición y la pasa al orquestador de componentes.",
        "El orquestador arranca los workers runtime bajo demanda.",
    ]))
    _escribir(raiz, "13_Flows", "Flujo de pedidos", "\n".join([
        "Este diagrama describe el flujo de pedidos de punta a punta.",
        "El diagrama tiene tres fases: alta, cobro y envío.",
        "Cada fase del diagrama deja una traza en el log de pedidos.",
    ]))
    assert _ejecutar(raiz, "vault_graph.py")["ok"] is True
    return raiz


def _incluidas(raiz: Path, pregunta: str) -> list:
    env = _ejecutar(raiz, "vault_context_pack.py", "--query", pregunta)
    assert env["ok"] is True, env
    return [i["path"] for i in env["included"]]


def test_la_pista_lexica_no_esconde_la_nota_de_otra_seccion(raiz):
    """El parser sigue apostando por 13_Flows; el paquete ya no se limita a ella."""
    assert "13_Flows" in vault_query_parse("Diagrama de componentes runtime")["structured"]["sections"]
    incluidas = _incluidas(raiz, "Diagrama de componentes runtime")
    assert incluidas[:1] == ["06_Diagrams/diagrama-de-componentes-runtime.md"], incluidas


def test_la_seccion_nombrada_literalmente_sigue_mandando(raiz):
    incluidas = _incluidas(raiz, "en 13_Flows diagrama de componentes runtime")
    assert "13_Flows/flujo-de-pedidos.md" in incluidas, incluidas
    # Lo de otra sección solo entra si el grafo lo conecta al tema (diseño
    # previo, se conserva); la nota de 06_Diagrams no está enlazada.
    assert "06_Diagrams/diagrama-de-componentes-runtime.md" not in incluidas, incluidas


def test_el_parser_distingue_la_seccion_nombrada_de_la_inferida():
    inferida = vault_query_parse("Diagrama de componentes runtime")["structured"]
    nombrada = vault_query_parse("en 13_Flows diagrama de componentes")["structured"]
    assert inferida["sections_named"] == []
    assert nombrada["sections_named"] == ["13_Flows"]
