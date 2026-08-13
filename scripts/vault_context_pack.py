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
    prohibió el usuario al agente, gana lo segundo.

Usage:
    python vault_context_pack.py "que decidimos sobre el transporte MCP"
    python vault_context_pack.py "errores del proyecto ans" --budget 2000
    python vault_context_pack.py "auth" --format markdown --no-preferences
    python vault_context_pack.py "mcp" --explain
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_errors import emit_error, wrap_main
from vault_lib import parse_frontmatter_with_body
from vault_query_parse import vault_query_parse
from vault_search import vault_search
from vault_subgraph import vault_subgraph
from vault_token_service import estimate_tokens

DEFAULT_BUDGET = 4000
DEFAULT_TOP_K = 12
DEFAULT_EXCERPT_TOKENS = 350

# Pesos del rerank. Suman 1.0 a propósito: así `score` es comparable entre
# consultas y un umbral fijo significa lo mismo siempre.
W_LEXICAL = 0.45
W_GRAPH = 0.30
W_RECENCY = 0.15
W_CIA = 0.10


# Una nota deprecada o revocada sigue siendo recuperable —no se borra nada—
# pero no debe desplazar a la vigente que la reemplazó.
STATUS_PENALTY: Dict[str, float] = {
    "deprecated": 0.4, "superseded": 0.3, "revoked": 0.2, "archived": 0.5,
}

RECENCY_HALFLIFE_DAYS = 90.0



sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.consulta.repositorio import RepositorioConsulta  # noqa: E402
from vault.kernel import construir  # noqa: E402

# El vocabulario se declara una vez y se consume, no se copia. Ver
# `vault_vocabulario.py` para el registro y su contexto dueno.
from vault_vocabulario import peso as _peso

CIA_WEIGHT: Dict[str, float] = _peso("severidad")


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
        return "\n".join(out) + "\n…", True
    return "\n\n".join(out) + "\n\n…", True


def _must_preferences() -> List[Dict[str, Any]]:
    try:
        from vault_preferences import vault_preferences_list

        listing = vault_preferences_list(strength="must")
        return listing.get("preferences", []) if listing.get("ok") else []
    except Exception:
        return []


