#!/usr/bin/env python3
"""vault_contrato_nota — los campos que una nota debe llevar, y desde cuándo.

Hoja del núcleo: lee tres registros que ya lo son —`vault_registry`,
`vault_fundamentals_catalog` y `vault_norms_catalog`— y no importa nada más.

## Por qué existe

Hasta 2026-10-05 la lista de campos obligatorios era un literal dentro de
`vault_validate.validate_frontmatter`, con «v37: required fields expanded» como
toda su historia. Quien quisiera saber qué le falta a una nota —el escritor, una
tool que complete los huecos, un consumidor que valide con JSON Schema— tenía
que copiar esa lista, y la copia es AP-57. La versión en que cada campo pasó a
exigirse tampoco estaba en ningún registro: había que leer el `git log`.

## Tres niveles, y por qué no se mezclan

- **requerido** — `vault_validate` reprueba la nota si falta. Es el contrato.
- **recomendado** — el escritor lo pone siempre y `vault_audit` penaliza su
  ausencia (AP-27 `type`, AP-29 `status`), pero la nota sigue siendo válida.
  Subirlo a requerido es una decisión, no un arreglo: medido el 2026-10-05,
  dieciocho primers del sandbox llevan `type: primer`, que no es ningún tipo de
  `SECTION_TYPES`, y cinco notas llevan un `status` fuera de `STATUS_VOCAB`.
- **valor** — si el campo está, su valor tiene que pertenecer al vocabulario
  (CIA) o no estar vacío (`agent`).

## Lo que no está y se declara

`MIGRATIONS` empieza en v21 y `vault_validate` entra en el repo con v25. De
v21 a v24 no había ninguna regla ejecutable: `contrato_de_version` lo dice con
`validador: False` en vez de inventarse una que nadie aplicaba.
"""

import re
from typing import Any, Dict, List, Mapping, Optional, Tuple

from vault_fundamentals_catalog import cia_valores
from vault_norms_catalog import STATUS_VOCAB
from vault_registry import es_artefacto_derivado

CLASES = ("derivada", "sistema", "contenido")

#: Las versiones mayores del estándar con migración registrada. Es la lista de
#: `vault_standard_upgrade.MIGRATIONS`, que vive en otro contexto y no se
#: importa desde el núcleo; `test_la_historia_cubre_las_versiones_de_migrations`
#: falla si divergen.
VERSIONES: Tuple[str, ...] = tuple(f"v{n}" for n in range(21, 41))

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

#: El contrato vigente, campo a campo. El orden es el de `faltantes`.
#: `clases`: a qué clase de nota se le exige. `requerido_desde`: versión en que
#: `vault_validate` empezó a reprobar su ausencia (None si no la reprueba).
CAMPOS: Dict[str, Dict[str, Any]] = {
    "id": {"tipo": "string", "nivel": "requerido", "clases": ("sistema", "contenido"),
           "requerido_desde": "v25", "norma": "AP-12"},
    "title": {"tipo": "string", "nivel": "requerido", "clases": ("sistema", "contenido"),
              "requerido_desde": "v25", "norma": "AP-12"},
    "createdAt": {"tipo": "string", "formato": "date-time", "nivel": "requerido",
                  "clases": ("sistema", "contenido"), "requerido_desde": "v37", "norma": "AP-12"},
    "updatedAt": {"tipo": "string", "formato": "date-time", "nivel": "requerido",
                  "clases": ("sistema", "contenido"), "requerido_desde": "v37", "norma": "AP-12"},
    "cia_integrity": {"tipo": "string", "nivel": "requerido", "clases": ("contenido",),
                      "requerido_desde": "v37", "valores_desde": "v27", "norma": "AP-30",
                      "valores": tuple(sorted(cia_valores("cia_integrity")))},
    "cia_availability": {"tipo": "string", "nivel": "requerido", "clases": ("contenido",),
                         "requerido_desde": "v37", "valores_desde": "v27", "norma": "AP-30",
                         "valores": tuple(sorted(cia_valores("cia_availability")))},
    "cia_sensitivity": {"tipo": "string", "nivel": "requerido", "clases": ("contenido",),
                        "requerido_desde": "v37", "valores_desde": "v27", "norma": "AP-30",
                        "valores": tuple(sorted(cia_valores("cia_sensitivity")))},
    "agent": {"tipo": "string", "nivel": "requerido", "clases": ("contenido",),
              "requerido_desde": "v37", "valores_desde": "v27", "no_vacio": True, "norma": "AP-16"},
    "tags": {"tipo": "array", "nivel": "requerido", "clases": ("contenido",),
             "requerido_desde": "v37", "norma": "AP-26"},
    "type": {"tipo": "string", "nivel": "recomendado", "clases": ("contenido",),
             "requerido_desde": None, "norma": "AP-27"},
    "status": {"tipo": "string", "nivel": "recomendado", "clases": ("contenido",),
               "requerido_desde": None, "norma": "AP-29", "vocabulario": tuple(STATUS_VOCAB)},
    "dq_validated_at": {"tipo": "string", "formato": "date-time", "nivel": "opcional",
                        "clases": ("contenido",), "requerido_desde": None,
                        "valores_desde": "v27", "patron": _ISO.pattern},
}

