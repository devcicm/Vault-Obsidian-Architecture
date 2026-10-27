"""El manifiesto del candidato es mecanicamente validable (QA-R14-DOC-02).

Los campos de identidad llevan SOLO valores (hex puro); las notas viven en
claves separadas. Este test valida el formato y la existencia real de los
SHAs, y ejercita los negativos: hash mal formado, SHA ajeno (que no existe
en git) y SHA real que NO es ancestro del HEAD documental deben ser
RECHAZADOS por el validador.

CONTRATO VIGENTE (QA-R16-DOC-01, confirmado en R18 por QA-R17-DOC-01): la
relación que se comprueba entre el product_sha y el HEAD documental es de
ASCENDENCIA (`merge-base --is-ancestor`), NO de paternidad inmediata
(`HEAD^`): entre el producto y el HEAD pueden intercalarse commits
documentales. `doc_parent_sha` es el commit de publicación inicial de este
manifiesto, no el padre actual.
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
                       cwd=str(REPO), capture_output=True, text=True,
                       encoding="utf-8")
    assert p.returncode == 0
    assert p.stdout.strip() == rc["product_tree_sha"], "el tree del manifiesto no coincide"


def test_el_product_sha_es_ancestro_del_head_documental():
    """El product_sha es ANCESTRO del HEAD documental (no su padre inmediato).

    QA-R16-DOC-01: el comentario del manifiesto decia `HEAD^ == product_sha`
    mientras la prueba admitia ascendencia. Aqui el contrato es UNICO: se
    comprueba ascendencia con `merge-base --is-ancestor`, y el manifiesto
    declara lo mismo (`documentation.product_ancestor_of_head: true`).
    """
    m = _cargar()
    rc = m["release_candidate"]
    assert m["release_candidate"]["documentation"]["product_ancestor_of_head"] is True
    p = subprocess.run(["git", "merge-base", "--is-ancestor",
                        rc["product_sha"], "HEAD"], cwd=str(REPO),
                       capture_output=True)
    assert p.returncode == 0, "el product_sha no es ancestro del HEAD documental"
    # El doc_parent_sha declarado (publicacion inicial del manifiesto) tiene
    # que existir en git: no se fabrica una relacion de paternidad.
    inicial = m["release_candidate"]["documentation"]["doc_parent_sha"]
    _validar_hex(inicial, SHA1_RE, "documentation.doc_parent_sha")
    assert _commit_existe(inicial), "el doc_parent_sha no existe en git"


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


def test_negativo_un_sha_producto_ajeno_que_existe_no_puede_certificar():
    """QA-R16-DOC-01: reforzar el negativo para un SHA producto ajeno.

    La punta de la rama de dictamen QA es un commit REAL de este
    repositorio que NO es ancestro del HEAD de la rama de trabajo: usarlo
    como product_sha tiene que fallar la comprobacion de ascendencia.
    (origin/main NO sirve como negativo: la rama de trabajo nace de main,
    asi que main SI es ancestro.)
    """
    import subprocess as _sp
    p = _sp.run(["git", "rev-parse",
                 "origin/qa/review-release-cli-mcp-09e849c-20261027"],
                cwd=str(REPO), capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        return  # sin esa rama en este clon: el negativo no aplica
    ajeno = p.stdout.strip()
    assert SHA1_RE.match(ajeno)
    assert _commit_existe(ajeno), "el commit ajeno deberia existir"
    r = _sp.run(["git", "merge-base", "--is-ancestor", ajeno, "HEAD"],
                cwd=str(REPO), capture_output=True)
    assert r.returncode != 0, ("la punta de la rama QA no deberia ser ancestro "
                               "del HEAD de la rama de trabajo")


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
