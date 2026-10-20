"""Nadie lee el frontmatter línea a línea fuera del dueño (AP-44 / AP-57, deuda #5).

Medido el 2026-10-08: once funciones repartidas en diez módulos leían claves
con `line.split(":", 1)` o `partition(":")` sobre el bloque. Ese lector no ve
lo que el consumidor —`yaml.safe_load`— sí ve:

- un título en bloque (`title: >-`) sale como `>-`;
- una lista de tags en bloque sale como texto vacío, y `vault_quality_check`
  la puntuaba como ausente;
- un valor entre comillas conserva las comillas, y `vault_flow_save` las
  volvía a escribir dentro de `createdAt` al actualizar la nota.

El dueño es `vault/kernel/frontmatter_parsing.py`: `cargar_bloque_tolerante`
lee con YAML y solo degrada a lectura por líneas —diciéndolo— cuando YAML
rechaza el bloque.
"""

import os
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_audit  # noqa: E402
import vault_criterios  # noqa: E402
import vault_delta  # noqa: E402
import vault_merge  # noqa: E402
import vault_quality_check  # noqa: E402
import vault_tags  # noqa: E402
import vault_timeline  # noqa: E402
from vault.kernel.frontmatter_parsing import (  # noqa: E402
    cargar_bloque_tolerante, separar_frontmatter,
)

BLOQUE = (
    "title: >-\n"
    "  Un título\n"
    "  en dos líneas\n"
    "tags:\n"
    "  - bug\n"
    "  - error\n"
    'createdAt: "2026-10-01T10:00:00Z"\n'
    'updatedAt: "2026-10-02T11:00:00Z"\n'
    'cia_integrity: "high"\n'
    "agent: claude\n"
)
NOTA = f"---\n{BLOQUE}---\n\ncuerpo real de la nota\n"
ESPERADO = yaml.safe_load(BLOQUE)


def test_ap44_cada_lector_ve_lo_que_ve_yaml(tmp_path):
    nota = tmp_path / "n.md"
    nota.write_text(NOTA, encoding="utf-8")

    assert vault_tags._parse_frontmatter_title(NOTA) == ESPERADO["title"]
    assert vault_timeline.parse_frontmatter(NOTA)["title"] == ESPERADO["title"]
    assert vault_audit._frontmatter_de(BLOQUE)["title"] == ESPERADO["title"]
    assert vault_delta._read_cia_integrity(nota) == "high"
    assert vault_merge._note_updated_at(nota) == ESPERADO["updatedAt"]

    fm, cuerpo = vault_quality_check._read_frontmatter_raw(nota)
    assert fm["title"] == ESPERADO["title"]
    assert fm["createdAt"] == ESPERADO["createdAt"]
    assert fm["tags"], "una lista en bloque no es un campo vacío"
    assert cuerpo.strip() == "cuerpo real de la nota"


def test_ap44_un_bloque_que_yaml_rechaza_se_lee_degradado_y_lo_dice():
    roto = "title: Antes: después\nid: abc\n  sangría: rota\n"
    datos, degradado = cargar_bloque_tolerante(roto)
    assert degradado is True
    assert datos == {"title": "Antes: después", "id": "abc"}

    sano, degradado = cargar_bloque_tolerante(BLOQUE)
    assert degradado is False
    assert sano["tags"] == ["bug", "error"]


def test_ap44_la_auditoria_externa_lee_el_titulo_sin_caerse(tmp_path):
    """Una nota sin `title:` leía `parts[2]`, que ya no existía: NameError."""
    relleno = "texto de relleno para superar el umbral de nota vacía. " * 3
    (tmp_path / "en_bloque.md").write_text(NOTA + relleno, encoding="utf-8")
    (tmp_path / "con_encabezado.md").write_text(
        f"---\nid: x\n---\n\n# Encabezado\n\n{relleno}\n", encoding="utf-8")
    (tmp_path / "sin_titulo.md").write_text(
        f"---\nid: y\n---\n\n{relleno}\n", encoding="utf-8")

    r = vault_audit._audit_external_path(tmp_path)
    assert [Path(p).name for p in r["noTitle"]] == ["sin_titulo.md"]


