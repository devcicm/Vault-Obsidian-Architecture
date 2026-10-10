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
  ausencia, pero la nota sigue siendo válida. Fue el nivel de `type` (AP-27) y
  `status` (AP-29) de v37 a v40 (`recomendado_desde`).
  En v41 los dos pasan a requeridos **por presencia, no por valor**: AP-12
  del manifiesto ya contaba `type` entre los obligatorios desde v18, y el
  validador exigía menos que la norma. El valor no se cierra con un enum
  porque, medido el 2026-10-05, dieciocho primers del sandbox llevan
  `type: primer` —`SCAFFOLD_TYPE`, que no pertenece a ninguna sección de
  `SECTION_TYPES`— y cinco notas llevan un `status` fuera de `STATUS_VOCAB`
  (`accepted`, `active`) que `normalize_status` lleva al canónico como
  sinónimo. Un enum cerrado reprobaría las veintitrés; su valor lo sigue
  juzgando `vault_audit`.
- **valor** — si el campo está, su valor tiene que pertenecer al vocabulario
  (CIA) o no estar vacío (`agent`).

## Dos autoridades, según la versión

`vault_validate` entra en el repo con v25. Antes, el contrato de una nota era
la regla de AP-12 del manifiesto —«los campos obligatorios (`id`, `title`,
`type`, `createdAt`, `updatedAt`, `tags`) deben existir en todas las notas»—,
escrita igual en los manifiestos de v18, v19 y v20 que guarda git (`PREVIAS`)
y en el de v25. `contrato_de_version` devuelve, para cada versión, lo que
exigía la autoridad que había: el manifiesto hasta v24 (`origen: manifiesto`,
`validador: False`) y el validador desde v25 (`origen: validador`). Las dos
cosas no coinciden, y se declara en vez de igualarlas: de v25 a v36 el
validador solo exigía `id` y `title`, menos de lo que la norma decía.

De v21 a v24 no hay manifiesto en git: el de v20 y el de v25 escriben la regla
con el mismo texto, y eso es lo que se aplica entre ambos. Antes de v18 el
manifiesto no está en el repositorio y no se publica contrato.

Cualquier versión se puede validar hoy con `vault_validate --contrato vNN`: el
validador vigente aplicando el contrato de entonces.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from vault_fundamentals_catalog import cia_valores
from vault_norms_catalog import STATUS_VOCAB
from vault_registry import es_artefacto_derivado, es_de_seccion

CLASES = ("derivada", "sistema", "sin_seccion", "contenido")

#: Primera versión con la clase `sin_seccion`. Antes, un `.md` fuera de toda
#: sección se juzgaba como contenido, y el contrato de esas versiones lo dice
#: así: la clase nueva no reescribe lo que el validador exigía entonces.
SIN_SECCION_DESDE = "v41"

#: Las versiones mayores del estándar con migración registrada. Es la lista de
#: `vault_standard_upgrade.MIGRATIONS`, que vive en otro contexto y no se
#: importa desde el núcleo; `test_la_historia_cubre_las_versiones_de_migrations`
#: falla si divergen.
VERSIONES: Tuple[str, ...] = tuple(f"v{n}" for n in range(21, 42))

#: Versiones anteriores a `MIGRATIONS` cuyo manifiesto está en git, con el
#: commit que lo atestigua. `test_las_versiones_previas_son_las_del_manifiesto`
#: comprueba que el banner de cada commit dice esa versión.
PREVIAS: Dict[str, str] = {"v18": "974c2ba", "v19": "5ebb043", "v20": "28b5700"}

#: Todas las versiones con contrato publicado: las previas y las de `MIGRATIONS`.
VERSIONES_CON_CONTRATO: Tuple[str, ...] = tuple(PREVIAS) + VERSIONES

#: Primera versión con un validador ejecutable en el repo.
PRIMER_VALIDADOR = "v25"

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

