"""El criterio «esta tool no tiene script Python», con un solo dueño (v40.17).

El conjunto estaba escrito tres veces —`cli/registry.py`, el `.mjs` y ningún
sitio que los comparase— a través de una frontera de lenguaje. Es AP-05 en el
camino de ejecución, y ya cobró una vez: siete tools se despachaban como
nativas en JS mientras `vault_smoke` probaba el `.py` que el agente no tocaba,
de modo que `vault_graph` devolvía `ok: true` sin regenerar nada.

El test que decide si esto sirve de algo es
`test_una_divergencia_en_el_json_rompe_la_puerta`: los tres pueden coincidir hoy
por casualidad. Lo que hay que probar es que dejar de coincidir se ve.
"""

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ))

import vault_mcp_catalog as MC  # noqa: E402

CATALOGO = RAIZ / "mcp" / "nodejs" / "tools-catalog.json"
SERVIDOR = RAIZ / "mcp" / "nodejs" / "vault-mcp-server.mjs"


# ── Un dueño ─────────────────────────────────────────────────────────────────

def test_el_dueno_es_el_catalogo_python():
    assert MC.NATIVE_JS_TOOLS, "el conjunto quedó vacío: nadie despacharía en JS"


def test_la_cli_no_declara_su_propia_copia():
    """Si `cli/registry.py` volviera a decidirlo, el guard mediría dos cosas
    que ya no tienen por qué coincidir."""
    from cli.registry import NATIVE_JS_TOOLS as DE_LA_CLI

    assert set(DE_LA_CLI) == set(MC.NATIVE_JS_TOOLS)


def test_el_catalogo_json_lo_publica():
    """Sin esto el `.mjs` se queda con su respaldo y el enganche es decorativo."""
    d = json.loads(CATALOGO.read_text(encoding="utf-8"))
    assert set(d.get("js_native_tools", [])) == set(MC.NATIVE_JS_TOOLS), (
        "regenera con `python scripts/vault_mcp_catalog.py --sync`"
    )


def test_el_servidor_lee_del_catalogo_y_no_solo_de_su_literal():
    texto = SERVIDOR.read_text(encoding="utf-8")
    assert "data.js_native_tools" in texto, (
        "el `.mjs` volvió a decidirlo por su cuenta: el literal es respaldo, "
        "no la fuente"
    )
    assert "let JS_NATIVE_TOOLS" in texto, (
        "con `const` el catálogo no puede sobreescribirlo"
    )


def test_el_respaldo_del_servidor_tampoco_diverge():
    """Un respaldo que nadie compara es la segunda declaración otra vez: basta
    con que el catálogo no cargue para que las dos fronteras despachen
    distinto."""
    medido = MC._js_native_del_servidor()
    assert medido is not None, "dejó de encontrarse el literal en el `.mjs`"
    assert medido == set(MC.NATIVE_JS_TOOLS)


# ── Y que el guard muerda ────────────────────────────────────────────────────

def test_una_divergencia_en_el_json_rompe_la_puerta(monkeypatch):
    """**El criterio que decide si el guard es real** (AP-44)."""
    monkeypatch.setattr(MC, "NATIVE_JS_TOOLS", frozenset({"vault_backup_base64"}))
    r = MC.check_sync()
    assert r["ok"] is False
    assert any("js_native_tools" in d for d in r["diffs"])


def test_una_divergencia_en_el_mjs_rompe_la_puerta(monkeypatch):
    """La frontera que no se podía medir desde Python hasta v40.17."""
    monkeypatch.setattr(
        MC, "_js_native_del_servidor", lambda: {"vault_backup_base64", "inventada"}
    )
    r = MC.check_sync()
    assert r["ok"] is False
    assert any("(mjs)" in d for d in r["diffs"])


def test_un_mjs_ausente_no_se_lee_como_conjunto_vacio(monkeypatch, tmp_path):
    """AP-51: vacío y ausente no son lo mismo — leer un fichero que no está
    como `set()` reportaría una divergencia inventada en cada consumidor que
    no lleve el servidor MCP."""
    monkeypatch.setattr(MC, "REPO_ROOT", tmp_path)
    assert MC._js_native_del_servidor() is None
    assert MC.check_sync()["ok"] is True


def test_ninguna_js_native_tiene_script_python():
    """El criterio tiene que seguir siendo verdad: si una de ellas estrenara
    `.py`, el despacho JS la dejaría sin ejecutar."""
    for nombre in MC.NATIVE_JS_TOOLS:
        entrada = MC.TOOLS_CATALOG.get(nombre)
        if entrada is None:
            continue
        script = entrada.get("script")
        if script:
            assert not (RAIZ / "scripts" / script).exists(), (
                f"{nombre} se despacha en JS pero ya tiene {script}: el "
                f"script no se ejecutaría nunca"
            )


def test_la_regex_del_respaldo_no_se_traga_otro_set(monkeypatch, tmp_path):
    """Que lea el conjunto correcto y no el primero que encuentre."""
    falso = tmp_path / "mcp" / "nodejs"
    falso.mkdir(parents=True)
    (falso / "vault-mcp-server.mjs").write_text(
        'const OTRO = new Set(["ruido"]);\n'
        'let JS_NATIVE_TOOLS = new Set([\n  "a", "b",\n]);\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(MC, "REPO_ROOT", tmp_path)
    assert MC._js_native_del_servidor() == {"a", "b"}


def test_el_comentario_del_mjs_sigue_registrando_por_que():
    """La no-derogación aplica también al motivo: el párrafo que cuenta el
    fallo de las siete tools es la única memoria de por qué existe el conjunto."""
    texto = SERVIDOR.read_text(encoding="utf-8")
    assert re.search(r"AP-05 en el camino de ejecuci", texto)
