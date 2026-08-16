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
    """
    original = list(vp.PREGUNTAS)
    try:
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
