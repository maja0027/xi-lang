#!/usr/bin/env python3
"""
Ξ (Xi) Benchmarks
Copyright (c) 2026 Alex P. Slaby — MIT License

Simple performance benchmarks for the reference implementation.

Usage:
  python tests/test_bench.py
  pytest tests/test_bench.py -v  (skipped by default, run with --benchmark)
"""

import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from xi import Node, Tag, PrimOp, Effect, B, serialize, Interpreter


def bench(name, fn, iterations=1000):
    """Run a benchmark and report results."""
    # Warmup
    for _ in range(10):
        fn()

    t0 = time.perf_counter()
    for _ in range(iterations):
        fn()
    t1 = time.perf_counter()

    total_ms = (t1 - t0) * 1000
    per_op = total_ms / iterations
    ops_sec = iterations / (t1 - t0)
    print(f"  {name:40s} {per_op:8.3f} ms/op  ({ops_sec:,.0f} ops/s)")
    return per_op


def run_benchmarks():
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║  Ξ (Xi) Benchmarks                                       ║")
    print("║  Copyright (c) 2026 Alex P. Slaby — MIT License           ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")

    interp = Interpreter()

    # ── Node construction ──
    print("  ── Node Construction ──")
    bench("int_lit(42)", lambda: B.int_lit(42), 10000)
    bench("str_lit('hello')", lambda: B.str_lit("hello"), 10000)
    bench("app(add, 3, 5)", lambda: B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(3)), B.int_lit(5)), 10000)
    bench("lam(Int, var(0))", lambda: B.lam(B.universe(0), B.var(0)), 10000)
    print()

    # ── Content hashing ──
    print("  ── Content Hashing (SHA-256) ──")
    small = B.int_lit(42)
    medium = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(3)), B.int_lit(5))
    deep = B.int_lit(0)
    for i in range(20):
        deep = B.app(B.prim(PrimOp.INT_NEG), deep)
    bench("hash(int_lit)", lambda: small.content_hash(), 5000)
    bench("hash(add(3,5))", lambda: medium.content_hash(), 5000)
    bench("hash(depth=20)", lambda: deep.content_hash(), 1000)
    print()

    # ── Serialization ──
    print("  ── Serialization ──")
    hello = B.effect(B.app(B.prim(PrimOp.PRINT), B.str_lit("Hello!")), Effect.IO)
    bench("serialize(hello_world)", lambda: serialize(hello), 5000)
    bench("serialize(add(3,5))", lambda: serialize(medium), 5000)
    bench("serialize(depth=20)", lambda: serialize(deep), 1000)
    print()

    # ── Interpretation ──
    print("  ── Interpretation ──")
    add_expr = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(3)), B.int_lit(5))
    mul_expr = B.app(B.app(B.prim(PrimOp.INT_MUL), B.int_lit(6)), B.int_lit(7))
    complex_expr = B.app(B.app(B.prim(PrimOp.INT_MUL),
        B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(3)), B.int_lit(5))),
        B.int_lit(2))
    double_21 = B.app(
        B.lam(B.universe(0), B.app(B.app(B.prim(PrimOp.INT_ADD), B.var(0)), B.var(0))),
        B.int_lit(21))

    bench("eval: 3 + 5", lambda: Interpreter().run(add_expr), 5000)
    bench("eval: 6 * 7", lambda: Interpreter().run(mul_expr), 5000)
    bench("eval: (3+5)*2", lambda: Interpreter().run(complex_expr), 5000)
    bench("eval: (λx.x+x)(21)", lambda: Interpreter().run(double_21), 5000)

    # Chain of additions: 1+1+1+...+1 (N times)
    for n in [10, 50, 100]:
        chain = B.int_lit(0)
        for _ in range(n):
            chain = B.app(B.app(B.prim(PrimOp.INT_ADD), chain), B.int_lit(1))
        iters = max(100, 5000 // n)
        bench(f"eval: chain add ×{n}", lambda c=chain: Interpreter().run(c), iters)
    print()

    # ── Type checking ──
    print("  ── Type Checking ──")
    from xi_typecheck import TypeChecker, Context, TYPE_INT
    tc = TypeChecker()
    ctx = Context()
    lam = B.lam(TYPE_INT, B.app(B.app(B.prim(PrimOp.INT_ADD), B.var(0)), B.var(0)))
    add_typed = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(3)), B.int_lit(5))
    double_typed = B.app(
        B.lam(TYPE_INT, B.app(B.app(B.prim(PrimOp.INT_ADD), B.var(0)), B.var(0))),
        B.int_lit(21))

    bench("typecheck: int_lit", lambda: TypeChecker().infer(Context(), B.int_lit(42)), 5000)
    bench("typecheck: 3 + 5", lambda: TypeChecker().infer(Context(), add_typed), 5000)
    bench("typecheck: λx.x+x", lambda: TypeChecker().infer(Context(), lam), 2000)
    bench("typecheck: (λx.x+x)(21)", lambda: TypeChecker().infer(Context(), double_typed), 2000)
    print()

    # ── Compilation ──
    print("  ── Compilation ──")
    from xi_compiler import Compiler
    compiler = Compiler()
    bench('compile: "3 + 5"', lambda: compiler.compile("3 + 5"), 5000)
    bench('compile: "(3 + 5) * 2"', lambda: compiler.compile("(3 + 5) * 2"), 5000)
    bench('compile: lambda', lambda: compiler.compile("fun (x : Int) . x + x"), 3000)
    print()


if __name__ == "__main__":
    run_benchmarks()
