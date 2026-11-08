"""A-01 (vault dev codex): el instalador y el desinstalador no devuelven 0 tras fallar.

Un `exit 0` con «Instalación completa» después de un paso fallido hace que un
script de despliegue siga adelante sobre una instalación a medias.

Y el segundo defecto de la misma familia (nota de causa raíz «Installer and
uninstaller report success after a required step fails», 2026-10-30): el
instalador **borraba el destino sin comprobar de quién era**, y solo en Unix.
Aquí se mide con el criterio del consumidor: se ejecuta el instalador contra
un directorio temporal y se mira lo que queda.
"""

import json
import os
from pathlib import Path

from vault import install, uninstall


def test_install_devuelve_distinto_de_cero_si_falla_el_mcp(monkeypatch, capsys):
    monkeypatch.setattr(install, "_install_cli", lambda: 0)
    monkeypatch.setattr(install, "_install_mcp", lambda: 7)
    monkeypatch.setattr(install, "_install_skills", lambda: 0)
    assert install.main(["--all"]) == 7
    assert "Instalación completa" not in capsys.readouterr().out


def test_install_devuelve_distinto_de_cero_si_fallan_las_skills(monkeypatch):
    monkeypatch.setattr(install, "_install_cli", lambda: 0)
    monkeypatch.setattr(install, "_install_skills", lambda: 3)
    assert install.main(["--all", "--dry-run"]) == 0
    monkeypatch.setattr(install, "_install_mcp", lambda: 0)
    assert install.main(["--all"]) == 3


def test_install_todo_bien_devuelve_cero(monkeypatch):
    monkeypatch.setattr(install, "_install_cli", lambda: 0)
    monkeypatch.setattr(install, "_install_mcp", lambda: 0)
    monkeypatch.setattr(install, "_install_skills", lambda: 0)
    assert install.main(["--all"]) == 0


def test_uninstall_devuelve_distinto_de_cero_si_falla_pip(monkeypatch, capsys):
    monkeypatch.setattr(uninstall, "_pip_uninstall", lambda: 1)
    assert uninstall.main([]) == 1
    assert "Desinstalación completa" not in capsys.readouterr().out


# ── La CLI que no importa no es una instalación ────────────────────────────


def test_una_cli_que_no_importa_no_se_declara_instalada(monkeypatch, capsys):
    """`_install_cli` devolvía 0 tras un ImportError: la instalación «completa»
    de una CLI que no arranca."""
    import builtins

    real_import = builtins.__import__

    def _importar(nombre, *args, **kwargs):
        if nombre.startswith("vault.product_cli"):
            raise ImportError("simulado: la CLI no se puede importar")
        return real_import(nombre, *args, **kwargs)

    monkeypatch.setattr(install, "_pip_install", lambda extra="": 0)
    monkeypatch.setattr(builtins, "__import__", _importar)
    assert install._install_cli() == 1
    assert "[ERROR]" in capsys.readouterr().out


# ── El destino tiene dueño ──────────────────────────────────────────────────


def test_un_destino_ajeno_no_se_toca(tmp_path, monkeypatch):
    """El destino de otro no se borra: se rechaza y se dice por qué."""
    destino = tmp_path / "bin" / "vault-mcp"
    destino.parent.mkdir(parents=True)
    destino.write_text("soy de otro\n", encoding="utf-8")

    monkeypatch.setattr(install, "_destino_mcp", lambda: destino)
    assert install._install_mcp() == 1
    assert destino.is_file(), "el instalador borró un fichero ajeno"
    assert destino.read_text(encoding="utf-8") == "soy de otro\n"


def test_el_lanzador_instalado_queda_con_manifiesto_de_propiedad(tmp_path, monkeypatch):
    """Instalar deja constancia de quién puso el lanzador: sin ella, el
    desinstalador no puede borrar (y antes borraba lo que fuera)."""
    destino = tmp_path / "bin" / "vault-mcp"
    destino.parent.mkdir(parents=True)
    monkeypatch.setattr(install, "_destino_mcp", lambda: destino)

    assert install._install_mcp() == 0
    assert destino.exists() or destino.is_symlink()
    manifiesto = install._manifiesto_de(destino)
    assert manifiesto.is_file(), "no se wrote el manifiesto de propiedad"
    datos = json.loads(manifiesto.read_text(encoding="utf-8"))
    assert datos["destino"] == str(destino)


def test_el_desinstalador_no_borra_lo_que_no_es_suyo(tmp_path, monkeypatch, capsys):
    destino = tmp_path / "bin" / "vault-mcp"
    destino.parent.mkdir(parents=True)
    destino.write_text("soy de otro\n", encoding="utf-8")
    monkeypatch.setattr(uninstall, "_destino_mcp", lambda: destino)

    assert uninstall._uninstall_mcp() == 0
    assert destino.is_file(), "el desinstalador borró un fichero ajeno"
    assert "NO se borra" in capsys.readouterr().out


def test_el_desinstalador_borra_lo_que_es_suyo(tmp_path, monkeypatch):
    destino = tmp_path / "bin" / "vault-mcp"
    destino.parent.mkdir(parents=True)
    monkeypatch.setattr(install, "_destino_mcp", lambda: destino)
    assert install._install_mcp() == 0
    manifiesto = install._manifiesto_de(destino)
    assert manifiesto.is_file()

    monkeypatch.setattr(uninstall, "_destino_mcp", lambda: destino)
    assert uninstall._uninstall_mcp() == 0
    assert not destino.exists() and not destino.is_symlink()
    assert not manifiesto.exists()


# ── La plataforma decide el destino ─────────────────────────────────────────


def test_el_destino_depende_de_la_plataforma():
    """`/usr/local/bin` es Unix: en Windows el destino es el directorio de los
    scripts —donde `pip` deja la CLI— y el lanzador es un `.cmd` (un symlink
    pediría privilegios de desarrollador)."""
    import sysconfig

    destino = install._destino_mcp()
    if os.name == "nt":
        assert destino.suffix == ".cmd", destino
        assert str(destino.parent) == str(Path(sysconfig.get_path("scripts"))), destino
        assert not str(destino).startswith("/usr/local"), destino
    else:
        assert str(destino) == "/usr/local/bin/vault-mcp", destino

