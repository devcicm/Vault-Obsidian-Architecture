"""La puerta única: el registro manda sobre el checklist, y no reimplementa nada.

`vault_gate` nace de un fallo concreto: las puertas de cierre vivían en una lista
en prosa dentro de `AGENTS.md`, y una lista en prosa no sabe cuántos elementos
tiene. Se hablaba de "las siete puertas" mientras el checklist tenía ocho ítems y
la práctica corría seis.

Estos tests vigilan las dos propiedades que hacen que la tool sirva para algo:

1. **El registro es canónico y el doc se comprueba contra él.** Si fuera al revés
   —el doc manda, el código lo sigue— habría dos sitios donde se decide qué
   puertas hay, que es AP-50 cometida en la versión que la estrena.
2. **Agrega, no mide.** Cada puerta corre como subproceso con su propio exit code.
   Una `vault_gate` que mirase los datos por su cuenta sería una segunda fuente de
   verdad sobre el estado del repo (AP-05) midiendo con su criterio en vez del de
   la puerta (AP-44).
"""

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_gate  # noqa: E402
import vault_mcp_catalog  # noqa: E402

import vault_grafo_import as gi  # noqa: E402


def test_toda_puerta_del_registro_esta_en_el_checklist():
    """La comprobación que hace `--check-doc`, corrida como test.

    Añadir una puerta al registro sin añadirla al checklist es publicar un guard
    que nadie ejecuta — AP-42 aplicada a las propias puertas.
    """
    r = vault_gate.check_doc()
    assert r["ok"], f"puertas fuera del checklist: {r['gates_missing_from_checklist']}"
    assert r["gates_total"] == len(vault_gate.PUERTAS)


def test_el_checklist_no_puede_anadir_puertas_por_su_cuenta():
    """La dirección de la dependencia, explícita.

    Si `AGENTS.md` cita un script de puerta que el registro no conoce, el registro
    ha dejado de ser canónico. Se comprueba sobre los scripts que el propio
    checklist presenta como puertas de cierre (`--check --strict` / `--check-*`).
    """
    texto = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8", errors="replace")
    checklist = texto.split("## Antes de cerrar un cambio", 1)[1]

    del_registro = {p["cmd"][0] for p in vault_gate.PUERTAS}
    citados = {
        linea.split("scripts/", 1)[1].split()[0]
        for linea in checklist.splitlines()
        if "python scripts/" in linea and ("--check" in linea or "--strict" in linea)
    }
    huerfanos = citados - del_registro - {"vault_gate.py"}
    assert not huerfanos, (
        f"el checklist cita puertas que el registro no conoce: {sorted(huerfanos)}. "
        "Se añaden a PUERTAS, no se dejan solo en el doc."
    )


def test_cada_puerta_apunta_a_un_script_que_existe():
    for puerta in vault_gate.PUERTAS:
        script = REPO_ROOT / "scripts" / puerta["cmd"][0]
        assert script.exists(), f"puerta {puerta['id']} apunta a {script}, que no existe"


def test_cada_puerta_declara_que_mide():
    """`mide` es lo que se lee cuando algo se pone en rojo. Vacío no vale."""
    for puerta in vault_gate.PUERTAS:
        assert puerta["mide"].strip(), f"la puerta {puerta['id']} no declara qué mide"
        assert "fix" in puerta, f"la puerta {puerta['id']} no declara su fix (None es válido)"


def test_los_ids_son_unicos():
    ids = [p["id"] for p in vault_gate.PUERTAS]
    assert len(ids) == len(set(ids)), f"ids repetidos en PUERTAS: {ids}"


def test_no_reimplementa_ninguna_comprobacion():
    """La propiedad estructural: `vault_gate` no importa las tools que corre.

    Se mide por AST y no por subcadena porque la docstring nombra varias de esas
    tools en prosa — medir el texto crudo daría un falso positivo, que es
    exactamente el AP-44 que este repo ya se comió una vez.
    """
    arbol = ast.parse(gi.codigo_de(REPO_ROOT / "scripts" / "vault_gate.py").read_text(encoding="utf-8"))
    importados = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            importados |= {a.name for a in nodo.names}
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            importados.add(nodo.module)

    de_puertas = {p["cmd"][0][:-3] for p in vault_gate.PUERTAS}
    assert not (importados & de_puertas), (
        f"vault_gate importa {sorted(importados & de_puertas)}: correría la "
        "comprobación en su propio proceso en vez de delegarla, y su veredicto "
        "dejaría de ser el de la puerta."
    )


def test_esta_en_el_catalogo():
    """Una tool fuera del catálogo es superficie que el MCP no expone (AP-42)."""
    assert "vault_gate" in vault_mcp_catalog.TOOLS_CATALOG
    assert "vault_gate" in vault_mcp_catalog.GROUPS["Normas"]


