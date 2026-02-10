#!/usr/bin/env python3
"""
Ξ (Xi) Deserializer — Read .xi binary files back into graphs
Copyright (c) 2026 Alex P. Slaby — MIT License

Usage:
  python xi_deserialize.py <file.xi>
  python xi_deserialize.py demo
"""

import sys, os, struct
sys.path.insert(0, os.path.dirname(__file__))
from xi import (
    Node, Tag, PrimOp, Effect, B, MAGIC, FORMAT_VERSION,
    render_tree, hexdump, Interpreter, node_label,
)


class DeserializeError(Exception):
    pass


def deserialize(data: bytes) -> Node:
    """
    Read a Xi binary and reconstruct the graph.

    Format (must match serialize() in xi.py exactly):
      Header: CE 9E <version:1> <node_count:2> <root_index:2>
      Body:   sequence of nodes, each:
        [TTTT AAAA]  tag/arity byte
        [child:2]*   child indices (arity count)
        tag-specific payload
    """
    if len(data) < 7:
        raise DeserializeError(f"File too short ({len(data)} bytes)")

    if data[0:2] != MAGIC:
        raise DeserializeError(f"Invalid magic: {data[0:2].hex()}")
    if data[2] != FORMAT_VERSION:
        raise DeserializeError(f"Unsupported version: {data[2]}")

    node_count = int.from_bytes(data[3:5], 'big')
    root_index = int.from_bytes(data[5:7], 'big')

    nodes = []
    pos = 7

    for i in range(node_count):
        if pos >= len(data):
            raise DeserializeError(f"Unexpected EOF at node {i}")

        tag_arity = data[pos]; pos += 1
        tag_val = (tag_arity >> 4) & 0x0F
        arity = tag_arity & 0x0F

        tag_map = {0: Tag.LAM, 1: Tag.APP, 2: Tag.PI, 3: Tag.SIG,
                   4: Tag.UNI, 5: Tag.FIX, 6: Tag.IND, 7: Tag.EQ,
                   8: Tag.EFF, 9: Tag.PRIM}
        if tag_val not in tag_map:
            raise DeserializeError(f"Unknown tag {tag_val:#x} at byte {pos-1}")
        tag = tag_map[tag_val]

        # Read child indices
        child_indices = []
        for _ in range(arity):
            child_indices.append(int.from_bytes(data[pos:pos+2], 'big'))
            pos += 2

        # Tag-specific payload
        prim_op = None
        node_data = None
        effect = 0
        universe_level = 0

        if tag == Tag.PRIM:
            prim_op = data[pos]; pos += 1
            if prim_op == PrimOp.INT_LIT:
                node_data = int.from_bytes(data[pos:pos+8], 'big', signed=True)
                pos += 8
            elif prim_op == PrimOp.FLOAT_LIT:
                node_data = struct.unpack('>d', data[pos:pos+8])[0]
                pos += 8
            elif prim_op == PrimOp.STR_LIT:
                str_len = int.from_bytes(data[pos:pos+2], 'big')
                pos += 2
                node_data = data[pos:pos+str_len].decode('utf-8')
                pos += str_len
            elif prim_op == PrimOp.VAR:
                node_data = int.from_bytes(data[pos:pos+2], 'big')
                pos += 2
            # Other prim_ops (ADD, MUL, PRINT, etc.) have no data

        elif tag == Tag.UNI:
            universe_level = int.from_bytes(data[pos:pos+2], 'big')
            pos += 2

        elif tag == Tag.EFF:
            effect = data[pos]; pos += 1

        node = Node(tag=tag, prim_op=prim_op, data=node_data,
                    effect=effect, universe_level=universe_level)
        node._child_indices = child_indices
        nodes.append(node)

    # Resolve indices → references
    for node in nodes:
        node.children = [nodes[idx] for idx in node._child_indices]
        del node._child_indices

    return nodes[root_index]


def load_file(path: str) -> Node:
    with open(path, 'rb') as f:
        return deserialize(f.read())


def run_demo():
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║  Ξ (Xi) Deserializer v0.1                                ║")
    print("║  Copyright (c) 2026 Alex P. Slaby — MIT License          ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")

    from xi import serialize

    # Round-trip tests
    print("  ── Round-trip verification ──\n")
    tests = [
        ("int(42)", B.int_lit(42)),
        ("int(0)", B.int_lit(0)),
        ("int(-7)", B.int_lit(-7)),
        ('str("hello")', B.str_lit("hello")),
        ("add(3,5)", B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(3)), B.int_lit(5))),
        ("print(hi)", B.effect(B.app(B.prim(PrimOp.PRINT), B.str_lit("hi")), Effect.IO)),
        ("lambda", B.lam(B.universe(0), B.var(0))),
    ]
    passed = 0
    for name, original in tests:
        binary = serialize(original)
        restored = deserialize(binary)
        match = original.content_hash() == restored.content_hash()
        print(f"    {name:20s} → {len(binary):3d} bytes → hash match? {match} {'✓' if match else '✗'}")
        if match:
            passed += 1

    print(f"\n    {passed}/{len(tests)} round-trip tests passed\n")

    # Load .xi files
    print("  ── Load compiled .xi files ──\n")
    examples_dir = os.path.join(os.path.dirname(__file__), '..', 'examples')
    interp = Interpreter()
    for filename in sorted(os.listdir(examples_dir)):
        if not filename.endswith('.xi'):
            continue
        filepath = os.path.join(examples_dir, filename)
        try:
            root = load_file(filepath)
            result = interp.run(root)
            display = result if result is not None else "()"
            print(f"    {filename:30s} → {display}")
        except Exception as e:
            print(f"    {filename:30s} → Error: {e}")
    print()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] != "demo":
        root = load_file(sys.argv[1])
        print(render_tree(root))
        result = Interpreter().run(root)
        if result is not None:
            print(f"Result: {result}")
    else:
        run_demo()
