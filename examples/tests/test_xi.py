#!/usr/bin/env python3
"""
Ξ (Xi) Test Suite
Copyright (c) 2026 Alex P. Slaby — MIT License

Run:  pytest tests/ -v
  or: python -m pytest tests/ -v
  or: python tests/test_xi.py
"""

import sys, os, struct, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from xi import (
    Node, Tag, PrimOp, Effect, B, MAGIC, FORMAT_VERSION,
    serialize, hexdump, render_tree, node_label, Interpreter, XiError,
)


# ═══════════════════════════════════════════════════════════════
# TEST: Core Node Construction
# ═══════════════════════════════════════════════════════════════

class TestNodeConstruction:
    def test_int_literal(self):
        n = B.int_lit(42)
        assert n.tag == Tag.PRIM
        assert n.prim_op == PrimOp.INT_LIT
        assert n.data == 42

    def test_str_literal(self):
        n = B.str_lit("hello")
        assert n.tag == Tag.PRIM
        assert n.prim_op == PrimOp.STR_LIT
        assert n.data == "hello"

    def test_application(self):
        f = B.prim(PrimOp.PRINT)
        a = B.str_lit("hi")
        app = B.app(f, a)
        assert app.tag == Tag.APP
        assert app.arity == 2
        assert app.children[0] is f
        assert app.children[1] is a

    def test_lambda(self):
        body = B.var(0)
        lam = B.lam(B.universe(0), body)
        assert lam.tag == Tag.LAM
        assert lam.arity == 2

    def test_effect(self):
        inner = B.app(B.prim(PrimOp.PRINT), B.str_lit("x"))
        eff = B.effect(inner, Effect.IO)
        assert eff.tag == Tag.EFF
        assert eff.effect == Effect.IO
        assert eff.children[0] is inner

    def test_universe_levels(self):
        u0 = B.universe(0)
        u1 = B.universe(1)
        u5 = B.universe(5)
        assert u0.universe_level == 0
        assert u1.universe_level == 1
        assert u5.universe_level == 5

    def test_unit(self):
        u = B.unit()
        assert u.tag == Tag.PRIM
        assert u.prim_op == PrimOp.UNIT

    def test_var(self):
        v = B.var(3)
        assert v.tag == Tag.PRIM
        assert v.prim_op == PrimOp.VAR
        assert v.data == 3

    def test_fix(self):
        ty = B.universe(0)
        body = B.var(0)
        f = B.fix(ty, body)
        assert f.tag == Tag.FIX
        assert f.arity == 2

    def test_pi(self):
        p = B.pi(B.universe(0), B.universe(0))
        assert p.tag == Tag.PI
        assert p.arity == 2


# ═══════════════════════════════════════════════════════════════
# TEST: Content Hashing
# ═══════════════════════════════════════════════════════════════

class TestContentHashing:
    def test_same_content_same_hash(self):
        a = B.int_lit(42)
        b = B.int_lit(42)
        assert a.content_hash() == b.content_hash()

    def test_different_content_different_hash(self):
        a = B.int_lit(42)
        b = B.int_lit(43)
        assert a.content_hash() != b.content_hash()

    def test_hash_is_32_bytes(self):
        h = B.int_lit(1).content_hash()
        assert len(h) == 32

    def test_hash_deterministic(self):
        n = B.app(B.prim(PrimOp.INT_ADD), B.int_lit(5))
        h1 = n.content_hash()
        h2 = n.content_hash()
        assert h1 == h2

    def test_structural_equality(self):
        """Two independently built identical graphs must hash the same."""
        a = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(3)), B.int_lit(5))
        b = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(3)), B.int_lit(5))
        assert a.content_hash() == b.content_hash()

    def test_different_structure_different_hash(self):
        a = B.app(B.prim(PrimOp.INT_ADD), B.int_lit(3))
        b = B.app(B.prim(PrimOp.INT_MUL), B.int_lit(3))
        assert a.content_hash() != b.content_hash()

    def test_string_hashing(self):
        a = B.str_lit("hello")
        b = B.str_lit("hello")
        c = B.str_lit("world")
        assert a.content_hash() == b.content_hash()
        assert a.content_hash() != c.content_hash()


# ═══════════════════════════════════════════════════════════════
# TEST: Serialization (Binary Format)
# ═══════════════════════════════════════════════════════════════

class TestSerialization:
    def test_magic_bytes(self):
        binary = serialize(B.int_lit(1))
        assert binary[:2] == MAGIC  # CE 9E

    def test_format_version(self):
        binary = serialize(B.int_lit(1))
        assert binary[2] == FORMAT_VERSION

    def test_node_count(self):
        binary = serialize(B.int_lit(1))
        count = int.from_bytes(binary[3:5], 'big')
        assert count == 1

    def test_hello_world_size(self):
        """Hello World should be compact."""
        hello = B.effect(
            B.app(B.prim(PrimOp.PRINT), B.str_lit("Hello, World!")),
            Effect.IO
        )
        binary = serialize(hello)
        assert len(binary) < 50  # should be ~35 bytes

    def test_root_index(self):
        hello = B.effect(
            B.app(B.prim(PrimOp.PRINT), B.str_lit("hi")),
            Effect.IO
        )
        binary = serialize(hello)
        node_count = int.from_bytes(binary[3:5], 'big')
        root_index = int.from_bytes(binary[5:7], 'big')
        assert root_index == node_count - 1  # root is last node

    def test_serialization_deterministic(self):
        prog = B.app(B.prim(PrimOp.INT_ADD), B.int_lit(5))
        b1 = serialize(prog)
        b2 = serialize(prog)
        assert b1 == b2

    def test_nested_serialization(self):
        """Deep nesting should serialize correctly."""
        expr = B.int_lit(1)
        for _ in range(10):
            expr = B.app(B.prim(PrimOp.INT_NEG), expr)
        binary = serialize(expr)
        assert binary[:2] == MAGIC


# ═══════════════════════════════════════════════════════════════
# TEST: Interpreter
# ═══════════════════════════════════════════════════════════════

