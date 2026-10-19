#!/usr/bin/env node
/**
 * mmd_validate.mjs — Oráculo Mermaid: el compilador real (`mermaid.parse`,
 * mermaid core sobre jsdom) como validador en batch.
 *
 * Por qué existe: el parser heurístico del estándar (`vault_mermaid_reglas`,
 * regex sobre líneas) deja pasar errores de sintaxis que el compilador de
 * Mermaid rechaza — medido 2026-10-19 contra SMART POS CR: 6 bloques que
 * jison rechaza (`-->|false (default)|` con paréntesis sin comillas, entidad
 * ER con comillas erradas, `stateDiagram-v2` vacío, `<br/>` antes de `]` en
 * label, 2 labels sin cerrar) y el heurístico no ve; y produce falsos
 * positivos (`mismatched_braces` en `fe-cr-entidades-fiscales.md` y
 * `mvp-pos-diagramas.md` que el compilador aprueba). El lenguaje del
 * compilador es el criterio del consumidor (AP-44): el renderer real es
 * quien decide si un diagrama se pinta.
 *
 * Alcance del oráculo: SINTAXIS. Las reglas semánticas del dominio
 * (`undefined_class`, `undefined_entity`, `undefined_state`) siguen siendo
 * del estándar — Mermaid auto-crea clases/entidades al relacionarlas y por
 * eso el compilador las aprueba; el estándar las exige declaradas (AP-25).
 *
 * Uso:
 *   node mmd_validate.mjs <entrada.json> [salida.json]
 *
 * Entrada: JSON `[{id, code}]` (los bloques ya extraídos de los .md).
 * Salida: JSON `{ok, reason?, parser, results: [{id, ok, diagramType?, error?}]}`.
 *
 * Dependencias: `mermaid` + `jsdom`. Se resuelven así:
 *   1. junto a este fichero (`mcp/nodejs/node_modules`): `npm install mermaid jsdom`,
 *   2. directorio señalado por la var de entorno `VOAS_MERMAID_ORACLE`
 *      (es.pack-dir foraneo al repo, útil para venvs instalados desde wheel).
 * Si no se resuelven: se emite `ok:false, reason:"oraculo-no-instalado"` y el
 * caller (vault_mermaid_check.py) degrada al heurístico **declarando** su
 * cobertura parcial — no simula haber validado (AP-51: un vacío honesto).
 *
 * Un proceso valida N bloques: jsdom + import de mermaid son una vez.
 */

import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL, fileURLToPath } from 'node:url';

const PARSER = 'mermaid-core';

function fail(json_out, { reason, detail }) {
  const envelope = { ok: false, reason, detail, parser: PARSER, results: [] };
  if (json_out) fs.writeFileSync(json_out, JSON.stringify(envelope, null, 1), 'utf8');
  else process.stdout.write(JSON.stringify(envelope, null, 1));
  process.exit(0);
}

// --- resolución de mermaid + jsdom (así de simple, sin instalar nada) ---

const r = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));

// AP-57 (frontera python->nodejs): nombrar la constante no es el delito,
// decidirla sí. El nombre de la variable del oráculo se valida contra la
// PASARELA derivada (`env-table.json`, que `vault_arch.py --sync-env`
// genera desde `vault/kernel/entorno.py`). Si el registro renombra la var,
// el helper degrada nombrándolo en vez de seguir escuchando una constante
// que ya nadie declara — cruzar por el artefacto, no copiar el criterio.
const VAR_ORACULO = "VOAS_MERMAID_ORACLE";
let declarada_en_tabla = null;
try {
  const tabla = JSON.parse(fs.readFileSync(path.join(aqui, "env-table.json"), "utf8"));
  declarada_en_tabla = Array.isArray(tabla.variables) && tabla.variables.some((v) => v.name === VAR_ORACULO);
} catch (sin_tabla) {
  declarada_en_tabla = null; // sin pasarela: la degradación lo dirá abajo
}

const dirs_extra = [];
if (declarada_en_tabla && process.env[VAR_ORACULO]) dirs_extra.push(path.resolve(process.env[VAR_ORACULO]));

