#!/usr/bin/env python3
"""
Ξ (Xi) Interactive REPL v0.2
Copyright (c) 2026 Alex P. Slaby — MIT License

Full-featured REPL with surface syntax, persistent definitions,
multi-line input, pattern matching, and recursion.

Usage:
  python xi_repl.py
"""

import sys, os, readline
sys.path.insert(0, os.path.dirname(__file__))

from xi import Node, Tag, PrimOp, Effect, B, Interpreter, render_tree, serialize, hexdump, XiError
from xi_compiler import Compiler, Parser, tokenize, ParseError, LexError, TK, Scope, KNOWN_CONSTRUCTORS, BUILTINS, load_import
from xi_match import MatchInterpreter, Constructor, nat_to_int
from xi_typecheck import TypeChecker, TypeErr, type_to_str, resolve_type, Context
from xi_optimizer import optimize

BANNER = """
╔═══════════════════════════════════════════════════════════╗
║  Ξ (Xi) REPL v0.2 — Surface Syntax                       ║
║  Copyright (c) 2026 Alex P. Slaby — MIT License           ║
╠═══════════════════════════════════════════════════════════╣
║  Type expressions, define functions, use pattern matching. ║
║  Commands:  :help  :tree  :hex  :type  :defs  :quit       ║
╚═══════════════════════════════════════════════════════════╝
"""

HELP = """
  Expressions:
    42                                Integer
    "hello"                           String
    2 + 3 * 4                         Arithmetic (with precedence)
    λx. x + x                         Lambda (also: \\x. or fun x.)
    (λx. x * x) 7                     Application → 49
    let x = 5 in x + x                Let binding → 10
    if 3 < 5 then "yes" else "no"     If/else
    match Succ Zero { Zero → 0 | Succ n → n }   Pattern match

  Definitions (persistent):
    def double = λx. x + x            Define a function
    double 21                          Use it → 42
    def fact = fix self. λn. match n { Zero → Succ Zero | Succ k → ... }

  Commands:
    :help             This help
    :defs             List all definitions
    :tree <expr>      Show graph structure
    :hex <expr>       Show binary encoding
    :type <expr>      Show inferred type
    :hash <expr>      Content hash (SHA-256)
    :opt <expr>       Show optimized graph + stats
    :reset            Clear all definitions
    :quit / :q        Exit

  Multi-line: end a line with \\ to continue on next line.
"""


