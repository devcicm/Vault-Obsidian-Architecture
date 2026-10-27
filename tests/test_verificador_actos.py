"""AUTORIDAD de los actos: esquema != autoridad, y su endurecimiento
(QA-R17-QG02-01, QA-R18-AUTH-01..04, QA-R19-AUTH-05..11).

Verificador REAL contra un repositorio DESCARTABLE (tmp_path) con commits
reales: demuestra la MECANICA (existencia, canal, contrato de acta, custodia
con custodio DESIGNADO, identidad del firmante, vigencia, revocacion). NO
demuestra que el propietario haya ratificado nada en el repositorio real: eso
exigiria una fuente declarada Y ratificada por el propietario (DEC-03).

  AUTH-05  una autoridad registrada NO es custodio; `custodios: []` no acredita
  AUTH-06  la identidad y la procedencia son de QUIEN FIRMA (el custodio); la
           delegacion exige acto verificable y alcance
  AUTH-07  el acta de ratificacion del registro cumple el contrato COMPLETO
           (ACTO, ACCION, ESTADO, OBJETO, VERSION, FECHA, CANAL, identidad)
  AUTH-08  alias legitimo normalizado; alias libre/ambiguo/de otra autoridad
           rechazado
  AUTH-09  vigencia completa: inicio <= hoy <= fin, fechas ISO, inicio <= fin
  AUTH-10  campos obligatorios duplicados o contradictorios se rechazan
  AUTH-11  ratificacion -> revocacion -> BLOCKED
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HUELLA = "c" * 64
FECHA = "2026-02-02"
CANAL = "refs/heads/canal/autoridad"
CUSTODIO = "custodio-1"


def _cargar(nombre):
    ruta = ROOT / "audits" / "fase2" / f"{nombre}.py"
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


verificador_mod = _cargar("verificador_actos")
contrato = _cargar("politica_certificacion_compuesta")


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


def _commit(repo: Path, nombre: str, mensaje: str, rama: str = "canal/autoridad",
            email: str = "autoridad@example.invalid") -> str:
    (repo / nombre).write_text(nombre + "\n", encoding="utf-8")
    _git(repo, "add", nombre)
    if rama != "canal/autoridad":
        _git(repo, "checkout", "-q", "-b", rama)
    _git(repo, "-c", f"user.email={email}", "-c", f"user.name={email.split('@')[0]}",
         "commit", "-q", "-m", mensaje)
    sha = _git(repo, "rev-parse", "HEAD")
    if rama != "canal/autoridad":
        _git(repo, "checkout", "-q", "canal/autoridad")
    return sha


def _acta_ratificacion(residuo="INC-0001", norma="AP-36",
                        ruta="../../vault-backups", decision="DEC-77",
                        autoridad="autoridad-x", accion="RATIFICAR",
                        estado="RATIFICADO", huella=HUELLA, fecha=FECHA,
                        canal=CANAL) -> str:
    return "\n".join([
        "ACTO: RATIFICACION",
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
    ])


def _acta_custodia(residuo="INC-0001", norma="AP-36",
                    ruta="../../vault-backups", custodio=CUSTODIO,
                    autoridad="autoridad-x", operaciones="lectura, inventario",
                    vigencia="2020-01-01/2099-12-31", canal=CANAL) -> str:
    return "\n".join([
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
    ])


def _commit_custodia(repo: Path, nombre: str, mensaje: str) -> str:
    """El acta de custodia la FIRMA el custodio designado (AUTH-06)."""
    return _commit(repo, nombre, mensaje, email="custodio@example.invalid")


def _registro(estado="RATIFICADO", ratification=None, custodios=None,
              alias=None, correo=None, canales=None) -> dict:
    return {
        "id": "autoridades-de-decision-v1",
        "version": "1",
        "estado": estado,
        "ratificacion": ratification if ratification is not None else {
            "acto": "", "canal": "", "fecha": "", "ratificado_por": ""},
        "custodios": custodios if custodios is not None else {
            CUSTODIO: {"id": CUSTODIO,
                        "identidad_git": {"correo": "custodio@example.invalid"},
                        "canales": [CANAL]}},
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
    sha = _commit(repo, "ratificacion.md", "\n".join([
        "ACTO: RATIFICACION",
        "ACCION: RATIFICAR",
        "ESTADO: RATIFICADO",
        "OBJETO: autoridades-de-decision-v1",
        "VERSION: 1",
        f"FECHA: {FECHA}",
        f"CANAL: {CANAL}",
    ]))
    registro = _registro(ratification={
        "acto": sha, "canal": CANAL, "fecha": FECHA,
        "ratificado_por": "autoridad@example.invalid"}, **cambios)
    return registro


# ── AUTH-01/07: ratificacion del registro ───────────────────────────────────

def test_un_registro_propuesto_no_es_fuente_confiable():
    for estado in ("PROPUESTA", "DRAFT", "PENDING", "", "RATIFICADO_ISH"):
        registro = _registro(estado=estado)
        en_vigor, motivos = verificador_mod.registro_en_vigor(registro)
        assert not en_vigor, f"estado={estado!r} no puede estar en vigor"
        assert verificador_mod.verificador_desde_registro(ROOT, registro) is None


def test_el_acta_de_ratificacion_necesita_el_contrato_completo(tmp_path):
    repo = _repo(tmp_path)
    completo = "\n".join([
        "ACTO: RATIFICACION", "ACCION: RATIFICAR", "ESTADO: RATIFICADO",
        "OBJETO: autoridades-de-decision-v1", "VERSION: 1",
        f"FECHA: {FECHA}", f"CANAL: {CANAL}",
    ])
    for falta in ("ACTO:", "ACCION:", "ESTADO:", "OBJETO:", "VERSION:",
                  "FECHA:", "CANAL:"):
        sha = _commit(repo, f"r-{falta.strip(':')}.md",
                      "\n".join(l for l in completo.splitlines()
                                if not l.startswith(falta)))
        registro = _registro(ratification={
            "acto": sha, "canal": CANAL, "fecha": FECHA,
            "ratificado_por": "autoridad@example.invalid"})
        verificador = _verificador(repo, registro)
        assert not verificador.en_vigor(), f"falta {falta} y aun asi esta en vigor"


def test_un_acta_de_ratificacion_con_fecha_contradicoria_no_entra_en_vigor(tmp_path):
    repo = _repo(tmp_path)
    sha = _commit(repo, "r.md", "\n".join([
        "ACTO: RATIFICACION", "ACCION: RATIFICAR", "ESTADO: RATIFICADO",
        "OBJETO: autoridades-de-decision-v1", "VERSION: 1",
        "FECHA: 2030-01-01", f"CANAL: {CANAL}",
    ]))
    registro = _registro(ratification={
        "acto": sha, "canal": CANAL, "fecha": FECHA,
        "ratificado_por": "autoridad@example.invalid"})
    verificador = _verificador(repo, registro)
    assert not verificador.en_vigor()
    assert any("FECHA_CONTRADICTORIA" in m for m in verificador.motivos_vigor())


def test_un_registro_ratificado_por_su_propia_acta_si_esta_en_vigor(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    assert verificador is not None and verificador.en_vigor()


# ── AUTH-02/08: identidades y alias ─────────────────────────────────────────

def test_un_alias_legitimo_se_normaliza(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo, alias=["alias-de-la-autoridad"])
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit_custodia(repo, "custodia.md", _acta_custodia())
    decision = _decision(acto, custodia, firmante="alias-de-la-autoridad")
    ok, motivos = verificador.verificar_acto(decision, _hallazgo())
    assert ok, motivos


def test_un_alias_desconocido_o_de_otra_autoridad_se_rechaza(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo, alias=["alias-de-la-autoridad"])
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit_custodia(repo, "custodia.md", _acta_custodia())
    for alias in ("alias-libre", "otra-autoridad"):
        decision = _decision(acto, custodia, firmante=alias)
        ok, motivos = verificador.verificar_acto(decision, _hallazgo())
        assert not ok, f"alias={alias} no puede acreditar"
        assert any("AUTORIDAD_DESCONOCIDA" in m for m in motivos)


def test_un_alias_ambiguo_se_rechaza(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo, alias=["compartido"])
    registro["autoridades"]["otra-autoridad"] = {
        "canales": [CANAL], "alias": ["compartido"], "identidad_git": {}}
    verificador = verificador_mod.VerificadorActosGit(repo, registro)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit_custodia(repo, "custodia.md", _acta_custodia())
    decision = _decision(acto, custodia, firmante="compartido")
    ok, motivos = verificador.verificar_acto(decision, _hallazgo())
    assert not ok
    assert any("ALIAS_AMBIGUO" in m for m in motivos)


def test_en_el_evaluador_un_alias_legitimo_no_se_rechaza(tmp_path):
    """AUTH-08 pide el positivo y el negativo EN EL EVALUADOR COMPUESTO."""
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo, alias=["alias-de-la-autoridad"])
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit_custodia(repo, "custodia.md", _acta_custodia())
    r = _evaluar(repo, _decision(acto, custodia, firmante="alias-de-la-autoridad"),
                 registro)
    assert r["estado"] == "PASS", r["motivos"]
    r2 = _evaluar(repo, _decision(acto, custodia, firmante="alias-libre"), registro)
    assert r2["estado"] == "BLOCKED"
    assert any("AUTORIDAD_DESCONOCIDA" in m for m in r2["motivos"])


# ── AUTH-05/06: custodio designado e identidad del firmante ─────────────────

def test_con_custodios_vacios_ninguna_custodia_puede_acentarse(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo, custodios={})
    verificador = verificador_mod.VerificadorActosGit(repo, registro)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit_custodia(repo, "custodia.md", _acta_custodia())
    ok, motivos = verificador.verificar_custodia(
        _decision(acto, custodia), _hallazgo())
    assert not ok
    assert any("CUSTODIO_NO_DESIGNADO" in m for m in motivos)


def test_una_autoridad_registrada_no_es_custodio(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo, custodios={})
    registro["autoridades"]["autoridad-x"]["canales"] = [CANAL]
    verificador = verificador_mod.VerificadorActosGit(repo, registro)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit_custodia(repo, "custodia.md",
                       _acta_custodia(custodio="autoridad-x"))
    ok, motivos = verificador.verificar_custodia(
        _decision(acto, custodia), _hallazgo())
    assert not ok
    assert any("CUSTODIO_NO_DESIGNADO" in m for m in motivos)


def test_un_custodio_que_no_firma_no_puede_ser_suplantado(tmp_path):
    """AUTH-06: el acta la firma alguien que NO es el custodio designado."""
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit(repo, "custodia.md", _acta_custodia(),
                       email="otro@example.invalid")
    ok, motivos = verificador.verificar_custodia(
        _decision(acto, custodia), _hallazgo())
    assert not ok
    assert any("IDENTIDAD_INCOMPATIBLE" in m for m in motivos)


def test_una_delegacion_exige_acto_verificable_con_alcance(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    datos = dict(registro["custodios"][CUSTODIO])
    datos["delega"] = {"de": "autoridad-x", "acto": "a" * 40,
                       "alcance": ["INC-0001"]}
    registro["custodios"][CUSTODIO] = datos
    verificador = verificador_mod.VerificadorActosGit(repo, registro)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit_custodia(repo, "custodia.md", _acta_custodia())
    ok, motivos = verificador.verificar_custodia(
        _decision(acto, custodia), _hallazgo())
    assert not ok
    assert any("DELEGACION_ACTO_INEXISTENTE" in m for m in motivos)


# ── AUTH-09: vigencia ───────────────────────────────────────────────────────

def test_una_vigencia_futura_invertida_o_invalida_se_rechaza(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    casos = [
        ("2099-01-01/2099-12-31", "VIGENCIA_FUTURA"),
        ("2099-12-31/2099-01-01", "VIGENCIA_INVERTIDA"),
        ("2020-13-45/2099-12-31", "VIGENCIA_INVALIDA"),
        ("2020/01/01", "VIGENCIA_INVALIDA"),
    ]
    for indice, caso in enumerate(casos):
        vigencia, esperado = caso
        custodia = _commit_custodia(repo, f"c-{indice}.md",
                                    _acta_custodia(vigencia=vigencia))
        ok, motivos = verificador.verificar_custodia(
            _decision(acto, custodia), _hallazgo())
        assert not ok, f"vigencia={vigencia} no puede pasar"
        assert any(esperado in m for m in motivos), motivos


def test_un_acta_con_campos_duplicados_se_rechaza(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    custodia = _commit_custodia(repo, "custodia.md", _acta_custodia())
    for extra in ("ACCION: REVOCAR", "ESTADO: REVOCADO", "ACTO: OTRO"):
        sha = _commit(repo, f"acto-{extra.split(':')[0]}.md",
                      _acta_ratificacion() + "\n" + extra)
        ok, motivos = verificador.verificar_acto(
            _decision(sha, custodia), _hallazgo())
        assert not ok, f"campo duplicado {extra!r} no puede pasar"
        assert any("DUPLICADO" in m for m in motivos)


# ── AUTH-11: revocacion ─────────────────────────────────────────────────────

def test_ratificacion_luego_revocacion_deja_el_residuo_bloqueado(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit_custodia(repo, "custodia.md", _acta_custodia())
    # Antes de revocar: el acto acredita.
    ok, _ = verificador.verificar_acto(_decision(acto, custodia), _hallazgo())
    assert ok
    # Acto de revocacion posterior, en el canal de la autoridad.
    _commit(repo, "revocacion.md", "\n".join([
        "ACTO: REVOCACION",
        "ACCION: REVOCAR",
        "ESTADO: REVOCADO",
        "DECISION: DEC-77",
        "ALCANCE: INC-0001",
        f"REVOCA: {acto}",
        f"CANAL: {CANAL}",
    ]))
    ok2, motivos2 = verificador.verificar_acto(
        _decision(acto, custodia), _hallazgo())
    assert not ok2, "un acto revocado no puede acreditar"
    assert any("ACTO_REVOCADO" in m for m in motivos2)
    # Y la nueva evaluacion del residuo queda bloqueada.
    r = _evaluar(repo, _decision(acto, custodia), registro)
    assert r["estado"] == "BLOCKED"
    assert any("ACTO_REVOCADO" in m for m in r["motivos"])


# ── extremo a extremo ───────────────────────────────────────────────────────

def _evaluar(repo: Path, decision: dict, registro=None):
    verificador = (verificador_mod.verificador_desde_registro(repo, registro)
                   if registro is not None else None)
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
    custodia = _commit_custodia(repo, "custodia.md", _acta_custodia())
    r = _evaluar(repo, _decision(acto, custodia), registro)
    assert r["estado"] == "PASS", r["motivos"]
    assert len(r["residuos_declarados"]) == 1


def test_el_registro_de_la_propuesta_sigue_sin_vigor():
    ruta = ROOT / "audits" / "fase2" / "autoridades-de-decision.yaml"
    datos = verificador_mod.cargar_registro(ruta)
    en_vigor, motivos = verificador_mod.registro_en_vigor(datos)
    assert not en_vigor
    assert verificador_mod.verificador_desde_registro(ROOT, datos) is None
    # AUTH-05: sin custodios designados, NADIE puede custodiar.
    assert datos["custodios"] in ({}, []) or not datos["custodios"]
    assert datos["autoridades"]["qa-arquitectonico"]["canales"] == []


# ── Cobertura recuperada (R19) adaptada al contrato de R20 ─────────────────

def test_un_acto_real_con_contenido_coincidente_se_verifica(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    custodia = _commit_custodia(repo, "custodia.md", _acta_custodia())
    sha = _commit(repo, "acto.md", _acta_ratificacion())
    ok, motivos = verificador.verificar_acto(
        _decision(sha, custodia), _hallazgo())
    assert ok, motivos


def test_un_sha_hexadecimal_inexistente_no_es_un_acto(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    custodia = _commit_custodia(repo, "custodia.md", _acta_custodia())
    ok, motivos = verificador.verificar_acto(
        _decision("a" * 40, custodia), _hallazgo())
    assert not ok
    assert any("ACTO_INEXISTENTE" in m for m in motivos)


def test_un_commit_existente_ajeno_al_canal_no_ratifica(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    custodia = _commit_custodia(repo, "custodia.md", _acta_custodia())
    ajeno = _commit(repo, "ajeno.md", _acta_ratificacion(), rama="otra-rama")
    ok, motivos = verificador.verificar_acto(
        _decision(ajeno, custodia), _hallazgo())
    assert not ok
    assert any("ACTO_AJENO" in m for m in motivos)


def test_un_firmante_no_registrado_con_autoridad_registrada_no_ratifica(tmp_path):
    """AUTH-02: firmante libre + autoridad registrada -> rechazo."""
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    custodia = _commit_custodia(repo, "custodia.md", _acta_custodia())
    sha = _commit(repo, "acto.md", _acta_ratificacion())
    decision = _decision(sha, custodia, firmante="firmante-libre")
    ok, motivos = verificador.verificar_acto(decision, _hallazgo())
    assert not ok
    assert any("AUTORIDAD_DESCONOCIDA" in m for m in motivos)


def test_un_acto_sin_contenido_coincidente_no_ratifica(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    custodia = _commit_custodia(repo, "custodia.md", _acta_custodia())
    sha = _commit(repo, "acto.md", "una nota sin relacion con el residuo")
    ok, motivos = verificador.verificar_acto(
        _decision(sha, custodia), _hallazgo())
    assert not ok
    assert any("ACTO_SIN_" in m or "ACTO_TIPO_INVALIDO" in m for m in motivos)


def test_los_estados_no_ratificados_se_distinguen(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    custodia = _commit_custodia(repo, "custodia.md", _acta_custodia())
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
    custodia = _commit_custodia(repo, "custodia.md", _acta_custodia())
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
    custodia = _commit_custodia(repo, "custodia.md", _acta_custodia())
    sha = _commit(repo, "acto.md", _acta_ratificacion(residuo="INC-OTRO"))
    ok, motivos = verificador.verificar_acto(
        _decision(sha, custodia), _hallazgo())
    assert not ok
    assert any("ALCANCE_NO_COINCIDE" in m for m in motivos)


def test_un_acto_que_no_declara_el_canal_se_rechaza(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    custodia = _commit_custodia(repo, "custodia.md", _acta_custodia())
    sha = _commit(repo, "acto.md", _acta_ratificacion(canal="refs/heads/otro"))
    ok, motivos = verificador.verificar_acto(
        _decision(sha, custodia), _hallazgo())
    assert not ok
    assert any("CANAL_NO_DECLARADO" in m for m in motivos)


def test_un_registro_que_se_autoafirma_sin_acto_no_entra_en_vigor(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro(ratification={"acto": "a" * 40, "canal": CANAL,
                                        "fecha": FECHA,
                                        "ratificado_por": "autoridad@example.invalid"})
    verificador = _verificador(repo, registro)
    assert not verificador.en_vigor()
    assert any("INEXISTENTE" in m for m in verificador.motivos_vigor())


def test_un_acto_de_ratificacion_consultivo_no_pone_en_vigor_el_registro(tmp_path):
    repo = _repo(tmp_path)
    sha = _commit(repo, "consulta.md", "\n".join([
        "ACTO: RATIFICACION", "ACCION: CONSULTAR", "ESTADO: CONSULTADO",
        "OBJETO: autoridades-de-decision-v1", "VERSION: 1",
        f"FECHA: {FECHA}", f"CANAL: {CANAL}",
    ]))
    registro = _registro(ratification={"acto": sha, "canal": CANAL,
                                        "fecha": FECHA,
                                        "ratificado_por": "autoridad@example.invalid"})
    verificador = _verificador(repo, registro)
    assert not verificador.en_vigor()
    assert any("NO_RATIFICA" in m or "NO_RATIFICADO" in m
               for m in verificador.motivos_vigor())


def test_un_registro_ratificado_por_otro_autor_no_entra_en_vigor(tmp_path):
    repo = _repo(tmp_path)
    sha = _commit(repo, "ratificacion.md", "\n".join([
        "ACTO: RATIFICACION", "ACCION: RATIFICAR", "ESTADO: RATIFICADO",
        "OBJETO: autoridades-de-decision-v1", "VERSION: 1",
        f"FECHA: {FECHA}", f"CANAL: {CANAL}",
    ]))
    registro = _registro(ratification={"acto": sha, "canal": CANAL,
                                        "fecha": FECHA,
                                        "ratificado_por": "otra-persona@example.invalid"})
    verificador = _verificador(repo, registro)
    assert not verificador.en_vigor()
    assert any("RATIFICADO_POR_OTRO" in m for m in verificador.motivos_vigor())


def test_una_custodia_autoafirmada_no_es_verificacion(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    sha = _commit(repo, "acto.md", _acta_ratificacion())
    decision = _decision(sha, sha)
    ok, motivos = verificador.verificar_custodia(decision, _hallazgo())
    assert not ok
    assert any("CUSTODIA_AUTOAFIRMADA" in m for m in motivos)


def test_una_custodia_inexistente_no_pasa(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    verificador = verificador_mod.verificador_desde_registro(repo, registro)
    sha = _commit(repo, "acto.md", _acta_ratificacion())
    ok, motivos = verificador.verificar_custodia(
        _decision(sha, "b" * 40), _hallazgo())
    assert not ok
    assert any("CUSTODIA_INEXISTENTE" in m for m in motivos)


def test_sin_fuente_de_autoridad_bloquea_en_el_evaluador(tmp_path):
    repo = _repo(tmp_path)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit_custodia(repo, "custodia.md", _acta_custodia())
    r = _evaluar(repo, _decision(acto, custodia), None)
    assert r["estado"] == "BLOCKED"
    assert any("SIN_FUENTE_DE_AUTORIDAD" in m for m in r["motivos"])


def test_custodia_autoafirmada_bloquea_en_el_evaluador(tmp_path):
    repo = _repo(tmp_path)
    registro = _registro_ratificado(repo)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    r = _evaluar(repo, _decision(acto, acto), registro)
    assert r["estado"] == "BLOCKED"
    assert any("CUSTODIA_AUTOAFIRMADA" in m for m in r["motivos"])


def test_un_registro_propuesto_bloquea_aunque_los_actos_sean_reales(tmp_path):
    repo = _repo(tmp_path)
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit_custodia(repo, "custodia.md", _acta_custodia())
    registro = _registro(estado="PROPUESTA")
    assert verificador_mod.verificador_desde_registro(repo, registro) is None
    r = _evaluar(repo, _decision(acto, custodia), registro)
    assert r["estado"] == "BLOCKED"
    assert any("SIN_FUENTE_DE_AUTORIDAD" in m or "REGISTRO_NO_EN_VIGOR" in m
               for m in r["motivos"])
