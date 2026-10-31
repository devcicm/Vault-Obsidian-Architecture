"""A-20 — el número de cada `### Grupo N` del manifiesto es el `group_id` del registro.

Medido el 2026-10-30 sobre el HEAD: a partir del 28 la numeración del manifiesto
iba desplazada una posición respecto del catálogo («Grupo 28» era Normas, id 35;
29 era Producción/SRE, id 28; 30 era Release, id 29; 31 era Riesgos/Calidad,
id 30) y Bootstrap (id 31) no tenía encabezado. Que hubiese 37 encabezados lo
escondía: el número sobrante de Normas tapaba el hueco de Bootstrap.

El criterio sale del registro (`vault_servicio.trazabilidad`), no de una lista
aquí: un bloque es del grupo N si las tools del grupo N son las que más cita.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

import vault_servicio  # noqa: E402

MANIFIESTO = (ROOT / "vault-obsidian-architecture.md").read_text(encoding="utf-8")


def _grupo_de_cada_tool():
    t = vault_servicio.trazabilidad()
    filas = t["trace"] if isinstance(t, dict) else t
    return {f["tool"]: f["group_id"] for f in filas}


def _bloques():
    """`[(N, título, cuerpo)]` de cada `### Grupo N`, hasta el siguiente `###` o `##`."""
    return [
        (int(m.group(1)), m.group(2).strip(), m.group(3))
        for m in re.finditer(
            r"^### Grupo (\d+) — (.+?)$(.*?)(?=^#{2,3} |\Z)", MANIFIESTO, re.S | re.M
        )
    ]


def test_los_encabezados_van_en_orden_y_sin_repetir():
    numeros = [n for n, _, _ in _bloques()]
    assert numeros == sorted(set(numeros)), f"numeración desordenada o repetida: {numeros}"


def test_todo_group_id_tiene_un_encabezado_con_su_numero():
    ids = set(_grupo_de_cada_tool().values())
    numeros = {n for n, _, _ in _bloques()}
    assert ids == numeros, (
        f"ids sin encabezado: {sorted(ids - numeros)}; "
        f"encabezados sin id: {sorted(numeros - ids)}"
    )


def test_cada_bloque_cita_sobre_todo_las_tools_de_su_numero():
    grupo_de = _grupo_de_cada_tool()
    desfasados = []
    for n, titulo, cuerpo in _bloques():
        citas = {}
        for tool in re.findall(r"\bvault_[a-z0-9_]+\b", cuerpo):
            if tool in grupo_de:
                citas[grupo_de[tool]] = citas.get(grupo_de[tool], 0) + 1
        propio = citas.get(n, 0)
        if propio == 0 or any(v > propio for k, v in citas.items() if k != n):
            desfasados.append((n, titulo, citas))
    assert not desfasados, f"bloques cuyo número no es el de las tools que cita: {desfasados}"


def test_bootstrap_nombra_sus_tools():
    grupo_de = _grupo_de_cada_tool()
    cuerpo = next((c for n, _, c in _bloques() if n == 31), "")
    sin = [t for t, g in grupo_de.items() if g == 31 and t not in cuerpo]
    assert cuerpo and not sin, f"Grupo 31 no nombra: {sin}"
