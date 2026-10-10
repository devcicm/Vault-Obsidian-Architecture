"""AP-42 en la documentación: un comando publicado que no corre.

`AGENTS.md` publicaba, en su sección de comandos habituales, las dos formas de
medir la salud del vault:

    python scripts/vault_audit.py --root vault-sandbox
    python scripts/vault_quality_check.py --root vault-sandbox --min-score 0.7

Ninguna de las dos tools acepta `--root`. Un agente que copiaba el comando
—que es exactamente para lo que está esa sección— recibía
`error: unrecognized arguments: --root vault-sandbox` y perdía el turno. Y lo
contradecía la regla 1 del mismo fichero, tres pantallas más arriba: solo
cuatro tools aceptan `--root`, y el destino se fuerza con `VAULT_ROOT`.

Duró versiones porque nada lo comprobaba: el manifiesto, el catálogo y los
conteos tienen guard; los comandos de la documentación, no. Que el invisible
fuese justo el de la salud es lo que lo hace caro — nadie mide el vault a mano
para descubrir que la herramienta de medirlo no arranca.

La comprobación es estática (los `add_argument` declarados) y no ejecuta nada:
varios comandos documentados escriben en el vault.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_doc_sync as vds  # noqa: E402

TOOLS_DE_SALUD = ("vault_audit.py", "vault_quality_check.py")

import vault_grafo_import as gi  # noqa: E402


def test_ningun_comando_publicado_usa_un_flag_que_su_tool_rechaza():
    problemas = vds.comandos_publicados()
    assert problemas == [], "\n".join(p["detail"] for p in problemas)


def test_el_detector_esta_conectado_al_check():
    """Un detector que existe y no se llama es el mismo fallo con otra cara."""
    assert "commands_checked" in vds.scan()


def test_el_detector_ve_el_defecto_original():
    """Si se reintrodujese `--root` en un comando de salud, tiene que salir."""
    declarados = vds._flags_declarados(REPO_ROOT / "scripts" / "vault_audit.py")
    assert "--root" not in declarados, (
        "si vault_audit pasara a aceptar --root, este test sobra; "
        "revisa la regla 1 de AGENTS.md antes de borrarlo"
    )


@pytest.mark.parametrize("script", TOOLS_DE_SALUD)
def test_la_tool_de_salud_arranca_tal_y_como_se_documenta(script):
    """Contra el flag, no contra el parser: se ejecuta de verdad.

    El guard es estático; este test es el contraste. Un `add_argument` que el
    regex vea pero que argparse no acepte pasaría el guard y moriría aquí.
    """
    linea = _comando_documentado(script)
    proc = subprocess.run(
        [sys.executable, *linea], capture_output=True, text=True,
        encoding="utf-8", errors="replace", cwd=str(REPO_ROOT), timeout=300,
    )
    assert "unrecognized arguments" not in (proc.stderr or ""), proc.stderr
    assert proc.returncode == 0, proc.stderr[-500:]


def _comando_documentado(script: str) -> list:
    """Extrae de AGENTS.md el comando que se publica para esa tool.

    No se copia aquí: se lee del documento. Copiarlo dejaría el test verde
    mientras la documentación se rompe, que es el defecto que este fichero
    cierra, cometido una segunda vez.
    """
    texto = (REPO_ROOT / "AGENTS.md").read_bytes().decode("utf-8")
    for linea in texto.splitlines():
        for m in vds.RE_COMANDO.finditer(linea):
            if m.group(1).endswith(script):
                # RE_COMANDO ya no captura el prefijo `scripts/` (admite la
                # forma corta que usa `scripts/README.md`): se ancla aquí.
                return [str(REPO_ROOT / "scripts" / m.group(1)),
                        *m.group(2).split()]
    pytest.fail(f"AGENTS.md ya no documenta ningún comando para {script}")


def test_el_documento_de_comandos_que_el_estandar_genera_esta_en_el_alcance():
    """v40.4 midió los docs escritos a mano, no la copia que el toolkit reparte.

    `vault_section_index` escribe `<vault>/00_System/vault-commands.md` en **cada
    vault que el estándar crea**, y ahí publicaba `vault_restore.py --name`, un
    flag que la tool no declara. El mismo defecto que este fichero cierra, en el
    único sitio donde no cuesta un turno de agente sino todos los turnos de todos
    los vaults creados desde entonces.
    """
    assert "vault-sandbox/00_System/vault-commands.md" in vds.DOCS_CON_COMANDOS
    assert (REPO_ROOT / "vault-sandbox/00_System/vault-commands.md").exists()


def test_el_generador_no_escribe_un_flag_que_su_tool_rechaza():
    """Contra la fuente, no contra la copia.

    Tener el documento generado dentro de `DOCS_CON_COMANDOS` solo muerde si
    alguien regenera el fichero del sandbox. El defecto vive en el literal del
    generador, así que es ahí donde se mide: un `--flag` nuevo en esa cadena
    tiene que fallar el día que se escribe, no el día que se copia.
    """
    fuente = gi.codigo_de(REPO_ROOT / "scripts" / "vault_section_index.py").read_text(
        encoding="utf-8"
    )
    revisados = 0
    for m in vds.RE_COMANDO.finditer(fuente):
        script = REPO_ROOT / "scripts" / m.group(1)
        assert script.exists(), f"el generador publica {m.group(1)}, que no existe"
        declarados = vds._flags_declarados(script)
        for flag in vds.RE_FLAG_USADO.findall(m.group(2)):
            assert flag in declarados, f"{m.group(1)} no acepta {flag}"
        revisados += 1
    assert revisados, "el generador ya no publica comandos; este test sobra"


def test_el_audit_publica_la_lectura_que_discrimina():
    """El comando de salud tiene que devolver la lectura nueva, no solo el score.

    `healthScore` satura a 0 en el propio sandbox; si el comando documentado
    solo trajese ese número, seguiría sin medir aunque arrancase.
    """
    import json

    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "vault_audit.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO_ROOT), timeout=300,
    )
    env = json.loads(proc.stdout)
    assert "healthIndex" in env and "healthProfile" in env
    assert set(env["healthProfile"]) == set(
        __import__("vault_audit").FAMILIAS_DE_SALUD
    )
    # El desglose no puede salir vacío mientras el score no sea 100: sería
    # AP-37, un campo que se publica y nunca se llena.
    if env["healthScore"] < 100:
        assert env["penalties"], "healthScore penalizado pero penalties vacío"
        assert sum(p["penalty"] for p in env["penalties"]) == 100 - env["healthScore"] \
            or env["healthScore"] == 0


def _comandos_de(tmp_path, monkeypatch, texto: str) -> list:
    doc = tmp_path / "doc.md"
    doc.write_bytes(texto.encode("utf-8"))
    monkeypatch.setattr(vds, "DOCS_CON_COMANDOS", (str(doc),))
    return [p["detail"] for p in vds.comandos_publicados()]


def test_ap42_un_flag_tras_una_continuacion_se_mide(tmp_path, monkeypatch):
    """v41.3: el shell une la línea que acaba en barra con la siguiente.

    Medir línea a línea dejaba sin comprobar todo flag de la segunda línea en
    adelante: nueve ejemplos de `scripts/README.md` estaban rotos y en verde.
    """
    texto = "python vault_audit.py \\\n  --no-existe 1\n"
    assert any("--no-existe" in d for d in _comandos_de(tmp_path, monkeypatch, texto))


def test_ap42_un_valor_entre_comillas_no_oculta_los_flags_siguientes(tmp_path, monkeypatch):
    """`--title "Q1 2026 Test Plan"` cortaba la captura en el primer espacio."""
    texto = 'python vault_qa_save.py --title "Q1 2026 Test Plan" --qa_type test-plan\n'
    assert any("--qa_type" in d for d in _comandos_de(tmp_path, monkeypatch, texto))


def test_ap42_el_negativo_de_un_flag_booleano_se_acepta(tmp_path, monkeypatch):
    """`--no-reversible` lo declara `BooleanOptionalAction`, no un `add_argument`."""
    texto = "python vault_ai_decision.py --no-reversible\n"
    assert _comandos_de(tmp_path, monkeypatch, texto) == []


def test_ap42_las_lineas_logicas_conservan_el_numero_de_la_primera():
    assert vds.lineas_logicas("a \\\nb\nc") == [(1, "a  b"), (3, "c")]


# Las secciones que v41.3 reescribió. El guard es estático: ve flags, no
# valores. `--priority high`, `--status passed` o `--coverage-target "80%"`
# pasaban el guard y morían en argparse; solo ejecutarlos los distingue.
EJEMPLOS_EJECUTADOS = (
    "vault_runbook_save", "vault_infra_save", "vault_env_save",
    "vault_project_status", "vault_project_overview", "vault_requirement_save",
    "vault_test_save", "vault_qa_save", "vault_ai_decision",
)


def _ejemplos_del_readme(tool: str) -> list:
    import re
    import shlex

    texto = (REPO_ROOT / "scripts" / "README.md").read_bytes().decode("utf-8")
    salida = []
    for bloque in re.findall(r"```bash\n(.*?)```", texto, re.S):
        for _, linea in vds.lineas_logicas(bloque):
            m = re.match(r"\s*python\s+(?:scripts/)?([a-z0-9_]+)\.py(.*)", linea)
            if m and m.group(1) == tool:
                salida.append(shlex.split(m.group(2)))
    return salida


@pytest.mark.parametrize("tool", EJEMPLOS_EJECUTADOS)
def test_ap42_los_ejemplos_del_readme_corren_en_un_vault(tool, tmp_path):
    import json
    import os

    entorno = dict(os.environ, VAULT_ROOT=str(tmp_path), PYTHONIOENCODING="utf-8")

    def correr(*args):
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / args[0]), *args[1:]],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(tmp_path), env=entorno, timeout=300,
        )

    assert correr("vault_init.py", "--no-audit").returncode == 0
    assert correr("vault_project.py", "--add", "mi-api").returncode == 0
    ejemplos = _ejemplos_del_readme(tool)
    assert ejemplos, f"scripts/README.md ya no publica ejemplos de {tool}"
    for args in ejemplos:
        proc = correr(f"{tool}.py", *args)
        assert proc.returncode == 0, (args, proc.stdout[-400:], proc.stderr[-400:])
        assert json.loads(proc.stdout)["ok"] is True
