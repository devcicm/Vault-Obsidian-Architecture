"""El seguimiento de la re-auditoría del vault: superficie de entorno.

La nota `19_Audits/environment-surface-re-measured-...` del vault (2026-11-09,
otro agente) remidió la superficie de entorno y encontró tres cosas. Este
módulo fija las que son **defectos del producto**, ya corregidos:

1. **Una credencial leída sin declarar.** `scripts/vault_token_service.py`
   leía `VAULT_TOKEN_SERVICE_TOKEN` por indireccion
   (`ENV_TOKEN = "..."` + `os.environ.get(ENV_TOKEN)`): el guard de lecturas
   sin declarar —que solo veía literales— no la veía. Ahora la variable está
   **declarada en el registro** y se lee **por su dueño** (`leer()`).
2. **El guard tenía un punto ciego de clase.** Con una indireccion de un
   salto (una constante que guarda el nombre), el guard no veía la lectura.
   Ahora la resuelve: `os.environ.get(ENV_TOKEN)` se lee como lo que es.
3. **La convención de nombres del registro, sin declarar.** Una variable con
   prefijo distinto de `VAULT_` (`VOAS_MERMAID_ORACLE`) rompía el
   invariante más barato de un registro —«prefijo implica pertenencia»— sin
   que nadie lo declarara. Renombrarla rompería a quien la usa, así que la
   excepción se **declara con su motivo**.

Y una cuarta, que es del **guard**, no del producto: el guard debe seguir
viendo lo que ve (una lectura por indirección se denuncia).
"""

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"

from vault.kernel import entorno  # noqa: E402


# ─── 1. La credencial del servicio de tokens está declarada ─────────────────


def test_la_credencial_del_servicio_de_tokens_esta_declarada():
    """SP-04: la variable que exige el servicio local de tokens, en el registro."""
    assert "VAULT_TOKEN_SERVICE_TOKEN" in entorno.VARIABLES
    variable = entorno.VARIABLES["VAULT_TOKEN_SERVICE_TOKEN"]
    assert variable.contexto, variable
    assert variable.default == "", "el default de una credencial es vacío"
    assert "00_System/token-usage" in variable.proposito, variable


def test_el_servicio_de_tokens_la_lee_por_su_dueno():
    """No por `os.environ.get`: por el registro, que es quien lo declara.

    Se mira el **código**, no el texto: el comentario que explica el
    arreglo menciona el patrón viejo, y un guard que leyera prosa
    denunciaría su propia explicación. Y se lee por el **módulo** (su
    fuente va con `inspect`), no por una ruta escrita a mano (m250).
    """
    import inspect

    import vault_token_service

    arbol = ast.parse(inspect.getsource(vault_token_service))
    lecturas_directas = [
        n for n in ast.walk(arbol)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "get"
        and isinstance(n.func.value, ast.Attribute)
        and n.func.value.attr == "environ"
    ]
    assert not lecturas_directas, (
        "la credencial se sigue leyendo del entorno sin pasar por el registro")
    por_dueno = [n for n in ast.walk(arbol)
                 if isinstance(n, ast.Call)
                 and getattr(n.func, "id", "") == "leer_entorno"]
    assert por_dueno, "la credencial no se lee por el dueño"


# ─── 2. El guard resuelve la indireccion de un salto ────────────────────────


def test_el_guard_denuncia_una_lectura_por_indireccion():
    """El punto ciego de clase: un nombre detrás de una constante.

    Se reproduce el caso real con un módulo de prueba: una constante que
    guarda el nombre y una lectura por esa constante. El guard tiene que
    denunciarla, porque si no, cualquier lectura se puede esconder detrás de
    un literal (la misma clase que BUG-009/010 con las vallas de código).
    """
    import vault_arch

    modulo = "modulo_de_prueba_indireccion"
    fuente = (
        'ENV_SECRETO = "VAULT_VARIABLE_NO_DECLARADA"\n'
        'import os\n'
        'def leer():\n'
        '    return os.environ.get(ENV_SECRETO, "")\n'
    )
    arbol = ast.parse(fuente)
    constantes = vault_arch._constantes_de_nombre(arbol)
    assert constantes == {"ENV_SECRETO": "VAULT_VARIABLE_NO_DECLARADA"}, constantes

    nombres = [vault_arch._nombre_de_variable_leida(nodo, constantes)
               for nodo in ast.walk(arbol)]
    assert "VAULT_VARIABLE_NO_DECLARADA" in nombres, nombres


def test_el_guard_sigue_viendo_la_lectura_literal():
    """Lo que ya veía, lo sigue viendo."""
    import vault_arch

    arbol = ast.parse('import os\nx = os.environ.get("VAULT_LITERAL", "")\n')
    nombres = [vault_arch._nombre_de_variable_leida(nodo, {})
               for nodo in ast.walk(arbol)]
    assert "VAULT_LITERAL" in nombres, nombres


# ─── 3. La convención de nombres, declarada ─────────────────────────────────


def test_toda_variable_del_registro_respeta_la_convencion_o_esta_declarada():
    """«Prefijo implica pertenencia» es el invariante; si se rompe, se declara."""
    patron = re.compile(r"^VAULT_[A-Z0-9_]+$")
    fuera = entorno.NOMBRES_FUERA_DEL_PREFIJO
    sin_declarar = [nombre for nombre in entorno.VARIABLES
                    if not patron.match(nombre) and nombre not in fuera]
    assert not sin_declarar, (
        f"variables fuera del prefijo y sin declaracion: {sin_declarar}")
    # Y toda excepcion tiene su motivo escrito: una lista sin razon es una
    # lista que nadie puede revisar.
    for nombre, motivo in fuera.items():
        assert nombre in entorno.VARIABLES, nombre
        assert len(motivo.strip()) > 40, f"{nombre} sin motivo escrito"


def test_la_excepcion_declarada_es_la_conocida():
    """La costura medida: una variable con prefijo ajeno, y solo una."""
    assert list(entorno.NOMBRES_FUERA_DEL_PREFIJO) == ["VOAS_MERMAID_ORACLE"]
    assert "VOAS_MERMAID_ORACLE" in entorno.VARIABLES


# ─── 4. El registro no tiene cifras escritas a mano ─────────────────────────


def test_el_docstring_del_registro_no_afirma_una_cifra_viva():
    """«Catorce variables» era historia; escrita en presente, era una cifra
    viva equivocada (AP-47)."""
    texto = (REPO_ROOT / "vault" / "kernel" / "entorno.py").read_text(encoding="utf-8")
    cabecera = texto.split('"""', 2)[1]
    assert "Catorce variables leídas" not in cabecera, (
        "el docstring afirma una cifra que ya no es la del registro")
    assert "Hasta v40.x" in cabecera, "la historia debe quedar marcada como tal"
