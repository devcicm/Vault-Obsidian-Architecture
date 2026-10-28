#!/usr/bin/env python3
"""Presupuesto de latencia de las primitivas calientes del kernel (opción A).

Cada llamada a una primitiva en memoria —parse de frontmatter, filtro de
regex, resolución de wikilinks, estimación de tokens— debe caber en el
presupuesto declarado en `vault_entorno` (AP-47: la cifra no se escribe a
mano en ningún doc; se lee del registro al llamarse):

- **Nominal 2 ms** (`VAULT_LATENCY_NOMINAL_MS`): el objetivo de regresión.
- **Máximo 5 ms** (`VAULT_LATENCY_MAX_MS`): el techo duro. Un fallo de esta
  aserción es un defecto, no ruido: la mejor de N aísla el ruido del entorno
  y una primitiva genuinamente lenta no pasa igual — su mínimo tampoco pasa.

El modo de medición es el de COST-a (`tests/test_puerto_controles.py`):
**serie**, sin `-n auto` — con 8 workers compitiendo, el reloj de pared mide
a los otros workers (5,1 s frente a 2,09 s en aislamiento, medido ahí) — y
"mejor de N" llamadas, para que la medida sea el coste de la primitiva y no
el de la máquina cargada.

Exclusión declarada (el presupuesto de lo demás ya existe y no se relaja):
las tools gruesas —`vault_audit`, `vault_smoke`, las 26 puertas, las
consultas sobre el vault entero— no entran en este presupuesto; su techo es
`VAULT_TOOL_TIMEOUT` (60 s default) y el de la pasada de humo,
`VAULT_SMOKE_TIMEOUT` (90 s). Meterlas aquí obligaría a relajar el umbral
hasta que ya no midiera nada.
"""

import json
import os
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO_ROOT))

from vault.kernel import entorno  # noqa: E402
from vault.kernel.frontmatter_parsing import parse_frontmatter  # noqa: E402
from vault.kernel import regex as vault_regex  # noqa: E402
from vault_lib import indice_de_nombres, resolver_wikilink  # noqa: E402
from vault_token_service import estimate_tokens  # noqa: E402

#: La nota típica que las primitivas van a masticar: frontmatter completo
#: del contrato, cuerpo con prosa, wikilinks y encabezados. No es un cebos
#: hostil — eso lo mide ya `test_filtro_de_expresiones_regulares.py` con su
#: propio umbral de escala (50 ms); este es el coste por llamada de lo común.
NOTA = """---
title: Transporte MCP del release
id: mcp-transport-release
createdAt: 2026-10-27T09:00:00.000Z
updatedAt: 2026-10-28T06:00:00.000Z
agent: smoke
tags: [mcp, release, qa]
type: knowledge
status: draft
cia_integrity: normal
cia_availability: normal
cia_sensitivity: normal
---

El transporte MCP decide como llegan las llamadas del cliente al toolkit.

## Contrato

- `stdio` es el transporte ejercitado por la suite y por el E2E.
- `[[mcp-token-service]]` emite el token por arranque (SP-04).
- El `[[graph-enriched]]` refresca las aristas tipadas (AP-31).

## Operaciones

Cada paso del recorrido llama por stdio y mide en serie, porque el reloj de
pared bajo `-n auto` mide a los otros workers, no a la tool. El nominal
declara lo que la primitiva cuesta en aislamiento; el techo decide.

Cierro con la matriz REL y el buzon al dia.
"""

#: Un índice del tamaño de un vault de consumidor (200 notas), construido
#: con el dueño canónico del criterio (`indice_de_nombres`), no a mano.
_INDICE = indice_de_nombres(
    [f"07_Knowledge/nota-ejemplo-{i:03d}" for i in range(200)]
    + ["03_Decisions/mcp-transport-release"]
)


def _resolver_tipico():
    """Lo que una pasada de resolución hace por nota: un hit, un miss y un
    sufijo de carpeta (la identidad que fija la carpeta, AP-21)."""
    resolver_wikilink("nota-ejemplo-007", None, _INDICE)
    resolver_wikilink("no-existe-en-ningun-sitio", None, _INDICE)
    resolver_wikilink("mcp-transport-release", None, _INDICE)


