"""Toda norma catalogada tiene sección propia en el manifiesto.

El hueco que motivó el guard: once normas (AP-25..AP-35) llevaban entre diez y
tres versiones **aplicadas y midiendo** —penalizan el health score, tienen
etiqueta propia en la salida de `vault_audit`, están en `NORM_CATALOG`— y sin
sección en el manifiesto. `vault_norms --list` las mostraba; la representación
pública del estándar, no.

Lo que lo hacía invisible es que sí aparecían **mencionadas**, en entradas de
changelog que contaban cuándo se registraron. Cualquier comprobación por
subcadena (`"AP-25" in texto`) habría dado verde. Por eso la medida es el
encabezado: es lo que busca quien lee el manifiesto para entender la norma, y
medir con el criterio del lector en vez de con el cómodo es AP-44.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

import vault_norms  # noqa: E402

MANIFIESTO = REPO_ROOT / "vault-obsidian-architecture.md"
ENCABEZADO = re.compile(r"^#{2,4}\s+((?:AP|PAT|SP|CN)-\d+)", re.M)


@pytest.fixture(scope="module")
def texto():
    return MANIFIESTO.read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def encabezados(texto):
    return set(ENCABEZADO.findall(texto))


@pytest.mark.parametrize("codigo", [n["code"] for n in vault_norms.NORM_CATALOG])
def test_cada_norma_tiene_seccion(codigo, encabezados):
    assert codigo in encabezados, (
        f"{codigo} está en NORM_CATALOG y no tiene sección en el manifiesto"
    )


def test_el_guard_lo_comprueba_y_no_solo_este_test(tmp_path, monkeypatch):
    """El test no puede ser el único sitio donde vive la regla.

    Un test que compruebe algo que la puerta no comprueba deja la regla fuera
    del checklist de cierre: se cumple mientras alguien ejecute la suite
    entera. Aquí se verifica que `--check-framework` **falla de verdad** con
    un manifiesto al que le falta una sección, en vez de confiar en que la
    comprueba porque el código lo diga.
    """
    recortado = tmp_path / "manifiesto.md"
    original = MANIFIESTO.read_text(encoding="utf-8", errors="replace")
    codigo = vault_norms.NORM_CATALOG[0]["code"]
    recortado.write_text(
        re.sub(rf"^#{{2,4}}\s+{re.escape(codigo)}\b", "#### xxx", original, flags=re.M),
        encoding="utf-8",
    )

    r = vault_norms.framework_drift_check(recortado)
    assert not r["ok"], "el guard aprobó un manifiesto sin la sección"
    assert codigo in r["norms_without_section"]


def test_una_mencion_de_pasada_no_cuenta_como_seccion(tmp_path):
    """La regresión concreta: `"AP-25" in texto` daba verde durante diez versiones."""
    falso = tmp_path / "manifiesto.md"
    original = MANIFIESTO.read_text(encoding="utf-8", errors="replace")
    codigo = vault_norms.NORM_CATALOG[0]["code"]
    # La sección desaparece, pero la mención sobrevive en prosa.
    sin_seccion = re.sub(
        rf"^#{{2,4}}\s+{re.escape(codigo)}\b",
        f"#### derogada\n\nVer {codigo} más abajo.",
        original,
        flags=re.M,
    )
    falso.write_text(sin_seccion, encoding="utf-8")

    assert codigo in falso.read_text(encoding="utf-8"), "la mención sigue ahí"
    assert codigo in vault_norms.framework_drift_check(falso)["norms_without_section"]


def test_el_manifiesto_real_esta_completo():
    """La puerta, tal como la corre el checklist de cierre."""
    r = vault_norms.framework_drift_check()
    assert r["ok"], (
        f"sin sección: {r['norms_without_section']} | ids sin doc: {r['missing']}"
    )
    assert r["norms_total"] == len(vault_norms.NORM_CATALOG)


def test_un_encabezado_dentro_de_un_bloque_de_codigo_no_cuenta(tmp_path):
    """A-17 — la sección quitada y su encabezado sobreviviendo en un ejemplo.

    Un `## AP-NN` dentro de un fence es un ejemplo de nota: el lector no lo ve
    como sección, y el `re.M` sobre el texto crudo sí lo contaba.
    """
    falso = tmp_path / "manifiesto.md"
    original = MANIFIESTO.read_text(encoding="utf-8", errors="replace")
    codigo = vault_norms.NORM_CATALOG[0]["code"]
    sin_seccion = re.sub(rf"^#{{2,4}}\s+{re.escape(codigo)}\b", "#### xxx",
                         original, flags=re.M)
    falso.write_text(sin_seccion + f"\n~~~~markdown\n## {codigo} — ejemplo\n~~~~\n",
                     encoding="utf-8")

    assert ENCABEZADO.search(falso.read_text(encoding="utf-8")), "el encabezado sigue ahí"
    assert codigo in vault_norms.framework_drift_check(falso)["norms_without_section"]


def test_un_id_del_marco_no_se_satisface_con_otro_mas_largo(tmp_path):
    """A-17 — `"F1" in texto` daba verde con solo `F13` escrito."""
    from vault_fundamentals_catalog import FRAMEWORK_REGISTRIES

    falso = tmp_path / "manifiesto.md"
    original = MANIFIESTO.read_text(encoding="utf-8", errors="replace")
    ident = FRAMEWORK_REGISTRIES["fundamentals"][0]["id"]
    borrado = re.sub(rf"(?<![A-Za-z0-9-]){re.escape(ident)}(?![0-9A-Za-z])", "",
                     original)
    falso.write_text(borrado + f"\nVer {ident}3 en otro sitio.\n", encoding="utf-8")

    assert ident in falso.read_text(encoding="utf-8"), "la subcadena sigue ahí"
    faltan = [m["id"] for m in vault_norms.framework_drift_check(falso)["missing"]]
    assert ident in faltan


def test_un_id_citado_solo_en_un_bloque_de_codigo_no_cuenta(tmp_path):
    """A-17 — el id que solo sale en un ejemplo de código no está documentado."""
    from vault_fundamentals_catalog import FRAMEWORK_REGISTRIES

    falso = tmp_path / "manifiesto.md"
    original = MANIFIESTO.read_text(encoding="utf-8", errors="replace")
    ident = FRAMEWORK_REGISTRIES["fundamentals"][0]["id"]
    borrado = re.sub(rf"(?<![A-Za-z0-9-]){re.escape(ident)}(?![0-9A-Za-z])", "",
                     original)
    falso.write_text(borrado + f"\n```yaml\nfundamento: {ident}\n```\n",
                     encoding="utf-8")

    faltan = [m["id"] for m in vault_norms.framework_drift_check(falso)["missing"]]
    assert ident in faltan
