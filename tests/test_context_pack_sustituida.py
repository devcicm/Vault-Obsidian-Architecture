"""Una nota sustituida sigue siendo recuperable, pero no gana a su canónica.

Medido el 2026-10-07 con `tests/banco_agente.py` sobre una copia de /ans
(regla 7): los únicos títulos que `vault_context_pack` no ponía primeros eran
pares con el mismo `title:` (AP-17), 0.8466 frente a 0.8444. La sanación que
pide el estándar es nombrar la canónica y anotar la otra con `superseded_by:`
—nada se borra—, pero el rerank no miraba ese campo: anotada o no, la gemela
competía igual. Y `STATUS_PENALTY` era un vocabulario copiado a mano: penalizaba
`superseded` y `revoked`, que no están en `STATUS_VOCAB`, y no `obsolete`, que sí.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import vault_context_pack as pack  # noqa: E402
from vault_norms_catalog import STATUS_VOCAB  # noqa: E402
pytestmark = pytest.mark.slow  # carril rápido (-m "not slow"): el perfil de la suite del 2026-10-20 midió aquí llamadas > 25 s


CUERPO = "\n".join(f"El libro blanco de arquitectura describe la capa {i} del sistema."
                   for i in range(4))


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


def _nota(raiz: Path, rel: str, extra: str = "") -> None:
    destino = raiz / rel
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(("---\ntitle: \"Libro blanco de arquitectura\"\n" + extra + "---\n\n"
        "# Libro blanco de arquitectura\n\n" + CUERPO + "\n").encode("utf-8"))


def _primera(raiz: Path) -> str:
    env = _ejecutar(raiz, "vault_context_pack.py", "--query", "Libro blanco de arquitectura")
    assert env["ok"] is True, env
    return [i["path"] for i in env["included"]][0]


@pytest.mark.parametrize("sustituida", ["05_Patterns/libro-blanco.md",
                                        "10_Migrated/LIBRO_BLANCO.md"])
def test_la_nota_con_superseded_by_no_gana_a_su_canonica(tmp_path, sustituida):
    """Las dos posiciones: la anotación decide, no el orden de llegada."""
    raiz = tmp_path / "vault"
    raiz.mkdir()
    assert _ejecutar(raiz, "vault_init.py")["ok"] is True
    rutas = ["05_Patterns/libro-blanco.md", "10_Migrated/LIBRO_BLANCO.md"]
    canonica = next(r for r in rutas if r != sustituida)
    _nota(raiz, canonica)
    _nota(raiz, sustituida, f"superseded_by: \"[[{Path(canonica).stem}]]\"\n")
    assert _ejecutar(raiz, "vault_reindex.py")["ok"] is True
    assert _primera(raiz) == canonica


def test_toda_penalizacion_canonica_es_un_status_del_vocabulario():
    """El dueño es STATUS_VOCAB; una clave fuera de él no la escribe nadie."""
    assert set(pack.PENALIZACION_POR_STATUS) <= set(STATUS_VOCAB)


@pytest.mark.parametrize("frontmatter, esperado", [
    ({"status": "obsolete"}, True),
    ({"status": "Deprecated"}, True),
    ({"status": "superseded"}, True),   # valor crudo heredado: se conserva
    ({"status": "revoked"}, True),      # idem
    ({"superseded_by": "[[otra]]"}, True),
    ({"superseded_by": ""}, False),
    ({"status": "implemented"}, False),
    ({}, False),
])
def test_la_penalizacion_sale_del_status_normalizado(frontmatter, esperado):
    assert (pack.penalizacion(frontmatter) < 1.0) is esperado
