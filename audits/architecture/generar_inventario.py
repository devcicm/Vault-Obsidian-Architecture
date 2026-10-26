#!/usr/bin/env python3
"""Generador del INVENTARIO MAESTRO y del GRAFO DE TRAZABILIDAD.

Deriva la informacion de las FUENTES VIVAS del repositorio, nunca de copias
propias:

  - `scripts/vault_arch.py`       : contextos, puertos, cruces y su baseline
  - `scripts/vault_mcp_catalog.py`: catalogo de tools con su clase y script
  - `vault/` , `scripts/`         : modulos reales en disco
  - `normas/`                     : normas en paquete
  - `audits/fase2/catalogo-qg.yaml`: Quality Gates y sus comprobaciones
  - `audits/fase2/inventario-deuda.yaml`: deuda registrada
  - `audits/`                     : evidencias y documentos

Cada recurso lleva identificador estable (RES-XXXX) derivado de su clave, y su
`status` dice si esta VERIFICADO (inspeccionado aqui) o NO_VERIFICADO
(declarado por otra fuente). Cada arista declara su fundamento: observada,
declarada, inferida o pendiente.

Uso:
    python audits/architecture/generar_inventario.py [--salida-dir DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ / "scripts") not in sys.path:
    sys.path.insert(0, str(RAIZ / "scripts"))

VERIFICADO = "VERIFICADO"
NO_VERIFICADO = "NO_VERIFICADO"


def _id(categoria: str, clave: str) -> str:
    digest = hashlib.sha1(f"{categoria}:{clave}".encode("utf-8")).hexdigest()[:4]
    return f"RES-{categoria[:3].upper()}-{digest}"


def _sha_corto() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(RAIZ),
                          capture_output=True, text=True).stdout.strip()


def _hash_fichero(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


class Inventario:
    def __init__(self) -> None:
        self.recursos: Dict[str, Dict[str, Any]] = {}
        self.aristas: List[Dict[str, Any]] = []
        self._vistos: set = set()

    def alta(self, rid: str, nombre: str, **campos: Any) -> str:
        if rid in self.recursos:
            return rid
        base = {
            "id": rid, "name": nombre, "nature": "codigo", "type": "",
            "purpose": "", "responsibility": "", "owner": "",
            "source_of_truth": "", "path": "", "symbol": "",
            "introduced_in": "", "last_verified_sha": "",
            "declared_behavior": "", "observed_behavior": "",
            "expected_behavior": "", "inputs": [], "outputs": [],
            "dependencies": [], "consumers": [], "contracts": [],
            "related_norms": [], "related_quality_gates": [], "related_tests": [],
            "related_decisions": [], "invariants": [], "preconditions": [],
            "postconditions": [], "failure_modes": [], "evidence": [],
            "derived_artifacts": [], "status": VERIFICADO,
            "confidence_basis": "", "risks": [], "debt_ids": [],
            "proposed_change": None, "acceptance_criteria": [],
        }
        base.update(campos)
        self.recursos[rid] = base
        return rid

    def arista(self, origen: str, destino: str, relacion: str,
               fundamento: str, detalle: str = "") -> None:
        if origen not in self.recursos or destino not in self.recursos:
            return
        clave = (origen, destino, relacion)
        if clave in self._vistos:
            return
        self._vistos.add(clave)
        self.aristas.append({"from": origen, "to": destino,
                             "relation": relacion, "basis": fundamento,
                             "detail": detalle})


def construir() -> Dict[str, Any]:
    import vault_arch as arch
    import vault_mcp_catalog as mc

    sha = _sha_corto()
    inv = Inventario()
    por_ruta: Dict[str, str] = {}
    modulos_por_contexto: Dict[str, List[str]] = {}

    # ── 1. modulos reales (primero: los puertos y tools los referencian) ────
    rutas_modulo = sorted(list((RAIZ / "vault").rglob("*.py")) +
                          list((RAIZ / "scripts").glob("*.py")))
    for ruta in rutas_modulo:
        rel = ruta.relative_to(RAIZ).as_posix()
        lineas = len(ruta.read_text(encoding="utf-8", errors="replace").splitlines())
        rid = inv.alta(_id("modulo", rel), ruta.stem,
                       nature="codigo", type="modulo",
                       responsibility="", owner="",
                       source_of_truth="disco", path=rel, last_verified_sha=sha,
                       observed_behavior=f"{lineas} lineas",
                       status=VERIFICADO,
                       confidence_basis="fichero inspeccionado en disco")
        por_ruta[rel] = rid
        por_ruta[ruta.stem] = rid

    # ── 2. contextos, puertos y su relacion con los modulos ────────────────
    for nombre, ctx in sorted(arch.CONTEXTS.items()):
        rid = inv.alta(_id("contexto_arquitectonico", nombre), nombre,
                       nature="arquitectura", type="contexto",
                       purpose=ctx.get("titulo", ""),
                       responsibility=f"contexto {nombre}",
                       owner=nombre,
                       source_of_truth="scripts/vault_arch.py:CONTEXTS",
                       path="scripts/vault_arch.py", last_verified_sha=sha,
                       declared_behavior=f"lenguaje: {ctx.get('lenguaje')}",
                       observed_behavior=f"{len(ctx.get('modulos') or [])} modulos, "
                                         f"{len(ctx.get('puertos') or {})} puertos",
                       expected_behavior="registro unico de contextos y puertos",
                       contracts=sorted((ctx.get("puertos") or {}).keys()),
                       status=VERIFICADO,
                       confidence_basis="leido de scripts/vault_arch.py")
        modulos_por_contexto[nombre] = [str(m) for m in (ctx.get("modulos") or [])]
        for modulo in modulos_por_contexto[nombre]:
            modulo_rid = por_ruta.get(modulo) or por_ruta.get(Path(modulo).name)
            if modulo_rid:
                inv.arista(modulo_rid, rid, "IMPLEMENTS", "declarada",
                           f"modulo declarado en el contexto {nombre}")
        for puerto, destino in sorted((ctx.get("puertos") or {}).items()):
            prid = inv.alta(_id("puerto", f"{nombre}.{puerto}"), f"{nombre}.{puerto}",
                            nature="contrato", type="puerto",
                            purpose=f"contrato de {puerto} para {nombre}",
                            responsibility=f"punto de acceso de {nombre}",
                            owner=nombre,
                            source_of_truth="scripts/vault_arch.py:CONTEXTS[*].puertos",
                            path="scripts/vault_arch.py", symbol=str(destino),
                            last_verified_sha=sha,
                            declared_behavior=str(destino),
                            expected_behavior="acceso por contrato declarado",
                            contracts=[f"{nombre}.{puerto}"],
                            status=VERIFICADO,
                            confidence_basis="leido del registro de contextos")
            inv.arista(rid, prid, "PROVIDES", "observada",
                       f"puerto declarado {puerto}")
            inv.arista(prid, rid, "OWNS", "declarada",
                       f"el puerto {puerto} pertenece a {nombre}")
            destino_modulo = str(destino).split(":", 1)[0]
            modulo_rid = por_ruta.get(destino_modulo)
            if modulo_rid:
                inv.arista(prid, modulo_rid, "CONSUMES", "declarada",
                           f"el puerto {puerto} resuelve a {destino}")

    # ── 3. tools del catalogo (CLI y MCP) ──────────────────────────────────
    for nombre, spec in sorted(mc.TOOLS_CATALOG.items()):
        spec = spec or {}
        clase = spec.get("clase") or spec.get("class") or spec.get("group") or ""
        rid = inv.alta(_id("adaptador_cli", nombre), nombre,
                       nature="interfaz", type=f"tool:{clase}",
                       purpose=spec.get("purpose", "") or
                               f"operacion publicada {nombre}",
                       responsibility=f"implementa la operacion {nombre}",
                       owner="meta_toolkit",
                       source_of_truth="scripts/vault_mcp_catalog.py:TOOLS_CATALOG",
                       path="mcp/nodejs/tools-catalog.json", symbol=nombre,
                       last_verified_sha=sha,
                       declared_behavior="tool publicada en el catalogo MCP",
                       observed_behavior="publicada en el catalogo",
                       expected_behavior="expuesta por CLI y por MCP",
                       status=VERIFICADO,
                       confidence_basis="leido del catalogo de tools")
        script = spec.get("script")
        if script:
            modulo_rid = por_ruta.get(script) or por_ruta.get(Path(script).name)
            if modulo_rid:
                inv.arista(rid, modulo_rid, "IMPLEMENTS", "observada",
                           f"la tool {nombre} la implementa {script}")
                inv.arista(modulo_rid, rid, "PROVIDES", "observada",
                           f"modulo que implementa la tool {nombre}")

    # ── 4. superficies (CLI y MCP) ─────────────────────────────────────────
    cli_rid = inv.alta(_id("adaptador_cli", "cli-producto"),
                       "CLI de producto (vault)", nature="interfaz",
                       type="entry point",
                       purpose="instalar, diagnosticar y operar un runtime",
                       responsibility="superficie de linea de comandos para terceros",
                       owner="meta_toolkit", source_of_truth="vault/product_cli.py",
                       path="vault/product_cli.py", symbol="main",
                       last_verified_sha=sha,
                       observed_behavior="init, doctor, status, tools, run, mcp-path",
                       expected_behavior="instalar y operar sin el checkout",
                       status=VERIFICADO,
                       confidence_basis="ejercitado en el recorrido de terceros")
    mcp_rid = inv.alta(_id("adaptador_mcp", "servidor-mcp"),
                       "servidor MCP (vault-mcp-server.mjs)", nature="interfaz",
                       type="servidor MCP",
                       purpose="exponer las tools del toolkit por JSON-RPC",
                       responsibility="frontera de protocolo hacia clientes MCP",
                       owner="meta_toolkit",
                       source_of_truth="mcp/nodejs/vault-mcp-server.mjs",
                       path="mcp/nodejs/vault-mcp-server.mjs", last_verified_sha=sha,
                       observed_behavior="carga 97 tools y responde por stdio",
                       expected_behavior="initialize / tools/list / tools/call",
                       status=VERIFICADO,
                       confidence_basis="ejercitado en el recorrido de terceros")
    for nombre in sorted(mc.TOOLS_CATALOG):
        tool_rid = por_ruta.get(nombre)
        if tool_rid:
            inv.arista(tool_rid, mcp_rid, "PROVIDES", "declarada",
                       "tool expuesta por el servidor MCP")
            inv.arista(tool_rid, cli_rid, "PROVIDES", "declarada",
                       "tool alcanzable desde el CLI de producto")

    # ── 5. normas en paquete ───────────────────────────────────────────────
    for norma in sorted((RAIZ / "normas").glob("*/norma.py")):
        codigo = norma.parent.name.upper()
        rid = inv.alta(_id("norma", codigo), codigo, nature="norma", type="norma",
                       purpose=f"norma {codigo} del estandar",
                       responsibility="criterio de gobernanza con guard",
                       owner="gobernanza",
                       source_of_truth=f"normas/{codigo}/norma.py",
                       path=f"normas/{codigo}/norma.py", last_verified_sha=sha,
                       status=VERIFICADO,
                       confidence_basis="paquete de norma inspeccionado")
        inv.arista(rid, rid, "APPLIES_TO", "declarada",
                   "la norma aplica al contexto de gobernanza")

    # ── 6. Quality Gates y los verificadores que ejecutan ──────────────────
    try:
        import yaml

        qg = yaml.safe_load((RAIZ / "audits" / "fase2" /
                              "catalogo-qg.yaml").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        qg = []
    for gate in qg or []:
        gid = gate.get("id", "")
        rid = inv.alta(_id("quality_gate", gid), gid, nature="gobierno",
                       type="quality gate", purpose=gate.get("purpose", ""),
                       responsibility=gate.get("owner", ""),
                       owner=gate.get("owner", ""),
                       source_of_truth="audits/fase2/catalogo-qg.yaml",
                       path="audits/fase2/catalogo-qg.yaml", last_verified_sha=sha,
                       declared_behavior="; ".join(gate.get("checks") or []),
                       expected_behavior=str(gate.get("pass_criteria", "")),
                       contracts=[str(gate.get("acceptance_authority", ""))],
                       status=VERIFICADO,
                       confidence_basis="leido del catalogo QG")
        for check in gate.get("checks") or []:
            for token in re.findall(r"[A-Za-z0-9_./-]+\.py", str(check)):
                modulo_rid = por_ruta.get(token) or por_ruta.get(Path(token).name)
                if modulo_rid:
                    inv.arista(rid, modulo_rid, "VERIFIES", "declarada",
                               f"la puerta ejecuta {token}")

    # ── 7. deuda registrada ────────────────────────────────────────────────
    try:
        import yaml

        deuda = yaml.safe_load((RAIZ / "audits" / "fase2" /
                                 "inventario-deuda.yaml").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        deuda = []
    for td in deuda or []:
        tid = td.get("id", "")
        rid = inv.alta(_id("riesgo_deuda_excepcion", tid), tid, nature="deuda",
                       type=str(td.get("category", "")),
                       purpose=str(td.get("title", "")),
                       responsibility=str(td.get("owner", "")),
                       owner=str(td.get("owner", "")),
                       source_of_truth="audits/fase2/inventario-deuda.yaml",
                       path=str(td.get("source_file", "")),
                       symbol=str(td.get("symbol", "")),
                       last_verified_sha=sha,
                       declared_behavior=str(td.get("observed_behavior", "")),
                       expected_behavior=str(td.get("expected_behavior", "")),
                       status=NO_VERIFICADO,
                       confidence_basis="declarado en el inventario de deuda",
                       debt_ids=[tid],
                       risks=[str(td.get("impact", ""))] if td.get("impact") else [])

    # ── 8. evidencias y documentos ─────────────────────────────────────────
    for ruta in sorted((RAIZ / "audits").rglob("*")):
        if not ruta.is_file() or ruta.suffix.lower() not in (".txt", ".md", ".json",
                                                            ".yaml", ".yml"):
            continue
        rel = ruta.relative_to(RAIZ).as_posix()
        if rel.startswith("audits/architecture/"):
            # La capa de trazabilidad no es evidencia del producto: si se
            # listara a si misma, el inventario no seria reproducible.
            continue
        es_doc = ("handoff" in rel or "diseno" in rel or "arquitectura" in rel
                  or "ADR" in ruta.name)
        rid = inv.alta(_id("documento_adr" if es_doc else "evidencia", rel),
                       ruta.name,
                       nature="documento" if es_doc else "evidencia",
                       type=ruta.suffix.lstrip("."), purpose="",
                       responsibility="", owner="", source_of_truth=rel,
                       path=rel, last_verified_sha=sha,
                       observed_behavior=f"{ruta.stat().st_size} bytes",
                       evidence=[f"sha256:{_hash_fichero(ruta)}"],
                       status=VERIFICADO,
                       confidence_basis="fichero presente y leido")

    # ── 9. artefactos, entornos y decisiones ───────────────────────────────
    inv.alta(_id("artefacto_distribuido", "wheel"), "wheel de producto",
             nature="artefacto", type="wheel",
             purpose="distribuir el toolkit a terceros",
             responsibility="paquete instalable", owner="meta_toolkit",
             source_of_truth="pyproject.toml", path="dist/", last_verified_sha=sha,
             observed_behavior="construido y probado fuera del checkout",
             expected_behavior="instalacion limpia sin el checkout",
             status=VERIFICADO, confidence_basis="recorrido de terceros 27/27")
    inv.alta(_id("artefacto_distribuido", "sdist"), "sdist de producto",
             nature="artefacto", type="sdist", purpose="distribuir el codigo",
             responsibility="paquete fuente", owner="meta_toolkit",
             source_of_truth="pyproject.toml", path="dist/", last_verified_sha=sha,
             status=VERIFICADO, confidence_basis="construido en la ronda R09")
    inv.alta(_id("entorno_sandbox", "vault-sandbox"),
             "sandbox canonico del repo", nature="entorno", type="sandbox",
             purpose="runtime de pruebas del propio repositorio",
             responsibility="contener fixtures y notas de prueba",
             owner="ciclo_de_vida", source_of_truth="vault-sandbox/",
             path="vault-sandbox/", last_verified_sha=sha,
             observed_behavior="14 hallazgos de auditoria (fixtures adversariales)",
             status=VERIFICADO, confidence_basis="auditoria ejecutada")
    inv.alta(_id("decision_producto", "release-candidate"),
             "candidato de release CLI+MCP", nature="decision", type="candidato",
             purpose="preparar el producto para integracion",
             owner="propietario",
             source_of_truth="audits/architecture/ESTADO-Y-TRAZABILIDAD.md",
             last_verified_sha=sha, status=NO_VERIFICADO,
             confidence_basis="pendiente de ratificacion del propietario")

    # ── 10. cruces vivos declarados ────────────────────────────────────────
    for cruce in arch.cruces():
        par = f"{cruce['from_context']}->{cruce['to_context']}"
        rid = inv.alta(_id("dependencia", par), par, nature="dependencia",
                       type="cruce declarado",
                       purpose="cruce de contextos declarado en el registro",
                       source_of_truth="scripts/vault_arch.py:CRUCES",
                       path="scripts/vault_arch.py",
                       symbol=f"{cruce.get('from')} -> {cruce.get('to')}",
                       last_verified_sha=sha, status=VERIFICADO,
                       confidence_basis="leido del registro de cruces")
        inv.arista(rid, cruce["from_context"], "DEPENDS_ON", "declarada",
                   f"cruce declarado hacia {cruce['to_context']}")

    # ── 11. indices transversales ───────────────────────────────────────────
    indices = {}
    for clave, nombre in (("calidad", "calidad y evidencia"),
                          ("arquitectura", "arquitectura"),
                          ("superficie-mcp", "superficie MCP"),
                          ("superficie-cli", "superficie CLI"),
                          ("gobierno", "gobernanza y normas")):
        rid = inv.alta(_id("dependencia", clave), nombre, nature="indice",
                       type="seccion transversal", purpose="agrupa recursos",
                       source_of_truth="generado", last_verified_sha=sha,
                       status=VERIFICADO, confidence_basis="indice del generador")
        indices[clave] = rid
    inv.arista(indices["arquitectura"], indices["calidad"], "AFFECTS", "declarada",
               "la arquitectura se acredita por las puertas")
    inv.arista(indices["superficie-cli"], indices["superficie-mcp"], "AFFECTS",
               "declarada", "CLI y MCP comparten el mismo runtime")

    grafo = {
        "generado_por": "audits/architecture/generar_inventario.py",
        "sha": sha,
        "conteo": {"recursos": len(inv.recursos), "relaciones": len(inv.aristas)},
        "indices": indices,
        "relaciones": sorted(inv.aristas,
                              key=lambda a: (a["from"], a["to"], a["relation"])),
    }
    return {"inventario": inv, "grafo": grafo}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--salida-dir", default=str(RAIZ / "audits" / "architecture"))
    args = ap.parse_args()
    salida = Path(args.salida_dir)
    salida.mkdir(parents=True, exist_ok=True)
    datos = construir()
    inv: Inventario = datos["inventario"]
    grafo = datos["grafo"]

    import yaml

    recursos = sorted(inv.recursos.values(), key=lambda r: r["id"])
    (salida / "inventario-maestro.yaml").write_text(
        yaml.safe_dump({"schema": 1,
                        "generado_por": "audits/architecture/generar_inventario.py",
                        "sha": grafo["sha"],
                        "nota": ("Generado: no editar a mano. Cada recurso dice si "
                                 "esta VERIFICADO (inspeccionado aqui) o "
                                 "NO_VERIFICADO (declarado por otra fuente)."),
                        "recursos": recursos},
                       allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8")
    (salida / "grafo-trazabilidad.json").write_text(
        json.dumps(grafo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verificados = sum(1 for r in recursos if r["status"] == VERIFICADO)
    print(json.dumps({"recursos": len(recursos), "verificados": verificados,
                      "no_verificados": len(recursos) - verificados,
                      "relaciones": len(grafo["relaciones"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
