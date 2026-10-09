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


@pytest.mark.parametrize("subruta", ["move-log.json", ".change-log.json",
                                     "propagation-queue.json", "tag-registry.json",
                                     ".tool-tokens.json", "scanner-degraded.jsonl"])
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


def test_la_bitacora_de_cambios_la_escribe_gobernanza(tmp_path):
    from vault.gobernanza.repositorio import RepositorioGobernanza
    from vault.kernel import construir

    repo = RepositorioGobernanza(construir(tmp_path))
    repo.escribir_bitacora_cambios([{"action": "create", "path": "a.md"}])
    texto = repo.bitacora_cambios.read_text(encoding="utf-8")
    assert json.loads(texto) == [{"action": "create", "path": "a.md"}]
    assert texto == json.dumps(json.loads(texto), indent=2, ensure_ascii=False)


def test_la_cola_de_propagacion_la_escribe_gobernanza(tmp_path):
    from vault.gobernanza.repositorio import RepositorioGobernanza
    from vault.kernel import construir

    repo = RepositorioGobernanza(construir(tmp_path))
    datos = {"updated_at": "2026-10-08T00:00:00Z", "pending": [{"path": "a.md"}]}
    repo.escribir_cola_propagacion(datos)
    texto = repo.cola_propagacion.read_text(encoding="utf-8")
    assert json.loads(texto) == datos
    assert texto == json.dumps(datos, indent=2, ensure_ascii=False)


def test_vault_audit_solo_lee_la_cola_de_propagacion():
    """El comentario de Ciclo de vida decía que `vault_audit` también la
    escribía; medido el 2026-10-08, solo la lee. Si un día la escribe, la
    guarda lo verá como escritor y este test lo dirá antes."""
    assert "vault_audit" not in {
        e["module"] for e in vault_arch.escrituras_de_sistema()
        if e["path"] == "propagation-queue.json"}


def test_el_registro_de_etiquetas_se_siembra_por_indices_sin_pisarlo(tmp_path):
    """`vault_init` siembra el registro solo si no existe; la semilla la
    escribe Índices, su dueño, y nunca pisa el que `vault_tags` ya generó."""
    from vault.ciclo_de_vida.repositorio import RepositorioCicloDeVida
    from vault.indices.repositorio import RepositorioIndices
    from vault.kernel import construir

    ctx = construir(tmp_path)
    ciclo = RepositorioCicloDeVida(ctx)
    assert ciclo.sembrar_registro_etiquetas({"version": "v1.0"}) is True
    ruta = RepositorioIndices(ctx).registro_etiquetas
    assert json.loads(ruta.read_text(encoding="utf-8")) == {"version": "v1.0"}
    assert ciclo.sembrar_registro_etiquetas({"version": "otra"}) is False
    assert json.loads(ruta.read_text(encoding="utf-8")) == {"version": "v1.0"}


def test_una_constante_del_modulo_no_esconde_la_subruta():
    """Mudar el literal a una constante no puede sacar la escritura de la vista."""
    arbol = ast.parse(
        "FICHERO = '.tool-tokens.json'\n"
        "def fichero():\n"
        "    return raiz() / '00_System' / FICHERO\n"
        "def f():\n"
        "    fichero().write_text('[]')\n"
    )
    assert [s for _l, _c, s in vault_arch.escrituras_de_sistema_en(arbol, {})] == [
        ".tool-tokens.json"]


def test_el_contador_de_tokens_es_del_kernel_y_consulta_lo_reexporta(tmp_path):
    import vault_errors_trace
    from vault.consulta import repositorio as consulta
    from vault.kernel import construir

    assert vault_arch.duenos_de_sistema()[".tool-tokens.json"] == vault_arch.KERNEL
    # No-derogación: el nombre que consulta publicaba sigue importable.
    assert consulta.FICHERO_TOKENS == vault_errors_trace.FICHERO_TOKENS
    repo = consulta.RepositorioConsulta(construir(tmp_path))
    assert repo.fichero_tokens.name == vault_errors_trace.FICHERO_TOKENS


def test_reiniciar_el_contador_lo_hace_el_kernel(tmp_path, monkeypatch):
    import vault_errors_trace
    import vault_tokens

    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    fichero = tmp_path / "00_System" / vault_errors_trace.FICHERO_TOKENS
    monkeypatch.setattr(vault_errors_trace, "tokens_file", lambda: fichero)
    fichero.parent.mkdir(parents=True)
    fichero.write_text("[]", encoding="utf-8")
    assert vault_errors_trace.reiniciar_tokens() is True
    assert not fichero.exists()
    assert vault_errors_trace.reiniciar_tokens() is False
    assert "reiniciar_tokens" in vault_tokens.vault_tokens.__code__.co_names
