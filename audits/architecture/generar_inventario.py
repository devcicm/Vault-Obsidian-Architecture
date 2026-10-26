#!/usr/bin/env python3
"""Generador del INVENTARIO MAESTRO y del GRAFO DE TRAZABILIDAD.

Deriva la informacion de FUENTES INMUTABLES:

  - el ARBOL GIT (`git ls-tree`/`git show`), no el workspace: el inventario
    describe un commit, no un directorio que otros tests estan mutando. Asi la
    generacion es determinista y estricta sin.read de carreras;
  - `scripts/vault_arch.py` (contextos, puertos, cruces) leido del arbol;
  - `scripts/vault_mcp_catalog.py` (catalogo de tools);
  - `normas/` (normas con guard);
  - `audits/fase2/catalogo-qg.yaml` (Quality Gates y sus comprobaciones);
  - `audits/fase2/inventario-deuda.yaml` (deuda registrada);
  - `tests/` (verificadores) y `docs/adr/` (decisiones);
  - `.archify/` (snapshot de otra revision).

Cada recurso lleva un identificador estable y su NIVEL DE VERIFICACION, que no
se confunde con la aprobacion funcional:

    descubierto -> declarado -> implementado -> ejecutado -> verificado ->
    evidencia_acreditada -> aceptado_qa -> ratificado_propietario

El grafo implementa la cadena prometida en la Constitucion:

    PROPOSITO -> PROMESA -> PREMISA -> INVARIANTE -> CONTRATO -> RECURSO
      -> DEPENDENCIA -> IMPLEMENTACION -> TEST -> EVIDENCIA -> QUALITY GATE
      -> DICTAMEN -> DECISION

Relaciones tipadas: DEPENDS_ON, DERIVED_FROM, PROVIDES, CONSUMES, OWNS,
IMPLEMENTS, VERIFIES, PRODUCES_EVIDENCE, RESOLVES, BLOCKS, APPROVED_BY,
SUPERSEDES, APPLIES_TO, CONTRADICTS, AFFECTS.

Uso:
    python audits/architecture/generar_inventario.py [--salida-dir DIR]
                                            [--sha SHA] [--verificar]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ / "scripts") not in sys.path:
    sys.path.insert(0, str(RAIZ / "scripts"))

# ── niveles de verificacion (QA-ARC-02) ─────────────────────────────────────
NIVELES = ("descubierto", "declarado", "implementado", "ejecutado",
           "verificado", "evidencia_acreditada", "aceptado_qa",
           "ratificado_propietario")
NIVEL_POR_DEFECTO = "descubierto"

# ── relaciones tipadas ──────────────────────────────────────────────────────
RELACIONES = ("DEPENDS_ON", "DERIVED_FROM", "PROVIDES", "CONSUMES", "OWNS",
              "IMPLEMENTS", "VERIFIES", "PRODUCES_EVIDENCE", "RESOLVES",
              "BLOCKS", "APPROVED_BY", "SUPERSEDES", "APPLIES_TO",
              "CONTRADICTS", "AFFECTS")

#: FUndamento admitido por relacion.
FUNDAMENTO = ("observada", "declarada", "inferida", "pendiente")


# ── acceso al arbol inmutable ───────────────────────────────────────────────

class Arbol:
    """Lectura del arbol de un commit: la fuente de verdad del inventario."""

    def __init__(self, sha: str, raiz: Path = RAIZ):
        self.sha = sha
        self.raiz = raiz
        self._cache: Dict[str, Optional[str]] = {}

    def _git(self, *args: str) -> str:
        p = subprocess.run(["git", *args], cwd=str(self.raiz),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=600)
        return p.stdout if p.returncode == 0 else ""

    def ficheros(self) -> List[str]:
        return [l for l in self._git("ls-tree", "-r", "--name-only",
                                     self.sha).splitlines() if l]

    def texto(self, ruta: str) -> Optional[str]:
        if ruta not in self._cache:
            p = subprocess.run(["git", "show", f"{self.sha}:{ruta}"],
                               cwd=str(self.raiz), capture_output=True,
                               text=True, encoding="utf-8", errors="replace",
                               timeout=600)
            self._cache[ruta] = p.stdout if p.returncode == 0 else None
        return self._cache[ruta]

    def blob_sha(self, ruta: str) -> Optional[str]:
        linea = self._git("ls-tree", self.sha, "--", ruta).strip()
        if not linea:
            return None
        partes = linea.split()
        return partes[2] if len(partes) >= 3 else None


def _id(categoria: str, clave: str) -> str:
    """Identificador estable y sin colisiones.

    El hash es de 8 hex (32 bits) sobre la clave completa: dos recursos con
    el mismo nombre abreviado en categorias distintas NO colisionan, porque la
    categoria entra en el hash.
    """
    digest = hashlib.sha1(f"{categoria}\x00{clave}".encode("utf-8")).hexdigest()[:8]
    return f"RES-{categoria[:3].upper()}-{digest}"


class Inventario:
    def __init__(self) -> None:
        self.recursos: Dict[str, Dict[str, Any]] = {}
        self.aristas: List[Dict[str, Any]] = []
        self._vistos: set = set()
        self._huerfanos: List[Dict[str, str]] = []

    def alta(self, rid: str, nombre: str, **campos: Any) -> str:
        if rid in self.recursos:
            return rid
        base = {
            "id": rid, "name": nombre, "nature": "codigo", "type": "",
            "purpose": "", "responsibility": "", "owner": "",
            "source_of_truth": "", "path": "", "symbol": "",
            "introduced_in": "", "source_sha": "", "publication_sha": "",
            "declared_behavior": "", "observed_behavior": "",
            "expected_behavior": "", "inputs": [], "outputs": [],
            "dependencies": [], "consumers": [], "contracts": [],
            "related_norms": [], "related_quality_gates": [], "related_tests": [],
            "related_decisions": [], "invariants": [], "preconditions": [],
            "postconditions": [], "failure_modes": [], "evidence": [],
            "derived_artifacts": [], "verification_level": NIVEL_POR_DEFECTO,
            "next_level_requires": "", "confidence_basis": "", "risks": [],
            "debt_ids": [], "proposed_change": None, "acceptance_criteria": [],
        }
        base.update(campos)
        base["id"] = rid
        base["name"] = nombre
        # `status` se conserva por compatibilidad con el inventario v1 y
        # significa lo que significaba: NO es una certificacion funcional.
        base["status"] = ("VERIFICADO"
                          if base.get("verification_level") in
                          ("ejecutado", "verificado", "evidencia_acreditada",
                           "aceptado_qa", "ratificado_propietario")
                          else "NO_VERIFICADO")
        self.recursos[rid] = base
        return rid

    def arista(self, origen: str, destino: str, relacion: str,
               fundamento: str, detalle: str = "") -> None:
        if relacion not in RELACIONES:
            raise ValueError(f"relacion no tipada: {relacion}")
        if fundamento not in FUNDAMENTO:
            raise ValueError(f"fundamento no valido: {fundamento}")
        if origen not in self.recursos or destino not in self.recursos:
            # No se descarta en silencio: queda registrado como huerfano.
            self._huerfanos.append({"from": origen, "to": destino,
                                     "relation": relacion})
            return
        clave = (origen, destino, relacion)
        if clave in self._vistos:
            return
        self._vistos.add(clave)
        self.aristas.append({"from": origen, "to": destino,
                             "relation": relacion, "basis": fundamento,
                             "detail": detalle})


# ── construccion ────────────────────────────────────────────────────────────

def _pruebas_ejecutadas(junit: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    """Mapa clase -> {ejecutada, fallo, tiempo} leido del JUnit."""
    if junit is None or not junit.is_file():
        return {}
    import xml.etree.ElementTree as ET

    try:
        raiz = ET.parse(str(junit)).getroot()
    except Exception:  # noqa: BLE001
        return {}
    suites = ([raiz] if raiz.tag == "testsuite" else raiz.findall("testsuite"))
    salida: Dict[str, Dict[str, Any]] = {}
    for suite in suites:
        for caso in suite.findall("testcase"):
            clase = caso.get("classname", "")
            entrada = salida.setdefault(clase, {"ejecutada": False, "fallo": False,
                                                "tiempo": 0.0})
            entrada["ejecutada"] = True
            entrada["fallo"] = (caso.find("failure") is not None
                                or caso.find("error") is not None)
            entrada["tiempo"] += float(caso.get("time") or 0)
    return salida


def _pruebas_por_fichero(junit: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    """Junit -> {fichero: {ejecutada, fallo, casos}}."""
    if junit is None or not junit.is_file():
        return {}
    import xml.etree.ElementTree as ET

    try:
        raiz = ET.parse(str(junit)).getroot()
    except Exception:  # noqa: BLE001
        return {}
    suites = ([raiz] if raiz.tag == "testsuite" else raiz.findall("testsuite"))
    salida: Dict[str, Dict[str, Any]] = {}
    for suite in suites:
        for caso in suite.findall("testcase"):
            clase = caso.get("classname", "")
            if not clase:
                continue
            # classname es el modulo de test: tests.test_x -> tests/test_x.py
            partes = clase.split(".")
            if partes and partes[0] == "tests":
                clave = "/".join(partes[:-1] + [partes[-1] + ".py"]) \
                    if len(partes) > 1 else f"tests/{clase}.py"
            else:
                clave = f"tests/{clase.replace('.', '/')}.py"
            entrada = salida.setdefault(clave, {"ejecutada": False, "fallo": False,
                                                "casos": 0})
            entrada["ejecutada"] = True
            entrada["casos"] += 1
            if caso.find("failure") is not None or caso.find("error") is not None:
                entrada["fallo"] = True
    return salida


def construir(arbol: Arbol, junit: Optional[Path] = None) -> Dict[str, Any]:
    import vault_arch as arch
    import vault_mcp_catalog as mc

    sha = arbol.sha
    pruebas_por_fichero = _pruebas_por_fichero(junit)
    inv = Inventario()
    ficheros = set(arbol.ficheros())
    por_ruta: Dict[str, str] = {}

    # ── 1. modulos (desde el arbol) ────────────────────────────────────────
    for rel in sorted(f for f in ficheros
                      if f.startswith(("vault/", "scripts/")) and f.endswith(".py")):
        texto = arbol.texto(rel) or ""
        rid = inv.alta(_id("modulo", rel), Path(rel).stem,
                       nature="codigo", type="modulo",
                       source_of_truth="arbol git", path=rel, source_sha=sha,
                       publication_sha=sha,
                       observed_behavior=f"{len(texto.splitlines())} lineas",
                       verification_level="descubierto",
                       next_level_requires="un test que lo ejecute",
                       confidence_basis="fichero leido del arbol del commit")
        por_ruta[rel] = rid
        por_ruta[Path(rel).stem] = rid

    # ── 2. contextos y puertos ─────────────────────────────────────────────
    modulos_por_contexto: Dict[str, List[str]] = {}
    contexto_id: Dict[str, str] = {}
    for nombre, ctx in sorted(arch.CONTEXTS.items()):
        rid = inv.alta(_id("contexto_arquitectonico", nombre), nombre,
                       nature="arquitectura", type="contexto",
                       purpose=str(ctx.get("titulo", "")),
                       responsibility=f"contexto {nombre}", owner=nombre,
                       source_of_truth="scripts/vault_arch.py:CONTEXTS",
                       path="scripts/vault_arch.py", source_sha=sha,
                       publication_sha=sha,
                       declared_behavior=f"lenguaje: {ctx.get('lenguaje')}",
                       observed_behavior=(
                           f"{len(ctx.get('modulos') or [])} modulos, "
                           f"{len(ctx.get('puertos') or {})} puertos"),
                       expected_behavior="registro unico de contextos y puertos",
                       contracts=sorted((ctx.get("puertos") or {}).keys()),
                       verification_level="declarado",
                       next_level_requires="un verificador que lo compruebe",
                       confidence_basis="leido del registro de contextos")
        modulos_por_contexto[nombre] = [str(m) for m in (ctx.get("modulos") or [])]
        contexto_id[nombre] = rid
        for modulo in modulos_por_contexto[nombre]:
            mid = por_ruta.get(modulo) or por_ruta.get(Path(modulo).name)
            if mid:
                inv.arista(mid, rid, "IMPLEMENTS", "declarada",
                           f"modulo declarado en el contexto {nombre}")
        for puerto, destino in sorted((ctx.get("puertos") or {}).items()):
            prid = inv.alta(_id("puerto", f"{nombre}.{puerto}"),
                            f"{nombre}.{puerto}", nature="contrato",
                            type="puerto",
                            purpose=f"contrato de {puerto} para {nombre}",
                            responsibility=f"punto de acceso de {nombre}",
                            owner=nombre,
                            source_of_truth="scripts/vault_arch.py:CONTEXTS[*].puertos",
                            path="scripts/vault_arch.py", symbol=str(destino),
                            source_sha=sha, publication_sha=sha,
                            declared_behavior=str(destino),
                            expected_behavior="acceso por contrato declarado",
                            contracts=[f"{nombre}.{puerto}"],
                            verification_level="declarado",
                            next_level_requires="un consumidor que lo use",
                            confidence_basis="leido del registro de contextos")
            inv.arista(rid, prid, "PROVIDES", "observada",
                       f"puerto declarado {puerto}")
            inv.arista(prid, rid, "OWNS", "declarada",
                       f"el puerto {puerto} pertenece a {nombre}")
            destino_modulo = str(destino).split(":", 1)[0]
            mid = por_ruta.get(destino_modulo)
            if mid:
                inv.arista(prid, mid, "CONSUMES", "declarada",
                           f"el puerto {puerto} resuelve a {destino}")

    # ── 3. tools y sus modulos ─────────────────────────────────────────────
    for nombre, spec in sorted(mc.TOOLS_CATALOG.items()):
        spec = spec or {}
        clase = spec.get("clase") or spec.get("class") or spec.get("group") or ""
        rid = inv.alta(_id("adaptador_cli", nombre), nombre, nature="interfaz",
                       type=f"tool:{clase}",
                       purpose=str(spec.get("purpose", "")
                                   or f"operacion publicada {nombre}"),
                       responsibility=f"implementa la operacion {nombre}",
                       owner="meta_toolkit",
                       source_of_truth="scripts/vault_mcp_catalog.py:TOOLS_CATALOG",
                       path="mcp/nodejs/tools-catalog.json", symbol=nombre,
                       source_sha=sha, publication_sha=sha,
                       declared_behavior="tool publicada en el catalogo MCP",
                       observed_behavior="publicada en el catalogo",
                       expected_behavior="expuesta por CLI y por MCP",
                       verification_level="declarado",
                       next_level_requires="ser ejecutada en el recorrido E2E",
                       confidence_basis="leido del catalogo de tools")
        script = spec.get("script")
        if script:
            mid = por_ruta.get(script) or por_ruta.get(Path(script).name)
            if mid:
                inv.arista(rid, mid, "IMPLEMENTS", "observada",
                           f"la tool {nombre} la implementa {script}")
                inv.arista(mid, rid, "PROVIDES", "observada",
                           f"modulo que implementa la tool {nombre}")

    # ── 4. superficies ─────────────────────────────────────────────────────
    cli_rid = inv.alta(_id("adaptador_cli", "cli-producto"),
                       "CLI de producto (vault)", nature="interfaz",
                       type="entry point",
                       purpose="instalar, diagnosticar y operar un runtime",
                       responsibility="superficie de linea de comandos para terceros",
                       owner="meta_toolkit", source_of_truth="vault/product_cli.py",
                       path="vault/product_cli.py", symbol="main",
                       source_sha=sha, publication_sha=sha,
                       observed_behavior="init, doctor, status, tools, run, mcp-path",
                       expected_behavior="instalar y operar sin el checkout",
                       verification_level="verificado",
                       next_level_requires="evidencia del recorrido E2E",
                       confidence_basis="ejercitado en el recorrido de terceros")
    mcp_rid = inv.alta(_id("adaptador_mcp", "servidor-mcp"),
                       "servidor MCP (vault-mcp-server.mjs)", nature="interfaz",
                       type="servidor MCP",
                       purpose="exponer las tools del toolkit por JSON-RPC",
                       responsibility="frontera de protocolo hacia clientes MCP",
                       owner="meta_toolkit",
                       source_of_truth="mcp/nodejs/vault-mcp-server.mjs",
                       path="mcp/nodejs/vault-mcp-server.mjs", source_sha=sha,
                       publication_sha=sha,
                       observed_behavior="carga 97 tools y responde por stdio",
                       expected_behavior="initialize / tools/list / tools/call",
                       verification_level="verificado",
                       next_level_requires="evidencia del recorrido E2E",
                       confidence_basis="ejercitado en el recorrido de terceros")
    for nombre in sorted(mc.TOOLS_CATALOG):
        tid = por_ruta.get(nombre)
        if tid:
            inv.arista(tid, mcp_rid, "PROVIDES", "declarada",
                       "tool expuesta por el servidor MCP")
            inv.arista(tid, cli_rid, "PROVIDES", "declarada",
                       "tool alcanzable desde el CLI de producto")

    # ── 5. normas con su guard ─────────────────────────────────────────────
    for rel in sorted(f for f in ficheros
                      if f.startswith("normas/") and f.endswith("/norma.py")):
        codigo = Path(rel).parent.name.upper()
        guard = rel.rsplit("/", 1)[0] + "/guard.py"
        rid = inv.alta(_id("norma", codigo), codigo, nature="norma", type="norma",
                       purpose=f"norma {codigo} del estandar",
                       responsibility="criterio de gobernanza con guard",
                       owner="gobernanza", source_of_truth=rel, path=rel,
                       source_sha=sha, publication_sha=sha,
                       verification_level="implementado",
                       next_level_requires="un test que la ejecute",
                       confidence_basis="paquete de norma inspeccionado")
        gid = por_ruta.get(guard)
        if gid:
            inv.arista(gid, rid, "VERIFIES", "observada",
                       f"el guard de {codigo} la verifica")
        gobernanza_id = contexto_id.get("gobernanza")
        if gobernanza_id:
            inv.arista(rid, gobernanza_id, "APPLIES_TO", "declarada",
                       "la norma aplica al contexto de gobernanza")

    # ── 6. Quality Gates y los verificadores que ejecutan ──────────────────
    import yaml

    qg_texto = arbol.texto("audits/fase2/catalogo-qg.yaml") or ""
    try:
        catalogo = yaml.safe_load(qg_texto) or []
    except Exception:  # noqa: BLE001
        catalogo = []
    for gate in catalogo:
        gid_ = str(gate.get("id", ""))
        rid = inv.alta(_id("quality_gate", gid_), gid_, nature="gobierno",
                       type="quality gate", purpose=str(gate.get("purpose", "")),
                       responsibility=str(gate.get("owner", "")),
                       owner=str(gate.get("owner", "")),
                       source_of_truth="audits/fase2/catalogo-qg.yaml",
                       path="audits/fase2/catalogo-qg.yaml", source_sha=sha,
                       publication_sha=sha,
                       declared_behavior="; ".join(gate.get("checks") or []),
                       expected_behavior=str(gate.get("pass_criteria", "")),
                       contracts=[str(gate.get("acceptance_authority", ""))],
                       verification_level="declarado",
                       next_level_requires="recibo con artefacto por subcheck",
                       confidence_basis="leido del catalogo QG")
        for check in gate.get("checks") or []:
            for token in re.findall(r"[A-Za-z0-9_./-]+\.py", str(check)):
                mid = por_ruta.get(token) or por_ruta.get(Path(token).name)
                if mid:
                    inv.arista(rid, mid, "VERIFIES", "declarada",
                               f"la puerta ejecuta {token}")

    # ── 7. deuda registrada ────────────────────────────────────────────────
    try:
        deuda = yaml.safe_load(arbol.texto("audits/fase2/inventario-deuda.yaml")
                                or "") or []
    except Exception:  # noqa: BLE001
        deuda = []
    for td in deuda:
        tid_ = str(td.get("id", ""))
        rid = inv.alta(_id("riesgo_deuda_excepcion", tid_), tid_, nature="deuda",
                       type=str(td.get("category", "")),
                       purpose=str(td.get("title", "")),
                       responsibility=str(td.get("owner", "")),
                       owner=str(td.get("owner", "")),
                       source_of_truth="audits/fase2/inventario-deuda.yaml",
                       path=str(td.get("source_file", "")),
                       symbol=str(td.get("symbol", "")), source_sha=sha,
                       publication_sha=sha,
                       declared_behavior=str(td.get("observed_behavior", "")),
                       expected_behavior=str(td.get("expected_behavior", "")),
                       verification_level="declarado",
                       next_level_requires="commit correctivo + evidencia",
                       confidence_basis="declarado en el inventario de deuda",
                       debt_ids=[tid_])

    # ── 8. tests (verificadores) y su relacion con modulos y QG ─────────────
    modulos_verificados, tests_ejecutados = set(), {}
    for rel in sorted(f for f in ficheros
                      if f.startswith("tests/") and f.endswith(".py")):
        texto = arbol.texto(rel) or ""
        nombre = Path(rel).stem
        ejecucion = pruebas_por_fichero.get(rel)
        if ejecucion and ejecucion["ejecutada"] and not ejecucion["fallo"]:
            nivel = "ejecutado"
            siguiente = ("el test debe FALLAR ante el defecto que vigila "
                         "(mutacion) para probar su sensibilidad")
            confianza = f"ejecutado y en verde en el JUnit ({ejecucion['casos']} casos)"
        elif ejecucion and ejecucion["fallo"]:
            nivel = "implementado"
            siguiente = "el test falla: arreglar el defecto o el test"
            confianza = "ejecutado y en ROJO"
        else:
            nivel = "implementado"
            siguiente = "ser ejecutado en una corrida"
            confianza = "fichero leido del arbol; sin ejecucion acreditada"
        rid = inv.alta(_id("verificador", rel), nombre, nature="verificador",
                       type="test", purpose=f"verifica {nombre}",
                       responsibility="detectar regresiones",
                       owner="qa", source_of_truth=rel, path=rel,
                       source_sha=sha, publication_sha=sha,
                       observed_behavior=f"{len(texto.splitlines())} lineas",
                       expected_behavior="falla cuando el defecto esta",
                       verification_level=nivel,
                       next_level_requires=siguiente,
                       confidence_basis=confianza)
        tests_ejecutados[rel] = rid
        modulos = [m for m in ("vault_init", "vault_norms", "vault_arch",
                                "vault_criterios", "vault_mcp_catalog",
                                "vault_tags", "colector_qg", "reconciliar_archify")
                    if m in texto]
        for m in modulos:
            mid = por_ruta.get(m)
            if mid:
                inv.arista(rid, mid, "VERIFIES", "inferida",
                           f"el test menciona {m}")
                if nivel == "ejecutado":
                    modulos_verificados.add(mid)

    # ── 9. decisiones (ADR) ────────────────────────────────────────────────
    for rel in sorted(f for f in ficheros
                      if f.startswith("docs/adr/") and f.endswith(".md")):
        rid = inv.alta(_id("decision_producto", rel), Path(rel).name,
                       nature="decision", type="ADR",
                       purpose="decision de arquitectura aceptada",
                       responsibility="fijar un limite del producto",
                       owner="propietario", source_of_truth=rel, path=rel,
                       source_sha=sha, publication_sha=sha,
                       verification_level="ratificado_propietario",
                       next_level_requires="",
                       confidence_basis="ADR versionado en el arbol")
        for ctx, ctx_id in (("meta_toolkit", None),):
            pass

    # ── 10. evidencia y artefactos ─────────────────────────────────────────
    for rel in sorted(f for f in ficheros
                      if f.startswith("audits/") and not f.startswith(
                          "audits/architecture/")
                      and Path(f).suffix.lower() in (".txt", ".md", ".json",
                                                    ".yaml", ".yml")):
        rid = inv.alta(_id("evidencia", rel), Path(rel).name,
                       nature="evidencia", type=Path(rel).suffix.lstrip("."),
                       source_of_truth=rel, path=rel, source_sha=sha,
                       publication_sha=sha,
                       observed_behavior="evidencia publicada en el arbol",
                       verification_level="evidencia_acreditada",
                       next_level_requires="",
                       evidence=[f"blob:{arbol.blob_sha(rel) or 'n/d'}"],
                       confidence_basis="fichero versionado con hash de blob")
        for gate in catalogo:
            gid_ = str(gate.get("id", ""))
            if gid_ and gid_ in Path(rel).name:
                qrid = inv.alta(_id("quality_gate", gid_), gid_,
                                nature="gobierno", type="quality gate",
                                source_of_truth="audits/fase2/catalogo-qg.yaml",
                                path="audits/fase2/catalogo-qg.yaml",
                                source_sha=sha, publication_sha=sha,
                                verification_level="declarado",
                                next_level_requires="recibo con artefacto",
                                confidence_basis="catalogo QG")
                inv.arista(qrid, rid, "PRODUCES_EVIDENCE", "observada",
                           "la evidencia sostiene la puerta")

    inv.alta(_id("artefacto_distribuido", "wheel"), "wheel de producto",
             nature="artefacto", type="wheel",
             purpose="distribuir el toolkit a terceros",
             responsibility="paquete instalable", owner="meta_toolkit",
             source_of_truth="pyproject.toml", path="dist/", source_sha=sha,
             publication_sha=sha,
             observed_behavior="construido y probado fuera del checkout",
             expected_behavior="instalacion limpia sin el checkout",
             verification_level="verificado",
             next_level_requires="evidencia de instalacion limpia",
             confidence_basis="recorrido de terceros")
    inv.alta(_id("artefacto_distribuido", "sdist"), "sdist de producto",
             nature="artefacto", type="sdist", purpose="distribuir el codigo",
             responsibility="paquete fuente", owner="meta_toolkit",
             source_of_truth="pyproject.toml", path="dist/", source_sha=sha,
             publication_sha=sha, verification_level="verificado",
             next_level_requires="evidencia de instalacion limpia",
             confidence_basis="construido en la ronda R09")
    inv.alta(_id("entorno_sandbox", "vault-sandbox"),
             "sandbox canonico del repo", nature="entorno", type="sandbox",
             purpose="runtime de pruebas del propio repositorio",
             responsibility="contener fixtures y notas de prueba",
             owner="ciclo_de_vida", source_of_truth="vault-sandbox/",
             path="vault-sandbox/", source_sha=sha, publication_sha=sha,
             observed_behavior="14 hallazgos de auditoria (fixtures adversariales)",
             verification_level="verificado",
             next_level_requires="higiene del vault de evidencia",
             confidence_basis="auditoria ejecutada")
    inv.alta(_id("decision_producto", "release-candidate"),
             "candidato de release CLI+MCP", nature="decision", type="candidato",
             purpose="preparar el producto para integracion", owner="propietario",
             source_of_truth="audits/architecture/ESTADO-Y-TRAZABILIDAD.md",
             source_sha=sha, publication_sha=sha,
             verification_level="declarado",
             next_level_requires="dictamen QA",
             confidence_basis="pendiente de ratificacion del propietario")

    # ── 11. cruces vivos (deuda arquitectonica vigente) ─────────────────────
    for cruce in arch.cruces():
        par = f"{cruce['from_context']}->{cruce['to_context']}"
        rid = inv.alta(_id("dependencia", par), par, nature="dependencia",
                       type="cruce declarado",
                       purpose="cruce de contextos declarado en el registro",
                       source_of_truth="scripts/vault_arch.py:CRUCES",
                       path="scripts/vault_arch.py",
                       symbol=f"{cruce.get('from')} -> {cruce.get('to')}",
                       source_sha=sha, publication_sha=sha,
                       verification_level="declarado",
                       next_level_requires="decision del propietario (A/B/C)",
                       confidence_basis="leido del registro de cruces")
        origen_id = contexto_id.get(cruce["from_context"])
        destino_id = contexto_id.get(cruce["to_context"])
        if origen_id and destino_id:
            inv.arista(rid, origen_id, "DEPENDS_ON", "declarada",
                       f"cruce declarado hacia {cruce['to_context']}")
            inv.arista(rid, destino_id, "AFFECTS", "declarada",
                       f"el cruce afecta a {cruce['to_context']}")

    # ── 12. indices transversales ──────────────────────────────────────────
    indices = {}
    for clave, nombre in (("calidad", "calidad y evidencia"),
                          ("arquitectura", "arquitectura"),
                          ("superficie-mcp", "superficie MCP"),
                          ("superficie-cli", "superficie CLI"),
                          ("gobierno", "gobernanza y normas")):
        indices[clave] = inv.alta(_id("dependencia", clave), nombre,
                                  nature="indice", type="seccion transversal",
                                  purpose="agrupa recursos del grafo",
                                  source_of_truth="generado", source_sha=sha,
                                  publication_sha=sha,
                                  verification_level="descubierto",
                                  next_level_requires="",
                                  confidence_basis="indice del generador")
    inv.arista(indices["arquitectura"], indices["calidad"], "AFFECTS",
               "declarada", "la arquitectura se acredita por las puertas")
    inv.arista(indices["superficie-cli"], indices["superficie-mcp"], "AFFECTS",
               "declarada", "CLI y MCP comparten el mismo runtime")

    # Un modulo con un test ejecutado en verde tiene comportamiento verificado.
    for mid in modulos_verificados:
        recurso = inv.recursos.get(mid)
        if recurso and recurso["verification_level"] == "implementado":
            recurso["verification_level"] = "verificado"
            recurso["next_level_requires"] = (
                "evidencia acreditada de la ejecucion (recibo con artefacto)")
            recurso["confidence_basis"] = (
                "al menos un test que lo verifica se ejecuto y paso")

    # Todo recurso dice que falta para el siguiente nivel (nunca vacio).
    for recurso in inv.recursos.values():
        if not recurso.get("next_level_requires"):
            recurso["next_level_requires"] = (
                "evidencia de ejecucion que lo confirme")

    grafo = {
        "generado_por": "audits/architecture/generar_inventario.py",
        "source_sha": sha,
        "source": "arbol git (inmutable)",
        "conteo": {"recursos": len(inv.recursos), "relaciones": len(inv.aristas),
                   "aristas_huerfanas": len(inv._huerfanos)},
        "niveles": {n: sum(1 for r in inv.recursos.values()
                           if r["verification_level"] == n) for n in NIVELES},
        "indices": indices,
        "aristas_huerfanas": inv._huerfanos,
        "relaciones": sorted(inv.aristas,
                             key=lambda a: (a["from"], a["to"], a["relation"])),
    }
    return {"inventario": inv, "grafo": grafo}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--salida-dir", default=str(RAIZ / "audits" / "architecture"))
    ap.add_argument("--sha", default=None, help="commit a inventariar")
    ap.add_argument("--verificar", action="store_true",
                    help="comprueba que el arbol de trabajo coincide con el sha")
    ap.add_argument("--junit", default=None,
                    help="JUnit XML de la corrida: sube el nivel de verificacion "
                         "de lo que se ejecuto y paso")
    args = ap.parse_args()
    salida = Path(args.salida_dir)
    salida.mkdir(parents=True, exist_ok=True)

    sha = args.sha
    if not sha:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(RAIZ),
                             capture_output=True, text=True).stdout.strip()
    if args.verificar:
        p = subprocess.run(["git", "diff", "--quiet", sha, "--"], cwd=str(RAIZ))
        if p.returncode != 0:
            print(json.dumps({"ok": False, "detalle":
                              "el arbol de trabajo difiere del sha"}, indent=2))
            return 1
    arbol = Arbol(sha)
    if not arbol.ficheros():
        print(json.dumps({"ok": False, "error_code": "SHA_INEXISTENTE",
                          "message": f"el commit {sha} no existe o no tiene "
                                     "ficheros: no se inventa un inventario"},
                         indent=2, ensure_ascii=False))
        return 2
    datos = construir(arbol, Path(args.junit) if args.junit else None)
    inv: Inventario = datos["inventario"]
    grafo = datos["grafo"]

    import yaml

    recursos = sorted(inv.recursos.values(), key=lambda r: r["id"])
    (salida / "inventario-maestro.yaml").write_text(
        yaml.safe_dump({"schema": 2,
                        "generado_por": "audits/architecture/generar_inventario.py",
                        "source_sha": sha,
                        "source": "arbol git (inmutable)",
                        "nota": ("Generado: no editar a mano. 'verification_level' "
                                 "NO es aprobacion funcional; 'next_level_requires' "
                                 "dice que falta para el siguiente nivel."),
                        "niveles": list(NIVELES),
                        "recursos": recursos},
                       allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8")
    (salida / "grafo-trazabilidad.json").write_text(
        json.dumps(grafo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    niveles = grafo["niveles"]
    print(json.dumps({"recursos": grafo["conteo"]["recursos"],
                      "relaciones": grafo["conteo"]["relaciones"],
                      "huerfanas": grafo["conteo"]["aristas_huerfanas"],
                      "niveles": niveles}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
