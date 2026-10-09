#!/usr/bin/env python3
"""Catálogo canónico de normas AP-XX / PAT-X, y el vocabulario de estado.

**Datos, no comportamiento.** Este módulo no lee el vault, no escribe nada y no
importa ninguna tool: es la mitad de `vault_norms` que era una constante de tres
mil líneas. Salió de ahí en v40.26 porque `vault_norms` hacía de catálogo, de
motor y de fachada a la vez, y el 60% del fichero era esta lista.

**Se entra por `vault_norms`, no por aquí.** La fachada reexporta todo lo
público de este módulo, así que ningún llamador tuvo que tocarse al partirlo —
que es lo que hizo el corte barato. Importar directamente de aquí no está
prohibido, pero tampoco es la superficie declarada: los puertos del contexto de
gobernanza siguen nombrando `vault_norms:NORM_CATALOG` y compañía.

**Por qué el vocabulario de estado vive aquí y no en el motor.** `STATUS_VOCAB`,
`LIFECYCLE_REGISTRY`, `STATUS_SYNONYMS`, `STATUS_TRANSITIONS` y
`DOMAIN_STATUS_VOCABS` son lo mismo que el catálogo: la declaración de qué es
legítimo. Las cuatro funciones que los acompañan —`normalize_status`,
`split_domain_status`, `status_frontmatter_lines`, `_canonical_status`— son
puras y no hacen otra cosa que consultarlos; separarlas de sus datos habría
creado un cruce donde no hay ninguno.
"""

from __future__ import annotations


import ast
import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# ─── La norma como paquete (deuda #10, piloto AP-65) ──────────────────────────
#
# Una norma puede vivir en `normas/<código>/` en vez de escrita aquí: `norma.py`
# con la entrada, `porque.md` con las rutas de las caras que la cumplen y un
# `test_*.py` (los ejecuta `tests/test_normas_paquete.py`). Este módulo sigue
# siendo la fuente única: la carga en el sitio que ocupaba, así que
# `NORM_CATALOG` no cambia de orden. Se lee con `ast.literal_eval` y no se
# importa —el catálogo es hoja y un `norma.py` con código no lo sería—, y la
# ruta sale de este fichero porque en la wheel `_impl/` y `normas/` son
# hermanas igual que `scripts/` y `normas/` en el checkout.

#: Carpeta de los paquetes de norma, junto a la de este módulo.
RAIZ_NORMAS = Path(__file__).resolve().parent.parent / "normas"

#: Códigos que el catálogo carga desde su paquete, en el orden en que los carga.
NORMAS_EN_PAQUETE: List[str] = []

#: Una cara citada en `porque.md`: `ruta/del/fichero.py::símbolo`.
_RE_CARA = re.compile(r"`([\w./-]+\.py)::(\w+)`")


def _leer_norma(fichero: Path) -> Dict[str, Any]:
    """La asignación `NORMA = {...}` de un `norma.py`, sin ejecutarlo."""
    arbol = ast.parse(fichero.read_text(encoding="utf-8"), filename=str(fichero))
    for nodo in arbol.body:
        if (isinstance(nodo, ast.Assign) and len(nodo.targets) == 1
                and isinstance(nodo.targets[0], ast.Name)
                and nodo.targets[0].id == "NORMA"):
            return ast.literal_eval(nodo.value)
    raise ValueError(f"{fichero}: no declara NORMA")


def _desde_paquete(code: str) -> Dict[str, Any]:
    """La entrada de `code`, leída de su paquete. Si falta, el import falla:
    un catálogo al que le falta una norma en silencio es peor que ninguno."""
    NORMAS_EN_PAQUETE.append(code)
    return _leer_norma(RAIZ_NORMAS / code / "norma.py")


def forma_de_paquetes(raiz: Optional[Path] = None,
                      cargadas: Optional[Sequence[str]] = None,
                      raiz_repo: Optional[Path] = None) -> List[Dict[str, str]]:
    """Qué paquetes de norma no tienen la forma declarada.

    Falla si falta `norma.py`, `porque.md` o un `test_*.py`; si el `code` no es
    el nombre de la carpeta; si la carpeta no la carga el catálogo, o la carga
    dos veces; y si `porque.md` cita una cara `ruta::símbolo` que no existe.

    El test y las caras solo se exigen con `raiz_repo`, que es el checkout: la
    wheel no lleva ni los `test_*.py` ni el código de gobernanza que citan, y
    exigirlos allí daría un problema que no lo es.
    """
    raiz = Path(raiz) if raiz else RAIZ_NORMAS
    cargadas = list(NORMAS_EN_PAQUETE if cargadas is None else cargadas)
    if raiz_repo is None and raiz == RAIZ_NORMAS and (raiz.parent / "scripts").is_dir():
        raiz_repo = raiz.parent
    problemas: List[Dict[str, str]] = []

    def falta(paquete: str, problema: str) -> None:
        problemas.append({"paquete": paquete, "problema": problema})

    carpetas = sorted(p for p in raiz.iterdir()
                      if p.is_dir() and not p.name.startswith(("_", "."))) if raiz.is_dir() else []
    for carpeta in carpetas:
        nombre = carpeta.name
        if cargadas.count(nombre) != 1:
            falta(nombre, f"el catálogo la carga {cargadas.count(nombre)} veces, no una")
        for cara in ("norma.py", "porque.md"):
            if not (carpeta / cara).is_file():
                falta(nombre, f"falta {cara}")
        if raiz_repo is not None and not list(carpeta.glob("test_*.py")):
            falta(nombre, "falta un test_*.py")
        if (carpeta / "norma.py").is_file():
            try:
                code = _leer_norma(carpeta / "norma.py").get("code")
            except (SyntaxError, ValueError) as exc:
                falta(nombre, f"norma.py ilegible: {exc}")
            else:
                if code != nombre:
                    falta(nombre, f"declara {code} en la carpeta {nombre}")
        if raiz_repo is not None and (carpeta / "porque.md").is_file():
            texto = (carpeta / "porque.md").read_text(encoding="utf-8")
            for ruta, simbolo in _RE_CARA.findall(texto):
                fichero = Path(raiz_repo) / ruta
                fuente = fichero.read_text(encoding="utf-8") if fichero.is_file() else ""
                if not re.search(rf"^\s*(?:def|class)\s+{simbolo}\b|^{simbolo}\s*=",
                                 fuente, re.M):
                    falta(nombre, f"porque.md cita {ruta}::{simbolo}, que no existe")
    nombres = {c.name for c in carpetas}
    for code in sorted(set(cargadas) - nombres):
        falta(code, "el catálogo la carga y no tiene carpeta")
    return problemas


# ─── Catálogo canónico (fuente de verdad) ──────────────────────────────────────
#
# type:        antipattern | pattern
# category:    content-quality | structure | frontmatter | linking | process
# severity:    critical | high | medium | low  (N/A para patterns)
# enforcement: guard | audit | guard+audit | manual | recommended
#   - guard:     vault_write rechaza en tiempo de escritura
#   - audit:     vault_audit detecta retrospectivamente
#   - guard+audit: ambos
#   - manual:    DEPRECADO (v38) — toda norma debe tener guard o audit; las no
#                automatizables usan audit heurístico (vault_drift_detect)
#   - recommended: patrón positivo a seguir

