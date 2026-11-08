#!/usr/bin/env python3
"""vault.kernel.vcs — la memoria del vault versionada en git. Nadie más lo sabe.

Módulo hoja del núcleo: **no importa ningún `vault_*`** salvo el dueño de git
(`vault.kernel.procesos_git`, su hermano de paquete) y `pathlib`. La raíz del
vault la recibe como argumento: resolverla aquí cerraría el ciclo
`kernel -> scripts` (AP-62).

## Qué hace y por qué existe

Un vault es memoria de un agente: lo que escribe es lo que sabe. Sin
historia, un error —una operación que tapó lo que no debía, una tool que
truncó una nota— se queda sin vuelta atrás. Hoy el toolkit tenía tres capas
de vuelta atrás, y ninguna cubría una operación completa:

- `.history/` + `vault_undo`: **por nota**. No puede deshacer una operación
  que tocó varias notas.
- `vault_backup` + `vault_restore`: **de todo el vault**, pero el restore
  borra lo más nuevo (antes de este trabajo, sin red: ahora el estado actual
  se copia antes de sustituir).
- `change-log.md`: **el registro**, no el contenido.

El repo de git que ya nace con cada vault (la casa y, desde v41.26, también
una ruta personalizada) es la capa que falta: **una operación = un commit**,
y volver a como estaba es volver a un commit.

## La puerta

Todo verbo de git pasa por `vault.kernel.procesos_git` (AP-68): aquí no hay
`subprocess` con git. Los verbos que escriben historia (`add`, `commit`) están
autorizados en `MUTADORES_AUTORIZADOS` con el motivo escrito, y `checkout`/
`restore` —los del deshacer— también.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from vault.kernel import procesos_git
from vault.kernel.procesos_git import es_hash

#: **El repo del vault versiona notas: markdown y nada más.** Lo decide el
#: dueño del versionado, no cada vault.
#:
#: La regla es una lista de patrones con la semántica de `.gitignore` —gana el
#: último que casa—, y el orden importa:
#:
#: 1. `*` deja fuera todo (json de estado, trazas, `.bak`, contadores).
#: 2. `!*/` deja recorrer las carpetas: sin esto git no baja a buscar notas.
#: 3. `!*.md` devuelve las notas.
#: 4. `!.gitignore` versiona la política para que viaje con el vault.
#: 5. `!00_System/.change-log.json` es la única excepción no-`.md`, y es
#:    **dato, no derivado**: ninguna nota la produce. La leen `vault_impact`
#:    (qué cambió desde una fecha), SP-01 y la métrica F8 del marco de datos
#:    (no-repudio: una entrada por nota). Sin ella, una copia del vault
#:    pierde la autoría de cada nota y no hay de dónde reconstruirla: los
#:    mensajes de los commits son genéricos y no nombraban al agente. Un
#:    JSON que se regenera de las notas (`graph.json`, `hash-index.json`)
#:    no entra ni entra este.
#: 6. Las carpetas de abajo van **después** de las negaciones porque contienen
#:    `.md` que no son notas: `.history/` son copias de versión (su nombre
#:    acaba en `.md`), `vault-backups/` son copias del vault entero y
#:    `.trash/` es lo borrado. Sin estas líneas, `!*.md` las metería.
#:
#: Lo que esto deja fuera del repo, además del ruido: los JSON de estado del
#: sistema (`graph.json`, `hash-index.json`, `tool-spec.json`,
#: `standard-version.json`…) y los `.gitkeep` de las carpetas vacías. Son
#: derivados o andamiaje: se regeneran, no son memoria. La memoria son las
#: notas y la bitácora que dice quién las escribió.
IGNORADOS_EN_GIT = (
    "*",
    "!*/",
    "!*.md",
    "!.gitignore",
    "!00_System/.change-log.json",
    ".history/",
    "vault-backups/",
    ".locks/",
    "00_System/.trash/",
)

#: Lo que además no se versiona por **riesgo**: la credencial que escribe el
#: servicio de tokens vive dentro del vault (SP-04, para que solo la lea quien
#: puede leer el vault). Con la política de arriba ya queda fuera por no ser
#: `.md`, pero se nombra para que el día que la política cambie —o que una tool
#: escriba un secreto con extensión de nota— su test lo diga.
IGNORADOS_POR_RIESGO = (
    "00_System/token-usage/",
)

#: La lista completa, en el orden en que se escribe el `.gitignore`.
IGNORADOS = IGNORADOS_EN_GIT + IGNORADOS_POR_RIESGO

#: La identidad local del repo del vault. Es **local** (`git config --local`):
#: no toca la configuración global de la máquina, que es de la persona.
IDENTIDAD_LOCAL = ("vault", "vault@local")


def hay_repo(raiz: Path) -> bool:
    """¿El vault tiene repositorio propio?"""
    return (Path(raiz) / ".git").exists()


def _git(raiz: Path, *args: str, env: Optional[Dict[str, str]] = None):
    extra = {"env": env} if env is not None else {}
    return procesos_git.ejecutar_git(Path(raiz), list(args),
                                     capture_output=True, **extra)


def identidad_de_commit() -> Dict[str, str]:
    """La identidad del commit, por ENTORNO y no por `config`.

    `git config user.name X` es un uso mutador de un verbo ambiguo y la puerta
    de AP-68 lo veta (con razón: escribe configuración). Y el commit necesita
    identidad: un runner de CI no tiene `user.name` global y el vault se
    quedaba sin commits (medido en la CI del 2026-11-04). Las variables
    `GIT_AUTHOR_*`/`GIT_COMMITTER_*` dan identidad a ESE commit sin tocar la
    configuración de la máquina ni la del repo.
    """
    import os

    nombre, correo = IDENTIDAD_LOCAL
    return {
        **os.environ,
        "GIT_AUTHOR_NAME": nombre,
        "GIT_AUTHOR_EMAIL": correo,
        "GIT_COMMITTER_NAME": nombre,
        "GIT_COMMITTER_EMAIL": correo,
    }


def asegurar_ignorados(raiz: Path) -> Dict[str, Any]:
    """Garantiza que el `.gitignore` del vault tenga lo que no se versiona.

    Idempotente y **aditivo**: si la persona ya escribió un `.gitignore`, su
    texto se conserva y solo se añaden las líneas que falten. No reescribe nada
    cuando no falta ninguna.

    Existe porque el `.gitignore` nació dentro del bootstrap de `vault_init`,
    que solo corre al **crear** el repo: un vault que ya tenía repositorio no
    lo recibía nunca y seguía versionando `.history/`, `.trash/` y la
    credencial. Medido el 2026-11-05 en un vault real: 99 de 345 ficheros
    rastreados eran versiones de `.history/`. Por eso la garantía vive aquí,
    en el dueño del versionado, que sí corre en cada operación.
    """
    raiz = Path(raiz)
    destino = raiz / ".gitignore"
    original = ""
    if destino.is_file():
        original = destino.read_text(encoding="utf-8", errors="replace")
    presentes = {linea.strip() for linea in original.splitlines()}
    faltan = [ruta for ruta in IGNORADOS if ruta not in presentes]
    if not faltan:
        return {"escrito": False, "anadidos": []}

    texto = original
    if texto and not texto.endswith("\n"):
        texto += "\n"
    texto += "\n".join(faltan) + "\n"
    destino.write_text(texto, encoding="utf-8")
    return {"escrito": True, "anadidos": faltan}


def _rastreados_ignorados(raiz: Path, tope: Optional[int] = 5) -> Tuple[List[str], Optional[str]]:
    """Ficheros que el índice sigue versionando pese a estar ignorados.

    `git rm --cached` los sacaría, pero es un verbo mutador que AP-68 solo
    autoriza al verbo de reparación (`reparar_indice`, abajo): retirar
    contenido del índice es una decisión visible, no un efecto colateral de
    una operación. Por defecto se publican los cinco primeros para que la
    deuda vieja sea visible en vez de silenciosa (AP-51); `tope=None`
    devuelve la lista entera, que es lo que el reparador necesita.

    **Devuelve dos cosas, no una** (AP-51): la lista y el motivo del fallo.
    Un `git` que no puede responder —«dubious ownership», un repo de otra
    cuenta, un binario que no está— devuelve una lista vacía, y una lista
    vacía indistinguible de «no hay nada que reparar» es un fallo presentado
    como un éxito. Medido el 2026-11-08: un vault cuyo repo pertenece a otra
    cuenta respondió «cero» cuando en realidad git no había dicho nada.
    """
    r = _git(raiz, "ls-files", "-ci", "--exclude-standard")
    if r.returncode != 0:
        motivo = (r.stderr or r.stdout or "git ls-files no pudo responder").strip()
        return [], (motivo[:300] or "git ls-files no pudo responder")
    lineas = [l for l in (r.stdout or "").splitlines() if l.strip()]
    return (lineas if tope is None else lineas[:tope]), None


def reparar_indice(raiz: Path) -> Dict[str, Any]:
    """El verbo de reparación del dueño: trae el índice a la política vigente.

    Un vault que nació antes de la capa de git tiene en su repo lo que hoy
    la política ignora —copias de `.history/`, JSON de estado, la credencial
    del servicio de tokens—: `commit_de_operacion` ya repara el `.gitignore`
    en cada escritura, pero eso no saca nada del índice; los ficheros siguen
    versionados hacia atrás. Este verbo es la decisión explícita:

    1. Garantiza el `.gitignore` (`asegurar_ignorados`, el mismo dueño).
    2. Le pide a git los rastreados-ignorados completos.
    3. Los retira del índice con `git rm --cached` — **el árbol de trabajo
       no se toca**: un fichero ignorado no se pierde, deja de
       versionarse.
    4. Deja la reparación en un commit propio con su cifra, para que
       `vault_undo --commits` la muestre como lo que fue.

    Idempotente: en un vault que ya cumple la política devuelve `cero` y
    no escribe nada. La autorización del `rm` en `MUTADORES_AUTORIZADOS`
    es solo para este uso y con `--cached`; un `rm` que toque el árbol
    sigue prohibido (AP-68).
    """
    raiz = Path(raiz)
    if not hay_repo(raiz):
        return {"reparado": False, "destrackeados": [],
                "motivo": "el vault no tiene repositorio git"}

    ignore = asegurar_ignorados(raiz)
    viejos, error_consulta = _rastreados_ignorados(raiz, tope=None)
    if error_consulta:
        # Git no respondió: no se puede afirmar que el índice esté bien.
        # «Cero» aquí sería mentir (AP-51).
        return {"reparado": False, "destrackeados": [],
                "git_no_respondio": True,
                "motivo": error_consulta}
    resultado: Dict[str, Any] = {"reparado": True, "destrackeados": viejos}
    if ignore.get("escrito"):
        resultado["ignore_reparado"] = ignore["anadidos"]
    if not viejos:
        resultado["cero"] = True
        return resultado

    entorno = identidad_de_commit()
    for i in range(0, len(viejos), 400):
        lote = viejos[i:i + 400]
        r = _git(raiz, "rm", "--cached", "-q", "--", *lote, env=entorno)
        if r.returncode != 0:
            return {"reparado": False, "destrackeados": [],
                    "motivo": (r.stderr or "").strip()[:300]
                    or "git rm no pudo"}

    mensaje = (f"reparacion del indice: {len(viejos)} ficheros destrackeados; "
               "el repo del vault versiona lo que la politica no ignora")
    commit = _git(raiz, "commit", "-m", mensaje, env=entorno)
    salida = (commit.stdout or "") + (commit.stderr or "")
    if commit.returncode != 0:
        if "nothing to commit" in salida or "no changes added" in salida:
            resultado["committed"] = False
            return resultado
        return {"reparado": False, "destrackeados": viejos,
                "motivo": salida.strip()[:300] or "git commit no pudo"}
    sha = _git(raiz, "rev-parse", "HEAD")
    resultado["committed"] = True
    resultado["sha"] = (sha.stdout or "").strip()
    resultado["mensaje"] = mensaje
    return resultado


def commit_de_operacion(raiz: Path, mensaje: str) -> Dict[str, Any]:
    """Versiona en git lo que esta operación dejó escrito.

    No es una operación si no cambió nada: sin cambios, `git commit` no tiene
    nada que decir y aquí se declara `unchanged`.

    Devuelve el envelope del commit (`committed`, `sha`, `message`) para que la
    tool pueda publicarlo: una operación sin rastro en `git log` es una
    operación que no pasó.
    """
    raiz = Path(raiz)
    if not hay_repo(raiz):
        return {"committed": False, "motivo": "el vault no tiene repositorio git"}

    ignore = asegurar_ignorados(raiz)
    entorno = identidad_de_commit()
    add = _git(raiz, "add", "-A", env=entorno)
    if add.returncode != 0:
        return {"committed": False,
                "motivo": (add.stderr or "").strip()[:300] or "git add no pudo"}
    commit = _git(raiz, "commit", "-m", mensaje, env=entorno)
    salida = (commit.stdout or "") + (commit.stderr or "")
    if commit.returncode != 0:
        # Sin cambios que commitear es el caso normal de una tool de lectura.
        if "nothing to commit" in salida or "no changes added" in salida:
            return {"committed": False, "unchanged": True,
                    "motivo": "no habia cambios que versionar"}
        return {"committed": False, "motivo": salida.strip()[:300]}
    sha = _git(raiz, "rev-parse", "HEAD")
    resultado: Dict[str, Any] = {
        "committed": True,
        "sha": (sha.stdout or "").strip(),
        "message": mensaje,
    }
    # Aditivo y solo cuando hay algo que decir: un vault sano no cambia su
    # envelope, uno reparado o con deuda vieja la publica.
    if ignore.get("escrito"):
        resultado["ignore_reparado"] = ignore["anadidos"]
    viejos, error_consulta = _rastreados_ignorados(raiz)
    if error_consulta:
        # El índice no se pudo consultar: se dice, en vez de publicar una lista
        # vacía que parece «no hay deuda» (AP-51).
        resultado["indice_no_consultable"] = error_consulta
    elif viejos:
        resultado["rastreados_ignorados"] = viejos
    return resultado


def commits_con_estado(raiz: Path, limite: int = 20) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Las operaciones versionadas y, si git no respondió, el motivo.

    Igual que `_rastreados_ignorados`: una lista vacía puede ser «no hay
    operaciones» o «git no pudo leer el historial». Quien publica esta lista
    —`vault_undo --commits`— tiene que poder distinguirlo (AP-51). Medido el
    2026-11-08: un vault cuyo repo pertenece a otra cuenta respondió «0
    operaciones» con git sin responder.
    """
    if not hay_repo(raiz):
        return [], None
    r = _git(raiz, "log", f"-{max(1, int(limite))}",
             "--format=%H%x1f%an%x1f%aI%x1f%s")
    if r.returncode != 0:
        motivo = (r.stderr or r.stdout or "git log no pudo responder").strip()
        return [], (motivo[:300] or "git log no pudo responder")
    lineas = [l for l in (r.stdout or "").splitlines() if l.strip()]
    operaciones = []
    for linea in lineas:
        partes = linea.split("\x1f")
        if len(partes) < 4:
            continue
        operaciones.append({"sha": partes[0], "autor": partes[1],
                             "fecha": partes[2], "mensaje": partes[3]})
    return operaciones, None


