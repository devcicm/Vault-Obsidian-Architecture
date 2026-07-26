#!/usr/bin/env python3
"""
vault_query_parse.py — Lenguaje natural → consulta estructurada del vault.

Entre "qué decidimos la semana pasada sobre el transporte MCP" y las tools que
saben responderlo hay un salto que hoy da el agente a mano, y lo da distinto
cada vez. Esta tool lo hace explícito, determinista y auditable: misma frase,
misma consulta, siempre.

Es deliberadamente **sin modelo**: reglas léxicas sobre vocabularios que ya
existen en el repo (secciones de `vault_registry`, `status` de `vault_norms`).
Coherente con el estándar — "sin base de datos, sin embeddings y sin servicio
externo". Cuando no está seguro, no adivina: baja `confidence` y deja el
término en `terms` para que la búsqueda léxica decida.

Usage:
    python vault_query_parse.py "qué decidimos sobre el transporte MCP"
    python vault_query_parse.py "errores de la semana pasada en el proyecto ans"
    python vault_query_parse.py "#arquitectura contexto amplio de mcp-protocol"
    python vault_query_parse.py "what did we decide about auth" --explain
"""

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from vault_errors import wrap_main

# ── vocabularios ─────────────────────────────────────────────────────────────
# Las secciones NO se listan aquí: se derivan del registro canónico. Lo único
# propio de esta tool son las pistas léxicas que apuntan a cada sección.

SECTION_HINTS: Dict[str, List[str]] = {
    "01_Projects": ["proyecto", "proyectos", "project", "avance", "estado del proyecto",
                    "roadmap", "milestone", "sprint"],
    "02_Observability": ["error", "errores", "fallo", "fallos", "bug", "excepcion",
                         "incidente", "alerta", "metrica", "metricas", "log", "logs",
                         "crash", "failure", "incident", "alert"],
    "03_Decisions": ["decision", "decisiones", "decidimos", "decidio", "adr",
                     "acordamos", "eleccion", "elegimos", "por que elegimos",
                     "decide", "decided", "decision record", "trade-off"],
    "04_Sessions": ["sesion", "sesiones", "ayer", "la semana pasada", "trabajamos",
                    "hicimos", "session", "diario", "bitacora"],
    "05_Tasks": ["tarea", "tareas", "pendiente", "pendientes", "todo", "backlog",
                 "task", "tasks"],
    "07_Knowledge": ["que es", "como funciona", "concepto", "aprendimos", "documenta",
                     "conocimiento", "explicacion", "what is", "how does", "knowledge"],
    "08_Runbooks": ["runbook", "procedimiento", "como despliego", "como se hace",
                    "pasos", "playbook", "how do i", "deploy"],
    "09_Infrastructure": ["infraestructura", "servidor", "servicio", "despliegue",
                          "infra", "cluster", "contenedor", "docker", "kubernetes"],
    "13_Flows": ["flujo", "flujos", "pipeline", "diagrama", "flow", "secuencia"],
    "16_AI_Governance": ["gobernanza", "riesgo", "riesgos", "cumplimiento", "auditoria",
                         "privacidad", "no conformidad", "governance", "compliance"],
    "17_Preferences": ["preferencia", "preferencias", "como quiero", "prefiero",
                       "restriccion", "no quiero que", "preference", "constraint"],
}

INTENT_HINTS: Dict[str, List[str]] = {
    "decision": ["decidimos", "decision", "decisiones", "por que elegimos", "adr",
                 "acordamos", "decided", "why did we"],
    "troubleshoot": ["error", "falla", "fallo", "no funciona", "bug", "roto",
                     "incidente", "debug", "broken", "failing"],
    "howto": ["como", "pasos", "procedimiento", "how do", "how to", "how can"],
    "definition": ["que es", "que significa", "definicion", "what is", "define"],
    "status": ["estado", "en que vamos", "avance", "status", "progress"],
    "recall": ["que hicimos", "recuerdas", "la ultima vez", "resumen", "recap",
               "what did we"],
}

STATUS_HINTS: Dict[str, List[str]] = {
    "active": ["activo", "activa", "vigente", "active", "en curso"],
    "deprecated": ["deprecado", "obsoleto", "deprecated"],
    "superseded": ["reemplazado", "superseded"],
    "revoked": ["revocado", "revocada", "revoked"],
    "draft": ["borrador", "draft"],
    "resolved": ["resuelto", "resuelta", "cerrado", "resolved", "closed"],
    "open": ["abierto", "abierta", "pendiente", "open"],
}

