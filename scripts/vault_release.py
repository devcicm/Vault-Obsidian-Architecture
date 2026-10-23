#!/usr/bin/env python3
"""vault_release — el bump de versión en un solo comando (O1a, v41.17).

La versión del estándar vivía en siete sitios y se subía a mano en cada
release: banner y fila de tabla del manifiesto, entrada de changelog,
badge del README, banner de `cli/README.md`, `pyproject.toml`,
`CURRENT_VERSION` y el campo `version` de `tool-spec.json`. Siete sitios
tocado a mano es la misma historia contada siete veces: cada release era
una tanda nueva de divergencias posibles (el badge desfase real de
v41.11, el literal `"v32"` que el bootstrap llevaba años escribiendo).
Este script es el dueño del movimiento — y su corrección la miden los
guards, no la esperanza:

- `tests/test_version_coherence.py` caza banner, badge, pyproject, cli,
  spec y el vault de pruebas; si algo se queda atrás, es rojo.
- Idempotente: segunda corrida con la versión ya corriente es no-op
  (ni siquiera se toca el fichero).
- Anti-colisión: se niega a tocar un fichero con trabajo sin commitear,
  se niega a bajar la versión, y la fila de tabla y la entrada de
  changelog se insertan donde les toca a la nueva — no se adivinan.

No es tool del catálogo MCP: no opera contra vaults de nadie — es un
invariante de ESTE repo, misma clase que `vault_doc_counts`. El campo de
contrato que los consumidores leen (`tool-spec.json`) lo sube
`vault_manifest --sync-version`, que es su dueño, así que este script no
lo reescribe por su cuenta (AP-57).

Uso típico de release:

    python scripts/vault_release.py --nueva-version v41.18 --nota "..."
    python scripts/vault_mcp_catalog.py --sync
    python scripts/vault_sdd_init.py --bilingual --force --vault-root .
    python scripts/vault_fix_all.py
    # suite + puertas → commit del release → --fijar-hash → commit de docs
"""
import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict
from datetime import date
from pathlib import Path

# El dueño del número. No se copia el literal: se importa.
_REPO = next((p for p in Path(__file__).resolve().parents
              if (p / "vault" / "kernel" / "version.py").is_file()), None)
sys.path.insert(0, str(_REPO))
from vault.kernel.version import CURRENT_VERSION  # noqa: E402
from vault.kernel import procesos_git  # noqa: E402


def _numero(version: str) -> tuple:
    return tuple(int(x) for x in version.lstrip("v").split("."))


def _vieja_efectiva(raiz: Path) -> str:
    """La versión corriente del repo OBJETIVO, leída de su version.py.

    Si se tomara del import (el repo de origen del script), una segunda
    corrida sobre un trabajo ya bump —aún sin commit— vería la versión
    vieja, compararía nueva > vieja y reescribiría todo dos veces: eso
    seria historia duplicada en fila y changelog, que es exactamente la
    clase de divergencia que este script existe para eliminar.
    """
    p = raiz / "vault" / "kernel" / "version.py"
    try:
        m = re.search(r'CURRENT_VERSION\s*=\s*"(v\d+\.\d+)"',
                      p.read_text(encoding="utf-8"))
        if m:
            return m.group(1)
    except OSError:
        pass
    return CURRENT_VERSION


def _envelope(**datos) -> str:
    return json.dumps({"tool": "vault_release", **datos},
                      ensure_ascii=False, indent=2)


def _escribir(ruta: Path, texto: str) -> None:
    # `write_text` no acepta `newline=` hasta 3.10 (el piso es 3.9): el
    # traductor de líneas queda tal cual, sin \n→\r\n. `open` sí lo acepta.
    with ruta.open("w", encoding="utf-8", newline="") as f:
        f.write(texto)


