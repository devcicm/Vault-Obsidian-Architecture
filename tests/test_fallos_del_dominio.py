"""v40.29 — quién escribe el envelope cuando el que falla es el dominio.

La deuda `envelopes_del_dominio_sin_error_code` estuvo declarada nueve versiones
con el motivo escrito: no era una cuestión de forma sino de capas. Nueve sitios
de `vault/indices/` y `vault/durabilidad/` devolvían `{"ok": False, "error": …}`
y tres adaptadores lo reenviaban tal cual, sin `error_code` ni `recovery`.

Lo que estos tests fijan es el reparto, no la redacción:

* el **dominio** nombra la causa y no sabe que existe un catálogo de errores;
* la **tool** traduce, en un solo sitio, y ahí es donde aparece `error_code`;
* los campos que el contrato declara estables siguen saliendo.

El tercero es el que más fácil se rompería sin darse cuenta: mejorar el envelope
por debajo es exactamente la clase de cambio que se lleva por delante un `hint`
que alguien lee.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import vault_errors  # noqa: E402
import vault_errors_catalog  # noqa: E402
from vault.kernel import fallos  # noqa: E402


def test_el_dominio_no_conoce_el_catalogo_de_errores():
    """Si el kernel importara `vault_errors`, dejaría de ser kernel.

    Se mide sobre el texto de los módulos de `vault/` y no sobre los imports ya
    resueltos porque un import diferido dentro de una función acopla igual: es
    AP-58 aplicado a esta frontera.
    """
    culpables = []
    for ruta in (REPO_ROOT / "vault").rglob("*.py"):
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            desnuda = linea.strip()
            if not desnuda.startswith(("import ", "from ")):
                continue  # la prosa puede nombrarlo: explicar dónde vive la
                          # traducción es justo lo que hay que dejar escrito
            if "vault_errors" in desnuda:
                culpables.append(f"{ruta.relative_to(REPO_ROOT)}: {desnuda}")
    assert culpables == [], (
        "el dominio no escribe el envelope de la herramienta: la traducción "
        "vive en vault_errors.emit_fallo"
    )


def test_fallos_no_importa_nada():
    """El vocabulario de causas es hoja: si depende de algo, deja de poder
    usarlo cualquier contexto sin arrastrarlo (AP-62)."""
    texto = (REPO_ROOT / "vault" / "kernel" / "fallos.py").read_text(encoding="utf-8")
    imports = [
        linea.strip()
        for linea in texto.splitlines()
        if linea.startswith(("import ", "from "))
    ]
    assert imports == ["from __future__ import annotations", "from typing import Any, Dict"]


def test_toda_causa_tiene_traduccion_y_al_reves():
    """Las dos direcciones.

    Una causa sin traducción saldría al consumidor por el camino genérico, que
    es la opacidad que esta tanda vino a cerrar; una traducción sin causa es una
    entrada muerta que sobrevive a que el dominio deje de emitirla.
    """
    assert set(fallos.CAUSAS) == set(vault_errors.MAPA_DE_FALLOS)
    for causa, codigo in vault_errors.MAPA_DE_FALLOS.items():
        assert codigo in vault_errors_catalog.ERROR_CATALOG, causa


def test_una_causa_no_declarada_no_se_puede_levantar():
    with pytest.raises(ValueError, match="causa no declarada"):
        fallos.FalloDeDominio("CAUSA_INVENTADA", "da igual")


def test_el_envelope_traducido_trae_lo_que_el_consumidor_decide_por():
    fallo = fallos.FalloDeDominio("BACKUP_NO_ENCONTRADO", "Backup not found: x",
                                  searched=["a", "b"])
    env = vault_errors.emit_fallo("vault_restore", fallo)
    assert env["ok"] is False
    assert env["error_code"] == "BACKUP_NOT_FOUND"
    assert env["recovery"]["action"] == "run_tool"
    assert env["causa"] == "BACKUP_NO_ENCONTRADO"
    # `error` no es redundante con `message`: es campo estable del contrato.
    assert env["error"] == "Backup not found: x"
    assert env["searched"] == ["a", "b"]
    # El envelope tiene que poder viajar: es lo único que ve el consumidor.
    json.dumps(env)


def test_las_tres_causas_del_manifiesto_comparten_codigo_pero_no_causa():
    """Compartir destino no pierde información: de las tres se recupera igual,
    y cuál de las tres fue lo dice `causa`."""
    codigos = {
        vault_errors.MAPA_DE_FALLOS[c]
        for c in ("MANIFIESTO_AUSENTE", "MANIFIESTO_ILEGIBLE", "MANIFIESTO_SIN_HUELLA")
    }
    assert codigos == {"BACKUP_MANIFEST_INVALID"}
    envs = [
        vault_errors.emit_fallo("vault_backup", fallos.FalloDeDominio(c, "m"))["causa"]
        for c in ("MANIFIESTO_AUSENTE", "MANIFIESTO_ILEGIBLE", "MANIFIESTO_SIN_HUELLA")
    ]
    assert len(set(envs)) == 3


def test_los_campos_estables_de_vault_restore_sobreviven_al_fallo():
    """El contrato de campos manda sobre la mejora del envelope.

    `error`, `hint` y `searched` están declarados estables en
    `field-compat-baseline.json`; que ahora salgan acompañados de `error_code`
    no autoriza a que dejen de salir.
    """
    import vault_restore

    sin_confirmar = vault_restore.vault_restore("da-igual")
    assert sin_confirmar["ok"] is False
    assert sin_confirmar["error_code"] == "MISSING_REQUIRED_ARG"
    assert "hint" in sin_confirmar and "vault_backup" in sin_confirmar["hint"]

    no_existe = vault_restore.vault_restore("no-existe-jamas", confirm=True)
    assert no_existe["error_code"] == "BACKUP_NOT_FOUND"
    assert len(no_existe["searched"]) == 2
    assert no_existe["error"].startswith("Backup not found:")


def test_la_deuda_de_ap52_llego_a_cero():
    """158 sitios en v40.0, nueve al empezar esta tanda, cero al cerrarla.

    Se comprueba la baseline vacía y no un número, porque el número escrito
    aquí sería AP-47 dentro del test que vigila el mecanismo anti-drift.
    """
    baseline = json.loads(
        (REPO_ROOT / "scripts" / "error-contract-baseline.json").read_text(
            encoding="utf-8"
        )
    )
    assert baseline["sites"] == []
