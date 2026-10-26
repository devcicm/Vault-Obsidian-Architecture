#!/usr/bin/env python3
"""
vault_init.py — Bootstrap de un vault fresco en un solo comando.

Hace lo que el README quickstart describe como 3-4 pasos, en uno solo:
  1. Crea las 17 carpetas estándar (00_System → 99_Index)
  2. Escribe 00_System/standard-version.json
  3. Aplica las migraciones pendientes (v20 → current)
  4. Auto-genera el índice de cada sección
  5. Crea 00_System/vault-hub.md y vault-commands.md si no existen
  6. Ejecuta vault_audit y reporta el health score inicial

Diseñado para que un consumer repo pueda ejecutar:

    mkdir vault-mi-proyecto
    cp -r Vault-Obsidian-Architecture/scripts ./
    python scripts/vault_init.py

Y termine con un vault navegable de inmediato, sin tener que recordar
la secuencia exacta de comandos del README.

Usage:
    python vault_init.py                  # versión por defecto (current)
    python vault_init.py --target v32     # migrar hasta v32 explícitamente
    python vault_init.py --no-audit       # omitir vault_audit final
    python vault_init.py --clean --confirm mi-vault   # mueve a cuarentena verificada
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List

from vault_errors import presupuesto_de_vault, emit_error, wrap_main
from vault_standard_upgrade import version_conocida
from vault_io import atomic_write_text, set_vault_root, write_report
from vault_lib import utcnow
from vault_version import CURRENT_VERSION
from vault.kernel import procesos_git
from vault_registry import (
    comando_de_tool,
    standard_folders,
    EVENT_DRIVEN_SECTIONS,
    ORDERED_SECTIONS,
    SCAFFOLD_TYPE,
    section_description,
    section_tool_hint,
)


# Sections that get a scaffold primer on init. 00_System is excluded because
# vault-hub.md + vault-commands.md already provide structure. All other
# standard sections get a primer so the vault starts at 100/100.
# Todas menos `00_System`, que vault_init puebla con ficheros de identidad
# reales y no necesita andamio. Estaba escrita a mano y se quedó en 17: las
# cuatro secciones de v39 nacían vacías, y el andamio existe justamente para
# que una sección recién creada no arrastre la puntuación del vault.
# Fuera: `00_System`, que vault_init puebla con ficheros de identidad reales,
# y las dirigidas por eventos, cuyo vacío es estado correcto.
_SCAFFOLD_SECTIONS = [
    f
    for f in ORDERED_SECTIONS
    if f != "00_System" and f not in EVENT_DRIVEN_SECTIONS
]


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.ciclo_de_vida.repositorio import RepositorioCicloDeVida  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.kernel.frontmatter_escritura import Frontmatter  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioCicloDeVida:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioCicloDeVida(construir(root))


def _create_scaffold_note(section: str) -> Dict[str, Any]:
    """Create a primer note in a section that explains its purpose and how to use it.

    The primer passes the strict content gate (>=3 real lines, >=10 real words)
    so the vault starts at healthScore 100/100 even before the user adds real
    content. Each primer is marked with `scaffold: true` in frontmatter so the
    user can identify and remove or replace it when real content is added.

    Returns: {"section": str, "path": str, "created": bool}
    """
    primer_path = _raiz() / section / f"00-{section.lower()}-primer.md"
    if primer_path.exists():
        return {
            "section": section,
            "path": str(primer_path.relative_to(_raiz())).replace("\\", "/"),
            "created": False,
        }

    description = section_description(section)
    tool_hint = (
        section_tool_hint(section)
        or f"vault_write --folder {section} --title <titulo> --content '...'"
    )
    comando = comando_de_tool(tool_hint)

    # Build content that is real documentation (passes content gate) but
    # explicitly says it's a primer. Real words count: 40+ per primer.
    content = f"""# {section} — Guía rápida

> Esta nota es un **scaffold generado por `vault_init`** para que el vault
> arranque en `healthScore 100/100`. Puedes **eliminarla** cuando la sección
> tenga contenido real, o **mantenerla** como referencia para el equipo.

## Propósito de esta sección

{description}

## Comando sugerido

```
{comando}
```

## Siguiente paso

1. Lee la guía completa en [[vault-hub|Hub del vault]].
2. Crea tu primera nota real con el comando sugerido arriba.
3. Cuando tengas contenido real en esta sección, elimina o renombra este scaffold.

