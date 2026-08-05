"""El detector de enlaces rotos debe resolver como resuelve el lector.

Encontrado sanando BuilderX. `vault_audit` contaba 86 enlaces rotos donde el
recuento real era 37, y los 49 de diferencia eran enlaces que **Obsidian abre
sin problema**. Dos causas, ambas de la misma familia:

  1. El índice de destinos se construía con el nombre de fichero y la ruta,
     pero **nunca con `aliases:`**. Obsidian resuelve `[[X]]` por nombre de
     fichero O por alias — nunca por `title:`. Un vault que use alias para
     conservar el texto legible del enlace veía marcado como roto cada uno.

  2. El barrido excluía `.history` pero no `vault-backups/` ni `.trash/`, así
     que contaba enlaces que viven dentro de instantáneas congeladas — el mismo
     hueco que `test_audit_no_audita_instantaneas` cerró en `vault_norms`.

Por qué importa más que el número: un contador de enlaces rotos es una lista de
trabajo. Si no modela la resolución real del lector, manda al agente a reescribir
enlaces que funcionan — y cada reescritura es una oportunidad de romper uno.

Es el tercer caso de la misma forma en este estándar: **una tool que verifica
con un criterio distinto del que usa el consumidor real, y por tanto certifica
su propio error**. Los otros dos: `vault_graph_fix` indexando por `title`, y el
propio `vault_audit` leyendo frontmatter con un mini-parser que no entendía las
listas YAML que el estándar escribe.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_audit as va  # noqa: E402


def _vault(tmp_path: Path) -> Path:
    root = tmp_path / "v"
    for sec in ("00_System", "01_Projects", "99_Index"):
        (root / sec).mkdir(parents=True)
        (root / sec / "index.md").write_text("# index\n", encoding="utf-8")
    return root


def _con_raiz(root: Path):
    """`VAULT_ROOT` es global del módulo; se restaura siempre."""
    previo = va.VAULT_ROOT
    va.VAULT_ROOT = root
    return previo


def _rotos(root: Path):
    previo = _con_raiz(root)
    try:
        notas = [
            p
            for p in root.rglob("*.md")
            if not va.is_snapshot_path(p.relative_to(root))
        ]
        _, stems = va._build_indexes(notas)
        return va._detect_broken_links(notas, stems)
    finally:
        va.VAULT_ROOT = previo


# --- 1) alias -----------------------------------------------------------------


def test_un_enlace_al_alias_no_esta_roto(tmp_path):
    """El caso literal de BuilderX: 46 instancias marcadas en falso."""
    root = _vault(tmp_path)
    (root / "01_Projects" / "ap-levenshtein-dual.md").write_text(
        "---\ntitle: AP-MAINT-01\naliases:\n- ap-maint-01\n---\n\n# nota\n",
        encoding="utf-8",
    )
    (root / "01_Projects" / "origen.md").write_text(
        "---\ntitle: Origen\n---\n\nVer [[ap-maint-01]].\n", encoding="utf-8"
    )

    assert _rotos(root) == []


def test_alias_escalar_tambien_resuelve(tmp_path):
    """Obsidian acepta `aliases: nombre` además de la lista."""
    root = _vault(tmp_path)
    (root / "01_Projects" / "destino.md").write_text(
        "---\ntitle: D\naliases: Nombre Legible\n---\n\n# d\n", encoding="utf-8"
    )
    (root / "01_Projects" / "origen.md").write_text(
        "---\ntitle: O\n---\n\nVer [[Nombre Legible]].\n", encoding="utf-8"
    )

    assert _rotos(root) == []


def test_el_title_NO_resuelve_un_enlace(tmp_path):
    """La otra mitad de la norma, y la que se olvida.

    Resolver por `title:` sería tan erróneo como no resolver por alias: Obsidian
    no lo hace, así que un enlace que solo casa por título ESTÁ roto para el
    lector. Una tool que lo diera por bueno escondería el problema en vez de
    reportarlo — que es exactamente lo que hacía `vault_graph_fix`.
    """
    root = _vault(tmp_path)
    (root / "01_Projects" / "destino.md").write_text(
        "---\ntitle: Un Titulo Que No Es Alias\n---\n\n# d\n", encoding="utf-8"
    )
    (root / "01_Projects" / "origen.md").write_text(
        "---\ntitle: O\n---\n\nVer [[Un Titulo Que No Es Alias]].\n", encoding="utf-8"
    )

    assert [r["link"] for r in _rotos(root)] == ["Un Titulo Que No Es Alias"]


def test_un_frontmatter_ilegible_no_revienta_el_audit(tmp_path):
    """Un `title:` con dos puntos sin comillas basta para invalidar el YAML."""
    root = _vault(tmp_path)
    (root / "01_Projects" / "rota.md").write_text(
        "---\ntitle: ADR: sin comillas\naliases: [x]\n---\n\n# r\n", encoding="utf-8"
    )
    assert va._aliases_de(root / "01_Projects" / "rota.md") == []
    _rotos(root)  # no debe lanzar


# --- 2) instantáneas ----------------------------------------------------------


def test_no_cuenta_enlaces_rotos_dentro_de_una_instantanea(tmp_path):
    root = _vault(tmp_path)
    snap = root / "vault-backups" / "snap" / "01_Projects"
    snap.mkdir(parents=True)
    (snap / "vieja.md").write_text(
        "---\ntitle: V\n---\n\nVer [[destino-que-ya-no-existe]].\n", encoding="utf-8"
    )

    assert _rotos(root) == []


def test_una_copia_en_backups_no_valida_un_enlace_roto(tmp_path):
    """El hueco simétrico: el índice de destinos tampoco puede incluirlas."""
    root = _vault(tmp_path)
    snap = root / "vault-backups" / "snap" / "01_Projects"
    snap.mkdir(parents=True)
    (snap / "borrada.md").write_text("# borrada\n", encoding="utf-8")
    (root / "01_Projects" / "origen.md").write_text(
        "---\ntitle: O\n---\n\nVer [[borrada]].\n", encoding="utf-8"
    )

    assert [r["link"] for r in _rotos(root)] == ["borrada"]


def test_una_nota_viva_que_nombra_el_directorio_no_se_excluye(tmp_path):
    """`is_snapshot_path` compara segmentos, no subcadenas."""
    root = _vault(tmp_path)
    (root / "01_Projects" / "como-usar-vault-backups.md").write_text(
        "---\ntitle: C\n---\n\nVer [[no-existe]].\n", encoding="utf-8"
    )

    assert [r["link"] for r in _rotos(root)] == ["no-existe"]


# --- 3) el generador no puede producir notas que su propio audit repruebe -----


def test_el_primer_de_vault_init_declara_status(tmp_path):
    """18 de 18 primers de BuilderX salían sin `status` y el audit los marcaba.

    `template` y no `draft`: un primer es andamiaje estable, no un borrador en
    camino a otra cosa — y es el valor que AP-03 y AP-07 eximen de exigencias de
    contenido y de estructura de ADR.
    """
    import vault_init as vi
    from vault_lib import read_frontmatter
    from vault_norms import STATUS_VOCAB

    previo = vi.VAULT_ROOT
    vi.VAULT_ROOT = tmp_path / "v"
    try:
        (vi.VAULT_ROOT / "01_Projects").mkdir(parents=True)
        creado = vi._create_scaffold_note("01_Projects")
        fm = read_frontmatter(vi.VAULT_ROOT / creado["path"])
    finally:
        vi.VAULT_ROOT = previo

    assert fm.get("status") == "template"
    assert fm["status"] in STATUS_VOCAB
