#!/usr/bin/env python3
"""
vault_voice.py — AP-43: el vault le habla al agente en cada interacción.

Síntoma que origina la norma: las normas AP-XX/PAT-X/SP-XX/CN-XX existen, están
catalogadas y tienen guards, pero el agente que documenta el vault **no las
tiene en contexto** mientras trabaja. Se entera de que una norma existe cuando
la incumple y algo falla — si es que falla, porque 33 de 53 normas solo
*detectan* en un audit que nadie corre. El refuerzo llega tarde o no llega.

La respuesta no es otro registro (este repo ya tiene el fallo de declarar cosas
que nadie consume): es enganchar el recordatorio al **único punto por el que ya
pasa la salida de todas las tools**, `vault_errors.wrap_main`. Cada llamada
devuelve, además de su resultado, un bloque `vault_says` derivado de
`vault_norms.NORM_CATALOG` — registro canónico, leído, nunca duplicado — y del
estado real de esa llamada (qué escribió, qué norma la frenó).

Control:
    VAULT_VOICE=0          silencia el bloque
    VAULT_VOICE=verbose    incluye descripción y señal de cada norma

CLI:
    python vault_voice.py --tool vault_write
    python vault_voice.py --coverage
"""

import json
import os
import sys
from functools import lru_cache
from typing import Any, Dict, List, Optional

# Frase de apertura por tipo de momento. El vault habla en primera persona:
# lo que se refuerza no es una regla abstracta, es lo que acaba de pasar aquí.
_APERTURA = {
    "blocked": "Te frené a propósito.",
    "wrote": "Acabas de cambiar lo que soy.",
    "read": "Nada cambió en mí con esta llamada.",
}


@lru_cache(maxsize=1)
def _catalog() -> List[Dict[str, Any]]:
    try:
        from vault_norms import NORM_CATALOG

        return list(NORM_CATALOG)
    except Exception:
        return []


def _menciona(entrada: Any, tool: str) -> bool:
    """`tools_enforcing` guarda a veces 'vault_write' y a veces 'vault_write --fix'."""
    return any(str(t).split()[0] == tool for t in (entrada or []))


@lru_cache(maxsize=256)
def norms_for_tool(tool: str) -> List[Dict[str, Any]]:
    """Normas que gobiernan una tool, primero las que la tool aplica ella misma."""
    aplica, detecta = [], []
    for norma in _catalog():
        if _menciona(norma.get("tools_enforcing"), tool):
            aplica.append(norma)
        elif _menciona(norma.get("tools_detecting"), tool):
            detecta.append(norma)
    orden = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    clave = lambda n: (orden.get(n.get("severity"), 9), n["code"])  # noqa: E731
    return sorted(aplica, key=clave) + sorted(detecta, key=clave)


def _norma(codigo: str) -> Optional[Dict[str, Any]]:
    return next((n for n in _catalog() if n.get("code") == codigo), None)


def _etiqueta(norma: Dict[str, Any]) -> str:
    return f"{norma['code']} — {norma['name']}"


