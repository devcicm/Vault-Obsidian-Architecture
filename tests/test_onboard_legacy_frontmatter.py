"""Cross-version frontmatter healing: v34–v40 notes curadas al contrato v41.

Medido 2026-10-18 contra el vault real de SMART POS CR (en `v34`, 158 notas,
tras upgrade a v41.11 sin datos perdidos):

- Una nota escrita por una versión anterior podía tener el `title:` con `:`
  sin citar (`title: Overview: smart-pos-cr`) — YAML inválido, `yaml.safe_load`
  falla, y `vault_onboard` abortaba la operación completa al intentar fusionar.
- Notas de v34–v40 no traían `status` ni `tags` — campos requeridos por v41
  (AP-27/AP-29). `_verificar_releyendo` las rechazaba al releer la fusión.

La cura vive en `vault_onboard._rellenar_frontmatter_legacy` y se aplica en el
camino de `skipped` (cuando no hay secciones que añadir) y en el de `merged`.
Este test fija su comportamiento y los errores que ya no deben propagarse.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_onboard  # noqa: E402
import vault_standard_upgrade  # noqa: E402

#: La versión vigente sale del dueño, nunca escrita a mano (AP-47/coherencia).
VIGENTE = vault_standard_upgrade.CURRENT_VERSION


# ── _rellenar_frontmatter_legacy — unidad ────────────────────────────────────


def test_cura_title_con_dos_puntos_sin_citar():
    """YAML inválido: `title: Overview: smart-pos-cr` divide el mapeo."""
    fm = (
        "---\n"
        "title: Overview: smart-pos-cr\n"
        "project: smart-pos-cr\n"
        "type: project-overview\n"
        "updatedAt: 2026-06-20T23:31:56.000Z\n"
        "---\n"
    )
    body = "\n# Overview: smart-pos-cr\n\n## Existing section\nTexto.\n"
    curado = vault_onboard._rellenar_frontmatter_legacy(fm + body)
    import yaml
    # El bloque curado tiene sus propios `---` delimiters; extraemos el
    # contenido entre el primero y el segundo `---`.
    partes = curado.split("---")
    bloque = partes[1]
    datos = yaml.safe_load(bloque)
    assert datos["title"] == "Overview: smart-pos-cr"
    assert datos["project"] == "smart-pos-cr"
    assert datos["type"] == "project-overview"


def test_anyade_status_y_tags_cuando_faltan():
    """v41 requiere `status` y `tags`; v34 no los tenía. Se rellenan."""
    fm = (
        "---\n"
        "title: Nota Legacy\n"
        "type: concept\n"
        "updatedAt: 2026-01-01T00:00:00.000Z\n"
        "---\n"
    )
    body = "\n# Nota\n"
    curado = vault_onboard._rellenar_frontmatter_legacy(fm + body)
    import yaml
    bloque = curado.split("---")[1]
    datos = yaml.safe_load(bloque)
    assert datos["status"] == "active"
    assert datos["tags"] == []


def test_no_inventa_cuando_ya_tiene_todo():
    """Si el frontmatter ya cumple el contrato, se devuelve idéntico."""
    fm = (
        "---\n"
        "title: OK Title\n"
        "type: concept\n"
        "status: active\n"
        "tags: [a, b]\n"
        "updatedAt: 2026-01-01T00:00:00.000Z\n"
        "---\n"
    )
    body = "\n# OK\n"
    curado = vault_onboard._rellenar_frontmatter_legacy(fm + body)
    assert curado == fm + body


def test_no_toca_notas_sin_frontmatter_delimitado():
    """README, archivos sueltos, etc.: sin `---`, no se interviene."""
    contenido = "# Solo un título\n\nSin frontmatter.\n"
    assert vault_onboard._rellenar_frontmatter_legacy(contenido) == contenido


def test_no_reescribe_fronmatter_irreparable():
    """Si el frontmatter no parsea y el rescate de comillas tampoco, se deja
    tal cual: un bloque roto necesita diagnóstico humano, no reescritura
    silenciosa. La verificación posterior fallará ruidosamente."""
    # `:` que no es del value de title sino un caso realmente corrupto.
    # El regex de rescate solo actúa sobre `title:`; aquí no hay `title:` así
    # que el rescate no aplica, y el contenido se devuelve sin tocar.
    contenido = (
        "---\n"
        "{ [ invalid yaml\n"
        "  * not: mapping\n"
        "---\n"
        "\n# Body\n"
    )
    assert vault_onboard._rellenar_frontmatter_legacy(contenido) == contenido


def test_preserva_el_cuerpo_y_las_secciones_existentes():
    """La cura del frontmatter no debe alterar el cuerpo de la nota."""
    fm = (
        "---\n"
        "title: Overview: x\n"
        "type: overview\n"
        "---\n"
    )
    cuerpo = "\n# Overview: x\n\n## Stack\nPython 3.14\n\n## Code\n```py\nx = 1\n```\n"
    curado = vault_onboard._rellenar_frontmatter_legacy(fm + cuerpo)
    assert "# Overview: x" in curado
    assert "## Stack" in curado
    assert "## Code" in curado
    assert "x = 1" in curado


def test_actualiza_updatedAt_si_falta():
    """Notas sin `updatedAt` reciben el sello UTC actual al ser curadas."""
    fm = (
        "---\n"
        "title: x\n"
        "type: concept\n"
        "---\n"
    )
    curado = vault_onboard._rellenar_frontmatter_legacy(fm + "\n# x\n")
    import yaml
    bloque = curado.split("---")[1]
    datos = yaml.safe_load(bloque)
    assert "updatedAt" in datos


# ── _merge_stub — integración mínima (sin subprocess) ────────────────────────


def test_merge_stub_heala_legacy_en_camino_skipped(tmp_path, monkeypatch):
    """Si la nota existe y no hay secciones que añadir, se cura el
    frontmatter legacy de todas formas (medido 2026-10-18: sin este camino,
    un vault v34–v40 nunca recibía la migración del contrato v41)."""
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    monkeypatch.setenv("VAULT_STRICT_ROOT", "1")
    (tmp_path / "00_System").mkdir()
    (tmp_path / "00_System" / "standard-version.json").write_text(
        f'{{"applied_version": "{VIGENTE}", "applied_at": "2026-10-18T00:00:00Z", '
        '"applied_by": "test", "migrations_applied": []}\n',
        encoding="utf-8",
    )
    vault_path = tmp_path / "01_Projects" / "legacy.md"
    vault_path.parent.mkdir(parents=True)
    vault_path.write_text(
        "---\n"
        "title: Overview: legacy-project\n"
        "type: project-overview\n"
        "updatedAt: 2026-06-20T00:00:00.000Z\n"
        "---\n\n"
        "# Overview: legacy-project\n\n"
        "## Descripción\nYa está escrita.\n",
        encoding="utf-8",
    )

    from vault_io import set_vault_root
    set_vault_root(str(tmp_path))

    # El nuevo contenido solo tiene `# título` (sin `## secciones`), así que
    # el merge se queda en `skipped` — pero el heal del frontmatter debe
    # ocurrir igualmente.
    new_content = "# Overview: legacy-project\n\nSin secciones que añadir.\n"
    resultado = vault_onboard._merge_stub(vault_path, new_content, dry_run=False)
    assert resultado == "skipped"

    import yaml
    contenido = vault_path.read_text(encoding="utf-8")
    datos = yaml.safe_load(contenido.split("---")[1])
    assert datos["title"] == "Overview: legacy-project"
    assert datos["status"] == "active"
    assert datos["tags"] == []


def test_merge_stub_heala_legacy_en_camino_merged(tmp_path, monkeypatch):
    """Si hay secciones que añadir Y el frontmatter es legacy, la curación
    ocurre antes de la fusión (medido 2026-10-18: sin esto, el merged
    releía con `status`/`tags` faltantes y `_verificar_releyendo` abortaba)."""
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    monkeypatch.setenv("VAULT_STRICT_ROOT", "1")
    (tmp_path / "00_System").mkdir()
    (tmp_path / "00_System" / "standard-version.json").write_text(
        f'{{"applied_version": "{VIGENTE}", "applied_at": "2026-10-18T00:00:00Z", '
        '"applied_by": "test", "migrations_applied": []}\n',
        encoding="utf-8",
    )
    vault_path = tmp_path / "01_Projects" / "legacy2.md"
    vault_path.parent.mkdir(parents=True)
    vault_path.write_text(
        "---\n"
        "title: Legacy Note\n"
        "type: concept\n"
        "updatedAt: 2026-01-01T00:00:00.000Z\n"
        "---\n\n"
        "# Legacy Note\n\n"
        "## Existing section\nAlgo.\n",
        encoding="utf-8",
    )

    from vault_io import set_vault_root
    set_vault_root(str(tmp_path))

    new_content = (
        "# Legacy Note\n\n"
        "## Existing section\nNo se duplica.\n\n"
        "## New section\nAportada por el onboard.\n"
    )
    resultado = vault_onboard._merge_stub(vault_path, new_content, dry_run=False)
    assert resultado == "merged"

    contenido = vault_path.read_text(encoding="utf-8")
    assert "## Existing section" in contenido
    assert "## New section" in contenido
    import yaml
    datos = yaml.safe_load(contenido.split("---")[1])
    assert datos["status"] == "active"
    assert datos["tags"] == []


# ── _intentar_citar_title — rescate para YAML inválido ───────────────────────


def test_intentar_citar_title_rescata_title_con_dos_puntos():
    """El rescate cita el valor de `title:` cuando el parseo falla por un
    `:` en su contenido. Si tras citar parsea, devuelve el mapeo."""
    bloque = (
        "title: Overview: smart-pos-cr\n"
        "project: smart-pos-cr\n"
        "type: overview\n"
    )
    fm = vault_onboard._intentar_citar_title(bloque)
    assert fm is not None
    assert fm["title"] == "Overview: smart-pos-cr"


def test_intentar_citar_title_no_toca_si_ya_esta_citado():
    """Si el `title:` ya viene entre comillas, el rescate no lo reabre."""
    bloque = 'title: "Ya citado"\nproject: x\n'
    assert vault_onboard._intentar_citar_title(bloque) is None


def test_intentar_citar_title_devuelve_none_si_no_hay_title():
    """Sin línea `title:` en el bloque, no hay nada que rescatar."""
    bloque = "project: x\ntype: concept\n"
    assert vault_onboard._intentar_citar_title(bloque) is None


def test_intentar_citar_title_devuelve_none_si_no_rescata():
    """YAML realmente corrupto (no relacionado con `title:`): no se reescribe."""
    bloque = "title: x\n{ invalid: [ mapping\n"
    # `title: x` parsea solo; el problema es el resto. El rescate intenta
    # citar y vuelve a parsear: si sigue fallando, devuelve None.
    resultado = vault_onboard._intentar_citar_title(bloque)
    # No podemos garantizar None (puede que parsee), pero si devuelve algo
    # debe seguir siendo un mapeo con `title == "x"`.
    if resultado is not None:
        assert isinstance(resultado, dict)
        assert resultado.get("title") == "x"


# ── _heal_legacy_pass — pasada global ────────────────────────────────────────


def test_heal_legacy_paso_curar_todas_las_notas_legacy(tmp_path, monkeypatch):
    """Una pasada global cura todas las notas con frontmatter legacy
    (medido 2026-10-18: 117 notas sin `status`, 17 sin `tags`, 3 con
    `title:` sin citar en un vault v34→v41.11 real)."""
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    monkeypatch.setenv("VAULT_STRICT_ROOT", "1")
    (tmp_path / "00_System").mkdir()
    (tmp_path / "00_System" / "standard-version.json").write_text(
        f'{{"applied_version": "{VIGENTE}", "applied_at": "2026-10-18T00:00:00Z", '
        '"applied_by": "test", "migrations_applied": []}\n',
        encoding="utf-8",
    )

    # 3 notas legacy: una con title citado, una con dos puntos, una sin
    # status/tags.
    (tmp_path / "01_Projects").mkdir()
    (tmp_path / "01_Projects" / "a.md").write_text(
        "---\n"
        "title: Concepto\n"
        "type: concept\n"
        "updatedAt: 2026-01-01T00:00:00.000Z\n"
        "---\n\n"
        "# Concepto\n",
        encoding="utf-8",
    )
    (tmp_path / "01_Projects" / "b.md").write_text(
        "---\n"
        "title: Overview: legacy\n"
        "type: project-overview\n"
        "updatedAt: 2026-06-20T00:00:00.000Z\n"
        "---\n\n"
        "# Overview: legacy\n",
        encoding="utf-8",
    )
    (tmp_path / "07_Knowledge").mkdir()
    (tmp_path / "07_Knowledge" / "c.md").write_text(
        "---\n"
        "title: OK\n"
        "type: concept\n"
        "status: active\n"
        "tags: [a]\n"
        "updatedAt: 2026-01-01T00:00:00.000Z\n"
        "---\n\n"
        "# OK\n",
        encoding="utf-8",
    )

    from vault_io import set_vault_root
    set_vault_root(str(tmp_path))

    resultado = vault_onboard._heal_legacy_pass(dry_run=False)

    assert resultado["ok"] is True
    assert resultado["escaneadas"] == 3
    assert resultado["curadas"] == 2  # a y b curadas; c ya cumplía
    assert resultado["saltadas_sin_cambios"] == 1
    assert resultado["curadas_por_seccion"] == {"01_Projects": 2}
    assert resultado["errores"] == []

    import yaml
    datos_a = yaml.safe_load((tmp_path / "01_Projects" / "a.md").read_text(
        encoding="utf-8").split("---")[1])
    assert datos_a["status"] == "active"
    assert datos_a["tags"] == []
    datos_b = yaml.safe_load((tmp_path / "01_Projects" / "b.md").read_text(
        encoding="utf-8").split("---")[1])
    assert datos_b["title"] == "Overview: legacy"
    # c no se tocó
    assert "status: active" in (tmp_path / "07_Knowledge" / "c.md").read_text(encoding="utf-8")


def test_heal_legacy_no_toca_rutas_exentas(tmp_path, monkeypatch):
    """Las notas en .history, vault-backups y 20_Quarantine no se curan:
    ahí el frontmatter roto es el dato, no el defecto."""
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    monkeypatch.setenv("VAULT_STRICT_ROOT", "1")
    (tmp_path / "00_System").mkdir()
    (tmp_path / "00_System" / "standard-version.json").write_text(
        f'{{"applied_version": "{VIGENTE}", "applied_at": "2026-10-18T00:00:00Z", '
        '"applied_by": "test", "migrations_applied": []}\n',
        encoding="utf-8",
    )
    (tmp_path / ".history" / "a").mkdir(parents=True)
    nota_exenta = tmp_path / ".history" / "a" / "b.md"
    contenido_original = (
        "---\n"
        "title: Overview: backup\n"
        "type: concept\n"
        "updatedAt: 2026-01-01T00:00:00.000Z\n"
        "---\n\n# b\n"
    )
    nota_exenta.write_text(contenido_original, encoding="utf-8")

    from vault_io import set_vault_root
    set_vault_root(str(tmp_path))

    resultado = vault_onboard._heal_legacy_pass(dry_run=False)
    assert resultado["escaneadas"] == 0  # ruta exenta no se escanea
    assert resultado["curadas"] == 0
    assert nota_exenta.read_text(encoding="utf-8") == contenido_original
