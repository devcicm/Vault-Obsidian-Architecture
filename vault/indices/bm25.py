"""Full-text lexical ranking: Okapi BM25 with the standard library.

`vault_search` scored a note by its title, tags and the 200-character preview
stored in `search-index.json`: a word in the fourth paragraph of a note did
not exist for the search. BM25 needs per-note term frequencies and lengths;
this module computes them when the index row is built (producer:
`vault.indices.reconstruccion`) and scores a query against them (consumer:
`vault_search`, through `RepositorioAutoria`). One tokenizer for both sides,
here, so the index and the query can never disagree on what a term is (AP-57).

No database, no embeddings, no external service: the statistics are plain
JSON in the index the vault already has, and the formula is twelve lines.

The title counts twice (`PESO_TITULO`): a query that names a note is the most
common question an agent asks, and the old ranking weighted the title above
everything for the same reason.
"""

from __future__ import annotations

import math
import re
from typing import Dict, Iterable, List, Mapping, Sequence

from ..kernel.normalizacion import fold_accents

#: Okapi BM25 defaults (Robertson & Zaragoza). Declared, not calibrated here.
K1 = 1.2
B = 0.75
#: How many times the title is counted in the document text.
PESO_TITULO = 2
#: Terms shorter than this carry no meaning on their own ("a", "de", "y").
LONGITUD_MINIMA = 2

_RE_TERMINO = re.compile(r"\w+", re.UNICODE)


def tokenizar(texto: str) -> List[str]:
    """The terms of a text, in order, as both the index and the query see them.

    Folded the way `vault_search` compares text (`fold_accents` + casefold):
    «Configuración» and «configuracion» are the same term.
    """
    return [t for t in _RE_TERMINO.findall(fold_accents(texto or "").casefold())
            if len(t) >= LONGITUD_MINIMA and not t.isdigit()]


def estadisticas(titulo: str, cuerpo: str) -> Dict[str, object]:
    """`{"terms": {term: tf}, "length": n}` for one note's index row."""
    terminos = tokenizar(" ".join([titulo or ""] * PESO_TITULO + [cuerpo or ""]))
    frecuencias: Dict[str, int] = {}
    for t in terminos:
        frecuencias[t] = frecuencias.get(t, 0) + 1
    return {"terms": dict(sorted(frecuencias.items())), "length": len(terminos)}


def puntuar(consulta: str, filas: Sequence[Mapping[str, object]]) -> Dict[str, float]:
    """BM25 score per note path for `consulta`; only notes with a score > 0.

    Rows without statistics (an index written before this module) score 0
    and are simply absent: the caller decides what to do with them, and a
    `vault_reindex` brings them in.
    """
    terminos = list(dict.fromkeys(tokenizar(consulta)))
    con_datos = [f for f in filas if isinstance(f.get("terms"), dict)]
    n = len(con_datos)
    if not terminos or not n:
        return {}
    media = sum(int(f.get("length") or 0) for f in con_datos) / n or 1.0
    df = {t: sum(1 for f in con_datos if t in f["terms"]) for t in terminos}
    puntos: Dict[str, float] = {}
    for fila in con_datos:
        tf_fila = fila["terms"]
        longitud = int(fila.get("length") or 0)
        total = 0.0
        for t in terminos:
            tf = tf_fila.get(t, 0)
            if not tf:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            total += idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * longitud / media))
        if total > 0:
            puntos[str(fila.get("path", ""))] = round(total, 6)
    return puntos


def faltan_estadisticas(filas: Iterable[Mapping[str, object]]) -> int:
    """How many rows predate the statistics (a reindex adds them)."""
    return sum(1 for f in filas if not isinstance(f.get("terms"), dict))
