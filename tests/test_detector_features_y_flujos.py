"""Fase G: detector determinista de features, capacidades, algoritmos y flujos de valor.

Fija el contrato verificable (repos internos y externos, CQRS lectura/escritura):
- `vault.grafo.features_y_flujos.detectar_features_y_flujos` detecta deterministamente:
  endpoints HTTP (ej. POST /login), comandos CLI, servicios/capacidades y algoritmos puros,
  trazando la cadena de llamadas extremo a extremo, puntos de decision (`if`/`raise`),
  etapas de flujo de valor y un diagrama Mermaid `flowchart TD` valido (AP-25).
- Repositorio vacio o de configuracion trivial devuelve 0 features sin alucinar (AP-45).
- Auto-escaneo sobre `ROOT` (`Vault-Obsidian-Architecture`) detecta comandos CLI y flujos reales.
- CQRS lectura: `vault_code_query --scan-path <repo_externo> [--feature login]` devuelve
  features + flujos + Mermaid en solo lectura y pasa el preflight `vault run` (AP-36).
- CQRS escritura: `vault_flow_save --project demo --scan-path <repo_externo> --feature login`
  persiste el flujo detectado en `13_Flows/workflow/` con diagrama Mermaid valido y evidencia.
"""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path

from apoyo import ROOT, correr_python, correr_tool

from vault_mermaid_reglas import validate_mermaid


def _crear_repo_sintetico(base: Path) -> Path:
    repo = base / "repo-externo-app"
    (repo / "src").mkdir(parents=True)

    (repo / "src" / "user_repo.py").write_text(
        textwrap.dedent(
            '''\
            """Repositorio de usuarios en memoria."""


            def find_by_email(email: str):
                """Busca un usuario activo por correo electronico."""
                if not email:
                    raise ValueError("email requerido")
                return {"email": email, "password_hash": "hash"}
            '''
        ),
        encoding="utf-8",
    )

    (repo / "src" / "token_service.py").write_text(
        textwrap.dedent(
            '''\
            """Emision de tokens de sesion."""


            def issue_token(user: dict) -> str:
                """Genera un token firmado para el usuario autenticado."""
                return f"tok-{user['email']}"
            '''
        ),
        encoding="utf-8",
    )

    (repo / "src" / "auth_service.py").write_text(
        textwrap.dedent(
            '''\
            """Servicio de autenticacion y login."""

            from src.user_repo import find_by_email
            from src.token_service import issue_token


            def authenticate(email: str, password: str) -> str:
                """Valida credenciales del usuario y emite token de acceso."""
                user = find_by_email(email)
                if not user or not password:
                    raise PermissionError("credenciales invalidas")
                return issue_token(user)
            '''
        ),
        encoding="utf-8",
    )

    (repo / "src" / "api.py").write_text(
        textwrap.dedent(
            '''\
            """Capa HTTP de entrada."""

            from src.auth_service import authenticate


            class _App:
                def post(self, route):
                    return lambda fn: fn


            app = _App()


            @app.post("/login")
            def login_endpoint(email: str, password: str) -> dict:
                """Autentica credenciales via HTTP y devuelve sesion."""
                token = authenticate(email, password)
                return {"ok": True, "token": token}
            '''
        ),
        encoding="utf-8",
    )

    (repo / "src" / "pricing.py").write_text(
        textwrap.dedent(
            '''\
            """Algoritmos de calculo de precios e impuestos."""


            def calcular_impuesto(subtotal: float, tasa: float) -> float:
                """Calcula el impuesto aplicable sobre un subtotal positivo."""
                if subtotal < 0:
                    raise ValueError("subtotal negativo")
                return round(subtotal * tasa, 2)
            '''
        ),
        encoding="utf-8",
    )

    (repo / "src" / "checkout.ts").write_text(
        textwrap.dedent(
            """\
            export function validateCart(items: string[]) {
              if (!items.length) { throw new Error("empty"); }
              return true;
            }

            app.post("/checkout", function handleCheckout(req, res) {
              validateCart(req.items);
              return res.json({ ok: true });
            });
            """
        ),
        encoding="utf-8",
    )
    return repo


