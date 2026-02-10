# Ξ (Xi) — Documentation

Welcome to the Xi language documentation. Xi is an AI-native programming language designed for machine-to-machine communication, with binary graph representation, dependent types, and content-addressed memory.

## Getting Started

- **[Quick Start Guide](guide/quickstart.md)** — Get running in 5 minutes
- **[Examples](guide/examples.md)** — Learn by example
- **[Docker](guide/docker.md)** — Run in a container
- **[VS Code](guide/vscode.md)** — Syntax highlighting

## Language Reference

- **[Language Specification](spec/language.md)** — 10 primitives, reduction rules, surface syntax
- **[Type System](spec/types.md)** — Dependent types, universes, HM inference
- **[Effect System](spec/effects.md)** — Algebraic effects and purity tracking
- **[Binary Format](spec/binary.md)** — .xi binary and serialization
- **[XiC Format](spec/xic.md)** — Compressed binary format

## Architecture

- **[Interpreter](arch/interpreter.md)** — Graph reduction engine
- **[Optimizer](arch/optimizer.md)** — Constant folding, CSE, DCE
- **[Module System](arch/modules.md)** — Content-addressed imports
- **[Hardware](arch/hardware.md)** — Multi-core FPGA and ASIC design

## API Reference

| Module | Description |
|--------|-------------|
| [`xi`](api/xi.md) | Core types, Node, Tag, serialization |
| [`xi_compiler`](api/xi_compiler.md) | Surface syntax parser and compiler |
| [`xi_match`](api/xi_match.md) | Pattern matching interpreter |
| [`xi_typecheck`](api/xi_typecheck.md) | Type checker with HM inference |
| [`xi_optimizer`](api/xi_optimizer.md) | Graph optimizer |
| [`xi_compress`](api/xi_compress.md) | XiC compressed format |
| [`xi_module`](api/xi_module.md) | Module system |
| [`xi_stdlib`](api/xi_stdlib.md) | Standard library |
| [`xi_repl`](api/xi_repl.md) | Interactive REPL |
| [`xi_multicore`](api/xi_multicore.md) | Parallel engine |
| [`xi_graphviz`](api/xi_graphviz.md) | Graph visualization |
| [`xi_deserialize`](api/xi_deserialize.md) | Binary deserializer |

## FAQ

See the **[Frequently Asked Questions](faq.md)** for common questions about Xi's design philosophy, performance, and roadmap.

## Project Links

- **GitHub:** [hovinek/xi-lang](https://github.com/hovinek/xi-lang)
- **License:** MIT (Copyright © 2026 Alex P. Slaby)
