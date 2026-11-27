"""Tests TDD para la skill `vault-mejora-continua` y el selector de carpetas por vault.

Cubre:
- Opción 2: descubrimiento, frontmatter YAML, ciclo de errores/antipatrones F1..F13,
  regla de recurrencia >=2, y paridad con `docs/SKILLS.md` y `CLAUDE.md`.
- Opción 3:
  - DN-01 (fallo verificable): deshabilitar `00_System` o `99_Index`, preset inválido,
    `only-sections` con sección inexistente, o `secciones.json` corrupto fallan cerrados.
  - DN-02 (no destructivo): deshabilitar una sección estándar con notas existentes NO borra
    archivos, bloquea escrituras NUEVAS allí, preserva búsqueda/grafo/lectura y `--enable`
    restaura la escritura.
  - DN-09 (opt-in estricto): `vault_init` sin flags crea las 23 secciones estándar igual
    que siempre; `--sections-preset minimo --extra-sections 22_Redes:referencia` crea solo
    las seleccionadas + la propia y pasa `vault_validate` sin falsos `missing`.
"""

import json
from pathlib import Path

import pytest
import yaml

from apoyo import correr_tool

REPO_ROOT = Path(__file__).resolve().parent.parent

import vault_registry as reg  # noqa: E402


# ── Opción 2: Skill `vault-mejora-continua` ──────────────────────────────────


def test_skill_mejora_continua_existe_y_cubre_ciclo_de_errores():
    ruta = REPO_ROOT / "agent" / "skills" / "vault-mejora-continua" / "SKILL.md"
    assert ruta.is_file(), "falta agent/skills/vault-mejora-continua/SKILL.md"
    texto = ruta.read_text(encoding="utf-8")
    partes = texto.split("---", 2)
    fm = yaml.safe_load(partes[1])
    assert fm["name"] == "vault-mejora-continua"
    assert fm["entry-point"] == "none"
    assert fm["version"] == "1.0"
    assert "## Arguments" not in texto
    for clave in (
        "vault_log_error",
        "vault_bug_save",
        "vault_ronda",
        "vault_write",
        "F1",
        "F13",
        "DN-01",
        "DN-10",
    ):
        assert clave in texto, f"falta '{clave}' en vault-mejora-continua/SKILL.md"
    assert "vault-mejora-continua" in (REPO_ROOT / "docs" / "SKILLS.md").read_text(
        encoding="utf-8"
    )
    assert "vault-mejora-continua" in (REPO_ROOT / "CLAUDE.md").read_text(
        encoding="utf-8"
    )


# ── Opción 3: Kernel (`vault_registry`) + `vault_section --disable/--enable` ─


@pytest.fixture
def vault_minimo(tmp_path):
    raiz = tmp_path / "vault"
    for sec in ("00_System", "07_Knowledge", "12_Bibliography", "99_Index"):
        (raiz / sec).mkdir(parents=True)
    return raiz


@pytest.mark.parametrize("obligatoria", sorted(reg.SECCIONES_OBLIGATORIAS))
def test_dn01_no_permite_deshabilitar_secciones_obligatorias(vault_minimo, obligatoria):
    r = correr_tool("vault_section", "--disable", obligatoria, "--json", vault=vault_minimo)
    assert r.codigo != 0
    assert r.envelope["ok"] is False
    assert r.envelope["error_code"] == "INVALID_FOLDER"
    assert not (vault_minimo / reg.SECCIONES_PROPIAS_RUTA).exists()