def _crear_vault_con_proyecto(base: Path, slug: str = "demo") -> Path:
    raiz = base / "vault"
    for carpeta in ("00_System", f"01_Projects/{slug}", "11_Code", "13_Flows"):
        (raiz / carpeta).mkdir(parents=True, exist_ok=True)
    (raiz / "01_Projects" / slug / "overview.md").write_text(
        textwrap.dedent(
            f"""\
            ---
            title: {slug}
            type: project
            status: active
            project: {slug}
            ---

            # {slug}

            Proyecto de pruebas para flujo de valor.
            """
        ),
        encoding="utf-8",
    )
    return raiz


def test_detector_traza_login_extremo_a_extremo_algoritmo_y_ts(tmp_path):
    from vault.grafo.features_y_flujos import detectar_features_y_flujos

    repo = _crear_repo_sintetico(tmp_path)
    res = detectar_features_y_flujos(repo)

    assert res["files_scanned"] >= 6
    assert res["features_count"] >= 3
    kinds = {f["kind"] for f in res["features"]}
    assert "http_endpoint" in kinds
    assert "algorithm" in kinds

    # Ninguna ruta de evidencia fuga prefijos de maquina (AP-36)
    for feat in res["features"]:
        assert not feat["file"].startswith("/")
        assert ":" not in feat["file"]

    # Buscar el flujo de login y verificar cadena completa api -> auth_service -> user_repo -> token_service
    flujos_login = [fl for fl in res["flows"] if "login" in fl["name"].lower()]
    assert len(flujos_login) == 1, res["flows"]
    flujo = flujos_login[0]
    simbolos = [s["to_symbol"] for s in flujo["steps"]]
    assert "authenticate" in simbolos, flujo["steps"]
    assert "find_by_email" in simbolos, flujo["steps"]
    assert "issue_token" in simbolos, flujo["steps"]
    assert flujo["value_stream"]["trigger"].startswith("HTTP POST /login")
    assert len(flujo["value_stream"]["decisions"]) >= 1

    # El diagrama Mermaid generado debe pasar AP-25 (`validate_mermaid`) sin errores
    errores_mermaid = validate_mermaid(flujo["mermaid"])
    assert errores_mermaid == [], errores_mermaid

    # Verificar deteccion del algoritmo puro y del endpoint TS
    assert any(f["symbol"] == "calcular_impuesto" and f["kind"] == "algorithm" for f in res["features"])
    assert any("/checkout" in (f.get("route_path") or "") for f in res["features"])


def test_detector_no_alucina_en_repo_vacio_o_trivial(tmp_path):
    from vault.grafo.features_y_flujos import detectar_features_y_flujos

    vacio = tmp_path / "repo-vacio"
    vacio.mkdir()
    (vacio / "config.py").write_text("DEBUG = True\nVERSION = '1.0'\n", encoding="utf-8")

    res = detectar_features_y_flujos(vacio)
    assert res["features_count"] == 0
    assert res["flows_count"] == 0


def test_detector_auto_escaneo_sobre_voa_detecta_capacidades_reales():
    from vault.grafo.features_y_flujos import detectar_features_y_flujos

    res = detectar_features_y_flujos(ROOT / "vault", filtro_feature="cli")
    assert res["files_scanned"] >= 1
    res_all = detectar_features_y_flujos(ROOT / "cli")
    assert res_all["features_count"] >= 1


