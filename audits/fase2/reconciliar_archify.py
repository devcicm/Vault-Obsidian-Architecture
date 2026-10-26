#!/usr/bin/env python3
"""Reconciliador Archify <-> codigo actual — auditoria de fase 2 (L1).

Archify es EVIDENCIA AUXILIAR: un snapshot de otra revision. Este script no
juzga el codigo — comprueba que del snapshot sigue vigente, que ya se resolvio
(y como), y que sigue siendo deuda. La verdad es el registro del repo
(`vault_arch`); el script solo lo confronta con el snapshot.

Dos capas, porque el snapshot y el codigo no habla la misma granularidad:

  1. PARES DE CONTEXTO: `_crucas` (23, con ficha) contra
     `PRESUPUESTO_DE_CRUCES` (23, con la misma ficha). Comparacion directa,
     metadatos incluidos.
  2. DEPENDENCIAS: `_crossings` (37, a nivel de FICHERO) contra los cruces vivos
     (49 sitios / 37 claves). Se comparan por par de contexto —el nivel que
     ambos comparten sin ambiguedad— y el resto se declara NO CONCILIABLE
     automaticamente, con la regla aplicada a la vista.

Uso: python audits/fase2/reconciliar_archify.py [--json SALIDA]
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import vault_arch as arch  # noqa: E402

ARCHIFY = ROOT / ".archify" / "extraccion-registro.json"

#: Puertos publicados en la ronda 1 (Q01/Q03) con el cruce que saldio: sin este
#: mapa, un cruce ya resuelto pareceria una violacion nueva.
RESUELTOS_EN_RONDA_1 = {
    "vault_write -> vault_tags.apply_vocabulary": "4fededd (Q01): puerto resolucion_de_vocabulario",
    "vault_write -> vault_tags.record_new_tags": "4fededd (Q01): puerto registro_de_nuevos_terminos",
    "vault_sanacion -> vault_reindex.notas_indexables": "f6a5387 (Q03): puerto enumeracion_indexable",
}

FICHA_CAMPOS = ("objetivo", "dueno", "revisado", "cadencia_dias", "por_que")


def _cargar_archify() -> Dict[str, Any]:
    return json.loads(ARCHIFY.read_text(encoding="utf-8"))


def _sha() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


#: Contexto dueno de cada nombre que aparece en los cruces vivos. El registro
#: habla de modulos por su nombre publico (alias) y a veces por la ruta del
#: dueno; el mapa se construye con los propios cruces, que traen las dos formas.
_ALIAS_A_CONTEXTO: Dict[str, str] = {}


def _construir_alias_a_contexto() -> Dict[str, str]:
    if _ALIAS_A_CONTEXTO:
        return _ALIAS_A_CONTEXTO
    for cruce in arch.cruces():
        for nombre, ctx in ((cruce.get("from"), cruce.get("from_context")),
                            (cruce.get("to"), cruce.get("to_context"))):
            if nombre and ctx:
                _ALIAS_A_CONTEXTO.setdefault(str(nombre), str(ctx))
    for ctx, datos in arch.CONTEXTS.items():
        for modulo in datos.get("modulos", []):
            _ALIAS_A_CONTEXTO.setdefault(str(modulo), str(ctx))
    return _ALIAS_A_CONTEXTO


def _contexto_de(nombre: str) -> str:
    """Contexto dueno de un modulo o de una ruta, con el criterio del repo.

    Tres formas conviven en el snapshot y en el codigo: el nombre publico del
    alias (`vault_change_log`), la ruta del dueno (`vault/gobernanza`) y el
    fichero (`vault/autoria/repositorio.py`). Los contextos son directorios de
    `vault/<contexto>/`, asi que la ruta se lee sin ambiguedad.
    """
    limpio = str(nombre).strip()
    if not limpio:
        return "desconocido"
    if limpio.endswith(".py"):
        limpio = limpio[:-3]
    if limpio.startswith("vault/"):
        partes = limpio.split("/")
        if len(partes) >= 2:
            return partes[1] if partes[1] in arch.CONTEXTS else "desconocido"
    if limpio.startswith("vault."):
        partes = limpio.split(".")
        if len(partes) >= 2:
            return partes[1] if partes[1] in arch.CONTEXTS else "desconocido"
    mapa = _construir_alias_a_contexto()
    if limpio in mapa:
        return mapa[limpio]
    try:
        ctx = arch.contexto_de(limpio)
    except Exception:
        ctx = None
    return ctx or "desconocido"


def reconciliar_pares(snap: Dict[str, Any]) -> Dict[str, Any]:
    """Capa 1: pares de contexto con su ficha."""
    snap_crucas = snap.get("_crucas", {}) or {}
    vivos = arch.PRESUPUESTO_DE_CRUCES

    def _clave(par: Any) -> Tuple[str, str]:
        """El par (origen, destino) de una ficha.

        El snapshot lo serializa como texto: "('autoria', 'gobernanza')".
        """
        if isinstance(par, (list, tuple)):
            return (str(par[0]).strip(), str(par[1]).strip())
        texto = str(par).strip()
        try:
            valor = ast.literal_eval(texto)
            if isinstance(valor, (list, tuple)) and len(valor) == 2:
                return (str(valor[0]).strip(), str(valor[1]).strip())
        except (ValueError, SyntaxError):
            pass
        limpio = texto.strip("()[] ")
        partes = [p.strip().strip("'\"") for p in limpio.split(",", 1)]
        return (partes[0], partes[1] if len(partes) > 1 else "")

    pares_snap = {_clave(k): v for k, v in snap_crucas.items()}
    pares_vivos = {_clave(k): v for k, v in vivos.items()}

    def _ficha(valor: Any) -> Dict[str, Any]:
        """La ficha del snapshot viene serializada como texto."""
        if isinstance(valor, dict):
            return valor
        try:
            posible = ast.literal_eval(str(valor))
            if isinstance(posible, dict):
                return posible
        except (ValueError, SyntaxError):
            pass
        return {}

    comun = set(pares_snap) & set(pares_vivos)
    filas = []
    for par in sorted(comun):
        fs, fv = _ficha(pares_snap[par]), _ficha(pares_vivos[par])
        diferencias = []
        for campo in FICHA_CAMPOS:
            vs, vv = str(fs.get(campo, "")), str(fv.get(campo, ""))
            if vs != vv:
                diferencias.append({"campo": campo, "snapshot": vs[:160],
                                    "registro": vv[:160]})
        filas.append({
            "par": list(par),
            "estado": "VIGENTE" if not diferencias else "DIVERGENTE (ficha)",
            "diferencias": diferencias,
        })
    return {
        "pares_snapshot_n": len(pares_snap),
        "pares_registro_n": len(pares_vivos),
        "coincidentes": len(comun),
        "solo_en_snapshot": [list(p) for p in sorted(set(pares_snap) - set(pares_vivos))],
        "solo_en_registro": [list(p) for p in sorted(set(pares_vivos) - set(pares_snap))],
        "fichas": filas,
    }


def _par_de_contexto(desde: str, hasta: str) -> Tuple[str, str]:
    """El par de contextos de una dependencia, con el criterio del repo.

    El snapshot habla a veces de ficheros (`vault/autoria/repositorio.py`) y el
    codigo de modulos (`vault_change_log`); se normaliza por el contexto dueno.
    """
    return (_contexto_de(desde), _contexto_de(hasta))


def reconciliar_dependencias(snap: Dict[str, Any]) -> Dict[str, Any]:
    """Capa 2: dependencias del snapshot contra los cruces vivos."""
    snap_deps = [str(c) for c in snap.get("_crossings", [])]
    vivos = arch.cruces()
    pares_vivos = {(c["from_context"], c["to_context"]) for c in vivos}
    pares_snap: Dict[Tuple[str, str], List[str]] = {}
    for dep in snap_deps:
        if " -> " in dep:
            desde, hasta = dep.split(" -> ", 1)
            pares_snap.setdefault(_par_de_contexto(desde, hasta), []).append(dep)

    filas = []
    for par, deps in sorted(pares_snap.items()):
        if par in pares_vivos:
            estado = "VIGENTE"
            nota = "el par de contextos sigue cruzando: vive en el registro"
        else:
            estado = "NO CONCILIABLE por par de contexto"
            nota = ("la dependencia del snapshot no aparece como par de contextos "
                    "en el codigo actual: puede ser un cruce ya resuelto, un "
                    "dueno migrado o granularidad de fichero; requiere lectura")
        filas.append({"par": list(par), "dependencias_snapshot": deps,
                      "estado": estado, "nota": nota})
    filas.extend(_dependencias_por_modulo(snap))
    return {
        "dependencias_snapshot_n": len(snap_deps),
        "pares_snapshot_n": len(pares_snap),
        "sitios_vivos_n": len(vivos),
        "pares_contexto_vivos_n": len(pares_vivos),
        "pares_vigentes": sum(1 for f in filas if f["estado"] == "VIGENTE"),
        "filas": filas,
    }


def reconciliar_off_port(snap: Dict[str, Any]) -> List[Dict[str, Any]]:
    claves_vivas = {arch._clave_fuera_de_puerto(x)
                    for x in arch.cruces_fuera_de_puerto()}
    filas = []
    for entrada in snap.get("_off_port", []):
        clave = str(entrada)
        if clave in claves_vivas:
            estado = "VIGENTE (deuda vigilada)"
            nota = "sigue fuera de puerto: no se ha resuelto"
        elif clave in RESUELTOS_EN_RONDA_1:
            estado = "RESUELTO en ronda 1"
            nota = RESUELTOS_EN_RONDA_1[clave]
        else:
            estado = "NO CONCILIADO"
            nota = "no aparece ni vivo ni resuelto: requiere investigacion"
        filas.append({"clave": clave, "estado": estado, "nota": nota})
    return filas


def _modulo_publico(nombre: str) -> str:
    """El nombre con el que el repo nombra hoy ese modulo o fichero.

    Usa los resolvers del propio repo (`vault_grafo_import`): el nombre
    publico del alias si lo hay, y el del dueno si no. Sin esta capa, la
    conciliacion solo llega al par de contextos y no puede afirmar nada sobre
    el SITIO: `vault/autoria/repositorio.py` y `vault/autoria/repositorio.py`
    son el mismo dueno con dos grafias.
    """
    import vault_grafo_import as gi

    limpio = str(nombre).strip()
    if not limpio:
        return ""
    if limpio.endswith(".py"):
        limpio = limpio[:-3]
    if limpio.startswith("vault/"):
        partes = limpio.split("/")
        if len(partes) >= 3:
            # Ruta de dueno: la clave canonica del repo es la ruta misma
            # (`vault_arch.clave_de_modulo`), no su basename: cinco duenos se
            # llaman `repositorio` y el nombre suelto no distinguiria ninguno.
            ruta = ROOT.joinpath(*partes).with_suffix(".py")
            if ruta.exists():
                return arch.clave_de_modulo(ruta)
            return limpio
        # `vault/<contexto>` es un CONTEXTO, no un modulo.
        return limpio
    # Ya es un nombre publico de modulo (alias).
    return limpio


def _dependencias_por_modulo(snap: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Capa fina: cada dependencia del snapshot, resuelta a modulo PUBLICO.

    Es la conciliacion EXACTA (no por par de contexto): se resuelve cada lado
    con el resolver del repo y se busca la fila viva que dice exactamente eso.
    Lo que no se resuelve se declara NO NORMALIZABLE, con el motivo: no se
    afirma una conciliacion que no se ha hecho.
    """
    vivos = arch.cruces()
    pares_modulo_vivos = {(c["from"], c["to"]) for c in vivos}
    claves_off_port = {arch._clave_fuera_de_puerto(x)
                       for x in arch.cruces_fuera_de_puerto()}
    filas = []
    for entrada in snap.get("_crossings", []):
        texto = str(entrada)
        if " -> " not in texto:
            continue
        desde, hasta = texto.split(" -> ", 1)
        mod_desde, mod_hasta = _modulo_publico(desde), _modulo_publico(hasta)
        if not mod_desde or not mod_hasta:
            filas.append({"dependencia": texto, "estado": "NO NORMALIZABLE",
                          "nota": "uno de los dos lados no se resuelve a modulo"})
            continue
        if (mod_desde, mod_hasta) in pares_modulo_vivos:
            estado = "EXACTA (modulo vivo)"
            nota = "la dependencia existe hoy con esos dos modulos"
        elif mod_hasta in arch.CONTEXTS or \
                (mod_hasta.startswith("vault/") and
                 mod_hasta.split("/", 1)[1] in arch.CONTEXTS):
            estado = "VIGENTE (par de contextos)"
            nota = ("el destino es un CONTEXTO en el snapshot: el cruce vive en "
                    "el registro por par, no por modulo")
        else:
            clave = f"{mod_desde} -> {mod_hasta}"
            if clave in RESUELTOS_EN_RONDA_1 or clave in claves_off_port:
                estado = "RESUELTO o vigilado"
                nota = ("el simbolo ya no cruza fuera de puerto o se resolvio "
                        "en la ronda 1")
            else:
                estado = "NO CONCILIABLE"
                nota = "no existe esa dependencia en el codigo actual"
        filas.append({"dependencia": texto, "modulos": [mod_desde, mod_hasta],
                      "estado": estado, "nota": nota})
    return filas


