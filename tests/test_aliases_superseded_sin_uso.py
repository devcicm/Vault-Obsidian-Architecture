"""Los nombres viejos que v40.8 y v40.9 dejaron como alias no se vuelven a leer.

Cuando `test_puertos_verificados` promovió símbolos privados a públicos, los
nombres privados se quedaron como alias anotados `superseded_by:` —la
no-derogación vale también para los símbolos—. Pero conservar un nombre no es
seguir usándolo: mientras el código del repo los leyera, el nombre «viejo» era
el que se aprendía leyendo el código, y la deuda #5 los contaba como «aliases
con el nombre viejo aún en uso».

La lista es explícita y no detectada: `_raiz` o `_slug` son también modismos
locales legítimos en otros módulos, así que una detección genérica de «alias
privado» mezclaría las dos cosas. Lo que sí se exige es que cada nombre de la
lista siga existiendo con su anotación: borrar el alias para pasar este test
sería cumplirlo derogando.
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: nombre viejo → (módulo que lo define, nombre canónico)
ALIASES = {
    "_cuerpo_sin_marcadores": ("scripts/vault_norms_engine.py", "cuerpo_sin_marcadores"),
    "_parse_frontmatter_tags": ("scripts/vault_tags.py", "tags_de_frontmatter"),
    "_deduce_type_from_folder": ("scripts/vault_write.py", "tipo_por_carpeta"),
    "_load_ledger": ("scripts/vault_tags.py", "load_ledger"),
    "_raiz": ("scripts/vault_tags.py", "raiz"),
    "_notas_en_disco": ("scripts/vault_reindex.py", "notas_indexables"),
}

#: `_raiz` es un modismo local en otros módulos: solo cuenta dentro de su dueño
#: o leído como atributo de `vault_tags`.
_SOLO_EN_SU_DUENO = {"_raiz"}

#: La fachada reexporta el nombre viejo para quien lo importe desde fuera; eso
#: es conservarlo, no usarlo.
_REEXPORTS = {("scripts/vault_norms.py", "_cuerpo_sin_marcadores")}


def _ficheros():
    for raiz in ("scripts", "vault", "cli", "tests"):
        yield from sorted((REPO / raiz).rglob("*.py"))


def _lecturas(path: Path):
    rel = path.relative_to(REPO).as_posix()
    arbol = ast.parse(path.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Name) and isinstance(nodo.ctx, ast.Load):
            nombre = nodo.id
            if nombre in _SOLO_EN_SU_DUENO and rel != ALIASES[nombre][0]:
                continue
        elif isinstance(nodo, ast.Attribute) and isinstance(nodo.ctx, ast.Load):
            nombre = nodo.attr
            if nombre in _SOLO_EN_SU_DUENO and not (
                isinstance(nodo.value, ast.Name) and "tags" in nodo.value.id
            ):
                continue
        elif isinstance(nodo, ast.ImportFrom):
            for alias in nodo.names:
                if alias.name not in ALIASES or (rel, alias.name) in _REEXPORTS:
                    continue
                if alias.name in _SOLO_EN_SU_DUENO and nodo.module != Path(
                        ALIASES[alias.name][0]).stem:
                    continue
                yield rel, nodo.lineno, alias.name
            continue
        else:
            continue
        if nombre in ALIASES:
            yield rel, nodo.lineno, nombre


def test_nadie_lee_los_nombres_superseded():
    lecturas = [l for p in _ficheros() if p.name != Path(__file__).name
                for l in _lecturas(p)]
    assert not lecturas, (
        "Estos sitios leen el nombre viejo; usa el canónico "
        f"({ {k: v[1] for k, v in ALIASES.items()} }): {lecturas}"
    )


def test_los_nombres_viejos_siguen_definidos_y_anotados():
    for viejo, (modulo, canonico) in ALIASES.items():
        texto = (REPO / modulo).read_text(encoding="utf-8")
        arbol = ast.parse(texto)
        definido = any(
            (isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == viejo for t in n.targets))
            or (isinstance(n, ast.FunctionDef) and n.name == viejo)
            for n in arbol.body
        )
        assert definido, f"{modulo} ya no define {viejo}: eso es derogar"
        assert f"superseded_by: `{canonico}`" in texto, (
            f"{modulo}: {viejo} debe declarar `superseded_by: `{canonico}``"
        )
