"""AP-69 — el guard de higiene de los tests y su apoyo compartido."""

import json
import textwrap

import pytest

import vault_tests_higiene as higiene
from apoyo import Corrida, correr_tool, entorno, escribir_nota, nota


def _clases(texto):
    return [s["clase"] for s in higiene.sitios_de("test_x.py", textwrap.dedent(texto))]


def test_ap69_reconoce_cada_clase_de_construccion_a_mano():
    assert _clases('''
        import subprocess, sys, time
        sys.path.insert(0, "scripts")
        def _run(*a):
            return subprocess.run([sys.executable, "x.py", *a])
        TEXTO = "---\\ntitle: A\\n" + "---\\n"
        def test_a(capsys):
            s = ""
            s += "x"
            sys.stdout = None
            time.sleep(1)
    ''') == ["ruta_a_mano", "lanzador_privado", "concatenacion",
             "buffer_a_mano", "captura_a_mano", "espera_fija"]


def test_ap69_lo_legitimo_no_cuenta():
    """Concatenar sin salto, un subprocess sin el intérprete o `capsys` no son deuda."""
    assert _clases('''
        import subprocess
        ruta = "a" + "b"
        def test_b(capsys):
            subprocess.run(["node", "--version"])
            print("x")
            assert capsys.readouterr().out
    ''') == []


def test_ap69_una_concatenacion_encadenada_cuenta_una_vez():
    assert _clases('x = "a\\n" + "b\\n" + "c\\n" + "d"\n') == ["concatenacion"]


def test_ap69_la_firma_no_depende_de_la_linea():
    a = higiene.sitios_de("test_x.py", "import time\ndef f():\n    time.sleep(1)\n")
    b = higiene.sitios_de("test_x.py", "import time\n\n\n# c\ndef f():\n    time.sleep(1)\n")
    assert [s["firma"] for s in a] == [s["firma"] for s in b]
    assert a[0]["linea"] != b[0]["linea"]


def test_ap69_check_ve_lo_nuevo_y_freeze_no_lo_congela_sin_admitirlo(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    base = tmp_path / "base.json"
    (tests / "test_a.py").write_text("import time\ntime.sleep(1)\n", encoding="utf-8")

    r = higiene.freeze(directorio=tests, baseline=base)
    assert r["ok"] is False and r["error_code"] == "DEBT_WOULD_GROW"

    r = higiene.freeze(admitir_nuevos=True, directorio=tests, baseline=base)
    assert r["ok"] and r["frozen"] == 1 and len(r["admitted_new"]) == 1
    assert higiene.check(tests, base)["ok"]

    (tests / "test_b.py").write_text("import sys\nsys.path.append('x')\n", encoding="utf-8")
    r = higiene.check(tests, base)
    assert r["ok"] is False
    assert [s["clase"] for s in r["new_sites"]] == ["ruta_a_mano"]

    (tests / "test_a.py").write_text("x = 1\n", encoding="utf-8")
    (tests / "test_b.py").unlink()
    r = higiene.check(tests, base)
    assert r["ok"] and len(r["resolved_since_baseline"]) == 1
    assert higiene.freeze(directorio=tests, baseline=base)["frozen"] == 0


def test_ap69_no_mide_el_apoyo_ni_el_conftest(tmp_path):
    (tmp_path / "apoyo.py").write_text("import sys\nsys.path.insert(0, 'x')\n", encoding="utf-8")
    (tmp_path / "conftest.py").write_text("import sys\nsys.path.insert(0, 'x')\n", encoding="utf-8")
    assert higiene.sitios(tmp_path) == []


def test_ap69_cada_clase_publica_su_sustituto():
    for clase, ficha in higiene.CLASES.items():
        assert {"ve", "en_vez", "por_que"} <= set(ficha), clase


def test_ap69_la_baseline_del_repo_no_crece():
    r = higiene.check()
    assert r["ok"], r["new_sites"][:5]


@pytest.mark.parametrize("argv, codigo", [
    ([], "MISSING_REQUIRED_ARG"),
    (["--check", "--freeze"], "CONFLICTING_ARGS"),
])
def test_ap69_argumentos_sin_sentido_salen_por_el_catalogo(argv, codigo, capsys):
    assert higiene.main(argv) == 1
    assert json.loads(capsys.readouterr().out)["error_code"] == codigo


# --- apoyo -----------------------------------------------------------------

def test_apoyo_nota_serializa_el_frontmatter_con_yaml():
    import yaml

    texto = nota({"title": "A: con dos puntos", "status": "draft"}, """
        # A
        cuerpo
    """)
    cabecera = texto.split("---\n")[1]
    assert yaml.safe_load(cabecera) == {"title": "A: con dos puntos", "status": "draft"}
    assert texto.endswith("# A\ncuerpo\n")


def test_apoyo_escribir_nota_crea_carpetas_y_escribe_en_lf(tmp_path):
    ruta = escribir_nota(tmp_path, "01_Projects/a.md", {"title": "A"}, "x\n")
    assert b"\r\n" not in ruta.read_bytes()


def test_apoyo_entorno_con_vault_fija_la_raiz_estricta(tmp_path):
    env = entorno(tmp_path, quitar=("VAULT_PERMISSIVE_ROOT",), EXTRA=1)
    assert env["VAULT_ROOT"] == str(tmp_path) and env["VAULT_STRICT_ROOT"] == "1"
    assert env["EXTRA"] == "1" and "VAULT_PERMISSIVE_ROOT" not in env


def test_apoyo_el_envelope_que_no_llega_ensena_el_stderr():
    with pytest.raises(AssertionError, match="Traceback"):
        Corrida(1, "", "Traceback (most recent call last)").envelope


def test_apoyo_correr_tool_lanza_la_tool_y_lee_su_envelope():
    r = correr_tool("vault_tests_higiene")
    assert r.codigo == 1
    assert r.envelope["error_code"] == "MISSING_REQUIRED_ARG"


# ── La firma no depende del intérprete ───────────────────────────────────────


def test_la_firma_no_depende_de_los_parentesis_del_destino():
    """`for (a, b) in` y `for a, b in` son el mismo código.

    3.9–3.11 escriben el paréntesis y 3.12+ no; si la firma los distinguiera,
    la misma baseline valdría en un intérprete y en otro no — que es como se
    puso la CI en rojo el 2026-11-02 sin mover una línea.
    """
    import ast

    from vault.meta_toolkit.estandar.firma_sitio import _texto_canonico

    con = ast.parse("for (a, b) in x:\n    pass").body[0]
    sin = ast.parse("for a, b in x:\n    pass").body[0]
    assert _texto_canonico(con) == _texto_canonico(sin)
    assert "(a, b)" not in _texto_canonico(con)


def test_la_firma_normaliza_la_comilla_del_fstring_anidado():
    """El f-string con comilla dentro: 3.12 lo escribe con simple, 3.14 con doble."""
    from vault.meta_toolkit.estandar.firma_sitio import _re_comillar_fstrings

    de_312 = "f'{d['tool']}.py'"
    assert _re_comillar_fstrings(de_312) == 'f"{d[\'tool\']}.py"'
    # Y el que ya viene con doble no se toca.
    de_314 = 'f"{d[\'tool\']}.py"'
    assert _re_comillar_fstrings(de_314) == de_314
    # Ni el simple, que no lleva comilla dentro.
    assert _re_comillar_fstrings("f'v{n}'") == "f'v{n}'"
