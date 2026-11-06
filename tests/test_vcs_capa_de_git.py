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
    """El historial del vault lleva las notas, no el estado del sistema.

    La política es «solo `.md`» y el orden de los patrones importa: `.history/`
    está lleno de copias que **acaban en `.md`**, así que tiene que re-ignorarse
    después de `!*.md`.
    """
    ignore = (vault_con_repo / ".gitignore").read_text(encoding="utf-8")
    lineas = [linea.strip() for linea in ignore.splitlines()]
    assert "*" in lineas
    assert "!*.md" in lineas
    assert "!.gitignore" in lineas
    # La única excepción no-`.md`: la bitácora de autoría (dato, no derivado).
    assert "!00_System/.change-log.json" in lineas
    # Las carpetas que contienen `.md` que no son notas van detrás.
    assert lineas.index(".history/") > lineas.index("!*.md")
    assert lineas.index("vault-backups/") > lineas.index("!*.md")
    assert lineas.index("00_System/.trash/") > lineas.index("!*.md")


def test_el_repo_del_vault_solo_versiona_notas(vault_con_repo):
    """La regla del dueño, medida en el índice: notas, la política y la
    bitácora de autoría.

    Un vault es memoria documental: su repo versiona notas. El estado del
    sistema (`graph.json`, `hash-index.json`, `tool-spec.json`, trazas,
    contadores) se regenera y no es memoria; los `.gitkeep` son andamiaje.
    La única excepción es `00_System/.change-log.json`: F8 (no-repudio) lo
    exige por nota y `vault_impact` lo lee como dato — con la política de
    `solo .md` se perdería del repo y no hay de dónde regenerarla.
    """
    cuerpo = vault_con_repo / "cuerpo.md"
    cuerpo.write_text(CUERPO, encoding="utf-8")
    r = correr_tool("vault_write", "--folder", "07_Knowledge",
                    "--title", "Nota versionada", "--content", f"@file:{cuerpo}",
                    "--tags", "prueba", vault=vault_con_repo)
    assert r.codigo == 0, r.stdout + r.stderr

    versionados = [l for l in _git(vault_con_repo, "ls-files").splitlines()
                   if l.strip()]
    intrusos = [f for f in versionados
                if not f.endswith(".md") and f != ".gitignore"
                and f != "00_System/.change-log.json"]
    assert not intrusos, f"el repo versiona algo que no es una nota: {intrusos}"
    assert any(f.endswith("nota-versionada.md") for f in versionados), versionados
    assert "00_System/.change-log.json" in versionados, (
        "la bitácora de autoría es dato del vault y tiene que viajar con él")

    # Una copia de versión existe en disco y no se versiona: se fabrica una y
    # se comprueba tras el commit de la segunda escritura.
    historia = vault_con_repo / ".history"
    historia.mkdir(exist_ok=True)
    copia = historia / "07_knowledge__nota-versionada__2026-01-01T00-00-00.md"
    copia.write_text("# version vieja\n", encoding="utf-8")
    r = correr_tool("vault_write", "--folder", "07_Knowledge",
                    "--title", "Otra nota", "--content", f"@file:{cuerpo}",
                    "--tags", "prueba", vault=vault_con_repo)
    assert r.codigo == 0, r.stdout + r.stderr

    versionados = [l for l in _git(vault_con_repo, "ls-files").splitlines()
                   if l.strip()]
    assert copia.is_file(), "la copia de versión se perdió del disco"
    assert not any(f.startswith(".history/") for f in versionados)


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


def test_reparar_indice_saca_lo_ignorado_del_index_y_nada_del_disco(vault_con_repo):
    """El caso que disparó C-03: un vault anterior a la capa de git.

    El self-healing añade el `.gitignore`, pero eso no saca nada del índice:
    lo volátil sigue versionado hacia atrás. La reparación es una decisión
    explícita: `--reparar-indice` retira del índice lo que la política
    ignora (`git rm --cached`, el árbol de trabajo no se toca) y lo deja en
    un commit propio con su cifra.
    """
    from vault.kernel.vcs import reparar_indice

    historia = vault_con_repo / ".history"
    historia.mkdir()
    copia = historia / "07_knowledge__nota__2026-01-01T00-00-00.md"
    copia.write_text("# version vieja\n", encoding="utf-8")
    estado = vault_con_repo / "00_System" / "estado-volatil.json"
    estado.write_text("{}", encoding="utf-8")
    # Estado de esa generación de vaults: el repositorio ya rastrearía lo volátil.
    _git(vault_con_repo, "add", "-f", str(copia.relative_to(vault_con_repo)),
         str(estado.relative_to(vault_con_repo)))
    _git(vault_con_repo, "commit", "-m", "estado previo: lo volatil esta rastreado")
    antes = [l for l in _git(vault_con_repo, "ls-files").splitlines() if l.strip()]
    assert any(f.startswith(".history/") for f in antes), antes
    assert "00_System/estado-volatil.json" in antes, antes

    resultado = reparar_indice(vault_con_repo)
    assert resultado["reparado"] is True, resultado
    assert any(f.startswith(".history/") for f in resultado["destrackeados"])
    assert "00_System/estado-volatil.json" in resultado["destrackeados"]
    assert resultado["committed"] is True and resultado.get("sha"), resultado
    assert "2 ficheros destrackeados" in resultado["mensaje"], resultado

    # El árbol no se toca: los ficheros ignorados siguen en el disco.
    assert copia.is_file(), "la reparación borró la copia de versión"
    assert estado.is_file(), "la reparación borró el estado del sistema"

    # El índice ya cumple la política y el commit de la reparación es visible.
    despues = [l for l in _git(vault_con_repo, "ls-files").splitlines()
               if l.strip()]
    intrusos = [f for f in despues
                if not f.endswith(".md") and f != ".gitignore"]
    assert not intrusos, despues
    mensajes = _git(vault_con_repo, "log", "--format=%s")
    assert "reparacion del indice: 2 ficheros destrackeados" in mensajes


def test_reparar_indice_es_idempotente_y_declara_cero(vault_con_repo):
    """En un vault que cumple la política: `cero`, y ni un commit de más."""
    from vault.kernel.vcs import reparar_indice

    antes = len(_git(vault_con_repo, "log", "--format=%H").splitlines())
    r = reparar_indice(vault_con_repo)
    assert r.get("cero") is True, r
    assert r["destrackeados"] == [] and "committed" not in r, r
    despues = len(_git(vault_con_repo, "log", "--format=%H").splitlines())
    assert despues == antes, "la reparación idempotente escribió un commit"


def test_git_rm_sin_cached_sigue_prohibido(vault_con_repo):
    """La autorización del `rm` es solo la forma que no toca el árbol.

    La puerta de AP-68 ahora conoce el verbo, pero solo con `--cached`: un
    `git rm` a secas borra del disco y no es una reparación del índice, es
    borrar notas — decisión de la persona.
    """
    from vault.kernel.procesos_git import GitProhibido, ejecutar_git

    with pytest.raises(GitProhibido):
        ejecutar_git(vault_con_repo, ["rm", "x.md"])
    # La forma autorizada pasa la puerta (el fallo de git por un fichero
    # inexistente, si lo hubiera, es de git, no de la puerta).
    p = ejecutar_git(vault_con_repo, ["rm", "--cached", "-q", "--", "x.md"])
    assert p.returncode != 0  # git dice que no está en el índice; sin GitProhibido

