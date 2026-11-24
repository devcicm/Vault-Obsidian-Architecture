"""Fase K: banco de evaluacion basado en evidencia, calibracion de pesos y benchmark CRUD.

Fija el contrato verificable de `vault.consulta.evaluacion_memoria`:
- Evalua `pesos` vs `bm25` sobre un corpus etiquetado (incluyendo consultas sin
  respuesta y contradicciones declaradas con `contradicts:`) midiendo Recall@3,
  MRR, tasa de primer acierto y rechazo de consultas sin respuesta.
- Calibra perfiles por `--intento` (`explorar`, `documentar`, `cambiar`, `depurar`,
  `revisar`) sobre senales reales de `vault_context_pack` sin romper el default
  declarado `PESOS_RERANK`.
- Distingue mecanicamente los cuatro estados de respuesta (`empty`, `stale_index`,
  `read_error`, `truncated_budget`) frente a `ok_complete`.
- Ejecuta benchmark CRUD reproducible (`create`, `read`, `search`, `update`, `reindex`)
  calculando p50/p95 en milisegundos.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import vault_context_pack
import vault_io
import vault_reindex
import vault_search


def _construir_vault_etiquetado(tmp_path: Path) -> Path:
    raiz = tmp_path / "vault-eval"
    for carpeta in (
        "00_System",
        "03_Decisions",
        "07_Knowledge",
        "17_Preferences",
        "18_Bugs",
        "99_Index",
    ):
        (raiz / carpeta).mkdir(parents=True, exist_ok=True)

    notas = {
        "07_Knowledge/arquitectura-cqrs-mcp.md": textwrap.dedent(
            """\
            ---
            title: Arquitectura CQRS del servidor MCP
            type: knowledge
            status: verified
            tags: [cqrs, mcp, concurrencia]
            cia_integrity: high
            updatedAt: 2026-11-23T10:00:00Z
            ---

            # Arquitectura CQRS del servidor MCP

            El coordinador AsyncRWCoordinator permite lecturas paralelas hasta VAULT_MCP_MAX_READS
            y serializa escrituras por alcance del vault para evitar carreras de escritura.
            Relacionado con [[politica-redondeo-iva-a]] y [[bug-timeout-lectura-larga]].
            """
        ),
        "03_Decisions/adr-001-no-reintentar-cobros.md": textwrap.dedent(
            """\
            ---
            title: ADR 001 No reintentar cobros con tarjeta
            type: decision
            status: approved
            responsable: Carlos Ivan
            tags: [adr, pagos, tarjeta]
            cia_integrity: critical
            updatedAt: 2026-11-22T10:00:00Z
            ---

            # ADR 001 No reintentar cobros con tarjeta

            ## Contexto
            Un reintento ciego tras timeout de pasarela produce doble cobro al cliente.

            ## Decisión
            Nunca reintentar automaticamente un cobro con tarjeta sin clave de idempotencia confirmada.

            ## Consecuencias
            El cajero concilia el estado antes de emitir un segundo intento de cargo.
            """
        ),
        "07_Knowledge/politica-redondeo-iva-a.md": textwrap.dedent(
            """\
            ---
            title: Politica redondeo IVA por linea
            type: knowledge
            status: verified
            tags: [iva, redondeo, fiscal]
            contradicts: "[[politica-redondeo-iva-b]]"
            cia_integrity: high
            updatedAt: 2026-11-20T10:00:00Z
            ---

            # Politica redondeo IVA por linea

            El impuesto IVA se redondea a dos decimales por cada linea del ticket fiscal.
            """
        ),
        "07_Knowledge/politica-redondeo-iva-b.md": textwrap.dedent(
            """\
            ---
            title: Politica redondeo IVA sobre subtotal
            type: knowledge
            status: verified
            tags: [iva, redondeo, fiscal]
            cia_integrity: high
            updatedAt: 2026-11-21T10:00:00Z
            ---

            # Politica redondeo IVA sobre subtotal

            El impuesto IVA se calcula y redondea una sola vez sobre el subtotal acumulado del ticket.
            """
        ),
        "18_Bugs/bug-timeout-lectura-larga.md": textwrap.dedent(
            """\
            ---
            title: Bug timeout en lectura larga de inventario
            type: bug
            status: active
            tags: [bug, timeout, inventario]
            cia_integrity: medium
            updatedAt: 2026-11-23T21:00:00Z
            ---

            # Bug timeout en lectura larga de inventario

            Al consultar el catalogo completo con red lenta, la rutina de cierre de turno agota el timeout
            y deja la cola de sincronizacion bloqueada hasta reiniciar el proceso lector.
            """
        ),
        "17_Preferences/regla-no-borrar-auditorias.md": textwrap.dedent(
            """\
            ---
            title: Regla obligatoria sobre auditorias
            type: preference
            status: active
            strength: must
            tags: [preferencia, gobernanza]
            cia_integrity: critical
            updatedAt: 2026-11-23T08:00:00Z
            ---

            # Regla obligatoria sobre auditorias

            Ninguna nota de auditoria en 19_Audits puede borrarse; se corrige mediante sucesora.
            """
        ),
    }

    for rel, texto in notas.items():
        (raiz / rel).write_text(texto, encoding="utf-8")
    return raiz


def test_evaluacion_pesos_vs_bm25_y_contradicciones(tmp_path):
    from vault.consulta.evaluacion_memoria import (
        PERFILES_INTENTO,
        calibrar_pesos_por_intento,
        clasificar_estado_respuesta,
        comparar_pesos_y_bm25,
    )

    raiz = _construir_vault_etiquetado(tmp_path)
    prev = vault_io.set_vault_root(raiz)
    try:
        idx_res = vault_reindex.vault_reindex()
        assert idx_res.get("ok"), idx_res

        casos = [
            {
                "id": "q-cqrs",
                "query": "AsyncRWCoordinator lecturas paralelas VAULT_MCP_MAX_READS",
                "intento": "explorar",
                "expected": ["07_Knowledge/arquitectura-cqrs-mcp.md"],
            },
            {
                "id": "q-cobros",
                "query": "idempotencia doble cobro pasarela tarjeta",
                "intento": "revisar",
                "expected": ["03_Decisions/adr-001-no-reintentar-cobros.md"],
            },
            {
                "id": "q-bug",
                "query": "cola sincronizacion bloqueada timeout cierre turno",
                "intento": "depurar",
                "expected": ["18_Bugs/bug-timeout-lectura-larga.md"],
            },
            {
                "id": "q-iva",
                "query": "redondeo IVA ticket fiscal",
                "intento": "cambiar",
                "expected": [
                    "07_Knowledge/politica-redondeo-iva-a.md",
                    "07_Knowledge/politica-redondeo-iva-b.md",
                ],
            },
            {
                "id": "q-sin-respuesta",
                "query": "telemetria satelital marciana criptografica inexistente",
                "intento": "documentar",
                "expected": [],
            },
        ]

        def _buscar(query: str, ranking: str) -> list[str]:
            r = vault_search.vault_search(query, ranking=ranking)
            assert r.get("ok"), r
            return [item["path"] for item in r.get("results", [])][:5]

        comp = comparar_pesos_y_bm25(casos, _buscar, top_k=3)
        assert comp["total_cases"] == 5
        assert comp["bm25"]["recall_at_k"] >= comp["pesos"]["recall_at_k"]
        assert comp["bm25"]["mrr"] >= 0.75
        assert comp["bm25"]["unanswered_rejection_rate"] == 1.0

        # Verificar que context_pack trae ambos lados de una contradiccion declarada
        pack_iva = vault_context_pack.vault_context_pack("redondeo IVA linea", budget_tokens=4000)
        assert pack_iva.get("ok"), pack_iva
        rutas_pack = {n["path"] for n in pack_iva.get("included", [])}
        assert "07_Knowledge/politica-redondeo-iva-a.md" in rutas_pack
        assert "07_Knowledge/politica-redondeo-iva-b.md" in rutas_pack

        # Calibracion por intento usando senales reales del context pack
        casos_senales = []
        for c in casos:
            if not c["expected"]:
                continue
            pk = vault_context_pack.vault_context_pack(
                c["query"], budget_tokens=4000, intento=c["intento"]
            )
            casos_senales.append({
                "id": c["id"],
                "intento": c["intento"],
                "expected": c["expected"],
                "candidates": pk.get("included", []),
            })
        cal = calibrar_pesos_por_intento(casos_senales, vault_context_pack.PESOS_RERANK, PERFILES_INTENTO)
        assert set(cal["perfiles_evaluados"]) == set(vault_context_pack.INTENTOS)
        for p in PERFILES_INTENTO.values():
            assert abs(sum(p.values()) - 1.0) < 1e-9

        # Clasificacion de los 4 estados diagnosticos + ok_complete
        assert clasificar_estado_respuesta({"ok": False, "error_code": "FILE_READ_ERROR"}) == "read_error"
        assert clasificar_estado_respuesta({"ok": True, "included": [], "warnings": ["index stale"]}) == "stale_index"
        assert clasificar_estado_respuesta({"ok": True, "included": [], "results": []}) == "empty"
        assert clasificar_estado_respuesta({"ok": True, "included": [{"path": "a.md", "truncated": True}]}) == "truncated_budget"
        assert clasificar_estado_respuesta({"ok": True, "included": [{"path": "a.md", "truncated": False}]}) == "ok_complete"
    finally:
        vault_io.set_vault_root(prev)


def test_banco_crud_escalado_100_notas_mide_p50_y_p95(tmp_path):
    from vault.consulta.evaluacion_memoria import banco_crud_escalado

    def _escribir(raiz: Path, rel: str, contenido: str) -> None:
        destino = raiz / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(contenido, encoding="utf-8")

    def _leer(raiz: Path, rel: str) -> str:
        return (raiz / rel).read_text(encoding="utf-8")

    def _reindexar(raiz: Path) -> None:
        prev = vault_io.set_vault_root(raiz)
        try:
            res = vault_reindex.vault_reindex()
            assert res.get("ok"), res
        finally:
            vault_io.set_vault_root(prev)

    def _buscar(raiz: Path, query: str, ranking: str) -> int:
        prev = vault_io.set_vault_root(raiz)
        try:
            res = vault_search.vault_search(query, ranking=ranking)
            assert res.get("ok"), res
            return len(res.get("results", []))
        finally:
            vault_io.set_vault_root(prev)

    reporte = banco_crud_escalado(
        tmp_path / "bench",
        escalas=(100,),
        muestras_lectura=15,
        escribir_fn=_escribir,
        leer_fn=_leer,
        reindexar_fn=_reindexar,
        buscar_fn=_buscar,
    )
    assert len(reporte["scales"]) == 1
    s100 = reporte["scales"][0]
    assert s100["notes"] == 100
    for op in ("create", "read", "update", "search_pesos", "search_bm25"):
        assert s100[op]["p50_ms"] >= 0.0
        assert s100[op]["p95_ms"] >= s100[op]["p50_ms"]
    assert s100["reindex_ms"] > 0.0
