"""AP-18: la ingesta no propone dos notas con la misma ruta.

Dos encabezados iguales producían el mismo slug, y el segundo se renombraba a
`<slug>-<len(seen_paths)>` sin volver a comprobar el resultado. Con «Alfa 2»,
«Alfa», «Alfa» la tercera recibía `alfa-2`, que ya era de la primera: en la
escritura salía como «ya existe» y su contenido no llegaba al vault, aunque en
el texto de origen era material distinto.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

CUERPO = "Contenido propio de este bloque, distinto de los demás. " * 3


def test_ap18_un_sufijo_no_cae_sobre_una_ruta_ya_propuesta(tmp_path, monkeypatch):
    import vault_io
    import vault_ingest

    monkeypatch.setenv("VAULT_ROOT", str(tmp_path))
    vault_io.set_vault_root(tmp_path)
    texto = "\n".join(
        f"# {titulo}\n{CUERPO} ({n})\n" for n, titulo in enumerate(["Alfa 2", "Alfa", "Alfa"])
    )
    r = vault_ingest.vault_ingest(texto, "07_Knowledge", "prueba", "inline", agent="pytest")
    assert r["ok"], r
    rutas = [p["path"] for p in r["proposed"]]
    assert len(rutas) == 3, rutas
    assert len(set(rutas)) == 3, rutas
