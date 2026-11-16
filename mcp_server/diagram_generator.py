#!/usr/bin/env python3
"""
Patent Diagram Generator
Renders technical diagrams from DOT code with patent-style annotations
"""

import os

try:
    from cli_command import render as _render_cmd
except ImportError:
    try:
        from mcp_server.cli_command import render as _render_cmd
    except ImportError:  # pragma: no cover - keep messages even if the helper is missing

        def _render_cmd(message: str) -> str:
            return message

import re
from pathlib import Path
from typing import Any, Optional

# Use defusedxml for secure XML parsing (prevents XML bombs and XXE attacks)
from defusedxml import ElementTree as ET

try:
    import graphviz
except ImportError:
    graphviz = None

try:
    from .graphviz_installer import GraphvizInstaller
except ImportError:
    GraphvizInstaller = None


# Default output directory for generated diagrams (created lazily in __init__,
# not at import time) — resolved outside site-packages (see data_paths / #51).
try:
    from data_paths import diagrams_dir
except ImportError:
    from mcp_server.data_paths import diagrams_dir

PROJECT_ROOT = Path(__file__).parent.parent
DIAGRAMS_DIR = diagrams_dir()

_LENGTH = re.compile(r"\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)\s*(em|ex|px|pt|%)?\s*$", re.IGNORECASE)


def _length(value: str, font_size: float) -> Optional[float]:
    """An SVG length in px, or None when it cannot be read. dx, dy and y may
    list several values; the first applies to the tspan's first character."""
    first = value.replace(",", " ").split()
    match = _LENGTH.match(first[0]) if first else None
    if not match:
        return None
    number = float(match.group(1))
    unit = (match.group(2) or "px").lower()
    if unit == "%":
        return None
    return {"em": number * font_size, "ex": number * font_size / 2, "pt": number * 4 / 3}.get(unit, number)


def _font_size(element, inherited: float) -> float:
    """The element's font size in px (font-size attribute or style), else inherited."""
    value = element.get("font-size", "")
    style = re.search(r"font-size\s*:\s*([^;]+)", element.get("style", ""))
    if style:
        value = style.group(1)
    size = _length(value, inherited) if value else None
    return size if size and size > 0 else inherited


def _inherited_font_size(element, parent_of: dict) -> float:
    """The font size a <text> inherits from its enclosing groups (default 14px)."""
    chain = []
    node = parent_of.get(element)
    while node is not None:
        chain.append(node)
        node = parent_of.get(node)
    size = 14.0
    for ancestor in reversed(chain):
        size = _font_size(ancestor, size)
    return size


# Attributes Graphviz changes between styled runs of one label line.
_RUN_STYLE = ("font-weight", "font-style", "font-family", "font-size", "baseline-shift",
              "fill", "text-decoration", "style")


def _join_text_elements(texts: list, parent_of: dict) -> tuple[str, str]:
    """One node's label from its <text> elements, read two ways.

    Graphviz writes each line of a multiline label as its own <text>, each
    record field or table cell as its own <text>, and also each styled run of
    one line (a subscript, a bold or italic word) as its own <text>. A new
    line, or a neighbour in the same style (a separate field or cell), always
    gets a space. A neighbour on the same baseline in a different style is
    either a styled run of the same line ("V" + subscript "out" reads "Vout")
    or a differently styled table cell ("Input" | bold "Sensor"); the SVG does
    not say which, so the label is returned both joined and spaced at those
    points, and a reference matching either reading counts.
    """
    joined, spaced = [], []
    previous = None
    previous_y = None
    for text in texts:
        size = _inherited_font_size(text, parent_of)
        rendered = _rendered_text(text, size)
        own_size = _font_size(text, size)
        y = _length(text.get("y", ""), own_size)
        maybe_run = (
            previous is not None
            and y is not None and previous_y is not None
            and abs(y - previous_y) < 0.8 * own_size
            and any(previous.get(a) != text.get(a) for a in _RUN_STYLE)
        )
        if joined:
            spaced.append(" ")
            if not maybe_run:
                joined.append(" ")
        joined.append(rendered)
        spaced.append(rendered)
        previous, previous_y = text, y
    return "".join(joined), "".join(spaced)


