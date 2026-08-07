"""Un puerto que nadie implementa es una frontera imaginaria.

`CONTEXTS[ctx]["puertos"]` era una lista de nombres que solo se imprimía en
`docs/ARQUITECTURA.md`. Al comprobarlos por primera vez, **22 de los 30 no
existían**: eran los términos del lenguaje ubicuo —`escribir_nota`,
`crear_backup`, `subgrafo`— escritos donde iba la API, mientras la API real se
llamaba `vault_write`, `vault_backup`, `vault_subgraph`. El refactor de v40.0
dibujó los bordes; esto es lo que faltaba para que uno pudiera romperse.

`puertos` pasa a ser `nombre_ubicuo → "modulo:simbolo"`. Se conserva el nombre
del dominio —es la mitad del valor del registro— y se ata al símbolo que lo
implementa.
"""

import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_arch as arch  # noqa: E402

PUERTOS = [
    (ctx, puerto, destino)
    for ctx, datos in arch.CONTEXTS.items()
    for puerto, destino in sorted(datos["puertos"].items())
]


def test_hay_puertos_en_los_nueve_contextos():
    """33: los 30 originales más los tres registros canónicos de Gobernanza.

    `STATUS_VOCAB`, `DOMAIN_STATUS_VOCABS` y `cia_valores` son fuente única de
    verdad según `CLAUDE.md` y se entraban a leer por fuera de la superficie
    publicada — que es exactamente cómo nacieron las catorce copias de la
    severidad. Un dato canónico que no es puerto se acaba copiando.
    """
    assert len(PUERTOS) == 33
    assert {c for c, _, _ in PUERTOS} == set(arch.CONTEXTS)


@pytest.mark.parametrize("ctx,puerto,destino", PUERTOS, ids=lambda v: str(v))
def test_cada_puerto_apunta_a_un_simbolo_que_existe(ctx, puerto, destino):
    modulo, _, simbolo = destino.partition(":")
    assert simbolo, f"{ctx}.{puerto}: falta el símbolo"
    assert modulo in arch.CONTEXTS[ctx]["modulos"], (
        f"{ctx}.{puerto} publica `{modulo}`, que no es suyo — un puerto que "
        "delega en otro contexto no es una frontera, es una fuga"
    )
    simbolos = arch._simbolos_de_nivel_superior(modulo)
    assert simbolos is not None, modulo
    assert simbolo in simbolos or "*" in simbolos, destino


def test_el_check_no_reporta_puertos_rotos():
    """La deuda se saldó al declarar la puerta; no hay baseline que la tape."""
    assert arch.puertos_rotos() == []
    assert arch.check(strict=True)["broken_ports"] == []


def test_la_puerta_muerde_de_verdad(monkeypatch):
    """Sin esto, el test anterior solo dice que la función devuelve `[]`."""
    inventado = dict(arch.CONTEXTS)
    inventado["kernel"] = dict(
        arch.CONTEXTS["kernel"],
        puertos={"fantasma": "vault_io:no_existe_este_simbolo"},
    )
    monkeypatch.setattr(arch, "CONTEXTS", inventado)

    rotos = arch.puertos_rotos()
    assert [r["port"] for r in rotos] == ["fantasma"]
    assert "no define" in rotos[0]["reason"]
    assert arch.check()["ok"] is False


def test_un_puerto_prestado_de_otro_contexto_tambien_falla(monkeypatch):
    """El caso sutil: el símbolo existe, pero no en este contexto."""
    inventado = dict(arch.CONTEXTS)
    inventado["durabilidad"] = dict(
        arch.CONTEXTS["durabilidad"], puertos={"ajeno": "vault_io:get_vault_root"}
    )
    monkeypatch.setattr(arch, "CONTEXTS", inventado)

    rotos = arch.puertos_rotos()
    assert len(rotos) == 1 and "no es un módulo" in rotos[0]["reason"]


def test_el_lector_de_simbolos_no_importa_los_modulos():
    """Por qué va por AST: varios módulos resuelven el vault al importarse.

    Un guard que necesita un vault montado para decir si una frontera existe
    deja de ser un guard y pasa a ser otra dependencia (AP-49 por la puerta de
    atrás).
    """
    fuente = Path(arch.__file__).read_text(encoding="utf-8")
    cuerpo = fuente.split("def _simbolos_de_nivel_superior")[1].split("\ndef ")[0]
    assert "ast.parse" in cuerpo
    assert "import_module" not in cuerpo and "__import__" not in cuerpo


def test_un_puerto_perezoso_pep562_se_reconoce():
    """`vault_compact_contracts.GROUPS` ya no se define al importar.

    Se resuelve por `__getattr__` para que `set_vault_root()` pueda cambiarlo.
    El AST no lo ve, y una puerta que lo diera por roto empujaría a deshacer
    justo la corrección de AP-49 que se acaba de hacer.
    """
    simbolos = arch._simbolos_de_nivel_superior("vault_compact_contracts")
    assert "__getattr__" in simbolos and "*" in simbolos


def test_el_blueprint_publica_el_destino_no_solo_el_nombre():
    plano = arch.blueprint()
    assert "`escribir_nota` → `vault_write:vault_write`" in plano


# ── Y por dónde se cruza, no solo hacia dónde ────────────────────────────────

def test_hay_deuda_de_cruces_fuera_de_puerto_y_esta_congelada():
    """`cruces()` decía a qué contexto; esto dice por qué símbolo.

    49 imports entran a un contexto por un símbolo que su registro no publica.
    Se congelan porque exigir cero el primer día haría nacer la puerta en rojo,
    y una puerta en rojo se desactiva. La baseline solo puede encoger.
    """
    resultado = arch.check(strict=True)
    assert resultado["off_port_total"] > 0
    assert resultado["new_off_port_crossings"] == []
    assert resultado["settled_off_port_crossings"] == []


def test_el_kernel_queda_fuera_de_la_regla_a_proposito():
    """Es shared kernel: existe para que todos dependan de él.

    Si contara, 343 de los 392 hallazgos serían ruido y enterrarían los 49 que
    sí son fronteras cruzadas por detrás.
    """
    assert not [x for x in arch.cruces_fuera_de_puerto() if x["to_context"] == "kernel"]


def test_lo_que_entra_por_un_puerto_no_se_reporta():
    """El nombre ubicuo y el símbolo valen los dos: quien importa usa el símbolo."""
    publica = arch._superficie_publica("gobernanza")
    assert "auditar" in publica and "vault_audit" in publica
    assert not [
        x for x in arch.cruces_fuera_de_puerto()
        if x["symbol"].endswith(".NORM_CATALOG")
    ]


def test_un_cruce_nuevo_fuera_de_puerto_rompe_la_puerta(monkeypatch):
    monkeypatch.setattr(
        arch, "_leer_baseline", lambda: {"crossings": [], "off_port_crossings": []}
    )
    resultado = arch.check()
    assert resultado["new_off_port_crossings"], "la puerta no mide nada"
    assert resultado["ok"] is False
