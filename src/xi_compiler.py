#!/usr/bin/env python3
"""
Ξ (Xi) Surface Syntax Parser v0.3
Copyright (c) 2026 Alex P. Slaby — MIT License

Full surface syntax for Xi with:
- Algebraic data types (type declarations)
- Multi-file imports (import Prelude)
- Pattern matching, recursion, let-bindings
- Operator precedence (Pratt parsing)
- Source spans for error messages

Grammar:

  program   ::= decl*
  decl      ::= 'def' IDENT ('(' params ')') ? (':' type)? '=' expr
              | 'type' CONSTR params? '=' constr ('|' constr)*
              | 'import' CONSTR
              | 'module' CONSTR

  constr    ::= CONSTR type*

  expr      ::= 'λ' binders '.' expr
              | 'fix' IDENT '.' expr | 'μ' IDENT '.' expr
              | 'Π' '(' IDENT ':' expr ')' '.' expr
              | 'let' IDENT '=' expr 'in' expr
              | 'if' expr 'then' expr 'else' expr
              | 'match' expr '{' branch ('|' branch)* '}'
              | infix

  infix     ::= app (BINOP app)*   -- precedence climbing
  app       ::= atom+              -- left-assoc application
  atom      ::= INT | STRING | IDENT | CONSTR | '(' expr ')'

Operator precedence (low → high):
  1: ||   2: &&   3: == !=   4: < > <= >=   5: + - ++   6: * / %
"""

import sys, os, re, glob
sys.path.insert(0, os.path.dirname(__file__))
from xi import Node, Tag, PrimOp, Effect, B, serialize, hexdump, render_tree, Interpreter
from xi_match import (
    MatchInterpreter, Constructor, constr, match_expr,
    BOOL_TRUE, BOOL_FALSE, bool_match,
    NAT_ZERO, nat_succ, nat, nat_match, nat_to_int,
    list_nil, list_cons, list_match,
    option_none, option_some, option_match,
    result_ok, result_err, result_match,
    build_nat_add, build_nat_mul, build_factorial,
)


# ═══════════════════════════════════════════════════════════════
# SOURCE SPANS
# ═══════════════════════════════════════════════════════════════

class Span:
    """Source location for error messages."""
    __slots__ = ('file', 'line', 'col', 'end_line', 'end_col')
    def __init__(self, file="<input>", line=0, col=0, end_line=0, end_col=0):
        self.file = file
        self.line = line
        self.col = col
        self.end_line = end_line or line
        self.end_col = end_col or col

    def __repr__(self):
        if self.file == "<input>":
            return f"{self.line}:{self.col}"
        return f"{self.file}:{self.line}:{self.col}"

    def merge(self, other):
        return Span(self.file, self.line, self.col, other.end_line, other.end_col)


# ═══════════════════════════════════════════════════════════════
# TOKENS
# ═══════════════════════════════════════════════════════════════

class TK:
    INT     = "INT"
    FLOAT   = "FLOAT"
    STRING  = "STRING"
    IDENT   = "IDENT"
    CONSTR  = "CONSTR"
    LAMBDA  = "LAMBDA"
    PI      = "PI"
    FIX     = "FIX"
    LET     = "LET"
    IN      = "IN"
    IF      = "IF"
    THEN    = "THEN"
    ELSE    = "ELSE"
    MATCH   = "MATCH"
    DEF     = "DEF"
    TYPE    = "TYPE"
    MODULE  = "MODULE"
    IMPORT  = "IMPORT"
    OPEN    = "OPEN"
    WHERE   = "WHERE"
    ARROW   = "ARROW"
    DARROW  = "DARROW"
    PIPE    = "PIPE"
    COLON   = "COLON"
    DOT     = "DOT"
    COMMA   = "COMMA"
    EQ      = "EQ"
    LPAREN  = "LPAREN"
    RPAREN  = "RPAREN"
    LBRACE  = "LBRACE"
    RBRACE  = "RBRACE"
    LBRACK  = "LBRACK"
    RBRACK  = "RBRACK"
    BANG    = "BANG"
    AT      = "AT"
    UNDER   = "UNDER"
    PLUS    = "PLUS"
    MINUS   = "MINUS"
    STAR    = "STAR"
    SLASH   = "SLASH"
    PERCENT = "PERCENT"
    EQEQ    = "EQEQ"
    NEQ     = "NEQ"
    LT      = "LT"
    GT      = "GT"
    LEQ     = "LEQ"
    GEQ     = "GEQ"
    CONCAT  = "CONCAT"
    AND     = "AND"
    OR      = "OR"
    SEMI    = "SEMI"
    EOF     = "EOF"


