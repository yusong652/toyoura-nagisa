#!/usr/bin/env node

import { spawn } from 'node:child_process';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, '..');
const cliEntry = path.join(repoRoot, 'packages', 'cli', 'src', 'index.tsx');
const cliPackageJson = path.join(repoRoot, 'packages', 'cli', 'package.json');
const cliTsconfig = path.join(repoRoot, 'packages', 'cli', 'tsconfig.json');

const cliRequire = createRequire(cliPackageJson);

let tsxLoaderPath;
try {
  tsxLoaderPath = cliRequire.resolve('tsx');
} catch {
  console.error('[nagisa] Missing dependency: tsx. Run `npm install` in the repository root first.');
  process.exit(1);
}

const child = spawn(
  process.execPath,
  ['--import', pathToFileURL(tsxLoaderPath).href, cliEntry, ...process.argv.slice(2)],
  {
    cwd: process.cwd(),
    env: {
      ...process.env,
      TSX_TSCONFIG_PATH: cliTsconfig,
    },
    stdio: 'inherit',
  }
);

child.on('error', (error) => {
  console.error(`[nagisa] Failed to launch CLI: ${error.message}`);
  process.exit(1);
});

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 0);
});
