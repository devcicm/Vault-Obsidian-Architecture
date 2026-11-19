"""Who signs the vault's commits is configurable, and never someone else's name.

Owner request (2026-11-19): "El tema de nombre que mo ponga el mio en este repo
y que no lo ponga en proyectos de terceros y sea configurable la autoridad".
Until then every per-operation commit was forced to `vault <vault@local>`, so
in the owner's own vault his configured `user.name` was ignored. The order now:
1) `VAULT_COMMIT_NAME` + `VAULT_COMMIT_EMAIL` (both, from the env registry);
2) the identity git already has for that repo; 3) the neutral `vault`.
The commit message also names the agent (it said "por  —", empty).
"""

from pathlib import Path

import pytest

from apoyo import correr_tool, entorno, git_en

CONTENIDO = ("La cola de eventos usa NATS JetStream desde marzo.\n"
             "Cada consumidor durable confirma lo que procesa.\n"
             "Reemplazo a Redis Streams por la retencion por tiempo.\n")


@pytest.fixture()
def vault(tmp_path):
    raiz = tmp_path / "vault"
    raiz.mkdir()
    sin_global = tmp_path / "gitconfig-vacio"
    sin_global.write_bytes(b"")
    aislado = {"GIT_CONFIG_GLOBAL": str(sin_global), "GIT_CONFIG_NOSYSTEM": "1"}
    r = correr_tool("vault_init", "--no-audit", env=entorno(raiz, **aislado))
    assert r.codigo == 0, r.stdout + r.stderr
    return raiz, aislado


def _escribir(raiz: Path, aislado: dict, **extra) -> str:
    r = correr_tool("vault_write", "--folder", "07_Knowledge", "--title", "Cola de eventos",
                    "--tags", "eventos", "--content", CONTENIDO,
                    env=entorno(raiz, VAULT_AGENT="agente-x", **aislado, **extra))
    assert r.envelope.get("ok") is True, r.stdout + r.stderr
    return git_en(raiz, "log", "-1", "--format=%an <%ae>|%s").strip()


def test_sin_identidad_firma_el_vault_neutral(vault):
    raiz, aislado = vault
    autor, mensaje = _escribir(raiz, aislado).split("|", 1)
    assert autor == "vault <vault@local>"
    assert "por agente-x" in mensaje, mensaje


def test_la_identidad_del_repo_firma_sus_commits(vault):
    """The owner's vault signs with his name; a third party's, with theirs."""
    raiz, aislado = vault
    git_en(raiz, "config", "user.name", "Ana Tercera", check=True)
    git_en(raiz, "config", "user.email", "ana@ejemplo.test", check=True)
    autor, _ = _escribir(raiz, aislado).split("|", 1)
    assert autor == "Ana Tercera <ana@ejemplo.test>"


def test_la_configuracion_explicita_manda(vault):
    raiz, aislado = vault
    git_en(raiz, "config", "user.name", "Ana Tercera", check=True)
    git_en(raiz, "config", "user.email", "ana@ejemplo.test", check=True)
    autor, _ = _escribir(raiz, aislado, VAULT_COMMIT_NAME="Bot de CI",
                         VAULT_COMMIT_EMAIL="ci@ejemplo.test").split("|", 1)
    assert autor == "Bot de CI <ci@ejemplo.test>"


def test_un_nombre_sin_correo_no_se_usa_a_medias(vault):
    raiz, aislado = vault
    autor, _ = _escribir(raiz, aislado, VAULT_COMMIT_NAME="Solo Nombre").split("|", 1)
    assert autor == "vault <vault@local>"


def test_sin_vault_agent_el_mensaje_nombra_al_agente_por_defecto(vault):
    """The dev vault showed "vault: vault_write por  —": VAULT_AGENT unset was
    read raw. The default has one owner, `entorno.agente_por_defecto` (AP-16)."""
    raiz, aislado = vault
    r = correr_tool("vault_write", "--folder", "07_Knowledge", "--title", "Cola de eventos",
                    "--tags", "eventos", "--content", CONTENIDO, "--meta", '{"agent": "otro"}',
                    env=entorno(raiz, quitar=("VAULT_AGENT",), **aislado))
    assert r.envelope.get("ok") is True, r.stdout + r.stderr
    mensaje = git_en(raiz, "log", "-1", "--format=%s").strip()
    assert "por  " not in mensaje and "por claude" in mensaje, mensaje
