// Ajuste local generation-v1 para @google-cloud/storage-mcp@0.6.0.
// Expone metadata.generation de la misma consulta GCS; no agrega tools ni permisos.
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

export const UPSTREAM_SHA256 =
  '1b671a6438df9cd3c702cfd8a5795f20718dbac7f419395b53f6210bd319bf96';

const START = 'var formatFileMetadataResponse = (metadata) => ({\n';
export function requireGeneration(value) {
  if (typeof value !== 'string' || !/^[1-9][0-9]*$/.test(value)) {
    throw new Error('GCS no devolvió una generation válida; releer antes de aprobar la spec.');
  }
  return value;
}

const REPLACEMENT = `// gcsgrep: conservar generation como string, sin convertir a Number.
var gcsgrepRequireGeneration = ${requireGeneration.toString()};
var formatFileMetadataResponse = (metadata) => ({
  generation: gcsgrepRequireGeneration(metadata.generation),
`;

export function patchMetadata(source) {
  const text = Buffer.from(source).toString('utf8');
  // Rechaza otra versión o un bundle modificado: nunca arrancar sin el ajuste.
  if (createHash('sha256').update(text).digest('hex') !== UPSTREAM_SHA256) {
    throw new Error('generation-v1: el bundle no coincide con storage-mcp@0.6.0.');
  }
  if (text.split(START).length !== 2) {
    throw new Error('generation-v1: no encontré un único formatter de metadata.');
  }
  return text.replace(START, REPLACEMENT);
}

export async function load(url, context, nextLoad) {
  const result = await nextLoad(url, context);
  if (!url.startsWith('file:')) return result;
  const path = fileURLToPath(url).replaceAll('\\', '/');
  if (!path.endsWith('/node_modules/@google-cloud/storage-mcp/dist/bundle.js')) {
    return result;
  }
  return { ...result, source: patchMetadata(result.source) };
}
