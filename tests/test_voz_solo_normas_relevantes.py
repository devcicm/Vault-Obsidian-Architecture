"""La voz nombra las normas que importan, no todas las que mencionan la tool.

Hallazgo P1 de la nota `norm-injection-relevance-and-noise-assessment`
(2026-11-07): el bloque `vault_says` viaja en **cada** respuesta, y la lista
`norms` enumeraba todas las reglas que mencionan la tool. Medido: una
escritura **correcta** sin cambios producía 27 etiquetas de norma y 1.896
caracteres de bloque — el agente leía un muro de reglas donde no se había
incumplido ninguna.

La regla de la selección:

- **blocked**: solo la norma que bloqueó (es la que se disparó);
- **wrote**: las normas que **ejercen** esa tool;
- **read** / **unknown**: la norma enfocada, y nada más.

Y lo que el bloque no dice: que una norma nombrada se incumplió. Es un
recordatorio, no un veredicto.
"""

from __future__ import annotations

from apoyo import ROOT as REPO_ROOT  # el conftest ya pone el path

from vault.autoria import voz


CATALOGO = [
    {"code": "AP-01", "name": "Documentacion de lo que no existe",
     "severity": "critical", "tools_enforcing": ["vault_write"],
     "tools_detecting": [], "signal": "documenta algo que no existe",
     "prevention": "enlaza lo que existe"},
    {"code": "AP-11", "name": "Nota sin cuerpo",
     "severity": "high", "tools_enforcing": ["vault_write"],
     "tools_detecting": [], "signal": "nota sin cuerpo",
     "prevention": "escribe el contenido"},
    {"code": "AP-20", "name": "Lista de vacios",
     "severity": "medium", "tools_enforcing": [],
     "tools_detecting": ["vault_write"], "signal": "lista vacia",
     "prevention": "rellena la lista"},
    {"code": "AP-36", "name": "Ruta fuera del vault",
     "severity": "critical", "tools_enforcing": [],
     "tools_detecting": ["otra_tool"], "signal": "ruta fuera del vault",
     "prevention": "deriva la ruta del vault"},
]
SEVERIDAD = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _bloque(momento, writes=None, norm_code=None, ok=True):
    payload = {"ok": ok}
    if norm_code:
        payload["norm_code"] = norm_code
    return voz.speak(
        "vault_write", payload, writes or {},
        catalog=CATALOGO, severity_order=SEVERIDAD,
        runtime_root=None, rotation=lambda: 0,
    )


def test_una_escritura_correcta_no_muestra_todas_las_normas():
    """El caso medido: 27 etiquetas y 1.896 caracteres. Ahora, solo las que aplican."""
    bloque = _bloque("read", writes={"written": 0})
    assert bloque is not None
    assert len(bloque["norms"]) == 1, bloque["norms"]
    assert len(bloque["message"]) < 1200, len(bloque["message"])


def test_lo_que_se_escribe_muestra_las_normas_que_ejercen_la_tool():
    """Escribir sí activa recordatorios: los de las normas que aplican."""
    bloque = _bloque("wrote", writes={"written": 3})
    assert bloque is not None
    etiquetas = bloque["norms"]
    assert etiquetas, bloque
    assert len(etiquetas) <= voz.LIMITE_ETIQUETAS, etiquetas
    # Las que ejercen la tool, no las que solo la mencionan para detectar.
    assert all("AP-01" in e or "AP-11" in e for e in etiquetas), etiquetas


def test_lo_que_bloquea_muestra_solo_la_norma_que_bloqueo():
    """La que se disparó es la relevante; las demás son ruido."""
    bloque = _bloque("blocked", writes={"written": 0}, norm_code="AP-11", ok=False)
    assert bloque is not None
    assert bloque["focus"] == "AP-11", bloque
    assert len(bloque["norms"]) == 1, bloque["norms"]
    assert "AP-11" in bloque["norms"][0], bloque["norms"]


def test_el_tope_esta_publicado():
    """El tope es una decisión del registro, no un número en cada llamada."""
    assert 1 <= voz.LIMITE_ETIQUETAS <= 10, voz.LIMITE_ETIQUETAS
    fuente = (REPO_ROOT / "vault" / "autoria" / "voz.py").read_text(encoding="utf-8")
    assert "LIMITE_ETIQUETAS" in fuente
    assert "norm-injection-relevance-and-noise-assessment" in fuente, (
        "el limite debe citar la nota que lo motiva: un tope sin motivo es "
        "una cifra escrita a mano")
