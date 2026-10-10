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

import pytest

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


def test_lote_b_un_alias_ejecutado_como_script_corre_el_main_del_dueno(tmp_path):
    """Lote B de la deuda #12 (2026-10-09): `vault_secret_scan` es hoja pero
    también CLI. Un alias en `sys.modules` no ejecuta el `__main__` del dueño
    —el dueño se carga con su propio nombre—, así que el alias de una tool con
    CLI lo delega con `runpy`. Se prueba por las dos puertas: import y script."""
    import importlib
    import subprocess

    assert "vault_secret_scan" not in set(vault_arch.modulos_sin_hogar())
    assert (importlib.import_module("vault_secret_scan")
            is importlib.import_module("vault.gobernanza.secret_scan"))

    import vault_grafo_import as gi

    assert gi.fuente_de("vault_secret_scan") == (
        ROOT / "vault" / "gobernanza" / "secret_scan.py").resolve()

    nota = tmp_path / "n.md"
    # Compuesta al ejecutar: escrita de una pieza, el fuente tendría forma de
    # credencial y `test_publicacion_limpia` la cazaría con razón.
    clave = "AKIA" + "ABCDEFGHIJKLMNOP"
    nota.write_text(f"api_key = '{clave}'\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "vault_secret_scan.py"),
                        str(nota)], capture_output=True, text=True, encoding="utf-8")
    assert "potential secret" in r.stdout, (r.returncode, r.stdout, r.stderr)
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "vault_secret_scan.py"),
                        str(nota), "--json"], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 2, "argparse del dueño no corrió"


def test_lote_c_vault_entorno_vive_en_el_kernel():
    """Lote C de la deuda #12 (2026-10-09): `vault_entorno`, el registro de
    variables de entorno, es hoja sin `__file__` ni lectores de su fuente por
    ruta; el `.mjs` y `env-table.json` solo lo nombran en prosa, y la tabla se
    sigue derivando por import (`vault_arch --sync-env`)."""
    import importlib

    import vault_grafo_import as gi

    assert "vault_entorno" not in set(vault_arch.modulos_sin_hogar())
    assert (importlib.import_module("vault_entorno")
            is importlib.import_module("vault.kernel.entorno"))
    assert gi.fuente_de("vault_entorno") == (ROOT / "vault" / "kernel" / "entorno.py").resolve()
    assert "VAULT_ROOT" in importlib.import_module("vault_entorno").VARIABLES


LOTE_D = [
    ("vault_link_safety", "vault/grafo/link_safety.py"),
    ("vault_escaneo_grafo", "vault/kernel/escaneo_grafo.py"),
    ("vault_firma_sitio", "vault/meta_toolkit/firma_sitio.py"),
    ("vault_index", "vault/indices/indice.py"),
]


@pytest.mark.parametrize("modulo,dueno", LOTE_D)
def test_lote_d_cuatro_hojas_con_dependencias_solo_del_kernel(modulo, dueno):
    """Lote D de la deuda #12 (2026-10-10): hojas sin `__file__` cuyas
    dependencias en `scripts/` son del kernel, lo único que un módulo de
    `vault/<ctx>/` puede importar sin cruzar frontera. Ningún lector de su
    fuente por ruta: `vault_restore` nombra `vault_index.py` en la instalación
    del usuario, y ese fichero sigue existiendo como alias que corre el
    `__main__` del dueño."""
    import importlib

    import vault_grafo_import as gi

    assert modulo not in set(vault_arch.modulos_sin_hogar())
    nombre = dueno[:-3].replace("/", ".")
    assert importlib.import_module(modulo) is importlib.import_module(nombre)
    assert gi.fuente_de(modulo) == (ROOT / dueno).resolve()


LOTE_E = [
    ("vault_append", "vault/autoria/append.py"),
    ("vault_list", "vault/autoria/listar.py"),
    ("vault_log_error", "vault/autoria/log_error.py"),
    ("vault_merge", "vault/autoria/merge.py"),
    ("vault_project_status", "vault/autoria/project_status.py"),
    ("vault_runbook_log", "vault/autoria/runbook_log.py"),
    ("vault_section", "vault/indices/registro_de_secciones.py"),
    ("vault_env_matrix", "vault/grafo/env_matrix.py"),
]


