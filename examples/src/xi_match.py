#!/usr/bin/env python3
"""
Ξ (Xi) Pattern Matching & ι-Elimination
Copyright (c) 2026 Alex P. Slaby — MIT License

Implements full pattern matching over inductive types (ι-elimination).
Usage:  python xi_match.py demo
"""

import sys, os
sys.setrecursionlimit(50000)
sys.path.insert(0, os.path.dirname(__file__))
from xi import Node, Tag, PrimOp, Effect, B, Interpreter, XiError, render_tree, node_label, PRIM_NAME

# New primitive ops for pattern matching
MATCH     = 0x60
CONSTR    = 0x61

PRIM_NAME[MATCH]  = "match"
PRIM_NAME[CONSTR] = "constr"


def constr(index, *args):
    """Build a constructor node: constr(index, arg1, arg2, ...)"""
    node = Node(Tag.PRIM, prim_op=CONSTR, data=index)
    result = node
    for arg in args:
        result = B.app(result, arg)
    return result


def match_expr(scrutinee, branches):
    """Build a match expression: @(@(@(#match(n), scrut), b0), b1)"""
    node = Node(Tag.PRIM, prim_op=MATCH, data=len(branches))
    result = B.app(node, scrutinee)
    for branch in branches:
        result = B.app(result, branch)
    return result


class Constructor:
    """A fully applied constructor value."""
    def __init__(self, index, args=None):
        self.index = index
        self.args = args or []

    def to_node(self):
        return constr(self.index, *self.args)

    @staticmethod
    def from_node(node):
        args = []
        current = node
        while current.tag == Tag.APP:
            args.insert(0, current.children[1])
            current = current.children[0]
        if current.tag == Tag.PRIM and current.prim_op == CONSTR:
            return Constructor(current.data, args)
        return None

    def __repr__(self):
        return f"Constructor({self.index}, {len(self.args)} args)"


def _is_constr_chain(node):
    """Check if node is a CONSTR application chain (not match, not other prims)."""
    current = node
    while current.tag == Tag.APP:
        current = current.children[0]
    return current.tag == Tag.PRIM and current.prim_op == CONSTR


