"""C-03 — `_onboard_15_tests` clasifica por la palabra entera y solo ficheros de test.

Medido en el vault ajeno: el inventario `performance` listaba
`vault_toolkit/loading.py` (`load` dentro de `loading`) y `security` dos
módulos de producción. Un nombre de módulo no es evidencia de que sea un test.
"""
import vault_grafo_import as gi  # noqa: F401  (pone scripts/ en sys.path)
from vault_onboard import clasificar_test


def test_un_modulo_de_produccion_no_es_un_test():
    assert clasificar_test("vault_toolkit/loading.py") is None
    assert clasificar_test("src/security/policy.py") is None
    assert clasificar_test("src/performance_monitor.py") is None


def test_load_dentro_de_otra_palabra_no_es_performance():
    assert clasificar_test("tests/test_loading.py") == "unit"
    assert clasificar_test("tests/load/test_checkout.py") == "performance"


def test_la_palabra_entera_clasifica_los_tests_de_verdad():
    assert clasificar_test("tests/security/test_authz.py") == "security"
    assert clasificar_test("tests/test_integration_db.py") == "integration"
    assert clasificar_test("tests/e2e/login.py") == "e2e"
    assert clasificar_test("web/app.test.ts") == "unit"
    assert clasificar_test("tests/test_basico.py") == "unit"
