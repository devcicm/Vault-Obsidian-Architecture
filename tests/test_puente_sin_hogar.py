"""El puente `scripts/` → `_impl/` tiene cifra derivada y frontera (deuda #12).

ADR-0002 declara el puente transitorio: desaparece cuando el código de
`scripts/` viva en `vault/<contexto>/`. Hasta aquí nadie medía cuánto faltaba,
y un módulo nuevo podía entrar en `scripts/` con toda su lógica sin que nada
lo notara. `vault_arch.modulos_sin_hogar` cuenta los módulos que no importan
nada del paquete de su propio contexto; la baseline `bridge_modules` congela
los que ya estaban y solo encoge.

Lo que la cifra **no** dice: que un módulo que sí importa de su contexto haya
migrado entero. Importar un repositorio es empezar a delegar, no terminar; el
criterio es sintáctico y se declara así en el docstring del detector.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import vault_arch  # noqa: E402


def test_un_modulo_que_importa_de_su_contexto_tiene_hogar():
    arbol = ast.parse("from vault.grafo.repositorio import RepositorioGrafo\n")
    assert vault_arch.tiene_hogar(arbol, "grafo") is True


def test_importar_solo_del_kernel_no_es_hogar_para_otro_contexto():
    arbol = ast.parse("from vault.kernel import construir\nimport json\n")
    assert vault_arch.tiene_hogar(arbol, "grafo") is False
    assert vault_arch.tiene_hogar(arbol, "kernel") is True


def test_la_cifra_es_la_baseline_y_no_crece():
    sin_hogar = vault_arch.modulos_sin_hogar()
    base = json.loads((ROOT / "scripts" / "arch-baseline.json")
                      .read_text(encoding="utf-8"))["bridge_modules"]
    assert set(sin_hogar) <= set(base)
    r = vault_arch.check()
    assert r["bridge_modules_total"] == len(sin_hogar)
    assert r["new_bridge_modules"] == []


def test_un_modulo_nuevo_sin_hogar_bloquea_la_puerta(monkeypatch):
    actuales = vault_arch.modulos_sin_hogar()
    monkeypatch.setattr(vault_arch, "modulos_sin_hogar",
                        lambda: sorted(actuales + ["vault_nuevo_sin_hogar"]))
    r = vault_arch.check()
    assert r["ok"] is False
    assert r["new_bridge_modules"] == ["vault_nuevo_sin_hogar"]


def test_el_plano_publica_la_cifra_derivada():
    import vault_blueprint

    texto = vault_blueprint.blueprint()
    assert f"{len(vault_arch.modulos_sin_hogar())} módulos de `scripts/`" in texto


def test_la_cifra_vive_dentro_de_la_capa_3_y_no_estrena_capa():
    """m150 la publicó como octava clave de `capas()` y rompió las siete capas
    del plano. La cifra es de contextos: cada contexto dice cuántos de sus
    módulos siguen sin hogar, y la suma es la cifra del puente."""
    import vault_blueprint

    c = vault_blueprint.capas()
    assert len(c) == 7 and "3_puente_sin_hogar" not in c
    por_contexto = {ctx: d["sin_hogar"] for ctx, d in c["3_contextos"].items()}
    assert sum(por_contexto.values()) == len(vault_arch.modulos_sin_hogar())
    esperado = {}
    for modulo in vault_arch.modulos_sin_hogar():
        ctx = vault_arch.contexto_de(modulo)
        esperado[ctx] = esperado.get(ctx, 0) + 1
    assert {k: v for k, v in por_contexto.items() if v} == esperado


def test_el_piloto_vive_en_el_kernel_y_scripts_lo_reexporta():
    """Primera migración (2026-10-09): `vault_subproceso`, hoja del kernel.

    El dueño pasa a `vault/kernel/subproceso.py`; el nombre de `scripts/` se
    conserva como fachada (no-derogación) y es el mismo objeto, no una copia.
    """
    import vault_subproceso
    from vault.kernel import subproceso

    assert "vault_subproceso" not in vault_arch.modulos_sin_hogar()
    assert vault_subproceso.ejecutar is subproceso.ejecutar
    assert vault_subproceso.sitios_sin_codificacion is subproceso.sitios_sin_codificacion
    assert (vault_subproceso.CODIFICACION, vault_subproceso.ERRORES) == ("utf-8", "replace")


def test_el_ledger_vive_en_el_kernel_y_scripts_lo_reexporta():
    """Segunda migración (2026-10-09): `vault_ledger`, hoja del kernel.

    El contador es thread-local: la fachada tiene que reexportar **el mismo**
    `threading.local`, o `vault_io` y `vault_errors` contarían en dos libros.
    """
    import vault_io
    import vault_ledger
    from vault.kernel import ledger

    assert "vault_ledger" not in vault_arch.modulos_sin_hogar()
    assert vault_ledger._write_ledger is ledger._write_ledger
    assert vault_io._write_ledger is ledger._write_ledger
    for nombre in ("write_report", "write_ledger_reset", "record_raw_write",
                   "_record_write", "_ledger", "_NO_ES_TRABAJO"):
        assert getattr(vault_ledger, nombre) is getattr(ledger, nombre), nombre
    ledger.write_ledger_reset()
    assert vault_io.write_report()["written"] == 0


def test_lo_que_no_viaja_en_la_wheel_no_cuenta_como_puente():
    """El puente de ADR-0002 existe para la wheel: mapea `scripts/` a
    `vault_toolkit/_impl/`. Un módulo que la wheel excluye
    (`empaquetado/fuera-de-la-wheel.json`, derivado de la capacidad
    «gobernanza del estándar») no cruza ese puente, y contarlo inflaba la
    deuda #12 con módulos que no tienen que migrar para que el puente caiga."""
    fuera = set(json.loads((ROOT / "empaquetado" / "fuera-de-la-wheel.json")
                           .read_text(encoding="utf-8"))["modulos"])
    assert fuera, "la lista de exclusión está vacía: el test no probaría nada"
    assert not fuera & set(vault_arch.modulos_sin_hogar())


