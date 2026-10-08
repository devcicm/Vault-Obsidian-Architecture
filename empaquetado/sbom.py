"""SBOM del paquete en SPDX 2.2 (ISO/IEC 5962:2021), con su inventario de licencias.

Quien instala la wheel recibe código de este repo y de sus dependencias. Saber
qué recibe —qué paquetes, en qué versión, bajo qué licencia— no puede depender
de leer `pyproject.toml` a mano: es lo que pide la gestión de cumplimiento de
licencias de ISO/IEC 5230 (OpenChain) y lo que el formato SPDX de ISO/IEC 5962
hace legible por máquina.

**Nada se escribe a mano.** El nombre, la versión, la licencia y las
dependencias salen de `pyproject.toml`; la versión y la licencia de cada
dependencia, de los metadatos del paquete instalado. Lo que no se puede medir
sale como `NOASSERTION`, que es el valor que SPDX reserva para «no se afirma»:
una licencia supuesta en un inventario de licencias es peor que un hueco.

Solo stdlib, y sin `tomllib` (3.11+): la CI lo ejecuta en el piso 3.9.

    python empaquetado/sbom.py                       # a stdout
    python empaquetado/sbom.py --salida dist/sbom.spdx.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

RAIZ = Path(__file__).resolve().parent.parent
NOASSERTION = "NOASSERTION"

#: Classifier de Trove → identificador SPDX. Solo las que aparecen o pueden
#: aparecer aquí; una que falte sale como NOASSERTION, nunca adivinada.
_TROVE_A_SPDX = {
    "License :: OSI Approved :: MIT License": "MIT",
    "License :: OSI Approved :: Apache Software License": "Apache-2.0",
    "License :: OSI Approved :: BSD License": NOASSERTION,  # BSD-2 o BSD-3: no se sabe
    "License :: OSI Approved :: Python Software Foundation License": "PSF-2.0",
}
_SPDX_CONOCIDOS = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "PSF-2.0", "ISC"}


def _proyecto(pyproject: Path) -> Dict[str, Any]:
    texto = pyproject.read_text(encoding="utf-8")

    def campo(nombre: str) -> str:
        m = re.search(rf'^{nombre}\s*=\s*"([^"]*)"', texto, re.M)
        return m.group(1) if m else ""

    bloque = re.search(r"^dependencies\s*=\s*\[(.*?)\]", texto, re.M | re.S)
    deps = re.findall(r'"([^"]+)"', bloque.group(1)) if bloque else []
    classifiers = re.findall(r'"(License :: [^"]+)"', texto)
    return {
        "name": campo("name"),
        "version": campo("version"),
        "license": _licencia_de(None, classifiers),
        "dependencies": deps,
    }


def _licencia_de(expresion: Optional[str], classifiers: List[str]) -> str:
    """Licencia declarada en SPDX: la expresión si es un id conocido, si no el classifier."""
    expresion = (expresion or "").strip()
    if expresion in _SPDX_CONOCIDOS:
        return expresion
    for c in classifiers:
        if c in _TROVE_A_SPDX:
            return _TROVE_A_SPDX[c]
    return NOASSERTION


def _nombre_de_requisito(req: str) -> str:
    return re.split(r"[\s<>=!~;\[(]", req.strip(), maxsplit=1)[0]


def _dependencia(req: str) -> Dict[str, str]:
    """Versión y licencia de una dependencia, leídas del paquete instalado."""
    from importlib import metadata

    nombre = _nombre_de_requisito(req)
    try:
        meta = metadata.metadata(nombre)
        version = metadata.version(nombre)
    except metadata.PackageNotFoundError:
        return {"name": nombre, "requirement": req, "version": NOASSERTION,
                "license": NOASSERTION}
    licencia = _licencia_de(
        meta.get("License-Expression") or meta.get("License"),
        meta.get_all("Classifier") or [],
    )
    return {"name": nombre, "requirement": req, "version": version, "license": licencia}


def _ref(nombre: str) -> str:
    return "SPDXRef-Package-" + re.sub(r"[^A-Za-z0-9.-]", "-", nombre)


def _paquete(nombre: str, version: str, licencia: str, copyright_: str) -> Dict[str, Any]:
    p = {
        "SPDXID": _ref(nombre),
        "name": nombre,
        "downloadLocation": NOASSERTION,
        "filesAnalyzed": False,
        "licenseConcluded": NOASSERTION,
        "licenseDeclared": licencia,
        "copyrightText": copyright_,
    }
    if version != NOASSERTION:
        p["versionInfo"] = version
    return p


def construir(raiz: Path = RAIZ, ahora: Optional[datetime] = None) -> Dict[str, Any]:
    """El documento SPDX del paquete y sus dependencias directas."""
    proyecto = _proyecto(raiz / "pyproject.toml")
    licencia = raiz / "LICENSE"
    copyright_ = NOASSERTION
    if licencia.is_file():
        m = re.search(r"^Copyright .*$", licencia.read_text(encoding="utf-8"), re.M)
        copyright_ = m.group(0).strip() if m else NOASSERTION
    deps = [_dependencia(r) for r in proyecto["dependencies"]]
    raiz_ref = _ref(proyecto["name"])
    ahora = (ahora or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "spdxVersion": "SPDX-2.2",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{proyecto['name']}-{proyecto['version']}",
        "documentNamespace": (
            f"https://spdx.org/spdxdocs/{proyecto['name']}-{proyecto['version']}-{uuid.uuid4()}"
        ),
        "creationInfo": {
            "created": ahora,
            "creators": ["Tool: empaquetado/sbom.py"],
        },
        "packages": [
            _paquete(proyecto["name"], proyecto["version"], proyecto["license"], copyright_),
            *[_paquete(d["name"], d["version"], d["license"], NOASSERTION) for d in deps],
        ],
        "relationships": [
            {"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES",
             "relatedSpdxElement": raiz_ref},
            *[
                {"spdxElementId": raiz_ref, "relationshipType": "DEPENDS_ON",
                 "relatedSpdxElement": _ref(d["name"])}
                for d in deps
            ],
        ],
    }


def inventario(doc: Dict[str, Any]) -> List[Dict[str, str]]:
    """Paquete → licencia declarada: la lista que revisa quien redistribuye."""
    return [
        {"name": p["name"], "version": p.get("versionInfo", NOASSERTION),
         "license": p["licenseDeclared"]}
        for p in doc["packages"]
    ]


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--salida", help="fichero donde escribir el SBOM (por defecto, stdout)")
    ap.add_argument("--inventario", action="store_true",
                    help="emite solo el inventario de licencias")
    args = ap.parse_args(argv)
    doc = construir()
    salida = inventario(doc) if args.inventario else doc
    texto = json.dumps(salida, ensure_ascii=False, indent=2) + "\n"
    if args.salida:
        destino = Path(args.salida)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(texto, encoding="utf-8")
    else:
        sys.stdout.write(texto)
    # Una dependencia sin licencia afirmada no rompe el SBOM, pero sí la
    # promesa de inventario: quien redistribuye no sabe qué está aceptando.
    sin_licencia = [p["name"] for p in doc["packages"] if p["licenseDeclared"] == NOASSERTION]
    if sin_licencia:
        sys.stderr.write(f"sin licencia afirmada: {', '.join(sin_licencia)}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