NORM_CATALOG: List[Dict[str, Any]] = [
    # ── Anti-patrones ──────────────────────────────────────────────────────────
    _desde_paquete("AP-01"),
    _desde_paquete("AP-02"),
    _desde_paquete("AP-03"),
    _desde_paquete("AP-04"),
    _desde_paquete("AP-05"),
    _desde_paquete("AP-06"),
    _desde_paquete("AP-07"),
    _desde_paquete("AP-08"),
    _desde_paquete("AP-09"),
    _desde_paquete("AP-10"),
    _desde_paquete("AP-11"),
    _desde_paquete("AP-12"),
    _desde_paquete("AP-13"),
    _desde_paquete("AP-14"),
    _desde_paquete("AP-15"),
    _desde_paquete("AP-16"),
    _desde_paquete("AP-17"),
    _desde_paquete("AP-18"),
    _desde_paquete("AP-19"),
    _desde_paquete("AP-20"),
    _desde_paquete("AP-21"),
    _desde_paquete("AP-22"),
    # ── Patrones recomendados ──────────────────────────────────────────────────
    _desde_paquete("PAT-1"),
    _desde_paquete("PAT-2"),
    _desde_paquete("PAT-3"),
    _desde_paquete("PAT-4"),
    _desde_paquete("PAT-5"),
    # ── Anti-patrón AP-23 ──────────────────────────────────────────────────────
    _desde_paquete("AP-23"),
    # ── Anti-patrón AP-24 ──────────────────────────────────────────────────────
    _desde_paquete("AP-24"),
    # ── Anti-patrón AP-25 ──────────────────────────────────────────────────────
    _desde_paquete("AP-25"),
    # ── Anti-patrones AP-26..AP-30 ────────────────────────────────────────────
    # Frontmatter incompleto. Estaban aplicados por vault_audit desde v30 (con
    # penalización al health score y etiqueta propia en su salida) pero nunca
    # se registraron aquí: `vault_norms --list` no los mostraba y no tenían
    # severidad, enforcement ni prevención declaradas. El hueco lo detectó el
    # chequeo de contiguidad de vault_sdd_init al dejar de estar clavado en
    # AP-01..AP-25. Registrados sin cambiar el comportamiento del audit.
    _desde_paquete("AP-26"),
    _desde_paquete("AP-27"),
    _desde_paquete("AP-28"),
    _desde_paquete("AP-29"),
    _desde_paquete("AP-30"),
    # ── Anti-patrón AP-31 ──────────────────────────────────────────────────────
    _desde_paquete("AP-31"),
    # ── Anti-patrón AP-32 ──────────────────────────────────────────────────────
    _desde_paquete("AP-32"),
    # ── Anti-patrón AP-33 ──────────────────────────────────────────────────────
    _desde_paquete("AP-33"),
    # ── Anti-patrón AP-34 ──────────────────────────────────────────────────────
    _desde_paquete("AP-34"),
    # ── Anti-patrón AP-35 ──────────────────────────────────────────────────────
    _desde_paquete("AP-35"),
    _desde_paquete("AP-36"),
    # ── Anti-patrón AP-37 ──────────────────────────────────────────────────────
    # Síntoma que la originó: `vault_standard_upgrade --to latest` devolvía
    # `{"ok": true}` habiendo aplicado CERO migraciones, porque _version_index()
    # no normalizaba la minor version y _pending_migrations() devolvía []. El bug
    # sobrevivió versiones enteras porque su respuesta era indistinguible de un
    # éxito real: no había nada en la salida que un test o un agente pudiera
    # contradecir.
    _desde_paquete("AP-37"),
    # ── Anti-patrón AP-38 ──────────────────────────────────────────────────────
    # Síntoma que lo originó: un censo sobre 17 vaults reales (2.929 notas)
    # encontró 54 valores distintos de `status`, de los cuales solo el 6% caía
    # dentro de STATUS_VOCAB — pese a que CN-03 lo audita desde v38. La causa no
    # eran los agentes: el valor no canónico más frecuente, `implementado`
    # (205 notas), lo escribía `vault_pattern_save`. El estándar publicaba NUEVE
    # vocabularios de `status` en competencia y auditaba contra uno solo.
    _desde_paquete("AP-38"),
    # ── Anti-patrón AP-39 ──────────────────────────────────────────────────────
    # Síntoma que lo originó: el mismo censo de 17 vaults midió 1.180 tags
    # distintos para 6.358 usos — el 45% aparece en una sola nota — y 55 familias
    # de casi-duplicados (`ci-cd`/`cicd`/`ci_cd`). El ritmo de invención es plano
    # a lo largo de tres meses (37% → 36% → 34% → 27% → 36%): ninguna sesión
    # hereda el vocabulario de la anterior. La causa, otra vez, era el camino de
    # escritura: `vault_write` consultaba una clave que el tag-registry no tiene,
    # así que la sugerencia no se disparó nunca y un tag inventado costaba cero.
    _desde_paquete("AP-39"),
    _desde_paquete("AP-40"),
    {
        "code": "AP-41",
        "distinguido_de": {
            "CN-03": (
                "CN-03 mira el valor aislado: pertenece al vocabulario. AP-41 mira la "
                "transición: la máquina de estados está declarada y nadie verifica "
                "que los saltos entre valores sean legales. Todos los valores pueden "
                "ser válidos y la secuencia imposible."
            ),
        },
        "name": "Máquina de estados declarada sin verificar",
        "type": "antipattern",
        "category": "lifecycle",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "El estándar declara STATUS_TRANSITIONS —las transiciones válidas del "
            "ciclo de vida de una nota— y no las recorre nadie: su único consumidor "
            "era su propio test de coherencia. Un estado que no controla su "
            "transición es una etiqueta, no un ciclo de vida: una nota 'archived' "
            "podía volver a 'draft', o saltar de 'planned' a 'verified' sin pasar "
            "por revisión, y ningún guard lo veía. Es la misma forma del fallo "
            "histórico del estándar —declarar sin ejecutar— con la agravante de que "
            "existía un test en verde que verificaba que el grafo estaba bien "
            "dibujado, no que alguien lo recorriera."
        ),
        "signal": (
            "Secuencias de `status` en .history/ que no siguen ninguna arista de "
            "STATUS_TRANSITIONS; notas cuyo estado retrocede sin explicación; "
            "ningún script fuera de los tests importa STATUS_TRANSITIONS."
        ),
        "prevention": (
            "vault_write lee el `status` de la nota en disco antes de sobrescribirla "
            "y rechaza la transición que no está en STATUS_TRANSITIONS, citando los "
            "destinos válidos. Una actualización que no menciona `status` conserva el "
            "estado previo en vez de caer al default 'draft'. Las transiciones ya "
            "ocurridas se reportan desde .history/ con vault_norms --audit: se anotan, "
            "no se reescriben, porque el estado actual es un hecho."
        ),
        "tools_enforcing": ["vault_write"],
        "tools_detecting": ["vault_norms"],
        "introduced_version": "v39",
    },
    {
        "code": "AP-42",
        "distinguido_de": {
            "AP-04": (
                "AP-04 mide la nota: describe como entregado algo que no lo está. "
                "AP-42 mide la tool: está publicada en el catálogo y nunca se "
                "ejecutó. El discriminador es el sujeto medido —texto frente a "
                "artefacto ejecutable—, y por eso una la detecta el audit de "
                "contenido y la otra el smoke."
            ),
        },
        "name": "Tool publicada sin haberse ejecutado nunca",
        "type": "antipattern",
        "category": "process",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "Una tool se publica en el catálogo MCP porque responde a `--help` y "
            "porque su entrada existe. `--help` demuestra que el argparse se "
            "construye: no que el módulo importe sus dependencias, ni que el ejemplo "
            "documentado sea aceptado por la CLI, ni que la salida sea el JSON que el "
            "contrato promete. La primera medición dio 41 de 87 tools cuyo ejemplo "
            "documentado no llegaba a emitir un JSON con `ok` —36 de ellas porque el "
            "ejemplo del catálogo usaba flags que la CLI rechazaba, exactamente el "
            "defecto de AP-40 trasladado a la superficie de documentación."
        ),
        "signal": (
            "Ejemplos del catálogo o del README que salen con exit 2 y "
            "'unrecognized arguments'; tools cuya salida es texto para humanos sin "
            "modo JSON; tools que no aparecen en ningún test ni en ninguna ejecución."
        ),
        "prevention": (
            "vault_smoke ejecuta el ejemplo documentado de cada tool contra una copia "
            "desechable del vault de pruebas y exige tres cosas: que termine, que su "
            "salida sea JSON y que ese JSON tenga `ok`. Un `ok: false` bien formado "
            "aprueba: lo que se persigue es el fallo mudo. La baseline solo puede "
            "encoger y quedó en 0, así que es un guard duro desde el primer día. Las "
            "tools sin invocación posible (un servicio HTTP que no retorna) se "
            "declaran en SIN_SMOKE con su motivo, nunca se omiten en silencio."
        ),
        "tools_enforcing": ["vault_smoke"],
        "tools_detecting": ["vault_smoke", "vault_norms"],
        "introduced_version": "v39",
    },
    {
        "code": "AP-43",
        "distinguido_de": {
            "AP-40": (
                "AP-40 es la contradicción visible: el contrato publicado acepta algo "
                "que la CLI rechaza. AP-43 es la ausencia: la norma existe y el punto "
                "de uso no la menciona ni la aplica. El discriminador es si hay dos "
                "afirmaciones en conflicto o solo una sin refuerzo."
            ),
        },
        "name": "Norma sin refuerzo en el punto de uso",
        "type": "antipattern",
        "category": "governance",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "El catálogo de normas está completo, versionado y con guards, pero el "
            "agente que documenta el vault no lo tiene delante mientras trabaja: se "
            "entera de que una norma existe cuando la incumple —y solo si esa norma "
            "es una de las 14 que previenen, no una de las 33 que se limitan a "
            "detectar en un audit que puede no correrse nunca. El refuerzo llega "
            "tarde, fuera de contexto o no llega. Una norma que el agente no ve en el "
            "momento de escribir no gobierna la escritura: gobierna el post-mortem."
        ),
        "signal": (
            "Normas que ninguna tool declara en tools_enforcing ni tools_detecting "
            "(no se pronuncian nunca); resultados de tool que no llevan bloque "
            "`vault_says`; agentes que repiten el mismo antipatrón entre sesiones."
        ),
        "prevention": (
            "vault_errors.wrap_main —el único punto por el que ya pasa la salida de "
            "todas las tools— añade a cada resultado un bloque `vault_says` derivado "
            "de NORM_CATALOG y del estado real de esa llamada: qué norma acaba de "
            "actuar, cuántas notas cambiaron, qué mirar a continuación. El refuerzo "
            "rota entre las normas que gobiernan esa tool para no degradarse en ruido "
            "fijo. vault_voice --coverage nombra las normas que ninguna tool pronuncia."
        ),
        "tools_enforcing": ["vault_voice", "vault_errors"],
        "tools_detecting": ["vault_voice", "vault_norms"],
        "introduced_version": "v39",
    },
    {
        "code": "AP-44",
        "name": "Verificación autoconsistente — la tool se certifica a sí misma",
        "type": "antipattern",
        "category": "quality",
        "severity": "critical",
        "enforcement": "guard+audit",
        "description": (
            "Una tool escribe o mide con un criterio propio y verifica el resultado "
            "con ESE MISMO criterio, en vez de con el que usa el consumidor real "
            "—Obsidian al resolver un enlace, el parser de Mermaid al dibujar, YAML "
            "al leer un frontmatter, el audit del propio estándar al juzgar la nota "
            "que otra tool acaba de escribir. La tool queda internamente coherente y "
            "por eso mismo ciega a su propio fallo: no puede detectar el error porque "
            "lo comete en los dos lados de la comparación. Es más caro que un bug "
            "normal, porque el guard sale en verde y dirige el trabajo hacia donde no "
            "hay problema: reescribir enlaces que funcionan, 'corregir' diagramas "
            "válidos, retaguear notas ya etiquetadas."
        ),
        "signal": (
            "Dos tools del estándar dan cifras distintas para lo mismo (146 vs 86 "
            "enlaces rotos); un hallazgo desaparece al normalizar y reaparece al "
            "abrir el vault; el generador de una nota produce metadatos que el audit "
            "del mismo estándar reprueba; un 'arreglo' se declara aplicado y el "
            "usuario sigue viendo el problema; el 100% de una categoría de hallazgos "
            "resulta falsa al inspeccionarla a mano."
        ),
        "prevention": (
            "Verificar con el criterio del consumidor, no con el propio: resolver "
            "wikilinks por nombre de fichero y `aliases:` —nunca por `title:`, que "
            "Obsidian no mira—, leer frontmatter con `yaml.safe_load` y no con un "
            "regex por líneas, y validar Mermaid contra su gramática real. Toda tool "
            "que escribe reevalúa el resultado releyendo del disco. Un frontmatter "
            "ilegible devuelve error explícito, nunca `{}` silencioso, que es lo que "
            "hace que un write path anteponga un segundo bloque y corrompa la nota. "
            "Y toda medida se contrasta contra un vault preexistente ajeno al "
            "estándar: `vault-sandbox/` lo genera el propio estándar y comparte sus "
            "supuestos, así que no puede exhibir este fallo."
        ),
        # v40.28 — la gramática de Mermaid se mudó a `vault_mermaid_reglas`
        # (AP-62), y con ella el sitio que aplica AP-44: validar contra la
        # gramática real y no contra el criterio del generador. Se nombra al
        # dueño, no a la fachada, porque la traza tiene que llevar al código.
        "tools_enforcing": ["vault_audit", "vault_graph_fix", "vault_mermaid_reglas"],
        "tools_detecting": ["vault_norms", "vault_audit"],
        "distinguido_de": {
            "AP-55": (
                "AP-44 se comete al verificar: la tool mide con su propia "
                "normalización y queda ciega a su error. AP-55 está en el dato "
                "antes de que nadie verifique: dos registros canónicos afirman "
                "cosas distintas sobre el mismo hecho. Un catálogo puede ser "
                "coherente y estar verificado por un guard autoconsistente "
                "(AP-44 solo), o ser incoherente aunque el guard mire fuera "
                "(AP-55 solo). Se dieron juntos en v40.10, que es por lo que "
                "conviene tenerlos separados por escrito."
            )
        },
        "introduced_version": "v39",
    },
    {
        "code": "AP-45",
        "distinguido_de": {
            "AP-20": (
                "AP-45 es la nota que existe para que la sección no aparezca vacía: "
                "la cobertura se afirma sin evidencia detrás. AP-20 es la nota que "
                "tiene estructura y listas vacías. AP-45 se mide contra lo que la "
                "nota dice cubrir; AP-20, contra su propio contenido."
            ),
            "CN-04": (
                "AP-45 mide si el cuerpo tiene evidencia; CN-04, solo si la nota "
                "abre diciendo qué es. Poner el H1 no salda AP-45: una nota con "
                "título y sin evidencia sigue incumpliéndola."
            ),
        },
        "name": "Cobertura sin evidencia — la nota existe para llenar la sección",
        "type": "antipattern",
        "category": "quality",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "Una nota se crea porque una sección estaba vacía, no porque hubiera algo "
            "que afirmar. Su cuerpo son encabezados y marcadores de pendiente "
            "—`_Pendiente_`, `TODO`, `— No detectados`— y no enlaza con nada. Sube la "
            "cobertura y baja la fiabilidad: el conteo de notas dice que la sección "
            "está cubierta, el health score la cuenta como nota real, y el siguiente "
            "lector la abre esperando contenido. Es más caro que la ausencia, porque "
            "la ausencia sí se ve: un hueco invita a llenarlo, un relleno declara que "
            "ya está hecho. El generador que la escribió creía estar documentando."
        ),
        "signal": (
            "Notas cuyo cuerpo bajo el frontmatter, quitados encabezados y "
            "marcadores, queda vacío y sin wikilinks salientes; secciones que pasan "
            "de 0 a N notas en una sola ejecución de una tool; ADRs numerados sin "
            "nombre; conceptos cuyo cuerpo entero remite a leer otra fuente."
        ),
        "prevention": (
            "No escribir la nota sin evidencia detrás. Un generador que no encuentra "
            "contenido real para una sección lo declara en `warnings` y en "
            "`next_steps` —que es información útil— en vez de emitir un stub, que es "
            "desinformación. El andamiaje declarado sí es legítimo: los primers de "
            "vault_init llevan `status: template` y quedan exentos, porque anuncian "
            "lo que son. Secciones dirigidas por eventos (18_Bugs, 19_Audits, "
            "20_Quarantine) se quedan vacías hasta que ocurre el evento."
        ),
        "tools_enforcing": ["vault_onboard", "vault_write"],
        "tools_detecting": ["vault_norms", "vault_audit"],
        "introduced_version": "v39",
    },
    # ── Antipatrón AP-46 ───────────────────────────────────────────────────────
    {
        "code": "AP-46",
        "distinguido_de": {
            "AP-12": (
                "AP-12 es el síntoma medido en las notas: dos notas del mismo tipo "
                "con frontmatter distinto. AP-46 es la causa medida en el código: no "
                "hay escritor único de frontmatter. Se separan porque el vault puede "
                "quedar coherente a mano con la causa intacta."
            ),
            "AP-48": (
                "AP-46 es el caso particular de AP-48 sobre el frontmatter: cada tool "
                "lo escribe a su manera en vez de pasar por un escritor único. AP-48 "
                "es la forma general: la misma funcionalidad implementada dos veces, "
                "una por camino de acceso. Se declara así para que saldar AP-46 no se "
                "lea como haber saldado AP-48."
            ),
        },
        "name": "Frontmatter a mano — cada tool es su propio escritor",
        "type": "antipattern",
        "category": "consistency",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "Veintiséis tools montan el frontmatter concatenando líneas y tres "
            "importan el write path canónico. Cada concatenación es un segundo autor "
            "del formato sin guard detrás: el bloque se cierra o no, `type:` está o "
            "no, la fecha lleva el formato de quien la escribió. El fallo no se ve "
            "al escribir —la tool devuelve `ok: true` porque el fichero se creó— "
            "sino al auditar, y para entonces la nota ya es el dato. Es el mismo "
            "patrón que produjo 22 implementaciones de `slugify` y tres verdades "
            "para la lista de secciones: una fuente única declarada en la "
            "documentación y N implementaciones en el código. `vault_migrate_docs` "
            "cortaba el documento por la línea 7 y llevaba versiones publicándose "
            "así, con el bloque de frontmatter sin cerrar."
        ),
        "signal": (
            "Notas con `---` de apertura que nunca cierra o cuyo bloque no parsea "
            "con `yaml.safe_load`; notas sin `type:` recién escritas por una tool; "
            "tools que construyen listas de líneas de frontmatter en vez de llamar "
            "al write path; el generador aprueba y `vault_audit` reporta "
            "`missingFrontmatter` sobre lo que él mismo acaba de escribir."
        ),
        "prevention": (
            "El write path valida lo que escribe releyendo el resultado, no "
            "confiando en cómo se construyó: `atomic_write_text` rechaza un bloque "
            "de frontmatter que abre y no cierra o que no parsea, y registra el que "
            "parsea pero sale sin `type:`. Así el guard alcanza a las 26 tools sin "
            "reescribir ninguna, y la adopción de `vault_write` puede ser gradual. "
            "Verificar con el criterio del consumidor —`yaml.safe_load`, no un "
            "regex por líneas— es AP-44 aplicado al generador."
        ),
        "tools_enforcing": ["vault_io.atomic_write_text", "vault_write"],
        # AP-46 es una norma sobre **tools**, no sobre notas: dice que veintiséis
        # tools montan el frontmatter a mano. `vault_audit` audita notas y no
        # puede verlo. Quien lo mide es `vault_norms`.
        "tools_detecting": ["vault_norms"],
        "introduced_version": "v39.3",
    },
    # ── Antipatrón AP-47 ───────────────────────────────────────────────────────
    {
        "code": "AP-47",
        "name": "Artefacto derivado desfasado — el índice dejó de reflejar el disco",
        "type": "antipattern",
        "category": "consistency",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "El vault es la fuente de verdad y `search-index.json` y `graph.json` "
            "son proyecciones suyas. Una escritura que no pasa por `vault_write` "
            "—un agente remoto, una tool que escribe la nota y no toca el índice, "
            "una copia a mano— deja la proyección atrás, y a partir de ahí el "
            "agente busca sobre un mapa viejo: la nota existe y `vault_search` no "
            "la encuentra, así que la vuelve a escribir. La duplicación no es un "
            "descuido del agente, es la consecuencia lógica de un índice que "
            "miente.\n\n"
            "El estándar no lleva base de datos por decisión normativa, y con "
            "consistencia eventual el desfase es esperable. Lo que no es "
            "aceptable es que **nadie lo mida**: `vault_reindex --check` "
            "comprobaba `len(notes) > 0`, de modo que un índice con una entrada "
            "sobre un vault de 300 notas pasaba la puerta."
        ),
        "signal": (
            "`vault_reindex --check` devuelve `index_stale`; el conteo de `.md` en "
            "las secciones canónicas no coincide con las entradas de "
            "`search-index.json`; `vault_search` devuelve 0 resultados sobre una "
            "nota que está en disco; `graph.json` tiene menos nodos que notas."
        ),
        "prevention": (
            "`vault_reindex --check` contrasta disco contra índice con el mismo "
            "criterio con el que reconstruye —una sola función, `_notas_en_disco()`, "
            "para que la comprobación y el arreglo no puedan medir cosas distintas "
            "(AP-44)— y reporta las dos direcciones: notas invisibles para la "
            "búsqueda y entradas que apuntan a ficheros que ya no están. El "
            "remedio es `vault_reindex`, y por eso la norma se audita en vez de "
            "bloquear: el desfase es un estado a reconciliar, no una escritura a "
            "rechazar."
        ),
        "tools_enforcing": ["vault_reindex", "vault_write"],
        "tools_detecting": ["vault_norms", "vault_reindex"],
        "distinguido_de": {
            "AP-59": (
                "AP-47 es la **cifra** escrita a mano en la documentación; AP-59 "
                "es su versión estructural, la **lista** escrita a mano en el "
                "código. Comparten disciplina —derivar en vez de escribir— y por "
                "eso los umbrales de AP-59 no pueden ser literales sin cometer "
                "AP-47 dentro de AP-59."
            ),
        },
        "introduced_version": "v39.3",
    },
    {
        "code": "AP-48",
        "distinguido_de": {
            "AP-46": (
                "AP-46 es el caso particular de AP-48 sobre el frontmatter: cada tool "
                "lo escribe a su manera en vez de pasar por un escritor único. AP-48 "
                "es la forma general: la misma funcionalidad implementada dos veces, "
                "una por camino de acceso. Se declara así para que saldar AP-46 no se "
                "lea como haber saldado AP-48."
            ),
        },
        "name": "Implementación paralela por camino de acceso",
        "type": "antipattern",
        "category": "consistency",
        "severity": "critical",
        "enforcement": "guard+audit",
        "description": (
            "La misma tool publicada tiene dos implementaciones y cuál se ejecuta "
            "depende de por dónde entres. No es una fachada sobre un núcleo "
            "común: son dos cuerpos de código que nadie contrasta, con un solo "
            "nombre y un solo contrato publicado — así que el contrato describe "
            "como mucho a uno de los dos.\n\n"
            "Es AP-05 (múltiples fuentes de verdad) desplazado del dato al camino "
            "de ejecución, y se le parece poco en lo importante: dos definiciones "
            "de un vocabulario acaban divergiendo y alguien lo nota al leerlas, "
            "mientras que dos implementaciones divergen **en silencio** porque "
            "cada una tiene su propio público. La suite prueba una; el agente "
            "ejecuta la otra; las dos están verdes.\n\n"
            "Medido en v39.5 sobre el servidor MCP: nueve tools con backend "
            "nativo en Node, siete de ellas con script Python del mismo nombre. "
            "Ninguna de las siete compartía un solo campo de envelope con el "
            "contrato de `00_System/tool-spec.json` — `vault_fundamentals` "
            "devolvía `compliance_pct`/`passed` donde el contrato dice "
            "`path`/`total`. Y la divergencia peor no era de forma sino de "
            "efecto: la implementación nativa de `vault_graph` no escribía el "
            "grafo, así que un agente la llamaba, recibía `ok: true` y el índice "
            "se quedaba desfasado — AP-37 y AP-47 servidos por el único camino "
            "que un agente real usa. `vault_smoke` recorría las 91 tools del "
            "catálogo ejecutando el `.py`: probaba exactamente la implementación "
            "que el agente no toca."
        ),
        "signal": (
            "Una tool del catálogo tiene backend nativo en el servidor MCP **y** "
            "script en `scripts/`; el envelope que devuelve por MCP no cubre los "
            "`declared_returns` de su contrato; un side effect declarado en el "
            "contrato no ocurre por uno de los dos caminos."
        ),
        "prevention": (
            "Backend nativo solo para lo que **no tiene** implementación en "
            "Python; todo lo demás cae al runner, que es donde vive el contrato "
            "publicado. La implementación desplazada no se borra (no-derogación): "
            "se anota `superseded_by:` y se deja fuera del despacho. La regla se "
            "comprueba por comportamiento y no por lectura del código — se llama "
            "la tool por MCP y se contrasta el envelope contra el contrato, que "
            "es el criterio del consumidor y no el propio (AP-44)."
        ),
        "tools_enforcing": ["vault_mcp_catalog"],
        "tools_detecting": ["vault_norms", "vault_mcp_catalog"],
        "introduced_version": "v39.5",
    },
    {
        "code": "AP-49",
        "name": "Vínculo resuelto en tiempo de import",
        "type": "antipattern",
        "category": "architecture",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "Un módulo deriva su ruta, su configuración o su dependencia en el "
            "momento de **importarse**, no en el de usarse. `SYSTEM_DIR = "
            "VAULT_ROOT / '00_System'` a nivel de módulo se evalúa una sola vez, "
            "cuando el intérprete carga el fichero, y a partir de ahí es una "
            "constante.\n\n"
            "Lo grave no es la constante: es que deja **inerte una costura que "
            "existe**. `vault_io.set_vault_root()` está publicado y 12 tests lo "
            "usan, pero no puede reapuntar a un módulo que ya calculó su ruta al "
            "cargar. La inyección parece disponible y no lo está, que es peor que "
            "no tenerla — quien la usa cree haber redirigido la escritura.\n\n"
            "Medido en v40.0 por el propio guard: **0 vínculos congelados en "
            "0 módulos**. "
            "Eran 82 en 62 módulos antes de empezar a migrar contextos al "
            "dominio, y cayeron uno a uno: Durabilidad los dejó en 77, "
            "Índices en 69, Grafo en 51, Consulta en 45, Gobernanza en 38, "
            "Ciclo de vida en 34, Meta-toolkit en 31 y Autoría —donde estaban "
            "los 31 últimos, el 100% de la deuda que quedaba— en 0. Llegar a "
            "cero destapó la otra mitad de la norma: veinte módulos seguían "
            "haciendo `from vault_io import VAULT_ROOT` y usándolo **dentro de "
            "funciones**. No son asignaciones de nivel de módulo, así que el "
            "guard los daba por limpios, y seguían dependiendo del paliativo de "
            "reanclaje que el refactor existe para no necesitar. Se mide aparte "
            "(`raw_vault_root_imports`), también en cero, y el caso legítimo se "
            "pide con alias. La "
            "cifra es la que "
            "cuenta `vault_arch --check`, no una estimación a ojo: la norma y su "
            "puerta miden lo mismo o la norma no es comprobable. La consecuencia visible era "
            "que `cli/runner.py` aislaba cada tool en un subproceso citando "
            "«estado a nivel de módulo» como razón: el aislamiento por proceso "
            "no era una decisión de diseño libre sino la compensación de este "
            "acoplamiento. Saldada la deuda, esa razón caducó y quedó anotada "
            "allí mismo; el subproceso se conserva por las otras dos que siguen "
            "siendo ciertas —timeout que puede matar lo que vigila, y envelope "
            "sin reinterpretar—. El refactor lo hizo posible, no conveniente."
        ),
        "signal": (
            "Las pruebas necesitan subprocesos para aislarse unas de otras; "
            "`set_vault_root()` no cambia dónde escribe una tool; dos raíces de "
            "vault no pueden coexistir en el mismo intérprete; una asignación de "
            "nivel de módulo deriva de `VAULT_ROOT` sin pasar por "
            "`get_vault_root()`."
        ),
        "prevention": (
            "La raíz y sus derivadas se reciben, no se importan: el dominio toma "
            "un contexto (`VaultContext`) y el adaptador lo construye por "
            "llamada. Si un módulo necesita la ruta, la resuelve **tarde** con "
            "`get_vault_root()` dentro de la función. El guard es AST sobre "
            "asignaciones de nivel de módulo que derivan de `VAULT_ROOT`, con "
            "baseline que solo puede encoger — la deuda medida no se arregla en "
            "un commit, pero no puede crecer."
        ),
        "tools_enforcing": ["vault_arch"],
        "tools_detecting": ["vault_norms", "vault_arch"],
        "distinguido_de": {
            "AP-58": (
                "AP-49 mira **cuándo** se resuelve un vínculo: un valor "
                "copiado en tiempo de import deja de responder a un reanclaje. "
                "AP-58 mira la **dirección** de la dependencia, no su momento. "
                "Se tocan porque el ciclo del núcleo es parte de lo que obliga "
                "a congelar vínculos, pero un módulo puede tener ciclos sin un "
                "solo vínculo congelado, y al revés."
            )
        },
        "introduced_version": "v40.0",
    },
    {
        "code": "AP-50",
        "name": "Decisión duplicada sin dueño declarado",
        "type": "antipattern",
        "category": "architecture",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "La misma **decisión** —qué valores son válidos, cuál es el default, "
            "cómo se escapa un campo— se toma en más de un punto de uso sin que "
            "ningún registro declare quién manda. No es AP-05: aquel habla de un "
            "**dato** con dos fuentes, y se ve porque las dos copias divergen. "
            "Esto se ve cuando ya divergieron, que es tarde.\n\n"
            "Lo que lo hace caro es que cada copia parece correcta en su sitio. "
            "`SEVERITIES = ['critical', 'high', 'medium', 'low']` no está mal "
            "escrito en ninguno de los catorce ficheros donde se midió; está mal "
            "que sean catorce y que nada los compare. El día que el registro "
            "cambie, la copia que se quede atrás rechazará un valor válido o "
            "aceptará uno inventado, y ningún test lo notará porque cada fichero "
            "sigue siendo coherente consigo mismo.\n\n"
            "Medido en v40.1 por sus tres guards: **0 copias de vocabulario, 0 "
            "lecturas de entorno sin declarar, 0 vocabularios sin contexto "
            "dueño**. Eran 14 copias del vocabulario en 13 módulos —cuatro como "
            "`choices=` de argparse y diez como constante— y 13 variables de "
            "entorno con su default escrito en cada punto de lectura, de las que "
            "solo seis estaban documentadas. Dos ya habían divergido antes de "
            "que existiera el guard: `VAULT_VOICE` se comparaba contra "
            "`'verbose'` en un módulo y contra `'0'` con default `'1'` en otro, y "
            "`VAULT_MCP_LOG` estaba declarada como fichero de log mientras el "
            "único código que la lee la usa como nivel con default `'info'`.\n\n"
            "El dueño es la mitad que faltaba. `vault_norms.DOMAIN_STATUS_VOCABS` "
            "ya había resuelto esto para `status` en v39 y se quedó solo: "
            "compartir la constante evita la copia, pero no contesta quién decide "
            "cuándo cambia. Por eso cada entrada del registro declara el contexto "
            "acotado que manda sobre ella, y ese contexto tiene que existir en "
            "`vault_arch.CONTEXTS`."
        ),
        "signal": (
            "Un literal de lista o de tupla reproduce —en cualquier orden— un "
            "vocabulario que el registro ya declara; un `os.environ.get()` con "
            "un default escrito en el punto de lectura; un `choices=` de argparse "
            "con valores en duro; dos módulos que escriben el mismo campo con "
            "criterios de escapado distintos; un vocabulario declarado sin "
            "contexto dueño."
        ),
        "prevention": (
            "Registro canónico con dueño, consumidores derivados, guard sin "
            "baseline. Los vocabularios cerrados en `vault_vocabulario.py`, la "
            "configuración en `vault_entorno.py`, y `vault_arch --check` "
            "fallando si aparece una copia, una lectura sin declarar o un "
            "vocabulario huérfano. **Sin baseline a propósito**: las catorce "
            "copias se saldaron al declarar el registro, así que la puerta nace "
            "en cero y una baseline solo serviría para admitir la número quince. "
            "Lo que ya tiene registro canónico no se copia: se declara "
            "`derivado_de` y se resuelve al llamarse, nunca al importarse "
            "(AP-49). Un dato canónico que no es puerto de su contexto se acaba "
            "copiando — los tres registros que `AGENTS.md` declara fuente única "
            "de verdad se leían por fuera de la superficie publicada, y así "
            "nacieron las catorce copias."
        ),
        "tools_enforcing": ["vault_arch"],
        "tools_detecting": ["vault_norms", "vault_arch"],
        "distinguido_de": {
            "AP-57": (
                "AP-50 mira **datos** duplicados —vocabularios, defaults, "
                "regex—: dos copias que divergen se ven al compararlas. AP-57 "
                "mira **criterios** enterrados en una condición, donde no hay "
                "dato que comparar y la divergencia solo aparece por el "
                "resultado equivocado."
            )
        },
        "introduced_version": "v40.1",
    },
    {
        "code": "AP-51",
        "distinguido_de": {
            "AP-52": (
                "Las dos son fallos del manejo de error en una tool. AP-51 es la "
                "atribución: la tool devuelve un vacío que culpa al dato de su propio "
                "fallo. AP-52 es la forma: el envelope de error se emite fuera del "
                "contrato de ERROR_CATALOG. Un error puede estar bien atribuido y mal "
                "formado, y al revés."
            ),
            "AP-61": (
                "Son los dos extremos del mismo eje. AP-51 es el handler "
                "**demasiado ancho**: captura de más, se traga el fallo propio y "
                "devuelve un vacío indistinguible de un resultado legítimo. "
                "AP-61 es el handler **demasiado estrecho**: nombra menos de lo "
                "que la llamada lanza, así que no se traga nada — deja pasar. El "
                "discriminador es que pasa después del fallo: con AP-51 la tool "
                "sigue y miente, con AP-61 la tool cae."
            ),
        },
        "name": "La tool culpa al dato de su propio fallo",
        "type": "antipattern",
        "category": "quality",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "Una tool falla al leer o al interpretar algo, se traga el fallo y "
            "devuelve un vacio que el llamante no puede distinguir de un "
            "resultado legitimo. El error deja de ser un error y pasa a ser un "
            "**hecho sobre el vault**: el informe que lo agregue dira que N "
            "notas no tienen aliases, y no sera cierto \u2014 es que no se "
            "pudieron leer.\n\n"
            "No es lo mismo *no hay* que *no pude mirar*, y esa es toda la "
            "norma. AP-44 cubre la mitad de arriba \u2014verificar con el "
            "criterio del consumidor y no con el propio\u2014; esta cubre la de "
            "abajo, que es el mecanismo por el que un fallo propio acaba "
            "pareciendo un dato malo. Salio al ejecutar contra un vault ajeno "
            "al estandar (**regla 7**): tres tools declaraban invalidas notas "
            "que Obsidian leia sin problema. Las notas estaban bien; el "
            "criterio que las media, no.\n\n"
            "Lo que la norma **no** prohibe es capturar amplio. Prohibe "
            "capturar amplio y callarse: devolver `ok: false` con el error es "
            "correcto porque el llamante recibe la mala noticia y decide. "
            "Capturar `FileNotFoundError` tampoco infringe: es un criterio, el "
            "autor sabe que tolera y por que. Lo que infringe es `except "
            "Exception: return []`.\n\n"
            "Medida en v40.1: **86 sitios en 37 modulos**. Nace con baseline "
            "por la misma razon que AP-37 \u2014que empezo en 55 y llego a "
            "0\u2014: un guard que falla en 86 sitios se desactiva el primer "
            "dia, y un guard desactivado no protege nada. La baseline solo "
            "puede encoger.\n\n"
            "El propio detector estreno el fallo que persigue. La primera "
            "version midio 101 sitios porque clasificaba `except "
            "yaml.YAMLError` como captura amplia: son `ast.Attribute` y no "
            "`ast.Name`, asi que caian en la rama del `except` desnudo. "
            "Contaba como infraccion justo las capturas mas precisas del "
            "repo. Quince falsos positivos, y el error era el de AP-44 "
            "cometido dentro del guard."
        ),
        "signal": (
            "Un `except Exception` o un `except` desnudo cuya unica salida es "
            "`return []`, `return {}`, `return None`, `pass` o `continue`; un "
            "recuento agregado que no distingue el cero medido del cero por "
            "fallo de lectura; un veredicto sobre una nota emitido por un "
            "camino que ya habia fallado."
        ),
        "prevention": (
            "Capturar la excepcion concreta que se sabe tolerar, y si se "
            "captura amplio, **exponer**: devolver el fallo en el envelope en "
            "vez de un vacio. Cuando el vacio es la respuesta correcta, "
            "distinguirlo del vacio por fallo con un campo aparte "
            "(`unreadable`, `errors`) para que el agregado no los confunda. "
            "`vault_blame_audit --check --strict` mide por AST y no por "
            "texto: un detector que buscara la cadena `except Exception` no "
            "veria la diferencia entre devolver un vacio y devolver un "
            "envelope con `ok: false`, que es toda la distincion que la norma "
            "sostiene."
        ),
        "tools_enforcing": ["vault_blame_audit"],
        # No se lista `vault_norms --audit`: ese audita el **contenido del
        # vault**, y esta norma es sobre el codigo de las tools. Declararlo
        # aqui seria una tool_detecting que no detecta nada, que es la misma
        # afirmacion no falsable que AP-37 persigue.
        "tools_detecting": ["vault_blame_audit"],
        "introduced_version": "v40.1",
    },
    {
        "code": "AP-52",
        "distinguido_de": {
            "AP-51": (
                "Las dos son fallos del manejo de error en una tool. AP-51 es la "
                "atribución: la tool devuelve un vacío que culpa al dato de su propio "
                "fallo. AP-52 es la forma: el envelope de error se emite fuera del "
                "contrato de ERROR_CATALOG. Un error puede estar bien atribuido y mal "
                "formado, y al revés."
            ),
        },
        "name": "El error se emite fuera del contrato del catalogo",
        "type": "antipattern",
        "category": "quality",
        "severity": "medium",
        "enforcement": "guard+audit",
        "description": (
            "Una tool falla, lo dice, y lo dice mal: devuelve `{\"ok\": false, "
            "\"error\": \"...\"}` escrito a mano en vez de pasar por "
            "`vault_errors.emit_error`. La frase es correcta; el contrato, no. "
            "El envelope del catalogo trae `error_code`, `category`, "
            "`severity`, `recovery` y `timestamp`; el escrito a mano no trae "
            "ninguno.\n\n"
            "Importa porque el consumidor no lee la frase: **decide por el "
            "codigo**. El servidor MCP y `cli/` deciden si reintentar, abortar "
            "o pedir permiso mirando `error_code` y `recovery.action`. Sin "
            "ellos, un fallo con recuperacion conocida llega como un fallo "
            "opaco, y la unica salida del agente que lo recibe es adivinar.\n\n"
            "Es AP-05 aplicada al **contrato de error** \u2014hay un registro "
            "que declara como se nombra y se recupera cada fallo, y 158 sitios "
            "que lo deciden por su cuenta\u2014 y es AP-51 vista desde el otro "
            "lado: alli el fallo se disfrazaba de dato, aqui llega como fallo "
            "pero desnudo de todo lo que lo hace accionable.\n\n"
            "Salio de la caracterizacion maliciosa: invocar las 94 tools de "
            "forma malformada y mirar **como** fallan, no si fallan. El grueso "
            "estaba limpio \u2014las 45 tools con `required_args` rechazan la "
            "invocacion vacia por argparse, y las 92 tools Python rechazan un "
            "flag desconocido\u2014 y el hallazgo estaba en la forma del "
            "envelope, no en su ausencia.\n\n"
            "Medida en v40.2: **158 sitios en 58 modulos**. Nace con baseline "
            "por la misma razon que AP-37 y AP-51: un guard que falla en 158 "
            "sitios se desactiva el primer dia. La baseline solo puede "
            "encoger.\n\n"
            "El guard mide **forma y no flujo**: un dict con `ok: False` y "
            "pinta de envelope que no lleva `error_code`. No sigue el valor "
            "hasta stdout, asi que cuenta tambien envelopes internos que nunca "
            "se imprimen. Eso se declara en vez de esconderse: un guard que "
            "promete una precision que no tiene es la clase de afirmacion no "
            "falsable que AP-37 persigue."
        ),
        "signal": (
            "Un literal `{\"ok\": False, \"error\": ...}` en el camino de "
            "salida de una tool; un envelope de fallo sin `error_code`; un "
            "consumidor que tiene que leer `message` con un regex para saber "
            "que paso."
        ),
        "prevention": (
            "Emitir por `emit_error(tool, CODIGO, mensaje)` y, si el codigo no "
            "existe, anadirlo a `ERROR_CATALOG` \u2014 que es donde vive la "
            "decision de como se recupera ese fallo. Anadir el codigo cuesta "
            "una linea; no anadirlo traslada el coste a cada consumidor, para "
            "siempre. `vault_error_contract --check --strict` mide por AST."
        ),
        "tools_enforcing": ["vault_error_contract"],
        # Como en AP-51, no se lista `vault_norms --audit`: audita el
        # contenido del vault, y esta norma es sobre el codigo de las tools.
        "tools_detecting": ["vault_error_contract"],
        "introduced_version": "v40.2",
    },
    {
        "code": "AP-53",
        "distinguido_de": {
            "AP-13": (
                "AP-13 mide el timestamp del frontmatter contra su propio formato: "
                "inválido o incompleto. AP-53 mide la afirmación histórica contra "
                "git: la fecha es valida y no coincide con el commit. El "
                "discriminador es si hay una fuente externa contra la que contrastar."
            ),
        },
        "name": "El historial se afirma a mano y nadie lo contrasta con git",
        "type": "antipattern",
        "category": "quality",
        "severity": "medium",
        "enforcement": "guard",
        "description": (
            "La documentacion afirma un hecho del historial —que la version "
            "v39.0 la introdujo el commit `00731c6` el 2026-07-25— y ese "
            "hecho vive tambien en git, que es donde de verdad existe. Una de "
            "las dos copias se escribe a mano y ninguna se contrasta con la "
            "otra, asi que la de mano se queda atras sin que nada lo note.\n\n"
            "Es AP-05 aplicada al **historial**, y AP-47 en su forma menos "
            "visible: AP-47 persigue cifras escritas a mano —cuantas tools, "
            "cuantas normas— y una fecha o un hash de commit son la misma "
            "clase de dato derivable, solo que nadie los lee como una cifra.\n\n"
            "Medido en v40.7 sobre el changelog del manifiesto: **55 entradas, "
            "31 con hash real, los 31 existen** —ninguno inventado— y "
            "**5 fechas contradecian al commit que citaban**. Cuatro por un dia; "
            "la de v39.0 por once. Esa entrada arrastra ademas un commit de "
            "fijado que corrigio el hash (`13bf9ca -> 00731c6`) y no toco la "
            "fecha: la correccion parcial es el modo de fallo tipico, porque "
            "quien corrige mira el dato que le fallo y no el que viaja con el.\n\n"
            "Detras hay un huevo y una gallina que conviene nombrar, porque es "
            "lo que empuja a escribir el dato a mano: la entrada tiene que citar "
            "el hash del commit que la contiene, y ese hash no existe hasta que "
            "el commit esta hecho. La salida fue un ritual de dos commits "
            "—`feat: vX` con `git: pending`, luego `docs: fijar hash`— "
            "que aparece ocho veces en las ultimas veinte entradas del "
            "historial y cuyo segundo paso depende de que alguien se acuerde. "
            "Una norma que solo prohibe no sirve aqui: hay que dar el comando "
            "que hace el paso, o se seguira haciendo a mano."
        ),
        "signal": (
            "Un hash de commit, una fecha de release o un nombre de rama "
            "escritos en documentacion sin que ninguna tool los verifique "
            "contra el repositorio; un `pending` publicado en una version ya "
            "cerrada; una fecha que no coincide con la del commit que cita."
        ),
        "prevention": (
            "Derivar el dato del repositorio y comprobarlo en una puerta. "
            "`vault_changelog_check --check --strict` contrasta hash, fecha "
            "—de autoria, `%as`, que un rebase no reescribe—, "
            "`pending` y orden. Y `--fijar-hash` convierte en comando el paso "
            "manual que originaba la divergencia."
        ),
        "tools_enforcing": ["vault_changelog_check"],
        "tools_detecting": ["vault_changelog_check"],
        "introduced_version": "v40.7",
    },
    {
        "code": "AP-54",
        "name": "El lock falla y se escribe igual",
        "type": "antipattern",
        "category": "integrity",
        "severity": "high",
        "enforcement": "guard",
        "description": (
            "Un bloque toma un `file_lock`, no lo consigue, y en el handler "
            "escribe de todos modos sin sincronizar. El razonamiento que lleva "
            "ahi es que perder el dato es peor que escribirlo sin lock. Es al "
            "revés, y por una razón que se ve al leer el `TimeoutError`: ese "
            "error significa que **otro lo tiene tomado ahora mismo**. La "
            "escritura del handler no es una carrera improbable, es la unica "
            "situacion en la que ese codigo llega a ejecutarse, y entra justo "
            "encima de la de quien si consiguio el lock.\n\n"
            "Medido en v40.7 en `vault_sdd_init`, que se pasaba del timeout de "
            "60s de la tool y moria dejando `docs/sdd/` a medio escribir "
            "despues de haber anunciado `Drift status: PASS`. La medida: **26 "
            "tomas del lock del fichero de trazas, 13 fallidas, 65,14s de "
            "espera pura** —13 x 5s exactos—. Esas 13 acababan reescribiendo el "
            "trace sin lock mientras el llamante externo lo estaba "
            "reemplazando.\n\n"
            "La causa de las esperas era distinta de la norma y se corrigio "
            "aparte: `file_lock` no era reentrante, asi que un hilo que volvia "
            "a pedir un lock que el mismo sostenia esperaba el timeout entero "
            "contra si mismo. Conviene separar las dos cosas —la causa se "
            "arregla una vez en el kernel; la reaccion es la que se repite en "
            "cada llamante y la que esta norma vigila.\n\n"
            "Omitir la escritura al fallar el lock **no** es esta norma: es la "
            "respuesta correcta, y `vault_quality_check` ya la tenia."
        ),
        "signal": (
            "Un `except TimeoutError` (o un handler mas amplio) alrededor de un "
            "`with file_lock(...)` cuyo cuerpo contiene una llamada de "
            "escritura; una tool que se pasa de su timeout sin trabajo que lo "
            "justifique; un fichero de indice o de trazas con entradas perdidas."
        ),
        "prevention": (
            "Al fallar el lock, descartar la escritura o propagar el error — "
            "nunca escribir sin sincronizar. `vault_arch --check --strict` "
            "reporta el patron en `unsynced_writes`."
        ),
        "tools_enforcing": ["vault_arch"],
        "tools_detecting": ["vault_arch"],
        "distinguido_de": {
            "AP-58": (
                "AP-54 habla de escrituras sin sincronizar; AP-58, de la "
                "dirección de los imports. No se confunden por el tema sino "
                "por el remedio: los dos se arreglan moviendo una "
                "responsabilidad de sitio, y por eso conviene decir cuál toca. "
                "Un ciclo puede vivir entero dentro de un contexto acotado sin "
                "cruzar ninguna frontera — el componente de 14 módulos está "
                "casi todo dentro del kernel."
            )
        },
        "introduced_version": "v40.7",
    },
    {
        "code": "AP-55",
        "name": "El catálogo de normas se certifica a sí mismo",
        "type": "antipattern",
        "category": "process",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "`NORM_CATALOG` declara por norma qué tools la hacen cumplir "
            "(`tools_enforcing`) y cuáles la detectan (`tools_detecting`). Los "
            "dos campos se escriben a mano y nada los contrasta contra lo que "
            "las tools hacen: la cobertura publicada es una promesa sin "
            "verificar.\n\n"
            "Lo caro no es la lista, es el guard. `vault_voice.coverage()` "
            "existe para detectar normas mudas y comprueba que una norma tenga "
            "`tools_enforcing` o `tools_detecting` **leyendo `tools_enforcing` "
            "y `tools_detecting`**. Verifica el catálogo contra el catálogo, "
            "así que da verde sobre las 47 afirmaciones que ningún módulo "
            "respalda y es estructuralmente incapaz de verlas. Es AP-44 "
            "cometido dentro del guard de AP-43 — la tercera vez que el "
            "criterio de verificación sale del objeto verificado, tras el test "
            "de cruces de v40.8 y el cero de AP-52 medido sobre un subconjunto "
            "en v40.9.\n\n"
            "La forma general: **dos registros canónicos que hablan del mismo "
            "hecho no pueden contradecirse sin que algo falle.** Medido en "
            "v40.10: 54 valores de `tools_*` que mezclaban la tool con su flag "
            "y ningún consumidor podía resolver; AP-22 declarada `critical` "
            "mientras `vault_audit` la penalizaba con 2 puntos por unidad "
            "frente a los 5 de AP-24, que el catálogo llamaba `high`; y 47 "
            "afirmaciones de cobertura sin una línea de código que nombre la "
            "norma. `AP-05` —`critical`— nombra `vault_graph_inspect` como "
            "detector, y esa tool no la menciona en ninguna parte."
        ),
        "signal": (
            "Un valor de `tools_*` que no resuelve contra `mapa_de_grupos()`; "
            "una norma cuya `severity` invierte el orden que "
            "`vault_audit.PENALIZACIONES` aplica dentro de su misma familia; un "
            "módulo declarado enforcer que nunca nombra el código de la norma; "
            "un `distinguido_de` que solo declara una de las dos partes."
        ),
        "prevention": (
            "`vault_norms_coherence --check --strict` cruza el catálogo con el "
            "código y con `PENALIZACIONES`. La traza sin respaldo lleva "
            "baseline que solo puede encoger, y se salda de dos formas "
            "honestas: que el código nombre la norma en el sitio que la "
            "aplica, o que el catálogo deje de afirmar una cobertura que no "
            "tiene. Ampliar la baseline es la tercera y no lo es."
        ),
        "tools_enforcing": ["vault_norms_coherence"],
        "tools_detecting": ["vault_norms_coherence"],
        "distinguido_de": {
            "AP-44": (
                "AP-44 es medir con el propio criterio del objeto medido, en "
                "cualquier tool. AP-55 es su caso en el registro normativo: dos "
                "registros canónicos que afirman cosas distintas sobre el mismo "
                "hecho y nada los cruza. AP-44 se comete al verificar; AP-55 "
                "está en el dato antes de que nadie verifique."
            ),
            "AP-60": (
                "AP-55 mira **con qué criterio** se verifica el catálogo; AP-60, "
                "**a cuántos alcanza** esa verificación. C7 nació de que C5 —una "
                "medida de AP-55 correcta y con criterio ajeno— solo recorría a "
                "las 13 normas que habían declarado algo."
            ),
        },
        "introduced_version": "v40.10",
    },
    {
        "code": "AP-56",
        "name": "Frontmatter presente que el consumidor no puede leer",
        "type": "antipattern",
        "category": "metadata-completeness",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "La nota abre `---`, escribe sus claves y, para `yaml.safe_load`, "
            "no tiene frontmatter: ni id, ni tags, ni tipo, ni estado. El "
            "bloque **se ve** al abrir el fichero, y por eso nadie lo revisa. "
            "El dato parece estar y no está.\n\n"
            "No es AP-28, que es la nota que nunca tuvo bloque y se cuenta "
            "sola. Aquí el hueco es invisible a ojo y solo aparece al medir "
            "con el parser real (AP-44).\n\n"
            "Dos causas, medidas sobre doce notas de cuatro vaults "
            "consumidores: **escalar sin escapar** —`title: Overview: demo` no "
            "es un mapeo, nueve de las doce— y **delimitador sin cerrar**, las "
            "otras tres, donde el bloque nunca se cierra y el parser se traga "
            "la nota entera hasta reventar cientos de líneas más abajo, en un "
            "bloque de código. El mensaje de YAML señala ahí, que no es donde "
            "está el fallo; por eso llevaban meses así.\n\n"
            "v40.2 arregló la prevención: `yaml_scalar` escapa antes de "
            "escribir. Lo que faltaba era la otra mitad — nada reparaba lo que "
            "ya estaba en disco, y `vault_fix_brackets` llevaba versiones "
            "haciendo exactamente eso para AP-22/AP-24."
        ),
        "signal": (
            "`vault_frontmatter_heal` lo cuenta en `unparseable_total`; "
            "`vault_foreign_check` lo publica como `frontmatter_unparseable` "
            "al medir un vault ajeno."
        ),
        "prevention": (
            "Escribir por tool, nunca a mano (SP-04): el write path pasa todo "
            "escalar por `yaml_scalar` desde v40.2. Lo ya escrito se repara "
            "con `vault_frontmatter_heal --apply`, que solo toca las dos "
            "causas mecánicas y se niega a adivinar el resto: completar un "
            "YAML truncado inventa dato, que es peor que el hueco."
        ),
        "tools_enforcing": ["vault_write", "vault_frontmatter_heal"],
        "tools_detecting": ["vault_frontmatter_heal", "vault_foreign_check"],
        "distinguido_de": {
            "AP-28": (
                "AP-28 es la nota sin bloque: el hueco se ve y se cuenta. "
                "AP-56 es la nota con bloque que no parsea, que para toda "
                "métrica es idéntica a AP-28 pero para un humano parece "
                "correcta. Se separan porque solo una de las dos se repara "
                "sin escribir metadatos nuevos."
            )
        },
        "introduced_version": "v40.12",
    },
    {
        "code": "AP-57",
        "name": "Criterio con dueño, reimplementado en la medida",
        "type": "antipattern",
        "category": "architecture",
        "severity": "high",
        "enforcement": "guard",
        "description": (
            "Un **criterio** —qué cuenta como instantánea congelada, qué es "
            "documentación del estándar y no una nota, qué es código y no un "
            "enlace— tiene un dueño canónico en el toolkit, y otro módulo lo "
            "vuelve a decidir por su cuenta con un `if` local.\n\n"
            "No es AP-50, que habla de **patrones regex** y de vocabularios: "
            "aquellos son datos que alguien puede leer y comparar. Un criterio "
            "vive enterrado en una condición, así que la copia sobrevive años "
            "sin que nadie la vea, y el día que el dueño cambia solo cambia el "
            "dueño. `vault_graph_fix` llevaba su propio `skip_set` de "
            "instantáneas y ya divergía de `vault_io.SNAPSHOT_DIRS`; como esa "
            "tool **escribe**, la divergencia no inflaba una métrica: reparaba "
            "dentro de una instantánea, que es dejar de serlo.\n\n"
            "Sale de v40.12: cuatro defectos de `vault_foreign_check` "
            "arreglados en una tanda, los cuatro con la misma forma —el "
            "registro canónico existía y la tool no lo consultaba—. Uno de "
            "ellos tenía el sentido de error peligroso: resolver destinos por "
            "basename ponía la medida **verde** justo donde Obsidian pinta el "
            "enlace roto. La regla 4 pide norma, no cuatro parches."
        ),
        "signal": (
            "Un módulo que clasifica notas escribe una constante distintiva de "
            "otro —`\".history\"`, el nombre del manifiesto, la valla de un "
            "fence— sin importar el símbolo que la posee.\n\n"
            "**Y su forma más cara: la copia al otro lado de una frontera de "
            "lenguaje** (v40.19). Un `.mjs`, un workflow de CI o un `Makefile` "
            "no pueden importar un registro Python, así que reescriben la "
            "decisión — y ningún guard que solo lea `*.py` puede verlo. La CI de "
            "este repo listaba a mano seis puertas de las diecisiete del "
            "registro: once no se ejecutaban en ningún PR, y nada estaba roto. "
            "Una copia a través de una frontera no diverge de golpe; se atrasa."
        ),
        "prevention": (
            "Dos registros en `vault_criterios`. `CRITERIOS_CON_DUENO`: "
            "criterio, dueño, símbolo por el que se consulta y las constantes "
            "que lo delatan. `FRONTERAS`: cada frontera de lenguaje con su "
            "**zona dueña** (clave de `vault_arch.CONTEXTS`), su **norma** "
            "(código de `vault_norms`) y la **pasarela** —el artefacto derivado— "
            "por la que el criterio debe cruzar. Al otro lado la exención no es "
            "importar al dueño, que no se puede: es leer la pasarela.\n\n"
            "`vault_criterios --check --strict` (puerta 15) falla si aparece "
            "una copia nueva; la baseline **solo encoge** y se salda "
            "importando al dueño o leyendo la pasarela, no ampliándola. El "
            "alcance se declara: un fichero ejecutable de otro lenguaje fuera de "
            "toda zona declarada sale como `frontera_no_declarada`, porque un "
            "sitio donde una copia no se vería vale tanto como una copia.\n\n"
            "El límite se declara antes de que nadie se apoye en él: la "
            "detección es **sintáctica**. Un módulo puede reimplementar un "
            "criterio sin repetir ninguna constante y esta medida no lo verá. "
            "Verde no prueba que no haya copias — prueba que no hay copias de "
            "la forma que sabemos reconocer, que es exactamente lo que da un "
            "linter y es preferible a no mirar."
        ),
        "tools_enforcing": ["vault_criterios"],
        "tools_detecting": ["vault_criterios"],
        "distinguido_de": {
            "AP-62": (
                "AP-57 mira el criterio **escrito dos veces**; AP-62 mira el "
                "criterio escrito una sola vez y **leído por la puerta cara**. "
                "El consumidor de AP-62 hace justo lo que AP-57 pide —importar "
                "al dueño en vez de copiar— y aun así paga, porque el dueño "
                "trae el motor detrás. Se saldan al revés: AP-57 juntando el "
                "criterio en un dueño, AP-62 partiendo a ese dueño en catálogo "
                "y motor."
            ),
            "AP-61": (
                "AP-57 es el criterio escrito dos veces sin dueño; AP-61 es una "
                "excepción mal nombrada, que puede darse en un sitio único y sin "
                "copia ninguna. Se cruzan cuando la copia envejece —los doce "
                "sitios corregidos en v40.23 eran las dos cosas a la vez— pero "
                "AP-57 se salda importando al dueño y AP-61 nombrando la "
                "excepción, y un módulo puede quedar limpio de una y no de la otra."
            ),
            "AP-50": (
                "AP-50 es la **decisión duplicada legible**: un vocabulario, "
                "un default de entorno, un regex — dos copias que divergen se "
                "ven al compararlas. AP-57 es su generalización a criterios "
                "enterrados en una condición, donde no hay dato que comparar y "
                "la divergencia solo se nota por el resultado equivocado."
            ),
            "AP-59": (
                "AP-57 habla de un criterio escrito **dos veces** sin dueño; "
                "AP-59, de una **pertenencia afirmada una sola vez** y sin nada "
                "con que contrastarla. No hay copia que comparar: hay una lista "
                "y ninguna medida. Se tocan en el remedio —las dos se cierran "
                "dándole dueño a algo— pero AP-57 se salda importando al dueño "
                "y AP-59 derivando el dato de la forma medida."
            ),
        },
        "introduced_version": "v40.13",
    },
    {
        "code": "AP-58",
        "name": "Ciclo esquivado con un import diferido",
        "type": "antipattern",
        "category": "architecture",
        "severity": "high",
        "enforcement": "guard",
        "description": (
            "Dos módulos se necesitan mutuamente, y en vez de invertir la "
            "dependencia se mete uno de los `import` dentro del cuerpo de una "
            "función. Python deja de quejarse, el ciclo sigue ahí y **deja de "
            "verse**: cualquier medida que mire los imports de nivel de módulo "
            "dirá cero ciclos con toda honestidad.\n\n"
            "Aplicado una vez es una excepción razonable. Aplicado muchas es la "
            "arquitectura, tomada sin decidirla. Medido en v40.17 sobre este "
            "repo: **92 imports diferidos en 40 módulos**, de los cuales 30 "
            "esquivan un ciclo, y contándolos aparece un componente "
            "fuertemente conexo de **14 módulos** que contiene el núcleo "
            "entero. Ese componente es el que hacía que `vault_errors_trace` "
            "—un escritor de trazas de bajo nivel— importase `vault_io` "
            "entero, y el que obliga a `cli/runner.py` a aislar cada tool en "
            "un subproceso para que dos raíces no se contaminen.\n\n"
            "El daño no es el arranque: es que la dirección de la dependencia "
            "deja de ser una decisión revisable. Un ciclo escondido no se "
            "discute en revisión porque no aparece en ninguna medida."
        ),
        "signal": (
            "Un `import` de otro módulo del toolkit escrito dentro de una "
            "función, cuyo destino puede volver al origen siguiendo el grafo "
            "completo de imports."
        ),
        "prevention": (
            "`vault_ciclos --check --strict` (puerta 17) calcula los "
            "componentes fuertemente conexos **contando las aristas "
            "diferidas**, que es la única forma de que la pregunta se pueda "
            "formular. La baseline **solo encoge** y se salda invirtiendo la "
            "dependencia —el módulo de bajo nivel deja de pedirle el módulo "
            "entero al de alto y se le pasa lo que necesita—, no subiendo el "
            "import ni ampliando la baseline.\n\n"
            "Dos límites, dichos antes de que nadie se apoye en el verde. "
            "Primero: solo entran en la deuda los diferidos que **esquivan un "
            "ciclo** (30 de 92); los otros 62 se difieren por coste de "
            "arranque o por dependencia opcional y se publican como "
            "`deferred_benign` sin congelarse, porque una baseline llena de "
            "ruido es una baseline que nadie revisa. Segundo: la medida es del "
            "grafo **estático** de módulos. No ve `importlib`, ni un import "
            "construido con una cadena, ni el acoplamiento que pasa por el "
            "sistema de ficheros o por una variable global compartida."
        ),
        "tools_enforcing": ["vault_ciclos"],
        "tools_detecting": ["vault_ciclos"],
        "distinguido_de": {
            "AP-62": (
                "AP-58 mide una dependencia que **vuelve**: el ciclo. AP-62 "
                "mide una que no vuelve nunca y aun así cuesta, porque el "
                "importador solo quería un dato y se lleva el fan-out entero. "
                "Un repo sin un solo ciclo puede estar lleno de arrastre, y el "
                "remedio de AP-62 —partir el productor— es además una de las "
                "formas de romper un ciclo, que es donde se tocan."
            ),
            "AP-49": (
                "AP-49 mira el **vínculo congelado al importar**: un valor que "
                "se copia en tiempo de import y ya no responde a un reanclaje. "
                "AP-58 mira la **dirección** de la dependencia, no su momento. "
                "Se tocan porque el ciclo del núcleo es lo que obliga a "
                "congelar vínculos, pero un módulo puede tener ciclos sin "
                "vínculos congelados y al revés."
            ),
            "AP-54": (
                "AP-54 habla de cruces de frontera entre contextos acotados, "
                "que pueden ser perfectamente acíclicos. AP-58 habla del ciclo "
                "aunque ocurra dentro de un solo contexto — y el componente de "
                "14 módulos vive casi entero dentro del kernel."
            ),
            "AP-59": (
                "AP-58 mira la **dirección** de las dependencias: quién importa "
                "a quién y si eso vuelve. AP-59 mira **quién está declarado como "
                "fondo de esa pila**. Un repo puede tener cero ciclos y un núcleo "
                "mal declarado, y un núcleo impecable lleno de ciclos."
            ),
        },
        "introduced_version": "v40.17",
    },
    {
        "code": "AP-59",
        "name": "Núcleo declarado sin contraste",
        "type": "antipattern",
        "category": "architecture",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "Un sistema declara cuál es su núcleo —la lista de módulos de los "
            "que todo lo demás depende— y **ninguna medida contrasta esa "
            "afirmación** contra la forma real del grafo. La pertenencia al "
            "core deja de ser un hecho y pasa a ser una costumbre: se hereda de "
            "quien escribió la lista, y envejece en la dirección cómoda.\n\n"
            "Lo caro no es equivocarse de lista: es que **todo lo que se apoya "
            "en ella hereda el error en silencio**. Si un módulo está declarado "
            "como núcleo sin serlo, el guard de fronteras lo exime de reglas que "
            "sí debería cumplir y sale verde. Si uno lo es sin estar declarado, "
            "cada cambio suyo propaga hacia arriba sin que nadie lo trate como "
            "un cambio de núcleo. En ambos casos el verde es correcto respecto a "
            "un mapa equivocado.\n\n"
            "Medido en v40.20 sobre este repo, con la lista **bien elegida** —los "
            "cuatro de cabecera eran los correctos y K1 ya estaba verde—: aun "
            "así, **tres de quince módulos del kernel no se comportan como "
            "núcleo**. `vault_log_error` con fan-in 0, declarado núcleo y sin un "
            "solo consumidor; `vault_io` con fan-out 11 y 30 commits; "
            "`vault_errors` con 14, sobre una mediana de dominio de 9. Ninguno "
            "estaba roto. Ninguno se había visto, porque nadie miraba.\n\n"
            "La norma no exige que el núcleo sea perfecto: exige que su "
            "pertenencia sea **derivable y contrastada**, y que la distancia "
            "entre lo declarado y lo medido se publique en vez de suponerse cero."
        ),
        "signal": (
            "La lista del núcleo se edita a mano y ninguna puerta la lee; un "
            "módulo declarado kernel sin consumidores; un módulo de dominio con "
            "fan-in por encima del escalón de la distribución; el churn del "
            "núcleo por encima de la mediana de lo que sostiene."
        ),
        "prevention": (
            "`vault_kernel --check --strict` (puerta 18) mide tres invariantes. "
            "**K1** —el núcleo no depende del dominio— no se reimplementa: se "
            "delega en `vault_arch.dependencias_del_kernel()`, porque una tool "
            "que mide su propia pureza con su propio criterio es AP-44 cometido "
            "en el sitio que existe para detectarlo. **K2** —fan-in alto, "
            "fan-out bajo— sale del dueño único del grafo de imports "
            "(`vault_grafo_import`), no de un parser propio. **K3** —estabilidad— "
            "del churn de git, y sin historia disponible emite `desconocido` y "
            "nunca `0`: un cero fabricado saldría verde por no haber mirado "
            "(AP-51). Desde v41.3 el churn cuenta **commits que cambian el "
            "comportamiento** —funciones, clases, nombres—, leídos con `ast`; "
            "un commit que solo añade entradas a una tabla, o reescribe un "
            "docstring o un comentario, no mueve al módulo para quien lo "
            "importa. Núcleo y dominio se miden con la misma vara, y el churn "
            "bruto se publica al lado (`raw_churn`) sin decidir nada.\n\n"
            "Los umbrales **se derivan del escalón** de la distribución —la "
            "mayor caída relativa— y se publican en el envelope con su ratio en "
            "cada ejecución. Escribirlos a mano sería AP-47 en la tool que "
            "persigue los números a mano; por eso la baseline congela la "
            "**pertenencia** (qué módulo incumple qué invariante) y no el "
            "umbral, que puede oscilar al crecer el repo.\n\n"
            "Dos límites, dichos antes de que nadie se apoye en el verde. "
            "Primero: mide el grafo **estático** de imports y hereda sus "
            "cegueras (`importlib`, un import por cadena, el acoplamiento por "
            "fichero o por variable global). Segundo: mide **forma, no "
            "propósito**. Un módulo puede tener fan-in altísimo sin ser núcleo "
            "de nada, solo un cajón de utilidades que todo el mundo toca. Verde "
            "significa que la lista declarada no contradice a la forma medida."
        ),
        "tools_enforcing": ["vault_kernel"],
        # `vault_arch` NO se lista aquí aunque mida K1: la delegación va en un
        # solo sentido. `dependencias_del_kernel()` existía antes que la norma y
        # no la nombra, así que declararla detectora sería una cobertura que
        # nadie puede seguir hasta el código — el AP-55 que este catálogo mide.
        "tools_detecting": ["vault_kernel"],
        "distinguido_de": {
            "AP-62": (
                "AP-59 mira la **lista del núcleo** y pregunta si la forma "
                "medida la sostiene. AP-62 mira las **aristas de fuera del "
                "núcleo** y pregunta qué se paga al cruzarlas. Se tocan en la "
                "tentación opuesta: quien quiera bajar la cifra de AP-62 "
                "moviendo el productor al núcleo sin darle forma de hoja se "
                "encuentra con AP-59, y por eso el remedio es partirlo, no "
                "reclasificarlo."
            ),
            "AP-57": (
                "AP-57 habla de un **criterio** escrito dos veces sin dueño. "
                "AP-59 habla de una **pertenencia afirmada y no contrastada**: "
                "no hay copia ninguna, hay una sola lista y nada con qué "
                "compararla. Se tocan en el remedio —los dos se cierran dándole "
                "dueño a algo— pero AP-57 se salda importando al dueño y AP-59 "
                "derivando el dato de la forma medida."
            ),
            "AP-58": (
                "AP-58 mira la **dirección** de las dependencias: quién importa "
                "a quién y si eso vuelve. AP-59 mira **quién está declarado como "
                "fondo de esa pila**. Un repo puede tener cero ciclos y un "
                "núcleo mal declarado, y un núcleo perfecto lleno de ciclos."
            ),
            "AP-47": (
                "AP-47 es la cifra escrita a mano en la documentación. AP-59 es "
                "su versión estructural: la **lista** escrita a mano en el "
                "código. Por eso el remedio comparte disciplina —derivar en vez "
                "de escribir— y por eso los umbrales de esta tool no pueden ser "
                "literales sin cometer AP-47 dentro de AP-59."
            ),
        },
        "introduced_version": "v40.20",
    },
    {
        "code": "AP-60",
        "name": "El guard cobra por declarar y regala el silencio",
        "type": "antipattern",
        "category": "process",
        "severity": "medium",
        "enforcement": "guard+audit",
        "description": (
            "Un guard comprueba una propiedad **iterando sobre quien ya la "
            "declaró**. Quien no declaró nada queda fuera de su alcance, no por "
            "una decisión sino por la forma del bucle. El efecto es un incentivo "
            "invertido: declarar cuesta —obliga a mantener lo declarado, a veces "
            "a editar el otro extremo— y callarse sale gratis y verde.\n\n"
            "Medido en v40.21 sobre C5 de `vault_norms_coherence`: la "
            "comprobación de que dos normas se distinguen recorre "
            "`distinguido_de`, así que solo alcanzaba a **13 normas de 71**. Las "
            "otras 58 no estaban exentas: estaban invisibles. Y declarar una "
            "distinción en AP-59 costó tres ediciones recíprocas y un fallo de "
            "puerta, mientras no declarar ninguna habría salido verde a la "
            "primera.\n\n"
            "Es la misma forma que el repo ya prohíbe en `cobertura_descubierta` "
            "—una norma que declara su hueco no cuenta como deuda nueva, porque "
            "declararse honestamente no puede salir más caro que callarse—, "
            "cometida en el guard que vigila el catálogo donde esa regla está "
            "escrita."
        ),
        "symptoms": (
            "Un guard cuyo bucle empieza por un campo opcional; una medida cuyo "
            "total no puede subir porque el denominador es la lista de quienes "
            "ya hablaron; un envelope que publica cuántos casos revisó y no "
            "cuántos existían."
        ),
        "prevention": (
            "Medir sobre el universo —el catálogo, el registro, el conjunto de "
            "módulos— y no sobre el subconjunto que declaró. Admitir dos salidas "
            "honestas, la declaración y la exención con motivo escrito, y "
            "ninguna tercera: el silencio se cuenta como deuda. La baseline "
            "congela lo que ya estaba y solo encoge; lo que estrena se escribe."
        ),
        "tools_enforcing": ["vault_norms_coherence"],
        "tools_detecting": ["vault_norms_coherence"],
        "distinguido_de": {
            "AP-55": (
                "AP-55 es el catálogo verificándose con el catálogo: el criterio "
                "sale del propio objeto medido. AP-60 no habla del criterio sino "
                "del **alcance**: el criterio puede ser impecable y aun así "
                "aplicarse solo a quien se ofreció voluntario. Un guard puede "
                "medir con criterio ajeno —correcto frente a AP-55— y seguir "
                "recorriendo únicamente a los que declararon."
            ),
            "AP-37": (
                "AP-37 persigue la afirmación **no falsable**: el `ok: true` que "
                "ninguna evidencia podría contradecir. AP-60 persigue la "
                "afirmación falsable pero **parcial**: hay evidencia y se mira, "
                "solo que sobre un subconjunto que se autoselecciona. La primera "
                "no se puede refutar; la segunda se refuta mirando a quien no "
                "aparece en la lista."
            ),
        },
        "introduced_version": "v40.21",
    },
    {
        "code": "AP-61",
        "name": "El guard cae con el dato que vino a medir",
        "type": "antipattern",
        "category": "quality",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "Un handler captura la excepción que una librería **declara** y deja "
            "escapar la que esa librería **lanza de verdad**. El `try` parece "
            "contener el fallo y no lo contiene: la excepción sube entera y "
            "tumba la ejecución completa. Lo caro es la asimetría de alcance — "
            "el dato defectuoso es de una nota, la caída es del barrido entero, "
            "así que un solo fichero hostil deja al vault sin medida.\n\n"
            "El caso que le dio nombre: `RecursionError` **no hereda de "
            "`yaml.YAMLError`**. El parser de PyYAML es recursivo y el "
            "frontmatter es dato externo, así que `x: [[[[[…` —doce caracteres "
            "de escribir— desborda la pila dentro de `safe_load`, por encima de "
            "cualquier `except yaml.YAMLError`. `vault_lib.parse_frontmatter` lo "
            "resolvió y lo dejó escrito; los otros **doce sitios** que habían "
            "copiado el mismo `try` no se enteraron de la corrección, y entre "
            "ellos estaba `vault_foreign_check`, que es la tool de la regla 7 y "
            "por tanto la única que corre contra material que este repo no "
            "generó — exactamente donde el dato hostil aparece.\n\n"
            "Es primo de AP-57 y llega por su camino: un criterio copiado "
            "envejece por su lado, y aquí envejeció hacia el lado que deja caer "
            "la tool."
        ),
        "signal": (
            "Un `except` que nombra la excepción base de una librería alrededor "
            "de una llamada que también lanza `RecursionError`, `MemoryError` o "
            "una excepción de otra jerarquía; una tool que muere entera con un "
            "fichero concreto en vez de contarlo como fichero defectuoso."
        ),
        "prevention": (
            "`vault_excepcion_declarada --check --strict` recorre los `try` cuyo "
            "cuerpo contiene una llamada de riesgo declarada en `RIESGOS` y "
            "exige que la excepción que escapa esté nombrada. Se salda "
            "**delegando en el dueño que ya la contuvo** —para el frontmatter, "
            "`vault_lib.parse_frontmatter`— y solo cuando la firma de retorno lo "
            "impide, nombrándola en la tupla y citando al dueño en un "
            "comentario: ampliar la tupla en trece sitios sin dueño es AP-57 "
            "cometido al arreglar AP-61.\n\n"
            "Límite declarado: solo ve la llamada de riesgo escrita **a la "
            "vista** en el cuerpo del `try`. Un `safe_load` detrás de un helper "
            "queda fuera del alcance, que es la forma correcta de escribirlo — "
            "así que este guard mide mejor el código que peor está escrito, y "
            "eso se publica en vez de suponerse cubierto."
        ),
        "tools_enforcing": ["vault_excepcion_declarada"],
        "tools_detecting": ["vault_excepcion_declarada"],
        "distinguido_de": {
            "AP-51": (
                "Son los dos extremos del mismo eje. AP-51 es el handler "
                "**demasiado ancho**: captura `Exception`, se traga el fallo "
                "propio y devuelve un vacío que nadie distingue de un resultado "
                "legítimo. AP-61 es el handler **demasiado estrecho**: nombra "
                "menos de lo que la llamada lanza, así que no se traga nada — "
                "deja pasar. El discriminador es qué pasa después del fallo: "
                "con AP-51 la tool sigue y miente, con AP-61 la tool cae."
            ),
            "AP-57": (
                "AP-57 es el criterio escrito dos veces sin dueño; AP-61 es una "
                "excepción mal nombrada, que puede darse en un sitio único y sin "
                "copia ninguna. Se cruzan cuando la copia envejece —los doce "
                "sitios de v40.23 eran las dos cosas a la vez— pero AP-57 se "
                "salda importando al dueño y AP-61 se salda nombrando la "
                "excepción, y una tool puede quedar limpia de una y no de la otra."
            ),
        },
        "introduced_version": "v40.23",
    },
    # ── Anti-patrón AP-62 ──────────────────────────────────────────────────────
    {
        "code": "AP-62",
        "name": "El consumidor paga el fan-out del productor",
        "type": "antipattern",
        "category": "architecture",
        "severity": "medium",
        "enforcement": "guard+audit",
        "description": (
            "Un módulo importa a otro **solo para leer un recurso** —una tabla "
            "constante, una función pura— y con el import se lleva todas las "
            "dependencias del productor. Cuando los dos están en contextos "
            "distintos, la arquitectura registra un cruce de frontera de "
            "negocio donde lo único que ocurrió fue **leer un dato**.\n\n"
            "El caso que le dio nombre no se buscó: se tropezó con él en "
            "v40.27. De los veinticuatro importadores de `vault_norms`, "
            "**veintiuno solo querían datos** —`NORM_CATALOG`, `STATUS_VOCAB`, "
            "`status_frontmatter_lines`— y entraban por una fachada que "
            "reexporta el motor de auditoría y sus once dependencias. Mudado el "
            "catálogo a una hoja del núcleo y repuntados los importadores, los "
            "cruces del repo pasaron de **62 a 42** sin que se eliminara una "
            "sola capacidad.\n\n"
            "Lo caro es que **cada sitio, por separado, parece razonable**: "
            "quien escribe `from vault_norms import STATUS_VOCAB` no está "
            "haciendo nada mal, y ningún guard tenía por qué ponerse rojo. El "
            "daño solo existe en el agregado, y por eso hace falta medirlo en "
            "vez de revisarlo — que es la forma exacta que tiene el deterioro "
            "por acumulación."
        ),
        "signal": (
            "Un módulo con fan-out alto cuyos importadores solo le piden "
            "constantes; una fachada que reexporta a la vez el catálogo y el "
            "motor que lo consume; un cruce de contexto cuya única razón de ser "
            "es un `from X import UNA_CONSTANTE`."
        ),
        "prevention": (
            "`vault_recursos --check --strict` clasifica cada arista del grafo "
            "y cuenta como deuda la que cumple las cuatro condiciones: el "
            "destino no está en el núcleo, tiene fan-out mayor que cero, todo "
            "lo que el origen le pide es recurso, y los dos están en contextos "
            "distintos. `--ranking` ordena los productores por cuántos cruces "
            "colapsaría mudar cada uno, que es lo que convierte la medida en un "
            "plan.\n\n"
            "Se salda **dándole al recurso un dueño con forma de hoja**: partir "
            "el productor en catálogo y motor, y repuntar a los consumidores al "
            "dueño. La lección de v40.27 es que **partir el fichero por sí solo "
            "no mueve una sola cifra** — la arquitectura no cambia hasta que "
            "los importadores dejan de entrar por la fachada.\n\n"
            "Límites declarados: mide `from X import y` y no `import X`, porque "
            "quien importa el módulo entero no declara qué usa; decide la "
            "pureza por AST a punto fijo, así que una función que dependa de un "
            "global mutable pasará por pura; y da las clases por acopladas sin "
            "mirarlas, prefiriendo no contar un sitio a contar uno que no lo es."
        ),
        "tools_enforcing": ["vault_recursos"],
        "tools_detecting": ["vault_recursos", "vault_arch"],
        "distinguido_de": {
            "AP-57": (
                "AP-57 es el criterio escrito dos veces sin dueño; AP-62 es el "
                "criterio con un dueño perfectamente claro al que se llega por "
                "el camino caro. Son opuestos en el síntoma: AP-57 aparece "
                "cuando alguien **no** importó al dueño y reimplementó, AP-62 "
                "cuando sí lo importó y el dueño estaba envuelto en un módulo "
                "que arrastra. Y por eso la corrección de AP-62 no puede ser "
                "copiar el recurso al consumidor: eso lo cambia por un AP-57."
            ),
            "AP-58": (
                "Los dos hablan de imports, pero AP-58 mide el **ciclo** —el "
                "destino vuelve al origen— y AP-62 mide el **peso** —el destino "
                "arrastra más de lo que hacía falta—. Un arrastre puede no "
                "cerrar ningún ciclo y seguir siendo deuda, y un ciclo puede "
                "darse entre dos módulos que se piden justo lo que necesitan. "
                "Se cruzan al saldarlos: mudar el recurso a una hoja rompió de "
                "paso quince ciclos diferidos en v40.27, y ese efecto fue una "
                "consecuencia medida, no el objetivo."
            ),
            "AP-59": (
                "AP-59 vigila la **forma del núcleo**: que lo declarado núcleo "
                "lo parezca al medirlo. AP-62 vigila **quién paga por quién** "
                "fuera de él. Se necesitan mutuamente y en direcciones "
                "opuestas: la corrección típica de AP-62 es mudar un recurso al "
                "núcleo, y AP-59 es lo único que impide que esa mudanza sea una "
                "reclasificación de conveniencia para bajar la cifra."
            ),
        },
        "introduced_version": "v40.28",
    },
    # ── Anti-patrón AP-63 ──────────────────────────────────────────────────────
    {
        "code": "AP-63",
        "name": "El nombre de un proyecto como texto libre",
        "type": "antipattern",
        "category": "consistency",
        "severity": "high",
        "enforcement": "guard+audit",
        "description": (
            "El nombre de un proyecto es **identidad**, y hasta v40.34 era "
            "texto libre: cada `--project` escribía su valor tal cual, así que "
            "una errata, una variante de mayúsculas o un ejemplo del manifiesto "
            "**fundaban** un proyecto con su carpeta. Medido en solo lectura "
            "contra un vault consumidor (regla 7): cuatro proyectos fantasma "
            "—`mi-api`, `mi-proyecto`, `demo`, `website-demo`— que eran los "
            "ejemplos del estándar copiados por un agente.\n\n"
            "El registro existe sin que nadie lo declare: la carpeta "
            "`01_Projects/<slug>/` registra el slug. La ficha opcional "
            "`project.md` aporta `aliases`, `title` y `status`. Un nombre "
            "resuelve a **un** slug o falla: `PROJECT_NOT_FOUND` con "
            "sugerencias, `PROJECT_AMBIGUOUS` si un alias lo reclaman dos."
        ),
        "signal": (
            "Dos carpetas en `01_Projects/` que solo difieren en mayúsculas o "
            "guiones; notas con `project:` que no corresponde a ninguna "
            "carpeta; claves `proyecto:` o `Project:` junto a `project:`; la "
            "ruta local de un repositorio escrita dentro de una nota."
        ),
        "prevention": (
            "`vault_project` es la puerta de entrada: `--add` registra y "
            "rechaza un alias que ya es de otro proyecto, `--resolve` devuelve "
            "el slug o el código de error, `--audit` lista fantasmas y claves "
            "no canónicas sin escribir nada. La ruta local va a "
            "`00_System/.local/project-paths.json`, con su propio "
            "`.gitignore`: es de una máquina, no del proyecto.\n\n"
            "Límites declarados: las tools con `--project` todavía no pasan "
            "por el resolutor, así que la escritura sigue pudiendo fundar un "
            "fantasma que el audit verá después; y el audit no mira el cuerpo "
            "de las notas, donde los ejemplos del manifiesto citan nombres "
            "que no son proyectos."
        ),
        "tools_enforcing": ["vault_project"],
        "tools_detecting": ["vault_project"],
        "distinguido_de": {
            "AP-05": (
                "AP-05 es el mismo dato con valores distintos en varias notas. "
                "AP-63 es anterior: el **nombre** que decide a qué ámbito "
                "pertenece una nota. Si el nombre se bifurca, AP-05 ni siquiera "
                "puede ver el conflicto, porque las dos notas parecen de "
                "proyectos distintos."
            ),
            "AP-17": (
                "AP-17 es una nota sombra de un canónico declarado. AP-63 es "
                "el proyecto entero sin canónico: no hay sombra porque nadie "
                "dijo cuál era el original, y la corrección empieza por "
                "registrarlo, no por fusionar notas."
            ),
        },
        "introduced_version": "v40.34",
    },
    _desde_paquete("AP-64"),
    _desde_paquete("AP-65"),
    # ── Patrón PAT-6 ───────────────────────────────────────────────────────────
    _desde_paquete("PAT-6"),
    # ── Protocolo de sesión SP-XX ──────────────────────────────────────────────
    _desde_paquete("SP-01"),
    _desde_paquete("SP-02"),
    _desde_paquete("SP-03"),
    _desde_paquete("SP-04"),
    # ── Convenciones de nomenclatura CN-XX ────────────────────────────────────
    _desde_paquete("CN-01"),
    _desde_paquete("CN-02"),
    _desde_paquete("CN-03"),
    _desde_paquete("CN-04"),
]