#: El contrato vigente, campo a campo. El orden es el de `faltantes`.
#: `clases`: a qué clase de nota se le exige. `requerido_desde`: versión en que
#: `vault_validate` empezó a reprobar su ausencia (None si no la reprueba).
CAMPOS: Dict[str, Dict[str, Any]] = {
    "id": {"tipo": "string", "nivel": "requerido", "clases": ("sistema", "sin_seccion", "contenido"),
           "requerido_desde": "v25", "normativo_desde": "v18", "norma": "AP-12"},
    "title": {"tipo": "string", "nivel": "requerido", "clases": ("sistema", "sin_seccion", "contenido"),
              "requerido_desde": "v25", "normativo_desde": "v18", "norma": "AP-12"},
    "createdAt": {"tipo": "string", "formato": "date-time", "nivel": "requerido",
                  "clases": ("sistema", "sin_seccion", "contenido"), "requerido_desde": "v37",
                  "normativo_desde": "v18", "norma": "AP-12"},
    "updatedAt": {"tipo": "string", "formato": "date-time", "nivel": "requerido",
                  "clases": ("sistema", "sin_seccion", "contenido"), "requerido_desde": "v37",
                  "normativo_desde": "v18", "norma": "AP-12"},
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
             "requerido_desde": "v37", "normativo_desde": "v18", "norma": "AP-26"},
    "type": {"tipo": "string", "nivel": "requerido", "clases": ("contenido",),
             "requerido_desde": "v41", "recomendado_desde": "v37", "normativo_desde": "v18",
             "norma": "AP-27"},
    "status": {"tipo": "string", "nivel": "requerido", "clases": ("contenido",),
               "requerido_desde": "v41", "recomendado_desde": "v37", "norma": "AP-29",
               "vocabulario": tuple(sorted(STATUS_VOCAB))},
    "dq_validated_at": {"tipo": "string", "formato": "date-time", "nivel": "opcional",
                        "clases": ("contenido",), "requerido_desde": None,
                        "valores_desde": "v27", "patron": _ISO.pattern},
    # La versión del proyecto desde la que rige una nota de arquitectura. La lee
    # `vault_arquitectura_en`; sin valor, la nota cae en «indeterminada» y no
    # deja de ser válida. El fin de su vigencia no se escribe: sale de
    # `superseded_by` o del status.
    "vigente_desde": {"tipo": "string", "nivel": "opcional", "clases": ("contenido",),
                      "requerido_desde": None},
    # Quién responde del contenido de la nota —del porqué, en una decisión—. No
    # es `agent`, que dice quién la escribió: un agente redacta un ADR y una
    # persona lo firma.
    "responsable": {"tipo": "string", "nivel": "opcional", "clases": ("contenido",),
                    "requerido_desde": None, "valores_desde": "v41", "no_vacio": True,
                    "norma": "AP-64"},
    # La última vez que alguien comprobó que la nota sigue siendo cierta, la
    # cambiara o no. `updatedAt` solo se mueve si el texto cambia; sin este
    # campo, revisar una nota y confirmarla no deja rastro. Fecha o fecha y hora.
    # Lo lee `vault_drift_detect --mode vigencia` (AP-08).
    "revisado_en": {"tipo": "string", "formato": "date", "nivel": "opcional",
                    "clases": ("contenido",), "requerido_desde": None,
                    "valores_desde": "v41", "norma": "AP-08", "patron": r"^\d{4}-\d{2}-\d{2}"},
    # Las versiones de paquete que el texto de la nota da por buenas, como mapa
    # `paquete: versión`. Lo pide la `prevention` de AP-08 desde v19 y nadie lo
    # emitía; lo escribe `vault_write --version-pinned` y lo cruza con el
    # manifiesto del repo `vault_drift_detect --mode vigencia`. La relación la
    # declara la nota: el detector no adivina qué librería menciona el cuerpo.
    "version_pinned": {"tipo": "object", "nivel": "opcional", "clases": ("contenido",),
                       "requerido_desde": None, "valores_desde": "v41", "norma": "AP-08",
                       "mapa_no_vacio": True},
}

