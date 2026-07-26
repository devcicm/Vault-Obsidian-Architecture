"""scheduler — modelo de recursos y planificación de ejecución concurrente.

El problema: ejecutar N operaciones a la vez sin perder escrituras ni dejar
notas a medias. La solución NO es un lock global (serializa todo y anula la
concurrencia) ni confiar en que cada tool se proteja sola (no todas lo hacen).

Modelo de tres niveles de recurso:

  EXCLUSIVE  — la nota concreta y su carpeta contenedora.
               Dos escrituras sobre `01_Projects/api` chocan porque ambas
               regeneran `01_Projects/api/index.md` (lo dispara
               `vault_io.atomic_write_text` → `_auto_section_index`).
               Se serializan.

  GUARDED    — artefactos compartidos (graph.json, search-index.json,
               .change-log.json…). Sus escritores usan `vault_io.file_lock`
               + escritura atómica, así que toleran concurrencia. Se registran
               en el plan pero NO serializan.
               `cli scan --races` verifica que esa premisa se mantenga: si
               alguien escribe uno de estos sin lock, la garantía se rompe.

  GLOBAL     — operaciones que tocan el vault entero (backup, restore,
               reindex, migraciones). Corren solas, sin nada en paralelo.

Con eso el planificador agrupa las operaciones en OLAS: dentro de una ola nada
comparte recurso exclusivo, así que puede correr en paralelo con seguridad;
entre olas hay una barrera.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .registry import GUARDED_ARTIFACTS, Fragment, resolve

# Tools cuyo alcance es el vault completo: no admiten nada en paralelo.
# Un backup concurrente con una escritura produce un snapshot inconsistente;
# un restore concurrente con cualquier cosa es corrupción directa.
GLOBAL_SCOPE_TOOLS = frozenset({
    "vault_backup", "vault_restore", "vault_backup_base64", "vault_restore_base64",
    "vault_reindex", "vault_master_index", "vault_migrate_docs",
    "vault_migrate_rollback", "vault_standard_upgrade", "vault_init",
    "vault_merge", "vault_graph_merge", "vault_propagate", "vault_move",
})

_SLUG_STRIP = re.compile(r"[^\w\s-]", re.UNICODE)
_SLUG_SPACE = re.compile(r"[-\s]+")


def slug(text: str) -> str:
    """Normaliza un título a una clave de recurso estable.

    No pretende reproducir el nombre de archivo exacto que genera cada tool —
    solo agrupar de forma consistente. Ante la duda agrupa de más (serializa),
    nunca de menos.
    """
    value = _SLUG_STRIP.sub("", str(text).lower().strip())
    return _SLUG_SPACE.sub("-", value).strip("-") or "sin-titulo"


@dataclass
class Operation:
    """Una invocación concreta de un fragmento."""

    tool: str
    args: Dict[str, Any] = field(default_factory=dict)
    id: str = ""
    # Artefactos que se han verificado como NO protegidos por lock. Se rellena
    # desde analyzer.unsafe_artifacts(): la concurrencia sobre un artefacto
    # compartido se concede por verificación, no por declaración.
    unsafe: Set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not self.id:
            self.id = self.tool

    @property
    def fragment(self) -> Optional[Fragment]:
        return resolve(self.tool)

    def resources(self) -> Dict[str, Set[str]]:
        """Recursos que la operación toca, por nivel."""
        frag = self.fragment
        exclusive: Set[str] = set()
        guarded: Set[str] = set()

        if frag is None:
            # Fragmento desconocido: se asume lo peor.
            return {"exclusive": {"*"}, "guarded": set(), "global": {"unknown-tool"}}

        if self.tool in GLOBAL_SCOPE_TOOLS:
            return {"exclusive": set(), "guarded": set(), "global": {self.tool}}

        if frag.mode == "read":
            return {"exclusive": set(), "guarded": set(), "global": set()}

        folder = self.args.get("folder") or self.args.get("path")
        title = self.args.get("title") or self.args.get("name")

        if folder:
            norm = str(folder).replace("\\", "/").strip("/")
            # La carpeta es exclusiva: su index.md se regenera en cada escritura.
            exclusive.add(f"folder:{norm}")
            if title:
                exclusive.add(f"note:{norm}/{slug(title)}")
        elif frag.mode == "write":
            # Escritura sin destino identificable: no se puede acotar el
            # alcance, así que se trata como global. Serializar de más es
            # lento; serializar de menos corrompe.
            return {"exclusive": set(), "guarded": set(), "global": {self.tool}}

        for artifact in frag.touched_artifacts:
            if artifact in GUARDED_ARTIFACTS and artifact not in self.unsafe:
                guarded.add(artifact)
            else:
                # Sin lock verificado, dos escrituras simultáneas pierden una.
                exclusive.add(artifact)

        return {"exclusive": exclusive, "guarded": guarded, "global": set()}

    def to_dict(self) -> Dict[str, Any]:
        res = self.resources()
        return {
            "id": self.id,
            "tool": self.tool,
            "args": self.args,
            "mode": self.fragment.mode if self.fragment else "unknown",
            "resources": {k: sorted(v) for k, v in res.items()},
        }


def harden(operations: List[Operation]) -> Dict[str, List[str]]:
    """Verifica los artefactos compartidos del lote y endurece el plan.

    Marca en cada operación los artefactos que el escáner demuestra que se
    escriben sin lock. A partir de ahí el planificador los serializa. Devuelve
    el mapa artefacto → scripts culpables, para poder explicar por qué el lote
    corre con menos paralelismo del esperado.
    """
    from .analyzer import unsafe_artifacts

    tools = sorted({op.tool for op in operations})
    unsafe = unsafe_artifacts(tools)
    for op in operations:
        op.unsafe = set(unsafe)
    return unsafe


def conflicts(a: Operation, b: Operation) -> List[str]:
    """Recursos exclusivos que dos operaciones comparten."""
    ra, rb = a.resources(), b.resources()
    if ra["global"] or rb["global"]:
        return ["<vault completo>"]
    shared = ra["exclusive"] & rb["exclusive"]
    if "*" in ra["exclusive"] or "*" in rb["exclusive"]:
        return ["<alcance desconocido>"]
    return sorted(shared)


@dataclass
class Wave:
    """Conjunto de operaciones que pueden correr simultáneamente."""

    index: int
    operations: List[Operation] = field(default_factory=list)
    isolated: bool = False   # True → alcance global, corre sola

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wave": self.index,
            "isolated": self.isolated,
            "size": len(self.operations),
            "operations": [op.to_dict() for op in self.operations],
        }


def plan(operations: List[Operation], *, max_parallel: int = 4) -> List[Wave]:
    """Agrupa las operaciones en olas sin conflicto interno.

    Preserva el orden relativo: una operación nunca se adelanta a otra con la
    que comparte recurso. Es un empaquetado voraz, no un óptimo — pero es
    determinista, y la reproducibilidad importa más que el último 5% de
    paralelismo cuando lo que está en juego es la integridad de las notas.
    """
    waves: List[Wave] = []
    pending = list(operations)

    while pending:
        wave = Wave(index=len(waves) + 1)
        rest: List[Operation] = []

        for pos, op in enumerate(pending):
            if op.resources()["global"]:
                if not wave.operations:
                    # Va sola y todo lo posterior espera a la siguiente ola.
                    wave.operations.append(op)
                    wave.isolated = True
                    rest.extend(pending[pos + 1:])
                    break
                rest.append(op)
                continue

            if len(wave.operations) >= max_parallel:
                rest.append(op)
                continue

            if any(conflicts(op, placed) for placed in wave.operations):
                rest.append(op)
                continue

            # No basta con no chocar con la ola: no debe adelantarse a una
            # operación ANTERIOR que quedó fuera y con la que sí choca —
            # eso reordenaría escrituras sobre el mismo recurso.
            if any(conflicts(op, held) for held in rest):
                rest.append(op)
                continue

            wave.operations.append(op)

        if not wave.operations:  # defensa: nunca dejar el bucle sin progreso
            wave.operations.append(rest.pop(0))

        waves.append(wave)
        pending = rest

    return waves


def explain(operations: List[Operation]) -> Dict[str, Any]:
    """Plan legible: olas, paralelismo alcanzado y por qué se serializó algo."""
    waves = plan(operations)
    reasons: List[Dict[str, Any]] = []
    for i, a in enumerate(operations):
        for b in operations[i + 1:]:
            shared = conflicts(a, b)
            if shared:
                reasons.append({
                    "a": a.id, "b": b.id, "serialized_by": shared,
                })
    return {
        "operations": len(operations),
        "waves": [w.to_dict() for w in waves],
        "wave_count": len(waves),
        "max_wave_size": max((len(w.operations) for w in waves), default=0),
        "serialization_reasons": reasons,
    }


# Secciones que gestionan sus propios índices — espejo de
# vault_io._SKIP_AUTO_INDEX. Escribir dentro de ellas no dispara la cascada.
_NO_CASCADE = frozenset({"00_System", "99_Index", ".history", "vault-backups", "docs"})


def cascaded_indexes(folder: str, vault_root: Path) -> Set[str]:
    """`index.md` que se regeneran al escribir una nota en `folder`.

    `vault_io.atomic_write_text` llama a `_auto_section_index`, que invoca
    `vault_section_index(<sección>)` — y ese regenera el índice de la sección
    Y el de cada subcarpeta inmediata, no solo el de la carpeta escrita. Sin
    modelar esa cascada, la verificación de integridad reporta como cambio
    inesperado algo que es comportamiento declarado del estándar.
    """
    norm = str(folder).replace("\\", "/").strip("/")
    if not norm:
        return set()
    section = norm.split("/")[0]
    if section in _NO_CASCADE:
        return set()

    out = {f"{section}/index.md", f"{norm}/index.md"}
    section_path = vault_root / section
    if section_path.is_dir():
        for sub in section_path.iterdir():
            if sub.is_dir() and not sub.name.startswith("."):
                out.add(f"{section}/{sub.name}/index.md")
    return out


def declared_targets(operations: List[Operation], vault_root: Path) -> Set[str]:
    """Rutas que el plan dice que va a tocar. Se contrasta con lo que cambió."""
    targets: Set[str] = set()
    for op in operations:
        res = op.resources()
        if res["global"]:
            return {"*"}
        for item in res["exclusive"] | res["guarded"]:
            if item.startswith("folder:"):
                folder = item[len("folder:"):]
                targets.add(folder)
                targets |= cascaded_indexes(folder, vault_root)
            elif item.startswith("note:"):
                targets.add(item[len("note:"):])
            else:
                targets.add(item)
    return targets
