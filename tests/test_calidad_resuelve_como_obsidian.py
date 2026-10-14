"""`vault_quality_check` daba por rotos enlaces que Obsidian resuelve (AP-44).

F2 (consistencia) comparaba el destino entero —`99_Index/index`— con un
conjunto de *stems* —`index`—, así que ningún enlace con carpeta podía
resolver, y `aliases:` no entraba. En un vault recién creado con `vault init`,
`vault-hub.md` salía con 24 enlaces rotos a índices que existen, mientras
`vault_audit` daba conectividad 100: dos tools del mismo estándar
contradiciéndose sobre el mismo fichero. Y en el otro sentido, `normalize_stem`
quita guiones y espacios, así que `[[Mi Nota]]` contra `mi-nota.md` salía
resuelto cuando Obsidian lo pinta roto: la medida verde en el peor sentido.

El criterio tiene dueño (AP-57): `vault_lib.indice_de_destinos` y
`vault_lib.resolver_destino_wikilink`, los mismos con los que `vault_audit`
cuenta los rotos. Este módulo los importa en vez de copiarlos.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_io  # noqa: E402
import vault_quality_check as q  # noqa: E402

CABECERA = (
    "---\nid: {id}\ntitle: {id}\ncreatedAt: 2026-10-14\nupdatedAt: 2026-10-14\n"
    "{extra}---\n\n# {id}\n\n{cuerpo}\n"
)


def _nota(vault: Path, rel: str, cuerpo: str = "texto", extra: str = "") -> None:
    p = vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(CABECERA.format(id=p.stem, extra=extra, cuerpo=cuerpo), encoding="utf-8")


def _rotos(tmp_path: Path, cuerpo: str) -> list:
    vault = tmp_path / "vault"
    for d in ("00_System", "99_Index"):
        (vault / d).mkdir(parents=True, exist_ok=True)
    _nota(vault, "99_Index/index.md")
    _nota(vault, "09_Infrastructure/hosts/ct105.md")
    _nota(vault, "07_Knowledge/mi-nota.md")
    _nota(vault, "07_Knowledge/con-alias.md", extra="aliases: [Alias Uno]\n")
    _nota(vault, "07_Knowledge/origen.md", cuerpo=cuerpo)
    vault_io.set_vault_root(vault)
    r = q.vault_quality_check(check_only=True)
    assert r["ok"], r
    issues = r["notes"]["07_Knowledge/origen.md"]["issues"]
    return [i for i in issues if i.startswith("consistency: broken link")]


def test_ap44_un_enlace_con_carpeta_a_un_indice_que_existe_no_esta_roto(tmp_path):
    assert _rotos(tmp_path, "[[99_Index/index|Índice maestro]]") == []


def test_ap44_un_alias_declarado_resuelve(tmp_path):
    assert _rotos(tmp_path, "[[Alias Uno]]") == []


def test_ap44_la_carpeta_del_enlace_tiene_que_casar_como_sufijo(tmp_path):
    assert _rotos(tmp_path, "[[hosts/ct105]]") == []
    assert _rotos(tmp_path, "[[containers/ct105]]") == [
        "consistency: broken link [[containers/ct105]]"]


def test_ap44_espacios_contra_guiones_es_roto_como_en_obsidian(tmp_path):
    assert _rotos(tmp_path, "[[Mi Nota]]") == ["consistency: broken link [[Mi Nota]]"]
    assert _rotos(tmp_path, "[[MI-NOTA]]") == []
