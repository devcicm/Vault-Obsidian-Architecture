"""The pattern flow end to end: save, advance, tag, list, rebuild the index.

Flow QA on 2026-11-17 (c09473ab) found three defects that only show when the
tools are chained the way an agent chains them:

- QA-FL-01: every pattern was frozen after creation. The transition guard read
  the canonical `status` (`planned`) while `VALID_TRANSITIONS` is keyed by the
  domain state (`planificado`), so `planned → en_progreso` had no exit and even
  re-saving the same state was rejected.
- QA-FL-09: `vault_pattern_save` wrote no `tags`, so the product's own audit
  flagged every pattern note under AP-26.
- QA-FL-PAT: a vault with pattern notes but no `05_Patterns/index.json` had no
  way back; only a new save wrote the index, and only with its own entry.
"""
import json
from pathlib import Path

import yaml

from apoyo import SCRIPTS, correr_tool, escribir_nota


def _cli(vault: Path, script: str, *args: str):
    return correr_tool(script, *args, vault=vault, cwd=SCRIPTS)


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "00_System").mkdir(parents=True)
    assert _cli(vault, "vault_project.py", "--add", "demo").envelope["ok"]
    return vault


def _save(vault: Path, status: str, name: str = "Repository", tipo: str = "code"):
    return _cli(vault, "vault_pattern_save.py", "--project", "demo", "--name", name,
                "--type", tipo, "--status", status)


def _frontmatter(ruta: Path) -> dict:
    texto = ruta.read_text(encoding="utf-8")
    return yaml.safe_load(texto.split("---", 2)[1])


def _indice(vault: Path) -> dict:
    return json.loads((vault / "05_Patterns" / "index.json").read_text(encoding="utf-8"))


NOTA = "05_Patterns/code/demo-repository.md"


def test_qa_fl01_un_patron_avanza_de_planificado_a_en_progreso(tmp_path):
    vault = _vault(tmp_path)
    assert _save(vault, "planificado").envelope["ok"]

    corrida = _save(vault, "en_progreso")
    r = corrida.envelope
    assert corrida.codigo == 0 and r["ok"] is True, r
    assert r["status"] == "en_progreso", r
    assert r["transition"] == "planificado → en_progreso", r
    assert r["path"] == NOTA, r

    fm = _frontmatter(vault / NOTA)
    assert fm["pattern_state"] == "en_progreso", fm
    assert fm["status"] == "in-progress", fm
    texto = (vault / NOTA).read_text(encoding="utf-8")
    assert texto.count("**planificado** → **en_progreso**") == 1, texto

    entradas = _indice(vault)["patterns"]
    assert [(e["path"], e["status"]) for e in entradas] == [(NOTA, "en_progreso")], entradas


def test_qa_fl01_dos_transiciones_dejan_dos_lineas_de_evolucion(tmp_path):
    vault = _vault(tmp_path)
    for estado in ("planificado", "en_progreso", "implementado"):
        assert _save(vault, estado).envelope["ok"]

    texto = (vault / NOTA).read_text(encoding="utf-8")
    evolucion = texto.split("## Evolución", 1)[1].split("\n---\n", 1)[0]
    lineas = [linea for linea in evolucion.splitlines() if linea.strip()]
    assert len(lineas) == 2, texto
    assert lineas[0].startswith("- **planificado** → **en_progreso**"), texto
    assert lineas[1].startswith("- **en_progreso** → **implementado**"), texto
    assert texto.count("*Última actualización:") == 1, texto


