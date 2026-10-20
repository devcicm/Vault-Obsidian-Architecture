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

from vault.indices.reconstruccion import (  # noqa: E402
    ServicioReindex,
    escribir_json_si_cambia,
)
from vault.indices.seccion import (  # noqa: E402
    MARCA_DE_GENERADO,
    con_marca_de,
    conservar_marca_de_generado,
    texto_semantico,
)

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from vault.indices.carpetas import ServicioCarpetas  # noqa: E402
from vault.kernel.fallos import FalloDeDominio  # noqa: E402
from vault.indices.coherencia import coherencia_indice  # noqa: E402
from vault.indices.enumeracion import es_nota_indexable, notas_en_disco  # noqa: E402
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
    """Desde v40.29 el dominio **levanta** en vez de devolver un envelope.

    El cambio es el punto de la tanda, no un detalle de forma: un fallo
    devuelto como valor se ignora por olvido —basta con no mirar `["ok"]`— y
    aquí el mismo mecanismo cubre el borrado del vault sin confirmar. Quien
    quiera el envelope lo pide al adaptador, que es quien sabe a qué consumidor
    le habla.
    """
    servicio = ServicioCarpetas(_repo(_vault(tmp_path / "v")))
    assert servicio.anadir("11_Code/tests")["ok"] is True
    with pytest.raises(FalloDeDominio) as exc:
        servicio.anadir("11_Code/tests")
    assert exc.value.causa == "CARPETA_YA_REGISTRADA"
    assert exc.value.datos["path"] == "11_Code/tests"


def test_las_secciones_salen_del_registro_no_de_una_copia(tmp_path):
    """La lista copiada se quedó en 13 mientras el estándar ya tenía 22."""
    repo = _repo(_vault(tmp_path / "v"))
    indexables = ServicioCarpetas(repo).carpetas_indexables()
    assert set(repo.ctx.secciones.ordenadas()) <= set(indexables)
    assert len(repo.ctx.secciones.ordenadas()) == 23


# --- El formato del índice, probado sin tocar disco ---------------------------
#
# Antes vivía en `scripts/vault_section_index.py` mezclado con la escritura, el
# `file_lock` y el guard CN-02: comprobar una regla de formato obligaba a montar
# un vault y escribir un fichero. Ahora el renderizador recibe sus dependencias
# y devuelve texto, así que AP-21 se comprueba mirando el texto.

from vault.indices.seccion import (  # noqa: E402
    RE_ALIAS_EN_TABLA,
    RenderizadorDeIndice,
    migaja,
    recolectar_notas,
)


def _render(**kwargs):
    r = RenderizadorDeIndice(
        describir_seccion=lambda k: f"desc:{k}",
        pista_de_tool=lambda k: "",
        enlace_seguro=lambda s: s,
    )
    return r.render(**kwargs)


def test_el_enlace_de_la_tabla_va_por_stem_y_sin_alias():
    """AP-21 y el defecto de los alias en celda, en una sola aserción.

    Un `[[07_Knowledge/nota]]` deja de resolver en cuanto la nota se mueve, y un
    `[[nota|Título — largo]]` dentro de la celda parece celda combinada: los
    agentes creaban notas en blanco a partir del alias.
    """
    texto = _render(
        carpeta="07_Knowledge",
        notas=[{"title": "Un título", "path": "sub/nota-a.md",
                "type": "knowledge", "updatedAt": "2026-01-01"}],
        ahora="AHORA",
    )
    assert "| [[nota-a]] |" in texto
    assert "[[sub/nota-a]]" not in texto
    assert RE_ALIAS_EN_TABLA.search(texto) is None


def test_una_seccion_vacia_no_embebe_comandos():
    """AP-05: los comandos viven en `vault-commands.md` y en ningún otro sitio.

    Repetidos en 16 índices eran 16 copias que envejecen por separado.
    """
    texto = _render(carpeta="07_Knowledge", notas=[], ahora="AHORA")
    assert "_Sección sin notas._" in texto
    assert "```" not in texto
    assert "[[vault-commands|vault-commands]]" in texto


