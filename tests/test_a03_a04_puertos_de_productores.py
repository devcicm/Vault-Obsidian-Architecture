"""A-03 y A-04 — el kernel pide por puerto; el productor se ofrece al importarse.

Las dos son la misma forma de un mismo problema: el kernel (`vault_io`,
`vault_errors`) necesitaba algo de un contexto de dominio y lo importaba. Eso
era un ciclo diferido (AP-58) y un cruce de contexto (`kernel -> dominio`).

Con el registro de productores, el kernel **pide** por un puerto y quien lo
implementa **se ofrece al importarse**. La diferencia que estos tests fijan no
es de forma: es que la ausencia del productor es un estado **observable**, no
un gancho que desaparece en silencio.

Tres cosas se comprueban:

1. El productor se ofrece al importarse y el kernel lo encuentra.
2. El kernel **no importa** al productor: no hay `vault_section_index` ni
   `vault_tags` ni `vault.autoria.voz` en su grafo de imports (AP-58 y el
   cruce `kernel -> dominio`).
3. Sin productor, el kernel **degrada con el motivo escrito** en vez de
   callarse: el gancho se pierde a la vista, que es lo que antes no pasaba.
"""

import ast
import json
from pathlib import Path

import pytest

from apoyo import SCRIPTS, ROOT


def _importa(modulo: str):
    """Importa un módulo del repo.

    El `sys.path` lo pone el conftest (AP-69): aquí solo se importa.
    """
    return __import__(modulo)


def _imports_de(modulo: str) -> set:
    """Los módulos que importa `scripts/<modulo>.py`, por AST."""
    ruta = SCRIPTS / f"{modulo}.py"
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    salida = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            salida |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            salida.add(n.module.split(".")[0])
    return salida


# ── 1. El productor se ofrece al importarse ─────────────────────────────────


def test_el_productor_se_ofrece_al_importarse():
    """Importar el productor basta para que el kernel lo encuentre."""
    from vault.kernel import productores

    productores.limpiar()
    assert not productores.hay("voz"), "el registro arranca vacío"

    _importa("vault.autoria.voz")
    assert productores.hay("voz"), (
        "importar `vault.autoria.voz` tiene que ofrecer la voz al registro; "
        "si no, el gancho desaparece en silencio")

    productores.limpiar()
    assert not productores.hay("indices")
    _importa("vault_section_index")
    assert productores.hay("indices"), (
        "importar `vault_section_index` tiene que ofrecer el regenerador")


def test_el_registro_distingue_ausencia_de_presencia():
    """`None` es un estado: se puede comprobar que no hay nadie."""
    from vault.kernel import productores

    productores.limpiar()
    assert productores.buscar("voz") is None
    assert not productores.hay("voz")
    assert "voz" not in productores.registrados()


def test_el_runtime_ofrece_lo_que_se_le_pide():
    """El runtime compone: ofrece el productor que le piden."""
    from vault.kernel import productores
    import vault.runtime as runtime

    productores.limpiar()
    assert runtime.componer_voz() is True
    assert runtime.componer_indices() is True
    assert runtime.componer_voz() is True  # idempotente
    assert set(productores.registrados()) >= {"voz", "indices"}


def test_el_registro_avisa_si_se_sustituye_un_productor():
    """Registrar dos veces el mismo nombre con otro productor avisa."""
    from vault.kernel import productores

    productores.limpiar()
    primero = object()
    segundo = object()
    productores.registrar("voz", primero)
    with pytest.warns(RuntimeWarning, match="ya estaba registrado"):
        productores.registrar("voz", segundo)
    assert productores.buscar("voz") is segundo
    productores.limpiar()


# ── 2. El kernel no importa al productor ────────────────────────────────────


def test_el_kernel_no_importa_a_sus_productores():
    """A-03: `vault_io` no importa a quien le regenera los índices."""
    imports = _imports_de("vault_io")
    assert "vault_section_index" not in imports, (
        "`vault_io` vuelve a importar `vault_section_index`: el ciclo "
        "`vault_io -> vault_section_index` ha vuelto")
    assert "vault_tags" not in imports, (
        "`vault_io` vuelve a importar `vault_tags`: el ciclo "
        "`vault_io -> vault_tags` ha vuelto")


