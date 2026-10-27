"""El manifiesto del candidato es mecanicamente validable (QA-R14-DOC-02).

Los campos de identidad llevan SOLO valores (hex puro); las notas viven en
claves separadas. Este test valida el formato y la existencia real de los
SHAs, y ejercita los negativos: hash mal formado y SHA ajeno (que no existe
en git) deben ser RECHAZADOS por el validador.
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MANIFIESTO = REPO / "audits" / "fase2" / "CANDIDATO-RELEASE.yaml"

SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _cargar():
    import yaml

    return yaml.safe_load(MANIFIESTO.read_text(encoding="utf-8"))


def _validar_hex(valor, patron, nombre):
    """Validador puro: el valor debe ser hex puro del formato pedido."""
    if not isinstance(valor, str):
        raise ValueError(f"{nombre}: debe ser una cadena hex pura, no {valor!r}")
    if not patron.match(valor):
        raise ValueError(f"{nombre}: {valor!r} no es un hex valido del formato exigido")
    return valor


def _commit_existe(sha):
    p = subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"],
                       cwd=str(REPO), capture_output=True)
    return p.returncode == 0


def test_los_campos_de_identidad_son_hex_puro():
    m = _cargar()
    rc = m["release_candidate"]
    # NINGUN campo de identidad lleva prosa anexada (QA-R14-DOC-02)
    _validar_hex(rc["product_sha"], SHA1_RE, "product_sha")
    _validar_hex(rc["product_tree_sha"], SHA1_RE, "product_tree_sha")
    art = m["artifacts"]
    _validar_hex(art["wheel"]["digest"], SHA256_RE, "wheel.digest")
    _validar_hex(art["sdist"]["digest"], SHA256_RE, "sdist.digest")
    ver = m["verification"]
    _validar_hex(ver["suite"]["junit_digest"], SHA256_RE, "junit_digest")
    _validar_hex(ver["gates"]["manifest_digest"], SHA256_RE, "gates.manifest_digest")
    _validar_hex(ver["e2e"]["manifest_digest"], SHA256_RE, "e2e.manifest_digest")
    _validar_hex(ver["ci"]["run_sha"], SHA1_RE, "ci.run_sha")


def test_el_product_sha_existe_en_git_y_coincide_con_el_arbol():
    m = _cargar()
    rc = _cargar()["release_candidate"]
    assert _commit_existe(rc["product_sha"]), "el product_sha no existe en git"
    p = subprocess.run(["git", "rev-parse", f"{rc['product_sha']}^{{tree}}"],
                       cwd=str(REPO), capture_output=True, text=True)
    assert p.returncode == 0
    assert p.stdout.strip() == rc["product_tree_sha"], "el tree del manifiesto no coincide"


def test_el_head_documental_tiene_al_candidato_como_padre():
    """El commit que fija el manifiesto (HEAD) desciende del product_sha."""
    m = _cargar()
    rc = m["release_candidate"]
    padre = subprocess.run(["git", "rev-parse", "HEAD^"], cwd=str(REPO),
                           capture_output=True, text=True)
    # El manifiesto definitivo puede estar en el propio commit candidato
    # (primera publicacion) o en un delta documental posterior.
    if padre.returncode == 0 and padre.stdout.strip() == rc["product_sha"]:
        return
    rama = subprocess.run(["git", "merge-base", "--is-ancestor",
                           rc["product_sha"], "HEAD"], cwd=str(REPO),
                          capture_output=True)
    assert rama.returncode == 0, "el product_sha no es ancestro del HEAD documental"


def test_negativo_hash_mal_formado_es_rechazado():
    with pytest.raises(ValueError):
        _validar_hex("8cda5ef4", SHA256_RE, "digest_recortado")
    with pytest.raises(ValueError):
        _validar_hex("8CDA5EF45626DD244199528EB3F8B5403788F6F1E4B3E2E75AC98F5F737F3CFD",
                     SHA256_RE, "digest_mayusculas")
    with pytest.raises(ValueError):
        _validar_hex("z" * 64, SHA256_RE, "digest_no_hex")
    with pytest.raises(ValueError):
        _validar_hex(None, SHA1_RE, "sha_ausente")


def test_negativo_sha_ajeno_no_existe_en_git():
    # 40 hex VALIDOS en formato, pero un SHA que no existe en el repo.
    ajeno = "0" * 40
    assert SHA1_RE.match(ajeno), "el formato acepta el sha sintetico"
    assert not _commit_existe(ajeno), "el sha sintetico no debe existir en git"


def test_negativo_la_prosa_no_se_cuela_en_los_campos_de_identidad():
    """El defecto original (QA-R14-DOC-02): un SHA con comentario anexado."""
    contaminado = "015b7765b80cac21c6dcf859ae075d036cd01def (commit de congelacion)"
    with pytest.raises(ValueError):
        _validar_hex(contaminado, SHA1_RE, "product_sha_contaminado")


def test_governance_declara_el_estado_fail_closed():
    m = _cargar()
    g = m["governance"]
    assert g["release_authorized"] is False
    assert g["publication_status"] == "CANDIDATE"
    assert g["qg_statuses"]["QG-07"] == "BLOCKED"
