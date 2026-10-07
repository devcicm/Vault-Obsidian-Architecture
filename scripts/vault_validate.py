#!/usr/bin/env python3

"""

Vault Validate — Validates frontmatter, folder structure, and index integrity.



Blueprint: vault-obsidian-architecture.md § vault_validate(path?, folder?, check?)



Usage:

    python vault_validate.py --check all

    python vault_validate.py --path "07_Knowledge/api.md" --check frontmatter

    python vault_validate.py --folder "01_Projects" --check frontmatter

    python vault_validate.py --check structure

    python vault_validate.py --check indexes

"""


import argparse

import json

import sys

from vault_registry import ORDERED_SECTIONS, es_artefacto_derivado
from vault_encoding import strip_bom
from vault_errors import emit_error, wrap_main

from vault_io import assert_within_vault
from vault.kernel.frontmatter_parsing import FrontmatterParseError, parse_frontmatter_with_body
from vault_fundamentals_catalog import cia_valores
from vault_contrato_nota import VERSIONES_CON_CONTRATO, contrato_de_version, errores_de_valor, faltantes

import yaml

from pathlib import Path

from typing import Any, Dict, List, Optional


# El vocabulario CIA lo declara `vault_fundamentals.CIA_TRIAD`, que es la fuente
# única del marco según AGENTS.md. Aquí estaba copiado a mano: coincidía, pero
# nada lo obligaba, y una tercera copia vivía dentro de `_check_fundamentals`.
CIA_INTEGRITY_VALUES = cia_valores("cia_integrity")

CIA_AVAILABILITY_VALUES = cia_valores("cia_availability")

CIA_SENSITIVITY_VALUES = cia_valores("cia_sensitivity")


# Se congeló en v33 con diez secciones y nunca creció: un vault sin `11_Code`
# ni `18_Bugs` pasaba la validación como completo, porque «requerido» aquí
# significaba lo que era requerido hace siete versiones. Ahora lo dice el
# registro, así que una sección nueva es exigible el mismo día que existe.
REQUIRED_FOLDERS = list(ORDERED_SECTIONS)


REQUIRED_INDEXES = [

    "99_Index/search-index.json",

    "99_Index/graph.json",

]


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.gobernanza.repositorio import RepositorioGobernanza  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.kernel.errores import completar_envelope  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioGobernanza:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioGobernanza(construir(root))


def _validate_cia_fields(data: Dict[str, Any]) -> List[str]:

    """Validate optional CIA fields if present. Returns list of error messages.

    Lo que se acepta lo dice `vault_contrato_nota.errores_de_valor` —CIA,
    `dq_validated_at` y `agent` no vacío (F7)—; aquí solo se conserva el nombre
    para quien ya lo llamaba (no-derogación).
    """

    return errores_de_valor(data)


