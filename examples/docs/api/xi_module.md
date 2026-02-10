# API: xi_module.py — Module System

Content-addressed module registry for multi-file Xi programs.

## Classes

### `ModuleRegistry`
```python
class ModuleRegistry:
    def register(name: str, binary: bytes) → bytes    # Returns hash
    def resolve(hash: bytes) → Module
    def compile_source(name: str, source: str) → bytes
    def link(program: Node, deps: list[bytes]) → Node
```

### `Module`
```python
class Module:
    name: str
    hash: bytes           # SHA-256 of compiled binary
    definitions: dict     # name → Node
    dependencies: list    # Required module hashes
```

## Functions

### `create_registry() → ModuleRegistry`
Creates a new empty registry with the stdlib pre-registered.

## Content Addressing

Modules are identified by SHA-256 hash of their serialized form. Two modules with identical source code compile to identical hashes.

```python
reg = create_registry()
h1 = reg.compile_source("A", "def id x = x")
h2 = reg.compile_source("B", "def id x = x")
assert h1 == h2  # Same code → same hash
```
