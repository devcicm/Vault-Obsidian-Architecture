#!/usr/bin/env python3
"""
Vault Code Module Tool — Document a code file in the vault (IEEE 1016 compliant)

Creates or updates 11_Code/{project}/{file-slug}.md with full code documentation.
The source file is never moved -- its disk path is the canonical identifier.
Supports IEEE 1016 viewpoints: context, interface, data, operations, dependency.

Usage:
    python vault_code_module.py --project "ans" --file_path "src/server.py" --description "Main entry point" --language "python"
    python vault_code_module.py --project "ans" --file_path "src/auth.py" --description "Auth service" --methods '[{"name":"login","signature":"(str,str)->bool","description":"Authenticates user"}]'
    python vault_code_module.py --project "ans" --file_path "src/models.py" --description "Data models" --classes '[{"name":"User","description":"User entity","extends":"BaseModel"}]'
    python vault_code_module.py --project "ans" --scan-path "src/"
"""

import argparse
import json
import re
import sys
from vault_errors import wrap_main
from vault_lib import utcnow, slugify
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


from vault_io import atomic_write_text, atomic_write_json, write_report, resolve_input_path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.grafo.repositorio import RepositorioGrafo  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioGrafo:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioGrafo(construir(root))


def _code_dir() -> Path:
    return _repo().dir_codigo

INDEX_FILE = _code_dir() / ".code-index.json"

LANGUAGES = [
    "javascript",
    "typescript",
    "python",
    "go",
    "rust",
    "java",
    "c",
    "cpp",
    "csharp",
    "ruby",
    "php",
    "bash",
    "shell",
    "yaml",
    "json",
    "toml",
    "html",
    "css",
    "sql",
    "markdown",
]

ISO_TYPES = ["module", "component", "service", "library", "script"]

QUALITY_ATTRIBUTES = [
    "functional_suitability",
    "performance_efficiency",
    "compatibility",
    "usability",
    "reliability",
    "security",
    "maintainability",
    "portability",
]


def file_slug(file_path: str) -> str:
    name = Path(file_path).stem
    return slugify(name)


def load_index() -> Dict[str, Any]:
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"modules": [], "relations": []}


def save_index(data: Dict[str, Any]) -> None:
    _code_dir().mkdir(parents=True, exist_ok=True)
    atomic_write_json(INDEX_FILE, data)


def _build_class_diagram(classes: List[Dict[str, Any]]) -> str:
    """Generate a Mermaid classDiagram from the classes list."""
    lines = ["classDiagram"]
    for cls in classes:
        name = cls.get("name", "Unknown")
        extends = cls.get("extends")
        implements = cls.get("implements", [])

        if extends:
            lines.append(f"    {extends} <|-- {name}")
        for iface in implements if isinstance(implements, list) else []:
            lines.append(f"    {iface} <|.. {name}")

        lines.append(f"    class {name}{{")
        for prop in cls.get("properties", []):
            pname = prop.get("name", "")
            ptype = prop.get("type", "")
            lines.append(f"        +{ptype} {pname}")
        for meth in cls.get("methods", []):
            if isinstance(meth, str):
                lines.append(f"        +{meth}()")
            elif isinstance(meth, dict):
                lines.append(f"        +{meth.get('name', '')}()")
        lines.append("    }")
    return "\n".join(lines)


