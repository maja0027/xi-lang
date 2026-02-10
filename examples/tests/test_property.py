#!/usr/bin/env python3
"""
Ξ (Xi) Property-Based Tests — Hypothesis Fuzzing
Copyright (c) 2026 Alex P. Slaby — MIT License

Fuzz-tests core Xi invariants:
  1. Serialization roundtrip:  deserialize(serialize(x)) ≡ eval(x)
  2. XiC roundtrip:            decompress(compress(x)) evaluates identically
  3. Optimizer correctness:    eval(optimize(x)) ≡ eval(x)
  4. Type checker soundness:   well-typed programs don't crash at runtime
  5. CSE idempotence:          cse(cse(x)) ≡ cse(x)
  6. Content hash determinism: hash(x) = hash(rebuild(x))

Run:  pytest tests/test_property.py -v
  or: python tests/test_property.py
"""

import sys, os
sys.setrecursionlimit(50000)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import hypothesis
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from xi import (
    Node, Tag, PrimOp, Effect, B, serialize, Interpreter, XiError,
    MAGIC, FORMAT_VERSION,
)
from xi_deserialize import deserialize, DeserializeError
from xi_optimizer import optimize, cse, constant_fold, OptimizerStats
from xi_compress import compress, decompress, compression_ratio
from xi_typecheck import TypeChecker, TypeErr as XiTypeError


# ═══════════════════════════════════════════════════════════════
# STRATEGIES — Random Xi AST generation
# ═══════════════════════════════════════════════════════════════

@st.composite
def xi_int(draw):
    """Random Xi integer literal."""
    return B.int_lit(draw(st.integers(min_value=-2**31, max_value=2**31 - 1)))

