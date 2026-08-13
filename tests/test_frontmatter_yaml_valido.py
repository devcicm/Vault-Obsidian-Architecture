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

import json
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


# ── El ultimo de los diecisiete (v40.7) ──────────────────────────────────────
#
# `vault_slo_save` siguio construyendo su frontmatter a mano despues de que los
# otros dieciseis pasaran al escritor unico. No era un rezagado inocuo: `unit`
# es campo suyo y el valor por defecto de un SLO de disponibilidad es `%`, que
# es justo uno de los dos valores que dejaron notas ilegibles en el vault de
# pruebas y que este fichero abre citando.
#
# Lo pasaba porque `yaml_scalar` ya citaba `unit`. Eso es exactamente lo que
# hace cara la duplicacion: el sitio duplicado acierta hasta el dia que no, y
# el bloque mezclaba tres criterios (`yaml_scalar`, `json.dumps` y f-string
# crudo) donde el titulo iba con comillas puestas a mano.

SAVES = sorted(p.stem for p in (REPO_ROOT / "scripts").glob("*_save.py"))


def test_ningun_save_construye_el_frontmatter_a_mano():
    """El guard de AP-50 para este bloque: la decision se toma en un sitio.

    Un `*_save` que vuelva a abrir su frontmatter con un `"---"` literal esta
    tomando por su cuenta una decision que ya tiene dueno declarado.
    """
    culpables = [
        s for s in SAVES
        if 'Frontmatter(' not in (REPO_ROOT / "scripts" / f"{s}.py").read_text(
            encoding="utf-8")
    ]
    assert not culpables, (
        "escriben su frontmatter a mano en vez de usar vault.autoria."
        "frontmatter: " + ", ".join(culpables)
    )


@pytest.mark.parametrize("unidad", ["%", "ms", "req/s", "Overview: demo"])
def test_el_slo_escribe_una_unidad_hostil_y_se_relee(unidad):
    """Extremo a extremo sobre la tool real, con el valor que rompio fuera.

    Se lee con `yaml.safe_load` y se compara el objeto, no el texto: medir con
    la misma normalizacion que escribio es AP-44.
    """
    import os
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        entorno = dict(os.environ, VAULT_ROOT=tmp, PYTHONIOENCODING="utf-8")
        def corre(script, *argv):
            return subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / f"{script}.py"),
                 *argv],
                env=entorno, capture_output=True, text=True,
                encoding="utf-8", cwd=str(REPO_ROOT))

        corre("vault_init")
        r = corre(
            "vault_slo_save",
            "--project", "demo", "--service", "api de migración",
            "--slo_type", "availability", "--target", "99.9",
            "--unit", unidad,
        )
        assert r.returncode == 0, r.stderr
        ruta = Path(tmp) / json.loads(r.stdout)["path"]
        texto = ruta.read_text(encoding="utf-8")

    datos = yaml.safe_load(texto.split("---", 2)[1])
    assert datos["unit"] == unidad
    assert datos["service"] == "api de migración"
    # El guion largo sale como `--`: el write path normaliza los guiones
    # tipograficos (`vault_encoding.DASH_REPLACEMENTS`) antes de escribir, y lo
    # hacia ya antes de este cambio —el dorado anterior tambien lo trae asi—.
    # Es decision declarada del estandar, no un efecto de pasar al escritor
    # unico: los acentos, que no se normalizan, siguen intactos al lado.
    assert datos["title"] == "SLO: api de migración -- Disponibilidad"
    assert "\\u00" not in texto, "acento escapado por json.dumps"


def test_ningun_envelope_sale_con_los_acentos_escapados():
    """`json.dumps` por defecto escapa: `Migración` sale `Migraci\u00f3n`.

    No rompe nada y por eso llevaba tiempo ahi: 28 de 160 salidas a stdout lo
    hacian y 132 no. El consumidor que lee el envelope recibe basura una de
    cada seis veces, sin que ninguna puerta se ponga roja.

    Se comprueba por AST y no por grep: dos de los sitios que un grep encuentra
    estan dentro de docstrings, y uno de ellos es el ejemplo de lo que NO hay
    que hacer en `vault_error_contract`.
    """
    import ast

    culpables = []
    for f in sorted(list((REPO_ROOT / "scripts").glob("*.py"))
                    + list((REPO_ROOT / "cli").glob("*.py"))):
        for nodo in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if not (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name)
                    and nodo.func.id == "print"):
                continue
            for arg in nodo.args:
                if (isinstance(arg, ast.Call)
                        and isinstance(arg.func, ast.Attribute)
                        and arg.func.attr == "dumps"
                        and getattr(arg.func.value, "id", "") == "json"
                        and not any(k.arg == "ensure_ascii" for k in arg.keywords)):
                    culpables.append(f"{f.name}:{arg.lineno}")

    assert not culpables, (
        "json.dumps a stdout sin ensure_ascii=False: " + ", ".join(culpables))


# ── El guard medía una línea, no la norma (v40.16) ───────────────────────────
#
# `test_ninguna_tool_escribe_el_titulo_sin_escapar` vigila el literal
# `f"title: {`. Es un patrón, no una norma: `generate_frontmatter` escapaba el
# título y concatenaba **todo lo demás** en crudo, y el guard salía verde.
# Lo de abajo mide el bloque entero, y por su efecto —lo que el consumidor
# lee— en vez de por la forma del código que lo escribe (AP-44).

_VALORES_QUE_MIENTEN = [
    ("owner", "#infra", "YAML lo lee como comentario: el valor DESAPARECE"),
    ("version", "1.0", "vuelve como float"),
    ("answer", "no", "vuelve como False"),
    ("serie", "007", "vuelve como int 7"),
    ("dia", "2026-01-01", "vuelve como datetime.date"),
    ("summary", "Overview: demo", "dos puntos sin escapar rompen el bloque"),
    ("owner2", "@carlos", "arroba reservada"),
    ("marca", "*star", "alias YAML"),
    ("hueco", "  con bordes  ", "el espacio de los extremos se pierde"),
    ("multi", "una\nlinea mas", "el salto parte el bloque"),
]


@pytest.mark.parametrize("clave,valor,por_que", _VALORES_QUE_MIENTEN)
def test_ningun_campo_de_meta_llega_distinto_al_consumidor(clave, valor, por_que):
    """Todo `--meta` vuelve del parser igual que entró, o el guard falla.

    El peor caso no es el que revienta: es `#infra`, que produce un bloque
    perfectamente parseable con el campo vacío. La nota queda en disco, el
    verificador la aprueba y el dato se perdió sin que nada lo dijera.
    """
    import vault_write

    bloque = vault_write.generate_frontmatter(
        title="Demo", tags=[], folder="07_Knowledge", meta={clave: valor}
    )
    datos = yaml.safe_load(bloque.split("---")[1])
    assert datos.get(clave) == valor, (
        f"`{clave}: {valor!r}` no sobrevive al viaje ({por_que}); "
        f"volvió {datos.get(clave)!r}"
    )


def test_los_campos_propios_del_bloque_tambien_se_escapan():
    """`agent`, `status_note` y los tres CIA son texto libre y salían crudos."""
    import vault_write

    bloque = vault_write.generate_frontmatter(
        title="Demo", tags=[], folder="07_Knowledge",
        meta={"agent": "claude: opus", "cia_sensitivity": "#interno"},
    )
    datos = yaml.safe_load(bloque.split("---")[1])
    assert datos["agent"] == "claude: opus"
    assert datos["cia_sensitivity"] == "#interno"
