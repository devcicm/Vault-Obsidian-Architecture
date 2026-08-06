"""Una sola verdad para "cuál es el vault" en runtime.

Síntoma medido: `set_vault_root()` cambiaba `get_vault_root()` y no cambiaba
nada de lo que las tools usan de verdad.

    get_vault_root()   : C:\\tmp\\otro-vault
    vault_audit.VAULT_ROOT : ...\\vault-sandbox   <-- el que lee y escribe

Causa: 89 de 98 módulos hacen `from vault_io import VAULT_ROOT` y derivan sus
rutas EN EL IMPORT (`CODE_DIR = VAULT_ROOT / "11_Code"`), congelando un `Path`
literal. La API pública de cambiar el vault mentía, y `CLAUDE.md` ya declaraba
`get_vault_root()` como fuente única: el código no cumplía su propia tabla.

No basta con un proxy perezoso sobre `VAULT_ROOT`: no alcanzaría a las
constantes ya derivadas de él. Por eso `set_vault_root()` reancla.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import vault_io  # noqa: E402


@pytest.fixture
def raiz_restaurada():
    """set_vault_root() es estado de proceso: hay que devolverlo o contamina."""
    original = vault_io.get_vault_root()
    yield
    vault_io.set_vault_root(original)


def test_cambiar_el_vault_alcanza_a_los_modulos(tmp_path, raiz_restaurada):
    import vault_audit
    import vault_code_map

    nuevo = tmp_path / "otro-vault"
    vault_io.set_vault_root(nuevo)

    assert vault_io.get_vault_root() == nuevo.resolve()
    assert vault_audit.VAULT_ROOT == nuevo.resolve(), (
        "el auditor sigue mirando el vault anterior"
    )
    assert vault_code_map.CODE_DIR == nuevo.resolve() / "11_Code", (
        "las constantes derivadas quedaron ancladas al vault anterior"
    )


def test_el_reanclaje_es_auditable(tmp_path, raiz_restaurada):
    """Una operación que reescribe estado de módulos no puede ser invisible."""
    import vault_audit  # noqa: F401

    vault_io.set_vault_root(tmp_path / "otro")
    tocadas = vault_io.rebound_constants()
    assert tocadas, "no declaró qué reancló"
    assert any(n.endswith(".VAULT_ROOT") for n in tocadas)


def test_volver_a_la_raiz_original_deja_todo_como_estaba(tmp_path):
    import vault_audit

    original = vault_io.get_vault_root()
    antes = vault_audit.VAULT_ROOT
    vault_io.set_vault_root(tmp_path / "temporal")
    vault_io.set_vault_root(original)
    assert vault_audit.VAULT_ROOT == antes


def test_no_toca_rutas_que_no_cuelgan_del_vault(tmp_path, raiz_restaurada):
    """`SCRIPTS_DIR` y compañía apuntan al repo, no al vault: se dejan."""
    import vault_fundamentals

    antes = vault_fundamentals.SCRIPTS_DIR
    vault_io.set_vault_root(tmp_path / "otro")
    assert vault_fundamentals.SCRIPTS_DIR == antes


def test_la_mayoria_de_modulos_derivan_del_import():
    """El dato que motivó el arreglo, fijado para que no se degrade en silencio.

    No es un objetivo mantenerlo alto: es un recordatorio de por qué
    `set_vault_root()` tiene que reanclar. Si algún día la cifra baja a 0
    porque todos usan `get_vault_root()`, este test sobra y se borra.
    """
    import re

    patron = re.compile(r"^from vault_io import [^\n]*\bVAULT_ROOT\b", re.MULTILINE)
    congelan = [
        py.name for py in SCRIPTS.glob("vault_*.py")
        if patron.search(py.read_text(encoding="utf-8"))
    ]
    assert len(congelan) > 50, (
        "si esto baja, revisa si set_vault_root() sigue necesitando reanclar"
    )


def test_el_write_path_rechaza_el_traversal(tmp_path, raiz_restaurada):
    """AP-36 comprobado por el propio write path, no por memoria del llamante."""
    vault_io.set_vault_root(tmp_path / "vault")
    fuera = tmp_path / "vault" / "07_Knowledge" / ".." / ".." / ".." / "robada.md"
    with pytest.raises(ValueError, match="fuera del vault"):
        vault_io.atomic_write_text(fuera, "contenido")
    assert not (tmp_path.parent / "robada.md").exists()


def test_una_ruta_normal_dentro_del_vault_pasa(tmp_path, raiz_restaurada):
    vault_io.set_vault_root(tmp_path / "vault")
    destino = tmp_path / "vault" / "07_Knowledge" / "nota.md"
    vault_io.atomic_write_text(destino, "---\ntype: knowledge\n---\n\nCuerpo.\n")
    assert destino.exists()


def test_el_cwd_del_cliente_ancla_las_rutas_de_entrada(tmp_path, monkeypatch):
    """El CWD del proceso no es el del usuario cuando arranca por MCP."""
    monkeypatch.setenv("VAULT_CLIENT_CWD", str(tmp_path))
    assert vault_io.resolve_input_path("src/foo.ts") == tmp_path / "src" / "foo.ts"
    absoluta = tmp_path / "x" / "y.ts"
    assert vault_io.resolve_input_path(absoluta) == absoluta


def test_sin_la_variable_el_cwd_del_proceso_sigue_valiendo(monkeypatch):
    """CLI directa: ahí el CWD del proceso SÍ es el del usuario."""
    monkeypatch.delenv("VAULT_CLIENT_CWD", raising=False)
    assert vault_io.client_cwd() == Path.cwd()


def test_un_cwd_de_cliente_inexistente_no_rompe(monkeypatch, tmp_path):
    monkeypatch.setenv("VAULT_CLIENT_CWD", str(tmp_path / "no-existe"))
    assert vault_io.client_cwd() == Path.cwd()
