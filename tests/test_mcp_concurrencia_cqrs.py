"""TDD Fase C: coordinador CQRS lectura/escritura asíncrono y mantenimiento del MCP.

Prueba contra el servidor MCP real (`mcp/nodejs/vault-mcp-server.mjs`):
1. Lecturas paralelas acotadas por `maxReads` (`VAULT_MCP_MAX_READS`).
2. Escrituras serializadas por carpeta y paralelas entre carpetas distintas.
3. Barrera global exclusiva (`vault_backup`, `vault_reindex`, etc.) sin inanición.
4. Liberación garantizada en `finally` ante excepciones (cero deadlocks).
5. Clasificación `accessModeDe` y clave de recurso desde `tools-catalog.json`.
6. Higiene documental y estructural del MCP (sin SECCIÓN 7 duplicada, PLAN histórico,
   roadmap alineado con AP-48).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from apoyo import ROOT

SERVER = ROOT / "mcp" / "nodejs" / "vault-mcp-server.mjs"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="el servidor MCP necesita Node en el PATH"
)


def _node_eval(codigo: str) -> dict:
    url = SERVER.as_uri()
    script = f'const mod = await import({json.dumps(url)});\n{codigo}\n'
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), timeout=30,
    )
    assert proc.returncode == 0, f"node fallo:\nSTDOUT:{proc.stdout}\nSTDERR:{proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_coordinador_rw_paraleliza_lecturas_con_tope_max_reads():
    r = _node_eval("""
const coord = new mod.AsyncRWCoordinator(2);
let active = 0, peak = 0;
const delay = (ms) => new Promise((res) => setTimeout(res, ms));
await Promise.all([1, 2, 3, 4].map((i) => coord.run("read", null, async () => {
  active++;
  if (active > peak) peak = active;
  await delay(40);
  active--;
  return i;
})));
console.log(JSON.stringify({ peak, stats: coord.stats() }));
""")
    assert r["peak"] == 2, r
    assert r["stats"]["activeReads"] == 0 and r["stats"]["pendingReads"] == 0


def test_coordinador_rw_serializa_misma_carpeta_y_paraleliza_carpetas_distintas():
    r = _node_eval("""
const coord = new mod.AsyncRWCoordinator(4);
const delay = (ms) => new Promise((res) => setTimeout(res, ms));
let sameActive = 0, samePeak = 0;
await Promise.all([1, 2].map(() => coord.run("write", "folder:07_Knowledge", async () => {
  sameActive++;
  if (sameActive > samePeak) samePeak = sameActive;
  await delay(40);
  sameActive--;
})));
let diffActive = 0, diffPeak = 0;
await Promise.all(["folder:07_Knowledge", "folder:18_Bugs"].map((k) => coord.run("write", k, async () => {
  diffActive++;
  if (diffActive > diffPeak) diffPeak = diffActive;
  await delay(40);
  diffActive--;
})));
console.log(JSON.stringify({ samePeak, diffPeak, stats: coord.stats() }));
""")
    assert r["samePeak"] == 1, r
    assert r["diffPeak"] == 2, r
    assert r["stats"]["activeWriteKeys"] == 0


def test_coordinador_rw_barrera_global_drena_activas_y_retiene_entrantes():
    r = _node_eval("""
const coord = new mod.AsyncRWCoordinator(4);
const delay = (ms) => new Promise((res) => setTimeout(res, ms));
const log = [];
const p1 = coord.run("read", null, async () => {
  log.push("read1:start");
  await delay(50);
  log.push("read1:end");
});
await delay(10);
const pGlobal = coord.run("global", null, async () => {
  log.push("global:start:" + coord.stats().activeReads + ":" + coord.stats().activeWriteKeys);
  await delay(40);
  log.push("global:end");
});
await delay(10);
const p2 = coord.run("read", null, async () => {
  log.push("read2:start");
});
await Promise.all([p1, pGlobal, p2]);
console.log(JSON.stringify({ log, stats: coord.stats() }));
""")
    assert r["log"] == ["read1:start", "read1:end", "global:start:0:0", "global:end", "read2:start"], r
    assert r["stats"]["activeGlobal"] is False


def test_coordinador_rw_libera_siempre_ante_errores_sin_deadlock():
    r = _node_eval("""
const coord = new mod.AsyncRWCoordinator(2);
for (const [mode, key] of [["read", null], ["write", "folder:07_Knowledge"], ["global", null]]) {
  try {
    await coord.run(mode, key, async () => { throw new Error("boom-" + mode); });
  } catch (_) {}
}
const ok = await coord.run("write", "folder:07_Knowledge", async () => "recuperado");
console.log(JSON.stringify({ ok, stats: coord.stats() }));
""")
    assert r["ok"] == "recuperado"
    assert r["stats"]["activeReads"] == 0
    assert r["stats"]["activeWriteKeys"] == 0
    assert r["stats"]["activeGlobal"] is False


def test_access_mode_y_clave_recurso_desde_catalogo():
    r = _node_eval("""
mod.loadCatalog?.();
const readMode = mod.accessModeDe("vault_search");
const writeMode = mod.accessModeDe("vault_write");
const globalMode = mod.accessModeDe("vault_backup");
const keyFolder = mod.claveRecursoEscritura("vault_write", { folder: "07_Knowledge/sub" });
const keyNotePath = mod.claveRecursoEscritura("vault_append", { path: "07_Knowledge/sub/nota.md" });
const keyDefault = mod.claveRecursoEscritura("vault_project", { add: "demo" });
console.log(JSON.stringify({ readMode, writeMode, globalMode, keyFolder, keyNotePath, keyDefault }));
""")
    assert r["readMode"] == "read", r
    assert r["writeMode"] == "write", r
    assert r["globalMode"] == "global", r
    assert r["keyFolder"] == "folder:07_Knowledge/sub", r
    assert r["keyNotePath"] == "folder:07_Knowledge/sub", r
    assert r["keyDefault"] == "vault:write", r


def test_mantenimiento_mcp_cabeceras_y_docs_alineados_con_ap48():
    mjs = SERVER.read_text(encoding="utf-8")
    assert mjs.count("// SECCIÓN 7:") == 1, "SECCIÓN 7 duplicada en vault-mcp-server.mjs"

    plan = (ROOT / "mcp" / "PLAN.md").read_text(encoding="utf-8")
    assert "superseded_by:" in plan.lower() or "histórico" in plan.lower()

    roadmap = (ROOT / "docs" / "product" / "roadmap" / "roadmap-mcp.md").read_text(encoding="utf-8")
    assert "+50 JS-native" not in roadmap
    assert "+20 JS-native" not in roadmap
    assert "AP-48" in roadmap
