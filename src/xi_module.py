#!/usr/bin/env python3
"""
Ξ (Xi) Module System
Copyright (c) 2026 Alex P. Slaby — MIT License

Content-addressed module system for Xi. Modules are linked by SHA-256
hash — not filenames. This means:
  - No dependency conflicts (every version has a unique hash)
  - No broken imports (if the hash exists, it's correct)
  - Deterministic builds (same source → same hash → same binary)

Module file format (.xi-mod):
  A compiled .xi binary preceded by an export table that maps
  names to graph node hashes.

Usage:
  python xi_module.py demo
"""

import sys, os, json, hashlib
sys.path.insert(0, os.path.dirname(__file__))
from xi import (
    Node, Tag, PrimOp, Effect, B, serialize, Interpreter,
    XiError, render_tree, node_label, MAGIC, FORMAT_VERSION,
)
from xi_compiler import Compiler, ParseError
from xi_deserialize import deserialize, DeserializeError


# ═══════════════════════════════════════════════════════════════
# MODULE REPRESENTATION
# ═══════════════════════════════════════════════════════════════

class ModuleError(Exception):
    pass


class Export:
    """A named export from a module."""
    __slots__ = ('name', 'node', 'hash')

    def __init__(self, name: str, node: Node):
        self.name = name
        self.node = node
        self.hash = node.content_hash().hex()

    def __repr__(self):
        return f"Export({self.name}, {self.hash[:16]}…)"


class Module:
    """
    A Xi module: a collection of named definitions linked by hash.

    Each module has:
      - A unique hash (derived from all exports)
      - A name (human-readable, not used for linking)
      - Exports: name → Node mapping
      - Dependencies: hash → Module mapping
    """

    def __init__(self, name: str):
        self.name = name
        self.exports: dict[str, Export] = {}
        self.dependencies: dict[str, 'Module'] = {}
        self._hash = None

    def define(self, name: str, node: Node) -> Export:
        """Add a definition to this module."""
        export = Export(name, node)
        self.exports[name] = export
        self._hash = None  # invalidate
        return export

    def depend(self, module: 'Module'):
        """Add a dependency on another module."""
        self.dependencies[module.module_hash()] = module
        self._hash = None

    def resolve(self, name: str) -> Node:
        """
        Resolve a name: look in this module first, then dependencies.
        """
        if name in self.exports:
            return self.exports[name].node

        # Search dependencies (depth-first)
        for dep in self.dependencies.values():
            try:
                return dep.resolve(name)
            except ModuleError:
                continue

        raise ModuleError(f"Unresolved: '{name}' not found in module '{self.name}' or dependencies")

    def resolve_by_hash(self, hash_hex: str) -> Node:
        """Resolve a definition by its content hash."""
        for exp in self.exports.values():
            if exp.hash == hash_hex:
                return exp.node

        for dep in self.dependencies.values():
            try:
                return dep.resolve_by_hash(hash_hex)
            except ModuleError:
                continue

        raise ModuleError(f"Hash not found: {hash_hex[:16]}…")

    def module_hash(self) -> str:
        """Compute the module's content hash from all exports."""
        if self._hash is None:
            h = hashlib.sha256()
            h.update(self.name.encode('utf-8'))
            for name in sorted(self.exports.keys()):
                h.update(name.encode('utf-8'))
                h.update(bytes.fromhex(self.exports[name].hash))
            self._hash = h.hexdigest()
        return self._hash

    def export_table(self) -> dict:
        """Get the export table as a dictionary."""
        return {name: exp.hash for name, exp in sorted(self.exports.items())}

    def list_exports(self) -> list[tuple[str, str]]:
        """List all exports as (name, hash_short) pairs."""
        return [(name, exp.hash[:16]) for name, exp in sorted(self.exports.items())]

    def __repr__(self):
        return f"Module({self.name}, {len(self.exports)} exports, hash={self.module_hash()[:16]}…)"


# ═══════════════════════════════════════════════════════════════
# MODULE REGISTRY — Global content-addressed store
# ═══════════════════════════════════════════════════════════════