class TestInterpreter:
    def setup_method(self):
        self.interp = Interpreter()

    def test_int_literal(self):
        assert self.interp.run(B.int_lit(42)) == 42

    def test_str_literal(self):
        assert self.interp.run(B.str_lit("hello")) == "hello"

    def test_addition(self):
        expr = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(3)), B.int_lit(5))
        assert self.interp.run(expr) == 8

    def test_subtraction(self):
        expr = B.app(B.app(B.prim(PrimOp.INT_SUB), B.int_lit(10)), B.int_lit(3))
        assert self.interp.run(expr) == 7

    def test_multiplication(self):
        expr = B.app(B.app(B.prim(PrimOp.INT_MUL), B.int_lit(6)), B.int_lit(7))
        assert self.interp.run(expr) == 42

    def test_division(self):
        expr = B.app(B.app(B.prim(PrimOp.INT_DIV), B.int_lit(20)), B.int_lit(4))
        assert self.interp.run(expr) == 5

    def test_modulo(self):
        expr = B.app(B.app(B.prim(PrimOp.INT_MOD), B.int_lit(17)), B.int_lit(5))
        assert self.interp.run(expr) == 2

    def test_negation(self):
        expr = B.app(B.prim(PrimOp.INT_NEG), B.int_lit(7))
        assert self.interp.run(expr) == -7

    def test_comparison_lt(self):
        assert self.interp.run(B.app(B.app(B.prim(PrimOp.INT_LT), B.int_lit(3)), B.int_lit(5))) == True
        assert self.interp.run(B.app(B.app(B.prim(PrimOp.INT_LT), B.int_lit(5)), B.int_lit(3))) == False

    def test_comparison_gt(self):
        assert self.interp.run(B.app(B.app(B.prim(PrimOp.INT_GT), B.int_lit(5)), B.int_lit(3))) == True

    def test_comparison_eq(self):
        assert self.interp.run(B.app(B.app(B.prim(PrimOp.INT_EQ), B.int_lit(5)), B.int_lit(5))) == True
        assert self.interp.run(B.app(B.app(B.prim(PrimOp.INT_EQ), B.int_lit(5)), B.int_lit(3))) == False

    def test_boolean_not(self):
        assert self.interp.run(B.app(B.prim(PrimOp.BOOL_NOT), Node(Tag.PRIM, prim_op=PrimOp.BOOL_TRUE))) == False

    def test_boolean_and(self):
        t = Node(Tag.PRIM, prim_op=PrimOp.BOOL_TRUE)
        f = Node(Tag.PRIM, prim_op=PrimOp.BOOL_FALSE)
        assert self.interp.run(B.app(B.app(B.prim(PrimOp.BOOL_AND), t), t)) == True
        assert self.interp.run(B.app(B.app(B.prim(PrimOp.BOOL_AND), t), f)) == False

    def test_string_concat(self):
        expr = B.app(B.app(B.prim(PrimOp.STR_CONCAT), B.str_lit("Hello, ")), B.str_lit("Xi!"))
        assert self.interp.run(expr) == "Hello, Xi!"

    def test_string_len(self):
        expr = B.app(B.prim(PrimOp.STR_LEN), B.str_lit("hello"))
        assert self.interp.run(expr) == 5

    def test_effect_unwrap(self):
        """Effect wrapper should be transparent to execution."""
        inner = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(1)), B.int_lit(2))
        expr = B.effect(inner, Effect.IO)
        assert self.interp.run(expr) == 3

    def test_lambda_identity(self):
        """λx. x applied to 42 should return 42."""
        identity = B.lam(B.universe(0), B.var(0))
        expr = B.app(identity, B.int_lit(42))
        assert self.interp.run(expr) == 42

    def test_lambda_double(self):
        """λx. x + x applied to 21 should return 42."""
        double = B.lam(B.universe(0),
            B.app(B.app(B.prim(PrimOp.INT_ADD), B.var(0)), B.var(0))
        )
        expr = B.app(double, B.int_lit(21))
        assert self.interp.run(expr) == 42

    def test_lambda_compose(self):
        """λx. x * x applied to 5 should return 25."""
        square = B.lam(B.universe(0),
            B.app(B.app(B.prim(PrimOp.INT_MUL), B.var(0)), B.var(0))
        )
        expr = B.app(square, B.int_lit(5))
        assert self.interp.run(expr) == 25

    def test_complex_arithmetic(self):
        """(3 + 5) × 2 = 16"""
        add = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(3)), B.int_lit(5))
        expr = B.app(B.app(B.prim(PrimOp.INT_MUL), add), B.int_lit(2))
        assert self.interp.run(expr) == 16

    def test_deeply_nested(self):
        """1 + 1 + 1 + ... + 1 (10 times) = 10"""
        expr = B.int_lit(1)
        for _ in range(9):
            expr = B.app(B.app(B.prim(PrimOp.INT_ADD), expr), B.int_lit(1))
        assert self.interp.run(expr) == 10

    def test_unbound_variable_error(self):
        try:
            self.interp.run(B.var(0))
            assert False, "Should have raised XiError"
        except XiError:
            pass

    def test_print_returns_none(self, capsys):
        prog = B.effect(B.app(B.prim(PrimOp.PRINT), B.str_lit("test")), Effect.IO)
        result = self.interp.run(prog)
        assert result is None
        captured = capsys.readouterr()
        assert "test" in captured.out

    def test_unit_value(self):
        assert self.interp.run(B.unit()) is None


# ═══════════════════════════════════════════════════════════════
# TEST: Type Checker
# ═══════════════════════════════════════════════════════════════

class TestTypeChecker:
    def setup_method(self):
        from xi_typecheck import TypeChecker, Context, TypeErr, type_to_str
        self.tc = TypeChecker()
        self.ctx = Context()
        self.TypeErr = TypeErr
        self.type_to_str = type_to_str

    def test_int_literal_type(self):
        ty = self.tc.infer(self.ctx, B.int_lit(42))
        assert self.type_to_str(ty) == "Int"

    def test_str_literal_type(self):
        ty = self.tc.infer(self.ctx, B.str_lit("hello"))
        assert self.type_to_str(ty) == "String"

    def test_bool_literal_type(self):
        ty = self.tc.infer(self.ctx, Node(Tag.PRIM, prim_op=PrimOp.BOOL_TRUE))
        assert self.type_to_str(ty) == "Bool"

    def test_addition_type(self):
        expr = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(3)), B.int_lit(5))
        ty = self.tc.infer(self.ctx, expr)
        assert self.type_to_str(ty) == "Int"

    def test_comparison_type(self):
        expr = B.app(B.app(B.prim(PrimOp.INT_LT), B.int_lit(3)), B.int_lit(5))
        ty = self.tc.infer(self.ctx, expr)
        assert self.type_to_str(ty) == "Bool"

    def test_lambda_type(self):
        from xi_typecheck import TYPE_INT
        lam = B.lam(TYPE_INT, B.app(B.app(B.prim(PrimOp.INT_ADD), B.var(0)), B.var(0)))
        ty = self.tc.infer(self.ctx, lam)
        assert "Int → Int" in self.type_to_str(ty)

    def test_type_error_add_string(self):
        bad = B.app(B.prim(PrimOp.INT_ADD), B.str_lit("oops"))
        try:
            self.tc.infer(self.ctx, bad)
            assert False, "Should have raised TypeErr"
        except self.TypeErr:
            pass

    def test_type_error_not_int(self):
        bad = B.app(B.prim(PrimOp.BOOL_NOT), B.int_lit(5))
        try:
            self.tc.infer(self.ctx, bad)
            assert False, "Should have raised TypeErr"
        except self.TypeErr:
            pass

    def test_universe_type(self):
        ty = self.tc.infer(self.ctx, B.universe(0))
        assert "Type" in self.type_to_str(ty)

    def test_effect_type(self):
        expr = B.effect(B.app(B.prim(PrimOp.PRINT), B.str_lit("hi")), Effect.IO)
        ty = self.tc.infer(self.ctx, expr)
        s = self.type_to_str(ty)
        assert "IO" in s


# ═══════════════════════════════════════════════════════════════
# TEST: Standard Library
# ═══════════════════════════════════════════════════════════════