@pytest.mark.parametrize("modulo,dueno", LOTE_E)
def test_lote_e_ocho_tools_con_cli_migran_y_el_alias_corre_su_main(modulo, dueno):
    """Lote E de la deuda #12 (2026-10-10): ocho tools con CLI, sin `__file__`,
    cuyas dependencias en `scripts/` son del kernel o de su contexto
    (`vault_merge` toma `vault_undo`, también de autoría). Sus lectores por ruta
    las ejecutan como script, y el alias delega el `__main__` con `runpy`."""
    import importlib
    import subprocess

    import vault_grafo_import as gi

    assert modulo not in set(vault_arch.modulos_sin_hogar())
    nombre = dueno[:-3].replace("/", ".")
    assert importlib.import_module(modulo) is importlib.import_module(nombre)
    assert gi.fuente_de(modulo) == (ROOT / dueno).resolve()
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / f"{modulo}.py"), "--help"],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0 and "usage" in r.stdout.lower(), r.stderr[-300:]


@pytest.mark.parametrize("modulo,dueno", LOTE_E)
def test_el_esquema_mcp_de_una_tool_migrada_se_lee_en_el_dueno(modulo, dueno):
    """`vault_mcp_catalog.argparse_params` leía `scripts/<tool>.py` por ruta y,
    tras migrar, encontraba el alias sin un solo `add_argument`: el esquema MCP
    se habría publicado vacío y el servidor rechazaría las llamadas válidas.
    Sigue el alias con `fuente_de`, como un import (AP-44)."""
    import vault_mcp_catalog as cat

    params = cat.argparse_params(f"{modulo}.py")
    texto = (ROOT / dueno).read_text(encoding="utf-8")
    assert params, f"{modulo}: argparse_params vacío, leyó el alias"
    assert all(f'"--{p.replace("_", "-")}"' in texto or f'"--{p}"' in texto
               for p in params), params


LOTE_F = [
    ("vault_history_compact", "vault/ciclo_de_vida/history_compact.py"),
    ("vault_arquitectura_en", "vault/ciclo_de_vida/arquitectura_en.py"),
    ("vault_graph_fix", "vault/grafo/graph_fix.py"),
    ("vault_supersede", "vault/autoria/supersede.py"),
    ("vault_frontmatter_completar", "vault/autoria/frontmatter_completar.py"),
    ("vault_frontmatter_heal", "vault/autoria/frontmatter_heal.py"),
]


@pytest.mark.parametrize("modulo,dueno", LOTE_F)
def test_lote_f_seis_tools_migran_y_el_alias_corre_su_main(modulo, dueno):
    """Lote F de la deuda #12 (2026-10-10). `vault_subgraph` se quedó fuera: su
    cruce hacia `vault/grafo` está en la baseline con la clave del nombre de
    `scripts/`, y moverlo lo habría re-clavado como cruce nuevo. Las caras de
    las normas que citan a estos seis apuntan ya al dueño."""
    import importlib
    import subprocess

    import vault_grafo_import as gi

    assert modulo not in set(vault_arch.modulos_sin_hogar())
    nombre = dueno[:-3].replace("/", ".")
    assert importlib.import_module(modulo) is importlib.import_module(nombre)
    assert gi.fuente_de(modulo) == (ROOT / dueno).resolve()
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / f"{modulo}.py"), "--help"],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0 and "usage" in r.stdout.lower(), r.stderr[-300:]


@pytest.mark.parametrize("modulo,dueno", LOTE_F)
def test_lote_f_ninguna_cara_de_norma_cita_el_alias(modulo, dueno):
    """Una cara que cita `scripts/<m>.py::símbolo` apunta a un fichero sin el
    símbolo tras la migración: tiene que citar al dueño."""
    viejo = f"scripts/{modulo}.py::"
    for cara in (ROOT / "normas").glob("*/*.py"):
        assert viejo not in cara.read_text(encoding="utf-8"), cara



LOTE_H = [
    ("vault_errors_trace", "vault/kernel/errors_trace.py", False),
    ("vault_fix_brackets", "vault/autoria/fix_brackets.py", True),
    ("vault_graph_inspect", "vault/grafo/graph_inspect.py", True),
    ("vault_sanacion", "vault/ciclo_de_vida/sanacion.py", True),
    ("vault_spec_generate_catalog", "vault/meta_toolkit/spec_generate_catalog.py", True),
]


