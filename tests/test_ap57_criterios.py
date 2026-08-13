"""AP-57 — un criterio con dueño, reimplementado en la medida.

Los tests que importan no son los del feliz camino: son los que fijan **qué
promete y qué no** el detector. Es sintáctico, y su valor depende de que nadie
lea su verde como «no hay copias».
"""
import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_criterios as vc  # noqa: E402


def _arbol(src: str) -> ast.AST:
    return ast.parse(src)


# ── El registro ───────────────────────────────────────────────────────────────

def test_cada_criterio_declara_dueno_simbolo_senales_y_motivo():
    for c in vc.CRITERIOS_CON_DUENO:
        assert c["criterio"] and c["dueño"] and c["simbolo"]
        assert c["senales"], f"{c['criterio']} sin señales no detecta nada"
        assert len(c["por_que"]) > 40, "un registro sin motivo escrito no se audita"


def test_el_dueno_declarado_existe_y_define_su_simbolo():
    """Un dueño que no existe convierte la norma en una promesa (AP-45)."""
    for c in vc.CRITERIOS_CON_DUENO:
        mod = RAIZ / "scripts" / f"{c['dueño']}.py"
        assert mod.exists(), f"dueño inexistente: {c['dueño']}"
        arbol = ast.parse(mod.read_text(encoding="utf-8"))
        definidos = {n.name for n in ast.walk(arbol)
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        definidos |= {n.id for n in ast.walk(arbol)
                      if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        assert c["simbolo"] in definidos, (
            f"{c['dueño']} no define {c['simbolo']}: el registro apunta a un hueco")


# ── El detector ───────────────────────────────────────────────────────────────

def test_importar_al_dueno_por_from_no_es_copia():
    arbol = _arbol("from vault_io import is_snapshot_path\nX = 'vault-backups'\n")
    assert vc._importa(arbol, "vault_io", "is_snapshot_path")


def test_importar_al_dueno_por_atributo_tambien_vale():
    """Exigir una sola forma de importar sería inventarse un estilo."""
    arbol = _arbol("import vault_io\nvault_io.is_snapshot_path(p)\n")
    assert vc._importa(arbol, "vault_io", "is_snapshot_path")


def test_no_importar_al_dueno_se_ve():
    arbol = _arbol("SKIP = {'vault-backups', '.history'}\n")
    assert not vc._importa(arbol, "vault_io", "is_snapshot_path")


def test_los_duenos_no_se_marcan_a_si_mismos():
    """El dueño escribe sus constantes porque es su trabajo, no por copiar."""
    for c in vc.CRITERIOS_CON_DUENO:
        assert c["dueño"] in vc.DUEÑOS


def test_ningun_hallazgo_apunta_a_un_dueno():
    for h in vc.medir():
        assert h["modulo"] not in vc.DUEÑOS


# ── El límite, que es lo que no hay que malinterpretar ────────────────────────

def test_una_copia_sin_constante_distintiva_no_se_ve_y_esta_declarado():
    """Verde no prueba que no haya copias.

    Un módulo puede reimplementar «qué es una instantánea» comparando contra
    una constante importada de un tercero, o derivándola, sin escribir ninguna
    de las señales. El detector no lo verá, y el docstring lo dice.
    """
    arbol = _arbol("import os\nSKIP = {os.environ['X']}\nG = '*.md'\n")
    for c in vc.CRITERIOS_CON_DUENO:
        literales = set(vc._literales(arbol))
        assert not [s for s in c["senales"] if s in literales]
    assert "no significa que no haya copias" in vc.__doc__


def test_la_precondicion_md_evita_marcar_a_quien_nombra_la_constante_por_otro_motivo():
    """`vault_restore` nombra `vault-backups` porque restaurar de ahí es su trabajo."""
    marcados = {h["modulo"] for h in vc.medir()}
    assert "vault_restore" not in marcados


# ── La baseline ───────────────────────────────────────────────────────────────

def test_la_baseline_existe_y_esta_indexada_por_modulo_y_criterio():
    datos = json.loads(vc.BASELINE.read_text(encoding="utf-8"))
    assert datos["sitios"], "una baseline vacía sin deuda saldada esconde la medida"
    for s in datos["sitios"]:
        assert "::" in s and not s.split("::")[1].isdigit(), (
            "la firma no puede depender de la línea: mover código no es deuda nueva")


def test_freeze_se_niega_a_congelar_deuda_nueva(monkeypatch, tmp_path):
    base = tmp_path / "b.json"
    base.write_text(json.dumps({"sitios": ["vault_x::que_es_una_instantanea"]}),
                    encoding="utf-8")
    monkeypatch.setattr(vc, "BASELINE", base)
    monkeypatch.setattr(vc, "medir", lambda: [
        {"modulo": "vault_x", "criterio": "que_es_una_instantanea",
         "senal": "", "dueño": ""},
        {"modulo": "vault_nuevo", "criterio": "que_es_codigo_y_no_enlace",
         "senal": "", "dueño": ""},
    ])
    r = vc.freeze()
    assert r["ok"] is False and r["error_code"] == "DEBT_WOULD_GROW"
    assert r["new_copies"] == ["vault_nuevo::que_es_codigo_y_no_enlace"]
    assert "recovery" in r


def test_admitir_nuevos_congela_pero_lo_lista(monkeypatch, tmp_path):
    base = tmp_path / "b.json"
    base.write_text(json.dumps({"sitios": ["vault_x::que_es_una_instantanea"]}),
                    encoding="utf-8")
    monkeypatch.setattr(vc, "BASELINE", base)
    monkeypatch.setattr(vc, "medir", lambda: [
        {"modulo": "vault_nuevo", "criterio": "que_es_codigo_y_no_enlace",
         "senal": "", "dueño": ""},
    ])
    r = vc.freeze(admitir_nuevos=True)
    assert r["ok"] and r["admitted_new"] == ["vault_nuevo::que_es_codigo_y_no_enlace"]


def test_check_no_reporta_deuda_congelada_como_nueva():
    r = vc.check()
    assert r["ok"], f"copias nuevas: {r['new_copies']}"
    assert r["norm"] == "AP-57"


# ── Lo que la norma arregló, y no puede volver ────────────────────────────────

def test_vault_graph_fix_no_lleva_su_propia_lista_de_instantaneas():
    """Era el caso peligroso: esa tool **escribe**.

    Su `skip_set` local ya divergía de `vault_io.SNAPSHOT_DIRS`, así que no
    inflaba una métrica — reparaba dentro de una instantánea congelada, que es
    dejar de serlo.
    """
    src = (RAIZ / "scripts" / "vault_graph_fix.py").read_text(encoding="utf-8")
    assert vc._importa(ast.parse(src), "vault_io", "is_snapshot_path")


def test_vault_foreign_check_consulta_a_los_tres_duenos():
    src = (RAIZ / "scripts" / "vault_foreign_check.py").read_text(encoding="utf-8")
    arbol = ast.parse(src)
    for c in vc.CRITERIOS_CON_DUENO:
        assert vc._importa(arbol, c["dueño"], c["simbolo"]), c["criterio"]


# ── Contrato de CLI ───────────────────────────────────────────────────────────

def test_check_y_freeze_a_la_vez_es_un_error_declarado():
    r = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "vault_criterios.py"),
         "--check", "--freeze"],
        capture_output=True, text=True, encoding="utf-8")
    assert r.returncode != 0
    assert "CONFLICTING_ARGS" in r.stdout + r.stderr


