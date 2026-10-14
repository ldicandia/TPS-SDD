// Node --import: registra el ajuste antes de que arranque storage-mcp.
import { register } from 'node:module';

register('./generation-loader.mjs', import.meta.url);
