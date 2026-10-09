"""El límite declarado de la guarda de `00_System/` (aviso 6 de la tanda v41.3).

`vault_arch.escrituras_de_sistema_en` decide la subruta mirando la llamada que
escribe, sin análisis de flujo. Desde v41.3 sigue además **un nivel** entre
módulos: una función del repo cuyo `return` es una ruta literal de
`00_System/` (`vault_io.tool_spec_path`) se resuelve en el módulo que la
importa —`from vault_io import tool_spec_path` o `vault_io.tool_spec_path()`—.

El caso medido el 2026-10-09 era ese: `vault_manifest --bootstrap` escribe
`00_System/tool-spec.json` con `atomic_write_json(tool_spec_path())` y la
guarda no lo veía. Ahora lo ve.

Siguen fuera, y la entrada `fronteras_de_escritura_por_contexto` del plano los
declara en vez de dar la frontera por cubierta entera:

- la ruta **llega por parámetro**: el escritor recibe `ruta` y quien la
  construye no escribe;
- la función **no se sabe de dónde viene** (sin import que la resuelva, o con
  la ruta calculada a más de un nivel): colapsa a `"*"`, que la guarda no
  reporta porque es «crear la carpeta».

Estos tests fijan las dos cosas: lo que se ve y lo que no.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import vault_arch  # noqa: E402


def _subrutas(fuente: str) -> list[str]:
    return [s for _, _, s in vault_arch.escrituras_de_sistema_en(ast.parse(fuente))]


def test_limite_declarado_la_ruta_por_parametro_no_se_ve():
    fuente = '''
def registrar(ruta, datos):
    atomic_write_json(ruta, datos)
def quien_la_construye(root):
    registrar(root / "00_System" / "tag-registry.json", {})
'''
    assert _subrutas(fuente) == []
    # Si el helper se llama como una escritura, la guarda lo ve por el nombre
    # (`vault_arch.llamada_de_escritura`): el límite es el del helper neutro.
    assert _subrutas(fuente.replace("registrar", "escribir")) == ["tag-registry.json"]


def test_limite_declarado_la_funcion_sin_import_colapsa_a_la_carpeta():
    fuente = '''
def bootstrap():
    spec_file = tool_spec_path()
    atomic_write_json(spec_file, {})
'''
    # Sin import que diga de dónde viene, se reconoce la carpeta, no la subruta.
    assert _subrutas(fuente) == ["*"]


def _subrutas_con_repo(fuente: str) -> list[str]:
    arbol = ast.parse(fuente)
    return [s for _, _, s in vault_arch.escrituras_de_sistema_en(
        arbol, externas=vault_arch.funciones_de_sistema_del_repo())]


def test_la_funcion_importada_se_resuelve_un_nivel():
    por_nombre = '''
from vault_io import tool_spec_path
def bootstrap():
    spec_file = tool_spec_path()
    atomic_write_json(spec_file, {})
'''
    assert _subrutas_con_repo(por_nombre) == ["tool-spec.json"]

    por_modulo = '''
import vault_io as vio
def bootstrap():
    atomic_write_json(vio.tool_spec_path(), {})
'''
    assert _subrutas_con_repo(por_modulo) == ["tool-spec.json"]


def test_una_funcion_homonima_de_otro_modulo_no_se_confunde():
    # El índice es por módulo: importar `tool_spec_path` de un módulo que no la
    # define con ruta literal no hereda la subruta de `vault_io`.
    fuente = '''
from otro_modulo import tool_spec_path
def bootstrap():
    atomic_write_json(tool_spec_path(), {})
'''
    assert _subrutas_con_repo(fuente) == ["*"]


def test_el_indice_solo_guarda_rutas_literales():
    indice = vault_arch.funciones_de_sistema_del_repo()
    assert indice["vault_io"]["tool_spec_path"] == "tool-spec.json"
    assert all(s != "*" for funcs in indice.values() for s in funcs.values())


def test_el_caso_medido_tool_spec_tiene_dueno_y_escritor_visible():
    fuente = (ROOT / "scripts" / "vault_manifest.py").read_text(encoding="utf-8")
    assert "spec_file = tool_spec_path()" in fuente
    assert "atomic_write_json(spec_file, spec)" in fuente
    # Dueño = único escritor (criterio de la deuda #3): el que lo escribe.
    assert vault_arch.duenos_de_sistema()["tool-spec.json"] == "meta_toolkit"
    assert "vault_manifest" in vault_arch.CONTEXTS["meta_toolkit"]["modulos"]
    vistas = {e["path"] for e in vault_arch.escrituras_de_sistema()
              if e["module"] == "vault_manifest"}
    assert "tool-spec.json" in vistas
