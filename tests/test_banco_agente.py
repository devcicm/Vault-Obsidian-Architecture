"""La promesa del servicio, medida como la ejerce un agente: `tests/banco_agente.py`.

Medido el 2026-10-07 al construir el banco: con el perfil `agente`, la pista de
`INVALID_FOLDER` mandaba a `vault_section --list`, que no nombraba las
secciones del estándar, y el agente que la seguía no llegaba a escribir. La
tarea `recuperarse` es la que lo habría visto; cada tarea va en su propio test
para que un rojo diga cuál de las cinco promesas se rompió.
"""

import shutil

import pytest

import banco_agente as banco
pytestmark = pytest.mark.slow  # carril rápido (-m "not slow"): el perfil de la suite del 2026-10-20 midió aquí llamadas > 25 s


pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="el banco habla con el servidor MCP por Node"
)

TAREAS = ("orientar", "escribir", "recuperarse", "recordar", "borrar", "cerrar")


@pytest.fixture(scope="module")
def informe(tmp_path_factory):
    vault = banco._init_vault(tmp_path_factory.mktemp("banco") / "vault")
    return banco.correr(vault)


def test_el_agente_recibe_exactamente_su_perfil(informe):
    assert informe["perfil_expuesto"]


@pytest.mark.parametrize("tarea", TAREAS)
def test_cada_tarea_del_agente_sale_bien(informe, tarea):
    assert informe["tareas"][tarea]["ok"], informe["tareas"][tarea]


def test_la_pista_de_invalid_folder_lleva_a_escribir(informe):
    caso = informe["tareas"]["recuperarse"]["casos"]["INVALID_FOLDER"]
    assert caso["secciones_ofrecidas"] > 0, "la pista no nombra ninguna sección"
    assert caso["tras_la_pista"]


def test_lo_escrito_se_recuerda_en_una_sesion_nueva_y_primero(informe):
    """La sesión B no comparte nada con la A salvo el vault."""
    assert informe["tareas"]["recordar"]["posicion_en_pack"] == 1


def test_la_huella_ve_un_byte_cambiado(tmp_path):
    (tmp_path / "a.md").write_text("uno\n", encoding="utf-8")
    antes = banco.huella(tmp_path)
    (tmp_path / "a.md").write_text("uno.\n", encoding="utf-8")
    assert banco.huella(tmp_path) != antes


def test_un_vault_ajeno_dentro_del_repo_se_rechaza(capsys, tmp_path, monkeypatch):
    """Regla 7: con una ruta del repo mediría a vault-sandbox/, que comparte
    supuestos. Y el rechazo no deja un directorio temporal detrás."""
    monkeypatch.setattr(banco.tempfile, "tempdir", str(tmp_path))
    assert banco.main(["--copiar-de", str(banco.REPO_ROOT / "vault-sandbox")]) == 2
    assert not list(tmp_path.iterdir())


def test_los_argumentos_salen_del_uso_del_protocolo(informe):
    """Ningún paso de `inicio` se quedó sin derivar sus argumentos del registro."""
    assert all(p.get("por_que") != "uso sin derivar"
               for p in informe["tareas"]["orientar"]["pasos"])


def test_un_vault_viejo_orienta_con_una_salida_dentro_del_perfil(tmp_path):
    """Medido sobre una copia de /vcloud (v32): faltaban carpetas del estándar y
    `orientar` contaba el VALIDATION_FAILED como fallo del agente. Lo que se
    exige no es que valide, sino que el error diga cómo salir con una tool que
    el agente tiene."""
    vault = banco._init_vault(tmp_path / "vault")
    shutil.rmtree(vault / "21_QA")
    a = banco.Agente(vault)
    try:
        r = banco.orientar(a, set(banco.tools_del_perfil(banco.PERFIL)))
    finally:
        a.cerrar()
    assert r["ok"], r
    assert {"tool": "vault_validate", "error_code": "FOLDER_NOT_FOUND",
            "recovery_tool": "vault_standard_upgrade"} in r["hallazgos"], r


def test_un_titulo_repetido_no_cuenta_como_fallo_de_ranking(tmp_path):
    """Medido en una copia de /ans: los tres «no sale primera» eran dos notas
    con el mismo `title:` y puntuación casi igual. Preguntar por ese título es
    ambiguo; el banco lo separa en vez de culpar al ranking."""
    vault = banco._init_vault(tmp_path / "vault")
    a = banco.Agente(vault)
    try:
        cuerpo = "\n".join(f"Registro de cambios del servicio, entrada {i}." for i in range(4))
        assert banco._escribir(a, "07_Knowledge", "Registro de cambios", cuerpo)["ok"] is True
        # El estándar no deja escribir el duplicado (`note_moved`); un vault
        # heredado lo trae con otro nombre de fichero, como /ans.
        (vault / "05_Patterns" / "CHANGELOG_SERVICIO.md").write_text(
            '---\ntitle: "Registro de cambios"\n---\n\n# Registro de cambios\n\n' + cuerpo + "\n",
            encoding="utf-8")
        assert a("vault_reindex", {})["ok"] is True
        r = banco.recuerdo_preexistente(a, vault)
    finally:
        a.cerrar()
    assert r["ambiguas"] >= 2, r
    assert r["acierto_primera_sin_ambiguas"] == 1.0, r
