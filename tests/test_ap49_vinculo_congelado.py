"""AP-49 — vínculo resuelto en tiempo de import, con su puerta.

La costura de inyección lleva versiones publicada (`vault_io.set_vault_root()`,
usada por 12 tests) y está **inerte** para la mayoría del repo: un módulo que
hizo `SYSTEM_DIR = VAULT_ROOT / '00_System'` al cargarse ya no puede reapuntar.
La inyección parece disponible y no lo está, que es peor que no tenerla — quien
la usa cree haber redirigido la escritura.

Estas pruebas ejercen la regla del guard, no repiten su resultado: qué cuenta
como vínculo congelado y qué no. Y una comprueba lo que la norma afirma sobre el
repo, que es lo que la hace algo más que una opinión bien redactada.
"""

import ast
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_arch as arch  # noqa: E402
from vault_norms import NORM_CATALOG  # noqa: E402


def _norma():
    return next(n for n in NORM_CATALOG if n["code"] == "AP-49")


# ── La norma existe y cumple las reglas del repo ─────────────────────────────

def test_ap49_esta_en_el_catalogo_con_enforcement_real():
    """Ninguna norma nueva puede tener enforcement `manual` (regla 5)."""
    n = _norma()
    assert n["enforcement"] in {"guard", "audit", "guard+audit", "recommended"}
    assert n["enforcement"] == "guard+audit"
    assert n["severity"] == "high"
    assert n["introduced_version"] == "v40.0"


def test_ap49_nombra_la_tool_que_la_hace_cumplir():
    """Una norma cuyo `tools_enforcing` no existe es AP-42."""
    n = _norma()
    assert "vault_arch --check" in n["tools_enforcing"]
    assert (REPO_ROOT / "scripts" / "vault_arch.py").exists()


# ── La regla del guard, ejercida ─────────────────────────────────────────────

def _bindings(fuente: str, tmp_path: Path, monkeypatch) -> list[str]:
    """Corre el guard sobre un módulo de mentira y devuelve los nombres."""
    (tmp_path / "vault_falso.py").write_text(fuente, encoding="utf-8")
    monkeypatch.setattr(arch, "SCRIPTS_DIR", tmp_path)
    monkeypatch.setattr(arch, "_modulos_en_disco", lambda: ["vault_falso"])
    return [v["binding"] for v in arch.vinculos_congelados()]


def test_una_ruta_derivada_al_importar_es_vinculo(tmp_path, monkeypatch):
    fuente = "from vault_io import VAULT_ROOT\nSYSTEM_DIR = VAULT_ROOT / '00_System'\n"
    assert _bindings(fuente, tmp_path, monkeypatch) == ["SYSTEM_DIR"]


def test_dentro_de_una_funcion_no_es_vinculo(tmp_path, monkeypatch):
    """En una función la expresión se reevalúa: `set_vault_root()` sí la afecta.

    Marcarlo sería marcar la solución, y un guard que castiga el arreglo es un
    guard que se desactiva.
    """
    fuente = (
        "from vault_io import VAULT_ROOT\n"
        "def sistema():\n    return VAULT_ROOT / '00_System'\n"
    )
    assert _bindings(fuente, tmp_path, monkeypatch) == []


def test_resolver_tarde_no_es_vinculo_aunque_se_guarde(tmp_path, monkeypatch):
    """Pasar por el kernel es la vía correcta; el guard no la penaliza."""
    fuente = (
        "import vault_io\n"
        "SYSTEM_DIR = vault_io.get_vault_root() / '00_System'\n"
    )
    assert _bindings(fuente, tmp_path, monkeypatch) == []


def test_una_constante_sin_relacion_con_la_raiz_no_es_vinculo(tmp_path, monkeypatch):
    fuente = "MAX = 10\nNOMBRE = 'x' + 'y'\n"
    assert _bindings(fuente, tmp_path, monkeypatch) == []


def test_la_anotacion_de_tipo_no_esconde_el_vinculo(tmp_path, monkeypatch):
    """`SYSTEM_DIR: Path = VAULT_ROOT / ...` congela exactamente igual."""
    fuente = (
        "from pathlib import Path\nfrom vault_io import VAULT_ROOT\n"
        "SYSTEM_DIR: Path = VAULT_ROOT / '00_System'\n"
    )
    assert _bindings(fuente, tmp_path, monkeypatch) == ["SYSTEM_DIR"]


def test_un_fichero_con_sintaxis_rota_no_tumba_el_guard(tmp_path, monkeypatch):
    assert _bindings("def (\n", tmp_path, monkeypatch) == []


# ── La baseline ──────────────────────────────────────────────────────────────

def test_la_deuda_de_vinculos_solo_encoge():
    r = arch.check()
    assert not r["new_frozen_bindings"], (
        f"vínculos congelados nuevos: {r['new_frozen_bindings']}. Se arreglan "
        f"resolviendo tarde con `get_vault_root()` dentro de la función, no "
        f"ampliando arch-baseline.json."
    )


def test_la_baseline_de_vinculos_esta_al_dia():
    r = arch.check()
    assert not r["settled_frozen_bindings"], (
        f"ya no están congelados: {r['settled_frozen_bindings']} — corre "
        f"`--freeze` para que no puedan volver"
    )


def test_la_cifra_de_la_norma_es_la_que_mide_la_puerta():
    """Norma y guard miden lo mismo, o la norma no es comprobable (AP-44).

    Es literal: la descripción dice «82 vínculos en 62 módulos» y eso lo cuenta
    el guard. Si alguien salda deuda y no actualiza el texto, este test lo dice.
    """
    vinculos = arch.vinculos_congelados()
    texto = _norma()["description"]
    assert f"**{len(vinculos)} vínculos congelados en" in texto, (
        f"la norma dice otra cifra; el guard cuenta {len(vinculos)} vínculos en "
        f"{len({v['module'] for v in vinculos})} módulos"
    )
    assert f"{len({v['module'] for v in vinculos})} módulos**" in texto


def test_el_kernel_nuevo_no_comete_la_norma_que_cura():
    """`vault/` no puede tener un solo vínculo congelado.

    Es el paquete que existe para eliminar AP-49: cometerla aquí sería el
    equivalente exacto de AP-44 —la solución certificándose a sí misma—.
    """
    for src in (REPO_ROOT / "vault").rglob("*.py"):
        arbol = ast.parse(src.read_text(encoding="utf-8"))
        for nodo in arbol.body:
            if isinstance(nodo, (ast.Assign, ast.AnnAssign)):
                usa = any(
                    isinstance(n, ast.Name) and n.id == "VAULT_ROOT"
                    for n in ast.walk(nodo.value)
                ) if nodo.value else False
                assert not usa, f"{src.name}:{nodo.lineno} congela VAULT_ROOT"


def test_ningun_modulo_de_vault_importa_vault_root():
    """La regla que hace real la inyección: el dominio recibe la raíz.

    Se permite exactamente en `adaptadores.py`, que es la frontera declarada con
    `scripts/` — y ni siquiera ahí se importa el valor, se llama a la función.
    """
    for src in (REPO_ROOT / "vault").rglob("*.py"):
        texto = src.read_text(encoding="utf-8")
        assert "import VAULT_ROOT" not in texto, src.name
        assert "vault_io.VAULT_ROOT" not in texto, src.name
