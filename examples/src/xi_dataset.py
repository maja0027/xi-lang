"""
Ξ (Xi) — Training Dataset Generator
Copyright (c) 2026 Alex P. Slaby — MIT License

Generates structured training data for AI learning:
  - Each example: source → ir.json → binary.xi → expected_output → properties
  - Mutation pairs: (program, change_description, correct_patch)
  - Multiple difficulty levels
"""

import json, os, hashlib, base64, random
from xi import Node, Tag, PrimOp, serialize
from xi_compiler import Compiler
from xi_match import MatchInterpreter, Constructor, nat_to_int
from xi_json import to_json, hash_node, diff, diff_stats, analyze_properties, node_count
from xi_optimizer import optimize
from xi_sandbox import SandboxedInterpreter, SandboxConfig


# ═══════════════════════════════════════════
# PROGRAM TEMPLATES
# ═══════════════════════════════════════════

TEMPLATES = {
    "arithmetic": [
        ("{a} + {b}", lambda a, b: a + b),
        ("{a} * {b}", lambda a, b: a * b),
        ("{a} - {b}", lambda a, b: a - b),
        ("({a} + {b}) * {c}", lambda a, b, c: (a + b) * c),
        ("({a} * {b}) + ({c} * {d})", lambda a, b, c, d: a * b + c * d),
        ("{a} * {a} + {b} * {b}", lambda a, b: a * a + b * b),
    ],
    "lambda": [
        ("(λx. x + {a}) {b}", lambda a, b: b + a),
        ("(λx. x * x) {a}", lambda a: a * a),
        ("(λx. λy. x + y) {a} {b}", lambda a, b: a + b),
        ("(λf. λx. f (f x)) (λx. x + {a}) {b}", lambda a, b: b + a + a),
        ("(λx. x + x) {a}", lambda a: a + a),
    ],
    "conditional": [
        ("if {a} < {b} then {a} else {b}", lambda a, b: a if a < b else b),
        ("if {a} == {b} then 1 else 0", lambda a, b: 1 if a == b else 0),
        ("if {a} > 0 then {a} * {b} else 0", lambda a, b: a * b if a > 0 else 0),
    ],
    "let_binding": [
        ("let x = {a} in x + x", lambda a: a + a),
        ("let x = {a} + {b} in x * x", lambda a, b: (a + b) ** 2),
        ("let x = {a} in let y = {b} in x + y", lambda a, b: a + b),
    ],
    "string": [
        ('"{s1}" ++ "{s2}"', lambda s1, s2: s1 + s2),
    ],
    "multi_def": [
        ("def f x = x + {a}\ndef main = f {b}", lambda a, b: b + a),
        ("def sq x = x * x\ndef main = sq {a}", lambda a: a * a),
        ("def add a b = a + b\ndef main = add {a} {b}", lambda a, b: a + b),
        ("def f x = x + x\ndef g x = f (f x)\ndef main = g {a}", lambda a: a * 4),
    ],
    "adt": [
        ("type T = A | B Int\ndef main = match A { A → {a} | B x → x }", lambda a: a),
        ("type T = A | B Int\ndef main = match B {a} { A → 0 | B x → x }", lambda a: a),
    ],
}

# Mutation templates: (description, original_template, mutated_template)
MUTATIONS = [
    ("add_constant", "def main = {a} + {b}", "def main = {a} + {b} + {c}"),
    ("change_operator", "def main = {a} + {b}", "def main = {a} * {b}"),
    ("extract_function", "def main = {a} * {a} + {b} * {b}",
     "def sq x = x * x\ndef main = sq {a} + sq {b}"),
    ("inline_let", "def main = let x = {a} in x + x", "def main = {a} + {a}"),
    ("wrap_conditional", "def main = {a} + {b}",
     "def main = if {a} > 0 then {a} + {b} else {b}"),
    ("add_parameter", "def f x = x + {a}\ndef main = f {b}",
     "def f x y = x + y\ndef main = f {b} {a}"),
]