def speak(
    tool: str,
    payload: Optional[Dict[str, Any]] = None,
    writes: Optional[Dict[str, int]] = None,
) -> Optional[Dict[str, Any]]:
    """Bloque `vault_says` para una llamada concreta. `None` si no hay nada que decir.

    `payload` es el JSON que la tool ya devolvía; `writes` es el reporte del
    ledger AP-37 capturado en el hilo donde corrió la tool (es thread-local: si
    se lee desde el hilo principal siempre da cero).
    """
    if os.environ.get("VAULT_VOICE", "1") == "0":
        return None
    normas = norms_for_tool(tool)
    payload = payload if isinstance(payload, dict) else {}
    escritas = int((writes or {}).get("written", 0))

    codigo_bloqueo = payload.get("norm_code")
    if codigo_bloqueo and payload.get("ok") is False:
        momento = "blocked"
    elif escritas:
        momento = "wrote"
    else:
        momento = "read"

    # La norma que se refuerza: la que acaba de actuar si hubo una; si no, se
    # rota por el número de llamada para que el agente no vea siempre la misma.
    foco = _norma(codigo_bloqueo) if codigo_bloqueo else None
    if foco is None and normas:
        foco = normas[_rotacion() % len(normas)]
    if foco is None and not normas:
        return None

    partes = [_APERTURA[momento]]
    if momento == "blocked":
        partes.append(
            f"{_etiqueta(foco)}. No es un fallo de la tool: es la norma haciendo su trabajo."
        )
        if foco.get("prevention"):
            partes.append(foco["prevention"])
    elif momento == "wrote":
        plural = "notas" if escritas != 1 else "nota"
        partes.append(f"{escritas} {plural} en disco, y eso queda en mi historial.")
        partes.append(f"Recuerda {_etiqueta(foco)}: {foco.get('prevention') or foco.get('signal', '')}")
    else:
        partes.append(f"Mientras lees, ten presente {_etiqueta(foco)}.")
        if foco.get("signal"):
            partes.append(f"Señal de que se está incumpliendo: {foco['signal']}")

    bloque: Dict[str, Any] = {
        "moment": momento,
        "message": " ".join(p.strip() for p in partes if p and p.strip()),
        "focus": foco["code"],
        "norms": [_etiqueta(n) for n in normas],
        "next": _siguiente(momento, tool, foco),
    }
    if os.environ.get("VAULT_VOICE") == "verbose":
        bloque["detail"] = [
            {
                "code": n["code"],
                "name": n["name"],
                "severity": n.get("severity"),
                "enforcement": n.get("enforcement"),
                "description": n.get("description"),
                "signal": n.get("signal"),
                "prevention": n.get("prevention"),
            }
            for n in normas
        ]
    return bloque


def _siguiente(momento: str, tool: str, foco: Dict[str, Any]) -> str:
    if momento == "blocked":
        return f"python scripts/vault_norms.py --explain {foco['code']}"
    if momento == "wrote":
        return "python scripts/vault_norms.py --audit"
    return f"python scripts/vault_voice.py --tool {tool}"


def _rotacion() -> int:
    """Contador de llamadas persistido en el vault, para que el refuerzo rote.

    Vive DENTRO del vault (AP-36) y su fallo nunca es fatal: si no se puede
    escribir, la voz rota sobre el pid y se sigue hablando igual.
    """
    try:
        from vault_io import get_vault_root

        ruta = get_vault_root() / "00_System" / ".voice-counter"
        n = int(ruta.read_text(encoding="utf-8").strip() or 0) if ruta.is_file() else 0
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(str(n + 1), encoding="utf-8")
        return n
    except Exception:
        return os.getpid()


def coverage() -> Dict[str, Any]:
    """AP-43 — qué parte del catálogo llega alguna vez al agente por esta vía.

    Una norma que no está en `tools_enforcing` ni en `tools_detecting` de
    ninguna tool no se pronuncia nunca: es prosa, y esto la nombra.
    """
    try:
        from vault_mcp_catalog import TOOLS_CATALOG

        tools = sorted(TOOLS_CATALOG)
    except Exception:
        tools = []
    dichas = {n["code"] for t in tools for n in norms_for_tool(t)}
    todas = {n["code"] for n in _catalog()}
    mudas = sorted(todas - dichas)
    return {
        "ok": not mudas,
        "tool": "vault_voice",
        "action": "coverage",
        "norms_total": len(todas),
        "norms_spoken": len(dichas),
        "silent": mudas,
        "hint": "Una norma que ninguna tool nombra no llega nunca al agente: "
        "dale tools_enforcing o tools_detecting en vault_norms.NORM_CATALOG.",
    }


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="vault_voice — refuerzo de normas por interacción")
    p.add_argument("--tool", help="Normas que gobiernan una tool")
    p.add_argument("--coverage", action="store_true", help="Normas que ninguna tool pronuncia")
    args = p.parse_args()

    if args.coverage:
        print(json.dumps(coverage(), ensure_ascii=False, indent=2))
        return 0
    if args.tool:
        normas = norms_for_tool(args.tool)
        print(
            json.dumps(
                {
                    "ok": True,
                    "tool": "vault_voice",
                    "target": args.tool,
                    "count": len(normas),
                    "norms": [
                        {
                            "code": n["code"],
                            "name": n["name"],
                            "severity": n.get("severity"),
                            "enforcement": n.get("enforcement"),
                            "prevention": n.get("prevention"),
                        }
                        for n in normas
                    ],
                    "says": speak(args.tool),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
    from vault_errors import wrap_main

    sys.exit(wrap_main(main, "vault_voice"))
