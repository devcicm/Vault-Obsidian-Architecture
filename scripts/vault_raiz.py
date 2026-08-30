#!/usr/bin/env python3
"""vault_raiz — dónde está el vault. Módulo hoja, y esa es toda su razón de ser.

Aquí vive el estado de «cuál es el vault activo»: la autodetección, el override
de `set_vault_root()` y el reanclaje de las constantes que otros módulos
derivaron de la raíz anterior. Nada más.

**Por qué existe (v40.17).** Este código estaba dentro de `vault_io`, que además
sabe de saneado de codificación, escaneo de secretos, ledger de escrituras,
índices de sección y wikilinks. Medido sobre el grafo de imports, eso ponía a
`vault_io` dentro de un componente fuertemente conexo de 15 módulos —el núcleo
entero era un nudo mutuamente recursivo— y el nudo se sostenía con 92 imports
diferidos dentro de funciones: un rompe-ciclos aplicado a mano, módulo a módulo.

La inversión que lo deshace es la de siempre: quien está abajo no puede depender
de quien está arriba. `vault_errors_trace` necesita saber *dónde escribir*, y
para eso pedía el módulo entero de IO, que a su vez necesita emitir errores, que
necesita trazarlos. Extraído el dato a una hoja, la arista desaparece en vez de
esquivarse.

**Este módulo no importa ningún `vault_*` salvo `vault_entorno`** (el registro de
variables de entorno, hoja también). Si alguna vez necesita importar otro, el
corte se ha perdido y `vault_ciclos` lo dirá.

Compatibilidad: `vault_io` reexporta todo lo público de aquí, así que los ~89
módulos que hacen `from vault_io import VAULT_ROOT, get_vault_root` siguen
funcionando sin tocarse (no-derogación).
"""

from pathlib import Path
from typing import List, Optional

from vault_entorno import leer as _env


#: Origen de la detección del vault root — lo fija _detect_vault_root() y lo
#: consulta el guard AP-36. `repo_root_fallback` es el único valor de baja
#: confianza: significa que NO se encontró ningún vault y se está usando la raíz
#: del repo como si lo fuera (v39: causa histórica de 00_System/ y 99_Index/
#: generados fuera de todo vault-*).
_VAULT_ROOT_ORIGIN: str = "unknown"

#: Valores de _VAULT_ROOT_ORIGIN que NO identifican un vault real.
LOW_CONFIDENCE_ORIGINS = frozenset({"repo_root_fallback"})


