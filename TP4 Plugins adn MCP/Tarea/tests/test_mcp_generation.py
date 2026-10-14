"""MCP real + API GCS local: sin ADC, red externa ni bucket real.

Definir STORAGE_MCP_BUNDLE con el dist/bundle.js oficial instalado (0.6.0).
Opcional: GCSGREP_NODE con la ruta a Node 24. Sin bundle se saltea explícitamente.
"""
import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
BUNDLE = os.environ.get("STORAGE_MCP_BUNDLE")
NODE = os.environ.get("GCSGREP_NODE") or shutil.which("node")


class API(BaseHTTPRequestHandler):
    generation = "1791942299203604"
    paths = []

    def do_GET(self):
        type(self).paths.append(self.path)
        if "/b/bucket-de-prueba/o/x.log" not in self.path:
            self.send_error(404)
            return
        metadata = {
            "bucket": "bucket-de-prueba", "name": "x.log", "size": "12",
            "contentType": "text/plain", "timeCreated": "2026-10-14T01:00:00Z",
            "updated": "2026-10-14T01:00:00Z", "storageClass": "STANDARD",
        }
        if type(self).generation is not None:
            metadata["generation"] = type(self).generation
        body = json.dumps(metadata).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


@unittest.skipUnless(BUNDLE and NODE, "requiere STORAGE_MCP_BUNDLE y Node 24")
class GenerationMCP(unittest.TestCase):
    def test_metadata_y_reemplazo_desde_proyecto_y_plugin(self):
        for mode in ("proyecto", "plugin"):
            with self.subTest(mode=mode):
                self.run_session(mode)

    def run_session(self, mode):
        API.generation = "1791942299203604"
        API.paths = []
        api = ThreadingHTTPServer(("127.0.0.1", 0), API)
        thread = threading.Thread(target=api.serve_forever, daemon=True)
        thread.start()
        messages = queue.Queue()
        try:
            with tempfile.TemporaryDirectory(prefix="tp4-plugin-") as empty:
                config_root = RAIZ if mode == "proyecto" else RAIZ / "plugin/gcsgrep-sdd"
                config = json.loads((config_root / ".mcp.json").read_text())
                options = '--import "' + (config_root / "mcp/register-generation.mjs").as_uri() + '"'
                env = os.environ.copy()
                env.update({
                    "NODE_OPTIONS": options,
                    "STORAGE_EMULATOR_HOST": "http://127.0.0.1:" + str(api.server_port),
                    "GOOGLE_CLOUD_PROJECT": "demo-local",
                    "GOOGLE_APPLICATION_CREDENTIALS": str(Path(empty) / "adc-inexistente.json"),
                    "NO_PROXY": "127.0.0.1,localhost",
                })
                command = [NODE, str(Path(BUNDLE).resolve())]
                if os.environ.get("GCSGREP_MCP_NPX") == "1":
                    command = [NODE] + [a.replace("${CLAUDE_PLUGIN_ROOT}", str(config_root))
                                        for a in config["mcpServers"]["gcs"]["args"]]
                    env["PATH"] = str(Path(NODE).parent) + os.pathsep + env["PATH"]
                    env.pop("NODE_OPTIONS")  # El launcher calcula la precarga.
                proc = subprocess.Popen(
                    command, env=env,
                    cwd=str(RAIZ) if mode == "proyecto" else empty,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding="utf-8",
                )
                stderr = []

                def read_messages():
                    try:
                        for line in proc.stdout:
                            messages.put(json.loads(line))
                    finally:
                        messages.put(None)

                def read_errors():
                    stderr.extend(proc.stderr)

                readers = [threading.Thread(target=read_messages, daemon=True),
                           threading.Thread(target=read_errors, daemon=True)]
                for reader in readers:
                    reader.start()
                request_id = 0

                def rpc(method, params=None):
                    nonlocal request_id
                    request_id += 1
                    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": request_id,
                                                "method": method, "params": params or {}}) + "\n")
                    proc.stdin.flush()
                    while True:
                        try:
                            response = messages.get(timeout=30)
                        except queue.Empty:
                            self.fail("MCP no respondió: " + "".join(stderr)[-2000:])
                        if response is None:
                            readers[1].join(timeout=1)
                            self.fail("MCP terminó antes de responder: " + "".join(stderr)[-2000:])
                        if response.get("id") == request_id:
                            self.assertNotIn("error", response, response)
                            return response["result"]

                def metadata():
                    result = rpc("tools/call", {"name": "read_object_metadata", "arguments": {
                        "bucket_name": "bucket-de-prueba", "object_name": "x.log"}})
                    return json.loads(result["content"][0]["text"])

                try:
                    rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                       "clientInfo": {"name": "tp4-generation-test", "version": "1.0"}})
                    proc.stdin.write('{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
                    proc.stdin.flush()
                    names = {t["name"] for t in rpc("tools/list")["tools"]}
                    self.assertEqual(len(names), 15)
                    self.assertIn("write_object_safe", names)
                    self.assertNotIn("delete_object", names)
                    before = metadata()
                    self.assertEqual(before["generation"], "1791942299203604")
                    # Nueva versión, incluso con fecha y tamaño idénticos.
                    API.generation = "18446744073709551615"
                    after = metadata()
                    self.assertNotEqual(before["generation"], after["generation"])
                    self.assertEqual(after["generation"], API.generation)
                    self.assertEqual(before["time_created"], after["time_created"])
                    self.assertEqual(before["size"], after["size"])
                    API.generation = None
                    self.assertIn("generation válida", metadata()["error"])
                    self.assertEqual(len(API.paths), 3)
                finally:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)
                    for reader in readers:
                        reader.join(timeout=2)
                    for stream in (proc.stdin, proc.stdout, proc.stderr):
                        stream.close()
        finally:
            api.shutdown()
            api.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