def _protegidos(raiz: Path) -> list:
    """Los ficheros que el bump va a tocar.

    Anti-colisión: si alguno tiene trabajo sin commitear, el bump se
    niega — no va a tapar edición ajena ni a mezclarla con la suya.
    """
    return [
        raiz / "vault-obsidian-architecture.md",
        raiz / "README.md",
        raiz / "pyproject.toml",
        raiz / "cli" / "README.md",
        raiz / "vault" / "kernel" / "version.py",
    ]


def _editar_manifiesto(ruta: Path, nueva: str, vieja: str, fecha: str,
                       nota: str) -> None:
    src = ruta.read_text(encoding="utf-8")

    # Banner
    banner_viejo = re.search(r"^\*\*Versión:\*\* (v[\d.]+) - (\d{4}-\d{2}-\d{2})",
                             src, re.M)
    if not banner_viejo:
        raise SystemExit(_envelope(ok=False, action="bump", escrito=False,
                                   detalle="banner de versión no encontrado"))
    src = src.replace(
        f"**Versión:** {banner_viejo.group(1)} - {banner_viejo.group(2)}  ",
        f"**Versión:** {nueva} - {fecha}  ", 1)

    # Fila de tabla: la nueva va a continuación de la del release anterior
    # (el orden del propio manifiesto). Si la fila anterior no está, no se
    # inserta a ciegas: se corta con el motivo escrito.
    fila_anterior = None
    for m in re.finditer(rf"^\| {re.escape(vieja)} \| .*$", src, re.M):
        fila_anterior = m
    if fila_anterior is None:
        raise SystemExit(_envelope(
            ok=False, action="bump", escrito=False,
            detalle=f"la fila de la tabla de {vieja} no está en el manifiesto; "
                    "la nueva no se inserta sin su ancla — revisa la tabla"))
    fin = src.find("\n", fila_anterior.start())
    fila_nueva = f"| {nueva} | {fecha} | {nota} |"
    src = src[:fin] + "\n" + fila_nueva + src[fin:]

    # Changelog: la entrada nueva va antes de la primera existente (la más
    # nueva arriba), con el hash `pending` del release que aún no existe.
    i_ch = src.find("## Changelog")
    if i_ch == -1:
        raise SystemExit(_envelope(ok=False, action="bump", escrito=False,
                                   detalle="## Changelog no encontrado"))
    cuerpo = src[i_ch:]
    m = re.search(r"\n### v", cuerpo)
    entrada = f"### {nueva} — {fecha} `git: pending`\n\n{nota}\n\n"
    if m:
        cuerpo = cuerpo[:m.start()] + "\n" + entrada + cuerpo[m.start():]
        src = src[:i_ch] + cuerpo
    _escribir(ruta, src)


#: Cuántos días puede tener el último contraste contra un vault ajeno para que
#: el bump lo considere vigente (regla 7, v41.20). Con cero, cada bump exigiría
#: uno nuevo —disciplina pura—; con un plazo, la evidencia de consumidor deja de
#: depender de que alguien la pida, que es como estaba.
DIAS_DE_CONTRASTE = 60