def test_la_migaja_nunca_enlaza_un_stem_generico():
    """`index` es el stem de las 22 secciones: enlazarlo apunta a cualquiera.

    AP-21 precisado (v40.35): la ruta entera sí fija cuál es, y solo se
    escribe si el índice existe. Sin saberlo, la migaja se queda en texto.
    """
    for clave in ("07_Knowledge", "02_Observability/errors"):
        for disponible in (None, lambda ruta: True):
            texto = migaja(clave, disponible)
            assert "[[vault-hub|Hub]]" in texto
            assert "[[index" not in texto
        # Sin predicado, solo el hub y la nota de comandos son enlaces.
        assert migaja(clave).count("[[") == 2


def test_el_indice_no_se_cuenta_a_si_mismo(tmp_path):
    """Incluirlo añadiría una fila en cada regeneración (AP-47 realimentado).

    `readme.md` sí sale: es contenido, no navegación generada. Por eso el
    recorte se hace por nombre exacto aquí y no con `incluir_indices=False`,
    que se llevaría los dos por delante.
    """
    raiz = tmp_path / "vault"
    seccion = raiz / "07_Knowledge"
    (seccion / ".oculta").mkdir(parents=True)
    (seccion / "index.md").write_text("# viejo\n", encoding="utf-8")
    (seccion / ".oculta" / "x.md").write_text("---\ntitle: X\n---\n", encoding="utf-8")
    (seccion / "readme.md").write_text("---\ntitle: Léeme\n---\n", encoding="utf-8")
    (seccion / "real.md").write_text("---\ntitle: Real\n---\n", encoding="utf-8")

    notas = recolectar_notas(
        raiz, seccion, ["07_Knowledge"], True, lambda c: {"title": "T"}
    )
    assert [n["path"] for n in notas] == ["readme.md", "real.md"]


def test_una_raiz_con_punto_no_vacia_la_seccion(tmp_path):
    """El defecto heredado: se filtraba por los tramos de la ruta ABSOLUTA.

    Un vault en `~/.claude/vault-x/` salía entero como sección vacía, sin
    error. Al consumir el enumerador único el criterio pasa a ser el relativo:
    se mide el vault, no la disposición de la máquina que lo aloja (AP-44).
    """
    raiz = tmp_path / ".claude" / "vault-x"
    (raiz / "07_Knowledge").mkdir(parents=True)
    (raiz / "07_Knowledge" / "real.md").write_text("---\n---\n", encoding="utf-8")

    notas = recolectar_notas(
        raiz, raiz / "07_Knowledge", ["07_Knowledge"], True, lambda c: {}
    )
    assert [n["path"] for n in notas] == ["real.md"]


# ── Mismo cuerpo ⇒ mismo documento (v41.12, el C3 del auditor) ──────────────


def test_texto_semantico_quita_la_linea_de_marca():
    """El sello de tiempo NO es contenido: dos generaciones del mismo cuerpo
    comparten texto semántico aunque el reloj haya avanzado."""
    cuerpo = "# 99_Index\n\n| Sección | Notas |\n|---|---|\n"
    previo = cuerpo + f"\n> {MARCA_DE_GENERADO} · 2026-10-20T09:00:00.000Z · 5 nota(s)\n"
    nuevo = cuerpo + f"\n> {MARCA_DE_GENERADO} · 2026-10-20T10:00:00.000Z · 5 nota(s)\n"
    assert texto_semantico(previo) == texto_semantico(nuevo)


def test_con_marca_de_conserva_el_sello_si_el_cuerpo_no_cambia():
    """Regenerar lo mismo no produce documento nuevo: se devuelve el texto
    previo y el disco queda tal cual — el `unchanged` del ledger sale honesto."""
    previo = f"# Índice\n\n> {MARCA_DE_GENERADO} · viejo · 5 nota(s)\n\ncuerpo\n"
    nuevo = f"# Índice\n\n> {MARCA_DE_GENERADO} · nuevo · 5 nota(s)\n\ncuerpo\n"
    assert con_marca_de(previo, nuevo) == previo


def test_con_marca_de_a_cuerpo_nuevo_le_toca_sello_nuevo():
    """Si el cuerpo cambió, el texto nuevo va entero: contenido nuevo, sello
    nuevo. Conservar aquí sería congelar un índice desfasado."""
    previo = f"# Índice\n\n> {MARCA_DE_GENERADO} · viejo · 5 nota(s)\n\n5 filas\n"
    nuevo = f"# Índice\n\n> {MARCA_DE_GENERADO} · nuevo · 6 nota(s)\n\n6 filas\n"
    assert con_marca_de(previo, nuevo) == nuevo


