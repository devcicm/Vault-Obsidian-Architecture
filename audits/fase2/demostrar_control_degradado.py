#!/usr/bin/env python3
"""Demostracion: un control que no puede cargar su dependencia informa cero
hallazgos (TD-0003 / Q04-Q07).

NO se modifica el motor: esto lo OBSERVA. Se inyecta, por un lado, un
verificador que devuelve un hallazgo (para que el control tenga algo que
decir) y, por otro, la rotura de su dependencia (para que el control no pueda
decir nada). Se mide lo que el envelope publica en los dos casos.

Lo que se demuestra, para AP-40, AP-42 y AP-43:
  con la dependencia sana   -> el control aparece en `by_norm` con su hallazgo;
  con la dependencia rota   -> el control NO aparece, y el envelope NO dice
                              que no se pudo ejecutar: `ok` sigue siendo True
                              y no hay ningun campo que lo distinga de
                              "se ejecuto y no encontro nada".

Salida: JSON en `audits/fase2/logs/L2-control-degradado.json`.

Uso: python audits/fase2/demostrar_control_degradado.py [--salida F]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))


def _auditar() -> Dict[str, Any]:
    """La auditoria tal cual la publica la CLI (fachada -> motor -> runtime)."""
    import vault_norms

    return vault_norms.vault_norms_audit(root=ROOT / "vault-sandbox")


def _roto(modulo: str) -> None:
    """Deja el modulo como si no se pudiera importar.

    `sys.modules[nombre] = None` hace que `import <nombre>` lance ImportError:
    es la forma estandar de simular una dependencia ausente sin tocar disco.
    """
    sys.modules[modulo] = None


def _restaurar(modulo: str) -> None:
    sys.modules.pop(modulo, None)


def _con_hallazgo(modulo: str, atributo: str, valor: Any) -> Dict[str, Any]:
    """El control tiene algo que decir (su dependencia responde)."""
    import importlib

    mod = importlib.import_module(modulo)
    original = getattr(mod, atributo)
    setattr(mod, atributo, lambda *a, **k: valor)
    try:
        sobre = _auditar()
    finally:
        setattr(mod, atributo, original)
    return sobre


def _con_dependencia_rota(modulo: str) -> Dict[str, Any]:
    """El control no puede ni intentar hablar."""
    _roto(modulo)
    try:
        sobre = _auditar()
    finally:
        _restaurar(modulo)
    return sobre


CASOS = [
    ("AP-40", "vault_mcp_catalog", "check_params",
     {"problems": [{"tool": "herramienta-de-demostracion",
                    "problem": "parametro declarado que argparse no acepta"}]}),
    ("AP-42", "vault_smoke", "load_baseline", ["herramienta-congelada-de-demostracion"]),
    ("AP-43", "vault_voice", "coverage", {"silent": ["AP-99"]}),
]



def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--salida", default="audits/fase2/logs/L2-control-degradado.json")
    args = ap.parse_args()

    filas: List[Dict[str, Any]] = []
    for norma, modulo, atributo, valor in CASOS:
        sano = _con_hallazgo(modulo, atributo, valor)
        roto = _con_dependencia_rota(modulo)
        filas.append({
            "norma": norma,
            "dependencia": modulo,
            "con_dependencia_sana": {
                "ok": sano.get("ok"),
                "aparece_en_by_norm": norma in (sano.get("by_norm") or {}),
                "total_violations": sano.get("total_violations"),
                "violaciones_de_esa_norma": [
                    v for v in (sano.get("violations") or []) if v.get("norm") == norma
                ],
                "declara_algo_sobre_no_ejecutado": False,
            },
            "con_dependencia_rota": {
                "ok": roto.get("ok"),
                "aparece_en_by_norm": norma in (roto.get("by_norm") or {}),
                "total_violations": roto.get("total_violations"),
                "violaciones_de_esa_norma": [
                    v for v in (roto.get("violations") or []) if v.get("norm") == norma
                ],
                "declara_algo_sobre_no_ejecutado": any(
                    clave in (roto or {}) for clave in ("checks", "controles", "degraded")
                ),
            },
        })
        fila = filas[-1]
        diferencia = (fila["con_dependencia_sana"]["aparece_en_by_norm"]
                      != fila["con_dependencia_rota"]["aparece_en_by_norm"])
        print(f"{norma}: con dependencia sana aparece={fila['con_dependencia_sana']['aparece_en_by_norm']}"
              f" | con dependencia rota aparece={fila['con_dependencia_rota']['aparece_en_by_norm']}"
              f" | el envelope avisa de que no se ejecuto: "
              f"{fila['con_dependencia_rota']['declara_algo_sobre_no_ejecutado']}"
              f" | diferencia observable: {diferencia}")

    veredicto = {
        "que_demuestra": (
            "Un control cuyo verificador no se puede cargar desaparece del "
            "resultado sin dejar rastro: el envelope publica ok=True y no "
            "distingue 'no se encontro nada' de 'no se pudo mirar'."),
        "filas": filas,
        "conclusion": (
            "Las tres familias (AP-40, AP-42, AP-43) comparten el mismo "
            "defecto: el resultado no declara el ESTADO de ejecucion del "
            "control, solo sus hallazgos."),
    }
    Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
    Path(args.salida).write_text(json.dumps(veredicto, ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8")
    print(f"\nlog: {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())