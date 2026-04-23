import argparse
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = ROOT / "graph" / "simple_graph.py"
DEFAULT_OUTPUT = ROOT / "simple_graph_diagram.mmd"


class CallCollector(ast.NodeVisitor):
    def __init__(self, known_functions):
        self.known_functions = known_functions
        self.calls = set()

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id in self.known_functions:
            self.calls.add(node.func.id)
        self.generic_visit(node)


def collect_call_graph(source_path):
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    graph = {}
    for name, node in functions.items():
        collector = CallCollector(set(functions))
        collector.visit(node)
        graph[name] = collector.calls
    return graph


def reachable_from(graph, entry, max_depth=None):
    if not entry:
        return set(graph)

    seen = set()
    queue = [(entry, 0)]
    while queue:
        name, depth = queue.pop(0)
        if name in seen or name not in graph:
            continue
        seen.add(name)
        if max_depth is not None and depth >= max_depth:
            continue
        queue.extend((child, depth + 1) for child in sorted(graph[name]))
    return seen


def mermaid_id(name):
    return "fn_" + "".join(char if char.isalnum() else "_" for char in name)


def build_mermaid(graph, selected, entry=None):
    lines = ["flowchart LR"]
    for name in sorted(selected):
        lines.append(f'    {mermaid_id(name)}["{name}"]')

    edges = [
        (caller, callee)
        for caller in selected
        for callee in graph.get(caller, set())
        if callee in selected
    ]
    for caller, callee in sorted(edges):
        lines.append(f"    {mermaid_id(caller)} --> {mermaid_id(callee)}")

    if entry in selected:
        lines.append(f"    class {mermaid_id(entry)} entry")
        lines.append("    classDef entry fill:#dbeafe,stroke:#2563eb,stroke-width:2px")
    return "\n".join(lines) + "\n"


def write_preview_html(mermaid_path, mermaid_text):
    html_path = mermaid_path.with_suffix(".html")
    html_path.write_text(
        """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>simple_graph.py diagram</title>
  <script type="module">
    import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
    mermaid.initialize({ startOnLoad: true });
  </script>
</head>
<body>
  <pre class="mermaid">
"""
        + mermaid_text
        + """  </pre>
</body>
</html>
""",
        encoding="utf-8",
    )
    return html_path


def main():
    parser = argparse.ArgumentParser(description="Generate a Mermaid call diagram for graph/simple_graph.py")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--entry", default="run_chat", help="Entry function to diagram. Use --all for every function.")
    parser.add_argument("--depth", type=int, default=None, help="Limit traversal depth from --entry.")
    parser.add_argument("--all", action="store_true", help="Diagram every top-level function.")
    args = parser.parse_args()

    graph = collect_call_graph(args.source)
    entry = None if args.all else args.entry
    selected = reachable_from(graph, entry, args.depth)
    mermaid_text = build_mermaid(graph, selected, entry=entry)

    args.output.write_text(mermaid_text, encoding="utf-8")
    html_path = write_preview_html(args.output, mermaid_text)
    print(f"Wrote Mermaid diagram: {args.output}")
    print(f"Wrote browser preview:  {html_path}")


if __name__ == "__main__":
    main()
