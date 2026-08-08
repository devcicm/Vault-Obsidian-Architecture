"""Lo que los diecisiete `*_save` escriben hoy, byte a byte, antes de tocarlos.

AP-46 dice que el frontmatter no se escribe a mano, y los diecisiete lo hacen:
133 líneas construyendo YAML con tres criterios de escapado mezclados en el
mismo repo —`json.dumps`, `yaml_scalar` y f-string crudo—. Unificarlos en un
escritor único es la corrección; el riesgo es cambiar en silencio un envelope o
una nota que ya consumen los repos de fuera.

Por eso este fichero se captura **antes** del cambio y no después. No prueba
que la salida sea correcta: prueba que **no cambia**. Si un día falla por un
cambio deliberado, se actualiza el dorado en el mismo commit que lo motiva y se
ve en el diff, que es exactamente lo que un cambio silencioso no permite.

Los títulos llevan acentos a propósito: `json.dumps` sin `ensure_ascii=False`
guarda `Migración` como `Migraci\\u00f3n`, y el sandbox no tiene un solo título
acentuado en estas tools, así que el defecto está latente y verde.
"""

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
DORADOS = Path(__file__).parent / "dorados" / "saves"

#: Argv mínimo de cada tool para producir una nota. Los siete primeros salen de
#: `test_indice_no_se_regenera_dos_veces`, que ya los tenía medidos.
INVOCACIONES = {
    "vault_risk_save": ["--project", "demo", "--title", "Un riesgo de migración"],
    "vault_ncr_save": ["--project", "demo", "--title", "Una no conformidad"],
    "vault_slo_save": [
        "--project", "demo", "--service", "api",
        "--slo_type", "availability", "--target", "99.9",
    ],
    "vault_incident_save": ["--project", "demo", "--title", "Caída del índice"],
    "vault_privacy_save": [
        "--project", "demo", "--title", "Un tratamiento",
        "--purpose", "Analítica interna", "--legal_basis", "consent",
    ],
    "vault_release_save": ["--project", "demo", "--version", "1.0.0"],
    "vault_knowledge_save": [
        "--category", "concept",
        "--title", "Un concepto con acentuación",
        "--content", "Una línea.\nOtra línea.\nY una tercera con palabras.",
    ],
    "vault_bibliography_save": [
        "--title", "Guía de diseño", "--url", "https://example.org/guia",
        "--summary", "Un resumen corto.", "--source_type", "docs",
    ],
    "vault_bug_save": [
        "--project", "demo", "--title", "Excepción al guardar",
        "--symptom", "Revienta con acentuación en el título.",
    ],
    "vault_diagram_save": [
        "--project", "demo", "--title", "Diagrama de migración",
        "--diagram_type", "mermaid", "--category", "component",
        "--content", "flowchart TD\n  A --> B",
    ],
    "vault_env_save": [
        "--project", "demo", "--environment", "staging",
        "--vars",
        '[{"name": "API_URL", "description": "Dirección del servicio",'
        ' "required": true, "provider": "env-file"}]',
    ],
    "vault_flow_save": [
        "--project", "demo", "--name", "Alta de usuario",
        "--type", "workflow", "--description", "Cómo se da de alta.",
        "--mermaid", "flowchart TD\n  A --> B",
    ],
    "vault_infra_save": [
        "--name", "servidor-de-índices", "--type", "server",
        "--description", "Máquina que sirve los índices.",
        "--config", '{"cpu": 4}',
    ],
    "vault_pattern_save": [
        "--project", "demo", "--name", "Repositorio por contexto",
        "--type", "architecture", "--status", "implementado",
    ],
    "vault_requirement_save": [
        "--project", "demo", "--title", "Búsqueda por categoría",
        "--description", "El usuario busca por categoría.",
        "--type", "functional", "--priority", "must-have",
    ],
    "vault_runbook_save": [
        "--project", "demo", "--title", "Rotación de credenciales",
        "--trigger", "Cada noventa días", "--category", "maintenance",
        "--steps",
        '[{"step": "Generar la credencial nueva", "command": "vault kv put"},'
        ' {"step": "Desplegarla y verificar el índice"}]',
    ],
    "vault_test_save": [
        "--project", "demo", "--title", "Validación de acentos",
        "--test_type", "unit", "--description", "Comprueba la codificación.",
    ],
}

