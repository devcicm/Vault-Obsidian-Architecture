#!/usr/bin/env python3
"""Verificador de ACTOS y CUSTODIAS para la propuesta de certificacion
compuesta (DEC-03, PROPUESTA — NO APLICADA al QG-02 de produccion).

ESTADO: PROPUESTA. Corrige los hallazgos preactivacion de los dictamenes
`2369be8` (QA-R18-AUTH-01..04) y `222094f` (QA-R19-AUTH-05..11):

  AUTH-01  Un registro NO ratificado no es fuente: la mera presencia de
           autoridades no pone nada en vigor. El registro esta en vigor solo si
           declara `estado: RATIFICADO` y un ACTO DE RATIFICACION propio que
           cumple el CONTRATO completo (AUTH-07).
  AUTH-02  Identidad de autoridad UNICA: `autoridad` es el identificador
           canonico y `firmante` un alias, normalizados SOLO contra el
           registro (AUTH-08).
  AUTH-03  El texto de un commit no ratifica por resemblance: el acto tiene que
           cumplir un CONTRATO explicito, con estados distinguidos.
  AUTH-04  La custodia es un SEGUNDO acto con contrato propio ( custodio
           DESIGNADO, identidad y canal propios, operaciones y vigencia).
  AUTH-05  Una autoridad registrada NO es custodio: el custodio tiene que
           estar DESIGNADO expresamente (id) en el registro; sin designacion,
           BLOCKED. La lista de autoridades NO se une a la de custodios.
  AUTH-06  Se verifica la identidad y la procedencia de QUIEN FIRMA el acta
           de custodia (el custodio), no las de la autoridad que decidio. Si
           hay delegacion, exige un acto verificable y un alcance concreto.
  AUTH-07  La ratificacion del registro exige el acta completa: ACTO:
           RATIFICACION, ACCION: RATIFICAR, ESTADO: RATIFICADO, OBJETO,
           VERSION, FECHA y CANAL coincidentes con lo declarado, e identidad
           del ratificador.
  AUTH-08  Los alias legitimos se normalizan contra el registro; un alias
           libre, ambiguo o de otra autoridad se rechaza. La comparacion
           cruda de cadenas se hace en el verificador, no en el esquema.
  AUTH-09  Vigencia temporal completa: `inicio <= fecha de evaluacion <= fin`,
           fechas ISO reales y `inicio <= fin`.
  AUTH-10  Un acta con campos obligatorios DUPLICADOS o contradictorios se
           rechaza, aunque la primera ocurrencia sea valida.
  AUTH-11  REVOCACION: un acto ratificado y luego revocado por un acto
           posterior del canal deja de acreditar (ratificacion -> revocacion
           -> BLOCKED). La fuente de revocaciones es el canal declarado de la
           autoridad: su integridad es el MISMO control administrativo que el
           canal, y su incorporacion al contrato del release depende de
           DEC-03 (no se improvisa autoridad).

FUENTE CONFIABLE (la define el propietario en DEC-03):

  1. REGISTRO (`autoridades-de-decision.yaml`): autoridades con su canal y su
     identidad, CUSTODIOS DESIGNADOS con su identidad y canal, y su propio
     acto de ratificacion.
  2. REPOSITORIO: los actos existen como commits, son alcanzables desde su
     canal y su contenido cumple el contrato.
  3. SIN registro ratificado, SIN canal declarado o SIN fuente: no hay
     acreditacion y el veredicto es BLOCKED.

LIMIT HONESTO (no se vende mas de lo que es): en este repositorio el
ejecutor y el propietario comparten identidad git y permisos de push, asi que
el canal es un control ADMINISTRATIVO (lo declara y lo vigila el
propietario), no criptografico. Este verificador acredita que EXISTE un acto
verificable en la fuente declarada; que ese acto emane del propietario
depende de la integridad del canal — una decision del propietario (DEC-03/
DEC-04) que sigue PENDIENTE. El mecanismo recomendado para separarlos
(canal protegido, identidad verificable, reglas de custodia) esta descrito en
el buzon del ejecutor (ronda R20) y NO se configura aqui.
"""
from __future__ import annotations

import datetime
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
FECHA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REGISTRO_EN_VIGOR = "RATIFICADO"
#: Estados de un acto, distinguidos de forma inequivoca.
ESTADOS_ACTO = ("PROPUESTO", "CONSULTADO", "RATIFICADO", "RECHAZADO", "REVOCADO")
#: Acciones que NO ratifican (el acto consultivo mas explicito del mundo).
ACCIONES_QUE_NO_RATIFICAN = ("PROPONER", "CONSULTAR", "INFORMAR", "RECHAZAR",
                              "REVOCAR", "PROPONE", "CONSULTA")