class Token:
    __slots__ = ('kind', 'value', 'line', 'col', 'file')
    def __init__(self, kind, value=None, line=0, col=0, file="<input>"):
        self.kind = kind
        self.value = value
        self.line = line
        self.col = col
        self.file = file
    def __repr__(self):
        return f"Token({self.kind}, {self.value!r}, {self.line}:{self.col})"
    @property
    def span(self):
        return Span(self.file, self.line, self.col)


KEYWORDS = {
    "fun": TK.LAMBDA, "fn": TK.LAMBDA,
    "forall": TK.PI,
    "fix": TK.FIX, "rec": TK.FIX,
    "let": TK.LET, "in": TK.IN,
    "if": TK.IF, "then": TK.THEN, "else": TK.ELSE,
    "match": TK.MATCH,
    "def": TK.DEF, "type": TK.TYPE,
    "module": TK.MODULE, "import": TK.IMPORT, "open": TK.OPEN,
    "where": TK.WHERE,
}

UNICODE_KW = {'λ': TK.LAMBDA, '\\': TK.LAMBDA, 'Π': TK.PI, 'μ': TK.FIX, '→': TK.ARROW, '⇒': TK.DARROW}


# ═══════════════════════════════════════════════════════════════
# LEXER
# ═══════════════════════════════════════════════════════════════

class LexError(Exception):
    def __init__(self, msg, span=None):
        self.span = span
        super().__init__(msg)


def tokenize(source, filename="<input>"):
    tokens = []
    i = 0; line = 1; col = 1

    def emit(kind, value=None):
        tokens.append(Token(kind, value, line, col, filename))

    while i < len(source):
        ch = source[i]
        if ch in ' \t\r': i += 1; col += 1; continue
        if ch == '\n': i += 1; line += 1; col = 1; continue

        # Line comment
        if ch == '-' and i+1 < len(source) and source[i+1] == '-':
            while i < len(source) and source[i] != '\n': i += 1
            continue

        # Block comment {- ... -}
        if ch == '{' and i+1 < len(source) and source[i+1] == '-':
            depth = 1; i += 2; col += 2
            while i < len(source) and depth > 0:
                if source[i] == '{' and i+1 < len(source) and source[i+1] == '-': depth += 1; i += 2; col += 2
                elif source[i] == '-' and i+1 < len(source) and source[i+1] == '}': depth -= 1; i += 2; col += 2
                elif source[i] == '\n': i += 1; line += 1; col = 1
                else: i += 1; col += 1
            continue

        # Multi-char operators
        if i+1 < len(source):
            two = source[i:i+2]
            tw_map = {'->': TK.ARROW, '=>': TK.DARROW, '++': TK.CONCAT, '==': TK.EQEQ,
                      '!=': TK.NEQ, '<=': TK.LEQ, '>=': TK.GEQ, '&&': TK.AND, '||': TK.OR}
            if two in tw_map: emit(tw_map[two], two); i += 2; col += 2; continue

        # Unicode keywords
        if ch in UNICODE_KW: emit(UNICODE_KW[ch], ch); i += 1; col += 1; continue

        # Single-char
        sym_map = {'(': TK.LPAREN, ')': TK.RPAREN, '{': TK.LBRACE, '}': TK.RBRACE,
                   '[': TK.LBRACK, ']': TK.RBRACK, ':': TK.COLON, '.': TK.DOT,
                   ',': TK.COMMA, '=': TK.EQ, '|': TK.PIPE, '!': TK.BANG, '@': TK.AT,
                   '_': TK.UNDER, '+': TK.PLUS, '-': TK.MINUS, '*': TK.STAR,
                   '/': TK.SLASH, '%': TK.PERCENT, '<': TK.LT, '>': TK.GT, ';': TK.SEMI}
        if ch in sym_map: emit(sym_map[ch], ch); i += 1; col += 1; continue

        # String
        if ch == '"':
            j = i+1; s = []
            while j < len(source) and source[j] != '"':
                if source[j] == '\\' and j+1 < len(source):
                    esc_map = {'n': '\n', 't': '\t', 'r': '\r', '\\': '\\', '"': '"'}
                    s.append(esc_map.get(source[j+1], source[j+1])); j += 2
                else:
                    if source[j] == '\n': line += 1; col = 0
                    s.append(source[j]); j += 1
            if j >= len(source):
                raise LexError(f"Unterminated string literal", Span(filename, line, col))
            emit(TK.STRING, ''.join(s)); col += j-i+1; i = j+1; continue

        # Number
        if ch.isdigit():
            j = i
            while j < len(source) and source[j].isdigit(): j += 1
            if j < len(source) and source[j] == '.' and j+1 < len(source) and source[j+1].isdigit():
                j += 1
                while j < len(source) and source[j].isdigit(): j += 1
                emit(TK.FLOAT, float(source[i:j]))
            else:
                emit(TK.INT, int(source[i:j]))
            col += j-i; i = j; continue

        # Identifier / keyword / constructor
        if ch.isalpha() or ch == '_':
            j = i
            while j < len(source) and (source[j].isalnum() or source[j] in "_'"): j += 1
            word = source[i:j]
            if word in KEYWORDS: emit(KEYWORDS[word], word)
            elif word[0].isupper(): emit(TK.CONSTR, word)
            else: emit(TK.IDENT, word)
            col += j-i; i = j; continue

        raise LexError(f"Unexpected character '{ch}'", Span(filename, line, col))

    tokens.append(Token(TK.EOF, None, line, col, filename))
    return tokens