#: Cuándo cambió el contrato y quién lo atestigua. `fuente` es
#: `MIGRATIONS:<texto>` —un fragmento literal de la migración de esa versión—
#: o `git:<hash>` cuando la migración no lo dejó escrito. El test comprueba
#: las dos. Nada de aquí se escribe de memoria.
HISTORIA: Dict[str, List[Dict[str, Any]]] = {
    "v21": [{"campos": ["agent"], "cambio": "el escritor pone agent en las notas nuevas",
             "fuente": "MIGRATIONS:AP-16: add agent: field to new notes"}],
    "v25": [{"campos": ["id", "title"], "cambio": "primer validador: id y title obligatorios",
             "fuente": "git:767a84a"}],
    "v27": [{"campos": ["cia_integrity", "cia_availability", "cia_sensitivity", "agent"],
             "cambio": "si están, el valor CIA pertenece al vocabulario y agent no está vacío",
             "fuente": "MIGRATIONS:vault_validate: CIA field validation + agent field validation"}],
    "v28": [{"campos": ["cia_integrity", "cia_availability", "cia_sensitivity", "agent"],
             "cambio": "los scripts de escritura ponen CIA y agent",
             "fuente": "MIGRATIONS:CIA frontmatter obligatorio en 12 scripts de escritura"}],
    "v30": [{"campos": ["status"], "cambio": "vocabulario de status auditado (CN-03)",
             "fuente": "MIGRATIONS:status vocabulary"}],
    "v37": [{"campos": ["createdAt", "updatedAt", "cia_integrity", "cia_availability",
                        "cia_sensitivity", "agent", "tags"],
             "cambio": ("requeridos; CIA, agent y tags solo en notas de contenido, y los "
                        "índices quedan fuera del contrato. type y status, recomendados"),
             "fuente": "git:f1fc051"}],
}


def _numero(version: str) -> int:
    return int(version.lstrip("v").split(".", 1)[0])


def clase_de_nota(ruta_relativa: str) -> str:
    """`derivada`, `sistema` o `contenido`. La clase decide el conjunto (AP-12)."""
    rel = ruta_relativa.replace("\\", "/")
    if es_artefacto_derivado(rel):
        return "derivada"
    if rel == "00_System" or rel.startswith("00_System/"):
        return "sistema"
    return "contenido"


def campos_requeridos(ruta_relativa: str) -> Tuple[str, ...]:
    clase = clase_de_nota(ruta_relativa)
    return tuple(c for c, d in CAMPOS.items() if d["nivel"] == "requerido" and clase in d["clases"])


def campos_recomendados(ruta_relativa: str) -> Tuple[str, ...]:
    clase = clase_de_nota(ruta_relativa)
    return tuple(c for c, d in CAMPOS.items() if d["nivel"] == "recomendado" and clase in d["clases"])


def faltantes(datos: Mapping[str, Any], ruta_relativa: str) -> List[str]:
    """Los requeridos que la nota no lleva, en el orden del contrato."""
    return [c for c in campos_requeridos(ruta_relativa) if c not in datos]


def errores_de_valor(datos: Mapping[str, Any]) -> List[str]:
    """Los valores presentes que el contrato rechaza. La ausencia no es un error aquí."""
    errores: List[str] = []
    for campo, d in CAMPOS.items():
        if campo not in datos:
            continue
        if "valores" in d:
            v = str(datos[campo]).lower()
            if v not in d["valores"]:
                errores.append(f"{campo} '{v}' must be one of: {sorted(d['valores'])}")
        if "patron" in d and not re.match(d["patron"], str(datos[campo])):
            errores.append(f"{campo} '{datos[campo]}' must be ISO 8601 (YYYY-MM-DDTHH:MM:SS...)")
        if d.get("no_vacio") and not str(datos[campo]).strip():
            errores.append(f"{campo} field present but empty (F7 AUTENTICIDAD requires non-empty value)")
    return errores


def contrato_de_version(version: str) -> Dict[str, Any]:
    """El contrato tal como lo aplicaba `vault_validate` en esa versión mayor.

    Acepta `v40.36` y lo lee como `v40`: el contrato no ha cambiado dentro de
    una versión mayor, y si cambia, la historia tendrá que decirlo.
    """
    n = _numero(version)
    if not _numero(VERSIONES[0]) <= n <= _numero(VERSIONES[-1]):
        raise ValueError(f"{version}: fuera de {VERSIONES[0]}..{VERSIONES[-1]}")
    requeridos: Dict[str, List[str]] = {"sistema": [], "contenido": []}
    valores: Dict[str, Dict[str, Any]] = {}
    for campo, d in CAMPOS.items():
        desde = d.get("requerido_desde")
        if desde and _numero(desde) <= n:
            for clase in d["clases"]:
                requeridos[clase].append(campo)
        vdesde = d.get("valores_desde")
        if vdesde and _numero(vdesde) <= n:
            valores[campo] = {k: d[k] for k in ("valores", "patron", "no_vacio") if k in d}
    return {
        "version": f"v{n}",
        "validador": n >= _numero("v25"),
        "indices_exentos": n >= 37,
        "requeridos": requeridos,
        "valores": valores,
        "recomendados": [c for c, d in CAMPOS.items() if d["nivel"] == "recomendado"] if n >= 37 else [],
        "historia": [h for v, hs in HISTORIA.items() if _numero(v) <= n for h in hs],
    }


def vocabulario(campo: str) -> Optional[Tuple[str, ...]]:
    d = CAMPOS.get(campo, {})
    return d.get("valores") or d.get("vocabulario")
