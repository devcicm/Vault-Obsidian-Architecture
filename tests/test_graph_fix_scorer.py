"""El scorer que decide a qué nota se redirige un enlace roto.

Encontrado sanando el vault de BuilderX (318 notas, 161 enlaces rotos, 47
targets únicos). `--classify` recomendaba, para el target
`02observability/antipatterns/apbarenumbercssunits`, la nota
`css-design-system-gap-analysis` con 0.730 — y dejaba la obviamente correcta,
`numbers-without-css-units`, en 0.727. Con `--auto-fix-safe` (umbral 0.75) eso
reescribe enlaces hacia notas arbitrarias: la tool cuya única función es reparar
el grafo era la que lo corrompía.

Tres defectos que se reforzaban:

  1. `_seq_ratio` era `sum(1 for ch in a if ch in b)`: contaba caracteres
     presentes en CUALQUIER posición, sin orden ni multiplicidad. No mide
     parecido, mide solapamiento de alfabeto — y dos slugs en minúsculas
     comparten casi todo el alfabeto. Además premiaba la longitud: más
     caracteres distintos en el candidato → más aciertos → más score, así que
     el ranking tendía a la nota de título más largo del vault.
  2. `_jaccard_tokens` devolvía 0.000 en TODAS las comparaciones: el target
     llega colapsado sin separadores y el candidato los conserva, así que la
     intersección de tokens era siempre vacía. El 20% del score que llevaba la
     semántica no pesaba nada.
  3. Con (1), un par sin ninguna relación puntuaba 0.608, por encima de
     `threshold_partial=0.60`: entraba el vault entero como candidato.

Los tres tienen el mismo síntoma visible — la recomendación es plausible — y por
eso ningún test los detectó: nada comparaba el orden del ranking contra una
respuesta conocida.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_graph_fix as g  # noqa: E402


def _score(target: str, candidato: str) -> float:
    """La misma combinación que usa `_classify_broken`."""
    return 0.8 * g._seq_ratio(target, candidato) + 0.2 * g._jaccard_tokens(
        target, candidato
    )


# ─── El caso real de BuilderX ────────────────────────────────────────────────

CASO_BUILDERX = "02observability/antipatterns/apbarenumbercssunits"
CORRECTO = "numbers-without-css-units"
SENUELOS = [
    "gapanalysisreferencecssvsbuilderxtoken/componentsystem",
    "adr-remediacion-de-tech-debt-2026-06-06-6-hallazgos-p0p1p2",
    "ap-bx-compile-overwrites-functional-html",
    "2026-05-31-viewer-js-invalid-or-unexpected-token-bloquea-cone",
]


@pytest.mark.parametrize("senuelo", SENUELOS)
def test_el_candidato_correcto_gana_a_los_senuelos(senuelo):
    """El fallo original: el señuelo ganaba por 0.003."""
    bueno, malo = _score(CASO_BUILDERX, CORRECTO), _score(CASO_BUILDERX, senuelo)
    assert bueno > malo, (
        f"{CORRECTO} ({bueno:.3f}) debe ganar a {senuelo} ({malo:.3f}); "
        f"si no, --auto-fix-safe redirige el enlace a la nota equivocada"
    )


def test_la_ventaja_del_correcto_no_es_un_empate_tecnico():
    """0.003 de margen no es una decisión, es ruido."""
    bueno = _score(CASO_BUILDERX, CORRECTO)
    mejor_senuelo = max(_score(CASO_BUILDERX, s) for s in SENUELOS)
    assert bueno - mejor_senuelo > 0.15, (
        f"margen {bueno - mejor_senuelo:.3f}: demasiado estrecho para decidir "
        f"una reescritura automática"
    )


# ─── _seq_ratio: orden y longitud ────────────────────────────────────────────


def test_seq_ratio_no_premia_la_longitud_del_candidato():
    """El defecto estructural: alargar el candidato subía el score."""
    target = "backup-restore"
    corto = g._seq_ratio(target, "backup-restore-runbook")
    largo = g._seq_ratio(
        target, "backup-restore-runbook-con-un-titulo-larguisimo-y-redundante"
    )
    assert corto > largo, (
        "un candidato más largo y menos parecido no puede puntuar más alto"
    )


def test_seq_ratio_es_sensible_al_orden():
    """Solapamiento de alfabeto daba 1.0 a un anagrama."""
    assert g._seq_ratio("abc-def", "fed-cba") < 0.9


def _umbral_partial() -> float:
    """El umbral real de la firma, no una copia escrita a mano en el test."""
    import inspect

    return inspect.signature(g._classify_broken).parameters["threshold_partial"].default


def test_un_par_sin_relacion_queda_bajo_el_umbral_de_candidato():
    """Antes 0.608, con threshold_partial=0.60: entraba el vault entero."""
    s = _score(CASO_BUILDERX, "runbook-restauracion-de-backup")
    assert s < _umbral_partial(), (
        f"{s:.3f} superaría threshold_partial y sería candidato"
    )


def test_una_coincidencia_recuperable_sigue_siendo_candidata():
    """El riesgo del arreglo: bajar la escala y tirar los buenos a no_match.

    `apbarenumbercssunits` y `numbers-without-css-units` son la misma nota
    renombrada. No llega a auto-aplicarse — no debe —, pero tiene que aparecer
    en el cajón de revisión.
    """
    s = _score(CASO_BUILDERX, CORRECTO)
    assert s >= _umbral_partial(), (
        f"{s:.3f} < {_umbral_partial()}: un enlace recuperable acabaría en no_match"
    )


def test_seq_ratio_identidad_y_vacio():
    assert g._seq_ratio("a-b", "a-b") == 1.0
    assert g._seq_ratio("", "x") == 0.0
    assert g._seq_ratio("x", "") == 0.0


def test_el_prefijo_de_carpeta_no_castiga_al_stem():
    """El target trae ruta, el candidato es solo stem: no puede penalizar."""
    con_ruta = g._seq_ratio("07knowledge/concepts/token-dictionary", "token-dictionary")
    assert con_ruta > 0.9


# ─── _jaccard_tokens: normalización simétrica ────────────────────────────────


def test_el_mismo_slug_en_los_dos_formatos_no_puede_dar_cero():
    """El defecto: target colapsado vs candidato con guiones → 0.000 siempre."""
    j = g._jaccard_tokens("runbookrestauraciondebackup", "runbook-restauracion-de-backup")
    assert j > 0.5, f"{j:.3f}: son el mismo slug escrito de dos formas"


def test_jaccard_aporta_algo_en_el_caso_real():
    """Si el término vale 0 en todas las comparaciones, no es un término."""
    assert g._jaccard_tokens(CASO_BUILDERX, CORRECTO) > 0


def test_jaccard_identidad_y_disjuntos():
    assert g._jaccard_tokens("a-b-c", "a-b-c") == 1.0
    assert g._jaccard_tokens("alpha-bravo", "charlie-delta") == 0.0


def test_los_tokens_se_normalizan_igual_en_los_dos_lados():
    assert g._tokens("Foo_Bar-baz.qux") == ["foo", "bar", "baz", "qux"]
    assert g._tokens("02_Observability/errors") == ["02", "observability", "errors"]


# ─── El writer: lo que se ESCRIBE tiene que resolver ─────────────────────────


def test_el_enlace_reparado_se_escribe_con_el_nombre_real_del_fichero():
    """El defecto más caro: la reparación producía enlaces rotos nuevos.

    `decision["stem"]` es la clave de `active_stems`, que está normalizada
    (colapsada, sin separadores). Escribirla dejaba
    `[[adrmodeloaccioncanonicoydeudacomponentes]]` apuntando al fichero
    `adr-modelo-accion-canonico-y-deuda-componentes.md`. Obsidian no resuelve
    eso — pero la propia tool sí, porque al comprobar normaliza los dos lados.
    Se autoengañaba: reportaba 17 enlaces reparados y el recuento real de rotos
    subía. En BuilderX pasó de 160 a 166.
    """
    decision = {
        "action": "fix",
        "stem": "adrmodeloaccioncanonicoydeudacomponentes",
        "path": "03_Decisions/adr-modelo-accion-canonico-y-deuda-componentes.md",
    }
    escrito = g._destino_escribible(decision, "adrmodeloaccioncanonico")
    assert escrito == "adr-modelo-accion-canonico-y-deuda-componentes"


def test_el_destino_escrito_nunca_es_una_forma_colapsada():
    """Un destino sin separadores contra un fichero que sí los tiene es el bug."""
    casos = [
        ("02_Observability/antipatterns/ap-validator-advisory-not-blocking.md",
         "apvalidatoradvisorynotblocking"),
        ("07_Knowledge/concepts/builderx/numbers-without-css-units.md",
         "numberswithoutcssunits"),
    ]
    for path, stem_normalizado in casos:
        escrito = g._destino_escribible({"path": path, "stem": stem_normalizado}, "x")
        assert escrito == Path(path).stem
        assert "-" in escrito


def test_sin_ruta_no_se_inventa_un_destino_colapsado():
    """Ante la duda, dejar el enlace como estaba antes que escribir algo que no resuelve."""
    assert g._destino_escribible({"stem": "algocolapsado"}, "original-target") == (
        "original-target"
    )


def test_el_writer_produce_un_enlace_que_el_propio_grafo_resuelve(tmp_path):
    """End-to-end: reparar y volver a medir no puede empeorar el recuento."""
    from vault_io import normalize_stem

    destino = "03_Decisions/adr-modelo-accion-canonico-y-deuda-componentes.md"
    escrito = g._destino_escribible(
        {"path": destino, "stem": normalize_stem(Path(destino).stem)}, "viejo"
    )
    # La condición que Obsidian aplica: el texto del wikilink es el nombre del
    # fichero, tal cual. No una normalización de él.
    assert escrito == Path(destino).stem
    # Y la que aplica el grafo: siguen coincidiendo tras normalizar.
    assert normalize_stem(escrito) == normalize_stem(Path(destino).stem)


# ─── El invariante que faltaba ───────────────────────────────────────────────


# ─── La zona muerta: descartado por parecerse demasiado ──────────────────────


def _clasificar(target: str, stems: list[str]) -> dict:
    activos = {s: [f"02_Observability/antipatterns/{s}.md"] for s in stems}
    return g._classify_broken(target, activos, {})


def test_un_candidato_casi_perfecto_no_se_descarta_por_serlo():
    """El filtro era `score >= partial AND score < exact`.

    Un candidato que puntuaba por encima de `threshold_exact` caía en una zona
    muerta y no entraba en la lista. En BuilderX,
    `apvalidatoradvisorynotblocking` daba 0.864 contra su propia nota y se
    descartaba, así que ganaba un ADR distinto con 0.615: dos enlaces rotos
    acababan apuntando cada uno a la nota del otro.
    """
    r = _clasificar(
        "apvalidatoradvisorynotblocking",
        ["ap-validator-advisory-not-blocking", "adr-validator-advisory-vs-blocking"],
    )
    assert r["recommended_stem"] == "ap-validator-advisory-not-blocking"
    assert r["category"] == "exact_candidate"


def test_la_categoria_exact_candidate_es_alcanzable_por_fuzzy():
    """Con el tope puesto, ningún fuzzy podía llegar a >= threshold_exact.

    La categoría existía en el código y era inalcanzable por esa vía: se
    declaraba una confianza que la tool nunca podía emitir.
    """
    r = _clasificar("bug20260611tokennumericcoercion", ["bug-2026-06-11-token-numeric-coercion"])
    assert r["category"] == "exact_candidate", (
        "una coincidencia casi literal debe clasificarse como exact_candidate"
    )


def test_el_stem_propio_gana_aunque_haya_un_vecino_muy_parecido():
    r = _clasificar(
        "20260611tokenwidthparsedasstring",
        [
            "2026-06-11-token-width-parsed-as-string",
            "2026-06-11-token-resolver-not-validated",
            "2026-06-11-token-numeric-coercion",
        ],
    )
    assert r["recommended_stem"] == "2026-06-11-token-width-parsed-as-string"


def test_la_seccion_del_enlace_roto_desempata():
    """Dos notas homónimas en secciones distintas: manda la que pedía el enlace."""
    activos = {
        "validator-advisory": [
            "03_Decisions/validator-advisory.md",
            "02_Observability/antipatterns/validator-advisory.md",
        ],
    }
    r = g._classify_broken("02observability/antipatterns/validatoradvisory", activos, {})
    assert r["candidates"][0]["path"].startswith("02_Observability/")


def test_el_bono_de_seccion_no_fabrica_coincidencias():
    """Estar en la carpeta correcta no convierte a una nota en la correcta."""
    activos = {"algo-sin-relacion": ["02_Observability/antipatterns/algo-sin-relacion.md"]}
    r = g._classify_broken(
        "02observability/antipatterns/apbarenumbercssunits", activos, {}
    )
    assert r["category"] == "no_match", (
        f"el bono de sección subió un candidato sin parecido: {r['candidates']}"
    )


def test_ninguna_nota_del_vault_gana_a_su_propio_stem():
    """Un stem debe recomendarse a sí mismo por encima de cualquier otro.

    Es el invariante que hubiera atrapado los tres defectos de golpe: si el
    scorer no reconoce una nota como su mejor coincidencia, no puede decidir
    reescrituras.
    """
    stems = [
        "numbers-without-css-units",
        "runbook-restauracion-de-backup",
        "ap-bx-compile-overwrites-functional-html",
        "dsl-v2-token-dictionary",
        "adr-2026-06-11-validator-advisory-vs-blocking",
    ]
    for propio in stems:
        colapsado = propio.replace("-", "")
        ganador = max(stems, key=lambda s: _score(colapsado, s))
        assert ganador == propio, (
            f"'{colapsado}' se resolvió a '{ganador}' en vez de a '{propio}'"
        )
