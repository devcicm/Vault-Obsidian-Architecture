"""La pregunta del consumidor, convertida en puerta.

`vault_produccion` mide algo que ninguna de las otras veinte puertas mira: que
cada promesa hecha a quien instala el toolkit tenga a alguien que la ejerza. Es
AP-44 subido un nivel — no «verificar con el criterio del consumidor» dentro de
una tool, sino verificar que el consumidor está representado en la sala.

Estos tests fijan las tres cosas que hacen que la puerta signifique algo:
la asimetría entre `cubierta` y `descubierta`, que el predicado se evalúe al
medir y no al importar, y que la guía sea derivada de verdad.
"""

from __future__ import annotations

import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_produccion as vp  # noqa: E402


def test_el_registro_esta_bien_formado():
    """Cada fila declara promesa, motivo, ejecutor y estado conocido."""
    vistos = set()
    for p in vp.PREGUNTAS:
        assert p["id"] not in vistos, f"id duplicado: {p['id']}"
        vistos.add(p["id"])
        assert p["estado"] in vp.ESTADOS, f"{p['id']}: estado {p['estado']}"
        assert callable(p["ejerce"]), (
            f"{p['id']}: `ejerce` tiene que ser un predicado. Descrito en prosa "
            "vuelve a ser un párrafo que nadie ejecuta, que es el fallo que "
            "este registro existe para no repetir."
        )
        for campo in ("pregunta", "por_que", "quien"):
            assert p[campo].strip(), f"{p['id']}: {campo} vacío"


def test_hoy_la_puerta_esta_verde():
    r = vp.check()
    assert r["ok"], (
        f"promesas sin ejecutor: {r['promesas_sin_ejecutor']}; "
        f"descubiertas sin motivo: {r['descubiertas_sin_motivo']}"
    )


def test_una_promesa_cubierta_sin_ejecutor_rompe_la_puerta():
    """Es el único caso que rompe: una mentira comprobable."""
    original = list(vp.PREGUNTAS)
    try:
        vp.PREGUNTAS.append({
            "id": "_fixture_rota", "pregunta": "¿?", "promesa": "—",
            "por_que": "—", "quien": "un fichero que no existe",
            "ejerce": lambda: vp._existe("no-existe-en-ningun-sitio.md"),
            "estado": "cubierta",
        })
        r = vp.check()
        assert not r["ok"]
        assert "_fixture_rota" in r["promesas_sin_ejecutor"]
    finally:
        vp.PREGUNTAS[:] = original


def test_una_descubierta_con_motivo_no_rompe_la_puerta():
    """Declararse honestamente no puede salir más caro que callarse.

    Es la misma asimetría que el repo ya decidió en v40.16 para las coberturas
    de norma: `cobertura_descubierta` con motivo escrito no cuenta como deuda.

    Se mide con Beta publicado: con Estable, una descubierta sí rompe la puerta
    a través de `madurez_declarada`, y eso lo fija
    `test_estable_con_descubiertas_rompe_la_puerta`.
    """
    original = list(vp.PREGUNTAS)
    try:
        # Beta siempre es coherente (`_madurez_coherente`), así que la fila de
        # madurez se ejerce como lo haría con Beta en pyproject.toml.
        vp.PREGUNTAS[:] = [
            dict(p, ejerce=lambda: True) if p["id"] == "madurez_declarada" else p
            for p in original
        ]
        vp.PREGUNTAS.append({
            "id": "_fixture_honesta", "pregunta": "¿?", "promesa": "—",
            "por_que": "—", "quien": "—",
            "ejerce": lambda: False, "estado": "descubierta",
            "motivo": "decisión sin tomar, y escrita",
        })
        assert vp.check()["ok"]
    finally:
        vp.PREGUNTAS[:] = original


def test_una_descubierta_sin_motivo_si_rompe():
    """Un hueco sin motivo es un hueco que nadie va a revisar."""
    original = list(vp.PREGUNTAS)
    try:
        vp.PREGUNTAS.append({
            "id": "_fixture_muda", "pregunta": "¿?", "promesa": "—",
            "por_que": "—", "quien": "—",
            "ejerce": lambda: False, "estado": "descubierta",
        })
        r = vp.check()
        assert not r["ok"]
        assert "_fixture_muda" in r["descubiertas_sin_motivo"]
    finally:
        vp.PREGUNTAS[:] = original


def test_un_predicado_que_no_puede_leer_no_cuenta_como_verde():
    """AP-51: un vacío por avería no debe ser indistinguible de un vacío legítimo."""
    original = list(vp.PREGUNTAS)

    def revienta():
        raise OSError("el fichero que medía ya no está")

    try:
        vp.PREGUNTAS.append({
            "id": "_fixture_averiada", "pregunta": "¿?", "promesa": "—",
            "por_que": "—", "quien": "—", "ejerce": revienta,
            "estado": "cubierta",
        })
        r = vp.check()
        assert not r["ok"]
        assert "_fixture_averiada" in r["promesas_sin_ejecutor"]
    finally:
        vp.PREGUNTAS[:] = original