def vault_code_module(
    project: str,
    file_path: str,
    description: str,
    language: Optional[str] = None,
    exports: Optional[List[str]] = None,
    imports_from: Optional[List[str]] = None,
    responsibilities: Optional[List[str]] = None,
    notes: Optional[str] = None,
    tags: Optional[List[str]] = None,
    methods: Optional[List[Dict[str, Any]]] = None,
    classes: Optional[List[Dict[str, Any]]] = None,
    constants: Optional[List[Dict[str, Any]]] = None,
    exceptions: Optional[List[Dict[str, Any]]] = None,
    iso_type: Optional[str] = None,
    quality: Optional[List[Dict[str, Any]]] = None,
    tag_source: bool = False,
) -> Dict[str, Any]:
    safe_project = slugify(project)
    fslug = file_slug(file_path)

    if language and language.lower() not in LANGUAGES:
        return {
            "ok": False,
            "error": f"Language '{language}' not recognized. Use: {LANGUAGES}",
        }

    if iso_type and iso_type.lower() not in ISO_TYPES:
        return {
            "ok": False,
            "error": f"iso_type '{iso_type}' not recognized. Use: {ISO_TYPES}",
        }

    # QUALITY_ATTRIBUTES son las 8 características de ISO/IEC 25010, y la nota
    # titula su tabla "Calidad (ISO 25010)". El registro estaba declarado y no
    # se comprobaba: cualquier cadena entraba en la tabla, así que la nota podía
    # afirmar conformidad con una norma usando atributos que no son los suyos.
    invalidos = [
        q.get("attribute")
        for q in (quality or [])
        if str(q.get("attribute", "")).lower() not in QUALITY_ATTRIBUTES
    ]
    if invalidos:
        return {
            "ok": False,
            "error": (
                f"quality.attribute fuera de ISO/IEC 25010: {invalidos}. "
                f"Use: {QUALITY_ATTRIBUTES}"
            ),
            "valid_attributes": QUALITY_ATTRIBUTES,
        }

    # AP-17 guard: check .code-index.json for existing note with same file_path.
    # vault_write and vault_code_module may derive different slugs for the same source file.
    # The index is the canonical source of truth for which slug was used first.
    note_path = _code_dir() / safe_project / f"{fslug}.md"
    index = load_index()
    for existing_mod in index.get("modules", []):
        if (
            existing_mod.get("filePath") == file_path
            and existing_mod.get("project") == project
        ):
            canonical_rel = existing_mod.get("relPath", "")
            canonical_path = _raiz() / canonical_rel if canonical_rel else None
            if (
                canonical_path
                and canonical_path.exists()
                and canonical_path != note_path
            ):
                # Use the canonical path instead of generating a different slug
                note_path = canonical_path
                fslug = canonical_path.stem
            break

    now = utcnow()
    created_at = now
    existing_id = None

    if note_path.exists():
        with open(note_path, "r", encoding="utf-8") as f:
            content = f.read()
        frontmatter_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if frontmatter_match:
            for line in frontmatter_match.group(1).split("\n"):
                if line.startswith("id:"):
                    existing_id = line.split(":", 1)[1].strip()
                elif line.startswith("createdAt:"):
                    created_at = line.split(":", 1)[1].strip()
        action = "updated"
    else:
        action = "created"

    note_id = existing_id or str(uuid.uuid4())

    tags = list(tags or [])
    tags.extend([safe_project, "code", fslug])
    if iso_type:
        tags.append(iso_type)

    frontmatter = ["---"]
    frontmatter.append(f"id: {note_id}")
    frontmatter.append(f"title: {Path(file_path).name}")
    frontmatter.append(f"project: {project}")
    frontmatter.append(f"file_path: {file_path}")
    frontmatter.append(f"type: code-module")
    if language:
        frontmatter.append(f"language: {language}")
    if iso_type:
        frontmatter.append(f"iso_type: {iso_type}")
    frontmatter.append(f"createdAt: {created_at}")
    frontmatter.append(f"updatedAt: {now}")
    if tags:
        frontmatter.append(f"tags: {json.dumps(list(dict.fromkeys(tags)))}")
    frontmatter.append("cia_integrity: medium")
    frontmatter.append("cia_availability: medium")
    frontmatter.append("cia_sensitivity: internal")
    frontmatter.append("status: draft")
    frontmatter.append("agent: system")
    frontmatter.append("---")

    body_sections = []

    header = f"**Ruta:** `{file_path}`"
    if language:
        header += f"  |  **Lenguaje:** `{language}`"
    if iso_type:
        header += f"  |  **Tipo ISO:** `{iso_type}`"
    body_sections.append(header + "\n")

    body_sections.append(f"## Proposito\n\n{description}")

    # IEEE 1016 — Operations viewpoint
    if methods:
        rows = ["## Metodos\n", "| Metodo | Firma | Descripcion |", "|---|---|---|"]
        for m in methods:
            name = m.get("name", "")
            sig = m.get("signature", "")
            desc = m.get("description", "")
            rows.append(f"| `{name}` | `{sig}` | {desc} |")

            # Detail block if params or raises defined
            params = m.get("params", [])
            raises = m.get("raises", [])
            ret = m.get("returns", {})
            if params or raises or ret:
                rows.append("")
                rows.append(f"**`{name}`**")
                if params:
                    rows.append("")
                    rows.append("Parametros:")
                    for p in params:
                        rows.append(
                            f"- `{p.get('name', '')}` ({p.get('type', '')}) — {p.get('desc', '')}"
                        )
                if ret and isinstance(ret, dict):
                    rows.append(
                        f"- **Retorna** `{ret.get('type', '')}` — {ret.get('desc', '')}"
                    )
                if raises:
                    rows.append("")
                    rows.append("Lanza:")
                    for r in raises if isinstance(raises, list) else [raises]:
                        rows.append(f"- `{r}`")
        body_sections.append("\n".join(rows))

    # IEEE 1016 — Data viewpoint: classes
    if classes:
        class_lines = ["## Clases\n"]
        for cls in classes:
            name = cls.get("name", "Unknown")
            desc = cls.get("description", "")
            extends = cls.get("extends", "")
            implements = cls.get("implements", [])

            header_parts = [f"### `{name}`"]
            if extends:
                header_parts.append(f"(extends `{extends}`)")
            if implements:
                ifaces = ", ".join(
                    f"`{i}`"
                    for i in (
                        implements if isinstance(implements, list) else [implements]
                    )
                )
                header_parts.append(f"(implements {ifaces})")
            class_lines.append(" ".join(header_parts))

            if desc:
                class_lines.append(f"\n{desc}\n")

            props = cls.get("properties", [])
            if props:
                class_lines.append("**Propiedades:**")
                for p in props:
                    class_lines.append(
                        f"- `{p.get('name', '')}` ({p.get('type', '')}) — {p.get('desc', '')}"
                    )
                class_lines.append("")

            meths = cls.get("methods", [])
            if meths:
                class_lines.append("**Metodos:**")
                for m in meths:
                    if isinstance(m, str):
                        class_lines.append(f"- `{m}()`")
                    elif isinstance(m, dict):
                        class_lines.append(
                            f"- `{m.get('name', '')}()` — {m.get('description', '')}"
                        )
                class_lines.append("")

        body_sections.append("\n".join(class_lines))

        # Auto-generate classDiagram Mermaid
        diagram = _build_class_diagram(classes)
        body_sections.append(f"## Diagrama de Clases\n\n```mermaid\n{diagram}\n```")

    # IEEE 1016 — Data viewpoint: constants
    if constants:
        rows = [
            "## Constantes\n",
            "| Nombre | Valor | Tipo | Descripcion |",
            "|---|---|---|---|",
        ]
        for c in constants:
            rows.append(
                f"| `{c.get('name', '')}` | `{c.get('value', '')}` | `{c.get('type', '')}` | {c.get('description', '')} |"
            )
        body_sections.append("\n".join(rows))

    # IEEE 1016 — Error handling
    if exceptions:
        rows = ["## Excepciones\n", "| Excepcion | Cuando se lanza |", "|---|---|"]
        for e in exceptions:
            rows.append(
                f"| `{e.get('name', '')}` | {e.get('raised_when', e.get('description', ''))} |"
            )
        body_sections.append("\n".join(rows))

    # ISO 25010 — Quality model
    if quality:
        rows = [
            "## Calidad (ISO 25010)\n",
            "| Atributo | Rating | Notas |",
            "|---|---|---|",
        ]
        for q in quality:
            attr = q.get("attribute", "")
            rating = q.get("rating", "")
            stars = (
                "★" * int(rating) + "☆" * (5 - int(rating))
                if str(rating).isdigit()
                else str(rating)
            )
            notes_q = q.get("notes", "")
            rows.append(f"| `{attr}` | {stars} ({rating}/5) | {notes_q} |")
        body_sections.append("\n".join(rows))

    if exports:
        body_sections.append("## Exportaciones\n")
        lines = []
        for exp in exports:
            lines.append(f"- {exp}")
        body_sections.append("\n".join(lines))

    if imports_from:
        body_sections.append("## Importaciones desde\n")
        lines = []
        for imp in imports_from:
            lines.append(f"- `{imp}`")
        body_sections.append("\n".join(lines))

    if responsibilities:
        body_sections.append("## Responsabilidades\n")
        lines = []
        for resp in responsibilities:
            lines.append(f"- {resp}")
        body_sections.append("\n".join(lines))

    if notes:
        body_sections.append(f"## Notas\n\n{notes}")

    final_content = "\n".join(frontmatter) + "\n\n" + "\n\n".join(body_sections)

    note_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(note_path, final_content)

    index = load_index()

    method_names = [m.get("name", "") for m in (methods or [])] if methods else []
    class_names = [c.get("name", "") for c in (classes or [])] if classes else []

    module_entry = {
        "docId": note_id,
        "project": project,
        "filePath": file_path,
        "title": Path(file_path).name,
        "relPath": str(note_path.relative_to(_raiz())).replace("\\", "/"),
        "exports": exports or [],
        "language": language or "",
        "iso_type": iso_type or "",
        "methods": method_names,
        "classes": class_names,
        "quality": {q.get("attribute"): q.get("rating") for q in (quality or [])},
        "updatedAt": now,
    }

    for i, m in enumerate(index["modules"]):
        if m["filePath"] == file_path:
            index["modules"][i] = module_entry
            break
    else:
        index["modules"].append(module_entry)

    save_index(index)

    has_relations = any(
        r.get("from") == file_path or r.get("to") == file_path
        for r in index.get("relations", [])
    )

    note_rel = str(note_path.relative_to(_raiz())).replace("\\", "/")

    result: Dict[str, Any] = {
        "ok": True,
        **write_report(),
        "path": note_rel,
        "project": project,
        "file_path": file_path,
        "action": action,
        "has_class_diagram": bool(classes),
        "mapRegenerated": has_relations,
        "source_tagged": False,
    }

    # Bidirectional link: embed @vault: in the source file
    if tag_source:
        abs_file = resolve_input_path(file_path)
        if abs_file.exists():
            try:
                from vault_code_tag import vault_code_tag_link_vault

                tag_title = f"{Path(file_path).name} ({iso_type or 'module'})"
                note_ref = note_rel.removesuffix(".md")
                tag_result = vault_code_tag_link_vault(
                    note_ref, str(abs_file), title=tag_title
                )
                result["source_tagged"] = tag_result.get("ok", False)
                result["tag_action"] = tag_result.get("action", "error")
                if not tag_result.get("ok"):
                    result["tag_warning"] = tag_result.get("detail", "")
            except Exception as e:
                result["tag_warning"] = f"Could not tag source: {e}"
        else:
            result["tag_warning"] = (
                f"Source file not found on disk: {abs_file} — @vault: not injected"
            )

    return result


