#!/usr/bin/env python3
"""
Patent Diagram Generator
Renders technical diagrams from DOT code with patent-style annotations
"""

import os
import re
from pathlib import Path

# Use defusedxml for secure XML parsing (prevents XML bombs and XXE attacks)
try:
    from defusedxml import ElementTree as ET
except ImportError:
    # Fallback to standard library if defusedxml not available
    # Note: This is less secure and should only be used for trusted, locally-generated files
    from xml.etree import ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

try:
    import graphviz
except ImportError:
    graphviz = None

try:
    from .graphviz_installer import GraphvizInstaller
except ImportError:
    GraphvizInstaller = None


# Output directory for generated diagrams
PROJECT_ROOT = Path(__file__).parent.parent
DIAGRAMS_DIR = PROJECT_ROOT / "diagrams"
DIAGRAMS_DIR.mkdir(exist_ok=True)


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
                    "1. pip install graphviz\n"
                    "2. System Graphviz:\n"
                    "   - Windows: winget install graphviz\n"
                    "   - macOS: brew install graphviz\n"
                    "   - Linux: sudo apt install graphviz"
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
        steps: List[Dict[str, str]],
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
                {"id": "decision", "label": "Valid?", "shape": "diamond", "next": ["step2", "end"]},
                {"id": "step2", "label": "Save result", "shape": "box", "next": ["end"]},
                {"id": "end", "label": "End", "shape": "ellipse", "next": []}
            ]
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

        # Add edges
        for step in steps:
            node_id = step["id"]
            next_nodes = step.get("next", [])

            for next_node in next_nodes:
                dot_lines.append(f'    "{node_id}" -> "{next_node}";')

        dot_lines.append("}")

        dot_code = "\n".join(dot_lines)

        return self.render_dot_diagram(dot_code, filename, output_format)

    def create_block_diagram(
        self,
        blocks: List[Dict[str, Any]],
        connections: List[Tuple[str, str, Optional[str]]],
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

    def add_reference_numbers(self, svg_path: Path, reference_map: Dict[str, int]) -> Path:
        """
        Add patent-style reference numbers to an SVG diagram

        Args:
            svg_path: Path to input SVG file
            reference_map: Dict mapping element text/id to reference number

        Returns:
            Path to annotated SVG file

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

        # Find text elements and add reference numbers
        for text_elem in root.findall(".//svg:text", ns):
            text_content = "".join(text_elem.itertext()).strip()

            # Check if this text matches a reference
            for pattern, ref_num in reference_map.items():
                if pattern.lower() in text_content.lower():
                    # Add reference number in parentheses
                    # Graphviz puts text in <tspan> children, so check those first
                    tspans = text_elem.findall("svg:tspan", ns) if ns else text_elem.findall("tspan")
                    if tspans:
                        last_tspan = tspans[-1]
                        last_tspan.text = f"{last_tspan.text or ''} ({ref_num})"
                    elif text_elem.text:
                        text_elem.text = f"{text_elem.text} ({ref_num})"
                    break

        # Save annotated SVG
        output_path = svg_path.parent / f"{svg_path.stem}_annotated{svg_path.suffix}"
        tree.write(output_path, encoding="utf-8", xml_declaration=True)

        return output_path

    def get_templates(self) -> Dict[str, str]:
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


def check_graphviz_installed() -> Dict[str, Any]:
    """Check if Graphviz is installed and available"""
    if GraphvizInstaller:
        installer = GraphvizInstaller()
        status = installer.status
        if not status["ready"]:
            status["message"] = installer.get_installation_instructions()
        return status

    # Fallback if installer not available
    status = {
        "python_package": graphviz is not None,
        "system_command": False,
        "version": None,
        "ready": False,
    }

    if not graphviz:
        status["message"] = "Python graphviz package not installed. Run: pip install graphviz"
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
        status["message"] = "System Graphviz not installed. See installation instructions."

    return status
