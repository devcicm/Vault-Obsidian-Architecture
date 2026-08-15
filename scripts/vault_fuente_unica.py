#!/usr/bin/env python3
"""vault_fuente_unica — el mismo dato con valores distintos en varias notas (AP-05).

## Por qué llega tan tarde

AP-05 es `critical` desde v19 y estuvo sin detector hasta v40.15 — la única en
esa situación, y declarada así en `cobertura_descubierta` en vez de escondida
en una lista vacía. El motivo escrito era real: decidir qué es «el mismo dato»
sin embeddings es un problema de diseño abierto.

Lo es **en general**. La observación que lo desbloquea es que no hace falta
resolverlo en general para medir lo que hace daño. Un dato **tipado** —una IP,
una URL, un puerto, un semver— no hay que reconocerlo por parecido: se compara
por igualdad. Y su identidad no hay que adivinarla, porque está escrita al lado
en forma de clave. `ip: 192.168.1.10` en una nota y `ip: 192.168.1.20` en otra
del mismo proyecto es AP-05 sin ninguna semántica de por medio.

Esto no cubre AP-05 entera y decirlo forma parte de la medida. Cubre el trozo
en que un agente LLM toma una decisión con un dato erróneo: se conecta a la IP
que no es, llama al puerto que no es, documenta la versión que no es.

## Qué NO ve, dicho antes de que nadie se apoye en ello

- **La prosa.** «el servidor está en el .20» no lleva su clave escrita. Solo se
  miran `clave: valor` en frontmatter y en línea del cuerpo.
- **Los valores sin tipo.** Un `status:` o un `owner:` divergen entre notas
  legítimamente; medirlos sería ruido, y un guard con ruido deja de leerse.
- **El sinónimo.** `ip:` y `direccion_ip:` son la misma cosa para una persona y
  dos claves distintas aquí. Reconocerlo pedía justo los embeddings que el
  estándar no tiene.

Verde aquí no significa que el vault tenga una sola fuente de verdad. Significa
que no hay divergencia **de la clase que se puede decidir sin interpretar**.

## Lo que sí ve, y por qué se puede confiar

Excluye instantáneas congeladas (`vault_io.is_snapshot_path`), documentación
del estándar embarcada (`vault_audit.es_documentacion_del_estandar`) y bloques
de código (`vault_lib.strip_code_blocks`) preguntando a sus dueños canónicos.
Un `ip: 10.0.0.1` dentro de un fence es un ejemplo, no una afirmación, y
contarlo habría sido AP-57 cometido en la tool que se escribe para cumplirlo.

    python scripts/vault_fuente_unica.py --check --strict
    python scripts/vault_fuente_unica.py --report    # los conflictos, legibles
    python scripts/vault_fuente_unica.py --freeze    # solo puede encoger
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

import vault_baseline
from vault_audit_catalog import es_documentacion_del_estandar
from vault_errors import emit_error, wrap_main
from vault_io import get_vault_root, is_snapshot_path
from vault_lib import strip_code_blocks, parse_frontmatter_with_body
from vault_regex import RE_CLAVE_VALOR, tipo_de_valor

BASELINE = Path(__file__).parent / "fuente-unica-baseline.json"

#: Claves cuyo valor es **de la nota**, no un dato compartido del proyecto.
#: Que dos notas tengan `version: 1.0.0` y `version: 2.0.0` no es que el dato
#: diverja: es que son dos notas distintas. Sin esta lista la medida marca el
#: frontmatter entero de cualquier vault y nace inservible.
CLAVES_DE_LA_NOTA = frozenset({
    "version", "created", "modified", "updated", "date", "fecha",
    "id", "uid", "uuid", "hash", "size", "tamaño", "orden", "order",
    "line", "linea", "count", "total", "score", "peso", "weight",
    "confidence", "duration", "duracion", "port_local",
})


def _ambito(rel: Path, fm: Dict[str, Any]) -> str:
    """A qué conjunto de notas pertenece este dato.

    Dos notas solo pueden contradecirse si hablan de lo mismo. `project:` del
    frontmatter es la respuesta cuando está, porque la escribió el autor; sin
    ella, la carpeta de primer nivel es la aproximación menos inventada — y
    cuando la nota está en la raíz, el ámbito es la raíz.

    Es la decisión más discutible de la tool y por eso se declara: un ámbito
    demasiado ancho produce falsos conflictos entre proyectos que comparten
    nombre de clave; demasiado estrecho no ve la contradicción real.
    """
    p = fm.get("project") or fm.get("proyecto")
    if isinstance(p, str) and p.strip():
        return f"project:{p.strip()}"
    partes = rel.parts
    return f"folder:{partes[0]}" if len(partes) > 1 else "folder:."


def _clave(bruta: str) -> str:
    """La forma normalizada de una clave, en un solo sitio.

    El cuerpo y el frontmatter la normalizaban por separado y no igual: el
    frontmatter filtraba `CLAVES_DE_LA_NOTA` con un `lower()` a secas y
    normalizaba **después**, así que un `port-local:` en el frontmatter pasaba
    el filtro que el mismo `port-local:` del cuerpo no pasaba. Dos lectores del
    mismo campo con criterios distintos es lo que esta tool existe para señalar.
    """
    return bruta.strip().lower().replace(" ", "_").replace("-", "_")


def _pares(texto: str) -> List[tuple]:
    """`clave: valor` con valor tipado. Todo lo demás se descarta aquí."""
    fuera = []
    for m in RE_CLAVE_VALOR.finditer(texto):
        clave = _clave(m.group(1))
        if not clave or clave in CLAVES_DE_LA_NOTA:
            continue
        valor = m.group(2).strip()
        tipo = tipo_de_valor(valor)
        if tipo:
            fuera.append((clave, valor.strip("`\"'"), tipo))
    return fuera


def medir(raiz: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Los conflictos: misma clave tipada, mismo ámbito, valores distintos."""
    raiz = Path(raiz) if raiz else get_vault_root()
    # (ámbito, clave) -> valor -> [notas que lo afirman]
    visto: Dict[tuple, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    tipos: Dict[tuple, str] = {}

    for p in sorted(raiz.rglob("*.md")):
        rel = p.relative_to(raiz)
        if is_snapshot_path(rel):
            continue
        try:
            crudo = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # El orden importa y ya salió mal una vez: la firma es
        # `(rel, contenido)`, y v40.15 la llamó al revés. Con el contenido en
        # `rel`, la función buscaba `"/scripts/"` dentro del **texto** de la
        # nota, así que cualquier nota que citara un comando quedaba fuera de
        # la medida — y la documentación del estándar, que sí se excluye,
        # entraba. Verde por no mirar en un sentido y ruido en el otro.
        # `as_posix()` porque la firma pide la ruta con `/`, no un Path.
        if es_documentacion_del_estandar(rel.as_posix(), crudo):
            continue

        # Frontmatter roto es AP-46, no AP-05: el dueño del criterio devuelve
        # `{}` y el cuerpo entero, así que la nota se sigue midiendo en vez de
        # perderse — el defecto de otro no debe volver ciega a esta medida.
        # Delega en `vault_lib` (AP-57) porque la copia que había aquí se quedó
        # sin la contención de `RecursionError` del dueño (AP-61): una nota con
        # el frontmatter muy anidado tumbaba el barrido completo, y esta tool
        # acepta `--root` contra vaults ajenos, que es donde eso llega.
        fm_bruto, cuerpo = parse_frontmatter_with_body(crudo)
        fm: Dict[str, Any] = fm_bruto if isinstance(fm_bruto, dict) else {}

        # Un valor dentro de un fence es un ejemplo, no una afirmación (AP-57).
        texto = crudo[:0] + strip_code_blocks(cuerpo)
        pares = _pares(texto)
        for k, v in fm.items():
            clave = _clave(str(k))
            if isinstance(v, (str, int)) and clave and clave not in CLAVES_DE_LA_NOTA:
                t = tipo_de_valor(str(v))
                if t:
                    pares.append((clave, str(v), t))

        ambito = _ambito(rel, fm)
        for clave, valor, tipo in pares:
            llave = (ambito, clave)
            tipos[llave] = tipo
            notas = visto[llave][valor]
            if str(rel) not in notas:
                notas.append(str(rel))

    conflictos = []
    for (ambito, clave), valores in sorted(visto.items()):
        if len(valores) < 2:
            continue
        conflictos.append({
            "ambito": ambito,
            "clave": clave,
            "tipo": tipos[(ambito, clave)],
            "valores": {v: sorted(ns) for v, ns in sorted(valores.items())},
            "notas_afectadas": sum(len(ns) for ns in valores.values()),
        })
    return conflictos


def _firma(c: Dict[str, Any]) -> str:
    return f"{c['ambito']}::{c['clave']}"


def _baseline() -> List[str]:
    """superseded_by: vault_baseline.cargar (v40.24).

    Era la cuarta copia del mismo criterio, y la única que además distinguía mal
    el fallo: `except (OSError, json.JSONDecodeError)` en un solo bloque perdía
    cuál de las dos cosas había pasado antes de relanzar. Se conserva la función
    porque la llaman `check` y `freeze`.
    """
    return vault_baseline.cargar(BASELINE, "conflictos", "AP-05")


def check(raiz: Optional[Path] = None) -> Dict[str, Any]:
    conflictos = medir(raiz)
    firmas = {_firma(c) for c in conflictos}
    base = set(_baseline())
    nuevos = sorted(firmas - base)
    return {
        "ok": not nuevos,
        "tool": "vault_fuente_unica",
        "norm": "AP-05",
        "action": "check",
        "conflicts": conflictos,
        "conflicts_total": len(conflictos),
        "baseline_size": len(base),
        "new_conflicts": nuevos,
        "resolved_since_baseline": sorted(base - firmas),
        "hint": (
            "Se salda con PAT-1: una nota canónica declara el dato y las demás "
            "la enlazan. Verde aquí no prueba una sola fuente de verdad: prueba "
            "que no hay divergencia de la clase decidible sin interpretar."
        ),
    }


def freeze(raiz: Optional[Path] = None, admitir_nuevos: bool = False) -> Dict[str, Any]:
    conflictos = medir(raiz)
    firmas = sorted({_firma(c) for c in conflictos})
    base = set(_baseline())
    nuevos = sorted(set(firmas) - base)
    # Sin `and base`: una baseline vacía —o todavía sin fichero, que es como
    # nace esta— no es permiso para congelar la primera deuda en silencio. Es
    # justo el momento en que más barato sale hacerlo y menos se nota.
    if nuevos and not admitir_nuevos:
        return vault_baseline.negativa(
            "vault_fuente_unica", "freeze", "new_conflicts", nuevos,
            "Resuélvelos con PAT-1. Si de verdad hay que congelar deuda "
            "nueva, `--freeze --admitir-nuevos` la lista aquí.")
    vault_baseline.escribir(
        BASELINE, "conflictos", "AP-05",
        "Conflictos de fuente de verdad que ya estaban cuando AP-05 estrenó "
        "detector. Solo puede encoger: un conflicto nuevo se resuelve con "
        "PAT-1, no se congela.",
        firmas)
    return {"ok": True, "tool": "vault_fuente_unica", "action": "freeze",
            "frozen": len(firmas), "admitted_new": nuevos if admitir_nuevos else []}


def report(raiz: Optional[Path] = None) -> Dict[str, Any]:
    """El conflicto en forma legible: qué dato, qué valores, quién dice cuál."""
    conflictos = medir(raiz)
    lineas = []
    for c in conflictos:
        lineas.append(f"[{c['ambito']}] {c['clave']} ({c['tipo']})")
        for valor, notas in c["valores"].items():
            lineas.append(f"    {valor}  <- {', '.join(notas)}")
    return {"ok": True, "tool": "vault_fuente_unica", "action": "report",
            "conflicts_total": len(conflictos), "report": lineas}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="vault_fuente_unica — el mismo dato con valores distintos (AP-05)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--admitir-nuevos", action="store_true")
    ap.add_argument("--root", help="solo para contrastar contra un vault ajeno (regla 7)")
    args = ap.parse_args()

    if args.freeze and (args.check or args.report):
        env = emit_error("vault_fuente_unica", "CONFLICTING_ARGS",
                         "--freeze y --check/--report piden cosas distintas: o mide o congela")
        env["recovery"] = "elige uno"
        print(json.dumps(env, ensure_ascii=False))
        return 1

    raiz = Path(args.root) if args.root else None
    if args.freeze:
        r = freeze(raiz, args.admitir_nuevos)
    elif args.report:
        r = report(raiz)
    else:
        r = check(raiz)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 1 if args.strict and not r["ok"] else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_fuente_unica"))
