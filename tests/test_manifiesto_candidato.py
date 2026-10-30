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
    # sin run de CI (NOT_RUN) no hay SHA que validar; con run, es hex puro.
    # La autorizacion exige ademas run_sha == product_sha (test de governance).
    if ver["ci"].get("status") != "NOT_RUN":
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


def test_governance_solo_autoriza_con_todo_en_pass():
    """Fail-closed (R23): `release_authorized: true` exige QG-00..07 en PASS,
    la CI del MISMO SHA concluida en success con todos sus jobs, y el acta del
    propietario existente. Cualquier otra combinacion debe declarar false."""
    m = _cargar()
    g = m["governance"]
    if g["release_authorized"] is not True:
        assert g["publication_status"] == "CANDIDATE"
        return
    assert g["publication_status"] == "AUTHORIZED"
    assert set(g["qg_statuses"]) == {f"QG-0{i}" for i in range(8)}
    assert all(v == "PASS" for v in g["qg_statuses"].values()), g["qg_statuses"]
    ci = m["verification"]["ci"]
    assert ci["run_sha"] == m["release_candidate"]["product_sha"]
    assert ci["conclusion"] == "success"
    assert ci["successful_jobs"] == ci["required_jobs"] > 0
    assert (REPO / g["owner_decision_ref"]).is_file()
    assert (REPO / m["verification"]["recibos"]).is_dir()


def test_release_yml_exige_la_ci_del_mismo_sha():
    """Fail-closed en la publicacion: `release.yml` no basta con
    `release_authorized`; la CI certificada tiene que ser la del `product_sha`
    y haber concluido en success. Un manifiesto con la CI de otro SHA (o sin
    CI, `NOT_RUN`) no publica aunque alguien lo marque como autorizado."""
    texto = (REPO / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert 'ci.get("run_sha") != sha' in texto
    assert 'ci.get("conclusion") != "success"' in texto


# --- B-01 / B-02 (vault dev codex, Fase 1): la puerta de publicacion se EJERCE ---

def _guion_de_la_puerta():
    """El Python del paso «El tag es el candidato autorizado» de release.yml."""
    import textwrap
    texto = (REPO / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    ini = texto.index("python - <<'EOF'\n") + len("python - <<'EOF'\n")
    return textwrap.dedent(texto[ini:texto.index("\n          EOF", ini)])


def _correr_puerta(tmp_path, mutar=None):
    """Repo git minimo con un manifiesto coherente; `mutar(m, tree)` lo estropea."""
    import copy
    import sys
    import yaml

    def git(*a):
        return subprocess.run(["git", *a], cwd=str(tmp_path), capture_output=True,
                              text=True, encoding="utf-8", check=True).stdout.strip()

    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\nversion="1.0"\n')
    (tmp_path / "audits" / "fase2").mkdir(parents=True)
    git("add", "-A")
    git("commit", "-qm", "producto")
    sha, tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
    m = {
        "release_candidate": {"product_sha": sha, "product_tree_sha": tree, "version": 1.0},
        "verification": {"ci": {"run_sha": sha, "conclusion": "success"}},
        "governance": {
            "release_authorized": True,
            "qg_statuses": {f"QG-0{i}": "PASS" for i in range(8)},
        },
    }
    m = copy.deepcopy(m)
    if mutar:
        mutar(m)
    (tmp_path / "audits" / "fase2" / "CANDIDATO-RELEASE.yaml").write_text(yaml.safe_dump(m))
    env = {**__import__("os").environ, "GITHUB_REF_NAME": "v1.0"}
    return subprocess.run([sys.executable, "-c", _guion_de_la_puerta()], cwd=str(tmp_path),
                          env=env, capture_output=True, text=True, encoding="utf-8")


@pytest.mark.skipif(__import__("sys").version_info < (3, 11), reason="tomllib")
def test_puerta_de_publicacion_acepta_el_candidato_coherente(tmp_path):
    assert _correr_puerta(tmp_path).returncode == 0


@pytest.mark.skipif(__import__("sys").version_info < (3, 11), reason="tomllib")
def test_puerta_de_publicacion_rechaza_qg_que_no_este_en_pass(tmp_path):
    """B-01: `release_authorized: true` con un QG en FAIL/NOT_RUN no publica."""
    def mutar(m):
        m["governance"]["qg_statuses"]["QG-03"] = "NOT_RUN"
    r = _correr_puerta(tmp_path, mutar)
    assert r.returncode != 0 and "QG-03" in r.stdout


@pytest.mark.skipif(__import__("sys").version_info < (3, 11), reason="tomllib")
def test_puerta_de_publicacion_rechaza_qg_ausentes(tmp_path):
    def mutar(m):
        del m["governance"]["qg_statuses"]["QG-07"]
    assert _correr_puerta(tmp_path, mutar).returncode != 0


@pytest.mark.skipif(__import__("sys").version_info < (3, 11), reason="tomllib")
def test_puerta_de_publicacion_ata_el_contenido_no_solo_la_ascendencia(tmp_path):
    """B-02: un `product_tree_sha` que no es el arbol de `product_sha` no publica."""
    def mutar(m):
        m["release_candidate"]["product_tree_sha"] = "0" * 40
    r = _correr_puerta(tmp_path, mutar)
    assert r.returncode != 0 and "product_tree_sha" in r.stdout
