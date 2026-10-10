"""El protocolo de sesión del agente es un registro, y el perfil `agente` sale de él.

Medido el 2026-10-07: el protocolo de sesión vivía solo en el manifiesto
(§ Protocolo de sesión para LLMs remotos, de v22). No nombraba
`vault_context_pack` ni `vault_preferences` —el camino de recordar, que es la
mitad de la promesa de `vault_servicio.SERVICIO`, llegó en v39—, mandaba
llamar `vault_change_log` antes de borrar cuando `vault_delete` ya lo hace
(SP-01), y por MCP el agente recibía las 96 tools `runtime` sin ninguna guía
de cuáles usa una sesión. Un concepto que solo existe en el manifiesto no
existe (regla 3): ahora es `vault.meta_toolkit.protocolo_de_sesion`.
"""

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from vault.meta_toolkit.naturalezas import NATURALEZAS  # noqa: E402
from vault.meta_toolkit.protocolo_de_sesion import (  # noqa: E402
    PERFILES,
    PISTAS_FUERA_DEL_PERFIL,
    PROTOCOLO_DE_SESION,
    tools_del_perfil,
)

CATALOGO = json.loads(
    (ROOT / "mcp" / "nodejs" / "tools-catalog.json").read_text(encoding="utf-8"))

import vault_grafo_import as gi  # noqa: E402


def _naturaleza(tool):
    return next((n for n, d in NATURALEZAS.items() if tool in d["tools"]), None)


def _pasos():
    for momento, datos in PROTOCOLO_DE_SESION.items():
        for paso in datos["pasos"]:
            yield momento, paso


def test_todo_paso_dice_para_que_y_de_donde_sale():
    for momento, paso in _pasos():
        assert paso["tool"].startswith("vault_"), (momento, paso)
        assert paso["para"].strip(), (momento, paso["tool"])
        assert paso["fuente"].strip(), (momento, paso["tool"])


@pytest.mark.parametrize("perfil", sorted(PERFILES))
def test_el_perfil_solo_tiene_tools_que_un_agente_puede_llamar(perfil):
    for tool in tools_del_perfil(perfil):
        entrada = CATALOGO["tools"].get(tool)
        assert entrada is not None, f"{tool} no está en el catálogo"
        assert entrada["exposed_via_mcp"] is True, f"{tool} no se expone por MCP"
        assert _naturaleza(tool) != "meta_estandar", f"{tool} mide el repo, no el vault"


def test_el_perfil_agente_es_el_protocolo_entero():
    """Derivado, no escrito a mano: cada tool que un paso nombra, y ninguna más."""
    assert tools_del_perfil("agente") == sorted({p["tool"] for _, p in _pasos()})


def test_el_perfil_agente_puede_recordar_y_escribir():
    """La promesa tiene dos mitades: lo que el agente necesita recordar se le
    devuelve como contexto, y lo que escribe queda gobernado."""
    tools = tools_del_perfil("agente")
    assert "vault_context_pack" in tools
    assert {_naturaleza(t) for t in tools} >= {"consulta", "documentacion", "custodia"}


def test_cada_paso_de_recuperar_es_la_pista_de_su_error():
    """Un paso que existe para recuperarse de un error declara cuál, y el
    catálogo de errores manda justo a esa tool: si la pista cambia de tool, el
    perfil deja de darle al agente lo que necesita para seguirla."""
    pasos = [p for m, p in _pasos() if p.get("recupera")]
    assert pasos, "el protocolo no declara cómo recuperarse de ningún error"
    for paso in pasos:
        for codigo in paso["recupera"]:
            recovery = CATALOGO["errors"][codigo]["recovery"]
            assert recovery["tool"] == paso["tool"], (codigo, recovery)


