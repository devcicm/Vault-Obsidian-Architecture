"""QA-FL-13 -- a project can be unlinked and removed, and onboarding registers it.

The flow QA found three gaps on a fresh vault:

1. `vault_project --help` offered no way back from `--link` or `--add`.
2. After deleting the project card and running `--rebuild`, the slug stayed
   registered (`ficha: None`) and `--audit` said nothing about it.
3. `vault_onboard --project repob --path <repo>` neither created the project
   card nor linked the repository, so the session protocol's next step,
   `vault_drift_detect --project repob --mode snapshot`, failed with
   `MISSING_REQUIRED_ARG`.

Every test drives the published CLI on a copy of an initialised vault. Notes
are never deleted by these flows: `--remove` refuses while anything still
belongs to the project.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from apoyo import correr_tool, entorno, escribir_nota, git_en
from vault_base import copiar_vault

TOOL = "vault_project"
LOCAL_PATHS = Path("00_System") / ".local" / "project-paths.json"


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    return copiar_vault(tmp_path / "vault", "demo")


def _repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    (repo / "README.md").write_text(f"# {name}\n\nA small repository.\n", encoding="utf-8")
    (repo / "main.py").write_text("print('hello')\n", encoding="utf-8")
    identity = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
                    GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")
    git_en(repo, "init", "-q", check=True)
    git_en(repo, "add", ".", check=True)
    git_en(repo, "commit", "-q", "-m", "init", env=identity, check=True)
    return repo


def _local_paths(vault: Path) -> dict:
    fichero = vault / LOCAL_PATHS
    return json.loads(fichero.read_text(encoding="utf-8")) if fichero.is_file() else {}


def test_help_offers_unlink_and_remove():
    run = correr_tool(TOOL, "--help")
    assert run.codigo == 0
    assert "--unlink" in run.stdout
    assert "--remove" in run.stdout


def test_unlink_forgets_the_local_path_and_sync_status_says_unlinked(vault, tmp_path):
    repo = _repo(tmp_path)
    assert correr_tool(TOOL, "--link", "demo", "--path", repo, vault=vault).codigo == 0
    assert "demo" in _local_paths(vault)

    run = correr_tool(TOOL, "--unlink", "demo", vault=vault)

    env = run.envelope
    assert run.codigo == 0 and env["ok"] is True
    assert env["action"] == "unlink" and env["project"] == "demo"
    assert env["unlinked"] is True
    assert env["written"] >= 1
    assert "demo" not in _local_paths(vault)
    status = correr_tool(TOOL, "--sync-status", "demo", vault=vault).envelope
    assert status["linked"] is False and status["state"] == "unlinked"
    # The card keeps the portable repo data and the project stays registered.
    assert (vault / "01_Projects" / "demo" / "project.md").is_file()

    again = correr_tool(TOOL, "--unlink", "demo", vault=vault)
    assert again.codigo == 0
    assert again.envelope["unlinked"] is False and again.envelope["written"] == 0


def test_unlink_with_a_different_path_is_refused_and_keeps_the_link(vault, tmp_path):
    repo = _repo(tmp_path)
    other = _repo(tmp_path, "other")
    assert correr_tool(TOOL, "--link", "demo", "--path", repo, vault=vault).codigo == 0
    before = (vault / LOCAL_PATHS).read_bytes()

    run = correr_tool(TOOL, "--unlink", "demo", "--path", other, vault=vault)

    assert run.codigo == 1
    assert run.envelope["error_code"] == "INVALID_PATH"
    assert (vault / LOCAL_PATHS).read_bytes() == before
    matching = correr_tool(TOOL, "--unlink", "demo", "--path", repo, vault=vault)
    assert matching.codigo == 0 and matching.envelope["unlinked"] is True


def test_audit_reports_a_registered_project_without_card(vault):
    (vault / "01_Projects" / "demo" / "project.md").unlink()

    env = correr_tool(TOOL, "--audit", vault=vault).envelope

    assert env["ok"] is True
    assert env["projects_without_card"] == ["demo"]
    assert env["projects_without_card_total"] == 1


def test_audit_previous_fields_are_unchanged_with_a_card(vault):
    env = correr_tool(TOOL, "--audit", vault=vault).envelope
    assert env["ok"] is True and env["projects_registered"] == 1
    assert env["phantoms"] == [] and env["projects_without_card"] == []


def test_remove_refuses_while_the_card_exists(vault):
    card = vault / "01_Projects" / "demo" / "project.md"
    before = card.read_bytes()

    run = correr_tool(TOOL, "--remove", "demo", vault=vault)

    env = run.envelope
    assert run.codigo == 1
    assert env["error_code"] == "INVALID_INPUT"
    assert "vault_delete" in env["recovery"]["hint"]
    assert env["owned_notes"] == ["01_Projects/demo/project.md"]
    assert card.read_bytes() == before


def test_remove_refuses_while_notes_belong_to_the_project(vault):
    (vault / "01_Projects" / "demo" / "project.md").unlink()
    escribir_nota(vault, "07_Knowledge/jwt.md",
                  {"title": "JWT", "project": "demo", "status": "draft"}, "# JWT\n\nbody\n")

    run = correr_tool(TOOL, "--remove", "demo", vault=vault)

    assert run.codigo == 1
    assert run.envelope["error_code"] == "INVALID_INPUT"
    assert run.envelope["owned_notes"] == ["07_Knowledge/jwt.md"]
    assert (vault / "01_Projects" / "demo").is_dir()
    assert (vault / "07_Knowledge" / "jwt.md").is_file()


def test_remove_after_the_card_is_gone_unregisters_the_slug(vault, tmp_path):
    repo = _repo(tmp_path)
    assert correr_tool(TOOL, "--link", "demo", "--path", repo, vault=vault).codigo == 0
    assert correr_tool(TOOL, "--rebuild", vault=vault).codigo == 0
    (vault / "01_Projects" / "demo" / "project.md").unlink()

    run = correr_tool(TOOL, "--remove", "demo", vault=vault)

    env = run.envelope
    assert run.codigo == 0 and env["ok"] is True, env
    assert env["action"] == "remove" and env["project"] == "demo"
    assert env["written"] >= 1
    assert not (vault / "01_Projects" / "demo").exists()
    assert "demo" not in _local_paths(vault)
    listed = correr_tool(TOOL, "--list", vault=vault).envelope
    assert [p["slug"] for p in listed["projects"]] == []
    derived = json.loads((vault / "00_System" / "project-registry.json").read_text(encoding="utf-8"))
    assert derived["projects"] == []
    unknown = correr_tool(TOOL, "--resolve", "demo", vault=vault)
    assert unknown.codigo == 1 and unknown.envelope["error_code"] == "PROJECT_NOT_FOUND"


def test_onboard_registers_and_links_so_the_drift_snapshot_works(tmp_path):
    vault = copiar_vault(tmp_path / "vault")
    repo = _repo(tmp_path, "repob")

    onboard = correr_tool("vault_onboard", "--project", "repob", "--path", repo, vault=vault)

    env = onboard.envelope
    assert onboard.codigo == 0 and env["ok"] is True, env
    assert env["project_link"]["project"] == "repob"
    assert env["project_link"]["registered"] in ("added", "aliased")
    assert env["project_link"]["linked"] is True
    assert (vault / "01_Projects" / "repob" / "project.md").is_file()
    assert Path(_local_paths(vault)["repob"]) == repo.resolve()

    snapshot = correr_tool("vault_drift_detect", "--project", "repob", "--mode", "snapshot",
                           vault=vault)
    assert snapshot.codigo == 0, snapshot.envelope
    assert snapshot.envelope["ok"] is True
    status = correr_tool(TOOL, "--sync-status", "repob", vault=vault).envelope
    assert status["linked"] is True and status["state"] == "in_sync"


def test_onboard_dry_run_registers_and_links_nothing(tmp_path):
    vault = copiar_vault(tmp_path / "vault")
    repo = _repo(tmp_path, "repob")

    run = correr_tool("vault_onboard", "--project", "repob", "--path", repo, "--dry-run",
                      vault=vault)

    env = run.envelope
    assert run.codigo == 0 and env["dry_run"] is True
    assert env["project_link"] == {"project": "repob", "dry_run": True,
                                   "would_register": True, "would_link": str(repo.resolve())}
    assert not (vault / "01_Projects" / "repob").exists()
    assert "repob" not in _local_paths(vault)


def _link_dir(link: Path, target: Path, kind: str) -> None:
    """A directory junction (Windows) or a directory symlink; skip if the OS refuses."""
    try:
        if kind == "junction":
            if os.name != "nt":
                pytest.skip("directory junctions only exist on Windows")
            import _winapi
            _winapi.CreateJunction(str(target), str(link))
        else:
            link.symlink_to(target, target_is_directory=True)
    except OSError as exc:  # symlinks need a privilege on Windows
        pytest.skip(f"cannot create a {kind}: {exc}")


def _outside(tmp_path: Path) -> Path:
    out = tmp_path / "OUT"
    (out / "sub").mkdir(parents=True)
    (out / "index.md").write_text("x\n", encoding="utf-8")
    (out / "sub" / "index.md").write_text("y\n", encoding="utf-8")
    return out


def _vault_bytes(vault: Path, skip: Path) -> dict:
    """Every vault file except git, tool traces and anything behind ``skip``."""
    state = {}
    for folder, dirs, files in os.walk(vault):
        here = Path(folder)
        dirs[:] = [d for d in dirs if d != ".git" and here / d != skip]
        for name in files:
            path = here / name
            rel = path.relative_to(vault).as_posix()
            if ".tool-trace" in rel or "voice-counter" in rel:
                continue
            state[rel] = path.read_bytes()
    return state


@pytest.mark.parametrize("kind", ["junction", "symlink"])
def test_remove_never_deletes_through_a_linked_project_folder(vault, tmp_path, kind):
    out = _outside(tmp_path)
    link = vault / "01_Projects" / "evil"
    _link_dir(link, out, kind)
    before = _vault_bytes(vault, link)

    run = correr_tool(TOOL, "--remove", "evil", vault=vault)

    env = run.envelope
    assert run.codigo == 1
    assert env["ok"] is False and env["error_code"] == "INVALID_PATH"
    assert env["project"] == "evil" and env["link"] == "01_Projects/evil"
    assert "removed_files" not in env
    assert (out / "index.md").read_text(encoding="utf-8") == "x\n"
    assert (out / "sub" / "index.md").read_text(encoding="utf-8") == "y\n"
    assert os.path.lexists(link)
    assert _vault_bytes(vault, link) == before


@pytest.mark.parametrize("kind", ["junction", "symlink"])
def test_remove_never_deletes_through_a_link_inside_the_project_folder(vault, tmp_path, kind):
    out = _outside(tmp_path)
    folder = vault / "01_Projects" / "legit"
    folder.mkdir()
    (folder / "index.md").write_text("# legit\n", encoding="utf-8")
    link = folder / "sub"
    _link_dir(link, out, kind)
    before = _vault_bytes(vault, link)

    run = correr_tool(TOOL, "--remove", "legit", vault=vault)

    env = run.envelope
    assert run.codigo == 1
    assert env["error_code"] == "INVALID_PATH"
    assert env["link"] == "01_Projects/legit/sub"
    assert (out / "index.md").is_file() and (out / "sub" / "index.md").is_file()
    assert (folder / "index.md").is_file() and os.path.lexists(link)
    assert _vault_bytes(vault, link) == before
