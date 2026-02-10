# Interpreter Architecture

The Xi reference interpreter is a graph reduction engine written in Python. It evaluates Xi binary programs by repeatedly applying reduction rules until reaching a normal form.

---

## 1. Components

```
┌──────────────┐    ┌──────────────┐    ┌───────────────┐
│ xi.py        │    │ xi_match.py  │    │ xi_stdlib.py  │
│ Core types   │───▶│ Interpreter  │◀───│ Standard lib  │
│ Serialize    │    │ β/δ/ι/μ      │    │ Nat,Bool,List │
│ Deserialize  │    │ Pattern match│    │ Option,Result │
└──────────────┘    └──────────────┘    └───────────────┘
        │                  │
        ▼                  ▼
┌──────────────┐    ┌──────────────┐
│ Node (DAG)   │    │ Constructor  │
│ Tag, children│    │ name, index  │
│ data, hash   │    │ args list    │
└──────────────┘    └──────────────┘
```

## 2. Node Representation

```python
class Node:
    tag: Tag          # 0-9 (LAM, APP, PI, SIG, UNI, FIX, IND, EQ, EFF, PRIM)
    children: list    # Child nodes (shared references)
    data: any         # Payload (int, str, PrimOp, de Bruijn index)
```

Nodes are immutable. Reduction produces new nodes rather than mutating existing ones. This enables safe sharing — the same `Node` object can appear as a child of multiple parents.

## 3. Evaluation Strategy

The interpreter uses **lazy evaluation with weak head normal form (WHNF)**:

1. To evaluate an expression, reduce it to WHNF
2. WHNF means the outermost node is a value (lambda, literal, constructor)
3. Arguments are not evaluated until needed (call-by-need)

The `MatchInterpreter.run()` method:

```python
def run(self, node):
    while True:
        if is_value(node):
            return node
        node = step(node)  # Apply one reduction rule
```

## 4. Reduction Rules

### β-reduction (Lambda Application)
```python
if node.tag == APP and node.children[0].tag == LAM:
    body = node.children[0].children[1]
    arg = node.children[1]
    return substitute(body, 0, arg)
```

### μ-reduction (Fixpoint Unfolding)
```python
if node.tag == FIX:
    body = node.children[1]
    return substitute(body, 0, node)  # Self-reference
```

### δ-reduction (Primitive Evaluation)
```python
if node.tag == APP and is_fully_applied_prim(node):
    op = get_prim_op(node)
    args = collect_args(node)
    return eval_prim(op, args)  # e.g., ADD(2, 3) → 5
```

### ι-reduction (Pattern Matching)
```python
if node.tag == IND:
    scrutinee = evaluate(node.children[0])
    if isinstance(scrutinee, Constructor):
        branch = node.children[scrutinee.index + 1]
        return apply_args(branch, scrutinee.args)
```

## 5. De Bruijn Indices

Variables use de Bruijn indices instead of names. Index 0 refers to the nearest enclosing binder, 1 to the next, etc.

```
λx. λy. x  =  λ. λ. #[var 1]
λx. λy. y  =  λ. λ. #[var 0]
```

Substitution shifts indices to maintain correctness:
```python
def substitute(node, index, replacement):
    if node is VAR:
        if node.data == index: return replacement
        if node.data > index: return VAR(node.data - 1)
    return Node(node.tag, [substitute(c, index, replacement) for c in node.children])
```

## 6. Performance Characteristics

The Python interpreter prioritizes correctness and clarity over speed:

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| β-reduction | O(n) | Substitution traverses body |
| δ-reduction | O(1) | Direct primitive evaluation |
| ι-reduction | O(k) | k = number of constructor args |
| μ-reduction | O(n) | Substitution traverses body |

For performance-critical execution, the multi-core hardware engine (see `docs/arch/hardware.md`) performs reductions in O(1) amortized via graph rewriting.
