# Changelog
### v0.5.1 — 2026-02-10 — Documentation & Examples Complete

#### Documentation (all stubs filled)
- **Language Specification** (`docs/spec/language.md`) — 200 lines: 10 primitives, reduction rules, type system, content addressing, surface syntax grammar
- **Type System** (`docs/spec/types.md`) — 168 lines: universe hierarchy, built-in types, Π/Σ/ι/≡ types, HM inference algorithm, canonical forms
- **Effect System** (`docs/spec/effects.md`) — 158 lines: effect sets, annotations, subtyping, effect rules, hardware implications
- **Binary Format** (`docs/spec/binary.md`) — 112 lines: node encoding, varint, content addressing, examples
- **XiC Format** (`docs/spec/xic.md`) — 128 lines: compression algorithm, back-references, decompression
- **Interpreter Architecture** (`docs/arch/interpreter.md`) — 117 lines: components, evaluation strategy, reduction rules, de Bruijn indices
- **Hardware Architecture** (`docs/arch/hardware.md`) — 136 lines: block diagram, pipeline, sparks, memory hierarchy, FPGA/ASIC specs
- **Optimizer Architecture** (`docs/arch/optimizer.md`) — 108 lines: constant folding, CSE, DCE, correctness
- **Module System** (`docs/arch/modules.md`) — 92 lines: content addressing, resolution, registry
- **12 API docs** — all Python modules documented with types, functions, and examples
- **Quick Start Guide** (`docs/guide/quickstart.md`) — 189 lines: installation, REPL, functions, ADTs, compilation
- **Examples Guide** (`docs/guide/examples.md`) — 164 lines: 10 annotated example programs
- **Docker Guide** (`docs/guide/docker.md`) — 84 lines: build, run, compose, CI
- **VS Code Guide** (`docs/guide/vscode.md`) — 60 lines: installation, features, Unicode input
- **FAQ** (`docs/faq.md`) — 63 lines: design, performance, type system, hardware, ecosystem
- **Documentation index** (`docs/index.md`) — full navigation with all sections
- **MkDocs config** (`mkdocs.yml`) — complete nav with 30+ pages

#### Examples
- 6 new `.xi-src` examples: fibonacci, ADT, Church numerals, option, strings, higher-order, multidef
- Fixed 3 empty binary `.xi` examples (hello_world, compiled_hello, string_concat)
- Updated examples/README.md with full table

#### Other
- BibTeX citation block in README
- CI updated: example verification, demo checks, benchmark smoke test
- Fixed test_xi_src_file_run test

### v0.5.0 — 2026-02-10 — Multi-Core FPGA & ASIC Tape-Out

#### Hardware
- **Multi-core reduction engine** (`hardware/xi_multicore.sv`) — 550+ lines
  - Parameterized 4–16 core array with `generate` blocks
  - Round-robin crossbar interconnect for shared memory
  - Work-stealing spark distributor with per-core FIFO queues
  - Hardware reference-counting GC with free list
  - L2 node cache (4-way set-associative, LRU, write-back)
  - SHA-256 content addressing accelerator (64-round pipelined)
  - Cycle counter, reduction counter, cache hit/miss stats

- **Zynq UltraScale+ FPGA top** (`hardware/xi_zynq_top.sv`) — 200+ lines
  - AXI-Lite slave: control/status register map
  - AXI-Full slave: graph DMA from PS ARM to PL BRAM
  - Memory-mapped config: start, entry, cycles, reductions, version
  - 4 debug LEDs: done, busy, all-idle, start pulse
  - Target: ZCU104 (XCZU7EV) or ZCU102 (XCZU9EG)

- **FPGA constraints** (`hardware/constraints/zynq_zcu104.xdc`)
  - Timing: 200 MHz PL clock, multi-cycle paths for SHA-256/crossbar
  - Area: pblocks per core in separate clock regions
  - I/O: LED mapping for ZCU104 board

- **ASIC top level** (`hardware/asic/xi_asic_top.sv`) — 250+ lines
  - 16-core SoC targeting TSMC N7 (7nm)
  - AXI4 master to LPDDR4X / HBM memory
  - AXI4-Lite slave for host configuration
  - Clock domain crossing with async reset sync
  - AXI memory bridge FSM (rd/wr address + data phases)
  - Per-core power gating via `core_enable` pins
  - JTAG debug port stub

- **ASIC SDC constraints** (`hardware/asic/constraints.sdc`)
  - 1 GHz core clock, 800 MHz memory clock, 50 MHz JTAG
  - Clock domain crossing false paths
  - SHA-256 multi-cycle (64 rounds)
  - Fanout/transition/capacitance design rules
  - Worst-case operating conditions (SS, 0.72V, 125°C)

