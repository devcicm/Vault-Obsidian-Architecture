#!/usr/bin/env python3
"""Genera los documentos narrativos de las fichas derivadas.

  - DIVERGENCIAS-ARCHIFY.md  (10 fichas DIV-01..DIV-10)
  - HALLAZGOS-QG02.md        (fichas INC-0001..INC-0015, dos escenarios)

Los datos salen de los YAML derivados; este guion solo los redacta.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent


def _yaml(nombre: str) -> dict:
    import yaml

    return yaml.safe_load((BASE / nombre).read_text(encoding="utf-8")) or {}


def divergencias() -> str:
    datos = _yaml("divergencias-archify.yaml")
    fichas = datos.get("divergencias") or []
    lineas = [
        "# Las diez divergencias Archify ↔ registro vivo — fichas individuales",
        "",
        f"**SHA:** `{datos.get('sha','')}` · **Fuente:** `{datos.get('fuente','')}`",
        "",
        "Causa común: la composición de los controles AP-40/42/43 se movió de",
        "`vault_norms_engine` a la fachada `vault_norms` (commit `667a6a5`), y la",
        "ficha de la deuda se actualizó (`59d0465`). El snapshot de Archify",
        "documenta la revisión anterior, así que las diez divergencias comparten",
        "esa causa. **Actualizar el inventario no elimina el adeudado**: la deuda",
        "sigue declarada como `a_eliminar` con plazo y decisión pendiente.",
        "",
        "| ID | Clave | Naturaleza | Ratificada |",
        "|---|---|---|---|",
    ]
    for f in fichas:
        lineas.append(f"| {f['id']} | `{f.get('clave','')}` | "
                      f"{f.get('naturaleza','')} | "
                      f"{'sí' if f.get('ratificado') else 'NO'} |")
    lineas.append("")
    for f in fichas:
        lineas += [
            f"## {f['id']}",
            "",
            f"- **Clave del reconciliador:** `{f.get('clave','')}`",
            f"- **Tipo:** {f.get('tipo','')}",
            f"- **Elemento original (snapshot):** {f.get('elemento_original','')}",
            f"- **Elemento vigente (código):** {f.get('elemento_vigente','')}",
            f"- **SHA snapshot:** `{f.get('sha_referencia_snapshot','')}`",
            f"- **SHA código actual:** `{f.get('sha_codigo_actual','')}`",
            f"- **Cambio responsable:** {f.get('cambio_responsable','')}",
            f"- **Naturaleza:** {f.get('naturaleza','')}",
            f"- **¿Movimiento legítimo?** {'sí' if f.get('es_movimiento_legitimo') else 'no'}",
            f"- **¿Deuda viva?** {'sí' if f.get('es_deuda_viva') else 'no'}",
            f"- **¿Regresión?** {'sí' if f.get('es_regresion') else 'no'}",
            f"- **Riesgo de actualizar el inventario:** "
            f"{f.get('riesgo_de_actualizar_el_inventario','')}",
            f"- **Alternativas:** {' · '.join(f.get('alternativas') or [])}",
            f"- **Recomendación:** {f.get('recomendacion','')}",
            f"- **Acción que requiere ratificación:** "
            f"{f.get('accion_requerida','')}",
            "",
        ]
    lineas += [
        "## Procedimiento de reconciliación",
        "",
        "1. El snapshot **no se sustituye**: es evidencia de otra revisión.",
        "2. `divergencias-aceptadas.yaml` es la lista DECLARADA de aceptaciones;",
        "   sin `ratificado: true` y evidencia, el reconciliador las lista igual.",
        "3. Alternativa preferida: **re-tomar el snapshot** de Archify sobre el",
        "   SHA vigente → cero divergencias sin tocar la deuda.",
        "4. La decisión es del **propietario**; el ejecutor no ratifica.",
        "",
    ]
    return "\n".join(lineas) + "\n"


def hallazgos() -> str:
    datos = _yaml("hallazgos-qg02.yaml")
    fichas = datos.get("hallazgos") or []
    lineas = [
        "# Los quince hallazgos de QG-02 — fichas con los dos escenarios",
        "",
        f"**SHA:** `{datos.get('sha','')}`",
        "",
        "- **Escenario A** — sandbox canónico (`vault-sandbox`): 14 hallazgos",
        "- **Escenario B** — runtime limpio creado por el producto: 1 hallazgo",
        "",
        "Conclusión: los 14 del sandbox son hallazgos **reales de contenido de",
        "evidencia** (no fixtures adversariales): 12 en cuatro ADR de MCP, 1 en",
        "una nota de conocimiento y 1 de contención (AP-36) procedente de una",
        "ejecución previa. El runtime limpio del producto deja **1** hallazgo",
        "(AP-39): eso es un defecto **del producto** — un runtime recién creado",
        "viola la norma que el producto certifica (invariante INV-10).",
        "",
        "| ID | Norma | Ruta | Entorno | Clasificación | Severidad |",
        "|---|---|---|---|---|---|",
    ]
    for f in fichas:
        lineas.append(f"| {f['id']} | {f['norm']} | `{f.get('path','')}` | "
                      f"{f.get('environment','')} | {f.get('classification','')} | "
                      f"{f.get('severity','')} |")
    lineas.append("")
    for f in fichas:
        lineas += [
            f"## {f['id']} — {f['norm']} (`{f.get('path','')}`)",
            "",
            f"- **Entorno:** {f.get('environment','')}",
            f"- **Observado:** {f.get('observed','')}",
            f"- **Causa raíz:** {f.get('root_cause','')}",
            f"- **Reproducción:** `{f.get('reproduction','')}`",
            f"- **Clasificación:** {f.get('classification','')}",
            f"- **Severidad:** {f.get('severity','')}",
            f"- **Acción recomendada:** {f.get('recommended_action','')}",
            f"- **¿Requiere decisión del propietario?** "
            f"{'sí' if f.get('decision_required') else 'no'}",
            "",
        ]
    lineas += [
        "## Recomendación de contrato para QG-02 (pendiente del propietario)",
        "",
        "1. Certificar sobre **runtime limpio de certificación** (escenario B),",
        "   no sobre el vault de evidencia.",
        "2. Corregir el defecto del producto AP-39 (INV-10).",
        "3. La higiene del vault de evidencia (los 14) es deuda de contenido,",
        "   no una puerta de producto.",
        "4. La contención AP-36 se resuelve con el dueño de los datos",
        "   (`vault-backups` fuera del vault no se borra desde aquí).",
        "",
    ]
    return "\n".join(lineas) + "\n"


def main() -> int:
    (BASE / "DIVERGENCIAS-ARCHIFY.md").write_text(divergencias(), encoding="utf-8")
    (BASE / "HALLAZGOS-QG02.md").write_text(hallazgos(), encoding="utf-8")
    print("documentos de fichas generados")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
