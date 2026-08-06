"""Caracterización del contexto Durabilidad: argv y envelope, congelados.

Capturado **antes** de mover una sola línea al dominio. No describe lo que las
cuatro tools deberían hacer: describe lo que hacen hoy, incluidos los campos que
uno no elegiría de nuevo. Ése es justo el valor — el criterio de aceptación del
piloto es que los envelopes salgan idénticos después del refactor, y un test
escrito «como debería ser» no detectaría la rotura del contrato publicado.

Si un test de aquí falla tras el refactor, el refactor rompió un contrato y se
revierte. No se ajusta el test. Es el punto de no negociación del plan.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"


@pytest.fixture
def vault(tmp_path):
    destino = tmp_path / "vault"
    shutil.copytree(REPO_ROOT / "vault-sandbox", destino)
    return destino


def _run(vault: Path, script: str, *args: str) -> dict:
    """Ejecuta la tool como la ejecuta un consumidor: por argv, leyendo stdout.

    Por subproceso a propósito. El dominio todavía no está migrado, así que
    importar el módulo contaminaría el proceso con sus rutas congeladas (AP-49)
    — que es exactamente lo que este piloto viene a eliminar.
    """
    env = {**os.environ, "PYTHONIOENCODING": "utf-8",
           "VAULT_ROOT": str(vault), "VAULT_TOOL_TIMEOUT": "600"}
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=600,
    )
    assert proc.stdout.strip(), f"{script} no escribió nada en stdout: {proc.stderr[-400:]}"
    return json.loads(proc.stdout)


def _campos(envelope: dict) -> set[str]:
    """Sin `vault_says`, que es la capa de voz y no el contrato de datos."""
    return {k for k in envelope if k != "vault_says"}


# ── vault_backup ─────────────────────────────────────────────────────────────

CAMPOS_BACKUP = {
    "created", "manifest", "merkle_file_count", "merkle_root", "name", "ok",
    "path", "timestamp", "tool", "unchanged", "updated", "written",
}


def test_backup_devuelve_exactamente_estos_campos(vault):
    env = _run(vault, "vault_backup.py", "--label", "caracterizacion")
    assert _campos(env) == CAMPOS_BACKUP
    assert env["ok"] is True
    assert env["tool"] == "vault_backup"


def test_backup_expone_indicador_de_trabajo(vault):
    """AP-37: `ok: true` a secas no distingue «copié N» de «no copié nada»."""
    env = _run(vault, "vault_backup.py", "--label", "trabajo")
    assert env["merkle_file_count"] > 0
    assert isinstance(env["written"], int)
    assert env["merkle_root"], "el merkle root es lo que hace verificable la copia"


def test_el_backup_no_se_copia_a_si_mismo(vault):
    """`vault-backups/` cuelga del vault; sin exclusión, cada copia doblaría.

    Está bien resuelto y conviene que siga estándolo: el conteo se mantiene
    plano copia tras copia en vez de crecer 196 → 392 → 588.
    """
    conteos = [
        _run(vault, "vault_backup.py", "--label", f"n{i}")["merkle_file_count"]
        for i in range(3)
    ]
    assert len(set(conteos)) == 1, f"el backup se está copiando a sí mismo: {conteos}"


def test_el_merkle_root_del_vault_incluye_la_huella_de_la_propia_tool(vault):
    """Congelado como está: dos copias de un vault intacto NO comparten raíz.

    Correr cualquier tool reescribe `00_System/.tool-trace.json` y
    `00_System/.voice-counter` —observabilidad—, y el Merkle del vault los
    incluye. La medida arrastra la huella de quien mide, así que `merkle_root`
    no puede responder «¿cambió el vault entre estas dos copias?»: siempre dice
    que sí. Es AP-44 aplicado a una métrica de integridad.

    Para lo que la tool usa el Merkle —`--verify`, que recomputa sobre el
    directorio del backup y lo compara con el manifiesto— sigue siendo válido.

    No se corrige en el piloto **a propósito**. Excluir la telemetría cambiaría
    la raíz calculada, y todo backup ya existente pasaría a reportarse CORRUPTO
    al verificarlo contra su manifiesto guardado. Eso es romper un contrato con
    datos en producción, no refactorizar. Necesita migración de manifiestos, que
    es una decisión aparte.
    """
    primera = _run(vault, "vault_backup.py", "--label", "a")
    segunda = _run(vault, "vault_backup.py", "--label", "b")
    assert segunda["merkle_file_count"] == primera["merkle_file_count"]
    assert segunda["merkle_root"] != primera["merkle_root"]


def test_los_contadores_del_ledger_no_cuentan_los_ficheros_copiados(vault):
    """Congelado como está, y lo que hay está torcido.

    `created`/`updated`/`unchanged`/`written` vienen de `vault_io.write_report()`,
    que solo ve lo que pasó por `atomic_write_text`. El backup copia con
    `shutil`, así que un backup de 196 ficheros reporta `written: 1` —el
    manifiesto— y `unchanged: 0` siempre. Como indicador de trabajo (AP-37) es
    engañoso: no distingue copiar el vault entero de no copiar nada.

    El indicador honesto de esta tool es `merkle_file_count`, y por eso el test
    de arriba lo comprueba. Esto se deja anotado y NO se corrige aquí: cambiar
    la semántica de un campo del envelope es romper el contrato publicado, que
    es justo lo que este piloto tiene prohibido hacer.
    """
    env = _run(vault, "vault_backup.py", "--label", "contadores")
    assert env["unchanged"] == 0
    assert env["written"] == env["created"] + env["updated"]
    assert env["written"] < env["merkle_file_count"], (
        "si esto deja de cumplirse, alguien arregló los contadores: revisa el "
        "contrato antes de dar por buena la nueva semántica"
    )


def test_backup_declara_donde_escribio(vault):
    """`path` es relativo A LA RAÍZ DEL VAULT, y el envelope no lo dice.

    Se congela porque es el contrato vigente: un consumidor que haga
    `Path(env["path"])` desde otro CWD no encuentra nada. La contención sí es
    correcta —`vault-backups/` cuelga del vault, no es un hermano—, que es lo
    que AP-36 exige.
    """
    env = _run(vault, "vault_backup.py", "--label", "ruta")
    assert not Path(env["path"]).is_absolute()
    destino = vault / env["path"]
    assert destino.exists(), destino
    assert destino.resolve().is_relative_to(vault.resolve())
    assert isinstance(env["manifest"], dict), "manifest es el contenido, no la ruta"


# ── vault_backup_list ────────────────────────────────────────────────────────

CAMPOS_LIST = {"backups", "message", "ok", "timestamp", "tool", "total"}


def test_list_devuelve_exactamente_estos_campos(vault):
    assert _campos(_run(vault, "vault_backup_list.py")) == CAMPOS_LIST


def test_list_ve_lo_que_backup_acaba_de_escribir(vault):
    """Los dos lados del contexto, contrastados uno contra otro (AP-44).

    Que `vault_backup` diga que escribió no demuestra que `vault_backup_list` lo
    encuentre: son las dos tools que un usuario encadena.
    """
    creado = _run(vault, "vault_backup.py", "--label", "visible")
    listado = _run(vault, "vault_backup_list.py")
    assert listado["total"] >= 1
    assert creado["name"] in [b["name"] for b in listado["backups"]], listado


def test_list_respeta_el_limite(vault):
    """`--limit` estaba publicado y sin implementar (AP-42).

    El catálogo declaraba el parámetro con `min:1`, `max:100` y default 20, y el
    ejemplo documentado decía `--limit 5`. El `argparse` no tenía un solo
    argumento: esa línea del ejemplo moría en `unrecognized arguments`. No lo
    cazó nadie porque `vault_smoke` ejecuta la primera línea del ejemplo.
    """
    for i in range(3):
        _run(vault, "vault_backup.py", "--label", f"n{i}")
    env = _run(vault, "vault_backup_list.py", "--limit", "2")
    assert len(env["backups"]) == 2
    assert env["total"] == 3, (
        "`total` dice cuántos HAY, no cuántos se devuelven: si el límite lo "
        "cambiara, quien pagina no podría saber que falta algo"
    )


def test_el_limite_fuera_de_rango_se_rechaza(vault):
    """Los validadores `min:1`/`max:100` del catálogo, ejecutables."""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "VAULT_ROOT": str(vault)}
    for malo in ("0", "101"):
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "vault_backup_list.py"), "--limit", malo],
            capture_output=True, text=True, encoding="utf-8", env=env, timeout=120,
        )
        assert proc.returncode != 0, malo
        assert "fuera de rango" in proc.stderr, proc.stderr


def test_list_sin_backups_no_miente(vault):
    env = _run(vault, "vault_backup_list.py")
    assert env["ok"] is True
    assert env["total"] == len(env["backups"])


# ── vault_quarantine ─────────────────────────────────────────────────────────

CAMPOS_QUARANTINE_LIST = {"count", "entries", "ok", "restored_total", "timestamp", "tool"}


def test_quarantine_list_devuelve_exactamente_estos_campos(vault):
    assert _campos(_run(vault, "vault_quarantine.py", "--list")) == CAMPOS_QUARANTINE_LIST


def test_quarantine_mueve_la_nota_y_la_registra(vault):
    """El side effect declarado: mover a 20_Quarantine/ y anotar en el ledger."""
    nota = vault / "07_Knowledge" / "sospechosa-caracterizacion.md"
    nota.parent.mkdir(parents=True, exist_ok=True)
    nota.write_text("origen desconocido, con ñ y acentuación\n", encoding="utf-8")

    env = _run(vault, "vault_quarantine.py", "--add", "07_Knowledge/sospechosa-caracterizacion.md",
               "--reason", "Sin frontmatter y origen desconocido", "--agent", "claude")
    assert env["ok"] is True, env
    assert not nota.exists(), "la nota debía moverse, no copiarse"

    listado = _run(vault, "vault_quarantine.py", "--list")
    assert listado["count"] >= 1
    assert any("sospechosa-caracterizacion" in json.dumps(e, ensure_ascii=False)
               for e in listado["entries"]), listado


def test_quarantine_no_saca_nada_del_vault(vault):
    """AP-36 sobre el contexto entero: todo side effect vive DENTRO del vault."""
    nota = vault / "07_Knowledge" / "contenida.md"
    nota.parent.mkdir(parents=True, exist_ok=True)
    nota.write_text("x\n", encoding="utf-8")
    _run(vault, "vault_quarantine.py", "--add", "07_Knowledge/contenida.md",
         "--reason", "prueba de contención", "--agent", "test")

    cuarentena = vault / "20_Quarantine"
    assert cuarentena.exists()
    for p in cuarentena.rglob("*"):
        assert p.resolve().is_relative_to(vault.resolve()), p


def test_el_ledger_de_cuarentena_es_append_only(vault):
    """Lo declara el catálogo como side effect; aquí se comprueba que es cierto."""
    for i in range(2):
        nota = vault / "07_Knowledge" / f"append-{i}.md"
        nota.parent.mkdir(parents=True, exist_ok=True)
        nota.write_text("x\n", encoding="utf-8")
        _run(vault, "vault_quarantine.py", "--add", f"07_Knowledge/append-{i}.md",
             "--reason", "append-only", "--agent", "test")
    env = _run(vault, "vault_quarantine.py", "--list")
    assert env["count"] >= 2, "la segunda entrada pisó a la primera"


# ── El contexto, contra su contrato publicado ────────────────────────────────

def test_los_cuatro_envelopes_cubren_su_contrato():
    """El criterio del consumidor, no el propio (AP-44).

    Se lee del tool-spec, que es lo que un agente recibe, en vez de comprobar
    contra la lista de campos escrita arriba — dos fuentes para lo mismo serían
    AP-05, y la de arriba solo existe para congelar la FORMA.
    """
    spec = json.loads(
        (REPO_ROOT / "vault-sandbox" / "00_System" / "tool-spec.json")
        .read_text(encoding="utf-8")
    )["tools"]
    for tool in ("vault_backup", "vault_backup_list", "vault_restore", "vault_quarantine"):
        assert tool in spec, tool
        assert spec[tool]["declared_returns"], f"{tool} sin contrato declarado"
        assert spec[tool].get("status", "active") == "active", tool