def test_drift_detect_declara_el_proyecto_que_exige():
    """`--project` es obligatorio desde AP-63; un uso sin él falla con INVALID_ARGS."""
    usos = [p["uso"] for _, p in _pasos() if p["tool"] == "vault_drift_detect"]
    assert usos and all("--project" in u for u in usos)
    assert "project" in CATALOGO["tools"]["vault_drift_detect"]["inputSchema"]["required"]


def test_el_catalogo_mcp_publica_los_perfiles():
    assert CATALOGO.get("perfiles") == {p: tools_del_perfil(p) for p in sorted(PERFILES)}


def test_un_perfil_desconocido_no_devuelve_vacio():
    with pytest.raises(KeyError):
        tools_del_perfil("no-existe")


def test_el_manifiesto_nombra_cada_tool_del_protocolo():
    texto = (ROOT / "vault-obsidian-architecture.md").read_text(encoding="utf-8")
    inicio = texto.index("## Protocolo de sesión para LLMs remotos")
    seccion = texto[inicio:texto.index("\n## ", inicio + 1)]
    faltan = sorted({p["tool"] for _, p in _pasos()
                     if not re.search(rf"\b{p['tool']}\b", seccion)})
    assert not faltan, f"el manifiesto no nombra: {faltan}"


def _pistas_fuera_del_perfil():
    perfil = set(tools_del_perfil("agente"))
    return {
        codigo for codigo, entrada in CATALOGO["errors"].items()
        if (tool := (entrada.get("recovery") or {}).get("tool"))
        and not tool.startswith("<") and tool not in perfil
    }


def test_toda_pista_fuera_del_perfil_esta_clasificada():
    """Medido el 2026-10-07: cuatro códigos mandan a tools que el perfil no
    tiene. Cada uno declara por qué el agente no lo recibe; uno nuevo falla
    hasta que se decida si su tool entra en el perfil o su pista cambia."""
    declaradas = set(PISTAS_FUERA_DEL_PERFIL)
    medidas = _pistas_fuera_del_perfil()
    assert medidas - declaradas == set(), f"sin clasificar: {sorted(medidas - declaradas)}"
    assert declaradas - medidas == set(), f"ya no salen del perfil: {sorted(declaradas - medidas)}"
    assert all(m.strip() for m in PISTAS_FUERA_DEL_PERFIL.values())


def test_ninguna_tool_del_perfil_emite_una_pista_que_no_puede_seguir():
    """Descarte por texto, no confirmación: si el script de una tool del
    perfil nombra el código, o una causa del dominio que se traduce a él, la
    clasificación de arriba es falsa. Lo que emita un módulo importado sin
    nombrar el código no lo ve."""
    from vault.kernel.errores import MAPA_DE_FALLOS

    for codigo in PISTAS_FUERA_DEL_PERFIL:
        nombres = {codigo} | {c for c, d in MAPA_DE_FALLOS.items() if d == codigo}
        for tool in tools_del_perfil("agente"):
            texto = gi.codigo_de(ROOT / "scripts" / f"{tool}.py").read_text(encoding="utf-8")
            assert not any(f'"{n}"' in texto for n in nombres), (tool, codigo)


def test_un_paso_con_un_valor_del_agente_declara_cuando_aplica():
    """Medido el 2026-10-07: el cierre pedía `vault_drift_detect --project
    <slug>` sin decir que solo aplica a un proyecto con repo enlazado, y sin
    un snapshot tomado al empezar el report de un repo sin git no tenía con
    qué comparar. Un paso que necesita un valor que solo el agente conoce
    dice cuándo se da."""
    for momento, paso in _pasos():
        if "<" in paso["uso"]:
            assert paso.get("cuando", "").strip(), (momento, paso["tool"])


def test_el_drift_del_cierre_tiene_su_snapshot_al_empezar():
    inicio = [p for p in PROTOCOLO_DE_SESION["inicio"]["pasos"]
              if p["tool"] == "vault_drift_detect"]
    assert inicio and all("--mode snapshot" in p["uso"] for p in inicio)