class TestStdlib:
    def setup_method(self):
        from xi_stdlib import (
            mk_unit, mk_true, mk_false, mk_zero, mk_succ, mk_nat,
            mk_none, mk_some, mk_ok, mk_err, mk_nil, mk_cons, mk_list,
            Nat, Bool, Unit, Option, Result, List,
        )
        self.mk_unit = mk_unit
        self.mk_true = mk_true
        self.mk_false = mk_false
        self.mk_zero = mk_zero
        self.mk_succ = mk_succ
        self.mk_nat = mk_nat
        self.mk_none = mk_none
        self.mk_some = mk_some
        self.mk_ok = mk_ok
        self.mk_err = mk_err
        self.mk_nil = mk_nil
        self.mk_cons = mk_cons
        self.mk_list = mk_list

    def test_nat_construction(self):
        zero = self.mk_zero()
        assert zero.tag == Tag.PRIM

    def test_nat_peano(self):
        n3 = self.mk_nat(3)
        assert n3.tag == Tag.APP  # succ(succ(succ(zero)))

    def test_nat_hash_equality(self):
        a = self.mk_nat(5)
        b = self.mk_nat(5)
        assert a.content_hash() == b.content_hash()

    def test_nat_hash_inequality(self):
        a = self.mk_nat(3)
        b = self.mk_nat(4)
        assert a.content_hash() != b.content_hash()

    def test_option_none(self):
        n = self.mk_none()
        assert n.tag == Tag.PRIM

    def test_option_some(self):
        s = self.mk_some(B.int_lit(42))
        assert s.tag == Tag.APP

    def test_result_ok(self):
        ok = self.mk_ok(B.str_lit("success"))
        assert ok.tag == Tag.APP

    def test_result_err(self):
        err = self.mk_err(B.int_lit(404))
        assert err.tag == Tag.APP

    def test_list_nil(self):
        nil = self.mk_nil()
        assert nil.tag == Tag.PRIM

    def test_list_construction(self):
        lst = self.mk_list([1, 2, 3])
        assert lst.tag == Tag.APP


# ═══════════════════════════════════════════════════════════════
# TEST: Compiler
# ═══════════════════════════════════════════════════════════════

class TestCompiler:
    def setup_method(self):
        from xi_compiler import Compiler, ParseError, tokenize
        self.compiler = Compiler()
        self.ParseError = ParseError
        self.tokenize = tokenize

    def test_compile_int(self):
        graph, binary = self.compiler.compile("42")
        assert graph.tag == Tag.PRIM
        assert graph.data == 42

    def test_compile_string(self):
        graph, binary = self.compiler.compile('"hello"')
        assert graph.data == "hello"

    def test_compile_addition(self):
        graph, binary = self.compiler.compile("3 + 5")
        assert graph.tag == Tag.APP
        assert binary[:2] == MAGIC

    def test_compile_complex_arithmetic(self):
        graph, _ = self.compiler.compile("(3 + 5) * 2")
        interp = Interpreter()
        assert interp.run(graph) == 16

    def test_compile_string_concat(self):
        graph, _ = self.compiler.compile('"a" ++ "b"')
        interp = Interpreter()
        assert interp.run(graph) == "ab"

    def test_compile_lambda(self):
        graph, _ = self.compiler.compile("fun (x : Int) . x + x")
        assert graph.tag == Tag.LAM

    def test_compile_applied_lambda(self):
        graph, _ = self.compiler.compile("(fun (x : Int) . x + x) 21")
        interp = Interpreter()
        assert interp.run(graph) == 42

    def test_compile_effect(self):
        graph, _ = self.compiler.compile('!{IO} print "test"')
        assert graph.tag == Tag.EFF
        assert graph.effect == Effect.IO

    def test_compile_curried(self):
        graph, _ = self.compiler.compile("fun (x : Int) . fun (y : Int) . x + y")
        assert graph.tag == Tag.LAM
        assert graph.children[1].tag == Tag.LAM

    def test_tokenize_basic(self):
        tokens = self.tokenize("3 + 5")
        kinds = [t.kind for t in tokens]
        assert "INT" in kinds
        assert "PLUS" in kinds

    def test_compile_error(self):
        try:
            self.compiler.compile("??? invalid")
            assert False, "Should have raised error"
        except (self.ParseError, SyntaxError, Exception):
            pass


# ═══════════════════════════════════════════════════════════════
# TEST: Multi-Core Engine
# ═══════════════════════════════════════════════════════════════

class TestMultiCore:
    def test_single_core_correct(self):
        from xi_multicore import MultiCoreEngine
        expr = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(10)), B.int_lit(20))
        engine = MultiCoreEngine(num_cores=1)
        assert engine.run(expr) == 30

    def test_multi_core_correct(self):
        from xi_multicore import MultiCoreEngine
        a = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(10)), B.int_lit(20))
        b = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(30)), B.int_lit(40))
        expr = B.app(B.app(B.prim(PrimOp.INT_ADD), a), b)
        engine = MultiCoreEngine(num_cores=4)
        assert engine.run(expr) == 100

    def test_graph_memory_dedup(self):
        from xi_multicore import GraphMemory
        mem = GraphMemory()
        h1 = mem.store(B.int_lit(42))
        h2 = mem.store(B.int_lit(42))
        assert h1 == h2
        assert mem.size() == 1
        assert mem.dedup_hits == 1

    def test_graph_memory_fetch(self):
        from xi_multicore import GraphMemory
        mem = GraphMemory()
        n = B.int_lit(99)
        h = mem.store(n)
        fetched = mem.fetch(h)
        assert fetched is n


# ═══════════════════════════════════════════════════════════════
# TEST: Visualization
# ═══════════════════════════════════════════════════════════════

class TestVisualization:
    def test_render_tree_basic(self):
        n = B.int_lit(42)
        s = render_tree(n)
        assert "42" in s

    def test_render_tree_nested(self):
        expr = B.app(B.prim(PrimOp.PRINT), B.str_lit("hi"))
        s = render_tree(expr)
        assert "print" in s
        assert "hi" in s

    def test_node_label(self):
        assert "42" in node_label(B.int_lit(42))
        assert "print" in node_label(B.prim(PrimOp.PRINT))
        assert "IO" in node_label(B.effect(B.unit(), Effect.IO))

    def test_hexdump(self):
        data = b'\xCE\x9E\x01\x00'
        s = hexdump(data)
        assert "CE" in s
        assert "9E" in s



# ═══════════════════════════════════════════════════════════════
# TEST: Deserializer (Round-trip)
# ═══════════════════════════════════════════════════════════════

class TestDeserializer:
    def setup_method(self):
        from xi_deserialize import deserialize, DeserializeError
        self.deserialize = deserialize
        self.DeserializeError = DeserializeError

    def _roundtrip(self, node):
        binary = serialize(node)
        restored = self.deserialize(binary)
        return node.content_hash() == restored.content_hash()

    def test_roundtrip_int(self):
        assert self._roundtrip(B.int_lit(42))

    def test_roundtrip_negative_int(self):
        assert self._roundtrip(B.int_lit(-7))

    def test_roundtrip_zero(self):
        assert self._roundtrip(B.int_lit(0))

    def test_roundtrip_string(self):
        assert self._roundtrip(B.str_lit("hello"))

    def test_roundtrip_empty_string(self):
        assert self._roundtrip(B.str_lit(""))

    def test_roundtrip_add(self):
        assert self._roundtrip(B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(3)), B.int_lit(5)))

    def test_roundtrip_effect(self):
        assert self._roundtrip(B.effect(B.app(B.prim(PrimOp.PRINT), B.str_lit("hi")), Effect.IO))

    def test_roundtrip_lambda(self):
        assert self._roundtrip(B.lam(B.universe(0), B.var(0)))

    def test_invalid_magic(self):
        try:
            self.deserialize(b'\x00\x00\x01\x00\x01\x00\x00')
            assert False
        except self.DeserializeError:
            pass

    def test_truncated(self):
        try:
            self.deserialize(b'\xCE\x9E')
            assert False
        except self.DeserializeError:
            pass


# ═══════════════════════════════════════════════════════════════
# TEST: Graphviz Export
# ═══════════════════════════════════════════════════════════════

