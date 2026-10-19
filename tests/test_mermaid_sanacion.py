from __future__ import annotations

r"""Sanación con oráculo (v41.13): el heal de AP-25 con el compilador de árbitro.

Ciclo del estándar: AP-25 ya tenía guard (`vault_diagram_save`) y audit
(esta tool); aquí se cierra con el heal. Los sanadores son mecánicos y
el criterio de aceptación NO es el regex: toda propuesta pasa por
`mermaid.parse` y solo se escribe la que aprueba. Medido contra los 6
bloques reales de un vault ajeno (SMART POS CR, 2026-10-19).

Un defecto doble (POS: `|false (default)|` en una línea, `Cedula(12)` en
otra) exige composiciones: la propuesta parcial de un solo sanador sigue
parseando mal y el compilador la rechaza. Eso está congelado aquí.
"""
import sys
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import vault_mermaid_check as vmc  # noqa: E402

# ============================================================================
# Fixtures: los 5 defectos reales del vault ajeno y la cura que los deja
# aprobados por el compilador (probeada con mermaid 12 core el 2026-10-19).
# ============================================================================

ROTO_A_CURA = {
    "label_sin_cerrar": ("corchete_abierto", "flowchart TD\n    A[Label] --> B[Label2]\n"),
    "edge_label_con_parentesis": (
        "edge_label_especial",
        'flowchart TD\n    DECIDE -->|"false (default)"| BTN[Mostrar]\n',
    ),
    "state_con_salto_literales": (
        "saltos_literales",
        "stateDiagram-v2\n    [*] --> Abierta: open\n",
    ),
    "er_comillas_fuera": (
        "er_etiqueta",
        'erDiagram\n    USER }o--|| TENANT : "pertenece a"\n',
    ),
    "br_paren_en_label": (
        "label_especial",
        'flowchart TD\n    A["gateway.py<br/>(httpx async)"] --> B\n',
    ),
}

ROTO_ORIGINAL = {
    "label_sin_cerrar": "flowchart TD\n    A[Label] --> B[Label2\n",
    "edge_label_con_parentesis": "flowchart TD\n    DECIDE -->|false (default)| BTN[Mostrar]\n",
    "state_con_salto_literales": "stateDiagram-v2\\n    [*] --> Abierta: open\\n",
    "er_comillas_fuera": 'erDiagram\n    USER }o--|| TENANT "pertenece a"\n',
    "br_paren_en_label": "flowchart TD\n    A[gateway.py<br/>(httpx async)] --> B\n",
}

# Dos defectos en un mismo bloque: la cura exige la COMPOSICIÓN de dos
# sanadores (la propuesta de cualquiera solo sigue parseando mal).
ROTO_DOBLE = "flowchart TD\n    A[paso uno (x)] -->|false (default)| B\n"
CURA_DOBLE = 'flowchart TD\n    A["paso uno (x)"] -->|"false (default)"| B\n'

# Un defecto que ningún sanador mecánico cubre: la línea suelta de un
# sequenceDiagram queda declarada, no maquillada.
ROTO_NO_SALVABLE = "sequenceDiagram\n    A ->> B: hola\n    esto no es nada\n"


# ============================================================================
# Unit: cada sanador transforma exacto (sin compilador).
# ============================================================================


@pytest.mark.parametrize("roto", sorted(ROTO_A_CURA))
def test_sanador_aplica_los_casos_reales(roto):
    """El sanador correcto para cada defecto real produce la cura exacta."""
    sanador, cura = ROTO_A_CURA[roto]
    fns = dict(vmc.SANADORES_MERMAID)
    assert fns[sanador](ROTO_ORIGINAL[roto]) == cura


def test_sanadores_devuelven_none_si_no_aplican():
    """Sin defecto de su clase, el sanador no toca nada (no propone)."""
    fns = dict(vmc.SANADORES_MERMAID)
    sano = "pie\n    title T\n    \"a\" : 40\n"
    for nombre, fn in fns.items():
        assert fn(sano) is None, f"{nombre} propuso algo sobre un diagrama sano"


