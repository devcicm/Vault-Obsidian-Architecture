"""TD-0008 · `vault_init --clean` no puede perder informacion (GOAL A).

Todas las pruebas destructivas corren en directorios temporales descartables.
Cada una demuestra estado antes -> fallo inducido -> rollback -> estado
recuperado, comparando CONTENIDO (hash) y no solo nombres.
"""
import importlib.util
import json
import os
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _cargar_vault_init():
    ruta = ROOT / "scripts" / "vault_init.py"
    spec = importlib.util.spec_from_file_location("vault_init_td0008", ruta)
    modulo = importlib.util.module_from_spec(spec)
    # El modulo importa a sus hermanos por nombre: hay que poder resolverlos.
    import sys
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    spec.loader.exec_module(modulo)
    return modulo


vi = _cargar_vault_init()


def _vault(tmp_path: Path, nombre: str = "mi-vault") -> Path:
    raiz = tmp_path / nombre
    (raiz / "00_System").mkdir(parents=True)
    (raiz / "07_Knowledge").mkdir(parents=True)
    (raiz / "00_System" / "standard-version.json").write_text(
        '{"version": "v41.24"}\n', encoding="utf-8")
    (raiz / "07_Knowledge" / "nota.md").write_text(
        "---\ntitle: Nota\n---\ncontenido importante\n", encoding="utf-8")
    (raiz / ".locks").mkdir()
    (raiz / ".locks" / "vault.lock").write_text("lock\n", encoding="utf-8")
    return raiz


def _huellas(raiz: Path) -> dict:
    """Hash por ruta relativa, sin el manifiesto de cuarentena."""
    import hashlib

    salida = {}
    for base, _, ficheros in os.walk(raiz):
        for nombre in ficheros:
            ruta = Path(base) / nombre
            rel = ruta.relative_to(raiz).as_posix()
            if rel == vi.MANIFIESTO_CUARENTENA:
                continue
            salida[rel] = hashlib.sha256(ruta.read_bytes()).hexdigest()
    return salida


def test_clean_sin_confirmacion_no_toca_nada(tmp_path):
    raiz = _vault(tmp_path)
    antes = _huellas(raiz)
    resultado = vi._preparar_clean(raiz, confirm=None)
    assert resultado["ok"] is False
    assert resultado["preparacion"]["motivo"] == "CONFIRMACION_REQUERIDA"
    assert _huellas(raiz) == antes
    assert not list(tmp_path.glob(".*cuarentena*"))


def test_confirmacion_con_otro_nombre_no_toca_nada(tmp_path):
    raiz = _vault(tmp_path)
    antes = _huellas(raiz)
    resultado = vi._preparar_clean(raiz, confirm="otro-vault")
    assert resultado["ok"] is False
    assert _huellas(raiz) == antes


def test_una_raiz_sin_marcas_de_vault_aborta(tmp_path):
    ajena = tmp_path / "documentos"
    (ajena / "proyecto").mkdir(parents=True)
    (ajena / "proyecto" / "importante.txt").write_text("no borrar\n", encoding="utf-8")
    resultado = vi._preparar_clean(ajena, confirm="documentos")
    assert resultado["ok"] is False
    assert resultado["preparacion"]["motivo"] == "VAULT_NOT_RECOGNIZED"
    assert (ajena / "proyecto" / "importante.txt").exists()


def test_dry_run_emite_plan_y_no_borra(tmp_path):
    raiz = _vault(tmp_path)
    antes = _huellas(raiz)
    resultado = vi._preparar_clean(raiz, confirm=raiz.name, dry_run=True)
    assert resultado["ok"] is True
    assert resultado["cuarentena"] is None
    assert "07_Knowledge" in resultado["preparacion"]["plan"]
    assert _huellas(raiz) == antes