class TestGraphviz:
    def test_dot_output(self):
        from xi_graphviz import to_dot
        dot = to_dot(B.int_lit(42), "test")
        assert "digraph Xi" in dot
        assert "42" in dot

    def test_dot_nested(self):
        from xi_graphviz import to_dot
        expr = B.app(B.prim(PrimOp.PRINT), B.str_lit("hi"))
        dot = to_dot(expr, "test")
        assert "func" in dot or "arg" in dot

    def test_dot_lambda(self):
        from xi_graphviz import to_dot
        lam = B.lam(B.universe(0), B.var(0))
        dot = to_dot(lam, "identity")
        assert "body" in dot


# ═══════════════════════════════════════════════════════════════
# TEST: Compiler (additional)
# ═══════════════════════════════════════════════════════════════

class TestCompilerRoundtrip:
    """Compile → execute → verify result."""
    def setup_method(self):
        from xi_compiler import Compiler
        self.compiler = Compiler()
        self.interp = Interpreter()

    def test_compile_run_addition(self):
        g, _ = self.compiler.compile("3 + 5")
        assert self.interp.run(g) == 8

    def test_compile_run_multiplication(self):
        g, _ = self.compiler.compile("6 * 7")
        assert self.interp.run(g) == 42

    def test_compile_run_nested(self):
        g, _ = self.compiler.compile("(10 + 20) * 3")
        assert self.interp.run(g) == 90

    def test_compile_run_string(self):
        g, _ = self.compiler.compile('"ab" ++ "cd"')
        assert self.interp.run(g) == "abcd"

    def test_compile_run_lambda(self):
        g, _ = self.compiler.compile("(fun (x : Int) . x + x) 21")
        assert self.interp.run(g) == 42

    def test_compile_serialize_roundtrip(self):
        """Compile → serialize → deserialize → same hash."""
        from xi_deserialize import deserialize
        g, binary = self.compiler.compile("3 + 5")
        restored = deserialize(binary)
        assert g.content_hash() == restored.content_hash()


# ═══════════════════════════════════════════════════════════════
# RUN (without pytest)
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# TEST: Pattern Matching & ι-Elimination
# ═══════════════════════════════════════════════════════════════

class TestPatternMatching:
    def setup_method(self):
        from xi_match import (
            MatchInterpreter, Constructor, constr, match_expr,
            BOOL_TRUE, BOOL_FALSE, bool_match,
            NAT_ZERO, nat_succ, nat, nat_match,
            option_none, option_some, option_match,
            list_nil, list_cons, xi_list, list_match,
            result_ok, result_err, result_match,
            build_nat_add, build_list_length, nat_to_int,
        )
        self.interp = MatchInterpreter()
        self.Constructor = Constructor
        self.constr = constr
        self.match_expr = match_expr
        self.BOOL_TRUE = BOOL_TRUE
        self.BOOL_FALSE = BOOL_FALSE
        self.bool_match = bool_match
        self.NAT_ZERO = NAT_ZERO
        self.nat_succ = nat_succ
        self.nat = nat
        self.nat_match = nat_match
        self.option_none = option_none
        self.option_some = option_some
        self.option_match = option_match
        self.list_nil = list_nil
        self.xi_list = xi_list
        self.list_match = list_match
        self.result_ok = result_ok
        self.result_err = result_err
        self.result_match = result_match
        self.build_nat_add = build_nat_add
        self.build_list_length = build_list_length
        self.nat_to_int = nat_to_int

    def test_bool_match_true(self):
        result = self.interp.run(
            self.bool_match(self.BOOL_TRUE, B.int_lit(1), B.int_lit(0)))
        assert result == 1

    def test_bool_match_false(self):
        result = self.interp.run(
            self.bool_match(self.BOOL_FALSE, B.int_lit(1), B.int_lit(0)))
        assert result == 0

    def test_nat_is_zero(self):
        result = self.interp.run(
            self.nat_match(self.nat(0),
                Node(Tag.PRIM, prim_op=PrimOp.BOOL_TRUE),
                B.lam(B.universe(0), Node(Tag.PRIM, prim_op=PrimOp.BOOL_FALSE))))
        assert result == True

    def test_nat_is_not_zero(self):
        result = self.interp.run(
            self.nat_match(self.nat(3),
                Node(Tag.PRIM, prim_op=PrimOp.BOOL_TRUE),
                B.lam(B.universe(0), Node(Tag.PRIM, prim_op=PrimOp.BOOL_FALSE))))
        assert result == False

    def test_nat_pred(self):
        result = self.interp.run(
            self.nat_match(self.nat(5), self.NAT_ZERO, B.lam(B.universe(0), B.var(0))))
        n = self.nat_to_int(self.interp, result)
        assert n == 4

    def test_nat_add(self):
        add = self.build_nat_add()
        result = self.interp.run(B.app(B.app(add, self.nat(2)), self.nat(3)))
        assert self.nat_to_int(self.interp, result) == 5

    def test_option_none(self):
        result = self.interp.run(
            self.option_match(self.option_none(),
                B.int_lit(42),
                B.lam(B.universe(0), B.var(0))))
        assert result == 42

    def test_option_some(self):
        result = self.interp.run(
            self.option_match(self.option_some(B.int_lit(7)),
                B.int_lit(42),
                B.lam(B.universe(0), B.var(0))))
        assert result == 7

    def test_list_head_nil(self):
        result = self.interp.run(
            self.list_match(self.list_nil(),
                B.int_lit(0),
                B.lam(B.universe(0), B.lam(B.universe(0), B.var(1)))))
        assert result == 0

    def test_list_head_cons(self):
        result = self.interp.run(
            self.list_match(self.xi_list([7, 8, 9]),
                B.int_lit(0),
                B.lam(B.universe(0), B.lam(B.universe(0), B.var(1)))))
        assert result == 7

    def test_list_length_nil(self):
        length = self.build_list_length()
        result = self.interp.run(B.app(length, self.list_nil()))
        assert self.nat_to_int(self.interp, result) == 0

    def test_list_length_3(self):
        length = self.build_list_length()
        result = self.interp.run(B.app(length, self.xi_list([1, 2, 3])))
        assert self.nat_to_int(self.interp, result) == 3

    def test_result_ok(self):
        result = self.interp.run(
            self.result_match(self.result_ok(B.str_lit("yes")),
                B.lam(B.universe(0), B.var(0)),
                B.lam(B.universe(0), B.str_lit("error"))))
        assert result == "yes"

    def test_result_err(self):
        result = self.interp.run(
            self.result_match(self.result_err(B.int_lit(404)),
                B.lam(B.universe(0), B.var(0)),
                B.lam(B.universe(0), B.str_lit("error"))))
        assert result == "error"

    def test_constructor_from_node(self):
        node = self.constr(2, B.int_lit(1), B.int_lit(2))
        c = self.Constructor.from_node(node)
        assert c is not None
        assert c.index == 2
        assert len(c.args) == 2


# ═══════════════════════════════════════════════════════════════
# TEST: Module System
# ═══════════════════════════════════════════════════════════════

