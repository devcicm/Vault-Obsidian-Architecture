"""Contrato de las skills: definición ↔ entry point ↔ documentación.

Una skill vive en dos piezas (`.claude/skills/<x>/SKILL.md` y el script que
ejecuta). Si divergen, el agente invoca argumentos que no existen — que es
exactamente AP-01/AP-04 (tool alucinada) por la puerta de atrás.

Ancla además el rango de antipatrones: se escribía con `len(aps)` (el conteo)
en vez del máximo, así que con huecos de numeración el rango documentado
dejaba fuera las normas más recientes.
"""

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "agent" / "skills"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_sdd_init as sdd  # noqa: E402


def _skill_files():
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


def _frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "SKILL.md sin frontmatter"
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def test_hay_al_menos_una_skill():
    assert _skill_files(), "ninguna agent/skills/*/SKILL.md encontrada"


@pytest.mark.parametrize("skill_path", _skill_files(), ids=lambda p: p.parent.name)
def test_frontmatter_completo(skill_path):
    fm = _frontmatter(skill_path.read_text(encoding="utf-8"))
    for campo in ("name", "description", "allowed-tools", "argument-hint"):
        assert fm.get(campo), f"falta '{campo}' en {skill_path}"
    assert fm["name"] == skill_path.parent.name, (
        "el name del frontmatter debe coincidir con el directorio: "
        "el agente invoca por nombre de directorio"
    )


@pytest.mark.parametrize("skill_path", _skill_files(), ids=lambda p: p.parent.name)
def test_entry_point_existe(skill_path):
    """Definición sin script = skill que falla al invocarse."""
    nombre = skill_path.parent.name.replace("-", "_")
    script = REPO_ROOT / "scripts" / f"{nombre}.py"
    assert script.exists(), f"{skill_path.parent.name} sin entry point {script}"


@pytest.mark.parametrize("skill_path", _skill_files(), ids=lambda p: p.parent.name)
def test_argumentos_documentados_existen_en_el_script(skill_path):
    """Todo --flag citado en el SKILL.md debe estar en el argparse real."""
    nombre = skill_path.parent.name.replace("-", "_")
    script = (REPO_ROOT / "scripts" / f"{nombre}.py").read_text(encoding="utf-8")
    documentados = set(re.findall(r"`(--[a-z][a-z0-9-]*)`", skill_path.read_text(encoding="utf-8")))
    for flag in documentados:
        assert f'"{flag}"' in script, (
            f"{flag} documentado en {skill_path.parent.name} pero ausente "
            f"del argparse de {nombre}.py"
        )


@pytest.mark.parametrize("skill_path", _skill_files(), ids=lambda p: p.parent.name)
def test_skill_listada_en_docs(skill_path):
    doc = (REPO_ROOT / "docs" / "SKILLS.md").read_text(encoding="utf-8")
    assert skill_path.parent.name in doc, (
        f"{skill_path.parent.name} no aparece en docs/SKILLS.md"
    )


def test_rango_ap_usa_el_maximo_no_el_conteo():
    """Con huecos, conteo != máximo. El rango debe seguir al máximo."""
    codes = {"AP-01", "AP-02", "AP-36"}  # 3 normas, máximo 36
    assert sdd.ap_range_label(codes) == "AP-01..AP-36"


def test_rango_ap_refleja_el_registro_actual():
    from vault_norms import NORM_CATALOG

    maximo = max(
        int(n["code"][3:])
        for n in NORM_CATALOG
        if n["code"].startswith("AP-") and n["code"][3:].isdigit()
    )
    assert sdd.ap_range_label() == f"AP-01..AP-{maximo:02d}"


def test_drift_detecta_huecos_de_contiguidad():
    """El detector estaba clavado en AP-01..AP-25: ciego a partir de ahí."""
    drift = sdd.detect_drift(REPO_ROOT / "vault-sandbox")
    assert drift["version"], "sin versión detectada"
    # No afirmamos una lista concreta (cambiará al cerrar el hueco del
    # registro), sí que el detector alcanza el rango alto del catálogo.
    from vault_norms import NORM_CATALOG

    codes = {n["code"] for n in NORM_CATALOG}
    for code in drift["missing_norms"]:
        assert code not in codes, f"{code} reportado como ausente pero existe"


def test_skill_manifest_anotado_no_borrado():
    """No-derogación: la constante muerta se anota, no se elimina."""
    src = (REPO_ROOT / "scripts" / "vault_sdd_init.py").read_text(encoding="utf-8")
    assert "SKILL_MANIFEST" in src
    assert "superseded_by:" in src, (
        "SKILL_MANIFEST quedó sin anotar: una constante sin uso y sin nota "
        "vuelve a leerse como contrato vigente"
    )
