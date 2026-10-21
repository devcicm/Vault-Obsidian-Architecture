"""O9 — el material ajeno a las secciones no se audita como notas del vault.

Medido en un vault ajeno real (15.614 ficheros): 75 READMEs de `node_modules`
contaban como notas sin frontmatter y 25 corchetes de dependencias como
AP-24. El barrido crudo sigue siendo el que RESUELVE enlaces (el criterio de
Obsidian: un enlace a `Plataforma/README.md` resuelve y no es un enlace
roto), pero los chequeos de contenido son de las notas: lo que vive fuera de
toda sección tiene veredicto estructural (CN-02), no de metadatos.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import vault_io  # noqa: E402


def _vault(tmp_path):
    raiz = tmp_path / "vault"
    for carpeta in ("00_System", "07_Knowledge", "99_Index"):
        (raiz / carpeta).mkdir(parents=True)
    (raiz / "07_Knowledge" / "nota.md").write_text(
        "---\ntitle: Nota\ntype: knowledge\nstatus: draft\nid: n1\n"
        "createdAt: 2026-10-20T10:00:00.000Z\nupdatedAt: 2026-10-20T10:00:00.000Z\n"
        "cia_integrity: medium\ncia_availability: medium\n"
        "cia_sensitivity: internal\nagent: test\ntags: [x]\n---\n\n"
        "Cuerpo.\n", encoding="utf-8")
    # Material ajeno: un proyecto dentro del vault, con sus README sin
    # frontmatter (el caso de `node_modules`).
    ajeno = raiz / "Plataforma" / "node_modules" / "axios"
    ajeno.mkdir(parents=True)
    (ajeno / "README.md").write_text(
        "# axios\n\n[badge][npm-url] stuff\n", encoding="utf-8")
    (raiz / "Plataforma" / "codigo.py").write_text("print('x')\n", encoding="utf-8")
    return raiz


def test_el_material_ajeno_no_cuenta_como_notas(tmp_path, monkeypatch):
    import vault_audit

    raiz = _vault(tmp_path)
    vault_io.set_vault_root(raiz)
    monkeypatch.setenv("VAULT_ROOT", str(raiz))
    try:
        env = vault_audit.vault_audit()
    finally:
        vault_io.reset_vault_root()

    det = env["issues"]
    sin_frontmatter = [x["path"] for x in det.get("missingFrontmatter", [])]
    assert not any("Plataforma" in p for p in sin_frontmatter), sin_frontmatter
    assert "07_Knowledge/nota.md" not in sin_frontmatter, sin_frontmatter

    # Los corchetes malformados del README ajeno tampoco son AP-24 del vault.
    malformados = [x["path"] for x in det.get("malformedWikilinks", [])]
    assert not any("Plataforma" in p for p in malformados), malformados

    # Y la carpeta sigue INFORMADA: una fila, no 15.000 ficheros.
    fuera = det.get("carpetasFueraDeSeccion") or []
    carpetas = [c["folder"] for c in fuera]
    assert "Plataforma" in carpetas, carpetas


def test_un_enlace_al_material_ajeno_no_es_roto(tmp_path, monkeypatch):
    """El criterio de Obsidian se conserva: un enlace a un README fuera de
    sección RESUELVE (no es un enlace roto)."""
    import vault_audit

    raiz = _vault(tmp_path)
    (raiz / "07_Knowledge" / "nota.md").write_text(
        "---\ntitle: Nota\ntype: knowledge\nstatus: draft\nid: n1\n"
        "createdAt: 2026-10-20T10:00:00.000Z\nupdatedAt: 2026-10-20T10:00:00.000Z\n"
        "cia_integrity: medium\ncia_availability: medium\n"
        "cia_sensitivity: internal\nagent: test\ntags: [x]\n---\n\n"
        "Cuerpo con [[Plataforma/node_modules/axios/README]].\n",
        encoding="utf-8")
    vault_io.set_vault_root(raiz)
    monkeypatch.setenv("VAULT_ROOT", str(raiz))
    try:
        env = vault_audit.vault_audit()
    finally:
        vault_io.reset_vault_root()

    rotos = [b.get("link") for b in env["issues"].get("brokenLinks", [])]
    # El enlace por ruta completa RESUELVE: el fichero existe, aunque viva
    # fuera de las secciones (criterio de Obsidian: lo que hay, resuelve).
    assert "Plataforma/node_modules/axios/README" not in rotos, rotos