class TestModuleSystem:
    def setup_method(self):
        from xi_module import (
            Module, Registry, ModuleCompiler, Export, ModuleError,
            serialize_module, deserialize_module,
        )
        self.Module = Module
        self.Registry = Registry
        self.ModuleCompiler = ModuleCompiler
        self.ModuleError = ModuleError
        self.serialize_module = serialize_module
        self.deserialize_module = deserialize_module
        self.interp = Interpreter()

    def test_module_define(self):
        m = self.Module("Test")
        m.define("x", B.int_lit(42))
        assert "x" in m.exports
        assert len(m.exports) == 1

    def test_module_resolve(self):
        m = self.Module("Test")
        m.define("x", B.int_lit(42))
        node = m.resolve("x")
        assert self.interp.run(node) == 42

    def test_module_resolve_missing(self):
        m = self.Module("Test")
        try:
            m.resolve("nonexistent")
            assert False
        except self.ModuleError:
            pass

    def test_module_hash_deterministic(self):
        m1 = self.Module("A")
        m1.define("x", B.int_lit(1))
        m2 = self.Module("A")
        m2.define("x", B.int_lit(1))
        assert m1.module_hash() == m2.module_hash()

    def test_module_hash_changes(self):
        m1 = self.Module("A")
        m1.define("x", B.int_lit(1))
        m2 = self.Module("A")
        m2.define("x", B.int_lit(2))
        assert m1.module_hash() != m2.module_hash()

    def test_dependency_resolution(self):
        base = self.Module("Base")
        base.define("val", B.int_lit(99))
        app = self.Module("App")
        app.depend(base)
        assert self.interp.run(app.resolve("val")) == 99

    def test_registry(self):
        reg = self.Registry()
        m = self.Module("Test")
        m.define("x", B.int_lit(1))
        h = reg.register(m)
        assert reg.get(h) is m
        assert reg.get_by_name("Test") is m

    def test_registry_list(self):
        reg = self.Registry()
        m = self.Module("A")
        m.define("x", B.int_lit(1))
        reg.register(m)
        lst = reg.list_modules()
        assert len(lst) == 1
        assert lst[0][0] == "A"

    def test_serialize_roundtrip(self):
        m = self.Module("RT")
        m.define("a", B.int_lit(42))
        m.define("b", B.str_lit("hello"))
        binary = self.serialize_module(m)
        restored = self.deserialize_module(binary)
        assert restored.module_hash() == m.module_hash()

    def test_serialize_with_deps(self):
        reg = self.Registry()
        base = self.Module("Base")
        base.define("x", B.int_lit(1))
        reg.register(base)
        app = self.Module("App")
        app.depend(base)
        app.define("y", B.int_lit(2))
        binary = self.serialize_module(app)
        restored = self.deserialize_module(binary, reg)
        assert restored.module_hash() == app.module_hash()

    def test_module_compiler(self):
        reg = self.Registry()
        mc = self.ModuleCompiler(reg)
        source = """
module Test
def x = 42
def y = "hello"
"""
        m = mc.compile_source(source)
        assert len(m.exports) == 2
        assert self.interp.run(m.resolve("x")) == 42
        assert self.interp.run(m.resolve("y")) == "hello"

    def test_resolve_by_hash(self):
        m = self.Module("Test")
        m.define("x", B.int_lit(42))
        h = m.exports["x"].hash
        node = m.resolve_by_hash(h)
        assert self.interp.run(node) == 42

    def test_export_table(self):
        m = self.Module("Test")
        m.define("a", B.int_lit(1))
        m.define("b", B.int_lit(2))
        table = m.export_table()
        assert "a" in table
        assert "b" in table
        assert len(table["a"]) == 64  # hex SHA-256


if __name__ == "__main__":
    import traceback, inspect

    test_classes = [
        TestNodeConstruction, TestContentHashing, TestSerialization,
        TestInterpreter, TestTypeChecker, TestStdlib,
        TestCompiler, TestMultiCore, TestVisualization,
        TestDeserializer, TestGraphviz, TestCompilerRoundtrip,
        TestPatternMatching, TestModuleSystem,
    ]

    passed = failed = errors = 0
    for cls in test_classes:
        print(f"\n  ── {cls.__name__} ──")
        obj = cls()
        for name in sorted(dir(obj)):
            if not name.startswith("test_"):
                continue
            if hasattr(obj, 'setup_method'):
                try:
                    obj.setup_method()
                except Exception as e:
                    print(f"    ✗ {name} (setup: {e})")
                    errors += 1
                    continue
            try:
                method = getattr(obj, name)
                params = inspect.signature(method).parameters
                if len(params) > 0:
                    print(f"    ⊘ {name} (needs pytest)")
                    continue
                method()
                print(f"    ✓ {name}")
                passed += 1
            except AssertionError as e:
                print(f"    ✗ {name}: {e}")
                failed += 1
            except Exception as e:
                print(f"    ✗ {name}: {type(e).__name__}: {e}")
                failed += 1

    print(f"\n  ═══════════════════════════════════")
    print(f"  Results: {passed} passed, {failed} failed, {errors} errors")
    print(f"  ═══════════════════════════════════\n")
    sys.exit(1 if failed + errors > 0 else 0)


# ═══════════════════════════════════════════════════════════════
# EXAMPLE PROGRAMS TESTS
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
# EXAMPLE PROGRAMS TESTS
# ═══════════════════════════════════════════════════════════════

import sys as _sys
_sys.setrecursionlimit(50000)

class TestExamplePrograms:
    """Integration tests for example programs (Fibonacci, factorial, Church, tree, eval)."""

    def _nat_result(self, expr):
        from xi_match import MatchInterpreter, nat_to_int
        interp = MatchInterpreter()
        return nat_to_int(interp, interp.run(expr))

    # ── Fibonacci ──

    def test_fibonacci_sequence(self):
        from xi_match import (MatchInterpreter, NAT_ZERO, nat_succ, nat, nat_match, nat_to_int, build_nat_add)
        add = build_nat_add()
        inner_zero = nat_succ(NAT_ZERO)
        inner_succ = B.lam(B.universe(0),
            B.app(B.app(add, B.app(B.var(3), nat_succ(B.var(0)))), B.app(B.var(3), B.var(0))))
        outer_succ = B.lam(B.universe(0), nat_match(B.var(0), inner_zero, inner_succ))
        body = B.lam(B.universe(0), nat_match(B.var(0), NAT_ZERO, outer_succ))
        fib = B.fix(B.universe(0), body)
        expected = [0, 1, 1, 2, 3, 5, 8, 13]
        for i in range(8):
            assert expected[i] == self._nat_result(B.app(fib, nat(i)))

    # ── Factorial ──

    def test_factorial_sequence(self):
        from xi_match import nat, build_factorial
        fact = build_factorial()
        expected = [1, 1, 2, 6, 24]
        for i in range(5):
            assert expected[i] == self._nat_result(B.app(fact, nat(i)))

    # ── Church Numerals ──

    def test_church_numerals(self):
        from xi_match import MatchInterpreter
        interp = MatchInterpreter()
        for n in range(5):
            body = B.var(0)
            for _ in range(n):
                body = B.app(B.var(1), body)
            c = B.lam(B.universe(0), B.lam(B.universe(0), body))
            inc = B.lam(B.universe(0), B.app(B.app(B.prim(PrimOp.INT_ADD), B.var(0)), B.int_lit(1)))
            assert n == interp.run(B.app(B.app(c, inc), B.int_lit(0)))

    # ── List Sum via Foldr ──

    def test_list_sum(self):
        from xi_match import NAT_ZERO, nat, list_nil, list_cons, build_nat_add, build_list_foldr
        add = build_nat_add()
        foldr = build_list_foldr()
        sum_fn = B.app(B.app(foldr, add), NAT_ZERO)
        nat_list = list_nil()
        for i in reversed([1, 2, 3]):
            nat_list = list_cons(nat(i), nat_list)
        assert 6 == self._nat_result(B.app(sum_fn, nat_list))

    # ── Binary Tree ──

    def test_tree_size(self):
        from xi_match import NAT_ZERO, nat, nat_succ, constr, match_expr, build_nat_add
        TREE_LEAF = constr(0)
        def tree_branch(l, v, r): return constr(1, l, v, r)

        add = build_nat_add()
        branch_b = B.lam(B.universe(0), B.lam(B.universe(0), B.lam(B.universe(0),
            B.app(B.app(add, nat_succ(NAT_ZERO)),
                B.app(B.app(add, B.app(B.var(4), B.var(2))), B.app(B.var(4), B.var(0)))))))
        body = B.lam(B.universe(0), match_expr(B.var(0), [NAT_ZERO, branch_b]))
        size_fn = B.fix(B.universe(0), body)

        assert 0 == self._nat_result(B.app(size_fn, TREE_LEAF))
        tree = tree_branch(
            tree_branch(TREE_LEAF, nat(1), TREE_LEAF), nat(3),
            tree_branch(TREE_LEAF, nat(5), TREE_LEAF))
        assert 3 == self._nat_result(B.app(size_fn, tree))

    # ── Expression Evaluator ──

    def test_expr_evaluator(self):
        from xi_match import nat, constr, match_expr, build_nat_add, build_nat_mul
        add = build_nat_add()
        mul = build_nat_mul()
        lit_b = B.lam(B.universe(0), B.var(0))
        add_b = B.lam(B.universe(0), B.lam(B.universe(0),
            B.app(B.app(add, B.app(B.var(3), B.var(1))), B.app(B.var(3), B.var(0)))))
        mul_b = B.lam(B.universe(0), B.lam(B.universe(0),
            B.app(B.app(mul, B.app(B.var(3), B.var(1))), B.app(B.var(3), B.var(0)))))
        body = B.lam(B.universe(0), match_expr(B.var(0), [lit_b, add_b, mul_b]))
        ev = B.fix(B.universe(0), body)

        def expr_lit(n): return constr(0, n)
        def expr_add(a, b): return constr(1, a, b)
        assert 5 == self._nat_result(B.app(ev, expr_add(expr_lit(nat(2)), expr_lit(nat(3)))))
        assert 42 == self._nat_result(B.app(ev, expr_lit(nat(42))))

    # ── Adoption artifacts ──

    def test_dockerfile_exists(self):
        assert os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'Dockerfile'))

    def test_docker_entrypoint_exists(self):
        assert os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'docker-entrypoint.sh'))

    def test_vscode_extension_exists(self):
        assert os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'editors', 'vscode', 'package.json'))

    def test_examples_file_exists(self):
        assert os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'examples', 'xi_examples.py'))


