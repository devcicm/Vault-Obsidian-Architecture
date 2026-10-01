"""F1 — `vault_ingest --commit` no pisa una nota que otro escritor está creando.

Medido en v40.34: la tool comprobaba `full.exists()` y después escribía con
`atomic_write_text`, sin lock entre las dos. `vault_write` escribe bajo el lock
de la nota; una ingesta concurrente que no lo tomaba podía pisar, entre su
comprobación y su escritura, la nota que `vault_write` acababa de crear — con
material sin revisar sustituyendo al revisado y `ok: true`.
"""

import json
import sys
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

PARRAFO = ("Un parrafo con contenido de sobra para superar el minimo de caracteres "
           "exigido por la segmentacion de esta tool. ")
TEXTO = "\n\n".join(["# Unica", PARRAFO * 2])
NOTA = "07_Knowledge/unica.md"


@pytest.fixture
def ingest(tmp_path, monkeypatch):
    import vault_io
    import vault_ingest

    anterior = vault_io.get_vault_root()
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    vault_io.set_vault_root(tmp_path)
    monkeypatch.setattr(vault_ingest, "update_section_index", lambda section: None)
    yield vault_ingest, tmp_path
    vault_io.set_vault_root(anterior)


def _ingerir(vault_ingest):
    return vault_ingest.vault_ingest(text=TEXTO, section="07_Knowledge", source="prueba",
                                     origin="inline", commit=True, agent="test")


def test_la_ruta_propuesta_es_la_del_test(ingest):
    vault_ingest, _ = ingest
    r = vault_ingest.vault_ingest(text=TEXTO, section="07_Knowledge", source="prueba",
                                  origin="inline", commit=False, agent="test")
    assert [p["path"] for p in r["proposed"]] == [NOTA], r["proposed"]


def test_con_la_nota_tomada_por_otro_escritor_no_escribe_y_lo_dice(ingest, monkeypatch):
    vault_ingest, raiz = ingest
    monkeypatch.setattr(vault_ingest, "_LOCK_TIMEOUT", 0.3, raising=False)
    destino = raiz / NOTA
    ocupado = destino.parent / ".locks" / f"{destino.name}.lock"
    ocupado.mkdir(parents=True)
    (ocupado / "owner.json").write_text(
        json.dumps({"pid": 0, "createdAt": time.time(), "token": "otro"}), encoding="utf-8")

    r = _ingerir(vault_ingest)

    assert not destino.exists(), "se escribió saltándose el lock de otro escritor"
    assert r["ok"] is False and r["written"] == [], r
    assert r["failed"] and "NOTE_LOCKED" in r["failed"][0]["reason"], r


def test_una_nota_creada_mientras_esperaba_el_lock_no_se_pisa(ingest, monkeypatch):
    vault_ingest, raiz = ingest
    destino = raiz / NOTA
    real = vault_ingest.tomar_lock

    def otro_escritor_llego_antes(target, timeout):
        # Lo que deja `vault_write` al soltar su lock: la nota ya existe.
        Path(target).write_text("---\ntitle: revisada\n---\nrevisada\n", encoding="utf-8")
        return real(target, timeout)

    monkeypatch.setattr(vault_ingest, "tomar_lock", otro_escritor_llego_antes)

    r = _ingerir(vault_ingest)

    assert destino.read_text(encoding="utf-8").endswith("revisada\n")
    assert r["written"] == [] and r["skipped"] == [{"path": NOTA, "reason": "ya existe"}], r


def test_sin_competencia_escribe(ingest):
    vault_ingest, raiz = ingest
    r = _ingerir(vault_ingest)
    assert r["ok"] and r["written"] == [NOTA], r
    assert (raiz / NOTA).exists()