@st.composite
def xi_str(draw):
    """Random Xi string literal."""
    return B.str_lit(draw(st.text(min_size=0, max_size=50,
                                   alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')))))

@st.composite
def xi_prim(draw):
    """Random Xi primitive."""
    return draw(st.sampled_from([
        B.prim(PrimOp.INT_ADD), B.prim(PrimOp.INT_SUB),
        B.prim(PrimOp.INT_MUL), B.prim(PrimOp.INT_NEG),
        B.prim(PrimOp.STR_CONCAT), B.prim(PrimOp.STR_LEN),
        B.prim(PrimOp.INT_LT), B.prim(PrimOp.INT_GT),
        B.prim(PrimOp.INT_EQ), B.prim(PrimOp.BOOL_NOT),
        B.unit(),
        Node(Tag.PRIM, prim_op=PrimOp.BOOL_TRUE),
        Node(Tag.PRIM, prim_op=PrimOp.BOOL_FALSE),
    ]))


def xi_leaf():
    """Leaf nodes: int, str, prim, unit."""
    return st.one_of(xi_int(), xi_str(), xi_prim())


@st.composite
def xi_tree(draw, max_depth=4):
    """Random Xi AST of bounded depth."""
    if max_depth <= 0:
        return draw(xi_leaf())

    choice = draw(st.integers(min_value=0, max_value=5))

    if choice <= 2:
        # Leaf
        return draw(xi_leaf())
    elif choice == 3:
        # Application
        func = draw(xi_tree(max_depth=max_depth - 1))
        arg = draw(xi_tree(max_depth=max_depth - 1))
        return B.app(func, arg)
    elif choice == 4:
        # Lambda
        ty = B.universe(draw(st.integers(min_value=0, max_value=3)))
        body = draw(xi_tree(max_depth=max_depth - 1))
        return B.lam(ty, body)
    else:
        # Universe
        return B.universe(draw(st.integers(min_value=0, max_value=5)))


# Well-typed arithmetic expressions (always evaluate successfully)
@st.composite
def xi_arith(draw, max_depth=3):
    """Random well-typed arithmetic expression."""
    if max_depth <= 0:
        return B.int_lit(draw(st.integers(min_value=-1000, max_value=1000)))

    op = draw(st.sampled_from([PrimOp.INT_ADD, PrimOp.INT_SUB, PrimOp.INT_MUL]))
    lhs = draw(xi_arith(max_depth=max_depth - 1))
    rhs = draw(xi_arith(max_depth=max_depth - 1))

    # Avoid division by zero
    if op == PrimOp.INT_MUL:
        pass  # always safe
    return B.app(B.app(B.prim(op), lhs), rhs)


# ═══════════════════════════════════════════════════════════════
# PROPERTY 1: Serialization Roundtrip
# ═══════════════════════════════════════════════════════════════

class TestSerializationProperties:
    """Serialization invariants."""

    @given(node=xi_tree(max_depth=3))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_serialize_produces_valid_header(self, node):
        """All serialized bytes start with the Xi magic and version."""
        data = serialize(node)
        assert data[:2] == MAGIC
        assert data[2] == FORMAT_VERSION

    @given(node=xi_tree(max_depth=3))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_serialize_deterministic(self, node):
        """Serializing the same tree twice gives identical bytes."""
        assert serialize(node) == serialize(node)

    @given(node=xi_tree(max_depth=2))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_deserialize_roundtrip_structure(self, node):
        """deserialize(serialize(x)) produces a node with the same tag."""
        data = serialize(node)
        root = deserialize(data)
        assert root.tag == node.tag

    @given(val=st.integers(min_value=-2**31, max_value=2**31 - 1))
    @settings(max_examples=200)
    def test_int_roundtrip_exact(self, val):
        """Integer literals survive serialization roundtrip."""
        interp = Interpreter()
        node = B.int_lit(val)
        rt = deserialize(serialize(node))
        assert interp.run(rt) == val

    @given(s=st.text(min_size=0, max_size=100,
                     alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z'))))
    @settings(max_examples=200)
    def test_str_roundtrip_exact(self, s):
        """String literals survive serialization roundtrip."""
        interp = Interpreter()
        node = B.str_lit(s)
        rt = deserialize(serialize(node))
        assert interp.run(rt) == s


# ═══════════════════════════════════════════════════════════════
# PROPERTY 2: XiC Compression Roundtrip
# ═══════════════════════════════════════════════════════════════

class TestCompressionProperties:
    """XiC/0.1 invariants."""

    @given(val=st.integers(min_value=-2**31, max_value=2**31 - 1))
    @settings(max_examples=200)
    def test_xic_int_roundtrip(self, val):
        """XiC roundtrip preserves integer values."""
        node = B.int_lit(val)
        rt = decompress(compress(node))
        assert Interpreter().run(rt) == val

    @given(s=st.text(min_size=0, max_size=100,
                     alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z'))))
    @settings(max_examples=200)
    def test_xic_str_roundtrip(self, s):
        """XiC roundtrip preserves string values."""
        node = B.str_lit(s)
        rt = decompress(compress(node))
        assert Interpreter().run(rt) == s

    @given(expr=xi_arith(max_depth=2))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_xic_arith_roundtrip(self, expr):
        """XiC roundtrip preserves arithmetic evaluation."""
        interp = Interpreter()
        expected = interp.run(expr)
        rt = decompress(compress(expr))
        actual = interp.run(rt)
        assert expected == actual

    @given(node=xi_tree(max_depth=2))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_xic_preserves_tag(self, node):
        """XiC roundtrip preserves root tag."""
        rt = decompress(compress(node))
        assert rt.tag == node.tag


# ═══════════════════════════════════════════════════════════════
# PROPERTY 3: Optimizer Correctness
# ═══════════════════════════════════════════════════════════════

class TestOptimizerProperties:
    """Optimizer semantic preservation."""

    @given(expr=xi_arith(max_depth=3))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_constant_fold_preserves_value(self, expr):
        """constant_fold(e) evaluates to the same result as e."""
        interp = Interpreter()
        expected = interp.run(expr)
        folded = constant_fold(expr)
        actual = interp.run(folded)
        assert expected == actual

    @given(expr=xi_arith(max_depth=3))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_optimize_preserves_value(self, expr):
        """Full optimize pipeline preserves evaluation."""
        interp = Interpreter()
        expected = interp.run(expr)
        optimized, _ = optimize(expr)
        actual = interp.run(optimized)
        assert expected == actual

    @given(expr=xi_arith(max_depth=2))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_cse_idempotent(self, expr):
        """CSE is idempotent: cse(cse(x)) evaluates same as cse(x)."""
        interp = Interpreter()
        once = cse(expr)
        twice = cse(once)
        assert interp.run(once) == interp.run(twice)

    @given(expr=xi_arith(max_depth=3))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_fold_reduces_or_preserves_size(self, expr):
        """Constant folding never increases serialized size."""
        before = len(serialize(expr))
        folded = constant_fold(expr)
        after = len(serialize(folded))
        assert after <= before


# ═══════════════════════════════════════════════════════════════
# PROPERTY 4: Type Checker Soundness
# ═══════════════════════════════════════════════════════════════

class TestTypeCheckerProperties:
    """Type system soundness properties."""

    @given(val=st.integers(min_value=-2**31, max_value=2**31 - 1))
    @settings(max_examples=100)
    def test_int_always_typechecks(self, val):
        """Integer literals always have type Int."""
        tc = TypeChecker()
        ty = tc.infer([], B.int_lit(val))
        assert ty.data == "Int"

    @given(s=st.text(min_size=0, max_size=50,
                     alphabet=st.characters(whitelist_categories=('L', 'N'))))
    @settings(max_examples=100)
    def test_str_always_typechecks(self, s):
        """String literals always have type String."""
        tc = TypeChecker()
        ty = tc.infer([], B.str_lit(s))
        assert ty.data == "String"

    @given(expr=xi_arith(max_depth=3))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_arith_typechecks_as_int(self, expr):
        """Well-typed arithmetic expressions have type Int."""
        tc = TypeChecker()
        ty = tc.infer([], expr)
        assert ty.data == "Int"

    @given(expr=xi_arith(max_depth=3))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_well_typed_doesnt_crash(self, expr):
        """Well-typed programs evaluate without crashing."""
        interp = Interpreter()
        result = interp.run(expr)
        assert isinstance(result, int)


# ═══════════════════════════════════════════════════════════════
# PROPERTY 5: Content Hash Determinism
# ═══════════════════════════════════════════════════════════════

class TestHashProperties:
    """Content-addressed hashing invariants."""

    @given(val=st.integers(min_value=-2**31, max_value=2**31 - 1))
    @settings(max_examples=200)
    def test_hash_deterministic(self, val):
        """Same value → same hash."""
        a = B.int_lit(val)
        b = B.int_lit(val)
        assert a.content_hash() == b.content_hash()

    @given(a=st.integers(min_value=-1000, max_value=1000),
           b=st.integers(min_value=-1000, max_value=1000))
    @settings(max_examples=200)
    def test_different_values_different_hash(self, a, b):
        """Different values → different hash (with overwhelming probability)."""
        assume(a != b)
        na = B.int_lit(a)
        nb = B.int_lit(b)
        assert na.content_hash() != nb.content_hash()

    @given(expr=xi_arith(max_depth=2))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_hash_length_always_32(self, expr):
        """Content hash is always 32 bytes (SHA-256)."""
        assert len(expr.content_hash()) == 32


# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, '-v', '--tb=short']))