def test_con_marca_de_no_toca_un_indice_escrito_a_mano(tmp_path):
    """Un `index.md` sin la marca es AJENO (AP-25): ni se conserva ni se
    compara — el llamador decide si le toca reescritura, y a eso viene."""
    ajeno = tmp_path / "index.md"
    ajeno.write_text("# Escrito a mano\n\n- [[una-nota]]\n", encoding="utf-8")
    nuevo = f"# Índice\n\n> {MARCA_DE_GENERADO} · nuevo\n"
    assert conservar_marca_de_generado(ajeno, nuevo) == nuevo


def test_la_reconstruccion_del_mismo_vault_no_reescribe_los_json(tmp_path, monkeypatch):
    """Reconstruir dos veces el mismo vault es UNA escritura (v41.12).

    Cada corrida sellaba `rebuiltAt`/`snapshot_at` con el reloj y el diff de
    bytes daba por trabajo una regeneración que no cambió nada — el gemelo JSON
    del parpadeo de los índices .md que el auditor midió en O1."""
    raiz = _vault(tmp_path / "v", ["07_Knowledge/a.md", "11_Code/b.md"])
    repo = _repo(raiz)
    servicio = ServicioReindex(repo, _parse)
    servicio.reconstruir()
    antes = repo.indice_busqueda.read_bytes()

    llamadas = []
    original = type(repo.ctx.escritor).escribir_json

    def espia(self, ruta, datos):
        llamadas.append(Path(ruta).name)
        original(self, ruta, datos)

    monkeypatch.setattr(type(repo.ctx.escritor), "escribir_json", espia)
    servicio.reconstruir()
    # La segunda pasada no escribe NINGUNO de los dos índices: el cuerpo es
    # igual y solo los sellos movían.
    assert llamadas == [], llamadas
    assert repo.indice_busqueda.read_bytes() == antes


def test_la_reconstruccion_tras_un_cambio_si_reescribe(tmp_path):
    """La dedup no congelan el índice: a nota nueva le toca fila nueva."""
    raiz = _vault(tmp_path / "v", ["07_Knowledge/a.md"])
    repo = _repo(raiz)
    servicio = ServicioReindex(repo, _parse)
    servicio.reconstruir()
    antes = repo.indice_busqueda.read_bytes()

    (raiz / "07_Knowledge" / "b.md").write_text(
        "---\ntitle: b\n---\n# b\n", encoding="utf-8")
    servicio.reconstruir()
    despues = repo.indice_busqueda.read_bytes()
    assert despues != antes
    assert "b.md" in despues.decode("utf-8")


def test_escribir_json_si_cambia_excluye_sellos_del_llamador(tmp_path):
    """Las claves de sello propias del llamador entran por parámetro — el caso
    de `vault_graph_merge`, cuyas lecturas de reloj sobre sí mismo nunca
    convergen (0.0h → 0.2h → …): son sello, no contenido."""
    ruta = tmp_path / "enriquecido.json"
    escritos = []

    def escritor(r, datos):
        escritos.append(r.name)
        ruta.write_text(__import__("json").dumps(datos), encoding="utf-8")

    def cuerpo(horas):
        return {"stats": {"nodos": 3},
                "diagnostics": {"silo_flags": {
                    "graph_enriched_hours_old": horas,
                    "graph_enriched_stale": horas > 24}}}

    sellos = frozenset({"graph_enriched_hours_old", "graph_enriched_stale"})
    assert escribir_json_si_cambia(escritor, ruta, cuerpo(0.0),
                                   claves_de_sello=sellos) is True
    # Mismo cuerpo con otra edad: sin escritura.
    assert escribir_json_si_cambia(escritor, ruta, cuerpo(0.3),
                                   claves_de_sello=sellos) is False
    assert escritos == ["enriquecido.json"]
    # Cuerpo nuevo: escritura.
    assert escribir_json_si_cambia(escritor, ruta, {"stats": {"nodos": 4}},
                                   claves_de_sello=sellos) is True
    assert escritos == ["enriquecido.json", "enriquecido.json"]