def test_el_predicado_se_evalua_al_medir_y_no_al_importar():
    """AP-49: un binding congelado al importar mide el mundo de hace un rato."""
    llamadas = []
    original = list(vp.PREGUNTAS)
    try:
        vp.PREGUNTAS.append({
            "id": "_fixture_perezosa", "pregunta": "¿?", "promesa": "—",
            "por_que": "—", "quien": "—",
            "ejerce": lambda: (llamadas.append(1), True)[1],
            "estado": "cubierta",
        })
        vp.medir()
        vp.medir()
        assert len(llamadas) == 2
    finally:
        vp.PREGUNTAS[:] = original


def test_la_guia_es_derivada_y_no_se_edita_a_mano():
    r = vp.check_doc()
    assert r["ok"], (
        "docs/GUIA-DE-PRODUCCION.md diverge del registro. Se regenera con "
        "`python scripts/vault_produccion.py --guia`; lo escrito a mano se pierde."
    )


def test_la_guia_publica_los_huecos_en_vez_de_esconderlos():
    guia = vp._guia()
    for p in vp.PREGUNTAS:
        if p.get("motivo"):
            assert p["motivo"] in guia, f"{p['id']}: el motivo no llega a la guía"
        if p.get("hueco_conocido"):
            assert p["hueco_conocido"] in guia, f"{p['id']}: el hueco no llega a la guía"


def test_la_puerta_esta_registrada_en_vault_gate():
    """Una tool que no está en el registro no la ejecuta la CI, y la CI ya
    aprendió en v40.19 que enumerar puertas a mano las deja quietas."""
    import vault_gate
    ids = {p["id"] for p in vault_gate.PUERTAS}
    assert "produccion" in ids


def test_el_dueno_es_una_hoja():
    """No importa ningún registro del repo, a propósito.

    Preguntarle al registro qué promete el producto sería medir con el propio
    criterio (AP-44), que es justo el fallo del que nace esta tool.
    """
    import ast
    arbol = ast.parse((RAIZ / "scripts" / "vault_produccion.py").read_text(encoding="utf-8"))
    permitidos = {"vault_errors"}
    for nodo in ast.walk(arbol):
        nombres = []
        if isinstance(nodo, ast.Import):
            nombres = [a.name for a in nodo.names]
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            nombres = [nodo.module]
        for n in nombres:
            base = n.split(".")[0]
            assert not base.startswith("vault_") or base in permitidos, (
                f"vault_produccion importa {base}: deja de ser hoja"
            )


def test_el_classifier_publicado_es_estable_y_lo_sostiene_el_registro():
    """v40.34 publicó Beta hasta que la Fase 6 cerrase las descubiertas; cerradas
    (2026-10-04), se publica Estable. Si una fila vuelve a quedar descubierta,
    este test cae junto con la puerta: la etiqueta no puede ir por delante."""
    proj = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    assert vp.CLASSIFIER_ESTABLE in proj
    assert vp.CLASSIFIER_BETA not in proj
    assert vp._madurez_coherente()


def _con_classifier(tmp_path, monkeypatch, classifier):
    (tmp_path / "pyproject.toml").write_text(
        f'classifiers = [\n    "{classifier}",\n]\n', encoding="utf-8")
    monkeypatch.setattr(vp, "RAIZ", tmp_path)


def test_estable_con_descubiertas_rompe_la_puerta(tmp_path, monkeypatch):
    """Lo que había hasta v40.34: 5 - Production/Stable con huecos declarados."""
    _con_classifier(tmp_path, monkeypatch, vp.CLASSIFIER_ESTABLE)
    # La propiedad, no el registro de hoy: desde v40.34 no queda ninguna
    # descubierta, y el test no puede depender de que las haya.
    una_abierta = [dict(p, estado="descubierta", motivo="fixture")
                   if p["id"] == "wheel_instalada_funciona" else p for p in vp.PREGUNTAS]
    monkeypatch.setattr(vp, "PREGUNTAS", una_abierta)
    assert not vp._madurez_coherente()


def test_estable_sin_descubiertas_es_coherente(tmp_path, monkeypatch):
    """Subir a 5 se gana cerrando huecos, no se prohíbe."""
    _con_classifier(tmp_path, monkeypatch, vp.CLASSIFIER_ESTABLE)
    cerradas = [dict(p, estado="cubierta") for p in vp.PREGUNTAS]
    monkeypatch.setattr(vp, "PREGUNTAS", cerradas)
    assert vp._madurez_coherente()


def test_sin_classifier_de_madurez_no_cuenta_como_verde(tmp_path, monkeypatch):
    _con_classifier(tmp_path, monkeypatch, "Programming Language :: Python :: 3")
    assert not vp._madurez_coherente()


