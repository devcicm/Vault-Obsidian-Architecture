"""Una sola verdad para "cuál es el vault" en runtime.

Síntoma medido: `set_vault_root()` cambiaba `get_vault_root()` y no cambiaba
nada de lo que las tools usan de verdad.

    get_vault_root()   : C:\\tmp\\otro-vault
    vault_change_log.VAULT_ROOT : ...\\vault-sandbox   <-- el que lee y escribe

Causa: 89 de 98 módulos hacen `from vault_io import VAULT_ROOT` y derivan sus
rutas EN EL IMPORT (`SYSTEM_DIR = VAULT_ROOT / "00_System"`), congelando un `Path`
literal. La API pública de cambiar el vault mentía, y `AGENTS.md` ya declaraba
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
    """Ya no hace falta ejemplo: no queda un solo módulo que congele la raíz.

    Este test se escribió con `vault_audit`, luego con `vault_change_log`, y en
    ambos casos comprobaba el **paliativo** —que `set_vault_root()` reescribiera
    a posteriori una constante ya derivada—. Al migrar Autoría, el último de los
    82 vínculos congelados desapareció y con él el último módulo que podía
    servir de ejemplo: cualquier `X.SYSTEM_DIR` que se escribiera aquí sería un
    `AttributeError`.

    Así que lo que se comprueba ahora es lo contrario y es más fuerte: la raíz
    llega a los módulos porque **la resuelven al usarla**, no porque alguien se
    la reescriba. `vinculos_congelados() == []` es la condición que lo garantiza
    para todo el repo, no para el módulo que este test eligiera.
    """
    import vault_arch
    import vault_change_log

    nuevo = tmp_path / "otro-vault"
    vault_io.set_vault_root(nuevo)

    assert vault_io.get_vault_root() == nuevo.resolve()
    assert vault_arch.vinculos_congelados() == [], (
        "un módulo volvió a derivar su ruta en el import: el paliativo vuelve a "
        "ser necesario y esta garantía deja de valer"
    )
    assert vault_change_log._log_json().is_relative_to(nuevo.resolve()), (
        "el módulo sigue mirando el vault anterior"
    )


def test_el_reanclaje_es_auditable(tmp_path, raiz_restaurada):
    """Una operación que reescribe estado de módulos no puede ser invisible."""
    import vault_change_log  # noqa: F401

    vault_io.set_vault_root(tmp_path / "otro")
    tocadas = vault_io.rebound_constants()
    assert tocadas, "no declaró qué reancló"
    assert any(n.endswith(".VAULT_ROOT") for n in tocadas)


def test_volver_a_la_raiz_original_deja_todo_como_estaba(tmp_path):
    """Ir y volver no deja residuo — ni en el proceso ni en lo que ve un módulo.

    El paliativo se conserva (no-derogación) aunque hoy no le quede un solo
    consumidor: `set_vault_root()` sigue reanclando el nombre `VAULT_ROOT` que
    los módulos importaron. Lo que este test fija es que la ida y la vuelta sean
    simétricas, medido por lo que de verdad usa una tool: la ruta que resuelve.
    """
    import vault_change_log

    original = vault_io.get_vault_root()
    antes = vault_change_log._log_json()
    vault_io.set_vault_root(tmp_path / "temporal")
    assert vault_change_log._log_json() != antes, (
        "el módulo no se enteró del cambio: la inyección sería decorativa"
    )
    vault_io.set_vault_root(original)
    assert vault_change_log._log_json() == antes


def test_no_toca_rutas_que_no_cuelgan_del_vault(tmp_path, raiz_restaurada):
    """`SCRIPTS_DIR` y compañía apuntan al repo, no al vault: se dejan."""
    import vault_fundamentals

    antes = vault_fundamentals.SCRIPTS_DIR
    vault_io.set_vault_root(tmp_path / "otro")
    assert vault_fundamentals.SCRIPTS_DIR == antes


def test_ningun_modulo_importa_ya_el_nombre_vault_root():
    """Era `test_la_mayoria_de_modulos_derivan_del_import`, y la cifra llegó a 0.

    Ese test fijaba «89 de 98 módulos importan `VAULT_ROOT`» como recordatorio
    de por qué `set_vault_root()` tiene que reanclar, y su propio enunciado
    decía qué hacer si algún día bajaba a cero. Bajó. No se borra: se le da la
    vuelta, que es más fuerte —de recordatorio de una deuda pasa a puerta que
    impide reabrirla— y no deroga nada.

    El punto que costó ver: al terminar de migrar los ocho contextos,
    `vault_arch.vinculos_congelados()` medía 0 y veinte módulos seguían
    importando el nombre y usándolo dentro de funciones. El guard solo miraba
    asignaciones de nivel de módulo, así que los daba por limpios mientras
    seguían dependiendo del paliativo.

    El caso legítimo se pide con alias: `VAULT_ROOT as _DETECTED_ROOT` en
    `vault_norms` quiere la raíz detectada, no la efectiva.
    """
    import re

    patron = re.compile(
        r"^from vault_io import (?!.*VAULT_ROOT as ).*VAULT_ROOT",
        re.MULTILINE,
    )
    congelan = [
        py.name for py in SCRIPTS.glob("vault_*.py")
        if patron.search(py.read_text(encoding="utf-8"))
    ]
    assert congelan == [], (
        f"vuelven a arrastrar el nombre en vez de resolver tarde: {congelan}"
    )


def test_el_paliativo_se_conserva_aunque_no_le_quede_consumidor():
    """No-derogación: el reanclaje se queda, y se documenta que ya no hace falta.

    Lo único que `set_vault_root()` reancla hoy es `vault_io.VAULT_ROOT`, es
    decir a sí mismo. Retirarlo sería derogar una API pública para ahorrar una
    línea; dejarlo sin decir que sobra sería peor, porque el siguiente que lo
    lea creerá que hay módulos dependiendo de él.
    """
    import vault_arch

    assert hasattr(vault_io, "rebound_constants")
    assert vault_arch.usos_del_nombre_congelado() == []
    assert vault_arch.vinculos_congelados() == []


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
