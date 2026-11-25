"""Tests TDD de Fase P (cierre estructural interno):
- P1: trazabilidad @vault: en namespace, clase y metodo (C#/C++/PHP/TS/Java/Python) y
      exposicion de vault_code_tag en Grupo 12 (Codigo), MCP y producto wheel.
- P2: escaneo_grafo ignora backticks inline y bloques cercados (paridad con vault_audit).
- P3: AP-17 no marca como duplicados series particionadas por seccion NN_Nombre.
- P4: recetas de vault_audit emitidas via comando_de_tool (portables a `vault run`).
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from apoyo import ROOT
import vault_audit as va
import vault_escaneo_grafo as veg
import vault_mcp_catalog as vmc
import vault_registry as vr
from vault.kernel import trazabilidad_codigo as tc
from vault.meta_toolkit.naturalezas import NATURALEZAS


def test_p1_trazabilidad_vault_en_namespace_clase_y_metodo_csharp_allman():
    codigo_cs = textwrap.dedent("""\
        namespace Facturacion.Impuestos
        {
            public class CalculadoraIva
            {
                public decimal CalcularIva(decimal monto)
                {
                    return monto * 0.16m;
                }

                public decimal Redondear(decimal x) => System.Math.Round(x, 2);
            }
        }
    """)
    ruta = Path("src/Facturacion.cs")

    c1, a1, _, _ = tc.insertar_vault_en_simbolo(
        codigo_cs, "REQ-040", "Facturacion.Impuestos", "line", "Dominio Fiscal", file_path=ruta
    )
    assert a1 == "linked"

    c2, a2, _, _ = tc.insertar_vault_en_simbolo(
        c1, "REQ-041", "CalculadoraIva", "line", "Servicio IVA", file_path=ruta
    )
    assert a2 == "linked"

    c3, a3, _, _ = tc.insertar_vault_en_simbolo(
        c2, "REQ-042#redondeo", "CalculadoraIva.CalcularIva", "line", "Calculo IVA", file_path=ruta
    )
    assert a3 == "linked"

    c4, a4, _, _ = tc.insertar_vault_en_simbolo(
        c3, "REQ-043", "Redondear", "line", "Regla Redondeo", file_path=ruta
    )
    assert a4 == "linked"

    # Idempotencia: re-aplicar no duplica
    c4_bis, a4_bis, _, _ = tc.insertar_vault_en_simbolo(
        c4, "REQ-040", "Facturacion.Impuestos", "line", "Dominio Fiscal", file_path=ruta
    )
    assert a4_bis == "already_present"
    assert c4_bis == c4

    refs = tc.extract_all_vault_refs(c4, file_path=ruta)
    por_simbolo = {r["symbol"]: r for r in refs}
    assert set(por_simbolo) == {"Facturacion.Impuestos", "CalculadoraIva", "CalcularIva", "Redondear"}
    assert por_simbolo["Facturacion.Impuestos"]["symbol_kind"] == "namespace"
    assert por_simbolo["CalculadoraIva"]["symbol_kind"] == "class"
    assert por_simbolo["CalcularIva"]["symbol_kind"] == "method"
    assert por_simbolo["Redondear"]["symbol_kind"] == "method"
    assert all(r["scope"] == "symbol" for r in refs)


def test_p1_namespaces_multilenguaje_calificados():
    casos = [
        ("namespace Facturacion.Impuestos;", ("Facturacion.Impuestos", "namespace")),
        ("namespace App::Billing {", ("App::Billing", "namespace")),
        ("namespace App\\Billing\\Taxes;", ("App\\Billing\\Taxes", "namespace")),
        ("export namespace Billing.Taxes {", ("Billing.Taxes", "namespace")),
        ("package com.acme.billing;", ("com.acme.billing", "namespace")),
        ("module Facturacion::Impuestos", ("Facturacion::Impuestos", "namespace")),
    ]
    for linea, esperado in casos:
        assert tc.extraer_declaracion_linea(linea) == esperado, linea


def test_p1_vault_code_tag_en_grupo_codigo_mcp_y_wheel():
    entry = vmc.TOOLS_CATALOG["vault_code_tag"]
    assert entry["group"] == "Código"
    assert "vault_code_tag" in vmc.GROUPS["Código"]
    assert "vault_code_tag" not in vmc.GROUPS["Normas"]
    assert "vault_code_tag" in NATURALEZAS["custodia"]["tools"]
    assert "vault_code_tag" not in NATURALEZAS["meta_estandar"]["tools"]

    cat_json = json.loads((ROOT / "mcp" / "nodejs" / "tools-catalog.json").read_text(encoding="utf-8"))
    assert cat_json["tools"]["vault_code_tag"]["exposed_via_mcp"] is True

    fuera = json.loads((ROOT / "empaquetado" / "fuera-de-la-wheel.json").read_text(encoding="utf-8"))
    assert "vault_code_tag" not in fuera["modulos"]


def test_p2_escaneo_grafo_ignora_backticks_inline_y_bloques_cercados():
    notas = {
        "07_Knowledge/nota-real.md": "---\ntitle: Nota Real\n---\n# Nota Real\n",
        "19_Audits/ejemplos.md": textwrap.dedent("""\
            ---
            title: Ejemplos de sintaxis
            ---
            Enlace valido a [[nota-real]].
            Sintaxis en codigo inline: `[[nota]]` y regex `r"\\[\\[[^\\]]+\\]\\]"`.

            ```markdown
            [[no-existe-en-bloque]]
            ```

            ~~~markdown
            [[no-existe-en-tilde]]
            ~~~
        """),
    }
    res = veg.escanear_wikilinks(notas)
    assert res["rotos"] == [], res["rotos"]
    assert len(res["aristas"]) == 1
    assert res["aristas"][0]["to"] == "07_Knowledge/nota-real.md"


def test_p3_ap17_no_marca_series_particionadas_por_seccion_pero_si_duplicados():
    assert va._distintos_por_convencion(
        "Agent Vault Inventory — 01_Projects",
        "Agent Vault Inventory — 11_Code",
    ) == "seccion:01_projects/11_code"
    assert va._distintos_por_convencion(
        "Inventario - 00_System",
        "Inventario - 99_Index",
    ) == "seccion:00_system/99_index"

    # Misma seccion o duplicados reales siguen siendo detectados (devuelve None)
    assert va._distintos_por_convencion(
        "Agent Vault Inventory — 01_Projects",
        "Agent Vault Inventory — 01_Projects",
    ) is None
    assert va._distintos_por_convencion(
        "Consumer Vault State Re-Verified 2026-10-29",
        "Consumer Vault State Re-Verified",
    ) is None


def test_p4_recetas_vault_audit_portables_y_vocabulario_status_valido(monkeypatch):
    # En modo wheel instalada, _get_roadmap_for_populated_vault emite `vault run ...`
    monkeypatch.setattr(vr, "corre_instalado", lambda: True)
    acciones = va._get_roadmap_for_populated_vault([])
    comandos = [a["command"] for a in acciones if "command" in a]
    assert comandos, acciones
    assert all(cmd.startswith("vault run vault_") for cmd in comandos), comandos
    assert all("python scripts/" not in cmd for cmd in comandos), comandos

    # La guia de AP-29 no debe sugerir el valor invalido `active`
    rem_status = va._GUIA_PENALIZACION["missing_status"]["remediation"]
    assert "`active`" not in rem_status
