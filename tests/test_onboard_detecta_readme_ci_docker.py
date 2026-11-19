"""The onboarding reads README headings, CI jobs and Docker facts (writer U2, 2026-11-19).

Six compiled patterns were called as `patron.findall(text, re.MULTILINE)`: on a
compiled pattern the second argument is `pos`, so they searched from character
8 without MULTILINE and `^` never matched. README headings (concept notes),
CI jobs, docker-compose services and Dockerfile FROM/EXPOSE were never
detected on any real project: the infra note always said "No detectados".
"""

from test_onboard_escalonado import PROYECTO, proyecto, vault  # noqa: F401  (fixtures)


def _texto(v, carpeta):
    return "\n".join(n.read_text(encoding="utf-8") for n in sorted((v / carpeta).rglob("*.md"))
                     if n.stem != "index")


def test_los_jobs_del_workflow_llegan_a_la_nota_del_flujo(vault):
    v, _ = vault
    assert "- `test`" in _texto(v, "13_Flows")


def test_los_servicios_de_docker_compose_llegan_a_la_infraestructura(vault):
    v, _ = vault
    infra = _texto(v, "09_Infrastructure")
    assert "api" in infra, infra[:1500]


def test_los_titulos_del_readme_alimentan_los_conceptos(vault):
    v, _ = vault
    assert "Arquitectura" in _texto(v, "07_Knowledge")


def test_ningun_patron_compilado_recibe_un_flag_como_posicion():
    """The static guard: a flag passed where `pos` goes is the same bug again."""
    import ast
    from pathlib import Path

    fuente = (Path(__file__).resolve().parent.parent / "scripts" / "vault_onboard.py").read_text(
        encoding="utf-8")
    malos = []
    for nodo in ast.walk(ast.parse(fuente)):
        if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr in ("search", "match", "findall", "finditer", "fullmatch")
                and isinstance(nodo.func.value, ast.Name) and nodo.func.value.id.startswith("_RE_")
                and len(nodo.args) >= 2):
            malos.append(nodo.lineno)
    assert malos == [], malos