# Índice rápido por código
_NORM_BY_CODE: Dict[str, Dict[str, Any]] = {n["code"]: n for n in NORM_CATALOG}


def norma_por_codigo(code: str) -> Dict[str, Any] | None:
    """La norma con ese código, o `None`.

    El puerto público del índice. `vault_code_tag` —que es del contexto de
    grafo— venía importando `_NORM_BY_CODE` directamente: un nombre privado
    atravesando una frontera, que es lo contrario de una superficie publicada.
    El dict sigue existiendo para uso interno de este módulo; lo que cambia es
    que quien viene de fuera entra por aquí.
    """
    return _NORM_BY_CODE.get(code)

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "N/A": 4}
_CATEGORY_ORDER = {
    "linking": 0,
    "content-quality": 1,
    "structure": 2,
    "frontmatter": 3,
    "process": 4,
    "session-protocol": 5,
    "convention": 6,
}



# Vocabulario canónico de meta.status (CN-03) — unificado v38.
# Antes existían DOS vocabularios contradictorios: CN-03 (7 valores) y el
# ciclo de vida del spec §status (draft→reviewed→approved→implemented→
# verified→obsolete). Este set es la unión canónica; CN-03 y el spec
# referencian este símbolo como fuente única.
STATUS_VOCAB = {
    "planned",
    "draft",
    "in-progress",
    "reviewed",
    "approved",
    "implemented",
    "verified",
    "deprecated",
    "obsolete",
    "archived",
    "stub",
    "template",
}

