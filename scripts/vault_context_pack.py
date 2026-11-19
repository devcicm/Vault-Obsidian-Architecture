#!/usr/bin/env python3
"""
vault_context_pack.py — Pregunta → contexto empaquetado bajo presupuesto.

Es la pieza que faltaba en el eje consulta → contexto: el vault sabía escribir,
gobernar y auditar, pero devolver "lo que hay que saber para responder esto,
en N tokens" quedaba en manos del agente, sin criterio ni traza.

Encadena tools existentes, no las reimplementa:

    vault_query_parse  →  vault_search      (recuperación léxica)
                       →  vault_subgraph    (expansión por grafo)
                       →  rerank            (léxico + grafo + frescura + CIA)
                       →  packing           (Top-K bajo presupuesto de tokens)

Dos decisiones que explican el resto:

  - **El presupuesto se respeta recortando notas enteras, no partiéndolas.**
    Media nota en el contexto es peor que ninguna: el agente la cita como si
    estuviera completa. Lo que no cabe se reporta en `excluded` con su motivo.
  - **Las preferencias `must` entran siempre**, antes que cualquier resultado.
    Si el presupuesto obliga a elegir entre saber más del tema y saber qué le
    prohibió el usuario al agente, gana lo segundo. Si no caben íntegras con
    la cabecera, se devuelve INVALID_BUDGET sin entregar contexto parcial.

Usage:
    python vault_context_pack.py "que decidimos sobre el transporte MCP"
    python vault_context_pack.py "errores del proyecto ans" --budget 2000
    python vault_context_pack.py "auth" --format markdown --no-preferences
    python vault_context_pack.py "mcp" --explain
    python vault_context_pack.py "mcp" --incluir-historico
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from vault_errors import emit_error, mensaje_de, wrap_main
from vault_lib import parse_frontmatter_with_body
from vault_query_parse import vault_query_parse
from vault_search import vault_search
from vault_subgraph import vault_subgraph
from vault_token_service import estimate_tokens

FLOOR_BUDGET = 2000
DEFAULT_BUDGET = FLOOR_BUDGET
DEFAULT_TOP_K = 12
DEFAULT_EXCERPT_TOKENS = 350

# Pesos del rerank. Suman 1.0 a propósito: así `score` es comparable entre
# consultas y un umbral fijo significa lo mismo siempre.
#
# **Declarados, no calibrados** (propuesta `compact-agent-memory-weights`):
# son una decisión de diseño, no un resultado medido. El envelope los publica
# junto a esta frase para que nadie los lea como óptimos; calibrarlos exige
# una evaluación con consultas y notas reales, y eso es un experimento, no un
# ajuste a ojo.
PESOS_RERANK: Dict[str, float] = {
    "lexical": 0.45,
    "graph": 0.30,
    "recency": 0.15,
    "cia": 0.10,
}
W_LEXICAL = PESOS_RERANK["lexical"]
W_GRAPH = PESOS_RERANK["graph"]
W_RECENCY = PESOS_RERANK["recency"]
W_CIA = PESOS_RERANK["cia"]

#: Los intentos que el briefing entiende (propuesta `compact-agent-memory-
#: weights`, paso 2). Se **registran** en el envelope; todavia no reordenan,
#: porque cambiar el orden sin medir es exactamente lo que la propuesta
#: critica. Estan aquí para que el consumidor vea con qué propósito se pidió.
INTENTOS = ("explorar", "documentar", "cambiar", "depurar", "revisar")


# Una nota deprecada o revocada sigue siendo recuperable —no se borra nada—
# pero no debe desplazar a la vigente que la reemplazó.
# superseded_by: PENALIZACION_POR_STATUS + penalizacion() (2026-10-07). Era un
# vocabulario copiado: `superseded` y `revoked` no están en STATUS_VOCAB y
# `obsolete`, que sí, no pesaba. Se conserva como lectura del valor crudo que
# un vault heredado pueda traer escrito.
RECENCY_HALFLIFE_DAYS = 90.0



sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.consulta.repositorio import RepositorioConsulta  # noqa: E402
from vault.kernel import construir  # noqa: E402
# The rule and its weights have one owner, shared with `vault_search`
# (producto-usable S4): re-exported so `vault_context_pack.penalizacion` and
# friends keep working for their callers.
from vault.kernel.vigencia import (  # noqa: E402
    PENALIZACION_POR_STATUS, STATUS_PENALTY, motivo_historico, penalizacion)


def index_coherence():
    """Check via the runtime-injected read port, never by rebuilding."""
    from vault.runtime import componer_coherencia_indices

    if not componer_coherencia_indices():
        return {"ok": False, "status": "index_unavailable"}
    contexto = construir()
    proveedor = contexto.coherencia_indices
    if proveedor is None:
        return {"ok": False, "status": "index_unavailable"}
    return proveedor.comprobar(contexto)

# El vocabulario se declara una vez y se consume, no se copia. Ver
# `vault_vocabulario.py` para el registro y su contexto dueno.
from vault_vocabulario import peso as _peso

CIA_WEIGHT: Dict[str, float] = _peso("severidad")


def _resolve_budget_from_profile() -> int:
    """AP-49: resuelve el budget desde el perfil de modelo al ejecutarse.

    El servidor MCP propaga VAULT_MODEL_PROFILE en cada llamada. Si la
    variable existe se usa; si no, se recurre al perfil activo. El floor
    de 2000 tokens asegura que cualquier modelo recibir contexto.
    """
    import os
    import subprocess
    try:
        profile_script = Path(__file__).resolve().parent / "vault_model_profile.py"
        result = subprocess.run(
            [sys.executable, str(profile_script), "--budget"],
            capture_output=True, text=True, encoding="utf-8", timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                try:
                    return int(line.strip())
                except ValueError:
                    continue
    except (OSError, ValueError):
        pass
    return FLOOR_BUDGET


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioConsulta:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioConsulta(construir(root))


def _days_since(timestamp: str, now: datetime) -> Optional[float]:
    if not timestamp:
        return None
    raw = str(timestamp).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(raw[:10])
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0.0, (now - parsed).total_seconds() / 86400.0)


def _recency_score(timestamp: str, now: datetime) -> float:
    """Decaimiento exponencial con vida media de 90 días.

    No es un corte: una nota de hace un año sigue puntuando ~0.06, suficiente
    para entrar si nada más responde la pregunta.
    """
    days = _days_since(timestamp, now)
    if days is None:
        return 0.3  # sin fecha: ni fresca ni rancia, no se premia ni castiga
    return 0.5 ** (days / RECENCY_HALFLIFE_DAYS)


def _read_note(path: str) -> Dict[str, Any]:
    """Lee una nota del vault. Nunca sale del vault (AP-36)."""
    full = (_raiz() / path).resolve()
    try:
        full.relative_to(_raiz().resolve())
    except ValueError:
        return emit_error("vault_context_pack", "INVALID_PATH", "fuera del vault")
    if not full.is_file():
        return emit_error("vault_context_pack", "NOTE_NOT_FOUND", "no existe")
    try:
        raw = full.read_text(encoding="utf-8")
    except OSError as exc:
        return emit_error("vault_context_pack", "FILE_READ_ERROR", str(exc), exception=exc)
    frontmatter, body = parse_frontmatter_with_body(raw)
    return {"ok": True, "frontmatter": frontmatter, "body": body.strip()}


def _consulta_pide_historia(statuses: List[str]) -> bool:
    """The query names a status that is history (`deprecated`, `revoked`…).

    Then history is what was asked for, and the pack behaves as with
    `--incluir-historico`: filtering it out would answer a different question.
    """
    return any(penalizacion({"status": s}) < 1.0 for s in statuses or [])


class _FiltroDeHistoria:
    """S4: history leaves the candidate set before the rerank scores it.

    The penalty (`penalizacion`) kept historic notes competing for the budget
    and costing ranking work: with h of them relevant to a query, the rerank
    scored them all and the pack spent tokens on them. Inactive (with
    `--incluir-historico`, or when the query names a historic status), nothing
    is classified as history and the pack is the one before this filter.

    A note left out that declares `superseded_by:` points to its successor;
    when that successor is current it enters the candidates inheriting the
    predecessor's lexical and graph signals (it answers what the predecessor
    answered) and carries `supersedes`.
    """

    def __init__(self, activo: bool) -> None:
        self.activo = activo
        self.censo = None
        self._indice: Optional[Dict[str, List[str]]] = None
        self._notas: Dict[str, Dict[str, Any]] = {}
        self._motivos: Dict[str, Optional[str]] = {}
        self._sucesoras: Dict[str, Optional[str]] = {}
        self.excluidas: Dict[str, str] = {}
        self.punteros: Dict[str, Dict[str, Any]] = {}
        self.herencia: Dict[str, Dict[str, Any]] = {}

    def leer(self, path: str) -> Dict[str, Any]:
        """`_read_note`, once per path and pack."""
        if path not in self._notas:
            self._notas[path] = _read_note(path)
        return self._notas[path]

    def _fm(self, path: str) -> Dict[str, Any]:
        nota = self.leer(path)
        return nota.get("frontmatter", {}) if nota.get("ok") else {}

    def motivo(self, path: str) -> Optional[str]:
        """The reason `path` is history, or `None` (also for index.md, never scored)."""
        if not self.activo or Path(path).name.lower() == "index.md":
            return None
        if path not in self._motivos:
            self._motivos[path] = motivo_historico(path, self._fm(path))
        return self._motivos[path]

    def sucesora(self, path: str) -> Optional[str]:
        """The current note `superseded_by:` leads to from `path`, following a chain.

        Resolved by the owner (`vault_lib.resolver_sustitucion`): a broken or
        ambiguous target, a cycle, or a chain that ends in history has none.
        """
        if path in self._sucesoras:
            return self._sucesoras[path]
        from vault_lib import indice_de_nombres, resolver_sustitucion

        destino: Optional[str] = None
        vistas, actual = {path}, path
        while True:
            valor = self._fm(actual).get("superseded_by")
            if not str(valor or "").strip():
                break
            if self._indice is None:
                self.censo = self.censo or _censo()
                self._indice = indice_de_nombres(self.censo[0], self.censo[1])
            siguiente = resolver_sustitucion(valor, Path(actual), self._indice)[0]
            if (not siguiente or siguiente in vistas
                    or Path(siguiente).name.lower() == "index.md"):
                break
            if self.motivo(siguiente) is None:
                destino = siguiente if self.leer(siguiente).get("ok") else None
                break
            vistas.add(siguiente)
            actual = siguiente
        self._sucesoras[path] = destino
        return destino

    def excluir(self, path: str, lexical: float, graph: float) -> None:
        """Leave `path` out, record why, and hand its signals to its successor."""
        self.excluidas[path] = self._motivos[path] or ""
        declarado = str(self._fm(path).get("superseded_by") or "").strip()
        if not declarado:
            return
        destino = self.sucesora(path)
        self.punteros[path] = {"path": path, "superseded_by": declarado, "successor": destino}
        if destino:
            h = self.herencia.setdefault(destino, {"lexical": 0.0, "graph": 0.0, "supersedes": []})
            h["lexical"] = max(h["lexical"], lexical)
            h["graph"] = max(h["graph"], graph)
            h["supersedes"].append(path)

    def informe(self) -> Dict[str, Any]:
        """Additive envelope field; absent when nothing was left out."""
        if not self.excluidas:
            return {}
        por_motivo: Dict[str, int] = {}
        for motivo in self.excluidas.values():
            por_motivo[motivo] = por_motivo.get(motivo, 0) + 1
        return {"history_excluded": {
            "total": len(self.excluidas),
            "by_reason": dict(sorted(por_motivo.items())),
            "superseded_by": [self.punteros[p] for p in sorted(self.punteros)],
            "hint": ("solo verdad vigente: --incluir-historico devuelve estas notas "
                     "al ranking, penalizadas"),
        }}


def _censo() -> Tuple[List[str], Dict[str, List[str]], Dict[str, Dict[str, Any]]]:
    """One read of the vault: every note, its `aliases:` and the PAT-7 declarers.

    Shared by the disagreement pairs and the `superseded_by:` resolution, so a
    pack that needs both walks the disk once.
    """
    from vault.kernel.enumeracion import notas_en_disco
    from vault.kernel.normativa.desacuerdos import PREDICADO
    from vault_lib import parse_frontmatter

    raiz = _raiz()
    relativas: List[str] = []
    aliases: Dict[str, List[str]] = {}
    declarantes: Dict[str, Dict[str, Any]] = {}
    for ruta in notas_en_disco(raiz, _repo().ctx.secciones.ordenadas(), incluir_indices=False):
        rel = ruta.relative_to(raiz).as_posix()
        relativas.append(rel)
        try:
            fm = parse_frontmatter(ruta.read_text(encoding="utf-8")) or {}
        except (OSError, UnicodeDecodeError):
            continue
        alias = fm.get("aliases")
        aliases[rel] = ([alias] if isinstance(alias, str)
                        else [a for a in alias if isinstance(a, str)]
                        if isinstance(alias, list) else [])
        if fm.get(PREDICADO):
            declarantes[rel] = fm
    return relativas, aliases, declarantes


def _pares_en_desacuerdo(censo=None) -> set:
    """PAT-7: every declared `contradicts` pair in the vault, symmetric.

    Declaring it on either note is enough, so the whole vault is read, and
    names resolve the Obsidian way (file name and `aliases:`). The reader of
    the declaration is its single owner, shared with the AP-05 detector
    (`vault.kernel.normativa.desacuerdos`).
    """
    from vault.kernel.normativa.desacuerdos import pares_declarados
    from vault_lib import indice_de_nombres

    relativas, aliases, declarantes = censo or _censo()
    if not declarantes:
        return set()
    return pares_declarados(declarantes, indice_de_nombres(relativas, aliases))


def _con_los_dos_lados(cabeza: List[Dict[str, Any]], now: datetime,
                       censo=None) -> List[Dict[str, Any]]:
    """PAT-7: a selected note that declares a disagreement brings the other side.

    The counterpart enters right after the note that names it, with the same
    score and `via: {"contradicts": <declarer>}`, so the budget sees the pair
    together; both carry `disagrees_with`. Without any declaration in the vault
    the selection is returned unchanged.
    """
    pares = _pares_en_desacuerdo(censo)
    if not pares:
        return cabeza
    elegidas = {c["path"] for c in cabeza}
    salida: List[Dict[str, Any]] = []
    for candidato in cabeza:
        salida.append(candidato)
        otros = sorted(x for par in pares if candidato["path"] in par
                       for x in par if x != candidato["path"])
        if not otros:
            continue
        candidato["disagrees_with"] = otros
        for otro in otros:
            if otro in elegidas:
                continue
            elegidas.add(otro)
            nota = _read_note(otro)
            fm = nota.get("frontmatter", {}) if nota.get("ok") else {}
            updated = str(fm.get("updatedAt") or "")
            salida.append({
                "path": otro,
                "title": fm.get("title") or Path(otro).stem,
                "score": candidato["score"],
                "signals": {"lexical": 0.0, "graph": 0.0,
                            "recency": round(_recency_score(updated, now), 4),
                            "cia": CIA_WEIGHT.get(str(fm.get("cia_integrity", "medium")).lower(), 0.5),
                            "status_penalty": penalizacion(fm)},
                "status": str(fm.get("status", "")).lower(),
                "updatedAt": updated,
                "via": {"contradicts": candidato["path"]},
                "disagrees_with": [candidato["path"]],
                "readable": nota.get("ok", False),
                "body": nota.get("body", "") if nota.get("ok") else "",
            })
    return salida


def _truncate_to_tokens(text: str, max_tokens: int) -> tuple[str, bool]:
    """Recorta por párrafos, no por caracteres: cortar a mitad de frase produce
    un extracto que el agente cita mal."""
    if estimate_tokens(text) <= max_tokens:
        return text, False
    out: List[str] = []
    used = 0
    for block in text.split("\n\n"):
        cost = estimate_tokens(block) + 1
        if used + cost > max_tokens:
            break
        out.append(block)
        used += cost
    if not out:  # un solo bloque enorme: se recorta por líneas
        for line in text.splitlines():
            cost = estimate_tokens(line) + 1
            if used + cost > max_tokens:
                break
            out.append(line)
            used += cost
        if not out:  # una sola línea enorme: se recorta por palabras
            for palabra in text.split():
                if estimate_tokens(" ".join(out + [palabra])) > max_tokens:
                    break
                out.append(palabra)
            return " ".join(out) + " …", True
        return "\n".join(out) + "\n…", True
    return "\n\n".join(out) + "\n\n…", True


def _must_preferences() -> List[Dict[str, Any]]:
    """Las preferencias `must` (ver `_preferencias_must`, que además avisa)."""
    return _preferencias_must()[0]


def _preferencias_must() -> Tuple[List[Dict[str, Any]], List[str]]:
    """Las preferencias `must` y los avisos de las que no se pudieron cargar.

    Auditoría del 2026-10-15: el fallo quedaba en la traza y el paquete salía
    `ok: true` sin decir que le faltaban preferencias vinculantes.
    """
    # AP-51: una preferencia que falta se dice en el paquete, no solo en la traza.
    try:
        from vault_preferences import vault_preferences_list

        listing = vault_preferences_list(strength="must")
    except (ImportError, OSError) as exc:
        emit_error("vault_context_pack", "PREFERENCES_UNAVAILABLE",
                  f"No se pudieron cargar preferencias must: {exc}")
        return [], [f"preferencias must no disponibles: {type(exc).__name__}"]
    except Exception as exc:
        emit_error("vault_context_pack", "UNEXPECTED_ERROR", str(exc))
        return [], [f"preferencias must no disponibles: {type(exc).__name__}"]
    avisos = [f"preferencia ilegible, fuera del paquete: {u['path']} ({u['error']})"
              for u in listing.get("unreadable", [])]
    return listing.get("preferences", []), avisos


def vault_context_pack(
    query: str,
    budget_tokens: int = DEFAULT_BUDGET,
    top_k: int = DEFAULT_TOP_K,
    excerpt_tokens: int = DEFAULT_EXCERPT_TOKENS,
    include_preferences: bool = True,
    min_score: float = 0.0,
    now: Optional[datetime] = None,
    intento: Optional[str] = None,
    incluir_historico: bool = False,
) -> Dict[str, Any]:
    """
