"""AP-57 — toda baseline de deuda se escribe por `vault_baseline.escribir`.

Siete `--freeze` reescribían su JSON a mano: `vault_noop_audit`,
`vault_blueprint`, `vault_norms_coherence` (dos), `vault_smoke`, `vault_arch` y
`vault_firma_sitio` (blame y error-contract). Cada copia conservaba como mucho
una clave ajena y escribía con el fin de línea de la plataforma, así que el
`objetivo` que la capa 7 del plano pide asignar se habría borrado en el
siguiente `--freeze`, y en Windows el fichero salía entero en CRLF. Medido el
2026-10-05 al revisar db37a5c, que arregló el CRLF en una sola de las copias.
"""

import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_arch  # noqa: E402
import vault_blueprint  # noqa: E402
import vault_firma_sitio  # noqa: E402
import vault_noop_audit  # noqa: E402
import vault_norms_coherence  # noqa: E402
import vault_smoke  # noqa: E402

OBJETIVO = {"tamano": 0, "fecha_limite": "2027-01-01", "cadencia_dias": 30,
            "dueno": "prueba"}

_SCAN_VACIO = {"new_untraceable": [], "untraceable_claims": [],
               "new_norms_without_distinction": [], "norms_without_distinction": []}

import vault_grafo_import as gi  # noqa: E402


def _previa(path: Path, clave: str) -> None:
    path.write_bytes(json.dumps({clave: [], "objetivo": OBJETIVO}).encode("utf-8"))


def _noop(mp, p):
    mp.setattr(vault_noop_audit, "BASELINE_PATH", p)
    mp.setattr(vault_noop_audit, "offenders", lambda: [])
    return "tools", vault_noop_audit.freeze


def _blueprint(mp, p):
    mp.setattr(vault_blueprint, "BASELINE", p)
    mp.setattr(vault_blueprint, "_sin_cobertura", lambda: set())
    return "uncovered_norms", vault_blueprint.freeze


def _coherencia(mp, p):
    mp.setattr(vault_norms_coherence, "BASELINE", p)
    mp.setattr(vault_norms_coherence, "scan", lambda: dict(_SCAN_VACIO))
    return "claims", vault_norms_coherence.freeze


def _distincion(mp, p):
    mp.setattr(vault_norms_coherence, "BASELINE_DISTINCION", p)
    mp.setattr(vault_norms_coherence, "scan", lambda: dict(_SCAN_VACIO))
    return "normas", vault_norms_coherence.freeze_distincion


def _smoke(mp, p):
    mp.setattr(vault_smoke, "BASELINE_PATH", p)
    mp.setattr(vault_smoke, "REPO_ROOT", p.parent)
    mp.setattr(vault_smoke, "smoke", lambda: {"failures": [], "new_offenders": []})
    return "failing", vault_smoke.freeze


def _arch(mp, p):
    mp.setattr(vault_arch, "BASELINE_PATH", p)
    for f in ("cruces", "cruces_fuera_de_puerto", "vinculos_congelados", "rutas_duplicadas"):
        mp.setattr(vault_arch, f, lambda: [])
    return "crossings", vault_arch.freeze


def _firma(mp, p):
    def congelar():
        _, _, previos = vault_firma_sitio.cargar_baseline(p)
        vault_firma_sitio.escribir_baseline(p, "AP-51", "prueba", [], previos)
        return {"ok": True}
    return "sites", congelar


ESCRITORES = {"noop": _noop, "blueprint": _blueprint, "coherencia": _coherencia,
              "distincion": _distincion, "smoke": _smoke, "arch": _arch, "firma": _firma}


@pytest.mark.parametrize("nombre", sorted(ESCRITORES))
def test_el_freeze_conserva_objetivo_y_escribe_en_lf(nombre, tmp_path, monkeypatch):
    base = tmp_path / f"{nombre}-baseline.json"
    clave, congelar = ESCRITORES[nombre](monkeypatch, base)
    _previa(base, clave)
    r = congelar()
    assert r.get("ok") is True, r
    crudo = base.read_bytes()
    assert b"\r\n" not in crudo
    datos = json.loads(crudo)
    assert datos.get("objetivo") == OBJETIVO, sorted(datos)
    assert datos[clave] == []


def test_ningun_modulo_escribe_una_baseline_por_su_cuenta():
    """Una escritura sobre un nombre `*BASELINE*` fuera del dueño es una copia.

    `field-compat-baseline.json` (`FIELDS_BASELINE`) queda fuera a propósito:
    no es deuda que solo encoge sino un contrato que crece, con su propia
    procedencia (`generated`), y ya escribe en LF.
    """
    copias = []
    for py in sorted(SCRIPTS.glob("*.py")):
        if py.name == "vault_baseline.py":
            continue
        for n in ast.walk(ast.parse(gi.codigo_de(py).read_text(encoding="utf-8"))):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr in ("write_text", "write_bytes")
                    and isinstance(n.func.value, ast.Name)
                    and "BASELINE" in n.func.value.id
                    and n.func.value.id != "FIELDS_BASELINE"):
                copias.append(f"{py.name}:{n.lineno}")
    assert copias == []
