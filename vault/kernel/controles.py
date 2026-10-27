"""Puerto de los controles obligatorios del estandar (DEC-02, ruta B, I2-a).

**Contrato de DATOS, no de simbolos.** Este modulo es hoja del nucleo: no
importa ningun contexto (solo stdlib), y publica la tabla de que superficie
responde a cada control. Quien compone —gobernanza— lee la tabla y lanza la
superficie del dueno como **proceso**. Un proceso no es una arista del grafo de
imports: el cruce `gobernanza -> meta_toolkit` desaparece del grafo sin
esconderse (AP-58: esconder el cruce dentro de una funcion es el fallo que ese
guard persigue, y por eso aqui no hay imports diferidos).

## Por que proceso y no registro en memoria

La variante de registro (`registrar_control("AP-40", callable)`) obliga a quien
compone a importar al dueno para que se registre: la arista vuelve. La variante
de proceso no depende de quien importa a quien, y la evidencia la produce el
dueno (su tool, su exit code, su envelope), que es lo que AP-43 pide.

## Contrato de la superficie del dueno

Cada superficie imprime **un** JSON en stdout con, como minimo:

  - `ok`: bool — si el control paso;
  - `problemas`: lista de `{"clave": str, "detalle": str}` — un elemento por
    hallazgo (vacia si no hay);
  - opcionalmente `hallazgos`: int — si no viene, se cuenta `problemas`.

Un envelope que no cumple el contrato **no es un PASS**: se degrada a
`fallido` y el consumidor lo ve. Un control que no pudo correr nunca cuenta
como cero hallazgos.

## Fail-closed

| Situacion | Estado |
|---|---|
| script ausente / no invocable | `no_ejecutado` |
| timeout | `fallido` |
| stdout no es JSON / sin `ok` | `fallido` |
| JSON valido y `ok: false` | `ejecutado` (corrio; sus hallazgos cuentan) |
| JSON valido y `ok: true` | `ejecutado` |

Ninguno de esos estados es "limpio por omision": `no_ejecutado` y `fallido`
hacen fallar el resumen de cobertura del consumidor (TD-0003).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = [
    "CONTROLES",
    "ESTADOS",
    "contrato_del_puerto",
    "ejecutar",
]

ESTADOS = ("ejecutado", "degradado", "fallido", "no_ejecutado")

#: El registro es DATOS: el analizador de contextos puede leerlo y declarar el
#: puerto, en vez de encontrarse un import dinamico. Cada entrada nombra al
#: dueno, el script que publica la superficie y su argv; nada de callables.
CONTROLES: Dict[str, Dict[str, Any]] = {
    "AP-40": {
        "dueno": "meta_toolkit",
        "script": "vault_mcp_catalog",
        "argv": ["--check-params"],
        "severidad": "medium",
        "que_mide": "el contrato publicado del catalogo es el que la CLI acepta",
    },
    "AP-42": {
        "dueno": "meta_toolkit",
        "script": "vault_smoke",
        "argv": ["--baseline-check"],
        "severidad": "medium",
        "que_mide": ("la deuda de ejecucion esta declarada y ningun ejemplo "
                     "documentado se queda sin invocacion"),
    },
    "AP-43": {
        "dueno": "autoria",
        "script": "vault_voice",
        "argv": ["--coverage"],
        "severidad": "medium",
        "que_mide": "ninguna norma se queda sin que la pronuncie una tool",
    },
}

#: Presupuesto de latencia por control (DEC-02/COST-a). Medido: ver
#: `tests/test_puerto_controles.py`. El camino ingenuo medía ~149 s porque
#: ejecutaba el smoke completo; la superficie ligera no ejecuta tools.
SEGUNDOS_MAXIMOS = 5.0
TIMEOUT = 120


def _raiz_de_scripts(raiz: Optional[Path]) -> Optional[Path]:
    """Directorio donde vive la superficie del dueno, o None si no esta.

    Con `raiz` explicita se mira SOLO `raiz/scripts`: quien acota el arbol no
    espera que el puerto caiga al del repo (fail-closed, y es lo que permite
    probar la ausencia de superficie). Sin `raiz`, se deriva del propio
    paquete: checkout (`<repo>/scripts`) o wheel instalada
    (`vault_toolkit/_impl`, I2-a). Nunca del CWD.
    """
    if raiz is not None:
        candidato = Path(raiz) / "scripts"
        return candidato if candidato.is_dir() else None
    candidatos: List[Path] = [
        Path(__file__).resolve().parent.parent.parent / "scripts"]
    try:  # wheel instalada: el paquete viaja en vault_toolkit/_impl/
        import importlib.util

        especificacion = importlib.util.find_spec("vault_toolkit")
        if especificacion is not None and especificacion.origin:
            candidatos.append(
                Path(especificacion.origin).resolve().parent / "_impl")
    except (ImportError, ValueError, OSError):
        pass
    for candidato in candidatos:
        if candidato.is_dir():
            return candidato
    return None


def _normalizar_problemas(envelope: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extrae `problemas` del envelope, aceptando el contrato o nada."""
    crudos = envelope.get("problemas")
    if not isinstance(crudos, list):
        return []
    normalizados: List[Dict[str, str]] = []
    for item in crudos:
        if isinstance(item, dict):
            normalizados.append({
                "clave": str(item.get("clave") or ""),
                "detalle": str(item.get("detalle") or ""),
            })
    return normalizados


