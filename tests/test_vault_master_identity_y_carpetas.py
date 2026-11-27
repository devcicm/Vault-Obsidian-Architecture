"""TDD integral: Registro Maestro, Identity fail-closed, paridad MCP, carpetas recursivas y PAT-10 (72).

Verifica:
1. Registro Maestro (`<VAULT_MASTER>/registry.json`): inventario unificado de
   baules internos + externos, corrupcion fail-closed (AP-51) y `vault_init --list`.
2. Migracion verificada por SHA-256 + paridad HEAD Git (sin borrar origen).
3. Identity & Politica de acceso soberana (`00_System/access-policy.json`):
   fail-closed por defecto, solo lectura entre baules (AP-36), filtrado por
   vault/rol/proyecto/seccion/tags/sensibilidad CIA/expiracion y cero fuga de
   metadatos en `consultar_notas_autorizadas`.
4. Paridad MCP (`vault-mcp-server.mjs`): descubrimiento de `VAULT_MASTER` sin
   prefijo `vault-` + baules externos en `registry.json` + `.vault-path`.
5. Carpetas recursivas a profundidad 3+ sin colar prefijos `_`/`.` y
   `vault_section --add --subfolders --sync` integrando nodos, aristas y busqueda.
6. Patrones `identity-access-management` y `multi-tenancy-isolation` en PAT-10 (72).
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import textwrap

import pytest

from apoyo import SCRIPTS, correr_tool, entorno
from test_mcp_runner import SesionMCP
from vault_version import CURRENT_VERSION


def _vault_minimo(ruta: Path) -> Path:
    """Crea una estructura minima de vault valida en ~1ms para pruebas TDD rapidas."""
    for sec in ("00_System", "01_Projects", "08_Runbooks", "09_Infrastructure", "99_Index"):
        (ruta / sec).mkdir(parents=True, exist_ok=True)
    (ruta / "00_System" / "standard-version.json").write_text(
        json.dumps({"applied_version": CURRENT_VERSION}, indent=2),
        encoding="utf-8",
    )
    return ruta


def _escribir_nota(ruta: Path, *, title: str, tags: list[str], sensitivity: str | None, cuerpo: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    sens_linea = f"cia_sensitivity: {sensitivity}\n" if sensitivity is not None else ""
    contenido = (
        "---\n"
        f'title: "{title}"\n'
        "createdAt: 2026-11-26T00:00:00Z\n"
        "updatedAt: 2026-11-26T00:00:00Z\n"
        f"{sens_linea}"
        f"tags: {json.dumps(tags)}\n"
        "---\n\n"
        f"{cuerpo}\n"
    )
    ruta.write_text(contenido, encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Registro Maestro y Migracion Verificada
# ---------------------------------------------------------------------------


def test_registro_maestro_unifica_baules_master_y_externos_y_vault_init_list(tmp_path):
    from vault.kernel.acceso_baules import (
        leer_registro_maestro,
        listar_ecosistema_baules,
        registrar_baul_maestro,
    )

    casa = tmp_path / ".vault-master"
    baul_master = _vault_minimo(casa / "infraestructura-redes")
    baul_externo = _vault_minimo(tmp_path / "proyectos" / "vault-dev-codex")

    res_reg = registrar_baul_maestro(
        "vault-dev-codex",
        baul_externo,
        alias=["codex"],
        proyectos=["voa"],
        descripcion="Baul externo de arquitectura",
        casa=casa,
    )
    assert res_reg["ok"] is True
    assert res_reg["vault"]["origin"] == "external"

    eco = listar_ecosistema_baules(casa)
    assert eco["ok"] is True
    assert eco["master_count"] == 1
    assert eco["external_count"] == 1
    por_nombre = {v["name"]: v for v in eco["vaults"]}
    assert por_nombre["infraestructura-redes"]["origin"] == "master"
    assert por_nombre["vault-dev-codex"]["origin"] == "external"
    assert por_nombre["vault-dev-codex"]["projects"] == ["voa"]

    # CLI `vault_init --list` expone tanto master como external_vaults
    env_cli = entorno(baul_master)
    env_cli["VAULT_MASTER"] = str(casa)
    out = correr_tool(
        "vault_init.py",
        "--list",
        vault=baul_master,
        cwd=SCRIPTS,
        env=env_cli,
    )
    assert out.returncode == 0
    assert out.envelope["ok"] is True
    assert out.envelope["total"] == 1
    assert out.envelope["external_total"] == 1
    assert out.envelope["external_vaults"][0]["name"] == "vault-dev-codex"

    # AP-51: registro corrupto lanza ValueError en vez de devolver vacio
    (casa / "registry.json").write_text("{corrupto", encoding="utf-8")
    with pytest.raises(ValueError, match="Registro maestro ilegible"):
        leer_registro_maestro(casa)


def test_migracion_verificada_sha256_preserva_origen_y_registra_en_master(tmp_path):
    from vault.kernel.acceso_baules import leer_registro_maestro, verificar_migracion_baul

    casa = tmp_path / ".vault-master"
    origen = _vault_minimo(tmp_path / "externo-red")
    _escribir_nota(
        origen / "08_Runbooks" / "bgp-failover.md",
        title="BGP Failover",
        tags=["redes", "bgp"],
        sensitivity="internal",
        cuerpo="Procedimiento de failover BGP.",
    )
    destino = casa / "infraestructura-redes"

    # Dry-run: no escribe destino
    plan = verificar_migracion_baul(origen, destino, ejecutar=False)
    assert plan["ok"] is True
    assert plan["executed"] is False
    assert plan["files_count"] >= 1
    assert not destino.exists()

    # Ejecucion real: paridad 100% SHA-256 + origen intacto + registro actualizado
    hecho = verificar_migracion_baul(
        origen,
        destino,
        ejecutar=True,
        registrar_en_casa=casa,
        nombre_registro="infraestructura-redes",
    )
    assert hecho["ok"] is True
    assert hecho["verified"] is True
    assert hecho["mismatches"] == {"missing": [], "extra": [], "hash_diff": []}
    assert (origen / "08_Runbooks" / "bgp-failover.md").is_file()
    assert (destino / "08_Runbooks" / "bgp-failover.md").is_file()
    reg = leer_registro_maestro(casa)
    assert any(v["name"] == "infraestructura-redes" and v["origin"] == "master" for v in reg["vaults"])

    # No pisa destino existente (contrato AP-52)
    repetido = verificar_migracion_baul(origen, destino, ejecutar=True)
    assert repetido["ok"] is False
    assert repetido["error_code"] == "VAULT_EXISTS"


# ---------------------------------------------------------------------------
# 2. Identity & Politica Fail-Closed entre Baules (`infraestructura-redes`)
# ---------------------------------------------------------------------------


def test_identity_y_politica_fail_closed_infraestructura_redes(tmp_path):
    from vault.kernel.acceso_baules import (
        Principal,
        consultar_notas_autorizadas,
        crear_plantilla_politica_acceso,
        escribir_politica_acceso,
        evaluar_acceso_cruzado,
        validar_politica_acceso,
    )

    redes = _vault_minimo(tmp_path / "infraestructura-redes")
    _escribir_nota(
        redes / "08_Runbooks" / "vlan-core.md",
        title="Runbook VLAN Core",
        tags=["redes", "vlan"],
        sensitivity="internal",
        cuerpo="Topologia VLAN core autorizada para lectura interna.",
    )
    _escribir_nota(
        redes / "08_Runbooks" / "firewall-secrets.md",
        title="Credenciales Firewall",
        tags=["redes", "firewall"],
        sensitivity="confidential",
        cuerpo="Reglas confidenciales del firewall perimetral.",
    )
    _escribir_nota(
        redes / "08_Runbooks" / "sin-clasificar.md",
        title="Nota sin sensibilidad",
        tags=["redes"],
        sensitivity=None,
        cuerpo="Sin cia_sensitivity declarada.",
    )
    _escribir_nota(
        redes / "09_Infrastructure" / "core-router.md",
        title="Router Core",
        tags=["redes"],
        sensitivity="internal",
        cuerpo="Inventario privado de infraestructura.",
    )

    lector_codex = Principal(vault="vault-dev-codex", role="lector", project="voa")
    ejecutor_codex = Principal(vault="vault-dev-codex", role="ejecutor", project="voa")
    intruso = Principal(vault="agente", role="operador")

    # 1. Sin politica -> fail-closed
    d0 = evaluar_acceso_cruzado(lector_codex, redes, ruta_nota="08_Runbooks/vlan-core.md")
    assert d0["allowed"] is False
    assert d0["reason"] == "no_policy_fail_closed"

    # 2. Validacion rechaza default abierto, wildcard `*` y modo write
    assert validar_politica_acceso({"schema_version": 1, "default": "allow", "grants": []})
    assert validar_politica_acceso(
        crear_plantilla_politica_acceso([
            {"principal": {"vault": "*", "roles": ["lector"]}, "mode": "read_only"}
        ])
    )
    assert validar_politica_acceso(
        crear_plantilla_politica_acceso([
            {"principal": {"vault": "vault-dev-codex", "roles": ["lector"]}, "mode": "read_write"}
        ])
    )

    # 3. Politica soberana en `infraestructura-redes`
    politica = crear_plantilla_politica_acceso([
        {
            "principal": {"vault": "vault-dev-codex", "roles": ["lector", "operador"], "projects": ["voa"]},
            "mode": "read_only",
            "allowed_sections": ["08_Runbooks"],
            "denied_sections": ["00_System", "17_Preferences"],
            "allowed_tags": ["redes"],
            "max_sensitivity": "internal",
            "expires_at": "2026-12-31T23:59:59Z",
        }
    ])
    escribir_politica_acceso(redes, politica)
    ahora_valido = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
    ahora_expirado = datetime(2027, 1, 1, 0, 0, tzinfo=timezone.utc)

    # Escritura cruzada siempre prohibida (AP-36)
    d_write = evaluar_acceso_cruzado(lector_codex, redes, ruta_nota="08_Runbooks/vlan-core.md", operacion="write")
    assert d_write["allowed"] is False
    assert d_write["reason"] == "cross_vault_write_forbidden"

    # Acceso autorizado
    d_ok = evaluar_acceso_cruzado(
        lector_codex, redes,
        ruta_nota="08_Runbooks/vlan-core.md", tags_nota=["redes"], sensibilidad_nota="internal",
        ahora_utc=ahora_valido,
    )
    assert d_ok["allowed"] is True
    assert d_ok["mode"] == "read_only"

    # Bloqueo por rol, baul, sensibilidad, seccion y expiracion
    assert evaluar_acceso_cruzado(ejecutor_codex, redes, ruta_nota="08_Runbooks/vlan-core.md", tags_nota=["redes"], ahora_utc=ahora_valido)["allowed"] is False
    assert evaluar_acceso_cruzado(intruso, redes, ruta_nota="08_Runbooks/vlan-core.md", tags_nota=["redes"], ahora_utc=ahora_valido)["allowed"] is False
    assert evaluar_acceso_cruzado(lector_codex, redes, ruta_nota="08_Runbooks/firewall-secrets.md", tags_nota=["redes"], sensibilidad_nota="confidential", ahora_utc=ahora_valido)["allowed"] is False
    assert evaluar_acceso_cruzado(lector_codex, redes, ruta_nota="09_Infrastructure/core-router.md", tags_nota=["redes"], sensibilidad_nota="internal", ahora_utc=ahora_valido)["allowed"] is False
    assert evaluar_acceso_cruzado(lector_codex, redes, ruta_nota="08_Runbooks/vlan-core.md", tags_nota=["redes"], ahora_utc=ahora_expirado)["reason"] == "grant_expired"

    # Consulta filtrada: solo devuelve la nota autorizada; cero fuga de confidenciales ni sin clasificar
    consulta = consultar_notas_autorizadas(lector_codex, redes, query="redes", ahora_utc=ahora_valido)
    assert consulta["ok"] is True
    assert consulta["returned"] == 1
    assert consulta["results"][0]["path"] == "08_Runbooks/vlan-core.md"
    assert consulta["filtered_by_policy"] >= 3
    serializado = json.dumps(consulta, ensure_ascii=False)
    assert "Credenciales Firewall" not in serializado
    assert "Router Core" not in serializado


# ---------------------------------------------------------------------------
# 3. Paridad MCP (`VAULT_MASTER` + `registry.json` + `.vault-path`)
# ---------------------------------------------------------------------------


def test_mcp_descubre_vault_master_sin_prefijo_y_externos_en_registry(tmp_path):
    from vault.kernel.acceso_baules import (
        crear_plantilla_politica_acceso,
        escribir_politica_acceso,
        registrar_baul_maestro,
    )

    casa = tmp_path / ".vault-master"
    redes = _vault_minimo(casa / "infraestructura-redes")
    escribir_politica_acceso(redes, crear_plantilla_politica_acceso([]))
    externo = _vault_minimo(tmp_path / "externos" / "mi-baul-custom")
    registrar_baul_maestro("mi-baul-custom", externo, casa=casa)

    por_defecto = _vault_minimo(tmp_path / "activo")
    sesion = SesionMCP(
        por_defecto,
        {"VAULT_MASTER": str(casa), "VAULT_SCAN_ROOTS": str(tmp_path / "vacio")},
    )
    try:
        resp = sesion.llamar("vault_registry", {})
    finally:
        sesion.cerrar()

    datos = json.loads(resp["result"]["content"][0]["text"])
    por_nombre = {v["name"]: v for v in datos["vaults"]}
    assert "infraestructura-redes" in por_nombre, datos
    assert por_nombre["infraestructura-redes"]["origin"] == "master"
    assert por_nombre["infraestructura-redes"]["has_access_policy"] is True
    assert "mi-baul-custom" in por_nombre, datos
    assert por_nombre["mi-baul-custom"]["origin"] == "external"
    assert por_nombre["mi-baul-custom"]["has_access_policy"] is False


# ---------------------------------------------------------------------------
# 4. Carpetas recursivas + `vault_section --add --subfolders --sync`
# ---------------------------------------------------------------------------


def test_carpetas_recursivas_y_vault_section_sync_integran_grafo_y_busqueda(tmp_path):
    from vault.indices.carpetas import ServicioCarpetas
    from vault.indices.repositorio import RepositorioIndices
    from vault.kernel import construir

    vault = _vault_minimo(tmp_path / "vault-redes")

    # 1. Crear seccion propia con subcarpetas de profundidad 3 + sync atomico
    res_sec = correr_tool(
        "vault_section.py",
        "--add", "22_Redes",
        "--documentacion", "referencia",
        "--description", "Topologia y operacion de redes",
        "--tipos", "network-topology,vlan-spec",
        "--subfolders", "switches/core/vlans,firewalls/perimetro",
        "--sync",
        "--json",
        vault=vault,
        cwd=SCRIPTS,
    )
    assert res_sec.returncode == 0, res_sec.stderr
    assert res_sec.envelope["ok"] is True
    assert "22_Redes/switches/core/vlans" in res_sec.envelope["subfolders_created"]
    assert res_sec.envelope["sync"]["ok"] is True
    assert (vault / "22_Redes" / "index.md").is_file()
    assert (vault / "99_Index" / "graph.json").is_file()
    assert (vault / "99_Index" / "search-index.json").is_file()

    # 2. Verificar que profundidad 3+ aparece y que `_attachments`/`.oculto` en nivel 2 NO se cuelan
    (vault / "22_Redes" / "switches" / "_attachments").mkdir(parents=True)
    (vault / "22_Redes" / "switches" / ".privado").mkdir(parents=True)
    carpetas = ServicioCarpetas(RepositorioIndices(construir(vault))).detectar()
    rutas_detectadas = {c["path"] for c in carpetas}
    assert "22_Redes/switches" in rutas_detectadas
    assert "22_Redes/switches/core" in rutas_detectadas
    assert "22_Redes/switches/core/vlans" in rutas_detectadas
    assert "22_Redes/firewalls/perimetro" in rutas_detectadas
    assert "22_Redes/switches/_attachments" not in rutas_detectadas
    assert "22_Redes/switches/.privado" not in rutas_detectadas

    # 3. Escribir notas en profundidad 3 con wikilinks mutuos y reindexar grafo + busqueda
    _escribir_nota(
        vault / "22_Redes" / "switches" / "core" / "vlans" / "vlan-100.md",
        title="VLAN 100 Produccion",
        tags=["redes", "vlan"],
        sensitivity="internal",
        cuerpo="Enrutada por [[fw-edge-01|Firewall Perimetral]].",
    )
    _escribir_nota(
        vault / "22_Redes" / "firewalls" / "perimetro" / "fw-edge-01.md",
        title="Firewall Perimetral",
        tags=["redes", "firewall"],
        sensitivity="internal",
        cuerpo="Protege la [[vlan-100|VLAN 100 Produccion]].",
    )
    res_re = correr_tool("vault_reindex.py", "--graph", vault=vault, cwd=SCRIPTS)
    assert res_re.returncode == 0, res_re.stderr

    grafo = json.loads((vault / "99_Index" / "graph.json").read_text(encoding="utf-8"))
    assert "22_Redes/switches/core/vlans/vlan-100.md" in grafo["nodes"]
    assert "22_Redes/firewalls/perimetro/fw-edge-01.md" in grafo["nodes"]
    aristas = {(e["from"], e["to"]) for e in grafo["edges"]}
    assert (
        "22_Redes/switches/core/vlans/vlan-100.md",
        "22_Redes/firewalls/perimetro/fw-edge-01.md",
    ) in aristas
    assert (
        "22_Redes/firewalls/perimetro/fw-edge-01.md",
        "22_Redes/switches/core/vlans/vlan-100.md",
    ) in aristas

    # Busqueda filtrada por subcarpeta profunda
    res_search = correr_tool(
        "vault_search.py",
        "--query", "VLAN 100",
        "--folder", "22_Redes/switches/core/vlans",
        vault=vault,
        cwd=SCRIPTS,
    )
    assert res_search.returncode == 0
    rutas_busq = [r["path"] for r in res_search.envelope.get("results", [])]
    assert "22_Redes/switches/core/vlans/vlan-100.md" in rutas_busq

    # 4. Retirar la seccion NO borra notas ni rompe aristas
    res_ret = correr_tool(
        "vault_section.py", "--retire", "22_Redes", "--json", vault=vault, cwd=SCRIPTS
    )
    assert res_ret.returncode == 0
    assert res_ret.envelope["status"] == "retirada"
    res_re2 = correr_tool("vault_reindex.py", "--graph", vault=vault, cwd=SCRIPTS)
    assert res_re2.returncode == 0
    grafo2 = json.loads((vault / "99_Index" / "graph.json").read_text(encoding="utf-8"))
    assert "22_Redes/switches/core/vlans/vlan-100.md" in grafo2["nodes"]


# ---------------------------------------------------------------------------
# 5. Patrones Identity y Multi-Tenancy en PAT-10 (Python + TS + AP-45 negativo)
# ---------------------------------------------------------------------------


def test_pat10_detecta_identity_y_multi_tenancy_sin_falsos_positivos(tmp_path):
    from vault.autoria.patrones_diseno import detectar_patrones

    repo = tmp_path / "iam-saas"
    (repo / "py").mkdir(parents=True)
    (repo / "ts").mkdir(parents=True)
    (repo / "plain").mkdir(parents=True)

    (repo / "py" / "auth.py").write_text(
        textwrap.dedent(
            """\
            class OidcIdentityProvider:
                def authenticate(self, token): return True
                def authorize(self, principal, resource): return True

            class RequestTenantContext:
                def __init__(self, tenant_id: str):
                    self.tenant_id = tenant_id
            """
        ),
        encoding="utf-8",
    )
    (repo / "ts" / "tenant.ts").write_text(
        textwrap.dedent(
            """\
            export class HeaderTenantResolver {
              resolveTenant(req: unknown) { return 't1'; }
            }
            export class JwtAccessPolicyEngine {
              authorizePrincipal(p: unknown) { return true; }
            }
            """
        ),
        encoding="utf-8",
    )
    (repo / "plain" / "util.py").write_text("def sumar(a, b):\n    return a + b\n", encoding="utf-8")

    det = detectar_patrones(repo)
    assert det["ok"] is True
    por_id = {p["id"]: p for p in det["patterns"]}
    assert "identity-access-management" in por_id
    assert "multi-tenancy-isolation" in por_id
    assert any(f.endswith("auth.py") for f in por_id["identity-access-management"]["files"])
    assert any(f.endswith("tenant.ts") for f in por_id["multi-tenancy-isolation"]["files"])

    # AP-45: archivo simple sin patrones -> 0 detecciones
    det_plain = detectar_patrones(repo / "plain" / "util.py")
    assert det_plain["total_patterns"] == 0
