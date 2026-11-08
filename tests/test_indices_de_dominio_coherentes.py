"""Los índices de dominio se leen: una entrada que no resuelve se ve (D-04).

La nota de causa raíz «vault_move does not update per-domain indexes»
(2026-10-30) medía dos entradas de `.bugs-index.json` que apuntaban a notas
que ya no existían, y el motivo por el que nadie lo notaba: **ningún gate leía
esos ficheros**. La escritura ya se había arreglado (`vault_io.
actualizar_indices_de_dominio`, al que llaman `vault_move` y `vault_delete`),
faltaba la lectura.

Este test comprueba las dos mitades: que la comprobación **ve** la deriva
(roja antes de reparar) y que la reparación del dueño la deja verde.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"


def _vault_con_indice(tmp_path: Path) -> tuple[Path, Path]:
    """Un vault con un índice de dominio que apunta a una nota que no existe."""
    raiz = tmp_path / "vault"
    (raiz / "18_Bugs").mkdir(parents=True)
    (raiz / "00_System").mkdir(parents=True)
    nota = raiz / "18_Bugs" / "nota-real.md"
    nota.write_text("# nota\n", encoding="utf-8")
    indice = raiz / "18_Bugs" / ".bugs-index.json"
    indice.write_text(json.dumps({
        "bugs": [
            {"bug_id": "BUG-001", "relPath": "18_Bugs/nota-real.md"},
            {"bug_id": "BUG-002", "relPath": "18_Bugs/nota-renombrada.md"},
        ]
    }, ensure_ascii=False), encoding="utf-8")
    return raiz, indice


def test_la_comprobacion_ve_la_entrada_que_no_resuelve(tmp_path):
    """La cuenta de entradas puede cuadrar y la ruta estar rota: por eso se
    pregunta por cada `relPath`, no por el número."""
    from vault_io import verificar_indices_de_dominio

    raiz, _ = _vault_con_indice(tmp_path)
    informe = verificar_indices_de_dominio(raiz)
    assert informe["ok"] is False, informe
    assert informe["revisados"] == 2, informe
    assert len(informe["rotas"]) == 1, informe
    assert "nota-renombrada.md" in informe["rotas"][0], informe


def test_la_comprobacion_es_verde_cuando_todo_resuelve(tmp_path):
    from vault_io import verificar_indices_de_dominio

    raiz, indice = _vault_con_indice(tmp_path)
    datos = json.loads(indice.read_text(encoding="utf-8"))
    datos["bugs"][1]["relPath"] = "18_Bugs/nota-real.md"
    indice.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")

    informe = verificar_indices_de_dominio(raiz)
    assert informe["ok"] is True, informe
    assert informe["rotas"] == [], informe


def test_el_ayudante_de_la_cli_publica_el_envelope(tmp_path):
    """`vault_reindex --check-indices` es la superficie: exit 1 y error_code
    cuando hay rutas rotas."""
    from apoyo import correr_tool

    raiz, _ = _vault_con_indice(tmp_path)
    r = correr_tool("vault_reindex", "--check-indices", vault=raiz)
    assert r.codigo == 1, r.stdout + r.stderr
    envelope = json.loads(r.stdout)
    assert envelope["ok"] is False, envelope
    assert envelope["error_code"] == "INDEX_STALE", envelope
    assert envelope["rotas"], envelope


def test_reparar_con_el_dueno_deja_la_comprobacion_en_verde(tmp_path):
    """La escritura del dueño (`actualizar_indices_de_dominio`) y la lectura
    (`verificar_indices_de_dominio`) son la misma criterio: el drift que la
    una arregla es el que la otra ve."""
    import vault_io

    raiz, indice = _vault_con_indice(tmp_path)
    antes = vault_io.verificar_indices_de_dominio(raiz)
    assert antes["ok"] is False, antes

    # El renombrado: la nota nueva toma el sitio de la vieja.
    (raiz / "18_Bugs" / "nota-real.md").rename(
        raiz / "18_Bugs" / "nota-renombrada.md")
    # El dueño escribe sobre la raíz activa del vault, no sobre una ruta
    # que le pasen: se le dice cuál es.
    previa = vault_io.get_vault_root()
    vault_io.set_vault_root(raiz)
    try:
        vault_io.actualizar_indices_de_dominio(
            "18_Bugs/nota-real.md", "18_Bugs/nota-renombrada.md")
    finally:
        vault_io.set_vault_root(previa)

    despues = vault_io.verificar_indices_de_dominio(raiz)
    assert despues["ok"] is True, despues
    assert indice.is_file()
