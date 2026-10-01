"""Los defectos de v34.1 no vuelven (comparativa v34/v40, 2026-10-01).

`docs/auditorias/2026-10-01-comparativa-v34-v40.md` ejecutó la misma batería
contra las tools de v34.1 —las que sigue usando `/ans`— y contra la versión
actual, y miró **lo que quedó en disco**, no solo el envelope. Cada escenario de
aquí es una fila de esa tabla en la que v34.1 respondía `ok: true` con el daño
hecho. Se ejecutan como un tercero: un proceso por tool, `VAULT_ROOT` apuntado
a un vault temporal y `VAULT_STRICT_ROOT=1`.

Contra los scripts de v34.1 esta batería falla en siete de sus ocho casos (el de
`.history/` al sobrescribir ya lo cumplía), cada uno por el defecto que nombra.
Se comprobó a mano el mismo día con `VOA_SCRIPTS_BAJO_PRUEBA` apuntando a una
copia de esos scripts en la que solo se cambió la línea `VAULT_ROOT = …`: v34.1
fija la raíz desde `__file__` e ignora la variable de entorno, así que sin esa
sustitución los fallos habrían sido por escribir en otro sitio y no probarían
nada. No forma parte de la suite porque esos scripts no viven en este repo.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(os.environ.get("VOA_SCRIPTS_BAJO_PRUEBA", ROOT / "scripts"))

CUERPO = (
    "primera linea con suficientes palabras para pasar la validacion de contenido\n"
    "segunda linea del cuerpo de la nota de prueba\n"
    "tercera linea que cierra el cuerpo"
)
META = json.dumps({"agent": "regresion"})


@pytest.fixture
def entorno(tmp_path):
    raiz = tmp_path / "vault"
    for seccion in ("00_System", "03_Decisions", "07_Knowledge", "99_Index"):
        (raiz / seccion).mkdir(parents=True)
    fuera = tmp_path / "fuera-del-vault"
    fuera.mkdir()
    canario = fuera / "canario.md"
    canario.write_text("CONTENIDO-PRIVADO-DEL-DISCO\n", encoding="utf-8")
    return raiz, fuera, canario


def _tool(raiz: Path, tool: str, *argv: str):
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_AGENT="regresion")
    env.pop("VAULT_SKIP_SECRET_SCAN", None)
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / f"{tool}.py"), *argv],
        env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", cwd=str(raiz.parent), timeout=120)
    salida = p.stdout.strip()
    datos = json.loads(salida[salida.index("{"):]) if "{" in salida else {}
    return datos, salida


def _write(raiz, folder, title, *extra):
    return _tool(raiz, "vault_write", "--meta", META, "--tags", "demo",
                 "--folder", folder, "--title", title, *extra)


def _frontmatter(path: Path) -> dict:
    """Con el criterio del consumidor: `yaml.safe_load` sobre el bloque cerrado
    en una línea `---` (AP-44), no con el parser del propio repo."""
    texto = path.read_text(encoding="utf-8")
    assert texto.startswith("---\n"), texto[:80]
    bloque = texto[4:].split("\n---\n", 1)[0]
    datos = yaml.safe_load(bloque)
    assert isinstance(datos, dict), bloque
    return datos


def _notas(raiz: Path, carpeta: str):
    return [p for p in (raiz / carpeta).glob("*.md") if p.name != "index.md"]


def test_v34_titulo_con_dos_puntos_deja_frontmatter_legible(entorno):
    raiz, _, _ = entorno
    _write(raiz, "03_Decisions", "ADR-001: usar markdown", "--content", CUERPO)
    notas = _notas(raiz, "03_Decisions")
    assert notas, "la nota no se escribió"
    assert _frontmatter(notas[0])["title"] == "ADR-001: usar markdown"


def test_v34_titulo_no_inyecta_claves_en_el_frontmatter(entorno):
    raiz, _, _ = entorno
    _write(raiz, "07_Knowledge", "x\nstatus: hackeado\n---", "--content", CUERPO)
    for nota in _notas(raiz, "07_Knowledge"):
        assert _frontmatter(nota).get("status") != "hackeado", nota.name


def test_v34_write_no_sale_del_vault(entorno):
    raiz, fuera, _ = entorno
    datos, _ = _write(raiz, "../fuera-del-vault", "escapada", "--content", CUERPO)
    assert datos.get("ok") is not True
    assert not list(fuera.glob("escapada*"))
    assert not list(raiz.parent.glob("escapada*"))


def test_v34_read_no_lee_fuera_del_vault(entorno):
    raiz, _, _ = entorno
    datos, salida = _tool(raiz, "vault_read", "--path", "../fuera-del-vault/canario.md")
    assert datos.get("ok") is not True
    assert "CONTENIDO-PRIVADO" not in salida


def test_v34_un_secreto_no_llega_al_disco(entorno):
    raiz, _, _ = entorno
    clave = "AKIAIOSFODNN7EXAMPLE"
    datos, _ = _write(raiz, "07_Knowledge", "credenciales", "--content",
                      CUERPO + f"\naws_access_key_id = {clave}")
    assert datos.get("ok") is not True
    assert not any(clave in p.read_text(encoding="utf-8", errors="replace")
                   for p in raiz.rglob("*") if p.is_file())


def test_v34_sobrescribir_guarda_la_version_anterior(entorno):
    raiz, _, _ = entorno
    _write(raiz, "07_Knowledge", "Nota base", "--content", CUERPO)
    _write(raiz, "07_Knowledge", "Nota base", "--content", CUERPO + "\ncuarta linea nueva")
    assert list(raiz.rglob(".history/*nota-base*"))


def test_v34_relaciones_corruptas_no_se_pisan(entorno):
    raiz, _, _ = entorno
    primero, _ = _tool(raiz, "vault_relation_add", "--project", "demo", "--from", "A",
                       "--to", "B", "--relation_type", "uses")
    assert primero.get("ok") is True, primero
    fichero = next(raiz.rglob("demo-relations.json"))
    roto = fichero.read_text(encoding="utf-8").rstrip()[:-1] + ",]}"
    fichero.write_text(roto, encoding="utf-8")
    datos, _ = _tool(raiz, "vault_relation_add", "--project", "demo", "--from", "C",
                     "--to", "D", "--relation_type", "uses")
    assert datos.get("ok") is False
    assert datos.get("error_code") == "DATA_FILE_CORRUPT"
    assert fichero.read_text(encoding="utf-8") == roto


def test_v34_merge_overwrite_guarda_la_version_tapada(entorno):
    raiz, fuera, _ = entorno
    _write(raiz, "07_Knowledge", "Nota base", "--content", CUERPO)
    origen = fuera / "origen" / "07_Knowledge"
    origen.mkdir(parents=True)
    (origen / "nota-base.md").write_text(
        "---\ntitle: Nota base\n---\n\nversion del origen\n", encoding="utf-8")
    _tool(raiz, "vault_merge", "--source", str(fuera / "origen"), "--conflict", "overwrite")
    nota = raiz / "07_Knowledge" / "nota-base.md"
    assert "version del origen" in nota.read_text(encoding="utf-8")
    historial = [p for p in raiz.rglob(".history/*nota-base*")
                 if CUERPO.splitlines()[0] in p.read_text(encoding="utf-8")]
    assert historial, "la versión tapada no quedó en .history/"
