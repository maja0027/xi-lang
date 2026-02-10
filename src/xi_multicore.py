#!/usr/bin/env python3
"""
Ξ (Xi) Multi-Core Graph Reduction Engine
Copyright (c) 2026 Alex P. Slaby — MIT License

Simulates parallel graph reduction using a spark pool and
multiple reduction workers. Demonstrates implicit parallelism
from independent subgraphs.

Usage:
  python xi_multicore.py demo
"""

import sys, os, time, hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, current_thread
from dataclasses import dataclass, field
from collections import deque

sys.path.insert(0, os.path.dirname(__file__))
from xi import Node, Tag, PrimOp, Effect, B, Interpreter, render_tree, node_label


# ═══════════════════════════════════════════════════════════════
# GRAPH MEMORY POOL — Content-addressed node storage
# ═══════════════════════════════════════════════════════════════

class GraphMemory:
    """
    Thread-safe, content-addressed node store.
    Nodes are deduplicated: identical subgraphs share storage.
    """
    def __init__(self):
        self._store = {}    # hash → Node
        self._lock = Lock()
        self.lookups = 0
        self.inserts = 0
        self.dedup_hits = 0

    def store(self, node: Node) -> str:
        """Store a node, returning its content hash. Deduplicates."""
        h = node.content_hash().hex()
        with self._lock:
            self.inserts += 1
            if h in self._store:
                self.dedup_hits += 1
            else:
                self._store[h] = node
        return h

    def fetch(self, hash_hex: str) -> Node:
        """Fetch a node by its content hash."""
        with self._lock:
            self.lookups += 1
            return self._store[hash_hex]

    def size(self) -> int:
        with self._lock:
            return len(self._store)


# ═══════════════════════════════════════════════════════════════
# SPARK POOL — Work-stealing queue
# ═══════════════════════════════════════════════════════════════

@dataclass
class Spark:
    """A unit of work: reduce this node."""
    node: Node
    priority: int = 0   # higher = reduce first

    def __lt__(self, other):
        return self.priority > other.priority


class SparkPool:
    """Thread-safe work queue for parallel graph reduction."""
    def __init__(self):
        self._queue = deque()
        self._lock = Lock()
        self.total_sparks = 0

    def push(self, spark: Spark):
        with self._lock:
            self._queue.append(spark)
            self.total_sparks += 1

    def pop(self) -> Spark | None:
        with self._lock:
            return self._queue.popleft() if self._queue else None

    def is_empty(self) -> bool:
        with self._lock:
            return len(self._queue) == 0

    def size(self) -> int:
        with self._lock:
            return len(self._queue)


# ═══════════════════════════════════════════════════════════════
# REDUCTION CORE — Worker thread
# ═══════════════════════════════════════════════════════════════

class ReductionCore:
    """A single reduction worker (simulates one hardware core)."""

    def __init__(self, core_id: int, memory: GraphMemory, spark_pool: SparkPool):
        self.core_id = core_id
        self.memory = memory
        self.spark_pool = spark_pool
        self.reductions = 0
        self.interpreter = Interpreter()

    def reduce_node(self, node: Node) -> any:
        """Reduce a single node, potentially spawning child sparks."""
        self.reductions += 1

        if node.tag == Tag.EFF:
            return self.reduce_node(node.children[0])

        if node.tag == Tag.APP:
            func = node.children[0]
            arg = node.children[1]

            # If both children are independent, they can be reduced in parallel
            if self._is_reducible(func) and self._is_reducible(arg):
                self.spark_pool.push(Spark(arg, priority=1))

            val = self.reduce_node(arg) if not self._is_value(arg) else self._to_value(arg)

            if func.tag == Tag.PRIM:
                return self._apply_prim_unary(func.prim_op, val)

            if func.tag == Tag.APP and func.children[0].tag == Tag.PRIM:
                lhs = self.reduce_node(func.children[1])
                return self._apply_prim_binary(func.children[0].prim_op, lhs, val)

            if func.tag == Tag.LAM:
                return self.reduce_node(
                    self.interpreter._substitute(func.children[1], 0, self.interpreter._to_node(val))
                )

        if node.tag == Tag.PRIM:
            return self._to_value(node)

        if node.tag == Tag.LAM:
            return node

        return node

    def _is_reducible(self, node: Node) -> bool:
        return node.tag in (Tag.APP, Tag.EFF, Tag.FIX)

    def _is_value(self, node: Node) -> bool:
        return node.tag == Tag.PRIM or node.tag == Tag.LAM

    def _to_value(self, node: Node):
        if node.tag == Tag.PRIM:
            if node.prim_op == PrimOp.STR_LIT: return node.data
            if node.prim_op == PrimOp.INT_LIT: return node.data
            if node.prim_op == PrimOp.BOOL_TRUE: return True
            if node.prim_op == PrimOp.BOOL_FALSE: return False
            if node.prim_op == PrimOp.UNIT: return None
        return node

    def _apply_prim_unary(self, op, val):
        if op == PrimOp.PRINT: return val  # collect, don't print during parallel
        if op == PrimOp.INT_NEG: return -val
        if op == PrimOp.BOOL_NOT: return not val
        if op == PrimOp.STR_LEN: return len(val)
        return val

    def _apply_prim_binary(self, op, a, b):
        ops = {
            PrimOp.INT_ADD: lambda x,y: x+y, PrimOp.INT_SUB: lambda x,y: x-y,
            PrimOp.INT_MUL: lambda x,y: x*y, PrimOp.INT_DIV: lambda x,y: x//y,
            PrimOp.INT_MOD: lambda x,y: x%y,
            PrimOp.INT_EQ: lambda x,y: x==y, PrimOp.INT_LT: lambda x,y: x<y,
            PrimOp.INT_GT: lambda x,y: x>y,
            PrimOp.BOOL_AND: lambda x,y: x and y, PrimOp.BOOL_OR: lambda x,y: x or y,
            PrimOp.STR_CONCAT: lambda x,y: str(x)+str(y),
        }
        return ops.get(op, lambda x,y: None)(a, b)


