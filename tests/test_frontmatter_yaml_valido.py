"""El frontmatter que escriben las tools tiene que poder leerse.

Tres notas del vault de pruebas —escritas por las tools de este estándar— no
parseaban: `title: Overview: demo` no es un mapeo YAML, y `unit: %` empieza por
un carácter que YAML reserva. El fichero se escribía sin error y sin aviso, y la
nota perdía **todo** su frontmatter al leerse: sin id, sin tags, sin tipo. Para
`vault_audit` era una nota sin metadatos; para Obsidian, una nota sin
propiedades.

El origen es que veinticuatro tools construyen su frontmatter concatenando
f-strings, y solo ocho se acordaban de escapar. No es que ocho lo hicieran bien:
es que la decisión se tomaba veinticuatro veces.
"""

import re
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from vault_lib import yaml_scalar  # noqa: E402

HOSTILES = [
    "Overview: demo",
    "file_lock: TOCTOU en cleanup",
    "100%",
    "%",
    "#hashtag",
    "*asterisco*",
    "&ancla",
    "[corchetes]",
    "{llaves}",
    "- guion inicial",
    "yes",
    "no",
    "null",
    "123",
    "2026-08-06",
    'con "comillas" dentro',
    "con 'simples' dentro",
    "dos\nlineas",
    "",
    "  espacios  ",
]


@pytest.mark.parametrize("valor", HOSTILES)
def test_todo_escalar_sobrevive_la_ida_y_la_vuelta(valor):
    """Escrito y releído, el valor es el mismo objeto que entró."""
    texto = f"clave: {yaml_scalar(valor)}"
    assert yaml.safe_load(texto)["clave"] == valor, texto


@pytest.mark.parametrize("valor", ["simple", "sin-nada-raro", "https://x.test/a?b=1"])
def test_lo_que_ya_era_valido_no_se_cita(valor):
    """No cita por si acaso: solo si hace falta.

    Importa porque si citara siempre, este cambio reescribiría el frontmatter de
    cada nota del estándar y de cada vault consumidor sin necesidad.
    """
    assert yaml_scalar(valor) == valor


def test_una_lista_sigue_viajando_como_lista():
    """`tags:` y `norm_refs:` se escriben como JSON de flujo y así deben quedar."""
    assert yaml.safe_load(f"tags: {yaml_scalar(['a', 'b'])}")["tags"] == ["a", "b"]


def test_ninguna_tool_escribe_el_titulo_sin_escapar():
    """El guard: la decisión se toma en un sitio, no en veinticuatro.

    Escribir `f"title: {title}"` vuelve a abrir exactamente el agujero que
    dejó tres notas ilegibles en el vault de pruebas.
    """
    patron = re.compile(r'f"title: \{(?!json\.dumps|yaml_scalar)')
    culpables = [
        f"{f.name}:{s[:m.start()].count(chr(10)) + 1}"
        for f in sorted((REPO_ROOT / "scripts").glob("*.py"))
        for s in [f.read_text(encoding="utf-8")]
        for m in patron.finditer(s)
    ]
    assert not culpables, (
        "títulos escritos sin pasar por yaml_scalar() ni json.dumps(): "
        + ", ".join(culpables)
    )


def test_el_write_path_escribe_un_frontmatter_parseable():
    """Extremo a extremo sobre el generador real, con el título que rompió."""
    import vault_write

    bloque = vault_write.generate_frontmatter(
        title="Overview: 100% del *plan* [v2]",
        tags=["prueba"],
        folder="07_Knowledge",
        meta={},
    )
    lineas = bloque if isinstance(bloque, list) else bloque.splitlines()
    datos = yaml.safe_load("\n".join(l for l in lineas if l.strip() != "---"))
    assert datos["title"] == "Overview: 100% del *plan* [v2]"
    assert datos["tags"] == ["prueba"]
