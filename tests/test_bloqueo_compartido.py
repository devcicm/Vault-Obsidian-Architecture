"""AP-57 — el lock de una nota tiene un solo dueño de sus piezas compartidas.

`vault_fs.file_lock` y `_FileLock` de `vault.autoria.conocimiento` toman el mismo
lock. Escritas por separado, sus piezas divergieron dos veces: dd593d0 (dos
nombres de directorio para la misma nota) y ad5b10b (el hueco del borrado
pendiente, arreglado una vez por tomador). Desde entonces la ruta, el alta de
`.locks/` y su retirada viven en `vault.kernel.bloqueo`.

Lo que vigila `vault_criterios` es una segunda definición con el **mismo
nombre**; una copia con otro nombre no la ve, y por eso aquí también se mira
que ninguno de los dos tomadores escriba `.locks` por su cuenta.
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_criterios  # noqa: E402
import vault_fs  # noqa: E402
from vault.autoria.conocimiento import _FileLock  # noqa: E402
from vault.kernel.bloqueo import rutas_de_lock  # noqa: E402

TOMADORES = (SCRIPTS / "vault_fs.py", ROOT / "vault" / "autoria" / "conocimiento.py")
PIEZAS = ("rutas_de_lock", "crear_carpeta_de_locks", "retirar_carpeta_si_vacia")


def test_ap57_las_piezas_del_lock_tienen_dueno_registrado():
    duenos = {f["simbolo"]: f["dueño"] for f in vault_criterios.FUNCIONES_CON_DUENO}
    for pieza in PIEZAS:
        assert duenos.get(pieza) == "vault/kernel/bloqueo.py", pieza


def test_ap57_una_copia_de_una_pieza_se_detecta(tmp_path):
    (tmp_path / "vault" / "kernel").mkdir(parents=True)
    (tmp_path / "vault" / "kernel" / "bloqueo.py").write_text(
        "def rutas_de_lock(o):\n    return o\n", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "otro_lock.py").write_text(
        "def rutas_de_lock(o):\n    return o.parent / '.locks'\n", encoding="utf-8")
    hallazgos = vault_criterios.medir_definiciones(tmp_path)
    assert [h["modulo"] for h in hallazgos] == ["scripts/otro_lock.py"]


def test_ap57_el_repo_no_tiene_copias_de_las_piezas():
    copias = [h for h in vault_criterios.medir_definiciones()
              if h["criterio"] in {f"definicion_de_{p}" for p in PIEZAS}]
    assert copias == []


def test_ningun_tomador_nombra_locks_por_su_cuenta():
    for fichero in TOMADORES:
        arbol = ast.parse(fichero.read_text(encoding="utf-8"))
        literales = [n.value for n in ast.walk(arbol)
                     if isinstance(n, ast.Constant) and isinstance(n.value, str)
                     and n.value in (".locks", ".lock")]
        assert literales == [], fichero.name


def test_los_dos_tomadores_toman_el_mismo_directorio(tmp_path):
    nota = tmp_path / "jwt.md"
    esperado = rutas_de_lock(nota)[1]
    with vault_fs.file_lock(nota, timeout=2) as lock_dir:
        assert Path(lock_dir) == esperado
    assert _FileLock(nota)._lock == esperado


def test_scripts_usa_el_vault_de_su_repo_y_no_uno_instalado(tmp_path):
    """Un `vault` de otra versión en el path no gana al del checkout.

    Medido el 2026-10-05: con la wheel anterior en el user-site, los procesos
    hijos de `test_file_lock_entre_procesos` cargaban ese `vault`, que no
    tenía `kernel.bloqueo`, y morían. Aquí el `vault` viejo es uno falso.
    """
    import os
    import subprocess

    viejo = tmp_path / "site" / "vault" / "kernel"
    viejo.mkdir(parents=True)
    (viejo.parent / "__init__.py").write_text("VIEJO = True\n", encoding="utf-8")
    (viejo / "__init__.py").write_text("", encoding="utf-8")
    codigo = (
        "import sys; from pathlib import Path\n"
        f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
        "from vault_fs import file_lock\n"
        f"with file_lock(Path({str(tmp_path / 'n.md')!r}), timeout=2):\n"
        "    pass\n"
        "import vault; print(getattr(vault, 'VIEJO', False))\n"
    )
    env = dict(os.environ, PYTHONPATH=str(tmp_path / "site"))
    p = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8",
                       env=env, cwd=str(tmp_path), timeout=60)
    assert p.returncode == 0, p.stderr[-600:]
    assert p.stdout.strip() == "False"
