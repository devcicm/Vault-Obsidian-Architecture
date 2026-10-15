"""`vault_audit` daba por resuelto un enlace que solo se *parece* a un fichero (AP-44).

`_detect_broken_links` aceptaba el enlace si `normalize_stem(link)` estaba en el
índice de stems, antes de preguntar al dueño canónico. `normalize_stem` quita
mayúsculas, guiones, espacios, puntos y tildes —está hecho para detectar
duplicados, no para resolver—, así que `[[Elegir PostgreSQL]]` contra
`elegir-postgresql.md` salía verde. Obsidian lo pinta roto: resuelve por nombre
de fichero (sin distinguir mayúsculas), sufijo de ruta y `aliases:`, nada más.

Lo encontró una sesión de agente consumidor el 2026-10-14: `vault_write` avisó
del *ghost link* y `vault_audit` dio `brokenLinks: []` sobre la misma nota. Dos
tools del estándar en desacuerdo sobre el mismo enlace, y la que mide la salud
en el sentido peligroso. El atajo es de junio (e6a744e), anterior a
`resolver_wikilink`; desde entonces el dueño cubre todo lo legítimo que cubría.

Medido sin el atajo sobre copias (hash intacto): sandbox 11 = 11, /vcloud 6 = 6,
/ans 79 → 80. El que aparece es `[[08_Runbooks-pipeline-ans-ci-cd]]`, que
casaba con `08_Runbooks/pipeline/ans-ci-cd.md` concatenando carpeta y nombre:
un roto real que el atajo escondía, y ningún roto falso nuevo.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_audit as va  # noqa: E402
import vault_io  # noqa: E402


def _rotos(tmp_path: Path, cuerpo: str):
    root = tmp_path / "v"
    for sec in ("00_System", "03_Decisions", "07_Knowledge", "99_Index"):
        (root / sec).mkdir(parents=True)
    (root / "99_Index" / "index.md").write_text("# index\n", encoding="utf-8")
    (root / "03_Decisions" / "elegir-postgresql.md").write_text(
        "---\ntitle: Elegir PostgreSQL\n---\n\n# Elegir PostgreSQL\n", encoding="utf-8")
    (root / "07_Knowledge" / "red.md").write_text(
        "---\ntitle: Red\n---\n\n# Red\n\n" + cuerpo + "\n", encoding="utf-8")
    vault_io.set_vault_root(root)
    notas = [p for p in root.rglob("*.md")
             if not va.is_snapshot_path(p.relative_to(root))]
    _, stems = va._build_indexes(notas)
    return sorted(r["link"] for r in va._detect_broken_links(notas, stems))


def test_ap44_el_title_con_espacios_no_resuelve_un_fichero_con_guiones(tmp_path):
    assert _rotos(tmp_path, "[[Elegir PostgreSQL]]") == ["Elegir PostgreSQL"]


def test_ap44_carpeta_y_nombre_pegados_con_guion_no_resuelven(tmp_path):
    assert _rotos(tmp_path, "[[03_Decisions-elegir-postgresql]]") == [
        "03_Decisions-elegir-postgresql"]


def test_ap44_lo_que_obsidian_abre_sigue_resolviendo(tmp_path):
    cuerpo = ("[[elegir-postgresql]] [[ELEGIR-POSTGRESQL]] "
              "[[03_Decisions/elegir-postgresql]] [[elegir-postgresql#Contexto]] "
              "[[elegir-postgresql|la decisión]]")
    assert _rotos(tmp_path, cuerpo) == []


def test_ap44_un_enlace_roto_no_da_entrantes_a_quien_se_le_parece(tmp_path):
    """Un solo veredicto por enlace (auditoría del 2026-10-15).

    Retirado el atajo de `_detect_broken_links`, quedaba su gemelo en el índice
    de backlinks (`stem_map`, emparejamiento por `normalize_stem`): el mismo
    `[[Elegir PostgreSQL]]` salía **roto** y a la vez daba un entrante a
    `elegir-postgresql.md`, que dejaba de ser huérfana por un enlace que
    Obsidian no sigue. AP-14 en `vault_norms_scan` tenía la misma copia.
    """
    _rotos(tmp_path, "[[Elegir PostgreSQL]]")
    notas = sorted((tmp_path / "v").rglob("*.md"))
    backlinks, _ = va._build_indexes(notas)
    assert not backlinks.get("elegir-postgresql"), dict(backlinks)