#: `STATUS_VOCAB` como tipo (D4, v40.34). Se **deriva** del set, no repite los
#: doce valores: una segunda lista es un segundo dueño, y el set ya tuvo dos
#: vocabularios contradictorios antes de v38. Hereda de `str`, así que
#: `Status.IN_PROGRESS == "in-progress"` y lo que se escribe en el frontmatter
#: no cambia. Comprobar pertenencia se sigue haciendo contra el set: `"x" in
#: Status` lanza TypeError antes de Python 3.12, y el piso es 3.9.
Status = Enum(
    "Status",
    {valor.replace("-", "_").upper(): valor for valor in sorted(STATUS_VOCAB)},
    type=str,
)
Status.__doc__ = "Valor canónico de meta.status (CN-03); derivado de STATUS_VOCAB."

# ─── Registro de lifecycles ──────────────────────────────────────────────────
#
# El catálogo de máquinas de estado vivía escrito a mano dentro de
# `vault_sdd_init.generate_state_machines`, en una cadena constante, y llevaba
# tiempo mintiendo: daba el ciclo de la versión del estándar como «v19 → … →
# v36» estando el repo en v39.5, y el de las tools como
# `active/deprecated/internal/meta/removed` cuando los estados que el tool-spec
# usa de verdad son `active/archived/internal`. Dos de trece filas incorrectas en
# el documento cuyo trabajo entero es describir las máquinas de estado.
#
# El orden que fija AGENTS.md es registro primero y doc después, así que la tabla
# se declara aquí —junto a STATUS_VOCAB, que es la otra verdad sobre estados— y
# el generador del SDD la deriva. Las dos filas que sí tienen fuente viva
# (versión del estándar, estados de tool) se resuelven en tiempo de generación
# contra esa fuente, no se copian.
LIFECYCLE_REGISTRY = [
    {"entity": "Nota", "entity_en": "Note",
     "states": ["active", "archived", "deleted"], "tool": "vault_change_log"},
    {"entity": "Patrón", "entity_en": "Pattern",
     "states": ["planificado", "en_progreso", "implementado", "deprecado", "refactoring"],
     "tool": "vault_pattern_save"},
    {"entity": "Requisito", "entity_en": "Requirement",
     "states": ["draft", "reviewed", "approved", "implemented", "verified", "obsolete"],
     "tool": "vault_requirement_save"},
    {"entity": "Test", "entity_en": "Test",
     "states": ["not_run", "pass", "fail", "blocked", "skip"], "tool": "vault_test_save"},
    {"entity": "Ejecución de runbook", "entity_en": "Runbook execution",
     "states": ["success", "failed", "partial"], "tool": "vault_runbook_log"},
    {"entity": "Incidente", "entity_en": "Incident",
     "states": ["detected", "investigating", "identified", "mitigating", "resolved",
                "closed", "post-mortem"], "tool": "vault_incident_save"},
    {"entity": "Consumo de SLO", "entity_en": "SLO burn",
     "states": ["healthy", "1h-burn", "6h-burn", "30d-burn", "breached"],
     "tool": "vault_slo_save"},
    {"entity": "Tratamiento de riesgo", "entity_en": "Risk treatment",
     "states": ["accept", "mitigate", "transfer", "avoid"], "tool": "vault_risk_save"},
    {"entity": "NCR", "entity_en": "NCR",
     "states": ["open", "closed"], "tool": "vault_ncr_save"},
    {"entity": "Backup", "entity_en": "Backup",
     "states": ["active", "superseded"], "tool": "vault_backup_list"},
    {"entity": "Propagación pendiente", "entity_en": "Propagation pending",
     "states": ["pending", "reviewed"], "tool": "vault_propagate"},
    # `states: None` = se resuelve contra la fuente viva al generar la doc.
    {"entity": "Ciclo de vida de una tool", "entity_en": "Tool lifecycle",
     "states": None, "source": "tool_spec_status", "tool": "vault_mcp_catalog"},
    {"entity": "Versión del estándar", "entity_en": "Standard version",
     "states": None, "source": "standard_version", "tool": "vault_standard_upgrade"},
]