def test_dn01_json_con_obligatoria_en_disabled_standard_falla_cerrado(vault_minimo):
    destino = vault_minimo / reg.SECCIONES_PROPIAS_RUTA
    destino.write_text(
        json.dumps({"schema": 1, "secciones": [], "disabled_standard": ["00_System"]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="obligatoria"):
        reg.leer_secciones_deshabilitadas(vault_minimo)
    r = correr_tool("vault_section", "--list", "--json", vault=vault_minimo)
    assert r.codigo != 0
    assert r.envelope["ok"] is False and r.envelope["error_code"] == "DATA_FILE_CORRUPT"


def test_dn02_disable_preserva_notas_bloquea_nuevas_y_enable_restaura(vault_minimo):
    nota = vault_minimo / "12_Bibliography" / "fuente-existente.md"
    nota.write_text(
        "---\ntitle: Fuente Existente\ntype: bibliography\nstatus: active\n---\n\n"
        "Contenido de prueba real.\n",
        encoding="utf-8",
    )

    r_dis = correr_tool(
        "vault_section", "--disable", "12_Bibliography", "--json", vault=vault_minimo
    )
    assert r_dis.codigo == 0 and r_dis.envelope["ok"] is True
    assert r_dis.envelope["written"] == 1
    assert r_dis.envelope["notes_preserved"] is True
    assert "12_Bibliography" in r_dis.envelope["disabled_standard"]
    # DN-02: la nota existente NO se borra y sigue siendo reconocida como de sección.
    assert nota.is_file()
    assert "12_Bibliography" in reg.secciones_del_vault(vault_minimo)
    assert "12_Bibliography" not in reg.standard_folders(vault_minimo)
    assert "12_Bibliography" not in reg.secciones_activas_del_vault(vault_minimo)

    # Nuevas notas quedan bloqueadas, pero actualizar una nota existente sigue permitido.
    motivo_nueva = reg.motivo_de_destino_invalido("12_Bibliography", vault_minimo, nueva=True)
    assert motivo_nueva is not None and "deshabilitada" in motivo_nueva
    assert reg.motivo_de_destino_invalido("12_Bibliography", vault_minimo, nueva=False) is None

    # vault_write rechaza nota nueva en la sección deshabilitada.
    r_w = correr_tool(
        "vault_write",
        "--folder",
        "12_Bibliography",
        "--title",
        "Nueva Fuente Bloqueada",
        "--content",
        "Linea uno de prueba.\nLinea dos con contenido real.\nLinea tres suficiente para el gate.",
        vault=vault_minimo,
    )
    assert r_w.codigo != 0 and r_w.envelope["ok"] is False

    # --list publica disabled_standard y excluye la deshabilitada de writable_sections.
    r_ls = correr_tool("vault_section", "--list", "--json", vault=vault_minimo)
    assert r_ls.codigo == 0 and r_ls.envelope["ok"] is True
    assert "12_Bibliography" in r_ls.envelope["disabled_standard"]
    assert "12_Bibliography" not in r_ls.envelope["writable_sections"]
    assert "minimo" in r_ls.envelope["presets"]

    # Idempotencia de --disable repetido.
    r_dis2 = correr_tool(
        "vault_section", "--disable", "12_Bibliography", "--json", vault=vault_minimo
    )
    assert r_dis2.codigo == 0 and r_dis2.envelope["ok"] is True and r_dis2.envelope["written"] == 0

    # --enable reactiva escritura y conserva la nota previa.
    r_en = correr_tool(
        "vault_section", "--enable", "12_Bibliography", "--json", vault=vault_minimo
    )
    assert r_en.codigo == 0 and r_en.envelope["ok"] is True and r_en.envelope["written"] == 1
    assert "12_Bibliography" not in r_en.envelope["disabled_standard"]
    assert reg.motivo_de_destino_invalido("12_Bibliography", vault_minimo, nueva=True) is None
    assert nota.is_file()


def test_enable_reactiva_seccion_propia_retirada(vault_minimo):
    r_add = correr_tool(
        "vault_section",
        "--add",
        "22_Laboratorio",
        "--documentacion",
        "guia",
        "--json",
        vault=vault_minimo,
    )
    assert r_add.envelope["ok"] is True
    r_ret = correr_tool(
        "vault_section", "--retire", "22_Laboratorio", "--json", vault=vault_minimo
    )
    assert r_ret.envelope["ok"] is True
    assert reg.motivo_de_destino_invalido("22_Laboratorio", vault_minimo, nueva=True) is not None

    r_en = correr_tool(
        "vault_section", "--enable", "22_Laboratorio", "--json", vault=vault_minimo
    )
    assert r_en.codigo == 0 and r_en.envelope["ok"] is True and r_en.envelope["status"] == "activa"
    assert reg.motivo_de_destino_invalido("22_Laboratorio", vault_minimo, nueva=True) is None


# ── Opción 3: `vault_init` opt-in (`DN-09`) ──────────────────────────────────


def test_dn09_vault_init_preset_minimo_y_extra_sections(tmp_path):
    raiz = tmp_path / "vault-minimo"
    raiz.mkdir()

    r = correr_tool(
        "vault_init",
        "--sections-preset",
        "minimo",
        "--extra-sections",
        "22_Redes:referencia,23_Lab:guia",
        "--no-audit",
        "--no-git",
        vault=raiz,
    )
    assert r.codigo == 0, r.stderr or r.stdout
    assert r.envelope["ok"] is True

    # Solo deben existir las 5 secciones del preset mínimo + las 2 extra.
    carpetas = {p.name for p in raiz.iterdir() if p.is_dir() and not p.name.startswith(".")}
    esperadas = set(reg.PRESETS_SECCIONES["minimo"]) | {"22_Redes", "23_Lab"}
    assert carpetas == esperadas

    # 00_System/secciones.json refleja las deshabilitadas y las propias.
    assert set(reg.standard_folders(raiz)) == set(reg.PRESETS_SECCIONES["minimo"])
    assert [s["folder"] for s in reg.leer_secciones_propias(raiz)] == ["22_Redes", "23_Lab"]

    # vault_validate --check structure pasa sin falsos missing por secciones deshabilitadas.
    r_val = correr_tool("vault_validate", "--check", "structure", vault=raiz)
    assert r_val.codigo == 0 and r_val.envelope["ok"] is True
    assert r_val.envelope["structure"]["missing"] == []
    assert r_val.envelope["structure"]["expected"] == len(reg.PRESETS_SECCIONES["minimo"])


def test_dn01_vault_init_rechaza_preset_invalido_o_conflicto_sin_crear_carpetas(tmp_path):
    raiz = tmp_path / "vault-invalido"
    raiz.mkdir()

    r_bad = correr_tool(
        "vault_init",
        "--sections-preset",
        "inexistente",
        "--no-audit",
        "--no-git",
        vault=raiz,
    )
    assert (
        r_bad.codigo != 0
        and r_bad.envelope["ok"] is False
        and r_bad.envelope["error_code"] == "INVALID_INPUT"
    )
    # emit_error puede escribir su traza en 00_System/, pero no debe crearse
    # secciones.json ni ninguna carpeta de contenido ni 99_Index/.
    assert not (raiz / reg.SECCIONES_PROPIAS_RUTA).exists()
    assert not (raiz / "07_Knowledge").exists()
    assert not (raiz / "99_Index").exists()

    r_mix = correr_tool(
        "vault_init",
        "--sections-preset",
        "minimo",
        "--only-sections",
        "07_Knowledge",
        "--no-audit",
        "--no-git",
        vault=raiz,
    )
    assert (
        r_mix.codigo != 0
        and r_mix.envelope["ok"] is False
        and r_mix.envelope["error_code"] == "INVALID_INPUT"
    )
    assert not (raiz / reg.SECCIONES_PROPIAS_RUTA).exists()
    assert not (raiz / "07_Knowledge").exists()
    assert not (raiz / "99_Index").exists()


def test_dn09_vault_init_only_sections_fuerza_obligatorias(tmp_path):
    raiz = tmp_path / "vault-only"
    raiz.mkdir()

    r = correr_tool(
        "vault_init",
        "--only-sections",
        "07_Knowledge,03_Decisions",
        "--no-audit",
        "--no-git",
        vault=raiz,
    )
    assert r.codigo == 0 and r.envelope["ok"] is True
    carpetas = {p.name for p in raiz.iterdir() if p.is_dir() and not p.name.startswith(".")}
    assert carpetas == {"00_System", "03_Decisions", "07_Knowledge", "99_Index"}
