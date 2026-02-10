#!/usr/bin/env python3
"""
Ξ (Xi) Reference Implementation
Copyright (c) 2026 Alex P. Slaby — MIT License

Usage:
  python xi.py demo              Run built-in demos
  python xi.py info <file.xi>    Show binary file info
  python xi.py help              Show this help
"""

import hashlib
import struct
import sys
import os
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, Any


# ═══════════════════════════════════════════════════════════════
# CORE DEFINITIONS
# ═══════════════════════════════════════════════════════════════

class Tag(IntEnum):
    """The 10 primitive constructs of Xi."""
    LAM  = 0x0   # λ  Abstraction
    APP  = 0x1   # @  Application
    PI   = 0x2   # Π  Dependent product
    SIG  = 0x3   # Σ  Dependent sum
    UNI  = 0x4   # 𝒰  Universe
    FIX  = 0x5   # μ  Fixed point
    IND  = 0x6   # ι  Induction
    EQ   = 0x7   # ≡  Identity
    EFF  = 0x8   # !  Effect
    PRIM = 0x9   # #  Primitive


TAG_SYMBOL = {
    Tag.LAM: "λ", Tag.APP: "@", Tag.PI: "Π", Tag.SIG: "Σ", Tag.UNI: "𝒰",
    Tag.FIX: "μ", Tag.IND: "ι", Tag.EQ: "≡", Tag.EFF: "!", Tag.PRIM: "#",
}


class PrimOp(IntEnum):
    """Primitive operation codes."""
    VAR        = 0x00
    PRINT      = 0x01
    STR_LIT    = 0x02
    INT_LIT    = 0x03
    FLOAT_LIT  = 0x04
    UNIT       = 0x05
    INT_ADD    = 0x10
    INT_SUB    = 0x11
    INT_MUL    = 0x12
    INT_DIV    = 0x13
    INT_MOD    = 0x14
    INT_NEG    = 0x15
    INT_EQ     = 0x20
    INT_LT     = 0x21
    INT_GT     = 0x22
    BOOL_TRUE  = 0x30
    BOOL_FALSE = 0x31
    BOOL_NOT   = 0x32
    BOOL_AND   = 0x33
    BOOL_OR    = 0x34
    STR_CONCAT = 0x50
    STR_LEN    = 0x51


PRIM_NAME = {
    0x00: "var",  0x01: "print",  0x02: "str",  0x03: "int",
    0x04: "float",  0x05: "unit",
    0x10: "add",  0x11: "sub",  0x12: "mul",  0x13: "div",
    0x14: "mod",  0x15: "neg",
    0x20: "eq",   0x21: "lt",   0x22: "gt",
    0x30: "true", 0x31: "false", 0x32: "not", 0x33: "and", 0x34: "or",
    0x50: "str_concat", 0x51: "str_len",
}


class Effect(IntEnum):
    """Effect flags (bitfield)."""
    PURE   = 0x00
    IO     = 0x01
    MUT    = 0x02
    NONDET = 0x04
    EXN    = 0x08
    CONC   = 0x10


EFFECT_NAME = {1: "IO", 2: "Mut", 4: "Nondet", 8: "Exn", 16: "Conc"}

MAGIC = b'\xCE\x9E'
FORMAT_VERSION = 0x01


# ═══════════════════════════════════════════════════════════════
# GRAPH NODE
# ═══════════════════════════════════════════════════════════════

@dataclass
class Node:
    """A node in the Xi program graph."""
    tag: Tag
    children: list = field(default_factory=list)
    prim_op: Optional[PrimOp] = None
    data: Any = None
    effect: int = 0
    universe_level: int = 0

    @property
    def arity(self) -> int:
        return len(self.children)

    def content_hash(self) -> bytes:
        """Compute SHA-256 content hash of this node (recursive)."""
        h = hashlib.sha256()
        h.update(bytes([self.tag << 4 | (self.arity & 0x0F)]))
        for child in self.children:
            h.update(child.content_hash())
        if self.tag == Tag.PRIM and self.prim_op is not None:
            h.update(bytes([self.prim_op]))
            if self.data is not None:
                if isinstance(self.data, str):
                    h.update(self.data.encode('utf-8'))
                elif isinstance(self.data, int):
                    h.update(self.data.to_bytes(8, 'big', signed=True))
                elif isinstance(self.data, float):
                    h.update(struct.pack('>d', self.data))
        if self.tag == Tag.UNI:
            h.update(self.universe_level.to_bytes(4, 'big'))
        if self.tag == Tag.EFF:
            h.update(bytes([self.effect]))
        return h.digest()

    def hash_short(self) -> str:
        return self.content_hash().hex()[:16]


