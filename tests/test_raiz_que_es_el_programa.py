"""AP-36 — una raíz adivinada que es el propio toolkit no se audita como vault.

Medido como consumidor el 2026-10-15 con la wheel 41.6 instalada: `vault run
vault_audit` sin `VAULT_ROOT`, lanzado desde dentro de un runtime recién creado
con `vault init`, auditó `site-packages/vault_toolkit` —`byFolder: {"normas":
80}`—, devolvió `ok: true` con healthIndex 85 y sugirió `vault_fix_brackets
--apply` sobre los ficheros del paquete. `vault_write` en la misma situación ya
se negaba (RaizNoIdentificada). Leer con una raíz dudosa sigue permitido; lo que
no es una raíz dudosa sino una equivocada es el paquete Python del programa: el
detector ya sabe que un paquete no es un vault, y aquí se le pregunta a él.

El rechazo vive en `vault_errors.wrap_main`, junto al de `VAULT_ROOT`
inexistente: es el punto por el que pasan todas las tools antes de tocar nada.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

SONDA = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[2])
import vault_raiz
vault_raiz.VAULT_ROOT = Path(sys.argv[1])
vault_raiz._VAULT_ROOT_ORIGIN = "repo_root_fallback"
import vault_errors
llamada = []
sys.argv = ["vault_audit", *sys.argv[3:]]
rc = vault_errors.wrap_main(lambda: llamada.append(1) or 0, "vault_audit")
print(json.dumps({"rc": rc, "ejecutada": bool(llamada)}))
"""


def _sondear(raiz: Path, *argv: str, cwd: Path, permisivo: bool = False,
             cwd_cliente: Optional[Path] = None) -> Tuple[dict, str]:
    env = {k: v for k, v in os.environ.items()
           if k not in ("VAULT_ROOT", "VAULT_STRICT_ROOT", "VAULT_PERMISSIVE_ROOT",
                        "VAULT_CLIENT_CWD")}
    if cwd_cliente is not None:
        env["VAULT_CLIENT_CWD"] = str(cwd_cliente)
    env["PYTHONIOENCODING"] = "utf-8"
    env["VAULT_AGENT"] = "pytest"
    if permisivo:
        env["VAULT_PERMISSIVE_ROOT"] = "1"
    p = subprocess.run([sys.executable, "-c", SONDA, str(raiz), str(SCRIPTS), *argv],
                       env=env, cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    lineas = [l for l in p.stdout.strip().splitlines() if l.startswith("{")]
    assert lineas, p.stderr[-2000:]
    return json.loads(lineas[-1]), "\n".join(lineas[:-1])


def _paquete(tmp_path: Path) -> Path:
    paquete = tmp_path / "site-packages" / "vault_toolkit"
    paquete.mkdir(parents=True)
    (paquete / "__init__.py").write_text("", encoding="utf-8")
    return paquete


def test_ap36_la_raiz_que_es_el_paquete_no_se_ejecuta(tmp_path):
    paquete = _paquete(tmp_path)
    salida, envelope = _sondear(paquete, cwd=tmp_path)
    assert salida == {"rc": 1, "ejecutada": False}, (salida, envelope)
    error = json.loads(envelope)
    assert error["error_code"] == "VAULT_NOT_FOUND"
    assert "VAULT_ROOT" in error["recovery"]["hint"]
    # Rechazar no es escribir: el paquete queda como estaba.
    assert sorted(p.name for p in paquete.rglob("*")) == ["__init__.py"]


def test_desde_un_runtime_la_pista_lo_nombra(tmp_path):
    paquete = _paquete(tmp_path)
    runtime = tmp_path / "runtime"
    (runtime / "00_System").mkdir(parents=True)
    (runtime / "00_System" / "standard-version.json").write_text("{}", encoding="utf-8")
    _, envelope = _sondear(paquete, cwd=runtime)
    error = json.loads(envelope)
    assert error["cwd_is_runtime"] is True
    assert "VAULT_ROOT=." in error["recovery"]["hint"]


def test_por_mcp_la_pista_mira_el_cwd_del_cliente(tmp_path):
    """El runner MCP lanza la tool con cwd=scripts/ y publica el del usuario en
    `VAULT_CLIENT_CWD`; el dueño de ese criterio es `client_cwd`. Mirar el CWD
    del proceso le negaba la pista a quien sí estaba dentro de un runtime."""
    paquete = _paquete(tmp_path)
    runtime = tmp_path / "runtime"
    (runtime / "00_System").mkdir(parents=True)
    (runtime / "00_System" / "standard-version.json").write_text("{}", encoding="utf-8")
    hijo = tmp_path / "scripts"
    hijo.mkdir()
    _, envelope = _sondear(paquete, cwd=hijo, cwd_cliente=runtime)
    assert json.loads(envelope)["cwd_is_runtime"] is True


def test_help_y_root_explicito_siguen_ejecutandose(tmp_path):
    paquete = _paquete(tmp_path)
    for argv in (("--help",), ("-h",), ("--root", str(tmp_path)), (f"--root={tmp_path}",)):
        salida, _ = _sondear(paquete, *argv, cwd=tmp_path)
        assert salida == {"rc": 0, "ejecutada": True}, argv


def test_la_bandera_permisiva_conserva_lo_anterior(tmp_path):
    # No-derogación: VAULT_PERMISSIVE_ROOT=1 restaura el comportamiento previo.
    salida, _ = _sondear(_paquete(tmp_path), cwd=tmp_path, permisivo=True)
    assert salida == {"rc": 0, "ejecutada": True}


def test_un_checkout_sin_vault_no_cambia(tmp_path):
    # La raíz de un repo consumidor sin vault no es un paquete: sigue siendo
    # una raíz dudosa, que se lee y no se escribe, como antes.
    repo = tmp_path / "repo"
    repo.mkdir()
    salida, _ = _sondear(repo, cwd=tmp_path)
    assert salida == {"rc": 0, "ejecutada": True}