def test_el_kernel_de_errores_no_importa_la_voz():
    """A-04: `vault_errors` no importa la voz del dominio."""
    fuente = (SCRIPTS / "vault_errors.py").read_text(encoding="utf-8")
    assert "from vault.autoria.voz import" not in fuente, (
        "`vault_errors` vuelve a importar `vault.autoria.voz`: el cruce "
        "`kernel -> autoria` ha vuelto")


def test_la_voz_llega_al_envelope_por_el_puerto():
    """El camino real: una tool emite su envelope y el `vault_says` está."""
    from apoyo import correr_tool

    corrida = correr_tool("vault_voice", "--tool", "vault_write")
    assert corrida.codigo == 0, corrida.stderr[-500:]
    envelope = json.loads(corrida.stdout)
    assert envelope.get("vault_says"), (
        "la voz no llega al envelope: el productor no se ofreció en la raíz "
        "de composición")


# ── 3. Sin productor, el kernel degrada con el motivo escrito ───────────────


def test_sin_productor_el_gancho_falla_con_el_motivo_escrito():
    """La diferencia real: la ausencia se dice, no se calla.

    Con el import diferido, si nadie importaba al productor el gancho
    desaparecía y la nota se escribía sin índice y sin bitácora, sin que
    nada lo dijera. Ahora el gancho falla con un motivo en la traza.

    Para que el caso sea real —nadie atiende el puerto— se vacía el registro
    **después** de componer: el gancho no se auto-serviza (ofrecer el
    productor es oficio de la raíz de composición), así que con el registro
    vacío el gancho no encuentra a nadie y tiene que dejar escrito su
    motivo. Vaciarlo antes no serviría: la composición lo volvería a llenar.
    """
    import shutil
    import tempfile

    from vault.kernel.productores import limpiar

    vault_io = _importa("vault_io")

    destino = Path(tempfile.mkdtemp(prefix="a03-")) / "vault"
    shutil.copytree(ROOT / "vault-sandbox", destino)
    anterior = vault_io.get_vault_root()
    vault_io.set_vault_root(destino)
    try:
        # La ruta se toma de la raíz **resuelta**, no de la que dio
        # `tempfile`: en Windows la forma corta (`CARLOS~1`) y la larga no se
        # comparan con `relative_to`, y el gancho se creería fuera del vault.
        nota = vault_io.get_vault_root() / "07_Knowledge" / "nota-de-prueba.md"
        nota.parent.mkdir(parents=True, exist_ok=True)
        traza = vault_io.get_vault_root() / "00_System" / ".tool-trace.json"
        traza.write_text("[]", encoding="utf-8")
        # Frontmatter con `title`: el gancho solo dispara en las notas que lo
        # llevan (`_seccion_con_indice` mira el título, no solo la extensión).
        #
        # El registro se vacía DESPUÉS de componer: nadie atiende.
        limpiar()
        vault_io.atomic_write_text(
            nota, "---\ntitle: Nota de prueba\n---\n\ncuerpo de la nota\n")
        # La traza se lee ANTES de restaurar la raíz: `log_trace` escribe
        # donde dice `get_vault_root()`, que aquí es el vault de prueba.
        texto = traza.read_text(encoding="utf-8") if traza.exists() else ""
    finally:
        vault_io.set_vault_root(anterior)
        shutil.rmtree(destino.parent, ignore_errors=True)
        limpiar()

    assert "AUTO_INDEX_ERROR" in texto or "AUTO_TAG_LEDGER_ERROR" in texto, (
        "sin productor, el gancho tiene que dejar escrito su motivo; si no, "
        "vuelve a desaparecer en silencio")


class _Mudo:
    """Un doble que no hace nada: el puerto existe, pero nadie cumple."""

    def regenerar(self, seccion, rutas, nombres=None):
        return []

    def anotar(self, texto, ruta_relativa):
        return None
