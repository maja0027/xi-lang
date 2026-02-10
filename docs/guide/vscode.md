# VS Code Extension

Syntax highlighting for Xi source files (`.xi-src`).

---

## 1. Installation

Copy the extension directory to your VS Code extensions folder:

```bash
cp -r editors/vscode ~/.vscode/extensions/xi-lang
```

Reload VS Code, then open any `.xi-src` file.

## 2. Features

- **Keyword highlighting:** `def`, `type`, `import`, `let`, `in`, `if`, `then`, `else`, `match`, `fix`
- **Operator highlighting:** `λ`, `μ`, `Π`, `→`, `⇒`, `+`, `-`, `*`, `/`, `==`, `<`, `>`
- **Constructor highlighting:** Capitalized identifiers (`True`, `Succ`, `Cons`)
- **String highlighting:** Double-quoted strings with escape sequences
- **Comment highlighting:** `--` single-line comments
- **Number highlighting:** Integer literals

## 3. Typing Unicode

The extension does not include auto-replacement. Use your OS keyboard shortcuts:

| Symbol | macOS | Windows/Linux |
|--------|-------|---------------|
| λ | `Opt+L` (custom) | Compose key |
| → | `Opt+→` | `→` key |
| Π | `Opt+P` (custom) | Compose key |

Or use the ASCII alternatives in Xi surface syntax:
- `\` or `lambda` for λ
- `->` for →
- `Pi` for Π
- `fix` for μ

## 4. Extension Structure

```
editors/vscode/
├── package.json                    # Extension manifest
├── language-configuration.json     # Brackets, comments
├── syntaxes/
│   └── xi.tmLanguage.json         # TextMate grammar
└── README.md                      # Extension readme
```

## 5. Future: LSP Support

A Language Server Protocol (LSP) implementation is planned, which would add:
- Go-to-definition
- Hover type information
- Inline type errors
- Autocomplete
- Rename symbol
