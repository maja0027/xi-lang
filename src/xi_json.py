"""
Ξ (Xi) — JSON IR, Canonicalization, Diff & Patch
Copyright (c) 2026 Alex P. Slaby — MIT License

Machine-readable representation of Xi programs for AI tooling.

Key operations:
  - to_json / from_json: Xi ↔ JSON-IR round-trip
  - canonicalize: deterministic canonical form
  - diff / patch: structural graph diff
  - hash_node: content-addressed SHA-256
"""

import json, hashlib, copy
from xi import Node, Tag, PrimOp, serialize

# ═══════════════════════════════════════════
# JSON-IR SCHEMA
# ═══════════════════════════════════════════

XI_IR_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://xi-lang.org/schema/xi-ir-v1.json",
    "title": "Xi-IR v1",
    "description": "Canonical JSON representation of Xi program graphs",
    "type": "object",
    "required": ["version", "root"],
    "properties": {
        "version": {"const": "xi-ir-v1"},
        "root": {"$ref": "#/$defs/node"},
        "metadata": {
            "type": "object",
            "properties": {
                "hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                "node_count": {"type": "integer", "minimum": 1},
                "max_depth": {"type": "integer", "minimum": 0},
                "effects": {"type": "array", "items": {"type": "string"}},
                "properties": {"type": "array", "items": {"type": "string"}}
            }
        }
    },
    "$defs": {
        "node": {
            "type": "object",
            "required": ["tag"],
            "properties": {
                "tag": {"enum": ["lam", "app", "pi", "sig", "uni", "fix", "ind", "eq", "eff", "prim"]},
                "children": {"type": "array", "items": {"$ref": "#/$defs/node"}},
                "data": {},
                "prim_op": {"type": "string"},
                "hash": {"type": "string"}
            }
        }
    }
}

TAG_NAMES = {
    Tag.LAM: "lam", Tag.APP: "app", Tag.PI: "pi", Tag.SIG: "sig",
    Tag.UNI: "uni", Tag.FIX: "fix", Tag.IND: "ind", Tag.EQ: "eq",
    Tag.EFF: "eff", Tag.PRIM: "prim"
}
NAME_TAGS = {v: k for k, v in TAG_NAMES.items()}

PRIMOP_NAMES = {}
NAMES_PRIMOP = {}
for op in PrimOp:
    name = op.name.lower()
    PRIMOP_NAMES[op] = name
    NAMES_PRIMOP[name] = op

# ═══════════════════════════════════════════
# NODE → JSON
# ═══════════════════════════════════════════

def to_json(node, include_hash=True, include_metadata=True):
    """Convert a Xi Node graph to JSON-IR dict."""
    seen_hashes = set()
    node_count = [0]
    max_depth = [0]

    def convert(n, depth=0):
        node_count[0] += 1
        max_depth[0] = max(max_depth[0], depth)
        obj = {"tag": TAG_NAMES.get(n.tag, str(n.tag))}

        if n.children:
            obj["children"] = [convert(c, depth + 1) for c in n.children]

        # Emit prim_op if present
        if hasattr(n, 'prim_op') and n.prim_op is not None and isinstance(n.prim_op, PrimOp):
            obj["prim_op"] = PRIMOP_NAMES.get(n.prim_op, str(n.prim_op))

        # Emit data if present (separate from prim_op)
        if n.data is not None:
            if isinstance(n.data, PrimOp):
                # data is a PrimOp (legacy: some nodes store op in data)
                obj["prim_op"] = PRIMOP_NAMES.get(n.data, str(n.data))
            elif isinstance(n.data, (int, float)):
                obj["data"] = n.data
            elif isinstance(n.data, str):
                obj["data"] = n.data
            elif isinstance(n.data, bytes):
                obj["data"] = n.data.hex()
            else:
                obj["data"] = str(n.data)

        if include_hash:
            obj["hash"] = hash_node(n)

        return obj

    root = convert(node)
    result = {"version": "xi-ir-v1", "root": root}

    if include_metadata:
        result["metadata"] = {
            "hash": hash_node(node),
            "node_count": node_count[0],
            "max_depth": max_depth[0]
        }

    return result


def to_json_str(node, pretty=True, **kwargs):
    """Convert to JSON string."""
    obj = to_json(node, **kwargs)
    if pretty:
        return json.dumps(obj, indent=2, ensure_ascii=False)
    return json.dumps(obj, separators=(',', ':'), ensure_ascii=False)


# ═══════════════════════════════════════════
# JSON → NODE
# ═══════════════════════════════════════════

def from_json(obj):
    """Convert a JSON-IR dict back to a Xi Node graph."""
    if isinstance(obj, str):
        obj = json.loads(obj)

    if "root" in obj:
        return _convert_node(obj["root"])
    return _convert_node(obj)