class MatchInterpreter(Interpreter):
    """Extended interpreter with ι-elimination (pattern matching)."""

    def _eval(self, n):
        self.reductions += 1
        if self.reductions > 5_000_000:
            raise XiError("Reduction limit exceeded")

        if n.tag == Tag.EFF:
            return self._eval(n.children[0])

        if n.tag == Tag.PRIM:
            if n.prim_op == PrimOp.STR_LIT:  return n.data
            if n.prim_op == PrimOp.INT_LIT:  return n.data
            if n.prim_op == PrimOp.FLOAT_LIT: return n.data
            if n.prim_op == PrimOp.UNIT:     return None
            if n.prim_op == PrimOp.BOOL_TRUE: return True
            if n.prim_op == PrimOp.BOOL_FALSE: return False
            if n.prim_op == PrimOp.VAR:
                raise XiError(f"Unbound variable: de Bruijn index {n.data}")
            return n  # partially applied prim

        if n.tag == Tag.LAM: return n
        if n.tag == Tag.UNI: return f"𝒰{n.universe_level}"
        if n.tag == Tag.PI or n.tag == Tag.SIG: return n
        if n.tag == Tag.IND: return n

        if n.tag == Tag.FIX:
            body = n.children[1]
            return self._eval(self._substitute(body, 0, n))

        if n.tag == Tag.APP:
            return self._eval_app(n)

        raise XiError(f"Cannot evaluate: {node_label(n)}")

    def _eval_app(self, n):
        func = n.children[0]
        arg = n.children[1]

        # 1. Match expression?
        match_info = self._decompose_match(n)
        if match_info:
            return self._reduce_match(*match_info)

        # 2. Direct constructor: @(constr(i), arg)
        if func.tag == Tag.PRIM and func.prim_op == CONSTR:
            val = self._eval(arg)
            return Constructor(func.data, [self._to_node(val)])

        # 3. Multi-arg constructor chain: @(@(constr(i), a1), a2)
        if _is_constr_chain(func):
            c = self._build_constructor(func)
            val = self._eval(arg)
            c.args.append(self._to_node(val))
            return c

        # 4. Lambda β-reduction (check before evaluating arg for efficiency)
        if func.tag == Tag.LAM:
            val = self._eval(arg)
            body = func.children[1]
            return self._eval(self._substitute(body, 0, self._to_node(val)))

        # 5. Direct unary primitive
        if func.tag == Tag.PRIM and func.prim_op != MATCH:
            val = self._eval(arg)
            return self._apply_unary(func.prim_op, val)

        # 6. Binary primitive: @(@(prim, lhs), rhs)
        if func.tag == Tag.APP and func.children[0].tag == Tag.PRIM:
            op = func.children[0].prim_op
            if op != CONSTR and op != MATCH:
                val = self._eval(arg)
                lhs = self._eval(func.children[1])
                return self._apply_binary(op, lhs, val)

        # 7. Evaluate func, then retry
        val = self._eval(arg)
        evaled_func = self._eval(func)
        if isinstance(evaled_func, Node):
            return self._eval(B.app(evaled_func, self._to_node(val)))
        if isinstance(evaled_func, Constructor):
            evaled_func.args.append(self._to_node(val))
            return evaled_func

        raise XiError(f"Cannot apply: {type(evaled_func)}")

    def _build_constructor(self, node):
        """Decompose a constructor application chain and evaluate args."""
        args = []
        current = node
        while current.tag == Tag.APP:
            args.insert(0, current.children[1])
            current = current.children[0]
        idx = current.data
        evaled = [self._to_node(self._eval(a)) for a in args]
        return Constructor(idx, evaled)

    def _decompose_match(self, node):
        """Decompose @(@(@(#match(n), scrut), b0), b1) → (scrutinee, [branches])"""
        apps = []
        current = node
        while current.tag == Tag.APP:
            apps.insert(0, current.children[1])
            current = current.children[0]
        if current.tag == Tag.PRIM and current.prim_op == MATCH:
            num = current.data
            if len(apps) >= 1 + num:
                return apps[0], apps[1:1+num]
        return None

    def _reduce_match(self, scrutinee, branches):
        """ι-reduction: eval scrutinee → Constructor(idx, args), select branch[idx], apply to args."""
        val = self._eval(scrutinee)

        if isinstance(val, Constructor):
            idx, args = val.index, val.args
        elif isinstance(val, Node):
            c = Constructor.from_node(val)
            if c:
                idx, args = c.index, c.args
            else:
                raise XiError(f"Match on non-constructor: {node_label(val)}")
        elif isinstance(val, bool):
            idx, args = (0 if val else 1), []
        elif isinstance(val, int):
            idx, args = val, []
        else:
            raise XiError(f"Match on non-constructor: {val}")

        if idx < 0 or idx >= len(branches):
            raise XiError(f"Constructor {idx} out of range ({len(branches)} branches)")

        result = branches[idx]
        for a in args:
            result = B.app(result, a)
        return self._eval(result)

    def _to_node(self, value):
        if isinstance(value, Constructor):
            return value.to_node()
        return super()._to_node(value)


# ═══════════════════════════════════════════════════════════════
# STANDARD TYPES
# ═══════════════════════════════════════════════════════════════

BOOL_TRUE  = constr(0)
BOOL_FALSE = constr(1)
def bool_match(s, tb, fb): return match_expr(s, [tb, fb])

NAT_ZERO = constr(0)
def nat_succ(n): return constr(1, n)
def nat(v):
    r = NAT_ZERO
    for _ in range(v): r = nat_succ(r)
    return r
def nat_match(s, zb, sb): return match_expr(s, [zb, sb])

def option_none(): return constr(0)
def option_some(v): return constr(1, v)
def option_match(s, nb, sb): return match_expr(s, [nb, sb])

def list_nil(): return constr(0)
def list_cons(h, t): return constr(1, h, t)
def xi_list(items):
    r = list_nil()
    for item in reversed(items):
        if isinstance(item, int): r = list_cons(B.int_lit(item), r)
        elif isinstance(item, str): r = list_cons(B.str_lit(item), r)
        else: r = list_cons(item, r)
    return r