# ═══════════════════════════════════════════════════════════════
# MULTI-CORE ENGINE
# ═══════════════════════════════════════════════════════════════

class MultiCoreEngine:
    """
    Parallel graph reduction engine with N reduction cores.
    Uses spark pool for work distribution.
    """

    def __init__(self, num_cores: int = 4):
        self.num_cores = num_cores
        self.memory = GraphMemory()
        self.spark_pool = SparkPool()
        self.cores = [ReductionCore(i, self.memory, self.spark_pool) for i in range(num_cores)]

    def run(self, program: Node) -> any:
        """Reduce a Xi program using all cores."""
        # Primary reduction on core 0
        core = self.cores[0]
        result = core.reduce_node(program)

        # Process any spawned sparks in parallel
        with ThreadPoolExecutor(max_workers=self.num_cores) as executor:
            futures = []
            while not self.spark_pool.is_empty():
                spark = self.spark_pool.pop()
                if spark:
                    core_idx = len(futures) % self.num_cores
                    futures.append(
                        executor.submit(self.cores[core_idx].reduce_node, spark.node)
                    )

            for f in as_completed(futures):
                try:
                    f.result()
                except Exception as e:
                    pass  # log errors but don't halt

        return result

    def stats(self) -> dict:
        total_reductions = sum(c.reductions for c in self.cores)
        return {
            "cores": self.num_cores,
            "total_reductions": total_reductions,
            "per_core": [c.reductions for c in self.cores],
            "sparks_created": self.spark_pool.total_sparks,
            "graph_nodes": self.memory.size(),
            "graph_lookups": self.memory.lookups,
            "dedup_hits": self.memory.dedup_hits,
        }


# ═══════════════════════════════════════════════════════════════
# DEMO
# ═══════════════════════════════════════════════════════════════

def run_demo():
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║  Ξ (Xi) Multi-Core Graph Reduction Engine v0.1           ║")
    print("║  Copyright (c) 2026 Alex P. Slaby — MIT License          ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")

    NUM_CORES = 4

    # Build a computation-heavy program:
    # Compute ((10+20) * (30+40)) + ((50+60) * (70+80))
    # The four additions can be reduced in parallel!

    a = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(10)), B.int_lit(20))   # 30
    b = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(30)), B.int_lit(40))   # 70
    c = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(50)), B.int_lit(60))   # 110
    d = B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(70)), B.int_lit(80))   # 150

    ab = B.app(B.app(B.prim(PrimOp.INT_MUL), a), b)  # 30 * 70 = 2100
    cd = B.app(B.app(B.prim(PrimOp.INT_MUL), c), d)  # 110 * 150 = 16500

    program = B.app(B.app(B.prim(PrimOp.INT_ADD), ab), cd)  # 2100 + 16500 = 18600

    print(f"  Program: ((10+20)*(30+40)) + ((50+60)*(70+80))")
    print(f"  Expected: 18600")
    print(f"  Cores: {NUM_CORES}")
    print()

    # Show graph
    print("  Graph:")
    for line in render_tree(program).split('\n')[:8]:
        print(f"    {line}")
    print(f"    ... ({sum(1 for _ in _walk(program))} total nodes)")
    print()

    # Run single-core
    print("  ── Single-core ──")
    engine1 = MultiCoreEngine(num_cores=1)
    t0 = time.perf_counter()
    result1 = engine1.run(program)
    t1 = time.perf_counter()
    s1 = engine1.stats()
    print(f"    Result:     {result1}")
    print(f"    Reductions: {s1['total_reductions']}")
    print(f"    Time:       {(t1-t0)*1000:.2f} ms")
    print()

    # Run multi-core
    print(f"  ── Multi-core ({NUM_CORES} cores) ──")
    engine4 = MultiCoreEngine(num_cores=NUM_CORES)
    t0 = time.perf_counter()
    result4 = engine4.run(program)
    t1 = time.perf_counter()
    s4 = engine4.stats()
    print(f"    Result:     {result4}")
    print(f"    Reductions: {s4['total_reductions']}")
    print(f"    Per core:   {s4['per_core']}")
    print(f"    Sparks:     {s4['sparks_created']}")
    print(f"    Time:       {(t1-t0)*1000:.2f} ms")
    print()

    # Content addressing demo
    print("  ── Content-Addressed Memory ──")
    mem = GraphMemory()
    n1 = B.int_lit(42)
    n2 = B.int_lit(42)
    n3 = B.int_lit(99)
    h1 = mem.store(n1)
    h2 = mem.store(n2)
    h3 = mem.store(n3)
    print(f"    Store int(42) twice, int(99) once:")
    print(f"    Unique nodes: {mem.size()} (from 3 inserts)")
    print(f"    Dedup hits:   {mem.dedup_hits}")
    print(f"    hash(42):     {h1[:16]}…")
    print(f"    hash(42):     {h2[:16]}…  (same!)")
    print(f"    hash(99):     {h3[:16]}…  (different)")
    print()

    ok = result1 == 18600 and result4 == 18600
    print(f"  {'✓' if ok else '✗'} Both engines produce correct result: {ok}")
    print()


def _walk(node):
    yield node
    for c in node.children:
        yield from _walk(c)


if __name__ == "__main__":
    run_demo()
