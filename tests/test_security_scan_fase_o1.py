"""Tests TDD de Fase O1: reglas limpias en security_rules y no sobrescritura en vault_security_scan."""

from __future__ import annotations

from pathlib import Path

import vault_io
import vault_security_rules as vsr
import vault_security_scan as vss


def test_todos_los_ids_de_reglas_son_unicos():
    vistos = {}
    duplicados = []
    for cat, rules in vsr.REGLAS_POR_CATEGORIA.items():
        for r in rules:
            rid = r["id"]
            if rid in vistos:
                duplicados.append((rid, vistos[rid], cat))
            vistos[rid] = cat
    assert duplicados == [], duplicados
    assert "X001" in vistos and "XXE001" in vistos


def test_codigo_limpio_y_buenas_practicas_no_disparan_falsos_positivos(tmp_path: Path):
    casos_limpios = {
        "import_subprocess.py": "import subprocess\n",
        "body_strip.py": "body = text.strip()\n",
        "sql_param.py": 'cursor.execute("SELECT * FROM users WHERE id = %s", (uid,))\n',
        "session_regen.js": "req.session.regenerate();\n",
        "env_token.py": 'tok = os.environ.get("GITHUB_TOKEN")\n',
        "env_example.py": 'open(".env.example").read()\n',
        "process_env.js": "const port = process.env.PORT;\n",
    }
    for nombre, codigo in casos_limpios.items():
        f = tmp_path / nombre
        f.write_text(codigo, encoding="utf-8")
        hits = vss.scan_file(f, vsr.REGLAS_POR_CATEGORIA)
        assert hits == [], f"Falso positivo en {nombre}: {hits}"


def test_vulnerabilidades_reales_siguen_detectandose(tmp_path: Path):
    gh_tok = "ghp_" + "A" * 36
    casos_vulnerables = [
        ("cmd.js", "exec(req.query.cmd);\n", "C001"),
        ("path.js", "fs.readFile(req.params.file, cb);\n", "P001"),
        ("sqli.py", 'cursor.execute(f"SELECT * FROM u WHERE id = {uid}")\n', "I002"),
        ("sqli_pct.py", 'cursor.execute("SELECT * FROM u WHERE id = %s" % uid)\n', "I002"),
        ("dotenv.py", 'open(".env").read()\n', "CF004"),
        ("sess.js", "req.session.id = req.query.sid;\n", "A006"),
        ("tok.py", f't = "{gh_tok}"\n', "S006"),
        ("redos.js", "const rx = new RegExp(req.query.pattern);\n", "R001"),
    ]
    for nombre, codigo, regla_esperada in casos_vulnerables:
        f = tmp_path / nombre
        f.write_text(codigo, encoding="utf-8")
        hits = vss.scan_file(f, vsr.REGLAS_POR_CATEGORIA)
        ids = {h["ruleId"] for h in hits}
        assert regla_esperada in ids, f"No detecto {regla_esperada} en {nombre}: {hits}"


def test_dos_hallazgos_criticos_misma_regla_no_se_sobrescriben(tmp_path: Path):
    vault = tmp_path / "vault-o1"
    (vault / "00_System").mkdir(parents=True)
    src = tmp_path / "src"
    src.mkdir()
    tok1 = "ghp_" + "A" * 36
    tok2 = "ghp_" + "B" * 36
    (src / "a.py").write_text(f't = "{tok1}"\n', encoding="utf-8")
    (src / "b.py").write_text(f't = "{tok2}"\n', encoding="utf-8")

    prev = vault_io.set_vault_root(vault)
    try:
        res = vss.vault_security_scan(
            str(src), project="demo", categories=["secrets"], save_findings=True
        )
        assert res["ok"] is True, res
        assert res["totalFindings"] == 2
        saved = res["savedToVault"]
        # 1 reporte consolidado + 2 notas individuales distintas (nunca repetidas)
        assert len(saved) == 3, saved
        assert len(set(saved)) == 3, saved
        for rel in saved:
            assert (vault / rel).is_file()
    finally:
        vault_io.set_vault_root(prev)