def list_match(s, nb, cb): return match_expr(s, [nb, cb])

def result_ok(v): return constr(0, v)
def result_err(v): return constr(1, v)
def result_match(s, ob, eb): return match_expr(s, [ob, eb])


# ═══════════════════════════════════════════════════════════════
# RECURSIVE FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def build_nat_add():
    """add = μ self. λn. λm. match n { zero→m | succ k→succ(self k m) }"""
    zero_branch = B.var(0)  # m
    succ_branch = B.lam(B.universe(0),  # λk
        nat_succ(B.app(B.app(B.var(3), B.var(0)), B.var(1))))
    body = B.lam(B.universe(0), B.lam(B.universe(0),
        nat_match(B.var(1), zero_branch, succ_branch)))
    return B.fix(B.universe(0), body)

def build_nat_mul():
    """mul = μ self. λn. λm. match n { zero→zero | succ k→add m (self k m) }"""
    add = build_nat_add()
    succ_branch = B.lam(B.universe(0),
        B.app(B.app(add, B.var(1)), B.app(B.app(B.var(3), B.var(0)), B.var(1))))
    body = B.lam(B.universe(0), B.lam(B.universe(0),
        nat_match(B.var(1), NAT_ZERO, succ_branch)))
    return B.fix(B.universe(0), body)

def build_list_length():
    """length = μ self. λxs. match xs { nil→zero | cons h t→succ(self t) }"""
    cons_branch = B.lam(B.universe(0), B.lam(B.universe(0),
        nat_succ(B.app(B.var(3), B.var(0)))))
    body = B.lam(B.universe(0), list_match(B.var(0), NAT_ZERO, cons_branch))
    return B.fix(B.universe(0), body)

def build_list_map():
    """map = μ self. λf. λxs. match xs { nil→nil | cons h t→cons(f h)(self f t) }"""
    cons_branch = B.lam(B.universe(0), B.lam(B.universe(0),
        list_cons(B.app(B.var(3), B.var(1)), B.app(B.app(B.var(4), B.var(3)), B.var(0)))))
    body = B.lam(B.universe(0), B.lam(B.universe(0),
        list_match(B.var(0), list_nil(), cons_branch)))
    return B.fix(B.universe(0), body)

def build_list_foldr():
    """foldr = μ self. λf. λz. λxs. match xs { nil→z | cons h t→f h (self f z t) }"""
    nil_branch = B.var(1)
    cons_branch = B.lam(B.universe(0), B.lam(B.universe(0),
        B.app(B.app(B.var(4), B.var(1)),
            B.app(B.app(B.app(B.var(5), B.var(4)), B.var(3)), B.var(0)))))
    body = B.lam(B.universe(0), B.lam(B.universe(0), B.lam(B.universe(0),
        list_match(B.var(0), nil_branch, cons_branch))))
    return B.fix(B.universe(0), body)

def build_factorial():
    """fact = μ self. λn. match n { zero→1 | succ k→mul(succ k)(self k) }"""
    mul = build_nat_mul()
    succ_branch = B.lam(B.universe(0),
        B.app(B.app(mul, nat_succ(B.var(0))), B.app(B.var(2), B.var(0))))
    body = B.lam(B.universe(0),
        nat_match(B.var(0), nat_succ(NAT_ZERO), succ_branch))
    return B.fix(B.universe(0), body)


# ═══════════════════════════════════════════════════════════════
# NAT → INT HELPER
# ═══════════════════════════════════════════════════════════════

def nat_to_int(interp, val):
    count = 0
    current = val
    limit = 100000
    while limit > 0:
        limit -= 1
        if isinstance(current, Constructor):
            if current.index == 0: return count
            if current.index == 1:
                count += 1
                if current.args:
                    a = current.args[0]
                    current = interp._eval(a) if isinstance(a, Node) else a
                else:
                    return count
            else: return count
        elif isinstance(current, Node):
            c = Constructor.from_node(current)
            if c: current = c
            else: return count
        elif isinstance(current, int):
            return count + current
        else:
            return count
    return count


