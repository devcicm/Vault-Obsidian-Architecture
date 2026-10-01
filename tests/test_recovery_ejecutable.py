"""AP-52 — la recuperación que publica el catálogo de errores se puede ejecutar.

El envelope de error existe para que el agente sepa qué hacer después, y
`recovery` es la parte que obedece sin leer el resto. Medido en v40.34, cuatro
entradas de `ERROR_CATALOG` mandaban a algo que no existe:

- `BACKUP_NOT_FOUND` → `vault_backup --list`: el flag no existe; lista
  `vault_backup_list`.
- `FRONTMATTER_MISSING` → `vault_write --path`: `vault_write` no tiene
  `--path`.
- `AP18_HASH_DUPLICATE` → `vault_audit --hash`: tampoco existe; el audit por
  defecto ya detecta AP-18.
- `SPEC_LOAD_ERROR` → regenerar con `vault_compact_contracts`, que lee
  `tool-spec.json` y no lo escribe; lo escribe `vault_manifest --bootstrap`.

Las tres primeras acaban en un error de argparse justo después de un error;
la cuarta, en el mismo error otra vez. Este test mide las tres primeras clases
con el criterio del consumidor (argparse del script nombrado); la cuarta es de
significado y queda fijada por su caso.
"""

import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SCRIPTS = RAIZ / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(RAIZ))

from vault.kernel.errores import ERROR_CATALOG  # noqa: E402
from vault_mcp_catalog import argparse_params  # noqa: E402

#: `vault_x`, opcionalmente `.py`, seguido de sus flags. Lo que va pegado a otra
#: palabra (`_detect_vault_root()`) o es una llamada no es el nombre de una tool.
CITA = re.compile(r"(?<![\w.])(vault_[a-z0-9_]+)(?:\.py)?(?!\w|\()((?:\s+--[a-z][\w-]*)*)")


def _subcomandos(script: Path) -> set:
    return set(re.findall(r'add_parser\(\s*"([^"]+)"', script.read_text(encoding="utf-8")))


def _invalidos(tool: str, args) -> list:
    script = SCRIPTS / f"{tool}.py"
    if not script.is_file():
        return [f"{tool}: no hay scripts/{tool}.py"]
    flags, subs = argparse_params(script.name), _subcomandos(script)
    malos = []
    for a in args:
        if not isinstance(a, str) or a.startswith("<"):
            continue  # marcador del valor que pone quien obedece
        if a.startswith("--"):
            if a[2:].split("=")[0] not in flags:
                malos.append(f"{tool} {a}")
        elif a not in subs:
            malos.append(f"{tool} {a} (ni flag ni subcomando)")
    return malos


def test_ap52_recovery_tool_y_args_existen():
    rotos = {}
    for codigo, entrada in ERROR_CATALOG.items():
        r = entrada["recovery"]
        tool = r.get("tool")
        if not tool or tool.startswith("<"):
            continue  # `<la misma tool>`: la resuelve quien emite
        malos = _invalidos(tool, r.get("args") or [])
        if malos:
            rotos[codigo] = malos
    assert rotos == {}


def test_ap52_la_tool_que_cita_una_pista_existe_con_esos_flags():
    rotos = {}
    for codigo, entrada in ERROR_CATALOG.items():
        for m in CITA.finditer(entrada["recovery"].get("hint") or ""):
            malos = _invalidos(m.group(1), m.group(2).split())
            if malos:
                rotos.setdefault(codigo, []).extend(malos)
    assert rotos == {}


@pytest.mark.parametrize("pista,rota", [
    ("Ejecutar vault_audit --hash para ver duplicados.", True),
    ("Listar con vault_backup_list --limit 5.", False),
    ("Verificar que _detect_vault_root() lo detecte.", False),
    ("Correr python scripts/vault_kernel.py --check.", False),
])
def test_el_detector_distingue_una_cita_rota(pista, rota):
    hallado = [x for m in CITA.finditer(pista) for x in _invalidos(m.group(1), m.group(2).split())]
    assert bool(hallado) is rota, hallado


def test_spec_load_error_manda_a_quien_escribe_el_contrato():
    pista = ERROR_CATALOG["SPEC_LOAD_ERROR"]["recovery"]["hint"]
    assert "vault_manifest.py --bootstrap" in pista
    assert "bootstrap" in argparse_params("vault_manifest.py")
