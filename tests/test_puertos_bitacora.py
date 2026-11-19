"""The change-log port (`bitacora_cambios`): consulta and gobernanza write the
operation log without importing autoria.

`vault_ingest` (consulta) logs `ingested` and applies the appends it proposes;
the mutation-allowed lint run of `vault_audit` (gobernanza) logs `linted`.
Importing `vault_change_log` or `vault_append` from either would be a new
context crossing (`vault_arch`). The kernel declares the port, the autoria
side offers it on import, and the runtime composes it on demand — the same
mechanism as `indices` and `tags`. Without a producer the main action still
succeeds and the envelope says the row was not written.
"""

import json
from pathlib import Path

import pytest
from apoyo import filas_de_bitacora


@pytest.fixture(autouse=True)
def _registro_restaurado():
    """The producer registry lives per process: restore it after each test."""
    from vault.kernel import productores

    previo = productores.registrados()
    try:
        yield
    finally:
        productores.limpiar()
        for nombre, producto in previo.items():
            productores.registrar(nombre, producto)


@pytest.fixture
def vault(tmp_path):
    import vault_io

    raiz = tmp_path / "vault"
    (raiz / "07_Knowledge").mkdir(parents=True)
    previa = vault_io.set_vault_root(raiz)
    yield raiz
    vault_io.set_vault_root(previa)


TEXTO = "\n".join([
    "# Arranque del cluster",
    "El arranque del cluster tiene dos fases y una verificación previa.",
    "La segunda fase depende de que la primera deje el quorum formado.",
])


def _filas(raiz: Path, accion: str) -> list:
    return [f for f in filas_de_bitacora(raiz) if f["action"] == accion]


def test_el_runtime_compone_el_puerto_de_la_bitacora():
    from vault import runtime
    from vault.kernel import productores
    from vault.kernel.puertos import BitacoraCambios

    assert runtime.PRODUCTORES["bitacora_cambios"] == "vault.autoria.bitacora"
    productores.restaurar("bitacora_cambios", None)
    runtime.componer("bitacora_cambios")
    assert isinstance(productores.buscar("bitacora_cambios"), BitacoraCambios)


def test_el_kernel_no_importa_al_productor_de_la_bitacora():
    import ast

    raiz = Path(__file__).resolve().parents[1]
    for modulo in ("vault/kernel/puertos.py", "vault/kernel/productores.py"):
        arbol = ast.parse((raiz / modulo).read_text(encoding="utf-8"))
        importados = {getattr(n, "module", None) or "" for n in ast.walk(arbol)
                      if isinstance(n, ast.ImportFrom)}
        importados |= {a.name for n in ast.walk(arbol) if isinstance(n, ast.Import)
                       for a in n.names}
        assert not any(m.startswith(("vault.autoria", "vault_change_log", "vault_append"))
                       for m in importados), (modulo, importados)


def test_ingest_commit_deja_una_fila_ingested(vault):
    import vault_ingest

    r = vault_ingest.vault_ingest(TEXTO, "07_Knowledge", "--text", "inline",
                                  commit=True, agent="pytest")

    assert r["ok"] and r["written"], r
    filas = _filas(vault, "ingested")
    assert len(filas) == 1 and filas[0]["agent"] == "pytest", filas
    assert r["change_log"] == {"id": filas[0]["id"], "action": "ingested"}


def test_ingest_en_dry_run_no_anota_nada(vault):
    import vault_ingest

    r = vault_ingest.vault_ingest(TEXTO, "07_Knowledge", "--text", "inline", agent="pytest")

    assert r["ok"] and "change_log" not in r
    assert _filas(vault, "ingested") == []


def test_sin_productor_la_ingesta_escribe_y_dice_que_no_anoto(vault, monkeypatch):
    from vault import runtime
    from vault.kernel import productores
    import vault_ingest

    productores.restaurar("bitacora_cambios", None)
    monkeypatch.setattr(runtime, "componer", lambda *nombres: {})

    r = vault_ingest.vault_ingest(TEXTO, "07_Knowledge", "--text", "inline",
                                  commit=True, agent="pytest")

    assert r["ok"] and r["written"], r
    assert (vault / r["written"][0]).is_file()
    assert "change_log" not in r
    assert "bitacora_cambios" in r["change_log_error"]
    assert _filas(vault, "ingested") == []


def test_el_lint_con_permiso_de_escritura_deja_una_fila_linted(vault):
    import vault_audit

    r = vault_audit.vault_audit(refresh_dq=True)

    filas = _filas(vault, "linted")
    assert len(filas) == 1, filas
    assert r["change_log"] == {"id": filas[0]["id"], "action": "linted"}


def test_el_lint_de_solo_lectura_no_escribe_en_la_bitacora(vault):
    import vault_audit

    r = vault_audit.vault_audit()

    assert "change_log" not in r and _filas(vault, "linted") == []