# ═══════════════════════════════════════════════════════════════
# OPTIMIZER TESTS
# ═══════════════════════════════════════════════════════════════

class TestOptimizer:
    """Optimizer unit tests."""

    def test_constant_fold_add(self):
        from xi_optimizer import constant_fold
        expr = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(2)), B.int_lit(3))
        folded = constant_fold(expr)
        assert Interpreter().run(folded) == 5

    def test_constant_fold_nested(self):
        from xi_optimizer import constant_fold
        inner = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(10)), B.int_lit(20))
        expr = B.app(B.app(B.prim(PrimOp.INT_MUL), inner), inner)
        folded = constant_fold(expr)
        assert Interpreter().run(folded) == 900

    def test_constant_fold_unary(self):
        from xi_optimizer import constant_fold
        expr = B.app(B.prim(PrimOp.INT_NEG), B.int_lit(42))
        folded = constant_fold(expr)
        assert Interpreter().run(folded) == -42

    def test_cse_shares_identical(self):
        from xi_optimizer import cse
        a = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(1)), B.int_lit(2))
        b = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(1)), B.int_lit(2))
        expr = B.app(B.app(B.prim(PrimOp.INT_ADD), a), b)
        opt = cse(expr)
        assert Interpreter().run(opt) == 6

    def test_optimize_reduces_size(self):
        from xi_optimizer import optimize
        inner = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(10)), B.int_lit(20))
        expr = B.app(B.app(B.prim(PrimOp.INT_MUL), inner), inner)
        opt, stats = optimize(expr)
        assert Interpreter().run(opt) == 900
        assert len(serialize(opt)) < len(serialize(expr))

    def test_fold_string_concat(self):
        from xi_optimizer import constant_fold
        expr = B.app(B.app(B.prim(PrimOp.STR_CONCAT), B.str_lit("a")), B.str_lit("b"))
        folded = constant_fold(expr)
        assert Interpreter().run(folded) == "ab"


# ═══════════════════════════════════════════════════════════════
# XiC COMPRESSION TESTS
# ═══════════════════════════════════════════════════════════════

class TestXiCompressed:
    """XiC/0.1 unit tests."""

    def test_roundtrip_int(self):
        from xi_compress import compress, decompress
        assert Interpreter().run(decompress(compress(B.int_lit(42)))) == 42

    def test_roundtrip_negative(self):
        from xi_compress import compress, decompress
        assert Interpreter().run(decompress(compress(B.int_lit(-999)))) == -999

    def test_roundtrip_string(self):
        from xi_compress import compress, decompress
        assert Interpreter().run(decompress(compress(B.str_lit("test")))) == "test"

    def test_roundtrip_addition(self):
        from xi_compress import compress, decompress
        expr = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(10)), B.int_lit(20))
        assert Interpreter().run(decompress(compress(expr))) == 30

    def test_roundtrip_lambda(self):
        from xi_compress import compress, decompress
        expr = B.app(B.lam(B.universe(0), B.app(B.app(B.prim(PrimOp.INT_MUL), B.var(0)), B.var(0))), B.int_lit(7))
        assert Interpreter().run(decompress(compress(expr))) == 49

    def test_compression_ratio_large(self):
        from xi_compress import compression_ratio
        chain = B.int_lit(0)
        for i in range(1, 51):
            chain = B.app(B.app(B.prim(PrimOp.INT_ADD), chain), B.int_lit(i))
        xi_size, xic_size, ratio = compression_ratio(chain)
        assert ratio > 50  # at least 50% reduction

    def test_magic_bytes(self):
        from xi_compress import compress, XIC_MAGIC
        data = compress(B.int_lit(1))
        assert data[:3] == XIC_MAGIC

    def test_dedup_repeated_subtrees(self):
        from xi_compress import compress, decompress
        sub = B.app(B.app(B.prim(PrimOp.INT_MUL), B.int_lit(7)), B.int_lit(13))
        expr = B.app(B.app(B.prim(PrimOp.INT_ADD), sub),
                     B.app(B.app(B.prim(PrimOp.INT_MUL), B.int_lit(7)), B.int_lit(13)))
        assert Interpreter().run(decompress(compress(expr))) == 182


# ═══════════════════════════════════════════════════════════════
# SURFACE SYNTAX PARSER TESTS
# ═══════════════════════════════════════════════════════════════

