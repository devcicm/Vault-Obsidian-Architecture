#!/usr/bin/env python3
"""Shared file IO helpers for vault tools."""

import copy
import json
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

from vault_encoding import (
    normalize_to_nfc,
    sanitize_content,
    strip_bom,
    decode_safely,
)

from vault_regex import (
    sanitize_wikilink_content,
    fix_nested_brackets,
    fix_whitespace_in_links,
    WIKILINK_MAX_LEN,
)

# La configuración se declara una vez y se lee por el registro, no con un
# `os.environ.get()` y un default por punto de uso. Ver `vault_entorno.py`
# para las trece variables y por qué estaban dispersas.
#
# El registro vive en `scripts/` y no en el paquete `vault/` porque un
# módulo de `scripts/` tiene que seguir funcionando **copiado suelto**: así
# se sincronizan los repos consumidores, y así lo comprueba
# `test_vault_containment`, que copia solo este fichero a un repo vacío.
# Colgarlo de `vault.kernel` lo rompía con un ModuleNotFoundError.
from vault_entorno import leer as _env


# ── Dónde está el vault: lo decide `vault_raiz` (v40.17) ──────────────────────
# Este bloque era 250 líneas de detección, override y reanclaje viviendo dentro
# del módulo que además sanea codificación, escanea secretos y regenera índices.
# Esa mezcla es la que metía a `vault_io` en un componente fuertemente conexo de
# 15 módulos: quien solo necesitaba saber *dónde* escribir se llevaba entero al
# que necesita emitir errores, que necesita trazarlos, que necesita saber dónde
# escribir. Extraído a una hoja, la arista se corta en vez de esquivarse con un
# import diferido.
#
# Se reexporta todo lo público **sin cambiar un solo nombre**: los ~89 módulos
# que hacen `from vault_io import VAULT_ROOT, get_vault_root, set_vault_root`
# siguen funcionando sin tocarse. No-derogación: la puerta de entrada histórica
# no se retira porque haya aparecido otra mejor.
import vault_raiz as _raiz
from vault_raiz import (  # noqa: F401  (reexport deliberado)
    LOW_CONFIDENCE_ORIGINS,
    get_vault_root,
    rebound_constants,
    reset_vault_root,
    set_vault_root,
    vault_root_is_confident,
    vault_root_origin,
)

#: Alias histórico. `VAULT_ROOT` se reancla igual que antes: `_reanclar_constantes`
#: recorre `sys.modules` y reapunta toda constante en MAYÚSCULAS que sea un `Path`
#: del vault, y este módulo entra en ese barrido como cualquier otro.
VAULT_ROOT: Path = _raiz.VAULT_ROOT

_detect_vault_root = _raiz._detect_vault_root



# ── Rutas de ENTRADA del usuario (AP-36) ──────────────────────────────────────
# Distinto problema que el vault root: aquí la ruta apunta al proyecto que se
# documenta, no al vault. `Path.cwd()` no vale como ancla porque el CWD del
# proceso no es el del usuario: el runner MCP lanza las tools con cwd=scripts/,
# así que `--file src/foo.ts` resolvía a `scripts/src/foo.ts` y la tool leía un
# fichero que no existe o, peor, otro que sí.


def client_cwd() -> Path:
    """Directorio desde el que el usuario invocó, no desde el que corre Python.

    El runner MCP lo publica en `VAULT_CLIENT_CWD`. Sin esa variable —CLI
    directa— el CWD del proceso sí es el del usuario y vale.
    """
    declarado = _env("VAULT_CLIENT_CWD")
    if declarado:
        candidato = Path(declarado)
        if candidato.is_dir():
            return candidato.resolve()
    return Path.cwd()


def resolve_input_path(file_path) -> Path:
    """Ancla una ruta de entrada relativa contra client_cwd(). Absoluta: intacta."""
    p = Path(file_path)
    return p if p.is_absolute() else client_cwd() / p


