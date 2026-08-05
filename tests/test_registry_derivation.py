"""Invariantes derivadas del registro, no de literales congelados.

Generalización del patrón que destapó el hueco de AP-26..AP-30: aquel chequeo
esperaba `range(1, 26)` — un literal escrito una vez y nunca revisado — así que
dejó de ver los antipatrones nuevos en el momento en que el catálogo creció.

La regla que estos tests imponen: **lo esperado se calcula desde el registro**.
Ninguna afirmación de este archivo contiene un conteo ni un rango escrito a
mano. Si el registro crece, estos tests siguen siendo correctos; si el registro
tiene un hueco, fallan.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_mcp_catalog  # noqa: E402
import vault_registry  # noqa: E402
import vault_standard_upgrade as vsu  # noqa: E402
from vault_norms import NORM_CATALOG, STATUS_VOCAB  # noqa: E402


# ─── Catálogo de tools ───────────────────────────────────────────────────────


def test_toda_tool_del_catalogo_pertenece_a_un_grupo():
    """Sin esto, una tool puede existir y ser invisible en todo recorrido por grupos."""
    agrupadas = {t for tools in vault_mcp_catalog.GROUPS.values() for t in tools}
    huerfanas = sorted(set(vault_mcp_catalog.TOOLS_CATALOG) - agrupadas)
    assert not huerfanas, f"tools sin grupo: {huerfanas}"


def test_el_campo_group_coincide_con_la_clave_de_groups():
    """Los dos sistemas de nombres deben ser uno.

    Durante varias versiones convivieron dos vocabularios de grupo: la etiqueta
    de `TOOLS_CATALOG[tool]["group"]` ("Normas y Etiquetas", "Salud", "Vista
    proyecto"...) y la clave de `GROUPS` ("Normas", "Salud del Vault", "Vista
    del Proyecto"...). Cualquier recorrido que agrupara por el campo `group`
    producía grupos distintos que el que agrupaba por `GROUPS`, y ninguno de los
    dos fallaba — divergían en silencio. `GROUPS` manda: es lo que itera el
    tooling. El campo `group` es su reflejo.
    """
    pertenencia = {
        t: g for g, tools in vault_mcp_catalog.GROUPS.items() for t in tools
    }
    desalineadas = sorted(
        (nombre, spec.get("group"), pertenencia.get(nombre))
        for nombre, spec in vault_mcp_catalog.TOOLS_CATALOG.items()
        if spec.get("group") != pertenencia.get(nombre)
    )
    assert not desalineadas, (
        "tools cuyo campo `group` no es la clave de GROUPS que las contiene "
        f"(tool, declara, pertenece a): {desalineadas}"
    )


def test_ningun_grupo_referencia_una_tool_inexistente():
    fantasmas = sorted(
        {
            t
            for tools in vault_mcp_catalog.GROUPS.values()
            for t in tools
            if t not in vault_mcp_catalog.TOOLS_CATALOG
        }
    )
    assert not fantasmas, f"grupos que citan tools inexistentes: {fantasmas}"


def test_ninguna_tool_esta_en_dos_grupos():
    visto = {}
    duplicadas = []
    for grupo, tools in vault_mcp_catalog.GROUPS.items():
        for t in tools:
            if t in visto:
                duplicadas.append((t, visto[t], grupo))
            visto[t] = grupo
    assert not duplicadas, f"tools en más de un grupo: {duplicadas}"


def test_toda_tool_con_entry_point_python_tiene_su_script():
    """`script: ""` es legítimo (JS-native). Un script declarado que no existe, no."""
    faltantes = [
        (name, spec["script"])
        for name, spec in vault_mcp_catalog.TOOLS_CATALOG.items()
        if spec.get("script") and not (REPO_ROOT / "scripts" / spec["script"]).exists()
    ]
    assert not faltantes, f"scripts declarados e inexistentes: {faltantes}"


def test_toda_relacion_related_apunta_a_algo_que_existe():
    """`related` puede citar una tool del catálogo o un módulo interno.

    Lo que no puede citar es algo inexistente: eso es una referencia alucinada
    (AP-01) dentro del propio registro que sirve de fuente de verdad.
    """
    rotas = [
        (name, r)
        for name, spec in vault_mcp_catalog.TOOLS_CATALOG.items()
        for r in spec.get("related", [])
        if r not in vault_mcp_catalog.TOOLS_CATALOG
        and not (REPO_ROOT / "scripts" / f"{r}.py").exists()
    ]
    assert not rotas, f"related rotos: {rotas}"


# ─── Catálogo de normas ──────────────────────────────────────────────────────


def _numeros(prefijo):
    return sorted(
        int(n["code"].split("-", 1)[1])
        for n in NORM_CATALOG
        if n["code"].startswith(f"{prefijo}-") and n["code"].split("-", 1)[1].isdigit()
    )


def test_la_numeracion_de_cada_familia_es_contigua():
    """Un hueco significa una norma aplicada en código pero sin entrada canónica.

    Es exactamente lo que ocurrió con AP-26..AP-30: `vault_audit` las penalizaba
    desde v30 y `NORM_CATALOG` no las conocía.
    """
    for prefijo in ("AP", "PAT", "SP", "CN"):
        numeros = _numeros(prefijo)
        assert numeros, f"familia {prefijo} vacía"
        esperado = list(range(1, max(numeros) + 1))
        huecos = sorted(set(esperado) - set(numeros))
        assert not huecos, f"{prefijo} con huecos: {huecos}"


def test_ningun_codigo_de_norma_duplicado():
    codigos = [n["code"] for n in NORM_CATALOG]
    assert len(codigos) == len(set(codigos))


def test_ninguna_norma_tiene_enforcement_manual():
    """Regla no negociable del repo: `manual` no es enforcement, es una intención."""
    manuales = [n["code"] for n in NORM_CATALOG if n.get("enforcement") == "manual"]
    assert not manuales, f"normas con enforcement manual: {manuales}"


def test_status_vocab_no_esta_duplicado_como_literal_en_scripts():
    """`STATUS_VOCAB` es fuente única. Una copia literal envejece por su cuenta."""
    fuente = REPO_ROOT / "scripts" / "vault_norms.py"
    firma = set(STATUS_VOCAB)
    copias = []
    for path in (REPO_ROOT / "scripts").glob("vault_*.py"):
        if path == fuente:
            continue
        texto = path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"[\[\{]([^\[\]\{\}]{20,600}?)[\]\}]", texto, re.S):
            literales = set(re.findall(r"[\"']([a-z_]+)[\"']", m.group(1)))
            if firma.issubset(literales):
                copias.append(path.name)
                break
    assert not copias, (
        f"{copias} replican STATUS_VOCAB completo como literal: importarlo de "
        "vault_norms en vez de copiarlo"
    )


# ─── Secciones y migraciones ─────────────────────────────────────────────────


def test_toda_seccion_del_registro_esta_numerada():
    sin_numero = [s for s in vault_registry.standard_folders() if not s[:2].isdigit()]
    assert not sin_numero, f"secciones sin prefijo numérico: {sin_numero}"


def test_toda_seccion_es_alcanzable_por_un_vault_preexistente():
    """Añadir una sección al registro sin migración la deja inaccesible.

    Duplica deliberadamente el guard de test_standard_upgrade_path.py: es la
    invariante que más caro sale perder, y aquí se comprueba desde el registro
    de secciones en vez de desde el de migraciones.
    """
    creadas = {
        f.split("/")[0]
        for m in vsu.MIGRATIONS.values()
        for f in m.get("add_folders", [])
    }
    base = set(vsu.STANDARD_FOLDERS)
    inalcanzables = [
        s for s in vault_registry.standard_folders() if s not in base and s not in creadas
    ]
    assert not inalcanzables, (
        f"secciones sin ruta de migración: {inalcanzables} — un vault preexistente "
        "nunca las obtendría"
    )


def test_la_version_actual_es_la_ultima_del_orden():
    mayor = vsu.CURRENT_VERSION.split(".", 1)[0]
    assert vsu.VERSION_ORDER[-1] == mayor, (
        f"CURRENT_VERSION={vsu.CURRENT_VERSION} pero VERSION_ORDER termina en "
        f"{vsu.VERSION_ORDER[-1]}"
    )


# ─── Secciones: una sola fuente ──────────────────────────────────────────────


def test_ningun_modulo_declara_su_propia_lista_de_secciones():
    """`vault_registry.SECTIONS` es la única verdad sobre qué secciones hay.

    `vault_folder_registry` tenía la suya, congelada en 13 mientras el estándar
    ya iba por 22: las carpetas personalizadas dentro de las 9 secciones que
    faltaban eran invisibles para la detección y para la indexación. Un
    duplicado no falla al crearse — falla en silencio meses después, cuando la
    fuente real crece y la copia no.

    El chequeo es sobre el código: ningún módulo puede volver a escribir un
    literal con nombres de sección numerados.
    """
    canonicas = set(vault_registry.ORDERED_SECTIONS)

    import vault_folder_registry as vfr

    assert set(vfr.STANDARD_SECTIONS) == canonicas, (
        "vault_folder_registry.STANDARD_SECTIONS divergió del registro canónico"
    )

    # Un mapa `{"03_Decisions": "adr", ...}` con unas cuantas secciones es
    # legítimo: asocia un dato a la sección, no redefine cuáles hay. Lo que no
    # puede existir es una COPIA de la lista — un módulo que enumera casi todas
    # las secciones sin derivarlas. Ese es el que se queda atrás cuando el
    # registro crece, y es exactamente lo que le pasó a
    # `vault_folder_registry`: 13 de 22, en silencio, durante nueve secciones.
    patron = re.compile(r'["\'](?:0\d|1\d|2\d|99)_[A-Z][A-Za-z_]*["\']')
    exentos = {"vault_registry.py", "vault_standard_upgrade.py"}
    # Enumerar todas las secciones es legítimo cuando cada una lleva un valor
    # propio —el mapa sección→tipo de `vault_write`, el mapa sección→comando de
    # `vault_audit`—: eso no se puede derivar, porque el dato no está en el
    # registro. Lo que delata la deriva es la enumeración **incompleta**: casi
    # todas las secciones, y justo las últimas ausentes. Ese hueco es el que
    # nadie ve, porque no rompe nada — solo deja la sección nueva sin tratar.
    umbral = 0.8 * len(canonicas)
    culpables = {}

    for py in sorted((REPO_ROOT / "scripts").glob("vault_*.py")):
        if py.name in exentos:
            continue
        texto = py.read_text(encoding="utf-8", errors="ignore")
        if "from vault_registry import" in texto or "import vault_registry" in texto:
            continue
        nombres = {m.strip("\"'") for m in patron.findall(texto)} & canonicas
        if umbral <= len(nombres) < len(canonicas):
            culpables[py.name] = sorted(canonicas - nombres)

    assert not culpables, (
        "módulos que enumeran casi todas las secciones y se dejan algunas "
        f"fuera (derivar de vault_registry o completar el mapa): {culpables}"
    )