def validate_frontmatter(note_path: Path, contrato: Optional[str] = None) -> Dict[str, Any]:

    """Validate YAML frontmatter of a single note. Returns {valid, error?, data?}.

    Aquí se miden dos normas, y conviene no confundirlas:

    - **AP-28** es el caso degenerado: no hay bloque de frontmatter en absoluto
      (`No frontmatter block`, `Frontmatter not closed`, o un bloque que no es
      un mapping YAML). Sin bloque no hay ningún campo que discutir.
    - **AP-12** es la inconsistencia entre notas del mismo tipo, y se aplica
      exigiendo el **mismo** conjunto `required` a toda nota de la misma clase
      —contenido, índice derivado, `00_System/`— en vez de campo a campo. Que
      la clase decida el conjunto es lo que impide que dos notas hermanas
      lleguen a tener frontmatter distinto y las dos pasen.

    `vault_audit` mide los campos uno por uno como AP-16/26/27/29/30; esa es
    otra medida y no sustituye a esta.

    `contrato` (`v18`..) aplica el contrato de esa versión en vez del vigente:
    un vault que se quedó en v30 se juzga por lo que v30 exigía.
    """

    try:

        content = note_path.read_text(encoding="utf-8", errors="ignore")

    except Exception as e:

        return {"valid": False, "error": str(e)}


    # Un BOM delante del `---` no impide leer el frontmatter: ni Obsidian ni
    # `yaml.safe_load` sobre el bloque ya recortado lo notan, y el kernel tiene
    # `strip_bom` precisamente para esto. Sin quitarlo, `startswith("---")` era
    # falso y once notas del vault de pruebas —con frontmatter completo y
    # legible— salían como «No frontmatter block». AP-44: la comprobación medía
    # con su criterio, no con el del consumidor.

    content, _ = strip_bom(content)


    rel_path = str(note_path.relative_to(_raiz())).replace("\\", "/")
    is_index = es_artefacto_derivado(rel_path) and (
        contrato is None or contrato_de_version(contrato)["indices_exentos"])

    if not content.startswith("---"):

        # Un artefacto derivado se escribe sin frontmatter: lo genera una tool
        # —`vault_section_index`, `vault_change_log`, `vault_compact_contracts`—
        # que no le pone ninguno. Exigírselo hacía que el estándar reprobara 65
        # ficheros que acababa de escribir él mismo (AP-44: medir con criterio
        # propio). Tres líneas más abajo esta misma función ya los exceptúa de
        # los campos de trazabilidad — la excepción existía, solo llegaba tarde.
        # Cuáles son lo dice `vault_registry`, no esta función.
        if is_index:
            return {"valid": True, "data": {}, "derived": True}
        return {"valid": False, "error": "No frontmatter block"}


    # AP-44 / AP-57: el bloque se cierra en una línea que es `---`, no en
    # cualquier `---` del texto. `split("---", 2)` cortaba dentro de un título
    # entre comillas —`title: "x\n---"`, YAML válido y escrito así por el
    # propio `vault_write`— y declaraba rota la nota. El corte lo decide el
    # dueño del criterio; aquí solo se conserva el motivo del rechazo, que el
    # dueño encadena como causa.
    try:

        data, cuerpo = parse_frontmatter_with_body(content)

    except FrontmatterParseError as e:

        if e.__cause__ is None:

            return {"valid": False, "error": "Frontmatter is not a YAML mapping"}

        return {"valid": False, "error": f"YAML parse error: {e.__cause__}"}


    if cuerpo == content:

        return {"valid": False, "error": "Frontmatter not closed"}


    # Qué campos exige cada clase de nota —y desde qué versión— lo dice
    # `vault_contrato_nota` (AP-57). Aquí vivía el literal, con «v37: required
    # fields expanded» como toda su historia, y nadie más podía preguntar qué
    # le falta a una nota sin copiarlo.
    missing = faltantes(data, rel_path, contrato, raiz=_raiz())
    if missing:
        return {"valid": False, "error": f"Missing required fields: {missing}",
                "missing": missing, "data": data}


    cia_errors = _validate_cia_fields(data) if contrato is None else errores_de_valor(data, contrato)

    if cia_errors:

        return {"valid": False, "error": f"CIA field errors: {'; '.join(cia_errors)}", "data": data}


    return {"valid": True, "data": data}


def check_frontmatter(path: Optional[str], folder: Optional[str],
                      contrato: Optional[str] = None) -> Dict[str, Any]:

    """Run frontmatter validation on one note, a folder, or the whole vault."""

    if path:

        note = _raiz() / path

        result = validate_frontmatter(note, contrato)

        if result["valid"]:

            return {"valid": [path], "invalid": []}

        return {"valid": [], "invalid": [{"path": path, "error": result["error"]}]}


    notes = _notas_del_alcance(folder)

    valid: List[str] = []

    invalid: List[Dict[str, str]] = []


    for note in notes:

        result = validate_frontmatter(note, contrato)

        rel = note.relative_to(_raiz()).as_posix()

        if result["valid"]:

            valid.append(rel)

        else:

            invalid.append({"path": rel, "error": result["error"]})


    return {"valid": valid, "invalid": invalid}


