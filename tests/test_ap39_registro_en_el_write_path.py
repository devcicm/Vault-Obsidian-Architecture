"""AP-39 se cumplía en una de cada quince escrituras.

La norma dice que un tag nuevo se admite **pero se registra**. Quien lo
registraba era `vault_write`, y `vault_write` no es el único escritor: los
catorce `*_save` que llevan tags construyen su frontmatter a mano y llaman
directamente a `atomic_write_text`. El término entraba en el vault, la bitácora
no se enteraba, y el audit lo denunciaba después contra la nota — culpando al
contenido de un fallo del escritor. Es AP-43 en su forma literal: norma sin
refuerzo en el punto de uso.

El refuerzo está ahora en el write path del kernel, junto al índice de sección,
por el mismo motivo que aquel: es el único punto por el que pasan todas las
escrituras. Cablearlo en los catorce sitios funciona hasta que alguien escribe
el decimoquinto.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _entradas(raiz: Path):
    bitacora = raiz / "19_Audits" / "vocabulary" / "tag-ledger.json"
    if not bitacora.exists():
        return []
    return [e["tag"] for e in json.loads(bitacora.read_text(encoding="utf-8"))["entries"]]


def _ejecutar(raiz: Path, *argv: str):
    entorno = dict(
        os.environ,
        VAULT_ROOT=str(raiz),
        VAULT_AGENT="claude",
        PYTHONIOENCODING="utf-8",
    )
    return subprocess.run(
        [sys.executable, str(SCRIPTS / argv[0]), *argv[1:]],
        env=entorno,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(REPO_ROOT),
    )


@pytest.fixture
def raiz(tmp_path):
    """Apunta el kernel a `tmp_path` por la costura declarada.

    Parchear `vault_io.get_vault_root` con monkeypatch parecía equivalente y no
    lo es: los módulos hacen `from vault_io import get_vault_root`, así que el
    primero que se importe *dentro* de la ventana parcheada se queda con el
    doble para siempre —monkeypatch deshace el atributo, no la copia—. Eso
    envenenaba a `vault_section_index` y tumbaba dos tests de otro fichero.
    `set_vault_root()` es la costura que sí respeta la resolución tardía.
    """
    import vault_io

    vault_io.set_vault_root(tmp_path)
    yield tmp_path
    vault_io.reset_vault_root()


@pytest.fixture
def vault(tmp_path):
    _ejecutar(tmp_path, "vault_init.py")
    return tmp_path


def test_un_save_que_no_pasa_por_vault_write_tambien_deja_rastro(vault):
    """`vault_knowledge_save` escribe con `atomic_write_text` y nunca registró."""
    resultado = _ejecutar(
        vault,
        "vault_knowledge_save.py",
        "--category", "concept",
        "--title", "Concepto de prueba",
        "--content", "Una linea.\nOtra linea.\nY una tercera con palabras de sobra.",
        "--tags", "terminonuevoxyz",
    )
    assert '"ok": true' in resultado.stdout, resultado.stdout[-400:] + resultado.stderr[-400:]
    assert "terminonuevoxyz" in _entradas(vault)


def test_el_gancho_esta_declarado_y_dice_por_que():
    """Un gancho del kernel sin motivo escrito es un cruce escondido."""
    from vault_arch import GANCHOS_DEL_KERNEL

    motivo = GANCHOS_DEL_KERNEL.get(("vault_io", "vault_tags"))
    assert motivo, "el gancho de la bitácora no está declarado en vault_arch"
    assert "AP-39" in motivo and "AP-43" in motivo


def test_un_gancho_declarado_no_cuenta_ademas_como_deuda():
    """Si contara dos veces, el registro de ganchos sería inservible: usarlo
    rompería una puerta que solo puede encoger. Los tres que ya existían
    entraron escondidos dentro de la baseline genérica."""
    from vault_arch import GANCHOS_DEL_KERNEL, cruces

    pares = {(c["from"], c["to"]) for c in cruces()}
    assert not (pares & set(GANCHOS_DEL_KERNEL)), sorted(pares & set(GANCHOS_DEL_KERNEL))


def test_la_bitacora_no_puede_tumbar_una_escritura(tmp_path, monkeypatch, raiz):
    """Es memoria, no un guard. Si falla, la nota ya es válida."""
    import vault_io

    def _explota(*_a, **_k):
        raise RuntimeError("bitácora rota")

    import vault_tags

    monkeypatch.setattr(vault_tags, "registrar_tags_de_nota", _explota)

    destino = tmp_path / "07_Knowledge" / "nota.md"
    vault_io.atomic_write_text(destino, '---\ntags: ["x"]\n---\n\nCuerpo.\n')

    assert destino.exists()


def test_lo_que_no_es_una_nota_no_toca_la_bitacora(tmp_path, raiz):
    """Un JSON de índice pasa por el mismo write path y no tiene vocabulario."""
    import vault_io

    vault_io.atomic_write_json(tmp_path / "99_Index" / "graph.json", {"nodes": []})

    assert _entradas(tmp_path) == []


def test_la_carpeta_de_la_bitacora_no_se_indexa_como_seccion(vault):
    """Su `index.md` contaba como nota en disco y desajustaba la búsqueda.

    Un vault recién onboardeado pasaba a violar AP-47 —«1 nota en disco fuera
    del índice»— por una nota que nadie escribió: el índice de una carpeta que
    solo guarda un JSON. Es la maquinaria de una norma, no una sección.
    """
    from vault_registry import MACHINERY_FOLDERS

    assert "19_Audits/vocabulary" in MACHINERY_FOLDERS

    _ejecutar(
        vault,
        "vault_knowledge_save.py",
        "--category", "concept",
        "--title", "Otro concepto",
        "--content", "Una linea.\nOtra linea.\nY una tercera con palabras de sobra.",
        "--tags", "otroterminoxyz",
    )
    _ejecutar(vault, "vault_section_index.py", "--folder", "19_Audits")

    assert not (vault / "19_Audits" / "vocabulary" / "index.md").exists()
