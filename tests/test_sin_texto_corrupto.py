"""El código del producto no lleva fragmentos CJK colados en la prosa.

Medido el 2026-10-01: seis sitios con palabras sueltas en chino o japonés en
mitad de comentarios y docstrings en español (`sin血行`, `para文件名`,
`初始化ados`, …), uno de ellos en el `purpose` de `vault_delete` que el
catálogo MCP enseña a cada agente. Ninguno lo vio una puerta: el texto es
UTF-8 válido y Python lo acepta.

Los módulos que tratan escrituras no latinas a propósito —sus ejemplos de
normalización son japonés y cirílico— están declarados abajo con el motivo.
Los tests no se miden: ahí un título en chino es un dato de prueba.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ZONAS = ("scripts", "vault", "cli", "vault_toolkit")
FICHEROS_SUELTOS = ("mcp/nodejs/tools-catalog.json", "scripts/README.md",
                    "AGENTS.md")

# ruta POSIX relativa -> por qué puede llevar CJK
DECLARADOS = {
    "vault/indices/vocabulario.py": "ejemplos de tags no latinos que no se pliegan",
    "vault/kernel/normalizacion.py": "ejemplo del dakuten que NFKD no debe quitar",
}

CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯]")


def _candidatos():
    for zona in ZONAS:
        for p in (ROOT / zona).rglob("*"):
            if p.suffix in (".py", ".mjs", ".json", ".md") and "__pycache__" not in p.parts:
                yield p
    for rel in FICHEROS_SUELTOS:
        yield ROOT / rel


def test_ningun_fragmento_cjk_fuera_de_los_declarados():
    hallados = []
    for p in _candidatos():
        rel = p.relative_to(ROOT).as_posix()
        if rel in DECLARADOS or "_archived" in p.parts or not p.is_file():
            continue
        texto = p.read_text(encoding="utf-8", errors="replace")
        for n, linea in enumerate(texto.splitlines(), 1):
            if CJK.search(linea):
                hallados.append(f"{rel}:{n}: {linea.strip()[:80]}")
    assert not hallados, "\n".join(hallados)


def test_el_detector_ve_el_caso_medido():
    assert CJK.search("sin血行 un Exception")
    assert CJK.search("candidatos初始化ados")
    assert not CJK.search("Straße, Über, Проект, café")


def test_los_declarados_siguen_existiendo():
    for rel in DECLARADOS:
        assert (ROOT / rel).is_file(), rel
