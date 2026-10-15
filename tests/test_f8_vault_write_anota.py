"""F8 (no repudio): `vault_write` anota en `.change-log.json` lo que crea y lo
que actualiza.

El registro (`vault_fundamentals_catalog`, F8) pide que «al menos una entrada en
.change-log.json referencia la ruta de la nota», y `vault_quality_check` lo aplica
a toda nota viva. `vault_write` no anotaba nada, así que un vault recién poblado
puntuaba 0 en `non_repudiation` en todas sus notas (26 de 26, medido el
2026-10-14 con la wheel instalada). El usuario eligió el 2026-10-15 que el
write path deje la constancia (opción a) en vez de rebajar el criterio a «1 por
borrado», y la deuda `f8_criterio_sin_decidir` se salda con este test.

La anotación es un campo nuevo del contrato de `vault_write` (`change_log`, con
el `id` y la `action` de la entrada); si la bitácora falla, la nota ya está
escrita y el fallo se publica en `change_log_error` en vez de tumbar la
escritura, como hace la bitácora de etiquetas de AP-39.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _escribir(raiz: Path, contenido: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_AGENT="agente-f8")
    p = subprocess.run([sys.executable, str(SCRIPTS / "vault_write.py"),
                        "--folder", "07_Knowledge", "--title", "Nota F8",
                        "--tags", "f8",
                        "--content", (f"{contenido}\n\nLa segunda línea aporta contexto real a la prueba.\n\n"
                                      "La tercera línea cierra la nota de prueba sin relleno.")],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    assert p.returncode == 0, p.stdout + p.stderr
    return json.loads(p.stdout)


def _vault(tmp_path: Path) -> Path:
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    (raiz / "07_Knowledge").mkdir()
    return raiz


def test_vault_write_anota_la_creacion_y_la_actualizacion(tmp_path):
    raiz = _vault(tmp_path)
    alta = _escribir(raiz, "Primera versión.")
    cambio = _escribir(raiz, "Segunda versión.")
    log = json.loads((raiz / "00_System" / ".change-log.json").read_text(encoding="utf-8"))
    assert [(e["action"], e["path"], e["agent"]) for e in log] == [
        ("created", alta["path"], "agente-f8"),
        ("updated", alta["path"], "agente-f8"),
    ]
    assert alta["change_log"] == {"id": log[0]["id"], "action": "created"}
    assert cambio["change_log"] == {"id": log[1]["id"], "action": "updated"}


def test_una_nota_escrita_por_vault_write_puntua_en_no_repudio(tmp_path):
    import vault_quality_check as q

    raiz = _vault(tmp_path)
    alta = _escribir(raiz, "Contenido.")
    log = json.loads((raiz / "00_System" / ".change-log.json").read_text(encoding="utf-8"))
    rutas = {e["path"] for e in log}
    assert q._score_non_repudiation(alta["path"], rutas)[0] == 1.0


def test_f8_registro_matriz_y_manifiesto_dicen_lo_mismo():
    from vault_fundamentals import TRACEABILITY_MATRIX
    from vault_fundamentals_catalog import FUNDAMENTALS

    f8 = next(f for f in FUNDAMENTALS if f["id"] == "F8")
    assert any("referencia la ruta de la nota" in v for v in f8["verifies"])
    fila_matriz = next(r for r in TRACEABILITY_MATRIX if r["concept"] == "No repudio (F8)")
    fila_doc = next(l for l in (ROOT / "vault-obsidian-architecture.md").read_text(
        encoding="utf-8").splitlines() if l.startswith("| No repudio (F8)"))
    assert fila_matriz["threshold"] == "1 por nota"
    assert "| 1 por nota |" in fila_doc
    assert "por borrado" not in fila_doc