# ═══════════════════════════════════════════════════════════════
# PARSER
# ═══════════════════════════════════════════════════════════════

class ParseError(Exception):
    def __init__(self, msg, span=None):
        self.span = span
        if span and span.line:
            msg = f"{span}: {msg}"
        super().__init__(msg)


BINOP_INFO = {
    TK.OR:      (1, 'left', PrimOp.BOOL_OR),
    TK.AND:     (2, 'left', PrimOp.BOOL_AND),
    TK.EQEQ:   (3, 'left', PrimOp.INT_EQ),
    TK.NEQ:     (3, 'left', None),
    TK.LT:     (4, 'left', PrimOp.INT_LT),
    TK.GT:     (4, 'left', PrimOp.INT_GT),
    TK.LEQ:    (4, 'left', None),
    TK.GEQ:    (4, 'left', None),
    TK.PLUS:    (5, 'left', PrimOp.INT_ADD),
    TK.MINUS:   (5, 'left', PrimOp.INT_SUB),
    TK.CONCAT:  (5, 'left', PrimOp.STR_CONCAT),
    TK.STAR:    (6, 'left', PrimOp.INT_MUL),
    TK.SLASH:   (6, 'left', PrimOp.INT_DIV),
    TK.PERCENT: (6, 'left', PrimOp.INT_MOD),
}

# Constructor registry — (index, arity).  Mutable: type decls add to this.
KNOWN_CONSTRUCTORS = {
    "True": (0, 0), "False": (1, 0),
    "Zero": (0, 0), "Succ":  (1, 1),
    "None": (0, 0), "Some":  (1, 1),
    "Nil":  (0, 0), "Cons":  (1, 2),
    "Ok":   (0, 1), "Err":   (1, 1),
    "Leaf": (0, 0), "Branch": (1, 3),
    "Lit":  (0, 1), "Add":   (1, 2), "Mul": (2, 2),
    "Pair": (0, 2),
}

# Type registry — type_name → [(constr_name, arity)]
TYPE_REGISTRY = {
    "Bool":   [("True", 0), ("False", 0)],
    "Nat":    [("Zero", 0), ("Succ", 1)],
    "Option": [("None", 0), ("Some", 1)],
    "List":   [("Nil", 0), ("Cons", 2)],
    "Result": [("Ok", 1), ("Err", 1)],
    "Tree":   [("Leaf", 0), ("Branch", 3)],
    "Expr":   [("Lit", 1), ("Add", 2), ("Mul", 2)],
    "Pair":   [("Pair", 2)],
}

BUILTINS = {
    "print":  lambda: B.prim(PrimOp.PRINT),
    "not":    lambda: B.prim(PrimOp.BOOL_NOT),
    "neg":    lambda: B.prim(PrimOp.INT_NEG),
    "strlen": lambda: B.prim(PrimOp.STR_LEN),
    "true":   lambda: Node(Tag.PRIM, prim_op=PrimOp.BOOL_TRUE),
    "false":  lambda: Node(Tag.PRIM, prim_op=PrimOp.BOOL_FALSE),
    "unit":   lambda: B.unit(),
}


class Scope:
    def __init__(self, parent=None):
        self.parent = parent
        self.bindings = {}
        self.depth = parent.depth if parent else 0

    def bind(self, name):
        child = Scope(self)
        child.depth = self.depth + 1
        child.bindings = {name: child.depth}
        return child

    def resolve(self, name, _origin_depth=None):
        if _origin_depth is None: _origin_depth = self.depth
        if name in self.bindings: return _origin_depth - self.bindings[name]
        if self.parent: return self.parent.resolve(name, _origin_depth)
        return None


# ── Import resolver ──

LIB_DIRS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'),
    'lib', '.',
]

_import_cache = {}

def resolve_import(name, search_dirs=None):
    """Resolve an import name to a file path."""
    if name in _import_cache:
        return _import_cache[name]
    dirs = search_dirs or LIB_DIRS
    for d in dirs:
        for ext in ['.xi-src', '.xi']:
            path = os.path.join(d, name + ext)
            if os.path.exists(path):
                _import_cache[name] = path
                return path
    return None


