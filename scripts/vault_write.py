#!/usr/bin/env python3

"""

Vault Write Tool — Core writing tool for Obsidian vault



Creates or updates any note with correct YAML frontmatter.

Implements versioning: copies previous version to .history/ before overwriting.

Updates search-index.json automatically.



Usage:

    python vault_write.py --folder "01_Projects/ans" --title "Status" --content "# Status\n\n..."

    python vault_write.py --folder "03_Decisions" --title "ADR-001" --tags "architecture,backend" --meta '{"status": "accepted"}'

"""

import argparse

import difflib

import json

import os

import re

import shutil

import sys

import vault_tags
import yaml
from vault_errors import emit_error, emit_fallo, fuera_de_sesion, wrap_main

from vault_io import (
    is_snapshot_path,  # dueño único de qué es una instantánea (AP-57)
    write_report,
    atomic_write_text,
    atomic_write_json,
    atomic_update_json,
    assert_within_vault,
    normalize_stem,
    file_lock,
    guarda_secretos,  # dueño único del escaneo de secretos (AP-57)
)
from vault_encoding import (
    sanitize_content,
    normalize_to_nfc,
    sanitize_filename,
    detect_issues,
)
from vault_regex import (
    RE_WIKILINK,
    detect_bracket_anomalies,
    detect_path_anchored,
    fix_nested_brackets,
    fix_whitespace_in_links,
    WIKILINK_MAX_LEN,
)
from vault_lib import (
    indice_de_destinos,          # dueño único de qué resuelve (AP-57)
    resolver_destino_wikilink,   # dueño único de cómo se resuelve (AP-57)
    read_frontmatter,
    separar_frontmatter,
    slugify_strict,              # dueño único del slug (CN-01, v40.35)
    utcnow,
    strip_code_blocks,
    Config,
    parse_frontmatter_with_body,
    canonical_utc,
)
from vault_norms_catalog import (
    compute_norm_refs,
    normalize_status,
    STATUS_VOCAB,
    STATUS_TRANSITIONS,
)
from datetime import datetime, timezone

import uuid

from pathlib import Path

from typing import Any, Dict, List, Optional


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# La configuración se lee del registro único, no con un default por punto
# de uso. Ver `vault_entorno.py`.
from vault_entorno import leer as _env

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.kernel.errores import completar_envelope  # noqa: E402
from vault.kernel.frontmatter_escritura import Frontmatter  # noqa: E402
from vault.kernel.indices_structural import describir_reserva, es_nombre_reservado  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _history_dir() -> Path:
    return _repo().dir_historial


def _index_file() -> Path:
    return _repo().indice_busqueda


def _tag_registry() -> Path:
    return _repo().registro_etiquetas


def _check_content_gate(content: str, folder: str) -> bool:
    """AP-45: la puerta que impide la nota que existe para llenar la sección.

    Return True if content passes the strict content gate. 00_System is exempt.

    The gate requires:
    - ≥ 3 real lines (excluding blank, TODO-only, lone-dashes, lone-headings)
    - ≥ 10 real words across those lines (reject lorem-ipsum stubs and 1-word lines)
    - No line longer than 800 chars (reject minified blobs that hide emptiness)
    - Bracket balance: opens == closes for [[...]] (AP-24 prevention)
    - No empty [[]] wiki-links (AP-22 prevention, mild)

    Previous version (3 real lines) allowed trivial notes like:
        "ok
        test
        done"
    which produce orphan/empty notes that pollute the search index.
    """
    if folder.startswith("00_System"):
        return True
    real_lines = [
        l
        for l in content.split("\n")
        if l.strip()
        and not l.strip().startswith("TODO")
        and l.strip() not in ("-", "- ", "---")
        and not re.match(r"^#+\s*$", l.strip())
    ]
    if len(real_lines) < 3:
        return False
    # Word count: split on whitespace, ignore markdown markers and pipes
    words: List[str] = []
    for line in real_lines:
        # strip heading markers, bullets, table pipes
        cleaned = re.sub(r"^[#\-\*\s|>]+", "", line)
        for tok in cleaned.split():
            tok = tok.strip("`*~_[]()#").strip(".,;:!?")
            if tok and len(tok) > 1:
                words.append(tok)
    if len(words) < 10:
        return False
    # Reject minified blobs
    if any(len(l) > 800 for l in real_lines):
        return False
    # AP-21 prevention: reject path-anchored wiki-links [[folder/note]]
    path_anchored = detect_path_anchored(content)
    if path_anchored:
        return False

    # AP-24 prevention: detect bracket anomalies (nested, mixed, etc)
    anomalies = detect_bracket_anomalies(content)
    if anomalies:
        # Try auto-fix first
        fixed_content = fix_nested_brackets(content)
        fixed_content = fix_whitespace_in_links(fixed_content)
        # Check again after auto-fix
        remaining = detect_bracket_anomalies(fixed_content)
        # Filter out empty links (handled separately)
        remaining_non_empty = [r for r in remaining if r["type"] != "empty"]
        if remaining_non_empty:
            return False

    # AP-22 prevention (soft): reject notes with empty [[]] wiki-links.
    # These pass the strict gate otherwise but pollute the search index with
    # literal `[[]]` as text. Allow them only in spec/example documentation
    # where they're meaningful; for regular notes, reject.
    if folder.startswith("00_System"):
        return True
    clean = strip_code_blocks(content)
    if re.search(r"\[\[\s*\]\]", clean):
        return False
    return True


