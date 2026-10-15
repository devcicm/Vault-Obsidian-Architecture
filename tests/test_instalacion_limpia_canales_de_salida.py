"""La guía de instalación dice por qué canal sale cada error y con qué código.

Medido el 2026-10-15 al reinstalar la wheel 41.5 y probarla a ciegas: un
`vault run vault_read --path ../../fuera.md` sale con código 10 y stdout
vacío, porque el rechazo del pre-flight es del propio `vault` y va por stderr;
el de la tool (`missing_agent`, código 7) va por stdout. Es un contrato con
test (`tests/clean_install_gate.py` exige el JSON controlado en stderr), pero
la guía no lo decía, y quien solo lee stdout no ve nada.

Los códigos de salida no se copian a mano: el test los deriva de las
constantes `EXIT_*` de `vault.product_cli` (AP-47).
"""

import json
import re
from pathlib import Path

from vault import product_cli

GUIA = Path(__file__).resolve().parent.parent / "docs" / "INSTALACION-LIMPIA.md"


def _seccion_salida() -> str:
    texto = GUIA.read_text(encoding="utf-8")
    inicio = texto.index("## 5. Leer la salida desde otro programa")
    fin = texto.find("\n## ", inicio + 1)
    return texto[inicio:] if fin == -1 else texto[inicio:fin]


def test_la_guia_dice_que_canal_lleva_cada_error():
    seccion = _seccion_salida()
    assert "stderr" in seccion and "stdout" in seccion
    assert "PREFLIGHT_REJECTED" in seccion


def test_la_guia_lista_cada_codigo_de_salida_como_lo_define_el_codigo():
    seccion = _seccion_salida()
    codigos = {nombre: valor for nombre, valor in vars(product_cli).items()
               if nombre.startswith("EXIT_") and isinstance(valor, int)}
    assert codigos, "vault.product_cli ya no define EXIT_*"
    filas = dict(re.findall(r"^\| `(\d+)` \| `(EXIT_[A-Z_]+)` \|", seccion, re.M))
    assert {nombre: int(valor) for valor, nombre in filas.items()} == codigos


def test_un_rechazo_del_preflight_sale_por_stderr_con_stdout_vacio(capsys):
    rc = product_cli.main(["run", "vault_read", "--path", "../../fuera.md"])
    salida = capsys.readouterr()
    assert rc == product_cli.EXIT_PREFLIGHT_FAILED
    assert salida.out == ""
    error = json.loads(salida.err)
    assert error["error_code"] == "PREFLIGHT_REJECTED"