LOTE_A = {
    "vault_audit_catalog": "vault.kernel.audit_catalog",
    "vault_fundamentals_catalog": "vault.kernel.fundamentals_catalog",
    "vault_mermaid_reglas": "vault.kernel.mermaid_reglas",
    "vault_security_rules": "vault.gobernanza.security_rules",
}


def test_el_lote_a_es_alias_del_dueno_y_no_una_copia(monkeypatch):
    """Lote A de la deuda #12 (2026-10-09): hojas sin `__file__` ni lectores
    del fuente por ruta. A diferencia de las dos primeras migraciones, el
    nombre de `scripts/` es un alias en `sys.modules`: `import vault_x`
    devuelve el módulo del dueño, y un monkeypatch sobre él lo ve el dueño."""
    import importlib

    sin_hogar = set(vault_arch.modulos_sin_hogar())
    for viejo, dueno in LOTE_A.items():
        assert viejo not in sin_hogar, viejo
        assert importlib.import_module(viejo) is importlib.import_module(dueno), viejo
        assert not (ROOT / "vault" / dueno.split(".")[1] / f"{viejo}.py").exists()

    import vault_audit_catalog
    from vault.kernel import audit_catalog

    monkeypatch.setattr(vault_audit_catalog, "_SONDA_DEL_ALIAS", 1, raising=False)
    assert audit_catalog._SONDA_DEL_ALIAS == 1


def test_los_guards_que_leen_el_fuente_siguen_el_alias_hasta_el_dueno():
    """Un alias en `sys.modules` no tiene código: leer `scripts/<m>.py` como
    fuente de la tool dejó a `vault_norms_coherence` sin la traza de AP-44 en
    `vault_mermaid_reglas`, y a `vault_arch` sin reconocer como dueño de
    vocabulario a `vault/kernel/fundamentals_catalog.py`. Un solo sitio
    resuelve el alias (AP-57): `vault_grafo_import.fuente_de`."""
    import vault_grafo_import as gi

    for viejo, dueno in LOTE_A.items():
        esperado = ROOT.joinpath(*dueno.split(".")).with_suffix(".py").resolve()
        assert gi.fuente_de(viejo) == esperado, viejo
        assert gi.nombre_de(esperado) == viejo, viejo
    # Un módulo que no es alias se resuelve a sí mismo.
    assert gi.fuente_de("vault_arch") == (ROOT / "scripts" / "vault_arch.py").resolve()
    assert gi.nombre_de(ROOT / "scripts" / "vault_arch.py") == "vault_arch"

    import vault_norms_coherence as nc

    assert "AP-44" in nc._fuente("vault_mermaid_reglas")
    assert not [c for c in vault_arch.copias_de_vocabulario()
                if "fundamentals_catalog" in str(c.get("module", c))]