#: Cuándo cambió el contrato y quién lo atestigua. `fuente` es
#: `MIGRATIONS:<texto>` —un fragmento literal de la migración de esa versión—
#: o `git:<hash>` cuando la migración no lo dejó escrito. El test comprueba
#: las dos. Nada de aquí se escribe de memoria.
HISTORIA: Dict[str, List[Dict[str, Any]]] = {
    "v18": [{"campos": ["id", "title", "type", "createdAt", "updatedAt", "tags"],
             "cambio": ("AP-12 en el manifiesto: los seis campos obligatorios en toda nota; "
                        "ninguna tool lo aplica"),
             "fuente": ("manifiesto:974c2ba:Los campos obligatorios (`id`, `title`, `type`, "
                        "`createdAt`, `updatedAt`, `tags`)")}],
    "v21": [{"campos": ["agent"], "cambio": "el escritor pone agent en las notas nuevas",
             "fuente": "MIGRATIONS:AP-16: add agent: field to new notes"}],
    "v25": [{"campos": ["id", "title"],
             "cambio": ("primer validador: exige id y title, menos que AP-12, que el "
                        "manifiesto de v25 sigue escribiendo igual"),
             "fuente": "git:767a84a"}],
    "v27": [{"campos": ["cia_integrity", "cia_availability", "cia_sensitivity", "agent",
                        "dq_validated_at"],
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
             "fuente": "git:f1fc051"},
            {"campos": ["type", "status"],
             "cambio": "el escritor los pone por defecto y vault_audit penaliza su ausencia",
             "fuente": "git:f1fc051"}],
    "v41": [{"campos": ["type", "status"],
             "cambio": ("requeridos en notas de contenido, por presencia: el valor lo sigue "
                        "juzgando vault_audit"),
             "fuente": "MIGRATIONS:AP-27/AP-29: type y status requeridos en notas de contenido"},
            {"campos": ["id", "title", "createdAt", "updatedAt"],
             "cambio": ("clase sin_seccion: un .md fuera de toda sección lleva identidad y "
                        "timestamps; CIA, agent, tags, type y status son de las notas de sección"),
             "fuente": "MIGRATIONS:clase sin_seccion: un .md fuera de toda seccion"},
            {"campos": ["vigente_desde"],
             "cambio": ("opcional: la versión del proyecto desde la que rige una nota de "
                        "arquitectura; el fin sale de superseded_by o del status"),
             "fuente": "MIGRATIONS:vigente_desde (opcional): version del proyecto"},
            {"campos": ["responsable", "revisado_en"],
             "cambio": ("opcionales: quién responde del contenido y cuándo se comprobó por "
                        "última vez; si están, responsable no vacío y revisado_en con fecha ISO"),
             "fuente": "MIGRATIONS:responsable y revisado_en (opcionales)"},
            {"campos": ["version_pinned"],
             "cambio": ("opcional: mapa paquete → versión que la nota da por buena; si está, "
                        "un mapa no vacío sin claves ni valores vacíos (AP-08)"),
             "fuente": "MIGRATIONS:version_pinned (opcional)"}],
}

#: Lo que el escritor pone cuando nadie dice otra cosa. Estaba como literal en
#: `vault_write.generate_frontmatter`; quien complete una nota a la que le falta
#: un campo tiene que poner lo mismo, no un valor propio (AP-57). Los de CIA no
#: están aquí porque su dueño es `CIA_TRIAD` (`cia_por_defecto`).
#: `test_los_valores_por_defecto_son_los_del_escritor` compara con lo que
#: `vault_write` escribe de verdad.
POR_DEFECTO: Dict[str, Any] = {"status": "draft", "agent": "system", "tags": []}


def _numero(version: str) -> int:
    return int(version.lstrip("v").split(".", 1)[0])