- **Tape-out specification** (`hardware/asic/TAPE_OUT.md`)
  - Process options: TSMC N7, GF 12LP+, SkyWater SKY130
  - Architecture block diagram and floorplan
  - Power analysis: 514 mW total, 23.6 mW/core
  - Verification plan: RTL sim, formal, FPGA proto, UVM
  - Design flow: synthesis → P&R → signoff → GDSII
  - DFT: scan chains, SRAM BIST, JTAG, ATPG >98%
  - SKU planning: Xi-4/16/64/256
  - BOM: $68 total for evaluation board
  - Schedule: tape-out Q4 2026, silicon Q2 2027

- **Multi-core testbench** (`hardware/tb/xi_multicore_tb.sv`)
  - Smoke test: identity(42) graph loaded into ext memory
  - Timeout watchdog, waveform dump (VCD)

### v0.4.0 — 2026-02-10 — Tier 3: Playground, Benchmarks, Lean Proofs

#### Added
- **Web Playground** (`playground.jsx`) — full React interactive environment
  - Syntax-highlighted editor with Ctrl+Enter to run
  - 10 built-in examples (basics → fibonacci)
  - **Graph visualization** — SVG tree rendering of AST at any reduction step
  - **Step-by-step reduction** — click through β/μ/δ/ι reductions with progress bar
  - Result display with type inference and step count
  - Info panel explaining Xi's 10 primitives
  - Mini Xi interpreter in JavaScript (~400 lines): tokenizer, parser, evaluator
  - Dark theme with indigo/violet palette, JetBrains Mono font

- **Benchmark Suite** (`bench/bench.py`)
  - Fibonacci: Nat/Peano (fib 8 = 141ms) vs Int (fib 20 = 3.4s)
  - Factorial: Nat/Peano (fact 5 = 764ms) vs Int (fact 12 = 2.5ms)
  - Church numerals: church(10) + church(10) = 13ms
  - Compilation speed: parse 0.6ms, optimize 0.4ms, typecheck 0.03ms
  - Serialization: roundtrip 0.28ms, XiC roundtrip 0.6ms
  - Binary size comparison table (raw vs optimized vs XiC)
  - Reference comparison with Python, GHC, Agda
  - `--quick` flag for fast CI runs

- **Lean 4 Soundness Proofs** (`formal/Xi/Basic.lean`) — 320 lines, 18 theorems
  - **Subject Reduction** (Type Preservation) — structurally proved for all 5 step rules
  - **Progress** — proved for all typing rules (closed terms are values or can step)
  - **Type Safety** — fully proved (combines preservation + progress)
  - `value_irreducible` — values don't reduce (fully proved)
  - `Steps.trans`, `Steps.single` — multi-step properties (fully proved)
  - Effect system: `effect_weakening`, `effect_sub_trans` (fully proved)
  - `EffSet.subset_refl/trans/empty_subset/union_left` (fully proved)
  - `no_type_in_type` — universe consistency (¬ 𝒰ᵢ : 𝒰ᵢ)
  - Canonical forms: `canonical_pi`, `canonical_int`, `canonical_bool`
  - Content addressing: `content_eq_decidable`
  - Axiomatized: weakening, substitution lemma (~250 lines each if expanded)

### v0.3.0 — 2026-02-10 — ADTs, Imports, HM Inference, CLI

#### Added
- **Algebraic data types** — `type Color = Red | Green | Blue` in surface syntax
  - Dynamic constructor registration (no more hardcoded-only constructors)
  - Type registry tracking type → constructor mapping
  - Arbitrary arity: `type Shape = Circle Int | Rect Int Int | Point`
- **Multi-file imports** — `import Prelude` resolves and loads .xi-src files
  - Search path: lib/, src/lib/, .
  - Import caching (each module loaded once)
  - Prelude: add, mul, fib, fact, id, const, compose, min, max, abs, mapOpt
- **Hindley-Milner type inference** — TypeChecker v0.2
  - TypeVar with mutable unification bindings
  - Occurs check for infinite types
  - Untyped lambda inference: `λx. x + 1` → `Int → Int`
  - Inference through let-bindings and applications
  - resolve_type for full type variable resolution
- **def with parameters** — `def double x = x + x` (sugar for lambda)
  - Multi-param: `def add a b = a + b`
  - Mixes with typed params
- **Source spans** — Span(file, line, col) on all tokens and errors
  - ParseError and LexError carry span info
  - format_error() shows source line with ^ pointer
- **xi CLI tool** — unified entry point
  - `xi run <file>` / `xi run -e '<expr>'`
  - `xi build [--xic] <file>` — compile to .xi or .xic
  - `xi check <file>` — type-check with HM inference
  - `xi repl` / `xi test` / `xi demo`
- **REPL v0.2** enhancements
  - `import Prelude` in REPL
  - `type Color = ...` declarations
  - `def f x = ...` with params
  - `:type` uses HM inference (shows inferred types)
  - Multi-line input (trailing \ or unbalanced braces)
- **38 new tests** — ADTs, imports, HM inference, error messages, e2e pipeline
- **Test suite: 268 tests** (248 unit + 20 property-based)

### v0.2.0 — 2026-02-10 — Surface Syntax Parser

