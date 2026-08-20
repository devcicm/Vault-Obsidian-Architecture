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


def test_hay_puertos_en_los_contextos_que_publican_api():
    """56 en v40.8: los 33 anteriores más los 23 que el código ya usaba.

    Los 33 salieron de los 30 originales más los tres registros canónicos de
    Gobernanza. Los 23 nuevos no amplían ninguna API: son símbolos públicos que
    otro contexto **ya** importaba y que el registro no nombraba. Doce `*_save`
    entrando por `status_frontmatter_lines` no eran doce fugas; eran un puerto
    de gobernanza sin declarar, y la baseline de `off_port` los contaba como
    deuda porque el registro iba por detrás del código.

    Declararlos no relaja la medida: desde v40.8 un puerto no puede nombrar un
    símbolo privado, así que la única forma de que un `_x` deje de reportarse
    es promoverlo de verdad.
    """
    # +1 en v40.26: `auditar_normas`. Se declaró antes de partir `vault_norms`
    # porque el motor de audit era el único cruce entrante fuera de puerto, y
    # mezclarlo con el troceado habría hecho ilegible cuál movió la cifra.
    # +1 en v40.30: `NATIVE_JS_TOOLS`, en `meta_toolkit`. No es un puerto nuevo
    # por conveniencia para que la puerta pase: `cli/registry.py` lo consume
    # desde siempre y su comentario ya nombraba a `vault_mcp_catalog` como
    # dueño. Lo que faltaba era declararlo, y mientras `cli/` no tuvo contexto
    # no había dónde notar que el cruce existía.
    assert len(PUERTOS) == 60
    # `cli` queda fuera a propósito: es un adaptador de transporte y **nadie
    # importa de `cli/`**, así que no publica API. Exigirle un puerto obligaría
    # a inventar uno, que es justo lo contrario de lo que mide este fichero.
    # Su contexto declara `puertos: {}` y `prohibe: decidir`.
    SIN_API = {"cli"}
    assert {c for c, _, _ in PUERTOS} == set(arch.CONTEXTS) - SIN_API
    for ctx in SIN_API:
        assert arch.CONTEXTS[ctx]["puertos"] == {}, (
            f"{ctx} ya publica API: sácalo de SIN_API en vez de dejar el "
            "hueco sin verificar")


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


def test_un_puerto_no_puede_nombrar_un_simbolo_privado(monkeypatch):
    """El agujero que habría convertido este cambio en un blanqueo.

    Declarar un puerto encoge la baseline de `off_port` sin tocar una línea de
    dominio. Sin esta comprobación bastaba con escribir
    `vault_norms:_NORM_BY_CODE` en el registro para que un cruce por detrás
    dejara de reportarse: la medida se relaja y el número dice que mejoró. Es
    AP-44 —verificar con el criterio del consumidor— aplicado al propio guard.

    Puerta dura y sin baseline, como los otros motivos de `puertos_rotos()`:
    se midió cero al declararla porque los cuatro privados que cruzaban
    frontera se promovieron a público en la misma tanda.
    """
    inventado = dict(arch.CONTEXTS)
    inventado["gobernanza"] = dict(
        arch.CONTEXTS["gobernanza"], puertos={"colado": "vault_norms:_NORM_BY_CODE"}
    )
    monkeypatch.setattr(arch, "CONTEXTS", inventado)

    rotos = arch.puertos_rotos()
    assert len(rotos) == 1, rotos
    assert "privado" in rotos[0]["reason"], rotos[0]
    assert arch.check()["ok"] is False


def test_ningun_simbolo_privado_cruza_una_frontera():
    """Siete en total: cuatro promovidos en v40.8 y tres que no se veían.

    Los de v40.8 entraban por `from x import y`: `vault_code_tag` leía
    `vault_norms._NORM_BY_CODE`, `vault_io` leía `vault_tags._parse_frontmatter_tags`
    y `vault_onboard` leía `vault_write._deduce_type_from_folder` y
    `vault_norms._cuerpo_sin_marcadores`.

    **Este test pasaba en v40.8 por el motivo equivocado.** El detector filtraba
    por `ast.ImportFrom`, así que `import vault_tags as _tags` seguido de
    `_tags._raiz()` era invisible: la afirmación era universal y la medida no
    podía observar lo que la habría falsificado — AP-44 dentro del guard. Al
    mirar también `ast.Import` (v40.9) aparecieron tres más:
    `vault_norms` leía `vault_tags._raiz` y `vault_tags._load_ledger`, y
    `vault_sanacion` leía `vault_reindex._notas_en_disco`. Promovidos a
    `raiz`, `load_ledger` y `notas_indexables`, con el nombre viejo conservado
    como alias (no-derogación).
    """
    privados = [
        x for x in arch.cruces_fuera_de_puerto()
        if x["symbol"].rpartition(".")[2].startswith("_")
    ]
    assert privados == [], privados


def test_el_detector_ve_los_dos_estilos_de_import():
    """Lo que faltaba para que el test de arriba afirme algo.

    Sin esto, «ningún privado cruza» se puede volver a cumplir mañana por
    estrechar la medida en vez de arreglar el código, que es exactamente lo que
    pasó entre v40.8 y v40.9.
    """
    fuera = arch.cruces_fuera_de_puerto()
    # `from vault_smoke import SIN_SMOKE` en vault_norms — estilo ImportFrom.
    assert [x for x in fuera if x["symbol"] == "vault_smoke.SIN_SMOKE"]
    # `import vault_tags as _tags` + `_tags.normalize_tag` — estilo Import, que
    # es el que el detector no veía.
    assert [x for x in fuera if x["symbol"] == "vault_tags.normalize_tag"]


