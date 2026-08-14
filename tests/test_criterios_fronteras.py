"""AP-57 a través de una frontera de lenguaje (v40.19).

Hasta v40.18 `vault_criterios` solo leía `scripts/*.py`, y el hueco no era
teórico: el criterio «esta tool no tiene script Python» estaba escrito cuatro
veces —una de ellas en `.mjs`— y la norma que existe justo para eso no podía
verlo. Una norma que parece cubierta y tiene un lado ciego es peor que una sin
detector: nadie vuelve a mirar.

Lo midió al nacer: la CI listaba a mano seis puertas de las diecisiete del
registro. Once no se ejecutaban en ningún PR y nada estaba roto — una copia a
través de una frontera no diverge de golpe, se atrasa.

Los tests que deciden si esto sirve de algo son los tres de la sección
«y que muerda». El resto describe; esos prueban.
"""

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_criterios as C  # noqa: E402


# ── El registro no se inventa lo que ya tiene dueño ──────────────────────────

def test_toda_zona_existe_en_el_registro_de_contextos():
    """Una frontera que declara una zona inventada es el mismo defecto un piso
    más arriba: el detector de criterios copiados, decidiendo por su cuenta."""
    from vault_arch import CONTEXTS

    for f in C.FRONTERAS:
        assert f["zona_dueña"] in CONTEXTS, (
            f"{f['frontera']} declara la zona `{f['zona_dueña']}`, que "
            f"`vault_arch.CONTEXTS` no reconoce"
        )


def test_toda_norma_existe_en_el_catalogo():
    from vault_norms import NORM_CATALOG

    codigos = {n["code"] for n in NORM_CATALOG}
    for f in C.FRONTERAS:
        assert f["norma"] in codigos, f"{f['frontera']} cita una norma inexistente"


def test_las_senales_se_piden_al_registro_que_las_posee():
    """Escribirlas en `FRONTERAS` sería reimplementar un criterio dentro del
    detector de criterios reimplementados."""
    con_registro = [c for f in C.FRONTERAS for c in f["criterios"] if "senales_de" in c]
    assert con_registro, "ninguna señal se deriva ya: se volvieron literales"
    for c in con_registro:
        assert C._senales_de(c["senales_de"]), f"{c['senales_de']} no devuelve señales"


def test_una_clave_de_senales_desconocida_no_se_lee_como_vacia():
    """AP-51: devolver `[]` haría pasar la frontera entera por limpia."""
    with pytest.raises(RuntimeError, match="señales sin registro"):
        C._senales_de("no_existe")


def test_toda_frontera_declara_por_que():
    for f in C.FRONTERAS:
        assert len(f.get("por_que", "")) > 80, (
            f"{f['frontera']} sin motivo escrito: una frontera sin porqué no se "
            f"revisa, se hereda"
        )


# ── La medida ────────────────────────────────────────────────────────────────

def test_el_repo_no_tiene_copias_nuevas_en_frontera():
    r = C.check()
    assert r["ok"], (
        f"criterios reescritos al otro lado de una frontera: {r['new_copies']}. "
        f"Se salda leyendo la pasarela, no ampliando la baseline."
    )


def test_el_envelope_publica_zona_y_norma_de_cada_frontera():
    r = C.check()
    assert r["boundaries_total"] == len(C.FRONTERAS)
    for b in r["boundaries"]:
        assert b["zona_dueña"] and b["norma"] and b["pasarelas"]
    json.dumps(r)  # la puerta lo consume por subproceso


def test_leer_la_pasarela_es_lo_que_distingue_cruzar_de_copiar():
    """El `.mjs` nombra variables de entorno del registro y NO es una copia.

    Si la exención por pasarela dejara de aplicarse, este fichero saldría como
    infractor y la medida se volvería ruido — que es como un guard deja de
    leerse.
    """
    mjs = (RAIZ / "mcp" / "nodejs" / "vault-mcp-server.mjs").read_text(encoding="utf-8")
    nombres = C._senales_de("entorno")
    assert [n for n in nombres if n in mjs], "el `.mjs` dejó de nombrar variables"
    assert "env-table.json" in mjs, "dejó de leer la pasarela: ahora sí sería copia"
    assert not [h for h in C.medir_fronteras() if h["modulo"].endswith(".mjs")]


