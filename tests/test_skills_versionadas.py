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
from pathlib import Path

import pytest

from apoyo import git_en

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "agent" / "skills"
SCRIPTS = REPO_ROOT / "scripts"
DOC = (REPO_ROOT / "docs" / "SKILLS.md").read_text(encoding="utf-8")

SKILLS = sorted(SKILLS_DIR.glob("*/SKILL.md"))
IDS = [p.parent.name for p in SKILLS]

import vault_grafo_import as gi  # noqa: E402


def _frontmatter(texto: str) -> dict:
    import yaml

    m = re.match(r"^---\n(.*?)\n---\n", texto, re.DOTALL)
    assert m, "SKILL.md sin frontmatter"
    return yaml.safe_load(m.group(1))


def _version(ruta: Path) -> str:
    return str(_frontmatter(ruta.read_text(encoding="utf-8")).get("version", ""))


def _flags_del_argparse(script: Path) -> set:
    arbol = ast.parse(gi.codigo_de(script).read_text(encoding="utf-8"))
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
    """El historial es real, no una convención de nombres (paper 4.5).

    Tres exigencias, en orden de costo: la archivada existe, `docs/SKILLS.md`
    la nombra, y **Git la lleva** — una copia en disco sin seguimiento se
    pierde en la primera sincronización, que es exactamente como estaba la
    `SKILL-v2.0.md` en el árbol de otro agente cuando la re-auditoría la
    midió. Y el peldaño tiene que ser el **inmediatamente anterior**: de
    v1.0 a v2.1 sin v2.0 archivada, el salto deja la v2.0 sin restauración
    posible.
    """
    actual = tuple(map(int, _version(skill).split(".")))
    archivadas = sorted(skill.parent.glob("SKILL-v*.md"))
    seguidos = set(git_en(REPO_ROOT, "ls-files", "agent/skills").splitlines())
    numeros = []
    for vieja in archivadas:
        numero = vieja.stem[len("SKILL-v"):]
        numero_t = tuple(map(int, numero.split(".")))
        assert numero_t < actual, vieja
        numeros.append(numero_t)
        assert vieja.relative_to(REPO_ROOT).as_posix() in DOC, vieja
        relativa = vieja.relative_to(REPO_ROOT).as_posix()
        assert relativa in seguidos, (
            f"{relativa} existe en disco pero no está en Git: la copia del "
            f"repo no la lleva y el historial se pierde al sincronizar")
    if actual > (1, 0):
        if actual[1] > 0:
            requerida = (actual[0], actual[1] - 1)
            assert requerida in numeros, (
                f"{skill.parent.name} v{actual[0]}.{actual[1]} no tiene "
                f"archivada la inmediatamente anterior "
                f"v{requerida[0]}.{requerida[1]}: el historial tiene un "
                f"salto ({sorted(numeros)})")
        else:
            mayores = [n for n in numeros if n[0] == actual[0] - 1]
            assert mayores, (
                f"{skill.parent.name} subió a v{actual[0]}.0 sin archivar "
                f"ninguna v{actual[0] - 1}.x")


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
