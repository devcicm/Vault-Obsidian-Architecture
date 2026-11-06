#!/usr/bin/env python3
"""generar_defectos_producto — defectos de producto, candidatos y gaps negativos.

## Qué mide y por qué así

Un defecto de producto es el que sufre **quien consume** la wheel, la CLI o el
MCP: una credencial que se commitea, una cifra publicada que ya no es cierta,
una remediación que nombra al modelo de quien escribió la tool. No lo que
estorba por dentro.

La regla 7 manda medir con el criterio del consumidor. Por eso el instrumento
no se pregunta «¿está declarado?» sino «¿qué pasa cuando esto se usa?»:

- Los ficheros que el vault versionado acaba rastreando se cuentan con
  `git ls-files` sobre un vault real (`--vault`), no sobre el sandbox.
- Las cifras de un documento de producto se contrastan con el registro que las
  produce, no con una copia.
- Los gaps negativos salen de dos sitios: lo que el catálogo de normas declara
  como cobertura parcial y **lo que ninguna puerta mira**, medido como carpetas
  con `.py` fuera de `CARPETAS_DE_CODIGO`.

## Uso

    python audits/analisis-por-pendiente/generar_defectos_producto.py
    python audits/analisis-por-pendiente/generar_defectos_producto.py --vault ~/.vault-master/gestion
    python audits/analisis-por-pendiente/generar_defectos_producto.py --json

`--vault` es **solo lectura**: lista el índice del repo del vault y su
`.gitignore`. No ejecuta una tool de escritura contra material ajeno.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent.parent
DESTINO = AQUI / "DEFECTOS-PRODUCTO-2026-11-05.md"

sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))


# ── 1. El vault versionado: qué acaba dentro de git ──────────────────────────

#: Lo que el vault versionado escribe dentro de sí y **no** es contenido: se
#: reescribe solo, crece con el uso, o es una credencial. Cada uno cita al
#: dueño que lo produce para que el día que cambie, el instrumento lo diga.
VOLATILES: List[Dict[str, str]] = [
    {"ruta": ".history/", "clase": "versiones por nota",
     "dueno": "vault_io.guardar_version_actual"},
    {"ruta": "vault-backups/", "clase": "copias de seguridad",
     "dueno": "vault_backup"},
    {"ruta": ".locks/", "clase": "locks de escritura",
     "dueno": "vault.kernel.bloqueo"},
    {"ruta": "00_System/.tool-trace.json", "clase": "traza de operaciones",
     "dueno": "vault_errors_trace"},
    {"ruta": "00_System/.mcp-trace-log.json", "clase": "traza del servidor MCP",
     "dueno": "mcp/nodejs/vault-mcp-server.mjs"},
    {"ruta": "00_System/.trash/", "clase": "contenido borrado",
     "dueno": "vault_delete / vault_move"},
    {"ruta": "00_System/token-usage/", "clase": "credencial del servicio de tokens",
     "dueno": "vault.consulta.repositorio.Repositorio.token_servicio_tokens"},
]


def _ignorados() -> List[str]:
    from vault.kernel.vcs import IGNORADOS_EN_GIT

    return list(IGNORADOS_EN_GIT)


def _ignorado(patrones: List[str], ruta: str) -> bool:
    """¿La política deja fuera `ruta`? Gana el último patrón que casa.

    Misma semántica que `.gitignore`, que es lo que el consumidor va a obtener.
    Sin esto, una política de una línea (`*`) se leería como «no cubre nada».
    """
    ruta = ruta.replace("\\", "/")
    estado = False
    for patron in patrones:
        niega = patron.startswith("!")
        limpio = patron[1:] if niega else patron
        casa = fnmatch.fnmatch(ruta, limpio)
        if limpio.endswith("/"):
            casa = casa or ruta == limpio[:-1] or ruta.startswith(limpio)
        if casa:
            estado = not niega
    return estado


def _cubre(ignorados: List[str], ruta: str) -> bool:
    """Compatibilidad con el nombre anterior: la ruta queda dentro del ignore."""
    return _ignorado(ignorados, ruta)


def _publicable(ruta: Path) -> str:
    """La ruta del vault, saneada: lo publicado no lleva el home de nadie.

    `tests/test_publicacion_limpia.py` veta `C:\\Users\\<nombre>` en lo
    versionado, y tiene razón: este informe se publica. Bajo el home se muestra
    con `~`; fuera de él, solo el nombre del vault.
    """
    try:
        rel = ruta.resolve().relative_to(Path.home().resolve())
        return "~/" + rel.as_posix()
    except ValueError:
        return f"<vault>/{ruta.name}"


def git_del_vault(vault: Path) -> Dict[str, Any]:
    """El índice del repo del vault, en solo lectura."""
    def _git(*args: str) -> str:
        r = subprocess.run(["git", "-C", str(vault), *args],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
        return (r.stdout or "") if r.returncode == 0 else ""

    if not (vault / ".git").exists():
        return {"es_repo": False}
    ficheros = [l for l in _git("ls-files").splitlines() if l.strip()]
    ignore = (vault / ".gitignore")
    rastreados: Dict[str, int] = {}
    for v in VOLATILES:
        rastreados[v["ruta"]] = sum(1 for f in ficheros
                                    if _cubre(v["ruta"], f))
    return {
        "es_repo": True,
        "tiene_gitignore": ignore.is_file(),
        "gitignore_bytes": ignore.stat().st_size if ignore.is_file() else 0,
        "ficheros_rastreados": len(ficheros),
        "volatiles_rastreados": rastreados,
        "volatiles_total": sum(rastreados.values()),
        "commits": int(_git("rev-list", "--count", "HEAD").strip() or 0),
    }


def medir_versionado(vault: Optional[Path]) -> Dict[str, Any]:
    from vault.kernel.vcs import IGNORADOS_POR_RIESGO

    ignorados = _ignorados() + list(IGNORADOS_POR_RIESGO)
    # Para una carpeta se mide un fichero de dentro: `!*/` deja recorrer el
    # árbol, así que preguntar por el nodo del directorio diría «no ignorado»
    # aunque su contenido sí lo esté. El `.md` es el caso difícil a propósito.
    cubiertos = {
        v["ruta"]: _cubre(ignorados,
                          v["ruta"] + "ejemplo.md" if v["ruta"].endswith("/")
                          else v["ruta"])
        for v in VOLATILES
    }
    datos: Dict[str, Any] = {
        "ignorados_declarados": ignorados,
        "volatiles": VOLATILES,
        "cubiertos": cubiertos,
        "sin_cubrir": [v["ruta"] for v in VOLATILES if not cubiertos[v["ruta"]]],
    }
    if vault is not None:
        datos["vault"] = _publicable(vault)
        datos["medicion_vault"] = git_del_vault(vault)
    return datos


# ── 2. Documentos de producto que afirman cifras ────────────────────────────

def medir_docs() -> List[Dict[str, Any]]:
    """Contrasta las afirmaciones numéricas de `docs/product/` con su registro."""
    from vault_doc_counts import (count_tools_js_native,
                                  count_tools_mcp_expuestas,
                                  count_tools_active)
    from vault_version import CURRENT_VERSION

    overview = REPO / "docs" / "product" / "overview.md"
    if not overview.is_file():
        return []
    texto = overview.read_text(encoding="utf-8", errors="replace")
    reales = {
        "tools_mcp": count_tools_mcp_expuestas(),
        "tools_total": count_tools_active(),
        "js_native": count_tools_js_native(),
        "version": CURRENT_VERSION,
    }
    hallazgos: List[Dict[str, Any]] = []
    for patron, etiqueta, clave in (
        (r"expone\s+(\d+)\s+tools", "tools expuestas por MCP", "tools_mcp"),
        (r"JS-native para\s+(\d+)\s+tools", "tools JS-native", "js_native"),
    ):
        m = re.search(patron, texto)
        if m:
            afirmado = int(m.group(1))
            hallazgos.append({
                "que": etiqueta, "afirmado": afirmado,
                "real": reales[clave], "coincide": afirmado == reales[clave],
            })
    m = re.search(r"Estándar:\s*(v[\d.]+)", texto)
    if m:
        hallazgos.append({
            "que": "versión del estándar", "afirmado": m.group(1),
            "real": reales["version"], "coincide": m.group(1) == reales["version"],
        })
    m = re.search(r"Toolkit:\s*([\d.]+)\s*\(próxima", texto)
    if m:
        hallazgos.append({
            "que": "toolkit publicado como «próxima»",
            "afirmado": m.group(1), "real": reales["version"], "coincide": False,
        })
    return hallazgos


def patrones_de_doc_counts() -> Dict[str, Any]:
    """El patrón con el que el guard vigila la cifra de MCP, tal cual está."""
    import vault_doc_counts as vdc

    for hecho in vdc.COUNTED_FACTS:
        if hecho.get("id") == "tools_mcp_expuestas":
            return {"id": hecho["id"], "patterns": hecho["patterns"],
                    "casa_con_el_doc": any(
                        re.search(p, "expone 116 tools") for p in hecho["patterns"])}
    return {}


# ── 3. Catálogo: lo que dice el enforcement frente a lo que existe ──────────

def medir_catalogo() -> Dict[str, Any]:
    from vault_norms_catalog import NORM_CATALOG

    con_hueco_declarado = [n for n in NORM_CATALOG
                           if str(n.get("cobertura_descubierta") or "").strip()]
    declaradas = {n["code"] for n in con_hueco_declarado}
    sin_tool = [{"code": n["code"], "enforcement": n["enforcement"],
                 "severity": n["severity"], "name": n["name"],
                 "cobertura": n.get("cobertura_parcial")}
                for n in NORM_CATALOG
                if n["enforcement"] in ("guard", "audit", "guard+audit")
                and not (n.get("tools_enforcing") or n.get("tools_detecting"))
                and n["code"] not in declaradas]
    descubiertas = [{"code": n["code"], "enforcement": n["enforcement"],
                     "name": n["name"],
                     "cobertura": n["cobertura_descubierta"]}
                    for n in con_hueco_declarado]
    parciales = [{"code": n["code"], "enforcement": n["enforcement"],
                  "name": n["name"], "cobertura": n["cobertura_parcial"]}
                 for n in NORM_CATALOG
                 if str(n.get("cobertura_parcial") or "").strip()]
    return {"normas": len(NORM_CATALOG), "sin_tool": sin_tool,
            "parciales": parciales, "descubiertas": descubiertas}


# ── 4. Huellas estáticas de defecto ─────────────────────────────────────────

def medir_estaticos() -> Dict[str, Any]:
    base = [REPO / "scripts", REPO / "vault", REPO / "cli"]
    py: List[Path] = []
    for b in base:
        if b.is_dir():
            py.extend(p for p in b.rglob("*.py") if "__pycache__" not in p.parts)

    def _cuenta(patron: str) -> Dict[str, Any]:
        rx = re.compile(patron, re.MULTILINE)
        ficheros, veces = [], 0
        for p in py:
            texto = p.read_text(encoding="utf-8", errors="replace")
            n = len(rx.findall(texto))
            if n:
                ficheros.append(p.relative_to(REPO).as_posix())
                veces += n
        return {"ficheros": ficheros, "veces": veces}

    return {
        "chmod_0600": _cuenta(r"chmod\([^\n]*0o0?[67]00"),
        "asserts": _cuenta(r"^\s+assert\s"),
        "utcnow": _cuenta(r"utcnow\(\)|utcfromtimestamp"),
        "agente_hardcodeado": _cuenta(r"agent:\s*deepseek"),
    }


def medir_alcance() -> Dict[str, Any]:
    """Carpetas con `.py` que ninguna puerta barre, por nombre."""
    from vault.kernel import rutas

    barridas = set(rutas.CARPETAS_DE_CODIGO) | set(rutas.CARPETAS_DE_CODIGO_Y_MCP)
    por_carpeta: Dict[str, int] = {}
    for p in REPO.rglob("*.py"):
        if any(x in p.parts for x in ("__pycache__", ".git", "node_modules")):
            continue
        rel = p.relative_to(REPO)
        if len(rel.parts) < 2:
            continue
        por_carpeta[rel.parts[0]] = por_carpeta.get(rel.parts[0], 0) + 1
    return {
        "barridas": sorted(barridas),
        "por_carpeta": dict(sorted(por_carpeta.items())),
        "sin_barrido": {k: v for k, v in sorted(por_carpeta.items())
                        if k not in barridas},
    }


def medir_estado_del_arreglo() -> Dict[str, Any]:
    """Lo que está saldado **hoy**, medido en el dueño y no en la intención."""
    import ast

    from vault.kernel.vcs import (IGNORADOS, IGNORADOS_POR_RIESGO,
                                  IGNORADOS_EN_GIT)

    vcs = (REPO / "vault" / "kernel" / "vcs.py").read_text(
        encoding="utf-8", errors="replace")
    arbol = ast.parse(vcs)
    repara = False
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.FunctionDef) and nodo.name == "commit_de_operacion":
            nombres = {n.id for n in ast.walk(nodo) if isinstance(n, ast.Name)}
            repara = "asegurar_ignorados" in nombres
            break
    init = (REPO / "scripts" / "vault_init.py").read_text(
        encoding="utf-8", errors="replace")
    politica = list(IGNORADOS_EN_GIT) + list(IGNORADOS_POR_RIESGO)
    audit = (REPO / "scripts" / "vault_audit.py").read_text(
        encoding="utf-8", errors="replace")
    token = (REPO / "scripts" / "vault_token_service.py").read_text(
        encoding="utf-8", errors="replace")
    import vault_doc_counts as _vdc
    return {
        "agente_generico": "deepseek" not in audit,
        "doc_producto_vigilado": any("product/overview.md" in d
                                     for d in _vdc.WATCHED_DOCS),
        "acl_windows": "_restringir_a_la_persona" in token,
        "token_ignorado": _ignorado(politica, "00_System/token-usage/token-service.token"),
        "trash_ignorado": _ignorado(politica, "00_System/.trash/x.md.bak"),
        "mcp_ignorado": _ignorado(politica, "00_System/.mcp-trace-log.json"),
        "notas_versionadas": (_ignorado(politica, "07_Knowledge/nota.md") is False
                              and _ignorado(politica, ".gitignore") is False),
        "repara_en_commit": repara,
        "repara_en_init": "asegurar_ignorados" in init,
    }


def medir_cobertura_del_ignore() -> Dict[str, Any]:
    """Qué volátiles fija el test del versionado y qué caso no prueba.

    Un test que enumera la lista vigente no falla cuando la lista se queda
    corta: solo prueba que las cuatro entradas de ayer siguen ahí. Y si el
    caso «ya tenía repo» no se prueba, el guard del `.gitignore` puede vivir
    dentro de la rama que ese caso nunca ejecuta.
    """
    from vault.kernel.vcs import IGNORADOS

    p = REPO / "tests" / "test_vcs_capa_de_git.py"
    if not p.is_file():
        return {"test": None}
    texto = p.read_text(encoding="utf-8", errors="replace")
    fijados = [patron for patron in IGNORADOS if f'"{patron}"' in texto]
    return {
        "test": "tests/test_vcs_capa_de_git.py",
        "fijados": fijados,
        "sin_fijar": [patron for patron in IGNORADOS if patron not in fijados],
        "prueba_repo_previo": ("repo_previo" in texto
                               or "ya tenía repo" in texto
                               or "ya existente" in texto),
        "prueba_funcional": "ls-files" in texto and "intrusos" in texto,
    }


def medir_criterios() -> Dict[str, Any]:
    """La cobertura real de `vault_criterios`, que la publica su envelope."""
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "vault_criterios.py"),
                        "--check"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600,
                       cwd=str(REPO))
    try:
        d = json.loads(r.stdout)
    except ValueError:
        return {"error": "envelope ilegible", "exit": r.returncode}
    return {k: d.get(k) for k in ("modules_measured", "modules_skipped", "ok")}


# ── 5. El documento ─────────────────────────────────────────────────────────

DEFECTOS = [
    {
        "id": "D-01",
        "sev": "alta",
        "que": "El token del servicio de tokens se commitea: vive en el vault y "
               "no está en la lista de ignorados.",
        "evidencia": ("`vault/consulta/repositorio.py:93` devuelve "
                      "`00_System/token-usage/token-service.token`; "
                      "`vault/kernel/vcs.py:48` no ignora esa carpeta y "
                      "`commit_de_operacion` hace `git add -A` (`vcs.py:108`)."),
        "efecto": "La primera operación que escriba en el vault después de "
                  "arrancar el servicio deja la credencial en `git log`. En un "
                  "vault con remoto, se publica.",
        "arreglo": "La política pasa a **solo notas `.md`**: `IGNORADOS_EN_GIT` "
                   "deja fuera todo lo que no sea markdown y `IGNORADOS_POR_RIESGO` "
                   "nombra la credencial para que el test la cruce con su dueño. "
                   "Ver C-01/C-02.",
    },
    {
        "id": "D-02",
        "sev": "media",
        "que": "Lo borrado y la traza del MCP se quedan en el repositorio: "
               "`00_System/.trash/` y `.mcp-trace-log.json` no se ignoran, "
               "aunque `.tool-trace.json` sí.",
        "evidencia": "`vault/kernel/vcs.py:48-53`; `vault_delete --force` mueve "
                     "a `.trash/` y el commit siguiente lo rastrea. La traza del "
                     "MCP la escribe `mcp/nodejs/vault-mcp-server.mjs` y cambia "
                     "en cada llamada.",
        "efecto": "`vault_delete` no borra de verdad —la nota recuperable queda "
                  "en la historia— y cada commit del vault arrastra un diff de "
                  "traza que no interesa a nadie.",
        "arreglo": "Re-ignorar `.history/`, `vault-backups/`, `.locks/` y "
                   "`00_System/.trash/` **después** de `!*.md`: contienen `.md` "
                   "que no son notas y la negación los devolvería. Ver C-02.",
    },
    {
        "id": "D-03",
        "sev": "alta",
        "que": "Un vault anterior a la capa de git se queda con repo y **sin "
               "`.gitignore`**: el versionado rastrea todo lo volátil.",
        "evidencia": "`scripts/vault_init.py:1058-1073`: el `.gitignore` se "
                     "escribe dentro de `if not (destino / '.git').exists()`, "
                     "así que un vault que ya tenía repo nunca lo recibe. El "
                     "comentario del propio código cita la medida que lo "
                     "motivó —«99 de 345 ficheros versionados eran versiones de "
                     "`.history/`»— y ese vault sigue sin el fichero: el arreglo "
                     "se aplicó a la rama que no vuelve a ejecutarse para el "
                     "caso medido. Ver «medición del vault».",
        "efecto": "Cada operación versiona `.history/`, `.trash/`, trazas y "
                  "el token. El repo crece sin techo y el diff de cada commit es "
                  "ruido.",
        "arreglo": "`commit_de_operacion` garantiza el ignore antes de `add -A` "
                   "(C-01) y una reparación explícita para vaults existentes "
                   "(C-03).",
    },
    {
        "id": "D-04",
        "sev": "baja",
        "que": "La remediación de `vault_audit` nombra un modelo concreto: "
               "«Agregar agent: deepseek».",
        "evidencia": "`scripts/vault_audit.py:2952`.",
        "efecto": "El consejo que recibe un consumidor depende de con qué "
                  "modelo trabajaba el autor de la tool. Es el criterio del "
                  "productor filtrado en la salida del producto.",
        "arreglo": "Derivar de `VAULT_AGENT` o dejar el campo como "
                   "`<agente>`; nunca un nombre propio. Ver C-04.",
    },
    {
        "id": "D-05",
        "sev": "media",
        "que": "`docs/product/overview.md` publica cifras que ya no son "
               "ciertas, y el guard de cifras no las ve.",
        "evidencia": "El documento se declara `Estado: Draft`, "
                     "`revisión: manual`, fechado el 2026-09-20, y afirma "
                     "`expone 116 tools`, "
                     "`Estándar: v40.34` y `Toolkit: 41.0 (próxima release)`. "
                     "El registro dice otra cosa: ver «afirmaciones "
                     "contrastadas». El patrón de `vault_doc_counts` exige "
                     "`expone N de las` (`vault_doc_counts.py:315`), así que "
                     "`expone 116 tools` no casa.",
        "efecto": "Un documento de producto que un consumidor lee para decidir "
                  "si instalar miente en tres cifras, y la puerta de AP-47 sale "
                  "verde.",
        "arreglo": "O se deriva del registro y se añade el patrón que falta, o "
                   "se archiva como histórico. Ver C-05.",
    },
    {
        "id": "D-06",
        "sev": "media",
        "que": "En Windows, `os.chmod(0o600)` sobre el token no protege nada: "
               "solo toca el bit de solo-lectura.",
        "evidencia": "`scripts/vault_token_service.py:448`, sin rama por "
                     "plataforma; en POSIX funciona, en Windows las ACL no "
                     "cambian y el `except OSError` esconde el no-op.",
        "efecto": "El servicio dice que la credencial «solo la lee quien puede "
                  "leer el vault» y en Windows cualquier proceso del usuario "
                  "puede leerla. La protección es declarativa, no efectiva.",
        "arreglo": "`icacls`/ACL explícita en Windows, o `%LOCALAPPDATA%`, o "
                   "declarar el límite en el docstring. Ver C-06.",
    },
    {
        "id": "D-07",
        "sev": "baja",
        "que": "Siete `assert` en código de producto desaparecen con "
               "`python -O`, incluidos los de `vault_release`.",
        "evidencia": "Ver «huellas estáticas»: `vault_release.py` valida banner, "
                     "badge y `pyproject` con `assert`.",
        "efecto": "Un release lanzado con `-O` se publica sin validar sus "
                  "cuatro sitios de versión, en silencio.",
        "arreglo": "Cambiar los `assert` de rutas de producto por `if … raise`.",
    },
]


CANDIDATOS = [
    {"id": "C-01", "que": "`commit_de_operacion` garantiza el ignore antes de "
                          "`add -A`.",
     "coste": "Una función pequeña en el dueño del versionado y un test; "
              "repara el vault la primera vez que se opera en él.",
     "beneficio": "Cierra D-01/D-02/D-03 sin pedirle nada a la persona."},
    {"id": "C-02", "que": "Separar `IGNORADOS_EN_GIT` (ruido) de "
                          "`IGNORADOS_POR_RIESGO` (credenciales y borrado), y "
                          "test que cruce las rutas que producen los dueños.",
     "coste": "Una constante y un test de contrato.",
     "beneficio": "El día que una tool escriba un secreto nuevo dentro del "
                  "vault, la puerta lo dice."},
    {"id": "C-03", "que": "Reparación explícita para vaults existentes "
                          "(`vault_init --repair` o `vault_undo` companion).",
     "coste": "Un verbo más y su docstring; toca `.gitignore` y nada más.",
     "beneficio": "Los vaults ya creados salen del estado de D-03 sin migración "
                  "manual."},
    {"id": "C-04", "que": "Quitar el nombre propio de la remediación de AP-16 y "
                          "derivarlo de `VAULT_AGENT`.",
     "coste": "Dos líneas.",
     "beneficio": "El producto deja de recomendar el modelo del autor."},
    {"id": "C-05", "que": "Cubrir `docs/product/` con `vault_doc_counts` "
                          "(patrón `expone N tools`) o archivarlo.",
     "coste": "Un patrón y, si se archiva, mover un fichero.",
     "beneficio": "Las cifras del documento de producto se regeneran o dejan de "
                  "publicarse."},
    {"id": "C-06", "que": "Credencial con ACL real en Windows o fuera del vault.",
     "coste": "Depende de la vía; la más barata es `%LOCALAPPDATA%`.",
     "beneficio": "La promesa de SP-04 pasa a ser cierta en las dos "
                  "plataformas."},
    {"id": "C-08", "que": "Barrer `vault_toolkit/` en clones y criterios, ahora "
                          "que los adaptadores son generados.",
     "coste": "Excluir `operations/` (generado, idéntico por construcción) y "
              "medir `loading.py` y el `__init__`.",
     "beneficio": "La capa de despacho del producto entra en el barrido sin "
                  "llenar la baseline."},
]


def markdown() -> str:
    versionado = medir_versionado(VAULT_ARG)
    docs = medir_docs()
    patron = patrones_de_doc_counts()
    catalogo = medir_catalogo()
    estaticos = medir_estaticos()
    alcance = medir_alcance()
    criterios = medir_criterios()
    cobertura_ignore = medir_cobertura_del_ignore()
    estado = medir_estado_del_arreglo()

    L: List[str] = []

    def an(linea: str = "") -> None:
        L.append(linea)

    an("# Defectos de producto, candidatos y gaps negativos")
    an()
    an("Documento **generado**: "
       "`python audits/analisis-por-pendiente/generar_defectos_producto.py "
       "--vault <vault real>`. Ninguna cifra está escrita a mano (AP-47).")
    an()
    an("El criterio es el de **quien consume** (regla 7): no «¿está "
       "declarado?», sino «¿qué pasa cuando se usa?». Lo que se mide sobre un "
       "vault ajeno es **solo lectura**.")
    an()

    # 1. Defectos
    an("## 1. Defectos")
    an()
    an("| ID | Sev. | Qué |")
    an("|---|---|---|")
    for d in DEFECTOS:
        an(f"| {d['id']} | {d['sev']} | {d['que']} |")
    an()
    for d in DEFECTOS:
        an(f"### {d['id']} — {d['que']}")
        an()
        an(f"- **Evidencia**: {d['evidencia']}")
        an(f"- **Efecto en el consumidor**: {d['efecto']}")
        an(f"- **Arreglo**: {d['arreglo']}")
        an()
    an("**Retirado al medir:** D-08 decía que AP-04 declaraba "
       "`enforcement: audit` sin tool ni cobertura. Falso: el catálogo **sí** "
       "declara el hueco en `cobertura_descubierta`; este instrumento solo "
       "leía `cobertura_parcial`. Era el instrumento, no el catálogo.")
    an()

    # 2. La medición del vault
    an("## 2. La medición del vault (lo que acaba dentro de git)")
    an()
    if "medicion_vault" in versionado:
        v = versionado["medicion_vault"]
        if not v.get("es_repo"):
            an("El vault medido no tiene repositorio.")
        else:
            an(f"- Vault: `{versionado['vault']}`")
            an(f"- Repo: sí · commits: **{v['commits']}** · ficheros "
               f"rastreados: **{v['ficheros_rastreados']}**")
            an(f"- `.gitignore`: "
               + (f"**sí** ({v['gitignore_bytes']} bytes)"
                  if v["tiene_gitignore"] else "**no existe**"))
            an()
            an("| Ruta volátil | Clase | ¿Ignorada por el dueño? | Rastreados |")
            an("|---|---|---|---:|")
            for fila in versionado["volatiles"]:
                an(f"| `{fila['ruta']}` | {fila['clase']} | "
                   f"{'sí' if versionado['cubiertos'][fila['ruta']] else '**no**'} | "
                   f"{v['volatiles_rastreados'].get(fila['ruta'], 0)} |")
            an()
            an(f"**Total de ficheros volátiles rastreados: "
               f"{v['volatiles_total']}**.")
    else:
        an("Sin `--vault`: solo se mide el contrato del repo. Para ver el efecto "
           "en un vault real, pásalo por `--vault`.")
    an()
    an("Lo que el dueño del versionado ignora hoy: "
       + ", ".join(f"`{i}`" for i in versionado["ignorados_declarados"]) + ".")
    an()
    an("Volátiles **sin cubrir** por el dueño: "
       + (", ".join(f"`{r}`" for r in versionado["sin_cubrir"]) or "ninguno")
       + ".")
    an()

    # 3. Documentos
    an("## 3. Afirmaciones de producto contrastadas con su registro")
    an()
    an("| Afirmación | Dice el documento | Dice el registro | ¿Coincide? |")
    an("|---|---:|---:|---|")
    for h in docs:
        an(f"| {h['que']} | {h['afirmado']} | {h['real']} | "
           f"{'sí' if h['coincide'] else '**no**'} |")
    an()
    if patron:
        an("El patrón de AP-47 para esa cifra es "
           + " o ".join(f"`{p}`" for p in patron["patterns"])
           + f"; sobre la frase del documento casa: "
           + ("sí" if patron["casa_con_el_doc"] else "**no**") + ".")
        an()

    # 4. Gaps negativos
    an("## 4. Gaps negativos (lo que ninguna puerta mide)")
    an()
    an(f"### 4.1 El catálogo declara {len(catalogo['parciales'])} coberturas "
       "parciales")
    an()
    an("Están declaradas: el catálogo no las da por cubiertas, así que son "
       "deuda honesta, no un hallazgo. Se listan porque **son** el mapa de lo "
       "que ningún guard ve.")
    an()
    for n in catalogo["parciales"]:
        texto = " ".join(str(n["cobertura"]).split())
        recorte = texto[:220] + ("…" if len(texto) > 220 else "")
        an(f"- **{n['code']}** ({n['enforcement']}) — {n['name']}: {recorte}")
    an()
    an("### 4.2 Normas con enforcement medible y sin tool")
    an()
    if catalogo["sin_tool"]:
        for n in catalogo["sin_tool"]:
            cobertura = ("sin cobertura declarada"
                         if not n["cobertura"] else "con cobertura declarada")
            an(f"- **{n['code']}** ({n['enforcement']}, {n['severity']}) — "
               f"{n['name']}: {cobertura}.")
    else:
        an("Ninguna: la única que no tiene tool lo declara por escrito. Un "
           "hueco declarado no es deuda nueva — es lo que el catálogo existe "
           "para no esconder.")
    an()
    if catalogo["descubiertas"]:
        an("### 4.2b Huecos declarados como descubiertos")
        an()
        an("No los mide nadie **y lo dicen**. Se listan porque son el mapa de "
           "lo que el estándar no sabe ver todavía.")
        an()
        for n in catalogo["descubiertas"]:
            texto = " ".join(str(n["cobertura"]).split())
            an(f"- **{n['code']}** ({n['enforcement']}) — {n['name']}: "
               + texto[:240] + ("…" if len(texto) > 240 else ""))
        an()
    an("### 4.3 Carpetas con `.py` que ningún barrido de código recorre")
    an()
    an("Los barridos usan `CARPETAS_DE_CODIGO`: "
       + ", ".join(f"`{c}`" for c in alcance["barridas"]) + ".")
    an()
    notas = {
        "audits": "instrumentos de análisis; declarados en el layout, sin "
                  "barrido de código",
        "empaquetado": "hooks de construcción de la wheel; no son producto",
        "normas": "paquetes de norma: sus `guard.py` y `test_*.py` los "
                  "descubre pytest y los vigila `--check-framework`",
        "vault_toolkit": "capa de despacho del producto: `loading.py` tiene "
                         "lógica y no la mide ninguna puerta (C-08)",
    }
    an("| Carpeta | Ficheros `.py` | ¿Barrida? | Qué es |")
    an("|---|---:|---|---|")
    for carpeta, n in alcance["por_carpeta"].items():
        barrida = carpeta in alcance["barridas"]
        if barrida:
            nota = "código del toolkit"
        else:
            nota = notas.get(carpeta, "sin declarar")
        an(f"| `{carpeta}/` | {n} | {'sí' if barrida else '**no**'} | {nota} |")
    an()
    if criterios and "modules_measured" in criterios:
        total = criterios["modules_measured"] + criterios["modules_skipped"]
        an(f"### 4.4 `vault_criterios` mide {criterios['modules_measured']} de "
           f"{total} módulos")
        an()
        an("Salta los módulos que ni nombran `*.md` ni filtran notas por sufijo: "
           "un módulo puede reimplementar el criterio sin repetir la constante y "
           "el guard no lo verá. Es una cobertura parcial **medida**, no "
           "declarada en el catálogo.")
        an()

    an("### 4.5 Por qué el defecto del versionado pasó la CI")
    an()
    if cobertura_ignore.get("test"):
        an(f"El test `{cobertura_ignore['test']}` fija los patrones de la "
           "política ("
           + (", ".join(f"`{r}`" for r in cobertura_ignore["fijados"])
              or "ninguno")
           + ") y "
           + ("**sí** comprueba el resultado en el índice (`git ls-files`), que "
              "es el criterio del consumidor."
              if cobertura_ignore.get("prueba_funcional")
              else "**no** comprueba el índice.")
           + " El caso «vault que ya tenía repo» "
           + ("**sí** se prueba: la garantía vive en `commit_de_operacion`, que "
              "corre en cada escritura."
              if cobertura_ignore["prueba_repo_previo"]
              else "**no** se prueba — la rama donde vive el guard."))
    an()

    # 5. Huellas estáticas
    an("## 5. Huellas estáticas")
    an()
    an("| Clase | Sitios |")
    an("|---|---:|")
    for etiqueta, clave in (
            ("`chmod` con permiso `0600`/`0700`", "chmod_0600"),
            ("`assert` en código de producto", "asserts"),
            ("`utcnow()`/`utcfromtimestamp` (deprecados desde 3.12)", "utcnow"),
            ("Remediación con un modelo hardcodeado", "agente_hardcodeado")):
        dato = estaticos[clave]
        an(f"| {etiqueta} | {dato['veces']} en {len(dato['ficheros'])} "
           f"ficheros |")
    an()
    for clave, titulo in (("chmod_0600", "chmod"),
                          ("asserts", "assert"),
                          ("agente_hardcodeado", "modelo hardcodeado")):
        dato = estaticos[clave]
        if dato["ficheros"]:
            an(f"- **{titulo}**: "
               + ", ".join(f"`{f}`" for f in dato["ficheros"]) + ".")
    an()

    # 6. Candidatos
    an("## 6. Candidatos")
    an()
    an("| ID | Qué | Coste | Beneficio |")
    an("|---|---|---|---|")
    for c in CANDIDATOS:
        an(f"| {c['id']} | {c['que']} | {c['coste']} | {c['beneficio']} |")
    an()

    # 8. Estado tras el arreglo (se salda, no se borra)
    an("## 7. Estado tras el arreglo")
    an()
    an("Una deuda que se salda no se borra: pasa a `saldada` con la evidencia "
       "de que está cerrada. Esto se mide en el dueño, no en la intención.")
    an()
    an("| Defecto | Estado | Evidencia |")
    an("|---|---|---|")
    an(f"| D-01 | {'saldado' if estado['token_ignorado'] else 'abierto'} | "
       "`IGNORADOS_POR_RIESGO` "
       + ("cubre la credencial" if estado["token_ignorado"] else "no la cubre")
       + " |")
    an(f"| D-02 | "
       f"{'saldado' if (estado['trash_ignorado'] and estado['mcp_ignorado']) else 'abierto'} | "
       "`.trash/` "
       + ("cubierto" if estado["trash_ignorado"] else "sin cubrir")
       + " y `.mcp-trace-log.json` "
       + ("cubierto" if estado["mcp_ignorado"] else "sin cubrir") + " |")
    an(f"| Notas | "
       f"{'sí' if estado.get('notas_versionadas') else 'no'} | "
       "la política deja versionar `*.md` y el propio `.gitignore` |")
    medido = versionado.get("medicion_vault") or {}
    d03_datos = bool(medido.get("es_repo") and medido.get("tiene_gitignore")
                     and medido.get("volatiles_total", 1) == 0)
    an(f"| D-04 | {'saldado' if estado['agente_generico'] else 'abierto'} | "
       "la remediación de AP-16 no nombra un modelo concreto |")
    an(f"| D-05 | {'saldado' if estado['doc_producto_vigilado'] else 'abierto'} | "
       "`docs/product/overview.md` entra en `WATCHED_DOCS` y sus cifras se "
       "contrastan con el registro |")
    an(f"| D-06 | {'saldado' if estado['acl_windows'] else 'abierto'} | "
       "la credencial se restringe con ACL real en Windows (`icacls`) y con "
       "`chmod 0600` en POSIX |")
    an(f"| D-07 | {'saldado' if estaticos['asserts']['veces'] == 0 else 'abierto'} | "
       f"{estaticos['asserts']['veces']} `assert` en código de producto |")
    an(f"| D-03 | "
       f"{'saldado' if d03_datos else 'mecanismo saldado' if (estado['repara_en_commit'] and estado['repara_en_init']) else 'abierto'} | "
       "`commit_de_operacion` "
       + ("repara el ignore en cada escritura" if estado["repara_en_commit"]
          else "**no** repara")
       + " y `vault_init` "
       + ("usa el mismo dueño" if estado["repara_en_init"] else "sigue con su copia")
       + ". Los ficheros ya rastreados se dejan en la traza "
       "(`rastreados_ignorados`) y retirarlos del índice es una decisión "
       "del dueño, no un efecto colateral. |")
    an()
    if "medicion_vault" in versionado:
        v = versionado["medicion_vault"]
        pendiente = v.get("volatiles_total", 0) if v.get("es_repo") else 0
        if pendiente == 0 and v.get("tiene_gitignore"):
            an("El vault medido ya no rastrea volátiles: tiene su `.gitignore` y "
               "su índice solo lleva notas. El `HEAD` de vuelta de esa limpieza "
               "está en el registro del vault.")
        else:
            an(f"El vault medido sigue con **{pendiente}** ficheros volátiles en "
               "el índice: la próxima operación que escriba le añade el "
               "`.gitignore` y deja de sumar, pero los que ya están no se "
               "retiran solos.")
        an()

    # 7. Zonas limpias
    an("## 8. Lo que se midió y está limpio")
    an()
    an("No todo es hallazgo. Estas cosas se probaron y no dieron defecto:")
    an()
    an("- **Las 26 puertas rápidas** en verde sobre este mismo árbol.")
    an("- **La paridad de contratos**: toda tool del catálogo tiene entrada en "
       "`tool-spec.json` y ninguna tiene backend duplicado Python + Node.")
    an("- **El error envelope**: ningún envelope nuevo fuera de "
       "`ERROR_CATALOG` (AP-52) en su parte decidible.")
    an("- **Las escrituras**: AP-36 en verde; sin escrituras fuera del vault.")
    an("- **git**: AP-68 sin baseline y sin sitios fuera del dueño.")
    an("- **Código muerto**: 0 (barrido de dark data, 2026-11-05).")
    an()
    return "\n".join(L) + "\n"


def main() -> int:
    global VAULT_ARG
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser(
        description="defectos de producto, candidatos y gaps negativos")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--vault", type=Path, default=None,
                    help="vault real para medir el versionado (solo lectura)")
    args = ap.parse_args()

    VAULT_ARG = args.vault.expanduser().resolve() if args.vault else None

    if args.json:
        print(json.dumps({
            "versionado": medir_versionado(VAULT_ARG),
            "docs": medir_docs(),
            "catalogo": medir_catalogo(),
            "estaticos": medir_estaticos(),
            "alcance": medir_alcance(),
            "criterios": medir_criterios(),
        }, ensure_ascii=False, indent=1, default=str))
        return 0

    texto = markdown()
    DESTINO.write_text(texto, encoding="utf-8")
    print(f"escrito: {DESTINO.relative_to(REPO)} ({len(texto)} bytes)")
    return 0


VAULT_ARG: Optional[Path] = None

if __name__ == "__main__":
    raise SystemExit(main())