# ─── Sinónimos de estado (AP-38) ─────────────────────────────────────────────
#
# CN-03 lleva desde v38 declarando el vocabulario y auditándolo. Un censo sobre
# 17 vaults reales (2.929 notas) mostró el resultado de auditar sin normalizar:
# **54 valores distintos de `status`, de los cuales solo el 6% caía dentro del
# vocabulario** — y de los 12 canónicos únicamente 4 llegaron a usarse. Los más
# frecuentes eran inventados: `implementado` (205 notas), `active` (60),
# `activo` (53), `accepted` (45), `fixed` (31).
#
# La lección del censo no es que los agentes escriban mal: es que un vocabulario
# que solo se audita *después* de escribir no gobierna nada, porque nadie
# ejecuta el audit — `vault_norms` no aparece ni una vez en las 1.356
# ejecuciones registradas del parque. Por eso este mapa se aplica en la
# escritura, no en la revisión.
#
# Cubre español e inglés porque el parque los mezcla en la misma nota.
STATUS_SYNONYMS = {
    # activo / en curso
    "active": "in-progress",
    "activo": "in-progress",
    "en_desarrollo": "in-progress",
    "en-desarrollo": "in-progress",
    "in_progress": "in-progress",
    "en_progreso": "in-progress",
    "refactoring": "in-progress",
    "wip": "in-progress",
    "investigating": "in-progress",
    "investigado": "in-progress",
    "open": "in-progress",
    "abierto": "in-progress",
    "identificado": "in-progress",
    "pendiente_accion": "in-progress",
    # planificado
    "planificado": "planned",
    "pendiente": "planned",
    "deferred": "planned",
    "proposed": "planned",
    "propuesto": "planned",
    # aprobado
    "accepted": "approved",
    "aceptado": "approved",
    "aceptada": "approved",
    "amended": "approved",
    # implementado
    "implementado": "implemented",
    "implementada": "implemented",
    "completado": "implemented",
    "completada": "implemented",
    "completed": "implemented",
    "complete": "implemented",
    "documentacion_completada": "implemented",
    "documented": "implemented",
    "documentado": "implemented",
    "en_produccion": "implemented",
    "operativo": "implemented",
    "estable": "implemented",
    "vigente": "implemented",
    # verificado
    "fixed": "verified",
    "corregido": "verified",
    "resuelto": "verified",
    "resolved": "verified",
    "validated": "verified",
    "validado": "verified",
    "mitigado": "verified",
    "mitigated": "verified",
    "prevenido": "verified",
    "pass": "verified",
    "implemented-and-validated": "verified",
    # retirado
    "deprecado": "deprecated",
    "deprecada": "deprecated",
    "obsoleto": "obsolete",
    "obsoleta": "obsolete",
    # histórico
    "historical": "archived",
    "archivo-historico": "archived",
    "archivo-histórico": "archived",
    "offline": "archived",
    "no-bug": "archived",
}

