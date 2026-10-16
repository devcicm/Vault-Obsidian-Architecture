"""Los `required_args` de `tool-spec.json` son flags que la CLI acepta.

Medido el 2026-10-16 al retirar `returns_match` de `vault_spec_validate`: de
los chequeos que quedaban, `args_match` destapó que `vault_qa_save` publicaba
`--qa_type`, que es el `dest` de argparse, no el flag (`--type`). Quien leyera
el contrato para invocarla recibía `INVALID_ARGS` (`allow_abbrev=False`), y
el contrato callaba `--description`, que la CLI exige.

Se mide contra el argparse del dueño (`fuente_de`, AP-44). No se exige que la
lista sea idéntica a los `required=True`: seis tools exigen un flag en código
(`vault_foreign_check --root`) o por exclusión mutua, y el extractor no lo ve.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

import vault_grafo_import  # noqa: E402
import vault_manifest  # noqa: E402
import vault_spec_validate  # noqa: E402

SPEC = ROOT / "vault-sandbox" / "00_System" / "tool-spec.json"


def _tools():
    return json.loads(SPEC.read_text(encoding="utf-8"))["tools"]


def test_todo_flag_publicado_existe_en_la_cli():
    medidas, culpables = 0, []
    for nombre, entrada in sorted(_tools().items()):
        fuente = vault_grafo_import.fuente_de(nombre)
        if entrada.get("status") != "active" or not fuente.exists():
            continue
        medidas += 1
        aceptados = vault_spec_validate._extract_argparse_flags(
            fuente.read_text(encoding="utf-8"))
        falsos = [a for a in entrada["required_args"] if a not in aceptados]
        if falsos:
            culpables.append((nombre, falsos))
    assert medidas > 100, medidas  # un universo vacío no sale verde (AP-60)
    assert culpables == [], culpables


def test_qa_save_publica_los_flags_que_su_cli_exige():
    entrada = _tools()["vault_qa_save"]
    fuente = vault_grafo_import.fuente_de("vault_qa_save").read_text(encoding="utf-8")
    assert sorted(entrada["required_args"]) == sorted(
        vault_manifest._extract_required_flags(fuente))
