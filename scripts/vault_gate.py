#!/usr/bin/env python3
"""vault_gate — la puerta única: corre todas las puertas de cierre y agrega el veredicto.

El problema que resuelve no es de comodidad. Las puertas estaban repartidas en un
checklist de prosa dentro de `CLAUDE.md`, y una lista en prosa tiene tres fallos
que ya se cobraron su precio en este repo:

1. **Nadie sabe cuántas son.** Se decía "las siete puertas" mientras el checklist
   tenía ocho ítems y la práctica corría seis. El número era folclore.
2. **Añadir una puerta no la pone en circulación.** Una puerta nueva que nadie
   añade al checklist es un guard que no corre — y un guard que no corre es
   exactamente lo que AP-42 castiga: superficie publicada sin ejecutar.
3. **Correrlas a mano las corre a medias.** Ocho comandos escritos uno a uno se
   ejecutan completos el primer día y salteados el décimo, y el que se saltea es
   siempre el más lento.

Por eso la lista **canónica vive aquí, en código**, y el checklist de `CLAUDE.md`
se comprueba contra ella (`--check-doc`). El orden es el del estándar: registro
canónico primero, doc después, guard que falla si divergen. Al revés —lista en el
doc, código que la sigue— sería AP-50 estrenada en la misma versión que la declara.

    python scripts/vault_gate.py              # corre todas, envelope agregado
    python scripts/vault_gate.py --strict     # exit 1 si alguna falla
    python scripts/vault_gate.py --list       # qué puertas hay y qué mide cada una
    python scripts/vault_gate.py --check-doc  # el checklist de CLAUDE.md vs. este registro

## Lo que esta tool NO hace

**No reimplementa ninguna comprobación y no baja el enforcement de ninguna norma**
(regla 5). Cada puerta se ejecuta como subproceso, con su propio exit code y su
propio envelope, y `vault_gate` solo agrega. Si mirara los datos por su cuenta
sería una segunda fuente de verdad sobre el estado del repo — AP-05 — y además
mediría con su criterio en vez del de la puerta, que es AP-44.

**No sustituye a `pytest`.** La suite es lenta y estas son rápidas; correrlas
antes de la suite ahorra el ciclo largo cuando algo evidente está roto, pero
verde aquí no es verde allí.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from vault_errors import emit_error, wrap_main

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent

#: El registro canónico de puertas de cierre. Añadir una aquí la pone en
#: circulación en el mismo commit — que es la mitad que faltaba.
#:
#: `mide` no es decoración: es lo que se lee cuando una puerta falla y hay que
#: decidir si es un fallo real o un artefacto derivado que solo hay que
#: regenerar. Las que tienen `fix` se arreglan solas; las que no, no.
PUERTAS: List[Dict[str, Any]] = [
    {
        "id": "framework",
        "cmd": ["vault_norms.py", "--check-framework"],
        "mide": "El manifiesto documenta todo id del marco de datos y toda norma "
                "catalogada tiene sección propia",
        "fix": None,
    },
    {
        "id": "catalogo",
        "cmd": ["vault_mcp_catalog.py", "--check"],
        "mide": "El catálogo Python y tools-catalog.json no divergen",
        "fix": "python scripts/vault_mcp_catalog.py --sync",
    },
    {
        "id": "contratos",
        "cmd": ["vault_mcp_catalog.py", "--check-contracts"],
        "mide": "Toda tool del catálogo tiene entrada en tool-spec.json, y toda "
                "entrada que ya no está declara su status en vez de borrarse",
        "fix": None,
    },
    {
        "id": "conteos",
        "cmd": ["vault_doc_counts.py", "--check", "--strict"],
        "mide": "Ninguna cifra de la documentación está escrita a mano (AP-47)",
        "fix": "python scripts/vault_doc_counts.py --fix",
    },
    {
        "id": "doc_sync",
        "cmd": ["vault_doc_sync.py", "--check", "--strict"],
        "mide": "Toda tool tiene sección en scripts/README.md y el índice una fila "
                "por grupo",
        "fix": "python scripts/vault_doc_sync.py --fix  (solo el índice; las "
               "secciones se escriben a mano)",
    },
    {
        "id": "noop",
        "cmd": ["vault_noop_audit.py", "--check", "--strict"],
        "mide": "AP-37 — ninguna tool con side effects devuelve ok: true sin "
                "indicador de trabajo",
        "fix": "saldar la deuda y luego --freeze",
    },
    {
        "id": "blame",
        "cmd": ["vault_blame_audit.py", "--check", "--strict"],
        "mide": "AP-51 — ningún handler amplio devuelve un vacío indistinguible "
                "de un resultado legítimo",
        "fix": "saldar la deuda y luego --freeze",
    },
    {
        "id": "contrato_error",
        "cmd": ["vault_error_contract.py", "--check", "--strict"],
        "mide": "AP-52 \u2014 ningun envelope de error nuevo se emite fuera del "
                "contrato de ERROR_CATALOG",
        "fix": "emitir por emit_error y luego --freeze",
    },
    {
        "id": "campos",
        "cmd": ["vault_spec_catalog_check.py", "--check-fields", "--strict"],
        "mide": "Contrato de campos con los repos consumidores: ningún campo "
                "estable desaparece sin quedar anotado en superseded_fields",
        "fix": "anotar el campo en superseded_fields (superseded_by + why) o "
               "volver a emitirlo; --freeze-fields solo tras revisar",
    },
    {
        "id": "changelog",
        "cmd": ["vault_changelog_check.py", "--check", "--strict"],
        "mide": "El changelog no contradice a git: hash existente, fecha igual a "
                "la del commit, ningún `pending` de una versión ya cerrada",
        "fix": "python scripts/vault_changelog_check.py --fijar-hash  (cierra la "
               "versión en curso); corregir la fecha contra su commit",
    },
    {
        "id": "arquitectura",
        "cmd": ["vault_arch.py", "--check", "--strict"],
        "mide": "Contextos acotados: fronteras, puertos, vocabularios con dueño, "
                "entorno declarado, AP-49 en cero",
        "fix": None,
    },
    {
        "id": "servicio",
        "cmd": ["vault_servicio.py", "--check", "--strict"],
        "mide": "Trazabilidad tool → grupo → capacidad → servicio: todo grupo "
                "pertenece a una capacidad y toda capacidad tiene tool viva",
        "fix": "clasificar el grupo en la capacidad a la que sirve; si no sirve "
               "a ninguna, la pregunta es por qué existe el grupo",
    },
    {
        "id": "blueprint",
        "cmd": ["vault_blueprint.py", "--check", "--strict"],
        "mide": "El plano de docs/BLUEPRINT.md no diverge de los registros, y "
                "ninguna norma estrena falta de puerta y test a la vez",
        "fix": "python scripts/vault_blueprint.py --blueprint  (regenera el "
               "plano); una norma nueva sin cobertura se cubre con un test, no "
               "se congela",
    },
    {
        "id": "norms_coherence",
        "cmd": ["vault_norms_coherence.py", "--check", "--strict"],
        "mide": "El catálogo de normas no se contradice ni con el código que "
                "lo aplica ni con las penalizaciones que lo pesan (AP-55)",
        "fix": "que el código nombre la norma en el sitio que la aplica, o que "
               "el catálogo retire la cobertura que no tiene; ampliar la "
               "baseline no es una de las dos",
    },
    {
        "id": "criterios",
        "cmd": ["vault_criterios.py", "--check", "--strict"],
        "mide": "Ningún módulo que clasifica notas reescribe un criterio que "
                "ya tiene dueño canónico (AP-57)",
        "fix": "importar al dueño en vez de decidir por cuenta propia; la "
               "baseline solo encoge",
    },
    {
        "id": "fuente_unica",
        "cmd": ["vault_fuente_unica.py", "--check", "--strict"],
        "mide": "El mismo dato tipado no tiene valores distintos en varias "
                "notas del mismo ámbito (AP-05)",
        "fix": "PAT-1: una nota canónica declara el dato y las demás la "
               "enlazan; verde solo cubre la parte decidible sin interpretar",
    },
    {
        "id": "ciclos",
        "cmd": ["vault_ciclos.py", "--check", "--strict"],
        "mide": "Ningún ciclo de importación nuevo se esquiva metiendo el "
                "import dentro de una función (AP-58)",
        "fix": "invertir la dependencia: el módulo de bajo nivel deja de "
               "pedirle el módulo entero al de alto; subir el import o "
               "ampliar la baseline no son la solución, solo esconden dónde",
    },
    {
        "id": "kernel",
        "cmd": ["vault_kernel.py", "--check", "--strict"],
        "mide": "La lista del núcleo no contradice a la forma medida del grafo: "
                "K1 delegada, fan-in/fan-out contra el escalón derivado y churn "
                "contra la mediana del dominio (AP-59)",
        "fix": "sacar el módulo del kernel o darle forma de núcleo —fan-out "
               "abajo, consumidores reales—; los umbrales se derivan del "
               "escalón y se publican, así que ajustarlos para pasar no es una "
               "opción, y la baseline solo encoge",
    },
    {
        "id": "excepcion_declarada",
        "cmd": ["vault_excepcion_declarada.py", "--check", "--strict"],
        "mide": "Ningún handler captura la excepción que una librería declara "
                "dejando escapar la que lanza de verdad (AP-61)",
        "fix": "delegar en el dueño que ya la contuvo —para el frontmatter, "
               "vault_lib.parse_frontmatter— o nombrar la excepción citando al "
               "dueño; ampliar la tupla en trece sitios sin dueño es AP-57 "
               "cometido al arreglar AP-61",
    },
    {
        "id": "recursos",
        "cmd": ["vault_recursos.py", "--check", "--strict"],
        "mide": "Ningún consumidor cruza una frontera de contexto para leer un "
                "recurso que no necesita el fan-out del productor (AP-62)",
        "fix": "partir el productor en catálogo y motor y repuntar a los "
               "consumidores al dueño; partir el fichero solo no mueve la "
               "cifra —lo enseñó v40.27—, y reclasificar el productor al "
               "núcleo sin medirle el fan-out lo vería AP-59",
    },
]


def _correr(puerta: Dict[str, Any], timeout: float = 180.0) -> Dict[str, Any]:
    """Ejecuta una puerta como subproceso y traduce su resultado.

    `encoding` y `errors` explícitos porque en Windows el default del sistema
    rompe con los acentos de los envelopes, y un `UnicodeDecodeError` aquí se
    leería como "la puerta falló" — un fallo del corredor presentado como
    fallo del medido, que es AP-51.
    """
    inicio = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / puerta["cmd"][0]), *puerta["cmd"][1:]],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(REPO_ROOT),
        )
    except subprocess.TimeoutExpired:
        return {
            "gate": puerta["id"],
            "ok": False,
            "reason": f"timeout tras {timeout:.0f}s",
            "seconds": round(time.monotonic() - inicio, 2),
        }

    salida: Dict[str, Any] = {
        "gate": puerta["id"],
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "seconds": round(time.monotonic() - inicio, 2),
    }

    # El envelope de la puerta, si lo emitió. Se guarda el detalle solo cuando
    # falla: en verde son ocho JSON grandes que nadie lee.
    try:
        envelope = json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        envelope = None

    if not salida["ok"]:
        salida["fix"] = puerta["fix"]
        salida["detail"] = envelope if envelope is not None else (
            proc.stdout or proc.stderr
        )[-1200:]
        if envelope is None:
            salida["reason"] = "la puerta no emitió JSON"
    return salida


def correr_todas(strict: bool = False) -> Dict[str, Any]:
    resultados = [_correr(p) for p in PUERTAS]
    fallidas = [r["gate"] for r in resultados if not r["ok"]]
    return {
        "ok": not fallidas,
        "tool": "vault_gate",
        "gates_total": len(PUERTAS),
        "passing": len(resultados) - len(fallidas),
        "failing": len(fallidas),
        "failed_gates": fallidas,
        "seconds": round(sum(r["seconds"] for r in resultados), 2),
        "gates": resultados,
        "hint": (
            "Verde aquí no es verde en la suite: `python -m pytest tests/` sigue "
            "siendo obligatorio antes de cerrar un cambio."
        ),
    }


#: Marcas del bloque derivado dentro de `CLAUDE.md`. Lo de dentro lo escribe
#: `checklist()`; lo de fuera se escribe a mano y no se toca.
MARCA_INICIO = "<!-- puertas:inicio — generado por vault_gate.py --fix-doc -->"
MARCA_FIN = "<!-- puertas:fin -->"


def checklist() -> str:
    """El bloque del checklist, derivado de `PUERTAS`.

    Hasta v40.16 cada puerta llevaba en `CLAUDE.md` su propio párrafo escrito a
    mano: dieciséis ensayos que repetían `mide` y `fix` con otras palabras. Eso
    es una segunda fuente de verdad sobre lo que mide cada puerta (AP-05) y
    envejece en la dirección cómoda — el registro cambia y la prosa se queda.
    Ahora se genera, y el `fix` que se lee cuando algo se pone en rojo es
    literalmente el del registro.

    Lo que **no** se deriva y sigue a mano fuera del bloque: por qué existe cada
    decisión, y las trampas que no caben en un campo.
    """
    lineas = [MARCA_INICIO, ""]
    for p in PUERTAS:
        cmd = "python scripts/" + " ".join(p["cmd"])
        lineas.append(f"- [ ] `{cmd}`")
        lineas.append(f"      {p['mide']}.")
        if p["fix"]:
            lineas.append(f"      *Se arregla con:* {p['fix']}")
    lineas += ["", MARCA_FIN]
    return "\n".join(lineas)


def _bloque_publicado(texto: str) -> str:
    if MARCA_INICIO not in texto or MARCA_FIN not in texto:
        return ""
    return MARCA_INICIO + texto.split(MARCA_INICIO, 1)[1].split(MARCA_FIN, 1)[0] + MARCA_FIN


def check_doc() -> Dict[str, Any]:
    """El checklist de `CLAUDE.md` no diverge del registro de puertas.

    Dos comprobaciones, y la segunda existe porque la primera se quedaba corta:

    1. **Ninguna puerta ausente**, por nombre de script. Se mira el documento
       entero: una puerta puede citarse también fuera del bloque.
    2. **El bloque derivado coincide con `checklist()`**. Sin esto, editar a
       mano el texto de una puerta pasaba desapercibido mientras el nombre del
       script siguiera ahí — que es como los dieciséis párrafos se despegaron
       del registro sin que nadie lo viera.
    """
    doc = REPO_ROOT / "CLAUDE.md"
    if not doc.exists():
        return emit_error("vault_gate", "FILE_NOT_FOUND", "CLAUDE.md no encontrado")

    texto = doc.read_text(encoding="utf-8", errors="replace")
    ausentes = [p["id"] for p in PUERTAS if p["cmd"][0] not in texto]
    publicado = _bloque_publicado(texto)
    if not publicado:
        divergencia = "sin_bloque"
    elif publicado.replace("\r\n", "\n").strip() != checklist().strip():
        divergencia = "bloque_desactualizado"
    else:
        divergencia = None
    return {
        "ok": not ausentes and not divergencia,
        "tool": "vault_gate",
        "action": "check-doc",
        "gates_total": len(PUERTAS),
        "gates_missing_from_checklist": ausentes,
        "checklist_drift": divergencia,
        "hint": (
            "El registro manda: si una puerta no está en el checklist, se añade "
            "al checklist — no se quita del registro. El bloque entre marcas es "
            "derivado: se regenera con `--fix-doc`, y lo escrito a mano ahí se "
            "pierde."
        ),
    }


def fix_doc() -> Dict[str, Any]:
    """Reescribe el bloque derivado de `CLAUDE.md` conservando sus finales de línea."""
    doc = REPO_ROOT / "CLAUDE.md"
    if not doc.exists():
        return emit_error("vault_gate", "FILE_NOT_FOUND", "CLAUDE.md no encontrado")

    crudo = doc.read_bytes().decode("utf-8")
    if MARCA_INICIO not in crudo or MARCA_FIN not in crudo:
        return emit_error(
            "vault_gate", "INVALID_INPUT",
            "CLAUDE.md no tiene el bloque `puertas:inicio`/`puertas:fin`: "
            "añade las dos marcas donde deba ir el checklist",
        )
    # El fichero es CRLF en este repo; se respeta el final de línea que ya tiene
    # o el diff sale de fichero entero.
    crlf = "\r\n" in crudo
    nuevo_bloque = checklist().replace("\n", "\r\n") if crlf else checklist()
    antes = crudo.split(MARCA_INICIO, 1)[0]
    despues = crudo.split(MARCA_FIN, 1)[1]
    salida = antes + nuevo_bloque + despues
    cambiado = salida != crudo
    if cambiado:
        doc.write_bytes(salida.encode("utf-8"))
    return {
        "ok": True, "tool": "vault_gate", "action": "fix-doc",
        "changed": cambiado, "gates_total": len(PUERTAS),
    }


def listar() -> Dict[str, Any]:
    return {
        "ok": True,
        "tool": "vault_gate",
        "action": "list",
        "gates_total": len(PUERTAS),
        "gates": [
            {
                "gate": p["id"],
                "command": "python scripts/" + " ".join(p["cmd"]),
                "measures": p["mide"],
                "fix": p["fix"],
            }
            for p in PUERTAS
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_gate — corre todas las puertas de cierre y agrega el veredicto",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:

  python vault_gate.py                # corre todas
  python vault_gate.py --strict       # exit 1 si alguna falla (gate de CI)
  python vault_gate.py --list         # qué mide cada puerta y cómo se arregla
  python vault_gate.py --check-doc    # el checklist de CLAUDE.md vs. el registro

No sustituye a la suite: `python -m pytest tests/` sigue siendo obligatorio.
""",
    )
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 si alguna puerta falla")
    parser.add_argument("--list", action="store_true", dest="listar",
                        help="Lista las puertas sin ejecutarlas")
    parser.add_argument("--check-doc", action="store_true", dest="check_doc",
                        help="Comprueba que el checklist de CLAUDE.md las cite todas")
    parser.add_argument("--fix-doc", action="store_true", dest="fix_doc",
                        help="Regenera el bloque derivado del checklist en CLAUDE.md")
    args = parser.parse_args()

    if args.fix_doc:
        r = fix_doc()
        print(json.dumps(r, ensure_ascii=False))
        return 0 if r["ok"] else 1

    if args.listar:
        print(json.dumps(listar(), ensure_ascii=False, indent=2))
        return 0

    if args.check_doc:
        r = check_doc()
        print(json.dumps(r, ensure_ascii=False))
        return 0 if r["ok"] else (1 if args.strict else 0)

    r = correr_todas(args.strict)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 1 if (args.strict and not r["ok"]) else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_gate"))