# ═══════════════════════════════════════════════════════════════
# BUILDER — High-level graph construction
# ═══════════════════════════════════════════════════════════════

class B:
    """Fluent builder for Xi graphs."""

    @staticmethod
    def var(index: int) -> Node:
        return Node(Tag.PRIM, prim_op=PrimOp.VAR, data=index)

    @staticmethod
    def lam(type_ann: Node, body: Node) -> Node:
        return Node(Tag.LAM, children=[type_ann, body])

    @staticmethod
    def app(func: Node, arg: Node) -> Node:
        return Node(Tag.APP, children=[func, arg])

    @staticmethod
    def pi(domain: Node, codomain: Node) -> Node:
        return Node(Tag.PI, children=[domain, codomain])

    @staticmethod
    def universe(level: int = 0) -> Node:
        return Node(Tag.UNI, universe_level=level)

    @staticmethod
    def fix(type_ann: Node, body: Node) -> Node:
        return Node(Tag.FIX, children=[type_ann, body])

    @staticmethod
    def effect(expr: Node, eff: int = Effect.IO) -> Node:
        return Node(Tag.EFF, children=[expr], effect=eff)

    @staticmethod
    def int_lit(value: int) -> Node:
        return Node(Tag.PRIM, prim_op=PrimOp.INT_LIT, data=value)

    @staticmethod
    def str_lit(value: str) -> Node:
        return Node(Tag.PRIM, prim_op=PrimOp.STR_LIT, data=value)

    @staticmethod
    def prim(op: PrimOp) -> Node:
        return Node(Tag.PRIM, prim_op=op)

    @staticmethod
    def unit() -> Node:
        return Node(Tag.PRIM, prim_op=PrimOp.UNIT)


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Binary encoding
# ═══════════════════════════════════════════════════════════════

def serialize(root: Node) -> bytes:
    """Serialize a Xi graph to the binary format."""
    # Flatten DAG to ordered node list (children before parents)
    nodes = []
    visited = set()

    def collect(node):
        nid = id(node)
        if nid in visited:
            return
        visited.add(nid)
        for child in node.children:
            collect(child)
        nodes.append(node)

    collect(root)
    index_of = {id(n): i for i, n in enumerate(nodes)}

    # Header
    result = bytearray()
    result += MAGIC
    result += bytes([FORMAT_VERSION])
    result += len(nodes).to_bytes(2, 'big')
    result += index_of[id(root)].to_bytes(2, 'big')

    # Nodes
    for node in nodes:
        # Header byte: [TTTT AAAA]
        result += bytes([(node.tag << 4) | (node.arity & 0x0F)])

        # Edges (child references)
        for child in node.children:
            result += index_of[id(child)].to_bytes(2, 'big')

        # Tag-specific data
        if node.tag == Tag.PRIM and node.prim_op is not None:
            result += bytes([node.prim_op])
            if node.data is not None:
                if isinstance(node.data, str):
                    enc = node.data.encode('utf-8')
                    result += len(enc).to_bytes(2, 'big') + enc
                elif isinstance(node.data, int) and node.prim_op == PrimOp.INT_LIT:
                    result += node.data.to_bytes(8, 'big', signed=True)
                elif isinstance(node.data, float):
                    result += struct.pack('>d', node.data)
                elif isinstance(node.data, int) and node.prim_op == PrimOp.VAR:
                    result += node.data.to_bytes(2, 'big')

        if node.tag == Tag.UNI:
            result += node.universe_level.to_bytes(2, 'big')

        if node.tag == Tag.EFF:
            result += bytes([node.effect])

    return bytes(result)


