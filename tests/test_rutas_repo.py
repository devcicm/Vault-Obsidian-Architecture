"""F4 — el layout del repo tiene dueño, y el dueño es el único que lo nombra.

`vault/kernel/rutas.py` posee los nombres de la disposición de este repo
(`scripts/`, `docs/`, `schemas/`, `normas/`, `vault-sandbox/`…). Antes de
v41.21 estaban como literal suelto en ~30 módulos: cada uno razonable, el
agregado invisible — el día que la disposición cambiara, treinta sitios
romperían en silencio.

Este test es el guard: cuenta los literales de layout que aparecen en
módulos que no son el dueño y los compara contra `scripts/rutas-baseline.json`,
que **solo encoge**. Un sitio nuevo se migra al dueño con `ruta_repo()`,
no se congela — exactamente la mecánica de las baselines de AP-58/AP-62.
"""

import ast
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
for _r in (RAIZ / "scripts", RAIZ):
    if str(_r) not in sys.path:
        sys.path.insert(0, str(_r))

sys.stdout.reconfigure(encoding="utf-8")

from vault.kernel.rutas import es_layout_repo  # noqa: E402

BASELINE = RAIZ / "scripts" / "rutas-baseline.json"
DUEÑO = "rutas.py"
BASES = ("scripts", "vault", "cli")


def sitios_actuales() -> set[str]:
    """Los literales de layout en módulos que no son el dueño, `fich:linea:lit`."""
    sitios: set[str] = set()
    for base in BASES:
        for p in sorted(Path(RAIZ / base).rglob("*.py")):
            if "node_modules" in p.parts or p.name == DUEÑO:
                continue
            if "_archived" in p.parts:
                continue
            try:
                arbol = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            docs: set[str] = set()
            for n in ast.walk(arbol):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef, ast.Module)):
                    d = ast.get_docstring(n, clean=False)
                    if d:
                        docs.add(d)
            for n in ast.walk(arbol):
                if isinstance(n, ast.Constant) and isinstance(n.value, str):
                    v = n.value.strip().rstrip("/")
                    if v and es_layout_repo(v):
                        # un literal citado dentro de un docstring es prosa,
                        # no un path en ejecución
                        if any(v in d for d in docs):
                            continue
                        rel = p.relative_to(RAIZ).as_posix()
                        sitios.add(f"{rel}:{v}")
    return sitios


def baseline() -> set[str]:
    if not BASELINE.is_file():
        return set()
    return set(json.loads(BASELINE.read_text(encoding="utf-8")).get("sitios", []))


def test_el_dueno_existe_y_valida_los_nombres():
    from vault.kernel import rutas

    assert "scripts" in rutas.NOMBRES
    assert rutas.ruta_repo("scripts") == RAIZ / "scripts"
    try:
        rutas.ruta_repo("no-existe")
        raise AssertionError("ruta_repo admitió un directorio fuera de la lista")
    except ValueError:
        pass


def test_ningun_literal_de_layout_nuevo_fuera_del_dueno():
    """La baseline congela lo que ya estaba; lo que entra después se migra."""
    actuales = sitios_actuales()
    congelados = baseline()
    nuevos = sorted(actuales - congelados)
    assert not nuevos, (
        f"literales de layout nuevos fuera de su dueño: {nuevos[:8]}. "
        "Se salda migrando la llamada a vault.kernel.rutas.ruta_repo() — la "
        "baseline solo encoge, y añadir el sitio a ella no es la solución."
    )


def test_la_baseline_solo_encoge_y_no_incluye_fantasmas():
    congelados = baseline()
    actuales = sitios_actuales()
    fantasma = sorted(congelados - actuales)
    if fantasma:
        # sitios que ya se migraron y siguen congelados: la baseline tiene que
        # encogerse en el mismo commit que la migración
        raise AssertionError(
            f"la baseline congela {len(fantasma)} sitios que ya no existen: "
            f"{fantasma[:5]} — encógela en el mismo commit de la migración"
        )
