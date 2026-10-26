"""El protocolo QA es un doc derivado del catálogo: se guarda la forma.

`audits/handoff/PROTOCOLO-QA.md` nació a mano y a la primera divergió del
registro del que dice derivar: asignaba QG-01 al «agente ejecutor» cuando el
dueño del catálogo es `meta_toolkit - vault_arch`, a QG-02 «agente ejecutor»
que importa nada dependientes del yaml (que es lo dictaminó QA en R12). El
guard vive así: el catálogo de `audits/fase2/catalogo-qg.yaml` es el registro,
la tabla §2 del protocolo su derivado, y este test falla ante el drift.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOGO = REPO_ROOT / "audits" / "fase2" / "catalogo-qg.yaml"
PROTOCOLO = REPO_ROOT / "audits" / "handoff" / "PROTOCOLO-QA.md"


def _limpia(texto: str) -> str:
    """El texto sin adornos de markdown (negritas, backticks, espacios)."""
    sin = re.sub(r"\*\*(.*?)\*\*", r"\1", texto)
    sin = sin.replace("`", "").strip()
    # El catálogo escribe sin acentos (yaml en ASCII); el protocolo es prosa
    # en español con ellos. Se comparan en forma canónica sin diacríticos.
    return unicodedata.normalize("NFKD", sin.lower()).replace("\u0301", "")


def _tabla_del_protocolo() -> dict[str, dict[str, str]]:
    """Filas QG-xx de la tabla §2 del protocolo: dueño, aceptación y exención."""
    seccion = PROTOCOLO.read_text(encoding="utf-8")
    m = re.search(r"## 2\. Autoridad.*?\n((?:\|[^\n]*\n)+)", seccion, re.DOTALL)
    assert m, "el protocolo perdió la tabla de autoridad §2"
    filas = re.findall(
        r"^\|\s*(QG-\d\d)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|$",
        m.group(1),
        re.M,
    )
    assert filas, "la tabla §2 no tiene filas con el formato de cuatro columnas"
    return {f[0]: {"owner": _limpia(f[1]),
                  "aceptacion": _limpia(f[2]),
                  "waiver": _limpia(f[3])} for f in filas}


def test_la_tabla_de_autoridad_del_protocolo_cubre_todo_el_catalogo():
    catalogo = yaml.safe_load(CATALOGO.read_text(encoding="utf-8"))
    proto = _tabla_del_protocolo()
    faltan = [g["id"] for g in catalogo if g["id"] not in proto]
    sobran = [i for i in proto if i not in {g["id"] for g in catalogo}]
    assert not faltan and not sobran, (faltan, sobran)


def test_dueno_y_aceptacion_de_cada_qg_copian_el_catalogo():
    catalogo = yaml.safe_load(CATALOGO.read_text(encoding="utf-8"))
    proto = _tabla_del_protocolo()
    divergencias = []
    for g in catalogo:
        fila = proto.get(g["id"])
        if fila is None:
            continue
        if _limpia(g["owner"]) != fila["owner"]:
            divergencias.append((g["id"], "owner", g["owner"], fila["owner"]))
        if _limpia(g["acceptance_authority"]) != fila["aceptacion"]:
            divergencias.append(
                (g["id"], "acceptance_authority",
                 g["acceptance_authority"], fila["aceptacion"]))
    assert not divergencias, divergencias


def test_la_exencion_del_protocolo_es_la_del_catalogo():
    """La política de waiver es la parte que QA pidió unir: se guarda entera."""
    catalogo = yaml.safe_load(CATALOGO.read_text(encoding="utf-8"))
    proto = _tabla_del_protocolo()
    divergencias = []
    for g in catalogo:
        fila = proto.get(g["id"])
        if fila is None:
            continue
        esperado = (g.get("waiver_policy", "") or "").strip().replace("`", "")
        if esperado and _limpia(esperado) != fila["waiver"]:
            divergencias.append((g["id"], esperado, fila["waiver"]))
    assert not divergencias, divergencias
