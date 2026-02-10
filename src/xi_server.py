"""
Ξ (Xi) — HTTP API Server
Copyright (c) 2026 Alex P. Slaby — MIT License

AI-first REST API for Xi operations.
All endpoints accept/return JSON. Stateless & deterministic.

Routes:
  POST /encode   {source, format?}        → {binary|json_ir}
  POST /decode   {base64}                 → {json_ir}
  POST /eval     {source, gas?, pure?}    → {result, stats}
  POST /hash     {source}                 → {hash, node_count}
  POST /normalize {source}                → {canonical, hash}
  POST /diff     {old_source, new_source} → {operations, stats}
  POST /patch    {source, operations}     → {patched, hash}
  POST /check    {source}                 → {types}
  GET  /schema                            → {json_schema}
  GET  /health                            → {ok, version}
"""

import json, hashlib, base64, time, traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from xi import Node, Tag, PrimOp, serialize
from xi_compiler import Compiler, ParseError, LexError
from xi_deserialize import deserialize
from xi_json import (to_json, from_json, canonicalize, hash_node, diff, patch,
                     diff_stats, node_count, max_depth, validate_json,
                     analyze_properties, XI_IR_SCHEMA)
from xi_optimizer import optimize
from xi_sandbox import SandboxedInterpreter, SandboxConfig


VERSION = "0.6.0"


def create_app():
    """Create and return the HTTP server application."""
    return XiServer


class XiHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Xi API."""

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self._json_response({"ok": True, "version": VERSION, "service": "xi-api"})
        elif path == "/schema":
            self._json_response(XI_IR_SCHEMA)
        else:
            self._json_response({"error": f"Unknown GET endpoint: {path}"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()

        handlers = {
            "/encode": self._handle_encode,
            "/decode": self._handle_decode,
            "/eval": self._handle_eval,
            "/hash": self._handle_hash,
            "/normalize": self._handle_normalize,
            "/diff": self._handle_diff,
            "/patch": self._handle_patch,
            "/check": self._handle_check,
        }

        handler = handlers.get(path)
        if handler:
            try:
                result = handler(body)
                self._json_response({"ok": True, **result})
            except (ParseError, LexError) as e:
                self._json_response({"ok": False, "error": str(e), "type": "parse_error"}, 400)
            except Exception as e:
                self._json_response({"ok": False, "error": str(e), "type": "internal"}, 500)
        else:
            self._json_response({"error": f"Unknown POST endpoint: {path}"}, 404)

    def _handle_encode(self, body):
        source = body.get("source", "")
        fmt = body.get("format", "json")
        entry = body.get("entry", "main")
        c = Compiler()
        defs = c.compile_program(source)
        node = defs.get(entry)
        if not node:
            raise ValueError(f"Entry '{entry}' not found. Available: {list(defs.keys())}")

        if fmt == "binary":
            b = serialize(node)
            return {"format": "xi-binary", "size_bytes": len(b),
                    "base64": base64.b64encode(b).decode(),
                    "hash": hashlib.sha256(b).hexdigest()}
        else:
            return {"format": "xi-ir-v1", **to_json(node)}

    def _handle_decode(self, body):
        b64 = body.get("base64", "")
        data = base64.b64decode(b64)
        node = deserialize(data)
        return to_json(node)

    def _handle_eval(self, body):
        source = body.get("source", "")
        gas = body.get("gas", 100000)
        pure = body.get("pure", False)
        timeout = body.get("timeout", 10.0)
        caps = body.get("capabilities", [])
        entry = body.get("entry", "main")

        c = Compiler()
        defs = c.compile_program(source)
        node = defs.get(entry)
        if not node:
            raise ValueError(f"Entry '{entry}' not found")

        config = SandboxConfig(gas=gas, timeout_seconds=timeout,
                               pure_only=pure, capabilities=caps)
        sandbox = SandboxedInterpreter(config)
        result, stats = sandbox.eval_safe(node)

        return {"result": result, "stats": stats, "sandbox": config.to_dict()}

    def _handle_hash(self, body):
        source = body.get("source", "")
        entry = body.get("entry", "main")
        c = Compiler()
        defs = c.compile_program(source)
        node = defs.get(entry)
        if not node:
            raise ValueError(f"Entry '{entry}' not found")
        return {"hash": hash_node(node), "algorithm": "sha-256",
                "node_count": node_count(node), "max_depth": max_depth(node)}

    def _handle_normalize(self, body):
        source = body.get("source", "")
        entry = body.get("entry", "main")
        c = Compiler()
        defs = c.compile_program(source)
        node = defs.get(entry)
        if not node:
            raise ValueError(f"Entry '{entry}' not found")
        opt, stats = optimize(node)
        canon = canonicalize(opt)
        return {"canonical": to_json(canon), "hash": hash_node(canon), "optimization": stats}

    def _handle_diff(self, body):
        old_src = body.get("old_source", "")
        new_src = body.get("new_source", "")
        c = Compiler()
        na = c.compile_program(old_src).get("main")
        nb = c.compile_program(new_src).get("main")
        if not na or not nb:
            raise ValueError("Both sources must have 'main'")
        ops = diff(na, nb)
        return {"old_hash": hash_node(na), "new_hash": hash_node(nb),
                "operations": ops, "stats": diff_stats(ops), "identical": len(ops) == 0}

    def _handle_patch(self, body):
        source = body.get("source", "")
        operations = body.get("operations", [])
        entry = body.get("entry", "main")
        c = Compiler()
        node = c.compile_program(source).get(entry)
        if not node:
            raise ValueError(f"Entry '{entry}' not found")
        patched = patch(node, operations)
        return {"original_hash": hash_node(node), "patched_hash": hash_node(patched),
                "patched": to_json(patched), "operations_applied": len(operations)}

    def _handle_check(self, body):
        source = body.get("source", "")
        from xi_typecheck import TypeChecker, TypeErr, type_to_str
        c = Compiler()
        defs = c.compile_program(source)
        tc = TypeChecker()
        types = {}
        for name, node in defs.items():
            try:
                ty = tc.infer_type(node)
                types[name] = type_to_str(ty) if ty else "unknown"
            except:
                types[name] = "unknown"
        return {"types": types}

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    def _json_response(self, data, code=200):
        body = json.dumps(data, indent=2, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # Suppress default logging


class XiServer(HTTPServer):
    def __init__(self, host="0.0.0.0", port=8420):
        super().__init__((host, port), XiHandler)

    def run(self, host=None, port=None):
        if host and port:
            self.server_address = (host, port)
        print(f"Ξ Xi API listening on {self.server_address[0]}:{self.server_address[1]}")
        self.serve_forever()


def create_app():
    return XiServer()


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8420
    server = XiServer(port=port)
    server.run()
