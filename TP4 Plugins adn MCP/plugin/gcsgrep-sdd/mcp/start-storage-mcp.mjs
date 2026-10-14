// Arranque portátil: Node convierte la ruta de precarga a URL antes de llamar npx.
// Evita que NODE_OPTIONS interprete las barras de una ruta Windows como escapes.
import { spawn } from 'node:child_process';
import { pathToFileURL } from 'node:url';

const PACKAGE = '@google-cloud/storage-mcp@0.6.0';

export function preloadOptions(registerURL) {
  return `--import "${registerURL.href}"`;
}

function start() {
  if (process.argv.length !== 3 || process.argv[2] !== PACKAGE) {
    throw new Error(`Arranque permitido: node start-storage-mcp.mjs ${PACKAGE}`);
  }
  const child = spawn('npx', ['-y', PACKAGE], {
    stdio: 'inherit',
    env: { ...process.env,
      NODE_OPTIONS: preloadOptions(new URL('./register-generation.mjs', import.meta.url)) },
    // npx.cmd requiere el shell de Windows; el comando y ambos args son constantes.
    shell: process.platform === 'win32',
    detached: process.platform !== 'win32',
  });
  child.on('error', (error) => {
    console.error(`generation-v1: no pude arrancar npx: ${error.message}`);
    process.exitCode = 1;
  });
  child.on('exit', (code) => { process.exitCode = code ?? 1; });
  for (const signal of ['SIGINT', 'SIGTERM']) {
    process.on(signal, () => {
      try {
        if (process.platform === 'win32') child.kill(signal);
        else process.kill(-child.pid, signal);
      } catch (error) {
        if (error.code !== 'ESRCH') throw error;
      }
    });
  }
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) start();