def load_import(name, search_dirs=None):
    """Load and parse an import, returning definitions dict."""
    path = resolve_import(name, search_dirs)
    if path is None:
        raise ParseError(f"Cannot find module '{name}' in {LIB_DIRS}")
    with open(path) as f:
        source = f.read()
    tokens = tokenize(source, filename=path)
    parser = Parser(tokens)
    return parser.parse_program()


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.scope = Scope()
        self.definitions = {}
        self.constructors = dict(KNOWN_CONSTRUCTORS)  # local copy
        self.type_registry = dict(TYPE_REGISTRY)
        self.source_lines = None  # set by Compiler for error display
        self.imported = set()

    def peek(self, offset=0):
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else self.tokens[-1]

    def at(self, *kinds): return self.peek().kind in kinds
    def advance(self):
        tok = self.tokens[self.pos]; self.pos += 1; return tok

    def expect(self, kind):
        tok = self.advance()
        if tok.kind != kind:
            raise ParseError(
                f"Expected {kind}, got {tok.kind} ({tok.value!r})",
                tok.span)
        return tok

    def match_tok(self, *kinds):
        if self.peek().kind in kinds: return self.advance()
        return None

    def error(self, msg, tok=None):
        tok = tok or self.peek()
        raise ParseError(msg, tok.span)

    # ── Entry points ──

    def parse_program(self):
        while not self.at(TK.EOF):
            if self.at(TK.MODULE):
                self.advance(); self.expect(TK.CONSTR)
            elif self.at(TK.IMPORT):
                self._parse_import()
            elif self.at(TK.OPEN):
                self.advance(); self.expect(TK.CONSTR)
            elif self.at(TK.DEF):
                self._parse_def()
            elif self.at(TK.TYPE):
                self._parse_type_decl()
            elif self.at(TK.SEMI):
                self.advance()
            else:
                self.error(f"Expected declaration (def/type/import), got {self.peek().kind}")
        return self.definitions

    def _parse_import(self):
        self.advance()  # consume 'import'
        name_tok = self.expect(TK.CONSTR)
        name = name_tok.value
        if name in self.imported:
            return  # skip duplicate imports
        self.imported.add(name)
        try:
            defs = load_import(name)
            for k, v in defs.items():
                self.definitions[k] = v
                self.scope = self.scope.bind(k)
        except (ParseError, LexError, FileNotFoundError) as e:
            raise ParseError(f"Error importing '{name}': {e}", name_tok.span)

    def _parse_def(self):
        self.advance()  # consume 'def'
        name = self.expect(TK.IDENT).value
        # Optional function params: def f x y = body  →  def f = λx. λy. body
        params = []
        while self.at(TK.IDENT) and self.peek().value not in BUILTINS:
            params.append(self.advance().value)
        if self.at(TK.LPAREN) and self.peek(1).kind == TK.IDENT and self.peek(2).kind == TK.COLON:
            # Typed params: def f (x : Int) = ...
            while self.at(TK.LPAREN):
                self.advance()
                pname = self.expect(TK.IDENT).value
                self.expect(TK.COLON)
                _pty = self.parse_expr()
                self.expect(TK.RPAREN)
                params.append(pname)
        if self.match_tok(TK.COLON):
            _ty = self.parse_expr()
        self.expect(TK.EQ)
        # Bind params for body
        saved = self.scope
        for p in params:
            self.scope = self.scope.bind(p)
        body = self.parse_expr()
        self.scope = saved
        # Wrap in lambdas
        for p in reversed(params):
            body = B.lam(B.universe(0), body)
        self.definitions[name] = body
        self.scope = self.scope.bind(name)

    def _parse_type_decl(self):
        """Parse: type Name params = Constr1 args | Constr2 args | ..."""
        self.advance()  # consume 'type'
        type_name = self.expect(TK.CONSTR).value
        # Optional type parameters
        type_params = []
        while self.at(TK.IDENT):
            type_params.append(self.advance().value)
        self.expect(TK.EQ)
        # Parse constructors
        constrs = []
        self.match_tok(TK.PIPE)  # optional leading pipe
        while True:
            cname = self.expect(TK.CONSTR).value
            # Count constructor arguments (types)
            arity = 0
            while self.at(TK.CONSTR, TK.IDENT, TK.LPAREN):
                if self.at(TK.LPAREN):
                    # Parenthesized type like (List a)
                    depth = 0
                    while True:
                        if self.at(TK.LPAREN): depth += 1
                        elif self.at(TK.RPAREN): depth -= 1
                        self.advance()
                        if depth == 0: break
                else:
                    self.advance()
                arity += 1
            constrs.append((cname, arity))
            if not self.match_tok(TK.PIPE):
                break
        # Register type and constructors
        self.type_registry[type_name] = constrs
        for idx, (cname, arity) in enumerate(constrs):
            self.constructors[cname] = (idx, arity)

    def parse_single(self):
        expr = self.parse_expr()
        if not self.at(TK.EOF):
            self.error(f"Unexpected token after expression: {self.peek().kind}")
        return expr

    # ── Expressions ──

    def parse_expr(self):
        if self.at(TK.LAMBDA): return self.parse_lambda()
        if self.at(TK.PI): return self.parse_pi()
        if self.at(TK.FIX): return self.parse_fix()
        if self.at(TK.LET): return self.parse_let()
        if self.at(TK.IF): return self.parse_if()
        if self.at(TK.MATCH): return self.parse_match()
        if self.at(TK.BANG): return self.parse_effect()
        return self.parse_infix(0)

    def parse_lambda(self):
        self.advance()
        params = self.parse_binders()
        self.expect(TK.DOT)
        saved = self.scope
        for name, ty in params: self.scope = self.scope.bind(name)
        body = self.parse_expr()
        self.scope = saved
        result = body
        for name, ty in reversed(params):
            result = B.lam(ty if ty else B.universe(0), result)
        return result

    def parse_binders(self):
        params = []
        while True:
            if self.at(TK.LPAREN):
                self.advance()
                name = self.expect(TK.IDENT).value
                self.expect(TK.COLON)
                ty = self.parse_expr()
                self.expect(TK.RPAREN)
                params.append((name, ty))
            elif self.at(TK.IDENT) and self.peek().value not in BUILTINS:
                params.append((self.advance().value, None))
            else:
                break
        if not params: self.error("Expected parameter name")
        return params

    def parse_pi(self):
        self.advance()
        self.expect(TK.LPAREN)
        name = self.expect(TK.IDENT).value
        self.expect(TK.COLON)
        domain = self.parse_expr()
        self.expect(TK.RPAREN)
        self.expect(TK.DOT)
        saved = self.scope
        self.scope = self.scope.bind(name)
        codomain = self.parse_expr()
        self.scope = saved
        return B.pi(domain, codomain)

    def parse_fix(self):
        self.advance()
        name = self.expect(TK.IDENT).value
        self.expect(TK.DOT)
        saved = self.scope
        self.scope = self.scope.bind(name)
        body = self.parse_expr()
        self.scope = saved
        return B.fix(B.universe(0), body)

    def parse_let(self):
        self.advance()
        name = self.expect(TK.IDENT).value
        type_ann = None
        if self.match_tok(TK.COLON): type_ann = self.parse_expr()
        self.expect(TK.EQ)
        value = self.parse_expr()
        self.expect(TK.IN)
        saved = self.scope
        self.scope = self.scope.bind(name)
        body = self.parse_expr()
        self.scope = saved
        return B.app(B.lam(type_ann if type_ann else B.universe(0), body), value)

    def parse_if(self):
        self.advance()
        cond = self.parse_expr()
        self.expect(TK.THEN)
        then_br = self.parse_expr()
        self.expect(TK.ELSE)
        else_br = self.parse_expr()
        return bool_match(cond, then_br, else_br)

    def parse_match(self):
        self.advance()
        scrutinee = self.parse_app()
        self.expect(TK.LBRACE)
        branches = []
        self.match_tok(TK.PIPE)
        while not self.at(TK.RBRACE):
            idx, bound_vars = self.parse_pattern()
            if not self.match_tok(TK.ARROW):
                if not self.match_tok(TK.DARROW):
                    self.error("Expected → or => after pattern")
            saved = self.scope
            for v in bound_vars: self.scope = self.scope.bind(v)
            body = self.parse_expr()
            self.scope = saved
            result = body
            for _ in reversed(bound_vars): result = B.lam(B.universe(0), result)
            branches.append((idx, result))
            self.match_tok(TK.PIPE)
        self.expect(TK.RBRACE)
        sorted_branches = sorted(branches, key=lambda b: b[0])
        return match_expr(scrutinee, [b[1] for b in sorted_branches])

    def parse_pattern(self):
        if self.at(TK.UNDER): self.advance(); return (0, [])
        if not self.at(TK.CONSTR, TK.IDENT):
            self.error("Expected constructor in pattern")
        tok = self.advance()
        name = tok.value
        if name not in self.constructors:
            raise ParseError(f"Unknown constructor '{name}'", tok.span)
        idx, arity = self.constructors[name]
        bound_vars = []
        for _ in range(arity):
            if self.at(TK.IDENT): bound_vars.append(self.advance().value)
            elif self.at(TK.UNDER): self.advance(); bound_vars.append(f"_anon_{len(bound_vars)}")
            else: break
        return (idx, bound_vars)

    def parse_effect(self):
        self.advance()
        self.expect(TK.LBRACE)
        eff_name = self.expect(TK.CONSTR).value
        self.expect(TK.RBRACE)
        eff_map = {"IO": Effect.IO, "Mut": Effect.MUT, "Exn": Effect.EXN,
                   "Conc": Effect.CONC, "Pure": Effect.PURE}
        inner = self.parse_expr()
        return B.effect(inner, eff_map.get(eff_name, Effect.IO))

    # ── Pratt precedence climbing ──

    def parse_infix(self, min_prec):
        left = self.parse_app()
        while True:
            tok = self.peek()
            if tok.kind not in BINOP_INFO: break
            prec, assoc, prim_op = BINOP_INFO[tok.kind]
            if prec < min_prec: break
            op_kind = self.advance().kind
            right = self.parse_infix(prec + 1 if assoc == 'left' else prec)
            if prim_op is not None:
                left = B.app(B.app(B.prim(prim_op), left), right)
            elif op_kind == TK.NEQ:
                left = B.app(B.prim(PrimOp.BOOL_NOT), B.app(B.app(B.prim(PrimOp.INT_EQ), left), right))
            elif op_kind == TK.LEQ:
                left = B.app(B.prim(PrimOp.BOOL_NOT), B.app(B.app(B.prim(PrimOp.INT_GT), left), right))
            elif op_kind == TK.GEQ:
                left = B.app(B.prim(PrimOp.BOOL_NOT), B.app(B.app(B.prim(PrimOp.INT_LT), left), right))
        if self.at(TK.ARROW) and min_prec == 0:
            self.advance()
            right = self.parse_expr()
            return B.pi(left, right)
        return left

    def parse_app(self):
        func = self.parse_atom()
        if func is None: self.error("Expected expression")
        while True:
            arg = self.try_parse_atom()
            if arg is None: break
            func = B.app(func, arg)
        return func

    def try_parse_atom(self):
        if self.at(TK.INT, TK.FLOAT, TK.STRING, TK.IDENT, TK.CONSTR, TK.LPAREN, TK.UNDER):
            return self.parse_atom()
        return None

    def parse_atom(self):
        tok = self.peek()
        if tok.kind == TK.INT: self.advance(); return B.int_lit(tok.value)
        if tok.kind == TK.FLOAT: self.advance(); return Node(Tag.PRIM, prim_op=PrimOp.FLOAT_LIT, data=tok.value)
        if tok.kind == TK.STRING: self.advance(); return B.str_lit(tok.value)
        if tok.kind == TK.UNDER: self.advance(); return B.universe(0)
        if tok.kind == TK.LPAREN:
            self.advance()
            if self.at(TK.RPAREN): self.advance(); return B.unit()
            expr = self.parse_expr()
            if self.match_tok(TK.COLON): _ty = self.parse_expr()
            self.expect(TK.RPAREN)
            return expr
        if tok.kind == TK.CONSTR:
            self.advance(); name = tok.value
            if name in self.constructors:
                idx, arity = self.constructors[name]
                return constr(idx)
            return Node(Tag.IND, data=name)
        if tok.kind == TK.IDENT:
            self.advance(); name = tok.value
            if name in BUILTINS: return BUILTINS[name]()
            if name in self.definitions: return self.definitions[name]
            idx = self.scope.resolve(name)
            if idx is not None: return B.var(idx)
            raise ParseError(f"Undefined variable '{name}'", tok.span)
        return None


