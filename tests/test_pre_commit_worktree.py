"""El hook se ancla al checkout activo, no al gitdir que lo almacena."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".githooks" / "pre-commit"
_git_exec = Path(subprocess.run(
    ["git", "--exec-path"], check=True, capture_output=True, text=True,
    encoding="utf-8", errors="replace",
).stdout.strip())
SH = shutil.which("sh") or next(
    (str(p) for p in (_git_exec.parents[2] / "bin" / "sh.exe",) if p.exists()), None
)


@pytest.mark.skipif(SH is None, reason="requiere shell POSIX de Git")
def test_hook_resuelve_checkout_convencional_y_worktree(tmp_path):
    fuera = tmp_path / "fuera"
    fuera.mkdir()
    invalido = subprocess.run(
        [SH, str(HOOK)], cwd=fuera, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    assert invalido.returncode != 0
    assert "checkout Git activo" in invalido.stderr

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "base.txt"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "commit", "-m", "base"],
        cwd=repo, check=True, capture_output=True,
    )

    worktree = tmp_path / "secondary"
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(worktree)],
        cwd=repo, check=True, capture_output=True,
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    python_spy = bin_dir / "python"
    python_spy.write_text(
        "#!/bin/sh\nprintf '%s|%s\\n' \"$(git rev-parse --show-toplevel)\" "
        "\"$(git rev-parse --show-prefix)\" >> \"$HOOK_PROBE\"\n",
        encoding="utf-8",
    )
    python_spy.chmod(0o755)

    try:
        for checkout in (repo, worktree):
            probe = tmp_path / f"{checkout.name}.log"
            env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                   "HOOK_PROBE": str(probe)}
            subprocess.run(
                [SH, str(HOOK)], cwd=checkout, env=env,
                check=True, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
            calls = [line.split("|", 1) for line in
                     probe.read_text(encoding="utf-8").splitlines()]
            assert len(calls) == 2
            assert all(Path(root).resolve() == checkout.resolve() for root, _ in calls)
            assert all(prefix == "" for _, prefix in calls)
            assert not subprocess.run(
                ["git", "status", "--porcelain"], cwd=checkout,
                check=True, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            ).stdout
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=repo, check=True, capture_output=True,
        )
