"""
Diagram Generation and Patent Drawing Tools

Provides MCP tools for creating technical diagrams in patent-style formats.
Generates flowcharts, block diagrams, and other technical visualizations using Graphviz.

Tools:
    - render_diagram: Render Graphviz DOT code to SVG/PNG/PDF diagrams
    - create_flowchart: Create patent-style flowcharts with steps and decisions
    - create_block_diagram: Create system architecture block diagrams
    - add_diagram_references: Add patent-style reference numbers to SVG diagrams
    - get_diagram_templates: Retrieve common diagram templates in DOT language
    - check_diagram_tools_status: Check Graphviz installation and readiness

Dependencies:
    - PatentDiagramGenerator, check_graphviz_installed from diagram_generator
    - Path from pathlib
    - Validation models from validation.py
"""

from pathlib import Path
from typing import Any, Optional


def _resolve_under_cwd(user_path: str, default_subdir: str) -> Path:
    """Resolve a user-supplied path under cwd, rejecting any escape."""
    cwd = Path.cwd().resolve()
    if not user_path:
        return cwd / default_subdir
    candidate = Path(user_path)
    candidate = candidate.resolve() if candidate.is_absolute() else (cwd / candidate).resolve()
    try:
        candidate.relative_to(cwd)
    except ValueError as e:
        raise ValueError(
            f"path must be inside the project directory ({cwd}); got: {user_path}"
        ) from e
    return candidate


