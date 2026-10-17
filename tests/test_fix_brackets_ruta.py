"""vault_fix_brackets --path no confunde «no pude mirar» con «no hay nada» (AP-51).

Medido 2026-10-02: una ruta fuera del vault (`../x.md`, absoluta) o una que no
existe devolvían `ok: true, scanned: 0, findings_total: 0`, idéntico a un
vault sin corchetes rotos. El agente que lo pedía daba la nota por sana.
La contención sí se cumplía: nunca leyó fuera.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

ROTA = "---\ntitle: n\n---\nver [[]] aquí\n"


@pytest.fixture
def vault(tmp_path):
    import vault_io

    root = tmp_path / "v"
    (root / "00_System").mkdir(parents=True)
    (root / "07_Knowledge").mkdir()
    (root / "07_Knowledge" / "n.md").write_text(ROTA, encoding="utf-8")
    (tmp_path / "fuera.md").write_text(ROTA, encoding="utf-8")
    vault_io.set_vault_root(root)
    return root


@pytest.mark.parametrize("ruta", ["../fuera.md", "ABS"])
def test_ap51_ruta_fuera_del_vault_es_un_error(vault, ruta):
    import vault_fix_brackets

    if ruta == "ABS":
        ruta = str(vault.parent / "fuera.md")
    r = vault_fix_brackets.vault_fix_brackets(path=ruta, apply=True)
    assert r["ok"] is False and r["error_code"] == "INVALID_PATH"
    assert (vault.parent / "fuera.md").read_text(encoding="utf-8") == ROTA


def test_ap51_ruta_inexistente_es_un_error(vault):
    import vault_fix_brackets

    r = vault_fix_brackets.vault_fix_brackets(path="07_Knowledge/no-existe.md")
    assert r["ok"] is False and r["error_code"] == "FILE_NOT_FOUND"


def test_ruta_valida_sigue_encontrando(vault):
    import vault_fix_brackets

    r = vault_fix_brackets.vault_fix_brackets(path="07_Knowledge/n.md")
    assert r["ok"] is True and r["scanned"] == 1 and r["findings_total"] == 1


def test_cn02_el_respaldo_no_estrena_una_carpeta_en_la_raiz(vault):
    # Medido con C8 en una copia de /ans: cada --apply dejaba en la raíz una
    # `.vault-fix-backup-<ts>/` que el audit contaba como CN-02 — el sanador de
    # AP-22/AP-24 subía otra norma. El criterio es el del audit, no el propio.
    import vault_fix_brackets
    from vault.gobernanza.auditoria_runtime import auditar_runtime

    r = vault_fix_brackets.vault_fix_brackets(apply=True)
    assert r["ok"] is True and r["backup_dir"], r
    assert (vault / r["backup_dir"]).is_dir()
    cn02 = [v for v in auditar_runtime(vault)["violations"] if v["norm"] == "CN-02"]
    assert cn02 == [], cn02


class _Atasco(BaseException):
    """Escapa del `except Exception` del bucle: el test falla en vez de colgarse."""


def test_un_fallo_al_escribir_no_deja_el_bucle_sin_fin(vault, monkeypatch):
    # El bucle de `--apply` recorría `fixes_applied` mientras le añadía la
    # entrada de error; esa entrada no trae `kinds_applied`, su vuelta lanza
    # `KeyError`, añade otra y la lista no se acaba nunca.
    import pathlib

    from vault.autoria import fix_brackets

    def falla(*a, **kw):
        raise OSError("disco lleno")

    lecturas = {"n": 0}
    leer = pathlib.Path.read_text

    def contada(self, *a, **kw):
        lecturas["n"] += 1
        if lecturas["n"] > 50:
            raise _Atasco
        return leer(self, *a, **kw)

    monkeypatch.setattr(fix_brackets, "atomic_write_text", falla)
    monkeypatch.setattr(pathlib.Path, "read_text", contada)
    r = fix_brackets.vault_fix_brackets(apply=True)
    monkeypatch.undo()
    assert r["files_modified"] == [], r
    assert [f for f in r["fixes_applied"] if "error" in f] == [
        {"path": "07_Knowledge/n.md", "error": "disco lleno"}], r


def test_ap51_un_arreglo_que_no_se_escribio_no_sale_ok(vault, monkeypatch):
    # `ok: True` con la escritura fallada se leía como «arreglado»: el error
    # solo aparecía mezclado dentro de `fixes_applied`.
    from vault.autoria import fix_brackets

    def falla(*a, **kw):
        raise OSError("disco lleno")

    monkeypatch.setattr(fix_brackets, "atomic_write_text", falla)
    r = fix_brackets.vault_fix_brackets(apply=True)
    assert r["ok"] is False and r["errors_count"] == 1, r
    assert (vault / "07_Knowledge" / "n.md").read_text(encoding="utf-8") == ROTA
