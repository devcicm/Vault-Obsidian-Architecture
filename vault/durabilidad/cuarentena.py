"""Retener sin borrar (`20_Quarantine/`).

La cuarentena existe porque **la alternativa a retener no es limpiar: es
borrar**. Una nota sin sección determinable, o cuyo contenido disparó el
pre-vuelo anti-poisoning, necesita salir del camino sin desaparecer. Sin un
sitio donde ponerla, la única salida operativa es `rm`, y eso contradice la
política de no-derogación del estándar.

Tres propiedades la hacen segura, y las tres son invariantes de este módulo, no
recordatorios en un script:

  - **La nota se mueve, no se copia.** Dos copias de una nota dudosa es peor que
    una: la que queda fuera se sigue leyendo como contexto válido.
  - **El origen se guarda siempre**, y viaja dentro de la nota además de en el
    ledger. Si el ledger se pierde, la nota sigue sabiendo de dónde salió.
  - **La razón es obligatoria.** Es lo que permite que otra sesión decida sin
    repetir el análisis que llevó a retenerla.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from ..kernel.contexto import VaultContext

CARPETA = "20_Quarantine"
FICHERO_LEDGER = ".quarantine-ledger.json"

#: Categorías = subcarpetas registradas en `vault_registry.SUBFOLDERS`. La razón
#: por la que se retiene determina quién puede sacarla: un duplicado lo resuelve
#: `vault_merge`, un contenido sospechoso exige revisión humana.
CATEGORIAS = ["unclassified", "suspicious", "duplicates"]


def _serializar_frontmatter(fm: dict) -> str:
    lineas = ["---"]
    for k, v in fm.items():
        lineas.append(
            f"{k}: {v}" if isinstance(v, str)
            else f"{k}: {json.dumps(v, ensure_ascii=False)}"
        )
    lineas.append("---")
    return "\n".join(lineas)


class ServicioCuarentena:
    def __init__(self, ctx: VaultContext, partir_frontmatter=None) -> None:
        self._ctx = ctx
        # El parseo de frontmatter es del kernel (`vault_lib`) y se inyecta:
        # el dominio no debe saber si viene de un regex o de PyYAML, y así el
        # test puede ejercer las reglas de retención sin arrastrar el parser.
        self._partir = partir_frontmatter

    # ── Rutas y ledger ───────────────────────────────────────────────────────

    @property
    def carpeta(self) -> Path:
        return self._ctx.ruta(CARPETA)

    @property
    def fichero_ledger(self) -> Path:
        return self._ctx.ruta(CARPETA, FICHERO_LEDGER)

    def _leer_ledger(self) -> dict:
        try:
            datos = json.loads(self.fichero_ledger.read_text(encoding="utf-8"))
        except (FileNotFoundError, NotADirectoryError, json.JSONDecodeError, OSError):
            return {"entries": []}
        if not isinstance(datos.get("entries"), list):
            return {"entries": []}
        return datos

    def _guardar_ledger(self, datos: dict) -> None:
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self._ctx.escritor.escribir_json(self.fichero_ledger, datos)

    def _relativa(self, ruta: Path) -> str:
        return str(ruta.relative_to(self._ctx.raiz)).replace("\\", "/")

    # ── Retener ──────────────────────────────────────────────────────────────

    def retener(self, ruta: str, razon: str, categoria: str = "unclassified",
                agente: str = "") -> dict:
        if categoria not in CATEGORIAS:
            return {"ok": False, "error_code": "INVALID_CATEGORY",
                    "error": f"category '{categoria}' no válida. Usa: {CATEGORIAS}"}
        if not (razon or "").strip():
            return {
                "ok": False, "error_code": "EMPTY_REASON",
                "error": ("La razón es obligatoria: sin ella, quien encuentre la "
                          "nota tiene que repetir el análisis que llevó a retenerla"),
            }
        if not agente:
            return {"ok": False, "error_code": "missing_agent", "norm_code": "AP-16",
                    "error": "missing_agent",
                    "message": "AP-16: usa --agent <nombre> o exporta VAULT_AGENT."}

        try:
            origen = self._ctx.ruta(*Path(ruta).parts)
        except ValueError as exc:
            return {"ok": False, "error_code": "INVALID_PATH", "error": str(exc)}

        if not origen.is_file():
            return {"ok": False, "error_code": "NOT_FOUND",
                    "error": f"No existe la nota: {ruta}"}

        rel_origen = self._relativa(origen)
        if rel_origen.startswith(f"{CARPETA}/"):
            return {"ok": True, "action": "noop", "written": 0, "path": rel_origen,
                    "message": "Ya estaba en cuarentena"}

        destino = self.carpeta / categoria / origen.name
        # Colisión de nombres: dos notas distintas con el mismo nombre se
        # pisarían, y perder la primera al retener la segunda es exactamente el
        # borrado que la cuarentena existe para evitar.
        if destino.exists():
            destino = destino.with_name(f"{destino.stem}-{uuid.uuid4().hex[:8]}.md")

        ahora = self._ctx.reloj.marca()
        fm, cuerpo = self._partir(origen.read_text(encoding="utf-8", errors="replace"))
        fm["quarantine_origin"] = rel_origen
        fm["quarantine_reason"] = razon.strip()
        fm["quarantine_category"] = categoria
        fm["quarantine_at"] = ahora
        fm["quarantine_by"] = agente
        # No se toca `status`: el estado de la nota no cambió por estar
        # retenida, y sobrescribirlo destruiría el dato que quizá haga falta
        # para clasificarla.

        self._ctx.escritor.escribir(
            destino, _serializar_frontmatter(fm) + "\n\n" + cuerpo.lstrip("\n")
        )
        # Se mueve: dejar la original en su sitio significa que se sigue leyendo
        # como contexto válido, que es justo lo que se quería impedir.
        origen.unlink()

        rel_destino = self._relativa(destino)
        ledger = self._leer_ledger()
        ledger["entries"].append({
            "origin": rel_origen, "path": rel_destino, "category": categoria,
            "reason": razon.strip(), "agent": agente, "at": ahora, "restored": False,
        })
        self._guardar_ledger(ledger)

        return {"action": "quarantined", "path": rel_destino,
                "origin": rel_origen, "category": categoria}

    # ── Devolver ─────────────────────────────────────────────────────────────

    def devolver(self, ruta: str, agente: str = "") -> dict:
        """Sin esto, la cuarentena es una papelera con otro nombre."""
        ledger = self._leer_ledger()
        rel = str(ruta).replace("\\", "/")

        entrada = next((e for e in reversed(ledger["entries"])
                        if e["path"] == rel and not e["restored"]), None)
        if entrada is None:
            return {"ok": False, "error_code": "NOT_QUARANTINED",
                    "error": f"'{rel}' no consta como retenida y sin restaurar"}

        try:
            actual = self._ctx.ruta(*Path(rel).parts)
            destino = self._ctx.ruta(*Path(entrada["origin"]).parts)
        except ValueError as exc:
            return {"ok": False, "error_code": "INVALID_PATH", "error": str(exc)}

        if not actual.is_file():
            return {"ok": False, "error_code": "NOT_FOUND", "error": f"No existe: {rel}"}
        if destino.exists():
            return {
                "ok": False, "error_code": "ORIGIN_OCCUPIED",
                "error": (f"El origen '{entrada['origin']}' ya está ocupado. "
                          f"Restaurar encima sobrescribiría una nota existente."),
            }

        fm, cuerpo = self._partir(actual.read_text(encoding="utf-8", errors="replace"))
        # Los campos de cuarentena se van con ella: el paso por cuarentena queda
        # en el ledger, que es append-only, no incrustado en la nota devuelta.
        for k in [k for k in fm if k.startswith("quarantine_")]:
            fm.pop(k)

        self._ctx.escritor.escribir(
            destino, _serializar_frontmatter(fm) + "\n\n" + cuerpo.lstrip("\n")
        )
        actual.unlink()

        entrada["restored"] = True
        entrada["restored_at"] = self._ctx.reloj.marca()
        entrada["restored_by"] = agente or "unknown"
        self._guardar_ledger(ledger)

        return {"action": "restored", "path": entrada["origin"], "from": rel}

    # ── Consultar ────────────────────────────────────────────────────────────

    def listar(self, categoria: str | None = None) -> dict:
        entradas = self._leer_ledger()["entries"]
        retenidas = [e for e in entradas
                     if not e["restored"] and (categoria is None
                                               or e["category"] == categoria)]
        return {
            "ok": True,
            "count": len(retenidas),
            "restored_total": sum(1 for e in entradas if e["restored"]),
            "entries": retenidas,
        }


__all__ = ["CARPETA", "FICHERO_LEDGER", "CATEGORIAS", "ServicioCuarentena"]