def test_label_especial_no_encierra_comillas_ni_er():
    """Un label que ya tiene comillas no se re-encierra, y en `erDiagram`
    los corchetes son atributos de entidad — ahí el sanador no entra."""
    fns = dict(vmc.SANADORES_MERMAID)
    assert fns["label_especial"]('flowchart TD\n    A["ya bien (x)"] --> B\n') is None
    assert (
        fns["label_especial"]("erDiagram\n    CLIENTE {\n        string nombre\n    }\n")
        is None
    )


def test_composicion_aprueba_el_minimo_con_los_dos_sanadores():
    """`curar_bloques` con un verificador que solo aprueba el bloque COMPLETO
    (como el compilador real): la cura del doble defecto nombra los DOS
    sanadores, no uno."""
    parcial_edge = 'flowchart TD\n    A[paso uno (x)] -->|"false (default)"| B\n'
    parcial_label = 'flowchart TD\n    A["paso uno (x)"] -->|false (default)| B\n'
    usados = []

    def verificar(codigos):
        usados.append(list(codigos))
        return [c == CURA_DOBLE for c in codigos]

    sanados, no_salvables = vmc.curar_bloques({"b#0": ROTO_DOBLE}, verificar)
    assert no_salvables == []
    assert sanados["b#0"][0] == CURA_DOBLE
    assert set(sanados["b#0"][1]) == {"edge_label_especial", "label_especial"}
    # Las parciales también pasaron por el árbitro y fueron RECHAZADAS: la
    # composición no se saltó la verificación ninguna vez.
    planas = [c for lote in usados for c in lote]
    assert parcial_edge in planas and parcial_label in planas


def test_curar_declara_no_salvables_sin_simular():
    """Todo rechazado: `no_salvables` con el id declarado y NADA en sanados —
    el vacío del compilador no se interpreta como cura (AP-51)."""

    def verificar(codigos):
        return [False] * len(codigos)

    sanados, no_salvables = vmc.curar_bloques({"b#0": ROTO_NO_SALVABLE}, verificar)
    assert sanados == {}
    assert no_salvables == ["b#0"]


def test_curar_sobre_bloque_sano_no_propone():
    """Un bloque ya curado no genera propuestas (2ª pasada = 0 trabajo)."""

    def verificar(codigos):
        return [False] * len(codigos)  # ni se llama si no hay propuestas

    sanados, no_salvables = vmc.curar_bloques({"b#0": CURA_DOBLE}, verificar)
    assert sanados == {} and no_salvables == ["b#0"]


# ============================================================================
# sanar_bloques: guardia sin oráculo, escritura, idempotencia, dry-run.
# ============================================================================


def _diagnostico_con_roto(vault: Path, roto: str, tipo: str = "flowchart") -> dict:
    """El envelope que `scan_vault` devolvería para un vault con un roto."""
    return {
        "ok": False,
        "files_checked": 1,
        "files_with_diagrams": 1,
        "total_errors": 1,
        "oraculo": {
            "disponible": True,
            "parser": vmc._NOMBRE_ORACULO,
            "bloques_comprobados": 1,
            "helper": str(vmc._helper_oraculo()),
            "pack": str(vmc._pack_oraculo()),
            "motivo": None,
        },
        "results": [
            {
                "file": str(vault / "roto.md"),
                "valid": False,
                "blocks": [
                    {
                        "index": 0,
                        "type": tipo,
                        "valid": False,
                        "errors": [
                            {
                                "type": "parse_error",
                                "source": vmc._NOMBRE_ORACULO,
                                "message": "Parse error on line 1",
                                "suggestion": "s",
                                "line": 1,
                            }
                        ],
                    }
                ],
                "errors": [],
            }
        ],
    }


@pytest.fixture()
def vault_estandar(monkeypatch, tmp_path):
    """Un vault tmp con la raíz y el grafo controlados por el test.

    `refrescar_grafo` se sustituye: en test tiraría de la autodetección y
    metería una nota tmp_path en el grafo del vault-sandbox del repo.
    """
    vault = tmp_path / "mini-vault-sanacion"
    vault.mkdir()
    monkeypatch.setattr(vmc, "_raiz", lambda: vault)
    monkeypatch.setattr(vmc, "refrescar_grafo", lambda *a, **k: {})
    return vault


