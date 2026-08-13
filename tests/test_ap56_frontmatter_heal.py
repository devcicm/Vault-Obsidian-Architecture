"""AP-56 — frontmatter presente que el consumidor no puede leer.

La norma no es "el YAML es feo": es que el bloque **está ahí**, se ve al abrir
el fichero, y para el parser la nota no tiene metadatos. Por eso nadie lo
revisa. Estos tests fijan las dos causas que salieron del contraste de regla 7
contra los cuatro vaults consumidores, y —más importante— fijan lo que la tool
se **niega** a hacer: un healer sin negativas escritas acaba inventando dato.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import vault_io  # noqa: E402
import vault_frontmatter_heal as heal_mod  # noqa: E402
from vault_norms import NORM_CATALOG  # noqa: E402

ESCALAR = "---\ntitle: Overview: demo\nid: n1\n---\n\ncuerpo\n"
#: El bloque abre y no cierra. El `---` que aparece es un separador del cuerpo,
#: cientos de líneas más abajo — por eso el parser se traga la nota entera y el
#: mensaje de YAML señala el sitio donde explotó, no donde está el fallo.
SIN_CERRAR = "---\ntitle: demo\nid: n1\n\n# Cuerpo\n\ntexto\n\n---\n\nmás\n"


def _norma(code):
    return next(n for n in NORM_CATALOG if n["code"] == code)


# ── Las dos causas ────────────────────────────────────────────────────────

def test_el_escalar_sin_escapar_se_diagnostica_y_se_repara():
    assert heal_mod.diagnosticar(ESCALAR) is not None
    arreglo = heal_mod.reparar(ESCALAR)
    assert arreglo is not None
    assert arreglo["cause"] == heal_mod.REPARABLE
    assert "title" in arreglo["keys_quoted"]
    assert heal_mod.diagnosticar(arreglo["text"]) is None


def test_el_bloque_sin_cerrar_se_repara_insertando_el_delimitador():
    """La causa que el mensaje de YAML no señala.

    El parser revienta cientos de líneas más abajo, en el cuerpo, así que el
    error apunta al sitio donde explotó y no al sitio donde está el fallo.
    """
    assert heal_mod.diagnosticar(SIN_CERRAR) is not None
    arreglo = heal_mod.reparar(SIN_CERRAR)
    assert arreglo is not None
    assert arreglo["cause"] == heal_mod.SIN_CERRAR
    assert arreglo["keys_recovered"] == ["title", "id"]
    assert heal_mod.diagnosticar(arreglo["text"]) is None
    # El diff es exactamente una línea insertada: nada del cuerpo se reescribe.
    assert arreglo["text"].count("\n") == SIN_CERRAR.count("\n") + 1


def test_el_limite_declarado_un_bloque_sin_cerrar_y_sin_otro_delimitador():
    """Lo que esta tool NO ve, escrito para que no se descubra dos veces.

    Sin un segundo `---` en ninguna parte del fichero no hay bloque que partir,
    así que la nota es indistinguible de una sin frontmatter (AP-28) sin
    adivinar dónde acaba el bloque — que es justo lo que `_cerrar_bloque` se
    niega a hacer. Se declara como límite, no se disimula con una heurística.
    """
    huerfano = "---\ntitle: demo\nid: n1\n\ncuerpo\n"
    assert heal_mod.diagnosticar(huerfano) is None


# ── Lo que se niega a tocar ───────────────────────────────────────────────

def test_no_se_adivina_un_bloque_escalar_truncado():
    truncado = "---\ndesc: |\n  linea\n   mal sangrada\n\t tab\n---\n\ncuerpo\n"
    if heal_mod.diagnosticar(truncado) is not None:
        assert heal_mod.reparar(truncado) is None


def test_si_el_cuerpo_tambien_parece_frontmatter_no_se_corta():
    """Adivinar dónde acaba el bloque es inventarse dónde empieza la nota."""
    ambiguo = "---\ntitle: demo\nid: n1\notra: x: y\n---\ncuerpo\n"
    arreglo = heal_mod.reparar(ambiguo)
    if arreglo is not None:
        assert arreglo["cause"] == heal_mod.REPARABLE


def test_ninguna_clave_que_ya_se_leia_cambia_de_valor(monkeypatch):
    """La garantía única de la tool, verificada contra un reparador mentiroso.

    Sin esto, "arreglado" significaría solo "ahora parsea", que es lo que dice
    la tool y no lo que dice el dato (AP-44).

    Muerde sobre un bloque que **sí** parseaba: si el bloque revienta entero no
    se leía ninguna clave y no hay nada que conservar — ahí lo que protege es
    la estrechez de `_cerrar_bloque`, no esta comprobación.
    """
    texto = "---\nid: n1\ntitle: sano\n---\n\ncuerpo\n"

    def _mentiroso(bloque):
        return "\nid: OTRO\ntitle: sano\n", ["title"]

    monkeypatch.setattr(heal_mod, "_reparar_bloque", _mentiroso)
    assert heal_mod.reparar(texto) is None


def test_una_nota_sana_no_se_toca():
    sana = "---\ntitle: 'Overview: demo'\n---\n\ncuerpo\n"
    assert heal_mod.diagnosticar(sana) is None


def test_una_nota_sin_bloque_no_es_AP56():
    """Es AP-28, que es ausencia. Confundirlas invierte la reparación."""
    assert heal_mod.diagnosticar("# Solo cuerpo\n") is None


# ── El healer contra un vault, y AP-37 ────────────────────────────────────

def test_el_dry_run_no_escribe_y_lo_dice_en_healed(tmp_path, monkeypatch):
    (tmp_path / "rota.md").write_text(ESCALAR, encoding="utf-8")
    monkeypatch.setattr(vault_io, "get_vault_root", lambda: tmp_path)
    monkeypatch.setattr(heal_mod, "get_vault_root", lambda: tmp_path)

    seco = heal_mod.heal(apply=False)
    assert seco["repaired_count"] == 1
    assert seco["healed"] == 0
    assert (tmp_path / "rota.md").read_text(encoding="utf-8") == ESCALAR

    aplicado = heal_mod.heal(apply=True)
    assert aplicado["healed"] == 1
    assert heal_mod.diagnosticar(
        (tmp_path / "rota.md").read_text(encoding="utf-8")) is None


def test_una_instantanea_congelada_no_la_repara_nadie(tmp_path, monkeypatch):
    """Reescribir una instantánea la deja de ser: su valor es no cambiar."""
    snap = tmp_path / ".history" / "rota.md"
    snap.parent.mkdir(parents=True)
    snap.write_text(ESCALAR, encoding="utf-8")
    monkeypatch.setattr(heal_mod, "get_vault_root", lambda: tmp_path)

    resultado = heal_mod.heal(apply=True)
    assert resultado["repaired_count"] == 0
    assert snap.read_text(encoding="utf-8") == ESCALAR


# ── La norma en el catálogo ───────────────────────────────────────────────

def test_ap56_esta_en_el_catalogo_con_enforcement_real():
    n = _norma("AP-56")
    assert n["enforcement"] in {"guard", "audit", "guard+audit", "recommended"}
    assert "vault_frontmatter_heal" in n["tools_detecting"]


def test_ap56_y_ap28_se_distinguen_en_las_dos_direcciones():
    """Quien lea AP-28 tiene que ver la diferencia, no solo quien lea AP-56."""
    assert "AP-28" in _norma("AP-56").get("distinguido_de", {})
    assert "AP-56" in _norma("AP-28").get("distinguido_de", {})


def test_apply_y_check_a_la_vez_sale_por_el_contrato_de_error():
    """La rama que ninguna prueba pisaba hasta v40.13.

    `emit_error` **construye** el envelope; devolverlo desde `main` hacía que
    `wrap_main` publicara `UNEXPECTED_ERROR` — «fallo interno» sobre un error
    de uso que tiene arreglo, que es justo lo que AP-52 existe para evitar.
    """
    import subprocess
    import sys as _sys
    from pathlib import Path as _Path

    raiz = _Path(__file__).resolve().parents[1]
    r = subprocess.run(
        [_sys.executable, str(raiz / "scripts" / "vault_frontmatter_heal.py"),
         "--apply", "--check"],
        capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1
    assert "CONFLICTING_ARGS" in r.stdout
    assert "UNEXPECTED_ERROR" not in r.stdout
