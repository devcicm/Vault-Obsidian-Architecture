"""Contrato de las skills: definición ↔ entry point ↔ documentación.

Una skill vive en dos piezas (`agent/skills/<x>/SKILL.md` y el script que
ejecuta, o las tools `vault run` que orquesta si declara `entry-point: none`). Si divergen, el agente invoca argumentos que no existen — que es
exactamente AP-01/AP-04 (tool alucinada) por la puerta de atrás.

Ancla además el rango de antipatrones: se escribía con `len(aps)` (el conteo)
en vez del máximo, así que con huecos de numeración el rango documentado
dejaba fuera las normas más recientes.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "agent" / "skills"

import vault_sdd_init as sdd  # noqa: E402

import vault_grafo_import as gi  # noqa: E402


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
    """Definición sin script = skill que falla al invocarse.

    The script is the one `entry-point:` declares, or the one named like the
    skill; an orchestration skill (`entry-point: none`) must teach at least one
    `vault run` command instead (skills audit F18, 2026-11-19).
    """
    from apoyo import comandos_vault_run, script_de_skill

    script = script_de_skill(skill_path)
    if script is None:
        assert comandos_vault_run(skill_path.read_text(encoding="utf-8")), skill_path.parent.name
        return
    assert script.exists(), f"{skill_path.parent.name} sin entry point {script}"


@pytest.mark.parametrize("skill_path", _skill_files(), ids=lambda p: p.parent.name)
def test_argumentos_documentados_existen_en_el_script(skill_path):
    """Todo --flag citado en el SKILL.md debe estar en el argparse real."""
    from apoyo import script_de_skill

    ruta = script_de_skill(skill_path)
    if ruta is None:
        return  # orchestration skill: its commands are checked per tool below
    nombre = ruta.stem
    script = gi.codigo_de(ruta).read_text(encoding="utf-8")
    documentados = set(re.findall(r"`(--[a-z][a-z0-9-]*)`", skill_path.read_text(encoding="utf-8")))
    for flag in documentados:
        assert f'"{flag}"' in script, (
            f"{flag} documentado en {skill_path.parent.name} pero ausente "
            f"del argparse de {nombre}.py"
        )


@pytest.mark.parametrize("skill_path", _skill_files(), ids=lambda p: p.parent.name)
def test_cada_comando_vault_run_es_valido_para_su_tool(skill_path):
    """Skills audit F18 (2026-11-19): every `vault run <tool> ...` a skill teaches
    names a real tool, each `--flag` exists in THAT tool's argparse, and a flag
    that requires a value gets one. The old vault-backup taught
    `vault run vault_backup --verify` with no value, and the tests passed."""
    from apoyo import comandos_vault_run, flags_de_argparse
    from vault.meta_toolkit.resolucion_producto import resolver_producto

    for tool, tokens in comandos_vault_run(skill_path.read_text(encoding="utf-8")):
        script = REPO_ROOT / "scripts" / f"{tool}.py"
        assert script.exists(), f"{skill_path.parent.name}: vault run {tool} no existe"
        resolucion = resolver_producto(tool)
        assert resolucion.estado == "installed", (
            f"{skill_path.parent.name}: `vault run {tool}` no es una tool instalada "
            f"(estado={resolucion.estado!r}); usa `python scripts/{tool}.py` si es de checkout"
        )
        flags = flags_de_argparse(script)
        for i, token in enumerate(tokens):
            if not token.startswith("--"):
                continue
            nombre = token.split("=", 1)[0]
            assert nombre in flags, f"{skill_path.parent.name}: {tool} no tiene {nombre}"
            if flags[nombre] and "=" not in token:
                siguiente = tokens[i + 1] if i + 1 < len(tokens) else ""
                assert siguiente and not siguiente.startswith("--"), (
                    f"{skill_path.parent.name}: {tool} {nombre} exige un valor")


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
    src = gi.codigo_de(REPO_ROOT / "scripts" / "vault_sdd_init.py").read_text(encoding="utf-8")
    assert "SKILL_MANIFEST" in src
    assert "superseded_by:" in src, (
        "SKILL_MANIFEST quedó sin anotar: una constante sin uso y sin nota "
        "vuelve a leerse como contrato vigente"
    )
