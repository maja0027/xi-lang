# API: xi_optimizer.py — Graph Optimizer

Performs compile-time graph transformations to reduce size and improve execution speed.

## Functions

### `optimize(node: Node, max_passes: int = 10) → tuple[Node, dict]`
Applies all optimization passes until fixed point. Returns (optimized_node, statistics).

### `constant_fold(node: Node) → tuple[Node, dict]`
Evaluates compile-time computable subexpressions.

### `cse(node: Node) → tuple[Node, dict]`
Common subexpression elimination via hash-based deduplication.

### `dce(node: Node) → tuple[Node, dict]`
Dead code elimination — removes unreachable subtrees.

## Statistics Dict
```python
{
    'constant_fold': int,   # Nodes folded
    'cse': int,             # Subexpressions shared
    'dce': int,             # Dead nodes removed
    'passes': int,          # Optimization rounds
    'original_size': int,
    'optimized_size': int
}
```

## Example
```python
from xi_optimizer import optimize
from xi_compiler import Compiler

node = Compiler().compile_expr("(2 + 3) * (4 + 5)")
opt, stats = optimize(node)
# stats: {'constant_fold': 3, 'original_size': 7, 'optimized_size': 1}
# opt is just the literal node 45
```