def test_la_ci_ejecuta_las_puertas_por_el_registro():
    """El hallazgo que destapó la frontera, fijado para que no vuelva.

    No se comprueba que estén las diecisiete escritas —eso sería la copia otra
    vez, en un test—: se comprueba que invoca al registro.
    """
    ci = (RAIZ / ".github" / "workflows" / "vault-ci.yml").read_text(encoding="utf-8")
    assert "vault_gate.py" in ci, (
        "la CI volvió a listar puertas a mano: una puerta nueva no se ejecutará "
        "en ningún PR hasta que alguien se acuerde de añadirla aquí"
    )


def test_make_check_no_promete_menos_que_el_estandar():
    mk = (RAIZ / "Makefile").read_text(encoding="utf-8")
    assert "vault_gate.py" in mk


# ── Y que muerda ─────────────────────────────────────────────────────────────

def test_una_copia_nueva_en_frontera_rompe_la_puerta(monkeypatch, tmp_path):
    """**El criterio que decide si el guard es real** (AP-44).

    Se fabrica un `.mjs` que nombra una tool nativa sin leer el catálogo: es
    exactamente el defecto de v40.18, y tiene que salir en rojo.
    """
    (tmp_path / "mcp" / "nodejs").mkdir(parents=True)
    (tmp_path / "mcp" / "nodejs" / "falso.mjs").write_text(
        'const X = new Set(["vault_backup_base64"]);\n', encoding="utf-8"
    )
    monkeypatch.setattr(C, "REPO", tmp_path)
    hallazgos = C.medir_fronteras()
    copias = [h for h in hallazgos if h["criterio"] == "que_tools_se_despachan_en_js"]
    assert copias, "una copia evidente en `.mjs` no se detecta"
    assert copias[0]["norma"] == "AP-57"
    assert copias[0]["zona"] == "meta_toolkit"
    assert copias[0]["pasarela"] == "tools-catalog.json"


def test_una_ci_que_lista_puertas_a_mano_rompe_la_puerta(monkeypatch, tmp_path):
    """El hallazgo original, reproducido: la regresión que ya ocurrió una vez."""
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        "steps:\n  - run: python scripts/vault_norms.py --check-framework\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(C, "REPO", tmp_path)
    copias = [h for h in C.medir_fronteras()
              if h["criterio"] == "que_puertas_hay_que_pasar"]
    assert copias, "la CI puede volver a listar puertas a mano sin que nadie lo vea"
    assert copias[0]["dueño"] == "vault_gate:PUERTAS"


def test_un_lenguaje_sin_frontera_declarada_sale_como_hallazgo(monkeypatch, tmp_path):
    """El alcance se declara, no se supone.

    Sin esto, añadir un `.sh` con criterios copiados dentro daría verde: no
    porque no haya copia, sino porque nadie mira ahí. Es el cero fabricado que
    AP-58 acababa de destapar en los ciclos, un piso más arriba.
    """
    (tmp_path / "herramientas").mkdir()
    (tmp_path / "herramientas" / "deploy.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(C, "REPO", tmp_path)
    sin_declarar = [h for h in C.medir_fronteras()
                    if h["criterio"] == "frontera_no_declarada"]
    assert [h for h in sin_declarar if h["modulo"].endswith("deploy.sh")]


def test_un_fichero_ajeno_ilegible_no_se_cuenta_como_limpio(monkeypatch, tmp_path):
    """AP-51: el fallo de la tool no se presenta como ausencia en el dato."""
    (tmp_path / "mcp" / "nodejs").mkdir(parents=True)
    (tmp_path / "mcp" / "nodejs" / "roto.mjs").write_bytes(b"\xff\xfe\x00binario")
    monkeypatch.setattr(C, "REPO", tmp_path)
    assert [h for h in C.medir_fronteras() if h["criterio"] == "_no_se_lee"]


def test_las_exclusiones_se_listan_con_motivo():
    """Una exclusión por patrón se traga lo que venga después."""
    assert C.FUERA_DE_FRONTERA
    for ruta, motivo in C.FUERA_DE_FRONTERA.items():
        assert len(motivo) > 20, f"{ruta} excluida sin motivo escrito"


# ── Registro y puerta ────────────────────────────────────────────────────────

def test_la_norma_declara_la_frontera_en_su_prevencion():
    """Regla 3: el concepto vive en el registro, y la doc lo deriva. Si AP-57
    no nombra las fronteras, quien lea la norma seguirá creyendo que solo mide
    Python."""
    from vault_norms import NORM_CATALOG

    n = next(x for x in NORM_CATALOG if x["code"] == "AP-57")
    assert "FRONTERAS" in n["prevention"]
    assert "pasarela" in n["prevention"].lower()
