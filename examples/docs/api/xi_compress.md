# API: xi_compress.py — XiC Compressed Format

Compresses and decompresses Xi binary graphs using the XiC/0.1 format.

## Functions

### `compress(node: Node) → bytes`
Compresses a Node graph to XiC format with structural sharing.

### `decompress(data: bytes) → Node`
Decompresses XiC data back to a Node graph.

### `compress_ratio(node: Node) → float`
Returns the compression ratio (compressed_size / original_size).

## Format

XiC/0.1 uses:
- Magic header: `XiC\x01` (4 bytes)
- Back-references for shared subtrees (`0xFF` + varint offset)
- Tag-arity packing in single byte

## Example
```python
from xi_compress import compress, decompress
from xi import serialize, Node

node = large_program()
xic = compress(node)        # → bytes (smaller)
restored = decompress(xic)  # → Node (identical)
assert serialize(restored) == serialize(node)
```
