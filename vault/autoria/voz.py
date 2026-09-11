"""Servicio de voz para los resultados de un runtime documental.

La voz es presentacion contextual del resultado de una operacion.  Esta capa
no conoce la CLI ``vault_voice``, su cobertura AP-43 ni el catalogo de tools
del estandar: recibe las normas y su orden desde el adaptador que conoce esos
registros.  Asi el emisor comun de envelopes puede hablar sin importar una
tool meta-estandar.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional


_APERTURA = {
    "blocked": "Te frené a propósito.",
    "wrote": "Acabas de cambiar lo que soy.",
    "read": "Nada cambió en mí con esta llamada.",
}


def menciona(entrada: Any, tool: str) -> bool:
    """Una referencia con flags sigue nombrando a su tool base."""
    return any(str(item).split()[0] == tool for item in (entrada or []))


def norms_for_tool(
    tool: str,
    catalog: Iterable[Mapping[str, Any]],
    severity_order: Mapping[str, int],
) -> List[Dict[str, Any]]:
    """Selecciona las normas de una tool desde los registros canónicos dados."""
    aplica: List[Dict[str, Any]] = []
    detecta: List[Dict[str, Any]] = []
    for entrada in catalog:
        norma = dict(entrada)
        if menciona(norma.get("tools_enforcing"), tool):
            aplica.append(norma)
        elif menciona(norma.get("tools_detecting"), tool):
            detecta.append(norma)
        elif menciona(norma.get("tools_del_patron"), tool):
            detecta.append(norma)
    clave = lambda norma: (severity_order.get(norma.get("severity"), 9), norma["code"])
    return sorted(aplica, key=clave) + sorted(detecta, key=clave)


def rotacion(runtime_root: Optional[Path]) -> int:
    """Obtiene y avanza el contador persistente de voz dentro del runtime.

    El contador es deliberadamente best-effort: la voz no puede convertir una
    respuesta correcta en un error solo porque el runtime no permita escribir
    este detalle de presentacion.
    """
    try:
        if runtime_root is None:
            raise OSError("runtime root unavailable")
        ruta = Path(runtime_root) / "00_System" / ".voice-counter"
        numero = int(ruta.read_text(encoding="utf-8").strip() or 0) if ruta.is_file() else 0
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(str(numero + 1), encoding="utf-8")
        return numero
    except Exception:
        return os.getpid()


def _catalogo_runtime() -> Iterable[Mapping[str, Any]]:
    """Carga la hoja canónica sólo cuando el adaptador no inyectó el dato."""
    from vault_norms_catalog import NORM_CATALOG

    return NORM_CATALOG


def _orden_severidad_runtime() -> Mapping[str, int]:
    """Carga el vocabulario canónico sólo cuando no fue inyectado."""
    from vault_vocabulario import rango

    return rango("severidad", base=0, mayor_primero=False)


def _root_runtime() -> Optional[Path]:
    """Consulta el root en su hoja dueña, sin pedir la fachada de IO.

    Un consumidor del paquete puede seguir pasando ``runtime_root``
    explícitamente. Esta rama conserva la persistencia histórica al ejecutar
    desde el checkout y falla de forma inocua si esa hoja no está disponible.
    """
    try:
        from vault_raiz import get_vault_root

        return get_vault_root()
    except (ImportError, OSError, RuntimeError):
        return None


def _norma(codigo: str, catalog: Iterable[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    return next((dict(n) for n in catalog if n.get("code") == codigo), None)


def _etiqueta(norma: Mapping[str, Any]) -> str:
    return f"{norma['code']} — {norma['name']}"


def _siguiente(momento: str, tool: str, foco: Mapping[str, Any]) -> str:
    if momento == "blocked":
        return f"python scripts/vault_norms.py --explain {foco['code']}"
    if momento == "wrote":
        return "python scripts/vault_norms.py --audit"
    return f"python scripts/vault_voice.py --tool {tool}"


def speak(
    tool: str,
    payload: Optional[Dict[str, Any]] = None,
    writes: Optional[Dict[str, int]] = None,
    *,
    catalog: Optional[Iterable[Mapping[str, Any]]] = None,
    severity_order: Optional[Mapping[str, int]] = None,
    runtime_root: Optional[Path] = None,
    voice_mode: Optional[str] = None,
    rotation: Optional[Callable[[], int]] = None,
) -> Optional[Dict[str, Any]]:
    """Construye ``vault_says`` sin depender de una fachada legacy.

    Los registros se inyectan en vez de importarse desde ``scripts/``.  El
    servicio puede por tanto importarse como paquete normal y el adaptador
    decide cuál es la fuente canónica aplicable al entorno donde se ejecuta.
    """
    if (voice_mode if voice_mode is not None else os.environ.get("VAULT_VOICE", "1")) == "0":
        return None

    catalogo = list(catalog if catalog is not None else _catalogo_runtime())
    severity_order = severity_order if severity_order is not None else _orden_severidad_runtime()
    runtime_root = runtime_root if runtime_root is not None else _root_runtime()
    normas = norms_for_tool(tool, catalogo, severity_order)
    datos = payload if isinstance(payload, dict) else {}
    escritas = int((writes or {}).get("written", 0))

    codigo_bloqueo = datos.get("norm_code")
    if codigo_bloqueo and datos.get("ok") is False:
        momento = "blocked"
    elif escritas:
        momento = "wrote"
    else:
        momento = "read"

    foco = _norma(codigo_bloqueo, catalogo) if codigo_bloqueo else None
    if foco is None and normas:
        siguiente = rotation() if rotation is not None else rotacion(runtime_root)
        foco = normas[siguiente % len(normas)]
    if foco is None:
        return None

    partes = [_APERTURA[momento]]
    if momento == "blocked":
        partes.append(
            f"{_etiqueta(foco)}. No es un fallo de la tool: es la norma haciendo su trabajo."
        )
        if foco.get("prevention"):
            partes.append(str(foco["prevention"]))
    elif momento == "wrote":
        plural = "notas" if escritas != 1 else "nota"
        partes.append(f"{escritas} {plural} en disco, y eso queda en mi historial.")
        partes.append(
            f"Recuerda {_etiqueta(foco)}: "
            f"{foco.get('prevention') or foco.get('signal', '')}"
        )
    else:
        partes.append(f"Mientras lees, ten presente {_etiqueta(foco)}.")
        if foco.get("signal"):
            partes.append(f"Señal de que se está incumpliendo: {foco['signal']}")

    bloque: Dict[str, Any] = {
        "moment": momento,
        "message": " ".join(parte.strip() for parte in partes if parte and parte.strip()),
        "focus": foco["code"],
        "norms": [_etiqueta(norma) for norma in normas],
        "next": _siguiente(momento, tool, foco),
    }
    if (voice_mode if voice_mode is not None else os.environ.get("VAULT_VOICE", "1")) == "verbose":
        bloque["detail"] = [
            {
                "code": norma["code"],
                "name": norma["name"],
                "severity": norma.get("severity"),
                "enforcement": norma.get("enforcement"),
                "description": norma.get("description"),
                "signal": norma.get("signal"),
                "prevention": norma.get("prevention"),
            }
            for norma in normas
        ]
    return bloque
