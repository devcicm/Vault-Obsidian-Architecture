"""El inventario por lotes: de solo lectura, con contrato y comparable.

Propuesta `data-engineering-contracts-and-vault-applicability`: antes de
elegir un pipeline, una medida **reproducible** y de solo lectura. Lo que se
prueba aquí:

- el inventario **no escribe en el vault** (ni una nota, ni un índice);
- un snapshot **no puede vivir dentro del vault**: el inventario lo contaría
  y el artefacto contaminaría la medida;
- la comparación distingue añadidas, retiradas y modificadas (por hash del
  cuerpo), y **no mezcla esquemas distintos**;
- el alcance se publica: metadatos, no verdad del contenido.
"""

from __future__ import annotations

import json
from pathlib import Path

from apoyo import ROOT as REPO_ROOT  # el conftest ya pone el path

import vault_insights
from vault.gobernanza.insights import ESQUEMA


def _vault(tmp_path: Path) -> Path:
    raiz = tmp_path / "vault"
    (raiz / "07_Knowledge").mkdir(parents=True)
    (raiz / "00_System").mkdir(parents=True)
    (raiz / "07_Knowledge" / "uno.md").write_text(
        "---\ntitle: Uno\ntype: note\nstatus: draft\ntags: [a]\n"
        "createdAt: 2026-01-01T00:00:00.000Z\n---\n\nCuerpo de la nota uno.\n",
        encoding="utf-8")
    (raiz / "07_Knowledge" / "dos.md").write_text(
        "---\ntitle: Dos\ntype: note\nstatus: reviewed\n---\n\n"
        "Cuerpo de la nota dos.\n",
        encoding="utf-8")
    return raiz


def test_el_inventario_es_de_solo_lectura(tmp_path):
    raiz = _vault(tmp_path)
    antes = {p: p.stat().st_mtime_ns for p in raiz.rglob("*") if p.is_file()}

    datos = vault_insights.inventario(raiz)

    despues = {p: p.stat().st_mtime_ns for p in raiz.rglob("*") if p.is_file()}
    assert datos["ok"] and datos["total"] == 2, datos
    assert antes == despues, "el inventario escribió en el vault"
    assert datos["schema"] == ESQUEMA
    nota = next(n for n in datos["notas"] if n["path"].endswith("uno.md"))
    assert nota["seccion"] == "07_Knowledge"
    assert nota["type"] == "note"
    assert nota["status"] == "draft"
    assert nota["hash_cuerpo"], nota


def test_el_snapshot_no_puede_vivir_dentro_del_vault(tmp_path):
    raiz = _vault(tmp_path)
    datos = vault_insights.inventario(raiz)

    import pytest

    with pytest.raises(vault_insights.SnapshotInvalido) as exc:
        vault_insights.guardar(datos, str(raiz / "snap.json"), raiz)
    assert exc.value.causa == "INVALID_PATH"
    assert not (raiz / "snap.json").exists()

    fuera = vault_insights.guardar(datos, str(tmp_path / "datos" / "snap.json"), raiz)
    assert fuera.get("ok"), fuera
    assert (tmp_path / "datos" / "snap.json").is_file()


def test_la_comparacion_distingue_anadidas_retiradas_y_modificadas(tmp_path):
    raiz = _vault(tmp_path)
    a = vault_insights.inventario(raiz)
    (raiz / "07_Knowledge" / "tres.md").write_text(
        "---\ntitle: Tres\n---\n\nNota nueva.\n", encoding="utf-8")
    (raiz / "07_Knowledge" / "dos.md").write_text(
        "---\ntitle: Dos\n---\n\nCuerpo cambiado.\n", encoding="utf-8")
    (raiz / "07_Knowledge" / "uno.md").unlink()
    b = vault_insights.inventario(raiz)

    pa = tmp_path / "a.json"
    pb = tmp_path / "b.json"
    pa.write_text(json.dumps(a), encoding="utf-8")
    pb.write_text(json.dumps(b), encoding="utf-8")

    informe = vault_insights.comparar(str(pa), str(pb))
    assert informe.get("ok"), informe
    assert informe["anadidas"] == ["07_Knowledge/tres.md"], informe
    assert informe["retiradas"] == ["07_Knowledge/uno.md"], informe
    assert informe["modificadas"] == ["07_Knowledge/dos.md"], informe
    assert "no mide si el contenido es verdadero" in informe["alcance"]


def test_no_se_mezclan_esquemas_distintos(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps({"schema": 1, "notas": []}), encoding="utf-8")
    b.write_text(json.dumps({"schema": 2, "notas": []}), encoding="utf-8")
    import pytest

    with pytest.raises(vault_insights.SnapshotInvalido) as exc:
        vault_insights.comparar(str(a), str(b))
    assert exc.value.causa == "SCHEMA_MISMATCH"


def test_el_snapshot_ilegible_se_declara(tmp_path):
    a = tmp_path / "roto.json"
    a.write_text("{no es json", encoding="utf-8")
    import pytest

    with pytest.raises(vault_insights.SnapshotInvalido) as exc:
        vault_insights.comparar(str(a), str(a))
    assert exc.value.causa == "DATA_FILE_CORRUPT"
