#!/usr/bin/env python3
"""vault_changelog_check — el changelog del manifiesto, contrastado contra git.

El changelog vive dentro de `vault-obsidian-architecture.md` y cada entrada
publica el hash del commit que introdujo la versión:

    ### v40.6 — 2026-08-08 `git: bf8ba6d`

Ese hash y esa fecha se escribían a mano. Nada los contrastaba con git, que es
donde el dato existe de verdad, así que el changelog podía —y podía en cinco
entradas— afirmar una fecha que su propio commit desmiente. Cuatro eran de un
día. La quinta, v39.0, de once: el changelog decía 2026-07-25 y el commit que
cita es de 2026-08-05. Esa entrada arrastra además un commit de fijado que
corrigió el hash (`13bf9ca -> 00731c6`) sin tocar la fecha; sea cual sea el
motivo del cambio de hash, la fecha se quedó atrás y nada podía notarlo. Un dato
con dos fuentes donde solo una se mantiene es AP-05; escrito a mano en
documentación, AP-47. Este guard cierra las dos.

Y cierra también el huevo y la gallina que lo originó. La entrada tiene que
citar el hash del commit que la contiene, y ese hash no existe hasta que el
commit está hecho. La salida fue un ritual de dos commits:

    feat: v40.6 — …                              (changelog con `git: pending`)
    docs: fijar hash del changelog v40.6 (git: pending -> bf8ba6d)

Ocho veces en las últimas veinte entradas del historial, y con dos costes que
nadie había escrito: el segundo commit depende de acordarse —si se olvida, el
`pending` queda publicado y el único guard que existía no lo cazaba hasta la
versión SIGUIENTE—, y el hash publicado apunta a un commit que **no contiene** la
entrada que lo cita, así que el comando que el propio changelog recomienda para
navegar (`git show <hash> -- vault-obsidian-architecture.md`) enseña el manifiesto
sin ella. `--fijar-hash` convierte ese ritual en un comando.

Uso:

    python scripts/vault_changelog_check.py --check --strict   # la puerta
    python scripts/vault_changelog_check.py --list             # tabla de entradas
    python scripts/vault_changelog_check.py --fijar-hash       # cierra la versión
    python scripts/vault_changelog_check.py --freeze           # baseline de fechas

Las cinco divergencias **se corrigieron**, no se anotaron: el preámbulo del
changelog ya permite explícitamente corregir errores factuales —«hashes, rutas,
conteos»— y una fecha equivocada es exactamente eso. La no-derogación prohíbe
reescribir la historia, no prohíbe que la historia diga la verdad.

Queda aun así una **baseline que solo puede encoger** (`--freeze`), por el mismo
motivo que la tienen AP-37, AP-51 y AP-52: el día que aparezca una divergencia
que no se pueda corregir —una entrada cuyo commit ya no exista tras un filtrado
del historial, por ejemplo— la puerta tiene que poder quedarse en verde
anotándola, en vez de vivir en rojo hasta que alguien la desactive. Hoy la
baseline está vacía, que es donde debe estar.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

from vault_errors import emit_error, wrap_main

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC = REPO_ROOT / "vault-obsidian-architecture.md"
BASELINE = REPO_ROOT / "scripts" / "changelog-baseline.json"

#: `### v40.6 — 2026-08-08 `git: bf8ba6d``
#: El separador es una raya larga, no un guion: escribirlo como `-` hace que el
#: guard no vea ninguna entrada y salga verde por no mirar, que es AP-44.
RE_ENTRADA = re.compile(
    r"^### (v[\d.]+) — (\d{4}-\d{2}-\d{2}) `git: ([^`]+)`", re.MULTILINE
)

#: Hashes que no son hashes. `—` es el histórico anterior a git; `pending`, la
#: versión en curso, cuyo commit todavía no existe.
NO_HASH = ("—", "-", "pending")


# ─────────────────────────────────────────────────────────────────────────────
# Lectura
# ─────────────────────────────────────────────────────────────────────────────


def _changelog(texto: Optional[str] = None) -> str:
    """El cuerpo del changelog, sin el resto del manifiesto."""
    texto = texto if texto is not None else SPEC.read_text(encoding="utf-8")
    marca = "\n## Changelog"
    if marca not in texto:
        return ""
    return texto[texto.index(marca):]


def entradas(texto: Optional[str] = None) -> List[Dict[str, str]]:
    """Todas las entradas del changelog, en el orden en que aparecen."""
    return [
        {"version": v, "fecha": f, "hash": h}
        for v, f, h in RE_ENTRADA.findall(_changelog(texto))
    ]


def _git(*args: str) -> Optional[str]:
    """Ejecuta git y devuelve stdout, o None si el comando falla.

    Devolver None y no cadena vacía es deliberado (AP-51): «git no pudo
    responder» y «git respondió vacío» son cosas distintas, y quien llama
    decide. Un `except` que las fundiera haría pasar el fallo del guard por
    ausencia en el dato.
    """
    try:
        r = subprocess.run(
            ["git", *args], cwd=str(REPO_ROOT),
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip()


#: Se usa la fecha de AUTORÍA (`%as`), no la de commit (`%cs`). Un rebase
#: reescribe la segunda y conserva la primera, así que `%cs` haría que reordenar
#: el historial estrenara divergencias falsas. En las cinco entradas que este
#: guard destapó las dos coinciden —el desfase no venía de un rebase, las fechas
#: estaban mal escritas— pero el criterio se elige por lo que aguanta, no por lo
#: que da igual hoy.


def hay_git() -> bool:
    return _git("rev-parse", "--git-dir") is not None


# ─────────────────────────────────────────────────────────────────────────────
# Baseline de fechas ya divergentes
# ─────────────────────────────────────────────────────────────────────────────


def _cargar_baseline() -> Dict[str, str]:
    if not BASELINE.exists():
        return {}
    try:
        datos = json.loads(BASELINE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return datos.get("fechas_divergentes", {})


# ─────────────────────────────────────────────────────────────────────────────
# La comprobación
# ─────────────────────────────────────────────────────────────────────────────


def comprobar(version_en_curso: Optional[str] = None) -> Dict[str, Any]:
    """Contrasta cada entrada con hash real contra el commit que cita.

    **AP-53** entera vive aquí: la documentación afirma un hecho del historial
    —qué commit introdujo una versión y en qué fecha— y ese hecho existe de
    verdad en git. Detectar es preguntárselo a git; aplicar es `--fijar-hash`,
    que sustituye el `git: pending` por el hash real en vez de dejar que se
    escriba a mano. La fecha se toma de la **autoría**, no del commit: un
    rebase reescribe la segunda y desincronizaría la afirmación sin que nadie
    hubiera tocado el changelog.
    """
    todas = entradas()
    if not todas:
        return emit_error(
            "vault_changelog_check", "PARSE_FAILED",
            "No se reconoció ninguna entrada de changelog en el manifiesto",
        )

    if version_en_curso is None:
        try:
            from vault_standard_upgrade import CURRENT_VERSION
            version_en_curso = CURRENT_VERSION
        except ImportError:
            version_en_curso = None

    baseline = _cargar_baseline()
    problemas: List[Dict[str, str]] = []
    saldadas: List[str] = []
    con_hash = [e for e in todas if e["hash"] not in NO_HASH]
    pendientes = [e["version"] for e in todas if e["hash"] == "pending"]

    # (a) `pending` de una versión ya cerrada. El guard viejo vivía suelto en la
    #     suite y solo miraba esto; aquí es una comprobación más de la puerta.
    for v in pendientes:
        if v != version_en_curso:
            problemas.append({
                "version": v,
                "problema": "hash_sin_fijar",
                "detalle": (
                    f"{v} no es la versión en curso ({version_en_curso}) y "
                    "sigue publicando `git: pending`"
                ),
            })

    # (b) Orden cronológico. Una entrada intercalada ya pasó una vez.
    numeros = [
        tuple(int(p) for p in (e["version"].lstrip("v").split(".") + ["0"])[:2])
        for e in todas
    ]
    if numeros != sorted(numeros, reverse=True):
        problemas.append({
            "version": "—",
            "problema": "fuera_de_orden",
            "detalle": "las entradas no están en orden decreciente de versión",
        })

    git_disponible = hay_git()
    for e in con_hash:
        if not git_disponible:
            break
        # (c) El hash existe y es un commit.
        tipo = _git("cat-file", "-t", e["hash"])
        if tipo != "commit":
            problemas.append({
                "version": e["version"],
                "problema": "hash_inexistente",
                "detalle": (
                    f"`{e['hash']}` no es un commit de este repositorio"
                    + ("" if tipo is None else f" (git dice: {tipo})")
                ),
            })
            continue
        # (d) La fecha coincide con la del commit citado.
        fecha_commit = _git("show", "-s", "--format=%as", e["hash"])
        if fecha_commit and fecha_commit != e["fecha"]:
            detalle = (
                f"el changelog dice {e['fecha']} y el commit `{e['hash']}` "
                f"es de {fecha_commit}"
            )
            if baseline.get(e["version"]) == fecha_commit:
                continue  # divergencia conocida, ya anotada
            problemas.append({
                "version": e["version"],
                "problema": "fecha_divergente",
                "detalle": detalle,
            })

    # La baseline solo puede encoger: una entrada anotada que ya no diverge se
    # reporta como saldada, para que `--freeze` la saque.
    if git_disponible:
        vivas = {e["version"]: e for e in con_hash}
        for version, fecha_commit in baseline.items():
            e = vivas.get(version)
            if e is None or _git("show", "-s", "--format=%as", e["hash"]) == e["fecha"]:
                saldadas.append(version)

    return {
        "ok": not problemas,
        "tool": "vault_changelog_check",
        "entries_total": len(todas),
        "entries_with_hash": len(con_hash),
        "current_version": version_en_curso,
        "pending": pendientes,
        "git_available": git_disponible,
        "baseline_size": len(baseline),
        "problems": problemas,
        "settled": saldadas,
        "hint": (
            "python scripts/vault_changelog_check.py --fijar-hash  (cierra la "
            "versión en curso)  |  --freeze  (anota una divergencia histórica)"
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Fijar el hash — el segundo commit del ritual, hecho por la tool
# ─────────────────────────────────────────────────────────────────────────────


def fijar_hash(hash_objetivo: Optional[str] = None,
               dry_run: bool = False) -> Dict[str, Any]:
    """Sustituye el `pending` de la versión en curso por un hash real.

    Por defecto usa `HEAD`, que es el commit que acaba de introducir la versión.
    No hace el commit: deja el manifiesto escrito y dice qué commitear. Que una
    tool de gobernanza commitee por su cuenta convertiría un guard en una
    escritura sobre el historial, y eso no se decide desde aquí.
    """
    if not hay_git():
        return emit_error(
            "vault_changelog_check", "GIT_UNAVAILABLE",
            "No hay repositorio git: no se puede resolver ningún hash",
        )
    try:
        from vault_standard_upgrade import CURRENT_VERSION
    except ImportError:
        return emit_error(
            "vault_changelog_check", "REGISTRY_UNAVAILABLE",
            "No se pudo leer CURRENT_VERSION de vault_standard_upgrade",
        )

    objetivo = hash_objetivo or _git("rev-parse", "--short", "HEAD")
    if not objetivo:
        return emit_error(
            "vault_changelog_check", "GIT_UNAVAILABLE",
            "git no devolvió el hash de HEAD",
        )
    if _git("cat-file", "-t", objetivo) != "commit":
        return emit_error(
            "vault_changelog_check", "INVALID_INPUT",
            f"`{objetivo}` no es un commit de este repositorio",
        )

    texto = SPEC.read_text(encoding="utf-8")
    fecha_commit = _git("show", "-s", "--format=%as", objetivo)
    viejo = re.compile(
        r"^(### " + re.escape(CURRENT_VERSION) + r" — )(\d{4}-\d{2}-\d{2})"
        r"( `git: )pending(`)",
        re.MULTILINE,
    )
    encontrado = viejo.search(texto)
    if not encontrado:
        return {
            "ok": False,
            "tool": "vault_changelog_check",
            "error_code": "NOTHING_TO_FIX",
            "error": (
                f"No hay una entrada `### {CURRENT_VERSION} — … `git: pending`` "
                "en el changelog"
            ),
            "recovery": (
                "Escribe primero la entrada de la versión con `git: pending`, "
                "o comprueba que CURRENT_VERSION es la que crees"
            ),
        }

    fecha_vieja = encontrado.group(2)
    # La fecha se toma del commit, no se conserva la escrita a mano: es
    # exactamente el dato que se desincronizó en v39.0.
    nuevo_texto = viejo.sub(
        lambda m: m.group(1) + (fecha_commit or fecha_vieja) + m.group(3)
        + objetivo + m.group(4),
        texto, count=1,
    )
    cambios = {
        "version": CURRENT_VERSION,
        "hash": objetivo,
        "date_before": fecha_vieja,
        "date_after": fecha_commit or fecha_vieja,
        "date_corrected": bool(fecha_commit and fecha_commit != fecha_vieja),
    }
    if not dry_run:
        SPEC.write_text(nuevo_texto, encoding="utf-8")
    return {
        "ok": True,
        "tool": "vault_changelog_check",
        "dry_run": dry_run,
        "fixed": 1,
        "changes": cambios,
        "commit_message": (
            f"docs: fijar hash del changelog {CURRENT_VERSION} "
            f"(git: pending -> {objetivo})"
        ),
        "hint": "Revisa el diff del manifiesto y haz el commit de documentación.",
    }


def congelar() -> Dict[str, Any]:
    """Anota las divergencias de fecha vivas. La baseline solo puede encoger."""
    if not hay_git():
        return emit_error(
            "vault_changelog_check", "GIT_UNAVAILABLE",
            "No hay repositorio git: no se puede construir la baseline",
        )
    previa = _cargar_baseline()
    nueva: Dict[str, str] = {}
    for e in entradas():
        if e["hash"] in NO_HASH:
            continue
        if _git("cat-file", "-t", e["hash"]) != "commit":
            continue
        fecha_commit = _git("show", "-s", "--format=%as", e["hash"])
        if fecha_commit and fecha_commit != e["fecha"]:
            nueva[e["version"]] = fecha_commit

    estrenadas = sorted(set(nueva) - set(previa))
    if estrenadas:
        return {
            "ok": False,
            "tool": "vault_changelog_check",
            "error_code": "DEBT_WOULD_GROW",
            "error": (
                "Congelar ahora aumentaría la deuda: hay entradas con la fecha "
                f"recién divergente: {estrenadas}"
            ),
            "recovery": (
                "Corrige la fecha de esas entradas contra su commit; la baseline "
                "es para historia que ya estaba mal, no para estrenar deuda"
            ),
        }
    BASELINE.write_text(
        json.dumps(
            {
                "_comment": (
                    "Entradas del changelog cuya fecha no coincide con la del "
                    "commit que citan. Historia, no permiso: la lista solo "
                    "puede encoger. version -> fecha real del commit."
                ),
                "fechas_divergentes": dict(sorted(nueva.items())),
            },
            indent=2, ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )
    return {
        "ok": True,
        "tool": "vault_changelog_check",
        "frozen": len(nueva),
        "settled": sorted(set(previa) - set(nueva)),
        "entries": dict(sorted(nueva.items())),
    }


def listar() -> Dict[str, Any]:
    todas = entradas()
    filas = []
    disponible = hay_git()
    for e in todas:
        fila = dict(e)
        if disponible and e["hash"] not in NO_HASH:
            fila["commit_date"] = _git("show", "-s", "--format=%as", e["hash"])
            fila["exists"] = _git("cat-file", "-t", e["hash"]) == "commit"
        filas.append(fila)
    return {
        "ok": True,
        "tool": "vault_changelog_check",
        "entries_total": len(todas),
        "entries": filas,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--check", action="store_true",
                   help="contrasta el changelog contra git")
    p.add_argument("--strict", action="store_true",
                   help="con --check, sale 1 si hay problemas")
    p.add_argument("--list", action="store_true", dest="listar",
                   help="tabla de entradas con su commit")
    p.add_argument("--fijar-hash", action="store_true", dest="fijar",
                   help="sustituye el `pending` de la versión en curso")
    p.add_argument("--hash", default=None,
                   help="con --fijar-hash, el commit a citar (por defecto HEAD)")
    p.add_argument("--dry-run", action="store_true",
                   help="con --fijar-hash, no escribe el manifiesto")
    p.add_argument("--freeze", action="store_true",
                   help="anota las divergencias de fecha vivas")
    args = p.parse_args()

    if args.fijar:
        r = fijar_hash(args.hash, dry_run=args.dry_run)
    elif args.freeze:
        r = congelar()
    elif args.listar:
        r = listar()
    else:
        r = comprobar()

    print(json.dumps(r, indent=2, ensure_ascii=False))
    if args.strict and not r.get("ok"):
        return 1
    return 0 if r.get("ok") else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_changelog_check"))