def test_un_acceso_por_import_liso_se_reporta(tmp_path, monkeypatch):
    """La puerta muerde sobre `import X`, no solo sobre `from X import y`."""
    fichero = tmp_path / "vault_falso.py"
    fichero.write_text(
        "import vault_norms\n\ndef f():\n    return vault_norms.NO_ES_UN_PUERTO\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(arch, "arboles_medidos", lambda: [fichero])
    monkeypatch.setattr(
        arch,
        "_mapa_modulos",
        lambda: {"vault_falso": "meta_toolkit", "vault_norms": "gobernanza"},
    )
    hallazgos = arch.cruces_fuera_de_puerto()
    assert [h["symbol"] for h in hallazgos] == ["vault_norms.NO_ES_UN_PUERTO"]


def test_el_total_de_cruces_se_cuenta_como_su_baseline():
    """Dos cifras contiguas que no se podían restar, en la medida hermana.

    `off_port` se arregló en v40.8 y `crossings` se quedó publicando sitios
    junto a una baseline de claves: 60 contra 58 sin una sola deuda nueva. Quien
    leyera la diferencia como una regresión buscaría un cruce que no existe.
    """
    resultado = arch.check()
    assert resultado["crossings_total"] == len(
        {arch._clave(c) for c in arch.cruces()}
    )
    assert resultado["crossings_sites"] == len(arch.cruces())


def test_el_lector_de_simbolos_no_importa_los_modulos():
    """Por qué va por AST: varios módulos resuelven el vault al importarse.

    Un guard que necesita un vault montado para decir si una frontera existe
    deja de ser un guard y pasa a ser otra dependencia (AP-49 por la puerta de
    atrás).
    """
    fuente = Path(arch.__file__).read_text(encoding="utf-8")
    cuerpo = fuente.split("def _simbolos_de_nivel_superior")[1].split("\ndef ")[0]
    # Va por AST (hoy vía el helper cacheado `_ast_de`, que lo envuelve): el
    # requisito es no importar los módulos, no qué función llama a `ast.parse`.
    assert "ast.parse" in cuerpo or "_ast_de(" in cuerpo
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

def test_la_deuda_de_cruces_fuera_de_puerto_esta_saldada():
    """`cruces()` decía a qué contexto; esto dice por qué símbolo.

    Nació con 49 congelados —exigir cero el primer día habría hecho nacer la
    puerta en rojo, y una puerta en rojo se desactiva—. En v40.8 la baseline
    llegó a cero, pero por dos vías distintas que conviene no confundir: ~40
    eran puertos que el registro no nombraba y 5 eran cruces reales que hubo
    que arreglar promoviendo el símbolo. Solo la segunda mitad era deuda.

    En v40.9 vuelve a 13, y conviene no leerlo como una regresión: no apareció
    ningún cruce nuevo, apareció la mitad de la medida que faltaba. El detector
    solo miraba `from x import y`; al mirar también `import x` salieron 13
    claves que llevaban ahí desde siempre, tres de ellas por símbolo privado —
    ésas sí eran deuda, y se saldaron promoviendo. Las otras diez entran
    congeladas, que es lo que se hace con la deuda que se descubre, no con la
    que se estrena.
    """
    resultado = arch.check(strict=True)
    assert resultado["off_port_total"] == resultado["off_port_baseline"]
    assert resultado["new_off_port_crossings"] == []
    assert resultado["settled_off_port_crossings"] == []


def test_el_total_de_off_port_se_cuenta_como_la_baseline():
    """Dos cifras contiguas que no se podían restar.

    El envelope publicaba `off_port_total` por sitios y `off_port_baseline` por
    claves `módulo -> símbolo`, así que daban 48 y 47 sin que hubiera deuda
    nueva: `vault_io` importa `vault_section_index` dos veces en el mismo
    fichero y las dos colapsan en una clave. Quien leyera la diferencia como
    una regresión se habría puesto a buscar un cruce que no existía.
    """
    resultado = arch.check()
    fuera = arch.cruces_fuera_de_puerto()
    claves = {arch._clave_fuera_de_puerto(x) for x in fuera}
    assert resultado["off_port_total"] == len(claves)
    assert resultado["off_port_sites"] == len(fuera)


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
    """Que la deuda sea cero no puede confundirse con que no se mida nada.

    Hasta v40.8 bastaba con vaciar la baseline para que reaparecieran los 47
    congelados. Con la baseline saldada eso ya no prueba nada: hay que provocar
    un cruce. Se estrecha la superficie de gobernanza a un solo puerto —los
    doce `*_save` que entran por `status_frontmatter_lines` pasan a estar
    fuera— y la puerta debe verlos.
    """
    inventado = dict(arch.CONTEXTS)
    inventado["gobernanza"] = dict(
        arch.CONTEXTS["gobernanza"], puertos={"auditar": "vault_audit:vault_audit"}
    )
    monkeypatch.setattr(arch, "CONTEXTS", inventado)
    monkeypatch.setattr(
        arch, "_leer_baseline", lambda: {"crossings": [], "off_port_crossings": []}
    )
    resultado = arch.check()
    assert resultado["new_off_port_crossings"], "la puerta no mide nada"
    assert resultado["ok"] is False
