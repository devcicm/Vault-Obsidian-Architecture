"""La casa de los vaults: `~/.vault-master/`, multiplataforma (v41.15).

El caso que la hizo necesaria: un vault real que era una carpeta suelta
dentro del repositorio del proyecto. Las notas del proyecto absorbidas
quedaban **borradas** del repo del proyecto y sin versionar en ninguna parte
—la memoria sin historia— y las tools solo la encontraban con `VAULT_ROOT`
puesto a mano, porque las reglas de autodetección estaban ancladas en el
directorio del programa (site-packages, con la wheel instalada).

Lo que se mide aquí:

- la casa es la misma carpeta en Windows y en Linux (`Path.home()`), y se
  puede mover con `VAULT_MASTER`;
- un vault en el directorio del cliente se encuentra sin `VAULT_ROOT`;
- el puntero `.vault-path` del repositorio original se lee y se respeta;
- `VAULT_MASTER` está en el registro del entorno (lo publica
  `vault_entorno`).
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))


def test_la_casa_es_la_misma_carpeta_en_los_dos_sistemas(monkeypatch, tmp_path):
    """Windows y Linux comparten nombre: `Path.home()` es la forma de decirlo."""
    from vault.kernel.vault_home import MASTER_DIR_NAME, master_home

    monkeypatch.delenv("VAULT_MASTER", raising=False)
    casa = master_home()
    assert casa.name == MASTER_DIR_NAME
    assert casa.parent == Path.home()

    monkeypatch.setenv("VAULT_MASTER", str(tmp_path / "casa"))
    assert master_home() == tmp_path / "casa"


def test_el_nombre_de_un_vault_no_es_una_ruta(monkeypatch, tmp_path):
    from vault.kernel.vault_home import vault_en_master

    monkeypatch.setenv("VAULT_MASTER", str(tmp_path / "casa"))
    assert vault_en_master("agente") == tmp_path / "casa" / "agente"
    for malo in ("../escape", "con/barra", "con\\barra", "", "  "):
        try:
            vault_en_master(malo)
        except ValueError:
            continue
        raise AssertionError(f"{malo!r} deberia rechazarse como nombre de vault")


def test_el_vault_del_cliente_se_encuentra_sin_vault_root(tmp_path, monkeypatch):
    """La regla que hace usables las tools instaladas: el vault donde estas."""
    import vault_raiz

    vault = tmp_path / "casa" / "agente"
    (vault / "00_System").mkdir(parents=True)
    (vault / "99_Index").mkdir(parents=True)
    dentro = vault / "07_Knowledge"
    dentro.mkdir()

    monkeypatch.setenv("VAULT_CLIENT_CWD", str(dentro))
    monkeypatch.delenv("VAULT_ROOT", raising=False)

    origen = vault_raiz._detect_vault_root()
    assert origen == vault, origen


def test_el_puntero_del_repositorio_declara_el_vault(tmp_path, monkeypatch):
    """`.vault-path` en el repositorio original: lo declara la persona."""
    from vault_raiz import PUNTER_VAULT, leer_puntero

    repo = tmp_path / "proyecto"
    repo.mkdir()
    vault = tmp_path / "casa" / "agente"
    vault.mkdir(parents=True)

    assert leer_puntero(repo) is None
    (repo / PUNTER_VAULT).write_text(str(vault) + "\n", encoding="utf-8")
    assert leer_puntero(repo) == vault

    # Una ruta RELATIVA se resuelve contra el repositorio, no contra el
    # directorio de trabajo: asi el puntero puede viajar en git.
    (repo / PUNTER_VAULT).write_text("../casa/agente\n", encoding="utf-8")
    assert leer_puntero(repo) == tmp_path / "casa" / "agente"


def test_la_variable_de_la_casa_esta_en_el_registro_del_entorno():
    import vault.kernel.entorno as entorno

    assert "VAULT_MASTER" in entorno.VARIABLES
    assert entorno.VARIABLES["VAULT_MASTER"].contexto == "kernel"


def test_los_pasos_del_init_de_la_casa_reciben_la_raiz(tmp_path, monkeypatch):
    """Los pasos del init son subprocesos: la raíz les llega por entorno.

    `vault_init --name` fija la raíz EN PROCESO (`set_vault_root`) y sus pasos
    (`vault_standard_upgrade`, `vault_master_index`, `vault_reindex`,
    `vault_audit`) corren como subprocesos. Sin `VAULT_ROOT` en el entorno el
    hijo autodetecta desde donde está y escribe en OTRO vault: medido el
    2026-11-04 lanzando el init desde el repo, el vault nuevo nacía sin
    `standard-version.json`, sin grafo y sin hash-index —sus pasos habían ido
    al sandbox— y el audit del init reportaba las notas del sandbox con
    `healthScore` 0 en vez de las del vault recién creado.
    """
    from apoyo import correr_tool, entorno

    monkeypatch.setenv("VAULT_MASTER", str(tmp_path / "casa"))
    # Como la persona: sin VAULT_ROOT. El hijo no puede heredar lo que no hay.
    env = entorno(None, quitar=("VAULT_ROOT", "VAULT_STRICT_ROOT"))

    proc = correr_tool("vault_init", "--name", "prueba", env=env)
    assert proc.returncode == 0, (proc.stdout or "")[-600:] + (proc.stderr or "")[-600:]

    vault = tmp_path / "casa" / "prueba"
    for rel in ("00_System/standard-version.json", "99_Index/graph.json",
                "99_Index/hash-index.json", "00_System/vault-hub.md"):
        assert (vault / rel).is_file(), f"el paso que escribe {rel} se fue a otro vault"

    lineas = [l for l in (proc.stdout or "").strip().splitlines() if l.strip()]
    sobre = json.loads(lineas[-1])
    assert sobre["ok"] is True, sobre
    # El audit del paso 5 midió ESTE vault, no el que el hijo autodetectara.
    assert sobre["healthScore"] > 0, "el audit del init miró otro vault"


def test_la_herramienta_de_entorno_publica_la_casa(capsys):
    """Lo que se publica no se escribe a mano: sale del registro (AP-47)."""
    from vault.kernel.entorno import main

    codigo = main(["--json"])
    salida = capsys.readouterr().out
    assert codigo == 0
    variables = json.loads(salida)
    casa = next(v for v in variables if v["variable"] == "VAULT_MASTER")
    assert casa["contexto"] == "kernel"
    assert casa["proposito"], "una variable sin propósito no se puede conocer"