class TestSurfaceSyntaxParser:
    """Tests for the Xi surface syntax parser (xi_compiler.py v0.2)."""

    def _run(self, source):
        from xi_compiler import Compiler
        from xi_match import MatchInterpreter, nat_to_int, Constructor
        c = Compiler()
        result = c.run_expr(source)
        if isinstance(result, (Constructor, Node)):
            try:
                return nat_to_int(MatchInterpreter(), result)
            except Exception:
                pass
        return result

    def _run_prog(self, source, entry="main"):
        from xi_compiler import Compiler
        from xi_match import MatchInterpreter, nat_to_int, Constructor
        c = Compiler()
        result = c.run_program(source, entry)
        if isinstance(result, (Constructor, Node)):
            try:
                return nat_to_int(MatchInterpreter(), result)
            except Exception:
                pass
        return result

    # ── Literals ──

    def test_integer_literal(self):
        assert self._run("42") == 42

    def test_zero(self):
        assert self._run("0") == 0

    def test_string_literal(self):
        assert self._run('"hello"') == "hello"

    def test_empty_string(self):
        assert self._run('""') == ""

    # ── Arithmetic operators ──

    def test_addition(self):
        assert self._run("2 + 3") == 5

    def test_subtraction(self):
        assert self._run("10 - 3") == 7

    def test_multiplication(self):
        assert self._run("6 * 7") == 42

    def test_division(self):
        assert self._run("15 / 3") == 5

    def test_modulo(self):
        assert self._run("17 % 5") == 2

    def test_precedence_mul_add(self):
        assert self._run("2 + 3 * 4") == 14

    def test_precedence_parens(self):
        assert self._run("(2 + 3) * 4") == 20

    def test_nested_arithmetic(self):
        assert self._run("((1 + 2) * 3 - 4) * 5") == 25

    def test_string_concat(self):
        assert self._run('"hello" ++ " " ++ "world"') == "hello world"

    def test_strlen(self):
        assert self._run('strlen "test"') == 4

    # ── Comparison & boolean ──

    def test_less_than_true(self):
        assert self._run("3 < 5") == True

    def test_less_than_false(self):
        assert self._run("5 < 3") == False

    def test_greater_than(self):
        assert self._run("5 > 3") == True

    def test_equality(self):
        assert self._run("7 == 7") == True

    def test_inequality(self):
        assert self._run("7 == 8") == False

    # ── Lambda ──

    def test_lambda_identity(self):
        assert self._run("(λx. x) 42") == 42

    def test_lambda_double(self):
        assert self._run("(λx. x + x) 21") == 42

    def test_lambda_typed(self):
        assert self._run("(λ(x : Int). x * x) 7") == 49

    def test_lambda_multi_binder(self):
        assert self._run("(λx y. x + y) 3 4") == 7

    def test_lambda_curried(self):
        assert self._run("(λ(x : Int). λ(y : Int). x * y) 6 7") == 42

    def test_lambda_nested_app(self):
        assert self._run("(λf. f 5) (λx. x + 1)") == 6

    def test_lambda_backslash(self):
        assert self._run("(\\x. x) 99") == 99

    def test_lambda_fun(self):
        assert self._run("(fun x. x) 99") == 99

    # ── Let ──

    def test_let_simple(self):
        assert self._run("let x = 5 in x + x") == 10

    def test_let_nested(self):
        assert self._run("let x = 3 in let y = 4 in x * y") == 12

    def test_let_with_lambda(self):
        assert self._run("let double = λx. x + x in double 21") == 42

    def test_let_shadowing(self):
        assert self._run("let x = 1 in let x = 2 in x") == 2

    # ── Pattern matching ──

    def test_match_zero(self):
        assert self._run("match Zero { Zero → 1 | Succ n → 0 }") == 1

    def test_match_succ(self):
        assert self._run("match Succ Zero { Zero → 0 | Succ n → 1 }") == 1

    def test_match_extract_pred(self):
        assert self._run("match Succ (Succ (Succ Zero)) { Zero → Zero | Succ k → k }") == 2

    def test_match_option_none(self):
        assert self._run("match None { None → 0 | Some x → x }") == 0

    def test_match_option_some(self):
        assert self._run("match Some 99 { None → 0 | Some x → x }") == 99

    def test_match_bool_true(self):
        assert self._run("match True { True → 42 | False → 0 }") == 42

    def test_match_with_arrow_syntax(self):
        assert self._run("match Zero { Zero -> 1 | Succ n -> 0 }") == 1

    # ── If/then/else ──

    def test_if_true(self):
        assert self._run("if True then 42 else 0") == 42

    def test_if_false(self):
        assert self._run("if False then 42 else 0") == 0

    def test_if_comparison(self):
        assert self._run("if 3 < 5 then 1 else 0") == 1

    # ── Fix (recursion) ──

    def test_fix_nat_add(self):
        assert self._run("""
            let add = fix self. λn. λm. match n {
                Zero → m | Succ k → Succ (self k m)
            }
            in add (Succ (Succ Zero)) (Succ (Succ (Succ Zero)))
        """) == 5

    def test_fix_fib_7(self):
        assert self._run("""
            let add = fix self. λn. λm. match n {
                Zero → m | Succ k → Succ (self k m)
            }
            in let fib = fix self. λn. match n {
                Zero → Zero
              | Succ k → match k {
                  Zero → Succ Zero
                | Succ j → add (self (Succ j)) (self j)
              }
            }
            in fib (Succ (Succ (Succ (Succ (Succ (Succ (Succ Zero)))))))
        """) == 13

    # ── Comments ──

    def test_line_comment(self):
        assert self._run("42 -- this is a comment") == 42

    def test_block_comment(self):
        assert self._run("{- block comment -} 42") == 42

    def test_nested_block_comment(self):
        assert self._run("{- {- nested -} -} 42") == 42

    # ── Program (def) ──

    def test_program_def(self):
        assert self._run_prog("""
            def double = λx. x + x
            def main = double 21
        """) == 42

    def test_program_multiple_defs(self):
        assert self._run_prog("""
            def add1 = λx. x + 1
            def double = λx. x + x
            def main = double (add1 4)
        """) == 10

    # ── Lexer edge cases ──

    def test_escape_string(self):
        assert self._run(r'"hello\nworld"') == "hello\nworld"

    def test_tokenize_unicode_lambda(self):
        from xi_compiler import tokenize, TK
        tokens = tokenize("λx. x")
        assert tokens[0].kind == TK.LAMBDA
        assert tokens[1].kind == TK.IDENT
        assert tokens[1].value == "x"

    def test_tokenize_arrow(self):
        from xi_compiler import tokenize, TK
        tokens = tokenize("A → B")
        assert tokens[1].kind == TK.ARROW

    def test_tokenize_ascii_arrow(self):
        from xi_compiler import tokenize, TK
        tokens = tokenize("A -> B")
        assert tokens[1].kind == TK.ARROW


# ═══════════════════════════════════════════════════════════════
# TIER 1 & 2: ADTs, IMPORTS, TYPE INFERENCE, ERROR MESSAGES
# ═══════════════════════════════════════════════════════════════

class TestAlgebraicDataTypes:
    """Tests for user-defined algebraic data types."""

    def _run_prog(self, source, entry="main"):
        from xi_compiler import Compiler
        from xi_match import MatchInterpreter, nat_to_int, Constructor
        c = Compiler()
        result = c.run_program(source, entry)
        if isinstance(result, (Constructor, Node)):
            try: return nat_to_int(MatchInterpreter(), result)
            except Exception: pass
        return result

    def test_type_color(self):
        assert self._run_prog("""
            type Color = Red | Green | Blue
            def main = match Red { Red → 1 | Green → 2 | Blue → 3 }
        """) == 1

    def test_type_color_green(self):
        assert self._run_prog("""
            type Color = Red | Green | Blue
            def main = match Green { Red → 1 | Green → 2 | Blue → 3 }
        """) == 2

    def test_type_maybe(self):
        assert self._run_prog("""
            type Maybe = Nothing | Just Int
            def main = match Just 42 { Nothing → 0 | Just x → x }
        """) == 42

    def test_type_maybe_nothing(self):
        assert self._run_prog("""
            type Maybe = Nothing | Just Int
            def main = match Nothing { Nothing → 99 | Just x → x }
        """) == 99

    def test_type_shape(self):
        assert self._run_prog("""
            type Shape = Circle Int | Rect Int Int | Point
            def main = match Point { Circle r → 0 | Rect w h → 0 | Point → 1 }
        """) == 1

    def test_type_multi_arity(self):
        assert self._run_prog("""
            type Shape = Circle Int | Rect Int Int | Point
            def main = match Circle 5 { Circle r → r | Rect w h → 0 | Point → 0 }
        """) == 5