def test_la_wheel_sin_gobernanza_se_mide_y_no_se_afirma(tmp_path, monkeypatch):
    """Sin el hook declarado en pyproject, la promesa no se ejerce."""
    assert vp._wheel_sin_gobernanza()
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    monkeypatch.setattr(vp, "RAIZ", tmp_path)
    assert not vp._wheel_sin_gobernanza()


def test_el_mcp_instalable_se_mide_y_no_se_afirma(tmp_path, monkeypatch):
    """P3: sin package data del servidor en pyproject, la promesa no se ejerce."""
    promesa = next(p for p in vp.PREGUNTAS if p["id"] == "mcp_requiere_checkout")
    assert promesa["estado"] == "cubierta" and promesa["ejerce"]()
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    monkeypatch.setattr(vp, "RAIZ", tmp_path)
    assert not vp._mcp_en_la_wheel()


def _raiz_falsa(tmp_path, monkeypatch, tools, fuera=()):
    import json
    (tmp_path / "vault" / "meta_toolkit").mkdir(parents=True)
    (tmp_path / "empaquetado").mkdir()
    (tmp_path / "vault_toolkit" / "operations").mkdir(parents=True)
    (tmp_path / "vault_toolkit" / "operations" / "vault_a.py").write_text("", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project.scripts]\nvault = "vault.product_cli:main"\n', encoding="utf-8")
    (tmp_path / "vault" / "meta_toolkit" / "tools-catalog.json").write_text(
        json.dumps({"tools": tools}), encoding="utf-8")
    (tmp_path / "empaquetado" / "fuera-de-la-wheel.json").write_text(
        json.dumps({"modulos": list(fuera)}), encoding="utf-8")
    monkeypatch.setattr(vp, "RAIZ", tmp_path)


def test_vault_run_se_mide_contra_el_catalogo_instalado(tmp_path, monkeypatch):
    """Hasta v40.34 bastaba con que pyproject dijera `[project.scripts]`."""
    assert vp._vault_run_resuelve_el_producto()
    a = {"name": "vault_a", "script": "vault_a.py",
         "execution_module": "vault_toolkit.operations.vault_a"}
    nativa = {"name": "vault_js", "script": "", "execution_module": None}
    gobierno = {"name": "vault_g", "script": "vault_g.py", "execution_module": None}
    _raiz_falsa(tmp_path, monkeypatch, [a, nativa, gobierno], fuera=["vault_g"])
    assert vp._vault_run_resuelve_el_producto()

    sin_modulo = {"name": "vault_b", "script": "vault_b.py", "execution_module": None}
    (tmp_path / "vault" / "meta_toolkit" / "tools-catalog.json").write_text(
        __import__("json").dumps({"tools": [a, sin_modulo]}), encoding="utf-8")
    assert not vp._vault_run_resuelve_el_producto()

    modulo_fantasma = dict(a, execution_module="vault_toolkit.operations.vault_z")
    (tmp_path / "vault" / "meta_toolkit" / "tools-catalog.json").write_text(
        __import__("json").dumps({"tools": [modulo_fantasma]}), encoding="utf-8")
    assert not vp._vault_run_resuelve_el_producto()


def test_la_wheel_probada_exige_venv_y_fuente_retirada(tmp_path, monkeypatch):
    assert vp._wheel_probada_sin_la_fuente()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "vault-ci.yml").write_text(
        "run: python tests/run_product_gates.py\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    for gate in ("clean_install_gate.py", "memory_recovery_e2e_gate.py"):
        (tmp_path / "tests" / gate).write_text(
            'run(["-m", "venv"])\nreport = {"source_tree_physically_absent": True}\n',
            encoding="utf-8")
    monkeypatch.setattr(vp, "RAIZ", tmp_path)
    # Declarar la ausencia en el informe no es retirar la fuente.
    assert not vp._wheel_probada_sin_la_fuente()


def test_memoria_para_agentes_exige_el_perfil_y_la_ejecucion(tmp_path, monkeypatch):
    """Un banco que hablara con el servidor entero, o un test que no lo
    ejecutara, no ejerce la promesa del agente: el predicado tiene que caer."""
    (tmp_path / "tests").mkdir()
    banco = (vp.RAIZ / "tests" / "banco_agente.py").read_text(encoding="utf-8")
    test = (vp.RAIZ / "tests" / "test_banco_agente.py").read_text(encoding="utf-8")
    monkeypatch.setattr(vp, "RAIZ", tmp_path)

    def con(b, t):
        (tmp_path / "tests" / "banco_agente.py").write_text(b, encoding="utf-8")
        (tmp_path / "tests" / "test_banco_agente.py").write_text(t, encoding="utf-8")
        return vp._banco_de_agente()

    assert con(banco, test)
    assert not con(banco.replace('"VAULT_MCP_PERFIL": PERFIL', "{}"), test)
    assert not con(banco, test.replace("banco.correr(", "dict("))
    (tmp_path / "tests" / "test_banco_agente.py").unlink()
    assert not vp._banco_de_agente()