def _skip_si_no_oraculo():
    pack = vmc._pack_oraculo()
    if pack is None or vmc._helper_oraculo() is None or shutil.which("node") is None:
        pytest.skip(
            "oráculo no instalado (node + mermaid + jsdom): "
            "npm install mermaid jsdom en mcp/nodejs o VOAS_MERMAID_ORACLE"
        )


def test_sanar_sin_oraculo_no_escribe_nada(vault_estandar, monkeypatch):
    """Con rotos en el diagnóstico pero oráculo caído: ok False, motivo
    declarado y el archivo intacto — sin criterio no hay cura (AP-51)."""
    vault = vault_estandar
    nota = vault / "roto.md"
    contenido = "# x\n\n```mermaid\n" + ROTO_DOBLE + "```\n"
    nota.write_text(contenido, encoding="utf-8")
    d = _diagnostico_con_roto(vault, ROTO_DOBLE)
    d["oraculo"] = {**d["oraculo"], "disponible": False, "motivo": "node no está en PATH"}
    monkeypatch.setattr(vmc, "_pack_oraculo", lambda: None)
    sanacion = vmc.sanar_bloques(d)
    assert sanacion["ok"] is False
    assert "oráculo" in sanacion["motivo"]
    assert sanacion["escritos"] == []
    assert nota.read_text(encoding="utf-8") == contenido


def test_recorrida_punta_a_punta_sana_verifica_y_queda_idempotente(vault_estandar):
    """La recorrida completa de AP-25: scan → sanar → el bloque curado está
    en disco, el re-scan no ve parse_error, y una segunda pasada no hace
    nada (healed 0, clean). Con el compilador real, no simulado."""
    _skip_si_no_oraculo()
    vault = vault_estandar
    (vault / "roto.md").write_text(
        "# x\n\n```mermaid\n" + ROTO_DOBLE + "```\n",
        encoding="utf-8",
    )
    d = vmc.scan_vault(path=vault)
    assert d["oraculo"]["disponible"] is True
    sanacion = vmc.sanar_bloques(d)
    assert sanacion["ok"] is True, sanacion
    assert sanacion["healed"] == 1
    assert sanacion["no_salvables"] == []
    assert len(sanacion["escritos"]) == 1
    # La exactitud: el bloque en disco es la cura escrita por el compilador.
    en_disco = (vault / "roto.md").read_text(encoding="utf-8")
    assert "```mermaid\n" + CURA_DOBLE + "```" in en_disco
    # El re-diagnóstico confirma: cero parse_error tras la cura.
    d2 = vmc.scan_vault(path=vault)
    parse_errors = [
        e
        for r in d2["results"]
        for b in r["blocks"]
        for e in b["errors"]
        if e["type"] == "parse_error"
    ]
    assert parse_errors == []
    assert d2["ok"] is True
    # Idempotencia: segunda sanación no propone nada (healed 0, clean 1).
    sanacion2 = vmc.sanar_bloques(d2)
    assert sanacion2["ok"] is True
    assert sanacion2["healed"] == 0
    assert sanacion2.get("clean") == 1


def test_dry_run_reporta_sin_escribir(vault_estandar):
    """`dry_run=True`: la propuesta sale con su `code_curado`, `healed` NO
    cuenta (nada se escribió) y el archivo queda byte a byte igual."""
    _skip_si_no_oraculo()
    vault = vault_estandar
    nota = vault / "roto.md"
    contenido = "# x\n\n```mermaid\n" + ROTO_DOBLE + "```\n"
    nota.write_text(contenido, encoding="utf-8")
    d = vmc.scan_vault(path=vault)
    sanacion = vmc.sanar_bloques(d, dry_run=True)
    assert sanacion["dry_run"] is True
    assert sanacion["healed"] == 0
    assert sanacion["propuestos"] == 1
    assert sanacion["sanados"][0]["code_curado"] == CURA_DOBLE
    assert sanacion["escritos"] == []
    assert nota.read_text(encoding="utf-8") == contenido


