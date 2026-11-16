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


def test_exact_reading_wins_over_a_joined_guess(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    svg = tmp_path / 'input.svg'
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<g class="node"><text x="6" y="-9" font-size="14">Input</text>'
        '<text x="46" y="-9" font-weight="bold" font-size="14">Sensor</text></g>'
        '<g class="node"><text x="6" y="40" font-size="14">InputSensor</text></g></svg>'
    )
    registry = Registry()
    mod.register_diagram_tools(registry, None, None, None, None, None, lambda _: lambda f: f)
    result = registry.tools['add_diagram_references'](str(svg), {'InputSensor': 10, 'Input Sensor': 20})
    assert result['num_references'] == 2 and result['unmatched_labels'] == []


def test_guess_skips_a_label_another_node_matched_exactly(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    svg = tmp_path / 'input.svg'
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<g class="node"><text x="6" y="-9" font-size="14">Input</text>'
        '<text x="46" y="-9" font-weight="bold" font-size="14">Sensor</text></g>'
        '<g class="node"><text x="6" y="40" font-size="14">InputSensor</text></g></svg>'
    )
    registry = Registry()
    mod.register_diagram_tools(registry, None, None, None, None, None, lambda _: lambda f: f)
    result = registry.tools['add_diagram_references'](str(svg), {'InputSensor': 10})
    assert result['num_references'] == 1


@pytest.mark.parametrize(('content', 'references', 'count', 'unmatched'), [
    ('<g class="node"><text>Input</text><text>Sensor</text></g>', {'Input Sensor': 10}, 1, []),
    ('<text><tspan x="0">Input</tspan><tspan x="0" dy="1.2em">Sensor</tspan></text>', {'Input Sensor': 10}, 1, []),
    ('<text><tspan>Pro</tspan><tspan>cessor</tspan></text>', {'Processor': 10}, 1, []),
    ('<text><tspan>Pro</tspan><tspan dy="0">cessor</tspan></text>', {'Processor': 10}, 1, []),
    ('<text>V<tspan dy="3">out</tspan></text>', {'Vout': 10}, 1, []),
    ('<text>Con<tspan dx="-0.4">troller</tspan></text>', {'Controller': 10}, 1, []),
    ('<text><tspan x="0" y="10">Input</tspan><tspan x="0" y="24">Sensor</tspan></text>', {'Input Sensor': 10}, 1, []),
    ('<text x="0" y="10"><tspan>Input</tspan><tspan dx="-30" dy="14">Sensor</tspan></text>', {'Input Sensor': 10}, 1, []),
    ('<text><tspan>Input</tspan><tspan dy="1.2em">Sensor</tspan></text>', {'Input Sensor': 10}, 1, []),
    ('<text>Input<tspan dy="1e2">Sensor</tspan></text>', {'Input Sensor': 10}, 1, []),
    ('<text>Input<tspan dy="+14">Sensor</tspan></text>', {'Input Sensor': 10}, 1, []),
    ('<text font-size="10pt">Input<tspan dy="11">Sensor</tspan></text>', {'Input Sensor': 10}, 1, []),
    ('<text y="0">Input<tspan y="20">Sensor</tspan></text>', {'Input Sensor': 10}, 1, []),
    ('<text y="10">V<tspan y="13">out</tspan></text>', {'Vout': 10}, 1, []),
    ('<text>Input<tspan dy="calc(1em)">Sensor</tspan></text>', {'Input Sensor': 10}, 1, []),
    ('<text y="0">Input<tspan dy="14">Sensor</tspan><tspan y="0">Output</tspan></text>', {'Sensor Output': 10}, 1, []),
    ('<g font-size="8"><text y="0">Input<tspan dy="8">Sensor</tspan></text></g>', {'Input Sensor': 10}, 1, []),
    ('<g class="node"><text x="21" y="-13.95" font-size="14.00">V</text>'
     '<text x="31" y="-13.95" baseline-shift="sub" font-size="14.00">out</text>'
     '<text x="46" y="-13.95" font-size="14.00"> Stage</text></g>', {'Vout Stage': 10}, 1, []),
    ('<g class="node"><text x="0" y="-20">Input</text><text x="0" y="-5">Sensor</text></g>', {'Input Sensor': 10}, 1, []),
    ('<g class="node"><text text-anchor="start" x="6" y="-9.75" font-size="14.00">Input</text>'
     '<text text-anchor="start" x="42.5" y="-9.75" font-size="14.00">Sensor</text></g>', {'Input Sensor': 10}, 1, []),
    ('<g class="node"><text text-anchor="middle" x="22.25" y="-13.45" font-size="14.00">Input</text>'
     '<text text-anchor="middle" x="70.88" y="-13.45" font-size="14.00">Sensor</text></g>', {'Input Sensor': 10}, 1, []),
    ('<g class="node"><text x="6" y="-9.75" font-weight="bold" font-size="14.00">Input</text>'
     '<text x="46" y="-9.75" font-size="14.00">Sensor</text></g>', {'Input Sensor': 10}, 1, []),
    ('<g class="node"><text x="16" y="-13.95" font-size="14.00">In</text>'
     '<text x="27" y="-13.95" font-style="italic" font-size="14.00">put</text></g>', {'Input': 10}, 1, []),
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