def test_qa_fl01_avanzar_el_estado_no_borra_lo_que_la_nota_ya_documentaba(tmp_path):
    """Once a transition goes through, a save with only `--status` must not
    rewrite the note without its description, files, related patterns or notes."""
    vault = _vault(tmp_path)
    assert _cli(vault, "vault_pattern_save.py", "--project", "demo", "--name", "Repository",
                "--type", "code", "--status", "planificado",
                "--description", "Data access behind an interface.",
                "--files", "src/repo.py", "--related", "Unit-of-Work",
                "--notes", "See ADR-003.").envelope["ok"]

    assert _save(vault, "en_progreso").envelope["ok"]

    texto = (vault / NOTA).read_text(encoding="utf-8")
    assert "## Descripción\n\nData access behind an interface." in texto, texto
    assert "## Archivos\n\n- `src/repo.py`" in texto, texto
    assert "[[demo-unit-of-work|Unit-of-Work]]" in texto, texto
    assert "## Notas\n\nSee ADR-003." in texto, texto
    fm = _frontmatter(vault / NOTA)
    assert fm["files"] == ["src/repo.py"] and fm["relatedPatterns"] == ["Unit-of-Work"], fm

    # An explicit value still replaces the previous one.
    assert _cli(vault, "vault_pattern_save.py", "--project", "demo", "--name", "Repository",
                "--type", "code", "--status", "en_progreso",
                "--description", "Collections of aggregates.").envelope["ok"]
    texto = (vault / NOTA).read_text(encoding="utf-8")
    assert "Collections of aggregates." in texto and "Data access" not in texto, texto


def test_qa_fl01_guardar_el_mismo_estado_otra_vez_no_es_una_transicion(tmp_path):
    vault = _vault(tmp_path)
    assert _save(vault, "planificado").envelope["ok"]

    corrida = _save(vault, "planificado")
    r = corrida.envelope
    assert corrida.codigo == 0 and r["ok"] is True, r
    assert r["transition"] is None, r
    assert "## Evolución" not in (vault / NOTA).read_text(encoding="utf-8")
    assert _frontmatter(vault / NOTA)["pattern_state"] == "planificado"


def test_qa_fl01_la_maquina_de_estados_sigue_rechazando_lo_que_no_admite(tmp_path):
    """S4: the guard is read from the right field, not relaxed."""
    vault = _vault(tmp_path)
    assert _save(vault, "planificado").envelope["ok"]
    antes = (vault / NOTA).read_bytes()

    corrida = _save(vault, "implementado")
    r = corrida.envelope
    assert corrida.codigo == 1 and r["ok"] is False, r
    assert r["error_code"] == "INVALID_VALUE", r
    assert "planificado → implementado" in r["message"], r
    assert "en_progreso" in r["message"], r
    assert (vault / NOTA).read_bytes() == antes
    assert _indice(vault)["patterns"][0]["status"] == "planificado"


def test_qa_fl01_una_nota_antigua_con_el_estado_de_dominio_en_status(tmp_path):
    """Notes written before AP-38 carry the domain value in `status` itself."""
    vault = _vault(tmp_path)
    escribir_nota(vault, NOTA, {"title": "Repository", "id": "p-1", "project": "demo",
                                "type": "code", "status": "implementado"}, "# Repository\n")

    r = _save(vault, "deprecado").envelope
    assert r["ok"] is True and r["transition"] == "implementado → deprecado", r
    rechazo = _save(vault, "planificado").envelope
    assert rechazo["ok"] is False and rechazo["error_code"] == "INVALID_VALUE", rechazo


def test_qa_fl09_el_patron_nace_con_tags(tmp_path):
    vault = _vault(tmp_path)
    assert _save(vault, "planificado").envelope["ok"]

    assert _frontmatter(vault / NOTA)["tags"] == ["code", "demo", "pattern"]


def test_qa_fl09_resave_conserva_los_tags_que_ya_tenia_la_nota(tmp_path):
    vault = _vault(tmp_path)
    escribir_nota(vault, NOTA, {"title": "Repository", "id": "p-1", "project": "demo",
                                "type": "code", "status": "planned",
                                "pattern_state": "planificado", "tags": ["ddd"]},
                  "# Repository\n")

    assert _save(vault, "en_progreso").envelope["ok"]
    assert _frontmatter(vault / NOTA)["tags"] == ["code", "ddd", "demo", "pattern"]


