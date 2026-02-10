#!/usr/bin/env python3
"""
Ξ (Xi) Graph Visualization — Graphviz DOT Export
Copyright (c) 2026 Alex P. Slaby — MIT License

Exports Xi graphs as Graphviz DOT format for SVG/PNG rendering.

Usage:
  python xi_graphviz.py <file.xi>          # output DOT to stdout
  python xi_graphviz.py <file.xi> -o out.svg  # render SVG (needs graphviz)
  python xi_graphviz.py demo               # demo with example programs
"""

import sys, os, subprocess
sys.path.insert(0, os.path.dirname(__file__))
from xi import Node, Tag, PrimOp, Effect, B, TAG_SYMBOL, PRIM_NAME, EFFECT_NAME


# ── Colors by tag ──
TAG_COLORS = {
    Tag.LAM: "#6366f1",  # indigo
    Tag.APP: "#f59e0b",  # amber
    Tag.PI:  "#10b981",  # emerald
    Tag.SIG: "#14b8a6",  # teal
    Tag.UNI: "#a855f7",  # purple
    Tag.FIX: "#ef4444",  # red
    Tag.IND: "#06b6d4",  # cyan
    Tag.EQ:  "#8b5cf6",  # violet
    Tag.EFF: "#f97316",  # orange
    Tag.PRIM:"#64748b",  # slate
}

TAG_SHAPES = {
    Tag.LAM: "oval",
    Tag.APP: "diamond",
    Tag.PI:  "hexagon",
    Tag.PRIM:"box",
    Tag.EFF: "octagon",
    Tag.UNI: "doublecircle",
}


def to_dot(root: Node, title: str = "Xi Graph") -> str:
    """Convert a Xi graph to Graphviz DOT format."""
    lines = [
        'digraph Xi {',
        '  rankdir=TB;',
        '  bgcolor="#1e1b2e";',
        f'  label="{title}";',
        '  labelloc=t;',
        '  fontname="Helvetica";',
        '  fontcolor="#e2e8f0";',
        '  fontsize=16;',
        '  node [fontname="Helvetica", fontsize=11, style=filled, color="#334155"];',
        '  edge [color="#94a3b8", arrowsize=0.7];',
        '',
    ]

    visited = {}
    counter = [0]

    def node_id(node):
        nid = id(node)
        if nid not in visited:
            visited[nid] = f"n{counter[0]}"
            counter[0] += 1
        return visited[nid]

    def walk(node):
        nid = node_id(node)
        if nid in [l.split('[')[0].strip() for l in lines if l.strip().startswith('n')]:
            return nid

        # Node label
        label = _node_label(node)
        color = TAG_COLORS.get(node.tag, "#475569")
        shape = TAG_SHAPES.get(node.tag, "ellipse")
        fontcolor = "#ffffff"

        lines.append(
            f'  {nid} [label="{label}", fillcolor="{color}", '
            f'fontcolor="{fontcolor}", shape={shape}];'
        )

        # Edges
        for i, child in enumerate(node.children):
            cid = walk(child)
            edge_label = ""
            if node.tag == Tag.LAM:
                edge_label = "type" if i == 0 else "body"
            elif node.tag == Tag.APP:
                edge_label = "func" if i == 0 else "arg"
            elif node.tag == Tag.PI:
                edge_label = "dom" if i == 0 else "cod"

            if edge_label:
                lines.append(f'  {nid} -> {cid} [label=" {edge_label}", fontcolor="#94a3b8", fontsize=9];')
            else:
                lines.append(f'  {nid} -> {cid};')

        return nid

    walk(root)
    lines.append('}')
    return '\n'.join(lines)


def _node_label(node: Node) -> str:
    """Compact label for DOT node."""
    sym = TAG_SYMBOL.get(node.tag, "?")

    if node.tag == Tag.PRIM:
        if node.prim_op == PrimOp.INT_LIT:
            return str(node.data)
        if node.prim_op == PrimOp.STR_LIT:
            s = node.data if len(node.data) <= 12 else node.data[:10] + "…"
            return f'\\"{s}\\"'
        if node.prim_op == PrimOp.FLOAT_LIT:
            return str(node.data)
        if node.prim_op == PrimOp.VAR:
            return f"var({node.data})"
        if node.prim_op == PrimOp.BOOL_TRUE:
            return "true"
        if node.prim_op == PrimOp.BOOL_FALSE:
            return "false"
        if node.prim_op == PrimOp.UNIT:
            return "()"
        name = PRIM_NAME.get(node.prim_op, f"op{node.prim_op}")
        return f"#{name}"

    if node.tag == Tag.UNI:
        return f"𝒰{node.universe_level}"

    if node.tag == Tag.EFF:
        effs = [EFFECT_NAME.get(e, "?") for e in Effect if e != Effect.PURE and node.effect & e]
        return f"!{{{','.join(effs)}}}"

    return sym


def render_svg(dot: str, output_path: str):
    """Render DOT to SVG using graphviz (if installed)."""
    try:
        result = subprocess.run(
            ['dot', '-Tsvg'],
            input=dot, capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr)
        with open(output_path, 'w') as f:
            f.write(result.stdout)
        return True
    except FileNotFoundError:
        return False


def run_demo():
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║  Ξ (Xi) Graph Visualization v0.1                         ║")
    print("║  Copyright (c) 2026 Alex P. Slaby — MIT License          ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")

    programs = [
        ("Hello World",
         B.effect(B.app(B.prim(PrimOp.PRINT), B.str_lit("Hello!")), Effect.IO)),
        ("Arithmetic: (3+5)*2",
         B.app(B.app(B.prim(PrimOp.INT_MUL),
             B.app(B.app(B.prim(PrimOp.INT_ADD), B.int_lit(3)), B.int_lit(5))),
             B.int_lit(2))),
        ("Lambda: double",
         B.lam(B.universe(0),
             B.app(B.app(B.prim(PrimOp.INT_ADD), B.var(0)), B.var(0)))),
    ]

    out_dir = os.path.join(os.path.dirname(__file__), '..', 'docs', 'assets')
    os.makedirs(out_dir, exist_ok=True)

    for name, prog in programs:
        dot = to_dot(prog, title=f"Ξ — {name}")
        safe_name = name.lower().replace(' ', '_').replace(':', '').replace('(', '').replace(')', '').replace('+', '')
        dot_path = os.path.join(out_dir, f"graph_{safe_name}.dot")
        with open(dot_path, 'w') as f:
            f.write(dot)
        print(f"  ✓ {name} → {os.path.basename(dot_path)}")

        # Try SVG render
        svg_path = dot_path.replace('.dot', '.svg')
        if render_svg(dot, svg_path):
            print(f"    → {os.path.basename(svg_path)} (rendered)")
        else:
            print(f"    (install graphviz to render SVG: brew install graphviz)")

    print()
    print("  DOT files saved. Render with:")
    print("    dot -Tsvg docs/assets/graph_hello_world.dot -o graph.svg")
    print("    dot -Tpng docs/assets/graph_hello_world.dot -o graph.png\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] != "demo":
        from xi_deser import load_file
        node = load_file(sys.argv[1])
        dot = to_dot(node, title=sys.argv[1])
        if len(sys.argv) > 3 and sys.argv[2] == "-o":
            out = sys.argv[3]
            if out.endswith('.svg'):
                render_svg(dot, out)
            else:
                with open(out, 'w') as f:
                    f.write(dot)
            print(f"Saved: {out}")
        else:
            print(dot)
    else:
        run_demo()