def hexdump(data: bytes, width: int = 16) -> str:
    """Format binary data as a hex dump string."""
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        hex_part = ' '.join(f'{b:02X}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '·' for b in chunk)
        lines.append(f"  {i:04X}  {hex_part:<{width * 3}}  {ascii_part}")
    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════
# INTERPRETER — Graph reduction engine
# ═══════════════════════════════════════════════════════════════

class XiError(Exception):
    pass


class Interpreter:
    """Minimal graph reduction interpreter for Xi."""

    def __init__(self):
        self.reductions = 0

    def run(self, node: Node) -> Any:
        """Reduce a Xi graph to a value."""
        self.reductions = 0
        return self._eval(node)

    def _eval(self, n: Node) -> Any:
        self.reductions += 1

        if n.tag == Tag.EFF:
            # Unwrap effect annotation, execute inner expression
            return self._eval(n.children[0])

        elif n.tag == Tag.APP:
            func = n.children[0]
            arg = n.children[1]
            val = self._eval(arg)

            # Direct primitive application (unary)
            if func.tag == Tag.PRIM:
                return self._apply_unary(func.prim_op, val)

            # Curried primitive application (binary): @(@(#[op], lhs), rhs)
            if func.tag == Tag.APP and func.children[0].tag == Tag.PRIM:
                lhs = self._eval(func.children[1])
                return self._apply_binary(func.children[0].prim_op, lhs, val)

            # Lambda application (β-reduction)
            if func.tag == Tag.LAM:
                body = func.children[1]
                substituted = self._substitute(body, 0, self._to_node(val))
                return self._eval(substituted)

            raise XiError(f"Cannot apply: {TAG_SYMBOL.get(func.tag, '?')}")

        elif n.tag == Tag.PRIM:
            if n.prim_op == PrimOp.STR_LIT:
                return n.data
            elif n.prim_op == PrimOp.INT_LIT:
                return n.data
            elif n.prim_op == PrimOp.FLOAT_LIT:
                return n.data
            elif n.prim_op == PrimOp.UNIT:
                return None
            elif n.prim_op == PrimOp.BOOL_TRUE:
                return True
            elif n.prim_op == PrimOp.BOOL_FALSE:
                return False
            elif n.prim_op == PrimOp.VAR:
                raise XiError(f"Unbound variable: de Bruijn index {n.data}")
            else:
                return n  # partially applied primitive

        elif n.tag == Tag.LAM:
            return n  # return as closure

        elif n.tag == Tag.FIX:
            # μ-reduction: unfold one step
            body = n.children[1]
            return self._eval(self._substitute(body, 0, n))

        elif n.tag == Tag.UNI:
            return f"𝒰{n.universe_level}"

        elif n.tag == Tag.PI:
            return n  # type — return as-is

        raise XiError(f"Cannot evaluate: {TAG_SYMBOL.get(n.tag, '?')}")

    def _apply_unary(self, op: PrimOp, val: Any) -> Any:
        if op == PrimOp.PRINT:
            print(val)
            return None
        elif op == PrimOp.INT_NEG:
            return -val
        elif op == PrimOp.BOOL_NOT:
            return not val
        elif op == PrimOp.STR_LEN:
            return len(val)
        raise XiError(f"Unknown unary op: {PRIM_NAME.get(op, '?')}")

    def _apply_binary(self, op: PrimOp, a: Any, b: Any) -> Any:
        ops = {
            PrimOp.INT_ADD: lambda x, y: x + y,
            PrimOp.INT_SUB: lambda x, y: x - y,
            PrimOp.INT_MUL: lambda x, y: x * y,
            PrimOp.INT_DIV: lambda x, y: x // y,
            PrimOp.INT_MOD: lambda x, y: x % y,
            PrimOp.INT_EQ:  lambda x, y: x == y,
            PrimOp.INT_LT:  lambda x, y: x < y,
            PrimOp.INT_GT:  lambda x, y: x > y,
            PrimOp.BOOL_AND: lambda x, y: x and y,
            PrimOp.BOOL_OR:  lambda x, y: x or y,
            PrimOp.STR_CONCAT: lambda x, y: str(x) + str(y),
        }
        if op in ops:
            return ops[op](a, b)
        raise XiError(f"Unknown binary op: {PRIM_NAME.get(op, '?')}")

    def _substitute(self, node: Node, idx: int, val: Node) -> Node:
        """Substitute de Bruijn index `idx` with `val` in `node`."""
        if node.tag == Tag.PRIM and node.prim_op == PrimOp.VAR:
            if node.data == idx:
                return val
            elif node.data > idx:
                return Node(Tag.PRIM, prim_op=PrimOp.VAR, data=node.data - 1)
            return node

        # Under binders, shift the index
        new_children = []
        for i, child in enumerate(node.children):
            if node.tag in (Tag.LAM, Tag.FIX) and i == 1:
                new_children.append(self._substitute(child, idx + 1, val))
            else:
                new_children.append(self._substitute(child, idx, val))

        return Node(
            tag=node.tag, children=new_children,
            prim_op=node.prim_op, data=node.data,
            effect=node.effect, universe_level=node.universe_level,
        )

    def _to_node(self, value: Any) -> Node:
        if isinstance(value, Node):
            return value
        if isinstance(value, int):
            return B.int_lit(value)
        if isinstance(value, float):
            return Node(Tag.PRIM, prim_op=PrimOp.FLOAT_LIT, data=value)
        if isinstance(value, str):
            return B.str_lit(value)
        if isinstance(value, bool):
            return Node(Tag.PRIM, prim_op=PrimOp.BOOL_TRUE if value else PrimOp.BOOL_FALSE)
        return B.unit()


# ═══════════════════════════════════════════════════════════════
# VISUALIZER — Debug graph rendering
# ═══════════════════════════════════════════════════════════════

def node_label(n: Node) -> str:
    """Human-readable label for a node."""
    if n.tag == Tag.PRIM:
        name = PRIM_NAME.get(n.prim_op, f"0x{n.prim_op:02x}")
        if n.prim_op == PrimOp.VAR:
            return f"var({n.data})"
        elif n.data is not None:
            if isinstance(n.data, str):
                return f'# [{name}: "{n.data}"]'
            return f"# [{name}: {n.data}]"
        return f"# [{name}]"
    elif n.tag == Tag.EFF:
        effs = [EFFECT_NAME[e] for e in Effect if e != Effect.PURE and n.effect & e]
        return "!{" + ", ".join(effs) + "}" if effs else "!{Pure}"
    elif n.tag == Tag.UNI:
        return f"𝒰{n.universe_level}"
    return TAG_SYMBOL.get(n.tag, f"Tag(0x{n.tag:x})")


def render_tree(n: Node, indent: int = 0, prefix: str = "") -> str:
    """Render a Xi graph as an indented tree string."""
    pad = "   " * indent
    lines = [f"{pad}{prefix}{node_label(n)}"]
    for i, child in enumerate(n.children):
        is_last = (i == len(n.children) - 1)
        child_prefix = "└─ " if is_last else "├─ "
        lines.append(render_tree(child, indent + 1, child_prefix))
    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════
# DEMO PROGRAMS
# ═══════════════════════════════════════════════════════════════

def make_demos():
    """Build the demo programs."""
    demos = []

    # 1. Hello World
    hello = B.effect(
        B.app(B.prim(PrimOp.PRINT), B.str_lit("Hello, World!")),
        Effect.IO
    )
    demos.append(("Hello, World!", hello, "!{IO} Unit"))

    # 2. Arithmetic: (3 + 5) × 2 = 16
    add_3_5 = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(3)), B.int_lit(5))
    mul_by_2 = B.app(B.app(B.prim(PrimOp.INT_MUL), add_3_5), B.int_lit(2))
    arith = B.effect(
        B.app(B.prim(PrimOp.PRINT), mul_by_2),
        Effect.IO
    )
    demos.append(("Arithmetic: (3+5)×2", arith, "!{IO} Unit"))

    # 3. String concatenation
    concat = B.app(
        B.app(B.prim(PrimOp.STR_CONCAT), B.str_lit("Hello, ")),
        B.str_lit("Xi!")
    )
    str_demo = B.effect(
        B.app(B.prim(PrimOp.PRINT), concat),
        Effect.IO
    )
    demos.append(("String concat", str_demo, "!{IO} Unit"))

    # 4. Lambda: double = λx. x + x, applied to 21
    double_body = B.app(
        B.app(B.prim(PrimOp.INT_ADD), B.var(0)),
        B.var(0)
    )
    double_fn = B.lam(B.universe(0), double_body)
    double_applied = B.effect(
        B.app(B.prim(PrimOp.PRINT), B.app(double_fn, B.int_lit(21))),
        Effect.IO
    )
    demos.append(("Lambda: double(21)", double_applied, "!{IO} Unit"))

    return demos


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

