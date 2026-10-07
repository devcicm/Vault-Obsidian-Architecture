"""AP-56 — ninguna línea de frontmatter interpola un valor crudo.

Medido en v40.34: `vault_log_error --project $'demo\\nstatus: active'` escribía
`project: demo` seguido de un `status: active` que nadie había pedido. El
bloque seguía parseando —la inyección no rompe el YAML, le añade claves— así
que el guard de `atomic_write_text`, que solo mira que parsee, no lo veía, y
la tool devolvía `ok: true`. Había 60 sitios `f"clave: {valor}"` en catorce
tools; se saldaron todos al nacer este guard, por eso no lleva baseline.
"""

import ast
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

from vault.kernel.frontmatter_parsing import valor_de_frontmatter  # noqa: E402

_CLAVE = re.compile(r"^[a-z][A-Za-z_]*: $")
#: Lo que ya es un escalar seguro: el escapador canónico, JSON (YAML de flujo
#: válido) o un identificador que el propio código genera.
_SEGURAS = {"valor_de_frontmatter", "yaml_scalar", "dumps", "uuid4", "utcnow"}


#: Sitio → por qué su valor no puede traer una clave. Sin número de línea, para
#: que mover el sitio no lo estrene como deuda (la lección de v40.6).
_VOCABULARIO_CERRADO = {
    "scripts/vault_norms_catalog.py: status: {canonico}": (
        "`canonico` sale de split_domain_status y la función lanza si no está en "
        "STATUS_VOCAB; el módulo es hoja del núcleo y no importa el escapador"
    ),
}


def _segura(expr: ast.AST) -> bool:
    if isinstance(expr, ast.Call):
        f = expr.func
        nombre = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
        if nombre in _SEGURAS:
            return True
        return nombre == "str" and bool(expr.args) and _segura(expr.args[0])
    # Una constante de módulo la escribe el repo, no el invocante.
    return isinstance(expr, ast.Name) and expr.id.isupper()


def interpolaciones_crudas(raiz: Path = RAIZ):
    """`f"clave: {expr}"` con `expr` sin escapar, en código que escribe notas.

    Fuera de alcance, y por qué:
    - `scripts/_archived/`: no se ejecuta; la no-derogación lo conserva.
    - el argumento de `yaml.safe_load`: es una sonda del parser, no una nota.
    - el valor de un dict, o lo asignado a un subíndice: es un campo de informe
      (`"reason": f"ilegible: …"`), y lo serializa `json.dumps`.
    - `_VOCABULARIO_CERRADO`: valores que el código ya validó contra un
      vocabulario cerrado antes de escribirlos, declarados uno a uno con motivo.
    """
    sitios = []
    for zona in ("scripts", "vault"):
        for ruta in sorted((raiz / zona).rglob("*.py")):
            if "__pycache__" in ruta.parts or "_archived" in ruta.parts:
                continue
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
            exentos = set()
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Call) and getattr(nodo.func, "attr", "") == "safe_load":
                    exentos.update(id(a) for a in nodo.args)
                elif isinstance(nodo, ast.Dict):
                    exentos.update(id(v) for v in nodo.values)
                elif isinstance(nodo, ast.Assign) and all(
                        isinstance(t, ast.Subscript) for t in nodo.targets):
                    exentos.add(id(nodo.value))
            for nodo in ast.walk(arbol):
                if not isinstance(nodo, ast.JoinedStr) or id(nodo) in exentos:
                    continue
                if len(nodo.values) != 2:
                    continue
                prefijo, valor = nodo.values
                if (isinstance(prefijo, ast.Constant) and _CLAVE.match(str(prefijo.value))
                        and isinstance(valor, ast.FormattedValue)
                        and not _segura(valor.value)):
                    sitio = (f"{ruta.relative_to(raiz).as_posix()}: "
                             f"{prefijo.value}{{{ast.unparse(valor.value)}}}")
                    if sitio not in _VOCABULARIO_CERRADO:
                        sitios.append(sitio)
    return sitios


def test_ap56_ninguna_linea_de_frontmatter_interpola_crudo():
    assert interpolaciones_crudas() == []


def test_ap56_el_detector_ve_las_formas_que_persigue(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "vault").mkdir()
    (tmp_path / "scripts" / "vault_x.py").write_text(
        "lineas = [f'project: {project}', f'agent: {extra.get(\"agent\")}']\n"
        "ok = [f'title: {yaml_scalar(t)}', f'id: {uuid.uuid4()}', f'type: {SCAFFOLD}']\n"
        "sonda = yaml.safe_load(f'k: {valor}')\n"
        "informe = {'reason': f'ilegible: {exc}'}\n",
        encoding="utf-8",
    )
    sitios = interpolaciones_crudas(tmp_path)
    assert [s.split(": ", 1)[1] for s in sitios] == [
        "project: {project}", "agent: {extra.get('agent')}",
    ]


def test_ap56_el_valor_normal_sale_identico():
    assert valor_de_frontmatter("medium") == "medium"
    assert valor_de_frontmatter("CWE-798") == "CWE-798"
    assert valor_de_frontmatter("") == ""
    instante = "2026-10-01T08:10:06.000Z"
    assert valor_de_frontmatter(instante) == instante
    assert isinstance(yaml.safe_load(f"k: {valor_de_frontmatter(instante)}")["k"], datetime)


def test_ap56_un_salto_de_linea_no_crea_claves():
    hostil = "demo\nstatus: active"
    fm = yaml.safe_load(f"project: {valor_de_frontmatter(hostil)}\nagent: x\n")
    assert fm == {"project": hostil, "agent": "x"}


def test_ap56_vault_log_error_no_admite_claves_por_project(tmp_path):
    """El caso medido, con el criterio del consumidor: `yaml.safe_load`.

    Desde AP-63 la CLI ya no deja llegar el valor hostil: no es un proyecto
    registrado y sale `PROJECT_NOT_FOUND` sin escribir. El escapado del
    escritor sigue medido llamando a la función, que es quien lo garantiza
    para cualquier otro llamador."""
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    hostil = "demo\nstatus: active\ncia_sensitivity: public"
    env = dict(os.environ, VAULT_ROOT=str(raiz), PYTHONIOENCODING="utf-8")
    p = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "vault_log_error.py"),
         "--type", "error", "--title", "Fallo de prueba",
         "--description", "Descripcion suficientemente larga del fallo.",
         "--project", hostil],
        env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(RAIZ / "scripts"), timeout=180,
    )
    salida = json.loads(p.stdout[p.stdout.index("{"):])
    assert salida["error_code"] == "PROJECT_NOT_FOUND", salida
    assert [x.name for x in raiz.iterdir()] == ["00_System"]

    p = subprocess.run(
        [sys.executable, "-c",
         "import json, sys; from vault_log_error import vault_log_error; "
         "print(json.dumps(vault_log_error('error', 'Fallo de prueba', "
         "'Descripcion suficientemente larga del fallo.', project=sys.argv[1])))",
         hostil],
        env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(RAIZ / "scripts"), timeout=180,
    )
    salida = json.loads(p.stdout[p.stdout.index("{"):])
    assert salida["ok"] is True, salida
    texto = (raiz / salida["path"].replace("\\", "/")).read_text(encoding="utf-8")
    fm = yaml.safe_load(texto.split("---")[1])
    assert fm["project"] == hostil
    # Desde v41 `status` es requerido y el escritor lo pone: la inyección se
    # mide en que su valor sigue siendo el del contrato, no `active`.
    assert fm["status"] == "draft"
    assert fm["cia_sensitivity"] == "internal"
