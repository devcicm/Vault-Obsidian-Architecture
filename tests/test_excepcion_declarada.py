"""AP-61 — el guard cae con el dato que vino a medir.

Dos tests deciden si esto sirve de algo:
`test_un_handler_que_deja_escapar_la_excepcion_rompe_la_puerta`, sin el cual
`vault_excepcion_declarada` sería un informe que no impide nada, y
`test_ninguna_tool_cae_con_un_frontmatter_muy_anidado`, que es la comprobación
**funcional** — ejecuta el dato hostil contra los parsers reales en vez de
mirar su AST. Sin el segundo, el guard mediría su propia forma: verde porque la
excepción está nombrada, sin que nadie haya probado que la tool aguanta.
"""

import ast
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_excepcion_declarada as E  # noqa: E402
import vault_lib  # noqa: E402


def _hostil(profundidad: int = 20000) -> str:
    """Un frontmatter que desborda la pila DENTRO de `safe_load`."""
    return "---\nx: " + "[" * profundidad + "\n---\ncuerpo\n"


# ── La medida ────────────────────────────────────────────────────────────────

def test_el_registro_de_riesgos_nombra_dueño_y_motivo():
    """Un par sin dueño escrito deja al usuario sin saber qué delegar."""
    assert E.RIESGOS, "sin riesgos declarados la tool no mide nada"
    for r in E.RIESGOS:
        assert r["llamadas"] and r["declarada"] and r["escapa"]
        assert r["dueño"] and r["por_que"]


def test_el_repo_no_tiene_deuda_de_AP_61():
    """Los doce sitios de v40.23 se corrigieron; la baseline nació vacía."""
    r = E.check()
    assert r["ok"], r["new_sites"]
    assert r["baseline_size"] == 0, (
        "la baseline de AP-61 dejó de estar vacía: se congeló deuda en vez de "
        "contenerla, y esta norma nació precisamente sin ninguna"
    )


def test_un_handler_que_deja_escapar_la_excepcion_rompe_la_puerta(tmp_path):
    """El guard muerde. Sin esto sería un informe.

    Se mide sobre un árbol sintético, no sobre el repo: si dependiera de que
    exista un infractor real, saldría verde el día que se salden todos — que es
    justo el día en que la norma tiene que seguir vigilando.
    """
    fuente = textwrap.dedent(
        """
        def leer(texto):
            try:
                return yaml.safe_load(texto)
            except yaml.YAMLError:
                return {}
        """
    )
    arbol = ast.parse(fuente)
    riesgo = E.RIESGOS[0]
    handlers = [n for n in ast.walk(arbol) if isinstance(n, ast.ExceptHandler)]
    tipos = E._tipos(handlers[0])
    assert any(riesgo["declarada"] in t for t in tipos)
    assert not any(riesgo["escapa"] in t for t in tipos), (
        "este handler debe contar como infractor: captura la declarada y no la "
        "que escapa"
    )


def test_nombrar_la_excepcion_que_escapa_lo_saca_de_la_deuda():
    """La salida honesta existe y es la que el `hint` recomienda."""
    fuente = textwrap.dedent(
        """
        def leer(texto):
            try:
                return yaml.safe_load(texto)
            except (yaml.YAMLError, RecursionError):
                return {}
        """
    )
    arbol = ast.parse(fuente)
    handler = [n for n in ast.walk(arbol) if isinstance(n, ast.ExceptHandler)][0]
    tipos = E._tipos(handler)
    assert any(E.RIESGOS[0]["escapa"] in t for t in tipos)


# ── El contraste funcional: el dato hostil contra los parsers reales ─────────

@pytest.mark.parametrize("modulo,funcion", [
    ("vault_lib", "parse_frontmatter"),
    ("vault_foreign_check", "_frontmatter"),
    ("vault_migrate_docs", "_frontmatter_valido"),
])
def test_ninguna_tool_cae_con_un_frontmatter_muy_anidado(modulo, funcion):
    """AP-61 medido como lo sufre el consumidor: ejecutando el dato hostil.

    Doce caracteres de anidamiento tumbaban el barrido entero de un vault. Lo
    que se exige aquí no es un veredicto concreto —cada tool tiene el suyo—
    sino que **devuelva** en vez de propagar.
    """
    mod = __import__(modulo)
    getattr(mod, funcion)(_hostil())  # no debe levantar RecursionError


def test_el_cuerpo_sobrevive_al_frontmatter_hostil():
    """El dueño canónico degrada a «sin frontmatter», no a «sin nota»."""
    fm, cuerpo = vault_lib.parse_frontmatter_with_body(_hostil())
    assert fm == {}
    assert "cuerpo" in cuerpo


def test_fuente_unica_mide_el_vault_con_una_nota_hostil_dentro(tmp_path):
    """La tool que acepta `--root` contra vaults ajenos no puede caer.

    Es el caso que la regla 7 hace real: el vault ajeno es el que trae el dato
    que este repo nunca habría generado.
    """
    import vault_fuente_unica as FU

    (tmp_path / "00_System").mkdir()
    (tmp_path / "hostil.md").write_text(_hostil(), encoding="utf-8")
    (tmp_path / "sana.md").write_text(
        "---\nhost_ip: 10.0.0.1\n---\ncontenido\n", encoding="utf-8"
    )
    r = FU.check(tmp_path)  # no debe levantar RecursionError
    assert "conflicts" in r
    assert r["conflicts_total"] == 0
