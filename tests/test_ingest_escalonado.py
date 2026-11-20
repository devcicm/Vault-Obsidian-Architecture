"""An ingested note opens with a lead when its source text has none (nota-escalonada U3).

The ingested note is `# title` plus the source text as it arrived. A fragment
of a few lines gave an auditor without context nothing to read first. The lead
says what the note is, where it came from and that it still needs review; a
source that already opens with its own lead is left as it was.
"""

from apoyo import correr_tool, entorno
from vault.kernel.contenido import lead_de, profundidad_de_nota
from vault_lib import separar_frontmatter

SIN_LEAD = ("## Puertos\n\n- 8080 api publica de pedidos para las tiendas\n"
            "- 5432 base de datos principal con los pedidos y los clientes\n"
            "- 6379 cache de sesiones y de carritos abiertos\n"
            "- 9090 metricas que lee el monitoreo del equipo de operaciones\n")
CON_LEAD = ("La pasarela de pagos recibe los cobros de la tienda y los envia al banco adquirente. "
            "Corre como un servicio aparte desde marzo de 2026 y guarda cada intento con su resultado.\n\n"
            "## Puertos\n\n- 9000 pagos\n")


def _ingerir(tmp_path, titulo, texto):
    v = tmp_path / "vault"
    v.mkdir()
    env = entorno(v, VAULT_TOOL_TIMEOUT="600")
    assert correr_tool("vault_init", "--no-audit", env=env, timeout=600).codigo == 0
    r = correr_tool("vault_ingest", "--text", f"# {titulo}\n\n{texto}", "--section", "07_Knowledge",
                    "--commit", env=env)
    assert r.envelope.get("ok"), r.stdout + r.stderr
    notas = [n for n in (v / "07_Knowledge").glob("*.md") if n.stem != "index" and not n.stem.startswith("00-")]
    assert len(notas) == 1, notas
    return separar_frontmatter(notas[0].read_text(encoding="utf-8"))[1]


def test_un_fragmento_sin_lead_recibe_uno(tmp_path):
    cuerpo = _ingerir(tmp_path, "Puertos del entorno", SIN_LEAD)
    assert profundidad_de_nota(cuerpo)["tiene_lead"], cuerpo
    assert "ingerida" in lead_de(cuerpo) and "8080" in cuerpo


def test_una_fuente_con_lead_propio_no_recibe_otro(tmp_path):
    cuerpo = _ingerir(tmp_path, "Pasarela de pagos", CON_LEAD)
    assert lead_de(cuerpo).startswith("La pasarela de pagos"), lead_de(cuerpo)
    assert "ingerida" not in cuerpo.split("## Puertos")[0]
