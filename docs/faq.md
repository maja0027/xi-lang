# Frequently Asked Questions

## Design

**Q: If humans can't read Xi, how do they debug it?**

A: Through visualization tools that render the graph structure, type information, and reduction traces. The web playground (`playground.jsx`) shows the AST as an interactive graph with step-by-step reduction. The Graphviz module (`xi_graphviz.py`) generates static diagrams. Think of it like a circuit diagram — you don't read raw GDSII files, you use a viewer.

**Q: Isn't this just a virtual machine bytecode like WASM?**

A: No. WASM is a linear instruction sequence — a flattened tree. Xi is a graph with sharing, content-addressing, dependent types, and formal verification. WASM is closer to assembly; Xi is closer to mathematical logic. The key difference: Xi nodes are content-addressed (identified by hash), enabling deduplication and integrity checking impossible with linear bytecodes.

**Q: Why not just improve existing languages?**

A: Because the fundamental constraint — human readability — limits what's possible. You can't add dependent types, content-addressing, and graph representation to JavaScript without creating a completely different language. Xi starts from the other end: what's the ideal representation if humans aren't in the loop?

**Q: Why exactly 10 primitives?**

A: They form a minimal complete basis: λ/@/Π for the lambda calculus core, Σ for pairs, 𝒰 for universe consistency, μ for recursion, ι for data types, ≡ for equality proofs, ! for effects, # for machine primitives. Removing any one loses expressiveness. Adding more would be redundant.

## Performance

**Q: Can Xi run on today's computers?**

A: Yes, through the Python reference interpreter, but slowly. Xi's graph structure causes frequent cache misses on conventional CPUs. The language is designed for future hardware (graph reduction processors) while being implementable on current hardware for development.

**Q: How does Xi compare to other languages?**

A: For fib(20): Python ~4 ms, Xi ~3.4 s (interpreted), GHC -O2 ~0.01 ms, Agda ~50 ms. Xi's interpreted performance is comparable to other proof assistants. The hardware implementation targets orders-of-magnitude improvement.

**Q: Why is the interpreter slow?**

A: Three reasons: (1) Python overhead — the interpreter is a reference implementation prioritizing clarity, (2) graph reduction creates many small allocations, (3) de Bruijn substitution traverses the entire body. The hardware engine (Xi-Machine) eliminates all three by doing graph rewriting in silicon.

## Type System

**Q: Is Xi's type system sound?**

A: The core properties are proved in Lean 4 (`formal/Xi/Basic.lean`): subject reduction (type preservation), progress, and type safety. The universe hierarchy prevents Girard's paradox (𝒰ᵢ ∉ 𝒰ᵢ).

**Q: How does HM inference interact with dependent types?**

A: The surface language uses standard Hindley-Milner with unification variables. These are mapped to Π types in the core language. For most programs, annotations aren't needed — `λx. x + 1` is inferred as `Int → Int` automatically.

## Hardware

**Q: Is the FPGA implementation real?**

A: The RTL is synthesizable SystemVerilog targeting Xilinx Zynq UltraScale+. The single-core design (455 lines) and multi-core engine (908 lines) pass linting. FPGA validation on actual ZCU104 hardware is planned for Q1 2026.

**Q: When will the ASIC tape out?**

A: The tape-out specification targets Q4 2026 via MPW shuttle (TSMC N7 or SkyWater SKY130). See `hardware/asic/TAPE_OUT.md` for the full plan.

## Ecosystem

**Q: Can I use Xi today?**

A: Yes — install from source, use the REPL, write `.xi-src` files, run programs. The web playground works without installation. For production use, Xi needs more stdlib, better error messages, and the LSP.

**Q: How do I contribute?**

A: See `CONTRIBUTING.md`. The most impactful areas are: stdlib expansion, LSP server, FPGA validation, and additional Lean proofs.
