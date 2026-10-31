"""B-04 — el colector QG está cableado en `release.yml`, y como el colector lo pide.

Lo que se mide es la forma del workflow leída con `yaml.safe_load` (el criterio
del consumidor, AP-44: Actions parsea YAML, no busca subcadenas). Que el job
funcione de verdad solo lo dice una corrida de la CI; ese hueco es la deuda
`colector_qg_sin_primera_corrida`, sostenida por `test_colector_qg_sin_puerta.py`.
"""
import yaml

from apoyo import ROOT

WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def _jobs():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]


def _guion(job):
    return "\n".join(p.get("run", "") for p in job["steps"])


def test_publicar_espera_a_los_recibos():
    necesita = _jobs()["publish"].get("needs")
    assert "qg-receipts" in ([necesita] if isinstance(necesita, str) else necesita)


def test_el_colector_corre_en_un_worktree_del_product_sha():
    """Sobre el checkout del tag devolvería QG-00 BLOCKED por CHECKOUT_EN_OTRO_SHA."""
    job = _jobs()["qg-receipts"]
    guion = _guion(job)
    assert "CANDIDATO-RELEASE.yaml" in guion and "product_sha" in guion
    assert "git worktree add --detach" in guion
    colector = next(p for p in job["steps"] if "colector_qg.py" in p.get("run", ""))
    assert colector["working-directory"] == "${{ steps.candidato.outputs.dir }}"
    assert '--sha "${{ steps.candidato.outputs.sha }}"' in colector["run"]


def test_el_colector_recibe_la_evidencia_que_exige_cada_gate():
    """Sin cada una, su gate sale NOT_RUN y la política no libera."""
    colector = next(p["run"] for p in _jobs()["qg-receipts"]["steps"]
                    if "colector_qg.py" in p.get("run", ""))
    for bandera in ("--ejecutar", "--recibos", "--suite-xml", "--e2e-json",
                    "--pip-audit-python", "--paridad-venv", "--paridad-runtime"):
        assert bandera in colector, bandera


def test_la_suite_deja_su_recibo_de_procedencia():
    """QG-03 rechaza un JUnit sin `<xml>.procedencia.json` (SIN_RECIBO_DE_EJECUCION)
    y uno cuyo exit no se registró: el paso no puede cortar antes de escribirlo."""
    guion = _guion(_jobs()["qg-receipts"])
    assert ".procedencia.json" in guion and "junit_sha256" in guion
    assert "set +e" in guion


def test_los_recibos_se_suben_aunque_algo_falle():
    subida = next(p for p in _jobs()["qg-receipts"]["steps"]
                  if str(p.get("uses", "")).startswith("actions/upload-artifact"))
    assert subida.get("if") == "always()"
