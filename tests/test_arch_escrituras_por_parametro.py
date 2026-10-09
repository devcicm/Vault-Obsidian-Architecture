"""El límite declarado de la guarda de `00_System/` (aviso 6 de la tanda v41.3).

`vault_arch.escrituras_de_sistema_en` decide la subruta mirando la llamada que
escribe, dentro de un solo módulo y sin análisis de flujo. Dos formas se le
escapan, y la entrada `fronteras_de_escritura_por_contexto` del plano las
declara en vez de dar la frontera por cubierta entera:

- la ruta **llega por parámetro**: el escritor recibe `ruta` y quien la
  construye no escribe;
- la ruta **la calcula otro módulo**: la subruta no es decidible y colapsa a
  `"*"`, que la guarda no reporta porque es «crear la carpeta».

El caso medido el 2026-10-09 es real: `vault_manifest --bootstrap` escribe
`00_System/tool-spec.json` con `atomic_write_json(tool_spec_path())`, la ruta
sale de `vault_io`, y esa subruta no tiene dueño en `duenos_de_sistema`.

Estos tests no piden que el límite exista: lo fijan. El día que la guarda siga
la ruta, fallarán, y quien lo consiga tendrá que actualizar la declaración en
vez de dejar una prosa que ya no es verdad.
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


def test_limite_declarado_la_ruta_de_otro_modulo_colapsa_a_la_carpeta():
    fuente = '''
def bootstrap():
    spec_file = tool_spec_path()
    atomic_write_json(spec_file, {})
'''
    # Se reconoce la escritura en `00_System/`, pero no qué subruta.
    assert _subrutas(fuente) == ["*"]


def test_el_caso_medido_tool_spec_no_tiene_dueno_ni_escritor_visible():
    fuente = (ROOT / "scripts" / "vault_manifest.py").read_text(encoding="utf-8")
    assert "spec_file = tool_spec_path()" in fuente
    assert "atomic_write_json(spec_file, spec)" in fuente
    assert "tool-spec.json" not in vault_arch.duenos_de_sistema()
    vistas = {e["path"] for e in vault_arch.escrituras_de_sistema()
              if e["module"] == "vault_manifest"}
    assert "tool-spec.json" not in vistas
