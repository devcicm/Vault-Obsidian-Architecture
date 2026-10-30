"""La base compartida: cada copia es independiente y trae lo prometido."""
from vault_base import copiar_vault, vault_base


def test_la_copia_trae_el_vault_y_los_proyectos_pedidos(tmp_path):
    raiz = copiar_vault(tmp_path / "v", "demo")
    assert (raiz / "00_System" / "standard-version.json").is_file()
    assert (raiz / "projects" / "demo").exists() or any(raiz.rglob("demo"))


def test_lo_escrito_en_una_copia_no_llega_a_la_base_ni_a_otra_copia(tmp_path):
    a = copiar_vault(tmp_path / "a")
    (a / "07_Knowledge" / "solo-en-a.md").write_text("x", encoding="utf-8")
    assert not (vault_base() / "07_Knowledge" / "solo-en-a.md").exists()
    assert not (copiar_vault(tmp_path / "b") / "07_Knowledge" / "solo-en-a.md").exists()
