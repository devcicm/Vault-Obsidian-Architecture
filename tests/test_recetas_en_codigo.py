"""AP-42: toda receta `vault_x --flag` que el código entrega usa flags que existen.

La comprobación 6 de vault_doc_sync medía los `.md` escritos a mano. Medido
2026-10-02, el código entregaba 56 recetas rotas: el `example` del catálogo MCP,
`nextActions` del audit, el `tool_hint` de cada carpeta, la siguiente acción de
voz.py tras un bloqueo (`vault_norms --explain`) y las tablas que vault_sdd_init
reparte a cada vault (`vault_audit --broken-links`, `vault_fix_brackets --fix`).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_doc_sync as vds  # noqa: E402


def test_ap42_ninguna_receta_del_codigo_usa_un_flag_inexistente():
    rotas = [p["detail"] for p in vds.recetas_en_codigo()]
    assert rotas == []


def test_ap42_la_comprobacion_llega_a_la_puerta():
    kinds = {p["kind"] for p in vds.scan()["problems"]}
    assert "receta_flag_no_aceptado" not in kinds


def _detectar(tmp_path, codigo):
    (tmp_path / "zona").mkdir()
    (tmp_path / "zona" / "m.py").write_text(codigo, encoding="utf-8")
    return [p["sitio"] for p in vds.recetas_en_codigo(raices=["zona"], repo_root=tmp_path)]


def test_ap42_ve_una_receta_rota_en_un_literal_y_en_un_fstring(tmp_path):
    sitios = _detectar(tmp_path, (
        'A = "usa `vault_audit --broken-links` y luego vault_read --path x"\n'
        'def f(c):\n    return f"python scripts/vault_norms.py --explain {c}"\n'
    ))
    assert ("zona/m.py", "vault_audit", "--broken-links") in sitios
    assert ("zona/m.py", "vault_norms", "--explain") in sitios
    assert all(flag != "--path" for _, _, flag in sitios)


def test_ap42_no_cuenta_comentarios_ni_flags_de_otro_comando(tmp_path):
    sitios = _detectar(tmp_path, (
        "# `vault_backup --list` no existe: un comentario que lo cita no es receta\n"
        'B = "python -m cli show vault_write --pretty"\n'
        'C = "cli scan --tool vault_write --summary"\n'
        'D = "vault_fundamentals --framework && vault_norms --rebuild"\n'
        'E = "vault_mcp.py exec vault_write --params x"\n'
    ))
    assert sitios == []


def test_las_recetas_exhibidas_siguen_exhibidas():
    """Mundo cerrado: una exhibición que desaparece se retira de la tabla."""
    import ast

    for (rel, tool, flag) in vds.RECETAS_EXHIBIDAS:
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        textos = [t for _, t in vds._literales(tree)]
        assert any(tool in t and flag in vds._flags_de_receta(t.split(tool, 1)[1].removeprefix(".py"))
                   for t in textos), (rel, tool, flag)
