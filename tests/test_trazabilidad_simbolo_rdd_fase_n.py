"""Tests TDD de Fase N1: trazabilidad @vault por simbolo, IDs cortos, visor HTML y matriz RDD."""

from __future__ import annotations

import textwrap
from pathlib import Path

import vault_code_sync
import vault_code_tag
import vault_io
from vault.kernel.trazabilidad_codigo import (
    extract_all_vault_refs,
    resolver_referencia_vault,
)


def _crear_vault_n1(tmp_path: Path) -> Path:
    raiz = tmp_path / "vault-n1"
    for carpeta in ("00_System", "03_Decisions", "11_Code/tienda", "14_Requirements/tienda", "15_Tests/unit", "19_Audits"):
        (raiz / carpeta).mkdir(parents=True, exist_ok=True)

    (raiz / "14_Requirements" / "tienda" / "req-042-calculo-iva.md").write_text(
        textwrap.dedent(
            """\
            ---
            id: 11111111-1111-1111-1111-111111111142
            req_id: REQ-042
            title: Calculo y redondeo fiscal de IVA
            project: tienda
            type: requirement
            status: approved
            priority: must-have
            ---
            # REQ-042 — Calculo y redondeo fiscal de IVA

            ## Reglas de negocio
            - Tasa general: 16 % sobre subtotal neto.
            - Productos exentos tienen tasa 0 %.

            ## Redondeo
            - Redondear siempre a 2 decimales usando ROUND_HALF_UP.
            """
        ),
        encoding="utf-8",
    )

    (raiz / "14_Requirements" / "tienda" / "req-043-sin-cobertura.md").write_text(
        textwrap.dedent(
            """\
            ---
            req_id: REQ-043
            title: Devolucion parcial de factura
            project: tienda
            type: requirement
            status: approved
            priority: must-have
            ---
            # REQ-043 — Devolucion parcial

            ## Reglas de negocio
            - Emitir nota de credito sin borrar el asiento original.
            """
        ),
        encoding="utf-8",
    )

    (raiz / "03_Decisions" / "adr-0001-tasa-vieja.md").write_text(
        textwrap.dedent(
            """\
            ---
            title: ADR-0001 Tasa fija legada
            project: tienda
            type: adr
            status: superseded
            superseded_by: 14_Requirements/tienda/req-042-calculo-iva.md
            ---
            # ADR-0001 Tasa fija legada

            ## Decision
            Esta decision fue sustituida por REQ-042.
            """
        ),
        encoding="utf-8",
    )

    (raiz / "15_Tests" / "unit" / "tienda-iva-tests.md").write_text(
        textwrap.dedent(
            """\
            ---
            title: Pruebas unitarias de calculo IVA
            project: tienda
            type: test
            test_type: unit
            related_requirement: REQ-042
            ---
            # Pruebas unitarias IVA

            Verifica REQ-042 con casos borde de redondeo.
            """
        ),
        encoding="utf-8",
    )

    return raiz


def test_extract_y_resolve_metodo_indentado_calcular_iva_con_ancla_y_links(tmp_path: Path):
    vault = _crear_vault_n1(tmp_path)
    src_file = tmp_path / "src" / "fiscal.py"
    src_file.parent.mkdir(parents=True)
    codigo = textwrap.dedent(
        """\
        # @vault: 11_Code/tienda/fiscal — Servicio fiscal

        class ServicioFiscal:
            # @vault: REQ-042#redondeo — Reglas fiscales de IVA
            @staticmethod
            def calcular_iva(subtotal: float, tasa: float = 0.16) -> float:
                return round(subtotal * tasa, 2)

            # @vault: ADR-0001 — Decision reemplazada
            def tasa_legacy(self) -> float:
                return 0.15
        """
    )
    src_file.write_text(codigo, encoding="utf-8")

    refs = extract_all_vault_refs(codigo, file_path=src_file)
    assert len(refs) == 3
    hdr, iva_ref, legacy_ref = refs

    assert hdr["scope"] == "file"
    assert iva_ref["scope"] == "symbol"
    assert iva_ref["symbol"] == "ServicioFiscal.calcular_iva"
    assert iva_ref["ref_target"] == "REQ-042"
    assert iva_ref["anchor"] == "redondeo"
    assert iva_ref["span"]["line"] == 4
    assert iva_ref["span"]["col_start"] > 1

    res_iva = resolver_referencia_vault(vault, "REQ-042", anchor="redondeo", project="tienda")
    assert res_iva["resolved"] is True
    assert res_iva["status"] == "ok"
    assert res_iva["anchor_found"] is True
    assert "ROUND_HALF_UP" in res_iva["rules_excerpt"]
    assert res_iva["links"]["obsidian_uri"].startswith("obsidian://open?")
    assert res_iva["links"]["file_uri"].startswith("file:///")

    res_leg = resolver_referencia_vault(vault, "ADR-0001", project="tienda")
    assert res_leg["resolved"] is True
    assert res_leg["status"] == "superseded"
    assert res_leg["stale"] is True
    assert "req-042" in str(res_leg["superseded_by"])


