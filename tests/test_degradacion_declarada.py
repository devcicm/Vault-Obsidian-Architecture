"""Lo que la tool no pudo leer sale en el envelope, no se olvida (AP-37).

`vault_audit` tenía nueve `except Exception: continue` sobre la lectura de una
nota, y `vault_onboard` once sobre la lectura del proyecto. Saltarse el fichero
es lo correcto —ninguna de las dos puede caerse porque algo esté bloqueado—, pero
hacerlo en silencio invierte el resultado:

- cada nota ilegible es una nota que no aporta hallazgos, así que el
  `healthScore` **sube** cuanto menos se consigue leer del vault;
- cada fichero de proyecto ilegible se escribe en el vault como «el proyecto no
  tiene eso», que es una ausencia afirmada sin haberla comprobado.

Lo que estos tests fijan no es que se lea siempre —no se puede—, es que **el
alcance de la medida sea parte del resultado**.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import vault_audit  # noqa: E402
import vault_onboard  # noqa: E402


# ── vault_audit ───────────────────────────────────────────────────────────────

def test_una_nota_ilegible_queda_registrada(tmp_path, monkeypatch):
    vault_audit._reset_degradacion()
    nota = tmp_path / "rota.md"
    nota.write_text("x", encoding="utf-8")

    def _explota(*a, **k):
        raise PermissionError("bloqueada por otro proceso")

    monkeypatch.setattr(Path, "read_text", _explota)
    assert vault_audit._leer_nota(nota) is None

    deg = vault_audit.degradaciones()
    assert len(deg) == 1
    assert "PermissionError" in deg[0]["error"]
    assert "rota.md" in deg[0]["path"]


def test_una_nota_legible_no_ensucia_el_registro(tmp_path):
    vault_audit._reset_degradacion()
    nota = tmp_path / "sana.md"
    nota.write_text("contenido\n", encoding="utf-8")
    assert vault_audit._leer_nota(nota) == "contenido\n"
    assert vault_audit.degradaciones() == []


def test_el_modo_binario_tambien_registra(tmp_path, monkeypatch):
    """El detector de duplicados lee bytes; su fallo cuenta igual."""
    vault_audit._reset_degradacion()
    nota = tmp_path / "b.md"
    nota.write_text("x", encoding="utf-8")
    monkeypatch.setattr(
        Path, "read_bytes", lambda *a, **k: (_ for _ in ()).throw(OSError("io"))
    )
    assert vault_audit._leer_nota(nota, binario=True) is None
    assert vault_audit.degradaciones()


def test_el_registro_es_por_auditoria_no_por_proceso(tmp_path, monkeypatch):
    """Dos audits en el mismo intérprete no acumulan el uno sobre el otro."""
    nota = tmp_path / "r.md"
    nota.write_text("x", encoding="utf-8")
    monkeypatch.setattr(
        Path, "read_text", lambda *a, **k: (_ for _ in ()).throw(OSError("io"))
    )
    vault_audit._reset_degradacion()
    vault_audit._leer_nota(nota)
    vault_audit._reset_degradacion()
    vault_audit._leer_nota(nota)
    assert len(vault_audit.degradaciones()) == 1


def test_ninguna_lectura_de_nota_se_quedo_fuera():
    """El guard: una lectura nueva con `except Exception` vuelve al silencio.

    Se cuenta sobre el fuente porque el defecto no es de comportamiento —cada
    sitio por separado funciona— sino de que alguien añada el sitio número diez
    sin enterarse de que existe el registro.
    """
    fuente = (
        Path(__file__).resolve().parent.parent / "scripts" / "vault_audit.py"
    ).read_text(encoding="utf-8")
    cuerpo = fuente.split("def _leer_nota", 1)[1].split("def _aliases_de", 1)[1]
    for linea in cuerpo.splitlines():
        limpia = linea.strip()
        if not limpia.startswith(("content = ", "text = ", "raw = ")):
            continue
        if ".read_text(" not in limpia and ".read_bytes(" not in limpia:
            continue
        sujeto = limpia.split("=", 1)[1].strip().split(".", 1)[0]
        # Los artefactos derivados (`ENRICHED_FILE`, `QUALITY_INDEX`…) son
        # constantes en mayúsculas y no son notas: que falten es un hallazgo
        # aparte, con su propio camino, no un hueco en la cobertura del audit.
        if sujeto.isupper():
            continue
        assert "_leer_nota" in limpia, (
            f"lectura de nota sin registrar la degradación: {limpia}"
        )


# ── vault_onboard ─────────────────────────────────────────────────────────────

def test_un_paso_de_deteccion_fallido_se_anota():
    vault_onboard._DETECCION_DEGRADADA.clear()
    vault_onboard._registrar_degradacion("leer_readme", UnicodeDecodeError(
        "utf-8", b"\xff", 0, 1, "invalid start byte"
    ))
    deg = vault_onboard._DETECCION_DEGRADADA
    assert deg[0]["step"] == "leer_readme"
    assert "UnicodeDecodeError" in deg[0]["error"]


def test_el_envelope_declara_el_campo(tmp_path):
    """`degraded` acompaña siempre, vacío incluido: su ausencia sería ambigua."""
    vault_onboard._DETECCION_DEGRADADA.clear()
    res = vault_onboard.vault_onboard(
        project="demo", path=str(tmp_path), dry_run=True, no_git=True
    )
    assert "degraded" in res
    assert isinstance(res["degraded"], list)


def test_los_pasos_anotados_tienen_nombre_util():
    """`step` nombra qué se intentaba, no dónde: un número de línea no dirige nada."""
    fuente = (
        Path(__file__).resolve().parent.parent / "scripts" / "vault_onboard.py"
    ).read_text(encoding="utf-8")
    nombres = [
        l.split('_registrar_degradacion("', 1)[1].split('"', 1)[0]
        for l in fuente.splitlines()
        if '_registrar_degradacion("' in l
    ]
    assert len(nombres) >= 11
    assert all("_" in n and n.islower() for n in nombres), nombres