#: Sufijos que un estado arrastra y que NO son parte del estado: progreso
#: parcial, versión en que se resolvió, fecha de corrección. El censo los
#: encontró incrustados en el propio campo (`1-fixed-6-pending`, `all-fixed`,
#: `resuelto (v0.58)`, `aceptada (corregida 2026-05-11)`, `mayormente_corregido`).
#: Se extraen a `status_note` en vez de perderse: no-derogación aplicada al dato.
STATUS_QUALIFIERS = {
    "mayormente_corregido": ("verified", "corrección parcial"),
    "partial": ("in-progress", "parcial"),
    "all-fixed": ("verified", "all-fixed"),
    "not_run": ("planned", "not_run"),
}

#: Transiciones permitidas del ciclo de vida. Un estado que no puede alcanzarse
#: desde ninguno otro es inalcanzable, y uno del que no se sale es terminal.
#: `stub` y `template` no participan del ciclo: son marcas de naturaleza de la
#: nota, no fases de su vida.
STATUS_TRANSITIONS = {
    "planned": {"draft", "in-progress", "archived"},
    "draft": {"in-progress", "reviewed", "archived"},
    "in-progress": {"draft", "reviewed", "implemented", "archived"},
    "reviewed": {"approved", "draft", "archived"},
    "approved": {"implemented", "deprecated", "archived"},
    "implemented": {"verified", "deprecated", "archived"},
    "verified": {"deprecated", "obsolete", "archived"},
    "deprecated": {"obsolete", "archived"},
    "obsolete": {"archived"},
    "archived": set(),
    "stub": {"draft", "in-progress", "archived"},
    "template": {"archived"},
}


