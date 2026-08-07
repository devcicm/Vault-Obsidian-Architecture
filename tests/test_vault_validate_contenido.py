"""`vault_validate` sobre notas reales, no sobre fixtures que ya cumplen.

Los dos defectos que motivan este archivo llevaban versiones en el código y la
suite no los veía, por la misma razón en los dos casos: los tests existentes
construían notas con frontmatter completo, que es justo el caso en el que
ninguno de los dos se manifiesta. Ejecutar la tool contra el vault de pruebas
—notas escritas por las demás tools, no por un fixture— los sacó a los dos a la
primera (regla 7 de CLAUDE.md, en su versión de andar por casa).
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_io  # noqa: E402
import vault_validate  # noqa: E402


def _en_vault(tmp_path, rel, texto):
    destino = tmp_path / rel
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")
    return destino


def test_una_nota_de_contenido_sin_tags_no_revienta_la_tool(tmp_path, monkeypatch):
    """Era `UnboundLocalError`, no un hallazgo.

    `missing.append("tags")` corría tres líneas antes de que `missing`
    existiera. La excepción subía hasta `wrap_main` y la tool entera devolvía
    UNEXPECTED_ERROR: no reportaba esa nota como inválida, es que no validaba
    ninguna de las 125.
    """
    monkeypatch.setattr(vault_io, "_ACTIVE_VAULT_ROOT", tmp_path, raising=False)
    monkeypatch.setattr(vault_validate, "_raiz", lambda: tmp_path)
    nota = _en_vault(
        tmp_path,
        "07_Knowledge/sin-tags.md",
        "---\nid: n1\ntitle: Sin tags\ncreatedAt: 2026-01-01\nupdatedAt: 2026-01-01\n---\n\ncuerpo\n",
    )
    res = vault_validate.validate_frontmatter(nota)
    assert res["valid"] is False
    assert "tags" in res["error"], res


def test_un_indice_generado_no_se_reprueba_por_no_llevar_frontmatter(tmp_path, monkeypatch):
    """El estándar escribe los índices sin frontmatter y luego los exigía.

    `vault_section_index` no le pone frontmatter a `index.md` — es un artefacto
    derivado. Validarlo como nota reprobaba 63 ficheros que el propio estándar
    acababa de generar.
    """
    monkeypatch.setattr(vault_io, "_ACTIVE_VAULT_ROOT", tmp_path, raising=False)
    monkeypatch.setattr(vault_validate, "_raiz", lambda: tmp_path)
    indice = _en_vault(tmp_path, "07_Knowledge/index.md", "# 07_Knowledge — Índice\n")
    assert vault_validate.validate_frontmatter(indice)["valid"] is True

    nota = _en_vault(tmp_path, "07_Knowledge/normal.md", "# sin frontmatter\n")
    assert vault_validate.validate_frontmatter(nota)["valid"] is False