def _mejor_de(funcion, *args, intentos: int = 5) -> float:
    """El menor coste de N llamadas, en ms: el coste de la primitiva, no de
    la máquina. La mejor aísla el ruido del entorno (COST-a)."""
    mejor = float("inf")
    for _ in range(intentos):
        t0 = time.perf_counter_ns()
        funcion(*args)
        mejor = min(mejor, (time.perf_counter_ns() - t0) / 1e6)
    return mejor


# ── el guard del registro: los presupuestos existen y no se contradicen ─────

def test_el_presupuesto_esta_declarado_en_el_registro():
    """Sin entrada en `VARIABLES`, `leer()` explota: este test fija que los
    dos presupuestos viven ahí, con el máximo por encima del nominal."""
    for nombre in ("VAULT_LATENCY_NOMINAL_MS", "VAULT_LATENCY_MAX_MS"):
        assert nombre in entorno.VARIABLES, f"{nombre} no está en el registro"
        assert entorno.leer(nombre) > 0, f"{nombre} sin valor positivo"
    assert entorno.leer("VAULT_LATENCY_MAX_MS") > entorno.leer(
        "VAULT_LATENCY_NOMINAL_MS"), "el techo no puede caber dentro del nominal"


def test_la_puerta_limites_publica_el_presupuesto(capsys):
    """`--limites` es la puerta por la que el usuario ve los presupuestos
    (AP-44: el criterio del consumidor, no el del propio guard)."""
    assert entorno.main(["--limites", "--json"]) == 0
    datos = json.loads(capsys.readouterr().out)
    nombres = {fila["variable"] for fila in datos}
    faltan = {"VAULT_LATENCY_NOMINAL_MS",
              "VAULT_LATENCY_MAX_MS"} - nombres
    assert not faltan, f"--limites no publica: {faltan}"


# ── la medida: serie, mejor de N, techo duro ────────────────────────────────

@pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason=("medición de latencia serial-only: con 8 workers compitiendo el "
            "reloj de pared mide a los otros workers. Se mide "
            "`pytest tests/test_latencia_primitivas.py` sin -n y en el "
            "informe de la ronda; el techo no se relaja"))
def test_las_primitivas_calientes_caben_en_el_presupuesto():
    """La mejor llamada de cada primitiva cabe en `VAULT_LATENCY_MAX_MS`.

    Se reportan las que cruzan el nominal aunque pasen el techo: el nominal
    existe para que el alejamiento silencioso no sea la forma normal del
    ageing del catálogo.
    """
    nominal = entorno.leer("VAULT_LATENCY_NOMINAL_MS")
    techo = entorno.leer("VAULT_LATENCY_MAX_MS")

    medidas = {
        "frontmatter.parse": _mejor_de(parse_frontmatter, NOTA),
        "regex.corchetes": _mejor_de(vault_regex.detect_bracket_anomalies, NOTA),
        "wikilink.resolver": _mejor_de(_resolver_tipico),
        "tokens.estimar": _mejor_de(estimate_tokens, NOTA),
    }

    print("\nmedidas (mejor de 5, ms):")
    for k, v in sorted(medidas.items()):
        marca = "TECHO" if v > techo else ("nominal" if v > nominal else "ok")
        print(f"  {k}: {v:.3f} ms [{marca}] (nominal {nominal}, techo {techo})")

    sobre_techo = {k: round(v, 3) for k, v in medidas.items() if v > techo}
    assert not sobre_techo, (
        f"primitivas por encima del techo {techo} ms: {sobre_techo}. "
        "Es un defecto de latencia, no ruido: la mejor de N aísla la carga "
        "de la máquina; si su mínimo tampoco cabe, la primitiva es lenta "
        "de verdad. Corregir el coste o declarar una excepción con motivo "
        "en la norma que la sostenga — no subir el umbral.")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))
