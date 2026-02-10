#!/usr/bin/env python3
"""
Ξ (Xi) CLI — AI-First Command-Line Tool
Copyright (c) 2026 Alex P. Slaby — MIT License

Machine-readable interface. All commands produce JSON on stdout.

EXIT CODES:  0=success  1=input  2=runtime  3=type  4=io  5=internal

COMMANDS:
  xi encode [--json] <file | -e 'expr'>   Source → binary/JSON-IR
  xi decode <file.xi>                      Binary → JSON-IR
  xi eval <file | -e 'expr'> [--gas N] [--pure] [--timeout N]
  xi hash <file | -e 'expr'>              SHA-256 content hash
  xi normalize <file | -e 'expr'>         Canonicalize → JSON
  xi diff <a.xi-src> <b.xi-src>           Structural diff
  xi patch <file.xi-src> <patch.json>     Apply patch
  xi check <file | -e 'expr'>             Type-check → JSON
  xi schema                               Print Xi-IR JSON schema
  xi run <file | -e 'expr'>               Human-readable output
  xi repl                                 Interactive REPL
  xi serve [--port N]                     HTTP API server
  xi dataset --generate N [--out dir]     Training dataset
  xi fuzz [--rounds N]                    Roundtrip fuzz testing
"""
import sys, os, json, time, hashlib, base64, traceback
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

EXIT_OK, EXIT_INPUT, EXIT_RUNTIME, EXIT_TYPE, EXIT_IO, EXIT_INTERNAL = 0, 1, 2, 3, 4, 5

def json_out(data, code=0):
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    sys.exit(code)

def json_error(msg, code, details=None):
    obj = {"ok": False, "error": msg, "exit_code": code}
    if details: obj["details"] = details
    json_out(obj, code)

def read_source(path):
    if not os.path.exists(path): json_error(f"File not found: {path}", EXIT_IO)
    with open(path) as f: return f.read()

def read_binary(path):
    if not os.path.exists(path): json_error(f"File not found: {path}", EXIT_IO)
    with open(path, 'rb') as f: return f.read()

def compile_to_node(source, entry="main"):
    from xi_compiler import Compiler, ParseError, LexError
    try:
        c = Compiler()
        defs = c.compile_program(source)
        if entry not in defs: json_error(f"No '{entry}'. Available: {list(defs.keys())}", EXIT_INPUT)
        return defs[entry]
    except (ParseError, LexError) as e: json_error(str(e), EXIT_INPUT)
    except Exception as e: json_error(str(e), EXIT_INPUT)

def parse_expr_or_file(args):
    if not args: return None, None
    if args[0] == "-e": return f"def main = {' '.join(args[1:])}", "main"
    return read_source(args[0]), "main"

# ── Commands ──

def cmd_encode(args):
    use_json = "--json" in args
    args = [a for a in args if a != "--json"]
    src, entry = parse_expr_or_file(args)
    if not src: json_error("Usage: xi encode [--json] <file | -e 'expr'>", EXIT_INPUT)
    node = compile_to_node(src, entry)
    if use_json:
        from xi_json import to_json
        json_out({"ok": True, "format": "xi-ir-v1", **to_json(node)})
    else:
        from xi import serialize
        b = serialize(node)
        json_out({"ok": True, "format": "xi-binary", "size_bytes": len(b),
                  "base64": base64.b64encode(b).decode(), "hash": hashlib.sha256(b).hexdigest()})

def cmd_decode(args):
    if not args: json_error("Usage: xi decode <file.xi>", EXIT_INPUT)
    from xi_deserialize import deserialize
    from xi_json import to_json
    try:
        node = deserialize(read_binary(args[0]))
        json_out({"ok": True, **to_json(node)})
    except Exception as e: json_error(f"Decode failed: {e}", EXIT_INPUT)

def cmd_eval(args):
    gas, timeout, pure, caps = 100000, 10.0, False, []
    filtered = []
    i = 0
    while i < len(args):
        if args[i] == "--gas": gas = int(args[i+1]); i += 2
        elif args[i] == "--timeout": timeout = float(args[i+1]); i += 2
        elif args[i] == "--pure": pure = True; i += 1
        elif args[i] == "--cap": caps.append(args[i+1]); i += 2
        else: filtered.append(args[i]); i += 1
    src, entry = parse_expr_or_file(filtered)
    if not src: json_error("Usage: xi eval <file | -e 'expr'> [--gas N] [--pure]", EXIT_INPUT)
    from xi_sandbox import SandboxedInterpreter, SandboxConfig
    node = compile_to_node(src, entry)
    config = SandboxConfig(gas=gas, timeout_seconds=timeout, pure_only=pure, capabilities=caps)
    result, stats = SandboxedInterpreter(config).eval_safe(node)
    json_out({"ok": stats["exit_code"] == 0, "result": result, "stats": stats,
              "sandbox": config.to_dict()}, stats["exit_code"])

def cmd_hash(args):
    src, entry = parse_expr_or_file(args)
    if not src: json_error("Usage: xi hash <file | -e 'expr'>", EXIT_INPUT)
    from xi_json import hash_node, node_count, max_depth
    node = compile_to_node(src, entry)
    json_out({"ok": True, "hash": hash_node(node), "algorithm": "sha-256",
              "node_count": node_count(node), "max_depth": max_depth(node)})

