#!/usr/bin/env python3
"""Verificador de ACTOS y CUSTODIAS para la propuesta de certificacion
compuesta (DEC-03, PROPUESTA — NO APLICADA al QG-02 de produccion).

ESTADO: PROPUESTA. El modulo `politica_certificacion_compuesta` (R16/R17)
exige que una decision tenga forma de decision (id, estado, firmante, fecha,
referencia, alcance, custodia). Eso es el ESQUEMA. Este modulo responde a la
pregunta que el esquema no puede responder: **¿existe el acto, y lo ha
ratificado quien puede?**

Que una referencia sea 40 hex NO demuestra que el objeto exista; que un
`firmante` sea un string NO demuestra que tenga autoridad; que
`custodia.verificada` sea `true` NO demuestra una verificacion independiente
(campo autoafirmado por el mismo recibo).

LA FUENTE CONFIABLE (definida por el propietario en DEC-03):

  1. Un REGISTRO de autoridades (`autoridades-de-decision.yaml`): que id de
     autoridad existe, en que canal (ref) publica sus actos y con que
     identidad. Una autoridad NO registrada no es autoridad.
  2. El REPOSITORIO: el acto debe existir como commit, ser alcanzable desde
     un canal declarado para esa autoridad y su CONTENIDO debe nombrar la
     decision y el residuo preciso (id, norma, ruta y huella). Un commit
     ajeno, un mensaje generico o un acto revocado no ratifican.
  3. La CUSTODIA es OTRO acto: distinto del de la decision, existente,
     alcanzable y con contenido que nombre la custodia y el residuo.

LIMIT HONESTO (no se vende mas de lo que es): en este repositorio el
ejecutor y el propietario comparten identidad git y permisos de push, asi que
el CANAL declarado es un control ADMINISTRATIVO (lo declara y lo vigila el
propietario), no criptografico. Este verificador acredita que EXISTE un acto
verificable en la fuente declarada; la garantia de que ese acto emane del
propietario depende de la integridad del canal, que es una decisión del
propietario (DEC-03). Si no hay fuente declarada, el veredicto es BLOCKED.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
#: Palabras que revocan un acto aunque exista y sea alcanzable.
REVOCACION = ("REVOCADO", "RECHAZADO", "ANULADO", "REVOKED", "REJECTED")


class VerificadorActosGit:
    """Verifica actos y custodias contra un repositorio y un registro."""

    def __init__(self, raiz: Path, registro: Dict[str, Any]):
        self.raiz = Path(raiz)
        self.autoridades = registro.get("autoridades") or {}
        if not isinstance(self.autoridades, dict):
            self.autoridades = {}

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

    def _autoridad_de(self, decision: Dict[str, Any]) -> str:
        """La autoridad del acto.

        El esquema (R17) llama al campo `firmante`; la verificacion lo trata
        como un IDENTIFICADOR DE AUTORIDAD registrado, no como un nombre
        libre: `firmante: "alguien"` no es autoridad, `firmante:
        "propietario-datos"` si lo es (si consta en el registro).
        """
        return str(decision.get("autoridad") or decision.get("firmante") or "")

    # ── canales ──────────────────────────────────────────────────────────
    def _canales_de(self, autoridad: str) -> List[str]:
        datos = self.autoridades.get(autoridad)
        if not isinstance(datos, dict):
            return []
        canales = datos.get("canales") or []
        return [str(c) for c in canales if str(c).strip()]

    def _autoridad_registrada(self, autoridad: str) -> bool:
        datos = self.autoridades.get(autoridad)
        return isinstance(datos, dict) and bool(self._canales_de(autoridad))

    def _identidad_coincide(self, autoridad: str, sha: str) -> Tuple[bool, str]:
        """La identidad declarada para la autoridad debe ser la del commit.

        En este repositorio la identidad git es compartida por ejecutor y
        propietario, asi que esto NO basta para autorizar: por eso el
        verificador exige ademas canal y contenido. Se mantiene porque acota
        el error (un commit de otra identidad no es de esa autoridad).
        """
        datos = self.autoridades.get(autoridad) or {}
        identidad = datos.get("identidad_git") or {}
        if not identidad:
            return (True, "")  # la autoridad no declara identidad: no se exige
        rc, autor = self._git("show", "-s", "--format=%an <%ae>", sha)
        if rc != 0:
            return (False, "IDENTIDAD_ILEGIBLE")
        esperado = str(identidad.get("correo") or "").strip()
        if not esperado:
            return (True, "")
        if esperado not in autor:
            return (False, f"IDENTIDAD_NO_AUTORIZADA: el acto no esta firmado por {esperado}")
        return (True, "")

    # ── verificacion ─────────────────────────────────────────────────────
    def verificar_acto(self, decision: Dict[str, Any],
                        hallazgo: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """El acto debe existir, ser alcanzable, no estar revocado y nombrar
        el residuo preciso (incluida su huella)."""
        motivos: List[str] = []
        autoridad = self._autoridad_de(decision)
        if not self._autoridad_registrada(autoridad):
            motivos.append(
                f"AUTORIDAD_NO_REGISTRADA: {autoridad!r} no consta en el "
                "registro de autoridades (o no declara canal)")
            return (False, motivos)
        referencia = str(decision.get("referencia") or "")
        if not self._existe_commit(referencia):
            motivos.append(f"ACTO_INEXISTENTE: {referencia!r} no es un commit de este repositorio")
            return (False, motivos)
        canales = self._canales_de(autoridad)
        if not self._alcanzable_desde(referencia, canales):
            motivos.append(
                f"ACTO_AJENO: {referencia[:12]}… no es alcanzable desde los "
                f"canales declarados de {autoridad}")
            return (False, motivos)
        ok_id, motivo_id = self._identidad_coincide(autoridad, referencia)
        if not ok_id:
            motivos.append(motivo_id)
        mensaje = self._mensaje(referencia)
        if any(palabra in mensaje.upper() for palabra in REVOCACION):
            motivos.append("ACTO_REVOCADO: el contenido del acto lo declara revocado")
        decision_id = str(decision.get("id") or "")
        if decision_id and decision_id not in mensaje:
            motivos.append(
                f"ACTO_SIN_ALCANCE: el contenido del acto no menciona la "
                f"decision {decision_id}")
        huella = str(hallazgo.get("huella") or "")
        if huella and huella not in mensaje:
            motivos.append(
                "ACTO_SIN_ALCANCE: el contenido del acto no menciona la huella "
                "del residuo")
        for campo, etiqueta in (("id", "residuo"), ("norm", "norma"),
                                ("path", "ruta")):
            valor = str(hallazgo.get(campo) or "")
            if valor and valor not in mensaje:
                motivos.append(
                    f"ACTO_SIN_ALCANCE: el contenido del acto no menciona la "
                    f"{etiqueta} del residuo ({valor})")
        return (not motivos, motivos)

    def verificar_custodia(self, decision: Dict[str, Any],
                            hallazgo: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """La custodia es OTRO acto, existente, alcanzable y con contenido."""
        motivos: List[str] = []
        custodia = decision.get("custodia") or {}
        referencia = str(custodia.get("referencia") or "")
        if not SHA_RE.match(referencia):
            motivos.append("CUSTODIA_SIN_REFERENCIA_VERIFICABLE")
            return (False, motivos)
        if referencia == str(decision.get("referencia") or ""):
            motivos.append(
                "CUSTODIA_AUTOAFIRMADA: el acta de custodia es el propio acto "
                "de la decision (no es una verificacion independiente)")
            return (False, motivos)
        if not self._existe_commit(referencia):
            motivos.append(f"CUSTODIA_INEXISTENTE: {referencia!r} no es un commit")
            return (False, motivos)
        autoridad = self._autoridad_de(decision)
        if not self._alcanzable_desde(referencia, self._canales_de(autoridad)):
            motivos.append("CUSTODIA_AJENA: el acta de custodia no es alcanzable desde el canal declarado")
            return (False, motivos)
        mensaje = self._mensaje(referencia)
        if any(palabra in mensaje.upper() for palabra in REVOCACION):
            motivos.append("CUSTODIA_REVOCADA")
        id_custodia = str(custodia.get("id") or "")
        if id_custodia and id_custodia not in mensaje:
            motivos.append("CUSTODIA_SIN_ALCANCE: el acta no menciona su identificador")
        huella = str(hallazgo.get("huella") or "")
        if huella and huella not in mensaje:
            motivos.append("CUSTODIA_SIN_ALCANCE: el acta no menciona la huella del residuo")
        return (not motivos, motivos)


def cargar_registro(ruta: Path) -> Dict[str, Any]:
    """Lee el registro de autoridades (PROPUESTA).

    Acepta las dos formas de declaracion: mapa `id -> datos` (la que consume
    el verificador) o lista de entradas con `id` (mas legible en YAML), que se
    normaliza al mapa.
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


def verificador_desde_registro(raiz: Path, registro: Dict[str, Any]
                               ) -> Optional[VerificadorActosGit]:
    """Construye el verificador si hay registro con autoridades declaradas.

    Sin registro (o sin autoridades) NO hay fuente confiable: se devuelve
    None y el evaluador BLOCKED.
    """
    if not isinstance(registro, dict):
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
    return VerificadorActosGit(raiz, registro)
