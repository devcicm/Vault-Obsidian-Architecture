#!/usr/bin/env python3
"""vault_produccion — «¿puede usar esto otra persona, y con qué fiabilidad?»

## De dónde sale esta tool

De una pregunta del usuario, hecha con v40.30 recién cerrada y las 20 puertas en
verde: *«¿entonces ya puede ser usado por otras personas, aparte de mí, y con
resultados óptimos, decentes y fiables?»*

La respuesta honesta obligó a medir cosas que ninguna puerta miraba, y apareció
un defecto en menos de diez minutos: `pyproject.toml` prometía Python **>=3.9** y
la CI probaba **solo 3.11**. Seis sitios rompían en 3.9, y no al llamarse sino al
**importar** —`ast.AST | None` se evalúa al definir la función—, dos de ellos en
`vault_grafo_import` y `vault_norms_catalog`, que importa medio repo. Quien
instalara en 3.9 o 3.10 no habría arrancado nada.

Nada de eso estaba roto *aquí*. Ese es justo el punto.

## Por qué es un registro y no un párrafo en un doc

Porque una pregunta que hay que acordarse de hacer no se hace. Las 20 puertas
existentes miden **el repo contra sí mismo**: que el catálogo no diverja del
JSON, que la baseline no crezca, que el plano no envejezca. Todas correctas, y
todas ciegas a la misma cosa — el consumidor no está en la sala. Es AP-44 subido
un nivel: no «verificar con el criterio del consumidor» dentro de una tool, sino
**verificar que existe alguien que ejerza lo que el producto promete**.

El patrón que comparten los ocho defectos de v40.30 es uno solo:

    alcance declarado  >  alcance ejercido   ⇒   el hueco devuelve CERO,
                                                 y un cero se lee como limpio.

`cli/` declarado en `ARBOLES_MEDIDOS` sin contexto que lo clasificara. `vault/`
fuera del grafo de ciclos. El servidor MCP escaneando un disco que fuera del repo
no es el suyo. `>=3.9` sin nadie que ejecutase 3.9. Cada una devolvía un cero
tranquilizador.

## Qué mide, exactamente

Cada entrada de `PREGUNTAS` declara una **promesa al consumidor** y **quién la
ejerce**. La puerta falla cuando una promesa marcada como cubierta apunta a un
ejecutor que no existe: un fichero borrado, una versión que se cayó de la matriz
de CI, un comando que ya no está. No comprueba que el ejecutor *pase* —eso es
trabajo de la CI y de la suite—: comprueba que **exista**, que es la condición
que faltaba y que nadie miraba.

## Qué NO demuestra el verde

Verde aquí significa que toda promesa listada tiene ejecutor, y que las que no lo
tienen lo dicen con el motivo escrito. No significa que la lista esté completa.
Una promesa que nadie escribió en `PREGUNTAS` sigue sin medirse, y esta tool no
puede saber qué prometiste en un README que no lee. Por eso el registro se amplía
cuando alguien tropieza, y por eso las descubiertas se publican en vez de
callarse: una promesa que declara su hueco es más barata que una que lo esconde.

    python scripts/vault_produccion.py --check --strict
    python scripts/vault_produccion.py --guia     # regenera docs/GUIA-DE-PRODUCCION.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from vault_errors import emit_error, wrap_main

RAIZ = Path(__file__).resolve().parent.parent
GUIA = RAIZ / "docs" / "GUIA-DE-PRODUCCION.md"

#: Estados posibles de una promesa. `descubierta` NO es un fallo: es la forma
#: honesta de declarar un hueco, y el repo ya decidió en v40.16 que declararse
#: no puede salir más caro que callarse. Lo que rompe la puerta es una promesa
#: `cubierta` cuyo ejecutor no existe — o sea, una mentira comprobable.
ESTADOS = ("cubierta", "descubierta")


def _existe(rel: str) -> bool:
    return (RAIZ / rel).exists()


def _ci_prueba_el_piso() -> bool:
    """La matriz de CI y `requires-python` dicen la misma versión mínima."""
    ci = RAIZ / ".github" / "workflows" / "vault-ci.yml"
    proj = RAIZ / "pyproject.toml"
    if not ci.exists() or not proj.exists():
        return False
    m = re.search(r'requires-python\s*=\s*"[><=~^]*\s*(\d+)\.(\d+)',
                  proj.read_text(encoding="utf-8"))
    if not m:
        return False
    piso = (int(m.group(1)), int(m.group(2)))
    versiones = {
        tuple(int(x) for x in v.split("."))
        for v in re.findall(r"['\"](\d+\.\d+)['\"]", ci.read_text(encoding="utf-8"))
    }
    return bool(versiones) and min(versiones) == piso


def _ci_cubre_los_sistemas() -> bool:
    ci = RAIZ / ".github" / "workflows" / "vault-ci.yml"
    if not ci.exists():
        return False
    texto = ci.read_text(encoding="utf-8")
    return "ubuntu" in texto and "windows" in texto


def _hay_dependencias_declaradas() -> bool:
    """Toda dependencia que un módulo importa sin red está en `pyproject.toml`.

    Se comprueba contra PyYAML porque es la única, y porque el motivo por el que
    esta entrada existe fue afirmar en `INSTALL.md` que era opcional cuando seis
    módulos —`vault_write` entre ellos— la importan sin `except ImportError`.
    """
    proj = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    duros = [
        p.name for p in sorted((RAIZ / "scripts").glob("*.py"))
        if re.search(r"^import yaml\b", p.read_text(encoding="utf-8", errors="replace"),
                     flags=re.M)
    ]
    return (not duros) or ("PyYAML" in proj or "pyyaml" in proj.lower())


#: El registro. **Fuente única**: la guía de `docs/` se deriva de aquí y se
#: regenera con `--guia`; lo que se escriba a mano allí se pierde.
#:
#: `ejerce` es un predicado, no una cadena: una promesa cuyo ejecutor se
#: describe en prosa vuelve a ser un párrafo que nadie ejecuta, que es
#: exactamente el fallo que este fichero existe para no repetir.
PREGUNTAS: List[Dict[str, Any]] = [
    {
        "id": "piso_de_lenguaje",
        "pregunta": "¿La versión mínima que promete el paquete la ejecuta alguien?",
        "promesa": "pyproject.toml declara requires-python",
        "por_que": (
            "Un piso que ninguna máquina ejecuta es una promesa, no soporte. "
            "Medido en v40.30: la CI probaba solo 3.11 con >=3.9 publicado, y "
            "seis sitios rompían al IMPORTAR en 3.9 —no al llamarse—, dos de "
            "ellos en módulos que importa medio repo."
        ),
        "ejerce": _ci_prueba_el_piso,
        "quien": "matriz python-version de .github/workflows/vault-ci.yml + tests/test_piso_python.py",
        "estado": "cubierta",
    },
    {
        "id": "dependencias_reales",
        "pregunta": "¿Lo que se importa sin red está declarado como dependencia?",
        "promesa": "INSTALL.md y pyproject.toml enumeran qué hace falta instalar",
        "por_que": (
            "Se afirmó que PyYAML era opcional porque «cada módulo que la "
            "importa tiene su except ImportError». Falso: seis la importan sin "
            "red, y uno es vault_write, el camino de escritura. La diferencia "
            "entre opcional y obligatoria la decide el código, no el recuerdo."
        ),
        "ejerce": _hay_dependencias_declaradas,
        "quien": "pyproject.toml [project.dependencies]",
        "estado": "cubierta",
    },
    {
        "id": "instalacion_fuera_del_repo",
        "pregunta": "¿Funciona copiado fuera de este repositorio?",
        "promesa": "INSTALL.md: copiar cuatro carpetas y exportar VAULT_ROOT",
        "por_que": (
            "Dentro del repo la autodetección acierta, los vaults de al lado "
            "son los consumidores conocidos y la ruta al manifiesto existe. "
            "Fuera, ninguna de las tres cosas es verdad: la raíz caía a "
            "repo_root_fallback y las escrituras aterrizaban DENTRO del "
            "toolkit, y el servidor MCP inventariaba el disco del usuario."
        ),
        "ejerce": lambda: _existe("INSTALL.md") and _existe("tests/test_portabilidad_v4030.py"),
        "quien": "tests/test_portabilidad_v4030.py + INSTALL.md",
        "estado": "cubierta",
    },
    {
        "id": "material_ajeno",
        "pregunta": "¿Se ha medido contra material que este repo no generó?",
        "promesa": "El estándar sirve para vaults preexistentes, no solo para los suyos",
        "por_que": (
            "Es la regla 7, y es la única de la casa que ya se pagó cinco "
            "veces: vault-sandbox/ lo genera este repo y comparte sus "
            "supuestos, así que no puede exhibir el fallo que la medida tiene."
        ),
        "ejerce": lambda: _existe("scripts/vault_foreign_check.py"),
        "quien": "vault_foreign_check --root <vault ajeno>, o --self-test sin uno a mano",
        "estado": "cubierta",
    },
    {
        "id": "sistemas_operativos",
        "pregunta": "¿Se ejecuta en los sistemas donde se dice que corre?",
        "promesa": "Multiplataforma: rutas por pathlib, sin dependencias del shell",
        "por_que": (
            "Todo el desarrollo ocurre en Windows. Las trampas de plataforma "
            "—finales de línea, codificación de la locale, mayúsculas del "
            "sistema de ficheros— son justo las que no se ven desde dentro."
        ),
        "ejerce": _ci_cubre_los_sistemas,
        "quien": "matriz os de la CI (ubuntu-latest, windows-latest)",
        "estado": "cubierta",
        "hueco_conocido": (
            "La CI ejecuta la suite en ubuntu, pero el paseo de INSTALACIÓN "
            "fuera del repo solo se ha hecho en Windows. macOS no lo toca nadie."
        ),
    },
    {
        "id": "superficie_expuesta",
        "pregunta": "¿Está escrito qué expone y a quién, donde lo lee quien instala?",
        "promesa": "El servidor MCP es local y sin autenticación",
        "por_que": (
            "Escucha en 127.0.0.1 y no comprueba ninguna cabecera. Es correcto "
            "como diseño y peligroso como sorpresa: quien lo ponga detrás de un "
            "proxy sin saberlo publica el vault entero. La decisión es del "
            "usuario, pero solo si la tiene delante."
        ),
        "ejerce": lambda: "autenticación" in (RAIZ / "INSTALL.md").read_text(encoding="utf-8"),
        "quien": "INSTALL.md, sección «Servidor MCP»",
        "estado": "cubierta",
    },
    {
        "id": "ergonomia_de_entrada",
        "pregunta": "¿Se invoca como un programa o como un montón de scripts?",
        "promesa": "—",
        "por_que": (
            "No hay [project.scripts], así que no existe un comando `vault`: se "
            "invoca `python .../scripts/vault_x.py`. Funciona y no engaña a "
            "nadie, pero es la diferencia entre un toolkit y un producto, y "
            "quien llega de fuera la nota en el primer minuto."
        ),
        "ejerce": lambda: "[project.scripts]" in (RAIZ / "pyproject.toml").read_text(encoding="utf-8"),
        "quien": "—",
        "estado": "descubierta",
        "motivo": (
            "Decisión de producto sin tomar. Declarar entry points ata el "
            "nombre público de cada tool del catálogo, y renombrar uno después "
            "rompe a quien lo llamara. Se decide el día que esto se publique en "
            "un índice de paquetes, no hoy."
        ),
    },
    {
        "id": "contrato_con_quien_contribuye",
        "pregunta": "¿Sabe alguien de fuera cómo aportar o cómo reportar un fallo?",
        "promesa": "Repositorio público",
        "por_que": (
            "Para un repo público esto no es un detalle de forma: sin canal "
            "declarado, un fallo de seguridad no tiene por dónde llegar salvo "
            "un issue abierto, que es el peor sitio para reportarlo."
        ),
        "ejerce": lambda: _existe("CONTRIBUTING.md") and _existe("SECURITY.md"),
        "quien": "CONTRIBUTING.md + SECURITY.md",
        "estado": "cubierta",
    },
    {
        "id": "lo_publicado_es_solo_el_estandar",
        "pregunta": "¿Puede irse en un push algo que no es de este repo?",
        "promesa": "Repositorio público que convive con copias de vaults reales",
        "por_que": (
            "En el mismo disco, al lado del estándar, viven `_datasets/`, "
            "`_datasets-reports/` y `_backups-builderx/`: notas privadas de "
            "otros proyectos, runbooks con credenciales, datos de clientes. "
            "Hasta hoy eso lo sostenía solo el `.gitignore`, que es advisory: "
            "no para un `git add -f` ni un directorio hermano nuevo que nadie "
            "añada al fichero. Y publicado es publicado, aunque se borre "
            "después — la copia queda en el historial, en los forks y en la "
            "caché de quien lo indexó."
        ),
        "ejerce": lambda: _existe("tests/test_publicacion_limpia.py"),
        "quien": "tests/test_publicacion_limpia.py (mide el índice de git, no el disco)",
        "estado": "cubierta",
        "hueco_conocido": (
            "Mide el índice de HOY. Lo que ya esté en un commit anterior del "
            "historial no lo ve nadie: para eso haría falta recorrer todos los "
            "árboles, y este repo nunca ha versionado esos directorios."
        ),
    },
]


def medir() -> Dict[str, Any]:
    """Evalúa cada promesa. El predicado se llama AHORA, nunca al importar."""
    filas = []
    for p in PREGUNTAS:
        try:
            ejercida = bool(p["ejerce"]())
        except (OSError, ValueError, KeyError):
            # Un predicado que no puede leer lo que mide no es un verde: es una
            # promesa que dejó de tener ejecutor, que es justo el caso a cazar.
            ejercida = False
        filas.append({
            "id": p["id"],
            "pregunta": p["pregunta"],
            "estado": p["estado"],
            "ejercida": ejercida,
            "quien": p["quien"],
            **({"hueco_conocido": p["hueco_conocido"]} if p.get("hueco_conocido") else {}),
            **({"motivo": p["motivo"]} if p.get("motivo") else {}),
        })
    return {"filas": filas}


def check() -> Dict[str, Any]:
    m = medir()
    rotas = [
        f["id"] for f in m["filas"]
        if f["estado"] == "cubierta" and not f["ejercida"]
    ]
    sin_motivo = [
        f["id"] for f in m["filas"]
        if f["estado"] == "descubierta" and not f.get("motivo")
    ]
    desconocidos = [f["id"] for f in m["filas"] if f["estado"] not in ESTADOS]
    return {
        "ok": not rotas and not sin_motivo and not desconocidos,
        "tool": "vault_produccion",
        "action": "check",
        "promesas": len(m["filas"]),
        "cubiertas": sum(1 for f in m["filas"] if f["estado"] == "cubierta"),
        "descubiertas": sum(1 for f in m["filas"] if f["estado"] == "descubierta"),
        "huecos_declarados": [
            f["id"] for f in m["filas"] if f.get("hueco_conocido")
        ],
        "promesas_sin_ejecutor": rotas,
        "descubiertas_sin_motivo": sin_motivo,
        "estados_desconocidos": desconocidos,
        "filas": m["filas"],
        "hint": (
            "Verde significa que toda promesa listada tiene quien la ejerza, no "
            "que la lista esté completa. Una promesa que nadie escribió aquí "
            "sigue sin medirse."
        ),
    }


def _guia() -> str:
    m = medir()
    L = [
        "# Guía de construcción — las preguntas que no se hace el repo a sí mismo",
        "",
        "> **Documento derivado.** Sale de `scripts/vault_produccion.PREGUNTAS` y se",
        "> regenera con `python scripts/vault_produccion.py --guia`. Lo que se escriba",
        "> a mano aquí se pierde: es lo que lo mantiene honesto.",
        "",
        "## De dónde sale",
        "",
        "De una pregunta hecha con todas las puertas en verde y una versión recién",
        "cerrada: **«¿ya puede usarlo otra persona, aparte de mí, y con resultados",
        "fiables?»**. En menos de diez minutos apareció un defecto que ninguna puerta",
        "veía —el piso de Python prometido que ninguna máquina ejecutaba—, porque",
        "todas las puertas miden *el repo contra sí mismo* y en esa sala no está el",
        "consumidor.",
        "",
        "El patrón es siempre el mismo, y es el de toda la tanda v40.30:",
        "",
        "```",
        "alcance declarado  >  alcance ejercido   ⇒   el hueco devuelve CERO,",
        "                                             y un cero se lee como limpio.",
        "```",
        "",
        "Por eso la pregunta se hace **antes** de dar algo por terminado, y por eso",
        "está escrita como registro ejecutable y no como recordatorio.",
        "",
        "## Cómo se usa en construcción",
        "",
        "1. Antes de cerrar una versión, `python scripts/vault_produccion.py --check --strict`.",
        "2. Cuando añadas una promesa al consumidor —una versión soportada, una",
        "   plataforma, una dependencia opcional, una superficie de red— **añade su fila**",
        "   con el predicado que la ejerce. Una promesa sin fila no la mide nadie.",
        "3. Si no tiene ejecutor, se declara `descubierta` **con el motivo escrito**. No",
        "   es un fallo: es la forma barata. Lo que rompe la puerta es una promesa",
        "   marcada como cubierta cuyo ejecutor ya no existe — una mentira comprobable.",
        "",
        "## Estado",
        "",
        "| Promesa | Pregunta | Estado | Quién la ejerce |",
        "|---|---|---|---|",
    ]
    for f in m["filas"]:
        marca = "✅" if f["ejercida"] else ("⚠️" if f["estado"] == "descubierta" else "❌")
        L.append(f"| `{f['id']}` | {f['pregunta']} | {marca} {f['estado']} | {f['quien']} |")

    L += ["", "## Los huecos, escritos", ""]
    hay = False
    for p in PREGUNTAS:
        if p.get("motivo"):
            hay = True
            L += [f"**`{p['id']}` — descubierta.** {p['por_que']}", "",
                  f"*Por qué se deja así:* {p['motivo']}", ""]
        if p.get("hueco_conocido"):
            hay = True
            L += [f"**`{p['id']}` — cubierta con hueco.** {p['hueco_conocido']}", ""]
    if not hay:
        L += ["Ninguno declarado.", ""]

    L += [
        "## Qué NO demuestra el verde",
        "",
        "Que toda promesa **listada** tiene ejecutor. No que la lista esté completa:",
        "una promesa que nadie escribió en el registro sigue sin medirse, y esta tool",
        "no puede leer lo que prometiste en un README que no conoce. El registro se",
        "amplía cuando alguien tropieza — que es exactamente como nació.",
        "",
    ]
    return "\n".join(L)


def escribir_guia() -> Dict[str, Any]:
    GUIA.parent.mkdir(parents=True, exist_ok=True)
    GUIA.write_text(_guia(), encoding="utf-8")
    return {"ok": True, "tool": "vault_produccion", "action": "guia",
            "written": str(GUIA.relative_to(RAIZ)).replace("\\", "/"),
            "promesas": len(PREGUNTAS)}


def check_doc() -> Dict[str, Any]:
    actual = GUIA.read_text(encoding="utf-8") if GUIA.exists() else ""
    al_dia = actual == _guia()
    return {"ok": al_dia, "tool": "vault_produccion", "action": "check-doc",
            "doc": str(GUIA.relative_to(RAIZ)).replace("\\", "/"),
            "stale": not al_dia,
            "recovery": "python scripts/vault_produccion.py --guia"}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="vault_produccion — ¿puede usar esto otra persona? (guía de construcción)")
    ap.add_argument("--check", action="store_true", help="Mide cada promesa contra su ejecutor")
    ap.add_argument("--strict", action="store_true", help="Exit 1 si alguna promesa perdió ejecutor")
    ap.add_argument("--guia", action="store_true", help="Regenera docs/GUIA-DE-PRODUCCION.md")
    ap.add_argument("--check-doc", action="store_true", help="Falla si la guía diverge del registro")
    args = ap.parse_args()

    if args.guia and args.check:
        env = emit_error("vault_produccion", "CONFLICTING_ARGS",
                         "--guia escribe y --check mide: elige uno")
        env["recovery"] = "elige uno"
        print(json.dumps(env, ensure_ascii=False))
        return 1

    if args.guia:
        r: Dict[str, Any] = escribir_guia()
    elif args.check_doc:
        r = check_doc()
    else:
        r = check()

    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 1 if args.strict and not r["ok"] else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_produccion"))
