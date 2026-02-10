# PROMPT_PATCH — Xi Structural Diff & Patch Contract

You are modifying Xi programs via structural patches. Follow this protocol.

## Patch Format

A patch is a JSON array of operations:

```json
{
  "operations": [
    {"op": "replace", "path": "root.children[1]", "old_hash": "abc...", "new": { <NODE> }},
    {"op": "modify_data", "path": "root.children[0]", "old": 2, "new": 3},
    {"op": "insert", "path": "root.children[2]", "new": { <NODE> }},
    {"op": "delete", "path": "root.children[1]", "old_hash": "def..."}
  ]
}
```

## Operations

### `replace`
Replace an entire subtree at the given path.
```json
{"op": "replace", "path": "root.children[0]", "old_hash": "<sha256>", "new": { <NODE> }}
```
- `path`: dot-separated path from root (e.g. `root.children[0].children[1]`)
- `old_hash`: SHA-256 of the node being replaced (for verification)
- `new`: the replacement node (full Xi-IR node)

### `modify_data`
Change the data field of a node without changing structure.
```json
{"op": "modify_data", "path": "root", "old": 42, "new": 43}
```
Use for: changing literals, changing prim_ops, changing var indices.

### `insert`
Insert a new child at the given index.
```json
{"op": "insert", "path": "root.children[2]", "new": { <NODE> }}
```

### `delete`
Remove a child at the given index.
```json
{"op": "delete", "path": "root.children[1]", "old_hash": "<sha256>"}
```

## Path Syntax

Paths use dot notation with bracket indices:
- `root` — the root node
- `root.children[0]` — first child of root
- `root.children[1].children[0]` — first child of root's second child

## Workflow

### 1. Get current program hash
```bash
xi hash -e "original expression"
# → {"hash": "abc123..."}
```

### 2. Compute diff between versions
```bash
xi diff original.xi-src modified.xi-src
# → {"operations": [...], "stats": {"total_ops": 2, ...}}
```

### 3. Apply patch
```bash
xi patch original.xi-src patch.json
# → {"patched_hash": "def456...", "patched": { <NODE> }}
```

### 4. Verify result
```bash
xi eval modified.xi-src --pure
# → {"ok": true, "result": 42}
```

## Best Practices

1. **Minimize operations.** Prefer `modify_data` over `replace` when only data changes.
2. **Always include `old_hash`** for replace/delete — enables verification.
3. **One logical change = one patch.** Don't combine unrelated changes.
4. **Test after patching.** Always `xi eval` the result.
5. **Prefer structural sharing.** If two subtrees are identical, they share a hash.

## Common Patterns

### Change a constant
```json
[{"op": "modify_data", "path": "root.children[1]", "old": 3, "new": 4}]
```

### Change an operator
```json
[{"op": "modify_data", "path": "root", "old": "int_add", "new": "int_mul"}]
```

### Add a wrapper (e.g., add clamping)
```json
[{"op": "replace", "path": "root", "old_hash": "...",
  "new": {"tag": "app", "children": [
    {"tag": "lam", "children": [
      {"tag": "prim", "prim_op": "int_lit", "data": 0},
      {"tag": "ind", "children": [
        {"tag": "prim", "prim_op": "int_gt", "children": [
          {"tag": "prim", "prim_op": "var", "data": 0},
          {"tag": "prim", "prim_op": "int_lit", "data": 100}
        ]},
        {"tag": "prim", "prim_op": "int_lit", "data": 100},
        {"tag": "prim", "prim_op": "var", "data": 0}
      ]}
    ]},
    <ORIGINAL_NODE>
  ]}
}]
```

### Extract into function
```json
[{"op": "replace", "path": "root",
  "new": {"tag": "app", "children": [
    {"tag": "lam", "children": [
      {"tag": "prim", "prim_op": "int_lit", "data": 0},
      <BODY_WITH_VAR_0_REPLACING_EXTRACTED>
    ]},
    <EXTRACTED_EXPRESSION>
  ]}
}]
```

## API Endpoints

```
POST /diff   {"old_source": "...", "new_source": "..."}  → operations
POST /patch  {"source": "...", "operations": [...]}       → patched node
```
