"""El estado de release es trazable y la wheel es reproducible.

Dos hallazgos de la re-auditoría del vault (paper
`paper-contraste-auditoria-y-rutas-portables-f1ce0774`, sección 4.4):

1. La puerta del tag admite los centinelas de QA (`PENDIENTE`,
   `OMITIDO_POR_PROPIETARIO`, DEC-06). La excepción ya estaba declarada en el
   workflow y trazada en el manifiesto con `qa_verdict_ref_note`; lo que
   faltaba es que el receipt del release diga QUÉ centinela aceptó, y que un
   test congele el contrato para que nadie lo afloje en silencio.
2. La reproducibilidad de la wheel se midió a mano el 2026-11-09 (dos builds
   con `SOURCE_DATE_EPOCH` fijado → mismo SHA-256) pero no estaba
   instrumentada: nadie habría notado que dejó de serlo.
"""

import hashlib
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "release.yml"
MANIFIESTO = REPO / "audits" / "fase2" / "CANDIDATO-RELEASE.yaml"

SENTINELAS = ("PENDIENTE", "OMITIDO_POR_PROPIETARIO")


def _script_de_la_puerta() -> str:
    """El código inline del paso «El tag es el candidato autorizado»."""
    import yaml

    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    pasos = wf["jobs"]["publish"]["steps"]
    for paso in pasos:
        if paso.get("name") == "El tag es el candidato autorizado":
            return paso["run"]
    raise AssertionError("el paso de la puerta del tag ya no está en release.yml")


def test_los_centinelas_de_qa_siguen_siendo_el_unico_atajo():
    """El contrato DEC-06 congelado: se admite el centinela, no una string suelta."""
    script = _script_de_la_puerta()
    for centinela in SENTINELAS:
        assert f'"{centinela}"' in script, (
            f"el centinela {centinela} ya no se admite: alguien endureció la "
            f"puerta. Actualizar este test y DEC-06, no al revés.")
    # Sin centinela ni fichero real, la puerta falla: `ref_real` exige el
    # prefijo audits/ y rechaza traversals.
    assert 'startswith("audits/")' in script
    assert '".." in valor.split("/")' in script
    assert "DEC-06" in script, "la excepción perdió su referencia normativa"


def test_el_receipt_del_release_nombra_el_estado_de_qa():
    """Un centinela aceptado en silencio no es trazable: sale en el OK."""
    script = _script_de_la_puerta()
    linea_ok = [l for l in script.splitlines() if "OK: {tag}" in l]
    assert linea_ok, "la línea de OK del release desapareció"
    assert "qa" in linea_ok[0], (
        f"el receipt no dice el estado de QA: {linea_ok[0].strip()}")


def test_todo_centinela_del_manifiesto_lleva_su_nota_de_trazabilidad():
    """`qa_verdict_ref` en centinela exige `qa_verdict_ref_note` no vacía.

    La traza vive en el manifiesto; que exista la clave y no se escriba es
    la forma silenciosa del mismo defecto.
    """
    import yaml

    m = yaml.safe_load(MANIFIESTO.read_text(encoding="utf-8"))
    candidatos = [
        v for k, v in m.items()
        if isinstance(v, dict) and "qa_verdict_ref" in v
    ]
    assert candidatos, "el manifiesto ya no declara candidatos: test sin objeto"
    sin_nota = []
    for c in candidatos:
        qa = c.get("qa_verdict_ref")
        if qa in SENTINELAS and not (c.get("qa_verdict_ref_note") or "").strip():
            sin_nota.append(c.get("version", "?"))
    assert not sin_nota, f"centinelas sin nota: {sin_nota}"


def test_la_wheel_es_reproducible(tmp_path):
    """Dos builds con el mismo SOURCE_DATE_EPOCH producen el mismo byte.

    Medido a mano el 2026-11-09: sha256 idéntico. Si este test falla, algo
    metió reloj o entorno en el artefacto distribuido — el release publicado
    deja de ser certificable contra su hash.

    En proceso por la API PEP 517 (`build.ProjectBuilder`): el backend es
    importable en el intérprete de la suite, y un subprocess con
    `sys.executable` sería el lanzador privado que AP-69 ya veta.
    """
    pytest.importorskip("build")
    from build import ProjectBuilder

    os.environ["SOURCE_DATE_EPOCH"] = "1700000000"
    hashes = []
    for turno in (1, 2):
        salida = tmp_path / f"build-{turno}"
        ProjectBuilder(REPO).build("wheel", output_directory=str(salida))
        whl = sorted(salida.glob("vault_obsidian_architecture-*.whl"))
        assert len(whl) == 1, whl
        hashes.append(hashlib.sha256(whl[0].read_bytes()).hexdigest())
    assert hashes[0] == hashes[1], hashes