def clase_de_nota(ruta_relativa: str, raiz: Optional[Path] = None) -> str:
    """`derivada`, `sistema`, `sin_seccion` o `contenido`. La clase decide el conjunto (AP-12).

    `sin_seccion` es un `.md` de la raíz o de una carpeta que el registro no
    declara: medido en dos vaults ajenos, `README.md` y `Home.md` se juzgaban
    como contenido y el contrato les pedía la CIA que decide una sección.

    Con `raiz`, una sección propia que ese vault declara (`vault_section`) es
    contenido como cualquier otra (v41.2). Sin ella solo cuentan las del
    estándar: quien no dice de qué vault es la ruta no puede saber qué declaró.
    """
    rel = ruta_relativa.replace("\\", "/")
    if es_artefacto_derivado(rel):
        return "derivada"
    if rel == "00_System" or rel.startswith("00_System/"):
        return "sistema"
    if not es_de_seccion(rel, raiz):
        return "sin_seccion"
    return "contenido"


def campos_requeridos(ruta_relativa: str, raiz: Optional[Path] = None) -> Tuple[str, ...]:
    clase = clase_de_nota(ruta_relativa, raiz)
    return tuple(c for c, d in CAMPOS.items() if d["nivel"] == "requerido" and clase in d["clases"])


def campos_recomendados(ruta_relativa: str, raiz: Optional[Path] = None) -> Tuple[str, ...]:
    clase = clase_de_nota(ruta_relativa, raiz)
    return tuple(c for c, d in CAMPOS.items() if d["nivel"] == "recomendado" and clase in d["clases"])


def _requeridos_en(ruta_relativa: str, version: str,
                   raiz: Optional[Path] = None) -> Tuple[str, ...]:
    """Los requeridos de la clase de la nota según el contrato de `version`."""
    c = contrato_de_version(version)
    clase = clase_de_nota(ruta_relativa, raiz)
    if clase == "derivada":
        # Antes de v37 un índice no tenía excepción: era una nota como otra.
        return () if c["indices_exentos"] else tuple(c["requeridos"]["contenido"])
    if clase not in c["requeridos"]:
        # Una clase que esa versión no conocía: entonces se juzgaba como contenido.
        return tuple(c["requeridos"]["contenido"])
    return tuple(c["requeridos"][clase])


def faltantes(datos: Mapping[str, Any], ruta_relativa: str,
              version: Optional[str] = None, raiz: Optional[Path] = None) -> List[str]:
    """Los requeridos que la nota no lleva, en el orden del contrato.

    Sin `version`, el contrato vigente; con ella, el de esa versión mayor. Con
    `raiz`, las secciones propias de ese vault cuentan (ver `clase_de_nota`).
    """
    requeridos = (campos_requeridos(ruta_relativa, raiz) if version is None
                  else _requeridos_en(ruta_relativa, version, raiz))
    return [c for c in requeridos if c not in datos]


def errores_de_valor(datos: Mapping[str, Any], version: Optional[str] = None) -> List[str]:
    """Los valores presentes que el contrato rechaza. La ausencia no es un error aquí.

    Con `version`, solo los campos cuyo valor ya se juzgaba en esa versión.
    """
    juzgados = None if version is None else set(contrato_de_version(version)["valores"])
    errores: List[str] = []
    for campo, d in CAMPOS.items():
        if campo not in datos or (juzgados is not None and campo not in juzgados):
            continue
        if "valores" in d:
            v = str(datos[campo]).lower()
            if v not in d["valores"]:
                errores.append(f"{campo} '{v}' must be one of: {sorted(d['valores'])}")
        if "patron" in d and not re.match(d["patron"], str(datos[campo])):
            errores.append(f"{campo} '{datos[campo]}' must be ISO 8601 (YYYY-MM-DDTHH:MM:SS...)")
        if d.get("no_vacio") and not str(datos[campo]).strip():
            errores.append(f"{campo} field present but empty (F7 AUTENTICIDAD requires non-empty value)")
        if d.get("mapa_no_vacio") and not es_mapa_de_versiones(datos[campo]):
            errores.append(f"{campo} must be a non-empty mapping package: version")
    return errores


def es_mapa_de_versiones(valor: Any) -> bool:
    """Un mapa no vacío `paquete: versión`, sin clave ni valor en blanco."""
    return (isinstance(valor, Mapping) and bool(valor)
            and all(str(k).strip() and v is not None and str(v).strip()
                    for k, v in valor.items()))