# ═══════════════════════════════════════════════════════════════
# DEMO
# ═══════════════════════════════════════════════════════════════

def run_demo():
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║  Ξ (Xi) Pattern Matching & ι-Elimination v0.2            ║")
    print("║  Copyright (c) 2026 Alex P. Slaby — MIT License          ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")

    interp = MatchInterpreter()
    passed = 0
    failed = 0

    def check(name, expected, expr):
        nonlocal passed, failed
        try:
            result = interp.run(expr)
            if isinstance(expected, int) and isinstance(result, (Constructor, Node)):
                result = nat_to_int(interp, result)
            ok = result == expected
            print(f"  {'✓' if ok else '✗'} {name}")
            if ok:
                print(f"    → {result}")
                passed += 1
            else:
                print(f"    Expected: {expected}, Actual: {result}")
                failed += 1
        except Exception as e:
            print(f"  ✗ {name}")
            print(f"    Error: {type(e).__name__}: {e}")
            failed += 1

    print("  ── Bool ──\n")
    check("match true → 1", 1, bool_match(BOOL_TRUE, B.int_lit(1), B.int_lit(0)))
    check("match false → 0", 0, bool_match(BOOL_FALSE, B.int_lit(1), B.int_lit(0)))

    print("\n  ── Nat ──\n")
    check("isZero(0)", True, nat_match(nat(0), Node(Tag.PRIM, prim_op=PrimOp.BOOL_TRUE),
        B.lam(B.universe(0), Node(Tag.PRIM, prim_op=PrimOp.BOOL_FALSE))))
    check("isZero(3)", False, nat_match(nat(3), Node(Tag.PRIM, prim_op=PrimOp.BOOL_TRUE),
        B.lam(B.universe(0), Node(Tag.PRIM, prim_op=PrimOp.BOOL_FALSE))))
    check("pred(0) → 0", 0, nat_match(nat(0), NAT_ZERO, B.lam(B.universe(0), B.var(0))))
    check("pred(5) → 4", 4, nat_match(nat(5), NAT_ZERO, B.lam(B.universe(0), B.var(0))))

    print("\n  ── Recursive (μ + match) ──\n")
    add = build_nat_add()
    check("add(2,3) → 5", 5, B.app(B.app(add, nat(2)), nat(3)))
    check("add(0,4) → 4", 4, B.app(B.app(add, nat(0)), nat(4)))

    print("\n  ── Option ──\n")
    check("none.getOrElse(42)", 42, option_match(option_none(), B.int_lit(42), B.lam(B.universe(0), B.var(0))))
    check("some(7).get", 7, option_match(option_some(B.int_lit(7)), B.int_lit(42), B.lam(B.universe(0), B.var(0))))

    print("\n  ── List ──\n")
    check("head([]) → 0", 0, list_match(list_nil(), B.int_lit(0),
        B.lam(B.universe(0), B.lam(B.universe(0), B.var(1)))))
    check("head([7,8,9]) → 7", 7, list_match(xi_list([7,8,9]), B.int_lit(0),
        B.lam(B.universe(0), B.lam(B.universe(0), B.var(1)))))

    print("\n  ── List recursive ──\n")
    length = build_list_length()
    check("length([]) → 0", 0, B.app(length, list_nil()))
    check("length([1,2,3]) → 3", 3, B.app(length, xi_list([1,2,3])))

    print("\n  ── Result ──\n")
    check('ok("yes").unwrap', "yes", result_match(result_ok(B.str_lit("yes")),
        B.lam(B.universe(0), B.var(0)), B.lam(B.universe(0), B.str_lit("error"))))
    check('err(404).unwrap', "error", result_match(result_err(B.int_lit(404)),
        B.lam(B.universe(0), B.var(0)), B.lam(B.universe(0), B.str_lit("error"))))

    print(f"\n  ═══════════════════════════════")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"  ═══════════════════════════════\n")
    return failed == 0


if __name__ == "__main__":
    ok = run_demo()
    sys.exit(0 if ok else 1)
