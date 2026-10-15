#!/usr/bin/env python3
"""vault_esquema — publica el contrato de nota como un JSON Schema por versión.

## Por qué existe

El contrato de campos de una nota vive en `vault_contrato_nota`, que es Python.
Quien consume un vault sin este toolkit —un editor, una CI de otro lenguaje, un
agente que solo sabe JSON Schema— no puede importarlo. Esta tool lo publica en
`schemas/`, un fichero por versión mayor del estándar, junto con los de las
versiones anteriores: un vault que se quedó en v28 se valida contra lo que v28
exigía, no contra lo de hoy.

## Lo que es derivado

`schemas/*.schema.json` y `schemas/README.md` se regeneran con `--sync` y no se
editan a mano: `--check` falla si el disco diverge del contrato, y la puerta
`esquemas` lo ejecuta. Lo escrito a mano se pierde, que es lo que mantiene
honesto lo publicado (AP-47).

## Lo que no cubre, dicho

- Hasta v24 no había validador: esos esquemas exigen lo que la regla AP-12 del
  manifiesto decía (`x-vault-origen: manifiesto`, `x-vault-validador: false`).
  Antes de v18 el manifiesto no está en git y no se publica esquema.
- La clase de una nota sale de su ruta, que no está en el frontmatter. El
  esquema trae una definición por clase en `$defs`; elegirla es de quien valida.

    python scripts/vault_esquema.py --check --strict   # 1 si schemas/ diverge
    python scripts/vault_esquema.py --sync             # regenera schemas/
    python scripts/vault_esquema.py --version v37      # imprime un esquema
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent))

from vault_contrato_nota import (CAMPOS, HISTORIA, PRIMER_VALIDADOR, VERSIONES_CON_CONTRATO,
                                 contrato_de_version, esquema_json)
from vault_errors import emit_error, wrap_main

RAIZ = Path(__file__).resolve().parent.parent
CARPETA = RAIZ / "schemas"


def _nombre(version: str) -> str:
    return f"vault-{version}.schema.json"


def _texto(version: str) -> str:
    return json.dumps(esquema_json(version), ensure_ascii=False, indent=2) + "\n"


def _readme() -> str:
    filas = []
    for v in VERSIONES_CON_CONTRATO:
        c = contrato_de_version(v)
        exige = ", ".join(f"`{x}`" for x in c["requeridos"]["contenido"])
        if not c["validador"]:
            exige += " (AP-12 del manifiesto; sin validador)"
        cambios = "; ".join(h["cambio"] for h in HISTORIA.get(v, [])) or "—"
        filas.append(f"| [{v}]({_nombre(v)}) | {exige} | {cambios} |")
    campos = "\n".join(
        f"| `{k}` | {d['nivel']} | {', '.join(d['clases'])} | {d.get('norma', '—')} |"
        for k, d in CAMPOS.items())
    return f"""# Esquemas de nota por versión

> Derivado de `vault/kernel/contrato_nota.py` por `python scripts/vault_esquema.py --sync`.
> No se edita a mano: `--check` falla si diverge, y lo escrito aquí se pierde.

Un fichero por versión mayor del estándar, todos al lado: un vault que se quedó
en una versión anterior se valida contra lo que esa versión exigía. Cada
esquema es JSON Schema 2020-12 sobre el frontmatter ya parseado como YAML.

## Cómo se usa

La raíz de cada esquema es el contrato de una **nota de contenido**. Las notas
de `00_System/` se validan contra `#/$defs/sistema`, y desde v41 un `.md` fuera
de toda sección —la raíz, o una carpeta que `vault_registry` no declara— contra
`#/$defs/sin_seccion`. Desde v37, los artefactos
derivados —todo `index.md` y los que declara `vault_registry.DERIVED_ARTIFACTS`—
quedan fuera del contrato. La clase sale de la ruta de la nota, que no está en
el frontmatter: elegirla es de quien valida.

El esquema restringe **solo lo que `vault_validate` restringía** en esa versión.
Lo que el escritor pone de forma habitual va como anotación (`x-vault-*`), no
como restricción: un esquema más estricto que el validador reprobaría notas
que la tool aprueba.

