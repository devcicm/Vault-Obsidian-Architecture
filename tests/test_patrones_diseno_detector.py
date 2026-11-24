r"""Fase D (TDD): detector de patrones de diseno y arquitectura (interno y externo).

Verifica que el dueno unico `vault.autoria.patrones_diseno` y las tools
`vault_pattern_list` (lectura CQRS) y `vault_pattern_save` (escritura CQRS):
- publican un catalogo canonico, categorizado y ordenado en 5 categorias;
- detectan patrones reales por AST (Python) y reglas estructurales conservadoras
  (JS/TS/otros) sobre repositorios externos e internos sin filtrar rutas de maquina;
- cumplen AP-45 (archivo plano sin patrones -> 0 detecciones, cero alucinacion);
- detectan patrones reales del propio `Vault-Obsidian-Architecture`;
- cruzan contra `05_Patterns/index.json` (`registrado` vs `nuevo`);
- permiten persistir los patrones detectados con evidencia en `05_Patterns/` via
  `vault_pattern_save --scan-path`;
- pasan preflight de `vault run` con `--scan-path` apuntando a un repo externo (AP-36).
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from apoyo import ROOT, SCRIPTS, correr_python, correr_tool


def _cli(vault: Path, script: str, *args: str):
    return correr_tool(script, *args, vault=vault, cwd=SCRIPTS)


def _vault_demo(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "00_System").mkdir(parents=True)
    assert _cli(vault, "vault_project.py", "--add", "demo").envelope["ok"]
    return vault


def _repo_externo_sintetico(tmp_path: Path) -> Path:
    """Repositorio externo fuera del vault con patrones reales en Python y JS."""
    repo = tmp_path / "repo-externo"
    (repo / "src").mkdir(parents=True)
    (repo / "web").mkdir(parents=True)

    (repo / "src" / "domain.py").write_text(
        textwrap.dedent(
            """\
            from abc import ABC, abstractmethod
            import os
            import threading

            VALID_TRANSITIONS = {
                'draft': ['active'],
                'active': ['archived'],
            }

            RANKINGS = {
                'default': lambda x: x,
                'bm25': lambda x: x * 2,
            }

            class OrderRepository:
                def get(self, oid: str):
                    return None

            class PaymentAdapter:
                def charge(self, amount: int):
                    return amount

            class ReportBuilder:
                def add_title(self, t: str):
                    return self
                def build(self) -> str:
                    return 'ok'

            class BasePipeline(ABC):
                def execute(self):
                    return self._step()
                @abstractmethod
                def _step(self):
                    raise NotImplementedError

            _LOCK = threading.Lock()

            def atomic_save(tmp_path: str, dest: str):
                os.replace(tmp_path, dest)
            """
        ),
        encoding="utf-8",
    )

    (repo / "web" / "coordinator.mjs").write_text(
        textwrap.dedent(
            """\
            export class AsyncRWCoordinator {
              run(mode, fn) { return fn(); }
            }
            export class UserRepository {
              find(id) { return id; }
            }
            export const ROUTES = {
              'items/list': () => [],
            };
            """
        ),
        encoding="utf-8",
    )
    return repo


def test_catalogo_canonico_tiene_5_categorias_ordenadas():
    from vault.autoria.patrones_diseno import CATALOGO_PATRONES, CATEGORIAS

    assert CATEGORIAS == (
        "arquitectonicos",
        "creacionales",
        "estructurales",
        "comportamiento",
        "concurrencia_resiliencia",
    )
    assert len(CATALOGO_PATRONES) >= 24
    cats = {p["category"] for p in CATALOGO_PATRONES}
    assert cats == set(CATEGORIAS)
    ordenes = [p["order"] for p in CATALOGO_PATRONES]
    assert ordenes == sorted(ordenes, key=lambda o: tuple(int(x) for x in o.split(".")))


def test_detector_en_repo_externo_detecta_patrones_python_y_js_sin_fuga_de_rutas(tmp_path):
    from vault.autoria.patrones_diseno import detectar_patrones

    repo = _repo_externo_sintetico(tmp_path)
    res = detectar_patrones(repo)

    assert res["ok"] is True
    assert res["files_scanned"] == 2
    nombres = {p["pattern"] for p in res["patterns"]}
    esperados = {
        "Repository",
        "Adapter",
        "Builder",
        "Template Method",
        "State Machine",
        "Strategy",
        "Atomic Write",
        "Reentrant & Cross-Process Lock",
        "CQRS",
        "Command + Dispatch Router",
    }
    assert esperados.issubset(nombres), f"Faltaron: {esperados - nombres}; detectados: {nombres}"

    raiz_str = str(repo.resolve()).replace("\\", "/")
    for p in res["patterns"]:
        assert p["evidence"], f"Patron sin evidencia (AP-45): {p}"
        for ev in p["evidence"]:
            assert raiz_str not in ev["file"], f"Fuga de ruta absoluta: {ev}"
            assert not Path(ev["file"]).is_absolute(), ev
            assert isinstance(ev["line"], int) and ev["line"] >= 1
            assert ev["symbol"] and ev["how"]


def test_detector_negativo_ap45_no_alucina_en_archivo_simple(tmp_path):
    from vault.autoria.patrones_diseno import detectar_patrones

    repo = tmp_path / "repo-plano"
    repo.mkdir()
    (repo / "math_utils.py").write_text(
        textwrap.dedent(
            """\
            def sumar(a: int, b: int) -> int:
                return a + b

            def multiplicar(a: int, b: int) -> int:
                return a * b
            """
        ),
        encoding="utf-8",
    )
    res = detectar_patrones(repo)
    assert res["ok"] is True
    assert res["files_scanned"] == 1
    assert res["total_patterns"] == 0, res["patterns"]
    assert res["patterns"] == []


def test_detector_sobre_vault_obsidian_architecture_encuentra_patrones_reales():
    from vault.autoria.patrones_diseno import detectar_patrones

    res = detectar_patrones(ROOT)
    assert res["ok"] is True
    assert res["files_scanned"] >= 100
    nombres = {p["pattern"] for p in res["patterns"]}
    nucleo_real = {
        "Bounded Contexts (DDD)",
        "Hexagonal / Ports & Adapters",
        "CQRS",
        "Append-Only Event Log",
        "Single Source of Truth / Registry",
        "Builder",
        "Repository",
        "Adapter",
        "Module Alias / Facade",
        "Template Method",
        "State Machine",
        "Strategy",
        "Command + Dispatch Router",
        "Envelope / Result Object",
        "Atomic Write",
        "Reentrant & Cross-Process Lock",
    }
    assert nucleo_real.issubset(nombres), f"Faltaron: {nucleo_real - nombres}"


def test_vault_pattern_list_catalog_y_scan_path_con_cruce_de_vault(tmp_path):
    vault = _vault_demo(tmp_path)
    repo = _repo_externo_sintetico(tmp_path)

    # 1. --catalog funciona sin indice previo
    cat = _cli(vault, "vault_pattern_list.py", "--catalog").envelope
    assert cat["ok"] is True, cat
    assert cat["mode"] == "catalog"
    assert len(cat["categories"]) == 5
    assert cat["total_catalog"] >= 24

    # 2. Registrar Repository en el vault y luego escanear el repo externo
    assert _cli(
        vault,
        "vault_pattern_save.py",
        "--project", "demo",
        "--name", "Repository",
        "--type", "design",
        "--status", "implementado",
    ).envelope["ok"]

    det = _cli(vault, "vault_pattern_list.py", "--scan-path", str(repo)).envelope
    assert det["ok"] is True, det
    assert det["mode"] == "detect"
    assert det["total_patterns"] >= 8
    por_nombre = {p["pattern"]: p for p in det["patterns"]}
    assert por_nombre["Repository"]["vault_status"] == "registrado"
    assert por_nombre["Adapter"]["vault_status"] == "nuevo"

    # 3. Filtro por categoria
    solo_est = _cli(
        vault,
        "vault_pattern_list.py",
        "--scan-path", str(repo),
        "--category", "estructurales",
    ).envelope
    assert solo_est["ok"] is True
    assert {p["category"] for p in solo_est["patterns"]} == {"estructurales"}


def test_vault_pattern_save_scan_path_persiste_patrones_detectados_y_es_idempotente(tmp_path):
    vault = _vault_demo(tmp_path)
    repo = _repo_externo_sintetico(tmp_path)

    r1 = _cli(
        vault,
        "vault_pattern_save.py",
        "--project", "demo",
        "--scan-path", str(repo),
        "--category", "estructurales",
    )
    env1 = r1.envelope
    assert r1.codigo == 0 and env1["ok"] is True, env1
    assert env1["action"] == "detect-and-save"
    assert env1["saved_count"] >= 2
    guardados = {s["pattern"] for s in env1["saved"]}
    assert {"Repository", "Adapter"}.issubset(guardados)

    # Verificar que se crearon notas reales con evidencia y se actualizo el indice
    indice = json.loads((vault / "05_Patterns" / "index.json").read_text(encoding="utf-8"))
    nombres_idx = {e["pattern"] for e in indice["patterns"]}
    assert {"Repository", "Adapter"}.issubset(nombres_idx)
    nota_repo = vault / "05_Patterns" / "design" / "demo-repository.md"
    assert nota_repo.is_file()
    texto_nota = nota_repo.read_text(encoding="utf-8")
    assert "src/domain.py" in texto_nota and "OrderRepository" in texto_nota

    # Re-escanear sobre el mismo proyecto no falla por transicion de estado
    r2 = _cli(
        vault,
        "vault_pattern_save.py",
        "--project", "demo",
        "--scan-path", str(repo),
        "--category", "estructurales",
    )
    assert r2.codigo == 0 and r2.envelope["ok"] is True, r2.envelope


def test_vault_run_acepta_scan_path_externo_en_preflight(tmp_path):
    rt = tmp_path / "rt"
    p_init = correr_python("-m", "vault", "init", rt)
    assert p_init.returncode == 0, p_init.stderr[-1000:]

    repo = _repo_externo_sintetico(tmp_path)
    p = correr_python(
        "-m", "vault", "run", "vault_pattern_list",
        "--scan-path", str(repo.resolve()),
        vault=rt,
    )
    salida = p.stdout if "{" in p.stdout else p.stderr
    env = json.loads(salida[salida.index("{"):])
    assert env.get("error_code") != "PREFLIGHT_REJECTED", env
    assert p.returncode == 0 and env["ok"] is True, env
    assert env["total_patterns"] >= 8


def test_catalogo_oficial_tiene_35_patrones_con_nombre_oficial_y_referencia_estandar(tmp_path):
    from vault.autoria.patrones_diseno import CATALOGO_PATRONES, catalogo_ordenado, detectar_patrones

    assert len(CATALOGO_PATRONES) == 35
    cat = catalogo_ordenado()
    assert cat["total_catalog"] == 35
    for p in cat["patterns"]:
        assert p.get("official_name"), p
        assert p.get("reference"), p

    # Repositorio sintetico con arquitectura Clean + Layered + 8 nuevos patrones de industria
    repo = tmp_path / "app-enterprise"
    for carpeta in ("src/controllers", "src/services", "src/domain", "src/use_cases", "src/adapters", "src/repositories"):
        (repo / carpeta).mkdir(parents=True)

    (repo / "src" / "controllers" / "orders.py").write_text("def list_orders(): return []\n", encoding="utf-8")
    (repo / "src" / "services" / "plugins.py").write_text(
        textwrap.dedent(
            """\
            from functools import wraps

            class AuthDecorator:
                pass

            def audit_decorator(fn):
                @wraps(fn)
                def wrapper(*a, **k):
                    return fn(*a, **k)
                return wrapper

            class PluginRegistry:
                pass

            class OrderEventBroker:
                pass

            class ValidationFilter:
                pass

            class AppDIContainer:
                pass

            class PaymentCircuitBreaker:
                pass

            def retry_with_backoff(fn):
                return fn()
            """
        ),
        encoding="utf-8",
    )
    (repo / "src" / "domain" / "specs.py").write_text(
        textwrap.dedent(
            """\
            class ActiveOrderSpecification:
                def is_satisfied_by(self, order):
                    return True
            """
        ),
        encoding="utf-8",
    )
    (repo / "src" / "use_cases" / "uow.py").write_text(
        textwrap.dedent(
            """\
            class SqlUnitOfWork:
                def __enter__(self): return self
                def __exit__(self, *a): pass
                def commit(self): pass
                def rollback(self): pass
            """
        ),
        encoding="utf-8",
    )
    (repo / "src" / "adapters" / "http.py").write_text("class HttpAdapter:\n    pass\n", encoding="utf-8")
    (repo / "src" / "repositories" / "orders_repo.py").write_text("class OrdersRepository:\n    pass\n", encoding="utf-8")

    det = detectar_patrones(repo)
    assert det["ok"] is True
    ids = {p["id"] for p in det["patterns"]}
    for esperado in (
        "layered-architecture",
        "clean-architecture",
        "event-driven-architecture",
        "microkernel-plugin",
        "pipe-and-filter",
        "dependency-injection",
        "decorator",
        "specification",
        "unit-of-work",
        "circuit-breaker-retry",
    ):
        assert esperado in ids, f"Falto detectar {esperado}: {sorted(ids)}"
    for item in det["patterns"]:
        assert item.get("official_name") and item.get("reference"), item