def _starts_new_line(tspan, font_size: float, baseline: Optional[float]) -> bool:
    """Whether a tspan begins a new rendered line.

    A tspan that sets x starts a new line. So does a move of the baseline by
    about a line height (0.8em or more), whether through dy or an absolute y.
    A horizontal nudge alone (dx, as kerning uses) stays on the line. Smaller shifts (dy="0",
    subscripts) and inline formatting continue the same line:
    <tspan>Pro</tspan><tspan dy="0">cessor</tspan> renders as "Processor".
    """
    if "x" in tspan.attrib:
        return True
    shift = _length(tspan.get("dy", ""), font_size)
    y = _length(tspan.get("y", ""), font_size)
    # A shift the reader cannot measure (calc(), a percentage) is treated as a
    # new line, so the label keeps a separating space.
    if (shift is None and tspan.get("dy", "").strip()) or (y is None and tspan.get("y", "").strip()):
        return True
    if y is not None:
        if baseline is None:
            return True
        shift = (shift or 0) + y - baseline
    return shift is not None and abs(shift) >= 0.8 * font_size


def _rendered_text(element, font_size: float = 14.0, baseline: Optional[float] = None) -> str:
    """The text an SVG <text> element shows: inline pieces joined as rendered,
    with a space only where a tspan starts a new line."""
    font_size = _font_size(element, font_size)
    own_y = _length(element.get("y", ""), font_size)
    if own_y is not None:
        baseline = own_y
    parts = [element.text or ""]
    for child in element:
        if child.tag.endswith("tspan"):
            size = _font_size(child, font_size)
            if _starts_new_line(child, size, baseline):
                parts.append(" ")
            # Track where the baseline now sits: an absolute y sets it, a
            # relative dy moves it.
            child_y = _length(child.get("y", ""), size)
            child_dy = _length(child.get("dy", ""), size)
            if child_y is not None:
                baseline = child_y + (child_dy or 0)
            elif child_dy is not None and baseline is not None:
                baseline += child_dy
        parts.append(_rendered_text(child, font_size, baseline))
        parts.append(child.tail or "")
    return "".join(parts)