def pin_de_texto(texto: str) -> Optional[Tuple[str, str]]:
    """`paquete@versión` → `(paquete, versión)`; None si falta una de las dos.

    Corta por la **última** arroba: un paquete con ámbito de npm
    (`@scope/pkg@2.1`) empieza por una. Es la forma de la CLI de `vault_write`;
    el frontmatter guarda el mapa.
    """
    paquete, _, version = str(texto).strip().rpartition("@")
    if not paquete.strip() or not version.strip():
        return None
    return paquete.strip(), version.strip()


def contrato_de_version(version: str) -> Dict[str, Any]:
    """El contrato de una nota en esa versión mayor, según la autoridad de entonces.

    Desde `PRIMER_VALIDADOR`, lo que aplicaba `vault_validate`; antes, lo que
    la regla AP-12 del manifiesto exigía a toda nota, sin clases (`origen`).
    Acepta `v40.36` y lo lee como `v40`: el contrato no ha cambiado dentro de
    una versión mayor, y si cambia, la historia tendrá que decirlo.
    """
    n = _numero(version)
    primera, ultima = VERSIONES_CON_CONTRATO[0], VERSIONES_CON_CONTRATO[-1]
    if not _numero(primera) <= n <= _numero(ultima):
        raise ValueError(f"{version}: fuera de {primera}..{ultima}")
    validador = n >= _numero(PRIMER_VALIDADOR)
    requeridos: Dict[str, List[str]] = {"sistema": [], "contenido": []}
    if n >= _numero(SIN_SECCION_DESDE):
        requeridos = {"sistema": [], "sin_seccion": [], "contenido": []}
    valores: Dict[str, Dict[str, Any]] = {}
    for campo, d in CAMPOS.items():
        desde = d.get("requerido_desde") if validador else d.get("normativo_desde")
        if desde and _numero(desde) <= n:
            for clase in (d["clases"] if validador else ("sistema", "contenido")):
                if clase in requeridos:
                    requeridos[clase].append(campo)
        vdesde = d.get("valores_desde")
        if vdesde and _numero(vdesde) <= n:
            valores[campo] = {k: d[k] for k in ("valores", "patron", "no_vacio") if k in d}
    return {
        "version": f"v{n}",
        "validador": validador,
        "origen": "validador" if validador else "manifiesto",
        "indices_exentos": n >= 37,
        "requeridos": requeridos,
        "valores": valores,
        "recomendados": [c for c, d in CAMPOS.items() if _recomendado_en(d, n, validador)],
        "historia": [h for v, hs in HISTORIA.items() if _numero(v) <= n for h in hs],
    }


def _recomendado_en(d: Mapping[str, Any], n: int, validador: bool) -> bool:
    """Recomendado en `n`: ya lo era y todavía no se exigía."""
    desde = d.get("recomendado_desde")
    if not validador or not desde or _numero(desde) > n:
        return False
    hasta = d.get("requerido_desde")
    return not (hasta and _numero(hasta) <= n)


def vocabulario(campo: str) -> Optional[Tuple[str, ...]]:
    d = CAMPOS.get(campo, {})
    return d.get("valores") or d.get("vocabulario")


def conocido_desde(campo: str) -> Optional[str]:
    """La primera versión cuya historia nombra el campo."""
    for v in sorted(HISTORIA, key=_numero):
        if any(campo in h["campos"] for h in HISTORIA[v]):
            return v
    return None


def _sin_mayusculas(valor: str) -> str:
    return "".join(f"[{c.lower()}{c.upper()}]" if c.isalpha() else re.escape(c) for c in valor)


def _nivel_en(campo: str, c: Mapping[str, Any]) -> str:
    """El nivel del campo en el contrato `c`, no el vigente.

    Escribir el vigente en el esquema de una versión pasada la reescribiría:
    `createdAt` diría «requerido» en v30, cuando no se exigía hasta v37.
    """
    if any(campo in c["requeridos"][clase] for clase in ("sistema", "contenido")):
        return "requerido"
    return "recomendado" if campo in c["recomendados"] else "opcional"


