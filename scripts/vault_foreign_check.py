#!/usr/bin/env python3
"""vault_foreign_check — regla 7: contrastar las medidas contra material ajeno.

La regla 7 dice que toda medida nueva se contrasta al menos una vez contra un
vault preexistente ajeno al estándar, y da la razón: `vault-sandbox/` lo genera
este repo y comparte sus supuestos, así que **no puede exhibir** la clase de
fallo que la regla persigue. Cinco defectos reales salieron solo al ejecutar
contra un vault de fuera.

Hasta ahora eso era disciplina personal: alguien se acordaba, o no. Esta tool lo
convierte en algo ejecutable.

    python scripts/vault_foreign_check.py --root <vault ajeno>
    python scripts/vault_foreign_check.py --root <vault> --json
    python scripts/vault_foreign_check.py --self-test   # sin vault a mano

## Por qué NO tiene destino por defecto

Todas las demás tools del repo autodetectan el vault y acaban en
`vault-sandbox/`. Ésta no puede: un contraste que cae al sandbox certifica la
medida contra el material que la medida ya sabe leer, y devuelve verde
precisamente en el caso que existe para detectar. Sin `--root` falla, y falla
diciendo qué le falta — no cae a ningún sitio "razonable". Es la única tool del
estándar para la que la autodetección sería un defecto y no una comodidad.

Por el mismo motivo **rechaza** cualquier raíz dentro de este repositorio.

## Solo lectura, sin excepciones

No escribe una línea en el vault de destino. Ni backups, ni índices, ni traces:
el destino puede ser un vault real de trabajo de alguien, y una tool de
diagnóstico que modifica lo que diagnostica no es una tool de diagnóstico. El
informe sale por stdout, o al fichero que se le indique con `--report` — que se
resuelve **fuera** del vault medido.

## Qué mide, y por qué separa "no hay" de "no pude leer"

Las medidas están escritas con el criterio del **consumidor** (AP-44), que es
Obsidian, y no con el del estándar:

* el frontmatter con `yaml.safe_load`, no con un regex por líneas;
* los wikilinks resueltos por **nombre de fichero y `aliases:`** — nunca por
  `title:`, que Obsidian no mira;
* el texto leído con varios encodings antes de declarar nada.

Y todo recuento distingue el cero medido del cero por fallo de lectura (AP-51).
Un vault ajeno es exactamente donde esa distinción se cobra: la mayoría de los
"defectos" que un estándar cree ver en material de fuera son su propio criterio
fallando.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_regex import RE_WIKILINK_DESTINO  # dueño único del patrón (AP-50)
from vault_audit import es_documentacion_del_estandar  # dueño único del criterio

sys.path.insert(0, str(Path(__file__).parent))

from vault_errors import emit_error, wrap_main

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Encodings que se prueban antes de declarar una nota ilegible. Un vault
#: preexistente trae ficheros que nadie normalizó nunca; declararlos inválidos
#: por no abrirlos en UTF-8 sería culpar al dato del criterio propio (AP-51).
ENCODINGS = ("utf-8", "utf-8-sig", "cp1252", "latin-1")

WIKILINK = RE_WIKILINK_DESTINO


class DestinoInvalido(Exception):
    """La raíz pedida no sirve para un contraste de regla 7.

    Lleva su propio `code` del ERROR_CATALOG: la tool que estrena la puerta de
    AP-52 no puede emitir sus errores fuera del contrato.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def validar_destino(root: Optional[str]) -> Path:
    """La comprobación que da sentido a la tool.

    Sin `--root` no hay default: caer al sandbox devolvería verde justo en el
    caso que la regla 7 existe para ver.
    """
    if not root:
        raise DestinoInvalido(
            "MISSING_REQUIRED_ARG",
            "--root es obligatorio y no tiene valor por defecto: un contraste "
            "de regla 7 contra el vault que genera este repo no contrasta nada.",
        )
    destino = Path(root).expanduser().resolve()
    if not destino.exists():
        raise DestinoInvalido("VAULT_NOT_FOUND", f"la raíz {destino} no existe")
    if not destino.is_dir():
        raise DestinoInvalido("INVALID_PATH", f"la raíz {destino} no es un directorio")
    try:
        destino.relative_to(REPO_ROOT)
    except ValueError:
        return destino
    raise DestinoInvalido(
        "INVALID_PATH",
        f"{destino} está dentro del repositorio del estándar. `vault-sandbox/` "
        "y todo lo que cuelga de aquí comparte los supuestos de las medidas: "
        "medir contra ello no puede exhibir el fallo que la regla 7 persigue.",
    )


