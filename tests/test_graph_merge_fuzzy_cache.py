"""AP-49: la caché fuzzy de `vault_graph_merge` memoiza el fallo y no cruza vaults.

Dos defectos en la misma caché de módulo. El fallo se guardaba como `None` y
se comprobaba con `is not None`, así que una entidad que no resuelve repetía
cada vez el último recurso —SequenceMatcher contra **todos** los stems—: la
memoización existía justo para el caso que no la necesita. Y la clave era solo
`(entidad, umbral)`: en un proceso que mira dos vaults, el segundo heredaba la
ruta resuelta contra el primero, que es AP-49 —un vínculo fijado por quien
llegó antes— en forma de estado y no de constante.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import vault_graph_merge as gm  # noqa: E402


class _Contador:
    def __init__(self, real):
        self.real = real
        self.llamadas = 0

    def __call__(self, *a, **k):
        self.llamadas += 1
        return self.real(*a, **k)


def test_ap49_el_fallo_queda_memoizado(monkeypatch):
    stems = {f"nota{i:04d}": f"07_Knowledge/nota{i:04d}.md" for i in range(200)}
    indice = gm._build_prefix_index(stems)
    contador = _Contador(gm.SequenceMatcher)
    monkeypatch.setattr(gm, "SequenceMatcher", contador)

    assert gm._fuzzy_resolve("zzzinexistente", stems, indice) is None
    primera = contador.llamadas
    assert primera == len(stems)  # sin prefijo común: último recurso, todos
    assert gm._fuzzy_resolve("zzzinexistente", stems, indice) is None
    assert contador.llamadas == primera, "el fallo no se memoizó"


def test_ap49_un_vault_nuevo_no_hereda_la_resolucion_del_anterior():
    viejo = {"arquitectura": "07_Knowledge/arquitectura.md"}
    nuevo = {"arquitecturas": "03_Docs/arquitecturas.md"}
    assert gm._fuzzy_resolve("arquitecturax", viejo, gm._build_prefix_index(viejo)) == (
        "07_Knowledge/arquitectura.md"
    )
    assert gm._fuzzy_resolve("arquitecturax", nuevo, gm._build_prefix_index(nuevo)) == (
        "03_Docs/arquitecturas.md"
    )


def test_ap49_cada_nota_se_lee_una_sola_vez(tmp_path, monkeypatch):
    """La segunda pasada releía del disco lo que la primera ya había extraído."""
    import vault_io

    kn = tmp_path / "07_Knowledge"
    kn.mkdir()
    (tmp_path / "00_System").mkdir()
    for i in range(5):
        (kn / f"n{i}.md").write_text(
            f"---\ntitle: N{i}\n---\n\n[[n{(i + 1) % 5}]] [[falta]]\n", encoding="utf-8"
        )
    vault_io.set_vault_root(tmp_path)

    lecturas = []
    real = Path.read_text

    def contar(self, *a, **k):
        if self.suffix == ".md":
            lecturas.append(self.name)
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", contar)
    nodes, edges, broken, _ = gm._build_wiki_link_graph()
    assert sorted(lecturas) == sorted(f"n{i}.md" for i in range(5))
    assert len(nodes) == 5 and len(edges) == 5 and len(broken) == 5
