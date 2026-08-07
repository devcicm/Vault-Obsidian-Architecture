"""El dominio de Durabilidad, ejercido sin CLI y sin subproceso.

Es lo que la caracterización no puede demostrar: aquélla prueba que el contrato
publicado no se movió, y ésta que la decisión ya vive en un sitio donde se puede
probar barato. Las dos hacen falta y ninguna sustituye a la otra.

El test que decide si el piloto se acepta es
`test_dos_vaults_en_el_mismo_proceso_no_se_contaminan`. Con los scripts es
imposible —82 vínculos congelados hacen que la primera raíz gane para todo el
proceso, AP-49—, y es la razón por la que `cli/runner.py` aísla cada tool en un
subproceso.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from vault.durabilidad.modelo import (  # noqa: E402
    LIMITE_DEFECTO, Backup, LimiteInvalido, RegistroBackups, validar_limite,
)
from vault.durabilidad.repositorio import RepositorioDurabilidad  # noqa: E402
from vault.kernel import construir  # noqa: E402


# ── Las entidades: sin disco, sin vault, sin contexto ────────────────────────

def test_una_entidad_del_dominio_no_necesita_nada_del_mundo():
    """Si hiciera falta un vault para probar esto, no sería dominio."""
    b = Backup(name="vault-2026-01-01-000000-x", label="x", noteCount=3)
    assert b.a_envelope()["noteCount"] == 3


def test_los_nombres_del_envelope_se_conservan_en_camelcase():
    """Son contrato publicado, no preferencia de estilo.

    Renombrar `noteCount` a `note_count` «de paso» sería exactamente la rotura
    silenciosa que este piloto existe para no cometer.
    """
    campos = set(Backup(name="n").a_envelope())
    assert campos == {
        "name", "label", "createdAt", "noteCount", "fileCount", "sizeKB", "sections"
    }


def test_desde_manifiesto_reconstruye_el_camino_degradado():
    """Un backup sin registro: copiado a mano, o registro perdido."""
    b = Backup.desde_manifiesto("bk-1", {
        "label": "suelto",
        "createdAt": "2026-01-01T00:00:00Z",
        "vault": {"totals": {"notes": 5, "files": 9, "sizeKB": 12.5},
                  "sections": [{"folder": "07_Knowledge"}]},
    })
    assert (b.noteCount, b.fileCount, b.sizeKB) == (5, 9, 12.5)
    assert b.sections == ["07_Knowledge"]


def test_un_manifiesto_vacio_no_revienta():
    b = Backup.desde_manifiesto("bk-roto", {})
    assert b.name == "bk-roto" and b.noteCount == 0 and b.sections == []


# ── El límite, que estaba publicado y sin implementar (AP-42) ────────────────

def test_el_total_no_lo_cambia_el_limite():
    reg = RegistroBackups(tuple(Backup(name=f"b{i}") for i in range(30)))
    total, devueltos = reg.acotado(5)
    assert total == 30, "quien pagina tiene que poder saber que falta algo"
    assert len(devueltos) == 5


def test_el_default_es_el_que_declara_el_contrato():
    reg = RegistroBackups(tuple(Backup(name=f"b{i}") for i in range(50)))
    assert LIMITE_DEFECTO == 20
    assert len(reg.acotado()[1]) == 20


@pytest.mark.parametrize("malo", [0, -1, 101, 1000])
def test_un_limite_fuera_de_rango_se_rechaza_en_el_dominio(malo):
    """Los validadores del catálogo, ejecutables sin pasar por argparse."""
    with pytest.raises(LimiteInvalido):
        validar_limite(malo)


@pytest.mark.parametrize("bueno", [1, 20, 100])
def test_los_limites_del_rango_son_admisibles(bueno):
    assert validar_limite(bueno) == bueno


def test_menos_backups_que_el_limite_no_inventa_ninguno():
    total, devueltos = RegistroBackups((Backup(name="uno"),)).acotado(20)
    assert total == 1 and len(devueltos) == 1


# ── El repositorio: contención como invariante ───────────────────────────────

def test_las_rutas_del_repositorio_cuelgan_del_vault(tmp_path):
    r = RepositorioDurabilidad(construir(tmp_path))
    assert r.raiz_backups.is_relative_to(tmp_path.resolve())
    assert r.fichero_registro.is_relative_to(tmp_path.resolve())
    assert r.ruta_de("bk-1").is_relative_to(tmp_path.resolve())


@pytest.mark.parametrize("hostil", [
    "../fuera", "..\\fuera", "sub/dir", ".oculto", "", "../../etc",
])
def test_un_nombre_de_backup_hostil_se_rechaza(tmp_path, hostil):
    """`nombre` puede venir de argv o de un manifiesto ajeno: entrada hostil.

    Es el mismo vector que v39.6 encontró en el restore por base64, cerrado
    ahora en el sitio por el que pasan todos.
    """
    r = RepositorioDurabilidad(construir(tmp_path))
    with pytest.raises(ValueError):
        r.ruta_de(hostil)


def test_sin_carpeta_de_backups_el_registro_esta_vacio(tmp_path):
    r = RepositorioDurabilidad(construir(tmp_path))
    assert r.registro().backups == ()


def test_un_registro_corrupto_es_vacio_y_no_excepcion(tmp_path):
    """Listar backups es a lo que acude quien YA tiene un problema."""
    (tmp_path / "vault-backups").mkdir(parents=True)
    (tmp_path / "vault-backups" / ".backup-registry.json").write_text(
        "{esto no es json", encoding="utf-8"
    )
    assert RepositorioDurabilidad(construir(tmp_path)).registro().backups == ()


def test_el_registro_manda_sobre_el_escaneo(tmp_path):
    raiz = tmp_path / "vault-backups"
    (raiz / "bk-en-disco").mkdir(parents=True)
    (raiz / ".backup-registry.json").write_text(
        json.dumps({"backups": [{"name": "bk-del-registro", "label": "r"}]}),
        encoding="utf-8",
    )
    reg = RepositorioDurabilidad(construir(tmp_path)).registro()
    assert [b.name for b in reg.backups] == ["bk-del-registro"]


def test_sin_registro_se_escanea_el_disco(tmp_path):
    raiz = tmp_path / "vault-backups"
    for nombre in ("bk-a", "bk-b"):
        (raiz / nombre).mkdir(parents=True)
        (raiz / nombre / ".manifest.json").write_text(
            json.dumps({"label": nombre, "vault": {"totals": {"notes": 2}}}),
            encoding="utf-8",
        )
    (raiz / ".oculto").mkdir()
    reg = RepositorioDurabilidad(construir(tmp_path)).registro()
    assert [b.name for b in reg.backups] == ["bk-b", "bk-a"], "más reciente primero"
    assert all(b.noteCount == 2 for b in reg.backups)


# ── El criterio de aceptación del piloto ─────────────────────────────────────

def test_dos_vaults_en_el_mismo_proceso_no_se_contaminan(tmp_path):
    """**Si esto falla, la inyección es decorativa y el piloto no pasa.**

    Dos raíces, un solo intérprete, sin subprocesos: cada repositorio lee y
    resuelve contra la suya. Con los scripts sin migrar es imposible.
    """
    a, b = tmp_path / "a", tmp_path / "b"
    for raiz, nombres in ((a, ["solo-en-a"]), (b, ["solo-en-b-1", "solo-en-b-2"])):
        (raiz / "vault-backups").mkdir(parents=True)
        (raiz / "vault-backups" / ".backup-registry.json").write_text(
            json.dumps({"backups": [{"name": n} for n in nombres]}), encoding="utf-8"
        )

    ra = RepositorioDurabilidad(construir(a))
    rb = RepositorioDurabilidad(construir(b))

    # Se leen alternados a propósito: si hubiera estado global, el segundo
    # acceso devolvería lo del otro vault.
    assert [x.name for x in ra.registro().backups] == ["solo-en-a"]
    assert [x.name for x in rb.registro().backups] == ["solo-en-b-1", "solo-en-b-2"]
    assert [x.name for x in ra.registro().backups] == ["solo-en-a"]

    assert ra.raiz_backups.is_relative_to(a.resolve())
    assert rb.raiz_backups.is_relative_to(b.resolve())
    assert not rb.raiz_backups.is_relative_to(a.resolve())


def test_el_adaptador_tambien_acepta_dos_raices(tmp_path):
    """La tool migrada, en proceso, contra dos vaults. Lo mismo desde arriba."""
    import vault_backup_list as adaptador

    a, b = tmp_path / "a", tmp_path / "b"
    for raiz, n in ((a, 1), (b, 3)):
        (raiz / "vault-backups").mkdir(parents=True)
        (raiz / "vault-backups" / ".backup-registry.json").write_text(
            json.dumps({"backups": [{"name": f"bk-{i}"} for i in range(n)]}),
            encoding="utf-8",
        )
    assert adaptador.vault_backup_list(root=a)["total"] == 1
    assert adaptador.vault_backup_list(root=b)["total"] == 3
    assert adaptador.vault_backup_list(root=a)["total"] == 1


def test_el_adaptador_no_decide_nada():
    """Un adaptador que crece lógica deja de ser adaptador.

    Se mide por AST y no por búsqueda de texto: el `--help` **sí** debe
    explicar dónde viven las copias, y penalizar esa prosa sería penalizar la
    documentación. Lo que no puede volver es la lógica — abrir ficheros,
    construir rutas de backup, parsear su JSON.
    """
    import ast

    fuente = (REPO_ROOT / "scripts" / "vault_backup_list.py").read_text(encoding="utf-8")
    arbol = ast.parse(fuente)

    llamadas = {
        n.func.id for n in ast.walk(arbol)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    } | {
        n.func.attr for n in ast.walk(arbol)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    }
    for fuga in ("open", "read_text", "iterdir", "glob", "loads", "mkdir"):
        assert fuga not in llamadas, f"{fuga}() volvió al adaptador: eso es dominio"

    # `dumps` sí: serializar el envelope a stdout es exactamente su trabajo.
    assert "dumps" in llamadas

    assert "VAULT_ROOT" not in fuente, "AP-49: el adaptador congeló la raíz"