def contrato_del_puerto() -> Dict[str, Any]:
    """La tabla publicada, para tests y para el analizador de contextos."""
    return {
        "ok": True,
        "tool": "vault.kernel.controles",
        "contrato": "datos+proceso",
        "segundos_maximos": SEGUNDOS_MAXIMOS,
        "controles": {
            codigo: {
                "dueno": datos["dueno"],
                "script": datos["script"],
                "argv": list(datos["argv"]),
                "severidad": datos["severidad"],
            }
            for codigo, datos in CONTROLES.items()
        },
    }


def ejecutar(codigo: str, raiz: Optional[Path] = None,
             timeout: int = TIMEOUT) -> Dict[str, Any]:
    """Lanza la superficie del dueno como proceso y normaliza su resultado.

    Devuelve `{control, estado, detalle, hallazgos, problemas, envelope,
    exit_code, segundos, superficie}`. Nunca lanza por un control que no
    pudo correr: lo declara.
    """
    import time

    datos = CONTROLES.get(codigo)
    if datos is None:
        return {"control": codigo, "estado": "no_ejecutado",
                "detalle": "control_no_declarado_en_el_puerto",
                "hallazgos": 0, "problemas": [], "envelope": None,
                "exit_code": None, "segundos": 0.0, "superficie": None}

    directorio = _raiz_de_scripts(raiz)
    script = (directorio / f"{datos['script']}.py") if directorio else None
    if script is None or not script.is_file():
        return {"control": codigo, "estado": "no_ejecutado",
                "detalle": f"superficie_ausente ({datos['script']}.py)",
                "hallazgos": 0, "problemas": [], "envelope": None,
                "exit_code": None, "segundos": 0.0, "superficie": None}

    # Las tres superficies imprimen JSON por defecto: el puerto no inyecta
    # flags que no esten declarados en el registro (datos, no adivinacion).
    argv = [sys.executable, str(script), *datos["argv"]]
    inicio = time.monotonic()
    try:
        proceso = subprocess.run(argv, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace",
                                 timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"control": codigo, "estado": "fallido",
                "detalle": f"timeout ({timeout}s)", "hallazgos": 0,
                "problemas": [], "envelope": None, "exit_code": None,
                "segundos": round(time.monotonic() - inicio, 3),
                "superficie": script.name}
    except OSError as exc:
        return {"control": codigo, "estado": "no_ejecutado",
                "detalle": f"no_invocable ({exc})", "hallazgos": 0,
                "problemas": [], "envelope": None, "exit_code": None,
                "segundos": round(time.monotonic() - inicio, 3),
                "superficie": script.name}
    segundos = round(time.monotonic() - inicio, 3)

    envelope: Optional[Dict[str, Any]] = None
    # Primero el stdout completo (los envelopes indentados son JSON valido de
    # varias lineas: `--check-params` lo imprime con indent=2), y despues la
    # ultima linea que parsea, para las tools que escriben un log antes.
    candidatos = [proceso.stdout or ""]
    candidatos += list(reversed((proceso.stdout or "").splitlines()))
    for texto in candidatos:
        texto = (texto or "").strip()
        if not texto:
            continue
        try:
            candidato = json.loads(texto)
        except ValueError:
            continue
        if isinstance(candidato, dict) and "ok" in candidato:
            envelope = candidato
            break

    if envelope is None:
        return {"control": codigo, "estado": "fallido",
                "detalle": (f"sin envelope JSON con `ok` (exit "
                            f"{proceso.returncode})"),
                "hallazgos": 0, "problemas": [], "envelope": None,
                "exit_code": proceso.returncode, "segundos": segundos,
                "superficie": script.name}

    problemas = _normalizar_problemas(envelope)
    hallazgos = envelope.get("hallazgos")
    if not isinstance(hallazgos, int) or isinstance(hallazgos, bool):
        hallazgos = len(problemas)
    detalle = None if envelope.get("ok") else (
        f"el dueno declara ok: false con {hallazgos} hallazgo(s)")
    return {"control": codigo, "estado": "ejecutado", "detalle": detalle,
            "hallazgos": hallazgos, "problemas": problemas,
            "envelope": envelope, "exit_code": proceso.returncode,
            "segundos": segundos, "superficie": script.name}
