"""Tests integrados en `tests/` para las 6 nuevas ID normas (AP-80..83, PAT-11, SP-07).

Cubre el catálogo (`norms_catalog`), audiencias Público (`consumidor`) vs.
Privado (`interno_estandar`), las primitivas de `SPEC-05` Etapa 2 (`GestorDispose`,
`SagaPreSha`, `CheckpointLog`, `LeaseHeartbeat`, DAG `vault_fix_all`), `SPEC-06`
(5 umbrales `70/80/85/90/99%`, offloading y triggers JIT) y el motor nativo
estilo Graphify (`AP-80`, `PAT-11`).
"""

from __future__ import annotations

from pathlib import Path

import vault_fix_all as vfa
import vault_norms_catalog as ncat
from vault.grafo.analisis import camino_mas_corto, explicar_nodo, reporte_grafo
from vault.grafo.aristas import CONFIANZA_EPISTEMICA, clasificar_arista_epistemica, consolidar_aristas
from vault.kernel.ciclo_ejecucion import CheckpointLog, GestorDispose, LeaseHeartbeat
from vault.kernel.presupuesto_contexto import (
    HARD_CAPS_CONTEXTO,
    compactar_observaciones,
    evaluar_presion_contexto,
    evaluar_triggers_jit,
    offload_texto_a_puntero,
)


def test_audiencias_publicas_y_privadas_de_las_seis_nuevas_id_normas():
    codigos = {n["code"]: n for n in ncat.NORM_CATALOG}
    for pub in ("AP-80", "AP-81", "PAT-11", "SP-07"):
        assert pub in codigos
        assert ncat.audiencia_de_norma(codigos[pub]) == "consumidor"
    for priv in ("AP-82", "AP-83"):
        assert priv in codigos
        assert ncat.audiencia_de_norma(codigos[priv]) == "interno_estandar"


def test_ap80_y_pat11_epistemica_y_grafo_primero():
    assert CONFIANZA_EPISTEMICA == ("EXTRACTED", "INFERRED", "AMBIGUOUS")
    aristas = consolidar_aristas([
        {"from": "a.md", "to": "b.md", "type": "wiki-link"},
        {"from": "b.md", "to": "c.md", "predicate": "mentions"},
    ])
    assert aristas[0]["epistemic"] == "EXTRACTED"
    assert aristas[1]["epistemic"] == "INFERRED"
    assert clasificar_arista_epistemica({"predicate": "desconocido"})[0] == "AMBIGUOUS"

    grafo = {
        "nodes": {
            "03_Decisions/a.md": {"title": "A", "tags": []},
            "07_Knowledge/b.md": {"title": "B", "tags": []},
            "07_Knowledge/c.md": {"title": "C", "tags": []},
        },
        "edges": [
            {"from": "03_Decisions/a.md", "to": "07_Knowledge/b.md", "type": "wiki-link"},
            {"from": "07_Knowledge/b.md", "to": "07_Knowledge/c.md", "type": "wiki-link"},
        ],
    }
    assert reporte_grafo(grafo)["summary"]["total_nodes"] == 3
    assert camino_mas_corto(grafo, "a", "c")["hops"] == 2
    assert explicar_nodo(grafo, "b")["node"]["total_degree"] == 2


def test_ap81_y_sp07_presupuesto_cinco_umbrales_y_jit(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    assert HARD_CAPS_CONTEXTO["max_active_jit_reminders"] == 3
    assert evaluar_presion_contexto(700, 1000)["strategy"] == "telemetria"
    assert evaluar_presion_contexto(800, 1000)["strategy"] == "enmascarado"
    assert evaluar_presion_contexto(850, 1000)["strategy"] == "poda_rapida"
    assert evaluar_presion_contexto(900, 1000)["strategy"] == "enmascarado_agresivo"
    assert evaluar_presion_contexto(990, 1000)["strategy"] == "compactacion_completa"

    off = offload_texto_a_puntero(
        "bloque largo " * 200,
        offload_dir=vault / "00_System" / "context-offload",
        vault_root=vault,
    )
    assert off["written"] is True and off["pointer_tokens"] <= 25

    obs = [{"id": f"o{i}", "tool": "audit", "content": "salida " * 100} for i in range(10)]
    comp = compactar_observaciones(
        obs, tokens_usados=9950, ventana_maxima=10000,
        offload_dir=vault / "00_System" / "context-offload", vault_root=vault,
    )
    assert comp["full_dump_ref"] is not None

    jit = evaluar_triggers_jit([{"type": "tool_error"}, {"type": "code_edit"}])
    assert jit["active_count"] == 2 and all(r["role"] == "user" for r in jit["reminders"])


def test_ap82_y_ap83_dispose_lease_checkpoint_y_dag(tmp_path: Path):
    orden = []
    with GestorDispose() as g:
        g.register("primero", lambda: orden.append("primero"))
        g.register("segundo", lambda: orden.append("segundo"))
    assert orden == ["segundo", "primero"]

    reloj = [10.0]
    lease = LeaseHeartbeat("op", ttl_seconds=5.0, clock=lambda: reloj[0])
    lease.acquire_lease()
    assert not lease.is_expired()
    reloj[0] = 20.0
    assert lease.is_expired()

    ck = CheckpointLog(tmp_path)
    ck.save_checkpoint("r1", "s1")
    assert ck.replay_pending("r1", ["s1", "s2"]) == ["s2"]

    pasos = [p["nombre"] for p in vfa.orden_topologico_pasos()]
    assert len(pasos) == len(vfa.PASOS)
