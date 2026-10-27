"""AUTORIDAD de los actos: el esquema no basta (QA-R17-QG02-01) y su
endurecimiento (QA-R18-AUTH-01..04, dictamen 2369be8).

Estas pruebas usan el verificador REAL contra un repositorio DESCARTABLE
(tmp_path) con commits reales: demuestran la MECANICA (existencia, canal,
contrato de acto, custodia independiente, vigencia, identidad). NO demuestran
que el propietario haya ratificado nada en el repositorio real: eso exigiria
una fuente declarada Y ratificada por el propietario (DEC-03).

Las cuatro familias de defecto:
  AUTH-01  registro no ratificado (PROPUESTA/DRAFT/PENDING/desconocido),
           sin acto de ratificacion, o autoactivado por si mismo.
  AUTH-02  `firmante` libre con `autoridad` registrada distinta; autoridad
           desconocida; identidad incompatible con el canal.
  AUTH-03  commit consultivo que menciona todos los tokens pero NO ratifica
           expresamente; y los estados PROPUESTO/CONSULTADO/RECHAZADO/REVOCADO.
  AUTH-04  custodia sin custodio, con custodio no admitido, sin
           norma/ruta/huella, expirada, o que pretende autorizar operaciones
           destructivas (archivar/trasladar/purgar).
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HUELLA = "c" * 64
FECHA = "2026-02-02"


def _cargar(nombre):
    ruta = ROOT / "audits" / "fase2" / f"{nombre}.py"
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


verificador_mod = _cargar("verificador_actos")
contrato = _cargar("politica_certificacion_compuesta")

CANAL = "refs/heads/canal/autoridad"


def _git(repo: Path, *args: str) -> str:
    p = subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    assert p.returncode == 0, f"git {' '.join(args)} fallo: {p.stderr[-300:]}"
    return (p.stdout or "").strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "canal/autoridad")
    _git(repo, "config", "user.email", "autoridad@example.invalid")
    _git(repo, "config", "user.name", "Autoridad de Prueba")
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "base.txt")
    _git(repo, "commit", "-q", "-m", "base")
    return repo


def _commit(repo: Path, nombre: str, mensaje: str, rama: str = "canal/autoridad") -> str:
    (repo / nombre).write_text(nombre + "\n", encoding="utf-8")
    _git(repo, "add", nombre)
    if rama != "canal/autoridad":
        _git(repo, "checkout", "-q", "-b", rama)
    _git(repo, "commit", "-q", "-m", mensaje)
    sha = _git(repo, "rev-parse", "HEAD")
    if rama != "canal/autoridad":
        _git(repo, "checkout", "-q", "canal/autoridad")
    return sha


def _acta_ratificacion(residuo="INC-0001", norma="AP-36",
                        ruta="../../vault-backups", decision="DEC-77",
                        autoridad="autoridad-x", accion="RATIFICAR",
                        estado="RATIFICADO", huella=HUELLA, fecha=FECHA,
                        canal=CANAL) -> str:
    return ("\n".join([
        f"ACTO: RATIFICACION",
        f"ACCION: {accion}",
        f"ESTADO: {estado}",
        f"DECISION: {decision}",
        f"AUTORIDAD: {autoridad}",
        f"ALCANCE: {residuo}",
        f"RESIDUO: {residuo}",
        f"NORMA: {norma}",
        f"RUTA: {ruta}",
        f"HUELLA: {huella}",
        f"FECHA: {fecha}",
        f"CANAL: {canal}",
    ]))


def _acta_custodia(residuo="INC-0001", norma="AP-36",
                    ruta="../../vault-backups", custodio="custodio-1",
                    autoridad="autoridad-x", operaciones="lectura, inventario",
                    vigencia="2026-01-01/2099-12-31", canal=CANAL) -> str:
    return ("\n".join([
        "ACTO: CUSTODIA",
        "ACCION: CUSTODIAR",
        "ESTADO: VIGENTE",
        f"CUSTODIO: {custodio}",
        f"AUTORIDAD: {autoridad}",
        "ACTID: ACTA-77",
        f"RESIDUO: {residuo}",
        f"NORMA: {norma}",
        f"RUTA: {ruta}",
        f"HUELLA: {HUELLA}",
        f"OPERACIONES: {operaciones}",
        f"VIGENCIA: {vigencia}",
        f"CANAL: {canal}",
        f"FECHA: {FECHA}",
    ]))


def _registro(estado="RATIFICADO", ratification=None, custodios=None,
              alias=None, correo=None, canales=None) -> dict:
    return {
        "id": "autoridades-de-decision-v1",
        "version": "1",
        "estado": estado,
        "ratificacion": ratification if ratification is not None else {
            "acto": "", "canal": "", "fecha": "", "ratificado_por": ""},
        "custodios": custodios if custodios is not None else ["custodio-1"],
        "autoridades": {
            "autoridad-x": {
                "canales": canales if canales is not None else [CANAL],
                "alias": alias if alias is not None else [],
                "identidad_git": {"correo": correo} if correo else {},
            }
        },
    }


def _decision(referencia: str, custodia: str, **cambios) -> dict:
    base = {
        "id": "DEC-77",
        "estado": "RATIFICADO",
        "autoridad": "autoridad-x",
        "firmante": "autoridad-x",
        "fecha": FECHA,
        "referencia": referencia,
        "alcance": {"residuo": "INC-0001", "norma": "AP-36",
                    "ruta": "../../vault-backups", "huella": HUELLA},
        "custodia": {"id": "ACTA-77", "referencia": custodia,
                     "verificada": True},
    }
    base.update(cambios)
    return base


def _hallazgo() -> dict:
    return {"id": "INC-0001", "norm": "AP-36", "path": "../../vault-backups",
            "huella": HUELLA}


def _verificador(repo: Path, registro=None):
    return verificador_mod.VerificadorActosGit(
        repo, registro if registro is not None else _registro())


def _registro_ratificado(repo: Path, **cambios) -> dict:
    """Registro EN VIGOR: su propio acto de ratificacion existe y es alcanzable."""
    sha = _commit(repo, "ratificacion.md", "\n".join([
        "ACTO: RATIFICACION",
        "ACCION: RATIFICAR",
        "ESTADO: RATIFICADO",
        "OBJETO: autoridades-de-decision-v1",
        "VERSION: 1",
        f"FECHA: {FECHA}",
    ]))
    registro = _registro(ratification={
        "acto": sha, "canal": CANAL, "fecha": FECHA,
        "ratificado_por": "autoridad@example.invalid"}, **cambios)
    return registro


# ── AUTH-01: el registro tiene que estar ratificado ─────────────────────────

def test_un_registro_propuesto_no_es_fuente_confiable():
    for estado in ("PROPUESTA", "DRAFT", "PENDING", "", "RATIFICADO_ISH"):
        registro = _registro(estado=estado)
        en_vigor, motivos = verificador_mod.registro_en_vigor(registro)
        assert not en_vigor, f"estado={estado!r} no puede estar en vigor"
        assert any("REGISTRO_NO_RATIFICADO" in m for m in motivos)
        assert verificador_mod.verificador_desde_registro(ROOT, registro) is None


def test_un_registro_sin_acto_de_ratificacion_no_esta_en_vigor(tmp_path):
    """Un SHA con forma de SHA no es un acto: tiene que EXISTIR."""
    repo = _repo(tmp_path)
    registro = _registro(ratification={"acto": "a" * 40, "canal": CANAL,
                                        "fecha": FECHA,
                                        "ratificado_por": "autoridad@example.invalid"})
    verificador = _verificador(repo, registro)
    assert not verificador.en_vigor()
    assert any("ACTO_INEXISTENTE" in m for m in verificador.motivos_vigor())
    assert verificador_mod.verificador_desde_registro(repo, registro) is None


def test_un_registro_no_ratificado_bloquea_aunque_los_actos_sean_reales(tmp_path):
    """AUTH-01: con commits que CUMPLEN el contrato, un registro PROPUESTA no
    puede acreditar un PASS."""
    repo = _repo(tmp_path)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit(repo, "custodia.md", _acta_custodia())
    registro = _registro(estado="PROPUESTA")
    assert verificador_mod.verificador_desde_registro(repo, registro) is None
    r = _evaluar(repo, _decision(acto, custodia), registro)
    assert r["estado"] == "BLOCKED"
    assert any("SIN_FUENTE_DE_AUTORIDAD" in m or "REGISTRO_NO_EN_VIGOR" in m
               for m in r["motivos"])


def test_un_registro_que_se_autoafirma_sin_acto_no_entra_en_vigor(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro(ratification={"acto": "a" * 40, "canal": CANAL,
                                        "fecha": FECHA,
                                        "ratificado_por": "autoridad@example.invalid"})
    verificador = _verificador(repo, registro)
    assert not verificador.en_vigor()
    assert any("ACTO" in m for m in verificador.motivos_vigor())


def test_un_acto_de_ratificacion_consultivo_no_pone_en_vigor_el_registro(tmp_path):
    """Un commit que MENCIONA el registro pero no ratifica expresamente."""
    repo = _repo(tmp_path)
    sha = _commit(repo, "consulta.md", "\n".join([
        "ACTO: RATIFICACION",
        "ACCION: CONSULTAR",
        "ESTADO: CONSULTADO",
        "OBJETO: autoridades-de-decision-v1",
        "VERSION: 1",
        f"FECHA: {FECHA}",
    ]))
    registro = _registro(ratification={"acto": sha, "canal": CANAL,
                                        "fecha": FECHA,
                                        "ratificado_por": "autoridad@example.invalid"})
    verificador = _verificador(repo, registro)
    assert not verificador.en_vigor()
    assert any("NO_RATIFICA" in m for m in verificador.motivos_vigor())


def test_un_registro_ratificado_por_otro_autor_no_entra_en_vigor(tmp_path):
    repo = _repo(tmp_path)
    sha = _commit(repo, "ratificacion.md", "\n".join([
        "ACTO: RATIFICACION", "ACCION: RATIFICAR", "ESTADO: RATIFICADO",
        "OBJETO: autoridades-de-decision-v1", "VERSION: 1", f"FECHA: {FECHA}",
    ]))
    registro = _registro(ratification={"acto": sha, "canal": CANAL,
                                        "fecha": FECHA,
                                        "ratificado_por": "otra-persona@example.invalid"})
    verificador = _verificador(repo, registro)
    assert not verificador.en_vigor()
    assert any("RATIFICADO_POR_OTRO" in m for m in verificador.motivos_vigor())


def test_un_registro_ratificado_por_su_propia_acta_si_esta_en_vigor(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    assert verificador is not None
    assert verificador.en_vigor()


# ── AUTH-02: identidad de autoridad ─────────────────────────────────────────

def test_un_firmante_libre_con_autoridad_registrada_distinta_se_rechaza(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit(repo, "custodia.md", _acta_custodia())
    decision = _decision(acto, custodia)
    decision["firmante"] = "alguien-que-no-es-autoridad"
    ok, motivos = verificador.verificar_acto(decision, _hallazgo())
    assert not ok
    assert any("IDENTIDADES_CONTRADICTORIAS" in m or "AUTORIDAD_DESCONOCIDA" in m
               for m in motivos)


def test_una_autoridad_desconocida_se_rechaza(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit(repo, "custodia.md", _acta_custodia())
    decision = _decision(acto, custodia, autoridad="inventada", firmante="inventada")
    ok, motivos = verificador.verificar_acto(decision, _hallazgo())
    assert not ok
    assert any("AUTORIDAD_DESCONOCIDA" in m for m in motivos)


def test_un_alias_que_apunta_a_otra_autoridad_se_rechaza(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit(repo, "custodia.md", _acta_custodia())
    decision = _decision(acto, custodia, autoridad="autoridad-x", firmante="alias-ajeno")
    ok, motivos = verificador.verificar_acto(decision, _hallazgo())
    assert not ok
    assert any("AUTORIDAD_DESCONOCIDA" in m or "IDENTIDADES_CONTRADICTORIAS" in m
               for m in motivos)


def test_una_identidad_incompatible_con_el_canal_se_rechaza(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    registro["autoridades"]["autoridad-x"]["identidad_git"] = {
        "correo": "alguien-otro@example.invalid"}
    verificador = verificador_mod.VerificadorActosGit(repo, registro)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit(repo, "custodia.md", _acta_custodia())
    ok, motivos = verificador.verificar_acto(_decision(acto, custodia), _hallazgo())
    assert not ok
    assert any("IDENTIDAD_INCOMPATIBLE" in m for m in motivos)


# ── AUTH-03: ratificacion expresa ───────────────────────────────────────────

def test_un_commit_consultivo_que_mentciona_todos_los_datos_no_ratifica(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    consultivo = _commit(repo, "consulta.md", "\n".join([
        "Propongo tratar DEC-77 (AP-36, ../../vault-backups, "
        f"huella {HUELLA}) como ratificado.",
    ]))
    custodia = _commit(repo, "custodia.md", _acta_custodia())
    ok, motivos = verificador.verificar_acto(
        _decision(consultivo, custodia), _hallazgo())
    assert not ok
    assert any("ACTO_" in m for m in motivos)


def test_los_estados_no_ratificados_se_distinguen(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    custodia = _commit(repo, "custodia.md", _acta_custodia())
    for estado in ("PROPUESTO", "CONSULTADO", "RECHAZADO", "REVOCADO"):
        sha = _commit(repo, f"acto-{estado}.md",
                      _acta_ratificacion(estado=estado))
        ok, motivos = verificador.verificar_acto(
            _decision(sha, custodia), _hallazgo())
        assert not ok, f"estado={estado} no puede ratificar"
        assert any("ESTADO" in m or "NO_RATIFICA" in m for m in motivos)


def test_una_accion_que_no_ratifica_se_rechaza(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    custodia = _commit(repo, "custodia.md", _acta_custodia())
    for accion in ("PROPONER", "CONSULTAR", "RECHAZAR"):
        sha = _commit(repo, f"acto-{accion}.md",
                      _acta_ratificacion(accion=accion))
        ok, motivos = verificador.verificar_acto(
            _decision(sha, custodia), _hallazgo())
        assert not ok, f"accion={accion} no ratifica"
        assert any("ACTO_NO_RATIFICA" in m or "ACCION_INVALIDA" in m
                   for m in motivos)


def test_un_acto_con_alcance_distinto_no_ratifica(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    custodia = _commit(repo, "custodia.md", _acta_custodia())
    sha = _commit(repo, "acto.md", _acta_ratificacion(residuo="INC-OTRO"))
    ok, motivos = verificador.verificar_acto(_decision(sha, custodia), _hallazgo())
    assert not ok
    assert any("ALCANCE_NO_COINCIDE" in m for m in motivos)


def test_un_acto_que_no_declara_el_canal_se_rechaza(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    custodia = _commit(repo, "custodia.md", _acta_custodia())
    sha = _commit(repo, "acto.md", _acta_ratificacion(canal="refs/heads/otro"))
    ok, motivos = verificador.verificar_acto(_decision(sha, custodia), _hallazgo())
    assert not ok
    assert any("CANAL_NO_DECLARADO" in m for m in motivos)


# ── AUTH-04: custodia ───────────────────────────────────────────────────────

def test_una_custodia_sin_custodio_se_rechaza(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit(repo, "custodia.md",
                       "\n".join(l for l in _acta_custodia().splitlines()
                                 if not l.startswith("CUSTODIO:")))
    ok, motivos = verificador.verificar_custodia(
        _decision(acto, custodia), _hallazgo())
    assert not ok
    assert any("CUSTODIA_SIN_CUSTODIO" in m for m in motivos)


def test_un_custodio_no_admitido_se_rechaza(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit(repo, "custodia.md", _acta_custodia(custodio="desconocido"))
    ok, motivos = verificador.verificar_custodia(
        _decision(acto, custodia), _hallazgo())
    assert not ok
    assert any("CUSTODIO_NO_ADMITIDO" in m for m in motivos)


def test_una_custodia_sin_norma_ruta_ni_huella_se_rechaza(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit(repo, "custodia.md", "\n".join(
        l for l in _acta_custodia().splitlines()
        if not l.startswith(("NORMA:", "RUTA:", "HUELLA:"))))
    ok, motivos = verificador.verificar_custodia(
        _decision(acto, custodia), _hallazgo())
    assert not ok
    assert any("CUSTODIA_SIN_" in m for m in motivos)


def test_una_custodia_expirada_se_rechaza(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit(repo, "custodia.md",
                       _acta_custodia(vigencia="2020-01-01/2020-12-31"))
    ok, motivos = verificador.verificar_custodia(
        _decision(acto, custodia), _hallazgo())
    assert not ok
    assert any("CUSTODIA_EXPIRADA" in m for m in motivos)


def test_una_custodia_no_puede_autorizar_operaciones_destructivas(tmp_path):
    """AUTH-04: custodiar no autoriza archivar, trasladar ni purgar."""
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit(repo, "custodia.md",
                       _acta_custodia(operaciones="lectura, archivar, purgar"))
    ok, motivos = verificador.verificar_custodia(
        _decision(acto, custodia), _hallazgo())
    assert not ok
    assert any("CUSTODIA_NO_AUTORIZA_OPERACIONES_DESTRUCTIVAS" in m
               for m in motivos)


# ── extremo a extremo ───────────────────────────────────────────────────────

def _evaluar(repo: Path, decision: dict, registro=None):
    verificador = (verificador_mod.verificador_desde_registro(repo, registro)
                   if registro is not None
                   else verificador_mod.verificador_desde_registro(repo, None))
    return contrato.evaluar_certificacion_compuesta(
        sha_objetivo="b" * 40,
        auditoria_runtime={"sha": "b" * 40, "total_violations": 0,
                            "violations": [], "completo": True,
                            "checks": {c: "ejecutado" for c in
                                       contrato.CONTROLES_OBLIGATORIOS}},
        auditoria_sandbox={"sha": "b" * 40, "total_violations": 1,
                            "violations": [_hallazgo()], "completo": True,
                            "checks": {c: "ejecutado" for c in
                                       contrato.CONTROLES_OBLIGATORIOS}},
        residuos_registrados=[{"id": "INC-0001", "norma": "AP-36",
                                "ruta": "../../vault-backups", "huella": HUELLA,
                                "decision": decision}],
        verificador_actos=verificador)


def test_actos_reales_verificados_dan_pass_y_dejan_el_residuo_listado(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit(repo, "custodia.md", _acta_custodia())
    r = _evaluar(repo, _decision(acto, custodia), registro)
    assert r["estado"] == "PASS", r["motivos"]
    assert len(r["residuos_declarados"]) == 1
    assert r["residuos_declarados"][0]["decision_referencia"] == acto


def test_custodia_autoafirmada_bloquea_en_el_evaluador(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    r = _evaluar(repo, _decision(acto, acto), registro)
    assert r["estado"] == "BLOCKED"
    assert any("CUSTODIA_AUTOAFIRMADA" in m for m in r["motivos"])


def test_sin_fuente_de_autoridad_bloquea_en_el_evaluador(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit(repo, "custodia.md", _acta_custodia())
    r = _evaluar(repo, _decision(acto, custodia), None)
    assert r["estado"] == "BLOCKED"
    assert any("SIN_FUENTE_DE_AUTORIDAD" in m for m in r["motivos"])


def test_el_registro_de_la_propuesta_sigue_sin_vigor():
    """El registro versionado esta en PROPUESTA: no puede acreditar nada."""
    ruta = ROOT / "audits" / "fase2" / "autoridades-de-decision.yaml"
    datos = verificador_mod.cargar_registro(ruta)
    en_vigor, motivos = verificador_mod.registro_en_vigor(datos)
    assert not en_vigor
    assert any("REGISTRO_NO_RATIFICADO" in m for m in motivos)
    assert verificador_mod.verificador_desde_registro(ROOT, datos) is None
    # Y dictaminar no es ratificar: QA no tiene canales.
    assert datos["autoridades"]["qa-arquitectonico"]["canales"] == []
    assert datos["autoridades"]["propietario-datos"]["canales"]
