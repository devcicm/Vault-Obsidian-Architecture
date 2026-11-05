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
from typing import Any, Dict, List, Optional

from vault.kernel import procesos_git
from vault.kernel.procesos_git import es_hash

#: Lo que NO se versiona dentro del vault, por **ruido**: las versiones por
#: nota (`.history/` ya está en el historial de git), las copias de seguridad
#: (`.history/` y `vault-backups/` son el pasado, no el presente) y las trazas,
#: que cambian en cada llamada y ensuciarían el árbol.
IGNORADOS_EN_GIT = (
    ".history/",
    "vault-backups/",
    "00_System/.tool-trace.json",
    "00_System/.mcp-trace-log.json",
    "00_System/.trash/",
    ".locks/",
)

#: Lo que NO se versiona por **riesgo**: la credencial que escribe el servicio
#: de tokens vive dentro del vault (SP-04, para que solo la lea quien puede
#: leer el vault) y un `git add -A` la publicaría. Se separa del ruido porque
#: el día que una tool escriba un secreto nuevo, esta lista es la que hay que
#: mirar — y su test la cruza con el dueño que produce cada ruta.
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


def _rastreados_ignorados(raiz: Path) -> List[str]:
    """Ficheros que el índice sigue versionando pese a estar ignorados.

    `git rm --cached` los sacaría, pero es un verbo mutador que AP-68 no
    autoriza aquí: retirar contenido del índice es una decisión del dueño, no
    un efecto colateral de una operación. Se publican para que la deuda vieja
    sea visible en vez de silenciosa (AP-51).
    """
    r = _git(raiz, "ls-files", "-ci", "--exclude-standard")
    if r.returncode != 0:
        return []
    return [l for l in (r.stdout or "").splitlines() if l.strip()][:5]


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
    viejos = _rastreados_ignorados(raiz)
    if viejos:
        resultado["rastreados_ignorados"] = viejos
    return resultado


def commits(raiz: Path, limite: int = 20) -> List[Dict[str, Any]]:
    """Las operaciones versionadas, de la más reciente a la más antigua."""
    if not hay_repo(raiz):
        return []
    r = _git(raiz, "log", f"-{max(1, int(limite))}",
             "--format=%H%x1f%an%x1f%aI%x1f%s")
    lineas = [l for l in (r.stdout or "").splitlines() if l.strip()]
    operaciones = []
    for linea in lineas:
        partes = linea.split("\x1f")
        if len(partes) < 4:
            continue
        operaciones.append({"sha": partes[0], "autor": partes[1],
                             "fecha": partes[2], "mensaje": partes[3]})
    return operaciones


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


def ficheros_del_repo(raiz: Path) -> Dict[str, List[str]]:
    """Lo que el repo tiene: versionados y sin rastrear (lo declarado y lo nuevo)."""
    versionados = [l for l in (_git(raiz, "ls-files").stdout or "").splitlines() if l.strip()]
    sin_rastrear = [l for l in (_git(raiz, "ls-files", "--others",
                                     "--exclude-standard").stdout or "").splitlines()
                    if l.strip()]
    return {"versionados": versionados, "sin_rastrear": sin_rastrear}


__all__ = ["IGNORADOS", "IGNORADOS_EN_GIT", "IGNORADOS_POR_RIESGO",
           "IDENTIDAD_LOCAL", "asegurar_ignorados", "hay_repo", "es_hash",
           "commit_de_operacion", "commits", "contenido_del_commit",
           "ficheros_del_repo", "identidad_de_commit"]