def main():
    EXT_LANGUAGE_MAP = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".mjs": "javascript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".go": "go",
        ".java": "java",
        ".rb": "ruby",
        ".rs": "rust",
        ".cpp": "cpp",
        ".c": "c",
        ".cs": "csharp",
        ".php": "php",
    }
    CODE_EXTS = set(EXT_LANGUAGE_MAP.keys())

    parser = argparse.ArgumentParser(
        description="Vault Code Module Tool — IEEE 1016 compliant code documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Documentacion basica
  python vault_code_module.py --project "ans" --file_path "src/server.py" --description "Main MCP server" --language "python"

  # Con metodos (IEEE 1016 Operations viewpoint)
  python vault_code_module.py --project "ans" --file_path "src/auth.py" --description "Auth service" --iso_type service --methods '[{"name":"login","signature":"(str,str)->bool","description":"Authenticates user","params":[{"name":"user","type":"str","desc":"Username"},{"name":"pwd","type":"str","desc":"Password"}],"returns":{"type":"bool","desc":"True if authenticated"}}]'

  # Con clases (auto-genera classDiagram Mermaid)
  python vault_code_module.py --project "ans" --file_path "src/models.py" --description "Data models" --classes '[{"name":"User","description":"User entity","extends":"BaseModel","properties":[{"name":"id","type":"int","desc":"Primary key"}]}]'

  # Con constantes y excepciones
  python vault_code_module.py --project "ans" --file_path "src/config.py" --description "Config constants" --constants '[{"name":"MAX_RETRY","value":"3","type":"int","description":"Max retry attempts"}]' --exceptions '[{"name":"ConfigError","raised_when":"Missing required env var"}]'

  # Con calidad ISO 25010
  python vault_code_module.py --project "ans" --file_path "src/auth.py" --description "Auth service" --quality '[{"attribute":"security","rating":5,"notes":"Input validation, no injection risk"},{"attribute":"maintainability","rating":4,"notes":"Well structured"}]'

  # Escanear directorio completo
  python vault_code_module.py --project "ans" --scan-path "src/"

Notas:
  - iso_type: module | component | service | library | script  (ISO/IEC 12207)
  - Con --classes se genera automaticamente un classDiagram Mermaid en la nota
  - Con --scan-path, --file_path y --description son opcionales
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
""",
    )
    parser.add_argument("--project", required=True, help="Project slug")
    parser.add_argument(
        "--file_path", help="Real file path on disk (canonical identifier)"
    )
    parser.add_argument("--description", help="Purpose of the file in 1-3 lines")
    parser.add_argument("--language", help=f"Language: {LANGUAGES}")
    parser.add_argument("--iso_type", help=f"ISO/IEC 12207 component type: {ISO_TYPES}")
    parser.add_argument("--exports", help="JSON array of exported symbols")
    parser.add_argument(
        "--imports", dest="imports_from", help="JSON array of imported modules"
    )
    parser.add_argument("--responsibilities", help="JSON array of responsibilities")
    parser.add_argument("--notes", help="Additional notes")
    parser.add_argument("--tags", nargs="*", help="Additional tags")
    parser.add_argument(
        "--methods",
        help="JSON array of methods: [{name, signature, description, params:[{name,type,desc}], returns:{type,desc}, raises:[str]}]",
    )
    parser.add_argument(
        "--classes",
        help="JSON array of classes: [{name, description, extends?, implements?:[], properties:[{name,type,desc}], methods:[str]}]",
    )
    parser.add_argument(
        "--constants",
        help="JSON array of constants: [{name, value, type, description}]",
    )
    parser.add_argument(
        "--exceptions",
        help="JSON array of exceptions: [{name, description, raised_when}]",
    )
    parser.add_argument(
        "--quality", help="JSON array ISO 25010: [{attribute, rating(1-5), notes}]"
    )
    parser.add_argument(
        "--scan-path",
        help="Directory to scan recursively for code files and document each one",
    )
    parser.add_argument(
        "--tag-source",
        action="store_true",
        help="Embed @vault: reference in the source file after creating the vault note",
    )

    args = parser.parse_args()

    if args.scan_path:
        scan_dir = Path(args.scan_path)
        if not scan_dir.exists():
            print(
                json.dumps(
                    {"ok": False, "error": f"scan-path not found: {args.scan_path}"}
                )
            )
            return 1

        code_files = [
            f
            for f in scan_dir.rglob("*")
            if f.is_file() and f.suffix.lower() in CODE_EXTS
        ]
        documented = []
        skipped = []

        for code_file in code_files:
            try:
                rel_path = str(code_file.relative_to(scan_dir)).replace("\\", "/")
            except ValueError:
                rel_path = str(code_file).replace("\\", "/")

            detected_language = args.language or EXT_LANGUAGE_MAP.get(
                code_file.suffix.lower()
            )

            fslug_val = file_slug(str(code_file))
            safe_project = slugify(args.project)
            note_path_check = _code_dir() / safe_project / f"{fslug_val}.md"
            if note_path_check.exists():
                skipped.append({"file": rel_path, "reason": "already documented"})
                continue

            result = vault_code_module(
                args.project,
                rel_path,
                code_file.name,
                detected_language,
                None,
                None,
                None,
                None,
                args.tags,
            )
            if result.get("ok"):
                documented.append(result["path"])
            else:
                skipped.append(
                    {"file": rel_path, "reason": result.get("error", "unknown")}
                )

        print(
            json.dumps(
                {
                    "ok": True,
                    "scanned": len(code_files),
                    "documented": documented,
                    "skipped": skipped,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if not args.file_path:
        parser.error("--file_path is required when --scan-path is not used")
    if not args.description:
        parser.error("--description is required when --scan-path is not used")

    def parse_json_arg(val, name):
        if not val:
            return None
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            # Accept comma-separated string as fallback for list-type args
            # e.g. --exports "Foo,Bar,Baz" → ["Foo", "Bar", "Baz"]
            if name in ("exports", "imports", "responsibilities", "tags"):
                parts = [p.strip() for p in val.split(",") if p.strip()]
                if parts:
                    return parts
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": f"Invalid JSON in --{name}. Expected JSON array or comma-separated list.",
                    }
                )
            )
            sys.exit(1)

    result = vault_code_module(
        args.project,
        args.file_path,
        args.description,
        args.language,
        parse_json_arg(args.exports, "exports"),
        parse_json_arg(args.imports_from, "imports"),
        parse_json_arg(args.responsibilities, "responsibilities"),
        args.notes,
        args.tags,
        parse_json_arg(args.methods, "methods"),
        parse_json_arg(args.classes, "classes"),
        parse_json_arg(args.constants, "constants"),
        parse_json_arg(args.exceptions, "exceptions"),
        args.iso_type,
        parse_json_arg(args.quality, "quality"),
        tag_source=args.tag_source,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_code_module"))
