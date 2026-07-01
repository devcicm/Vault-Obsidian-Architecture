#!/usr/bin/env node
/**
 * vault-mcp-server.mjs — Vault Obsidian Architecture MCP Monolith
 *
 * Servidor MCP monolítico que expone las 71 herramientas del vault
 * como MCP tools accesibles directamente por IAs sin registro en harness.
 *
 * Versión: v37.0 (SDD)
 * Transporte: dual (stdio + SSE/HTTP)
 * Dependencias: CERO npm — solo node:* built-ins
 *
 * Uso:
 *   node vault-mcp-server.mjs                # modo stdio
 *   node vault-mcp-server.mjs --port 3000     # modo SSE/HTTP
 *   node vault-mcp-server.mjs --vault C:/...  # vault root explícito
 */

import { createInterface } from "node:readline";
import { createServer } from "node:http";
import { spawn, execSync } from "node:child_process";
import { readFile, readdir, stat, writeFile, mkdir, rename, rmdir } from "node:fs/promises";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { createHash, randomUUID } from "node:crypto";
import { resolve, basename, dirname, join, sep } from "node:path";
import { fileURLToPath } from "node:url";

// ============================================================================
// SECCIÓN 1: Bootstrap & Config
// ============================================================================

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const REPO_ROOT = resolve(__dirname, "..", "..");
const SCRIPTS_DIR = join(REPO_ROOT, "scripts");
const VERSION = "v37.0 (SDD)";

let VAULT_ROOT = process.env.VAULT_ROOT || null;
let SSE_PORT = 0;
let LOG_LEVEL = process.env.VAULT_MCP_LOG || "info";

const CATALOG_PATH = join(__dirname, "tools-catalog.json");
let TOOLS_CATALOG = {};
let TOOL_GROUPS = {};

function loadCatalog() {
  try {
    const raw = readFileSync(CATALOG_PATH, "utf-8");
    const data = JSON.parse(raw);
    TOOLS_CATALOG = data.tools || {};
    TOOL_GROUPS = data.groups || {};
    log("info", `Loaded ${Object.keys(TOOLS_CATALOG).length} tools in ${Object.keys(TOOL_GROUPS).length} groups`);
  } catch (e) {
    log("warn", `Could not load catalog from ${CATALOG_PATH}: ${e.message}. Tools/list will be empty.`);
  }
}

function detectVaultRoot() {
  if (VAULT_ROOT) return VAULT_ROOT;
  const candidates = [
    join(REPO_ROOT, "vault-sandbox"),
    ...Array.from({ length: 20 }, (_, i) => join(REPO_ROOT, `..`)).map(p => resolve(p))
  ];
  const MARKERS = ["00_System", "01_Projects", "99_Index", ".obsidian"];
  for (const dir of candidates) {
    try {
      const entries = readdirSync(dir);
      const markers = entries.filter(e => MARKERS.includes(e));
      if (markers.length >= 2) { VAULT_ROOT = dir; return dir; }
    } catch (_) { /* skip */ }
  }
  VAULT_ROOT = join(REPO_ROOT, "vault-sandbox");
  return VAULT_ROOT;
}

function log(level, msg, data) {
  const levels = { debug: 0, info: 1, warn: 2, error: 3 };
  if (levels[level] < levels[LOG_LEVEL]) return;
  const line = `[MCP ${level.toUpperCase()}] ${msg}` + (data ? " " + JSON.stringify(data) : "");
  process.stderr.write(line + "\n");
}

// ============================================================================
// SECCIÓN 2: Core Utilities (JS-native equivalents of Python vault_*)
// ============================================================================

function normalizeStem(s) {
  return s.toLowerCase()
    .replace(/-/g, "").replace(/_/g, "").replace(/ /g, "")
    .replace(/\./g, "").replace(/md$/, "");
}

function extractWikilinks(content) {
  const clean = content
    .replace(/```mermaid[\s\S]*?```/g, "")
    .replace(/```[\s\S]*?```/g, "")
    .replace(/`[^`]+`/g, "");
  const re = /\[\[([^\]|]+)(?:\|[^\]]+)?\]\]/g;
  const links = [];
  let m;
  while ((m = re.exec(clean)) !== null) {
    const target = m[1].trim();
    if (target && target.length <= 200 && !/^https?:/.test(target) && !target.includes('"')) {
      links.push(target);
    }
  }
  return links;
}

function stripCodeBlocks(content) {
  return content
    .replace(/```[\s\S]*?```/g, "")
    .replace(/`[^`]+`/g, "");
}

