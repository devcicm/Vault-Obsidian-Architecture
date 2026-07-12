#!/usr/bin/env python3
"""vault_errors_trace — Trace log + token usage logging for vault tools.

Importado por vault_errors.py. No debe importar vault_errors (circular).
"""

import json
import re as _re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from vault_io import atomic_write_text, file_lock, get_vault_root


# AP-36: los paths se resuelven LAZY vía get_vault_root() en cada llamada, para
# que un tool ejecutado con --root (que llama vault_io.set_vault_root) escriba
# sus traces en el vault objetivo y no en el VAULT_ROOT detectado en import.
def trace_file() -> Path:
    return get_vault_root() / "00_System" / ".tool-trace.json"


def tokens_file() -> Path:
    return get_vault_root() / "00_System" / ".tool-tokens.json"


TRACE_MAX_ENTRIES = 500
TOKENS_MAX_ENTRIES = 2000


def _append_trace_entry(entry: Dict[str, Any], use_atomic: bool) -> None:
    """Lee, rota y escribe el trace file."""
    tf = trace_file()
    if tf.exists():
        try:
            entries: List[Dict] = json.loads(tf.read_text(encoding="utf-8"))
            if not isinstance(entries, list):
                entries = []
        except Exception:
            entries = []
    else:
        entries = []

    entries.append(entry)
    if len(entries) > TRACE_MAX_ENTRIES:
        entries = entries[-TRACE_MAX_ENTRIES:]

    text = json.dumps(entries, indent=2, ensure_ascii=False)
    if use_atomic:
        atomic_write_text(tf, text)
    else:
        tf.write_text(text, encoding="utf-8")


def log_trace(entry: Dict[str, Any]) -> None:
    """Añade entrada al trace log con rotación a TRACE_MAX_ENTRIES."""
    try:
        tf = trace_file()
        tf.parent.mkdir(parents=True, exist_ok=True)
        try:
            with file_lock(tf, timeout=5):
                _append_trace_entry(entry, use_atomic=True)
            return
        except TimeoutError:
            pass
        _append_trace_entry(entry, use_atomic=False)
    except Exception:
        pass


def query_trace(
    tool: Optional[str] = None,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    last: int = 20,
) -> List[Dict[str, Any]]:
    """Consulta el trace log."""
    tf = trace_file()
    if not tf.exists():
        return []
    try:
        entries: List[Dict] = json.loads(tf.read_text(encoding="utf-8"))
    except Exception:
        return []
    if tool:
        entries = [e for e in entries if e.get("tool") == tool]
    if severity:
        entries = [e for e in entries if e.get("severity") == severity]
    if category:
        entries = [e for e in entries if e.get("category") == category]
    return list(reversed(entries))[:last]


def _count_tokens(text: str) -> Tuple[int, str]:
    """Count tokens using best available tokenizer (anthropic → tiktoken → heuristic)."""
    if not text:
        return 0, "heuristic"

    try:
        import anthropic

        client = anthropic.Anthropic(api_key="dummy")
        count = client.count_tokens(text)
        return count, "anthropic"
    except Exception:
        pass

    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text)), "tiktoken"
    except Exception:
        pass

    pieces = _re.findall(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]", text)
    total = sum(
        max(1, (len(p) + 3) // 4) if _re.match(r"^[A-Za-z0-9_]+$", p) else 1
        for p in pieces
    )
    return max(1, total), "heuristic"


def log_token_usage(tool: str, input_text: str, output_text: str) -> None:
    """Record token usage to .tool-tokens.json."""
    try:
        in_tokens, provider = _count_tokens(input_text)
        out_tokens, _ = _count_tokens(output_text)
        entry = {
            "tool": tool,
            "timestamp": datetime.now(timezone.utc).isoformat()[:19] + "Z",
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "total_tokens": in_tokens + out_tokens,
            "provider": provider,
        }
        tkf = tokens_file()
        tkf.parent.mkdir(parents=True, exist_ok=True)
        if tkf.exists():
            try:
                entries: List[Dict] = json.loads(tkf.read_text(encoding="utf-8"))
                if not isinstance(entries, list):
                    entries = []
            except Exception:
                entries = []
        else:
            entries = []
        entries.append(entry)
        if len(entries) > TOKENS_MAX_ENTRIES:
            entries = entries[-TOKENS_MAX_ENTRIES:]
        tkf.write_text(
            json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass
