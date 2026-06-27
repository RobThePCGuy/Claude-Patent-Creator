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


def test_plan_save_persists_only_changed_validated_fields():
    from mcp_server import config

    opt_proj = config.OPTIONS_BY_KEY["GOOGLE_CLOUD_PROJECT"]
    opt_cap = config.OPTIONS_BY_KEY["PATENT_BIGQUERY_MAX_BYTES_BILLED"]
    opt_log = config.OPTIONS_BY_KEY["PATENT_LOG_LEVEL"]
    opt_cpu = config.OPTIONS_BY_KEY["FORCE_CPU"]

    entries = [
        (opt_proj, "secret-from-env", "secret-from-env"),  # unchanged -> not saved
        (opt_cap, "abc", str(25 * config.GIB)),            # changed but invalid
        (opt_log, "DEBUG", "INFO"),                        # changed + valid
        (opt_cpu, "true", "false"),                        # changed + valid
    ]
    to_save, errors = config_gui._plan_save(entries)

    # Unchanged env-sourced value is never written to disk; invalid is rejected.
    assert to_save == {"PATENT_LOG_LEVEL": "DEBUG", "FORCE_CPU": "true"}
    assert len(errors) == 1 and "cost cap" in errors[0].lower()


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