def _content_gate_reason(content: str, folder: str) -> Optional[str]:
    """Return human-readable reason why content failed the gate, or None if it passes."""
    if folder.startswith("00_System"):
        return None
    real_lines = [
        l
        for l in content.split("\n")
        if l.strip()
        and not l.strip().startswith("TODO")
        and l.strip() not in ("-", "- ", "---")
        and not re.match(r"^#+\s*$", l.strip())
    ]
    if len(real_lines) < 3:
        return f"only {len(real_lines)} real line(s) (need ≥3)"
    words: List[str] = []
    for line in real_lines:
        cleaned = re.sub(r"^[#\-\*\s|>]+", "", line)
        for tok in cleaned.split():
            tok = tok.strip("`*~_[]()#").strip(".,;:!?")
            if tok and len(tok) > 1:
                words.append(tok)
    if len(words) < 10:
        return f"only {len(words)} real word(s) (need ≥10)"
    if any(len(l) > 800 for l in real_lines):
        return "line longer than 800 chars (minified blob?)"

    # AP-21: path-anchored wiki-links check
    path_anchored = detect_path_anchored(content)
    if path_anchored:
        return f"AP-21: path-anchored wiki-links detected: {path_anchored}. Use [[note-name]] without folder path."

    # AP-24 / AP-22 reasons — checked AFTER basic quality gates
    # First try auto-fix
    fixed_content = fix_nested_brackets(content)
    fixed_content = fix_whitespace_in_links(fixed_content)

    # Check for remaining anomalies
    anomalies = detect_bracket_anomalies(fixed_content)
    if anomalies:
        empty_anomalies = [a for a in anomalies if a["type"] == "empty"]
        non_empty_anomalies = [a for a in anomalies if a["type"] != "empty"]

        if non_empty_anomalies:
            examples = [a["example"] for a in non_empty_anomalies[:3]]
            return f"AP-24: bracket anomalies detected: {examples}. These will be auto-fixed on save."

    # Check empty links
    clean = strip_code_blocks(content)
    if re.search(r"\[\[\s*\]\]", clean):
        n = len(re.findall(r"\[\[\s*\]\]", clean))
        return (
            f"AP-22: {n} empty `[[]]` wiki-link(s). "
            "Empty wiki-links pollute the search index — remove them or replace with real targets."
        )
    return None


# Configuration


def _tag_suggestions(new_tags: List[str]) -> List[Dict[str, Any]]:
    """Return canonical similar tags for any new_tags not yet in registry. Non-blocking."""

    if not _tag_registry().exists():
        return []

    # AP-39 — leía `registry["tags"]`, una clave que el registro no tiene desde
    # que las facetas viven en `canonical_tags`. La sugerencia llevaba versiones
    # sin dispararse nunca, y por eso inventar un tag no costaba nada.
    canonical: set = set(vault_tags.canonical_tags())

    suggestions = []

    for tag in new_tags:
        if tag in canonical:
            continue

        for candidate in canonical:
            # simple similarity: exact prefix/substring

            a, b = tag.lower(), candidate.lower()

            if a == b:
                continue

            if a in b or b in a:
                score = 0.85

            else:
                common_prefix = sum(1 for x, y in zip(a, b) if x == y)

                if common_prefix >= 3:
                    score = 0.6 + (common_prefix / max(len(a), len(b))) * 0.2

                else:
                    score = sum(1 for x, y in zip(a, b) if x == y) / max(len(a), len(b))

            if score >= 0.6:
                suggestions.append(
                    {
                        "new_tag": tag,
                        "similar_canonical": candidate,
                        "score": round(score, 2),
                    }
                )

    return sorted(suggestions, key=lambda x: -x["score"])[:10]


def slugify(title: str) -> str:
    """CN-01: el filename en kebab-case, derivado del título y no recibido.

    Aquí se cumple CN-01 entera: ninguna otra tool audita después los nombres
    ya escritos, así que si esto no normaliza, nada lo corrige. Por eso el
    enforcement de CN-01 es `guard` y no `guard+audit`.

    Delega en el dueño canónico, `slugify_strict` (v40.35). Hasta v40.34 este
    módulo derivaba su propio slug con `sanitize_filename(...).lower()`, que
    conserva acentos, `—`, paréntesis y puntos: «Mapa de Código — ANS (v2)»
    daba `mapa-de-código-—-ans-(v2)` aquí y `mapa-de-codigo-ans-v2` en el resto
    del toolkit — dos identidades para una nota (AP-57). Las notas escritas con
    el slug viejo las sigue encontrando `_nota_heredada`, para no duplicarlas.

    Un título sin un solo carácter de palabra (`!!!`) deja vacío el slug
    estricto; entonces se usa el viejo, que es el nombre que esa nota tendría
    ya, en vez de inventar uno.
    """
    slug = slugify_strict(title)[:200].strip("-")
    return slug or _slug_heredado(title)


def _slug_heredado(title: str) -> str:
    """superseded_by: slugify (v40.35) — solo para encontrar notas ya escritas.

    Es el slug que `vault_write` usó hasta v40.34. Se conserva su contrato
    (`sanitize_filename` + minúsculas) porque las notas que produjo siguen en
    los vaults de los consumidores, y actualizar una no puede duplicarla.
    """
    return sanitize_filename(title, max_length=200).lower()


def _nota_heredada(vault_path: Path, titulo: Optional[str] = None) -> Path:
    """CN-01: la nota ya escrita con otro nombre para el mismo título.

    Dos generaciones de nombres heredados, en este orden:

    1. El mismo nombre con otras mayúsculas — antes de que el slug fuera a
       minúsculas. En un sistema de ficheros sensible a mayúsculas la primera
       actualización tras el cambio crearía un duplicado (AP-02); y en Windows,
       donde `exists()` sí la encuentra, la escritura atómica la renombraba a
       minúsculas — medido, no supuesto: el test de esta función lo destapó.
    2. El nombre del slug anterior a v40.35 (`_slug_heredado`), con acentos y
       puntuación, si se pasa el título.

    Si alguno existe, es la misma nota: se actualiza ella, con su nombre y su
    identidad. El nombre nuevo solo se estrena cuando no hay ninguna.
    """
    carpeta = vault_path.parent
    if not carpeta.is_dir():
        return vault_path
    buscados = [vault_path.name.lower()]
    if titulo is not None:
        buscados.append(f"{_slug_heredado(titulo)}.md".lower())
    existentes: dict = {}
    for candidato in sorted(carpeta.iterdir()):
        if candidato.is_file():
            existentes.setdefault(candidato.name.lower(), candidato)
    for nombre in buscados:
        if nombre in existentes:
            return existentes[nombre]
    return vault_path
    nombre = vault_path.name.lower()
    for candidato in sorted(vault_path.parent.iterdir()):
        if candidato.is_file() and candidato.name.lower() == nombre:
            return candidato
    return vault_path


def _check_bracket_balance(content: str) -> Optional[str]:
    """AP-22 y AP-14: corchetes desbalanceados y wiki-links vacíos.

    AP-22 nombra el `[[]]` vacío y AP-24 los corchetes rotos; los dos son
    variantes de AP-14, que es la norma que gobierna el enlace que no resuelve.
    Este es el punto de rechazo en escritura de AP-14 (`tools_enforcing`): más
    allá de aquí el enlace roto ya es el dato.
    """
    clean = strip_code_blocks(content)
    opens = len(re.findall(r"\[\[", clean))

    closes = len(re.findall(r"\]\]", clean))

    if opens != closes:
        return f"AP-22: corchetes desbalanceados — {opens} '[[' vs {closes} ']]'"

    empty = re.findall(r"\[\[\s*\]\]", clean)

    if empty:
        return f"AP-22: wiki-links vacios detectados: {empty[:3]}"

    return None