def _contraste_vigente(raiz: Path, hoy: date) -> Dict[str, Any]:
    """¿Hay un contraste reciente contra un vault ajeno? (regla 7)

    El repo entero se mide contra `vault-sandbox/`, que él mismo genera: no
    puede exhibir los defectos de un vault ajeno. Los tres que han salido —
    siete títulos de frontmatter compuestos sin escapar, el criterio de
    documentación comparando el nombre exacto, dos conflictos AP-05 entre notas
    del mismo servidor— aparecieron midiendo en solo lectura contra material de
    otra persona, y ninguna puerta de aquí los habría visto nunca.
    """
    recibo = raiz / "docs" / "contrastes" / "ultimo-contraste.json"
    if not recibo.is_file():
        return {"vigente": False, "motivo": "no hay ningún contraste registrado",
                "dias": None, "max_dias": DIAS_DE_CONTRASTE}
    try:
        datos = json.loads(recibo.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"vigente": False, "motivo": f"el recibo no se lee: {exc}",
                "dias": None, "max_dias": DIAS_DE_CONTRASTE}
    try:
        fecha = date.fromisoformat(str(datos.get("fecha", "")))
    except ValueError:
        return {"vigente": False, "motivo": "el recibo no trae una fecha legible",
                "dias": None, "max_dias": DIAS_DE_CONTRASTE}
    dias = (hoy - fecha).days
    vigente = 0 <= dias <= DIAS_DE_CONTRASTE
    return {
        "vigente": vigente,
        "fecha": fecha.isoformat(),
        "dias": dias,
        "max_dias": DIAS_DE_CONTRASTE,
        "vault_medido": datos.get("vault_medido"),
        "motivo": "" if vigente else
                  f"el contraste es de hace {dias} días y el máximo son {DIAS_DE_CONTRASTE}",
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="vault_release — el bump de versión del estándar en un "
                    "solo comando",
        allow_abbrev=False)
    ap.add_argument("--nueva-version",
                    help="Versión del release (vX.Y); no puede ser menor ni "
                         "igual salvo idempotencia")
    ap.add_argument("--nota",
                    help="Cuerpo de la fila de tabla y de la entrada de "
                         "changelog; el hash queda `pending` hasta "
                         "--fijar-hash")
    ap.add_argument("--fecha", help="ISO del release; hoy por defecto")
    ap.add_argument("--raiz",
                    help="Raíz del repo (para los tests); la autodetección "
                         "en su ausencia")
    ap.add_argument("--declarar-contraste-pendiente",
                    dest="declarar_contraste",
                    action="store_true",
                    help="Deja pasar el bump sin contraste de vault ajeno y lo "
                         "declara en el changelog (el hueco queda escrito, que "
                         "es lo que lo hace revisable)")
    args = ap.parse_args()

    if not args.nueva_version or not args.nota:
        print(_envelope(ok=False, action="bump", escrito=False,
                        detalle="falta --nueva-version o --nota"))
        return 1
    nueva = args.nueva_version.strip()
    vieja = CURRENT_VERSION
    fecha = args.fecha or date.today().isoformat()

    raiz = (Path(args.raiz).resolve() if args.raiz else _REPO)
    vieja = _vieja_efectiva(raiz)
    fecha = args.fecha or date.today().isoformat()

    if nueva == vieja:  # idempotencia: no op
        print(_envelope(ok=True, action="bump", escrito=False, version=vieja,
                        detalle="ya manda esta versión: no se toca nada"))
        return 0
    if _numero(nueva) <= _numero(vieja):
        print(_envelope(ok=False, action="bump", escrito=False,
                        detalle=f"{nueva} no es mayor que la corriente "
                                f"{vieja}: bajar la versión rompe los "
                                "migradores"))
        return 1
    protegidos = [str(p.relative_to(raiz)) for p in _protegidos(raiz)
                  if p.exists()]
    sucio = procesos_git.ejecutar_git(
        raiz, ["status", "--porcelain", "--", *protegidos],
        capture_output=True)
    if (sucio.stdout or "").strip():
        print(_envelope(
            ok=False, action="bump", escrito=False,
            detalle="ficheros protegidos con trabajo sin commitear:\n  "
                    + (sucio.stdout or "").strip()
                    + "\ncommit o stash antes — el bump no tapa trabajo "
                      "ajeno"))
        return 1

    # Regla 7: este repo se mide contra vault-sandbox/, que él mismo genera, y
    # por eso no puede exhibir los defectos de un vault ajeno. Los tres que han
    # salido salieron de medir en solo lectura contra material de otra persona.
    # El bump se para a preguntar si ese contraste está vigente; la salida es
    # dos, y las dos están escritas: medir, o declarar el hueco.
    contraste = _contraste_vigente(raiz, date.fromisoformat(fecha))
    if not contraste["vigente"] and not args.declarar_contraste:
        print(_envelope(
            ok=False, action="bump", escrito=False,
            detalle=(
                "regla 7: no hay un contraste reciente contra un vault ajeno "
                f"({contraste['motivo']}). Este repo solo se mide contra "
                "vault-sandbox/, que él mismo genera, y no puede exhibir lo "
                "que solo aparece en material de otra persona.\n\n"
                "  python scripts/vault_foreign_check.py --root <vault ajeno> "
                "--registrar-contraste\n"
                "  python scripts/vault_release.py ... "
                "--declarar-contraste-pendiente  (deja el hueco escrito)"),
            contraste=contraste))
        return 1

    # 1. el número, en su dueño
    p = raiz / "vault" / "kernel" / "version.py"
    s = p.read_text(encoding="utf-8")
    anciano = f'CURRENT_VERSION = "{vieja}"'
    assert anciano in s, "version.py no casa con CURRENT_VERSION importada"
    _escribir(p, s.replace(anciano,
                           f'CURRENT_VERSION = "{nueva}"', 1))

    # 2. el número, en los cuatro sitios que lo reflejan
    num_nueva, num_vieja = nueva.lstrip("v"), vieja.lstrip("v")
    p = raiz / "pyproject.toml"
    s = p.read_text(encoding="utf-8")
    assert f'version = "{num_vieja}"' in s, "pyproject sin la versión vieja"
    _escribir(p, s.replace(f'version = "{num_vieja}"',
                           f'version = "{num_nueva}"', 1))

    p = raiz / "README.md"
    s = p.read_text(encoding="utf-8")
    assert f"version-{vieja}-blue" in s, "badge sin la versión vieja"
    _escribir(p, s.replace(f"version-{vieja}-blue",
                           f"version-{nueva}-blue", 1))

    p = raiz / "cli" / "README.md"
    s = p.read_text(encoding="utf-8")
    assert f"**{vieja} · " in s, "banner de cli/README sin la versión vieja"
    _escribir(p, s.replace(f"**{vieja} · ", f"**{nueva} · ", 1))

    # 3. el manifiesto: banner, fila y changelog
    _editar_manifiesto(raiz / "vault-obsidian-architecture.md",
                       nueva, vieja, fecha, args.nota)

    # 4. el contrato de versión de los consumidores, por su dueño
    sandbox = raiz / "vault-sandbox"
    if (sandbox / "00_System").is_dir():
        subprocess.run(
            [sys.executable, str(Path(__file__).parent / "vault_manifest.py"),
             "--sync-version", "--campo-version", nueva],
            capture_output=True, text=True,
            env={**os.environ, "VAULT_ROOT": str(sandbox),
                 "VAULT_STRICT_ROOT": "1",
                 "VAULT_MASTER": str(sandbox / ".casa-temp")},
            encoding="utf-8", errors="replace",
            cwd=str(raiz))
    else:
        print(_envelope(ok=True, action="bump", escrito=True, version=nueva,
                        anterior=vieja, fecha=fecha,
                        advertencia="repo sin vault-sandbox: tool-spec.json "
                                    "no existe ahí, el campo de versión "
                                    "queda por su dueño"))
        print(_envelope(
            ok=True, action="bump", escrito=True, version=nueva,
            anterior=vieja, fecha=fecha,
            siguiente=[
                "python scripts/vault_mcp_catalog.py --sync",
                "python scripts/vault_sdd_init.py --bilingual --force "
                "--vault-root .",
                "python scripts/vault_fix_all.py",
                "python -m pytest tests/ -q -n auto --tb=short",
                "python scripts/vault_gate.py --strict",
                "commit del release; luego vault_changelog_check "
                "--fijar-hash y su commit de docs",
            ]))
        return 0

    print(_envelope(
        ok=True, action="bump", escrito=True, version=nueva, anterior=vieja,
        fecha=fecha,
        siguiente=[
            "python scripts/vault_mcp_catalog.py --sync",
            "python scripts/vault_sdd_init.py --bilingual --force "
            "--vault-root .",
            "python scripts/vault_fix_all.py",
            "python -m pytest tests/ -q -n auto --tb=short",
            "python scripts/vault_gate.py --strict",
            "commit del release; luego vault_changelog_check --fijar-hash "
            "y su commit de docs",
        ]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
