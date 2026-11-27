"""Identity, Registro Maestro y Control de Acceso fail-closed entre baules (hoja del nucleo).

Arquitectura de tenencia e identidad de VOA:
- **1 Baul = 1 Tenant soberano (silo fisico en disco + Git)**: evita fugas
  en Obsidian, indices y repositorio Git; no introduce multi-tenancy logico
  dentro de un mismo baul.
- **Registro Maestro (`<VAULT_MASTER>/registry.json`)**: unifica el inventario
  de baules dentro de la casa (`~/.vault-master/`) y baules externos en rutas
  personalizadas (ej. `B:\\vault-dev-codex`), mas protocolo de migracion
  verificada por SHA-256 sin perdida de datos.
- **Identidad y Politica Soberana (`<baul-destino>/00_System/access-policy.json`)**:
  modelo **fail-closed** (`default: "deny"`). Todo acceso entre baules es
  **estrictamente de solo lectura (`AP-36`)**, autenticado por `Principal`
  `(vault, role, project)`, y filtrado por secciones, etiquetas y nivel de
  sensibilidad CIA (`public` < `internal` < `confidential` < `restricted`).

Cero dependencias externas fuera de stdlib + PyYAML (via parser del kernel).
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

from . import procesos_git
from .enumeracion import notas_en_disco
from .errores import construir_error
from .frontmatter_parsing import parse_frontmatter, separar_frontmatter
from .vault_home import es_ruta_de_master, listar_vaults_de_la_casa, master_home

#: Version del esquema del registro maestro y de la politica de acceso.
SCHEMA_VERSION = 1

#: Nombre del registro maestro dentro de la casa de los vaults (`VAULT_MASTER`).
ARCHIVO_REGISTRO_MAESTRO = "registry.json"

#: Ruta relativa de la politica de acceso soberana dentro de cada baul.
RUTA_POLITICA_ACCESO = "00_System/access-policy.json"

#: Roles validos para identidad entre baules (alineado con SP-04 / SP-05).
ROLES_VALIDOS: Tuple[str, ...] = ("lector", "ejecutor", "operador")

#: Escala ordenada de sensibilidad CIA (menor a mayor restriccion).
NIVELES_SENSIBILIDAD: Tuple[str, ...] = (
    "public",
    "internal",
    "confidential",
    "restricted",
)

_ORDEN_SENSIBILIDAD: Dict[str, int] = {
    nivel: idx for idx, nivel in enumerate(NIVELES_SENSIBILIDAD)
}

#: Unico modo permitido para acceso entre baules (AP-36: cero escritura cruzada).
MODOS_ACCESO_CRUZADO: Tuple[str, ...] = ("read_only",)

#: Secciones sensibles bloqueadas por defecto en acceso cruzado si el grant no
#: las autoriza explicitamente en `allowed_sections`.
SECCIONES_SENSIBLES_POR_DEFECTO = frozenset({"00_System", "17_Preferences", "20_Quarantine"})

#: Carpetas operativas efimeras excluidas al calcular manifiesto de contenido en migracion.
_EXCLUIR_MANIFIESTO = frozenset({".git", ".locks", "__pycache__", "node_modules"})


@dataclass(frozen=True)
class Principal:
    """Identidad inmutable del llamador en una operacion entre baules."""

    vault: str
    role: str = "lector"
    project: Optional[str] = None
    subject: Optional[str] = None

    def como_dict(self) -> Dict[str, Any]:
        return {
            "vault": self.vault,
            "role": self.role,
            "project": self.project,
            "subject": self.subject,
        }


def _ahora_utc_iso(ahora_utc: Optional[datetime] = None) -> str:
    dt = ahora_utc or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parsear_iso_utc(valor: str) -> datetime:
    texto = str(valor).strip()
    if texto.endswith("Z"):
        texto = texto[:-1] + "+00:00"
    dt = datetime.fromisoformat(texto)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _escribir_json_atomico(destino: Path, payload: Mapping[str, Any]) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    contenido = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        dir=str(destino.parent),
        prefix=f".{destino.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(contenido)
            fh.flush()
        os.replace(str(tmp_path), str(destino))
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# 1. Registro Maestro (`<VAULT_MASTER>/registry.json`)
# ---------------------------------------------------------------------------


def ruta_registro_maestro(casa: Optional[Path] = None) -> Path:
    """Ruta canonica del indice maestro dentro de `VAULT_MASTER`."""
    return Path(casa or master_home()) / ARCHIVO_REGISTRO_MAESTRO


def leer_registro_maestro(casa: Optional[Path] = None) -> Dict[str, Any]:
    """Lee el registro maestro. Si no existe devuelve estructura vacia; si esta
    corrupto lanza ValueError (AP-51: nunca ocultar corrupcion como vacio)."""
    ruta = ruta_registro_maestro(casa)
    if not ruta.is_file():
        return {
            "schema_version": SCHEMA_VERSION,
            "updated_at": None,
            "vaults": [],
        }
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Registro maestro ilegible en {ruta}: {exc}") from exc
    if not isinstance(datos, dict) or not isinstance(datos.get("vaults"), list):
        raise ValueError(f"Registro maestro invalido en {ruta}: falta lista 'vaults'")
    return datos


@contextmanager
def _bloquear_registro(ruta_reg: Path, timeout_s: float = 10.0) -> Iterator[None]:
    """Lock exclusivo de fichero para serializar escrituras concurrentes a `registry.json` (H-06)."""
    ruta_reg.parent.mkdir(parents=True, exist_ok=True)
    lock_path = ruta_reg.with_name(f".{ruta_reg.name}.lock")
    limite = time.monotonic() + max(0.5, float(timeout_s))
    adquirido = False
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, f"{os.getpid()}\n".encode("ascii"))
            finally:
                os.close(fd)
            adquirido = True
            break
        except FileExistsError:
            if time.monotonic() >= limite:
                raise TimeoutError(f"Timeout adquiriendo lock de registro maestro: {lock_path}")
            time.sleep(0.02)
    try:
        yield
    finally:
        if adquirido:
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass


def registrar_baul_maestro(
    nombre: str,
    ruta: "str | Path",
    *,
    alias: Sequence[str] = (),
    proyectos: Sequence[str] = (),
    descripcion: str = "",
    tenant_id: Optional[str] = None,
    previous_path: Optional[str] = None,
    allow_update: bool = False,
    casa: Optional[Path] = None,
) -> Dict[str, Any]:
    """Registra o actualiza un baul (interno en master o externo) en `registry.json`.

    H-06: serializado bajo lock de fichero y protegido contra colisiones de
    identidad — registrar un `name` existente con distinta ruta (o una ruta
    existente con distinto `name`) lanza `ValueError` salvo `allow_update=True`.
    """
    limpio = (nombre or "").strip()
    if not limpio or any(sep in limpio for sep in ("/", "\\", ":")):
        raise ValueError(f"Nombre de baul invalido: {nombre!r}")

    casa_dir = Path(casa or master_home()).expanduser()
    ruta_resuelta = Path(ruta).expanduser().resolve()
    try:
        en_master = ruta_resuelta.is_relative_to(casa_dir.resolve())
    except (OSError, ValueError):
        en_master = es_ruta_de_master(ruta_resuelta) if casa is None else False

    reg_path = ruta_registro_maestro(casa_dir)
    with _bloquear_registro(reg_path):
        registro = leer_registro_maestro(casa_dir)
        entradas: List[Dict[str, Any]] = [
            dict(v) for v in registro.get("vaults", []) if isinstance(v, dict)
        ]

        ahora = _ahora_utc_iso()
        nueva = {
            "name": limpio,
            "tenant_id": (tenant_id or limpio).strip(),
            "path": str(ruta_resuelta),
            "origin": "master" if en_master else "external",
            "aliases": sorted({str(a).strip() for a in alias if str(a).strip()}),
            "projects": sorted({str(p).strip() for p in proyectos if str(p).strip()}),
            "description": (descripcion or "").strip(),
            "updated_at": ahora,
        }
        if previous_path:
            nueva["previous_path"] = str(Path(previous_path).expanduser().resolve())

        reemplazada = False
        for idx, existente in enumerate(entradas):
            misma_ruta = False
            try:
                misma_ruta = Path(existente.get("path", "")).expanduser().resolve() == ruta_resuelta
            except OSError:
                misma_ruta = False
            mismo_nombre = existente.get("name") == limpio
            if mismo_nombre and not misma_ruta and not allow_update:
                raise ValueError(
                    f"Conflicto de identidad en registro maestro: el baul {limpio!r} ya apunta a "
                    f"{existente.get('path')!r}; usa allow_update=True para reubicarlo."
                )
            if misma_ruta and not mismo_nombre and not allow_update:
                raise ValueError(
                    f"Conflicto de identidad en registro maestro: la ruta {str(ruta_resuelta)!r} "
                    f"ya esta registrada como {existente.get('name')!r}; usa allow_update=True para renombrarla."
                )
            if mismo_nombre or misma_ruta:
                if not previous_path and existente.get("previous_path"):
                    nueva["previous_path"] = existente["previous_path"]
                nueva["registered_at"] = existente.get("registered_at") or ahora
                entradas[idx] = nueva
                reemplazada = True
                break

        if not reemplazada:
            nueva["registered_at"] = ahora
            entradas.append(nueva)

        entradas.sort(key=lambda item: (item.get("origin") != "master", item.get("name", "")))
        payload = {
            "schema_version": SCHEMA_VERSION,
            "updated_at": ahora,
            "vaults": entradas,
        }
        _escribir_json_atomico(reg_path, payload)
    return {
        "ok": True,
        "written": 1,
        "registry_path": str(reg_path),
        "vault": nueva,
    }


def _leer_version_baul(raiz: Path) -> str:
    try:
        datos = json.loads(
            (raiz / "00_System" / "standard-version.json").read_text(encoding="utf-8")
        )
        return str(
            datos.get("applied_version")
            or datos.get("version")
            or datos.get("standard_version")
            or ""
        )
    except (OSError, ValueError):
        return ""


def listar_ecosistema_baules(casa: Optional[Path] = None) -> Dict[str, Any]:
    """Combina los baules fisicos de `VAULT_MASTER` y los externos en `registry.json`."""
    casa_dir = Path(casa or master_home()).expanduser()
    internos = listar_vaults_de_la_casa(casa_dir)
    registro = leer_registro_maestro(casa_dir)

    por_ruta: Dict[str, Dict[str, Any]] = {}
    resultado: List[Dict[str, Any]] = []

    for item in internos:
        ruta_p = Path(item["ruta"]).resolve()
        clave = str(ruta_p).lower()
        entrada = {
            "name": item["nombre"],
            "tenant_id": item["nombre"],
            "path": str(ruta_p),
            "origin": "master",
            "version": item.get("version", ""),
            "git": bool(item.get("git")),
            "exists": ruta_p.is_dir(),
            "has_access_policy": (ruta_p / RUTA_POLITICA_ACCESO).is_file(),
            "aliases": [],
            "projects": [],
        }
        por_ruta[clave] = entrada
        resultado.append(entrada)

    for reg in registro.get("vaults", []):
        if not isinstance(reg, dict) or not reg.get("path"):
            continue
        ruta_p = Path(reg["path"]).expanduser().resolve()
        clave = str(ruta_p).lower()
        if clave in por_ruta:
            por_ruta[clave]["aliases"] = list(reg.get("aliases") or [])
            por_ruta[clave]["projects"] = list(reg.get("projects") or [])
            por_ruta[clave]["tenant_id"] = reg.get("tenant_id") or por_ruta[clave]["tenant_id"]
            if reg.get("description"):
                por_ruta[clave]["description"] = reg["description"]
            continue
        existe = ruta_p.is_dir()
        entrada = {
            "name": reg.get("name") or ruta_p.name,
            "tenant_id": reg.get("tenant_id") or reg.get("name") or ruta_p.name,
            "path": str(ruta_p),
            "origin": reg.get("origin") or "external",
            "version": _leer_version_baul(ruta_p) if existe else "",
            "git": (ruta_p / ".git").is_dir() if existe else False,
            "exists": existe,
            "has_access_policy": (ruta_p / RUTA_POLITICA_ACCESO).is_file() if existe else False,
            "aliases": list(reg.get("aliases") or []),
            "projects": list(reg.get("projects") or []),
        }
        if reg.get("description"):
            entrada["description"] = reg["description"]
        por_ruta[clave] = entrada
        resultado.append(entrada)

    return {
        "ok": True,
        "casa": str(casa_dir),
        "registry_path": str(ruta_registro_maestro(casa_dir)),
        "total": len(resultado),
        "master_count": sum(1 for v in resultado if v["origin"] == "master"),
        "external_count": sum(1 for v in resultado if v["origin"] != "master"),
        "vaults": resultado,
    }


# ---------------------------------------------------------------------------
# 2. Migracion segura verificada por SHA-256 (cero perdida)
# ---------------------------------------------------------------------------


def _manifiesto_sha256(raiz: Path) -> Tuple[Dict[str, str], int]:
    """Calcula SHA-256 de cada fichero de contenido bajo `raiz`."""
    hashes: Dict[str, str] = {}
    total_bytes = 0
    for actual, dirs, archivos in os.walk(raiz, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in _EXCLUIR_MANIFIESTO)
        base = Path(actual)
        for nombre in sorted(archivos):
            ruta = base / nombre
            if ruta.is_symlink():
                continue
            rel = ruta.relative_to(raiz).as_posix()
            datos = ruta.read_bytes()
            total_bytes += len(datos)
            hashes[rel] = hashlib.sha256(datos).hexdigest()
    return hashes, total_bytes


def _git_head_sha(raiz: Path) -> Optional[str]:
    if not (raiz / ".git").is_dir():
        return None
    res = procesos_git.ejecutar_git(raiz, ["rev-parse", "HEAD"], capture_output=True)
    return res.stdout.strip() if res.returncode == 0 else None


def verificar_migracion_baul(
    origen: "str | Path",
    destino: "str | Path",
    *,
    ejecutar: bool = False,
    registrar_en_casa: Optional[Path] = None,
    nombre_registro: Optional[str] = None,
) -> Dict[str, Any]:
    """Planifica o ejecuta la migracion de un baul completo con verificacion
    criptografica SHA-256 y paridad de HEAD Git. Nunca borra el origen."""
    src = Path(origen).expanduser().resolve()
    dst = Path(destino).expanduser().resolve()

    if not src.is_dir():
        return construir_error("vault_init", "VAULT_NOT_FOUND", f"Origen inexistente: {src}")
    if src == dst:
        return construir_error("vault_init", "INVALID_INPUT", "Origen y destino son iguales")
    if dst.is_relative_to(src):
        return construir_error("vault_init", "INVALID_INPUT", "Destino no puede vivir dentro del origen")
    if dst.exists() and any(dst.iterdir()):
        return construir_error("vault_init", "VAULT_EXISTS", f"Destino ya existe y no esta vacio: {dst}")

    hashes_origen, bytes_origen = _manifiesto_sha256(src)
    head_origen = _git_head_sha(src)

    plan = {
        "ok": True,
        "executed": False,
        "source": str(src),
        "destination": str(dst),
        "files_count": len(hashes_origen),
        "total_bytes": bytes_origen,
        "git_head_source": head_origen,
        "source_preserved": True,
    }
    if not ejecutar:
        return plan

    shutil.copytree(src, dst, symlinks=False, dirs_exist_ok=True)
    hashes_destino, bytes_destino = _manifiesto_sha256(dst)
    head_destino = _git_head_sha(dst)

    faltantes = sorted(set(hashes_origen) - set(hashes_destino))
    extras = sorted(set(hashes_destino) - set(hashes_origen))
    distintos = sorted(
        rel for rel in set(hashes_origen) & set(hashes_destino)
        if hashes_origen[rel] != hashes_destino[rel]
    )
    git_ok = head_origen == head_destino
    paridad_ok = not faltantes and not extras and not distintos and git_ok

    salida = {
        **plan,
        "ok": paridad_ok,
        "executed": True,
        "verified": paridad_ok,
        "destination_files_count": len(hashes_destino),
        "destination_bytes": bytes_destino,
        "git_head_destination": head_destino,
        "git_head_match": git_ok,
        "mismatches": {
            "missing": faltantes,
            "extra": extras,
            "hash_diff": distintos,
        },
    }
    if paridad_ok and registrar_en_casa is not None:
        reg = registrar_baul_maestro(
            nombre_registro or dst.name,
            dst,
            previous_path=str(src),
            allow_update=True,
            casa=registrar_en_casa,
        )
        salida["registry_updated"] = reg.get("ok", False)
    return salida


# ---------------------------------------------------------------------------
# 3. Identity & Politica Soberana Fail-Closed (`00_System/access-policy.json`)
# ---------------------------------------------------------------------------


def crear_plantilla_politica_acceso(
    grants: Sequence[Mapping[str, Any]] = (),
) -> Dict[str, Any]:
    """Construye una politica de acceso canonica cerrada por defecto."""
    return {
        "schema_version": SCHEMA_VERSION,
        "default": "deny",
        "grants": [dict(g) for g in grants],
    }


def validar_politica_acceso(politica: Mapping[str, Any]) -> List[str]:
    """Valida la estructura de `access-policy.json`; devuelve lista de errores."""
    errores: List[str] = []
    if not isinstance(politica, Mapping):
        return ["la politica debe ser un objeto JSON"]
    if politica.get("schema_version") != SCHEMA_VERSION:
        errores.append(f"schema_version debe ser {SCHEMA_VERSION}")
    if politica.get("default") != "deny":
        errores.append("default debe ser 'deny' (politica fail-closed obligatoria)")
    grants = politica.get("grants")
    if not isinstance(grants, list):
        errores.append("'grants' debe ser una lista")
        return errores

    for idx, g in enumerate(grants):
        pref = f"grants[{idx}]"
        if not isinstance(g, Mapping):
            errores.append(f"{pref}: debe ser un objeto")
            continue
        principal = g.get("principal")
        if not isinstance(principal, Mapping):
            errores.append(f"{pref}.principal: debe ser un objeto")
        else:
            vault_name = str(principal.get("vault") or "").strip()
            if not vault_name or vault_name == "*":
                errores.append(f"{pref}.principal.vault: obligatorio y no puede ser wildcard '*'")
            roles = principal.get("roles")
            if not isinstance(roles, list) or not roles:
                errores.append(f"{pref}.principal.roles: debe listar al menos un rol valido")
            else:
                invalidos = [r for r in roles if r not in ROLES_VALIDOS]
                if invalidos:
                    errores.append(f"{pref}.principal.roles: roles invalidos {invalidos!r}")
        mode = g.get("mode", "read_only")
        if mode not in MODOS_ACCESO_CRUZADO:
            errores.append(f"{pref}.mode: solo se permite {MODOS_ACCESO_CRUZADO!r} (AP-36)")
        max_sens = g.get("max_sensitivity", "internal")
        if max_sens not in _ORDEN_SENSIBILIDAD:
            errores.append(f"{pref}.max_sensitivity: invalido {max_sens!r}")
        for campo_lista in ("allowed_sections", "denied_sections", "allowed_tags"):
            if campo_lista in g and g[campo_lista] is not None:
                if not isinstance(g[campo_lista], list):
                    errores.append(f"{pref}.{campo_lista}: debe ser una lista")
        exp = g.get("expires_at")
        if exp is not None:
            try:
                _parsear_iso_utc(str(exp))
            except ValueError:
                errores.append(f"{pref}.expires_at: fecha ISO-8601 invalida {exp!r}")
    return errores


def leer_politica_acceso(raiz_destino: "str | Path") -> Optional[Dict[str, Any]]:
    """Lee `00_System/access-policy.json`. None si no existe; ValueError si corrupto."""
    ruta = Path(raiz_destino) / RUTA_POLITICA_ACCESO
    if not ruta.is_file():
        return None
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Politica de acceso ilegible en {ruta}: {exc}") from exc
    errores = validar_politica_acceso(datos)
    if errores:
        raise ValueError(f"Politica de acceso invalida en {ruta}: {'; '.join(errores)}")
    return datos


def escribir_politica_acceso(
    raiz_destino: "str | Path",
    politica: Mapping[str, Any],
) -> Path:
    """Valida y escribe atómicamente `00_System/access-policy.json` dentro del destino."""
    errores = validar_politica_acceso(politica)
    if errores:
        raise ValueError("Politica invalida: " + "; ".join(errores))
    destino = Path(raiz_destino).resolve() / RUTA_POLITICA_ACCESO
    _escribir_json_atomico(destino, politica)
    return destino


def _grant_aplica_a_principal(
    grant: Mapping[str, Any],
    principal: Principal,
    ahora: datetime,
) -> Tuple[bool, str]:
    p = grant.get("principal") or {}
    if str(p.get("vault") or "").strip() != principal.vault:
        return False, "vault_mismatch"
    roles = p.get("roles") or []
    if principal.role not in roles:
        return False, "role_not_granted"
    proyectos_permitidos = p.get("projects")
    if proyectos_permitidos:
        if not principal.project or principal.project not in proyectos_permitidos:
            return False, "project_not_granted"
    exp = grant.get("expires_at")
    if exp is not None and _parsear_iso_utc(str(exp)) < ahora:
        return False, "grant_expired"
    return True, "principal_matched"


def _grant_permite_recurso(
    grant: Mapping[str, Any],
    *,
    ruta_nota: Optional[str],
    tags_nota: Sequence[str],
    sensibilidad_nota: Optional[str],
) -> Tuple[bool, str]:
    max_sens = grant.get("max_sensitivity", "internal")
    # Conservador (fail-closed): nota sin sensibilidad declarada o desconocida
    # se trata como `restricted` al cruzar fronteras de baul.
    sens_ef = (sensibilidad_nota or "").strip().lower()
    if sens_ef not in _ORDEN_SENSIBILIDAD:
        sens_ef = "restricted"
    if _ORDEN_SENSIBILIDAD[sens_ef] > _ORDEN_SENSIBILIDAD[max_sens]:
        return False, f"sensitivity_exceeds_max:{sens_ef}>{max_sens}"

    if ruta_nota:
        rel = ruta_nota.replace("\\", "/").lstrip("/")
        seccion = rel.split("/", 1)[0] if "/" in rel else ""
        allowed_sec = list(grant.get("allowed_sections") or [])
        denied_sec = set(grant.get("denied_sections") or [])
        if seccion in denied_sec:
            return False, f"section_denied:{seccion}"
        if allowed_sec:
            if seccion not in allowed_sec:
                return False, f"section_not_allowed:{seccion}"
        elif seccion in SECCIONES_SENSIBLES_POR_DEFECTO:
            return False, f"sensitive_section_blocked_by_default:{seccion}"

    allowed_tags = {str(t).strip().lower() for t in (grant.get("allowed_tags") or []) if str(t).strip()}
    if allowed_tags:
        nota_tags = {str(t).strip().lower() for t in tags_nota if str(t).strip()}
        if not (nota_tags & allowed_tags):
            return False, "tag_not_allowed"

    return True, "authorized"


def evaluar_acceso_cruzado(
    principal: Principal,
    raiz_destino: "str | Path",
    *,
    ruta_nota: Optional[str] = None,
    tags_nota: Sequence[str] = (),
    sensibilidad_nota: Optional[str] = "internal",
    operacion: str = "read",
    ahora_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Evalua fail-closed si `principal` puede acceder a `raiz_destino`."""
    destino = Path(raiz_destino).resolve()
    target_name = destino.name
    base = {
        "principal": principal.como_dict(),
        "target_vault": target_name,
        "operation": operacion,
        "resource": ruta_nota,
    }

    if operacion != "read":
        return {**base, "allowed": False, "mode": "deny", "reason": "cross_vault_write_forbidden"}

    if principal.role not in ROLES_VALIDOS:
        return {**base, "allowed": False, "mode": "deny", "reason": "invalid_role"}

    if principal.vault == target_name:
        return {**base, "allowed": True, "mode": "read_only", "reason": "self_vault"}

    try:
        politica = leer_politica_acceso(destino)
    except ValueError as exc:
        return {
            **base,
            "allowed": False,
            "mode": "deny",
            "reason": "invalid_policy_fail_closed",
            "detail": str(exc),
        }

    if politica is None:
        return {**base, "allowed": False, "mode": "deny", "reason": "no_policy_fail_closed"}

    ahora = ahora_utc or datetime.now(timezone.utc)
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=timezone.utc)

    motivo_cercano = "no_matching_grant"
    for idx, grant in enumerate(politica.get("grants") or []):
        ok_p, r_p = _grant_aplica_a_principal(grant, principal, ahora)
        if not ok_p:
            if r_p in ("grant_expired", "role_not_granted", "project_not_granted"):
                motivo_cercano = r_p
            continue
        ok_r, r_r = _grant_permite_recurso(
            grant,
            ruta_nota=ruta_nota,
            tags_nota=tags_nota,
            sensibilidad_nota=sensibilidad_nota,
        )
        if ok_r:
            return {
                **base,
                "allowed": True,
                "mode": "read_only",
                "reason": "grant_matched",
                "grant_index": idx,
                "max_sensitivity": grant.get("max_sensitivity", "internal"),
            }
        motivo_cercano = r_r

    return {**base, "allowed": False, "mode": "deny", "reason": motivo_cercano}