def generate_dataset(n=100, output_dir="dataset"):
    """Generate n training examples with JSON metadata."""
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "examples"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "mutations"), exist_ok=True)

    c = Compiler()
    sandbox = SandboxedInterpreter(SandboxConfig.strict())
    manifest = {"version": "xi-dataset-v1", "count": 0, "examples": [], "mutations": []}
    generated = 0

    # Generate examples
    for i in range(n):
        category = random.choice(list(TEMPLATES.keys()))
        templates = TEMPLATES[category]
        template_expr, compute_fn = random.choice(templates)

        # Generate random parameters
        params = _random_params(template_expr)
        try:
            if category == "string":
                words = ["hello", "world", "xi", "lang", "ai", "code", "test"]
                params = {"s1": random.choice(words), "s2": random.choice(words)}
            source_expr = template_expr.format(**params)
        except:
            continue

        # Build full source
        if "def " in source_expr:
            source = source_expr
        else:
            source = f"def main = {source_expr}"

        # Compile and evaluate
        try:
            node = c.compile_program(source).get("main")
            if not node:
                continue
            result = c.run_program(source, "main")
            if isinstance(result, Constructor):
                try:
                    result = nat_to_int(MatchInterpreter(), result)
                except:
                    result = str(result)
        except:
            continue

        # Compute expected (for verification)
        try:
            if category == "string":
                expected = compute_fn(**params)
            else:
                int_params = {k: v for k, v in params.items() if isinstance(v, int)}
                expected = compute_fn(**int_params)
        except:
            expected = result

        # Build example record
        ir = to_json(node, include_hash=True)
        binary = serialize(node)
        props = analyze_properties(node)

        example_id = f"ex_{i:06d}"
        record = {
            "id": example_id,
            "category": category,
            "source": source,
            "ir": ir,
            "binary_base64": base64.b64encode(binary).decode(),
            "binary_size": len(binary),
            "expected_output": result,
            "verified": result == expected,
            "hash": hash_node(node),
            "node_count": node_count(node),
            "properties": props["properties"],
            "effects": props["effects"],
        }

        # Save individual file
        path = os.path.join(output_dir, "examples", f"{example_id}.json")
        with open(path, 'w') as f:
            json.dump(record, f, indent=2, default=str)

        manifest["examples"].append({"id": example_id, "category": category,
                                      "hash": hash_node(node)})
        generated += 1

    # Generate mutations
    mutation_count = min(n // 2, len(MUTATIONS) * 20)
    for i in range(mutation_count):
        desc, orig_tmpl, mutated_tmpl = random.choice(MUTATIONS)
        params = _random_params(orig_tmpl)
        try:
            orig_src = orig_tmpl.format(**params)
            mut_src = mutated_tmpl.format(**params)
            if "def " not in orig_src:
                orig_src = f"def main = {orig_src}"
            if "def " not in mut_src:
                mut_src = f"def main = {mut_src}"

            orig_node = c.compile_program(orig_src).get("main")
            mut_node = c.compile_program(mut_src).get("main")
            if not orig_node or not mut_node:
                continue

            orig_result = c.run_program(orig_src, "main")
            mut_result = c.run_program(mut_src, "main")

            ops = diff(orig_node, mut_node)
            stats = diff_stats(ops)

            mut_id = f"mut_{i:06d}"
            mutation_record = {
                "id": mut_id,
                "description": desc,
                "original_source": orig_src,
                "mutated_source": mut_src,
                "original_output": orig_result,
                "mutated_output": mut_result,
                "patch": ops,
                "diff_stats": stats,
                "original_hash": hash_node(orig_node),
                "mutated_hash": hash_node(mut_node),
            }

            path = os.path.join(output_dir, "mutations", f"{mut_id}.json")
            with open(path, 'w') as f:
                json.dump(mutation_record, f, indent=2, default=str)

            manifest["mutations"].append({"id": mut_id, "description": desc})
        except:
            continue

    manifest["count"] = generated
    with open(os.path.join(output_dir, "manifest.json"), 'w') as f:
        json.dump(manifest, f, indent=2)

    print(json.dumps({
        "ok": True,
        "examples_generated": generated,
        "mutations_generated": len(manifest["mutations"]),
        "output_dir": output_dir
    }, indent=2))


def _random_params(template):
    """Generate random parameters for a template."""
    params = {}
    for key in ['a', 'b', 'c', 'd']:
        if '{' + key + '}' in template:
            params[key] = random.randint(1, 20)
    return params


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    generate_dataset(n)
