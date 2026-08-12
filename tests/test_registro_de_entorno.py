"""Catorce variables de entorno, once módulos, catorce defaults escritos a mano.

Ninguna tenía guard y solo seis aparecían documentadas, así que saber qué
configura el estándar exigía leer los once ficheros. Dos ya habían divergido:
`VAULT_VOICE` se comparaba contra `"verbose"` en un módulo y contra `"0"` con
default `"1"` en otro, y el servidor MCP declaraba dos que Python no conocía.

Es AP-05 sobre configuración —la misma decisión tomada en cada punto de uso—
y se corrige igual que todo lo demás aquí: registro canónico primero
(`scripts/vault_entorno.py`), lectores derivados después, guard que falla si
aparece una lectura sin entrada (`vault_arch --check`).

Vive en `scripts/` y no en el paquete `vault/` porque un módulo de `scripts/`
tiene que seguir funcionando **copiado suelto** —así se sincronizan los repos
consumidores, y así lo comprueba `test_vault_containment`, que copia solo
`vault_io.py` a un repo vacío—. Colgarlo de `vault.kernel` lo rompía con un
`ModuleNotFoundError`.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_arch as arch  # noqa: E402
from vault_entorno import VARIABLES, leer, tabla  # noqa: E402


def test_toda_variable_declara_las_cinco_cosas():
    """Nombre, tipo, default, contexto que la lee y para qué sirve."""
    for nombre, var in VARIABLES.items():
        assert var.nombre == nombre
        assert var.tipo and var.proposito.strip()
        assert var.contexto in arch.CONTEXTS, f"{nombre}: contexto inexistente"


def test_ninguna_lectura_del_repo_queda_sin_declarar():
    """El guard, sobre el repo real. Es lo que convierte el registro en norma."""
    assert arch.lecturas_de_entorno_sin_registro() == []


def test_el_guard_muerde(tmp_path, monkeypatch):
    """Sin esto, el test anterior solo dice que la función devuelve `[]`."""
    modulo = tmp_path / "vault_inventado.py"
    modulo.write_text(
        'import os\nx = os.environ.get("VAULT_NO_DECLARADA", "1")\n',
        encoding="utf-8",
    )
    # v40.9: el alcance de los guards ya no es un glob por sitio sino
    # `vault_arch.arboles_medidos()`. Se redirige el alcance, no el
    # directorio, para que el guard vea exactamente el módulo de prueba.
    monkeypatch.setattr(arch, "arboles_medidos",
                        lambda: sorted(tmp_path.glob("vault_*.py")))
    hallazgos = arch.lecturas_de_entorno_sin_registro()
    assert hallazgos == [
        {"module": "vault_inventado", "variable": "VAULT_NO_DECLARADA"}
    ]


def test_el_guard_ve_tambien_el_acceso_por_indice(tmp_path, monkeypatch):
    """`os.environ["X"]` configura igual que `os.environ.get("X")`."""
    (tmp_path / "vault_indexado.py").write_text(
        'import os\nx = os.environ["VAULT_OTRA"]\n', encoding="utf-8"
    )
    # v40.9: el alcance de los guards ya no es un glob por sitio sino
    # `vault_arch.arboles_medidos()`. Se redirige el alcance, no el
    # directorio, para que el guard vea exactamente el módulo de prueba.
    monkeypatch.setattr(arch, "arboles_medidos",
                        lambda: sorted(tmp_path.glob("vault_*.py")))
    assert arch.lecturas_de_entorno_sin_registro()[0]["variable"] == "VAULT_OTRA"


def test_ningun_modulo_conserva_su_propio_default():
    """El síntoma concreto: un `os.environ.get(..., "30")` suelto por ahí.

    Se excluyen las dos copias legítimas del entorno completo —pasar el entorno
    a un subproceso no es leer configuración— y se enumeran a propósito, porque
    una lista corta es auditable y una heurística no.
    """
    sospechosos = []
    for ruta in sorted((REPO_ROOT / "scripts").glob("vault_*.py")):
        if ruta.stem in arch._COPIAS_DE_ENTORNO_LEGITIMAS:
            continue
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            # Por AST y no por texto: el propio guard menciona `os.environ` en
            # sus docstrings, y un test que lea líneas acusaría al detector.
            if arch._nombre_de_variable_leida(nodo) is not None:
                sospechosos.append(f"{ruta.name}:{nodo.lineno}")
    assert not sospechosos, sospechosos


# ── Conversión ───────────────────────────────────────────────────────────────

def test_el_default_llega_sin_convertir_y_ya_tipado(monkeypatch):
    monkeypatch.delenv("VAULT_TOOL_TIMEOUT", raising=False)
    assert leer("VAULT_TOOL_TIMEOUT") == 60


def test_un_entero_del_entorno_llega_como_entero(monkeypatch):
    monkeypatch.setenv("VAULT_TOOL_TIMEOUT", "5")
    assert leer("VAULT_TOOL_TIMEOUT") == 5


def test_un_entero_mal_escrito_cae_al_default_en_vez_de_tumbar_el_proceso(
    monkeypatch,
):
    """`VAULT_TOOL_TIMEOUT=mucho` reventaba con un ValueError sin decir de dónde.

    La configuración mal escrita no debe impedir que la tool arranque.
    """
    monkeypatch.setenv("VAULT_TOOL_TIMEOUT", "mucho")
    assert leer("VAULT_TOOL_TIMEOUT") == 60


@pytest.mark.parametrize("valor,esperado", [("1", True), ("0", False), ("si", False)])
def test_la_bandera_solo_se_enciende_con_uno(monkeypatch, valor, esperado):
    monkeypatch.setenv("VAULT_FSYNC", valor)
    assert leer("VAULT_FSYNC") is esperado


@pytest.mark.parametrize("valor", ["1", "0", "cualquiera"])
def test_las_dos_heredadas_se_encienden_con_solo_estar(monkeypatch, valor):
    """`VAULT_STRICT_ROOT=0` activaba el modo estricto, y se conserva.

    Cambiarlo aquí alteraría en silencio dos guards. Se documenta la asimetría
    en vez de unificarla a escondidas.
    """
    monkeypatch.setenv("VAULT_STRICT_ROOT", valor)
    assert leer("VAULT_STRICT_ROOT") is True


def test_una_variable_no_declarada_falla_en_vez_de_devolver_none():
    """Devolver `None` la dejaría pasar en silencio (AP-37)."""
    with pytest.raises(KeyError, match="VARIABLES"):
        leer("VAULT_QUE_NO_EXISTE")


# ── Comportamiento observable, sin cambios ───────────────────────────────────

def test_vault_root_sigue_mandando_sobre_la_autodeteccion(tmp_path):
    """La costura más usada del estándar, verificada de extremo a extremo."""
    salida = subprocess.run(
        [
            sys.executable, "-c",
            "import sys; sys.path.insert(0,'scripts'); import vault_io;"
            " print(vault_io.get_vault_root(), vault_io.vault_root_origin())",
        ],
        env=dict(os.environ, VAULT_ROOT=str(tmp_path), PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO_ROOT),
    )
    assert str(tmp_path) in salida.stdout, salida.stderr[-400:]
    assert "env" in salida.stdout


def test_la_tabla_derivada_sirve_al_mjs():
    """`--env` existe para que el servidor deje de inventarse sus variables."""
    filas = {f["name"]: f for f in tabla()}
    assert len(filas) == len(VARIABLES)
    # Las cuatro del `.mjs`, incluidas las dos que solo él leía.
    for nombre in ("VAULT_ROOT", "VAULT_SCAN_ROOTS", "VAULT_MCP_LOG",
                   "VAULT_TOOL_TIMEOUT"):
        assert nombre in filas, nombre


def test_el_arch_publica_el_recuento():
    resultado = arch.check()
    assert resultado["env_vars_declared"] == len(VARIABLES)
    assert resultado["undeclared_env_reads"] == []


# ── El artefacto derivado que consume el servidor MCP ────────────────────────

def test_la_tabla_del_mjs_esta_al_dia():
    """AP-47 aplicado a la configuración: el JSON refleja el registro."""
    assert arch.tabla_de_entorno_desfasada() is False
    assert arch.check()["mjs_env_table_stale"] is False


def test_la_puerta_del_desfase_muerde(tmp_path, monkeypatch):
    monkeypatch.setattr(arch, "TABLA_ENTORNO_MJS", tmp_path / "no-existe.json")
    assert arch.tabla_de_entorno_desfasada() is True
    assert arch.check()["ok"] is False


def test_el_mjs_ya_no_declara_sus_propios_defaults():
    """Cuatro variables declaradas por su cuenta; una ya divergía.

    `VAULT_MCP_LOG` estaba en el registro como fichero de log con default
    `None` y el servidor la usa como **nivel** con default `"info"`. El defecto
    era del registro, no del `.mjs`, y salió al contrastarlo contra el único
    código que la lee — AP-44 dentro del módulo que existe para que las dos
    mitades no divergieran.
    """
    fuente = (REPO_ROOT / "mcp" / "nodejs" / "vault-mcp-server.mjs").read_text(
        encoding="utf-8"
    )
    assert 'process.env.VAULT_MCP_LOG || "info"' not in fuente
    assert 'envDefault("VAULT_MCP_LOG")' in fuente
    assert 'envDefault("VAULT_TOOL_TIMEOUT")' in fuente


def test_el_mjs_falla_ruidosamente_si_falta_la_tabla():
    """Un fallback silencioso devolvería justo los defaults que esto quita."""
    fuente = (REPO_ROOT / "mcp" / "nodejs" / "vault-mcp-server.mjs").read_text(
        encoding="utf-8"
    )
    bloque = fuente.split("const ENV_DEFAULTS")[1].split("let VAULT_ROOT")[0]
    assert "catch" not in bloque
    assert "throw new Error" in bloque


def test_el_nivel_de_log_del_mjs_coincide_con_el_registro():
    """La divergencia concreta, medida contra el consumidor y no contra el nombre."""
    import json as _json

    filas = _json.loads(
        (REPO_ROOT / "mcp" / "nodejs" / "env-table.json").read_text(encoding="utf-8")
    )["variables"]
    log = next(f for f in filas if f["name"] == "VAULT_MCP_LOG")
    assert log["default"] == "info" and log["type"] == "texto"
