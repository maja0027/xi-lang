# API: xi_graphviz.py — Graph Visualization

Generates Graphviz DOT representations of Xi node graphs for debugging and presentation.

## Functions

### `to_dot(node: Node, title: str = "") → str`
Converts a Node graph to DOT format string.

### `render_svg(node: Node, output_path: str)`
Renders the graph directly to an SVG file (requires `graphviz` system package).

### `render_png(node: Node, output_path: str)`
Renders the graph to a PNG file.

## Node Styling

Each node type gets a distinctive color:

| Tag | Color | Shape |
|-----|-------|-------|
| λ (Lambda) | Indigo | Ellipse |
| @ (Application) | Amber | Box |
| Π (Pi) | Purple | Diamond |
| μ (Fix) | Red | Octagon |
| # (Primitive) | Green | Box |
| ι (Inductive) | Teal | Hexagon |

## Example
```python
from xi_graphviz import to_dot
from xi_compiler import Compiler

node = Compiler().compile_expr("λx. x + x")
dot = to_dot(node, title="double")
# Write to file and render: dot -Tsvg output.dot -o output.svg
```
