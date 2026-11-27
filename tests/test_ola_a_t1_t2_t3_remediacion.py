"""Tests TDD RED->GREEN para Ola A: T-1 (H-03), T-2 (H-05) y T-3 (log append-only)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from apoyo import ROOT, correr_tool
from test_mcp_http_seguridad import TOKEN, Servidor

SERVER_MJS = ROOT / "mcp" / "nodejs" / "vault-mcp-server.mjs"


def _crear_vault_basico(ruta: Path) -> Path:
    for sec in ("00_System", "07_Knowledge", "99_Index"):
        (ruta / sec).mkdir(parents=True, exist_ok=True)
    return ruta


def _eval_node_policy(
    target_root: Path,
    caller_vault: str,
    role: str,
    *,
    caller_root: Path | None = None,
    ruta_nota: str | None = None,
    sensibilidad_nota: str | None = None,
    tags_nota: list[str] | None = None,
) -> dict:
    """Invoca `evaluateCrossVaultAccessPolicy` en Node para validar paridad Python<->Node."""
    url_mjs = SERVER_MJS.as_uri()
    opts = {
        "callerRoot": str(caller_root) if caller_root else None,
        "rutaNota": ruta_nota,
        "sensibilidadNota": sensibilidad_nota,
        "tagsNota": tags_nota or [],
    }
    script = (
        f"import * as srv from {json.dumps(url_mjs)};"
        "if (typeof srv.evaluateCrossVaultAccessPolicy !== 'function') {"
        "  console.log(JSON.stringify({missing_export: true})); process.exit(0);"
        "}"
        f"const res = srv.evaluateCrossVaultAccessPolicy("
        f"{json.dumps(str(target_root))}, {json.dumps(caller_vault)}, {json.dumps(role)}, {json.dumps(opts)});"
        "console.log(JSON.stringify(res));"
    )
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


# ── T-1 (H-03): Fail-closed sin política, paridad Python<->Node, homónimos y sesión individual ──


def test_t1_sin_politica_node_y_python_deniegan_fail_closed(tmp_path):
    """T-1: un vault destino sin 00_System/access-policy.json debe ser denegado (403/deny) en Python y Node."""
    from vault.kernel.acceso_baules import Principal, evaluar_acceso_cruzado

    origen = _crear_vault_basico(tmp_path / "vault-origen")
    destino = _crear_vault_basico(tmp_path / "vault-destino")

    py_res = evaluar_acceso_cruzado(
        Principal(vault="vault-origen", role="lector"),
        destino,
        raiz_origen=origen,
    )
    node_res = _eval_node_policy(destino, "vault-origen", "lector", caller_root=origen)

    assert py_res["allowed"] is False and py_res["reason"] == "no_policy_fail_closed"
    assert node_res.get("missing_export") is not True, "evaluateCrossVaultAccessPolicy debe exportarse"
    assert node_res["allowed"] is False, node_res
    assert node_res["reason"] == "no_policy_fail_closed", node_res
    assert node_res["mode"] == py_res["mode"] == "deny"


def test_t1_carpetas_homonimas_en_rutas_distintas_no_son_self_vault(tmp_path):
    """T-1: dos carpetas llamadas igual ('vault') en rutas distintas NO deben saltarse access-policy."""
    from vault.kernel.acceso_baules import Principal, evaluar_acceso_cruzado

    origen = _crear_vault_basico(tmp_path / "tenant-a" / "vault")
    destino = _crear_vault_basico(tmp_path / "tenant-b" / "vault")

    py_res = evaluar_acceso_cruzado(
        Principal(vault="vault", role="lector"),
        destino,
        raiz_origen=origen,
    )
    node_res = _eval_node_policy(destino, "vault", "lector", caller_root=origen)

    assert py_res["allowed"] is False and py_res["reason"] == "no_policy_fail_closed"
    assert node_res["allowed"] is False and node_res["reason"] == "no_policy_fail_closed"


def test_t1_paridad_python_node_con_politica_y_recurso(tmp_path):
    """T-1: Python y Node deben coincidir en sección, sensibilidad y tags ante las mismas entradas."""
    from vault.kernel.acceso_baules import Principal, escribir_politica_acceso, evaluar_acceso_cruzado

    origen = _crear_vault_basico(tmp_path / "vault-a")
    destino = _crear_vault_basico(tmp_path / "vault-b")
    escribir_politica_acceso(
        destino,
        {
            "schema_version": 1,
            "default": "deny",
            "grants": [
                {
                    "principal": {"vault": "vault-a", "roles": ["lector"]},
                    "mode": "read_only",
                    "max_sensitivity": "internal",
                    "allowed_sections": ["07_Knowledge"],
                    "denied_sections": ["17_Preferences"],
                    "allowed_tags": ["shared"],
                }
            ],
        },
    )

    casos = [
        ("07_Knowledge/ok.md", "internal", ["shared"], True),
        ("07_Knowledge/secreto.md", "restricted", ["shared"], False),
        ("17_Preferences/pref.md", "internal", ["shared"], False),
        ("03_Decisions/adr.md", "internal", ["shared"], False),
        ("07_Knowledge/sin-tag.md", "internal", ["privado"], False),
    ]
    for ruta, sens, tags, esperado in casos:
        py_r = evaluar_acceso_cruzado(
            Principal(vault="vault-a", role="lector"),
            destino,
            raiz_origen=origen,
            ruta_nota=ruta,
            sensibilidad_nota=sens,
            tags_nota=tags,
        )
        nd_r = _eval_node_policy(
            destino,
            "vault-a",
            "lector",
            caller_root=origen,
            ruta_nota=ruta,
            sensibilidad_nota=sens,
            tags_nota=tags,
        )
        assert py_r["allowed"] is esperado, (ruta, py_r)
        assert nd_r["allowed"] is esperado, (ruta, nd_r)
        assert nd_r["mode"] == py_r["mode"], (ruta, py_r, nd_r)


def test_t1_http_sse_sin_politica_responde_403_y_deniega_doble_sesion_misma_instancia(tmp_path):
    """T-1: GET /sse?vault=<otro> sin política -> 403; misma instancia duplicada -> 409."""
    vault_a = _crear_vault_basico(tmp_path / "vault-alfa")
    vault_b = _crear_vault_basico(tmp_path / "vault-beta")

    srv = Servidor(
        vault_a,
        token=TOKEN,
        extra_env={"VAULT_SCAN_ROOTS": str(tmp_path)},
    )
    try:
        # 1) Acceso cruzado a vault-beta sin access-policy.json -> 403 fail-closed
        c_cross, r_cross = srv.pedir(
            "GET",
            "/sse?vault=vault-beta",
            {"Authorization": f"Bearer {TOKEN}"},
        )
        assert r_cross.status == 403, f"esperaba 403 fail-closed, obtuvo {r_cross.status}"
        c_cross.close()

        # 2) Sesión individual por instancia: misma X-MCP-Instance simultánea -> 409 Conflict
        c1, r1 = srv.pedir(
            "GET",
            "/sse",
            {"Authorization": f"Bearer {TOKEN}", "X-MCP-Instance": "inst-neon-1"},
        )
        assert r1.status == 200
        c2, r2 = srv.pedir(
            "GET",
            "/sse",
            {"Authorization": f"Bearer {TOKEN}", "X-MCP-Instance": "inst-neon-1"},
        )
        assert r2.status == 409, f"esperaba 409 por instancia duplicada, obtuvo {r2.status}"
        c2.close()
        c1.close()
    finally:
        srv.cerrar()


# ── T-2 (H-05): Respaldo con ficheros ilegibles no puede devolver unchanged ──


def test_t2_backup_con_fichero_nuevo_ilegible_desactiva_dedup_y_publica_unreadable(tmp_path, monkeypatch):
    """T-2: si un fichero nuevo lanza PermissionError al leerse, crear() no declara unchanged y publica unreadable."""
    from vault.durabilidad.snapshot import ServicioSnapshot
    from vault.kernel import construir

    raiz = _crear_vault_basico(tmp_path / "vault")
    (raiz / "07_Knowledge" / "normal.md").write_text("---\ntitle: Normal\n---\n\nContenido.\n", encoding="utf-8")

    svc = ServicioSnapshot(construir(raiz))
    r1 = svc.crear("base")
    assert r1.get("unchanged") is not True
    assert r1["files_copied"] > 0

    bloqueado = raiz / "07_Knowledge" / "bloqueado.md"
    bloqueado.write_text("---\ntitle: Bloqueado\n---\n\nSecreto.\n", encoding="utf-8")

    orig_read_bytes = Path.read_bytes

    def _read_bytes_bloqueado(self: Path, *args, **kwargs):
        if self.name == "bloqueado.md":
            raise PermissionError("acceso denegado simulado")
        return orig_read_bytes(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", _read_bytes_bloqueado)

    r2 = svc.crear("con-ilegible")
    assert r2.get("unchanged") is not True, f"no debe declarar unchanged con ilegibles: {r2}"
    assert "unreadable" in r2 and any("bloqueado.md" in u for u in r2["unreadable"]), r2


# ── T-3: Desempate por posición de línea en vault_change_log --query ─────────


def test_t3_change_log_query_desempata_mismo_segundo_por_posicion_en_fichero(tmp_path):
    """T-3: varias entradas con el mismo timestamp deben salir en orden inverso de posición en el fichero."""
    raiz = _crear_vault_basico(tmp_path / "vault")
    jsonl = raiz / "00_System" / ".change-log.jsonl"
    mismo_ts = "2026-11-27T12:00:00Z"
    filas = [
        {"id": f"e-{i}", "action": "updated", "path": f"07_Knowledge/n{i}.md",
         "new_path": None, "reason": f"paso {i}", "agent": "pytest", "timestamp": mismo_ts}
        for i in range(5)
    ]
    jsonl.write_text("\n".join([*(json.dumps(f) for f in filas), ""]), encoding="utf-8")

    res = correr_tool("vault_change_log", "--query", "--last", "5", vault=raiz)
    assert res.codigo == 0 and res.envelope["ok"] is True
    rutas = [e["path"] for e in res.envelope["entries"]]
    assert rutas == [
        "07_Knowledge/n4.md",
        "07_Knowledge/n3.md",
        "07_Knowledge/n2.md",
        "07_Knowledge/n1.md",
        "07_Knowledge/n0.md",
    ], f"orden incorrecto en empate de segundo: {rutas}"