def _convert_node(obj):
    tag = NAME_TAGS.get(obj["tag"])
    if tag is None:
        raise ValueError(f"Unknown tag: {obj['tag']}")

    children = [_convert_node(c) for c in obj.get("children", [])]

    prim_op = None
    data = None
    if "prim_op" in obj:
        prim_op = NAMES_PRIMOP.get(obj["prim_op"])
        if prim_op is None:
            raise ValueError(f"Unknown prim_op: {obj['prim_op']}")
    if "data" in obj:
        data = obj["data"]

    node = Node(tag, children, prim_op)
    if data is not None:
        node.data = data
    return node


# ═══════════════════════════════════════════
# CANONICALIZATION
# ═══════════════════════════════════════════

def canonicalize(node):
    """Return a canonical form of the node (structurally shared, deterministic).
    Two semantically equivalent nodes produce the same canonical form.
    """
    memo = {}  # hash → canonical node

    def canon(n):
        h = hash_node(n)
        if h in memo:
            return memo[h]
        children = [canon(c) for c in n.children]
        result = Node(n.tag, children, n.data)
        memo[h] = result
        return result

    return canon(node)


def canonicalize_json(obj):
    """Canonicalize a JSON-IR: sort keys, normalize whitespace, stable output."""
    node = from_json(obj)
    canon = canonicalize(node)
    return to_json(canon, include_hash=True, include_metadata=True)


# ═══════════════════════════════════════════
# CONTENT-ADDRESSED HASHING
# ═══════════════════════════════════════════

def hash_node(node):
    """SHA-256 hash of a node, including all children (content-addressed)."""
    h = hashlib.sha256()
    h.update(bytes([node.tag]))
    h.update(bytes([len(node.children)]))

    for child in node.children:
        h.update(bytes.fromhex(hash_node(child)))

    # Hash prim_op if present
    if hasattr(node, 'prim_op') and node.prim_op is not None and isinstance(node.prim_op, PrimOp):
        h.update(b'P')
        h.update(bytes([node.prim_op.value]))

    if node.data is not None:
        if isinstance(node.data, int):
            h.update(b'I')
            h.update(node.data.to_bytes(8, 'little', signed=True))
        elif isinstance(node.data, str):
            h.update(b'S')
            h.update(node.data.encode('utf-8'))
        elif isinstance(node.data, PrimOp):
            h.update(b'P')
            h.update(bytes([node.data.value]))
        elif isinstance(node.data, bytes):
            h.update(b'B')
            h.update(node.data)

    return h.hexdigest()


# ═══════════════════════════════════════════
# STRUCTURAL DIFF
# ═══════════════════════════════════════════

def diff(old, new, path="root"):
    """Compute structural diff between two Xi node graphs.

    Returns a list of patch operations:
      {"op": "replace", "path": "root.children[0]", "old_hash": ..., "new": ...}
      {"op": "insert", "path": "root.children[2]", "new": ...}
      {"op": "delete", "path": "root.children[1]"}
      {"op": "modify_data", "path": "root", "old": ..., "new": ...}
    """
    ops = []

    if hash_node(old) == hash_node(new):
        return ops  # Identical subtrees

    # Tag changed → full replace
    if old.tag != new.tag:
        ops.append({
            "op": "replace",
            "path": path,
            "old_hash": hash_node(old),
            "new": _node_to_patch(new)
        })
        return ops

    # Data changed
    if old.data != new.data:
        ops.append({
            "op": "modify_data",
            "path": path,
            "old": _data_repr(old.data),
            "new": _data_repr(new.data)
        })

    # prim_op changed
    old_pop = getattr(old, 'prim_op', None)
    new_pop = getattr(new, 'prim_op', None)
    if old_pop != new_pop:
        ops.append({
            "op": "modify_data",
            "path": path,
            "old": _data_repr(old_pop),
            "new": _data_repr(new_pop)
        })

    # Recurse into children
    max_len = max(len(old.children), len(new.children))
    for i in range(max_len):
        child_path = f"{path}.children[{i}]"
        if i >= len(old.children):
            ops.append({
                "op": "insert",
                "path": child_path,
                "new": _node_to_patch(new.children[i])
            })
        elif i >= len(new.children):
            ops.append({
                "op": "delete",
                "path": child_path,
                "old_hash": hash_node(old.children[i])
            })
        else:
            ops.extend(diff(old.children[i], new.children[i], child_path))

    return ops


def _node_to_patch(node):
    """Minimal representation of a node for patches."""
    obj = {"tag": TAG_NAMES.get(node.tag, str(node.tag))}
    if node.children:
        obj["children"] = [_node_to_patch(c) for c in node.children]
    # Check prim_op attribute first (compiler-generated nodes)
    pop = getattr(node, 'prim_op', None)
    if pop is not None and isinstance(pop, PrimOp):
        obj["prim_op"] = PRIMOP_NAMES.get(pop, str(pop))
    if node.data is not None:
        if isinstance(node.data, PrimOp):
            obj["prim_op"] = PRIMOP_NAMES.get(node.data, str(node.data))
        else:
            obj["data"] = node.data
    return obj


def _data_repr(data):
    if isinstance(data, PrimOp):
        return PRIMOP_NAMES.get(data, str(data))
    return data


# ═══════════════════════════════════════════
# PATCH APPLICATION
# ═══════════════════════════════════════════

