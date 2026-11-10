"""Reference annotation reports actual changes and unmatched labels."""
import importlib
from pathlib import Path

import pytest

mod = importlib.import_module('mcp_server.tools.diagram_tools')


class Registry:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def register(fn):
            self.tools[fn.__name__] = fn
            return fn
        return register


@pytest.mark.parametrize(('content', 'references', 'count', 'unmatched'), [
    ('<g class="node"><text>Input</text><text>Sensor</text></g>', {'Input Sensor': 10}, 1, []),
    ('<text><tspan>Input</tspan><tspan>Sensor</tspan></text>', {'Input Sensor': 10}, 1, []),
    ('<text>Unknown</text>', {'Input Sensor': 10}, 0, ['Input Sensor']),
    ('<text>Input Sensor</text>', {'Input Sensor': 10, 'Other': 20}, 1, ['Other']),
])
def test_annotation_reports_actual_changes(content, references, count, unmatched, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    svg = tmp_path / 'input.svg'
    svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg">{content}</svg>')
    registry = Registry()
    mod.register_diagram_tools(registry, None, None, None, None, None, lambda _: lambda f: f)
    result = registry.tools['add_diagram_references'](str(svg), references)
    assert result['num_references'] == count
    assert result['unmatched_labels'] == unmatched
    assert result['success'] is (not unmatched)
    output = Path(result['path']).read_text()
    assert output.count('(10)') == count
    assert '(20)' not in output