class Repl:
    def __init__(self):
        self.interp = MatchInterpreter()
        self.tc = TypeChecker()
        self.definitions = {}  # name → Node (persistent across inputs)
        self.constructors = dict(KNOWN_CONSTRUCTORS)  # includes user types
        self.imported = set()
        self.history = []

    def _make_parser(self, tokens):
        """Create a parser pre-loaded with current definitions and constructors."""
        p = Parser(tokens)
        p.definitions = dict(self.definitions)
        p.constructors = dict(self.constructors)
        p.imported = set(self.imported)
        return p

    def compile_expr(self, source):
        """Compile expression with access to all definitions."""
        tokens = tokenize(source)
        parser = self._make_parser(tokens)
        return parser.parse_single()

    def display_result(self, result):
        if result is None:
            return "()"
        if isinstance(result, (Constructor, Node)):
            try:
                return str(nat_to_int(self.interp, result))
            except Exception:
                pass
            if isinstance(result, Constructor):
                # Try to display constructor name
                for name, (idx, ar) in KNOWN_CONSTRUCTORS.items():
                    if idx == result.tag and ar == len(result.args):
                        if result.args:
                            args = ' '.join(self.display_result(a) for a in result.args)
                            return f"{name} {args}"
                        return name
        if isinstance(result, bool):
            return "True" if result else "False"
        return str(result)

    def handle_def(self, source):
        """Handle a def declaration."""
        tokens = tokenize(source)
        parser = self._make_parser(tokens)
        parser.expect(TK.DEF)
        name = parser.expect(TK.IDENT).value
        # Optional function params
        params = []
        while parser.at(TK.IDENT) and parser.peek().value not in BUILTINS:
            params.append(parser.advance().value)
        if parser.match_tok(TK.COLON):
            _ty = parser.parse_expr()
        parser.expect(TK.EQ)
        saved = parser.scope
        for p in params:
            parser.scope = parser.scope.bind(p)
        body = parser.parse_expr()
        parser.scope = saved
        for p in reversed(params):
            body = B.lam(B.universe(0), body)
        self.definitions[name] = body
        # Try to infer type
        try:
            ty = resolve_type(self.tc.infer(Context(), body))
            print(f"  {name} : {type_to_str(ty)} defined")
        except Exception:
            print(f"  {name} defined")

    def handle_import(self, source):
        """Handle import declaration."""
        tokens = tokenize(source)
        parser = self._make_parser(tokens)
        parser.expect(TK.IMPORT)
        name = parser.expect(TK.CONSTR).value
        if name in self.imported:
            print(f"  {name} already imported")
            return
        defs = load_import(name)
        for k, v in defs.items():
            self.definitions[k] = v
        self.imported.add(name)
        print(f"  Imported {name} ({len(defs)} definitions)")

    def handle_type(self, source):
        """Handle type declaration."""
        tokens = tokenize(source)
        parser = self._make_parser(tokens)
        parser._parse_type_decl()
        # Copy new constructors back
        for k, v in parser.constructors.items():
            if k not in self.constructors:
                self.constructors[k] = v
                print(f"  Constructor {k} registered")

    def cmd_eval(self, source):
        graph = self.compile_expr(source)
        result = self.interp.run(graph)
        print(f"  {self.display_result(result)}")

    def cmd_tree(self, source):
        graph = self.compile_expr(source)
        for line in render_tree(graph).split('\n'):
            print(f"  {line}")

    def cmd_hex(self, source):
        graph = self.compile_expr(source)
        binary = serialize(graph)
        print(f"  {len(binary)} bytes:")
        print(hexdump(binary))

    def cmd_type(self, source):
        graph = self.compile_expr(source)
        ty = resolve_type(self.tc.infer(Context(), graph))
        print(f"  {type_to_str(ty)}")

    def cmd_hash(self, source):
        graph = self.compile_expr(source)
        print(f"  {graph.content_hash().hex()}")

    def cmd_opt(self, source):
        graph = self.compile_expr(source)
        before = len(serialize(graph))
        opt, stats = optimize(graph)
        after = len(serialize(opt))
        result = self.interp.run(opt)
        print(f"  Result: {self.display_result(result)}")
        print(f"  Size:   {before} → {after} bytes ({100*(before-after)//max(before,1)}% reduction)")
        print(f"  Stats:  {stats}")

    def cmd_defs(self):
        if not self.definitions:
            print("  No definitions.")
            return
        for name, node in self.definitions.items():
            try:
                ty = resolve_type(self.tc.infer(Context(), node))
                print(f"  {name} : {type_to_str(ty)}")
            except Exception:
                print(f"  {name}")

    def read_input(self):
        """Read input with multi-line continuation (trailing \\)."""
        try:
            line = input("Ξ> ").rstrip()
        except (EOFError, KeyboardInterrupt):
            return None

        lines = [line]
        while line.endswith('\\'):
            lines[-1] = lines[-1][:-1]  # strip trailing backslash
            try:
                line = input(".. ").rstrip()
            except (EOFError, KeyboardInterrupt):
                return None
            lines.append(line)

        # Also continue if braces aren't balanced
        full = '\n'.join(lines)
        while full.count('{') > full.count('}'):
            try:
                line = input(".. ").rstrip()
            except (EOFError, KeyboardInterrupt):
                return None
            full += '\n' + line

        return full

    def run(self):
        print(BANNER)

        # Setup readline history
        histfile = os.path.expanduser("~/.xi_history")
        try:
            readline.read_history_file(histfile)
        except FileNotFoundError:
            pass

        while True:
            source = self.read_input()
            if source is None:
                print("\n  Bye!")
                break

            source = source.strip()
            if not source:
                continue

            self.history.append(source)

            try:
                # Commands
                if source in (":quit", ":q", ":exit"):
                    print("  Bye!")
                    break
                elif source == ":help":
                    print(HELP)
                elif source == ":defs":
                    self.cmd_defs()
                elif source == ":reset":
                    self.definitions.clear()
                    self.constructors = dict(KNOWN_CONSTRUCTORS)
                    self.imported.clear()
                    print("  Definitions cleared.")
                elif source.startswith(":tree "):
                    self.cmd_tree(source[6:])
                elif source.startswith(":hex "):
                    self.cmd_hex(source[5:])
                elif source.startswith(":type "):
                    self.cmd_type(source[6:])
                elif source.startswith(":hash "):
                    self.cmd_hash(source[6:])
                elif source.startswith(":opt "):
                    self.cmd_opt(source[5:])
                # Definitions / imports / type declarations
                elif source.startswith("def "):
                    self.handle_def(source)
                elif source.startswith("import "):
                    self.handle_import(source)
                elif source.startswith("type "):
                    self.handle_type(source)
                # Expression
                else:
                    self.cmd_eval(source)

            except (ParseError, LexError) as e:
                print(f"  Parse error: {e}")
            except TypeErr as e:
                print(f"  Type error: {e}")
            except XiError as e:
                print(f"  Runtime error: {e}")
            except RecursionError:
                print(f"  Error: maximum recursion depth exceeded")
            except Exception as e:
                print(f"  Error: {type(e).__name__}: {e}")

        # Save history
        try:
            readline.write_history_file(histfile)
        except Exception:
            pass


