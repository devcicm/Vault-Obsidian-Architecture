"""AP-16: la prevención publicada dice lo que `vault_write` hace de verdad.

Medido el 2026-10-15 en la instalación ciega (R7, wheel limpia en un venv
nuevo): la primera escritura de un consumidor sin `VAULT_AGENT` sale con
`missing_agent`, y el `vault_says` de ese mismo rechazo le cuenta que
«vault_write agrega agent: automáticamente». Tres fuentes, tres versiones: el
registro prometía el relleno automático, el manifiesto que `vault_write` omite
el campo «(no bloquea)», y el código bloquea. Manda el código —es lo que ejerce
el consumidor—, y este test ata la prosa a él.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _seccion_ap16() -> str:
    texto = (ROOT / "vault-obsidian-architecture.md").read_text(encoding="utf-8")
    inicio = texto.index("### AP-16 —")
    return texto[inicio:texto.index("\n### ", inicio + 1)]


def test_vault_write_sin_agente_bloquea_con_missing_agent(tmp_path):
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    (raiz / "07_Knowledge").mkdir()
    env = {k: v for k, v in os.environ.items() if k != "VAULT_AGENT"}
    env.update(VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1", PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPTS / "vault_write.py"),
                        "--folder", "07_Knowledge", "--title", "Sin agente", "--tags", "ap16",
                        "--content", "Primera línea de la nota sin agente declarado.\n\n"
                        "Segunda línea con contexto real para el mínimo.\n\nTercera línea."],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    salida = json.loads(p.stdout)
    assert salida["ok"] is False and salida["error_code"] == "missing_agent"
    assert not list((raiz / "07_Knowledge").glob("*.md"))


def test_el_registro_no_promete_un_relleno_que_no_existe():
    import vault_norms_catalog

    prevencion = vault_norms_catalog.norma_por_codigo("AP-16")["prevention"]
    assert "automáticamente" not in prevencion
    for pista in ("missing_agent", "--agent", "VAULT_AGENT"):
        assert pista in prevencion, pista


def test_el_manifiesto_no_dice_que_no_bloquea():
    seccion = _seccion_ap16()
    assert "no bloquea" not in seccion
    assert "missing_agent" in seccion and "VAULT_AGENT" in seccion