# Cuánto contexto vecino pedir. Es la única pista que decide `hops` del
# subgrafo; sin ella, 1 salto — barato y suficiente para la mayoría.
DEPTH_HINTS: List[Tuple[int, List[str]]] = [
    (3, ["contexto amplio", "todo lo relacionado", "panorama", "todo el contexto",
         "full context", "everything about"]),
    (2, ["relacionado", "relacionados", "alrededor", "en torno a", "contexto de",
         "related", "context of", "around"]),
]
DEFAULT_HOPS = 1

STOPWORDS = {
    # español
    "a", "al", "algo", "ante", "aqui", "asi", "como", "con", "cual", "cuando",
    "cuanto", "de", "del", "desde", "donde", "dos", "el", "ella", "ellos", "en",
    "entre", "era", "es", "esa", "ese", "eso", "esta", "estan", "este", "esto",
    "fue", "ha", "hay", "la", "las", "le", "les", "lo", "los", "mas", "me", "mi",
    "muy", "no", "nos", "o", "para", "pero", "por", "porque", "que", "quien", "se",
    "ser", "si", "sin", "sobre", "solo", "son", "su", "sus", "tan", "te", "tiene",
    "todo", "todos", "un", "una", "uno", "y", "ya", "yo", "nuestro", "nuestra",
    "hicimos", "tenemos", "hacer", "dime", "dame", "busca", "buscar", "muestrame",
    # inglés
    "about", "all", "an", "and", "any", "are", "as", "at", "be", "been", "but",
    "by", "can", "did", "do", "does", "for", "from", "had", "has", "have", "how",
    "i", "if", "in", "is", "it", "its", "me", "my", "of", "on", "or", "our", "she",
    "show", "so", "than", "that", "the", "their", "them", "then", "there", "these",
    "they", "this", "to", "up", "us", "was", "we", "were", "what", "when", "where",
    "which", "who", "why", "will", "with", "you", "your",
}

MONTHS_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


def _fold(text: str) -> str:
    """Minúsculas sin acentos: 'Decisión' y 'decision' son el mismo término."""
    normalized = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def _sections() -> List[str]:
    try:
        from vault_registry import standard_folders

        return list(standard_folders())
    except Exception:
        return sorted(SECTION_HINTS)


def _parse_temporal(folded: str, now: datetime) -> Optional[Dict[str, Any]]:
    """Extrae una ventana temporal. Devuelve `since` (y `until`) en ISO date.

    Solo entiende expresiones que aparecen de verdad en preguntas a un vault.
    Ante una fecha ambigua prefiere no interpretarla: un filtro temporal
    equivocado esconde la nota que el usuario buscaba, y no se nota.
    """
    today = now.date()

    explicit = re.search(r"\b(\d{4}-\d{2}(?:-\d{2})?)\b", folded)
    if explicit:
        value = explicit.group(1)
        since = value if len(value) == 10 else f"{value}-01"
        return {"since": since, "expression": value, "kind": "explicit"}

    rules: List[Tuple[str, int]] = [
        (r"\bhoy\b|\btoday\b", 0),
        (r"\bayer\b|\byesterday\b", 1),
        (r"\besta semana\b|\bthis week\b", 7),
        (r"\b(la )?semana pasada\b|\blast week\b", 14),
        (r"\beste mes\b|\bthis month\b", 30),
        (r"\b(el )?mes pasado\b|\blast month\b", 60),
        (r"\bultimo trimestre\b|\blast quarter\b", 90),
        (r"\beste ano\b|\bthis year\b", 365),
    ]
    for pattern, days in rules:
        match = re.search(pattern, folded)
        if match:
            return {
                "since": (today - timedelta(days=days)).isoformat(),
                "expression": match.group(0).strip(),
                "kind": "relative",
            }

    relative = re.search(r"\bultim[oa]s?\s+(\d+)\s+(dias?|semanas?|meses?)\b", folded)
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2)
        days = amount * (1 if unit.startswith("dia") else 7 if unit.startswith("semana") else 30)
        return {
            "since": (today - timedelta(days=days)).isoformat(),
            "expression": relative.group(0),
            "kind": "relative",
        }

    for name, number in MONTHS_ES.items():
        if re.search(rf"\b{name}\b", folded):
            year = today.year if number <= today.month else today.year - 1
            return {"since": f"{year}-{number:02d}-01", "expression": name,
                    "kind": "month"}

    return None