@pytest.mark.parametrize("flag", ["--list", "--check-doc"])
def test_las_acciones_de_lectura_emiten_json_y_no_escriben(flag):
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "vault_gate.py"), flag],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO_ROOT), timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-800:]
    envelope = json.loads(proc.stdout.strip().splitlines()[-1])
    assert envelope["tool"] == "vault_gate"
    assert envelope["gates_total"] == len(vault_gate.PUERTAS)


def test_el_listado_dice_como_arreglar_lo_que_se_arregla_solo():
    """Distinguir el artefacto derivado del defecto real es la mitad del valor.

    Un conteo desincronizado se regenera con `--fix`; un contrato roto no. Sin esa
    distinción, cada rojo cuesta lo mismo averiguarlo.
    """
    por_id = {g["gate"]: g for g in vault_gate.listar()["gates"]}
    assert por_id["conteos"]["fix"], "los conteos se regeneran: el fix debe estar dicho"
    assert por_id["catalogo"]["fix"], "el catálogo se sincroniza: el fix debe estar dicho"
    assert por_id["contratos"]["fix"] is None, (
        "los contratos exigen decisión: anunciar un fix automático sería mentir"
    )


def test_el_envelope_recuerda_que_no_sustituye_a_la_suite():
    """La confusión previsible, cerrada en el propio envelope y no en el README.

    Quien corre la puerta única y la ve verde tiene todos los incentivos para no
    esperar diez minutos de suite. Que el recordatorio viaje con el resultado es
    la diferencia entre una convención y algo que se lee.
    """
    import inspect

    fuente = inspect.getsource(vault_gate.correr_todas)
    assert '"hint"' in fuente and "pytest" in fuente, (
        "correr_todas debe emitir un hint que recuerde que la suite sigue siendo "
        "obligatoria; sin él, el recordatorio vive solo en el README y no se lee"
    )


# --- el checklist derivado (v40.16) ------------------------------------------

def test_el_bloque_del_checklist_sale_del_registro():
    """Cada puerta aparece con su comando y con lo que mide, sin prosa a mano."""
    bloque = vault_gate.checklist()
    for p in vault_gate.PUERTAS:
        assert "python scripts/" + " ".join(p["cmd"]) in bloque
        assert p["mide"] in bloque
        if p["fix"]:
            assert p["fix"] in bloque


def test_editar_a_mano_el_bloque_lo_pone_en_rojo(tmp_path, monkeypatch):
    """El defecto que `--check-doc` no veía: el script sigue citado y el texto miente.

    Comprobar solo la presencia del nombre dejaba pasar cualquier deriva del
    texto — que es exactamente como los dieciséis párrafos se despegaron del
    registro sin que nadie lo notara.
    """
    doc = tmp_path / "AGENTS.md"
    manipulado = vault_gate.checklist().replace(
        vault_gate.PUERTAS[0]["mide"], "mide otra cosa"
    )
    doc.write_text(manipulado, encoding="utf-8")
    monkeypatch.setattr(vault_gate, "REPO_ROOT", tmp_path)

    r = vault_gate.check_doc()
    assert r["ok"] is False
    assert r["checklist_drift"] == "bloque_desactualizado"
    assert r["gates_missing_from_checklist"] == [], (
        "todas las puertas siguen citadas: el fallo es la deriva del texto"
    )


def test_fix_doc_conserva_los_finales_de_linea(tmp_path, monkeypatch):
    """CRLF: reescribir el bloque no puede producir un diff de fichero entero."""
    doc = tmp_path / "AGENTS.md"
    cuerpo = ("# Doc\n\n" + vault_gate.MARCA_INICIO + "\nviejo\n"
              + vault_gate.MARCA_FIN + "\n\nfin\n")
    doc.write_bytes(cuerpo.replace("\n", "\r\n").encode("utf-8"))
    monkeypatch.setattr(vault_gate, "REPO_ROOT", tmp_path)

    assert vault_gate.fix_doc()["changed"] is True
    crudo = doc.read_bytes().decode("utf-8")
    assert "\r\n" in crudo and "\n" not in crudo.replace("\r\n", "")
    assert vault_gate.PUERTAS[0]["mide"] in crudo


def test_sin_marcas_el_fix_no_inventa_donde_escribir(tmp_path, monkeypatch):
    doc = tmp_path / "AGENTS.md"
    doc.write_text("# Doc sin marcas\n", encoding="utf-8")
    monkeypatch.setattr(vault_gate, "REPO_ROOT", tmp_path)

    r = vault_gate.fix_doc()
    assert r["ok"] is False and r["error_code"] == "INVALID_INPUT"


