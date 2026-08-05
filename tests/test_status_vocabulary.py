"""AP-38 — el vocabulario de `status` se impone al escribir, no al auditar.

Lo que estos tests protegen no es una convención de estilo. Un censo sobre 17
vaults reales (2.929 notas) encontró 54 valores distintos de `status` con CN-03
auditándolo desde v38: el audit existía y nadie lo ejecutaba. Y el valor no
canónico más frecuente lo escribía una tool del propio catálogo.

Por eso hay dos guards distintos aquí: uno sobre el comportamiento (normalizar y
rechazar) y otro sobre el código fuente (que no reaparezca una emisión directa).
El segundo es el que importa a largo plazo: el primero se cumple hoy, el segundo
impide que la próxima tool nazca fuera del registro.
"""

import ast
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))

from vault_norms import (  # noqa: E402
    DOMAIN_STATUS_VOCABS,
    STATUS_SYNONYMS,
    STATUS_TRANSITIONS,
    STATUS_VOCAB,
    normalize_status,
    split_domain_status,
    status_frontmatter_lines,
)

SCRIPTS = sorted((RAIZ / "scripts").glob("vault_*.py"))


# ── El registro es coherente consigo mismo ────────────────────────────────────

def test_todo_sinonimo_apunta_a_un_valor_canonico():
    rotos = {k: v for k, v in STATUS_SYNONYMS.items() if v not in STATUS_VOCAB}
    assert not rotos, f"sinónimos que apuntan fuera de STATUS_VOCAB: {rotos}"


def test_ningun_sinonimo_pisa_un_valor_canonico():
    """Un canónico que además es clave de sinónimo tiene dos lecturas posibles."""
    colision = set(STATUS_SYNONYMS) & STATUS_VOCAB
    assert not colision, f"claves que son a la vez canónicas y sinónimo: {colision}"


def test_las_transiciones_cubren_el_vocabulario_completo():
    assert set(STATUS_TRANSITIONS) == STATUS_VOCAB
    destinos = {d for ds in STATUS_TRANSITIONS.values() for d in ds}
    assert destinos <= STATUS_VOCAB, f"transiciones a estados inexistentes: {destinos - STATUS_VOCAB}"


def test_todo_estado_es_alcanzable_o_es_un_estado_inicial():
    """Un estado al que no llega ninguna transición y que nadie asigna es basura."""
    alcanzables = {d for ds in STATUS_TRANSITIONS.values() for d in ds}
    iniciales = {"planned", "draft", "stub", "template"}
    huerfanos = STATUS_VOCAB - alcanzables - iniciales
    assert not huerfanos, f"estados inalcanzables: {huerfanos}"


def test_todo_vocabulario_de_dominio_aterriza_en_el_canonico():
    rotos = [
        (tool, valor, destino)
        for tool, (_campo, mapa) in DOMAIN_STATUS_VOCABS.items()
        for valor, destino in mapa.items()
        if destino not in STATUS_VOCAB
    ]
    assert not rotos, f"mapeos de dominio fuera de STATUS_VOCAB: {rotos}"


def test_cada_dominio_usa_un_campo_propio_y_distinto():
    """Dos dominios compartiendo campo reintroducen el problema en otro nombre."""
    campos = [campo for campo, _ in DOMAIN_STATUS_VOCABS.values()]
    assert len(campos) == len(set(campos)), f"campos de dominio repetidos: {campos}"
    assert "status" not in campos


# ── Normalización ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "crudo,esperado",
    [
        # los cinco valores no canónicos más frecuentes del censo real
        ("implementado", "implemented"),
        ("active", "in-progress"),
        ("activo", "in-progress"),
        ("accepted", "approved"),
        ("fixed", "verified"),
        # el valor ya canónico pasa intacto
        ("draft", "draft"),
        # variantes de formato que no son valores nuevos
        ("In Progress", "in-progress"),
        ("in_progress", "in-progress"),
    ],
)
def test_normaliza_los_valores_observados_en_vaults_reales(crudo, esperado):
    assert normalize_status(crudo)[0] == esperado


@pytest.mark.parametrize(
    "crudo,estado,nota",
    [
        ("resuelto (v0.58)", "verified", "v0.58"),
        ("aceptada (corregida 2026-05-11)", "approved", "corregida 2026-05-11"),
        ("mayormente_corregido", "verified", "corrección parcial"),
    ],
)
def test_lo_que_no_era_estado_se_conserva_en_vez_de_perderse(crudo, estado, nota):
    """No-derogación aplicada al dato: normalizar no puede ser destruir."""
    canonico, resto, _ = normalize_status(crudo)
    assert (canonico, resto) == (estado, nota)


def test_lo_indecidible_se_rechaza_y_no_se_adivina():
    """`1-fixed-6-pending` es un informe de progreso, no un estado.

    Inventarle un canónico sería peor que rechazarlo: el error dejaría de verse
    y se heredaría en cada nota que lo copiase.
    """
    canonico, resto, regla = normalize_status("1-fixed-6-pending")
    assert canonico is None and regla == "unknown"
    assert resto == "1-fixed-6-pending", "el valor original debe sobrevivir al rechazo"


