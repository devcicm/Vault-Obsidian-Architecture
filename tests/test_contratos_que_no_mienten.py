"""Los contratos que no pueden mentir: un fallo nunca se lee como un éxito.

Cuatro defectos medidos el 2026-11-08, todos de la misma familia (AP-51: un
vacio indistinguible de un resultado legítimo) y dos de ellos del propio
producto, aparecidos al usar el verbo de reparación contra un vault real:

1. `reparar_indice` respondía «cero — el índice ya cumple la política» cuando
   **git no había respondido**: el repo del vault pertenecía a otra cuenta y
   git lo rechazaba. Una lista vacía indistinguible de «no hay nada que
   reparar» es un fallo presentado como un éxito.
2. `vault_undo --commits` respondía «0 operaciones» con el mismo git mudo.
3. `vault_mcp_catalog --check-contracts` se caía con `Traceback` cuando el
   vault no tenía `tool-spec.json`: el envelope que lo cubría estaba escrito,
   pero **debajo** del `Path(None)` que reventaba.
4. El verificador del merkle respondía `ok: true` con ficheros ilegibles.
5. La escritura atómica dejaba el temporal en el disco con `KeyboardInterrupt`.
6. El escáner de secretos confundía un hash de commit (40 hex) con una clave
   de AWS y bloqueaba evidencia legítima con `GUARD_CHAIN_FAILED`.

El criterio es el del consumidor: se ejecuta el camino real y se lee lo que
vuelve, no se inspecciona el fuente.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"


# ─── 1 y 2: git que no responde NO es «cero» ─────────────────────────────────


def test_el_verbos_no_dicen_cero_cuando_git_no_responde(tmp_path, monkeypatch):
    """`reparar_indice` con git mudo: ni «cero» ni «reparado»."""
    from vault.kernel import vcs

    raiz = tmp_path / "vault"
    (raiz / ".git").mkdir(parents=True)

    class _Fallido:
        returncode = 128
        stdout = ""
        stderr = "fatal: detected dubious ownership in repository"

    monkeypatch.setattr(vcs, "_git", lambda *a, **k: _Fallido())
    resultado = vcs.reparar_indice(raiz)
    assert resultado["reparado"] is False, resultado
    assert resultado.get("git_no_respondio") is True, resultado
    assert "cero" not in resultado, f"«cero» con git mudo: {resultado}"
    assert "dubious ownership" in resultado["motivo"], resultado


def test_los_commits_no_dicen_cero_cuando_git_no_responde(tmp_path, monkeypatch):
    """`commits_con_estado` distingue «no hay» de «no se pudo leer»."""
    from vault.kernel import vcs

    raiz = tmp_path / "vault"
    (raiz / ".git").mkdir(parents=True)

    class _Fallido:
        returncode = 128
        stdout = ""
        stderr = "fatal: detected dubious ownership in repository"

    monkeypatch.setattr(vcs, "_git", lambda *a, **k: _Fallido())
    operaciones, error = vcs.commits_con_estado(raiz)
    assert operaciones == [], operaciones
    assert error and "dubious ownership" in error, error


def test_el_envelope_de_commits_publish_el_fallo(tmp_path, monkeypatch):
    """`vault_undo --commits` responde con error_code, no con una lista vacía."""
    import vault_undo

    class _Fallido:
        returncode = 128
        stdout = ""
        stderr = "fatal: detected dubious ownership in repository"

    from vault.kernel import vcs

    monkeypatch.setattr(vcs, "hay_repo", lambda raiz: True)
    monkeypatch.setattr(vcs, "commits_con_estado",
                        lambda raiz, limite=20: ([], "dubious ownership"))
    envelope = vault_undo._operaciones_del_vault(10)
    assert envelope["ok"] is False, envelope
    assert envelope["error_code"] == "GIT_NO_RESPONDIO", envelope
    assert "operations" not in envelope, envelope


# ─── 3: el contrato ausente se responde, no revienta ───────────────────────


def test_check_contracts_sin_spec_devuelve_envelope(tmp_path):
    """El crash estaba debajo del arreglo: `Path(None)` reventaba antes."""
    from apoyo import correr_tool

    vault = tmp_path / "vault-sin-spec"
    (vault / "00_System").mkdir(parents=True)
    r = correr_tool("vault_mcp_catalog", "--check-contracts", vault=vault)
    assert r.codigo != 0, r.stdout + r.stderr
    assert r.stdout.strip(), "stdout vacío: no hay envelope que leer"
    envelope = json.loads(r.stdout)
    assert envelope["ok"] is False, envelope
    assert envelope["error_code"] == "FILE_NOT_FOUND", envelope
    assert "Traceback" not in r.stderr, r.stderr


# ─── 4: el merkle con ilegibles no se verifica ─────────────────────────────


def test_el_merkle_con_ficheros_ilegibles_no_se_da_por_verificado(tmp_path):
    """`ok: true` con `intact: false` se leía como un backup verificado."""
    from vault.durabilidad import snapshot

    backup = tmp_path / "backup"
    backup.mkdir()
    (backup / "nota.md").write_text("# nota\n", encoding="utf-8")
    (backup / snapshot.FICHERO_MANIFIESTO).write_text(
        json.dumps({"merkle_root": "0" * 64, "merkle_algo": 1,
                    "merkle_file_count": 1}), encoding="utf-8")

    def _merkle(ruta, algo, coleccion=None):
        if coleccion is not None:
            coleccion.append("nota.md")
        return ("raiz", 1)

    original = snapshot.merkle_de
    snapshot.merkle_de = _merkle
    try:
        servicio = object.__new__(snapshot.ServicioSnapshot)

        class _Repo:
            @staticmethod
            def ruta_de(nombre):
                return backup

        servicio._repo = _Repo()
        envelope = servicio.verificar("backup")
    finally:
        snapshot.merkle_de = original

    assert envelope["ok"] is False, envelope
    assert envelope["intact"] is False, envelope
    assert envelope["unreadable"], envelope


# ─── 5: el temporal no sobrevive a un Ctrl-C ────────────────────────────────


def test_la_escritura_atomica_limpia_el_temporal_si_interrumpen(tmp_path):
    """`except Exception` no cubre `KeyboardInterrupt`: el `.tmp.*` quedaba."""
    from vault.kernel import escritura

    destino = tmp_path / "nota.md"

    def _interrumpir(*_a, **_k):
        raise KeyboardInterrupt()

    original = escritura._escribir_temporal
    escritura._escribir_temporal = _interrumpir
    try:
        with pytest.raises(KeyboardInterrupt):
            escritura.escritura_atomica(destino, "contenido")
    finally:
        escritura._escribir_temporal = original

    temporales = list(tmp_path.glob(".tmp.*"))
    assert not temporales, f"quedaron temporales: {temporales}"


# ─── 6: un hash de commit no es una credencial ──────────────────────────────


def test_un_hash_de_commit_no_es_un_secreto():
    """El guard bloqueó una nota de auditoría legítima: `GUARD_CHAIN_FAILED`."""
    from vault.gobernanza.secret_scan import scan_content

    sha = "1db90da822904345980165b44b18917eff2fe257"
    hallazgos = scan_content(f"El commit revisado es `{sha}` del repositorio.")
    ids = {h["pattern_id"] for h in hallazgos}
    assert "aws_secret_key" not in ids, hallazgos

    # Y una credencial real sigue saltando: el arreglo no abre la puerta.
    clave = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    hallazgos = scan_content(f"la clave es {clave} en el archivo")
    ids = {h["pattern_id"] for h in hallazgos}
    assert "aws_secret_key" in ids, hallazgos
