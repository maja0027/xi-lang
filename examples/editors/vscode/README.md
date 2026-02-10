# Ξ (Xi) Language — VS Code Extension

Syntax highlighting and language support for the Xi programming language.

## Features

- Syntax highlighting for `.xi-src` and `.xi` files
- Comment toggling (`--` line, `{- -}` block)
- Bracket matching and auto-closing
- Smart indentation
- Highlighting for:
  - Keywords: `λ`, `μ`, `Π`, `Σ`, `match`, `def`, `module`, etc.
  - Types: `Nat`, `Bool`, `List`, `Option`, `Result`, universe `𝒰`
  - Constructors: `Zero`, `Succ`, `Nil`, `Cons`, `Some`, `None`
  - Operators: `→`, `←`, `⊢`, `≡`
  - Built-in primitives and constants

## Installation

### From VSIX (local)
```bash
cd editors/vscode
npx @vscode/vsce package
code --install-extension xi-lang-0.1.0.vsix
```

### Manual
Copy this folder to `~/.vscode/extensions/xi-lang/`

## Screenshots

```xi
-- Fibonacci in Xi surface syntax
module Fibonacci

import Nat

def fib : Nat → Nat
def fib = λn. match n with
  | Zero    → Zero
  | Succ k  → match k with
    | Zero    → Succ Zero
    | Succ k' → add (fib k) (fib k')
```

## License

MIT — Copyright (c) 2026 Alex P. Slaby
