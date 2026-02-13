#!/usr/bin/env node

import { execSync, spawnSync } from 'node:child_process';
import os from 'node:os';

function parseArgs(argv) {
  const args = [...argv];
  const dryRun = args.includes('--dry-run');
  const positional = args.filter((arg) => !arg.startsWith('--'));
  const target = positional[0] ?? 'backend';
  return { target, dryRun };
}

function resolvePorts(target) {
  const devPortRaw = process.env.DEV_PORT ?? '8000';
  const devPort = Number.parseInt(devPortRaw, 10);
  const backendPort = Number.isFinite(devPort) ? devPort : 8000;

  const presets = {
    backend: [backendPort],
    web: [5173],
    all: [backendPort, 5173],
  };

  if (presets[target]) {
    return presets[target];
  }

  if (/^\d+$/.test(target)) {
    return [Number.parseInt(target, 10)];
  }

  if (/^\d+(,\d+)+$/.test(target)) {
    return target.split(',').map((part) => Number.parseInt(part, 10));
  }

  throw new Error(`Unknown target: ${target}. Use backend|web|all|<port>|<port,port>.`);
}

function getPidsWindows(port) {
  const output = execSync('netstat -ano -p tcp', { encoding: 'utf8' });
  const pids = new Set();

  for (const rawLine of output.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line.startsWith('TCP')) {
      continue;
    }

    const cols = line.split(/\s+/);
    if (cols.length < 5) {
      continue;
    }

    const localAddress = cols[1];
    const state = cols[3];
    const pid = cols[4];

    if (state !== 'LISTENING') {
      continue;
    }
    if (!localAddress.endsWith(`:${port}`)) {
      continue;
    }

    pids.add(pid);
  }

  return [...pids];
}

function getPidsUnix(port) {
  const pids = new Set();

  try {
    const output = execSync(`lsof -ti tcp:${port} -sTCP:LISTEN`, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
    for (const line of output.split(/\r?\n/)) {
      const pid = line.trim();
      if (/^\d+$/.test(pid)) {
        pids.add(pid);
      }
    }
    return [...pids];
  } catch {
    // Fall back to ss below.
  }

  try {
    const output = execSync('ss -ltnp', { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
    for (const rawLine of output.split(/\r?\n/)) {
      if (!rawLine.includes(`:${port}`)) {
        continue;
      }
      const matches = rawLine.matchAll(/pid=(\d+)/g);
      for (const match of matches) {
        pids.add(match[1]);
      }
    }
  } catch {
    // No available command to discover pids.
  }

  return [...pids];
}

function getPidsForPort(port) {
  if (os.platform() === 'win32') {
    return getPidsWindows(port);
  }
  return getPidsUnix(port);
}

function killPid(pid) {
  if (os.platform() === 'win32') {
    const result = spawnSync('taskkill', ['/PID', String(pid), '/F'], { stdio: 'ignore' });
    return result.status === 0;
  }

  try {
    process.kill(Number.parseInt(String(pid), 10), 'SIGKILL');
    return true;
  } catch {
    return false;
  }
}

function main() {
  const { target, dryRun } = parseArgs(process.argv.slice(2));
  const ports = resolvePorts(target);
  let totalKilled = 0;

  for (const port of ports) {
    const pids = getPidsForPort(port);
    if (pids.length === 0) {
      console.log(`[kill-ports] port ${port}: no listener`);
      continue;
    }

    if (dryRun) {
      console.log(`[kill-ports] port ${port}: would kill PIDs ${pids.join(', ')}`);
      continue;
    }

    const killed = [];
    const failed = [];

    for (const pid of pids) {
      if (killPid(pid)) {
        killed.push(pid);
      } else {
        failed.push(pid);
      }
    }

    totalKilled += killed.length;
    if (killed.length > 0) {
      console.log(`[kill-ports] port ${port}: killed PIDs ${killed.join(', ')}`);
    }
    if (failed.length > 0) {
      console.log(`[kill-ports] port ${port}: failed to kill PIDs ${failed.join(', ')}`);
    }
  }

  if (dryRun) {
    console.log('[kill-ports] dry-run complete');
    return;
  }

  console.log(`[kill-ports] done, killed ${totalKilled} process(es)`);
}

try {
  main();
} catch (error) {
  console.error(`[kill-ports] ${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
}
