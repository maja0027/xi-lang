[![CI](https://github.com/maja0027/xi-lang/actions/workflows/ci.yml/badge.svg)](https://github.com/maja0027/xi-lang/actions/workflows/ci.yml)

# Ξ (Xi) — The Final Programming Language

> A binary graph-based programming language designed for AI authorship, machine execution, and mathematical completeness.

<p align="center">
  <img src="docs/assets/xi-banner.svg" alt="Xi Language" width="600">
</p>

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Specification: v0.1](https://img.shields.io/badge/Spec-v0.1--draft-orange.svg)](docs/SPECIFICATION.md)
[![Status: Research](https://img.shields.io/badge/Status-Research-red.svg)](#status)

---

## What is Ξ?

**Ξ (Xi)** is a programming language with no syntax. Programs are not text — they are **binary-encoded directed graphs** built from exactly **10 primitive constructs**. These 10 constructs are mathematically sufficient to express any computation, any data type, and any proof.

Xi is not designed for humans to read or write. It is designed for:

- **AI to generate** — no syntax errors, no ambiguity, no formatting debates
- **Machines to verify** — dependent types enable formal verification as a built-in feature
- **Hardware to execute** — binary graph format requires zero parsing

### Why?

Every programming language ever created carries the same burden: it must be readable by humans. This constraint forces trade-offs — verbose syntax, ambiguous grammar, limited type systems, and endless language evolution. Xi eliminates this constraint entirely.

The result is a language whose core is **frozen forever**. New paradigms, new abstractions, new domains — all are expressed as libraries composed from the same 10 primitives. The core never changes because it is **mathematically complete**.

---

## Key Properties

| Property | Description |
|---|---|
| **Binary graph format** | Programs are directed graphs encoded in binary. No text, no parsing, no syntax. |
| **10 primitive constructs** | The complete, immutable foundation. Mathematically proven sufficient. |
| **Dependent type system** | Types can depend on values. Buffer overflows, null pointers, and race conditions become type errors. |
| **Content-addressed** | Every node is identified by SHA-256 hash. Structural equality = byte equality. |
| **Effect system** | Side effects (IO, mutation, nondeterminism) are explicit in the type. Pure functions are guaranteed pure. |
| **Formal verification** | The type checker is simultaneously a theorem prover. Programs carry mathematical proofs of correctness. |
| **Implicit parallelism** | Independent subgraphs can be reduced in parallel without explicit threading. |
| **Global deduplication** | Identical subexpressions share the same hash. Zero duplication by construction. |

---

## The 10 Primitives

Xi's entire foundation consists of exactly 10 constructs. Everything else — numbers, strings, lists, objects, classes, monads, async/await, SQL, neural networks — is built from these:

| Tag | Symbol | Name | Purpose |
|-----|--------|------|---------|
| `0x0` | `λ` | **Abstraction** | Functions. Binds a variable in a body expression. |
| `0x1` | `@` | **Application** | Applies a function to an argument. |
| `0x2` | `Π` | **Dependent Product** | Function types where the return type depends on the argument value. |
| `0x3` | `Σ` | **Dependent Sum** | Pair types where the second component's type depends on the first's value. |
| `0x4` | `𝒰` | **Universe** | The type of types. Stratified hierarchy `𝒰₀ : 𝒰₁ : 𝒰₂ : ...` prevents paradoxes. |
| `0x5` | `μ` | **Fixed Point** | Recursion. Enables self-referential definitions. |
| `0x6` | `ι` | **Induction** | Inductive type definitions. Encodes enums, structs, lists, trees, and all algebraic data types. |
| `0x7` | `≡` | **Identity** | Propositional equality type. Enables proofs about program behavior. |
| `0x8` | `!` | **Effect** | Effect annotation. Declares what side effects an expression may perform. |
| `0x9` | `#` | **Primitive** | Hardware operations. Arithmetic, bitwise ops, system calls. |

### Why exactly 10?

These 10 constructs correspond to the **Calculus of Inductive Constructions (CIC)** extended with effects and hardware primitives. CIC is the mathematical foundation behind proof assistants like Coq/Rocq and Lean. It has been formally proven to be:

1. **Turing-complete** — can express any computable function (via `μ`)
2. **Type-complete** — can express any data type (via `ι`)
3. **Proof-complete** — can express any constructive proof (via Curry-Howard correspondence)
4. **Effect-complete** — can model any computational effect (via `!`)

Adding an 11th construct would either be **derivable** from the existing 10 (making it redundant) or **inconsistent** with them (making it harmful).

---

## Quick Example

### "Hello, World!" in Xi

**Human-readable debug representation:**

```
!{IO}
└─ @
   ├─ # [print]
   └─ # [str: "Hello, World!"]
```

**Type:** `!{IO} Unit`

**Binary encoding (hex):**

```
CE 9E 01 00 04 00 03 90 02 00 0D 48 65 6C 6C 6F
2C 20 57 6F 72 6C 64 21 90 01 12 00 01 00 00 81
01 00 02
```

**35 bytes.** No parser needed. Directly executable.

**For comparison in JavaScript:**
```javascript
console.log("Hello, World!");
```
31 bytes of text that requires a parser, AST builder, JIT compiler, and runtime to execute.

---

## Architecture

### Layer Model

```
Layer 3+  │  Domain libraries (web, ML, databases, crypto...)
          │  All are Xi graphs with metadata.
──────────┤
Layer 2   │  Standard data structures and algorithms
          │  List, Map, String, Sort... defined via ι and μ
──────────┤
Layer 1   │  Arithmetic, logic, control flow
          │  Nat, Bool, If, Match... defined via ι
──────────┤
Layer 0   │  CORE: λ @ Π Σ 𝒰 μ ι ≡ ! #
          │  ═══════ IMMUTABLE FOREVER ═══════
```

### Content Addressing

Every node is identified by the SHA-256 hash of its content (tag + edges). This means:

- Two structurally identical programs always have the same hash
- Libraries are identified by hash, not by name or version
- Global caching of compiled code is trivial
- Equivalence checking is O(1) — just compare hashes

---

## Documentation

| Document | Description |
|---|---|
| [**Specification**](docs/SPECIFICATION.md) | Complete formal specification of the Xi language |
| [**Type System**](docs/TYPE_SYSTEM.md) | Dependent type theory, universe hierarchy, and type checking rules |
| [**Effect System**](docs/EFFECT_SYSTEM.md) | Algebraic effects, effect handlers, and effect polymorphism |
| [**Binary Format**](docs/BINARY_FORMAT.md) | Wire format specification for Xi programs |
| [**Standard Library**](docs/STDLIB.md) | Core data types and functions built from the 10 primitives |
| [**Hardware Vision**](docs/HARDWARE.md) | Xi-Machine: purpose-built hardware for graph reduction |
| [**Comparison**](docs/COMPARISON.md) | How Xi relates to existing languages and systems |
| [**Examples**](examples/) | Annotated example programs |

---

## Reference Implementation

The `src/` directory contains a complete toolchain in Python:

```bash
# Run interpreter demos (Hello World, arithmetic, lambda, etc.)
python src/xi.py demo

# Run type checker (with type error detection)
python src/xi_typecheck.py demo

# Run standard library demos (Nat, Bool, List, Option, etc.)
python src/xi_stdlib.py demo

# Run multi-core parallel reduction engine
python src/xi_multicore.py demo

# Compile surface syntax to Xi binary
python src/xi_compiler.py demo

# Interactive REPL (:tree, :type, :hex, :hash, :save)
python src/xi_repl.py

# Deserialize .xi binary back to graph (round-trip verified)
python src/xi_deserialize.py demo

# Export graph as Graphviz DOT/SVG
python src/xi_graphviz.py demo

# Pattern matching & ι-elimination (Bool, Nat, List, Option, Result)
python src/xi_match.py demo

# Module system (content-addressed imports, registry, serialization)
python src/xi_module.py demo

# Run all 133 tests
pytest tests/ -v

# Performance benchmarks
python tests/test_bench.py

# Compile a source file
python src/xi_compiler.py compile myprogram.xi-src

# Show info about a compiled Xi binary
python src/xi.py info examples/hello_world.xi
```

The `hardware/` directory contains a SystemVerilog FPGA prototype:
- `reduction_core.sv` — Single reduction core with spark pool
- `XI_MACHINE_SPEC.md` — Full hardware specification

The `formal/` directory contains Lean 4 formalization:
- `Xi/Basic.lean` — Syntax, typing rules, and metatheory

> **Note:** The reference implementation is intentionally simple. It exists to validate the specification, not to be fast. See the [benchmarks](src/xi_bench.py) for performance data.

---

## Comparison with Existing Systems

| Feature | JavaScript | Rust | Haskell | Lean 4 | Unison | **Xi** |
|---|---|---|---|---|---|---|
| Source format | Text | Text | Text | Text | Text + Hash | **Binary graph** |
| Parsing required | Yes | Yes | Yes | Yes | Yes | **No** |
| Variable names | Yes | Yes | Yes | Yes | Yes | **No (de Bruijn)** |
| Type safety | Weak | Strong | Strong | Very strong | Strong | **Total (dependent)** |
| Formal verification | No | Partial | Partial | Yes | No | **Yes, native** |
| Effect system | No | Partial | Monads | Monads | Algebraic | **Algebraic, native** |
| Content-addressed | No | No | No | No | Yes | **Yes (SHA-256)** |
| Core extensibility | Constantly | Constantly | Occasionally | Occasionally | Rarely | **Never** |
| AI-optimized | No | No | No | No | No | **Yes** |

---

## Status

**Xi is currently a research proposal and specification draft.** It is not production-ready.

### Roadmap

- [x] Core language specification (10 primitives)
- [x] Binary format specification
- [x] Reference interpreter (Python)
- [x] Type checker implementation
- [x] Standard library (Nat, Bool, List, Option, Result)
- [x] FPGA prototype of a single reduction core
- [x] Formal verification of the type system in Lean 4
- [x] Multi-core graph reduction engine
- [x] Compiler from surface syntax to Xi binary format
- [x] Xi-Machine hardware specification
- [x] Interactive REPL
- [x] Binary deserializer (round-trip verified)
- [x] Graphviz graph visualization
- [x] Test suite (230 tests: unit + property + parser) + CI
- [x] Performance benchmarks
- [x] Full pattern matching and ι-elimination
- [x] Content-addressed module system
- [x] Optimizer (constant fold, CSE, DCE)
- [x] XiC/0.1 compressed binary format
- [x] Property-based tests (Hypothesis)
- [x] Documentation site (MkDocs)
- [x] Dockerfile & docker-entrypoint
- [x] VS Code extension (syntax highlighting)
- [x] Example programs (Fibonacci, factorial, Church, tree, eval)
- [x] Multi-core FPGA (4-16 cores on Zynq UltraScale+)
- [x] ASIC tape-out design (TSMC N7, 16 cores, 1 GHz, 4 mm²)

---

## FAQ

**Q: If humans can't read Xi, how do they debug it?**
A: Through visualization tools that render the graph structure, type information, and reduction traces. Think of it like a circuit diagram — you don't read raw GDSII files, you use a viewer.

**Q: Isn't this just a virtual machine bytecode like WASM?**
A: No. WASM is a linear instruction sequence — a flattened tree. Xi is a graph with sharing, content-addressing, dependent types, and formal verification. WASM is closer to assembly; Xi is closer to mathematical logic.

**Q: Why not just improve existing languages?**
A: Because the fundamental constraint — human readability — limits what's possible. You can't add dependent types, content-addressing, and graph representation to JavaScript without creating a completely different language. Xi starts from the other end: what's the ideal representation if humans aren't in the loop?

**Q: Can Xi run on today's computers?**
A: Yes, through an interpreter or compiler, but slowly. Xi's graph structure causes frequent cache misses on conventional CPUs. The language is designed for future hardware (graph reduction processors) while being implementable on current hardware for development.

---

## License

Xi is released under the [MIT License](LICENSE).

**Copyright © 2026 Alex P. Slaby.** All copies and derivative works must include this attribution.

---

## Citation

If you use Xi in academic work, please cite:

```bibtex
@misc{xi-lang-2026,
  author = {Slaby, Alex P.},
  title  = {Xi: A Binary Graph-Based Programming Language for AI Authorship},
  year   = {2026},
  url    = {https://github.com/maja0027/xi-lang},
  note   = {Language specification and reference implementation}
}
```

---

<p align="center">
  <i>Xi is not a better programming language. It is the last one.</i>
</p>

## Docker

Run Xi without installing anything:

```bash
docker build -t xi-lang .
docker run xi-lang              # Run all demos
docker run xi-lang test         # Run 144 tests
docker run -it xi-lang repl     # Interactive REPL
docker run xi-lang match        # Pattern matching demo
docker run xi-lang module       # Module system demo
```

## Surface Syntax

Xi programs can be written in a human-readable surface syntax:

```bash

python src/xi_compiler.py demo           # 36 parser demos

python src/xi_compiler.py run examples/demo.xi-src  # Run .xi-src files

```

Example:

```

def double = λx. x + x

def fact = fix self. λn. match n {

    Zero → Succ Zero

  | Succ k → mul (Succ k) (self k)

}

def main = double 21

```

## Examples

Run the example programs (Fibonacci, factorial, Church numerals, list ops, binary trees, expression evaluator):

```bash
python examples/xi_examples.py
```

## VS Code Extension

Syntax highlighting for `.xi-src` files:

```bash
# Install locally
cp -r editors/vscode ~/.vscode/extensions/xi-lang

# Or build VSIX
cd editors/vscode && npx @vscode/vsce package
code --install-extension xi-lang-0.1.0.vsix
```

## Citation (BibTeX)

```bibtex
@software{slaby2026xi,
  author       = {Slaby, Alex P.},
  title        = {{$\Xi$ (Xi): An AI-Native Programming Language with Binary Graph Representation}},
  year         = {2026},
  url          = {https://github.com/hovinek/xi-lang},
  version      = {0.5.0},
  note         = {Reference implementation with dependent types, content-addressed memory,
                  multi-core hardware design, and Lean 4 soundness proofs}
}
```
