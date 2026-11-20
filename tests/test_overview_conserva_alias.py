"""Refreshing the project overview keeps its `<slug>-overview` alias (writer U3, 2026-11-20).

`vault_onboard` writes the overview with `aliases: [<slug>-overview]`, and its
event records (sessions, debt, governance baseline) link `[[<slug>-overview]]`.
`vault_project_overview` rebuilt the frontmatter from scratch without the alias,
so after a refresh every one of those links stopped resolving.
"""

from apoyo import correr_tool, entorno
from vault_lib import parse_frontmatter


def test_el_overview_refrescado_conserva_su_alias(tmp_path):
    v = tmp_path / "vault"
    v.mkdir()
    env = entorno(v, VAULT_TOOL_TIMEOUT="600")
    assert correr_tool("vault_init", "--no-audit", env=env, timeout=600).codigo == 0
    assert correr_tool("vault_project", "--add", "demo-api", "--title", "Demo API", env=env).envelope.get("ok")
    r = correr_tool("vault_project_overview", "--project", "demo-api",
                    "--description", "API de pedidos para tiendas pequenas", env=env)
    assert r.envelope.get("ok"), r.stdout + r.stderr
    fm = parse_frontmatter((v / "01_Projects" / "demo-api" / "overview.md").read_text(encoding="utf-8"))
    assert "demo-api-overview" in (fm.get("aliases") or []), fm
