"""Ningún módulo nuevo decide «qué es sección del vault» con la lista del estándar.

Medido el 2026-10-07: `vault_graph`, `vault_graph_merge`, `vault_validate`,
`vault_tags`, `vault_delta`, `vault_graph_fix`, `vault_section_index` y
`vault_frontmatter_completar` recorrían o filtraban las notas con
`ORDERED_SECTIONS` (o una copia: `VAULT_SECTIONS`, `REQUIRED_FOLDERS`,
`vault_registry.SECTIONS`). Las secciones propias de `00_System/secciones.json`
quedaban fuera sin error: notas sin nodo en el grafo, sin validar, sin
etiquetas registradas, sin hash en el snapshot, índices rechazados.

El criterio tiene dueño (AP-57): `vault_registry.secciones_del_vault(raiz)` o
el puerto `ctx.secciones.ordenadas()`. La lista del estándar sigue siendo
correcta donde lo que se pregunta ES el estándar —qué carpetas crea
`vault_init`, qué estructura exige `check_structure`, qué receta tiene cada
sección del estándar—, y cada uno de esos sitios está abajo con su motivo.

Lo permitido solo encoge: un sitio nuevo falla, y una entrada cuyo sitio ya no
existe también, para que no quede permiso para un uso que nadie mira.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Nombres que contienen la lista de secciones del estándar.
_NOMBRES = {"ORDERED_SECTIONS", "VAULT_SECTIONS", "REQUIRED_FOLDERS", "STANDARD_SECTIONS"}

#: El dueño de la lista: dentro de él, usarla es definirla.
_DUENO = "vault/kernel/registry.py"

PERMITIDOS = {
    "scripts/vault_audit.py::<module>":
        "recetas `tool_hint` por sección: solo el estándar declara receta",
    "scripts/vault_delta.py::<module>":
        "`VAULT_SECTIONS` conservada con superseded_by (no-derogación)",
    "scripts/vault_folder_registry.py::<module>":
        "`STANDARD_SECTIONS`: el conjunto del estándar, por nombre y contrato",
    "scripts/vault_graph.py::<module>":
        "`VAULT_SECTIONS` conservada (no-derogación)",
    "scripts/vault_graph.py::_is_vault_note":
        "función superseded_by notas_en_disco; ya no la llama el barrido",
    "scripts/vault_graph_merge.py::<module>":
        "`VAULT_SECTIONS` conservada (no-derogación)",
    "scripts/vault_graph_merge.py::_is_vault_note":
        "función superseded_by notas_en_disco; ya no la llama el barrido",
    "scripts/vault_init.py::<module>":
        "andamiaje: las carpetas que crea un vault nuevo son las del estándar",
    "vault/autoria/listar.py::<module>":
        "descripciones del estándar para el listado de carpetas",
    "scripts/vault_onboard.py::vault_onboard":
        "índices de las secciones que el onboarding puebla, todas del estándar",
    "vault/indices/registro_de_secciones.py::listar":
        "separa en el listado las del estándar de las propias",
    "vault/indices/registro_de_secciones.py::retirar":
        "una sección del estándar no se retira",
    "scripts/vault_section_index.py::recetas_de_la_nota_de_comandos":
        "recetas `tool_hint`: solo el estándar declara receta",
    "scripts/vault_section_index.py::_nota_de_comandos":
        "recetas `tool_hint`: solo el estándar declara receta",
    "scripts/vault_tags.py::<module>":
        "`VAULT_SECTIONS` conservada con superseded_by (no-derogación)",
    "scripts/vault_validate.py::<module>":
        "`REQUIRED_FOLDERS`: estructura exigida por el estándar",
    "scripts/vault_validate.py::check_structure":
        "la estructura mínima es la del estándar; las propias son opcionales",
    "vault/gobernanza/auditoria_runtime.py::auditar_runtime":
        "respaldo con secciones.json roto: se reporta CN-02 y se sigue con el estándar",
}


def _alias_de_sections(arbol: ast.AST) -> set:
    """Los nombres locales de `vault_registry.SECTIONS` importado."""
    alias = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module == "vault_registry":
            for n in nodo.names:
                if n.name == "SECTIONS":
                    alias.add(n.asname or n.name)
    return alias


def _sitios() -> set:
    sitios = set()
    for base in ("scripts", "vault", "cli", "vault_toolkit"):
        for ruta in sorted((ROOT / base).rglob("*.py")):
            rel = ruta.relative_to(ROOT).as_posix()
            if rel == _DUENO:
                continue
            try:
                arbol = ast.parse(ruta.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            nombres = _NOMBRES | _alias_de_sections(arbol)

            def recorrer(nodo, funcion):
                for hijo in ast.iter_child_nodes(nodo):
                    f = hijo.name if isinstance(
                        hijo, (ast.FunctionDef, ast.AsyncFunctionDef)) else funcion
                    if isinstance(hijo, ast.Name) and hijo.id in nombres:
                        sitios.add(f"{rel}::{funcion}")
                    recorrer(hijo, f)

            recorrer(arbol, "<module>")
    return sitios


def test_ap57_ningun_sitio_nuevo_usa_la_lista_del_estandar_como_secciones_del_vault():
    """AP-57: «qué es sección del vault» lo decide `secciones_del_vault`."""
    nuevos = sorted(_sitios() - set(PERMITIDOS))
    assert not nuevos, (
        "Estos sitios usan la lista de secciones del estándar. Si recorren o "
        "filtran notas, usa vault_registry.secciones_del_vault(raiz) o "
        "ctx.secciones.ordenadas(); si de verdad preguntan por el estándar, "
        f"añádelos a PERMITIDOS con el motivo: {nuevos}"
    )


def test_ap57_lo_permitido_solo_encoge():
    """AP-57: un permiso cuyo sitio ya no existe se borra, no se queda."""
    sobrantes = sorted(set(PERMITIDOS) - _sitios())
    assert not sobrantes, f"Ya no usan la lista del estándar; quítalos: {sobrantes}"


def test_todo_permiso_lleva_motivo():
    assert all(m.strip() for m in PERMITIDOS.values())