> **Más comandos:** ver [[vault-commands|Comandos del vault]].
"""
    # AP-46: el bloque lo escribe su dueño. Una sola hora para las dos marcas:
    # con dos llamadas a `utcnow()` un primer recién creado podía nacer con
    # `updatedAt` un segundo posterior a su `createdAt`.
    ahora = utcnow()
    frontmatter = (
        Frontmatter()
        # El escape va sobre el valor entero; sobre la mitad salía
        # `title: "x" — Guía rápida`, que YAML no lee.
        .set("title", section + " — Guía rápida", texto=True)
        .set("id", section.lower() + "-primer", texto=True)
        .set("createdAt", ahora)
        .set("updatedAt", ahora)
        .set("cia_integrity", "medium")
        .set("cia_availability", "medium")
        .set("cia_sensitivity", "internal")
        .set("agent", "vault_init")
        .set("tags", ["primer", "scaffold", "onboarding"])
        .set("scaffold", True)
        # `SCAFFOLD_TYPE`, no el literal: `vault_registry.is_scaffold_note()`
        # decide con esa misma constante qué nota es andamio y cuál contenido.
        # Escrito a mano aquí, el escritor y el lector del mismo campo podían
        # dejar de coincidir sin que nada lo notara.
        .set("type", SCAFFOLD_TYPE)
        # Sin `status`, el propio `vault_audit` marcaba como incompleta cada nota
        # que este generador acaba de escribir: 18 primers de 18 en el vault de
        # BuilderX. El generador del estándar producía notas que su auditoría
        # reprueba, y el usuario no tenía forma de saber que la deuda no era suya.
        # `template` — y no `draft` — porque un primer es andamiaje estable, no un
        # borrador en camino a otra cosa; es además el valor que AP-03 y AP-07
        # eximen de exigencias de contenido y estructura de ADR.
        .set("status", "template")
        .set("norm_refs", ["CN-01"])
        .render()
        + "\n\n"
    )
    primer_path.parent.mkdir(parents=True, exist_ok=True)
    # AP-36: `Path.write_text` esquivaba el temp+replace, el escaneo de
    # secretos y el ledger, y los primers no contaban como trabajo (AP-37).
    atomic_write_text(primer_path, frontmatter + content)
    return {
        "section": section,
        "path": str(primer_path.relative_to(_raiz())).replace("\\", "/"),
        "created": True,
    }


def _vault_init_sin_clean(
    target_version: str = CURRENT_VERSION, run_audit: bool = True
) -> dict:
    """Inicializa un vault fresco en VAULT_ROOT.

    No limpia nada: la operacion destructiva la orquesta `vault_init()` a
    traves de `_preparar_clean()`, que garantiza copia verificable y rollback
    antes de llamar aqui (TD-0008).

    Returns a structured result suitable for both CLI JSON output and tests.
    """
    # Antes de crear una sola carpeta: `--target` es una versión, no una ruta,
    # y lo que llegue aquí acaba como `applied_version` del vault.
    if not version_conocida(target_version):
        return emit_error(
            "vault_init",
            "INVALID_INPUT",
            f"--target {target_version!r} no es una versión del estándar "
            f"(se espera vNN o vNN.M; la vigente es {CURRENT_VERSION}). "
            "El vault de destino se fija con VAULT_ROOT, no con --target.",
            args={"target": target_version},
        )
    # Safety: refuse to run if VAULT_ROOT looks wrong (sandbox not detected).
    # AP-52: el rechazo sale del catálogo, no de mutar un `ok: True`.
    if not _raiz().exists() or not _raiz().is_dir():
        return emit_error(
            "vault_init", "VAULT_NOT_FOUND",
            f"VAULT_ROOT does not exist or is not a directory: {_raiz()}",
        )
    result = {
        "ok": True,
        **write_report(),
        "vault_root": str(_raiz()).replace("\\", "/"),
        "target_version": target_version,
        "steps": [],
    }

    # (El antiguo "Step 0: --clean wipes..." vivia aqui. Se elimino porque
    # borraba con shutil.rmtree sin copia ni verificacion. La operacion
    # destructiva completa la orquesta `vault_init()` mediante
    # `_preparar_clean()`, y esta funcion solo corre cuando el contenido
    # anterior ya esta a salvo en una cuarentena verificada.)

    # Step 1: create all 17 standard folders
    folders_created = []
    for folder in standard_folders():
        folder_path = _raiz() / folder
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
            folders_created.append(folder)
        # always ensure .gitkeep
        gitkeep = folder_path / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()
    result["steps"].append(
        {
            "step": "folders",
            "created": folders_created,
            "total": len(standard_folders()),
        }
    )

    # Step 1.2: índices y hub sobre la estructura vacía, antes que la primera
    # nota. El hub se crea una sola vez y no se reescribe; si lo creara el
    # primer andamio, al escribirse solo existiría el índice de esa sección y
    # el hub nacería sin enlazar ninguna otra (QA de producto, 2026-10-04).
    # Dentro de `vault_master_index` sí enlaza todas: es una regeneración
    # completa. El paso 3 vuelve a pasar para contar las notas ya escritas.
    master_script = Path(__file__).parent / "vault_master_index.py"
    if master_script.exists():
        import vault_subproceso

        proc = vault_subproceso.ejecutar(
            [sys.executable, str(master_script)], capture_output=True
        )
        result["steps"].append(
            {"step": "navigation", "ok": proc.returncode == 0}
            if proc.returncode == 0
            else {"step": "navigation", "ok": False, "raw_stderr": proc.stderr}
        )

    # Step 1.5: create a primer note in each content section so the vault
    # starts at healthScore 100/100. Each primer has real content (passes
    # the strict content gate) and explains what the section is for. They
    # are marked scaffold: true so the user can identify and remove them
    # as they add real content.
    scaffolds_created = []
    scaffold_failed = False
    for section in _SCAFFOLD_SECTIONS:
        try:
            res = _create_scaffold_note(section)
            if res.get("created"):
                scaffolds_created.append(res)
        except Exception as exc:
            # scaffold failure must never block init (best-effort)
            scaffold_failed = True
            result["steps"].append(
                {"step": "scaffold_error", "section": section, "error": str(exc)}
            )
    result["steps"].append(
        {
            "step": "scaffolds",
            "created": scaffolds_created,
            "total": len(_SCAFFOLD_SECTIONS),
            "failed": scaffold_failed,
        }
    )

    # Step 2: run vault_standard_upgrade --init <target>
    # We invoke the script as a subprocess to reuse its full logic
    import subprocess
    import vault_subproceso

    scripts_dir = Path(__file__).parent
    upgrade_script = scripts_dir / "vault_standard_upgrade.py"
    if upgrade_script.exists():
        proc = vault_subproceso.ejecutar(
            [
                sys.executable,
                str(upgrade_script),
                "--init",
                target_version,
                "--agent",
                "vault_init",
            ],
            capture_output=True,
        )
        try:
            upgrade_data = json.loads(proc.stdout)
            result["steps"].append({"step": "init", "output": upgrade_data})
        except json.JSONDecodeError:
            result["steps"].append(
                {"step": "init", "raw_stdout": proc.stdout, "raw_stderr": proc.stderr}
            )

    # Step 3: run vault_master_index which also indexes all sections
    master_script = scripts_dir / "vault_master_index.py"
    if master_script.exists():
        proc = vault_subproceso.ejecutar(
            [sys.executable, str(master_script)],
            capture_output=True,
        )
        try:
            master_data = json.loads(proc.stdout)
            result["steps"].append({"step": "master_index", "output": master_data})
        except json.JSONDecodeError:
            result["steps"].append(
                {
                    "step": "master_index",
                    "raw_stdout": proc.stdout,
                    "raw_stderr": proc.stderr,
                }
            )

    # Step 4: run vault_reindex --graph to populate graph.json + search-index.json + hash-index.json
    reindex_script = scripts_dir / "vault_reindex.py"
    if reindex_script.exists():
        proc = vault_subproceso.ejecutar(
            [sys.executable, str(reindex_script), "--graph"],
            capture_output=True,
        )
        try:
            reindex_data = json.loads(proc.stdout)
            result["steps"].append({"step": "reindex", "output": reindex_data})
        except json.JSONDecodeError:
            result["steps"].append(
                {
                    "step": "reindex",
                    "raw_stdout": proc.stdout,
                    "raw_stderr": proc.stderr,
                }
            )

    # Step 4.5: write tag-registry.json with canonical tags
    # La escribe Índices, su dueño, y solo si no existe (deuda #3, residuo).
    tag_registry = {
        "version": "v1.0",
        "generated_at": utcnow(),
        "canonical_tags": {
            "project": ["ans", "builderx", "homelab"],
            "section": ["flow", "pattern", "runbook", "code", "diagram", "infrastructure", "knowledge", "decision", "test", "requirement", "alert", "metric", "slo", "incident"],
            "domain": ["mcp", "toon", "ansible", "ssh", "proxmox", "docker", "deploy", "pipeline", "ci-cd", "mikrotik", "runner", "proxy", "vault"],
            "type": ["dataflow", "lifecycle", "workflow", "pipeline-flow", "architecture", "concept", "api", "config", "guide", "reference"],
            "quality": ["verified", "stub", "draft", "informacion-decrepita", "deprecated"],
            "migration": ["migrated", "direct", "indirect", "excluded"],
            "agent": ["deepseek", "mavis", "opencode", "system", "vault_init"],
            # QA-RC-02e (AP-39): los tags de las notas bootstrap que vault_init
            # crea son canónicos por diseño — no son vocabulario abierto.
            "bootstrap": ["command", "hub", "nav", "onboarding", "primer", "scaffold"],
        },
    }
    if _repo().sembrar_registro_etiquetas(tag_registry):
        result["steps"].append({"step": "tag_registry", "output": "tag-registry.json created"})

    # Step 4.6: write ontology.json into the vault (copy from scripts/vault_ontology.json)
    ontology_src = Path(__file__).parent / "vault_ontology.json"
    ontology_dst = _raiz() / "00_System" / "vault-ontology.json"
    if ontology_src.exists() and not ontology_dst.exists():
        ontology_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ontology_src, ontology_dst)
        result["steps"].append({"step": "ontology", "output": "vault-ontology.json copied to vault"})

    # Step 5: optional vault_audit
    if run_audit:
        audit_script = scripts_dir / "vault_audit.py"
        if audit_script.exists():
            proc = vault_subproceso.ejecutar(
                [sys.executable, str(audit_script)],
                capture_output=True,
            )
            try:
                audit_data = json.loads(proc.stdout)
                result["steps"].append({"step": "audit", "output": audit_data})
                result["healthScore"] = audit_data.get("healthScore")
                result["noteCount"] = audit_data.get("stats", {}).get("total", 0)
            except json.JSONDecodeError:
                result["steps"].append(
                    {
                        "step": "audit",
                        "raw_stdout": proc.stdout,
                        "raw_stderr": proc.stderr,
                    }
                )

    # Step 6: report on hub notes
    hub_note = _raiz() / "00_System" / "vault-hub.md"
    commands_note = _raiz() / "00_System" / "vault-commands.md"
    result["hub_notes"] = {
        "hub": str(hub_note.relative_to(_raiz())).replace("\\", "/")
        if hub_note.exists()
        else None,
        "commands": str(commands_note.relative_to(_raiz())).replace("\\", "/")
        if commands_note.exists()
        else None,
    }

    # Promote healthScore + noteCount to top-level so the spec contract is satisfied.
    # They are computed in step 5 (audit) and step 4 (reindex).
    if "healthScore" not in result:
        for step in result["steps"]:
            if step.get("step") == "audit":
                out = step.get("output", {})
                if isinstance(out, dict):
                    result["healthScore"] = out.get("healthScore")
                    result["noteCount"] = out.get("stats", {}).get("total", 0)
                    break

    # AP-37: el indicador se mide al terminar. Expandido solo al construir
    # `result`, antes de escribir nada, declaraba `written: 0` siempre.
    result.update(write_report())
    return result


# ── TD-0008: operacion destructiva con recuperacion verificable ──────────────
#
# AP-36 pide que los side effects vivan dentro del vault. La cuarentena es la
# excepcion deliberada y se documenta: tiene que SOBREVIVIR al borrado, asi que
# no puede estar dentro de lo que se borra. Vive como hermana del vault
# (`.<nombre>.cuarentena-<TS>`), en el mismo volumen, para que el rename sea
# atomico.
#
# Maquina de estados (audits/fase2/R04-diseno-td0008.md):
#   PRECHECK -> BACKUP -> VERIFY_BACKUP -> READY -> CLEAN -> VERIFIED
# Un fallo antes de CLEAN deja el vault intacto; uno posterior deja la
# cuarentena en pie para restaurar.

MANIFIESTO_CUARENTENA = ".cuarentena.json"


def _marcas_de_vault(raiz: Path) -> bool:
    """Un vault se reconoce por sus marcas, no por estar en una ruta.

    Sin esta comprobacion, un VAULT_ROOT mal exportado convierte `--clean` en
    el borrado de un directorio de trabajo cualquiera.
    """
    return (raiz / "00_System").is_dir() or (raiz / "17_Preferences").is_dir()


def _inventario(raiz: Path) -> Dict[str, Any]:
    """Inventario con hash de contenido, sin seguir symlinks (TD-0008).

    Verificar nombres no demuestra nada. Los symlinks se registran como tales y
    NO se atraviesan: el inventario no puede salirse del arbol ni entrar en un
    ciclo.
    """
    import hashlib
    import os

    entradas: Dict[str, Dict[str, Any]] = {}
    errores: List[str] = []
    for base, dirs, ficheros in os.walk(raiz, followlinks=False):
        base_path = Path(base)
        for d in list(dirs):
            ruta = base_path / d
            if ruta.is_symlink():
                rel = ruta.relative_to(raiz).as_posix()
                entradas[rel] = {"tipo": "symlink", "destino": os.readlink(ruta)}
                dirs.remove(d)
        for nombre in ficheros:
            ruta = base_path / nombre
            rel = ruta.relative_to(raiz).as_posix()
            try:
                if ruta.is_symlink():
                    entradas[rel] = {"tipo": "symlink", "destino": os.readlink(ruta)}
                    continue
                digest = hashlib.sha256()
                with ruta.open("rb") as fh:
                    for bloque in iter(lambda: fh.read(1 << 20), b""):
                        digest.update(bloque)
                entradas[rel] = {"tipo": "fichero", "tamano": ruta.stat().st_size,
                                 "sha256": digest.hexdigest()}
            except OSError as exc:
                errores.append(f"{rel}: {exc}")
    return {"entradas": entradas, "errores": errores, "total": len(entradas),
            "bytes": sum(e.get("tamano", 0) for e in entradas.values())}


def _cuarentena_hermana(raiz: Path) -> Path:
    """Una ruta hermana libre, en el mismo volumen, para el rename atomico."""
    from datetime import datetime, timezone

    sello = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = raiz.parent / f".{raiz.name}.cuarentena-{sello}"
    candidata, n = base, 1
    while candidata.exists():
        n += 1
        candidata = base.with_name(f"{base.name}-{n}")
    return candidata


def _verificar_copia(original: Dict[str, Any], copia: Path) -> Dict[str, Any]:
    """Compara inventarios por CONTENIDO, no por nombre."""
    actual = _inventario(copia)
    faltan = sorted(set(original["entradas"]) - set(actual["entradas"]))
    sobran = sorted(set(actual["entradas"]) - set(original["entradas"]))
    distintos = sorted(
        rel for rel in set(original["entradas"]) & set(actual["entradas"])
        if original["entradas"][rel] != actual["entradas"][rel])
    return {"ok": not (faltan or sobran or distintos or actual["errores"]),
            "faltan": faltan[:20], "sobran": sobran[:20],
            "distintos": distintos[:20], "errores": actual["errores"][:20],
            "total": actual["total"]}


def _preparar_clean(raiz: Path, confirm: str | None, dry_run: bool = False,
                    recibo: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """PRECHECK -> BACKUP -> VERIFY_BACKUP -> READY (y CLEAN si no es dry-run).

    `recibo` es un diccionario que esta funcion actualiza a medida que progresa
    (fase, cuarentena, inventario): si algo explota a mitad, el llamador sabe
    QUE hacer para recuperar sin adivinar (QA-RC-01b).
    """
    paso: Dict[str, Any] = {"step": "clean", "estado": "PRECHECK"}

    def _fase(nombre: str) -> None:
        paso["estado"] = nombre
        if recibo is not None:
            recibo["fase"] = nombre
            recibo["estado"] = paso["estado"]
    if not _marcas_de_vault(raiz):
        paso.update({"estado": "ABORTED", "motivo": "VAULT_NOT_RECOGNIZED",
                     "detalle": (f"'{raiz}' no tiene marcas de vault (00_System "
                                 "o 17_Preferences): no se borra un directorio "
                                 "que no se reconoce como vault.")})
        return {"ok": False, "preparacion": paso}
    if confirm != raiz.name:
        paso.update({"estado": "ABORTED", "motivo": "CONFIRMACION_REQUERIDA",
                     "detalle": (f"Operacion destructiva: repite con "
                                 f"--confirm {raiz.name!r} (el nombre del vault "
                                 "que se va a limpiar).")})
        return {"ok": False, "preparacion": paso}

    inventario = _inventario(raiz)
    if inventario["errores"]:
        paso.update({"estado": "ABORTED", "motivo": "INVENTARIO_INCOMPLETO",
                     "detalle": ("No se pudo leer todo el contenido; sin "
                                 "inventario completo no hay copia verificable."),
                     "errores": inventario["errores"][:20]})
        return {"ok": False, "preparacion": paso}

    plan = sorted(p.name for p in raiz.iterdir() if p.name != ".locks")
    if dry_run:
        paso.update({"estado": "READY", "dry_run": True, "plan": plan,
                     "total": inventario["total"], "bytes": inventario["bytes"]})
        return {"ok": True, "preparacion": paso, "cuarentena": None}

    cuarentena = _cuarentena_hermana(raiz)
    if recibo is not None:
        recibo["inventario"] = inventario
    _fase("BACKUP")
    if recibo is not None:
        recibo["cuarentena"] = str(cuarentena)
    try:
        raiz.rename(cuarentena)
    except OSError as exc:
        # Rename imposible (volumen distinto o bloqueo): copia verificada y
        # solo despues se borra el original. Si la copia no verifica, no se
        # borra nada.
        paso["mecanismo"] = "copia"
        try:
            shutil.copytree(raiz, cuarentena, symlinks=True)
        except OSError as exc_copia:
            shutil.rmtree(cuarentena, ignore_errors=True)
            paso.update({"estado": "ABORTED", "motivo": "BACKUP_FALLIDO",
                         "detalle": f"rename: {exc}; copia: {exc_copia}"})
            return {"ok": False, "preparacion": paso}
        verificacion = _verificar_copia(inventario, cuarentena)
        if not verificacion["ok"]:
            retirada = False
            detalle_retirada = None
            try:
                shutil.rmtree(cuarentena)
                retirada = not cuarentena.exists()
            except OSError as exc:
                detalle_retirada = str(exc)
            paso.update({"estado": "ABORTED", "motivo": "COPIA_NO_VERIFICADA",
                         "cuarentena": (None if retirada else str(cuarentena)),
                         "detalle_retirada": detalle_retirada,
                         "verificacion": verificacion})
            return {"ok": False, "preparacion": paso}
        try:
            for entry in sorted(raiz.iterdir(), reverse=True):
                if entry.name == ".locks":
                    continue
                if entry.is_dir() and not entry.is_symlink():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
        except OSError as exc:
            # QA-RC-01: el borrado del original puede fallar a mitad. No hay
            # forma de reconstruirlo desde el original, pero SI desde la copia
            # verificada: se restaura desde la cuarentena y, si tampoco se
            # puede, se deja la cuarentena intacta y se declara recuperacion
            # pendiente. Nunca se borra la copia en este camino.
            restauracion = _restaurar_copia(raiz, cuarentena, inventario)
            paso.update({"estado": ("ROLLBACK" if restauracion.get("ok")
                                    else "RECUPERACION_PENDIENTE"),
                         "motivo": "BORRADO_INCOMPLETO",
                         "cuarentena": str(cuarentena),
                         "restauracion": restauracion,
                         "detalle": str(exc)})
            return {"ok": False, "preparacion": paso}
    else:
        paso["mecanismo"] = "rename"
        raiz.mkdir(parents=True, exist_ok=True)
        # `.locks` es estado del runtime, no contenido del usuario: el borrado
        # antiguo lo preservaba y la cuarentena no debe llevarselo.
        bloqueo = cuarentena / ".locks"
        if bloqueo.exists():
            shutil.copytree(bloqueo, raiz / ".locks", dirs_exist_ok=True)

    _fase("VERIFY_BACKUP")
    try:
        verificacion = _verificar_copia(inventario, cuarentena)
    except OSError as exc:
        restauracion = _restaurar_copia(raiz, cuarentena, inventario)
        paso.update({"estado": ("ROLLBACK" if restauracion.get("ok")
                                else "RECUPERACION_PENDIENTE"),
                     "motivo": "VERIFICACION_ILEGIBLE", "detalle": str(exc),
                     "restauracion": restauracion})
        return {"ok": False, "preparacion": paso}
    if not verificacion["ok"]:
        # QA-RC-01f: el backup no es fiable y NUNCA reemplaza al original.
        if paso.get("mecanismo") == "rename":
            # `raiz` es el directorio vacio recien creado: se retira para
            # devolver la cuarentena a su sitio, y la devolucion se VERIFICA.
            if raiz.exists():
                shutil.rmtree(raiz)
            try:
                cuarentena.rename(raiz)
            except OSError as exc:
                paso.update({"estado": "RECUPERACION_PENDIENTE",
                             "motivo": "RESTAURACION_FALLIDA",
                             "cuarentena": str(cuarentena),
                             "detalle": str(exc),
                             "verificacion": verificacion})
                return {"ok": False, "preparacion": paso}
            post = _verificar_copia(inventario, raiz)
            estado = "ROLLBACK" if post["ok"] else "RECUPERACION_PENDIENTE"
            paso.update({"estado": estado, "motivo": "VERIFICACION_FALLIDA",
                         "restauracion": post, "verificacion": verificacion,
                         "cuarentena": (None if post["ok"] else str(raiz))})
            return {"ok": False, "preparacion": paso}
        # Via de copia: el original esta intacto (aun no se borro nada), asi
        # que basta con retirar la copia mala y abortar. Si la retirada
        # falla, se declara: la cuarentena muerta no se oculta.
        retirada = False
        detalle_retirada = None
        try:
            shutil.rmtree(cuarentena)
            retirada = not cuarentena.exists()
        except OSError as exc:
            detalle_retirada = str(exc)
        paso.update({"estado": "ABORTED", "motivo": "COPIA_NO_VERIFICADA",
                     "cuarentena": (None if retirada else str(cuarentena)),
                     "detalle_retirada": detalle_retirada,
                     "verificacion": verificacion})
        return {"ok": False, "preparacion": paso}

    try:
        (cuarentena / MANIFIESTO_CUARENTENA).write_text(
            json.dumps({"vault": raiz.name, "verificado": True,
                        "total": verificacion["total"],
                        "mecanismo": paso["mecanismo"]},
                       indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as exc:
        paso["aviso_manifiesto"] = str(exc)

    paso.update({"estado": "READY", "cuarentena": str(cuarentena),
                 "total": verificacion["total"], "bytes": inventario["bytes"]})
    return {"ok": True, "preparacion": paso, "cuarentena": cuarentena}


def _restaurar_copia(raiz: Path, cuarentena: Path,
                     inventario: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Rollback desde la COPIA cuando el original quedo a medio borrar.

    Verifica el contenido restaurado contra el inventario del ORIGINAL: sin esa
    comprobacion, `ok: true` seria una afirmacion (QA-RC-01c). La cuarentena no
    se elimina: si esta restauracion falla, es la unica via de recuperacion.
    """
    try:
        shutil.copytree(cuarentena, raiz, dirs_exist_ok=True, symlinks=True)
    except OSError as exc:
        return {"ok": False, "detalle": str(exc), "cuarentena": str(cuarentena)}
    manifiesto = raiz / MANIFIESTO_CUARENTENA
    if manifiesto.exists():
        manifiesto.unlink()
    if inventario is not None:
        verificacion = _verificar_copia(inventario, raiz)
        if not verificacion["ok"]:
            return {"ok": False, "via": "copia", "cuarentena": str(cuarentena),
                    "detalle": "RESTAURACION_NO_VERIFICADA",
                    "verificacion": verificacion}
    return {"ok": True, "via": "copia", "cuarentena": str(cuarentena),
            "verificado": inventario is not None}