def _collect_ghost_links(wiki_links: List[str], desde: Optional[Path] = None) -> List[str]:
    """SP-02 y AP-14: enlaces cuyo destino no existe todavía en el vault.

    SP-02 pide verificar antes de linkar. Esto lo hace por el agente en el
    momento de escribir —no bloquea, avisa— y `vault_graph` y `vault_audit` lo
    vuelven a medir después sobre el vault entero.

    **Es la validación que ocurre al nacer la nota**, y hasta v40.14 medía con
    su propio criterio en los cuatro sitios donde hay un dueño canónico
    (AP-57), con los dos sentidos del error a la vez:

    - Resolvía por **basename**, así que `[[containers/ct105]]` pasaba si
      existía cualquier `ct105.md` en cualquier carpeta. Falso negativo: el
      enlace nace roto y la validación lo bendice — el peor sentido, porque
      sale verde.
    - Trataba `.history` como única instantánea, así que las notas de
      `vault-backups/` y `.trash/` contaban como destinos válidos. Un enlace a
      algo que solo existe en una copia congelada pasaba igual.
    - **No miraba `aliases:`**, que es la mitad de cómo Obsidian resuelve. Un
      `[[Change Log]]` con ese alias declarado se avisaba como fantasma. Falso
      positivo: ruido, y un aviso con ruido se ignora — que es como un vault
      llega a 221 enlaces muertos con la validación puesta.

    Los dos errores se sostienen mutuamente: el ruido enseña a ignorar el aviso
    justo cuando el aviso deja escapar lo que importa.
    """
    raiz = _raiz()
    relativas = []
    alias: List[str] = []
    for p in raiz.rglob("*.md"):
        rel = p.relative_to(raiz)
        if is_snapshot_path(rel):
            continue
        relativas.append(rel)
        try:
            fm = read_frontmatter(p)
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            # Un frontmatter que no se lee no aporta aliases, pero el fichero
            # sigue siendo un destino válido por su ruta: ya está en
            # `relativas`. Se capturan las tres concretas y no `Exception`,
            # que convertiría cualquier fallo propio en «esta nota no tiene
            # aliases» (AP-51).
            continue
        for a in (fm or {}).get("aliases") or []:
            if isinstance(a, str):
                alias.append(a)

    destinos = indice_de_destinos(relativas, alias)

    ghost = []
    for link in wiki_links:
        objetivo = resolver_destino_wikilink(link, desde)
        if objetivo and objetivo not in destinos:
            ghost.append(link)

    return ghost


#: Campos que decide el write path y no quien llama. `--meta` los sobrescribía
#: en silencio (medido el 2026-10-04): `{"id":"fijo","createdAt":"ayer"}` dejaba
#: en disco una nota con otra identidad que la que la tool devolvía en `id`, y
#: un timestamp que no es ISO 8601. La identidad no puede ser ambigua (CN-01) y
#: las fechas salen del reloj, no del agente (AP-13).
CAMPOS_DEL_WRITE_PATH: Dict[str, str] = {
    "title": "usa --title",
    "id": "es la identidad de la nota: la acuña vault_write o la conserva al actualizar (CN-01)",
    "createdAt": "sale del reloj al crear, no de quien llama (AP-13)",
    "updatedAt": "sale del reloj en cada escritura (AP-13)",
    "tags": "usa --tags",
    "norm_refs": "se derivan de las normas que aplica la escritura",
    "status_note": "lo deriva la normalización de status (AP-38)",
}

#: Campos con significado que `--meta` sí puede fijar, y por eso los que una
#: errata suele imitar.
CAMPOS_DE_META = ("type", "status", "cia_integrity", "cia_availability",
                  "cia_sensitivity", "agent")


def problemas_de_meta(meta: Any, folder: str = "") -> List[str]:
    """Lo que `--meta` no puede decir, antes de escribir nada.

    `--meta` es la puerta abierta del frontmatter: el vocabulario de claves es
    abierto a propósito (propiedades propias de quien usa el vault), así que
    aquí no se rechaza lo desconocido sino lo que se hace pasar por conocido:
    un campo del write path, una errata de un campo con significado
    (`statsu`, `tag`, `Status`) o un valor fuera del vocabulario que el
    registro ya declara. Antes todo ello pasaba con `ok: true`.
    """
    if meta is None:
        return []
    if not isinstance(meta, dict):
        return [f"--meta tiene que ser un objeto JSON; llegó {type(meta).__name__}"]

    conocidos = {c.lower(): c for c in (*CAMPOS_DEL_WRITE_PATH, *CAMPOS_DE_META)}
    problemas: List[str] = []
    for clave in meta:
        canon = conocidos.get(clave.lower())
        if canon in CAMPOS_DEL_WRITE_PATH:
            problemas.append(
                f"`{clave}` no se fija por --meta: {CAMPOS_DEL_WRITE_PATH[canon]}"
            )
        elif canon and canon != clave:
            problemas.append(f"`{clave}` no es un campo; el campo es `{canon}`")
        elif canon is None:
            parecido = difflib.get_close_matches(clave.lower(), list(conocidos), n=1, cutoff=0.8)
            if parecido:
                problemas.append(
                    f"`{clave}` parece una errata de `{conocidos[parecido[0]]}`; "
                    "corrígela o usa un nombre que no se confunda con un campo del estándar"
                )

    if "status" in meta:
        if not isinstance(meta["status"], str) or normalize_status(meta["status"])[0] is None:
            problemas.append(
                f"status {meta['status']!r} no pertenece al vocabulario canónico "
                f"(CN-03); usa uno de {sorted(STATUS_VOCAB)}"
            )

    from vault_fundamentals_catalog import cia_valores

    for campo in ("cia_integrity", "cia_availability", "cia_sensitivity"):
        if campo in meta and meta[campo] not in cia_valores(campo):
            problemas.append(
                f"{campo} {meta[campo]!r} fuera de {sorted(cia_valores(campo))}"
            )

    for campo in ("type", "agent"):
        if campo in meta and (not isinstance(meta[campo], str) or not meta[campo].strip()):
            problemas.append(f"{campo} tiene que ser texto no vacío")

    if isinstance(meta.get("type"), str) and folder:
        from vault_registry import type_misfiled_in

        destino = type_misfiled_in(folder, meta["type"])
        if destino:
            problemas.append(
                f"type {meta['type']!r} pertenece a {', '.join(destino)}, no a "
                f"{folder.split('/')[0]} (CN-02): escribe la nota allí o deja que el "
                "tipo se derive de la carpeta"
            )
    return problemas


