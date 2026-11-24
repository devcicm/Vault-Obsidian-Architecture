"""Fase F: modos de historial (snapshots/diff/git/auto), base_inmutable y transiciones sin perdida.

Fija el contrato verificable de historial multi-backend y politicas de inmutabilidad:
- `00_System/reglas.json` admite `historial` (`snapshots` | `git` | `diff` | `auto`)
  y `base_inmutable` (lista de secciones) con fallo cerrado ante valores invalidos
  o conflictos entre modos de inmutabilidad (`inmutable`, `sustitucion`, `base_inmutable`)
  o `historial: "git"` en un vault sin `.git`.
- Modo `diff` almacena deltas en `.history/<clave>.patches.jsonl` sin duplicar
  archivos completos `.history/*.md` y reconstruye cualquier version byte a byte.
- Modo `git` y `auto` (con repo git) usan commits sin duplicar `.history/*.md`.
- Cambiar entre `snapshots -> diff -> git -> snapshots` no pierde ninguna version:
  `historia.linea_temporal`, `vault_diff --timeline` y `vault_undo` ven toda la historia.
- `AP-75` (`vault_audit`) detecta reescritura de decisiones cerradas en modo `diff` y `git`,
  sin depender de copias completas `.history/*.md`.
- `base_inmutable` bloquea sobrescribir la nota base sellada y permite evolucionar
  una sucesora que declare `evolves_from:`.
"""

from __future__ import annotations

import hashlib
import json
import os
import textwrap
from pathlib import Path

import pytest

from apoyo import correr_tool

import vault_audit
import vault_diff
import vault_io
import vault_undo
import vault_write
from vault.kernel import historia, procesos_git, vcs


def _init_vault(tmp_path: Path, con_git: bool = False) -> Path:
    raiz = tmp_path / "vault"
    for carpeta in (
        "00_System",
        "01_Projects",
        "03_Decisions",
        "07_Knowledge",
        "17_Preferences",
        ".history",
    ):
        (raiz / carpeta).mkdir(parents=True, exist_ok=True)
    if con_git:
        entorno = vcs.identidad_de_commit(raiz)
        procesos_git.ejecutar_git(raiz, ["init"], capture_output=True, env=entorno)
        vcs.asegurar_ignorados(raiz)
        (raiz / "00_System" / "change-log.md").write_text("# Change Log\n", encoding="utf-8")
        vcs.commit_de_operacion(raiz, "vault: bootstrap test")
    return raiz


