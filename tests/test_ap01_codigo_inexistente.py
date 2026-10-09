"""AP-01 — una nota que declara código que no existe en el repo sale nombrada.

AP-01 es documentación que describe código inexistente. Entera no es decidible:
saber si una función descrita en prosa existe exige leer la prosa. Pero una
parte sí lo es, y ya estaba escrita en la nota: `files:` declara qué ficheros
documenta. Si uno de ellos no está en el disco del repo,
la nota afirma algo sobre código que no existe. `vault_drift_detect --mode
vigencia` ya recorría esas relaciones para AP-08 y las que git no conocía las
listaba sin nombre en `sin_historia`; ahora separa las que apuntan a un
fichero ausente y las nombra AP-01.

Lo que sigue sin medirse —la referencia en prosa, la firma que no coincide—
queda declarado en el catálogo como `cobertura_parcial`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ap08_vigencia import SCRIPTS, _nota, _proyecto, _tool  # noqa: E402


def test_ap01_files_que_no_existe_se_nombra(tmp_path):
    raiz, repo = _proyecto(tmp_path)
    base = "project: demo\nstatus: active\nupdatedAt: 2026-04-01T00:00:00Z"
    _nota(raiz, "inventada", base + "\nfiles:\n  - no-existe.py")
    _nota(raiz, "mezcla", base + "\nfiles:\n  - viejo.py\n  - fantasma.py")
    # Existe en disco pero git aún no lo conoce: no es código inexistente.
    (repo / "sin-commit.py").write_text("x = 1\n", encoding="utf-8")
    _nota(raiz, "sin-commit", base + "\nfiles:\n  - sin-commit.py")

    rc, r = _tool(raiz, "vault_drift_detect", "--project", "demo", "--mode", "vigencia")
    assert rc == 0 and r["ok"] is True, r
    ap01 = {d["path"]: d["inexistentes"] for d in r["codigo_inexistente"]}
    assert ap01 == {"07_Knowledge/inventada.md": ["no-existe.py"],
                    "07_Knowledge/mezcla.md": ["fantasma.py"]}
    assert all(d["norm"] == "AP-01" for d in r["codigo_inexistente"])
    assert r["summary"]["codigo_inexistente"] == 2
    # `sin_historia` sigue diciendo lo que decía: no se le quita nada.
    assert sorted(d["path"] for d in r["sin_historia"]) == [
        "07_Knowledge/inventada.md", "07_Knowledge/sin-commit.md"]
    assert r["action_required"] is True


def test_ap01_el_catalogo_nombra_al_detector():
    sys.path.insert(0, str(SCRIPTS))
    from vault_norms_catalog import NORM_CATALOG as NORMS
    ap01 = next(n for n in NORMS if n["code"] == "AP-01")
    assert "vault_drift_detect" in ap01["tools_detecting"]
    assert "cobertura_descubierta" not in ap01
    assert ap01.get("cobertura_parcial")


def test_ap01_si_no_resuelve_ningun_files_sospecha_de_la_base(tmp_path):
    """Medido en la regla 7 (copia de /ans): con `--path` en la raíz del repo y
    los `files:` escritos desde `ANS/ans-core/src`, las siete notas salían
    como AP-01. Con la base buena, cero. Cuando no resuelve ni uno, lo más
    probable es la base y no siete notas inventadas: se dice, sin ocultar la
    lista."""
    raiz, _ = _proyecto(tmp_path)
    base = "project: demo\nstatus: active\nupdatedAt: 2026-04-01T00:00:00Z"
    _nota(raiz, "a", base + "\nfiles:\n  - src/viejo.py")
    _nota(raiz, "b", base + "\nfiles:\n  - src/nuevo.py")
    rc, r = _tool(raiz, "vault_drift_detect", "--project", "demo", "--mode", "vigencia")
    assert rc == 0 and r["summary"]["codigo_inexistente"] == 2, r
    assert "--path" in r.get("pista", ""), r

    _nota(raiz, "c", base + "\nfiles:\n  - viejo.py")
    rc, r = _tool(raiz, "vault_drift_detect", "--project", "demo", "--mode", "vigencia")
    assert r["summary"]["codigo_inexistente"] == 2 and "pista" not in r, r