def _restaurar(raiz: Path, cuarentena: Path) -> Dict[str, Any]:
    """ROLLBACK: el contenido anterior vuelve a su sitio y se verifica."""
    try:
        if raiz.exists():
            shutil.rmtree(raiz)
        cuarentena.rename(raiz)
        manifiesto = raiz / MANIFIESTO_CUARENTENA
        if manifiesto.exists():
            manifiesto.unlink()
        return {"ok": True, "restaurado": str(raiz)}
    except OSError as exc:
        # La cuarentena se conserva: es la via de recuperacion manual.
        return {"ok": False, "detalle": str(exc), "cuarentena": str(cuarentena)}


def _purgar_cuarentena(ruta: Path, raiz: Path) -> Dict[str, Any]:
    """Purga DIFERIDA: solo una cuarentena hermana, verificada y explicita."""
    ruta = ruta.resolve()
    try:
        ruta.relative_to(raiz.parent)
    except ValueError:
        return {"ok": False, "motivo": "FUERA_DEL_AMBITO"}
    if not ruta.name.startswith(f".{raiz.name}.cuarentena-"):
        return {"ok": False, "motivo": "NO_ES_CUARENTENA_DE_ESTE_VAULT"}
    if not (ruta / MANIFIESTO_CUARENTENA).is_file():
        return {"ok": False, "motivo": "SIN_MANIFIESTO_DE_VERIFICACION"}
    shutil.rmtree(ruta)
    return {"ok": True, "purgado": str(ruta)}


