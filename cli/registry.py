"""registry — índice consolidado de tools, tratadas como fragmentos buscables.

Cada tool es un fragmento: un trozo de funcionalidad con nombre estable, grupo,
contrato de argumentos y side-effects declarados. Este módulo los indexa para
que sean localizables por nombre, grupo, propósito, argumento, guard o efecto.

Fuente de verdad (no se duplica, se lee):
  - scripts/vault_mcp_catalog.py :: TOOLS_CATALOG   → grupo, propósito, params
  - <vault>/00_System/tool-spec.json               → required_args, status
El registro NO inventa tools: si un fragmento no existe en el catálogo, no
existe en la CLI (AP-01/AP-04 — nada de documentación alucinada).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# Verbos que identifican un fragmento de solo lectura cuando el catálogo no
# declara side-effects. Conservador: ante la duda se clasifica como escritura,
# porque una escritura tratada como lectura es una corrupción silenciosa.
_READ_VERBS = (
    "read", "list", "search", "get", "query", "check", "inspect", "map",
    "overview", "status", "count", "audit", "validate", "detect", "scan",
    "diff", "export", "timeline", "counter",
)

# Artefactos compartidos que varias tools tocan. Están protegidos por
# vault_io.file_lock() + escritura atómica, así que admiten concurrencia:
# el scheduler los registra pero NO serializa por ellos. El analyzer verifica
# que esa premisa siga siendo cierta (RC-01) — si alguien escribe uno de estos
# sin lock, el escáner lo reporta y esta lista deja de ser segura.
# Rutas verificadas contra el vault real (vault-sandbox) y contra las
# constantes de los scripts — no supuestas: los índices de grafo y búsqueda
# viven en 99_Index/, no en 00_System/.
GUARDED_ARTIFACTS = frozenset({
    "99_Index/graph.json",
    "99_Index/graph-enriched.json",
    "99_Index/search-index.json",
    "99_Index/hash-index.json",
    "00_System/quality-index.json",
    "00_System/tools-manifest.json",
    "00_System/.change-log.json",
    "00_System/.tool-trace.json",
    "00_System/tags-index.json",
    "99_Index/index.md",
})

# Tools sin script Python: implementadas de forma nativa en el servidor MCP
# (mcp/nodejs/vault-mcp-server.mjs). No son fragmentos ausentes — son fragmentos
# de otro runtime. Distinguirlas evita reportar un AP-04 falso.
#
# v40.17 — deja de ser una segunda declaración. El mismo conjunto estaba escrito
# aquí, en el `.mjs` y en ningún sitio que los comparase: AP-05 a través de una
# frontera de lenguaje. El dueño es `vault_mcp_catalog.NATIVE_JS_TOOLS`, que lo
# emite a `tools-catalog.json` para que el servidor lo lea; el literal de abajo
# solo se usa si este repo no está importable desde el consumidor, y
# `vault_mcp_catalog --check` falla si alguna de las tres copias diverge.
try:  # pragma: no cover - depende de dónde se instale la CLI
    from vault_mcp_catalog import NATIVE_JS_TOOLS  # type: ignore
except ImportError:  # respaldo verificado por el guard, no una segunda verdad
    NATIVE_JS_TOOLS = frozenset({"vault_backup_base64", "vault_restore_base64"})

_ARTIFACT_HINTS = {
    "graph-enriched": "99_Index/graph-enriched.json",
    "graph": "99_Index/graph.json",
    "search-index": "99_Index/search-index.json",
    "search index": "99_Index/search-index.json",
    "hash-index": "99_Index/hash-index.json",
    "quality-index": "00_System/quality-index.json",
    "change-log": "00_System/.change-log.json",
    "change log": "00_System/.change-log.json",
    "changelog": "00_System/.change-log.json",
    "trace": "00_System/.tool-trace.json",
    "tags-index": "00_System/tags-index.json",
    "master-index": "99_Index/index.md",
    "master index": "99_Index/index.md",
    "tools-manifest": "00_System/tools-manifest.json",
}


@dataclass(frozen=True)
class Fragment:
    """Una tool vista como fragmento indexable."""

    name: str
    script: str
    group: str
    purpose: str
    params: Dict[str, Any] = field(default_factory=dict)
    guards: List[str] = field(default_factory=list)
    side_effects: List[str] = field(default_factory=list)
    example: str = ""
    related: List[str] = field(default_factory=list)
    status: str = "active"
    required_args: List[str] = field(default_factory=list)
    #: ¿Se pudo leer el contrato formal de esta tool? `False` significa que el
    #: `tool-spec.json` estaba presente y **no** se pudo leer, así que
    #: `required_args` viene vacía por ignorancia y no por contrato. Sin este
    #: campo, `check_contract` validaba cero argumentos obligatorios y salía
    #: verde: un fichero corrupto desactivaba la comprobación en silencio
    #: (AP-51). Ausente no lo pone a `False` — el catálogo basta y eso siempre
    #: fue legítimo.
    contract_known: bool = True

    @property
    def mode(self) -> str:
        """'read' o 'write'. Determina si el fragmento puede paralelizarse libremente."""
        if self.side_effects:
            return "write"
        if any(v in self.name for v in _READ_VERBS):
            return "read"
        return "write"  # sin evidencia de lectura pura → se asume escritura

    @property
    def script_path(self) -> Path:
        return SCRIPTS_DIR / self.script

    @property
    def runtime(self) -> str:
        return "node" if self.name in NATIVE_JS_TOOLS else "python"

    @property
    def exists(self) -> bool:
        if self.runtime == "node":
            return True  # vive en el servidor MCP, no en scripts/
        return self.script_path.exists()

    @property
    def touched_artifacts(self) -> List[str]:
        """Artefactos compartidos que el fragmento declara tocar."""
        blob = " ".join(self.side_effects).lower()
        found = {path for hint, path in _ARTIFACT_HINTS.items() if hint in blob}
        return sorted(found)

    def haystack(self) -> str:
        """Texto sobre el que opera la búsqueda de fragmentos."""
        parts = [
            self.name, self.group, self.purpose, " ".join(self.guards),
            " ".join(self.side_effects), " ".join(self.params.keys()),
            " ".join(self.related), self.example,
        ]
        return " ".join(parts).lower()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "script": self.script,
            "group": self.group,
            "mode": self.mode,
            "runtime": self.runtime,
            "status": self.status,
            "purpose": self.purpose,
            "required_args": self.required_args,
            "params": sorted(self.params.keys()),
            "guards": self.guards,
            "side_effects": self.side_effects,
            "touched_artifacts": self.touched_artifacts,
            "related": self.related,
            "script_exists": self.exists,
        }


def normalize_arg(name: str) -> str:
    """'--meta-file' → 'meta_file'.

    tool-spec.json guarda los required_args tal como aparecen en argparse
    (con `--` y guiones); el catálogo y los lotes usan la clave desnuda.
    Sin esta normalización todo required_arg se reporta como ausente.
    """
    return name.lstrip("-").replace("-", "_")


def _leer_spec() -> tuple[Dict[str, Any], Dict[str, Any]]:
    """El contrato formal, y **cómo fue** leerlo.

    Hasta v40.23 esto devolvía `{}` a cuatro situaciones distintas —no hay
    spec, el JSON es ilegible, `vault_io` no importa, falla la lectura— y el
    llamante no podía distinguirlas. La consecuencia no era cosmética: con la
    spec ilegible, `required_args` quedaba vacía y `cli/safety.check_contract`
    dejaba de validar nada, mientras `cli doctor` reportaba `tool_spec.ok`
    porque preguntaba por otro camino. Un fichero corrupto desactivaba una
    comprobación de seguridad y el diagnóstico decía que todo estaba bien
    (AP-51).

    `ausente` sigue siendo legítimo: el catálogo basta. `ilegible` no.
    """
    try:
        from vault_io import resolve_tool_spec
    except ImportError as e:
        return {}, {"estado": "ilegible", "path": None,
                    "detail": f"vault_io no importable: {e}"}

    try:
        path = resolve_tool_spec()
    except OSError as e:
        return {}, {"estado": "ilegible", "path": None,
                    "detail": f"no se pudo resolver la ruta del spec: {e}"}

    if path is None:
        return {}, {"estado": "ausente", "path": None,
                    "detail": "no hay tool-spec.json; el catálogo basta"}
    try:
        datos = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        return {}, {"estado": "ilegible", "path": str(path),
                    "detail": f"{type(e).__name__}: {e}"}
    tools = datos.get("tools")
    if not isinstance(tools, dict):
        return {}, {"estado": "ilegible", "path": str(path),
                    "detail": "el spec no tiene un mapa `tools`"}
    return tools, {"estado": "legible", "path": str(path), "detail": None}


def _load_spec() -> Dict[str, Any]:
    """Contrato formal de tools. Ausente no es error: el catálogo basta.

    superseded_by: `_leer_spec`, que además dice **cómo** fue leerlo. Se
    conserva —no-derogación— porque su contrato de lectura sigue siendo válido
    para quien solo necesita el mapa.
    """
    return _leer_spec()[0]


def spec_status() -> Dict[str, Any]:
    """Cómo fue leer el contrato formal en la última construcción del registro.

    Lo consume `cli doctor`: su check `tool_spec` preguntaba a
    `resolve_tool_spec()` —que solo dice si el fichero **está**— y por eso un
    spec presente y corrupto salía verde.
    """
    load_registry()
    return dict(_SPEC_STATUS)


#: Estado de la última lectura del spec. Se rellena en `load_registry`, que
#: está cacheado, así que refleja la lectura que construyó el registro vivo.
_SPEC_STATUS: Dict[str, Any] = {"estado": "sin_leer", "path": None, "detail": None}


@lru_cache(maxsize=1)
def load_registry() -> Dict[str, Fragment]:
    """Construye el índice de fragmentos. Cacheado — el catálogo es estático."""
    from vault_mcp_catalog import TOOLS_CATALOG

    spec, estado = _leer_spec()
    _SPEC_STATUS.clear()
    _SPEC_STATUS.update(estado)
    contrato_conocido = estado["estado"] != "ilegible"
    registry: Dict[str, Fragment] = {}

    for name, entry in TOOLS_CATALOG.items():
        spec_entry = spec.get(name, {})
        registry[name] = Fragment(
            name=name,
            script=entry.get("script") or f"{name}.py",
            group=entry.get("group", "Sin grupo"),
            purpose=entry.get("purpose", ""),
            params=entry.get("params", {}) or {},
            guards=list(entry.get("guards", []) or []),
            side_effects=list(entry.get("side_effects", []) or []),
            example=entry.get("example", "") or "",
            related=list(entry.get("related", []) or []),
            status=spec_entry.get("status", entry.get("status", "active")),
            required_args=[
                normalize_arg(a) for a in (spec_entry.get("required_args") or [])
            ],
            contract_known=contrato_conocido,
        )
    return registry


def get(name: str) -> Optional[Fragment]:
    return load_registry().get(name)


def resolve(name: str) -> Optional[Fragment]:
    """Resuelve un nombre tolerando el prefijo 'vault_' omitido."""
    reg = load_registry()
    if name in reg:
        return reg[name]
    prefixed = f"vault_{name}"
    return reg.get(prefixed)


def groups() -> Dict[str, List[Fragment]]:
    out: Dict[str, List[Fragment]] = {}
    for frag in load_registry().values():
        out.setdefault(frag.group, []).append(frag)
    for frags in out.values():
        frags.sort(key=lambda f: f.name)
    return dict(sorted(out.items()))


def search(query: str, *, mode: Optional[str] = None,
           group: Optional[str] = None) -> List[Fragment]:
    """Busca fragmentos. Todos los términos deben aparecer (AND)."""
    terms = [t for t in query.lower().split() if t]
    results: List[Fragment] = []
    for frag in load_registry().values():
        if mode and frag.mode != mode:
            continue
        if group and group.lower() not in frag.group.lower():
            continue
        hay = frag.haystack()
        if all(t in hay for t in terms):
            results.append(frag)
    results.sort(key=lambda f: (0 if query.lower() in f.name else 1, f.name))
    return results


def missing_scripts() -> List[str]:
    """Fragmentos catalogados cuyo script no existe (señal de AP-01/AP-04)."""
    return sorted(f.name for f in load_registry().values() if not f.exists)


def stats() -> Dict[str, Any]:
    reg = load_registry()
    return {
        "total": len(reg),
        "read": sum(1 for f in reg.values() if f.mode == "read"),
        "write": sum(1 for f in reg.values() if f.mode == "write"),
        "groups": len(groups()),
        "missing_scripts": missing_scripts(),
    }


def iter_fragments() -> Iterable[Fragment]:
    return load_registry().values()
