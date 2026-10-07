"""Los consumidores de secciones ven las propias que el vault declara (CN-02).

`vault_registry.secciones_del_vault(raiz)` suma a las del estándar las que el
vault declara en `00_System/secciones.json`. Declararlas no sirve de nada si los
que recorren el vault siguen leyendo `ORDERED_SECTIONS` a pelo: la nota de una
sección propia seguiría fuera de los índices, del contrato y del audit. Aquí se
prueba cada consumidor por donde el consumidor la ve.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import vault_registry as reg  # noqa: E402
from vault.indices.enumeracion import notas_en_disco  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.kernel.fallos import FalloDeDominio  # noqa: E402


def _vault(raiz: Path, secciones=None, notas=()) -> Path:
    for seccion in ("00_System", "07_Knowledge", "99_Index"):
        (raiz / seccion).mkdir(parents=True, exist_ok=True)
    if secciones is not None:
        (raiz / reg.SECCIONES_PROPIAS_RUTA).write_text(
            json.dumps({"schema": 1, "secciones": secciones}), encoding="utf-8")
    for rel in notas:
        p = raiz / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"---\ntitle: {p.stem}\n---\n# {p.stem}\n", encoding="utf-8")
    return raiz


_SCRIPTS_SEC = {"folder": "22_Scripts", "documentacion": "referencia", "tipos": ["script"]}


def test_el_puerto_de_secciones_incluye_las_propias(tmp_path):
    ctx = construir(_vault(tmp_path, [_SCRIPTS_SEC]))
    assert "22_Scripts" in ctx.secciones.ordenadas()
    assert ctx.secciones.existe("22_Scripts")
    assert ctx.secciones.ruta_de("22_Scripts") == ctx.raiz / "22_Scripts"


def test_sin_secciones_propias_el_puerto_es_el_registro(tmp_path):
    ctx = construir(_vault(tmp_path))
    assert list(ctx.secciones.ordenadas()) == list(reg.ORDERED_SECTIONS)


def test_una_seccion_no_declarada_sigue_sin_existir(tmp_path):
    ctx = construir(_vault(tmp_path, [_SCRIPTS_SEC]))
    assert not ctx.secciones.existe("scripts")
    with pytest.raises(ValueError):
        ctx.secciones.ruta_de("scripts")


def test_la_enumeracion_de_notas_ve_la_seccion_propia(tmp_path):
    raiz = _vault(tmp_path, [_SCRIPTS_SEC],
                  notas=["22_Scripts/deploy.md", "07_Knowledge/a.md", "scripts/b.md"])
    ctx = construir(raiz)
    rel = {p.relative_to(raiz).as_posix() for p in notas_en_disco(raiz, ctx.secciones.ordenadas())}
    assert "22_Scripts/deploy.md" in rel and "07_Knowledge/a.md" in rel
    assert "scripts/b.md" not in rel


def test_un_registro_roto_es_un_fallo_del_dominio_no_un_vacio(tmp_path):
    """AP-51: leerlo como «no hay propias» sacaría sus notas de los índices en silencio."""
    raiz = _vault(tmp_path)
    (raiz / reg.SECCIONES_PROPIAS_RUTA).write_text("{roto", encoding="utf-8")
    with pytest.raises(FalloDeDominio) as e:
        construir(raiz).secciones.ordenadas()
    assert e.value.causa == "INDICE_ILEGIBLE"


# ── El contrato de nota: una sección propia es contenido, no `sin_seccion` ──

import os  # noqa: E402
import subprocess  # noqa: E402

import vault_contrato_nota as contrato  # noqa: E402

_MINIMA = ("---\nid: x\ntitle: X\ncreatedAt: 2026-10-07T00:00:00Z\n"
           "updatedAt: 2026-10-07T00:00:00Z\n---\n# X\n")


def test_la_clase_de_una_nota_de_seccion_propia_es_contenido(tmp_path):
    raiz = _vault(tmp_path, [_SCRIPTS_SEC])
    assert contrato.clase_de_nota("22_Scripts/x.md", raiz) == "contenido"
    assert contrato.clase_de_nota("scripts/x.md", raiz) == "sin_seccion"
    # Sin raíz no se sabe qué declaró el vault: solo cuentan las del estándar.
    assert contrato.clase_de_nota("22_Scripts/x.md") == "sin_seccion"


def test_a_una_nota_de_seccion_propia_se_le_pide_el_contrato_de_contenido(tmp_path):
    raiz = _vault(tmp_path, [_SCRIPTS_SEC])
    datos = {"id": "x", "title": "X", "createdAt": "a", "updatedAt": "b"}
    assert "type" in contrato.faltantes(datos, "22_Scripts/x.md", raiz=raiz)
    assert contrato.faltantes(datos, "scripts/x.md", raiz=raiz) == []
    assert "type" in contrato.campos_requeridos("22_Scripts/x.md", raiz)


def _validar(raiz: Path, rel: str) -> dict:
    proceso = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_validate.py"),
         "--path", rel, "--check", "frontmatter"],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT / "scripts"),
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


def test_vault_validate_juzga_la_seccion_propia_con_su_raiz(tmp_path):
    raiz = _vault(tmp_path, [_SCRIPTS_SEC])
    for rel in ("22_Scripts/x.md", "scripts/x.md"):
        (raiz / rel).parent.mkdir(parents=True, exist_ok=True)
        (raiz / rel).write_text(_MINIMA, encoding="utf-8")
    assert _validar(raiz, "scripts/x.md")["ok"] is True
    propia = _validar(raiz, "22_Scripts/x.md")
    assert propia["ok"] is False
    assert "type" in json.dumps(propia)


# ── El audit de CN-02: declarar la sección es la salida de la violación ──

from vault.gobernanza.auditoria_runtime import auditar_runtime  # noqa: E402


def _cn02(raiz: Path) -> dict:
    return {v["path"]: v["detail"] for v in auditar_runtime(raiz)["violations"]
            if v["norm"] == "CN-02"}


def test_el_audit_no_reporta_cn02_de_una_seccion_declarada(tmp_path):
    raiz = _vault(tmp_path, [_SCRIPTS_SEC], notas=["22_Scripts/a.md", "scripts/b.md"])
    cn02 = _cn02(raiz)
    assert "22_Scripts" not in cn02
    assert "scripts" in cn02
    # La pista lleva a la salida que ahora existe.
    assert "vault_section" in cn02["scripts"]


def test_el_audit_reporta_un_registro_de_secciones_roto_sin_caerse(tmp_path):
    """AP-51: ni excepción ni «no hay propias» callado; se nombra el fichero."""
    raiz = _vault(tmp_path, notas=["22_Scripts/a.md"])
    (raiz / reg.SECCIONES_PROPIAS_RUTA).write_text("{roto", encoding="utf-8")
    cn02 = _cn02(raiz)
    assert reg.SECCIONES_PROPIAS_RUTA in cn02
    assert "22_Scripts" in cn02


# ── vault_write: el destino es una sección del vault (CN-02) ──
#
# Hasta v41.2 el catálogo afirmaba que `vault_write` exige un `--folder`
# canónico y escribía en `scripts/` sin protestar: cobertura declarada sin
# código detrás (AP-55). Ahora el destino se valida con el criterio de
# `vault_registry`, y una sección propia activa es un destino como otro.

_CUERPO = ("## Contexto\n\nPrimera línea real sobre el despliegue del servicio.\n"
           "Segunda línea real que explica el motivo de la decisión.\n"
           "Tercera línea real con la consecuencia y cómo se verifica.\n")


def _escribir(raiz: Path, folder: str, *extra: str) -> dict:
    proceso = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_write.py"),
         "--folder", folder, "--title", "Despliegue", "--content", _CUERPO,
         "--tags", "demo", *extra],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 VAULT_AGENT="system", PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT / "scripts"),
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


@pytest.mark.parametrize("folder", ["scripts", "23_Nada", "", "22_Viejo"])
def test_vault_write_rechaza_un_destino_que_no_es_seccion(tmp_path, folder):
    raiz = _vault(tmp_path, [{"folder": "22_Viejo", "documentacion": "guia",
                              "status": "retirada"}])
    r = _escribir(raiz, folder)
    assert r["ok"] is False and r["error_code"] == "INVALID_FOLDER", r
    assert "vault_section" in json.dumps(r, ensure_ascii=False)
    assert not list(raiz.rglob("despliegue.md"))


@pytest.mark.parametrize("folder", ["22_Scripts", "22_Scripts/deploy", "07_Knowledge"])
def test_vault_write_acepta_seccion_del_estandar_y_propia_activa(tmp_path, folder):
    raiz = _vault(tmp_path, [_SCRIPTS_SEC])
    r = _escribir(raiz, folder)
    assert r["ok"] is True, r
    assert (raiz / folder / "despliegue.md").is_file()


def test_vault_write_con_registro_de_secciones_roto_no_escribe(tmp_path):
    """Solo un destino que necesita el registro falla; el estándar no lo lee."""
    raiz = _vault(tmp_path)
    (raiz / reg.SECCIONES_PROPIAS_RUTA).write_text("{roto", encoding="utf-8")
    r = _escribir(raiz, "22_Scripts")
    assert r["ok"] is False and r["error_code"] == "DATA_FILE_CORRUPT", r
    assert not list(raiz.rglob("despliegue.md"))
    assert _escribir(raiz, "07_Knowledge")["ok"] is True


# ── El tipo de una nota de sección propia (C3) ──
#
# `type` se deriva de la carpeta, y una sección propia no tenía de dónde
# derivarlo: la nota nacía sin `type` y el contrato de contenido, que lo exige,
# la reprobaba. La sección declara sus `tipos`; si no lo hace, el tipo se pasa.

def _tipo_escrito(raiz: Path, folder: str) -> object:
    import yaml
    texto = (raiz / folder / "despliegue.md").read_text(encoding="utf-8")
    return yaml.safe_load(texto.split("---")[1]).get("type")


def test_vault_write_deriva_el_tipo_que_declara_la_seccion_propia(tmp_path):
    raiz = _vault(tmp_path, [_SCRIPTS_SEC])
    assert _escribir(raiz, "22_Scripts")["ok"] is True
    assert _tipo_escrito(raiz, "22_Scripts") == "script"
    assert _validar(raiz, "22_Scripts/despliegue.md")["ok"] is True


def test_sin_tipos_declarados_la_nota_no_nace_sin_type(tmp_path):
    raiz = _vault(tmp_path, [{"folder": "23_Libre", "documentacion": "guia"}])
    r = _escribir(raiz, "23_Libre")
    assert r["ok"] is False and r["error_code"] == "INVALID_INPUT", r
    assert "tipos" in json.dumps(r, ensure_ascii=False)
    assert not list(raiz.rglob("despliegue.md"))
    assert _escribir(raiz, "23_Libre", "--meta", '{"type": "guia"}')["ok"] is True
    assert _tipo_escrito(raiz, "23_Libre") == "guia"
    # Actualizar sin --meta conserva el tipo que la nota ya tiene.
    assert _escribir(raiz, "23_Libre")["ok"] is True
    assert _tipo_escrito(raiz, "23_Libre") == "guia"


# ── vault_frontmatter_completar ──
#
# Barría `ORDERED_SECTIONS` y derivaba el `type` sin la raíz: la nota de una
# sección propia no se completaba nunca sin `--path`, y con `--path` se quedaba
# sin `type` aunque la sección declarase sus `tipos`.

def _completar(raiz: Path, **kw):
    import vault_frontmatter_completar as vfc
    import vault_io
    vault_io.set_vault_root(raiz)
    return vfc.completar(**kw)


def _plan_de(informe, rel):
    return next((c for c in informe.get("completed", informe.get("completadas", []))
                 if c.get("path") == rel), None)


def test_completar_barre_la_seccion_propia(tmp_path):
    raiz = _vault(tmp_path, [_SCRIPTS_SEC], notas=["22_Scripts/deploy.md"])
    informe = _completar(raiz)
    assert _plan_de(informe, "22_Scripts/deploy.md"), informe


def test_completar_deriva_el_type_que_declara_la_seccion_propia(tmp_path):
    raiz = _vault(tmp_path, [_SCRIPTS_SEC], notas=["22_Scripts/deploy.md"])
    plan = _plan_de(_completar(raiz, path="22_Scripts/deploy.md"), "22_Scripts/deploy.md")
    assert plan and plan["fields"]["type"]["value"] == "script", plan


def test_completar_con_el_registro_roto_falla_en_vez_de_saltarse_las_propias(tmp_path):
    raiz = _vault(tmp_path, notas=["07_Knowledge/a.md"])
    (raiz / reg.SECCIONES_PROPIAS_RUTA).write_text("{roto", encoding="utf-8")
    informe = _completar(raiz)
    assert informe["ok"] is False and informe["error_code"] == "DATA_FILE_CORRUPT", informe


# ── vault_graph ──
#
# Barría `ORDERED_SECTIONS`: la nota de una sección propia no era nodo de
# `graph.json`, así que sus enlaces no contaban y quien la enlazaba la veía
# como destino roto.

def _grafo(raiz: Path):
    import vault_graph
    import vault_io
    vault_io.set_vault_root(raiz)
    return vault_graph.vault_graph()


def test_el_grafo_incluye_la_seccion_propia(tmp_path):
    raiz = _vault(tmp_path, [_SCRIPTS_SEC], notas=["22_Scripts/deploy.md"])
    informe = _grafo(raiz)
    assert informe["ok"] is True, informe
    grafo = json.loads((raiz / "99_Index" / "graph.json").read_text(encoding="utf-8"))
    assert "22_Scripts/deploy.md" in grafo["nodes"], sorted(grafo["nodes"])


def test_el_grafo_con_el_registro_roto_falla_en_vez_de_saltarse_las_propias(tmp_path):
    raiz = _vault(tmp_path, notas=["07_Knowledge/a.md"])
    (raiz / reg.SECCIONES_PROPIAS_RUTA).write_text("{roto", encoding="utf-8")
    informe = _grafo(raiz)
    assert informe["ok"] is False and informe["error_code"] == "DATA_FILE_CORRUPT", informe


# ── vault_graph_merge ──
#
# El mismo barrido por `ORDERED_SECTIONS` que `vault_graph`: la nota de una
# sección propia faltaba en `graph-enriched.json`.

def _grafo_enriquecido(raiz: Path):
    import vault_graph_merge
    import vault_io
    vault_io.set_vault_root(raiz)
    return vault_graph_merge.vault_graph_merge()


def test_el_grafo_enriquecido_incluye_la_seccion_propia(tmp_path):
    raiz = _vault(tmp_path, [_SCRIPTS_SEC], notas=["22_Scripts/deploy.md"])
    informe = _grafo_enriquecido(raiz)
    assert informe["ok"] is True, informe
    grafo = json.loads(
        (raiz / "99_Index" / "graph-enriched.json").read_text(encoding="utf-8"))
    nodos = grafo["nodes"]
    ids = set(nodos) if isinstance(nodos, dict) else {n.get("id") for n in nodos}
    assert "22_Scripts/deploy.md" in ids, sorted(ids)


def test_el_grafo_enriquecido_con_el_registro_roto_falla(tmp_path):
    raiz = _vault(tmp_path, notas=["07_Knowledge/a.md"])
    (raiz / reg.SECCIONES_PROPIAS_RUTA).write_text("{roto", encoding="utf-8")
    informe = _grafo_enriquecido(raiz)
    assert informe["ok"] is False and informe["error_code"] == "DATA_FILE_CORRUPT", informe