def vault_init(
    target_version: str = CURRENT_VERSION,
    run_audit: bool = True,
    clean: bool = False,
    confirm: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Inicializa un vault; con `clean`, solo sobre una copia verificada.

    El contenido anterior se mueve a una cuarentena hermana verificada por
    contenido antes de inicializar nada. Un fallo antes de CLEAN deja el vault
    intacto; uno posterior deja la cuarentena en pie para restaurar. Nunca se
    borra sin una via de recuperacion.
    """
    if not clean:
        return _vault_init_sin_clean(target_version=target_version,
                                     run_audit=run_audit)

    raiz = _raiz()
    if not raiz.exists() or not raiz.is_dir():
        return emit_error("vault_init", "VAULT_NOT_FOUND",
                          f"VAULT_ROOT does not exist or is not a directory: {raiz}")

    # QA-RC-01: la preparacion tambien puede fallar (copia, borrado parcial,
    # permisos). El recibo dice hasta donde llego y QUE hay que recuperar.
    recibo: Dict[str, Any] = {"fase": "PRECHECK", "cuarentena": None,
                              "inventario": None}
    try:
        preparacion = _preparar_clean(raiz, confirm, dry_run=dry_run,
                                      recibo=recibo)
    except BaseException as exc:
        restauracion: Dict[str, Any] = {"ok": False, "cuarentena": None}
        if recibo.get("cuarentena") and recibo.get("inventario"):
            restauracion = _restaurar_copia(raiz, Path(recibo["cuarentena"]),
                                            recibo["inventario"])
        estado = ("ROLLBACK" if restauracion.get("ok")
                  else "RECUPERACION_PENDIENTE")
        sobre = emit_error("vault_init", "INIT_FAILED_AFTER_CLEAN",
                           f"fallo preparando la limpieza: {exc}",
                           args={"fase": recibo.get("fase"),
                                 "cuarentena": recibo.get("cuarentena"),
                                 "restauracion": restauracion,
                                 "estado": estado})
        sobre["clean"] = {"step": "clean", "estado": estado,
                          "detalle": str(exc)}
        return sobre
    paso = preparacion.get("preparacion", {})
    if not preparacion["ok"]:
        sobre = emit_error("vault_init", "INVALID_INPUT",
                           paso.get("detalle", "no se pudo preparar la limpieza"),
                           args={"motivo": paso.get("motivo"),
                                 "estado": paso.get("estado")})
        sobre["clean"] = paso
        return sobre
    if dry_run:
        return {"ok": True, "clean": paso,
                "vault_root": str(raiz).replace("\\", "/"),
                "plan": paso.get("plan", [])}

    cuarentena = preparacion["cuarentena"]
    paso["estado"] = "CLEAN"
    try:
        resultado = _vault_init_sin_clean(target_version=target_version,
                                          run_audit=run_audit)
    except BaseException as exc:  # rollback tambien ante KeyboardInterrupt
        restauracion = _restaurar(raiz, cuarentena)
        estado = "ROLLBACK" if restauracion.get("ok") else "RECUPERACION_PENDIENTE"
        sobre = emit_error("vault_init", "INIT_FAILED_AFTER_CLEAN", str(exc),
                           args={"cuarentena": str(cuarentena),
                                 "restauracion": restauracion,
                                 "estado": estado})
        sobre["clean"] = {**paso, "estado": estado}
        return sobre
    # QA-RC-01: un ok:false NO es una excepcion, y tambien deja el runtime a
    # medio inicializar. Se restaura igual; nunca se declara VERIFIED.
    if isinstance(resultado, dict) and resultado.get("ok") is False:
        restauracion = _restaurar(raiz, cuarentena)
        estado = "ROLLBACK" if restauracion.get("ok") else "RECUPERACION_PENDIENTE"
        sobre = emit_error(
            "vault_init", "INIT_FAILED_AFTER_CLEAN",
            resultado.get("message") or "la inicializacion devolvio ok=false",
            args={"cuarentena": str(cuarentena),
                  "restauracion": restauracion,
                  "error_code_interno": resultado.get("error_code"),
                  "estado": estado})
        sobre["clean"] = {**paso, "estado": estado}
        return sobre
    paso["estado"] = "VERIFIED"
    resultado["clean"] = paso
    resultado["cuarentena"] = str(cuarentena)
    resultado["purga"] = "diferida"
    return resultado


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Init — bootstrap a fresh vault in one command",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
    Ejemplos:
  # Bootstrap con la versión actual del estándar
  python vault_init.py

  # Migrar a una versión específica
  python vault_init.py --target v38.1

  # Bootstrap sin ejecutar vault_audit al final
  python vault_init.py --no-audit

  # Bootstrap desde cero (BORRA el contenido actual — usar con cuidado)
  python vault_init.py --clean --confirm mi-vault

  # Ver que se borraria, sin borrar nada
  python vault_init.py --clean --confirm mi-vault --dry-run

Notas:
  - VAULT_ROOT se detecta automáticamente
  - Crea las carpetas estándar del registro, aplica migraciones, indexa todo,
    genera hub/commands notes y reporta el health score.
  - --clean exige --confirm <nombre-del-vault>: mueve el contenido
    anterior a una cuarentena hermana verificada por hash antes de
    inicializar, y la conserva hasta purgarla expresamente.
        """,
        allow_abbrev=False,
    )
    parser.add_argument(
        "--target",
        default=CURRENT_VERSION,
        help=(
            "Versión objetivo del estándar. Por defecto, la versión actual "
            f"({CURRENT_VERSION}): fijarla a mano dejaba el vault sellado con "
            "una versión antigua y las carpetas de las migraciones posteriores "
            "sin crear."
        ),
    )
    parser.add_argument(
        "--no-audit", action="store_true", help="Skip final vault_audit run"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Wipe existing vault content before init (DANGEROUS)",
    )
    parser.add_argument(
        "--confirm",
        default=None,
        help=(
            "Nombre del vault que se va a limpiar. Obligatorio con --clean: "
            "una operacion destructiva no se dispara por accidente."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Con --clean: muestra el plan de borrado y no borra nada.",
    )
    parser.add_argument(
        "--purge-backup",
        default=None,
        metavar="RUTA",
        help="Purga una cuarentena concreta de este vault (purga diferida).",
    )
    parser.add_argument(
        "--name",
        default=None,
        help=(
            "Crea el vault en la casa de los vaults: "
            "~/.vault-master/<nombre> (Windows: %%USERPROFILE%%\\.vault-master\\<nombre>). "
            "Es donde vive un vault con su propio repositorio git."
        ),
    )
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="Con --name: no inicializa el repositorio git del vault.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Lista los vaults de la casa (nombre, version y si tienen git).",
    )
    args = parser.parse_args()

    if args.purge_backup:
        raiz_actual = _raiz()
        resultado_purga = _purgar_cuarentena(Path(args.purge_backup), raiz_actual)
        print(json.dumps({"ok": resultado_purga.get("ok"),
                          "purga": resultado_purga},
                         indent=2, ensure_ascii=False))
        return 0 if resultado_purga.get("ok") else 1

    if args.list:
        print(json.dumps(_listar_vaults_de_la_casa(), indent=2, ensure_ascii=False))
        return 0

    destino = None
    if args.name:
        from vault.kernel.vault_home import vault_en_master

        try:
            destino = vault_en_master(args.name)
        except ValueError as exc:
            print(json.dumps(emit_error("vault_init", "INVALID_NAME", str(exc)),
                             indent=2, ensure_ascii=False))
            return 1
        if destino.exists() and any(destino.iterdir()):
            print(json.dumps(emit_error(
                "vault_init", "VAULT_EXISTS",
                f"'{destino}' ya existe y no esta vacio: no se pisa un vault."),
                indent=2, ensure_ascii=False))
            return 1
        # La deteccion se resuelve al crearlo: el vault nuevo es el destino.
        # El init rechaza una raiz que no existe (para no materializar un
        # vault fantasma), asi que la crea quien ha pedido el vault por
        # nombre: la carpeta vacia es el destino, y `--clean` no toca nada.
        destino.mkdir(parents=True, exist_ok=True)
        set_vault_root(destino)

    result = vault_init(
        target_version=args.target,
        run_audit=not args.no_audit,
        clean=args.clean,
        confirm=args.confirm,
        dry_run=args.dry_run,
    )
    if args.name and result.get("ok") and not args.no_git:
        result["git"] = _inicializar_git(destino)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


