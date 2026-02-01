import { spawn } from 'node:child_process';

export function openBrowser(url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    let command: string;
    let args: string[];

    if (process.platform === 'darwin') {
      command = 'open';
      args = [url];
    } else if (process.platform === 'win32') {
      command = 'cmd';
      args = ['/c', 'start', '', url];
    } else {
      command = 'xdg-open';
      args = [url];
    }

    let settled = false;
    const child = spawn(command, args, {
      stdio: 'ignore',
      detached: true,
      windowsHide: true,
    });

    const settle = (err?: Error) => {
      if (settled) return;
      settled = true;
      if (err) {
        reject(err);
      } else {
        resolve();
      }
    };

    child.once('error', settle);
    child.once('spawn', () => {
      child.unref();
      settle();
    });
  });
}
