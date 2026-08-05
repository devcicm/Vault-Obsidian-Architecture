"""Higiene del código fuente del repo. No mira el vault: mira las tools.

Dos defectos reales encontrados en v39, ambos invisibles hasta que alguien
tropezó con ellos:

  1. **20 scripts con retornos de carro desnudos** (`\\r` sin `\\n`), estilo Mac
     clásico. Python los ejecuta sin quejarse, así que nadie lo notó — pero
     `grep`, `sed` y `git diff` ven el archivo entero como UNA línea. Un diff
     de un cambio de tres caracteres aparecía como "todo el archivo cambió",
     que es exactamente cómo una revisión deja de revisar.
  2. **Una tool archivada que no parsea.** `vault_create.py` lleva sin compilar
     desde que se archivó en v21. No-derogación dice que no se borra; no dice
     que no se sepa.
  3. **11 scripts con nombres nunca importados.** `vault_graph` leía
     `SYSTEM_DIR / "move-log.json"` sin que `SYSTEM_DIR` existiera; siete tools
     usaban `datetime`/`timezone` sin importarlos. Compilan perfectamente: el
     `NameError` solo aparece cuando la ejecución entra en esa rama, que en
     `vault_graph` era la de nodos movidos — una rama poco frecuente que llevaba
     versiones rota. `ast.parse` no lo ve; este módulo sí.
"""
import ast
import builtins
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = sorted((ROOT / "scripts").rglob("*.py"))

# Deuda conocida, congelada como la baseline de AP-37: puede encoger, no crecer.
# Vacía desde v39: `vault_create.py` (archivada en v21, superseded_by vault_write)
# se reparó — llevaba versiones sin compilar. Que esté vacía es lo que convierte
# `test_todo_script_compila` en un guard duro en vez de una foto de la deuda.
SIN_PARSEAR: set = set()


def test_hay_scripts_que_revisar():
    assert len(SCRIPTS) > 50, "el glob no encontró los scripts"


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_ningun_script_usa_retornos_de_carro_desnudos(script):
    crudo = script.read_bytes()
    assert b"\r" not in crudo.replace(b"\r\n", b""), (
        f"{script.name} tiene CR sin LF: el archivo es una sola línea para grep, "
        f"sed y git diff, y cualquier revisión sobre él es ilegible"
    )


@pytest.mark.parametrize(
    "script", [p for p in SCRIPTS if p.name not in SIN_PARSEAR], ids=lambda p: p.name
)
def test_todo_script_compila(script):
    ast.parse(script.read_text(encoding="utf-8", errors="replace"), filename=str(script))


def _nombres_no_resueltos(script: Path) -> set:
    """Nombres leídos que no se definen ni se importan en ningún punto del módulo.

    Aproximación deliberadamente laxa: se recogen TODAS las definiciones del
    archivo (de cualquier ámbito) en un único conjunto. Eso deja pasar errores
    de ámbito reales — una variable local usada desde otra función — pero a
    cambio no produce ni un falso positivo, que es lo que hace que un guard
    sobreviva. Lo que sí detecta sin ambigüedad es el caso que nos costó
    caro: el nombre que no está en ninguna parte.
    """
    try:
        arbol = ast.parse(script.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()

    definidos = set(dir(builtins)) | {"__file__", "__name__", "__doc__"}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Import, ast.ImportFrom)):
            definidos |= {(a.asname or a.name).split(".")[0] for a in nodo.names}
        elif isinstance(nodo, ast.Name) and isinstance(nodo.ctx, (ast.Store, ast.Del)):
            definidos.add(nodo.id)
        elif isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definidos.add(nodo.name)
        elif isinstance(nodo, ast.arg):
            definidos.add(nodo.arg)
        elif isinstance(nodo, ast.ExceptHandler) and nodo.name:
            definidos.add(nodo.name)
        elif isinstance(nodo, (ast.Global, ast.Nonlocal)):
            definidos |= set(nodo.names)

    return {
        n.id
        for n in ast.walk(arbol)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in definidos
    }


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_ningun_script_lee_un_nombre_que_no_existe(script):
    sueltos = sorted(_nombres_no_resueltos(script))
    assert not sueltos, (
        f"{script.name} usa {sueltos} sin importarlos ni definirlos: compila, "
        f"pero lanza NameError en cuanto la ejecución entre en esa rama"
    )


