"""AP-57 — el pre-flight anti-poison y el saneador deciden la unión ortográfica igual.

Medido como consumidor el 2026-10-10: `vault_ingest` con una frase en persa
(«می» + ZWNJ + «خواهم») se rechazaba con POISON-INVISIBLE de severidad `high`,
y `vault run` hacía lo mismo, aunque m223 ya enseñó al saneador que ese ZWNJ es
ortografía. Dos módulos decidiendo si un U+200C/U+200D une una palabra es el
criterio repetido que AP-57 nombra: el dueño es `vault.kernel.normalizacion`.

Un ZWJ entre letras latinas sigue siendo un invisible que el revisor no ve.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from vault.consulta import safety  # noqa: E402
from vault.kernel import normalizacion  # noqa: E402

ZWNJ, ZWJ = "\u200c", "\u200d"


def _invisibles(texto):
    return [f for f in safety.scan_content(texto) if f.code == "POISON-INVISIBLE"]


@pytest.mark.parametrize("texto", [
    f"Una frase en persa: می{ZWNJ}خواهم sobre la replicación.",
    f"Hindi: क्{ZWJ}ष en una nota de glosario.",
    f"Equipo: 👩{ZWJ}💻 de guardia.",
])
def test_una_union_ortografica_no_es_poison(texto):
    assert _invisibles(texto) == []


@pytest.mark.parametrize("texto", [f"pass{ZWJ}word", f"hola {ZWNJ}mundo", "a​b"])
def test_un_invisible_que_no_une_sigue_bloqueando(texto):
    hallazgos = _invisibles(texto)
    assert hallazgos and hallazgos[0].severity == "high"


def test_el_criterio_tiene_un_solo_dueno():
    import vault_encoding
    assert vault_encoding.es_union_ortografica is normalizacion.es_union_ortografica
    assert vault_encoding.UNIONES_ORTOGRAFICAS is normalizacion.UNIONES_ORTOGRAFICAS
