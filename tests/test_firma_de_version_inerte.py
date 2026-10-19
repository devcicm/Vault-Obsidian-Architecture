"""La firma de versión es metadato, no interruptor.

Promesa medida aquí: un vault sellado en cualquier versión conocida —la
vigente, una menor atrás, una mayor atrás— se comporta igual ante las tools,
y `--check` mira el historial de versiones sin autorizar escrituras.

Medido 2026-10-18 al preguntarse si el sello afecta a la funcionalidad:

- Ningún lector de `standard-version.json` cambia su comportamiento por
  `applied_version` (el servidor MCP cae a "unknown", `vault_compact_contracts`
  cae al perfil "full"), pero nada lo garantizaba con un test.
- `vault_manifest` llevaba meses leyendo la clave equivocada (`version` en vez
  de `applied_version`) y diciendo "unknown" en silencio.
- El epilog de `vault_standard_upgrade --help` decía a mano "v19 a v34" cuando
  la vigente era v41.11: el historial existía (`VERSION_ORDER`) pero no había
  forma de mirlo desde fuera sin migrar.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
REPO_ROOT = TESTS.parent
for _p in (str(TESTS), str(REPO_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import vault_compact_contracts as vcc  # noqa: E402
import vault_io  # noqa: E402
import vault_manifest  # noqa: E402
import vault_standard_upgrade as vsu  # noqa: E402

VIGENTE = vsu.CURRENT_VERSION
#: Una menor atrás de la vigente: mismo mayor, sello pendiente, cero migraciones.
MENOR_ATRAS = VIGENTE.split(".", 1)[0]
#: Una mayor atrás del registro: migración pendiente de verdad.
MAYOR_ATRAS = vsu.VERSION_ORDER[-2]


def _raiz_sellada(tmp_path: Path, version: str, nombre: str) -> Path:
    """Un vault recién creado, re-sellado a `version` cuando no es la vigente.

    `vault_init` estampa siempre la vigente — comprobado contra un root
    temporal el 2026-10-18 —, así que el sello viejo se escribe DESPUÉS del
    init, sobre un vault completo: lo que se mide es el sello, no la falta
    de carpetas.
    """
    raiz = tmp_path / nombre / "vault-sandbox"
    # La raíz tiene que EXISTIR antes de init: con VAULT_STRICT_ROOT=1 el
    # detector se niega a adivinar sobre un path que no está en disco.
    raiz.mkdir(parents=True)
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "vault_init.py"), "--no-audit"],
        env={**os.environ, "VAULT_ROOT": str(raiz), "VAULT_STRICT_ROOT": "1"},
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300, check=True,
    )
    estado = raiz / "00_System" / "standard-version.json"
    if version != VIGENTE:
        datos = json.loads(estado.read_text(encoding="utf-8"))
        datos["applied_version"] = version
        estado.write_text(json.dumps(datos, indent=2) + "\n", encoding="utf-8")
    return raiz


def _estado_de(raiz: Path) -> Path:
    return raiz / "00_System" / "standard-version.json"


def _correr(raiz: Path, *flags):
    env = {**os.environ, "VAULT_ROOT": str(raiz), "VAULT_STRICT_ROOT": "1"}
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "vault_standard_upgrade.py"), *flags],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO_ROOT), timeout=300, env=env,
    )
    return json.loads(proc.stdout)


# --- la firma no cambia la funcionalidad -------------------------------------

@pytest.mark.skipif(shutil.which("node") is None, reason="necesita Node en el PATH")
def test_escribir_leer_buscar_igual_con_cualquier_sello(tmp_path):
    from test_mcp_runner import SesionMCP

    marca = "FIRMA-INERTE"
    cuerpo = "\n".join(
        f"El dato {marca} vive en la línea {i} de la nota de la firma inerte."
        for i in range(4))
    comportamientos = {}
    for nombre, version in (("vigente", VIGENTE), ("menor_atras", MENOR_ATRAS)):
        raiz = _raiz_sellada(tmp_path, version, nombre)
        antes = _estado_de(raiz).read_bytes()
        sesion = SesionMCP(raiz)
        try:
            def env(tool, args):
                return json.loads(sesion.llamar(tool, args)["result"]["content"][0]["text"])
            alta = env("vault_write", {"folder": "07_Knowledge", "title": "Firma inerte",
                                       "content": cuerpo, "tags": ["banco"],
                                       "agent": "firma-test"})
            assert alta.get("ok") is True, alta
            lectura = env("vault_read", {"path": alta["path"]})
            busca = env("vault_search", {"query": marca})
            comportamientos[nombre] = {
                "path": alta["path"],
                "leido": lectura.get("ok") is True and marca in (lectura.get("body") or ""),
                "hallada": any(r.get("path") == alta["path"]
                               for r in busca.get("results", [])),
            }
        finally:
            sesion.cerrar()
        # Trabajar no toca la firma: ni la repara ni la actualiza.
        assert _estado_de(raiz).read_bytes() == antes, (
            f"el sello {version} cambió al usar las tools"
        )
    assert comportamientos["vigente"] == comportamientos["menor_atras"], (
        f"la funcionalidad depende del sello: {comportamientos}"
    )


def test_el_historial_se_mira_desde_un_sello_viejo_sin_migrar(tmp_path):
    """Desde una mayor atrás, `--check` expone el catálogo completo de
    versiones —y sigue sin escribir: mirar no autoriza."""
    raiz = _raiz_sellada(tmp_path, MAYOR_ATRAS, "mayor_atras")
    antes = _estado_de(raiz).read_bytes()
    env = _correr(raiz, "--check")
    assert env["ok"] is True
    # El historial es de MAYORES; la vigente exacta viaja en current_standard.
    assert VIGENTE.split(".", 1)[0] in env["known_versions"], env.get("known_versions")
    assert MAYOR_ATRAS in env["known_versions"]
    assert env["current_standard"] == VIGENTE
    assert env["applied_version"] == MAYOR_ATRAS
    # Una mayor atrás tiene migración pendiente de verdad: se avisa, no se aplica.
    assert env["pending_count"] >= 1
    assert _estado_de(raiz).read_bytes() == antes, "--check escribió sobre el sello"


def test_el_historial_tambien_se_mira_desde_la_vigente(tmp_path):
    raiz = _raiz_sellada(tmp_path, VIGENTE, "al_dia")
    env = _correr(raiz, "--check")
    assert env["ok"] is True
    assert env["applied_version"] == VIGENTE
    assert env["stamp_pending"] is False
    assert VIGENTE.split(".", 1)[0] in env["known_versions"]
    assert MAYOR_ATRAS in env["known_versions"]


# --- los lectores del sello, uno a uno ---------------------------------------

def test_manifest_lee_la_version_sellada(tmp_path):
    """`vault_manifest` mostraba "unknown" siempre: leía la clave `version`
    cuando el fichero sella `applied_version` (defecto medido 2026-10-18)."""
    raiz = _raiz_sellada(tmp_path, VIGENTE, "manifest")
    vault_io.set_vault_root(str(raiz))
    assert vault_manifest._read_version() == VIGENTE
    # Formato anterior: clave `version` numérica — no-derogación, se acepta.
    _estado_de(raiz).write_text(json.dumps({"version": 40}), encoding="utf-8")
    assert vault_manifest._read_version() == "v40"


def test_el_perfil_por_defecto_es_ajeno_al_sello(tmp_path):
    """Un sello viejo (o sin clave de perfil) no cambia qué tools se generan:
    el perfil cae a "full", igual que con el sello vigente."""
    raiz = _raiz_sellada(tmp_path, MENOR_ATRAS, "perfil")
    vault_io.set_vault_root(str(raiz))
    assert vcc._read_current_profile() == "full"
    # Sin fichero de versión tampoco hay interruptor: mismo perfil.
    _estado_de(raiz).unlink()
    assert vcc._read_current_profile() == "full"
