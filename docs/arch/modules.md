# Module System Architecture

Xi uses content-addressed modules for code organization, sharing, and linking.

---

## 1. Content-Addressed Identity

Every module is identified by the SHA-256 hash of its compiled binary representation. Two modules with identical code have identical hashes, regardless of filename, author, or build environment.

```
Module "Prelude"
  → compiled binary: 0x4a7b2c...
  → hash: SHA-256(binary) = 0x8f3e21a9...
```

This means:
- **No version conflicts:** Same code = same hash = same module
- **Reproducible builds:** Hash determines exact module content
- **Automatic deduplication:** Multiple imports of the same code resolve to one module

## 2. Surface Syntax

### Import

```
import Prelude          -- loads lib/Prelude.xi-src
import Data.List        -- loads lib/Data/List.xi-src
```

### Module File (lib/Prelude.xi-src)

```
-- Standard library definitions
def id x = x
def const x y = x
def compose f g x = f (g x)
def add a b = match a { Zero → b | Succ n → Succ (add n b) }
def fib n = match n { Zero → Zero | Succ m → ... }
```

## 3. Module Resolution

Search order for `import Foo`:
1. `./lib/Foo.xi-src` (project-local library)
2. `$XI_PATH/Foo.xi-src` (environment variable)
3. Built-in stdlib

The compiler caches compiled modules to avoid re-parsing on duplicate imports.

## 4. Module Compilation Pipeline

```
Foo.xi-src → tokenize → parse → resolve → compile → Foo (binary DAG)
                                    ↓
                              Module Registry
                              (hash → definitions)
```

Each `def name = expr` in a module becomes an entry in the definition table. When a program uses `import Foo`, all of Foo's definitions are added to the compilation scope.

## 5. Registry

The `ModuleRegistry` maintains a mapping from module hash to compiled content:

```python
class ModuleRegistry:
    modules: dict[bytes, Module]     # hash → module
    names: dict[str, bytes]          # name → hash

    def register(name, source):
        compiled = compile(source)
        h = sha256(serialize(compiled))
        self.modules[h] = compiled
        self.names[name] = h

    def resolve(name) -> Module:
        h = self.names[name]
        return self.modules[h]
```

## 6. Future: Package Registry

Planned content-addressed package distribution:

```
xi pkg publish Prelude    # Upload by hash
xi pkg fetch 0x8f3e21a9  # Download by hash
xi pkg search "sort"      # Search by keyword
```

Packages are immutable — once published with a hash, the content never changes. Updates create new hashes.