def consultar_notas_autorizadas(
    principal: Principal,
    raiz_destino: "str | Path",
    *,
    query: str = "",
    folder: Optional[str] = None,
    max_results: int = 20,
    ahora_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Consulta de solo lectura filtrada por Identity y politica de acceso.

    Nunca revela rutas, titulos ni previews de notas denegadas (cero fuga de metadatos).
    """
    destino = Path(raiz_destino).resolve()
    if not destino.is_dir():
        return construir_error(
            "vault_search",
            "VAULT_NOT_FOUND",
            f"Baul destino no encontrado: {destino}",
            extra={"target_vault": destino.name, "results": []},
        )

    from .registry import secciones_del_vault

    secciones = secciones_del_vault(destino)
    notas = notas_en_disco(destino, secciones, incluir_indices=False)
    terminos = [t for t in (query or "").lower().split() if t]
    carpeta_norm = (folder or "").replace("\\", "/").strip("/")

    autorizadas: List[Dict[str, Any]] = []
    denegadas = 0

    for ruta in sorted(notas):
        rel = ruta.relative_to(destino).as_posix()
        if carpeta_norm and not (rel == carpeta_norm or rel.startswith(carpeta_norm + "/")):
            continue
        try:
            texto = ruta.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            denegadas += 1
            continue
        meta = parse_frontmatter(texto) or {}
        tags = meta.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        sensibilidad = meta.get("cia_sensitivity")

        decision = evaluar_acceso_cruzado(
            principal,
            destino,
            ruta_nota=rel,
            tags_nota=tags,
            sensibilidad_nota=sensibilidad,
            operacion="read",
            ahora_utc=ahora_utc,
        )
        if not decision["allowed"]:
            denegadas += 1
            continue

        titulo = str(meta.get("title") or ruta.stem)
        cuerpo = separar_frontmatter(texto)[1]
        texto_buscable = f"{titulo}\n{' '.join(str(t) for t in tags)}\n{cuerpo}".lower()
        if terminos and not all(t in texto_buscable for t in terminos):
            continue

        autorizadas.append({
            "path": rel,
            "title": titulo,
            "tags": list(tags),
            "cia_sensitivity": sensibilidad or "internal",
            "preview": cuerpo.strip()[:200].replace("\n", " "),
        })
        if len(autorizadas) >= max(1, int(max_results)):
            break

    return {
        "ok": True,
        "mode": "read_only",
        "principal": principal.como_dict(),
        "target_vault": destino.name,
        "returned": len(autorizadas),
        "filtered_by_policy": denegadas,
        "results": autorizadas,
    }