#: Lo que cambia en cada corrida y no puede entrar en un dorado. Se sustituye
#: por un marcador en vez de borrarse: que el campo esté es parte del contrato.
VOLATILES = [
    # Antes que las fechas: `NCR-2026-312` lleva año y correlativo, y el
    # correlativo cambia de una corrida a otra.
    (re.compile(r"\b[A-Z]{2,6}-\d{4}-\d{1,4}\b"), "<CORRELATIVO>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?"), "<FECHA>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}"), "<DIA>"),
    (re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
                r"[0-9a-f]{4}-[0-9a-f]{12}"), "<UUID>"),
]


def _estable(texto: str, raiz: Path) -> str:
    texto = texto.replace(str(raiz), "<VAULT>").replace(
        str(raiz).replace("\\", "\\\\"), "<VAULT>"
    ).replace(str(raiz).replace("\\", "/"), "<VAULT>")
    for patron, marca in VOLATILES:
        texto = patron.sub(marca, texto)
    return texto


def _ejecutar(raiz: Path, script: str, *argv: str):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / f"{script}.py"), *argv],
        env=dict(
            os.environ,
            VAULT_ROOT=str(raiz),
            PYTHONIOENCODING="utf-8",
            # Fijada a propósito: `vault_bug_save` exige atribución (AP-16) y
            # cae a esta variable. Sin fijarla, el dorado saldría distinto
            # según quién ejecute la suite.
            VAULT_AGENT="system",
        ),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO_ROOT),
    )


