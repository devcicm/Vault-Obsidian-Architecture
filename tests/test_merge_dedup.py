"""O2 — `vault_merge --action dedup` deja de fusionar artefactos generados
y respalda antes de borrar.

Dos defectos medidos sobre una copia del sandbox en la ola O2:

1. El barrido agrupaba por stem y los 23 `index.md` de sección comparten el
   suyo: `dedup` los fusionaba todos en uno y borraba los otros 22. Es la
   misma clase de daño que `vault_append` ya rechaza — el criterio lo posee
   `vault.kernel.registry.es_artefacto_derivado`.
2. El borrado de la duplicada no dejaba versión: el catálogo promete «Crea
   backups antes de modificar» y la rama `dedup` no lo cumplía (la rama
   `merge --conflict overwrite` sí, y desde v41.12 también el canónico).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))

from vault.kernel import bloqueo  # noqa: E402


def _vault(tmp_path):
    raiz = tmp_path / "vault"
    for d in ("00_System", "03_Decisions", "07_Knowledge"):
        (raiz / d).mkdir(parents=True)
    return raiz


def _nota(ruta: Path, titulo: str, cuerpo: str, actualizado: str) -> None:
    ruta.write_text(
        f"---\ntitle: {titulo}\nupdatedAt: {actualizado}\n---\n\n"
        f"# {titulo}\n\n{cuerpo}\n", encoding="utf-8")


def _dedup(raiz: Path, tmp_path: Path) -> dict:
    (tmp_path / "cwd").mkdir(exist_ok=True)
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_merge.py"), "--action", "dedup"],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(tmp_path / "cwd"), timeout=120,
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


def test_dedup_no_fusiona_los_indices_de_seccion(tmp_path):
    """Los `index.md` de sección comparten stem y NO son duplicados."""
    raiz = _vault(tmp_path)
    (raiz / "00_System" / "index.md").write_text("# Índice de sistema\n", encoding="utf-8")
    (raiz / "03_Decisions" / "index.md").write_text("# Índice de decisiones\n", encoding="utf-8")

    r = _dedup(raiz, tmp_path)

    assert r["ok"] and r["merged"] == 0, r
    assert (raiz / "00_System" / "index.md").exists()
    assert (raiz / "03_Decisions" / "index.md").exists()
    assert "sistema" in (raiz / "00_System" / "index.md").read_text(encoding="utf-8")


def test_dedup_si_fusiona_el_duplicado_real(tmp_path):
    """La cura no congeló la herramienta: el duplicado de verdad se fusiona."""
    raiz = _vault(tmp_path)
    _nota(raiz / "07_Knowledge" / "guia.md", "Guía A", "cuerpo A",
          "2026-10-20T10:00:00Z")
    _nota(raiz / "03_Decisions" / "guia.md", "Guía B", "cuerpo B",
          "2026-10-20T09:00:00Z")

    r = _dedup(raiz, tmp_path)

    assert r["ok"] and r["merged"] == 1, r
    vivas = sorted(p.relative_to(raiz).as_posix() for p in raiz.rglob("guia.md"))
    assert vivas == ["07_Knowledge/guia.md"], vivas
    assert "cuerpo B" in (raiz / "07_Knowledge" / "guia.md").read_text(encoding="utf-8")


def test_dedup_guarda_la_version_de_lo_que_borra(tmp_path):
    """La promesa del catálogo: respaldo antes de modificar — también aquí."""
    raiz = _vault(tmp_path)
    _nota(raiz / "07_Knowledge" / "guia.md", "Guía A", "cuerpo A",
          "2026-10-20T10:00:00Z")
    _nota(raiz / "03_Decisions" / "guia.md", "Guía B", "cuerpo B",
          "2026-10-20T09:00:00Z")

    _dedup(raiz, tmp_path)

    historial = sorted(p.name for p in (raiz / ".history").glob("*guia*"))
    assert any("03_Decisions" in h for h in historial), historial
    assert any("07_Knowledge" in h for h in historial), historial
    borrada = next(p for p in (raiz / ".history").glob("*03_Decisions*guia*"))
    assert "cuerpo B" in borrada.read_text(encoding="utf-8")


def test_dedup_con_el_canonico_tomado_no_borra_nada(tmp_path):
    """Sin lock no se borra la duplicada: nada desaparece sin escribirse."""
    raiz = _vault(tmp_path)
    _nota(raiz / "07_Knowledge" / "guia.md", "Guía A", "cuerpo A",
          "2026-10-20T10:00:00Z")
    _nota(raiz / "03_Decisions" / "guia.md", "Guía B", "cuerpo B",
          "2026-10-20T09:00:00Z")
    canonico = raiz / "07_Knowledge" / "guia.md"
    ocupado = canonico.parent / ".locks" / f"{canonico.name}.lock"
    ocupado.mkdir(parents=True)
    (ocupado / "owner.json").write_text(
        json.dumps(bloqueo.ficha_del_dueno("otro")), encoding="utf-8")

    r = _dedup(raiz, tmp_path)

    assert r["ok"] and r["merged"] == 0, r
    assert r.get("locked") == ["07_Knowledge/guia.md"], r
    assert (raiz / "03_Decisions" / "guia.md").exists(), (
        "la duplicada se borró sin poder escribir el canónico")
