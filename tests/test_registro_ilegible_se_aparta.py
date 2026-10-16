"""Un registro que no se lee se aparta, no se pisa.

Medido en la auditoría del 2026-10-15: el log diario de `vault_graph_fix
--fix`, la traza de tools (`.tool-trace.json`) y el contador de tokens leían un
JSON corrupto como `[]` y lo reescribían con la entrada nueva. Lo que había
—qué arreglos se aplicaron y cuándo, qué tools fallaron— desaparecía sin aviso,
que es AP-51 en el sitio que existe para dejar constancia.

Los tres son registros de efecto lateral: ninguno debe tumbar la operación que
anota —el arreglo ya está aplicado; la tool ya respondió—. Por eso no se aborta
como la bitácora F8: el fichero ilegible se **aparta** junto al original
(`<nombre>.ilegible-<utc>`) para repararlo a mano y el registro sigue desde
cero. No se pierde un byte, y quien lo apartó lo dice.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from vault.kernel.escritura import apartar_ilegible  # noqa: E402

ROTO = '[{"tool": "x", "ok": tr'


def _apartados(path: Path) -> list:
    return sorted(p for p in path.parent.iterdir() if p.name.startswith(path.name + ".ilegible-"))


def test_apartar_conserva_el_contenido_y_libera_el_nombre(tmp_path):
    log = tmp_path / "log.json"
    log.write_text(ROTO, encoding="utf-8")
    destino = apartar_ilegible(log)
    assert not log.exists()
    assert destino.read_text(encoding="utf-8") == ROTO
    assert _apartados(log) == [destino]


def test_dos_apartados_seguidos_no_se_pisan(tmp_path):
    log = tmp_path / "log.json"
    log.write_text("uno", encoding="utf-8")
    a = apartar_ilegible(log)
    log.write_text("dos", encoding="utf-8")
    b = apartar_ilegible(log)
    assert a != b
    assert {a.read_text(encoding="utf-8"), b.read_text(encoding="utf-8")} == {"uno", "dos"}


def test_la_traza_corrupta_se_aparta(tmp_path, monkeypatch):
    from vault.kernel import errors_trace

    monkeypatch.setattr(errors_trace, "trace_file", lambda: tmp_path / "00_System" / ".tool-trace.json")
    tf = errors_trace.trace_file()
    tf.parent.mkdir(parents=True)
    tf.write_text(ROTO, encoding="utf-8")
    errors_trace._append_trace_entry([{"tool": "nueva"}], use_atomic=True)
    assert json.loads(tf.read_text(encoding="utf-8")) == [{"tool": "nueva"}]
    assert [p.read_text(encoding="utf-8") for p in _apartados(tf)] == [ROTO]


def test_el_contador_de_tokens_corrupto_se_aparta(tmp_path, monkeypatch):
    from vault.kernel import errors_trace

    tkf = tmp_path / "00_System" / ".tool-tokens.json"
    monkeypatch.setattr(errors_trace, "tokens_file", lambda: tkf)
    tkf.parent.mkdir(parents=True)
    tkf.write_text(ROTO, encoding="utf-8")
    errors_trace.log_token_usage("vault_x", "entrada", "salida")
    assert [e["tool"] for e in json.loads(tkf.read_text(encoding="utf-8"))] == ["vault_x"]
    assert [p.read_text(encoding="utf-8") for p in _apartados(tkf)] == [ROTO]


def test_el_log_de_graph_fix_corrupto_se_aparta(tmp_path):
    from vault.grafo import graph_fix

    raiz = tmp_path / "vault"
    raiz.mkdir()
    informe = {"fixes": [], "summary": {"total": 0}}
    primero = graph_fix.apply_fix(informe, raiz)
    log = raiz / primero["log_file"]
    log.write_text(ROTO, encoding="utf-8")
    segundo = graph_fix.apply_fix(informe, raiz)
    assert len(json.loads(log.read_text(encoding="utf-8"))) == 1
    apartados = _apartados(log)
    assert [p.read_text(encoding="utf-8") for p in apartados] == [ROTO]
    assert segundo["log_apartado"] == str(apartados[0].relative_to(raiz)).replace("\\", "/")


@pytest.mark.parametrize("roto", [ROTO, "[1, 2]"])
def test_la_cola_de_propagacion_corrupta_se_aparta(tmp_path, roto):
    """`vault_propagate` leía la cola ilegible como vacía y la pisaba al encolar.

    Auditoría del 2026-10-15: `_read_propagation_queue` devolvía
    `{"pending": []}` ante un JSON roto —o válido pero sin forma de cola— y
    `_action_queue` escribía encima la única entrada nueva. Las pendientes que
    había se perdían sin rastro.
    """
    import vault_io
    import vault_propagate as vp

    raiz = tmp_path / "vault"
    for d in ("00_System", "07_Knowledge", "99_Index"):
        (raiz / d).mkdir(parents=True)
    vault_io.set_vault_root(raiz)
    cola = vp._propagation_queue()
    cola.parent.mkdir(parents=True, exist_ok=True)
    cola.write_text(roto, encoding="utf-8")

    vp._action_queue("07_Knowledge/n.md", ["07_Knowledge/m.md"], 1, "low")

    assert [p["path"] for p in json.loads(cola.read_text(encoding="utf-8"))["pending"]] == [
        "07_Knowledge/n.md"]
    assert [p.read_text(encoding="utf-8") for p in _apartados(cola)] == [roto]