// Un intento de resolución devuelve la ruta del paquete o null: el catch
// madruga al vacío con una instrucción (return), no se lo traga callado.
function _resolver_uno(pkg, dir) {
  try {
    return path.dirname(r.resolve(pkg, { paths: [dir] }));
  } catch (no_resuelve) {
    return null;
  }
}

function resolver(pkg) {
  return _resolver_uno(pkg, aqui) ?? dirs_extra.map((d) => _resolver_uno(pkg, d)).find(Boolean) ?? null;
}

// --- bootstrap: DOM de jsdom ANTES de importar mermaid (DOMPurify se arma
// contra la window global al cargarse; después ya es tarde) ---

let mermaid, jsdomMod;
const entry_mermaid = resolver('mermaid/package.json');
const entry_jsdom = resolver('jsdom/package.json');
if (!entry_mermaid || !entry_jsdom) {
  fail(null, { reason: 'oraculo-no-instalado', detail: `mermaid: ${entry_mermaid ?? 'no resuelto'} | jsdom: ${entry_jsdom ?? 'no resuelto'} (npm install mermaid jsdom en ${aqui} o ${VAR_ORACULO})` });
}
if (declarada_en_tabla === false) {
  // La pasarela existe y ya no declara la constante que el caller usó.
  fail(null, { reason: 'oraculo-no-instalado', detail: `env-table.json (pasarela derivada de vault_entorno) no declara ${VAR_ORACULO}: el registro renombró la variable; alinear el caller (vault_mermaid_check) con la tabla` });
}
// r.resolve('x/package.json') resuelve aunque el paquete sea ESM-only;
// el punto de entrada real sale del campo exports del package.json.
const exports_json = JSON.parse(fs.readFileSync(path.join(entry_mermaid, 'package.json'), 'utf8'));
const punto = (exports_json.exports?.['.']?.import) || exports_json.main;

jsdomMod = await import(pathToFileURL(path.join(entry_jsdom, 'lib', 'api.js')).href);
const { JSDOM } = jsdomMod;
const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
  url: 'http://mermaid.test/',
  pretendToBeVisual: true,
});
Object.defineProperty(globalThis, 'window', { value: dom.window, configurable: true });
globalThis.document = dom.window.document;
// Node ≥21 ya trae `navigator` global; solo se define si el runtime no lo tiene.
if (globalThis.navigator === undefined) {
  Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true });
}

// mermaid se importa DESPUÉS de tener el DOM, apuntando a su entry resuelto
mermaid = (await import(pathToFileURL(path.join(entry_mermaid, punto ?? 'dist/mermaid.core.mjs')).href)).default;
mermaid.initialize({ startOnLoad: false, suppressErrorRendering: true });

// --- lote ---

// `"-"` como entrada → stdin; como salida → stdout. Evita artefactos tmp
// en disco (AP-36): el caller pasa el JSON por stdin y lee el veredicto del stdout.
const argv_in = process.argv[2];
const argv_out = process.argv[3];
const contenido_sin = (argv_in && argv_in !== "-") ? fs.readFileSync(argv_in, "utf8") : fs.readFileSync(0, "utf8");
const entrada = JSON.parse(contenido_sin);
const a_archivo = argv_out && argv_out !== "-";

const results = [];
for (const it of entrada) {
  const rBloque = { id: it.id, ok: false };
  try {
    const res = await mermaid.parse(it.code);
    rBloque.ok = true;
    rBloque.diagramType = res?.diagramType ?? null;
  } catch (e) {
    // El compilador habla: "Parse error on line N: ...markdown^". Mensaje
    // colapsado a pocas líneas — la línea y el contexto son lo accionable.
    rBloque.error = String(e?.message ?? e).split('\n').slice(0, 4).join(' | ').slice(0, 400);
    if (e?.name) rBloque.errorName = e.name;
  }
  results.push(rBloque);
}

const envelope = { ok: true, parser: PARSER, results };
const texto = JSON.stringify(envelope, null, 1);
if (a_archivo) fs.writeFileSync(argv_out, texto, "utf8");
else process.stdout.write(texto);