def test_link_symbol_vault_respeta_indentacion_decoradores_y_es_idempotente(tmp_path: Path):
    vault = _crear_vault_n1(tmp_path)
    src_file = tmp_path / "src" / "impuestos.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text(
        textwrap.dedent(
            """\
            class CalculadoraFiscal:
                @classmethod
                def calcular_iva(cls, monto: float) -> float:
                    return round(monto * 0.16, 2)
            """
        ),
        encoding="utf-8",
    )

    prev = vault_io.set_vault_root(vault)
    try:
        r1 = vault_code_tag.vault_code_tag_link_vault(
            "REQ-042", str(src_file), title="Reglas fiscales IVA", symbol="calcular_iva"
        )
        assert r1["ok"] is True and r1["action"] == "linked", r1
        texto = src_file.read_text(encoding="utf-8")
        lineas = texto.splitlines()
        assert lineas[1].startswith("    # @vault: REQ-042")
        assert lineas[2].strip() == "@classmethod"

        # Segunda corrida: idempotente
        r2 = vault_code_tag.vault_code_tag_link_vault(
            "REQ-042", str(src_file), title="Reglas fiscales IVA", symbol="calcular_iva"
        )
        assert r2["ok"] is True and r2["action"] == "already_present", r2
        assert src_file.read_text(encoding="utf-8") == texto

        # --resolve + --html-preview genera visor web clicable dentro del vault (AP-36)
        res = vault_code_tag.vault_code_tag_resolve(
            str(src_file), symbol="calcular_iva", project="tienda", html_preview=True
        )
        assert res["ok"] is True
        assert res["resolved_count"] == 1
        assert "16 %" in res["references"][0]["rules_excerpt"]
        assert res["html_preview_path"] is not None
        html_file = vault / res["html_preview_path"]
        assert html_file.is_file()
        html_txt = html_file.read_text(encoding="utf-8")
        assert 'data-vault-ref="REQ-042"' in html_txt
        assert "obsidian://open?" in html_txt
        assert "ROUND_HALF_UP" in html_txt
    finally:
        vault_io.set_vault_root(prev)


def test_desambiguacion_de_codigo_corto_entre_proyectos(tmp_path: Path):
    vault = _crear_vault_n1(tmp_path)
    (vault / "14_Requirements" / "otro").mkdir(parents=True)
    (vault / "14_Requirements" / "otro" / "req-042-otro.md").write_text(
        "---\nreq_id: REQ-042\ntitle: Otro REQ 042\nproject: otro\nstatus: draft\n---\n# Otro\n",
        encoding="utf-8",
    )

    amb = resolver_referencia_vault(vault, "REQ-042")
    assert amb["resolved"] is False
    assert amb["status"] == "ambiguous"
    assert len(amb["candidates"]) == 2

    ok_proj = resolver_referencia_vault(vault, "REQ-042", project="tienda")
    assert ok_proj["resolved"] is True and ok_proj["project"] == "tienda"

    ok_pref = resolver_referencia_vault(vault, "otro/REQ-042")
    assert ok_pref["resolved"] is True and ok_pref["project"] == "otro"


def test_code_sync_valida_simbolos_ids_cortos_stale_y_matriz_rdd(tmp_path: Path):
    vault = _crear_vault_n1(tmp_path)
    src_dir = tmp_path / "repo" / "src"
    src_dir.mkdir(parents=True)
    fiscal = src_dir / "fiscal.py"
    fiscal.write_text(
        textwrap.dedent(
            """\
            # @vault: 11_Code/tienda/fiscal — Servicio fiscal

            class Fiscal:
                # @vault: REQ-042 — Calculo IVA
                def calcular_iva(self, x: float) -> float:
                    return round(x * 0.16, 2)

                # @vault: ADR-0001 — Decision reemplazada
                def legado(self) -> float:
                    return 0.15
            """
        ),
        encoding="utf-8",
    )
    (vault / "11_Code" / "tienda" / "fiscal.md").write_text(
        f"---\ntitle: Fiscal\nproject: tienda\nsource_file: {fiscal}\n---\n# Fiscal\n",
        encoding="utf-8",
    )

    prev = vault_io.set_vault_root(vault)
    try:
        res = vault_code_sync.vault_code_sync(
            project="tienda", scan_dir=str(src_dir), include_rdd=True
        )
        assert res["ok"] is True
        assert res["orphan_vault_refs"] == [], res["orphan_vault_refs"]
        assert res["summary"]["symbol_refs_checked"] == 2
        assert len(res["stale_vault_refs"]) == 1
        assert res["stale_vault_refs"][0]["status"] == "superseded"

        rdd = res["rdd_traceability"]
        assert rdd["total_requirements"] == 2
        assert rdd["full_coverage"] == 1
        assert rdd["uncovered_approved"] == 1
        by_id = {r["req_id"]: r for r in rdd["requirements"]}
        assert by_id["REQ-042"]["coverage_state"] == "verified_full"
        assert by_id["REQ-042"]["methods"][0]["symbol"] == "Fiscal.calcular_iva"
        assert len(by_id["REQ-042"]["tests"]) == 1
        assert by_id["REQ-043"]["coverage_state"] == "uncovered"
    finally:
        vault_io.set_vault_root(prev)
