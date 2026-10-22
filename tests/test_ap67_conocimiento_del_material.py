"""AP-67 — el material que el agente opera tiene que estar en la memoria.

El caso que la destapó: en un vault real se ejecutaron cinco scripts de
prueba del TTS y el vault no tenía ni una nota que los apuntara. El
recorrido de `vault_code_sync` solo miraba los ficheros que ya tenían
`@vault:` —es decir, solo veía lo que ya estaba enlazado—, así que el hueco
no salía en ninguna parte.

Las dos comprobaciones que se añaden:

- `proyecto_sin_conocimiento`: un proyecto enlazado al vault sin una sola
  nota de su código. Es decidible, y es el caso medido.
- `fuente_sin_nota`: los ficheros del repositorio que ninguna nota apunta.
  Se informa con el recuento y una muestra: el número dice la verdad, la
  lista orienta.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))


def _proyecto_con_codigo(tmp_path, con_notas):
    """Un vault con un proyecto enlazado y, opcionalmente, notas de código."""
    import vault_io

    raiz = tmp_path / "v"
    repo = tmp_path / "repo"
    (raiz / "00_System" / ".local").mkdir(parents=True)
    (raiz / "11_Code" / "mi-api").mkdir(parents=True)
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "auth.py").write_text("def login():\n    pass\n", encoding="utf-8")
    (repo / "src" / "perfil.py").write_text("def perfil():\n    pass\n", encoding="utf-8")

    vault_io.set_vault_root(raiz)
    # La ruta local del repo vive fuera de git: `00_System/.local/project-paths.json`
    # (la escribe `vault_project --link`; aquí se escribe a mano para que el
    # test no dependa del CLI).
    (raiz / "00_System" / ".local" / "project-paths.json").write_text(
        json.dumps({"mi-api": str(repo)}), encoding="utf-8")

    if con_notas:
        (raiz / "11_Code" / "mi-api" / "auth.md").write_text(
            "---\ntitle: auth\ntype: code\nstatus: draft\nid: n1\n"
            "createdAt: 2026-10-21T10:00:00.000Z\nupdatedAt: 2026-10-21T10:00:00.000Z\n"
            "cia_integrity: medium\ncia_availability: medium\n"
            "cia_sensitivity: internal\nagent: test\ntags: [x]\n"
            f"source_file: {repo / 'src' / 'auth.py'}\n---\n\n"
            "# auth\n\nAutenticación.\n",
            encoding="utf-8")
    return raiz, repo


def test_un_proyecto_enlazado_sin_notas_es_un_hueco_decidible(tmp_path, monkeypatch):
    import vault_code_sync
    import vault_io

    raiz, repo = _proyecto_con_codigo(tmp_path, con_notas=False)
    monkeypatch.setenv("VAULT_ROOT", str(raiz))
    try:
        env = vault_code_sync.vault_code_sync(project="mi-api", scan_dir=str(repo))
    finally:
        vault_io.reset_vault_root()

    assert env["proyecto_sin_conocimiento"], env
    assert env["summary"]["proyecto_sin_conocimiento"] == 1
    # El hallazgo dice qué norma lo exige: quien lo lee tiene que saber a qué
    # obedecer (y el resto del toolkit lo hace así: `issues.*` lleva su
    # `norm_code`).
    assert env["proyecto_sin_conocimiento"][0]["norm"] == "AP-67"
    # Y el veredicto lo dice: un proyecto que el vault declara conocer y no
    # conoce no es un vault limpio.
    assert env["status"] == "gaps_found"


def test_el_fichero_que_ninguna_nota_apunta_se_cuenta(tmp_path, monkeypatch):
    import vault_code_sync
    import vault_io

    raiz, repo = _proyecto_con_codigo(tmp_path, con_notas=True)
    monkeypatch.setenv("VAULT_ROOT", str(raiz))
    try:
        env = vault_code_sync.vault_code_sync(project="mi-api", scan_dir=str(repo))
    finally:
        vault_io.reset_vault_root()

    # `auth.py` tiene nota; `perfil.py` no. El segundo se cuenta.
    assert env["summary"]["fuente_sin_nota"] == 1, env["fuente_sin_nota"]
    assert any("perfil.py" in f["source_file"] for f in env["fuente_sin_nota"])
    # Y cada hallazgo dice qué norma lo exige (AP-67).
    assert all(f["norm"] == "AP-67" for f in env["fuente_sin_nota"])
    # Y el proyecto enlazado ya tiene conocimiento: no es un hueco.
    assert env["summary"]["proyecto_sin_conocimiento"] == 0
