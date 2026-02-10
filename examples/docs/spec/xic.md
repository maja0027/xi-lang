# XiC/0.1 — Compressed Binary Format

XiC (Xi Compressed) is a space-efficient encoding of Xi binary graphs. It trades marginal decompression overhead for significant size reduction on real programs.

---

## 1. Format Structure

```
┌──────────────┬───────────┬───────────────────────────┐
│ Magic (4B)   │ Root node │ Compressed node stream     │
│ "XiC\x01"   │ (inline)  │ (variable length)          │
└──────────────┴───────────┴───────────────────────────┘
```

### Magic Header

| Offset | Bytes | Meaning |
|--------|-------|---------|
| 0 | `0x58` | 'X' |
| 1 | `0x69` | 'i' |
| 2 | `0x43` | 'C' |
| 3 | `0x01` | Format version (1) |

---

## 2. Node Encoding

Each node begins with a tag-arity byte, identical to the `.xi` format:

```
tag_arity = (tag << 4) | arity
```

### 2.1 Back-References

When a subtree has been seen before (same structure), it is replaced by a back-reference:

```
0xFF ref_offset(varint)
```

The `ref_offset` is the byte offset from the start of the node stream where the original node was serialized. This enables structural sharing without full SHA-256 hashing at decode time.

### 2.2 Primitive Data

Primitive nodes encode their data inline:

| Type | Encoding |
|------|----------|
| Integer | Zigzag varint |
| String | Length (varint) + UTF-8 bytes |
| Boolean | Tag byte only (TRUE=0x30, FALSE=0x31) |
| Var | De Bruijn index (varint) |
| Operator | Opcode byte |

---

## 3. Compression Algorithm

```python
def compress(node):
    seen = {}       # hash → byte offset
    buf = BytesIO()
    buf.write(b'XiC\x01')  # magic

    def emit(n, offset):
        h = hash(n)
        if h in seen:
            buf.write(b'\xFF')
            write_varint(buf, seen[h])
            return
        seen[h] = offset
        buf.write(tag_arity_byte(n))
        for child in n.children:
            emit(child, buf.tell())
        if n.tag == PRIM:
            write_prim_data(buf, n)

    emit(node, 4)
    return buf.getvalue()
```

---

## 4. Decompression Algorithm

```python
def decompress(data):
    assert data[:4] == b'XiC\x01'
    buf = BytesIO(data[4:])
    nodes = {}      # offset → Node

    def read_node():
        offset = buf.tell()
        b = buf.read(1)[0]
        if b == 0xFF:
            ref = read_varint(buf)
            return nodes[ref]
        tag = b >> 4
        arity = b & 0xF
        children = [read_node() for _ in range(arity)]
        data = read_prim_data(buf, tag) if tag == 9 else None
        node = Node(tag, children, data)
        nodes[offset] = node
        return node

    return read_node()
```

---

## 5. Properties

- **Lossless:** `decompress(compress(n)) ≡ n` for all valid Xi nodes
- **Deterministic:** Same node always compresses to same bytes
- **Streaming:** Decompressor needs only a single pass + offset table
- **Backward compatible:** Standard `.xi` files are not valid `.xic` (different magic)

---

## 6. Future: XiC/0.2

Planned improvements:
- Huffman coding for tag distributions
- Dictionary-based compression for common patterns (APP-LAM, INT-ADD)
- Block-level deduplication for large programs
- Optional zstd outer compression layer
