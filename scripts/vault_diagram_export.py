#!/usr/bin/env python3

"""
Vault Diagram Export — Exporta diagramas con configuraciones de visualización.

Genera archivos Mermaid con opciones de zoom, pan, filtros y configuraciones
de visualización. Útil para crear exports personalizados o configuraciones
para visualizadores externos.

Usage:
    python vault_diagram_export.py --path "06_Diagrams/foo.md"
    python vault_diagram_export.py --path "06_Diagrams/foo.md" --zoom 2.0
    python vault_diagram_export.py --project "mi-api" --filter "flowchart"
    python vault_diagram_export.py --config
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_errors import emit_error, wrap_main
from vault_io import write_report


DEFAULT_CONFIG = {
    "zoomLevel": 1.0,
    "panX": 0,
    "panY": 0,
    "fit": False,
    "maxZoom": 2.0,
    "minZoom": 0.5,
    "highlightNodes": [],
    "hideNodes": [],
    "direction": "TD",
}


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _diagrams_dir() -> Path:
    return _repo().seccion("06_Diagrams")


def _config_file() -> Path:
    return _repo().seccion("06_Diagrams") / ".mermaid-config.json"


def generate_mermaid_config(
    zoom: float = 1.0,
    pan_x: int = 0,
    pan_y: int = 0,
    fit: bool = False,
    max_zoom: float = 2.0,
    min_zoom: float = 0.5,
    highlight: Optional[List[str]] = None,
    hide: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Genera configuración de Mermaid."""
    return {
        "zoomLevel": zoom,
        "panX": pan_x,
        "panY": pan_y,
        "fit": fit,
        "maxZoom": max_zoom,
        "minZoom": min_zoom,
        "highlightNodes": highlight or [],
        "hideNodes": hide or [],
    }


def export_with_config(
    diagram: str,
    config: Dict[str, Any],
) -> str:
    """Exporta diagrama con configuración aplicada."""
    result = diagram

    if config.get("highlightNodes"):
        highlight = config["highlightNodes"]
        for node in highlight:
            result = re.sub(
                rf"(\b{re.escape(node)}\b)(?!\])",
                f":::highlight\n{node}\n:::",
                result,
            )

    if config.get("hideNodes"):
        for node in config["hideNodes"]:
            result = re.sub(
                rf"^\s*{re.escape(node)}.*$",
                "",
                result,
                flags=re.MULTILINE,
            )

    return result


def apply_zoom_pan(
    diagram: str, zoom: float, pan_x: int, pan_y: int, direction: str = "TD"
) -> str:
    """Aplica zoom y pan a un diagrama flowchart."""
    lines = diagram.strip().split("\n")
    result_lines = []

    for line in lines:
        if line.strip().startswith("flowchart"):
            if direction:
                result_lines.append(f"flowchart {direction}")
            else:
                result_lines.append(line)
        else:
            result_lines.append(line)

    return "\n".join(result_lines)


def extract_diagram(file_path: Path, index: int = 0) -> Optional[str]:
    """Extrae un diagrama específico de un archivo."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError, PermissionError) as exc:
        emit_error("vault_diagram_export", "FILE_READ_ERROR", str(exc))
        return None
    except Exception as exc:
        emit_error("vault_diagram_export", "UNEXPECTED_ERROR", str(exc))
        return None

    pattern = r"```mermaid\s*\n(.*?)```"
    matches = re.findall(pattern, content, re.DOTALL)

    if index < len(matches):
        return matches[index]
    return None


def export_diagram(
    file_path: Path,
    output_path: Optional[Path] = None,
    zoom: float = 1.0,
    pan_x: int = 0,
    pan_y: int = 0,
    fit: bool = False,
    highlight: Optional[List[str]] = None,
    hide: Optional[List[str]] = None,
    direction: Optional[str] = None,
) -> Dict[str, Any]:
    """Exporta un diagrama con opciones de visualización."""
    result = {
        "ok": True,
        "file": str(file_path),
    }

    diagram = extract_diagram(file_path)
    if not diagram:
        result["ok"] = False
        result["error"] = f"No diagram found at index 0"
        return result

    config = generate_mermaid_config(
        zoom=zoom,
        pan_x=pan_x,
        pan_y=pan_y,
        fit=fit,
        highlight=highlight,
        hide=hide,
    )

    if direction:
        diagram = apply_zoom_pan(diagram, zoom, pan_x, pan_y, direction)
    else:
        diagram = apply_zoom_pan(diagram, zoom, pan_x, pan_y, "TD")

    diagram = export_with_config(diagram, config)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"```mermaid\n{diagram}\n```", encoding="utf-8")
        result["output"] = str(output_path)
    else:
        result["diagram"] = diagram

    result["config"] = config
    return result


def export_project(
    project: str,
    output_dir: Path,
    filter_type: Optional[str] = None,
    zoom: float = 1.0,
    **kwargs,
) -> Dict[str, Any]:
    """Exporta todos los diagramas de un proyecto."""
    project_dir = _raiz() / "01_Projects" / project

    if not project_dir.exists():
        return emit_error("vault_diagram_export", "PROJECT_NOT_FOUND", f"Proyecto no encontrado: {project}")

    output_dir.mkdir(parents=True, exist_ok=True)
    exported = []

    for md in project_dir.rglob("*.md"):
        if ".history" in str(md):
            continue

        try:
            content = md.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError, PermissionError) as exc:
            emit_error("vault_diagram_export", "FILE_READ_ERROR", str(exc))
            continue
        except Exception as exc:
            emit_error("vault_diagram_export", "UNEXPECTED_ERROR", str(exc))
            continue

        pattern = r"```mermaid\s*\n(.*?)```"
        matches = re.findall(pattern, content, re.DOTALL)

        if filter_type:
            filtered = []
            for match in matches:
                if filter_type.lower() in match.lower():
                    filtered.append(match)
            matches = filtered

        for idx, diagram in enumerate(matches):
            config = generate_mermaid_config(zoom=zoom, **kwargs)
            diagram = apply_zoom_pan(diagram, zoom, 0, 0, "TD")
            diagram = export_with_config(diagram, config)

            filename = f"{md.stem}-{idx}.mmd"
            out_path = output_dir / filename
            out_path.write_text(f"```mermaid\n{diagram}\n```", encoding="utf-8")
            exported.append(str(out_path))

    return {
        "ok": True,
        **write_report(),
        "project": project,
        "exported": len(exported),
        "files": exported,
    }


def save_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Guarda configuración global de Mermaid."""
    _config_file().parent.mkdir(parents=True, exist_ok=True)
    _config_file().write_text(json.dumps(config, indent=2), encoding="utf-8")
    return {"ok": True, "config_file": str(_config_file())}


