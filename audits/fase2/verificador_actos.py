#!/usr/bin/env python3
"""Verificador de ACTOS y CUSTODIAS para la propuesta de certificacion
compuesta (DEC-03, PROPUESTA — NO APLICADA al QG-02 de produccion).

ESTADO: PROPUESTA. Corrige los cuatro defectos preactivacion del dictamen
`2369be8` (QA-R18-AUTH-01..04):

  AUTH-01  Un registro NO ratificado no es fuente: la mera presencia de
           autoridades no pone nada en vigor. El registro esta en vigor solo si
           declara `estado: RATIFICADO` y un ACTO DE RATIFICACION propio
           (existente, alcanzable por el canal declarado, con intencion
           expresa y con la identidad del ratificador). Un registro
           `PROPUESTA`/`DRAFT`/`PENDING` se rechaza, y el registro no puede
           autoactivarse: su ratificacion es un acto externo, con contenido
           y autor comprobables.
  AUTH-02  Identidad de autoridad UNICA: `autoridad` es el identificador
           canonico y `firmante` es un alias. Si aparecen ambos, tienen que
           resolver a la MISMA autoridad registrada; si discrepan, se
           rechaza. Un alias libre no es autoridad.
  AUTH-03  El texto de un commit no ratifica por resemblance: el acto tiene
           que cumplir un CONTRATO explicito (tipo, accion expresa, estado,
           decision, autoridad, alcance, residuo, norma, ruta, huella, fecha,
           commit y canal). Un documento consultivo que mencione todos los
           datos pero no RATIFIQUE expresamente devuelve BLOCKED.
  AUTH-04  La custodia es un SEGUNDO acto con contrato propio (custodio,
           autoridad, id, residuo, norma, ruta, huella, operaciones
           autorizadas, vigencia, canal y commit) y su autorizacion NO
           alcanza para archivar, trasladar ni purgar: esas operaciones
           exigen actos independientes (DEC-04).

FUENTE CONFIABLE (la define el propietario en DEC-03):

  1. REGISTRO (`autoridades-de-decision.yaml`): autoridades con su canal y
     su identidad, custodios admitidos, y su propio acto de ratificacion.
  2. REPOSITORIO: los actos existen como commits, son alcanzables desde su
     canal y su contenido cumple el contrato.
  3. SIN registro ratificado, SIN canal declarado o SIN fuente: no hay
     acreditacion y el veredicto es BLOCKED.

LIMIT HONESTO (no se vende mas de lo que es): en este repositorio el
ejecutor y el propietario comparten identidad git y permisos de push, asi que
el canal es un control ADMINISTRATIVO (lo declara y lo vigila el
propietario), no criptografico. Este verificador acredita que EXISTE un acto
verificable en la fuente declarada; que ese acto emane del propietario
depende de la integridad del canal — una decision del propietario (DEC-03).
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
#: Acciones que NO ratifican (el acto consultativo mas explicito del mundo).
ACCIONES_QUE_NO_RATIFICAN = ("PROPONER", "CONSULTAR", "INFORMAR", "RECHAZAR",
                              "REVOCAR", "PROPONE", "CONSULTA")
#: Operaciones que una custodia NO puede autorizar por si misma (DEC-04).
OPERACIONES_DESTRUCTIVAS = ("archivar", "trasladar", "purgar", "eliminar",
                             "mover", "borrar", "comprimir")
#: Valores de `estado` que habilitan un registro.
ESTADOS_REGISTRO_VALIDOS = (REGISTRO_EN_VIGOR,)


class VerificadorActosGit:
    """Verifica actos y custodias contra un repositorio y un registro."""

    def __init__(self, raiz: Path, registro: Dict[str, Any]):
        self.raiz = Path(raiz)
        self.registro = registro if isinstance(registro, dict) else {}
        autoridades = self.registro.get("autoridades")
        self.autoridades = autoridades if isinstance(autoridades, dict) else {}
        self.custodios = self.registro.get("custodios") or []
        if not isinstance(self.custodios, list):
            self.custodios = []
        self.motivos_no_vigor: List[str] = []
        self._evaluar_vigor()

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

    def _exige(self, campos: Dict[str, List[str]], clave: str) -> Tuple[bool, str]:
        valores = campos.get(clave) or []
        if not valores:
            return (False, f"ACTO_SIN_{clave}: el acta no declara {clave}")
        return (True, valores[0])

    # ── vigencia del registro (AUTH-01) ──────────────────────────────────
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
        if not FECHA_RE.match(fecha):
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
        ok_accion, valor_accion = self._exige(campos, "ACCION")
        if not ok_accion or valor_accion.upper() != "RATIFICAR":
            motivos.append(
                "REGISTRO_ACTO_NO_RATIFICA: el acta no declara una accion expresa "
                "RATIFICAR")
        ok_estado, valor_estado = self._exige(campos, "ESTADO")
        if not ok_estado or valor_estado.upper() != REGISTRO_EN_VIGOR:
            motivos.append(
                f"REGISTRO_ACTO_NO_RATIFICADO: el acta declara estado "
                f"{valor_estado!r}")
        objeto, valor_objeto = self._exige(campos, "OBJETO")
        if not objeto or valor_objeto != str(self.registro.get("id") or ""):
            motivos.append(
                "REGISTRO_ACTO_NO_RATIFICA_EL_REGISTRO: el acta no nombra el "
                "identificador de este registro")
        version, valor_version = self._exige(campos, "VERSION")
        if not version or valor_version != str(self.registro.get("version") or ""):
            motivos.append(
                "REGISTRO_ACTO_NO_RATIFICA_EL_REGISTRO: el acta no nombra la "
                "version de este registro")
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

    # ── autoridades (AUTH-02) ────────────────────────────────────────────
    def _resuelve_autoridad(self, decision: Dict[str, Any]) -> Tuple[Optional[str], List[str]]:
        """Identificador CANONICO de la autoridad de una decision.

        `autoridad` es el canonico; `firmante` es un alias. Si aparecen los
        dos, tienen que resolver a la MISMA autoridad registrada: un firmante
        libre con una autoridad registrada distinta se rechaza.
        """
        motivos: List[str] = []
        canonico = str(decision.get("autoridad") or "").strip()
        alias = str(decision.get("firmante") or "").strip()
        if not canonico and not alias:
            return (None, ["AUTORIDAD_AUSENTE"])
        candidatos = [c for c in (canonico, alias) if c]
        resueltos = []
        for candidato in candidatos:
            if candidato in self.autoridades:
                resueltos.append(candidato)
                continue
            # alias declarado en el registro
            for id_autoridad, datos in self.autoridades.items():
                if isinstance(datos, dict) and candidato in (datos.get("alias") or []):
                    resueltos.append(id_autoridad)
                    break
            else:
                motivos.append(
                    f"AUTORIDAD_DESCONOCIDA: {candidato!r} no consta en el "
                    "registro ni es alias de ninguna autoridad")
        if motivos:
            return (None, motivos)
        if len(set(resueltos)) > 1:
            motivos.append(
                f"IDENTIDADES_CONTRADICTORIAS: la decision declara dos "
                f"autoridades que no son la misma ({resueltos})")
            return (None, motivos)
        return (resueltos[0], [])

    def _canales_de(self, autoridad: str) -> List[str]:
        datos = self.autoridades.get(autoridad)
        if not isinstance(datos, dict):
            return []
        return [str(c) for c in (datos.get("canales") or []) if str(c).strip()]

    def _identidad_coincide(self, autoridad: str, sha: str) -> Tuple[bool, str]:
        """La identidad declarada para la autoridad debe ser la del commit.

        En este repositorio la identidad git es compartida por ejecutor y
        propietario, asi que esto NO basta para autorizar: por eso el
        verificador exige ademas canal y contenido (y el registro en vigor).
        """
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

    # ── contrato de acto (AUTH-03) ───────────────────────────────────────
    def _valida_contrato_acto(self, campos: Dict[str, List[str]], decision: Dict[str, Any],
                              hallazgo: Dict[str, Any], autoridad: str,
                              canales: List[str]) -> List[str]:
        motivos: List[str] = []
        ok, valor = self._exige(campos, "ACTO")
        if not ok or valor.upper() != "RATIFICACION":
            motivos.append(f"ACTO_TIPO_INVALIDO: {valor!r} (se exige RATIFICACION)")
        ok, valor_accion = self._exige(campos, "ACCION")
        if not ok:
            motivos.append("ACTO_SIN_ACCION: el acta no declara accion")
        elif valor_accion.upper() in ACCIONES_QUE_NO_RATIFICAN:
            motivos.append(
                f"ACTO_NO_RATIFICA: la accion {valor_accion!r} no es una "
                "ratificacion expresa")
        elif valor_accion.upper() != "RATIFICAR":
            motivos.append(
                f"ACTO_ACCION_INVALIDA: {valor_accion!r} (se exige RATIFICAR)")
        ok, valor_estado = self._exige(campos, "ESTADO")
        if not ok:
            motivos.append("ACTO_SIN_ESTADO")
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
            ok, valor = self._exige(campos, clave)
            if not ok:
                motivos.append(f"ACTO_SIN_{clave}")
            elif valor != esperado:
                motivos.append(
                    f"ACTO_ALCANCE_NO_COINCIDE: {clave} del acta ({valor!r}) no "
                    f"es el declarado ({esperado!r})")
        ok, valor_canal = self._exige(campos, "CANAL")
        if not ok:
            motivos.append("ACTO_SIN_CANAL")
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
        campos = self._campos(self._mensaje(referencia))
        motivos.extend(self._valida_contrato_acto(campos, decision, hallazgo,
                                                  autoridad, canales))
        return (not motivos, motivos)

    # ── contrato de custodia (AUTH-04) ───────────────────────────────────
    def _valida_contrato_custodia(self, campos: Dict[str, List[str]], decision: Dict[str, Any],
                                  hallazgo: Dict[str, Any], autoridad: str,
                                  canales: List[str]) -> List[str]:
        motivos: List[str] = []
        ok, valor = self._exige(campos, "ACTO")
        if not ok or valor.upper() != "CUSTODIA":
            motivos.append(f"CUSTODIA_TIPO_INVALIDO: {valor!r} (se exige CUSTODIA)")
        ok, valor_accion = self._exige(campos, "ACCION")
        if not ok or valor_accion.upper() != "CUSTODIAR":
            motivos.append(
                f"CUSTODIA_ACCION_INVALIDA: {valor_accion!r} (se exige CUSTODIAR)")
        ok, valor_estado = self._exige(campos, "ESTADO")
        if not ok or valor_estado.upper() not in ("VIGENTE", REGISTRO_EN_VIGOR):
            motivos.append(f"CUSTODIA_ESTADO_INVALIDO: {valor_estado!r}")
        custodia = decision.get("custodia") or {}
        # El custodio NO se compara con un valor esperado: tiene que EXISTIR y
        # estar ADMITIDO por el registro.
        ok_custodio, valor_custodio = self._exige(campos, "CUSTODIO")
        if not ok_custodio:
            motivos.append("CUSTODIA_SIN_CUSTODIO")
        else:
            admitidos = set(self.custodios) | set(self.autoridades)
            if valor_custodio not in admitidos:
                motivos.append(
                    f"CUSTODIO_NO_ADMITIDO: {valor_custodio!r} no consta en el "
                    "registro")
        for clave, esperado in (("ACTID", str(custodia.get("id") or "")),
                                ("RESIDUO", str(hallazgo.get("id") or "")),
                                ("NORMA", str(hallazgo.get("norm") or "")),
                                ("RUTA", str(hallazgo.get("path") or "")),
                                ("HUELLA", str(hallazgo.get("huella") or ""))):
            ok, valor_campo = self._exige(campos, clave)
            if not ok:
                motivos.append(f"CUSTODIA_SIN_{clave}")
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
        # vigencia temporal
        ok, vigencia = self._exige(campos, "VIGENCIA")
        if not ok:
            motivos.append("CUSTODIA_SIN_VIGENCIA")
        else:
            partes = [p.strip() for p in vigencia.replace(" ", "").split("/")]
            if len(partes) != 2 or not all(FECHA_RE.match(p) for p in partes):
                motivos.append(
                    f"CUSTODIA_VIGENCIA_INVALIDA: {vigencia!r} (se exige "
                    "YYYY-MM-DD/YYYY-MM-DD)")
            else:
                try:
                    fin = datetime.date.fromisoformat(partes[1])
                    if fin < datetime.date.today():
                        motivos.append(
                            f"CUSTODIA_EXPIRADA: la vigencia termina el "
                            f"{fin.isoformat()}")
                except ValueError:
                    motivos.append(f"CUSTODIA_VIGENCIA_INVALIDA: {vigencia!r}")
        ok, valor_canal = self._exige(campos, "CANAL")
        if not ok:
            motivos.append("CUSTODIA_SIN_CANAL")
        elif valor_canal not in canales:
            motivos.append(
                f"CUSTODIA_CANAL_NO_DECLARADO: {valor_canal!r} no es un canal de "
                f"{autoridad}")
        return motivos

    def verificar_custodia(self, decision: Dict[str, Any],
                            hallazgo: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """La custodia: SEGUNDO acto, con contrato propio, y sin alcanzar para
        archivar, trasladar ni purgar."""
        motivos: List[str] = []
        if not self.en_vigor():
            return (False, [f"REGISTRO_NO_EN_VIGOR: {m}"
                            for m in self.motivos_no_vigor])
        autoridad, motivos_auth = self._resuelve_autoridad(decision)
        if autoridad is None:
            return (False, motivos_auth)
        canales = self._canales_de(autoridad)
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
        if not self._alcanzable_desde(referencia, canales):
            return (False, [
                "CUSTODIA_AJENA: el acta de custodia no es alcanzable desde el "
                "canal declarado"])
        ok_id, motivo_id = self._identidad_coincide(autoridad, referencia)
        if not ok_id:
            motivos.append(motivo_id)
        campos = self._campos(self._mensaje(referencia))
        motivos.extend(self._valida_contrato_custodia(campos, decision, hallazgo,
                                                      autoridad, canales))
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
    autoridades = datos.get("autoridades")
    if isinstance(autoridades, list):
        mapa: Dict[str, Any] = {}
        for entrada in autoridades:
            if isinstance(entrada, dict) and entrada.get("id"):
                mapa[str(entrada["id"])] = entrada
        datos = {**datos, "autoridades": mapa}
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
        if not FECHA_RE.match(str(ratificacion.get("fecha") or "")):
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
    autoridades = registro.get("autoridades")
    if isinstance(autoridades, list):
        mapa: Dict[str, Any] = {}
        for entrada in autoridades:
            if isinstance(entrada, dict) and entrada.get("id"):
                mapa[str(entrada["id"])] = entrada
        registro = {**registro, "autoridades": mapa}
        autoridades = mapa
    if not isinstance(autoridades, dict) or not autoridades:
        return None
    verificador = VerificadorActosGit(raiz, registro)
    if not verificador.en_vigor():
        return None
    return verificador
