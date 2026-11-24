"""Tests TDD de Fase M3: Onboarding v3 (greenfield/brownfield, --deep-ast, infra/BD/QA y --post-check)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import vault_io
import vault_onboard


def _crear_vault_vacio(tmp_path: Path) -> Path:
    raiz = tmp_path / "vault-m3"
    (raiz / "00_System").mkdir(parents=True)
    return raiz


def test_onboard_v3_greenfield_detecta_modo_y_emite_checklist_sin_inventar_notas(tmp_path):
    vault = _crear_vault_vacio(tmp_path)
    repo = tmp_path / "proyecto-nuevo"
    repo.mkdir()
    (repo / "README.md").write_text("# Proyecto Nuevo\n\nArranque limpio.\n", encoding="utf-8")

    prev = vault_io.set_vault_root(vault)
    try:
        res = vault_onboard.vault_onboard(
            project="nuevo",
            path=str(repo),
            no_git=True,
            mode="auto",
            lang_hint="python",
        )
        assert res["ok"] is True, res
        assert res["onboarding_mode"] == "greenfield"
        assert len(res["greenfield_checklist"]) == 4
        assert any("PAT-10" in paso["layer"] for paso in res["greenfield_checklist"])
        assert set(res["sections_report"]) == set(vault_onboard.ORDERED_SECTIONS)
    finally:
        vault_io.set_vault_root(prev)


def test_onboard_v3_brownfield_deep_ast_infra_bd_qa_adrs_scripts_y_post_check(tmp_path):
    vault = _crear_vault_vacio(tmp_path)
    repo = tmp_path / "tienda-py"
    for carpeta in (
        "scripts",
        "src/controllers",
        "src/services",
        "src/repositories",
        "docs/adr",
        "infra/terraform",
        "prisma",
    ):
        (repo / carpeta).mkdir(parents=True)

    (repo / "pyproject.toml").write_text(
        textwrap.dedent(
            """\
            [project]
            name = "tienda-py"
            version = "0.2.0"
            description = "Servicio de pagos"
            requires-python = ">=3.11"
            license = { text = "MIT" }
            dependencies = ["fastapi>=0.110", "pydantic>=2.0"]

            [project.scripts]
            tienda-cli = "tienda.cli:main"
            """
        ),
        encoding="utf-8",
    )
    (repo / "uv.lock").write_text("# lock\n", encoding="utf-8")
    (repo / "AGENTS.md").write_text("# Reglas\n", encoding="utf-8")
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (repo / "infra" / "terraform" / "main.tf").write_text('resource "null_resource" "x" {}\n', encoding="utf-8")
    (repo / "prisma" / "schema.prisma").write_text("model Order { id Int @id }\n", encoding="utf-8")
    (repo / "docs" / "adr" / "0001-elegir-fastapi.md").write_text("# ADR 0001\n", encoding="utf-8")
    (repo / "README.md").write_text(
        "# tienda-py\n\n## Funcionalidades\n\n- Autenticar clientes con JWT\n",
        encoding="utf-8",
    )
    (repo / "scripts" / "tool_cli.py").write_text("def run_cli():\n    return True\n", encoding="utf-8")
    (repo / "src" / "controllers" / "auth_controller.py").write_text(
        textwrap.dedent(
            """\
            from services.auth_service import authenticate_user

            @app.post("/login")
            def login_endpoint(email: str, secret: str):
                return authenticate_user(email, secret)
            """
        ),
        encoding="utf-8",
    )
    (repo / "src" / "services" / "auth_service.py").write_text(
        textwrap.dedent(
            """\
            from repositories.user_repository import UserRepository

            def authenticate_user(email: str, secret: str):
                if not email:
                    raise ValueError("email requerido")
                return UserRepository().find_by_email(email)
            """
        ),
        encoding="utf-8",
    )
    (repo / "src" / "repositories" / "user_repository.py").write_text(
        textwrap.dedent(
            """\
            class UserRepository:
                def find_by_email(self, email: str):
                    return {"email": email}
            """
        ),
        encoding="utf-8",
    )

    prev = vault_io.set_vault_root(vault)
    try:
        res = vault_onboard.vault_onboard(
            project="tienda-py",
            path=str(repo),
            no_git=True,
            mode="brownfield",
            deep_ast=True,
            post_check=True,
        )
        assert res["ok"] is True, res
        assert res["onboarding_mode"] == "brownfield"
        assert res["deep_ast"] is True
        assert res["ast_summary"]["pattern"] == "PAT-10"
        assert res["ast_summary"]["patterns_detected"] >= 1
        assert res["ast_summary"]["flows_detected"] >= 1
        assert "auth" in res["ast_summary"]["summary_by_operation"]

        # 1. scripts/ ya no se excluye del escaneo de módulos
        assert (vault / "11_Code" / "tienda-py" / "tool-cli.md").is_file()

        # 2. Infraestructura detecta Terraform y Prisma BD
        infra_txt = (vault / "09_Infrastructure" / "tienda-py" / "infra.md").read_text(encoding="utf-8")
        assert "infra/terraform/main.tf" in infra_txt
        assert "prisma/schema.prisma" in infra_txt

        # 3. 03_Decisions inventaria docs/adr/* existentes
        adrs_txt = (vault / "03_Decisions" / "tienda-py-adrs-existentes.md").read_text(encoding="utf-8")
        assert "docs/adr/0001-elegir-fastapi.md" in adrs_txt

        # 4. 14_Requirements nace stub en cuerpo Markdown (nunca implemented)
        req_txt = (vault / "14_Requirements" / "tienda-py" / "req-001.md").read_text(encoding="utf-8")
        assert "**Status:** stub" in req_txt
        assert "**Status:** implemented" not in req_txt

        # 5. 15_Tests registra quality gates detectados (pytest.ini)
        qa_txt = (vault / "15_Tests" / "qa" / "tienda-py-quality-gates.md").read_text(encoding="utf-8")
        assert "pytest.ini" in qa_txt

        # 6. 17_Preferences detecta gestor de paquetes (uv) y convenciones (AGENTS.md)
        pref_txt = (vault / "17_Preferences" / "tienda-py-contexto.md").read_text(encoding="utf-8")
        assert "uv" in pref_txt and "AGENTS.md" in pref_txt

        # 7. 16_AI_Governance detecta licencia real (MIT) y dependencias de pyproject.toml
        gov_txt = (vault / "16_AI_Governance" / "tienda-py-baseline.md").read_text(encoding="utf-8")
        assert "MIT" in gov_txt

        # 8. 05_Patterns usa nombres oficiales y referencia estándar
        pat_files = list((vault / "05_Patterns").rglob("*.md"))
        pat_text = "\n".join(p.read_text(encoding="utf-8") for p in pat_files if p.name != "index.md")
        assert "Nombre oficial:" in pat_text and "Referencia estándar:" in pat_text

        # 9. 13_Flows tiene flujo de valor AST con operaciones PAT-10
        flow_files = list((vault / "13_Flows" / "workflow").glob("*.md"))
        assert flow_files, "faltan flujos AST en 13_Flows/workflow"
        flow_text = "\n".join(p.read_text(encoding="utf-8") for p in flow_files)
        assert "Operaciones de negocio (PAT-10):" in flow_text and "auth" in flow_text

        # 10. --post-check devuelve audit con toReach100 y drift_snapshot
        assert res["post_check"]["audit"]["ok"] is True
        assert res["post_check"]["audit"]["toReach100"]
        assert res["post_check"]["drift_snapshot"]["ok"] is True
    finally:
        vault_io.set_vault_root(prev)


def test_deep_ast_no_duplica_escaneo_y_receta_usa_flag_type(tmp_path: Path, monkeypatch):
    """Regresion del code review: --deep-ast escanea una sola vez y la receta usa --type."""
    vault = _crear_vault_vacio(tmp_path)
    repo = tmp_path / "repo-unico"
    (repo / "src" / "services").mkdir(parents=True)
    (repo / "src" / "services" / "order_service.py").write_text(
        "class OrderService:\n    def create_order(self): return True\n", encoding="utf-8"
    )
    (repo / "src" / "services" / "tax_service.py").write_text(
        "class TaxService:\n    def calculate(self): return 0\n", encoding="utf-8"
    )

    calls = {"pat": 0, "flujos": 0}
    orig_pat = vault_onboard.patrones_diseno.detectar_patrones
    orig_flujos = vault_onboard.features_y_flujos.detectar_features_y_flujos

    def _spy_pat(*a, **kw):
        calls["pat"] += 1
        return orig_pat(*a, **kw)

    def _spy_flujos(*a, **kw):
        calls["flujos"] += 1
        return orig_flujos(*a, **kw)

    monkeypatch.setattr(vault_onboard.patrones_diseno, "detectar_patrones", _spy_pat)
    monkeypatch.setattr(vault_onboard.features_y_flujos, "detectar_features_y_flujos", _spy_flujos)

    prev = vault_io.get_vault_root()
    try:
        vault_io.set_vault_root(vault)
        res = vault_onboard.vault_onboard(
            project="repo-unico", path=str(repo), no_git=True, deep_ast=True,
        )
        assert res["ok"] is True
        assert calls == {"pat": 1, "flujos": 1}, calls

        # Sin --deep-ast, la receta de 05_Patterns debe usar --type (no --pattern_type)
        vault2 = tmp_path / "vault2"
        vault2.mkdir()
        (vault2 / "00_System").mkdir()
        vault_io.set_vault_root(vault2)
        res2 = vault_onboard.vault_onboard(
            project="repo-unico", path=str(repo), no_git=True, deep_ast=False,
        )
        assert res2["ok"] is True
        pat_notes = [p for p in (vault2 / "05_Patterns").rglob("*.md") if p.name != "index.md"]
        assert pat_notes
        txt = "\n".join(p.read_text(encoding="utf-8") for p in pat_notes)
        assert "--pattern_type" not in txt
        assert "--type architecture" in txt
    finally:
        vault_io.set_vault_root(prev)