def _leer(path: Path) -> Optional[str]:
    """El texto, o None si de verdad no se pudo leer con ningún encoding.

    Devolver None y contarlo aparte es la diferencia entre "esta nota no tiene
    frontmatter" y "no pude mirar esta nota" (AP-51).
    """
    for enc in ENCODINGS:
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, LookupError):
            continue
        except OSError:
            return None
    return None


def _frontmatter(texto: str) -> Any:
    """El frontmatter según `yaml.safe_load`, que es como lo lee el consumidor.

    Sentinelas: `None` si no hay bloque, `False` si lo hay y no parsea. Se
    distinguen porque son cosas distintas y agregarlas juntas es el error que
    AP-51 describe.
    """
    if not texto.startswith("---"):
        return None
    partes = texto.split("---", 2)
    if len(partes) < 3:
        return None
    import yaml

    try:
        datos = yaml.safe_load(partes[1])
    except yaml.YAMLError:
        # Solo el error de parseo, y solo aquí: un `except Exception` haría que
        # un fallo de la tool se contase como frontmatter roto del vault ajeno,
        # que es AP-51 exactamente en el sitio donde más caro sale — midiendo
        # material que no conocemos y que no puede defenderse.
        return False
    return datos if isinstance(datos, dict) else False


def contrastar(destino: Path) -> Dict[str, Any]:
    notas = [p for p in destino.rglob("*.md") if p.is_file()]

    ilegibles: List[str] = []
    sin_frontmatter = 0
    frontmatter_roto: List[str] = []
    con_frontmatter = 0

    #: nombre de fichero y aliases: los dos criterios con los que Obsidian
    #: resuelve un wikilink. `title:` no entra a propósito.
    destinos = {p.stem.lower() for p in notas}
    enlaces_totales = 0
    textos: Dict[Path, str] = {}

    for p in notas:
        texto = _leer(p)
        if texto is None:
            ilegibles.append(str(p.relative_to(destino)))
            continue
        textos[p] = texto
        fm = _frontmatter(texto)
        if fm is None:
            sin_frontmatter += 1
        elif fm is False:
            frontmatter_roto.append(str(p.relative_to(destino)))
        else:
            con_frontmatter += 1
            for alias in fm.get("aliases") or []:
                if isinstance(alias, str):
                    destinos.add(alias.lower())

    # La documentación del estándar que el consumidor copia dentro de su vault
    # —el manifiesto, la referencia de tools— cita sintaxis de wikilink como
    # ejemplo: `[[nota]]`, `[[carpeta/nota]]`. No son enlaces rotos del vault,
    # son la doc enseñando a escribirlos. Contarlos infla la medida justo en los
    # vaults consumidores, que son los que más doc copiada llevan.
    #
    # El criterio no se reescribe aquí: lo tiene `vault_audit` desde v40.5 —por
    # contenido y no por ubicación, que es lo que hace que una copia archivada
    # con sufijo de versión siga siendo doc—. Una segunda versión de la misma
    # regla diría otra cosa el día que una de las dos cambiara (AP-05).
    docs: List[str] = []
    rotos: List[Dict[str, str]] = []
    for p, texto in textos.items():
        rel = str(p.relative_to(destino))
        if es_documentacion_del_estandar(rel.replace("\\", "/"), texto):
            docs.append(rel)
            continue
        for m in WIKILINK.finditer(texto):
            enlaces_totales += 1
            objetivo = m.group(1).strip().split("/")[-1].lower()
            if objetivo and objetivo not in destinos:
                rotos.append({
                    "from": str(p.relative_to(destino)),
                    "target": m.group(1).strip(),
                })

    medidas = len(notas) - len(ilegibles)
    return {
        "notes_found": len(notas),
        "notes_measured": medidas,
        # Va junto al resultado y no enterrado: un recuento sobre `notes_measured`
        # no es un recuento sobre el vault, y quien lo lea tiene derecho a saberlo.
        "unreadable": ilegibles,
        "unreadable_count": len(ilegibles),
        "with_frontmatter": con_frontmatter,
        "without_frontmatter": sin_frontmatter,
        "frontmatter_unparseable": frontmatter_roto,
        # Qué se dejó fuera del recuento de enlaces, con nombre: una exclusión
        # silenciosa es indistinguible de un vault sin enlaces rotos.
        "standard_docs_excluded": docs,
        "standard_docs_excluded_count": len(docs),
        "wikilinks_total": enlaces_totales,
        "wikilinks_unresolved": len(rotos),
        "wikilinks_unresolved_sample": rotos[:20],
    }


