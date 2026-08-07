"""El contrato de versión con los repos consumidores.

Un vault consumidor pregunta dos cosas a `vault_standard_upgrade`: en qué
versión está y si tiene algo pendiente. Las dos son preguntas — ninguna
autoriza a escribir.

El defecto que cierra este fichero: la rama de «salto menor sin migración
estructural» comprobaba `dry_run` pero **no** `check_only`, así que un
consumidor que solo corría `--check` salía sellado en la versión nueva sin
haberlo pedido, y el envelope se lo devolvía como `action: version_stamped`.
Escribir de más en un vault ajeno al preguntar es la peor forma de este fallo:
el consumidor no tiene por qué revisar si una consulta le tocó el estado.

Sellar sigue estando disponible, y con el comando exacto en el mensaje. Lo que
cambia es quién decide.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_standard_upgrade as vsu  # noqa: E402

ESTADO = REPO_ROOT / "vault-sandbox" / "00_System" / "standard-version.json"


@pytest.fixture
def sandbox_atrasado():
    """Deja el sandbox una menor por detrás y lo restaura pase lo que pase."""
    original = ESTADO.read_bytes()
    d = json.loads(original.decode("utf-8"))
    d["applied_version"] = "v40.0"
    ESTADO.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
    try:
        yield ESTADO
    finally:
        ESTADO.write_bytes(original)


def _correr(*flags):
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "vault_standard_upgrade.py"), *flags],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO_ROOT), timeout=120,
    )
    return json.loads(proc.stdout)


@pytest.mark.parametrize("flags", [("--check",), ("--dry-run",), ("--check", "--from", "v39.0")])
def test_preguntar_no_escribe(flags, sandbox_atrasado):
    antes = sandbox_atrasado.read_bytes()
    _correr(*flags)
    assert sandbox_atrasado.read_bytes() == antes, (
        f"{' '.join(flags)} modificó el estado de versión del vault"
    )


def test_check_no_se_atribuye_un_sellado_que_no_hizo(sandbox_atrasado):
    env = _correr("--check")
    assert env["version_stamped"] is False
    assert env["action"] != "version_stamped"


def test_check_dice_que_hay_un_sello_pendiente_y_como_hacerlo(sandbox_atrasado):
    """Si no lo hace por su cuenta, tiene que decirlo — o es AP-37 al revés."""
    env = _correr("--check")
    assert env["stamp_pending"] is True
    assert f"--to {vsu.CURRENT_VERSION}" in env["message"]
    assert "no se ha escrito nada" in env["message"]


def test_el_estado_no_avanza_solo_por_preguntar(sandbox_atrasado):
    _correr("--check")
    assert json.loads(sandbox_atrasado.read_text(encoding="utf-8"))["applied_version"] == "v40.0"


def test_sellar_sigue_siendo_posible_cuando_se_pide(sandbox_atrasado):
    env = _correr("--to", vsu.CURRENT_VERSION)
    assert env["version_stamped"] is True
    assert env["action"] == "version_stamped"
    assert json.loads(sandbox_atrasado.read_text(encoding="utf-8"))["applied_version"] == \
        vsu.CURRENT_VERSION


def test_un_vault_al_dia_no_declara_nada_pendiente():
    env = _correr("--check")
    assert env["stamp_pending"] is False
    assert env["version_stamped"] is False


def test_una_menor_no_inventa_migraciones_estructurales():
    """`_pending_migrations` compara por versión mayor, y está bien que lo haga.

    v40.1 → v40.2 no crea ni renombra una carpeta. Lo que faltaba no era una
    migración: era decir en voz alta que no la hay.
    """
    assert vsu._pending_migrations("v40.1", "v40.2") == []
    assert vsu._version_index("v40.2") == vsu._version_index("v40.0")


def test_stamp_pending_esta_en_el_envelope_siempre_que_no_haya_migraciones(sandbox_atrasado):
    for flags in (("--check",), ("--dry-run",)):
        assert "stamp_pending" in _correr(*flags), flags