def test_qa_fl_pat_la_recuperacion_reconstruye_el_indice_desde_las_notas(tmp_path):
    vault = _vault(tmp_path)
    assert _save(vault, "planificado").envelope["ok"]
    assert _save(vault, "en_progreso", name="Hexagonal", tipo="architecture").envelope["ok"]
    assert _save(vault, "en_progreso", name="Hexagonal", tipo="architecture").envelope["ok"]
    # A note the pattern module does not recognise stays out of the index.
    escribir_nota(vault, "05_Patterns/code/suelta.md", {"title": "Suelta", "type": "code"},
                  "# Suelta\n")
    (vault / "05_Patterns" / "index.json").unlink()

    error = _cli(vault, "vault_pattern_list.py").envelope
    assert error["ok"] is False and error["error_code"] == "INDEX_NOT_FOUND", error
    recovery = error["recovery"]
    assert recovery["action"] == "run_tool", recovery
    assert recovery["tool"] == "vault_pattern_save", recovery
    assert recovery["args"] == ["--rebuild-index"], recovery

    # Obeying the recovery literally, with no placeholder to invent.
    corrida = _cli(vault, "vault_pattern_save.py", *recovery["args"])
    r = corrida.envelope
    assert corrida.codigo == 0 and r["ok"] is True, r
    assert r["action"] == "rebuild-index", r
    assert r["index"] == "05_Patterns/index.json", r
    assert r["indexed"] == 2, r
    assert r["skipped"] == [{"path": "05_Patterns/code/suelta.md",
                             "reason": "no pattern_state in the pattern vocabulary"}], r

    listado = _cli(vault, "vault_pattern_list.py").envelope
    assert listado["ok"] is True and listado["total"] == 2, listado
    assert listado["grouped"]["planificado"] == ["Repository"], listado
    assert listado["grouped"]["en_progreso"] == ["Hexagonal"], listado
    rutas = sorted(p["path"] for p in listado["patterns"])
    assert rutas == ["05_Patterns/architecture/demo-hexagonal.md", NOTA], listado
    assert all(p["project"] == "demo" for p in listado["patterns"]), listado


def test_qa_fl_pat_rebuild_index_no_admite_los_campos_de_un_guardado(tmp_path):
    vault = _vault(tmp_path)

    corrida = _cli(vault, "vault_pattern_save.py", "--rebuild-index", "--name", "X")
    r = corrida.envelope
    assert corrida.codigo == 2 and r["ok"] is False, r
    assert r["error_code"] == "INVALID_ARGS", r
    assert "--rebuild-index" in r["message"] and "--name" in r["message"], r
    assert not (vault / "05_Patterns" / "index.json").exists()


def test_guardar_sin_los_campos_obligatorios_sigue_fallando(tmp_path):
    """Previous behaviour of a save: `--project/--name/--type/--status` stay required."""
    vault = _vault(tmp_path)

    corrida = _cli(vault, "vault_pattern_save.py", "--project", "demo", "--name", "X")
    r = corrida.envelope
    assert corrida.codigo == 2 and r["ok"] is False, r
    assert r["error_code"] == "INVALID_ARGS", r
    assert "--type" in r["message"] and "--status" in r["message"], r
    assert not (vault / "05_Patterns").exists()


def test_el_listado_con_indice_filtra_como_antes(tmp_path):
    vault = _vault(tmp_path)
    assert _save(vault, "planificado").envelope["ok"]
    assert _save(vault, "planificado", name="CQRS", tipo="design").envelope["ok"]

    r = _cli(vault, "vault_pattern_list.py", "--type", "design").envelope
    assert r["ok"] is True and r["total"] == 1, r
    assert r["patterns"][0]["pattern"] == "CQRS", r


def test_resave_conserva_la_fecha_de_creacion(tmp_path):
    """The creation date is a fact of the note: a re-save used to overwrite
    it with the time of the save (W1 advisory, 2026-11-17)."""
    vault = _vault(tmp_path)
    assert _save(vault, "planificado").envelope["ok"]
    nota = vault / NOTA
    texto = nota.read_text(encoding="utf-8")
    antigua = "createdAt: 2020-01-02T03:04:05.000Z"  # the tool's own format
    lineas = [antigua if linea.startswith("createdAt:") else linea for linea in texto.split("\n")]
    nota.write_text("\n".join(lineas), encoding="utf-8")

    assert _save(vault, "en_progreso").envelope["ok"]
    escrita = nota.read_text(encoding="utf-8")
    assert antigua in escrita, escrita
    assert str(_frontmatter(nota)["updatedAt"]) != str(_frontmatter(nota)["createdAt"])
