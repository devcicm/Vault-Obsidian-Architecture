"""La documentación del estándar embarcada en un vault no son enlaces rotos.

Un vault consumidor lleva dentro el manifiesto, la referencia de tools y los
documentos SDD. Todos citan **sintaxis** de wikilink —`[[wiki-link]]`, `[[]]`,
`[[nota]]`, `[[stem|título]]`— que no apunta a ninguna nota porque no pretende
apuntar a ninguna. Contarlos como rotos es medir el manual y llamarlo vault.

Ya se excluía, pero por igualdad de nombre exacto con
`vault-obsidian-architecture.md`. Esa igualdad se rompe sola, y se rompió: el
contraste contra un vault ajeno al estándar (regla 7) midió **45** enlaces
rotos falsos en `vault-obsidian-architecture.v27.backup.md` y **30** en
`docs/sdd/04-antipatterns.md`. Setenta y cinco de 624 en un solo vault, con
`broken_links` saturando a los diez: el vault entero quedaba juzgado por su
propia documentación.

Lo llamativo es de quién era la culpa. Los consumidores archivan el manifiesto
con sufijo de versión, que es exactamente lo que la política de no-derogación
les pide. Quien tenía que ceder era el criterio de medida, no ellos — AP-44 en
su forma más limpia: la tool medía con su propio supuesto (el fichero se llama
así) en vez de con el del consumidor (esto es documentación).

El sandbox lo exhibía también: al corregirlo, su `healthIndex` subió de 60 a
64 sin que cambiase una sola nota.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_audit as va  # noqa: E402

# Casos tomados de vaults reales. Las rutas son relativas al vault, así que no
# atan la suite a ninguna máquina.
ES_DOCUMENTACION = [
    "vault-obsidian-architecture.md",
    "00_System/vault-obsidian-architecture.md",
    "vault-obsidian-architecture.v27.backup.md",
    "scripts.bak-20260619-131332/vault-obsidian-architecture.md",
    "docs/sdd/04-antipatterns.md",
    "scripts/README.md",
]

ES_NOTA = [
    "11_Code/ans/index.md",
    "10_Migrated/legacy/INDEX.md",
    "03_Decisions/2026-05-03-adr-001.md",
    "09_Infrastructure/servers/proxmox-50.md",
    # Una nota puede *hablar* del manifiesto sin serlo.
    "02_Observability/errors/informe-sobre-vault-obsidian-architecture.md",
]


@pytest.mark.parametrize("ruta", ES_DOCUMENTACION)
def test_la_documentacion_del_estandar_no_se_mide_como_vault(ruta):
    assert va.es_documentacion_del_estandar(ruta) is True


@pytest.mark.parametrize("ruta", ES_NOTA)
def test_una_nota_del_vault_si_se_mide(ruta):
    assert va.es_documentacion_del_estandar(ruta) is False, (
        "excluir de más es peor que el defecto original: esconde enlaces "
        "rotos de verdad y el vault puntúa bien por no mirarse"
    )


def test_el_sufijo_de_version_no_burla_la_exclusion():
    """El defecto exacto: la igualdad por nombre no sobrevive a un archivado.

    Archivar con sufijo es lo que la no-derogación pide a los consumidores.
    Si esto vuelve a fallar, el criterio ha vuelto a compararse con `==`.
    """
    for sufijo in (".v27.backup.md", ".v39.md", "-2026-08-07.md", ".old.md"):
        ruta = f"00_System/vault-obsidian-architecture{sufijo}"
        assert va.es_documentacion_del_estandar(ruta), ruta


def test_la_barra_invertida_de_windows_no_cambia_el_criterio():
    assert va.es_documentacion_del_estandar(r"docs\sdd\04-antipatterns.md")


def test_el_criterio_esta_declarado_como_registro():
    """Tres condiciones sueltas en un bucle no las puede leer un guard."""
    assert va.DOCUMENTACION_DEL_ESTANDAR
    for clave, motivo in va.DOCUMENTACION_DEL_ESTANDAR.items():
        assert motivo.strip(), f"{clave} sin motivo declarado"


def test_el_detector_de_enlaces_rotos_usa_el_registro():
    """Si alguien reintroduce el `==` dentro del bucle, esto lo ve."""
    import inspect

    fuente = inspect.getsource(va._detect_broken_links)
    assert "es_documentacion_del_estandar" in fuente
    assert 'n.name == "vault-obsidian-architecture.md"' not in fuente
