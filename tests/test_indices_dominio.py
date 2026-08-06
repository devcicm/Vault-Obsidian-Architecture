"""El contexto Índices, probado por donde ahora vive.

Dos cosas se comprueban aquí y no en los tests de las tools:

1. **Que la inyección es real, no decorativa.** Dos vaults en el mismo
   intérprete tienen que poder reindexarse sin contaminarse. Ése es el criterio
   de aceptación del refactor: si no se cumple, `VaultContext` es un adorno y el
   subproceso de `cli/runner.py` sigue siendo obligatorio para siempre.

2. **Que los defectos que salieron al migrar no vuelven.** Cada uno tiene su
   test con nombre, porque una corrección sin prueba que la sostenga se vuelve a
   romper (ciclo síntoma → norma → guard → test).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from vault.indices.carpetas import ServicioCarpetas  # noqa: E402
from vault.indices.coherencia import coherencia_indice  # noqa: E402
from vault.indices.enumeracion import es_nota_indexable, notas_en_disco  # noqa: E402
from vault.indices.reconstruccion import ServicioReindex  # noqa: E402
from vault.indices.repositorio import RepositorioIndices  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _vault(raiz: Path, notas=()) -> Path:
    for seccion in ("00_System", "99_Index", "07_Knowledge", "11_Code"):
        (raiz / seccion).mkdir(parents=True, exist_ok=True)
    for rel in notas:
        p = raiz / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"---\ntitle: {p.stem}\n---\n# {p.stem}\n", encoding="utf-8")
    return raiz


def _repo(raiz: Path) -> RepositorioIndices:
    return RepositorioIndices(construir(raiz))


def _parse(contenido: str) -> dict:
    from vault_lib import parse_frontmatter

    return parse_frontmatter(contenido)


# ── El criterio de aceptación ────────────────────────────────────────────────


def test_dos_vaults_se_reindexan_en_el_mismo_proceso_sin_contaminarse(tmp_path):
    """Si esto falla, la inyección es decorativa y el piloto no pasa."""
    a = _vault(tmp_path / "vault-a", ["07_Knowledge/uno.md"])
    b = _vault(tmp_path / "vault-b", ["07_Knowledge/dos.md", "11_Code/tres.md"])

    ra, rb = _repo(a), _repo(b)
    resultado_a = ServicioReindex(ra, _parse).reconstruir()
    resultado_b = ServicioReindex(rb, _parse).reconstruir()

    assert resultado_a["indexed"] == 1
    assert resultado_b["indexed"] == 2
    assert ra.indice_busqueda.is_relative_to(a)
    assert rb.indice_busqueda.is_relative_to(b)
    # Y ninguno escribió en el otro.
    assert not (a / "99_Index" / "search-index.json").read_text(
        encoding="utf-8"
    ).count("dos.md")


def test_el_repositorio_no_deja_salir_del_vault(tmp_path):
    """AP-36 es invariante del contexto, no algo que cada tool recuerde."""
    repo = _repo(_vault(tmp_path / "v"))
    with pytest.raises(ValueError, match="AP-36"):
        repo.ctx.ruta("..", "fuera.json")


# ── Enumeración: una definición, variantes declaradas ────────────────────────


def test_el_indice_de_una_seccion_no_es_contenido_para_las_etiquetas(tmp_path):
    raiz = _vault(tmp_path / "v", ["07_Knowledge/index.md", "07_Knowledge/nota.md"])
    secciones = _repo(raiz).ctx.secciones.ordenadas()

    con = {p.name for p in notas_en_disco(raiz, secciones, incluir_indices=True)}
    sin = {p.name for p in notas_en_disco(raiz, secciones, incluir_indices=False)}

    assert con == {"index.md", "nota.md"}
    assert sin == {"nota.md"}


def test_una_nota_suelta_en_la_raiz_no_se_indexa(tmp_path):
    """Una nota sin sección es AP-15; indexarla legitimaría la infracción."""
    raiz = _vault(tmp_path / "v")
    (raiz / "suelta.md").write_text("x", encoding="utf-8")
    secciones = _repo(raiz).ctx.secciones.ordenadas()
    assert not es_nota_indexable(raiz / "suelta.md", raiz, secciones)


def test_un_vault_bajo_un_directorio_oculto_se_indexa_igual(tmp_path):
    """El criterio mide el vault, no la disposición de la máquina (AP-44).

    `vault_reindex` filtraba tramos ocultos sobre la ruta **absoluta**: un vault
    colgado de `~/.claude/` se indexaba entero como vacío, sin error y sin que
    nada lo detectara.
    """
    raiz = _vault(tmp_path / ".oculto" / "vault-x", ["07_Knowledge/nota.md"])
    secciones = _repo(raiz).ctx.secciones.ordenadas()
    assert len(notas_en_disco(raiz, secciones)) == 1


def test_una_carpeta_oculta_dentro_del_vault_sigue_fuera(tmp_path):
    raiz = _vault(tmp_path / "v")
    escondida = raiz / "07_Knowledge" / ".borradores" / "x.md"
    escondida.parent.mkdir(parents=True)
    escondida.write_text("x", encoding="utf-8")
    secciones = _repo(raiz).ctx.secciones.ordenadas()
    assert notas_en_disco(raiz, secciones) == []


# ── Coherencia (AP-47) ───────────────────────────────────────────────────────


def test_un_indice_al_dia_es_coherente(tmp_path):
    raiz = _vault(tmp_path / "v", ["07_Knowledge/a.md"])
    repo = _repo(raiz)
    ServicioReindex(repo, _parse).reconstruir()
    informe = coherencia_indice(repo)
    assert informe["ok"] and informe["status"] == "index_ok"
    assert informe["on_disk"] == informe["indexed"] == 1


def test_una_nota_nueva_deja_el_indice_desfasado(tmp_path):
    raiz = _vault(tmp_path / "v", ["07_Knowledge/a.md"])
    repo = _repo(raiz)
    ServicioReindex(repo, _parse).reconstruir()
    (raiz / "07_Knowledge" / "b.md").write_text("---\ntitle: b\n---\n", encoding="utf-8")

    informe = coherencia_indice(repo)
    assert informe["status"] == "index_stale"
    assert informe["missing_count"] == 1
    assert "07_Knowledge/b.md" in informe["missing_in_index"]


def test_un_indice_corrupto_se_distingue_de_uno_ausente(tmp_path):
    """Degradar en silencio sería AP-37: los dos casos piden acciones distintas."""
    raiz = _vault(tmp_path / "v", ["07_Knowledge/a.md"])
    repo = _repo(raiz)
    assert coherencia_indice(repo)["status"] == "index_missing"

    repo.indice_busqueda.write_text("{roto", encoding="utf-8")
    informe = coherencia_indice(repo)
    assert informe["status"] == "index_corrupt" and "error" in informe


def test_un_vault_vacio_con_indice_vacio_es_coherente(tmp_path):
    repo = _repo(_vault(tmp_path / "v"))
    ServicioReindex(repo, _parse).reconstruir()
    assert coherencia_indice(repo)["ok"]


# ── Reconstrucción ───────────────────────────────────────────────────────────


def test_el_dry_run_no_escribe(tmp_path):
    repo = _repo(_vault(tmp_path / "v", ["07_Knowledge/a.md"]))
    resultado = ServicioReindex(repo, _parse).reconstruir(dry_run=True)
    assert resultado["indexed"] == 1 and resultado["dry_run"] is True
    assert not repo.indice_busqueda.exists()


def test_una_nota_ilegible_se_cuenta_en_vez_de_tragarse(tmp_path):
    """`skipped` es el indicador de trabajo que impide el no-op silencioso (AP-37)."""
    raiz = _vault(tmp_path / "v", ["07_Knowledge/a.md"])
    (raiz / "07_Knowledge" / "binaria.md").write_bytes(b"\xff\xfe\x00rota")
    resultado = ServicioReindex(_repo(raiz), _parse).reconstruir()
    assert resultado["indexed"] == 1 and resultado["skipped"] == 1


def test_las_rutas_del_indice_no_llevan_separador_de_windows(tmp_path):
    """Un índice con `\\` no lo resuelve el consumidor de otra plataforma."""
    repo = _repo(_vault(tmp_path / "v", ["07_Knowledge/sub/a.md"]))
    resultado = ServicioReindex(repo, _parse).reconstruir()
    assert "\\" not in resultado["path"]
    import json

    datos = json.loads(repo.indice_busqueda.read_text(encoding="utf-8"))
    assert datos["notes"][0]["path"] == "07_Knowledge/sub/a.md"


# ── Carpetas personalizadas ──────────────────────────────────────────────────


def test_una_carpeta_detectada_se_puede_eliminar_por_su_nombre(tmp_path):
    """El escaneo grababa `11_Code\\tests` y `--remove` recibe `11_Code/tests`.

    Una carpeta detectada automáticamente no se podía quitar del registro, y el
    fichero no era portable entre plataformas.
    """
    raiz = _vault(tmp_path / "v")
    (raiz / "11_Code" / "tests").mkdir(parents=True)
    servicio = ServicioCarpetas(_repo(raiz))

    assert servicio.escanear()["new_paths"] == ["11_Code/tests"]
    assert servicio.eliminar("11_Code/tests")["ok"] is True


def test_las_carpetas_auxiliares_no_se_registran(tmp_path):
    raiz = _vault(tmp_path / "v")
    for nombre in ("_datasets", ".oculta", "reales"):
        (raiz / "07_Knowledge" / nombre).mkdir(parents=True)
    detectadas = {c["path"] for c in ServicioCarpetas(_repo(raiz)).detectar()}
    assert detectadas == {"07_Knowledge/reales"}


def test_una_carpeta_registrada_que_ya_no_existe_es_huerfana(tmp_path):
    raiz = _vault(tmp_path / "v")
    servicio = ServicioCarpetas(_repo(raiz))
    servicio.anadir("11_Code/borrada")
    assert servicio.huerfanas() == ["11_Code/borrada"]
    assert servicio.limpiar_huerfanas()["removed"] == 1
    assert servicio.huerfanas() == []


def test_registrar_dos_veces_la_misma_carpeta_falla(tmp_path):
    servicio = ServicioCarpetas(_repo(_vault(tmp_path / "v")))
    assert servicio.anadir("11_Code/tests")["ok"] is True
    assert servicio.anadir("11_Code/tests")["ok"] is False


def test_las_secciones_salen_del_registro_no_de_una_copia(tmp_path):
    """La lista copiada se quedó en 13 mientras el estándar ya tenía 22."""
    repo = _repo(_vault(tmp_path / "v"))
    indexables = ServicioCarpetas(repo).carpetas_indexables()
    assert set(repo.ctx.secciones.ordenadas()) <= set(indexables)
    assert len(repo.ctx.secciones.ordenadas()) == 22
