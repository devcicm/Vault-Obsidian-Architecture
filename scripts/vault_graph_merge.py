#!/usr/bin/env python3
"""
Vault Graph Merge Tool — Unifica wiki-links + entity relations + code relations

Lee los tres sistemas de relaciones del vault y genera graph-enriched.json
con predicados semanticos unificados basados en vault-ontology.json.

Sistemas mergeados:
  1. Wiki-links:        [[target]] en notas .md  →  predicate: "wiki_link"
  2. Entity relations:  06_Diagrams/entity/{project}-relations.json  →  predicates canon
  3. Code relations:    11_Code/.code-index.json  →  predicates canon

Tambien detecta: unknown_predicates, unresolved_entities, silo_flags.

Usage:
    python vault_graph_merge.py
    python vault_graph_merge.py --project "ans"
    python vault_graph_merge.py --predicate-filter depends_on,implements
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple

from vault_regex import RE_WIKILINK  # dueño único del patrón (AP-50)

from vault_errors import emit_error, wrap_main, proyecto_registrado
from vault_version import CURRENT_VERSION  # generator_version de los artefactos (AP-47)
from vault_io import atomic_write_json, normalize_stem, write_report
from vault_escaneo_grafo import escanear_wikilinks  # el único escaneo del grafo
from vault_lib import clave_de_nombre  # dueño único de la identidad por nombre (AP-57, AP-17)
from vault_registry import ORDERED_SECTIONS

ONTOLOGY_FILE = Path(__file__).parent / "vault_ontology.json"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.grafo.aristas import consolidar_aristas  # noqa: E402
from vault.grafo.repositorio import RepositorioGrafo  # noqa: E402
from vault.kernel import construir, proyectos as _proyectos  # noqa: E402
from vault.kernel.enumeracion import notas_en_disco  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioGrafo:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioGrafo(construir(root))


def _graph_file() -> Path:
    return _repo().grafo


def _enriched_file() -> Path:
    return _repo().grafo_enriquecido


def _entity_dir() -> Path:
    return _repo().dir_entidades


def _code_index() -> Path:
    return _repo().indice_codigo


def _move_log() -> Path:
    return _repo().bitacora_movimientos


# Derivado de `vault_registry`, no copiado: la copia literal se quedo en 18
# secciones y dejaba fuera `17_Preferences`, `18_Bugs`, `19_Audits` y
# `20_Quarantine` sin que nada fallara.
VAULT_SECTIONS = frozenset(ORDERED_SECTIONS)


def _load_ontology() -> Tuple[Dict[str, Any], str]:
    """`(ontología, origen)`: la del vault primero, la del paquete después.

    `vault_init` copia la ontología a `00_System/vault-ontology.json` para que
    cada vault pueda ajustarla; leer solo la de `__file__` dejaba esa copia sin
    consumidor. Sin ninguna de las dos el origen es `ausente` y el resultado lo
    dice: devolver `{}` a secas tipaba el grafo con cero predicados bajo un
    `ok: true` igual al de un grafo bien tipado (AP-51).
    """
    for origen, ruta in (
        ("vault", _repo().dir_sistema / "vault-ontology.json"),
        ("paquete", ONTOLOGY_FILE),
    ):
        if ruta.exists():
            return json.loads(ruta.read_text(encoding="utf-8")), origen
    return {}, "ausente"


def _is_vault_note(note_path: Path) -> bool:
    """superseded_by: vault.kernel.enumeracion.notas_en_disco — el escaneo ya no
    enumera con esto (AP-44). Se conserva el contrato por no-derogación."""
    try:
        parts = note_path.relative_to(_raiz()).parts
    except ValueError:
        return False
    if len(parts) < 2:
        return False
    return parts[0] in VAULT_SECTIONS


def _normalize_stem(s: str) -> str:
    # Identidad por nombre: la del dueño, no una copia (AP-57, AP-17).
    return normalize_stem(s)


def _extract_wiki_links(content: str) -> List[str]:
    return RE_WIKILINK.findall(content)


def _extract_title(content: str) -> Optional[str]:
    """superseded_by: vault_escaneo_grafo.escanear_wikilinks. Lee `title:` con un regex por
    líneas (AP-44); se conserva por contrato, ningún productor la usa ya."""
    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if m:
        t = re.search(r"^title:\s*(.+)$", m.group(1), re.MULTILINE)
        if t:
            return t.group(1).strip("\"'")
    return None


def _extract_tags(content: str) -> List[str]:
    """superseded_by: vault_escaneo_grafo.escanear_wikilinks. Lee `tags:` con un regex por
    líneas (AP-44); se conserva por contrato, ningún productor la usa ya."""
    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return []
    t = re.search(r"^tags:\s*(.+)$", m.group(1), re.MULTILINE)
    if not t:
        return []
    try:
        return json.loads(t.group(1))
    except json.JSONDecodeError:
        return []


def _folder_to_class(folder: str) -> str:
    """Clase de nodo del grafo para una sección.

    No es el `type:` de la nota y por eso no deriva de `SECTION_TYPES`: son dos
    vocabularios (`10_Migrated` escribe `type: documentation` y sus nodos son de
    clase `migrated`). Lo que sí tenía que ser completo es la cobertura — las
    cuatro secciones de v39 caían en `"unknown"`, así que sus notas entraban al
    grafo sin clase y quedaban fuera de todo recorrido por clase, en silencio.
    """
    mapping = {
        "00_System": "system", "01_Projects": "project", "02_Observability": "observability",
        "03_Decisions": "decision", "04_Sessions": "session", "05_Patterns": "pattern",
        "06_Diagrams": "diagram", "07_Knowledge": "knowledge", "08_Runbooks": "runbook",
        "09_Infrastructure": "infrastructure", "10_Migrated": "migrated", "11_Code": "code",
        "12_Bibliography": "bibliography", "13_Flows": "flow", "14_Requirements": "requirement",
        "15_Tests": "test", "16_AI_Governance": "ai_governance",
        "17_Preferences": "preference", "18_Bugs": "bug", "19_Audits": "audit",
        "20_Quarantine": "quarantine", "99_Index": "index",
    }
    return mapping.get(folder, "unknown")


def _build_node_class_index(ontology: Dict[str, Any]) -> Dict[str, str]:
    """Build folder → class_name mapping from ontology."""
    index = {}
    for class_name, cls in ontology.get("node_classes", {}).items():
        folder = cls.get("folder", "")
        if folder:
            index[folder] = class_name
    return index


# Cache para búsquedas fuzzy: evita repetir SequenceMatcher para el mismo
# entity name ya procesado. Key = (entity_norm, threshold), value = ruta o None.
# Vale solo para el stem_map del último índice: `_build_prefix_index` la vacía,
# porque la clave no nombra el vault y un segundo vault heredaba las rutas del
# primero (AP-49). El fallo se guarda como None y se distingue de la ausencia
# con `in`: con `.get() is not None` nunca se memoizaba.
_FUZZY_CACHE: Dict[Tuple[str, float], Optional[str]] = {}


def _build_prefix_index(stem_map: Dict[str, str]) -> Dict[str, List[Tuple[str, str]]]:
    """Construye índice inverso por prefijo (primeros 3 chars) para filtrado rápido.

    En lugar de iterar por TODAS las notas en cada búsqueda fuzzy (O n),
    se pre-filtra por prefijo común, reduciendo drásticamente los candidatos.
    """
    _FUZZY_CACHE.clear()
    prefix_index: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    for norm_stem, path in stem_map.items():
        prefix = norm_stem[:3] if len(norm_stem) >= 3 else norm_stem
        prefix_index[prefix].append((norm_stem, path))
    return prefix_index


def _fuzzy_resolve(
    entity_norm: str,
    stem_map: Dict[str, str],
    prefix_index: Dict[str, List[Tuple[str, str]]],
    threshold: float = 0.75,
) -> Optional[str]:
    """Resolución fuzzy O(k m) con pre-filtrado por prefijo y memoización.

    1. Memoización: si ya buscamos este entity_norm, retorna el resultado cacheado.
    2. Pre-filtrado: solo considera notas cuyo stem comparta los primeros 3 chars.
    3. Búsqueda: SequenceMatcher sobre los candidatos filtrados.

    Args:
        entity_norm: nombre de entidad ya normalizado
        stem_map: mapa de stems normalizados → paths
        prefix_index: índice por prefijo construido con _build_prefix_index
        threshold: umbral mínimo de similaridad (default 0.75)

    Returns:
        Path del mejor match o None si no supera el threshold.
    """
    cache_key = (entity_norm, threshold)
    if cache_key in _FUZZY_CACHE:
        return _FUZZY_CACHE[cache_key]

    # Longitud mínima para evitar matches ruidosos (entity_norm < 4 → skip)
    if len(entity_norm) < 4:
        _FUZZY_CACHE[cache_key] = None
        return None

    prefix = entity_norm[:3]
    candidates = prefix_index.get(prefix, [])
    # Si no hay candidatos con prefijo común, buscar en todos los stems (último recurso)
    if not candidates:
        candidates = [(ns, p) for ns, p in stem_map.items()]

    best_score = 0.0
    best_path = ""

    for norm_stem, cand_path in candidates:
        score = SequenceMatcher(None, entity_norm, norm_stem).ratio()
        if score > best_score and score >= threshold:
            best_score = score
            best_path = cand_path

    result = best_path if best_score >= threshold and best_path else None
    _FUZZY_CACHE[cache_key] = result
    return result


class _Identidades:
    """A qué nota se refiere un nombre, y lo que no llega a fijarlo (AP-17).

    `destinos` es el criterio de Obsidian para los wikilinks —nombre de
    fichero, sufijo de ruta y `aliases:`—; `por_clave` agrupa por
    `clave_de_nombre` los nombres de fichero y los alias, que es como se
    identifica a una entidad o a un fichero de código que no se escribió como
    enlace. `por_titulo` y la similitud solo sirven para **sugerir**: el
    `title:` no lo mira Obsidian y un parecido no es una identidad.
    """

    def __init__(self) -> None:
        self.destinos: Dict[str, List[str]] = {}
        self.por_clave: Dict[str, List[str]] = defaultdict(list)
        self.por_titulo: Dict[str, List[str]] = defaultdict(list)
        self.ambiguos: List[Dict] = []
        self.sugerencias: List[Dict] = []
        self._vistas: Set[Tuple] = set()

    def unicos(self) -> Dict[str, str]:
        """Clave → ruta de las claves con una sola nota: el universo del fuzzy."""
        return {clave: rutas[0] for clave, rutas in self.por_clave.items() if len(rutas) == 1}

    def sugerir(self, sugerencia: Dict) -> None:
        firma = (sugerencia["source"], sugerencia.get("from"), sugerencia["endpoint"])
        if firma not in self._vistas:
            self._vistas.add(firma)
            self.sugerencias.append(sugerencia)


def _build_wiki_link_graph() -> Tuple[Dict[str, Dict], List[Dict], List[Dict], "_Identidades"]:
    """Scan all .md notes and build wiki-link graph."""
    nodes: Dict[str, Dict] = {}
    edges: List[Dict] = []
    broken: List[Dict] = []
    identidades = _Identidades()
    contenidos: Dict[str, str] = {}

    # El mismo enumerador que `vault_graph` (AP-44, AP-57): el tramo oculto se
    # mide en la ruta relativa al vault, no en la de la máquina que lo aloja.
    all_files = notas_en_disco(_raiz(), ORDERED_SECTIONS)

    for p in all_files:
        rel = str(p.relative_to(_raiz())).replace("\\", "/")

        try:
            contenidos[rel] = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError, OSError):
            continue
        except Exception as exc:
            emit_error("vault_graph_merge", "FILE_READ_ERROR",
                      f"{rel}: {exc}")
            continue

    # El frontmatter, el índice de nombres y la resolución de los enlaces son
    # del escaneo único que comparte con `vault_graph` (AP-57): hasta ahora
    # `_extract_title`/`_extract_tags` leían con un regex por líneas y dejaban
    # vacías las etiquetas en lista de bloque, sin comillas o CRLF (AP-44).
    escaneo = escanear_wikilinks(contenidos)

    for rel, nota in escaneo["notas"].items():
        # Identidad: el nombre de fichero y los alias. El `title:` no fija
        # nada —Obsidian no lo mira— y solo se guarda para sugerir.
        clave = clave_de_nombre(Path(rel).stem)
        identidades.por_clave[clave].append(rel)
        for alias in nota["aliases"]:
            clave_alias = clave_de_nombre(alias)
            if rel not in identidades.por_clave[clave_alias]:
                identidades.por_clave[clave_alias].append(rel)
        clave_titulo = clave_de_nombre(nota["title"])
        if clave_titulo != clave:
            identidades.por_titulo[clave_titulo].append(rel)

        folder = rel.split("/")[0] if "/" in rel else ""
        nodes[rel] = {
            "path": rel,
            "title": nota["title"],
            "type": folder,
            "class": _folder_to_class(folder),
            "tags": nota["tags"],
            "linkCount": len(nota["links"]),
        }

    for rutas in (*identidades.por_clave.values(), *identidades.por_titulo.values()):
        rutas.sort()
    identidades.destinos = escaneo["indice"]
    identidades.ambiguos = escaneo["ambiguos"]

    edges = [
        {"from": a["from"], "to": a["to"], "predicate": "wiki_link", "source": "wikilinks"}
        for a in escaneo["aristas"]
    ]
    broken = escaneo["rotos"]
    for roto in broken:
        nombre = roto["link"].split("|")[0].split("#")[0].strip()
        clave = clave_de_nombre(nombre.replace("\\", "/").rsplit("/", 1)[-1])
        for criterio, indice in (("name_key", identidades.por_clave),
                                 ("title", identidades.por_titulo)):
            if indice.get(clave):
                identidades.sugerir({
                    "source": "wikilinks",
                    "from": roto["from"],
                    "endpoint": nombre,
                    "criterion": criterio,
                    "candidates": list(indice[clave]),
                })
                break

    return nodes, edges, broken, identidades


def _resolver_extremo(
    nombre: str,
    identidades: "_Identidades",
    prefix_index: Dict[str, List[Tuple[str, str]]],
    source: str,
) -> str:
    """La nota de un extremo de relación, o `""` y una sugerencia (AP-17).

    Solo una nota con la misma `clave_de_nombre` —en su nombre de fichero o
    en un alias— fija el extremo. Dos o más notas con la clave, un `title:`
    que coincide o un nombre parecido (`_fuzzy_resolve`) dejan el extremo sin
    resolver y lo publican en `suggestions`: confirmarlo es de quien conoce el
    vault, renombrando la entidad o añadiendo el alias.
    """
    clave = clave_de_nombre(nombre)
    candidatos = identidades.por_clave.get(clave, [])
    if len(candidatos) == 1:
        return candidatos[0]
    criterio = "ambiguous" if candidatos else ""
    if not candidatos and identidades.por_titulo.get(clave):
        candidatos, criterio = identidades.por_titulo[clave], "title"
    if not candidatos:
        similar = _fuzzy_resolve(clave, identidades.unicos(), prefix_index)
        if similar:
            candidatos, criterio = [similar], "similar"
    if candidatos:
        identidades.sugerir({
            "source": source,
            "endpoint": nombre,
            "criterion": criterio,
            "candidates": list(candidatos),
        })
    return ""


def _registrar_predicado_desconocido(
    desconocidos: Dict[Tuple[str, str, str], Dict],
    predicate: str,
    raw_predicate: str,
    source: str,
    valid_predicates: Set[str],
) -> None:
    """AP-32: el predicado fuera de la ontología se informa, no se corrige.

    `_closest_predicate` lo sustituía por el más parecido (ratio ≥ 0.5) y la
    lista era una variable local que nadie emitía: la arista afirmaba un
    predicado que el autor no escribió y el informe que el catálogo promete
    no existía. Lo parecido es una sugerencia (AP-17); se agrupa por
    predicado para que mil relaciones con la misma errata sean una entrada.
    """
    firma = (predicate, raw_predicate, source)
    entrada = desconocidos.get(firma)
    if entrada is None:
        desconocidos[firma] = {
            "predicate": predicate,
            "raw_predicate": raw_predicate,
            "source": source,
            "suggestion": _closest_predicate(predicate, valid_predicates),
            "occurrences": 1,
        }
    else:
        entrada["occurrences"] += 1


def _merge_entity_relations(
    ontology: Dict[str, Any],
    identidades: "_Identidades",
    desconocidos: Optional[Dict[Tuple[str, str, str], Dict]] = None,
) -> List[Dict]:
    """Read entity relations and convert to enriched edges."""
    edges: List[Dict] = []
    unresolved: List[Dict] = []
    if desconocidos is None:
        desconocidos = {}

    valid_predicates = set(ontology.get("predicates", {}).keys())
    synonym_map = ontology.get("predicate_synonyms", {})

    if not _entity_dir().exists():
        return edges

    # Construir índice de prefijo UNA VEZ para todas las búsquedas fuzzy
    # (antes se hacía O(n) por cada relación no resuelta → ahora O(1) amortizado)
    prefix_index = _build_prefix_index(identidades.unicos())

    for rel_file in _entity_dir().glob("*relations.json"):
        try:
            raw = rel_file.read_bytes()
            if raw.startswith(b"\xef\xbb\xbf"):
                raw = raw[3:]
            text = raw.decode("utf-8")
            data = json.loads(text)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue
        except Exception as exc:
            emit_error("vault_graph_merge", "ENTITY_PARSE_ERROR",
                      f"{rel_file.name}: {exc}")
            continue

        project = data.get("project", "unknown")
        for rel in data.get("relations", []):
            # AP-33 se aplica en esta línea: las relaciones de entidad usan
            # `relationType` y las de código `type` para el mismo concepto, así
            # que el predicado se normaliza contra `predicate_synonyms` antes de
            # compararlo. Sin este paso, un sinónimo legítimo saldría como AP-32.
            raw_predicate = rel.get("relationType", "wiki_link")
            predicate = synonym_map.get(raw_predicate, raw_predicate)

            from_entity = rel.get("fromEntity", "")
            to_entity = rel.get("toEntity", "")
            from_path = _resolver_extremo(from_entity, identidades, prefix_index, "entity_relations")
            to_path = _resolver_extremo(to_entity, identidades, prefix_index, "entity_relations")

            unresolved_parts = []
            if not from_path:
                unresolved_parts.append(from_entity)
            if not to_path:
                unresolved_parts.append(to_entity)
            if unresolved_parts:
                unresolved.append({
                    "fromEntity": from_entity,
                    "toEntity": to_entity,
                    "predicate": predicate,
                    "missing_endpoints": unresolved_parts,
                    "source_file": str(rel_file.relative_to(_raiz())).replace("\\", "/"),
                })

            # AP-32: el predicado ya normalizado tampoco existe en la ontología.
            # Se reportan los dos —`predicate` y `raw_predicate`— porque sin el
            # crudo no se puede saber si el fallo fue del autor o del mapa de
            # sinónimos, que es lo que el consumidor necesita para arreglarlo.
            predicate_known = predicate in valid_predicates
            if not predicate_known:
                _registrar_predicado_desconocido(
                    desconocidos, predicate, raw_predicate, "entity", valid_predicates
                )

            edge = {
                "from": from_path or from_entity,
                "to": to_path or to_entity,
                "predicate": predicate,
                "predicate_known": predicate_known,
                "source": "entity_relations",
                "project": project,
                "cardinality": rel.get("cardinality"),
                "label": rel.get("label"),
                "entity_type": rel.get("entityType"),
                "endpoint_resolved": bool(from_path and to_path),
            }
            edges.append(edge)

    return edges


def _merge_code_relations(
    ontology: Dict[str, Any],
    identidades: "_Identidades",
    desconocidos: Optional[Dict[Tuple[str, str, str], Dict]] = None,
) -> List[Dict]:
    """Read code relations and convert to enriched edges."""
    edges: List[Dict] = []
    unresolved: List[Dict] = []
    if desconocidos is None:
        desconocidos = {}

    valid_predicates = set(ontology.get("predicates", {}).keys())
    synonym_map = ontology.get("predicate_synonyms", {})

    if not _code_index().exists():
        return edges

    # Construir índice de prefijo UNA VEZ para todas las búsquedas fuzzy
    prefix_index = _build_prefix_index(identidades.unicos())

    try:
        raw = _code_index().read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        text = raw.decode("utf-8")
        data = json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        emit_error("vault_graph_merge", "CODE_INDEX_PARSE_ERROR", str(exc))
        return edges
    except Exception as exc:
        emit_error("vault_graph_merge", "UNEXPECTED_ERROR", str(exc))
        return edges

    for rel in data.get("relations", []):
        raw_predicate = rel.get("type", "wiki_link")
        predicate = synonym_map.get(raw_predicate, raw_predicate)

        from_file = rel.get("from", "")
        to_file = rel.get("to", "")

        from_path = _resolver_extremo(Path(from_file).stem, identidades, prefix_index, "code_relations")
        to_path = _resolver_extremo(Path(to_file).stem, identidades, prefix_index, "code_relations")

        unresolved_parts = []
        if not from_path:
            unresolved_parts.append(from_file)
        if not to_path:
            unresolved_parts.append(to_file)
        if unresolved_parts:
            unresolved.append({
                "fromFile": from_file,
                "toFile": to_file,
                "predicate": predicate,
                "missing_endpoints": unresolved_parts,
            })

        predicate_known = predicate in valid_predicates
        if not predicate_known:
            _registrar_predicado_desconocido(
                desconocidos, predicate, raw_predicate, "code", valid_predicates
            )

        edge = {
            "from": from_path or from_file,
            "to": to_path or to_file,
            "predicate": predicate,
            "predicate_known": predicate_known,
            "source": "code_relations",
            "project": rel.get("project", ""),
            "cardinality": rel.get("cardinality"),
            "label": rel.get("label"),
            "endpoint_resolved": bool(from_path and to_path),
        }
        edges.append(edge)

    return edges


def _closest_predicate(predicate: str, valid: Set[str]) -> Optional[str]:
    """El predicado válido más parecido: solo para `suggestion`, nunca se aplica (AP-32)."""
    best = None
    best_score = 0.0
    for v in valid:
        score = SequenceMatcher(None, predicate, v).ratio()
        if score > best_score:
            best_score = score
            best = v
    return best if best_score >= 0.5 else None


def _detect_orphans(nodes: Dict[str, Dict], edges: List[Dict]) -> List[Dict]:
    in_degree = defaultdict(int)
    for e in edges:
        if e.get("endpoint_resolved", True):
            in_degree[e["to"]] += 1

    orphans = []
    for path, node in nodes.items():
        if path.startswith("00_System/") or path.startswith("04_Sessions/"):
            continue
        if in_degree.get(path, 0) == 0:
            orphans.append({"path": path, "title": node.get("title", ""), "type": node.get("type", "")})
    return orphans


def _detect_silos() -> Dict[str, bool]:
    """AP-35: detect if entity/code relations exist but haven't been merged."""
    flags = {}
    entity_files = list(_entity_dir().glob("*relations.json")) if _entity_dir().exists() else []
    flags["entity_relations_exist"] = len(entity_files) > 0
    flags["code_relations_exist"] = _code_index().exists()

    if _enriched_file().exists():
        try:
            enriched = json.loads(_enriched_file().read_text(encoding="utf-8"))
            last_merge = enriched.get("metadata", {}).get("merged_at", "")
            if last_merge:
                dt = datetime.fromisoformat(last_merge.replace("Z", "+00:00"))
                hours_old = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
                flags["graph_enriched_hours_old"] = round(hours_old, 1)
                flags["graph_enriched_stale"] = hours_old > 24
        except (json.JSONDecodeError, ValueError, OSError):
            pass
        except Exception as exc:
            emit_error("vault_graph_merge", "ENRICHED_PARSE_ERROR", str(exc))
    else:
        flags["graph_enriched_exists"] = False

    return flags