@pytest.mark.parametrize("modulo,dueno,cli", LOTE_H)
def test_lote_h_los_cinco_con_firmas_en_baselines_migran(modulo, dueno, cli):
    """Lote H de la deuda #12 (2026-10-10): los cinco que tenían sitios en las
    baselines de AP-51 (blame) y AP-57 (criterios) o cruces en la de
    arquitectura. Migran porque la clave sigue al alias (m234, m245): sus firmas
    no salen como deuda nueva ni sus cruces como saldados."""
    import importlib
    import subprocess

    import vault_grafo_import as gi

    assert modulo not in set(vault_arch.modulos_sin_hogar())
    nombre = dueno[:-3].replace("/", ".")
    assert importlib.import_module(modulo) is importlib.import_module(nombre)
    assert gi.fuente_de(modulo) == (ROOT / dueno).resolve()
    assert vault_arch.clave_de_modulo(ROOT / dueno) == f"{modulo}.py"
    if cli:
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / f"{modulo}.py"), "--help"],
                           capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert r.returncode == 0 and "usage" in r.stdout.lower(), r.stderr[-300:]


def test_lote_h_el_cruce_de_sanacion_sigue_medido():
    claves = {f"{c['module']} -> {c['symbol']}" for c in vault_arch.cruces_fuera_de_puerto()}
    assert "vault_sanacion -> vault_reindex.notas_indexables" in claves


def test_spec_generate_catalog_lee_el_catalogo_donde_vive():
    """Leía `vault_mcp_catalog.py` junto a `__file__`, que tras migrar es
    `vault/meta_toolkit/`: el fichero no está ahí. Se deriva con `fuente_de`."""
    import vault_grafo_import as gi
    import vault_spec_generate_catalog as g

    assert g._CATALOGO == gi.fuente_de("vault_mcp_catalog")
    assert g._CATALOGO.is_file()

def test_la_clave_de_baseline_de_un_dueno_es_la_de_su_alias():
    """Las baselines por firma de sitio y la de cruces se indexan por el nombre
    de `scripts/`. Migrar un módulo con entradas las re-clavaba —la ruta del
    dueño en vez del nombre— y salían como deuda nueva más deuda resuelta: lo
    que dejó a `vault_subgraph` fuera del lote F. El nombre público del alias es
    la identidad que conserva la no-derogación, y la clave lo sigue."""
    import vault_grafo_import as gi

    dueno = gi.fuente_de("vault_graph_fix")
    assert dueno != (ROOT / "scripts" / "vault_graph_fix.py").resolve()
    assert vault_arch.clave_de_modulo(dueno) == "vault_graph_fix.py"
    # Un módulo de `vault/` que no es dueño de un alias conserva su ruta.
    repo = ROOT / "vault" / "grafo" / "repositorio.py"
    assert vault_arch.clave_de_modulo(repo) == "vault/grafo/repositorio.py"
    duenos = {p.relative_to(ROOT.resolve()).as_posix() for p in gi._puente().values()}
    assert not [c for c in vault_arch.cruces() if c["from"] in duenos]



def test_subgraph_migra_a_consulta_y_su_cruce_conserva_la_clave():
    """`vault_subgraph` se quedó fuera del lote F porque migrarlo re-clavaba su
    cruce `vault_subgraph -> vault/grafo` (está en la baseline) como cruce nuevo.
    Con la clave del dueño siguiendo al alias, migra a `vault/consulta/` y el
    cruce sigue siendo el mismo, ni nuevo ni resuelto."""
    import importlib
    import subprocess

    import vault_grafo_import as gi

    assert "vault_subgraph" not in set(vault_arch.modulos_sin_hogar())
    assert importlib.import_module("vault_subgraph") is importlib.import_module(
        "vault.consulta.subgraph")
    assert gi.fuente_de("vault_subgraph") == (ROOT / "vault/consulta/subgraph.py").resolve()
    claves = {f"{c['from']} -> {c['to']}" for c in vault_arch.cruces()}
    assert "vault_subgraph -> vault/grafo" in claves
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "vault_subgraph.py"), "--help"],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0 and "--seeds" in r.stdout, r.stderr[-300:]