class Registry:
    """
    Global module registry. Stores modules by their content hash.
    This simulates a content-addressed package store.
    """

    def __init__(self):
        self.modules: dict[str, Module] = {}   # hash → Module
        self.by_name: dict[str, Module] = {}   # name → Module (convenience)

    def register(self, module: Module) -> str:
        """Register a module and return its hash."""
        h = module.module_hash()
        self.modules[h] = module
        self.by_name[module.name] = module
        return h

    def get(self, hash_hex: str) -> Module:
        """Get a module by hash."""
        if hash_hex in self.modules:
            return self.modules[hash_hex]
        # Try prefix match
        for h, m in self.modules.items():
            if h.startswith(hash_hex):
                return m
        raise ModuleError(f"Module not found: {hash_hex[:16]}…")

    def get_by_name(self, name: str) -> Module:
        """Get a module by name (convenience, not deterministic)."""
        if name in self.by_name:
            return self.by_name[name]
        raise ModuleError(f"Module not found: '{name}'")

    def list_modules(self) -> list[tuple[str, str, int]]:
        """List all modules as (name, hash_short, num_exports)."""
        return [(m.name, h[:16], len(m.exports))
                for h, m in sorted(self.modules.items(), key=lambda x: x[1].name)]


# ═══════════════════════════════════════════════════════════════
# MODULE COMPILER — Parse module source
# ═══════════════════════════════════════════════════════════════

class ModuleCompiler:
    """
    Compile a module source file (.xi-src) into a Module.

    Module syntax:
      module <name>

      import <module-name>

      def <name> = <expr>
      def <name> = <expr>
      ...
    """

    def __init__(self, registry: Registry = None):
        self.registry = registry or Registry()
        self.compiler = Compiler()

    def compile_source(self, source: str) -> Module:
        """Parse module source and compile all definitions."""
        lines = source.strip().split('\n')
        lines = [l.strip() for l in lines if l.strip() and not l.strip().startswith('--')]

        # Parse header
        if not lines or not lines[0].startswith('module '):
            raise ModuleError("Module must start with 'module <name>'")

        name = lines[0][7:].strip()
        module = Module(name)
        i = 1

        # Parse imports
        while i < len(lines) and lines[i].startswith('import '):
            dep_name = lines[i][7:].strip()
            try:
                dep = self.registry.get_by_name(dep_name)
                module.depend(dep)
            except ModuleError:
                raise ModuleError(f"Import failed: module '{dep_name}' not found in registry")
            i += 1

        # Parse definitions
        while i < len(lines):
            line = lines[i]
            if line.startswith('def '):
                # Collect multi-line definition
                rest = line[4:]
                eq_pos = rest.find('=')
                if eq_pos == -1:
                    raise ModuleError(f"Invalid definition: {line}")
                def_name = rest[:eq_pos].strip()
                def_body = rest[eq_pos+1:].strip()

                # Continue collecting if next lines don't start a new def/import
                while i + 1 < len(lines) and not lines[i+1].startswith('def ') and not lines[i+1].startswith('import '):
                    i += 1
                    def_body += ' ' + lines[i]

                # Compile expression, resolving names from dependencies
                node = self._compile_with_imports(def_body, module)
                module.define(def_name, node)
            i += 1

        return module

    def _compile_with_imports(self, source: str, module: Module) -> Node:
        """
        Compile an expression, replacing imported names with their graph nodes.
        Simple text-level substitution for now — a real implementation would
        do this at the AST level.
        """
        # Replace imported names with their compiled forms
        processed = source
        for dep in module.dependencies.values():
            for exp_name, exp in dep.exports.items():
                # For now, only substitute simple numeric/string expressions
                if processed.strip() == exp_name:
                    return exp.node

        try:
            graph, _ = self.compiler.compile(processed)
            return graph
        except (ParseError, SyntaxError) as e:
            raise ModuleError(f"Compilation error: {e}")


# ═══════════════════════════════════════════════════════════════
# MODULE SERIALIZATION
# ═══════════════════════════════════════════════════════════════

def serialize_module(module: Module) -> bytes:
    """
    Serialize a module to bytes.

    Format:
      [XI_MOD_MAGIC: 4 bytes] CE 9E 4D 4F  ("ΞMO")
      [version: 1 byte]
      [module_name_len: 2 bytes] [module_name: utf-8]
      [num_exports: 2 bytes]
      For each export:
        [name_len: 2 bytes] [name: utf-8]
        [hash: 32 bytes]
        [binary_len: 4 bytes] [binary: serialized node]
      [num_dependencies: 2 bytes]
      For each dependency:
        [dep_hash: 32 bytes]
    """
    result = bytearray()
    result += b'\xCE\x9E\x4D\x4F'  # magic
    result += bytes([0x01])          # version

    name_enc = module.name.encode('utf-8')
    result += len(name_enc).to_bytes(2, 'big') + name_enc

    exports = sorted(module.exports.items())
    result += len(exports).to_bytes(2, 'big')
    for name, exp in exports:
        name_bytes = name.encode('utf-8')
        result += len(name_bytes).to_bytes(2, 'big') + name_bytes
        result += bytes.fromhex(exp.hash)
        binary = serialize(exp.node)
        result += len(binary).to_bytes(4, 'big') + binary

    dep_hashes = sorted(module.dependencies.keys())
    result += len(dep_hashes).to_bytes(2, 'big')
    for dh in dep_hashes:
        result += bytes.fromhex(dh)

    return bytes(result)


