"""El validador de flowchart no puede inventar errores en diagramas correctos.

Encontrado sanando BuilderX: `vault_audit` reportaba **69 errores Mermaid
(AP-25)**. Ninguno era real.

Dos causas, independientes:

  1. **46 de los 69 vivían dentro de `vault-backups/`.** El barrido excluía
     `.history/` pero no las copias de seguridad, que AP-36 obliga a guardar
     DENTRO del vault. Con `--fix`, la tool llegaba a reescribir diagramas de
     una instantánea congelada.

  2. **Los 23 restantes eran falsos positivos del parser.** Los patrones de
     definición de nodo iban anclados con `^` y el bucle hacía `continue` tras
     el primer acierto, así que:

       * `F --> G[Output HTML]` — G se define a la derecha de la flecha y esa
         definición no se veía nunca.
       * `A[Agente] --> B[MCP]` — casaba por la izquierda, pero el `continue`
         saltaba el escaneo de aristas de la misma línea: ni se definía B ni se
         registraba la arista.

Y una tercera cuestión de criterio: en Mermaid un identificador suelto
(`cli --> core`) **es** un nodo válido, se dibuja con su id como etiqueta. No es
un error de sintaxis. Marcarlo como tal restaba 2 puntos de health score por
cada uno — convertía una preferencia de estilo en una caída de la métrica.

El coste conjunto: un vault con diagramas correctos no podía subir de
`healthScore: 0`, y sanar no movía el número.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_mermaid_check as mc  # noqa: E402


def _tipos(diagrama: str) -> list[str]:
    return [e["type"] for e in mc.validate_flowchart(diagrama)]


def _mensajes(diagrama: str) -> str:
    return " | ".join(e["message"] for e in mc.validate_flowchart(diagrama))


# ── El caso literal de BuilderX ──────────────────────────────────────────────

BUILDERX_ARCH = """graph TD
    A[Agente LLM] -->|lenguaje natural| B[MCP Server :3202]
    B -->|apply_bx_script| C[Core - Parser .bx]
    C -->|AST| D[Core - Compiler]
    D -->|HTML| E[Studio Viewer :3101]
    B -->|emit_packet| E
    A -->|playwright navigate| E
    F[CLI bx.js] --> C
    F --> G[Output HTML]
    C -->|validate| H[Core - Validator]
"""

BUILDERX_PIPELINE = """graph TD
  BX[".bx script"] --> PRE["BxPreprocessor"]
  PRE --> VAL["BxValidator (lint estatico)"]
  VAL --> EXE["BxExecutor -> SessionState"]
  EXE --> DOC["Documento V2 (root.kind=page)"]
  DOC --> DV["DocumentValidator (schema + contraste)"]
  DV --> LC["LayoutCompiler"]
  LC --> NR["NodeRenderer.renderTree"]
  NR --> RN["renderNode recursivo"]
  RN --> NAV{"kind == navbar?"}
  NAV -->|si| NAVBLK["defaults: space-between"]
  NAV -->|no| RN2["otros kinds"]
  NAVBLK --> CSSARR["cssRules[]"]
  RN2 --> CSSARR
  CSSARR --> MERGE["_mergeIdenticalNodeRules"]
  MERGE --> CSSOUT["CSS final"]
  RN --> HTMLOUT["HTML"]
  CSSOUT --> PAGE["Pagina HTML + CSS"]
  HTMLOUT --> PAGE