def recon_off_port(snap: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Los accesos fuera de puerto del snapshot, ya clasificados."""
    return reconciliar_off_port(snap)


def reconciliar_anclas(snap: Dict[str, Any]) -> Dict[str, Any]:
    anclas_snap = snap.get("_anclas", {}) or {}
    anclas_vivas = dict(arch.ANCLA_DEL_PUENTE)
    comunes = sorted(set(anclas_snap) & set(anclas_vivas))
    return {
        "anclas_snapshot": sorted(anclas_snap),
        "anclas_registro": sorted(anclas_vivas),
        "coinciden": set(anclas_snap) == set(anclas_vivas),
        "motivos_iguales": {
            a: str(anclas_snap.get(a, "")).strip() == str(anclas_vivas.get(a, "")).strip()
            for a in comunes
        },
    }


def reconciliar_contextos(snap: Dict[str, Any]) -> List[Dict[str, Any]]:
    vivos = {c: d for c, d in arch.CONTEXTS.items()}
    filas = []
    for nombre, datos in snap.items():
        if nombre.startswith("_"):
            continue
        vivo = vivos.get(nombre)
        if vivo is None:
            filas.append({"contexto": nombre, "estado": "NO EXISTE en el registro"})
            continue
        puertos_snap = set((datos.get("puertos") or {}).keys())
        puertos_vivos = set(vivo.get("puertos", {}).keys())
        if puertos_snap == puertos_vivos:
            estado = "VIGENTE"
        elif puertos_vivos - puertos_snap:
            estado = "AMPLIADO (puertos publicados en el registro)"
        else:
            estado = "DIVERGENTE"
        filas.append({
            "contexto": nombre,
            "estado": estado,
            "titulo_snapshot": datos.get("titulo", ""),
            "titulo_registro": vivo.get("titulo", ""),
            "puertos_snapshot_n": len(puertos_snap),
            "puertos_registro_n": len(puertos_vivos),
            "modulos_snapshot_n": datos.get("modulos_n"),
            "modulos_registro_n": len(vivo.get("modulos", [])),
            "solo_en_registro": sorted(puertos_vivos - puertos_snap),
            "solo_en_snapshot": sorted(puertos_snap - puertos_vivos),
        })
    return filas


def _divergencias_aceptadas() -> Dict[str, Dict[str, Any]]:
    """Aceptaciones DECLARADAS de divergencias concretas.

    Una entrada solo silencia la divergencia si esta RATIFICADA
    (`ratificado: true`) y declara evidencia. Sin ratificacion, el
    reconciliador se comporta como antes. Es un mecanismo de decision, no un
    apagafuegos: la lista vive en
    `audits/architecture/divergencias-aceptadas.yaml`.
    """
    ruta = (Path(__file__).resolve().parents[2] / "audits" / "architecture" /
            "divergencias-aceptadas.yaml")
    if not ruta.is_file():
        return {}
    try:
        import yaml

        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return {}
    aceptadas: Dict[str, Dict[str, Any]] = {}
    for entrada in datos.get("divergencias") or []:
        if not isinstance(entrada, dict):
            continue
        if not entrada.get("ratificado") or not entrada.get("evidencia"):
            continue
        clave = str(entrada.get("divergencia", "")).strip()
        if clave:
            aceptadas[clave] = entrada
    return aceptadas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", dest="salida", help="fichero JSON de salida")
    ap.add_argument("--check", action="store_true",
                    help="modo comprobacion: sale con codigo distinto de cero si "
                         "queda alguna divergencia NO aceptada (sin tocar "
                         "inventario)")
    args = ap.parse_args()

    snap = _cargar_archify()
    pares = reconciliar_pares(snap)
    deps = reconciliar_dependencias(snap)
    informe = {
        "sha": _sha(),
        "contextos": reconciliar_contextos(snap),
        "pares_de_contexto": pares,
        "dependencias": deps,
        "off_port": reconciliar_off_port(snap),
        "anclas": reconciliar_anclas(snap),
        "invariantes": {
            "contextos": len(arch.CONTEXTS),
            "puertos_totales": sum(len(d["puertos"]) for d in arch.CONTEXTS.values()),
            "presupuesto_cruces": len(arch.PRESUPUESTO_DE_CRUCES),
            "off_port_total": len({arch._clave_fuera_de_puerto(x)
                                   for x in arch.cruces_fuera_de_puerto()}),
            "off_port_baseline": len(arch._leer_baseline().get("off_port_crossings", [])),
        },
    }

    print("== CONTEXTOS (snapshot vs registro)")
    for f in informe["contextos"]:
        print(f"  {f['contexto']:14s} {f['estado']:42s} "
              f"puertos {f.get('puertos_snapshot_n')}->{f.get('puertos_registro_n')} "
              f"modulos {f.get('modulos_snapshot_n')}->{f.get('modulos_registro_n')}")
    print("== PARES DE CONTEXTO (con ficha)")
    print(f"  snapshot={pares['pares_snapshot_n']} registro={pares['pares_registro_n']} "
          f"coincidentes={pares['coincidentes']}")
    for f in pares["fichas"]:
        if f["estado"] != "VIGENTE":
            print(f"  {f['par']} -> {f['estado']}")
            for d in f["diferencias"]:
                print(f"      {d['campo']}: snapshot={d['snapshot']!r} registro={d['registro']!r}")
    for k in ("solo_en_snapshot", "solo_en_registro"):
        for v in pares[k]:
            print(f"    {k}: {v}")
    print("== DEPENDENCIAS (nivel de contexto)")
    print(f"  deps={deps['dependencias_snapshot_n']} pares_snapshot={deps['pares_snapshot_n']} "
          f"sitios_vivos={deps['sitios_vivos_n']} pares_vivos={deps['pares_contexto_vivos_n']} "
          f"vigentes={deps['pares_vigentes']}")
    for f in deps["filas"]:
        if f["estado"] == "VIGENTE":
            continue
        etiqueta = f.get("par") or f.get("dependencia")
        print(f"  {etiqueta} -> {f['estado']}")
        for d in f.get("dependencias_snapshot", []):
            print(f"      {d}")
        if f.get("modulos"):
            print(f"      modulos: {f['modulos']}")
    print("== ACCESOS FUERA DE PUERTO")
    for f in informe["off_port"]:
        print(f"  {f['clave']:56s} {f['estado']}")
    print("== ANCLAS")
    a = informe["anclas"]
    print(f"  snapshot={a['anclas_snapshot']} registro={a['anclas_registro']} "
          f"coinciden={a['coinciden']} motivos_iguales={a['motivos_iguales']}")
    print("== INVARIANTES")
    for k, v in informe["invariantes"].items():
        print(f"  {k}: {v}")

    if args.salida:
        Path(args.salida).write_text(
            json.dumps(informe, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        print(f"\ninforme escrito: {args.salida}")

    if args.check:
        divergencias = []
        for par in pares.get("solo_en_snapshot", []):
            divergencias.append(f"par solo en el snapshot: {par}")
        for par in pares.get("solo_en_registro", []):
            divergencias.append(f"par solo en el registro: {par}")
        for f in pares.get("fichas", []):
            if f.get("estado") != "VIGENTE":
                divergencias.append(f"ficha divergente: {f['par']}")
        for f in recon_off_port(snap):
            if f["estado"] == "NO CONCILIADO":
                divergencias.append(f"acceso no conciliado: {f['clave']}")
        for f in informe["dependencias"]["filas"]:
            if f["estado"] in ("NO CONCILIABLE", "NO NORMALIZABLE"):
                divergencias.append(f"dependencia {f['estado']}: {f.get('dependencia')}")
        if not informe["anclas"].get("coinciden"):
            divergencias.append("las anclas del puente no coinciden")
        print("== MODO CHECK")
        if divergencias:
            aceptadas = _divergencias_aceptadas()
            remanentes = []
            aceptadas_efectivas = []
            for d in divergencias:
                entrada = aceptadas.get(d)
                if entrada is not None:
                    aceptadas_efectivas.append((d, entrada))
                else:
                    remanentes.append(d)
            for d in divergencias:
                entrada = aceptadas.get(d)
                etiqueta = ("ACEPTADA (ratificada)" if entrada is not None
                            else "DIVERGENCIA")
                print(f"  {etiqueta}: {d}")
            for d, entrada in aceptadas_efectivas:
                print(f"    aceptada por: "
                      f"{entrada.get('accion_requerida', 'ratificacion')}")
            if remanentes:
                print(f"\n{len(remanentes)} divergencia(s) no aceptada(s): "
                      "el estado del inventario NO es conforme")
                return 1
            print(f"\n0 divergencia(s) no aceptada(s): el inventario es conforme "
                  f"({len(aceptadas_efectivas)} aceptada(s) por ratificacion)")
            return 0
        print("  sin divergencias no aceptadas: el inventario es conforme")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())