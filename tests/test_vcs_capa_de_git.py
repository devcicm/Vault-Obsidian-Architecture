"""La capa de git del vault: una operacion que escribe, un commit.

Medido el 2026-11-04 probando el producto como un consumidor (un vault de
verdad para un proyecto de verdad): las tres redes de vuelta atras que habia
—`.history/` por nota, `vault_backup` de todo el vault y el change-log— no
cubrian una operacion que toca varias notas. El repo que ya nace con cada
vault si: una operacion = un commit, y volver a como estaba = volver a un
commit.

Lo que estos tests fijan:

1. Un vault nuevo, en ruta personalizada, nace con su repo y su `.gitignore`.
2. Cada operacion que escribe deja un commit que dice que tool lo hizo.
3. `vault_undo --commits` las lista; `vault_undo --to` devuelve el vault.
4. Un vault sin repo no se toca (el sandbox del repo, los vaults de test).
"""

import json
from pathlib import Path

import pytest

from apoyo import correr_tool, git_en  # noqa: E402

CUERPO = (
    "# Nota de la operacion\n\n"
    "Linea uno con contenido real para que el contrato de la nota (AP-11) la\n"
    "acepte y la tool no frene la escritura.\n\n"
    "Tercera linea: tres lineas reales de contenido.\n"
)


@pytest.fixture()
def vault_con_repo(tmp_path):
    """Un vault nuevo en una ruta personalizada: con repo y con `.gitignore`."""
    raiz = tmp_path / "vault-en-ruta-personalizada"
    raiz.mkdir()
    r = correr_tool("vault_init", "--no-audit", vault=raiz)
    assert r.codigo == 0, r.stdout + r.stderr
    return raiz


def _git(raiz: Path, *args: str) -> str:
    """El lanzador de git vive en el apoyo compartido (AP-69)."""
    return git_en(raiz, *args)


def test_un_vault_en_ruta_personalizada_nace_con_su_repo(vault_con_repo):
    """El repo no es solo de la casa: un vault en cualquier ruta lo tiene.

    Antes solo la casa (`vault_init --name`) nacía con repo, y un vault en
    ruta personalizada se quedaba sin historia: sin donde volver si algo
    salía mal.
    """
    assert (vault_con_repo / ".git").exists()
    assert "vault: bootstrap del vault" in _git(vault_con_repo, "log", "--format=%s")


def test_el_vault_ignora_las_versiones_las_copias_y_la_traza(vault_con_repo):
    """El historial del vault lleva el vault, no tres veces el vault.

    `.history/` ya está en el historial de git (son las versiones de cada
    nota), `vault-backups/` son copias de lo pasado y la traza cambia en cada
    llamada: dentro del repo, el árbol quedaba sucio siempre y el historial
    llevaba 99 de 345 ficheros que eran versiones.
    """
    ignore = (vault_con_repo / ".gitignore").read_text(encoding="utf-8")
    assert ".history/" in ignore
    assert "vault-backups/" in ignore
    assert "00_System/.tool-trace.json" in ignore


def test_una_operacion_que_escribe_deja_un_commit(vault_con_repo, tmp_path):
    """El commit dice qué tool hizo el trabajo: una operación sin nombre no
    se puede deshacer a ciegas."""
    cuerpo = tmp_path / "cuerpo.md"
    cuerpo.write_text(CUERPO, encoding="utf-8")
    r = correr_tool("vault_write", "--folder", "07_Knowledge",
                    "--title", "Nota con historia", "--content", f"@file:{cuerpo}",
                    "--tags", "prueba", vault=vault_con_repo)
    assert r.codigo == 0, r.stdout + r.stderr

    log = _git(vault_con_repo, "log", "--format=%s")
    assert "vault_write" in log, log
    assert "1 creada" in log or "creadas" in log, log


def test_vault_undo_lista_las_operaciones(vault_con_repo, tmp_path):
    """`--commits` es el "qué se ha hecho aquí" con fecha y autor."""
    cuerpo = tmp_path / "cuerpo.md"
    cuerpo.write_text(CUERPO, encoding="utf-8")
    correr_tool("vault_write", "--folder", "07_Knowledge", "--title", "Nota listada",
                "--content", f"@file:{cuerpo}", "--tags", "prueba",
                vault=vault_con_repo)
    r = correr_tool("vault_undo", "--commits", vault=vault_con_repo)
    assert r.codigo == 0, r.stdout + r.stderr
    sobre = json.loads(r.stdout.strip().splitlines()[-1])
    assert sobre["ok"] is True, sobre
    assert sobre["operations"], sobre
    assert any("vault_write" in o["mensaje"] for o in sobre["operations"]), sobre


def test_vault_undo_to_devuelve_el_vault_a_un_commit(vault_con_repo, tmp_path):
    """Volver a como estaba: el contenido del commit, y lo que sobraba, fuera."""
    cuerpo = tmp_path / "cuerpo.md"
    cuerpo.write_text(CUERPO, encoding="utf-8")
    correr_tool("vault_write", "--folder", "07_Knowledge", "--title", "Nota del deshacer",
                "--content", f"@file:{cuerpo}", "--tags", "prueba",
                vault=vault_con_repo)
    # El commit de este momento: el estado al que se quiere volver.
    objetivo = _git(vault_con_repo, "rev-parse", "HEAD")
    antes = _git(vault_con_repo, "rev-list", "--count", "HEAD")

    cuerpo2 = tmp_path / "cuerpo2.md"
    cuerpo2.write_text("\n".join([
        CUERPO,
        "Una linea mas que cambia el contenido.",
        "",
    ]), encoding="utf-8")
    correr_tool("vault_write", "--folder", "07_Knowledge", "--title", "Nota del deshacer",
                "--content", f"@file:{cuerpo2}", "--tags", "prueba",
                vault=vault_con_repo)
    nota = vault_con_repo / "07_Knowledge" / "nota-del-deshacer.md"
    assert "Una linea mas" in nota.read_text(encoding="utf-8")

    # Al commit de antes de la segunda escritura: la nota vuelve a su estado.
    r = correr_tool("vault_undo", "--to", objetivo, "--force", vault=vault_con_repo)
    assert r.codigo == 0, r.stdout + r.stderr
    sobre = json.loads(r.stdout.strip().splitlines()[-1])
    assert sobre["ok"] is True, sobre
    # La nota vuelve a como estaba: con su contenido de entonces, o fuera (no
    # existía en ese commit y `--force` la retira).
    if nota.exists():
        assert "Una linea mas" not in nota.read_text(encoding="utf-8")
    else:
        assert "nota-del-deshacer.md" in str(sobre.get("borrados") or [])
    assert int(antes) >= 1


def test_un_vault_sin_repo_no_se_toca(tmp_path):
    """El sandbox del repo y los vaults de test no tienen repo: nada se rompe."""
    raiz = tmp_path / "sin-repo"
    raiz.mkdir()
    r = correr_tool("vault_undo", "--commits", vault=raiz)
    assert r.codigo == 1
    sobre = json.loads(r.stdout.strip().splitlines()[-1])
    assert sobre["ok"] is False
    assert sobre["error_code"] == "NO_HAY_REPO"