def observaciones(m: Dict[str, Any]) -> List[str]:
    """Lo que un humano debe mirar, dicho sin adornos.

    No se emite un veredicto de "salud": esta tool no juzga el vault ajeno —
    juzga si **las medidas del estándar** sobreviven a material que no generó.
    """
    fuera = []
    if m["notes_found"] == 0:
        fuera.append(
            "0 notas .md: o la raíz no es un vault, o el contraste no ha medido nada. "
            "Un verde aquí no significa nada."
        )
    if m["unreadable_count"]:
        fuera.append(
            f"{m['unreadable_count']} notas ilegibles con {len(ENCODINGS)} encodings. "
            "Todo recuento de abajo es sobre las demás, no sobre el vault."
        )
    if m["frontmatter_unparseable"]:
        fuera.append(
            f"{len(m['frontmatter_unparseable'])} notas con frontmatter que no parsea "
            "por YAML. Antes de llamarlas inválidas, comprobar que Obsidian tampoco "
            "las lee: si las lee, el criterio roto es el nuestro (AP-44)."
        )
    if m["wikilinks_total"] and m["wikilinks_unresolved"] / m["wikilinks_total"] > 0.3:
        fuera.append(
            f"{m['wikilinks_unresolved']} de {m['wikilinks_total']} wikilinks sin "
            "resolver (>30%). Una proporción así casi nunca es el vault: suele ser "
            "la resolución la que no contempla algo — carpetas, alias, mayúsculas."
        )
    return fuera


def self_test() -> Dict[str, Any]:
    """Comprueba las negativas de la tool sin necesitar un vault ajeno.

    Existe porque la propiedad que hace útil a esta tool es lo que se **niega**
    a hacer, y eso sí se puede verificar en cualquier máquina. Sin esto, en un
    entorno sin vault ajeno la tool no tendría nada ejecutable y sería
    superficie publicada que nadie corre (AP-42).
    """
    casos = []

    for etiqueta, valor in (
        ("sin --root", None),
        ("vault-sandbox del repo", str(REPO_ROOT / "vault-sandbox")),
        ("la raíz del repo", str(REPO_ROOT)),
        ("una ruta inexistente", str(REPO_ROOT / "no-existe-jamas")),
    ):
        try:
            validar_destino(valor)
            casos.append({"case": etiqueta, "rejected": False})
        except DestinoInvalido as e:
            casos.append({"case": etiqueta, "rejected": True,
                          "code": e.code, "reason": str(e)})

    return {
        "ok": all(c["rejected"] for c in casos),
        "tool": "vault_foreign_check",
        "action": "self-test",
        "cases": casos,
        "hint": (
            "El self-test verifica que la tool se niega a medir donde no debe. "
            "NO sustituye al contraste: la regla 7 solo se cumple ejecutando "
            "contra un vault ajeno de verdad."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_foreign_check — regla 7: contraste contra un vault ajeno, en solo lectura",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:

  python scripts/vault_foreign_check.py --root "D:/vaults/notas-personales"
  python scripts/vault_foreign_check.py --root "D:/vaults/notas" --report informe.json
  python scripts/vault_foreign_check.py --self-test

No escribe nada en el vault medido. --root no tiene valor por defecto y
rechaza cualquier ruta dentro de este repositorio: un contraste contra el
material que el estandar genera no contrasta nada.
""",
    )
    parser.add_argument("--root", help="Raíz del vault AJENO a medir (obligatorio)")
    parser.add_argument("--report", help="Escribe el informe en este fichero (fuera del vault)")
    parser.add_argument("--self-test", action="store_true", dest="self_test",
                        help="Verifica las negativas de la tool, sin vault ajeno")
    args = parser.parse_args()

    if args.self_test:
        r = self_test()
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["ok"] else 1

    try:
        destino = validar_destino(args.root)
    except DestinoInvalido as e:
        print(json.dumps(
            emit_error("vault_foreign_check", e.code, str(e)),
            ensure_ascii=False,
        ))
        return 1

    medidas = contrastar(destino)
    resultado = {
        "ok": True,
        "tool": "vault_foreign_check",
        "root": str(destino),
        "read_only": True,
        **medidas,
        "observations": observaciones(medidas),
        "hint": (
            "Esta tool no juzga el vault: juzga si las medidas del estándar "
            "sobreviven a material que no generó. Una anomalía alta es antes "
            "sospechosa del criterio que del dato (AP-44)."
        ),
    }

    if args.report:
        salida = Path(args.report).expanduser().resolve()
        try:
            salida.relative_to(destino)
            print(json.dumps(
                emit_error(
                    "vault_foreign_check", "INVALID_PATH",
                    f"--report {salida} cae dentro del vault medido: esta tool no escribe ahí.",
                ),
                ensure_ascii=False,
            ))
            return 1
        except ValueError:
            pass
        salida.write_text(
            json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        resultado["report_path"] = str(salida)

    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_foreign_check"))
