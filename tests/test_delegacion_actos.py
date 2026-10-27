"""AUTH-12: pruebas de la delegacion limitada al alcance del residuo.

Casos exigidos por el dictamen (QA-R20-AUTH-12): acta valida para el residuo
correcto; valida para OTRO residuo; canal ajeno; delegante no autorizado;
delegado distinto; alcance vacio o contradictorio; delegacion revocada; acta
inexistente.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
HUELLA = "c" * 64
FECHA = "2026-02-02"
CANAL = "refs/heads/canal/autoridad"
CANAL_DELEGADO = "refs/heads/canal/custodio"
CUSTODIO = "custodio-1"


def _cargar(nombre):
    ruta = ROOT / "audits" / "fase2" / f"{nombre}.py"
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


v = _cargar("verificador_actos")


def _git(repo, *args):
    p = subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    assert p.returncode == 0, p.stderr[-300:]
    return (p.stdout or "").strip()


def _repo(tmp):
    repo = tmp / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "canal/autoridad")
    _git(repo, "config", "user.email", "autoridad@example.invalid")
    _git(repo, "config", "user.name", "Autoridad")
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    _git(repo, "add", "b.txt")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "checkout", "-q", "-b", "canal/custodio")
    (repo / "c.txt").write_text("c\n", encoding="utf-8")
    _git(repo, "add", "c.txt")
    _git(repo, "-c", "user.email=custodio@example.invalid",
         "-c", "user.name=Custodio", "commit", "-q", "-m", "canal custodio")
    _git(repo, "checkout", "-q", "canal/autoridad")
    return repo


def _commit(repo, nombre, mensaje, email="autoridad@example.invalid",
            rama="canal/autoridad"):
    if rama != "canal/autoridad":
        _git(repo, "checkout", "-q", "-B", rama)
    (repo / nombre).write_text(nombre + "\n", encoding="utf-8")
    _git(repo, "add", nombre)
    _git(repo, "-c", f"user.email={email}", "-c", f"user.name={email.split('@')[0]}",
         "commit", "-q", "-m", mensaje)
    sha = _git(repo, "rev-parse", "HEAD")
    if rama != "canal/autoridad":
        _git(repo, "checkout", "-q", "canal/autoridad")
    return sha


def _delegacion(residuo="INC-0001", norma="AP-36", huella=HUELLA,
                alcanza="INC-0001", delegante="autoridad-x",
                delegado=CUSTODIO, vigencia="", extra=""):
    lineas = [
        "ACTO: DELEGACION",
        "ACCION: DELEGAR",
        f"DELEGANTE: {delegante}",
        f"DELEGADO: {delegado}",
        f"RESIDUO: {residuo}",
        f"NORMA: {norma}",
        f"HUELLA: {huella}",
        f"ALCANCE: {alcanza}",
    ]
    if vigencia:
        lineas.append(f"VIGENCIA: {vigencia}")
    if extra:
        lineas.append(extra)
    return "\n".join(lineas)


def _acta_ratificacion():
    return "\n".join([
        "ACTO: RATIFICACION", "ACCION: RATIFICAR", "ESTADO: RATIFICADO",
        "DECISION: DEC-77", "AUTORIDAD: autoridad-x", "ALCANCE: INC-0001",
        "RESIDUO: INC-0001", "NORMA: AP-36", "RUTA: ../../vault-backups",
        f"HUELLA: {HUELLA}", f"FECHA: {FECHA}", f"CANAL: {CANAL}",
    ])


def _acta_custodia():
    return "\n".join([
        "ACTO: CUSTODIA", "ACCION: CUSTODIAR", "ESTADO: VIGENTE",
        f"CUSTODIO: {CUSTODIO}", "AUTORIDAD: autoridad-x", "ACTID: ACTA-77",
        "RESIDUO: INC-0001", "NORMA: AP-36", "RUTA: ../../vault-backups",
        f"HUELLA: {HUELLA}", "OPERACIONES: lectura, inventario",
        "VIGENCIA: 2020-01-01/2099-12-31", f"CANAL: {CANAL_DELEGADO}",
        f"FECHA: {FECHA}",
    ])


def _registro(delegacion_acto=None, alcance_cfg="INC-0001"):
    custodio = {"id": CUSTODIO,
                "identidad_git": {"correo": "custodio@example.invalid"},
                "canales": [CANAL_DELEGADO]}
    if delegacion_acto is not None:
        custodio["delega"] = {"de": "autoridad-x", "acto": delegacion_acto,
                              "alcance": alcance_cfg}
    return {
        "id": "autoridades-de-decision-v1", "version": "1",
        "estado": "RATIFICADO",
        "ratificacion": {"acto": _SHA_RAT, "canal": CANAL, "fecha": FECHA,
                          "ratificado_por": "autoridad@example.invalid"},
        "custodios": {CUSTODIO: custodio},
        "autoridades": {
            "autoridad-x": {"canales": [CANAL], "alias": [],
                             "identidad_git": {"correo": "autoridad@example.invalid"}},
        },
    }


_SHA_RAT = "0" * 40


def _con_delegacion(registro, acto, alcance="INC-0001", de="autoridad-x"):
    """Inyecta el bloque de delegacion completo en el custodio."""
    registro["custodios"][CUSTODIO]["delega"] = {
        "de": de, "acto": acto, "alcance": alcance}
    return registro


def _hallazgo(residuo="INC-0001", norma="AP-36", huella=HUELLA):
    return {"id": residuo, "norm": norma, "path": "../../vault-backups",
            "huella": huella}


def _decision(acto, custodia):
    return {"id": "DEC-77", "estado": "RATIFICADO", "autoridad": "autoridad-x",
            "firmante": "autoridad-x", "fecha": FECHA, "referencia": acto,
            "alcance": {"residuo": "INC-0001", "norma": "AP-36",
                        "ruta": "../../vault-backups", "huella": HUELLA},
            "custodia": {"id": "ACTA-77", "referencia": custodia,
                          "verificada": True}}


def _preparar(tmp, delegacion_acto=None, alcance_cfg="INC-0001"):
    """Repo con acto+custodia reales y registro con delegacion."""
    repo = _repo(tmp)
    # acto de ratificacion del registro (para que el verificador este en vigor)
    rat = _commit(repo, "rat.md", "\n".join([
        "ACTO: RATIFICACION", "ACCION: RATIFICAR", "ESTADO: RATIFICADO",
        "OBJETO: autoridades-de-decision-v1", "VERSION: 1",
        f"FECHA: {FECHA}", f"CANAL: {CANAL}",
    ]))
    registro = _registro(delegacion_acto, alcance_cfg)
    registro["ratificacion"]["acto"] = rat
    acto = _commit(repo, "acto.md", _acta_ratificacion())
    custodia = _commit(repo, "custodia.md", _acta_custodia(),
                       email="custodio@example.invalid", rama="canal/custodio")
    return repo, registro, acto, custodia


def _delega(repo, registro, acto, custodia, hallazgo=None):
    verificador = v.VerificadorActosGit(repo, registro)
    return verificador.verificar_custodia(_decision(acto, custodia),
                                          hallazgo or _hallazgo())


def test_delegacion_valida_para_el_residuo_correcto(tmp_path):
    repo, registro, acto, custodia = _preparar(tmp_path)
    deleg = _commit(repo, "deleg.md", _delegacion())
    _con_delegacion(registro, deleg)
    ok, motivos = _delega(repo, registro, acto, custodia)
    assert ok, motivos


def test_delegacion_valida_para_otro_residuo_no_alcanza(tmp_path):
    repo, registro, acto, custodia = _preparar(tmp_path)
    deleg = _commit(repo, "deleg.md", _delegacion(residuo="INC-OTRO",
                                                  alcanza="INC-OTRO"))
    _con_delegacion(registro, deleg, alcance="INC-OTRO")
    ok, motivos = _delega(repo, registro, acto, custodia)
    assert not ok
    assert any("FUERA_DE_ALCANCE" in m for m in motivos), motivos


def test_delegacion_de_canal_ajeno_no_alcanza(tmp_path):
    repo, registro, acto, custodia = _preparar(tmp_path)
    deleg = _commit(repo, "deleg.md", _delegacion(), rama="otra-rama")
    _con_delegacion(registro, deleg)
    ok, motivos = _delega(repo, registro, acto, custodia)
    assert not ok
    assert any("DELEGACION_AJENA" in m for m in motivos), motivos


def test_delegante_no_autorizado(tmp_path):
    repo, registro, acto, custodia = _preparar(tmp_path)
    deleg = _commit(repo, "deleg.md", _delegacion(delegante="inventado"))
    _con_delegacion(registro, deleg)
    registro["custodios"][CUSTODIO]["delega"]["de"] = "inventado"
    ok, motivos = _delega(repo, registro, acto, custodia)
    assert not ok
    assert any("DELEGANTE_NO_AUTORIZADO" in m for m in motivos), motivos


def test_delegado_diferente(tmp_path):
    repo, registro, acto, custodia = _preparar(tmp_path)
    deleg = _commit(repo, "deleg.md", _delegacion(delegado="otro-custodio"))
    _con_delegacion(registro, deleg)
    ok, motivos = _delega(repo, registro, acto, custodia)
    assert not ok
    assert any("DELEGADO_NO_COINCIDE" in m for m in motivos), motivos


def test_alcance_vacio_o_contradictorio(tmp_path):
    repo, registro, acto, custodia = _preparar(tmp_path)
    # sin ALCANCE en el acta
    deleg = _commit(repo, "deleg.md", "\n".join(
        l for l in _delegacion().splitlines() if not l.startswith("ALCANCE:")))
    _con_delegacion(registro, deleg)
    ok, motivos = _delega(repo, registro, acto, custodia)
    assert not ok
    assert any("DELEGACION_SIN_ALCANCE" in m for m in motivos), motivos
    # ALCANCE contradictorio con el registro
    deleg2 = _commit(repo, "deleg2.md", _delegacion(alcanza="INC-0001"))
    _con_delegacion(registro, deleg2, alcance="OTRO-ALCANCE")
    ok2, motivos2 = _delega(repo, registro, acto, custodia)
    assert not ok2
    assert any("ALCANCE_NO_COINCIDE" in m for m in motivos2), motivos2


def test_delegacion_revocada(tmp_path):
    repo, registro, acto, custodia = _preparar(tmp_path)
    deleg = _commit(repo, "deleg.md", _delegacion())
    _con_delegacion(registro, deleg)
    _commit(repo, "revoc.md", "\n".join([
        "ACTO: REVOCACION", "ACCION: REVOCAR", "ESTADO: REVOCADO",
        f"REVOCA: {deleg}", f"CANAL: {CANAL}",
    ]))
    ok, motivos = _delega(repo, registro, acto, custodia)
    assert not ok
    assert any("DELEGACION_REVOCADA" in m for m in motivos), motivos


def test_delegacion_inexistente(tmp_path):
    repo, registro, acto, custodia = _preparar(tmp_path)
    _con_delegacion(registro, "a" * 40)
    ok, motivos = _delega(repo, registro, acto, custodia)
    assert not ok
    assert any("DELEGACION_ACTO_INEXISTENTE" in m for m in motivos), motivos


def test_delegacion_con_vigencia_expirada(tmp_path):
    repo, registro, acto, custodia = _preparar(tmp_path)
    deleg = _commit(repo, "deleg.md",
                    _delegacion(vigencia="2020-01-01/2020-12-31"))
    _con_delegacion(registro, deleg)
    ok, motivos = _delega(repo, registro, acto, custodia)
    assert not ok
    assert any("DELEGACION_EXPIRADA" in m for m in motivos), motivos
