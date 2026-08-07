"""AP-42 en la documentación: un comando publicado que no corre.

`CLAUDE.md` publicaba, en su sección de comandos habituales, las dos formas de
medir la salud del vault:

    python scripts/vault_audit.py --root vault-sandbox
    python scripts/vault_quality_check.py --root vault-sandbox --min-score 0.7

Ninguna de las dos tools acepta `--root`. Un agente que copiaba el comando
—que es exactamente para lo que está esa sección— recibía
`error: unrecognized arguments: --root vault-sandbox` y perdía el turno. Y lo
contradecía la regla 1 del mismo fichero, tres pantallas más arriba: solo
cuatro tools aceptan `--root`, y el destino se fuerza con `VAULT_ROOT`.

Duró versiones porque nada lo comprobaba: el manifiesto, el catálogo y los
conteos tienen guard; los comandos de la documentación, no. Que el invisible
fuese justo el de la salud es lo que lo hace caro — nadie mide el vault a mano
para descubrir que la herramienta de medirlo no arranca.

La comprobación es estática (los `add_argument` declarados) y no ejecuta nada:
varios comandos documentados escriben en el vault.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_doc_sync as vds  # noqa: E402

TOOLS_DE_SALUD = ("vault_audit.py", "vault_quality_check.py")


def test_ningun_comando_publicado_usa_un_flag_que_su_tool_rechaza():
    problemas = vds.comandos_publicados()
    assert problemas == [], "\n".join(p["detail"] for p in problemas)


def test_el_detector_esta_conectado_al_check():
    """Un detector que existe y no se llama es el mismo fallo con otra cara."""
    assert "commands_checked" in vds.scan()


def test_el_detector_ve_el_defecto_original():
    """Si se reintrodujese `--root` en un comando de salud, tiene que salir."""
    declarados = vds._flags_declarados(REPO_ROOT / "scripts" / "vault_audit.py")
    assert "--root" not in declarados, (
        "si vault_audit pasara a aceptar --root, este test sobra; "
        "revisa la regla 1 de CLAUDE.md antes de borrarlo"
    )


@pytest.mark.parametrize("script", TOOLS_DE_SALUD)
def test_la_tool_de_salud_arranca_tal_y_como_se_documenta(script):
    """Contra el flag, no contra el parser: se ejecuta de verdad.

    El guard es estático; este test es el contraste. Un `add_argument` que el
    regex vea pero que argparse no acepte pasaría el guard y moriría aquí.
    """
    linea = _comando_documentado(script)
    proc = subprocess.run(
        [sys.executable, *linea], capture_output=True, text=True,
        encoding="utf-8", errors="replace", cwd=str(REPO_ROOT), timeout=300,
    )
    assert "unrecognized arguments" not in (proc.stderr or ""), proc.stderr
    assert proc.returncode == 0, proc.stderr[-500:]


def _comando_documentado(script: str) -> list:
    """Extrae de CLAUDE.md el comando que se publica para esa tool.

    No se copia aquí: se lee del documento. Copiarlo dejaría el test verde
    mientras la documentación se rompe, que es el defecto que este fichero
    cierra, cometido una segunda vez.
    """
    texto = (REPO_ROOT / "CLAUDE.md").read_bytes().decode("utf-8")
    for linea in texto.splitlines():
        for m in vds.RE_COMANDO.finditer(linea):
            if m.group(1).endswith(script):
                return [str(REPO_ROOT / m.group(1)), *m.group(2).split()]
    pytest.fail(f"CLAUDE.md ya no documenta ningún comando para {script}")


def test_el_audit_publica_la_lectura_que_discrimina():
    """El comando de salud tiene que devolver la lectura nueva, no solo el score.

    `healthScore` satura a 0 en el propio sandbox; si el comando documentado
    solo trajese ese número, seguiría sin medir aunque arrancase.
    """
    import json

    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "vault_audit.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO_ROOT), timeout=300,
    )
    env = json.loads(proc.stdout)
    assert "healthIndex" in env and "healthProfile" in env
    assert set(env["healthProfile"]) == set(
        __import__("vault_audit").FAMILIAS_DE_SALUD
    )
    # El desglose no puede salir vacío mientras el score no sea 100: sería
    # AP-37, un campo que se publica y nunca se llena.
    if env["healthScore"] < 100:
        assert env["penalties"], "healthScore penalizado pero penalties vacío"
        assert sum(p["penalty"] for p in env["penalties"]) == 100 - env["healthScore"] \
            or env["healthScore"] == 0
