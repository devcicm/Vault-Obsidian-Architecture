"""Tests de paquete de la ID norma AP-83 (DAG en vault_fix_all, SagaPreSha y CheckpointLog)."""

import importlib.util
from pathlib import Path
import subprocess
import tempfile

from vault.kernel.ciclo_ejecucion import CheckpointLog, SagaPreSha

_ROOT = Path(__file__).resolve().parents[2]


def _cargar_fix_all():
    spec = importlib.util.spec_from_file_location("vault_fix_all", _ROOT / "scripts" / "vault_fix_all.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ap83_dag_topologico_en_vault_fix_all():
    vfa = _cargar_fix_all()
    orden = [p["nombre"] for p in vfa.orden_topologico_pasos()]
    assert set(orden) == {p["nombre"] for p in vfa.PASOS}
    assert len(orden) == len(vfa.PASOS)
    pos = {nombre: idx for idx, nombre in enumerate(orden)}
    for paso, deps in vfa.DEPENDENCIAS_PASOS.items():
        for dep in deps:
            assert pos[dep] < pos[paso], f"{dep} debe preceder a {paso}"


def test_ap83_checkpoints_replay_y_saga_pre_sha():
    with tempfile.TemporaryDirectory() as td:
        tmp_path = Path(td)
        vault = tmp_path / "vault-git"
        vault.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=vault, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=vault, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=vault, check=True)
        nota = vault / "nota.md"
        nota.write_text("estado inicial\n", encoding="utf-8")
        subprocess.run(["git", "add", "nota.md"], cwd=vault, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "inicial"], cwd=vault, check=True)

        ck = CheckpointLog(vault)
        ck.save_checkpoint("run-1", "paso-a")
        ck.save_checkpoint("run-1", "paso-b")
        assert ck.replay_pending("run-1", ["paso-a", "paso-b", "paso-c"]) == ["paso-c"]

        saga = SagaPreSha(vault, run_id="run-1")
        sha = saga.begin()
        assert sha and len(sha) == 40
        nota.write_text("mutacion parcial fallida\n", encoding="utf-8")
        comp = saga.compensate(checkpoints=ck)
        assert comp["ok"] is True and comp["compensated"] is True
        assert nota.read_text(encoding="utf-8") == "estado inicial\n"
