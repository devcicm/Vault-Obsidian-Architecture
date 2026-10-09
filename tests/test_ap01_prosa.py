"""AP-01 en prosa — una ruta de código citada en el cuerpo que no está en el repo.

`codigo_inexistente` mide lo que la nota declara en `files:`. La referencia
escrita en prosa quedaba fuera, declarada en la `cobertura_parcial` de AP-01.
Una parte es decidible sin interpretar el texto: la ruta citada entre
backticks (`src/pago.py`) se resuelve contra el disco del repo igual que un
`files:`.

Regla 7 (2026-10-09, copias de seis consumidores, solo lectura) — las clases
de ruido que la medida destapó, y cómo se tratan:

- documentación del estándar copiada en el vault: cientos de rutas de
  ejemplo (`src/auth.py`). Se excluye con el criterio canónico.
- notas de clase `registro` o `indice` (sesiones, auditorías, incidentes):
  describen el código **en su fecha**, no afirman que siga ahí.
- bloques de código: muestran, no afirman.
- ruta ausente cuyo nombre de fichero sí está en otro sitio del repo: lo más
  probable es otra base, no código inventado. Se cuenta aparte
  (`prosa_base_ambigua`) y no se nombra AP-01.

Lo que queda se publica como `prosa_inexistente` sin entrar en
`action_required`: la muestra contrastada contra los originales dio ausencias
reales —código archivado o renombrado— junto a rutas de otro repo que no se
pueden distinguir, y un hallazgo sin precisión medida informa, no exige.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ap08_vigencia import _proyecto, _tool  # noqa: E402

FM = "---\ntitle: {t}\nproject: demo\nstatus: active\nupdatedAt: 2026-04-01T00:00:00Z\n---\n# {t}\n\n"


def _escribir(raiz, rel, cuerpo):
    p = raiz / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(FM.format(t=p.stem) + cuerpo + "\n", encoding="utf-8")


def test_ap01_la_ruta_citada_en_prosa_que_no_existe_se_nombra(tmp_path):
    raiz, repo = _proyecto(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "pago.py").write_text("x = 1\n", encoding="utf-8")
    _escribir(raiz, "07_Knowledge/pagos.md",
              "El cobro vive en `src/pago.py` y reintenta en `src/reintento.py`.\n\n"
              "```\nsrc/ejemplo_en_bloque.py\n`src/tambien_en_bloque.py`\n```")
    # El nombre `viejo.py` existe en la raíz del repo: otra base, no inventado.
    _escribir(raiz, "11_Code/viejo.md", "Ver `lib/viejo.py`.")
    # Una sesión cuenta lo que había en su fecha.
    _escribir(raiz, "04_Sessions/2026-04-01.md", "Borrado `src/antiguo.py`.")

    rc, r = _tool(raiz, "vault_drift_detect", "--project", "demo", "--mode", "vigencia")
    assert rc == 0 and r["ok"] is True, r
    assert r["prosa_inexistente"] == [
        {"path": "07_Knowledge/pagos.md", "norm": "AP-01",
         "inexistentes": ["src/reintento.py"]}]
    assert r["summary"]["prosa_inexistente"] == 1
    assert r["summary"]["prosa_base_ambigua"] == 1
    # Informa sin exigir: sin `files:` rotos ni desfases no hay acción.
    assert r["action_required"] is False


def test_ap01_la_cobertura_parcial_declara_la_prosa_medida():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from vault_norms_catalog import NORM_CATALOG
    ap01 = next(n for n in NORM_CATALOG if n["code"] == "AP-01")
    assert "prosa_inexistente" in ap01["cobertura_parcial"]
