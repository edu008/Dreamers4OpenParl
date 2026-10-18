#!/usr/bin/env node
// Prüft den Build der Web-App (web/dist) auf Abhängigkeiten nach aussen (PRD 9 Offline, ADR 0006).
//
//   node scripts/check-web-dist.mjs [verzeichnis]   Standard: web/dist
//
// Regeln:
//   1. HTML lädt nichts von fremden Hosts (src, href, srcset, content mit http:, https: oder //).
//   2. CSS lädt nichts von fremden Hosts (url(...) und @import nur relativ, absolut oder data:).
//   3. Jede URL im Build gehört zu einem erlaubten Host. Erlaubt sind nur Hosts, die nie geladen
//      werden: XML-Namensräume, Doku-Links in Fehlermeldungen, Lizenzkommentare.
// Ein neuer Host bricht die Prüfung ab und muss bewusst auf die Liste.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { extname, join, relative } from 'node:path';

const ALLOWED_HOSTS = new Map([
  ['www.w3.org', 'XML-Namensräume für SVG, MathML und XLink'],
  ['react.dev', 'Link in React-Fehlermeldungen'],
  ['reactrouter.com', 'Link in React-Router-Warnungen'],
  ['base-ui.com', 'Link in Base-UI-Fehlermeldungen'],
  ['tailwindcss.com', 'Lizenzkommentar im CSS'],
  ['localhost', 'Basis-URL für Pfadberechnungen in React Router'],
]);
const TEXT_TYPES = new Set(['.html', '.js', '.mjs', '.css', '.svg', '.json', '.txt', '.webmanifest']);
const EXTERNAL = /^(?:https?:)?\/\//i;

const dist = process.argv[2] ?? 'web/dist';
const errors = [];

function files(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? files(path) : [path];
  });
}

let all;
try {
  all = files(dist);
} catch {
  console.error(`${dist} fehlt: zuerst make web-build ausführen`);
  process.exit(1);
}
if (!all.some((path) => relative(dist, path) === 'index.html')) {
  errors.push('index.html fehlt');
}

const hosts = new Map();
for (const path of all.filter((p) => TEXT_TYPES.has(extname(p)))) {
  const name = relative(dist, path);
  const text = readFileSync(path, 'utf8');
  if (extname(path) === '.html') {
    for (const [, attr, value] of text.matchAll(/\b(src|href|srcset|content)\s*=\s*["']([^"']*)["']/gi)) {
      if (EXTERNAL.test(value.trim())) errors.push(`${name}: ${attr}="${value}" lädt von aussen`);
    }
  }
  if (extname(path) === '.css') {
    for (const [, value] of text.matchAll(/url\(\s*["']?([^"')]+)/gi)) {
      if (EXTERNAL.test(value.trim())) errors.push(`${name}: url(${value}) lädt von aussen`);
    }
    for (const [, value] of text.matchAll(/@import\s+(?:url\()?\s*["']?([^"');\s]+)/gi)) {
      if (EXTERNAL.test(value.trim())) errors.push(`${name}: @import ${value} lädt von aussen`);
    }
  }
  for (const [, host] of text.matchAll(/https?:\/\/([A-Za-z0-9.-]+)/g)) {
    const key = host.toLowerCase();
    if (!hosts.has(key)) hosts.set(key, new Set());
    hosts.get(key).add(name);
  }
}

for (const [host, where] of [...hosts].sort()) {
  if (ALLOWED_HOSTS.has(host)) {
    console.log(`ok     ${host} (${ALLOWED_HOSTS.get(host)})`);
  } else {
    errors.push(`unbekannter Host ${host} in ${[...where].join(', ')}`);
  }
}

if (errors.length > 0) {
  for (const error of errors) console.error(`FEHLER ${error}`);
  process.exit(1);
}
console.log(`${dist}: ${all.length} Dateien, keine Abhängigkeit nach aussen`);
