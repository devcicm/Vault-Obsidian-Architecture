"""Detector determinista de patrones de diseno y arquitectura (interno y externo).

Hoja pura en el nucleo (`vault.kernel`, reexportada en `vault.autoria.patrones_diseno`) para:
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
        "official_name": "Bounded Context (Domain-Driven Design)",
        "reference": "Evans (DDD, 2003)",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Delimita contextos de dominio explicitos con lenguaje ubicuo y presupuesto de cruces.",
    },
    {
        "id": "hexagonal-ports-adapters",
        "order": "1.2",
        "name": "Hexagonal / Ports & Adapters",
        "official_name": "Hexagonal Architecture (Ports and Adapters)",
        "reference": "Cockburn (2005)",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Desacopla el dominio de los adaptadores externos mediante puertos explicitos.",
    },
    {
        "id": "cqrs",
        "order": "1.3",
        "name": "CQRS",
        "official_name": "Command Query Responsibility Segregation (CQRS)",
        "reference": "Young / Fowler (2011)",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Separa operaciones de lectura/consulta (paralelizables) de comandos de escritura (serializados por recurso).",
    },
    {
        "id": "append-only-event-log",
        "order": "1.4",
        "name": "Append-Only Event Log",
        "official_name": "Append-Only Event Log",
        "reference": "Kreps (2013) / Fowler",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Registra mutaciones en un log de solo anexado (p. ej. JSONL) para auditoria y reconstruccion en O(1).",
    },
    {
        "id": "single-source-of-truth-registry",
        "order": "1.5",
        "name": "Single Source of Truth / Registry",
        "official_name": "Registry (Single Source of Truth)",
        "reference": "Fowler (PoEAA, 2002)",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Centraliza catalogos y contratos en un registro canonico del que se derivan artefactos.",
    },
    {
        "id": "composition-root",
        "order": "1.6",
        "name": "Composition Root",
        "official_name": "Composition Root",
        "reference": "Seemann (Dependency Injection, 2011)",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Concentra el ensamblaje de contexto, repositorios y adaptadores en un punto unico.",
    },
    {
        "id": "layered-architecture",
        "order": "1.7",
        "name": "Layered Architecture (N-Tier)",
        "official_name": "Layered Architecture (N-Tier)",
        "reference": "Richards & Ford (2020)",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Organiza responsabilidades en capas horizontales explicitas (presentacion, aplicacion/servicios, dominio, datos).",
    },
    {
        "id": "clean-architecture",
        "order": "1.8",
        "name": "Clean Architecture",
        "official_name": "Clean Architecture",
        "reference": "R. C. Martin (2017)",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Aisla entidades y casos de uso del nucleo de negocio respecto a adaptadores de interfaz y frameworks.",
    },
    {
        "id": "event-driven-architecture",
        "order": "1.9",
        "name": "Event-Driven Architecture (EDA)",
        "official_name": "Event-Driven Architecture (EDA)",
        "reference": "Richards & Ford (2020) / Hohpe & Woolf (EIP, 2003)",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Coordina componentes desacoplados mediante produccion, enrutamiento y consumo de eventos asincronos.",
    },
    {
        "id": "microkernel-plugin",
        "order": "1.10",
        "name": "Microkernel / Plug-in Architecture",
        "official_name": "Microkernel Architecture (Plug-in)",
        "reference": "Buschmann et al. (POSA, 1996) / Richards & Ford (2020)",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Mantiene un nucleo minimo extensible mediante registro dinamico de plugins o entry points.",
    },
    {
        "id": "pipe-and-filter",
        "order": "1.11",
        "name": "Pipe-and-Filter",
        "official_name": "Pipes and Filters",
        "reference": "Buschmann et al. (POSA, 1996) / Hohpe & Woolf (EIP, 2003)",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Procesa flujos de datos a traves de etapas o filtros componibles y desacoplados.",
    },
    {
        "id": "event-sourcing",
        "order": "1.12",
        "name": "Event Sourcing",
        "official_name": "Event Sourcing",
        "reference": "Fowler (2005) / Kleppmann (DDIA, 2017)",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Persiste el estado de dominio como secuencia inmutable de eventos en vez de sobrescribir solo el estado actual.",
    },
    {
        "id": "transactional-outbox",
        "order": "1.13",
        "name": "Transactional Outbox",
        "official_name": "Transactional Outbox",
        "reference": "Richardson (Microservices Patterns, 2018) / Hohpe & Woolf (EIP)",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Registra estado y evento saliente en la misma transaccion atomica antes de publicarlo a un broker externo.",
    },
    {
        "id": "dag-workflow-orchestration",
        "order": "1.14",
        "name": "Workflow / DAG Orchestration",
        "official_name": "Directed Acyclic Graph (DAG) Workflow Orchestration",
        "reference": "Hohpe & Woolf (EIP, 2003) / Modern Workflow Engines",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Modela flujos de trabajo como grafo aciclico dirigido de tareas con dependencias explicitas y ejecucion paralelizable.",
    },
    {
        "id": "modular-monolith",
        "order": "1.15",
        "name": "Modular Monolith",
        "official_name": "Modular Monolith",
        "reference": "Richards & Ford (2020) / Newman (2021)",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Despliega una unidad unica particionada en modulos fuertemente encapsulados con contratos publicos explicitos.",
    },
    {
        "id": "microservices-architecture",
        "order": "1.16",
        "name": "Microservices Architecture",
        "official_name": "Microservices Architecture",
        "reference": "Newman (2015) / Richardson (2018)",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Descompone el sistema en servicios autonomos desplegables de forma independiente con propiedad aislada de datos.",
    },
    {
        "id": "strangler-fig",
        "order": "1.17",
        "name": "Strangler Fig",
        "official_name": "Strangler Fig Application",
        "reference": "Fowler (2004) / Newman (2019)",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Sustituye gradualmente un sistema heredado interceptando rutas hacia componentes nuevos sin reescritura total.",
    },
    {
        "id": "backend-for-frontend",
        "order": "1.18",
        "name": "Backend for Frontend (BFF)",
        "official_name": "Backends for Frontends (BFF)",
        "reference": "Newman (2015)",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Expone una fachada backend dedicada por tipo de cliente que agrega llamadas y adapta contratos.",
    },
    {
        "id": "sidecar-ambassador",
        "order": "1.19",
        "name": "Sidecar / Ambassador",
        "official_name": "Sidecar / Ambassador Pattern",
        "reference": "Burns (Designing Distributed Systems, 2018)",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Adjunta un proceso o contenedor auxiliar para red, seguridad u observabilidad sin contaminar la logica principal.",
    },
    {
        "id": "anti-corruption-layer",
        "order": "1.20",
        "name": "Anti-Corruption Layer (ACL)",
        "official_name": "Anti-Corruption Layer (DDD)",
        "reference": "Evans (DDD, 2003)",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Aisla el modelo del dominio frente a contratos o semanticas heredadas de sistemas externos mediante una capa traductora.",
    },
    {
        "id": "identity-access-management",
        "order": "1.21",
        "name": "Identity & Access Management (IAM / RBAC / ABAC)",
        "official_name": "Identity & Access Management (Federated Identity / RBAC / ABAC)",
        "reference": "NIST SP 800-63 / Sandhu (RBAC, 1996) / OAuth 2.0 & OIDC (RFC 6749)",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Establece identidad verificable (Principal/Claims) y autorizacion fail-closed por roles o atributos entre fronteras de confianza.",
    },
    {
        "id": "multi-tenancy-isolation",
        "order": "1.22",
        "name": "Multi-Tenancy & Tenant Isolation",
        "official_name": "Multi-Tenancy Architecture (Silo / Bridge / Pool Isolation)",
        "reference": "Chong & Carraro (Microsoft, 2006) / AWS SaaS Lens",
        "category": "arquitectonicos",
        "pattern_type": "architecture",
        "summary": "Aisla datos, identidad y politicas por tenant mediante silo fisico, esquema dedicado o pool con filtro obligatorio de tenant_id/RLS.",
    },
    # 2. Creacionales
    {
        "id": "builder",
        "order": "2.1",
        "name": "Builder",
        "official_name": "Builder",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "creacionales",
        "pattern_type": "design",
        "summary": "Construye objetos o documentos complejos paso a paso antes de renderizarlos o validarlos.",
    },
    {
        "id": "factory",
        "order": "2.2",
        "name": "Factory",
        "official_name": "Factory Method / Abstract Factory",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "creacionales",
        "pattern_type": "design",
        "summary": "Encapsula la creacion parametrizada de instancias o validadores reutilizables.",
    },
    {
        "id": "singleton-module-cache",
        "order": "2.3",
        "name": "Singleton / Module-Scoped Cache",
        "official_name": "Singleton",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "creacionales",
        "pattern_type": "design",
        "summary": "Mantiene una instancia o cache unica por proceso para evitar trabajo repetido.",
    },
    {
        "id": "dependency-injection",
        "order": "2.4",
        "name": "Dependency Injection (DI)",
        "official_name": "Dependency Injection (Inversion of Control)",
        "reference": "Fowler (2004) / Seemann (2011)",
        "category": "creacionales",
        "pattern_type": "design",
        "summary": "Inyecta colaboradores desde fuera via contenedor, anotacion o fabrica en vez de instanciarlos internamente.",
    },
    {
        "id": "prototype",
        "order": "2.5",
        "name": "Prototype",
        "official_name": "Prototype",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "creacionales",
        "pattern_type": "design",
        "summary": "Crea nuevas instancias clonando un objeto prototipo existente en lugar de reconstruirlo desde cero.",
    },
    {
        "id": "object-pool",
        "order": "2.6",
        "name": "Object Pool",
        "official_name": "Object Pool / Pooling",
        "reference": "Kircher & Jain (POSA3, 2004)",
        "category": "creacionales",
        "pattern_type": "design",
        "summary": "Reutiliza un conjunto acotado de recursos costosos (conexiones, workers, buffers) evitando crear y destruir en cada uso.",
    },
    {
        "id": "abstract-factory",
        "order": "2.7",
        "name": "Abstract Factory",
        "official_name": "Abstract Factory",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "creacionales",
        "pattern_type": "design",
        "summary": "Expone una interfaz para crear familias completas de objetos relacionados sin acoplar a clases concretas.",
    },
    {
        "id": "lazy-initialization",
        "order": "2.8",
        "name": "Lazy Initialization",
        "official_name": "Lazy Initialization",
        "reference": "Fowler (PoEAA, 2002) / POSA3",
        "category": "creacionales",
        "pattern_type": "design",
        "summary": "Difiere la creacion o calculo de un objeto costoso hasta el momento en que realmente se solicita.",
    },
    # 3. Estructurales
    {
        "id": "repository",
        "order": "3.1",
        "name": "Repository",
        "official_name": "Repository",
        "reference": "Fowler (PoEAA, 2002) / Evans (DDD, 2003)",
        "category": "estructurales",
        "pattern_type": "design",
        "summary": "Encapsula el acceso a persistencia, rutas o colecciones tras una frontera de dominio.",
    },
    {
        "id": "adapter",
        "order": "3.2",
        "name": "Adapter",
        "official_name": "Adapter",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "estructurales",
        "pattern_type": "design",
        "summary": "Traduce la interfaz de un modulo o proveedor externo al contrato esperado por el dominio.",
    },
    {
        "id": "module-alias-facade",
        "order": "3.3",
        "name": "Module Alias / Facade",
        "official_name": "Facade",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "estructurales",
        "pattern_type": "design",
        "summary": "Expone una fachada simplificada o alias de compatibilidad sobre modulos internos.",
    },
    {
        "id": "proxy-lazy-export",
        "order": "3.4",
        "name": "Proxy (Lazy Export)",
        "official_name": "Proxy (Virtual / Lazy Proxy)",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "estructurales",
        "pattern_type": "design",
        "summary": "Controla o difiere el acceso y la carga de un recurso hasta su uso efectivo.",
    },
    {
        "id": "decorator",
        "order": "3.5",
        "name": "Decorator",
        "official_name": "Decorator",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "estructurales",
        "pattern_type": "design",
        "summary": "Anade responsabilidades dinamicamente envolviendo componentes o funciones sin alterar su interfaz.",
    },
    {
        "id": "bridge",
        "order": "3.6",
        "name": "Bridge",
        "official_name": "Bridge",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "estructurales",
        "pattern_type": "design",
        "summary": "Desacopla una abstraccion de su implementacion para que ambas evolucionen de forma independiente.",
    },
    {
        "id": "composite",
        "order": "3.7",
        "name": "Composite",
        "official_name": "Composite",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "estructurales",
        "pattern_type": "design",
        "summary": "Compone objetos en arboles jerarquicos permitiendo tratar elementos individuales y compuestos de manera uniforme.",
    },
    {
        "id": "flyweight",
        "order": "3.8",
        "name": "Flyweight",
        "official_name": "Flyweight",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "estructurales",
        "pattern_type": "design",
        "summary": "Comparte estado intrinseco inmutable entre multiples instancias ligeras para minimizar uso de memoria.",
    },
    {
        "id": "data-transfer-object",
        "order": "3.9",
        "name": "Data Transfer Object (DTO)",
        "official_name": "Data Transfer Object (DTO)",
        "reference": "Fowler (PoEAA, 2002)",
        "category": "estructurales",
        "pattern_type": "design",
        "summary": "Transporta datos serializables entre fronteras de capa o proceso sin exponer entidades ni logica interna.",
    },
    {
        "id": "gateway-data-mapper",
        "order": "3.10",
        "name": "Gateway / Data Mapper",
        "official_name": "Gateway / Data Mapper",
        "reference": "Fowler (PoEAA, 2002)",
        "category": "estructurales",
        "pattern_type": "design",
        "summary": "Encapsula llamadas a recursos externos o traduce bidireccionalmente entre objetos de dominio y persistencia.",
    },
    # 4. Comportamiento
    {
        "id": "template-method",
        "order": "4.1",
        "name": "Template Method",
        "official_name": "Template Method",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Define el esqueleto invariante de un flujo y delega pasos variables a subclases.",
    },
    {
        "id": "chain-of-responsibility",
        "order": "4.2",
        "name": "Chain of Responsibility",
        "official_name": "Chain of Responsibility",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Encadena manejadores o guardas secuenciales que validan o procesan una solicitud.",
    },
    {
        "id": "state-machine",
        "order": "4.3",
        "name": "State Machine",
        "official_name": "State (Finite State Machine)",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Gobierna transiciones explicitas entre estados validos rechazando saltos ilegales.",
    },
    {
        "id": "strategy",
        "order": "4.4",
        "name": "Strategy",
        "official_name": "Strategy",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Permite intercambiar algoritmos o politicas en tiempo de ejecucion via tabla o protocolo.",
    },
    {
        "id": "command-dispatch-router",
        "order": "4.5",
        "name": "Command + Dispatch Router",
        "official_name": "Command",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Encapsula invocaciones como comandos y las despacha declarativamente por ruta o accion.",
    },
    {
        "id": "envelope-result-object",
        "order": "4.6",
        "name": "Envelope / Result Object",
        "official_name": "Notification / Result Object",
        "reference": "Fowler (2014)",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Estandariza respuestas y errores estructurados con codigo, categoria y recuperacion.",
    },
    {
        "id": "observer-event-bus",
        "order": "4.7",
        "name": "Observer / Event Bus",
        "official_name": "Observer / Publish-Subscribe Channel",
        "reference": "GoF (Gamma et al., 1994) / Hohpe & Woolf (EIP, 2003)",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Notifica eventos a suscriptores desacoplados sin acoplar emisor y oyentes.",
    },
    {
        "id": "specification",
        "order": "4.8",
        "name": "Specification",
        "official_name": "Specification",
        "reference": "Evans (DDD, 2003) / Fowler",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Encapsula reglas de negocio booleanas componibles y reutilizables (`is_satisfied_by`).",
    },
    {
        "id": "unit-of-work",
        "order": "4.9",
        "name": "Unit of Work",
        "official_name": "Unit of Work",
        "reference": "Fowler (PoEAA, 2002)",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Agrupa cambios en una unidad transaccional o lote atomico con commit y rollback coordinados.",
    },
    {
        "id": "iterator",
        "order": "4.10",
        "name": "Iterator",
        "official_name": "Iterator",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Recorre secuencialmente elementos de una coleccion o stream sin exponer su representacion interna.",
    },
    {
        "id": "mediator",
        "order": "4.11",
        "name": "Mediator",
        "official_name": "Mediator",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Centraliza interacciones complejas entre multiples componentes reduciendo acoplamiento muchos-a-muchos.",
    },
    {
        "id": "visitor",
        "order": "4.12",
        "name": "Visitor",
        "official_name": "Visitor",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Separa operaciones nuevas sobre estructuras de nodos (p. ej. AST o grafos) sin alterar las clases visitadas.",
    },
    {
        "id": "interpreter",
        "order": "4.13",
        "name": "Interpreter",
        "official_name": "Interpreter",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Define una gramatica o DSL y evalua expresiones mediante nodos ejecutables componibles.",
    },
    {
        "id": "memento",
        "order": "4.14",
        "name": "Memento",
        "official_name": "Memento",
        "reference": "GoF (Gamma et al., 1994)",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Captura y restaura el estado interno de un objeto sin romper su encapsulamiento.",
    },
    {
        "id": "null-object",
        "order": "4.15",
        "name": "Null Object",
        "official_name": "Null Object",
        "reference": "Woolf (PLoPD3, 1997) / Fowler (Refactoring)",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Sustituye referencias nulas por una implementacion inofensiva que evita condicionales repetitivos.",
    },
    {
        "id": "policy-rule-engine",
        "order": "4.16",
        "name": "Policy / Rule Engine",
        "official_name": "Policy / Rules Engine Pattern",
        "reference": "Evans (DDD, 2003) / Fowler",
        "category": "comportamiento",
        "pattern_type": "design",
        "summary": "Evalua politicas y reglas de decision declarativas separadas del flujo de control principal.",
    },
    # 5. Concurrencia y Resiliencia
    {
        "id": "atomic-write",
        "order": "5.1",
        "name": "Atomic Write",
        "official_name": "Atomic File Replacement (Write-Temp-Rename)",
        "reference": "POSIX / Systems Reliability",
        "category": "concurrencia_resiliencia",
        "pattern_type": "code",
        "summary": "Escribe a archivo temporal y reemplaza atomicamente para evitar lecturas parciales.",
    },
    {
        "id": "reentrant-cross-process-lock",
        "order": "5.2",
        "name": "Reentrant & Cross-Process Lock",
        "official_name": "Monitor / Reentrant & Distributed Lock",
        "reference": "Schmidt et al. (POSA2, 2000)",
        "category": "concurrencia_resiliencia",
        "pattern_type": "code",
        "summary": "Serializa secciones criticas entre hilos o procesos mediante locks explicitos.",
    },
    {
        "id": "process-isolation-sandbox",
        "order": "5.3",
        "name": "Process Isolation / Sandbox",
        "official_name": "Bulkhead / Process Isolation",
        "reference": "Nygard (Release It!, 2007)",
        "category": "concurrencia_resiliencia",
        "pattern_type": "code",
        "summary": "Aisla subprocesos (Job Object / subreaper / sesion nueva) para contener timeouts y fallos.",
    },
    {
        "id": "snapshot-quarantine-rollback",
        "order": "5.4",
        "name": "Snapshot, Quarantine & Rollback",
        "official_name": "Memento / Compensating Rollback",
        "reference": "GoF (Gamma et al., 1994) / Nygard (2007)",
        "category": "concurrencia_resiliencia",
        "pattern_type": "code",
        "summary": "Resguarda instantaneas o cuarentena antes de mutaciones destructivas para garantizar vuelta atras.",
    },
    {
        "id": "wave-resource-scheduler",
        "order": "5.5",
        "name": "Wave / Resource-Based Scheduler",
        "official_name": "Scheduler / Resource-Partitioned Concurrency",
        "reference": "Lea (Concurrent Programming) / Schmidt (POSA2)",
        "category": "concurrencia_resiliencia",
        "pattern_type": "code",
        "summary": "Planifica ejecuciones paralelas en olas o colas respetando conflictos de recursos.",
    },
    {
        "id": "circuit-breaker-retry",
        "order": "5.6",
        "name": "Circuit Breaker & Retry with Backoff",
        "official_name": "Circuit Breaker & Retry with Exponential Backoff",
        "reference": "Nygard (Release It!, 2007)",
        "category": "concurrencia_resiliencia",
        "pattern_type": "code",
        "summary": "Corta cascadas de fallos hacia dependencias inestables y reintenta con espera exponencial acotada.",
    },
    {
        "id": "dispose-raii",
        "order": "5.7",
        "name": "Dispose / RAII",
        "official_name": "Dispose Pattern / Resource Acquisition Is Initialization (RAII)",
        "reference": "Stroustrup (RAII) / .NET IDisposable / Python PEP 343",
        "category": "concurrencia_resiliencia",
        "pattern_type": "code",
        "summary": "Garantiza liberacion determinista e idempotente de recursos (locks, sockets, archivos, timers, subprocesos) al salir del ambito o ante fallo.",
    },
    {
        "id": "acid-transactions",
        "order": "5.8",
        "name": "ACID Transactions",
        "official_name": "ACID Transaction (Atomicity, Consistency, Isolation, Durability)",
        "reference": "Haerder & Reuter (1983) / Gray & Reuter (1993) / Kleppmann (DDIA, 2017)",
        "category": "concurrencia_resiliencia",
        "pattern_type": "code",
        "summary": "Garantiza atomicidad, consistencia, aislamiento y durabilidad en mutaciones compuestas evitando estados parciales corruptos.",
    },
    {
        "id": "saga-compensation",
        "order": "5.9",
        "name": "Saga / Compensating Transaction",
        "official_name": "Saga Pattern (Compensating Transactions)",
        "reference": "Garcia-Molina & Salem (1987) / Richardson (2018)",
        "category": "concurrencia_resiliencia",
        "pattern_type": "code",
        "summary": "Coordina operaciones largas o distribuidas como secuencia de pasos locales con compensacion explicita ante fallo.",
    },
    {
        "id": "durable-execution-checkpoint-replay",
        "order": "5.10",
        "name": "Durable Execution / Checkpoint & Replay",
        "official_name": "Durable Execution (Checkpoint & Deterministic Replay)",
        "reference": "Kleppmann (DDIA, 2017) / Temporal Durable Execution",
        "category": "concurrencia_resiliencia",
        "pattern_type": "code",
        "summary": "Persiste checkpoints deterministas del progreso para reanudar o reproducir flujos interrumpidos sin repetir efectos secundarios.",
    },
    {
        "id": "idempotent-consumer",
        "order": "5.11",
        "name": "Idempotent Receiver / Consumer",
        "official_name": "Idempotent Receiver / Consumer",
        "reference": "Hohpe & Woolf (EIP, 2003) / Richardson (2018)",
        "category": "concurrencia_resiliencia",
        "pattern_type": "code",
        "summary": "Deduplica comandos o eventos repetidos mediante clave de idempotencia para tolerar reintentos seguros.",
    },
    {
        "id": "heartbeat-lease",
        "order": "5.12",
        "name": "Heartbeat & Lease",
        "official_name": "Heartbeat & Time-Bounded Lease",
        "reference": "Gray & Cheriton (1989) / Kleppmann (DDIA, 2017)",
        "category": "concurrencia_resiliencia",
        "pattern_type": "code",
        "summary": "Mantiene concesiones temporales renovadas por latidos periodicos para detectar caidas y liberar bloqueos huerfanos.",
    },
    {
        "id": "timeout-deadline-propagation",
        "order": "5.13",
        "name": "Timeout & Deadline Propagation",
        "official_name": "Timeout & Deadline Propagation",
        "reference": "Nygard (Release It!, 2007) / Beyer et al. (Google SRE, 2016)",
        "category": "concurrencia_resiliencia",
        "pattern_type": "code",
        "summary": "Impone limites explicitos de espera y propaga el presupuesto de tiempo restante a cada llamada descendente.",
    },
    {
        "id": "rate-limiter-throttling",
        "order": "5.14",
        "name": "Rate Limiter / Throttling",
        "official_name": "Rate Limiting / Throttling (Token Bucket / Sliding Window)",
        "reference": "Nygard (Release It!, 2007) / Microsoft Cloud Design Patterns",
        "category": "concurrencia_resiliencia",
        "pattern_type": "code",
        "summary": "Limita la tasa de solicitudes para proteger servicios, cuotas y recursos compartidos frente a picos de trafico.",
    },
    {
        "id": "backpressure",
        "order": "5.15",
        "name": "Backpressure / Bounded Queue",
        "official_name": "Backpressure / Bounded Queue",
        "reference": "Nygard (Release It!, 2007) / Reactive Systems",
        "category": "concurrencia_resiliencia",
        "pattern_type": "code",
        "summary": "Acota colas intermedias y frena productores cuando los consumidores se saturan para evitar agotamiento de memoria.",
    },
    {
        "id": "graceful-shutdown",
        "order": "5.16",
        "name": "Graceful Shutdown & Draining",
        "official_name": "Graceful Shutdown (Signal Handling & Draining)",
        "reference": "Nygard (Release It!, 2007) / POSIX Signal Handling",
        "category": "concurrencia_resiliencia",
        "pattern_type": "code",
        "summary": "Intercepta SIGTERM/SIGINT, deja de aceptar trabajo nuevo, drena operaciones en curso y ejecuta dispose ordenado antes de salir.",
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
        re.compile(r"\bclass\s+([A-Za-z0-9_]*(?:CommandHandler|QueryHandler|CommandBus|QueryBus|RWCoordinator))\b"),
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
        re.compile(r"\bfunction\s+(buildError|emitError|buildEnvelope|createResult)\s*\("),
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
        re.compile(r"\bclass\s+([A-Za-z0-9_]*(?:Scheduler|RWCoordinator))\b"),
        "evidencia_fuerte",
        "Planificador o coordinador concurrente por tipo de acceso",
    ),
    (
        "event-driven-architecture",
        re.compile(r"\b(?:class|interface)\s+([A-Za-z0-9_]*(?:EventBroker|MessageBroker|EventHandler|EventConsumer))\b"),
        "evidencia_fuerte",
        "Componente broker/consumidor explicito de arquitectura dirigida por eventos",
    ),
    (
        "microkernel-plugin",
        re.compile(r"\b(?:class\s+([A-Za-z0-9_]*PluginRegistry)|(?:function|const)\s+(registerPlugin|loadPlugins))\b"),
        "evidencia_fuerte",
        "Registro o carga dinamica de plugins estilo Microkernel",
    ),
    (
        "pipe-and-filter",
        re.compile(r"\b(?:class|interface)\s+([A-Za-z0-9_]*(?:Pipe|Filter|PipelineStage))\b"),
        "evidencia_fuerte",
        "Etapa o filtro componible de arquitectura Pipe-and-Filter",
    ),
    (
        "dependency-injection",
        re.compile(r"\b(?:class\s+([A-Za-z0-9_]*(?:DIContainer|ServiceContainer|Injector))|@(Injectable|Inject)\b)"),
        "evidencia_fuerte",
        "Contenedor o decorador explicito de Dependency Injection",
    ),
    (
        "decorator",
        re.compile(r"\bclass\s+([A-Za-z0-9_]*Decorator)\b"),
        "evidencia_fuerte",
        "Clase Decorator que envuelve otro componente preservando su interfaz",
    ),
    (
        "specification",
        re.compile(r"\b(?:class\s+([A-Za-z0-9_]*Specification)|\b(isSatisfiedBy)\s*\()"),
        "evidencia_fuerte",
        "Regla de dominio componible estilo Specification",
    ),
    (
        "unit-of-work",
        re.compile(r"\b(?:class|interface)\s+([A-Za-z0-9_]*UnitOfWork)\b"),
        "evidencia_fuerte",
        "Coordinador transaccional Unit of Work",
    ),
    (
        "circuit-breaker-retry",
        re.compile(r"\b(?:class\s+([A-Za-z0-9_]*CircuitBreaker)|(?:function|const)\s+(retryWithBackoff|exponentialBackoff))\b"),
        "evidencia_fuerte",
        "Mecanismo de resiliencia Circuit Breaker o retry con backoff exponencial",
    ),
    (
        "dispose-raii",
        re.compile(r"\b(?:implements\s+(?:IDisposable|IAsyncDisposable|Disposable)|Symbol\.(?:dispose|asyncDispose)|\busing\s+(?:const|var)\s+([A-Za-z0-9_]+)|(?:async\s+)?(dispose|asyncDispose)\s*\(\s*\))"),
        "evidencia_fuerte",
        "Patron Dispose / RAII para liberacion determinista de recursos",
    ),
    (
        "acid-transactions",
        re.compile(r"\b(?:class|interface)\s+([A-Za-z0-9_]*(?:TransactionManager|AcidTransaction))|\b(beginTransaction|IsolationLevel)\b"),
        "evidencia_fuerte",
        "Gestor o contrato explicito de transacciones ACID",
    ),
    (
        "saga-compensation",
        re.compile(r"\b(?:class|interface)\s+([A-Za-z0-9_]*(?:SagaOrchestrator|SagaCoordinator|CompensatingAction|SagaStep))\b"),
        "evidencia_fuerte",
        "Orquestador o paso compensatorio del patron Saga",
    ),
    (
        "durable-execution-checkpoint-replay",
        re.compile(r"\b(?:class|interface)\s+([A-Za-z0-9_]*(?:CheckpointStore|WorkflowCheckpoint|ReplayEngine|DurableExecutor))|\b(saveCheckpoint|replayEvents)\s*\("),
        "evidencia_fuerte",
        "Persistencia de checkpoints y replay determinista (Durable Execution)",
    ),
    (
        "dag-workflow-orchestration",
        re.compile(r"\b(?:class|interface)\s+([A-Za-z0-9_]*(?:WorkflowDAG|TaskGraph|DagExecutor|WorkflowEngine|WorkflowOrchestrator))\b"),
        "evidencia_fuerte",
        "Motor u orquestador de flujo de trabajo modelado como DAG",
    ),
    (
        "heartbeat-lease",
        re.compile(r"\b(?:class|interface)\s+([A-Za-z0-9_]*(?:LeaseManager|HeartbeatMonitor))|\b(renewLease|sendHeartbeat)\s*\("),
        "evidencia_fuerte",
        "Gestion de concesiones temporales (Lease) renovadas por Heartbeat",
    ),
    (
        "graceful-shutdown",
        re.compile(r"\b(?:class\s+([A-Za-z0-9_]*(?:GracefulShutdown|ShutdownCoordinator))|process\.on\(\s*['\"](SIGTERM|SIGINT)['\"])"),
        "evidencia_fuerte",
        "Manejo de senales SIGTERM/SIGINT y drenaje ordenado (Graceful Shutdown)",
    ),
    (
        "transactional-outbox",
        re.compile(r"\b(?:class|interface)\s+([A-Za-z0-9_]*(?:OutboxRepository|OutboxRelay|OutboxPublisher|TransactionalOutbox))\b"),
        "evidencia_fuerte",
        "Implementacion explicita del patron Transactional Outbox",
    ),
    (
        "event-sourcing",
        re.compile(r"\b(?:class|interface)\s+([A-Za-z0-9_]*(?:EventStore|EventSourcedAggregate|AggregateRoot))\b"),
        "evidencia_fuerte",
        "Almacen o agregado reconstruido mediante Event Sourcing",
    ),
    (
        "anti-corruption-layer",
        re.compile(r"\b(?:class|interface)\s+([A-Za-z0-9_]*(?:AntiCorruptionLayer|ACLTranslator))\b"),
        "evidencia_fuerte",
        "Capa traductora Anti-Corruption Layer (DDD)",
    ),
    (
        "idempotent-consumer",
        re.compile(r"\b(?:class|interface)\s+([A-Za-z0-9_]*(?:IdempotentConsumer|IdempotencyStore|IdempotencyGuard))\b"),
        "evidencia_fuerte",
        "Deduplicacion de comandos o eventos mediante Idempotent Consumer",
    ),
    (
        "rate-limiter-throttling",
        re.compile(r"\b(?:class|interface)\s+([A-Za-z0-9_]*(?:RateLimiter|TokenBucket|LeakyBucket|SlidingWindowLimiter))\b"),
        "evidencia_fuerte",
        "Limitador de tasa (Rate Limiter / Throttling)",
    ),
    (
        "backpressure",
        re.compile(r"\b(?:class|interface)\s+([A-Za-z0-9_]*(?:BoundedQueue|BackpressureController))\b"),
        "evidencia_fuerte",
        "Cola acotada o control explicito de Backpressure",
    ),
    (
        "timeout-deadline-propagation",
        re.compile(r"\b(?:class\s+([A-Za-z0-9_]*DeadlineContext)|context\.(WithDeadline|WithTimeout)\s*\()"),
        "evidencia_fuerte",
        "Propagacion explicita de timeout o deadline entre llamadas",
    ),
    (
        "object-pool",
        re.compile(r"\b(?:class|struct)\s+([A-Za-z0-9_]*(?:ObjectPool|ConnectionPool|WorkerPool))\b"),
        "evidencia_fuerte",
        "Pool acotado de recursos reutilizables (Object Pool)",
    ),
    (
        "data-transfer-object",
        re.compile(r"\b(?:class|interface|type|record)\s+([A-Za-z0-9_]+DTO)\b"),
        "evidencia_fuerte",
        "Objeto de transferencia serializable (DTO)",
    ),
    (
        "mediator",
        re.compile(r"\b(?:class|interface)\s+([A-Za-z0-9_]*Mediator)\b"),
        "evidencia_fuerte",
        "Componente centralizador de comunicaciones estilo Mediator",
    ),
    (
        "visitor",
        re.compile(r"\b(?:class|interface)\s+([A-Za-z0-9_]*Visitor)\b"),
        "evidencia_fuerte",
        "Clase Visitor para recorrer y operar sobre estructuras de nodos",
    ),
    (
        "identity-access-management",
        re.compile(r"\b(?:class|interface)\s+([A-Za-z0-9_]*(?:IdentityProvider|AccessPolicyEngine|RbacGuard|AbacPolicy|AuthPrincipal|TokenVerifier))|\b(authorizePrincipal|verifyJwtToken|evaluateAccessPolicy)\s*\("),
        "evidencia_fuerte",
        "Identidad verificable y autorizacion IAM/RBAC/ABAC explicita",
    ),
    (
        "multi-tenancy-isolation",
        re.compile(r"\b(?:class|interface)\s+([A-Za-z0-9_]*(?:TenantContext|TenantResolver|TenantIsolationMiddleware|TenantIsolationGuard|MultiTenantStore))|\b(resolveTenant|withTenantScope|assertTenantIsolation)\s*\("),
        "evidencia_fuerte",
        "Aislamiento explicito por tenant (Multi-Tenancy & Tenant Isolation)",
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
                "official_name": p["official_name"],
                "reference": p["reference"],
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
            if nombre_var in ("CONTEXTS", "BOUNDED_CONTEXTS"):
                agregar(
                    "bounded-contexts-ddd",
                    nodo.lineno,
                    nombre_var,
                    "evidencia_fuerte",
                    "Registro explicito de contextos acotados",
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
            elif nombre_var in ("_INSTANCE", "_SINGLETON"):
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

            # Puertos declarados dentro de contextos (Hexagonal, criterio generico)
            if nombre_var in ("CONTEXTS", "BOUNDED_CONTEXTS") and isinstance(valor_var, ast.Dict):
                for val_ctx in valor_var.values:
                    if isinstance(val_ctx, ast.Dict):
                        claves = {
                            k.value for k in val_ctx.keys
                            if isinstance(k, ast.Constant) and isinstance(k.value, str)
                        }
                        if "ports" in claves or "puertos" in claves:
                            agregar(
                                "hexagonal-ports-adapters",
                                nodo.lineno,
                                nombre_var,
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
            if cname.endswith("Adapter") or cname.startswith("Adaptador"):
                agregar(
                    "adapter",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Clase Adapter que traduce contratos entre capas",
                )
            retorna_self = any(
                isinstance(sub, ast.Return)
                and isinstance(sub.value, ast.Name)
                and sub.value.id == "self"
                for m in nodo.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                for sub in ast.walk(m)
            )
            if cname.endswith("Builder") or (
                retorna_self and bool(metodos.intersection({"build", "render", "to_dict"}))
            ):
                agregar(
                    "builder",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Clase Builder con construccion fluida (retorna self) y build/render final",
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
            if cname.endswith("Proxy"):
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
            if cname.endswith(("CommandHandler", "QueryHandler", "CommandBus", "QueryBus", "RWCoordinator")):
                agregar(
                    "cqrs",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Componente explicito CQRS de comandos/consultas",
                )
            if cname.endswith(("Command", "Dispatcher", "Router")):
                agregar(
                    "command-dispatch-router",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Objeto Command o enrutador de despacho",
                )
            if cname.endswith(("Observer", "EventBus", "Publisher")):
                agregar(
                    "observer-event-bus",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Clase Observer/EventBus para notificaciones desacopladas",
                )
            if cname.endswith(("EventBroker", "MessageBroker", "EventHandler", "EventConsumer")):
                agregar(
                    "event-driven-architecture",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Componente broker/manejador explicito de Event-Driven Architecture",
                )
            if cname.endswith(("PluginRegistry", "PluginManager", "ExtensionRegistry")):
                agregar(
                    "microkernel-plugin",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Registro dinamico de plugins estilo Microkernel",
                )
            if cname.endswith(("Filter", "Pipe", "PipelineStage")):
                agregar(
                    "pipe-and-filter",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Componente etapa/filtro de arquitectura Pipe-and-Filter",
                )
            if cname.endswith(("DIContainer", "ServiceContainer", "Injector")):
                agregar(
                    "dependency-injection",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Contenedor explicito de Dependency Injection",
                )
            if cname.endswith("Decorator"):
                agregar(
                    "decorator",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Clase Decorator que envuelve otro objeto preservando interfaz",
                )
            if cname.endswith("Specification") or "is_satisfied_by" in metodos:
                agregar(
                    "specification",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Regla componible de dominio estilo Specification",
                )
            if cname.endswith("UnitOfWork") or (
                {"__enter__", "__exit__", "commit", "rollback"}.issubset(metodos)
            ):
                agregar(
                    "unit-of-work",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Gestor transaccional Unit of Work con commit/rollback",
                )
            if cname.endswith("CircuitBreaker"):
                agregar(
                    "circuit-breaker-retry",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Clase CircuitBreaker para resiliencia frente a fallos en cascada",
                )
            if (
                cname.endswith(("Disposable", "ResourceGuard", "ScopeGuard"))
                or "dispose" in metodos
                or "aclose" in metodos
                or (
                    {"__enter__", "__exit__"}.issubset(metodos)
                    and bool(metodos.intersection({"close", "dispose", "release", "cleanup", "shutdown"}))
                )
                or {"__aenter__", "__aexit__"}.issubset(metodos)
            ):
                agregar(
                    "dispose-raii",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Liberacion determinista de recursos mediante protocolo Dispose / Context Manager (RAII)",
                )
            if cname.endswith(("TransactionManager", "AcidTransaction")) or (
                {"begin", "commit", "rollback"}.issubset(metodos)
            ):
                agregar(
                    "acid-transactions",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Gestor transaccional explicito con begin/commit/rollback (ACID)",
                )
            if cname.endswith(("SagaOrchestrator", "SagaCoordinator", "CompensatingAction", "SagaStep")) or (
                "compensate" in metodos and bool(metodos.intersection({"execute", "run", "apply"}))
            ):
                agregar(
                    "saga-compensation",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Orquestador o paso compensatorio del patron Saga",
                )
            if cname.endswith(("CheckpointStore", "WorkflowCheckpoint", "ReplayEngine", "DurableExecutor")) or (
                {"save_checkpoint", "load_checkpoint"}.issubset(metodos)
            ):
                agregar(
                    "durable-execution-checkpoint-replay",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Motor o almacen de checkpoints y replay determinista (Durable Execution)",
                )
            if cname.endswith(("WorkflowDAG", "TaskGraph", "DagExecutor", "WorkflowEngine", "WorkflowOrchestrator")):
                agregar(
                    "dag-workflow-orchestration",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Orquestador de flujo de trabajo modelado como grafo aciclico dirigido (DAG)",
                )
            if cname.endswith(("LeaseManager", "HeartbeatMonitor")) or (
                {"acquire_lease", "renew_lease"}.issubset(metodos)
            ):
                agregar(
                    "heartbeat-lease",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Control de concesiones temporales renovadas por Heartbeat & Lease",
                )
            if cname.endswith(("GracefulShutdown", "ShutdownCoordinator")):
                agregar(
                    "graceful-shutdown",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Coordinador de drenaje y cierre ordenado (Graceful Shutdown)",
                )
            if cname.endswith(("OutboxRepository", "OutboxRelay", "OutboxPublisher", "TransactionalOutbox")):
                agregar(
                    "transactional-outbox",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Componente explicito del patron Transactional Outbox",
                )
            if cname.endswith(("EventStore", "EventSourcedAggregate")) or (
                cname.endswith("AggregateRoot") and bool(metodos.intersection({"apply_event", "replay"}))
            ):
                agregar(
                    "event-sourcing",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Almacen o agregado reconstruido a partir de eventos (Event Sourcing)",
                )
            if cname.endswith(("AntiCorruptionLayer", "ACLTranslator")):
                agregar(
                    "anti-corruption-layer",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Capa traductora Anti-Corruption Layer frente a contratos externos",
                )
            if cname.endswith(("IdempotentConsumer", "IdempotencyStore", "IdempotencyGuard")):
                agregar(
                    "idempotent-consumer",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Guardia o almacen de deduplicacion estilo Idempotent Consumer",
                )
            if cname.endswith(("RateLimiter", "TokenBucket", "LeakyBucket", "SlidingWindowLimiter")):
                agregar(
                    "rate-limiter-throttling",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Limitador de tasa (Rate Limiter / Throttling)",
                )
            if cname.endswith(("BoundedQueue", "BackpressureController")):
                agregar(
                    "backpressure",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Cola acotada o regulador explicito de Backpressure",
                )
            if cname.endswith(("DeadlineContext", "TimeoutBudget")):
                agregar(
                    "timeout-deadline-propagation",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Propagacion explicita de presupuesto de tiempo (Timeout & Deadline)",
                )
            if cname.endswith(("ObjectPool", "ConnectionPool", "WorkerPool")):
                agregar(
                    "object-pool",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Pool de recursos reutilizables (Object Pool)",
                )
            if cname.endswith("AbstractFactory"):
                agregar(
                    "abstract-factory",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Fabrica abstracta para familias de objetos relacionados",
                )
            if cname.endswith("Prototype") or ("clone" in metodos and "Prototype" in cname):
                agregar(
                    "prototype",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Clase Prototype con clonacion de instancias",
                )
            if cname.endswith("Bridge"):
                agregar(
                    "bridge",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Separacion abstraccion/implementacion estilo Bridge",
                )
            if cname.endswith("Composite"):
                agregar(
                    "composite",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Estructura jerarquica uniforme estilo Composite",
                )
            if cname.endswith(("Flyweight", "FlyweightFactory")):
                agregar(
                    "flyweight",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Comparticion de estado intrinseco estilo Flyweight",
                )
            if cname.endswith("DTO") and len(cname) > 3:
                agregar(
                    "data-transfer-object",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Objeto de transferencia serializable entre fronteras (DTO)",
                )
            if cname.endswith(("DataMapper", "Gateway")):
                agregar(
                    "gateway-data-mapper",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Traductor Data Mapper o pasarela Gateway",
                )
            if cname.endswith("Mediator"):
                agregar(
                    "mediator",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Mediador centralizado de comunicaciones entre componentes",
                )
            if cname.endswith("Visitor") or any(_nombre_base(b) == "NodeVisitor" for b in nodo.bases):
                agregar(
                    "visitor",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Clase Visitor sobre estructura de nodos o AST",
                )
            if cname.endswith("Interpreter"):
                agregar(
                    "interpreter",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Evaluador de gramatica o DSL estilo Interpreter",
                )
            if cname.endswith("Memento"):
                agregar(
                    "memento",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Instantanea encapsulada de estado estilo Memento",
                )
            if cname.endswith("NullObject") or cname.startswith("Null") and len(cname) > 4 and metodos:
                if cname.endswith("NullObject"):
                    agregar(
                        "null-object",
                        nodo.lineno,
                        cname,
                        "evidencia_fuerte",
                        "Implementacion inofensiva estilo Null Object",
                    )
            if cname.endswith(("PolicyEngine", "RuleEngine", "RulesEngine")):
                agregar(
                    "policy-rule-engine",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Motor declarativo de politicas o reglas de negocio",
                )
            if cname.endswith((
                "IdentityProvider",
                "AccessPolicy",
                "AccessPolicyEngine",
                "AuthProvider",
                "TokenVerifier",
                "RbacEnforcer",
                "AbacEnforcer",
            )) or (cname == "Principal") or ({"authenticate", "authorize"}.issubset(metodos)):
                agregar(
                    "identity-access-management",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Identidad (Principal/IAM) o control de acceso RBAC/ABAC explicito",
                )
            if cname.endswith((
                "TenantContext",
                "TenantResolver",
                "TenantIsolationGuard",
                "TenantStore",
                "MultiTenantRouter",
            )):
                agregar(
                    "multi-tenancy-isolation",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Resolucion o aislamiento explicito por tenant (Multi-Tenancy)",
                )
            if {"__iter__", "__next__"}.issubset(metodos):
                agregar(
                    "iterator",
                    nodo.lineno,
                    cname,
                    "evidencia_fuerte",
                    "Protocolo explicito Iterator (`__iter__` + `__next__`)",
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
            if fname in ("create_container", "compose_app", "build_container") and (
                "__init__" in rel_posix or "container" in rel_posix or "composition" in rel_posix
            ):
                agregar(
                    "composition-root",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Raiz de composicion que ensambla contexto y adaptadores",
                )
            if fname.endswith("_factory") or (
                fname.startswith(("make_", "create_", "build_"))
                and any(isinstance(sub, ast.FunctionDef) for sub in nodo.body)
            ):
                agregar(
                    "factory",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Fabrica parametrizada que construye validadores u objetos",
                )
            # Envelope / Result Object generico: funcion que retorna dict estructurado con `ok` y `error_code`/`error`
            emite_envelope = False
            for sub in ast.walk(nodo):
                if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Dict):
                    claves_ret = {
                        k.value for k in sub.value.keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)
                    }
                    if "ok" in claves_ret and ("error_code" in claves_ret or "error" in claves_ret):
                        emite_envelope = True
                        break
            if emite_envelope:
                agregar(
                    "envelope-result-object",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Constructor canonico de envelope de respuesta/error estructurado",
                )
            if fname in ("create_snapshot", "quarantine_file", "rollback_to_commit", "restore_snapshot"):
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
            if fname in ("register_plugin", "load_plugins"):
                agregar(
                    "microkernel-plugin",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Funcion de registro/carga de plugins estilo Microkernel",
                )
            if fname in ("retry_with_backoff", "exponential_backoff"):
                agregar(
                    "circuit-breaker-retry",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Funcion de reintento con espera exponencial acotada",
                )
            if fname in ("save_checkpoint", "load_checkpoint", "replay_events", "replay_workflow"):
                agregar(
                    "durable-execution-checkpoint-replay",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Funcion de checkpoint o replay determinista (Durable Execution)",
                )
            if fname in ("topological_sort", "execute_dag", "run_workflow_dag"):
                agregar(
                    "dag-workflow-orchestration",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Ordenamiento topologico o ejecucion de grafo aciclico dirigido (DAG)",
                )
            if fname in ("renew_lease", "send_heartbeat", "acquire_lease"):
                agregar(
                    "heartbeat-lease",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Renovacion de lease o latido periodico (Heartbeat & Lease)",
                )
            if fname in ("graceful_shutdown", "drain_and_shutdown", "install_signal_handlers"):
                agregar(
                    "graceful-shutdown",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Manejador de cierre ordenado y drenaje de recursos (Graceful Shutdown)",
                )
            if fname in ("evaluar_acceso_cruzado", "authorize_principal", "verify_jwt_token", "evaluate_access_policy"):
                agregar(
                    "identity-access-management",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Evaluador explicito de identidad y autorizacion (IAM/RBAC/ABAC)",
                )
            if fname in ("resolve_tenant", "assert_tenant_isolation", "set_tenant_context"):
                agregar(
                    "multi-tenancy-isolation",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Funcion explicita de resolucion o aislamiento por tenant (Multi-Tenancy)",
                )
            if any(_es_decorador(d, "contextmanager") for d in nodo.decorator_list) and any(
                k in fname.lower() for k in ("transaction", "batch", "unit_of_work", "uow", "lote")
            ):
                agregar(
                    "unit-of-work",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Context manager transaccional o por lote estilo Unit of Work",
                )
            if any(_es_decorador(d, "contextmanager") for d in nodo.decorator_list) and any(
                k in fname.lower() for k in ("dispose", "resource", "managed_", "scoped_", "closing")
            ):
                agregar(
                    "dispose-raii",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Context manager RAII/Dispose para adquisicion y liberacion garantizada de recursos",
                )
            for sub in ast.walk(nodo):
                if isinstance(sub, ast.Call):
                    cn_ext = _es_call_nombre(sub, {"ExitStack", "AsyncExitStack", "TopologicalSorter"})
                    if cn_ext in ("ExitStack", "AsyncExitStack"):
                        agregar(
                            "dispose-raii",
                            sub.lineno,
                            f"{fname} ({cn_ext})",
                            "evidencia_fuerte",
                            f"Composicion determinista de liberacion de recursos via `{cn_ext}` (RAII/Dispose)",
                        )
                        break
                    if cn_ext == "TopologicalSorter":
                        agregar(
                            "dag-workflow-orchestration",
                            sub.lineno,
                            f"{fname} (TopologicalSorter)",
                            "evidencia_fuerte",
                            "Planificacion determinista de dependencias DAG via `graphlib.TopologicalSorter`",
                        )
                        break
            if any(
                isinstance(sub, ast.FunctionDef)
                and any(
                    isinstance(dec, ast.Call)
                    and ((isinstance(dec.func, ast.Name) and dec.func.id == "wraps")
                         or (isinstance(dec.func, ast.Attribute) and dec.func.attr == "wraps"))
                    for dec in sub.decorator_list
                )
                for sub in nodo.body
            ):
                agregar(
                    "decorator",
                    nodo.lineno,
                    fname,
                    "evidencia_fuerte",
                    "Funcion Decorator con `functools.wraps` que envuelve otra funcion",
                )


def _detectar_arquitectura_directorios(
    archivos_rel: Sequence[str],
    hallazgos: Dict[str, List[Dict[str, Any]]],
) -> None:
    """Detecta Layered Architecture y Clean Architecture a partir de capas explicitas."""
    segmentos_por_archivo: Dict[str, Set[str]] = {}
    for rel in archivos_rel:
        partes = {p.lower() for p in Path(rel).parts[:-1]}
        if partes:
            segmentos_por_archivo[rel] = partes

    todos = set().union(*segmentos_por_archivo.values()) if segmentos_por_archivo else set()
    if not todos:
        return

    capas_layered = {
        "presentation": {"controllers", "controller", "api", "routes", "presentation", "ui"},
        "application": {"services", "service", "application"},
        "domain": {"domain", "models", "entities"},
        "data": {"repositories", "repository", "persistence", "data", "infrastructure", "dal"},
    }
    capas_encontradas = [
        capa for capa, vocab in capas_layered.items() if todos & vocab
    ]
    if len(capas_encontradas) >= 3:
        muestra = next(
            (rel for rel, segs in sorted(segmentos_por_archivo.items())
             if segs & capas_layered[capas_encontradas[0]]),
            sorted(segmentos_por_archivo)[0],
        )
        hallazgos.setdefault("layered-architecture", []).append({
            "file": muestra,
            "line": 1,
            "symbol": "+".join(capas_encontradas),
            "confidence": "indicio_estructural",
            "how": f"Separacion explicita en {len(capas_encontradas)} capas horizontales ({', '.join(capas_encontradas)})",
        })

    tiene_nucleo = bool(todos & {"entities", "domain"})
    tiene_casos = bool(todos & {"use_cases", "usecases", "interactors"})
    tiene_adaptadores = bool(todos & {"interface_adapters", "adapters", "frameworks", "frameworks_drivers", "infrastructure"})
    if tiene_nucleo and tiene_casos and tiene_adaptadores:
        muestra = next(
            (rel for rel, segs in sorted(segmentos_por_archivo.items())
             if segs & {"use_cases", "usecases", "interactors"}),
            sorted(segmentos_por_archivo)[0],
        )
        hallazgos.setdefault("clean-architecture", []).append({
            "file": muestra,
            "line": 1,
            "symbol": "domain+use_cases+adapters",
            "confidence": "evidencia_fuerte",
            "how": "Capas explicitas de Clean Architecture (entities/domain + use_cases + adapters/frameworks)",
        })


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
    archivos_vistos: List[str] = []
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
        archivos_vistos.append(rel_posix)
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

    _detectar_arquitectura_directorios(archivos_vistos, hallazgos)

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
                "official_name": meta["official_name"],
                "reference": meta["reference"],
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
