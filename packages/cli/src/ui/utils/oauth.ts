import { createServer } from 'node:http';

export interface OAuthCallbackResult {
  code: string;
  state: string;
}

interface WaitForOAuthCallbackOptions {
  expectedState: string;
  timeoutMs: number;
  /** Optional port override (default: 8085 for Google, 1455 for OpenAI) */
  port?: number;
  /** Optional path override (default: /oauth2callback for Google, /auth/callback for OpenAI) */
  path?: string;
}

const DEFAULT_CALLBACK_PORT = 8085;
const DEFAULT_CALLBACK_PATH = '/oauth2callback';
const CALLBACK_HOST = 'localhost';

export function waitForOAuthCallback({
  expectedState,
  timeoutMs,
  port = DEFAULT_CALLBACK_PORT,
  path = DEFAULT_CALLBACK_PATH,
}: WaitForOAuthCallbackOptions): Promise<OAuthCallbackResult> {
  return new Promise((resolve, reject) => {
    let timeout: NodeJS.Timeout | null = null;

    const server = createServer((req, res) => {
      try {
        const requestUrl = new URL(req.url ?? '/', `http://${CALLBACK_HOST}:${port}`);
        if (requestUrl.pathname !== path) {
          res.statusCode = 404;
          res.setHeader('Content-Type', 'text/plain');
          res.end('Not found');
          return;
        }

        const error = requestUrl.searchParams.get('error');
        if (error) {
          const errorDesc = requestUrl.searchParams.get('error_description') || error;
          res.statusCode = 400;
          res.setHeader('Content-Type', 'text/plain');
          res.end(`Authentication failed: ${errorDesc}`);
          finish(new Error(`OAuth error: ${errorDesc}`));
          return;
        }

        const code = requestUrl.searchParams.get('code')?.trim();
        const state = requestUrl.searchParams.get('state')?.trim();

        if (!code || !state) {
          res.statusCode = 400;
          res.setHeader('Content-Type', 'text/plain');
          res.end('Missing code or state');
          finish(new Error('Missing OAuth code or state'));
          return;
        }

        if (state !== expectedState) {
          res.statusCode = 400;
          res.setHeader('Content-Type', 'text/plain');
          res.end('Invalid state');
          finish(new Error('OAuth state mismatch'));
          return;
        }

        res.statusCode = 200;
        res.setHeader('Content-Type', 'text/html; charset=utf-8');
        res.end(
          '<!doctype html><html><head><meta charset="utf-8"/></head>' +
            '<body><h2>OAuth Authentication Complete</h2>' +
            '<p>You can close this window and return to the terminal.</p></body></html>'
        );

        finish(undefined, { code, state });
      } catch (err) {
        finish(err instanceof Error ? err : new Error('OAuth callback failed'));
      }
    });

    const finish = (err?: Error, result?: OAuthCallbackResult) => {
      if (timeout) {
        clearTimeout(timeout);
        timeout = null;
      }
      try {
        server.close();
      } catch {
        // ignore close errors
      }
      if (err) {
        reject(err);
      } else if (result) {
        resolve(result);
      }
    };

    server.once('error', (err) => {
      finish(err instanceof Error ? err : new Error('OAuth callback server error'));
    });

    server.listen(port, CALLBACK_HOST, () => {
      timeout = setTimeout(() => {
        finish(new Error('OAuth callback timeout'));
      }, timeoutMs);
    });
  });
}
