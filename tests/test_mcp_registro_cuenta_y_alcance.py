"""El registro publica **cuántas** notas tiene el vault y **qué cuenta**.

Dos defectos medidos el 2026-11-08 en el vault `vault dev codex`:

1. La raíz explícita (`VAULT_ROOT`) que no sigue la convención del
   descubrimiento (`vault-*` o `vault`) se registraba con `notes: 0`: el vault
   aparecía **vacío** aunque tuviera cientos de notas. La corrección existía
   en el árbol local de otra máquina y no había llegado al repositorio.
2. La cifra no decía **qué cuenta**: cinco medidas distintas de lo mismo
   (194 por `/health`, 207 por la auditoría, 242 en disco, 243 por
   `vault_list`, 188 indexadas) sin que ninguna declarara su alcance.

Aquí se comprueba con el criterio del consumidor: una sesión MCP real sobre
un vault cuyo nombre **no** sigue la convención (el caso que fallaba).
"""

import json

from test_mcp_runner import SesionMCP, _init_vault


def _registro(sesion):
    r = sesion.llamar("vault_registry", {})
    return json.loads(r["result"]["content"][0]["text"])


def test_el_vault_explicito_no_aparece_vacio(tmp_path):
    """El caso que fallaba: un vault cuyo nombre no sigue la convención."""
    vault = _init_vault(tmp_path / "vault dev codex")
    sesion = SesionMCP(vault)
    try:
        registro = _registro(sesion)
    finally:
        sesion.cerrar()

    entradas = {v["name"]: v for v in registro["vaults"]}
    explicito = entradas.get("vault dev codex")
    assert explicito is not None, list(entradas)
    assert explicito["notes"] > 0, explicito
    # El alcance va publicado con la cifra: sin él, un número no dice qué
    # cuenta y dos medidas no se pueden comparar.
    assert explicito.get("notes_scope"), explicito


def test_la_cuenta_es_la_de_los_ficheros_visibles(tmp_path):
    """La cifra es la del alcance declarado: .md visibles, sin carpetas
    ocultas ni node_modules."""
    vault = _init_vault(tmp_path / "vault dev codex")
    # Una nota visible más una copia en carpeta oculta: la segunda no cuenta.
    (vault / "07_Knowledge" / "visible.md").write_text("# Visible\n", encoding="utf-8")
    oculto = vault / ".history"
    oculto.mkdir(exist_ok=True)
    (oculto / "copia.md").write_text("# Copia\n", encoding="utf-8")

    sesion = SesionMCP(vault)
    try:
        registro = _registro(sesion)
    finally:
        sesion.cerrar()

    entradas = {v["name"]: v for v in registro["vaults"]}
    explicito = entradas["vault dev codex"]
    visibles = [p for p in vault.rglob("*.md")
                if not any(parte.startswith(".") for parte in p.relative_to(vault).parts)]
    assert explicito["notes"] == len(visibles), (explicito["notes"], len(visibles))
    assert explicito["notes"] < len(list(vault.rglob("*.md"))), explicito
