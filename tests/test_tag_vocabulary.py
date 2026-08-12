"""AP-39 — vocabulario abierto CON memoria.

Lo que estos tests protegen no es "que los tags estén bien escritos": es que el
camino de escritura **lea** el registro y **anote** lo que no estaba. El defecto
original no fue de los agentes — `vault_write` consultaba una clave inexistente
del tag-registry, así que la sugerencia no se disparó nunca y la única señal de
que algo iba mal fue un censo hecho meses después.
"""

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_tags  # noqa: E402
import vault_norms  # noqa: E402


# ── Normalización ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "crudo,esperado",
    [
        ("CI_CD", "ci-cd"),
        ("ci cd", "ci-cd"),
        ("CI/CD", "ci-cd"),
        ("migración", "migracion"),
        ("  Observability  ", "observability"),
        ("anti.pattern", "anti-pattern"),
        ("a--b", "a-b"),
        ("--x--", "x"),
        ("", ""),
        ("###", ""),
    ],
)
def test_normalize_tag_colapsa_variantes_tipograficas(crudo, esperado):
    assert vault_tags.normalize_tag(crudo) == esperado


@pytest.mark.parametrize(
    "plural,singular",
    [
        ("patterns", "pattern"),
        ("flows", "flow"),
        ("indices", "indic"),   # inequívoco por regla, aunque no sea bonito
        ("css", "css"),         # -ss no se toca
        ("status", "status"),   # -us no se toca
        ("analysis", "analysis"),  # -is no se toca
        ("api", "api"),
    ],
)
def test_singular_tag_solo_toca_los_plurales_inequivocos(plural, singular):
    assert vault_tags.singular_tag(plural) == singular


def test_normalize_tag_es_idempotente():
    for crudo in ["CI_CD", "migración", "Anti Pattern", "flows"]:
        una = vault_tags.normalize_tag(crudo)
        assert vault_tags.normalize_tag(una) == una


# ── Resolución contra el registro ────────────────────────────────────────────

INDICE = {"ci-cd": "ci-cd", "pattern": "pattern", "mcp": "mcp"}


@pytest.mark.parametrize(
    "crudo,tag,regla",
    [
        ("mcp", "mcp", "canonical"),
        ("MCP", "mcp", "normalized"),
        ("CI_CD", "ci-cd", "normalized"),
        ("patterns", "pattern", "singular"),
        ("kubernetes", "kubernetes", "new"),
        ("", "", "empty"),
    ],
)
def test_resolve_tag_devuelve_tag_y_regla(crudo, tag, regla):
    assert vault_tags.resolve_tag(crudo, INDICE) == (tag, regla)


def test_un_termino_nuevo_se_admite_no_se_rechaza():
    """Rechazar empujaría a omitir el campo, y entonces lo que se rompe es AP-26."""
    tag, regla = vault_tags.resolve_tag("termino-que-nadie-uso-jamas", INDICE)
    assert regla == "new"
    assert tag == "termino-que-nadie-uso-jamas"


def test_apply_vocabulary_deduplica_lo_que_colapsa_al_mismo_termino(monkeypatch):
    monkeypatch.setattr(vault_tags, "_canonical_index", lambda: dict(INDICE))
    tags, nuevos = vault_tags.apply_vocabulary(["MCP", "mcp", "CI_CD", "ci-cd"])
    assert tags == ["mcp", "ci-cd"]
    assert nuevos == []


def test_apply_vocabulary_reporta_los_terminos_introducidos(monkeypatch):
    monkeypatch.setattr(vault_tags, "_canonical_index", lambda: dict(INDICE))
    tags, nuevos = vault_tags.apply_vocabulary(["mcp", "Kubernetes"], note="07_Knowledge/x.md")
    assert tags == ["mcp", "kubernetes"]
    assert [n["tag"] for n in nuevos] == ["kubernetes"]
    assert nuevos[0]["raw"] == "Kubernetes"
    assert nuevos[0]["note"] == "07_Knowledge/x.md"


def test_apply_vocabulary_no_escribe_nada(monkeypatch, tmp_path):
    """Anotar antes de confirmar la escritura sería memoria de algo inexistente."""
    _apuntar_al_vault(monkeypatch, tmp_path)
    monkeypatch.setattr(vault_tags, "_canonical_index", lambda: dict(INDICE))
    vault_tags.apply_vocabulary(["termino-nuevo"])
    assert not (tmp_path / "19_Audits" / "vocabulary" / "tag-ledger.json").exists()


# ── Bitácora ─────────────────────────────────────────────────────────────────

