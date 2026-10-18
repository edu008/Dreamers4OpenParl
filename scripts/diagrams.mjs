#!/usr/bin/env node
// Baut und prüft die Architektur-Diagramme mit Archify (.claude/skills/archify).
//
//   node scripts/diagrams.mjs build [name ...]  finalize je Quelle (inkl. Browser-Check), aktualisiert manifest.json
//   node scripts/diagrams.mjs check             validate je Quelle und Abgleich der Hashes mit manifest.json
//
// Quellen: docs/architecture/src/<name>.json, Ausgabe: docs/architecture/<name>.html.
// Belege von Archify landen in .archify/<name>/ (nicht im Repo).
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { basename, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const SRC_DIR = 'docs/architecture/src';
const OUT_DIR = 'docs/architecture';
const MANIFEST = join(OUT_DIR, 'manifest.json');
const ARCHIFY_DIR = '.claude/skills/archify';
const ARCHIFY = join(ARCHIFY_DIR, 'bin/archify.mjs');
const WORK_DIR = '.archify';

const abs = (path) => join(ROOT, path);
const sha256 = (path) => createHash('sha256').update(readFileSync(abs(path))).digest('hex');

function listSources(names) {
  const all = readdirSync(abs(SRC_DIR))
    .filter((file) => file.endsWith('.json'))
    .map((file) => basename(file, '.json'))
    .sort();
  if (names.length === 0) return all;
  const unknown = names.filter((name) => !all.includes(name));
  if (unknown.length > 0) {
    throw new Error(`Unbekannte Diagramme: ${unknown.join(', ')} (vorhanden: ${all.join(', ')})`);
  }
  return names;
}

function readSpec(name) {
  const path = join(SRC_DIR, `${name}.json`);
  const spec = JSON.parse(readFileSync(abs(path), 'utf8'));
  const output = `${OUT_DIR}/${name}.html`;
  if (spec.meta?.output !== output) {
    throw new Error(`${path}: meta.output muss "${output}" sein, ist "${spec.meta?.output}"`);
  }
  return {
    path,
    output,
    type: spec.diagram_type,
    quality: spec.meta.quality_profile ?? 'showcase',
  };
}

function runArchify(args) {
  return spawnSync(process.execPath, [abs(ARCHIFY), ...args], {
    cwd: ROOT,
    encoding: 'utf8',
    maxBuffer: 64 * 1024 * 1024,
    env: { ...process.env, ARCHIFY_UPDATE_CHECK_DISABLED: '1' },
  });
}

function parseJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function report(name, result) {
  const receipt = parseJson(result.stdout);
  if (!receipt) {
    console.error(`FEHLER ${name}\n${result.stdout}\n${result.stderr}`);
    return;
  }
  const stage = receipt.failedStage ? ` (Stufe ${receipt.failedStage})` : '';
  console.error(`FEHLER ${name}${stage}`);
  for (const d of receipt.diagnostics ?? receipt.errors ?? []) {
    console.error(`  ${d.code ?? d.rule ?? 'fehler'}: ${d.message ?? JSON.stringify(d)}`);
  }
  for (const hint of receipt.hints ?? []) console.error(`  Hinweis: ${hint}`);
}

function loadManifest() {
  if (!existsSync(abs(MANIFEST))) return { archify: null, diagrams: {} };
  return JSON.parse(readFileSync(abs(MANIFEST), 'utf8'));
}

function archifyVersion() {
  const release = JSON.parse(readFileSync(abs(join(ARCHIFY_DIR, 'skill-release.json')), 'utf8'));
  return release.version;
}

function build(names) {
  const manifest = loadManifest();
  let failed = 0;
  for (const name of listSources(names)) {
    const spec = readSpec(name);
    const workDir = join(WORK_DIR, name);
    rmSync(abs(workDir), { recursive: true, force: true });
    mkdirSync(abs(workDir), { recursive: true });
    const result = runArchify([
      'finalize', spec.type, spec.path, spec.output,
      '--quality', spec.quality, '--out-dir', workDir, '--json',
    ]);
    if (result.status !== 0) {
      failed += 1;
      report(name, result);
      continue;
    }
    manifest.diagrams[name] = {
      type: spec.type,
      quality: spec.quality,
      source_sha256: sha256(spec.path),
      html_sha256: sha256(spec.output),
    };
    console.log(`ok     ${name}`);
  }
  manifest.archify = archifyVersion();
  manifest.diagrams = Object.fromEntries(Object.entries(manifest.diagrams).sort(([a], [b]) => a.localeCompare(b)));
  writeFileSync(abs(MANIFEST), `${JSON.stringify(manifest, null, 2)}\n`);
  if (failed > 0) {
    console.error(`${failed} Diagramm(e) fehlgeschlagen.`);
    process.exit(1);
  }
}

function check() {
  const manifest = loadManifest();
  const names = listSources([]);
  let problems = 0;
  const problem = (message) => {
    problems += 1;
    console.error(message);
  };
  for (const name of names) {
    const spec = readSpec(name);
    const result = runArchify(['validate', spec.type, spec.path, '--quality', spec.quality, '--json']);
    if (result.status !== 0) {
      problems += 1;
      report(name, result);
      continue;
    }
    const entry = manifest.diagrams[name];
    if (!entry) {
      problem(`${name}: fehlt in ${MANIFEST}. "make diagrams" ausführen.`);
      continue;
    }
    if (!existsSync(abs(spec.output))) {
      problem(`${name}: ${spec.output} fehlt. "make diagrams" ausführen.`);
      continue;
    }
    if (entry.source_sha256 !== sha256(spec.path)) {
      problem(`${name}: Quelle geändert, HTML veraltet. "make diagrams" ausführen.`);
    }
    if (entry.html_sha256 !== sha256(spec.output)) {
      problem(`${name}: HTML passt nicht zum Manifest. Nicht von Hand ändern, "make diagrams" ausführen.`);
    }
    if (problems === 0) console.log(`ok     ${name}`);
  }
  for (const name of Object.keys(manifest.diagrams)) {
    if (!names.includes(name)) problem(`${name}: im Manifest, aber ohne Quelle in ${SRC_DIR}.`);
  }
  if (problems > 0) process.exit(1);
}

const [command, ...rest] = process.argv.slice(2);
try {
  if (command === 'build') build(rest);
  else if (command === 'check') check();
  else {
    console.error('Aufruf: node scripts/diagrams.mjs build [name ...] | check');
    process.exit(2);
  }
} catch (error) {
  console.error(error.message);
  process.exit(1);
}