#: Vocabularios de dominio (AP-38).
#:
#: El censo del parque atribuía los 54 estados a agentes descuidados. Falso: el
#: valor no canónico más frecuente, `implementado` (205 notas), lo escribe
#: `vault_pattern_save`, que trae su propio vocabulario y su propia máquina de
#: transiciones. El estándar publicaba **nueve** vocabularios de `status` en
#: competencia — AP-05 dentro del propio toolkit. Un agente que escribía
#: `implementado` estaba obedeciendo a la tool, no ignorándola.
#:
#: La corrección no es borrar esos vocabularios: `pass` de un test o `P2` de un
#: incidente son información real que `verified` no expresa. Son **otro eje**.
#: Así que `status` queda reservado al ciclo de vida de la nota, canónico, y
#: cada dominio conserva su vocabulario íntegro en su propio campo. Las flags de
#: CLI no cambian: lo que cambia es en qué campo aterriza el valor.
#:
#: Formato: `tool -> (campo_de_dominio, {valor_de_dominio: status_canonico})`.
DOMAIN_STATUS_VOCABS = {
    "vault_pattern_save": ("pattern_state", {
        "planificado": "planned",
        "en_progreso": "in-progress",
        "implementado": "implemented",
        "deprecado": "deprecated",
        "refactoring": "in-progress",
    }),
    "vault_bug_save": ("bug_state", {
        "open": "in-progress",
        "confirmed": "in-progress",
        "in_fix": "in-progress",
        "fixed": "verified",
        "wont_fix": "approved",
        "duplicate": "obsolete",
    }),
    "vault_test_save": ("test_result", {
        "not_run": "planned",
        "pass": "verified",
        "fail": "implemented",
        "blocked": "in-progress",
        "skip": "draft",
    }),
    "vault_incident_save": ("incident_state", {
        "detected": "in-progress",
        "investigating": "in-progress",
        "identified": "in-progress",
        "mitigating": "in-progress",
        "resolved": "verified",
        "closed": "archived",
        "post-mortem": "reviewed",
    }),
    "vault_ncr_save": ("ncr_state", {
        "open": "in-progress",
        "in_progress": "in-progress",
        "pending_verification": "reviewed",
        "closed": "archived",
        "cancelled": "obsolete",
    }),
    "vault_risk_save": ("risk_state", {
        "open": "in-progress",
        "in_treatment": "in-progress",
        "accepted": "approved",
        "closed": "archived",
    }),
    "vault_release_save": ("release_state", {
        "planned": "planned",
        "in_progress": "in-progress",
        "deployed": "implemented",
        "rolled_back": "deprecated",
        "cancelled": "obsolete",
    }),
    "vault_privacy_save": ("privacy_state", {
        "active": "implemented",
        "under_review": "reviewed",
        "deprecated": "deprecated",
        "closed": "archived",
    }),
    # El comentario de vault_preferences decía "alineado con STATUS_VOCAB" y sus
    # dos únicos valores estaban fuera. Una afirmación falsa desde que se
    # escribió, y nadie podía verla porque no había guard que la comprobara.
    "vault_preferences": ("preference_state", {
        "active": "implemented",
        "revoked": "deprecated",
    }),
    # `--status` de infra es texto libre y nunca tuvo validación: es la única
    # de las nueve que no publicaba vocabulario, así que aceptaba cualquier
    # cosa. Se le da uno; lo que no encaje sigue cayendo en `normalize_status`.
    "vault_infra_save": ("infra_state", {
        "active": "implemented",
        "activo": "implemented",
        "provisioning": "in-progress",
        "degraded": "in-progress",
        "decommissioned": "archived",
        "offline": "archived",
    }),
    # `vault_runbook_save` escribía `status: active` a pelo desde su creación:
    # fuera de STATUS_VOCAB, solo aceptado como sinónimo de `in-progress`, que
    # además no es lo que un runbook listo para ejecutarse está. Mismo caso que
    # privacy y preferences: el valor de dominio se conserva, el canónico va en
    # `status` (CN-03, v40.35).
    "vault_runbook_save": ("runbook_state", {
        "active": "implemented",
    }),
    # `vault_qa_save` anunciaba y validaba cinco estados sin registrarlos aquí:
    # `review` y `published` no son canónicos, así que pasaban su validación y
    # `status_frontmatter_lines` los rechazaba después con UNEXPECTED_ERROR
    # crítico (v41.3). Un informe QA publicado es uno aprobado y distribuido:
    # `approved`, como `wont_fix` de un bug; el valor de dominio lo conserva.
    "vault_qa_save": ("qa_state", {
        "draft": "draft",
        "review": "reviewed",
        "approved": "approved",
        "published": "approved",
        "archived": "archived",
    }),
    "vault_project_status": ("project_state", {
        "en_desarrollo": "in-progress",
        "en_revision": "reviewed",
        "bloqueado": "in-progress",
        "completado": "implemented",
        "archivado": "archived",
        "en_produccion": "implemented",
    }),
}


