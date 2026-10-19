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

El segundo defecto que cierra: hasta 2026-10-18 el estado que estos tests
mutaban era el `vault-sandbox/` COMPARTIDO del repo, con un read-modify-write
sin lock. Con la suite en paralelo (`-n auto`) otro worker leía el sello a
medias, `test_un_vault_al_dia` dependía de qué worker había re-sembrado el
runtime, y una corrida muerta a mitad del fixture dejaba el sandbox atrasado
para todo lo que venía después. Cada test trabaja ahora sobre una raíz
desechable en su `tmp_path`, apuntada por `VAULT_ROOT` — el mismo puerto que
usa cualquier consumidor real de la tool.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_standard_upgrade as vsu  # noqa: E402

#: Misma mayor que la vigente y sin su menor: atrasada, pero sin migración
#: estructural pendiente. Hasta v41.0 era el literal "v40.0", que con la mayor
#: nueva pasó a tener la migración v41 pendiente y dejó de probar este camino.
ATRASADA = vsu.CURRENT_VERSION.split(".", 1)[0]


def _escribir_estado(raiz: Path, version: str) -> Path:
    estado = raiz / "00_System" / "standard-version.json"
    estado.write_text(
        json.dumps({"applied_version": version, "applied_at": None,
                    "applied_by": "pytest", "migrations_applied": []},
                   indent=2) + "\n",
        encoding="utf-8",
    )
    return estado


def _raiz_con_version(tmp_path: Path, version: str) -> Path:
    """Una raíz desechable con su `standard-version.json` sellado en `version`."""
    raiz = tmp_path / "vault-sandbox"
    (raiz / "00_System").mkdir(parents=True)
    _escribir_estado(raiz, version)
    return raiz


def _raiz_de(estado: Path) -> Path:
    """La raíz del vault a la que pertenece un fichero de estado."""
    return estado.parent.parent


@pytest.fixture
def sandbox_atrasado(tmp_path):
    """Una raíz propia, una menor por detrás de la vigente, y el estado que la
    declara. Nada fuera del `tmp_path` del test se lee ni se escribe."""
    return _escribir_estado(_raiz_con_version(tmp_path, ATRASADA), ATRASADA)


def _correr(raiz: Path, *flags):
    env = {**os.environ, "VAULT_ROOT": str(raiz), "VAULT_STRICT_ROOT": "1"}
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "vault_standard_upgrade.py"), *flags],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO_ROOT), timeout=120, env=env,
    )
    return json.loads(proc.stdout)


@pytest.mark.parametrize("flags", [("--check",), ("--dry-run",), ("--check", "--from", "v39.0")])
def test_preguntar_no_escribe(flags, sandbox_atrasado):
    antes = sandbox_atrasado.read_bytes()
    _correr(_raiz_de(sandbox_atrasado), *flags)
    assert sandbox_atrasado.read_bytes() == antes, (
        f"{' '.join(flags)} modificó el estado de versión del vault"
    )


def test_check_no_se_atribuye_un_sellado_que_no_hizo(sandbox_atrasado):
    env = _correr(_raiz_de(sandbox_atrasado), "--check")
    assert env["version_stamped"] is False
    assert env["action"] != "version_stamped"


def test_check_dice_que_hay_un_sello_pendiente_y_como_hacerlo(sandbox_atrasado):
    """Si no lo hace por su cuenta, tiene que decirlo — o es AP-37 al revés."""
    env = _correr(_raiz_de(sandbox_atrasado), "--check")
    assert env["stamp_pending"] is True
    assert f"--to {vsu.CURRENT_VERSION}" in env["message"]
    assert "no se ha escrito nada" in env["message"]


def test_el_estado_no_avanza_solo_por_preguntar(sandbox_atrasado):
    _correr(_raiz_de(sandbox_atrasado), "--check")
    assert json.loads(sandbox_atrasado.read_text(encoding="utf-8"))["applied_version"] == ATRASADA


def test_sellar_sigue_siendo_posible_cuando_se_pide(sandbox_atrasado):
    env = _correr(_raiz_de(sandbox_atrasado), "--to", vsu.CURRENT_VERSION)
    assert env["version_stamped"] is True
    assert env["action"] == "version_stamped"
    assert json.loads(sandbox_atrasado.read_text(encoding="utf-8"))["applied_version"] == \
        vsu.CURRENT_VERSION


def test_un_vault_al_dia_no_declara_nada_pendiente(tmp_path):
    raiz = _raiz_con_version(tmp_path, vsu.CURRENT_VERSION)
    env = _correr(raiz, "--check")
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
        assert "stamp_pending" in _correr(_raiz_de(sandbox_atrasado), *flags), flags