def register_diagram_tools(
    mcp,
    log_info,
    log_error,
    log_warning,
    validate_input,
    RenderDiagramInput,
    track_performance,
):
    """Register diagram generation tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        log_info: Logging function for info messages
        log_error: Logging function for error messages
        log_warning: Logging function for warning messages
        validate_input: Input validation function
        RenderDiagramInput: Pydantic model for diagram validation
        track_performance: Performance tracking decorator
    """

    @mcp.tool()
    @track_performance("tool_render_diagram")
    def render_diagram(
        dot_code: str,
        filename: str = "diagram",
        output_format: str = "svg",
        engine: str = "dot",
        output_dir: str = "",
    ) -> dict[str, Any]:
        """
        Render a technical diagram from Graphviz DOT code.

        Use this tool to convert DOT language code into patent-style technical drawings.
        Claude should generate the DOT code based on user's description, then call this tool to render it.

        Args:
            dot_code: Complete Graphviz DOT language code for the diagram
            filename: Output filename (without extension, default: "diagram")
            output_format: Output format - "svg" (default), "png", or "pdf"
            engine: Graphviz layout engine - "dot" (hierarchical), "neato" (spring),
                    "fdp" (force-directed), "circo" (circular), "twopi" (radial)

        Returns:
            Dict with "path" (file path), "format", "success", and optional "error"

        Example DOT code:
            digraph Example {
                A [label="Start"];
                B [label="Process"];
                C [label="End"];
                A -> B -> C;
            }
        """
        try:
            validated = validate_input(
                RenderDiagramInput,
                dot_code=dot_code,
                filename=filename,
                output_format=output_format,
                engine=engine,
            )
            dot_code = validated.dot_code
            filename = validated.filename
            output_format = validated.output_format
            engine = validated.engine

            from diagram_generator import (
                PatentDiagramGenerator,
                check_graphviz_installed,
            )

            # Check if Graphviz is available
            status = check_graphviz_installed()
            if not status["ready"]:
                return {
                    "success": False,
                    "error": f"Graphviz not installed. {status.get('message', 'See https://graphviz.org/download/')}",
                    "status": status,
                }

            target_dir = _resolve_under_cwd(output_dir, "diagrams")
            generator = PatentDiagramGenerator(output_dir=target_dir)
            output_path = generator.render_dot_diagram(
                dot_code=dot_code,
                filename=filename,
                output_format=output_format,
                engine=engine,
            )

            return {
                "success": True,
                "path": str(output_path.absolute()),
                "format": output_format,
                "message": f"Diagram rendered successfully to {output_path.name}",
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to render diagram: {str(e)}"}

    @mcp.tool()
    @track_performance("tool_create_flowchart")
    def create_flowchart(
        steps: list[dict[str, Any]], filename: str = "flowchart", output_format: str = "svg",
        output_dir: str = "",
    ) -> dict[str, Any]:
        """
        Create a patent-style flowchart from a list of steps.

        Args:
            steps: List of step dictionaries with keys:
                - "id": Unique identifier (e.g., "start", "step1")
                - "label": Display label (e.g., "Initialize System")
                - "shape": Node shape - "box" (default), "ellipse" (start/end), "diamond" (decision)
                - "next": List of next step IDs (e.g., ["step2", "step3"])
            filename: Output filename (default: "flowchart")
            output_format: Output format - "svg" (default), "png", or "pdf"

        Returns:
            Dict with "path", "format", "success", and optional "error"

        Example steps:
            [
                {"id": "start", "label": "Start", "shape": "ellipse", "next": ["step1"]},
                {"id": "step1", "label": "Process Data", "shape": "box", "next": ["decision"]},
                {"id": "decision", "label": "Valid?", "shape": "diamond", "next": ["step2", "end"]},
                {"id": "step2", "label": "Save Result", "shape": "box", "next": ["end"]},
                {"id": "end", "label": "End", "shape": "ellipse", "next": []}
            ]
        """
        try:
            from diagram_generator import (
                PatentDiagramGenerator,
                check_graphviz_installed,
            )

            status = check_graphviz_installed()
            if not status["ready"]:
                return {
                    "success": False,
                    "error": f"Graphviz not installed. {status.get('message', 'See https://graphviz.org/download/')}",
                }

            target_dir = _resolve_under_cwd(output_dir, "diagrams")
            generator = PatentDiagramGenerator(output_dir=target_dir)
            output_path = generator.create_flowchart(
                steps=steps, filename=filename, output_format=output_format
            )

            return {
                "success": True,
                "path": str(output_path.absolute()),
                "format": output_format,
                "num_steps": len(steps),
                "message": f"Flowchart with {len(steps)} steps rendered to {output_path.name}",
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to create flowchart: {str(e)}"}

    @mcp.tool()
    @track_performance("tool_create_block_diagram")
    def create_block_diagram(
        blocks: list[dict[str, Any]],
        connections: list[list[str]],
        filename: str = "block_diagram",
        output_format: str = "svg",
        output_dir: str = "",
    ) -> dict[str, Any]:
        """
        Create a patent-style block diagram showing system components and connections.

        Args:
            blocks: List of block dictionaries with keys:
                - "id": Unique identifier (e.g., "input", "processor")
                - "label": Display label (use \\n for line breaks, e.g., "Input\\nSensor")
                - "type": Block type - "input", "output", "process", "storage", "decision", or "default"
            connections: List of connection lists, each with 2-3 elements:
                - [from_id, to_id] or [from_id, to_id, label]
            filename: Output filename (default: "block_diagram")
            output_format: Output format - "svg" (default), "png", or "pdf"

        Returns:
            Dict with "path", "format", "success", and optional "error"

        Example:
            blocks = [
                {"id": "sensor", "label": "Input\\nSensor", "type": "input"},
                {"id": "cpu", "label": "Central\\nProcessor", "type": "process"},
                {"id": "display", "label": "Output\\nDisplay", "type": "output"}
            ]
            connections = [
                ["sensor", "cpu", "raw data"],
                ["cpu", "display", "processed data"]
            ]
        """
        try:

            from diagram_generator import (
                PatentDiagramGenerator,
                check_graphviz_installed,
            )

            status = check_graphviz_installed()
            if not status["ready"]:
                return {
                    "success": False,
                    "error": f"Graphviz not installed. {status.get('message', 'See https://graphviz.org/download/')}",
                }

            # Convert connections to tuples with proper typing
            connections_tuples: list[tuple[str, str, Optional[str]]] = [
                (conn[0], conn[1], conn[2] if len(conn) > 2 else None) for conn in connections
            ]

            target_dir = _resolve_under_cwd(output_dir, "diagrams")
            generator = PatentDiagramGenerator(output_dir=target_dir)
            output_path = generator.create_block_diagram(
                blocks=blocks,
                connections=connections_tuples,
                filename=filename,
                output_format=output_format,
            )

            return {
                "success": True,
                "path": str(output_path.absolute()),
                "format": output_format,
                "num_blocks": len(blocks),
                "num_connections": len(connections),
                "message": f"Block diagram with {len(blocks)} blocks rendered to {output_path.name}",
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to create block diagram: {str(e)}"}

    @mcp.tool()
    @track_performance("tool_add_diagram_references")
    def add_diagram_references(svg_path: str, reference_map: dict[str, int]) -> dict[str, Any]:
        """
        Add patent-style reference numbers to an existing SVG diagram.

        Args:
            svg_path: Path to input SVG file (from render_diagram or create_* tools)
            reference_map: Dictionary mapping element text/label to reference number
                Example: {"Input Sensor": 10, "Processor": 20, "Display": 30}

        Returns:
            Dict with "path" to annotated SVG, "success", and optional "error"

        Note: Reference numbers are added in parentheses after matching text (e.g., "Processor (20)")
        """
        try:
            from diagram_generator import PatentDiagramGenerator

            if not svg_path:
                return {"success": False, "error": "svg_path is required"}

            generator = PatentDiagramGenerator()
            try:
                input_path = _resolve_under_cwd(svg_path, "diagrams")
            except ValueError as ve:
                return {"success": False, "error": str(ve)}

            if not input_path.is_file():
                return {"success": False, "error": f"SVG file not found: {svg_path}"}

            output_path = generator.add_reference_numbers(
                svg_path=input_path, reference_map=reference_map
            )

            return {
                "success": True,
                "path": str(output_path.absolute()),
                "num_references": len(reference_map),
                "message": f"Added {len(reference_map)} reference numbers to {output_path.name}",
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to add references: {str(e)}"}

    @mcp.tool()
    @track_performance("tool_get_diagram_templates")
    def get_diagram_templates() -> dict[str, Any]:
        """
        Get common patent diagram templates in DOT language.

        Returns:
            Dictionary mapping template names to DOT code. Templates include:
            - "simple_flowchart": Basic process flow with start/end
            - "system_block": System architecture with components
            - "method_steps": Sequential method steps with numbering
            - "component_hierarchy": Hierarchical component structure

        Use these as starting points and modify the DOT code as needed.
        """
        try:
            from diagram_generator import PatentDiagramGenerator

            generator = PatentDiagramGenerator()
            templates = generator.get_templates()

            return {
                "success": True,
                "templates": templates,
                "available": list(templates.keys()),
                "message": f"Retrieved {len(templates)} diagram templates",
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to get templates: {str(e)}"}

    @mcp.tool()
    @track_performance("tool_check_diagram_tools_status")
    def check_diagram_tools_status() -> dict[str, Any]:
        """
        Check if diagram generation tools are installed and ready.

        Returns:
            Status information about Graphviz installation and readiness
        """
        try:
            from diagram_generator import check_graphviz_installed

            status = check_graphviz_installed()

            if status["ready"]:
                message = f"Diagram tools ready. Graphviz version {status['version']}"
            elif status["python_package"] and not status["system_command"]:
                message = f"Python package installed but system Graphviz missing. {status.get('message', 'See https://graphviz.org/download/')}"
            elif not status["python_package"]:
                message = "Python graphviz package missing. Install with: pip install graphviz"
            else:
                message = "Diagram tools not ready"

            return {**status, "message": message}

        except Exception as e:
            return {"ready": False, "error": f"Failed to check status: {str(e)}"}
