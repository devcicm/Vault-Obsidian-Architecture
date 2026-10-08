"""SBOM SPDX (ISO/IEC 5962) e inventario de licencias (ISO/IEC 5230).

Lo que mide es que el SBOM no se pueda escribir a mano: cada paquete y cada
licencia salen de `pyproject.toml` y de los metadatos instalados, y lo que no
se puede medir sale como NOASSERTION en vez de suponerse.
"""

import json
import re
from pathlib import Path

from empaquetado import sbom

ROOT = Path(__file__).resolve().parents[1]


def _deps_de_pyproject():
    texto = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    bloque = re.search(r"^dependencies\s*=\s*\[(.*?)\]", texto, re.M | re.S).group(1)
    return [sbom._nombre_de_requisito(r) for r in re.findall(r'"([^"]+)"', bloque)]


def test_el_sbom_describe_el_paquete_y_toda_dependencia_declarada():
    doc = sbom.construir()
    assert doc["spdxVersion"] == "SPDX-2.2" and doc["dataLicense"] == "CC0-1.0"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", doc["creationInfo"]["created"])
    nombres = [p["name"] for p in doc["packages"]]
    assert nombres[0] == "vault-obsidian-architecture"
    deps = _deps_de_pyproject()
    assert deps and nombres[1:] == deps
    raiz = doc["packages"][0]["SPDXID"]
    dependientes = {r["relatedSpdxElement"] for r in doc["relationships"]
                    if r["relationshipType"] == "DEPENDS_ON" and r["spdxElementId"] == raiz}
    assert dependientes == {p["SPDXID"] for p in doc["packages"][1:]}
    describe = [r for r in doc["relationships"] if r["relationshipType"] == "DESCRIBES"]
    assert describe == [{"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES",
                         "relatedSpdxElement": raiz}]
    json.dumps(doc)  # serializable tal cual


def test_la_licencia_propia_coincide_con_el_fichero_license():
    """El classifier dice MIT; el criterio del consumidor es el texto que recibe."""
    doc = sbom.construir()
    propia = doc["packages"][0]
    assert propia["licenseDeclared"] == "MIT"
    assert (ROOT / "LICENSE").read_text(encoding="utf-8").startswith("MIT License")
    assert propia["copyrightText"].startswith("Copyright")


def test_pyyaml_instalado_lleva_su_version_y_licencia_medidas():
    from importlib import metadata
    (yaml_,) = [p for p in sbom.inventario(sbom.construir()) if p["name"] == "PyYAML"]
    assert yaml_["version"] == metadata.version("PyYAML")
    assert yaml_["license"] == "MIT"


def test_lo_que_no_se_puede_medir_sale_como_noassertion(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "1"\n'
        'dependencies = ["paquete-que-no-existe-voa>=1"]\n', encoding="utf-8")
    doc = sbom.construir(tmp_path)
    propia, dep = doc["packages"]
    assert propia["licenseDeclared"] == sbom.NOASSERTION   # sin classifier ni LICENSE
    assert propia["copyrightText"] == sbom.NOASSERTION
    assert dep["licenseDeclared"] == sbom.NOASSERTION and "versionInfo" not in dep


def test_una_licencia_bsd_ambigua_no_se_adivina():
    assert sbom._licencia_de(None, ["License :: OSI Approved :: BSD License"]) == sbom.NOASSERTION
    assert sbom._licencia_de("BSD-3-Clause", ["License :: OSI Approved :: BSD License"]) == "BSD-3-Clause"


def test_el_inventario_falla_si_algo_queda_sin_licencia(monkeypatch, capsys):
    doc = sbom.construir()
    doc["packages"][1]["licenseDeclared"] = sbom.NOASSERTION
    monkeypatch.setattr(sbom, "construir", lambda: doc)
    assert sbom.main(["--inventario"]) == 1
    assert "sin licencia afirmada" in capsys.readouterr().err


def test_la_ci_genera_y_publica_el_sbom():
    ci = (ROOT / ".github" / "workflows" / "vault-ci.yml").read_text(encoding="utf-8")
    assert "python empaquetado/sbom.py --salida dist/sbom.spdx.json" in ci
    assert "actions/upload-artifact" in ci