class PatentDiagramGenerator:
    """Generate patent-style technical diagrams"""

    def __init__(self, output_dir: Path = DIAGRAMS_DIR):
        """
        Initialize diagram generator

        Args:
            output_dir: Directory to save generated diagrams
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if not graphviz:
            if GraphvizInstaller:
                installer = GraphvizInstaller()
                instructions = installer.get_diagnostic_info()
                raise ImportError(f"Graphviz not available.\n\n{instructions}")
            else:
                raise ImportError(
                    "Graphviz not available. Install with:\n"
                    + _render_cmd("1. pip install graphviz\n")
                    + "2. System Graphviz:\n"
                    + "   - Windows: winget install graphviz\n"
                    + "   - macOS: brew install graphviz\n"
                    + "   - Linux: sudo apt install graphviz"
                )

    def render_dot_diagram(
        self,
        dot_code: str,
        filename: str,
        output_format: str = "svg",
        engine: str = "dot",
    ) -> Path:
        """
        Render DOT code to image file

        Args:
            dot_code: Graphviz DOT language code
            filename: Output filename (without extension)
            output_format: Output format ("svg", "png", "pdf")
            engine: Graphviz layout engine ("dot", "neato", "fdp", "circo", "twopi")

        Returns:
            Path to rendered diagram file
        """
        if not graphviz:
            raise ImportError("Graphviz not available")

        # Validate output_format and engine against whitelists
        allowed_formats = {"svg", "png", "pdf"}
        if output_format not in allowed_formats:
            raise ValueError(f"Invalid output_format '{output_format}'. Must be one of: {allowed_formats}")
        allowed_engines = {"dot", "neato", "fdp", "circo", "twopi", "sfdp"}
        if engine not in allowed_engines:
            raise ValueError(f"Invalid engine '{engine}'. Must be one of: {allowed_engines}")

        # Clean filename
        filename = re.sub(r"[^\w\-_]", "_", filename)

        # Create graphviz source
        src = graphviz.Source(dot_code, engine=engine)

        # Render to file
        output_path = self.output_dir / filename
        rendered_path = src.render(
            filename=str(output_path),
            format=output_format,
            cleanup=True,  # Remove intermediate DOT file
        )

        return Path(rendered_path)

    def create_flowchart(
        self,
        steps: list[dict[str, str]],
        filename: str = "flowchart",
        output_format: str = "svg",
    ) -> Path:
        """
        Create a flowchart from a list of steps

        Args:
            steps: List of step dicts with keys: "id", "label", "shape", "next"
            filename: Output filename
            output_format: Output format

        Returns:
            Path to rendered diagram

        Example steps:
            [
                {"id": "start", "label": "Start", "shape": "ellipse", "next": ["step1"]},
                {"id": "step1", "label": "Process data", "shape": "box", "next": ["decision"]},
                {"id": "decision", "label": "Valid?", "shape": "diamond",
                 "next": [{"id": "step2", "label": "Yes"}, {"id": "end", "label": "No"}]},
                {"id": "step2", "label": "Save result", "shape": "box", "next": ["end"]},
                {"id": "end", "label": "End", "shape": "ellipse", "next": []}
            ]

        A "next" entry is either a step-id string or {"id", "label"} to
        label the edge (required for unambiguous decision branches).
        """
        # Build DOT code
        dot_lines = [
            "digraph Flowchart {",
            "    rankdir=TB;",
            '    node [fontname="Arial", fontsize=10];',
            '    edge [fontname="Arial", fontsize=9];',
            "",
        ]

        # Add nodes
        for step in steps:
            node_id = step["id"]
            label = step["label"].replace('"', '\\"')
            shape = step.get("shape", "box")

            dot_lines.append(f'    "{node_id}" [label="{label}", shape={shape}];')

        dot_lines.append("")

        # Add edges. A `next` entry is a step-id string, or {"id", "label"}
        # to label the edge — decision-diamond branches need Yes/No labels
        # to be unambiguous in a patent figure (issue #60).
        for step in steps:
            node_id = step["id"]
            next_nodes = step.get("next", [])

            for next_node in next_nodes:
                if isinstance(next_node, dict):
                    target = next_node["id"]
                    edge_label = next_node.get("label", "")
                else:
                    target = next_node
                    edge_label = ""
                if edge_label:
                    escaped = edge_label.replace('"', '\\"')
                    dot_lines.append(
                        f'    "{node_id}" -> "{target}" [label="{escaped}"];'
                    )
                else:
                    dot_lines.append(f'    "{node_id}" -> "{target}";')

        dot_lines.append("}")

        dot_code = "\n".join(dot_lines)

        return self.render_dot_diagram(dot_code, filename, output_format)

    def create_block_diagram(
        self,
        blocks: list[dict[str, Any]],
        connections: list[tuple[str, str, Optional[str]]],
        filename: str = "block_diagram",
        output_format: str = "svg",
    ) -> Path:
        """
        Create a block diagram

        Args:
            blocks: List of block dicts with keys: "id", "label", "type"
            connections: List of tuples (from_id, to_id, label)
            filename: Output filename
            output_format: Output format

        Returns:
            Path to rendered diagram

        Example:
            blocks = [
                {"id": "input", "label": "Input\\nSensor", "type": "input"},
                {"id": "processor", "label": "Data\\nProcessor", "type": "process"},
                {"id": "output", "label": "Output\\nDisplay", "type": "output"}
            ]
            connections = [
                ("input", "processor", "raw data"),
                ("processor", "output", "processed data")
            ]
        """
        # Build DOT code
        dot_lines = [
            "digraph BlockDiagram {",
            "    rankdir=LR;",
            '    node [fontname="Arial", fontsize=10, style=filled];',
            '    edge [fontname="Arial", fontsize=9];',
            "",
        ]

        # Define block types
        block_styles = {
            "input": "shape=invhouse, fillcolor=lightblue",
            "output": "shape=house, fillcolor=lightgreen",
            "process": "shape=box, fillcolor=lightyellow",
            "storage": "shape=cylinder, fillcolor=lightgray",
            "decision": "shape=diamond, fillcolor=lightcoral",
            "default": "shape=box, fillcolor=white",
        }

        # Add blocks
        for block in blocks:
            block_id = block["id"]
            label = block["label"].replace('"', '\\"')
            block_type = block.get("type", "default")
            style = block_styles.get(block_type, block_styles["default"])

            dot_lines.append(f'    "{block_id}" [label="{label}", {style}];')

        dot_lines.append("")

        # Add connections
        for conn in connections:
            from_id, to_id = conn[0], conn[1]
            label = conn[2] if len(conn) > 2 and conn[2] else ""

            if label:
                dot_lines.append(f'    "{from_id}" -> "{to_id}" [label="{label}"];')
            else:
                dot_lines.append(f'    "{from_id}" -> "{to_id}";')

        dot_lines.append("}")

        dot_code = "\n".join(dot_lines)

        return self.render_dot_diagram(dot_code, filename, output_format)

    def add_reference_numbers(
        self, svg_path: Path, reference_map: dict[str, int], *, return_report: bool = False
    ) -> Any:
        """
        Add patent-style reference numbers to an SVG diagram

        Args:
            svg_path: Path to input SVG file
            reference_map: Dict mapping element text/id to reference number

        Returns:
            Path to annotated SVG file, or a change report when return_report=True

        Example:
            reference_map = {
                "Input Sensor": 10,
                "Data Processor": 20,
                "Output Display": 30
            }
        """
        # Validate svg_path is within the output directory to prevent path traversal
        resolved_svg = svg_path.resolve()
        resolved_output = self.output_dir.resolve()
        if not str(resolved_svg).startswith(str(resolved_output) + os.sep) and resolved_svg.parent != resolved_output:
            raise ValueError(
                f"SVG path must be within the diagrams directory ({resolved_output}), "
                f"got: {resolved_svg}"
            )

        # Parse SVG
        tree = ET.parse(svg_path)
        root = tree.getroot()

        # SVG namespace
        ns = {"svg": "http://www.w3.org/2000/svg"}

        if root is None:
            raise ValueError("SVG has no root element")

        # Graphviz emits multiline labels as sibling text elements in a node.
        # Other renderers use tspans inside one text element.
        groups = []
        grouped = set()
        for node in root.findall(".//svg:g", ns):
            if "node" in node.get("class", "").split():
                texts = node.findall(".//svg:text", ns)
                if texts:
                    groups.append(texts)
                    grouped.update(texts)
        groups.extend([text] for text in root.findall(".//svg:text", ns) if text not in grouped)
        parent_of = {child: parent for parent in root.iter() for child in parent}
        matched = set()
        count = 0
        readings = [
            tuple(" ".join(label.split()).casefold() for label in _join_text_elements(texts, parent_of))
            for texts in groups
        ]

        def first_match(label: str, allowed) -> Optional[tuple[str, int]]:
            for pattern, ref_num in reference_map.items():
                normalized = " ".join(pattern.split()).casefold()
                if normalized and normalized in label and allowed(pattern):
                    return pattern, ref_num
            return None

        # The spaced reading of every node is certain, so it is matched first
        # across the whole drawing. The joined reading (styled runs read as one
        # word) is a fallback for nodes still unmatched, and only for
        # references no node matched exactly, so a guess never takes a label
        # that belongs to another node.
        choices = [first_match(spaced, lambda _p: True) for _joined, spaced in readings]
        exact = {c[0] for c in choices if c}
        for i, (joined, spaced) in enumerate(readings):
            if choices[i] is None and joined != spaced:
                choices[i] = first_match(joined, lambda p: p not in exact)

        for texts, choice in zip(groups, choices):
            if not choice:
                continue
            pattern, ref_num = choice
            target = texts[-1]
            tspans = target.findall(".//svg:tspan", ns)
            if tspans:
                target = tspans[-1]
            target.text = f"{target.text or ''} ({ref_num})"
            matched.add(pattern)
            count += 1

        # Save annotated SVG
        output_path = svg_path.parent / f"{svg_path.stem}_annotated{svg_path.suffix}"
        tree.write(output_path, encoding="utf-8", xml_declaration=True)

        if return_report:
            return {"path": output_path, "num_references": count,
                    "unmatched_labels": [label for label in reference_map if label not in matched]}
        return output_path

    def get_templates(self) -> dict[str, str]:
        """
        Get common patent diagram templates

        Returns:
            Dict of template name to DOT code
        """
        templates = {
            "simple_flowchart": """
