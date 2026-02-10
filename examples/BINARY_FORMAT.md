# Xi Binary Format Specification

**Version:** 0.1-draft
**Author:** Alex P. Slaby

---

## File Structure

```
┌──────────────────────────────────────────────┐
│  Header (7 bytes)                            │
├──────────────────────────────────────────────┤
│  Node Table (variable length)                │
│  ┌────────────────────────────────────────┐  │
│  │  Node 0                                │  │
│  │  Node 1                                │  │
│  │  ...                                   │  │
│  │  Node N-1                              │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

## Header

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| `0x00` | 2 | `magic` | `0xCE 0x9E` (UTF-8 of `Ξ`) |
| `0x02` | 1 | `version` | Format version (currently `0x01`) |
| `0x03` | 2 | `node_count` | Number of nodes (big-endian uint16) |
| `0x05` | 2 | `root_index` | Index of root node (big-endian uint16) |

## Node Header (1 byte)

```
[TTTT AAAA]    T = tag (0x0-0x9), A = arity (0-15)
```

## Edge Encoding

Each child edge follows the node header:
- **Local reference:** varint index into node table
- **External reference:** `0xFF` prefix + 32-byte SHA-256 hash

## Tag-Specific Data

- **Universe (0x4):** varint universe level
- **Effect (0x8):** 1-byte effect bitfield
- **Primitive (0x9):** 1-byte opcode + optional literal data

### Primitive Opcodes

| Opcode | Name | Type |
|--------|------|------|
| `0x00` | `var` | De Bruijn variable |
| `0x01` | `print` | `String → !{IO} Unit` |
| `0x02` | `str_lit` | String literal |
| `0x03` | `int_lit` | Integer literal |
| `0x10-0x15` | Arithmetic | `Int → Int → Int` |
| `0x20-0x24` | Comparison | `Int → Int → Bool` |
| `0x50-0x51` | String ops | Various |
| `0x60-0x62` | File IO | Various |

### Literal Encoding

- **Integer:** 8-byte big-endian signed int64
- **Float:** 8-byte IEEE 754 double
- **String:** 2-byte length (uint16) + UTF-8 bytes

## Content Hash

```
hash(node) = SHA-256(tag_byte ‖ edge_hashes ‖ data_bytes)
```

Metadata is NOT included in the hash.

## Metadata (Optional)

Prefix `0xFE`, then 2-byte length + CBOR-encoded key-value pairs. Standard keys: `inline`, `eager`, `strict`, `parallel`, `source`, `provenance`.

## Hello World Example

```
CE 9E 01 00 04 00 03     Header: magic, v1, 4 nodes, root=3
90 02 00 0D 48 65 ...    Node 0: str "Hello, World!"
90 01                    Node 1: print
12 00 01 00 00           Node 2: app(node1, node0)
81 00 02 01              Node 3: !{IO}(node2)
```

Total: 35 bytes.