def check_cumplimiento(path: Optional[str], folder: Optional[str]) -> Dict[str, Any]:
    """Qué contratos cumple cada nota, versión a versión, y qué le falta para el vigente.

    Medido el 2026-10-07 en dos vaults ajenos: el cumplimiento no es monótono
    —una nota con `id` y `title` cumple de v25 a v36 y ni v18 ni v37— así que
    se publica la lista de versiones, no un umbral. El juez de cada versión es
    `validate_frontmatter`, el mismo de `--contrato` (AP-57): un informe que
    juzgara con criterio propio podría decir «cumple v30» de una nota que
    `--contrato v30` reprueba.

    Es un informe: no reprueba nada y no cambia `ok`.
    """
    notes = [_raiz() / path] if path else _notas_del_alcance(folder)
    vigente = VERSIONES_CON_CONTRATO[-1]
    notas: List[Dict[str, Any]] = []
    cumplen: Dict[str, int] = {v: 0 for v in VERSIONES_CON_CONTRATO}
    mas_alta: Dict[str, int] = {}
    faltan: Dict[str, int] = {}
    derivadas = 0
    for note in notes:
        # Un artefacto derivado no tiene contrato desde v37 y el juez lo da por
        # válido: contarlo inflaba la cifra. Medido en un vault ajeno, 38 de los
        # 40 «cumple v41» eran `index.md`.
        if es_artefacto_derivado(note.relative_to(_raiz()).as_posix()):
            derivadas += 1
            continue
        cumple = [v for v in VERSIONES_CON_CONTRATO if validate_frontmatter(note, v)["valid"]]
        actual = validate_frontmatter(note)
        falta = list(actual.get("missing") or [])
        for v in cumple:
            cumplen[v] += 1
        alta = cumple[-1] if cumple else None
        mas_alta[alta or "ninguna"] = mas_alta.get(alta or "ninguna", 0) + 1
        for campo in falta:
            faltan[campo] = faltan.get(campo, 0) + 1
        fila: Dict[str, Any] = {
            "path": note.relative_to(_raiz()).as_posix(),
            "cumple": cumple,
            "version_mas_alta": alta,
            "cumple_vigente": bool(actual["valid"]),
            "falta_para_vigente": falta,
        }
        if not actual["valid"] and not falta:
            # No le falta un campo: lo que la reprueba es otra cosa (un valor
            # fuera de vocabulario, un frontmatter que no se lee).
            fila["error_vigente"] = actual.get("error")
        notas.append(fila)
    return {
        "vigente": vigente,
        "total": len(notas),
        "derivadas_excluidas": derivadas,
        "cumplen_por_version": cumplen,
        "por_version_mas_alta": dict(sorted(mas_alta.items())),
        "faltantes_vigente": dict(sorted(faltan.items(), key=lambda kv: (-kv[1], kv[0]))),
        "notas": notas,
    }


def _notas_del_alcance(folder: Optional[str]) -> List[Path]:
    """Las notas que se validan sin `--path`: las de `folder`, o las de las secciones."""

    if folder:

        return list((_raiz() / folder).rglob("*.md"))

    else:

        # Solo las secciones canónicas. Barrer el vault entero con `rglob` desde
        # la raíz mete en el informe cualquier markdown que conviva con él
        # —`docs/`, notas de trabajo, un README— y los reprueba por no llevar
        # frontmatter, que es justo lo que no se les pide: no son notas del
        # vault. En el vault de pruebas eran 13 de las 26 «No frontmatter
        # block», todas de `docs/sdd/`. Qué cuenta como nota lo decide
        # `ORDERED_SECTIONS` (AP-05), no el disco.

        notes = [

            n

            for seccion in REQUIRED_FOLDERS

            for n in (_raiz() / seccion).rglob("*.md")

            if ".history" not in str(n) and not n.name.startswith("_")

        ]

        return notes


def check_structure() -> Dict[str, Any]:

    """Verify that the standard numbered folders exist."""

    missing = [f for f in REQUIRED_FOLDERS if not (_raiz() / f).exists()]

    return {"expected": len(REQUIRED_FOLDERS), "missing": missing}


def check_indexes() -> Dict[str, Any]:

    """Verify that required JSON indexes are present and readable."""

    invalid: List[str] = []

    for idx in REQUIRED_INDEXES:

        path = _raiz() / idx

        if not path.exists():

            invalid.append(f"{idx} (missing)")

        else:

            try:

                json.loads(path.read_text(encoding="utf-8"))

            except Exception:

                invalid.append(f"{idx} (unreadable)")

    return {"required": len(REQUIRED_INDEXES), "invalid": invalid}


