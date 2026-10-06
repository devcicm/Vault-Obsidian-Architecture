"""Las skills llevan versión y su tabla de argumentos es la del argparse.

`test_skills_contract` mira una dirección: todo `--flag` citado existe en el
script. La otra no la miraba nadie, y por ahí se fue la skill de onboard:
documentaba `--skip 07_Knowledge`, un valor que el script aceptaba y no omitía
nada, y describía `--lang` como el idioma de la prosa cuando es el lenguaje del
proyecto. Medido el 2026-10-05.

Una skill reescrita no borra la anterior (no-derogación): la versión previa
queda al lado como `SKILL-v<x>.md`, y `docs/SKILLS.md` las nombra a las dos.
"""

import ast
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "agent" / "skills"
SCRIPTS = REPO_ROOT / "scripts"
DOC = (REPO_ROOT / "docs" / "SKILLS.md").read_text(encoding="utf-8")
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SKILLS = sorted(SKILLS_DIR.glob("*/SKILL.md"))
IDS = [p.parent.name for p in SKILLS]


def _frontmatter(texto: str) -> dict:
    import yaml

    m = re.match(r"^---\n(.*?)\n---\n", texto, re.DOTALL)
    assert m, "SKILL.md sin frontmatter"
    return yaml.safe_load(m.group(1))


def _version(ruta: Path) -> str:
    return str(_frontmatter(ruta.read_text(encoding="utf-8")).get("version", ""))


def _flags_del_argparse(script: Path) -> set:
    arbol = ast.parse(script.read_text(encoding="utf-8"))
    flags = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Call) and getattr(nodo.func, "attr", "") == "add_argument":
            largos = [a.value for a in nodo.args
                      if isinstance(a, ast.Constant) and str(a.value).startswith("--")]
            if largos:
                flags.add(largos[0])
    return flags


def _flags_de_la_tabla(texto: str) -> set:
    seccion = texto.split("## Arguments", 1)[1].split("\n## ", 1)[0]
    return set(re.findall(r"^\| `(--[a-z][a-z0-9-]*)`", seccion, re.MULTILINE))


@pytest.mark.parametrize("skill", SKILLS, ids=IDS)
def test_el_frontmatter_es_yaml_valido(skill):
    """Criterio del consumidor (AP-44): quien carga la skill lee el frontmatter
    como YAML. Las tres v1.0 llevaban `argument-hint: [--phase N] [--strict]`,
    que `yaml.safe_load` rechaza —dos flujos seguidos—; el test de contrato lo
    partía por `:` y no lo veía. La v1.0 archivada conserva el defecto: es
    historia, y no se descubre como skill."""
    fm = _frontmatter(skill.read_text(encoding="utf-8"))
    assert isinstance(fm, dict) and fm["name"] == skill.parent.name
    assert isinstance(fm["argument-hint"], str), fm["argument-hint"]


@pytest.mark.parametrize("skill", SKILLS, ids=IDS)
def test_la_skill_declara_su_version_y_la_doc_la_publica(skill):
    version = _version(skill)
    assert re.fullmatch(r"\d+\.\d+", version), (skill, version)
    fila = next((l for l in DOC.splitlines() if l.startswith(f"| `{skill.parent.name}`")), None)
    assert fila is not None, skill.parent.name
    assert f"| v{version} |" in fila, fila


@pytest.mark.parametrize("skill", SKILLS, ids=IDS)
def test_las_versiones_anteriores_quedan_al_lado_y_nombradas(skill):
    actual = tuple(map(int, _version(skill).split(".")))
    archivadas = sorted(skill.parent.glob("SKILL-v*.md"))
    for vieja in archivadas:
        numero = vieja.stem[len("SKILL-v"):]
        assert tuple(map(int, numero.split("."))) < actual, vieja
        assert vieja.relative_to(REPO_ROOT).as_posix() in DOC, vieja
    if actual > (1, 0):
        assert archivadas, f"{skill.parent.name} subió de versión sin archivar la anterior"


@pytest.mark.parametrize("skill", SKILLS, ids=IDS)
def test_la_tabla_de_argumentos_es_la_del_argparse(skill):
    script = SCRIPTS / f"{skill.parent.name.replace('-', '_')}.py"
    tabla = _flags_de_la_tabla(skill.read_text(encoding="utf-8"))
    assert tabla == _flags_del_argparse(script), skill.parent.name


def test_los_valores_de_skip_del_ejemplo_los_acepta_el_onboard():
    from vault_onboard import SECCIONES_OMITIBLES

    texto = (SKILLS_DIR / "vault-onboard" / "SKILL.md").read_text(encoding="utf-8")
    bloques = "\n".join(re.findall(r"```bash\n(.*?)```", texto, re.DOTALL))
    usos = re.findall(r"--skip((?: [^\s-][^\s]*)+)", bloques)
    assert usos, "la skill ya no enseña --skip: este test se queda sin objeto"
    for uso in usos:
        assert set(uso.split()) <= set(SECCIONES_OMITIBLES), uso


def test_el_script_de_sdd_init_dice_la_version_de_su_skill():
    """El script imprimía y escribía en el README generado un «v1.0» propio:
    la definición podía subir de versión sin que la salida se enterara."""
    import vault_sdd_init

    assert vault_sdd_init.SKILL_VERSION == _version(SKILLS_DIR / "vault-sdd-init" / "SKILL.md")
