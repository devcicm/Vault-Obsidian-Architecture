"""v40.30 — lo que solo se rompe cuando el toolkit no está en su propio repo.

Los tres defectos que cubre este fichero pasaban en verde aquí y solo aquí: la
suite completa corre **dentro** del repo del estándar, donde la autodetección
acierta, donde los vaults de al lado son los consumidores conocidos y donde la
locale de la máquina resulta coincidir lo bastante con UTF-8 para que nadie
mirase. Se destaparon copiando `scripts vault cli mcp` fuera del repo y
ejecutando contra un vault vacío.

Es el mismo argumento de la regla 7 aplicado al propio programa: una medida
tomada en el entorno que la generó comparte sus supuestos y no puede exhibir el
fallo. Aquí no se puede reproducir la instalación externa dentro de un test sin
volverlo lento y frágil, así que cada test ataca **la decisión** que falló, no
el escenario: la raíz dudosa, el default de escaneo y el criterio de decodificar.
"""

from __future__ import annotations

import ast
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import vault_entorno  # noqa: E402
import vault_io  # noqa: E402
import vault_subproceso  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent


# --- Fallo 1: escribir sobre una raíz que nadie identificó ---------------------


def test_la_bandera_permisiva_esta_declarada():
    """Una variable de entorno que nadie declaró es la que este registro impide."""
    assert "VAULT_PERMISSIVE_ROOT" in vault_entorno.VARIABLES
    var = vault_entorno.VARIABLES["VAULT_PERMISSIVE_ROOT"]
    assert var.default is False
    assert var.contexto == "kernel"


def test_escribir_con_raiz_dudosa_se_rechaza(tmp_path, monkeypatch):
    """`repo_root_fallback` significa «no encontré nada y estoy suponiendo».

    Instalado fuera del repo, ese fallback devuelve el directorio del propio
    programa: la escritura sembraba artefactos de vault dentro del toolkit.
    """
    monkeypatch.setattr(vault_io, "vault_root_is_confident", lambda: False)
    monkeypatch.setattr(vault_io, "vault_root_origin", lambda: "repo_root_fallback")
    monkeypatch.setattr(vault_io, "get_vault_root", lambda: tmp_path)
    monkeypatch.delenv("VAULT_PERMISSIVE_ROOT", raising=False)
    with pytest.raises(PermissionError) as exc:
        vault_io.atomic_write_text(tmp_path / "nota.md", "x")
    assert "repo_root_fallback" in str(exc.value)
    assert "VAULT_ROOT" in str(exc.value), "el error debe decir cómo salir de él"


def test_leer_con_raiz_dudosa_sigue_permitido(tmp_path, monkeypatch):
    """El daño empieza al escribir, no al mirar.

    Rechazar también la lectura habría roto `vault doctor` y toda la superficie
    de diagnóstico justo en el caso en que hace falta diagnosticar.
    """
    monkeypatch.setattr(vault_io, "vault_root_is_confident", lambda: False)
    monkeypatch.setattr(vault_io, "get_vault_root", lambda: tmp_path)
    destino = tmp_path / "nota.md"
    destino.write_text("contenido", encoding="utf-8")
    assert destino.read_text(encoding="utf-8") == "contenido"


def test_la_bandera_permisiva_devuelve_el_comportamiento_anterior(tmp_path, monkeypatch):
    """No-derogación: el modo viejo sigue disponible, ahora con nombre."""
    monkeypatch.setattr(vault_io, "vault_root_is_confident", lambda: False)
    monkeypatch.setattr(vault_io, "vault_root_origin", lambda: "repo_root_fallback")
    monkeypatch.setattr(vault_io, "get_vault_root", lambda: tmp_path)
    monkeypatch.setenv("VAULT_PERMISSIVE_ROOT", "1")
    vault_io.atomic_write_text(tmp_path / "nota.md", "x")
    assert (tmp_path / "nota.md").read_text(encoding="utf-8") == "x"


def test_una_raiz_de_confianza_no_se_toca(tmp_path, monkeypatch):
    """El guard no puede cobrarse el caso normal, que es el 100% del uso real."""
    monkeypatch.setattr(vault_io, "vault_root_is_confident", lambda: True)
    monkeypatch.setattr(vault_io, "get_vault_root", lambda: tmp_path)
    vault_io.atomic_write_text(tmp_path / "nota.md", "x")
    assert (tmp_path / "nota.md").exists()


# --- Fallo 2: el servidor MCP inventariando el disco del usuario ---------------

MJS = (REPO / "mcp" / "nodejs" / "vault-mcp-server.mjs").read_text(
    encoding="utf-8", errors="replace"
)


def test_el_barrido_automatico_esta_condicionado_a_estar_en_el_repo():
    """`join(REPO_ROOT, "..")` es el repo aquí y una carpeta del usuario fuera.

    Medido en v40.30: instalado fuera, el servidor registraba y exponía al
    agente tres vaults ajenos **con `VAULT_ROOT` explícito puesto**. Un
    inventario del disco ajeno no puede ser un default.
    """
    assert "EN_REPO_DEL_ESTANDAR" in MJS
    assert 'existsSync(join(REPO_ROOT, "vault-obsidian-architecture.md"))' in MJS


def test_el_marcador_del_mjs_es_el_mismo_que_usa_python():
    """Las dos mitades del toolkit no pueden discrepar sobre «estar en el repo».

    Python decide `spec_repo_sandbox` con ese mismo fichero. Dos criterios para
    la misma pregunta es AP-57 cruzando una frontera de lenguaje.
    """
    raiz = (REPO / "scripts" / "vault_raiz.py").read_text(encoding="utf-8")
    assert "vault-obsidian-architecture.md" in raiz


