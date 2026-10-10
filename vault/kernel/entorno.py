"""Las variables de entorno del estándar, declaradas una sola vez.

Catorce variables leídas en once módulos, cada una con su `os.environ.get()` y
su default escrito a mano en el punto de lectura. Seis aparecían documentadas y
ninguna tenía guard, así que la única forma de saber qué configura el estándar
era leer los once ficheros. Dos ya divergían: `VAULT_VOICE` se compara contra
`"verbose"` en un sitio y contra `"0"` con default `"1"` en otro, y el `.mjs`
declara por su cuenta dos que Python no conoce.

Es AP-05 sobre configuración: el mismo dato —qué variable existe, de qué tipo
es, qué vale si no está— decidido en cada punto de uso. La corrección es la de
siempre en este repo: registro canónico primero, lectores derivados después,
guard que falle si aparece una lectura sin entrada.

Este módulo es kernel: declara, no decide. No importa dominio y no toca el
vault. `leer()` resuelve **al llamarse**, nunca al importarse (AP-49): una
variable fijada en tiempo de import es exactamente el vínculo congelado que ya
costó dos rondas de limpieza.

Vive en `scripts/` y no en el paquete `vault/` pese a ser kernel: un módulo de
`scripts/` tiene que seguir funcionando **copiado suelto**, que es cómo se
sincronizan los repos consumidores y lo que comprueba `test_vault_containment`
copiando solo `vault_io.py` a un repo vacío. Colgarlo de `vault.kernel` lo
rompía con un `ModuleNotFoundError`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass(frozen=True)
class Variable:
    """Una variable de configuración y todo lo que hay que saber de ella.

    `contexto` es quién la lee, con los nombres de `vault_arch.CONTEXTS`: una
    variable sin contexto dueño es la misma decisión sin dueño que AP-05
    persigue en los datos.
    """

    nombre: str
    tipo: str
    default: Any
    contexto: str
    proposito: str
    #: Cómo se convierte el texto crudo del entorno al valor útil. El default
    #: ya viene convertido, así que solo se aplica cuando la variable existe.
    convertir: Callable[[str], Any] = str


def _entero(valor: str) -> int:
    return int(valor)


def _bandera(valor: str) -> bool:
    """`"1"` enciende; cualquier otra cosa apaga.

    Ese fue siempre el criterio en `vault_io`, pero `VAULT_STRICT_ROOT` y
    `VAULT_SKIP_SECRET_SCAN` usaban la verdad de Python —cualquier cadena no
    vacía—, de modo que `VAULT_STRICT_ROOT=0` activaba el modo estricto. Se
    conserva ese comportamiento donde ya estaba (`presencia`) y no se
    generaliza: cambiarlo aquí alteraría en silencio dos guards.
    """
    return valor == "1"


def _presencia(valor: str) -> bool:
    """Basta con estar definida, con el valor que sea. Heredado, no imitado."""
    return bool(valor)


#: El registro. Una entrada por variable; el orden es el de lectura habitual.
VARIABLES: Dict[str, Variable] = {
    v.nombre: v
    for v in [
        Variable(
            "VAULT_ROOT", "ruta", None, "kernel",
            "Fuerza la raíz del vault en vez de autodetectarla. Es la costura "
            "declarada para apuntar las tools a un destino concreto.",
        ),
        Variable(
            "VAULT_STRICT_ROOT", "bandera", False, "kernel",
            "Hace fallar una detección insegura en vez de caer a la raíz del "
            "repo. Basta con estar definida (comportamiento heredado).",
            _presencia,
        ),
        Variable(
            "VAULT_PERMISSIVE_ROOT", "bandera", False, "kernel",
            "Permite ESCRIBIR sobre una raíz detectada con baja confianza "
            "(`repo_root_fallback`). Sin ella, leer con esa raíz sigue "
            "permitido y escribir se rechaza: instalado fuera del repo, ese "
            "fallback devuelve el propio directorio del programa, así que la "
            "escritura caía dentro del toolkit en vez de en un vault.",
            _bandera,
        ),
        Variable(
            "VAULT_CLIENT_CWD", "ruta", None, "kernel",
            "El directorio del cliente MCP, que el servidor no comparte con "
            "el proceso Python. Sin ella la autodetección mira el CWD del "
            "servidor, que no es el del usuario.",
        ),
        Variable(
            "VAULT_FSYNC", "bandera", False, "kernel",
            "Fuerza `fsync()` tras cada escritura atómica. Cuesta latencia; "
            "se activa cuando la durabilidad importa más que la velocidad.",
            _bandera,
        ),
        Variable(
            "VAULT_SKIP_SECRET_SCAN", "bandera", False, "kernel",
            "Desactiva el escaneo de secretos del write path. Existe para "
            "los tests del propio escáner; en uso normal no se toca.",
            _presencia,
        ),
        Variable(
            "VAULT_AGENT", "texto", "", "autoria",
            "Quién firma la nota cuando no se pasa `--agent` (AP-16). Es el "
            "campo `agent:` del frontmatter, no un identificador de sesión.",
        ),
        Variable(
            "VAULT_VOICE", "texto", "1", "autoria",
            "Verbosidad de la voz del vault: `0` la calla, `verbose` la "
            "amplía, cualquier otro valor deja el mensaje normal.",
        ),
        Variable(
            "VAULT_TOOL_TIMEOUT", "entero", 60, "kernel",
            "Segundos antes de que una tool se declare colgada. Lo leen "
            "`vault_errors` y el servidor MCP, que hasta ahora lo declaraban "
            "por separado con el mismo número.",
            _entero,
        ),
        Variable(
            "VAULT_COUNT_TOKENS", "bandera", False, "kernel",
            "Añade el conteo de tokens al envelope de error. Apagado por "
            "defecto: contar cuesta más que el propio error.",
            _bandera,
        ),
        Variable(
            "VAULT_DEBUG", "bandera", False, "kernel",
            "Adjunta el traceback a los envelopes de error. Apagada por "
            "defecto: el traceback lleva rutas absolutas del intérprete y del "
            "usuario, y por MCP llega al agente y a sus logs.",
            _bandera,
        ),
        Variable(
            "VAULT_SMOKE_TIMEOUT", "entero", 90, "meta_toolkit",
            "Segundos por tool en la pasada de humo. Más alto que "
            "`VAULT_TOOL_TIMEOUT` porque el smoke arranca un intérprete nuevo.",
            _entero,
        ),
        Variable(
            "VAULT_DQ_CACHE_MINUTES", "entero", 30, "gobernanza",
            "Cuánto vale el índice de calidad cacheado antes de recalcularlo.",
            _entero,
        ),
        Variable(
            "VAULT_SCAN_ROOTS", "texto", "", "meta_toolkit",
            "Rutas separadas por `;` donde el servidor MCP busca vaults. Vacía "
            "significa dos rutas relativas al repo, no «ninguna». Solo la lee "
            "el `.mjs`; se declara aquí para que `--env` la publique y el "
            "servidor deje de inventarse su propia tabla.",
        ),
        # Se declaró como fichero de log con default `None` mirando el nombre y
        # no al consumidor: el `.mjs` la usa como **nivel** con default
        # `"info"`. Es AP-44 en pequeño, dentro del registro que existe para
        # que las dos mitades no divergieran — y salió al contrastarlo contra
        # el único código que la lee.
        Variable(
            "VAULT_MCP_LOG", "texto", "info", "meta_toolkit",
            "Nivel de log del servidor MCP (`info` por defecto). Solo la lee "
            "el `.mjs`.",
        ),
        # SP-04. Vacía no significa «sin autenticación»: el `.mjs` genera un
        # token al arrancar y lo imprime por stderr. El default es cerrado.
        Variable(
            "VAULT_MCP_TOKEN", "texto", "", "meta_toolkit",
            "Token que exige el transporte HTTP/SSE del servidor MCP "
            "(`Authorization: Bearer`). Si falta, se genera uno por arranque. "
            "Solo la lee el `.mjs`; stdio no la usa.",
        ),
        # v41.2. Vacía es el catálogo entero, que es lo que recibía todo
        # cliente hasta ahora; un nombre que no está en `perfiles` no arranca,
        # porque caer al catálogo entero sería exponer lo que se pidió no exponer.
        Variable(
            "VAULT_MCP_PERFIL", "texto", "", "meta_toolkit",
            "Perfil de tools que el servidor MCP expone y acepta (`agente`: las "
            "del protocolo de sesión, de `tools-catalog.json` → `perfiles`). "
            "Vacía, todas las expuestas por MCP. Solo la lee el `.mjs`.",
        ),
        Variable(
            "VAULT_MCP_PYTHON", "ruta", None, "meta_toolkit",
            "Intérprete con el que el servidor MCP lanza las tools. Vacía, "
            "prueba `py`, `python3` y `python` del PATH; instalado en un venv, "
            "solo el de ese venv ve el toolkit, y `vault mcp-path` la fija a "
            "él. Solo la lee el `.mjs`.",
        ),
        # AP-63, P5. Las dos van juntas: sin el candado, el proyecto de la
        # sesión no restringe nada; con el candado y sin proyecto, se cierra.
        Variable(
            "VAULT_PROJECT", "texto", "", "kernel",
            "Proyecto al que está atada la sesión (slug o alias registrado). "
            "Solo restringe con `VAULT_PROJECT_LOCK=1`. `vault mcp-path "
            "--project` la fija ya resuelta.",
        ),
        Variable(
            "VAULT_PROJECT_LOCK", "bandera", False, "kernel",
            "Con `1`, todo `--project` que no resuelva al de `VAULT_PROJECT` "
            "se rechaza con `PROJECT_LOCKED` antes de que la tool haga nada. "
            "Encendida sin `VAULT_PROJECT`, rechaza todos: el candado no se "
            "abre por falta de configuración.",
            _bandera,
        ),
        Variable(
            "VAULT_MODEL_PROFILE", "texto", "", "consulta",
            "Perfil de modelo LLM activo. Lo propaga el servidor MCP al detectar "
            "el cliente (clientInfo.name). Lo lee vault_model_profile y vault_context_pack "
            "para adaptar el budget al modelo.",
        ),
    ]
}


def leer(nombre: str) -> Any:
    """El valor efectivo de una variable, resuelto ahora (AP-49).

    Falla si el nombre no está en el registro: una variable que nadie declaró
    es justo lo que este módulo existe para impedir, y devolver `None` la
    dejaría pasar en silencio (AP-37).
    """
    if nombre not in VARIABLES:
        raise KeyError(
            f"`{nombre}` no está en VARIABLES. Toda variable de entorno que "
            "el estándar lea se declara aquí primero: nombre, tipo, default, "
            "contexto que la lee y para qué sirve."
        )
    var = VARIABLES[nombre]
    crudo = os.environ.get(nombre)
    if crudo is None:
        return var.default
    try:
        return var.convertir(crudo)
    except (TypeError, ValueError):
        # Un `VAULT_TOOL_TIMEOUT=mucho` tumbaba el proceso con un ValueError sin
        # decir de dónde venía. El default es la respuesta correcta aquí: la
        # configuración mal escrita no debe impedir que la tool arranque.
        return var.default


#: Quién firma cuando ni `--agent` ni `VAULT_AGENT` lo dicen. Es el default
#: que trece tools escribían a mano; se conserva su valor (no-derogación).
AGENTE_HISTORICO = "claude"


def agente_por_defecto() -> str:
    """El default de todo `--agent`: `VAULT_AGENT`, y si falta, el histórico (AP-16).

    Hasta 2026-10-10 cada argparse decía `default="claude"` y no leía la
    variable que el registro declara para eso: con `VAULT_AGENT` exportada, la
    nota la firmaba el agente y el change-log de su borrado, `claude`.
    """
    return leer("VAULT_AGENT") or AGENTE_HISTORICO


def tabla() -> list[dict]:
    """El registro como datos, para `--env` y para el `.mjs`."""
    return [
        {
            "name": v.nombre,
            "type": v.tipo,
            "default": v.default,
            "context": v.contexto,
            "purpose": v.proposito,
        }
        for v in VARIABLES.values()
    ]
