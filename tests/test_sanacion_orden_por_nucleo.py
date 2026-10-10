"""La fase 8 de la sanación ordena por núcleo (deuda #11).

`vault_audit` publica `vaultCore`: las notas por encima del escalón de fan-in.
De lo que esa medida habilitaba, la prioridad en `vault_context_pack` se midió
y bajó el recall, y el peso en el `healthIndex` lo descartó el usuario. Queda
el orden de la sanación: los enlaces rotos de una nota que medio vault cita se
reparan antes que los de una nota que no cita nadie, porque es por ahí por
donde se lee el vault.

La fase solo ordena la evidencia que ya tenía: no decide qué enlace es una
nota ausente y qué un símbolo de código —eso sigue siendo
`decision_not_automatable`— ni escribe nada.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _ruta in (ROOT / "scripts", ROOT):
    if str(_ruta) not in sys.path:
        sys.path.insert(0, str(_ruta))

import vault_sanacion  # noqa: E402


def _nota(ruta: Path, cuerpo: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(f"---\ntitle: {ruta.stem}\ntype: note\n---\n# {ruta.stem}\n\n{cuerpo}\n",
                    encoding="utf-8")


def _vault_con_hub(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    k = vault / "07_Knowledge"
    # Un hub citado por todas las hojas, con un enlace roto.
    _nota(k / "hub.md", "Ver [[no-existe-desde-el-hub]].")
    # Cada hoja cita al hub y a la siguiente: fan-in {12, 1}. `escalon` ignora
    # los ceros, así que sin la cadena no habría corte y tampoco núcleo.
    for i in range(12):
        _nota(k / f"hoja-{i:02d}.md", f"Parte de [[hub]]; sigue en [[hoja-{(i + 1) % 12:02d}]].")
    # Una hoja con más enlaces rotos que el hub: sin el núcleo saldría primera.
    _nota(k / "suelta.md", "[[rota-1]] [[rota-2]] [[rota-3]]")
    return vault


def test_la_fase_8_repara_primero_las_notas_del_nucleo(tmp_path):
    vault = _vault_con_hub(tmp_path)
    plan = vault_sanacion.plan_de_sanacion(vault)
    fase = next(f for f in plan["phases"] if f["phase"] == 8)
    assert fase["verdict"] == "applies"
    orden = fase["order"]
    assert [e["path"] for e in orden] == ["07_Knowledge/hub.md", "07_Knowledge/suelta.md"]
    assert orden[0]["core"] is True and orden[0]["brokenLinks"] == 1
    assert orden[1]["core"] is False and orden[1]["brokenLinks"] == 3
    # El criterio se publica con el orden: quien lo lee sabe por qué va así.
    assert "vaultCore" in fase["order_criterion"]


def test_sin_nucleo_el_orden_es_por_enlaces_rotos_y_lo_dice(tmp_path):
    """Sin escalón no hay núcleo, y no se fabrica uno: el orden cae al recuento."""
    vault = tmp_path / "vault"
    k = vault / "07_Knowledge"
    _nota(k / "a.md", "[[rota-a]]")
    _nota(k / "b.md", "[[rota-b1]] [[rota-b2]]")
    plan = vault_sanacion.plan_de_sanacion(vault)
    fase = next(f for f in plan["phases"] if f["phase"] == 8)
    assert [e["path"] for e in fase["order"]] == ["07_Knowledge/b.md", "07_Knowledge/a.md"]
    assert not any(e["core"] for e in fase["order"])


def test_el_plan_sigue_siendo_de_solo_lectura(tmp_path):
    vault = _vault_con_hub(tmp_path)
    antes = {p: p.read_bytes() for p in vault.rglob("*") if p.is_file()}
    vault_sanacion.plan_de_sanacion(vault)
    despues = {p: p.read_bytes() for p in vault.rglob("*") if p.is_file()}
    assert antes == despues
