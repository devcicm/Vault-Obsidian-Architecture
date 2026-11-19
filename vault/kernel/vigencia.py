"""Whether a note is current truth or history: one rule for every reader.

The context pack (`vault_context_pack`) and the search (`vault_search`) both
leave history out of what they answer, and both weigh a note that is no longer
current. Before this module the rule lived inside the context pack, and the
search could not use it without importing the whole pack (+229 ms per call,
measured 2026-11-19). Here it costs dictionary lookups: the canonical status is
computed once, when the search index row is built (`ciclo_de_vida`), and the
status normalizer is imported only when a reader holds a raw status.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

# superseded_by: PENALIZACION_POR_STATUS + penalizacion() (2026-10-07). It was a
# copied vocabulary: `superseded` and `revoked` are not in STATUS_VOCAB and
# `obsolete`, which is, weighed nothing. Kept as the reading of the raw value a
# legacy vault may carry.
STATUS_PENALTY: Dict[str, float] = {
    "deprecated": 0.4, "superseded": 0.3, "revoked": 0.2, "archived": 0.5,
}

# Keys of the canonical vocabulary, normalized by its owner (`normalize_status`).
# `obsolete` weighs as `deprecated`: the vocabulary does not tell them apart.
PENALIZACION_POR_STATUS: Dict[str, float] = {
    "deprecated": 0.4, "obsolete": 0.4, "archived": 0.5,
}

#: Sentinel: "the caller did not normalize the status; normalize it here".
_SIN_CANONICO = object()


def _canonico(crudo: str) -> Optional[str]:
    from .normativa.norms_catalog import normalize_status

    return normalize_status(crudo)[0]


def ciclo_de_vida(meta: Mapping[str, Any]) -> Dict[str, Optional[str]]:
    """What the rule reads from a note's frontmatter, with the status normalized.

    Stored in each search-index row by its builder, so a reader decides
    current or history without reading the note or loading the normalizer.
    """
    meta = meta or {}
    crudo = str(meta.get("status") or "").strip().lower()
    return {
        "status": crudo or None,
        "status_canonical": _canonico(crudo) if crudo else None,
        "type": str(meta.get("type") or "").strip().lower() or None,
        "superseded_by": str(meta.get("superseded_by") or "").strip() or None,
    }


def penalizacion(frontmatter: Mapping[str, Any], canonico: Any = _SIN_CANONICO) -> float:
    """Rerank factor for a note that is no longer the current one (AP-17).

    A note annotated with `superseded_by:` (what healing writes instead of
    deleting the twin) weighs as `superseded`: without this the annotation
    changed nothing and the twin competed on equal terms with its canonical
    note. The `status` is read normalized by its owner; if it is not canonical,
    by its raw value. `canonico` is the already normalized status, when the
    caller has it (a search-index row).
    """
    frontmatter = frontmatter or {}
    factores = []
    if str(frontmatter.get("superseded_by") or "").strip():
        factores.append(STATUS_PENALTY["superseded"])
    crudo = str(frontmatter.get("status") or "").strip().lower()
    if crudo:
        if canonico is _SIN_CANONICO:
            canonico = _canonico(crudo)
        factor = PENALIZACION_POR_STATUS.get(canonico) or STATUS_PENALTY.get(crudo)
        if factor:
            factores.append(factor)
    return min(factores, default=1.0)


def motivo_historico(rel: str, frontmatter: Mapping[str, Any],
                     canonico: Any = _SIN_CANONICO) -> Optional[str]:
    """Why a note is history rather than current truth, or `None` (S4, bigo).

    Each class is decided by its owner, never by a list copied here:

    - `quarantine`: the note lives in the section the registry declares for the
      `quarantine` type (`vault.kernel.registry.SECTION_TYPES`; the folder that
      `vault.durabilidad.cuarentena` writes), held "without a safe destination"
      (unknown origin, suspected injection); that module says a doubtful copy
      must not be read as valid context. Read from the kernel registry, not from
      `vault.durabilidad`, so readers gain no dependency on `durabilidad`.
    - `archived_source`: `vault.kernel.contenido.es_fuente_archivada` (AP-73),
      the raw source kept verbatim; the compiled knowledge lives elsewhere.
    - `superseded`: the note carries `superseded_by:`, the decision of which
      note rules (AP-17).
    - otherwise the status the rerank already treats as "no longer current"
      (`penalizacion() < 1.0`): `deprecated`, `obsolete`, `archived` and the
      legacy raw `superseded`/`revoked`, reported by that status.
    """
    from .contenido import es_fuente_archivada

    rel = str(rel).replace("\\", "/")
    frontmatter = frontmatter or {}
    if es_seccion_historica(rel):
        return "quarantine"
    if es_fuente_archivada(rel, frontmatter):
        return "archived_source"
    if str(frontmatter.get("superseded_by") or "").strip():
        return "superseded"
    crudo = str(frontmatter.get("status") or "").strip().lower()
    if crudo and canonico is _SIN_CANONICO:
        canonico = _canonico(crudo)
    if penalizacion(frontmatter, canonico) < 1.0:
        return canonico if canonico in PENALIZACION_POR_STATUS else crudo
    return None


def es_seccion_historica(rel: str) -> bool:
    """`rel` lies in the section the registry declares for quarantined copies."""
    from .registry import SECTION_TYPES

    rel = str(rel).replace("\\", "/").strip("/") + "/"
    return any(rel.startswith(seccion + "/") for seccion, tipos in SECTION_TYPES.items()
               if "quarantine" in tipos)


def motivo_de_fila(fila: Mapping[str, Any]) -> Any:
    """The reason a search-index row is history, `None`, or `KeyError` when the
    row predates `lifecycle` (the caller then reads the note)."""
    vida = fila.get("lifecycle")
    if not isinstance(vida, Mapping):
        raise KeyError("lifecycle")
    frontmatter = {"status": vida.get("status"), "type": vida.get("type"),
                   "superseded_by": vida.get("superseded_by")}
    return motivo_historico(str(fila.get("path", "")), frontmatter, vida.get("status_canonical"))
