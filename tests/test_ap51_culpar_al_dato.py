"""AP-51 — la tool no acusa al dato de su propio fallo.

Los tests van contra el **detector**, no contra el repo. Un test que solo
comprobara "el repo está en cero" no distinguiría un guard que funciona de uno
que no encuentra nada porque su criterio está roto — que es literalmente lo que
le pasó a la primera versión de este detector, y es AP-44 otra vez.

Así que cada caso construye el fragmento que debe cazar y el fragmento
parecido que **no** debe cazar. La pareja es el test: cazar `except Exception:
return []` no vale de nada si también caza `except Exception: return {"ok":
False}`, porque entonces la norma no dice nada.
"""

import ast
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_blame_audit as blame  # noqa: E402
import vault_norms  # noqa: E402


def _handlers(fuente: str):
    return [
        n for n in ast.walk(ast.parse(fuente)) if isinstance(n, ast.ExceptHandler)
    ]


def _infringe(fuente: str) -> bool:
    """Aplica el criterio del audit a un fragmento suelto."""
    return blame.handler_infringe(_handlers(fuente)[0])


#: (fragmento, infringe, por qué). El "por qué" no es decoración: es lo que
#: hace revisable la tabla cuando alguien discuta un caso concreto.
CASOS = [
    # ── Infringen: el llamante no puede distinguir esto de un resultado real ──
    ("try:\n    x()\nexcept Exception:\n    return []", True,
     "lista vacía indistinguible de 'no tiene nada'"),
    ("try:\n    x()\nexcept Exception:\n    return {}", True,
     "dict vacío, igual"),
    ("try:\n    x()\nexcept Exception:\n    return None", True,
     "None indistinguible de 'no encontrado'"),
    ("try:\n    x()\nexcept Exception:\n    return", True,
     "return desnudo es None"),
    ("try:\n    x()\nexcept Exception:\n    pass", True,
     "sigue como si nada"),
    ("for i in y:\n    try:\n        x()\n    except Exception:\n        continue", True,
     "salta el elemento sin contarlo: el agregado queda corto y nadie lo sabe"),
    ("try:\n    x()\nexcept:\n    return []", True,
     "except desnudo, mismo caso"),
    ("try:\n    x()\nexcept BaseException:\n    return []", True,
     "BaseException es aún más amplia"),
    ("try:\n    x()\nexcept (Exception, ValueError):\n    return []", True,
     "basta con que una de la tupla sea amplia"),
    ("try:\n    x()\nexcept Exception:\n    return False", True,
     "un predicado que responde por el camino de fallo afirma lo que no comprobó"),
    ("try:\n    x()\nexcept Exception:\n    return True", True,
     "y en el otro sentido, igual"),
    ('try:\n    x()\nexcept Exception:\n    return {}, ""', True,
     "una tupla de vacíos es un vacío: el punto ciego de `vault_quality_check` "
     "(auditoría del 2026-10-15)"),
    ("try:\n    x()\nexcept Exception as e:\n    emit_error('t', 'X', str(e))\n    return []",
     True, "el envelope se construye y se tira: va a la traza y el llamante recibe "
           "el vacío de siempre (`vault_context_pack`, 2026-10-15)"),
    ("for i in y:\n    try:\n        x()\n    except Exception as e:\n"
     "        vault_errors.emit_error('t', 'X', str(e))\n        continue", True,
     "lo mismo saltando el elemento, y por atributo"),

    # ── No infringen: exponen el fallo, o el criterio es preciso ──
    ('try:\n    x()\nexcept Exception as e:\n    return {"ok": False, "error": str(e)}',
     False, "expone el fallo: el llamante recibe la mala noticia y decide"),
    ("try:\n    x()\nexcept Exception:\n    raise", False,
     "propaga, que es la forma más honesta"),
    ("try:\n    x()\nexcept Exception:\n    log(); return []", False,
     "deja rastro; el vacío ya no es mudo"),
    ("try:\n    x()\nexcept FileNotFoundError:\n    return []", False,
     "es un criterio: el autor sabe qué tolera y por qué"),
    ("try:\n    x()\nexcept (FileNotFoundError, json.JSONDecodeError):\n    return []",
     False, "tupla de excepciones concretas"),
    ("try:\n    x()\nexcept yaml.YAMLError:\n    return {}", False,
     "REGRESIÓN: la primera versión lo contaba como `except` desnudo porque "
     "`yaml.YAMLError` es ast.Attribute y no ast.Name — quince falsos positivos"),
    ("try:\n    x()\nexcept json.JSONDecodeError:\n    return None", False,
     "el mismo caso, y es el más común del repo"),
    ("try:\n    x()\nexcept Exception:\n    return [1]", False,
     "no está vacío: devuelve algo que el llamante puede mirar"),
    ("try:\n    x()\nexcept Exception:\n    return [], ['aviso']", False,
     "la tupla lleva el aviso: el llamante puede distinguirlo"),
    ("try:\n    x()\nexcept Exception as e:\n    return emit_error('t', 'X', str(e))",
     False, "el envelope se devuelve: eso es exponer el fallo"),
    ("try:\n    x()\nexcept Exception as e:\n    emit_error('t', 'X', str(e))", False,
     "sin vacío final el handler sigue adelante; no es la forma que se mide"),
]


@pytest.mark.parametrize("fuente,esperado,motivo", CASOS)
def test_el_criterio_distingue_tragarse_el_fallo_de_exponerlo(fuente, esperado, motivo):
    assert _infringe(fuente) is esperado, motivo


