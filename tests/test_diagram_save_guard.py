"""vault_diagram_save — guard de pre-escritura AP-25.

Medido 2026-10-18: un agente podía llamar a
`vault_diagram_save --content "graph TD\\n  A -->"` y la nota quedaba
en disco con un bloque que Mermaid no dibuja. El guard rechaza la
escritura con `MERMAID_INVALID` y NO toca el disco, así el error es
accionable en el mismo turno del agente.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
TESTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_io  # noqa: E402
import vault_diagram_save as vds  # noqa: E402
import vault_standard_upgrade  # noqa: E402

#: La versión vigente sale del dueño, nunca escrita a mano (AP-47).
VIGENTE = vault_standard_upgrade.CURRENT_VERSION


def _vault(tmp_path, monkeypatch):
    (tmp_path / "00_System").mkdir()
    (tmp_path / "00_System" / "standard-version.json").write_text(
        f'{{"applied_version": "{VIGENTE}", "applied_at": "2026-10-18T00:00:00Z", '
        '"applied_by": "test", "migrations_applied": []}\n',
        encoding="utf-8",
    )
    (tmp_path / "06_Diagrams").mkdir()
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    monkeypatch.setenv("VAULT_STRICT_ROOT", "1")
    vault_io.set_vault_root(str(tmp_path))
    return tmp_path


def test_contenido_valido_escribe(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    r = vds.vault_diagram_save(
        "proj", "OK", "mermaid", "component",
        "graph TD\n  A[Inicio] --> B[Fin]",
    )
    assert r.get("ok") is True, r
    # El tool escribe el diagrama Y actualiza los índices de sección.
    escritos = list((tmp_path / "06_Diagrams").rglob("*.md"))
    diagramas = [
        p for p in escritos
        if p.name not in {"index.md"}
        and p.parent.name not in {"component"}  # component/index.md se regenera
        or ("proj" in p.name and p.name.startswith("proj"))
    ]
    # El contrato: al menos un diagrama del proyecto se escribió, y los
    # índices se actualizaron (no se queda un índice stale).
    assert any("proj-ok" in p.name for p in escritos), escritos
    assert any(p.name == "index.md" for p in escritos), escritos


def test_contenido_invalido_rechaza_y_no_escribe(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    contenido_invalido = "flowchartDesconocido\n  A --> B"  # tipo no reconocido
    r = vds.vault_diagram_save(
        "proj", "Mal", "mermaid", "component",
        contenido_invalido,
    )
    assert r.get("ok") is False
    assert r.get("error_code") == "MERMAID_INVALID"
    written = list((tmp_path / "06_Diagrams").rglob("*.md"))
    assert written == [], (
        f"el guard debía impedir la escritura pero dejó: {written}"
    )


def test_llaves_desbalanceadas_rechazan(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    contenido = "graph TD\n  A[Ini] --> B[Fin\n  B --> C"  # faltan ']'
    r = vds.vault_diagram_save(
        "proj", "Llaves", "mermaid", "component", contenido,
    )
    assert r.get("ok") is False
    assert r.get("error_code") == "MERMAID_INVALID"
    assert list((tmp_path / "06_Diagrams").rglob("*.md")) == []


def test_plantuml_y_ascii_no_pasan_por_el_guard_mermaid(tmp_path, monkeypatch):
    """El guard solo aplica a `diagram_type == "mermaid"`. PlantUML y
    ASCII se escriben sin validación Mermaid (no aplica)."""
    _vault(tmp_path, monkeypatch)
    r = vds.vault_diagram_save(
        "proj", "PU", "plantuml", "component",
        "@startuml\nA -> B\n@enduml",
    )
    assert r.get("ok") is True


def test_el_envelope_devuelve_los_errores_de_validacion(tmp_path, monkeypatch):
    """El guard no solo rechaza: lista los errores para que el agente los
    arregle en el mismo turno."""
    _vault(tmp_path, monkeypatch)
    contenido = "flowchartDesconocido\n  A --> B"
    r = vds.vault_diagram_save(
        "proj", "Con Diagnóstico", "mermaid", "component", contenido,
    )
    assert r.get("ok") is False
    # `args` viaja anidado en `envelope["args"]` (forma del contrato AP-52),
    # no como campos top-level.
    args = r.get("args") or {}
    validation = args.get("validation_errors") or []
    assert len(validation) >= 1
    assert any(e.get("type") == "unknown_type" for e in validation), validation
