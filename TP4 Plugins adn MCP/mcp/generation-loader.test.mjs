import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { load, patchMetadata, requireGeneration } from './generation-loader.mjs';
import { preloadOptions } from './start-storage-mcp.mjs';

test('generation se conserva como string, incluso fuera del rango seguro de Number', () => {
  for (const value of ['1791942299203604', '18446744073709551615']) {
    assert.equal(requireGeneration(value), value);
  }
});

test('generation ausente, numérica o inválida produce error, sin fallback a fecha/tamaño', () => {
  for (const value of [undefined, null, 1791942299203604, '', '0', '-1', '1.2', '2026-10-14']) {
    assert.throws(() => requireGeneration(value), /generation válida/);
  }
});

test('otro bundle o versión se rechaza antes de arrancar', () => {
  assert.throws(() => patchMetadata('var formatFileMetadataResponse = (metadata) => ({\n});'), /no coincide/);
});

test('el loader deja intactos los módulos ajenos al server', async () => {
  const original = { format: 'module', source: 'export const x = 1;' };
  assert.equal(await load('file:///tmp/otro.mjs', {}, async () => original), original);
});

test('el loader rechaza un bundle upstream modificado', async () => {
  await assert.rejects(
    load('file:///tmp/node_modules/@google-cloud/storage-mcp/dist/bundle.js', {},
      async () => ({ format: 'module', source: 'alterado' })),
    /no coincide/,
  );
});

test('la ruta de precarga del plugin admite Windows y espacios', async () => {
  const options = preloadOptions(new URL('file:///C:/Users/Equipo%20Demo/gcsgrep-sdd/mcp/register-generation.mjs'));
  const url = options.match(/^--import "(.+)"$/)[1];
  assert.ok(!options.includes('\\'));
  assert.ok(options.includes('%20'));
  assert.equal(fileURLToPath(url, { windows: true }),
    'C:\\Users\\Equipo Demo\\gcsgrep-sdd\\mcp\\register-generation.mjs');
});

test('el launcher rechaza flags adicionales antes de ejecutar npx', () => {
  const script = fileURLToPath(new URL('./start-storage-mcp.mjs', import.meta.url));
  const result = spawnSync(process.execPath,
    [script, '@google-cloud/storage-mcp@0.6.0', '--enable-destructive-tools'],
    { encoding: 'utf8' });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Arranque permitido/);
});

// Permite verificar el formatter real del paquete descargado sin credenciales GCP.
test('formatter del bundle oficial expone generation y conserva los otros campos', {
  skip: !process.env.STORAGE_MCP_BUNDLE && 'definir STORAGE_MCP_BUNDLE con el dist/bundle.js oficial 0.6.0',
}, async () => {
  const patched = patchMetadata(await readFile(process.env.STORAGE_MCP_BUNDLE));
  const start = patched.indexOf('var gcsgrepRequireGeneration = ');
  const end = patched.indexOf('var validateBase64Content = ', start);
  const formatter = vm.runInNewContext(
    patched.slice(start, end) + '\nformatFileMetadataResponse;',
  );
  const metadata = {
    bucket: 'bucket-de-prueba', name: 'x.log', generation: '18446744073709551615',
    size: '12', contentType: 'text/plain', timeCreated: '2026-10-14T01:00:00Z',
    updated: '2026-10-14T02:00:00Z', storageClass: 'STANDARD', metadata: { x: 'dato' },
  };
  const result = formatter(metadata);
  assert.equal(result.generation, metadata.generation);
  assert.equal(result.size, 12);
  assert.equal(result.time_created, metadata.timeCreated);
  assert.equal(result.updated, metadata.updated);
  assert.equal(result.metadata, metadata.metadata);
  assert.throws(() => formatter({ ...metadata, generation: undefined }), /generation válida/);
});
