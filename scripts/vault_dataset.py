#!/usr/bin/env python3

"""

Vault Dataset - Gestión de keywords y búsqueda avanzada tipo LINQ

"""

import sys

from vault_errors import emit_error, wrap_main

import json

import re

import argparse

from pathlib import Path

from datetime import datetime, timezone

from collections import Counter, defaultdict


try:
    import nltk

    from nltk.corpus import stopwords

    from nltk.tokenize import word_tokenize

    from nltk.stem import SnowballStemmer

    NLTK_AVAILABLE = True

except ImportError:
    NLTK_AVAILABLE = False


# Default dictionary keywords (generic — extend via --keywords for project-specific terms)

DEFAULT_KEYWORDS = [
    "deploy",
    "runner",
    "vault",
    "node",
    "server",
    "docker",
    "container",
    "infrastructure",
    "automation",
    "orchestration",
    "config",
    "policy",
    "security",
    "vault",
    "ssh",
    "scp",
    "health",
    "retry",
    "circuit",
]


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _keywords_file() -> Path:
    return _repo().indice_palabras


def _notes_file() -> Path:
    return _repo().notas_palabras


def get_nltk_stopwords():
    """Inicializar stopwords de NLTK"""

    if not NLTK_AVAILABLE:
        return set()

    try:
        stop_words = set(stopwords.words("english"))

        stop_words.update(set(stopwords.words("spanish")))

        return stop_words

    except LookupError:
        nltk.download("stopwords", quiet=True)

        try:
            stop_words = set(stopwords.words("english"))

            stop_words.update(set(stopwords.words("spanish")))

            return stop_words

        except LookupError:
            return {
                "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
                "for", "of", "with", "by", "from",
                "el", "la", "los", "las", "y", "e", "o", "que",
            }

    except Exception:
        return {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "from",
            "el", "la", "los", "las", "y", "e", "o", "que",
        }


def extract_keywords_nltk(content: str) -> list:
    """Extraer keywords usando NLTK"""

    if not NLTK_AVAILABLE:
        return []

    stop_words = get_nltk_stopwords()

    # Limpiar contenido

    content = re.sub(r"```[\s\S]*?```", "", content)

    content = re.sub(r"\[\[([^\]]+)\]\]", r"\1", content)

    content = re.sub(r"[^\w\s]", " ", content.lower())

    # Tokenizar

    try:
        tokens = word_tokenize(content)

    except LookupError:
        nltk.download("punkt", quiet=True)

        try:
            tokens = word_tokenize(content)

        except LookupError:
            tokens = content.split()

    except Exception:
        tokens = content.split()

    # Filtrar

    keywords = []

    for token in tokens:
        token = token.lower()

        if len(token) > 3 and token not in stop_words and token.isalpha():
            keywords.append(token)

    return keywords


def extract_keywords_dict(content: str, custom_keywords: list = None) -> list:
    """Extraer keywords usando diccionario"""

    keywords = custom_keywords or DEFAULT_KEYWORDS

    content_lower = content.lower()

    found = []

    for kw in keywords:
        if kw.lower() in content_lower:
            found.append(kw.lower())

    return found


def calculate_tf_idf(keywords_by_file: dict) -> dict:
    """Calcular TF-IDF simplificado"""

    N = len(keywords_by_file)

    # Contar documentos por keyword

    doc_freq = Counter()

    for file_keywords in keywords_by_file.values():
        for kw in set(file_keywords):
            doc_freq[kw] += 1

    # Calcular IDF

    idf = {}

    for kw, df in doc_freq.items():
        idf[kw] = 1 + (N / (df + 1))

    # Calcular TF-IDF por documento

    tfidf = {}

    for filename, keywords in keywords_by_file.items():
        kw_count = Counter(keywords)

        tf = {}

        for kw, count in kw_count.items():
            tf[kw] = count * idf.get(kw, 1)

        # Normalizar

        total = sum(tf.values())

        if total > 0:
            tfidf[filename] = {k: round(v / total, 3) for k, v in tf.items()}

        else:
            tfidf[filename] = {}

    return tfidf