def test_ap44_en_modo_texto_las_fechas_conservan_lo_escrito():
    datos, _ = cargar_bloque_tolerante(
        "createdAt: 2026-10-08T23:34:46.000Z\nevergreen: true\n", texto=True)
    assert datos == {"createdAt": "2026-10-08T23:34:46.000Z", "evergreen": "true"}


def test_ap44_flow_save_no_reescribe_las_comillas_de_created_at(tmp_path):
    """Re-guardar lo idéntico no toca el fichero; cambiar algo conserva identidad.

    v41.12/O4: antes este test pedía que el re-guardado CANONICALIZARA la
    comilla de `createdAt` (devolverla a timestamp plano). Con el criterio
    «mismo cuerpo ⇒ mismo documento» el fichero ni se abre a escribir: la
    forma que escribió la persona se queda como está — que es la lectura
    literal del nombre del test. Lo que sigue siendo contrato: al cambiar de
    verdad, el `id` y el `createdAt` NO se regeneran.
    """
    import vault_flow_save
    import vault_io

    vault = tmp_path / "vault"
    for d in ("00_System", "99_Index"):
        (vault / d).mkdir(parents=True)
    vault_io.set_vault_root(vault)

    args = dict(project="demo", name="Alta", flow_type="workflow",
                description="d", mermaid="flowchart TD\n  A-->B")
    assert vault_flow_save.vault_flow_save(**args)["ok"]
    nota = next(vault.rglob("demo-alta.md"))
    texto = nota.read_text(encoding="utf-8")
    bloque, _ = separar_frontmatter(texto)
    original = yaml.safe_load(bloque)
    con_comillas = texto.replace(
        f"createdAt: {bloque.split('createdAt: ')[1].splitlines()[0]}",
        f'createdAt: "{original["createdAt"]}"', 1)
    nota.write_text(con_comillas, encoding="utf-8")

    # 1. Mismo cuerpo: el fichero queda byte a byte como estaba.
    assert vault_flow_save.vault_flow_save(**args)["ok"]
    assert nota.read_text(encoding="utf-8") == con_comillas

    # 2. Cambio real: se reescribe, pero la identidad (id, createdAt) sobrevive.
    assert vault_flow_save.vault_flow_save(**{**args, "description": "otra"})["ok"]
    despues = yaml.safe_load(separar_frontmatter(nota.read_text(encoding="utf-8"))[0])
    assert despues["id"] == original["id"]
    assert despues["createdAt"] == original["createdAt"]


def test_ap57_un_lector_a_mano_se_detecta(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "vault_copia.py").write_text(
        "from vault.kernel.frontmatter_parsing import separar_frontmatter\n"
        "def f(t):\n"
        "    bloque, _ = separar_frontmatter(t)\n"
        "    for linea in bloque.splitlines():\n"
        "        if linea.startswith('id:'):\n"
        "            return linea.split(':', 1)[1]\n",
        encoding="utf-8")
    (tmp_path / "scripts" / "vault_otra.py").write_text(
        "def g(t):\n"
        "    for linea in t.splitlines():\n"
        "        k, _, v = linea.partition(':')\n",
        encoding="utf-8")
    dueño = tmp_path / "vault" / "kernel"
    dueño.mkdir(parents=True)
    (dueño / "frontmatter_parsing.py").write_text(
        "def separar_frontmatter(t):\n"
        "    for l in t.splitlines():\n"
        "        l.split(':', 1)\n",
        encoding="utf-8")
    h = vault_criterios.medir_lecturas(tmp_path)
    assert [x["modulo"] for x in h] == ["scripts/vault_copia.py"]
    assert h[0]["dueño"].endswith(":cargar_bloque_tolerante")


def test_ap57_hoy_nadie_lee_el_frontmatter_a_mano():
    assert vault_criterios.medir_lecturas() == []