def _detect_vault_root() -> Path:
    """Auto-detect vault root.

    Priority order:
    1. VAULT_ROOT env var (explicit override)
    2. vault-* subdirectory beside scripts/ (consumer repo layout):
       - First pass: prefer dirs that already have 00_System/, 99_Index/ or .obsidian
       - Second pass: accept any vault-* dir (fresh install, nothing initialized yet)
       vault-backups* AND vault-sandbox* dirs are excluded from both passes
       (vault-sandbox is a side-effect of the spec-repo fallback, not a real vault).
    3. scripts/ parent (scripts-inside-vault layout) IF it has vault structure
       (00_System/01_Projects/etc. directly under it). Previously this fallback
       only triggered when the parent had vault-obsidian-architecture.md, which
       caused a bug: any consumer vault that included the spec as a reference
       doc got misidentified as the spec repo and redirected to vault-sandbox/.
    4. Spec-repo sandbox: if the parent has vault-obsidian-architecture.md
       AND no vault structure markers, treat as spec repo and use vault-sandbox/.
    5. Último recurso: la raíz del repo. Marcada como `repo_root_fallback` —
       ver `vault_root_origin()`. Con VAULT_STRICT_ROOT=1 esto es un error en
       lugar de un silencio, porque es el caso en el que las tools escriben
       artefactos de vault fuera de cualquier vault.

    AP-36: esta función NO crea directorios. Antes hacía `sandbox.mkdir()` en
    la rama 4, y como VAULT_ROOT se evalúa a nivel de módulo, *importar*
    vault_io materializaba `vault-sandbox/` en cualquier repo que tuviera el
    manifiesto como doc de referencia. Los directorios se crean ahora en la
    primera escritura real (atomic_write_* ya hace mkdir del padre).

    El ancla es `Path(__file__).parent.parent`: este módulo vive en `scripts/`,
    igual que `vault_io` cuando la función estaba allí, así que la raíz que
    devuelve no cambia por haberse mudado de fichero.
    """
    global _VAULT_ROOT_ORIGIN
    if env := _env("VAULT_ROOT"):
        _VAULT_ROOT_ORIGIN = "env"
        return Path(env).resolve()
    project_root = Path(__file__).parent.parent.resolve()
    _MARKERS = {"00_System", "99_Index", ".obsidian"}
    # Strong vault structure marker — at least 2 of these folders must exist
    # at the root level for the directory to be considered a vault.
    _VAULT_MARKERS = {
        "00_System",
        "01_Projects",
        "02_Observability",
        "03_Decisions",
        "99_Index",
        ".obsidian",
    }
    # Exclude vault-sandbox and *.bak from candidates — they're side-effects
    # of the spec-repo fallback or backups, not real vaults. Excluding them
    # prevents a chicken-and-egg situation where the old detection created
    # vault-sandbox/ and the new detection picks it as the vault because it
    # has 00_System.
    candidates = [
        s
        for s in sorted(project_root.iterdir())
        if s.is_dir()
        and (s.name.startswith("vault-") or s.name == "vault")
        and not s.name.startswith("vault-backups")
        and s.name != "vault-sandbox"
        and not s.name.endswith(".bak")
        # Un paquete Python no es un vault, aunque se llame `vault/`. La rama
        # "fresh" de abajo acepta un candidato por el NOMBRE, sin exigir un solo
        # marcador, así que crear el paquete `vault/` del refactor bastó para
        # que la autodetección dejara de devolver `vault-sandbox/` y empezara a
        # apuntar al código fuente — con origen `sibling_vault_dir_fresh`, es
        # decir, anunciando confianza. Es AP-44 en el detector: se validaba a sí
        # mismo por convención de nombre en vez de por el criterio del
        # consumidor, que es «¿tiene esto contenido de vault?».
        and not (s / "__init__.py").exists()
    ]
    # Prefer candidates that already have vault content (initialized vault).
    # Con varios candidatos初始化ados se selecciona el de mayor madurez:
    # el que más marcadores de estructura tenga. A igualdad, el primero
    # alfabéticamente (candidates ya está sorted).
    best_candidate: Optional[Path] = None
    best_score = 0
    for c in candidates:
        score = sum(1 for m in _MARKERS if (c / m).exists())
        if score > best_score:
            best_score = score
            best_candidate = c
    if best_candidate is not None:
        _VAULT_ROOT_ORIGIN = "sibling_vault_dir"
        return best_candidate
    # Accept any vault-* dir (fresh vault, nothing initialized yet)
    if candidates:
        _VAULT_ROOT_ORIGIN = "sibling_vault_dir_fresh"
        return candidates[0]
    # Check if project_root itself IS a vault (scripts-inside-vault layout).
    # This is the case when the consumer has 00_System/01_Projects/etc. directly
    # under the same dir that contains scripts/ — common when a project ships
    # the spec file as a reference doc and the vault sits at the same level.
    marker_count = sum(1 for m in _VAULT_MARKERS if (project_root / m).exists())
    # 00_System/ and 99_Index/ are auto-created by the observability layer
    # (tool-trace, graph index) as a side-effect of running any tool, so their
    # presence alone must NOT qualify project_root as a vault — that creates a
    # self-reinforcing loop where one stray write makes the repo root the vault
    # forever. Require at least one CONTENT marker authored by a human/init.
    _CONTENT_MARKERS = {"01_Projects", "02_Observability", "03_Decisions", ".obsidian"}
    has_content = any((project_root / m).exists() for m in _CONTENT_MARKERS)
    if marker_count >= 2 and has_content:
        _VAULT_ROOT_ORIGIN = "scripts_inside_vault"
        return project_root
    # Spec repo fallback: parent has vault-obsidian-architecture.md AND no
    # vault structure (i.e., this IS the spec repo, not a consumer vault).
    # NO se crea el directorio aquí — ver docstring (AP-36).
    if (project_root / "vault-obsidian-architecture.md").exists():
        _VAULT_ROOT_ORIGIN = "spec_repo_sandbox"
        return project_root / "vault-sandbox"
    # Último recurso: no hay vault. Devolvemos la raíz del repo para no romper
    # los ~94 tools que no aceptan --root, pero queda marcado como baja
    # confianza para que el guard AP-36 lo denuncie en vez de silenciarlo.
    _VAULT_ROOT_ORIGIN = "repo_root_fallback"
    if _env("VAULT_STRICT_ROOT"):
        raise RuntimeError(
            f"No se encontró ningún vault desde {project_root}. Con VAULT_STRICT_ROOT=1 "
            "esto es un error: escribir aquí generaría 00_System/, 99_Index/ y demás "
            "artefactos fuera de todo vault. Crea un directorio 'vault-<nombre>/' o "
            "exporta VAULT_ROOT=<ruta del vault>."
        )
    return project_root


