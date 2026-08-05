"""AP-45 — una nota que existe para llenar la sección, no para afirmar algo.

El síntoma que motivó la norma es medible: `vault_onboard` sobre un proyecto
real emitía 8 notas de concepto cuyo cuerpo entero era
`_Pendiente. Leer la sección del README._`, más cinco ADRs numerados sin nombre.
Ninguna tool lo reprobaba: para el conteo eran 13 notas, para el health score
eran cobertura, y para quien las abría eran nada.

Lo caro no es el hueco: es taparlo. Una sección vacía invita a llenarla; una
sección con trece stubs declara que el trabajo ya está hecho.

El guard exige las DOS condiciones —cuerpo sin contenido Y sin wikilinks
salientes— porque cada una por separado tiene usos legítimos. Estos tests fijan
esa frontera, que es donde un guard de este tipo se rompe: no en lo que detecta,
sino en lo que arrastra por delante.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_norms  # noqa: E402
from vault_norms import NORM_CATALOG, vault_norms_audit  # noqa: E402


FM = (
    "---\n"
    "title: {title}\n"
    "type: concept\n"
    "status: {status}\n"
    'tags: ["x"]\n'
    "---\n\n"
)


def _vault(tmp_path):
    root = tmp_path / "vault"
    (root / "09_Knowledge").mkdir(parents=True)
    return root


def _nota(root, nombre, cuerpo, status="draft", title=None):
    p = root / "09_Knowledge" / f"{nombre}.md"
    p.write_text(
        FM.format(title=title or nombre, status=status) + cuerpo, encoding="utf-8"
    )
    return f"09_Knowledge/{nombre}.md"


def _ap45(root):
    return {
        v["path"]
        for v in vault_norms_audit(root).get("violations", [])
        if v["norm"] == "AP-45"
    }


# ── La norma existe y es exigible ────────────────────────────────────────────


def test_ap45_esta_en_el_catalogo_con_enforcement_real():
    norma = next((n for n in NORM_CATALOG if n["code"] == "AP-45"), None)
    assert norma is not None, "AP-45 no está en NORM_CATALOG"
    assert norma["enforcement"] in {"guard", "audit", "guard+audit"}, (
        "regla no negociable del repo: `manual` no es enforcement"
    )
    assert norma["tools_detecting"], "una norma que ninguna tool detecta no gobierna"


# ── Lo que detecta ───────────────────────────────────────────────────────────


def test_el_relleno_literal_de_onboard_se_reporta(tmp_path):
    """El caso medido: cuerpo entero remitiendo a leer otra fuente."""
    root = _vault(tmp_path)
    rel = _nota(
        root, "orquestacion", "# Orquestación\n\n_Pendiente. Leer la sección del README._\n"
    )
    assert rel in _ap45(root)


def test_una_seccion_de_no_detectados_se_reporta(tmp_path):
    root = _vault(tmp_path)
    rel = _nota(root, "dependencias", "## Dependencias\n\n- No detectadas\n\n## Notas\n\nTODO\n")
    assert rel in _ap45(root)


def test_una_tabla_de_solo_cabecera_no_cuenta_como_contenido(tmp_path):
    """Promete columnas y no trae ni una fila. La cabecera tiene texto, así que
    un filtro línea a línea la dejaría pasar — hay que quitar la tabla entera."""
    root = _vault(tmp_path)
    rel = _nota(root, "modulos", "## Módulos\n\n| Módulo | Rol |\n|---|---|\n\n---\n")
    assert rel in _ap45(root)


# ── Lo que NO detecta: la frontera ───────────────────────────────────────────


def test_un_parrafo_real_basta_aunque_sea_corto(tmp_path):
    """El umbral es afirmar algo, no la longitud. Una frase verdadera es una nota."""
    root = _vault(tmp_path)
    rel = _nota(root, "runtime", "## Runtime\n\nEl scraper usa Playwright sobre Chromium.\n")
    assert rel not in _ap45(root)


def test_una_nota_de_puros_enlaces_no_se_reporta(tmp_path):
    """Un índice temático es prosa cero y valor alto: el enlace ES la afirmación."""
    root = _vault(tmp_path)
    _nota(root, "destino", "Contenido real.\n")
    rel = _nota(root, "mapa", "## Mapa\n\n- [[destino]]\n")
    assert rel not in _ap45(root)


def test_un_primer_de_vault_init_no_se_reporta(tmp_path):
    """`status: template` anuncia lo que es. Andamiaje declarado no es relleno:
    el relleno miente sobre su naturaleza, el primer no."""
    root = _vault(tmp_path)
    rel = _nota(root, "00-09_knowledge-primer", "## Uso\n\n_Pendiente_\n", status="template")
    assert rel not in _ap45(root)


def test_un_indice_de_seccion_vacio_no_se_reporta(tmp_path):
    """Lo genera `vault_section_index` a partir de lo que hay. Un índice vacío
    refleja una sección vacía — reportarlo sería culpar al espejo."""
    root = _vault(tmp_path)
    rel = _nota(root, "index", "# 09_Knowledge\n\n---\n")
    assert rel not in _ap45(root)


def test_nada_dentro_de_una_instantanea_se_reporta(tmp_path):
    """Un backup es una foto del pasado. Reportarlo multiplica cada hallazgo por
    el número de copias y convierte el audit en ruido."""
    root = _vault(tmp_path)
    snap = root / "vault-backups" / "2026-01-01" / "09_Knowledge"
    snap.mkdir(parents=True)
    (snap / "orquestacion.md").write_text(
        FM.format(title="x", status="draft") + "_Pendiente_\n", encoding="utf-8"
    )
    assert not _ap45(root)


# ── El extractor, aislado ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "cuerpo",
    [
        "",
        "# Solo un encabezado\n",
        "## A\n\n_Pendiente_\n\n## B\n\nTODO\n",
        "- Desconocido\n- N/A\n",
        "```\n```\n",
        "---\n\n***\n",
    ],
)
def test_cuerpos_que_no_afirman_nada(cuerpo):
    assert vault_norms._cuerpo_sin_marcadores(cuerpo) == ""


def test_una_frase_que_empieza_por_un_marcador_sigue_siendo_contenido():
    """La frontera que este guard estuvo a punto de cruzar.

    El primer intento casaba el marcador por prefijo, así que «Pendiente de
    revisar el retry, pero el flujo ya está descrito arriba» —una frase que
    afirma dos cosas— desaparecía entera. Es el mismo defecto que
    `PLACEHOLDER_PATTERNS` en `vault_audit`, donde `patron` como prefijo se
    tragaba los enlaces a `patron-mcp-streaming`: AP-44, decidir con criterio
    propio en vez de mirar lo que hay.

    La regla que quedó: el marcador es la línea ENTERA, o un aparte envuelto
    en énfasis de principio a fin.
    """
    frase = "Pendiente de revisar el retry, pero el flujo ya está descrito arriba."
    assert vault_norms._cuerpo_sin_marcadores(frase) == frase
    assert vault_norms._cuerpo_sin_marcadores("_Pendiente. Leer el README._") == ""


@pytest.mark.parametrize(
    "cuerpo",
    [
        "Una frase.",
        "## A\n\nAlgo cierto.\n",
        "| Módulo | Rol |\n|---|---|\n| core | orquesta |\n",
        "- Pendiente de revisar el retry, pero el flujo ya está descrito arriba.\n",
    ],
)
def test_cuerpos_que_si_afirman_algo(cuerpo):
    assert vault_norms._cuerpo_sin_marcadores(cuerpo) != ""