HEADER = """\
╔═══════════════════════════════════════════════════════════╗
║  Ξ (Xi) Reference Implementation v0.1                    ║
║  Copyright (c) 2026 Alex P. Slaby — MIT License          ║
╚═══════════════════════════════════════════════════════════╝"""


def cmd_demo():
    print(HEADER)
    print()

    interp = Interpreter()
    demos = make_demos()

    for i, (name, program, type_str) in enumerate(demos, 1):
        binary = serialize(program)
        hash_str = program.hash_short()

        print(f"{'─' * 59}")
        print(f"  Demo {i}: {name}")
        print(f"  Type: {type_str}  │  {len(binary)} bytes  │  {hash_str}…")
        print(f"{'─' * 59}")
        print()

        # Graph visualization
        print("  Graph:")
        for line in render_tree(program).split('\n'):
            print(f"    {line}")
        print()

        # Hex dump
        print("  Binary:")
        print(hexdump(binary))
        print()

        # Execute
        print("  Output: ", end="", flush=True)
        try:
            result = interp.run(program)
            if result is not None:
                print(f"→ {result}")
            # (print already outputs, so just newline if None)
        except XiError as e:
            print(f"[error] {e}")
        print()

    # Save binary files
    script_dir = os.path.dirname(os.path.abspath(__file__))
    examples_dir = os.path.join(os.path.dirname(script_dir), "examples")
    os.makedirs(examples_dir, exist_ok=True)

    for name, program, _ in demos:
        safe_name = name.lower()
        for ch in " ,:!()×+":
            safe_name = safe_name.replace(ch, "_")
        while "__" in safe_name:
            safe_name = safe_name.replace("__", "_")
        safe_name = safe_name.strip("_")
        filepath = os.path.join(examples_dir, f"{safe_name}.xi")
        with open(filepath, 'wb') as f:
            f.write(serialize(program))

    print(f"  ✓ Binary .xi files saved to {examples_dir}/")
    print()