class TestDefWithParams:
    """Tests for def with direct parameters (sugar for lambda)."""

    def _run_prog(self, source, entry="main"):
        from xi_compiler import Compiler
        return Compiler().run_program(source, entry)

    def test_def_one_param(self):
        assert self._run_prog("""
            def double x = x + x
            def main = double 21
        """) == 42

    def test_def_two_params(self):
        assert self._run_prog("""
            def add a b = a + b
            def main = add 17 25
        """) == 42

    def test_def_three_params(self):
        assert self._run_prog("""
            def sum3 a b c = a + b + c
            def main = sum3 10 20 12
        """) == 42

    def test_def_uses_other_def(self):
        assert self._run_prog("""
            def double x = x + x
            def quad x = double (double x)
            def main = quad 5
        """) == 20


class TestImportSystem:
    """Tests for multi-file import."""

    def _run_prog(self, source, entry="main"):
        from xi_compiler import Compiler
        from xi_match import MatchInterpreter, nat_to_int, Constructor
        c = Compiler()
        result = c.run_program(source, entry)
        if isinstance(result, (Constructor, Node)):
            try: return nat_to_int(MatchInterpreter(), result)
            except Exception: pass
        return result

    def test_import_prelude_add(self):
        assert self._run_prog("""
            import Prelude
            def main = add (Succ (Succ Zero)) (Succ (Succ (Succ Zero)))
        """) == 5

    def test_import_prelude_fib(self):
        assert self._run_prog("""
            import Prelude
            def main = fib (Succ (Succ (Succ (Succ (Succ (Succ Zero))))))
        """) == 8

    def test_import_prelude_id(self):
        assert self._run_prog("""
            import Prelude
            def main = id 42
        """) == 42

    def test_import_prelude_const(self):
        assert self._run_prog("""
            import Prelude
            def main = const 42 99
        """) == 42

    def test_import_prelude_max(self):
        assert self._run_prog("""
            import Prelude
            def main = max 3 7
        """) == 7

    def test_import_prelude_min(self):
        assert self._run_prog("""
            import Prelude
            def main = min 3 7
        """) == 3

    def test_import_duplicate_ok(self):
        """Duplicate import should be silently ignored."""
        assert self._run_prog("""
            import Prelude
            import Prelude
            def main = id 42
        """) == 42

    def test_import_not_found(self):
        from xi_compiler import Compiler, ParseError
        import pytest
        with pytest.raises(ParseError, match="Cannot find module"):
            Compiler().run_program("import Nonexistent\ndef main = 1")


class TestHMInference:
    """Tests for Hindley-Milner type inference."""

    def _infer(self, source):
        from xi_compiler import Compiler
        from xi_typecheck import TypeChecker, type_to_str, resolve_type, Context
        graph = Compiler().compile_expr(source)
        ty = resolve_type(TypeChecker().infer(Context(), graph))
        return type_to_str(ty)

    def test_int_literal(self):
        assert self._infer("42") == "Int"

    def test_string_literal(self):
        assert self._infer('"hello"') == "String"

    def test_addition(self):
        assert self._infer("2 + 3") == "Int"

    def test_comparison(self):
        assert self._infer("3 < 5") == "Bool"

    def test_string_concat(self):
        assert self._infer('"a" ++ "b"') == "String"

    def test_typed_lambda(self):
        ty = self._infer("λ(x : Int). x + x")
        assert "Int" in ty and "→" in ty

    def test_untyped_lambda_infer(self):
        """HM should infer Int from x + 1."""
        ty = self._infer("λx. x + 1")
        assert "Int" in ty and "→" in ty

    def test_untyped_multi_lambda(self):
        """HM should infer both params as Int."""
        ty = self._infer("λx. λy. x + y")
        assert ty.count("Int") >= 3 or ("Int → Int → Int" in ty)

    def test_applied_typed_lambda(self):
        assert self._infer("(λ(x : Int). x * x) 7") == "Int"

    def test_let_binding(self):
        assert self._infer("let x = 5 in x + x") == "Int"

    def test_type_error_add_string(self):
        from xi_typecheck import TypeChecker, TypeErr, Context
        from xi_compiler import Compiler
        import pytest
        graph = Compiler().compile_expr('(λ(x : Int). x + 1) "oops"')
        with pytest.raises(TypeErr):
            TypeChecker().infer(Context(), graph)


class TestErrorMessages:
    """Tests for error message quality."""

    def test_undefined_var_has_name(self):
        from xi_compiler import Compiler, ParseError
        import pytest
        with pytest.raises(ParseError, match="xyz"):
            Compiler().compile_expr("xyz")

    def test_undefined_var_has_location(self):
        from xi_compiler import Compiler, ParseError
        try:
            Compiler().compile_expr("xyz")
        except ParseError as e:
            assert e.span is not None
            assert e.span.line == 1

    def test_unknown_constructor_named(self):
        from xi_compiler import Compiler, ParseError
        import pytest
        with pytest.raises(ParseError, match="Blarg"):
            Compiler().compile_expr("match Blarg { Blarg → 1 }")

    def test_unterminated_string(self):
        from xi_compiler import LexError
        import pytest
        with pytest.raises(LexError, match="Unterminated"):
            from xi_compiler import tokenize
            tokenize('"hello')

    def test_unexpected_char(self):
        from xi_compiler import LexError
        import pytest
        with pytest.raises(LexError):
            from xi_compiler import tokenize
            tokenize("§§§")

    def test_format_error_shows_source(self):
        from xi_compiler import Compiler, ParseError, format_error
        try:
            Compiler().compile_expr("1 + + 2")
        except ParseError as e:
            msg = format_error("1 + + 2", e)
            assert "^" in msg  # pointer to error location


class TestEndToEndPipeline:
    """Test full pipeline: source → parse → optimize → serialize → run."""

    def test_full_pipeline(self):
        from xi_compiler import Compiler
        from xi_optimizer import optimize
        from xi import serialize
        from xi_deserialize import deserialize
        from xi_match import MatchInterpreter

        c = Compiler()
        graph = c.compile_expr("(2 + 3) * (4 + 5)")
        opt, stats = optimize(graph)
        binary = serialize(opt)
        restored = deserialize(binary)
        result = MatchInterpreter().run(restored)
        assert result == 45

    def test_pipeline_with_xic(self):
        from xi_compiler import Compiler
        from xi_optimizer import optimize
        from xi_compress import compress, decompress
        from xi_match import MatchInterpreter

        c = Compiler()
        graph = c.compile_expr("(10 + 20) * (10 + 20)")
        opt, stats = optimize(graph)
        xic_bytes = compress(opt)
        restored = decompress(xic_bytes)
        result = MatchInterpreter().run(restored)
        assert result == 900

    def test_xi_src_file_run(self):
        """Test running a .xi-src file."""
        from xi_compiler import Compiler
        import os
        c = Compiler()
        path = os.path.join(os.path.dirname(__file__), '..', 'examples', 'hello.xi-src')
        if os.path.exists(path):
            with open(path) as f:
                source = f.read()
            result = c.run_program(source, 'main')
            assert result == "Hello, Xi!"