@pytest.fixture(scope="module")
def vault(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("caracterizacion")
    _ejecutar(raiz, "vault_init")
    return raiz


#: Una sola invocación por tool, compartida por los cuatro casos. Invocarla
#: cuatro veces no medía lo mismo cuatro veces: la segunda pasada de
#: `vault_pattern_save` ya no era una creación sino una transición de estado,
#: y el caso fallaba sin que hubiera nada roto.
_CACHE: dict = {}


def _salida(raiz: Path, script: str):
    if script in _CACHE:
        return _CACHE[script]
    r = _ejecutar(raiz, script, *INVOCACIONES[script])
    assert r.returncode == 0, (r.stdout[-600:] + r.stderr[-600:])
    envelope = json.loads(r.stdout.strip().splitlines()[-1])
    ruta = envelope.get("path") or envelope.get("file")
    nota = None
    if ruta:
        p = Path(ruta)
        if not p.is_absolute():
            p = raiz / ruta
        if p.exists():
            nota = p.read_text(encoding="utf-8")
    _CACHE[script] = (envelope, nota)
    return envelope, nota


def _sin_lo_best_effort(envelope: dict) -> dict:
    """`unchanged` no se puede congelar: cuenta trabajo que puede no ocurrir.

    Medido en `vault_infra_save`: escribir `infra-map.md` regenera la sección
    entera, y eso reescribe `09_Infrastructure/servers/index.md` con contenido
    idéntico al que la nota acababa de generar. Ese segundo pase es redundante
    **y** best-effort: `_auto_section_index` traga cualquier excepción a
    propósito, para que un índice roto nunca bloquee la escritura que lo
    disparó. Si el pase no ocurre, `unchanged` baja de 1 a 0 sin que haya
    cambiado nada de lo que un consumidor observa.

    Se sustituye por un marcador en vez de borrarse: que el campo exista es
    parte del contrato de AP-37, y `created`, `updated`, `written` y `path` —lo
    que sí es trabajo comprobable— se siguen congelando byte a byte. La
    regeneración duplicada es deuda declarada, no algo que este dorado tape.
    """
    return {**envelope, "unchanged": "<BEST-EFFORT>"} if "unchanged" in envelope else envelope


@pytest.mark.parametrize("script", sorted(INVOCACIONES))
def test_el_envelope_y_la_nota_no_cambian(vault, script):
    """El dorado. Si esto falla, algo cambió para quien ya consume la tool."""
    envelope, nota = _salida(vault, script)
    actual = _estable(
        json.dumps({"envelope": _sin_lo_best_effort(envelope), "nota": nota},
                   indent=2, ensure_ascii=False, sort_keys=True),
        vault,
    )
    dorado = DORADOS / f"{script}.json"
    if not dorado.exists():
        dorado.parent.mkdir(parents=True, exist_ok=True)
        dorado.write_text(actual + "\n", encoding="utf-8")
        pytest.skip(f"dorado creado: {dorado.name}")
    assert actual == dorado.read_text(encoding="utf-8").rstrip("\n"), (
        f"{script} cambió su salida. Si es deliberado, actualiza "
        f"tests/dorados/saves/{script}.json en este mismo commit."
    )


@pytest.mark.parametrize("script", sorted(INVOCACIONES))
def test_el_frontmatter_es_yaml_valido(vault, script):
    """Con `yaml.safe_load` y no con un regex por líneas (AP-44).

    Medir el frontmatter con la misma normalización que lo escribió es cómo
    tres de los cuatro defectos de las rondas anteriores pasaron desapercibidos.
    """
    _, nota = _salida(vault, script)
    assert nota is not None, script
    assert nota.startswith("---\n"), script
    fm = yaml.safe_load(nota.split("---", 2)[1])
    assert isinstance(fm, dict) and fm, script


#: `vault_knowledge_save`, `vault_risk_save` y `vault_runbook_save` estuvieron
#: marcados aquí como `xfail(strict=True)`: los tres escribían `ó` dentro
#: del YAML. El escritor único (`vault/autoria/frontmatter.py`) los arregló y
#: el propio marcador estricto falló por XPASS, que es para lo que se puso.
#: Ya no hay excepciones: los diecisiete pasan.
@pytest.mark.parametrize("script", sorted(INVOCACIONES))
def test_ningun_acento_se_guarda_escapado(vault, script):
    """AP-46 por la puerta de atrás: `json.dumps` sin `ensure_ascii=False`.

    Guarda `Migración` como `Migraci\\u00f3n` dentro del YAML. Está latente
    porque el sandbox no tiene un solo título acentuado en estas tools — el
    fallo solo aparece con datos reales, que es la peor forma de que aparezca.
    """
    envelope, nota = _salida(vault, script)
    for donde, texto in (("nota", nota), ("envelope", json.dumps(
            envelope, ensure_ascii=False))):
        if texto:
            assert "\\u00" not in texto, f"{script}: acento escapado en {donde}"


def test_ningun_main_devuelve_envelope_en_vez_de_codigo_de_salida():
    """El defecto que destapó esta caracterización, convertido en puerta.

    `vault_infra_save` y `vault_runbook_save` hacían `return {"ok": False, ...}`
    en la rama de JSON inválido, mientras el resto de `main()` devuelve `0` o
    `1`. Ese dict llegaba a `sys.exit()`, que intenta convertirlo a entero: el
    usuario que escribía mal un `--config` veía un `UNEXPECTED_ERROR` de
    severidad **critical** con traceback, en vez del mensaje "Invalid JSON in
    --config" que la tool ya tenía escrito para exactamente ese caso.

    Va por AST y sobre las 113 tools, no sobre las dos: el patrón —una rama de
    error temprana que se olvida de que está en `main()`— no tiene nada de
    particular de estas dos.
    """
    culpables = []
    for ruta in sorted(SCRIPTS.glob("vault_*.py")):
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
        for fn in ast.walk(arbol):
            if not (isinstance(fn, ast.FunctionDef) and fn.name == "main"):
                continue
            for nodo in ast.walk(fn):
                if isinstance(nodo, ast.Return) and isinstance(nodo.value, ast.Dict):
                    culpables.append(f"{ruta.name}:{nodo.lineno}")
    assert not culpables, (
        "`main()` devuelve código de salida, no envelope. Imprime el JSON y "
        f"devuelve 1: {culpables}"
    )


@pytest.mark.parametrize("script", sorted(INVOCACIONES))
def test_el_envelope_declara_trabajo(vault, script):
    """AP-37: un `ok: true` sin indicador de trabajo no dice si hizo algo."""
    envelope, _ = _salida(vault, script)
    assert envelope.get("ok") is True, script
    assert any(k in envelope for k in
               ("path", "file", "created", "written", "updated", "changes")), (
        f"{script}: envelope sin indicador de trabajo"
    )
