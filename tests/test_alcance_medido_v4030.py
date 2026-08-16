"""v40.30 — el alcance que se amplió donde se buscan los ficheros y no donde se decide.

Las tres correcciones de esta tanda tienen la **misma forma de defecto**, y por
eso comparten fichero: una medida cuyo alcance declarado es más ancho que el
alcance que de verdad recorre. El resultado no es un error visible sino un cero
—la peor salida posible de un guard, porque se lee igual que estar limpio.

- `cli/` estaba en `vault_arch.ARBOLES_MEDIDOS` desde v40.9 y `CONTEXTS` no
  declaraba contexto `cli`, así que `_mapa_modulos()` devolvía `None` para sus
  ficheros y las dos rutas de detección los descartaban antes de leer un import.
- `vault_audit` recorría el disco 25 veces por invocación para leer el mismo
  contenido, tres cuartas partes de ellas trabajo repetido.
- `vault_ciclos` mide el grafo de `scripts/`, así que `vault/` —el paquete que
  existe para imponer fronteras— era el único cuyos ciclos no contaba nadie.

Cada test de aquí falla si la corrección se revierte. Ninguno comprueba una
cifra global: comprueban la propiedad, que es lo que sobrevive a la siguiente
tanda.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_arch as A  # noqa: E402
import vault_ciclos as C  # noqa: E402
import vault_io  # noqa: E402


# --------------------------------------------------------------------------
# ① `cli/` medido pero inclasificable
# --------------------------------------------------------------------------

def test_cli_tiene_contexto_declarado():
    """Sin contexto, `cli/` está en ARBOLES_MEDIDOS y no lo mide nadie."""
    assert "cli" in A.CONTEXTS
    assert A.CONTEXTS["cli"]["modulos"], "un contexto sin módulos vuelve al cero"


def test_los_modulos_de_cli_se_clasifican():
    """El mapa tiene que devolver `cli` para ellos, no `None`.

    Este es el sitio exacto del defecto: `if origen is None: continue`, antes de
    leer un solo import.
    """
    mapa = A._mapa_modulos()
    en_disco = C._modulos_dominio  # noqa: F841 — solo para fijar el import
    for nombre in A._modulos_cli():
        assert mapa.get(nombre) == "cli", (
            f"cli/{nombre}.py se mide pero no se clasifica: vuelve al punto "
            "ciego que arregló v40.30")


def test_el_cruce_de_cli_al_meta_toolkit_se_cuenta():
    """`cli/registry` lee el catálogo desde siempre; hasta v40.30 no era contable."""
    cruces = A.cruces()
    origenes = {c["from"] for c in cruces} if isinstance(cruces, list) else set()
    assert any(o.startswith("cli/") for o in origenes), (
        "ningún cruce sale de `cli/`: o se dejó de recorrer el árbol, o se "
        "dejó de declarar el contexto — v40.30 necesitó las dos mitades")


def test_cli_declara_su_cruce_en_el_presupuesto():
    """Un cruce contable sin entrada en el presupuesto bloquea la puerta."""
    assert any(k[0] == "cli" for k in A.PRESUPUESTO_DE_CRUCES)


def test_ningun_modulo_declarado_es_fantasma():
    """`fantasmas()` solo sabía globear `scripts/vault_*.py`.

    Al declarar el contexto `cli` dio por ausentes sus siete ficheros, que
    existían todos: la misma forma del defecto que la tanda arregla.
    """
    assert A.fantasmas() == []


def test_la_excepcion_de_alcance_sobrevive_a_un_freeze(tmp_path, monkeypatch):
    """Un `--freeze` que la borrase dejaría el fichero mudo.

    La regla del repo es que una deuda saldada pasa a `saldada` en vez de
    desaparecer, por el mismo motivo: una entrada borrada no se distingue de
    una que nadie volvió a mirar. `excepcion_de_alcance` la escribe una persona
    y el escritor automático no la conoce — así que tiene que conservarla.
    """
    import json

    destino = tmp_path / "arch-baseline.json"
    # El valor da igual —lo que se prueba es que sobreviva— pero escribirlo a
    # mano lo convierte en una cifra que envejece, y hay un guard que lo mira.
    marca = {"version": "cualquiera", "por_que": "prueba"}
    destino.write_text(
        json.dumps({"crossings": [], "excepcion_de_alcance": marca}),
        encoding="utf-8")
    monkeypatch.setattr(A, "BASELINE_PATH", destino)
    A.freeze()
    escrito = json.loads(destino.read_text(encoding="utf-8"))
    assert escrito.get("excepcion_de_alcance") == marca


def test_la_baseline_real_declara_su_excepcion():
    """El único cruce que hizo crecer la lista está nombrado uno a uno."""
    import json

    datos = json.loads(A.BASELINE_PATH.read_text(encoding="utf-8"))
    exc = datos.get("excepcion_de_alcance")
    assert exc, "la lista creció y no hay excepción declarada"
    assert exc["entrada"] in datos["crossings"]
    assert exc.get("no_es_precedente"), "una excepción sin límite escrito es una puerta abierta"


# --------------------------------------------------------------------------
# ② El barrido repetido de `vault_audit`
# --------------------------------------------------------------------------

def test_vault_audit_recorre_el_disco_una_vez_por_medida(tmp_path, monkeypatch):
    """Cuenta `rglob` de verdad, no confía en leer el código.

    Eran 25 recorridos completos por invocación (dos en `_get_active_notes`,
    uno en `_build_indexes`, uno en `_detect_broken_links` y veinte en
    `_detect_empty_indexes`, uno por carpeta de primer nivel). El límite de 4
    deja margen para una medida nueva sin volver a tolerar veinticinco.
    """
    import vault_audit  # import local: fija la raíz antes de tocarlo

    vault = tmp_path / "v"
    (vault / "00_System").mkdir(parents=True)
    (vault / "10_Notes").mkdir()
    (vault / "10_Notes" / "a.md").write_text(
        "---\ntitle: A\nstatus: active\n---\n\ncuerpo\n", encoding="utf-8")

    llamadas = []
    original = Path.rglob

    def espia(self, patron):
        if patron == "*.md":
            llamadas.append(str(self))
        return original(self, patron)

    monkeypatch.setattr(Path, "rglob", espia)
    anterior = vault_io.get_vault_root()
    try:
        vault_io.set_vault_root(vault)
        vault_audit.vault_audit()
    finally:
        vault_io.set_vault_root(anterior)

    assert len(llamadas) <= 4, (
        f"{len(llamadas)} barridos de `*.md` por invocación: el dato "
        "compartido es el barrido crudo y se pasa como argumento "
        f"({llamadas})")


def test_las_firmas_viejas_de_vault_audit_siguen_valiendo(tmp_path):
    """No-derogación: `barrido` es opcional y el llamador viejo no se toca.

    Los tests que llaman `_build_indexes(notas)` con un solo argumento son
    llamadores legítimos y no debían migrarse en la misma tanda.
    """
    import vault_audit

    anterior = vault_io.get_vault_root()
    vault = tmp_path / "v"
    (vault / "10_Notes").mkdir(parents=True)
    (vault / "10_Notes" / "a.md").write_text("# A\n", encoding="utf-8")
    try:
        vault_io.set_vault_root(vault)
        notas = vault_audit._get_active_notes()
        backlinks, stems = vault_audit._build_indexes(notas)
        vault_audit._detect_broken_links(notas, stems)
        vault_audit._detect_empty_indexes()
    finally:
        vault_io.set_vault_root(anterior)
    assert "a" in stems


# --------------------------------------------------------------------------
# ③ Los ciclos del dominio
# --------------------------------------------------------------------------

def test_el_dominio_se_mide(tmp_path):
    """Un cero aquí no distingue «no hay ciclos» de «no se miró»."""
    assert C._modulos_dominio(), "no se está recorriendo `vault/`"
    assert C.check()["domain_modules"] > 0


def test_el_ciclo_conocido_del_kernel_esta_declarado():
    """Un comentario en el código no impide que el ciclo crezca; esto sí."""
    esperados = C.CICLOS_DEL_DOMINIO_ESPERADOS
    assert "vault/kernel/adaptadores.py <-> vault/kernel/contexto.py" in esperados
    for motivo in esperados.values():
        assert len(motivo) > 80, "un ciclo declarado sin motivo escrito es una excepción muda"


def test_no_hay_ciclos_del_dominio_sin_declarar():
    r = C.check()
    assert r["new_domain_cycles"] == [], (
        "ciclo nuevo en `vault/`: se invierte la dependencia, no se añade a "
        f"CICLOS_DEL_DOMINIO_ESPERADOS — {r['new_domain_cycles']}")


def test_un_ciclo_nuevo_del_dominio_rompe_la_puerta(monkeypatch):
    """El test que decide si la medida sirve de algo.

    Sin esto, `domain_cycles` sería un informe: publica un número y no impide
    nada. La regla 4 pide guard, y un guard que no muerde no es un guard.
    """
    monkeypatch.setattr(
        C, "ciclos_del_dominio",
        lambda: sorted(set(C.CICLOS_DEL_DOMINIO_ESPERADOS) | {"vault/a.py <-> vault/b.py"}))
    r = C.check()
    assert r["ok"] is False
    assert r["new_domain_cycles"] == ["vault/a.py <-> vault/b.py"]


def test_un_ciclo_declarado_que_desaparece_se_publica(monkeypatch):
    """Se resuelve sin romper: la lista solo puede encoger, y encoger es bueno."""
    monkeypatch.setattr(C, "ciclos_del_dominio", lambda: [])
    r = C.check()
    assert r["ok"] is True
    assert r["resolved_domain_cycles"] == sorted(C.CICLOS_DEL_DOMINIO_ESPERADOS)


def test_el_import_diferido_del_dominio_cuenta_como_ciclo():
    """Meterlo dentro de una función es lo que AP-58 persigue.

    `contexto.py` difiere su import de `adaptadores` precisamente para esquivar
    el ciclo. Si la medida descontara los diferidos, el par no aparecería — y el
    caso que la norma existe para ver saldría verde.
    """
    assert "vault/kernel/adaptadores.py <-> vault/kernel/contexto.py" in C.ciclos_del_dominio()