def generate_frontmatter(
    title: str,
    tags: Optional[List[str]] = None,
    meta: Optional[Dict[str, Any]] = None,
    existing_id: Optional[str] = None,
    existing_created: Optional[str] = None,
    norm_refs: Optional[List[str]] = None,
    folder: str = "",
) -> str:
    """El único autor del frontmatter — AP-46, AP-12, AP-13 y CN-02 a la vez.

    AP-46 dice que veintiséis tools montan el bloque concatenando líneas; esta
    función es la que no hay que duplicar. De ahí cuelgan las otras tres:
    AP-12 —el mismo juego de campos para todas las notas del mismo tipo— se
    cumple porque el bloque se arma en un solo sitio; AP-13 —timestamps ISO
    8601 completos— porque las fechas salen de `utcnow()` y no de quien llame;
    y CN-02 porque `type` se deriva de la carpeta con `tipo_por_carpeta()`, que
    es lo que ancla la nota a su sección canónica.

    Generate YAML frontmatter with v37-compliant metadata (type + status + CIA
    + agent + norm_refs).
    """

    meta = dict(meta or {})

    pisados = sorted(set(meta) & set(CAMPOS_DEL_WRITE_PATH))
    if pisados:
        raise ValueError(
            f"meta no puede fijar {pisados}: los decide el write path (CN-01, AP-13)"
        )

    # AP-38 — normalizar antes de escribir, no auditar después.
    #
    # CN-03 audita `status` contra `STATUS_VOCAB` desde v38, y aun así en el
    # parque real hay 54 valores distintos de los que solo el 6% es canónico.
    # El motivo es estructural: `status` llegaba aquí dentro de `meta` y salía
    # tal cual por el bucle genérico del final, sin pasar por ningún control, y
    # el audit que lo habría detectado no lo ejecuta nadie. Se corrige en el
    # único punto por el que pasa toda escritura.
    status_note = None
    if "status" in meta:
        canonico, status_note, _regla = normalize_status(meta["status"])
        if canonico is None:
            raise ValueError(
                f"status {meta['status']!r} no pertenece al vocabulario canónico "
                f"(CN-03) ni se puede derivar de él. Usa uno de "
                f"{sorted(STATUS_VOCAB)} — inventar un estado lo propaga a cada "
                f"nota que lo copie."
            )
        meta["status"] = canonico

    # AP-46: aquí se deciden los campos y su orden; el bloque y su escapado
    # los escribe el dueño del núcleo.
    fm = Frontmatter()

    # AP-56, la mitad preventiva. `yaml_scalar` cita solo si hace falta, y el
    # criterio de "hace falta" es que el parser real no devuelva el mismo texto
    # (AP-44). Sin esto, un título con `: ` dejaba la nota **entera** sin
    # frontmatter para el consumidor: el bloque se ve al abrir el fichero, y
    # por eso nadie lo revisa. Lo que ya está escrito así se repara con
    # `vault_frontmatter_heal`; aquí solo se impide que vuelva a nacer.
    fm.set("title", title, texto=True)

    fm.set("id", existing_id or str(uuid.uuid4()))

    fm.set("createdAt", existing_created or utcnow())

    fm.set("updatedAt", utcnow())

    if tags:
        fm.set("tags", tags)

    # v37: type auto-deduced from folder if not provided in meta
    if "type" not in meta and folder:
        deduced = _deduce_type_from_folder(folder)
        if deduced:
            fm.set("type", deduced)

    # v37: status defaults to draft if not provided in meta.
    # v39: se emite siempre en esta posición — antes, un `status` que venía en
    # `meta` salía por el bucle genérico del final y quedaba detrás del CIA y de
    # `agent`. El campo era el mismo pero el orden no, y un formato que depende
    # de por dónde entró el dato no es un formato.
    fm.set("status", str(meta.pop("status", "draft")), texto=True)

    # Lo que el valor original arrastraba y no era estado (progreso, versión en
    # que se resolvió, fecha) se conserva aquí en vez de perderse al normalizar.
    if status_note:
        fm.set("status_note", str(status_note), texto=True)

    if norm_refs:
        fm.set("norm_refs", norm_refs)

    # v27 CIA schema — defaults overridable via meta

    fm.set("cia_integrity", str(meta.pop("cia_integrity", "medium")), texto=True)

    fm.set("cia_availability", str(meta.pop("cia_availability", "medium")), texto=True)

    fm.set("cia_sensitivity", str(meta.pop("cia_sensitivity", "internal")), texto=True)

    fm.set("agent", str(meta.pop("agent", "system")), texto=True)

    # AP-56 completo. Hasta v40.16 `yaml_scalar` se aplicaba **solo** al
    # título, y todo lo demás salía por aquí concatenado en un f-string —
    # exactamente lo que el docstring de `yaml_scalar` describe como el
    # defecto. El campo con el que se midió: `--meta '{"owner":"#infra"}'`
    # escribía `owner: #infra`, que YAML lee como comentario, así que el valor
    # **desaparecía** y el bloque seguía parseando limpio. `_verificar_frontmatter`
    # lo aprobaba y la nota quedaba en disco con el campo evaporado.
    #
    # La pérdida silenciosa era la peor cara, pero no la única: `"1.0"` volvía
    # como float, `"no"` como False, `"007"` como 7 y `"2026-01-01"` como
    # `datetime.date`. El consumidor no leía lo que el agente escribió.
    #
    # El guard de esto medía un solo campo —el literal del título—, que es por lo que
    # la forma estaba cubierta para el título y no existía para el resto del
    # bloque: un guard que vigila una línea no vigila una norma.
    #
    # Un `str` de `meta` es texto aunque tenga forma de fecha; lo demás sale
    # como JSON, que es YAML de flujo válido.
    for key, value in meta.items():
        fm.set(key, value, texto=isinstance(value, str))

    return fm.render()


# El mapa sección→tipo vivía aquí completo y era la cuarta copia del mismo
# dato; las otras tres (dos auditores y el grafo) se habían quedado en 18, 14 y
# 14 secciones, y dos de ellas se contradecían. Ahora lo declara el registro y
# esto solo lo consume: `SECTION_TYPES[seccion][0]` es exactamente lo que este
# write path escribía, valor por valor.