def test_las_excepciones_cualificadas_no_cuentan_como_amplias():
    """La regresión concreta, aislada.

    `except yaml.YAMLError` produce un `ast.Attribute`. La primera versión del
    detector hacía `[t.id] if isinstance(t, ast.Name) else ... else ["bare"]`,
    así que toda excepción cualificada caía en la rama del `except` desnudo.
    Resultado: 101 sitios medidos en vez de 86, y los quince de más eran las
    capturas *más* precisas del repo.
    """
    h = _handlers("try:\n    x()\nexcept yaml.YAMLError:\n    return {}")[0]
    assert blame._tipos_capturados(h) == []
    assert not (blame.AMPLIAS & set(blame._tipos_capturados(h)))


def test_la_baseline_esta_congelada_y_el_repo_no_ha_crecido():
    """El gate: la deuda histórica no bloquea, pero no puede crecer."""
    r = blame.scan()
    assert r["ok"], f"deuda AP-51 nueva: {r['new_offenders']}"
    assert r["new_offenders"] == []
    assert r["baseline_size"] > 0, (
        "una baseline vacía haría pasar este test sin medir nada"
    )


def test_la_baseline_apunta_a_sitios_que_existen():
    """Una baseline que envejece admite deuda nueva por la puerta de atrás.

    Si una firma congelada ya no corresponde a ningún handler —porque el
    handler se reescribió o desapareció— el sitio real cuenta como nuevo y el
    gate lo caza. Lo que este test cubre es lo contrario: entradas que ya no
    señalan a nada y que solo sirven para inflar `baseline_size`.
    """
    vivos = {o["firma"] for o in blame.offenders()}
    muertos = sorted(set(blame.load_baseline()) - vivos)
    assert not muertos, (
        f"{len(muertos)} entradas de la baseline ya no señalan a ningún handler; "
        f"ejecuta --freeze: {muertos[:5]}"
    )


def test_la_norma_esta_registrada_con_enforcement_real():
    """Regla 5 de AGENTS.md: ninguna norma nueva puede ser `manual`."""
    norma = next(n for n in vault_norms.NORM_CATALOG if n["code"] == "AP-51")
    assert norma["enforcement"] in {"guard", "audit", "guard+audit", "recommended"}
    assert norma["enforcement"] == "guard+audit"
    assert norma["tools_enforcing"], "una norma sin tool que la aplique es prosa"


def test_el_audit_se_excluye_a_si_mismo():
    """Sus propios ejemplos en el docstring y el epílogo no son infracciones.

    Sin esta exclusión el guard se acusaría a sí mismo por documentar lo que
    persigue, que es la forma más tonta de que una norma pierda credibilidad.
    """
    assert not any(o["module"] == "vault_blame_audit.py" for o in blame.offenders())


def test_freeze_no_se_ejecuta_por_error_al_solo_comprobar(tmp_path, monkeypatch):
    """`--check` no debe tocar la baseline (AP-36: side effect no declarado)."""
    destino = tmp_path / "blame-baseline.json"
    destino.write_text(json.dumps({"norm": "AP-51", "sites": []}), encoding="utf-8")
    monkeypatch.setattr(blame, "BASELINE_PATH", destino)
    antes = destino.read_bytes()
    blame.scan()
    assert destino.read_bytes() == antes


# --- La frontera JS (v41.2): el AST de Python no ve el `.mjs` ---------------

@pytest.mark.parametrize("fuente,esperado,motivo", [
    ("try { f(); } catch (_) {}", True, "vacío"),
    ("try { f(); } catch { }", True, "vacío sin binding"),
    ("try { f(); } catch (_) { /* skip */ }", True, "un comentario sin motivo"),
    ("try { f(); } catch (_) {\n  // nada\n}", True, "comentario de línea sin motivo"),
    ("try { f(); } catch (_) { /* AP-51: cae al error de abajo */ }", False, "declara por qué"),
    ("try { f(); } catch (e) { log(\"warn\", e); }", False, "expone el fallo"),
    ("try { f(); } catch (e) { throw e; }", False, "propaga"),
    ("// antes era `catch (_) {}` y se tragaba el fallo", False, "mención en un comentario"),
])
def test_ap51_el_detector_js_distingue_silencio_de_motivo(tmp_path, fuente, esperado, motivo):
    (tmp_path / "srv.mjs").write_text(fuente + "\n", encoding="utf-8")
    assert bool(blame.catch_silenciosos_js(tmp_path)) is esperado, motivo


def test_ap51_el_detector_js_no_mide_dependencias(tmp_path):
    (tmp_path / "node_modules" / "x").mkdir(parents=True)
    (tmp_path / "node_modules" / "x" / "i.js").write_text("try{}catch(_){}\n", encoding="utf-8")
    assert blame.catch_silenciosos_js(tmp_path) == []


def test_ap51_la_frontera_js_no_tiene_deuda_y_bloquea_la_puerta(tmp_path, monkeypatch):
    """Sin baseline: el servidor quedó en cero y un sitio nuevo tumba `ok`."""
    assert blame.catch_silenciosos_js() == []
    (tmp_path / "srv.mjs").write_text("try { f(); } catch (_) {}\n", encoding="utf-8")
    original = blame.catch_silenciosos_js
    monkeypatch.setattr(blame, "catch_silenciosos_js", lambda: original(tmp_path))
    resultado = blame.scan()
    assert resultado["ok"] is False
    assert [o["file"] for o in resultado["js_silent_catches"]] == ["srv.mjs"]
