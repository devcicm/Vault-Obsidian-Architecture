"""El plan de sanación mide, y lo que no pudo medir lo dice.

`docs/MODO-AGENTICO-SANACION.md` describe 12 fases; hasta ahora se ejecutaban
leyendo el documento, y la decisión de qué fase aplicaba no quedaba escrita en
ningún sitio. Lo que estos tests fijan es lo que hace que un plan valga: que
**discrimine** —si todas las fases aplican siempre, no mide nada—, que
`unknown` no se confunda con `clean`, y que la tool no escriba jamás.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import vault_sanacion as san  # noqa: E402


@pytest.fixture
def plan_sandbox():
    return san.plan_de_sanacion(REPO_ROOT / "vault-sandbox")


def test_las_doce_fases_estan_y_en_orden(plan_sandbox):
    assert [f["phase"] for f in plan_sandbox["phases"]] == list(range(1, 13))


def test_cada_fase_trae_evidencia(plan_sandbox):
    """Un veredicto sin evidencia es una opinión: no dirige ninguna decisión."""
    for fase in plan_sandbox["phases"]:
        assert fase["evidence"].strip(), f"fase {fase['phase']} sin evidencia"
        assert fase["verdict"] in {"applies", "clean", "unknown"}


def test_el_plan_discrimina(plan_sandbox):
    """Si todas las fases aplican siempre, la tool no está midiendo nada."""
    veredictos = {f["verdict"] for f in plan_sandbox["phases"]}
    assert "clean" in veredictos, (
        "ninguna fase salió limpia sobre vault-sandbox: el plan no discrimina"
    )
    assert "applies" in veredictos


def test_unknown_no_se_confunde_con_clean(plan_sandbox):
    """El fallo original: siete fases en `unknown` y el plan las daba por buenas.

    `issues.*` del audit son listas de hallazgos, no cifras. El primer intento
    exigía `int` y devolvía `None`, así que medio plan quedó ciego sin que nada
    fallara. `phases_unknown` existe para que eso no pueda volver a pasar en
    silencio: una fase que no se pudo medir es una fase que sigues debiendo.
    """
    unknown = {f["phase"] for f in plan_sandbox["phases"]
               if f["verdict"] == "unknown"}
    assert set(plan_sandbox["phases_unknown"]) == unknown
    assert unknown.isdisjoint(set(plan_sandbox["phases_apply"]))


def test_la_fase_1_siempre_aplica(plan_sandbox):
    """Ninguna medida confirma que copiaste el vault antes de tocarlo."""
    fase1 = plan_sandbox["phases"][0]
    assert fase1["verdict"] == "applies"
    assert "copia" in fase1["evidence"].lower()


def test_cada_fase_nombra_quien_escribe(plan_sandbox):
    """La tool propone; el que escribe es otro, y tiene que estar nombrado."""
    for fase in plan_sandbox["phases"]:
        if fase["phase"] == 1:
            continue  # copiar el vault no es trabajo de ninguna tool
        assert fase["tool"], f"fase {fase['phase']} sin tool que la ejecute"


def test_el_envelope_declara_que_no_escribe(plan_sandbox):
    assert plan_sandbox["writes"] is False
    assert plan_sandbox["ok"] is True


def test_no_escribe_nada(tmp_path):
    """El contrato duro, comprobado por comportamiento y no por promesa."""
    import vault_init
    import vault_io

    vault_io.set_vault_root(tmp_path)
    vault_init.vault_init()
    antes = {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*") if p.is_file()}

    san.plan_de_sanacion(tmp_path)

    despues = {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*") if p.is_file()}
    assert set(antes) == set(despues), (
        f"aparecieron o desaparecieron ficheros: "
        f"{set(antes) ^ set(despues)}"
    )
    tocados = [p.name for p in antes if antes[p] != despues[p]]
    assert not tocados, f"vault_sanacion modificó {tocados}"


def test_la_tipografia_deliberada_no_cuenta_como_dano():
    """Contar em-dash como mojibake daba 106 notas «afectadas» de 111.

    La fase 5 es encoding roto, no normalización tipográfica: una fase que
    siempre aplica es una fase que nadie lee.
    """
    assert "smart_quotes" not in san._ENCODING_DANINO
    assert "unicode_dash" not in san._ENCODING_DANINO
    assert "nfd_char" not in san._ENCODING_DANINO
    assert "invisible_char" in san._ENCODING_DANINO
    assert "bom" in san._ENCODING_DANINO


def test_las_fases_salen_del_documento_que_las_define():
    """El registro es `docs/MODO-AGENTICO-SANACION.md`; aquí no se reinventa.

    Se contrasta el título de cada fase contra la tabla del documento: si
    alguien renumera allí y no aquí, el plan dirige hacia otra cosa con el
    nombre correcto, que es peor que fallar.
    """
    # El documento marca las tools con backticks dentro del propio título
    # ("pasada de `vault_norms --audit`"); se quitan para comparar la frase,
    # no su formato.
    doc = (REPO_ROOT / "docs" / "MODO-AGENTICO-SANACION.md").read_text(
        encoding="utf-8"
    ).replace("`", "")
    for numero, titulo, _tool, _decision in san.FASES:
        assert titulo in doc, (
            f"la fase {numero} '{titulo}' no aparece en MODO-AGENTICO-SANACION.md"
        )


def test_una_fase_fuera_de_rango_no_inventa_nada(plan_sandbox):
    assert not [f for f in plan_sandbox["phases"] if f["phase"] > 12]