def _build_predicate_topology(edges: List[Dict]) -> Dict[str, int]:
    """Count edges by predicate type for health scoring."""
    counts = defaultdict(int)
    for e in edges:
        counts[e.get("predicate", "wiki_link")] += 1
    return dict(counts)


def vault_graph_merge(
    project: Optional[str] = None,
    predicate_filter: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Unifica los tres sistemas de relaciones en graph-enriched.json.

    Args:
        project: Optional project slug to filter scope.
        predicate_filter: Optional list of predicates to include (e.g. ['depends_on', 'implements']).

    Returns:
        Dict with nodes, edges, stats, diagnostics, and metadata.
    """
    es_del = _proyectos.pertenencia_en(_raiz(), project)
    ontology, ontology_source = _load_ontology()

    nodes, wiki_edges, broken_links, identidades = _build_wiki_link_graph()

    # Una arista por relación (from, predicate, to): por fuente, para que las
    # métricas de cada una cuenten relaciones, y después el conjunto.
    wiki_edges = consolidar_aristas(wiki_edges)
    desconocidos: Dict[Tuple[str, str, str], Dict] = {}
    entity_edges = consolidar_aristas(_merge_entity_relations(ontology, identidades, desconocidos))
    code_edges = consolidar_aristas(_merge_code_relations(ontology, identidades, desconocidos))
    unknown_predicates = list(desconocidos.values())

    all_edges = consolidar_aristas(wiki_edges + entity_edges + code_edges)

    if project:
        all_edges = [
            e for e in all_edges
            if es_del(e.get("project")) or e.get("source") == "wikilinks"
        ]

    if predicate_filter:
        predicates_set = set(predicate_filter)
        all_edges = [e for e in all_edges if e.get("predicate") in predicates_set]

    orphans = _detect_orphans(nodes, all_edges)
    predicate_counts = _build_predicate_topology(all_edges)
    silo_flags = _detect_silos()

    deleted_nodes = 0
    if _graph_file().exists():
        try:
            old = json.loads(_graph_file().read_text(encoding="utf-8"))
            for old_path in old.get("nodes", {}):
                if old_path not in nodes:
                    all_edges.append({
                        "from": old_path,
                        "to": "__deleted__",
                        "predicate": "deleted_node",
                        "source": "graph_history",
                    })
                    deleted_nodes += 1
        except (json.JSONDecodeError, OSError):
            pass
        except Exception as exc:
            emit_error("vault_graph_merge", "GRAPH_HISTORY_ERROR", str(exc))

    resolved_entity = len([e for e in entity_edges if e.get("endpoint_resolved")])
    unresolved_entity = len(entity_edges) - resolved_entity
    resolved_code = len([e for e in code_edges if e.get("endpoint_resolved")])
    unresolved_code = len(code_edges) - resolved_code

    class_index = _build_node_class_index(ontology)
    for path, node in nodes.items():
        folder_derived = _folder_to_class(node.get("type", ""))
        node["class"] = class_index.get(node["type"], folder_derived)
        node["status"] = node.get("status", "active")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    total_edges = len(all_edges)
    typed_edges = len([e for e in all_edges if e.get("predicate") != "wiki_link"])

    enriched = {
        "metadata": {
            "version": "v37",
            "generator_version": CURRENT_VERSION,
            "merged_at": now_iso,
            "ontology_version": ontology.get("version", "unknown"),
            "ontology_source": ontology_source,
            "total_edges": total_edges,
            "wiki_edges": len(wiki_edges),
            "entity_edges": len(entity_edges),
            "code_edges": len(code_edges),
            "typed_edges": typed_edges,
            "predicate_counts": predicate_counts,
        },
        "nodes": nodes,
        "edges": all_edges,
        "stats": {
            "totalNodes": len(nodes),
            "totalEdges": total_edges,
            "typedEdges": typed_edges,
            "orphanNotes": len(orphans),
            "brokenWikiLinks": len(broken_links),
            "ambiguousLinks": len(identidades.ambiguos),
            "suggestions": len(identidades.sugerencias),
            "unknownPredicates": len(unknown_predicates),
            "deletedNodes": deleted_nodes,
            "predicateCounts": predicate_counts,
        },
        "orphans": orphans,
        "brokenLinks": broken_links,
        "ambiguousLinks": identidades.ambiguos,
        "suggestions": identidades.sugerencias,
        "unknownPredicates": unknown_predicates,
        "diagnostics": {
            "entity_relations": {
                "total": len(entity_edges),
                "resolved": resolved_entity,
                "unresolved": unresolved_entity,
            },
            "code_relations": {
                "total": len(code_edges),
                "resolved": resolved_code,
                "unresolved": unresolved_code,
            },
            "silo_flags": silo_flags,
        },
    }

    _enriched_file().parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(_enriched_file(), enriched)

    next_actions = []
    if ontology_source == "ausente":
        next_actions.append(
            "Sin ontología: ni 00_System/vault-ontology.json ni la del paquete "
            "existen, así que ninguna relación se tipó contra predicados válidos "
            "(AP-51). Ejecutar vault_init o reinstalar el toolkit."
        )
    if unresolved_entity > 0:
        next_actions.append(
            f"{unresolved_entity} entity relations con endpoints no resueltos (AP-34). "
            "Ejecutar vault_search para verificar que las entidades existen como notas del vault."
        )
    if unresolved_code > 0:
        next_actions.append(
            f"{unresolved_code} code relations con endpoints no resueltos (AP-34). "
            "Verificar que los modulos de codigo esten documentados en 11_Code/."
        )
    if identidades.ambiguos or identidades.sugerencias:
        next_actions.append(
            f"{len(identidades.ambiguos)} enlaces ambiguos y {len(identidades.sugerencias)} "
            "sugerencias de identidad (AP-17): un nombre parecido, un title: o dos notas "
            "con el mismo nombre no crean arista. Confirmar con la carpeta en el enlace, "
            "un alias o renombrando; ver suggestions en graph-enriched.json."
        )
    if unknown_predicates:
        next_actions.append(
            f"{len(unknown_predicates)} predicados fuera de la ontología (AP-32): la arista "
            "conserva el que se escribió y la suggestion de unknownPredicates no se aplica. "
            "Corregir el relationType/type o añadirlo a predicate_synonyms."
        )
    if typed_edges == 0 and (entity_edges or code_edges):
        next_actions.append(
            "El grafo tiene entity/code relations pero 0 edges tipados (AP-31). "
            "Verificar que el nombre de cada entidad coincida con el de su nota o con un alias."
        )
    if silo_flags.get("graph_enriched_stale"):
        next_actions.append(
            f"graph-enriched.json tiene {silo_flags.get('graph_enriched_hours_old', '?')}h de antiguedad (AP-35). "
            "Recomendado: ejecutar vault_graph_merge al final de cada sesion."
        )

    return {
        "ok": True,
        **write_report(),
        "savedTo": str(_enriched_file().relative_to(_raiz())).replace("\\", "/"),
        "metadata": enriched["metadata"],
        "stats": enriched["stats"],
        "diagnostics": enriched["diagnostics"],
        "nextActions": next_actions,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Graph Merge — unify wiki-links + entity + code relations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_graph_merge.py
  python vault_graph_merge.py --project "ans"
  python vault_graph_merge.py --predicate-filter depends_on,implements,calls

Notas:
  - Genera 99_Index/graph-enriched.json con predicados semanticos unificados
  - Detecta unknown_predicates, unresolved_entities (AP-34), y silos (AP-35)
  - La ontologia se define en vault_ontology.json
""",
    )
    parser.add_argument("--project", type=proyecto_registrado("vault_graph_merge"), help="Optional project slug to filter scope")
    parser.add_argument(
        "--predicate-filter",
        help="Comma-separated list of predicates to include (e.g. depends_on,implements)",
    )
    args = parser.parse_args()

    predicate_filter = None
    if args.predicate_filter:
        predicate_filter = [p.strip() for p in args.predicate_filter.split(",")]

    result = vault_graph_merge(
        project=args.project,
        predicate_filter=predicate_filter,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_graph_merge"))
