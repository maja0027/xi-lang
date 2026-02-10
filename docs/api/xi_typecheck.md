# API: xi_typecheck.py — Type Checker

Bidirectional type checker with Hindley-Milner inference for Xi programs.

## Classes

### `TypeChecker`
```python
class TypeChecker:
    def infer(ctx: Context, node: Node) → Type   # Infer type
    def check(ctx: Context, node: Node, ty: Type) # Check against expected type
```

### `Context`
```python
class Context:
    bindings: list[Type]  # De Bruijn indexed type environment
```

### Type Representations
- `TInt`, `TBool`, `TString` — base types
- `TArrow(param, result)` — function type `A → B`
- `TPi(param, body)` — dependent function type `Π(x:A). B`
- `TUniverse(level)` — universe `𝒰ᵢ`
- `TypeVar(id)` — unification variable `?α`

## Functions

### `type_to_str(ty: Type) → str`
Pretty-prints a type: `Int → Int → Bool`

### `resolve_type(ty: Type) → Type`
Follows the unification chain, replacing all `TypeVar` with their solutions.

## Exceptions

- `TypeErr(msg)` — type mismatch, occurs check failure, or unification failure

## HM Inference

The type checker introduces `TypeVar` for unannotated lambda parameters and resolves them through unification:

```python
tc = TypeChecker()
ctx = Context()

# λx. x + 1 → infers x : Int, result : Int → Int
node = Compiler().compile_expr("λx. x + 1")
ty = tc.infer(ctx, node)
assert type_to_str(resolve_type(ty)) == "Int → Int"
```
