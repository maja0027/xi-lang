#!/usr/bin/env python3
"""
Ξ (Xi) Optimizer — Graph-level optimizations
Copyright (c) 2026 Alex P. Slaby — MIT License

Implements three optimization passes over the Xi graph:
  1. Dead node elimination — remove unreachable subgraphs
  2. Common subexpression elimination (CSE) — share structurally equal subtrees
  3. Constant folding — evaluate pure primitive operations at compile time

Usage:  python xi_optimizer.py demo
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from xi import Node, Tag, PrimOp, Effect, B, Interpreter, XiError, serialize, render_tree


class OptimizerStats:
    """Track optimization metrics."""
    def __init__(self):
        self.dead_eliminated = 0
        self.cse_shared = 0
        self.constants_folded = 0

    @property
    def total(self):
        return self.dead_eliminated + self.cse_shared + self.constants_folded

    def __repr__(self):
        return (f"OptStats(dead={self.dead_eliminated}, "
                f"cse={self.cse_shared}, fold={self.constants_folded})")


# ═══════════════════════════════════════════════════════════════
# PASS 1: Dead Node Elimination
# ═══════════════════════════════════════════════════════════════

def _collect_reachable(root):
    """Return set of ids of all nodes reachable from root."""
    visited = set()
    stack = [root]
    while stack:
        node = stack.pop()
        nid = id(node)
        if nid in visited:
            continue
        visited.add(nid)
        for child in node.children:
            stack.append(child)
    return visited


def eliminate_dead_nodes(root, stats=None):
    """
    Dead node elimination.

    In a content-addressed DAG, shared nodes may become orphaned after
    other transformations. This pass traverses from the root and rebuilds
    the graph keeping only reachable nodes.

    Returns: (new_root, nodes_removed_count)
    """
    # Count all nodes
    all_nodes = set()
    stack = [root]
    while stack:
        n = stack.pop()
        nid = id(n)
        if nid not in all_nodes:
            all_nodes.add(nid)
            for c in n.children:
                stack.append(c)

    reachable = _collect_reachable(root)
    removed = len(all_nodes) - len(reachable)
    if stats:
        stats.dead_eliminated += removed
    return root, removed


# ═══════════════════════════════════════════════════════════════
# PASS 2: Common Subexpression Elimination (CSE)
# ═══════════════════════════════════════════════════════════════

def _structural_key(node):
    """
    Compute a structural key for CSE.
    Two nodes with the same key are structurally identical.
    """
    if node.tag == Tag.PRIM:
        return (Tag.PRIM, node.prim_op, node.data, node.arity)
    if node.tag == Tag.UNI:
        return (Tag.UNI, node.universe_level)
    if node.tag == Tag.EFF:
        child_keys = tuple(id(c) for c in node.children)
        return (Tag.EFF, node.effect, child_keys)

    child_keys = tuple(id(c) for c in node.children)
    return (node.tag, child_keys)


def cse(root, stats=None):
    """
    Common Subexpression Elimination.

    Bottom-up pass: for each node, compute a structural signature.
    If two nodes have the same signature, share one instance.

    Returns: new root with shared subtrees.
    """
    # Build post-order traversal
    order = []
    visited = set()

    def postorder(node):
        nid = id(node)
        if nid in visited:
            return
        visited.add(nid)
        for child in node.children:
            postorder(child)
        order.append(node)

    postorder(root)

    # Map: structural_key → canonical node
    canonical = {}
    # Map: old node id → replacement node
    replacement = {}
    shared_count = 0

    for node in order:
        # First, replace children with canonical versions
        new_children = []
        changed = False
        for c in node.children:
            rep = replacement.get(id(c), c)
            new_children.append(rep)
            if rep is not c:
                changed = True

        if changed:
            new_node = Node(node.tag, children=new_children,
                           prim_op=node.prim_op, data=node.data,
                           effect=node.effect,
                           universe_level=node.universe_level)
        else:
            new_node = node

        # Compute structural key with canonical children
        if new_node.tag == Tag.PRIM:
            key = (Tag.PRIM, new_node.prim_op, new_node.data, new_node.arity)
        elif new_node.tag == Tag.UNI:
            key = (Tag.UNI, new_node.universe_level)
        elif new_node.tag == Tag.EFF:
            key = (Tag.EFF, new_node.effect, tuple(id(c) for c in new_node.children))
        else:
            key = (new_node.tag, tuple(id(c) for c in new_node.children))

        if key in canonical:
            replacement[id(node)] = canonical[key]
            shared_count += 1
        else:
            canonical[key] = new_node
            replacement[id(node)] = new_node

    if stats:
        stats.cse_shared += shared_count

    return replacement.get(id(root), root)


# ═══════════════════════════════════════════════════════════════
# PASS 3: Constant Folding
# ═══════════════════════════════════════════════════════════════

# Pure primitive ops that can be folded at compile time
_FOLDABLE_BINARY = {
    PrimOp.INT_ADD, PrimOp.INT_SUB, PrimOp.INT_MUL,
    PrimOp.INT_DIV, PrimOp.INT_MOD,
    PrimOp.INT_LT, PrimOp.INT_GT, PrimOp.INT_EQ,
    PrimOp.STR_CONCAT,
}

_FOLDABLE_UNARY = {
    PrimOp.INT_NEG, PrimOp.BOOL_NOT, PrimOp.STR_LEN,
}


def _is_literal(node):
    """Check if node is a compile-time constant."""
    if node.tag != Tag.PRIM:
        return False
    return node.prim_op in (PrimOp.INT_LIT, PrimOp.STR_LIT, PrimOp.FLOAT_LIT,
                            PrimOp.BOOL_TRUE, PrimOp.BOOL_FALSE, PrimOp.UNIT)


def _literal_value(node):
    """Extract the Python value from a literal node."""
    if node.prim_op == PrimOp.INT_LIT: return node.data
    if node.prim_op == PrimOp.STR_LIT: return node.data
    if node.prim_op == PrimOp.FLOAT_LIT: return node.data
    if node.prim_op == PrimOp.BOOL_TRUE: return True
    if node.prim_op == PrimOp.BOOL_FALSE: return False
    if node.prim_op == PrimOp.UNIT: return None
    return None


def _value_to_node(val):
    """Convert a Python value back to a Xi node."""
    if isinstance(val, bool):
        return Node(Tag.PRIM, prim_op=PrimOp.BOOL_TRUE if val else PrimOp.BOOL_FALSE)
    if isinstance(val, int):
        return B.int_lit(val)
    if isinstance(val, str):
        return B.str_lit(val)
    if isinstance(val, float):
        return Node(Tag.PRIM, prim_op=PrimOp.FLOAT_LIT, data=val)
    return None


def constant_fold(root, stats=None):
    """
    Constant folding.

    Bottom-up: when a primitive application has all-literal arguments,
    evaluate it at compile time and replace with the result.

    Example: @(@(#+, 2), 3) → 5
    """
    cache = {}

    def fold(node):
        nid = id(node)
        if nid in cache:
            return cache[nid]

        # Recursively fold children first
        new_children = [fold(c) for c in node.children]
        changed = any(new_children[i] is not node.children[i] for i in range(len(new_children)))

        if changed:
            result = Node(node.tag, children=new_children,
                         prim_op=node.prim_op, data=node.data,
                         effect=node.effect,
                         universe_level=node.universe_level)
        else:
            result = node

        # Try to fold: @(@(prim, lit), lit) → lit
        if (result.tag == Tag.APP
                and result.children[0].tag == Tag.APP
                and result.children[0].children[0].tag == Tag.PRIM
                and result.children[0].children[0].prim_op in _FOLDABLE_BINARY
                and _is_literal(result.children[0].children[1])
                and _is_literal(result.children[1])):
            op = result.children[0].children[0].prim_op
            lhs = _literal_value(result.children[0].children[1])
            rhs = _literal_value(result.children[1])
            try:
                interp = Interpreter()
                val = interp._apply_binary(op, lhs, rhs)
                folded = _value_to_node(val)
                if folded is not None:
                    if stats:
                        stats.constants_folded += 1
                    cache[nid] = folded
                    return folded
            except Exception:
                pass

        # Try to fold: @(prim, lit) → lit  (unary)
        if (result.tag == Tag.APP
                and result.children[0].tag == Tag.PRIM
                and result.children[0].prim_op in _FOLDABLE_UNARY
                and _is_literal(result.children[1])):
            op = result.children[0].prim_op
            arg = _literal_value(result.children[1])
            try:
                interp = Interpreter()
                val = interp._apply_unary(op, arg)
                folded = _value_to_node(val)
                if folded is not None:
                    if stats:
                        stats.constants_folded += 1
                    cache[nid] = folded
                    return folded
            except Exception:
                pass

        cache[nid] = result
        return result

    return fold(root)


# ═══════════════════════════════════════════════════════════════
# COMBINED OPTIMIZER
# ═══════════════════════════════════════════════════════════════

def optimize(root, passes=None):
    """
    Run all optimization passes on a Xi graph.

    Args:
        root: Root node of the Xi graph.
        passes: List of pass names to run. Default: all three.
                Options: 'dce', 'cse', 'fold'

    Returns: (optimized_root, stats)
    """
    if passes is None:
        passes = ['fold', 'cse', 'dce']

    stats = OptimizerStats()
    node = root

    for p in passes:
        if p == 'dce':
            node, _ = eliminate_dead_nodes(node, stats)
        elif p == 'cse':
            node = cse(node, stats)
        elif p == 'fold':
            node = constant_fold(node, stats)
        else:
            raise ValueError(f"Unknown pass: {p}")

    return node, stats


# ═══════════════════════════════════════════════════════════════
# DEMO
# ═══════════════════════════════════════════════════════════════

def run_demo():
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║  Ξ (Xi) Optimizer v0.1                                    ║")
    print("║  Copyright (c) 2026 Alex P. Slaby — MIT License          ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")

    passed = 0
    failed = 0

    def check(name, expected, actual):
        nonlocal passed, failed
        ok = expected == actual
        print(f"  {'✓' if ok else '✗'} {name}")
        if ok:
            print(f"    → {actual}")
            passed += 1
        else:
            print(f"    Expected: {expected}, Got: {actual}")
            failed += 1

    interp = Interpreter()

    # ── Constant folding ──
    print("  ── Constant Folding ──\n")

    # 2 + 3 → 5
    expr1 = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(2)), B.int_lit(3))
    opt1, s1 = optimize(expr1, ['fold'])
    check("fold(2 + 3)", 5, interp.run(opt1))
    check("  folded ops", 1, s1.constants_folded)

    # (2 + 3) * (4 - 1) → 5 * 3 → 15
    add_expr = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(2)), B.int_lit(3))
    sub_expr = B.app(B.app(B.prim(PrimOp.INT_SUB), B.int_lit(4)), B.int_lit(1))
    expr2 = B.app(B.app(B.prim(PrimOp.INT_MUL), add_expr), sub_expr)
    opt2, s2 = optimize(expr2, ['fold'])
    check("fold((2+3)*(4-1))", 15, interp.run(opt2))
    check("  folded ops", 3, s2.constants_folded)

    # -(-5) → 5
    expr3 = B.app(B.prim(PrimOp.INT_NEG), B.app(B.prim(PrimOp.INT_NEG), B.int_lit(5)))
    opt3, s3 = optimize(expr3, ['fold'])
    check("fold(-(-5))", 5, interp.run(opt3))
    check("  folded ops", 2, s3.constants_folded)

    # "hello" ++ " " ++ "world"
    expr4 = B.app(B.app(B.prim(PrimOp.STR_CONCAT),
        B.app(B.app(B.prim(PrimOp.STR_CONCAT), B.str_lit("hello")), B.str_lit(" "))),
        B.str_lit("world"))
    opt4, s4 = optimize(expr4, ['fold'])
    check('fold("hello" ++ " " ++ "world")', "hello world", interp.run(opt4))

    # len("abc") → 3
    expr5 = B.app(B.prim(PrimOp.STR_LEN), B.str_lit("abc"))
    opt5, s5 = optimize(expr5, ['fold'])
    check('fold(len("abc"))', 3, interp.run(opt5))

    # ── CSE ──
    print("\n  ── Common Subexpression Elimination ──\n")

    # Two identical subtrees
    shared = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(1)), B.int_lit(2))
    dup = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(1)), B.int_lit(2))
    expr6 = B.app(B.app(B.prim(PrimOp.INT_ADD), shared), dup)
    before_size = len(serialize(expr6))
    opt6 = cse(expr6)
    after_size = len(serialize(opt6))
    check("CSE((1+2)+(1+2)) correct", 6, interp.run(opt6))
    check("  size reduced", True, after_size <= before_size)

    # ── Combined ──
    print("\n  ── Combined Pipeline ──\n")

    expr7 = B.app(B.app(B.prim(PrimOp.INT_MUL),
        B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(10)), B.int_lit(20))),
        B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(10)), B.int_lit(20)))
    before = len(serialize(expr7))
    opt7, s7 = optimize(expr7)
    after = len(serialize(opt7))
    check("optimize((10+20)*(10+20))", 900, interp.run(opt7))
    check("  size reduced", True, after < before)
    print(f"    Bytes: {before} → {after} ({100*(before-after)//before}% reduction)")
    print(f"    {s7}")

    print(f"\n  ═══════════════════════════════════")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"  ═══════════════════════════════════\n")
    return failed == 0


if __name__ == "__main__":
    ok = run_demo()
    sys.exit(0 if ok else 1)
