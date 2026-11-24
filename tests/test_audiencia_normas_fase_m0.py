"""Tests TDD de Fase M0: separación de audiencia de normas y conteo exacto de familias."""

from __future__ import annotations

import vault_norms
import vault_norms_catalog
import vault_servicio
from vault.autoria import voz


def test_catalogo_clasifica_todas_las_normas_en_audiencia_cerrada():
    audiencias = set(vault_norms_catalog.AUDIENCIAS_NORMA)
    assert audiencias == {"consumidor", "interno_estandar"}
    assert len(vault_norms_catalog.NORMAS_INTERNAS_ESTANDAR) >= 20

    consumidor = [n for n in vault_norms_catalog.NORM_CATALOG if vault_norms_catalog.audiencia_de_norma(n) == "consumidor"]
    internas = [n for n in vault_norms_catalog.NORM_CATALOG if vault_norms_catalog.audiencia_de_norma(n) == "interno_estandar"]
    assert len(consumidor) + len(internas) == len(vault_norms_catalog.NORM_CATALOG)
    assert consumidor and internas

    # Normas de desarrollo interno del toolkit nunca se mezclan como consumidor
    for codigo_interno in ("AP-48", "AP-49", "AP-52", "AP-55", "AP-57", "AP-58", "AP-68", "AP-69"):
        assert vault_norms_catalog.audiencia_de_norma(codigo_interno) == "interno_estandar"

    # Normas de buenas prácticas de terceros son consumidor
    for codigo_consumidor in ("AP-01", "AP-05", "AP-41", "AP-45", "AP-75", "PAT-1", "PAT-7", "SP-01", "CN-01"):
        assert vault_norms_catalog.audiencia_de_norma(codigo_consumidor) == "consumidor"


def test_vault_norms_list_filtra_por_audiencia_sin_mezclar_internas():
    todas = vault_norms.vault_norms_list()
    solo_consumidor = vault_norms.vault_norms_list(audience="consumidor")
    solo_internas = vault_norms.vault_norms_list(audience="interno_estandar")

    assert todas["ok"] and solo_consumidor["ok"] and solo_internas["ok"]
    assert solo_consumidor["total"] + solo_internas["total"] == todas["total"]
    assert todas["by_audience"]["consumidor"] == solo_consumidor["total"]
    assert todas["by_audience"]["interno_estandar"] == solo_internas["total"]

    codigos_cons = {r["code"] for r in solo_consumidor["norms"]}
    codigos_int = {r["code"] for r in solo_internas["norms"]}
    assert codigos_cons.isdisjoint(codigos_int)
    assert "AP-58" not in codigos_cons
    assert "AP-58" in codigos_int
    assert "AP-05" in codigos_cons


def test_voz_del_vault_no_mezcla_normas_internas_en_tools_de_consumidor():
    catalogo = [
        {
            "code": "AP-46",
            "name": "Frontmatter a mano",
            "severity": "critical",
            "audiencia": "interno_estandar",
            "tools_enforcing": ["vault_write"],
            "prevention": "Usa el escritor único.",
        },
        {
            "code": "AP-41",
            "name": "Máquina de estados",
            "severity": "high",
            "audiencia": "consumidor",
            "tools_enforcing": ["vault_write"],
            "prevention": "Transiciona paso a paso.",
        },
    ]
    res = voz.speak(
        "vault_write",
        {"ok": True},
        {"written": 1},
        catalog=catalogo,
        severity_order={"critical": 0, "high": 1},
        voice_mode="1",
        rotation=lambda: 0,
    )
    assert res is not None
    assert res["focus"] == "AP-41"
    assert all("AP-46" not in n for n in res["norms"])


def test_gobierno_doc_cuenta_las_cuatro_familias_y_las_dos_audiencias():
    doc = vault_servicio.documento()
    assert "(0 vigentes)" not in doc
    assert "normas de consumidor" in doc
    assert "normas internas del estándar" in doc