digraph SimpleFlowchart {
    rankdir=TB;
    node [fontname="Arial", fontsize=10, shape=box];

    start [label="Start", shape=ellipse];
    step1 [label="Step 1:\\nInitialize"];
    step2 [label="Step 2:\\nProcess"];
    decision [label="Success?", shape=diamond];
    step3 [label="Step 3:\\nFinalize"];
    end [label="End", shape=ellipse];

    start -> step1;
    step1 -> step2;
    step2 -> decision;
    decision -> step3 [label="Yes"];
    decision -> step1 [label="No"];
    step3 -> end;
}
""",
            "system_block": """
digraph SystemBlock {
    rankdir=LR;
    node [fontname="Arial", fontsize=10, style=filled];

    input [label="Input\\nDevice", shape=invhouse, fillcolor=lightblue];
    controller [label="Controller\\nUnit", shape=box, fillcolor=lightyellow];
    processor [label="Processing\\nModule", shape=box, fillcolor=lightyellow];
    memory [label="Memory\\nStorage", shape=cylinder, fillcolor=lightgray];
    output [label="Output\\nDevice", shape=house, fillcolor=lightgreen];

    input -> controller [label="signals"];
    controller -> processor [label="commands"];
    processor -> memory [label="data"];
    memory -> processor [label="data"];
    processor -> output [label="results"];
}
""",
            "method_steps": """