#### Added
- **Surface syntax parser** (`xi_compiler.py` v0.2) — full rewrite
  - Lexer: Unicode (λ μ Π →) and ASCII (fun fix forall ->) tokens, nested block comments
  - Parser: recursive descent with Pratt-style operator precedence
  - Lambda: `λx. body`, `λ(x : Int). body`, `λx y z. body` (multi-binder)
  - Pattern matching: `match expr { Zero → a | Succ n → b }`
  - Recursion: `fix self. λn. ...` or `μself. ...`
  - Let bindings: `let x = expr in body` (desugared to λ-application)
  - If/then/else: `if cond then a else b` (desugared to bool_match)
  - Effect annotation: `!{IO} expr`
  - Program mode: `def name = expr` with `main` entry point
  - Constructors: True/False, Zero/Succ, None/Some, Nil/Cons, Ok/Err
  - Proper de Bruijn index computation via Scope chain
  - 36 demo checks, all passing
- **Example .xi-src files**: `examples/demo.xi-src`, `examples/hello.xi-src`
- **52 new parser tests** in test suite
- **Test suite**: 230 tests (210 unit + 20 property-based)

#### Fixed
- Tokenizer: Unicode chars (λ, →, Π, μ) now advance by 1 char, not UTF-8 byte length
- Scope.resolve: de Bruijn indices now computed correctly in nested let/lambda

### v0.1.3 — 2026-02-10 — Optimizer, XiC, Property Tests, Docs

#### Added
- **Optimizer** (`xi_optimizer.py`) — 3-pass pipeline: constant folding, CSE, dead code elimination
  - Constant folding: evaluates pure primitives at compile time (79% size reduction on arithmetic)
  - CSE: shares structurally identical subtrees via content hashing
  - DCE: removes unreachable nodes after transformation
- **XiC/0.1** (`xi_compress.py`) — compressed binary format
  - LEB128 variable-length integer encoding
  - Structural deduplication (content-addressed node hashing)
  - zlib payload compression
  - Up to 89% reduction vs standard Xi binary
  - Full roundtrip: compress → decompress preserves evaluation
- **Property-based tests** (`test_property.py`) — 20 Hypothesis fuzz tests covering:
  - Serialization roundtrip, XiC roundtrip, optimizer correctness
  - Type checker soundness, CSE idempotence, hash determinism
- **MkDocs documentation** — 19 pages covering spec, guide, architecture, API
- **Test suite**: 178 tests (158 unit + 20 property-based)

### v0.1.2 — 2026-02-10 — Adoption

#### Added
- **Dockerfile** — `docker run xi-lang demo` runs all demos without setup
- **Docker entrypoint** — subcommands: demo, test, repl, bench, match, module, typecheck, compile
- **Example programs** — Fibonacci, factorial, Church numerals, list operations, binary tree, expression evaluator (29 checks)
- **VS Code extension** — syntax highlighting for `.xi-src` and `.xi` files with TextMate grammar
- **Test suite**: 144 tests (10 new for examples & adoption artifacts)


All notable changes to Xi will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] — 2026-02-10

### Added
- **Core specification** — 10 immutable primitives (λ @ Π Σ 𝒰 μ ι ≡ ! #)
- **Binary format** — content-addressed DAG encoding with SHA-256 hashing
- **Reference interpreter** (`src/xi.py`) — tree-walking reducer for all 10 primitives
- **Type checker** (`src/xi_typecheck.py`) — bidirectional dependent type checking
- **Standard library** (`src/xi_stdlib.py`) — Nat, Bool, List, Option, Result as Xi graphs
- **Compiler** (`src/xi_compiler.py`) — surface syntax → Xi binary format
- **Multi-core engine** (`src/xi_multicore.py`) — parallel graph reduction with spark pool
- **REPL** (`src/xi_repl.py`) — interactive read-eval-print loop
- **Deserializer** (`src/xi_deserialize.py`) — read .xi binaries back to graphs (round-trip verified)
- **Graphviz export** (`src/xi_graphviz.py`) — DOT format visualization
- **Pattern matching** (`src/xi_match.py`) — ι-elimination for Bool, Nat, List, Option, Result with recursive functions (add, mul, length, map, foldr, factorial)
- **Module system** (`src/xi_module.py`) — content-addressed modules, registry, dependency resolution, serialization
- **Benchmarks** (`tests/test_bench.py`) — performance measurement suite
- **FPGA prototype** (`hardware/reduction_core.sv`) — single reduction core in SystemVerilog
- **Hardware specification** (`hardware/XI_MACHINE_SPEC.md`) — Xi-Machine SoC design
- **Lean 4 formalization** (`formal/Xi/Basic.lean`) — syntax, typing rules, metatheory
- **Test suite** — 133 tests across all components
- **CI/CD** — GitHub Actions workflow for Python 3.10-3.12
- **Documentation** — specification, type system, effects, binary format, stdlib, hardware, comparisons
- **Example programs** — Hello World, arithmetic, string concat, lambda application

[0.1.0]: https://github.com/maja0027/xi-lang/releases/tag/v0.1.0
