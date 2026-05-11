#!/usr/bin/env python3
"""Shared file IO helpers for vault tools."""

import json
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterator


@contextmanager
def file_lock(target: Path, timeout: float = 30.0, stale_after: float = 120.0) -> Iterator[Path]:
    """Create an atomic directory lock near the target file.

    This avoids lost updates when multiple documentation tools update the same
    JSON index during mass generation. Stale locks are removed after
    ``stale_after`` seconds.
    """
    lock_root = target.parent / ".locks"
    lock_root.mkdir(parents=True, exist_ok=True)
    lock_dir = lock_root / f"{target.name}.lock"
    deadline = time.time() + timeout

    while True:
        try:
            os.mkdir(lock_dir)
            (lock_dir / "owner.json").write_text(
                json.dumps({"pid": os.getpid(), "createdAt": time.time()}),
                encoding="utf-8",
            )
            break
        except FileExistsError:
            try:
                age = time.time() - lock_dir.stat().st_mtime
                if age > stale_after:
                    for child in lock_dir.iterdir():
                        child.unlink()
                    lock_dir.rmdir()
                    continue
            except OSError:
                pass
            if time.time() >= deadline:
                raise TimeoutError(f"Timeout waiting for lock: {lock_dir}")
            time.sleep(0.05)

    try:
        yield lock_dir
    finally:
        try:
            for child in lock_dir.iterdir():
                child.unlink()
            lock_dir.rmdir()
        except OSError:
            pass


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temp.write_text(text, encoding=encoding)
    os.replace(temp, path)


def atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def atomic_update_json(
    path: Path,
    default: Dict[str, Any],
    update: Callable[[Dict[str, Any]], Dict[str, Any]],
    timeout: float = 30.0,
) -> Dict[str, Any]:
    with file_lock(path, timeout=timeout):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = dict(default)
        except (FileNotFoundError, json.JSONDecodeError):
            data = dict(default)
        updated = update(data)
        atomic_write_json(path, updated)
        return updated