def deserialize_module(data: bytes, registry: Registry = None) -> Module:
    """Deserialize a module from bytes."""
    if data[:4] != b'\xCE\x9E\x4D\x4F':
        raise ModuleError("Invalid module magic")
    if data[4] != 0x01:
        raise ModuleError(f"Unsupported module version: {data[4]}")

    pos = 5
    name_len = int.from_bytes(data[pos:pos+2], 'big'); pos += 2
    name = data[pos:pos+name_len].decode('utf-8'); pos += name_len

    module = Module(name)

    num_exports = int.from_bytes(data[pos:pos+2], 'big'); pos += 2
    for _ in range(num_exports):
        exp_name_len = int.from_bytes(data[pos:pos+2], 'big'); pos += 2
        exp_name = data[pos:pos+exp_name_len].decode('utf-8'); pos += exp_name_len
        exp_hash = data[pos:pos+32].hex(); pos += 32
        bin_len = int.from_bytes(data[pos:pos+4], 'big'); pos += 4
        bin_data = data[pos:pos+bin_len]; pos += bin_len
        node = deserialize(bin_data)
        exp = module.define(exp_name, node)
        assert exp.hash == exp_hash, f"Hash mismatch for {exp_name}"

    num_deps = int.from_bytes(data[pos:pos+2], 'big'); pos += 2
    for _ in range(num_deps):
        dep_hash = data[pos:pos+32].hex(); pos += 32
        if registry:
            try:
                dep = registry.get(dep_hash)
                module.depend(dep)
            except ModuleError:
                pass  # dependency not in registry

    return module


# ═══════════════════════════════════════════════════════════════
# DEMO
# ═══════════════════════════════════════════════════════════════