def test_clean_exitoso_deja_cuarentena_verificada_y_contenido_intacto(tmp_path):
    raiz = _vault(tmp_path)
    antes = _huellas(raiz)
    resultado = vi._preparar_clean(raiz, confirm=raiz.name)
    assert resultado["ok"] is True, resultado
    cuarentena = resultado["cuarentena"]
    assert cuarentena != raiz and cuarentena.exists()
    assert _huellas(cuarentena) == antes, "la cuarentena no conserva el contenido"
    assert (cuarentena / vi.MANIFIESTO_CUARENTENA).is_file()
    assert (raiz / ".locks" / "vault.lock").exists(), "el lock debe sobrevivir"
    assert not (raiz / "07_Knowledge").exists(), "el contenido anterior no queda en el vault nuevo"
    assert not (raiz / "00_System").exists()


def test_un_fallo_de_inicializacion_restaura_el_contenido(tmp_path, monkeypatch):
    raiz = _vault(tmp_path)
    antes = _huellas(raiz)
    monkeypatch.setattr(vi, "_raiz", lambda: raiz)
    monkeypatch.setattr(vi, "_marcas_de_vault", lambda r: True)

    def _explota(**kwargs):
        raise RuntimeError("fallo inducido en REINITIALIZE")

    monkeypatch.setattr(vi, "_vault_init_sin_clean", _explota)
    resultado = vi.vault_init(clean=True, confirm=raiz.name, run_audit=False)
    assert resultado["ok"] is False
    assert resultado["error_code"] == "INIT_FAILED_AFTER_CLEAN"
    assert resultado["args"]["restauracion"]["ok"] is True
    assert _huellas(raiz) == antes, "el rollback no restauro el contenido"


def test_verificacion_fallida_hace_rollback_sin_perder_nada(tmp_path, monkeypatch):
    raiz = _vault(tmp_path)
    antes = _huellas(raiz)
    monkeypatch.setattr(vi, "_verificar_copia",
                        lambda original, copia: {"ok": False, "faltan": ["x"],
                                                 "sobran": [], "distintos": [],
                                                 "errores": [], "total": 0})
    resultado = vi._preparar_clean(raiz, confirm=raiz.name)
    assert resultado["ok"] is False
    assert resultado["preparacion"]["motivo"] == "VERIFICACION_FALLIDA"
    assert _huellas(raiz) == antes


def test_cambiar_un_byte_en_la_cuarentena_se_detecta(tmp_path):
    raiz = _vault(tmp_path)
    inventario = vi._inventario(raiz)
    cuarentena = vi._cuarentena_hermana(raiz)
    shutil.copytree(raiz, cuarentena, symlinks=True)
    (cuarentena / "07_Knowledge" / "nota.md").write_text("alterado\n", encoding="utf-8")
    verificacion = vi._verificar_copia(inventario, cuarentena)
    assert verificacion["ok"] is False
    assert "07_Knowledge/nota.md" in verificacion["distintos"]


def test_rename_imposible_degrada_a_copia_verificada(tmp_path, monkeypatch):
    raiz = _vault(tmp_path)
    antes = _huellas(raiz)
    original_rename = Path.rename

    def _rename_falla(self, destino):
        raise OSError(18, "EXDEV: cross-device link")

    monkeypatch.setattr(Path, "rename", _rename_falla)
    resultado = vi._preparar_clean(raiz, confirm=raiz.name)
    monkeypatch.setattr(Path, "rename", original_rename)
    assert resultado["ok"] is True, resultado
    assert resultado["preparacion"]["mecanismo"] == "copia"
    assert _huellas(resultado["cuarentena"]) == antes
    assert not (raiz / "07_Knowledge").exists(), "el original se borra tras verificar"


