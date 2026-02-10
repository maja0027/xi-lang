# API: xi_multicore.py — Multi-Core Parallel Engine

Python simulation of the hardware multi-core graph reduction engine with spark-based parallelism.

## Classes

### `MultiCoreEngine`
```python
class MultiCoreEngine:
    def __init__(n_cores: int = 4)
    def run(node: Node) → any
    def run_with_stats() → tuple[any, dict]
```

### `SparkPool`
```python
class SparkPool:
    def push(addr: int)      # Add parallel work
    def pop() → int | None   # Get work (local)
    def steal() → int | None # Steal from other core
```

## Statistics
```python
{
    'total_reductions': int,
    'per_core_reductions': list[int],
    'sparks_created': int,
    'sparks_stolen': int,
    'max_parallelism': int
}
```

## Usage
```python
from xi_multicore import MultiCoreEngine
from xi_compiler import Compiler

prog = Compiler().compile_expr("(2 + 3) * (4 + 5)")
engine = MultiCoreEngine(n_cores=4)
result = engine.run(prog)
assert result == 45
```
