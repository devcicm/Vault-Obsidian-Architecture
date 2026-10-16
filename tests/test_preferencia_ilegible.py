"""Una preferencia ilegible no se lleva por delante a las demás, y se avisa.

Auditoría del 2026-10-15 (AP-51). `_load_preference` dejaba escapar el
`FrontmatterParseError` de un YAML roto, `vault_preferences_list` caía entera y
`vault_context_pack._must_preferences` lo capturaba con `except Exception` y
devolvía `[]`: **todas** las preferencias `must` salían del paquete, que seguía
diciendo `ok: true` sin un solo aviso. Y una preferencia que no se podía leer
(`OSError`) se descartaba como si no fuera una preferencia.

Ahora la ilegible se nombra en `unreadable` y las legibles siguen; el paquete
lo dice en `warnings`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

BUENA = (
    "---\ntitle: Respuestas en español\ntype: preference\ncategory: idioma\n"
    "strength: must\nstatement: Responder siempre en español\nstatus: active\n---\n\n"
    "# Respuestas en español\n"
)
ROTA = "---\ntitle: [sin cerrar\ntype: preference\nstrength: must\n---\n\n# Rota\n"


def _ejecutar(raiz: Path, script: str, *argv: str) -> dict:
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *argv],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS), timeout=120,
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


def _vault(tmp_path: Path) -> Path:
    raiz = tmp_path / "vault"
    for d in ("00_System", "07_Knowledge", "99_Index"):
        (raiz / d).mkdir(parents=True)
    prefs = raiz / "17_Preferences" / "idioma"
    prefs.mkdir(parents=True)
    (prefs / "espanol.md").write_text(BUENA, encoding="utf-8")
    (prefs / "rota.md").write_text(ROTA, encoding="utf-8")
    (raiz / "07_Knowledge" / "nota.md").write_text(
        "---\ntitle: Arquitectura\n---\n\n# Arquitectura\n\nLa capa de arquitectura.\n",
        encoding="utf-8")
    return raiz


def test_la_lista_nombra_la_ilegible_y_conserva_las_demas(tmp_path):
    raiz = _vault(tmp_path)
    r = _ejecutar(raiz, "vault_preferences.py", "--list")
    assert r["ok"] is True, r
    assert [p["path"] for p in r["preferences"]] == ["17_Preferences/idioma/espanol.md"]
    assert [u["path"] for u in r["unreadable"]] == ["17_Preferences/idioma/rota.md"]


def test_el_paquete_conserva_las_must_legibles_y_lo_avisa(tmp_path):
    raiz = _vault(tmp_path)
    r = _ejecutar(raiz, "vault_context_pack.py", "--query", "arquitectura")
    assert r["ok"] is True, r
    assert r["preferences_included"] == 1, r
    assert any("rota.md" in w for w in r["warnings"]), r["warnings"]
