"""El guard de `note_moved` llevaba muerto desde que se escribió (v40.16).

Comparaba `note.get("stem")` contra una clave que ningún escritor del índice
emite. Consecuencia: escribir el mismo título en dos carpetas creaba dos notas
duplicadas en silencio — lo contrario de lo que el bloque existe para hacer.
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

CUERPO = "\n".join([
    "Una nota con contenido suficiente para pasar la puerta de calidad.",
    "Segunda linea real del cuerpo con varias palabras.",
    "Tercera linea real del cuerpo con varias palabras.",
    "",
])


def test_el_indice_no_escribe_ninguna_clave_stem(tmp_path, monkeypatch):
    """Fija el hecho que dejaba muerto al guard: el escritor no emite `stem`.

    Si algún día se emitiera, este test falla y hay que decidir a conciencia
    cuál de los dos criterios manda — no tener dos.
    """
    import vault_io
    import vault_write

    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    monkeypatch.setenv("VAULT_AGENT", "prueba")
    vault_io.set_vault_root(tmp_path)
    (tmp_path / "01_Projects").mkdir(parents=True)

    vault_write.vault_write(
        folder="01_Projects",
        title="Nota Repetida",
        content=CUERPO,
        tags=["prueba"],
    )
    indice = json.loads((tmp_path / "99_Index" / "search-index.json").read_text(encoding="utf-8"))
    assert indice["notes"], "el indice tiene la nota"
    assert all("stem" not in n for n in indice["notes"])


def test_la_nota_en_otra_carpeta_se_detecta(tmp_path, monkeypatch):
    """El caso que el guard muerto dejaba pasar."""
    import vault_io
    import vault_write

    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    monkeypatch.setenv("VAULT_AGENT", "prueba")
    vault_io.set_vault_root(tmp_path)
    cuerpo = "Una nota con contenido suficiente para pasar la puerta de calidad.\nSegunda linea real del cuerpo.\nTercera linea real del cuerpo.\n"
    for carpeta in ("01_Projects", "07_Knowledge"):
        (tmp_path / carpeta).mkdir(parents=True, exist_ok=True)

    vault_write.vault_write(folder="01_Projects", title="Nota Repetida", content=cuerpo, tags=["prueba"])
    segunda = vault_write.vault_write(
        folder="07_Knowledge", title="Nota Repetida", content=cuerpo, tags=["prueba"]
    )

    assert segunda.get("ok") is False, "la segunda carpeta debe rechazarse"
    assert segunda.get("error_code") == "note_moved"
    assert "01_Projects" in segunda.get("current_path", "")