def test_un_cruce_fuera_de_puerto_de_un_dueno_se_mide_con_su_alias(tmp_path, monkeypatch):
    """`cruces_fuera_de_puerto` buscaba el contexto del módulo por `ruta.stem`:
    un dueño migrado (`vault/ciclo_de_vida/sanacion.py`) no está en el mapa con
    ese nombre y sus cruces dejaban de medirse. Lo destapó el lote H, al dar por
    saldado `vault_sanacion -> vault_reindex.notas_indexables` sin que nadie lo
    hubiera saldado. La clave es la del alias, como en `cruces()` (AP-44)."""
    dueno = tmp_path / "sanacion.py"
    dueno.write_text("import vault_reindex\nvault_reindex.notas_indexables\n",
                     encoding="utf-8")
    monkeypatch.setattr(vault_arch, "arboles_medidos", lambda: [dueno])
    monkeypatch.setattr(vault_arch, "alias_de_dueno",
                        lambda r: "vault_sanacion" if r == dueno else None)
    cruces = vault_arch.cruces_fuera_de_puerto()
    assert {"module": "vault_sanacion", "from_context": "ciclo_de_vida",
            "to_context": vault_arch.contexto_de("vault_reindex"),
            "symbol": "vault_reindex.notas_indexables"} in cruces, cruces


def test_las_guardas_de_ap49_leen_el_codigo_del_dueno(tmp_path, monkeypatch):
    """`usos_del_nombre_congelado` y `vinculos_congelados` (AP-49) parseaban
    `scripts/<m>.py`; tras migrar ese fichero es un alias sin código y un
    `from vault_io import VAULT_ROOT` en el dueño pasaba la puerta dura sin
    medirse. Leen el dueño con `fuente_de`, como un import (AP-44)."""
    import vault_grafo_import as gi

    dueno = tmp_path / "dueno.py"
    dueno.write_text('from vault_io import VAULT_ROOT\nX = VAULT_ROOT / "a"\n',
                     encoding="utf-8")
    monkeypatch.setattr(vault_arch, "_modulos_en_disco", lambda: ["vault_falso"])
    monkeypatch.setattr(gi, "fuente_de",
                        lambda m: dueno if m == "vault_falso" else ROOT / "scripts" / f"{m}.py")
    assert [h["module"] for h in vault_arch.usos_del_nombre_congelado()] == ["vault_falso"]
    assert [h["binding"] for h in vault_arch.vinculos_congelados()] == ["X"]

def test_el_contrato_compacto_de_una_tool_migrada_se_lee_en_el_dueno():
    """`vault_compact_contracts.introspect_tool` leía `scripts/<tool>.py` por
    ruta: tras migrar, el contrato que recibe el agente decía «alias de …» como
    descripción y ningún argumento obligatorio (medido el 2026-10-10 con
    `vault_append`, que exige `--path` y `--content`). Sigue el alias con
    `fuente_de`, como un import (AP-44)."""
    import vault_compact_contracts as cc
    import vault_grafo_import as gi

    c = cc.introspect_tool("vault_append")
    assert "alias de" not in c["description"], c["description"]
    obligatorios = {a["flag"] for a in c["required_args"]}
    assert {"--path", "--content"} <= obligatorios, obligatorios
    for alias in gi._puente():
        c = cc.introspect_tool(alias)
        assert c is None or "alias de `vault." not in c["description"], alias


def test_el_bootstrap_del_manifest_lee_los_obligatorios_en_el_dueno():
    """`vault_manifest._bootstrap_spec` introspeccionaba `scripts/<tool>.py`
    por ruta y, tras migrar, publicaba `required_args: []` para `vault_append`
    —que exige `--path` y `--content`—. Mismo arreglo que el contrato compacto."""
    import vault_manifest as vm

    tools = vm._bootstrap_spec()["tools"]
    assert {"--path", "--content"} <= set(tools["vault_append"]["required_args"])


def test_la_memoria_de_spec_lee_la_fuente_en_el_dueno():
    """`vault_spec_memory._read_source` leía el alias: la descripción, los
    argumentos y los `error_code` de una tool migrada salían del docstring del
    alias —«alias de `vault.autoria.append`»— y vacíos (medido 2026-10-10)."""
    import vault_spec_memory as sm

    fuente = sm._read_source("vault_append")
    assert "alias de `vault." not in sm._get_description(fuente)
    obligatorios, _ = sm._extract_args(fuente)
    assert obligatorios, "vault_append exige --path y --content"