def commits(raiz: Path, limite: int = 20) -> List[Dict[str, Any]]:
    """Las operaciones versionadas, de la más reciente a la más antigua."""
    return commits_con_estado(raiz, limite)[0]


def contenido_del_commit(raiz: Path, sha: str) -> Optional[Dict[str, str]]:
    """El contenido de un commit, LEÍDO: `{ruta relativa: texto}`.

    `git archive` es una lectura (está en `VERBOS_LECTURA`): produce el árbol
    de ese commit sin tocar el repo. Se lee en memoria; quien lo aplique
    (la tool `vault_undo`) lo hace por el write path, con su versión previa.

    El kernel no puede escribir —`atomic_write_text` vive en el contexto de
    scripts— y no tiene por qué: leer y aplicar son dos puertas.
    """
    import io
    import tarfile

    archivo = _git(raiz, "archive", "--format=tar", sha)
    if archivo.returncode != 0 or not archivo.stdout:
        return None
    try:
        crudo = archivo.stdout
        if isinstance(crudo, str):
            crudo = crudo.encode("utf-8", errors="replace")
        with tarfile.open(fileobj=io.BytesIO(crudo), mode="r:") as paquete:
            return {m.name: paquete.extractfile(m).read().decode("utf-8", errors="replace")
                    for m in paquete.getmembers()
                    if m.isfile() and m.name.endswith(".md")}
    except (OSError, ValueError):  # noqa: BLE001 - un tar ilegible no rompe la tool
        return None