def load_config() -> Dict[str, Any]:
    """Carga configuración global de Mermaid."""
    if _config_file().exists():
        return json.loads(_config_file().read_text(encoding="utf-8"))
    return DEFAULT_CONFIG.copy()


def main():
    parser = argparse.ArgumentParser(
        description="Vault Diagram Export - Exporta diagramas con opciones de visualización",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_diagram_export.py --path "06_Diagrams/foo.md"
  python vault_diagram_export.py --path "06_Diagrams/foo.md" --zoom 2.0 --pan_x 100
  python vault_diagram_export.py --path "06_Diagrams/foo.md" --highlight "A,B" --hide "C"
  python vault_diagram_export.py --project "mi-api" --filter "flowchart" --output "export/"
  python vault_diagram_export.py --config --zoom 1.5 --fit
        """,
    )

    parser.add_argument("--path", type=str, help="Archivo con diagrama a exportar")
    parser.add_argument("--project", type=str, help="Proyecto a exportar")
    parser.add_argument("--output", type=str, help="Carpeta de salida")
    parser.add_argument(
        "--filter", type=str, help="Filtrar por tipo (flowchart, sequence, etc)"
    )

    parser.add_argument(
        "--zoom", type=float, default=1.0, help="Nivel de zoom (default: 1.0)"
    )
    parser.add_argument(
        "--pan_x", type=int, default=0, help="Posición X del pan (default: 0)"
    )
    parser.add_argument(
        "--pan_y", type=int, default=0, help="Posición Y del pan (default: 0)"
    )
    parser.add_argument("--fit", action="store_true", help="Ajustar al contenedor")
    parser.add_argument(
        "--direction",
        type=str,
        default="TD",
        help="Dirección: TD, LR, RL, BT (default: TD)",
    )

    parser.add_argument(
        "--highlight", type=str, help="Nodos a resaltar (separados por coma)"
    )
    parser.add_argument("--hide", type=str, help="Nodos a ocultar (separados por coma)")

    parser.add_argument(
        "--config", action="store_true", help="Guardar configuración global"
    )
    parser.add_argument("--json", action="store_true", help="Salida JSON")

    args = parser.parse_args()

    highlight = args.highlight.split(",") if args.highlight else None
    hide = args.hide.split(",") if args.hide else None

    if args.config:
        config = generate_mermaid_config(
            zoom=args.zoom,
            pan_x=args.pan_x,
            pan_y=args.pan_y,
            fit=args.fit,
            highlight=highlight,
            hide=hide,
        )
        result = save_config(config)
    elif args.path:
        file_path = _raiz() / args.path
        output_path = Path(args.output) if args.output else None
        result = export_diagram(
            file_path,
            output_path,
            zoom=args.zoom,
            pan_x=args.pan_x,
            pan_y=args.pan_y,
            fit=args.fit,
            highlight=highlight,
            hide=hide,
            direction=args.direction,
        )
    elif args.project:
        output_dir = Path(args.output) if args.output else _diagrams_dir() / "export"
        result = export_project(
            args.project,
            output_dir,
            filter_type=args.filter,
            zoom=args.zoom,
            highlight=highlight,
            hide=hide,
        )
    else:
        result = load_config()
        result["config_file"] = str(_config_file())

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result.get("ok", True):
            if "diagram" in result:
                print(result["diagram"])
            elif "exported" in result:
                print(f"Exportados: {result['exported']} diagramas")
                for f in result.get("files", []):
                    print(f"  - {f}")
            else:
                print(f"Configuración guardada: {_config_file()}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
            return 1

    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_diagram_export"))
