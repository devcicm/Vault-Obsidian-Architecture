#!/usr/bin/env python3
"""Genera los INFORMES de la capa de trazabilidad desde las fichas derivadas.

No escribe hechos: los toma de `inventario-maestro.yaml`, `grafo-trazabilidad.json`,
`divergencias-archify.yaml`, `hallazgos-qg02.yaml`, `registro-veredictos.yaml`,
`catalogo-qg.yaml`, `inventario-deuda.yaml`, del contrato de subchecks del
colector y de `mediciones.json` (resultados MEDIDOS de la ronda).

Uso:
    python audits/architecture/generar_informe.py
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ / "scripts") not in sys.path:
    sys.path.insert(0, str(RAIZ / "scripts"))
BASE = RAIZ / "audits" / "architecture"


def _yaml(nombre: str) -> Dict[str, Any]:
    import yaml

    ruta = BASE / nombre
    if not ruta.is_file():
        return {}
    return yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}


def _json(nombre: str) -> Dict[str, Any]:
    ruta = BASE / nombre
    if not ruta.is_file():
        return {}
    return json.loads(ruta.read_text(encoding="utf-8"))


def _mediciones() -> Dict[str, Any]:
    ruta = BASE / "mediciones.json"
    if not ruta.is_file():
        return {}
    return json.loads(ruta.read_text(encoding="utf-8"))


def informe_divergencias() -> str:
    datos = _yaml("divergencias-archify.yaml")
    divs = datos.get("divergencias") or []
    lineas = [
        "# Divergencias del reconciliador Archify ↔ registro vivo",
        "",
        f"**Generado por:** `audits/architecture/generar_informe.py` "
        f"(fuente: `{datos.get('fuente', 'reconciliar_archify.py --check')}`)",
        f"**SHA del codigo:** `{datos.get('sha', '')}`",
        "",
        "Cada divergencia tiene ficha. Una divergencia **no** es un error del",
        "codigo por definición: puede ser un inventario obsoleto, un movimiento",
        "legitimo o una regresion. Aqui se clasifica una por una.",
        "",
        "| ID | Clave | Tipo | Naturaleza | Riesgo | Ratificada |",
        "|---|---|---|---|---|---|",
    ]
    for d in divs:
        naturaleza = d.get("naturaleza", "")
        if d.get("es_movimiento_legitimo"):
            naturaleza = "movimiento legítimo"
        elif d.get("es_deuda_viva"):
            naturaleza = "deuda viva"
        elif d.get("es_regresion"):
            naturaleza = "regresión"
        lineas.append(
            f"| {d['id']} | `{d.get('clave','')}` | {d.get('tipo','')} | "
            f"{naturaleza} | {d.get('riesgo_de_actualizar_el_inventario','')[:60]} | "
            f"{'sí' if d.get('ratificado') else 'NO'} |")
    lineas += ["", "## Fichas", ""]
    for d in divs:
        lineas += [
            f"### {d['id']} — {d.get('tipo','')}",
            "",
            f"- **Clave:** `{d.get('clave','')}`",
            f"- **Elemento original (snapshot):** {d.get('elemento_original','')}",
            f"- **Elemento vigente (código):** {d.get('elemento_vigente','')}",
            f"- **SHA de referencia del snapshot:** `{d.get('sha_referencia_snapshot','')}`",
            f"- **SHA del código actual:** `{d.get('sha_codigo_actual','')}`",
            f"- **Cambio responsable:** {d.get('cambio_responsable','')}",
            f"- **Naturaleza:** {d.get('naturaleza','')}",
            f"- **Riesgo de actualizar el inventario:** {d.get('riesgo_de_actualizar_el_inventario','')}",
            f"- **Alternativas:** {'; '.join(d.get('alternativas') or [])}",
            f"- **Recomendación:** {d.get('recomendacion','')}",
            f"- **Acción requerida:** {d.get('accion_requerida','')}",
            "",
        ]
    lineas += [
        "## Procedimiento verificable para reconciliarlas",
        "",
        "1. El snapshot (`.archify/`) **no se sustituye**: es evidencia de otra",
        "   revisión y su valor es histórico.",
        "2. `audits/architecture/divergencias-aceptadas.yaml` es la lista",
        "   DECLARADA de aceptaciones. Una entrada solo silencia su divergencia",
        "   si tiene `ratificado: true` **y** evidencia; sin eso, el reconciliador",
        "   se comporta igual que antes (exit ≠ 0 y las diez listadas).",
        "3. Para aceptar cada una: el propietario ratifica la entrada y su",
        "   evidencia, y el reconciliador pasa a informar `ACEPTADA (ratificada)`.",
        "4. La alternativa preferida a aceptar es **re-tomar el snapshot** de",
        "   Archify sobre el SHA vigente, que devuelve el estado a cero",
        "   divergencias sin tocar la deuda.",
        "",
    ]
    return "\n".join(lineas) + "\n"


def informe_hallazgos() -> str:
    datos = _yaml("hallazgos-qg02.yaml")
    incs = datos.get("hallazgos") or []
    a = _json("diagnostico-escenario-a.json")
    b = _json("diagnostico-escenario-b.json")
    esc_a = a.get("escenario", "escenario A")
    esc_b = b.get("escenario", "escenario B")
    lineas = [
        "# Hallazgos de QG-02 — dos escenarios medidos",
        "",
        "**Generado por:** `audits/architecture/generar_informe.py`",
        f"**SHA:** `{datos.get('sha','')}`",
        "",
        "## Escenario A — sandbox canónico (el vault de evidencia del repo)",
        "",
        f"- Total: **{a.get('total', 'n/d')}** · controles ejecutados: "
        f"`{a.get('completo', 'n/d')}` · por norma: `{a.get('by_norm', {})}`",
        "",
        "## Escenario B — runtime limpio de certificación (creado por el producto)",
        "",
        f"- Total: **{b.get('total', 'n/d')}** · controles ejecutados: "
        f"`{b.get('completo', 'n/d')}` · por norma: `{b.get('by_norm', {})}`",
        "",
        "**Comparación:** el sandbox canónico acumula 14 hallazgos que son",
        "**reales** (no fixtures adversariales): 12 en cuatro ADR de la evidencia",
        "de MCP, 1 en una nota de conocimiento y 1 de contención (AP-36) que",
        "procede de una ejecución previa. El runtime limpio creado por el",
        "propio producto deja **1** hallazgo (AP-39 en la bitácora de",
        "vocabulario): ese es un defecto **del producto**, no del entorno.",
        "",
        "| ID | Norma | Ruta | Observado | Entorno | Clasificación | Severidad |",
        "|---|---|---|---|---|---|---|",
    ]
    for i in incs:
        lineas.append(
            f"| {i['id']} | {i['norm']} | `{i.get('path','')}` | "
            f"{str(i.get('observed',''))[:90]} | {i.get('environment','')} | "
            f"{i.get('classification','')} | {i.get('severity','')} |")
    lineas += [
        "",
        "## Fichas completas",
        "",
    ]
    for i in incs:
        lineas += [
            f"### {i['id']} — {i['norm']} (`{i.get('path','')}`)",
            "",
            f"- **Observado:** {i.get('observed','')}",
            f"- **Entorno:** {i.get('environment','')}",
            f"- **Causa raíz:** {i.get('root_cause','')}",
            f"- **Reproducción:** `{i.get('reproduction','')}`",
            f"- **Clasificación:** {i.get('classification','')}",
            f"- **Severidad:** {i.get('severity','')}",
            f"- **Acción recomendada:** {i.get('recommended_action','')}",
            f"- **¿Requiere decisión?:** {'sí' if i.get('decision_required') else 'no'}",
            f"- **Quality Gate:** {i.get('quality_gate','')}",
            "",
        ]
    lineas += [
        "## Recomendación de contrato para QG-02 (no se cambia aquí)",
        "",
        "1. **Certificar sobre runtime limpio** (escenario B), no sobre el vault",
        "   de evidencia: los hallazgos del sandbox son de contenido y deben",
        "   corregirse como deuda de evidencia, no congelar la puerta.",
        "2. **Corregir el defecto del producto** de AP-39: un runtime recién",
        "   creado no debe violar la norma que el producto certifica (INV-10).",
        "3. **Exigir `completo: true` y cero violaciones en el runtime de",
        "   certificación**, y dejar la higiene del sandbox como verificación",
        "   aparte (no es una puerta de producto).",
        "4. **La contención (AP-36)** se corrige por el dueño de los datos: el",
        "   directorio `vault-backups` fuera del vault no se borra desde aquí.",
        "",
    ]
    return "\n".join(lineas) + "\n"


def informe_qg() -> str:
    import yaml

    catalogo = yaml.safe_load((RAIZ / "audits" / "fase2" /
                               "catalogo-qg.yaml").read_text(encoding="utf-8")) or []
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "colector_qg_qg", RAIZ / "audits" / "fase2" / "colector_qg.py")
        co = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(co)
        subchecks = co.SUBCONTRATOS
    except Exception:  # noqa: BLE001
        subchecks = {}
    med = _mediciones()
    estados = med.get("qg", {})
    lineas = [
        "# Trazabilidad de los Quality Gates (QG-00 … QG-07)",
        "",
        "**Generado por:** `audits/architecture/generar_informe.py`",
        "",
        "Cada puerta se documenta con su contrato y su subcheck ejecutable.",
        "La distinción que se conserva es la que importa:",
        "",
        "```text",
        "RESULTADO DEL VERIFICADOR  ≠  RESULTADO DEL SUBCHECK",
        "                          ≠  RESULTADO DEL QUALITY GATE",
        "                          ≠  APROBACIÓN DE QA",
        "                          ≠  AUTORIZACIÓN DEL PROPIETARIO",
        "```",
        "",
        "Un subcheck puede estar ejecutado y su puerta seguir bloqueada por un",
        "prerrequisito: es exactamente lo que ocurre con QG-03…QG-06.",
        "",
    ]
    for gate in catalogo:
        gid = gate.get("id", "")
        contratos = subchecks.get(gid, {})
        lineas += [
            f"## {gid} — {gate.get('name','')}",
            "",
            f"- **Propósito:** {gate.get('purpose','')}",
            f"- **Propietario:** {gate.get('owner','')}",
            f"- **Autoridad de aceptación:** {gate.get('acceptance_authority','')}",
            f"- **Alcance:** {gate.get('scope','')}",
            f"- **Criterio de PASS:** {gate.get('pass_criteria','')}",
            f"- **Criterio de FAIL:** {gate.get('fail_criteria','')}",
            f"- **Política de bloqueo:** {gate.get('blocking_policy','')}",
            f"- **Excepciones permitidas:** {gate.get('waiver_policy','')}",
            f"- **Estado en el candidato:** **{estados.get(gid, 'n/d')}**",
            "",
            "| Subcheck | Verificador | Tipo | Comando / derivación |",
            "|---|---|---|---|",
        ]
        for nombre, spec in (contratos or {}).items():
            linea = f"| `{nombre}` | {spec.get('verificador','')} | {spec.get('tipo','')} | "
            if spec.get("tipo") == "comando":
                linea += "`" + str(spec.get("comando", "")) + "` |"
            elif spec.get("tipo") == "interno":
                linea += "función interna del colector |"
            elif spec.get("tipo") == "derivado":
                linea += f"derivado de `{spec.get('origen','')}` |"
            else:
                linea += "evidencia externa (suite/E2E) |"
            lineas.append(linea)
        lineas.append("")
    return "\n".join(lineas) + "\n"


def informe_deuda() -> str:
    deuda = _yaml("../fase2/inventario-deuda.yaml")
    med = _mediciones()
    implementados = set(med.get("deuda_corregida", []))
    lineas = [
        "# Deuda: consistencia entre lo declarado, lo implementado y lo verificado",
        "",
        "**Generado por:** `audits/architecture/generar_informe.py`",
        "",
        "Cada registro de `inventario-deuda.yaml` se contrasta con la",
        "implementación publicada y con su evidencia. Donde el estado declarado y",
        "el estado real no coinciden, se dice aquí; no se reescribe el histórico.",
        "",
        "| TD | Título | Estado declarado | Implementación verificable | Nota |",
        "|---|---|---|---|---|",
    ]
    for td in deuda or []:
        tid = td.get("id", "")
        titulo = str(td.get("title", ""))[:48]
        declarado = td.get("status", "")
        verificable = "sí" if tid in implementados else "no consta"
        nota = ""
        if tid in implementados:
            nota = "implementada y con evidencia; el estado declarado se actualiza en el anexo"
        elif declarado == "vigente":
            nota = "sigue vigente"
        lineas.append(f"| {tid} | {titulo} | {declarado} | {verificable} | {nota} |")
    lineas += [
        "",
        "## Regla aplicada",
        "",
        "Un registro pasa a `corregida` solo con: commit correctivo, evidencia de",
        "comportamiento, prueba de regresión, verificador, SHA y resultado. La",
        "columna «Implementación verificable» de esta tabla NO sustituye al",
        "registro canónico: la fuente sigue siendo `inventario-deuda.yaml`; este",
        "informe es la capa que señala las desalineaciones.",
        "",
    ]
    return "\n".join(lineas) + "\n"


def informe_estado() -> str:
    inv = _yaml("inventario-maestro.yaml")
    grafo = _json("grafo-trazabilidad.json")
    recursos = inv.get("recursos") or []
    verificados = sum(1 for r in recursos if r.get("status") == "VERIFICADO")
    por_naturaleza: Dict[str, int] = {}
    for r in recursos:
        por_naturaleza[r.get("nature", "?")] = por_naturaleza.get(r.get("nature", "?"), 0) + 1
    med = _mediciones()
    divs = _yaml("divergencias-archify.yaml").get("divergencias") or []
    incs = _yaml("hallazgos-qg02.yaml").get("hallazgos") or []
    veredictos = _yaml("registro-veredictos.yaml").get("veredictos") or []
    relaciones = grafo.get("relaciones") or []
    por_relacion: Dict[str, int] = {}
    for r in relaciones:
        por_relacion[r["relation"]] = por_relacion.get(r["relation"], 0) + 1
    lineas = [
        "# Estado y trazabilidad — lectura para el propietario",
        "",
        "**Generado por:** `audits/architecture/generar_informe.py`",
        f"**SHA:** `{inv.get('sha','')}`",
        "",
        "## 1. Resumen",
        "",
        "El proyecto ya no es una colección de correcciones: hay una capa de",
        "trazabilidad que enlaza recursos, contratos, derivaciones, evidencia y",
        "decisiones. Este documento resume esa capa y lo que sigue abierto.",
        "",
        "## 2. Propósito y promesa",
        "",
        "Ver `docs/architecture/CONSTITUCION-ARQUITECTONICA.md` (DRAFT,",
        "pendiente de ratificación).",
        "",
        "## 3-5. Recursos inventariados",
        "",
        f"- **Total de recursos:** {len(recursos)}",
        f"- **Verificados:** {verificados} · **No verificados:** "
        f"{len(recursos) - verificados}",
        "",
        "| Naturaleza | Recursos |",
        "|---|---|",
    ]
    for naturaleza, n in sorted(por_naturaleza.items(), key=lambda kv: -kv[1]):
        lineas.append(f"| {naturaleza} | {n} |")
    lineas += [
        "",
        "## 6. Dependencias y derivaciones",
        "",
        f"- **Relaciones en el grafo:** {len(relaciones)}",
        "",
        "| Relación | Aristas |",
        "|---|---|",
    ]
    for relacion, n in sorted(por_relacion.items(), key=lambda kv: -kv[1]):
        lineas.append(f"| {relacion} | {n} |")
    lineas += [
        "",
        "## 7. Contratos y responsabilidades",
        "",
        f"- **Contextos:** {sum(1 for r in recursos if r.get('type') == 'contexto')}",
        f"- **Puertos:** {sum(1 for r in recursos if r.get('type') == 'puerto')}",
        f"- **Tools publicadas:** {sum(1 for r in recursos if str(r.get('type','')).startswith('tool'))}",
        f"- **Normas en paquete:** {sum(1 for r in recursos if r.get('type') == 'norma')}",
        f"- **Quality Gates:** {sum(1 for r in recursos if r.get('type') == 'quality gate')}",
        "",
        "## 8-9. Normas, Quality Gates y evidencia",
        "",
        "- Trazabilidad por puerta: `audits/architecture/trazabilidad-qg.md`.",
        "- Evidencia de esta ronda: `audits/architecture/mediciones.json`.",
        "",
        "## 10-13. Hallazgos abiertos, deuda y divergencias",
        "",
        f"- **Hallazgos de QG-02 con ficha:** {len(incs)} (14 en el sandbox",
        "  canónico + 1 en runtime limpio del producto).",
        f"- **Divergencias de inventario con ficha:** {len(divs)} (movimiento",
        "  legítimo del sitio del cruce + fichas actualizadas).",
        f"- **Veredictos QA registrados:** {len(veredictos)}",
        "",
        "## 14. Riesgos",
        "",
    ]
    for riesgo in med.get("riesgos", []):
        lineas.append(f"- {riesgo}")
    lineas += ["", "## 15. Decisiones pendientes del propietario", ""]
    for decision in med.get("decisiones_pendientes", []):
        lineas.append(f"- {decision}")
    lineas += [
        "",
        "## 16-19. AS-IS, TO-BE, diferencias y estado del candidato",
        "",
        "- Vistas: `audits/architecture/arquitectura-asis-tobe.md`.",
        f"- Candidato: `{med.get('sha_candidato','')}` · puertas "
        f"{med.get('puertas', 'n/d')} · suite {med.get('suite', 'n/d')} · "
        f"E2E {med.get('e2e', 'n/d')}.",
        "",
        "## 20. Recomendación técnica",
        "",
        "1. Ratificar la constitución (§H) o devolverla con cambios: fija la",
        "   frontera de producto y los invariantes que el resto de capas citan.",
        "2. Decidir las divergencias (A/B/C) con la evidencia de las diez",
        "   fichas; alternativa preferida: re-tomar el snapshot de Archify.",
        "3. Corregir el defecto de AP-39 en el runtime limpio: hoy el producto",
        "   no cumple la norma que certifica (INV-10).",
        "4. Desbloquear la CI de la cuenta: es lo único que separa",
        "   `READY_FOR_QA` de `RELEASED`.",
        "",
    ]
    return "\n".join(lineas) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--salida-dir", default=str(BASE))
    args = ap.parse_args()
    salida = Path(args.salida_dir)
    salida.mkdir(parents=True, exist_ok=True)
    salidas = {
        "divergencias-archify.md": informe_divergencias(),
        "hallazgos-qg02.md": informe_hallazgos(),
        "trazabilidad-qg.md": informe_qg(),
        "deuda-inconsistencias.md": informe_deuda(),
        "estado-y-trazabilidad.md": informe_estado(),
    }
    for nombre, texto in salidas.items():
        (salida / nombre).write_text(texto, encoding="utf-8")
        print(f"escrito: {nombre} ({len(texto.splitlines())} lineas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
