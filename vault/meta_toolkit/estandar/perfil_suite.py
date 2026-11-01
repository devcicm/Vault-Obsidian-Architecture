"""Hoja canónica del perfil de la suite: segundos medidos por módulo y qué es `slow`.

Hasta v41.25 el marker `slow` se ponía a mano (`pytestmark` en 24 módulos,
según un perfil del 2026-10-20) y nadie lo usaba, porque el cierre pedía la
suite entera. El perfil ya existía (`tests/duraciones-por-modulo.json`, para
repartir shards) y el marker lo copiaba a mano: dos fuentes de la misma
medida, que divergen en la dirección cómoda (AP-05). Seis de los 24 ya no
llegaban a 25 s, y quince que sí llegaban no lo llevaban. Desde v41.26 `slow`
se **deriva** de aquí:

- `conftest.pytest_collection_modifyitems` marca `slow` a todo test de un
  módulo cuyo total medido llega a `UMBRAL_LENTO_S`, para iterar a mano con
  `-m "not slow"`.
- El carril `dev` (`vault_test_scope --changed --correr`) saca de su lista los
  módulos lentos y los nombra, salvo el fichero de test que el propio cambio
  edita: dejar fuera lo que se está tocando sería seleccionar de menos en
  silencio. Los exige `merge`, que corre la suite sin filtro. Un carril más
  barato no rebaja al siguiente.

El umbral es por **módulo** y no por llamada: lo que paga el carril `dev` es
el reloj del módulo entero, y un módulo de mil tests de 30 ms cuesta lo mismo
que uno de un test de 30 s.

Un módulo que el perfil no conoce **no** es lento: un test nuevo corre en
`dev` hasta que una medida diga lo contrario. Equivocarse ahí cuesta segundos;
lo contrario sacaría del desarrollo justo lo que se acaba de escribir.

El perfil se refresca desde los spans de la última corrida
(`tests/.spans/ultima.json`, que escribe el conftest). Los módulos medidos
sustituyen a su valor y el resto conserva el suyo, así que una corrida del
carril `dev` —que deja fuera los lentos— no los borra. Lo que los spans no
pueden decir es si un módulo corrió entero: refrescar tras un `-k` o un `::test`
suelto lo mediría de menos. Por eso el sitio es tras una corrida de `merge`:

    python -m vault.meta_toolkit.estandar.perfil_suite --refrescar
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from vault.kernel import rutas
from vault.kernel.errores import construir_error

DURACIONES = rutas.ruta_repo(rutas.TESTS) / "duraciones-por-modulo.json"
SPANS = rutas.ruta_repo(rutas.TESTS) / ".spans" / "ultima.json"

#: Segundos de trabajo de un módulo entero a partir de los cuales es `slow`.
UMBRAL_LENTO_S = 25.0


def pesos(ruta: Path = DURACIONES) -> Dict[str, float]:
    """Módulo -> segundos medidos. Vacío si el perfil falta o está roto.

    Vacío es un valor legítimo y no un error escondido (AP-51): sin perfil el
    reparto pesa todo igual y ningún módulo es lento, que es lo seguro.
    """
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return {k: float(v) for k, v in datos["segundos_por_modulo"].items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}


def lentos(medidos: Optional[Mapping[str, float]] = None) -> Dict[str, float]:
    """Módulo -> segundos, solo los que llegan a `UMBRAL_LENTO_S`."""
    medidos = pesos() if medidos is None else medidos
    return {m: s for m, s in medidos.items() if s >= UMBRAL_LENTO_S}


def medir_spans(spans: Any) -> Dict[str, float]:
    """Spans por (módulo, worker) -> segundos de trabajo por módulo."""
    total: Dict[str, float] = {}
    for s in spans:
        total[s["modulo"]] = total.get(s["modulo"], 0.0) + float(s["trabajo_s"])
    return {m: round(v, 1) for m, v in total.items()}


def refrescar(spans_ruta: Path = SPANS, destino: Path = DURACIONES,
              hoy: Optional[str] = None) -> Dict[str, Any]:
    """Funde los spans de la última corrida en el perfil. Escritura atómica."""
    try:
        medidos = medir_spans(json.loads(spans_ruta.read_text(encoding="utf-8"))["spans"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return construir_error(
            "perfil_suite", "DATA_FILE_CORRUPT", message=f"{spans_ruta}: {exc}",
            exception=exc,
            pista="corre la suite (carril merge) para que el conftest escriba los spans")
    previos = pesos(destino)
    fundidos = {**previos, **medidos}
    cambian = sorted(m for m in fundidos if previos.get(m) != fundidos[m])
    hoy = hoy or date.today().isoformat()
    datos = {
        "_fuente": (
            f"refrescado {hoy} desde tests/.spans/ultima.json "
            f"({len(medidos)} modulos medidos, {platform.system()}); el resto "
            f"conserva la medida anterior. Equilibra el reparto de shards y "
            f"decide `slow` (>= {UMBRAL_LENTO_S:g} s por modulo): "
            f"vault/meta_toolkit/perfil_suite.py."),
        "segundos_por_modulo": dict(sorted(fundidos.items())),
    }
    tmp = destino.with_suffix(".json.tmp")
    # Bytes y no `write_text(newline=)`, que no existe en el piso (3.9): el
    # JSON no lleva CR, así que el fichero sale en LF en cualquier plataforma.
    tmp.write_bytes((json.dumps(datos, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    tmp.replace(destino)
    antes, ahora = set(lentos(previos)), set(lentos(fundidos))
    return {"ok": True, "tool": "perfil_suite", "written": 1 if cambian else 0,
            "medidos": len(medidos), "cambian": len(cambian),
            "entran_en_slow": sorted(ahora - antes),
            "salen_de_slow": sorted(antes - ahora)}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Perfil de la suite: qué módulos son `slow` y cómo se refresca.",
        allow_abbrev=False)
    ap.add_argument("--refrescar", action="store_true",
                    help="funde tests/.spans/ultima.json en el perfil (tras una corrida de merge)")
    args = ap.parse_args()
    if args.refrescar:
        r = refrescar()
    else:
        lista = lentos()
        r = {"ok": True, "tool": "perfil_suite", "umbral_s": UMBRAL_LENTO_S,
             "lentos": dict(sorted(lista.items(), key=lambda kv: -kv[1])),
             "n": len(lista), "segundos": round(sum(lista.values()), 1)}
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
