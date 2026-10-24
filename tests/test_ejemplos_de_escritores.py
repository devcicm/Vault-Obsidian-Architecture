"""El ejemplo del catálogo de un escritor crea la nota, no un error bien formado.

`vault_smoke` (AP-42) da por buena una salida `ok: false` con forma de JSON,
porque el sandbox no tiene las rutas de muchos ejemplos. Eso dejaba pasar lo
que salió al medir CN-04 (2026-10-08): siete escritores cuyo ejemplo
documentado lo rechaza la propia tool —un `--type` fuera de sus `choices`, un
`--steps` que no es el array JSON que pide—. Quien copia el ejemplo no tiene
otra cosa que copiar.

El argv es el que construye `vault_smoke.invocation`, el mismo que el smoke, y
se contrasta con lo que haría una shell POSIX con esa línea (AP-44: el
consumidor del ejemplo es una persona en su terminal).
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import vault_smoke  # noqa: E402
from vault_mcp_catalog import TOOLS_CATALOG  # noqa: E402

ESCRITORES = [
    "vault_ai_decision", "vault_env_save", "vault_infra_save", "vault_pattern_save",
    "vault_requirement_save", "vault_runbook_save",
]


def _env(v: Path) -> dict:
    return {**os.environ, "VAULT_ROOT": str(v), "VAULT_STRICT_ROOT": "1",
            "VAULT_AGENT": "test", "VAULT_VOICE": "0", "PYTHONIOENCODING": "utf-8"}


@pytest.fixture(scope="module")
def copia_con_proyecto(tmp_path_factory):
    v = tmp_path_factory.mktemp("ejemplos") / "vault"
    # Copiar el sandbox compartido mientras otros workers escriben en él
    # falla en Windows: un fichero abierto para escritura no se puede leer,
    # y `copytree` levanta PermissionError —que pytest reporta como ERROR
    # de fixture, no como fallo de aserción—. Se reintenta: la copia es
    # idempotente y lo que hace falta es una foto estable, no la primera.
    import time

    ultimo_error = None
    for intento in range(5):
        try:
            shutil.copytree(ROOT / "vault-sandbox", v,
                            ignore=shutil.ignore_patterns(".locks"))
            ultimo_error = None
            break
        except PermissionError as exc:
            ultimo_error = exc
            shutil.rmtree(v, ignore_errors=True)
            time.sleep(0.5 * (intento + 1))
    assert ultimo_error is None, (
        f"no se pudo copiar el sandbox tras 5 intentos: {ultimo_error}"
    )
    if not (v / "01_Projects" / "mi-api").exists():
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "vault_project.py"),
             "--add", "mi-api", "--title", "Mi API"],
            cwd=ROOT, env=_env(v), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=300)
        assert r.returncode == 0, r.stdout + r.stderr
    return v


@pytest.mark.parametrize("tool", ESCRITORES)
def test_el_ejemplo_documentado_del_escritor_tiene_exito(copia_con_proyecto, tool):
    argv = vault_smoke.invocation(tool)
    linea = TOOLS_CATALOG[tool]["example"].splitlines()[0]
    # Lo que la shell le pasaría a la tool es lo mismo que le pasa el smoke.
    assert [a for a in argv[2:] if a != "--json"] == shlex.split(linea)[2:]
    r = subprocess.run(argv, cwd=ROOT / "scripts", env=_env(copia_con_proyecto),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    salida = r.stdout.strip()
    try:
        datos = json.loads(salida)
    except ValueError:
        datos = json.loads(salida.splitlines()[-1])
    assert datos.get("ok") is True, (linea, datos)


def test_el_efecto_declarado_de_ai_decision_es_donde_escribe():
    efectos = " ".join(TOOLS_CATALOG["vault_ai_decision"].get("side_effects", []))
    assert "16_AI_Governance" in efectos
    assert "03_Decisions" not in efectos


def test_el_filtro_documentado_de_pattern_list_es_un_tipo_que_existe():
    """Un `--type` que no existe no falla: filtra a cero patrones en silencio."""
    from vault_pattern_save import PATTERN_TYPES

    for linea in TOOLS_CATALOG["vault_pattern_list"]["example"].splitlines():
        partes = shlex.split(linea)
        if "--type" in partes:
            assert partes[partes.index("--type") + 1] in PATTERN_TYPES, linea


def _fuera_del_esquema(nombre: str, linea: str, props: dict) -> list:
    """Flags y valores de una línea de ejemplo que el esquema publicado rechaza."""
    from vault_mcp_catalog import PARAMS_FIJADOS_POR_LA_SESION

    partes, malos, i = shlex.split(linea), [], 2
    while i < len(partes):
        if not partes[i].startswith("--"):
            i += 1
            continue
        flag = partes[i][2:].split("=")[0]
        j = i + 1
        while j < len(partes) and not partes[j].startswith("--"):
            j += 1
        clave = next((c for c in (flag, flag.replace("-", "_")) if c in props), None)
        if clave is None:
            if flag not in PARAMS_FIJADOS_POR_LA_SESION:
                malos.append(f"{nombre}: --{flag} no está en el esquema")
        else:
            esquema = props[clave]
            enum = esquema.get("enum") or (esquema.get("items") or {}).get("enum")
            for valor in partes[i + 1:j]:
                if enum and valor not in [str(e) for e in enum]:
                    malos.append(f"{nombre}: --{flag} {valor!r} fuera de {enum}")
        i = j
    return malos


def test_ningun_ejemplo_usa_un_flag_o_un_valor_que_el_esquema_rechaza():
    """Toda línea `python …` de todo ejemplo, contra el esquema que se publica.

    El test de arriba ejecuta seis escritores y solo su primera línea. El banco
    de AP-37 (2026-10-17) ejecutó todas y destapó dos ejemplos que la propia
    tool rechaza: `vault_infra_map --location "us-east-1"` (las ubicaciones son
    `cloud-aws`, `homelab`…) y `vault_relation_add --relation_type
    "one-to-many"` (los tipos son `has_many`, `belongs_to`…). El esquema sale de
    argparse (AP-40), así que es lo que acepta la CLI y lo que valida el
    cliente MCP; contrastar con él no ejecuta nada.
    """
    publicado = json.loads((ROOT / "mcp" / "nodejs" / "tools-catalog.json")
                           .read_text(encoding="utf-8"))["tools"]
    malos = []
    for nombre, tool in sorted(TOOLS_CATALOG.items()):
        props = publicado.get(nombre, {}).get("inputSchema", {}).get("properties", {})
        for linea in (tool.get("example") or "").splitlines():
            if linea.startswith("python "):
                malos += _fuera_del_esquema(nombre, linea, props)
    assert not malos, "\n".join(malos)


def test_restore_no_documenta_una_vista_previa_que_no_existe():
    """AP-42, medido por `vault_noop_audit --ejecutado` (2026-10-17), que corre
    todas las líneas del ejemplo y no solo la primera, como el smoke: la
    segunda línea de `vault_restore` omitía `--confirm` y la ayuda prometía
    que así «solo muestra info sin restaurar». El servicio se niega a
    propósito (`CONFIRMACION_REQUERIDA`, sin default permisivo): no hay vista
    previa, y quien copiaba la línea recibía un error."""
    lineas = TOOLS_CATALOG["vault_restore"]["example"].splitlines()
    assert lineas and all("--confirm true" in l for l in lineas), lineas
    ayuda = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_restore.py"), "--help"],
        capture_output=True, text=True, encoding="utf-8", timeout=120).stdout
    assert "solo muestra info" not in ayuda, ayuda
    assert "--confirm false" not in ayuda, ayuda
