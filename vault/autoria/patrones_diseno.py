"""Detector determinista de patrones de diseno y arquitectura (interno y externo).

Dueño unico dentro del contexto `autoria` para:
- publicar el catalogo canonico, categorizado y ordenado de patrones (5 categorias);
- inspeccionar cualquier repositorio o archivo (interno del vault/repo o externo)
  mediante AST real en Python y reglas estructurales conservadoras en JS/TS/Go/C#/Rust/Java;
- devolver evidencia verificable (`file` relativo POSIX, `line`, `symbol`, `confidence`, `how`)
  sin inventar hallazgos (AP-45) y sin filtrar rutas absolutas de maquina.

Cero dependencias externas: solo stdlib de Python >= 3.9.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from vault.kernel import rutas

CATEGORIAS: Tuple[str, ...] = (
    "arquitectonicos",
    "creacionales",
    "estructurales",
    "comportamiento",
    "concurrencia_resiliencia",
)

ETIQUETAS_CATEGORIA: Dict[str, str] = {
    "arquitectonicos": "Patrones Arquitectonicos",
    "creacionales": "Patrones Creacionales",
    "estructurales": "Patrones Estructurales",
    "comportamiento": "Patrones de Comportamiento",
    "concurrencia_resiliencia": "Patrones de Concurrencia y Resiliencia",
}

CATALOGO_PATRONES: Tuple[Dict[str, str], ...] = (
    # 1. Arquitectonicos
    {
        "id": "bounded-contexts-ddd",
        "order": "1.1",
        "name": "Bounded Contexts (DDD)",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Delimita contextos de dominio explicitos con lenguaje ubicuo y presupuesto de cruces.",
    },
    {
        "id": "hexagonal-ports-adapters",
        "order": "1.2",
        "name": "Hexagonal / Ports & Adapters",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Desacopla el dominio de los adaptadores externos mediante puertos explicitos.",
    },
    {
        "id": "cqrs",
        "order": "1.3",
        "name": "CQRS",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Separa operaciones de lectura/consulta (paralelizables) de comandos de escritura (serializados por recurso).",
    },
    {
        "id": "append-only-event-log",
        "order": "1.4",
        "name": "Append-Only Event Log",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Registra mutaciones en un log de solo anexado (p. ej. JSONL) para auditoria y reconstruccion en O(1).",
    },
    {
        "id": "single-source-of-truth-registry",
        "order": "1.5",
        "name": "Single Source of Truth / Registry",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Centraliza catalogos y contratos en un registro canonico del que se derivan artefactos.",
    },
    {
        "id": "composition-root",
        "order": "1.6",
        "name": "Composition Root",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Concentra el ensamblaje de contexto, repositorios y adaptadores en un punto unico.",
    },
    # 2. Creacionales
    {
        "id": "builder",
        "order": "2.1",
        "name": "Builder",
        "category": "creacionales",
        "pattern_type": "design",
        "summary": "Construye objetos o documentos complejos paso a paso antes de renderizarlos o validarlos.",
    },
    {
        "id": "factory",
        "order": "2.2",
        "name": "Factory",
        "category": "creacionales",
        "pattern_type": "design",
        "summary": "Encapsula la creacion parametrizada de instancias o validadores reutilizables.",
    },
    {
        "id": "singleton-module-cache",
        "order": "2.3",
        "name": "Singleton / Module-Scoped Cache",
        "category": "creacionales",
        "pattern_type": "design",
        "summary": "Mantiene una instancia o cache unica por proceso para evitar trabajo repetido.",
    },
    # 3. Estructurales
    {
        "id": "repository",
        "order": "3.1",
        "name": "Repository",
        "category": "estructurales",
        "pattern_type": "design",
        "summary": "Encapsula el acceso a persistencia, rutas o colecciones tras una frontera de dominio.",
    },
    {
        "id": "adapter",
        "order": "3.2",
        "name": "Adapter",
        "category": "estructurales",
        "pattern_type": "design",
        "summary": "Traduce la interfaz de un modulo o proveedor externo al contrato esperado por el dominio.",
    },
    {
        "id": "module-alias-facade",
        "order": "3.3",
        "name": "Module Alias / Facade",
        "category": "estructurales",
        "pattern_type": "design",
        "summary": "Expone una fachada simplificada o alias de compatibilidad sobre modulos internos.",
    },
    {
        "id": "proxy-lazy-export",
        "order": "3.4",
        "name": "Proxy (Lazy Export)",
        "category": "estructurales",
        "pattern_type": "design",
        "summary": "Controla o difiere el acceso y la carga de un recurso hasta su uso efectivo.",
    },
    # 4. Comportamiento
    {
        "id": "template-method",
        "order": "4.1",
        "name": "Template Method",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Define el esqueleto invariante de un flujo y delega pasos variables a subclases.",
    },
    {
        "id": "chain-of-responsibility",
        "order": "4.2",
        "name": "Chain of Responsibility",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Encadena manejadores o guardas secuenciales que validan o procesan una solicitud.",
    },
    {
        "id": "state-machine",
        "order": "4.3",
        "name": "State Machine",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Gobierna transiciones explicitas entre estados validos rechazando saltos ilegales.",
    },
    {
        "id": "strategy",
        "order": "4.4",
        "name": "Strategy",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Permite intercambiar algoritmos o politicas en tiempo de ejecucion via tabla o protocolo.",
    },
    {
        "id": "command-dispatch-router",
        "order": "4.5",
        "name": "Command + Dispatch Router",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Encapsula invocaciones como comandos y las despacha declarativamente por ruta o accion.",
    },
    {
        "id": "envelope-result-object",
        "order": "4.6",
        "name": "Envelope / Result Object",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Estandariza respuestas y errores estructurados con codigo, categoria y recuperacion.",
    },
    {
        "id": "observer-event-bus",
        "order": "4.7",
        "name": "Observer / Event Bus",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Notifica eventos a suscriptores desacoplados sin acoplar emisor y oyentes.",
    },
    # 5. Concurrencia y Resiliencia
    {
        "id": "atomic-write",
        "order": "5.1",
        "name": "Atomic Write",
        "category": "concurrencia_resiliencia",
        "pattern_type": "code",
        "summary": "Escribe a archivo temporal y reemplaza atomicamente para evitar lecturas parciales.",
    },
    {
        "id": "reentrant-cross-process-lock",
        "order": "5.2",
        "name": "Reentrant & Cross-Process Lock",
        "category": "concurrencia_resiliencia",
        "pattern_type": "code",
        "summary": "Serializa secciones criticas entre hilos o procesos mediante locks explicitos.",
    },
    {
        "id": "process-isolation-sandbox",
        "order": "5.3",
        "name": "Process Isolation / Sandbox",
        "category": "concurrencia_resiliencia",
        "pattern_type": "code",
        "summary": "Aisla subprocesos (Job Object / subreaper / sesion nueva) para contener timeouts y fallos.",
    },
    {
        "id": "snapshot-quarantine-rollback",
        "order": "5.4",
        "name": "Snapshot, Quarantine & Rollback",
        "category": "concurrencia_resiliencia",
        "pattern_type": "code",
        "summary": "Resguarda instantaneas o cuarentena antes de mutaciones destructivas para garantizar vuelta atras.",
    },
    {
        "id": "wave-resource-scheduler",
        "order": "5.5",
        "name": "Wave / Resource-Based Scheduler",
        "category": "concurrencia_resiliencia",
        "pattern_type": "code",
        "summary": "Planifica ejecuciones paralelas en olas o colas respetando conflictos de recursos.",
    },
)

_POR_ID: Dict[str, Dict[str, str]] = {p["id"]: p for p in CATALOGO_PATRONES}

_DIRECTORIOS_OMITIDOS: Set[str] = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".history",
    ".backups",
    ".quarantine",
    rutas.SANDBOX,
    rutas.TESTS,
    "test",
    "__tests__",
}

_EXTENSIONES_PYTHON: Set[str] = {".py"}
_EXTENSIONES_GENERICAS: Set[str] = {".js", ".mjs", ".cjs", ".ts", ".tsx", ".cs", ".go", ".rs", ".java"}
_EXTENSIONES_SOPORTADAS: Set[str] = _EXTENSIONES_PYTHON | _EXTENSIONES_GENERICAS

_MAX_EVIDENCIAS_POR_PATRON = 20
_MAX_BYTES_ARCHIVO = 1_500_000

# ── Reglas precompiladas para analisis multi-lenguaje (sin cuantificadores anidados) ──

_REGLAS_GENERICAS: Tuple[Tuple[str, re.Pattern, str, str], ...] = (
    (
        "cqrs",
        re.compile(r"\bclass\s+(AsyncRWCoordinator|[A-Za-z0-9_]*(?:CommandHandler|QueryHandler|CommandBus|QueryBus))\b"),
        "evidencia_fuerte",
        "Clase coordinadora CQRS de lectura/escritura o bus de comandos/consultas",
    ),
    (
        "repository",
        re.compile(r"\b(?:class|struct|interface)\s+([A-Za-z0-9_]*Repository|Repositorio[A-Za-z0-9_]*)\b"),
        "evidencia_fuerte",
        "Tipo Repository que encapsula acceso a datos",
    ),
    (
        "adapter",
        re.compile(r"\b(?:class|struct)\s+([A-Za-z0-9_]*Adapter|Adaptador[A-Za-z0-9_]*)\b"),
        "evidencia_fuerte",
        "Tipo Adapter que adapta interfaces entre componentes",
    ),
    (
        "builder",
        re.compile(r"\b(?:class|struct)\s+([A-Za-z0-9_]*Builder)\b"),
        "evidencia_fuerte",
        "Clase Builder para construccion incremental",
    ),
    (
        "factory",
        re.compile(r"\b(?:class|struct)\s+([A-Za-z0-9_]*Factory)\b"),
        "evidencia_fuerte",
        "Clase Factory para creacion encapsulada de objetos",
    ),
    (
        "module-alias-facade",
        re.compile(r"\b(?:class|struct)\s+([A-Za-z0-9_]*Facade)\b"),
        "evidencia_fuerte",
        "Clase Facade que expone una interfaz simplificada",
    ),
    (
        "proxy-lazy-export",
        re.compile(r"\bclass\s+([A-Za-z0-9_]*Proxy)\b"),
        "indicio_estructural",
        "Clase Proxy para intermediar acceso a un recurso",
    ),
    (
        "strategy",
        re.compile(r"\b(?:class|interface|struct)\s+([A-Za-z0-9_]*Strategy)\b"),
        "evidencia_fuerte",
        "Tipo Strategy para algoritmos intercambiables",
    ),
    (
        "state-machine",
        re.compile(r"\b(?:class\s+([A-Za-z0-9_]*StateMachine)|(?:const|let|var)\s+(VALID_TRANSITIONS|STATE_TRANSITIONS|STATUS_TRANSITIONS))\b"),
        "evidencia_fuerte",
        "Maquina de estados o tabla explicita de transiciones",
    ),
    (
        "command-dispatch-router",
        re.compile(r"\b(?:const|let|var)\s+(ROUTES|COMMAND_ROUTES)\s*=\s*\{"),
        "evidencia_fuerte",
        "Tabla declarativa de enrutamiento de comandos/metodos",
    ),
    (
        "envelope-result-object",
        re.compile(r"\bfunction\s+(construirError|emitError|buildEnvelope)\s*\("),
        "evidencia_fuerte",
        "Constructor canonico de envelope estructurado de respuesta/error",
    ),
    (
        "observer-event-bus",
        re.compile(r"\b(?:extends\s+(EventEmitter)|class\s+([A-Za-z0-9_]*(?:Observer|EventBus)))\b"),
        "evidencia_fuerte",
        "Publicacion y suscripcion de eventos desacoplados",
    ),
    (
        "singleton-module-cache",
        re.compile(r"\bstatic\s+(getInstance)\s*\("),
        "indicio_estructural",
        "Punto de acceso estatico unico tipo Singleton",
    ),
    (
        "reentrant-cross-process-lock",
        re.compile(r"\b(?:new\s+(Mutex|Semaphore|RWLock)|sync\.(Mutex|RWMutex))\b"),
        "evidencia_fuerte",
        "Primitiva explicita de exclusion mutua o semaforo",
    ),
    (
        "wave-resource-scheduler",
        re.compile(r"\bclass\s+([A-Za-z0-9_]*Scheduler|AsyncRWCoordinator)\b"),
        "evidencia_fuerte",
        "Planificador o coordinador concurrente por tipo de acceso",
    ),
)

_RE_SLUGS = re.compile(r"[^a-z0-9]+")


def normalizar_nombre_patron(nombre: str) -> str:
    """Clave estable para cruzar nombres de patrones entre detector y vault."""
    return _RE_SLUGS.sub("-", nombre.strip().lower()).strip("-")


def catalogo_ordenado(categoria: Optional[str] = None) -> Dict[str, Any]:
    """Devuelve el catalogo canonico de patrones agrupado y ordenado por categoria."""
    if categoria is not None and categoria not in ETIQUETAS_CATEGORIA:
        raise ValueError(f"Categoria invalida: {categoria}. Validas: {list(CATEGORIAS)}")

    cats = (categoria,) if categoria else CATEGORIAS
    grupos: List[Dict[str, Any]] = []
    planos: List[Dict[str, Any]] = []

    for cat in cats:
        items = [
            {
                "id": p["id"],
                "order": p["order"],
                "pattern": p["name"],
                "category": p["category"],
                "category_label": ETIQUETAS_CATEGORIA[p["category"]],
                "type": p["pattern_type"],
                "summary": p["summary"],
            }
            for p in CATALOGO_PATRONES
            if p["category"] == cat
        ]
        grupos.append({
            "category": cat,
            "label": ETIQUETAS_CATEGORIA[cat],
            "count": len(items),
            "patterns": items,
        })
        planos.extend(items)

    return {
        "ok": True,
        "mode": "catalog",
        "total_catalog": len(planos),
        "categories": grupos,
        "patterns": planos,
    }


def _nombre_base(nodo: ast.expr) -> str:
    if isinstance(nodo, ast.Name):
        return nodo.id
    if isinstance(nodo, ast.Attribute):
        return nodo.attr
    return ""


def _es_decorador(dec: ast.expr, nombre: str) -> bool:
    if isinstance(dec, ast.Name):
        return dec.id == nombre
    if isinstance(dec, ast.Attribute):
        return dec.attr == nombre
    if isinstance(dec, ast.Call):
        return _es_decorador(dec.func, nombre)
    return False


def _nombre_asignado(nodo: ast.AST) -> Optional[str]:
    if isinstance(nodo, ast.Assign) and nodo.targets:
        t = nodo.targets[0]
        if isinstance(t, ast.Name):
            return t.id
    if isinstance(nodo, ast.AnnAssign) and isinstance(nodo.target, ast.Name):
        return nodo.target.id
    return None


def _valor_asignado(nodo: ast.AST) -> Optional[ast.expr]:
    if isinstance(nodo, ast.Assign):
        return nodo.value
    if isinstance(nodo, ast.AnnAssign):
        return nodo.value
    return None


def _es_call_nombre(nodo: ast.Call, nombres: Set[str]) -> Optional[str]:
    if isinstance(nodo.func, ast.Name) and nodo.func.id in nombres:
        return nodo.func.id
    if isinstance(nodo.func, ast.Attribute) and nodo.func.attr in nombres:
        return nodo.func.attr
    return None


def _tiene_sys_modules_alias(nodo: ast.Assign) -> bool:
    for t in nodo.targets:
        if not isinstance(t, ast.Subscript):
            continue
        val = t.value
        if (
            isinstance(val, ast.Attribute)
            and isinstance(val.value, ast.Name)
            and val.value.id == "sys"
            and val.attr == "modules"
        ):
            slc = t.slice
            if isinstance(slc, ast.Name) and slc.id == "__name__":
                return True
    return False


def _es_template_method(cls: ast.ClassDef) -> bool:
    bases = {_nombre_base(b) for b in cls.bases}
    abstractos: Set[str] = set()
    concretos: List[ast.FunctionDef] = []
    for item in cls.body:
        if not isinstance(item, ast.FunctionDef):
            continue
        es_abs = any(_es_decorador(d, "abstractmethod") for d in item.decorator_list)
        if not es_abs:
            for sub in ast.walk(item):
                if isinstance(sub, ast.Raise) and isinstance(sub.exc, (ast.Name, ast.Call)):
                    nombre_exc = (
                        sub.exc.id if isinstance(sub.exc, ast.Name) else _nombre_base(sub.exc.func)
                    )
                    if nombre_exc == "NotImplementedError":
                        es_abs = True
                        break
        if es_abs:
            abstractos.add(item.name)
        elif not item.name.startswith("__"):
            concretos.append(item)

    if not abstractos or not concretos:
        return False
    for fn in concretos:
        for sub in ast.walk(fn):
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and isinstance(sub.func.value, ast.Name)
                and sub.func.value.id == "self"
                and sub.func.attr in abstractos
            ):
                return True
    return "ABC" in bases and bool(abstractos) and bool(concretos)


def _detectar_python(
    arbol: ast.Module,
    rel_posix: str,
    hallazgos: Dict[str, List[Dict[str, Any]]],
) -> None:
    def agregar(pid: str, line: int, symbol: str, confidence: str, how: str) -> None:
        hallazgos.setdefault(pid, []).append({
            "file": rel_posix,
            "line": int(line),
            "symbol": symbol,
            "confidence": confidence,
            "how": how,
        })

    # Nivel modulo: constantes, clases y funciones top-level
    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign) and _tiene_sys_modules_alias(nodo):
            agregar(
                "module-alias-facade",
                nodo.lineno,
                "sys.modules[__name__]",
                "evidencia_fuerte",
                "Alias de modulo que reexporta al dueno canonico conservando contrato",
            )
            continue

        nombre_var = _nombre_asignado(nodo)
        valor_var = _valor_asignado(nodo)
        if nombre_var and valor_var is not None:
            if nombre_var in ("CONTEXTS", "BOUNDED_CONTEXTS", "PRESUPUESTO_DE_CRUCES"):
                agregar(
                    "bounded-contexts-ddd",
                    nodo.lineno,
                    nombre_var,
                    "evidencia_fuerte",
                    "Registro explicito de contextos acotados o presupuesto de cruces",
                )
            elif nombre_var == "ACCESS_MODES" or nombre_var == "GLOBAL_SCOPE_TOOLS":
                agregar(
                    "cqrs",
                    nodo.lineno,
                    nombre_var,
                    "evidencia_fuerte",
                    "Contrato canonico de clasificacion lectura/escritura/global (CQRS)",
                )
            elif (
                nombre_var.endswith(("_CATALOG", "_REGISTRY", "REGISTRIES"))
                and isinstance(valor_var, (ast.Dict, ast.Tuple, ast.List))
            ):
                agregar(
                    "single-source-of-truth-registry",
                    nodo.lineno,
                    nombre_var,
                    "evidencia_fuerte",
                    "Registro canonico de fuente unica de verdad",
                )
            elif (
                "TRANSITIONS" in nombre_var or nombre_var == "STATE_MACHINE"
            ) and isinstance(valor_var, (ast.Dict, ast.Call)):
                agregar(
                    "state-machine",
                    nodo.lineno,
                    nombre_var,
                    "evidencia_fuerte",
                    "Mapa explicito de transiciones validas de estado",
                )
            elif (
                nombre_var in ("RANKINGS", "STRATEGIES")
                or nombre_var.endswith(("_STRATEGIES", "_RANKINGS"))
            ) and isinstance(valor_var, (ast.Dict, ast.Tuple, ast.List)):
                agregar(
                    "strategy",
                    nodo.lineno,
                    nombre_var,
                    "evidencia_fuerte",
                    "Tabla o catalogo de estrategias intercambiables por clave",
                )
            elif (
                isinstance(valor_var, ast.Constant)
                and isinstance(valor_var.value, str)
                and valor_var.value.endswith(".jsonl")
            ):
                agregar(
                    "append-only-event-log",
                    nodo.lineno,
                    nombre_var,
                    "evidencia_fuerte",
                    f"Declaracion de bitacora JSONL append-only (`{valor_var.value}`)",
                )
            elif (
                nombre_var in ("ROUTES", "COMMAND_ROUTES", "DISPATCH")
                and isinstance(valor_var, ast.Dict)
            ):
                agregar(
                    "command-dispatch-router",
                    nodo.lineno,
                    nombre_var,
                    "evidencia_fuerte",
                    "Tabla declarativa de despacho de comandos/rutas",
                )
            elif nombre_var in ("_LOCAL_LOCKS", "_INSTANCE", "_SINGLETON"):
                agregar(
                    "singleton-module-cache",
                    nodo.lineno,
                    nombre_var,
                    "indicio_estructural",
                    "Estado o tabla unica de proceso con alcance de modulo",
                )
            elif isinstance(valor_var, ast.Call):
                llamado = _es_call_nombre(valor_var, {"Lock", "RLock", "Semaphore"})
                if llamado:
                    agregar(
                        "reentrant-cross-process-lock",
                        nodo.lineno,
                        f"{nombre_var} ({llamado})",
                        "evidencia_fuerte",
                        f"Instanciacion de lock explicito `{llamado}` para exclusion mutua",
                    )

            # Puertos declarados dentro de CONTEXTS (Hexagonal)
            if nombre_var == "CONTEXTS" and isinstance(valor_var, ast.Dict):
                for val_ctx in valor_var.values:
                    if isinstance(val_ctx, ast.Dict):
                        claves = {
                            k.value for k in val_ctx.keys
                            if isinstance(k, ast.Constant) and isinstance(k.value, str)
                        }
                        if "puertos" in claves:
                            agregar(
                                "hexagonal-ports-adapters",
                                nodo.lineno,
                                "CONTEXTS[*]['puertos']",
                                "evidencia_fuerte",
                                "Declaracion formal de puertos entre contextos acotados",
                            )
                            break

        elif isinstance(nodo, ast.ClassDef):
            cname = nodo.name
            metodos = {
                m.name for m in nodo.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            if cname.endswith("Repository") or cname.startswith("Repositorio"):
                agregar(
                    "repository",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Clase Repository que encapsula persistencia/rutas del dominio",
                )
            if cname.endswith("Adapter") or cname.startswith("Adaptador") or cname == "NormasDelCatalogo":
                agregar(
                    "adapter",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Clase Adapter que traduce contratos entre capas",
                )
            if cname.endswith("Builder") or (
                cname == "Frontmatter" and {"set", "render"}.issubset(metodos)
            ):
                agregar(
                    "builder",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Clase Builder con construccion incremental y render/build final",
                )
            if cname.endswith("Factory"):
                agregar(
                    "factory",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Clase Factory que encapsula instanciacion",
                )
            if cname.endswith("Facade"):
                agregar(
                    "module-alias-facade",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Clase Facade que simplifica el acceso a un subsistema",
                )
            if cname.endswith("Proxy") or cname == "_StablePrimitiveExport":
                agregar(
                    "proxy-lazy-export",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Clase Proxy que media o difiere la resolucion del recurso",
                )
            if cname.endswith("Strategy"):
                agregar(
                    "strategy",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Clase Strategy que encapsula algoritmo intercambiable",
                )
            if cname.endswith("StateMachine"):
                agregar(
                    "state-machine",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Clase StateMachine con transiciones gobernadas",
                )
            if cname.endswith(("CommandHandler", "QueryHandler", "CommandBus", "QueryBus")) or cname == "AsyncRWCoordinator":
                agregar(
                    "cqrs",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Componente explicito CQRS de comandos/consultas",
                )
            if cname.endswith(("Command", "Dispatcher", "Router")) or cname == "Operation":
                agregar(
                    "command-dispatch-router",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Objeto Command/Operation o enrutador de despacho",
                )
            if cname.endswith(("Observer", "EventBus", "Publisher")):
                agregar(
                    "observer-event-bus",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Clase Observer/EventBus para notificaciones desacopladas",
                )
            if cname.endswith(("Scheduler",)) or cname == "Wave":
                agregar(
                    "wave-resource-scheduler",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Planificador por olas o recursos concurrentes",
                )
            if cname.endswith(("Handler", "Middleware")) and (
                "set_next" in metodos or "next_handler" in metodos
            ):
                agregar(
                    "chain-of-responsibility",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Manejador encadenable en Chain of Responsibility",
                )
            if _es_template_method(nodo):
                agregar(
                    "template-method",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Clase base Template Method con metodo concreto y hooks abstractos",
                )
            if "__new__" in metodos:
                for sub in ast.walk(nodo):
                    if isinstance(sub, ast.Attribute) and sub.attr in ("_instance", "_instancia"):
                        agregar(
                            "singleton-module-cache",
                            nodo.lineno,
                            cname,
                            "evidencia_fuerte",
                            "Singleton clasico mediante control en `__new__`",
                        )
                        break

        elif isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fname = nodo.name
            if fname == "__getattr__":
                agregar(
                    "proxy-lazy-export",
                    nodo.lineno,
                    "__getattr__",
                    "evidencia_fuerte",
                    "Exportacion perezosa a nivel de modulo (PEP 562)",
                )
            if fname in ("construir", "create_container", "compose_app") and (
                "adaptadores" in rel_posix or "__init__" in rel_posix or "container" in rel_posix
            ):
                agregar(
                    "composition-root",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Raiz de composicion que ensambla contexto y adaptadores",
                )
            if fname in ("proyecto_registrado", "crear_validador") or fname.endswith("_factory"):
                agregar(
                    "factory",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Fabrica parametrizada que construye validadores u objetos",
                )
            if fname in ("emit_error", "wrap_main", "emit_fallo", "construir_error"):
                agregar(
                    "envelope-result-object",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Emisor canonico de envelopes de respuesta/error",
                )
            if fname in ("file_lock", "indice_compartido"):
                agregar(
                    "reentrant-cross-process-lock",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Primitiva de bloqueo reentrante o entre procesos",
                )
            if fname in ("guardar_version_actual", "quarantine_file", "rollback_to_commit"):
                agregar(
                    "snapshot-quarantine-rollback",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Mecanismo explicito de snapshot, cuarentena o rollback",
                )
            if any(_es_decorador(d, "lru_cache") or _es_decorador(d, "cache") for d in nodo.decorator_list):
                agregar(
                    "singleton-module-cache",
                    nodo.lineno,
                    fname,
                    "indicio_estructural",
                    "Memoizacion con alcance de proceso (`@lru_cache`/`@cache`)",
                )

            # Guard chain dentro de funciones criticas (>= 3 llamadas a _verificar_*/guard_*)
            guard_calls: Set[str] = set()
            tiene_os_replace = False
            tiene_aislamiento = False
            tiene_jsonl_append = False
            for sub in ast.walk(nodo):
                if isinstance(sub, ast.Call):
                    cn = _es_call_nombre(sub, {"replace", "CreateJobObjectW", "prctl", "open"})
                    if cn == "replace" and isinstance(sub.func, ast.Attribute) and isinstance(sub.func.value, ast.Name) and sub.func.value.id == "os":
                        tiene_os_replace = True
                    elif cn in ("CreateJobObjectW", "prctl"):
                        tiene_aislamiento = True
                    elif cn == "open" and len(sub.args) >= 2:
                        if isinstance(sub.args[1], ast.Constant) and isinstance(sub.args[1].value, str) and "a" in sub.args[1].value:
                            for arg_sub in ast.walk(sub.args[0]):
                                if isinstance(arg_sub, ast.Constant) and isinstance(arg_sub.value, str) and ".jsonl" in arg_sub.value:
                                    tiene_jsonl_append = True
                                elif isinstance(arg_sub, ast.Name) and "log" in arg_sub.id.lower():
                                    tiene_jsonl_append = True
                    fn_llamada = _nombre_base(sub.func)
                    if fn_llamada.startswith(("_verificar_", "_check_", "guard_", "assert_")):
                        guard_calls.add(fn_llamada)
                elif isinstance(sub, ast.keyword) and sub.arg == "start_new_session":
                    if isinstance(sub.value, ast.Constant) and sub.value.value is True:
                        tiene_aislamiento = True

            if len(guard_calls) >= 3:
                agregar(
                    "chain-of-responsibility",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    f"Cadena secuencial de {len(guard_calls)} guardas antes de ejecutar la operacion",
                )
            if tiene_os_replace:
                agregar(
                    "atomic-write",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Escritura atomica mediante reemplazo `os.replace`",
                )
            if tiene_aislamiento:
                agregar(
                    "process-isolation-sandbox",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Aislamiento de arbol de subprocesos (Job Object / subreaper / sesion nueva)",
                )
            if tiene_jsonl_append and (
                "change_log" in rel_posix
                or "event" in rel_posix
                or "bitacora" in rel_posix
                or "escritura" in rel_posix
                or "log" in fname.lower()
                or "append" in fname.lower()
                or "anexar" in fname.lower()
            ):
                agregar(
                    "append-only-event-log",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Anexado incremental en modo append sobre log de eventos",
                )


def _detectar_generico(
    texto: str,
    rel_posix: str,
    hallazgos: Dict[str, List[Dict[str, Any]]],
) -> None:
    lineas = texto.splitlines()
    for idx, linea in enumerate(lineas, start=1):
        for pid, patron_re, confianza, como in _REGLAS_GENERICAS:
            m = patron_re.search(linea)
            if not m:
                continue
            simbolo = next((g for g in m.groups() if g), m.group(0).strip())
            hallazgos.setdefault(pid, []).append({
                "file": rel_posix,
                "line": idx,
                "symbol": simbolo,
                "confidence": confianza,
                "how": como,
            })


def _iterar_fuentes(objetivo: Path, incluir_tests: bool = False) -> Iterable[Tuple[Path, str]]:
    if objetivo.is_file():
        if objetivo.suffix.lower() in _EXTENSIONES_SOPORTADAS:
            yield objetivo, objetivo.name
        return

    omitidos = _DIRECTORIOS_OMITIDOS - ({rutas.TESTS, "test", "__tests__"} if incluir_tests else set())
    for actual, dirs, archivos in os.walk(objetivo):
        dirs[:] = sorted(d for d in dirs if d not in omitidos and not d.startswith(".git"))
        base = Path(actual)
        for nombre in sorted(archivos):
            ruta = base / nombre
            if ruta.suffix.lower() not in _EXTENSIONES_SOPORTADAS:
                continue
            rel = ruta.relative_to(objetivo).as_posix()
            yield ruta, rel


def detectar_patrones(
    objetivo: Path,
    *,
    categoria: Optional[str] = None,
    registrados: Optional[Set[str]] = None,
    incluir_tests: bool = False,
) -> Dict[str, Any]:
    """Escanea un archivo o repositorio (interno o externo) y devuelve patrones categorizados.

    Nunca devuelve rutas absolutas de maquina en la evidencia; solo rutas POSIX
    relativas a `objetivo`. Si un archivo no contiene patrones verificables,
    devuelve 0 hallazgos (AP-45).
    """
    if categoria is not None and categoria not in ETIQUETAS_CATEGORIA:
        raise ValueError(f"Categoria invalida: {categoria}. Validas: {list(CATEGORIAS)}")

    ruta = Path(objetivo).resolve()
    if not ruta.exists():
        raise FileNotFoundError(f"La ruta a escanear no existe: {objetivo}")

    hallazgos: Dict[str, List[Dict[str, Any]]] = {}
    files_scanned = 0
    skipped_files: List[Dict[str, str]] = []

    for archivo, rel_posix in _iterar_fuentes(ruta, incluir_tests=incluir_tests):
        try:
            if archivo.stat().st_size > _MAX_BYTES_ARCHIVO:
                skipped_files.append({"file": rel_posix, "reason": "exceeds_size_limit"})
                continue
            texto = archivo.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            skipped_files.append({"file": rel_posix, "reason": f"read_error: {type(exc).__name__}"})
            continue

        files_scanned += 1
        ext = archivo.suffix.lower()
        if ext in _EXTENSIONES_PYTHON:
            try:
                arbol = ast.parse(texto)
            except SyntaxError:
                skipped_files.append({"file": rel_posix, "reason": "syntax_error"})
                continue
            _detectar_python(arbol, rel_posix, hallazgos)
        else:
            _detectar_generico(texto, rel_posix, hallazgos)

    reg_norm = {normalizar_nombre_patron(r) for r in (registrados or set())}
    cats = (categoria,) if categoria else CATEGORIAS
    grupos: List[Dict[str, Any]] = []
    planos: List[Dict[str, Any]] = []
    total_evidencias = 0

    for cat in cats:
        detectados_cat: List[Dict[str, Any]] = []
        for meta in CATALOGO_PATRONES:
            if meta["category"] != cat:
                continue
            evidencias = hallazgos.get(meta["id"], [])
            if not evidencias:
                continue
            # Deduplicar por (file, line, symbol) y ordenar deterministicamente
            unicas_map: Dict[Tuple[str, int, str], Dict[str, Any]] = {}
            for ev in evidencias:
                clave = (ev["file"], ev["line"], ev["symbol"])
                if clave not in unicas_map:
                    unicas_map[clave] = ev
            evidencias_ord = [unicas_map[k] for k in sorted(unicas_map)]
            archivos_unicos = sorted({e["file"] for e in evidencias_ord})
            confianza = (
                "evidencia_fuerte"
                if any(e["confidence"] == "evidencia_fuerte" for e in evidencias_ord)
                else "indicio_estructural"
            )
            estado_vault = (
                "registrado"
                if normalizar_nombre_patron(meta["name"]) in reg_norm
                or meta["id"] in reg_norm
                else "nuevo"
            )
            entrada = {
                "id": meta["id"],
                "order": meta["order"],
                "pattern": meta["name"],
                "category": meta["category"],
                "category_label": ETIQUETAS_CATEGORIA[meta["category"]],
                "type": meta["pattern_type"],
                "confidence": confianza,
                "vault_status": estado_vault,
                "summary": meta["summary"],
                "files": archivos_unicos,
                "evidence_total": len(evidencias_ord),
                "evidence": evidencias_ord[:_MAX_EVIDENCIAS_POR_PATRON],
            }
            total_evidencias += len(evidencias_ord)
            detectados_cat.append(entrada)
            planos.append(entrada)

        grupos.append({
            "category": cat,
            "label": ETIQUETAS_CATEGORIA[cat],
            "count": len(detectados_cat),
            "patterns": detectados_cat,
        })

    return {
        "ok": True,
        "mode": "detect",
        "target_name": ruta.name,
        "files_scanned": files_scanned,
        "total_patterns": len(planos),
        "total_evidences": total_evidencias,
        "categories": grupos,
        "patterns": planos,
        "skipped_files": skipped_files,
    }
