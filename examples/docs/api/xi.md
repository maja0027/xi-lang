# API: xi.py — Core Types & Serialization

The foundation module defining Xi's node types, tags, and binary serialization.

## Types

### `Tag` (Enum)
```python
class Tag(IntEnum):
    LAM = 0    # λ  Lambda abstraction
    APP = 1    # @  Application
    PI  = 2    # Π  Dependent function type
    SIG = 3    # Σ  Dependent pair type
    UNI = 4    # 𝒰  Universe
    FIX = 5    # μ  Fixed point
    IND = 6    # ι  Inductive type
    EQ  = 7    # ≡  Propositional equality
    EFF = 8    # !  Effect annotation
    PRIM = 9   # #  Primitive
```

### `PrimOp` (Enum)
Built-in operations: `VAR`, `PRINT`, `STR_LIT`, `INT_LIT`, `INT_ADD`, `INT_SUB`, `INT_MUL`, `INT_DIV`, `INT_MOD`, `INT_EQ`, `INT_LT`, `INT_GT`, `BOOL_NOT`, `BOOL_AND`, `BOOL_OR`, `STR_CONCAT`, `STR_LEN`, `INT_NEG`.

### `Node`
```python
class Node:
    tag: Tag              # Node type (0-9)
    children: list[Node]  # Child references (shared)
    data: any             # Payload (int, str, PrimOp, etc.)
```

## Functions

### `serialize(node: Node) → bytes`
Serializes a Node graph to Xi binary format. Produces a depth-first encoding with back-references for shared subtrees.

### `make_lam(param_type, body) → Node`
### `make_app(func, arg) → Node`
### `make_int(n: int) → Node`
### `make_var(index: int) → Node`
### `make_prim(op: PrimOp, *children) → Node`
Convenience constructors for common node patterns.

## Example
```python
from xi import Node, Tag, PrimOp, serialize

# Build: (λx. x + 1) applied to 41
inc = make_lam(make_int(0), make_prim(PrimOp.INT_ADD, make_var(0), make_int(1)))
prog = make_app(inc, make_int(41))
binary = serialize(prog)  # → bytes
```
