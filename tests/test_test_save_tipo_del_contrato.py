"""vault_test_save: la nota que escribe cumple el contrato (AP-27).

La tool escribia `test_type` y ningun `type`: sus notas salian del contrato
incumplido, y el audit lo media como `missing_type` (medido en un vault real
el 2026-10-21, al documentar con esta tool los scripts de prueba que el
agente habia ejecutado). `type` es el canonico de la seccion (`test`), y
`test_type` es la granularidad fina.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import vault_io  # noqa: E402


def _vault(tmp_path, monkeypatch):
    raiz = tmp_path / "v"
    for sec in ("00_System", "15_Tests", "99_Index"):
        (raiz / sec).mkdir(parents=True)
    vault_io.set_vault_root(raiz)
    monkeypatch.setenv("VAULT_ROOT", str(raiz))
    return raiz


def test_la_nota_de_prueba_declara_el_tipo_del_contrato(tmp_path, monkeypatch):
    import vault_test_save

    _vault(tmp_path, monkeypatch)
    env = vault_test_save.vault_test_save(
        project="mi-api",
        title="Login correcto",
        test_type="unit",
        description="Verifica el login con credenciales validas",
        preconditions="Existe un usuario",
        steps=None,
        expected_result="Token valido",
        related_requirement=None,
        related_code="src/auth.py",
        status="pass",
        tags=None,
    )
    assert env.get("ok"), env
    escrito = env.get("path") or env.get("note")
    assert escrito, env
    ruta = Path(tmp_path / "v" / escrito) if not Path(escrito).is_absolute() else Path(escrito)
    texto = ruta.read_text(encoding="utf-8")
    assert "type: test" in texto, texto[:400]
    assert "test_type: unit" in texto, texto[:400]


def test_el_tipo_es_el_canonico_de_la_seccion():
    """No se escribe a mano lo que el registro ya declara (AP-57)."""
    import vault_registry

    assert "test" in vault_registry.SECTION_TYPES["15_Tests"]