# ── Contrato de tools (v39) ───────────────────────────────────────────────────
# El contrato vive DENTRO del vault: es un artefacto de datos del vault, no un
# archivo de las tools. Hasta v38.1 se escribía en scripts/tool-spec.json —
# fuera de todo vault y con write_text() no atómico.
TOOL_SPEC_NAME = "tool-spec.json"

#: Ubicación legacy (v33–v38.1). Se sigue LEYENDO para no romper vaults e
#: instalaciones que aún no han migrado — política de no-derogación. Nunca se
#: escribe aquí.
LEGACY_TOOL_SPEC = Path(__file__).resolve().parent / TOOL_SPEC_NAME


def tool_spec_path() -> Path:
    """Ruta canónica del contrato de tools: <vault>/00_System/tool-spec.json."""
    return get_vault_root() / "00_System" / TOOL_SPEC_NAME


def resolve_tool_spec() -> Optional[Path]:
    """Contrato existente a leer: el canónico si está, si no el legacy.

    Devuelve None si no existe en ninguna de las dos ubicaciones (los lectores
    ya tienen fallback a sus datos hardcodeados).
    """
    canonical = tool_spec_path()
    if canonical.exists():
        return canonical
    if LEGACY_TOOL_SPEC.exists():
        return LEGACY_TOOL_SPEC
    return None


# ── Exclusión mutua y escritura atómica: el mecanismo vive en `vault_fs` (v40.17)
# El lock reentrante y el par temporal→os.replace no saben nada de vaults: son
# sistema de ficheros puro. Estaban aquí, y por eso `vault_errors_trace` —que
# solo quiere depositar un JSON que él mismo genera— tenía que importar el
# módulo que sanea codificación y regenera índices, cerrando el ciclo
# `errors → errors_trace → io → encoding → errors`.
#
# Lo que se queda en este módulo es la POLÍTICA: qué se comprueba antes de
# escribir, qué se sanea, qué se cuenta como trabajo y qué índices se recalculan
# después. Ver `atomic_write_text`, que ahora se lee como lo que siempre fue.
from vault_fs import (  # noqa: F401  (reexport deliberado)
    _escribir_temporal,
    _fsync_si_procede,
    _held,
    _local_lock_for,
    _HELD_LOCKS,
    _LOCAL_LOCKS,
    _LOCAL_LOCKS_GUARD,
    escritura_atomica,
    file_lock,
    guarda_secretos,
)

def assert_within_vault(path: Path, vault_root: Path) -> Path:
    """Resolve *path* and verify it stays inside *vault_root*.

    Protects against:
    - Absolute --folder args: Path("/vault") / "/etc" → "/etc" (pathlib replaces base)
    - Path traversal: --folder "../../outside"

    Returns the resolved absolute path on success; raises ValueError otherwise.
    """
    resolved = path.resolve()
    vault_resolved = vault_root.resolve()
    try:
        resolved.relative_to(vault_resolved)
    except ValueError:
        raise ValueError(
            f"Path '{path}' resolves to '{resolved}' which is outside "
            f"vault root '{vault_resolved}'. Use a relative path within the vault."
        )
    return resolved


# ── AP-37: el ledger de escrituras vive en `vault_ledger` (v40.17) ────────────
# Contabilidad thread-local pura: cuenta created/updated/unchanged y no toca el
# disco para nada. Que estuviera aquí es lo que obligaba a `vault_errors` —el
# módulo con más fan-in del repo, 110 importadores— a importar `vault_io` solo
# para poner un contador a cero antes de lanzar la tool. Esa arista cerraba el
# ciclo `errors → io → encoding → errors`.
#
# Reexportado sin cambiar nombres: `from vault_io import write_report` sigue
# siendo válido.
from vault_ledger import (  # noqa: F401  (reexport deliberado)
    _NO_ES_TRABAJO,
    _ledger,
    _record_write,
    _write_ledger,
    record_raw_write,
    write_ledger_reset,
    write_report,
)



#: Fallos del escáner de secretos ocurridos en este proceso. En memoria además
#: de en disco: un test —y la propia tool— pueden preguntarlo sin leer ficheros.
_ESCANER_DEGRADADO: List[Dict[str, str]] = []

