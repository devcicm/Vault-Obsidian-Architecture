"""A-11 — una raiz EXPLICITA que es el propio repo del estandar se rechaza.

`escritura_admitida` admite toda raiz explicita, y es diseno: ``--root`` o
``VAULT_ROOT`` a un vault real no paga porque la autodeteccion no encontrara
nada. Hasta v41.25 eso incluia apuntar al repo del estandar, que la regla 1 de
AGENTS.md prohibe: `vault_audit` corria con ``VAULT_ROOT=<repo>`` y la traza
sembraba `00_System/` en la raiz. El criterio «esto es el repo del estandar» es
de `vault.kernel.raiz.es_repo_del_estandar`; `vault_errors.wrap_main` no ejecuta
nada con esa raiz y `escritura_admitida` rechaza la escritura si llega por
``--root``.

La entrada `raiz_explicita_apunta_al_repo` de `vault_blueprint.DEUDA_DECLARADA`
queda `saldada` y se sostiene en este test.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from vault.kernel import raiz as vault_raiz  # noqa: E402


def _audit(env_extra):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", **env_extra)
    env.pop("VAULT_PERMISSIVE_ROOT", None)
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "vault_audit.py")],
                       env=env, capture_output=True, text=True, encoding="utf-8",
                       cwd=str(ROOT), timeout=120)
    salida = p.stdout.strip()
    assert salida, p.stderr[-500:]
    return json.loads(salida[salida.index("{"):])


def _huella(directorio):
    """Nombre y mtime de lo que haya en `directorio`; vacío si no existe."""
    if not directorio.is_dir():
        return {}
    return {p.name: p.stat().st_mtime_ns for p in directorio.iterdir()}


def test_raiz_explicita_en_el_repo_se_rechaza_antes_de_ejecutar():
    # Lo que la corrida dejaba: `.tool-trace.json` y `.voice-counter` en el
    # `00_System/` de la raíz, medido el 2026-10-30 (9 entradas de vault_audit).
    sistema = ROOT / "00_System"
    antes = _huella(sistema)
    r = _audit({"VAULT_ROOT": str(ROOT)})
    assert r.get("error_code") == "VAULT_NOT_FOUND", r
    assert _huella(sistema) == antes, "el rechazo escribio en la raiz del repo"


def test_el_repo_del_estandar_se_reconoce_por_su_firma_doble(tmp_path):
    assert vault_raiz.es_repo_del_estandar(ROOT)
    assert not vault_raiz.es_repo_del_estandar(ROOT / "vault-sandbox")

    clon = tmp_path / "clon"
    (clon / "vault" / "kernel").mkdir(parents=True)
    (clon / "vault-obsidian-architecture.md").write_text("# m\n", encoding="utf-8")
    assert vault_raiz.es_repo_del_estandar(clon)


@pytest.mark.parametrize("contenido", ["01_Projects", ".obsidian"])
def test_un_vault_que_guarda_el_manifiesto_sigue_siendo_vault(tmp_path, contenido):
    """La no-derogacion pide a los consumidores conservar el manifiesto."""
    vault = tmp_path / "consumidor"
    (vault / contenido).mkdir(parents=True)
    (vault / "vault" / "kernel").mkdir(parents=True)
    (vault / "vault-obsidian-architecture.md").write_text("# m\n", encoding="utf-8")
    assert not vault_raiz.es_repo_del_estandar(vault)

    solo_manifiesto = tmp_path / "referencia"
    solo_manifiesto.mkdir()
    (solo_manifiesto / "vault-obsidian-architecture.md").write_text("# m\n", encoding="utf-8")
    assert not vault_raiz.es_repo_del_estandar(solo_manifiesto)


def test_root_explicito_al_repo_no_es_confiado(monkeypatch):
    """Por ``--root`` (el override) tampoco se escribe en el repo.

    Se fija `_ACTIVE_VAULT_ROOT` sin `set_vault_root`: reanclar hacia la raíz
    del repo y volver arrastraría al sandbox constantes que cuelgan del repo
    (`vault_io.LEGACY_TOOL_SPEC`) y ensuciaría a los tests siguientes.
    """
    assert vault_raiz.vault_root_is_confident()
    monkeypatch.setattr(vault_raiz, "_ACTIVE_VAULT_ROOT", ROOT)
    monkeypatch.delenv("VAULT_PERMISSIVE_ROOT", raising=False)
    assert not vault_raiz.vault_root_is_confident()
    assert not vault_raiz.escritura_admitida(ROOT / "00_System" / "x.json")