def test_validar_el_spec_de_una_tool_migrada_mide_al_dueno():
    """`vault_spec_validate._read_source` leía el alias: un spec correcto que
    declara `--path` y `--content` para `vault_append` salía como drift
    —«falta en argparse»— porque el alias no tiene un solo `add_argument`."""
    import vault_spec_validate as sv

    r = sv.validate_tool("vault_append", {"required_args": ["--path", "--content"]})
    assert not [d for d in r["drifts"] if "path" in str(d) or "content" in str(d)], r


def test_el_escaner_de_carreras_mira_el_codigo_del_dueno():
    """`cli.analyzer.unsafe_artifacts` escaneaba `scripts/<tool>.py`: tras
    migrar, el alias no escribe nada y su dueño desaparecía del escáner. Medido
    el 2026-10-10: `vault_index` escribe `99_Index/search-index.json` sin lock y
    el scheduler lo daba por seguro en paralelo. Se escanea el dueño y se
    reporta con el nombre de la tool."""
    from cli import analyzer

    sin_lock = analyzer.unsafe_artifacts()
    assert "vault_index" in sin_lock.get("99_Index/search-index.json", []), sin_lock
    assert "vault_index" in analyzer.unsafe_artifacts(["vault_index"]).get(
        "99_Index/search-index.json", [])


def test_el_escaner_de_la_cli_mira_el_codigo_del_dueno():
    """`vault scan` (`analyzer.scan`) analizaba el alias de `scripts/`, que no
    tiene código: medido el 2026-10-10, cero hallazgos donde los dueños tienen
    tres —RC-01 y RC-04 en `vault_index`, PY-02 en `vault_secret_scan`—. Se
    escanea el dueño y el hallazgo lleva el nombre de la tool, que es también el
    que deciden las exenciones por nombre (`_META_FILES`) (AP-44)."""
    from cli import analyzer

    r = analyzer.scan([ROOT / "scripts" / "vault_index.py"], min_severity="low")
    codigos = {(i["file"], i["code"]) for i in r["issues"]}
    assert {("vault_index.py", "RC-01"), ("vault_index.py", "RC-04")} <= codigos, codigos
    todos = analyzer.scan(min_severity="low")["issues"]
    assert ("vault_secret_scan.py", "PY-02") in {(i["file"], i["code"]) for i in todos}


LOTE_G = [
    ("vault_mcp", "vault/meta_toolkit/mcp.py", "SCRIPTS_DIR", ""),
    ("vault_spec_catalog_check", "vault/meta_toolkit/spec_catalog_check.py",
     "FIELDS_BASELINE", "field-compat-baseline.json"),
    ("vault_test_runner", "vault/meta_toolkit/test_runner.py", "SCRIPTS_DIR", ""),
    ("vault_fuente_unica", "vault/gobernanza/fuente_unica.py", "BASELINE", "fuente-unica-baseline.json"),
    ("vault_token_counter", "vault/consulta/token_counter.py", "SCRIPTS_DIR", ""),
]


@pytest.mark.parametrize("modulo,dueno,ruta,fichero", LOTE_G)
def test_lote_g_migra_y_sus_rutas_salen_del_puente(modulo, dueno, ruta, fichero):
    """Lote G de la deuda #12 (2026-10-10). Estos cinco derivaban `SCRIPTS_DIR` o
    su baseline de `__file__`; en `vault/<ctx>/` eso apuntaría al contexto, no a
    `scripts/` (ni a `_impl/` en la wheel). Las rutas salen de
    `vault_grafo_import.DIRECTORIO`, y el alias sigue arrancando como CLI."""
    import importlib
    import subprocess

    import vault_grafo_import as gi

    assert modulo not in set(vault_arch.modulos_sin_hogar())
    m = importlib.import_module(modulo)
    assert m is importlib.import_module(dueno[:-3].replace("/", "."))
    assert gi.fuente_de(modulo) == (ROOT / dueno).resolve()
    assert getattr(m, ruta) == gi.DIRECTORIO / fichero if fichero else getattr(m, ruta) == gi.DIRECTORIO
    assert "__file__" not in (ROOT / dueno).read_text(encoding="utf-8").split("def ", 1)[0]
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / f"{modulo}.py"), "--help"],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0 and "usage" in r.stdout.lower(), r.stderr[-300:]
