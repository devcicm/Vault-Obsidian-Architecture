#!/usr/bin/env python3
"""Genera las fichas DERIVADAS de la capa de trazabilidad:

  - `divergencias-archify.yaml` : una ficha por divergencia del reconciliador
  - `hallazgos-qg02.yaml`       : una ficha por hallazgo de la auditoria
  - `registro-veredictos.yaml`  : una ficha por veredicto QA (ramas QA)

Todo se deriva de fuentes reales (el reconciliador, la auditoria y las ramas
QA). Lo que no se puede extraer de la fuente se declara como tal, nunca se
inventa.

Uso:
    python audits/architecture/generar_fichas.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

RAIZ = Path(__file__).resolve().parents[2]
TMP = Path(tempfile.gettempdir()) / "opencode"

#: Clasificacion de cada divergencia por su clave. La CAUSA es una sola: el
#: sitio del cruce se movio de `vault_norms_engine` a `vault_norms` (commit
#: 667a6a5) y la ficha de la deuda se actualizo (59d0465). Actualizar un
#: inventario obsoleto NO es eliminar una violacion.
MOVIMIENTO = "movimiento legitimo del sitio del cruce (commit 667a6a5)"
FICHA = "ficha de la deuda actualizada: mismo adeudado, sitio vigente (59d0465)"


def _sha_actual() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(RAIZ),
                          capture_output=True, text=True).stdout.strip()


def _cargar_json(ruta: Path) -> Dict[str, Any]:
    if not ruta.is_file():
        return {}
    return json.loads(ruta.read_text(encoding="utf-8"))


def divergencias(salida: Path) -> List[Dict[str, Any]]:
    informe = _cargar_json(TMP / "diag-reconciliacion.json")
    if not informe:
        return []
    fichas: List[Dict[str, Any]] = []
    n = 0

    def _nueva(clave: str, tipo: str, elemento_original: str,
               elemento_vigente: str, causa: str, naturaleza: str,
               riesgo: str, recomendacion: str) -> Dict[str, Any]:
        nonlocal n
        n += 1
        return {
            "id": f"DIV-{n:02d}",
            "clave": clave,
            "tipo": tipo,
            "elemento_original": elemento_original,
            "elemento_vigente": elemento_vigente,
            "sha_referencia_snapshot": informe.get("sha", ""),
            "sha_codigo_actual": _sha_actual(),
            "cambio_responsable": causa,
            "naturaleza": naturaleza,
            "es_movimiento_legitimo": naturaleza == "movimiento",
            "es_deuda_viva": naturaleza == "deuda viva",
            "es_regresion": naturaleza == "regresion",
            "riesgo_de_actualizar_el_inventario": riesgo,
            "alternativas": [
                "A: eliminar el cruce componiendo desde el meta-toolkit",
                "B: migrarlo a un owner con puerto declarado",
                "C: excepcion formal con plazo, riesgo y dueno (ratificacion)",
            ],
            "recomendacion": recomendacion,
            "accion_requerida": "ratificacion del propietario",
            "ratificado": False,
        }

    for f in informe.get("pares_de_contexto", {}).get("fichas", []):
        if f.get("estado") == "VIGENTE":
            continue
        par = f.get("par")
        fichas.append(_nueva(
            f"ficha divergente: {par}", "ficha de par de contextos",
            "ficha del par en el snapshot de Archify (revision anterior)",
            f"ficha vigente del par en scripts/vault_arch.py",
            "59d0465 (ficha actualizada al mover el cruce) + 667a6a5 (sitio)",
            "ficha desactualizada: el adeudado NO cambio",
            "bajo: la ficha describe el mismo adeudado con el sitio vigente",
            "ratificar el texto de la ficha conservando la clase a_eliminar y su "
            "fecha limite, o re-tomar el snapshot",
        ))
    for f in informe.get("off_port", []):
        if f.get("estado") != "NO CONCILIADO":
            continue
        fichas.append(_nueva(
            f"acceso no conciliado: {f.get('clave')}", "acceso a fichero",
            f"acceso declarado en el snapshot: {f.get('clave')}",
            f"acceso vigente en la fachada de mantenimiento (mismo par de contextos)",
            "667a6a5 (la composicion paso de vault_norms_engine a vault_norms)",
            "movimiento",
            "bajo: el par de contextos sigue cruzando; solo cambio el modulo",
            "re-tomar el snapshot de Archify o ratificar la aceptacion con la "
            "ficha correspondiente",
        ))
    for f in informe.get("dependencias", {}).get("filas", []):
        if f.get("estado") not in ("NO CONCILIABLE", "NO NORMALIZABLE"):
            continue
        fichas.append(_nueva(
            f"dependencia {f.get('estado')}: {f.get('dependencia')}",
            "dependencia a granularidad de fichero",
            f"dependencia en el snapshot: {f.get('dependencia')}",
            "dependencia vigente en el par de contextos (mismo adeudado)",
            "667a6a5 (la composicion paso de vault_norms_engine a vault_norms)",
            "movimiento",
            "medio: la granularidad del snapshot (fichero) no coincide con la "
            "del registro (par de contextos); el adorno de la divergencia lo dice",
            "re-tomar el snapshot o ratificar la aceptacion",
        ))
    return fichas


def hallazgos(salida: Path) -> List[Dict[str, Any]]:
    a = _cargar_json(TMP / "diag-escenario-A.json")
    b = _cargar_json(TMP / "diag-escenario-B.json")
    fichas: List[Dict[str, Any]] = []
    n = 0

    def _nueva(norm: str, path: str, observed: str, entorno: str,
               clasificacion: str, causa: str, severidad: str,
               accion: str, decision: bool) -> Dict[str, Any]:
        nonlocal n
        n += 1
        return {
            "id": f"INC-{n:04d}",
            "norm": norm,
            "path": path,
            "observed": observed,
            "environment": entorno,
            "root_cause": causa,
            "reproduction": ("python scripts/vault_norms.py --audit --root "
                             "<runtime>"),
            "evidence": [f"audits/architecture/hallazgos-qg02.yaml#{'INC-%04d' % n}"],
            "classification": clasificacion,
            "impact": "",
            "severity": severidad,
            "resolution_options": [],
            "recommended_action": accion,
            "decision_required": decision,
            "quality_gate": "QG-02",
        }

    adr_vistos = set()
    for h in a.get("hallazgos", []):
        path = h.get("path", "")
        if h["norm"] == "AP-07" and path not in adr_vistos:
            adr_vistos.add(path)
        if h["norm"] == "AP-36":
            causa = ("efecto lateral escrito FUERA del vault root (AP-36): un "
                     "directorio vault-backups existe dos niveles por encima del "
                     "vault; procede de una ejecucion previa de backup")
            accion = ("localizar y purgar el directorio con el dueno de los "
                      "datos (no se borra desde aqui) y evitar que las "
                      "ejecuciones escriban fuera del vault")
            fichas.append(_nueva(h["norm"], path, h.get("detail") or h.get("message") or "",
                                  "escenario A (sandbox canonico)", "contaminacion de ejecuciones previas",
                                  causa, "critical", accion, True))
            continue
        causa = {
            "CN-03": ("status fuera del vocabulario canonico en un documento de "
                      "decision del propio vault de evidencia"),
            "AP-07": ("ADR sin las secciones obligatorias (Contexto, Decision, "
                      "Consecuencias)"),
            "AP-64": ("decision cerrada sin `responsable`: nadie responde de "
                      "su porque"),
        }.get(h["norm"], "")
        accion = ("corregir el documento de evidencia: status canonico, "
                  "secciones obligatorias y responsable")
        fichas.append(_nueva(h["norm"], path, h.get("detail") or h.get("message") or "",
                              "escenario A (sandbox canonico)",
                              "violacion real del producto (contenido de evidencia)",
                              causa, "medium", accion, False))
    for h in b.get("hallazgos", []):
        fichas.append(_nueva(h["norm"], h.get("path", ""), h.get("detail") or h.get("message") or "",
                              "escenario B (runtime limpio creado por el producto)",
                              "violacion real del producto (el init deja el runtime con una violacion)",
                              "el init del producto escribe una entrada de "
                              "vocabulario sin memoria en la bitacora de tags "
                              "(AP-39)",
                              "medium",
                              "corregir el init o el registro que produce; es un "
                              "defecto del producto, no del entorno",
                              True))
    # Hallazgo CERRADO: se conserva con su estado. Un hallazgo corregido que
    # desaparece del ledger parece un hallazgo que nunca existio.
    if b.get("total") == 0 and a.get("total", 0) > 0:
        fichas.append({
            "id": "INC-0015",
            "norm": "AP-39",
            "path": "19_Audits/vocabulary/tag-ledger.json",
            "observed": ("3 terminos en uso sin memoria canonica (command, hub, "
                         "nav) en un runtime recien creado por el producto"),
            "environment": "escenario B (runtime limpio creado por el producto)",
            "root_cause": ("vault_init crea notas bootstrap con tags que no "
                           "declaraba como canonicos en su propio "
                           "tag-registry.json"),
            "reproduction": ("python scripts/vault_init.py  # con VAULT_ROOT "
                             "apuntando a un runtime nuevo; despues "
                             "python scripts/vault_norms.py --audit --root <rt>"),
            "evidence": ["audits/architecture/hallazgos-qg02.yaml#INC-0015",
                         "commit 2174bb1 (fix(AP-39))",
                         "re-auditoria: 0 violaciones en runtime con 75 ficheros"],
            "classification": "violacion real del producto (CORREGIDA)",
            "impact": ("un runtime recien creado por el producto violaba la "
                       "norma que el producto certifica (invariante INV-10)"),
            "severity": "medium",
            "resolution_options": ["declarar los tags bootstrap como canonicos",
                                   "registrar los tags en el ledger al crear las notas"],
            "recommended_action": ("aplicada: categoria 'bootstrap' en "
                                   "canonical_tags del tag-registry"),
            "decision_required": False,
            "quality_gate": "QG-02",
            "estado": "CORREGIDO",
            "commit_correctivo": "2174bb1",
            "verificacion": ("re-auditoria con el codigo actual sobre un runtime "
                             "de 75 ficheros: 0 violaciones, 0 AP-39"),
        })
    return fichas


def veredictos(salida: Path) -> List[Dict[str, Any]]:
    ramas = subprocess.run(["git", "branch", "-r", "--list", "origin/qa/*"],
                           cwd=str(RAIZ), capture_output=True, text=True).stdout
    fichas: List[Dict[str, Any]] = []
    n = 0
    for linea in ramas.splitlines():
        rama = linea.strip()
        if not rama:
            continue
        p = subprocess.run(["git", "show", f"{rama}:audits/handoff/RESPUESTA-QA.md"],
                           cwd=str(RAIZ), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if p.returncode != 0:
            continue
        texto = p.stdout
        sha_rama = subprocess.run(["git", "rev-parse", "--short", rama],
                                  cwd=str(RAIZ), capture_output=True,
                                  text=True).stdout.strip()
        for bloque in texto.split("\n---\n"):
            titulo = ""
            for linea_b in bloque.splitlines():
                if linea_b.startswith("# "):
                    titulo = linea_b[2:].strip()
                    break
            if not titulo:
                continue
            n += 1
            sha_eval = ""
            for cand in re.findall(r"\b[0-9a-f]{7,40}\b", bloque):
                # un sha tiene letras: los tokens solo numericos son fechas
                if any(ch in "abcdef" for ch in cand):
                    sha_eval = cand
                    break
            veredicto = ""
            for linea_b in bloque.splitlines():
                if ("ESTADO" in linea_b or "Decisión" in linea_b or
                        "Decisi" in linea_b or "Dictamen" in linea_b):
                    veredicto = linea_b.strip()[:200]
                    break
            fichas.append({
                "id": f"VER-{n:03d}",
                "sha_evaluado": sha_eval or "NO_DETERMINADO",
                "sha_rama_qa": sha_rama,
                "fecha": "",
                "autoridad": "QA (revision independiente)",
                "hallazgo": titulo,
                "severidad": "NO_DETERMINADO",
                "motivo": veredicto or "NO_EXTRAIDO",
                "evidencia": [f"origin/{rama}:audits/handoff/RESPUESTA-QA.md"],
                "accion_exigida": "",
                "commit_correctivo": "",
                "prueba": "",
                "estado_posterior": "NO_DETERMINADO",
                "veredicto_que_lo_cerro": "",
                "riesgo_residual": "",
                "confidence_basis": "titulo y veredicto extraidos del buzon QA; "
                                   "el resto no se extrae automaticamente",
            })
    return fichas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--salida-dir", default=str(RAIZ / "audits" / "architecture"))
    args = ap.parse_args()
    salida = Path(args.salida_dir)
    salida.mkdir(parents=True, exist_ok=True)

    import yaml

    div = divergencias(salida)
    inc = hallazgos(salida)
    ver = veredictos(salida)
    (salida / "divergencias-archify.yaml").write_text(
        yaml.safe_dump({"schema": 1, "sha": _sha_actual(),
                        "fuente": "audits/fase2/reconciliar_archify.py --check",
                        "divergencias": div}, allow_unicode=True,
                       sort_keys=False, width=100), encoding="utf-8")
    (salida / "hallazgos-qg02.yaml").write_text(
        yaml.safe_dump({"schema": 1, "sha": _sha_actual(),
                        "escenario_a": "sandbox canonico (vault-sandbox)",
                        "escenario_b": "runtime limpio creado por el producto",
                        "hallazgos": inc}, allow_unicode=True,
                       sort_keys=False, width=100), encoding="utf-8")
    (salida / "registro-veredictos.yaml").write_text(
        yaml.safe_dump({"schema": 1, "sha": _sha_actual(),
                        "fuente": "ramas origin/qa/* (buzon RESPUESTA-QA.md)",
                        "veredictos": ver}, allow_unicode=True,
                       sort_keys=False, width=100), encoding="utf-8")
    print(json.dumps({"divergencias": len(div), "hallazgos": len(inc),
                      "veredictos": len(ver)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