"""


@pytest.mark.parametrize(
    "nombre,diagrama",
    [("architecture", BUILDERX_ARCH), ("pipeline", BUILDERX_PIPELINE)],
)
def test_los_diagramas_reales_de_builderx_no_dan_ni_un_hallazgo(nombre, diagrama):
    """Ambos son sintácticamente correctos: 23 hallazgos entre los dos."""
    assert mc.validate_flowchart(diagrama) == [], (
        f"{nombre}: el validador inventa errores sobre un diagrama válido — "
        f"{_mensajes(diagrama)}"
    )


# ── Las causas, una a una ───────────────────────────────────────────────────


def test_un_nodo_definido_a_la_derecha_de_la_flecha_cuenta_como_definido():
    """`F --> G[Label]`: el ancla `^` no veía esta definición."""
    assert _tipos("graph TD\n    F[CLI] --> G[Output HTML]\n") == []


def test_una_linea_define_los_dos_nodos_y_ademas_la_arista():
    """El `continue` tras la primera definición mataba el resto de la línea."""
    assert _tipos("graph TD\n    A[Uno] --> B[Dos]\n    B --> A\n") == []


def test_el_texto_de_una_etiqueta_de_arista_no_es_un_nodo():
    d = "graph TD\n    A[Uno] -->|manda un evento| B[Dos]\n"
    assert _tipos(d) == [], _mensajes(d)


def test_el_texto_entrecomillado_de_un_rombo_no_es_un_grafo():
    """`NAV{"kind == navbar?"}`: `==` es flecha, pero no dentro de la etiqueta."""
    d = 'graph TD\n    A["x"] --> NAV{"kind == navbar?"}\n'
    assert _tipos(d) == [], _mensajes(d)


@pytest.mark.parametrize(
    "linea",
    [
        "A[corchete] --> B[otro]",
        "A(redondo) --> B(otro)",
        "A{rombo} --> B{otro}",
        "A((circulo)) --> B((otro))",
        "A[[subrutina]] --> B[[otra]]",
        "A[(base de datos)] --> B[(otra)]",
        "A{{hexagono}} --> B{{otro}}",
        "A[/paralelogramo/] --> B[/otro/]",
        "A>bandera] --> B>otra]",
    ],
)
def test_reconoce_todas_las_formas_de_nodo(linea):
    d = f"graph TD\n    {linea}\n"
    assert _tipos(d) == [], _mensajes(d)


@pytest.mark.parametrize(
    "flecha", ["-->", "---", "==>", "===", "-.->", "--", "~~~"]
)
def test_reconoce_los_tipos_de_flecha(flecha):
    d = f"graph TD\n    A[Uno] {flecha} B[Dos]\n"
    assert _tipos(d) == [], _mensajes(d)


# ── El criterio: un id sin etiqueta es válido, no un error ──────────────────


def test_un_id_suelto_es_aviso_y_no_error():
    """`cli --> core` es Mermaid válido: el nodo se dibuja con su propio id."""
    hallazgos = mc.validate_flowchart("graph TD\n    cli --> core\n")
    assert [h["type"] for h in hallazgos] == ["unlabeled_node"] * 2
    assert all(h["severity"] == "info" for h in hallazgos)


def test_un_aviso_no_invalida_el_bloque_ni_cuenta_como_error_ap25(tmp_path):
    """AP-25 resta -2 por entrada de `errors`: los avisos no pueden entrar ahí."""
    md = tmp_path / "d.md"
    md.write_text("```mermaid\ngraph TD\n    cli --> core\n```\n", encoding="utf-8")

    r = mc.check_file(md)
    assert r["valid"] is True
    assert r["errors"] == []
    assert len(r["blocks"][0]["warnings"]) == 2


def test_subgraph_y_comentarios_no_se_leen_como_nodos():
    d = "graph TD\n    %% un comentario\n    subgraph S\n    A[Uno] --> B[Dos]\n    end\n"
    assert _tipos(d) == [], _mensajes(d)


# ── El barrido no toca instantáneas ─────────────────────────────────────────


def test_el_scan_no_entra_en_las_copias_de_seguridad(tmp_path):
    """46 de los 69 hallazgos de BuilderX vivían en `vault-backups/`."""
    roto = "```mermaid\ngraph TD\n    A[Uno] -->\n```\n"
    (tmp_path / "vault-backups" / "snap").mkdir(parents=True)
    (tmp_path / "vault-backups" / "snap" / "d.md").write_text(roto, encoding="utf-8")
    (tmp_path / ".trash").mkdir()
    (tmp_path / ".trash" / "d.md").write_text(roto, encoding="utf-8")

    r = mc.scan_vault(path=tmp_path)
    assert r["files_with_diagrams"] == 0, (
        f"el checker está leyendo diagramas de instantáneas congeladas: "
        f"{[x['file'] for x in r['results']]}"
    )


def test_una_nota_viva_si_se_escanea(tmp_path):
    """Excluir instantáneas no puede volverse una excusa para no ver nada."""
    (tmp_path / "06_Diagrams").mkdir()
    (tmp_path / "06_Diagrams" / "d.md").write_text(
        "```mermaid\ngraph TD\n    cli --> core\n```\n", encoding="utf-8"
    )
    assert mc.scan_vault(path=tmp_path)["files_with_diagrams"] == 1