def test_strict_devuelve_uno_cuando_hay_copias_nuevas(monkeypatch, tmp_path):
    base = tmp_path / "b.json"
    base.write_text(json.dumps({"sitios": []}), encoding="utf-8")
    monkeypatch.setattr(vc, "BASELINE", base)
    monkeypatch.setattr(vc, "medir", lambda: [
        {"modulo": "vault_nuevo", "criterio": "que_es_codigo_y_no_enlace",
         "senal": "```", "dueño": "vault_lib:strip_code_blocks"},
    ])
    assert vc.check()["ok"] is False


# ── La norma en el catálogo ───────────────────────────────────────────────────

def test_ap57_esta_en_el_catalogo_con_enforcement_real_y_distincion_reciproca():
    import vault_norms
    cat = {n["code"]: n for n in vault_norms.NORM_CATALOG}
    ap57 = cat["AP-57"]
    assert ap57["enforcement"] != "manual"  # regla 5
    assert ap57["tools_detecting"] == ["vault_criterios"]
    assert "AP-50" in ap57["distinguido_de"]
    assert "AP-57" in cat["AP-50"]["distinguido_de"], (
        "si solo la declara una, quien llegue leyendo la otra no ve la diferencia")


def test_la_puerta_15_existe_y_apunta_a_la_tool():
    import vault_gate
    ids = {p["id"] for p in vault_gate.PUERTAS}
    assert "criterios" in ids
    p = next(p for p in vault_gate.PUERTAS if p["id"] == "criterios")
    assert p["cmd"][0] == "vault_criterios.py"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