def ficheros_del_repo_con_estado(raiz: Path) -> Tuple[Dict[str, List[str]], Optional[str]]:
    """Lo que el repo tiene, y si git pudo decirlo.

    Igual que el resto de verbos de lectura: un índice vacío puede ser un
    repo vacío o un git que no respondió (AP-51).
    """
    versionados_r = _git(raiz, "ls-files")
    if versionados_r.returncode != 0:
        motivo = (versionados_r.stderr or versionados_r.stdout
                  or "git ls-files no pudo responder").strip()
        return ({"versionados": [], "sin_rastrear": []},
                (motivo[:300] or "git ls-files no pudo responder"))
    otros_r = _git(raiz, "ls-files", "--others", "--exclude-standard")
    error = None
    if otros_r.returncode != 0:
        error = ((otros_r.stderr or otros_r.stdout
                  or "git ls-files --others no pudo responder").strip()[:300]
                 or "git ls-files --others no pudo responder")
    return ({"versionados": [l for l in (versionados_r.stdout or "").splitlines() if l.strip()],
             "sin_rastrear": [l for l in (otros_r.stdout or "").splitlines() if l.strip()]},
            error)


def ficheros_del_repo(raiz: Path) -> Dict[str, List[str]]:
    """Lo que el repo tiene: versionados y sin rastrear (lo declarado y lo nuevo)."""
    return ficheros_del_repo_con_estado(raiz)[0]


__all__ = ["IGNORADOS", "IGNORADOS_EN_GIT", "IGNORADOS_POR_RIESGO",
           "IDENTIDAD_LOCAL", "asegurar_ignorados", "hay_repo", "es_hash",
           "commit_de_operacion", "commits", "commits_con_estado",
           "contenido_del_commit", "ficheros_del_repo",
           "ficheros_del_repo_con_estado", "identidad_de_commit",
           "reparar_indice"]
