"""AP-50 — decisión duplicada sin dueño declarado, con su puerta.

AP-05 habla de un **dato** con dos fuentes, y se nota porque las dos copias
divergen. Esto es una **decisión** —qué valores son válidos, cuál es el
default, cómo se escapa un campo— tomada en más de un punto de uso sin que
ningún registro diga quién manda; se nota cuando ya divergió, que es tarde.

Estas pruebas ejercen la regla de los tres guards que la hacen cumplir, no
repiten su resultado. Y una comprueba lo que la norma afirma sobre el repo,
que es lo que la separa de una opinión bien redactada.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_arch as arch  # noqa: E402
import vault_vocabulario as voc  # noqa: E402
from vault_norms import NORM_CATALOG  # noqa: E402


def _norma():
    return next(n for n in NORM_CATALOG if n["code"] == "AP-50")


# ── La norma existe y cumple las reglas del repo ─────────────────────────────

def test_ap50_esta_en_el_catalogo_con_enforcement_real():
    """Ninguna norma nueva puede tener enforcement `manual` (regla 5)."""
    n = _norma()
    assert n["enforcement"] == "guard+audit"
    assert n["severity"] == "high"
    assert n["introduced_version"] == "v40.1"


def test_ap50_nombra_la_tool_que_la_hace_cumplir():
    """Una norma cuyo `tools_enforcing` no existe sería AP-42."""
    n = _norma()
    assert "vault_arch" in n["tools_enforcing"]
    assert (REPO_ROOT / "scripts" / "vault_arch.py").exists()


# ── Los tres detectores, ejercidos sobre material de mentira ─────────────────

def _copias(fuente: str, tmp_path: Path, monkeypatch) -> list[str]:
    (tmp_path / "vault_falso.py").write_text(fuente, encoding="utf-8")
    # v40.9: el alcance de los guards ya no es un glob por sitio sino
    # `vault_arch.arboles_medidos()`. Se redirige el alcance, no el
    # directorio, para que el guard vea exactamente el módulo de prueba.
    monkeypatch.setattr(arch, "arboles_medidos",
                        lambda: sorted(tmp_path.glob("vault_*.py")))
    monkeypatch.setattr(arch, "_modulos_en_disco", lambda: ["vault_falso"])
    return [c["vocabulary"] for c in arch.copias_de_vocabulario()]


def test_un_literal_que_reproduce_un_vocabulario_es_una_copia(
    tmp_path, monkeypatch
):
    valores = list(voc.valores("severidad"))
    fuente = f"SEVERITIES = {valores!r}\n"
    assert "severidad" in _copias(fuente, tmp_path, monkeypatch)


def test_el_orden_no_disfraza_la_copia(tmp_path, monkeypatch):
    """Reordenar la lista no la convierte en otra decisión."""
    valores = list(reversed(voc.valores("severidad")))
    fuente = f"SEVERITIES = {valores!r}\n"
    assert "severidad" in _copias(fuente, tmp_path, monkeypatch)


def test_una_lista_que_no_es_un_vocabulario_no_se_denuncia(
    tmp_path, monkeypatch
):
    """El guard no puede volverse ruido: sin coincidencia, sin hallazgo."""
    fuente = "COLORES = ['rojo', 'verde', 'azul']\n"
    assert _copias(fuente, tmp_path, monkeypatch) == []


def test_una_lectura_de_entorno_sin_registro_se_denuncia(
    tmp_path, monkeypatch
):
    fuente = "import os\nX = os.environ.get('VAULT_INVENTADA', '1')\n"
    (tmp_path / "vault_falso.py").write_text(fuente, encoding="utf-8")
    # v40.9: el alcance de los guards ya no es un glob por sitio sino
    # `vault_arch.arboles_medidos()`. Se redirige el alcance, no el
    # directorio, para que el guard vea exactamente el módulo de prueba.
    monkeypatch.setattr(arch, "arboles_medidos",
                        lambda: sorted(tmp_path.glob("vault_*.py")))
    monkeypatch.setattr(arch, "_modulos_en_disco", lambda: ["vault_falso"])
    nombres = [x["variable"] for x in arch.lecturas_de_entorno_sin_registro()]
    assert "VAULT_INVENTADA" in nombres


def test_todo_vocabulario_declara_un_contexto_que_existe():
    """La otra mitad de la norma: sin dueño no hay quién decida el cambio."""
    contextos = set(arch.CONTEXTS)
    for nombre, v in voc.VOCABULARIOS.items():
        assert v.contexto in contextos, f"{nombre} apunta a {v.contexto}"
    assert arch.vocabularios_sin_dueno() == []


# ── Lo que la norma afirma sobre este repo ───────────────────────────────────

def test_el_repo_esta_en_cero_y_la_puerta_no_tiene_baseline():
    """La norma dice **0** en las tres medidas. Se comprueba, no se cree.

    Sin baseline a propósito: las catorce copias se saldaron al declarar el
    registro, así que la puerta nace en cero y una baseline solo serviría
    para admitir la número quince.
    """
    assert arch.copias_de_vocabulario() == []
    assert arch.lecturas_de_entorno_sin_registro() == []
    assert arch.vocabularios_sin_dueno() == []