digraph MethodSteps {
    rankdir=TB;
    node [fontname="Arial", fontsize=10, shape=box, style=filled, fillcolor=lightyellow];

    step101 [label="101. Receive input data"];
    step102 [label="102. Validate data format"];
    step103 [label="103. Process data"];
    step104 [label="104. Generate output"];
    step105 [label="105. Transmit result"];

    step101 -> step102;
    step102 -> step103;
    step103 -> step104;
    step104 -> step105;
}
""",
            "component_hierarchy": """
digraph ComponentHierarchy {
    rankdir=TB;
    node [fontname="Arial", fontsize=10, shape=box];

    system [label="System 10", shape=box3d];
    subsystem1 [label="Subsystem 20"];
    subsystem2 [label="Subsystem 30"];
    component21 [label="Component 21"];
    component22 [label="Component 22"];
    component31 [label="Component 31"];
    component32 [label="Component 32"];

    system -> subsystem1;
    system -> subsystem2;
    subsystem1 -> component21;
    subsystem1 -> component22;
    subsystem2 -> component31;
    subsystem2 -> component32;
}
""",
        }

        return templates


def check_graphviz_installed() -> dict[str, Any]:
    """Check if Graphviz is installed and available"""
    if GraphvizInstaller:
        installer = GraphvizInstaller()
        status = installer.status
        if not status["ready"]:
            status["message"] = installer.get_installation_instructions()
        return status

    # Fallback if installer not available
    status: dict[str, Any] = {
        "python_package": graphviz is not None,
        "system_command": False,
        "version": None,
        "ready": False,
    }

    if not graphviz:
        status["message"] = _render_cmd("Python graphviz package not installed. Run: pip install graphviz")
        return status

    # Check if system graphviz is available
    try:
        import subprocess

        result = subprocess.run(["dot", "-V"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            status["system_command"] = True
            # Extract version from output like "dot - graphviz version 2.43.0"
            version_match = re.search(r"version (\d+\.\d+\.\d+)", result.stderr)
            if version_match:
                status["version"] = version_match.group(1)
    except Exception:
        pass

    status["ready"] = status["python_package"] and status["system_command"]

    if not status["ready"]:
        import platform as _platform

        system = _platform.system()
        if system == "Darwin":
            cmd = "brew install graphviz"
        elif system == "Windows":
            cmd = "winget install graphviz"
        else:
            cmd = "sudo apt-get install graphviz"
        status["message"] = (
            f"The free Graphviz program is missing. Install it by running: {cmd} "
            "(or see https://graphviz.org/download/), then restart Claude Code."
        )

    return status