def test_fuera_del_repo_el_default_es_no_escanear_nada():
    """La rama falsa del ternario tiene que ser la lista vacía, no otra ruta."""
    trozo = MJS.split("EN_REPO_DEL_ESTANDAR", 2)[-1]
    trozo = trozo[: trozo.index(";")]
    assert "[]" in trozo, "sin repo, se escanea lo que te digan y nada más"


def test_la_variable_de_escaneo_sigue_declarada():
    """La costura explícita no desaparece: se escanea lo que `VAULT_SCAN_ROOTS` diga."""
    assert "VAULT_SCAN_ROOTS" in vault_entorno.VARIABLES
    assert "process.env.VAULT_SCAN_ROOTS" in MJS


# --- Fallo 3: leer al hijo con la locale de la máquina ------------------------


def test_el_dueno_fija_la_codificacion():
    assert vault_subproceso.CODIFICACION == "utf-8"
    assert vault_subproceso.ERRORES == "replace"


def test_ningun_sitio_decodifica_con_la_locale():
    """El guard de la norma. Eran 23 en 13 ficheros; ahora la lista está vacía.

    `text=True` sin `encoding` decodifica con `locale.getpreferredencoding()`,
    la del sistema donde corre, no la del proceso que escribió. En cp1252 el
    acento se corrompe en silencio y se escribe corrompido al vault; en cp932 o
    cp949 `subprocess` levanta `UnicodeDecodeError` y la tool cae entera.
    """
    assert vault_subproceso.sitios_sin_codificacion() == []


def test_el_detector_ve_un_sitio_nuevo(tmp_path):
    """Un guard que no falla ante la violación no es un guard."""
    (tmp_path / "reincidente.py").write_text(
        "import subprocess\nsubprocess.run(['x'], text=True)\n", encoding="utf-8"
    )
    hallado = vault_subproceso.sitios_sin_codificacion([str(tmp_path)])
    assert len(hallado) == 1 and hallado[0].endswith("reincidente.py:2")


def test_el_detector_acepta_una_codificacion_explicita(tmp_path):
    """Poner `encoding` a mano sigue siendo correcto: la norma cubre el olvido."""
    (tmp_path / "ok.py").write_text(
        "import subprocess\nsubprocess.run(['x'], text=True, encoding='cp437')\n",
        encoding="utf-8",
    )
    assert vault_subproceso.sitios_sin_codificacion([str(tmp_path)]) == []


def test_ejecutar_lee_utf8_aunque_el_llamador_pida_texto():
    """`text=True` heredado del llamador no puede reabrir el agujero."""
    hijo = vault_subproceso.ejecutar(
        [sys.executable, "-c", "print('el \\u00edndice dej\\u00f3 de reflejar')"],
        capture_output=True,
        text=True,
        env={"PYTHONIOENCODING": "utf-8", "PATH": ""},
    )
    assert "el índice dejó de reflejar" in hijo.stdout


def test_el_llamador_puede_imponer_otra_codificacion(tmp_path):
    """La norma cubre a los hijos de este toolkit, no a cualquier binario."""
    hijo = vault_subproceso.ejecutar(
        [sys.executable, "-c", "print('ok')"], capture_output=True, encoding="latin-1"
    )
    assert hijo.stdout.strip() == "ok"


# --- Fallo 4: las cifras a mano del otro lado de la frontera de lenguaje ------


def test_el_mjs_no_escribe_la_version():
    """Decía `v39.3 (SDD)` con el estándar en v40.29, en la cara del agente."""
    assert 'const VERSION = "v39' not in MJS
    assert "data.standard_version" in MJS, "la versión llega por la pasarela"


def test_el_catalogo_publica_la_version_del_estandar():
    import json

    import vault_version

    catalogo = json.loads(
        (REPO / "mcp" / "nodejs" / "tools-catalog.json").read_text(encoding="utf-8")
    )
    assert catalogo["standard_version"] == vault_version.CURRENT_VERSION


def test_la_version_se_lee_al_responder_y_no_al_cargar():
    """AP-49: `SERVER_INFO` se evalúa al importar y el catálogo carga en `main()`.

    Copiar el número en el objeto lo habría congelado en el respaldo justo
    cuando el catálogo sí cargó — el arreglo funcionando al revés.
    """
    assert "get version() { return VERSION; }" in MJS


def test_el_mjs_no_escribe_cuantas_tools_expone():
    """«las 71 herramientas» cuando son 107. La cuenta la da el catálogo.

    Se comprueba que no lo **afirme**, no que el número no aparezca: el
    comentario que explica el arreglo cita la cifra vieja, y tiene que poder.
    """
    assert "expone las 71" not in MJS
    assert "Object.keys(TOOLS_CATALOG).length" in MJS


def test_el_check_del_catalogo_ve_una_version_desfasada(tmp_path, monkeypatch):
    """Un guard que no falla ante la divergencia no vigila nada."""
    import json

    import vault_mcp_catalog

    origen = REPO / "mcp" / "nodejs" / "tools-catalog.json"
    datos = json.loads(origen.read_text(encoding="utf-8"))
    datos["standard_version"] = "v1.0"
    destino = tmp_path / "tools-catalog.json"
    destino.write_text(json.dumps(datos), encoding="utf-8")
    r = vault_mcp_catalog.check_sync(str(destino))
    assert r["ok"] is False
    assert any("standard_version" in d for d in r["diffs"])


def test_el_dueno_no_importa_ningun_vault():
    """Módulo hoja (AP-62): si algún día necesita el toolkit, pierde el sitio."""
    arbol = ast.parse((REPO / "scripts" / "vault_subproceso.py").read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module:
            assert not nodo.module.startswith("vault"), nodo.module
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                assert not alias.name.startswith("vault"), alias.name