# ═══════════════════════════════════════════════════════════════
# COMPILER FACADE
# ═══════════════════════════════════════════════════════════════

class Compiler:
    def __init__(self, search_dirs=None):
        self.search_dirs = search_dirs

    def _make_parser(self, tokens, defs=None):
        p = Parser(tokens)
        if defs:
            p.definitions = dict(defs)
        return p

    def compile_expr(self, source, filename="<input>", defs=None):
        tokens = tokenize(source, filename)
        p = self._make_parser(tokens, defs)
        return p.parse_single()

    def compile_program(self, source, filename="<input>"):
        tokens = tokenize(source, filename)
        p = self._make_parser(tokens)
        return p.parse_program()

    def compile(self, source, filename="<input>"):
        """Backwards-compatible: returns (Node, bytes)."""
        graph = self.compile_expr(source, filename)
        return graph, serialize(graph)

    def compile_to_binary(self, source, filename="<input>"):
        return self.compile(source, filename)

    def run_expr(self, source, defs=None):
        graph = self.compile_expr(source, defs=defs)
        return MatchInterpreter().run(graph)

    def run_program(self, source, entry="main"):
        defs = self.compile_program(source)
        if entry not in defs:
            raise ParseError(f"No '{entry}' definition found")
        return MatchInterpreter().run(defs[entry])


