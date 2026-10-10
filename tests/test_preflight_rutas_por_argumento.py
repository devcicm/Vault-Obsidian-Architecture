r"""AP-36 — el pre-flight de `vault run` mira las rutas por argumento, no el repr entero.

Medido como consumidor el 2026-10-10 con la wheel instalada, dos defectos de
la misma causa: `cli_gobernanza` aplicaba sus regex a `str(args)`, que empieza
por `{`.

- La de ruta absoluta estaba anclada con `^` y no saltaba nunca: `--folder
  C:/x` y `--content @file:<ruta absoluta>` pasaban el pre-flight que declaraba
  pararlos.
- La de traversal buscaba `../` en cualquier valor, y un contenido con un
  enlace markdown relativo (`[guia](../08_Runbooks/x.md)`) salía
  PREFLIGHT_REJECTED: el pre-flight confundía el texto de la nota con una ruta.

El criterio de qué argumento es una ruta y cuándo es insegura tiene un dueño
(`vault.kernel.indices_structural.motivo_de_ruta_insegura`), el mismo que usa
`cli/safety.check_path_arg` (AP-57).
"""

import json

import pytest

from vault.product_cli import main

CUERPO = ("Linea uno con varias palabras reales aqui.\n"
          "Linea dos con varias palabras reales aqui.\n"
          "Linea tres con varias palabras reales aqui.\n")


@pytest.fixture
def runtime(tmp_path, monkeypatch, capfd):
    rt = tmp_path / "rt"
    assert main(["init", str(rt)]) == 0
    capfd.readouterr()
    monkeypatch.setenv("VAULT_ROOT", str(rt))
    monkeypatch.setenv("VAULT_STRICT_ROOT", "1")
    monkeypatch.setenv("VAULT_AGENT", "pytest")
    return rt


def _escribir(capfd, folder, contenido, titulo="Nota de prueba"):
    codigo = main(["run", "vault_write", "--folder", folder,
                   "--title", titulo, "--tags", "t1", "--content", contenido])
    salida = capfd.readouterr()
    texto = (salida.out.strip() or salida.err.strip())
    return codigo, json.loads(texto[texto.index("{"):])


def _clases(env):
    return {f.get("kind") for f in env.get("findings", [])}


def test_enlace_markdown_relativo_no_es_traversal(runtime, capfd):
    contenido = CUERPO + "\nVer [guia](../08_Runbooks/x.md) para el detalle.\n"
    codigo, env = _escribir(capfd, "07_Knowledge", contenido, "Con enlace relativo")
    assert env.get("error_code") != "PREFLIGHT_REJECTED", env
    assert codigo == 0 and env["ok"] is True, env


@pytest.mark.parametrize("folder", ["C:/fuera", "C:BSBSfuera", "/etc"])
def test_folder_absoluto_se_rechaza(runtime, capfd, folder):
    folder = folder.replace("BS", chr(92))
    codigo, env = _escribir(capfd, folder, CUERPO)
    assert env.get("error_code") == "PREFLIGHT_REJECTED", env
    assert "absolute_path" in _clases(env), env


def test_content_desde_fichero_absoluto_se_rechaza(runtime, capfd, tmp_path):
    fuera = tmp_path / "secreto.md"
    fuera.write_text(CUERPO, encoding="utf-8")
    codigo, env = _escribir(capfd, "07_Knowledge", f"@file:{fuera}")
    assert env.get("error_code") == "PREFLIGHT_REJECTED", env
    assert "absolute_path" in _clases(env), env


def test_content_desde_fichero_con_traversal_se_rechaza(runtime, capfd):
    codigo, env = _escribir(capfd, "07_Knowledge", "@file:../fuera.md")
    assert env.get("error_code") == "PREFLIGHT_REJECTED", env
    assert "parent_traversal" in _clases(env), env


def test_folder_con_traversal_se_rechaza(runtime, capfd):
    codigo, env = _escribir(capfd, "07_Knowledge/../../fuera", CUERPO)
    assert env.get("error_code") == "PREFLIGHT_REJECTED", env
    assert "parent_traversal" in _clases(env), env
