"""`vault init` instalado deja el vault navegable, no solo con carpetas.

Medido el 2026-10-04 en la QA de producto: el init de la wheel escribía un hub
mínimo («Runtime documental inicializado…») sin un solo enlace. Como
`vault_section_index` solo crea el hub si falta, el hub completo —el que
enlaza secciones y la nota de comandos— no se creaba nunca, y tampoco
`vault-commands.md`, los índices de sección ni los primers. El vault del
consumidor arrancaba con 23 carpetas vacías y ningún punto de entrada.
"""

import json
import os
import subprocess
import sys

from vault.ciclo_de_vida import producto


def _init_por_cli(root):
    p = subprocess.run(
        [sys.executable, "-c",
         "import sys; from vault.product_cli import main; sys.exit(main(sys.argv[1:]))",
         "init", str(root)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=dict(os.environ, PYTHONIOENCODING="utf-8"), timeout=600,
    )
    assert p.returncode == 0, p.stderr[-800:]
    return json.loads(p.stdout)


def test_el_init_de_la_cli_deja_hub_con_enlaces_y_nota_de_comandos(tmp_path):
    root = tmp_path / "rt"
    r = _init_por_cli(root)
    assert r["state"] == producto.CREATED and r["bootstrap"]["ok"] is True, r
    hub = (root / "00_System" / "vault-hub.md").read_text(encoding="utf-8")
    assert "[[vault-commands" in hub, hub[:400]
    assert "Runtime documental inicializado" not in hub
    assert (root / "00_System" / "vault-commands.md").is_file()
    for seccion in r["sections"]:
        if seccion != "00_System":
            assert (root / seccion / "index.md").is_file(), seccion
    assert producto.diagnosticar_runtime(root)["state"] == "RUNTIME_OK"
    # Idempotente: el segundo init no repuebla ni choca.
    assert _init_por_cli(root)["state"] == producto.ALREADY_INITIALIZED


def test_un_bootstrap_que_falla_deja_el_runtime_valido_y_lo_dice(tmp_path):
    root = tmp_path / "rt"
    r = producto.inicializar_runtime(
        root, bootstrap=lambda _: {"ok": False, "detail": "sin vault_init"})
    assert r["ok"] is True and r["bootstrap"] == {"ok": False, "detail": "sin vault_init"}
    assert (root / "00_System" / "vault-hub.md").is_file()
    assert producto.diagnosticar_runtime(root)["state"] == "RUNTIME_OK"


def test_un_bootstrap_que_lanza_no_pierde_el_runtime(tmp_path):
    def revienta(_):
        raise RuntimeError("boom")

    root = tmp_path / "rt"
    r = producto.inicializar_runtime(root, bootstrap=revienta)
    assert r["bootstrap"]["ok"] is False and "boom" in r["bootstrap"]["detail"]
    assert producto.diagnosticar_runtime(root)["state"] == "RUNTIME_OK"


def test_el_bootstrap_escribe_el_hub_y_el_seed_no_lo_pisa(tmp_path):
    """Con bootstrap, el seed no escribe el hub mínimo: si lo hiciera, el
    bootstrap lo encontraría y dejaría de escribir el completo."""
    vistos = []

    def mira(root):
        vistos.append((root / "00_System" / "vault-hub.md").exists())
        (root / "00_System" / "vault-hub.md").write_text("hub\n", encoding="utf-8")
        return {"ok": True}

    root = tmp_path / "rt"
    producto.inicializar_runtime(root, bootstrap=mira)
    assert vistos == [False]
    assert (root / "00_System" / "vault-hub.md").read_text(encoding="utf-8") == "hub\n"