def _detect(hints: Dict[str, List[str]], folded: str) -> List[Tuple[str, str]]:
    """Devuelve [(clave, pista que disparó)] para cada entrada que aparece."""
    found: List[Tuple[str, str]] = []
    for key, words in hints.items():
        for word in words:
            # El sufijo opcional cubre el plural español sin necesidad de
            # duplicar cada pista: 'error' capta 'errores', 'fallo' capta
            # 'fallos'. No es lematización — es lo justo para no fallar en
            # la forma más común de escribir la pregunta.
            pattern = (re.escape(word) if " " in word
                       else rf"\b{re.escape(word)}(?:e?s)?\b")
            if re.search(pattern, folded):
                found.append((key, word))
                break
    return found


def vault_query_parse(query: str, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Convierte una pregunta en lenguaje natural en una consulta estructurada."""
    query = (query or "").strip()
    if not query:
        return {"ok": False, "error_code": "EMPTY_QUERY",
                "error": "La consulta no puede estar vacía"}

    now = now or datetime.now(timezone.utc)
    folded = _fold(query)
    evidence: List[Dict[str, str]] = []

    # Frases entrecomilladas: el usuario pidió literalidad, se respeta tal cual.
    phrases = re.findall(r'"([^"]+)"', query) + re.findall(r"'([^']+)'", query)
    for phrase in phrases:
        evidence.append({"field": "phrases", "value": phrase, "why": "entrecomillado"})

    tags = [t.lower() for t in re.findall(r"#([A-Za-z0-9][\w/-]*)", query)]
    for tag in tags:
        evidence.append({"field": "tags", "value": tag, "why": "prefijo #"})

    # Rutas y wikilinks explícitos son semillas de grafo, no términos de búsqueda.
    seeds = re.findall(r"\[\[([^\]]+)\]\]", query)
    seeds += [p for p in re.findall(r"\b[\w./-]+\.md\b", query)]
    seeds = list(dict.fromkeys(seeds))
    for seed in seeds:
        evidence.append({"field": "seeds", "value": seed, "why": "ruta o wikilink"})

    sections: List[str] = []
    valid_sections = set(_sections())
    for section, hint in _detect(SECTION_HINTS, folded):
        if section in valid_sections:
            sections.append(section)
            evidence.append({"field": "sections", "value": section,
                             "why": f"pista léxica '{hint}'"})

    # Sección nombrada literalmente ("en 07_Knowledge") manda sobre las pistas.
    for section in valid_sections:
        if _fold(section) in folded and section not in sections:
            sections.insert(0, section)
            evidence.append({"field": "sections", "value": section,
                             "why": "sección nombrada literalmente"})

    intents = _detect(INTENT_HINTS, folded)
    intent = intents[0][0] if intents else "search"
    if intents:
        evidence.append({"field": "intent", "value": intent,
                         "why": f"pista léxica '{intents[0][1]}'"})

    statuses = [s for s, _ in _detect(STATUS_HINTS, folded)]
    for status, hint in _detect(STATUS_HINTS, folded):
        evidence.append({"field": "status", "value": status,
                         "why": f"pista léxica '{hint}'"})

    hops = DEFAULT_HOPS
    depth_expression: Optional[str] = None
    for depth, words in DEPTH_HINTS:
        hit = next((w for w in words if w in folded), None)
        if hit:
            hops, depth_expression = depth, hit
            evidence.append({"field": "hops", "value": str(depth),
                             "why": f"pide contexto relacionado ('{hit}')"})
            break

    temporal = _parse_temporal(folded, now)
    if temporal:
        evidence.append({"field": "temporal", "value": temporal["since"],
                         "why": f"expresión '{temporal['expression']}'"})

    # Términos: lo que queda tras quitar todo lo ya interpretado.
    residual = folded
    for phrase in phrases:
        residual = residual.replace(_fold(phrase), " ")
    for token in tags + seeds:
        residual = residual.replace(_fold(token), " ")
    if temporal:
        residual = residual.replace(_fold(temporal["expression"]), " ")
    if depth_expression:
        # "contexto amplio" ya se tradujo a hops=3; dejarlo en los términos
        # ensuciaría la búsqueda léxica con palabras que no son del dominio.
        residual = residual.replace(depth_expression, " ")

    terms = [
        w for w in re.findall(r"[a-z0-9][\w-]{1,}", residual)
        if w not in STOPWORDS and not w.isdigit()
    ]
    terms = list(dict.fromkeys(terms))

    # Confianza: cuánto de la frase quedó interpretado. Un consumidor puede
    # usarla para decidir si pedir aclaración en vez de responder a ciegas.
    signals = sum([
        bool(sections), bool(tags), bool(seeds), bool(temporal),
        bool(intents), bool(phrases), bool(terms),
    ])
    confidence = round(min(1.0, signals / 4.0), 2)

    structured = {
        "terms": terms,
        "phrases": phrases,
        "tags": tags,
        "seeds": seeds,
        "sections": list(dict.fromkeys(sections)),
        "status": list(dict.fromkeys(statuses)),
        "intent": intent,
        "hops": hops,
        "temporal": temporal,
    }

    return {
        "ok": True,
        "query": query,
        "structured": structured,
        "confidence": confidence,
        "evidence": evidence,
        "plan": _plan(structured),
    }


def _plan(structured: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Traduce la consulta a llamadas concretas de tools existentes.

    No las ejecuta: `vault_context_pack` es quien lo hace. Separar parseo de
    ejecución permite inspeccionar qué se va a consultar antes de consultarlo.
    """
    plan: List[Dict[str, Any]] = []

    search_terms = structured["phrases"] + structured["terms"] + structured["tags"]
    if search_terms:
        args: Dict[str, Any] = {"query": " ".join(search_terms[:8])}
        if structured["sections"]:
            args["section"] = structured["sections"][0]
        plan.append({"tool": "vault_search", "args": args,
                     "purpose": "recuperación léxica inicial"})

    if structured["seeds"]:
        plan.append({
            "tool": "vault_subgraph",
            "args": {"seeds": structured["seeds"], "hops": structured["hops"]},
            "purpose": "vecindario de las notas nombradas",
        })
    elif search_terms:
        plan.append({
            "tool": "vault_subgraph",
            "args": {"seeds": "<top-k de vault_search>", "hops": structured["hops"]},
            "purpose": "expandir el contexto desde los mejores resultados",
        })

    if structured["temporal"]:
        # La ventana temporal no se resuelve con una tool: se aplica como filtro
        # sobre `updatedAt` de los candidatos. Declararla como llamada a una
        # tool inexistente sería justo lo que prohíben AP-01/AP-04.
        plan.append({
            "filter": "updatedAt >= since",
            "args": {"since": structured["temporal"]["since"]},
            "purpose": "acotar a lo cambiado en la ventana temporal",
        })

    if structured["intent"] == "decision" and "03_Decisions" not in structured["sections"]:
        plan.append({"tool": "vault_search",
                     "args": {"query": " ".join(search_terms[:5]),
                              "section": "03_Decisions"},
                     "purpose": "la intención es una decisión: mirar ADRs"})

    return plan


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_query_parse — lenguaje natural → consulta estructurada",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_query_parse.py "que decidimos sobre el transporte MCP"
  python vault_query_parse.py "errores de la semana pasada en el proyecto ans"
  python vault_query_parse.py "#arquitectura contexto amplio de [[mcp-protocol]]"
  python vault_query_parse.py "what did we decide about auth" --explain

Notas:
  - Sin modelo ni embeddings: reglas lexicas sobre vocabularios del repo
  - Secciones derivadas de vault_registry.standard_folders()
  - `confidence` baja = conviene pedir aclaracion antes de responder
  - `plan` describe las llamadas; quien las ejecuta es vault_context_pack
""",
    )
    parser.add_argument("query", help="Pregunta en lenguaje natural")
    parser.add_argument("--explain", action="store_true",
                        help="Muestra la evidencia de cada campo inferido")
    parser.add_argument("--plan-only", action="store_true",
                        help="Emite solo el plan de tools")

    args = parser.parse_args()
    result = vault_query_parse(args.query)

    if result.get("ok"):
        if args.plan_only:
            result = {"ok": True, "plan": result["plan"]}
        elif not args.explain:
            result.pop("evidence", None)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_query_parse"))
