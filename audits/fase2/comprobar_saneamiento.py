#!/usr/bin/env python3
r"""Comprobacion reproducible de saneamiento de las evidencias publicadas.

Las logs de auditoria se publican en un repo publico: no pueden llevar la
ruta local de la maquina, ni el nombre de quien la usa, ni quedar en UTF-16
(caracteres NUL) que un visor de texto lee como ruido. Esta comprobacion es
ejecutable y devuelve codigo distinto de cero mientras quede algo.

Criterios (los mismos que el guard de publicacion limpia del repo, mas la
codificacion):
  1. Sin bytes NUL (senal de UTF-16).
  2. Sin BOM de UTF-16.
  3. Sin ruta local identificable: tras `Users/`, `home/` o `Users\` solo
     puede venir un marcador (`<...>`, `...`) o un nombre generico.
  4. Sin forma de credencial (AKIA, `api_key`, `Bearer ` con valor).

Uso: python audits/fase2/comprobar_saneamiento.py [--raiz DIR]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple

#: Nombres que delatan una maquina concreta; los genericos no.
GENERICOS = {"...", "user", "usuario", "tu-usuario", "username", "nombre",
             "<autor>", "<ruta-local>", "<ruta_local>"}

RUTA_WINDOWS = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+([^\s\"'`)\]]+)")
RUTA_UNIX = re.compile(r"/(?:home|Users)/([A-Za-z<][^\s\"'`)\]]*)")
CREDENCIAL = re.compile(r"AKIA[0-9A-Z]{12,}|api_key\s*[:=]\s*[\"'][^\"']{8,}[\"']|Bearer\s+[A-Za-z0-9\-_\.]{16,}")


def revisar(raiz: Path) -> List[Tuple[str, str]]:
    """Los problemas de saneamiento de los ficheros publicados bajo `raiz`."""
    problemas: List[Tuple[str, str]] = []
    base = raiz / "audits"
    if not base.is_dir():
        return problemas
    for ruta in sorted(base.rglob("*")):
        if not ruta.is_file() or ruta.suffix.lower() not in (".txt", ".md", ".json", ".yaml", ".yml", ".log"):
            continue
        datos = ruta.read_bytes()
        relative = ruta.relative_to(raiz).as_posix()
        if b"\x00" in datos:
            problemas.append((relative, "contiene bytes NUL (UTF-16 o binario)"))
            continue
        if datos[:2] in (b"\xff\xfe", b"\xfe\xff"):
            problemas.append((relative, "tiene BOM de UTF-16"))
            continue
        try:
            texto = datos.decode("utf-8")
        except UnicodeDecodeError as exc:
            problemas.append((relative, f"no es UTF-8 valido: {exc}"))
            continue
        for patron in (RUTA_WINDOWS, RUTA_UNIX):
            for coincidencia in patron.finditer(texto):
                segmento = coincidencia.group(1).strip().strip("/\\").lower()
                if segmento in GENERICOS:
                    continue
                problemas.append((relative, f"ruta local identificable: {coincidencia.group(0)[:80]}"))
        for coincidencia in CREDENCIAL.finditer(texto):
            problemas.append((relative, f"forma de credencial: {coincidencia.group(0)[:40]}"))
    return problemas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raiz", default=str(Path(__file__).resolve().parents[2]))
    args = ap.parse_args()
    raiz = Path(args.raiz)
    problemas = revisar(raiz)
    if problemas:
        print(f"{len(problemas)} problema(s) de saneamiento:")
        for fichero, motivo in problemas:
            print(f"  {fichero}: {motivo}")
        return 1
    print("saneamiento conforme: sin rutas identificables, sin NUL, sin UTF-16, sin credenciales")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())