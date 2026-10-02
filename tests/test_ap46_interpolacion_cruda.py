"""AP-46: ningún módulo interpola `title:` o `project:` crudos en un frontmatter.

El 2026-10-01 aparecieron tres sitios que lo hacían después de que v40.34
diera el escape por migrado: `vault_project_status` (`project: Alfa #1` dejaba
la nota atribuida a `Alfa`), los stubs de `vault_graph_fix` (`title: %tasa`
no es YAML) y el primer de `vault_init` (escapaba la mitad del valor). Los tres
se corrigieron con su test de comportamiento; este fija la forma para que un
cuarto no entre sin que nadie lo vea.

Es un guard sintáctico y declara su alcance: mira las dos claves que llevan
texto libre del invocante, en líneas de una f-string. Un valor escapado se
reconoce porque pasa por un escapador del kernel o porque vive en una variable
`*_yaml`, que es la convención para un escalar ya escapado. No ve una clave
montada por concatenación ni un valor que llegue escapado por otro nombre.
`_archived/` queda fuera, con el mismo criterio que `vault_criterios`: es
código conservado por no-derogación, no ejecutado.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Los escapadores con dueño (`vault.kernel.frontmatter_parsing`) y JSON, que es
#: un escalar YAML entre comillas.
_ESCAPADO = re.compile(r"\{(yaml_scalar|valor_de_frontmatter|json\.dumps)\(|\{\w+_yaml\}")
_CLAVE_INTERPOLADA = re.compile(r"\b(title|project): \{")


def _fuentes():
    for carpeta in ("scripts", "cli", "vault"):
        for p in (ROOT / carpeta).rglob("*.py"):
            if "_archived" not in p.parts and "__pycache__" not in p.parts:
                yield p


def test_ningun_title_ni_project_se_interpola_crudo():
    crudos = []
    for fuente in _fuentes():
        for n, linea in enumerate(fuente.read_text(encoding="utf-8").splitlines(), 1):
            for m in _CLAVE_INTERPOLADA.finditer(linea):
                if not _ESCAPADO.match(linea, m.end() - 1):
                    crudos.append(f"{fuente.relative_to(ROOT).as_posix()}:{n}: {linea.strip()}")
    assert not crudos, "AP-46 — valor interpolado sin escapar:\n" + "\n".join(crudos)


def test_el_guard_ve_la_forma_que_existe_para_detectar():
    assert _CLAVE_INTERPOLADA.search("title: {target_stem}")
    assert not _ESCAPADO.match("title: {target_stem}", len("title: "))
    assert _ESCAPADO.match("title: {yaml_scalar(t)}", len("title: "))
    assert _ESCAPADO.match("title: {titulo_yaml}", len("title: "))
