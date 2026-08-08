#!/usr/bin/env python3
"""vault_sanacion — El plan de sanación de un vault preexistente, medido.

Entry point de la skill `vault-sanacion`. `docs/MODO-AGENTICO-SANACION.md`
describe 12 fases para tomar un vault que ya existe —escrito por agentes sin
estándar, o por personas, o por ambos— y dejarlo conforme sin perder nada. Ese
documento se ejecutaba **leyéndolo**: el agente lo abría, decidía por su cuenta
qué fases aplicaban, y esa decisión no quedaba escrita en ningún sitio.

Lo que esta tool aporta no es automatizar la sanación —no puede, y no debe— sino
**medir antes de decidir**. Devuelve las 12 fases con un veredicto por fase:
`applies`, `clean` o `unknown`, cada uno con la evidencia que lo sostiene. Un
plan sin medida es una lista de buenas intenciones; el orden de las fases importa
—reubicar antes de arreglar enlaces multiplica los enlaces rotos— y saber cuáles
puedes saltarte es lo que hace que el orden sea seguro.

**No escribe. Nunca.** Es la regla 2 del modo agéntico —el subagente propone, no
escribe— aplicada a la tool que propone: cada fase nombra la tool del estándar
que sí escribe, con su guard y su entrada en `.change-log.json`. Una tool de
diagnóstico con permiso de escritura es un segundo autor sin norma que lo
gobierne.

El vault destino se resuelve por autodetección de `vault_io`, o se fuerza con la
variable de entorno `VAULT_ROOT` — que es como se apunta a un vault ajeno, que es
el único sitio donde esto sirve de algo (regla 7 de CLAUDE.md: `vault-sandbox/`
comparte los supuestos de las tools y no puede revelar una discrepancia).

Uso:
    VAULT_ROOT=/ruta/al/vault-ajeno python vault_sanacion.py
    python vault_sanacion.py --phase 8        # detalle de una fase
    python vault_sanacion.py --strict         # exit 1 si alguna fase aplica
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from vault_errors import emit_error, wrap_main
import vault_io

#: Las 12 fases de `docs/MODO-AGENTICO-SANACION.md`. El orden **es** el
#: contrato: cada fase asume cerradas las anteriores. Reubicar (7) antes de
#: arreglar enlaces (8) no es una preferencia de estilo — al revés, cada nota
#: movida rompe los enlaces que acabas de reparar.
FASES = [
    (1, "Copiar el vault; congelar el original", None,
     "dónde vive la copia (fuera de git si hay datos ajenos)"),
    (2, "Inventario: qué hay y qué falta", "vault_audit", None),
    (3, "Estructura: secciones numeradas", "vault_init",
     "qué carpeta suelta corresponde a qué sección"),
    (4, "Frontmatter mínimo en notas sin él", "vault_write",
     "de dónde se infiere: ruta, H1, mtime"),
    (5, "Encoding y mojibake", "vault_encoding", None),
    (6, "Normas: pasada de vault_norms --audit", "vault_norms",
     "cuáles son deuda real y cuáles ruido de la tool"),
    (7, "Reubicar lo que está fuera de estructura", "vault_move",
     "exige mapa de rollback (AP-10)"),
    (8, "Enlaces rotos", "vault_graph_fix --classify",
     "qué es una nota ausente y qué un símbolo de código"),
    (9, "Diagramas", "vault_mermaid_check", None),
    (10, "Tags y vocabulario", "vault_tags", "el vocabulario propio del dominio"),
    (11, "Índices y grafo", "vault_reindex, vault_graph", None),
    (12, "Re-audit y contraste contra la baseline", "vault_audit",
     "qué deltas son avance y cuáles son artefacto"),
]


def _fase(numero, veredicto, evidencia, medida=None):
    n, titulo, tool, decision = next(f for f in FASES if f[0] == numero)
    entrada = {
        "phase": n,
        "title": titulo,
        "tool": tool,
        "verdict": veredicto,
        "evidence": evidencia,
    }
    if medida is not None:
        entrada["measured"] = medida
    if decision:
        entrada["decision_not_automatable"] = decision
    return entrada


def _medir_audit(root):
    """Fases 2, 4 y 12: lo que el audit ya sabe contar.

    Se apunta la raíz del proceso, no la constante del módulo. `vault_audit`
    migró al contexto Gobernanza y resuelve la raíz al usarla: `vault_audit.
    VAULT_ROOT = root` seguía siendo una asignación legal de Python y no tenía
    ningún efecto, así que las fases 2, 4 y 12 habrían medido el vault
    **detectado** en vez del pedido —y devuelto un plan verosímil para el vault
    equivocado, sin excepción que lo delatara—. Es justo el modo de fallo que el
    modo agéntico de sanación no puede permitirse: se ejecuta contra vaults
    ajenos, donde detectado y pedido casi nunca coinciden.
    """
    previa = vault_io.get_vault_root()
    try:
        import vault_audit

        vault_io.set_vault_root(root)
        return vault_audit.vault_audit()
    except Exception as exc:  # noqa: BLE001 — una medida que falla no es "limpio"
        return {"_error": f"{type(exc).__name__}: {exc}"}
    finally:
        # La raíz es estado de proceso: apuntarla y no devolverla haría que una
        # sola llamada a `plan_de_sanacion()` reapuntase el vault de quien la
        # invocó. Read-only significa también no dejar rastro en el proceso.
        vault_io.set_vault_root(previa)


def _medir_normas(root):
    """Fase 6."""
    try:
        import vault_norms

        return vault_norms.vault_norms_audit(root=root)
    except Exception as exc:  # noqa: BLE001
        return {"_error": f"{type(exc).__name__}: {exc}"}


def _medir_indice(root):
    """Fase 11: el mismo criterio que la puerta de AP-47."""
    try:
        import vault_reindex

        return vault_reindex.index_coherence(root=root)
    except Exception as exc:  # noqa: BLE001
        return {"_error": f"{type(exc).__name__}: {exc}"}


#: Los tipos de `vault_encoding.detect_issues` que significan **daño**, no
#: estilo. `smart_quotes`, `unicode_dash` y `nfd_char` describen texto correcto
#: escrito a propósito: este mismo repo redacta con em-dash. Contarlos aquí da
#: 106 notas «afectadas» de 111 en `vault-sandbox/` — un plan donde la fase 5
#: siempre aplica es un plan que nadie lee. La fase 5 del modo agéntico es
#: mojibake y caracteres rotos, no normalización tipográfica; `vault_encoding`
#: mide bien, lo que estaba mal era el criterio con que se leía su salida.
_ENCODING_DANINO = frozenset({"invisible_char", "control_char", "bom",
                             "newline_inconsistency", "mojibake"})


def _medir_encoding(root):
    """Fase 5: el audit no cuenta mojibake, así que se cuenta aquí.

    Devuelve el número de notas con al menos un hallazgo **dañino**, o `None`
    si no se pudo medir. Contar notas y no hallazgos es deliberado: la unidad
    de trabajo de la fase 5 es el fichero que hay que abrir.
    """
    try:
        import vault_encoding
        import vault_reindex

        afectadas = 0
        for nota in vault_reindex._notas_en_disco(root=root):
            try:
                texto = nota.read_text(encoding="utf-8", errors="replace")
            except Exception:  # noqa: BLE001 — ilegible se trata aparte, en el audit
                continue
            hallazgos = vault_encoding.detect_issues(texto)
            if any(h.get("type") in _ENCODING_DANINO for h in hallazgos):
                afectadas += 1
        return afectadas
    except Exception:  # noqa: BLE001
        return None


def _secciones_ausentes(root):
    """Fase 3: contra el registro canónico, no contra una lista propia."""
    try:
        import vault_registry

        return [
            s for s in vault_registry.ORDERED_SECTIONS
            if not (root / s).is_dir()
        ]
    except Exception as exc:  # noqa: BLE001
        return [f"_error: {type(exc).__name__}: {exc}"]


def plan_de_sanacion(root=None):
    """Las 12 fases con veredicto y evidencia. Read-only de principio a fin."""
    root = Path(root) if root else vault_io.get_vault_root()
    audit = _medir_audit(root)
    normas = _medir_normas(root)
    indice = _medir_indice(root)
    ausentes = _secciones_ausentes(root)

    def _stat(*claves):
        """Un contador del audit, o None si el audit no pudo medirlo.

        `issues.*` son listas de hallazgos, no cifras: lo que interesa aquí es
        cuántos hay. Leer la longitud en vez de exigir un `int` es la diferencia
        entre siete fases en `unknown` y siete fases medidas — el primer intento
        pedía `int` y dejó el plan entero a ciegas sin que nada fallara.
        """
        nodo = audit
        for k in claves:
            if not isinstance(nodo, dict) or k not in nodo:
                return None
            nodo = nodo[k]
        if isinstance(nodo, bool):
            return None
        if isinstance(nodo, int):
            return nodo
        if isinstance(nodo, (list, tuple, dict)):
            return len(nodo)
        return None

    def _por_contador(numero, valor, texto_si_aplica, texto_si_limpio):
        if valor is None:
            return _fase(numero, "unknown",
                         "el audit no pudo medirlo; trátalo como pendiente")
        if valor:
            return _fase(numero, "applies", texto_si_aplica.format(n=valor), valor)
        return _fase(numero, "clean", texto_si_limpio, 0)

    fases = []

    # 1 — Copiar. Ninguna tool puede saber si ya lo hiciste; se declara siempre
    # pendiente a propósito. Dar por hecha la copia es el único fallo de este
    # modo que no tiene vuelta atrás.
    fases.append(_fase(
        1, "applies",
        "sin copia verificable, la sanación es irreversible: hazla y congela el "
        "original antes de la fase 2. Ninguna medida puede confirmarlo por ti.",
    ))

    total = _stat("stats", "total")
    fases.append(_fase(
        2,
        "clean" if isinstance(total, int) else "unknown",
        f"inventario tomado: {total} notas" if isinstance(total, int)
        else "el audit no devolvió inventario; sin baseline no hay fase 12",
        total,
    ))

    fases.append(_fase(
        3,
        "applies" if ausentes else "clean",
        f"{len(ausentes)} sección(es) del registro sin carpeta: "
        f"{', '.join(ausentes[:6])}" if ausentes
        else "las 22 secciones del registro existen",
        len(ausentes),
    ))

    fases.append(_por_contador(
        4, _stat("issues", "missingType"),
        "{n} nota(s) sin `type:` en el frontmatter",
        "toda nota declara su `type:`",
    ))
    fases.append(_por_contador(
        5, _medir_encoding(root),
        "{n} nota(s) con caracteres rotos: invisibles, de control, BOM o "
        "newlines mezclados (la tipografía deliberada no cuenta)",
        "sin encoding dañado",
    ))

    violaciones = normas.get("violations") if isinstance(normas, dict) else None
    if violaciones is None:
        fases.append(_fase(6, "unknown", f"vault_norms no pudo medir: "
                                         f"{normas.get('_error', 'sin detalle')}"))
    else:
        fases.append(_fase(
            6, "applies" if violaciones else "clean",
            f"{len(violaciones)} violación(es) de norma; decide cuáles son deuda "
            f"real antes de tocar nada" if violaciones
            else "0 violaciones contra el catálogo de normas",
            len(violaciones),
        ))

    fases.append(_por_contador(
        7, _stat("issues", "orphans"),
        "{n} nota(s) fuera de la estructura — exige mapa de rollback (AP-10)",
        "ninguna nota fuera de estructura",
    ))
    fases.append(_por_contador(
        8, _stat("issues", "brokenLinks"),
        "{n} enlace(s) roto(s); clasifica antes de reparar",
        "sin enlaces rotos",
    ))
    fases.append(_por_contador(
        9, _stat("issues", "mermaidErrors"),
        "{n} diagrama(s) que no compilan",
        "los diagramas compilan",
    ))
    fases.append(_por_contador(
        10, _stat("issues", "missingTags"),
        "{n} nota(s) sin tags",
        "toda nota tiene tags",
    ))

    if "_error" in indice:
        fases.append(_fase(11, "unknown", f"no se pudo medir: {indice['_error']}"))
    else:
        fases.append(_fase(
            11,
            "clean" if indice.get("ok") else "applies",
            f"índice al día ({indice.get('indexed')} indexadas)"
            if indice.get("ok")
            else f"{indice.get('status')}: {indice.get('on_disk')} en disco, "
                 f"{indice.get('indexed')} indexadas (AP-47)",
            indice.get("missing_count"),
        ))

    # 12 — El re-audit no puede estar "limpio" antes de sanar: mide el después
    # contra el antes, y el antes es esta misma ejecución.
    fases.append(_fase(
        12, "applies",
        "vuelve a correr esta tool al terminar y contrasta fase a fase; los "
        "contadores discreparán, y la discrepancia informa",
    ))

    aplican = [f["phase"] for f in fases if f["verdict"] == "applies"]
    desconocidas = [f["phase"] for f in fases if f["verdict"] == "unknown"]
    return {
        "ok": True,
        "tool": "vault_sanacion",
        "vault_root": str(root),
        "vault_root_origin": vault_io.vault_root_origin(),
        "phases": fases,
        "phases_apply": aplican,
        "phases_unknown": desconocidas,
        "writes": False,
        "next": (
            f"empieza por la fase {aplican[0]}" if aplican
            else "ninguna fase con deuda medible; la 1 y la 12 son siempre tuyas"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_sanacion — plan de sanación medido; no escribe nada",
    )
    parser.add_argument(
        "--phase", type=int, help="Detalle de una sola fase (1..12)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 si alguna fase aplica o no se pudo medir",
    )
    args = parser.parse_args()

    plan = plan_de_sanacion()
    if args.phase:
        elegida = [f for f in plan["phases"] if f["phase"] == args.phase]
        if not elegida:
            print(json.dumps(
                emit_error("vault_sanacion", "INVALID_VALUE",
                           f"fase {args.phase} fuera de rango (1..12)"),
                indent=2, ensure_ascii=False,
            ))
            return 1
        plan = {**plan, "phases": elegida}

    print(json.dumps(plan, indent=2, ensure_ascii=False))
    if args.strict and (plan["phases_apply"] or plan["phases_unknown"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_sanacion"))