def cmd_normalize(args):
    src, entry = parse_expr_or_file(args)
    if not src: json_error("Usage: xi normalize <file | -e 'expr'>", EXIT_INPUT)
    from xi_json import canonicalize, to_json, hash_node
    from xi_optimizer import optimize
    node = compile_to_node(src, entry)
    opt, stats = optimize(node)
    canon = canonicalize(opt)
    json_out({"ok": True, "canonical": to_json(canon), "hash": hash_node(canon), "optimization": stats})

def cmd_diff(args):
    if len(args) < 2: json_error("Usage: xi diff <a.xi-src> <b.xi-src>", EXIT_INPUT)
    from xi_json import diff, diff_stats, hash_node
    na = compile_to_node(read_source(args[0]))
    nb = compile_to_node(read_source(args[1]))
    ops = diff(na, nb)
    json_out({"ok": True, "old_hash": hash_node(na), "new_hash": hash_node(nb),
              "operations": ops, "stats": diff_stats(ops), "identical": len(ops) == 0})

def cmd_patch(args):
    if len(args) < 2: json_error("Usage: xi patch <file.xi-src> <patch.json>", EXIT_INPUT)
    from xi_json import patch as apply_patch, to_json, hash_node
    node = compile_to_node(read_source(args[0]))
    pdata = json.loads(read_source(args[1]))
    ops = pdata.get("operations", pdata)
    if isinstance(ops, dict): ops = [ops]
    patched = apply_patch(node, ops)
    json_out({"ok": True, "original_hash": hash_node(node), "patched_hash": hash_node(patched),
              "patched": to_json(patched), "operations_applied": len(ops)})

def cmd_check(args):
    src, entry = parse_expr_or_file(args)
    if not src: json_error("Usage: xi check <file | -e 'expr'>", EXIT_INPUT)
    from xi_compiler import Compiler
    from xi_typecheck import TypeChecker, TypeErr, type_to_str
    try:
        c = Compiler(); defs = c.compile_program(src); tc = TypeChecker()
        types = {}
        for name, node in defs.items():
            try:
                ty = tc.infer_type(node)
                types[name] = type_to_str(ty) if ty else "unknown"
            except (TypeErr, Exception): types[name] = "unknown"
        json_out({"ok": True, "types": types})
    except Exception as e: json_error(str(e), EXIT_TYPE)

def cmd_schema(args):
    from xi_json import XI_IR_SCHEMA
    json_out(XI_IR_SCHEMA)

def cmd_serve(args):
    port = 8420
    for i, a in enumerate(args):
        if a == "--port" and i+1 < len(args): port = int(args[i+1])
    from xi_server import create_app
    app = create_app()
    print(f"Ξ Xi API on http://0.0.0.0:{port}", file=sys.stderr)
    app.run(host="0.0.0.0", port=port)

def cmd_dataset(args):
    n, out = 100, "dataset"
    for i, a in enumerate(args):
        if a == "--generate" and i+1 < len(args): n = int(args[i+1])
        elif a == "--out" and i+1 < len(args): out = args[i+1]
    from xi_dataset import generate_dataset
    generate_dataset(n, out)

def cmd_fuzz(args):
    rounds = 1000
    for i, a in enumerate(args):
        if a == "--rounds" and i+1 < len(args): rounds = int(args[i+1])
    from xi_fuzz import run_fuzz
    run_fuzz(rounds)

def cmd_run(args):
    src, entry = parse_expr_or_file(args)
    if not src:
        print("Usage: xi run <file | -e 'expr'>", file=sys.stderr); sys.exit(1)
    from xi_compiler import Compiler
    from xi_match import MatchInterpreter, Constructor, nat_to_int
    try:
        result = Compiler().run_program(src, entry)
        if isinstance(result, Constructor):
            try: print(nat_to_int(MatchInterpreter(), result))
            except: print(result)
        else: print(result)
    except Exception as e: print(f"Error: {e}", file=sys.stderr); sys.exit(1)

def cmd_repl(args):
    from xi_repl import XiREPL; XiREPL().start()

def cmd_test(args):
    import subprocess
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
                       cwd=os.path.dirname(os.path.abspath(__file__)))
    sys.exit(r.returncode)

def cmd_demo(args):
    from xi_compiler import Compiler
    c = Compiler(); passed = failed = 0
    for expr, exp in [("2+3",5),("3*4",12),("10-3",7),("(λx. x*x) 7",49),("(λx. x+x) 21",42)]:
        try:
            r = c.run_program(f"def main = {expr}", "main")
            if r == exp: passed += 1
            else: print(f"FAIL: {expr}→{r} expected {exp}"); failed += 1
        except Exception as e: print(f"ERROR: {expr}→{e}"); failed += 1
    print(f"{passed} passed, {failed} failed"); sys.exit(0 if failed == 0 else 1)

COMMANDS = {k.replace("cmd_",""): v for k, v in locals().items() if k.startswith("cmd_")}

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h","--help","help"):
        print(__doc__); sys.exit(0)
    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        json_error(f"Unknown: {cmd}. Available: {', '.join(sorted(COMMANDS))}", EXIT_INPUT)
    try: COMMANDS[cmd](sys.argv[2:])
    except SystemExit: raise
    except Exception as e: json_error(f"Internal: {e}", EXIT_INTERNAL, {"traceback": traceback.format_exc()})

if __name__ == "__main__": main()
