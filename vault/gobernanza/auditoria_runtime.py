"""Auditoría de un runtime documental, independiente del repositorio estándar.

Este servicio examina únicamente los datos del vault consumidor. La fachada
legacy vault_norms compone, en el punto histórico del resultado, las
observaciones que sí pertenecen al estándar: contrato CLI, smoke y cobertura.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from ..kernel import construir
from ..kernel.contenido import cuerpo_sin_marcadores
from .repositorio import RepositorioGobernanza

_ES_PRIMER = re.compile(r"^\d{2}-\d{2}_.*-primer$")
_ADR_TYPES = ("decision", "adr")
_VAULT_ARTIFACT_NAMES = ("00_System", "99_Index", "vault-backups", ".history")
_CONTAMINATION_DEPTH = 2

__all__ = ["auditar_runtime"]


def _repo(root: str | Path | None = None) -> RepositorioGobernanza:
    return RepositorioGobernanza(construir(root))


def _raiz() -> Path:
    return _repo().raiz


def auditar_runtime(
    root: Optional[Path] = None,
    *,
    insertar_checks_estandar: Callable[[Callable[[str, str, str], None]], None] | None = None,
) -> Dict[str, Any]:
    """Audita sólo estructura, contenido y artefactos del runtime.

    La callback existe exclusivamente para que la fachada histórica pueda
    conservar el orden de sus observaciones del estándar. El camino de runtime
    no la proporciona y nunca importa vault_norms, vault_smoke ni vault_voice.
    """
    from datetime import datetime, timezone

    import yaml

    from vault_io import is_snapshot_path, normalize_stem
    from vault_lib import (
        extract_wikilinks,
        parse_frontmatter_with_body,
        read_frontmatter as _leer_frontmatter,
    )
    from vault_norms_catalog import NORM_CATALOG, STATUS_TRANSITIONS, STATUS_VOCAB, normalize_status
    from vault_registry import NON_SECTION_ROOT_FOLDERS, SECTIONS

    root_allowed = set(NON_SECTION_ROOT_FOLDERS)
    root = (root or _raiz()).resolve()
    canonical_sections = {s["folder"] for s in SECTIONS}
    violations: List[Dict[str, Any]] = []

    def _flag(norm: str, path: str, detail: str) -> None:
        n = next((x for x in NORM_CATALOG if x["code"] == norm), {})
        violations.append(
            {
                "norm": norm,
                "severity": n.get("severity", "medium"),
                "path": path,
                "detail": detail,
            }
        )

    # ── AP-15 + CN-02: higiene de raíz ────────────────────────────────────────
    if root.exists():
        for entry in sorted(root.iterdir()):
            name = entry.name
            if name.startswith(".") and name in root_allowed:
                continue
            if entry.is_dir():
                if name not in canonical_sections and name not in root_allowed:
                    _flag(
                        "CN-02",
                        name,
                        f"Carpeta '{name}' en la raíz no es una sección canónica "
                        f"({len(canonical_sections)} secciones válidas en vault_registry).",
                    )
            elif not name.startswith("."):
                _flag("AP-15", name, f"Archivo suelto '{name}' en la raíz del vault.")

    # ── AP-47: el índice refleja el disco ─────────────────────────────────────
    # Se delega en `vault_reindex.index_coherence`, que es quien define qué
    # cuenta como nota indexable, en vez de recontar aquí con el criterio del
    # audit —que excluye `10_Migrated/` y las instantáneas—. Dos criterios para
    # "cuántas notas hay" darían un desfase que `vault_reindex` no arreglaría
    # nunca, porque no es el que él mide (AP-44). Un solo hallazgo por vault: el
    # desfase es del índice, no de cada nota que falta en él.
    if root.exists():
        try:
            from vault.indices.coherencia import coherencia_indice
            from vault.indices.repositorio import RepositorioIndices

            coherencia = coherencia_indice(RepositorioIndices(_repo(root).ctx))
            if not coherencia["ok"]:
                detalle = {
                    "index_missing": "No existe 99_Index/search-index.json.",
                    "index_corrupt": "99_Index/search-index.json no parsea.",
                }.get(
                    coherencia["status"],
                    f"{coherencia.get('missing_count', 0)} nota(s) en disco fuera "
                    f"del índice y {coherencia.get('stale_count', 0)} entrada(s) "
                    f"que ya no existen "
                    f"({coherencia['on_disk']} en disco / {coherencia['indexed']} "
                    f"indexadas).",
                )
                _flag(
                    "AP-47",
                    "99_Index/search-index.json",
                    f"{detalle} La búsqueda no ve lo que hay escrito, así que el "
                    f"agente lo vuelve a escribir. Remedio: `vault_reindex`.",
                )
        except ImportError:
            pass  # sin la tool no hay nada que contrastar

    # ── Cargar notas una sola vez ─────────────────────────────────────────────
    notes: Dict[str, Dict[str, Any]] = {}
    for md in sorted(root.rglob("*.md")):
        rel = str(md.relative_to(root)).replace("\\", "/")
        if rel.startswith(("10_Migrated/", ".")) or "/.history/" in rel:
            continue
        if is_snapshot_path(rel):
            continue
        try:
            raw = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        # ── AP-46: frontmatter construido a mano y nunca releído ──────────────
        # Se mira el texto CRUDO a propósito: `parse_frontmatter_with_body`
        # devuelve `{}` tanto para "no tiene frontmatter" como para "lo tiene y
        # está roto", y esa indistinción es justamente lo que dejó a
        # `vault_migrate_docs` publicando bloques sin cerrar. El criterio es el
        # del consumidor —`yaml.safe_load`—, no un regex por líneas (AP-44).
        if raw.startswith("---"):
            resto = raw.split("\n", 1)[1] if "\n" in raw else ""
            corte = resto.find("\n---")
            if corte == -1 and not resto.startswith("---"):
                _flag(
                    "AP-46",
                    rel,
                    "Frontmatter abierto con '---' que nunca cierra: la nota "
                    "entera se lee como metadatos y su cuerpo desaparece para "
                    "quien la consuma.",
                )
            else:
                try:
                    yaml.safe_load(resto[: corte + 1] if corte != -1 else "")
                except Exception as exc:
                    _flag(
                        "AP-46",
                        rel,
                        f"Frontmatter que no parsea como YAML "
                        f"({type(exc).__name__}): lo escribió una tool "
                        f"concatenando líneas y nadie releyó el resultado.",
                    )

        try:
            fm, body = parse_frontmatter_with_body(raw)
        except (OSError, UnicodeDecodeError):
            continue
        notes[rel] = {"fm": fm or {}, "body": body}

    inbound: Dict[str, int] = {}
    for rel, info in notes.items():
        for link in extract_wikilinks(info["body"]):
            inbound[link.split("|")[0].strip().lower()] = (
                inbound.get(link.split("|")[0].strip().lower(), 0) + 1
            )

    for rel, info in notes.items():
        fm, body = info["fm"], info["body"]
        note_type = str(fm.get("type", "")).lower()
        status = str(fm.get("status", "")).lower()
        stem = Path(rel).stem.lower()

        # ── CN-03: vocabulario de status ──────────────────────────────────────
        if status and status not in STATUS_VOCAB:
            _flag("CN-03", rel, f"status '{status}' fuera del vocabulario canónico {sorted(STATUS_VOCAB)}.")

        # ── AP-45: cobertura sin evidencia ────────────────────────────────────
        # Detectable sin ambigüedad: el cuerpo, quitados encabezados y
        # marcadores de pendiente, queda vacío Y no hay un solo wikilink
        # saliente. Las dos condiciones juntas, porque cada una por separado
        # tiene usos legítimos: una nota puede ser un índice de puros enlaces
        # sin prosa, y un apunte corto puede no enlazar todavía con nada.
        #
        # Dos exenciones, ambas por declararse:
        #   `status: template` — los primers de vault_init son andamiaje que
        #   anuncia lo que es, y eso es lo contrario del relleno.
        #   `index` — los índices de sección los genera vault_section_index a
        #   partir de lo que hay; uno vacío refleja una sección vacía, que ya
        #   es el estado honesto.
        if status != "template" and note_type != "index" and stem != "index":
            if not extract_wikilinks(body):
                residuo = cuerpo_sin_marcadores(body)
                if not residuo:
                    _flag(
                        "AP-45",
                        rel,
                        "Cuerpo sin contenido ni enlaces: solo encabezados y "
                        "marcadores de pendiente. Una sección vacía es un hueco "
                        "visible; esta nota lo tapa sin llenarlo. Bórrala o "
                        "escribe lo que afirma.",
                    )

        # ── AP-09: runbooks fuera de 08_Runbooks ──────────────────────────────
        if note_type == "runbook" and not rel.startswith("08_Runbooks/"):
            _flag("AP-09", rel, "Nota type:runbook fuera de 08_Runbooks/.")

        # ── AP-07: ADRs incompletos ───────────────────────────────────────────
        # No toda nota de 03_Decisions/ es un ADR: la sección aloja también
        # primers y guías de uso, a las que exigir "Contexto/Decisión/
        # Consecuencias" no las mejora — las deforma. Una nota queda fuera solo
        # si DECLARA un `type` ajeno a la decisión; sin `type` sigue tratándose
        # como ADR, para que omitir el campo no sea la vía de escape del guard.
        es_adr = note_type in _ADR_TYPES or not note_type or stem.startswith("adr-")
        if (
            rel.startswith("03_Decisions/")
            and stem != "index"
            and es_adr
            and status not in ("stub", "template")  # stubs se rigen por AP-03
        ):
            required = {
                "Contexto": "context",
                "Decisión": "decisi",
                "Consecuencias": "consecuen|consequence",
            }
            lower_body = body.lower()
            missing = [
                name
                for name, pat in required.items()
                if not re.search(rf"^#+.*({pat})", lower_body, re.MULTILINE | re.IGNORECASE)
            ]
            if missing or not status:
                problems = []
                if missing:
                    problems.append(f"secciones faltantes: {', '.join(missing)}")
                if not status:
                    problems.append("sin campo status")
                _flag("AP-07", rel, "ADR incompleto — " + "; ".join(problems) + ".")

        # ── AP-06: templates sin instancias (sin inbound links) ──────────────
        if note_type == "template" or "template" in [str(t).lower() for t in fm.get("tags", []) or []]:
            if inbound.get(stem, 0) == 0:
                _flag("AP-06", rel, "Template sin inbound links — sin instancias que lo usen.")

        # ── AP-19: shadow indexing ────────────────────────────────────────────
        if (
            "index" in stem
            and stem != "index"
            and not rel.startswith("99_Index/")
            and stem not in ("master-index",)
        ):
            _flag("AP-19", rel, f"Nota índice paralela '{rel}' fuera de 99_Index/ (shadow indexing).")

    # ── AP-39: vocabulario abierto sin memoria ────────────────────────────────
    # Dos señales distintas, y conviene no confundirlas: familias de variantes
    # tipográficas del mismo término (lo que el guard de escritura ya colapsa a
    # partir de ahora, y que aquí solo aparece como deuda anterior), y términos
    # fuera del registro canónico que nadie anotó en la bitácora — el olvido
    # propiamente dicho.
    try:
        from vault.indices.repositorio import RepositorioIndices
        from vault.indices.vocabulario import (
            cargar_bitacora,
            etiquetas_canonicas,
            normalizar_etiqueta,
            singularizar_etiqueta,
        )

        indices = RepositorioIndices(_repo(root).ctx)

        familias: Dict[str, Dict[str, List[str]]] = {}
        for rel, info in notes.items():
            crudos = info["fm"].get("tags") or []
            if isinstance(crudos, str):
                crudos = [t.strip() for t in crudos.split(",") if t.strip()]
            for crudo in crudos:
                norma = normalizar_etiqueta(str(crudo))
                if not norma:
                    continue
                familias.setdefault(singularizar_etiqueta(norma), {}).setdefault(
                    str(crudo), []
                ).append(rel)

        for raiz, variantes in sorted(familias.items()):
            if len(variantes) > 1:
                muestra = ", ".join(f"'{v}'" for v in sorted(variantes)[:4])
                notas = sorted({r for v in variantes.values() for r in v})
                _flag(
                    "AP-39",
                    notas[0],
                    f"{len(variantes)} variantes del mismo término '{raiz}' ({muestra}) "
                    f"en {len(notas)} nota(s) — correr vault_tags --rename para unificar.",
                )

        canonicos_norm = {
            normalizar_etiqueta(t) for t in etiquetas_canonicas(indices)
        }
        anotados = {e["tag"] for e in cargar_bitacora(indices).get("entries", [])}
        sin_memoria = sorted(
            raiz
            for raiz, variantes in familias.items()
            if raiz not in canonicos_norm
            and not any(normalizar_etiqueta(v) in canonicos_norm for v in variantes)
            # La bitácora guarda la forma normalizada, no la raíz en singular:
            # comparar solo contra `raiz` daría por no anotado todo plural.
            and raiz not in anotados
            and not any(normalizar_etiqueta(v) in anotados for v in variantes)
        )
        if sin_memoria:
            muestra = ", ".join(f"'{t}'" for t in sin_memoria[:6])
            _flag(
                "AP-39",
                "19_Audits/vocabulary/tag-ledger.json",
                f"{len(sin_memoria)} término(s) en uso que no son canónicos ni constan "
                f"en la bitácora ({muestra}) — vocabulario introducido sin dejar rastro "
                f"de quién ni cuándo. Correr vault_tags --backfill-ledger para anotarlos.",
            )
    except ImportError:
        pass

    # AP-40, AP-42 y AP-43 observan el estándar, no este runtime.
    # La fachada legacy los intercala aquí para conservar su orden histórico.
    if insertar_checks_estandar is not None:
        insertar_checks_estandar(_flag)

    # ── AP-44: enlaces que resuelven para la tool pero no para el lector ──────
    # El sintoma automatizable de la verificacion autoconsistente. Obsidian
    # resuelve `[[X]]` por nombre de fichero o por `aliases:`, NUNCA por `title:`.
    # Una tool que indexe por titulo da el enlace por bueno y no lo reporta; el
    # usuario abre el vault y ve un enlace muerto. La diferencia entre ambos
    # criterios es exactamente esta lista: enlaces invisibles para el estandar y
    # rotos para quien lee. En BuilderX eran 46.
    #
    # La reparacion correcta es anadir el titulo a `aliases:` en el destino, no
    # reescribir cada punto de llamada: el texto legible del enlace es contenido,
    # y sustituirlo por un slug degrada la nota para arreglar una metrica.
    try:
        _por_nombre: Set[str] = set()
        _por_titulo: Dict[str, str] = {}
        _vivas = [
            p for p in root.rglob("*.md") if not is_snapshot_path(p.relative_to(root))
        ]
        for _n in _vivas:
            _por_nombre.add(normalize_stem(_n.stem))
            _fm = _leer_frontmatter(_n) or {}
            _al = _fm.get("aliases") or _fm.get("alias") or []
            if isinstance(_al, str):
                _al = [_al]
            for _a in _al:
                if isinstance(_a, str) and _a.strip():
                    _por_nombre.add(normalize_stem(_a))
            _t = _fm.get("title")
            if isinstance(_t, str) and _t.strip():
                _por_titulo.setdefault(normalize_stem(_t), _n)

        for _n in _vivas:
            try:
                _txt = _n.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            _rel = str(_n.relative_to(root)).replace("\\", "/")
            for _m in re.finditer(r"\[\[([^\]|#]+)", _txt):
                _dest = _m.group(1).strip()
                _clave = normalize_stem(_dest)
                if _clave in _por_nombre or _clave not in _por_titulo:
                    continue
                _destino = str(_por_titulo[_clave].relative_to(root)).replace("\\", "/")
                _flag(
                    "AP-44",
                    _rel,
                    f"[[{_dest}]] solo resuelve por el `title:` de `{_destino}`: "
                    "Obsidian no mira ese campo, asi que el enlace esta roto para "
                    f"quien lee. Anade `{_dest}` a los `aliases:` del destino.",
                )
    except (OSError, ValueError):
        pass

    # ── AP-41: transiciones de estado ya ocurridas ────────────────────────────
    # El guard de vault_write solo puede detener las futuras. Lo ya escrito está
    # en `.history/`: cada versión guardada es el estado anterior de la nota, así
    # que la secuencia de `status` a lo largo del historial es la traza real de
    # la máquina. Se reporta, no se corrige: el estado actual es un hecho y el
    # camino irregular es justamente la información que interesa.
    historia = root / ".history"
    if historia.is_dir():
        # `<carpeta>__<slug>-<YYYY-MM-DDTHH-MM-SS>.md`
        _re_hist = re.compile(r"^(?P<base>.+)-(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})\.md$")
        secuencias: Dict[str, List[Tuple[str, str]]] = {}
        for version in historia.glob("*.md"):
            m = _re_hist.match(version.name)
            if not m:
                continue
            try:
                fm, _ = parse_frontmatter_with_body(version.read_text(encoding="utf-8"))
            except OSError:
                continue
            estado = str((fm or {}).get("status") or "").strip()
            if estado:
                secuencias.setdefault(m.group("base"), []).append((m.group("ts"), estado))

        for base, puntos in sorted(secuencias.items()):
            rel_nota = base.replace("__", "/") + ".md"
            puntos.sort()
            previo = None
            for _ts, estado in puntos:
                canonico, _n, _r = normalize_status(estado)
                if canonico is None:
                    continue  # deuda de vocabulario: la reporta CN-03/AP-38
                if previo and canonico != previo:
                    permitidos = STATUS_TRANSITIONS.get(previo, set())
                    if canonico not in permitidos:
                        _flag(
                            "AP-41",
                            rel_nota,
                            f"Transición ya ocurrida {previo!r} -> {canonico!r} fuera de "
                            f"STATUS_TRANSITIONS (permitidas desde {previo!r}: "
                            f"{sorted(permitidos) or ['ninguna']}). Anterior al guard; "
                            f"se anota, no se reescribe.",
                        )
                previo = canonico

    # ── AP-36: contención e idempotencia ──────────────────────────────────────
    # (a) Artefactos .bak/.tmp dentro de secciones de contenido
    for sec in sorted(canonical_sections):
        sec_path = root / sec
        if not sec_path.is_dir():
            continue
        for artifact in sec_path.rglob("*"):
            if artifact.is_file() and (
                artifact.suffix in (".bak", ".tmp") or artifact.name.startswith(".tmp.")
            ):
                rel_a = str(artifact.relative_to(root)).replace("\\", "/")
                if "/.trash/" in rel_a or "/.history/" in rel_a:
                    continue  # ubicaciones de mantenimiento permitidas
                _flag("AP-36", rel_a, "Artefacto temporal/backup dentro de una sección de contenido.")
        # (b) Toda sección presente debe tener index.md (rastreabilidad de nodos)
        if sec not in ("00_System", "10_Migrated", "99_Index") and not (sec_path / "index.md").exists():
            _flag("AP-36", f"{sec}/", "Sección sin index.md — nodos no indexados (correr vault_section_index).")
        # (b2) index.md con formato legacy: [[stem|alias]] en celdas de tabla
        # (identidad+título fusionados — genera notas en blanco; sanear con --heal)
        for idx in [sec_path / "index.md", *sec_path.glob("*/index.md")]:
            if not idx.exists():
                continue
            try:
                idx_text = idx.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if re.search(r"^\|\s*\[\[[^\]|]+\|[^\]]+\]\]", idx_text, re.MULTILINE):
                rel_i = str(idx.relative_to(root)).replace("\\", "/")
                _flag(
                    "AP-36",
                    rel_i,
                    "Índice con [[stem|alias]] en celdas — formato legacy; correr vault_section_index --heal.",
                )

    # (c) Contaminación externa: artefactos de vault generados FUERA del vault.
    #
    # Hasta v38.1 esto miraba solo root.parent, un único nivel. No bastaba: el
    # patrón legacy Path(__file__).parent.parent.parent (vault_restore) escribe
    # en el ABUELO del directorio de scripts, que en topología spec-repo queda
    # dos niveles por encima del vault. El guard pasaba en verde mientras la
    # carpeta existía. Ahora se recorren _CONTAMINATION_DEPTH niveles.
    seen_contamination: set = set()
    for level in range(1, _CONTAMINATION_DEPTH + 1):
        ancestor = root.parents[level - 1] if len(root.parents) >= level else None
        if ancestor is None:
            break
        for artifact_name in _VAULT_ARTIFACT_NAMES:
            stray = ancestor / artifact_name
            if not stray.exists() or stray == root / artifact_name or stray == root:
                continue
            key = str(stray)
            if key in seen_contamination:
                continue
            seen_contamination.add(key)
            _flag(
                "AP-36",
                f"{'../' * level}{artifact_name}",
                f"'{artifact_name}' existe {level} nivel(es) por encima del vault "
                f"({stray}) — side-effect escrito fuera del vault root.",
            )

    # (d) Vault mal identificado: la raíz del repo usada COMO vault.
    #
    # Cuando _detect_vault_root() no encuentra ningún vault devuelve la raíz del
    # repo. A partir de ahí los artefactos se escriben "dentro del vault" según
    # las tools, pero fuera de todo vault-* en realidad. El audit no podía verlo
    # porque la contaminación cae DENTRO de root: se reportaba como CN-02
    # ("carpeta scripts no es sección canónica"), culpando al repo de no ser un
    # vault en lugar de señalar que el vault fue mal detectado.
    try:
        from vault_io import VAULT_ROOT as _DETECTED_ROOT
        from vault_io import vault_root_origin, vault_root_is_confident

        # Solo aplica cuando se audita el root AUTO-DETECTADO. Con --root
        # explícito el usuario ya declaró cuál es el vault y la confianza de la
        # detección no dice nada sobre él.
        audits_detected_root = root.resolve() == _DETECTED_ROOT.resolve()
        if audits_detected_root and not vault_root_is_confident():
            _flag(
                "AP-36",
                ".",
                f"vault root detectado por '{vault_root_origin()}': no se encontró ningún "
                f"vault y se está usando {root} como si lo fuera. Los artefactos caerían "
                "fuera de todo vault-*. Crea 'vault-<nombre>/' o exporta VAULT_ROOT.",
            )
    except ImportError:
        pass

    # ── AP-10: migración sin plan de rollback ─────────────────────────────────
    migrated = root / "10_Migrated"
    if migrated.exists():
        # El andamiaje de la sección no es contenido migrado: los `index.md` los
        # genera `vault_reindex` en cada subcarpeta y los primers los crea
        # `vault_init`. Contándolos, una sección vacía recién inicializada ya
        # exigía un mapa de rollback de una migración que nunca ocurrió — en
        # BuilderX eran 6 de las 7 "notas migradas". Un rollback de un `index.md`
        # generado no significa nada.
        migrated_notes = [
            p
            for p in migrated.rglob("*.md")
            if not p.name.startswith("_report-")
            and p.stem != "index"
            and not _ES_PRIMER.match(p.stem)
        ]
        reports = list(migrated.glob("_report-*.md"))
        if migrated_notes and not reports:
            _flag(
                "AP-10",
                "10_Migrated/",
                f"{len(migrated_notes)} notas migradas sin _report-*.md (mapa de rollback para vault_migrate_rollback).",
            )

    # ── SP-01: eliminaciones sin change_log ───────────────────────────────────
    graph_file = root / "99_Index" / "graph.json"
    change_log = root / "00_System" / ".change-log.json"
    if graph_file.exists():
        try:
            graph = json.loads(graph_file.read_text(encoding="utf-8"))
            deleted = [e.get("from", "") for e in graph.get("edges", []) if e.get("to") == "__deleted__"]
            if deleted:
                logged: set = set()
                if change_log.exists():
                    try:
                        logged = {
                            str(e.get("path", "")) for e in json.loads(change_log.read_text(encoding="utf-8"))
                        }
                    except (json.JSONDecodeError, TypeError):
                        pass
                for d in deleted:
                    if d not in logged:
                        _flag("SP-01", d, "Nota eliminada sin entrada en change_log (delete protocol).")
        except (json.JSONDecodeError, OSError):
            pass

    by_norm: Dict[str, int] = {}
    for v in violations:
        by_norm[v["norm"]] = by_norm.get(v["norm"], 0) + 1

    return {
        "ok": True,
        "tool": "vault_runtime_audit",
        "vault_root": str(root),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes_scanned": len(notes),
        "total_violations": len(violations),
        "by_norm": by_norm,
        "violations": violations,
    }

# ─── Guard anti-drift del marco de datos (v39) ─────────────────────────────────