Recupera, rerankea y empaqueta el contexto para responder `query`.

Por defecto el paquete es verdad vigente: las notas históricas
(`motivo_historico`) salen de las candidatas antes del rerank y el envelope
dice cuántas y por qué (`history_excluded`). `incluir_historico=True` es el
paquete de antes: compiten, penalizadas."""

    if intento is not None and intento not in INTENTOS:
        return emit_error(
            "vault_context_pack", "INVALID_INPUT",
            f"--intento {intento!r} no es uno de {', '.join(INTENTOS)}",
        )
    if budget_tokens <= 0:
        return {"ok": False, "error_code": "INVALID_BUDGET",
                "error": "El presupuesto de tokens debe ser positivo"}
    # AP-51: los otros dos topes, igual que el presupuesto. `--top-k 0` daba un
    # paquete vacío con ok:true —indistinguible de «nada relevante»— y un
    # negativo cortaba `candidates[:-1]`, todas menos la última.
    for nombre, valor in (("--top-k", top_k), ("--excerpt-tokens", excerpt_tokens)):
        if valor < 1:
            return emit_error("vault_context_pack", "INVALID_INPUT",
                              f"{nombre} debe ser un entero positivo (recibido: {valor}).")

    now = now or datetime.now(timezone.utc)

    parsed = vault_query_parse(query)
    if not parsed.get("ok"):
        return parsed
    structured = parsed["structured"]
    filtro = _FiltroDeHistoria(
        not incluir_historico and not _consulta_pide_historia(structured["status"]))

    # ── 1. recuperación léxica ───────────────────────────────────────────────
    terms = structured["phrases"] + structured["terms"] + structured["tags"]
    lexical: Dict[str, Dict[str, Any]] = {}
    search_error: Optional[str] = None
    search_incomplete = False
    search_index_used = False
    index_warning: Optional[str] = None

    def codigo_busqueda(resultado: Dict[str, Any]) -> str:
        # No propagar mensajes arbitrarios de un proveedor: pueden contener rutas.
        codigo = resultado.get("error_code")
        if codigo == "INDEX_NOT_FOUND":
            return "INDEX_NOT_FOUND; ejecuta vault_reindex"
        if (isinstance(codigo, str) and codigo.isascii() and codigo
                and all(c.isupper() or c.isdigit() or c == "_" for c in codigo)):
            return codigo
        return "error sin código"
    # Solo la sección que la pregunta nombra filtra. Hasta v41.2 también lo
    # hacía la inferida por una palabra («diagrama» → 13_Flows), y bastaba con
    # que esa sección devolviera algo para esconder la nota de otra: medido
    # con tests/banco_agente.py en /vcloud y /ans (regla 7).
    named = structured.get("sections_named", [])
    if terms:
        section = named[0] if named else None
        # Every match, history included: the pack applies its own history
        # filter (`_FiltroDeHistoria`), which counts what it leaves out and
        # hands a superseded note's signals to its successor. The search's
        # current-only default would hide them before the pack saw them.
        found = vault_search(" ".join(terms[:8]), folder=section, incluir_historico=True)
        if not found.get("ok"):
            search_error = codigo_busqueda(found)
        elif found.get("source") != "live_visible_markdown":
            search_index_used = True
        search_incomplete = bool(found.get("incomplete"))
        for hit in found.get("results", []):
            lexical[hit["path"]] = hit
        # Ni la nombrada se queda sin respuesta: si no devuelve nada, se
        # reintenta sin ella antes que responder "no hay contexto" teniendo el
        # vault la nota en otra sección.
        if section and not lexical:
            retry = vault_search(" ".join(terms[:8]), incluir_historico=True)
            if not retry.get("ok"):
                detalle = codigo_busqueda(retry)
                search_error = f"{search_error}; reintento: {detalle}" if search_error else detalle
            elif retry.get("source") != "live_visible_markdown":
                search_index_used = True
            search_incomplete = search_incomplete or bool(retry.get("incomplete"))
            for hit in retry.get("results", []):
                lexical[hit["path"]] = hit

    if search_index_used:
        try:
            estado_indice = index_coherence()
            if estado_indice.get("status") == "index_stale":
                index_warning = "índice de búsqueda desactualizado: ejecuta vault_reindex"
            elif estado_indice.get("status") == "index_incomplete":
                index_warning = "verificación del índice de búsqueda incompleta; revisa vault_reindex"
            elif estado_indice.get("status") != "index_ok":
                index_warning = "no se pudo verificar el índice de búsqueda; revisa vault_reindex"
        except Exception:
            index_warning = "no se pudo verificar el índice de búsqueda; revisa vault_reindex"

    # The scale is the current notes' own: history neither scores nor rescales them.
    max_lexical = max((h["score"] for p, h in lexical.items() if filtro.motivo(p) is None),
                      default=0.0) or 1.0

    # ── 2. expansión por grafo ───────────────────────────────────────────────
    seeds = list(structured["seeds"])
    if not seeds:
        seeds = [p for p in lexical if filtro.motivo(p) is None][:3]
    if not seeds and filtro.activo:
        # Every lexical hit is history: expand from what replaced it.
        seeds = list(dict.fromkeys(
            s for s in (filtro.sucesora(p) for p in lexical) if s))[:3]
    graph_rel: Dict[str, float] = {}
    graph_via: Dict[str, Any] = {}
    graph_error: Optional[str] = None
    graph_stale: Optional[Dict[str, Any]] = None
    if seeds:
        sub = vault_subgraph(seeds=seeds, hops=structured["hops"],
                             max_nodes=max(top_k * 3, 30))
        if sub.get("ok"):
            for node in sub["nodes"]:
                if node["in_graph"]:
                    graph_rel[node["path"]] = node["relevance"]
                    graph_via[node["path"]] = node["via"]
        else:
            graph_error = mensaje_de(sub)
        # Con el grafo desfasado las notas nuevas entran por la vía léxica pero
        # sin sus aristas: el paquete sale, pero no puede presentarse como
        # completo sin decirlo.
        if sub.get("stale_graph"):
            graph_stale = sub.get("stale", {})

    # ── 3. rerank ────────────────────────────────────────────────────────────
    candidates: List[Dict[str, Any]] = []
    caminos = set(lexical) | set(graph_rel)
    if filtro.activo:
        # S4: history leaves before scoring, so it costs neither ranking work nor
        # budget; its successor takes its place.
        for path in sorted(caminos):
            if filtro.motivo(path) is not None:
                hit = lexical.get(path)
                filtro.excluir(path, min(1.0, hit["score"] / max_lexical) if hit else 0.0,
                               graph_rel.get(path, 0.0))
        caminos = (caminos - set(filtro.excluidas)) | set(filtro.herencia)
    for path in caminos:
        # Los index.md son artefactos regenerados, no conocimiento: entregarlos
        # como contexto gasta presupuesto en una lista de enlaces que el agente
        # ya puede recorrer con vault_subgraph.
        if Path(path).name.lower() == "index.md":
            continue
        hit = lexical.get(path, {})
        note = filtro.leer(path)
        frontmatter = note.get("frontmatter", {}) if note.get("ok") else {}
        heredado = filtro.herencia.get(path)

        if structured["status"]:
            if str(frontmatter.get("status", "")).lower() not in structured["status"]:
                continue
        if named and path.split("/")[0] not in named:
            # Solo excluye si el grafo tampoco lo justifica: una nota de otra
            # sección conectada directamente al tema sí es contexto legítimo.
            if graph_rel.get(path, 0.0) < 0.5:
                continue

        updated = str(frontmatter.get("updatedAt") or hit.get("updatedAt") or "")
        if structured["temporal"] and updated:
            if updated[:10] < structured["temporal"]["since"]:
                continue

        lex = (hit.get("score", 0.0) / max_lexical) if hit else 0.0
        graph = graph_rel.get(path, 0.0)
        if heredado:
            lex = max(lex, heredado["lexical"])
            graph = max(graph, heredado["graph"])
        recency = _recency_score(updated, now)
        cia = CIA_WEIGHT.get(str(frontmatter.get("cia_integrity", "medium")).lower(), 0.5)

        score = W_LEXICAL * lex + W_GRAPH * graph + W_RECENCY * recency + W_CIA * cia
        status = str(frontmatter.get("status", "")).lower()
        penalty = penalizacion(frontmatter)
        score *= penalty

        if score < min_score:
            continue

        candidates.append({
            "path": path,
            "title": frontmatter.get("title") or hit.get("title") or Path(path).stem,
            "score": round(score, 4),
            "signals": {"lexical": round(lex, 4), "graph": round(graph, 4),
                        "recency": round(recency, 4), "cia": cia,
                        "status_penalty": penalty},
            "status": status,
            "updatedAt": updated,
            "via": graph_via.get(path),
            "readable": note.get("ok", False),
            "body": note.get("body", "") if note.get("ok") else "",
            **({"supersedes": sorted(heredado["supersedes"])} if heredado else {}),
        })

    candidates.sort(key=lambda c: (-c["score"], c["path"]))

    # ── 4. empaquetado bajo presupuesto ──────────────────────────────────────
    blocks: List[str] = []
    included: List[Dict[str, Any]] = []
    excluded: List[Dict[str, Any]] = []

    # El presupuesto cubre el texto que se entrega, no solo las notas: si la
    # cabecera y los separadores no se contabilizan, el paquete se pasa del
    # límite justo cuando el límite importa.
    header = f"# Contexto para: {query}\n"
    SEPARATOR_TOKENS = 4  # "\n\n---\n\n"
    used = estimate_tokens(header)

    preferences, avisos_de_preferencias = (
        _preferencias_must() if include_preferences else ([], []))
    if preferences:
        lines = ["## Preferencias vinculantes del usuario", ""]
        lines += [f"- **{p['title']}** ({p['category']}): {p['statement']}"
                  for p in preferences]
        block = "\n".join(lines)
        minimo = estimate_tokens(header + "\n\n" + block)
        if minimo > budget_tokens:
            return emit_error(
                "vault_context_pack", "INVALID_BUDGET",
                f"Las preferencias obligatorias requieren al menos {minimo} "
                f"tokens con la cabecera; presupuesto recibido: {budget_tokens}.",
            )
        cost = estimate_tokens(block) + SEPARATOR_TOKENS
        blocks.append(block)
        used += cost

    seleccion = _con_los_dos_lados(candidates[:top_k], now, filtro.censo)
    traidas = {c["path"] for c in seleccion}
    for candidate in seleccion:
        if not candidate["readable"]:
            excluded.append({"path": candidate["path"], "reason": "no legible"})
            continue
        excerpt, truncated = _truncate_to_tokens(candidate["body"], excerpt_tokens)
        block = (f"### {candidate['title']}\n"
                 f"`{candidate['path']}`"
                 + (f" · status: {candidate['status']}" if candidate["status"] else "")
                 + f" · score {candidate['score']}\n\n{excerpt}")
        cost = estimate_tokens(block) + SEPARATOR_TOKENS
        if used + cost > budget_tokens:
            excluded.append({"path": candidate["path"], "reason": "sin presupuesto",
                             "would_cost": cost, "score": candidate["score"]})
            continue
        blocks.append(block)
        used += cost
        included.append({k: v for k, v in candidate.items() if k != "body"}
                        | {"truncated": truncated, "tokens": cost})

    for candidate in candidates[top_k:]:
        if candidate["path"] in traidas:
            continue
        excluded.append({"path": candidate["path"], "reason": "fuera del top-k",
                         "score": candidate["score"]})

    context = header + "\n\n" + "\n\n---\n\n".join(blocks) if blocks else ""

    warnings: List[str] = list(avisos_de_preferencias)
    if search_error:
        warnings.append(f"búsqueda léxica: {search_error}")
    if search_incomplete:
        warnings.append("búsqueda léxica incompleta: algunas notas no se pudieron leer")
    if index_warning:
        warnings.append(index_warning)
    if graph_error:
        warnings.append(f"expansión por grafo: {graph_error}")
    if graph_stale:
        warnings.append(
            f"grafo desactualizado: {graph_stale.get('new', 0)} nota(s) nuevas y "
            f"{graph_stale.get('gone', 0)} borradas sin reflejar; sus aristas no "
            "cuentan. Regenera con vault_graph."
        )
    if not included:
        warnings.append("ninguna nota entró en el contexto: revisa la consulta "
                        "o amplía --budget")

    return {
        "ok": True,
        "query": query,
        "structured": structured,
        "confidence": parsed["confidence"],
        "context": context,
        "tokens": {
            "budget": budget_tokens,
            "used": estimate_tokens(context),
            "remaining": max(0, budget_tokens - estimate_tokens(context)),
            "preferences": estimate_tokens(blocks[0]) if preferences else 0,
        },
        "included": included,
        "excluded": excluded,
        "candidates_considered": len(candidates),
        "preferences_included": len(preferences),

        "weights": dict(PESOS_RERANK),

        "weights_origen": (

            "declarados: decision de diseno que suma 1.0, no una "

            "medicion. Calibrarlos exige una evaluacion con consultas "

            "y notas reales."

        ),

        "intento": intento,

        "intento_nota": (

            "el intento se registra; no reordena mientras no haya medicion"

        ),
        "warnings": warnings,
        **filtro.informe(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_context_pack — pregunta → contexto bajo presupuesto",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_context_pack.py "que decidimos sobre el transporte MCP"
  python vault_context_pack.py "errores del proyecto ans" --budget 2000
  python vault_context_pack.py "auth" --format markdown
  python vault_context_pack.py "mcp" --explain          # senales del rerank

Notas:
  - Encadena vault_query_parse -> vault_search -> vault_subgraph -> rerank
  - El presupuesto recorta notas enteras: nunca entrega media nota como entera
  - Las preferencias 'must' entran siempre primero (--no-preferences las omite);
    si no caben íntegras con la cabecera, devuelve INVALID_BUDGET
  - `excluded` dice que se dejo fuera y por que: el recorte es auditable
  - Por defecto solo verdad vigente: lo historico sale antes del rerank y
    `history_excluded` lo cuenta por motivo; --incluir-historico lo devuelve
""",
        allow_abbrev=False,
    )
    # La pregunta se admite **también** como `--query`. El catálogo MCP publica
    # los parámetros por nombre de flag, así que un posicional no aparecía en el
    # `inputSchema`: el servidor invocaba con `--query "..."` y argparse
    # respondía `unrecognized arguments`. Toda la capacidad consulta -> contexto
    # era inalcanzable por MCP, que es su único consumidor real.
    #
    # El posicional se conserva (no-derogación): quien lo usa desde la CLI sigue
    # funcionando. Lo que cambia es que ahora hay una forma nombrada, que es la
    # que un catálogo puede publicar.
    parser.add_argument("query", nargs="?", default=None,
                        help="Pregunta en lenguaje natural")
    parser.add_argument("--query", dest="query_flag", default=None,
                        help="La misma pregunta, en forma nombrada (la que usa MCP)")
    parser.add_argument(
        "--intento", choices=list(INTENTOS), default=None,
        help="Propósito de la consulta (explorar, documentar, cambiar, "
             "depurar, revisar). Se registra en el envelope; todavía no "
             "reordena: cambiar el orden sin medir es lo que la propuesta "
             "critica.")
    parser.add_argument("--budget", type=int, default=None,
                        dest="budget_tokens",
                        help="Presupuesto en tokens (default: del perfil de modelo)")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K,
                        help=f"Máximo de notas candidatas (default: {DEFAULT_TOP_K})")
    parser.add_argument("--excerpt-tokens", type=int, default=DEFAULT_EXCERPT_TOKENS,
                        help=f"Tope por nota (default: {DEFAULT_EXCERPT_TOKENS})")
    parser.add_argument("--min-score", type=float, default=0.0,
                        help="Descarta candidatas por debajo de este score")
    parser.add_argument("--no-preferences", action="store_true",
                        help="No inyecta las preferencias 'must'")
    parser.add_argument("--format", default="json", choices=["json", "markdown"])
    parser.add_argument("--explain", action="store_true",
                        help="Incluye las señales del rerank por nota")
    parser.add_argument(
        "--incluir-historico", action="store_true",
        help="Devuelve las notas históricas (superseded_by, archived, deprecated, "
             "obsolete, revoked, fuentes archivadas, cuarentena) al ranking, "
             "penalizadas como antes. Por defecto el paquete es solo verdad vigente.")

    args = parser.parse_args()
    pregunta = args.query_flag or args.query
    if not pregunta:
        parser.error("falta la pregunta: pasala como posicional o con --query")
    args.query = pregunta

    budget = args.budget_tokens if args.budget_tokens is not None else _resolve_budget_from_profile()

    result = vault_context_pack(
        query=args.query, budget_tokens=budget, top_k=args.top_k,
        excerpt_tokens=args.excerpt_tokens, min_score=args.min_score,
        include_preferences=not args.no_preferences,
        intento=args.intento, incluir_historico=args.incluir_historico,
    )

    if args.format == "markdown" and result.get("ok"):
        print(result["context"])
    else:
        if result.get("ok") and not args.explain:
            for item in result["included"]:
                item.pop("signals", None)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_context_pack"))