def split_domain_status(tool, raw):
    """Separa el eje de dominio del ciclo de vida de la nota.

    Devuelve `(status_canonico, campo_dominio, valor_dominio)`. El valor de
    dominio se devuelve intacto — se conserva, no se traduce. Si la tool no
    tiene vocabulario propio, o el valor no está en él, cae en
    `normalize_status` y no se emite campo de dominio.
    """
    entrada = DOMAIN_STATUS_VOCABS.get(tool)
    if entrada and raw in entrada[1]:
        campo, mapa = entrada
        return mapa[raw], campo, raw
    canonico, _nota, _regla = normalize_status(raw)
    return canonico, None, None


def status_frontmatter_lines(tool, raw):
    """Las líneas de frontmatter que corresponden a un estado de dominio.

    Devuelve siempre `status:` canónico primero y, si aplica, el campo de
    dominio detrás. Que las 8 tools con vocabulario propio llamen aquí es lo que
    impide que vuelvan a divergir: el orden y los nombres de campo salen de un
    único sitio.
    """
    if raw is None:
        return []
    canonico, campo, valor = split_domain_status(tool, raw)
    if canonico is None:
        raise ValueError(
            f"{tool}: status {raw!r} no pertenece a su vocabulario de dominio "
            f"ni al canónico (CN-03)"
        )
    lineas = [f"status: {canonico}"]
    if campo:
        lineas.append(f"{campo}: {valor}")
    return lineas


def normalize_status(raw):
    """Lleva un `status` cualquiera al vocabulario canónico.

    Devuelve `(canonico, nota, regla)`:

      - `canonico` es un valor de `STATUS_VOCAB`, o `None` si no se pudo decidir
        — y entonces quien llama **rechaza**, no adivina. Inventar un estado es
        peor que no tenerlo: uno se detecta, el otro se hereda.
      - `nota` recoge lo que el valor original arrastraba y no era estado
        (progreso, versión, fecha). Nunca se descarta.
      - `regla` dice por qué se decidió: `canonical`, `synonym`, `qualifier`,
        `parenthetical` o `unknown`. Sirve para auditar la propia normalización.
    """
    if raw is None:
        return None, None, "unknown"

    original = str(raw).strip()
    if not original:
        return None, None, "unknown"

    # Un paréntesis o guion largo suele traer la circunstancia, no el estado:
    # "resuelto (v0.58)" es `verified` con una nota, no un estado nuevo.
    nota = None
    # El prefiltro barato va antes a propósito. `(.*?)\s*` delante de un
    # delimitador que **no está** hace al motor probar cada punto de corte:
    # 10.000 espacios sin paréntesis tardan 417 ms en decir que no. Preguntar
    # primero si hay delimitador cuesta una pasada lineal y evita el caso malo
    # entero, que es además el único que un valor hostil puede provocar.
    if any(c in original for c in "([—-"):
        m = re.match(r"^([^\(\[—-]*?)(?<!\s)\s*[\(\[—-]\s*(.+?)[\)\]]?$", original)
    else:
        m = None
    base = original
    if m and m.group(1).strip():
        candidato_base, candidato_nota = m.group(1).strip(), m.group(2).strip()
        if _canonical_status(candidato_base) is not None:
            base, nota = candidato_base, candidato_nota

    clave = base.lower().replace(" ", "_").replace("__", "_")

    if clave in STATUS_QUALIFIERS:
        canonico, cualificador = STATUS_QUALIFIERS[clave]
        return canonico, nota or cualificador, "qualifier"

    directo = _canonical_status(base)
    if directo is not None:
        regla = "parenthetical" if nota else (
            "canonical" if directo == base.lower() else "synonym"
        )
        return directo, nota, regla

    # "1-fixed-6-pending" y similares: un informe de progreso en el campo de
    # estado. No hay estado que deducir sin mentir, pero el dato se conserva.
    return None, original, "unknown"


def _canonical_status(valor):
    clave = str(valor).strip().lower().replace(" ", "_")
    if clave in STATUS_VOCAB:
        return clave
    guion = clave.replace("_", "-")
    if guion in STATUS_VOCAB:
        return guion
    if clave in STATUS_SYNONYMS:
        return STATUS_SYNONYMS[clave]
    if guion in STATUS_SYNONYMS:
        return STATUS_SYNONYMS[guion]
    return None


#: Una viñeta es una **línea** `-` o `*` seguida de blanco o de fin de línea.
#: superseded_by: este patrón (v40.35) — `^\s*[-*]\s*(.*)`, copiado en tres
#: sitios: el `\s*` cruzaba el salto de línea, así que una viñeta vacía se
#: tragaba la línea siguiente y contaba como llena, y `**negrita**` o `---`
#: pasaban por viñetas. Una lista `- ` / `- [ ]` / `- algo` salía con un 0 %
#: de vacías en vez del 67 %, y AP-20 no frenaba el esqueleto.
_VINETA = re.compile(r"^[ \t]*[-*](?:[ \t]+(.*?))?[ \t]*$", re.MULTILINE)

#: Lo que deja una viñeta sin contenido: nada, una casilla o un enlace vacío.
VINETA_VACIA = ("", "[]", "[[]]", "-", "[ ]")


def vinetas_de_lista(texto: str) -> List[str]:
    """AP-20: el texto de cada viñeta, `""` si está vacía. Dueño único (AP-57):
    `vault_write` lo usa para frenar y `vault_norms` para auditar."""
    return [(m.group(1) or "").strip() for m in _VINETA.finditer(texto)]


def compute_norm_refs(folder: str, content: str, wiki_links: List[str]) -> List[str]:
    """Las normas que aplican a una nota, deducidas de su carpeta y su cuerpo.

    Vive aquí y no en la fachada (v40.27) porque es **derivación de catálogo**:
    no lee el vault, no escribe nada y su única dependencia es `re`. Estaba
    arriba por herencia del fichero único, y eso costaba nueve cruces de
    contexto — nueve tools de Autoría importando `vault_norms`, y con él la
    fachada que reexporta el motor entero, para pedir una lista de códigos.

    Reglas:
      - universales:             AP-11, AP-12, AP-13, AP-16, CN-01, CN-02, SP-01
      - hay wikilinks:           + AP-14, AP-21, AP-22, SP-02
      - hay viñetas:             + AP-20
      - carpeta 03_Decisions/:   + AP-07
      - más de 500 líneas:       + AP-23 (informativa)
    """
    refs: set = {"AP-11", "AP-12", "AP-13", "AP-16", "CN-01", "CN-02", "SP-01"}

    if wiki_links:
        refs.update({"AP-14", "AP-21", "AP-22", "SP-02"})

    if vinetas_de_lista(content):
        refs.add("AP-20")

    folder_lower = folder.lower()
    if folder_lower.startswith("03_decisions") or "decisions" in folder_lower:
        refs.add("AP-07")

    if len(content.split("\n")) > 500:
        refs.add("AP-23")

    return sorted(refs)
