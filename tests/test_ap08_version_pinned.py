"""AP-08 en el cuerpo: `version_pinned` cruzado con el manifiesto del repo (deuda #2).

La `prevention` de AP-08 pide desde v19 «agregar campo version_pinned al
frontmatter con la versión referenciada», y nadie lo emitía ni lo leía: medido
el 2026-10-09 en las copias de ocho consumidores, ninguna nota lo declara. Un
detector sobre un universo vacío saldría verde sin medir nada (AP-60), así que
el orden es el de la regla 3: el contrato lo declara, el escritor lo emite, y
`vault_drift_detect --mode vigencia` lo compara y publica su universo.

La forma es un mapa `paquete: versión`. La relación con el código la escribe
la nota, como `files:`; el detector no adivina qué librería menciona el cuerpo.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
for _ruta in (SCRIPTS, ROOT):
    if str(_ruta) not in sys.path:
        sys.path.insert(0, str(_ruta))

import vault_contrato_nota as contrato  # noqa: E402
from test_ap08_vigencia import _commit, _nota, _proyecto, _tool  # noqa: E402


def test_ap08_version_pinned_es_campo_opcional_del_contrato_v41():
    campo = contrato.CAMPOS["version_pinned"]
    assert campo["nivel"] == "opcional" and campo["norma"] == "AP-08"
    assert campo["tipo"] == "object"
    assert contrato.conocido_desde("version_pinned") == "v41"
    assert "version_pinned" not in contrato.campos_requeridos("07_Knowledge/x.md")
    assert contrato.errores_de_valor({"version_pinned": {"react": "18.2.0"}}) == []
    assert contrato.errores_de_valor({"version_pinned": "react 18"})
    assert contrato.errores_de_valor({"version_pinned": {"react": ""}})


def test_ap08_vault_write_emite_version_pinned(tmp_path):
    raiz = tmp_path / "vault"
    raiz.mkdir()
    assert _tool(raiz, "vault_init")[1]["ok"] is True
    rc, r = _tool(raiz, "vault_write", "--folder", "07_Knowledge", "--title", "Uso de React",
                  "--content", "Linea uno de la nota.\nLinea dos con mas palabras.\nLinea tres final.",
                  "--tags", "react", "--version-pinned", "react@18.2.0",
                  "--version-pinned", "@scope/pkg@2.1")
    assert rc == 0 and r["ok"] is True, r
    texto = (raiz / r["path"]).read_text(encoding="utf-8")
    fm = yaml.safe_load(texto.split("---", 2)[1])
    # Los valores salen como texto: `2.1` sin comillas volvería como float.
    assert fm["version_pinned"] == {"react": "18.2.0", "@scope/pkg": "2.1"}


def test_ap08_version_pinned_mal_formado_no_se_escribe(tmp_path):
    raiz = tmp_path / "vault"
    raiz.mkdir()
    assert _tool(raiz, "vault_init")[1]["ok"] is True
    rc, r = _tool(raiz, "vault_write", "--folder", "07_Knowledge", "--title", "Sin version",
                  "--content", "Linea uno de la nota.\nLinea dos con mas palabras.\nLinea tres final.",
                  "--tags", "react", "--version-pinned", "react")
    assert rc != 0 and r["ok"] is False, r
    assert not list((raiz / "07_Knowledge").glob("sin-version*.md"))


def test_ap08_vigencia_nombra_la_nota_anclada_a_una_version_que_ya_paso(tmp_path):
    raiz, repo = _proyecto(tmp_path)
    (repo / "package.json").write_text(json.dumps({
        "name": "demo", "version": "3.1.0",
        "dependencies": {"react": "^18.2.0"},
        "devDependencies": {"vitest": "latest"},
    }), encoding="utf-8")
    (repo / "requirements.txt").write_text("FastAPI==0.110.0\n# comentario\n", encoding="utf-8")
    _commit(repo, "otro.py", "2026-03-02T00:00:00+00:00")
    base = "project: demo\nstatus: active\nupdatedAt: 2026-06-01T00:00:00Z"
    _nota(raiz, "anclada", base + "\nversion_pinned:\n  react: '17.0.2'")
    _nota(raiz, "al-dia", base + "\nversion_pinned:\n  react: '18'\n  fastapi: '0.110.0'")
    _nota(raiz, "propia", base + "\nversion_pinned:\n  demo: '3.0'")
    _nota(raiz, "ajeno", base + "\nversion_pinned:\n  django: '4.2'")
    _nota(raiz, "sin-numero", base + "\nversion_pinned:\n  vitest: '1.0'")
    _nota(raiz, "ilegible", base + "\nversion_pinned: react 18")

    rc, r = _tool(raiz, "vault_drift_detect", "--project", "demo", "--mode", "vigencia")
    assert rc == 0 and r["ok"] is True, r
    vp = r["version_pinned"]
    assert vp["norm"] == "AP-08"
    assert vp["declaran"] == 6 and vp["comparadas"] == 3
    ancladas = {a["path"]: a for a in vp["ancladas"]}
    assert set(ancladas) == {"07_Knowledge/anclada.md", "07_Knowledge/propia.md"}
    assert ancladas["07_Knowledge/anclada.md"]["paquetes"] == [
        {"paquete": "react", "fijada": "17.0.2", "manifiesto": "^18.2.0",
         "fuente": "package.json"}]
    assert ancladas["07_Knowledge/propia.md"]["paquetes"][0]["manifiesto"] == "3.1.0"
    # Fuera de todo manifiesto, o con una versión sin número (`latest`): no se
    # juzga, se lista.
    assert vp["sin_comparar"] == [{"path": "07_Knowledge/ajeno.md", "paquetes": ["django"]},
                                    {"path": "07_Knowledge/sin-numero.md", "paquetes": ["vitest"]}]
    assert vp["ilegibles"] == ["07_Knowledge/ilegible.md"]
    assert r["action_required"] is True


def test_ap08_un_universo_vacio_se_publica_y_no_sale_verde_en_silencio(tmp_path):
    raiz, _ = _proyecto(tmp_path)
    _nota(raiz, "normal", "project: demo\nstatus: active\nupdatedAt: 2026-06-01T00:00:00Z")
    rc, r = _tool(raiz, "vault_drift_detect", "--project", "demo", "--mode", "vigencia")
    assert rc == 0 and r["ok"] is True, r
    vp = r["version_pinned"]
    assert vp["declaran"] == 0 and vp["comparadas"] == 0 and vp["ancladas"] == []
    # AP-60: cero comparadas no es «ninguna anclada»; el criterio lo dice.
    assert "ninguna nota declara" in vp["universo"]
