#!/usr/bin/env python3
"""
Vault Section Index — Generate {folder}/index.md for a vault section.

Scans all notes in a section folder and writes a human-readable index.md.
This is a derived artifact — it is auto-regenerated and must never be edited manually.
vault_write calls this automatically after each successful write.

Usage:
    python vault_section_index.py --folder 01_Projects
    python vault_section_index.py --folder 01_Projects --no-subdirs
"""

import argparse
import json
import sys
from vault_errors import emit_error, wrap_main
from vault_lib import (
    destino_mas_corto,
    indice_de_nombres,
    inventario_de_nombres,
    parse_frontmatter,
    utcnow,
)
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_io import (
    assert_within_vault,
    escritura_atomica,
    file_lock,
    get_vault_root,
    record_raw_write,
    refrescar_grafo,
    is_snapshot_path,
    safe_wikilink,
    write_report,
)
from vault_registry import (
    MACHINERY_FOLDERS,
    ORDERED_SECTIONS,
    section_description,
    comando_de_tool,
    secciones_del_vault,
    section_tool_hint,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vault.indices.seccion import (  # noqa: E402
    RE_ALIAS_EN_TABLA,
    RenderizadorDeIndice,
    es_indice_generado,
    indice_de_la_carpeta,
    migaja,
    recolectar_notas,
)
from vault.indices.reconstruccion import ServicioReindex  # noqa: E402
from vault.indices.repositorio import RepositorioIndices  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.kernel.frontmatter_escritura import Frontmatter  # noqa: E402


# AP-36: paths lazy — respetan set_vault_root() en runtime (--root).
def _hub_note() -> Path:
    return get_vault_root() / "00_System" / "vault-hub.md"


def _commands_note() -> Path:
    return get_vault_root() / "00_System" / "vault-commands.md"


def _escribir_hub(destino: Path, contenido: str) -> None:
    """Las dos notas hub por el mismo camino que los índices.

    Se escribían con un `write_text` pelado: sin `assert_within_vault`, sin
    lock, y —lo que más pesa— sin `record_raw_write`, que es donde vive el
    escaneo de secretos y el ledger que hace falsable el `ok: true` (AP-37).
    Son las dos únicas notas que el estándar escribe en todo vault que crea,
    así que eran justo las que no podían ir por la puerta de atrás.
    """
    vroot = get_vault_root()
    assert_within_vault(destino, vroot)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(destino):
        record_raw_write(destino, contenido)
        escritura_atomica(destino, contenido)
    # AP-47: el grafo las cuenta como nodos y se escriben fuera del gancho de
    # `atomic_write_text`; sin esto el grafo refrescado no las ve hasta la
    # siguiente reconstrucción. Fuera del lock: el refresco toma el suyo.
    refrescar_grafo(destino)


def _bloque_de_navegacion(titulo: str, id_: str, etiqueta: str) -> str:
    """El frontmatter de las dos notas de navegación, que solo difieren en
    título, id y su segunda etiqueta."""
    return (
        Frontmatter()
        .set("title", titulo, texto=True)
        .set("id", id_)
        .set("createdAt", utcnow())
        .set("updatedAt", utcnow())
        .set("cia_integrity", "high")
        .set("cia_availability", "high")
        .set("cia_sensitivity", "internal")
        .set("agent", "system")
        .set("tags", ["nav", etiqueta])
        .set("norm_refs", ["CN-01"])
        .render()
    )


def _ensure_hub_notes(indice_disponible=None) -> None:
    """Idempotently create 00_System/vault-hub.md and vault-commands.md.

    The hub note is the single authoritative entry point — it links to every
    section index using stems Obsidian can resolve. The commands note is the
    single authoritative reference for execution commands — no command should
    appear inline in any other auto-generated file.

    Both are user-editable: if the file already exists we leave it alone.
    This protects manual edits while still bootstrapping a fresh vault.

    `indice_disponible(ruta)` dice qué índices existen o se escriben en la
    misma ejecución: esos se enlazan, el resto se nombra en código. Hasta
    v40.35 el hub nombraba todos en código y ninguno se podía pulsar — el
    punto único de navegación no navegaba a ninguna sección.
    """
    def enlace_a_indice(ruta: str, texto: str) -> Optional[str]:
        if indice_disponible is not None and indice_disponible(ruta):
            return f"[[{ruta[:-3]}|{texto}]]"
        return None

    if not _hub_note().exists():
        # AP-46: el bloque lo escribe su dueño; aquí solo se declaran los campos.
        hub_content = _bloque_de_navegacion("Vault Hub", "vault-hub", "hub") + (
            "\n"
            "\n"
            "# Vault Hub — Punto único de navegación\n"
            "\n"
            "> Esta nota es el **único hub** del vault. Todos los índices de sección "
            "y el índice maestro apuntan aquí. Si acabas de llegar al vault, lee primero esto.\n"
            "\n"
            "## Navegación principal\n"
            "\n"
            "- [[vault-commands|Comandos del vault]] — referencia unificada de comandos CLI\n"
            f"- {enlace_a_indice('99_Index/index.md', 'Índice maestro') or '`99_Index/index.md` (Índice Maestro)'}"
            " — tabla resumen con conteo de notas por sección\n"
            "\n"
            "## Secciones\n"
            "\n"
            "| Sección | Descripción | Índice |\n"
            "|---|---|---|\n"
        )
        # La tabla del hub listaba 18 secciones escritas a mano: las cuatro
        # más nuevas existían en disco y no aparecían en el índice principal,
        # que es la única página por la que se navega el vault. Se deriva.
        # Con las propias que ya estén declaradas cuando nace el hub.
        for section in secciones_del_vault(get_vault_root()):
            desc = section_description(section, get_vault_root())
            enlace = enlace_a_indice(f"{section}/index.md", "índice") or f"`{section}/index.md`"
            hub_content += f"| `{section}` | {desc} | {enlace} |\n"
        hub_content += (
            "\n"
            "## Protocolo de sesión\n"
            "\n"
            "Inicio:\n"
            f"1. `{comando_de_tool('vault_standard_upgrade --check')}`\n"
            f"2. `{comando_de_tool('vault_reindex')}`\n"
            f"3. `{comando_de_tool('vault_audit')}`\n"
            "\n"
            "Cierre:\n"
            f"1. `{comando_de_tool('vault_audit')}`\n"
            f"2. `{comando_de_tool('vault_tags')}`\n"
            f"3. `{comando_de_tool('vault_reindex --graph')}`\n"
            "\n"
            "Para detalles de cada comando, ver [[vault-commands|vault-commands]].\n"
        )
        _escribir_hub(_hub_note(), hub_content)

    if not _commands_note().exists():
        _escribir_hub(_commands_note(), _nota_de_comandos())


#: Bloques de la nota de comandos: (título, [(comentario, receta)]). La receta
#: va sin forma de invocación — la pone `comando_de_tool` según dónde corra.
#:
#: Hasta v40.35 la nota era un literal con `python scripts/...`, que en una
#: instalación por wheel no existe; citaba `--init v32`, catorce versiones
#: atrás; publicaba `vault_spec_validate`, que no es una tool instalable, y su
#: lista por sección —escrita a mano, 01–16— daba a once de ellas un comando
#: al que le faltaban flags obligatorios. Las secciones salen ahora del
#: registro, con las mismas recetas que sugiere `vault_audit`.
BLOQUES_DE_COMANDOS = (
    ("Inicialización", (
        ("Crear o completar el vault: carpetas, índices de sección y hub",
         "vault_init"),
        ("Versión del estándar y migraciones pendientes, sin aplicar nada",
         "vault_standard_upgrade --check"),
        ("Aplicar las migraciones pendientes hasta la versión vigente",
         "vault_standard_upgrade"),
    )),
    ("Escritura y lectura de notas", (
        ("Crear o actualizar una nota",
         "vault_write --folder 07_Knowledge --title 'Mi nota' --content '...'"),
        ("Leer una nota por ruta", "vault_read --path 07_Knowledge/mi-nota.md"),
        ("Buscar full-text", "vault_search --query 'circuit breaker'"),
        ("Listar notas de una carpeta", "vault_list --folder 07_Knowledge"),
        ("Agregar contenido al final (changelogs, session logs)",
         "vault_append --path 07_Knowledge/mi-nota.md --content '...'"),
    )),
    ("Índices", (
        ("Regenerar el índice de una sección",
         "vault_section_index --folder 07_Knowledge"),
        ("Regenerar todos los índices de sección y el índice maestro",
         "vault_master_index"),
        ("Regenerar search-index.json, graph.json y hash-index.json",
         "vault_reindex --graph"),
    )),
    ("Salud y auditoría", (
        ("Health score e issues (enlaces rotos, notas huérfanas…)", "vault_audit"),
        ("Validar estructura del vault (notas, frontmatter, CIA)", "vault_validate"),
    )),
    ("Backups", (
        ("Snapshot con árbol Merkle para verificar integridad", "vault_backup"),
        ("Listar backups disponibles", "vault_backup_list"),
        # `--name` no existe: la tool declara `--backup_name` y el comando moría
        # en `unrecognized arguments`. Lo escribía el generador, así que el
        # comando roto viajaba a *cada vault que el estándar crea* — el defecto
        # de v40.4 en la copia que el guard de v40.4 no estaba mirando.
        ("Restaurar desde un backup", "vault_restore --backup_name <backup-name>"),
    )),
)


def recetas_de_la_nota_de_comandos() -> List[str]:
    """Toda receta que la nota publica, en el orden en que aparece."""
    recetas = [r for _, filas in BLOQUES_DE_COMANDOS for _, r in filas]
    recetas += [section_tool_hint(s) for s in ORDERED_SECTIONS if section_tool_hint(s)]
    return recetas


def _nota_de_comandos() -> str:
    lineas = [
        _bloque_de_navegacion("Vault Commands", "vault-commands", "commands"),
        "",
        "# Vault Commands — Referencia unificada de comandos CLI",
        "",
        "> Esta nota es la **referencia única de comandos** del vault. Ningún "
        "otro archivo (incluyendo índices auto-generados y stubs de sección) "
        "debería embeber un bloque de comandos inline. Si necesitas un "
        "comando nuevo, agrégalo aquí.",
        "",
        "Con el paquete instalado cada comando es `vault run <tool> <flags>`; desde "
        "un checkout del estándar, `python scripts/<tool>.py <flags>`. Esta nota "
        "está escrita en la forma del sitio que la generó. El vault destino se "
        "fija con la variable de entorno `VAULT_ROOT`.",
        "",
    ]
    for titulo, filas in BLOQUES_DE_COMANDOS:
        lineas += [f"## {titulo}", ""]
        lineas += [f"- {comentario} — `{comando_de_tool(receta)}`"
                   for comentario, receta in filas]
        lineas.append("")
    lineas += [
        "## Comandos por sección",
        "",
        "La receta con la que se crea la primera nota de cada sección. `<...>` y "
        "`'...'` son lo que rellenas tú.",
        "",
    ]
    for section in ORDERED_SECTIONS:
        receta = section_tool_hint(section)
        if receta:
            lineas.append(f"- **{section}** — `{comando_de_tool(receta)}`")
    lineas.append("")
    return "\n".join(lineas)


def _collect_notes(section_path: Path, include_subdirs: bool) -> List[Dict[str, Any]]:
    """Adaptador: el recorrido vive en el dominio de Índices.

    Las secciones son las del vault: con `vault_registry.SECTIONS`, el índice
    de una sección propia salía vacío aunque tuviera notas (hasta v41.2).
    """
    return recolectar_notas(
        get_vault_root(),
        section_path,
        secciones_del_vault(get_vault_root()),
        include_subdirs,
        parse_frontmatter,
    )


def _breadcrumb(folder_key: str) -> str:
    """Adaptador: la migaja de navegación vive en el dominio de Índices."""
    return migaja(folder_key)


def _indices_de_una_regeneracion_completa(vroot: Path) -> set:
    """Los `index.md` que `vault_master_index` escribe en una pasada: el de
    cada sección con carpeta en disco y el suyo propio."""
    return {"99_Index/index.md"} | {
        f"{s}/index.md" for s in secciones_del_vault(vroot) if (vroot / s).is_dir()}


def _indices_disponibles(vroot: Path, previstos: set):
    """Ruta de un índice → ¿se puede enlazar? Lo está si existe o si esta
    ejecución lo va a escribir. Enlazar uno que no llega a existir es un
    enlace roto, peor que nombrarlo en texto."""
    def disponible(ruta: str) -> bool:
        return ruta in previstos or (vroot / ruta).is_file()
    return disponible


def _renderizador(indice_disponible=None) -> RenderizadorDeIndice:
    """Se construye por llamada: `section_description` lee el registro y
    `safe_wikilink` el kernel, y ninguno de los dos se congela en el import."""
    # El índice de nombres se construye la primera vez que hace falta: una
    # sección vacía no enlaza nada y no tiene por qué recorrer el vault.
    indice: Dict[str, List[str]] = {}

    def destino(rel: str) -> str:
        if not indice:
            indice.update(indice_de_nombres(
                *inventario_de_nombres(get_vault_root(), is_snapshot_path)))
        return destino_mas_corto(rel, indice)

    return RenderizadorDeIndice(
        # Con la raíz, para que una sección propia lleve su descripción.
        describir_seccion=lambda s: section_description(s, get_vault_root()),
        pista_de_tool=section_tool_hint,
        enlace_seguro=safe_wikilink,
        destino=destino,
        indice_disponible=indice_disponible,
    )


def _build_index_content(
    folder: str,
    notes: List[Dict[str, Any]],
    now: str,
    subdirs: Optional[List[str]] = None,
    indice_disponible=None,
) -> str:
    """Adaptador: el formato del índice vive en el dominio de Índices."""
    return _renderizador(indice_disponible).render(
        folder, notes, now, subcarpetas=subdirs)



def _indice_a_escribir(carpeta: Path) -> Optional[Path]:
    """Dónde regenerar el índice de `carpeta`, o `None` si el que hay es ajeno.

    Hasta v41.2 se escribía `carpeta/index.md` sin mirar: un índice escrito a
    mano se perdía, y un `INDEX.md` acababa renombrado en un sistema de ficheros
    que no distingue mayúsculas. Ahora el generador solo reescribe lo que lleva
    su marca, y conserva el nombre que el fichero ya tenía.
    """
    existente = indice_de_la_carpeta(carpeta)
    if existente is None:
        return carpeta / "index.md"
    try:
        texto = existente.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return existente if es_indice_generado(texto) else None


def vault_section_index(
    folder: str, include_subdirs: bool = True, regeneracion_completa: bool = False
) -> Dict[str, Any]:
    """
    Generate or update {folder}/index.md with navigation, notes table and subdir listing.
    Always produces populated content — never a bare empty file.
    Also generates index.md for each immediate subdirectory when include_subdirs=True.

    Args:
        folder: Section folder relative to vault root (e.g. "01_Projects")
        include_subdirs: If True, include notes in subdirectories and index their subdirs
        regeneracion_completa: el llamador garantiza que en esta misma ejecución
            escribe el índice de cada sección y `99_Index/index.md`
            (`vault_master_index`). Con eso la migaja y el hub los enlazan
            aunque todavía no estén en disco; sin él, solo los que ya existen.

    Returns:
        {"ok": True, "path": "01_Projects/index.md", "noteCount": 12, "is_empty": False,
         "subdirIndexes": [...], "creados": [...]}

        `creados` son los índices que no existían antes de esta llamada: notas
        nuevas en disco que el gancho de escritura pone en la búsqueda (AP-47).
    """
    # Guard CN-02/AP-15: solo secciones canónicas son destinos válidos. Sin esto,
    # folder="" o "." escribe index.md y .locks/ en la RAÍZ del vault.
    folder = (folder or "").strip().replace("\\", "/").strip("/")
    if not folder or folder == ".":
        # `detail` se conserva: los consumidores que ya lo leían siguen
        # encontrándolo. Lo que cambia es que el motivo ahora también viaja
        # como `error_code` del catálogo, que es por donde se decide.
        return {
            **emit_error(
                "vault_section_index",
                "INVALID_FOLDER",
                "folder no puede ser la raíz del vault (CN-02/AP-15); usar una sección canónica, ej. 01_Projects",
            ),
            "detail": "folder no puede ser la raíz del vault (CN-02/AP-15); usar una sección canónica, ej. 01_Projects",
        }
    # CN-02: una sección es la del estándar o la propia declarada en
    # `secciones.json`. Hasta v41.2 se aceptaba solo `vault_registry.SECTIONS`
    # y el índice de una sección propia se rechazaba, también cuando lo pedía
    # `vault_master_index`, que ya las recorre. Un registro ilegible es un
    # fallo, no un rechazo de la carpeta (AP-51).
    try:
        secciones = secciones_del_vault(get_vault_root())
    except ValueError as exc:
        return emit_error("vault_section_index", "DATA_FILE_CORRUPT", str(exc),
                          pista="corregir 00_System/secciones.json (vault_section --list)")

    if folder.split("/")[0] not in secciones:
        return {
            **emit_error(
                "vault_section_index",
                "INVALID_FOLDER",
                f"'{folder.split('/')[0]}' no es una sección del vault: ni del estándar ni propia declarada (CN-02)",
            ),
            "detail": f"'{folder.split('/')[0]}' no es una sección del vault: ni del estándar ni propia declarada (CN-02)",
        }

    # Ensure the hub notes exist (idempotent — only creates on first call).
    # This makes the vault self-bootstrapping: a single call to vault_section_index
    # for any section creates vault-hub.md and vault-commands.md if missing.
    # Qué índices se pueden enlazar: los que existen y los que esta ejecución
    # va a escribir. Enlazar uno que no llega a existir es un enlace roto.
    vroot = get_vault_root()
    previstos = {f"{folder}/index.md"}
    if regeneracion_completa:
        previstos |= _indices_de_una_regeneracion_completa(vroot)
    indice_disponible = _indices_disponibles(vroot, previstos)

    aviso_hub = None
    try:
        _ensure_hub_notes(indice_disponible)
    except (OSError, ValueError, TimeoutError) as exc:
        # Sigue sin bloquear al indexador, pero deja de ser invisible (AP-51):
        # el `except Exception: pass` convertía "no pude crear el hub" en
        # indistinguible de "ya existía", y el hub es el punto de entrada del
        # vault entero. El tipo va acotado a propósito: un fallo de programación
        # aquí debe salir, no absorberse.
        aviso_hub = f"{type(exc).__name__}: {exc}"
        print(f"[vault_section_index] hub no creado: {aviso_hub}", file=sys.stderr)

    section_path = vroot / folder
    if not section_path.exists():
        return {**emit_error("vault_section_index", "FOLDER_NOT_FOUND", f"La seccion no existe: {folder}"), "folder": folder}

    try:
        assert_within_vault(section_path, vroot)
    except ValueError as e:
        return {**emit_error("vault_section_index", "INVALID_PATH", str(e)), "detail": str(e)}

    now = utcnow()
    notes = _collect_notes(section_path, include_subdirs)
    preservados: List[str] = []
    creados: List[str] = []

    # Discover immediate subdirectories (for subdir listing in index)
    subdir_folders: List[str] = []
    subdir_indexes: List[str] = []
    if include_subdirs:
        for sub in sorted(section_path.iterdir()):
            if not sub.is_dir() or sub.name.startswith("."):
                continue
            sub_folder = str(sub.relative_to(vroot)).replace("\\", "/")
            # Maquinaria declarada: la carpeta existe porque una norma guarda
            # ahí su estado, no porque haya notas. Indexarla creaba un
            # `index.md` sobre una carpeta vacía que después contaba como nota
            # en disco y desajustaba el índice de búsqueda (AP-47) — un vault
            # recién onboardeado nacía violando una norma del estándar que lo
            # creó, y solo se veía al escribir la bitácora antes del reindex.
            if sub_folder in MACHINERY_FOLDERS:
                continue
            subdir_folders.append(sub_folder)

            # Generate sub-section index (no nested subdirs to avoid deep recursion)
            sub_notes = _collect_notes(sub, include_subdirs=True)
            sub_index = _indice_a_escribir(sub)
            if sub_index is None:
                ajeno = indice_de_la_carpeta(sub)
                preservados.append(str(ajeno.relative_to(vroot)).replace("\\", "/"))
                subdir_indexes.append(preservados[-1])
                continue
            assert_within_vault(sub_index, vroot)
            # Leaf lock on the index file itself: serializes concurrent regens of
            # this same sub-index (two notes in the section written at once). Safe
            # from deadlock — index.md is in _SKIP_AUTO_INDEX so writing it never
            # re-enters _auto_section_index, and no caller holds this lock.
            with file_lock(sub_index):
                sub_contenido = _build_index_content(
                    sub_folder, sub_notes, now, subdirs=None,
                    indice_disponible=indice_disponible,
                )
                if not sub_index.exists():
                    creados.append(str(sub_index.relative_to(vroot)).replace("\\", "/"))
                record_raw_write(sub_index, sub_contenido)
                escritura_atomica(sub_index, sub_contenido)
            subdir_indexes.append(
                str(sub_index.relative_to(vroot)).replace("\\", "/")
            )

    # Write main section index — includes subdir listing
    index_path = _indice_a_escribir(section_path)
    if index_path is None:
        index_path = indice_de_la_carpeta(section_path)
        preservados.append(str(index_path.relative_to(vroot)).replace("\\", "/"))
    else:
        assert_within_vault(index_path, vroot)
        # Leaf lock (see sub-index note above): serialize concurrent regens of this
        # section index; deadlock-free because index.md is skipped by _auto_section_index.
        with file_lock(index_path):
            contenido = _build_index_content(
                folder, notes, now, subdirs=subdir_folders or None,
                indice_disponible=indice_disponible,
            )
            if not index_path.exists():
                creados.append(str(index_path.relative_to(vroot)).replace("\\", "/"))
            record_raw_write(index_path, contenido)
            escritura_atomica(index_path, contenido)

    return {
        "ok": True,
        "hub_warning": aviso_hub,
        **write_report(),
        "path": str(index_path.relative_to(vroot)).replace("\\", "/"),
        # Índices que no llevan la marca del generador: se conservan tal cual.
        "indice_ajeno_preservado": preservados,
        "noteCount": len(notes),
        "is_empty": len(notes) == 0,
        "subdirIndexes": subdir_indexes,
        "creados": creados,
    }


def refrescar_busqueda(path: Path, *mas: Path) -> Dict[str, Any]:
    """Pone la nota recién escrita en `search-index.json` (AP-47).

    Vive aquí y no en cada escritor porque `vault_io -> vault_section_index` es
    el gancho que el kernel ya tiene declarado: importarlo desde `vault_ingest`
    estrenaba un cruce consulta -> autoría que ningún puerto descuenta.
    """
    return ServicioReindex(
        RepositorioIndices(construir()), parse_frontmatter
    ).refrescar(Path(path), *(Path(m) for m in mas))


# Nombre público conservado (lo importan tests y `vault_norms`); la definición
# es una sola y vive en el dominio, para que el guard y el generador no puedan
# discrepar sobre qué formato está prohibido (AP-05).
RE_ALIAS_IN_INDEX_TABLE = RE_ALIAS_EN_TABLA


def heal_indexes(root: Optional[Path] = None) -> Dict[str, Any]:
    """Sanea todos los index.md del vault: regenera los que tengan formato
    legacy ([[stem|alias]] en celdas) o estén ausentes en secciones con notas.

    Idempotente (AP-36): correrlo N veces converge al mismo estado.
    """
    from vault_io import get_vault_root

    vroot = (root or get_vault_root()).resolve()
    healed: List[Dict[str, str]] = []
    skipped = 0
    # Las del vault, también las propias: hasta v41.2 era `SECTIONS` y el
    # índice ausente de una sección propia no se reparaba nunca. Sanear con el
    # registro ilegible dejaría fuera las propias en silencio (AP-51).
    try:
        secciones = secciones_del_vault(vroot)
    except ValueError as exc:
        return emit_error("vault_section_index", "DATA_FILE_CORRUPT", str(exc),
                          pista="corregir 00_System/secciones.json (vault_section --list)")
    for folder in secciones:
        sec_path = vroot / folder
        if not sec_path.is_dir() or folder in ("00_System", "10_Migrated", "99_Index"):
            continue
        for index_path in [sec_path / "index.md", *sec_path.glob("*/index.md")]:
            reason = None
            if not index_path.exists():
                if any(index_path.parent.glob("*.md")):
                    reason = "missing"
            else:
                try:
                    text = index_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    reason = "unreadable"
                else:
                    # Un índice escrito a mano no se «sana»: la regeneración lo
                    # conservaría igual y aquí saldría como reparado sin serlo.
                    if es_indice_generado(text) and RE_ALIAS_IN_INDEX_TABLE.search(text):
                        reason = "legacy_alias_format"
            if reason is None:
                skipped += 1
                continue
            target_folder = str(index_path.parent.relative_to(vroot)).replace("\\", "/")
            # Regenerar la sección top-level cubre también sus sub-índices
            top = target_folder.split("/")[0]
            r = vault_section_index(top)
            healed.append({"index": f"{target_folder}/index.md", "reason": reason, "ok": str(r.get("ok"))})
    return {
        "ok": True,
        "tool": "vault_section_index.heal",
        "vault_root": str(vroot),
        "healed": healed,
        "healed_count": len(healed),
        "clean_count": skipped,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Section Index -- generate {folder}/index.md",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_section_index.py --folder 01_Projects
  python vault_section_index.py --folder 07_Knowledge
  python vault_section_index.py --folder 01_Projects --no-subdirs
  python vault_section_index.py --folder 08_Runbooks

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Se llama automaticamente por vault_write despues de cada escritura exitosa
  - El index.md generado es un artefacto derivado -- no editar manualmente
""",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--folder", help="Section folder relative to vault root"
    )
    parser.add_argument(
        "--no-subdirs", action="store_true", help="Exclude notes in subdirectories"
    )
    parser.add_argument(
        "--heal",
        action="store_true",
        help="Sanear todos los index.md (formato legacy con alias o ausentes)",
    )
    parser.add_argument("--root", help="Vault root para --heal (default: auto-detect)")
    args = parser.parse_args()

    if args.heal:
        if args.root:
            from vault_io import set_vault_root

            set_vault_root(Path(args.root))  # AP-36: side-effects al vault objetivo
        result = heal_indexes(Path(args.root) if args.root else None)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if not args.folder:
        parser.error("--folder es requerido (o usar --heal)")

    result = vault_section_index(args.folder, include_subdirs=not args.no_subdirs)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_section_index"))