Los campos que faltan se completan con `python scripts/vault_frontmatter_completar.py`
(dry-run por defecto, `--apply` para escribir), que pone lo que el escritor
habría puesto y declara el origen de cada valor.

## Versiones

| Esquema | Requeridos en una nota de contenido | Qué cambió en esa versión |
|---|---|---|
{chr(10).join(filas)}

Hasta v24 no había validador: el contrato de esas versiones es la regla AP-12
del manifiesto, que exigía los mismos campos a toda nota, de cualquier clase.
De v21 a v24 no hay manifiesto en git; el de v20 y el de {PRIMER_VALIDADOR} escriben
la regla igual, y eso es lo que se aplica. Antes de v18 el manifiesto no está
en el repositorio y no se publica esquema.

Cualquier versión se valida con el validador vigente:
`python scripts/vault_validate.py --check frontmatter --contrato v30`.

## Campos del contrato vigente

| Campo | Nivel | Clases | Norma |
|---|---|---|---|
{campos}
"""


def _esperado() -> Dict[str, str]:
    salida = {_nombre(v): _texto(v) for v in VERSIONES_CON_CONTRATO}
    salida["README.md"] = _readme()
    return salida


def check() -> Dict[str, Any]:
    divergentes = []
    for nombre, texto in _esperado().items():
        ruta = CARPETA / nombre
        actual = ruta.read_text(encoding="utf-8") if ruta.exists() else None
        if actual != texto:
            divergentes.append({"file": f"schemas/{nombre}",
                                "problem": "ausente" if actual is None else "desactualizado"})
    sobrantes = sorted(p.name for p in CARPETA.glob("*.schema.json")
                       if p.name not in _esperado()) if CARPETA.exists() else []
    return {
        "ok": not divergentes and not sobrantes,
        "tool": "vault_esquema",
        "action": "check",
        "versions": list(VERSIONES_CON_CONTRATO),
        "stale": divergentes,
        "stale_count": len(divergentes),
        # Un esquema sin versión en el contrato no se borra (no-derogación): se
        # informa, y decide una persona.
        "unknown": sobrantes,
        "hint": "python scripts/vault_esquema.py --sync" if divergentes else "",
    }


def sync() -> Dict[str, Any]:
    CARPETA.mkdir(parents=True, exist_ok=True)
    escritos = []
    for nombre, texto in _esperado().items():
        ruta = CARPETA / nombre
        if ruta.exists() and ruta.read_text(encoding="utf-8") == texto:
            continue
        ruta.write_bytes(texto.encode("utf-8"))
        escritos.append(f"schemas/{nombre}")
    return {"ok": True, "tool": "vault_esquema", "action": "sync",
            "versions": list(VERSIONES_CON_CONTRATO),
            # AP-37: cuántos ficheros cambiaron en disco. Cero es la respuesta
            # de un `--sync` sobre un `schemas/` al día.
            "written": escritos, "written_count": len(escritos)}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="vault_esquema — el contrato de nota como JSON Schema por versión", allow_abbrev=False)
    ap.add_argument("--check", action="store_true", help="Falla si schemas/ diverge del contrato")
    ap.add_argument("--strict", action="store_true", help="Exit 1 si algo diverge")
    ap.add_argument("--sync", action="store_true", help="Regenera schemas/ desde el contrato")
    ap.add_argument("--version", help="Imprime el esquema de una versión (v18..)")
    args = ap.parse_args()

    if args.sync and args.check:
        env = emit_error("vault_esquema", "CONFLICTING_ARGS",
                         "--sync escribe y --check mide: elige uno", pista="elige uno")
        print(json.dumps(env, ensure_ascii=False))
        return 1
    if args.version:
        try:
            r: Dict[str, Any] = esquema_json(args.version)
        except ValueError as exc:
            env = emit_error("vault_esquema", "INVALID_VALUE", str(exc),
                             pista=f"una de {VERSIONES_CON_CONTRATO[0]}..{VERSIONES_CON_CONTRATO[-1]}")
            print(json.dumps(env, ensure_ascii=False))
            return 1
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0

    r = sync() if args.sync else check()
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 1 if args.strict and not r["ok"] else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_esquema"))
