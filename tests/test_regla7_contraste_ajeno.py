"""Regla 7 — contraste contra material ajeno, y lo que salió de él.

Dos bloques que conviene no confundir:

* **La tool** (`vault_foreign_check`): lo que se puede verificar en cualquier
  máquina es lo que la tool se **niega** a hacer. Ejecutar el contraste de
  verdad exige un vault ajeno, que existe en la máquina de quien lo corra y en
  ninguna otra; atar la suite a esa ruta la haría verde por accidente en un
  sitio y roja en todos los demás. Así que la suite verifica las negativas, y el
  contraste se corre a mano — su resultado se congela abajo.

* **El hallazgo**: el primer contraste real (317 notas de un vault consumidor
  que este repo no generó) devolvió una nota con frontmatter que YAML no parsea.
  La causa no estaba en el vault: estaba en cómo el estándar **escribe** el
  título. Siete sitios componían `title:` concatenando texto fuera de las
  comillas —o sin comillas—, y bastaba un `:` en un nombre de proyecto para
  romper el bloque entero. `vault_project_overview` lo rompía **siempre**,
  porque su título es literalmente `Overview: <proyecto>`.

  `vault-sandbox/` no podía exhibirlo: ninguno de sus nombres lleva `:`. Es el
  caso de la regla 7 en su forma más limpia — no un fallo que el sandbox no
  tenía, sino uno que el sandbox **no podía tener**.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_foreign_check as vfc  # noqa: E402
import vault_mcp_catalog  # noqa: E402
from vault_lib import yaml_scalar  # noqa: E402

SPEC = json.loads(
    (REPO_ROOT / "vault-sandbox" / "00_System" / "tool-spec.json").read_text(
        encoding="utf-8"
    )
)["tools"]


# ── El hallazgo: títulos que rompen el frontmatter ─────────────────────────

#: (etiqueta, título compuesto como lo escribe hoy cada sitio corregido)
TITULOS = [
    ("vault_project_overview", f"Overview: {yaml_scalar('MiProy')}"),
    ("overview con dos puntos", yaml_scalar("Overview: Mi: Proy")),
    ("code_map", yaml_scalar("Code Map - Mi: Proy")),
    ("relation_add ERD", yaml_scalar("Mi: Proy ERD")),
    ("security_scan regla estilo Sonar", yaml_scalar("python:S1234 - seguridad")),
    ("migrate_docs", yaml_scalar("Migration Report - Mi: Proy")),
]


@pytest.mark.parametrize("etiqueta,titulo", TITULOS[1:])
def test_el_titulo_compuesto_sobrevive_a_yaml(etiqueta, titulo):
    """El criterio es el del consumidor: `yaml.safe_load`, no un regex (AP-44).

    Todos estos fallaban antes del contraste. `python:S1234` no es un caso
    rebuscado: es la forma que tienen los identificadores de regla de Sonar,
    que es justo lo que `vault_security_scan` interpola.
    """
    datos = yaml.safe_load(f"title: {titulo}\nid: x\n")
    assert isinstance(datos, dict), f"{etiqueta}: el bloque no parsea"
    assert "title" in datos


@pytest.mark.parametrize("modulo,fragmento", [
    ("vault_project_overview.py", "f\"title: Overview: {project}\""),
    ("vault_code_map.py", "f\"title: Code Map - {project}\""),
    ("vault_code_relation.py", "f\"title: Code Map - {project}\""),
    ("vault_migrate_docs.py", "f\"title: Migration Report - {project}\""),
    ("vault_security_scan.py", "f\"title: Security Scan Report - {project}\""),
])
def test_ningun_titulo_se_interpola_sin_escapar(modulo, fragmento):
    """Guard de regresión sobre la forma exacta que el contraste encontró.

    Interpolar un dato en `title:` sin pasarlo por `yaml_scalar` es el defecto,
    no el símbolo concreto que lo dispara: mañana será un `#`, o un `@`.
    """
    fuente = (REPO_ROOT / "scripts" / modulo).read_text(encoding="utf-8")
    assert fragmento not in fuente, (
        f"{modulo} vuelve a componer el título sin escapar — "
        "compón la cadena y pásala entera por yaml_scalar()"
    )


def test_escapar_solo_una_parte_no_vale():
    """El error más sutil de los siete: comillas alrededor de media cadena.

    `f"title: {yaml_scalar(project)} ERD"` produce `title: "Mi: Proy" ERD`, que
    es peor que no escapar nada — parece correcto y no lo es.
    """
    roto = f"title: {yaml_scalar('Mi: Proy')} ERD"
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load(roto)


# ── La tool: lo que se niega a hacer ───────────────────────────────────────

def test_sin_root_no_hay_destino_por_defecto():
    """La propiedad que la hace útil. Si cayera al sandbox, sería inútil."""
    with pytest.raises(vfc.DestinoInvalido):
        vfc.validar_destino(None)


def test_se_niega_a_medir_contra_el_sandbox():
    with pytest.raises(vfc.DestinoInvalido) as exc:
        vfc.validar_destino(str(REPO_ROOT / "vault-sandbox"))
    assert "regla 7" in str(exc.value)


def test_se_niega_a_medir_contra_cualquier_ruta_del_repo(tmp_path):
    """No basta con vetar `vault-sandbox`: todo el repo comparte los supuestos."""
    with pytest.raises(vfc.DestinoInvalido):
        vfc.validar_destino(str(REPO_ROOT / "docs"))
    # y una raíz de fuera sí se acepta
    (tmp_path / "nota.md").write_text("# hola\n", encoding="utf-8")
    assert vfc.validar_destino(str(tmp_path)) == tmp_path.resolve()


def test_la_suite_no_depende_de_un_vault_de_una_maquina_concreta():
    """Ninguna ruta absoluta de nadie dentro del fichero de tests.

    Un test que solo pasa en un portátil es peor que no tenerlo: pasa a ser
    ruido rojo para todos los demás y acaba marcado como xfail.
    """
    fuente = Path(__file__).read_text(encoding="utf-8")
    # Compuesto y no literal: si no, el guard se encuentra a sí mismo. Es el
    # mismo motivo por el que los detectores de este repo van por AST.
    unidad = "C" + ":"
    for sep in ("\\", "/"):
        assert unidad + sep + "Users" not in fuente, (
            "hay una ruta absoluta de una máquina concreta en el fichero"
        )


def test_el_self_test_verifica_las_cuatro_negativas():
    r = vfc.self_test()
    assert r["ok"]
    assert len(r["cases"]) == 4
    assert all(c["rejected"] for c in r["cases"])
    assert all(c["code"] for c in r["cases"]), "los errores van por ERROR_CATALOG (AP-52)"
    assert "NO sustituye al contraste" in r["hint"], (
        "un self-test verde no puede leerse como regla 7 cumplida"
    )


def test_el_error_de_destino_va_por_el_catalogo():
    """AP-52: la tool que estrena la puerta no puede saltársela."""
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "vault_foreign_check.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO_ROOT), timeout=60,
    )
    assert proc.returncode != 0
    env = json.loads(proc.stdout)
    assert env["ok"] is False
    assert env["error_code"] == "MISSING_REQUIRED_ARG"
    assert env["recovery"]["action"]


def test_no_escribe_en_el_vault_medido(tmp_path):
    """Solo lectura, verificado por huella y no por promesa."""
    vault = tmp_path / "ajeno"
    vault.mkdir()
    (vault / "a.md").write_text("---\ntitle: A\n---\n[[b]]\n", encoding="utf-8")
    (vault / "b.md").write_text("# B\n", encoding="utf-8")

    def huella():
        return sorted((p.name, p.stat().st_size, p.stat().st_mtime_ns)
                      for p in vault.rglob("*") if p.is_file())

    antes = huella()
    vfc.contrastar(vault)
    assert huella() == antes, "el contraste modificó el vault que estaba midiendo"


def test_el_report_no_puede_caer_dentro_del_vault_medido(tmp_path):
    vault = tmp_path / "ajeno"
    vault.mkdir()
    (vault / "a.md").write_text("# A\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "vault_foreign_check.py"),
         "--root", str(vault), "--report", str(vault / "informe.json")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO_ROOT), timeout=60,
    )
    assert proc.returncode != 0
    assert not (vault / "informe.json").exists()


# ── Las medidas, con el criterio del consumidor ────────────────────────────

def test_el_wikilink_se_resuelve_por_fichero_y_alias_nunca_por_title(tmp_path):
    """Lo que Obsidian mira. `title:` no entra, y por eso el contraste lo vio.

    En el vault ajeno, 158 wikilinks del índice apuntaban a títulos. Una medida
    que resolviera por `title:` los habría dado por buenos.
    """
    (tmp_path / "nota-a.md").write_text(
        "---\ntitle: Título Bonito\naliases: [Apodo]\n---\n"
        "[[nota-a]] [[Apodo]] [[Título Bonito]]\n",
        encoding="utf-8",
    )
    m = vfc.contrastar(tmp_path)
    assert m["wikilinks_total"] == 3
    assert m["wikilinks_unresolved"] == 1
    assert m["wikilinks_unresolved_sample"][0]["target"] == "Título Bonito"


def test_la_doc_del_estandar_copiada_no_aporta_enlaces_rotos(tmp_path):
    """El defecto que salió al medir los cuatro vaults consumidores.

    Un consumidor copia el manifiesto dentro de su vault, y el manifiesto **cita**
    sintaxis de wikilink como ejemplo. `vault_audit` ya excluía esa doc por
    contenido desde v40.5; el contraste de regla 7 no, y era el único sitio donde
    se notaba: en `vault-sandbox/` no hay copia del manifiesto, así que la medida
    salía verde justo en el caso que la tool existe para ver. En el vault de `ans`
    eran 199 de 545; en el de `electron`, los 175.
    """
    (tmp_path / "nota.md").write_text("[[nota]]\n", encoding="utf-8")
    (tmp_path / "vault-obsidian-architecture.v27.backup.md").write_text(
        "Se escribe `[[nombre-nota]]`, nunca `[[Título]]`.\n", encoding="utf-8")

    m = vfc.contrastar(tmp_path)
    assert m["standard_docs_excluded_count"] == 1
    assert m["wikilinks_unresolved"] == 0, m["wikilinks_unresolved_sample"]
    assert m["wikilinks_total"] == 1, "la doc no aporta ni el enlace ni el roto"


def test_una_instantanea_congelada_no_es_una_nota_del_vault(tmp_path):
    """El segundo hallazgo del contraste contra los cuatro consumidores.

    `.history/` es el historial local de VSCode: la misma nota veinte veces, con
    el estado que tuvo veinte tardes distintas. Sus enlaces apuntan a ficheros
    que desde entonces se renombraron, así que salían como enlaces rotos del
    vault vivo — 38 notas en el de `ans`, 2 en el de `electron`. Ninguna otra
    tool las miraba: `vault_io.SNAPSHOT_DIRS` es el dueño del criterio desde
    hace versiones, y el contraste era el único que no lo consultaba.
    """
    (tmp_path / "viva.md").write_text("[[viva]]\n", encoding="utf-8")
    (tmp_path / ".history").mkdir()
    (tmp_path / ".history" / "viva-2026-05-09T06-52-01.md").write_text(
        "[[un-nombre-que-ya-no-existe]]\n", encoding="utf-8")

    m = vfc.contrastar(tmp_path)
    assert m["notes_found"] == 1, "la instantánea no cuenta como nota"
    assert m["snapshot_notes_excluded_count"] == 1
    assert m["wikilinks_unresolved"] == 0, m["wikilinks_unresolved_sample"]


def test_el_criterio_de_instantanea_tampoco_se_reimplementa():
    import vault_io

    assert vfc.is_snapshot_path is vault_io.is_snapshot_path


def test_la_exclusion_de_doc_se_publica_en_vez_de_hacerse_en_silencio():
    """Excluir sin decirlo es indistinguible de un vault sin enlaces rotos."""
    campos = vfc.contrastar(Path(__file__).parent.parent / "docs")
    assert "standard_docs_excluded" in campos


def test_el_criterio_de_doc_no_se_reimplementa_aqui():
    """AP-05: dos versiones de la misma regla divergen el día que una cambia."""
    import vault_audit

    assert vfc.es_documentacion_del_estandar is vault_audit.es_documentacion_del_estandar


def test_lo_ilegible_no_se_cuenta_como_ausente(tmp_path):
    """AP-51 en la propia tool de contraste.

    Un byte que ningún encoding acepta no es "una nota sin frontmatter": es una
    nota que no se pudo mirar, y el informe lo dice por separado.
    """
    (tmp_path / "ok.md").write_text("---\ntitle: A\n---\n", encoding="utf-8")
    (tmp_path / "roto.md").write_bytes(b"\xff\xfe\x00\x00---\ntitle: X\n---\n")
    m = vfc.contrastar(tmp_path)
    assert m["notes_found"] == 2
    assert m["notes_measured"] + m["unreadable_count"] == m["notes_found"]


def test_frontmatter_ilegible_se_distingue_de_frontmatter_ausente(tmp_path):
    (tmp_path / "sin.md").write_text("# solo cuerpo\n", encoding="utf-8")
    (tmp_path / "roto.md").write_text(
        "---\ntitle: ADR: dos puntos sin comillas\n---\n", encoding="utf-8"
    )
    m = vfc.contrastar(tmp_path)
    assert m["without_frontmatter"] == 1
    assert len(m["frontmatter_unparseable"]) == 1
    assert "roto.md" in m["frontmatter_unparseable"][0]


def test_no_emite_un_veredicto_de_salud():
    """Deliberado: esta tool no puntúa el vault ajeno.

    Un `score` invitaría a comparar vaults entre sí, que no es lo que mide.
    Mide si **nuestras** medidas sobreviven a material que no generamos.
    """
    m = vfc.contrastar(REPO_ROOT / "tests")
    assert "score" not in m and "health" not in m


def test_cero_notas_no_se_presenta_como_exito(tmp_path):
    """Un vault vacío no es un contraste limpio: es un contraste que no ocurrió."""
    obs = vfc.observaciones(vfc.contrastar(tmp_path))
    assert any("no significa nada" in o for o in obs)


# ── Registro ───────────────────────────────────────────────────────────────

def test_esta_en_el_catalogo_y_en_el_tool_spec():
    assert "vault_foreign_check" in vault_mcp_catalog.TOOLS_CATALOG
    assert SPEC["vault_foreign_check"]["status"] == "active"
