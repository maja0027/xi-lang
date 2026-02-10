#!/usr/bin/env python3
"""
Ξ (Xi) Example Programs
Copyright (c) 2026 Alex P. Slaby — MIT License

Demonstrates Xi through progressively complex programs:
  1. Fibonacci (recursive, via μ + match)
  2. Factorial (recursive, via μ + match)
  3. Church numerals (pure λ-calculus encoding)
  4. List operations (map, length, sum)
  5. Binary tree (inductive type + size)
  6. Expression evaluator (interpreter in Xi)

Usage:  python examples/xi_examples.py
"""

import sys, os
sys.setrecursionlimit(50000)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from xi import Node, Tag, PrimOp, Effect, B, Interpreter, XiError, serialize
from xi_match import (
    MatchInterpreter, Constructor, constr, match_expr,
    BOOL_TRUE, BOOL_FALSE, bool_match,
    NAT_ZERO, nat_succ, nat, nat_match,
    option_none, option_some, option_match,
    list_nil, list_cons, xi_list, list_match,
    result_ok, result_err, result_match,
    build_nat_add, build_nat_mul, build_list_length,
    build_list_map, build_list_foldr, build_factorial,
    nat_to_int,
)

interp = MatchInterpreter()
passed = 0
failed = 0

def nat_result(expr):
    return nat_to_int(interp, interp.run(expr))

def check(name, expected, actual):
    global passed, failed
    if expected == actual:
        print(f"    ✓ {name} → {actual}")
        passed += 1
    else:
        print(f"    ✗ {name}: expected {expected}, got {actual}")
        failed += 1


# ═══════════════════════════════════════════════════════════════
# 1. FIBONACCI
# ═══════════════════════════════════════════════════════════════

def build_fibonacci():
    """fib = μ(self). λn. match n { zero→0 | succ k→match k { zero→1 | succ k'→add(self k)(self k') } }"""
    add = build_nat_add()
    inner_zero = nat_succ(NAT_ZERO)
    inner_succ = B.lam(B.universe(0),
        B.app(B.app(add, B.app(B.var(3), nat_succ(B.var(0)))), B.app(B.var(3), B.var(0))))
    outer_succ = B.lam(B.universe(0), nat_match(B.var(0), inner_zero, inner_succ))
    body = B.lam(B.universe(0), nat_match(B.var(0), NAT_ZERO, outer_succ))
    return B.fix(B.universe(0), body)

def demo_fibonacci():
    print("\n  ── 1. Fibonacci ──")
    fib = build_fibonacci()
    expected = [0, 1, 1, 2, 3, 5, 8, 13]
    for i in range(8):
        check(f"fib({i})", expected[i], nat_result(B.app(fib, nat(i))))


# ═══════════════════════════════════════════════════════════════
# 2. FACTORIAL
# ═══════════════════════════════════════════════════════════════

def demo_factorial():
    print("\n  ── 2. Factorial ──")
    fact = build_factorial()
    expected = [1, 1, 2, 6, 24]
    for i in range(5):
        check(f"fact({i})", expected[i], nat_result(B.app(fact, nat(i))))


# ═══════════════════════════════════════════════════════════════
# 3. CHURCH NUMERALS (using MatchInterpreter for full β-reduction)
# ═══════════════════════════════════════════════════════════════

def church(n):
    """n = λf. λx. f^n(x)"""
    body = B.var(0)
    for _ in range(n):
        body = B.app(B.var(1), body)
    return B.lam(B.universe(0), B.lam(B.universe(0), body))

def church_to_int(c):
    inc = B.lam(B.universe(0), B.app(B.app(B.prim(PrimOp.INT_ADD), B.var(0)), B.int_lit(1)))
    return interp.run(B.app(B.app(c, inc), B.int_lit(0)))

def demo_church():
    print("\n  ── 3. Church Numerals ──")
    for i in range(5):
        check(f"church({i})", i, church_to_int(church(i)))

    # succ = λn. λf. λx. f (n f x)
    succ_c = B.lam(B.universe(0), B.lam(B.universe(0), B.lam(B.universe(0),
        B.app(B.var(1), B.app(B.app(B.var(2), B.var(1)), B.var(0))))))
    check("succ(3)", 4, church_to_int(B.app(succ_c, church(3))))

    # add = λm. λn. λf. λx. m f (n f x)
    add_c = B.lam(B.universe(0), B.lam(B.universe(0), B.lam(B.universe(0), B.lam(B.universe(0),
        B.app(B.app(B.var(3), B.var(1)), B.app(B.app(B.var(2), B.var(1)), B.var(0)))))))
    check("add(2,3)", 5, church_to_int(B.app(B.app(add_c, church(2)), church(3))))


# ═══════════════════════════════════════════════════════════════
# 4. LIST OPERATIONS
# ═══════════════════════════════════════════════════════════════

