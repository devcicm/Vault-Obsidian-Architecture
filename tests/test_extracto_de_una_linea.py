"""Un cuerpo de una sola línea larga no se entrega como extracto vacío.

`_truncate_to_tokens` recorta por párrafos y, si ninguno cabe, por líneas.
Si la única línea tampoco cabe, devolvía `"\n…"`: la nota se incluía en el
paquete, gastaba presupuesto de cabecera y no aportaba una palabra. Pasa con
notas exportadas sin saltos de línea —un HTML aplanado, un volcado de chat—.
El último escalón recorta por palabras.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_context_pack as vcp  # noqa: E402


def test_una_linea_larga_da_un_extracto_con_palabras():
    texto = " ".join(f"palabra{i}" for i in range(400))
    extracto, recortado = vcp._truncate_to_tokens(texto, 100)
    assert recortado
    assert extracto.startswith("palabra0 palabra1"), extracto[:40]
    assert vcp.estimate_tokens(extracto) <= 100 + 2


def test_lo_que_cabe_no_se_toca():
    assert vcp._truncate_to_tokens("corto", 100) == ("corto", False)