SCANNER_DEGRADED_LOG = "scanner-degraded.jsonl"


def _registrar_escaner_degradado(path: Path, exc: BaseException) -> None:
    """Deja constancia de que una escritura pasó sin escanear.

    Nunca levanta: si esto fallara, el remedio sería peor que la enfermedad.
    """
    entrada = {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "path": str(path),
        "error": f"{type(exc).__name__}: {exc}",
    }
    _ESCANER_DEGRADADO.append(entrada)
    try:
        destino = get_vault_root() / "00_System" / SCANNER_DEGRADED_LOG
        destino.parent.mkdir(parents=True, exist_ok=True)
        # Append directo a propósito: pasar por atomic_write_text aquí sería
        # recursión, y el registro tiene que sobrevivir justo al caso en que
        # el write path está roto.
        with open(destino, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    except Exception:
        pass  # el registro es best-effort; la lista en memoria ya lo tiene


def scanner_degradations() -> List[Dict[str, str]]:
    """Escrituras de este proceso que se hicieron sin escaneo de secretos."""
    return list(_ESCANER_DEGRADADO)


#: Nombres de dispositivo reservados de Windows. Un fichero llamado así no es un
#: fichero: `CON` es la consola, `NUL` el vacío, `COM1`/`LPT1` puertos. La
#: reserva ignora la extensión —`con.md` es `CON` igual— y no distingue
#: mayúsculas.
_NOMBRES_RESERVADOS = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


def _rechazar_nombre_reservado(path: Path) -> None:
    """Bloquea nombres que en Windows son dispositivos, no ficheros.

    Una nota titulada «CON», «Aux» o «Com1» produce por slug `con.md`, `aux.md`,
    `com1.md` — y ahí deja de haber fichero. Medido: `Path('con.md').exists()`
    devuelve `True` en un directorio vacío, `os.lstat` da `st_mode=S_IFCHR`, la
    escritura se va a la consola y **cualquier lectura se cuelga indefinidamente**
    esperando entrada. No falla: se queda. Es la peor forma de fallo que puede
    tener un vault, porque el proceso que lo abra no muere ni avisa.

    Se bloquea en el write path y no en el generador de slugs porque los slugs
    los generan 22 sitios y las escrituras pasan todas por aquí — el mismo
    reparto que AP-46. Se prohíbe el nombre, no el prefijo: `console.md` y
    `contrato.md` son ficheros perfectamente normales, y confundir «empieza por
    con» con «es CON» apagaría media sección de conceptos.

    Salió al ejecutar, no al leer: un test de durabilidad que llamó `con.md` a su
    fichero de control se colgó para siempre en vez de fallar (regla 7 en su
    forma más barata — el estándar se desarrolla en Windows y aun así nadie lo
    había escrito).
    """
    if path.stem.upper() in _NOMBRES_RESERVADOS:
        raise ValueError(
            f"atomic_write bloqueado: '{path.name}' usa el nombre de dispositivo "
            f"reservado '{path.stem.upper()}'. En Windows no sería un fichero sino "
            f"un dispositivo, y leerlo cuelga al proceso en vez de fallar. Renombra "
            f"la nota (p. ej. '{path.stem}-nota{path.suffix}')."
        )


def _rechazar_raiz_insegura(path: Path) -> None:
    """Bloquea la escritura cuando NO se sabe cuál es el vault (v40.30).

    `vault_root_is_confident()` existía desde v39 y no lo hacía cumplir nadie:
    era un dato que el guard AP-36 publicaba en un informe. Medido instalando el
    toolkit fuera del repo, `_detect_vault_root()` cae a `repo_root_fallback` y
    devuelve **el propio directorio del programa**, así que una tool de
    escritura sembraba `00_System/`, `99_Index/` y notas dentro del toolkit.
    Dentro de este repo no se ve nunca: el manifiesto activa la rama anterior
    (`spec_repo_sandbox`), que sí es confiada.

    Se rechaza aquí y no en la detección a propósito. Elevar el fallback a
    excepción haría que `import vault_io` reventase en cualquier entorno sin
    vault —el import evalúa `VAULT_ROOT` a nivel de módulo—, y romper la lectura
    para proteger la escritura es un precio que no hay por qué pagar: leer con
    una raíz dudosa no ensucia nada. El daño empieza al escribir, y este es el
    único sitio por el que toda escritura pasa.

    `VAULT_PERMISSIVE_ROOT=1` restaura el comportamiento anterior para quien
    dependa de él (no-derogación), y `VAULT_ROOT` o `set_vault_root()` son la
    salida buena: las dos dan un origen confiado y no hacen falta banderas.
    """
    if vault_root_is_confident() or _env("VAULT_PERMISSIVE_ROOT"):
        return
    # Solo si la escritura cae DENTRO de la raíz dudosa. Una tool con `--root`
    # apuntada a un vault de verdad no tiene por qué pagar por el hecho de que
    # la autodetección no encontrara nada.
    raiz = get_vault_root().resolve()
    try:
        path.resolve().relative_to(raiz)
    except ValueError:
        return
    raise PermissionError(
        f"No se identificó ningún vault: la raíz activa es {raiz}, elegida por "
        f"`{vault_root_origin()}`, que significa «no encontré nada y estoy "
        "suponiendo». Escribir aquí sembraría artefactos de vault dentro del "
        "propio toolkit. Exporta VAULT_ROOT=<ruta del vault>, o crea un "
        "directorio 'vault-<nombre>/'. Para volver al comportamiento anterior, "
        "VAULT_PERMISSIVE_ROOT=1."
    )


def _rechazar_traversal(path: Path) -> None:
    """Bloquea la escritura si la ruta SALE del vault por `..`.

    `assert_within_vault()` existe desde v28, pero es el llamante quien tiene
    que acordarse de invocarla, y trece módulos que escriben no lo hacían. Aquí
    la comprobación es del propio write path, así que no depende de la memoria
    de nadie.

    Lo que se prohíbe es el traversal —el `..` que trepa por encima de la raíz,
    que es el vector real de AP-36—. NO se exige que toda escritura caiga bajo
    `get_vault_root()`: hay escrituras legítimas contra otro vault (tests con
    raíz temporal, tools con `--root`, migraciones entre vaults), y confundir
    "otro vault" con "fuera del vault" convertiría el guard en ruido.
    """
    if ".." not in path.parts:
        return
    raiz = get_vault_root().resolve()
    resuelta = path.resolve()
    try:
        resuelta.relative_to(raiz)
    except ValueError:
        raise ValueError(
            f"atomic_write bloqueado: '{path}' resuelve a '{resuelta}', fuera del "
            f"vault '{raiz}'. Las rutas se derivan de get_vault_root(), nunca por "
            f"concatenación de un argumento del usuario (AP-36)."
        )


#: Notas escritas en este proceso cuyo frontmatter parsea pero sale sin `type:`.
#: No se bloquea —hay notas legítimas sin tipo y romper el estándar entero por
#: eso sería peor—, pero deja de ser invisible (AP-46).
_FRONTMATTER_SIN_TIPO: List[Dict[str, str]] = []

#: Rutas donde un frontmatter roto es el dato, no el defecto: copias, historia y
#: cuarentena guardan justamente lo que vino mal para poder repararlo después.
_SIN_GUARD_FRONTMATTER = frozenset({"vault-backups", ".history", "20_Quarantine"})


def frontmatter_degradations() -> List[Dict[str, str]]:
    """Notas escritas en este proceso con frontmatter válido pero sin `type:`."""
    return list(_FRONTMATTER_SIN_TIPO)


def _verificar_frontmatter(path: Path, text: str) -> None:
    """Relee el frontmatter que se va a escribir, con el criterio del consumidor.

    AP-46: veintiséis tools montan el bloque concatenando líneas y ninguna
    comprueba el resultado. El fallo no se ve al escribir —la tool devuelve
    `ok: true` porque el fichero se creó— sino al auditar, cuando la nota ya es
    el dato. `vault_migrate_docs` cortaba el documento por la línea 7 y llevaba
    versiones publicándose con el bloque sin cerrar.

    Verificar aquí alcanza a las 26 tools sin tocar ninguna, y la adopción de
    `vault_write` puede seguir siendo gradual. Se valida con `yaml.safe_load`
    —lo que usa quien lo lee— y no con un regex por líneas (AP-44).

    Bloquea solo lo que nunca es intencional: abrir `---` y no cerrarlo, o un
    bloque que no parsea. La ausencia de `type:` se registra sin bloquear.
    """
    if path.suffix.lower() != ".md" or not text.startswith("---"):
        return
    if _SIN_GUARD_FRONTMATTER & set(path.parts):
        return

    cuerpo = text.split("\n", 1)[1] if "\n" in text else ""
    cierre = cuerpo.find("\n---")
    if cierre == -1 and not cuerpo.startswith("---"):
        raise ValueError(
            f"atomic_write bloqueado: '{path.name}' abre frontmatter con '---' y "
            f"nunca lo cierra. El bloque se construyó a mano y nadie releyó el "
            f"resultado (AP-46)."
        )
    bruto = cuerpo[: cierre + 1] if cierre != -1 else ""

    try:
        import yaml
    except ImportError:
        return
    try:
        datos = yaml.safe_load(bruto)
    except Exception as exc:
        raise ValueError(
            f"atomic_write bloqueado: el frontmatter de '{path.name}' no parsea "
            f"como YAML ({type(exc).__name__}: {exc}). Es lo que verá quien lea la "
            f"nota, no lo que creyó escribir la tool (AP-46)."
        )
    if isinstance(datos, dict) and not datos.get("type"):
        _FRONTMATTER_SIN_TIPO.append({"path": str(path), "reason": "missing_type"})



def atomic_write_text(
    path: Path, text: str, encoding: str = "utf-8", sanitize: bool = True
) -> None:
    """Write text to file with optional encoding sanitization.

    Args:
        path: Destination file path
        text: Content to write
        encoding: Text encoding (default: utf-8)
        sanitize: If True, applies encoding sanitization (default: True)

    v36: Pre-write secret scan (I1/I5 fix). If text contains critical
    secrets (AWS keys, GitHub tokens, bearer tokens, private keys), the
    write is aborted with a descriptive error. Set env var
    VAULT_SKIP_SECRET_SCAN=1 to bypass (not recommended).
    """
    if text and not _env("VAULT_SKIP_SECRET_SCAN"):
        try:
            guarda_secretos(path, text)
        except PermissionError:
            raise
        except Exception as exc:
            # No se bloquea la escritura por un fallo del escáner —eso
            # convertiría un bug del guard en una caída del estándar entero—,
            # pero un escáner roto dejaba de proteger sin que nadie se enterara.
            # Queda registrado para que `vault_audit` lo vea (AP-37: el fallo
            # silencioso se cuenta como éxito).
            _registrar_escaner_degradado(path, exc)

    _rechazar_raiz_insegura(path)
    _rechazar_traversal(path)
    _rechazar_nombre_reservado(path)
    _verificar_frontmatter(path, text or "")

    path.parent.mkdir(parents=True, exist_ok=True)

    # Apply encoding sanitization if enabled
    if sanitize and text:
        # Strip BOM if present
        text, had_bom = strip_bom(text)

        # Apply full sanitization pipeline (auto-fix mode)
        text, fixes = sanitize_content(text, dry_run=False)

        # Log fixes if any were applied (for debugging)
        if fixes:
            try:
                from vault_encoding import log_encoding_fixes

                log_encoding_fixes(fixes, path, "atomic_write_text")
            except Exception:
                pass  # Don't fail writing if logging fails

    # Se clasifica con el texto YA saneado: comparar contra el original daría
    # `updated` en escrituras que el saneado deja idénticas.
    _record_write(path, text, encoding)

    # El mecanismo —temporal, fsync opcional, os.replace y limpieza del huérfano
    # si algo falla— está en `vault_fs.escritura_atomica`. Las guardas ya se han
    # ejecutado arriba, así que aquí no se pasa ninguna: esta función las quiere
    # con su propio manejo de errores (el escáner degradado se registra en vez de
    # abortar), y eso es política, no mecanismo.
    escritura_atomica(path, text, encoding)

    _auto_section_index(path)

    _auto_tag_ledger(path, text)


# Carpetas que no disparan la cascada de índices. Son dos cosas distintas y
# conviene no mezclarlas: las dos secciones canónicas que gestionan su propio
# índice, y todo lo que ni siquiera es una sección — eso último lo declara
# `vault_registry.NON_SECTION_ROOT_FOLDERS`, que es también lo que el audit
# consulta para CN-02. Tenerlo copiado aquí fue como `docs/` acabó siendo
# invisible para el kernel y una violación para el audit (AP-05).
_SECCIONES_CON_INDICE_PROPIO = frozenset({"00_System", "99_Index"})


def _skip_auto_index() -> frozenset:
    from vault_registry import NON_SECTION_ROOT_FOLDERS  # lazy: registro sin deps

    return _SECCIONES_CON_INDICE_PROPIO | frozenset(NON_SECTION_ROOT_FOLDERS)


_SKIP_AUTO_INDEX = _skip_auto_index()


def _auto_section_index(path: Path) -> None:
    """Auto-trigger section index update after writing any vault .md note.

    Called internally by atomic_write_text. Covers all tools without requiring
    each one to explicitly call update_section_index — single responsibility point.

    Skips: non-.md files, index.md itself, system/index sections, paths outside vault.
    Uses lazy import to avoid circular dependency with vault_section_index.
    """
    if path.suffix != ".md":
        return
    try:
        rel = path.relative_to(get_vault_root())
    except ValueError:
        return  # path outside vault root
    parts = rel.parts
    if len(parts) < 2:
        return
    section = parts[0]
    if section in _SKIP_AUTO_INDEX:
        return
    try:
        from vault_section_index import (
            vault_section_index,
        )  # lazy — avoids circular import

        # Self-healing: si lo escrito ES un index.md (un agente lo generó a
        # mano, posiblemente con [[stem|alias]] en las celdas — formato
        # prohibido), regeneramos el índice canónico encima. Sin recursión:
        # el generador escribe via Path.write_text, no via atomic_write_text.
        vault_section_index(section)
    except Exception as exc:
        try:
            from vault_errors import emit_error  # type: ignore
            emit_error("_auto_section_index", "AUTO_INDEX_ERROR", str(exc))
        except Exception:
            pass  # AP-37: fail-safe logging — never crash the caller


def _auto_tag_ledger(path: Path, text: str) -> None:
    """Anota en la bitácora de vocabulario los tags de la nota recién escrita.

    AP-39 dice que un tag nuevo se admite **pero se registra**, y hasta ahora lo
    registraba un solo escritor: `vault_write`. Los catorce `*_save` que llevan
    tags construyen su frontmatter y llaman directamente a `atomic_write_text`,
    así que la norma se cumplía en una de cada quince escrituras. El término
    entraba en el vault, la bitácora no se enteraba, y el audit lo denunciaba
    después contra la nota — culpando al contenido de un fallo del escritor. Es
    AP-43 en su forma literal: norma sin refuerzo en el punto de uso.

    Va aquí y no en cada tool por lo mismo que `_auto_section_index`: este es el
    único punto por el que pasan todas las escrituras. Ponerlo en los catorce
    sitios funciona hasta que alguien escribe el decimoquinto.

    Nunca levanta ni bloquea: la bitácora es memoria, no un guard. Si falla, la
    escritura ya es válida y el audit de AP-39 recoge el término más tarde.
    """
    if path.suffix != ".md" or not text.startswith("---"):
        return
    try:
        rel = str(path.relative_to(get_vault_root())).replace("\\", "/")
    except ValueError:
        return  # fuera del vault: no es una nota
    if rel.split("/")[0] in _SKIP_AUTO_INDEX:
        return
    try:
        from vault_tags import (  # lazy — evita el ciclo con el kernel
            registrar_tags_de_nota,
            tags_de_frontmatter,
        )

        registrar_tags_de_nota(tags_de_frontmatter(text), rel)
    except Exception as exc:
        try:
            from vault_errors import emit_error  # type: ignore
            emit_error("_auto_tag_ledger", "AUTO_TAG_LEDGER_ERROR", str(exc))
        except Exception:
            pass  # AP-37: fail-safe logging — never crash the caller


def atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    atomic_write_text(
        path, json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8",
        sanitize=False,
    )


@contextmanager
def indice_compartido(path: Path, vacio: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    """Lee un índice compartido, deja mutarlo y lo devuelve al disco, bajo lock.

    `atomic_write_json` garantiza que el fichero nunca queda a medias, y **no
    hace nada** contra el problema real de estos índices, que es otro: cinco
    `*_save` hacían `load_index()` → mutar → `atomic_write_json()` sin lock.
    Dos guardados concurrentes leen el mismo índice, cada uno añade su entrada,
    gana el segundo, y la primera desaparece — con las dos tools devolviendo
    `ok: true`. Es AP-37 por la puerta de atrás: trabajo perdido reportado como
    éxito.

    La otra mitad es peor y por eso el lock abarca **desde la lectura hasta la
    escritura**, no solo la escritura: tres de esos índices son además el
    contador del correlativo (`len(index["bugs"]) + 1`). Reservar el número
    fuera del lock hace que dos guardados obtengan `REQ-001` los dos, escriban
    el mismo nombre de fichero y uno pise al otro. El número tiene que salir
    del mismo tramo exclusivo que lo consume.

    `vacio` es lo que se devuelve cuando el índice no existe todavía. Se copia
    en profundidad: si se cediera el mismo objeto, dos llamadas sobre un vault
    recién creado compartirían la lista y la segunda vería las entradas de la
    primera.

    **Solo escribe si algo cambió.** Tres de los cinco tienen un `return`
    temprano dentro de la región —rutas de error como `INVALID_PATH`— que hoy
    no tocan el índice. Un `with` sale por ahí de forma normal, así que la
    escritura se ejecutaría igualmente y el camino de fallo pasaría a tener un
    side-effect que no tenía, contado además por `write_report()`. Comparar
    antes de escribir es más barato que pedirle a cinco puntos de uso que se
    acuerden de confirmar, y deja la regla donde se puede comprobar: si no
    cambió nada, no se escribe nada (AP-36, AP-37).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(path, timeout=30.0):
        try:
            datos = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            datos = copy.deepcopy(vacio)
        antes = json.dumps(datos, sort_keys=True, ensure_ascii=False)
        yield datos
        if json.dumps(datos, sort_keys=True, ensure_ascii=False) != antes:
            atomic_write_json(path, datos)


def safe_wikilink(text: str) -> str:
    """Sanitize text for safe use inside [[...]] wiki-links (AP-22 guard).

    Sanitization steps:
    1. Fix nested brackets: [[[[ -> [[
    2. Fix whitespace: [[  note  ]] -> [[note]]
    3. Validate length (max WIKILINK_MAX_LEN chars)
    4. Remove brackets, pipe, newlines, quotes, backslashes
    5. Collapse multiple dashes
    6. Strip leading/trailing dashes

    Returns a safe fallback if result is empty.

    Raises:
        ValueError: If result exceeds max length after sanitization.
    """
    if not text or not text.strip():
        return "nota-sin-titulo"

    sanitized = text.strip()

    # Step 1: Fix nested brackets
    sanitized = fix_nested_brackets(sanitized)

    # Step 2: Fix whitespace inside links
    sanitized = fix_whitespace_in_links(sanitized)

    # Step 3: Validate length BEFORE removing characters (length is about content)
    if len(sanitized) > WIKILINK_MAX_LEN:
        # Try to sanitize first, then check again
        pass

    # Step 4: Remove brackets, pipe, newlines, quotes, backslashes
    sanitized = re.sub(r'[\[\]\|\n\r"\\]', "", sanitized)

    # Step 5: Collapse multiple spaces to single space
    sanitized = re.sub(r"[\s]+", " ", sanitized)

    # Step 6: Collapse multiple dashes and strip
    sanitized = re.sub(r"-{2,}", "-", sanitized).strip("-")

    # Step 7: Final strip
    sanitized = sanitized.strip()

    # Validate length after all processing
    if len(sanitized) > WIKILINK_MAX_LEN:
        sanitized = sanitized[:WIKILINK_MAX_LEN]

    return sanitized or "nota-sin-titulo"


def normalize_stem(s: str) -> str:
    """Canonical form for fuzzy stem comparison (vault_write + vault_audit).

    Strips case, dashes, underscores, spaces, dots, and the .md suffix.
    Used to detect whether a wiki-link target actually exists anywhere in
    the vault regardless of how it was written (kebab-case, snake_case, spaces).

    Examples:
        normalize_stem("Mi Proyecto Demo")   -> "miproyectodemo"
        normalize_stem("mi-proyecto-demo.md") -> "miproyectodemo"
        normalize_stem("mi_proyecto_demo")    -> "miproyectodemo"
        normalize_stem("Índice")              -> "indice"

    Los acentos se pliegan porque `slugify` translitera al derivar el nombre de
    fichero: sin plegarlos aquí, `Índice.md` (escrita antes) e `indice.md` (la
    que se derivaría hoy) parecerían dos notas distintas y el vault acabaría con
    las dos. El criterio de comparación tiene que ser el del consumidor, no el
    de quien escribe (AP-44).
    """
    from vault_lib import fold_accents

    return (
        fold_accents(s)
        .lower()
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
        .replace(".", "")
        .removesuffix("md")
    )


def update_section_index(folder: str) -> None:
    """Regenerate section index without silently discarding errors.

    Calls vault_section_index and logs failures to the trace log instead of
    swallowing them with bare except/pass. Safe to call from any tool.
    """
    try:
        from vault_section_index import vault_section_index  # type: ignore

        vault_section_index(folder)
    except Exception as exc:
        try:
            from vault_errors import emit_error  # type: ignore

            emit_error(
                "update_section_index",
                "UNEXPECTED_ERROR",
                f"Failed to update index for {folder}: {exc}",
            )
        except Exception:
            pass  # logging failure must never crash the caller


def atomic_update_json(
    path: Path,
    default: Dict[str, Any],
    update: Callable[[Dict[str, Any]], Dict[str, Any]],
    timeout: float = 30.0,
) -> Dict[str, Any]:
    with file_lock(path, timeout=timeout):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = dict(default)
        except (FileNotFoundError, json.JSONDecodeError):
            data = dict(default)
        updated = update(data)
        atomic_write_json(path, updated)
        return updated


#: Directorios cuyo contenido es una INSTANTÁNEA congelada, no una nota viva.
#: AP-36 obliga a que los side-effects (backups, papelera, historial) vivan
#: DENTRO del vault. Sin excluirlos, toda tool que barre `rglob("*.md")` se
#: audita a sí misma: en el vault de BuilderX eran 194 de 216 violaciones de
#: `vault_norms` (90%) y 46 de 69 errores Mermaid (67%), todas en copias de
#: seguridad. No es solo ruido en la métrica — manda al agente a "corregir" una
#: instantánea, que es exactamente lo que destruye su valor como backup. Una
#: violación dentro de un backup ya se reportó cuando la nota estaba viva.
#:
#: Vive aquí, y no en la tool que lo descubrió, porque el criterio de "qué es
#: una nota viva" es del vault, no de un barrido concreto.
SNAPSHOT_DIRS = ("vault-backups", ".trash", ".history")


def is_snapshot_path(rel: "str | Path") -> bool:
    """True si la ruta cae dentro de una instantánea congelada.

    Compara segmento a segmento — un `in` sobre la cadena daría falso positivo
    en una nota legítima como `07_Knowledge/concepts/como-usar-vault-backups.md`.
    Acepta separador de Windows porque las rutas relativas llegan de `os.path`.
    """
    partes = str(rel).replace("\\", "/").split("/")
    return any(p in SNAPSHOT_DIRS for p in partes)
