"""El contrato de campos de una nota tiene un dueño, y quien valida lo lee de él.

Hasta 2026-10-05 la lista de campos obligatorios vivía como literal dentro de
`vault_validate.validate_frontmatter`, con un comentario «v37: required fields
expanded» como única historia. Ni el escritor (`vault_write`) ni ninguna tool
de reparación podía preguntar qué le falta a una nota sin copiar esa lista, y
la versión en que cada campo pasó a exigirse no estaba en ningún registro.
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_contrato_nota as contrato  # noqa: E402


def test_las_tres_clases_de_nota():
    assert contrato.clase_de_nota("99_Index/index.md") == "derivada"
    assert contrato.clase_de_nota("07_Knowledge/index.md") == "derivada"
    assert contrato.clase_de_nota("00_System/primer.md") == "sistema"
    assert contrato.clase_de_nota("07_Knowledge/jwt.md") == "contenido"
    assert contrato.clase_de_nota("07_Knowledge\\jwt.md") == "contenido"


def test_los_requeridos_por_clase_son_los_de_v37():
    base = {"id", "title", "createdAt", "updatedAt"}
    assert set(contrato.campos_requeridos("00_System/x.md")) == base
    assert set(contrato.campos_requeridos("07_Knowledge/x.md")) == base | {
        "cia_integrity", "cia_availability", "cia_sensitivity", "agent", "tags"}
    assert contrato.campos_requeridos("07_Knowledge/index.md") == ()


def test_faltantes_respeta_el_orden_del_contrato():
    assert contrato.faltantes({"title": "x", "id": "1"}, "07_Knowledge/x.md")[:3] == [
        "createdAt", "updatedAt", "cia_integrity"]
    assert contrato.faltantes({}, "07_Knowledge/index.md") == []


def test_el_vocabulario_cia_sale_del_registro_y_no_se_copia():
    from vault_fundamentals_catalog import cia_valores

    for campo in ("cia_integrity", "cia_availability", "cia_sensitivity"):
        assert set(contrato.CAMPOS[campo]["valores"]) == cia_valores(campo)
    arbol = ast.parse((SCRIPTS / "vault_contrato_nota.py").read_text(encoding="utf-8"))
    literales = {n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant)}
    assert "critical" not in literales and "confidential" not in literales


def test_errores_de_valor():
    assert contrato.errores_de_valor({"cia_integrity": "HIGH", "agent": "a"}) == []
    errores = contrato.errores_de_valor({"cia_availability": "critical", "agent": "  "})
    assert len(errores) == 2


def test_validate_no_escribe_su_propia_lista():
    """AP-57: el literal con los campos ya no vive en el validador."""
    arbol = ast.parse((SCRIPTS / "vault_validate.py").read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.List, ast.Tuple, ast.Set)):
            valores = {e.value for e in nodo.elts if isinstance(e, ast.Constant)}
            assert not {"createdAt", "updatedAt"} <= valores, ast.unparse(nodo)


@pytest.mark.parametrize("version", sorted(contrato.HISTORIA))
def test_cada_hito_de_la_historia_tiene_su_fuente(version):
    """La historia no se escribe de memoria: o la cita MIGRATIONS o un commit."""
    import vault_standard_upgrade

    for hito in contrato.HISTORIA[version]:
        fuente = hito["fuente"]
        if fuente.startswith("MIGRATIONS:"):
            texto = repr(vault_standard_upgrade.MIGRATIONS[version])
            assert fuente.split(":", 1)[1] in texto, (version, fuente)
        else:
            assert fuente.startswith("git:"), fuente
            r = subprocess.run(["git", "cat-file", "-e", fuente[4:]], cwd=REPO_ROOT,
                               capture_output=True)
            if r.returncode != 0 and not (REPO_ROOT / ".git").exists():
                pytest.skip("sin historia de git")
            assert r.returncode == 0, fuente


def test_la_historia_cubre_las_versiones_de_migrations():
    import vault_standard_upgrade

    assert contrato.VERSIONES == tuple(vault_standard_upgrade.MIGRATIONS)


def test_el_contrato_de_una_version_crece_y_no_pierde_campos():
    """No-derogación aplicada al contrato: un campo exigido no deja de serlo."""
    previo = set()
    for v in contrato.VERSIONES:
        actual = {c for clase in ("sistema", "contenido")
                  for c in contrato.contrato_de_version(v)["requeridos"][clase]}
        assert previo <= actual, v
        previo = actual


def test_el_contrato_vigente_es_el_que_se_valida():
    vigente = contrato.contrato_de_version(contrato.VERSIONES[-1])
    assert tuple(vigente["requeridos"]["contenido"]) == contrato.campos_requeridos("07_Knowledge/x.md")
    assert tuple(vigente["requeridos"]["sistema"]) == contrato.campos_requeridos("00_System/x.md")


def test_antes_de_v25_no_habia_validador():
    """Declarado, no tapado: v21–v24 no tenían ninguna regla ejecutable."""
    assert contrato.contrato_de_version("v21")["validador"] is False
    assert contrato.contrato_de_version("v25")["validador"] is True


def test_validate_aplica_el_contrato(tmp_path, monkeypatch):
    import vault_validate

    monkeypatch.setattr(vault_validate, "_raiz", lambda: tmp_path)

    (tmp_path / "07_Knowledge").mkdir()
    nota = tmp_path / "07_Knowledge" / "x.md"
    nota.write_text("---\nid: a\ntitle: x\ncreatedAt: '1'\nupdatedAt: '1'\n---\n", encoding="utf-8")
    r = vault_validate.validate_frontmatter(nota)
    assert r["valid"] is False
    assert r["missing"] == contrato.faltantes(r["data"], "07_Knowledge/x.md")
