# API: xi_deserialize.py — Binary Deserializer

Converts Xi binary format back into Node graphs.

## Functions

### `deserialize(data: bytes) → Node`
Parses a `.xi` binary byte stream and reconstructs the Node graph.

### `deserialize_file(path: str) → Node`
Convenience wrapper that reads a file and deserializes its contents.

## Round-Trip Property

```python
from xi import serialize
from xi_deserialize import deserialize

for node in all_test_nodes:
    assert deserialize(serialize(node)) == node
```

This property is verified by both unit tests and property-based tests.

## Error Handling

Raises `ValueError` if:
- Data is truncated or corrupted
- Unknown tag value encountered
- Back-reference points outside the node table
