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
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"


@pytest.mark.parametrize("case", ["missing", "omitted", "invalid_identity", "corrupt", "complete", "empty"])
def test_requirement_completeness_check_is_read_only(tmp_path, case):
    from apoyo import correr_tool, nota

    root = tmp_path / "vault"
    section = root / "14_Requirements" / "demo"
    section.mkdir(parents=True)
    relative = "14_Requirements/demo/req-001.md"
    if case != "empty":
        (root / relative).write_text(nota({"id": "doc", "req_id": "REQ-001",
                                          "project": "demo", "type": "requirement"},
                                         "# Requirement"), encoding="utf-8")
    index = root / "14_Requirements" / ".requirements-index.json"
    if case not in ("missing", "empty"):
        entry = {"req_id": "bad" if case == "invalid_identity" else "REQ-001",
                 "project": "demo", "relPath": relative}
        index.write_text("[]" if case == "corrupt" else json.dumps({
            "requirements": [] if case == "omitted" else [entry]}), encoding="utf-8")
    before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    result = correr_tool("vault_reindex", "--check-indices", vault=root)
    assert result.codigo == (0 if case in ("complete", "empty") else 1), result.stdout + result.stderr
    assert result.envelope["ok"] == (case in ("complete", "empty"))
    if case == "missing":
        assert result.envelope["ausentes"] == ["14_Requirements/.requirements-index.json"]
        assert result.envelope["recovery"]["action"] == "manual"
        assert "tool" not in result.envelope["recovery"]
    if case == "omitted":
        assert result.envelope["omitidas"] == [relative]
    if case == "invalid_identity":
        assert result.envelope["invalidas"]
    assert {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("case", ["bug_escaped", "lookalike_folder", "requirement_invalid", "requirement_unreadable_index"])
def test_recovery_is_classified_by_domain(tmp_path, case):
    """Only requirement-domain failures get requirement recovery (L38 regression)."""
    from apoyo import correr_tool, nota

    root = tmp_path / "vault"
    folder = {"bug_escaped": "18_Bugs", "lookalike_folder": "14_Requirements_archive"}.get(case, "14_Requirements")
    (root / folder).mkdir(parents=True)
    (root / "00_System").mkdir()
    if case in ("bug_escaped", "lookalike_folder"):
        (root / folder / ".bugs-index.json").write_text(json.dumps(
            {"bugs": [{"bug_id": "BUG-001", "relPath": "../outside.md"}]}), encoding="utf-8")
    elif case == "requirement_invalid":
        (root / folder / "req-001.md").write_text(nota({"req_id": "REQ-001", "project": "demo"}, "# R"),
                                                  encoding="utf-8")
        (root / folder / ".requirements-index.json").write_text(json.dumps({"requirements": [
            {"req_id": "bad", "project": "demo", "relPath": "14_Requirements/req-001.md"}]}), encoding="utf-8")
    else:
        (root / folder / ".requirements-index.json").write_text("{broken", encoding="utf-8")
    baseline = correr_tool("vault_reindex", "--check-indices", vault=root)
    before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    result = correr_tool("vault_reindex", "--check-indices", vault=root)
    assert result.codigo == 1 and baseline.codigo == 1
    recovery = result.envelope.get("recovery") or {}
    requirement_hint = "restore their domain projection" in recovery.get("hint", "")
    assert requirement_hint == case.startswith("requirement"), recovery
    if case == "bug_escaped":
        assert result.envelope["invalidas"] == ["18_Bugs/.bugs-index.json"]
        assert "outside" not in json.dumps(result.envelope["invalidas"])
    assert {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("failure", ["unreadable", "concurrent"])
def test_requirement_read_failure_is_incomplete_and_sanitized(tmp_path, monkeypatch, failure):
    from apoyo import nota
    from vault_io import verificar_indices_de_dominio

    target = tmp_path / "14_Requirements" / "req-001.md"
    target.parent.mkdir()
    target.write_text(nota({"req_id": "REQ-001", "project": "demo"}, "# Requirement"), encoding="utf-8")
    read = Path.read_text

    def disrupted(path, *args, **kwargs):
        if path == target:
            if failure == "unreadable":
                raise OSError("PRIVATE-READ-CANARY")
            result = read(path, *args, **kwargs)
            path.write_text(result + "changed", encoding="utf-8")
            return result
        return read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", disrupted)
    report = verificar_indices_de_dominio(tmp_path)
    assert not report["ok"]
    assert report["ilegibles"] == ["14_Requirements/req-001.md"]
    assert "PRIVATE-READ-CANARY" not in json.dumps(report)
    assert not (tmp_path / "00_System").exists()


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


def _enlace_de_directorio(enlace: Path, destino: Path) -> None:
    import os
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(destino), str(enlace))
    else:
        enlace.symlink_to(destino, target_is_directory=True)


def test_domain_index_behind_a_junction_is_never_read_or_rewritten(tmp_path):
    from vault_io import actualizar_indices_de_dominio, set_vault_root, verificar_indices_de_dominio

    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    fuera = tmp_path / "outside"
    fuera.mkdir()
    externo = fuera / ".evil-index.json"
    externo.write_text(json.dumps({"bugs": [{"relPath": "SECRET-CANARY/outside.md"}]}), encoding="utf-8")
    _enlace_de_directorio(raiz / "55_Linked", fuera)
    before = externo.read_bytes()
    informe = verificar_indices_de_dominio(raiz)
    assert not informe["ok"]
    assert informe["ilegibles"] == ["55_Linked/.evil-index.json"]
    assert "SECRET-CANARY" not in json.dumps(informe)
    previous = set_vault_root(raiz)
    try:
        resultado = actualizar_indices_de_dominio("SECRET-CANARY/outside.md", None)
    finally:
        set_vault_root(previous)
    assert resultado["unreadable"] == ["55_Linked/.evil-index.json"]
    assert externo.read_bytes() == before


def test_a_requirement_saved_during_the_check_is_not_reported_invalid(tmp_path, monkeypatch):
    """A save landing between the census and the index read is a concurrent read, not corruption."""
    import vault_io
    from apoyo import nota

    req = tmp_path / "14_Requirements" / "demo"
    req.mkdir(parents=True)
    (req / "req-001.md").write_text(nota({"req_id": "REQ-001", "project": "demo"}, "# R1"), encoding="utf-8")
    (req / "req-002.md").write_text(nota({"req_id": "REQ-002", "project": "demo"}, "# R2"), encoding="utf-8")
    (tmp_path / "14_Requirements" / ".requirements-index.json").write_text(json.dumps({"requirements": [
        {"req_id": "REQ-001", "project": "demo", "relPath": "14_Requirements/demo/req-001.md"},
        {"req_id": "REQ-002", "project": "demo", "relPath": "14_Requirements/demo/req-002.md"},
    ]}), encoding="utf-8")
    original = vault_io.leer_requisitos_de_dominio
    calls = []

    def census_before_the_save(raiz):
        calls.append(1)
        result = original(raiz)
        if len(calls) == 1:  # the first census ran before REQ-002 was written
            result["requirements"].pop("demo/REQ-002", None)
        return result

    monkeypatch.setattr(vault_io, "leer_requisitos_de_dominio", census_before_the_save)
    report = vault_io.verificar_indices_de_dominio(tmp_path)
    assert report["ok"], report
    assert report["invalidas"] == []