def vault_context_pack(
    query: str,
    budget_tokens: int = DEFAULT_BUDGET,
    top_k: int = DEFAULT_TOP_K,
    excerpt_tokens: int = DEFAULT_EXCERPT_TOKENS,
    include_preferences: bool = True,
    min_score: float = 0.0,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Recupera, rerankea y empaqueta el contexto para responder `query`."""
    if budget_tokens <= 0:
        return {"ok": False, "error_code": "INVALID_BUDGET",
                "error": "El presupuesto de tokens debe ser positivo"}

    now = now or datetime.now(timezone.utc)

    parsed = vault_query_parse(query)
    if not parsed.get("ok"):
        return parsed
    structured = parsed["structured"]

    # ── 1. recuperación léxica ───────────────────────────────────────────────
    terms = structured["phrases"] + structured["terms"] + structured["tags"]
    lexical: Dict[str, Dict[str, Any]] = {}
    search_error: Optional[str] = None
    if terms:
        section = structured["sections"][0] if structured["sections"] else None
        found = vault_search(" ".join(terms[:8]), folder=section)
        if not found.get("ok"):
            search_error = found.get("error")
        for hit in found.get("results", []):
            lexical[hit["path"]] = hit
        # Una sección inferida por pista léxica es una apuesta, no un filtro
        # duro: si no devuelve nada, se reintenta sin ella antes que responder
        # "no hay contexto" teniendo el vault la nota en otra sección.
        if section and not lexical:
            for hit in vault_search(" ".join(terms[:8])).get("results", []):
                lexical[hit["path"]] = hit

    max_lexical = max((h["score"] for h in lexical.values()), default=0.0) or 1.0

    # ── 2. expansión por grafo ───────────────────────────────────────────────
    seeds = list(structured["seeds"])
    if not seeds:
        seeds = [p for p in list(lexical)[:3]]
    graph_rel: Dict[str, float] = {}
    graph_via: Dict[str, Any] = {}
    graph_error: Optional[str] = None
    if seeds:
        sub = vault_subgraph(seeds=seeds, hops=structured["hops"],
                             max_nodes=max(top_k * 3, 30))
        if sub.get("ok"):
            for node in sub["nodes"]:
                if node["in_graph"]:
                    graph_rel[node["path"]] = node["relevance"]
                    graph_via[node["path"]] = node["via"]
        else:
            graph_error = sub.get("error")

    # ── 3. rerank ────────────────────────────────────────────────────────────
    candidates: List[Dict[str, Any]] = []
    for path in set(lexical) | set(graph_rel):
        # Los index.md son artefactos regenerados, no conocimiento: entregarlos
        # como contexto gasta presupuesto en una lista de enlaces que el agente
        # ya puede recorrer con vault_subgraph.
        if Path(path).name.lower() == "index.md":
            continue
        hit = lexical.get(path, {})
        note = _read_note(path)
        frontmatter = note.get("frontmatter", {}) if note.get("ok") else {}

        if structured["status"]:
            if str(frontmatter.get("status", "")).lower() not in structured["status"]:
                continue
        if structured["sections"] and path.split("/")[0] not in structured["sections"]:
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
        recency = _recency_score(updated, now)
        cia = CIA_WEIGHT.get(str(frontmatter.get("cia_integrity", "medium")).lower(), 0.5)

        score = W_LEXICAL * lex + W_GRAPH * graph + W_RECENCY * recency + W_CIA * cia
        status = str(frontmatter.get("status", "")).lower()
        penalty = STATUS_PENALTY.get(status)
        if penalty:
            score *= penalty

        if score < min_score:
            continue

        candidates.append({
            "path": path,
            "title": frontmatter.get("title") or hit.get("title") or Path(path).stem,
            "score": round(score, 4),
            "signals": {"lexical": round(lex, 4), "graph": round(graph, 4),
                        "recency": round(recency, 4), "cia": cia,
                        "status_penalty": penalty or 1.0},
            "status": status,
            "updatedAt": updated,
            "via": graph_via.get(path),
            "readable": note.get("ok", False),
            "body": note.get("body", "") if note.get("ok") else "",
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

    preferences = _must_preferences() if include_preferences else []
    if preferences:
        lines = ["## Preferencias vinculantes del usuario", ""]
        lines += [f"- **{p['title']}** ({p['category']}): {p['statement']}"
                  for p in preferences]
        block = "\n".join(lines)
        cost = estimate_tokens(block) + SEPARATOR_TOKENS
        blocks.append(block)
        used += cost

    for candidate in candidates[:top_k]:
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
        excluded.append({"path": candidate["path"], "reason": "fuera del top-k",
                         "score": candidate["score"]})

    context = header + "\n\n" + "\n\n---\n\n".join(blocks) if blocks else ""

    warnings: List[str] = []
    if search_error:
        warnings.append(f"búsqueda léxica: {search_error}")
    if graph_error:
        warnings.append(f"expansión por grafo: {graph_error}")
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
        "warnings": warnings,
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
  - Las preferencias 'must' entran siempre primero (--no-preferences las omite)
  - `excluded` dice que se dejo fuera y por que: el recorte es auditable
""",
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
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                        dest="budget_tokens",
                        help=f"Presupuesto en tokens (default: {DEFAULT_BUDGET})")
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

    args = parser.parse_args()
    pregunta = args.query_flag or args.query
    if not pregunta:
        parser.error("falta la pregunta: pasala como posicional o con --query")
    args.query = pregunta

    result = vault_context_pack(
        query=args.query, budget_tokens=args.budget_tokens, top_k=args.top_k,
        excerpt_tokens=args.excerpt_tokens, min_score=args.min_score,
        include_preferences=not args.no_preferences,
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
