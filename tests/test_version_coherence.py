"""La versión del estándar se declara en cinco sitios. Deben decir lo mismo.

El plan de consolidación pedía `vault_version --check` para esto. Esa tool no
existe y nunca existió: la referencia venía de una verificación escrita a mano.
No se crea una tool nueva — no hay nada que ejecutar contra un vault, es un
invariante del propio repo, y su sitio es la suite.

`CURRENT_VERSION` manda: es lo que lee `vault_standard_upgrade` para decidir si
un vault necesita migración. Los otros cuatro son su reflejo, y cuando uno se
queda atrás el vault migra a una versión que la documentación no describe.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_standard_upgrade as vsu  # noqa: E402

VERSION = vsu.CURRENT_VERSION  # "v39.0"
NUMERO = VERSION.lstrip("v")  # "39.0"


def test_el_formato_de_current_version_es_canonico():
    assert re.fullmatch(r"v\d+\.\d+", VERSION), VERSION


def test_el_banner_del_manifiesto_coincide():
    cabecera = (ROOT / "vault-obsidian-architecture.md").read_text(
        encoding="utf-8"
    )[:2000]
    m = re.search(r"^\*\*Versión:\*\* (v[\d.]+)", cabecera, re.M)
    assert m, "no se encontró el banner de versión en el manifiesto"
    assert m.group(1) == VERSION


def test_el_badge_del_readme_coincide():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(r"img\.shields\.io/badge/version-(v[\d.]+)-", readme)
    assert m, "no se encontró el badge de versión en README.md"
    assert m.group(1) == VERSION


def test_pyproject_coincide():
    m = re.search(
        r'^version = "([\d.]+)"',
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        re.M,
    )
    assert m, "no se encontró version en pyproject.toml"
    assert m.group(1) == NUMERO


def test_el_vault_de_pruebas_esta_migrado_a_la_version_actual():
    """Si el sandbox se queda atrás, los guards corren contra un vault viejo."""
    estado = json.loads(
        (ROOT / "vault-sandbox/00_System/standard-version.json").read_text(
            encoding="utf-8"
        )
    )
    assert estado["applied_version"] == VERSION


def test_la_version_tiene_entrada_de_migracion_registrada():
    mayor = VERSION.split(".")[0]  # "v39"
    assert mayor in vsu.MIGRATIONS, f"{mayor} sin entrada en MIGRATIONS"
    assert mayor in vsu.VERSION_ORDER, f"{mayor} fuera de VERSION_ORDER"
    assert vsu.VERSION_ORDER[-1] == mayor, (
        f"VERSION_ORDER termina en {vsu.VERSION_ORDER[-1]!r} y CURRENT_VERSION "
        f"es {VERSION!r}: una migración posterior quedaría sin aplicar"
    )


def test_ningun_test_compara_contra_la_version_corriente_escrita_a_mano():
    """AP-47 dentro de la suite: una cifra a mano que caduca en el bump.

    `test_versionado_consumidores` afirmaba `"--to v40.2" in env["message"]`.
    Era cierto, pasaba, y se rompió sola al subir a v40.3 — no porque el código
    empeorase, sino porque el test llevaba escrita una versión que ya no era la
    corriente. Ese fallo es barato cuando lo caza el bump y caro cuando alguien
    lo "arregla" actualizando el literal: al siguiente vuelve.

    Un literal de versión **histórica** sí es legítimo: el `introduced_version`
    de una norma es un hecho del pasado, y fijarlo es justamente lo correcto.
    Lo que no puede aparecer es la versión de hoy, porque hoy dura una versión.
    """
    culpables = []
    for fichero in sorted(Path(__file__).parent.glob("test_*.py")):
        if fichero.name == Path(__file__).name:
            continue  # este fichero nombra la versión para comprobarla
        fuente = fichero.read_bytes().decode("utf-8", "replace")
        for numero, linea in enumerate(fuente.splitlines(), 1):
            sin_comentario = linea.split("#", 1)[0]
            if f'"{VERSION}"' in sin_comentario or f"'{VERSION}'" in sin_comentario:
                culpables.append(f"{fichero.name}:{numero}: {linea.strip()}")
    assert not culpables, (
        "la versión corriente está escrita a mano en la suite; derívala de "
        "`vault_standard_upgrade.CURRENT_VERSION`:\n" + "\n".join(culpables)
    )


def test_el_banner_de_la_cli_coincide():
    """`cli/README.md` publicaba v39.0 con el estándar seis versiones por delante.

    Ningún guard lo miraba: `vault_doc_counts` vigila cifras, no versiones, y
    los tests de coherencia solo cubrían manifiesto, badge y `pyproject`. El
    banner de la CLI es lo primero que lee quien la usa.
    """
    texto = (ROOT / "cli" / "README.md").read_text(encoding="utf-8")
    m = re.search(r"\*\*(v\d+\.\d+) ", texto)
    assert m, "no se encontró el banner de versión en cli/README.md"
    assert m.group(1) == VERSION


# ---------------------------------------------------------------------------
# v40.32 — el sexto sitio, que eran todos los demás.
#
# Los cinco tests de arriba miden los cinco sitios que alguien recordó listar.
# `docs/SKILLS.md` decía «`CURRENT_VERSION` actual: **v39.3**» con el estándar
# en v40.31: veintiocho versiones de retraso en el documento que a los agentes
# les describe qué capacidades tiene el vault. No falló nada — el alcance
# declarado de este fichero («la versión se declara en cinco sitios») era más
# ancho que el conjunto de sitios donde de verdad se escribe, y el hueco
# devolvía verde.
#
# Es el mismo defecto que `vault_produccion` nombra, cometido dentro del test
# que existe para impedirlo. Por eso el barrido no lleva lista: recorre.

#: Solo la forma que **afirma vigencia**: un nombre de versión, un conector de
#: igualdad (`:` o `es`) y el número, sin nada en medio.
#:
#: El primer intento fue laxo —cualquier `v\d+\.\d+` a menos de 80 caracteres de
#: la palabra «versión»— y marcó tres sitios legítimos: «hoja del núcleo **desde**
#: v40.28» en `CLAUDE.md` y dos entradas de changelog que citan bugs antiguos.
#: Eso es historia, no una afirmación de qué versión corre hoy, y un guard que
#: la marca acaba desactivado. La lección ya está escrita en
#: `vault_doc_counts.COUNTED_FACTS`, donde el patrón de `scripts` exige la coma
#: por este mismo motivo: preferir no ver un sitio a ver uno que no lo es.
#: El adorno de markdown —backticks, negritas— va entre los dos, y la primera
#: versión estricta no lo contemplaba: pasaba en verde **sin cazar el caso para
#: el que se escribió**, porque el original decía «`CURRENT_VERSION` actual:» con
#: el backtick justo donde el patrón esperaba un espacio. Un guard verde que no
#: ve su propio motivo es AP-44 en estado puro, y por eso el test de abajo se
#: verifica contra la cadena histórica antes de creerse nada.
_ADORNO = r"[`*_\s]*"

VERSIONES_EN_DOCS = re.compile(
    r"(?:CURRENT_VERSION|[Vv]ersión (?:vigente|actual|del estándar))"
    + _ADORNO + r"(?:actual|vigente)?" + _ADORNO
    + r"(?:es|:|=)" + _ADORNO + r"v(\d+\.\d+)"
)

#: La cadena exacta que estuvo veintiocho versiones desfasada en `docs/SKILLS.md`.
#: Se conserva como fixture, no como comentario: un ejemplo que no se ejecuta no
#: prueba nada.
CASO_HISTORICO = "- vault-spec >= v36.0 (`CURRENT_VERSION` actual: **v39.3**)"


def _docs_del_repo():
    """Todo markdown del repo salvo el vault de pruebas, lo archivado y `_datasets/`.

    `_datasets/` queda fuera por dos razones que se refuerzan: es material de
    vaults ajenos que este repo no generó —medirlo con nuestro criterio sería
    lo contrario de la regla 7— y está fuera de git a propósito. Las versiones
    que ahí se afirmen son del dueño de ese vault, no nuestras.

    El manifiesto sí entra: su changelog cita versiones antiguas, pero como
    historia (`### v40.30 — …`), nunca afirmando cuál es la vigente, y el patrón
    de arriba solo mira la forma que afirma.
    """
    excluidos = (".git", "vault-sandbox", "node_modules", ".venv",
                 "_archived", "_datasets", "_datasets-reports", "_backups-builderx")
    return [
        p for p in sorted(ROOT.rglob("*.md"))
        if not any(x in p.parts for x in excluidos)
    ]


def test_ningun_documento_afirma_una_version_vigente_desfasada():
    """Una versión escrita a mano en prosa es AP-47, y envejece callada.

    La cura no es actualizarla: es no escribirla. Un documento que necesita
    nombrar la versión vigente apunta a `vault_version.CURRENT_VERSION` —que es
    su dueño— en vez de copiarla, igual que `docs/SKILLS.md` hace desde v40.32.
    """
    culpables = []
    for ruta in _docs_del_repo():
        texto = ruta.read_text(encoding="utf-8", errors="replace")
        for m in VERSIONES_EN_DOCS.finditer(texto):
            if m.group(1) != NUMERO:
                linea = texto[: m.start()].count("\n") + 1
                culpables.append(
                    f"{ruta.relative_to(ROOT).as_posix()}:{linea}: "
                    f"afirma v{m.group(1)}, vigente {VERSION}"
                )
    assert not culpables, (
        "versión vigente escrita a mano y desfasada. No la actualices: "
        "quítala y apunta a `vault_version.CURRENT_VERSION`, que es su dueño.\n  "
        + "\n  ".join(culpables)
    )


def test_el_barrido_caza_el_caso_que_lo_motivo():
    """Sin esto, el test de arriba puede estar verde por no mirar bien.

    Es la trampa que este repo llama AP-44: verificar con el criterio propio.
    Un barrido que no encuentra el defecto documentado no está limpio — está
    ciego, y las dos cosas se leen igual desde fuera.
    """
    hallado = VERSIONES_EN_DOCS.findall(CASO_HISTORICO)
    assert hallado == ["39.3"], (
        f"el patrón no ve el caso histórico: {hallado!r}. Un guard que no caza "
        "su propio motivo no protege de nada."
    )


def test_el_barrido_no_marca_una_mencion_historica():
    """La otra mitad: no marcar lo que legítimamente cita una versión pasada.

    Un guard con falsos positivos se desactiva, y entonces no protege tampoco.
    Estas tres cadenas son reales del repo y las tres deben pasar limpias.
    """
    historicas = [
        "`vault_version.CURRENT_VERSION` — hoja del núcleo desde v40.28.",
        "la versión del estándar decía «v19 → v20» cuando el registro traía otra",
        "### v40.30 — 2026-08-16 `git: b03e968`",
    ]
    for texto in historicas:
        assert not VERSIONES_EN_DOCS.findall(texto), (
            f"falso positivo sobre una mención histórica: {texto!r}"
        )
