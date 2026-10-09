"""Cada subruta de `00_System/` la escribe solo su dueño (deuda #3, residuo).

`vault_arch.escrituras_de_sistema_ajenas` dejaba cinco escrituras congeladas
en `arch-baseline.json` (`system_writes`): un contexto escribía la subruta que
el repositorio de otro declaraba. El criterio que se aplicó, decidido el
2026-10-08, es «dueño = único escritor»: el dueño expone la escritura y el
otro contexto delega en él por un par que ya está en
`vault_arch.PRESUPUESTO_DE_CRUCES`. Mover la declaración al escritor habría
obligado a los repositorios que solo **leen** a cruzar hacia él, y eso estrena
cruces que la baseline no tiene.

La escritura por el puerto del kernel (`ctx.escritor.escribir`) cuenta como
escritura para la guarda: si no contara, mudarla al puerto la escondería en vez
de ordenarla.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import vault_arch  # noqa: E402


def _escritores(subruta: str) -> set:
    return {e["context"] for e in vault_arch.escrituras_de_sistema()
            if e["path"] == subruta}


def test_la_escritura_por_el_puerto_cuenta_y_apunta_a_su_primer_argumento():
    nodo = ast.parse("self._ctx.escritor.escribir(ruta, texto)").body[0].value
    assert vault_arch.llamada_de_escritura(nodo) == "escribir"
    arbol = ast.parse(
        "def f(self):\n"
        "    ruta = self.bitacora_movimientos\n"
        "    self._ctx.escritor.escribir(ruta, '[]')\n"
    )
    props = {"bitacora_movimientos": "move-log.json"}
    assert [s for _l, _c, s in vault_arch.escrituras_de_sistema_en(arbol, props)] == [
        "move-log.json"]


@pytest.mark.parametrize("subruta", ["move-log.json"])
def test_la_subruta_la_escribe_solo_su_dueno(subruta):
    dueno = vault_arch.duenos_de_sistema()[subruta]
    assert _escritores(subruta) == {dueno}


def test_la_bitacora_de_movimientos_se_anota_por_el_dueno(tmp_path):
    from vault.autoria.repositorio import RepositorioAutoria
    from vault.grafo.repositorio import RepositorioGrafo
    from vault.kernel import construir

    ctx = construir(tmp_path)
    autoria = RepositorioAutoria(ctx)
    assert autoria.bitacora_movimientos == RepositorioGrafo(ctx).bitacora_movimientos
    autoria.anotar_movimiento({"from": "a.md", "to": "b.md"})
    autoria.anotar_movimiento({"from": "b.md", "to": "c.md"})
    texto = RepositorioGrafo(ctx).bitacora_movimientos.read_text(encoding="utf-8")
    assert json.loads(texto) == [{"from": "a.md", "to": "b.md"},
                                 {"from": "b.md", "to": "c.md"}]
    # El formato es contrato con el disco del usuario: el de siempre.
    assert texto == json.dumps(json.loads(texto), indent=2, ensure_ascii=False)
