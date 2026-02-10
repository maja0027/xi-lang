# API: xi_match.py — Pattern Matching Interpreter

The main evaluation engine. Handles all four reduction rules (β, δ, ι, μ) plus constructor-based pattern matching.

## Classes

### `MatchInterpreter`
```python
class MatchInterpreter:
    def run(node: Node) → any              # Evaluate to final value
    def step(node: Node) → Node            # Single reduction step
    def trace(node: Node) → list[Node]     # All intermediate steps
    def is_value(node: Node) → bool        # Check if in normal form
```

### `Constructor`
```python
class Constructor:
    name: str         # e.g., "Succ", "Cons", "True"
    index: int        # Constructor tag (0-based)
    args: list[Node]  # Applied arguments
```

## Functions

### `nat_to_int(interp, node) → int`
Converts a Peano natural (Succ(Succ(Zero))) to a Python integer.

### `int_to_nat(n: int) → Node`
Converts a Python integer to a Peano natural Node.

### `list_to_nodes(interp, items) → Node`
Builds a Xi linked list from Python values.

## Supported Reductions

| Rule | Pattern | Result |
|------|---------|--------|
| β | `(λA. body) arg` | `body[0 := arg]` |
| δ | `#[op] lit₁ lit₂` | Evaluated result |
| ι | `match (Cᵢ args) { ... }` | Selected branch applied |
| μ | `μT. body` | `body[0 := μT. body]` |

## Example
```python
from xi import make_app, make_lam, make_int, make_var, make_prim, PrimOp
from xi_match import MatchInterpreter

interp = MatchInterpreter()
# (λx. x * x) 7
prog = make_app(
    make_lam(None, make_prim(PrimOp.INT_MUL, make_var(0), make_var(0))),
    make_int(7)
)
assert interp.run(prog) == 49
```