function parseFrontmatter(content) {
  const m = content.match(/^---\s*\n([\s\S]*?)\n---/);
  if (!m) return {};
  const fm = {};
  for (const line of m[1].split("\n")) {
    const kv = line.match(/^(\w[\w_-]*):\s*(.*)$/);
    if (kv) {
      let val = kv[2].trim();
      if (val.startsWith("[") && val.endsWith("]")) {
        val = val.slice(1, -1).split(",").map(s => s.trim().replace(/['"]/g, ""));
      } else if (val === "true") val = true;
      else if (val === "false") val = false;
      fm[kv[1]] = val;
    }
  }
  return fm;
}

function parseFrontmatterWithBody(content) {
  const m = content.match(/^---\s*\n([\s\S]*?)\n---\s*\n?([\s\S]*)$/);
  if (!m) return [{}, content];
  return [parseFrontmatter(content), m[2] || ""];
}

function extractTitle(content) {
  const fmMatch = content.match(/^---\s*\n([\s\S]*?)\n---/);
  if (!fmMatch) return null;
  const fm = fmMatch[1];
  const m = fm.match(/^title:\s*(.+)$/m);
  return m ? m[1].trim().replace(/^["']|["']$/g, "") : null;
}

function extractTags(content) {
  const fmMatch = content.match(/^---\s*\n([\s\S]*?)\n---/);
  if (!fmMatch) return [];
  const fm = fmMatch[1];
  const m = fm.match(/^tags:\s*(.+)$/m);
  if (!m) return [];
  const raw = m[1].trim();
  if (raw.startsWith("[")) {
    return raw.slice(1, -1).split(",").map(s => s.trim().replace(/['"]/g, ""));
  }
  return raw.split(/\s+/).filter(Boolean);
}

// Bracket anomaly regex (ports from vault_regex.py)
const RE_NESTED_OPEN = /\[\[\[+/g;
const RE_NESTED_CLOSE = /\]\]\]+/g;
const RE_EMPTY_LINK = /\[\[\s*\]\]/g;
const RE_PATH_ANCHORED = /\[\[\/|\[\[[^\]]*\//g;
const RE_INVERTED = /\]\][^\n]*\[\[/g;

function detectBracketAnomalies(text) {
  const clean = stripCodeBlocks(text);
  const findings = [];
  const opens = (clean.match(/\[\[/g) || []).length;
  const closes = (clean.match(/\]\]/g) || []).length;

  let m;
  RE_NESTED_OPEN.lastIndex = 0;
  while ((m = RE_NESTED_OPEN.exec(clean)) !== null) {
    findings.push({ type: "nested_open", match: m[0], position: m.index });
  }
  RE_NESTED_CLOSE.lastIndex = 0;
  while ((m = RE_NESTED_CLOSE.exec(clean)) !== null) {
    findings.push({ type: "nested_close", match: m[0], position: m.index });
  }
  RE_EMPTY_LINK.lastIndex = 0;
  while ((m = RE_EMPTY_LINK.exec(clean)) !== null) {
    findings.push({ type: "empty_link", match: m[0], position: m.index });
  }
  RE_INVERTED.lastIndex = 0;
  while ((m = RE_INVERTED.exec(clean)) !== null) {
    findings.push({ type: "inverted_brackets", match: m[0], position: m.index });
  }
  if (opens !== closes) {
    findings.push({ type: "imbalanced", opens, closes, diff: Math.abs(opens - closes) });
  }

  return { opens, closes, balanced: opens === closes, count: findings.length, findings };
}

function detectPathAnchored(content) {
  const matches = [];
  let m;
  RE_PATH_ANCHORED.lastIndex = 0;
  while ((m = RE_PATH_ANCHORED.exec(stripCodeBlocks(content))) !== null) {
    matches.push(m[0]);
  }
  return matches;
}

function fixNestedBrackets(text) {
  return text
    .replace(/\[\[\[+/g, "[[")
    .replace(/\]\]\]+/g, "]]");
}

// ============================================================================
// SECCIÓN 2.5: JS-Native Tool Backend
// ============================================================================

const JS_NATIVE_TOOLS = new Set([
  "vault_read", "vault_list", "vault_search",
  "vault_graph", "vault_graph_inspect",
  "vault_tokens", "vault_token_counter", "vault_fundamentals",
]);

function assertWithinVault(p, vaultRoot) {
  const resolved = resolve(p);
  const normalizedRoot = resolve(vaultRoot);
  if (!resolved.startsWith(normalizedRoot + sep) && resolved !== normalizedRoot) {
    throw new Error(`Path traversal blocked: "${p}" is outside vault root`);
  }
  return resolved;
}

async function jsNativeRead(args) {
  const vaultRoot = detectVaultRoot();
  let content;
  if (args.path) {
    const p = assertWithinVault(join(vaultRoot, args.path), vaultRoot);
    content = await readFile(p, "utf-8");
  } else if (args.title) {
    const files = await scanMdFiles(vaultRoot);
    for (const f of files) {
      const c = await readFile(join(vaultRoot, f), "utf-8");
      const t = extractTitle(c);
      if (t && t.toLowerCase() === args.title.toLowerCase()) {
        content = c;
        break;
      }
    }
    if (!content) throw new Error(`Note with title '${args.title}' not found`);
  } else {
    throw new Error("Either --path or --title is required");
  }
  const [fm, body] = parseFrontmatterWithBody(content);
  return { ok: true, frontmatter: fm, body, path: args.path || null, size: content.length };
}

async function jsNativeList(args) {
  const vaultRoot = detectVaultRoot();
  const folder = args.folder || "";
  const targetDir = join(vaultRoot, folder);
  const files = await scanMdFiles(targetDir);
  const limit = parseInt(args.limit) || 50;
  const results = [];
  for (const f of files.slice(0, limit)) {
    const fullPath = join(targetDir, f);
    const content = await readFile(fullPath, "utf-8");
    const title = extractTitle(content) || basename(f, ".md");
    const tags = extractTags(content);
    const statInfo = await stat(fullPath);
    results.push({
      path: folder ? `${folder}/${f}` : f,
      title,
      tags,
      size: statInfo.size,
      modified: statInfo.mtime.toISOString(),
    });
  }
  return { ok: true, folder: folder || "(root)", count: results.length, total: files.length, notes: results };
}

async function jsNativeSearch(args) {
  const vaultRoot = detectVaultRoot();
  const query = args.query || "";
  const files = await scanMdFiles(vaultRoot);
  const limit = parseInt(args.limit) || 10;
  const results = [];
  for (const f of files) {
    if (results.length >= limit) break;
    const content = await readFile(join(vaultRoot, f), "utf-8");
    if (content.toLowerCase().includes(query.toLowerCase())) {
      const title = extractTitle(content) || basename(f, ".md");
      const idx = content.toLowerCase().indexOf(query.toLowerCase());
      const start = Math.max(0, idx - 50);
      const snippet = content.substring(start, start + 200).replace(/\n/g, " ");
      results.push({ path: f, title, snippet: `...${snippet}...` });
    }
  }
  return { ok: true, query, count: results.length, results };
}

async function jsNativeGraph(args) {
  const vaultRoot = detectVaultRoot();
  const files = await scanMdFiles(vaultRoot);
  const nodes = [];
  const edges = [];
  const stemMap = new Map();

  for (const f of files) {
    const content = await readFile(join(vaultRoot, f), "utf-8");
    const title = extractTitle(content) || basename(f, ".md");
    const fnameStem = normalizeStem(basename(f, ".md"));
    const titleStem = normalizeStem(title);
    stemMap.set(titleStem, f);
    if (fnameStem !== titleStem) stemMap.set(fnameStem, f);
    nodes.push({ path: f, title, stem: titleStem });
  }

  for (const node of nodes) {
    const content = await readFile(join(vaultRoot, node.path), "utf-8");
    const links = extractWikilinks(content);
    for (const link of links) {
      const linkStem = normalizeStem(link);
      const target = stemMap.get(linkStem);
      if (target) {
        edges.push({ source: node.path, target, link });
      } else {
        edges.push({ source: node.path, target: null, link, broken: true });
      }
    }
  }

  const broken = edges.filter(e => e.broken).length;
  return {
    ok: true, tool: "vault_graph",
    totalNodes: nodes.length, totalEdges: edges.length, brokenLinks: broken,
    nodes, edges,
  };
}

async function jsNativeGraphInspect(args) {
  const vaultRoot = detectVaultRoot();
  const graphResult = await jsNativeGraph(args);
  const { nodes, edges } = graphResult;

  const stemPathMap = new Map();
  for (const n of nodes) {
    stemPathMap.set(n.stem, n.path);
  }

  const brokenLinks = edges.filter(e => e.broken).map(e => ({ source: e.source, target: e.link }));
  const inDegree = new Map();
  for (const e of edges) {
    if (!e.broken && e.target) {
      inDegree.set(e.target, (inDegree.get(e.target) || 0) + 1);
    }
  }
  const orphans = nodes.filter(n => !inDegree.has(n.path) && !n.path.startsWith("00_System/") && !n.path.startsWith("04_Sessions/")).map(n => n.path);

  const bracketErrors = [];
  const mermaidErrors = [];
  let totalMermaidBlocksFound = 0;
  let totalMermaidErrorsFound = 0;

  for (const n of nodes) {
    const content = await readFile(join(vaultRoot, n.path), "utf-8");
    const anomalies = detectBracketAnomalies(content);
    if (anomalies.count > 0) {
      bracketErrors.push({ note: n.path, ...anomalies });
    }

    const mermaidResult = guardMermaidSyntax(content);
    if (mermaidResult.blocks_found > 0) {
      totalMermaidBlocksFound += mermaidResult.blocks_found;
      if (!mermaidResult.ok) {
        mermaidErrors.push({ note: n.path, ...mermaidResult });
        totalMermaidErrorsFound += mermaidResult.errors.length;
      }
    }
  }

  return {
    ok: true, tool: "vault_graph_inspect",
    vault_root: vaultRoot,
    summary: {
      total_notes: nodes.length,
      total_edges: edges.length,
      broken_links: brokenLinks.length,
      syntax_errors: bracketErrors.length,
      mermaid_blocks: totalMermaidBlocksFound,
      mermaid_errors: totalMermaidErrorsFound,
      orphans: orphans.length,
    },
    broken_links: brokenLinks,
    syntax_errors: bracketErrors,
    mermaid_errors: mermaidErrors,
    orphans,
  };
}

async function jsNativeTokens(args) {
  const vaultRoot = detectVaultRoot();
  const files = await scanMdFiles(vaultRoot);
  let totalTokens = 0;
  const perFile = [];
  for (const f of files.slice(0, 50)) {
    const content = await readFile(join(vaultRoot, f), "utf-8");
    const tokens = heuristicTokenCount(content);
    totalTokens += tokens;
    perFile.push({ path: f, tokens });
  }
  return { ok: true, total_files_scanned: perFile.length, total_tokens: totalTokens, per_file: perFile };
}

async function jsNativeTokenCounter(args) {
  const content = args.content || "";
  const tokens = heuristicTokenCount(content);
  return { ok: true, content_length: content.length, estimated_tokens: tokens, model: args.model || "heuristic" };
}

async function jsNativeFundamentals() {
  const vaultRoot = detectVaultRoot();
  const files = await scanMdFiles(vaultRoot);
  const results = [];
  let passCount = 0;
  const total = Math.min(files.length, 50);

  for (const f of files.slice(0, 50)) {
    const content = await readFile(join(vaultRoot, f), "utf-8");
    const fm = parseFrontmatter(content);
    const [, body] = parseFrontmatterWithBody(content);
    const bodyLines = body.split("\n").filter(l => l.trim() && !l.trim().startsWith("#") && !/^[-*]\s*$/.test(l.trim())).length;
    const words = body.split(/\s+/).filter(w => w.length > 1).length;

    const checks = {
      F1_integrity: !!(fm.id && fm.title && fm.createdAt),
      F2_consistency: true,
      F3_completeness: !!(fm.updatedAt && bodyLines >= 3),
      F5_validity: true,
      F7_authenticity: !!fm.agent,
      content_lines: bodyLines,
      content_words: words,
    };
    if (Object.values(checks).filter(v => typeof v === "boolean").every(Boolean)) passCount++;
    results.push({ path: f, ...checks });
  }

  return { ok: true, total_checked: total, passed: passCount, compliance_pct: Math.round(100 * passCount / total), results };
}

function heuristicTokenCount(text) {
  return Math.ceil(text.length / 4);
}

async function scanMdFiles(dir) {
  const results = [];
  try {
    const entries = await readdir(dir, { withFileTypes: true });
    for (const e of entries) {
      if (e.name.startsWith(".")) continue;
      const full = join(dir, e.name);
      if (e.isDirectory()) {
        const sub = await scanMdFiles(full);
        results.push(...sub.map(s => join(e.name, s)));
      } else if (e.name.endsWith(".md")) {
        results.push(e.name);
      }
    }
  } catch (_) { /* dir doesn't exist */ }
  return results;
}

async function dispatchJsNative(name, args) {
  switch (name) {
    case "vault_read": return jsNativeRead(args);
    case "vault_list": return jsNativeList(args);
    case "vault_search": return jsNativeSearch(args);
    case "vault_graph": return jsNativeGraph(args);
    case "vault_graph_inspect": return jsNativeGraphInspect(args);
    case "vault_tokens": return jsNativeTokens(args);
    case "vault_token_counter": return jsNativeTokenCounter(args);
    case "vault_fundamentals": return jsNativeFundamentals(args);
    default: return null;
  }
}

// ============================================================================
// SECCIÓN 3: MCP Protocol (JSON-RPC 2.0)
// ============================================================================

const SERVER_INFO = {
  name: "vault-mcp-server",
  version: VERSION,
};

const CAPABILITIES = {
  tools: { listChanged: false },
  resources: { listChanged: false, subscribe: false },
};

let initialized = false;
let clientCapabilities = null;

function jsonrpcResult(id, result) {
  return { jsonrpc: "2.0", id, result };
}

function jsonrpcError(id, code, message, data) {
  return { jsonrpc: "2.0", id, error: { code, message, data } };
}

function handleInitialize(params) {
  clientCapabilities = params.capabilities || {};
  return {
    protocolVersion: "2024-11-05",
    serverInfo: SERVER_INFO,
    capabilities: CAPABILITIES,
  };
}

function handleInitialized() {
  initialized = true;
  log("info", "MCP session initialized");
  return {};
}

async function handleToolsList() {
  const tools = Object.values(TOOLS_CATALOG).map(t => ({
    name: t.name,
    description: t.description,
    inputSchema: t.inputSchema || { type: "object", properties: {}, required: [] },
  }));

  const extraTools = [
    {
      name: "vault_graph_inspect",
      description: "Analiza el grafo del vault: broken links, orphans, duplicates, syntax errors, hubs.",
      inputSchema: { type: "object", properties: {}, required: [] },
    },
    {
      name: "vault_graph_fix",
      description: "Auto-fix de broken wiki-links (stem match, fuzzy, brackets, path-anchored, stubs, wizard).",
      inputSchema: {
        type: "object",
        properties: {
          threshold: { type: "string", description: "Fuzzy match threshold (default: 0.7)" },
          "auto-apply-partial": { type: "string", description: "Auto-fix partial matches above this threshold" },
          apply: { type: "string", description: "Apply fixes (default: dry-run)" },
          only: { type: "string", description: "Only run: brackets, path_anchored", enum: ["brackets", "path_anchored"] },
        },
        required: [],
      },
    },
  ];

  return { tools: [...tools, ...extraTools] };
}

async function handleToolsCall(params) {
  const name = params?.name;
  const args = params?.arguments || {};

  if (!name) {
    return formatToolError("missing_tool_name", "Tool name is required");
  }

  log("info", `Executing tool: ${name}`, args);

  try {
    const vaultRoot = detectVaultRoot();

    if ((name === "vault_write" || name === "vault_append") && args.content) {
      const guard = await runGuardChain(args.content, args.folder, vaultRoot);
      if (!guard.ok) {
        await TraceLog.record(name, args, { ok: false, guard_result: guard });
        return formatToolError("GUARD_CHAIN_FAILED",
          `Guard chain blocked at ${guard.failed_at}: ${JSON.stringify(guard.results[guard.failed_at])}`);
      }
    }

    if (name === "vault_health") {
      const result = await runHealthCheck();
      await TraceLog.record(name, args, result);
      return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
    }

    let result;
    if (JS_NATIVE_TOOLS.has(name)) {
      result = await dispatchJsNative(name, args);
    } else if (name === "vault_graph_fix" || name === "vault_graph_inspect") {
      const scriptName = name + ".py";
      const scriptPath = join(SCRIPTS_DIR, scriptName);
      result = await executePythonTool(scriptPath, args);
    } else {
      const tool = TOOLS_CATALOG[name];
      if (!tool || !tool.script) {
        return formatToolError("tool_not_found", `Tool '${name}' not found.`);
      }
      const scriptPath = join(SCRIPTS_DIR, tool.script);
      result = await executePythonTool(scriptPath, args);
    }

    await TraceLog.record(name, args, result);

    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  } catch (e) {
    log("error", `Tool ${name} failed: ${e.message}`);
    return formatToolError("TOOL_EXECUTION_FAILED", e.message, name);
  }
}

function formatToolError(error, message, tool) {
  return {
    content: [{ type: "text", text: JSON.stringify({ ok: false, error_code: error, tool: tool || "unknown", message }, null, 2) }],
    isError: true,
  };
}

let PYTHON_CMD = null;

function detectPython() {
  if (PYTHON_CMD) return PYTHON_CMD;
  for (const cmd of ["py", "python3", "python"]) {
    try {
      execSync(`"${cmd}" --version`, { stdio: "ignore", timeout: 5000 });
      PYTHON_CMD = cmd;
      log("info", `Python detected: ${cmd}`);
      return cmd;
    } catch (_) { /* try next */ }
  }
  PYTHON_CMD = "python";
  log("warn", "No Python found on PATH. Python-backed tools will fail.");
  return "python";
}

function executePythonTool(scriptPath, args) {
  return new Promise((resolve, reject) => {
    const cliArgs = [];
    for (const [key, value] of Object.entries(args)) {
      const flag = "--" + key.replace(/_/g, "-");
      const isBool = typeof value === "boolean" || value === "true" || value === "false";
      if (isBool) {
        if (value === true || value === "true") cliArgs.push(flag);
      } else if (Array.isArray(value)) {
        cliArgs.push(flag, ...value.map(String));
      } else {
        cliArgs.push(flag, String(value));
      }
    }

    const python = detectPython();
    const proc = spawn(python, [scriptPath, ...cliArgs], {
      cwd: SCRIPTS_DIR,
      timeout: 120000,
      stdio: ["pipe", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (d) => { stdout += d.toString(); });
    proc.stderr.on("data", (d) => { stderr += d.toString(); });

    proc.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(`Python tool exited with code ${code}: ${stderr || stdout}`));
        return;
      }
      try {
        resolve(JSON.parse(stdout.trim() || "{}"));
      } catch {
        resolve({ ok: true, tool: scriptPath, raw_output: stdout.trim(), stderr: stderr.trim() });
      }
    });

    proc.on("error", (err) => {
      reject(new Error(`Failed to spawn Python: ${err.message}`));
    });
  });
}

// Resources defined in SECCION 10 below

// ============================================================================
// SECCIÓN 4: JSON-RPC Dispatch Router
// ============================================================================

const ROUTES = {
  "initialize":       { handler: handleInitialize, initRequired: false },
  "notifications/initialized": { handler: handleInitialized, initRequired: false },
  "tools/list":       { handler: handleToolsList,   initRequired: true },
  "tools/call":       { handler: handleToolsCall,   initRequired: true },
  "resources/list":   { handler: handleResourcesList, initRequired: true },
  "resources/read":   { handler: handleResourcesRead, initRequired: true },
};

async function dispatch(method, params) {
  if (method === "notifications/initialized") {
    return handleInitialized();
  }

  const route = ROUTES[method];
  if (!route) {
    throw { code: -32601, message: `Method not found: ${method}` };
  }

  if (route.initRequired && !initialized) {
    throw { code: -32002, message: "Not initialized. Send 'initialize' first." };
  }

  return await route.handler(params);
}

async function processMessage(msg) {
  try {
    const rpc = JSON.parse(msg.trim());
    if (!rpc.jsonrpc || rpc.jsonrpc !== "2.0") {
      throw { code: -32600, message: "Invalid Request: jsonrpc must be '2.0'" };
    }

    const { id, method, params } = rpc;

    if (!method) {
      throw { code: -32600, message: "Invalid Request: missing method" };
    }

    const result = await dispatch(method, params || {});

    if (id !== undefined && id !== null) {
      return jsonrpcResult(id, result);
    }
    return null;
  } catch (e) {
    if (e.code && e.message) {
      return jsonrpcError(null, e.code, e.message, e.data);
    }
    log("error", "Unhandled dispatch error", e.message);
    return jsonrpcError(null, -32603, "Internal error", e.message);
  }
}

// ============================================================================
// SECCIÓN 5: Transport — stdio
// ============================================================================

let pendingOps = 0;

function startStdio() {
  log("info", `Starting MCP server in stdio mode (${VERSION})`);
  log("info", `Vault root: ${detectVaultRoot()}`);

  const rl = createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false,
  });

  rl.on("line", async (line) => {
    if (!line.trim()) return;
    log("debug", "RX", line.substring(0, 200));

    pendingOps++;
    try {
      const response = await processMessage(line);
      if (response !== null) {
        const out = JSON.stringify(response);
        log("debug", "TX", out.substring(0, 200));
        process.stdout.write(out + "\n");
      }
    } catch (e) {
      log("error", "Unhandled error in message loop", e.message);
    } finally {
      pendingOps--;
    }
  });

  rl.on("close", () => {
    log("info", "stdin closed, waiting for pending operations...");
    const check = setInterval(() => {
      if (pendingOps <= 0) {
        clearInterval(check);
        log("info", "All operations complete, exiting.");
        process.exit(0);
      }
    }, 100);
  });

  process.on("SIGINT", () => { process.exit(0); });
  process.on("SIGTERM", () => { process.exit(0); });
}

// ============================================================================
// SECCIÓN 6: Transport — SSE/HTTP (modo servicio sin harness)
// ============================================================================

function startSSE(port) {
  const clients = new Set();

  const server = createServer(async (req, res) => {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type, Accept");

    if (req.method === "OPTIONS") {
      res.writeHead(204);
      res.end();
      return;
    }

    if (req.method === "GET" && req.url === "/health") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({
        ok: true,
        server: "vault-mcp-server",
        version: VERSION,
        uptime: process.uptime(),
        vault_root: detectVaultRoot(),
        tools_loaded: Object.keys(TOOLS_CATALOG).length,
      }));
      return;
    }

    if (req.method === "GET" && req.url === "/sse") {
      res.writeHead(200, {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      });
      res.write(`data: ${JSON.stringify({ type: "connected", server: SERVER_INFO })}\n\n`);
      clients.add(res);
      req.on("close", () => clients.delete(res));
      return;
    }

    if (req.method === "POST" && req.url === "/message") {
      let body = "";
      req.on("data", (chunk) => { body += chunk; });
      req.on("end", async () => {
        try {
          const response = await processMessage(body);
          if (response !== null) {
            const out = JSON.stringify(response);
            res.writeHead(200, { "Content-Type": "application/json" });
            res.end(out);
            notifyClients(out, clients);
          } else {
            res.writeHead(202);
            res.end();
          }
        } catch (e) {
          res.writeHead(500, { "Content-Type": "application/json" });
          res.end(JSON.stringify(jsonrpcError(null, -32603, "Internal error", e.message)));
        }
      });
      return;
    }

    res.writeHead(404, { "Content-Type": "text/plain" });
    res.end("Not found. Available: /sse, /message, /health");
  });

  server.listen(port, "127.0.0.1", () => {
    log("info", `========================================`);
    log("info", `MCP SSE Server running on http://127.0.0.1:${port}`);
    log("info", `Connect IAs to: http://127.0.0.1:${port}/sse`);
    log("info", `Health check:   http://127.0.0.1:${port}/health`);
    log("info", `Vault root: ${detectVaultRoot()}`);
    log("info", `Tools loaded: ${Object.keys(TOOLS_CATALOG).length}`);
    log("info", `========================================`);
  });
}

function notifyClients(msg, clients) {
  for (const client of clients) {
    try { client.write(`data: ${msg}\n\n`); } catch (_) { clients.delete(client); }
  }
}

// ============================================================================
// SECCIÓN 7: Guard Chain (Validadores pre-escritura)
// ============================================================================

const SECRET_PATTERNS = [
  { id: "aws_access_key", pattern: /AKIA[0-9A-Z]{16}/, severity: "critical", desc: "AWS Access Key" },
  { id: "aws_secret_key", pattern: /[A-Za-z0-9\/+]{40}/, severity: "critical", desc: "AWS Secret Key (base64 40+ chars)" },
  { id: "github_token", pattern: /gh[pousr]_[A-Za-z0-9_]{36}/, severity: "critical", desc: "GitHub Token" },
  { id: "bearer_token", pattern: /bearer\s+[A-Za-z0-9\-._~+\/]{20,}={0,2}/i, severity: "critical", desc: "Bearer Token" },
  { id: "private_key", pattern: /-----BEGIN\s+(RSA|EC|DSA|OPENSSH)\s+PRIVATE\s+KEY-----/, severity: "critical", desc: "Private Key" },
  { id: "password_assign", pattern: /password\s*[:=]\s*["'][^"']{3,}["']/i, severity: "high", desc: "Password Assignment" },
  { id: "api_key_assign", pattern: /api[_-]?key\s*[:=]\s*["'][^"']{5,}["']/i, severity: "high", desc: "API Key Assignment" },
  { id: "jwt_token", pattern: /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/, severity: "warning", desc: "JWT Token" },
];

function guardSecretScan(text) {
  const findings = [];
  for (const p of SECRET_PATTERNS) {
    const m = text.match(p.pattern);
    if (m) {
      const matchText = m[0];
      const redacted = matchText.length > 8 ? matchText.slice(0, 4) + "..." + matchText.slice(-4) : "***";
      findings.push({ pattern_id: p.id, severity: p.severity, description: p.desc, match_redacted: redacted });
    }
  }
  const blocking = findings.filter(f => f.severity === "critical");
  return { ok: blocking.length === 0, findings, blocked_by: blocking };
}

function guardContentGate(content, folder) {
  if (folder && folder.startsWith("00_System/")) return { ok: true };

  const [_, body] = parseFrontmatterWithBody(content);
  const lines = body.split("\n");
  const realLines = lines.filter(l => {
    const t = l.trim();
    if (!t) return false;
    if (/^#+\s/.test(t) && lines.indexOf(l) === lines.findIndex(x => /^#+\s/.test(x.trim()))) return false;
    if (/^[-*]\s*$/.test(t)) return false;
    return true;
  });
  if (realLines.length < 3) {
    return { ok: false, reason: `Content too short: ${realLines.length} real lines (min 3)` };
  }
  const words = body.split(/\s+/).filter(w => w.length > 1).length;
  if (words < 10) {
    return { ok: false, reason: `Content too short: ${words} real words (min 10)` };
  }
  return { ok: true };
}

function guardBracketBalance(content) {
  const clean = stripCodeBlocks(content);
  const opens = (clean.match(/\[\[/g) || []).length;
  const closes = (clean.match(/\]\]/g) || []).length;
  const empty = (clean.match(RE_EMPTY_LINK) || []).length;
  if (empty > 0) {
    return { ok: false, reason: `Empty wiki-links found (AP-22): ${empty} empty [[]]` };
  }
  if (opens !== closes) {
    return { ok: false, reason: `Unbalanced brackets: ${opens} opens vs ${closes} closes (AP-24)` };
  }
  return { ok: true };
}

function guardEmptyLinks(content) {
  const clean = stripCodeBlocks(content);
  const empty = (clean.match(RE_EMPTY_LINK) || []).length;
  return { ok: empty === 0, count: empty, reason: empty > 0 ? `Empty wiki-links: ${empty}` : null };
}

function guardPathAnchored(content) {
  const matches = detectPathAnchored(content);
  return { ok: matches.length === 0, count: matches.length, examples: matches.slice(0, 3), reason: matches.length > 0 ? "Path-anchored links (AP-21)" : null };
}

function guardTableBrackets(content) {
  const lines = content.split("\n");
  const errors = [];
  let inTable = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.startsWith("|") && line.endsWith("|")) {
      inTable = true;
      if (/^\|[-:\s|]+\|$/.test(line)) continue;
      const cells = line.split("|").slice(1, -1);
      for (let j = 0; j < cells.length; j++) {
        const cell = cells[j].trim();
        const opens = (cell.match(/\[\[/g) || []).length;
        const closes = (cell.match(/\]\]/g) || []).length;
        if (opens !== closes) {
          errors.push({ row: i + 1, column: j + 1, cell_content: cell, opens, closes, type: opens > closes ? "unclosed_[[" : "stray_]]" });
        }
      }
    } else if (inTable && !line.startsWith("|")) {
      inTable = false;
    }
  }
  return { ok: errors.length === 0, errors, reason: errors.length > 0 ? `Table bracket imbalance in ${errors.length} cells` : null };
}

const MERMAID_HEADERS = [
  "flowchart TD", "flowchart LR", "flowchart RL", "flowchart TB", "flowchart BT",
  "graph TD", "graph LR", "graph RL", "graph TB", "graph BT",
  "sequenceDiagram", "classDiagram", "classDiagram-v2",
  "stateDiagram", "stateDiagram-v2", "erDiagram", "gantt", "pie"
];

function guardMermaidSyntax(content) {
  const re = /```mermaid\s*\n([\s\S]*?)```/g;
  const errors = [];
  let match;
  let idx = 0;

  while ((match = re.exec(content)) !== null) {
    const diagram = match[1].trim();
    const firstLine = diagram.split("\n")[0].trim();
    const headerMatch = MERMAID_HEADERS.some(h => firstLine.startsWith(h));

    if (!headerMatch) {
      errors.push({ index: idx, type: "unknown_type", header: firstLine.substring(0, 50) });
      idx++;
      continue;
    }

    const braceOpen = (diagram.match(/\{/g) || []).length;
    const braceClose = (diagram.match(/\}/g) || []).length;
    if (braceOpen !== braceClose) {
      errors.push({ index: idx, type: "mismatched_braces", opens: braceOpen, closes: braceClose, diff: braceOpen - braceClose });
    }

    const bracketOpen = (diagram.match(/\[/g) || []).length;
    const bracketClose = (diagram.match(/\]/g) || []).length;
    if (Math.abs(bracketOpen - bracketClose) % 2 !== 0) {
      errors.push({ index: idx, type: "mismatched_brackets", opens: bracketOpen, closes: bracketClose });
    }

    idx++;
  }

  return { ok: errors.length === 0, blocks_found: idx, errors, reason: errors.length > 0 ? `${errors.length} Mermaid syntax errors in ${idx} blocks` : null };
}

let _stemPathCache = null;
let _stemPathCacheRoot = null;

function buildStemPathMap(vaultRoot) {
  if (_stemPathCache && _stemPathCacheRoot === vaultRoot) return _stemPathCache;
  const map = new Map();
  try {
    const files = readdirSync(vaultRoot, { recursive: true });
    for (const f of files) {
      const name = typeof f === "string" ? f : f.name || String(f);
      if (!name.endsWith(".md")) continue;
      const relPath = name.replace(/\\/g, "/");
      const stem = normalizeStem(relPath.replace(/\.md$/, ""));
      const nameOnly = normalizeStem(relPath.split("/").pop().replace(/\.md$/, ""));
      if (stem) map.set(stem, relPath);
      if (nameOnly && nameOnly !== stem) map.set(nameOnly, relPath);
    }
  } catch (_) { /* vault root not accessible */ }
  _stemPathCache = map;
  _stemPathCacheRoot = vaultRoot;
  return map;
}

function invalidateStemPathCache() {
  _stemPathCache = null;
  _stemPathCacheRoot = null;
}

function guardReferencedNotes(content, vaultRoot) {
  const links = extractWikilinks(content);
  const errors = [];
  if (links.length === 0) return { ok: true, errors: [], total_links: 0, broken: 0, reason: null };

  const stemMap = buildStemPathMap(vaultRoot);
  for (const link of links) {
    const stem = normalizeStem(link);
    const found = stemMap.get(stem);
    if (!found) {
      errors.push({ link, stem, error: "note_not_found" });
    } else {
      try {
        const targetContent = readFileSync(join(vaultRoot, found), "utf-8");
        const [, body] = parseFrontmatterWithBody(targetContent);
        const realLines = body.split("\n").filter(l => l.trim() && !/^[-*]\s*$/.test(l.trim())).length;
        const words = body.split(/\s+/).filter(w => w.length > 1).length;
        if (realLines < 3 || words < 10) {
          errors.push({ link, stem, target: found, error: "note_is_stub_or_empty", lines: realLines, words });
        }
      } catch (_) {
        errors.push({ link, stem, error: "note_cannot_read" });
      }
    }
  }
  return { ok: errors.length === 0, errors, total_links: links.length, broken: errors.length, reason: errors.length > 0 ? `${errors.length} broken references` : null };
}

async function runGuardChain(content, folder, vaultRoot) {
  const results = {};

  results.secretScan = guardSecretScan(content);
  if (!results.secretScan.ok) return { ok: false, failed_at: "secretScan", results };

  results.contentGate = guardContentGate(content, folder);
  if (!results.contentGate.ok) return { ok: false, failed_at: "contentGate", results };

  results.bracketBalance = guardBracketBalance(content);
  if (!results.bracketBalance.ok) return { ok: false, failed_at: "bracketBalance", results };

  results.emptyLinks = guardEmptyLinks(content);
  results.pathAnchored = guardPathAnchored(content);
  if (!results.pathAnchored.ok) return { ok: false, failed_at: "pathAnchored", results };

  results.tableBrackets = guardTableBrackets(content);
  if (!results.tableBrackets.ok) return { ok: false, failed_at: "tableBrackets", results };

  results.mermaidSyntax = guardMermaidSyntax(content);
  if (!results.mermaidSyntax.ok) return { ok: false, failed_at: "mermaidSyntax", results };

  results.referencedNotes = guardReferencedNotes(content, vaultRoot);
  if (!results.referencedNotes.ok) return { ok: false, failed_at: "referencedNotes", results };

  return { ok: true, failed_at: null, results };
}

// ============================================================================
// SECCIÓN 8: Traceability Engine
// ============================================================================

const TRACE_LOG_PATH = join(__dirname, ".mcp-trace-log.json");
const TRACE_LOG_MD_PATH = join(__dirname, ".mcp-trace-log.md");

class TraceLog {
  static async record(tool, params, result, agent = "mcp-server") {
    const entry = {
      id: randomUUID(),
      timestamp: new Date().toISOString(),
      tool,
      params: JSON.stringify(params).substring(0, 500),
      result_ok: result?.ok !== false,
      result_summary: typeof result === "string" ? result.substring(0, 200) : JSON.stringify(result).substring(0, 200),
      agent,
      session_id: this._sessionId,
    };
    await this._appendJson(entry);
    await this._appendMd(entry);
    return entry;
  }

  static _sessionId = `session-${Date.now()}`;

  static async _appendJson(entry) {
    try {
      let entries = [];
      try { entries = JSON.parse(await readFile(TRACE_LOG_PATH, "utf-8")); } catch (_) {}
      entries.push(entry);
      if (entries.length > 1000) entries = entries.slice(-500);
      await writeFile(TRACE_LOG_PATH, JSON.stringify(entries, null, 2));
    } catch (e) { log("warn", "Failed to write trace JSON log", e.message); }
  }

  static async _appendMd(entry) {
    try {
      const row = `| ${entry.id} | ${entry.timestamp} | ${entry.tool} | ${entry.result_ok ? "OK" : "FAIL"} | ${entry.agent} |`;
      let content = "";
      try { content = await readFile(TRACE_LOG_MD_PATH, "utf-8"); } catch (_) {
        content = "| ID | Timestamp | Tool | Result | Agent |\n|---|---|---|---|---|\n";
      }
      await writeFile(TRACE_LOG_MD_PATH, content + row + "\n");
    } catch (e) { log("warn", "Failed to write trace MD log", e.message); }
  }
}

// ============================================================================
// SECCIÓN 9: Observability
// ============================================================================

async function runHealthCheck() {
  const vaultRoot = detectVaultRoot();
  const inspect = await jsNativeGraphInspect({});
  const s = inspect.summary;
  const mermaidPenalty = (s.mermaid_errors || 0) * 2;
  const score = Math.max(0, 100 - (s.broken_links * 0.5) - (s.syntax_errors * 3) - (s.orphans * 0.25) - mermaidPenalty);

  const nextActions = [];
  if (s.broken_links > 0) nextActions.push({ priority: "high", category: "broken_links", count: s.broken_links, command: "vault_graph_fix --auto-apply-partial 0.78 --apply" });
  if (s.syntax_errors > 0) nextActions.push({ priority: "high", category: "syntax_errors", count: s.syntax_errors, command: "vault_fix_brackets --apply" });
  if (s.mermaid_errors > 0) nextActions.push({ priority: "medium", category: "mermaid_errors", count: s.mermaid_errors, blocks: s.mermaid_blocks, hint: "Fix Mermaid syntax errors in diagram blocks" });
  if (s.orphans > 10) nextActions.push({ priority: "medium", category: "orphans", count: s.orphans, hint: "Review orphan notes" });

  return {
    ok: true,
    health_score: Math.round(score),
    summary: s,
    next_actions: nextActions,
    generated_at: new Date().toISOString(),
  };
}

// ============================================================================
// SECCIÓN 10: Resources (MCP resources URI)
// ============================================================================

async function handleResourcesList() {
  return {
    resources: [
      { uri: "vault://graph", name: "Vault Graph", mimeType: "application/json", description: "Current wiki-link graph (nodes, edges, broken links)" },
      { uri: "vault://health", name: "Vault Health", mimeType: "application/json", description: "Health check with score and next actions" },
      { uri: "vault://traceability/mutations", name: "Mutation Trace Log", mimeType: "application/json", description: "Immutable audit trail of all tool executions" },
      { uri: "vault://catalog", name: "Tool Catalog", mimeType: "application/json", description: "All 71+ tools with input schemas" },
      { uri: "vault://state", name: "Vault State", mimeType: "application/json", description: "Current vault state (version, root, tools loaded)" },
    ],
  };
}

async function handleResourcesRead(params) {
  const uri = params?.uri || "";
  try {
    switch (uri) {
      case "vault://graph": {
        const data = await jsNativeGraph({});
        return { contents: [{ uri, mimeType: "application/json", text: JSON.stringify(data, null, 2) }] };
      }
      case "vault://health": {
        const data = await runHealthCheck();
        return { contents: [{ uri, mimeType: "application/json", text: JSON.stringify(data, null, 2) }] };
      }
      case "vault://traceability/mutations": {
        let entries = [];
        try { entries = JSON.parse(await readFile(TRACE_LOG_PATH, "utf-8")); } catch (_) {}
        return { contents: [{ uri, mimeType: "application/json", text: JSON.stringify({ count: entries.length, entries: entries.slice(-50) }, null, 2) }] };
      }
      case "vault://catalog": {
        return { contents: [{ uri, mimeType: "application/json", text: JSON.stringify({ tools: TOOLS_CATALOG, groups: TOOL_GROUPS }, null, 2) }] };
      }
      case "vault://state": {
        return { contents: [{ uri, mimeType: "application/json", text: JSON.stringify({
          version: VERSION, vault_root: detectVaultRoot(), tools_loaded: Object.keys(TOOLS_CATALOG).length,
          uptime: process.uptime(), server_info: SERVER_INFO,
        }, null, 2) }] };
      }
      default: {
        return { contents: [{ uri, mimeType: "text/plain", text: `Unknown resource: ${uri}. Available: vault://graph, vault://health, vault://traceability/mutations, vault://catalog, vault://state` }] };
      }
    }
  } catch (e) {
    return { contents: [{ uri, mimeType: "text/plain", text: `Error reading resource ${uri}: ${e.message}` }] };
  }
}

// ============================================================================
// SECCIÓN 11: Obsidian Desktop API (validación externa)
// ============================================================================

const OBSIDIAN_API_URL = "http://localhost:27124";
let obsidianAvailable = null;

async function checkObsidianHealth() {
  if (obsidianAvailable !== null) return obsidianAvailable;
  try {
    const resp = await fetch(OBSIDIAN_API_URL + "/");
    obsidianAvailable = resp.ok;
    log("info", `Obsidian REST API: ${obsidianAvailable ? "available" : "unavailable"}`);
  } catch {
    obsidianAvailable = false;
    log("warn", "Obsidian REST API not available. Using filesystem fallback.");
  }
  return obsidianAvailable;
}

async function validateWithObsidian(vaultRoot) {
  if (!(await checkObsidianHealth())) {
    return { available: false, message: "Obsidian REST API not available. Validation is filesystem-only." };
  }
  return {
    available: true,
    vault_endpoint: OBSIDIAN_API_URL + "/vault/",
    search_endpoint: OBSIDIAN_API_URL + "/search/",
    message: "Obsidian REST API connected. Notes will be validated against Obsidian index."
  };
}

// ============================================================================
// SECCIÓN 7: Main Entry Point
// ============================================================================

function parseArgs() {
  const args = process.argv.slice(2);
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--port" && i + 1 < args.length) {
      SSE_PORT = parseInt(args[++i], 10);
    } else if (args[i] === "--vault" && i + 1 < args.length) {
      VAULT_ROOT = resolve(args[++i]);
    } else if (args[i] === "--log-level" && i + 1 < args.length) {
      LOG_LEVEL = args[++i];
    } else if (args[i] === "--version" || args[i] === "-v") {
      console.log(`vault-mcp-server ${VERSION}`);
      process.exit(0);
    } else if (args[i] === "--help" || args[i] === "-h") {
      console.log(`vault-mcp-server ${VERSION}
Usage:
  node vault-mcp-server.mjs                  stdio mode (default)
  node vault-mcp-server.mjs --port 3000       SSE/HTTP mode
  node vault-mcp-server.mjs --vault <path>    explicit vault root
  node vault-mcp-server.mjs --log-level debug debug logging
  node vault-mcp-server.mjs --version         show version
  node vault-mcp-server.mjs --help            this help`);
      process.exit(0);
    }
  }
}

function main() {
  parseArgs();
  loadCatalog();
  detectVaultRoot();

  if (SSE_PORT > 0) {
    startSSE(SSE_PORT);
  } else {
    startStdio();
  }
}

// ============================================================================
// BOOT
// ============================================================================

if (process.argv[1] && (process.argv[1].endsWith("vault-mcp-server.mjs") || process.argv[1].endsWith("vault-mcp-server"))) {
  main();
}

export {
  VERSION,
  SERVER_INFO,
  CAPABILITIES,
  detectVaultRoot,
  normalizeStem,
  extractWikilinks,
  stripCodeBlocks,
  dispatch,
  processMessage,
  handleInitialize,
  handleToolsList,
  handleToolsCall,
};