def tipo_por_carpeta(folder: str) -> str:
    """Derive type field value from the vault section folder."""
    if not folder:
        return ""
    from vault_registry import section_default_type

    top = folder.split("/")[0].split("\\")[0]
    return section_default_type(top)


#: superseded_by: `tipo_por_carpeta`. Se conserva el nombre privado —nada se
#: deroga— pero dejó de ser el canónico en v40.8: `vault_onboard`, del contexto
#: de ciclo de vida, lo importaba con el guion bajo por delante.
_deduce_type_from_folder = tipo_por_carpeta


def extract_wiki_links(content: str) -> List[str]:
    """Los wikilinks de la nota — los que Obsidian resuelve, no los que enseña.

    Un `[[ejemplo]]` dentro de un fence es texto que el consumidor pinta tal
    cual: no es una arista del grafo. Contarlo aquí propagaba el error a todo
    lo que cuelga de esta lista —`norm_refs`, el aviso de enlaces fantasma y el
    `wikiLinks` que publica el resultado—, así que la nota que documenta la
    convención de enlaces nacía avisando de destinos que nunca quiso enlazar.
    Qué es código y no un enlace lo decide `vault_lib.strip_code_blocks` (AP-57).
    """
    return RE_WIKILINK.findall(strip_code_blocks(content))


def update_search_index(
    vault_path: str, title: str, content: str, tags: List[str], is_new: bool = True
) -> None:
    """AP-47: la proyección se actualiza en la misma escritura que la nota.

    `search-index.json` es una proyección del disco. Aquí es donde AP-47 se
    impide en vez de detectarse: una escritura que llegue hasta la nota y no
    hasta aquí deja el índice atrás, y a partir de ahí el agente busca sobre un
    mapa viejo. Lock-protected read-modify-write.
    """

    _index_file().parent.mkdir(parents=True, exist_ok=True)

    body = separar_frontmatter(content)[1]

    preview = body.strip()[:200].replace("\n", " ")

    note_entry = {
        "path": vault_path,
        "title": title,
        "preview": preview,
        "tags": tags,
        "updatedAt": utcnow(),
    }

    def _update(index: Dict[str, Any]) -> Dict[str, Any]:
        notes = index.get("notes", [])

        for i, note in enumerate(notes):
            if note.get("path") == vault_path:
                notes[i] = note_entry

                return index

        notes.append(note_entry)

        index["notes"] = notes

        return index

    atomic_update_json(_index_file(), {"notes": []}, _update)