VAULT_ROOT: Path = _detect_vault_root()

#: El vault detectado al importar, guardado APARTE y nunca reescrito.
#:
#: `set_vault_root()` reancla las constantes de módulo derivadas del vault, y
#: `VAULT_ROOT` es una de ellas: se reapunta a sí misma. Sin esta copia, poner
#: el override a None no volvía al vault detectado —se quedaba en el último
#: destino para siempre— mientras `vault_root_origin()` seguía respondiendo
#: `spec_repo_sandbox`, es decir, anunciando confianza sobre una raíz que ya no
#: era ésa. Es AP-44 en el propio detector: certificaba con su criterio en vez
#: de con el del consumidor.
#: Se guarda como `str` y no como `Path` a propósito: `_reanclar_constantes()`
#: reapunta toda constante en mayúsculas cuyo valor sea un `Path` derivado del
#: vault, y esta copia lo es. Guardada como ruta, el reanclaje se la llevaba por
#: delante y el respaldo apuntaba al mismo sitio del que había que volver.
_VAULT_ROOT_DETECTADO: str = str(VAULT_ROOT)
_ORIGEN_DETECTADO: str = _VAULT_ROOT_ORIGIN


def vault_root_origin() -> str:
    """Qué regla de _detect_vault_root() eligió VAULT_ROOT.

    Valores: env | sibling_vault_dir | sibling_vault_dir_fresh |
    scripts_inside_vault | spec_repo_sandbox | repo_root_fallback |
    explicit_override.

    Con un override activo devuelve `explicit_override`: la raíz ya no la
    eligió ninguna regla de detección, y seguir citando la regla anterior sería
    atribuir a la autodetección una decisión que tomó quien llamó.
    """
    if _ACTIVE_VAULT_ROOT is not None:
        return "explicit_override"
    return _VAULT_ROOT_ORIGIN


def vault_root_is_confident() -> bool:
    """False cuando VAULT_ROOT es una suposición, no un vault identificado."""
    return _VAULT_ROOT_ORIGIN not in LOW_CONFIDENCE_ORIGINS


# ── Override en runtime (AP-36) ────────────────────────────────────────────────
# Los tools que aceptan --root deben llamar set_vault_root() ANTES de escribir,
# para que la capa de observabilidad (traces, tokens, locks) escriba en el vault
# objetivo y no en el VAULT_ROOT detectado en import. Los writers deben resolver
# la ruta vía get_vault_root() en tiempo de llamada, nunca como constante de módulo.
_ACTIVE_VAULT_ROOT: Optional[Path] = None