def test_la_corrida_no_hereda_el_limite_por_defecto_de_wrap_main():
    """`vault_gate --strict` sin VAULT_TOOL_TIMEOUT moría a los 60 s (TOOL_TIMEOUT).

    El límite de la corrida tiene que cubrir todas las puertas en serie, cada una
    con su propio límite, y el `__main__` tiene que pasárselo a `wrap_main`.
    """
    import vault_errors

    assert vault_gate.limite_total() >= len(vault_gate.PUERTAS) * vault_gate.LIMITE_POR_PUERTA
    assert vault_gate.limite_total() > vault_errors.TOOL_TIMEOUT_SECONDS

    arbol = ast.parse(gi.codigo_de(REPO_ROOT / "scripts" / "vault_gate.py").read_text(encoding="utf-8"))
    llamadas = [n for n in ast.walk(arbol) if isinstance(n, ast.Call)
                and getattr(n.func, "id", None) == "wrap_main"]
    assert llamadas, "vault_gate ya no se envuelve con wrap_main"
    for c in llamadas:
        nombres = {k.arg: k.value for k in c.keywords}
        assert "timeout" in nombres, "wrap_main sin timeout hereda el límite por defecto"
        assert ast.unparse(nombres["timeout"]) == "limite_total()"


# --- el registro de razones (v41.11) -----------------------------------------

def test_las_razones_salen_del_registro_y_del_docstring():
    """Cada puerta con su comando, lo que mide y el porqué de su tool."""
    doc = vault_gate.razones()
    for p in vault_gate.PUERTAS:
        assert f"## `{p['id']}`" in doc
        assert p["mide"] in doc
        r = vault_gate.razon(p)
        assert r["resumen"] and r["resumen"] in doc, p["id"]


def test_un_alias_da_la_razon_de_su_dueno():
    """ADR-0002: el docstring del alias solo dice dónde vive el dueño."""
    campos = next(p for p in vault_gate.PUERTAS if p["cmd"][0] == "vault_spec_catalog_check.py")
    assert "alias de" not in vault_gate.razon(campos)["resumen"]


def test_las_normas_citadas_existen_como_paquete():
    for p in vault_gate.PUERTAS:
        for n in vault_gate.razon(p)["normas"]:
            assert (vault_gate.REPO_ROOT / "normas" / n / "porque.md").exists(), n
    noop = next(p for p in vault_gate.PUERTAS if p["cmd"][0] == "vault_noop_audit.py")
    assert "AP-37" in vault_gate.razon(noop)["normas"]


def test_editar_a_mano_las_razones_las_pone_en_rojo(tmp_path, monkeypatch):
    (tmp_path / "AGENTS.md").write_text(vault_gate.checklist(), encoding="utf-8")
    destino = tmp_path / vault_gate.RAZONES
    destino.parent.mkdir(parents=True)
    destino.write_text(vault_gate.razones().replace("**Mide:**", "**Mide (a mano):**"),
                       encoding="utf-8")
    monkeypatch.setattr(vault_gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(vault_gate, "_docstring", lambda s: "Resumen.\n\nPorque sí.")

    r = vault_gate.check_doc()
    assert r["ok"] is False and r["reasons_drift"] == "razones_desactualizadas"
    assert r["checklist_drift"] is None

    assert vault_gate.fix_doc()["reasons_changed"] is True
    assert vault_gate.check_doc()["ok"] is True


def test_el_registro_publicado_esta_al_dia():
    r = vault_gate.check_doc()
    assert r["reasons_drift"] is None, "python scripts/vault_gate.py --fix-doc"


# ── Preparación del entorno (v41.25 H-1) ──────────────────────────────────


class _Proc:
    def __init__(self, rc, out=""):
        self.returncode, self.stdout, self.stderr = rc, out, out


def test_preparar_entorno_no_hace_nada_si_los_derivados_existen(monkeypatch):
    llamadas = []

    def falso(argv, **kw):
        llamadas.append(argv)
        return _Proc(0)

    monkeypatch.setattr(vault_gate.subprocess, "run", falso)
    r = vault_gate.preparar_entorno()
    assert r == {"necesaria": False, "ok": True}
    assert len(llamadas) == 1  # solo la medida, ningún bootstrap


def test_preparar_entorno_materializa_el_sandbox_cuando_faltan(monkeypatch):
    llamadas = []

    def falso(argv, **kw):
        llamadas.append(argv)
        return _Proc(1 if len(llamadas) == 1 else 0)

    monkeypatch.setattr(vault_gate.subprocess, "run", falso)
    r = vault_gate.preparar_entorno()
    assert r["necesaria"] and r["ok"]
    assert llamadas[1] == vault_gate.BOOTSTRAP_SANDBOX
    assert "--bootstrap" in llamadas[1]


def test_preparar_entorno_informa_si_el_bootstrap_falla(monkeypatch):
    estados = iter([_Proc(1), _Proc(2, "boom")])
    monkeypatch.setattr(vault_gate.subprocess, "run", lambda *a, **k: next(estados))
    r = vault_gate.preparar_entorno()
    assert r["necesaria"] and not r["ok"] and r["returncode"] == 2
    assert "boom" in r["stderr"]


def test_el_envelope_de_las_puertas_publica_la_preparacion(monkeypatch):
    monkeypatch.setattr(vault_gate, "preparar_entorno", lambda: {"necesaria": False, "ok": True})
    monkeypatch.setattr(vault_gate, "PUERTAS", [])
    assert vault_gate.correr_todas()["preparacion"] == {"necesaria": False, "ok": True}