def test_el_censo_completo_se_normaliza_salvo_lo_que_no_es_un_estado():
    """Cobertura medida contra los 54 valores que aparecieron en el parque."""
    observados = [
        "implementado", "active", "activo", "accepted", "fixed", "planificado",
        "en_progreso", "deprecado", "resuelto", "corregido", "completado",
        "en_desarrollo", "open", "investigating", "pass", "not_run", "partial",
        "no-bug", "offline", "stub", "draft", "implemented", "verified",
    ]
    sin_resolver = [v for v in observados if normalize_status(v)[0] is None]
    assert not sin_resolver, f"del censo quedan sin normalizar: {sin_resolver}"


# ── Los dos ejes no se mezclan ────────────────────────────────────────────────

def test_el_valor_de_dominio_se_conserva_intacto_junto_al_canonico():
    lineas = status_frontmatter_lines("vault_test_save", "pass")
    assert lineas == ["status: verified", "test_result: pass"]


def test_status_va_siempre_primero():
    """El orden del frontmatter no puede depender de la tool que lo escribió."""
    for tool, (_campo, mapa) in DOMAIN_STATUS_VOCABS.items():
        for valor in mapa:
            assert status_frontmatter_lines(tool, valor)[0].startswith("status: ")


def test_una_tool_sin_vocabulario_propio_cae_en_el_canonico():
    assert split_domain_status("vault_write", "fixed") == ("verified", None, None)


# ── vault_write corrige antes de escribir ─────────────────────────────────────

def test_vault_write_normaliza_en_la_escritura():
    from vault_write import generate_frontmatter

    fm = generate_frontmatter("T", meta={"status": "implementado"})
    assert "status: implemented" in fm
    assert "implementado" not in fm


def test_vault_write_emite_status_en_posicion_fija():
    """Antes, un `status` que venía en `meta` salía detrás del CIA y de `agent`.

    Mismo campo, distinto sitio según por dónde entrase el dato — que es
    justamente lo que hace que un formato deje de serlo.
    """
    from vault_write import generate_frontmatter

    con_meta = generate_frontmatter("T", meta={"status": "draft"}).splitlines()
    por_defecto = generate_frontmatter("T").splitlines()
    assert con_meta.index("status: draft") == por_defecto.index("status: draft")


def test_vault_write_rechaza_lo_que_no_puede_derivar():
    from vault_write import generate_frontmatter

    with pytest.raises(ValueError, match="vocabulario canónico"):
        generate_frontmatter("T", meta={"status": "1-fixed-6-pending"})


def test_vault_write_conserva_el_matiz_en_status_note():
    from vault_write import generate_frontmatter

    fm = generate_frontmatter("T", meta={"status": "resuelto (v0.58)"})
    assert "status: verified" in fm and "status_note: v0.58" in fm


# ── Guard de código fuente: que no reaparezca una emisión directa ─────────────

_EMISION_DIRECTA = re.compile(r'["\']status:\s*\{')


def _lineas_con_emision_directa(script):
    fuente = script.read_text(encoding="utf-8", errors="replace")
    return [
        (n, linea.strip())
        for n, linea in enumerate(fuente.splitlines(), 1)
        if _EMISION_DIRECTA.search(linea) and "status_frontmatter_lines" not in linea
    ]


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_ninguna_tool_emite_status_sin_pasar_por_el_registro(script):
    """El guard que faltaba en v38.

    CN-03 auditaba el vocabulario mientras nueve tools lo esquivaban escribiendo
    el campo a mano. Cualquier tool nueva que lo intente falla aquí, antes de
    llegar a un vault real.
    """
    # `vault_write` construye el frontmatter canónico y `vault_norms` es el
    # registro: son el punto de normalización, no un bypass de él.
    if script.name in {"vault_write.py", "vault_norms.py"}:
        return
    directas = _lineas_con_emision_directa(script)
    assert not directas, (
        f"{script.name} emite `status` sin pasar por status_frontmatter_lines(): "
        f"{directas}. Si la tool tiene vocabulario propio, decláralo en "
        f"DOMAIN_STATUS_VOCABS — no lo escribas a mano (AP-38)."
    )


def test_toda_tool_con_vocabulario_local_esta_declarada_en_el_registro():
    """Una lista de estados en el código que el registro no conoce vuelve a divergir."""
    sospechosas = {}
    for script in SCRIPTS:
        try:
            arbol = ast.parse(script.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Assign):
                continue
            nombres = [t.id for t in nodo.targets if isinstance(t, ast.Name)]
            if not any(re.search(r"STATUS|STATES", n) for n in nombres):
                continue
            if not isinstance(nodo.value, (ast.List, ast.Tuple)):
                continue
            valores = {
                e.value for e in nodo.value.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)
            }
            # Una lista cuyos valores ya son todos canónicos no es un
            # vocabulario en competencia: es un subconjunto del canónico, y
            # restringir el ciclo de vida por tipo de nota es legítimo.
            if valores and valores <= STATUS_VOCAB:
                continue
            if script.stem not in DOMAIN_STATUS_VOCABS:
                sospechosas[script.name] = nombres
    assert not sospechosas, (
        f"vocabularios de estado no declarados en DOMAIN_STATUS_VOCABS: {sospechosas}"
    )