def test_cqrs_lectura_vault_code_query_scan_path_y_preflight(tmp_path):
    repo = _crear_repo_sintetico(tmp_path)
    vault_rt = tmp_path / "rt"
    p_init = correr_python("-m", "vault", "init", vault_rt)
    assert p_init.returncode == 0, p_init.stderr

    # 1. Via CLI directo (`vault_code_query.py --scan-path ... --feature login`)
    env = {**os.environ, "VAULT_ROOT": str(vault_rt)}
    proc = correr_tool(
        "vault_code_query.py",
        "--scan-path",
        str(repo),
        "--feature",
        "login",
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["mode"] == "scan_features"
    assert data["features_count"] >= 1
    assert any("login" in fl["name"].lower() for fl in data["flows"])

    # 2. Via `vault run vault_code_query --scan-path <externa>` (preflight AP-36)
    p_run = correr_python(
        "-m",
        "vault",
        "run",
        "vault_code_query",
        "--scan-path",
        str(repo.resolve()),
        "--feature",
        "login",
        vault=vault_rt,
    )
    assert p_run.returncode == 0, p_run.stderr
    env_run = json.loads(p_run.stdout)
    assert env_run["ok"] is True
    assert env_run.get("error_code") != "PREFLIGHT_REJECTED"


def test_cqrs_escritura_vault_flow_save_scan_path_persiste_flujo_en_13_flows(tmp_path):
    repo = _crear_repo_sintetico(tmp_path)
    vault_dir = _crear_vault_con_proyecto(tmp_path, "demo")
    env = {**os.environ, "VAULT_ROOT": str(vault_dir)}

    proc = correr_tool(
        "vault_flow_save.py",
        "--project",
        "demo",
        "--scan-path",
        str(repo),
        "--feature",
        "login",
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["flows_saved"] >= 1
    assert data["written"] >= 1

    ruta_guardada = vault_dir / data["saved_flows"][0]["path"]
    assert ruta_guardada.is_file()
    contenido = ruta_guardada.read_text(encoding="utf-8")
    assert "```mermaid" in contenido
    assert "authenticate" in contenido
    assert "find_by_email" in contenido


def test_pat10_clasifica_las_ocho_operaciones_de_logica_de_negocio_y_fallback_honesto(tmp_path):
    from vault.grafo.features_y_flujos import (
        OPERACIONES_LOGICA_NEGOCIO,
        clasificar_operaciones_negocio,
        detectar_features_y_flujos,
    )

    assert len(OPERACIONES_LOGICA_NEGOCIO) == 8
    assert set(OPERACIONES_LOGICA_NEGOCIO) == {
        "auth", "rule", "lifecycle", "workflow",
        "transform", "event", "integration", "query",
    }

    assert "auth" in clasificar_operaciones_negocio("src/auth.py", "verify_token", "service_capability")
    assert "rule" in clasificar_operaciones_negocio("src/pricing.py", "calcular_impuesto", "algorithm")
    assert "lifecycle" in clasificar_operaciones_negocio("src/orders.py", "approve_transition", "service_capability")
    assert "workflow" in clasificar_operaciones_negocio("src/checkout.py", "orchestrate_pipeline", "service_capability")
    assert "transform" in clasificar_operaciones_negocio("src/etl.py", "parse_and_normalize", "algorithm")
    assert "event" in clasificar_operaciones_negocio("src/hooks.py", "emit_webhook", "service_capability")
    assert "integration" in clasificar_operaciones_negocio("src/http_client.py", "fetch_remote", "service_capability")
    assert "query" in clasificar_operaciones_negocio("src/search.py", "rank_bm25", "algorithm")
    assert clasificar_operaciones_negocio("src/misc.py", "foo_bar_baz", "service_capability") == ["unclassified"]

    repo = _crear_repo_sintetico(tmp_path)
    res = detectar_features_y_flujos(repo)
    assert res["pattern"] == "PAT-10"
    assert "auth" in res["summary_by_operation"]
    assert "rule" in res["summary_by_operation"]
    flujo_login = [fl for fl in res["flows"] if "login" in fl["name"].lower()][0]
    assert "auth" in flujo_login["business_operations"]
