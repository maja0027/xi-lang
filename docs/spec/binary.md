# Binary Format Specification

Xi programs are stored as binary DAGs (directed acyclic graphs). This document specifies the `.xi` binary format and the `.xic` compressed format.

---

## 1. Xi Binary Format (.xi)

### 1.1 Overview

A `.xi` file is a serialized graph of Xi nodes. Each node is encoded as a variable-length byte sequence. The file is a depth-first traversal of the DAG from the root.

### 1.2 Node Encoding

```
┌─────────┬───────┬─────────────┬──────────────┐
│ Tag (4b) │Arity  │ Children... │ Data (opt)   │
│ 0x0–0x9 │(4b)   │ (recursive) │ (varint/str) │
└─────────┴───────┴─────────────┴──────────────┘
```

**Tag byte:** Upper nibble = tag (0–9), lower nibble = arity (0–15).

**Children:** Each child is a recursively serialized node. Shared nodes (same hash) are serialized once and referenced by back-pointer.

**Data field (for primitives, tag 0x9):**

| Prim opcode | Data format |
|-------------|-------------|
| VAR (0x00) | varint: de Bruijn index |
| INT_LIT (0x03) | varint: signed integer |
| STR_LIT (0x02) | length-prefixed UTF-8 |
| BOOL_TRUE (0x30) | none |
| BOOL_FALSE (0x31) | none |
| Arithmetic ops | none (data in children) |

### 1.3 Varint Encoding

Integers use variable-length encoding (LEB128):
- Values 0–127: 1 byte
- Values 128–16383: 2 bytes
- Signed values use zigzag encoding

### 1.4 Content Addressing

Each node's canonical hash is `SHA-256(serialized_bytes)`. Two nodes with the same hash are guaranteed identical (collision-resistant). The serializer deduplicates nodes by hash during output.

### 1.5 Example

The expression `(λx. x + x) 3` serializes to approximately 39 bytes:

```
01          APP (tag=1, arity=2)
  00        LAM (tag=0, arity=2)
    90 03   PRIM INT (param type placeholder)
    91 10   PRIM ADD
      90 00 PRIM VAR 0
      90 00 PRIM VAR 0   (shared: same node)
  90 03 03  PRIM INT_LIT 3
```

---

## 2. XiC Compressed Format (.xic)

XiC/0.1 adds structural compression on top of the binary format.

### 2.1 Magic Header

```
Bytes 0–3: 0x58 0x69 0x43 0x01  ("XiC" + version 1)
```

### 2.2 Compression Techniques

1. **Tag-arity packing:** Tag and arity share one byte (already in .xi)
2. **Child deduplication:** Back-references for repeated subtrees (2-byte offset instead of full re-serialization)
3. **Varint optimization:** Small integers (0–127) in one byte
4. **Node frequency coding:** Common patterns (APP-LAM, PRIM-INT) get short codes

### 2.3 Decompression

XiC decompresses to standard .xi format. The decompressor:
1. Reads the magic header and verifies version
2. Builds a node table during decompression
3. Resolves back-references to shared nodes
4. Returns the root Node

### 2.4 Size Comparison

| Program | .xi | .xic | Ratio |
|---------|-----|------|-------|
| `42` | 17B | 21B | 1.24× (overhead for small) |
| `2 + 3` | 39B | 21B | 0.54× |
| `λx. x*x` | 33B | 33B | 1.00× |
| `fib def` | 101B | 62B | 0.61× |
| `fact+fib (large)` | 577B | 172B | 0.30× |

XiC is most effective on larger programs with repeated subexpressions. The overhead for trivial programs is ~4 bytes (magic header).

---

## 3. Round-Trip Guarantee

For any Xi node `n`:

```python
assert deserialize(serialize(n)) == n
assert decompress(compress(n)) == n
```

This is tested with both unit tests and property-based tests (Hypothesis).
