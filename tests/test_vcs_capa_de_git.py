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


def test_el_ignore_cubre_lo_que_los_duenos_escriben(vault_con_repo):
    """La lista se cruza con el dueño de cada ruta, no se enumera a mano.

    Enumerar las rutas de ayer no falla cuando aparece una nueva: este test
    pregunta a los dueños. La credencial sale de la constante que nombra su
    carpeta, y el borrado de la carpeta que `vault_delete` usa.
    """
    from vault.consulta import repositorio
    from vault.kernel.vcs import IGNORADOS, IGNORADOS_POR_RIESGO

    ignore = (vault_con_repo / ".gitignore").read_text(encoding="utf-8")
    for ruta in IGNORADOS:
        assert ruta in ignore, ruta

    # La credencial: la carpeta la nombra su dueño, no este test.
    assert any(ruta.endswith(f"{repositorio.SUBCARPETA_USO_TOKENS}/")
               for ruta in IGNORADOS_POR_RIESGO), repositorio.SUBCARPETA_USO_TOKENS
    # El borrado: `.trash/` es lo que `vault_delete` deja atrás.
    assert any(".trash/" in ruta for ruta in IGNORADOS)


def test_un_vault_con_repo_previo_recibe_el_gitignore(tmp_path):
    """El caso que rompió: el repo existía y el `.gitignore` no llegaba.

    `vault_init` escribía el ignore dentro de la rama que CREA el repo, así que
    un vault que ya tenía `.git` nunca lo recibía. Medido el 2026-11-05 en un
    vault real: 110 ficheros volátiles rastreados (99 de `.history/`).
    """
    raiz = tmp_path / "vault-con-repo-previo"
    raiz.mkdir()
    git_en(raiz, "init", "-b", "main")

    r = correr_tool("vault_init", "--no-audit", vault=raiz)
    assert r.codigo == 0, r.stdout + r.stderr

    ignore = (raiz / ".gitignore").read_text(encoding="utf-8")
    assert "00_System/token-usage/" in ignore
    assert ".history/" in ignore


def test_una_operacion_repara_un_gitignore_que_falta(vault_con_repo):
    """El dueño del versionado repara, no solo el bootstrap.

    Un vault que ya tiene repo no vuelve a pasar por `vault_init`: la garantía
    tiene que vivir en `commit_de_operacion`, que sí corre en cada escritura.
    """
    (vault_con_repo / ".gitignore").unlink()
    cuerpo = vault_con_repo / "cuerpo.md"
    cuerpo.write_text(CUERPO, encoding="utf-8")
    r = correr_tool("vault_write", "--folder", "07_Knowledge",
                    "--title", "Nota que repara", "--content", f"@file:{cuerpo}",
                    "--tags", "prueba", vault=vault_con_repo)
    assert r.codigo == 0, r.stdout + r.stderr

    ignore = (vault_con_repo / ".gitignore").read_text(encoding="utf-8")
    assert "00_System/token-usage/" in ignore
    assert "00_System/.trash/" in ignore

    # Y queda en la traza: el envelope no lo publica, el registro sí (AP-51).
    traza = vault_con_repo / "00_System" / ".tool-trace.json"
    entradas = [e for e in json.loads(traza.read_text(encoding="utf-8"))
                if e.get("event") == "git_del_vault"]
    assert entradas, "la reparación no dejó rastro en la traza"
    assert "00_System/token-usage/" in entradas[-1]["ignore_reparado"]


def test_el_gitignore_no_pisa_lo_que_la_persona_escribio(vault_con_repo):
    """Aditivo: lo que ya estaba se conserva, línea a línea."""
    mío = "# mío\nmi-carpeta/\n*.local\n"
    (vault_con_repo / ".gitignore").write_text(mío, encoding="utf-8")

    from vault.kernel.vcs import asegurar_ignorados

    resultado = asegurar_ignorados(vault_con_repo)
    assert resultado["escrito"] is True
    texto = (vault_con_repo / ".gitignore").read_text(encoding="utf-8")
    assert texto.startswith(mío)
    assert ".history/" in texto
    # Y la segunda pasada no escribe.
    assert asegurar_ignorados(vault_con_repo)["escrito"] is False


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
