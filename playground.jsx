import { useState, useCallback, useRef, useEffect } from "react";

// ═══════════════════════════════════════════════════════════════
// MINI XI INTERPRETER (JavaScript port of core Xi)
// ═══════════════════════════════════════════════════════════════

const T = { LAM: 1, APP: 2, PI: 3, VAR: 4, PRIM: 5, FIX: 6, IND: 7, EFF: 8, UNI: 9, INT: 10, STR: 11, BOOL: 12, MATCH: 13 };
const P = {
  ADD: 1, SUB: 2, MUL: 3, DIV: 4, MOD: 5,
  EQ: 6, LT: 7, GT: 8, NEG: 9,
  NOT: 10, AND: 11, OR: 12,
  CONCAT: 13, LEN: 14, PRINT: 15,
};

const nd = (tag, props = {}) => ({ tag, ...props });
const INT = (n) => nd(T.INT, { val: n });
const STR = (s) => nd(T.STR, { val: s });
const BOOL = (b) => nd(T.BOOL, { val: b });
const VAR = (i) => nd(T.VAR, { idx: i });
const LAM = (body, tyName) => nd(T.LAM, { body, tyName: tyName || "?" });
const APP = (fn, arg) => nd(T.APP, { fn, arg });
const PRIM = (op) => nd(T.PRIM, { op });
const FIX = (body) => nd(T.FIX, { body });
const CONSTR = (idx) => nd(T.IND, { cidx: idx, cargs: [] });
const MATCH = (scrut, branches) => nd(T.MATCH, { scrut, branches });

function subst(node, depth, val) {
  if (!node) return node;
  switch (node.tag) {
    case T.VAR:
      if (node.idx === depth) return val;
      if (node.idx > depth) return VAR(node.idx - 1);
      return node;
    case T.LAM: return LAM(subst(node.body, depth + 1, val), node.tyName);
    case T.APP: return APP(subst(node.fn, depth, val), subst(node.arg, depth, val));
    case T.FIX: return FIX(subst(node.body, depth + 1, val));
    case T.MATCH: return MATCH(subst(node.scrut, depth, val), node.branches.map(b => subst(b, depth, val)));
    default: return node;
  }
}

// One reduction step (returns null if no step possible)
function step(node) {
  if (!node) return null;
  switch (node.tag) {
    case T.APP:
      if (node.fn.tag === T.LAM) return { result: subst(node.fn.body, 0, node.arg), rule: "β-reduce" };
      if (node.fn.tag === T.PRIM && node.arg.tag === T.INT) {
        // Partial application of binary prim — return curried
        return null;
      }
      if (node.fn.tag === T.APP && node.fn.fn.tag === T.PRIM) {
        const op = node.fn.fn.op, a = node.fn.arg, b = node.arg;
        if (a.tag === T.INT && b.tag === T.INT) {
          const av = a.val, bv = b.val;
          const ops = {
            [P.ADD]: INT(av + bv), [P.SUB]: INT(av - bv), [P.MUL]: INT(av * bv),
            [P.DIV]: bv !== 0 ? INT(Math.trunc(av / bv)) : null,
            [P.MOD]: bv !== 0 ? INT(av % bv) : null,
            [P.EQ]: BOOL(av === bv), [P.LT]: BOOL(av < bv), [P.GT]: BOOL(av > bv),
          };
          if (ops[op] !== undefined) return { result: ops[op], rule: `δ-${primName(op)}` };
        }
        if (a.tag === T.STR && b.tag === T.STR && op === P.CONCAT)
          return { result: STR(a.val + b.val), rule: "δ-concat" };
        if (a.tag === T.BOOL && b.tag === T.BOOL) {
          if (op === P.AND) return { result: BOOL(a.val && b.val), rule: "δ-and" };
          if (op === P.OR) return { result: BOOL(a.val || b.val), rule: "δ-or" };
        }
      }
      if (node.fn.tag === T.PRIM) {
        const op = node.fn.op, a = node.arg;
        if (op === P.NEG && a.tag === T.INT) return { result: INT(-a.val), rule: "δ-neg" };
        if (op === P.NOT && a.tag === T.BOOL) return { result: BOOL(!a.val), rule: "δ-not" };
        if (op === P.LEN && a.tag === T.STR) return { result: INT(a.val.length), rule: "δ-len" };
      }
      // Constructor application
      if (node.fn.tag === T.IND) {
        return { result: nd(T.IND, { cidx: node.fn.cidx, cargs: [...(node.fn.cargs||[]), node.arg] }), rule: "constr-app" };
      }
      const fs = step(node.fn);
      if (fs) return { result: APP(fs.result, node.arg), rule: fs.rule };
      const as = step(node.arg);
      if (as) return { result: APP(node.fn, as.result), rule: as.rule };
      return null;
    case T.FIX:
      return { result: subst(node.body, 0, node), rule: "μ-unfold" };
    case T.MATCH:
      const s = node.scrut;
      if (s.tag === T.IND && s.cidx !== undefined) {
        const br = node.branches[s.cidx];
        if (br) {
          let result = br;
          const args = s.cargs || [];
          for (const a of args) result = APP(result, a);
          return { result, rule: `ι-match[${s.cidx}]` };
        }
      }
      const ss = step(node.scrut);
      if (ss) return { result: MATCH(ss.result, node.branches), rule: ss.rule };
      return null;
    default: return null;
  }
}