def _reanclar_constantes(anterior: Path, nueva: Path) -> List[str]:
    """Reapunta al vault nuevo las constantes de módulo derivadas del viejo.

    El problema que resuelve: 89 de 98 módulos hacen `from vault_io import
    VAULT_ROOT` y derivan sus rutas EN EL IMPORT (`CODE_DIR = VAULT_ROOT /
    "11_Code"`). Eso congela un `Path` literal, así que `set_vault_root()`
    cambiaba `get_vault_root()` y no cambiaba nada de lo que las tools usan de
    verdad para leer y escribir. Había dos verdades para "cuál es el vault", y
    la API pública de cambiarlo mentía: medido, `get_vault_root()` devolvía el
    vault nuevo mientras `vault_audit.VAULT_ROOT` seguía en el viejo.

    Reanclar es lo único que arregla el caso sin reescribir los 89 módulos:
    ningún proxy perezoso sobre `VAULT_ROOT` alcanzaría a las constantes ya
    derivadas de él. Se toca solo lo inequívoco —nombres en MAYÚSCULAS de
    módulos `vault_*` cuyo valor es un `Path` DENTRO de la raíz anterior—;
    cualquier otra cosa se deja como está.

    Devuelve los nombres reanclados, en `modulo.CONSTANTE`, para que la
    operación sea auditable en vez de mágica.

    Vive en la hoja y no en `vault_io` porque no necesita nada de IO: recorre
    `sys.modules` y reescribe atributos. Que pareciera código de IO es lo que lo
    mantuvo dentro del módulo-dios.
    """
    import sys as _sys

    tocados: List[str] = []
    for nombre_mod, modulo in list(_sys.modules.items()):
        if not nombre_mod.startswith("vault_") or modulo is None:
            continue
        for nombre, valor in list(vars(modulo).items()):
            if not nombre.isupper() or not isinstance(valor, Path):
                continue
            if nombre == "VAULT_ROOT":
                setattr(modulo, nombre, nueva)
                tocados.append(f"{nombre_mod}.{nombre}")
                continue
            try:
                relativa = valor.relative_to(anterior)
            except ValueError:
                continue  # no colgaba del vault: no es una ruta de vault
            setattr(modulo, nombre, nueva / relativa)
            tocados.append(f"{nombre_mod}.{nombre}")
    return tocados


#: Constantes reancladas por el último set_vault_root(). Auditable desde fuera.
_REANCLADAS: List[str] = []


def set_vault_root(path) -> Path:
    """Fija el vault activo para esta ejecución (override de la auto-detección).

    Además de fijar el override, reancla las constantes que los módulos ya
    importados derivaron del vault anterior — ver `_reanclar_constantes()`.
    """
    global _ACTIVE_VAULT_ROOT, _REANCLADAS
    anterior = get_vault_root().resolve()
    nueva = Path(path).resolve()
    _ACTIVE_VAULT_ROOT = nueva
    _REANCLADAS = _reanclar_constantes(anterior, nueva) if nueva != anterior else []
    return _ACTIVE_VAULT_ROOT


def rebound_constants() -> List[str]:
    """Constantes de módulo que el último set_vault_root() reapuntó."""
    return list(_REANCLADAS)


def reset_vault_root() -> Path:
    """Deshace el override y devuelve las constantes al vault detectado.

    Poner `_ACTIVE_VAULT_ROOT = None` a mano NO basta y ésa era la trampa: el
    reanclaje ya había reescrito `VAULT_ROOT` y las constantes de los módulos
    cargados, así que el proceso seguía apuntando al destino temporal. En una
    suite eso se ve como fallos que dependen del orden de los ficheros; en una
    tool, como escribir en el vault de la llamada anterior.
    """
    global _ACTIVE_VAULT_ROOT
    set_vault_root(Path(_VAULT_ROOT_DETECTADO))
    _ACTIVE_VAULT_ROOT = None
    return VAULT_ROOT


def get_vault_root() -> Path:
    """Vault root efectivo: el override de set_vault_root() o el auto-detectado."""
    return _ACTIVE_VAULT_ROOT if _ACTIVE_VAULT_ROOT is not None else VAULT_ROOT
