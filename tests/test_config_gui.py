"""Tests for the optional settings GUI.

The GUI is thin glue over the (already tested) config store, so these tests
cover the pure helpers and that the module imports without a display. The
widget-building path is exercised only when a Tk display is actually available
(skipped on headless CI).
"""

import pytest

from mcp_server import config_gui


def test_choice_display_roundtrip():
    assert config_gui._choice_display("") == "(default)"
    assert config_gui._choice_display("cu126") == "cu126"
    assert config_gui._choice_value("(default)") == ""
    assert config_gui._choice_value("cu126") == "cu126"


def test_module_imports_without_display():
    # Importing the module must never require tkinter or a display.
    assert callable(config_gui.launch)


def test_launch_builds_form_when_display_available(monkeypatch, tmp_path):
    monkeypatch.setenv("PATENT_CONFIG_DIR", str(tmp_path))
    try:
        import tkinter
    except Exception:  # pragma: no cover
        pytest.skip("tkinter not installed")
    try:
        tkinter.Tk().destroy()  # probe for a usable display
    except Exception:  # pragma: no cover - headless CI
        pytest.skip("no Tk display available")

    # Don't block on the event loop; just confirm the form builds cleanly.
    monkeypatch.setattr(tkinter.Tk, "mainloop", lambda self: None)
    assert config_gui.launch() == 0