def _propiedad(campo: str, n: int, c: Mapping[str, Any]) -> Dict[str, Any]:
    """La propiedad tal como la juzgaba `vault_validate` en la versión `n`.

    Solo restringe lo que el validador restringía: una propiedad más estricta
    que él haría que el esquema reprobara notas que la tool aprueba, y el
    esquema dejaría de ser el contrato para ser una opinión (AP-44). Por eso
    `id`, `title` o `tags` no llevan `type`: el validador solo mira que estén.
    Lo que el escritor pone de forma habitual va en `x-vault-tipo-esperado`.
    """
    d = CAMPOS[campo]
    prop: Dict[str, Any] = {"x-vault-tipo-esperado": d["tipo"], "x-vault-nivel": _nivel_en(campo, c)}
    if d.get("norma"):
        prop["x-vault-norma"] = d["norma"]
    vdesde = d.get("valores_desde")
    if vdesde and _numero(vdesde) <= n:
        if "valores" in d:
            # `vault_validate` compara en minúsculas; un `enum` de JSON Schema
            # no, así que el patrón acepta cualquier caja.
            prop["type"] = "string"
            prop["pattern"] = "^(" + "|".join(_sin_mayusculas(v) for v in d["valores"]) + ")$"
            prop["x-vault-valores"] = list(d["valores"])
        if "patron" in d:
            prop["pattern"] = d["patron"]
        if d.get("no_vacio"):
            prop["type"] = "string"
            prop["pattern"] = r"\S"
        if d.get("mapa_no_vacio"):
            # Un valor numérico sin comillas (`react: 18`) también lo acepta el
            # validador; `pattern` solo restringe las cadenas.
            prop["type"] = "object"
            prop["minProperties"] = 1
            prop["propertyNames"] = {"pattern": r"\S"}
            prop["additionalProperties"] = {"type": ["string", "number"], "pattern": r"\S"}
    if "vocabulario" in d and n >= _numero(conocido_desde(campo) or "v99"):
        prop["x-vault-vocabulario-auditado"] = list(d["vocabulario"])
    return prop


def esquema_json(version: str) -> Dict[str, Any]:
    """JSON Schema 2020-12 del frontmatter de una nota en esa versión mayor.

    La clase de la nota sale de su ruta, y la ruta no está en el frontmatter:
    por eso hay un esquema por clase en `$defs` y la raíz es el de contenido,
    que es el de casi toda nota. Las notas de `00_System/` se validan contra
    `#/$defs/sistema`; los artefactos derivados quedan fuera desde v37.
    """
    c = contrato_de_version(version)
    n = _numero(c["version"])
    conocidos = [k for k in CAMPOS if (conocido_desde(k) and _numero(conocido_desde(k)) <= n)]
    propiedades = {k: _propiedad(k, n, c) for k in conocidos}

    def clase(nombre: str) -> Dict[str, Any]:
        return {"type": "object", "required": list(c["requeridos"][nombre]),
                "properties": propiedades, "additionalProperties": True}

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"vault-{c['version']}.schema.json",
        "title": f"Frontmatter de una nota — estándar {c['version']}",
        "description": (
            "Generado por vault_esquema desde vault_contrato_nota; no se edita a "
            "mano. La raíz es el contrato de una nota de contenido; las de "
            "00_System/ usan #/$defs/sistema."
            + (" Un .md fuera de toda sección usa #/$defs/sin_seccion."
               if "sin_seccion" in c["requeridos"] else "")
        ),
        "x-vault-version": c["version"],
        "x-vault-validador": c["validador"],
        "x-vault-origen": c["origen"],
        "x-vault-indices-exentos": c["indices_exentos"],
        "x-vault-recomendados": c["recomendados"],
        "x-vault-historia": c["historia"],
        **clase("contenido"),
        "$defs": {nombre: clase(nombre) for nombre in ("contenido", "sistema", "sin_seccion")
                  if nombre in c["requeridos"]},
    }
