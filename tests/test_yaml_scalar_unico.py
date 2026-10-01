"""Un solo `yaml_scalar` (D1, AP-57).

Había dos cuerpos idénticos: `scripts/vault_lib.py` y
`vault/autoria/frontmatter.py`. Idénticos hoy no es idénticos mañana — es como
empezó la divergencia de tres criterios de escapado que `vault.autoria.frontmatter`
existe para cerrar. El dueño es `vault.kernel.frontmatter_parsing`: el escape
se decide con el mismo parser que lee el frontmatter, y en el núcleo ni
`vault_lib` (kernel) cruza hacia Autoría ni Autoría reescribe nada.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_criterios  # noqa: E402
import vault_lib  # noqa: E402
from vault.autoria import frontmatter as autoria  # noqa: E402
from vault.kernel import frontmatter_parsing as kernel  # noqa: E402


def test_hay_un_solo_yaml_scalar():
    assert vault_lib.yaml_scalar is kernel.yaml_scalar
    assert autoria.yaml_scalar is kernel.yaml_scalar


def test_el_escape_no_cambia_ni_un_byte():
    casos = {
        "Guía de diseño": "Guía de diseño",
        "Overview: demo": '"Overview: demo"',
        "#tag": '"#tag"',
        "": '""',
        "true": '"true"',
        True: "true",
        None: "null",
        3: "3",
    }
    for valor, esperado in casos.items():
        assert kernel.yaml_scalar(valor) == esperado, valor
    assert kernel.yaml_scalar(["api", "demo"]) == '["api", "demo"]'


def test_ap57_una_segunda_definicion_se_detecta(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "vault_copia.py").write_text(
        "def yaml_scalar(v):\n    return str(v)\n", encoding="utf-8")
    dueño = tmp_path / "vault" / "kernel"
    dueño.mkdir(parents=True)
    (dueño / "frontmatter_parsing.py").write_text(
        "def yaml_scalar(v):\n    return str(v)\n", encoding="utf-8")
    h = vault_criterios.medir_definiciones(tmp_path)
    assert [x["modulo"] for x in h] == ["scripts/vault_copia.py"]
    assert h[0]["dueño"] == "vault/kernel/frontmatter_parsing.py:yaml_scalar"


def test_ap57_reexportar_no_es_una_copia(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "vault_lib.py").write_text(
        "from vault.kernel.frontmatter_parsing import yaml_scalar\n", encoding="utf-8")
    assert vault_criterios.medir_definiciones(tmp_path) == []


def test_hoy_no_hay_segundas_definiciones():
    assert vault_criterios.medir_definiciones() == []