def test_no_salvable_queda_intacto_y_declarado(vault_estandar):
    """Un roto que ningún sanador cura: el envelope lo declara con el error
    activo del compilador y el archivo NO se toca."""
    _skip_si_no_oraculo()
    vault = vault_estandar
    nota = vault / "roto.md"
    contenido = "# x\n\n```mermaid\n" + ROTO_NO_SALVABLE + "```\n"
    nota.write_text(contenido, encoding="utf-8")
    d = vmc.scan_vault(path=vault)
    sanacion = vmc.sanar_bloques(d)
    assert sanacion["ok"] is False
    assert sanacion["healed"] == 0
    assert len(sanacion["no_salvables"]) == 1
    assert sanacion["no_salvables"][0]["error_activo"]
    assert nota.read_text(encoding="utf-8") == contenido


def test_vault_sano_devuelve_clean_sin_tocar_nada(vault_estandar):
    """Sin rotos: ok True con `clean` declarado — y ninguna escritura que
    simule trabajo (AP-37)."""
    vault = vault_estandar
    (vault / "sano.md").write_text(
        "# x\n\n```mermaid\npie\n    title T\n    \"a\" : 40\n```\n",
        encoding="utf-8",
    )
    d = vmc.scan_vault(path=vault)
    sanacion = vmc.sanar_bloques(d)
    assert sanacion["ok"] is True
    assert sanacion["healed"] == 0
    assert sanacion["clean"] == 1
    assert sanacion["escritos"] == []


def test_snapshot_no_se_sanea(tmp_path, monkeypatch):
    """Un .md en snapshot (.trash y suyos) no entra al diagnóstico — el
    `--fix` que reescribía backups ya está prohibido en scan_vault; aquí se
    congela: snapshot = ni escrito ni propuesto."""
    _skip_si_no_oraculo()
    vault = tmp_path / "mini-vault-snapshot"
    vault.mkdir()
    snapshot = vault / ".trash"
    snapshot.mkdir()
    viejo = snapshot / "viejo.md"
    contenido = "# viejo\n\n```mermaid\n" + ROTO_DOBLE + "```\n"
    viejo.write_text(contenido, encoding="utf-8")
    monkeypatch.setattr(vmc, "_raiz", lambda: vault)
    monkeypatch.setattr(vmc, "refrescar_grafo", lambda *a, **k: {})
    d = vmc.scan_vault(path=vault)
    sanacion = vmc.sanar_bloques(d)
    assert sanacion["ok"] is True
    assert sanacion["healed"] == 0
    assert sanacion["escritos"] == [] and sanacion["sanados"] == []
    # El snapshot queda con su bloque roto: la sanación no lo miró.
    assert "```mermaid\n" + ROTO_DOBLE + "```" in viejo.read_text(encoding="utf-8")


# ============================================================================
# El contrato del registro: el par SANADORES ↔ norma se sostiene en código.
# ============================================================================


def test_par_sanador_nombra_a_ap25_en_el_cuerpo():
    """AP-55: el par `SANADORES['vault_mermaid_check'] -> AP-25` lo sostiene
    una función de este módulo que nombra la norma en su cuerpo."""
    from vault.kernel.norms_catalog import SANADORES

    assert "vault_mermaid_check" in SANADORES
    assert "AP-25" in SANADORES["vault_mermaid_check"]
    cuerpo = Path(vmc.__file__).read_text(encoding="utf-8")
    assert "AP-25" in cuerpo
    # Y lo nombra en el cuerpo de la función sanadora, no solo en la cabecera
    # del módulo (el guard descuenta la cabecera desde v40.16).
    docstring = vmc.sanar_bloques.__doc__ or ""
    assert "AP-25" in docstring


def test_los_5_sanadores_registrados():
    """El registro `SANADORES_MERMAID` declara los 5 sanadores con nombre —
    el envelope de la sanación los cita tal cual."""
    nombres = [n for n, _fn in vmc.SANADORES_MERMAID]
    assert set(nombres) == {
        "saltos_literales",
        "edge_label_especial",
        "er_etiqueta",
        "label_especial",
        "corchete_abierto",
    }
