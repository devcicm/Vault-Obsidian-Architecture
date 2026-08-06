"""AP-46 — el frontmatter se verifica releyéndolo, no confiando en cómo se montó.

Veintiséis tools construyen el bloque concatenando líneas y tres importan el
write path canónico. Cada concatenación es un segundo autor del formato sin
guard detrás, y el fallo no se ve al escribir —la tool devuelve `ok: true`
porque el fichero se creó— sino al auditar, cuando la nota ya es el dato.
`vault_migrate_docs` cortaba el documento por la línea 7 y llevaba versiones
publicándose con el bloque sin cerrar.

La corrección no reescribe las 26 tools: valida la SALIDA en el único sitio por
el que todas pasan. Es AP-44 aplicado al generador — se comprueba con
`yaml.safe_load`, que es lo que usa quien lee la nota.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import vault_io  # noqa: E402
import vault_norms  # noqa: E402


@pytest.fixture
def vault(tmp_path):
    original = vault_io.get_vault_root()
    raiz = tmp_path / "vault"
    (raiz / "07_Knowledge").mkdir(parents=True)
    vault_io.set_vault_root(raiz)
    vault_io._FRONTMATTER_SIN_TIPO.clear()
    yield raiz
    vault_io.set_vault_root(original)
    vault_io._FRONTMATTER_SIN_TIPO.clear()


# ── La norma existe y tiene enforcement real ──────────────────────────────────

def test_la_norma_esta_en_el_catalogo_y_no_es_manual():
    ap46 = next((n for n in vault_norms.NORM_CATALOG if n["code"] == "AP-46"), None)
    assert ap46 is not None, "AP-46 no está registrada"
    assert ap46["enforcement"] != "manual", (
        "una norma sin enforcement automático se vuelve a romper (regla 5)"
    )
    assert ap46["enforcement"] in {"guard", "audit", "guard+audit", "recommended"}


# ── Guard: el write path ──────────────────────────────────────────────────────

def test_un_bloque_que_nunca_cierra_se_bloquea(vault):
    """El defecto literal de v39.2: el documento cortado por la línea 7."""
    destino = vault / "07_Knowledge" / "rota.md"
    with pytest.raises(ValueError, match="nunca lo cierra"):
        vault_io.atomic_write_text(destino, "---\ntype: knowledge\ntitle: A\n")
    assert not destino.exists(), "escribió la nota rota igualmente"


def test_un_frontmatter_que_no_parsea_se_bloquea(vault):
    destino = vault / "07_Knowledge" / "invalida.md"
    roto = "---\ntype: knowledge\ntags: [a, b\naliases: {sin cerrar\n---\n\nCuerpo.\n"
    with pytest.raises(ValueError, match="no parsea"):
        vault_io.atomic_write_text(destino, roto)
    assert not destino.exists()


def test_un_frontmatter_valido_pasa_intacto(vault):
    destino = vault / "07_Knowledge" / "buena.md"
    texto = "---\ntype: knowledge\nstatus: draft\ntags: [a, b]\n---\n\nCuerpo real.\n"
    vault_io.atomic_write_text(destino, texto)
    assert "type: knowledge" in destino.read_text(encoding="utf-8")


def test_la_falta_de_tipo_se_registra_pero_no_bloquea(vault):
    """Bloquear aquí rompería escrituras legítimas; callarlo es AP-37."""
    destino = vault / "07_Knowledge" / "sin-tipo.md"
    vault_io.atomic_write_text(destino, "---\ntitle: Algo\n---\n\nCuerpo.\n")
    assert destino.exists(), "no debía bloquearse"
    registradas = vault_io.frontmatter_degradations()
    assert registradas and registradas[-1]["reason"] == "missing_type"


def test_una_nota_sin_frontmatter_no_se_toca(vault):
    """No todo `.md` lleva bloque; exigirlo aquí sería inventar una norma."""
    destino = vault / "07_Knowledge" / "plana.md"
    vault_io.atomic_write_text(destino, "# Solo prosa\n\nSin metadatos.\n")
    assert destino.exists()
    assert not vault_io.frontmatter_degradations()


def test_en_cuarentena_el_bloque_roto_es_el_dato(vault):
    """`20_Quarantine` guarda justo lo que vino mal para poder repararlo."""
    destino = vault / "20_Quarantine" / "rescatada.md"
    vault_io.atomic_write_text(destino, "---\ntype: knowledge\nsin cerrar\n")
    assert destino.exists()


# ── Audit: la detección sobre un vault ya escrito ─────────────────────────────

def test_el_audit_reporta_la_nota_con_el_bloque_sin_cerrar(vault):
    # Escritura en crudo a propósito: simula lo que ya está en disco de antes
    # del guard. El audit tiene que verlo sin depender de quién lo escribió.
    (vault / "07_Knowledge" / "legacy.md").write_text(
        "---\ntype: knowledge\ntitle: Sin cerrar\n", encoding="utf-8"
    )
    res = vault_norms.vault_norms_audit(root=vault)
    ap46 = [v for v in res["violations"] if v["norm"] == "AP-46"]
    assert ap46, "el audit no vio el frontmatter sin cerrar"
    assert ap46[0]["path"].endswith("legacy.md")


def test_el_audit_no_reporta_una_nota_bien_formada(vault):
    (vault / "07_Knowledge" / "sana.md").write_text(
        "---\ntype: knowledge\nstatus: draft\n---\n\nContenido con [[enlace]].\n",
        encoding="utf-8",
    )
    res = vault_norms.vault_norms_audit(root=vault)
    assert not [v for v in res["violations"] if v["norm"] == "AP-46"]
