"""AP-47: lo que se escribe por el kernel se encuentra con `vault_search`.

`vault_search` busca solo sobre `99_Index/search-index.json`. `vault_write`
actualizaba esa proyección en la misma escritura que la nota; `vault_ingest` y
los `*_save` escribían por `atomic_write_text` y no la tocaban, así que la nota
existía en disco y en su sección pero la búsqueda no la veía hasta un
`vault_reindex` que nadie pedía. Se mide con el consumidor —la búsqueda—, no con
el índice.

El arreglo no importa nada desde `vault_ingest`: eso estrenaba un cruce
consulta -> autoría. Va por el gancho ya declarado `vault_io ->
vault_section_index`, y la fila sale del mismo dueño que la reconstrucción.
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

TEXTO = "\n".join([
    "# Zarzaparrilla operativa",
    "La zarzaparrilla describe el procedimiento de arranque del clúster.",
    "Incluye los pasos de verificación previos al despliegue.",
    "Y la forma de revertirlo si el arranque falla.",
])


def _vault(tmp_path, monkeypatch):
    import vault_io

    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    vault_io.set_vault_root(tmp_path)
    return vault_io


def test_ap47_la_nota_ingerida_aparece_en_la_busqueda(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    import vault_ingest
    import vault_search

    r = vault_ingest.vault_ingest(
        TEXTO, "07_Knowledge", "prueba", "inline", commit=True, agent="pytest",
    )
    assert r["ok"] and r["written"], r

    hallado = vault_search.vault_search("zarzaparrilla")
    rutas = {n.get("path") for n in hallado.get("results", [])}
    assert set(r["written"]) <= rutas, (r["written"], hallado)


def test_ap47_el_refresco_y_la_reconstruccion_escriben_la_misma_fila(tmp_path, monkeypatch):
    vault_io = _vault(tmp_path, monkeypatch)
    import vault_reindex

    nota = tmp_path / "07_Knowledge" / "arranque.md"
    nota.parent.mkdir(parents=True)
    vault_io.atomic_write_text(
        nota, "---\ntitle: Arranque\ntags: [ops]\n---\n\n" + TEXTO + "\n"
    )
    indice = tmp_path / "99_Index" / "search-index.json"

    def fila():
        notas = json.loads(indice.read_text(encoding="utf-8"))["notes"]
        return [n for n in notas if n["path"] == "07_Knowledge/arranque.md"]

    refrescada = fila()
    assert len(refrescada) == 1, refrescada
    vault_reindex.vault_reindex()
    assert fila() == refrescada