def vault_validate(

    path: Optional[str] = None,

    folder: Optional[str] = None,

    check: str = "all",

    contrato: Optional[str] = None,

) -> Dict[str, Any]:

    """

    Validate frontmatter, folder structure, and index integrity.



    Args:

        path:   Relative path to a specific note (frontmatter check only).

        folder: Relative path to a folder — validates all notes inside.

        check:  "frontmatter" | "structure" | "indexes" | "all" | "cumplimiento"
                ("cumplimiento" no entra en "all": es un informe por versión,
                no una validación, y no cambia `ok`)

        contrato: versión mayor (`v18`..) cuyo contrato de nota se aplica en
                  vez del vigente. Solo cambia el juicio del frontmatter.



    Returns:

        {

          "valid":     [...],           # present when check includes frontmatter

          "invalid":   [{path, error}], # present when check includes frontmatter

          "structure": {expected, missing},

          "indexes":   {required, invalid}

        }

    """

    # AP-36: `--path "../x.md"` validaba un fichero ajeno y `--folder ..`
    # recorria el disco fuera del vault, informando de que existe y de que
    # campos le faltan. Mismo guard que vault_read.
    for ruta in (path, folder):
        if ruta:
            try:
                assert_within_vault(_raiz() / ruta, _raiz())
            except ValueError as exc:
                return emit_error("vault_validate", "INVALID_PATH", str(exc))

    if contrato is not None:
        try:
            contrato = contrato_de_version(contrato)["version"]
        except ValueError as exc:
            return emit_error("vault_validate", "INVALID_VALUE", str(exc),
                              pista=f"una de {VERSIONES_CON_CONTRATO[0]}..{VERSIONES_CON_CONTRATO[-1]}")

    result: Dict[str, Any] = {"ok": True}

    if contrato is not None:
        result["contract_version"] = contrato


    if check in ("frontmatter", "all"):

        fm = check_frontmatter(path, folder, contrato)

        result["valid"] = fm["valid"]

        result["invalid"] = fm["invalid"]

        if fm["invalid"]:

            result["ok"] = False


    if check == "cumplimiento":

        result["cumplimiento"] = check_cumplimiento(path, folder)


    if check in ("structure", "all"):

        st = check_structure()

        result["structure"] = st

        if st["missing"]:

            result["ok"] = False


    if check in ("indexes", "all"):

        idx = check_indexes()

        result["indexes"] = idx

        if idx["invalid"]:

            result["ok"] = False


    if not result["ok"]:
        # AP-52 (2026-10-01): el resultado de la medida se conserva entero;
        # lo que se añade es el código por el que el consumidor decide.
        partes = []
        if result.get("invalid"):
            partes.append(f"{len(result['invalid'])} nota(s) inválida(s)")
        if (result.get("structure") or {}).get("missing"):
            partes.append(f"{len(result['structure']['missing'])} carpeta(s) ausente(s)")
        if (result.get("indexes") or {}).get("invalid"):
            partes.append(f"{len(result['indexes']['invalid'])} índice(s) inválido(s)")
        # Solo índices ausentes —el caso de todo runtime recién creado— tiene
        # una recuperación ejecutable: la de INDEX_NOT_FOUND. Con notas o
        # carpetas mal, reindexar no lo arregla y el código no lo promete.
        indices = (result.get("indexes") or {}).get("invalid") or []
        solo_indices_ausentes = (
            len(partes) == 1 and indices
            and all(i.endswith("(missing)") for i in indices))
        result["error_code"] = (
            "INDEX_NOT_FOUND" if solo_indices_ausentes else "VALIDATION_FAILED")
        result["message"] = "Validación con problemas: " + ", ".join(partes) + "."
        result = completar_envelope("vault_validate", result)

    return result


def main():

    parser = argparse.ArgumentParser(

        description="Vault Validate -- blueprint: vault-obsidian-architecture.md",

        formatter_class=argparse.RawDescriptionHelpFormatter,

        epilog="""

Ejemplos:

  python vault_validate.py --check all

  python vault_validate.py --path "07_Knowledge/api.md" --check frontmatter

  python vault_validate.py --folder "01_Projects" --check frontmatter

  python vault_validate.py --check structure

  python vault_validate.py --check indexes

  python vault_validate.py --check cumplimiento --folder "07_Knowledge"



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - --check all valida frontmatter, estructura de carpetas e indices JSON

  - Campos CIA opcionales validados si presentes: cia_integrity (critical|high|medium|low),

    cia_availability (high|medium|low), cia_sensitivity (public|internal|restricted),

    dq_validated_at (ISO 8601 — escrito por vault_quality_check, no editar a mano)

""",

        allow_abbrev=False,
    )

    parser.add_argument("--path", help="Relative path to a specific note")

    parser.add_argument("--folder", help="Relative path to a folder to validate")

    parser.add_argument(

        "--check",

        choices=["frontmatter", "structure", "indexes", "all", "cumplimiento"],

        default="all",

        help=("What to validate (default: all). cumplimiento: informe de qué "
              "contrato de versión cumple cada nota y qué le falta para el vigente"),

    )

    parser.add_argument(
        "--contrato",
        help=("Versión mayor cuyo contrato de nota se aplica (v18..; por defecto, "
              "el vigente). Ver schemas/README.md"),
    )


    args = parser.parse_args()

    result = vault_validate(args.path, args.folder, args.check, args.contrato)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":

    sys.exit(wrap_main(main, "vault_validate"))