function evaluate(node, maxSteps = 500) {
  const trace = [{ node, rule: "start" }];
  let current = node;
  for (let i = 0; i < maxSteps; i++) {
    const s = step(current);
    if (!s) break;
    current = s.result;
    trace.push({ node: current, rule: s.rule });
  }
  return trace;
}

function primName(op) {
  const m = { [P.ADD]:"+", [P.SUB]:"-", [P.MUL]:"*", [P.DIV]:"/", [P.MOD]:"%",
    [P.EQ]:"==", [P.LT]:"<", [P.GT]:">", [P.NEG]:"neg", [P.NOT]:"not",
    [P.AND]:"&&", [P.OR]:"||", [P.CONCAT]:"++", [P.LEN]:"len", [P.PRINT]:"print" };
  return m[op] || "?";
}

// ═══════════════════════════════════════════════════════════════
// MINI PARSER
// ═══════════════════════════════════════════════════════════════

function tokenize(src) {
  const toks = []; let i = 0;
  while (i < src.length) {
    const c = src[i];
    if (" \t\n\r".includes(c)) { i++; continue; }
    if (c === '-' && src[i+1] === '-') { while (i < src.length && src[i] !== '\n') i++; continue; }
    if (c === '"') {
      let s = ""; i++;
      while (i < src.length && src[i] !== '"') { s += src[i]; i++; }
      i++; toks.push({ t: "STR", v: s }); continue;
    }
    if (/\d/.test(c)) {
      let n = ""; while (i < src.length && /\d/.test(src[i])) { n += src[i]; i++; }
      toks.push({ t: "INT", v: parseInt(n) }); continue;
    }
    if (/[a-zA-Z_]/.test(c)) {
      let w = ""; while (i < src.length && /[a-zA-Z0-9_']/.test(src[i])) { w += src[i]; i++; }
      const kw = { "let":"LET","in":"IN","if":"IF","then":"THEN","else":"ELSE","match":"MATCH",
        "fix":"FIX","rec":"FIX","fun":"LAM","def":"DEF","true":"TRUE","false":"FALSE",
        "not":"NOT","neg":"NEG","strlen":"STRLEN","True":"CONSTR","False":"CONSTR",
        "Zero":"CONSTR","Succ":"CONSTR","None":"CONSTR","Some":"CONSTR","Nil":"CONSTR","Cons":"CONSTR" };
      toks.push({ t: kw[w] || (w[0] >= 'A' && w[0] <= 'Z' ? "CONSTR" : "IDENT"), v: w }); continue;
    }
    const two = src.slice(i, i+2);
    const twoMap = { "->":"ARROW","=>":"DARROW","++":"CONCAT","==":"EQEQ","!=":"NEQ",
      "<=":"LEQ",">=":"GEQ","&&":"AND","||":"OR" };
    if (twoMap[two]) { toks.push({ t: twoMap[two], v: two }); i += 2; continue; }
    if ("λ\\".includes(c)) { toks.push({ t: "LAM", v: c }); i++; continue; }
    if (c === "μ") { toks.push({ t: "FIX", v: c }); i++; continue; }
    if (c === "→") { toks.push({ t: "ARROW", v: c }); i++; continue; }
    if (c === "⇒") { toks.push({ t: "DARROW", v: c }); i++; continue; }
    const sym = { "(":"LPAREN",")":"RPAREN","{":"LBRACE","}":"RBRACE",".":"DOT","|":"PIPE",
      "=":"EQ","+":"PLUS","-":"MINUS","*":"STAR","/":"SLASH","%":"PERCENT","<":"LT",">":"GT",":":"COLON","_":"UNDER" };
    if (sym[c]) { toks.push({ t: sym[c], v: c }); i++; continue; }
    i++; // skip unknown
  }
  toks.push({ t: "EOF", v: null });
  return toks;
}

const CONSTRS = { "True":[0,0],"False":[1,0],"Zero":[0,0],"Succ":[1,1],"None":[0,0],"Some":[1,1],"Nil":[0,0],"Cons":[1,2] };
const BUILTINS = { "not":()=>PRIM(P.NOT),"neg":()=>PRIM(P.NEG),"strlen":()=>PRIM(P.LEN),"print":()=>PRIM(P.PRINT),
  "true":()=>BOOL(true),"false":()=>BOOL(false) };

function parse(src) {
  const toks = tokenize(src);
  let pos = 0;
  const scope = [];
  const defs = {};
  const pk = () => toks[pos]; const adv = () => toks[pos++];
  const at = (...ts) => ts.includes(pk().t);
  const expect = (t) => { if (pk().t !== t) throw new Error(`Expected ${t}, got ${pk().t} (${pk().v})`); return adv(); };
  const matchT = (...ts) => ts.includes(pk().t) ? adv() : null;

  function resolve(name) {
    for (let i = scope.length - 1; i >= 0; i--) if (scope[i] === name) return scope.length - 1 - i;
    return null;
  }

  function parseExpr() {
    if (at("LAM")) return parseLam();
    if (at("FIX")) return parseFix();
    if (at("LET")) return parseLet();
    if (at("IF")) return parseIf();
    if (at("MATCH")) return parseMatch();
    return parseInfix(0);
  }

  function parseLam() {
    adv();
    const params = [];
    while (at("IDENT","LPAREN")) {
      if (at("LPAREN")) { adv(); const n = expect("IDENT").v; if (at("COLON")) { adv(); parseExpr(); } expect("RPAREN"); params.push(n); }
      else params.push(adv().v);
    }
    if (!params.length) throw new Error("Lambda needs parameters");
    expect("DOT");
    for (const p of params) scope.push(p);
    const body = parseExpr();
    for (const _ of params) scope.pop();
    let r = body;
    for (let i = params.length - 1; i >= 0; i--) r = LAM(r, params[i]);
    return r;
  }

  function parseFix() {
    adv(); const name = expect("IDENT").v; expect("DOT");
    scope.push(name); const body = parseExpr(); scope.pop();
    return FIX(body);
  }

  function parseLet() {
    adv(); const name = expect("IDENT").v;
    if (at("COLON")) { adv(); parseExpr(); }
    expect("EQ"); const val = parseExpr(); expect("IN");
    scope.push(name); const body = parseExpr(); scope.pop();
    return APP(LAM(body, name), val);
  }

  function parseIf() {
    adv(); const c = parseExpr(); expect("THEN"); const t = parseExpr(); expect("ELSE"); const e = parseExpr();
    return MATCH(c, [t, e]); // True=0, False=1
  }

  function parseMatch() {
    adv(); const scrut = parseApp(); expect("LBRACE"); matchT("PIPE");
    const branches = [];
    while (!at("RBRACE")) {
      let idx = 0, vars = [];
      if (at("CONSTR","IDENT")) {
        const name = adv().v;
        if (CONSTRS[name]) { idx = CONSTRS[name][0]; const ar = CONSTRS[name][1]; for (let i = 0; i < ar; i++) { if (at("IDENT")) vars.push(adv().v); else if (at("UNDER")) { adv(); vars.push("_"); } } }
      } else if (at("UNDER")) { adv(); }
      if (!matchT("ARROW")) matchT("DARROW");
      for (const v of vars) scope.push(v);
      let body = parseExpr();
      for (const _ of vars) scope.pop();
      for (let i = vars.length - 1; i >= 0; i--) body = LAM(body, vars[i]);
      branches.push([idx, body]);
      matchT("PIPE");
    }
    expect("RBRACE");
    branches.sort((a,b) => a[0]-b[0]);
    return MATCH(scrut, branches.map(b => b[1]));
  }

  const OPS = { "OR":[1,P.OR],"AND":[2,P.AND],"EQEQ":[3,P.EQ],"NEQ":[3,null],"LT":[4,P.LT],"GT":[4,P.GT],
    "LEQ":[4,null],"GEQ":[4,null],"PLUS":[5,P.ADD],"MINUS":[5,P.SUB],"CONCAT":[5,P.CONCAT],
    "STAR":[6,P.MUL],"SLASH":[6,P.DIV],"PERCENT":[6,P.MOD] };

  function parseInfix(minP) {
    let left = parseApp();
    while (OPS[pk().t] && OPS[pk().t][0] >= minP) {
      const [prec, op] = OPS[adv().t];
      const right = parseInfix(prec + 1);
      if (op !== null) left = APP(APP(PRIM(op), left), right);
      else left = APP(PRIM(P.NOT), APP(APP(PRIM(P.EQ), left), right));
    }
    return left;
  }

  function parseApp() {
    let f = parseAtom(); if (!f) throw new Error("Expected expression");
    while (true) { const a = tryAtom(); if (!a) break; f = APP(f, a); }
    return f;
  }

  function tryAtom() { if (at("INT","STR","IDENT","CONSTR","LPAREN","TRUE","FALSE","NOT","NEG","STRLEN","UNDER")) return parseAtom(); return null; }

  function parseAtom() {
    if (at("INT")) return INT(adv().v);
    if (at("STR")) return STR(adv().v);
    if (at("TRUE")) { adv(); return BOOL(true); }
    if (at("FALSE")) { adv(); return BOOL(false); }
    if (at("NOT","NEG","STRLEN")) { const n = adv().v; return BUILTINS[n](); }
    if (at("CONSTR")) { const name = adv().v; if (CONSTRS[name]) return CONSTR(CONSTRS[name][0]); throw new Error(`Unknown: ${name}`); }
    if (at("LPAREN")) { adv(); if (at("RPAREN")) { adv(); return INT(0); } const e = parseExpr(); if (at("COLON")) { adv(); parseExpr(); } expect("RPAREN"); return e; }
    if (at("IDENT")) {
      const name = adv().v;
      if (BUILTINS[name]) return BUILTINS[name]();
      if (defs[name]) return defs[name];
      const idx = resolve(name);
      if (idx !== null) return VAR(idx);
      throw new Error(`Undefined: ${name}`);
    }
    return null;
  }

  // Try program mode
  if (at("DEF")) {
    while (at("DEF")) {
      adv(); const name = expect("IDENT").v;
      const params = [];
      while (at("IDENT") && !BUILTINS[pk().v] && pk().v !== "fix" && pk().v !== "match") params.push(adv().v);
      if (at("COLON")) { adv(); parseExpr(); }
      expect("EQ");
      for (const p of params) scope.push(p);
      let body = parseExpr();
      for (const _ of params) scope.pop();
      for (let i = params.length - 1; i >= 0; i--) body = LAM(body, params[i]);
      defs[name] = body;
    }
    return defs["main"] || Object.values(defs).pop();
  }

  return parseExpr();
}

// ═══════════════════════════════════════════════════════════════
// DISPLAY
// ═══════════════════════════════════════════════════════════════

function nodeToStr(n, depth = 0) {
  if (!n) return "?";
  switch (n.tag) {
    case T.INT: return `${n.val}`;
    case T.STR: return `"${n.val}"`;
    case T.BOOL: return n.val ? "True" : "False";
    case T.VAR: return `#${n.idx}`;
    case T.LAM: return `(λ${n.tyName || ""}. ${nodeToStr(n.body, depth+1)})`;
    case T.APP: return `(${nodeToStr(n.fn, depth)} ${nodeToStr(n.arg, depth)})`;
    case T.PRIM: return primName(n.op);
    case T.FIX: return `(μ. ${nodeToStr(n.body, depth+1)})`;
    case T.IND: {
      const cnames = ["Zero","Succ","True","False","None","Some","Nil","Cons"];
      const name = cnames[n.cidx] || `C${n.cidx}`;
      if (!n.cargs || !n.cargs.length) return name;
      return `(${name} ${n.cargs.map(a => nodeToStr(a, depth)).join(" ")})`;
    }
    case T.MATCH: return `(match ${nodeToStr(n.scrut, depth)} {...})`;
    default: return "??";
  }
}

function resultToStr(n) {
  if (!n) return "()";
  if (n.tag === T.INT) return `${n.val}`;
  if (n.tag === T.STR) return `"${n.val}"`;
  if (n.tag === T.BOOL) return n.val ? "True" : "False";
  if (n.tag === T.IND) {
    // Nat display
    let cur = n, count = 0;
    while (cur && cur.tag === T.IND && cur.cidx === 1 && cur.cargs && cur.cargs.length === 1) {
      count++; cur = cur.cargs[0];
    }
    if (cur && cur.tag === T.IND && cur.cidx === 0 && (!cur.cargs || cur.cargs.length === 0)) return `${count}`;
    return nodeToStr(n);
  }
  return nodeToStr(n);
}

function inferType(n) {
  if (!n) return "?";
  switch (n.tag) {
    case T.INT: return "Int";
    case T.STR: return "String";
    case T.BOOL: return "Bool";
    case T.LAM: return `${n.tyName === "?" ? "?" : n.tyName} → ?`;
    case T.PRIM: {
      const binary = [P.ADD,P.SUB,P.MUL,P.DIV,P.MOD]; const cmp = [P.EQ,P.LT,P.GT];
      if (binary.includes(n.op)) return "Int → Int → Int";
      if (cmp.includes(n.op)) return "Int → Int → Bool";
      if (n.op === P.NEG) return "Int → Int";
      if (n.op === P.NOT) return "Bool → Bool";
      if ([P.AND,P.OR].includes(n.op)) return "Bool → Bool → Bool";
      if (n.op === P.CONCAT) return "String → String → String";
      if (n.op === P.LEN) return "String → Int";
      return "?";
    }
    case T.IND: return "Nat";
    default: return "?";
  }
}

// ═══════════════════════════════════════════════════════════════
// GRAPH VISUALIZATION (SVG)
// ═══════════════════════════════════════════════════════════════

function buildTreeLayout(node, x = 0, y = 0, depth = 0) {
  if (!node || depth > 8) return { nodes: [], edges: [], width: 60 };
  const id = Math.random().toString(36).slice(2, 8);
  let label, color;
  switch (node.tag) {
    case T.LAM: label = "λ"; color = "#6366f1"; break;
    case T.APP: label = "@"; color = "#f59e0b"; break;
    case T.PI: label = "Π"; color = "#8b5cf6"; break;
    case T.VAR: label = `#${node.idx}`; color = "#64748b"; break;
    case T.PRIM: label = primName(node.op); color = "#10b981"; break;
    case T.FIX: label = "μ"; color = "#ef4444"; break;
    case T.INT: label = `${node.val}`; color = "#3b82f6"; break;
    case T.STR: label = `"${node.val.slice(0,6)}"`; color = "#f97316"; break;
    case T.BOOL: label = node.val ? "T" : "F"; color = "#8b5cf6"; break;
    case T.IND: label = `C${node.cidx}`; color = "#ec4899"; break;
    case T.MATCH: label = "match"; color = "#14b8a6"; break;
    default: label = "?"; color = "#94a3b8";
  }

  const children = [];
  if (node.tag === T.LAM) children.push(node.body);
  else if (node.tag === T.APP) { children.push(node.fn); children.push(node.arg); }
  else if (node.tag === T.FIX) children.push(node.body);
  else if (node.tag === T.MATCH) { children.push(node.scrut); children.push(...(node.branches || [])); }
  else if (node.tag === T.IND && node.cargs) children.push(...node.cargs);

  const childLayouts = children.map(c => buildTreeLayout(c, 0, 0, depth + 1));
  const totalWidth = Math.max(60, childLayouts.reduce((s, c) => s + c.width + 12, -12));

  const thisNode = { id, x: x + totalWidth / 2, y, label, color, w: Math.max(32, label.length * 9 + 12), h: 28 };
  let allNodes = [thisNode], allEdges = [];
  let cx = x;
  for (const cl of childLayouts) {
    const dx = cx + cl.width / 2 - (x + totalWidth / 2);
    const shifted = cl.nodes.map(n => ({ ...n, x: n.x + cx, y: n.y + y + 52 }));
    allNodes.push(...shifted);
    allEdges.push(...cl.edges.map(e => ({ ...e })));
    if (shifted.length > 0) allEdges.push({ from: thisNode.id, to: shifted[0].id, fx: thisNode.x, fy: thisNode.y + thisNode.h / 2, tx: shifted[0].x, ty: shifted[0].y - shifted[0].h / 2 });
    cx += cl.width + 12;
  }
  return { nodes: allNodes, edges: allEdges, width: totalWidth };
}

function GraphSVG({ node }) {
  const layout = buildTreeLayout(node);
  const pad = 20;
  const maxY = Math.max(60, ...layout.nodes.map(n => n.y + n.h)) + pad;
  const maxX = Math.max(120, ...layout.nodes.map(n => n.x + n.w / 2)) + pad;
  return (
    <svg viewBox={`${-pad} ${-pad} ${maxX + pad} ${maxY}`} className="w-full" style={{ maxHeight: 300, background: "#0c0c1a", borderRadius: 8 }}>
      {layout.edges.map((e, i) => {
        const fn = layout.nodes.find(n => n.id === e.from);
        const tn = layout.nodes.find(n => n.id === e.to);
        if (!fn || !tn) return null;
        return <line key={i} x1={fn.x} y1={fn.y + fn.h/2} x2={tn.x} y2={tn.y - tn.h/2} stroke="#4b5563" strokeWidth={1.5} opacity={0.6} />;
      })}
      {layout.nodes.map(n => (
        <g key={n.id}>
          <rect x={n.x - n.w/2} y={n.y - n.h/2} width={n.w} height={n.h} rx={6} fill={n.color} opacity={0.85} />
          <text x={n.x} y={n.y + 5} textAnchor="middle" fill="white" fontSize={12} fontFamily="JetBrains Mono, monospace" fontWeight="600">{n.label}</text>
        </g>
      ))}
    </svg>
  );
}

// ═══════════════════════════════════════════════════════════════
// EXAMPLES
// ═══════════════════════════════════════════════════════════════

const EXAMPLES = [
  { name: "Basics", code: `(2 + 3) * (4 + 5)` },
  { name: "Lambda", code: `(λx. x * x) 7` },
  { name: "Let", code: `let double = λx. x + x in double 21` },
  { name: "Curried", code: `(λx. λy. x + y) 17 25` },
  { name: "Boolean", code: `if 3 < 5 then 42 else 0` },
  { name: "Pattern", code: `match Succ (Succ Zero) { Zero → 0 | Succ n → 1 }` },
  { name: "Nat Add", code: `let add = fix self. λn. λm. match n {\n    Zero → m\n  | Succ k → Succ (self k m)\n}\nin add (Succ (Succ Zero)) (Succ (Succ (Succ Zero)))` },
  { name: "Fibonacci", code: `let add = fix self. λn. λm. match n {\n    Zero → m | Succ k → Succ (self k m) }\nin let fib = fix self. λn. match n {\n    Zero → Zero\n  | Succ k → match k {\n      Zero → Succ Zero\n    | Succ j → add (self (Succ j)) (self j) }\n}\nin fib (Succ (Succ (Succ (Succ (Succ (Succ Zero))))))` },
  { name: "String", code: `"Hello, " ++ "Xi!"` },
  { name: "Program", code: `def double x = x + x\ndef quad x = double (double x)\ndef main = quad 10` },
];

// ═══════════════════════════════════════════════════════════════
// SYNTAX HIGHLIGHTING
// ═══════════════════════════════════════════════════════════════

function highlight(code) {
  return code.replace(
    /("(?:[^"\\]|\\.)*")|(\b\d+\b)|(--[^\n]*)|(\b(?:let|in|if|then|else|match|fix|rec|fun|def|type|import|module)\b)|(λ|μ|Π|→|⇒)|(\\)|(True|False|Zero|Succ|None|Some|Nil|Cons|[A-Z]\w*)/g,
    (m, str, num, comment, kw, uni, backslash, constr) => {
      if (str) return `<span style="color:#f97316">${m}</span>`;
      if (num) return `<span style="color:#60a5fa">${m}</span>`;
      if (comment) return `<span style="color:#6b7280;font-style:italic">${m}</span>`;
      if (kw) return `<span style="color:#c084fc;font-weight:600">${m}</span>`;
      if (uni) return `<span style="color:#f472b6;font-weight:700">${m}</span>`;
      if (backslash) return `<span style="color:#f472b6;font-weight:700">${m}</span>`;
      if (constr) return `<span style="color:#34d399">${m}</span>`;
      return m;
    }
  );
}

// ═══════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════

export default function XiPlayground() {
  const [code, setCode] = useState(EXAMPLES[0].code);
  const [result, setResult] = useState(null);
  const [trace, setTrace] = useState([]);
  const [error, setError] = useState(null);
  const [activeStep, setActiveStep] = useState(-1);
  const [tab, setTab] = useState("result");
  const textareaRef = useRef(null);
  const highlightRef = useRef(null);

  const run = useCallback(() => {
    try {
      const ast = parse(code);
      const tr = evaluate(ast, 500);
      setTrace(tr);
      setResult(tr[tr.length - 1].node);
      setActiveStep(tr.length - 1);
      setError(null);
    } catch (e) {
      setError(e.message);
      setResult(null);
      setTrace([]);
    }
  }, [code]);

  useEffect(() => { run(); }, []);

  const syncScroll = () => {
    if (textareaRef.current && highlightRef.current) {
      highlightRef.current.scrollTop = textareaRef.current.scrollTop;
      highlightRef.current.scrollLeft = textareaRef.current.scrollLeft;
    }
  };

  const activeNode = activeStep >= 0 && activeStep < trace.length ? trace[activeStep].node : result;

  return (
    <div style={{ fontFamily: "'Instrument Sans', 'DM Sans', system-ui, sans-serif", background: "#08080f", color: "#e2e8f0", minHeight: "100vh", padding: 0 }}>
      {/* Header */}
      <div style={{ background: "linear-gradient(135deg, #0f0f23 0%, #1a0a2e 50%, #0a1628 100%)", borderBottom: "1px solid #1e293b", padding: "16px 24px", display: "flex", alignItems: "center", gap: 16 }}>
        <div style={{ fontSize: 28, fontWeight: 800, letterSpacing: -1 }}>
          <span style={{ color: "#818cf8" }}>Ξ</span>
          <span style={{ color: "#c4b5fd", fontSize: 18, marginLeft: 8, fontWeight: 400 }}>Xi Playground</span>
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {EXAMPLES.map((ex, i) => (
            <button key={i} onClick={() => { setCode(ex.code); setTimeout(run, 50); }}
              style={{ padding: "4px 10px", borderRadius: 6, border: "1px solid #334155", background: code === ex.code ? "#4338ca" : "#1e1b4b",
                color: code === ex.code ? "#fff" : "#a5b4fc", fontSize: 11, cursor: "pointer", fontWeight: 500, transition: "all 0.15s" }}>
              {ex.name}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0, height: "calc(100vh - 65px)" }}>
        {/* Left: Editor */}
        <div style={{ borderRight: "1px solid #1e293b", display: "flex", flexDirection: "column" }}>
          <div style={{ padding: "10px 16px", borderBottom: "1px solid #1e293b", display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ color: "#94a3b8", fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: 1 }}>Source</span>
            <div style={{ flex: 1 }} />
            <button onClick={run}
              style={{ padding: "6px 18px", borderRadius: 6, border: "none", background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                color: "white", fontWeight: 700, cursor: "pointer", fontSize: 13, boxShadow: "0 2px 12px #6366f140", transition: "all 0.2s" }}>
              ▶ Run
            </button>
          </div>
          <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
            <pre ref={highlightRef} aria-hidden="true"
              style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, margin: 0, padding: 16,
                fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace", fontSize: 14, lineHeight: 1.7,
                background: "transparent", color: "transparent", whiteSpace: "pre-wrap", wordWrap: "break-word",
                overflow: "auto", pointerEvents: "none" }}
              dangerouslySetInnerHTML={{ __html: highlight(code) + "\n" }} />
            <textarea ref={textareaRef} value={code}
              onChange={e => setCode(e.target.value)} onScroll={syncScroll}
              onKeyDown={e => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); run(); } }}
              spellCheck={false}
              style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, width: "100%", height: "100%",
                margin: 0, padding: 16, fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
                fontSize: 14, lineHeight: 1.7, background: "transparent", color: "transparent", caretColor: "#818cf8",
                border: "none", outline: "none", resize: "none", whiteSpace: "pre-wrap", wordWrap: "break-word" }} />
          </div>
        </div>

        {/* Right: Output */}
        <div style={{ display: "flex", flexDirection: "column", background: "#0a0a16" }}>
          {/* Tabs */}
          <div style={{ display: "flex", borderBottom: "1px solid #1e293b" }}>
            {[["result", "Result"], ["graph", "Graph"], ["steps", "Steps"], ["info", "Info"]].map(([id, label]) => (
              <button key={id} onClick={() => setTab(id)}
                style={{ padding: "10px 20px", border: "none", borderBottom: tab === id ? "2px solid #818cf8" : "2px solid transparent",
                  background: "transparent", color: tab === id ? "#c4b5fd" : "#64748b", cursor: "pointer",
                  fontWeight: tab === id ? 700 : 500, fontSize: 12, textTransform: "uppercase", letterSpacing: 1, transition: "all 0.15s" }}>
                {label}
              </button>
            ))}
          </div>

          <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
            {error && (
              <div style={{ background: "#450a0a", border: "1px solid #dc2626", borderRadius: 8, padding: 12, marginBottom: 12, fontFamily: "monospace", fontSize: 13, color: "#fca5a5" }}>
                ⚠ {error}
              </div>
            )}

            {tab === "result" && result && (
              <div>
                <div style={{ fontSize: 48, fontWeight: 800, color: "#a5b4fc", fontFamily: "'JetBrains Mono', monospace", marginBottom: 16, letterSpacing: -2 }}>
                  {resultToStr(result)}
                </div>
                <div style={{ color: "#64748b", fontSize: 13 }}>
                  <span style={{ color: "#6366f1" }}>type:</span> {inferType(result)}
                  <span style={{ marginLeft: 20, color: "#6366f1" }}>steps:</span> {trace.length - 1}
                </div>
              </div>
            )}

            {tab === "graph" && activeNode && <GraphSVG node={activeNode} />}

            {tab === "steps" && trace.length > 0 && (
              <div>
                <div style={{ display: "flex", gap: 8, marginBottom: 12, alignItems: "center" }}>
                  <button onClick={() => setActiveStep(Math.max(0, activeStep - 1))}
                    style={{ padding: "4px 12px", borderRadius: 6, border: "1px solid #334155", background: "#1e1b4b", color: "#a5b4fc", cursor: "pointer", fontSize: 13 }}>◀</button>
                  <span style={{ color: "#94a3b8", fontSize: 13, fontFamily: "monospace" }}>
                    Step {activeStep}/{trace.length - 1}
                  </span>
                  <button onClick={() => setActiveStep(Math.min(trace.length - 1, activeStep + 1))}
                    style={{ padding: "4px 12px", borderRadius: 6, border: "1px solid #334155", background: "#1e1b4b", color: "#a5b4fc", cursor: "pointer", fontSize: 13 }}>▶</button>
                  <button onClick={() => setActiveStep(trace.length - 1)}
                    style={{ padding: "4px 12px", borderRadius: 6, border: "1px solid #334155", background: "#1e1b4b", color: "#a5b4fc", cursor: "pointer", fontSize: 13 }}>⏭</button>
                </div>
                {/* Progress bar */}
                <div style={{ height: 4, background: "#1e293b", borderRadius: 2, marginBottom: 16 }}>
                  <div style={{ height: 4, background: "#6366f1", borderRadius: 2, width: `${(activeStep / Math.max(1, trace.length - 1)) * 100}%`, transition: "width 0.2s" }} />
                </div>
                <div style={{ maxHeight: 400, overflow: "auto" }}>
                  {trace.map((s, i) => (
                    <div key={i} onClick={() => setActiveStep(i)}
                      style={{ padding: "6px 12px", borderRadius: 6, marginBottom: 2, cursor: "pointer",
                        background: i === activeStep ? "#312e81" : "transparent",
                        border: i === activeStep ? "1px solid #4338ca" : "1px solid transparent",
                        fontFamily: "'JetBrains Mono', monospace", fontSize: 12, lineHeight: 1.5,
                        display: "flex", gap: 10, alignItems: "baseline", transition: "all 0.1s" }}>
                      <span style={{ color: "#4b5563", minWidth: 30 }}>{i}</span>
                      <span style={{ color: i === activeStep ? "#a5b4fc" : "#818cf8", minWidth: 80, fontWeight: 600 }}>{s.rule}</span>
                      <span style={{ color: "#94a3b8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {nodeToStr(s.node).slice(0, 80)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {tab === "info" && (
              <div style={{ color: "#94a3b8", fontSize: 13, lineHeight: 2 }}>
                <h3 style={{ color: "#c4b5fd", fontSize: 16, fontWeight: 700, marginBottom: 12 }}>Ξ (Xi) — The Final Programming Language</h3>
                <p>A dependently-typed language built from <strong style={{ color: "#818cf8" }}>10 primitives</strong>:</p>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 24px", margin: "12px 0", fontFamily: "monospace", fontSize: 12 }}>
                  {["λ Lambda","@ Apply","Π Pi type","Σ Sigma","𝒰 Universe","μ Fixpoint","ι Inductive","≡ Equality","! Effect","# Primitive"].map((s, i) => (
                    <div key={i}><span style={{ color: "#818cf8" }}>{s.split(" ")[0]}</span> {s.split(" ").slice(1).join(" ")}</div>
                  ))}
                </div>
                <p style={{ marginTop: 12 }}><strong style={{ color: "#818cf8" }}>Syntax:</strong> λx. body, let x = e in b, if/then/else, match/patterns, fix for recursion</p>
                <p><strong style={{ color: "#818cf8" }}>Features:</strong> Content-addressed (SHA-256), effect system, algebraic data types, HM inference</p>
                <p><strong style={{ color: "#818cf8" }}>Proofs:</strong> Type preservation, progress, type safety (formalized in Lean 4)</p>
                <p style={{ marginTop: 12, color: "#64748b", fontSize: 11 }}>Tip: Press Ctrl+Enter to run • Click steps to inspect graph at each reduction</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
