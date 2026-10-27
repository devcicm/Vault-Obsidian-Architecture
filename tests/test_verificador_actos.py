"""AUTORIDAD de los actos: el esquema no basta (QA-R17-QG02-01).

Un SHA hexadecimal no demuestra que exista el acto; un `firmante` cualquiera
no demuestra autoridad; un `custodia.verificada: true` aportado por el mismo
recibo no es una verificacion independiente.

Estas pruebas usan el verificador REAL contra un repositorio DESCARTABLE
(tmp_path) con commits reales: demonstrates la MECANICA (existencia, canal,
contenido coincidente, custodia independiente, revocacion, identidad). NO
demuestran que el propietario haya ratificado nada en el repositorio real:
eso exigiria una fuente declarada y ratificada por el propietario (DEC-03).
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HUELLA = "c" * 64


def _cargar(nombre):
    ruta = ROOT / "audits" / "fase2" / f"{nombre}.py"
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


verificador_mod = _cargar("verificador_actos")
contrato = _cargar("politica_certificacion_compuesta")

REGISTRO = {
    "autoridades": {
        "autoridad-x": {
            "canales": ["refs/heads/canal/autoridad"],
            "identidad_git": {},
        }
    }
}


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


def _decision(referencia: str, custodia: str, **cambios) -> dict:
    base = {
        "id": "DEC-77",
        "estado": "RATIFICADO",
        "firmante": "autoridad-x",
        "fecha": "2026-02-02",
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


def _verificador(repo: Path):
    return verificador_mod.VerificadorActosGit(repo, REGISTRO)


# ── el verificador ───────────────────────────────────────────────────────────

def test_un_acto_real_con_contenido_coincidente_se_verifica(tmp_path):
    repo = _repo(tmp_path)
    sha = _commit(repo, "acto.md",
                  "DEC-77: ratifico INC-0001 AP-36 ../../vault-backups "
                  f"huella {HUELLA}")
    ok, motivos = _verificador(repo).verificar_acto(
        _decision(sha, "e" * 40), _hallazgo())
    assert ok, motivos


def test_un_sha_hexadecimal_inexistente_no_es_un_acto(tmp_path):
    repo = _repo(tmp_path)
    ok, motivos = _verificador(repo).verificar_acto(
        _decision("a" * 40, "e" * 40), _hallazgo())
    assert not ok
    assert any("ACTO_INEXISTENTE" in m for m in motivos)


def test_un_commit_existente_ajeno_al_canal_no_ratifica(tmp_path):
    repo = _repo(tmp_path)
    ajeno = _commit(repo, "ajeno.md", "otro trabajo", rama="otra-rama")
    ok, motivos = _verificador(repo).verificar_acto(
        _decision(ajeno, "e" * 40), _hallazgo())
    assert not ok
    assert any("ACTO_AJENO" in m for m in motivos)


def test_un_firmante_no_autorizado_no_ratifica(tmp_path):
    repo = _repo(tmp_path)
    sha = _commit(repo, "acto.md",
                  "DEC-77: ratifico INC-0001 AP-36 ../../vault-backups "
                  f"huella {HUELLA}")
    decision = _decision(sha, "e" * 40, firmante="alguien-sin-registro")
    ok, motivos = _verificador(repo).verificar_acto(decision, _hallazgo())
    assert not ok
    assert any("AUTORIDAD_NO_REGISTRADA" in m for m in motivos)


def test_un_acto_sin_contenido_coincidente_no_ratifica(tmp_path):
    repo = _repo(tmp_path)
    sha = _commit(repo, "acto.md", "una nota sin relacion con el residuo")
    ok, motivos = _verificador(repo).verificar_acto(
        _decision(sha, "e" * 40), _hallazgo())
    assert not ok
    assert any("ACTO_SIN_ALCANCE" in m for m in motivos)


def test_un_acto_revocado_no_ratifica(tmp_path):
    repo = _repo(tmp_path)
    sha = _commit(repo, "acto.md",
                  "DEC-77 REVOCADO: INC-0001 AP-36 ../../vault-backups "
                  f"huella {HUELLA}")
    ok, motivos = _verificador(repo).verificar_acto(
        _decision(sha, "e" * 40), _hallazgo())
    assert not ok
    assert any("ACTO_REVOCADO" in m for m in motivos)


def test_una_custodia_autoafirmada_no_es_verificacion(tmp_path):
    """`verificada: true` con el MISMO SHA del acto no es independiente."""
    repo = _repo(tmp_path)
    sha = _commit(repo, "acto.md",
                  "DEC-77: ratifico INC-0001 AP-36 ../../vault-backups "
                  f"huella {HUELLA}")
    decision = _decision(sha, sha)
    ok, motivos = _verificador(repo).verificar_custodia(decision, _hallazgo())
    assert not ok
    assert any("CUSTODIA_AUTOAFIRMADA" in m for m in motivos)


def test_una_custodia_inexistente_o_sin_contenido_no_pasa(tmp_path):
    repo = _repo(tmp_path)
    sha = _commit(repo, "acto.md",
                  "DEC-77: ratifico INC-0001 AP-36 ../../vault-backups "
                  f"huella {HUELLA}")
    ok, motivos = _verificador(repo).verificar_custodia(
        _decision(sha, "b" * 40), _hallazgo())
    assert not ok
    assert any("CUSTODIA_INEXISTENTE" in m for m in motivos)

    otra = _commit(repo, "custodia.md", "ACTA-77: custodia sin la huella")
    ok2, motivos2 = _verificador(repo).verificar_custodia(
        _decision(sha, otra), _hallazgo())
    assert not ok2
    assert any("CUSTODIA_SIN_ALCANCE" in m for m in motivos2)


# ── extremo a extremo, por el evaluador ─────────────────────────────────────

def _evaluar(repo: Path, decision: dict, verificador=None):
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
    acto = _commit(repo, "acto.md",
                   "DEC-77: ratifico INC-0001 AP-36 ../../vault-backups "
                   f"huella {HUELLA}")
    custodia = _commit(repo, "custodia.md",
                       "ACTA-77: custodia de INC-0001 ../../vault-backups "
                       f"huella {HUELLA}")
    r = _evaluar(repo, _decision(acto, custodia), _verificador(repo))
    assert r["estado"] == "PASS", r["motivos"]
    assert len(r["residuos_declarados"]) == 1
    assert r["residuos_declarados"][0]["decision_referencia"] == acto


def test_custodia_autoafirmada_bloquea_en_el_evaluador(tmp_path):
    repo = _repo(tmp_path)
    acto = _commit(repo, "acto.md",
                   "DEC-77: ratifico INC-0001 AP-36 ../../vault-backups "
                   f"huella {HUELLA}")
    r = _evaluar(repo, _decision(acto, acto), _verificador(repo))
    assert r["estado"] == "BLOCKED"
    assert any("CUSTODIA_AUTOAFIRMADA" in m for m in r["motivos"])


def test_un_sha_sintetico_bloquea_en_el_evaluador(tmp_path):
    repo = _repo(tmp_path)
    custodia = _commit(repo, "custodia.md",
                       "ACTA-77: custodia de INC-0001 ../../vault-backups "
                       f"huella {HUELLA}")
    r = _evaluar(repo, _decision("a" * 40, custodia), _verificador(repo))
    assert r["estado"] == "BLOCKED"
    assert any("ACTO_INEXISTENTE" in m for m in r["motivos"])


def test_sin_fuente_de_autoridad_bloquea_en_el_evaluador(tmp_path):
    repo = _repo(tmp_path)
    acto = _commit(repo, "acto.md",
                   "DEC-77: ratifico INC-0001 AP-36 ../../vault-backups "
                   f"huella {HUELLA}")
    custodia = _commit(repo, "custodia.md",
                       "ACTA-77: custodia de INC-0001 ../../vault-backups "
                       f"huella {HUELLA}")
    r = _evaluar(repo, _decision(acto, custodia), None)
    assert r["estado"] == "BLOCKED"
    assert any("SIN_FUENTE_DE_AUTORIDAD" in m for m in r["motivos"])


def test_el_registro_sin_autoridades_no_es_fuente_confiable():
    assert verificador_mod.verificador_desde_registro(ROOT, {}) is None
    assert verificador_mod.verificador_desde_registro(ROOT, {"autoridades": {}}) is None
    v = verificador_mod.verificador_desde_registro(
        ROOT, {"autoridades": {"a": {"canales": ["refs/heads/x"]}}})
    assert v is not None


def test_el_registro_de_la_propuesta_es_una_propuesta_sin_autoridades_efectivas():
    """El registro versionado declara una autoridad SIN canales efectivos:
    no hay fuente confiable todavia (DEC-03 pendiente)."""
    ruta = ROOT / "audits" / "fase2" / "autoridades-de-decision.yaml"
    datos = verificador_mod.cargar_registro(ruta)
    assert "PROPUESTA" in str(datos.get("estado"))
    autoridades = datos["autoridades"]
    # La autoridad de QA no ratifica: dictaminar no es decidir.
    assert autoridades["qa-arquitectonico"]["canales"] == []
    assert autoridades["propietario-datos"]["canales"]
    # Y el verificador se construye con el registro normalizado.
    v = verificador_mod.verificador_desde_registro(ROOT, datos)
    assert v is not None