def patch(node, operations):
    """Apply a list of patch operations to a node graph.

    Returns the patched node (original is not modified).
    """
    result = copy.deepcopy(node)

    for op in operations:
        path = op["path"]
        parts = _parse_path(path)

        if op["op"] == "replace":
            new_node = _patch_to_node(op["new"])
            result = _set_at_path(result, parts, new_node)

        elif op["op"] == "modify_data":
            target = _get_at_path(result, parts)
            new_data = op["new"]
            if isinstance(new_data, str) and new_data in NAMES_PRIMOP:
                target.data = NAMES_PRIMOP[new_data]
            else:
                target.data = new_data

        elif op["op"] == "insert":
            parent_parts = parts[:-1]
            idx = parts[-1]
            parent = _get_at_path(result, parent_parts)
            new_node = _patch_to_node(op["new"])
            if isinstance(idx, int):
                parent.children.insert(idx, new_node)
            else:
                parent.children.append(new_node)

        elif op["op"] == "delete":
            parent_parts = parts[:-1]
            idx = parts[-1]
            parent = _get_at_path(result, parent_parts)
            if isinstance(idx, int) and idx < len(parent.children):
                parent.children.pop(idx)

    return result


def _parse_path(path):
    """Parse 'root.children[0].children[1]' into ['root', 0, 1]."""
    parts = []
    for segment in path.split('.'):
        if '[' in segment:
            name = segment[:segment.index('[')]
            idx = int(segment[segment.index('[') + 1:segment.index(']')])
            if name and name != "children":
                parts.append(name)
            parts.append(idx)
        else:
            parts.append(segment)
    return parts


def _get_at_path(node, parts):
    current = node
    for p in parts:
        if p == "root":
            continue
        if isinstance(p, int):
            current = current.children[p]
    return current


def _set_at_path(node, parts, new_node):
    if len(parts) <= 1:
        return new_node
    # Navigate to parent, replace child
    indices = [p for p in parts if isinstance(p, int)]
    if not indices:
        return new_node
    current = node
    for idx in indices[:-1]:
        current = current.children[idx]
    current.children[indices[-1]] = new_node
    return node


def _patch_to_node(obj):
    """Convert a patch node representation back to Node."""
    return _convert_node(obj)


# ═══════════════════════════════════════════
# DIFF STATS
# ═══════════════════════════════════════════

def diff_stats(operations):
    """Compute statistics about a diff."""
    return {
        "total_ops": len(operations),
        "replacements": sum(1 for o in operations if o["op"] == "replace"),
        "modifications": sum(1 for o in operations if o["op"] == "modify_data"),
        "insertions": sum(1 for o in operations if o["op"] == "insert"),
        "deletions": sum(1 for o in operations if o["op"] == "delete"),
    }


# ═══════════════════════════════════════════
# SCHEMA VALIDATION
# ═══════════════════════════════════════════

def validate_json(obj):
    """Validate a JSON-IR object against the schema (basic checks)."""
    errors = []

    if not isinstance(obj, dict):
        return ["Root must be an object"]
    if obj.get("version") != "xi-ir-v1":
        errors.append(f"Expected version 'xi-ir-v1', got '{obj.get('version')}'")
    if "root" not in obj:
        errors.append("Missing 'root' field")
    else:
        errors.extend(_validate_node(obj["root"], "root"))

    return errors


def _validate_node(obj, path):
    errors = []
    if not isinstance(obj, dict):
        return [f"{path}: node must be an object"]
    if "tag" not in obj:
        errors.append(f"{path}: missing 'tag'")
    elif obj["tag"] not in NAME_TAGS:
        errors.append(f"{path}: unknown tag '{obj['tag']}'")
    for i, child in enumerate(obj.get("children", [])):
        errors.extend(_validate_node(child, f"{path}.children[{i}]"))
    return errors


# ═══════════════════════════════════════════
# NODE PROPERTIES
# ═══════════════════════════════════════════

def analyze_properties(node):
    """Analyze properties of a Xi node graph for metadata."""
    props = []
    effects = set()

    def walk(n, depth=0):
        if n.tag == Tag.EFF:
            effects.add("io")
        if n.tag == Tag.FIX:
            props.append("recursive")
        if n.tag == Tag.PRIM and isinstance(n.data, PrimOp):
            if n.data == PrimOp.PRINT:
                effects.add("io")
        for c in n.children:
            walk(c, depth + 1)

    walk(node)

    if not effects:
        props.append("pure")
    if Tag.FIX not in _all_tags(node):
        props.append("terminates")
    if Tag.EFF not in _all_tags(node):
        props.append("no_effects")

    return {
        "properties": sorted(set(props)),
        "effects": sorted(effects)
    }


def _all_tags(node):
    tags = {node.tag}
    for c in node.children:
        tags |= _all_tags(c)
    return tags


def node_count(node):
    """Count total nodes in graph."""
    count = 1
    for c in node.children:
        count += node_count(c)
    return count


def max_depth(node):
    """Max depth of graph."""
    if not node.children:
        return 0
    return 1 + max(max_depth(c) for c in node.children)
