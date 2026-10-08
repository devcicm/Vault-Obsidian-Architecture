"""El nombre de una versión en `.history/` se lee como se escribe.

`vault_undo._guardar_version_actual` escribe `{carpeta}__{stem}-{ts}.md` y, si
dos versiones caen en el mismo segundo, `{carpeta}__{stem}-{ts}-{n}.md`. El
lector, `vault_history_compact._parse_history_filename`, solo conocía la
primera forma: la segunda salía sin fecha y con el sufijo pegado al stem, así
que `vault_history_compact` la agrupaba como si fuera de otra nota y nunca la
compactaba. Lo encontró la máquina del tiempo de arquitectura, que necesita la
fecha de cada versión y no puede fiarse del mtime —una copia del vault lo
reescribe entero—.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from vault_history_compact import _parse_history_filename  # noqa: E402

TS = datetime(2026, 5, 9, 1, 53, 23, tzinfo=timezone.utc)


def test_la_forma_simple():
    m = _parse_history_filename("01_Projects__ans__architecture-2026-05-09T01-53-23.md")
    assert m["stem"] == "01_Projects__ans__architecture"
    assert m["timestamp"] == TS


def test_dos_versiones_en_el_mismo_segundo_son_de_la_misma_nota():
    m = _parse_history_filename("01_Projects__ans__architecture-2026-05-09T01-53-23-1.md")
    assert m["stem"] == "01_Projects__ans__architecture"
    assert m["timestamp"] == TS
    assert m["secuencia"] == 1
    assert _parse_history_filename(
        "01_Projects__ans__architecture-2026-05-09T01-53-23.md")["secuencia"] == 0


def test_un_stem_que_acaba_en_numero_no_se_confunde_con_el_sufijo():
    m = _parse_history_filename("07_Knowledge__plan-2-2026-05-09T01-53-23.md")
    assert m["stem"] == "07_Knowledge__plan-2"
    assert m["secuencia"] == 0
