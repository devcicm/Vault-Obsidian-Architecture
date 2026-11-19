"""`vault_onboard` writes layered notes (nota-escalonada S3-S5).

Measured on 2026-11-19 on a brownfield onboarding of this repository: a median
of 5 content lines and 28 words per note, every note opening with its H1 and a
provenance quote and nothing that told a reader without context what the note
was. Every note was born `status: stub` without `expand_by`, so `vault_audit`
reported 42 AP-03 findings on a vault the standard had just generated.

The rule, through the public interface and on the resulting vault:

- an article note (any section whose documentation class is not `registro`)
  opens with a self-sufficient lead (`contenido.profundidad_de_nota`);
- an event record (`registro`) may stay short, but links its parent note,
  the project overview;
- what the onboarding does not know is a pending marker that the evidence
  criterion (AP-45) does not count;
- every stub carries its enrichment deadline (`expand_by`, PAT-2);
- a second onboarding rewrites nothing.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import textwrap
from datetime import datetime, timedelta, timezone

import pytest

from apoyo import correr_tool, entorno, git_en
from vault.grafo.graph_fix import PLAZO_DE_ENRIQUECIMIENTO_DIAS
from vault.kernel.contenido import cuerpo_sin_marcadores, palabras_reales, profundidad_de_nota
from vault_lib import parse_frontmatter_with_body
from vault_registry import section_documentacion


PROYECTO = "demo-pedidos"
OVERVIEW = f"[[{PROYECTO}-overview"
#: The subject of the decision commit: longer than the 60 characters an ADR
#: title keeps, with the cut falling inside a word (brownfield BF-05).
ASUNTO_LARGO = ("migrate order storage to the repository layer and calendar "
                "driven retention policies")
#: Median real words per generated note on this fixture before the change
#: (measured on e259f661): the lead must raise it, not only exist.
MEDIANA_BASE_PALABRAS = 38


def _commit(repo, mensaje, fecha):
    marca = f"{fecha}T10:00:00+00:00"
    git_en(repo, "add", "-A", check=True)
    git_en(repo, "commit", "-m", mensaje, check=True,
           env=dict(os.environ, GIT_AUTHOR_DATE=marca, GIT_COMMITTER_DATE=marca,
                    GIT_TERMINAL_PROMPT="0"))


def _escribir(raiz, relativa, texto):
    ruta = raiz / relativa
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(textwrap.dedent(texto).lstrip("\n"), encoding="utf-8")


@pytest.fixture(scope="module")
def proyecto(tmp_path_factory):
    """A real git repository that feeds most onboarding builders."""
    p = tmp_path_factory.mktemp("proyecto-escalonado")
    _escribir(p, "package.json", json.dumps({
        "name": PROYECTO, "version": "2.1.0",
        "description": "API de pedidos para tiendas pequeñas",
        "scripts": {"build": "tsc", "test": "vitest run"},
        "dependencies": {"express": "^4.0.0"},
    }))
    _escribir(p, "README.md", """
        # demo-pedidos

        API de pedidos para tiendas pequeñas.

        ## Arquitectura

        Capas: controlador, servicio, repositorio.

        ## Features

        - Crear pedidos con varias líneas
        - Consultar el estado de un pedido

        ## Instalación

        npm i
    """)
    _escribir(p, "src/orderService.ts", """
        export class OrderService {
          // TODO: paginar la consulta
          // FIXME: el total ignora descuentos
          find(id: string) { return id }
        }
    """)
    _escribir(p, "src/orderRepository.ts", "export class OrderRepository { get() {} }\n")
    _escribir(p, "src/orderController.ts", "export class OrderController {}\n")
    _escribir(p, "src/order.test.ts", "test('order', () => {})\n")
    _escribir(p, "Makefile", """
        lint:
        \tnpx eslint src
    """)
    _escribir(p, ".github/workflows/ci.yml", """
        name: ci
        on: [push]
        jobs:
          test:
            runs-on: ubuntu-latest
            steps:
              - run: npm test
    """)
    _escribir(p, "docker-compose.yml", """
        services:
          api:
            image: node:20
            ports:
              - "3000:3000"
    """)
    git_en(p, "init", "-b", "main", check=True)
    git_en(p, "config", "user.email", "t@example.com", check=True)
    git_en(p, "config", "user.name", "Tester", check=True)
    _commit(p, "feat: primera version de la API de pedidos", "2026-01-10")
    git_en(p, "tag", "v1.0.0", check=True)
    _escribir(p, "src/orderController.ts", "export class OrderController { list() {} }\n")
    _commit(p, f"refactor: {ASUNTO_LARGO}", "2026-03-15")
    return p


def _onboard(vault, proyecto):
    r = correr_tool("vault_onboard", "--project", PROYECTO, "--path", proyecto,
                    env=entorno(vault, VAULT_TOOL_TIMEOUT="600"), timeout=600)
    assert r.codigo == 0, r.stderr[-1500:]
    salida = r.envelope
    assert salida.get("ok"), salida
    return salida


@pytest.fixture(scope="module")
def vault(tmp_path_factory, proyecto):
    v = tmp_path_factory.mktemp("vault-escalonado")
    r = correr_tool("vault_init", env=entorno(v, VAULT_TOOL_TIMEOUT="600"), timeout=600)
    assert r.codigo == 0, r.stderr[-1500:]
    return v, _onboard(v, proyecto)


def _leer(nota):
    return parse_frontmatter_with_body(nota.read_text(encoding="utf-8"))


def _generadas(v):
    """The notes the onboarding builders wrote (their provenance says so).

    The project card (`project.md`) has its own owner and is out of scope.
    """
    notas = {}
    for nota in sorted(v.rglob("*.md")):
        if nota.stem == "index" or nota.name == "project.md":
            continue
        fm, cuerpo = _leer(nota)
        if str(fm.get("provenance", "")).startswith("onboarding"):
            notas[nota.relative_to(v).as_posix()] = (fm, cuerpo)
    return notas


def test_cada_articulo_abre_con_un_lead_que_se_sostiene_solo(vault):
    v, _ = vault
    notas = _generadas(v)
    articulos = {rel: c for rel, (_, c) in notas.items()
                 if section_documentacion(rel) != "registro"}
    secciones = {rel.split("/", 1)[0] for rel in articulos}
    assert {"01_Projects", "03_Decisions", "05_Patterns", "06_Diagrams", "07_Knowledge",
            "08_Runbooks", "09_Infrastructure", "11_Code", "13_Flows", "15_Tests",
            "17_Preferences"} <= secciones, sorted(secciones)
    sin_lead = {rel: profundidad_de_nota(c) for rel, c in articulos.items()
                if not profundidad_de_nota(c)["tiene_lead"]}
    assert not sin_lead, json.dumps(sin_lead, ensure_ascii=False, indent=1)[:3000]


def test_cada_registro_enlaza_su_nota_padre(vault):
    v, _ = vault
    registros = {rel: c for rel, (_, c) in _generadas(v).items()
                 if section_documentacion(rel) == "registro"}
    assert {"02_Observability", "04_Sessions", "16_AI_Governance"} <= {
        rel.split("/", 1)[0] for rel in registros}, sorted(registros)
    huerfanos = [rel for rel, c in registros.items() if OVERVIEW not in c]
    assert not huerfanos, huerfanos


def test_lo_que_falta_se_ve_y_no_cuenta_como_evidencia(vault):
    v, _ = vault
    pendientes = []
    for rel, (_, cuerpo) in _generadas(v).items():
        for linea in cuerpo.splitlines():
            if linea.startswith("> _Pendiente: "):
                motivo = linea[len("> _Pendiente: "):].rstrip("_").rstrip(".")
                pendientes.append(rel)
                assert motivo not in cuerpo_sin_marcadores(cuerpo), (rel, motivo)
    assert any(rel.startswith("11_Code/") for rel in pendientes), pendientes


def test_cada_stub_nace_con_su_plazo_de_enriquecimiento(vault):
    v, _ = vault
    hoy = datetime.now(timezone.utc).date()
    plazo = (hoy + timedelta(days=PLAZO_DE_ENRIQUECIMIENTO_DIAS)).isoformat()
    stubs = {rel: fm for rel, (fm, _) in _generadas(v).items() if fm.get("status") == "stub"}
    assert stubs
    sin_plazo = {rel: fm.get("expand_by") for rel, fm in stubs.items()
                 if str(fm.get("expand_by")) != plazo}
    assert not sin_plazo, sin_plazo
    sin_plazo_audit = correr_tool("vault_audit", vault=v).envelope["issues"]["stubsSinPlazo"]
    assert not [h for h in sin_plazo_audit if h["path"] in stubs], sin_plazo_audit[:5]


def test_el_titulo_del_adr_retroactivo_corta_en_una_palabra(vault):
    v, _ = vault
    adrs = {rel: fm for rel, (fm, _) in _generadas(v).items()
            if rel.startswith("03_Decisions/") and "retroactivo" in fm.get("title", "")
            and "repository" in fm.get("title", "")}
    assert adrs, sorted(_generadas(v))
    for rel, fm in adrs.items():
        # The write path renders the em dash of the title as `--`.
        nucleo = re.split(r" (?:—|--) ", fm["title"], maxsplit=1)[1].rsplit(" (retroactivo)", 1)[0]
        assert ASUNTO_LARGO.startswith(nucleo), (rel, nucleo)
        assert ASUNTO_LARGO[len(nucleo):len(nucleo) + 1] in ("", " "), (rel, nucleo)


def test_la_mediana_de_palabras_por_nota_sube(vault):
    v, _ = vault
    palabras = [len(palabras_reales(cuerpo_sin_marcadores(c)))
                for _, c in _generadas(v).values()]
    mediana = statistics.median(palabras)
    assert mediana >= MEDIANA_BASE_PALABRAS + 20, (mediana, sorted(palabras))


def test_segunda_corrida_no_reescribe_ninguna_nota_escalonada(vault, proyecto):
    v, _ = vault
    antes = {p: p.read_bytes() for p in v.rglob("*.md") if p.stem != "index"}
    salida = _onboard(v, proyecto)
    assert salida["merge_stats"]["created"] == 0, salida["merge_stats"]
    assert salida["merge_stats"]["merged"] == 0, salida["merge_stats"]
    despues = {p: p.read_bytes() for p in v.rglob("*.md") if p.stem != "index"}
    assert antes.keys() == despues.keys()
    assert [str(p) for p in antes if antes[p] != despues[p]] == []