def build_list_sum():
    add = build_nat_add()
    foldr = build_list_foldr()
    return B.app(B.app(foldr, add), NAT_ZERO)

def demo_list_ops():
    print("\n  ── 4. List Operations ──")

    length = build_list_length()
    check("length([])", 0, nat_result(B.app(length, list_nil())))
    check("length([1,2,3])", 3, nat_result(B.app(length, xi_list([1,2,3]))))

    # sum
    sum_fn = build_list_sum()
    nat_list = list_nil()
    for i in reversed([1, 2, 3]):
        nat_list = list_cons(nat(i), nat_list)
    check("sum([1,2,3])", 6, nat_result(B.app(sum_fn, nat_list)))

    # map (double) — check head
    map_fn = build_list_map()
    add = build_nat_add()
    double = B.lam(B.universe(0), B.app(B.app(add, B.var(0)), B.var(0)))
    src = list_nil()
    for i in reversed([1, 2, 3]):
        src = list_cons(nat(i), src)
    mapped = interp.run(B.app(B.app(map_fn, double), src))
    if isinstance(mapped, Constructor) and mapped.index == 1:
        head = nat_to_int(interp, interp._eval(mapped.args[0]) if isinstance(mapped.args[0], Node) else mapped.args[0])
        check("head(map(×2, [1,2,3]))", 2, head)


# ═══════════════════════════════════════════════════════════════
# 5. BINARY TREE
# ═══════════════════════════════════════════════════════════════

TREE_LEAF = constr(0)
def tree_branch(l, v, r): return constr(1, l, v, r)
def tree_match_fn(s, lb, bb): return match_expr(s, [lb, bb])

def build_tree_size():
    add = build_nat_add()
    branch_b = B.lam(B.universe(0), B.lam(B.universe(0), B.lam(B.universe(0),
        B.app(B.app(add, nat_succ(NAT_ZERO)),
            B.app(B.app(add, B.app(B.var(4), B.var(2))), B.app(B.var(4), B.var(0)))))))
    body = B.lam(B.universe(0), tree_match_fn(B.var(0), NAT_ZERO, branch_b))
    return B.fix(B.universe(0), body)

def demo_tree():
    print("\n  ── 5. Binary Tree ──")
    tree = tree_branch(
        tree_branch(TREE_LEAF, nat(1), TREE_LEAF),
        nat(3),
        tree_branch(TREE_LEAF, nat(5), TREE_LEAF))
    size_fn = build_tree_size()
    check("size(leaf)", 0, nat_result(B.app(size_fn, TREE_LEAF)))
    check("size(3-node tree)", 3, nat_result(B.app(size_fn, tree)))


# ═══════════════════════════════════════════════════════════════
# 6. EXPRESSION EVALUATOR (Interpreter in Xi)
# ═══════════════════════════════════════════════════════════════

def expr_lit(n): return constr(0, n)
def expr_add(a, b): return constr(1, a, b)
def expr_mul(a, b): return constr(2, a, b)
def expr_match_fn(s, lb, ab, mb): return match_expr(s, [lb, ab, mb])

def build_eval_expr():
    add = build_nat_add()
    mul = build_nat_mul()
    lit_b = B.lam(B.universe(0), B.var(0))
    add_b = B.lam(B.universe(0), B.lam(B.universe(0),
        B.app(B.app(add, B.app(B.var(3), B.var(1))), B.app(B.var(3), B.var(0)))))
    mul_b = B.lam(B.universe(0), B.lam(B.universe(0),
        B.app(B.app(mul, B.app(B.var(3), B.var(1))), B.app(B.var(3), B.var(0)))))
    body = B.lam(B.universe(0), expr_match_fn(B.var(0), lit_b, add_b, mul_b))
    return B.fix(B.universe(0), body)

def demo_eval():
    print("\n  ── 6. Expression Evaluator ──")
    ev = build_eval_expr()
    check("eval(2 + 3)", 5, nat_result(B.app(ev, expr_add(expr_lit(nat(2)), expr_lit(nat(3))))))
    check("eval(Lit 42)", 42, nat_result(B.app(ev, expr_lit(nat(42)))))
    check("eval(1 + (2 + 1))", 4, nat_result(B.app(ev,
        expr_add(expr_lit(nat(1)), expr_add(expr_lit(nat(2)), expr_lit(nat(1)))))))


# ═══════════════════════════════════════════════════════════════

def main():
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║  Ξ (Xi) Example Programs                                 ║")
    print("║  Copyright (c) 2026 Alex P. Slaby — MIT License          ║")
    print("╚═══════════════════════════════════════════════════════════╝")

    demo_fibonacci()
    demo_factorial()
    demo_church()
    demo_list_ops()
    demo_tree()
    demo_eval()

    print(f"\n  ═══════════════════════════════════")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"  ═══════════════════════════════════\n")
    return failed == 0

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