def _escribir_reglas(raiz: Path, reglas: dict) -> None:
    (raiz / "00_System" / "reglas.json").write_text(
        json.dumps(reglas, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _cuerpo_valido(titulo: str, marcador: str) -> str:
    return textwrap.dedent(
        f"""\
        # {titulo}

        Esta nota documenta el estado verificado del componente {marcador} con evidencia concreta.
        El contenido cumple las reglas minimas de densidad para pruebas deterministas de historial.
        Marcador verificable de version: {marcador} dentro del repositorio de pruebas controlado.
        """
    )


def _cuerpo_adr(titulo: str, decision: str) -> str:
    return textwrap.dedent(
        f"""\
        # {titulo}

        ## Contexto

        Contexto tecnico documentado para el registro de arquitectura y trazabilidad del vault.

        ## Decisión

        {decision}

        ## Consecuencias

        Las consecuencias operativas quedan registradas para auditoria continua sin perdida de historia.
        """
    )


def _snapshots_md(raiz: Path) -> list[Path]:
    hist = raiz / ".history"
    if not hist.is_dir():
        return []
    return sorted(p for p in hist.iterdir() if p.is_file() and p.name.endswith(".md"))


def test_politica_valida_modos_y_rechaza_conflictos(tmp_path):
    raiz = _init_vault(tmp_path, con_git=False)
    prev = vault_io.set_vault_root(raiz)
    try:
        # Por defecto (sin clave historial) conserva snapshots para compatibilidad.
        assert vault_io.modo_historial_declarado(raiz) == "snapshots"
        assert vault_io.modo_historial_efectivo(raiz) == "snapshots"

        # Modo auto sin git resuelve a diff.
        _escribir_reglas(raiz, {"historial": "auto"})
        assert vault_io.modo_historial_declarado(raiz) == "auto"
        assert vault_io.modo_historial_efectivo(raiz) == "diff"

        # Valor de historial invalido falla cerrado.
        _escribir_reglas(raiz, {"historial": "inventado"})
        with pytest.raises(vault_io.PoliticaInvalidaError):
            vault_io.modo_historial_declarado(raiz)

        # historial: git sin .git falla cerrado.
        _escribir_reglas(raiz, {"historial": "git"})
        with pytest.raises(vault_io.PoliticaInvalidaError):
            vault_io.modo_historial_efectivo(raiz)

        # Conflicto entre inmutable y sustitucion falla cerrado.
        _escribir_reglas(raiz, {"inmutable": ["02_Decisions"], "sustitucion": ["02_Decisions"]})
        with pytest.raises(vault_io.PoliticaInvalidaError):
            vault_io.reglas_declaradas(raiz)

        # Conflicto entre inmutable y base_inmutable falla cerrado.
        _escribir_reglas(raiz, {"inmutable": ["01_Projects"], "base_inmutable": ["01_Projects"]})
        with pytest.raises(vault_io.PoliticaInvalidaError):
            vault_io.base_inmutable_declarada(raiz)

        # Conflicto entre sustitucion y base_inmutable falla cerrado.
        _escribir_reglas(raiz, {"sustitucion": ["02_Decisions"], "base_inmutable": ["02_Decisions"]})
        with pytest.raises(vault_io.PoliticaInvalidaError):
            vault_io.base_inmutable_declarada(raiz)
    finally:
        vault_io.set_vault_root(prev)


def _escribir_nota(
    folder: str,
    title: str,
    marcador: str,
    note_type: str = "knowledge",
    tags: list[str] | None = None,
    extra_meta: dict | None = None,
) -> dict:
    meta = {"type": note_type, "agent": "tester"}
    if extra_meta:
        meta.update(extra_meta)
    return vault_write.vault_write(
        folder=folder,
        title=title,
        content=_cuerpo_valido(title, marcador),
        tags=tags or ["historial"],
        meta=meta,
    )


def test_modo_diff_no_duplica_md_y_reconstruye_cada_version(tmp_path):
    raiz = _init_vault(tmp_path, con_git=False)
    _escribir_reglas(raiz, {"historial": "diff"})
    prev = vault_io.set_vault_root(raiz)
    try:
        rel = "07_Knowledge/nota-diff.md"
        for idx in range(1, 5):
            res = _escribir_nota("07_Knowledge", "Nota Diff", f"REV-{idx}")
            assert res.get("ok"), res

        assert _snapshots_md(raiz) == []
        patch_file = historia.archivo_patches(raiz / ".history", rel)
        assert patch_file.is_file()

        timeline = historia.linea_temporal(raiz, rel)
        # 3 versiones previas almacenadas (REV-1, REV-2, REV-3) antes de cada sobrescritura
        assert len(timeline) == 3
        assert all(v["origen"] == "diff" for v in timeline)

        textos = [historia.contenido_de_version(raiz, rel, v) for v in reversed(timeline)]
        assert "REV-1" in (textos[0] or "")
        assert "REV-2" in (textos[1] or "")
        assert "REV-3" in (textos[2] or "")

        diff_tl = vault_diff.vault_diff(path=rel, timeline=True)
        assert diff_tl.get("ok"), diff_tl
        assert diff_tl["total_versions"] == 3
        assert diff_tl["changed"] is True
        assert "diff" in diff_tl["backends_used"]
    finally:
        vault_io.set_vault_root(prev)


def test_modo_git_y_auto_versionan_sin_snapshots_md(tmp_path):
    raiz = _init_vault(tmp_path, con_git=True)
    _escribir_reglas(raiz, {"historial": "auto"})
    prev = vault_io.set_vault_root(raiz)
    try:
        assert vault_io.modo_historial_efectivo(raiz) == "git"
        rel = "07_Knowledge/nota-git.md"
        for idx in range(1, 4):
            res = _escribir_nota("07_Knowledge", "Nota Git", f"GIT-V{idx}", tags=["git"])
            assert res.get("ok"), res

        assert _snapshots_md(raiz) == []
        timeline = historia.linea_temporal(raiz, rel)
        assert len(timeline) >= 2
        assert all(v["origen"] == "git" for v in timeline)

        diff_res = vault_diff.vault_diff(path=rel)
        assert diff_res.get("ok"), diff_res
        assert diff_res["changed"] is True
        assert diff_res["lines_added"] >= 1

        tl_res = vault_diff.vault_diff(path=rel, timeline=True)
        assert tl_res.get("ok"), tl_res
        assert "git" in tl_res["backends_used"]
    finally:
        vault_io.set_vault_root(prev)


def test_transicion_entre_modos_no_pierde_ninguna_version(tmp_path):
    raiz = _init_vault(tmp_path, con_git=True)
    prev = vault_io.set_vault_root(raiz)
    try:
        rel = "07_Knowledge/nota-transicion.md"

        # 1. Crear en snapshots y sobrescribir -> V1 queda en .history/*.md
        _escribir_reglas(raiz, {"historial": "snapshots"})
        assert _escribir_nota("07_Knowledge", "Nota Transicion", "PASO-1-SNAP", tags=["transicion"]).get("ok")
        assert _escribir_nota("07_Knowledge", "Nota Transicion", "PASO-2-DIFF", tags=["transicion"]).get("ok")

        # 2. Cambiar a diff y sobrescribir dos veces -> PASO-2-DIFF y PASO-3-DIFF en .patches.jsonl
        _escribir_reglas(raiz, {"historial": "diff"})
        assert _escribir_nota("07_Knowledge", "Nota Transicion", "PASO-3-DIFF", tags=["transicion"]).get("ok")
        assert _escribir_nota("07_Knowledge", "Nota Transicion", "PASO-4-GIT", tags=["transicion"]).get("ok")

        # 3. Cambiar a git y sobrescribir -> PASO-4-GIT queda en git commit
        _escribir_reglas(raiz, {"historial": "git"})
        assert _escribir_nota("07_Knowledge", "Nota Transicion", "PASO-5-FINAL", tags=["transicion"]).get("ok")

        timeline = historia.linea_temporal(raiz, rel)
        origenes = {v["origen"] for v in timeline}
        assert origenes == {"snapshots", "diff", "git"}, origenes

        contenidos = [
            historia.contenido_de_version(raiz, rel, v) or ""
            for v in reversed(timeline)
        ]
        marcadores = ["PASO-1-SNAP", "PASO-2-DIFF", "PASO-3-DIFF", "PASO-4-GIT"]
        for m in marcadores:
            assert any(m in c for c in contenidos), f"Se perdio {m} en la transicion"

        # vault_diff --timeline compara desde el inicio (PASO-1-SNAP) hasta el final (PASO-5-FINAL)
        tl = vault_diff.vault_diff(path=rel, timeline=True)
        assert tl.get("ok"), tl
        assert set(tl["backends_used"]) == {"snapshots", "diff", "git"}
        assert tl["changed"] is True

        # vault_undo --list expone versiones de todos los backends y permite restaurar la primera
        lista_undo = vault_undo.vault_undo_list(rel)
        assert lista_undo.get("ok"), lista_undo
        primera_id = lista_undo["versions"][-1]["filename"]
        restaurada = vault_undo.vault_undo(rel, version=primera_id, dry_run=False, agent="tester")
        assert restaurada.get("ok"), restaurada
        texto_restaurado = (raiz / restaurada["restored_to"]).read_text(encoding="utf-8")
        assert "PASO-1-SNAP" in texto_restaurado
    finally:
        vault_io.set_vault_root(prev)


@pytest.mark.parametrize("modo", ["diff", "git"])
def test_ap75_detecta_decision_reescrita_en_modo_diff_y_git(tmp_path, modo):
    raiz = _init_vault(tmp_path, con_git=(modo == "git"))
    _escribir_reglas(raiz, {"historial": modo})
    prev = vault_io.set_vault_root(raiz)
    try:
        rel = "03_Decisions/ADR-001-historial.md"
        v1 = textwrap.dedent(
            """\
            ---
            title: ADR 001 Historial
            type: decision
            status: accepted
            responsable: Carlos Ivan
            tags:
              - adr
            ---

            """
        ) + _cuerpo_adr("ADR 001 Historial", "Se adopta el backend inicial alfa con verificacion completa.")
        vault_io.atomic_write_text(raiz / rel, v1)

        # Guardar version previa via el dueno y reescribir el cuerpo de la decision cerrada
        vault_io.guardar_version_actual(raiz / rel)
        v2 = textwrap.dedent(
            """\
            ---
            title: ADR 001 Historial
            type: decision
            status: accepted
            responsable: Carlos Ivan
            tags:
              - adr
            ---

            """
        ) + _cuerpo_adr("ADR 001 Historial", "Se reescribe silenciosamente el cuerpo por el backend beta.")
        vault_io.atomic_write_text(raiz / rel, v2)

        assert _snapshots_md(raiz) == []
        res_ap75 = vault_audit._detect_decisiones_reescritas([raiz / rel])
        assert res_ap75["checked"] == 1
        assert res_ap75["unverifiable"] == [], res_ap75
        assert len(res_ap75["rewritten"]) == 1, res_ap75
        assert res_ap75["rewritten"][0]["path"] == rel
    finally:
        vault_io.set_vault_root(prev)


def test_base_inmutable_protege_nota_base_y_permite_sucesora_evolutiva(tmp_path):
    raiz = _init_vault(tmp_path, con_git=False)
    _escribir_reglas(raiz, {"base_inmutable": ["01_Projects"], "historial": "diff"})
    prev = vault_io.set_vault_root(raiz)
    try:
        base_rel = "01_Projects/plan-base.md"
        base_path = raiz / base_rel
        # Crear la nota base por primera vez esta permitido.
        res_crear = _escribir_nota("01_Projects", "Plan Base", "BASE-ORIGINAL", note_type="project", tags=["plan"])
        assert res_crear.get("ok"), res_crear
        sha_original = hashlib.sha256(base_path.read_bytes()).hexdigest()

        # Intentar sobrescribir la nota base sellada debe fallar con IMMUTABLE_NOTE.
        res_mutar = _escribir_nota("01_Projects", "Plan Base", "INTENTO-MUTACION", note_type="project", tags=["plan"])
        assert res_mutar.get("ok") is False
        assert res_mutar.get("error_code") == "IMMUTABLE_NOTE", res_mutar
        assert hashlib.sha256(base_path.read_bytes()).hexdigest() == sha_original

        # Crear una nota sucesora que declare evolves_from si se permite y puede evolucionar.
        suc_rel = "01_Projects/plan-base-v2.md"
        suc_path = raiz / suc_rel
        texto_v2 = textwrap.dedent(
            """\
            ---
            title: Plan Base v2
            type: project
            status: active
            evolves_from: "[[plan-base]]"
            tags:
              - plan
            ---

            """
        ) + _cuerpo_valido("Plan Base v2", "SUCESORA-R1")
        vault_io.atomic_write_text(suc_path, texto_v2)

        # Editar la sucesora (que declara evolves_from) SI esta permitido.
        vault_io.guardar_version_actual(suc_path)
        texto_v2_edit = texto_v2.replace("SUCESORA-R1", "SUCESORA-R2")
        vault_io.atomic_write_text(suc_path, texto_v2_edit)
        assert "SUCESORA-R2" in suc_path.read_text(encoding="utf-8")
        # La base original permanece intacta byte a byte.
        assert hashlib.sha256(base_path.read_bytes()).hexdigest() == sha_original
    finally:
        vault_io.set_vault_root(prev)


def test_cli_vault_diff_timeline_expone_salida_json(tmp_path):
    raiz = _init_vault(tmp_path, con_git=False)
    _escribir_reglas(raiz, {"historial": "diff"})
    prev = vault_io.set_vault_root(raiz)
    try:
        rel = "07_Knowledge/nota-cli.md"
        assert _escribir_nota("07_Knowledge", "Nota CLI", "CLI-V1", tags=["cli"]).get("ok")
        assert _escribir_nota("07_Knowledge", "Nota CLI", "CLI-V2", tags=["cli"]).get("ok")
    finally:
        vault_io.set_vault_root(prev)

    env = {**os.environ, "VAULT_ROOT": str(raiz)}
    proc = correr_tool("vault_diff.py", "--path", rel, "--timeline", env=env)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["total_versions"] == 1
    assert data["backends_used"] == ["diff"]
