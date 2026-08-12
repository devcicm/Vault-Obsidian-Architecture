"""Un catálogo sin servicio crece por acumulación.

`GROUPS` decía en qué cajón está cada tool; `CONTEXTS` decía en qué frontera vive.
Ninguno de los dos decía **a qué sirve**, así que una tool nueva no tenía contra qué
justificarse. `vault_servicio` es el registro que cierra esa pregunta, y estos tests
comprueban lo único que lo convierte en registro y no en prosa: que la trazabilidad
se exija de verdad y que el guard muerda cuando se rompe.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_servicio as srv  # noqa: E402


def test_hay_un_solo_servicio_y_toda_capacidad_lo_sirve():
    """Dos servicios serían dos productos, y este repo es uno."""
    assert srv.SERVICIO["id"] == "memoria_documental_gobernada"
    assert {d["sirve_a"] for d in srv.CAPACIDADES.values()} == {srv.SERVICIO["id"]}


def test_la_restriccion_de_no_tener_base_de_datos_esta_declarada_con_motivo():
    """Es decisión de producto, no limitación pendiente — y por eso lleva motivo.

    Sin el motivo escrito, la primera vez que alguien quiera buscar más rápido
    la lee como una carencia y añade un índice externo.
    """
    ids = {r["id"] for r in srv.SERVICIO["restricciones"]}
    assert "sin_base_de_datos" in ids
    assert all(r["motivo"] and r["declarada_en"] for r in srv.SERVICIO["restricciones"])


def test_la_trazabilidad_esta_completa():
    """Sin baseline a propósito: los 37 grupos se clasifican en la misma tanda."""
    resultado = srv.check(strict=True)
    assert resultado["ok"], resultado
    assert resultado["orphan_groups"] == []
    assert resultado["unknown_groups"] == []
    assert resultado["duplicated_groups"] == []
    assert resultado["empty_capabilities"] == []


def test_toda_tool_del_catalogo_llega_hasta_el_servicio():
    """La cadena entera, no solo sus eslabones por separado."""
    filas = srv.trazabilidad()
    assert len(filas) == srv.check()["tools_total"]
    sin_capacidad = [f["tool"] for f in filas if not f["capability"]]
    assert sin_capacidad == [], sin_capacidad
    assert all(f["service"] == srv.SERVICIO["id"] for f in filas)


def test_son_tres_capacidades_porque_la_medida_no_cabia_en_dos():
    """`CLAUDE.md` declara dos ejes; el catálogo tiene tres.

    El Grupo 35 gobierna el estándar —no las notas de nadie— y el Grupo 26 sirve a
    la consulta pese a caer en el rango 1–33. Meter esas 17 tools en un eje que no
    sirven habría sido el fallo que este registro existe para evitar. Si alguien
    reduce esto a dos capacidades, que sea porque reclasificó los grupos, no porque
    la prosa de `CLAUDE.md` le pesó más que la medida.
    """
    assert set(srv.CAPACIDADES) == {
        "escritura_a_gobernanza",
        "consulta_a_contexto",
        "gobernanza_del_estandar",
    }
    por_grupo = srv.capacidad_por_grupo()
    assert por_grupo[35] == "gobernanza_del_estandar"
    assert por_grupo[26] == "consulta_a_contexto"
    assert por_grupo[34] == "consulta_a_contexto"
    # Los dos desajustes llevan su motivo escrito en el registro, no en un commit.
    assert srv.CAPACIDADES["gobernanza_del_estandar"]["nota"]
    assert srv.CAPACIDADES["consulta_a_contexto"]["nota"]


# ── Que el guard muerda ──────────────────────────────────────────────────────

def test_un_grupo_sin_capacidad_rompe_la_puerta(monkeypatch):
    """Sin esto, el test de arriba solo dice que hoy están todos clasificados."""
    inventado = {
        nombre: dict(datos, grupos=[g for g in datos["grupos"] if g != 13])
        for nombre, datos in srv.CAPACIDADES.items()
    }
    monkeypatch.setattr(srv, "CAPACIDADES", inventado)

    resultado = srv.check()
    assert resultado["ok"] is False
    assert [h["group_id"] for h in resultado["orphan_groups"]] == [13]


def test_un_grupo_en_dos_capacidades_rompe_la_puerta(monkeypatch):
    """El cajón compartido: la tool serviría a dos cosas y a ninguna."""
    inventado = dict(srv.CAPACIDADES)
    inventado["consulta_a_contexto"] = dict(
        srv.CAPACIDADES["consulta_a_contexto"],
        grupos=srv.CAPACIDADES["consulta_a_contexto"]["grupos"] + [13],
    )
    monkeypatch.setattr(srv, "CAPACIDADES", inventado)

    resultado = srv.check()
    assert resultado["ok"] is False
    assert [d["group_id"] for d in resultado["duplicated_groups"]] == [13]


def test_una_capacidad_que_reclama_un_grupo_inexistente_rompe_la_puerta(monkeypatch):
    """El caso al revés: la capacidad promete algo que nadie realiza.

    Es como muere un registro: se declara la intención, se borra el grupo que la
    cumplía y queda la promesa sola. Aquí la promesa sola falla.
    """
    inventado = dict(srv.CAPACIDADES)
    inventado["gobernanza_del_estandar"] = dict(
        srv.CAPACIDADES["gobernanza_del_estandar"], grupos=[35, 999]
    )
    monkeypatch.setattr(srv, "CAPACIDADES", inventado)

    resultado = srv.check()
    assert resultado["ok"] is False
    assert [d["group_id"] for d in resultado["unknown_groups"]] == [999]


def test_una_capacidad_vacia_rompe_la_puerta(monkeypatch):
    inventado = dict(srv.CAPACIDADES)
    inventado["fantasma"] = {
        "titulo": "Fantasma",
        "resultado": "nada",
        "sirve_a": srv.SERVICIO["id"],
        "grupos": [],
    }
    monkeypatch.setattr(srv, "CAPACIDADES", inventado)

    resultado = srv.check()
    assert resultado["ok"] is False
    assert resultado["empty_capabilities"] == ["fantasma"]


def test_no_hay_numeracion_propia_de_grupos(monkeypatch):
    """Los `group_id` salen de `mapa_de_grupos()`, la fuente única de v40.8.

    Si `vault_servicio` guardara su propia tabla de números, sería la divergencia
    que aquel cambio cerró — productor y verificador leyendo fuentes distintas.
    """
    monkeypatch.setattr(
        srv, "_mapa_de_grupos", lambda: {"vault_x": {"name": "Inventado", "id": 41}}
    )
    resultado = srv.check()
    assert resultado["ok"] is False
    assert [h["group_id"] for h in resultado["orphan_groups"]] == [41]
