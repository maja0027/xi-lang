# PROMPT_SPEC — Xi-IR Generation Contract

You are generating Xi-IR JSON. Follow this spec exactly.

## Format

```json
{
  "version": "xi-ir-v1",
  "root": { <NODE> },
  "metadata": { "hash": "<sha256>", "node_count": <int>, "max_depth": <int> }
}
```

## Node Schema

```json
{
  "tag": "<TAG>",
  "children": [ <NODE>, ... ],
  "data": <value>,
  "prim_op": "<PRIMOP>"
}
```

### Tags (exactly 10)

| tag | meaning | children | data/prim_op |
|-----|---------|----------|-------------|
| `lam` | λ abstraction | `[param_type, body]` | — |
| `app` | application | `[function, argument]` | — |
| `pi` | Π type | `[param_type, result_type]` | — |
| `sig` | Σ type | `[first_type, second_type]` | — |
| `uni` | universe | `[]` | `data: <level>` |
| `fix` | fixpoint | `[type, body]` | — |
| `ind` | inductive | `[scrutinee, branch0, branch1, ...]` | — |
| `eq` | equality | `[type, left, right]` | — |
| `eff` | effect | `[inner_type]` | — |
| `prim` | primitive | `[]` or `[child, ...]` | `prim_op` or `data` |

### Primitive Operations

| prim_op | args | result | example |
|---------|------|--------|---------|
| `var` | 0 | — | `{"tag":"prim","prim_op":"var","data":0}` |
| `int_lit` | 0 | Int | `{"tag":"prim","prim_op":"int_lit","data":42}` |
| `str_lit` | 0 | String | `{"tag":"prim","prim_op":"str_lit","data":"hello"}` |
| `bool_true` | 0 | Bool | `{"tag":"prim","prim_op":"bool_true"}` |
| `bool_false` | 0 | Bool | `{"tag":"prim","prim_op":"bool_false"}` |
| `int_add` | 2 | Int | children: `[left, right]` |
| `int_sub` | 2 | Int | children: `[left, right]` |
| `int_mul` | 2 | Int | children: `[left, right]` |
| `int_div` | 2 | Int | children: `[left, right]` |
| `int_mod` | 2 | Int | children: `[left, right]` |
| `int_eq` | 2 | Bool | children: `[left, right]` |
| `int_lt` | 2 | Bool | children: `[left, right]` |
| `int_gt` | 2 | Bool | children: `[left, right]` |
| `bool_not` | 1 | Bool | children: `[operand]` |
| `bool_and` | 2 | Bool | children: `[left, right]` |
| `bool_or` | 2 | Bool | children: `[left, right]` |
| `str_concat` | 2 | String | children: `[left, right]` |
| `str_len` | 1 | Int | children: `[string]` |
| `print` | 1 | IO a | children: `[value]` |

### Variables

Variables use de Bruijn indices. `data: 0` = innermost binder, `data: 1` = next outer, etc.

```
λx. λy. x   →  lam(_, lam(_, var(1)))
λx. λy. y   →  lam(_, lam(_, var(0)))
```

## Examples

### `42`
```json
{"tag": "prim", "prim_op": "int_lit", "data": 42}
```

### `2 + 3`
```json
{"tag": "prim", "prim_op": "int_add", "children": [
  {"tag": "prim", "prim_op": "int_lit", "data": 2},
  {"tag": "prim", "prim_op": "int_lit", "data": 3}
]}
```

### `λx. x + 1`
```json
{"tag": "lam", "children": [
  {"tag": "prim", "prim_op": "int_lit", "data": 0},
  {"tag": "prim", "prim_op": "int_add", "children": [
    {"tag": "prim", "prim_op": "var", "data": 0},
    {"tag": "prim", "prim_op": "int_lit", "data": 1}
  ]}
]}
```

### `(λx. x * x) 7`
```json
{"tag": "app", "children": [
  {"tag": "lam", "children": [
    {"tag": "prim", "prim_op": "int_lit", "data": 0},
    {"tag": "prim", "prim_op": "int_mul", "children": [
      {"tag": "prim", "prim_op": "var", "data": 0},
      {"tag": "prim", "prim_op": "var", "data": 0}
    ]}
  ]},
  {"tag": "prim", "prim_op": "int_lit", "data": 7}
]}
```

### `if a < b then a else b` (min function body, a=var1, b=var0)
```json
{"tag": "ind", "children": [
  {"tag": "prim", "prim_op": "int_lt", "children": [
    {"tag": "prim", "prim_op": "var", "data": 1},
    {"tag": "prim", "prim_op": "var", "data": 0}
  ]},
  {"tag": "prim", "prim_op": "var", "data": 1},
  {"tag": "prim", "prim_op": "var", "data": 0}
]}
```

## Validation Rules

1. Every node MUST have a `tag` field
2. `tag` MUST be one of the 10 listed values
3. `children` MUST be an array (empty `[]` if no children)
4. `prim` nodes MUST have either `prim_op` or `data`
5. `var` nodes MUST have `data` as non-negative integer
6. `lam` nodes MUST have exactly 2 children
7. `app` nodes MUST have exactly 2 children

## Validation CLI

```bash
# Validate your generated JSON
echo '{"version":"xi-ir-v1","root":...}' | xi decode --validate

# Hash for dedup
xi hash -e "2 + 3"

# Full encode from source
xi encode --json -e "λx. x + 1"
```

## Anti-Patterns

DO NOT:
- Use string names for variables (use de Bruijn indices)
- Nest `prim_op` values that aren't in the table above
- Omit `version` field from top-level
- Use `null` for children (use `[]`)
- Generate `tag` values not in the 10-tag set