def extract_all(mode: str = "nltk", custom_keywords: list = None):
    """Extraer keywords de todas las notas"""

    stop_words = get_nltk_stopwords() if mode == "nltk" else set()

    keywords_global = Counter()

    keywords_by_file = {}

    notes_data = {}

    notes = [
        n
        for n in _raiz().rglob("*.md")
        if ".history" not in str(n) and not n.name.startswith("_")
    ]

    for md in notes:
        try:
            content = md.read_text(encoding="utf-8", errors="ignore")

            # Extraer keywords según modo

            if mode == "nltk":
                keywords = extract_keywords_nltk(content)

            else:
                keywords = extract_keywords_dict(content, custom_keywords)

            if not keywords:
                continue

            # Agregar al contador global

            keywords_global.update(keywords)

            keywords_by_file[str(md.relative_to(_raiz()))] = keywords

            # Datos de la nota

            title = md.stem.replace("-", " ").title()

            notes_data[str(md.relative_to(_raiz()))] = {
                "title": title,
                "keywords": keywords,
                "path": str(md.relative_to(_raiz())),
            }

        except (OSError, UnicodeDecodeError, PermissionError):
            pass  # Skip unreadable files gracefully
        except Exception as exc:
            emit_error("vault_dataset", "KEYWORD_EXTRACTION_ERROR",
                      f"{md.name}: {exc}")

    # Calcular TF-IDF

    tfidf = calculate_tf_idf(keywords_by_file)

    # Agregar scores a notes_data

    for filename, scores in tfidf.items():
        if filename in notes_data:
            score = sum(scores.values()) / len(scores) if scores else 0

            notes_data[filename]["score"] = round(score, 3)

            notes_data[filename]["tfidf"] = scores

    return {"keywords": dict(keywords_global), "notes": notes_data}


def search_keywords(
    query: str,
    operator: str = "OR",
    folder: str = None,
    min_score: float = 0,
    top: int = 20,
    mode: str = "nltk",
):
    """Buscar por keywords con filtros tipo LINQ"""

    if not _keywords_file().exists():
        print("Keywords not indexed. Run: python vault_dataset.py extract")

        return

    data = json.loads(_notes_file().read_text(encoding="utf-8"))

    notes = data.get("notes", {})

    # Query keywords

    query_kw = [k.strip().lower() for k in query.split()]

    results = []

    for filename, note_data in notes.items():
        # Filter by folder

        if folder and folder not in filename:
            continue

        note_keywords = note_data.get("keywords", [])

        score = note_data.get("score", 0)

        # Filter by score

        if score < min_score:
            continue

        # Match según operador

        if operator == "AND":
            match = all(qk in note_keywords for qk in query_kw)

        elif operator == "OR":
            match = any(qk in note_keywords for qk in query_kw)

        else:  # AND NOT
            match = any(qk in note_keywords for qk in query_kw)

            match = not match

        if match:
            results.append(
                {
                    "path": filename,
                    "title": note_data.get("title", ""),
                    "keywords": note_keywords,
                    "score": score,
                    "match_count": len([k for k in query_kw if k in note_keywords]),
                }
            )

    # Ordenar por score

    results.sort(key=lambda x: x["score"], reverse=True)

    return results[:top]


def list_keywords(limit: int = 30):
    """Listar keywords globales"""

    if not _notes_file().exists():
        print("Keywords not indexed. Run: python vault_dataset.py extract")

        return

    data = json.loads(_notes_file().read_text(encoding="utf-8"))

    keywords = data.get("keywords", {})

    print(f"=== KEYWORDS ({len(keywords)}) ===")

    for kw, info in sorted(keywords.items(), key=lambda x: -x[1].get("count", 0))[
        :limit
    ]:
        print(
            f"  {kw}: {info.get('count', 0)} files, weight: {info.get('weight', 0):.2f}"
        )


