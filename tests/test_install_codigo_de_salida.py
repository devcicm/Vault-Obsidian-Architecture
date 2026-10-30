"""A-01 (vault dev codex): el instalador y el desinstalador no devuelven 0 tras fallar.

Un `exit 0` con «Instalación completa» después de un paso fallido hace que un
script de despliegue siga adelante sobre una instalación a medias.
"""

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