def cmd_info(filepath):
    if not os.path.exists(filepath):
        print(f"Error: file not found: {filepath}")
        sys.exit(1)

    with open(filepath, 'rb') as f:
        data = f.read()

    print(HEADER)
    print()

    if data[:2] != MAGIC:
        print(f"  Error: not a Xi binary (expected magic CE 9E, got {data[0]:02X} {data[1]:02X})")
        sys.exit(1)

    version = data[2]
    node_count = int.from_bytes(data[3:5], 'big')
    root_index = int.from_bytes(data[5:7], 'big')

    print(f"  File:    {filepath}")
    print(f"  Size:    {len(data)} bytes")
    print(f"  Version: {version}")
    print(f"  Nodes:   {node_count}")
    print(f"  Root:    node {root_index}")
    print()
    print("  Hex dump:")
    print(hexdump(data))
    print()


def cmd_help():
    print(HEADER)
    print()
    print("  Usage:")
    print("    python xi.py demo              Run built-in demos")
    print("    python xi.py info <file.xi>    Show binary file info")
    print("    python xi.py help              Show this help")
    print()


def main():
    if len(sys.argv) < 2:
        cmd_help()
        return

    cmd = sys.argv[1].lower()

    if cmd == "demo":
        cmd_demo()
    elif cmd == "info" and len(sys.argv) >= 3:
        cmd_info(sys.argv[2])
    elif cmd in ("help", "--help", "-h"):
        cmd_help()
    else:
        cmd_help()


if __name__ == "__main__":
    main()
