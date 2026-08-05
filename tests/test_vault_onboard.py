"""`vault_onboard` — poblar un vault desde un proyecto que no tenía ninguno.

La tool existía desde hacía versiones, estaba documentada en el manifiesto y no
se había ejecutado nunca en CI: AP-42 literal. Al correrla salieron nueve
defectos, y el peor no era ninguno de ellos por separado — era que las 54 notas
que producía nacían reprobadas por `vault_audit`, o sea que el estándar
suspendía lo que su propia tool acababa de escribir.

**Por eso estos tests afirman sobre el VAULT RESULTANTE y no sobre `ok: true`.**
Un `ok: true` solo dice que la tool terminó. Lo que hay que saber es si lo que
escribió pasa el criterio del consumidor —el audit, las normas, Mermaid—, que es
AP-44 aplicado al propio test: comprobar el resultado con el criterio de quien lo
va a usar, no con el de quien lo generó.

El criterio de aceptación, en una frase: **un vault recién onboardeado no
necesita sanación.**
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


# ── Proyecto sintético con git real ──────────────────────────────────────────


def _git(cwd, *args):
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )


@pytest.fixture(scope="module")
def proyecto(tmp_path_factory):
    """Un repo de verdad, no un mock.

    Con un mock de `git log` el test comprobaría que la tool sabe leer lo que el
    test le da — que es la verificación autoconsistente de AP-44. Aquí git se
    ejecuta de verdad, así que lo que se prueba es la lectura real del historial.
    """
    p = tmp_path_factory.mktemp("proyecto-sin-vault")
    (p / "src").mkdir()
    (p / "src" / "userService.ts").write_text(
        "export class UserService {\n  // TODO: cachear\n  find(id: string) { return id }\n}\n",
        encoding="utf-8",
    )
    (p / "src" / "user-service.ts").write_text(
        "// duplicado por naming: misma nota para Obsidian\nexport const x = 1\n",
        encoding="utf-8",
    )
    (p / "src" / "authRepository.ts").write_text(
        "export class AuthRepository { get() {} }\n", encoding="utf-8"
    )
    (p / "package.json").write_text(
        json.dumps(
            {
                "name": "demo-api",
                "version": "1.0.0",
                "description": "API de demostración",
                "scripts": {"build": "tsc", "test": "vitest"},
                "dependencies": {"express": "^4.0.0"},
            }
        ),
        encoding="utf-8",
    )
    (p / "README.md").write_text(
        "﻿# demo-api\n\nUna API pequeña.\n\n## Arquitectura\n\n"
        "Capas: controlador, servicio, repositorio.\n\n## Instalación\n\nnpm i\n",
        encoding="utf-8",
    )

    _git(p, "init", "-b", "main")
    _git(p, "config", "user.email", "t@example.com")
    _git(p, "config", "user.name", "Tester")
    _git(p, "add", "-A")
    # Un asunto con el separador que usa el parser de commits: si `|` parte mal
    # la línea, el autor sale contaminado y aparece un contribuidor inventado.
    _git(p, "commit", "-m", "feat: arquitectura en capas | validada en revisión")
    _git(p, "tag", "v1-genesis")
    (p / "src" / "orderController.ts").write_text("export class C {}\n", encoding="utf-8")
    _git(p, "add", "-A")
    _git(p, "commit", "-m", "wip")  # asunto sin contenido: no debe generar ADR
    return p


@pytest.fixture(scope="module")
def vault(tmp_path_factory, proyecto):
    """Corre `vault_init` + `vault_onboard` en un vault nuevo y devuelve la ruta."""
    v = tmp_path_factory.mktemp("vault-destino")
    env = {
        **os.environ,
        "VAULT_ROOT": str(v),
        "PYTHONIOENCODING": "utf-8",
        "VAULT_TOOL_TIMEOUT": "600",
    }
    subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_init.py")],
        env=env, capture_output=True, timeout=600,
    )
    r = subprocess.run(
        [
            sys.executable, str(SCRIPTS / "vault_onboard.py"),
            "--project", "demo-api", "--path", str(proyecto),
        ],
        env=env, capture_output=True, text=True, timeout=600,
    )
    salida = json.loads(r.stdout)
    assert salida.get("ok"), salida
    return v, salida


def _correr(script, vault_root, *args):
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        env={**os.environ, "VAULT_ROOT": str(vault_root),
             "PYTHONIOENCODING": "utf-8", "VAULT_TOOL_TIMEOUT": "600"},
        capture_output=True, text=True, timeout=600,
    )
    return json.loads(r.stdout)


# ── El criterio de aceptación ────────────────────────────────────────────────


def test_el_vault_resultante_no_necesita_sanacion(vault):
    """La afirmación central. Si esto falla, el generador no está arreglado."""
    v, _ = vault
    violaciones = _correr("vault_norms.py", v, "--audit", "--root", str(v)).get(
        "violations", []
    )
    assert not violaciones, (
        "un vault recién onboardeado ya viola normas del estándar que lo creó: "
        + json.dumps(violaciones[:5], ensure_ascii=False, indent=2)
    )


def test_ninguna_nota_nace_con_deuda_de_metadatos(vault):
    """Las 54 notas del primer onboard nacían todas en `missingType`.

    Es el fallo de `vault_init` con sus primers repetido a escala: el estándar
    reprobando lo que su propio write path acaba de escribir.
    """
    v, _ = vault
    issues = _correr("vault_audit.py", v).get("issues", {})
    for campo in ("missingType", "missingStatus", "missingTags", "missingCIA"):
        assert not issues.get(campo), f"{campo}: {issues[campo][:5]}"


def test_los_diagramas_que_se_escriben_dibujan(vault):
    """AP-44: se valida con la gramática de Mermaid, no con la fe del generador."""
    v, _ = vault
    r = _correr("vault_mermaid_check.py", v, "--json")
    assert not r.get("errors"), r.get("errors")
    assert not [d for d in r.get("diagrams", []) if not d.get("valid", True)], r


# ── Los defectos, uno a uno ──────────────────────────────────────────────────


def test_no_se_escriben_notas_sin_evidencia(vault):
    """AP-45. Lo omitido se declara en la salida: el hueco nombrado es útil."""
    v, salida = vault
    for nota in (v).rglob("*.md"):
        cuerpo = nota.read_text(encoding="utf-8").split("---", 2)[-1]
        import vault_lib
        from vault_norms import _cuerpo_sin_marcadores

        if nota.parent.name in ("18_Bugs", "19_Audits", "20_Quarantine"):
            continue
        if "template" in nota.read_text(encoding="utf-8")[:400] or nota.stem == "index":
            continue
        assert vault_lib.extract_wikilinks(cuerpo) or _cuerpo_sin_marcadores(cuerpo), (
            f"{nota.name} no afirma nada ni enlaza con nada"
        )
    assert "skipped_no_evidence" in salida


def test_el_commit_sin_asunto_util_no_produce_adr(vault):
    """`wip` no es una decisión. Cinco ADRs llamados `adr-00N-retroactivo` no
    se distinguen entre sí, que es AP-07 por la vía del nombre."""
    v, _ = vault
    adrs = list((v / "03_Decisions").glob("adr-*.md"))
    assert not [a for a in adrs if a.stem.endswith("retroactivo")], (
        "un ADR cuyo nombre entero es su número no nombra la decisión"
    )


def test_el_separador_del_log_no_inventa_contribuidores(vault):
    """El commit del fixture lleva un `|` en el asunto. Con `split(maxsplit=3)`
    el autor salía como `validada en revisión|Tester`."""
    v, salida = vault
    assert salida["git_history"]["contributors"] == ["Tester"], salida["git_history"][
        "contributors"
    ]


def test_los_modulos_homonimos_producen_una_sola_nota(vault):
    """`userService.ts` y `user-service.ts` son dos ficheros y UNA nota para
    Obsidian, que resuelve por nombre normalizado."""
    v, _ = vault
    stems = [p.stem for p in (v / "11_Code").rglob("*.md") if p.stem != "index"]
    from vault_io import normalize_stem

    normalizados = [normalize_stem(s) for s in stems]
    assert len(normalizados) == len(set(normalizados)), stems


def test_el_bom_del_readme_no_viaja_al_frontmatter(vault):
    """El README del fixture empieza por BOM. Con `utf-8` a secas se colaba
    como primer carácter de la descripción."""
    v, salida = vault
    assert "﻿" not in json.dumps(salida, ensure_ascii=False)
    for nota in v.rglob("*.md"):
        assert "﻿" not in nota.read_text(encoding="utf-8"), nota.name


def test_el_tope_de_historia_se_declara_cuando_se_alcanza(proyecto, tmp_path):
    """`total_commits: 500` con `warnings: []` presentaba un parámetro de la
    invocación como un hecho del proyecto."""
    r = subprocess.run(
        [
            sys.executable, str(SCRIPTS / "vault_onboard.py"),
            "--project", "demo-api", "--path", str(proyecto),
            "--max-commits", "1", "--dry-run",
        ],
        env={**os.environ, "VAULT_ROOT": str(tmp_path), "PYTHONIOENCODING": "utf-8",
             "VAULT_TOOL_TIMEOUT": "600"},
        capture_output=True, text=True, timeout=600,
    )
    salida = json.loads(r.stdout)
    assert any("max-commits" in w for w in salida["warnings"]), salida["warnings"]


def test_las_secciones_dirigidas_por_eventos_quedan_vacias_y_se_dice(vault):
    """Poblarlas al arrancar sería inventar bugs y auditorías que no han pasado."""
    v, salida = vault
    declaradas = salida["sections_left_empty_by_design"]
    for seccion in ("18_Bugs", "19_Audits", "20_Quarantine"):
        assert seccion in declaradas
        notas = [p for p in (v / seccion).rglob("*.md") if p.stem != "index"]
        assert not notas, f"{seccion} debería estar vacía: {notas}"


def test_las_secciones_nuevas_se_pueblan_cuando_hay_evidencia(vault):
    """`16_AI_Governance` y `17_Preferences` no se tocaban: 12 de 22 secciones."""
    v, _ = vault
    assert list((v / "17_Preferences").glob("*.md")), (
        "el proyecto declara lenguaje y gestor de paquetes: hay contexto estable "
        "que registrar"
    )
