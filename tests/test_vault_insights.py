"""El inventario declara lo que no sabe, y el snapshot no pisa a otro.

Correcciones que pidio la revision independiente del 2026-11-09 sobre
`vault_insights`:

- una nota **ilegible** no desaparece en silencio: el inventario lleva
  `poblacion`, `errores` clasificados y `complete`, y **comparar rechaza**
  una captura incompleta (mezclar lo que falta con lo que cambio produce
  diferencias que no existen);
- un cambio **solo de metadatos** (`status`, `tags`) se detecta: hay dos
  hashes, el del cuerpo y el de los campos significativos;
- dos capturas de **vaults distintos** no se comparan;
- un **renombrado** es un renombrado, no una baja y un alta;
- un snapshot **no pisa** a otro sin permiso, y se escribe atomico.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apoyo import ROOT as REPO_ROOT  # el conftest ya pone el path

import vault_insights
from vault.gobernanza.insights import ESQUEMA, SnapshotInvalido


def _vault(tmp_path: Path) -> Path:
    raiz = tmp_path / "vault"
    (raiz / "07_Knowledge").mkdir(parents=True)
    (raiz / "00_System").mkdir(parents=True)
    (raiz / "07_Knowledge" / "uno.md").write_text(
        "---\ntitle: Uno\ntype: note\nstatus: draft\ntags: [a]\n"
        "createdAt: 2026-01-01T00:00:00.000Z\n---\n\nCuerpo de la nota uno.\n",
        encoding="utf-8")
    (raiz / "07_Knowledge" / "dos.md").write_text(
        "---\ntitle: Dos\ntype: note\nstatus: reviewed\n---\n\n"
        "Cuerpo de la nota dos.\n", encoding="utf-8")
    vault_insights.inicializar_identidad(raiz)
    return raiz


def test_el_inventario_es_de_solo_lectura(tmp_path):
    raiz = _vault(tmp_path)
    antes = {p: p.stat().st_mtime_ns for p in raiz.rglob("*") if p.is_file()}

    datos = vault_insights.inventario(raiz)

    despues = {p: p.stat().st_mtime_ns for p in raiz.rglob("*") if p.is_file()}
    assert datos["ok"] and datos["total"] == 2, datos
    assert antes == despues, "el inventario escribió en el vault"
    assert datos["schema"] == ESQUEMA
    assert datos["complete"] is True, datos
    assert datos["errores"] == []
    assert datos["poblacion"]["notas_encontradas"] == 2
    assert datos["poblacion"]["notas_leidas"] == 2
    assert datos["vault_id"], datos


def test_una_nota_ilegible_se_declara_y_el_inventario_no_es_completo(tmp_path, monkeypatch):
    """La condicion simulada que la revision reprodujo: `ok: true` sin mas.

    Ahora el inventario dice `complete: false` y **enumera** el error.
    """
    raiz = _vault(tmp_path)
    real = Path.read_text

    def falsa(self, *args, **kwargs):
        if self.name == "dos.md":
            raise PermissionError("simulado")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", falsa)
    datos = vault_insights.inventario(raiz)
    monkeypatch.undo()

    assert datos["complete"] is False, datos
    assert datos["total"] == 1, datos
    assert datos["errores"], datos
    assert datos["errores"][0]["tipo"] == "ilegible", datos["errores"]
    assert datos["errores"][0]["path"].endswith("dos.md")


def test_una_captura_incompleta_no_se_compara(tmp_path, monkeypatch):
    """Mezclar lo que falta con lo que cambio produce diferencias falsas."""
    raiz = _vault(tmp_path)
    real = Path.read_text

    def falsa(self, *args, **kwargs):
        if self.name == "dos.md":
            raise PermissionError("simulado")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", falsa)
    incompleto = vault_insights.inventario(raiz)
    monkeypatch.undo()
    completo = vault_insights.inventario(raiz)

    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps(incompleto), encoding="utf-8")
    b.write_text(json.dumps(completo), encoding="utf-8")

    with pytest.raises(SnapshotInvalido) as exc:
        vault_insights.comparar(str(a), str(b))
    assert exc.value.causa == "SNAPSHOT_INCOMPLETO"


def test_un_cambio_solo_de_metadatos_se_detecta(tmp_path):
    """El caso de la revision: solo cambia `status: draft` → `approved`."""
    raiz = _vault(tmp_path)
    a = vault_insights.inventario(raiz)
    (raiz / "07_Knowledge" / "uno.md").write_text(
        "---\ntitle: Uno\ntype: note\nstatus: approved\ntags: [a]\n"
        "createdAt: 2026-01-01T00:00:00.000Z\n---\n\nCuerpo de la nota uno.\n",
        encoding="utf-8")
    b = vault_insights.inventario(raiz)

    pa = tmp_path / "a.json"
    pb = tmp_path / "b.json"
    pa.write_text(json.dumps(a), encoding="utf-8")
    pb.write_text(json.dumps(b), encoding="utf-8")

    informe = vault_insights.comparar(str(pa), str(pb))
    assert informe["modificadas"] == [], informe
    assert informe["metadatos_modificados"] == ["07_Knowledge/uno.md"], informe


def test_un_renombrado_no_es_una_baja_y_un_alta(tmp_path):
    raiz = _vault(tmp_path)
    a = vault_insights.inventario(raiz)
    (raiz / "07_Knowledge" / "uno.md").rename(raiz / "07_Knowledge" / "uno-renombrada.md")
    b = vault_insights.inventario(raiz)

    pa = tmp_path / "a.json"
    pb = tmp_path / "b.json"
    pa.write_text(json.dumps(a), encoding="utf-8")
    pb.write_text(json.dumps(b), encoding="utf-8")

    informe = vault_insights.comparar(str(pa), str(pb))
    assert informe["anadidas"] == [], informe
    assert informe["retiradas"] == [], informe
    assert informe["renombradas"], informe
    par = informe["renombradas"][0]
    assert par["desde"].endswith("uno.md") and par["hasta"].endswith("uno-renombrada.md"), par


def test_vaults_distintos_no_se_comparan(tmp_path):
    """Dos poblaciones distintas no son comparables."""
    uno = vault_insights.inventario(_vault(tmp_path / "a"))
    otro = vault_insights.inventario(_vault(tmp_path / "b"))
    pa = tmp_path / "a.json"
    pb = tmp_path / "b.json"
    pa.write_text(json.dumps(uno), encoding="utf-8")
    pb.write_text(json.dumps(otro), encoding="utf-8")

    with pytest.raises(SnapshotInvalido) as exc:
        vault_insights.comparar(str(pa), str(pb))
    assert exc.value.causa == "IDENTITY_MISMATCH"


def test_el_snapshot_no_pisa_a_otro_sin_permiso(tmp_path):
    raiz = _vault(tmp_path)
    datos = vault_insights.inventario(raiz)
    destino = tmp_path / "datos" / "snap.json"

    assert vault_insights.guardar(datos, str(destino), raiz)["ok"]
    with pytest.raises(SnapshotInvalido) as exc:
        vault_insights.guardar(datos, str(destino), raiz)
    assert exc.value.causa == "SNAPSHOT_EXISTE"
    # Con permiso, si.
    assert vault_insights.guardar(datos, str(destino), raiz, force=True)["ok"]


def test_el_snapshot_no_vive_dentro_del_vault(tmp_path):
    raiz = _vault(tmp_path)
    datos = vault_insights.inventario(raiz)
    with pytest.raises(SnapshotInvalido) as exc:
        vault_insights.guardar(datos, str(raiz / "snap.json"), raiz)
    assert exc.value.causa == "INVALID_PATH"
    assert not (raiz / "snap.json").exists()


def test_los_codigos_nuevos_estan_en_el_catalogo():
    from vault.kernel.errores import ERROR_CATALOG

    for codigo in ("SNAPSHOT_INCOMPLETO", "IDENTITY_MISMATCH", "SNAPSHOT_EXISTE"):
        assert codigo in ERROR_CATALOG, codigo


def test_el_enlace_entrante_se_cuenta_con_el_extractor_del_dueno(tmp_path):
    """La cuenta anterior era presencia textual: coincidencias incidentales."""
    raiz = _vault(tmp_path)
    (raiz / "07_Knowledge" / "tres.md").write_text(
        "---\ntitle: Tres\n---\n\n[[uno]] y [[dos]].\n", encoding="utf-8")
    datos = vault_insights.inventario(raiz)
    por_ruta = {n["path"]: n["enlaces_entrantes"] for n in datos["notas"]}
    assert por_ruta["07_Knowledge/uno.md"] == 1, por_ruta
    assert por_ruta["07_Knowledge/dos.md"] == 1, por_ruta
    assert por_ruta["07_Knowledge/tres.md"] == 0, por_ruta


def test_identidad_se_inicializa_una_vez_y_sobrevive_a_renombrado(tmp_path):
    raiz = _vault(tmp_path)
    identidad = vault_insights.inicializar_identidad(raiz)
    assert identidad["created"] is False
    antes = vault_insights.inventario(raiz)
    movido = raiz.rename(tmp_path / "vault-renombrado")
    despues = vault_insights.inventario(movido)
    assert antes["vault_id"] == despues["vault_id"] == identidad["vault_id"]
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps(antes), encoding="utf-8")
    b.write_text(json.dumps(despues), encoding="utf-8")
    assert vault_insights.comparar(str(a), str(b))["ok"]


def test_inventario_no_crea_identidad_ausente(tmp_path):
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    with pytest.raises(SnapshotInvalido):
        vault_insights.inventario(raiz)
    assert not (raiz / "00_System" / "insights-identidad.json").exists()
    primera = vault_insights.inicializar_identidad(raiz)
    segunda = vault_insights.inicializar_identidad(raiz)
    assert primera["created"] and not segunda["created"]
    assert primera["vault_id"] == segunda["vault_id"]


@pytest.mark.parametrize("campo", ["vault_id", "complete", "poblacion", "schema"])
def test_comparar_rechaza_campos_obligatorios_ausentes(tmp_path, campo):
    raiz = _vault(tmp_path)
    uno = vault_insights.inventario(raiz)
    dos = dict(uno)
    dos.pop(campo)
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps(uno), encoding="utf-8")
    b.write_text(json.dumps(dos), encoding="utf-8")
    with pytest.raises(SnapshotInvalido):
        vault_insights.comparar(str(a), str(b))


def test_comparar_rechaza_esquema_antiguo_aun_si_ambos_coinciden(tmp_path):
    raiz = _vault(tmp_path)
    captura = vault_insights.inventario(raiz)
    captura["schema"] = 2
    a = tmp_path / "a.json"
    a.write_text(json.dumps(captura), encoding="utf-8")
    with pytest.raises(SnapshotInvalido) as exc:
        vault_insights.comparar(str(a), str(a))
    assert exc.value.causa == "SCHEMA_MISMATCH"


def test_utf8_invalido_deja_inventario_incompleto(tmp_path):
    raiz = _vault(tmp_path)
    (raiz / "07_Knowledge" / "dos.md").write_bytes(b"\xff")
    datos = vault_insights.inventario(raiz)
    assert datos["complete"] is False
    assert datos["errores"][0]["tipo"] == "codificacion"


def test_cuerpos_duplicados_no_inventan_renombrados(tmp_path):
    raiz = _vault(tmp_path)
    uno = raiz / "07_Knowledge" / "uno.md"
    dos = raiz / "07_Knowledge" / "dos.md"
    dos.write_bytes(uno.read_bytes())
    antes = vault_insights.inventario(raiz)
    uno.rename(raiz / "07_Knowledge" / "tres.md")
    despues = vault_insights.inventario(raiz)
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps(antes), encoding="utf-8")
    b.write_text(json.dumps(despues), encoding="utf-8")
    resultado = vault_insights.comparar(str(a), str(b))
    assert resultado["renombradas"] == []
    assert resultado["retiradas"] == ["07_Knowledge/uno.md"]
    assert resultado["anadidas"] == ["07_Knowledge/tres.md"]


def test_dos_guardados_concurrentes_no_se_pisan(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    raiz = _vault(tmp_path)
    datos = vault_insights.inventario(raiz)
    destino = tmp_path / "snapshot.json"
    def escribir(_):
        try:
            vault_insights.guardar(datos, str(destino), raiz)
            return "guardado"
        except SnapshotInvalido as exc:
            return exc.causa
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(escribir, range(2)))
    assert sorted(resultados) == ["SNAPSHOT_EXISTE", "guardado"]
    assert json.loads(destino.read_text(encoding="utf-8"))["vault_id"] == datos["vault_id"]


def test_guardar_sin_hardlinks_no_pisa_y_limpia_el_temporal(tmp_path, monkeypatch):
    from vault.gobernanza import insights

    raiz = _vault(tmp_path)
    datos = vault_insights.inventario(raiz)
    destino = tmp_path / "snapshot.json"
    destino.write_text("contenido previo", encoding="utf-8")

    def sin_hardlinks(*_args, **_kwargs):
        raise OSError("hardlinks no disponibles")

    monkeypatch.setattr(insights.os, "link", sin_hardlinks)
    with pytest.raises(OSError, match="hardlinks no disponibles"):
        vault_insights.guardar(datos, str(destino), raiz)
    assert destino.read_text(encoding="utf-8") == "contenido previo"
    assert not list(tmp_path.glob("snapshot.json.tmp.*"))


def test_criterios_de_poblacion_distintos_no_se_comparan(tmp_path):
    raiz = _vault(tmp_path)
    uno = vault_insights.inventario(raiz)
    dos = dict(uno)
    dos["poblacion"] = dict(uno["poblacion"], criterio="otra poblacion")
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps(uno), encoding="utf-8")
    b.write_text(json.dumps(dos), encoding="utf-8")
    with pytest.raises(SnapshotInvalido):
        vault_insights.comparar(str(a), str(b))


def test_hashes_invalidos_no_producen_cambios_falsos(tmp_path):
    raiz = _vault(tmp_path)
    datos = vault_insights.inventario(raiz)
    valido = tmp_path / "valido.json"
    invalido = tmp_path / "invalido.json"
    valido.write_text(json.dumps(datos), encoding="utf-8")
    for campo in ("hash_cuerpo", "hash_metadatos"):
        for valor in ("", "g" * 16, "a" * 15):
            copia = json.loads(json.dumps(datos))
            copia["notas"][0][campo] = valor
            invalido.write_text(json.dumps(copia), encoding="utf-8")
            with pytest.raises(SnapshotInvalido):
                vault_insights.comparar(str(valido), str(invalido))


@pytest.mark.parametrize("estado,causa", [("ausente", "IDENTITY_MISSING"), ("corrupta", "DATA_FILE_CORRUPT")])
def test_la_identidad_ausente_o_corrupta_tiene_su_propio_codigo(tmp_path, estado, causa):
    """A4: a missing identity is not two different vaults, and is never created implicitly."""
    from vault.gobernanza.insights import FICHERO_IDENTIDAD
    from vault.kernel.errores import ERROR_CATALOG

    raiz = _vault(tmp_path)
    fichero = raiz / FICHERO_IDENTIDAD
    if estado == "ausente":
        fichero.unlink(missing_ok=True)
    else:
        fichero.write_text("{roto", encoding="utf-8")
    before = fichero.read_bytes() if fichero.exists() else None
    with pytest.raises(SnapshotInvalido) as exc:
        vault_insights.inventario(raiz)
    assert exc.value.causa == causa
    assert causa in ERROR_CATALOG
    assert (fichero.read_bytes() if fichero.exists() else None) == before
    if causa == "IDENTITY_MISSING":
        assert ERROR_CATALOG[causa]["recovery"]["args"] == ["--inicializar-identidad"]
