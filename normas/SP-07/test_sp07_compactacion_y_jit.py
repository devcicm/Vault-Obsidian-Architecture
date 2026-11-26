"""Tests de paquete de la ID norma SP-07 (5 umbrales de compactación y triggers JIT)."""

from pathlib import Path

from vault.kernel.presupuesto_contexto import (
    compactar_observaciones,
    evaluar_presion_contexto,
    evaluar_triggers_jit,
)


def test_sp07_cinco_umbrales_y_volcado_al_99(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    assert evaluar_presion_contexto(690, 1000)["level"] == 0
    assert evaluar_presion_contexto(700, 1000)["level"] == 1
    assert evaluar_presion_contexto(800, 1000)["level"] == 2
    assert evaluar_presion_contexto(850, 1000)["level"] == 3
    assert evaluar_presion_contexto(900, 1000)["level"] == 4
    assert evaluar_presion_contexto(990, 1000)["level"] == 5

    obs = [{"id": f"t{i}", "tool": "audit", "content": "salida " * 120} for i in range(10)]
    r2 = compactar_observaciones(obs, tokens_usados=8000, ventana_maxima=10000)
    assert r2["masked_count"] == 4 and r2["tokens_saved"] > 0

    r3 = compactar_observaciones(obs, tokens_usados=8500, ventana_maxima=10000)
    assert r3["pruned_count"] == 6 and len(r3["observations"]) == 4

    r5 = compactar_observaciones(
        obs, tokens_usados=9950, ventana_maxima=10000,
        offload_dir=vault / "00_System" / "context-offload",
        vault_root=vault,
    )
    assert r5["full_dump_ref"] is not None
    assert (vault / r5["full_dump_ref"]).is_file()
    assert r5["observations"][0]["id"] == "compaction-summary"
    assert len(r5["observations"]) == 5  # 1 resumen + 4 literales recientes


def test_sp07_triggers_jit_con_rol_user_y_hard_cap():
    eventos = [
        {"type": "tool_error"},
        {"type": "code_edit"},
        {"type": "read"}, {"type": "read"}, {"type": "read"}, {"type": "read"}, {"type": "read"},
    ]
    res = evaluar_triggers_jit(eventos, max_activos=2)
    assert res["active_count"] == 2
    assert all(r["role"] == "user" for r in res["reminders"])
    triggers = {r["trigger"] for r in res["reminders"]}
    assert triggers == {"tool_error", "post_code_edit"}
