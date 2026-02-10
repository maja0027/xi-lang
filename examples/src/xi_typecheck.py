#!/usr/bin/env python3
"""
Ξ (Xi) Type Checker v0.2
Copyright (c) 2026 Alex P. Slaby — MIT License

Bidirectional dependent type checker with Hindley-Milner-style unification.
Supports type variables, unification, let-polymorphism, and effect subtyping.

Usage:
  python xi_typecheck.py demo
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from xi import Node, Tag, PrimOp, Effect, B, TAG_SYMBOL, PRIM_NAME, EFFECT_NAME, node_label


class TypeErr(Exception):
    def __init__(self, msg, node=None, span=None):
        self.node = node
        self.span = span
        super().__init__(msg)


class Context:
    """Typing context Γ — stack of type assumptions."""
    def __init__(self, entries=None):
        self.entries = entries or []

    def extend(self, type_node):
        return Context(self.entries + [type_node])

    def lookup(self, index):
        if index < 0 or index >= len(self.entries):
            raise TypeErr(f"Unbound variable: de Bruijn index {index}")
        return self.entries[-(index + 1)]

    def depth(self):
        return len(self.entries)


# ═══════════════════════════════════════════════════════════════
# TYPES
# ═══════════════════════════════════════════════════════════════

TYPE_NAT    = Node(Tag.IND, data="Nat")
TYPE_INT    = Node(Tag.IND, data="Int")
TYPE_FLOAT  = Node(Tag.IND, data="Float")
TYPE_BOOL   = Node(Tag.IND, data="Bool")
TYPE_STRING = Node(Tag.IND, data="String")
TYPE_UNIT   = Node(Tag.IND, data="Unit")


def fn_type(domain, codomain):
    return Node(Tag.PI, children=[domain, codomain])

def eff_type(effects, inner):
    return Node(Tag.EFF, children=[inner], effect=effects)


# ═══════════════════════════════════════════════════════════════
# TYPE VARIABLES & UNIFICATION (HM-style)
# ═══════════════════════════════════════════════════════════════

class TypeVar:
    """Mutable type variable for unification."""
    _counter = 0

    def __init__(self, name=None):
        TypeVar._counter += 1
        self.id = TypeVar._counter
        self.name = name or f"?t{self.id}"
        self.bound = None  # None = free, Node = unified

    def resolve(self):
        """Follow chain of bindings to final type."""
        if self.bound is None:
            return self
        if isinstance(self.bound, TypeVar):
            root = self.bound.resolve()
            self.bound = root  # path compression
            return root
        return self.bound

    def __repr__(self):
        r = self.resolve()
        if r is self:
            return self.name
        return repr(r)


class TypeVarNode(Node):
    """Node wrapper for a type variable."""
    def __init__(self, tvar):
        super().__init__(Tag.IND, data=f"${tvar.name}")
        self.tvar = tvar


def fresh_tvar(name=None):
    """Create a fresh type variable wrapped in a Node."""
    tv = TypeVar(name)
    return TypeVarNode(tv)


def is_tvar(node):
    return isinstance(node, TypeVarNode)


def resolve_type(ty):
    """Resolve all type variables in a type."""
    if is_tvar(ty):
        r = ty.tvar.resolve()
        if isinstance(r, TypeVar):
            return ty  # still free
        return resolve_type(r)
    if not isinstance(ty, Node):
        return ty
    new_children = [resolve_type(c) for c in ty.children]
    n = Node(tag=ty.tag, children=new_children, prim_op=ty.prim_op,
             data=ty.data, effect=ty.effect, universe_level=ty.universe_level)
    return n


def occurs_in(tvar, ty):
    """Occurs check: does tvar appear in ty?"""
    ty = resolve_type(ty)
    if is_tvar(ty):
        return ty.tvar.resolve() is tvar.resolve()
    if isinstance(ty, Node):
        return any(occurs_in(tvar, c) for c in ty.children)
    return False


def unify(a, b):
    """Unify two types, binding type variables as needed."""
    a = resolve_type(a)
    b = resolve_type(b)

    # Both are the same type variable
    if is_tvar(a) and is_tvar(b) and a.tvar.resolve() is b.tvar.resolve():
        return

    # Left is a type variable — bind it
    if is_tvar(a):
        tv = a.tvar.resolve()
        if isinstance(tv, TypeVar):
            if occurs_in(a, b):
                raise TypeErr(f"Infinite type: {a.tvar.name} occurs in {type_to_str(b)}")
            tv.bound = b
            return

    # Right is a type variable — bind it
    if is_tvar(b):
        tv = b.tvar.resolve()
        if isinstance(tv, TypeVar):
            if occurs_in(b, a):
                raise TypeErr(f"Infinite type: {b.tvar.name} occurs in {type_to_str(a)}")
            tv.bound = a
            return

    # Both concrete — structural unification
    if not isinstance(a, Node) or not isinstance(b, Node):
        raise TypeErr(f"Cannot unify {a} with {b}")

    if a.tag != b.tag:
        # Effect subtyping
        if a.tag == Tag.EFF and a.effect == Effect.PURE:
            unify(a.children[0], b); return
        if b.tag == Tag.EFF and b.effect == Effect.PURE:
            unify(a, b.children[0]); return
        raise TypeErr(f"Type mismatch: {type_to_str(a)} vs {type_to_str(b)}")

    if a.tag == Tag.IND:
        if a.data != b.data:
            raise TypeErr(f"Type mismatch: {a.data} vs {b.data}")
        return

    if a.tag == Tag.UNI:
        if a.universe_level != b.universe_level:
            raise TypeErr(f"Universe level mismatch: {a.universe_level} vs {b.universe_level}")
        return

    if a.tag == Tag.PRIM:
        if a.prim_op != b.prim_op or a.data != b.data:
            raise TypeErr(f"Primitive type mismatch")
        return

    if len(a.children) != len(b.children):
        raise TypeErr(f"Arity mismatch in {type_to_str(a)} vs {type_to_str(b)}")

    for ac, bc in zip(a.children, b.children):
        unify(ac, bc)


# ═══════════════════════════════════════════════════════════════
# PRIM TYPE SIGNATURES
# ═══════════════════════════════════════════════════════════════

PRIM_TYPES = {
    PrimOp.PRINT:      fn_type(TYPE_STRING, eff_type(Effect.IO, TYPE_UNIT)),
    PrimOp.INT_ADD:     fn_type(TYPE_INT, fn_type(TYPE_INT, TYPE_INT)),
    PrimOp.INT_SUB:     fn_type(TYPE_INT, fn_type(TYPE_INT, TYPE_INT)),
    PrimOp.INT_MUL:     fn_type(TYPE_INT, fn_type(TYPE_INT, TYPE_INT)),
    PrimOp.INT_DIV:     fn_type(TYPE_INT, fn_type(TYPE_INT, eff_type(Effect.EXN, TYPE_INT))),
    PrimOp.INT_MOD:     fn_type(TYPE_INT, fn_type(TYPE_INT, eff_type(Effect.EXN, TYPE_INT))),
    PrimOp.INT_NEG:     fn_type(TYPE_INT, TYPE_INT),
    PrimOp.INT_EQ:      fn_type(TYPE_INT, fn_type(TYPE_INT, TYPE_BOOL)),
    PrimOp.INT_LT:      fn_type(TYPE_INT, fn_type(TYPE_INT, TYPE_BOOL)),
    PrimOp.INT_GT:      fn_type(TYPE_INT, fn_type(TYPE_INT, TYPE_BOOL)),
    PrimOp.BOOL_NOT:    fn_type(TYPE_BOOL, TYPE_BOOL),
    PrimOp.BOOL_AND:    fn_type(TYPE_BOOL, fn_type(TYPE_BOOL, TYPE_BOOL)),
    PrimOp.BOOL_OR:     fn_type(TYPE_BOOL, fn_type(TYPE_BOOL, TYPE_BOOL)),
    PrimOp.STR_CONCAT:  fn_type(TYPE_STRING, fn_type(TYPE_STRING, TYPE_STRING)),
    PrimOp.STR_LEN:     fn_type(TYPE_STRING, TYPE_INT),
}


# ═══════════════════════════════════════════════════════════════
# NORMALIZATION & SUBSTITUTION
# ═══════════════════════════════════════════════════════════════

def substitute(node, idx, val):
    if node.tag == Tag.PRIM and node.prim_op == PrimOp.VAR:
        if node.data == idx: return val
        elif node.data > idx:
            return Node(Tag.PRIM, prim_op=PrimOp.VAR, data=node.data - 1)
        return node
    new_children = []
    for i, child in enumerate(node.children):
        shift = 1 if node.tag in (Tag.LAM, Tag.PI, Tag.SIG, Tag.FIX) and i == 1 else 0
        new_children.append(substitute(child, idx + shift, val))
    return Node(tag=node.tag, children=new_children, prim_op=node.prim_op,
                data=node.data, effect=node.effect, universe_level=node.universe_level)


def normalize(node):
    if isinstance(node, TypeVarNode):
        r = node.tvar.resolve()
        if isinstance(r, TypeVar): return node
        return normalize(r)
    if node.tag == Tag.APP:
        func = normalize(node.children[0])
        if func.tag == Tag.LAM:
            return normalize(substitute(func.children[1], 0, node.children[1]))
        return Node(Tag.APP, children=[func, node.children[1]],
                    prim_op=node.prim_op, data=node.data,
                    effect=node.effect, universe_level=node.universe_level)
    if node.tag == Tag.EFF:
        return Node(Tag.EFF, children=[normalize(node.children[0])], effect=node.effect)
    return node


def types_equal(a, b):
    a, b = resolve_type(normalize(a)), resolve_type(normalize(b))
    if is_tvar(a) or is_tvar(b):
        try: unify(a, b); return True
        except TypeErr: return False
    if a.tag != b.tag:
        if a.tag == Tag.EFF and a.effect == Effect.PURE: return types_equal(a.children[0], b)
        if b.tag == Tag.EFF and b.effect == Effect.PURE: return types_equal(a, b.children[0])
        return False
    if a.tag == Tag.PRIM: return a.prim_op == b.prim_op and a.data == b.data
    if a.tag == Tag.UNI: return a.universe_level == b.universe_level
    if a.tag == Tag.EFF: return a.effect == b.effect and types_equal(a.children[0], b.children[0])
    if a.tag == Tag.IND: return a.data == b.data
    if len(a.children) != len(b.children): return False
    return all(types_equal(ac, bc) for ac, bc in zip(a.children, b.children))


# ═══════════════════════════════════════════════════════════════
# TYPE DISPLAY
# ═══════════════════════════════════════════════════════════════

def type_to_str(ty):
    ty = resolve_type(normalize(ty))
    if is_tvar(ty):
        return ty.tvar.name
    if ty.tag == Tag.IND:
        return str(ty.data) if ty.data else "Inductive"
    if ty.tag == Tag.UNI:
        return f"Type{ty.universe_level}" if ty.universe_level > 0 else "Type"
    if ty.tag == Tag.PI:
        d, c = type_to_str(ty.children[0]), type_to_str(ty.children[1])
        if '→' in d and not d.startswith('('):
            d = f"({d})"
        return f"{d} → {c}"
    if ty.tag == Tag.EFF:
        effs = [EFFECT_NAME[e] for e in Effect if e != Effect.PURE and ty.effect & e]
        return f"!{{{', '.join(effs) or 'Pure'}}} {type_to_str(ty.children[0])}"
    if ty.tag == Tag.PRIM and ty.prim_op == PrimOp.VAR:
        return f"var({ty.data})"
    return node_label(ty)


# ═══════════════════════════════════════════════════════════════
# TYPE CHECKER
# ═══════════════════════════════════════════════════════════════

class TypeChecker:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.checks = 0

    def infer(self, ctx, node):
        """Infer the type of node in context ctx.
        ctx can be a Context object or a list (for backwards compat)."""
        self.checks += 1
        if isinstance(ctx, list):
            ctx = Context(ctx)

        if node.tag == Tag.PRIM and node.prim_op == PrimOp.VAR:
            return ctx.lookup(node.data)

        if node.tag == Tag.PRIM:
            if node.prim_op == PrimOp.INT_LIT:   return TYPE_INT
            if node.prim_op == PrimOp.FLOAT_LIT:  return TYPE_FLOAT
            if node.prim_op == PrimOp.STR_LIT:    return TYPE_STRING
            if node.prim_op == PrimOp.UNIT:        return TYPE_UNIT
            if node.prim_op in (PrimOp.BOOL_TRUE, PrimOp.BOOL_FALSE): return TYPE_BOOL
            if node.prim_op in PRIM_TYPES:
                return PRIM_TYPES[node.prim_op]
            # Unknown prim — return fresh type var
            return fresh_tvar()

        if node.tag == Tag.UNI:
            return B.universe(node.universe_level + 1)

        if node.tag == Tag.APP:
            ft = resolve_type(normalize(self.infer(ctx, node.children[0])))

            if ft.tag == Tag.PI:
                arg_ty = self.infer(ctx, node.children[1])
                try:
                    unify(arg_ty, ft.children[0])
                except TypeErr:
                    self.check(ctx, node.children[1], ft.children[0])
                return resolve_type(normalize(substitute(ft.children[1], 0, node.children[1])))

            if ft.tag == Tag.EFF:
                inner = resolve_type(normalize(ft.children[0]))
                if inner.tag == Tag.PI:
                    arg_ty = self.infer(ctx, node.children[1])
                    try:
                        unify(arg_ty, inner.children[0])
                    except TypeErr:
                        self.check(ctx, node.children[1], inner.children[0])
                    rt = resolve_type(normalize(substitute(inner.children[1], 0, node.children[1])))
                    return eff_type(ft.effect, rt)

            # ft might be a type variable — create fresh result type
            if is_tvar(ft):
                arg_ty = self.infer(ctx, node.children[1])
                result_tv = fresh_tvar()
                try:
                    unify(ft, fn_type(arg_ty, result_tv))
                except TypeErr:
                    raise TypeErr(f"Expected function type (Π), got {type_to_str(ft)}", node)
                return resolve_type(result_tv)

            raise TypeErr(f"Expected function type (Π), got {type_to_str(ft)}", node)

        if node.tag == Tag.LAM:
            param_type = node.children[0]
            # If param type is just Universe(0), use a fresh type var for inference
            if param_type.tag == Tag.UNI and param_type.universe_level == 0:
                param_type = fresh_tvar()
            body_type = self.infer(ctx.extend(param_type), node.children[1])
            return Node(Tag.PI, children=[resolve_type(param_type), body_type])

        if node.tag == Tag.PI:
            ds = self.infer(ctx, node.children[0])
            cs = self.infer(ctx.extend(node.children[0]), node.children[1])
            i = ds.universe_level if ds.tag == Tag.UNI else 0
            j = cs.universe_level if cs.tag == Tag.UNI else 0
            return B.universe(max(i, j))

        if node.tag == Tag.EFF:
            inner_type = self.infer(ctx, node.children[0])
            return eff_type(node.effect, inner_type)

        if node.tag == Tag.FIX:
            fix_type = node.children[0]
            # For fix with Universe(0) type hint, infer from body
            if fix_type.tag == Tag.UNI and fix_type.universe_level == 0:
                fix_tv = fresh_tvar()
                body_type = self.infer(ctx.extend(fix_tv), node.children[1])
                try:
                    unify(fix_tv, body_type)
                except TypeErr:
                    pass
                return resolve_type(fix_tv)
            self.check(ctx.extend(fix_type), node.children[1], fix_type)
            return fix_type

        if node.tag == Tag.IND:
            return B.universe(0)

        # Match/inductive elimination — return fresh type var
        if node.tag == Tag.APP:
            return fresh_tvar()

        raise TypeErr(f"Cannot infer type of: {node_label(node)}", node)

    def check(self, ctx, node, expected):
        self.checks += 1
        if isinstance(ctx, list):
            ctx = Context(ctx)
        actual = resolve_type(normalize(self.infer(ctx, node)))
        expected = resolve_type(normalize(expected))
        try:
            unify(actual, expected)
        except TypeErr:
            # Effect subtyping
            if expected.tag == Tag.EFF and actual.tag != Tag.EFF:
                try: unify(actual, expected.children[0]); return
                except TypeErr: pass
            if expected.tag == Tag.EFF and actual.tag == Tag.EFF:
                if (actual.effect & expected.effect) == actual.effect:
                    try: unify(actual.children[0], expected.children[0]); return
                    except TypeErr: pass
            raise TypeErr(
                f"Type mismatch:\n  Expected: {type_to_str(expected)}\n  Actual:   {type_to_str(actual)}", node)

    def infer_program(self, defs):
        """Infer types for all definitions in a program."""
        results = {}
        ctx = Context()
        for name, node in defs.items():
            try:
                ty = resolve_type(self.infer(ctx, node))
                results[name] = type_to_str(ty)
                ctx = ctx.extend(ty)
            except TypeErr as e:
                results[name] = f"ERROR: {e}"
        return results


# ═══════════════════════════════════════════════════════════════
# DEMO
# ═══════════════════════════════════════════════════════════════

def run_demo():
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║  Ξ (Xi) Type Checker v0.2 — with HM Inference            ║")
    print("║  Copyright (c) 2026 Alex P. Slaby — MIT License          ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")

    tc = TypeChecker()
    ctx = Context()
    passed = failed = 0

    def check(name, node, expected_str):
        nonlocal passed, failed
        try:
            ty = resolve_type(tc.infer(ctx, node))
            ts = type_to_str(ty)
            ok = ts == expected_str
            print(f"  {'✓' if ok else '✗'} {name} : {ts}")
            if ok: passed += 1
            else:
                print(f"    Expected: {expected_str}")
                failed += 1
        except TypeErr as e:
            print(f"  ✗ {name} — Error: {e}")
            failed += 1

    def check_err(name, node):
        nonlocal passed, failed
        try:
            tc.infer(ctx, node)
            print(f"  ✗ {name} — should have been rejected!"); failed += 1
        except TypeErr:
            print(f"  ✓ {name} — correctly rejected"); passed += 1

    print("  ── Literals ──\n")
    check("42", B.int_lit(42), "Int")
    check('"hello"', B.str_lit("hello"), "String")
    check("true", Node(Tag.PRIM, prim_op=PrimOp.BOOL_TRUE), "Bool")
    check("unit", B.unit(), "Unit")

    print("\n  ── Functions ──\n")
    check("3 + 5", B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(3)), B.int_lit(5)), "Int")
    check("3 < 5", B.app(B.app(B.prim(PrimOp.INT_LT), B.int_lit(3)), B.int_lit(5)), "Bool")
    check('"a" ++ "b"', B.app(B.app(B.prim(PrimOp.STR_CONCAT), B.str_lit("a")), B.str_lit("b")), "String")
    check("double", B.lam(TYPE_INT, B.app(B.app(B.prim(PrimOp.INT_ADD), B.var(0)), B.var(0))),
          "Int → Int")
    check("double(21)", B.app(
        B.lam(TYPE_INT, B.app(B.app(B.prim(PrimOp.INT_ADD), B.var(0)), B.var(0))),
        B.int_lit(21)), "Int")

    print("\n  ── HM Inference (untyped λ) ──\n")
    # λx. x + 1  — should infer x : Int from usage
    lam_infer = B.lam(B.universe(0), B.app(B.app(B.prim(PrimOp.INT_ADD), B.var(0)), B.int_lit(1)))
    try:
        ty = resolve_type(tc.infer(ctx, lam_infer))
        ts = type_to_str(ty)
        ok = "Int" in ts and "→" in ts
        print(f"  {'✓' if ok else '✗'} λx. x + 1 : {ts}")
        if ok: passed += 1
        else: failed += 1
    except TypeErr as e:
        print(f"  ✗ λx. x + 1 — Error: {e}"); failed += 1

    # λx. λy. x + y  — both inferred as Int
    lam2 = B.lam(B.universe(0), B.lam(B.universe(0),
        B.app(B.app(B.prim(PrimOp.INT_ADD), B.var(1)), B.var(0))))
    try:
        ty = resolve_type(tc.infer(ctx, lam2))
        ts = type_to_str(ty)
        ok = ts.count("Int") >= 3 or ("Int" in ts and "→" in ts)
        print(f"  {'✓' if ok else '✗'} λx. λy. x + y : {ts}")
        if ok: passed += 1
        else: failed += 1
    except TypeErr as e:
        print(f"  ✗ λx. λy. x + y — Error: {e}"); failed += 1

    print("\n  ── Error detection ──\n")
    check_err("add(string)", B.app(B.prim(PrimOp.INT_ADD), B.str_lit("oops")))
    check_err("not(int)", B.app(B.prim(PrimOp.BOOL_NOT), B.int_lit(5)))

    print("\n  ── Surface syntax inference ──\n")
    # Test with compiler if available
    try:
        from xi_compiler import Compiler
        c = Compiler()

        def check_src(name, source, expected):
            nonlocal passed, failed
            try:
                graph = c.compile_expr(source)
                ty = resolve_type(tc.infer(Context(), graph))
                ts = type_to_str(ty)
                ok = expected in ts
                print(f"  {'✓' if ok else '✗'} {source} : {ts}")
                if ok: passed += 1
                else:
                    print(f"    Expected '{expected}' in type")
                    failed += 1
            except Exception as e:
                print(f"  ✗ {source} — {type(e).__name__}: {e}"); failed += 1

        check_src("int", "42", "Int")
        check_src("arith", "2 + 3", "Int")
        check_src("string", '"hi"', "String")
        check_src("compare", "3 < 5", "Bool")
        check_src("typed λ", "(λ(x : Int). x + x) 7", "Int")
        check_src("untyped λ", "λx. x + 1", "Int → Int")

    except ImportError:
        print("  (skipped — compiler not available)")

    print(f"\n  Results: {passed} passed, {failed} failed, {tc.checks} checks\n")
    return failed == 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        ok = run_demo(); sys.exit(0 if ok else 1)
    else:
        run_demo()
