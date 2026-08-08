"""AP-46 — el heal que repara el frontmatter que dejaron los writers viejos.

La norma prohíbe escribir frontmatter a mano; este heal existe para el material
que ya se escribió así antes de que la norma tuviera guard. Repara **dos clases
y ninguna más**, y las dos salieron de medir un vault real ajeno al estándar
(regla 7) — no de imaginar roturas posibles:

* `escalar_sin_escapar` — `title: ADR-001: Adopción de MCP` rompe el YAML porque
  el segundo `:` abre un mapa donde había un escalar.
* `bloque_sin_cerrar` — el `---` de apertura nunca cierra, así que el bloque
  entero se lee como cuerpo y la nota queda sin metadatos.

El caso que costó la ronda está en `test_no_deduce_la_clase_por_la_presencia_de_otro_guion`:
deducir la clase mirando si hay un `\\n---` más abajo parecía obvio y clasificaba
mal **tres de las cuatro** notas rotas del vault real, porque llevan una regla
horizontal en el cuerpo. Ahora las dos hipótesis se prueban y gana la que
verifique. Es AP-44 dentro del propio heal: el criterio es el resultado que ve el
consumidor —`yaml.safe_load` sobre el bloque— y no la corazonada del detector.
"""

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_norms  # noqa: E402


CUERPO = "\n# Título\n\nTexto del cuerpo.\n\n---\n\nMás cuerpo tras una regla horizontal.\n"

SANA = "---\ntitle: Nota sana\nstatus: active\n---\n" + CUERPO

SIN_ESCAPAR = "---\ntitle: ADR-001: Adopción de MCP\nstatus: active\n---\n" + CUERPO

SIN_CERRAR = "---\ntitle: Nota sin cierre\nstatus: active\n" + CUERPO


def _bloque(texto: str) -> dict:
    """Lee el frontmatter como lo lee el consumidor, no como lo lee el heal."""
    resto = texto.split("\n", 1)[1]
    return yaml.safe_load(resto[: resto.find("\n---") + 1])


def _cuerpo(texto: str) -> str:
    i = texto.find("\n#")
    return texto[i:] if i != -1 else ""


# ── El plan ────────────────────────────────────────────────────────────────

def test_una_nota_sana_no_se_toca():
    assert vault_norms._planificar_ap46(SANA) is None


@pytest.mark.parametrize("raw,clase", [
    (SIN_ESCAPAR, "escalar_sin_escapar"),
    (SIN_CERRAR, "bloque_sin_cerrar"),
])
def test_repara_las_dos_clases_y_el_resultado_parsea(raw, clase):
    plan = vault_norms._planificar_ap46(raw)
    assert plan is not None, f"{clase} debería ser reparable"
    assert plan["clase"] == clase
    datos = _bloque(plan["texto"])
    assert isinstance(datos, dict) and datos
    assert sorted(datos) == plan["claves"]


@pytest.mark.parametrize("raw", [SIN_ESCAPAR, SIN_CERRAR])
def test_el_cuerpo_no_se_toca(raw):
    plan = vault_norms._planificar_ap46(raw)
    assert _cuerpo(plan["texto"]) == _cuerpo(raw)


def test_no_deduce_la_clase_por_la_presencia_de_otro_guion():
    """La regresión, aislada.

    `SIN_CERRAR` lleva un `---` en el cuerpo. La versión anterior lo tomaba por
    el cierre del bloque, concluía "bloque cerrado que no parsea" e intentaba
    reescapar escalares — que no arregla nada aquí. Las tres notas del vault
    real que caían en esto acababan en `skipped`.
    """
    assert "\n---" in CUERPO, "el fixture pierde su sentido sin la regla horizontal"
    plan = vault_norms._planificar_ap46(SIN_CERRAR)
    assert plan["clase"] == "bloque_sin_cerrar"


def test_no_inventa_una_reparacion_cuando_no_sabe():
    """Sin claves con forma de frontmatter no hay nada que cerrar ni que escapar."""
    assert vault_norms._planificar_ap46("---\n: : :\n" + CUERPO) is None


# ── La tool ────────────────────────────────────────────────────────────────

def _vault(tmp_path: Path) -> Path:
    (tmp_path / "03_Decisions").mkdir(parents=True)
    (tmp_path / "03_Decisions" / "rota.md").write_text(SIN_ESCAPAR, encoding="utf-8")
    (tmp_path / "03_Decisions" / "abierta.md").write_text(SIN_CERRAR, encoding="utf-8")
    (tmp_path / "03_Decisions" / "sana.md").write_text(SANA, encoding="utf-8")
    return tmp_path


def test_en_seco_no_escribe_nada(tmp_path):
    raiz = _vault(tmp_path)
    antes = {p: p.read_bytes() for p in raiz.rglob("*.md")}
    r = vault_norms.heal_ap46(root=raiz)
    assert r["ok"] and r["applied"] is False
    assert r["would_heal"] == 2 and r["healed"] == 0
    assert all(p.read_bytes() == b for p, b in antes.items()), "AP-36: side effect no declarado"


def test_apply_repara_y_deja_copia_dentro_del_vault(tmp_path):
    raiz = _vault(tmp_path)
    originales = {p.name: p.read_text(encoding="utf-8") for p in raiz.rglob("*.md")}

    r = vault_norms.heal_ap46(root=raiz, apply=True)
    assert r["healed"] == 2 and r["applied"] is True

    for nombre in ("rota.md", "abierta.md"):
        texto = (raiz / "03_Decisions" / nombre).read_text(encoding="utf-8")
        datos = _bloque(texto)
        assert isinstance(datos, dict) and datos, f"{nombre} sigue sin parsear"
        assert _cuerpo(texto) == _cuerpo(originales[nombre])

    assert (raiz / "03_Decisions" / "sana.md").read_text(encoding="utf-8") == originales["sana.md"]

    # AP-36: el backup vive DENTRO del vault, nunca junto al script.
    copias = list((raiz / ".history" / "ap46-heal").rglob("*.md"))
    assert len(copias) == 2
    assert {c.read_text(encoding="utf-8") for c in copias} == {SIN_ESCAPAR, SIN_CERRAR}


def test_es_idempotente(tmp_path):
    raiz = _vault(tmp_path)
    vault_norms.heal_ap46(root=raiz, apply=True)
    assert vault_norms.heal_ap46(root=raiz)["would_heal"] == 0


def test_una_raiz_inexistente_falla_por_el_catalogo(tmp_path):
    """AP-52: el fallo sale con `error_code`, no como una frase suelta."""
    r = vault_norms.heal_ap46(root=tmp_path / "no-existe")
    assert r["ok"] is False
    assert r["error_code"] == "VAULT_NOT_FOUND"