def vault_write(
    folder: str,
    title: str,
    content: str,
    tags: Optional[List[str]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """

    Create or update a note in the vault.



    Args:

        folder: Relative path to vault root (e.g., "01_Projects/ans")

        title: Note title - also determines filename via slugify

        content: Complete Markdown content

        tags: Tags for search and indexing

        meta: Additional frontmatter fields



    Returns:

        Dict with path, id, and operation details

    """

    tags = tags or []

    # Antes de tocar nada: un `--meta` que pisa la identidad, imita un campo con
    # una errata o trae un valor fuera de vocabulario se rechaza entero, con
    # todos sus problemas a la vez (CN-01, CN-02, CN-03, AP-13).
    problemas = problemas_de_meta(meta, folder)
    if problemas:
        return emit_error(
            "vault_write",
            "INVALID_INPUT",
            "--meta rechazado: " + "; ".join(problemas),
            args={"meta_keys": sorted(meta) if isinstance(meta, dict) else None},
        )

    meta = dict(meta or {})

    # Secretos antes que forma (2026-10-01). El escaneo solo ocurría al escribir,
    # detrás de once guardas: una nota con una clave AWS y sin tags volvía
    # AP-26 y el agente, obediente, añadía tags y reintentaba con la clave
    # dentro. Lo primero que tiene que oír es lo que no debe escribir. El
    # criterio es del dueño, `guarda_secretos`; aquí solo se adelanta.
    try:
        guarda_secretos(_raiz() / folder, f"{title}\n{content}")
    except PermissionError as exc:
        if getattr(exc, "causa", None) is None:
            raise
        return emit_fallo("vault_write", exc)

    # Content gate: new notes must pass strict content quality gate (00_System exempt)

    if not _check_content_gate(content, folder):
        reason = _content_gate_reason(content, folder) or "insufficient content"

        return {
            "ok": False,
            "error_code": "content_too_short",
            "error": "content_too_short",
            "norm_code": "AP-11",
            "norm_name": "Skeleton files — frontmatter válido, contenido vacío",
            "message": "AP-11: content rejected - "
            + reason
            + ". If content is not ready, do not create the note.",
        }

    # AP-20 guard: deceptive skeleton — reject if >50% of bullets are empty

    bullets = re.findall(r"^\s*[-*]\s*(.*)", content, re.MULTILINE)

    if bullets:
        empty_bullets = [
            b
            for b in bullets
            if not b.strip() or b.strip() in ("[]", "[[]]", "-", "[ ]")
        ]

        if len(empty_bullets) / len(bullets) > 0.5:
            return {
                "ok": False,
                "error_code": "content_empty_list",
                "error": "content_empty_list",
                "norm_code": "AP-20",
                "norm_name": "Deceptive skeleton (empty-list)",
                "message": f"AP-20: >{int(len(empty_bullets) / len(bullets) * 100)}% of bullets are empty. Fill content before saving.",
            }

    # AP-21 guard: path-anchored wiki-links — reject [[folder/note]] patterns

    # Por el dueño del criterio, no por un regex propio (AP-57): este sitio
    # corría sobre el contenido **crudo**, así que una nota que documenta la
    # sintaxis —`[[carpeta/nota]]` dentro de un fence, que es lo que enseña el
    # propio manifiesto— se rechazaba por incumplir lo que estaba explicando.
    # Las otras dos comprobaciones de AP-21 de este módulo ya usaban esta vía.
    path_links = detect_path_anchored(content)

    if path_links:
        return {
            "ok": False,
            "error_code": "path_anchored_wikilinks",
            "error": "path_anchored_wikilinks",
            "norm_code": "AP-21",
            "norm_name": "Path-anchored wiki-links",
            "message": f"AP-21: path-anchored wiki-links detected: {path_links}. Use [[note-name]] without folder path.",
        }

    # AP-22 guard: unbalanced or empty wiki-link brackets

    bracket_error = _check_bracket_balance(content)

    if bracket_error:
        return {
            "ok": False,
            "error_code": "malformed_wikilinks",
            "error": "malformed_wikilinks",
            "norm_code": "AP-22",
            "norm_name": "Bracket sanity — corchetes desbalanceados o vacíos",
            "message": bracket_error,
        }

    # Mermaid guard: validate syntax in ```mermaid blocks
    mermaid_pattern = r"```mermaid\s*\n(.*?)```"
    mermaid_blocks = re.findall(mermaid_pattern, content, re.DOTALL)
    if mermaid_blocks:
        try:
            # v40.28 — AP-62: la gramática vive en la hoja; el recorrido del
            # vault que la aplica se queda en `vault_mermaid_check`.
            from vault_mermaid_reglas import validate_mermaid

            for block in mermaid_blocks:
                errors = validate_mermaid(block)
                if errors:
                    error_types = [e["type"] for e in errors]
                    return {
                        "ok": False,
                        "error_code": "mermaid_syntax_error",
                        "error": "mermaid_syntax_error",
                        "norm_code": "AP-25",
                        "norm_name": "Mermaid syntax errors",
                        "message": f"AP-25: Errores en diagrama Mermaid: {error_types}. Corregir antes de guardar.",
                        "details": errors[:3],
                    }
        except ImportError:
            pass

    # AP-26 guard: tags required for content notes (not index/system)
    is_index = title.lower().strip() in ("index", "índice", "indice") or "/index" in folder
    is_system = folder.startswith("00_System")
    if not tags and not is_index and not is_system:
        return {
            "ok": False,
            "error_code": "missing_tags",
            "error": "missing_tags",
            "norm_code": "AP-26",
            "norm_name": "Missing tags — toda nota de contenido requiere al menos un tag",
            "message": "AP-26: tags required for content notes. "
            "Provide at least one tag via --tags. Index and system notes exempt.",
        }

    # AP-39: resolver el vocabulario ANTES de escribir. Colapsa lo que es la
    # misma palabra (acentos, mayúsculas, separadores, plural) contra el
    # registro canónico; un término que no está no se rechaza — se admite y se
    # anota más abajo, una vez la escritura está confirmada.
    tags, new_terms = vault_tags.apply_vocabulary(tags)

    # AP-16 guard: agent field required
    if not meta.get("agent") and not is_system:
        agent_env = _env("VAULT_AGENT")
        if agent_env:
            meta["agent"] = agent_env
        else:
            return {
                "ok": False,
                "error_code": "missing_agent",
                "error": "missing_agent",
                "norm_code": "AP-16",
                "norm_name": "Missing agent attribution",
                "message": "AP-16: agent field required for content notes. "
                "Set --meta '{\"agent\":\"my-agent\"}' or VAULT_AGENT env var. "
                "System notes (00_System/) exempt.",
            }

    # Determine filename and validate path stays inside vault

    filename = f"{slugify(title)}.md"

    # Nombre reservado: el index.md de cada carpeta es del generador. Una nota que se
    # llame igual no convive con él — es el mismo fichero, también con otra
    # capitalización en Windows/macOS — y la siguiente regeneración la pisa
    # dejando el contenido solo en un backup oculto. Se rechaza antes de
    # escribir nada, con el criterio del dueño canónico.
    if es_nombre_reservado(filename):
        return {
            **emit_error(
                "vault_write", "RESERVED_NAME",
                f"El título '{title}' produce '{filename}': "
                f"{describir_reserva(filename)}. Usar otro título.",
            ),
            "error": "RESERVED_NAME",
        }

    vault_path = _nota_heredada(_raiz() / folder / filename, title)

    try:
        assert_within_vault(vault_path, _raiz())

    except ValueError as exc:
        return {
            "ok": False,
            "error_code": "INVALID_PATH",
            "error": "INVALID_PATH",
            "message": str(exc),
        }

    bloqueo = fuera_de_sesion("vault_write", vault_path)
    if bloqueo:
        return bloqueo

    existing_id = None

    existing_created = None

    existing_status = None

    existing_content = ""

    # If note exists, backup to history

    if vault_path.exists():
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")

        history_filename = (
            f"{folder.replace('/', '__')}__{slugify(title)}-{timestamp}.md"
        )

        history_path = _history_dir() / history_filename

        _history_dir().mkdir(parents=True, exist_ok=True)

        existing_content = vault_path.read_text(encoding="utf-8")

        atomic_write_text(history_path, existing_content)

        # AP-41 — la identidad de la nota se lee AQUÍ, en la rama en la que la
        # nota existe.
        #
        # Esta extracción vivía en el `else` de abajo, es decir en la rama en la
        # que la nota **no** existe y `existing_content` es la cadena vacía: la
        # regex no encontraba nada nunca. Consecuencia medida en el sandbox: cada
        # actualización acuñaba un `id` nuevo y reseteaba `createdAt`, así que la
        # nota perdía su identidad en cada escritura y ninguna referencia por id
        # sobrevivía. El campo estaba en el frontmatter, el código para leerlo
        # estaba escrito, y no se ejecutaba jamás.
        fm_previo, _ = parse_frontmatter_with_body(existing_content)
        fm_previo = fm_previo or {}
        existing_id = str(fm_previo.get("id") or "") or None
        # `createdAt` vuelve del parser como `...+00:00` cuando en disco estaba
        # como `...000Z`: se re-canoniza para que releer y reescribir no cambie
        # la forma del campo.
        existing_created = canonical_utc(fm_previo.get("createdAt")) or None
        existing_status = str(fm_previo.get("status") or "") or None

    # Check if note exists in a different folder (auto-move suggestion)
    else:
        search_index = _raiz() / "99_Index" / "search-index.json"
        if search_index.exists():
            try:
                import json as json_module

                index_data = json_module.loads(search_index.read_text(encoding="utf-8"))
                note_stem = slugify(title)
                # Los dos nombres que este título ha tenido (CN-01, v40.35):
                # una nota escrita con el slug viejo en otra carpeta es la
                # misma nota y también se detecta.
                stems = {note_stem, _slug_heredado(title)}
                for note in index_data.get("notes", []):
                    # El stem se **deriva de la ruta**, que es un campo que el
                    # índice sí escribe. Esto comparaba `note.get("stem")`, una
                    # clave que ningún escritor emite —`update_search_index`
                    # escribe path/title/preview/tags/updatedAt—, así que el
                    # guard llevaba muerto desde que se escribió: crear la
                    # misma nota en dos carpetas producía dos notas duplicadas
                    # en silencio, que es justo lo que este bloque impide.
                    # Es la misma forma que la nota de AP-39 describe para
                    # `registry["tags"]`: código escrito contra una clave
                    # inexistente. Derivar de lo que hay evita estrenar un
                    # campo que los índices ya escritos no tendrían.
                    if Path(note.get("path", "")).stem.lower() in stems:
                        current_path = note.get("path", "")
                        if current_path and Path(current_path).parent.as_posix() != Path(folder).as_posix():
                            return {
                                "ok": False,
                                "error_code": "note_moved",
                                "error": "note_moved",
                                "message": f"La nota existe en: {current_path}. Usar vault_move para reubicarla o especificar otra carpeta.",
                                "suggestion": f'python scripts/vault_move.py --from "{current_path}" --to "{folder}/{note_stem}.md"',
                                "current_path": current_path,
                            }
            except (OSError, json.JSONDecodeError, ValueError) as e:
                # AP-51: el índice ilegible no se presenta como "no hay nota
                # duplicada". Se sigue —la escritura es válida— pero se dice.
                print(
                    json.dumps({
                        "warning": "search_index_unreadable",
                        "detail": f"{type(e).__name__}: {e}",
                        "impact": "no se pudo comprobar si la nota existe en otra carpeta",
                    }, ensure_ascii=False),
                    file=sys.stderr,
                )

        # La extracción del frontmatter previo estaba aquí, dentro de la rama en
        # la que la nota no existe: no había nada que extraer. Vive ahora en la
        # rama de arriba (AP-41), con el parser compartido en vez de una regex
        # propia — dos lectores del mismo campo es lo que ya costó una vez.

    # ── AP-41: la máquina de estados se verifica, no solo se declara ──────────
    #
    # `STATUS_TRANSITIONS` estaba escrita y bien formada desde v38, y su único
    # consumidor en todo el repo era su propio test de coherencia: nadie la
    # recorría. Un estado que no controla su transición es una etiqueta, no un
    # ciclo de vida — `archived` podía volver a `draft` sin que nada lo viera.
    if existing_status:
        # Una actualización que no menciona `status` no lo está cambiando. Antes
        # caía al default `draft` de generate_frontmatter, así que tocar una nota
        # `verified` para corregir una frase la degradaba a borrador en silencio.
        if "status" not in meta:
            meta["status"] = existing_status
        else:
            previo, _n, _r = normalize_status(existing_status)
            destino, _n2, _r2 = normalize_status(meta["status"])
            # Si el estado previo no es canónico (deuda anterior a AP-38) no hay
            # máquina que recorrer: se deja pasar y lo reporta el audit.
            if previo and destino and previo != destino:
                permitidos = STATUS_TRANSITIONS.get(previo, set())
                if destino not in permitidos:
                    return {
                        "ok": False,
                        "error_code": "illegal_status_transition",
                        "error": "illegal_status_transition",
                        "norm_code": "AP-41",
                        "norm_name": "Máquina de estados declarada sin verificar",
                        "message": (
                            f"AP-41: transición {previo!r} -> {destino!r} no está en "
                            f"STATUS_TRANSITIONS. Desde {previo!r} solo se puede pasar a "
                            f"{sorted(permitidos) or ['(ninguno: estado terminal)']}. "
                            f"Si el salto es correcto, la que está mal es la máquina: "
                            f"corrígela en vault_norms.STATUS_TRANSITIONS, no la nota."
                        ),
                        "from_status": previo,
                        "to_status": destino,
                        "allowed": sorted(permitidos),
                    }

    # Create folder if not exists

    vault_path.parent.mkdir(parents=True, exist_ok=True)

    # Compute applicable norm_refs before generating frontmatter

    wiki_links = extract_wiki_links(content)

    norm_refs = compute_norm_refs(folder, content, wiki_links)

    # AP-23 advisory: note exceeds complexity ceiling

    line_count = len(content.split("\n"))

    ap23_warning = line_count > 500

    # Generate frontmatter and write file (with file lock to prevent concurrent write data loss)

    # El id se decide aquí, una sola vez, y es el que va al frontmatter Y al
    # resultado. Antes `generate_frontmatter` acuñaba un uuid4 y el resultado
    # acuñaba otro: el id que la tool devolvía no era el de la nota, así que
    # cualquier agente que lo guardara guardaba una referencia inexistente.
    nota_id = existing_id or str(uuid.uuid4())

    frontmatter = generate_frontmatter(
        title, tags, meta, nota_id, existing_created, norm_refs, folder
    )

    final_content = f"{frontmatter}\n\n{content}"

    # Con `/` siempre, como escribe el dueño (`RepositorioIndices.relativa`).
    # Hasta aquí iba `str(relative_to)`: en Windows el índice recibía
    # `07_Knowledge\nota.md`, y `vault_context_pack`, que separa la sección con
    # `split("/")`, descartaba toda coincidencia léxica en cuanto la consulta
    # inducía una sección — «cómo funciona X» devolvía un paquete vacío.
    rel_path = vault_path.relative_to(_raiz()).as_posix()

    with file_lock(vault_path, timeout=10.0):
        atomic_write_text(vault_path, final_content)

        # Update search index (inside lock for consistency)

        update_search_index(
            rel_path,
            title,
        content,
        tags,
        is_new=(existing_id is None),
    )

    # El índice de sección ya se regeneró **dentro** de la escritura:
    # `atomic_write_text` llama a `vault_io._auto_section_index(path)` en este
    # mismo proceso y con la raíz activa.
    #
    # Aquí vivía además un `subprocess.Popen` que lanzaba
    # `vault_section_index.py` con la ruta derivada de `__file__` (AP-36) y sin
    # pasarle `VAULT_ROOT` ni `--root`: el hijo **volvía a autodetectar** el
    # vault. Si el padre había fijado el destino con `set_vault_root()` —tools
    # con `--root`, la CLI, los tests con `tmp_path`—, la nota se escribía en un
    # vault y el `index.md`, el `vault-hub.md` y el `vault-commands.md` se
    # generaban en otro; si en el hijo la detección caía en
    # `repo_root_fallback`, ese otro era la raíz de este repo. Con los dos
    # `DEVNULL` y el `except Exception: pass` alrededor, era inobservable por
    # construcción: ninguna prueba podía verlo desde dentro.
    #
    # No se sustituye por una versión con el entorno propagado porque no había
    # nada que propagar: el trabajo ya estaba hecho, y lo único que el
    # subproceso podía aportar era hacerlo en el vault equivocado.

    # AP-39: la nota ya está en disco, así que el término existe de verdad.
    # Anotarlo antes habría dejado en la bitácora palabras de escrituras que
    # fallaron — memoria de algo que nunca se escribió.
    introduced = 0
    if new_terms:
        for t in new_terms:
            t["note"] = rel_path
            t["agent"] = meta.get("agent", "") or _env("VAULT_AGENT")
        try:
            introduced = vault_tags.record_new_tags(new_terms)
        except OSError:
            # La bitácora no puede tumbar una escritura válida: se registra el
            # fallo en el resultado y el audit de AP-39 lo recoge después.
            introduced = -1

    tag_suggestions = _tag_suggestions(tags)

    # Se pasa la nota que se está escribiendo: un `[[../otra]]` se resuelve
    # contra su carpeta, no contra la raíz (AP-57, el dueño es `vault_lib`).
    ghost_links = _collect_ghost_links(wiki_links, Path(rel_path))

    result: Dict[str, Any] = {
        "ok": True,
        **write_report(),
        "path": rel_path,
        "id": nota_id,
        "filename": filename,
        "tags": tags,
        "wikiLinks": wiki_links,
        "norm_refs": norm_refs,
        "created": existing_id is None,
        "message": f"Note {'created' if existing_id is None else 'updated'} successfully",
    }

    if existing_status and meta.get("status") and existing_status != meta["status"]:
        result["status_transition"] = f"{existing_status} -> {meta['status']}"

    if ap23_warning:
        result["ap23_warning"] = (
            f"AP-23: note has {line_count} lines — consider splitting into sub-notes (threshold: 500)"
        )

    if ghost_links:
        result["ghost_links"] = ghost_links

    if tag_suggestions:
        result["tag_suggestions"] = tag_suggestions

    if new_terms:
        result["vocabulary_introduced"] = [t["tag"] for t in new_terms]
        result["vocabulary_recorded"] = introduced

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Vault Write Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_write.py --folder "01_Projects/mi-api" --title "Status" --content "# Status\\n\\nActivo"

  python vault_write.py --folder "03_Decisions" --title "ADR-001" --tags arch backend --meta '{"status":"accepted"}'

  python vault_write.py --folder "03_Decisions" --title "ADR-001" --content "..." --meta-file meta.json

  python vault_write.py --folder "07_Knowledge/concepts" --scan-path "docs/concepts/"



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Con --scan-path, --title y --content son opcionales

  - Solo se procesan archivos .md en --scan-path

""",
        allow_abbrev=False,
    )

    parser.add_argument(
        "--folder", required=True, help="Folder path relative to vault root"
    )

    parser.add_argument(
        "--title", help="Note title (optional when --scan-path is used)"
    )

    parser.add_argument(
        "--content",
        help="Markdown content (use @file:path to read from file; optional when --scan-path is used)",
    )

    parser.add_argument("--tags", nargs="*", help="Tags for search")

    parser.add_argument(
        "--meta", type=json.loads, help="Additional frontmatter as JSON"
    )

    parser.add_argument(
        "--meta-file",
        help="Path to JSON file with additional frontmatter (avoids shell quoting issues)",
    )

    parser.add_argument(
        "--scan-path",
        help="Directory to scan for .md files and write each one to --folder",
    )

    args = parser.parse_args()

    # --scan-path mode: scan directory for .md files

    if args.scan_path:
        scan_dir = Path(args.scan_path)

        if not scan_dir.exists():
            print(
                json.dumps(
                    emit_error("vault_write", "FOLDER_NOT_FOUND", f"scan-path not found: {args.scan_path}"),
                    ensure_ascii=False,
                )
            )

            return 1

        md_files = list(scan_dir.rglob("*.md"))

        written = []

        skipped = []

        meta = args.meta

        if args.meta_file:
            with open(args.meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)

        for md_file in md_files:
            try:
                file_content = md_file.read_text(encoding="utf-8")

            except Exception as e:
                skipped.append({"file": str(md_file), "reason": str(e)})

                continue

            # Extract title from first # Heading or use filename

            heading_match = re.search(r"^#\s+(.+)$", file_content, re.MULTILINE)

            title = (
                heading_match.group(1).strip()
                if heading_match
                else md_file.stem.replace("-", " ").replace("_", " ").title()
            )

            # Check if note already exists

            filename = f"{slugify(title)}.md"

            vault_path = _nota_heredada(_raiz() / args.folder / filename, title)

            if vault_path.exists():
                skipped.append(
                    {"file": str(md_file), "reason": "already exists in vault"}
                )

                continue

            result = vault_write(args.folder, title, file_content, args.tags, meta)

            if result["ok"]:
                written.append(result["path"])

            else:
                skipped.append(
                    {"file": str(md_file), "reason": result.get("error", "unknown")}
                )

        scan_result = {
            "ok": True,
            "scanned": len(md_files),
            "written": written,
            "skipped": skipped,
        }

        print(json.dumps(scan_result, indent=2, ensure_ascii=False))

        return 0

    # Standard single-note mode

    if not args.title:
        parser.error("--title is required when --scan-path is not used")

    if not args.content:
        parser.error("--content is required when --scan-path is not used")

    # Read content from file if @file:path

    if args.content.startswith("@file:"):
        file_path = Path(args.content[6:])

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

    else:
        content = args.content

    # Sanitize title and content to fix encoding issues from IA or cross-platform
    title = args.title
    if title:
        title, title_fixes = sanitize_content(title, dry_run=False)
        if title_fixes:
            # `error: "encoding_issue_in_title"` era un código de error
            # inventado en el sitio: la forma exacta que AP-52 persigue. El
            # catálogo ya tenía `ENCODING_ERROR`, y `fixes` y `suggestion` —que
            # son lo accionable— se conservan intactos junto al envelope.
            result = {
                **emit_error(
                    "vault_write",
                    "ENCODING_ERROR",
                    "El título contiene caracteres problemáticos que fueron corregidos.",
                ),
                "fixes": title_fixes,
                "suggestion": f"Usa el título corregido: {title}",
            }
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 1

    if content:
        content, content_fixes = sanitize_content(content, dry_run=False)
        # Log fixes but continue (content fixes are auto-applied)
        if content_fixes:
            pass  # Already logged in sanitize_content -> atomic_write_text

    meta = args.meta

    if args.meta_file:
        with open(args.meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

    # D5: los guards de contenido devuelven el envelope a mano; sale canónico.
    result = completar_envelope(
        "vault_write", vault_write(args.folder, title, content, args.tags, meta))

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_write"))