# ═══════════════════════════════════════════════════════════════
# PRETTY ERROR DISPLAY
# ═══════════════════════════════════════════════════════════════

def format_error(source, error):
    """Format a parse/lex error with source context."""
    span = getattr(error, 'span', None)
    if not span or not span.line:
        return str(error)

    lines = source.split('\n')
    line_idx = span.line - 1
    if line_idx < 0 or line_idx >= len(lines):
        return str(error)

    src_line = lines[line_idx]
    pointer = ' ' * max(0, span.col - 1) + '^'

    parts = [str(error), f"  {line_idx+1} | {src_line}", f"      {pointer}"]
    return '\n'.join(parts)


# ═══════════════════════════════════════════════════════════════
# DEMO
# ═══════════════════════════════════════════════════════════════

def run_demo():
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║  Ξ (Xi) Compiler v0.3 — Surface Syntax + ADTs + Imports   ║")
    print("║  Copyright (c) 2026 Alex P. Slaby — MIT License          ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")

    c = Compiler()
    interp = MatchInterpreter()
    passed = 0
    failed = 0

    def check(name, source, expected):
        nonlocal passed, failed
        try:
            result = c.run_expr(source)
            if isinstance(result, (Constructor, Node)) and isinstance(expected, int):
                result = nat_to_int(interp, result)
            ok = result == expected
            print(f"  {'✓' if ok else '✗'} {name}")
            if ok: passed += 1
            else:
                print(f"    Expected: {expected}, Got: {result}")
                failed += 1
        except Exception as e:
            print(f"  ✗ {name}")
            print(f"    Error: {type(e).__name__}: {e}")
            failed += 1

    def check_prog(name, source, expected, entry="main"):
        nonlocal passed, failed
        try:
            result = c.run_program(source, entry)
            if isinstance(result, (Constructor, Node)) and isinstance(expected, int):
                result = nat_to_int(interp, result)
            ok = result == expected
            print(f"  {'✓' if ok else '✗'} {name}")
            if ok: passed += 1
            else:
                print(f"    Expected: {expected}, Got: {result}")
                failed += 1
        except Exception as e:
            print(f"  ✗ {name}")
            print(f"    Error: {type(e).__name__}: {e}")
            failed += 1

    # ── Literals ──
    print("  ── Literals ──\n")
    check("integer", "42", 42)
    check("negative", "0 - 7", -7)
    check("string", '"hello"', "hello")

    # ── Operators ──
    print("\n  ── Operators (with precedence) ──\n")
    check("addition", "2 + 3", 5)
    check("precedence *>+", "2 + 3 * 4", 14)
    check("parens", "(2 + 3) * 4", 20)
    check("comparison <", "3 < 5", True)
    check("equality ==", "7 == 7", True)
    check("string ++", '"a" ++ "b"', "ab")
    check("strlen", 'strlen "hello"', 5)
    check("modulo", "17 % 5", 2)
    check("nested arith", "((1 + 2) * 3 - 4) * 5", 25)

    # ── Lambda ──
    print("\n  ── Lambda ──\n")
    check("identity", "(λx. x) 42", 42)
    check("double", "(λx. x + x) 21", 42)
    check("typed λ", "(λ(x : Int). x * x) 7", 49)
    check("multi-binder", "(λx y. x + y) 3 4", 7)
    check("curried", "(λ(x : Int). λ(y : Int). x * y) 6 7", 42)
    check("nested app", "(λf. f 5) (λx. x + 1)", 6)

    # ── Let ──
    print("\n  ── Let binding ──\n")
    check("let simple", "let x = 5 in x + x", 10)
    check("let nested", "let x = 3 in let y = 4 in x * y", 12)
    check("let lambda", "let double = λx. x + x in double 21", 42)

    # ── Constructors & match ──
    print("\n  ── Constructors & pattern matching ──\n")
    check("match Zero", "match Zero { Zero → 1 | Succ n → 0 }", 1)
    check("match Succ", "match Succ Zero { Zero → 0 | Succ n → 1 }", 1)
    check("extract pred", "match Succ (Succ (Succ Zero)) { Zero → Zero | Succ k → k }", 2)
    check("if true", "if True then 42 else 0", 42)
    check("if false", "if False then 42 else 0", 0)
    check("option none", "match None { None → 0 | Some x → x }", 0)
    check("option some", "match Some 99 { None → 0 | Some x → x }", 99)

    # ── Fix (recursion) ──
    print("\n  ── Recursion (fix) ──\n")
    check("fix: add 2 3", """
        let add = fix self. λn. λm. match n { Zero → m | Succ k → Succ (self k m) }
        in add (Succ (Succ Zero)) (Succ (Succ (Succ Zero)))
    """, 5)

    check("fix: fib 7", """
        let add = fix self. λn. λm. match n { Zero → m | Succ k → Succ (self k m) }
        in let fib = fix self. λn. match n {
            Zero → Zero
          | Succ k → match k {
              Zero → Succ Zero
            | Succ j → add (self (Succ j)) (self j)
          }
        }
        in fib (Succ (Succ (Succ (Succ (Succ (Succ (Succ Zero)))))))
    """, 13)

    # ── Comments ──
    print("\n  ── Comments ──\n")
    check("line comment", "42 -- ignore this", 42)
    check("block comment", "{- block -} 42", 42)
    check("nested block", "{- {- nested -} -} 42", 42)

    # ── If + comparison ──
    print("\n  ── If + comparison ──\n")
    check("if 3<5", "if 3 < 5 then 1 else 0", 1)
    check("if 5<3", "if 5 < 3 then 1 else 0", 0)

    # ── User-defined ADT ──
    print("\n  ── Algebraic Data Types (type decl) ──\n")

    check_prog("type Color", """
        type Color = Red | Green | Blue
        def main = match Red { Red → 1 | Green → 2 | Blue → 3 }
    """, 1)

    check_prog("type Maybe a", """
        type Maybe = Nothing | Just Int
        def main = match Just 42 { Nothing → 0 | Just x → x }
    """, 42)

    check_prog("type with 3 constrs", """
        type Shape = Circle Int | Rect Int Int | Point
        def main = match Point { Circle r → 0 | Rect w h → 0 | Point → 1 }
    """, 1)

    # ── Program with defs ──
    print("\n  ── Program (def + def with params) ──\n")

    check_prog("program: double 21", """
        def double = λx. x + x
        def main = double 21
    """, 42)

    check_prog("def with params", """
        def double x = x + x
        def main = double 21
    """, 42)

    check_prog("def multi-param", """
        def add a b = a + b
        def main = add 17 25
    """, 42)

    # ── Import ──
    print("\n  ── Import (Prelude) ──\n")

    try:
        result = c.run_program("""
            import Prelude
            def main = add (Succ (Succ Zero)) (Succ (Succ (Succ Zero)))
        """)
        result = nat_to_int(interp, result)
        ok = result == 5
        print(f"  {'✓' if ok else '✗'} import Prelude: add 2 3 → {result}")
        if ok: passed += 1
        else: failed += 1
    except Exception as e:
        print(f"  ✗ import Prelude: {type(e).__name__}: {e}")
        failed += 1

    try:
        result = c.run_program("""
            import Prelude
            def main = fib (Succ (Succ (Succ (Succ (Succ (Succ Zero))))))
        """)
        result = nat_to_int(interp, result)
        ok = result == 8
        print(f"  {'✓' if ok else '✗'} import Prelude: fib 6 → {result}")
        if ok: passed += 1
        else: failed += 1
    except Exception as e:
        print(f"  ✗ import Prelude: {type(e).__name__}: {e}")
        failed += 1

    # ── Error messages ──
    print("\n  ── Error messages ──\n")

    try:
        c.run_expr("1 + + 2")
        failed += 1
    except (ParseError, LexError) as e:
        msg = format_error("1 + + 2", e)
        has_loc = "1:" in str(e)
        print(f"  {'✓' if has_loc else '✗'} parse error has location: {e}")
        if has_loc: passed += 1
        else: failed += 1

    try:
        c.run_expr("xyz")
        failed += 1
    except ParseError as e:
        has_name = "xyz" in str(e)
        print(f"  {'✓' if has_name else '✗'} undefined var error: {e}")
        if has_name: passed += 1
        else: failed += 1

    print(f"\n  ═══════════════════════════════════")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"  ═══════════════════════════════════\n")
    return failed == 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "demo":
            ok = run_demo(); sys.exit(0 if ok else 1)
        elif cmd == "compile" and len(sys.argv) > 2:
            with open(sys.argv[2]) as f: source = f.read()
            g, b = Compiler().compile(source, sys.argv[2])
            out = sys.argv[2].replace('.xi-src', '.xi')
            with open(out, 'wb') as f: f.write(b)
            print(f"Compiled {sys.argv[2]} → {out} ({len(b)} bytes)")
        elif cmd == "run" and len(sys.argv) > 2:
            with open(sys.argv[2]) as f: source = f.read()
            try: print(Compiler().run_program(source))
            except ParseError: print(Compiler().run_expr(source))
        elif cmd == "tokenize" and len(sys.argv) > 2:
            for tok in tokenize(sys.argv[2]): print(tok)
        else:
            print("Usage: xi_compiler.py [demo|compile|run|tokenize] [args]")
    else:
        run_demo()
