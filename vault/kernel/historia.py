"""El historial de una nota: un solo criterio para escribirlo y leerlo en todos los modos.

Hasta v41.2 lo decidían cuatro sitios a su manera. `vault_undo` filtraba por el
prefijo `carpeta__stem-` y ordenaba por mtime, `vault_read` por una subcadena
del stem, `vault_diff` por prefijo con orden alfabético, y `vault_history_compact`
era el único que lo parseaba.

Forma de snapshots: `{carpeta con / → __}__{stem}-{AAAA-MM-DDTHH-MM-SS}[-{n}].md`.
Forma de deltas (modo `diff`): `{carpeta con / → __}__{stem}.patches.jsonl`,
append-only con base inicial + operaciones exactas (`difflib.SequenceMatcher`)
verificadas por SHA-256.
Forma de git (modo `git` / `auto`): commits de la nota leídos vía `vault.kernel.vcs`.

`linea_temporal` une los tres backends en orden cronológico (más reciente primero)
para que cambiar de modo (`snapshots` ↔ `diff` ↔ `git` ↔ `auto`) nunca pierda
versiones previas ni rompa `vault_diff`, `vault_undo` ni `AP-75`.

Hoja del núcleo: solo stdlib + `vault.kernel.vcs`.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

from vault.kernel import vcs

#: Formato del sello de tiempo, sin `:` para que el nombre valga en Windows.
FORMATO = "%Y-%m-%dT%H-%M-%S"

#: Modos de historial declarables en `00_System/reglas.json` (dueño único, AP-57).
MODOS_DE_HISTORIAL: Tuple[str, ...] = ("snapshots", "git", "diff", "auto")

#: El sello y la secuencia opcional al final del nombre sin extensión.
_PATRON = re.compile(r"-(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})(?:-(\d+))?$")

_PRIORIDAD_ORIGEN = {"snapshots": 0, "diff": 1, "git": 2}


def clave(rel: str) -> str:
    """El stem con el que se guardan las versiones de la nota `rel` (POSIX)."""
    p = PurePosixPath(rel.replace("\\", "/"))
    return f"{p.parent.as_posix().replace('/', '__')}__{p.stem}"


def archivo_patches(dir_historial: Path, rel: str) -> Path:
    """Ruta del registro incremental `.patches.jsonl` para la nota `rel`."""
    return Path(dir_historial) / f"{clave(rel)}.patches.jsonl"


def parsear(nombre: str) -> Dict[str, Any]:
    """`{stem, timestamp, timestamp_str, secuencia}` de un nombre de `.history/`.

    Un nombre sin sello sale con `timestamp: None` y el nombre entero como stem:
    no es una versión de ninguna nota con sello, y fingirle uno sería inventar.
    """
    sin_ext = nombre[:-3] if nombre.endswith(".md") else nombre
    m = _PATRON.search(sin_ext)
    if m:
        try:
            ts: Optional[datetime] = datetime.strptime(
                m.group(1), FORMATO).replace(tzinfo=timezone.utc)
        except ValueError:
            ts = None
        return {"stem": sin_ext[:m.start()], "timestamp": ts,
                "timestamp_str": m.group(1), "secuencia": int(m.group(2) or 0)}
    return {"stem": sin_ext, "timestamp": None, "timestamp_str": "", "secuencia": 0}


def nombre_libre(dir_historial: Path, rel: str,
                 ahora: Optional[datetime] = None) -> Path:
    """La ruta donde guardar ahora una versión de `rel` sin pisar otra."""
    sello = (ahora or datetime.now(timezone.utc)).strftime(FORMATO)
    base = f"{clave(rel)}-{sello}"
    destino = dir_historial / f"{base}.md"
    n = 1
    while destino.exists():
        destino = dir_historial / f"{base}-{n}.md"
        n += 1
    return destino


def versiones(dir_historial: Path, rel: str) -> List[Dict[str, Any]]:
    """Las versiones snapshot (`.history/*.md`) de `rel`, de la más reciente a la más vieja.

    Se compara el stem parseado entero, no un prefijo, y se ordena por el sello
    del nombre y no por mtime: copiar `.history/` a otra máquina conserva el
    nombre pero no siempre la fecha del fichero.
    """
    if not dir_historial.is_dir():
        return []
    buscada = clave(rel)
    salida: List[Dict[str, Any]] = []
    for f in dir_historial.iterdir():
        if not f.is_file() or not f.name.endswith(".md"):
            continue
        meta = parsear(f.name)
        if meta["stem"] != buscada or meta["timestamp"] is None:
            continue
        salida.append({"filename": f.name, "path": f, "origen": "snapshots", **meta})
    salida.sort(key=lambda v: (v["timestamp"], v["secuencia"]), reverse=True)
    return salida


# ── Backend incremental `diff` (.history/<clave>.patches.jsonl) ──────────────

def _sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _calcular_ops(previo: str, nuevo: str) -> List[List[Any]]:
    """Operaciones exactas (`e` = slice igual de `previo`, `i` = líneas nuevas)."""
    a = previo.splitlines(keepends=True)
    b = nuevo.splitlines(keepends=True)
    ops: List[List[Any]] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            ops.append(["e", i1, i2])
        elif tag in ("replace", "insert"):
            ops.append(["i", b[j1:j2]])
    return ops


def _aplicar_ops(previo: str, ops: List[List[Any]]) -> str:
    a = previo.splitlines(keepends=True)
    out: List[str] = []
    for op in ops:
        if not op:
            continue
        if op[0] == "e":
            out.extend(a[op[1]:op[2]])
        elif op[0] == "i":
            out.extend(op[1])
    return "".join(out)


def _leer_entradas_patches(fichero: Path) -> List[Dict[str, Any]]:
    """Reconstruye en orden cronológico (más vieja → más nueva) las versiones de `.patches.jsonl`."""
    if not fichero.is_file():
        return []
    reconstruidas: List[Dict[str, Any]] = []
    texto_actual = ""
    try:
        lineas = fichero.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for linea in lineas:
        if not linea.strip():
            continue
        try:
            obj = json.loads(linea)
        except ValueError:
            continue
        if not isinstance(obj, dict):
            continue
        kind = obj.get("kind")
        if kind == "base":
            texto = str(obj.get("text") or "")
        elif kind == "patch":
            ops = obj.get("ops")
            if not isinstance(ops, list):
                continue
            texto = _aplicar_ops(texto_actual, ops)
        else:
            continue
        esperado = obj.get("sha256")
        if isinstance(esperado, str) and esperado and _sha256(texto) != esperado:
            # Si una línea sufrió corrupción, no inventar contenido: detener la cadena aquí.
            break
        texto_actual = texto
        ts_str = str(obj.get("timestamp") or "")
        try:
            # Python 3.10: `fromisoformat` no acepta sufijo literal `Z` (añadido en 3.11).
            ts_norm = f"{ts_str[:-1]}+00:00" if ts_str.endswith("Z") else ts_str
            ts = datetime.fromisoformat(ts_norm).astimezone(timezone.utc) if ts_norm else None
        except ValueError:
            ts = None
        reconstruidas.append({
            "seq": int(obj.get("seq", len(reconstruidas))),
            "timestamp": ts,
            "timestamp_str": ts_str,
            "sha256": _sha256(texto),
            "content": texto,
        })
    return reconstruidas


def anexar_patch(
    dir_historial: Path,
    rel: str,
    contenido: str,
    ahora: Optional[datetime] = None,
) -> str:
    """Anexa `contenido` al registro incremental `.patches.jsonl` y devuelve su ID.

    Si es la primera versión, almacena una entrada `base`; las siguientes almacenan
    solo el delta (`ops`) contra la última versión registrada, reduciendo el coste
    de almacenamiento de O(versiones × tamaño) a O(tamaño + Σ deltas).
    """
    dir_historial = Path(dir_historial)
    dir_historial.mkdir(parents=True, exist_ok=True)
    fichero = archivo_patches(dir_historial, rel)
    previas = _leer_entradas_patches(fichero)
    digest = _sha256(contenido)
    key = clave(rel)

    if previas and previas[-1]["sha256"] == digest:
        return f"diff:{key}#{previas[-1]['seq']}"

    ts = (ahora or datetime.now(timezone.utc)).isoformat()
    seq = (previas[-1]["seq"] + 1) if previas else 0
    if not previas:
        entrada: Dict[str, Any] = {
            "seq": seq,
            "kind": "base",
            "timestamp": ts,
            "sha256": digest,
            "text": contenido,
        }
    else:
        ops = _calcular_ops(previas[-1]["content"], contenido)
        entrada = {
            "seq": seq,
            "kind": "patch",
            "timestamp": ts,
            "sha256": digest,
            "ops": ops,
        }

    linea = json.dumps(entrada, ensure_ascii=False) + "\n"
    fd = os.open(str(fichero), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o666)
    try:
        os.write(fd, linea.encode("utf-8"))
    finally:
        os.close(fd)
    return f"diff:{key}#{seq}"


def versiones_diff(dir_historial: Path, rel: str) -> List[Dict[str, Any]]:
    """Las versiones almacenadas en `.patches.jsonl` de `rel`, de más reciente a más vieja."""
    fichero = archivo_patches(dir_historial, rel)
    entradas = _leer_entradas_patches(fichero)
    key = clave(rel)
    salida: List[Dict[str, Any]] = []
    for e in reversed(entradas):
        salida.append({
            "filename": f"diff:{key}#{e['seq']}",
            "path": fichero,
            "origen": "diff",
            "stem": key,
            "timestamp": e["timestamp"],
            "timestamp_str": e["timestamp_str"],
            "secuencia": e["seq"],
            "seq": e["seq"],
            "sha256": e["sha256"],
            "size_bytes": len(e["content"].encode("utf-8")),
            "_content": e["content"],
        })
    return salida


def versiones_git(raiz: Path, rel: str, limite: int = 100) -> List[Dict[str, Any]]:
    """Las versiones git de `rel`, de más reciente a más vieja."""
    key = clave(rel)
    brutas = vcs.versiones_de_nota(Path(raiz), rel, limite=limite)
    total = len(brutas)
    salida: List[Dict[str, Any]] = []
    for idx, item in enumerate(brutas):
        sha = item["sha"]
        salida.append({
            "filename": f"git:{sha[:12]}",
            "sha": sha,
            "origen": "git",
            "stem": key,
            "timestamp": item["timestamp"],
            "timestamp_str": item["timestamp_str"],
            "secuencia": total - idx,
            "mensaje": item.get("mensaje", ""),
        })
    return salida


# ── Lector unificado multi-backend ───────────────────────────────────────────

def _clave_orden(entrada: Dict[str, Any]) -> Tuple[datetime, int, int]:
    ts = entrada.get("timestamp")
    if isinstance(ts, datetime):
        ts_sec = ts.astimezone(timezone.utc).replace(microsecond=0)
    else:
        ts_sec = datetime.min.replace(tzinfo=timezone.utc)
    prio = _PRIORIDAD_ORIGEN.get(str(entrada.get("origen") or ""), 0)
    seq = int(entrada.get("secuencia") or 0)
    return (ts_sec, prio, seq)


def linea_temporal(
    raiz: Path,
    rel: str,
    dir_historial: Optional[Path] = None,
    limite_git: int = 100,
) -> List[Dict[str, Any]]:
    """Une snapshots (`.history/*.md`), deltas (`.patches.jsonl`) y commits git.

    Devuelve la línea temporal completa de `rel`, de la versión más reciente a la
    más antigua. Cambiar de modo de historial nunca oculta ni pierde versiones
    escritas bajo otro backend.
    """
    raiz = Path(raiz)
    hist_dir = Path(dir_historial) if dir_historial is not None else (raiz / ".history")
    rel_posix = str(rel).replace("\\", "/").lstrip("./")

    combinadas: List[Dict[str, Any]] = []
    combinadas.extend(versiones(hist_dir, rel_posix))
    combinadas.extend(versiones_diff(hist_dir, rel_posix))
    if vcs.hay_repo(raiz):
        combinadas.extend(versiones_git(raiz, rel_posix, limite=limite_git))

    combinadas.sort(key=_clave_orden, reverse=True)
    return combinadas


def contenido_de_version(
    raiz: Path,
    rel: str,
    entrada: Dict[str, Any],
    dir_historial: Optional[Path] = None,
) -> Optional[str]:
    """Recupera el texto exacto de una entrada devuelta por `linea_temporal`."""
    origen = entrada.get("origen")
    if origen == "diff":
        if "_content" in entrada:
            return str(entrada["_content"])
        hist_dir = Path(dir_historial) if dir_historial is not None else (Path(raiz) / ".history")
        for v in versiones_diff(hist_dir, rel):
            if v["filename"] == entrada.get("filename"):
                return str(v["_content"])
        return None
    if origen == "git":
        sha = str(entrada.get("sha") or "")
        if not sha:
            return None
        return vcs.contenido_en_commit(Path(raiz), sha, rel)
    # snapshots (por defecto)
    ruta = entrada.get("path")
    if ruta is None:
        hist_dir = Path(dir_historial) if dir_historial is not None else (Path(raiz) / ".history")
        ruta = hist_dir / str(entrada.get("filename") or "")
    ruta = Path(ruta)
    if not ruta.is_file():
        return None
    try:
        return ruta.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
