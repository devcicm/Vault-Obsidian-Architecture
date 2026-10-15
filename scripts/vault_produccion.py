#!/usr/bin/env python3
"""vault_produccion — «¿puede usar esto otra persona, y con qué fiabilidad?»

## De dónde sale esta tool

De una pregunta del usuario, hecha con v40.30 recién cerrada y las 20 puertas en
verde: *«¿entonces ya puede ser usado por otras personas, aparte de mí, y con
resultados óptimos, decentes y fiables?»*

La respuesta honesta obligó a medir cosas que ninguna puerta miraba, y apareció
un defecto en menos de diez minutos: `pyproject.toml` prometía Python **>=3.9** y
la CI probaba **solo 3.11**. Seis sitios rompían en 3.9, y no al llamarse sino al
**importar** —`ast.AST | None` se evalúa al definir la función—, dos de ellos en
`vault_grafo_import` y `vault_norms_catalog`, que importa medio repo. Quien
instalara en 3.9 o 3.10 no habría arrancado nada.

Nada de eso estaba roto *aquí*. Ese es justo el punto.

## Por qué es un registro y no un párrafo en un doc

Porque una pregunta que hay que acordarse de hacer no se hace. Las 20 puertas
existentes miden **el repo contra sí mismo**: que el catálogo no diverja del
JSON, que la baseline no crezca, que el plano no envejezca. Todas correctas, y
todas ciegas a la misma cosa — el consumidor no está en la sala. Es AP-44 subido
un nivel: no «verificar con el criterio del consumidor» dentro de una tool, sino
**verificar que existe alguien que ejerza lo que el producto promete**.

El patrón que comparten los ocho defectos de v40.30 es uno solo:

    alcance declarado  >  alcance ejercido   ⇒   el hueco devuelve CERO,
                                                 y un cero se lee como limpio.

`cli/` declarado en `ARBOLES_MEDIDOS` sin contexto que lo clasificara. `vault/`
fuera del grafo de ciclos. El servidor MCP escaneando un disco que fuera del repo
no es el suyo. `>=3.9` sin nadie que ejecutase 3.9. Cada una devolvía un cero
tranquilizador.

## Qué mide, exactamente

Cada entrada de `PREGUNTAS` declara una **promesa al consumidor** y **quién la
ejerce**. La puerta falla cuando una promesa marcada como cubierta apunta a un
ejecutor que no existe: un fichero borrado, una versión que se cayó de la matriz
de CI, un comando que ya no está. No comprueba que el ejecutor *pase* —eso es
trabajo de la CI y de la suite—: comprueba que **exista**, que es la condición
que faltaba y que nadie miraba.

## Qué NO demuestra el verde

Verde aquí significa que toda promesa listada tiene ejecutor, y que las que no lo
tienen lo dicen con el motivo escrito. No significa que la lista esté completa.
Una promesa que nadie escribió en `PREGUNTAS` sigue sin medirse, y esta tool no
puede saber qué prometiste en un README que no lee. Por eso el registro se amplía
cuando alguien tropieza, y por eso las descubiertas se publican en vez de
callarse: una promesa que declara su hueco es más barata que una que lo esconde.

    python scripts/vault_produccion.py --check --strict
    python scripts/vault_produccion.py --guia     # regenera docs/GUIA-DE-PRODUCCION.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List

import yaml

sys.path.insert(0, str(Path(__file__).parent))

from vault_errors import emit_error, wrap_main

RAIZ = Path(__file__).resolve().parent.parent
GUIA = RAIZ / "docs" / "GUIA-DE-PRODUCCION.md"

#: Estados posibles de una promesa. `descubierta` NO es un fallo: es la forma
#: honesta de declarar un hueco, y el repo ya decidió en v40.16 que declararse
#: no puede salir más caro que callarse. Lo que rompe la puerta es una promesa
#: `cubierta` cuyo ejecutor no existe — o sea, una mentira comprobable.
ESTADOS = ("cubierta", "descubierta")


def _existe(rel: str) -> bool:
    return (RAIZ / rel).exists()


def _versiones_que_ejecutan_la_suite(ci: Path) -> set:
    """Versiones de Python de la matriz de los jobs que ejecutan pytest.

    Se lee el YAML como YAML (AP-44): buscar cualquier ``'x.y'`` en el texto
    contaba también versiones de jobs que no corren la suite, de comentarios o
    de `setup-python` fijo, y un piso «probado» en el job de lint pasaba.
    """
    datos = yaml.safe_load(ci.read_text(encoding="utf-8")) or {}
    versiones = set()
    for job in (datos.get("jobs") or {}).values():
        pasos = job.get("steps") or []
        if not any("pytest" in str(paso.get("run", "")) for paso in pasos):
            continue
        matriz = (job.get("strategy") or {}).get("matrix") or {}
        for v in matriz.get("python-version") or []:
            versiones.add(tuple(int(x) for x in str(v).split(".")[:2]))
    return versiones


def _ci_prueba_el_piso() -> bool:
    """La matriz de los jobs de tests y `requires-python` dicen el mismo mínimo."""
    ci = RAIZ / ".github" / "workflows" / "vault-ci.yml"
    proj = RAIZ / "pyproject.toml"
    if not ci.exists() or not proj.exists():
        return False
    m = re.search(r'requires-python\s*=\s*"[><=~^]*\s*(\d+)\.(\d+)',
                  proj.read_text(encoding="utf-8"))
    if not m:
        return False
    piso = (int(m.group(1)), int(m.group(2)))
    versiones = _versiones_que_ejecutan_la_suite(ci)
    return bool(versiones) and min(versiones) == piso


def _ci_cubre_los_sistemas() -> bool:
    ci = RAIZ / ".github" / "workflows" / "vault-ci.yml"
    if not ci.exists():
        return False
    texto = ci.read_text(encoding="utf-8")
    return "ubuntu" in texto and "windows" in texto


def _hay_dependencias_declaradas() -> bool:
    """Toda dependencia que un módulo importa sin red está en `pyproject.toml`.

    Se comprueba contra PyYAML porque es la única, y porque el motivo por el que
    esta entrada existe fue afirmar en `INSTALL.md` que era opcional cuando seis
    módulos —`vault_write` entre ellos— la importan sin `except ImportError`.
    """
    proj = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    duros = _importadores_duros_de_yaml()
    return (not duros) or ("PyYAML" in proj or "pyyaml" in proj.lower())


def _importadores_duros_de_yaml() -> List[str]:
    """Los módulos que hacen `import yaml` sin reserva, en los dos árboles que
    viajan en la wheel. Hasta la deuda #12 bastaba con `scripts/`; desde que
    una tool migrada deja allí un alias sin código, su `import yaml` vive en
    `vault/` y medir solo `scripts/` lo perdía (AP-44)."""
    fuentes = sorted((RAIZ / "scripts").glob("*.py")) + sorted(
        p for p in (RAIZ / "vault").rglob("*.py") if "__pycache__" not in p.parts)
    return [
        p.relative_to(RAIZ).as_posix() for p in fuentes
        if re.search(r"^import yaml\b", p.read_text(encoding="utf-8", errors="replace"),
                     flags=re.M)
    ]


#: Lo que el classifier de `pyproject.toml` puede afirmar. «Production/Stable»
#: es una promesa sobre todas las demás: se gana cuando ninguna queda
#: descubierta, no cuando alguien decide subirlo.
CLASSIFIER_ESTABLE = "Development Status :: 5 - Production/Stable"
CLASSIFIER_BETA = "Development Status :: 4 - Beta"


def _madurez_coherente() -> bool:
    """El classifier no promete más madurez de la que el registro sostiene.

    Medido en v40.34: `pyproject.toml` declaraba 5 - Production/Stable con
    tres promesas descubiertas en este mismo registro, una de ellas que la
    wheel nunca se había ejecutado en un venv limpio. Beta siempre es
    coherente; Estable solo si no queda ninguna otra descubierta.
    """
    proj = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    if CLASSIFIER_ESTABLE not in proj:
        return CLASSIFIER_BETA in proj
    return not [
        p["id"] for p in PREGUNTAS
        if p["id"] != "madurez_declarada" and p["estado"] == "descubierta"
    ]


def _mcp_en_la_wheel() -> bool:
    """La wheel declara el servidor como package data y el servidor sabe dónde
    están las tools instaladas. Que funcione de verdad lo ejerce la product
    gate de instalación limpia con una sesión stdio."""
    proj = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    servidor = RAIZ / "mcp" / "nodejs" / "vault-mcp-server.mjs"
    return (
        '"vault_toolkit.mcp" = "mcp/nodejs"' in proj
        and '"vault_toolkit.mcp" = ["vault-mcp-server.mjs"' in proj
        and servidor.is_file()
        and "IMPL_INSTALADO" in servidor.read_text(encoding="utf-8")
    )


def _wheel_sin_gobernanza() -> bool:
    """El build declara el hook y el hook tiene una lista que filtrar.

    Que la lista coincida con la capacidad lo exige `vault_servicio --check`;
    aquí no se importa —esta tool es hoja— y se mide lo que ve quien construye.
    """
    proj = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    if 'build_py = "empaquetado.construir.BuildPy"' not in proj:
        return False
    try:
        lista = json.loads(
            (RAIZ / "empaquetado" / "fuera-de-la-wheel.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return False
    return bool(lista.get("modulos")) and _existe("empaquetado/construir.py")


def _vault_run_resuelve_el_producto() -> bool:
    """`vault` es el programa y `vault run` alcanza toda tool Python de producto.

    Hasta v40.34 este predicado era `"[project.scripts]" in pyproject`, que no
    mide la promesa sino su prólogo, y la fila seguía declarando un hueco de
    «89 de 93 sin execution_module» que ya no existía. Se mide lo que viaja en
    la wheel: el catálogo instalado, menos lo que el build deja fuera, menos
    las nativas del servidor (`script` vacío, no tienen módulo que resolver).
    """
    proj = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    if 'vault = "vault.product_cli:main"' not in proj:
        return False
    try:
        catalogo = json.loads(
            (RAIZ / "vault" / "meta_toolkit" / "tools-catalog.json").read_text(encoding="utf-8"))
        fuera = set(json.loads(
            (RAIZ / "empaquetado" / "fuera-de-la-wheel.json").read_text(encoding="utf-8")
        )["modulos"])
    except (OSError, ValueError, KeyError):
        return False
    tools = catalogo.get("tools", catalogo) if isinstance(catalogo, dict) else catalogo
    tools = list(tools.values()) if isinstance(tools, dict) else tools
    producto = [t for t in tools if t.get("script") and Path(t["script"]).stem not in fuera]
    return bool(producto) and all(
        t.get("execution_module")
        and (RAIZ / Path(*t["execution_module"].split("."))).with_suffix(".py").is_file()
        for t in producto
    )


def _wheel_probada_sin_la_fuente() -> bool:
    """La CI ejecuta las product gates y estas instalan la wheel en un venv
    nuevo y comprueban que la fuente no está —ni en disco ni en `sys.path`—.
    Que pasen lo dice su ejecución; aquí se mide que existan y que lo exijan."""
    ci = RAIZ / ".github" / "workflows" / "vault-ci.yml"
    if not ci.is_file() or "run_product_gates.py" not in ci.read_text(encoding="utf-8"):
        return False
    for gate in ("clean_install_gate.py", "memory_recovery_e2e_gate.py"):
        ruta = RAIZ / "tests" / gate
        if not ruta.is_file():
            return False
        texto = ruta.read_text(encoding="utf-8")
        # El acto, no la clave del informe: un `True` escrito no retira nada.
        if '"venv"' not in texto or "shutil.rmtree(source)" not in texto:
            return False
    return True


def _banco_de_agente() -> bool:
    """El banco habla con el servidor MCP con el perfil `agente` y la suite lo
    ejecuta tarea por tarea. Que pase lo dice su ejecución; aquí se mide que el
    ejecutor exista y ejerza lo que la promesa dice, no un servidor cualquiera."""
    banco = RAIZ / "tests" / "banco_agente.py"
    test = RAIZ / "tests" / "test_banco_agente.py"
    if not banco.is_file() or not test.is_file():
        return False
    texto = banco.read_text(encoding="utf-8")
    return ('"VAULT_MCP_PERFIL": PERFIL' in texto
            and "banco.correr(" in test.read_text(encoding="utf-8"))


def _sbom_en_la_ci() -> bool:
    """La CI genera el SBOM tras instalar la wheel y lo publica, y la suite
    comprueba que el generador mide en vez de suponer. Que el documento sea
    correcto lo dice tests/test_sbom.py; aquí, que alguien lo produzca."""
    ci = RAIZ / ".github" / "workflows" / "vault-ci.yml"
    if not (ci.is_file() and _existe("empaquetado/sbom.py") and _existe("tests/test_sbom.py")):
        return False
    texto = ci.read_text(encoding="utf-8")
    return ("python empaquetado/sbom.py --salida dist/sbom.spdx.json" in texto
            and "python empaquetado/sbom.py --inventario" in texto
            and "actions/upload-artifact" in texto)


#: Secciones que SECURITY.md tiene que tener para que quien encuentra un fallo
#: sepa qué versión se arregla, por dónde avisar y qué esperar (ISO/IEC 29147).
SECCIONES_SECURITY = ("## Versiones soportadas", "## Cómo reportar", "## Qué esperar",
                      "## Superficie expuesta")


def _politica_de_vulnerabilidades() -> bool:
    ruta = RAIZ / "SECURITY.md"
    if not ruta.is_file():
        return False
    texto = ruta.read_text(encoding="utf-8")
    return all(s in texto for s in SECCIONES_SECURITY) and "/security/advisories/new" in texto


#: El registro. **Fuente única**: la guía de `docs/` se deriva de aquí y se
#: regenera con `--guia`; lo que se escriba a mano allí se pierde.
#:
#: `ejerce` es un predicado, no una cadena: una promesa cuyo ejecutor se
#: describe en prosa vuelve a ser un párrafo que nadie ejecuta, que es
#: exactamente el fallo que este fichero existe para no repetir.
PREGUNTAS: List[Dict[str, Any]] = [
    {
        "id": "piso_de_lenguaje",
        "pregunta": "¿La versión mínima que promete el paquete la ejecuta alguien?",
        "promesa": "pyproject.toml declara requires-python",
        "por_que": (
            "Un piso que ninguna máquina ejecuta es una promesa, no soporte. "
            "Medido en v40.30: la CI probaba solo 3.11 con >=3.9 publicado, y "
            "seis sitios rompían al IMPORTAR en 3.9 —no al llamarse—, dos de "
            "ellos en módulos que importa medio repo."
        ),
        "ejerce": _ci_prueba_el_piso,
        "quien": "matriz python-version de .github/workflows/vault-ci.yml + tests/test_piso_python.py",
        "estado": "cubierta",
    },
    {
        "id": "dependencias_reales",
        "pregunta": "¿Lo que se importa sin red está declarado como dependencia?",
        "promesa": "INSTALL.md y pyproject.toml enumeran qué hace falta instalar",
        "por_que": (
            "Se afirmó que PyYAML era opcional porque «cada módulo que la "
            "importa tiene su except ImportError». Falso: seis la importan sin "
            "red, y uno es vault_write, el camino de escritura. La diferencia "
            "entre opcional y obligatoria la decide el código, no el recuerdo."
        ),
        "ejerce": _hay_dependencias_declaradas,
        "quien": "pyproject.toml [project.dependencies]",
        "estado": "cubierta",
    },
    {
        "id": "instalacion_fuera_del_repo",
        "pregunta": "¿Funciona copiado fuera de este repositorio?",
        "promesa": "INSTALL.md: copiar cuatro carpetas y exportar VAULT_ROOT",
        "por_que": (
            "Dentro del repo la autodetección acierta, los vaults de al lado "
            "son los consumidores conocidos y la ruta al manifiesto existe. "
            "Fuera, ninguna de las tres cosas es verdad: la raíz caía a "
            "repo_root_fallback y las escrituras aterrizaban DENTRO del "
            "toolkit, y el servidor MCP inventariaba el disco del usuario."
        ),
        "ejerce": lambda: _existe("README.md") and _existe("tests/test_portabilidad_v4030.py"),
        "quien": "tests/test_portabilidad_v4030.py + README.md (instrucciones de instalación inlined)",
        "estado": "cubierta",
    },
    {
        "id": "material_ajeno",
        "pregunta": "¿Se ha medido contra material que este repo no generó?",
        "promesa": "El estándar sirve para vaults preexistentes, no solo para los suyos",
        "por_que": (
            "Es la regla 7, y es la única de la casa que ya se pagó cinco "
            "veces: vault-sandbox/ lo genera este repo y comparte sus "
            "supuestos, así que no puede exhibir el fallo que la medida tiene."
        ),
        "ejerce": lambda: _existe("scripts/vault_foreign_check.py"),
        "quien": "vault_foreign_check --root <vault ajeno>, o --self-test sin uno a mano",
        "estado": "cubierta",
    },
    {
        "id": "sistemas_operativos",
        "pregunta": "¿Se ejecuta en los sistemas donde se dice que corre?",
        "promesa": "Multiplataforma: rutas por pathlib, sin dependencias del shell",
        "por_que": (
            "Todo el desarrollo ocurre en Windows. Las trampas de plataforma "
            "—finales de línea, codificación de la locale, mayúsculas del "
            "sistema de ficheros— son justo las que no se ven desde dentro."
        ),
        "ejerce": _ci_cubre_los_sistemas,
        "quien": "matriz os de la CI (ubuntu-latest, windows-latest)",
        "estado": "cubierta",
        "hueco_conocido": (
            "La CI declara la suite y las product gates en ubuntu, pero esta "
            "rama no ha pasado por la CI. El paseo de INSTALACIÓN fuera del repo "
            "se ha hecho de forma recurrente en Windows y una vez a mano en "
            "Linux (2026-10-04, wheel 40.35 en python:3.12-slim con usuario sin "
            "privilegios: 16/16); en Linux no lo repite ninguna máquina. macOS "
            "no lo toca nadie. Las instrucciones de instalación están inlined "
            "en README.md."
        ),
    },
    {
        "id": "superficie_expuesta",
        "pregunta": "¿Está escrito qué expone y a quién, donde lo lee quien instala?",
        "promesa": (
            "El servidor MCP por HTTP y el servicio de tokens son locales y "
            "exigen token, sin Origin ni Host ajenos"
        ),
        "por_que": (
            "Hasta v40.34 esta fila prometía «local y sin autenticación» y lo "
            "llamaba correcto como diseño. No lo era: el navegador del usuario "
            "también vive en 127.0.0.1, y con CORS `*` cualquier página abría "
            "/sse y llamaba a vault_delete. SP-04 es la corrección, y se ejerce "
            "con el servidor real por HTTP, no leyendo el README. Hasta v41.2 "
            "SECURITY.md declaraba el servicio de tokens «no autentica» y esta "
            "fila no lo miraba: declarar el hueco no lo cerraba."
        ),
        "ejerce": lambda: _existe("tests/test_mcp_http_seguridad.py")
        and "tokenValido" in (RAIZ / "mcp" / "nodejs" / "vault-mcp-server.mjs").read_text(encoding="utf-8")
        and _existe("tests/test_token_service_seguridad.py")
        and "_autorizado" in (RAIZ / "scripts" / "vault_token_service.py").read_text(encoding="utf-8"),
        "quien": (
            "tests/test_mcp_http_seguridad.py (servidor real por HTTP) + "
            "tests/test_token_service_seguridad.py (servicio de tokens real) + README.md"
        ),
        "estado": "cubierta",
    },
    {
        "id": "ergonomia_de_entrada",
        "pregunta": "¿Se invoca como un programa o como un montón de scripts?",
        "promesa": "[project.scripts] declarado + execution_module poblado para todas las distributables",
        "por_que": (
            "Un toolkit que se invoca como `python scripts/vault_x.py` exige el "
            "checkout. `vault = vault.product_cli:main` es el programa, y `vault run` "
            "solo alcanza las tools cuyo `execution_module` resuelve en lo instalado. "
            "Medido en v40.34: toda tool Python de producto lo tiene y el módulo "
            "existe; las dos nativas del servidor no tienen módulo que resolver."
        ),
        "ejerce": _vault_run_resuelve_el_producto,
        "quien": (
            "vault/meta_toolkit/tools-catalog.json + empaquetado/fuera-de-la-wheel.json + "
            "`vault run` en tests/clean_install_gate.py"
        ),
        "estado": "cubierta",
        # superseded_by: _vault_run_resuelve_el_producto (v40.34). El hueco A2 se
        # cerró en el catálogo y esta fila siguió declarándolo; se conserva.
        "motivo_hasta_v40_34": (
            "El catálogo del producto (tools-catalog.json) se genera desde TOOLS_CATALOG "
            "con execution_module=null para la mayoría de las tools. La solución (A2) es "
            "auto-derivar execution_module = vault_toolkit.operations.<tool> en "
            "catalogo_producto cuando script existe y execution_module es null, igual que "
            "hace distribucion.py en el source. La decisión ya está tomada en el código; "
            "falta persistirla en el artefacto."
        ),
    },
    {
        "id": "mcp_requiere_checkout",
        "pregunta": "¿Se puede instalar el servidor MCP con un solo comando de pip/npm?",
        "promesa": (
            "`pip install` deja el servidor MCP en la instalación y `vault mcp-path` "
            "imprime su ruta y la configuración del cliente"
        ),
        "por_que": (
            "Hasta v40.34 el servidor vivía solo en `mcp/nodejs/` y resolvía las "
            "tools en `../../scripts`, que en una instalación no existe: el único "
            "camino era un git clone y `node mcp/nodejs/vault-mcp-server.mjs`. "
            "Ahora viaja como package data de `vault_toolkit.mcp` —el mismo "
            "fichero, sin copia— y lanza las tools desde `vault_toolkit/_impl/`. "
            "Sigue sin publicarse en npm: esa decisión de nombre público no se "
            "ha tomado, y pip ya cubre la instalación con un comando."
        ),
        "ejerce": _mcp_en_la_wheel,
        "quien": (
            "pyproject.toml (package data) + vault mcp-path + "
            "tests/test_mcp_instalado.py + tests/clean_install_gate.py"
        ),
        "estado": "cubierta",
    },
    {
        "id": "contrato_con_quien_contribuye",
        "pregunta": "¿Sabe alguien de fuera cómo aportar o cómo reportar un fallo?",
        "promesa": "Repositorio público",
        "por_que": (
            "Para un repo público esto no es un detalle de forma: sin canal "
            "declarado, un fallo de seguridad no tiene por dónde llegar salvo "
            "un issue abierto, que es el peor sitio para reportarlo."
        ),
        "ejerce": lambda: "pull request" in (RAIZ / "README.md").read_text(encoding="utf-8"),
        "quien": "README.md (sección «Estado del proyecto»)",
        "estado": "cubierta",
    },
    {
        "id": "lo_publicado_es_solo_el_estandar",
        "pregunta": "¿Puede irse en un push algo que no es de este repo?",
        "promesa": "Repositorio público que convive con copias de vaults reales",
        "por_que": (
            "En el mismo disco, al lado del estándar, viven `_datasets/`, "
            "`_datasets-reports/` y `_backups-builderx/`: notas privadas de "
            "otros proyectos, runbooks con credenciales, datos de clientes. "
            "Hasta hoy eso lo sostenía solo el `.gitignore`, que es advisory: "
            "no para un `git add -f` ni un directorio hermano nuevo que nadie "
            "añada al fichero. Y publicado es publicado, aunque se borre "
            "después — la copia queda en el historial, en los forks y en la "
            "caché de quien lo indexó."
        ),
        "ejerce": lambda: _existe("tests/test_publicacion_limpia.py"),
        "quien": "tests/test_publicacion_limpia.py (mide el índice de git, no el disco)",
        "estado": "cubierta",
        "hueco_conocido": (
            "Mide el índice de HOY. Lo que ya esté en un commit anterior del "
            "historial no lo ve nadie: para eso haría falta recorrer todos los "
            "árboles, y este repo nunca ha versionado esos directorios."
        ),
    },
    {
        "id": "wheel_instalada_funciona",
        "pregunta": "¿Funciona la wheel instalada en un venv limpio fuera del repo?",
        "promesa": "tests/run_product_gates.py ejecuta la wheel en venv aislado",
        "por_que": (
            "La wheel puede armarse mal y pasar los tests del repo (que usan el "
            "source) pero fallar en un venv limpio (que solo tiene lo instalado)."
        ),
        "ejerce": _wheel_probada_sin_la_fuente,
        "quien": (
            "tests/run_product_gates.py (clean_install + memory_e2e) + job "
            "'product-gates' en vault-ci.yml"
        ),
        "estado": "cubierta",
        # superseded_by: _wheel_probada_sin_la_fuente (v40.34). Las dos gates
        # instalan la wheel en un venv nuevo, borran la copia de la fuente y
        # fallan si una ruta del checkout aparece en sys.path: lo que este motivo
        # decía que faltaba. Ejecutadas en verde el 2026-09-29; se conserva.
        "motivo_hasta_v40_34": (
            "La promesa existe (run_product_gates.py + CI) pero nunca se ha "
            "ejecutado contra un venv limpio real fuera de este repo. "
            "El gate ejecuta la wheel desde el mismo checkout fuente, así que "
            "el test no garantiza que la wheel funcione aislada. "
            "Pendiente: ejecutar run_product_gates.py en un CI separado o "
            "desde una maquina limpia que no tenga este repo."
        ),
    },
    {
        "id": "madurez_declarada",
        "pregunta": "¿El grado de madurez publicado lo sostiene este registro?",
        "promesa": "El classifier Development Status de pyproject.toml",
        "por_que": (
            "Quien instala lee el classifier antes que cualquier documento. "
            "Hasta v40.34 decía 5 - Production/Stable mientras tres filas de "
            "esta misma tabla seguían descubiertas: la etiqueta prometía lo "
            "que el registro negaba. Subirlo a 5 no es una decisión de "
            "redacción; se gana cerrando las descubiertas. Se ganó tras la "
            "validación de la Fase 6 (2026-10-04), con cero descubiertas."
        ),
        "ejerce": _madurez_coherente,
        "quien": "vault_produccion._madurez_coherente + tests/test_produccion.py",
        "estado": "cubierta",
    },
    {
        "id": "wheel_sin_gobernanza",
        "pregunta": "¿Lo que instalo es el producto, o también las herramientas que miden este repo?",
        "promesa": "La wheel no lleva la capacidad gobernanza_del_estandar (grupo 35)",
        "por_que": (
            "Hasta v40.34 la wheel llevaba vault_gate, vault_arch y el resto del "
            "meta-toolkit sin sus baselines ni su manifiesto: código que en la "
            "máquina de un tercero no tiene sobre qué actuar. La lista de lo que "
            "queda fuera se deriva de vault_servicio.CAPACIDADES."
        ),
        "ejerce": _wheel_sin_gobernanza,
        "quien": (
            "empaquetado/construir.py + vault_servicio --check (invariante 11) + "
            "tests/clean_install_gate.py"
        ),
        "estado": "cubierta",
    },
    {
        "id": "memoria_para_agentes",
        "pregunta": "¿Un agente LLM que solo ve el MCP consigue orientarse, escribir, recordar, recuperarse y borrar?",
        "promesa": "El servicio: memoria documental persistente, auditable y gobernada para un agente",
        "por_que": (
            "Las demás filas miden la instalación; ninguna, el servicio. "
            "Medido el 2026-10-07 al construir el banco con el perfil agente: "
            "la pista de INVALID_FOLDER no nombraba ninguna sección, una "
            "sección inferida por una palabra escondía la nota pedida por su "
            "título (recuerdo de 0,84 y 0,88 sobre copias de /vcloud y /ans), "
            "validate mandaba a reparar frontmatter por carpetas ausentes y "
            "reindex --check salía en rojo sin error_code. Todo verde en las "
            "puertas: las puertas miran el repo, no al agente."
        ),
        "ejerce": _banco_de_agente,
        "quien": "tests/banco_agente.py (sesión MCP con VAULT_MCP_PERFIL=agente) + tests/test_banco_agente.py",
        "estado": "cubierta",
        "hueco_conocido": (
            "La suite ejerce las cinco tareas sobre un vault que crea el propio "
            "repo. El recuerdo sobre notas preexistentes de un vault ajeno "
            "(--copiar-de, regla 7) es una medida que se ejecuta a mano sobre "
            "copias y se reporta; no la repite la CI. Sin Node en el PATH el "
            "test se salta, y esta rama no ha pasado por la CI."
        ),
    },
    {
        "id": "sbom_y_licencias",
        "pregunta": "¿Sabe quien instala qué paquetes recibe y bajo qué licencia?",
        "promesa": "Un SBOM SPDX (ISO/IEC 5962) con el inventario de licencias (ISO/IEC 5230) de cada build",
        "por_que": (
            "Quien redistribuye la wheel acepta las licencias de todo lo que "
            "trae. Hasta v41.3 la única forma de saberlo era leer "
            "pyproject.toml a mano, y la licencia de la dependencia ni siquiera "
            "estaba ahí: está en sus metadatos. Un inventario escrito a mano "
            "envejece en la dirección cómoda, como cualquier cifra (AP-47)."
        ),
        "ejerce": _sbom_en_la_ci,
        "quien": "empaquetado/sbom.py en el job product-gates de la CI + tests/test_sbom.py",
        "estado": "cubierta",
        "hueco_conocido": (
            "El SBOM se publica como artefacto de la CI, no viaja dentro de la "
            "wheel. Cubre las dependencias directas; las transitivas no, porque "
            "PyYAML no tiene. Esta rama no ha pasado por la CI."
        ),
    },
    {
        "id": "politica_de_vulnerabilidades",
        "pregunta": "¿Sabe quien encuentra un fallo de seguridad por dónde avisar sin publicarlo?",
        "promesa": "SECURITY.md: versiones soportadas, canal privado y qué esperar (ISO/IEC 29147)",
        "por_que": (
            "El README decía «contactar directamente» sin decir cómo. Un fallo "
            "del servidor MCP por HTTP —el que expone el vault a la red local— "
            "acabaría en un issue público, que es el peor sitio donde puede "
            "aparecer antes de tener arreglo."
        ),
        "ejerce": _politica_de_vulnerabilidades,
        "quien": "SECURITY.md (secciones de SECCIONES_SECURITY) + tests/test_produccion_iso.py",
        "estado": "cubierta",
        "hueco_conocido": (
            "El canal es el reporte privado de vulnerabilidades de GitHub, y "
            "solo funciona si el dueño lo activa en la configuración del "
            "repositorio; desde aquí no se puede comprobar."
        ),
    },
]


def medir() -> Dict[str, Any]:
    """Evalúa cada promesa. El predicado se llama AHORA, nunca al importar."""
    filas = []
    for p in PREGUNTAS:
        try:
            ejercida = bool(p["ejerce"]())
        except (OSError, ValueError, KeyError):
            # Un predicado que no puede leer lo que mide no es un verde: es una
            # promesa que dejó de tener ejecutor, que es justo el caso a cazar.
            ejercida = False
        filas.append({
            "id": p["id"],
            "pregunta": p["pregunta"],
            "estado": p["estado"],
            "ejercida": ejercida,
            "quien": p["quien"],
            **({"hueco_conocido": p["hueco_conocido"]} if p.get("hueco_conocido") else {}),
            **({"motivo": p["motivo"]} if p.get("motivo") else {}),
        })
    return {"filas": filas}


def check() -> Dict[str, Any]:
    m = medir()
    rotas = [
        f["id"] for f in m["filas"]
        if f["estado"] == "cubierta" and not f["ejercida"]
    ]
    sin_motivo = [
        f["id"] for f in m["filas"]
        if f["estado"] == "descubierta" and not f.get("motivo")
    ]
    desconocidos = [f["id"] for f in m["filas"] if f["estado"] not in ESTADOS]
    return {
        "ok": not rotas and not sin_motivo and not desconocidos,
        "tool": "vault_produccion",
        "action": "check",
        "promesas": len(m["filas"]),
        "cubiertas": sum(1 for f in m["filas"] if f["estado"] == "cubierta"),
        "descubiertas": sum(1 for f in m["filas"] if f["estado"] == "descubierta"),
        "huecos_declarados": [
            f["id"] for f in m["filas"] if f.get("hueco_conocido")
        ],
        "promesas_sin_ejecutor": rotas,
        "descubiertas_sin_motivo": sin_motivo,
        "estados_desconocidos": desconocidos,
        "filas": m["filas"],
        "hint": (
            "Verde significa que toda promesa listada tiene quien la ejerza, no "
            "que la lista esté completa. Una promesa que nadie escribió aquí "
            "sigue sin medirse."
        ),
    }


def _guia() -> str:
    m = medir()
    L = [
        "# Guía de construcción — las preguntas que no se hace el repo a sí mismo",
        "",
        "> **Documento derivado.** Sale de `scripts/vault_produccion.PREGUNTAS` y se",
        "> regenera con `python scripts/vault_produccion.py --guia`. Lo que se escriba",
        "> a mano aquí se pierde: es lo que lo mantiene honesto.",
        "",
        "## De dónde sale",
        "",
        "De una pregunta hecha con todas las puertas en verde y una versión recién",
        "cerrada: **«¿ya puede usarlo otra persona, aparte de mí, y con resultados",
        "fiables?»**. En menos de diez minutos apareció un defecto que ninguna puerta",
        "veía —el piso de Python prometido que ninguna máquina ejecutaba—, porque",
        "todas las puertas miden *el repo contra sí mismo* y en esa sala no está el",
        "consumidor.",
        "",
        "El patrón es siempre el mismo, y es el de toda la tanda v40.30:",
        "",
        "```",
        "alcance declarado  >  alcance ejercido   ⇒   el hueco devuelve CERO,",
        "                                             y un cero se lee como limpio.",
        "```",
        "",
        "Por eso la pregunta se hace **antes** de dar algo por terminado, y por eso",
        "está escrita como registro ejecutable y no como recordatorio.",
        "",
        "## Cómo se usa en construcción",
        "",
        "1. Antes de cerrar una versión, `python scripts/vault_produccion.py --check --strict`.",
        "2. Cuando añadas una promesa al consumidor —una versión soportada, una",
        "   plataforma, una dependencia opcional, una superficie de red— **añade su fila**",
        "   con el predicado que la ejerce. Una promesa sin fila no la mide nadie.",
        "3. Si no tiene ejecutor, se declara `descubierta` **con el motivo escrito**. No",
        "   es un fallo: es la forma barata. Lo que rompe la puerta es una promesa",
        "   marcada como cubierta cuyo ejecutor ya no existe — una mentira comprobable.",
        "",
        "## Estado",
        "",
        "| Promesa | Pregunta | Estado | Quién la ejerce |",
        "|---|---|---|---|",
    ]
    for f in m["filas"]:
        marca = "✅" if f["ejercida"] else ("⚠️" if f["estado"] == "descubierta" else "❌")
        L.append(f"| `{f['id']}` | {f['pregunta']} | {marca} {f['estado']} | {f['quien']} |")

    L += ["", "## Los huecos, escritos", ""]
    hay = False
    for p in PREGUNTAS:
        if p.get("motivo"):
            hay = True
            L += [f"**`{p['id']}` — descubierta.** {p['por_que']}", "",
                  f"*Por qué se deja así:* {p['motivo']}", ""]
        if p.get("hueco_conocido"):
            hay = True
            L += [f"**`{p['id']}` — cubierta con hueco.** {p['hueco_conocido']}", ""]
    if not hay:
        L += ["Ninguno declarado.", ""]

    L += [
        "## Qué NO demuestra el verde",
        "",
        "Que toda promesa **listada** tiene ejecutor. No que la lista esté completa:",
        "una promesa que nadie escribió en el registro sigue sin medirse, y esta tool",
        "no puede leer lo que prometiste en un README que no conoce. El registro se",
        "amplía cuando alguien tropieza — que es exactamente como nació.",
        "",
    ]
    return "\n".join(L)


def escribir_guia() -> Dict[str, Any]:
    GUIA.parent.mkdir(parents=True, exist_ok=True)
    # El derivado versionado usa LF incluso cuando el productor corre en Windows:
    # de otro modo el CR introducido por la traducción de texto se reporta como
    # whitespace nuevo por ``git diff --check``.
    GUIA.write_bytes(_guia().encode("utf-8"))
    return {"ok": True, "tool": "vault_produccion", "action": "guia",
            "written": str(GUIA.relative_to(RAIZ)).replace("\\", "/"),
            "promesas": len(PREGUNTAS)}


def check_doc() -> Dict[str, Any]:
    actual = GUIA.read_text(encoding="utf-8") if GUIA.exists() else ""
    al_dia = actual == _guia()
    return {"ok": al_dia, "tool": "vault_produccion", "action": "check-doc",
            "doc": str(GUIA.relative_to(RAIZ)).replace("\\", "/"),
            "stale": not al_dia,
            "recovery": "python scripts/vault_produccion.py --guia"}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="vault_produccion — ¿puede usar esto otra persona? (guía de construcción)", allow_abbrev=False)
    ap.add_argument("--check", action="store_true", help="Mide cada promesa contra su ejecutor")
    ap.add_argument("--strict", action="store_true", help="Exit 1 si alguna promesa perdió ejecutor")
    ap.add_argument("--guia", action="store_true", help="Regenera docs/GUIA-DE-PRODUCCION.md")
    ap.add_argument("--check-doc", action="store_true", help="Falla si la guía diverge del registro")
    args = ap.parse_args()

    if args.guia and args.check:
        env = emit_error("vault_produccion", "CONFLICTING_ARGS",
                         "--guia escribe y --check mide: elige uno",
                         pista="elige uno")
        print(json.dumps(env, ensure_ascii=False))
        return 1

    if args.guia:
        r: Dict[str, Any] = escribir_guia()
    elif args.check_doc:
        r = check_doc()
    else:
        r = check()

    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 1 if args.strict and not r["ok"] else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_produccion"))
