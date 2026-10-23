"""AP-68 — el git del toolkit pasa por un dueño, con verbo declarado.

La pregunta que dio nombre a la norma («¿ejecuta alguna tool git sin
supervisión, o con comandos no autorizados?») tiene que quedar respondida
por algo que falle cuando la respuesta cambie. Estos tests son ese algo, y
miden al dueño y a la puerta por separado:

1. **El dueño, en runtime** — `ejecutar_git` deja pasar los verbos de lectura
   y **rechaza** el mutador desconocido, el uso mutador de un verbo ambiguo
   y el argv que no es lista. Aquí no hay análisis estático: es la garantía.
2. **La puerta, por AST** — `sitios_git_fuera_del_dueno` pilla un sitio nuevo
   en un árbol temporal, con las tres formas que el repo tenía: literal,
   concatenado y por variable.
3. **La puerta sobre el repo real** — cero sitios fuera del dueño, y la
   herramienta de cierre en verde.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
for _ruta in (RAIZ / "scripts", RAIZ):
    if str(_ruta) not in sys.path:
        sys.path.insert(0, str(_ruta))

from vault.kernel import procesos_git as pg  # noqa: E402


# ── 1. El dueño en runtime ──────────────────────────────────────────────────


def test_ap68_01_deja_pasar_los_verbos_de_lectura():
    r = pg.ejecutar_git(RAIZ, ["rev-parse", "--short", "HEAD"],
                        capture_output=True)
    assert r.returncode == 0
    assert r.stdout.strip()


def test_ap68_02_rechaza_un_mutador_no_declarado():
    import pytest

    for verbo in (["reset", "--hard"], ["checkout", "main"], ["clean", "-fd"],
                  ["push", "origin", "main"], ["pull"], ["gc"], ["clone", "http://x"]):
        with pytest.raises(pg.GitProhibido):
            pg.ejecutar_git(RAIZ, verbo, capture_output=True)


def test_ap68_03_rechaza_el_uso_mutador_de_un_verbo_ambiguo():
    """`branch -a` lee y `branch -D` destruye: el verbo no basta, el uso sí."""
    import pytest

    r = pg.ejecutar_git(RAIZ, ["branch", "-a", "--format=%(refname:short)"],
                        capture_output=True)
    assert r.returncode == 0  # el de lectura pasa
    for argv in (["branch", "-D", "main"], ["tag", "v9"], ["config", "user.name", "x"],
                 ["stash", "apply"], ["reflog", "expire", "--all"]):
        with pytest.raises(pg.GitProhibido):
            pg.ejecutar_git(RAIZ, argv, capture_output=True)


def test_ap68_04_rechaza_un_argv_que_no_sea_lista():
    """Sin lista no hay puerta: un string con espacios es un shell en potencia."""
    import pytest

    with pytest.raises(pg.GitProhibido):
        pg.ejecutar_git(RAIZ, "reset --hard", capture_output=True)


def test_ap68_05_el_bootstrap_esta_autorizado_con_motivo():
    """init/add/commit son los tres verbos mutadores que el toolkit admite, y
    cada uno dice por qué existe. Es lo que hace que un cuarto mutador sea una
    decisión revisada en diff y no un argumento que llega de fuera."""
    assert set(pg.MUTADORES_AUTORIZADOS) == {"init", "add", "commit"}
    for verbo, motivo in pg.MUTADORES_AUTORIZADOS.items():
        assert motivo.strip(), verbo
        assert "vault_init" in motivo, verbo


def test_ap68_06_el_dueno_pone_el_lexico_git_por_sus_cuentas():
    """El argv se llama con verbos: el sitio llamado nunca escribe la palabra
    'git', y por eso no puede saltarse el dueño por construcción."""
    import ast
    import inspect

    src = ast.parse(inspect.getsource(pg.ejecutar_git))
    # el unico sitio del repo que escribe el literal "git" en el argv
    llamadas = [n for n in ast.walk(src)
                if isinstance(n, ast.Call) and ast.unparse(n.func).endswith("subprocess.run")]
    assert llamadas, "ejecutar_git debe delegar en subprocess.run"
    assert ast.unparse(llamadas[0]).startswith("subprocess.run(['git'")


def test_ap68_07_asegurar_hash_cierra_la_inyeccion_de_opcion():
    import pytest

    assert pg.es_hash("220d036f")
    # un valor de fichero que empieza por -- es una opción para git, no una ref
    for malo in ("--upload-pack=evil", "--exec=rm", "HEAD~1..HEAD", "abc..def", ""):
        with pytest.raises(pg.RefInvalida):
            pg.asegurar_hash(malo)


# ── 2. La puerta por AST ────────────────────────────────────────────────────


def test_ap68_08_la_puerta_pilla_las_tres_formas_de_argv(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "trampa.py").write_text(
        "import subprocess\n"
        "def literal():\n"
        "    return subprocess.run(['git', 'clean', '-fdx'])\n"
        "def concatenado(repo):\n"
        "    return subprocess.run(['git', '-C', repo] + ['log'])\n"
        "def por_variable():\n"
        "    cmd = ['git', 'log', '-n1']\n"
        "    return subprocess.run(cmd)\n",
        encoding="utf-8",
    )
    sitios = pg.sitios_git_fuera_del_dueno(["scripts"], raiz_repo=str(tmp_path))
    assert len(sitios) == 3, sitios


def test_ap68_09_la_puerta_no_se_queja_de_lo_que_no_es_git():
    tmp_path_ = RAIZ  # usa el repo real como árbol limpio
    sitios = set(pg.sitios_git_fuera_del_dueno(["scripts"], raiz_repo=str(tmp_path_)))
    # ningún sitio del repo está fuera del dueño: esta es la aserción que
    # falla si alguien mete un subprocess.run(["git", ...]) por la puerta atrás
    assert sitios == set(), sorted(sitios)


def test_ap68_10_la_puerta_excluye_su_propio_dueno(tmp_path):
    """El dueño ejecuta git con el literal: si se escaneara a sí mismo, la
    puerta se pondría roja siempre y dejaría de decir nada."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "procesos_git.py").write_text(
        "import subprocess\n"
        "def r():\n"
        "    return subprocess.run(['git', 'log'])\n",
        encoding="utf-8",
    )
    assert pg.sitios_git_fuera_del_dueno(["scripts"], raiz_repo=str(tmp_path)) == []


# ── 3. La herramienta de cierre ──────────────────────────────────────────────


def test_ap68_11_la_tool_de_cierre_esta_en_verde():
    import json
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "vault_procesos_git.py"),
         "--check", "--strict"],
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(RAIZ), timeout=300,
    )
    env = json.loads(proc.stdout)
    assert env["ok"], env
    assert env["norm"] == "AP-68"
    assert env["sites"] == []


def test_ap68_12_la_norma_declara_su_limite_y_por_que():
    """Una norma cuyo alcance no declara lo que no ve promete más de lo que
    cumple (AP-44). Aquí el límite son los tests, y el motivo está escrito."""
    from vault_norms_catalog import norma_por_codigo

    norma = norma_por_codigo("AP-68")
    assert norma["enforcement"] == "guard"
    assert "vault_procesos_git" in norma["tools_enforcing"]
    assert "tests" in norma["prevention"]
    assert "AP-44" in norma["prevention"]  # el motivo del límite está escrito