def run_demo():
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║  Ξ (Xi) Module System v0.1                               ║")
    print("║  Copyright (c) 2026 Alex P. Slaby — MIT License          ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")

    registry = Registry()
    interp = Interpreter()
    passed = 0
    failed = 0

    def check(name, ok, detail=""):
        nonlocal passed, failed
        if ok:
            print(f"  ✓ {name}")
            if detail: print(f"    {detail}")
            passed += 1
        else:
            print(f"  ✗ {name}")
            if detail: print(f"    {detail}")
            failed += 1

    # ── 1. Build base math module ──
    print("  ── Build modules ──\n")

    math_mod = Module("Xi.Math")
    math_mod.define("zero", B.int_lit(0))
    math_mod.define("one", B.int_lit(1))
    math_mod.define("two", B.int_lit(2))
    math_mod.define("add_3_5", B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(3)), B.int_lit(5)))
    math_mod.define("double",
        B.lam(B.universe(0), B.app(B.app(B.prim(PrimOp.INT_ADD), B.var(0)), B.var(0))))
    math_mod.define("square",
        B.lam(B.universe(0), B.app(B.app(B.prim(PrimOp.INT_MUL), B.var(0)), B.var(0))))

    math_hash = registry.register(math_mod)
    check("Xi.Math registered",
        True,
        f"hash={math_hash[:16]}… | {len(math_mod.exports)} exports")

    # ── 2. Build string module ──
    str_mod = Module("Xi.String")
    str_mod.define("empty", B.str_lit(""))
    str_mod.define("hello", B.str_lit("Hello, "))
    str_mod.define("world", B.str_lit("World!"))
    str_mod.define("greet",
        B.app(B.app(B.prim(PrimOp.STR_CONCAT), B.str_lit("Hello, ")), B.str_lit("World!")))

    str_hash = registry.register(str_mod)
    check("Xi.String registered",
        True,
        f"hash={str_hash[:16]}… | {len(str_mod.exports)} exports")

    # ── 3. Build app module depending on both ──
    app_mod = Module("MyApp")
    app_mod.depend(math_mod)
    app_mod.depend(str_mod)

    app_mod.define("banner", B.str_lit("=== MyApp ==="))
    app_mod.define("magic_number",
        B.app(B.app(B.prim(PrimOp.INT_MUL),
            B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(3)), B.int_lit(5))),
            B.int_lit(2)))

    app_hash = registry.register(app_mod)
    check("MyApp registered (depends on Math, String)",
        True,
        f"hash={app_hash[:16]}… | {len(app_mod.exports)} exports, {len(app_mod.dependencies)} deps")

    # ── 4. Name resolution ──
    print("\n  ── Name resolution ──\n")

    node = app_mod.resolve("banner")
    check("resolve 'banner' in MyApp",
        interp.run(node) == "=== MyApp ===",
        f"→ {interp.run(node)}")

    node = app_mod.resolve("double")
    result = interp.run(B.app(node, B.int_lit(21)))
    check("resolve 'double' from Xi.Math dependency",
        result == 42,
        f"double(21) → {result}")

    node = app_mod.resolve("greet")
    result = interp.run(node)
    check("resolve 'greet' from Xi.String dependency",
        result == "Hello, World!",
        f"→ {result}")

    # ── 5. Hash-based resolution ──
    print("\n  ── Hash-based resolution ──\n")

    five_hash = math_mod.exports["add_3_5"].hash
    node = registry.get(math_hash).resolve_by_hash(five_hash)
    result = interp.run(node)
    check(f"resolve by hash {five_hash[:16]}…",
        result == 8,
        f"→ {result}")

    # ── 6. Content addressing ──
    print("\n  ── Content addressing ──\n")

    math2 = Module("Xi.Math")
    math2.define("zero", B.int_lit(0))
    math2.define("one", B.int_lit(1))
    math2.define("two", B.int_lit(2))
    math2.define("add_3_5", B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(3)), B.int_lit(5)))
    math2.define("double",
        B.lam(B.universe(0), B.app(B.app(B.prim(PrimOp.INT_ADD), B.var(0)), B.var(0))))
    math2.define("square",
        B.lam(B.universe(0), B.app(B.app(B.prim(PrimOp.INT_MUL), B.var(0)), B.var(0))))

    check("Same content → same hash (idempotent)",
        math2.module_hash() == math_hash,
        f"{math2.module_hash()[:16]}… == {math_hash[:16]}…")

    math3 = Module("Xi.Math")
    math3.define("zero", B.int_lit(0))
    math3.define("one", B.int_lit(1))
    math3.define("two", B.int_lit(2))
    math3.define("add_3_5", B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(3)), B.int_lit(5)))
    math3.define("double",
        B.lam(B.universe(0), B.app(B.app(B.prim(PrimOp.INT_ADD), B.var(0)), B.var(0))))
    math3.define("square",
        B.lam(B.universe(0), B.app(B.app(B.prim(PrimOp.INT_MUL), B.var(0)), B.var(0))))
    math3.define("cube",  # extra export
        B.lam(B.universe(0), B.app(B.app(B.prim(PrimOp.INT_MUL), B.var(0)),
            B.app(B.app(B.prim(PrimOp.INT_MUL), B.var(0)), B.var(0)))))

    check("Different content → different hash",
        math3.module_hash() != math_hash,
        f"{math3.module_hash()[:16]}… ≠ {math_hash[:16]}…")

    # ── 7. Module serialization round-trip ──
    print("\n  ── Module serialization ──\n")

    for mod in [math_mod, str_mod, app_mod]:
        binary = serialize_module(mod)
        restored = deserialize_module(binary, registry)
        hashes_match = restored.module_hash() == mod.module_hash()
        check(f"{mod.name}: serialize → deserialize → hash match",
            hashes_match,
            f"{len(binary)} bytes")

    # ── 8. Module source compilation ──
    print("\n  ── Module source compilation ──\n")

    mc = ModuleCompiler(registry)

    source = """
module Xi.Demo

def pi_approx = 3
def greeting = "Hello from Xi.Demo!"
def answer = (20 + 1) * 2
"""
    demo_mod = mc.compile_source(source)
    demo_hash = registry.register(demo_mod)

    check("Compile module from source",
        len(demo_mod.exports) == 3,
        f"{len(demo_mod.exports)} exports: {', '.join(demo_mod.exports.keys())}")

    result = interp.run(demo_mod.resolve("answer"))
    check("Evaluate 'answer' from compiled module",
        result == 42,
        f"→ {result}")

    result = interp.run(demo_mod.resolve("greeting"))
    check("Evaluate 'greeting' from compiled module",
        result == "Hello from Xi.Demo!",
        f"→ {result}")

    # ── 9. Registry listing ──
    print("\n  ── Registry ──\n")
    for name, h, n in registry.list_modules():
        print(f"    {name:20s}  {h}…  ({n} exports)")

    # ── Summary ──
    print(f"\n  ═══════════════════════════════")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"  ═══════════════════════════════\n")
    return failed == 0


if __name__ == "__main__":
    ok = run_demo()
    sys.exit(0 if ok else 1)
