"""Distribución de `vault_migrate_docs`: dónde aterriza y qué llega entero.

Dos defectos reales, encontrados al migrar la documentación de un proyecto ajeno
(FastApi NetCore) antes de onboardearlo:

1. El fichero acabó en `10_Migrated/10_Migrated/indirect/`. El clasificador
   devuelve rutas relativas a la RAÍZ del vault y la distribución las componía
   bajo `10_Migrated/`. Para los destinos que no son de migración
   (`03_Decisions`, `07_Knowledge/apis`) el efecto es peor que un segmento
   repetido: la nota se queda enterrada justo en la carpeta de la que la
   distribución existe para sacarla.
2. Era la única nota `missingFrontmatter` del vault. La escritura cortaba por
   `split("\\n", 8)` y se quedaba con las 7 primeras líneas: frontmatter sin
   `---` de cierre y cuerpo entero perdido. El generador fallaba la auditoría
   de su propio estándar porque nadie releía lo que escribía (AP-44).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"


def _correr(script, vault_root, *args):
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        env={
            **os.environ,
            "VAULT_ROOT": str(vault_root),
            "PYTHONIOENCODING": "utf-8",
            "VAULT_TOOL_TIMEOUT": "600",
        },
        capture_output=True,
        text=True,
        # El hijo emite UTF-8 (`PYTHONIOENCODING`); sin decirlo aquí, el padre
        # decodifica con la codificación local —cp1252 en Windows— y cualquier
        # acento de la salida revienta la lectura antes de llegar al assert.
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    assert r.stdout, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module")
def migrado(tmp_path_factory):
    """Un vault inicializado y una carpeta de docs con acentos y cuerpo real."""
    base = tmp_path_factory.mktemp("migrate")
    vault = base / "vault"
    vault.mkdir()
    docs = base / "docs"
    docs.mkdir()

    (docs / "Configuración del API.md").write_text(
        "# Configuración del API\n\n"
        "El servidor expone endpoints REST sobre HTTP. La configuración usa\n"
        "JSON y variables de entorno; el deploy va en Docker sobre Linux.\n\n"
        "## Índice de rutas\n\n"
        "- `/health` — comprobación del server\n"
        "- `/api/v1/items` — CRUD contra la database\n\n"
        "Este párrafo es el final del cuerpo y tiene que sobrevivir al viaje.\n",
        encoding="utf-8",
    )

    _correr("vault_init.py", vault)
    # AP-63: `--project demo` resuelve contra el registro; se da de alta.
    _correr("vault_project.py", vault, "--add", "demo")
    r = _correr(
        "vault_migrate_docs.py",
        vault,
        "--source_path",
        str(docs),
        "--project",
        "demo",
        "--dry_run",
        "false",
    )
    assert r["ok"], r
    return vault, r


def _nota_distribuida(vault, resultado):
    assert resultado["distributedFiles"], resultado
    return vault / resultado["distributedFiles"][0]["destPath"]


def test_el_segmento_de_seccion_no_se_duplica(migrado):
    vault, r = migrado
    for d in r["distributedFiles"]:
        assert "10_Migrated/10_Migrated" not in d["destPath"].replace("\\", "/")
        assert "10_Migrated\\10_Migrated" not in d["destPath"]


def test_la_nota_aterriza_donde_dice_el_informe(migrado):
    """`destPath` tiene que ser verdad en el disco, no solo en el JSON."""
    vault, r = migrado
    assert _nota_distribuida(vault, r).exists()


def test_el_frontmatter_cierra_y_parsea(migrado):
    vault, r = migrado
    texto = _nota_distribuida(vault, r).read_text(encoding="utf-8")
    assert texto.startswith("---\n")
    fin = texto.find("\n---", 3)
    assert fin != -1, "el bloque de frontmatter nunca cierra"
    datos = yaml.safe_load(texto[4:fin])
    assert isinstance(datos, dict)
    for clave in ("title", "type", "status", "id"):
        assert datos.get(clave), f"falta {clave}"


def test_el_cuerpo_llega_entero(migrado):
    """El corte por líneas se llevaba el documento por delante."""
    vault, r = migrado
    texto = _nota_distribuida(vault, r).read_text(encoding="utf-8")
    assert "Este párrafo es el final del cuerpo" in texto
    assert "/api/v1/items" in texto


def test_distributed_to_apunta_al_destino_real(migrado):
    vault, r = migrado
    nota = _nota_distribuida(vault, r)
    texto = nota.read_text(encoding="utf-8")
    fin = texto.find("\n---", 3)
    datos = yaml.safe_load(texto[4:fin])
    assert datos["distributedTo"], "distributedTo quedó vacío"
    assert nota.name in str(datos["distributedTo"])


def test_el_nombre_de_fichero_translitera_los_acentos(migrado):
    """Mismo slug canónico que el resto del estándar (ver test_slug_canonico)."""
    vault, r = migrado
    nombre = _nota_distribuida(vault, r).name
    assert nombre.isascii(), nombre
    assert nombre.startswith("configuracion-del-api")


def test_el_vault_migrado_no_nace_con_deuda_de_metadatos(migrado):
    """El criterio de aceptación, con el auditor y no con el propio."""
    vault, _ = migrado
    a = _correr("vault_audit.py", vault)
    assert a["issues"].get("missingFrontmatter", []) == []
    assert a["issues"].get("missingType", []) == []


def test_las_copias_se_quedan_en_la_carpeta_de_migracion(migrado):
    """La migración no reparte copias por el vault.

    Medido el 2026-11-04 al migrar el proyecto GESTION: los documentos
    clasificados como "directos" salían a la sección que el heurístico
    adivinaba (`07_Knowledge/apis/`, `09_Infrastructure/services/`), así que
    el mismo documento acababa en dos sitios y hubo que limpiar 7 duplicados
    y 15 stubs a mano. Ahora lo que migra vive en `10_Migrated/` y la sección
    detectada es una sugerencia del informe: decidir dónde vive un documento
    es de quien migra, no del clasificador.
    """
    vault, resultado = migrado
    for entrada in resultado["distributedFiles"]:
        assert entrada["destPath"].startswith("10_Migrated/"), entrada
    fuera = [p for p in vault.rglob("*.md")
             if "migratedFrom" in p.read_text(encoding="utf-8", errors="ignore")
             and "10_Migrated" not in p.parts]
    assert fuera == [], [str(p.relative_to(vault)) for p in fuera]


def test_una_copia_que_ya_existe_no_se_pisa(tmp_path):
    """Migrar dos veces no puede perder lo que alguien editó a mano.

    Antes, la segunda migración sobre el mismo proyecto tapaba la copia
    (incluida la edición del propietario) sin dejar rastro. Ahora la copia que
    ya existe se deja como estaba, su versión anterior queda en `.history/` y
    el conflicto se declara en el informe.
    """
    base = tmp_path / "conflicto"
    vault = base / "vault"
    vault.mkdir(parents=True)
    docs = base / "docs"
    docs.mkdir()
    (docs / "GUIA.md").write_text(
        "# Guia\n\nContenido original de la guia.\n", encoding="utf-8")

    _correr("vault_init.py", vault)
    _correr("vault_project.py", vault, "--add", "demo")
    _correr("vault_migrate_docs.py", vault, "--source_path", str(docs),
            "--project", "demo", "--dry_run", "false")

    copia = next(p for p in (vault / "10_Migrated").rglob("guia.md"))
    edicion = "\n".join([
        copia.read_text(encoding="utf-8"),
        "## Edicion del propietario",
        "",
        "No se debe perder.",
        "",
    ])
    copia.write_text(edicion, encoding="utf-8")

    r = _correr("vault_migrate_docs.py", vault, "--source_path", str(docs),
                "--project", "demo", "--dry_run", "false")
    assert r["ok"], r
    assert "Edicion del propietario" in copia.read_text(encoding="utf-8")
    # Lo que había antes quedó versionado: no se perdió, se declaró.
    versiones = list((vault / ".history").glob("*guia*"))
    assert versiones, "la versión anterior no quedó versionada"


def test_los_originales_del_proyecto_no_se_toquen(tmp_path):
    """La migración LEE el proyecto: ni un byte del origen cambia."""
    import hashlib

    base = tmp_path / "origenes"
    vault = base / "vault"
    vault.mkdir(parents=True)
    docs = base / "docs"
    docs.mkdir()
    (docs / "GUIA.md").write_text("# Guia\n\nContenido original.\n", encoding="utf-8")
    (docs / "manual.txt").write_text("Un fichero de texto.\n", encoding="utf-8")

    def huellas(base_dir):
        return {str(p.relative_to(base_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(base_dir.rglob("*")) if p.is_file()}

    antes = huellas(docs)
    _correr("vault_init.py", vault)
    _correr("vault_project.py", vault, "--add", "demo")
    _correr("vault_migrate_docs.py", vault, "--source_path", str(docs),
            "--project", "demo", "--dry_run", "false")
    assert huellas(docs) == antes
