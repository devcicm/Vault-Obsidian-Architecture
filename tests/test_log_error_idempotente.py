"""Loggear dos veces el mismo error no son dos errores (v41.12).

`vault_log_error` compone la nota con `uuid4` y sellos de cada llamada: el
mismo suceso re-loggeado reescribía el fichero con id y fechas nuevas y el C3
del auditor lo medía por hash de contenido. La cura —`conservar_nota_de_error`
en el dominio dueño— compara el cuerpo sin los campos de reloj e identidad; si
coincide con la nota que ya hay, el disco queda tal cual y el ledger la cuenta
como `unchanged`. A contenido distinto (otra descripción, otro contexto) le
toca nota nueva: eso es un suceso distinto, no una repetición.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import pytest

from vault.autoria.log_error import (  # noqa: E402
    conservar_nota_de_error,
    texto_estable_de_error,
)

def nota_de_error(vault, titulo="NullPointerException"):
    """La nota que la tool acaba de escribir, por patron y no por fecha fija.

    El nombre lleva la fecha del dia EN QUE SE ESCRIBE. Fijarla al importar el
    modulo hacia que una corrida que cruza las 00:00 UTC buscara el fichero con
    la fecha de ayer (rojo en la CI de cc8c770, ubuntu y windows). El sujeto del
    test no es el nombre: es que la nota exista y que re-loggear el mismo suceso
    no la reescriba.
    """
    candidatas = sorted((vault / "02_Observability" / "errors").glob(
        f"*-{titulo.lower()}.md"))
    assert candidatas, (
        f"no se creo ninguna nota para {titulo!r} en "
        f"{vault / '02_Observability' / 'errors'}")
    assert len(candidatas) == 1, f"notas inesperadas: {candidatas}"
    return candidatas[0]


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    (tmp_path / "02_Observability" / "errors").mkdir(parents=True)
    # La raíz es constante de módulo (calculada al importar): el env var solo
    # no basta — anclar el override es lo que evita escribir en el sandbox del
    # repo (patrón de test_contrato_de_campos.py).
    from vault_io import reset_vault_root, set_vault_root

    set_vault_root(tmp_path)
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    yield tmp_path
    reset_vault_root()


def loguea(vault, **cambios):
    """Corre la función del dominio con el ejemplo del catálogo y opcionalmente
    un campo cambiado; devuelve el envelope."""
    from vault.autoria.log_error import vault_log_error

    args = dict(
        error_type="error",
        title="NullPointerException",
        description="Fallo de puntero nulo en el servicio de pagos",
        severity="high",
    )
    args.update(cambios)
    return vault_log_error(**args)


def test_re_loggear_el_mismo_error_no_reescribe_la_nota(vault):
    primero = loguea(vault)
    assert primero["ok"] is True, primero
    nota = nota_de_error(vault)
    assert nota.exists()
    contenido = nota.read_bytes()

    segundo = loguea(vault)
    # Mismo suceso: el disco queda tal cual y la nota se cuenta como tal.
    # (Los contadores de la cascada —hub, índices, registros— son el reporte
    # acumulado del ledger y no distinguen corridas: ese olor AP-37 queda
    # anotado para el auditor; aquí manda el criterio del consumidor: bytes.)
    assert nota.read_bytes() == contenido
    assert segundo["unchanged"] >= 1
    # La ruta publicada se comprueba por FORMA (carpeta y sufijo), no por
    # fecha: el nombre la toma del reloj al escribir.
    ruta = segundo["path"].replace("\\", "/")
    assert ruta.startswith("02_Observability/errors/"), ruta
    assert ruta.endswith("-nullpointerexception.md"), ruta


def test_un_suceso_distinto_si_reescribe(vault):
    loguea(vault)
    nota = nota_de_error(vault)
    antes = nota.read_text(encoding="utf-8")

    loguea(vault, description="Fallo distinto: timeout en la pasarela")
    despues = nota.read_text(encoding="utf-8")
    assert antes != despues
    assert "timeout en la pasarela" in despues


def test_texto_estable_de_error_quita_identidad_y_sellos():
    """El comparador excluye lo que cambia por llamada, no lo que describe el
    suceso: id, createdAt/updatedAt y la línea **Fecha:** del cuerpo."""
    a = ("---\n"
         "title: NullPointerException\n"
         "id: 11111111-1111-1111-1111-111111111111\n"
         "createdAt: 2026-10-20T10:00:00+00:00\n"
         "updatedAt: 2026-10-20T10:00:00+00:00\n"
         "---\n"
         "# NullPointerException\n"
         "**Fecha:** 2026-10-20T10:00:00+00:00\n"
         "**Severidad:** HIGH\n")
    b = a.replace("11111111", "22222222").replace("T10:", "T11:")
    assert texto_estable_de_error(a) == texto_estable_de_error(b)
    c = a.replace("HIGH", "CRITICAL")
    assert texto_estable_de_error(a) != texto_estable_de_error(c)


def test_conservar_nota_de_error_sin_fichero_previo_devuelve_el_nuevo(tmp_path):
    nuevo = "---\ntitle: x\n---\ncuerpo\n"
    assert conservar_nota_de_error(tmp_path / "no-existe.md", nuevo) == nuevo
