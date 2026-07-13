"""Flowchart decision branches must be labelable (issue #60).

Patent flowcharts (MPEP 608.02) need Yes/No labels on decision-diamond
branches; unlabeled branch edges are ambiguous. `next` entries may be
plain step-id strings (back-compat) or {"id": ..., "label": ...} objects.
"""

import pytest

from mcp_server.diagram_generator import PatentDiagramGenerator


@pytest.fixture
def dot_of(tmp_path, monkeypatch):
    """Run create_flowchart but capture the DOT instead of rendering."""
    generator = PatentDiagramGenerator(output_dir=tmp_path)
    captured = {}

    def fake_render(dot_code, filename, output_format):
        captured["dot"] = dot_code
        return tmp_path / f"{filename}.{output_format}"

    monkeypatch.setattr(generator, "render_dot_diagram", fake_render)

    def run(steps):
        generator.create_flowchart(steps=steps)
        return captured["dot"]

    return run


def test_labeled_branch_edges(dot_of):
    dot = dot_of(
        [
            {"id": "decision", "label": "Valid?", "shape": "diamond",
             "next": [{"id": "save", "label": "Yes"}, {"id": "end", "label": "No"}]},
            {"id": "save", "label": "Save", "shape": "box", "next": ["end"]},
            {"id": "end", "label": "End", "shape": "ellipse", "next": []},
        ]
    )
    assert '"decision" -> "save" [label="Yes"];' in dot
    assert '"decision" -> "end" [label="No"];' in dot


def test_plain_string_next_still_works(dot_of):
    dot = dot_of(
        [
            {"id": "a", "label": "A", "next": ["b"]},
            {"id": "b", "label": "B", "next": []},
        ]
    )
    assert '"a" -> "b";' in dot


def test_label_quotes_are_escaped(dot_of):
    dot = dot_of(
        [
            {"id": "a", "label": "A",
             "next": [{"id": "b", "label": 'edge "label"'}]},
            {"id": "b", "label": "B", "next": []},
        ]
    )
    assert '"a" -> "b" [label="edge \\"label\\""];' in dot
