"""`vault_test_runner` prueba el código del repo, en su vault temporal, y termina.

Medido el 2026-10-04 con `--contracts --errors`:

- `TOOL_TIMEOUT` a los 60 s: el runner lanza decenas de subprocesos y heredaba
  el límite por defecto de `wrap_main`, así que nunca llegaba a informar.
- 6 de 45 contratos en rojo: `vault_write` sin `--tags` (AP-26) no creaba la
  nota y read, search, append, diff y validate fallaban en cascada.
- Los scripts copiados al vault temporal importaban `vault.kernel` de la
  instalación del usuario, no del repo (AP-44); y un `VAULT_ROOT` heredado
  —el que fija el servidor MCP— ganaba a la autodetección, de modo que los
  contratos habrían escrito en el vault real (AP-36).
- El caso AP-20 de `--errors` medía `content_too_short`, no AP-20.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_test_runner as tr  # noqa: E402


def test_el_entorno_fija_el_vault_temporal_y_el_codigo_del_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path / "vault-real"))
    env = tr._entorno(tmp_path / "temporal")
    assert env["VAULT_ROOT"] == str(tmp_path / "temporal")
    assert env["PYTHONPATH"].split(os.pathsep)[0] == str(ROOT)


def test_los_contratos_de_escritura_pasan_sin_tocar_el_vault_heredado(tmp_path, monkeypatch):
    real = tmp_path / "vault-real"
    (real / "01_Projects").mkdir(parents=True)
    monkeypatch.setenv("VAULT_ROOT", str(real))
    nombres = {"vault_write", "vault_read", "vault_append"}
    monkeypatch.setattr(tr, "TOOL_CONTRACTS",
                        [c for c in tr.TOOL_CONTRACTS if c["name"] in nombres])

    temporal = tmp_path / "temporal"
    temporal.mkdir()
    r = tr._run_contracts_in_vault(temporal)
    assert r["ok"], r["errors"]
    assert r["passed"] == len(nombres)
    assert (temporal / "01_Projects" / "smoke" / "smoktest.md").is_file()
    assert not list(real.rglob("*.md")), "los contratos escribieron en el vault heredado"


def test_los_casos_de_error_miden_su_norma(tmp_path):
    r = tr._run_errors_in_vault(tmp_path)
    assert r["ok"], r["errors"]
    assert r["passed"] == len(tr.ERROR_CASES)