#: Operaciones que una custodia NO puede autorizar por si misma (DEC-04).
OPERACIONES_DESTRUCTIVAS = ("archivar", "trasladar", "purgar", "eliminar",
                             "mover", "borrar", "comprimir")
#: Valores de `estado` que habilitan un registro.
ESTADOS_REGISTRO_VALIDOS = (REGISTRO_EN_VIGOR,)
#: Campos de un acta que aparecen como mucho una vez.
CAMPOS_UNICOS = ("ACTO", "ACCION", "ESTADO", "DECISION", "AUTORIDAD", "ALCANCE",
                 "RESIDUO", "NORMA", "RUTA", "HUELLA", "FECHA", "CANAL",
                 "OBJETO", "VERSION", "CUSTODIO", "ACTID", "OPERACIONES",
                 "VIGENCIA", "REVOCA", "DELEGANTE", "DELEGADO")


def _hoy() -> datetime.date:
    return datetime.date.today()


def _fecha(valor: str) -> Optional[datetime.date]:
    if not isinstance(valor, str) or not FECHA_RE.match(valor):
        return None
    try:
        return datetime.date.fromisoformat(valor)
    except ValueError:
        return None


class VerificadorActosGit:
    """Verifica actos y custodias contra un repositorio y un registro."""

    def __init__(self, raiz: Path, registro: Dict[str, Any]):
        self.raiz = Path(raiz)
        self.registro = registro if isinstance(registro, dict) else {}
        self.autoridades = self._mapa(self.registro.get("autoridades"))
        self.custodios = self._mapa(self.registro.get("custodios"))
        self.motivos_no_vigor: List[str] = []
        self._evaluar_vigor()

    @staticmethod
    def _mapa(datos: Any) -> Dict[str, Any]:
        """Normaliza a mapa `id -> datos` desde mapa o lista de entradas."""
        if isinstance(datos, dict):
            return {str(k): v for k, v in datos.items() if isinstance(v, dict)}
        mapa: Dict[str, Any] = {}
        if isinstance(datos, list):
            for entrada in datos:
                if isinstance(entrada, dict) and entrada.get("id"):
                    mapa[str(entrada["id"])] = entrada
        return mapa

    # ── git ──────────────────────────────────────────────────────────────
    def _git(self, *args: str) -> Tuple[int, str]:
        p = subprocess.run(["git", *args], cwd=str(self.raiz),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        return p.returncode, (p.stdout or "").strip()

    def _existe_commit(self, sha: str) -> bool:
        if not SHA_RE.match(sha or ""):
            return False
        rc, _ = self._git("cat-file", "-e", f"{sha}^{{commit}}")
        return rc == 0

    def _alcanzable_desde(self, sha: str, refs: Iterable[str]) -> bool:
        for ref in refs:
            rc, _ = self._git("merge-base", "--is-ancestor", sha, ref)
            if rc == 0:
                return True
        return False

    def _mensaje(self, sha: str) -> str:
        rc, salida = self._git("show", "-s", "--format=%B", sha)
        return salida if rc == 0 else ""

    def _autor_de(self, sha: str) -> str:
        rc, autor = self._git("show", "-s", "--format=%an <%ae>", sha)
        return autor if rc == 0 else ""

    # ── parsing del acta ─────────────────────────────────────────────────
    @staticmethod
    def _campos(mensaje: str) -> Dict[str, List[str]]:
        """Extrae `CLAVE: valor` del mensaje del commit (claves en mayusculas)."""
        campos: Dict[str, List[str]] = {}
        for linea in mensaje.splitlines():
            if ":" not in linea:
                continue
            clave, _, valor = linea.partition(":")
            clave = clave.strip().upper()
            valor = valor.strip()
            if clave and valor and len(clave) <= 32:
                campos.setdefault(clave, []).append(valor)
        return campos

    def _exige(self, campos: Dict[str, List[str]], clave: str) -> Tuple[bool, str, str]:
        """Valor de un campo OBLIGATORIO, exigiendo unicidad (AUTH-10).

        Devuelve (ok, valor, motivo): el motivo distingue "falta" de
        "aparece dos veces", y los dos son rechazos.
        """
        valores = campos.get(clave) or []
        if not valores:
            return (False, "", f"ACTO_SIN_{clave}: el acta no declara {clave}")
        if len(valores) > 1:
            return (False, "", f"ACTO_CAMPO_DUPLICADO: {clave} aparece "
                               f"{len(valores)} veces ({valores!r}); un acta no "
                               "declara dos veces el mismo campo")
        return (True, valores[0], "")

    # ── vigencia del registro (AUTH-01, AUTH-07) ─────────────────────────
    def _evaluar_vigor(self) -> None:
        motivos: List[str] = []
        estado = str(self.registro.get("estado") or "")
        if estado not in ESTADOS_REGISTRO_VALIDOS:
            motivos.append(
                f"REGISTRO_NO_RATIFICADO: estado={estado!r}; en vigor solo con "
                f"{REGISTRO_EN_VIGOR!r} (DRAFT/PROPUESTA/PENDING/desconocidos "
                "se rechazan)")
        ratificacion = self.registro.get("ratificacion")
        if not isinstance(ratificacion, dict) or not ratificacion:
            motivos.append("REGISTRO_SIN_ACTO_DE_RATIFICACION")
            self.motivos_no_vigor = motivos
            return
        acto = str(ratificacion.get("acto") or "")
        canal = str(ratificacion.get("canal") or "")
        fecha = str(ratificacion.get("fecha") or "")
        por = str(ratificacion.get("ratificado_por") or "")
        if not SHA_RE.match(acto):
            motivos.append("REGISTRO_ACTO_INVALIDO: el acta de ratificacion no es un SHA")
        if not canal:
            motivos.append("REGISTRO_SIN_CANAL")
        if _fecha(fecha) is None:
            motivos.append("REGISTRO_SIN_FECHA")
        if not por:
            motivos.append("REGISTRO_SIN_RATIFICADO_POR")
        if motivos:
            self.motivos_no_vigor = motivos
            return
        if not self._existe_commit(acto):
            motivos.append("REGISTRO_ACTO_INEXISTENTE: el acta de ratificacion no existe")
            self.motivos_no_vigor = motivos
            return
        if not self._alcanzable_desde(acto, [canal]):
            motivos.append(
                "REGISTRO_ACTO_AJENO: el acta de ratificacion no es alcanzable "
                "desde el canal declarado")
            self.motivos_no_vigor = motivos
            return
        campos = self._campos(self._mensaje(acto))
        # AUTH-07: el acta tiene que cumplir el CONTRATO COMPLETO.
        ok, valor, motivo = self._exige(campos, "ACTO")
        if not ok:
            motivos.append(f"REGISTRO_ACTO_INVALIDO: {motivo}")
        elif valor.upper() != "RATIFICACION":
            motivos.append(
                f"REGISTRO_ACTO_INVALIDO: el acta no declara ACTO: RATIFICACION ({valor!r})")
        ok, valor_accion, motivo = self._exige(campos, "ACCION")
        if not ok:
            motivos.append(f"REGISTRO_ACTO_NO_RATIFICA: {motivo}")
        elif valor_accion.upper() != "RATIFICAR":
            motivos.append(
                "REGISTRO_ACTO_NO_RATIFICA: el acta no declara ACCION: RATIFICAR")
        ok, valor_estado, motivo = self._exige(campos, "ESTADO")
        if not ok:
            motivos.append(f"REGISTRO_ACTO_NO_RATIFICADO: {motivo}")
        elif valor_estado.upper() != REGISTRO_EN_VIGOR:
            motivos.append(
                f"REGISTRO_ACTO_NO_RATIFICADO: el acta declara ESTADO {valor_estado!r}")
        ok, valor_objeto, motivo = self._exige(campos, "OBJETO")
        if not ok:
            motivos.append(f"REGISTRO_ACTO_NO_RATIFICA_EL_REGISTRO: {motivo}")
        elif valor_objeto != str(self.registro.get("id") or ""):
            motivos.append(
                "REGISTRO_ACTO_NO_RATIFICA_EL_REGISTRO: el acta no nombra el "
                "identificador de este registro")
        ok, valor_version, motivo = self._exige(campos, "VERSION")
        if not ok:
            motivos.append(f"REGISTRO_ACTO_NO_RATIFICA_EL_REGISTRO: {motivo}")
        elif valor_version != str(self.registro.get("version") or ""):
            motivos.append(
                "REGISTRO_ACTO_NO_RATIFICA_EL_REGISTRO: el acta no nombra la "
                "version de este registro")
        ok, valor_fecha, motivo = self._exige(campos, "FECHA")
        if not ok:
            motivos.append(f"REGISTRO_ACTO_SIN_FECHA: {motivo}")
        elif valor_fecha != fecha:
            motivos.append(
                f"REGISTRO_ACTO_FECHA_CONTRADICTORIA: el acta declara "
                f"{valor_fecha!r} y el registro {fecha!r}")
        ok, valor_canal, motivo = self._exige(campos, "CANAL")
        if not ok:
            motivos.append(f"REGISTRO_ACTO_SIN_CANAL: {motivo}")
        elif valor_canal != canal:
            motivos.append(
                f"REGISTRO_ACTO_CANAL_CONTRADICTORIO: el acta declara "
                f"{valor_canal!r} y el registro {canal!r}")
        autor = self._autor_de(acto)
        if por not in autor:
            motivos.append(
                f"REGISTRO_RATIFICADO_POR_OTRO: el acta esta firmada por "
                f"{autor!r} y el registro declara {por!r}")
        self.motivos_no_vigor = motivos

    def en_vigor(self) -> bool:
        return not self.motivos_no_vigor

    def motivos_vigor(self) -> List[str]:
        return list(self.motivos_no_vigor)

    # ── autoridades y aliases (AUTH-02, AUTH-08) ─────────────────────────
    def _canales_de(self, autoridad: str) -> List[str]:
        datos = self.autoridades.get(autoridad)
        if not isinstance(datos, dict):
            return []
        return [str(c) for c in (datos.get("canales") or []) if str(c).strip()]

    def _alias_ambiguos(self) -> Dict[str, List[str]]:
        """Un alias declarado por DOS autoridades es ambiguo: se rechaza."""
        tabla: Dict[str, List[str]] = {}
        for id_autoridad, datos in self.autoridades.items():
            if not isinstance(datos, dict):
                continue
            for alias in (datos.get("alias") or []):
                tabla.setdefault(str(alias), []).append(id_autoridad)
        return {alias: ids for alias, ids in tabla.items() if len(ids) > 1}

    def _resuelve_autoridad(self, decision: Dict[str, Any]) -> Tuple[Optional[str], List[str]]:
        """Identificador CANONICO de la autoridad de una decision.

        `autoridad` es el canonico; `firmante` es un alias. Los dos se
        normalizan SOLO contra el registro: un alias libre no es autoridad y
        un alias de otra autoridad no es la misma.
        """
        motivos: List[str] = []
        canonico = str(decision.get("autoridad") or "").strip()
        alias = str(decision.get("firmante") or "").strip()
        if not canonico and not alias:
            return (None, ["AUTORIDAD_AUSENTE"])
        ambiguos = self._alias_ambiguos()
        resueltos: List[str] = []
        for etiqueta, candidato in (("autoridad", canonico), ("firmante", alias)):
            if not candidato:
                continue
            if candidato in self.autoridades:
                resueltos.append(candidato)
                continue
            if candidato in ambiguos:
                motivos.append(
                    f"ALIAS_AMBIGUO: {candidato!r} ({etiqueta}) lo declaran "
                    f"varias autoridades {ambiguos[candidato]}")
                continue
            resuelto = None
            for id_autoridad, datos in self.autoridades.items():
                if isinstance(datos, dict) and candidato in [str(a) for a in (datos.get("alias") or [])]:
                    resuelto = id_autoridad
                    break
            if resuelto is None:
                motivos.append(
                    f"AUTORIDAD_DESCONOCIDA: {candidato!r} ({etiqueta}) no consta "
                    "en el registro ni es alias de ninguna autoridad")
            else:
                resueltos.append(resuelto)
        if motivos:
            return (None, motivos)
        if len(set(resueltos)) > 1:
            motivos.append(
                f"IDENTIDADES_CONTRADICTORIAS: la decision declara dos "
                f"autoridades que no son la misma ({resueltos})")
            return (None, motivos)
        return (resueltos[0], [])

    def _identidad_coincide(self, autoridad: str, sha: str,
                            identidad: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """La identidad declarada debe ser la del commit.

        En este repositorio la identidad git es compartida por ejecutor y
        propietario, asi que esto NO basta para autorizar: por eso el
        verificador exige ademas canal y contenido.
        """
        if identidad is None:
            datos = self.autoridades.get(autoridad) or {}
            identidad = datos.get("identidad_git") or {}
        if not isinstance(identidad, dict) or not identidad:
            return (True, "")
        esperado = str(identidad.get("correo") or "").strip()
        if not esperado:
            return (True, "")
        autor = self._autor_de(sha)
        if not autor:
            return (False, "IDENTIDAD_ILEGIBLE")
        if esperado not in autor:
            return (False,
                    f"IDENTIDAD_INCOMPATIBLE_CON_EL_CANAL: el acto no esta "
                    f"firmado por {esperado}")
        return (True, "")

    # ── revocacion (AUTH-11) ─────────────────────────────────────────────
    def _revocaciones(self, autoridad: str) -> List[Tuple[str, Dict[str, List[str]]]]:
        """Actos de revocacion del canal de la autoridad.

        Fuente: el canal declarado de la autoridad. La INTEGRIDAD de esa fuente
        es el mismo control administrativo que el canal (DEC-03 pendiente): no
        es una prueba criptografica de voluntad del dueno.
        """
        canales = self._canales_de(autoridad)
        if not canales:
            return []
        encontrados: List[Tuple[str, Dict[str, List[str]]]] = []
        vistos = set()
        for ref in canales:
            rc, salida = self._git("log", "--format=%H", ref)
            if rc != 0:
                continue
            for sha in salida.splitlines():
                sha = sha.strip()
                if not SHA_RE.match(sha) or sha in vistos:
                    continue
                vistos.add(sha)
                campos = self._campos(self._mensaje(sha))
                valores = [v.upper() for v in (campos.get("ACTO") or [])]
                acciones = [v.upper() for v in (campos.get("ACCION") or [])]
                if "REVOCACION" in valores and "REVOCAR" in acciones:
                    encontrados.append((sha, campos))
        return encontrados

    def _esta_revocado(self, referencia: str, autoridad: str) -> Optional[str]:
        for sha, campos in self._revocaciones(autoridad):
            valores = campos.get("REVOCA") or []
            if referencia in valores:
                return sha
        return None

    # ── contrato de acto (AUTH-03) ───────────────────────────────────────
    def _valida_contrato_acto(self, campos: Dict[str, List[str]], decision: Dict[str, Any],
                              hallazgo: Dict[str, Any], autoridad: str,
                              canales: List[str]) -> List[str]:
        motivos: List[str] = []
        ok, valor, motivo = self._exige(campos, "ACTO")
        if not ok:
            motivos.append(motivo)
        elif valor.upper() != "RATIFICACION":
            motivos.append(f"ACTO_TIPO_INVALIDO: {valor!r} (se exige RATIFICACION)")
        ok, valor_accion, motivo = self._exige(campos, "ACCION")
        if not ok:
            motivos.append(motivo)
        elif valor_accion.upper() in ACCIONES_QUE_NO_RATIFICAN:
            motivos.append(
                f"ACTO_NO_RATIFICA: la accion {valor_accion!r} no es una "
                "ratificacion expresa")
        elif valor_accion.upper() != "RATIFICAR":
            motivos.append(
                f"ACTO_ACCION_INVALIDA: {valor_accion!r} (se exige RATIFICAR)")
        ok, valor_estado, motivo = self._exige(campos, "ESTADO")
        if not ok:
            motivos.append(motivo)
        elif valor_estado.upper() != REGISTRO_EN_VIGOR:
            motivos.append(
                f"ACTO_ESTADO_NO_RATIFICADO: {valor_estado.upper()!r} "
                f"(valores distinguidos: {', '.join(ESTADOS_ACTO)})")
        for clave, esperado in (("DECISION", str(decision.get("id") or "")),
                                ("AUTORIDAD", autoridad),
                                ("ALCANCE", str(hallazgo.get("id") or "")),
                                ("RESIDUO", str(hallazgo.get("id") or "")),
                                ("NORMA", str(hallazgo.get("norm") or "")),
                                ("RUTA", str(hallazgo.get("path") or "")),
                                ("HUELLA", str(hallazgo.get("huella") or "")),
                                ("FECHA", str(decision.get("fecha") or ""))):
            ok, valor, motivo = self._exige(campos, clave)
            if not ok:
                motivos.append(motivo)
            elif valor != esperado:
                motivos.append(
                    f"ACTO_ALCANCE_NO_COINCIDE: {clave} del acta ({valor!r}) no "
                    f"es el declarado ({esperado!r})")
        ok, valor_canal, motivo = self._exige(campos, "CANAL")
        if not ok:
            motivos.append(motivo)
        elif valor_canal not in canales:
            motivos.append(
                f"ACTO_CANAL_NO_DECLARADO: {valor_canal!r} no es un canal de "
                f"{autoridad}")
        return motivos

    def verificar_acto(self, decision: Dict[str, Any],
                        hallazgo: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """El acto de ratificacion: existe, es del canal, no esta revocado y
        cumple el CONTRATO de ratificacion expresa."""
        motivos: List[str] = []
        if not self.en_vigor():
            return (False, [f"REGISTRO_NO_EN_VIGOR: {m}"
                            for m in self.motivos_no_vigor])
        autoridad, motivos_auth = self._resuelve_autoridad(decision)
        if autoridad is None:
            return (False, motivos_auth)
        canales = self._canales_de(autoridad)
        if not canales:
            return (False, [f"AUTORIDAD_SIN_CANAL: {autoridad} no declara canal"])
        referencia = str(decision.get("referencia") or "")
        if not self._existe_commit(referencia):
            return (False, [f"ACTO_INEXISTENTE: {referencia!r} no es un commit"])
        if not self._alcanzable_desde(referencia, canales):
            return (False, ["ACTO_AJENO: no es alcanzable desde el canal declarado"])
        ok_id, motivo_id = self._identidad_coincide(autoridad, referencia)
        if not ok_id:
            motivos.append(motivo_id)
        # AUTH-11: un acto ratificado y despues revocado deja de acreditar.
        revocacion = self._esta_revocado(referencia, autoridad)
        if revocacion:
            motivos.append(
                f"ACTO_REVOCADO: el acto {referencia[:12]}… fue revocado por "
                f"{revocacion[:12]}… en el canal de {autoridad}")
        campos = self._campos(self._mensaje(referencia))
        motivos.extend(self._valida_contrato_acto(campos, decision, hallazgo,
                                                  autoridad, canales))
        return (not motivos, motivos)

    # ── contrato de custodia (AUTH-04..06, AUTH-09) ─────────────────────
    def _custodio_designado(self, custodio: str) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        """El custodio tiene que estar DESIGNADO expresamente (AUTH-05).

        Una autoridad registrada NO es custodio: la lista de autoridades no se
        une a la de custodios. Sin designacion, BLOCKED.
        """
        if not custodio:
            return (None, ["CUSTODIA_SIN_CUSTODIO"])
        datos = self.custodios.get(custodio)
        if not isinstance(datos, dict):
            return (None, [
                f"CUSTODIO_NO_DESIGNADO: {custodio!r} no esta designado como "
                "custodio en el registro (una autoridad registrada no lo es "
                "por el hecho de estar registrada)"])
        return (datos, [])

    def _canales_del_custodio(self, custodio: str, datos: Dict[str, Any]) -> List[str]:
        canales = [str(c) for c in (datos.get("canales") or []) if str(c).strip()]
        delegacion = datos.get("delega")
        if isinstance(delegacion, dict):
            canales += [str(c) for c in (delegacion.get("canales") or []) if str(c).strip()]
        return canales

    def _delega_verificada(self, custodio: str, datos: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Si el custodio actua por delegacion, el acto de delegacion tiene que
        ser verificable y con alcance concreto (AUTH-06)."""
        delegacion = datos.get("delega")
        if not isinstance(delegacion, dict):
            return (True, [])
        motivos: List[str] = []
        acto = str(delegacion.get("acto") or "")
        if not SHA_RE.match(acto):
            return (False, ["DELEGACION_SIN_ACTO"])
        if not self._existe_commit(acto):
            return (False, ["DELEGACION_ACTO_INEXISTENTE"])
        campos = self._campos(self._mensaje(acto))
        ok, valor, motivo = self._exige(campos, "ACTO")
        if not ok:
            motivos.append(motivo)
        elif valor.upper() != "DELEGACION":
            motivos.append("DELEGACION_ACTO_INVALIDO: el acta no declara ACTO: DELEGACION")
        ok, valor_accion, motivo = self._exige(campos, "ACCION")
        if not ok:
            motivos.append(motivo)
        elif valor_accion.upper() != "DELEGAR":
            motivos.append("DELEGACION_ACCION_INVALIDA")
        ok, valor_delegante, motivo = self._exige(campos, "DELEGANTE")
        if not ok:
            motivos.append(motivo)
        elif valor_delegante != str(delegacion.get("de") or ""):
            motivos.append("DELEGACION_DELEGANTE_NO_COINCIDE")
        ok, valor_delegado, motivo = self._exige(campos, "DELEGADO")
        if not ok:
            motivos.append(motivo)
        elif valor_delegado != custodio:
            motivos.append("DELEGACION_DELEGADO_NO_COINCIDE")
        if not (campos.get("ALCANCE") or []):
            motivos.append("DELEGACION_SIN_ALCANCE: la delegacion no declara alcance")
        return (not motivos, motivos)

    def _valida_contrato_custodia(self, campos: Dict[str, List[str]], decision: Dict[str, Any],
                                  hallazgo: Dict[str, Any], custodio: str,
                                  custodio_datos: Dict[str, Any],
                                  canales: List[str]) -> List[str]:
        motivos: List[str] = []
        ok, valor, motivo = self._exige(campos, "ACTO")
        if not ok:
            motivos.append(motivo)
        elif valor.upper() != "CUSTODIA":
            motivos.append(f"CUSTODIA_TIPO_INVALIDO: {valor!r} (se exige CUSTODIA)")
        ok, valor_accion, motivo = self._exige(campos, "ACCION")
        if not ok:
            motivos.append(motivo)
        elif valor_accion.upper() != "CUSTODIAR":
            motivos.append(
                f"CUSTODIA_ACCION_INVALIDA: {valor_accion!r} (se exige CUSTODIAR)")
        ok, valor_estado, motivo = self._exige(campos, "ESTADO")
        if not ok:
            motivos.append(motivo)
        elif valor_estado.upper() not in ("VIGENTE", REGISTRO_EN_VIGOR):
            motivos.append(f"CUSTODIA_ESTADO_INVALIDO: {valor_estado!r}")
        custodia = decision.get("custodia") or {}
        for clave, esperado in (("ACTID", str(custodia.get("id") or "")),
                                ("RESIDUO", str(hallazgo.get("id") or "")),
                                ("NORMA", str(hallazgo.get("norm") or "")),
                                ("RUTA", str(hallazgo.get("path") or "")),
                                ("HUELLA", str(hallazgo.get("huella") or ""))):
            ok, valor_campo, motivo = self._exige(campos, clave)
            if not ok:
                motivos.append(motivo)
            elif valor_campo != esperado:
                motivos.append(
                    f"CUSTODIA_ALCANCE_NO_COINCIDE: {clave} del acta "
                    f"({valor_campo!r}) no es el declarado ({esperado!r})")
        # operaciones: una custodia NO autoriza archivar/trasladar/purgar
        operaciones = [o.strip().lower() for o in (campos.get("OPERACIONES") or [])]
        if not operaciones:
            motivos.append("CUSTODIA_SIN_OPERACIONES")
        destructivas = [o for o in operaciones
                        if any(d in o for d in OPERACIONES_DESTRUCTIVAS)]
        if destructivas:
            motivos.append(
                "CUSTODIA_NO_AUTORIZA_OPERACIONES_DESTRUCTIVAS: "
                f"{destructivas} requieren actos independientes (DEC-04)")
        # AUTH-09: vigencia completa (inicio <= hoy <= fin, fechas reales)
        ok, vigencia, motivo = self._exige(campos, "VIGENCIA")
        if not ok:
            motivos.append(motivo)
        else:
            partes = [p.strip() for p in str(vigencia).replace(" ", "").split("/")]
            if len(partes) != 2:
                motivos.append(
                    f"CUSTODIA_VIGENCIA_INVALIDA: {vigencia!r} (se exige "
                    "inicio/fin)")
            else:
                inicio = _fecha(partes[0])
                fin = _fecha(partes[1])
                if inicio is None or fin is None:
                    motivos.append(
                        f"CUSTODIA_VIGENCIA_INVALIDA: {vigencia!r} (fechas ISO reales)")
                elif inicio > fin:
                    motivos.append(
                        f"CUSTODIA_VIGENCIA_INVERTIDA: inicio {inicio} posterior a "
                        f"fin {fin}")
                elif inicio > _hoy():
                    motivos.append(
                        f"CUSTODIA_VIGENCIA_FUTURA: la custodia no empieza hasta "
                        f"{inicio}")
                elif fin < _hoy():
                    motivos.append(
                        f"CUSTODIA_EXPIRADA: la vigencia termina el {fin}")
        ok, valor_canal, motivo = self._exige(campos, "CANAL")
        if not ok:
            motivos.append(motivo)
        elif valor_canal not in canales:
            motivos.append(
                f"CUSTODIA_CANAL_NO_DECLARADO: {valor_canal!r} no es un canal de "
                f"la custodia")
        return motivos

    def verificar_custodia(self, decision: Dict[str, Any],
                            hallazgo: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """La custodia: SEGUNDO acto, con custodio DESIGNADO que lo firma, y
        sin alcanzar para archivar, trasladar ni purgar."""
        motivos: List[str] = []
        if not self.en_vigor():
            return (False, [f"REGISTRO_NO_EN_VIGOR: {m}"
                            for m in self.motivos_no_vigor])
        autoridad, motivos_auth = self._resuelve_autoridad(decision)
        if autoridad is None:
            return (False, motivos_auth)
        custodia = decision.get("custodia") or {}
        referencia = str(custodia.get("referencia") or "")
        if not SHA_RE.match(referencia):
            return (False, ["CUSTODIA_SIN_REFERENCIA_VERIFICABLE"])
        if referencia == str(decision.get("referencia") or ""):
            return (False, [
                "CUSTODIA_AUTOAFIRMADA: el acta de custodia es el propio acto "
                "de la decision (no es una verificacion independiente)"])
        if not self._existe_commit(referencia):
            return (False, [f"CUSTODIA_INEXISTENTE: {referencia!r} no es un commit"])
        campos = self._campos(self._mensaje(referencia))
        ok_custodio, custodio, motivo_custodio = self._exige(campos, "CUSTODIO")
        if not ok_custodio:
            return (False, [motivo_custodio])
        datos, motivos_designacion = self._custodio_designado(custodio)
        if datos is None:
            return (False, motivos_designacion)
        # AUTH-06: la identidad y la procedencia son del CUSTODIO que firma.
        identidad = datos.get("identidad_git") or {}
        if not identidad:
            motivos.append(
                "CUSTODIO_SIN_IDENTIDAD_DECLARADA: el custodio designado no "
                "declara identidad, asi que no se puede comprobar quien firma "
                "el acta (el registro debe declararla)")
        else:
            ok_id, motivo_id = self._identidad_coincide("", referencia, identidad)
            if not ok_id:
                motivos.append(motivo_id)
        canales = self._canales_del_custodio(custodio, datos)
        if not canales:
            return (False, [f"CUSTODIO_SIN_CANAL: {custodio} no declara canal"])
        if not self._alcanzable_desde(referencia, canales):
            motivos.append(
                "CUSTODIA_AJENA: el acta de custodia no es alcanzable desde el "
                "canal del custodio")
        ok_delegacion, motivos_delegacion = self._delega_verificada(custodio, datos)
        if not ok_delegacion:
            motivos.extend(motivos_delegacion)
        motivos.extend(self._valida_contrato_custodia(
            campos, decision, hallazgo, custodio, datos, canales))
        return (not motivos, motivos)


def cargar_registro(ruta: Path) -> Dict[str, Any]:
    """Lee el registro de autoridades (PROPUESTA).

    Acepta las dos formas de declaracion: mapa `id -> datos` (la que consume
    el verificador) o lista de entradas con `id` (mas legible en YAML), que se
    normaliza al mapa. Devuelve la CONFIGURACION CARGADA, no la vigente: la
    vigencia la evalua `VerificadorActosGit` (AUTH-01).
    """
    import yaml

    datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8")) or {}
    if not isinstance(datos, dict):
        return {}
    for clave in ("autoridades", "custodios"):
        entradas = datos.get(clave)
        if isinstance(entradas, list):
            mapa: Dict[str, Any] = {}
            for entrada in entradas:
                if isinstance(entrada, dict) and entrada.get("id"):
                    mapa[str(entrada["id"])] = entrada
            datos = {**datos, clave: mapa}
    return datos


def registro_en_vigor(registro: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Comprobacion ESTRUCTURAL de la vigencia (sin tocar git).

    Un registro no ratificado (DRAFT/PROPUESTA/PENDING/desconocido) o sin
    acto de ratificacion declarado NO esta en vigor: la mera presencia de
    autoridades no constituye puesta en vigor.
    """
    motivos: List[str] = []
    if not isinstance(registro, dict):
        return (False, ["REGISTRO_AUSENTE"])
    estado = str(registro.get("estado") or "")
    if estado not in ESTADOS_REGISTRO_VALIDOS:
        motivos.append(
            f"REGISTRO_NO_RATIFICADO: estado={estado!r}; en vigor solo con "
            f"{REGISTRO_EN_VIGOR!r}")
    ratificacion = registro.get("ratificacion")
    if not isinstance(ratificacion, dict) or not ratificacion:
        motivos.append("REGISTRO_SIN_ACTO_DE_RATIFICACION")
    else:
        if not SHA_RE.match(str(ratificacion.get("acto") or "")):
            motivos.append("REGISTRO_ACTO_INVALIDO")
        if not str(ratificacion.get("canal") or "").strip():
            motivos.append("REGISTRO_SIN_CANAL")
        if _fecha(str(ratificacion.get("fecha") or "")) is None:
            motivos.append("REGISTRO_SIN_FECHA")
        if not str(ratificacion.get("ratificado_por") or "").strip():
            motivos.append("REGISTRO_SIN_RATIFICADO_POR")
    return (not motivos, motivos)


def verificador_desde_registro(raiz: Path, registro: Dict[str, Any]
                               ) -> Optional[VerificadorActosGit]:
    """Construye el verificador SOLO si el registro esta EN VIGOR.

    Sin ratificacion efectiva (AUTH-01) se devuelve None y el evaluador
    BLOCKED: un registro propuesto nunca acredita un PASS.
    """
    if not isinstance(registro, dict):
        return None
    en_vigor, _ = registro_en_vigor(registro)
    if not en_vigor:
        return None
    verificador = VerificadorActosGit(raiz, registro)
    if not verificador.en_vigor():
        return None
    return verificador
