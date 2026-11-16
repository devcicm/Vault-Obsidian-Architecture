"""La politica de inmutabilidad la respetan TODOS los escritores.

Hallazgo de una revision independiente (2026-11-09): el veto vivia en
`vault_write` y **el onboarding lo esquivaba** —`_merge_stub` modifico una
nota de `11_Code` declarada inmutable—. El veto es ahora del **dueno de la
escritura** (`vault_io.atomic_write_text`), asi que todos los que escriben
por el dueno lo heredan.

Lo que se comprueba aqui, escritor por escritor:

- la nota **no cambia**: se comparan **bytes**, no texto. Una comprobacion de
  texto puede dejar un byte distinto (BOM, CRLF, salto final) y no notarlo;
- el envelope **no** dice que fue un exito;
- **crear** una nota nueva en la seccion inmutable si se permite: el
  historico crece, no se reescribe;
- los **artefactos derivados** (el `index.md` de la seccion) se siguen
  regenerando: no son notas, y bloquearlos dejaria la seccion sin indice.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apoyo import ROOT as REPO_ROOT  # el conftest ya pone el path

import vault_append
import vault_delete
import vault_io
import vault_merge
import vault_move
import vault_onboard
import vault_write

NOTA = (
    "---\ntitle: Nota historica\nid: abc-123\ntype: code\nstatus: draft\n"
    "tags: [historia]\ncreatedAt: 2026-01-01T00:00:00.000Z\n"
    "updatedAt: 2026-01-01T00:00:00.000Z\n---\n\n"
    "## Observacion\n\nEl texto que una persona escribio y que no se toca.\n"
)


@pytest.fixture
def vault(tmp_path):
    """Un vault desechable con `11_Code` declarada inmutable."""
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    (raiz / "11_Code").mkdir(parents=True)
    (raiz / "11_Code" / "nota-historica.md").write_text(NOTA, encoding="utf-8")
    (raiz / "00_System" / "inmutable.json").write_text(
        json.dumps({"secciones": ["11_Code"]}), encoding="utf-8")
    previa = vault_io.set_vault_root(raiz)
    yield raiz
    vault_io.set_vault_root(previa)


def _bytes(vault: Path) -> bytes:
    return (vault / "11_Code" / "nota-historica.md").read_bytes()


def test_el_onboarding_no_modifica_una_nota_inmutable(vault, tmp_path):
    """El repro del revisor, de punta a punta y con bytes.

    El onboarding es el escritor que esquivaba el veto: escribe por el
    dueño (`atomic_write_text`) y su propio camino no consultaba la
    politica. Ahora la consulta, omite la nota y **lo declara**.
    """
    proyecto = tmp_path / "proyecto"
    (proyecto / "src").mkdir(parents=True)
    (proyecto / "src" / "core.py").write_text(
        '"""Nucleo."""\n\n\ndef arrancar():\n    return 1\n', encoding="utf-8")
    antes = _bytes(vault)

    res = vault_onboard.vault_onboard(
        project="demo", path=str(proyecto), no_git=True)

    assert _bytes(vault) == antes, "el onboarding modifico una nota inmutable"
    # El envelope declara el campo aunque no haya omisiones: su ausencia
    # seria indistinguible de «no se comprobo».
    assert "omitidas_por_politica" in res, res


def test_la_fusion_del_onboarding_omite_una_nota_inmutable(vault):
    """El repro del revisor, sobre la funcion que lo hacia.

    `_merge_stub` es el camino que el onboarding usa para fusionar. Antes
    modificaba la nota sin mirar la politica (el veto vivia en
    `vault_write` y esta ruta escribe por el dueno). Ahora lo omite y lo
    declara.
    """
    antes = _bytes(vault)
    nuevo = (
        "---\ntitle: Nota historica\nid: abc-123\ntype: code\nstatus: draft\n"
        "tags: [historia]\ncreatedAt: 2026-01-01T00:00:00.000Z\n"
        "updatedAt: 2026-01-01T00:00:00.000Z\n---\n\n"
        "## Seccion nueva\n\nUna seccion que no debe entrar.\n"
    )
    accion = vault_onboard._merge_stub(
        vault / "11_Code" / "nota-historica.md", nuevo, dry_run=False)
    assert accion == "omitida_por_politica", accion
    assert _bytes(vault) == antes, "la fusion modifico una nota inmutable"


def test_vault_write_no_modifica_una_nota_inmutable(vault):
    antes = _bytes(vault)
    res = vault_write.vault_write(
        folder="11_Code", title="Nota historica",
        content="Contenido nuevo que no debe entrar en una nota historica.\n\n"
                "Segunda linea con suficiente texto para la valla de contenido.\n\n"
                "Tercera linea que tampoco deberia llegar al disco.\n",
        tags=["prueba"], meta={"agent": "opencode"})
    assert res.get("ok") is False, res
    assert res.get("error_code") == "IMMUTABLE_NOTE", res
    assert _bytes(vault) == antes


def test_vault_append_no_modifica_una_nota_inmutable(vault):
    antes = _bytes(vault)
    res = vault_append.vault_append(
        path="11_Code/nota-historica.md",
        content="Anadido que no debe entrar\n\n"
                "Segunda linea con suficiente texto para la valla.\n\n"
                "Tercera linea del anadido indebido.\n")
    assert res.get("ok") is False, res
    assert _bytes(vault) == antes


def test_vault_merge_no_modifica_una_nota_inmutable(vault, tmp_path):
    antes = _bytes(vault)
    otra = tmp_path / "otra.md"
    otra.write_text("---\ntitle: Otra\n---\n\nContenido.\n", encoding="utf-8")
    res = vault_merge.vault_merge(source=str(otra), action="merge")
    # El merge no puede terminar en exito sobre una nota inmutable: o falla,
    # o no la toca. Lo que no puede es cambiarla.
    assert _bytes(vault) == antes, res


def test_vault_move_no_saca_la_nota_de_la_seccion(vault):
    """Mover es tambien retirar: la nota sale de su sitio."""
    antes = _bytes(vault)
    res = vault_move.move_note(
        from_path="11_Code/nota-historica.md", to_path="07_Knowledge/nota.md")
    assert res.get("ok") is False, res
    assert _bytes(vault) == antes
    assert (vault / "11_Code" / "nota-historica.md").exists()


def test_vault_delete_no_borra_una_nota_inmutable(vault):
    antes = _bytes(vault)
    res = vault_delete.vault_delete(path="11_Code/nota-historica.md", reason="prueba")
    assert res.get("ok") is False, res
    assert res.get("error_code") == "DELETE_FORBIDDEN", res
    assert _bytes(vault) == antes


def test_crear_una_nota_nueva_si_se_permite(vault):
    """El historico crece: una nota nueva en la seccion inmutable, si."""
    res = vault_write.vault_write(
        folder="11_Code", title="sucesora",
        content="Una nota nueva, con su historia propia y su fecha.\n\n"
                "Segunda linea con contenido suficiente para la valla de "
                "contenido del toolkit.\n\n"
                "Tercera linea que cierra la nota sucesora.\n",
        tags=["sucesora"], meta={"agent": "opencode"})
    assert res.get("ok"), res
    assert (vault / "11_Code" / "sucesora.md").is_file()


def test_el_indice_derivado_se_regenera(vault):
    """Un `index.md` no es una nota: la seccion inmutable debe poder reindexarse."""
    indice = vault / "11_Code" / "index.md"
    indice.write_text("indice viejo\n", encoding="utf-8")
    vault_io.atomic_write_text(indice, "indice nuevo\n")
    assert indice.read_text(encoding="utf-8") == "indice nuevo\n"


def test_el_codigo_del_error_esta_en_el_catalogo():
    from vault.kernel.errores import ERROR_CATALOG

    assert "IMMUTABLE_NOTE" in ERROR_CATALOG
    assert "DELETE_FORBIDDEN" in ERROR_CATALOG


def test_el_veto_vive_en_el_dueno_y_no_en_cada_escritor():
    """Un solo sitio decide: si el criterio est\u00e1 duplicado, divergen.

    La lecci\u00f3n del hallazgo: el veto estaba en `vault_write` y cada
    escritor que no pasara por ah\u00ed lo esquivaba. Ahora est\u00e1 en el due\u00f1o de
    la escritura, y las tools no lo reimplementan.
    """
    import vault_grafo_import as gi

    fuente = gi.codigo_de(REPO_ROOT / "scripts" / "vault_write.py").read_text(
        encoding="utf-8")
    assert "nota_es_inmutable(" not in fuente, (
        "vault_write no debe reimplementar el veto: decide el dueno")
    assert "nota_es_inmutable(" not in fuente, (
        "vault_write no debe reimplementar el veto: decide el dueno")
    assert "inmutables_declaradas(" not in fuente, (
        "vault_write no debe reimplementar el veto: decide el dueno")
    assert "reglas_declaradas(" not in fuente, (
        "vault_write no debe reimplementar el veto: decide el dueno")
    dueno = gi.codigo_de(REPO_ROOT / "scripts" / "vault_io.py").read_text(
        encoding="utf-8")
    assert "_exigir_politica_de_inmutabilidad" in dueno


@pytest.mark.parametrize("fichero", ["inmutable.json", "reglas.json"])
@pytest.mark.parametrize("contenido", ["{", "[]", '{"secciones": "11_Code"}', "\ufffd"])
def test_politica_existente_invalida_bloquea_escritura(vault, fichero, contenido):
    (vault / "00_System" / fichero).write_text(contenido, encoding="utf-8")
    nota = vault / "11_Code" / "nota-historica.md"
    antes = nota.read_bytes()
    with pytest.raises(vault_io.PoliticaInvalidaError):
        vault_io.atomic_write_text(nota, "No debe escribirse")
    assert nota.read_bytes() == antes


def test_reglas_json_inmutable_prohibe_retirar_nota(vault):
    (vault / "00_System" / "inmutable.json").unlink()
    (vault / "00_System" / "reglas.json").write_text(
        json.dumps({"inmutable": ["11_Code"]}), encoding="utf-8")
    nota = vault / "11_Code" / "nota-historica.md"
    antes = nota.read_bytes()
    resultado = vault_delete.vault_delete("11_Code/nota-historica.md", reason="prueba")
    assert resultado.get("ok") is False, resultado
    assert nota.read_bytes() == antes


@pytest.mark.parametrize("carpeta", [False, True])
@pytest.mark.parametrize("dry_run", [False, True])
def test_mover_origen_inmutable_se_rechaza_sin_efectos(vault, carpeta, dry_run):
    (vault / "00_System" / "inmutable.json").unlink()
    (vault / "00_System" / "reglas.json").write_text(
        json.dumps({"inmutable": ["11_Code"]}), encoding="utf-8")
    nota = vault / "11_Code" / "nota-historica.md"
    antes = nota.read_bytes()
    if carpeta:
        resultado = vault_move.move_folder("11_Code", "07_Knowledge/movido", dry_run=dry_run)
    else:
        resultado = vault_move.move_note("11_Code/nota-historica.md", "07_Knowledge/movido.md", dry_run=dry_run)
    assert resultado.get("ok") is False, resultado
    assert resultado.get("error_code") == "IMMUTABLE_NOTE", resultado
    assert nota.read_bytes() == antes
    assert not (vault / "07_Knowledge" / "movido.md").exists()


@pytest.mark.parametrize("operacion", ["delete", "move", "folder"])
def test_politica_corrupta_detiene_retiro(vault, operacion):
    (vault / "00_System" / "reglas.json").write_bytes(b"\xff")
    nota = vault / "11_Code" / "nota-historica.md"
    antes = nota.read_bytes()
    if operacion == "delete":
        resultado = vault_delete.vault_delete("11_Code/nota-historica.md", reason="prueba")
    elif operacion == "move":
        resultado = vault_move.move_note("11_Code/nota-historica.md", "07_Knowledge/movido.md")
    else:
        resultado = vault_move.move_folder("11_Code", "07_Knowledge/movido")
    assert resultado.get("ok") is False, resultado
    assert resultado.get("error_code") == "INVALID_INPUT", resultado
    assert nota.read_bytes() == antes


@pytest.mark.parametrize("fichero,contenido", [
    ("inmutable.json", "{}"),
    ("inmutable.json", '{"seccion": ["11_Code"]}'),
    # S15/A3: an unknown key blocks only when the owner declared the policy
    # mandatory; the non-mandatory case is covered in test_reglas_y_adaptadores.
    ("reglas.json", '{"no_borrarr": ["11_Code"], "obligatoria": true}'),
])
def test_claves_de_politica_invalidas_no_abren_escritura(vault, fichero, contenido):
    (vault / "00_System" / fichero).write_text(contenido, encoding="utf-8")
    nota = vault / "11_Code" / "nota-historica.md"
    antes = nota.read_bytes()
    with pytest.raises(vault_io.PoliticaInvalidaError):
        vault_io.atomic_write_text(nota, "no debe escribirse")
    assert nota.read_bytes() == antes


def test_enlace_inmutable_que_no_puede_actualizarse_se_declara(vault):
    carpeta = vault / "07_Knowledge"
    carpeta.mkdir()
    origen = carpeta / "origen.md"
    origen.write_text("---\ntitle: Origen\ntype: knowledge\n---\n\nContenido.\n", encoding="utf-8")
    referencia = vault / "11_Code" / "nota-historica.md"
    referencia.write_text("\n".join((NOTA, "[[origen]]", "")), encoding="utf-8")
    antes = referencia.read_bytes()
    resultado = vault_move.move_note("07_Knowledge/origen.md", "07_Knowledge/nuevo.md", backup=False)
    assert resultado.get("ok"), resultado
    assert not origen.exists()
    assert (carpeta / "nuevo.md").exists()
    assert referencia.read_bytes() == antes
    assert "11_Code/nota-historica.md" in resultado["links_pending"], resultado
    assert any("IMMUTABLE_NOTE" in str(x) for x in resultado["degraded"]), resultado
    assert "links_pending" in resultado["next"]


def test_ap70_audita_politica_corrupta_sin_repararla(vault):
    from vault.gobernanza.auditoria_runtime import auditar_runtime
    from vault_norms_catalog import norma_por_codigo
    politica = vault / "00_System" / "reglas.json"
    politica.write_text('{"no_borrarr": ["11_Code"]}', encoding="utf-8")
    antes = politica.read_bytes()
    resultado = auditar_runtime(vault)
    assert norma_por_codigo("AP-70")["enforcement"] == "guard+audit"
    assert any(v["norm"] == "AP-70" for v in resultado["violations"]), resultado
    assert politica.read_bytes() == antes
