"""Las dos tools que solo existen en Node, ejercidas por el camino que las sirve.

`vault_backup_base64` y `vault_restore_base64` son las únicas dos del catálogo
sin fichero en `scripts/`: su implementación entera vive en el servidor MCP. Eso
las dejaba fuera de todo — `vault_smoke` recorre el catálogo pero ejecuta el
`.py`, y la CLI de Python las rechaza con un `TOOL-RUNTIME` explícito. Resultado:
la tool cuyo trabajo es que no se pierda nada no tenía una sola comprobación.

Lo que salió al escribir estos tests, y no antes:

- de los cuatro campos que declara su contrato, la implementación devolvía uno;
- las lecturas fallidas se tragaban con `catch (_) {}`, así que un backup
  incompleto salía con `ok: true`;
- el restore escribía **fuera del vault** (AP-36) y montaba `entry.path` del
  fichero de backup sin validar traversal, teniendo `assertWithinVault` en el
  mismo módulo.
"""

import importlib.util
import json
import shutil
import zlib
from base64 import b64decode, b64encode
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _mcp():
    spec = importlib.util.spec_from_file_location(
        "mr", Path(__file__).resolve().parent / "test_mcp_runner.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def vault(tmp_path):
    destino = tmp_path / "vault"
    shutil.copytree(REPO_ROOT / "vault-sandbox", destino)
    return destino


def _llamar(vault, tool, args):
    mr = _mcp()
    s = mr.SesionMCP(vault)
    try:
        return json.loads(s.llamar(tool, args)["result"]["content"][0]["text"])
    finally:
        s.cerrar()


def _contrato(vault, tool):
    entradas = json.loads(
        (vault / "00_System" / "tool-spec.json").read_text(encoding="utf-8")
    )["tools"]
    return set(entradas[tool]["declared_returns"])


def test_el_backup_cumple_su_contrato(vault):
    """De los cuatro campos declarados solo llegaba `ok`."""
    env = _llamar(vault, "vault_backup_base64", {"label": "prueba"})
    faltan = sorted(_contrato(vault, "vault_backup_base64") - set(env))
    assert not faltan, f"el backup no devuelve {faltan}; trae {sorted(env)}"
    assert env["files_included"] > 0
    assert env["size_bytes"] > 0


def test_el_backup_queda_dentro_del_vault(vault):
    """AP-36: el side effect vive bajo el vault, no al lado."""
    env = _llamar(vault, "vault_backup_base64", {"label": "contencion"})
    destino = Path(env["path"]).resolve()
    assert destino.is_file()
    assert vault.resolve() in destino.parents, destino


def test_las_lecturas_fallidas_se_declaran(vault):
    """Un backup incompleto con `ok: true` es el peor fallo de un backup.

    No se puede provocar un fichero ilegible de forma portable, así que se fija
    el contrato: el campo existe siempre, y una ejecución sana lo trae vacío.
    Sin el campo, un backup al que le faltan ficheros es indistinguible de uno
    completo — que es exactamente lo que hacía `catch (_) {}`.
    """
    env = _llamar(vault, "vault_backup_base64", {"label": "degradado"})
    assert env["degraded"] == [], env["degraded"]


def test_ida_y_vuelta(vault):
    """El invariante real: lo que entra al backup sale del restore."""
    marca = vault / "07_Knowledge" / "nota-de-ida-y-vuelta.md"
    marca.parent.mkdir(parents=True, exist_ok=True)
    marca.write_text("# Ida y vuelta\n\nContenido con acentos: cañón.\n", encoding="utf-8")

    backup = _llamar(vault, "vault_backup_base64", {"label": "roundtrip"})
    marca.unlink()

    restore = _llamar(vault, "vault_restore_base64",
                      {"path": backup["path"], "confirm": "true"})
    recuperada = Path(restore["path"]) / "07_Knowledge" / "nota-de-ida-y-vuelta.md"
    assert recuperada.is_file(), sorted(Path(restore["path"]).rglob("*.md"))[:5]
    assert "cañón" in recuperada.read_text(encoding="utf-8")
    assert restore["files_restored"] == backup["files_included"]


def test_el_restore_no_escribe_fuera_del_vault(vault):
    """Escribía en `join(vaultRoot, "..")`: una copia entera del vault, fuera."""
    backup = _llamar(vault, "vault_backup_base64", {"label": "fuera"})
    restore = _llamar(vault, "vault_restore_base64",
                      {"path": backup["path"], "confirm": "true"})
    destino = Path(restore["path"]).resolve()
    assert vault.resolve() in destino.parents, destino
    hermanos = [p.name for p in vault.parent.iterdir() if p.name != vault.name]
    assert not hermanos, f"el restore dejó cosas al lado del vault: {hermanos}"


def test_el_restore_sin_confirmar_no_escribe(vault):
    backup = _llamar(vault, "vault_backup_base64", {"label": "sin-confirmar"})
    antes = {p for p in vault.rglob("*")}
    env = _llamar(vault, "vault_restore_base64", {"path": backup["path"]})
    assert env["ok"] is False and env.get("need_confirm") is True
    assert {p for p in vault.rglob("*")} == antes


def test_una_ruta_con_traversal_se_rechaza(vault):
    """`entry.path` sale del fichero de backup, que es entrada no confiable.

    Se fabrica un backup con una entrada que escapa del directorio de restore.
    Antes escribía donde dijera la ruta; ahora la rechaza y lo declara.
    """
    backup = _llamar(vault, "vault_backup_base64", {"label": "traversal"})
    ruta = Path(backup["path"])
    envoltorio = json.loads(ruta.read_text(encoding="utf-8"))
    contenido = json.loads(zlib.decompress(b64decode(envoltorio["b64_data"])).decode("utf-8"))
    contenido["entries"].append({
        "path": "../../escapada.md",
        "content": b64encode(b"no deberia existir\n").decode("ascii"),
    })
    envoltorio["b64_data"] = b64encode(
        zlib.compress(json.dumps(contenido).encode("utf-8"))
    ).decode("ascii")
    ruta.write_text(json.dumps(envoltorio), encoding="utf-8")

    env = _llamar(vault, "vault_restore_base64", {"path": str(ruta), "confirm": "true"})
    assert env["ok"] is True
    assert [r["path"] for r in env["rejected"]] == ["../../escapada.md"], env["rejected"]
    assert not (vault.parent.parent / "escapada.md").exists()
    assert not (Path(env["path"]).parent.parent / "escapada.md").exists()