ARCHIVADAS = sorted((ROOT / "scripts" / "_archived").glob("vault*.py"))


@pytest.mark.parametrize("script", ARCHIVADAS, ids=lambda p: p.name)
def test_toda_tool_archivada_declara_quien_la_reemplaza(script):
    """No-derogación: archivar sin decir qué usar en su lugar deja un callejón.

    La política dice que lo reemplazado se anota `superseded_by:` conservando su
    contrato. Estaba declarada en el manifiesto y no aplicada aquí: las 8 tools
    de `_archived/` no decían nada.
    """
    cabecera = script.read_text(encoding="utf-8", errors="replace")[:1200]
    assert "superseded_by:" in cabecera, (
        f"{script.name} está archivada sin declarar sucesora; anótala en el "
        f"docstring y en scripts/_archived/README.md"
    )


def test_el_mapa_de_sucesion_esta_documentado():
    readme = (ROOT / "scripts" / "_archived" / "README.md").read_text(encoding="utf-8")
    for script in ARCHIVADAS:
        assert script.name in readme, f"{script.name} no aparece en _archived/README.md"


def test_ninguna_tool_archivada_se_expone_por_mcp():
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from vault_mcp_catalog import TOOLS_CATALOG

    filtradas = {p.stem for p in ARCHIVADAS} & set(TOOLS_CATALOG)
    assert not filtradas, (
        f"{sorted(filtradas)} está archivada pero publicada por MCP: un agente "
        f"puede invocar una tool que el estándar ya no sostiene"
    )


def test_toda_tool_del_catalogo_tiene_implementacion():
    """Una entrada sin script Python y sin runtime declarado es una promesa vacía.

    `vault_backup_base64` y `vault_restore_base64` no tienen `.py`: están
    implementadas nativas en el servidor MCP. Con `script: ""` a secas, todo
    guard que itera el catálogo las saltaba creyéndolas inexistentes — publicadas
    por MCP y sin que nadie comprobara nada sobre ellas.
    """
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from vault_mcp_catalog import TOOLS_CATALOG

    servidor = (ROOT / "mcp" / "nodejs" / "vault-mcp-server.mjs").read_text(
        encoding="utf-8", errors="replace"
    )

    huerfanas = []
    for nombre, spec in TOOLS_CATALOG.items():
        script = spec.get("script")
        if script and (ROOT / "scripts" / script).is_file():
            continue
        if spec.get("runtime") == "node":
            assert f'case "{nombre}"' in servidor, (
                f"{nombre} se declara runtime node pero el servidor MCP no la "
                f"despacha: la tool está publicada y no existe en ninguna parte"
            )
            continue
        huerfanas.append(nombre)

    assert not huerfanas, (
        f"{sorted(huerfanas)} están en el catálogo sin script Python ni "
        f"`runtime` declarado: se exponen por MCP sin implementación localizable"
    )


def test_la_deuda_de_scripts_rotos_no_crece():
    """Si uno de la lista se arregla, sale de ella y ya no puede volver a entrar."""
    rotos = set()
    for script in SCRIPTS:
        try:
            ast.parse(script.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            rotos.add(script.name)
    nuevos = rotos - SIN_PARSEAR
    assert not nuevos, f"scripts que dejaron de compilar: {sorted(nuevos)}"
    resueltos = SIN_PARSEAR - rotos
    assert not resueltos, (
        f"{sorted(resueltos)} ya compila: quítalo de SIN_PARSEAR para que no "
        f"pueda volver a romperse en silencio"
    )
