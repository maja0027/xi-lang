#!/usr/bin/env python3
"""
Ξ (Xi) Standard Library
Copyright (c) 2026 Alex P. Slaby — MIT License

Core data types and functions built from the 10 primitives.
Demonstrates that Nat, Bool, List, Option, Result etc. are all
expressible as Xi graphs using ι (induction) and μ (fixed point).

Usage:
  python xi_stdlib.py demo
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from xi import Node, Tag, PrimOp, Effect, B, TAG_SYMBOL, render_tree, Interpreter


# ═══════════════════════════════════════════════════════════════
# INDUCTIVE TYPE BUILDER
# ═══════════════════════════════════════════════════════════════

class InductiveType:
    """
    An inductive type definition built from ι-nodes.
    This is the Xi equivalent of 'data' in Haskell, 'enum' in Rust,
    or algebraic data types in ML.
    """
    def __init__(self, name, params=None, constructors=None):
        self.name = name
        self.params = params or []
        self.constructors = constructors or []

    def to_node(self):
        """Build the ι-node graph for this type."""
        # Each constructor is encoded as a child of the ι-node
        con_nodes = []
        for cname, arity in self.constructors:
            con_nodes.append(Node(Tag.PRIM, prim_op=PrimOp.STR_LIT, data=f"{cname}/{arity}"))
        return Node(Tag.IND, children=con_nodes, data=self.name)

    def constructor(self, index, *args):
        """Build a constructor application."""
        # Constructors are #[int_lit] with the constructor index as data
        con = Node(Tag.PRIM, prim_op=PrimOp.INT_LIT, data=index)
        result = con
        for arg in args:
            result = B.app(result, arg)
        return result

    def __repr__(self):
        cons = " | ".join(f"{c}({a})" for c, a in self.constructors)
        return f"{self.name} = ι {{ {cons} }}"


# ═══════════════════════════════════════════════════════════════
# LAYER 1: FOUNDATIONAL TYPES
# ═══════════════════════════════════════════════════════════════

# ── Unit ──
Unit = InductiveType("Unit", constructors=[("tt", 0)])

def mk_unit():
    return Unit.constructor(0)


# ── Bool ──
Bool = InductiveType("Bool", constructors=[("true", 0), ("false", 0)])

def mk_true():  return Bool.constructor(0)
def mk_false(): return Bool.constructor(1)


# ── Nat (Peano natural numbers) ──
Nat = InductiveType("Nat", constructors=[("zero", 0), ("succ", 1)])

def mk_zero():
    return Nat.constructor(0)

def mk_succ(n):
    return Nat.constructor(1, n)

def mk_nat(value):
    """Build a Nat from a Python integer."""
    result = mk_zero()
    for _ in range(value):
        result = mk_succ(result)
    return result

def nat_to_int(node):
    """Extract a Python int from a Nat node (for display)."""
    count = 0
    while True:
        if node.tag == Tag.PRIM and node.prim_op == PrimOp.INT_LIT:
            if node.data == 0:  # zero constructor
                return count
            elif node.data == 1:  # succ constructor
                return None  # partial succ without arg
        if node.tag == Tag.APP:
            # succ(n) = @(constructor(1), n)
            count += 1
            node = node.children[1]
        else:
            return count


# ── Option ──
Option = InductiveType("Option", params=["A"], constructors=[("none", 0), ("some", 1)])

def mk_none():
    return Option.constructor(0)

def mk_some(value):
    return Option.constructor(1, value)


# ── Result ──
Result = InductiveType("Result", params=["E", "A"], constructors=[("err", 1), ("ok", 1)])

def mk_err(value):
    return Result.constructor(0, value)

def mk_ok(value):
    return Result.constructor(1, value)


# ── List ──
List = InductiveType("List", params=["A"], constructors=[("nil", 0), ("cons", 2)])

def mk_nil():
    return List.constructor(0)

def mk_cons(head, tail):
    return List.constructor(1, head, tail)

def mk_list(items):
    """Build a List from Python values."""
    result = mk_nil()
    for item in reversed(items):
        if isinstance(item, int):
            result = mk_cons(B.int_lit(item), result)
        elif isinstance(item, str):
            result = mk_cons(B.str_lit(item), result)
        else:
            result = mk_cons(item, result)
    return result


# ═══════════════════════════════════════════════════════════════
# LAYER 2: FUNCTIONS ON CORE TYPES
# ═══════════════════════════════════════════════════════════════

def build_nat_add():
    """
    add : Nat → Nat → Nat
    add zero    m = m
    add (succ n) m = succ (add n m)

    Encoded as: μ(add). λn. λm. match n { zero → m | succ k → succ (add k m) }
    """
    return Node(Tag.FIX, children=[
        B.pi(Nat.to_node(), B.pi(Nat.to_node(), Nat.to_node())),  # type
        B.lam(Nat.to_node(), B.lam(Nat.to_node(),  # λn. λm.
            B.var(1)  # placeholder — real pattern matching needs ι-elimination
        ))
    ], data="nat_add")


def build_list_map():
    """
    map : (A → B) → List A → List B
    Encoded as: μ(map). λf. λxs. match xs { nil → nil | cons h t → cons (f h) (map f t) }
    """
    return Node(Tag.FIX, data="list_map", children=[
        B.universe(0),  # type placeholder
        B.lam(B.universe(0), B.lam(List.to_node(),
            B.var(1)  # placeholder
        ))
    ])


# ═══════════════════════════════════════════════════════════════
# LAYER 2: VERIFIED ALGORITHMS
# ═══════════════════════════════════════════════════════════════

class Sorted:
    """
    The type of proofs that a list is sorted.
    Sorted : List Nat → 𝒰₀
    Sorted nil = Unit
    Sorted (cons x nil) = Unit
    Sorted (cons x (cons y ys)) = (x ≤ y) × Sorted (cons y ys)
    """
    @staticmethod
    def to_node():
        return InductiveType("Sorted", params=["xs"],
            constructors=[("sorted_nil", 0), ("sorted_one", 1), ("sorted_cons", 3)]
        ).to_node()


class Permutation:
    """
    The type of proofs that one list is a permutation of another.
    """
    @staticmethod
    def to_node():
        return InductiveType("Permutation", params=["xs", "ys"],
            constructors=[("perm_nil", 0), ("perm_skip", 2), ("perm_swap", 2), ("perm_trans", 3)]
        ).to_node()


def verified_sort_type():
    """
    sort : Π(xs : List Nat).
           Σ(ys : List Nat).
           Σ(_ : Sorted ys).
           Permutation xs ys

    The return type is a dependent pair: a sorted list PLUS proofs.
    """
    list_nat = List.to_node()
    return B.pi(list_nat,
        Node(Tag.SIG, children=[
            list_nat,
            Node(Tag.SIG, children=[
                Sorted.to_node(),
                Permutation.to_node()
            ])
        ])
    )


# ═══════════════════════════════════════════════════════════════
# DEMO
# ═══════════════════════════════════════════════════════════════

def run_demo():
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║  Ξ (Xi) Standard Library v0.1                            ║")
    print("║  Copyright (c) 2026 Alex P. Slaby — MIT License          ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")

    # ── Type definitions ──
    print("  ── Inductive Type Definitions ──\n")
    for ty in [Unit, Bool, Nat, Option, Result, List]:
        print(f"    {ty}")
    print()

    # ── Value construction ──
    print("  ── Constructed Values ──\n")

    values = [
        ("unit",          mk_unit()),
        ("true",          mk_true()),
        ("false",         mk_false()),
        ("zero",          mk_zero()),
        ("3 (Peano)",     mk_nat(3)),
        ("none",          mk_none()),
        ("some(42)",      mk_some(B.int_lit(42))),
        ("ok(\"hello\")", mk_ok(B.str_lit("hello"))),
        ("err(404)",      mk_err(B.int_lit(404))),
        ("[1, 2, 3]",     mk_list([1, 2, 3])),
    ]

    for name, val in values:
        tree = render_tree(val)
        # Show just first 2 lines for compact display
        lines = tree.split('\n')
        display = lines[0]
        if len(lines) > 1:
            display += f"  (+ {len(lines)-1} more nodes)"
        print(f"    {name:20s} → {display}")

    print()

    # ── Graph structure of Nat 3 ──
    print("  ── Peano number 3 (full graph) ──\n")
    for line in render_tree(mk_nat(3)).split('\n'):
        print(f"    {line}")
    print()

    # ── List [1, 2, 3] ──
    print("  ── List [1, 2, 3] (full graph) ──\n")
    for line in render_tree(mk_list([1, 2, 3])).split('\n'):
        print(f"    {line}")
    print()

    # ── Verified sort type ──
    print("  ── Verified Sort Type Signature ──\n")
    for line in render_tree(verified_sort_type()).split('\n'):
        print(f"    {line}")
    print()

    # ── Content hashes ──
    print("  ── Content Hashes (SHA-256) ──\n")
    for name, val in values[:6]:
        h = val.hash_short()
        print(f"    {name:20s} → {h}…")
    print()

    # Identity check
    a = mk_nat(3)
    b = mk_nat(3)
    print(f"  ── Content Addressing ──")
    print(f"    nat(3) built twice: same hash? {a.content_hash() == b.content_hash()}")
    print(f"    nat(3) ≠ nat(4)?               {a.content_hash() != mk_nat(4).content_hash()}")
    print()


if __name__ == "__main__":
    run_demo()
