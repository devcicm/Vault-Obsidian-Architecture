"""El vocabulario de los controles tiene un dueño, y el dueño es el núcleo.

La nota de causa raíz «A canonical vocabulary has three owners» (2026-10-30)
declaraba tres copias de `ESTADOS` y dos de `CONTROLES_OBLIGATORIOS`. Al
medirlo en `1db90da` el cuadro era distinto: de las tres, dos eran **código
muerto** (una constante que nadie leía) y las que quedaban eran un
vocabulario **distinto** (`("cubierta", "descubierta")` y
`("PASS", "FAIL", "BLOCKED")`, que no son estados de control). La copia viva
era la de `CONTROLES_OBLIGATORIOS` en el script de política de certificación.

Este test fija el estado final: un dueño, el registro, y nadie que escriba
los cuatro estados por su cuenta.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ESTADOS = ("ejecutado", "degradado", "fallido", "no_ejecutado")
DUENO = "vault/kernel/controles.py"


def _modulos_python() -> list[Path]:
    return (sorted(REPO_ROOT.glob("scripts/*.py"))
            + sorted(REPO_ROOT.glob("vault/**/*.py"))
            + sorted(REPO_ROOT.glob("audits/**/*.py")))


def test_el_dueno_declara_los_cuatro_estados():
    """El dueño es la hoja del núcleo: sin imports, importable por todos."""
    from vault.kernel import controles

    assert tuple(controles.ESTADOS) == ESTADOS, controles.ESTADOS
    assert tuple(controles.CONTROLES_OBLIGATORIOS) == tuple(controles.CONTROLES)


def test_los_controles_obligatorios_se_derivan_del_registro():
    """La lista no se escribe: sale de las claves del registro, así que no
    puede divergir de lo que el puerto ejecuta."""
    from vault.kernel import controles

    for control in controles.CONTROLES_OBLIGATORIOS:
        assert control in controles.CONTROLES, control


def test_ningun_modulo_escribe_los_cuatro_estados_por_su_cuenta():
    """El guard: si alguien reimplementa el vocabulario, el test falla."""
    culpables = []
    for p in _modulos_python():
        rel = p.relative_to(REPO_ROOT).as_posix()
        if rel == DUENO:
            continue
        try:
            arbol = ast.parse(p.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for n in ast.walk(arbol):
            if not isinstance(n, ast.Assign):
                continue
            for objetivo in n.targets:
                if not isinstance(objetivo, ast.Name):
                    continue
                if objetivo.id not in ("ESTADOS", "CONTROLES_OBLIGATORIOS"):
                    continue
                try:
                    valor = ast.literal_eval(n.value)
                except ValueError:
                    continue
                if isinstance(valor, tuple) and set(ESTADOS) <= set(valor):
                    culpables.append(f"{rel}:{n.lineno} {objetivo.id}")
    assert not culpables, (
        f"el vocabulario de estados tiene mas de un dueño: {culpables}")


def test_los_consumidores_importan_al_dueno():
    """Quien usa el vocabulario lo nombra; no lo reescribe."""
    from vault.gobernanza import controles as gobernanza

    assert gobernanza.ESTADOS is not None
    assert tuple(gobernanza.CONTROLES_OBLIGATORIOS) == ("AP-40", "AP-42", "AP-43")
    fuente = (REPO_ROOT / "vault/gobernanza/controles.py").read_text(encoding="utf-8")
    assert "from vault.kernel.controles import" in fuente, (
        "gobernanza debe leer el vocabulario de su dueño")