def _inicializar_git(destino: Path) -> Dict[str, Any]:
    """El vault de la casa nace con su repositorio (v41.15).

    La memoria del agente se versiona como lo que es. Un vault suelto dentro
    del repositorio del proyecto —medido en un vault real: las notas del
    proyecto absorbidas quedaban borradas del repo del proyecto y sin
    versionar en ninguna parte— pierde su historia en cuanto alguien clona el
    proyecto. Con repo propio, la memoria tiene su historia.

    Si git no esta configurado (sin user.name), el repo queda inicializado y
    el commit se avisa: el commit lo hace quien tiene identidad.

    Desde AP-68 las tres órdenes pasan por `vault.kernel.procesos_git`, el
    dueño único de git en el toolkit: `init`, `add` y `commit` son los tres
    verbos mutadores que ese dueño autoriza, y están autorizados **solo**
    porque este bootstrap es el único sitio que los usa, sobre un vault que
    `vault_init` acaba de crear — un vault existente no vacío se rechaza
    antes de llegar aquí. Un cuarto verbo mutador en el repo no entra por
    esta puerta: lo veta el dueño y lo publica `vault_procesos_git`.
    """
    def _git(*args: str):
        return procesos_git.ejecutar_git(destino, list(args),
                                         capture_output=True)

    if not (destino / ".git").exists():
        r = _git("init", "-b", "main")
        if r.returncode != 0:
            return {"ok": False, "motivo": (r.stderr or "").strip()[:300]}
    r_add = _git("add", "-A")
    if r_add.returncode != 0:
        # Antes el `add` se lanzaba sin mirar su salida: un fallo de staging
        # llegaba al commit, que a su vez fallaba, y el motivo que se
        # reportaba era el del commit y no el del staging (AP-51).
        return {"ok": False,
                "motivo": "repo inicializado, sin staging: "
                          + (r_add.stderr or r_add.stdout).strip()[:300],
                "repo": str(destino / ".git")}
    r = _git("commit", "-q", "-m", "vault: bootstrap del vault")
    if r.returncode != 0:
        return {"ok": False,
                "motivo": "repo inicializado, sin commit: "
                          + (r.stderr or r.stdout).strip()[:300],
                "repo": str(destino / ".git")}
    commit = _git("rev-parse", "--short", "HEAD").stdout.strip()
    return {"ok": True, "repo": str(destino / ".git"), "commit": commit}


def _listar_vaults_de_la_casa() -> Dict[str, Any]:
    """Los vaults de la casa, con lo que se sabe de cada uno sin abrirlo."""
    from vault.kernel.vault_home import listar_vaults_de_la_casa, master_home

    casa = master_home()
    vaults = listar_vaults_de_la_casa()
    return {"ok": True, "tool": "vault_init", "action": "list", "casa": str(casa),
            "total": len(vaults), "vaults": vaults}


if __name__ == "__main__":
    # O8, medido en un vault ajeno real de 15.785 ficheros: el presupuesto
    # genérico de 60 s mataba el init a mitad de escritura (dejaba índices
    # y sello escritos y el envelope en TOOL_TIMEOUT). Es la misma clase que
    # `vault_reindex` ya resolvió: el init recorre el vault entero, así que
    # su presupuesto es max(VAULT_TOOL_TIMEOUT, 3600) — el default sigue
    # detectando una tool colgada, y un `VAULT_TOOL_TIMEOUT` mayor manda.
    import vault_errors

    sys.exit(wrap_main(main, "vault_init",
                       timeout=vault_errors.presupuesto_de_vault()))
