# Optimizer Architecture

The Xi optimizer performs graph-level transformations that reduce program size and execution time while preserving semantics.

---

## 1. Optimization Passes

### 1.1 Constant Folding

Evaluates compile-time computable expressions:

```
2 + 3        →  5
4 * (2 + 1)  →  12
True && x    →  x
0 * x        →  0
```

Rules applied recursively bottom-up through the graph.

### 1.2 Common Subexpression Elimination (CSE)

Identifies structurally identical subgraphs and shares them:

```
(f (2+3)) + (g (2+3))
→ let t = 2+3 in (f t) + (g t)
```

CSE leverages content addressing — nodes with the same hash are already shared at the binary level. The optimizer extends this to the AST level by memoizing node hashes during traversal.

### 1.3 Dead Code Elimination (DCE)

Removes unreachable subgraphs:

```
let unused = expensive_computation in 42
→ 42
```

A node is dead if:
- It has no path from the root
- Its only reference is from a let-binding that is never used
- It is an unreachable match branch (after constant folding)

### 1.4 Identity Elimination

Simplifies trivial expressions:

```
x + 0  →  x
x * 1  →  x
x - 0  →  x
```

---

## 2. Implementation

```python
def optimize(node, max_passes=10):
    stats = {}
    for i in range(max_passes):
        n1, s1 = constant_fold(node)
        n2, s2 = cse(n1)
        n3, s3 = dce(n2)
        stats.update(s1, s2, s3)
        if n3 == node:
            break  # Fixed point reached
        node = n3
    return node, stats
```

The optimizer iterates until no more changes are made (fixed-point) or the iteration limit is reached.

## 3. Statistics

The optimizer reports what it did:

```python
{
    'constant_fold': 3,    # Nodes folded
    'cse': 2,              # Subexpressions shared
    'dce': 1,              # Dead nodes removed
    'passes': 2,           # Optimization rounds
    'original_size': 15,   # Nodes before
    'optimized_size': 9    # Nodes after
}
```

## 4. Correctness

The optimizer preserves operational semantics:

```
∀ node: run(optimize(node)) ≡ run(node)
```

This is verified by property-based tests (Hypothesis) that generate random Xi ASTs, optimize them, and check that evaluation produces the same result.

## 5. Future Optimizations

- **Inlining:** Replace function calls with their bodies (size-guided)
- **Specialization:** Generate monomorphic versions of polymorphic functions
- **Strictness analysis:** Convert lazy evaluation to strict where safe
- **Tail call optimization:** Convert tail-recursive μ to loops
- **Deforestation:** Fuse producer-consumer pairs to avoid intermediate data structures
