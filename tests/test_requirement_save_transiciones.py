"""D-03 -- un cambio de estado de un requisito deja una fila `transition` y un evento."""
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

from vault_base import copiar_vault

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vault_requirement_save.py"


@pytest.mark.parametrize("payload", [[], {"requirements": {}}, {"requirements": [], "counters": {"demo": "bad"}}])
def test_invalid_projection_is_not_overwritten_during_replay(tmp_path, payload):
    import vault_io
    import vault_requirement_save as requirements

    index = tmp_path / "14_Requirements" / ".requirements-index.json"
    index.parent.mkdir()
    index.write_text(json.dumps(payload), encoding="utf-8")
    vault_io.set_vault_root(tmp_path)
    before = index.read_bytes()
    result = requirements.reconstruir_indice_requisitos()
    assert not result["ok"] and result["history_incomplete"]
    assert index.read_bytes() == before


def _run(raiz, *argv):
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest")
    p = subprocess.run([sys.executable, str(SCRIPT), *argv], env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", cwd=str(raiz.parent), timeout=300)
    return p.returncode, json.loads(p.stdout[p.stdout.index("{"):])


def _guardar(raiz, estado):
    return _run(raiz, "--project", "demo", "--title", "Login seguro", "--type", "functional",
                "--priority", "must-have", "--description", "Descripcion suficiente del requisito.",
                "--status", estado)


def test_cada_cambio_de_estado_deja_fila_y_evento(tmp_path):
    raiz = copiar_vault(tmp_path / "vault", "demo")
    assert _guardar(raiz, "draft")[1]["transition_logged"] is True
    assert _guardar(raiz, "approved")[1]["transition_logged"] is True
    # Mismo estado y mismo cuerpo: ni evento ni fila.
    assert _guardar(raiz, "approved")[1]["transition_logged"] is False

    indice = json.loads(next(raiz.rglob(".requirements-index.json")).read_text(encoding="utf-8"))
    ev = indice["requirements"][0]["events"]
    assert [(e["from"], e["to"]) for e in ev] == [(None, "draft"), ("draft", "approved")]

    log = json.loads((raiz / "00_System" / ".change-log.json").read_text(encoding="utf-8"))
    filas = [e for e in log if e["action"] == "transition"]
    assert [e["reason"] for e in filas] == ["REQ-001: (nuevo) -> draft", "REQ-001: draft -> approved"]
    assert [e["requirement"]["identity"] for e in filas] == ["demo/REQ-001"] * 2
    assert [e["id"] for e in filas] == [e["id"] for e in ev]


def test_requirement_projection_replays_complete_log_and_is_idempotent(tmp_path):
    import uuid
    import vault_io
    import vault_requirement_save as requirements

    root = copiar_vault(tmp_path / "vault", "demo")
    assert _guardar(root, "approved")[0] == 0
    log_path = root / "00_System" / ".change-log.json"
    log = json.loads(log_path.read_text(encoding="utf-8"))
    event = next(e for e in log if e["action"] == "transition")
    rows = []
    for number in range(31):
        state = "approved" if number % 2 == 0 else "draft"
        previous = "draft" if state == "approved" else "approved"
        row = {**event, "id": str(uuid.uuid4()),
               "requirement": {**event["requirement"], "from": None if number == 0 else previous,
                               "to": state}}
        rows.append(row)
    log_path.write_text(json.dumps(rows), encoding="utf-8")
    index = root / "14_Requirements" / ".requirements-index.json"
    index.unlink()
    code, saved = _guardar(root, "approved")
    assert code == 0 and saved["req_id"] == "REQ-001", saved
    vault_io.set_vault_root(root)
    result = requirements.reconstruir_indice_requisitos()
    assert result["ok"], result
    data = json.loads(index.read_text(encoding="utf-8"))
    assert len(data["requirements"][0]["events"]) == 31
    before = index.read_bytes()
    assert requirements.reconstruir_indice_requisitos()["ok"]
    assert index.read_bytes() == before
    assert json.loads(log_path.read_text(encoding="utf-8")) == rows


def test_legacy_requirement_history_is_reported_not_guessed(tmp_path):
    import vault_io
    import vault_requirement_save as requirements

    root = copiar_vault(tmp_path / "vault", "demo")
    assert _guardar(root, "draft")[0] == 0
    log_path = root / "00_System" / ".change-log.json"
    rows = json.loads(log_path.read_text(encoding="utf-8"))
    for row in rows:
        row.pop("requirement", None)
    log_path.write_text(json.dumps(rows), encoding="utf-8")
    vault_io.set_vault_root(root)
    result = requirements.reconstruir_indice_requisitos()
    assert not result["ok"]
    assert result["history_incomplete"] is True
    assert result["legacy_events"] == 1
    assert result["legacy_paths"] == [rows[0]["path"]]
    assert result["recovery"]["action"] == "manual"


def test_durable_event_retry_does_not_duplicate_after_markdown_failure(tmp_path, monkeypatch):
    import vault_change_log
    import vault_io
    import vault_requirement_save as requirements

    root = copiar_vault(tmp_path / "vault", "demo")
    vault_io.set_vault_root(root)
    arguments = dict(project="demo", title="Retry", description="Requirement description",
                     req_type="functional", priority="must-have")

    def broken(entry):
        raise OSError("PRIVATE-HISTORY-CANARY")

    with monkeypatch.context() as patch:
        patch.setattr(vault_change_log, "_append_md_log", broken)
        result = requirements.vault_requirement_save(**arguments)
    assert result["ok"] is False and result["partial"] is True
    assert result["transition_logged"] is False
    assert "PRIVATE-HISTORY-CANARY" not in json.dumps(result)
    result = requirements.vault_requirement_save(**arguments)
    assert result["ok"] and result["transition_logged"]
    assert requirements.vault_requirement_save(**arguments)["transition_logged"] is False
    rows = json.loads((root / "00_System" / ".change-log.json").read_text(encoding="utf-8"))
    assert len([row for row in rows if row.get("requirement")]) == 1
    index = json.loads((root / "14_Requirements" / ".requirements-index.json").read_text(encoding="utf-8"))
    assert len(index["requirements"][0]["events"]) == 1
    assert "pending_transition" not in index["requirements"][0]


def test_retry_after_projection_failure_converges_without_duplicate_events(tmp_path, monkeypatch):
    """The ledger commit succeeded, the index write did not: retries must converge (F1)."""
    import vault_io
    import vault_requirement_save as requirements

    root = copiar_vault(tmp_path / "vault", "demo")
    vault_io.set_vault_root(root)
    arguments = dict(project="demo", title="Projection retry", description="Requirement description",
                     req_type="functional", priority="must-have")
    assert requirements.vault_requirement_save(**arguments, status="draft")["ok"]
    original = vault_io.atomic_write_json

    def failing_index(path, *args, **kwargs):
        if Path(path).name == ".requirements-index.json":
            raise OSError("PRIVATE-INDEX-CANARY")
        return original(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(vault_io, "atomic_write_json", failing_index)
        with pytest.raises(OSError):
            requirements.vault_requirement_save(**arguments, status="approved")
    for _ in range(3):
        assert requirements.vault_requirement_save(**arguments, status="approved")["ok"]
    rows = json.loads((root / "00_System" / ".change-log.json").read_text(encoding="utf-8"))
    transitions = [(r["requirement"]["from"], r["requirement"]["to"]) for r in rows if r.get("requirement")]
    assert transitions == [(None, "draft"), ("draft", "approved")]
    index = json.loads((root / "14_Requirements" / ".requirements-index.json").read_text(encoding="utf-8"))
    entry = index["requirements"][0]
    assert entry["status"] == "approved"
    assert [(e["from"], e["to"]) for e in entry["events"]] == transitions
    assert requirements.reconstruir_indice_requisitos()["ok"]


def test_lost_index_with_no_remaining_notes_never_reuses_an_identifier(tmp_path):
    """Counters are recovered from durable history even when every note is gone (F4)."""
    import vault_io
    import vault_requirement_save as requirements

    root = copiar_vault(tmp_path / "vault", "demo")
    vault_io.set_vault_root(root)
    first = requirements.vault_requirement_save(
        project="demo", title="First requirement", description="Requirement description",
        req_type="functional", priority="must-have")
    assert first["ok"] and first["req_id"] == "REQ-001"
    (root / first["path"]).unlink()
    (root / "14_Requirements" / ".requirements-index.json").unlink()
    second = requirements.vault_requirement_save(
        project="demo", title="Second requirement", description="Requirement description",
        req_type="functional", priority="must-have")
    assert second["ok"] and second["req_id"] == "REQ-002", second
    assert requirements.reconstruir_indice_requisitos()["ok"]
