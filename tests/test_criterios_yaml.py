"""AP-57 · YAML de datos vs YAML ejecutable (H-F2-05).

El guard incluye `.yml/.yaml` en `EXT_EJECUTABLES` para no dejar sin medir un
workflow de CI fuera de `.github/`. El efecto colateral era que los inventarios
YAML de evidencia se reportaban como `frontera_no_declarada`.

Estas pruebas fijan las dos mitades del criterio: lo que debe seguir
detectándose (un CI mal ubicado) y lo que no debe reportarse (datos).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import vault_criterios  # noqa: E402


INVENTARIO = """
# Inventario de deuda: datos, no trabajo
- id: TD-0001
  titulo: ejemplo
  severity: P2
  aceptacion:
    - criterio uno
"""

WORKFLOW = """
name: ci
on:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""


def test_un_inventario_yaml_no_es_ejecutable():
    assert vault_criterios.yaml_es_ejecutable("audits/fase2/inventario.yaml", INVENTARIO) is False


def test_un_workflow_es_ejecutable_aunque_este_mal_ubicado():
    assert vault_criterios.yaml_es_ejecutable("ci/deploy.yaml", WORKFLOW) is True


def test_un_yaml_bajo_github_es_ejecutable_por_definicion():
    assert vault_criterios.yaml_es_ejecutable(".github/workflows/x.yml", "{}") is True


def test_una_clave_indentada_no_convierte_datos_en_ejecutable():
    datos = "config:\n  on: siempre\n  jobs: 3\n"
    assert vault_criterios.yaml_es_ejecutable("docs/config.yaml", datos) is False


def test_una_clave_en_comentario_no_convierte_datos_en_ejecutable():
    datos = "# on: push\n# jobs:\n- id: TD-0001\n"
    assert vault_criterios.yaml_es_ejecutable("audits/x.yaml", datos) is False


def test_los_yaml_de_evidencia_del_repo_no_son_frontera():
    """Integración: los inventarios reales deja de salir como hallazgo."""
    hallazgos = vault_criterios.medir_fronteras()
    culpables = [h["modulo"] for h in hallazgos
                 if h["criterio"] == "frontera_no_declarada"
                 and h["modulo"].startswith("audits/")]
    assert culpables == [], culpables


def test_el_workflow_del_repo_sigue_siendo_zona_declarada():
    zonas = {str(p).replace("\\", "/") for p in vault_criterios._zonas_declaradas()}
    assert any(z.endswith(".github/workflows/vault-ci.yml") for z in zonas), zonas