def _apuntar_al_vault(monkeypatch, raiz):
    """Se apunta la raíz, no cada ruta.

    Antes había que parchear `TAG_LEDGER`, `VOCAB_DIR` y `VAULT_ROOT` por
    separado — tres constantes congeladas al importar (AP-49) que el test tenía
    que mantener coherentes a mano. Ahora se inyecta la raíz una vez y las rutas
    salen del repositorio: si se separaran, el propio dominio fallaría.

    El override lo deshace el fixture autouse de `conftest.py` al terminar cada
    test, así que no hace falta restaurarlo aquí.
    """
    import vault_io

    vault_io.set_vault_root(raiz)


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    _apuntar_al_vault(monkeypatch, tmp_path)
    return tmp_path / "19_Audits" / "vocabulary" / "tag-ledger.json"


def test_record_new_tags_guarda_quien_cuando_y_donde(ledger):
    n = vault_tags.record_new_tags(
        [{"tag": "kubernetes", "raw": "Kubernetes", "note": "07_Knowledge/k.md", "agent": "claude"}]
    )
    assert n == 1
    entradas = vault_tags._load_ledger()["entries"]
    assert len(entradas) == 1
    e = entradas[0]
    assert e["tag"] == "kubernetes"
    assert e["raw"] == "Kubernetes"
    assert e["first_note"] == "07_Knowledge/k.md"
    assert e["introduced_by"] == "claude"
    assert e["introduced_at"]


def test_la_bitacora_conserva_la_primera_introduccion(ledger):
    vault_tags.record_new_tags([{"tag": "k8s", "note": "a.md", "agent": "sesion-1"}])
    vault_tags.record_new_tags([{"tag": "k8s", "note": "b.md", "agent": "sesion-2"}])
    entradas = vault_tags._load_ledger()["entries"]
    assert len(entradas) == 1, "un término se introduce una sola vez"
    assert entradas[0]["introduced_by"] == "sesion-1"
    assert entradas[0]["first_note"] == "a.md"


def test_la_bitacora_es_append_only(ledger):
    vault_tags.record_new_tags([{"tag": "uno", "note": "a.md", "agent": "x"}])
    vault_tags.record_new_tags([{"tag": "dos", "note": "b.md", "agent": "x"}])
    assert [e["tag"] for e in vault_tags._load_ledger()["entries"]] == ["uno", "dos"]


def test_agente_desconocido_no_pierde_la_entrada(ledger):
    vault_tags.record_new_tags([{"tag": "huerfano", "note": "a.md", "agent": ""}])
    assert vault_tags._load_ledger()["entries"][0]["introduced_by"] == "unknown"


def test_record_new_tags_sin_terminos_no_crea_el_archivo(ledger):
    assert vault_tags.record_new_tags([]) == 0
    assert not ledger.exists()


# ── La norma existe y tiene enforcement real ─────────────────────────────────

def test_ap39_esta_en_el_catalogo_con_enforcement_real():
    norma = next((n for n in vault_norms.NORM_CATALOG if n["code"] == "AP-39"), None)
    assert norma is not None
    assert norma["enforcement"] in ("guard", "audit", "guard+audit", "recommended")
    assert norma["enforcement"] != "manual"
    assert "vault_write" in norma["tools_enforcing"]


def test_ap39_declara_las_tools_que_lo_detectan():
    norma = next(n for n in vault_norms.NORM_CATALOG if n["code"] == "AP-39")
    assert "vault_tags" in norma["tools_detecting"]


# ── El camino de escritura, que es donde estaba el defecto ───────────────────

def test_vault_write_llama_al_registro_de_vocabulario():
    """El guard: si alguien quita la llamada, la memoria del vocabulario muere
    en silencio — igual que murió la sugerencia rota durante versiones."""
    fuente = (SCRIPTS / "vault_write.py").read_text(encoding="utf-8")
    assert "vault_tags.apply_vocabulary" in fuente
    assert "vault_tags.record_new_tags" in fuente


def test_vault_write_no_lee_la_clave_muerta_del_tag_registry():
    # Solo código: el comentario que explica el defecto cita la clave a propósito.
    codigo = "\n".join(
        l for l in (SCRIPTS / "vault_write.py").read_text(encoding="utf-8").splitlines()
        if not l.lstrip().startswith("#")
    )
    assert 'registry.get("tags"' not in codigo
    assert 'registry["tags"]' not in codigo


def test_las_secciones_de_vault_tags_salen_del_registro_no_de_una_lista():
    """La lista literal se quedó en 18 carpetas y dejó de ver las nuevas."""
    from vault_registry import SECTIONS

    assert vault_tags.VAULT_SECTIONS == {s["folder"] for s in SECTIONS}


def test_un_solo_lector_del_campo_tags():
    """Dos parsers del mismo campo discrepando es lo que hizo que el audit
    reportara términos que el heal no podía tocar."""
    fuente = (SCRIPTS / "vault_tags.py").read_text(encoding="utf-8")
    assert "parse_frontmatter_with_body" in fuente