def save_index(data: dict):
    """Guardar índice de keywords"""

    # keywords-index.json

    keywords_info = {}

    for kw, count in data["keywords"].items():
        weight = count / len(data["notes"]) if data["notes"] else 0

        keywords_info[kw] = {"count": count, "weight": round(weight, 3)}

    index_data = {
        "version": "1.0",
        "mode": "nltk" if NLTK_AVAILABLE else "dictionary",
        "updatedAt": datetime.now(timezone.utc).isoformat()[:19] + "Z",
        "keywords": keywords_info,
    }

    _keywords_file().parent.mkdir(parents=True, exist_ok=True)

    _keywords_file().write_text(json.dumps(index_data, indent=2), encoding="utf-8")

    # notes-keywords.json (para búsqueda rápida)

    notes_data = {}

    for filename, note_data in data.get("notes", {}).items():
        notes_data[filename] = {
            "title": note_data.get("title", ""),
            "keywords": note_data.get("keywords", []),
            "score": note_data.get("score", 0),
            "tfidf": note_data.get("tfidf", {}),
        }

    _notes_file().parent.mkdir(parents=True, exist_ok=True)

    _notes_file().write_text(json.dumps(notes_data, indent=2), encoding="utf-8")

    return {"keywords": len(keywords_info), "notes": len(notes_data)}


def main():
    parser = argparse.ArgumentParser(
        description="Vault Dataset - Keywords",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_dataset.py extract

  python vault_dataset.py extract --mode dictionary --keywords deploy ansible proxmox

  python vault_dataset.py search --query "ansible deploy"

  python vault_dataset.py search --query "docker" --operator AND --folder "09_Infrastructure" --top 10

  python vault_dataset.py search --query "obsoleto" --operator NOT --min-score 0.1

  python vault_dataset.py keywords --top 50

  python vault_dataset.py index



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Primero ejecutar 'extract' para construir el indice de keywords

  - Modo 'nltk' requiere la libreria nltk instalada; fallback a 'dictionary' si no esta disponible

  - Los indices se guardan en 99_Index/keywords-index.json y 99_Index/notes-keywords.json

""",
    )

    parser.add_argument(
        "command", choices=["extract", "search", "keywords", "index"], help="Comando"
    )

    parser.add_argument("--query", "-q", help="Query de busqueda")

    parser.add_argument(
        "--mode",
        "-m",
        choices=["nltk", "dictionary"],
        default="nltk" if NLTK_AVAILABLE else "dictionary",
        help="Modo de extraccion",
    )

    parser.add_argument(
        "--operator",
        "-o",
        choices=["AND", "OR", "NOT"],
        default="OR",
        help="Operador logico",
    )

    parser.add_argument("--folder", "-f", help="Filtrar por carpeta")

    parser.add_argument("--min-score", "-s", type=float, default=0, help="Score minimo")

    parser.add_argument("--top", "-t", type=int, default=20, help="Top resultados")

    parser.add_argument("--keywords", "-k", nargs="+", help="Keywords personalizadas")

    args = parser.parse_args()

    if args.command == "extract":
        print(f"Extracting keywords (mode: {args.mode})...")

        if args.mode == "nltk" and not NLTK_AVAILABLE:
            print("NLTK not installed. Installing...")

            try:
                import nltk

                nltk.download("punkt", quiet=True)

                nltk.download("stopwords", quiet=True)

            except Exception:
                print("NLTK not available. Using dictionary mode.")

                args.mode = "dictionary"

        custom_kw = args.keywords if args.keywords else None

        data = extract_all(args.mode, custom_kw)

        result = save_index(data)

        print(f"Keywords: {result['keywords']}")

        print(f"Notes: {result['notes']}")

        print(f"Index: {_keywords_file().name}, {_notes_file().name}")

    elif args.command == "search":
        if not args.query:
            print("Error: --query requerido")

            return

        results = search_keywords(
            args.query,
            operator=args.operator,
            folder=args.folder,
            min_score=args.min_score,
            top=args.top,
            mode=args.mode,
        )

        print(f"=== SEARCH: {args.query} ({args.operator}) ===")

        for r in results:
            print(f"\n[{r['title']}]")

            print(f"  {r['path']}")

            print(
                f"  Score: {r.get('score', 0):.3f}, Matches: {r.get('match_count', 0)}"
            )

            print(f"  Keywords: {', '.join(r.get('keywords', [])[:5])}")

    elif args.command == "keywords":
        list_keywords(args.top)

    elif args.command == "index":
        if not _keywords_file().exists():
            print("Run extract first")

            return

        print(f"Index: {_keywords_file().name}")


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_dataset"))
