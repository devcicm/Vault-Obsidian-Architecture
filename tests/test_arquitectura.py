"""El plano técnico tiene guard, y el kernel de inyección funciona de verdad.

`scripts/vault_arch.py` declara los nueve contextos acotados y sus fronteras.
Sin estas pruebas sería un documento más: la regla 3 de `CLAUDE.md` pide
registro canónico → doc derivada → guard que falla si divergen → test, y esto es
el cuarto paso.

El test que decide si el refactor sirve para algo es
`test_dos_raices_en_el_mismo_proceso_no_se_contaminan`. Si eso falla, la
inyección es decorativa: `VaultContext` sería un envoltorio bonito sobre el
mismo estado global que ya había.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import vault_arch as arch  # noqa: E402
from vault.kernel import VaultContext, construir  # noqa: E402


# ── El registro y su guard ───────────────────────────────────────────────────

def test_todo_modulo_en_disco_pertenece_a_un_contexto():
    """Puerta dura desde el primer día: clasificar cuesta una línea.

    Es el mismo hueco que cerró la invariante 4 de `vault_mcp_catalog`: cinco
    módulos con CLI propia no estaban en ningún registro, y uno era el que corre
    las puertas de cierre.
    """
    huerfanos = arch.sin_clasificar()
    assert not huerfanos, (
        f"módulos que ningún contexto reclama: {huerfanos}. Añádelos a CONTEXTS "
        f"en scripts/vault_arch.py."
    )


def test_ningun_modulo_declarado_desaparecio_del_disco():
    assert not arch.fantasmas()


def test_ningun_modulo_esta_en_dos_contextos():
    """`_mapa_modulos` revienta si hay solape; aquí se comprueba que no lo hay."""
    mapa = arch._mapa_modulos()
    total = sum(len(c["modulos"]) for c in arch.CONTEXTS.values())
    assert len(mapa) == total


def test_cada_contexto_declara_lenguaje_y_puertos():
    """Un contexto sin lenguaje ubicuo no es un contexto: es una carpeta."""
    for nombre, datos in arch.CONTEXTS.items():
        assert datos["lenguaje"], nombre
        assert datos["puertos"], nombre
        assert datos["modulos"], nombre


def test_el_meta_toolkit_declara_su_prohibicion():
    """Es el único contexto cuya frontera es una prohibición, no una interfaz."""
    assert any(
        "vault" in p for p in arch.CONTEXTS["meta_toolkit"]["prohibe"]
    ), "el meta-toolkit dejó de declarar que no escribe en un vault"


def test_la_baseline_de_fronteras_solo_encoge():
    r = arch.check()
    assert not r["new_crossings"], (
        f"fronteras nuevas: {r['new_crossings']}. Se arreglan publicando un "
        f"puerto en el contexto destino, no ampliando arch-baseline.json."
    )


def test_la_baseline_esta_al_dia_si_encogio():
    """Si se saldó deuda, la baseline lo refleja o el guard deja de apretar."""
    r = arch.check()
    assert not r["settled_crossings"], (
        f"estas fronteras ya no se cruzan: {r['settled_crossings']} — corre "
        f"`python scripts/vault_arch.py --freeze` para que no puedan volver"
    )


def test_el_map_responde_la_pregunta_que_hoy_nadie_puede_responder():
    assert arch.contexto_de("vault_backup") == "durabilidad"
    assert arch.contexto_de("vault_io") == arch.KERNEL
    assert arch.contexto_de("no_existe") is None


# ── El plano derivado ────────────────────────────────────────────────────────

def test_el_blueprint_nombra_todos_los_contextos_y_sus_modulos():
    doc = arch.blueprint()
    for datos in arch.CONTEXTS.values():
        assert datos["titulo"] in doc
        for mod in datos["modulos"]:
            assert f"`{mod}`" in doc, mod


def test_el_documento_publicado_esta_al_dia():
    """AP-47 sobre el propio plano: derivado que se commitea y se queda quieto."""
    publicado = (REPO_ROOT / "docs" / "ARQUITECTURA.md").read_text(encoding="utf-8")
    assert publicado.strip() == arch.blueprint().strip(), (
        "docs/ARQUITECTURA.md difiere del registro — regenera con "
        "`python scripts/vault_arch.py --blueprint`"
    )


# ── La inyección, ejercida ───────────────────────────────────────────────────

def test_el_contexto_es_inmutable():
    """Mutable, dos raíces volverían a poder contaminarse — con apariencia de DI."""
    c = construir()
    with pytest.raises(Exception):
        c.raiz = Path("/otro")


def test_la_confianza_viaja_con_la_raiz():
    c = construir()
    assert c.origen, "el origen de la detección no puede quedar vacío"
    assert c.raiz.name == "vault-sandbox", c.raiz


def test_una_raiz_explicita_se_declara_como_tal(tmp_path):
    c = construir(tmp_path)
    assert c.origen == "explicit_argument"
    assert c.raiz == tmp_path.resolve()


def test_la_contencion_ap36_es_invariante_del_contexto(tmp_path):
    """Salir del vault deja de depender de que cada tool se acuerde de mirar."""
    c = construir(tmp_path)
    assert c.ruta("07_Knowledge", "n.md").is_relative_to(tmp_path.resolve())
    for escape in (("..", "fuera.md"), ("..", "..", "etc", "passwd")):
        with pytest.raises(ValueError, match="AP-36"):
            c.ruta(*escape)


def test_dos_raices_en_el_mismo_proceso_no_se_contaminan(tmp_path):
    """**El criterio que decide si la inyección es real.**

    Hoy es imposible con las tools: 82 vínculos congelados al importar hacen que
    la primera raíz gane para todo el proceso, y por eso `cli/runner.py` aísla
    cada tool en un subproceso. Si este test pasa, el aislamiento por proceso
    pasa a ser una elección en vez de una necesidad.
    """
    a, b = construir(tmp_path / "a"), construir(tmp_path / "b")

    assert a.raiz != b.raiz
    assert a.ruta("00_System").is_relative_to(a.raiz)
    assert b.ruta("00_System").is_relative_to(b.raiz)
    assert not b.ruta("00_System").is_relative_to(a.raiz)

    # Y las secciones se resuelven contra SU raíz, no contra una global.
    assert a.secciones.ruta_de("07_Knowledge").is_relative_to(a.raiz)
    assert b.secciones.ruta_de("07_Knowledge").is_relative_to(b.raiz)


def test_el_escritor_escribe_atomico_y_dentro(tmp_path):
    c = construir(tmp_path)
    destino = c.ruta("07_Knowledge", "nota.md")
    c.escritor.escribir(destino, "# hola\n\nacentuación y ñ\n")
    assert destino.read_text(encoding="utf-8").startswith("# hola")
    assert c.lector.leer(destino).endswith("ñ\n")


def test_las_secciones_salen_del_registro_no_de_literales(tmp_path):
    """487 literales de sección existen pese a haber fuente única (AP-05)."""
    import vault_registry

    c = construir(tmp_path)
    assert list(c.secciones.ordenadas()) == list(vault_registry.ORDERED_SECTIONS)
    with pytest.raises(ValueError):
        c.secciones.ruta_de("99_Inventada")


def test_las_normas_salen_del_catalogo(tmp_path):
    c = construir(tmp_path)
    assert c.normas.por_codigo("AP-49")["severity"] == "high"
    assert c.normas.por_codigo("AP-00") is None
    assert len(c.normas.vigentes()) >= 60


# ── La regresión que provocó este mismo refactor ─────────────────────────────

def test_un_paquete_python_no_se_confunde_con_un_vault():
    """Crear `vault/` rompió la autodetección, y lo hizo anunciando confianza.

    La rama «fresh» aceptaba un candidato por el NOMBRE, sin exigir un solo
    marcador de vault, así que el paquete del refactor pasó a ser la raíz con
    origen `sibling_vault_dir_fresh`. Todas las tools habrían escrito dentro del
    código fuente.
    """
    import vault_io

    assert (REPO_ROOT / "vault" / "__init__.py").exists(), "el paquete existe"
    assert vault_io.get_vault_root().name == "vault-sandbox"
    assert vault_io.vault_root_origin() == "spec_repo_sandbox"


# ── El guard vigilándose a sí mismo: `vault/` también tiene fronteras ────────

def test_el_guard_ve_los_modulos_del_dominio():
    """El paquete que existe para imponer límites era el que podía cruzarlos.

    `vault_arch --check` nació mirando solo `scripts/`. Mientras fue así, el
    código nuevo pasaba únicamente por el guard de AP-49 y su clasificación por
    contexto no la comprobaba nadie.
    """
    modulos = arch._modulos_dominio()
    assert modulos, "sin módulos de dominio el guard no está midiendo nada"
    assert "vault/kernel/contexto.py" in modulos
    assert modulos["vault/durabilidad/repositorio.py"] == "durabilidad"
    assert "vault/__init__.py" not in modulos, "la raíz del paquete no es contexto"


def test_un_paquete_de_dominio_sin_contexto_declarado_no_pasa(tmp_path, monkeypatch):
    """La convención es el registro: `vault/<contexto>/` declara pertenencia.

    Un paquete cuyo nombre no esté en `CONTEXTS` se reporta sin clasificar en
    vez de colarse — el mismo trato que un módulo huérfano de `scripts/`.
    """
    (tmp_path / "inventado").mkdir()
    (tmp_path / "inventado" / "cosa.py").write_text("x = 1", encoding="utf-8")
    monkeypatch.setattr(arch, "DOMINIO_DIR", tmp_path)
    assert arch.dominio_sin_clasificar() == ["vault/inventado/cosa.py"]


def test_un_import_relativo_a_otro_contexto_es_un_cruce(tmp_path, monkeypatch):
    """`from ..gobernanza.x import y` cruza igual que `import vault_norms`.

    Los imports relativos hay que resolverlos a mano; ignorarlos dejaría ciego
    al guard justo donde más barato sale corregir.
    """
    (tmp_path / "durabilidad").mkdir()
    (tmp_path / "durabilidad" / "fuga.py").write_text(
        "from ..gobernanza.reglas import algo\n", encoding="utf-8"
    )
    monkeypatch.setattr(arch, "DOMINIO_DIR", tmp_path)
    cruces = [c for c in arch.cruces() if c["from"].startswith("vault/")]
    assert {"from": "vault/durabilidad/fuga.py", "from_context": "durabilidad",
            "to": "vault/gobernanza", "to_context": "gobernanza"} in cruces


def test_depender_del_propio_contexto_o_del_kernel_no_es_cruce(tmp_path, monkeypatch):
    """Límite 1: el kernel es de todos. Y dentro de casa no hay frontera."""
    (tmp_path / "durabilidad").mkdir()
    (tmp_path / "durabilidad" / "limpio.py").write_text(
        "from ..kernel.contexto import VaultContext\nfrom .modelo import Backup\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(arch, "DOMINIO_DIR", tmp_path)
    assert [c for c in arch.cruces() if c["from"].startswith("vault/")] == []


def test_la_raiz_de_composicion_es_una_excepcion_con_nombre():
    """Cablear implica conocer a todos; esconderlo en el guard, no.

    La excepción compra que ese conocimiento viva en un fichero en vez de
    repartirse por el dominio, y se paga leyéndolo entero al revisarlo. Por eso
    está declarada por nombre y es exactamente uno.
    """
    assert arch.RAIZ_COMPOSICION in arch._modulos_dominio()
    assert any("composición" in lim for lim in arch.LIMITES)
    fuera = [c["from"] for c in arch.cruces() if c["from"].startswith("vault/")]
    assert arch.RAIZ_COMPOSICION not in fuera
    # Y es la única que se salta el límite 2: si mañana otro fichero del dominio
    # importa `scripts/`, el guard tiene que verlo.
    assert isinstance(arch.RAIZ_COMPOSICION, str)


def test_el_paquete_de_dominio_esta_declarado_en_pyproject():
    """Funcionaba por `sys.path`, no por instalación (AP-42 en el empaquetado).

    `scripts/` sigue fuera a propósito: se resuelve por ruta de fichero.
    """
    texto = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for paquete in ("vault", "vault.kernel", "vault.durabilidad"):
        assert f'"{paquete}"' in texto, f"{paquete} no se instalaría"
