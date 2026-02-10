# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Xi, please report it responsibly:

1. **Do not** open a public issue
2. Email: [create a private security advisory](https://github.com/maja0027/xi-lang/security/advisories/new) on GitHub
3. Include a clear description and steps to reproduce

We will acknowledge receipt within 48 hours and aim to provide a fix within 7 days for critical issues.

## Security by Design

Xi's architecture eliminates entire classes of vulnerabilities at the language level:

| Vulnerability | Status | Mechanism |
|---|---|---|
| Buffer overflow | Impossible | No arrays or raw pointers — only typed graph nodes |
| Use-after-free | Impossible | Reference counting; no manual memory management |
| Null pointer | Impossible | No null — use `Option` type instead |
| Injection attacks | Impossible | Programs are binary graphs, not text to parse |
| Type confusion | Impossible | Dependent types checked before execution |

## Scope

This security policy covers:
- The Xi binary format and its parsing (deserializer)
- The reference interpreter
- The type checker
- The compiler (surface syntax parser)

The FPGA and hardware designs are research prototypes and not covered by this policy.
