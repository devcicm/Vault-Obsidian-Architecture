"""Los consumidores de secciones ven las propias que el vault declara (CN-02).

`vault_registry.secciones_del_vault(raiz)` suma a las del estándar las que el
vault declara en `00_System/secciones.json`. Declararlas no sirve de nada si los
que recorren el vault siguen leyendo `ORDERED_SECTIONS` a pelo: la nota de una
sección propia seguiría fuera de los índices, del contrato y del audit. Aquí se
prueba cada consumidor por donde el consumidor la ve.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import vault_registry as reg  # noqa: E402
from vault.indices.enumeracion import notas_en_disco  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.kernel.fallos import FalloDeDominio  # noqa: E402


def _vault(raiz: Path, secciones=None, notas=()) -> Path:
    for seccion in ("00_System", "07_Knowledge", "99_Index"):
        (raiz / seccion).mkdir(parents=True, exist_ok=True)
    if secciones is not None:
        (raiz / reg.SECCIONES_PROPIAS_RUTA).write_text(
            json.dumps({"schema": 1, "secciones": secciones}), encoding="utf-8")
    for rel in notas:
        p = raiz / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"---\ntitle: {p.stem}\n---\n# {p.stem}\n", encoding="utf-8")
    return raiz


_SCRIPTS_SEC = {"folder": "22_Scripts", "documentacion": "referencia"}


def test_el_puerto_de_secciones_incluye_las_propias(tmp_path):
    ctx = construir(_vault(tmp_path, [_SCRIPTS_SEC]))
    assert "22_Scripts" in ctx.secciones.ordenadas()
    assert ctx.secciones.existe("22_Scripts")
    assert ctx.secciones.ruta_de("22_Scripts") == ctx.raiz / "22_Scripts"


def test_sin_secciones_propias_el_puerto_es_el_registro(tmp_path):
    ctx = construir(_vault(tmp_path))
    assert list(ctx.secciones.ordenadas()) == list(reg.ORDERED_SECTIONS)


def test_una_seccion_no_declarada_sigue_sin_existir(tmp_path):
    ctx = construir(_vault(tmp_path, [_SCRIPTS_SEC]))
    assert not ctx.secciones.existe("scripts")
    with pytest.raises(ValueError):
        ctx.secciones.ruta_de("scripts")


def test_la_enumeracion_de_notas_ve_la_seccion_propia(tmp_path):
    raiz = _vault(tmp_path, [_SCRIPTS_SEC],
                  notas=["22_Scripts/deploy.md", "07_Knowledge/a.md", "scripts/b.md"])
    ctx = construir(raiz)
    rel = {p.relative_to(raiz).as_posix() for p in notas_en_disco(raiz, ctx.secciones.ordenadas())}
    assert "22_Scripts/deploy.md" in rel and "07_Knowledge/a.md" in rel
    assert "scripts/b.md" not in rel


def test_un_registro_roto_es_un_fallo_del_dominio_no_un_vacio(tmp_path):
    """AP-51: leerlo como «no hay propias» sacaría sus notas de los índices en silencio."""
    raiz = _vault(tmp_path)
    (raiz / reg.SECCIONES_PROPIAS_RUTA).write_text("{roto", encoding="utf-8")
    with pytest.raises(FalloDeDominio) as e:
        construir(raiz).secciones.ordenadas()
    assert e.value.causa == "INDICE_ILEGIBLE"