def test_un_symlink_se_registra_y_no_se_atraviesa(tmp_path):
    raiz = _vault(tmp_path)
    externo = tmp_path / "fuera"
    externo.mkdir()
    (externo / "secreto.txt").write_text("fuera del vault\n", encoding="utf-8")
    try:
        (raiz / "enlace").symlink_to(externo, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("el sistema no permite crear symlinks sin privilegios")
    inventario = vi._inventario(raiz)
    assert inventario["entradas"]["enlace"]["tipo"] == "symlink"
    assert "enlace/secreto.txt" not in inventario["entradas"], "atraveso el symlink"


def test_purga_rechaza_rutas_fuera_del_ambito(tmp_path):
    raiz = _vault(tmp_path)
    otra = tmp_path / "otra-cosa"
    otra.mkdir()
    resultado = vi._purgar_cuarentena(otra, raiz)
    assert resultado["ok"] is False
    assert resultado["motivo"] == "NO_ES_CUARENTENA_DE_ESTE_VAULT"


def test_purga_rechaza_cuarentena_sin_manifiesto(tmp_path):
    raiz = _vault(tmp_path)
    falsa = tmp_path / f".{raiz.name}.cuarentena-20260101T000000Z"
    falsa.mkdir()
    resultado = vi._purgar_cuarentena(falsa, raiz)
    assert resultado["ok"] is False
    assert resultado["motivo"] == "SIN_MANIFIESTO_DE_VERIFICACION"


def test_purga_explicita_elimina_solo_la_cuarentena_verificada(tmp_path):
    raiz = _vault(tmp_path)
    preparado = vi._preparar_clean(raiz, confirm=raiz.name)
    cuarentena = preparado["cuarentena"]
    resultado = vi._purgar_cuarentena(cuarentena, raiz)
    assert resultado["ok"] is True
    assert not cuarentena.exists()


def test_los_mensajes_no_publican_rutas_privadas(tmp_path):
    raiz = _vault(tmp_path)
    resultado = vi._preparar_clean(raiz, confirm=None)
    texto = json.dumps(resultado, ensure_ascii=False)
    assert "C:/Users" not in texto and "C:\\\\Users" not in texto


def test_version_invalida_tras_la_cuarentena_restaura(tmp_path, monkeypatch):
    """QA-RC-01: un ok:false no puede dejar el runtime a medio inicializar."""
    raiz = _vault(tmp_path)
    antes = _huellas(raiz)
    monkeypatch.setattr(vi, "_raiz", lambda: raiz)
    resultado = vi.vault_init(target_version="vNoExiste", clean=True,
                              confirm=raiz.name, run_audit=False)
    assert resultado["ok"] is False
    assert resultado["clean"]["estado"] == "ROLLBACK"
    assert resultado["args"]["restauracion"]["ok"] is True
    assert _huellas(raiz) == antes, "el rollback no restauro el contenido"


def test_fallo_al_borrar_el_original_restaura_desde_la_copia(tmp_path, monkeypatch):
    """QA-RC-01: el borrado de la via de copia puede fallar a mitad."""
    raiz = _vault(tmp_path)
    antes = _huellas(raiz)

    def _rename_falla(self, destino):
        raise OSError(18, "EXDEV: cross-device link")

    def _rmtree_falla(path, *args, **kwargs):
        raise OSError("permiso denegado al borrar")

    monkeypatch.setattr(Path, "rename", _rename_falla)
    monkeypatch.setattr("shutil.rmtree", _rmtree_falla)
    resultado = vi._preparar_clean(raiz, confirm=raiz.name)
    assert resultado["ok"] is False, resultado
    assert resultado["preparacion"]["estado"] in ("ROLLBACK",
                                                  "RECUPERACION_PENDIENTE")
    assert _huellas(raiz) == antes, "no se restauro desde la copia verificada"
    # La cuarentena sigue en pie: es la via de recuperacion.
    assert Path(resultado["preparacion"]["cuarentena"]).exists(), (
        "la cuarentena se conserva para recuperacion manual")


def test_si_la_restauracion_falla_la_cuarentena_se_conserva(tmp_path, monkeypatch):
    """QA-RC-01: recuperacion manual pendiente, sin borrar la copia."""
    raiz = _vault(tmp_path)
    preparado = vi._preparar_clean(raiz, confirm=raiz.name)
    cuarentena = preparado["cuarentena"]

    def _rename_falla(self, destino):
        raise OSError("no se puede restaurar")

    monkeypatch.setattr(Path, "rename", _rename_falla)
    restauracion = vi._restaurar(raiz, cuarentena)
    assert restauracion["ok"] is False
    assert restauracion["cuarentena"] == str(cuarentena)
    assert cuarentena.exists(), "la cuarentena no se borra si falla la restauracion"
