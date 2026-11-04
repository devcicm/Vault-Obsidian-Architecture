"""Un restore no puede truncar: antes de sustituir, el estado actual se copia.

Medido el 2026-11-04: `vault_restore`ava el contenido del vault por el del
snapshot, y lo que hubiera hecho desde el último backup se perdía sin más
(con el `--confirm true` como único freno, que es una confirmación de la
operación, no una red). Ahora, antes de borrar, se copia el estado actual: el
restore declara el snapshot de seguridad con el que se puede volver.
"""

import json
from pathlib import Path

import pytest

from apoyo import correr_tool  # noqa: E402

CUERPO = (
    "# Nota de la red\n\n"
    "Linea uno con contenido real para que el contrato de la nota (AP-11) la\n"
    "acepte y la tool no frene la escritura.\n\n"
    "Tercera linea: tres lineas reales de contenido.\n"
)


@pytest.fixture()
def vault(tmp_path):
    raiz = tmp_path / "vault"
    raiz.mkdir()
    r = correr_tool("vault_init", "--no-audit", vault=raiz)
    assert r.codigo == 0, r.stdout + r.stderr
    return raiz


def test_el_restore_copia_el_estado_actual_antes_de_sustituir(vault, tmp_path):
    """El snapshot de seguridad es lo que hace que el restore no trunque."""
    cuerpo = tmp_path / "cuerpo.md"
    cuerpo.write_text(CUERPO, encoding="utf-8")
    correr_tool("vault_write", "--folder", "07_Knowledge", "--title", "Nota del backup",
                "--content", f"@file:{cuerpo}", "--tags", "prueba", vault=vault)

    backup = correr_tool("vault_backup", "--label", "antes", vault=vault)
    assert backup.codigo == 0, backup.stdout + backup.stderr
    sobre = json.loads(backup.stdout.strip().splitlines()[-1])
    nombre_backup = sobre.get("name") or Path(sobre.get("path", "")).name

    # Ahora, una nota que el backup NO tiene: al restaurar, se perdería.
    cuerpo2 = tmp_path / "cuerpo2.md"
    cuerpo2.write_text("\n".join([
        CUERPO,
        "Una linea que solo existe ahora.",
        "",
    ]), encoding="utf-8")
    correr_tool("vault_write", "--folder", "07_Knowledge", "--title", "Nota posterior",
                "--content", f"@file:{cuerpo2}", "--tags", "prueba", vault=vault)

    restore = correr_tool("vault_restore", "--backup_name", str(nombre_backup),
                           "--confirm", "true", vault=vault)
    assert restore.codigo == 0, restore.stdout + restore.stderr
    envelope = json.loads(restore.stdout.strip().splitlines()[-1])
    assert envelope["ok"] is True, envelope

    # La red: el estado anterior al restore está en un snapshot con nombre.
    seguridad = envelope.get("safety_snapshot")
    assert seguridad, envelope
    assert "antes-de-restaurar" in seguridad, seguridad
    assert (vault / "vault-backups" / seguridad).is_dir(), seguridad

    # Y la nota posterior se puede recuperar desde ahí: no se perdió.
    recuperada = vault / "vault-backups" / seguridad / "07_Knowledge" / "nota-posterior.md"
    assert recuperada.is_file(), sorted(
        str(p.relative_to(vault)) for p in (vault / "vault-backups" / seguridad).rglob("*.md"))[:8]


def test_el_restore_sin_confirmar_no_escribe(vault):
    """La confirmación sigue siendo obligatoria (no es lo que se cambia)."""
    antes = {p for p in vault.rglob("*")}
    r = correr_tool("vault_restore", "--backup_name", "no-existe", vault=vault)
    assert r.codigo == 1
    assert {p for p in vault.rglob("*")} == antes
