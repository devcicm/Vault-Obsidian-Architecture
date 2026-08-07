"""`critical | high | medium | low`, escrito a mano en catorce ficheros.

Cuatro veces como `choices=` de argparse, diez como constante de módulo, y con
dos variantes que nadie declaraba como tales: `vault_log_error` añade `info`,
`vault_norms` añade `N/A` para los patterns. Nada ataba las copias entre sí. El
día que se midieron coincidían todas; la que se quedara atrás rechazaría un
valor válido o aceptaría uno inventado, y ningún test lo notaría.

Es AP-05 sobre vocabulario, y el precedente ya estaba en el repo:
`vault_norms.DOMAIN_STATUS_VOCABS` resolvió esto mismo para `status` y se quedó
ahí solo. Lo que `vault_vocabulario.py` añade es el **dueño**: cada vocabulario
declara el contexto acotado que manda sobre él.

El criterio de aceptación de este cambio es que ninguna lista cambie de valores
ni de orden — varias son ordinales y el índice **es** el nivel.
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_arch as arch  # noqa: E402
import vault_vocabulario as voc  # noqa: E402


def test_todo_vocabulario_declara_un_dueno_que_existe():
    """Sin dueño, «quién manda sobre estos valores» no tiene respuesta."""
    assert arch.vocabularios_sin_dueno() == []
    for nombre, v in voc.VOCABULARIOS.items():
        assert v.nombre == nombre
        assert v.proposito.strip()
        assert v.contexto in arch.CONTEXTS


def test_el_dueno_es_guard_no_convencion(monkeypatch):
    """Sin esto, el test anterior solo dice que la función devuelve `[]`."""
    inventado = dict(voc.VOCABULARIOS)
    inventado["fantasma"] = voc.Vocabulario(
        nombre="fantasma", contexto="contexto_que_no_existe",
        proposito="x", valores=("a",),
    )
    monkeypatch.setattr(voc, "VOCABULARIOS", inventado)
    assert arch.vocabularios_sin_dueno() == [
        {"vocabulary": "fantasma", "context": "contexto_que_no_existe"}
    ]


def test_ningun_modulo_conserva_su_copia():
    """El guard, sobre el repo real. Las catorce se saldaron al declararlas."""
    assert arch.copias_de_vocabulario() == []


def test_el_guard_de_copias_muerde(tmp_path, monkeypatch):
    modulo = tmp_path / "vault_copion.py"
    modulo.write_text(
        'SEVERITIES = ["critical", "high", "medium", "low"]\n', encoding="utf-8"
    )
    monkeypatch.setattr(arch, "SCRIPTS_DIR", tmp_path)
    hallazgos = arch.copias_de_vocabulario()
    assert hallazgos == [
        {"module": "vault_copion", "line": 1, "vocabulary": "severidad"}
    ]


def test_una_copia_desordenada_tambien_es_una_copia(tmp_path, monkeypatch):
    """El caso que un `==` literal dejaría pasar: la misma decisión, otro orden."""
    (tmp_path / "vault_listillo.py").write_text(
        'X = ("low", "critical", "medium", "high")\n', encoding="utf-8"
    )
    monkeypatch.setattr(arch, "SCRIPTS_DIR", tmp_path)
    assert arch.copias_de_vocabulario()[0]["vocabulary"] == "severidad"


def test_el_propio_registro_no_se_acusa_a_si_mismo():
    """En `vault_vocabulario` y en sus fuentes, el literal es la declaración."""
    assert not [
        x for x in arch.copias_de_vocabulario()
        if x["module"] in ("vault_vocabulario", "vault_norms", "vault_fundamentals")
    ]


# ── Los derivados, resueltos al llamarse ─────────────────────────────────────

@pytest.mark.parametrize("nombre", sorted(voc.VOCABULARIOS))
def test_todo_vocabulario_resuelve_a_valores(nombre):
    assert voc.valores(nombre), nombre


def test_un_derivado_no_guarda_su_lista():
    """Guardarla sería la copia número quince, dentro del registro que la prohíbe."""
    for nombre, v in voc.VOCABULARIOS.items():
        if v.derivado_de:
            assert v.valores == (), nombre


def test_el_registro_no_importa_el_dominio_al_importarse():
    """AP-49: `vault_fundamentals` monta el vault; atarlo aquí lo heredaría todo."""
    fuente = Path(voc.__file__).read_text(encoding="utf-8")
    preambulo = fuente.split("VOCABULARIOS")[0]
    assert "vault_fundamentals" not in preambulo.replace("`vault_fundamentals`", "")
    assert "import vault_norms" not in preambulo


def test_los_cia_salen_del_registro_de_fundamentos():
    from vault_fundamentals import cia_valores

    for campo in ("cia_integrity", "cia_availability", "cia_sensitivity"):
        assert set(voc.valores(campo)) == cia_valores(campo)
    #: La asimetría es real y del registro, no un descuido.
    assert "critical" not in voc.valores("cia_availability")


def test_un_vocabulario_no_declarado_falla_en_vez_de_devolver_vacio():
    """Devolver `()` dejaría pasar un `choices=[]` que no acepta nada (AP-37)."""
    with pytest.raises(KeyError, match="VOCABULARIOS"):
        voc.valores("severidad_inventada")


# ── Las ampliaciones, declaradas en vez de disimuladas ───────────────────────

@pytest.mark.parametrize("ampliacion,extra", [
    ("severidad_con_info", "info"),
    ("severidad_con_na", "N/A"),
])
def test_una_ampliacion_contiene_la_escala_base_y_lo_dice(ampliacion, extra):
    base = voc.valores("severidad")
    valores = voc.valores(ampliacion)
    assert valores[: len(base)] == base
    assert extra in valores
    assert voc.VOCABULARIOS[ampliacion].amplia == "severidad"


# ── Criterio de aceptación: ni un valor ni un orden cambiado ─────────────────

@pytest.mark.parametrize("modulo,constante,esperado", [
    # Ordinal: el índice **es** el nivel de impacto, por eso va al revés.
    ("vault_ai_decision", "IMPACT_LEVELS", ["low", "medium", "high", "critical"]),
    ("vault_bug_save", "SEVERITIES", ["critical", "high", "medium", "low"]),
    ("vault_bug_save", "BUG_STATES",
     ["open", "confirmed", "in_fix", "fixed", "wont_fix", "duplicate"]),
    ("vault_delta", "MIN_RISK_ORDER", ["critical", "high", "medium", "low"]),
    ("vault_log_error", "SEVERITIES",
     ["critical", "high", "medium", "low", "info"]),
    ("vault_pattern_save", "PATTERN_STATUSES",
     ["planificado", "en_progreso", "implementado", "deprecado", "refactoring"]),
    ("vault_test_save", "STATUSES",
     ["not_run", "pass", "fail", "blocked", "skip"]),
])
def test_ninguna_constante_publicada_cambio(modulo, constante, esperado):
    import importlib

    m = importlib.import_module(modulo)
    assert list(getattr(m, constante)) == esperado


@pytest.mark.parametrize("tool", [
    "vault_impact", "vault_propagate", "vault_quality_check",
    "vault_incident_save", "vault_security_scan", "vault_compact_contracts",
    "vault_standard_upgrade",
])
def test_la_cli_sigue_arrancando(tool):
    """Los siete donde el cambio vive dentro de una función.

    Ahí un import olvidado no revienta al importar el módulo: revienta al
    ejecutar la tool, que es donde nadie lo estaba mirando.
    """
    r = subprocess.run(
        [sys.executable, f"scripts/{tool}.py", "--help"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO_ROOT),
    )
    assert r.returncode == 0, r.stderr[-400:]


def test_los_choices_de_argparse_salen_del_registro():
    """Una tupla en `choices=` imprime `('a', 'b')` en el `--help`. Lista."""
    assert isinstance(voc.opciones("severidad"), list)


# ── Superficie publicada ─────────────────────────────────────────────────────

def test_gobernanza_publica_sus_registros_canonicos():
    """Un dato canónico que no es puerto es un dato que se acaba copiando.

    Los tres que `CLAUDE.md` declara fuente única de verdad se entraban a leer
    por fuera de la superficie publicada — que es exactamente cómo nacieron las
    catorce copias de la severidad.
    """
    puertos = arch.CONTEXTS["gobernanza"]["puertos"]
    assert puertos["vocabulario_de_estado"] == "vault_norms:STATUS_VOCAB"
    assert puertos["valores_cia"] == "vault_fundamentals:cia_valores"
    assert arch.puertos_rotos() == []


def test_el_cruce_del_registro_al_dominio_esta_declarado():
    """El kernel no depende del dominio; cuando lo hace, lo dice y por qué.

    Mudarlo a Gobernanza no eliminaría el cruce, lo movería: `vault_log_error`
    es kernel y consume la escala de severidad.
    """
    for destino in ("vault_norms", "vault_fundamentals"):
        clave = ("vault_vocabulario", destino)
        assert clave in arch.GANCHOS_DEL_KERNEL
        assert arch.GANCHOS_DEL_KERNEL[clave].strip()
    assert arch.dependencias_del_kernel() == []


def test_el_arch_publica_el_recuento():
    r = arch.check()
    assert r["vocabularies_declared"] == len(voc.VOCABULARIOS)
    assert r["vocabulary_copies"] == []
    assert r["vocabularies_without_owner"] == []


def test_la_tabla_derivada_se_puede_publicar():
    filas = {f["name"]: f for f in voc.tabla()}
    assert len(filas) == len(voc.VOCABULARIOS)
    assert filas["severidad"]["context"] == "gobernanza"
    assert filas["status"]["derived_from"] == "vault_norms:STATUS_VOCAB"
    assert filas["severidad_con_na"]["extends"] == "severidad"