def run_demo():
    """Non-interactive REPL demo."""
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║  Ξ (Xi) REPL Demo (non-interactive)                      ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")

    repl = Repl()
    passed = 0
    failed = 0

    def check(prompt, source, expected_contains=None, is_def=False):
        nonlocal passed, failed
        print(f"  Ξ> {source}")
        try:
            if is_def:
                repl.handle_def(source)
                passed += 1
            elif source.startswith(":"):
                cmd = source.split()[0]
                rest = source[len(cmd):].strip()
                if cmd == ":tree": repl.cmd_tree(rest)
                elif cmd == ":type": repl.cmd_type(rest)
                elif cmd == ":opt": repl.cmd_opt(rest)
                elif cmd == ":defs": repl.cmd_defs()
                passed += 1
            else:
                graph = repl.compile_expr(source)
                result = repl.interp.run(graph)
                displayed = repl.display_result(result)
                print(f"  {displayed}")
                if expected_contains and str(expected_contains) not in displayed:
                    print(f"    ✗ expected to contain: {expected_contains}")
                    failed += 1
                else:
                    passed += 1
        except Exception as e:
            print(f"  Error: {e}")
            failed += 1
        print()

    print("  ── Basics ──\n")
    check("int",    "42",             "42")
    check("arith",  "2 + 3 * 4",     "14")
    check("string", '"hello" ++ " world"', "hello world")

    print("  ── Lambda ──\n")
    check("id",     "(λx. x) 99",    "99")
    check("square", "(λx. x * x) 7", "49")

    print("  ── Let & if ──\n")
    check("let",    "let x = 5 in x + x", "10")
    check("if",     "if 3 < 5 then 1 else 0", "1")

    print("  ── Persistent definitions ──\n")
    check("def",    "def double = λx. x + x", is_def=True)
    check("use",    "double 21",      "42")
    check("def2",   "def square = λx. x * x", is_def=True)
    check("chain",  "square (double 3)", "36")

    print("  ── Pattern matching ──\n")
    check("nat",    "match Succ (Succ Zero) { Zero → 0 | Succ k → 1 }", "1")
    check("opt",    "match Some 42 { None → 0 | Some x → x }", "42")

    print("  ── Recursion ──\n")
    check("def3",   "def add = fix self. λn. λm. match n { Zero → m | Succ k → Succ (self k m) }", is_def=True)
    check("add",    "add (Succ (Succ Zero)) (Succ (Succ (Succ Zero)))", "5")

    print("  ── Commands ──\n")
    check("type",   ":type 42")
    check("defs",   ":defs")

    print(f"  ═══════════════════════════════════")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"  ═══════════════════════════════════\n")
    return failed == 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        ok = run_demo()
        sys.exit(0 if ok else 1)
    else:
        repl = Repl()
        repl.run()
